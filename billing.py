"""BRAIN passes - one-time Stripe payments that unlock the live dashboard for a set number of days (added 2026-10-22).

  * passes: 10 days $65, 30 days $160, 3.5 months (105 days) $379 (changed 2026-10-23 from 7 days $64.99 / 30 days $165) - one-time, never auto-renew
  * CHART ONLY (2026-10-23): 3.5 months (105 days) $35 - just the live BTC / XRP charts with the indicators, the "What do these
    mean?" guide and the chart patterns. No BRAIN bot features. Its time is kept separately in user["chart_until"]; a full pass
    also includes the chart.
  * a member's access is a single date: user["access_until"] (epoch seconds). Buying adds the pass's days on top of
    whatever time is left. The owner always has access and can give anyone free days from /admin.
  * checkout = Stripe Payment Links (env STRIPE_LINK_10D / STRIPE_LINK_30D / STRIPE_LINK_105D). The site adds
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
    "10d": (10, 6500, "10 days"),
    "30d": (30, 16000, "30 days"),
    "105d": (105, 37900, "3.5 months"),
    "chart105": (105, 3500, "Chart Only - 3.5 months"),
}
CHART_PASSES = {"chart105"}      # these add to user["chart_until"], not the full BRAIN access
BOT_PASSES = [k for k in PASSES if k not in CHART_PASSES]
_LINK_ENV = {"10d": "STRIPE_LINK_10D", "30d": "STRIPE_LINK_30D", "105d": "STRIPE_LINK_105D", "chart105": "STRIPE_LINK_CHART"}
_BY_AMOUNT = {cents: k for k, (_d, cents, _l) in PASSES.items()}
REMIND_BEFORE_S = 2 * 86400
SIG_TOLERANCE_S = 300
ET = ZoneInfo("America/New_York")


def _mode():
    k = os.environ.get("STRIPE_SECRET_KEY", "")
    return "live" if k.startswith(("sk_live_", "rk_live_")) else ("test" if k else "")


def _auto():
    return (_auth.DB.get("stripe") or {}).get(_mode()) or {}


def link_for(key):
    env = os.environ.get(_LINK_ENV[key], "")
    return env or (_auto().get("links") or {}).get(_link_key(key), "")


def _link_key(key):
    """Stripe links are remembered per pass AND price, so a price change makes a fresh link instead of reusing the old one."""
    return f"{key}@{PASSES[key][1]}"


def webhook_secret():
    return os.environ.get("STRIPE_WEBHOOK_SECRET") or _auto().get("whsec", "")


# ------------------------------------------------------------------------------------- one-time Stripe auto-setup
# With STRIPE_SECRET_KEY set (a test key sk_test_... first, the live key later), the site creates its own three products,
# prices, payment links and the webhook endpoint once, and remembers them (per test/live mode) in the user database.
# Nothing is ever charged by this - it only creates the catalog.
PRODUCT_DESC = ("Access to the BRAIN live market-data dashboard for {label}, plus the BRAIN Playbook (PDF guide). "
                "Educational market analysis and information service - not financial advice. One-time payment, "
                "does not renew. All sales final.")
CHART_DESC = ("BRAIN Chart Only: the live BTC and XRP charts with indicators (EMA, RSI, MACD, support / resistance zones), the "
              "plain-English indicator guide and chart patterns with their track record, for 3.5 months (105 days). Does not "
              "include the BRAIN bot features. Educational market information - not financial advice. One-time payment, does not "
              "renew. All sales final.")


def _stripe(method, path, data=None):
    import urllib.parse as _u, urllib.request as _r
    body = _u.urlencode(data or {}, doseq=True).encode() if data is not None else None
    req = _r.Request("https://api.stripe.com/v1/" + path, data=body, method=method,
                     headers={"Authorization": "Bearer " + os.environ["STRIPE_SECRET_KEY"],
                              "Content-Type": "application/x-www-form-urlencoded"})
    with _r.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def ensure_stripe():
    """Create whatever is missing for the current key's mode. Safe to call at every start. Returns a status line."""
    mode = _mode()
    if not mode:
        return "no STRIPE_SECRET_KEY"
    with _auth._lock:
        st = _auth.DB.setdefault("stripe", {}).setdefault(mode, {})
        links = st.setdefault("links", {})
    base = (_auth.public_url() or "https://brainswatch.com").rstrip("/")
    made = []
    for key, (days, cents, label) in PASSES.items():
        if links.get(_link_key(key)):
            continue
        desc = CHART_DESC if key in CHART_PASSES else PRODUCT_DESC.format(label=label)
        prod = _stripe("POST", "products", {"name": f"BRAIN {label} membership", "description": desc,
                                            "metadata[pass]": key, "tax_code": "txcd_10701401"})
        price = _stripe("POST", "prices", {"product": prod["id"], "unit_amount": cents, "currency": "usd",
                                           "metadata[pass]": key})
        link = _stripe("POST", "payment_links", {
            "line_items[0][price]": price["id"], "line_items[0][quantity]": 1,
            "metadata[pass]": key, "payment_intent_data[metadata][pass]": key,
            "after_completion[type]": "redirect", "after_completion[redirect][url]": base + "/analysis?paid=1",
            "custom_text[submit][message]": "One-time payment for " + label + " of membership. Does not renew. "
                                            "All sales final. Educational information service, not financial advice.",
        })
        links[_link_key(key)] = link["url"]
        made.append(key)
        with _auth._lock:
            _auth.save()
    if not st.get("whsec") and not os.environ.get("STRIPE_WEBHOOK_SECRET"):
        wh = _stripe("POST", "webhook_endpoints", {"url": base + "/stripe/webhook",
                                                   "enabled_events[]": ["checkout.session.completed",
                                                                        "checkout.session.async_payment_succeeded"],
                                                   "description": "BRAIN passes"})
        st["whsec"], st["webhook_id"] = wh["secret"], wh["id"]
        made.append("webhook")
        with _auth._lock:
            _auth.save()
    return f"{mode} mode ready" + (f" (created {', '.join(made)})" if made else "")


