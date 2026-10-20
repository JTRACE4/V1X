"""Accounts for the BRAIN dashboard (added 2026-10-20).

  * sign up -> request is PENDING until the owner approves it (email to the owner with one-tap Approve / Deny links,
    plus the /admin page)
  * a device that has logged in once is remembered (180-day cookie) - the login window only shows on a device it does
    not recognize
  * passwords are stored as PBKDF2-SHA256 hashes (never in plain text)
  * forgot password -> emailed reset link (1 hour, single use); without email set up, the request shows on /admin and the
    owner can make the link
  * the first owner account is created on /setup with OWNER_SETUP_CODE (one time only)

Email: set RESEND_API_KEY (+ EMAIL_FROM), or SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASS (+ EMAIL_FROM) on Railway.
Without either, everything still works - approvals and reset requests just wait on /admin instead of arriving by email.
Data lives in DATA_DIR/data_cache/users.json (on the Railway volume).
"""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import smtplib
import ssl
import threading
import time
from email.message import EmailMessage

import requests

_ROOT = os.environ.get("DATA_DIR") or os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(_ROOT, "data_cache", "users.json")
COOKIE = "brain_dev"
DEVICE_DAYS = 180
PBKDF2_ITERS = 210_000
_lock = threading.RLock()
DB = {"users": {}, "devices": {}, "reset_requests": [], "log": []}
_fails = {}                      # key -> [timestamps] of failed logins


def owner_email():
    return (os.environ.get("OWNER_EMAIL") or "").strip().lower()


def public_url():
    u = os.environ.get("PUBLIC_URL") or os.environ.get("RAILWAY_PUBLIC_DOMAIN") or ""
    if u and not u.startswith("http"):
        u = "https://" + u
    return u.rstrip("/")


def _secret():
    k = os.environ.get("AUTH_SECRET") or os.environ.get("HISTORY_SIGNING_KEY")
    if k:
        return ("auth|" + k).encode()
    kf = os.path.join(_ROOT, "data_cache", ".auth_key")
    try:
        with open(kf) as f:
            return f.read().strip().encode()
    except Exception:
        k = secrets.token_hex(32)
        os.makedirs(os.path.dirname(kf), exist_ok=True)
        with open(kf, "w") as f:
            f.write(k)
        return k.encode()


# ------------------------------------------------------------------------------------------------ storage
def load():
    global DB
    try:
        with open(USERS_FILE) as f:
            d = json.load(f)
        for k in ("users", "devices", "reset_requests", "log"):
            d.setdefault(k, {} if k in ("users", "devices") else [])
        DB = d
    except Exception:
        pass


def save():
    with _lock:
        os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
        tmp = USERS_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(DB, f)
        os.replace(tmp, USERS_FILE)


def _log(msg):
    DB["log"].append([int(time.time()), msg])
    del DB["log"][:-300]


# ------------------------------------------------------------------------------------------------ passwords
def hash_pw(pw):
    salt = secrets.token_bytes(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, PBKDF2_ITERS)
    return f"pbkdf2${PBKDF2_ITERS}${salt.hex()}${h.hex()}"


def check_pw(pw, stored):
    try:
        _alg, it, salt, h = stored.split("$")
        got = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), int(it))
        return hmac.compare_digest(got.hex(), h)
    except Exception:
        return False


USER_RE = re.compile(r"^[A-Za-z0-9_.-]{3,24}$")
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[A-Za-z]{2,24}$")


def _find(login):
    login = (login or "").strip().lower()
    u = DB["users"].get(login)
    if u:
        return u
    for x in DB["users"].values():
        if x["email"] == login:
            return x
    return None


def has_owner():
    return any(u.get("role") == "owner" and u.get("status") == "approved" for u in DB["users"].values())


def validate_new(username, email, pw, pw2):
    if not USER_RE.match(username or ""):
        return "Username: 3-24 letters, numbers, dots, dashes or underscores."
    if not EMAIL_RE.match(email or ""):
        return "That email doesn't look right."
    if len(pw or "") < 8:
        return "Password needs at least 8 characters."
    if pw != pw2:
        return "The two passwords don't match."
    if username.lower() in DB["users"]:
        return "That username is taken."
    if any(u["email"] == email.lower() for u in DB["users"].values()):
        return "That email already has an account."
    return None


def create_user(username, email, pw, role="viewer", status="pending", note=""):
    with _lock:
        u = {"username": username, "email": email.strip().lower(), "pw": hash_pw(pw), "role": role, "status": status,
             "created": int(time.time()), "approved": int(time.time()) if status == "approved" else None, "note": note[:300]}
        DB["users"][username.lower()] = u
        _log(f"signup {username} ({role}, {status})")
        save()
        return u


