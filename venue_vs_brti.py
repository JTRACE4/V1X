"""Which exchange (or blend of exchanges) tracks Kalshi's settlement index best?

Kalshi's 15-minute BTC / XRP markets settle on CF Benchmarks' real-time index (BRTI / XRP RTI): the simple average of the
60 seconds before the close.  Every settled market records that value (expiration_value) and the open reference
(floor_strike).  For the last N settled windows this pulls 1-minute candles from every exchange that serves history and
measures, per exchange and for several blends:
  * how far its price at the close is from the true settlement value (bps)
  * how often "price vs strike" predicts the actual YES/NO result
Read-only; writes data_cache/venue_vs_brti_<date>.json.  Run: python -m src.account_analysis.venue_vs_brti [N windows]
"""
import json
import os
_DATA_ROOT = os.environ.get("DATA_DIR") or os.path.dirname(os.path.abspath(__file__))   # Railway: point DATA_DIR at a volume
import sys
import time
import datetime as dt
import urllib.request

PUBLIC = "https://external-api.kalshi.com/trade-api/v2"
OUT = os.path.join(_DATA_ROOT, "data_cache")


def get(url, data=None, headers=None, tries=3):
    h = {"User-Agent": "kalshi-analysis"}
    h.update(headers or {})
    for i in range(tries):
        try:
            return json.loads(urllib.request.urlopen(urllib.request.Request(url, data=data, headers=h), timeout=20).read())
        except Exception:
            time.sleep(1 + i)
    return None


def settled(series, n):
    out, cursor = [], None
    while len(out) < n:
        j = get(f"{PUBLIC}/markets?series_ticker={series}&status=settled&limit=200" + (f"&cursor={cursor}" if cursor else ""))
        if not j or not j.get("markets"):
            break
        for m in j["markets"]:
            try:
                out.append({"close": int(dt.datetime.fromisoformat(m["close_time"].replace("Z", "+00:00")).timestamp()),
                            "exp": float(m["expiration_value"]), "strike": float(m["floor_strike"]), "res": m["result"]})
            except Exception:
                pass
        cursor = j.get("cursor")
        if not cursor:
            break
    out.sort(key=lambda x: x["close"])
    return out[-n:]


# every fetcher returns {minute_start_ts: (o, h, l, c, usd_volume)}
def f_coinbase(sym, t0, t1):
    out, t = {}, t0
    while t < t1:
        e = min(t + 300 * 60, t1)
        r = get(f"https://api.exchange.coinbase.com/products/{sym}-USD/candles?granularity=60&start={dt.datetime.utcfromtimestamp(t).isoformat()}Z&end={dt.datetime.utcfromtimestamp(e).isoformat()}Z")
        for ts, lo, hi, op, cl, v in (r or []):
            out[int(ts)] = (op, hi, lo, cl, v * cl)
        t = e; time.sleep(0.15)
    return out


def f_kraken(sym, t0, t1):
    pair = {"BTC": "XBTUSD", "XRP": "XRPUSD"}[sym]
    out, since = {}, t0
    while since < t1:
        r = get(f"https://api.kraken.com/0/public/OHLC?pair={pair}&interval=1&since={since}")
        if not r or r.get("error"):
            break
        rows = next(v for k, v in r["result"].items() if k != "last")
        if not rows:
            break
        for ts, o, h, l, c, vw, v, n in rows:
            out[int(ts)] = (float(o), float(h), float(l), float(c), float(v) * float(c))
        nxt = int(r["result"]["last"])
        if nxt <= since:
            break
        since = nxt; time.sleep(1.1)
    return out


def f_bitstamp(sym, t0, t1):
    out, t = {}, t0
    while t < t1:
        r = get(f"https://www.bitstamp.net/api/v2/ohlc/{sym.lower()}usd/?step=60&limit=1000&start={t}")
        rows = (r or {}).get("data", {}).get("ohlc", [])
        if not rows:
            break
        for x in rows:
            out[int(x["timestamp"])] = (float(x["open"]), float(x["high"]), float(x["low"]), float(x["close"]), float(x["volume"]) * float(x["close"]))
        t = int(rows[-1]["timestamp"]) + 60; time.sleep(0.3)
    return out


