"""Flip + stay-out audit (added 2026-10-23, user: "do a back test to find out why it's not catching the flips ... and
whether the stay-out has been saving money or we've been skipping out on money").

Runs inside the dashboard process a few minutes after start (and once a day), from data already on the server:
  * the 30-day BTC backtest replay (backtest_engine.cached_rounds - Kalshi prices, Coinbase candles, Binance flow)
  * the live graded rounds (BTC + XRP) with what each early / sealed call actually said, including sit-outs

Money is always "per $1 staked" buying the side at the market's own price at that minute + 1c slippage + taker fee
(backtest_engine.pnl), so a high win rate on expensive favorites can't hide a loss. Results go to the server log as
"[audit] ..." lines and to DATA_DIR/data_cache/backtest/audit.txt. Information only - it never trades.
"""
import itertools
import os
import time

import backtest_engine as bt

HOLD = 0.30


def _money(rows):
    """rows: [(win, price)] -> (n, win rate, avg profit per $1, total units)"""
    n = len(rows)
    if not n:
        return 0, None, None, 0.0
    w = sum(1 for x, _p in rows if x)
    tot = sum(bt.pnl(x, p) for x, p in rows)
    return n, w / n, tot / n, tot


def _fmt(label, rows):
    n, wr, roi, tot = _money(rows)
    if not n:
        return f"{label}: none"
    return f"{label}: {n} rounds, won {wr:.0%}, {roi * 100:+.1f}c per $1 ({tot:+.1f} units)"


def _split(rounds):
    k = max(1, int(len(rounds) * HOLD))
    return rounds[:-k], rounds[-k:]


# ------------------------------------------------------------------------------------------------ stay-out (backtest)
def stayout_backtest(rounds, out):
    for mark, name in ((240, "EARLY 4:00"), (480, "SEALED 8:00")):
        against, flip50 = {"call": [], "trend": []}, {"fav": [], "trend": []}
        rows_called = []
        for r in rounds:
            f = r["f"].get(mark)
            if not f:
                continue
            res_yes = r["m"]["result"] == "yes"
            call, _tier, p = bt.stage_call(f)
            tr = (f.get("sig") or {}).get("trend") or 0
            if call:
                win = (call == "YES") == res_yes
                rows_called.append((win, bt.price_of(call == "YES", f["kp"])))
                if tr and (tr > 0) != (call == "YES"):
                    against["call"].append((win, bt.price_of(call == "YES", f["kp"])))
                    t_yes = tr > 0
                    against["trend"].append((t_yes == res_yes, bt.price_of(t_yes, f["kp"])))
            else:
                fav_yes = f["kp"] >= 0.5
                flip50["fav"].append((fav_yes == res_yes, bt.price_of(fav_yes, f["kp"])))
                if tr:
                    flip50["trend"].append(((tr > 0) == res_yes, bt.price_of(tr > 0, f["kp"])))
        out.append(f"== STAY-OUT check, backtest {name} (30 days BTC) ==")
        out.append("  " + _fmt("all calls the rules make", rows_called))
        out.append("  " + _fmt("calls AGAINST the trend (live sits these out) - if taken anyway", against["call"]))
        out.append("  " + _fmt("   ...same rounds, trend side instead", against["trend"]))
        out.append("  " + _fmt("coin-flip skips - market favorite instead", flip50["fav"]))
        out.append("  " + _fmt("coin-flip skips - trend side instead", flip50["trend"]))


