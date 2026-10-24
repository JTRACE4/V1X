"""Trend study (2026-10-24, user: "develop a better understanding of the trend so we call accurately; if 6 minutes is a
better time to make the call, run the backtest and add it").

Replays every settled BTC 15-minute round in the backtest cache (~30 days) and asks, at 4:00, 6:00 and 8:00:
  * which trend read best predicts how the round ENDS - the 1-minute read used live today, or 5m / 15m / 1h candles,
    or a combination of the bigger timeframes;
  * what happens to win rate and profit when the call is lined up with each trend read (take the trend side when the
    call disagrees, or sit those rounds out).
Everything is scored on the newest 30% of rounds (never used to pick the rule) as well as overall.
Results go to the server log ("[trend study]") and to data_cache/backtest/trend_study.json; the dashboard reads the
picked rule from decisions(). Uses cached data only - nothing is downloaded.
"""
import json
import os
import time

import backtest_engine as bt

TF = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600}
MARKS = (240, 360, 480)
COINS = ("BTC", "XRP")
_state = {}                       # coin -> {"res": ..., "ts": ...}


def _file(coin, base):
    # BTC keeps the original file names; other coins get their own (2026-10-24: XRP was being called with BTC's lessons)
    return os.path.join(bt.CACHE, f"{base}.json" if coin == "BTC" else f"{base}_{coin.lower()}.json")


# ---- XRP replay data (2026-10-24, user: "data pulling problem or algorithm?"): the backtest only ever replayed BTC rounds,
# so every learned XRP rule was really a BTC rule. This pulls XRP's own settled rounds, their market price paths and
# XRP-USD 1-minute candles, cached and topped up incrementally.
def _xrp_data(max_new_paths=3200):
    series = "KXXRP15M"
    now = time.time()
    mk = bt._load("xrp_markets.json", [])
    if not mk or now - max(m["close"] for m in mk) > 1800:
        out, cursor = [], None
        for _ in range(60):
            params = {"series_ticker": series, "status": "settled", "limit": 1000, "min_close_ts": int(now - bt.LOOKBACK_DAYS * 86400)}
            if cursor:
                params["cursor"] = cursor
            j = bt._get(f"{bt.KALSHI}/markets", params)
            batch = j.get("markets") or []
            out += batch
            cursor = j.get("cursor")
            if not batch or not cursor:
                break
            time.sleep(0.4)
        rows = []
        for m in out:
            res_ = (m.get("result") or "").lower()
            if res_ not in ("yes", "no"):
                continue
            try:
                o, c = bt._ts(m["open_time"]), bt._ts(m["close_time"])
            except Exception:
                continue
            if c - o < 800 or c - o > 1000:
                continue
            st = m.get("floor_strike")
            rows.append({"ticker": m["ticker"], "open": o, "close": c, "strike": float(st) if st else None, "result": res_})
        if rows:
            mk = sorted(rows, key=lambda r: r["open"])
            bt._save("xrp_markets.json", mk)
    kc = bt._load("xrp_kalshi_paths.json", {})
    todo = [m for m in mk if m["ticker"] not in kc][-max_new_paths:]
    for i, m in enumerate(todo):
        try:
            j = bt._get(f"{bt.KALSHI}/series/{series}/markets/{m['ticker']}/candlesticks",
                        {"period_interval": 1, "start_ts": int(m["open"]), "end_ts": int(m["close"])})
            pts = []
            for c in j.get("candlesticks") or []:
                pr, bid, ask = c.get("price") or {}, c.get("yes_bid") or {}, c.get("yes_ask") or {}
                p_ = bt._cents(pr.get("close_dollars"))
                b_ = bt._cents(bid.get("close_dollars"))
                a_ = bt._cents(ask.get("close_dollars"))
                mid = (b_ + a_) / 2 if (b_ is not None and a_ is not None and a_ > 0) else None
                v = mid if mid is not None else p_
                if v is not None:
                    pts.append((int(c["end_period_ts"]), round(v, 4), b_, a_))
            kc[m["ticker"]] = pts
        except Exception:
            kc[m["ticker"]] = []
        time.sleep(0.4)                                   # leave room for the live market tape
        if i % 100 == 99:
            bt._save("xrp_kalshi_paths.json", kc)
    if todo:
        bt._save("xrp_kalshi_paths.json", kc)
    cb = {int(k): v for k, v in bt._load("xrp_coinbase_1m.json", {}).items()}
    if mk:
        start = mk[0]["open"] - 3 * 86400                  # 3 extra days so 1h / daily reads have history
        end = mk[-1]["close"] + 60
        have = sorted(cb)
        ranges = []
        if not have or have[0] > start + 3600:
            ranges.append((start, end))
        elif have[-1] < end - 120:
            ranges.append((have[-1] - 600, end))
        for a, b in ranges:
            t = int(a // 60 * 60)
            while t < b:
                t2 = min(b, t + 300 * 60)
                try:
                    j = bt._get("https://api.exchange.coinbase.com/products/XRP-USD/candles",
                                {"granularity": 60, "start": bt.dt.datetime.fromtimestamp(t, bt.dt.timezone.utc).isoformat(),
                                 "end": bt.dt.datetime.fromtimestamp(t2, bt.dt.timezone.utc).isoformat()})
                    for r in j or []:
                        cb[int(r[0])] = [float(r[3]), float(r[2]), float(r[1]), float(r[4]), float(r[5])]
                except Exception:
                    pass
                t = t2
                time.sleep(0.25)
        cb = {t: v for t, v in cb.items() if t >= start}
        bt._save("xrp_coinbase_1m.json", cb)
    done = sum(1 for m in mk if m["ticker"] in kc)
    print(f"[trend study] XRP data: {len(mk)} settled rounds, {done} with market prices, {len(cb):,} price minutes")
    return mk, kc, cb, {}


def _resample(cb, sec):
    """{bucket_start: [o, h, l, c]} for completed and partial buckets of `sec` seconds from 1-minute candles."""
    out = {}
    for t in sorted(cb):
        b = t // sec * sec
        o, h, l, c = cb[t][:4]
        x = out.get(b)
        if x is None:
            out[b] = [o, h, l, c, t]
        else:
            x[1] = max(x[1], h)
            x[2] = min(x[2], l)
            x[3] = c
            x[4] = t
    return out


def _series_at(cb, rs, sec, last_min, n=120):
    """Candles of `sec` seconds up to and including the minute `last_min` (the forming bucket only has minutes so far)."""
    if sec == 60:
        ts = [last_min - 60 * k for k in range(n)][::-1]
        return [[t, *cb[t][:4]] for t in ts if t in cb]
    cur = last_min // sec * sec
    out = []
    for k in range(n - 1, 0, -1):
        b = cur - k * sec
        x = rs.get(b)
        if x and x[4] >= b + sec - 60:          # completed bucket
            out.append([b, x[0], x[1], x[2], x[3]])
    # forming bucket built from the minutes so far
    o = h = l = c = None
    for t in range(cur, last_min + 1, 60):
        v = cb.get(t)
        if not v:
            continue
        if o is None:
            o, h, l, c = v[0], v[1], v[2], v[3]
        else:
            h, l, c = max(h, v[1]), min(l, v[2]), v[3]
    if o is not None:
        out.append([cur, o, h, l, c])
    return out


STRUCT_TF = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "1d": 86400}


