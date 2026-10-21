"""Link-preview card for BRAIN (added 2026-10-20).

When someone pastes the BRAIN link into iMessage, Discord, Slack, X etc., those apps read the page's Open Graph tags and show
this picture: the island night scene, BRAIN, and LIVE numbers - BTC and XRP prices, their 24h change, and what Kalshi is
paying right now on each 15-minute round (UP % / DOWN %, the round's line and time left), plus the sealed-call record.
Nothing owner-only is ever drawn here (no trading controls, balances, positions or calls in progress).

render_png(data) -> PNG bytes, 1200x630. Fonts: the site's own Fraunces + Nunito, fetched once from Google Fonts into
DATA_DIR/fonts (background thread); until they arrive it falls back to DejaVu, then Pillow's built-in font.
"""
import io
import os
import re
import threading
import urllib.request

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1200, 630
HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(os.environ.get("DATA_DIR") or HERE, "fonts")

CREAM = (251, 244, 236)
TEXT = (238, 226, 215)
MUTE = (188, 170, 161)
TAN = (220, 187, 145)
ROSE = (233, 165, 187)
GOLD = (229, 184, 92)
UP = (61, 214, 156)
DOWN = (240, 84, 84)

# file name -> (family query, italic, weight)
_FONTS = {
    "fraunces-800.ttf": ("Fraunces", False, 800),
    "fraunces-600i.ttf": ("Fraunces", True, 600),
    "nunito-700.ttf": ("Nunito", False, 700),
    "nunito-900.ttf": ("Nunito", False, 900),
}
_fetch_started = [False]
_font_cache = {}


def _fetch_fonts():
    """Ask Google Fonts for plain TTF files (an old-style User-Agent gets truetype URLs) and save them."""
    try:
        os.makedirs(FONT_DIR, exist_ok=True)
        css_url = ("https://fonts.googleapis.com/css2?family=Fraunces:ital,wght@0,800;1,600"
                   "&family=Nunito:wght@700;900&display=swap")
        req = urllib.request.Request(css_url, headers={"User-Agent": "Mozilla/4.0 (compatible; MSIE 6.0)"})
        css = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "replace")
        for block in re.findall(r"@font-face\s*{(.*?)}", css, re.S):
            fam = re.search(r"font-family:\s*'([^']+)'", block)
            sty = re.search(r"font-style:\s*(\w+)", block)
            wgt = re.search(r"font-weight:\s*(\d+)", block)
            src = re.search(r"url\((https://[^)]+)\)", block)
            if not (fam and sty and wgt and src):
                continue
            for fname, (f, ital, w) in _FONTS.items():
                if f == fam.group(1) and (sty.group(1) == "italic") == ital and int(wgt.group(1)) == w:
                    dest = os.path.join(FONT_DIR, fname)
                    if not os.path.isfile(dest):
                        data = urllib.request.urlopen(src.group(1), timeout=20).read()
                        with open(dest + ".part", "wb") as fh:
                            fh.write(data)
                        os.replace(dest + ".part", dest)
        _font_cache.clear()
    except Exception as e:
        print(f"[og] font fetch failed: {e!r}")