def set_status(username, status):
    with _lock:
        u = DB["users"].get((username or "").lower())
        if not u or u.get("role") == "owner":
            return None
        u["status"] = status
        if status == "approved":
            u["approved"] = int(time.time())
        if status != "approved":
            for tk in [k for k, d in DB["devices"].items() if d["u"] == u["username"].lower()]:
                DB["devices"].pop(tk, None)
        _log(f"{status} {u['username']}")
        save()
        return u


def remove_user(username):
    with _lock:
        u = DB["users"].get((username or "").lower())
        if not u or u.get("role") == "owner":
            return False
        DB["users"].pop(username.lower(), None)
        for tk in [k for k, d in DB["devices"].items() if d["u"] == username.lower()]:
            DB["devices"].pop(tk, None)
        _log(f"removed {username}")
        save()
        return True


def set_password(username, pw):
    with _lock:
        u = DB["users"].get(username.lower())
        if not u:
            return False
        u["pw"] = hash_pw(pw)
        for tk in [k for k, d in DB["devices"].items() if d["u"] == username.lower()]:
            DB["devices"].pop(tk, None)          # a new password signs every device out
        DB["reset_requests"] = [r for r in DB["reset_requests"] if r["u"] != username.lower()]
        _log(f"password changed {username}")
        save()
        return True


# ------------------------------------------------------------------------------------------------ devices / sessions
def _dkey(token):
    return hashlib.sha256(token.encode()).hexdigest()


def parse_cookie(header):
    out = {}
    for part in (header or "").split(";"):
        if "=" in part:
            k, v = part.strip().split("=", 1)
            out[k] = v
    return out


def user_from_cookie(header):
    """The approved user this device is signed in as, or None."""
    tok = parse_cookie(header).get(COOKIE)
    if not tok or len(tok) > 100:
        return None
    with _lock:
        d = DB["devices"].get(_dkey(tok))
        if not d:
            return None
        now = time.time()
        if now - d.get("seen", 0) > DEVICE_DAYS * 86400:
            DB["devices"].pop(_dkey(tok), None)
            return None
        u = DB["users"].get(d["u"])
        if not u or u.get("status") != "approved":
            return None
        if now - d.get("seen", 0) > 600:
            d["seen"] = int(now)
            save()
        return u


def _rate_ok(key):
    now = time.time()
    lst = [t for t in _fails.get(key, []) if now - t < 900]
    _fails[key] = lst
    return len(lst) < 8


def login(login_name, pw, ua="", ip=""):
    """(cookie_token, user, None) or (None, user_or_None, error message)."""
    if not (_rate_ok("ip:" + ip) and _rate_ok("u:" + (login_name or "").lower())):
        return None, None, "Too many tries. Wait 15 minutes and try again."
    with _lock:
        u = _find(login_name)
        if not u or not check_pw(pw or "", u["pw"]):
            now = time.time()
            _fails.setdefault("ip:" + ip, []).append(now)
            _fails.setdefault("u:" + (login_name or "").lower(), []).append(now)
            return None, None, "Wrong username / email or password."
        if u["status"] == "pending":
            return None, u, "Your access request is still waiting for approval."
        if u["status"] != "approved":
            return None, u, "This account doesn't have access."
        return new_device(u, ua, ip), u, None


def new_device(u, ua="", ip=""):
    with _lock:
        tok = secrets.token_urlsafe(32)
        DB["devices"][_dkey(tok)] = {"u": u["username"].lower(), "created": int(time.time()), "seen": int(time.time()),
                                     "ua": (ua or "")[:160], "ip": ip}
        _log(f"login {u['username']} {ip}")
        save()
        return tok


def logout(header):
    tok = parse_cookie(header).get(COOKIE)
    if tok:
        with _lock:
            DB["devices"].pop(_dkey(tok), None)
            save()


def cookie_header(tok, secure=True):
    return (f"{COOKIE}={tok}; Path=/; Max-Age={DEVICE_DAYS * 86400}; HttpOnly; SameSite=Lax"
            + ("; Secure" if secure else ""))


def clear_cookie_header():
    return f"{COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"


def devices_of(username):
    with _lock:
        return [dict(d, key=k[:12]) for k, d in DB["devices"].items() if d["u"] == username.lower()]