# ------------------------------------------------------------------------------------------------ stay-out (live)
def stayout_live(live_rounds, out):
    out.append("== STAY-OUT check, LIVE graded rounds ==")
    for asset, rs in (live_rounds or {}).items():
        for sk in ("early", "sealed"):
            sit, flip, called = [], [], []
            for r in rs:
                c = (r.get("stage_calls") or {}).get(sk) or {}
                act = r.get("actual")
                ky = c.get("kalshi_yes")
                if act not in ("YES", "NO") or ky is None:
                    continue
                if c.get("call"):
                    called.append((c["call"] == act, bt.price_of(c["call"] == "YES", ky)))
                elif c.get("sitout") and c.get("lean"):
                    sit.append((c["lean"] == act, bt.price_of(c["lean"] == "YES", ky)))
                elif c.get("skipped"):
                    fav = "YES" if ky >= 0.5 else "NO"
                    flip.append((fav == act, bt.price_of(fav == "YES", ky)))
            out.append(f"  {asset} {sk}: " + _fmt("calls made", called))
            out.append(f"  {asset} {sk}: " + _fmt("SAT OUT (against trend) - if the lean was taken", sit))
            out.append(f"  {asset} {sk}: " + _fmt("coin-flip skips - if the favorite was taken", flip))


# ------------------------------------------------------------------------------------------------ flips
def _feat(f, mark):
    fav = 1 if f["kp"] >= 0.5 else -1
    sc, opp, toward = bt.flip_score(f, fav, mark)
    v, rsi_st = bt.rev_votes(f, fav)
    return {"fav": fav, "dog": bt.price_of(fav < 0, f["kp"]), "ad": abs(f["dist"]), "cx": f.get("crosses") or 0,
            "votes": v, "rsi": rsi_st, "score": sc, "opp": opp or 0.5, "toward": bool(toward),
            "wrong": (f["dist"] * fav) < 0}


CONDS = {
    "dog": [(0.15, 0.30), (0.30, 0.40), (0.40, 0.50), (0.20, 0.50)],
    "ad": [0.0002, 0.0004, 0.0008, 1.0],
    "cx": [0, 1, 2, 3],
    "votes": [0, 2, 3],
    "score": [0, 45],
    "toward": [False, True],
    "wrong": [False, True],
}


def _match(x, rule):
    lo, hi = rule["dog"]
    return (lo <= x["dog"] < hi and x["ad"] <= rule["ad"] and x["cx"] >= rule["cx"] and x["votes"] >= rule["votes"]
            and x["score"] >= rule["score"] and (x["toward"] or not rule["toward"]) and (x["wrong"] or not rule["wrong"]))