def fvg_vote(cs, look=30):
    """Fair value gaps: a 3-candle gap (candle 1's high below candle 3's low = bullish gap, candle 1's low above candle 3's
    high = bearish gap) that price has NOT filled since. +1 when the nearest unfilled gap below price is bullish support
    and none sits above as resistance, -1 the mirror, else 0."""
    if len(cs) < 5:
        return 0
    cs = cs[-look:]
    px = cs[-1][4]
    bull = bear = 0
    for i in range(2, len(cs)):
        h1, l1 = cs[i - 2][2], cs[i - 2][3]
        h3, l3 = cs[i][2], cs[i][3]
        later = cs[i + 1:]
        if h1 < l3:                                       # bullish gap [h1, l3]
            if not any(c[3] <= h1 for c in later) and px >= h1:
                bull += 1
        elif l1 > h3:                                     # bearish gap [h3, l1]
            if not any(c[2] >= l1 for c in later) and px <= l1:
                bear += 1
    return 1 if bull > bear else (-1 if bear > bull else 0)


def sweep_vote(cs, look=20, recent=3):
    """Liquidity sweep: one of the last `recent` candles pokes past the prior `look`-candle high (or low) and closes back
    inside - stops taken, then rejected. A swept HIGH points down (-1), a swept LOW points up (+1)."""
    if len(cs) < look + recent:
        return 0
    v = 0
    for j in range(len(cs) - recent, len(cs)):
        prior = cs[j - look:j]
        hi, lo = max(c[2] for c in prior), min(c[3] for c in prior)
        c = cs[j]
        if c[2] > hi and c[4] < hi:
            v -= 1
        if c[3] < lo and c[4] > lo:
            v += 1
    return 1 if v > 0 else (-1 if v < 0 else 0)


def _struct(t, s):
    """s = {"fvg_5m": v, "swp_5m": v, ...}. Adds 'struct' (5m/15m/1h gaps + sweeps, net 2+) and 'struct_all' (all tfs)."""
    a = sum(s.get(f"{k}_{tf}", 0) for k in ("fvg", "swp") for tf in ("5m", "15m", "1h"))
    b = sum(s.values())
    t.update(s)
    t["struct"] = 1 if a >= 2 else (-1 if a <= -2 else 0)
    t["struct_all"] = 1 if b >= 3 else (-1 if b <= -3 else 0)
    h = t.get("htf2of3", 0)
    t["htf+struct"] = h if (h and t["struct"] in (0, h)) and not (t["struct"] == -h) else 0
    t["htf&struct"] = h if (h and t["struct"] == h) else 0
    return t


def _combos(t):
    """Extra trend reads built from the per-timeframe ones."""
    t5, t15, t60 = t.get("5m", 0), t.get("15m", 0), t.get("1h", 0)
    v = [x for x in (t5, t15, t60) if x]
    s = sum(v)
    t["5+15"] = t5 if (t5 and t5 == t15) else 0
    t["htf2of3"] = (1 if s >= 2 else (-1 if s <= -2 else 0))          # 2+ of 5m/15m/1h agree, counting a flat as no vote
    t["htf_any"] = (1 if s > 0 else (-1 if s < 0 else 0)) if len(v) >= 1 and not (1 in v and -1 in v) else 0
    t["15+1h"] = t15 if (t15 and t15 == t60) else 0
    return t


def _summ(rows):
    n = len(rows)
    if not n:
        return {"n": 0, "win": None, "pnl": 0.0, "per": None}
    w = sum(1 for r in rows if r[0])
    p = sum(r[1] for r in rows) * 100
    return {"n": n, "win": round(w / n, 4), "pnl": round(p, 1), "per": round(p / n, 2)}


def run_all():
    for coin in COINS:
        try:
            run(coin)
        except Exception as e:
            print(f"[trend study] {coin}: {e!r}")


