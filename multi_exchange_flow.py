"""Live buy-vs-sell pressure from as many public exchange feeds as we can reach (information only - never used for buying).

Two reads per coin:
  * TRADE FLOW  - every trade printed on each venue is classified by who hit whom (the taker / aggressor side) and summed in
                  dollars over rolling windows (10s / 30s / 1m / 5m).  Buyers lifting offers = buy pressure.
  * BOOK DEPTH  - resting bid dollars vs resting ask dollars close to the mid price on each venue (who is stacked up where).

Public, key-less WebSocket / REST endpoints only.  Venues that are geo-blocked or silent simply drop out of the count.
Coinbase and Kraken trades are fed in by the dashboard's own sockets (hub.record), so they are not opened twice.

2026-10-20 upgrade (aggr.trade / Bookmap / Cryptometer style, see orderflow_engine.py):
  * NO DUPLICATE SALES - every trade carries the exchange's own trade id and is dropped if that id was already counted
    (exchanges re-send recent trades when a socket reconnects or subscribes: Crypto.com, Hyperliquid, BitMEX ...).
    Each exchange is opened by exactly ONE connection. Liquidations are tracked on their own and never added to the
    volume (a forced close is already a trade on the tape). Cryptometer numbers are context only, never added.
  * Coin quantity (BTC / XRP bought and sold) is kept next to the dollars, straight from each trade's own size.
  * More of the venues aggr.trade reads: Binance USD-M futures, BitMEX, Bitget futures (they drop out quietly where
    geo-blocked), plus streamed liquidations from Binance futures, Bybit, OKX, BitMEX and Deribit.
  * Binance spot now uses aggTrade (one row per taker order per price).
"""
import collections
import csv
import json
import os
import threading
import time
import urllib.request

try:
    import websocket
except Exception:  # pragma: no cover - the dashboard already requires it
    websocket = None

try:
    from orderflow_engine import ENGINE, _VENUE_LABELS
except ImportError:  # pragma: no cover - run from inside src/
    from orderflow_engine import ENGINE, _VENUE_LABELS

ASSETS = ("BTC", "XRP")
WINDOWS = (10, 30, 60, 300)
KEEP_SECONDS = 900
_ROOT = os.path.dirname(os.path.abspath(__file__))
PRESSURE_LOG = os.path.join(_ROOT, "bot_state", "pressure_log.csv")
INCOMING_LOG = os.path.join(_ROOT, "bot_state", "incoming_log.csv")

# venue -> (display label, kind)
VENUES = {
    "coinbase": ("Coinbase", "spot"), "kraken": ("Kraken", "spot"), "bitstamp": ("Bitstamp", "spot"),
    "gemini": ("Gemini", "spot"), "bitfinex": ("Bitfinex", "spot"), "cryptocom": ("Crypto.com", "spot"),
    "okx": ("OKX", "spot"), "bybit": ("Bybit", "spot"), "gate": ("Gate.io", "spot"), "bitget": ("Bitget", "spot"),
    "kucoin": ("KuCoin", "spot"), "binance": ("Binance", "spot"), "binanceus": ("Binance.US", "spot"),
    "okx_perp": ("OKX perp", "perp"), "bybit_perp": ("Bybit perp", "perp"), "hyperliquid": ("Hyperliquid perp", "perp"),
    "deribit": ("Deribit perp", "perp"),
    "binance_perp": ("Binance futures", "perp"), "bitmex": ("BitMEX perp", "perp"), "bitget_perp": ("Bitget perp", "perp"),
}
_VENUE_LABELS.update({k: v[0] for k, v in VENUES.items()})
DEDUP_KEEP = 60_000          # trade ids remembered per exchange (minutes of history even on the busiest venue)