def flips(rounds, out, live_tables=None):
    for mark, name in ((240, "EARLY 4:00"), (480, "SEALED 8:00")):
        rows = []
        for r in rounds:
            f = r["f"].get(mark)
            if not f or f.get("kp") is None:
                continue
            x = _feat(f, mark)
            x["flip"] = (r["m"]["result"] == "yes") != (x["fav"] > 0)     # the favorite at the mark lost
            x["f"] = f
            rows.append(x)
        if not rows:
            continue
        out.append(f"== FLIPS at {name} (30 days BTC, {len(rows)} rounds) ==")
        nf = sum(x["flip"] for x in rows)
        out.append(f"  the favorite lost {nf} times ({nf / len(rows):.0%})")
        for lo, hi in ((0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.01)):
            g = [x for x in rows if lo <= 1 - x["dog"] < hi]
            if g:
                k = sum(x["flip"] for x in g)
                out.append(f"  favorite at {int(lo * 100)}-{int(min(hi, 1) * 100)}c: {len(g)} rounds, flipped {k} ({k / len(g):.0%})"
                           f" - underdog costs {sum(x['dog'] for x in g) / len(g):.2f} on average")
        # what flips looked like vs rounds that held
        fl, hd = [x for x in rows if x["flip"]], [x for x in rows if not x["flip"]]
        def avg(g, k):
            return sum(float(x[k]) for x in g) / len(g) if g else 0
        out.append("  flipped vs held (average): "
                   + ", ".join(f"{k} {avg(fl, k):.3g} vs {avg(hd, k):.3g}" for k in ("dog", "ad", "cx", "votes", "score", "opp", "toward", "wrong")))
        # the current flip-history reversal: built on the older 70%, scored on the newest 30% it never saw
        tr_r, ho_r = _split(rounds)
        tab = bt.build_flip_table(tr_r, mark)
        fired, missed = [], 0
        for r in ho_r:
            f = r["f"].get(mark)
            if not f or f.get("kp") is None:
                continue
            fc = bt.flip_call(tab, f)
            res_yes = r["m"]["result"] == "yes"
            fav_yes = f["kp"] >= 0.5
            if fc:
                fired.append(((fc["call"] == "YES") == res_yes, bt.price_of(fc["call"] == "YES", f["kp"])))
            elif res_yes != fav_yes:
                missed += 1
        out.append("  current reversal (flip history), newest 30%: " + _fmt("fired", fired) + f"; flips it did not call: {missed}")
        # rule search: train on the older 70%, keep rules that also make money on the newest 30%
        k = max(1, int(len(rows) * HOLD))

        def search(rs, label="flip"):
            tr, ho = rs[:-k], rs[-k:]
            res = []
            keys = list(CONDS)
            for combo in itertools.product(*(CONDS[c] for c in keys)):
                rule = dict(zip(keys, combo))
                a = [x for x in tr if _match(x, rule)]
                if len(a) < 50:
                    continue
                ta = _money([(x[label], x["dog"]) for x in a])
                if ta[2] is None or ta[2] < 0.05:
                    continue
                b = [x for x in ho if _match(x, rule)]
                if len(b) < 25:
                    continue
                hb = _money([(x[label], x["dog"]) for x in b])
                if hb[2] is not None and hb[2] > 0:
                    res.append((hb[2], rule, ta, hb))
            res.sort(key=lambda z: -z[0])
            return res
        found = search(rows)
        # control: the same search on shuffled outcomes (each round keeps its own odds, so cheap underdogs still win less).
        # If real data finds about as many "money rules" as shuffled data, those rules are luck, not a real flip signal.
        import random as _r
        rng = _r.Random(7)
        ctrl = []
        for _ in range(3):
            for x in rows:
                x["fake"] = rng.random() < x["dog"]
            ctrl.append(len(search(rows, "fake")))
        out.append(f"  luck check: shuffled outcomes find {sum(ctrl) / len(ctrl):.0f} money rules on average vs {len(found)} on the real data")
        out.append(f"  underdog rules that made money on BOTH the older 70% and the newest 30% ({len(found)} found, best 8):")
        for roi, rule, ta, hb in found[:8]:
            out.append(f"    dog {rule['dog'][0]:.2f}-{rule['dog'][1]:.2f}, |dist|<={rule['ad']}, crosses>={rule['cx']}, "
                       f"reads against>={rule['votes']}, radar>={rule['score']}{', moving at the line' if rule['toward'] else ''}"
                       f"{', already on the other side' if rule['wrong'] else ''} -> train {ta[0]} won {ta[1]:.0%} {ta[2] * 100:+.1f}c | "
                       f"unseen {hb[0]} won {hb[1]:.0%} {hb[2] * 100:+.1f}c")


# ------------------------------------------------------------------------------------------------ candidate fixes
def _cell(f):
    """Flip-history cell for the FAVORITE at a mark: favorite price band x distance to the line x crosses so far."""
    fav_yes = f["kp"] >= 0.5
    fp = bt.price_of(fav_yes, f["kp"])
    b = 0 if fp < 0.6 else 1 if fp < 0.7 else 2 if fp < 0.8 else 3 if fp < 0.9 else 4
    ad = abs(f["dist"])
    d = 0 if ad <= 0.0002 else 1 if ad <= 0.0005 else 2 if ad <= 0.001 else 3
    wrong = (f["dist"] > 0) != fav_yes and ad > 0.00003
    c = min(2, int(f.get("crosses") or 0))
    return f"{b}{d}{c}{int(wrong)}", fav_yes, fp