def run(coin="BTC"):
    tr = bt._fn.get("trend_read")
    if not tr:
        print("[trend study] trend_read not handed over yet")
        return None
    if coin == "BTC":
        markets = [m for m in bt._load("markets.json", []) if m.get("result") in ("yes", "no")]
        kcache = bt._load("kalshi_paths.json", {})
        cb = {int(k): v for k, v in bt._load("coinbase_1m.json", {}).items()}
        bn = {int(k): v for k, v in bt._load("binance_1m.json", {}).items()}
    else:
        markets, kcache, cb, bn = _xrp_data()
        markets = [m for m in markets if m.get("result") in ("yes", "no") and kcache.get(m["ticker"])]
    if len(markets) < 200 or not cb:
        print(f"[trend study] {coin}: not enough data yet ({len(markets)} rounds)")
        return None
    rs = {sec: _resample(cb, sec) for sec in (300, 900, 3600, 86400)}
    feeds, walls = _load_live_logs()
    print(f"[trend study] {coin}: live feed log covers {sum(1 for m in markets if m['ticker'] in feeds)} rounds, walls {sum(1 for m in markets if m['ticker'] in walls)}")
    rows = []                                    # one per round: {mark: {...}}
    for m in sorted(markets, key=lambda x: x["open"]):
        kp = kcache.get(m["ticker"]) or []
        line_fb = None
        if not m["strike"]:
            line_fb = cb.get(int(m["open"] // 60 * 60), [None] * 4)[0]
        up = m["result"] == "yes"
        per = {}
        for mark in MARKS:
            try:
                f = bt.features(m, mark, cb, bn, kp, line_fb)
            except Exception:
                f = None
            if not f:
                continue
            last_min = int((f["T"] - 60) // 60 * 60)
            t = {}
            for name, sec in TF.items():
                cs = _series_at(cb, rs.get(sec), sec, last_min)
                try:
                    t[name] = tr(cs)[0] if len(cs) >= 55 else 0
                except Exception:
                    t[name] = 0
            _combos(t)
            sv = {}
            for name, sec in STRUCT_TF.items():
                cs = _series_at(cb, rs.get(sec), sec, last_min, n=60 if sec < 86400 else 30)
                sv[f"fvg_{name}"] = fvg_vote(cs)
                sv[f"swp_{name}"] = sweep_vote(cs, look=20 if sec < 86400 else 10)
            _struct(t, sv)
            call, _tier, p = bt.stage_call(f)
            fav = "YES" if f["kp"] >= 0.5 else "NO"
            # 2026-10-24 (ideas from the Dominator dashboard the user shared): line behavior (crosses so far + one-way
            # market), choppiness of the last 4 minutes, and the 4-hour regime - all learnable from history
            ex = {"crosses": f["crosses"]}
            cl4 = [cb[last_min - 60 * k][3] for k in range(5) if (last_min - 60 * k) in cb]
            ex["chop"] = (sum(abs(cl4[i] / cl4[i + 1] - 1) for i in range(len(cl4) - 1)) * 1000) if len(cl4) >= 3 else 0.0
            p4 = cb.get(last_min - 240 * 60)
            ex["r4h"] = ((f["spot"] / p4[3] - 1) * 100) if p4 else 0.0
            r1 = f.get("r1_tv")
            if r1 is not None:
                ex["rsi"] = (r1 - 50) / 50
            lv = _nearest(feeds.get(m["ticker"]), 900 - mark)
            if lv:
                if lv[1] is not None:
                    ex["xflow"] = lv[1] - 0.5
                if lv[2] is not None:
                    ex["kmoney"] = lv[2] - 0.5
                if lv[3] is not None:
                    ex["liq"] = lv[3] - 0.5
                ex["has_live"] = lv[1] is not None or lv[2] is not None
            elif f.get("f2") is not None:                 # BTC replay: exchange taker flow from the candles
                ex["xflow"] = f["f2"] - 0.5
            wv = _nearest(walls.get(m["ticker"]), 900 - mark)
            if wv:
                ex["walls"] = wv[1]
            t["_ex"] = ex
            per[mark] = {"kp": f["kp"], "call": call, "fav": fav, "t": t, "dist": f["dist"]}
        if per:
            rows.append({"up": up, "ticker": m["ticker"], "open": m["open"], "per": per, "kpath": kp})
    if len(rows) < 200:
        print(f"[trend study] only {len(rows)} rounds replayed")
        return None
    split = int(len(rows) * 0.7)
    names = (list(TF) + ["5+15", "htf2of3", "htf_any", "15+1h", "struct", "struct_all", "htf+struct", "htf&struct"]
             + [f"{k}_{tf}" for k in ("fvg", "swp") for tf in STRUCT_TF])

    def outcome(r, mark, side):
        x = r["per"][mark]
        win = (side == "YES") == r["up"]
        return (win, bt.pnl(win, bt.price_of(side == "YES", x["kp"])))

    res = {"rounds": len(rows), "unseen": len(rows) - split, "generated": time.time(), "marks": {}}
    for mark in MARKS:
        R = [r for r in rows if mark in r["per"]]
        sp = int(len(R) * 0.7)
        part = {"all": R, "train": R[:sp], "unseen": R[sp:]}
        mk = {"trend_accuracy": {}, "strategies": {}}
        # how often each trend read's side is how the round ended (when it has a side)
        for nm in names:
            acc = {}
            for pn, P in part.items():
                g = [((r["per"][mark]["t"][nm] > 0) == r["up"]) for r in P if r["per"][mark]["t"].get(nm)]
                acc[pn] = {"n": len(g), "win": round(sum(g) / len(g), 4) if g else None, "cover": round(len(g) / len(P), 3) if P else 0}
            mk["trend_accuracy"][nm] = acc
        # strategies
        def strat(fn):
            out = {}
            for pn, P in part.items():
                g = []
                for r in P:
                    side = fn(r["per"][mark])
                    if side:
                        g.append(outcome(r, mark, side))
                s = _summ(g)
                s["cover"] = round(s["n"] / len(P), 3) if P else 0
                out[pn] = s
            return out
        mk["strategies"]["current (1m skip)"] = strat(
            lambda x: None if (x["call"] and x["t"]["1m"] and (x["t"]["1m"] > 0) != (x["call"] == "YES")) else x["call"])
        mk["strategies"]["call, no trend"] = strat(lambda x: x["call"])
        mk["strategies"]["market favorite"] = strat(lambda x: x["fav"])
        for nm in names:
            mk["strategies"][f"skip vs {nm}"] = strat(
                lambda x, nm=nm: None if (x["call"] and x["t"][nm] and (x["t"][nm] > 0) != (x["call"] == "YES")) else x["call"])
            mk["strategies"][f"follow {nm}"] = strat(
                lambda x, nm=nm: (("YES" if x["t"][nm] > 0 else "NO") if (x["call"] and x["t"][nm]) else x["call"]))
            mk["strategies"][f"only with {nm}"] = strat(
                lambda x, nm=nm: x["call"] if (x["call"] and x["t"][nm] and (x["t"][nm] > 0) == (x["call"] == "YES")) else None)
        if mark == 480:     # early (4:00) vs sealed (8:00): hold the early side, or only seal when the two agree
            def _early(r):
                e = r["per"].get(240)
                return e["call"] if e else None
            def strat2(fn):
                out = {}
                for pn, P in part.items():
                    g = []
                    for r in P:
                        side = fn(r["per"][mark], _early(r))
                        if side:
                            g.append(outcome(r, mark, side))
                    s_ = _summ(g)
                    s_["cover"] = round(s_["n"] / len(P), 3) if P else 0
                    out[pn] = s_
                return out
            mk["strategies"]["seal = early side"] = strat2(lambda x, e: e or x["call"])
            mk["strategies"]["seal only if early agrees"] = strat2(lambda x, e: x["call"] if (e and x["call"] == e) else None)
            for nm in ("htf2of3", "struct", "htf&struct", "htf+struct", "15m", "1h"):
                mk["strategies"][f"seal if early agrees + with {nm}"] = strat2(
                    lambda x, e, nm=nm: x["call"] if (e and x["call"] == e and x["t"][nm] and (x["t"][nm] > 0) == (x["call"] == "YES")) else None)
            dis = [r for r in part["all"] if _early(r) and r["per"][mark]["call"] and _early(r) != r["per"][mark]["call"]]
            both = [r for r in part["all"] if _early(r) and r["per"][mark]["call"]]
            mk["disagree"] = {"rate": round(len(dis) / len(both), 3) if both else None, "n": len(dis),
                              "sealed_right": round(sum(1 for r in dis if (r["per"][mark]["call"] == "YES") == r["up"]) / len(dis), 3) if dis else None}
        res["marks"][str(mark)] = mk
    # pick (user: "a much better win rate AND profitability"): per call time, among rules that call at least half the rounds,
    # win at least as often as today's rule on the unseen rounds AND on the older ones, and make more money on both -
    # the one with the most unseen profit. Longshot-heavy rules can't win this way. None passes -> keep today's rule.
    pick = {}
    for mark in MARKS:
        S = res["marks"][str(mark)]["strategies"]
        cur = S["current (1m skip)"]
        ok = []
        for k, v in S.items():
            u, t = v["unseen"], v["train"]
            if k == "current (1m skip)" or not u["n"] or not t["n"]:
                continue
            if u["n"] < 60 or u["cover"] < 0.5:
                continue
            if u["win"] < (cur["unseen"]["win"] or 0) or t["win"] < (cur["train"]["win"] or 0) - 0.01:
                continue
            if u["per"] <= (cur["unseen"]["per"] or 0) or t["per"] <= (cur["train"]["per"] or 0):
                continue
            ok.append((k, v))
        best = max(ok, key=lambda kv: (kv[1]["unseen"]["pnl"], kv[1]["unseen"]["win"])) if ok else None
        pick[str(mark)] = {"rule": best[0] if best else None, "stats": best[1] if best else None, "current": cur}
    res["pick"] = pick
    try:
        cur_by = {str(mk_): res["marks"][str(mk_)]["strategies"]["current (1m skip)"] for mk_ in MARKS}
        m2 = method2(rows, outcome, cur_by)
        _m2[coin] = m2
        mf = _file(coin, "method2")
        with open(mf + ".tmp", "w") as fh:
            json.dump(m2, fh)
        os.replace(mf + ".tmp", mf)
        res["method2"] = {k: {kk: vv for kk, vv in v.items() if kk != "w"} for k, v in m2.items()}
        res["method2_w"] = {k: dict(zip(["bias"] + M2_FEATS, [round(x, 3) for x in v["w"]])) for k, v in m2.items()}
        res["majority"] = majority_eval(rows, outcome, m2)
        try:
            res["sealed_report"] = sealed_report(rows, outcome, m2)
            _log_sealed(coin, res["sealed_report"])
            res["edge_report"] = edge_report(rows, outcome, m2)
            _log_edge(coin, res["edge_report"])
            res["tier_report"] = tier_report(rows, outcome, m2)
            _log_tiers(coin, res["tier_report"])
            res["dip_report"] = dip_report(rows, outcome, m2)
            _log_dip(coin, res["dip_report"])
        except Exception as _sre:
            print(f"[8:00 report] {coin}: {_sre!r}")
    except Exception as _e2:
        print(f"[trend study] method v2 failed: {_e2!r}")
    res["coin"] = coin
    FILE = _file(coin, "trend_study")
    os.makedirs(os.path.dirname(FILE), exist_ok=True)
    with open(FILE + ".tmp", "w") as fh:
        json.dump(res, fh)
    os.replace(FILE + ".tmp", FILE)
    _state[coin] = {"res": res, "ts": time.time()}
    _log(res)
    return res


def _f(s):
    if not s or not s.get("n"):
        return "n=0"
    return f"n={s['n']} win={s['win']:.1%} ${s['pnl']:+,.0f} ({s['per']:+.1f}/call)" + (f" cover={s['cover']:.0%}" if "cover" in s else "")


def _log(res):
    print(f"[trend study] {res.get('coin', 'BTC')}: {res['rounds']} rounds replayed, newest {res['unseen']} never used to pick")
    for mk_, v in (res.get("method2") or {}).items():
        lab = {"240": "4:00", "360": "6:00", "480": "8:00"}[mk_]
        print(f"[method v2] {res.get('coin', 'BTC')} {lab}: {'LIVE' if v['valid'] else 'not better - not used'} | confidence bar {v['thr']} flip bar {v['flip']}"
              f" | unseen {_f(v['unseen'])} vs current {_f(v.get('current_unseen'))} | train {_f(v.get('train'))}")
        print(f"[method v2] {res.get('coin', 'BTC')} {lab} weights: {res['method2_w'][mk_]}")
    mj = res.get("majority") or {}
    for nm_, v in (mj.get("modes") or {}).items():
        print(f"[majority] {res.get('coin', 'BTC')} {nm_:<36} unseen {_f(v['unseen'])} | all {_f(v['all'])}")
    if mj:
        print(f"[majority] {res.get('coin', 'BTC')} PICK: {mj.get('pick') or 'the 8:00 read alone did better - majority stays off'}")
    for mark, mk in res["marks"].items():
        lab = {"240": "4:00", "360": "6:00", "480": "8:00"}[mark]
        acc = " | ".join(f"{k} {v['unseen']['win']:.0%}/{v['unseen']['cover']:.0%}" for k, v in mk["trend_accuracy"].items()
                         if v["unseen"]["win"] is not None)
        print(f"[trend study] {res.get('coin', 'BTC')} {lab} trend read -> round result (unseen win / how often it has a side): {acc}")
        S = mk["strategies"]
        top = sorted(((k, v) for k, v in S.items() if v["unseen"]["n"] >= 60 and v["unseen"]["cover"] >= 0.5),
                     key=lambda kv: -((kv[1]["unseen"]["win"] or 0) + (0.0 if (kv[1]["unseen"]["per"] or 0) > 0 else -1)))[:8]
        for k in ("current (1m skip)", "call, no trend", "market favorite"):
            print(f"[trend study] {res.get('coin', 'BTC')} {lab} {k:<22} unseen {_f(S[k]['unseen'])} | all {_f(S[k]['all'])}")
        for k, v in top:
            print(f"[trend study] {res.get('coin', 'BTC')} {lab} TOP {k:<18} unseen {_f(v['unseen'])} | all {_f(v['all'])}")
        if mk.get("disagree"):
            d_ = mk["disagree"]
            print(f"[trend study] {res.get('coin', 'BTC')} 8:00 vs 4:00: the calls disagreed in {d_['rate']:.0%} of rounds ({d_['n']}); when they did, the sealed side was right {d_['sealed_right']:.0%}")
        p = res["pick"][mark]
        print(f"[trend study] {res.get('coin', 'BTC')} {lab} PICK: {p['rule'] or 'none beat the current rule on win rate AND profit - kept'}"
              + (f" | unseen {_f(p['stats']['unseen'])} vs current {_f(p['current']['unseen'])}" if p['rule'] else ""))


def load(coin="BTC"):
    st = _state.setdefault(coin, {"res": None})
    if st.get("res") is None:
        try:
            with open(_file(coin, "trend_study")) as fh:
                st["res"] = json.load(fh)
        except Exception:
            st["res"] = {}
    return st["res"] or {}


def decisions(coin="BTC"):
    """{"240": rule or None, "360": ..., "480": ...} - the picked trend rule per call time."""
    return {k: v.get("rule") for k, v in (load(coin).get("pick") or {}).items()}


def trend_from_windows(win, trend_read):
    """Live: the same trend reads from the dashboard's candle windows {tf: [[ts,o,h,l,c], ...]}."""
    t = {}
    for name in TF:
        cs = (win or {}).get(name) or []
        try:
            t[name] = trend_read([list(c) for c in cs])[0] if len(cs) >= 55 else 0
        except Exception:
            t[name] = 0
    _combos(t)
    sv = {}
    for name, sec in STRUCT_TF.items():
        cs = [list(c) for c in ((win or {}).get(name) or [])][-(60 if sec < 86400 else 30):]
        sv[f"fvg_{name}"] = fvg_vote(cs)
        sv[f"swp_{name}"] = sweep_vote(cs, look=20 if sec < 86400 else 10)
    return _struct(t, sv)


def apply_rule(rule, call, t, early=None):
    """(side or None, note) for a live call under a picked rule. call = 'YES'/'NO'/None, t = trend_from_windows(),
    early = the 4:00 call (for the sealed-call rules)."""
    if not rule or not call or rule in ("call, no trend",):
        return call, ""
    if rule == "seal = early side":
        return (early or call), ("held the 4:00 side" if early and early != call else "")
    if rule.startswith("seal only if early agrees") or rule.startswith("seal if early agrees"):
        if not early or early != call:
            return None, "the 4:00 and 8:00 reads disagree"
        if " + with " in rule:
            nm = rule.split(" + with ", 1)[1]
            v = t.get(nm, 0)
            if not v or (v > 0) != (call == "YES"):
                return None, f"not backed by the {nm} trend"
            return call, f"4:00 and 8:00 agree, with the {nm} trend"
        return call, "4:00 and 8:00 agree"
    if rule == "market favorite" or rule == "current (1m skip)":
        return call, ""
    kind, nm = rule.split(" ", 1) if " " in rule else (rule, "")
    if kind == "skip":
        nm = nm.replace("vs ", "")
    if kind == "only":
        nm = nm.replace("with ", "")
    v = t.get(nm, 0)
    if not v:
        return (call, "") if kind != "only" else (None, f"no clear {nm} trend")
    side = "YES" if v > 0 else "NO"
    if side == call:
        return call, f"with the {nm} trend"
    if kind == "follow":
        return side, f"switched to the {nm} trend ({'UP' if side == 'YES' else 'DOWN'})"
    return None, f"against the {nm} trend"


# ================================================================== METHOD v2 (2026-10-24, user: "fix the methodology behind the call")
# One model instead of stacked rules: the market's own price (where price sits vs the line, already priced in) PLUS the
# multi-timeframe read - trend on 1m / 5m / 15m / 1h, fair value gaps and liquidity sweeps on 1m / 5m / 15m / 1h / 1d.
# The weights are learned (logistic regression) from the older 70% of rounds; win rate and profit are scored on the newest
# 30%. The confidence bar (only call when the model is this sure) is also picked on the older rounds. The sealed call keeps
# the early side unless the model is clearly surer of the other side (flip bar learned the same way).
import math as _m

M2_FEATS = ["lk", "dist", "1m", "5m", "15m", "1h", "fvg_1m", "fvg_5m", "fvg_15m", "fvg_1h", "fvg_1d",
            "swp_1m", "swp_5m", "swp_15m", "swp_1h", "swp_1d",
            "crosses", "oneway_dist", "chop", "chop_dist", "r4h",
            "xflow", "kmoney", "liq", "rsi", "walls", "has_live"]
_m2 = {}


def _lk(p):
    p = min(0.97, max(0.03, p))
    return _m.log(p / (1 - p))


def m2_x(kp, dist, t):
    ex = t.get("_ex") or {}
    d = max(-3.0, min(3.0, dist * 1000))
    cr = min(4, int(ex.get("crosses") or 0))
    chop = min(5.0, float(ex.get("chop") or 0.0))
    sgn = (1 if d > 0 else (-1 if d < 0 else 0))
    return ([_lk(kp), d] + [float(t.get(k, 0)) for k in M2_FEATS[2:16]]
            + [-sgn * cr / 4.0,                          # more line crosses = less trust in the side price is on
               d if cr == 0 else 0.0,                    # one-way market: distance counts extra when it never crossed
               -sgn * chop / 5.0,                        # choppy last 4 minutes = less trust in the side price is on
               d * chop / 5.0,
               max(-2.0, min(2.0, float(ex.get("r4h") or 0.0))),
               float(ex.get("xflow") or 0.0),               # exchange buyers vs sellers this round, -0.5..+0.5
               float(ex.get("kmoney") or 0.0),              # the market's own money UP vs DOWN this round
               float(ex.get("liq") or 0.0),                 # liquidations: shorts squeezed (+) vs longs flushed (-)
               float(ex.get("rsi") or 0.0),                 # RSI 14 (1 min), -1..+1
               float(ex.get("walls") or 0.0),               # bid wall vs ask wall near price, -1..+1
               1.0 if ex.get("has_live") else 0.0])


def _fit(X, y, l2=0.02, iters=400, lr=0.3):
    n, d = len(X), len(X[0])
    w = [0.0] * (d + 1)
    for _ in range(iters):
        g = [0.0] * (d + 1)
        for xi, yi in zip(X, y):
            z = w[0] + sum(a * b for a, b in zip(w[1:], xi))
            p = 1 / (1 + _m.exp(-max(-30, min(30, z))))
            e = p - yi
            g[0] += e
            for j in range(d):
                g[j + 1] += e * xi[j]
        for j in range(d + 1):
            w[j] -= lr * (g[j] / n + (l2 * w[j] if j else 0))
    return w


def m2_p(w, x):
    z = w[0] + sum(a * b for a, b in zip(w[1:], x))
    return 1 / (1 + _m.exp(-max(-30, min(30, z))))


def method2(rows, outcome, cur_by_mark):
    """Fit + score per mark. Returns {"240": {...}, "480": {...}, "360": {...}}."""
    out = {}
    early_side = {}
    for mark in MARKS:
        R = [r for r in rows if mark in r["per"]]
        sp = int(len(R) * 0.7)
        tr, un = R[:sp], R[sp:]
        X = [m2_x(r["per"][mark]["kp"], r["per"][mark]["dist"], r["per"][mark]["t"]) for r in tr]
        y = [1.0 if r["up"] else 0.0 for r in tr]
        w = _fit(X, y)

        def score(P, thr, flip=None):
            g = []
            for r in P:
                x = r["per"][mark]
                p = m2_p(w, m2_x(x["kp"], x["dist"], x["t"]))
                side = "YES" if p >= 0.5 else "NO"
                conf = max(p, 1 - p)
                if mark == 480 and flip is not None:
                    e = early_side.get(r["ticker"])
                    if e and e != side:
                        if conf < flip:
                            side = e                     # hold the early side
                            conf = 1.0
                if conf < thr:
                    continue
                g.append(outcome(r, mark, side))
            s_ = _summ(g)
            s_["cover"] = round(s_["n"] / len(P), 3) if P else 0
            return s_
        cur = cur_by_mark[str(mark)]
        best = None
        flips = (None,) if mark != 480 else (None, 0.6, 0.7, 0.8, 0.9, 1.01)
        for thr in (0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8):
            for fl in flips:
                s_t = score(tr, thr, fl)
                if s_t["n"] < 40 or s_t["cover"] < 0.5:
                    continue
                if s_t["win"] < (cur["train"]["win"] or 0):
                    continue
                key = (s_t["pnl"], s_t["win"])
                if best is None or key > best[0]:
                    best = (key, thr, fl, s_t)
        if best is None:
            out[str(mark)] = {"w": w, "thr": None, "flip": None, "train": None, "unseen": score(un, 0.5), "valid": False}
            continue
        _k, thr, fl, s_t = best
        s_u = score(un, thr, fl)
        valid = bool(s_u["n"] >= 40 and s_u["win"] is not None and cur["unseen"]["win"] is not None
                     and s_u["win"] >= cur["unseen"]["win"] and s_u["pnl"] > cur["unseen"]["pnl"])
        out[str(mark)] = {"w": w, "thr": thr, "flip": fl, "train": s_t, "unseen": s_u, "valid": valid,
                          "current_unseen": cur["unseen"], "feats": M2_FEATS}
        if mark == 240:
            for r in R:
                x = r["per"][mark]
                p = m2_p(w, m2_x(x["kp"], x["dist"], x["t"]))
                if max(p, 1 - p) >= thr:
                    early_side[r["ticker"]] = "YES" if p >= 0.5 else "NO"
    return out


def m2_model(coin="BTC"):
    if _m2.get(coin) is None:
        try:
            with open(_file(coin, "method2")) as fh:
                _m2[coin] = json.load(fh)
        except Exception:
            _m2[coin] = {}
    return _m2[coin] or {}


LIVE_LOG = os.path.join(bt._ROOT, "bot_state", "tug_log.csv")
WALL_LOG = os.path.join(bt._ROOT, "bot_state", "walls_log.csv")
KMONEY_FIXED = 1792766280          # 2026-10-23 14:38 UTC: the market tape was undercounting (BTC) and dropping pulls (both) before this fix


def _wall_score(bid_usd, bid_d, ask_usd, ask_d, near=0.3):
    b = bid_usd if (bid_usd and bid_d is not None and bid_d <= near) else 0.0
    a = ask_usd if (ask_usd and ask_d is not None and ask_d <= near) else 0.0
    return (b - a) / (b + a) if (b + a) > 0 else 0.0


def _load_live_logs():
    """{ticker: [(seconds_left, xflow, kmoney, liq), ...]} and {ticker: [(seconds_left, wall_score), ...]} from the 30s logs."""
    import csv as _csv
    feeds, walls = {}, {}
    fl = lambda x: float(x) if x not in ("", None) else None
    try:
        with open(LIVE_LOG, newline="", encoding="utf-8") as fh:
            for r in _csv.DictReader(fh):
                try:
                    ts = bt._ts(r["ts_utc"] + "Z")
                    km = fl(r.get("kalshi_money_up"))
                    if ts < KMONEY_FIXED:
                        km = None
                    feeds.setdefault(r["ticker"], []).append((int(r["seconds_left"]), fl(r.get("exchange_up")), km, fl(r.get("liquidation_up"))))
                except Exception:
                    continue
    except FileNotFoundError:
        pass
    try:
        with open(WALL_LOG, newline="", encoding="utf-8") as fh:
            for r in _csv.DictReader(fh):
                try:
                    walls.setdefault(r["ticker"], []).append((int(r["seconds_left"]), _wall_score(
                        fl(r["bid_wall_usd"]), fl(r["bid_wall_dist_pct"]), fl(r["ask_wall_usd"]), fl(r["ask_wall_dist_pct"]))))
                except Exception:
                    continue
    except FileNotFoundError:
        pass
    return feeds, walls


def _nearest(rows, left, tol=40):
    best = None
    for r in rows or ():
        if abs(r[0] - left) <= tol and (best is None or abs(r[0] - left) < abs(best[0] - left)):
            best = r
    return best


def live_feeds(t, tn, rsi, bw, coin):
    """Live: exchange flow, market money, liquidations, RSI and walls into the model inputs (same scale as the replay)."""
    ex = t.setdefault("_ex", {})
    tn = tn or {}
    if tn.get("ex_up") is not None:
        ex["xflow"] = tn["ex_up"] - 0.5
    if tn.get("k_up") is not None:
        ex["kmoney"] = tn["k_up"] - 0.5
    if tn.get("liq_up") is not None:
        ex["liq"] = tn["liq_up"] - 0.5
    if rsi is not None:
        ex["rsi"] = (rsi - 50) / 50
    try:
        b, a = (bw or {}).get("bid_wall"), (bw or {}).get("ask_wall")
        ex["walls"] = _wall_score(b[1] if b else None, b[2] if b else None, a[1] if a else None, a[2] if a else None)
    except Exception:
        ex["walls"] = 0.0
    ex["has_live"] = any(k in ex for k in ("xflow", "kmoney"))
    return t


def live_extras(t, win, crosses):
    """Adds the line-behavior / choppiness / 4-hour inputs for a live call (same definitions as the replay)."""
    ex = {"crosses": int(crosses or 0)}
    one = [list(c) for c in ((win or {}).get("1m") or [])]
    cl = [c[4] for c in one[-6:-1]][::-1] if len(one) >= 6 else []        # completed minutes, newest first
    ex["chop"] = (sum(abs(cl[i] / cl[i + 1] - 1) for i in range(len(cl) - 1)) * 1000) if len(cl) >= 3 else 0.0
    q = [list(c) for c in ((win or {}).get("15m") or [])]
    ex["r4h"] = ((q[-1][4] / q[-17][4] - 1) * 100) if len(q) >= 17 else 0.0
    t["_ex"] = ex
    return t


def m2_live(mark, kp, dist, t, early=None, coin="BTC"):
    """(side or None, p_up, note) from this coin's validated model for this call time, or None when it isn't live."""
    m = m2_model(coin).get(str(mark))
    if not m or not m.get("valid") or kp is None or dist is None or m.get("feats") != M2_FEATS:
        return None
    p = m2_p(m["w"], m2_x(kp, dist, t))
    side = "YES" if p >= 0.5 else "NO"
    conf = max(p, 1 - p)
    note = f"BRAIN v2 read {conf:.0%} {'UP' if side == 'YES' else 'DOWN'}"
    if mark == 480 and m.get("flip") is not None and early and early != side and conf < m["flip"]:
        return early, p, f"held the 4:00 side - the {'UP' if side == 'YES' else 'DOWN'} read ({conf:.0%}) isn't strong enough to flip it"
    if conf < (m.get("thr") or 0.5):
        return (None, p, f"{note} - not confident enough to call")
    return side, p, note


# ================================================================== MAJORITY (2026-10-24, user: "keep the 4:00, 6:00 and 8:00 and
# use a majority-rules approach"). The final (8:00) call = the side at least 2 of the 3 reads agree on. Scored on the same
# newest-30% rounds as everything else; the 8:00 read on its own is the bar to beat.
def _side_at(r, mark, m2):
    x = r["per"].get(mark)
    if not x:
        return None
    mm = m2.get(str(mark)) or {}
    if mm.get("valid") and mm.get("feats") == M2_FEATS:
        p = m2_p(mm["w"], m2_x(x["kp"], x["dist"], x["t"]))
        if max(p, 1 - p) < (mm.get("thr") or 0.5):
            return None
        return "YES" if p >= 0.5 else "NO"
    c = x["call"]                                       # today's rules (1-minute trend skip)
    if c and x["t"].get("1m") and (x["t"]["1m"] > 0) != (c == "YES"):
        return None
    return c


def majority_eval(rows, outcome, m2):
    R = [r for r in rows if 480 in r["per"]]
    sp = int(len(R) * 0.7)
    part = {"train": R[:sp], "unseen": R[sp:], "all": R}
    modes = {
        "8:00 alone": lambda e, m, s: s,
        "majority (no majority = no call)": lambda e, m, s: (
            "YES" if [e, m, s].count("YES") >= 2 else ("NO" if [e, m, s].count("NO") >= 2 else None)),
        "majority (no majority = 8:00 read)": lambda e, m, s: (
            "YES" if [e, m, s].count("YES") >= 2 else ("NO" if [e, m, s].count("NO") >= 2 else s)),
        "all 3 agree": lambda e, m, s: (s if (e and m and s and e == m == s) else None),
    }
    out = {}
    for name, fn in modes.items():
        o = {}
        for pn, P in part.items():
            g = []
            for r in P:
                side = fn(_side_at(r, 240, m2), _side_at(r, 360, m2), _side_at(r, 480, m2))
                if side:
                    g.append(outcome(r, 480, side))
            s_ = _summ(g)
            s_["cover"] = round(s_["n"] / len(P), 3) if P else 0
            o[pn] = s_
        out[name] = o
    base = out["8:00 alone"]
    pick = None
    for name in ("majority (no majority = no call)", "majority (no majority = 8:00 read)"):
        u = out[name]["unseen"]
        if u["n"] and base["unseen"]["n"] and u["win"] >= base["unseen"]["win"] and u["pnl"] >= base["unseen"]["pnl"]:
            if pick is None or (u["win"], u["pnl"]) > (out[pick]["unseen"]["win"], out[pick]["unseen"]["pnl"]):
                pick = name
    return {"modes": out, "pick": pick}


def majority_mode(coin="BTC"):
    """'sit' (no majority = no call), 'raw' (no majority = 8:00 read) or None (use the 8:00 read alone)."""
    pk = (load(coin).get("majority") or {}).get("pick")
    return {"majority (no majority = no call)": "sit", "majority (no majority = 8:00 read)": "raw"}.get(pk)


# ================================================================== 8:00 METHODS + WHEN TO SKIP (2026-10-24, user: "give me the best 8:00
# sealed method, the most profitable, and recommend times to skip - BTC and XRP"). Every 8:00 method side by side, then broken
# down by hour of day (ET, round start), the price paid and the line crosses at 8:00. Skip rules are picked on the older 70% of
# rounds (a bucket is skipped when it lost money there over 15+ calls) and checked on the newest 30%.
def _v2_side(r, mark, m2, force=False):
    x = r["per"].get(mark)
    mm = m2.get(str(mark)) or {}
    if not x or mm.get("feats") != M2_FEATS or not (mm.get("valid") or force):
        return None
    p = m2_p(mm["w"], m2_x(x["kp"], x["dist"], x["t"]))
    if max(p, 1 - p) < (mm.get("thr") or 0.5):
        return None
    return "YES" if p >= 0.5 else "NO"


def _old_side(r, mark):
    x = r["per"].get(mark)
    if not x:
        return None
    c = x["call"]
    if c and x["t"].get("1m") and (x["t"]["1m"] > 0) != (c == "YES"):
        return None
    return c


def sealed_report(rows, outcome, m2):
    import datetime as _dt
    from zoneinfo import ZoneInfo as _Z
    et = _Z("America/New_York")
    R = [r for r in rows if 480 in r["per"]]
    sp = int(len(R) * 0.7)
    maj = lambda e, m, s: "YES" if [e, m, s].count("YES") >= 2 else ("NO" if [e, m, s].count("NO") >= 2 else None)
    methods = {
        "8:00 old rules": lambda r: _old_side(r, 480),
        "8:00 new method": lambda r: _v2_side(r, 480, m2, force=True),
        "majority, no majority = no call": lambda r: maj(_side_at(r, 240, m2), _side_at(r, 360, m2), _side_at(r, 480, m2)),
        "majority, no majority = 8:00 read": lambda r: (maj(_side_at(r, 240, m2), _side_at(r, 360, m2), _side_at(r, 480, m2))
                                                        or _side_at(r, 480, m2)),
        "all 3 agree": lambda r: (lambda e, m, s: s if (e and m and s and e == m == s) else None)(
            _side_at(r, 240, m2), _side_at(r, 360, m2), _side_at(r, 480, m2)),
        "majority + new 8:00 must agree": lambda r: (lambda v, s: v if (v and s == v) else None)(
            maj(_side_at(r, 240, m2), _side_at(r, 360, m2), _side_at(r, 480, m2)), _v2_side(r, 480, m2, force=True)),
    }

    def dims(r, side):
        x = r["per"][480]
        kp = x["kp"] if side == "YES" else 1 - x["kp"]
        cr = int(((x["t"].get("_ex") or {}).get("crosses")) or 0)
        h = _dt.datetime.fromtimestamp(r["open"], et).hour
        pb = "under 60c" if kp < 0.60 else ("60-70c" if kp < 0.70 else ("70-80c" if kp < 0.80 else ("80-90c" if kp < 0.90 else "90c+")))
        return {"hour": h, "price": pb, "crosses": "3+" if cr >= 3 else str(cr)}

    out = {}
    for name, fn in methods.items():
        trades = []
        for i, r in enumerate(R):
            side = fn(r)
            if side:
                w, pl = outcome(r, 480, side)
                trades.append({"i": i, "w": w, "pl": pl, **dims(r, side)})
        tr = [t for t in trades if t["i"] < sp]
        un = [t for t in trades if t["i"] >= sp]
        S = lambda ts: _summ([(t["w"], t["pl"]) for t in ts])
        res = {"all": S(trades), "train": S(tr), "unseen": S(un), "cover_all": round(len(trades) / len(R), 3)}
        # skip buckets: the worst-losing buckets on the older rounds (20+ calls each), worst first, while at least 60% of the
        # calls are kept and at most 6 hours are skipped - then checked on the newest rounds
        skips = {"hour": [], "price": [], "crosses": []}
        cands = []
        for dim in skips:
            for v in {t[dim] for t in tr}:
                g = [t for t in tr if t[dim] == v]
                pl = sum(t["pl"] for t in g)
                if len(g) >= 20 and pl < 0:
                    cands.append((pl / len(g), dim, v))
        kept = list(tr)
        for _per, dim, v in sorted(cands):
            if dim == "hour" and len(skips["hour"]) >= 6:
                continue
            nxt = [t for t in kept if t[dim] != v]
            if len(nxt) < 0.6 * len(tr):
                continue
            skips[dim].append(v)
            kept = nxt
        keep = lambda t: not any(t[d] in skips[d] for d in skips)
        res["skips"] = {k: [str(x) for x in v] for k, v in skips.items()}
        res["with_skips"] = {"train": S([t for t in tr if keep(t)]), "unseen": S([t for t in un if keep(t)]),
                             "all": S([t for t in trades if keep(t)])}
        # full breakdowns (all 30 days) for the report
        res["by"] = {d: {str(v): S([t for t in trades if t[d] == v]) for v in sorted({t[d] for t in trades}, key=str)}
                     for d in ("hour", "price", "crosses")}
        out[name] = res
    return out


# ================================================================== GOOD BUY-INS (2026-10-24, user: "winning isn't the same as profitable - I want good buy-ins,
# not a bunch of skipped rounds, and a great profitable ratio"). A call is only worth buying when the model's chance of being right
# beats the price by a margin (edge = chance - price), and not when the price is so high that one miss wipes out ten wins (price cap).
# Margin + cap are picked on the older 70% of rounds while still buying at least 65% of the calls, then checked on the newest 30%.
def edge_report(rows, outcome, m2):
    R = [r for r in rows if 480 in r["per"]]
    sp = int(len(R) * 0.7)
    mm = m2.get("480") or {}
    if mm.get("feats") != M2_FEATS or not R:
        return {}
    maj = lambda e, m, s: "YES" if [e, m, s].count("YES") >= 2 else ("NO" if [e, m, s].count("NO") >= 2 else None)
    methods = {
        "8:00 new method": lambda r: _v2_side(r, 480, m2, force=True),
        "majority, no majority = no call": lambda r: maj(_side_at(r, 240, m2), _side_at(r, 360, m2), _side_at(r, 480, m2)),
        "majority + new 8:00 must agree": lambda r: (lambda v, s: v if (v and s == v) else None)(
            maj(_side_at(r, 240, m2), _side_at(r, 360, m2), _side_at(r, 480, m2)), _v2_side(r, 480, m2, force=True)),
    }
    out = {}
    for name, fn in methods.items():
        T = []
        for i, r in enumerate(R):
            side = fn(r)
            if not side:
                continue
            x = r["per"][480]
            p = m2_p(mm["w"], m2_x(x["kp"], x["dist"], x["t"]))
            pc = p if side == "YES" else 1 - p
            c = x["kp"] if side == "YES" else 1 - x["kp"]
            w, pl = outcome(r, 480, side)
            T.append({"i": i, "w": w, "pl": pl, "c": c, "edge": pc - c})
        tr = [t for t in T if t["i"] < sp]
        un = [t for t in T if t["i"] >= sp]
        S = lambda ts: _summ([(t["w"], t["pl"]) for t in ts])
        best = None
        for mg in (-0.03, -0.01, 0.0, 0.01, 0.02, 0.03, 0.05, 0.08, 0.12):
            for cap in (0.80, 0.85, 0.88, 0.91, 0.94, 0.97, 1.0):
                keep = [t for t in tr if t["edge"] >= mg and t["c"] <= cap]
                if len(keep) < 40 or len(keep) < 0.65 * len(tr):
                    continue
                s_ = S(keep)
                key = (s_["per"], s_["win"])
                if best is None or key > best[0]:
                    best = (key, mg, cap)
        res = {"all": S(T), "unseen": S(un), "cover_all": round(len(T) / len(R), 3)}
        if best:
            _k, mg, cap = best
            kp_ = lambda t: t["edge"] >= mg and t["c"] <= cap
            res.update({"margin": mg, "cap": cap, "train": S([t for t in tr if kp_(t)]),
                        "with_unseen": S([t for t in un if kp_(t)]), "with_all": S([t for t in T if kp_(t)]),
                        "cover_unseen": round(sum(1 for t in un if kp_(t)) / len(un), 3) if un else 0})
        out[name] = res
    return out


def _log_edge(coin, rep):
    for name, v in rep.items():
        if "margin" not in v:
            print(f"[buy-in] {coin} {name}: no margin/cap kept 65% of calls with 40+ trades")
            continue
        print(f"[buy-in] {coin} {name:<34} before: unseen {_f(v['unseen'])} | now margin>={v['margin']:+.2f} price<={v['cap']:.2f} "
              f"keeps {v['cover_unseen']:.0%} of calls -> unseen {_f(v['with_unseen'])} | all 30d {_f(v['with_all'])}")


# ================================================================== LABELS THAT MEAN SOMETHING (2026-10-24, user: "don't enter calls above 89 and don't enter on
# weak - factor in the confidence tiers weak / good / super and reprogram it to be more effective with better labeling").
# Tiers are cut on the model's own chance of being right (not the old blend), and the cut points are the ones that made the most
# money on the older 70% of rounds when buying only GOOD + SUPER calls priced 89c or lower. Checked on the newest 30%.
ENTRY_CAP = 0.89


def tier_report(rows, outcome, m2):
    R = [r for r in rows if 480 in r["per"]]
    sp = int(len(R) * 0.7)
    mm = m2.get("480") or {}
    if mm.get("feats") != M2_FEATS or not R:
        return {}
    maj = lambda e, m, s: "YES" if [e, m, s].count("YES") >= 2 else ("NO" if [e, m, s].count("NO") >= 2 else None)
    methods = {
        "8:00 new method": lambda r: _v2_side(r, 480, m2, force=True),
        "majority + new 8:00 must agree": lambda r: (lambda v, s: v if (v and s == v) else None)(
            maj(_side_at(r, 240, m2), _side_at(r, 360, m2), _side_at(r, 480, m2)), _v2_side(r, 480, m2, force=True)),
    }
    out = {}
    for name, fn in methods.items():
        T = []
        for i, r in enumerate(R):
            side = fn(r)
            if not side:
                continue
            x = r["per"][480]
            p = m2_p(mm["w"], m2_x(x["kp"], x["dist"], x["t"]))
            pc = p if side == "YES" else 1 - p
            c = x["kp"] if side == "YES" else 1 - x["kp"]
            w, pl = outcome(r, 480, side)
            T.append({"i": i, "w": w, "pl": pl, "c": c, "pc": pc})
        tr = [t for t in T if t["i"] < sp]
        un = [t for t in T if t["i"] >= sp]
        S = lambda ts: _summ([(t["w"], t["pl"]) for t in ts])
        best = None
        for g in (0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85):
            for s_ in (0.80, 0.85, 0.90, 0.93, 0.96):
                if s_ <= g:
                    continue
                enter = [t for t in tr if t["pc"] >= g and t["c"] <= ENTRY_CAP]
                if len(enter) < 40 or len(enter) < 0.4 * len(tr):
                    continue
                sm = S(enter)
                if best is None or (sm["per"], sm["win"]) > best[0]:
                    best = (( sm["per"], sm["win"]), g, s_)
        res = {"calls": len(T), "all_before": S(T), "unseen_before": S(un)}
        if best:
            _k, g, s_ = best
            tier = lambda t: "SUPER" if t["pc"] >= s_ else ("GOOD" if t["pc"] >= g else "WEAK")
            ent = lambda t: tier(t) != "WEAK" and t["c"] <= ENTRY_CAP
            res.update({"good_at": g, "super_at": s_, "cap": ENTRY_CAP,
                        "enter_unseen": S([t for t in un if ent(t)]), "enter_all": S([t for t in T if ent(t)]),
                        "enter_train": S([t for t in tr if ent(t)]),
                        "kept_unseen": round(sum(1 for t in un if ent(t)) / len(un), 3) if un else 0,
                        "by_tier_all": {k: S([t for t in T if tier(t) == k and t["c"] <= ENTRY_CAP]) for k in ("SUPER", "GOOD", "WEAK")},
                        "above_cap_all": S([t for t in T if t["c"] > ENTRY_CAP])})
        out[name] = res
    return out


def _log_tiers(coin, rep):
    for name, v in rep.items():
        if "good_at" not in v:
            print(f"[tiers] {coin} {name}: no tier cut kept 40% of calls with 40+ trades")
            continue
        print(f"[tiers] {coin} {name:<32} GOOD at >={v['good_at']:.0%}, SUPER at >={v['super_at']:.0%}, price <= {v['cap']:.0%}: "
              f"buy {v['kept_unseen']:.0%} of calls -> unseen {_f(v['enter_unseen'])} | all 30d {_f(v['enter_all'])}")
        print(f"[tiers] {coin} {name:<32} all 30d by tier (price<=89c): " + " | ".join(
            f"{k} {_f(s)}" for k, s in v["by_tier_all"].items()) + f" | over 89c (never bought) {_f(v['above_cap_all'])}")
        print(f"[tiers] {coin} {name:<32} before (every call, any price): unseen {_f(v['unseen_before'])} | all {_f(v['all_before'])}")


# ================================================================== ENTRY TIMING (2026-10-24, user: "fix that"). The calls are right ~86-91% of the time but the
# market already charges for it, so the fix is to PAY LESS: after the 8:00 call, rest a buy order d cents under the price at the call
# and only get filled if the market dips that far within the next W minutes (a miss = no trade). Fill price = the limit, never better.
# d + W + the 89c cap are picked on the older 70% of rounds and checked on the newest 30%; losers that dip first are counted honestly.
def dip_report(rows, outcome, m2):
    import backtest_engine as _bt
    R = [r for r in rows if 480 in r["per"]]
    sp = int(len(R) * 0.7)
    mm = m2.get("480") or {}
    if mm.get("feats") != M2_FEATS or not R:
        return {}
    maj = lambda e, m, s: "YES" if [e, m, s].count("YES") >= 2 else ("NO" if [e, m, s].count("NO") >= 2 else None)
    methods = {
        "8:00 new method": lambda r: _v2_side(r, 480, m2, force=True),
        "majority + new 8:00 must agree": lambda r: (lambda v, s: v if (v and s == v) else None)(
            maj(_side_at(r, 240, m2), _side_at(r, 360, m2), _side_at(r, 480, m2)), _v2_side(r, 480, m2, force=True)),
        "all 3 agree": lambda r: (lambda e, m_, s: s if (e and m_ and s and e == m_ == s) else None)(
            _side_at(r, 240, m2), _side_at(r, 360, m2), _side_at(r, 480, m2)),
    }
    out = {}
    for name, fn in methods.items():
        T = []
        for i, r in enumerate(R):
            side = fn(r)
            if not side:
                continue
            x = r["per"][480]
            c0 = x["kp"] if side == "YES" else 1 - x["kp"]
            T0 = r["open"] + 480
            low = {}                                   # minutes after the call -> cheapest the side's ask got that minute
            for e, v, b_, a_ in (r.get("kpath") or []):
                if T0 < e <= T0 + 6 * 60:
                    ask = (a_ if side == "YES" else (1 - b_ if b_ is not None else None))
                    if ask is not None and ask > 0:
                        low[int((e - T0 + 59) // 60)] = ask
            T.append({"i": i, "w": (side == "YES") == r["up"], "c0": c0, "low": low})
        tr = [t for t in T if t["i"] < sp]
        un = [t for t in T if t["i"] >= sp]

        def fills(ts, d, W, cap):
            g = []
            for t in ts:
                lim = min(cap, t["c0"] - d)
                if lim <= 0.05:
                    continue
                if any(m <= W and a <= lim for m, a in t["low"].items()):
                    g.append((t["w"], _bt.pnl(t["w"], lim)))
            return g
        base = lambda ts: _summ([(t["w"], _bt.pnl(t["w"], t["c0"])) for t in ts])
        best = None
        for d in (0.0, 0.02, 0.04, 0.06, 0.08, 0.10, 0.15):
            for W in (1, 2, 3, 4, 6):
                for cap in (0.89, 0.85, 0.80, 0.75):
                    g = fills(tr, d, W, cap)
                    if len(g) < 40 or len(g) < 0.2 * len(tr):
                        continue
                    s_ = _summ(g)
                    key = (s_["pnl"], s_["win"])
                    if best is None or key > best[0]:
                        best = (key, d, W, cap)
        res = {"calls": len(T), "now_unseen": base(un), "now_all": base(T)}
        if best:
            _k, d, W, cap = best
            res.update({"dip": d, "minutes": W, "cap": cap, "train": _summ(fills(tr, d, W, cap)),
                        "unseen": _summ(fills(un, d, W, cap)), "all": _summ(fills(T, d, W, cap)),
                        "fill_rate_unseen": round(len(fills(un, d, W, cap)) / len(un), 3) if un else 0})
        out[name] = res
    return out


def _log_dip(coin, rep):
    for name, v in rep.items():
        if "dip" not in v:
            print(f"[dip] {coin} {name}: no dip rule filled 20% of calls with 40+ trades")
            continue
        print(f"[dip] {coin} {name:<32} buy now: unseen {_f(v['now_unseen'])} | rule: limit {v['dip']*100:.0f}c under the call price, "
              f"{v['minutes']} min, cap {v['cap']:.0%}, filled {v['fill_rate_unseen']:.0%} -> unseen {_f(v['unseen'])} | all 30d {_f(v['all'])}")


def _log_sealed(coin, rep):
    print(f"[8:00 report] {coin} ===== every 8:00 method, newest 30% of rounds never used to pick | all 30 days")
    for name, v in rep.items():
        print(f"[8:00 report] {coin} {name:<34} unseen {_f(v['unseen'])} | all {_f(v['all'])} cover {v['cover_all']:.0%}")
    for name, v in rep.items():
        sk = v["skips"]
        print(f"[8:00 report] {coin} {name:<34} SKIP hours(ET) {sk['hour'] or '-'} | price {sk['price'] or '-'} | crosses {sk['crosses'] or '-'}"
              f" -> unseen {_f(v['with_skips']['unseen'])} | all {_f(v['with_skips']['all'])}")
    for best in (max(rep.items(), key=lambda kv: (kv[1]["unseen"]["win"] or 0)),
                 max(rep.items(), key=lambda kv: (kv[1]["unseen"]["pnl"] or -1e9))):
      for d in ("hour", "price", "crosses"):
        print(f"[8:00 report] {coin} {best[0]} by {d}: " + " | ".join(
            f"{k}: {s['win']:.0%} ${s['pnl']:+,.0f} n={s['n']}" for k, s in sorted(best[1]["by"][d].items(),
                                                                              key=lambda kv: (len(kv[0]), kv[0])) if s["n"]))