class FlowHub:
    def __init__(self):
        self.lock = threading.Lock()
        self.buckets = {a: {} for a in ASSETS}      # asset -> {second: {venue: [buy_usd, sell_usd, n]}}
        self.last_seen = {}                         # (venue, asset) -> ts of last trade
        self.books = {}                             # (venue, asset) -> (ts, bid_usd, ask_usd)
        self.last_price = {}                        # (venue, asset) -> last trade price
        self._pruned = 0
        self._last_incoming = {}
        self.line = {}                              # asset -> {"ticker","strike"}: the Kalshi line of the round in progress
        self.line_vol = {}                          # asset -> {"ticker","above","below"} dollars traded on USD venues above / below the line
        self.on_trade = None                        # optional hook: fn(venue, asset, usd, side, price) for every trade
        self.bars = {a: {} for a in ASSETS}         # asset -> venue -> {minute: [open, close, usd_volume]} (for the composite RSI)
        self.deriv = {a: {} for a in ASSETS}        # asset -> funding / open interest / premium / liquidations (perp markets)
        self.oi_hist = {a: [] for a in ASSETS}      # asset -> [(ts, total open interest usd)]
        self._seen = {}                             # venue -> (set of (asset, trade id), deque in arrival order) - the de-dupe memory
        self.dupes = {}                             # venue -> duplicate trades dropped since start
        self.dupe_log = collections.deque()         # ts of every dropped duplicate (last 15 min shown on the page)
        self.accepted = 0
        self.engine = ENGINE

    # -------------------------------------------------------------- input
    def record(self, venue, asset, usd, side, price=None, qty=None, tid=None, ts_ms=None):
        """One trade. tid = the exchange's own trade id (or a unique fingerprint) - a trade whose id was already counted is
        DROPPED, so a reconnect / snapshot replay can never count the same sale twice. qty = coin amount (from the trade's
        own size, more exact than usd / price). ts_ms = the exchange's timestamp (groups fills into one taker order).
        Returns True when the trade was counted, False when it was a duplicate or invalid."""
        if asset not in self.buckets or not usd or usd <= 0 or side not in ("buy", "sell"):
            return False
        if not qty or qty <= 0:
            qty = (usd / price) if price else 0.0
        now = time.time()
        sec = int(now)
        with self.lock:
            if tid is not None and tid != "":
                st = self._seen.get(venue)
                if st is None:
                    st = self._seen[venue] = (set(), collections.deque())
                k = (asset, tid)
                if k in st[0]:
                    self.dupes[venue] = self.dupes.get(venue, 0) + 1
                    self.dupe_log.append(now)
                    return False
                st[0].add(k)
                st[1].append(k)
                if len(st[1]) > DEDUP_KEEP:
                    st[0].discard(st[1].popleft())
            self.accepted += 1
            b = self.buckets[asset]
            row = b.setdefault(sec, {}).setdefault(venue, [0.0, 0.0, 0, 0.0, 0.0])
            row[0 if side == "buy" else 1] += usd
            row[3 if side == "buy" else 4] += qty
            row[2] += 1
            self.last_seen[(venue, asset)] = now
            ln = self.line.get(asset)
            if ln and price and venue in ("coinbase", "kraken", "bitstamp", "gemini", "bitfinex", "cryptocom"):
                lv = self.line_vol.setdefault(asset, {"ticker": ln["ticker"], "above": 0.0, "below": 0.0})
                lv["above" if price >= ln["strike"] else "below"] += usd
            if price:
                self.last_price[(venue, asset)] = price
                mn = sec // 60
                vb = self.bars[asset].setdefault(venue, {})
                bar = vb.get(mn)
                if bar is None:
                    vb[mn] = [price, price, usd]
                else:
                    bar[1] = price; bar[2] += usd
            if sec - self._pruned >= 30:
                self._pruned = sec
                cutoff = sec - KEEP_SECONDS
                for a in self.buckets:
                    for k in [k for k in self.buckets[a] if k < cutoff]:
                        del self.buckets[a][k]
                    for vb in self.bars[a].values():
                        for k in [k for k in vb if k < sec // 60 - 200]:
                            del vb[k]
                while self.dupe_log and now - self.dupe_log[0] > 900:
                    self.dupe_log.popleft()
        eng = self.engine
        if eng is not None and price:
            try:
                eng.ingest(venue, asset, usd, qty, side, price, ts_ms, VENUES.get(venue, ("", "spot"))[1])
            except Exception:
                pass
        cb = self.on_trade
        if cb is not None:
            try:
                cb(venue, asset, usd, side, price)
            except Exception:
                pass
        return True

    def liquidation(self, venue, asset, liquidated, usd, price, ts_ms=None):
        """A forced close streamed by a perp exchange - handed to the engine for alerts / context ONLY. Never added to the
        buy / sell totals: the forced order is already printed on the trade tape, counting it again would double it."""
        eng = self.engine
        if eng is not None:
            try:
                eng.liquidation(venue, asset, liquidated, usd, price, ts_ms)
            except Exception:
                pass

    def set_book(self, venue, asset, bid_usd, ask_usd):
        with self.lock:
            self.books[(venue, asset)] = (time.time(), bid_usd, ask_usd)

    # -------------------------------------------------------------- output
    def summary(self, asset):
        now = time.time()
        sec_now = int(now)
        with self.lock:
            b = {s: {v: tuple(x) for v, x in vd.items()} for s, vd in self.buckets.get(asset, {}).items()}
            seen = {v: ts for (v, a), ts in self.last_seen.items() if a == asset}
            books = {v: x for (v, a), x in self.books.items() if a == asset}
        per = {}                         # venue -> {win: [buy, sell, n, buy_qty, sell_qty]}
        tot = {w: [0.0, 0.0, 0, 0.0, 0.0] for w in WINDOWS}
        for sec, vd in b.items():
            age = sec_now - sec
            for v, x in vd.items():
                bu, se, n, bq, sq = x[0], x[1], x[2], x[3], x[4]
                for w in WINDOWS:
                    if age < w:
                        t = tot[w]; t[0] += bu; t[1] += se; t[2] += n; t[3] += bq; t[4] += sq
                        p = per.setdefault(v, {}).setdefault(w, [0.0, 0.0, 0, 0.0, 0.0])
                        p[0] += bu; p[1] += se; p[2] += n; p[3] += bq; p[4] += sq
        wins = {}
        for w in WINDOWS:
            bu, se, n, bq, sq = tot[w]
            wins[w] = {"buy": bu, "sell": se, "n": n, "buy_qty": bq, "sell_qty": sq,
                       "pct": (bu / (bu + se)) if (bu + se) > 0 else None}
        venues = []
        for v in set(list(per) + list(books) + list(seen)):
            label, kind = VENUES.get(v, (v, "spot"))
            p60 = per.get(v, {}).get(60, [0.0, 0.0, 0, 0.0, 0.0])
            bk = books.get(v)
            book_pct = None
            if bk and now - bk[0] < 60 and (bk[1] + bk[2]) > 0:
                book_pct = bk[1] / (bk[1] + bk[2])
            venues.append({
                "key": v, "label": label, "kind": kind, "buy": p60[0], "sell": p60[1], "n": p60[2],
                "buy_qty": p60[3], "sell_qty": p60[4], "dupes": self.dupes.get(v, 0),
                "pct": (p60[0] / (p60[0] + p60[1])) if (p60[0] + p60[1]) > 0 else None,
                "live": (now - seen.get(v, 0)) < 120, "book_pct": book_pct,
            })
        venues.sort(key=lambda x: -(x["buy"] + x["sell"]))
        bids = sum(x[1] for x in books.values() if now - x[0] < 60)
        asks = sum(x[2] for x in books.values() if now - x[0] < 60)
        with self.lock:
            deriv = dict(self.deriv.get(asset, {}))
        return {
            "deriv": deriv,
            "wins": wins, "venues": venues,
            "live_n": sum(1 for x in venues if x["live"]),
            "book_pct": (bids / (bids + asks)) if (bids + asks) > 0 else None,
            "book_n": sum(1 for x in books.values() if now - x[0] < 60),
            "book_usd": bids + asks,
            "venues_total": len(VENUES),
            "dupes_15m": len(self.dupe_log),
            "dupes_total": sum(self.dupes.values()),
        }


    def volume_gauge(self, asset):
        """Live traded volume (dollars, every exchange) over the last 60s split buy / sell, with this market's own 'normal': the median
        and 95th percentile of the rolling 60s totals over the last ~14 minutes. Feeds the vertical volume bar beside the chart."""
        now = int(time.time())
        with self.lock:
            b = {s: [(x[0], x[1], x[3], x[4]) for x in vd.values()] for s, vd in self.buckets.get(asset, {}).items() if s >= now - 900}
        per = {s: (sum(r[0] for r in v), sum(r[1] for r in v)) for s, v in b.items()}
        perq = {s: (sum(r[2] for r in v), sum(r[3] for r in v)) for s, v in b.items()}

        def win(end, w=60):
            bu = se = 0.0
            for k in range(end - w + 1, end + 1):
                x = per.get(k)
                if x:
                    bu += x[0]; se += x[1]
            return bu, se
        bu, se = win(now)
        first = min(per) if per else now
        # only windows that lie fully inside the data we actually have (right after a start there is little history: no baseline yet)
        samples = sorted(sum(win(e)) for e in range(max(now - 840, first + 59), now - 59, 10))
        med = samples[len(samples) // 2] if len(samples) >= 6 else 0.0
        p95 = samples[int(len(samples) * 0.95)] if len(samples) >= 6 else 0.0
        bq = sum(perq[k][0] for k in range(now - 59, now + 1) if k in perq)
        sq = sum(perq[k][1] for k in range(now - 59, now + 1) if k in perq)
        return {"buy": bu, "sell": se, "total": bu + se, "median": med, "p95": p95, "prev": sum(win(now - 60)),
                "buy_qty": bq, "sell_qty": sq, "samples": len(samples)}

    INCOMING_FLOOR_USD = {"BTC": 3_000_000, "XRP": 400_000}   # one-sided 10-second push that counts as "huge"
    INCOMING_COOLDOWN = 45

    def incoming(self, asset):
        """A huge one-sided burst of taker flow across ALL exchanges in the last 10 seconds - an early warning that shows up
        before the chart moves. Fires once, then stays quiet for 45s. Needs >= the floor, >= 2.5x this market's own recent
        90th-percentile 10s push, and >= 65% of the 10s volume on one side. Returns an event dict or None."""
        now = int(time.time())
        with self.lock:
            b = {s: {v: tuple(x) for v, x in vd.items()} for s, vd in self.buckets.get(asset, {}).items() if s >= now - 900}
            last = self._last_incoming.get(asset)
        if last and now - last[0] < self.INCOMING_COOLDOWN:
            return None

        def sec(s):
            vd = b.get(s, {})
            return sum(x[0] for x in vd.values()), sum(x[1] for x in vd.values())
        per = {s: sec(s) for s in range(now - 899, now + 1)}

        def win(end):
            bu = sum(per[k][0] for k in range(end - 9, end + 1) if k in per)
            se = sum(per[k][1] for k in range(end - 9, end + 1) if k in per)
            return bu, se
        hist = sorted(abs(win(e)[0] - win(e)[1]) for e in range(now - 840, now - 10, 5))
        p90 = hist[int(len(hist) * 0.9)] if hist else 0.0
        bu, se = win(now)
        net, tot = bu - se, bu + se
        thr = max(self.INCOMING_FLOOR_USD.get(asset, 1e12), 2.5 * p90)
        if tot <= 0 or abs(net) < thr or max(bu, se) / tot < 0.65:
            return None
        side = "buy" if net > 0 else "sell"
        venues = {}
        for s in range(now - 9, now + 1):
            for v, x in b.get(s, {}).items():
                venues[v] = venues.get(v, 0.0) + (x[0] if side == "buy" else x[1])
        top = max(venues, key=venues.get) if venues else ""
        ev = {"side": side, "usd": abs(net), "venues": sum(1 for x in venues.values() if x > 0),
              "top": VENUES.get(top, (top, ""))[0], "ts": time.time(), "price": self.last_price.get(("coinbase", asset))}
        with self.lock:
            self._last_incoming[asset] = (now, side)
        try:
            os.makedirs(os.path.dirname(INCOMING_LOG), exist_ok=True)
            new = not os.path.exists(INCOMING_LOG)
            with open(INCOMING_LOG, "a", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                if new:
                    w.writerow(["ts_utc", "asset", "side", "net_usd_10s", "venues", "top_venue", "coinbase_price", "threshold_usd"])
                w.writerow([time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()), asset, side, f"{abs(net):.0f}", ev["venues"], ev["top"],
                            ev["price"], f"{thr:.0f}"])
        except Exception:
            pass
        return ev

    def set_line(self, asset, ticker, strike):
        """Tell the hub which Kalshi line (strike) the current round is about; the above / below tally restarts with each new round."""
        if not ticker or not strike:
            return
        with self.lock:
            cur = self.line.get(asset)
            if not cur or cur["ticker"] != ticker:
                self.line_vol[asset] = {"ticker": ticker, "above": 0.0, "below": 0.0}
            self.line[asset] = {"ticker": ticker, "strike": float(strike)}

    def line_volume(self, asset):
        with self.lock:
            v = self.line_vol.get(asset)
            return dict(v) if v else None

    def window_totals(self, asset, seconds, kind=None):
        """(buy_usd, sell_usd, trades) over the last `seconds` seconds, every exchange (or only 'spot' / only 'perp' venues)."""
        now = int(time.time())
        seconds = max(1, min(int(seconds), 900))
        bu = se = 0.0
        n = 0
        with self.lock:
            for s in range(now - seconds + 1, now + 1):
                vd = self.buckets.get(asset, {}).get(s)
                if vd:
                    for v, x in vd.items():
                        if kind and VENUES.get(v, ("", "spot"))[1] != kind:
                            continue
                        bu += x[0]; se += x[1]; n += x[2]
        return bu, se, n

    def window_detail(self, asset, seconds, kind=None, since_ts=None):
        """{buy, sell, n, buy_qty, sell_qty, venues} over the last `seconds` (or since `since_ts`), every exchange or one kind."""
        now = int(time.time())
        start = int(since_ts) if since_ts else now - max(1, min(int(seconds), 900)) + 1
        start = max(start, now - 899)
        bu = se = bq = sq = 0.0
        n = 0
        vs = set()
        with self.lock:
            for s in range(start, now + 1):
                vd = self.buckets.get(asset, {}).get(s)
                if not vd:
                    continue
                for v, x in vd.items():
                    if kind and VENUES.get(v, ("", "spot"))[1] != kind:
                        continue
                    bu += x[0]; se += x[1]; n += x[2]; bq += x[3]; sq += x[4]
                    vs.add(v)
        return {"buy": bu, "sell": se, "n": n, "buy_qty": bq, "sell_qty": sq, "venues": len(vs),
                "pct": (bu / (bu + se)) if (bu + se) > 0 else None}

    def cvd_series(self, asset, since_ts, step=10):
        """Cumulative volume delta (buy dollars minus sell dollars, every exchange) from since_ts to now in `step`-second
        points: [(ts, cvd_usd, cvd_coin)]. Rising = buyers have been the aggressors, falling = sellers."""
        now = int(time.time())
        start = max(int(since_ts), now - 899)
        out = []
        cu = cq = 0.0
        with self.lock:
            for s in range(start, now + 1):
                vd = self.buckets.get(asset, {}).get(s)
                if vd:
                    for x in vd.values():
                        cu += x[0] - x[1]; cq += x[3] - x[4]
                if (s - start) % step == step - 1 or s == now:
                    out.append((s, cu, cq))
        return out

    def feed_health(self):
        now = time.time()
        with self.lock:
            live = {v for (v, a), ts in self.last_seen.items() if now - ts < 120}
            return {"live": sorted(live), "n_live": len(live), "n_total": len(VENUES), "dupes_15m": len(self.dupe_log),
                    "dupes_total": sum(self.dupes.values()), "dupes_by_venue": dict(self.dupes), "accepted": self.accepted}

    def seed_bars(self, asset, venue, candles):
        """candles: {minute_start_ts: (o, h, l, c, usd_volume)} from REST history; live data wins where both exist."""
        with self.lock:
            vb = self.bars[asset].setdefault(venue, {})
            for ts, (o, h, l, cl, v) in candles.items():
                vb.setdefault(int(ts) // 60, [o, cl, v])

    def _composite_closes(self, asset, want=61):
        """Basis-neutral composite of every exchange: each minute's composite return is the volume-weighted average of each
        venue's OWN 1-minute return, so a constant USD-vs-USDT price offset cancels out. Returns [(minute, level)]."""
        cur = int(time.time()) // 60
        with self.lock:
            bars = {v: dict(b) for v, b in self.bars.get(asset, {}).items()}
        minutes = sorted({m for b in bars.values() for m in b if m < cur})[-want - 1:]
        closes, level = [], 1.0
        for i in range(1, len(minutes)):
            m, pm = minutes[i], minutes[i - 1]
            num = den = 0.0
            for b in bars.values():
                if m in b and pm in b and b[m][1] > 0 and b[pm][1] > 0:
                    w = max(b[m][2], 1.0)
                    num += w * (b[m][1] / b[pm][1] - 1.0); den += w
            if den > 0 and m - pm <= 3:
                level *= 1.0 + num / den
                closes.append((m, level))
        return closes

    @staticmethod
    def _rsi(closes, period=14):
        if len(closes) <= period + 5:
            return None
        gains = [max(closes[i] - closes[i - 1], 0.0) for i in range(1, period + 1)]
        losses = [max(closes[i - 1] - closes[i], 0.0) for i in range(1, period + 1)]
        ag, al = sum(gains) / period, sum(losses) / period
        for i in range(period + 1, len(closes)):
            ch = closes[i] - closes[i - 1]
            ag = (ag * (period - 1) + max(ch, 0.0)) / period
            al = (al * (period - 1) + max(-ch, 0.0)) / period
        return 100.0 if al == 0 else 100 - 100 / (1 + ag / al)

    def composite_rsi(self, asset, period=14, want=61):
        """RSI(14) of the all-exchange composite (1-minute). None until there are ~20 completed minutes of history."""
        return self._rsi([c for _, c in self._composite_closes(asset, want)], period)

    def rsi_multi(self, asset, period=14):
        """1-minute RSI, 5-minute RSI (from the same composite, 5-minute closes), the 1-minute RSI 3 minutes ago (is it
        turning?) and the composite % change over the last 10 minutes (for divergence against volume delta)."""
        cl = self._composite_closes(asset, want=195)
        c1 = [c for _, c in cl]
        r1 = self._rsi(c1[-61:], period) if c1 else None
        r1_prev = self._rsi(c1[-64:-3], period) if len(c1) > 30 else None
        c5 = [c for m, c in cl if m % 5 == 4]          # the close of each 5-minute candle
        r5 = self._rsi(c5, period) if len(c5) > period + 5 else None
        chg10 = (c1[-1] / c1[-11] - 1.0) * 100 if len(c1) >= 11 else None
        return {"rsi1": r1, "rsi5": r5, "rsi1_prev": r1_prev, "chg10_pct": chg10, "minutes": len(c1)}


HUB = FlowHub()
USD_VENUES = ("coinbase", "kraken", "bitstamp", "gemini", "bitfinex", "cryptocom")   # quoted in real dollars, so 'above / below the line' is fair


def _seed_history():
    """Fill ~90 minutes of 1-minute candles from the exchanges that serve history, so the composite RSI works right away."""
    try:
        import venue_vs_brti as vb
    except Exception:
        return
    now = int(time.time())
    for asset in ASSETS:
        for venue, fn in (("coinbase", vb.f_coinbase), ("bitstamp", vb.f_bitstamp), ("binance", vb.f_binance),
                          ("kucoin", vb.f_kucoin), ("okx", vb.f_okx), ("hyperliquid", vb.f_hyperliquid)):
            try:
                HUB.seed_bars(asset, venue, fn(asset, now - 95 * 60, now))
            except Exception:
                pass


# ====================================================================== trade feeds
def _f(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default


def _base(asset_symbol_map, sym):
    return asset_symbol_map.get(sym)


class _Feed:
    """One reconnecting WebSocket.  parse(msg_obj, ws, state) calls HUB.record(...)."""

    def __init__(self, name, url, subs, parse, ping=None, ping_every=15, url_fn=None, pre_sleep=0.0):
        self.name, self.url, self.subs, self.parse = name, url, subs, parse
        self.ping, self.ping_every, self.url_fn, self.pre_sleep = ping, ping_every, url_fn, pre_sleep
        self.state = {}

    def run_forever(self):
        backoff = 3
        while True:
            try:
                url = self.url_fn() if self.url_fn else self.url
                self.state = {}
                ws = websocket.WebSocketApp(url, on_open=self._open, on_message=self._msg,
                                            on_error=lambda w, e: None)
                ws.run_forever(ping_interval=20, ping_timeout=10)
            except Exception:
                pass
            time.sleep(backoff)
            backoff = min(60, backoff * 1.5)

    def _open(self, ws):
        def go():
            try:
                if self.pre_sleep:
                    time.sleep(self.pre_sleep)
                for s in self.subs:
                    ws.send(s if isinstance(s, str) else json.dumps(s))
                while ws.keep_running and self.ping is not None:
                    time.sleep(self.ping_every)
                    ws.send(self.ping if isinstance(self.ping, str) else json.dumps(self.ping))
            except Exception:
                pass
        threading.Thread(target=go, daemon=True).start()

    def _msg(self, ws, m):
        try:
            if isinstance(m, str) and m in ("pong", "ping"):
                return
            self.parse(json.loads(m), ws, self.state)
        except Exception:
            pass


def _ms(x):
    """Exchange timestamp -> integer milliseconds (accepts s / ms / us / ns numbers or numeric strings)."""
    try:
        v = float(x)
    except Exception:
        return None
    if v <= 0:
        return None
    while v > 1e14:          # us / ns -> ms
        v /= 1000.0
    if v < 1e11:             # seconds -> ms
        v *= 1000.0
    return int(v)


def _iso_ms(x):
    try:
        import datetime as _dt
        return int(_dt.datetime.fromisoformat(str(x).replace("Z", "+00:00")).timestamp() * 1000)
    except Exception:
        return None


def _bybit(venue):
    sym = {"BTCUSDT": "BTC", "XRPUSDT": "XRP"}

    def parse(d, ws, st):
        topic = str(d.get("topic", ""))
        if topic.startswith("publicTrade"):
            for t in d.get("data", []):
                a = sym.get(t.get("s"))
                if a:
                    p, q = _f(t["p"]), _f(t["v"])
                    HUB.record(venue, a, p * q, "buy" if t["S"] == "Buy" else "sell", p, qty=q, tid=t.get("i"), ts_ms=_ms(t.get("T")))
        elif topic.startswith("allLiquidation"):
            # S = side of the LIQUIDATED position: Buy = a long was liquidated (force-sold), Sell = a short (force-bought)
            for t in d.get("data", []):
                a = sym.get(t.get("s"))
                if a:
                    p, q = _f(t.get("p")), _f(t.get("v"))
                    HUB.liquidation(venue, a, "long" if t.get("S") == "Buy" else "short", p * q, p, _ms(t.get("T")))
    return parse


_OKX_INST = {"BTC-USDT-SWAP": ("okx_perp", "BTC", 0.01), "XRP-USDT-SWAP": ("okx_perp", "XRP", 100.0),
             "BTC-USDT": ("okx", "BTC", 1.0), "XRP-USDT": ("okx", "XRP", 1.0)}


def _okx(d, ws, st):
    ch = d.get("arg", {}).get("channel")
    if ch == "trades":
        for t in d.get("data", []):
            m = _OKX_INST.get(t.get("instId"))
            if m:
                p, q = _f(t["px"]), _f(t["sz"]) * m[2]
                HUB.record(m[0], m[1], p * q, "buy" if t["side"] == "buy" else "sell", p, qty=q, tid=t.get("tradeId"), ts_ms=_ms(t.get("ts")))
    elif ch == "liquidation-orders":
        for blk in d.get("data", []):
            m = _OKX_INST.get(blk.get("instId"))
            if not m or m[0] != "okx_perp":
                continue
            for t in blk.get("details", []):
                p, q = _f(t.get("bkPx")), _f(t.get("sz")) * m[2]
                # the liquidation ORDER side: sell = a long being closed out, buy = a short
                liq = "long" if (t.get("posSide") == "long" or (t.get("posSide") in (None, "", "net") and t.get("side") == "sell")) else "short"
                HUB.liquidation("okx_perp", m[1], liq, p * q, p, _ms(t.get("ts")))


def _bitstamp(d, ws, st):
    if d.get("event") == "trade":
        a = {"live_trades_btcusd": "BTC", "live_trades_xrpusd": "XRP"}.get(d.get("channel"))
        t = d.get("data", {})
        if a:
            p, q = _f(t.get("price")), _f(t.get("amount"))
            HUB.record("bitstamp", a, p * q, "buy" if t.get("type") == 0 else "sell", p, qty=q, tid=t.get("id"),
                       ts_ms=_ms(t.get("microtimestamp") or t.get("timestamp")))


def _gemini(d, ws, st):
    if d.get("type") == "trade":          # the l2 snapshot's "trades" list (old prints) is deliberately ignored
        a = {"BTCUSD": "BTC", "XRPUSD": "XRP"}.get(d.get("symbol"))
        if a:
            p, q = _f(d["price"]), _f(d["quantity"])
            HUB.record("gemini", a, p * q, "buy" if d.get("side") == "buy" else "sell", p, qty=q,
                       tid=d.get("event_id") or d.get("tid"), ts_ms=_ms(d.get("timestamp")))


def _bitfinex(d, ws, st):
    if isinstance(d, dict):
        if d.get("event") == "subscribed" and d.get("channel") == "trades":
            st[d["chanId"]] = {"tBTCUSD": "BTC", "tXRPUSD": "XRP"}.get(d.get("symbol"))
        return
    # [chan, "te", [ID, MTS, AMOUNT, PRICE]] - the snapshot (a list of old trades) and "tu" repeats are ignored
    if isinstance(d, list) and len(d) >= 3 and d[1] == "te" and st.get(d[0]):
        tid, mts, amt, p = d[2][0], d[2][1], _f(d[2][2]), _f(d[2][3])
        HUB.record("bitfinex", st[d[0]], abs(amt) * p, "buy" if amt > 0 else "sell", p, qty=abs(amt), tid=tid, ts_ms=_ms(mts))


def _cryptocom(d, ws, st):
    if d.get("method") == "public/heartbeat":
        ws.send(json.dumps({"id": d["id"], "method": "public/respond-heartbeat"}))
        return
    r = d.get("result") or {}
    if r.get("channel") == "trade":
        a = {"BTC_USD": "BTC", "XRP_USD": "XRP"}.get(r.get("instrument_name"))
        if a:
            # the first message after subscribing replays recent trades - the trade id ("d") de-dupe drops any already counted
            for t in r.get("data", []):
                p, q = _f(t["p"]), _f(t["q"])
                HUB.record("cryptocom", a, p * q, "buy" if t.get("s") == "BUY" else "sell", p, qty=q,
                           tid=t.get("d") or t.get("i"), ts_ms=_ms(t.get("t")))


def _gate(d, ws, st):
    if d.get("channel") == "spot.trades" and d.get("event") == "update":
        t = d.get("result") or {}
        a = {"BTC_USDT": "BTC", "XRP_USDT": "XRP"}.get(t.get("currency_pair"))
        if a:
            p, q = _f(t["price"]), _f(t["amount"])
            HUB.record("gate", a, p * q, "buy" if t.get("side") == "buy" else "sell", p, qty=q, tid=t.get("id"),
                       ts_ms=_ms(t.get("create_time_ms") or t.get("create_time")))


def _bitget(d, ws, st):
    arg = d.get("arg", {})
    if arg.get("channel") == "trade" and d.get("action") != "snapshot":
        a = {"BTCUSDT": "BTC", "XRPUSDT": "XRP"}.get(arg.get("instId"))
        venue = "bitget_perp" if arg.get("instType") == "USDT-FUTURES" else "bitget"
        if a:
            for t in d.get("data", []):
                p, q = _f(t["price"]), _f(t["size"])
                HUB.record(venue, a, p * q, "buy" if t.get("side") == "buy" else "sell", p, qty=q, tid=t.get("tradeId"), ts_ms=_ms(t.get("ts")))


def _hyperliquid(d, ws, st):
    if d.get("channel") == "trades" and isinstance(d.get("data"), list):
        # Hyperliquid replays recent trades right after subscribing - "tid" de-dupes them against what was already counted
        for t in d["data"]:
            a = t.get("coin")
            if a in ASSETS:
                p, q = _f(t["px"]), _f(t["sz"])
                HUB.record("hyperliquid", a, p * q, "buy" if t.get("side") == "B" else "sell", p, qty=q, tid=t.get("tid") or t.get("hash"),
                           ts_ms=_ms(t.get("time")))


def _kucoin(d, ws, st):
    if d.get("subject") == "trade.l3match":
        t = d.get("data") or {}
        a = {"BTC-USDT": "BTC", "XRP-USDT": "XRP"}.get(t.get("symbol"))
        if a:
            p, q = _f(t["price"]), _f(t["size"])
            HUB.record("kucoin", a, p * q, "buy" if t.get("side") == "buy" else "sell", p, qty=q, tid=t.get("tradeId"), ts_ms=_ms(t.get("time")))


def _deribit(d, ws, st):
    if d.get("method") == "subscription":
        for t in d.get("params", {}).get("data", []):
            if t.get("instrument_name") == "BTC-PERPETUAL":      # amount is in USD for the perpetual
                usd, p = _f(t["amount"]), _f(t.get("price"))
                side = "buy" if t.get("direction") == "buy" else "sell"
                HUB.record("deribit", "BTC", usd, side, p, qty=(usd / p if p else None), tid=t.get("trade_id"), ts_ms=_ms(t.get("timestamp")))
                if t.get("liquidation"):          # a trade where a position was force-closed: the taker side is the liquidated one
                    HUB.liquidation("deribit", "BTC", "long" if side == "sell" else "short", usd, p, _ms(t.get("timestamp")))


def _binance_parser(venue):
    def parse(d, ws, st):
        t = d.get("data", d)
        e = t.get("e")
        if e in ("aggTrade", "trade"):
            a = {"BTCUSDT": "BTC", "XRPUSDT": "XRP"}.get(t.get("s"))
            if a:
                p, q = _f(t["p"]), _f(t["q"])      # m = buyer is the maker -> the taker SOLD
                tid = t.get("a") if e == "aggTrade" else t.get("t")
                HUB.record(venue, a, p * q, "sell" if t.get("m") else "buy", p, qty=q, tid=tid, ts_ms=_ms(t.get("T")))
        elif e == "forceOrder":
            o = t.get("o") or {}
            a = {"BTCUSDT": "BTC", "XRPUSDT": "XRP"}.get(o.get("s"))
            if a:
                p = _f(o.get("ap")) or _f(o.get("p"))
                q = _f(o.get("z")) or _f(o.get("q"))
                # S = side of the liquidation ORDER: SELL = a long being force-sold
                HUB.liquidation(venue, a, "long" if o.get("S") == "SELL" else "short", p * q, p, _ms(o.get("T")))
    return parse


_binance = _binance_parser("binance")


def _bitmex(d, ws, st):
    """BitMEX XBTUSD (inverse: size is in USD). The first 'partial' message replays old trades - skipped; ids de-dupe too."""
    tbl, act = d.get("table"), d.get("action")
    if tbl == "trade" and act == "insert":
        for t in d.get("data", []):
            if t.get("symbol") == "XBTUSD":
                usd, p = _f(t.get("size")), _f(t.get("price"))
                HUB.record("bitmex", "BTC", usd, "buy" if t.get("side") == "Buy" else "sell", p, qty=(usd / p if p else None),
                           tid=t.get("trdMatchID"), ts_ms=_iso_ms(t.get("timestamp")))
    elif tbl == "liquidation" and act == "insert":
        for t in d.get("data", []):
            if t.get("symbol") == "XBTUSD" and t.get("orderID") not in st.setdefault("liq_ids", set()):
                st["liq_ids"].add(t.get("orderID"))
                usd, p = _f(t.get("leavesQty")), _f(t.get("price"))
                HUB.liquidation("bitmex", "BTC", "long" if t.get("side") == "Sell" else "short", usd, p)


def _binanceus_poll_loop():
    """Binance.US streams are silent from here, so poll its public REST trades (new trades since the last id)."""
    last = {}
    time.sleep(3)
    while True:
        for a in ASSETS:
            try:
                rows = _get(f"https://api.binance.us/api/v3/trades?symbol={a}USDT&limit=200")
                prev = last.get(a)
                for r in rows:
                    if prev is not None and r["id"] > prev:
                        p, q = _f(r["price"]), _f(r["qty"])
                        HUB.record("binanceus", a, p * q, "sell" if r["isBuyerMaker"] else "buy", p, qty=q, tid=r["id"], ts_ms=_ms(r.get("time")))
                if rows:
                    last[a] = max(r["id"] for r in rows)
            except Exception:
                pass
        time.sleep(3.5)


def _kucoin_url():
    req = urllib.request.Request("https://api.kucoin.com/api/v1/bullet-public", data=b"", method="POST")
    j = json.loads(urllib.request.urlopen(req, timeout=10).read())
    s = j["data"]["instanceServers"][0]
    return f'{s["endpoint"]}?token={j["data"]["token"]}'


def _feeds():
    """ONE connection per exchange market - never two sockets for the same venue (that would double its trades)."""
    return [
        # Binance's official public market-data-only endpoint (the main api/stream hosts refuse US addresses)
        _Feed("binance", "wss://data-stream.binance.vision/stream?streams=btcusdt@aggTrade/xrpusdt@aggTrade", [], _binance),
        # Binance USD-M futures - the biggest BTC market aggr.trade reads. Refuses US addresses: then it just stays silent.
        _Feed("binance_perp", "wss://fstream.binance.com/stream?streams=btcusdt@aggTrade/xrpusdt@aggTrade/btcusdt@forceOrder/xrpusdt@forceOrder",
              [], _binance_parser("binance_perp")),
        _Feed("bybit", "wss://stream.bybit.com/v5/public/spot",
              [{"op": "subscribe", "args": ["publicTrade.BTCUSDT", "publicTrade.XRPUSDT"]}], _bybit("bybit"), ping={"op": "ping"}),
        _Feed("bybit_perp", "wss://stream.bybit.com/v5/public/linear",
              [{"op": "subscribe", "args": ["publicTrade.BTCUSDT", "publicTrade.XRPUSDT"]},
               {"op": "subscribe", "args": ["allLiquidation.BTCUSDT", "allLiquidation.XRPUSDT"]}],
              _bybit("bybit_perp"), ping={"op": "ping"}),
        _Feed("okx", "wss://ws.okx.com:8443/ws/v5/public",
              [{"op": "subscribe", "args": [{"channel": "trades", "instId": i} for i in ("BTC-USDT", "XRP-USDT", "BTC-USDT-SWAP", "XRP-USDT-SWAP")]},
               {"op": "subscribe", "args": [{"channel": "liquidation-orders", "instType": "SWAP"}]}],
              _okx, ping="ping", ping_every=20),
        _Feed("bitstamp", "wss://ws.bitstamp.net",
              [{"event": "bts:subscribe", "data": {"channel": c}} for c in ("live_trades_btcusd", "live_trades_xrpusd")], _bitstamp),
        _Feed("gemini", "wss://api.gemini.com/v2/marketdata",
              [{"type": "subscribe", "subscriptions": [{"name": "l2", "symbols": ["BTCUSD", "XRPUSD"]}]}], _gemini),
        _Feed("bitfinex", "wss://api-pub.bitfinex.com/ws/2",
              [{"event": "subscribe", "channel": "trades", "symbol": s} for s in ("tBTCUSD", "tXRPUSD")], _bitfinex),
        _Feed("cryptocom", "wss://stream.crypto.com/exchange/v1/market",
              [{"id": 1, "method": "subscribe", "params": {"channels": ["trade.BTC_USD", "trade.XRP_USD"]}}], _cryptocom, pre_sleep=1.0),
        _Feed("gate", "wss://api.gateio.ws/ws/v4/",
              [{"time": int(time.time()), "channel": "spot.trades", "event": "subscribe", "payload": ["BTC_USDT", "XRP_USDT"]}],
              _gate, ping={"channel": "spot.ping"}),
        _Feed("bitget", "wss://ws.bitget.com/v2/ws/public",
              [{"op": "subscribe", "args": [{"instType": "SPOT", "channel": "trade", "instId": i} for i in ("BTCUSDT", "XRPUSDT")]},
               {"op": "subscribe", "args": [{"instType": "USDT-FUTURES", "channel": "trade", "instId": i} for i in ("BTCUSDT", "XRPUSDT")]}],
              _bitget, ping="ping", ping_every=25),
        _Feed("hyperliquid", "wss://api.hyperliquid.xyz/ws",
              [{"method": "subscribe", "subscription": {"type": "trades", "coin": c}} for c in ("BTC", "XRP")],
              _hyperliquid, ping={"method": "ping"}, ping_every=30),
        _Feed("kucoin", None,
              [{"id": 1, "type": "subscribe", "topic": "/market/match:BTC-USDT,XRP-USDT", "response": True}],
              _kucoin, ping={"id": 2, "type": "ping"}, ping_every=15, url_fn=_kucoin_url),
        _Feed("deribit", "wss://www.deribit.com/ws/api/v2",
              [{"jsonrpc": "2.0", "id": 1, "method": "public/subscribe", "params": {"channels": ["trades.BTC-PERPETUAL.100ms"]}}], _deribit),
        _Feed("bitmex", "wss://ws.bitmex.com/realtime?subscribe=trade:XBTUSD,liquidation:XBTUSD", [], _bitmex, ping="ping", ping_every=20),
    ]


# ====================================================================== MATH CHECK vs each exchange's own numbers
# 2026-10-20 per user request ("do one more math check ... to ensure that it's correct"): every 5 minutes, ask each exchange
# for ITS OWN 24-hour BTC volume and compare it with what we counted from that exchange over the last 15 minutes, plus each
# exchange's last trade price vs Coinbase. Same numbers aggr.trade / Bookmap / TradingView show, straight from the source.
# A venue counting wildly more than its own average (a units bug, or double counting) is flagged on the page.
VOL24 = {}            # venue -> {"btc": 24h volume in BTC, "ts": fetched at}


def _v24_fetchers():
    def hl():
        j = _get("https://api.hyperliquid.xyz/info", json.dumps({"type": "metaAndAssetCtxs"}).encode(), {"Content-Type": "application/json"})
        names = [u["name"] for u in j[0]["universe"]]
        x = j[1][names.index("BTC")]
        return _f(x["dayNtlVlm"]) / max(_f(x["markPx"]), 1.0)
    return {
        "coinbase": lambda: _f(_get("https://api.exchange.coinbase.com/products/BTC-USD/stats")["volume"]),
        "kraken": lambda: _f(next(iter(_get("https://api.kraken.com/0/public/Ticker?pair=XBTUSD")["result"].values()))["v"][1]),
        "bitstamp": lambda: _f(_get("https://www.bitstamp.net/api/v2/ticker/btcusd/")["volume"]),
        "gemini": lambda: _f(_get("https://api.gemini.com/v1/pubticker/btcusd")["volume"]["BTC"]),
        "bitfinex": lambda: abs(_f(_get("https://api-pub.bitfinex.com/v2/ticker/tBTCUSD")[7])),
        "cryptocom": lambda: _f(_get("https://api.crypto.com/exchange/v1/public/get-tickers?instrument_name=BTC_USD")["result"]["data"][0]["v"]),
        "okx": lambda: _f(_get("https://www.okx.com/api/v5/market/ticker?instId=BTC-USDT")["data"][0]["vol24h"]),
        "okx_perp": lambda: _f(_get("https://www.okx.com/api/v5/market/ticker?instId=BTC-USDT-SWAP")["data"][0]["volCcy24h"]),
        "bybit": lambda: _f(_get("https://api.bybit.com/v5/market/tickers?category=spot&symbol=BTCUSDT")["result"]["list"][0]["volume24h"]),
        "bybit_perp": lambda: _f(_get("https://api.bybit.com/v5/market/tickers?category=linear&symbol=BTCUSDT")["result"]["list"][0]["volume24h"]),
        "gate": lambda: _f(_get("https://api.gateio.ws/api/v4/spot/tickers?currency_pair=BTC_USDT")[0]["base_volume"]),
        "bitget": lambda: _f(_get("https://api.bitget.com/api/v2/spot/market/tickers?symbol=BTCUSDT")["data"][0]["baseVolume"]),
        "bitget_perp": lambda: _f(_get("https://api.bitget.com/api/v2/mix/market/ticker?symbol=BTCUSDT&productType=USDT-FUTURES")["data"][0]["baseVolume"]),
        "kucoin": lambda: _f(_get("https://api.kucoin.com/api/v1/market/stats?symbol=BTC-USDT")["data"]["vol"]),
        "binance": lambda: _f(_get("https://data-api.binance.vision/api/v3/ticker/24hr?symbol=BTCUSDT")["volume"]),
        "binanceus": lambda: _f(_get("https://api.binance.us/api/v3/ticker/24hr?symbol=BTCUSDT")["volume"]),
        "binance_perp": lambda: _f(_get("https://fapi.binance.com/fapi/v1/ticker/24hr?symbol=BTCUSDT")["volume"]),
        "deribit": lambda: _f(_get("https://www.deribit.com/api/v2/public/ticker?instrument_name=BTC-PERPETUAL")["result"]["stats"]["volume"]),
        "hyperliquid": hl,
    }


def _v24_loop():
    time.sleep(15)
    while True:
        for v, fn in _v24_fetchers().items():
            try:
                x = fn()
                if x and x > 0:
                    VOL24[v] = {"btc": x, "ts": time.time()}
            except Exception:
                pass
            time.sleep(0.3)
        time.sleep(300)


def math_check(asset="BTC"):
    """Per exchange: BTC we counted in the last 15 min vs that exchange's own average 15 min (its 24h volume / 96), and its
    last price vs Coinbase. ratio 0.2x-6x is normal (markets are busier at some hours and in fast moves); above 10x on a
    calm market points to a counting / units bug, which the page flags."""
    now = int(time.time())
    with HUB.lock:
        got = {}
        first = {}
        for s_, vd in HUB.buckets.get(asset, {}).items():
            if s_ < now - 899:
                continue
            for v, x in vd.items():
                got[v] = got.get(v, 0.0) + x[3] + x[4]
                first[v] = min(first.get(v, s_), s_)
        px = {v: p for (v, a), p in HUB.last_price.items() if a == asset}
    ref = px.get("coinbase")
    rows = []
    for v, q in got.items():
        span = max(60, now - first[v] + 1)
        vv = VOL24.get(v)
        norm = vv["btc"] / 86400 * span if vv else None
        ratio = (q / norm) if norm else None
        pdiff = ((px[v] / ref - 1) * 100) if (ref and px.get(v)) else None
        settled = span >= 300                                     # judge only after 5+ minutes of counting
        flag = ((settled and ratio is not None and ratio > 10 and q > 2)
                or (settled and ratio is not None and norm >= 5 and ratio < 0.05)
                or (pdiff is not None and abs(pdiff) > 0.5))
        rows.append({"venue": v, "label": VENUES.get(v, (v, ""))[0], "kind": VENUES.get(v, ("", "spot"))[1], "counted": q, "span": span,
                     "normal": norm, "ratio": ratio, "pdiff": pdiff, "flag": flag})
    rows.sort(key=lambda r: -r["counted"])
    tot_c = sum(r["counted"] for r in rows if r["normal"])
    tot_n = sum(r["normal"] for r in rows if r["normal"])
    return {"rows": rows, "ratio": (tot_c / tot_n) if tot_n else None, "checked": sum(1 for r in rows if r["normal"]),
            "flags": [r for r in rows if r["flag"]]}


# ====================================================================== perp-market extras (funding, open interest, liquidations)
_OKX_CT = {"BTC": 0.01, "XRP": 100.0}


def _deriv_loop():
    """Every 30s: perp funding rate, total open interest (and its 5-minute change), perp premium to spot, and recent forced
    liquidations - from Hyperliquid + OKX (+ Deribit for BTC).  Positioning context that raw trades do not show."""
    time.sleep(5)
    while True:
        try:
            hl = _get("https://api.hyperliquid.xyz/info", json.dumps({"type": "metaAndAssetCtxs"}).encode(),
                      {"Content-Type": "application/json"})
            names = [u["name"] for u in hl[0]["universe"]]
        except Exception:
            hl, names = None, []
        for a in ASSETS:
            d = {}
            oi_total = 0.0
            try:
                if a in names:
                    x = hl[1][names.index(a)]
                    mark = _f(x["markPx"])
                    d["funding_hl"] = _f(x["funding"])            # per hour
                    d["premium_pct"] = _f(x["premium"]) * 100
                    oi_total += _f(x["openInterest"]) * mark
            except Exception:
                pass
            try:
                inst = f"{a}-USDT-SWAP"
                d["funding_okx"] = _f(_get(f"https://www.okx.com/api/v5/public/funding-rate?instId={inst}")["data"][0]["fundingRate"])   # per 8h
                oi_total += _f(_get(f"https://www.okx.com/api/v5/public/open-interest?instId={inst}")["data"][0]["oiUsd"])
            except Exception:
                pass
            if a == "BTC":
                try:
                    r = _get("https://www.deribit.com/api/v2/public/ticker?instrument_name=BTC-PERPETUAL")["result"]
                    oi_total += _f(r.get("open_interest"))        # already USD
                except Exception:
                    pass
            try:
                liq = _get(f"https://www.okx.com/api/v5/public/liquidation-orders?instType=SWAP&instFamily={a}-USDT&state=filled")["data"]
                now_ms = time.time() * 1000
                longs = shorts = 0.0
                for blk in liq:
                    for t in blk.get("details", []):
                        if now_ms - _f(t.get("ts")) <= 300000:
                            usd = _f(t["sz"]) * _OKX_CT[a] * _f(t["bkPx"])
                            if t.get("posSide") == "long":
                                longs += usd        # longs force-sold = selling pressure
                            else:
                                shorts += usd       # shorts force-bought = buying pressure
                d["liq_long_usd_5m"], d["liq_short_usd_5m"] = longs, shorts
            except Exception:
                pass
            now = time.time()
            if oi_total > 0:
                h = HUB.oi_hist[a]
                h.append((now, oi_total))
                while h and now - h[0][0] > 1800:
                    h.pop(0)
                old = [v for t, v in h if now - t >= 270]
                d["oi_usd"] = oi_total
                d["oi_chg_5m_pct"] = ((oi_total - old[-1]) / old[-1] * 100) if old else None
            with HUB.lock:
                HUB.deriv[a].update(d)
        time.sleep(30)


# ====================================================================== order-book depth (REST, polled)
_tls = threading.local()


def _get(url, data=None, headers=None):
    """JSON GET (or POST when data is given) over a KEEP-ALIVE session, one per thread. A fresh urllib request per call
    re-did the TLS handshake and re-loaded the CA bundle every time (found 2026-10-10: ~5 requests/s from these pollers
    starved the dashboard's own refresh loop); a reused connection costs almost nothing."""
    import requests
    s = getattr(_tls, "s", None)
    if s is None:
        s = requests.Session()
        s.headers.update({"User-Agent": "kalshi-dashboard"})
        _tls.s = s
    try:
        if data is not None:
            r = s.post(url, data=data, headers=headers or {}, timeout=8)
        else:
            r = s.get(url, headers=headers or {}, timeout=8)
        r.raise_for_status()
        return r.json()
    except Exception:
        _tls.s = None          # rebuild the session next time
        raise


def _book_usd(bids, asks, mult=1.0, usd_qty=False):
    """bids / asks: [(price, qty)].  Resting dollars within the band both sides actually reach (max 0.25% from mid)."""
    bids = [(float(p), float(q) * mult) for p, q in bids if float(q) > 0]
    asks = [(float(p), float(q) * mult) for p, q in asks if float(q) > 0]
    if not bids or not asks:
        return None
    bb, ba = max(p for p, _ in bids), min(p for p, _ in asks)
    mid = (bb + ba) / 2
    if mid <= 0 or ba < bb:
        return None
    reach = min((mid - min(p for p, _ in bids)) / mid, (max(p for p, _ in asks) - mid) / mid, 0.0025)
    if reach < 0.00015:     # book too shallow to say anything (1.5 bps: drops KuCoin's 20-level book, keeps dense BTC books)
        return None
    lo, hi = mid * (1 - reach), mid * (1 + reach)
    if usd_qty:
        return (sum(q for p, q in bids if p >= lo), sum(q for p, q in asks if p <= hi))
    return (sum(p * q for p, q in bids if p >= lo), sum(p * q for p, q in asks if p <= hi))


def _pairs(rows, i=0, j=1):
    return [(r[i], r[j]) for r in rows]


def _book_coinbase(a):
    j = _get(f"https://api.exchange.coinbase.com/products/{a}-USD/book?level=2")
    return _book_usd(_pairs(j["bids"]), _pairs(j["asks"]))


def _book_binance(a):
    j = _get(f"https://data-api.binance.vision/api/v3/depth?symbol={a}USDT&limit=500")
    return _book_usd(_pairs(j["bids"]), _pairs(j["asks"]))


def _book_binanceus(a):
    j = _get(f"https://api.binance.us/api/v3/depth?symbol={a}USDT&limit=500")
    return _book_usd(_pairs(j["bids"]), _pairs(j["asks"]))


def _book_kraken(a):
    j = _get(f"https://api.kraken.com/0/public/Depth?pair={'XBT' if a == 'BTC' else 'XRP'}USD&count=100")
    r = next(iter(j["result"].values()))
    return _book_usd(_pairs(r["bids"]), _pairs(r["asks"]))


def _book_bitstamp(a):
    j = _get(f"https://www.bitstamp.net/api/v2/order_book/{a.lower()}usd/")
    return _book_usd(_pairs(j["bids"][:200]), _pairs(j["asks"][:200]))


def _book_gemini(a):
    j = _get(f"https://api.gemini.com/v1/book/{a.lower()}usd?limit_bids=100&limit_asks=100")
    return _book_usd([(x["price"], x["amount"]) for x in j["bids"]], [(x["price"], x["amount"]) for x in j["asks"]])


def _book_okx(a):
    d = _get(f"https://www.okx.com/api/v5/market/books?instId={a}-USDT&sz=400")["data"][0]
    return _book_usd(_pairs(d["bids"]), _pairs(d["asks"]))


def _book_okx_perp(a):
    d = _get(f"https://www.okx.com/api/v5/market/books?instId={a}-USDT-SWAP&sz=400")["data"][0]
    return _book_usd(_pairs(d["bids"]), _pairs(d["asks"]), mult=0.01 if a == "BTC" else 100.0)


def _book_bitfinex(a):
    j = _get(f"https://api-pub.bitfinex.com/v2/book/t{a}USD/P0?len=100")
    return _book_usd([(r[0], r[2]) for r in j if r[2] > 0], [(r[0], -r[2]) for r in j if r[2] < 0])


def _book_gate(a):
    j = _get(f"https://api.gateio.ws/api/v4/spot/order_book?currency_pair={a}_USDT&limit=100")
    return _book_usd(_pairs(j["bids"]), _pairs(j["asks"]))


def _book_bitget(a):
    d = _get(f"https://api.bitget.com/api/v2/spot/market/orderbook?symbol={a}USDT&limit=100")["data"]
    return _book_usd(_pairs(d["bids"]), _pairs(d["asks"]))


def _book_kucoin(a):
    d = _get(f"https://api.kucoin.com/api/v1/market/orderbook/level2_20?symbol={a}-USDT")["data"]
    return _book_usd(_pairs(d["bids"]), _pairs(d["asks"]))


def _book_cryptocom(a):
    d = _get(f"https://api.crypto.com/exchange/v1/public/get-book?instrument_name={a}_USD&depth=50")["result"]["data"][0]
    return _book_usd(_pairs(d["bids"]), _pairs(d["asks"]))


def _book_hyperliquid(a):
    j = _get("https://api.hyperliquid.xyz/info", json.dumps({"type": "l2Book", "coin": a}).encode(), {"Content-Type": "application/json"})
    return _book_usd([(x["px"], x["sz"]) for x in j["levels"][0]], [(x["px"], x["sz"]) for x in j["levels"][1]])


def _book_deribit(a):
    if a != "BTC":
        return None
    r = _get("https://www.deribit.com/api/v2/public/get_order_book?instrument_name=BTC-PERPETUAL&depth=50")["result"]
    return _book_usd(_pairs(r["bids"]), _pairs(r["asks"]), usd_qty=True)


def _book_binance_perp(a):
    j = _get(f"https://fapi.binance.com/fapi/v1/depth?symbol={a}USDT&limit=500")
    return _book_usd(_pairs(j["bids"]), _pairs(j["asks"]))


BOOKS = {"binance_perp": _book_binance_perp, "binance": _book_binance, "binanceus": _book_binanceus, "coinbase": _book_coinbase, "kraken": _book_kraken, "bitstamp": _book_bitstamp, "gemini": _book_gemini,
         "okx": _book_okx, "okx_perp": _book_okx_perp, "bitfinex": _book_bitfinex, "gate": _book_gate,
         "bitget": _book_bitget, "kucoin": _book_kucoin, "cryptocom": _book_cryptocom,
         "hyperliquid": _book_hyperliquid, "deribit": _book_deribit}


def _book_loop(venue, fn):
    time.sleep(2 + (hash(venue) % 5))
    while True:
        for a in ASSETS:
            try:
                r = fn(a)
                if r:
                    HUB.set_book(venue, a, r[0], r[1])
            except Exception:
                pass
            time.sleep(0.4)
        time.sleep(8)


# ====================================================================== log + start
def _log_loop():
    """Append-only record of the pressure every 5s (kept forever - lets us test later whether it ever predicted anything)."""
    time.sleep(20)
    try:
        os.makedirs(os.path.dirname(PRESSURE_LOG), exist_ok=True)
        new = not os.path.exists(PRESSURE_LOG)
        f = open(PRESSURE_LOG, "a", newline="", encoding="utf-8")
        w = csv.writer(f)
        if new:
            w.writerow(["ts", "asset", "buy_pct_10s", "buy_pct_30s", "buy_pct_60s", "buy_pct_300s", "usd_60s", "venues_live", "book_buy_pct", "book_venues"])
    except Exception:
        return
    while True:
        try:
            for a in ASSETS:
                s = HUB.summary(a)
                wn = s["wins"]
                fmt = lambda x: "" if x is None else f"{x:.4f}"
                w.writerow([time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()), a] + [fmt(wn[k]["pct"]) for k in WINDOWS]
                           + [f'{wn[60]["buy"] + wn[60]["sell"]:.0f}', s["live_n"], fmt(s["book_pct"]), s["book_n"]])
            f.flush()
        except Exception:
            pass
        time.sleep(5)


_started = False


def start():
    """Start every feed in its own daemon thread.  Safe to call twice."""
    global _started
    if _started or websocket is None:
        return
    _started = True
    ENGINE.start()
    for feed in _feeds():
        threading.Thread(target=feed.run_forever, daemon=True, name=f"flow-{feed.name}").start()
    for v, fn in BOOKS.items():
        threading.Thread(target=_book_loop, args=(v, fn), daemon=True, name=f"book-{v}").start()
    threading.Thread(target=_binanceus_poll_loop, daemon=True, name="flow-binanceus").start()
    threading.Thread(target=_deriv_loop, daemon=True, name="flow-deriv").start()
    threading.Thread(target=_v24_loop, daemon=True, name="flow-mathcheck").start()
    threading.Thread(target=_seed_history, daemon=True, name="flow-seed").start()
    if not os.environ.get("FLOW_NO_LOG"):      # tests set this so they never write into the real log
        threading.Thread(target=_log_loop, daemon=True, name="pressure-log").start()
