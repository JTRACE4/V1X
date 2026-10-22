"""Trader Radar - what specific, VERIFIED Kalshi traders are holding on the BTC / XRP 15-minute rounds.

Added 2026-10-22. Positions come from the position badges in Kalshi's Live Chat ("MOGS  UP $140"), read by BRAIN's own
small browser extension while the owner has a round's Live Chat open, and posted to /radar_ingest with a secret token.

Anti-impostor: every chat message links to the poster's Kalshi profile (/ideas/profiles/<handle>); handles are unique
per account, so each watched name is locked to its exact handle. Any other account using a lookalike name (M0GS, MOGS_,
Cyrillic letters...) is kept apart as an impostor and never counted.

Storage: one JSON line per sighting in DATA_DIR/bot_state/trader_radar.jsonl, pruned to the last 7 days. Everything is
in memory and tiny; nothing here polls anything.
"""
import json
import os
import re
import secrets
import threading
import time
import unicodedata
import datetime as dt
from zoneinfo import ZoneInfo

_ROOT = os.environ.get("DATA_DIR") or os.path.dirname(os.path.abspath(__file__))
_DIR = os.path.join(_ROOT, "bot_state")
EVENTS_FILE = os.path.join(_DIR, "trader_radar.jsonl")
REG_FILE = os.path.join(_DIR, "radar_traders.json")
KEEP_SECONDS = 7 * 24 * 3600
ET = ZoneInfo("America/New_York")
# Owner's picks + Kalshi's top 20 Crypto traders by all-time profit (leaderboard, read 2026-10-22).
# Identity = the Kalshi profile handle each chat message links to (/ideas/profiles/<handle>, case-insensitive, unique per
# account), so each name is locked to its own handle automatically - a lookalike (M0GS, mogs_) is a different handle.
DEFAULT_WATCH = ["MOGS", "RichieRich", "Vince23", "maxy", "smolsquid", "DineroBoy",
                 "financial.eagle6896", "gamma.goblin", "horrible.wildcat3161", "boostedtea", "KneeHowdy", "szg.szg",
                 "written.sheepdog2191", "mushy.basset5206", "plunder", "aware.mallard2262", "princezote",
                 "my.nickname.telegram.dorin1986", "zdxa", "vicious.boxer7605", "flag.tea", "representative.bulldog9046",
                 "jakeharv88", "lerugi", "System.AI", "misleading.chameleon2328"]

_lock = threading.Lock()
_events = []                     # dicts, oldest first
_reg = {"token": None, "traders": {}}
_last_prune = [0.0]

# lookalike letters people use to fake a name -> the plain letter
_HOMO = str.maketrans({"0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "7": "t", "$": "s", "@": "a", "|": "l", "!": "i",
                       "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "у": "y", "к": "k", "м": "m",
                       "т": "t", "в": "b", "н": "h", "і": "i", "ѕ": "s", "ј": "j", "ο": "o", "α": "a", "ν": "v"})


def norm(name):
    """Folded form used ONLY to spot lookalikes (never to trust): case, accents, separators and look-alike characters."""
    s = unicodedata.normalize("NFKC", str(name or "")).casefold().translate(_HOMO)
    s = "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]", "", s)


def _now():
    return time.time()


# ------------------------------------------------------------------------------------------------ registry
def _save_reg():
    os.makedirs(_DIR, exist_ok=True)
    tmp = REG_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(_reg, f)
    os.replace(tmp, REG_FILE)


def load():
    """Load the trader list + the last 7 days of sightings (call once at startup)."""
    global _reg
    with _lock:
        try:
            with open(REG_FILE) as f:
                _reg = json.load(f)
        except Exception:
            _reg = {"token": None, "traders": {}}
        _reg.setdefault("traders", {})
        if not _reg.get("token"):
            _reg["token"] = secrets.token_urlsafe(24)
        for n in DEFAULT_WATCH:
            if not any(norm(k) == norm(n) for k in _reg["traders"]):
                _reg["traders"][n] = {"account_id": n.lower(), "added": _now(), "note": ""}
        for k, t in _reg["traders"].items():          # every watched name is locked to its own profile handle
            if not t.get("account_id"):
                t["account_id"] = k.lower()
        _save_reg()
        cutoff = _now() - KEEP_SECONDS
        _events.clear()
        try:
            with open(EVENTS_FILE) as f:
                for line in f:
                    try:
                        e = json.loads(line)
                        if e.get("ts", 0) >= cutoff:
                            _events.append(e)
                    except Exception:
                        pass
        except FileNotFoundError:
            pass
        _rewrite_locked()
    print(f"[radar] {len(_reg['traders'])} watched traders, {len(_events)} sightings in the last 7 days")


def token():
    return os.environ.get("RADAR_TOKEN") or _reg.get("token")


def traders():
    with _lock:
        return {k: dict(v) for k, v in _reg["traders"].items()}


