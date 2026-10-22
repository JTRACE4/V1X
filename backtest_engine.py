"""Server-side backtest of the 15-minute Kalshi BTC calls (added 2026-10-20).

Runs on the dashboard's own server (it needs the public Kalshi / Coinbase / Binance APIs). For every settled KXBTC15M round
in the look-back window it rebuilds what the dashboard would have seen at the EARLY (4:00) and SEALED (8:00) marks, then
replays the call rules and grades them against Kalshi's real result:

  * baseline      - simply buying Kalshi's favorite at the mark
  * current rules - the stage-call blend + signal votes + tiers (SUPER / GOOD / WEAK)
  * reversal rule - calling the LOSING side when flip risk + RSI + momentum agree
  * 80% search    - thousands of filter combinations on the favorite side, chosen on the OLDER 70% of rounds and then
                    checked on the NEWEST 30% they never saw (so a rule that only "worked" by luck is caught)

Every strategy is scored on win rate AND money: buying the called side at Kalshi's own price at that minute plus 1c
slippage and Kalshi's taker fee. A high win rate on 90c favorites can still lose money, so both are reported.

Data used (all public, cached under DATA_DIR/data_cache/backtest/):
  Kalshi  /markets (settled)   strike + result     /series/.../candlesticks   price per minute
  Coinbase 1-minute candles     the USD price path (closest public stand-in for the CF Benchmarks index)
  Binance spot 1-minute klines  taker-buy volume -> buyers vs sellers (the live dashboard uses 20 exchanges at 1s;
                                the backtest only has this at 1-minute resolution, and no order-book walls)
"""
import datetime as dt
import json
import math
import os
import threading
import time

import requests

KALSHI = "https://external-api.kalshi.com/trade-api/v2"
SERIES = "KXBTC15M"
HEADERS = {"User-Agent": "crypto-15m-predictor/1.0"}
LOOKBACK_DAYS = int(os.environ.get("BACKTEST_DAYS", "21"))
HOLDOUT_FRAC = 0.30
SLIPPAGE = 0.01
MIN_TRAIN_N = 40
MIN_HOLD_N = 25
TARGET_WIN = 0.80

_ROOT = os.environ.get("DATA_DIR") or os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(_ROOT, "data_cache", "backtest")
RESULTS_FILE = os.path.join(CACHE, "backtest_results.json")

STATE = {"running": False, "stage": "idle", "progress": "", "started": None, "finished": None, "error": None}
RESULTS = None
_fn = {}                     # functions handed over by the dashboard (trend_read, stage_decide, signal_consensus, ...)
_lock = threading.Lock()


def configure(**kw):
    _fn.update(kw)


# ============================================================================ fetching (cached)
def _get(url, params=None, tries=5):
    last = None
    for a in range(tries):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=25)
            if r.status_code == 429 or r.status_code >= 500:
                last = RuntimeError(f"HTTP {r.status_code}")
            else:
                r.raise_for_status()
                return r.json()
        except requests.RequestException as e:
            last = e
        time.sleep(1.5 * (2 ** a))
    raise RuntimeError(f"{url}: {last!r}")


def _load(name, default):
    try:
        with open(os.path.join(CACHE, name)) as f:
            return json.load(f)
    except Exception:
        return default


def _save(name, obj):
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, name)
    with open(p + ".tmp", "w") as f:
        json.dump(obj, f)
    os.replace(p + ".tmp", p)


def _ts(iso):
    return dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()


def fetch_markets(since_ts):
    out, cursor = [], None
    for _ in range(60):
        params = {"series_ticker": SERIES, "status": "settled", "limit": 1000, "min_close_ts": int(since_ts)}
        if cursor:
            params["cursor"] = cursor
        j = _get(f"{KALSHI}/markets", params)
        batch = j.get("markets") or []
        out += batch
        cursor = j.get("cursor")
        STATE["progress"] = f"{len(out)} settled rounds listed"
        if not batch or not cursor:
            break
        time.sleep(0.2)
    rows = []
    for m in out:
        res = (m.get("result") or "").lower()
        if res not in ("yes", "no"):
            continue
        try:
            o, c = _ts(m["open_time"]), _ts(m["close_time"])
        except Exception:
            continue
        if c - o < 800 or c - o > 1000:
            continue
        strike = m.get("floor_strike")
        rows.append({"ticker": m["ticker"], "open": o, "close": c, "strike": float(strike) if strike else None, "result": res})
    rows.sort(key=lambda r: r["open"])
    return rows


def _cents(x):
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v / 100 if v > 1.0 else v


def fetch_kalshi_path(m):
    """[(end_ts, yes_price)] per minute for one market; carry the last price through quiet minutes."""
    j = _get(f"{KALSHI}/series/{SERIES}/markets/{m['ticker']}/candlesticks",
             {"period_interval": 1, "start_ts": int(m["open"]), "end_ts": int(m["close"])})
    pts = []
    for c in j.get("candlesticks") or []:
        pr = c.get("price") or {}
        bid, ask = c.get("yes_bid") or {}, c.get("yes_ask") or {}
        p = _cents(pr.get("close_dollars")) if pr.get("close_dollars") is not None else _cents(pr.get("close"))
        b = _cents(bid.get("close_dollars")) if bid.get("close_dollars") is not None else _cents(bid.get("close"))
        a = _cents(ask.get("close_dollars")) if ask.get("close_dollars") is not None else _cents(ask.get("close"))
        mid = (b + a) / 2 if (b is not None and a is not None and a > 0) else None
        v = mid if mid is not None else p
        if v is not None:
            pts.append((int(c["end_period_ts"]), round(v, 4), b, a))
    return pts


