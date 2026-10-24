"""BRAIN memberships - Stripe payments that unlock the live dashboard for a set number of days (added 2026-10-22).

  * 2026-10-24 (user): memberships AUTO-RENEW by default (Stripe subscriptions: every 10 / 30 / 105 days at the same price).
    Members turn auto-renew off themselves in Stripe's billing page (the "Manage membership" button on My Pass) - access
    then runs to the end of the time already paid for. Each renewal (Stripe invoice.paid) adds the plan's days.

  * passes: 10 days $65, 30 days $165, 3.5 months (105 days) $379 (30 days back to $165 on 2026-10-23, user; briefly $160) - one-time, never auto-renew
  * CHART ONLY (2026-10-23): 3.5 months (105 days) $35 - just the live charts for every coin (BTC, ETH, SOL, XRP, DOGE, BNB, HYPE, NEAR) with the indicators, the "What do these
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
    "30d": (30, 16500, "30 days"),
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
    """Stripe links are remembered per pass AND price (and billing type), so a change makes a fresh link instead of reusing
    the old one. '@sub' = the auto-renewing version (2026-10-24)."""
    return f"{key}@{PASSES[key][1]}@sub"


def webhook_secret():
    return os.environ.get("STRIPE_WEBHOOK_SECRET") or _auto().get("whsec", "")


# ------------------------------------------------------------------------------------- one-time Stripe auto-setup
# With STRIPE_SECRET_KEY set (a test key sk_test_... first, the live key later), the site creates its own three products,
# prices, payment links and the webhook endpoint once, and remembers them (per test/live mode) in the user database.
# Nothing is ever charged by this - it only creates the catalog.
WEBHOOK_EVENTS = ["checkout.session.completed", "checkout.session.async_payment_succeeded", "invoice.paid",
                  "customer.subscription.updated", "customer.subscription.deleted"]
PRODUCT_DESC = ("Access to the BRAIN live market-data dashboard for {label}, plus the BRAIN Playbook (PDF guide). "
                "Educational market analysis and information service - not financial advice. Renews automatically "
                "at the same price until you turn auto-renew off (any time, from My Pass). All sales final.")
CHART_DESC = ("BRAIN Chart Only: live charts for BTC, ETH, SOL, XRP, DOGE, BNB, HYPE and NEAR with indicators (EMA, RSI, MACD, support / resistance zones), the "
              "plain-English indicator guide and chart patterns with their track record, for 3.5 months (105 days). Does not "
              "include the BRAIN bot features. Educational market information - not financial advice. Renews automatically "
              "until you turn auto-renew off (any time, from My Pass). All sales final.")


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
                                           "recurring[interval]": "day", "recurring[interval_count]": days,
                                           "metadata[pass]": key})
        link = _stripe("POST", "payment_links", {
            "line_items[0][price]": price["id"], "line_items[0][quantity]": 1,
            "metadata[pass]": key, "subscription_data[metadata][pass]": key,
            "after_completion[type]": "redirect", "after_completion[redirect][url]": base + "/analysis?paid=1",
            "custom_text[submit][message]": "Renews automatically every " + (label if days != 105 else "105 days") + " at this price "
                                            "until you turn auto-renew off - any time, from My Pass on brainswatch.com. "
                                            "All sales final. Educational information service, not financial advice.",
        })
        st.setdefault("prices", {})[key] = price["id"]
        links[_link_key(key)] = link["url"]
        made.append(key)
        with _auth._lock:
            _auth.save()
    if not st.get("whsec") and not os.environ.get("STRIPE_WEBHOOK_SECRET"):
        wh = _stripe("POST", "webhook_endpoints", {"url": base + "/stripe/webhook",
                                                   "enabled_events[]": WEBHOOK_EVENTS,
                                                   "description": "BRAIN passes"})
        st["whsec"], st["webhook_id"] = wh["secret"], wh["id"]
        made.append("webhook")
        with _auth._lock:
            _auth.save()
    try:                                           # renewals + auto-renew on/off need these events on the endpoint
        for ep in _list("webhook_endpoints"):
            if (ep.get("url") or "").rstrip("/").endswith("/stripe/webhook") and set(WEBHOOK_EVENTS) - set(ep.get("enabled_events") or []):
                if "*" not in (ep.get("enabled_events") or []):
                    _stripe("POST", f"webhook_endpoints/{ep['id']}", {"enabled_events[]": WEBHOOK_EVENTS})
                    made.append("webhook events")
    except Exception as _we:
        print(f"[billing] webhook events update failed: {_we!r}")
    try:
        if not st.get("portal_cfg"):
            cfg = _stripe("POST", "billing_portal/configurations", {
                "business_profile[headline]": "BRAIN membership - turn auto-renew off or on, update your card, see receipts",
                "business_profile[privacy_policy_url]": base + "/terms", "business_profile[terms_of_service_url]": base + "/terms",
                "features[subscription_cancel][enabled]": "true", "features[subscription_cancel][mode]": "at_period_end",
                "features[payment_method_update][enabled]": "true", "features[invoice_history][enabled]": "true",
                "features[customer_update][enabled]": "false", "default_return_url": base + "/pricing"})
            st["portal_cfg"] = cfg["id"]
            made.append("billing page")
            with _auth._lock:
                _auth.save()
    except Exception as _pe:
        print(f"[billing] billing page setup failed: {_pe!r}")
    try:
        retired = retire_stale()
    except Exception as _re:                      # cleanup must never block checkout
        retired = []
        print(f"[billing] stale cleanup failed: {_re!r}")
    return (f"{mode} mode ready" + (f" (created {', '.join(made)})" if made else "")
            + (f" (retired old {', '.join(retired)})" if retired else ""))


def _list(path, params=None):
    """All objects from a Stripe list endpoint (follows has_more)."""
    import urllib.parse as _u
    out, after = [], None
    while True:
        q = dict(params or {}, limit=100)
        if after:
            q["starting_after"] = after
        page = _stripe("GET", path + "?" + _u.urlencode(q), None)
        out += page.get("data") or []
        if not page.get("has_more") or not out:
            return out
        after = out[-1]["id"]


def retire_stale():
    """After a price change: switch off the old BRAIN payment links and archive the old prices/products, so nobody can
    pay an old price. Only touches objects BRAIN made itself (metadata pass = one of ours). Safe to run at every start."""
    current = {k: cents for k, (_d, cents, _l) in PASSES.items()}
    stale_prices, keep_products, retired = set(), set(), []
    ours = [p for p in _list("prices", {"active": "true"}) if (p.get("metadata") or {}).get("pass") in current]

    def _ok(pr):                                  # the current price: right amount AND auto-renewing every <days> days
        k = pr["metadata"]["pass"]
        rc = pr.get("recurring") or {}
        return (pr.get("unit_amount") == current[k] and rc.get("interval") == "day"
                and int(rc.get("interval_count") or 0) == PASSES[k][0])
    for pr in ours:
        if _ok(pr):
            keep_products.add(pr.get("product"))
    for pr in ours:
        key = pr["metadata"]["pass"]
        if _ok(pr):
            continue
        stale_prices.add(pr["id"])
        _stripe("POST", f"prices/{pr['id']}", {"active": "false"})
        retired.append(f"{key} ${pr.get('unit_amount', 0) / 100:.0f}")
        prod = pr.get("product")
        if prod and prod not in keep_products:
            _stripe("POST", f"products/{prod}", {"active": "false"})
    for pl in _list("payment_links", {"active": "true"}):
        if (pl.get("metadata") or {}).get("pass") not in current:
            continue
        items = _stripe("GET", f"payment_links/{pl['id']}/line_items", None).get("data") or []
        price_ids = {((it.get("price") or {}).get("id")) for it in items}
        price_ok = any(((it.get("price") or {}).get("active")) and (it.get("price") or {}).get("unit_amount")
                       == current[pl["metadata"]["pass"]] and (it.get("price") or {}).get("recurring") for it in items)
        if (price_ids & stale_prices) or not price_ok:
            _stripe("POST", f"payment_links/{pl['id']}", {"active": "false"})
    with _auth._lock:                             # forget remembered links for old prices
        links = ((_auth.DB.get("stripe") or {}).get(_mode()) or {}).get("links") or {}
        old = [lk for lk in links if lk.partition("@")[0] in current and lk != _link_key(lk.partition("@")[0])]
        for lk in old:
            links.pop(lk, None)
        if old:
            _auth.save()
    return retired


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


# 2026-10-24 (user): the owner's own Jordan / J4 accounts always have full BRAIN access, like the owner.
COMP_ACCOUNTS = {"j44", "itsjordayer", "jordanmcontact", "j4admin"}
# kept through the 2026-10-24 cleanup with the time the admin gave them
KEEP_GIFTED = {"mogsonkalshi"}


def _comp(user):
    return bool(user) and (user.get("username") or "").lower() in COMP_ACCOUNTS


def has_access(user):
    if not user:
        return False
    if user.get("role") == "owner" or _comp(user):
        return True
    return access_until(user) > time.time()


def revoke_unpaid_once():
    """One time (2026-10-24, user): take away BRAIN and Chart Only time from every account that never paid through Stripe
    (the old startup 'grace' step had handed out free days). Comp accounts and KEEP_GIFTED keep theirs."""
    with _auth._lock:
        if _auth.DB.get("unpaid_cleanup_2026_10_24"):
            return []
        paid = {(p.get("user") or "").lower() for p in _auth.DB.get("payments", [])
                if p.get("user") and not p.get("unmatched") and str(p.get("session", "")).startswith(("cs_", "in:"))}
        gone = []
        for key, u in _auth.DB["users"].items():
            name = (u.get("username") or key).lower()
            if u.get("role") == "owner" or name in COMP_ACCOUNTS or name in KEEP_GIFTED or name in paid:
                continue
            if u.get("access_until") or u.get("chart_until"):
                u["access_until"] = 0
                u["chart_until"] = 0
                gone.append(u.get("username") or key)
        _auth.DB["unpaid_cleanup_2026_10_24"] = int(time.time())
        if gone:
            _auth._log(f"access removed (never paid via Stripe): {', '.join(gone)}")
        _auth.save()
    if gone:
        print(f"[billing] removed unpaid access from {len(gone)} account(s): {', '.join(gone)}")
    return gone


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


def _user_by(customer=None, sub=None, email=None, username=None):
    users = _auth.DB["users"].values()
    if username:
        u = _auth.DB["users"].get(username.lower())
        if u:
            return u
    for u in users:
        if (sub and u.get("stripe_sub") == sub) or (customer and u.get("stripe_customer") == customer):
            return u
    if email:
        return next((u for u in users if u.get("email") == email), None)
    return None


def _event_pass(obj):
    """Which membership an invoice / subscription / session is for: our metadata first, then the amount."""
    for md in ((obj.get("metadata") or {}),
               (((obj.get("parent") or {}).get("subscription_details") or {}).get("metadata") or {}),
               ((obj.get("subscription_details") or {}).get("metadata") or {})):
        if md.get("pass") in PASSES:
            return md["pass"]
    try:
        for ln in ((obj.get("lines") or {}).get("data") or []):
            md = ((ln.get("price") or {}).get("metadata") or {}) or ((((ln.get("pricing") or {}).get("price_details") or {}).get("metadata")) or {})
            if md.get("pass") in PASSES:
                return md["pass"]
            if (ln.get("metadata") or {}).get("pass") in PASSES:
                return ln["metadata"]["pass"]
    except Exception:
        pass
    for k in ("amount_total", "amount_paid"):
        if obj.get(k):
            return _BY_AMOUNT.get(int(obj[k]))
    return None


def _already(ref):
    with _auth._lock:
        return any(p.get("session") == ref for p in _auth.DB.setdefault("payments", []))


def _record(ref, user, key, amount, **extra):
    with _auth._lock:
        _auth.DB.setdefault("payments", []).append(dict({"session": ref, "user": user, "pass": key, "amount": amount,
                                                         "ts": int(time.time())}, **extra))
        del _auth.DB["payments"][:-2000]
        _auth.save()


def _renew_line(u, field):
    if u.get("auto_renew"):
        return (f"It renews automatically on {fmt_until(float(u.get(field) or 0))} at the same price. To turn auto-renew off, "
                f"open My Pass ({_auth.public_url()}/pricing) and tap Manage membership - any time before then.")
    return "Auto-renew is off - we'll email you 2 days before it ends."


def handle_event(event):
    """Apply one verified Stripe event. Returns a short status string (for the log)."""
    et = event.get("type")
    if et not in WEBHOOK_EVENTS:
        return "ignored " + str(et)
    if _mode() == "live" and event.get("livemode") is False:
        return "ignored test-mode event (site is live)"
    obj = (event.get("data") or {}).get("object") or {}
    # ---- auto-renew switched off / on, or the subscription ended
    if et in ("customer.subscription.updated", "customer.subscription.deleted"):
        u = _user_by(customer=obj.get("customer"), sub=obj.get("id"))
        if not u:
            return f"{et}: no matching account"
        on = et == "customer.subscription.updated" and not obj.get("cancel_at_period_end") and not obj.get("cancel_at") \
            and obj.get("status") in ("active", "trialing")
        with _auth._lock:
            was = u.get("auto_renew")
            u["auto_renew"] = bool(on)
            u["stripe_sub"] = obj.get("id") or u.get("stripe_sub")
            _auth.save()
        if was != bool(on):
            notify_owner(f"BRAIN: {u['username']} turned auto-renew {'on' if on else 'off'}",
                         f"{u['username']} ({u.get('email')}) turned auto-renew {'ON' if on else 'OFF'}.")
        return f"auto-renew {'on' if on else 'off'} for {u['username']}"
    # ---- a renewal payment (the first payment is handled by the checkout event below)
    if et == "invoice.paid":
        reason = obj.get("billing_reason")
        if reason == "subscription_create":
            return "first payment - granted at checkout"
        if reason not in ("subscription_cycle", "subscription_update", "manual"):
            return f"invoice.paid ignored ({reason})"
        ref = "in:" + str(obj.get("id"))
        if _already(ref):
            return "already applied"
        sub = obj.get("subscription") or (((obj.get("parent") or {}).get("subscription_details") or {}).get("subscription"))
        u = _user_by(customer=obj.get("customer"), sub=sub, email=(obj.get("customer_email") or "").lower())
        key = _event_pass(obj) or (u or {}).get("sub_pass")
        if not u or key not in PASSES:
            notify_owner("BRAIN: renewal needs matching", f"A renewal payment came in that BRAIN couldn't match.\n\nInvoice: {obj.get('id')}\n"
                         f"Customer: {obj.get('customer')} {obj.get('customer_email')}\nAmount: ${(obj.get('amount_paid') or 0) / 100:.2f}")
            _record(ref, (u or {}).get("username"), key, obj.get("amount_paid"), unmatched=True)
            return "renewal unmatched"
        days, _c, label = PASSES[key]
        field = "chart_until" if key in CHART_PASSES else "access_until"
        u = grant_days(u["username"], days, why=f"stripe renewal {key}", field=field)
        with _auth._lock:
            u["auto_renew"], u["sub_pass"] = True, key
            _auth.save()
        _record(ref, u["username"], key, obj.get("amount_paid"), renewal=True)
        _auth.send_email(u["email"], "Your BRAIN membership renewed",
                         f"Hi {u['username']},\n\nYour {label} membership renewed and is active until {fmt_until(float(u[field]))}.\n\n"
                         + _renew_line(u, field) + "\n\nAll sales are final.\n\n- BRAIN")
        notify_owner(f"BRAIN: {u['username']} renewed {label}", f"{u['username']} ({u['email']}) renewed {label} "
                     f"(${(obj.get('amount_paid') or 0) / 100:.2f}). Until {fmt_until(float(u[field]))}.")
        return f"renewed {label} for {u['username']}"
    # ---- checkout finished (first payment)
    s = obj
    if s.get("payment_status") != "paid":
        return "not paid yet"
    sid = s.get("id", "")
    if _already(sid):
        return "already applied"
    key = _event_pass(s)
    username = (s.get("client_reference_id") or "").strip()
    email = ((s.get("customer_details") or {}).get("email") or "").strip().lower()
    if not username and email:
        username = next((u["username"] for u in _auth.DB["users"].values() if u.get("email") == email), "")
    if not key or not username:
        print(f"[billing] PAID but could not match: session {sid} pass={key} user={username!r} email={email!r}")
        _record(sid, username, key, s.get("amount_total"), unmatched=True, email=email)
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
        if s.get("customer"):
            u["stripe_customer"] = s["customer"]
        if s.get("mode") == "subscription" and s.get("subscription"):
            u["stripe_sub"], u["auto_renew"], u["sub_pass"] = s["subscription"], True, key
        _auth.save()
    _record(sid, u["username"], key, s.get("amount_total"))
    if is_chart:
        _auth.send_email(u["email"], "Your BRAIN Chart Only membership is active",
                         f"Hi {u['username']},\n\nThanks for joining BRAIN. Your Chart Only membership is active until "
                         f"{fmt_until(u['chart_until'])}.\n\nOpen your live charts: {_auth.public_url()}/charts\n\n"
                         "It includes the live charts for every coin with the indicators, the 'What do these mean?' guide and the "
                         "chart patterns.\n\n" + _renew_line(u, "chart_until") + "\n\n"
                         "BRAIN is educational market information, not financial advice. All sales are final.\n\n- BRAIN")
        notify_owner(f"BRAIN: {u['username']} bought Chart Only",
                     f"{u['username']} ({u['email']}) bought the {label} membership (${PASSES[key][1] / 100:.2f}).\n"
                     f"Charts until {fmt_until(u['chart_until'])}.")
        return f"granted {label} to {u['username']}"
    _auth.send_email(u["email"], "Your BRAIN membership is active",
                     f"Hi {u['username']},\n\nThanks for joining BRAIN. Your {label} membership is active until "
                     f"{fmt_until(u['access_until'])}.\n\nOpen BRAIN Analysis: {_auth.public_url()}/analysis\n"
                     f"Your BRAIN Playbook (PDF guide to every screen): {_auth.public_url()}/playbook.pdf\n\n"
                     + _renew_line(u, "access_until") + "\n\n"
                     "BRAIN is educational market analysis, not financial advice. All sales are final.\n\n- BRAIN")
    notify_owner(f"BRAIN: {u['username']} bought {label}",
                 f"{u['username']} ({u['email']}) bought the {label} membership (${PASSES[key][1] / 100:.2f}).\n"
                 f"Access until {fmt_until(u['access_until'])}.")
    return f"granted {label} to {u['username']}"


def portal_url(user):
    """A one-time link to Stripe's billing page for this member (turn auto-renew off/on, card, receipts), or ''."""
    cust = (user or {}).get("stripe_customer")
    if not cust or not _mode():
        return ""
    base = (_auth.public_url() or "https://brainswatch.com").rstrip("/")
    data = {"customer": cust, "return_url": base + "/pricing"}
    cfg = _auto().get("portal_cfg")
    if cfg:
        data["configuration"] = cfg
    return _stripe("POST", "billing_portal/sessions", data).get("url", "")


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
        if u.get("auto_renew"):
            continue                              # renews on its own; the renewal email confirms it
        _auth.send_email(u["email"], "Your BRAIN Chart Only membership ends soon",
                         f"Hi {u['username']},\n\nYour Chart Only membership ends {fmt_until(chart_until(u))}.\n\n"
                         f"Keep your charts: {_auth.public_url()}/pricing\n\n- BRAIN")
    for u in due:
        if u.get("auto_renew"):
            _auth.send_email(u["email"], "Your BRAIN membership renews soon",
                             f"Hi {u['username']},\n\nHeads-up: your BRAIN membership renews automatically on "
                             f"{fmt_until(access_until(u))} at the same price.\n\nNothing to do if you'd like to keep it. To turn "
                             f"auto-renew off, open My Pass ({_auth.public_url()}/pricing) and tap Manage membership.\n\n- BRAIN")
            continue
        _auth.send_email(u["email"], "Your BRAIN membership ends soon",
                         f"Hi {u['username']},\n\nYour BRAIN membership ends {fmt_until(access_until(u))}.\n\n"
                         f"Keep your access: {_auth.public_url()}/pricing\n\n- BRAIN")
    return len(due) + len(chart_due)
