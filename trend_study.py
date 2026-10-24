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
FILE = os.path.join(bt.CACHE, "trend_study.json")
_state = {"res": None, "ts": 0.0}


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


def run():
    tr = bt._fn.get("trend_read")
    if not tr:
        print("[trend study] trend_read not handed over yet")
        return None
    markets = [m for m in bt._load("markets.json", []) if m.get("result") in ("yes", "no")]
    kcache = bt._load("kalshi_paths.json", {})
    cb = {int(k): v for k, v in bt._load("coinbase_1m.json", {}).items()}
    bn = {int(k): v for k, v in bt._load("binance_1m.json", {}).items()}
    if len(markets) < 200 or not cb:
        print(f"[trend study] not enough cached data ({len(markets)} rounds)")
        return None
    rs = {sec: _resample(cb, sec) for sec in (300, 900, 3600, 86400)}
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
            per[mark] = {"kp": f["kp"], "call": call, "fav": fav, "t": t, "dist": f["dist"]}
        if per:
            rows.append({"up": up, "ticker": m["ticker"], "open": m["open"], "per": per})
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
    os.makedirs(os.path.dirname(FILE), exist_ok=True)
    with open(FILE + ".tmp", "w") as fh:
        json.dump(res, fh)
    os.replace(FILE + ".tmp", FILE)
    _state["res"], _state["ts"] = res, time.time()
    _log(res)
    return res


def _f(s):
    if not s or not s.get("n"):
        return "n=0"
    return f"n={s['n']} win={s['win']:.1%} ${s['pnl']:+,.0f} ({s['per']:+.1f}/call) cover={s.get('cover', 0):.0%}"


def _log(res):
    print(f"[trend study] {res['rounds']} BTC rounds replayed, newest {res['unseen']} never used to pick")
    for mark, mk in res["marks"].items():
        lab = {"240": "4:00", "360": "6:00", "480": "8:00"}[mark]
        acc = " | ".join(f"{k} {v['unseen']['win']:.0%}/{v['unseen']['cover']:.0%}" for k, v in mk["trend_accuracy"].items()
                         if v["unseen"]["win"] is not None)
        print(f"[trend study] {lab} trend read -> round result (unseen win / how often it has a side): {acc}")
        S = mk["strategies"]
        top = sorted(((k, v) for k, v in S.items() if v["unseen"]["n"] >= 60 and v["unseen"]["cover"] >= 0.5),
                     key=lambda kv: -((kv[1]["unseen"]["win"] or 0) + (0.0 if (kv[1]["unseen"]["per"] or 0) > 0 else -1)))[:8]
        for k in ("current (1m skip)", "call, no trend", "market favorite"):
            print(f"[trend study] {lab} {k:<22} unseen {_f(S[k]['unseen'])} | all {_f(S[k]['all'])}")
        for k, v in top:
            print(f"[trend study] {lab} TOP {k:<18} unseen {_f(v['unseen'])} | all {_f(v['all'])}")
        if mk.get("disagree"):
            d_ = mk["disagree"]
            print(f"[trend study] 8:00 vs 4:00: the calls disagreed in {d_['rate']:.0%} of rounds ({d_['n']}); when they did, the sealed side was right {d_['sealed_right']:.0%}")
        p = res["pick"][mark]
        print(f"[trend study] {lab} PICK: {p['rule'] or 'none beat the current rule on win rate AND profit - kept'}"
              + (f" | unseen {_f(p['stats']['unseen'])} vs current {_f(p['current']['unseen'])}" if p['rule'] else ""))


def load():
    if _state["res"] is None:
        try:
            with open(FILE) as fh:
                _state["res"] = json.load(fh)
        except Exception:
            _state["res"] = {}
    return _state["res"] or {}


def decisions():
    """{"240": rule or None, "360": ..., "480": ...} - the picked trend rule per call time."""
    return {k: v.get("rule") for k, v in (load().get("pick") or {}).items()}


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