def watch(name, note=""):
    name = (name or "").strip().lstrip("@")[:40]
    if not re.fullmatch(r"[A-Za-z0-9._\-]{2,40}", name):
        return False, "Names are letters, numbers, dots, dashes or underscores."
    with _lock:
        if any(norm(k) == norm(name) for k in _reg["traders"]):
            return False, f"{name} is already on the list."
        _reg["traders"][name] = {"account_id": name.lower(), "added": _now(), "note": note[:80]}
        _save_reg()
    return True, f"Watching {name} (locked to the Kalshi profile handle '{name.lower()}')."


def unwatch(name):
    with _lock:
        if _reg["traders"].pop(name, None) is None:
            return False, "Not on the list."
        _save_reg()
    return True, f"Stopped watching {name}."


def trust(name, account_id, note=""):
    """Lock a watched name to one Kalshi account ID - the ONLY account counted for that name from now on."""
    account_id = str(account_id or "").strip()[:80]
    with _lock:
        t = _reg["traders"].get(name)
        if t is None or not account_id:
            return False, "Pick a watched name and a sighting's account."
        t["account_id"] = account_id.lower()
        if note:
            t["note"] = note[:80]
        _save_reg()
    return True, f"{name} is now locked to account {account_id[:10]}... - every other account using that name is ignored."


# ------------------------------------------------------------------------------------------------ sightings
def _match(display_name, account_id):
    """-> (watched_name or None, status) where status is 'trusted', 'pending' (name watched, not locked yet) or 'impostor'."""
    n = norm(display_name)
    for k, t in _reg["traders"].items():
        if norm(k) != n:
            continue
        if t.get("account_id"):
            return k, ("trusted" if str(account_id).lower() == t["account_id"].lower() else "impostor")
        return k, "pending"
    return None, None


_TICKER = re.compile(r"^KX(BTC|XRP)15M-[0-9A-Z]+-[0-9]+$")
_EVENT = re.compile(r"^KX(BTC|XRP)15M-\d{2}[A-Z]{3}\d{6}$")


