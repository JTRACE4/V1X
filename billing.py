"""BRAIN passes - one-time Stripe payments that unlock the live dashboard for a set number of days (added 2026-10-22).

  * passes: 7 days $64.99, 30 days $165, 3.5 months (105 days) $379 - one-time, never auto-renew
  * a member's access is a single date: user["access_until"] (epoch seconds). Buying adds the pass's days on top of
    whatever time is left. The owner always has access and can give anyone free days from /admin.
  * checkout = Stripe Payment Links (env STRIPE_LINK_7D / STRIPE_LINK_30D / STRIPE_LINK_105D). The site adds
    ?client_reference_id=<username>&prefilled_email=<email> so the payment lands on the right account.
  * Stripe tells the site about each payment at POST /stripe/webhook. Every call is checked against
    STRIPE_WEBHOOK_SECRET (Stripe's signature) - a request without a valid signature changes nothing.
  * emails from support@brainswatch.com: "pass active" right after paying, and a reminder 2 days before it ends.
  * all sales are final.
"""
import hashlib
import hmac
import json
import os
import time
import datetime as dt
from zoneinfo import ZoneInfo

import auth as _auth

PASSES = {                      # key -> (days, price in cents, label)
    "7d": (7, 6499, "7 days"),
    "30d": (30, 16500, "30 days"),
    "105d": (105, 37900, "3.5 months"),
}
_BY_AMOUNT = {cents: k for k, (_d, cents, _l) in PASSES.items()}
REMIND_BEFORE_S = 2 * 86400
SIG_TOLERANCE_S = 300
ET = ZoneInfo("America/New_York")


def link_for(key):
    return os.environ.get({"7d": "STRIPE_LINK_7D", "30d": "STRIPE_LINK_30D", "105d": "STRIPE_LINK_105D"}[key], "")


def checkout_url(key, user):
    base = link_for(key)
    if not base or not user:
        return ""
    import urllib.parse as _u
    return base + ("&" if "?" in base else "?") + _u.urlencode({"client_reference_id": user["username"],
                                                                 "prefilled_email": user.get("email", "")})


def access_until(user):
    return float((user or {}).get("access_until") or 0)


def has_access(user):
    if not user:
        return False
    if user.get("role") == "owner":
        return True
    return access_until(user) > time.time()


def fmt_until(ts):
    return dt.datetime.fromtimestamp(ts, ET).strftime("%b %d, %Y %-I:%M %p ET")


def grant_days(username, days, why="admin"):
    """Add days on top of any time left (or start from now). Returns the user, or None."""
    with _auth._lock:
        u = _auth.DB["users"].get((username or "").lower())
        if not u:
            return None
        start = max(time.time(), access_until(u))
        u["access_until"] = int(start + days * 86400)
        u.pop("reminded_for", None)
        if u.get("status") == "pending":
            u["status"] = "approved"
        _auth._log(f"access +{days}d for {u['username']} ({why}) -> {fmt_until(u['access_until'])}")
        _auth.save()
        return u


# ------------------------------------------------------------------------------------------------ Stripe webhook
def verify_signature(payload, header, secret, now=None):
    """Stripe-Signature: t=<ts>,v1=<hmac-sha256 of '<ts>.<payload>'> (one or more v1)."""
    if not secret or not header:
        return False
    parts = {}
    for item in header.split(","):
        k, _, v = item.partition("=")
        parts.setdefault(k.strip(), []).append(v.strip())
    try:
        ts = int((parts.get("t") or ["0"])[0])
    except ValueError:
        return False
    if abs((now or time.time()) - ts) > SIG_TOLERANCE_S:
        return False
    expected = hmac.new(secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, sig) for sig in parts.get("v1", []))


def handle_event(event):
    """Apply one verified Stripe event. Returns a short status string (for the log)."""
    if event.get("type") not in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        return "ignored " + str(event.get("type"))
    s = (event.get("data") or {}).get("object") or {}
    if s.get("payment_status") != "paid":
        return "not paid yet"
    sid = s.get("id", "")
    with _auth._lock:
        done = _auth.DB.setdefault("payments", [])
        if any(p.get("session") == sid for p in done):
            return "already applied"
    md = s.get("metadata") or {}
    key = md.get("pass") if md.get("pass") in PASSES else _BY_AMOUNT.get(int(s.get("amount_total") or 0))
    username = (s.get("client_reference_id") or "").strip()
    email = ((s.get("customer_details") or {}).get("email") or "").strip().lower()
    if not username and email:
        username = next((u["username"] for u in _auth.DB["users"].values() if u.get("email") == email), "")
    if not key or not username:
        print(f"[billing] PAID but could not match: session {sid} pass={key} user={username!r} email={email!r}")
        with _auth._lock:
            _auth.DB.setdefault("payments", []).append({"session": sid, "user": username, "pass": key, "amount": s.get("amount_total"),
                                                       "ts": int(time.time()), "unmatched": True, "email": email})
            _auth.save()
        notify_owner(f"BRAIN: payment needs matching ({email or 'no email'})",
                     f"A payment came in that BRAIN couldn't match to an account.\n\nStripe session: {sid}\nEmail: {email}\n"
                     f"Amount: ${(s.get('amount_total') or 0) / 100:.2f}\n\nGive them the days from {_auth.public_url()}/admin.")
        return "unmatched"
    days, _cents, label = PASSES[key]
    u = grant_days(username, days, why=f"stripe {key}")
    if not u:
        return "user missing"
    with _auth._lock:
        _auth.DB.setdefault("payments", []).append({"session": sid, "user": u["username"], "pass": key,
                                                   "amount": s.get("amount_total"), "ts": int(time.time())})
        del _auth.DB["payments"][:-2000]
        _auth.save()
    _auth.send_email(u["email"], "Your BRAIN pass is active",
                     f"Hi {u['username']},\n\nThanks for joining BRAIN. Your {label} pass is active until "
                     f"{fmt_until(u['access_until'])}.\n\nOpen the live dashboard: {_auth.public_url()}/app\n\n"
                     "Passes don't renew on their own - we'll email you 2 days before it ends.\n\n"
                     "BRAIN is educational market analysis, not financial advice. All sales are final.\n\n- BRAIN")
    notify_owner(f"BRAIN: {u['username']} bought {label}",
                 f"{u['username']} ({u['email']}) bought the {label} pass (${PASSES[key][1] / 100:.2f}).\n"
                 f"Access until {fmt_until(u['access_until'])}.")
    return f"granted {label} to {u['username']}"


def notify_owner(subject, text):
    to = _auth.owner_email() or next((x["email"] for x in _auth.DB["users"].values() if x.get("role") == "owner"), "")
    if to:
        _auth.send_email(to, subject, text)


def send_reminders():
    """Once per pass: email members whose access ends within 2 days. Safe to call often (it's a quick scan)."""
    now = time.time()
    due = []
    with _auth._lock:
        for u in _auth.DB["users"].values():
            au = access_until(u)
            if u.get("role") == "owner" or not au or au <= now or au - now > REMIND_BEFORE_S:
                continue
            if u.get("reminded_for") == int(au):
                continue
            u["reminded_for"] = int(au)
            due.append(dict(u))
        if due:
            _auth.save()
    for u in due:
        _auth.send_email(u["email"], "Your BRAIN pass ends soon",
                         f"Hi {u['username']},\n\nYour BRAIN pass ends {fmt_until(access_until(u))}.\n\n"
                         f"Keep your access: {_auth.public_url()}/pricing\n\n- BRAIN")
    return len(due)
