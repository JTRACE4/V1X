"""aggr.trade / Bookmap-style order-flow engine (information only - never used for buying).

Added 2026-10-20. What it does with the raw exchange tape that multi_exchange_flow.FlowHub already collects:

  * AGGREGATED PRINTS (the aggr.trade method) - one market order that hits 30 resting orders shows up on most exchanges as
    30 small trades. aggr.trade groups trades by exchange + market + side + timestamp back into the ONE order that caused
    them. We do the same here, so a $600k market buy is seen as one $600k print (whale detection and sweep detection both
    need this - counting slices would miss them). Totals are unaffected: grouping never adds or removes a dollar.
  * SWEEPS - a single aggregated print that tore through several price levels at once (it "swept" the book), a burst of
    same-side prints across several exchanges within 2 seconds that moved price, and the classic stop-run: price pokes
    through the recent high / low (where stops and resting liquidity sit) and snaps straight back inside.
  * LIQUIDATIONS - forced closes streamed by Binance futures, Bybit, OKX, BitMEX and Deribit. Kept SEPARATE from the trade
    totals: a liquidation is already a trade on the tape, so adding it again would count the same sale twice.
  * LIQUIDITY TRACKER (the Bookmap idea) - big resting orders near price on the full Coinbase order book; when one
    disappears we check whether price actually traded into it (ABSORBED - eaten by the other side) or whether it vanished
    before price got there (PULLED - liquidity yanked / possible spoof).
  * CRYPTOMETER (optional) - if a free API key is put in cryptometer_key.txt (or the CRYPTOMETER_API_KEY environment
    variable), its market-wide buy / sell pressure and "rapid movement" detections are shown as outside CONTEXT only.
    They are never added to our own totals (their numbers are built from the same exchanges - adding them would
    double-count every sale).

Every finding lands in one alert feed (ENGINE.alerts_for) that the dashboard shows in the alert box at the top.
Bookmap's own web app and aggr.trade have no public data feed to pull from - this rebuilds their method on the same
public exchange feeds they themselves connect to.
"""
import collections
import json
import os
import threading
import time

ASSETS = ("BTC", "XRP")
HIST_SECONDS = 900                     # aggregated prints kept for 15 minutes
_ROOT = os.path.dirname(os.path.abspath(__file__))

# ---- grouping fills into one print (aggr.trade style) ----
GROUP_MS_EXCHANGE = 1                  # fills stamped by the exchange within 1 ms, same side = the same taker order
GROUP_MS_LOCAL = 3                     # no exchange timestamp: fills that ARRIVED within 3 ms of each other
PENDING_FLUSH_S = 0.08                 # a print is final once nothing joined it for 80 ms

# ---- detector thresholds (per coin) ----
SWEEP_MIN_BPS = {"BTC": 2.5, "XRP": 6.0}          # one order that ate this many basis points of book (2.5 bps = 0.025%)
SWEEP_MIN_USD = {"BTC": 150_000, "XRP": 25_000}
XSWEEP_WINDOW_S = 2.0                              # cross-exchange sweep: same-side prints inside 2 seconds ...
XSWEEP_USD = {"BTC": 1_500_000, "XRP": 200_000}   # ... adding up to at least this much ...
XSWEEP_MIN_VENUES = 3                              # ... on at least this many exchanges ...
XSWEEP_BPS = {"BTC": 4.0, "XRP": 10.0}            # ... while price moved at least this far their way
LIQ_ALERT_USD = {"BTC": 250_000, "XRP": 40_000}   # one forced close this big gets its own alert
LIQ_CASCADE_USD = {"BTC": 1_000_000, "XRP": 150_000}   # same-side forced closes inside 30s
LIQ_CASCADE_S = 30
STOPRUN_LOOKBACK_S = 15 * 60          # the "recent high / low" = the last 15 minutes ...
STOPRUN_EXCLUDE_S = 60                # ... not counting the last minute (the move being judged)
STOPRUN_MIN_HISTORY_S = 5 * 60        # need at least 5 minutes of data before a high / low means anything
STOPRUN_REVERT_S = 90                 # back inside within 90s = a sweep (stop-run); still outside after 90s = a breakout
STOPRUN_POKE_BPS = {"BTC": 1.5, "XRP": 4.0}       # how far past the level counts as "took it out"
WALL_MIN_USD = {"BTC": 400_000, "XRP": 80_000}    # resting order size that counts as a wall (Coinbase book)
WALL_NEAR_PCT = 0.002                  # only walls within 0.2% of price matter for pulled / absorbed
WALL_MIN_AGE_S = 4                     # a wall must have stood at least this long (flickering quotes are ignored)
WHALE_FALLBACK = {"BTC": (50_000, 250_000), "XRP": (10_000, 50_000)}   # (show, alert) until there is history

