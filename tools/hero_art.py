"""BRAIN hero art: the brain at a trading desk, looking out over a Puerto Rico forest cove at dusk.
Rendered with PIL at 2x and downscaled. Anime-background approach: layered silhouettes with atmospheric haze,
soft glows, rim light, dense foliage."""
import math
import random
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

W0, H0 = 1600, 1200
S = 2
W, H = W0 * S, H0 * S
rng = random.Random(7)


def hexc(h, a=255):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


def mix(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(len(c1)))


def vgrad(w, h, stops):
    """stops: [(pos 0..1, '#hex')] -> RGBA image"""
    ys = np.linspace(0, 1, h)
    out = np.zeros((h, w, 4), dtype=np.float32)
    ps = [p for p, _ in stops]
    cs = [np.array(hexc(c), dtype=np.float32) for _, c in stops]
    for ch in range(4):
        col = np.interp(ys, ps, [c[ch] for c in cs])
        out[:, :, ch] = col[:, None]
    return Image.fromarray(out.astype(np.uint8), "RGBA")


def layer():
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))


def glow(img, radius):
    return img.filter(ImageFilter.GaussianBlur(radius * S))


def comp(base, top):
    base.alpha_composite(top)


def ridge_points(y0, amp, seeds, x0=0, x1=None, step=8):
    x1 = W if x1 is None else x1
    pts = []
    for x in range(x0, x1 + step, step):
        t = x / W
        y = y0
        for (a, f, ph) in seeds:
            y += amp * a * math.sin(t * f * math.tau + ph)
        pts.append((x, y))
    return pts


def fill_ridge(img, pts, color, bottom=None):
    bottom = H if bottom is None else bottom
    d = ImageDraw.Draw(img)
    d.polygon(pts + [(pts[-1][0], bottom), (pts[0][0], bottom)], fill=color)


# ------------------------------------------------------------------------------------------------ sky
def sky():
    img = vgrad(W, H, [(0.0, "#0b141d"), (0.14, "#1b2e3d"), (0.25, "#4c5966"), (0.33, "#a57a80"),
                       (0.40, "#e2a588"), (0.46, "#f6cf9c")])
    # sun glow low over the cove (slightly right of center)
    sx, sy = int(W * 0.58), int(H * 0.432)
    g = layer()
    d = ImageDraw.Draw(g)
    for r, a in ((900, 40), (560, 60), (320, 90), (170, 140)):
        d.ellipse([sx - r * S / 2, sy - r * S / 2, sx + r * S / 2, sy + r * S / 2], fill=(255, 214, 160, a))
    comp(img, glow(g, 60))
    d = ImageDraw.Draw(img)
    r = 46 * S
    d.ellipse([sx - r, sy - r, sx + r, sy + r], fill=hexc("#fff1d2"))
    # stars in the upper sky
    st = layer()
    d = ImageDraw.Draw(st)
    for _ in range(170):
        x, y = rng.uniform(0, W), rng.uniform(0, H * 0.24)
        a = int(255 * (1 - y / (H * 0.27)) * rng.uniform(0.35, 1))
        rr = rng.choice([1, 1, 1.5, 2]) * S
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=(255, 246, 230, max(0, a)))
    comp(img, st)
    # soft clouds lit from below
    cl = layer()
    d = ImageDraw.Draw(cl)
    for cx, cy, w_, h_ in ((0.18, 0.25, 520, 60), (0.36, 0.30, 420, 40), (0.80, 0.26, 560, 56), (0.66, 0.335, 380, 30),
                           (0.10, 0.34, 300, 26), (0.92, 0.355, 260, 22)):
        x, y = cx * W, cy * H
        for k in range(14):
            ox, oy = rng.uniform(-w_ / 2, w_ / 2) * S, rng.uniform(-h_ / 3, h_ / 3) * S
            rw, rh = rng.uniform(0.25, 0.5) * w_ * S, rng.uniform(0.5, 1.0) * h_ * S
            d.ellipse([x + ox - rw / 2, y + oy - rh / 2, x + ox + rw / 2, y + oy + rh / 2], fill=(238, 170, 160, 70))
    cl = glow(cl, 10)
    comp(img, cl)
    rim = layer()
    d = ImageDraw.Draw(rim)
    for cx, cy, w_ in ((0.18, 0.262, 420), (0.80, 0.272, 460), (0.36, 0.308, 300)):
        d.ellipse([cx * W - w_ * S / 2, cy * H, cx * W + w_ * S / 2, cy * H + 10 * S], fill=(255, 214, 180, 120))
    comp(img, glow(rim, 6))
    return img