def checkout_url(key, user):
    base = link_for(key)
    if not base or not user:
        return ""
    if "/test_" in base and user.get("role") not in ("owner", "admin"):
        return ""                 # test-mode checkout is for the owner only - test cards must never unlock real accounts
    import urllib.parse as _u
    return base + ("&" if "?" in base else "?") + _u.urlencode({"client_reference_id": user["username"],
                                                                 "prefilled_email": user.get("email", "")})


def access_until(user):
    return float((user or {}).get("access_until") or 0)


def chart_until(user):
    return float((user or {}).get("chart_until") or 0)


def has_chart(user):
    """The live charts: any full pass, or a Chart Only pass."""
    return has_access(user) or bool(user and chart_until(user) > time.time())


def chart_only(user):
    """True for a member whose ONLY access is a Chart Only pass."""
    return bool(user) and not has_access(user) and chart_until(user) > time.time()


def has_access(user):
    if not user:
        return False
    if user.get("role") == "owner":
        return True
    return access_until(user) > time.time()


def fmt_until(ts):
    return dt.datetime.fromtimestamp(ts, ET).strftime("%b %d, %Y %-I:%M %p ET")


def grant_days(username, days, why="admin", field="access_until"):
    """Add days on top of any time left (or start from now). field: "access_until" (full BRAIN) or "chart_until" (Chart Only).
    Returns the user, or None."""
    with _auth._lock:
        u = _auth.DB["users"].get((username or "").lower())
        if not u:
            return None
        start = max(time.time(), float(u.get(field) or 0))
        u[field] = int(start + days * 86400)
        u.pop("reminded_for" if field == "access_until" else "chart_reminded_for", None)
        if u.get("status") == "pending":
            u["status"] = "approved"
        _auth._log(f"{'chart' if field == 'chart_until' else 'access'} +{days}d for {u['username']} ({why}) -> {fmt_until(u[field])}")
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
    if _mode() == "live" and event.get("livemode") is False:
        return "ignored test-mode event (site is live)"
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
    is_chart = key in CHART_PASSES
    field = "chart_until" if is_chart else "access_until"
    u = grant_days(username, days, why=f"stripe {key}", field=field)
    if not u:
        return "user missing"
    with _auth._lock:
        _auth.DB.setdefault("payments", []).append({"session": sid, "user": u["username"], "pass": key,
                                                   "amount": s.get("amount_total"), "ts": int(time.time())})
        del _auth.DB["payments"][:-2000]
        _auth.save()
    if is_chart:
        _auth.send_email(u["email"], "Your BRAIN Chart Only membership is active",
                         f"Hi {u['username']},\n\nThanks for joining BRAIN. Your Chart Only membership is active until "
                         f"{fmt_until(u['chart_until'])}.\n\nOpen your live charts: {_auth.public_url()}/charts\n\n"
                         "It includes the live BTC and XRP charts with the indicators, the 'What do these mean?' guide and the "
                         "chart patterns. Memberships don't renew on their own - we'll email you 2 days before it ends.\n\n"
                         "BRAIN is educational market information, not financial advice. All sales are final.\n\n- BRAIN")
        notify_owner(f"BRAIN: {u['username']} bought Chart Only",
                     f"{u['username']} ({u['email']}) bought the {label} membership (${PASSES[key][1] / 100:.2f}).\n"
                     f"Charts until {fmt_until(u['chart_until'])}.")
        return f"granted {label} to {u['username']}"
    _auth.send_email(u["email"], "Your BRAIN membership is active",
                     f"Hi {u['username']},\n\nThanks for joining BRAIN. Your {label} membership is active until "
                     f"{fmt_until(u['access_until'])}.\n\nOpen BRAIN Analysis: {_auth.public_url()}/analysis\n"
                     f"Your BRAIN Playbook (PDF guide to every screen): {_auth.public_url()}/playbook.pdf\n\n"
                     "Memberships don't renew on their own - we'll email you 2 days before it ends.\n\n"
                     "BRAIN is educational market analysis, not financial advice. All sales are final.\n\n- BRAIN")
    notify_owner(f"BRAIN: {u['username']} bought {label}",
                 f"{u['username']} ({u['email']}) bought the {label} membership (${PASSES[key][1] / 100:.2f}).\n"
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
    chart_due = []
    with _auth._lock:
        for u in _auth.DB["users"].values():
            cu = chart_until(u)
            if u.get("role") == "owner" or not cu or cu <= now or cu - now > REMIND_BEFORE_S or access_until(u) > cu:
                continue
            if u.get("chart_reminded_for") == int(cu):
                continue
            u["chart_reminded_for"] = int(cu)
            chart_due.append(dict(u))
        if chart_due:
            _auth.save()
    for u in chart_due:
        _auth.send_email(u["email"], "Your BRAIN Chart Only membership ends soon",
                         f"Hi {u['username']},\n\nYour Chart Only membership ends {fmt_until(chart_until(u))}.\n\n"
                         f"Keep your charts: {_auth.public_url()}/pricing\n\n- BRAIN")
    for u in due:
        _auth.send_email(u["email"], "Your BRAIN membership ends soon",
                         f"Hi {u['username']},\n\nYour BRAIN membership ends {fmt_until(access_until(u))}.\n\n"
                         f"Keep your access: {_auth.public_url()}/pricing\n\n- BRAIN")
    return len(due) + len(chart_due)
