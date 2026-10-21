"""Kalshi API key entered on the Admin page (added 2026-10-21).

The owner pastes their Kalshi API key ID and private key (.pem text) on /admin. It is checked against Kalshi (a balance read)
before it is kept, then stored ENCRYPTED on the data volume (DATA_DIR/bot_state/kalshi_creds.enc) with a key derived from a
server secret (KALSHI_CREDS_SECRET, else HISTORY_SIGNING_KEY / AUTH_SECRET). It is never sent back to any page - the Admin
page only shows "connected", the last 4 characters of the key ID, and the balance.
"""
import base64
import hashlib
import json
import os
import threading
import time

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import serialization

_DIR = os.path.join(os.environ.get("DATA_DIR") or os.path.dirname(os.path.abspath(__file__)), "bot_state")
_FILE = os.path.join(_DIR, "kalshi_creds.enc")
_lock = threading.Lock()
_cache = {"loaded": False, "val": None}


def _secret():
    s = os.environ.get("KALSHI_CREDS_SECRET") or os.environ.get("HISTORY_SIGNING_KEY") or os.environ.get("AUTH_SECRET")
    return s.encode() if s else None


def can_store():
    return _secret() is not None


def _fernet():
    s = _secret()
    if not s:
        raise RuntimeError("no server secret set (KALSHI_CREDS_SECRET)")
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(b"kalshi-creds|" + s).digest()))


def clean_pem(text):
    """Accept the private key pasted with or without line breaks / with \\n escapes, return clean PEM bytes."""
    t = (text or "").strip().replace("\\n", "\n").replace("\r", "")
    if "-----BEGIN" in t and "\n" not in t:
        # pasted as one line: rebuild the body in 64-char lines
        import re
        m = re.match(r"(-----BEGIN [A-Z ]+-----)(.*?)(-----END [A-Z ]+-----)", t.replace("\n", ""), re.S)
        if m:
            body = m.group(2).replace(" ", "")
            t = m.group(1) + "\n" + "\n".join(body[i:i + 64] for i in range(0, len(body), 64)) + "\n" + m.group(3)
    return (t + "\n").encode()


def check_pem(pem_bytes):
    serialization.load_pem_private_key(pem_bytes, password=None)     # raises if it's not a valid unencrypted private key


def get():
    """(key_id, pem_bytes) or None."""
    with _lock:
        if not _cache["loaded"]:
            _cache["loaded"] = True
            _cache["val"] = None
            try:
                with open(_FILE, "rb") as f:
                    d = json.loads(_fernet().decrypt(f.read()).decode())
                _cache["val"] = (d["key_id"], d["pem"].encode(), d.get("saved"))
            except FileNotFoundError:
                pass
            except (InvalidToken, ValueError, KeyError, RuntimeError) as e:
                print(f"[kalshi key] stored key could not be read: {e!r}")
        v = _cache["val"]
        return (v[0], v[1]) if v else None


def info():
    v = get()
    saved = _cache["val"][2] if _cache["val"] else None
    return {"set": bool(v), "key_tail": v[0][-4:] if v else None, "saved": saved, "can_store": can_store()}


def save(key_id, pem_bytes):
    os.makedirs(_DIR, exist_ok=True)
    blob = _fernet().encrypt(json.dumps({"key_id": key_id, "pem": pem_bytes.decode(), "saved": time.time()}).encode())
    tmp = _FILE + ".tmp"
    with open(tmp, "wb") as f:
        f.write(blob)
    os.replace(tmp, _FILE)
    try:
        os.chmod(_FILE, 0o600)
    except OSError:
        pass
    with _lock:
        _cache.update(loaded=True, val=(key_id, pem_bytes, time.time()))


def remove():
    try:
        os.remove(_FILE)
    except FileNotFoundError:
        pass
    with _lock:
        _cache.update(loaded=True, val=None)