# ------------------------------------------------------------------------------------------------ land + water
def mountains(img):
    hz = H * 0.445
    # far ridge (hazy rose-grey)
    p = ridge_points(hz - 150 * S, 60 * S, [(1, 1.3, 0.4), (0.5, 3.7, 1.1), (0.22, 9, 2.0)])
    l = layer(); fill_ridge(l, p, hexc("#7d8288")); comp(img, l)
    mist = layer(); d = ImageDraw.Draw(mist)
    d.rectangle([0, hz - 120 * S, W, hz - 40 * S], fill=(240, 196, 180, 90)); comp(img, glow(mist, 24))
    # mid ridge (El Yunque style peaks, cooler)
    p = ridge_points(hz - 70 * S, 70 * S, [(1, 0.9, 2.2), (0.6, 2.6, 0.3), (0.25, 7.5, 1.7), (0.1, 19, 0.2)])
    l = layer(); fill_ridge(l, p, hexc("#3f5058")); comp(img, l)
    mist = layer(); d = ImageDraw.Draw(mist)
    d.rectangle([0, hz - 40 * S, W, hz + 10 * S], fill=(236, 186, 176, 110)); comp(img, glow(mist, 18))
    return hz


def canopy(img, pts, base_col, hi_col, density=1.0, size=(18, 42), bottom=None):
    """dense tree crowns along a ridge: many small overlapping crowns, thin warm rim light on the sun side"""
    l = layer(); d = ImageDraw.Draw(l)
    fill_ridge(l, pts, base_col, bottom)
    hl = layer(); dh = ImageDraw.Draw(hl)
    for (x, y) in pts:
        for _ in range(3):
            r = rng.uniform(size[0] * 0.45, size[1] * 0.55) * S
            ox = rng.uniform(-r * 1.5, r * 1.5)
            cy = y + rng.uniform(-r * 0.6, r * 0.9)
            shade = rng.uniform(-10, 8)
            col = tuple(max(0, min(255, int(c + shade))) for c in base_col[:3]) + (255,)
            d.ellipse([x + ox - r, cy - r, x + ox + r, cy + r], fill=col)
            if rng.random() < 0.3:
                dh.arc([x + ox - r, cy - r, x + ox + r, cy + r], 230, 320, fill=hi_col[:3] + (70,), width=max(1, int(1.1 * S)))
    comp(img, l)
    comp(img, hl)


def water(img, hz):
    top = int(hz)
    wimg = vgrad(W, H - top, [(0, "#f1c49e"), (0.16, "#b98a88"), (0.5, "#30505a"), (1, "#0e1d24")])
    img.alpha_composite(wimg, (0, top))
    # sun glitter path
    g = layer(); d = ImageDraw.Draw(g)
    sx = W * 0.58
    for i in range(160):
        y = top + (i / 160) ** 1.5 * (H * 0.2)
        spread = 18 * S + (y - top) * 0.35
        x = sx + rng.uniform(-spread, spread)
        w_ = rng.uniform(10, 46) * S * (1 - (y - top) / (H * 0.4))
        a = int(220 * (1 - (y - top) / (H * 0.3)))
        d.rounded_rectangle([x - w_ / 2, y, x + w_ / 2, y + 2.2 * S], 2 * S, fill=(255, 233, 196, max(0, a)))
    comp(img, glow(g, 1))
    # long soft ripples
    r = layer(); d = ImageDraw.Draw(r)
    for i in range(60):
        y = top + rng.uniform(4, H * 0.3) * 1.0
        x = rng.uniform(0, W)
        w_ = rng.uniform(80, 360) * S
        d.line([x - w_ / 2, y, x + w_ / 2, y], fill=(255, 220, 210, 26), width=2 * S)
    comp(img, r)