def _font(fname, size):
    key = (fname, size)
    if key in _font_cache:
        return _font_cache[key]
    fp = os.path.join(FONT_DIR, fname)
    f = None
    if os.path.isfile(fp):
        try:
            f = ImageFont.truetype(fp, size)
        except Exception:
            f = None
    if f is None:
        if not _fetch_started[0]:
            _fetch_started[0] = True
            threading.Thread(target=_fetch_fonts, daemon=True).start()
        serif = fname.startswith("fraunces")
        for cand in (("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf" if serif else
                      "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),):
            if os.path.isfile(cand):
                f = ImageFont.truetype(cand, int(size * 0.9))
                break
        if f is None:
            try:
                f = ImageFont.load_default(size=size)
            except TypeError:
                f = ImageFont.load_default()
        return f                                   # don't cache a fallback - the real font may arrive any moment
    _font_cache[key] = f
    return f


_bg_cache = {}


def _background():
    if "img" in _bg_cache:
        return _bg_cache["img"].copy()
    src = None
    for name in ("hero.jpg", "hero.webp"):
        p = os.path.join(HERE, "static", name)
        if os.path.isfile(p):
            try:
                src = Image.open(p).convert("RGB")
                break
            except Exception:
                src = None
    if src is None:
        img = Image.new("RGB", (W, H), (33, 27, 30))
    else:
        # cover-crop to 1200x630, focus a little below centre like the welcome page (object-position 50% 72%)
        sw, sh = src.size
        scale = max(W / sw, H / sh)
        nw, nh = int(sw * scale + 0.5), int(sh * scale + 0.5)
        src = src.resize((nw, nh), Image.LANCZOS)
        left = (nw - W) // 2
        top = int((nh - H) * 0.72)
        img = src.crop((left, top, left + W, top + H))
    # darken: strong on the left (text side) and along the bottom, lighter top-right so the palms still show
    shade = Image.new("L", (W, H))
    px = shade.load()
    for y in range(H):
        for x in range(0, W, 4):
            a = 120 + int(80 * (1 - x / W)) + int(70 * max(0, (y - H * 0.55) / (H * 0.45)))
            a = min(225, a)
            for k in range(4):
                if x + k < W:
                    px[x + k, y] = a
    dark = Image.new("RGB", (W, H), (14, 11, 13))
    img = Image.composite(dark, img, shade)
    _bg_cache["img"] = img
    return img.copy()


def _money(v, asset):
    if v is None:
        return "--"
    if asset == "XRP" or v < 10:
        return f"${v:,.4f}"
    return f"${v:,.2f}"


def _panel(base, box, radius=26, fill=(36, 28, 32, 205), outline=(240, 214, 200, 46)):
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=2)
    base.alpha_composite(layer)


def _text_w(d, s, f):
    try:
        return d.textlength(s, font=f)
    except Exception:
        return len(s) * 10


def render_png(data):
    """data = {"BTC": {...}, "XRP": {...}, "record": {...} or None, "site": "night.up.railway.app"}
    each coin: price, chg24 (percent), kalshi_up (0-1 or None), line, seconds_left."""
    img = _background().convert("RGBA")
    d = ImageDraw.Draw(img)

    # ---- title block
    title_f = _font("fraunces-800.ttf", 92)
    d.text((58, 40), "BRAIN", font=title_f, fill=CREAM)
    tag_f = _font("fraunces-600i.ttf", 30)
    d.text((62, 146), "Live crypto odds on Kalshi, every 15 minutes", font=tag_f, fill=TAN)
    live_f = _font("nunito-900.ttf", 22)
    lx = 58 + _text_w(d, "BRAIN", title_f) + 22
    d.ellipse((lx, 84, lx + 14, 98), fill=ROSE)
    d.text((lx + 22, 77), "LIVE", font=live_f, fill=ROSE)

    # ---- one panel per coin
    lab_f = _font("nunito-900.ttf", 24)
    coin_f = _font("fraunces-800.ttf", 40)
    price_f = _font("fraunces-800.ttf", 64)
    small_f = _font("nunito-700.ttf", 24)
    odds_f = _font("nunito-900.ttf", 30)
    y0, ph, pw, gap = 214, 300, 525, 34
    for i, asset in enumerate(("BTC", "XRP")):
        c = data.get(asset) or {}
        x0 = 58 + i * (pw + gap)
        _panel(img, (x0, y0, x0 + pw, y0 + ph))
        d = ImageDraw.Draw(img)
        d.text((x0 + 30, y0 + 22), asset, font=coin_f, fill=GOLD if asset == "BTC" else TAN)
        chg = c.get("chg24")
        if chg is not None:
            s = f"{'+' if chg >= 0 else ''}{chg:.2f}% 24h"
            d.text((x0 + pw - 30 - _text_w(d, s, small_f), y0 + 34), s, font=small_f, fill=UP if chg >= 0 else DOWN)
        d.text((x0 + 28, y0 + 78), _money(c.get("price"), asset), font=price_f, fill=CREAM)

        k = c.get("kalshi_up")
        d.text((x0 + 30, y0 + 168), "KALSHI 15-MIN ROUND", font=lab_f, fill=MUTE)
        if k is not None:
            up = max(0, min(100, round(k * 100)))
            dn = 100 - up
            bx0, bx1, by = x0 + 30, x0 + pw - 30, y0 + 248
            d.rounded_rectangle((bx0, by, bx1, by + 14), radius=7, fill=DOWN)
            if up > 0:
                d.rounded_rectangle((bx0, by, bx0 + max(14, int((bx1 - bx0) * up / 100)), by + 14), radius=7, fill=UP)
            d.text((x0 + 30, y0 + 204), f"UP {up}%", font=odds_f, fill=UP)
            s = f"{dn}% DOWN"
            d.text((x0 + pw - 30 - _text_w(d, s, odds_f), y0 + 204), s, font=odds_f, fill=DOWN)
        else:
            d.text((x0 + 30, y0 + 204), "between rounds", font=odds_f, fill=MUTE)
        line, secs = c.get("line"), c.get("seconds_left")
        bits = []
        if line:
            bits.append("line " + _money(line, asset))
        if secs is not None and secs >= 0:
            bits.append(f"{int(secs) // 60}:{int(secs) % 60:02d} left")
        if bits:
            d.text((x0 + 30, y0 + 270), "  ·  ".join(bits), font=_font("nunito-700.ttf", 20), fill=MUTE)

    # ---- footer
    d = ImageDraw.Draw(img)
    foot_f = _font("nunito-900.ttf", 26)
    rec = data.get("record")
    if rec and rec.get("n"):
        s = f"Sealed calls: {rec['pct']:.0f}% right over {rec['n']:,} rounds"
        d.text((60, 552), s, font=foot_f, fill=CREAM)
    site = data.get("site") or ""
    if site:
        d.text((W - 60 - _text_w(d, site, foot_f), 552), site, font=foot_f, fill=ROSE)

    out = io.BytesIO()
    img.convert("RGB").save(out, "PNG", optimize=True)
    return out.getvalue()