def revoke_device(key_prefix):
    with _lock:
        for k in list(DB["devices"]):
            if k.startswith(key_prefix) and len(key_prefix) >= 8:
                DB["devices"].pop(k, None)
                save()
                return True
    return False


# ------------------------------------------------------------------------------------------------ signed links
def _b64(b):
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def make_token(kind, username, ttl, extra=""):
    body = _b64(json.dumps({"k": kind, "u": username.lower(), "e": int(time.time() + ttl), "x": extra}).encode())
    sig = _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest()[:20])
    return body + "." + sig


def read_token(tok, kind):
    try:
        body, sig = tok.split(".", 1)
        good = _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest()[:20])
        if not hmac.compare_digest(sig, good):
            return None
        d = json.loads(_unb64(body))
        if d.get("k") != kind or d.get("e", 0) < time.time():
            return None
        return d
    except Exception:
        return None


def _pw_nonce(u):
    return hashlib.sha256(u["pw"].encode()).hexdigest()[:16]     # changes once the password changes -> link is single use


def reset_link(u):
    return f"{public_url()}/reset?t={make_token('reset', u['username'], 3600, _pw_nonce(u))}"


def reset_user_from_token(tok):
    d = read_token(tok, "reset")
    if not d:
        return None
    u = DB["users"].get(d["u"])
    if not u or d.get("x") != _pw_nonce(u):
        return None
    return u


# ------------------------------------------------------------------------------------------------ email
def email_ready():
    return bool(os.environ.get("RESEND_API_KEY") or (os.environ.get("SMTP_HOST") and os.environ.get("SMTP_USER")))


def send_email(to, subject, text):
    """Fire-and-forget. Returns True if an email service is configured (sending happens in the background)."""
    if not to or not email_ready():
        return False

    def go():
        sender = os.environ.get("EMAIL_FROM") or os.environ.get("SMTP_USER") or "BRAIN <onboarding@resend.dev>"
        try:
            if os.environ.get("RESEND_API_KEY"):
                r = requests.post("https://api.resend.com/emails", timeout=20,
                                  headers={"Authorization": "Bearer " + os.environ["RESEND_API_KEY"]},
                                  json={"from": sender, "to": [to], "subject": subject, "text": text})
                if r.status_code >= 300:
                    print(f"[email] resend {r.status_code}: {r.text[:200]}")
                return
            msg = EmailMessage()
            msg["From"], msg["To"], msg["Subject"] = sender, to, subject
            msg.set_content(text)
            host, port = os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT") or 465)
            if port == 465:
                with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=20) as s:
                    s.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASS", ""))
                    s.send_message(msg)
            else:
                with smtplib.SMTP(host, port, timeout=20) as s:
                    s.starttls(context=ssl.create_default_context())
                    s.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASS", ""))
                    s.send_message(msg)
        except Exception as e:
            print(f"[email] failed: {e!r}")
    threading.Thread(target=go, daemon=True).start()
    return True


def notify_owner_signup(u, ip=""):
    to = owner_email() or next((x["email"] for x in DB["users"].values() if x.get("role") == "owner"), "")
    base = public_url()
    ok = make_token("approve", u["username"], 7 * 86400)
    no = make_token("deny", u["username"], 7 * 86400)
    text = (f"New BRAIN access request\n\nUsername: {u['username']}\nEmail: {u['email']}\n"
            + (f"Note: {u['note']}\n" if u.get("note") else "") + f"From: {ip}\n\n"
            f"Approve: {base}/auth/approve?t={ok}\nDeny:    {base}/auth/deny?t={no}\n\n"
            f"Or manage everyone at {base}/admin")
    return send_email(to, f"BRAIN: {u['username']} wants access", text)


def notify_user_approved(u):
    return send_email(u["email"], "You're in - BRAIN access approved",
                      f"Hi {u['username']},\n\nYour BRAIN access was approved. Log in at {public_url()}/login\n")


def request_reset(email, ip=""):
    """Always answers the same way (never reveals whether an email has an account)."""
    with _lock:
        u = _find(email)
        if not u or u["status"] != "approved":
            return
        if send_email(u["email"], "Reset your BRAIN password",
                      f"Hi {u['username']},\n\nReset your password (link works for 1 hour, once):\n{reset_link(u)}\n\n"
                      f"If you didn't ask for this, ignore this email."):
            return
        DB["reset_requests"] = [r for r in DB["reset_requests"] if r["u"] != u["username"].lower()]
        DB["reset_requests"].append({"u": u["username"].lower(), "t": int(time.time()), "ip": ip})
        save()