def palm(d, x, y, h, lean, frond_col, trunk_col, rim_col=None, scale=1.0):
    """coconut palm: tapered curved trunk with ring marks, arching fronds whose leaflets hang with gravity"""
    pts = []
    for i in range(40):
        t = i / 39
        pts.append((x + lean * h * (t ** 1.7), y - h * t))
    for i in range(len(pts) - 1):
        wdt = (13 - 7 * i / 39) * S * scale * (h / (330 * S)) ** 0.6
        d.line([pts[i], pts[i + 1]], fill=trunk_col, width=max(2, int(wdt)))
    tx, ty = pts[-1]
    n = 11
    for k in range(n):
        side = -1 if k < n / 2 else 1
        base = -math.pi / 2 + (k - (n - 1) / 2) * 0.36 + rng.uniform(-0.08, 0.08)
        L = h * rng.uniform(0.30, 0.40)
        spine = []
        for i in range(26):
            t = i / 25
            a = base + side * 1.05 * t * t
            px = tx + math.cos(base) * L * t * 0.85 + side * L * 0.25 * t * t
            py = ty + math.sin(base) * L * t * 0.7 + L * 0.75 * t * t * (0.6 + abs(math.cos(base)))
            spine.append((px, py))
        for i in range(2, len(spine)):
            x0, y0 = spine[i - 1]; x1, y1 = spine[i]
            dx, dy = x1 - x0, y1 - y0
            nrm = math.hypot(dx, dy) or 1
            tx_, ty_ = dx / nrm, dy / nrm
            ln = L * 0.17 * math.sin(math.pi * min(1, i / 25 + 0.08))
            for sgn in (1, -1):
                nx, ny = -ty_ * sgn, tx_ * sgn
                vx, vy = nx * 0.55 + tx_ * 0.45, ny * 0.55 + ty_ * 0.45 + 0.9
                vn = math.hypot(vx, vy)
                ex, ey = x1 + vx / vn * ln, y1 + vy / vn * ln
                d.line([(x1, y1), (ex, ey)], fill=frond_col, width=max(2, int(2.2 * S * scale)))
        d.line(spine, fill=frond_col, width=max(2, int(2.6 * S * scale)))
    d.ellipse([tx - 8 * S, ty - 5 * S, tx + 8 * S, ty + 9 * S], fill=trunk_col)


def forest(img, hz):
    # left headland and right headland framing the cove
    left = [(x, hz - 10 * S - 160 * S * max(0.0, 1 - x / (W * 0.42)) ** 1.4 + 18 * S * math.sin(x / (40 * S))) for x in range(0, int(W * 0.46), 10)]
    right = [(x, hz - 10 * S - 190 * S * max(0.0, (x - W * 0.66) / (W * 0.34)) ** 1.2 + 16 * S * math.sin(x / (37 * S)))
             for x in range(int(W * 0.64), W + 10, 10)]
    canopy(img, left + [(W * 0.46, hz + 30 * S)], hexc("#22393a"), (232, 176, 140, 150), size=(14, 30), bottom=hz + 60 * S)
    canopy(img, [(W * 0.62, hz + 30 * S)] + right, hexc("#1f3536"), (240, 184, 146, 160), size=(16, 34), bottom=hz + 60 * S)
    # rim haze where land meets water
    m = layer(); d = ImageDraw.Draw(m)
    d.rectangle([0, hz + 6 * S, W, hz + 26 * S], fill=(246, 200, 170, 70)); comp(img, glow(m, 10))
    # palms on both headlands, back to front
    p = layer(); d = ImageDraw.Draw(p)
    for (x, y, h, lean) in ((0.06, 0.02, 300, 0.18), (0.14, 0.04, 360, -0.12), (0.24, 0.05, 280, 0.2), (0.33, 0.06, 230, 0.26),
                            (0.70, 0.04, 260, -0.22), (0.80, 0.02, 340, -0.1), (0.90, 0.01, 380, 0.12), (0.97, 0.03, 300, -0.15)):
        palm(d, x * W, hz + y * H, h * S, lean, hexc("#16292a"), hexc("#2c2422"))
    comp(img, p)
    # sun rim light on palm crowns facing the sun
    return img


