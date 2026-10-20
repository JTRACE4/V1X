"""Free, no-login data for the welcome page (added 2026-10-20): candles, live price vs the Kalshi line, 24h stats, crypto
headlines, Fear & Greed, and Philadelphia weather. Everything is cached server-side so visitors never hammer the sources,
and nothing here exposes the dashboard's calls."""
import html
import re
import threading
import time
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import requests

HEADERS = {"User-Agent": "brain-dashboard/1.0"}
PRODUCTS = {"BTC": "BTC-USD", "XRP": "XRP-USD"}
_cache = {}
_lock = threading.Lock()
_fn = {}            # get_state(name) -> dashboard state dict, get_ticks(symbol) -> [(ts, price)]


def configure(**kw):
    _fn.update(kw)


def _cached(key, ttl, fn):
    now = time.time()
    with _lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < ttl:
            return hit[1]
    try:
        val = fn()
    except Exception as e:
        print(f"[public] {key}: {e!r}")
        return hit[1] if hit else None            # stale beats nothing
    with _lock:
        _cache[key] = (now, val)
    return val


def _get(url, params=None, timeout=12):
    r = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r


# ------------------------------------------------------------------------------------------------ prices
TF = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "1d": 86400}


def candles(asset, tf):
    prod = PRODUCTS.get(asset)
    g = TF.get(tf)
    if not prod or not g:
        return []

    def go():
        rows = _get(f"https://api.exchange.coinbase.com/products/{prod}/candles", {"granularity": g}).json()
        return sorted([[int(r[0]), float(r[3]), float(r[2]), float(r[1]), float(r[4])] for r in rows])[-300:]
    return _cached(f"c:{asset}:{tf}", 15 if g <= 60 else 60, go) or []


def stats24(asset):
    prod = PRODUCTS.get(asset)
    if not prod:
        return {}

    def go():
        j = _get(f"https://api.exchange.coinbase.com/products/{prod}/stats").json()
        o, last = float(j["open"]), float(j["last"])
        return {"open": o, "high": float(j["high"]), "low": float(j["low"]), "vol": float(j["volume"]),
                "chg": (last / o - 1) * 100 if o else None, "last": last}
    return _cached(f"s:{asset}", 30, go) or {}


def ticker(asset):
    """Live price, the current Kalshi line and countdown, a rolling 60s average - no calls."""
    st = _fn.get("get_state", lambda n: {})(asset) or {}
    sym = PRODUCTS.get(asset)
    ticks = _fn.get("get_ticks", lambda s: [])(sym) if sym else []
    now = time.time()
    price = ticks[-1][1] if ticks and now - ticks[-1][0] < 60 else st.get("spot_price")
    secs, last = [], None
    i = 0
    for sec in range(int(now) - 59, int(now) + 1):
        while i < len(ticks) and ticks[i][0] <= sec:
            last = ticks[i][1]
            i += 1
        if last is not None:
            secs.append(last)
    s24 = stats24(asset)
    if price is None:
        price = s24.get("last")
    return {"asset": asset, "price": price, "line": st.get("target_price") if "error" not in st else None,
            "seconds_left": st.get("seconds_left"), "round": st.get("ticker"),
            "avg60": sum(secs) / len(secs) if secs else None, "chg24": s24.get("chg"), "high24": s24.get("high"),
            "low24": s24.get("low"), "vol24": s24.get("vol"), "ts": now}


def round_ticks(asset, seconds=900):
    sym = PRODUCTS.get(asset)
    ticks = _fn.get("get_ticks", lambda s: [])(sym) if sym else []
    now = time.time()
    out, last_s = [], None
    for t, p in ticks:
        if now - t > seconds:
            continue
        s = int(t)
        if s == last_s:
            out[-1] = [s, round(p, 6)]
        else:
            out.append([s, round(p, 6)])
            last_s = s
    return out