def _market_ticker(tk, asset, ts):
    """Event ticker KXBTC15M-26OCT221245 -> market KXBTC15M-26OCT221245-45. No ticker -> the round open at ts."""
    if _EVENT.match(tk):
        return tk + "-" + tk[-2:]
    if not tk and asset in ("BTC", "XRP"):
        t = dt.datetime.fromtimestamp(ts, ET)
        close = (t.replace(second=0, microsecond=0, minute=(t.minute // 15) * 15) + dt.timedelta(minutes=15))
        return f"KX{asset}15M-{close.strftime('%y%b%d%H%M').upper()}-{close.strftime('%M')}"
    return tk


def ingest(rows):
    """rows: [{name, account_id, side ('UP'/'DOWN'), usd, ticker, msg_id, ts?}] from the chat watcher. Returns counts."""
    added = trusted = imp = 0
    now = _now()
    with _lock:
        seen = {e.get("msg_id") for e in _events[-3000:] if e.get("msg_id")}
        out = []
        for r in rows[:200]:
            try:
                side = str(r.get("side", "")).upper()
                tk = _market_ticker(str(r.get("ticker", "")).upper(), str(r.get("asset", "")).upper(),
                                    min(now, float(r.get("ts") or now)))
                acct = str(r.get("account_id") or "").strip()[:80]
                usd = float(r.get("usd") or 0)
                mid = str(r.get("msg_id") or "")[:120]
                if side not in ("UP", "DOWN") or not _TICKER.match(tk) or not acct or usd < 0 or usd > 5_000_000:
                    continue
                if mid and mid in seen:
                    continue
                who, status = _match(r.get("name", ""), acct)
                if who is None:
                    continue                                   # not someone we watch (or a lookalike of them)
                e = {"ts": min(now, float(r.get("ts") or now)), "who": who, "name": str(r.get("name", ""))[:40],
                     "acct": acct, "status": status, "side": side, "usd": round(usd, 2), "ticker": tk,
                     "asset": tk[2:5], "msg_id": mid}
                out.append(e)
                seen.add(mid)
                added += 1
                trusted += status == "trusted"
                imp += status == "impostor"
            except Exception:
                continue
        if out:
            _events.extend(out)
            os.makedirs(_DIR, exist_ok=True)
            with open(EVENTS_FILE, "a") as f:
                for e in out:
                    f.write(json.dumps(e) + "\n")
        if now - _last_prune[0] > 3600:
            _rewrite_locked()
    return {"added": added, "trusted": trusted, "impostor": imp}


def _rewrite_locked():
    """Drop sightings older than 7 days (in memory and on disk). Caller holds _lock."""
    cutoff = _now() - KEEP_SECONDS
    _events[:] = [e for e in _events if e.get("ts", 0) >= cutoff]
    os.makedirs(_DIR, exist_ok=True)
    tmp = EVENTS_FILE + ".tmp"
    with open(tmp, "w") as f:
        for e in _events:
            f.write(json.dumps(e) + "\n")
    os.replace(tmp, EVENTS_FILE)
    _last_prune[0] = _now()


# ------------------------------------------------------------------------------------------------ views
def _status(e):
    """Trust is decided against the CURRENT locks, so sightings from before a lock are re-judged once it's set."""
    t = _reg["traders"].get(e.get("who"))
    if t is None:
        return None
    if not t.get("account_id"):
        return "pending"
    return "trusted" if (e.get("acct") or "").lower() == t["account_id"].lower() else "impostor"


def _with_status(evts):
    out = []
    for e in evts:
        st = _status(e)
        if st:
            x = dict(e)
            x["status"] = st
            out.append(x)
    return out


def _latest_by_trader(evts):
    """Each trusted trader's LAST badge per round (their current position that round)."""
    last = {}
    for e in evts:
        if e["status"] == "trusted":
            last[(e["who"], e["ticker"])] = e
    return last


def round_view(ticker):
    """This round: trusted positions, $ on each side, and impostor/pending sightings."""
    with _lock:
        ev = _with_status([e for e in _events if e["ticker"] == ticker])
    pos = sorted(_latest_by_trader(ev).values(), key=lambda e: -e["ts"])
    up = sum(e["usd"] for e in pos if e["side"] == "UP")
    down = sum(e["usd"] for e in pos if e["side"] == "DOWN")
    others = [e for e in ev if e["status"] != "trusted"]
    return {"positions": pos, "up": up, "down": down, "others": others[-6:]}


def records(result_of, asset=None):
    """Per trader and for 'the radar consensus': rounds, wins, $ in, over the last hour / today (ET) / 7 days.
    result_of(ticker) -> 'UP' / 'DOWN' / None (not settled yet)."""
    now = _now()
    day0 = dt.datetime.now(ET).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    windows = {"hour": now - 3600, "today": day0, "7d": now - KEEP_SECONDS}
    with _lock:
        ev = _with_status([e for e in _events if asset is None or e["asset"] == asset])
    last = _latest_by_trader(ev)
    out = {w: {"traders": {}, "consensus": [0, 0]} for w in windows}
    by_round = {}
    for (who, tk), e in last.items():
        res = result_of(tk)
        if res is None:
            continue
        by_round.setdefault(tk, []).append(e)
        for w, since in windows.items():
            if e["ts"] < since:
                continue
            r = out[w]["traders"].setdefault(who, {"n": 0, "w": 0, "usd": 0.0})
            r["n"] += 1
            r["w"] += e["side"] == res
            r["usd"] += e["usd"]
    for tk, es in by_round.items():
        res = result_of(tk)
        up = sum(e["usd"] for e in es if e["side"] == "UP")
        dn = sum(e["usd"] for e in es if e["side"] == "DOWN")
        if up == dn:
            continue
        side = "UP" if up > dn else "DOWN"
        ts = max(e["ts"] for e in es)
        for w, since in windows.items():
            if ts >= since:
                out[w]["consensus"][0] += 1
                out[w]["consensus"][1] += side == res
    return out


def recent_trusted(seconds=30):
    with _lock:
        return [e for e in _with_status(_events[-200:]) if e["status"] == "trusted" and _now() - e["ts"] <= seconds]


def sightings_for_locking(limit=20):
    """Distinct (watched name, account) pairs seen so far that are NOT the locked account - for the 'Trust' buttons."""
    with _lock:
        seen = {}
        for e in reversed(_with_status(_events)):
            if e["status"] in ("pending", "impostor"):
                k = (e["who"], e["acct"])
                if k not in seen:
                    seen[k] = {"who": e["who"], "name": e["name"], "acct": e["acct"], "n": 0, "last": e["ts"]}
                seen[k]["n"] += 1
        return list(seen.values())[:limit]


# ------------------------------------------------------------------------------------------------ sealed-call input
ELITE_MIN_WR = 0.80          # 7-day win rate to count at the sealed call
ELITE_MIN_ROUNDS = 10        # ...over at least this many settled rounds (a 4-for-5 streak doesn't qualify)
ELITE_MIN_TRADERS = 2        # need at least two of them in the round


def elite_view(ticker, result_of):
    """Qualified traders (80%+ over 10+ settled rounds in 7 days, verified accounts) holding a side in THIS round.
    -> {"side": 'UP'/'DOWN'/None (majority by head count), "up": n, "down": n, "who": [(name, side, usd, wr)]}"""
    asset = (ticker or "")[2:5]
    rec = records(result_of, asset=asset)["7d"]["traders"]
    elite = {k: v["w"] / v["n"] for k, v in rec.items() if v["n"] >= ELITE_MIN_ROUNDS and v["w"] / v["n"] >= ELITE_MIN_WR}
    pos = [e for e in round_view(ticker)["positions"] if e["who"] in elite]
    up = sum(1 for e in pos if e["side"] == "UP")
    down = sum(1 for e in pos if e["side"] == "DOWN")
    side = None
    if up + down >= ELITE_MIN_TRADERS and up != down:
        side = "UP" if up > down else "DOWN"
    return {"side": side, "up": up, "down": down, "who": [(e["who"], e["side"], e["usd"], elite[e["who"]]) for e in pos]}
