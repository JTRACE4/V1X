"""RSI cross-check (2026-10-20): computes RSI(14) the way TradingView does it and the way Webull's help page describes it,
on the same Coinbase BTC-USD / XRP-USD candles you'd load on either chart, so the number on BRAIN can be checked by eye.

Why BRAIN's old number could disagree with your chart:
  * it skipped the candle that is still forming (TradingView and Webull both include it live), so it lagged up to 60s
  * the 1-minute RSI only had ~60 candles of warm-up and the 5-minute RSI only ~20-40, so Wilder's smoothing had not settled
  * it was computed on an all-exchange composite, not on one exchange's price like a chart

Methods (both 14 periods, close-to-close changes):
  TradingView  - Wilder's RSI: ta.rsi = rma(gains)/rma(losses), rma seeded with a simple average of the first 14 changes,
                 then avg = (prev * 13 + new) / 14. Uses ~300 candles so the seed has no effect left (13/14 ** 286 ~ 0).
  Webull-style - Webull's help page describes plain averages of the up and down closes over the last 14 bars (no carry-
                 over smoothing). Webull does not publish more detail than that, so this is labelled "-style".
Read-only.  Never touches orders.
"""
import json
import threading
import time
import urllib.request

PERIOD = 14
POLL_SECONDS = 15
PRODUCTS = {"BTC": "BTC-USD", "XRP": "XRP-USD"}

_lock = threading.Lock()
_cache = {}          # asset -> {"c1": [(ts, close)], "c5": [(ts, close)], "fetched": ts}
_started = False


def rsi_wilder(closes, period=PERIOD):
    """TradingView ta.rsi(close, 14)."""
    if not closes or len(closes) <= period:
        return None
    ag = sum(max(closes[i] - closes[i - 1], 0.0) for i in range(1, period + 1)) / period
    al = sum(max(closes[i - 1] - closes[i], 0.0) for i in range(1, period + 1)) / period
    for i in range(period + 1, len(closes)):
        ch = closes[i] - closes[i - 1]
        ag = (ag * (period - 1) + max(ch, 0.0)) / period
        al = (al * (period - 1) + max(-ch, 0.0)) / period
    if al == 0:
        return 100.0 if ag > 0 else 50.0
    return 100.0 - 100.0 / (1.0 + ag / al)


def rsi_simple(closes, period=PERIOD):
    """Plain 14-bar average of up closes vs down closes (Webull help-page description)."""
    if not closes or len(closes) <= period:
        return None
    w = closes[-(period + 1):]
    ag = sum(max(w[i] - w[i - 1], 0.0) for i in range(1, len(w))) / period
    al = sum(max(w[i - 1] - w[i], 0.0) for i in range(1, len(w))) / period
    if al == 0:
        return 100.0 if ag > 0 else 50.0
    return 100.0 - 100.0 / (1.0 + ag / al)


def _fetch(product, gran):
    url = f"https://api.exchange.coinbase.com/products/{product}/candles?granularity={gran}"
    req = urllib.request.Request(url, headers={"User-Agent": "brain-rsi-check"})
    rows = json.loads(urllib.request.urlopen(req, timeout=10).read())
    # [time, low, high, open, close, volume], newest first, includes the candle still forming
    return sorted((int(r[0]), float(r[4])) for r in rows)


def _loop():
    while True:
        for asset, product in PRODUCTS.items():
            try:
                c1 = _fetch(product, 60)
                c5 = _fetch(product, 300)
                with _lock:
                    _cache[asset] = {"c1": c1, "c5": c5, "fetched": time.time()}
            except Exception:
                pass
            time.sleep(0.4)
        time.sleep(POLL_SECONDS)


def start():
    global _started
    if _started:
        return
    _started = True
    threading.Thread(target=_loop, daemon=True, name="rsi-check").start()


def _with_live(series, gran, live_price, now):
    """Closes with the forming candle's close set to the live price (what a chart shows mid-candle)."""
    closes = [c for _, c in series]
    if not closes or not live_price:
        return closes
    cur = int(now) // gran * gran
    if series[-1][0] == cur:
        closes[-1] = float(live_price)
    elif series[-1][0] < cur:
        closes.append(float(live_price))       # candle for this minute not published yet
    return closes


def read(asset, live_price=None, composite_rsi1=None):
    """All the versions side by side plus which one BRAIN shows. None when Coinbase candles are not in yet / stale."""
    with _lock:
        c = _cache.get(asset)
    if not c or time.time() - c["fetched"] > 120:
        return None
    now = time.time()
    k1 = _with_live(c["c1"], 60, live_price, now)
    k5 = _with_live(c["c5"], 300, live_price, now)
    tv1, tv5 = rsi_wilder(k1), rsi_wilder(k5)
    wb1, wb5 = rsi_simple(k1), rsi_simple(k5)
    tv1_prev = rsi_wilder(k1[:-3]) if len(k1) > 30 else None
    if tv1 is None:
        return None
    gap_wb = abs(tv1 - wb1) if wb1 is not None else None
    gap_all = abs(tv1 - composite_rsi1) if composite_rsi1 is not None else None
    return {
        "tv1": tv1, "tv5": tv5, "wb1": wb1, "wb5": wb5, "tv1_prev": tv1_prev, "all1": composite_rsi1,
        "gap_wb": gap_wb, "gap_all": gap_all, "bars1": len(k1), "bars5": len(k5),
        "pick": "tv",
        "pick_why": ("TradingView's version is Wilder's standard RSI with a full warm-up - the textbook definition, and it "
                     "is steadier. The Webull-style simple average jumps more on single candles."),
        "agree": gap_wb is not None and gap_wb < 5,
        "source": f"Index venue 1 {PRODUCTS[asset]}",
    }