# ------------------------------------------------------------------------------------------------ news
FEEDS = [("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
         ("Cointelegraph", "https://cointelegraph.com/rss"),
         ("Decrypt", "https://decrypt.co/feed"),
         ("Bitcoin Magazine", "https://bitcoinmagazine.com/.rss/full/"),
         ("U.Today", "https://u.today/rss")]
KEYWORDS = {"BTC": re.compile(r"\b(bitcoin|btc|crypto market|etf|fed|rate|halving|miners?)\b", re.I),
            "XRP": re.compile(r"\b(xrp|ripple|sec|garlinghouse)\b", re.I)}


def _all_news():
    items = []
    for src, url in FEEDS:
        try:
            root = ET.fromstring(_get(url, timeout=10).content)
        except Exception:
            continue
        for it in root.iter("item"):
            title = html.unescape((it.findtext("title") or "").strip())
            link = (it.findtext("link") or "").strip()
            when = it.findtext("pubDate") or ""
            try:
                ts = parsedate_to_datetime(when).timestamp()
            except Exception:
                ts = 0
            if title and link.startswith("http"):
                items.append({"title": title[:200], "url": link, "src": src, "ts": ts})
    items.sort(key=lambda x: -x["ts"])
    seen, out = set(), []
    for x in items:
        k = x["title"].lower()[:60]
        if k not in seen:
            seen.add(k)
            out.append(x)
    return out[:120]


def news(asset, n=8):
    allx = _cached("news", 300, _all_news) or []
    kw = KEYWORDS.get(asset, KEYWORDS["BTC"])
    hit = [x for x in allx if kw.search(x["title"])]
    return (hit or allx)[:n]


# ------------------------------------------------------------------------------------------------ fear & greed, weather
def fear_greed():
    def go():
        d = _get("https://api.alternative.me/fng/", {"limit": 1}).json()["data"][0]
        return {"value": int(d["value"]), "label": d["value_classification"]}
    return _cached("fng", 1800, go) or {}


WMO = {0: ("Clear", "☀"), 1: ("Mostly clear", "🌤"), 2: ("Partly cloudy", "⛅"), 3: ("Cloudy", "☁"),
       45: ("Fog", "🌫"), 48: ("Fog", "🌫"), 51: ("Drizzle", "🌦"), 53: ("Drizzle", "🌦"), 55: ("Drizzle", "🌦"),
       56: ("Freezing drizzle", "🌧"), 57: ("Freezing drizzle", "🌧"), 61: ("Rain", "🌧"), 63: ("Rain", "🌧"),
       65: ("Heavy rain", "🌧"), 66: ("Freezing rain", "🌧"), 67: ("Freezing rain", "🌧"), 71: ("Snow", "🌨"),
       73: ("Snow", "🌨"), 75: ("Heavy snow", "❄"), 77: ("Snow grains", "🌨"), 80: ("Showers", "🌦"),
       81: ("Showers", "🌦"), 82: ("Heavy showers", "⛈"), 85: ("Snow showers", "🌨"), 86: ("Snow showers", "🌨"),
       95: ("Thunderstorm", "⛈"), 96: ("Thunderstorm", "⛈"), 99: ("Thunderstorm", "⛈")}


def weather(lat=39.9526, lon=-75.1652, place="Philadelphia"):
    def go():
        j = _get("https://api.open-meteo.com/v1/forecast", {
            "latitude": lat, "longitude": lon, "timezone": "America/New_York",
            "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m,precipitation,is_day",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
            "temperature_unit": "fahrenheit", "wind_speed_unit": "mph", "forecast_days": 1}).json()
        c, d = j["current"], j["daily"]
        txt, icon = WMO.get(int(c["weather_code"]), ("", "🌡"))
        if icon == "☀" and not c.get("is_day"):
            icon = "🌙"
        return {"place": place, "temp": round(c["temperature_2m"]), "feels": round(c["apparent_temperature"]),
                "wind": round(c["wind_speed_10m"]), "text": txt, "icon": icon,
                "hi": round(d["temperature_2m_max"][0]), "lo": round(d["temperature_2m_min"][0]),
                "rain": d["precipitation_probability_max"][0]}
    return _cached("wx", 600, go) or {}