def details(img, hz):
    """far-shore village lights, a sailboat at anchor, soft sun rays"""
    d = ImageDraw.Draw(img)
    lt = layer(); dl = ImageDraw.Draw(lt)
    for _ in range(38):
        x = rng.uniform(W * 0.38, W * 0.62)
        y = hz - rng.uniform(2, 26) * S
        r_ = rng.uniform(1.2, 2.4) * S
        dl.ellipse([x - r_, y - r_, x + r_, y + r_], fill=(255, 214, 150, 230))
    comp(img, glow(lt, 2)); comp(img, lt)
    # sailboat
    bx, by = W * 0.44, hz + 46 * S
    d.polygon([(bx - 34 * S, by), (bx + 34 * S, by), (bx + 24 * S, by + 10 * S), (bx - 26 * S, by + 10 * S)], fill=hexc("#1c2a30"))
    d.line([(bx, by), (bx, by - 70 * S)], fill=hexc("#1c2a30"), width=int(3 * S))
    d.polygon([(bx + 2 * S, by - 66 * S), (bx + 2 * S, by - 6 * S), (bx + 36 * S, by - 8 * S)], fill=hexc("#e9c6b0"))
    d.polygon([(bx - 2 * S, by - 58 * S), (bx - 2 * S, by - 8 * S), (bx - 24 * S, by - 9 * S)], fill=hexc("#d7a99a"))
    rf = layer(); dr = ImageDraw.Draw(rf)
    for i in range(6):
        dr.line([(bx - 20 * S + rng.uniform(-6, 6) * S, by + 14 * S + i * 6 * S), (bx + 20 * S, by + 14 * S + i * 6 * S)],
                fill=(233, 198, 176, 60 - i * 9), width=int(2 * S))
    comp(img, rf)
    # sun rays fanning up from behind the ridge
    ry = layer(); dy = ImageDraw.Draw(ry)
    sx, sy = W * 0.58, H * 0.432
    for k in range(9):
        a = math.radians(-160 + k * 17 + rng.uniform(-4, 4))
        L = rng.uniform(500, 900) * S
        wdt = rng.uniform(0.025, 0.05)
        p1 = (sx + math.cos(a - wdt) * L, sy + math.sin(a - wdt) * L)
        p2 = (sx + math.cos(a + wdt) * L, sy + math.sin(a + wdt) * L)
        dy.polygon([(sx, sy), p1, p2], fill=(255, 220, 180, 26))
    comp(img, glow(ry, 18))


def palm_reflections(img, hz):
    r = layer(); d = ImageDraw.Draw(r)
    for x in (0.06, 0.14, 0.24, 0.33, 0.70, 0.80, 0.90, 0.97):
        xx = x * W
        for i in range(10):
            y = hz + 34 * S + i * 9 * S
            d.line([(xx - rng.uniform(4, 14) * S, y), (xx + rng.uniform(4, 14) * S, y)], fill=(10, 24, 26, 120 - i * 10), width=int(3 * S))
    comp(img, r)


def cove(out_path):
    img = sky()
    hz = mountains(img)
    water(img, hz)
    forest(img, hz)
    palm_reflections(img, hz)
    details(img, hz)
    import interior  # tools/interior.py - run from the tools folder: python hero_art.py ../static/hero.jpg
    interior.draw(img, hz)
    img = img.resize((W0, H0), Image.LANCZOS).convert("RGB")
    img.save(out_path, quality=86, optimize=True, progressive=True)
    img.save(out_path.rsplit(".", 1)[0] + ".webp", quality=82, method=6)


if __name__ == "__main__":
    cove(sys.argv[1])