def fetch_coinbase(start, end):
    """{minute_ts: [o, h, l, c, vol]} USD 1-minute candles."""
    out = {}
    t = int(start // 60 * 60)
    while t < end:
        t2 = min(end, t + 300 * 60)
        j = _get("https://api.exchange.coinbase.com/products/BTC-USD/candles",
                 {"granularity": 60, "start": dt.datetime.fromtimestamp(t, dt.timezone.utc).isoformat(),
                  "end": dt.datetime.fromtimestamp(t2, dt.timezone.utc).isoformat()})
        for r in j or []:
            out[int(r[0])] = [float(r[3]), float(r[2]), float(r[1]), float(r[4]), float(r[5])]
        STATE["progress"] = f"price candles {len(out):,}"
        t = t2
        time.sleep(0.25)
    return out


def fetch_binance(start, end):
    """{minute_ts: [vol, taker_buy_vol]} - buyers vs sellers per minute. Empty if Binance is not reachable."""
    out = {}
    t = int(start // 60 * 60) * 1000
    end_ms = int(end * 1000)
    for host in ("https://data-api.binance.vision", "https://api.binance.us"):
        try:
            while t < end_ms:
                sym = "BTCUSDT" if "vision" in host else "BTCUSD"
                j = _get(f"{host}/api/v3/klines", {"symbol": sym, "interval": "1m", "startTime": t, "limit": 1000}, tries=3)
                if not j:
                    break
                for r in j:
                    out[int(r[0] // 1000)] = [float(r[5]), float(r[9])]
                t = int(j[-1][0]) + 60_000
                STATE["progress"] = f"order flow {len(out):,} minutes"
                time.sleep(0.15)
            if out:
                return out
        except Exception:
            continue
    return out


# ============================================================================ features at a decision mark
def _rsi(closes, n=14):
    if len(closes) < n + 1:
        return None
    gains = losses = 0.0
    for i in range(1, n + 1):
        d = closes[i] - closes[i - 1]
        gains += max(d, 0); losses += max(-d, 0)
    ag, al = gains / n, losses / n
    for i in range(n + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        ag = (ag * (n - 1) + max(d, 0)) / n
        al = (al * (n - 1) + max(-d, 0)) / n
    if al == 0:
        return 100.0
    return 100 - 100 / (1 + ag / al)


def _rsi_simple(closes, n=14):
    """Webull-style RSI: plain average of the last 14 up / down moves (no carry-over smoothing)."""
    if len(closes) < n + 1:
        return None
    w = closes[-(n + 1):]
    ag = sum(max(w[i] - w[i - 1], 0.0) for i in range(1, len(w))) / n
    al = sum(max(w[i - 1] - w[i], 0.0) for i in range(1, len(w))) / n
    if al == 0:
        return 100.0 if ag > 0 else 50.0
    return 100 - 100 / (1 + ag / al)


def _lerp(x, x0, x1, y0, y1):
    if x is None:
        return y0
    if x <= x0:
        return y0
    if x >= x1:
        return y1
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def features(m, mark, cb, bn, kpath, line_fallback=None):
    T = m["open"] + mark
    last_min = int((T - 60) // 60 * 60)                 # last COMPLETE candle before the mark
    mins = [last_min - 60 * k for k in range(0, 120)][::-1]
    cs = [(t, *cb[t][:4]) for t in mins if t in cb]
    if len(cs) < 60 or cs[-1][0] != last_min:
        return None
    closes = [c[4] for c in cs]
    spot = closes[-1]
    line = m["strike"] or line_fallback
    if not line:
        return None
    kp = None
    for e, v, _b, _a in kpath:
        if e <= T:
            kp = v
    if kp is None:
        return None
    dist = (spot - line) / line
    # buyers vs sellers (Binance taker volume)
    def share(k):
        vs = [bn.get(last_min - 60 * i) for i in range(k)]
        vs = [x for x in vs if x and x[0] > 0]
        if not vs:
            return None
        return sum(x[1] for x in vs) / sum(x[0] for x in vs)
    f1, f2 = share(1), share(2)
    fr = None
    rr = [bn.get(t) for t in range(int(m["open"] // 60 * 60), last_min + 1, 60)]
    rr = [x for x in rr if x and x[0] > 0]
    if rr:
        fr = sum(x[1] for x in rr) / sum(x[0] for x in rr)
    vols = [cb[t][4] for t in mins[-15:] if t in cb]
    pace = (vols[-1] / sorted(vols[:-1])[len(vols[:-1]) // 2]) if len(vols) >= 6 and sorted(vols[:-1])[len(vols[:-1]) // 2] > 0 else None
    # crosses since open on 1-minute closes
    band = 0.00003
    side = 0; crosses = 0; events = []
    for t, o, h, l, c in cs:
        if t < m["open"]:
            continue
        d_ = (c - line) / line
        sd = 1 if d_ > band else (-1 if d_ < -band else 0)
        if sd and side and sd != side:
            crosses += 1
            events.append((int(t + 60 - m["open"]), sd))
        if sd:
            side = sd
    r1 = _rsi(closes[-60:])
    r1_tv = _rsi(closes[-120:])             # TradingView / Wilder with a long warm-up (what the live box shows)
    r1_wb = _rsi_simple(closes)             # Webull-style simple average
    c5 = [closes[i] for i in range(len(closes) - 1, -1, -5)][::-1]
    r5 = _rsi(c5[-30:]) if len(c5) >= 16 else None
    trend = 0
    if _fn.get("trend_read"):
        try:
            trend = _fn["trend_read"]([list(c) for c in cs])[0]
        except Exception:
            trend = 0
    sig = {"kalshi": 0 if kp is None else (1 if kp >= 0.51 else (-1 if kp <= 0.49 else 0)),
           "line": 1 if dist > band else (-1 if dist < -band else 0),
           "candles": (1 if spot / closes[-4] - 1 >= 0.0002 else (-1 if spot / closes[-4] - 1 <= -0.0002 else 0)) if len(closes) >= 4 else 0,
           "flow": (1 if (f2 is not None and f2 >= 0.53) else (-1 if (f2 is not None and f2 <= 0.47) else
                    (1 if (fr is not None and fr >= 0.52) else (-1 if (fr is not None and fr <= 0.48) else 0)))),
           "trend": trend}
    toward_fav = closes[-1] - closes[-2]
    return {"T": T, "spot": spot, "line": line, "dist": dist, "kp": kp, "f1": f1, "f2": f2, "fr": fr, "pace": pace,
            "crosses": crosses, "events": events, "r1": r1, "r5": r5, "r1_tv": r1_tv, "r1_wb": r1_wb, "trend": trend, "sig": sig, "last_move": toward_fav,
            "closes": closes[-5:]}


def flip_score(f, call_sign, mark):
    """Backtest version of flip_risk_core: same scoring, but 1-minute flow (no 10s / 30s windows) and no book walls."""
    sh = []
    if f["f1"] is not None:
        sh.append(((1 - f["f1"]) if call_sign > 0 else f["f1"], 0.6))
    if f["f2"] is not None:
        sh.append(((1 - f["f2"]) if call_sign > 0 else f["f2"], 0.4))
    opp = sum(a * w for a, w in sh) / sum(w for _a, w in sh) if sh else None
    mom = _lerp(opp, 0.45, 0.80, 0, 30) if opp is not None else 0.0
    toward = (f["last_move"] * call_sign) < -(f["line"] * 0.00005)
    if toward and opp is not None and opp > 0.55:
        mom += _lerp(opp, 0.55, 0.75, 0, 10)
    dist = f["dist"] * 100 * call_sign
    wrong = dist < 0
    if wrong:
        cush = 0.0
    elif dist >= 0.20:
        cush = 0.0
    elif dist < 0.02:
        cush = 25.0
    else:
        cush = 0.0
        for lo_, hi_, a_, b_ in ((0.15, 0.20, 5, 0), (0.10, 0.15, 12, 5), (0.05, 0.10, 20, 12), (0.02, 0.05, 25, 20)):
            if lo_ <= dist < hi_:
                cush = _lerp(dist, lo_, hi_, a_, b_)
    cx = min(15.0, sum(6.5 if (mark - e[0]) <= 180 else 5.0 for e in f["events"]))
    score = max(0.0, mom + cush + cx) * (min(1.35, max(0.75, f["pace"])) if f["pace"] else 1.0)
    if wrong:
        score = max(score, 75 + min(20, abs(dist) * 100))
    return min(99.0, score), opp, toward


def price_of(side_yes, kp):
    return kp if side_yes else 1 - kp


def pnl(win, p):
    """Profit per $1 staked buying at Kalshi price p (+slippage, + Kalshi taker fee 0.07*p*(1-p) rounded up to 1c)."""
    p = min(0.99, max(0.01, p + SLIPPAGE))
    fee = math.ceil(0.07 * p * (1 - p) * 100) / 100
    prof = (1 - p - fee) if win else (-p - fee)
    return prof / p


# ============================================================================ strategies
def stage_call(f):
    """The live rules (stage_blend without the fair-value model, which needs live order books: Kalshi 2/3, flow 1/3)."""
    flow_up = f["f2"] if f["f2"] is not None else f["fr"]
    if flow_up is not None:
        p = (0.5 * f["kp"] + 0.25 * flow_up) / 0.75
    else:
        p = f["kp"]
    sd, sc = _fn.get("stage_decide"), _fn.get("signal_consensus")
    if not sd:
        return ("YES" if p >= 0.5 else "NO"), "?", p
    ps = max(p, 1 - p)
    cs, agree, oppose = sc(f["sig"]) if sc else (0, 0, 0)
    if ps < 0.55 and not (cs and agree >= 3 and oppose == 0):
        if ps < 0.52:
            return None, None, p
    call, tier, _why = sd(p, flow_up, f["crosses"], signals=f["sig"])
    return call, tier, p


def reversal(f, mark, min_score=55, min_votes=3, rsi_hi=68, rsi_lo=32):
    if abs(f["dist"]) < 0.00003:
        return None
    fav = 1 if f["dist"] > 0 else -1
    sc, opp, toward = flip_score(f, fav, mark)
    if sc < min_score:
        return None
    votes = 0
    rsi_ok = f["r1"] is not None and ((fav > 0 and f["r1"] >= rsi_hi) or (fav < 0 and f["r1"] <= rsi_lo))
    votes += rsi_ok
    votes += bool(opp is not None and opp >= 0.58)
    votes += f["sig"]["candles"] == -fav
    votes += f["sig"]["trend"] == -fav
    votes += bool(toward)
    if votes < min_votes or not (rsi_ok or votes >= 4):
        return None
    return {"call": "NO" if fav > 0 else "YES", "score": sc, "votes": votes}


def _summ(trades):
    n = len(trades)
    if not n:
        return {"n": 0, "win": None, "roi": None, "avg_price": None}
    w = sum(1 for t in trades if t["win"])
    return {"n": n, "wins": w, "win": w / n, "roi": sum(t["pnl"] for t in trades) / n,
            "avg_price": sum(t["price"] for t in trades) / n, "units": sum(t["pnl"] for t in trades)}


def rule_match(f, r):
    fav_yes = f["kp"] >= 0.5
    kpf = price_of(fav_yes, f["kp"])
    if kpf < r["k"]:
        return None
    fs = 1 if fav_yes else -1
    if f["dist"] * fs < r["d"]:
        return None
    if f["crosses"] > r["c"]:
        return None
    agree = sum(1 for v in f["sig"].values() if v == fs)
    oppose = sum(1 for v in f["sig"].values() if v == -fs)
    if agree < r["a"] or oppose > r["o"]:
        return None
    if r["rsi"] and f["r1"] is not None and ((fs > 0 and f["r1"] >= 72) or (fs < 0 and f["r1"] <= 28)):
        return None
    return "YES" if fav_yes else "NO"


RULE_GRID = [{"k": k, "d": d, "c": c, "a": a, "o": o, "rsi": rsi}
             for k in (0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90)
             for d in (0.0, 0.0005, 0.001, 0.0015, 0.002)
             for c in (0, 1, 2, 99)
             for a in (0, 3, 4, 5)
             for o in (0, 1, 5)
             for rsi in (False, True)]


# ============================================================================ PRICE-vs-TARGET REGIME (2026-10-22, user)
# "Regime the call process to get me the most wins possible - check relative price target history, win or losses."
# Every settled round is filed by WHERE PRICE STOOD vs THE TARGET LINE at the mark (signed distance, % of the line), what
# Kalshi was pricing UP at, and whether RSI was stretched. For each spot we count how often the round really ended UP. A
# live call then takes the side that has WON MOST OFTEN from that same spot. Thin cells are shrunk toward Kalshi's own price
# (so a handful of lucky rounds can't flip a call), and cells fall back to coarser groupings when they don't have enough
# rounds. The table is only used live if it beats the current rules on the newest 30% of rounds it never saw.
REG_DIST = (-0.0015, -0.0008, -0.0004, -0.0002, -0.00005, 0.00005, 0.0002, 0.0004, 0.0008, 0.0015)   # price vs line
REG_KP = (0.20, 0.35, 0.50, 0.65, 0.80)                                                                # Kalshi UP price
REG_SHRINK = 20            # pseudo-rounds of Kalshi's own price mixed into every cell
REG_MIN_N = 25             # a cell needs this many rounds before it is used on its own
REG_HALFLIFE_DAYS = 5      # 2026-10-22 (user: "learn from the losses"): a round 5 days old counts half as much as one from
                           # today, so the table keeps learning from the latest wins AND losses as the market changes


def _bin(x, edges):
    i = 0
    while i < len(edges) and x >= edges[i]:
        i += 1
    return i


def _rsi_state(r):
    return "hi" if (r is not None and r >= 70) else ("lo" if (r is not None and r <= 30) else "mid")


def _tr(t):
    return "up" if (t or 0) > 0 else ("dn" if (t or 0) < 0 else "flat")


def regime_keys(dist, kp, rsi, trend=0):
    """Most specific first. 2026-10-22 (user: "especially during a trend"): the 1-minute TREND vote (EMA stack + SuperTrend
    + DMI) is part of every spot, so a call that keeps losing against a running trend gets flipped by its own history."""
    db, kb, tb = _bin(dist, REG_DIST), _bin(kp, REG_KP), _tr(trend)
    return (f"{db}|{kb}|{tb}|{_rsi_state(rsi)}", f"{db}|{kb}|{tb}", f"{db}|{kb}", f"{db}")


def build_regime(rows):
    """rows: [(dist, kp, rsi, trend, ended_up, t)] -> {key: [n, weighted_ups, weight]} (recent rounds weigh more)"""
    tab = {}
    if not rows:
        return tab
    t_now = max(r[5] or 0 for r in rows)
    for dist, kp, rsi, trend, up, t in rows:
        w = 0.5 ** (max(0.0, t_now - (t or t_now)) / (REG_HALFLIFE_DAYS * 86400))
        for k in regime_keys(dist, kp, rsi, trend):
            c = tab.setdefault(k, [0, 0.0, 0.0])
            c[0] += 1
            c[1] += w if up else 0.0
            c[2] += w
    for c in tab.values():
        c[1], c[2] = round(c[1], 3), round(c[2], 3)
    return tab


def regime_call(tab, dist, kp, rsi, trend=0):
    """None, or {"call", "p" (chance the called side wins), "n" (rounds behind it), "won", "level", "p_up"}."""
    if not tab or kp is None or dist is None:
        return None
    for lvl, k in zip(("fine", "trend", "mid", "coarse"), regime_keys(dist, kp, rsi, trend)):
        c = tab.get(k)
        if not c or c[0] < REG_MIN_N:
            continue
        n, wu, w = c[0], c[1], (c[2] if len(c) > 2 else c[0])
        # shrink toward Kalshi's price right now: thin evidence leans on the market, deep evidence leans on history
        p_up = (wu + REG_SHRINK * kp) / (w + REG_SHRINK)
        if abs(p_up - 0.5) < 1e-9:
            return None
        call = "YES" if p_up > 0.5 else "NO"
        won = round(n * (wu / w if w else 0.5)) if call == "YES" else round(n * (1 - (wu / w if w else 0.5)))
        return {"call": call, "p": p_up if call == "YES" else 1 - p_up, "n": n, "won": won, "level": lvl, "p_up": p_up,
                "trend": _tr(trend)}
    return None


def regime_tier(p):
    return "SUPER" if p >= 0.85 else ("GOOD" if p >= 0.72 else "WEAK")


def _reg_rows(rs, mark):
    out = []
    for r in rs:
        f = r["f"].get(mark)
        if f:
            out.append((f["dist"], f["kp"], f.get("r1_tv"), f.get("trend", 0), r["m"]["result"] == "yes", r["m"].get("close")))
    return out


def loss_check(rs, mark):
    """Where do the CURRENT rules lose? Win rate with / against / without a trend, and the share of all losses each holds."""
    out = {}
    for r in rs:
        f = r["f"][mark]
        call, _t, _p = stage_call(f)
        if not call:
            continue
        cs = 1 if call == "YES" else -1
        tv = f.get("trend", 0) or 0
        k = "with_trend" if tv == cs else ("against_trend" if tv == -cs else "no_trend")
        b = out.setdefault(k, [0, 0, 0.0, 0.0])
        win = (call == "YES") == (r["m"]["result"] == "yes")
        pr = price_of(call == "YES", f["kp"])
        b[0] += 1
        b[1] += win
        b[2] += pnl(win, pr)          # profit per $1 at the market's price, with fee + slippage
        b[3] += pr
    losses = sum(v[0] - v[1] for v in out.values()) or 1
    return {k: {"n": v[0], "win": v[1] / v[0], "loss_share": (v[0] - v[1]) / losses, "roi": v[2] / v[0],
                "units": v[2], "avg_price": v[3] / v[0]} for k, v in out.items()}


# ============================================================================ REVERSAL RULE SEARCH (2026-10-22, user)
# "Reversal calls need to be better - run a test and make the fixes." A reversal = calling the market's UNDERDOG. Thousands of
# filter combinations are tried on the older 70% of rounds and kept only if they MADE MONEY there with enough trades; the
# best one is then checked on the newest 30%. Live reversals only fire when a rule passes that check.
# 2026-10-22 (b, user: "4x reversals good - study the market and, if actually possible due to momentum and all the
# indicators, keep calling them"): searched separately per PAYOUT BAND, because a 4x underdog only has to win ~1 in 4 to pay,
# while a 2x one has to win ~1 in 2. A band's rule goes live only if it made money AND won clearly more often than its price
# implied - on the training rounds and again on the newest rounds it never saw.
# 2026-10-22 (c, user: "I want the ones with good win rates - even if they only go up 100% that's fine"): no long shots.
# Only underdogs priced 30c+ (pays at most ~3.3x), and each band needs a solid win rate, ranked by win rate first.
REV_BANDS = (("3x", 0.30, 0.37), ("2-2.7x", 0.37, 0.50))     # underdog price range
REV_MIN_WIN = {"3x": 0.42, "2-2.7x": 0.50}                   # win rate a band must reach (train and unseen rounds)
REV_GRID = [{"d": d, "c": c, "v": v, "rsi": rsi, "tr": tr}
            for d in (0.0003, 0.0006, 0.0012, 1.0)                    # price within this far of the line
            for c in (0, 1, 2)                                        # at least this many line crosses so far
            for v in (1, 2, 3, 4)                                     # at least this many reads turning against the favorite
            for rsi in (False, True)                                  # RSI stretched in the favorite's direction
            for tr in (False, True)]                                  # the trend itself must have turned against the favorite
REV_MIN_TRAIN = 20
REV_MIN_HOLD = 6
REV_MIN_EDGE = 0.05            # must win at least 5 points more often than the underdog's price implies


def rev_votes(f, fav):
    """How many reads are turning against the favorite side (fav = +1 UP favorite, -1 DOWN favorite)."""
    r = f.get("r1_tv") if f.get("r1_tv") is not None else f.get("r1")
    rsi_st = r is not None and ((fav > 0 and r >= 70) or (fav < 0 and r <= 30))
    sig = f.get("sig") or {}
    v = sum(1 for k in ("trend", "flow", "candles") if sig.get(k) == -fav) + (1 if rsi_st else 0)
    return v, rsi_st


def rev_rule_match(f, rule):
    if f.get("kp") is None or f.get("dist") is None:
        return None
    fav_yes = f["kp"] >= 0.5
    fav = 1 if fav_yes else -1
    dog = price_of(not fav_yes, f["kp"])
    if not (rule.get("lo", 0) <= dog < rule.get("hi", 0.5)):
        return None
    if abs(f["dist"]) > rule["d"] or (f.get("crosses") or 0) < rule["c"]:
        return None
    v, rsi_st = rev_votes(f, fav)
    if v < rule["v"] or (rule["rsi"] and not rsi_st) or (rule.get("tr") and (f.get("sig") or {}).get("trend") != -fav):
        return None
    return "NO" if fav_yes else "YES"


def evaluate(rounds):
    """rounds: [{"m": market, "f": {mark: features}}] oldest first."""
    n_hold = max(1, int(len(rounds) * HOLDOUT_FRAC))
    train, hold = rounds[:-n_hold], rounds[-n_hold:]
    out = {"rounds": len(rounds), "train_rounds": len(train), "holdout_rounds": len(hold),
           "from": rounds[0]["m"]["ticker"] if rounds else None, "to": rounds[-1]["m"]["ticker"] if rounds else None,
           "stages": {}}

    def trade(rd, mark, call):
        f = rd["f"][mark]
        p = price_of(call == "YES", f["kp"])
        win = (call == "YES") == (rd["m"]["result"] == "yes")
        return {"win": win, "price": p, "pnl": pnl(win, p), "t": rd["m"]["close"]}

    _tabs_tr = {}
    for key, mark in (("early", 240), ("sealed", 480)):
        rs = [r for r in rounds if r["f"].get(mark)]
        hs = [r for r in hold if r["f"].get(mark)]
        hold_ids = {id(r) for r in hs}
        st = {}
        fav = [trade(r, mark, "YES" if r["f"][mark]["kp"] >= 0.5 else "NO") for r in rs]
        st["favorite"] = _summ(fav)
        cur, by_tier = [], {}
        for r in rs:
            call, tier, _p = stage_call(r["f"][mark])
            if call:
                t = trade(r, mark, call)
                cur.append(t)
                by_tier.setdefault(tier, []).append(t)
        st["current"] = _summ(cur)
        st["current_by_tier"] = {k: _summ(v) for k, v in by_tier.items()}
        rev_all, rev_hold = [], []
        for r in rs:
            rv = reversal(r["f"][mark], mark)
            if rv:
                t = trade(r, mark, rv["call"])
                rev_all.append(t)
                if id(r) in hold_ids:
                    rev_hold.append(t)
        st["reversal"] = _summ(rev_all)
        st["reversal_holdout"] = _summ(rev_hold)
        # reversal threshold sweep (to show whether ANY version of it pays)
        sweep = []
        for ms in (45, 55, 65, 75):
            for mv in (2, 3, 4):
                tt = [trade(r, mark, rv["call"]) for r in rs for rv in [reversal(r["f"][mark], mark, ms, mv)] if rv]
                s_ = _summ(tt)
                s_.update({"min_score": ms, "min_votes": mv})
                sweep.append(s_)
        st["reversal_sweep"] = sweep
        # data-driven reversal rules, one per payout band: chosen on train by profit + edge, graded on the holdout
        trn = [x for x in train if x["f"].get(mark)]
        bands = []
        for lab, lo, hi in REV_BANDS:
            best = None
            for ri, g in enumerate(REV_GRID):
                if ri % 40 == 0:
                    time.sleep(0.01)
                rule = dict(g, lo=lo, hi=hi, band=lab)
                tt = [trade(r, mark, c) for r in trn for c in [rev_rule_match(r["f"][mark], rule)] if c]
                if len(tt) < REV_MIN_TRAIN:
                    continue
                s_ = _summ(tt)
                if (s_["roi"] > 0 and s_["win"] >= max(s_["avg_price"] + REV_MIN_EDGE, REV_MIN_WIN.get(lab, 0.5))
                        and (best is None or (s_["win"], s_["units"]) > (best[1]["win"], best[1]["units"]))):
                    best = (rule, s_)
            if not best:
                bands.append({"band": lab, "rule": None})
                continue
            th = [trade(r, mark, c) for r in hs for c in [rev_rule_match(r["f"][mark], best[0])] if c]
            sh = _summ(th)
            ok = bool(sh["n"] >= REV_MIN_HOLD and sh["roi"] is not None and sh["roi"] > 0 and sh["win"] >= REV_MIN_WIN.get(lab, 0.5) - 0.03
                      and sh["win"] >= sh["avg_price"] + REV_MIN_EDGE / 2)
            bands.append({"band": lab, "rule": best[0], "train": best[1], "holdout": sh, "validated": ok})
        st["reversal_bands"] = bands
        # 80% rule search: pick on train only, then check on the holdout
        tr = [r for r in train if r["f"].get(mark)]
        best_cov, best_ev = None, None
        for ri, rule in enumerate(RULE_GRID):
            if ri % 40 == 0:
                time.sleep(0.01)          # let the live dashboard threads run
            tt = [trade(r, mark, c) for r in tr for c in [rule_match(r["f"][mark], rule)] if c]
            if len(tt) < MIN_TRAIN_N:
                continue
            s_ = _summ(tt)
            if s_["win"] < TARGET_WIN + 0.02:
                continue
            if best_cov is None or s_["n"] > best_cov[1]["n"]:
                best_cov = (rule, s_)
            if s_["roi"] > 0 and (best_ev is None or s_["units"] > best_ev[1]["units"]):
                best_ev = (rule, s_)
        picks = {}
        for lab, b in (("most_rounds", best_cov), ("best_profit", best_ev)):
            if not b:
                continue
            rule, s_tr = b
            th = [trade(r, mark, c) for r in hs for c in [rule_match(r["f"][mark], rule)] if c]
            s_h = _summ(th)
            picks[lab] = {"rule": rule, "train": s_tr, "holdout": s_h,
                          "validated": bool(s_h["n"] >= MIN_HOLD_N and s_h["win"] is not None and s_h["win"] >= TARGET_WIN),
                          "profitable": bool(s_h["n"] >= MIN_HOLD_N and s_h["roi"] is not None and s_h["roi"] > 0),
                          "coverage": (s_tr["n"] + s_h["n"]) / max(1, len(rs))}
        st["rule80"] = picks
        # ---- price-vs-target regime: build on the OLDER 70%, grade on the NEWEST 30% next to the current rules
        tab_tr = build_regime(_reg_rows(tr, mark))
        _tabs_tr[key] = tab_tr
        reg_h, cur_h, by_lvl = [], [], {}
        overrides = [0, 0]                     # [times the regime picked the other side, times that override won]
        for r in hs:
            f = r["f"][mark]
            ccall, _t, _p = stage_call(f)
            rc = regime_call(tab_tr, f["dist"], f["kp"], f.get("r1_tv"), f.get("trend", 0))
            if ccall:
                cur_h.append(trade(r, mark, ccall))
            call = rc["call"] if rc else ccall
            if call:
                t = trade(r, mark, call)
                reg_h.append(t)
                if rc:
                    by_lvl.setdefault(rc["level"], []).append(t)
                    if ccall and rc["call"] != ccall:
                        overrides[0] += 1
                        overrides[1] += t["win"]
        sr, sc_ = _summ(reg_h), _summ(cur_h)
        enabled = bool(sr["n"] >= MIN_HOLD_N and sr["win"] is not None and sc_["win"] is not None
                       and sr["win"] >= sc_["win"] and sr["wins"] >= sc_.get("wins", 0))
        # dist-only win map for the logs: from each spot vs the line, how often did UP win
        dmap = {}
        for dist, kp, rsi, _tv, up, _t in _reg_rows(rs, mark):
            b = dmap.setdefault(_bin(dist, REG_DIST), [0, 0])
            b[0] += 1
            b[1] += up
        st["regime"] = {"holdout": sr, "current_holdout": sc_, "enabled": enabled,
                        "by_level": {k: _summ(v) for k, v in by_lvl.items()},
                        "overrides": {"n": overrides[0], "won": overrides[1]},
                        "dist_map": {str(k): {"n": v[0], "up": v[1]} for k, v in sorted(dmap.items())},
                        # the LIVE table uses every round (train + holdout), so it is as fresh as possible
                        "table": build_regime(_reg_rows(rs, mark)),
                        "loss_check": loss_check(rs, mark)}
        out["stages"][key] = st
    # ---- 2026-10-22 (user: "when the early call is more profitable than the sealed call we need to review it better on
    # time"): every round where the 8:00 sealed call would FLIP the 4:00 early call. Learn (on the older 70%) how sure the
    # sealed call has to be before a flip pays off; below that, the sealed call HOLDS the early side. Checked on the newest 30%.
    def _live_call(f, key):
        st_ = out["stages"][key].get("regime") or {}
        rc = regime_call(_tabs_tr.get(key), f["dist"], f["kp"], f.get("r1_tv"), f.get("trend", 0)) if st_.get("enabled") else None
        if rc:
            return rc["call"], rc["p"]
        c, _t, p = stage_call(f)
        return c, (max(p, 1 - p) if p is not None else None)
    flips = []                                 # (is_holdout, sealed_p, sealed_won, early_won, early_price, sealed_price)
    stage_pnl = {"early": [], "sealed": []}
    hold_set = {id(r) for r in hold}
    for r in rounds:
        fe, fs_ = r["f"].get(240), r["f"].get(480)
        if not fe or not fs_:
            continue
        ce, _pe = _live_call(fe, "early")
        cs_, ps_ = _live_call(fs_, "sealed")
        up = r["m"]["result"] == "yes"
        for k, c, f in (("early", ce, fe), ("sealed", cs_, fs_)):
            if c:
                pr = price_of(c == "YES", f["kp"])
                stage_pnl[k].append({"win": (c == "YES") == up, "price": pr, "pnl": pnl((c == "YES") == up, pr), "t": 0})
        if ce and cs_ and ce != cs_ and ps_ is not None:
            flips.append((id(r) in hold_set, ps_, (cs_ == "YES") == up, (ce == "YES") == up))
    def _policy_wins(rows, th):
        return sum((sw if p >= th else ew) for _h, p, sw, ew in rows)
    ftr = [x for x in flips if not x[0]]
    fho = [x for x in flips if x[0]]
    best_th, best_w = 0.0, _policy_wins(ftr, 0.0)
    for th in (0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 1.01):
        w_ = _policy_wins(ftr, th)
        if w_ > best_w:
            best_th, best_w = th, w_
    ho_base, ho_pol = _policy_wins(fho, 0.0), _policy_wins(fho, best_th)
    guard_on = bool(best_th > 0 and len(fho) >= 15 and ho_pol >= ho_base)
    out["flip_check"] = {"flips": len(flips), "flips_train": len(ftr), "flips_hold": len(fho),
                         "early_right_on_flips": (sum(x[3] for x in flips) / len(flips)) if flips else None,
                         "threshold": best_th, "hold_wins_always_flip": ho_base, "hold_wins_guarded": ho_pol,
                         "enabled": guard_on, "early": _summ(stage_pnl["early"]), "sealed": _summ(stage_pnl["sealed"])}

    # decisions the live dashboard applies
    rev_ok = {}
    for key in ("early", "sealed"):
        rh = out["stages"][key]["reversal_holdout"]
        ra = out["stages"][key]["reversal"]
        rev_ok[key] = bool(ra["n"] >= MIN_HOLD_N and ra["roi"] is not None and ra["roi"] > 0
                           and (rh["n"] < 8 or (rh["roi"] is not None and rh["roi"] > -0.05)))
    # ---- 2026-10-22: which RSI reads the round better, and are the line-cross zones right? ----
    out["rsi_check"] = {}
    out["cross_check"] = {}
    for key, mark in (("early", 240), ("sealed", 480)):
        rs = [r for r in rounds if r["f"].get(mark)]
        rc = {}
        for meth, fld in (("tradingview", "r1_tv"), ("webull", "r1_wb")):
            mom = [((r["f"][mark][fld] >= 50) == (r["m"]["result"] == "yes")) for r in rs
                   if r["f"][mark].get(fld) is not None and abs(r["f"][mark][fld] - 50) >= 0.5]
            hi = [r for r in rs if r["f"][mark].get(fld) is not None and r["f"][mark][fld] >= 70]
            lo = [r for r in rs if r["f"][mark].get(fld) is not None and r["f"][mark][fld] <= 30]
            ext_mom = sum(1 for r in hi if r["m"]["result"] == "yes") + sum(1 for r in lo if r["m"]["result"] == "no")
            rc[meth] = {"n": len(mom), "acc": (sum(mom) / len(mom)) if mom else None,
                        "ext_n": len(hi) + len(lo), "ext_acc": (ext_mom / (len(hi) + len(lo))) if (hi or lo) else None}
        tv, wb = rc["tradingview"]["acc"] or 0, rc["webull"]["acc"] or 0
        # stay on TradingView (the textbook RSI) unless Webull is CLEARLY better - 2+ points over 200+ rounds - so the shown
        # number doesn't flip back and forth on noise
        rc["pick"] = "webull" if (wb - tv >= 0.02 and rc["webull"]["n"] >= 200) else "tradingview"
        rc["avg_gap"] = (sum(abs(r["f"][mark]["r1_tv"] - r["f"][mark]["r1_wb"]) for r in rs
                             if r["f"][mark].get("r1_tv") is not None and r["f"][mark].get("r1_wb") is not None)
                         / max(1, sum(1 for r in rs if r["f"][mark].get("r1_tv") is not None and r["f"][mark].get("r1_wb") is not None)))
        out["rsi_check"][key] = rc
        buckets = {}
        for r in rs:
            c = min(r["f"][mark]["crosses"], 4)
            fav_yes = r["f"][mark]["kp"] >= 0.5
            win = fav_yes == (r["m"]["result"] == "yes")
            b = buckets.setdefault(c, [0, 0])
            b[0] += 1
            b[1] += win
        out["cross_check"][key] = {str(c): {"n": b[0], "fav_win": b[1] / b[0]} for c, b in sorted(buckets.items())}
    out["decisions"] = {
        "reversal_enabled": rev_ok,
        "rule80": {k: (out["stages"][k]["rule80"].get("best_profit") or out["stages"][k]["rule80"].get("most_rounds"))
                   for k in ("early", "sealed")},
        "rsi_pick": out["rsi_check"]["sealed"]["pick"],
        "reversal_rules": {k: [b["rule"] for b in out["stages"][k].get("reversal_bands") or [] if b.get("validated")]
                           for k in ("early", "sealed")},
        "flip_guard": (out["flip_check"]["threshold"] if out["flip_check"]["enabled"] else None),
        "regime": {k: (out["stages"][k]["regime"]["table"] if out["stages"][k]["regime"]["enabled"] else None)
                   for k in ("early", "sealed")},
    }
    for k in ("early", "sealed"):
        r = out["decisions"]["rule80"][k]
        if r and not r["validated"]:
            out["decisions"]["rule80"][k] = None
    return out


# ============================================================================ runner
def run(days=LOOKBACK_DAYS):
    global RESULTS
    with _lock:
        if STATE["running"]:
            return
        STATE.update({"running": True, "stage": "markets", "started": time.time(), "error": None, "progress": ""})
    try:
        now = time.time()
        since = now - days * 86400
        markets = fetch_markets(since)
        if not markets:
            raise RuntimeError("the market returned no settled rounds")
        STATE["stage"] = "kalshi prices"
        kcache = _load("kalshi_paths.json", {})
        for i, m in enumerate(markets):
            if m["ticker"] not in kcache:
                try:
                    kcache[m["ticker"]] = fetch_kalshi_path(m)
                except Exception:
                    kcache[m["ticker"]] = []
                time.sleep(0.12)
                if i % 100 == 0:
                    _save("kalshi_paths.json", kcache)
            STATE["progress"] = f"market prices {i + 1}/{len(markets)}"
        _save("kalshi_paths.json", kcache)
        STATE["stage"] = "BTC candles"
        start = markets[0]["open"] - 130 * 60
        cb = {int(k): v for k, v in _load("coinbase_1m.json", {}).items()}
        have = sorted(cb)
        if not have or have[0] > start + 3600:
            cb.update(fetch_coinbase(start, markets[-1]["close"] + 60))
        elif have[-1] < markets[-1]["close"]:
            cb.update(fetch_coinbase(have[-1] - 600, markets[-1]["close"] + 60))
        cb = {t: v for t, v in cb.items() if t >= start}
        _save("coinbase_1m.json", cb)
        STATE["stage"] = "order flow"
        bn = {int(k): v for k, v in _load("binance_1m.json", {}).items()}
        hb = sorted(bn)
        try:
            if not hb or hb[0] > start + 3600:
                bn.update(fetch_binance(start, markets[-1]["close"] + 60))
            elif hb[-1] < markets[-1]["close"]:
                bn.update(fetch_binance(hb[-1] - 600, markets[-1]["close"] + 60))
        except Exception:
            pass
        bn = {t: v for t, v in bn.items() if t >= start}
        _save("binance_1m.json", bn)
        STATE["stage"] = "replaying rounds"
        rounds = []
        for m in markets:
            kp = kcache.get(m["ticker"]) or []
            line_fb = None
            if not m["strike"]:
                o_min = int(m["open"] // 60 * 60)
                line_fb = cb.get(o_min, [None] * 4)[0]
            fs = {}
            for mark in (240, 480):
                try:
                    f = features(m, mark, cb, bn, kp, line_fb)
                except Exception:
                    f = None
                if f:
                    fs[mark] = f
            if fs:
                rounds.append({"m": m, "f": fs})
        if len(rounds) < 100:
            raise RuntimeError(f"only {len(rounds)} rounds had complete data")
        STATE["stage"] = "scoring"
        res = evaluate(rounds)
        res.update({"generated": time.time(), "days": days, "flow_minutes": len(bn), "price_minutes": len(cb),
                    "markets_listed": len(markets), "strike_missing": sum(1 for m in markets if not m["strike"])})
        RESULTS = res
        _save("backtest_results.json", res)
        STATE.update({"stage": "done", "finished": time.time()})
        try:     # also into the server log, so it can be read from Railway's logs without logging in to the site
            for ln in summary_text(res).splitlines():
                print("[backtest] " + ln)
        except Exception:
            pass
    except Exception as e:
        STATE.update({"stage": "failed", "error": repr(e), "finished": time.time()})
        print(f"[backtest] FAILED: {e!r}")
    finally:
        STATE["running"] = False


def load_saved():
    global RESULTS
    if RESULTS is None:
        RESULTS = _load("backtest_results.json", None)
    return RESULTS


def start_background(delay=90, every_hours=24):
    def loop():
        time.sleep(delay)
        while True:
            run()
            time.sleep(every_hours * 3600)
    threading.Thread(target=loop, daemon=True, name="backtest").start()


def decisions():
    r = load_saved()
    return (r or {}).get("decisions") or {}


def summary_text(r=None):
    r = r or load_saved()
    if not r:
        return f"Backtest not finished yet - stage: {STATE['stage']} {STATE['progress']} {STATE.get('error') or ''}"
    pct = lambda x: "-" if x is None else f"{x * 100:.1f}%"
    roi = lambda x: "-" if x is None else f"{x * 100:+.1f}%"
    L = [f"BACKTEST {r['days']} days, {r['rounds']} rounds ({r['from']} .. {r['to']}), holdout = newest {r['holdout_rounds']}",
         f"data: {r['price_minutes']:,} price minutes, {r['flow_minutes']:,} flow minutes, strike missing on {r['strike_missing']} rounds",
         "ROI = profit per $1 staked at the market's price at that minute + 1c slippage + taker fee"]
    for k in ("early", "sealed"):
        s = r["stages"][k]
        L.append(f"\n== {k.upper()} ({'4:00' if k == 'early' else '8:00'})")
        for lab in ("favorite", "current", "reversal", "reversal_holdout"):
            x = s[lab]
            ap = "-" if x["avg_price"] is None else f"{x['avg_price']:.2f}"
            L.append(f"  {lab:17s} n={x['n']:5d} win={pct(x['win'])} roi={roi(x['roi'])} avg price={ap}")
        for t, x in sorted(s["current_by_tier"].items(), key=lambda z: str(z[0])):
            L.append(f"    tier {t:6s} n={x['n']:5d} win={pct(x['win'])} roi={roi(x['roi'])}")
        for bd in s.get("reversal_bands") or []:
            ru = bd.get("rule")
            if not ru:
                L.append(f"  REVERSAL RULE {bd['band']}: nothing beat its price on the training rounds -> off")
                continue
            tr_, ho = bd["train"], bd["holdout"]
            L.append(f"  REVERSAL RULE {bd['band']}: price within {ru['d'] * 100:.2f}% of line, crosses >= {ru['c']}, {ru['v']}+ reads turning"
                     f"{', RSI stretched' if ru['rsi'] else ''}{', trend turned' if ru.get('tr') else ''}")
            L.append(f"    train n={tr_['n']} win={pct(tr_['win'])} at {tr_['avg_price'] * 100:.0f}c roi={roi(tr_['roi'])} | newest unseen "
                     f"n={ho['n']} win={pct(ho['win'])} at {(ho['avg_price'] or 0) * 100:.0f}c roi={roi(ho['roi'])} -> {'LIVE' if bd['validated'] else 'not used'}")
        L.append("  reversal sweep (min flip score / min votes):")
        for x in s["reversal_sweep"]:
            L.append(f"    {x['min_score']:3d}/{x['min_votes']}  n={x['n']:4d} win={pct(x['win'])} roi={roi(x['roi'])}")
        for lab, pk in s["rule80"].items():
            ru = pk["rule"]
            L.append(f"  80% rule [{lab}] fav price>={ru['k']:.2f} cushion>={ru['d'] * 100:.2f}% crosses<={ru['c']} agree>={ru['a']} "
                     f"oppose<={ru['o']} rsi_guard={ru['rsi']}")
            L.append(f"    train   n={pk['train']['n']} win={pct(pk['train']['win'])} roi={roi(pk['train']['roi'])}")
            L.append(f"    holdout n={pk['holdout']['n']} win={pct(pk['holdout']['win'])} roi={roi(pk['holdout']['roi'])} "
                     f"-> {'VALIDATED 80%+' if pk['validated'] else 'NOT validated'}, {'profitable' if pk['profitable'] else 'not profitable'}, "
                     f"covers {pk['coverage'] * 100:.0f}% of rounds")
        if not s["rule80"]:
            L.append("  80% rule: no filter reached 82% on the training rounds with 40+ trades")
        rg = s.get("regime")
        if rg:
            h, c = rg["holdout"], rg["current_holdout"]
            L.append(f"  PRICE-vs-TARGET REGIME (newest {h['n']} unseen rounds): regime win={pct(h['win'])} "
                     f"({h.get('wins', 0)}W) vs current rules win={pct(c['win'])} ({c.get('wins', 0)}W) "
                     f"-> {'LIVE' if rg['enabled'] else 'not used (did not beat current)'}")
            ov = rg["overrides"]
            L.append(f"    regime overruled the current call {ov['n']}x and was right {ov['won']}x"
                     + "".join(f" | {lv}: {pct(x['win'])} of {x['n']}" for lv, x in rg["by_level"].items()))
            lc = rg.get("loss_check") or {}
            if lc:
                L.append("    WHERE THE CURRENT RULES LOSE: " + " | ".join(
                    f"{k.replace('_', ' ')}: win {pct(v['win'])} of {v['n']}, {v['loss_share'] * 100:.0f}% of all losses, "
                    f"roi {roi(v.get('roi'))} at avg price {v.get('avg_price', 0):.2f}"
                    for k, v in lc.items()))
                kept = [lc[k] for k in ("with_trend", "no_trend") if k in lc]
                if kept and "against_trend" in lc:
                    kn = sum(v["n"] for v in kept)
                    kw = sum(v["win"] * v["n"] for v in kept)
                    ku = sum(v.get("units", 0) for v in kept)
                    au = lc["against_trend"].get("units", 0)
                    L.append(f"    SKIPPING AGAINST-TREND CALLS: win {pct(kw / kn)} on {kn} calls ({lc['against_trend']['n']} rounds sat out) | "
                             f"profit per $100/call: kept calls {ku * 100:+,.0f} vs all calls {(ku + au) * 100:+,.0f} "
                             f"(the skipped ones made {au * 100:+,.0f})")
            edges = ["<-0.15%"] + [f"{REG_DIST[i] * 100:+.3f}..{REG_DIST[i + 1] * 100:+.3f}%" for i in range(len(REG_DIST) - 1)] + [">+0.15%"]
            L.append("    UP won from each spot vs the line: " + " | ".join(
                f"{edges[int(k)]}: {x['up'] / x['n'] * 100:.0f}% of {x['n']}" for k, x in rg["dist_map"].items() if x["n"]))
    for k in ("early", "sealed"):
        rc = (r.get("rsi_check") or {}).get(k)
        if rc:
            L.append(f"\nRSI CHECK {k.upper()} (RSI>50 = up, scored against the round): "
                     + " | ".join(f"{m}: {pct(rc[m]['acc'])} of {rc[m]['n']}, extremes (70+/30-) {pct(rc[m]['ext_acc'])} of {rc[m]['ext_n']}"
                                  for m in ("tradingview", "webull"))
                     + f" -> more accurate: {rc['pick'].upper()}, avg gap {rc['avg_gap']:.1f} pts")
        cc = (r.get("cross_check") or {}).get(k)
        if cc:
            L.append(f"LINE CROSS CHECK {k.upper()} (1-min closes; market favorite's win rate by crosses so far): "
                     + " | ".join(f"{c}{'+' if c == '4' else ''}: {pct(x['fav_win'])} of {x['n']}" for c, x in cc.items()))
    d = r.get("decisions") or {}
    fc = r.get("flip_check")
    if fc:
        e_, s_ = fc["early"], fc["sealed"]
        L.append(f"\nEARLY vs SEALED (as called live): early win={pct(e_['win'])} roi={roi(e_['roi'])} | sealed win={pct(s_['win'])} "
                 f"roi={roi(s_['roi'])}")
        L.append(f"  sealed flipped the early call {fc['flips']}x; the EARLY side was right {pct(fc['early_right_on_flips'])} of those")
        L.append(f"  flip guard: {('sealed must be ' + format(fc['threshold'] * 100, '.0f') + '%+ sure to flip') if fc['threshold'] <= 1 else 'sealed never flips the early call'} -> newest rounds: "
                 f"{fc['hold_wins_guarded']} wins guarded vs {fc['hold_wins_always_flip']} always flipping "
                 f"({fc['flips_hold']} flips) -> {'LIVE' if fc['enabled'] else 'not used'}")
    L.append(f"\nPRICE-vs-TARGET REGIME live: early = {'on' if (d.get('regime') or {}).get('early') else 'off'}, "
             f"sealed = {'on' if (d.get('regime') or {}).get('sealed') else 'off'}")
    L.append(f"LIVE DECISIONS: reversal calls enabled = {d.get('reversal_enabled')}; "
             f"80% tag early = {'on' if (d.get('rule80') or {}).get('early') else 'off'}, sealed = {'on' if (d.get('rule80') or {}).get('sealed') else 'off'}")
    return "\n".join(L)