def fixes(rounds, out):
    tr_r, ho_r = _split(rounds)
    out.append("== CANDIDATE FIXES (built on the older 70%, scored ONLY on the newest 30% they never saw) ==")
    for mark, name in ((240, "EARLY"), (480, "SEALED")):
        # flip-history table for the favorite
        tab = {}
        for r in tr_r:
            f = r["f"].get(mark)
            if not f or f.get("kp") is None:
                continue
            key, fav_yes, fp = _cell(f)
            c = tab.setdefault(key, [0, 0, 0.0])
            c[0] += 1
            c[1] += int((r["m"]["result"] == "yes") != fav_yes)
            c[2] += fp
        def flip_rate(f):
            key, fav_yes, fp = _cell(f)
            c = tab.get(key)
            if not c or c[0] < 15:
                return None, fp, fav_yes
            return (c[1] + 4 * (1 - fp)) / (c[0] + 4), fp, fav_yes      # pulled toward the market's own price
        # (a) skip calls on the favorite when history says it flips 5+ points more often than its price allows
        base, kept, skipped = [], [], []
        brier_m = brier_t = 0.0; nb = 0
        for r in ho_r:
            f = r["f"].get(mark)
            if not f or f.get("kp") is None:
                continue
            call, _t, _p = bt.stage_call(f)
            res_yes = r["m"]["result"] == "yes"
            fr, fp, fav_yes = flip_rate(f)
            if fr is not None:
                flipped = res_yes != fav_yes
                brier_m += ((1 - fp) - flipped) ** 2; brier_t += (fr - flipped) ** 2; nb += 1
            if not call:
                continue
            row = (((call == "YES") == res_yes), bt.price_of(call == "YES", f["kp"]))
            base.append(row)
            on_fav = (call == "YES") == fav_yes
            if on_fav and fr is not None and fr > (1 - fp) + 0.05:
                skipped.append(row)
            else:
                kept.append(row)
        out.append(f"  {name}: " + _fmt("calls as now", base))
        out.append(f"  {name}: " + _fmt("calls kept if we skip favorites the flip history marks risky", kept))
        out.append(f"  {name}: " + _fmt("   ...the calls that would be skipped", skipped))
        if nb:
            out.append(f"  {name}: flip prediction error (lower = better): market price {brier_m / nb:.4f} vs flip history {brier_t / nb:.4f} ({nb} rounds)")
        # (b) against-trend: sit out vs take the trend side vs take the call
        sit = {"call": [], "trend": []}
        for r in ho_r:
            f = r["f"].get(mark)
            if not f:
                continue
            call, _t, _p = bt.stage_call(f)
            tr = (f.get("sig") or {}).get("trend") or 0
            res_yes = r["m"]["result"] == "yes"
            if call and tr and (tr > 0) != (call == "YES"):
                sit["call"].append(((call == "YES") == res_yes, bt.price_of(call == "YES", f["kp"])))
                sit["trend"].append(((tr > 0) == res_yes, bt.price_of(tr > 0, f["kp"])))
        out.append(f"  {name} against-trend, unseen rounds: " + _fmt("take the call", sit["call"]) + " | " + _fmt("take the trend side", sit["trend"]))
        # (c) coin-flip skips: trend side
        cf = []
        for r in ho_r:
            f = r["f"].get(mark)
            if not f:
                continue
            call, _t, _p = bt.stage_call(f)
            tr = (f.get("sig") or {}).get("trend") or 0
            if not call and tr:
                cf.append(((tr > 0) == (r["m"]["result"] == "yes"), bt.price_of(tr > 0, f["kp"])))
        out.append(f"  {name} coin-flip skips, unseen rounds: " + _fmt("take the trend side", cf))


def run(live_rounds=None):
    out = [f"BRAIN audit {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}"]
    try:
        rounds = bt.cached_rounds()
    except Exception as e:
        rounds = []
        out.append(f"backtest data not readable: {e!r}")
    out.append(f"backtest rounds available: {len(rounds)}")
    for fn, args in ((stayout_backtest, (rounds, out)), (stayout_live, (live_rounds, out)), (flips, (rounds, out)), (fixes, (rounds, out))):
        try:
            if fn is stayout_live or rounds:
                fn(*args)
        except Exception as e:
            out.append(f"{fn.__name__} failed: {e!r}")
    txt = "\n".join(out)
    try:
        os.makedirs(bt.CACHE, exist_ok=True)
        with open(os.path.join(bt.CACHE, "audit.txt"), "w") as f_:
            f_.write(txt)
    except Exception:
        pass
    for ln in out:
        print("[audit] " + ln)
    return txt