def f_binance(sym, t0, t1):
    out, t = {}, t0 * 1000
    while t < t1 * 1000:
        r = get(f"https://data-api.binance.vision/api/v3/klines?symbol={sym}USDT&interval=1m&startTime={t}&limit=1000")
        if not r:
            break
        for x in r:
            out[int(x[0]) // 1000] = (float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[7]))
        t = int(r[-1][0]) + 60000; time.sleep(0.2)
    return out


def f_bitfinex(sym, t0, t1):
    out, t = {}, t0 * 1000
    while t < t1 * 1000:
        r = get(f"https://api-pub.bitfinex.com/v2/candles/trade:1m:t{sym}USD/hist?start={t}&end={t1 * 1000}&limit=5000&sort=1")
        if not r:
            break
        for mts, o, c, h, l, v in r:
            out[int(mts) // 1000] = (o, h, l, c, v * c)
        t = int(r[-1][0]) + 60000; time.sleep(2.2)
    return out


def f_kucoin(sym, t0, t1):
    out, t = {}, t0
    while t < t1:
        e = min(t + 1400 * 60, t1)
        r = get(f"https://api.kucoin.com/api/v1/market/candles?type=1min&symbol={sym}-USDT&startAt={t}&endAt={e}")
        for ts, o, c, h, l, v, tv in ((r or {}).get("data") or []):
            out[int(ts)] = (float(o), float(h), float(l), float(c), float(tv))
        t = e; time.sleep(0.4)
    return out


def f_hyperliquid(sym, t0, t1):
    out, t = {}, t0 * 1000
    while t < t1 * 1000:
        body = json.dumps({"type": "candleSnapshot", "req": {"coin": sym, "interval": "1m", "startTime": t, "endTime": t1 * 1000}}).encode()
        r = get("https://api.hyperliquid.xyz/info", body, {"Content-Type": "application/json"})
        if not r:
            break
        for x in r:
            out[int(x["t"]) // 1000] = (float(x["o"]), float(x["h"]), float(x["l"]), float(x["c"]), float(x["v"]) * float(x["c"]))
        nt = int(r[-1]["t"]) + 60000
        if nt <= t:
            break
        t = nt; time.sleep(0.3)
    return out


def f_okx(sym, t0, t1):
    out, after = {}, t1 * 1000
    for _ in range(200):
        r = get(f"https://www.okx.com/api/v5/market/history-candles?instId={sym}-USDT&bar=1m&after={after}&limit=100")
        rows = (r or {}).get("data") or []
        if not rows:
            break
        for x in rows:
            out[int(x[0]) // 1000] = (float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[7]))
        after = int(rows[-1][0])
        if after // 1000 <= t0:
            break
        time.sleep(0.12)
    return out


FETCH = {"coinbase": f_coinbase, "kraken": f_kraken, "bitstamp": f_bitstamp, "binance": f_binance, "bitfinex": f_bitfinex,
         "kucoin": f_kucoin, "hyperliquid": f_hyperliquid, "okx": f_okx}
BRTI_LIKE = ["coinbase", "kraken", "bitstamp"]         # exchanges CF Benchmarks has published as constituents


def px(c, how):
    o, h, l, cl, _ = c
    return (o + cl) / 2 if how == "oc" else (o + h + l + cl) / 4


def main(n=500):
    stamp = dt.datetime.utcnow().strftime("%Y%m%d")
    result = {}
    for sym, series in (("BTC", "KXBTC15M"), ("XRP", "KXXRP15M")):
        wins = settled(series, n)
        if len(wins) < 50:
            print(sym, "not enough settled windows", len(wins)); continue
        t0, t1 = wins[0]["close"] - 1800, wins[-1]["close"] + 120
        print(f"\n===== {sym}: {len(wins)} settled windows, {dt.datetime.utcfromtimestamp(t0):%m-%d %H:%M} -> {dt.datetime.utcfromtimestamp(t1):%m-%d %H:%M} UTC")
        data = {}
        for v, fn in FETCH.items():
            try:
                data[v] = fn(sym, t0, t1)
            except Exception as e:
                data[v] = {}
            print(f"  fetched {v:12s} {len(data[v]):6d} minutes")
        rows = {}
        for how in ("oc", "ohlc4"):
            def price_at(venue, close):                      # average of the minute that ends at the close
                c = data[venue].get(close - 60)
                return px(c, how) if c else None

            def blend(venues, close):
                num = den = 0.0
                for v in venues:
                    c = data[v].get(close - 60)
                    if c and c[4] > 0:
                        num += px(c, how) * c[4]; den += c[4]
                return (num / den) if den > 0 else None

            sets = {v: [v] for v in FETCH}
            sets["blend: coinbase+kraken (what the dashboard uses now)"] = ["coinbase", "kraken"]
            sets["blend: coinbase+kraken+bitstamp"] = BRTI_LIKE
            sets["blend: all spot (no perps)"] = ["coinbase", "kraken", "bitstamp", "binance", "bitfinex", "kucoin", "okx"]
            sets["blend: everything incl. hyperliquid"] = list(FETCH)
            for name, vs in sets.items():
                errs, agree, tot = [], 0, 0
                for w in wins:
                    p = price_at(name, w["close"]) if name in FETCH else blend(vs, w["close"])
                    if p is None:
                        continue
                    errs.append(abs(p - w["exp"]) / w["exp"] * 1e4)
                    tot += 1
                    agree += ((p >= w["strike"]) == (w["res"] == "yes"))
                if tot >= 30:
                    errs.sort()
                    rows[(how, name)] = {"n": tot, "mae_bps": sum(errs) / tot, "median_bps": errs[tot // 2],
                                         "p90_bps": errs[int(tot * 0.9)], "agree_pct": 100 * agree / tot}
        for how in ("oc", "ohlc4"):
            print(f"\n  -- {sym}, minute price = {how} --   (error vs the TRUE settlement value; agree = price-vs-strike matches YES/NO)")
            for (h_, name), r in sorted(((k, v) for k, v in rows.items() if k[0] == how), key=lambda kv: kv[1]["mae_bps"]):
                print(f"    {name:55s} n={r['n']:4d}  mean err {r['mae_bps']:5.2f} bps  median {r['median_bps']:5.2f}  p90 {r['p90_bps']:5.2f}  agree {r['agree_pct']:5.1f}%")
        result[sym] = {f"{h}|{n_}": r for (h, n_), r in rows.items()}
    try:
        with open(os.path.join(OUT, f"venue_vs_brti_{stamp}.json"), "w") as f:
            json.dump(result, f, indent=1)
    except Exception:
        pass


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 500)