REF_VENUES = ("coinbase", "kraken", "bitstamp", "gemini")   # real-dollar venues used for the price path (no USDT basis)

KIND_LABEL = {
    "whale": "WHALE", "sweep": "BIG ORDER", "xsweep": "RUSH", "stoprun": "FAKE BREAKOUT",
    "breakout": "BREAKOUT", "liq": "FORCED SALE", "liqcascade": "FORCED-SALE WAVE", "absorbed": "BIG ORDER FILLED",
    "pulled": "BIG ORDER CANCELED", "wall": "BIG ORDER WAITING", "burst": "SURGE", "boom": "FAST MOVE",
    "sweep1m": "NEW HIGH/LOW", "rapid": "CRYPTOMETER", "flip": "FLIP WARNING",
}


def _usd(v):
    v = abs(v or 0)
    if v >= 1e9:
        return f"${v / 1e9:.2f}B"
    if v >= 1e6:
        return f"${v / 1e6:.2f}M"
    if v >= 1e3:
        return f"${v / 1e3:.0f}K"
    return f"${v:.0f}"


def _px(asset, p):
    if p is None:
        return "?"
    return f"${p:,.4f}" if asset == "XRP" else f"${p:,.2f}"


class Engine:
    def __init__(self):
        self.lock = threading.Lock()
        self.pending = {}                                   # (venue, asset) -> print being built
        self.out = collections.deque()                      # finished prints waiting for the worker
        self.prints = {a: collections.deque() for a in ASSETS}     # finished prints, last 15 min
        self.alerts = collections.deque(maxlen=400)
        self._alert_id = 0
        self._cool = {}                                     # dedupe key -> last fire ts
        self.liqs = {a: collections.deque() for a in ASSETS}       # (ts, venue, liquidated_side, usd, price)
        self.sec_bars = {a: collections.OrderedDict() for a in ASSETS}   # sec -> [o, h, l, c] from REF_VENUES
        self.run_state = {a: {} for a in ASSETS}
        self.walls = {}                                     # (asset, venue) -> {(side, price): {...}}
        self.px_range = {}                                  # (asset, venue) -> [lo, hi] traded since the last book check
        self.listeners = []                                 # fn(print_dict) for every finished print
        self.whale_threshold_fn = None                      # fn(asset) -> (show_usd, alert_usd); dashboard sets it
        self.kinds = {}                                     # venue -> "spot" / "perp"
        self.cmeter = {"enabled": False, "trend": None, "ts": None, "error": None}
        self.stats = {"prints": 0, "fills": 0}
        self._started = False

    # ================================================================== input (called from feed threads - must be cheap)
    def ingest(self, venue, asset, usd, qty, side, price, ts_ms=None, kind="spot", gkey=None):
        if asset not in self.prints or not price or usd <= 0:
            return
        now = time.time()
        exch = ts_ms is not None
        t_ms = int(ts_ms) if exch else int(now * 1000)
        with self.lock:
            self.kinds[venue] = kind
            key = (venue, asset)
            p = self.pending.get(key)
            if p is not None:
                gap = GROUP_MS_EXCHANGE if (exch and p["exch"]) else GROUP_MS_LOCAL
                same = (p["side"] == side and abs(t_ms - p["t_ms"]) <= gap
                        and (price >= p["last"] if side == "buy" else price <= p["last"])    # a sweep only walks one way
                        and (gkey is None and p.get("gkey") is None or gkey == p.get("gkey")))
                # gkey: venues that stamp every trade in a block with the same time (Hyperliquid) pass the taker order's
                # transaction hash, so two different traders' orders in the same block are never merged into one "print"
                if same:
                    p["usd"] += usd; p["qty"] += qty; p["n"] += 1; p["last"] = price; p["t_local"] = now
                    p["hi"] = max(p["hi"], price); p["lo"] = min(p["lo"], price)
                    return
                self.out.append(p)
            self.pending[key] = {"venue": venue, "asset": asset, "side": side, "usd": usd, "qty": qty, "n": 1,
                                 "first": price, "last": price, "hi": price, "lo": price, "t_ms": t_ms, "exch": exch,
                                 "t_local": now, "ts": now, "kind": kind, "gkey": gkey}

    def liquidation(self, venue, asset, liquidated, usd, price, ts_ms=None):
        """A forced close. liquidated = 'long' (their position was SOLD out -> selling pressure) or 'short' (bought back ->
        buying pressure). Information only - NOT added to volume (the forced trade is already on the tape)."""
        if asset not in self.liqs or usd <= 0 or liquidated not in ("long", "short"):
            return
        now = time.time()
        side = "sell" if liquidated == "long" else "buy"
        with self.lock:
            dq = self.liqs[asset]
            dq.append((now, venue, liquidated, usd, price))
            while dq and now - dq[0][0] > 900:
                dq.popleft()
        vname = _venue_label(venue)
        if usd >= LIQ_ALERT_USD.get(asset, 1e12):
            self.add_alert(asset, "liq", side, f"FORCED {'SALE' if liquidated == 'long' else 'BUY-BACK'}: {_usd(usd)}",
                           f"A losing {'long' if liquidated == 'long' else 'short'} bet was force-closed on {vname} at {_px(asset, price)}. "
                           f"That adds {'selling' if side == 'sell' else 'buying'} pressure.", usd=usd, price=price, venue=vname,
                           sev=3 if usd >= 4 * LIQ_ALERT_USD.get(asset, 1e12) else 2,
                           cooldown_key=("liq", asset, liquidated), cooldown=10)      # a burst becomes ONE cascade alert, not ten
        with self.lock:
            same = [x for x in self.liqs[asset] if now - x[0] <= LIQ_CASCADE_S and x[2] == liquidated]
        tot = sum(x[3] for x in same)
        if tot >= LIQ_CASCADE_USD.get(asset, 1e12):
            vs = sorted({_venue_label(x[1]) for x in same})
            self.add_alert(asset, "liqcascade", side, f"WAVE OF FORCED {'SELLING' if liquidated == 'long' else 'BUYING'}: {_usd(tot)} in {LIQ_CASCADE_S} seconds",
                           f"{len(same)} losing {'long' if side == 'sell' else 'short'} bets were force-closed on {', '.join(vs)}. "
                           f"This usually pushes the price further {'DOWN' if side == 'sell' else 'UP'}.", usd=tot, price=price, sev=3,
                           cooldown_key=("liqc", asset, liquidated), cooldown=45)

    # ================================================================== alerts
    def add_alert(self, asset, kind, side, title, detail, usd=None, price=None, sev=2, sound=True, cooldown_key=None, cooldown=0, venue=None):
        now = time.time()
        with self.lock:
            if cooldown_key is not None:
                last = self._cool.get(cooldown_key)
                if last and now - last < cooldown:
                    return None
                self._cool[cooldown_key] = now
            self._alert_id += 1
            a = {"id": self._alert_id, "ts": now, "asset": asset, "kind": kind, "label": KIND_LABEL.get(kind, kind.upper()),
                 "side": side, "title": title, "detail": detail, "usd": usd, "price": price, "sev": sev, "sound": sound,
                 "venue": venue}
            self.alerts.append(a)
        return a

    def recent_kind(self, asset, kinds, side=None, within=15):
        now = time.time()
        with self.lock:
            return any(a["asset"] == asset and a["kind"] in kinds and (side is None or a["side"] == side) and now - a["ts"] <= within
                       for a in self.alerts)

    def alerts_for(self, asset, max_age=1200, limit=14):
        now = time.time()
        with self.lock:
            rows = [dict(a) for a in self.alerts if a["asset"] == asset and now - a["ts"] <= max_age]
        return sorted(rows, key=lambda a: -a["ts"])[:limit]

    # ================================================================== read-outs for the page
    def big_prints(self, asset, seconds=180, limit=8):
        now = time.time()
        with self.lock:
            rows = [dict(p) for p in self.prints.get(asset, ()) if now - p["ts"] <= seconds]
        return sorted(rows, key=lambda p: -p["usd"])[:limit]

    def liq_totals(self, asset, seconds=300):
        now = time.time()
        with self.lock:
            rows = [x for x in self.liqs.get(asset, ()) if now - x[0] <= seconds]
        return {"long": sum(x[3] for x in rows if x[2] == "long"), "short": sum(x[3] for x in rows if x[2] == "short"),
                "n": len(rows), "venues": sorted({x[1] for x in rows})}

    def print_stats(self, asset, seconds=60):
        now = time.time()
        with self.lock:
            rows = [p for p in self.prints.get(asset, ()) if now - p["ts"] <= seconds]
        return {"prints": len(rows), "fills": sum(p["n"] for p in rows)}

    # ================================================================== Bookmap-style liquidity tracker
    def track_book(self, asset, venue, bids, asks, ref_price):
        """bids / asks: {price: resting_usd} near price (the dashboard passes the Coinbase full-depth book once a second).
        Finds walls, and when one disappears decides ABSORBED (price traded into it) vs PULLED (vanished untouched)."""
        if asset not in self.prints or not ref_price or not bids or not asks:
            return
        now = time.time()
        floor = WALL_MIN_USD.get(asset, 1e12)
        cur = {}
        for side, book in (("bid", bids), ("ask", asks)):
            for p, u in book.items():
                if u >= floor and abs(p - ref_price) / ref_price <= WALL_NEAR_PCT * 2:
                    cur[(side, p)] = u
        key = (asset, venue)
        with self.lock:
            prev = self.walls.get(key, {})
            rng = self.px_range.pop(key, None)
        vanished = []
        for wk, w in prev.items():
            u_now = cur.get(wk)
            if u_now is None:
                # level gone completely - or shrunk to under 30% of what stood there
                u_now = (bids if wk[0] == "bid" else asks).get(wk[1], 0.0)
            if u_now < 0.3 * w["max"]:
                vanished.append((wk, w))
        nxt = {}
        for wk, u in cur.items():
            w = prev.get(wk)
            if w is None:
                nxt[wk] = {"first": now, "last": now, "max": u, "usd": u}
            else:
                nxt[wk] = {"first": w["first"], "last": now, "max": max(w["max"], u), "usd": u}
        with self.lock:
            self.walls[key] = nxt
        if len(vanished) > 3:          # many walls gone at once = the book feed reconnected / reset, not a real event
            return
        for (side, p), w in vanished:
            if now - w["first"] < WALL_MIN_AGE_S or abs(p - ref_price) / ref_price > WALL_NEAR_PCT:
                continue
            traded = rng is not None and ((side == "ask" and rng[1] >= p) or (side == "bid" and rng[0] <= p))
            vname = _venue_label(venue)
            if traded:
                # an ask wall eaten = buyers took all of it (bullish); a bid wall eaten = sellers hit all of it (bearish)
                aside = "buy" if side == "ask" else "sell"
                self.add_alert(asset, "absorbed", aside, f"BIG {'SELL' if side == 'ask' else 'BUY'} ORDER ({_usd(w['max'])} at {_px(asset, p)}) GOT FULLY FILLED",
                               f"{'Buyers lifted' if side == 'ask' else 'Sellers hit'} the whole resting {'offer' if side == 'ask' else 'bid'} on {vname} "
                               f"(it sat there {int(now - w['first'])}s) - {'that ceiling is gone' if side == 'ask' else 'that floor is gone'}",
                               usd=w["max"], price=p, sev=2, venue=vname, cooldown_key=("wallx", asset, side, round(p, 4)), cooldown=60)
            else:
                # pulled ask = sellers stepped away (less resistance above); pulled bid = support stepped away
                aside = "buy" if side == "ask" else "sell"
                self.add_alert(asset, "pulled", aside, f"BIG {'SELL' if side == 'ask' else 'BUY'} ORDER ({_usd(w['max'])} at {_px(asset, p)}) WAS CANCELED",
                               f"A resting {'offer' if side == 'ask' else 'bid'} on {vname} was canceled before the price reached it (it sat there {int(now - w['first'])}s) - "
                               f"it may have been a fake order meant to scare traders", usd=w["max"], price=p, sev=1, venue=vname,
                               cooldown_key=("wallp", asset, side, round(p, 4)), cooldown=60)

    def walls_now(self, asset, venue="coinbase"):
        with self.lock:
            return {k: dict(v) for k, v in self.walls.get((asset, venue), {}).items()}

    # ================================================================== worker
    def _whale_thresholds(self, asset):
        fn = self.whale_threshold_fn
        if fn is not None:
            try:
                return fn(asset)
            except Exception:
                pass
        return WHALE_FALLBACK.get(asset, (1e12, 1e12))

    def _finish(self, p):
        a = p["asset"]
        p["vwap"] = p["usd"] / p["qty"] if p["qty"] > 0 else p["last"]
        p["bps"] = (p["hi"] - p["lo"]) / p["lo"] * 1e4 if p["lo"] > 0 else 0.0
        with self.lock:
            dq = self.prints[a]
            dq.append(p)
            while dq and p["ts"] - dq[0]["ts"] > HIST_SECONDS:
                dq.popleft()
            self.stats["prints"] += 1
            self.stats["fills"] += p["n"]
            rk = (a, p["venue"])
            r = self.px_range.get(rk)
            self.px_range[rk] = [min(r[0], p["lo"]), max(r[1], p["hi"])] if r else [p["lo"], p["hi"]]
            if p["venue"] in REF_VENUES:
                s = int(p["ts"])
                bars = self.sec_bars[a]
                b = bars.get(s)
                if b is None:
                    bars[s] = [p["first"], p["hi"], p["lo"], p["last"]]
                else:
                    b[1] = max(b[1], p["hi"]); b[2] = min(b[2], p["lo"]); b[3] = p["last"]
                while bars and next(iter(bars)) < s - 1500:
                    bars.popitem(last=False)
        for fn in list(self.listeners):
            try:
                fn(p)
            except Exception:
                pass
        vname = _venue_label(p["venue"])
        # ---- whale print (an aggregated taker order, not a slice of one)
        show, alert = self._whale_thresholds(a)
        if p["usd"] >= alert:
            self.add_alert(a, "whale", p["side"], f"WHALE {'BUY' if p['side'] == 'buy' else 'SELL'} {_usd(p['usd'])}",
                           f"Someone {'bought' if p['side'] == 'buy' else 'sold'} {p['qty']:,.{2 if a == 'BTC' else 0}f} {a} in one go on {vname} at "
                           f"{_px(a, p['vwap'])}.", usd=p["usd"], price=p["vwap"], venue=vname,
                           sev=3 if p["usd"] >= 4 * alert else 2, sound=False)    # the dashboard's whale voice already speaks these
        # ---- one order that swept several price levels
        if p["usd"] >= SWEEP_MIN_USD.get(a, 1e12) and p["bps"] >= SWEEP_MIN_BPS.get(a, 1e9) and p["n"] >= 3:
            self.add_alert(a, "sweep", p["side"], f"ONE BIG {'BUY' if p['side'] == 'buy' else 'SELL'} ORDER ({_usd(p['usd'])}) MOVED THE PRICE {'UP' if p['side'] == 'buy' else 'DOWN'}",
                           f"One {'buy' if p['side'] == 'buy' else 'sell'} order on {vname} was so big it pushed the price from "
                           f"{_px(a, p['first'])} to {_px(a, p['last'])} by itself.",
                           usd=p["usd"], price=p["last"], venue=vname, sev=3 if p["usd"] >= 3 * SWEEP_MIN_USD.get(a, 1e12) else 2,
                           cooldown_key=("sweep", a, p["side"], p["venue"]), cooldown=15)

    def _xsweep(self, a, now):
        with self.lock:
            rows = [p for p in self.prints[a] if now - p["ts"] <= XSWEEP_WINDOW_S]
            bars = [(s, b) for s, b in self.sec_bars[a].items() if s >= int(now - XSWEEP_WINDOW_S) - 1]
        if not rows or len(bars) < 2:
            return
        p0, p1 = bars[0][1][0], bars[-1][1][3]
        move_bps = (p1 - p0) / p0 * 1e4 if p0 else 0.0
        for side in ("buy", "sell"):
            mine = [p for p in rows if p["side"] == side]
            tot = sum(p["usd"] for p in mine)
            venues = {p["venue"] for p in mine}
            moved = move_bps >= XSWEEP_BPS.get(a, 1e9) if side == "buy" else move_bps <= -XSWEEP_BPS.get(a, 1e9)
            if tot >= XSWEEP_USD.get(a, 1e12) and len(venues) >= XSWEEP_MIN_VENUES and moved:
                self.add_alert(a, "xsweep", side, f"{'BUYING' if side == 'buy' else 'SELLING'} RUSH: {_usd(tot)} in {XSWEEP_WINDOW_S:.0f} seconds",
                               f"Heavy {'buying' if side == 'buy' else 'selling'} hit {len(venues)} exchanges at the same time and moved the price "
                               f"from {_px(a, p0)} to {_px(a, p1)}.", usd=tot, price=p1, sev=3,
                               cooldown_key=("xsweep", a, side), cooldown=30)

    def _stoprun(self, a, now):
        """Price pokes through the recent high / low and comes straight back = a liquidity sweep (stop-run)."""
        s_now = int(now)
        with self.lock:
            bars = list(self.sec_bars[a].items())
            liq = list(self.liqs[a])
        if not bars:
            return
        hist = [b for s, b in bars if s_now - STOPRUN_LOOKBACK_S <= s < s_now - STOPRUN_EXCLUDE_S]
        if not hist or s_now - bars[0][0] < STOPRUN_MIN_HISTORY_S:
            return
        span_min = max(5, min(15, (s_now - STOPRUN_EXCLUDE_S - max(bars[0][0], s_now - STOPRUN_LOOKBACK_S)) // 60))
        H = max(b[1] for b in hist)
        L = min(b[2] for b in hist)
        last5 = [b for s, b in bars if s >= s_now - 5]
        if not last5:
            return
        hi5, lo5, close = max(b[1] for b in last5), min(b[2] for b in last5), last5[-1][3]
        poke = STOPRUN_POKE_BPS.get(a, 2.0) / 1e4
        st = self.run_state[a]
        for which in ("hi", "lo"):
            e = st.get(which)
            lvl = H if which == "hi" else L
            if e is None:
                took = hi5 > lvl * (1 + poke) if which == "hi" else lo5 < lvl * (1 - poke)
                ck = ("run", a, which, round(lvl, 4))
                with self.lock:
                    cooled = now - self._cool.get(ck, 0) > 180
                if took and cooled:
                    st[which] = {"level": lvl, "t0": now, "peak": hi5 if which == "hi" else lo5, "span": span_min}
                continue
            e["peak"] = max(e["peak"], hi5) if which == "hi" else min(e["peak"], lo5)
            back = close < e["level"] * (1 - 0.5e-4) if which == "hi" else close > e["level"] * (1 + 0.5e-4)
            age = now - e["t0"]
            if back and age <= STOPRUN_REVERT_S:
                stops = sum(x[3] for x in liq if x[0] >= e["t0"] - 5 and x[2] == ("short" if which == "hi" else "long"))
                extra = f" ({_usd(stops)} of losing {'short' if which == 'hi' else 'long'} bets were force-closed on the way)" if stops > 0 else ""
                poke_bps = abs(e["peak"] - e["level"]) / e["level"] * 1e4
                self.add_alert(a, "stoprun", "sell" if which == "hi" else "buy",
                               f"FAKE BREAKOUT {'ABOVE' if which == 'hi' else 'BELOW'} THE {e['span']}-MIN {'HIGH' if which == 'hi' else 'LOW'} - THE PRICE CAME RIGHT BACK",
                               f"The price poked {'above' if which == 'hi' else 'below'} {_px(a, e['level'])} (as far as {_px(a, e['peak'])}), then came back "
                               f"{'under' if which == 'hi' else 'over'} it within {int(age)} seconds. The move failed, so the price may now turn "
                               f"{'DOWN' if which == 'hi' else 'UP'}{extra}.",
                               price=close, sev=3, cooldown_key=("run", a, which, round(e["level"], 4)), cooldown=180)
                st[which] = None
            elif age > STOPRUN_REVERT_S:
                self.add_alert(a, "breakout", "buy" if which == "hi" else "sell",
                               f"REAL BREAKOUT: THE PRICE BROKE THE {e['span']}-MIN {'HIGH' if which == 'hi' else 'LOW'} AND STAYED THERE",
                               f"Price has stayed {'above' if which == 'hi' else 'below'} {_px(a, e['level'])} for {STOPRUN_REVERT_S}s "
                               f"(it reached {_px(a, e['peak'])}) - a real breakout, not a sweep", price=close, sev=1, sound=False,
                               cooldown_key=("run", a, which, round(e["level"], 4)), cooldown=180)
                st[which] = None

    def _loop(self):
        last_slow = 0.0
        last_x = 0.0
        while True:
            time.sleep(0.1)
            now = time.time()
            with self.lock:
                for k in [k for k, p in self.pending.items() if now - p["t_local"] >= PENDING_FLUSH_S]:
                    self.out.append(self.pending.pop(k))
                batch = list(self.out)
                self.out.clear()
            for p in batch:
                try:
                    self._finish(p)
                except Exception:
                    pass
            if now - last_x >= 0.5:
                last_x = now
                for a in ASSETS:
                    try:
                        self._xsweep(a, now)
                    except Exception:
                        pass
            if now - last_slow >= 1.0:
                last_slow = now
                for a in ASSETS:
                    try:
                        self._stoprun(a, now)
                    except Exception:
                        pass
                with self.lock:
                    for k in [k for k, t in self._cool.items() if now - t > 900]:
                        del self._cool[k]

    # ================================================================== Cryptometer (optional, context only)
    def _cmeter_key(self):
        k = os.environ.get("CRYPTOMETER_API_KEY", "").strip()
        if k:
            return k
        try:
            with open(os.path.join(_ROOT, "cryptometer_key.txt"), encoding="utf-8") as f:
                return f.read().strip() or None
        except Exception:
            return None

    def _cmeter_loop(self):
        """Free Cryptometer keys get 10,000 calls a month: 2 calls every 10 minutes = ~8,600 a month. Set
        CRYPTOMETER_EVERY_S lower only on a paid plan."""
        key = self._cmeter_key()
        if not key:
            return
        import requests
        every = max(60, int(os.environ.get("CRYPTOMETER_EVERY_S", "600") or 600))
        self.cmeter["enabled"] = True
        seen = set()
        s = requests.Session()
        s.headers.update({"User-Agent": "kalshi-dashboard"})
        time.sleep(8)
        while True:
            try:
                j = s.get("https://api.cryptometer.io/trend-indicator-v3/", params={"api_key": key}, timeout=10).json()
                row = _first_row(j)
                if row:
                    self.cmeter.update({"trend": {"score": _f(row.get("trend_score")), "buy": _f(row.get("buy_pressure")),
                                                  "sell": _f(row.get("sell_pressure"))}, "ts": time.time(), "error": None})
                elif isinstance(j, dict) and j.get("error") not in (None, "false", False):
                    self.cmeter["error"] = str(j.get("error"))[:120]
            except Exception as e:
                self.cmeter["error"] = f"{type(e).__name__}"
            try:
                j = s.get("https://api.cryptometer.io/rapid-movements/", params={"api_key": key}, timeout=10).json()
                for r in _rows(j):
                    pair = str(r.get("pair", "")).upper()
                    a = next((x for x in ASSETS if pair.startswith(x)), None)
                    uid = (pair, str(r.get("exchange")), str(r.get("timestamp")))
                    if not a or uid in seen:
                        continue
                    seen.add(uid)
                    side = "buy" if str(r.get("side", "")).lower() in ("long", "buy", "up") else "sell"
                    self.add_alert(a, "rapid", side, f"RAPID MOVE {str(r.get('side', '')).upper()} ({r.get('exchange')})",
                                   f"Cryptometer detected a {r.get('change_detected')}% move on {pair} - outside context, not counted in our totals",
                                   sev=1, sound=False)
            except Exception:
                pass
            time.sleep(every)

    def start(self):
        if self._started:
            return
        self._started = True
        threading.Thread(target=self._loop, daemon=True, name="orderflow-engine").start()
        threading.Thread(target=self._cmeter_loop, daemon=True, name="cryptometer").start()


def _f(x):
    try:
        return float(x)
    except Exception:
        return None


def _rows(j):
    d = j.get("data") if isinstance(j, dict) else j
    if isinstance(d, list):
        out = []
        for x in d:
            if isinstance(x, list):
                out.extend(y for y in x if isinstance(y, dict))
            elif isinstance(x, dict):
                out.append(x)
        return out
    return [d] if isinstance(d, dict) else []


def _first_row(j):
    r = _rows(j)
    return r[0] if r else None


_VENUE_LABELS = {}


def _venue_label(v):
    return _VENUE_LABELS.get(v, v)


ENGINE = Engine()
