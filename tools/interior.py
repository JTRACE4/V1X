"""The room: window frame, hanging plants, desk, three chart monitors, the brain in its chair, glow + neural threads."""
import math
import random
from PIL import Image, ImageDraw, ImageFilter
from hero_art import W, H, S, hexc, layer, glow, comp, vgrad

rng = random.Random(11)
UP, DOWN, GOLD, ROSE, TAN, CREAM = hexc("#43cdb7"), hexc("#e8798f"), hexc("#e5b85c"), hexc("#e9a5bb"), hexc("#dcbb91"), hexc("#fbf4ec")


def rr(d, box, r, **k):
    d.rounded_rectangle([int(v) for v in box], int(r), **k)


def window_frame(img):
    # wall around a wide window opening; opening = x 6%..94%, y 4%..63%
    x0, x1, y0, y1 = W * 0.06, W * 0.94, H * 0.04, H * 0.66
    wall = vgrad(W, H, [(0, "#1b1618"), (0.6, "#2a2124"), (1, "#1a1416")])
    mask = Image.new("L", (W, H), 255)
    ImageDraw.Draw(mask).rounded_rectangle([int(x0), int(y0), int(x1), int(y1)], int(26 * S), fill=0)
    img.paste(wall, (0, 0), mask)
    d = ImageDraw.Draw(img)
    # frame + mullions (dark wood)
    fr = hexc("#3a2c27")
    rr(d, [x0 - 10 * S, y0 - 10 * S, x1 + 10 * S, y1 + 10 * S], 32 * S, outline=fr, width=int(12 * S))
    for fx in (0.335, 0.665):
        xx = x0 + (x1 - x0) * fx
        d.rectangle([xx - 5 * S, y0, xx + 5 * S, y1], fill=fr)
    d.rectangle([x0, y0 + (y1 - y0) * 0.30 - 4 * S, x1, y0 + (y1 - y0) * 0.30 + 4 * S], fill=fr)
    # warm dusk light catching the frame edges
    hi = layer(); dh = ImageDraw.Draw(hi)
    rr(dh, [x0 - 4 * S, y0 - 4 * S, x1 + 4 * S, y1 + 4 * S], 30 * S, outline=(255, 196, 150, 70), width=int(2 * S))
    comp(img, hi)
    # sill
    d.rectangle([x0 - 30 * S, y1 + 4 * S, x1 + 30 * S, y1 + 18 * S], fill=hexc("#4a3830"))
    d.rectangle([x0 - 30 * S, y1 + 4 * S, x1 + 30 * S, y1 + 7 * S], fill=hexc("#7b5e4c"))
    return x0, x1, y0, y1


def hanging_plants(img, x0, x1, y0):
    """pothos vines trailing from the top corners - dark silhouettes with a rim of window light"""
    l = layer(); d = ImageDraw.Draw(l)
    for cx, dirx in ((x0 + 60 * S, 1), (x1 - 60 * S, -1)):
        d.ellipse([cx - 60 * S, y0 - 10 * S, cx + 60 * S, y0 + 50 * S], fill=hexc("#2b2321"))   # pot
        for v in range(7):
            px, py = cx + rng.uniform(-40, 40) * S, y0 + 30 * S
            length = rng.uniform(180, 420) * S
            sway = rng.uniform(10, 50) * S * dirx
            prev = (px, py)
            for i in range(1, 40):
                t = i / 39
                x = px + sway * math.sin(t * 2.2) + dirx * t * 30 * S
                y = py + length * t
                d.line([prev, (x, y)], fill=hexc("#1a2b22"), width=int(2 * S))
                if i % 3 == 0:
                    side = 1 if i % 6 == 0 else -1
                    lx, ly = x + side * 14 * S, y + 4 * S
                    leaf = [(x, y), (lx - side * 4 * S, ly - 10 * S), (lx + side * 8 * S, ly), (lx - side * 2 * S, ly + 10 * S)]
                    d.polygon(leaf, fill=hexc("#1f3a2b"))
                prev = (x, y)
    comp(img, l)


def candle_chart(d, box, n=26, seed=1, trend=0.6):
    x0, y0, x1, y1 = box
    r = random.Random(seed)
    vals, v = [], 0.0
    for i in range(n):
        o = v
        v = v + r.gauss(trend * 0.15, 1)
        hi, lo = max(o, v) + abs(r.gauss(0, 0.5)), min(o, v) - abs(r.gauss(0, 0.5))
        vals.append((o, v, hi, lo))
    mn, mx = min(x[3] for x in vals), max(x[2] for x in vals)
    sy = lambda val: y1 - (val - mn) / (mx - mn + 1e-9) * (y1 - y0)
    cw = (x1 - x0) / n
    for i, (o, c, hi, lo) in enumerate(vals):
        cx = x0 + cw * (i + 0.5)
        col = UP if c >= o else DOWN
        d.line([(cx, sy(hi)), (cx, sy(lo))], fill=col, width=max(1, int(1.2 * S)))
        top, bot = sy(max(o, c)), sy(min(o, c))
        d.rectangle([cx - cw * 0.32, top, cx + cw * 0.32, max(bot, top + 2 * S)], fill=col)
    return sy, vals


def screen(img, box, kind, seed):
    """one monitor: bezel, screen with a chart, stand"""
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = box
    # stand
    cx = (x0 + x1) / 2
    d.rectangle([cx - 10 * S, y1, cx + 10 * S, y1 + 42 * S], fill=hexc("#17121a"))
    rr(d, [cx - 60 * S, y1 + 38 * S, cx + 60 * S, y1 + 50 * S], 6 * S, fill=hexc("#17121a"))
    # bezel + screen
    rr(d, [x0 - 8 * S, y0 - 8 * S, x1 + 8 * S, y1 + 8 * S], 12 * S, fill=hexc("#0d0b10"))
    scr = vgrad(int(x1 - x0), int(y1 - y0), [(0, "#151c24"), (1, "#0f1218")])
    img.alpha_composite(scr, (int(x0), int(y0)))
    d = ImageDraw.Draw(img)
    pad = 14 * S
    gx0, gy0, gx1, gy1 = x0 + pad, y0 + pad + 14 * S, x1 - pad, y1 - pad
    # faint grid
    for i in range(1, 5):
        yy = gy0 + (gy1 - gy0) * i / 5
        d.line([(gx0, yy), (gx1, yy)], fill=(255, 255, 255, 14), width=1)
    # header strip
    d.rectangle([x0 + pad, y0 + pad - 2 * S, x0 + pad + 70 * S, y0 + pad + 4 * S], fill=ROSE[:3] + (200,))
    d.rectangle([x1 - pad - 40 * S, y0 + pad - 2 * S, x1 - pad, y0 + pad + 4 * S], fill=UP[:3] + (180,))
    if kind == "candles":
        sy, vals = candle_chart(d, (gx0, gy0, gx1, gy1), n=30, seed=seed, trend=0.9)
        # the round's line (dashed cream) and the 60s average (gold)
        ly = sy((vals[0][0] + vals[-1][1]) / 2 - 0.4)
        for xx in range(int(gx0), int(gx1), int(14 * S)):
            d.line([(xx, ly), (xx + 7 * S, ly)], fill=CREAM[:3] + (150,), width=int(1.4 * S))
        pts = [(gx0 + (gx1 - gx0) * (i + 0.5) / len(vals), sy(sum(v[1] for v in vals[max(0, i - 3):i + 1]) / len(vals[max(0, i - 3):i + 1])))
               for i in range(len(vals))]
        d.line(pts, fill=GOLD, width=int(2 * S))
    elif kind == "area":
        r = random.Random(seed)
        v, pts = 0, []
        for i in range(60):
            v += r.gauss(0.08, 1)
            pts.append(v)
        mn, mx = min(pts), max(pts)
        xy = [(gx0 + (gx1 - gx0) * i / 59, gy1 - (p - mn) / (mx - mn) * (gy1 - gy0) * 0.9) for i, p in enumerate(pts)]
        a = layer(); da = ImageDraw.Draw(a)
        da.polygon(xy + [(gx1, gy1), (gx0, gy1)], fill=ROSE[:3] + (60,))
        comp(img, a)
        d = ImageDraw.Draw(img)
        d.line(xy, fill=ROSE, width=int(2.4 * S))
    else:   # bars: buy vs sell pressure + gauge
        r = random.Random(seed)
        n = 14
        bw = (gx1 - gx0) / n
        for i in range(n):
            hgt = r.uniform(0.2, 1) * (gy1 - gy0) * 0.6
            col = UP if r.random() < 0.6 else DOWN
            d.rectangle([gx0 + bw * i + bw * 0.2, gy1 - hgt, gx0 + bw * (i + 0.8), gy1], fill=col[:3] + (210,))
        cx2, cy2, rad = (gx0 + gx1) / 2, gy0 + (gy1 - gy0) * 0.3, (gx1 - gx0) * 0.16
        d.arc([cx2 - rad, cy2 - rad, cx2 + rad, cy2 + rad], 180, 360, fill=(255, 255, 255, 40), width=int(6 * S))
        d.arc([cx2 - rad, cy2 - rad, cx2 + rad, cy2 + rad], 180, 300, fill=GOLD, width=int(6 * S))
    # screen glow outward
    g = layer(); dg = ImageDraw.Draw(g)
    rr(dg, [x0 - 30 * S, y0 - 30 * S, x1 + 30 * S, y1 + 30 * S], 40 * S, fill=(120, 200, 200, 38))
    return glow(g, 30)


def _bez(p0, p1, p2, p3, n=24):
    out = []
    for i in range(n + 1):
        t = i / n
        a, b, c, e = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
        out.append((a * p0[0] + b * p1[0] + c * p2[0] + e * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + e * p3[1]))
    return out


def _path(cmds):
    """cmds: start point + list of (c1, c2, end) cubic segments in logo units (64 x 56)"""
    pts, cur = [], cmds[0]
    for c1, c2, e in cmds[1:]:
        pts += _bez(cur, c1, c2, e)
        cur = e
    return pts


LEFT = [(31, 6), ((25, 2), (17, 4), (15, 10)), ((9, 10), (5, 15), (7, 21)), ((2, 24), (2, 32), (7, 35)),
        ((5, 41), (10, 47), (16, 46)), ((18, 51), (26, 53), (31, 49)), ((31, 30), (31, 20), (31, 6))]
GYRI = [[(15, 16), ((19, 15), (21, 18), (24, 17))], [(10, 27), ((15, 25), (17, 29), (22, 27))],
        [(14, 38), ((18, 36), (21, 40), (25, 38))], [(24, 9), ((24, 13), (27, 14), (27, 18))],
        [(20, 45), ((22, 42), (26, 43), (27, 40))], [(8, 31), ((11, 33), (13, 31), (16, 33))]]


def brain(img, cx, cy, size, aura_scale=1.0):
    """the BRAIN logo brain, scaled up: two hemispheres (rose / tan) with gradient shading, white gyri, rim light, aura"""
    k = size / 64.0
    tf = lambda pts, mir: [((64 - x if mir else x) * k + cx - 32 * k, y * k + cy - 28 * k) for x, y in pts]
    aura = layer(); da = ImageDraw.Draw(aura)
    da.ellipse([cx - size * 0.62 * aura_scale, cy - size * 0.56 * aura_scale, cx + size * 0.62 * aura_scale, cy + size * 0.56 * aura_scale], fill=(233, 165, 187, 110))
    comp(img, glow(aura, 34 * aura_scale * size / (330 * S)))
    for mir, top, bot, line in ((False, "#f7c3d3", "#d77d9b", "#7a3b52"), (True, "#f6e3cb", "#c99a6c", "#6b4a33")):
        poly = tf(_path(LEFT), mir)
        mask = Image.new("L", (W, H), 0)
        ImageDraw.Draw(mask).polygon(poly, fill=255)
        bx = [p[0] for p in poly]; by = [p[1] for p in poly]
        x0, y0, x1, y1 = int(min(bx)), int(min(by)), int(max(bx)) + 1, int(max(by)) + 1
        grad = vgrad(x1 - x0, y1 - y0, [(0, top), (1, bot)])
        img.paste(grad, (x0, y0), mask.crop((x0, y0, x1, y1)))
        d = ImageDraw.Draw(img)
        d.line(poly + [poly[0]], fill=hexc(line), width=max(2, int(size / 82)), joint="curve")
        g = layer(); dg = ImageDraw.Draw(g)
        for gy in GYRI:
            dg.line(tf(_path(gy), mir), fill=(255, 252, 248, 235), width=max(2, int(size / 66)), joint="curve")
        comp(img, g)
        # soft top highlight inside the hemisphere
        h = layer(); dh = ImageDraw.Draw(h)
        hx = cx + (8 if mir else -14) * k
        dh.ellipse([hx - 9 * k, cy - 24 * k, hx + 9 * k, cy - 16 * k], fill=(255, 255, 255, 110))
        comp(img, glow(h, 5 * size / (330 * S)))
    # rim light from the screens (teal) on the top edge
    rim = layer(); dr = ImageDraw.Draw(rim)
    dr.arc([cx - 30 * k, cy - 26 * k, cx + 30 * k, cy + 30 * k], 200, 340, fill=(120, 225, 210, 120), width=max(2, int(size / 66)))
    comp(img, glow(rim, 3 * size / (330 * S)))
    d = ImageDraw.Draw(img)
    sx, sy = cx + 27 * k, cy - 26 * k
    st = [(sx, sy - 5 * k), (sx + 1.4 * k, sy - 1.4 * k), (sx + 5 * k, sy), (sx + 1.4 * k, sy + 1.4 * k), (sx, sy + 5 * k),
          (sx - 1.4 * k, sy + 1.4 * k), (sx - 5 * k, sy), (sx - 1.4 * k, sy - 1.4 * k)]
    d.polygon(st, fill=hexc("#ffd36e"))


def threads(img, src, targets):
    """glowing neural threads from the brain to each screen, with travelling signal dots"""
    l = layer(); d = ImageDraw.Draw(l)
    for (tx, ty), col in targets:
        sx, sy = src
        for j in range(3):
            off = (j - 1) * 14 * S
            pts = []
            for i in range(41):
                t = i / 40
                mx, my = (sx + tx) / 2 + off, min(sy, ty) - 80 * S - abs(off)
                x = (1 - t) ** 2 * sx + 2 * (1 - t) * t * mx + t * t * tx
                y = (1 - t) ** 2 * sy + 2 * (1 - t) * t * my + t * t * ty
                pts.append((x, y))
            d.line(pts, fill=col[:3] + (120,), width=int(2 * S))
            for k in (0.35, 0.7):
                x, y = pts[int(k * 40)]
                d.ellipse([x - 3.5 * S, y - 3.5 * S, x + 3.5 * S, y + 3.5 * S], fill=CREAM[:3] + (230,))
    comp(img, glow(l, 5))
    comp(img, l)


def draw(img, hz):
    x0, x1, y0, y1 = window_frame(img)
    hanging_plants(img, x0, x1, y0)
    # desk
    d = ImageDraw.Draw(img)
    dy = H * 0.745
    desk = vgrad(W, int(H - dy), [(0, "#4a3530"), (0.08, "#2c211f"), (1, "#140f10")])
    img.alpha_composite(desk, (0, int(dy)))
    d = ImageDraw.Draw(img)
    d.rectangle([0, dy, W, dy + 6 * S], fill=hexc("#8a6a55"))
    # monitors (center big, sides smaller)
    glows = []
    mons = [((W * 0.355, H * 0.495, W * 0.645, H * 0.695), "candles", 3),
            ((W * 0.085, H * 0.545, W * 0.315, H * 0.695), "area", 5),
            ((W * 0.685, H * 0.545, W * 0.915, H * 0.695), "bars", 8)]
    for box, kind, seed in mons:
        glows.append(screen(img, box, kind, seed))
    for g in glows:
        comp(img, g)
    # light the desk under the screens
    lt = layer(); dl = ImageDraw.Draw(lt)
    dl.ellipse([W * 0.2, dy - 40 * S, W * 0.8, dy + 160 * S], fill=(110, 190, 190, 55))
    comp(img, glow(lt, 40))
    d = ImageDraw.Draw(img)
    # keyboard + mouse + mug
    rr(d, [W * 0.40, dy + 30 * S, W * 0.60, dy + 64 * S], 8 * S, fill=hexc("#1b1619"))
    for r_ in range(3):
        for c in range(14):
            kx = W * 0.405 + c * (W * 0.19 / 14)
            ky = dy + 36 * S + r_ * 9 * S
            d.rectangle([kx, ky, kx + W * 0.19 / 14 - 3 * S, ky + 6 * S], fill=(80, 170, 170, 120) if (c + r_) % 5 else (233, 165, 187, 150))
    rr(d, [W * 0.64, dy + 34 * S, W * 0.665, dy + 58 * S], 10 * S, fill=hexc("#1b1619"))
    mx_, my_ = W * 0.25, dy + 18 * S
    rr(d, [mx_, my_, mx_ + 46 * S, my_ + 54 * S], 8 * S, fill=hexc("#dcbb91"))
    d.arc([mx_ + 34 * S, my_ + 10 * S, mx_ + 62 * S, my_ + 40 * S], 270, 90, fill=hexc("#dcbb91"), width=int(6 * S))
    st = layer(); ds = ImageDraw.Draw(st)
    for k in range(3):
        px = mx_ + 14 * S + k * 9 * S
        ds.line([(px + 6 * S * math.sin(i / 4 + k), my_ - i * 4 * S) for i in range(14)], fill=(255, 240, 230, 70), width=int(3 * S))
    comp(img, glow(st, 2))
    # the brain in its chair: brain first, chair back drawn over its lower part (we're behind the chair)
    bx, by, bs = W * 0.5, H * 0.80, 330 * S
    threads(img, (bx, by - bs * 0.32), [((W * 0.5, H * 0.60), UP), ((W * 0.20, H * 0.62), ROSE), ((W * 0.80, H * 0.62), GOLD)])
    brain(img, bx, by, bs)
    d = ImageDraw.Draw(img)
    cb = [W * 0.36, H * 0.835, W * 0.64, H * 1.06]
    rr(d, cb, 70 * S, fill=hexc("#1c1518"))
    rr(d, [cb[0] + 16 * S, cb[1] + 16 * S, cb[2] - 16 * S, cb[3]], 56 * S, fill=hexc("#241b1f"))
    hl = layer(); dh = ImageDraw.Draw(hl)
    dh.rounded_rectangle([int(cb[0]), int(cb[1]), int(cb[2]), int(cb[3])], int(70 * S), outline=(120, 210, 205, 90), width=int(3 * S))
    comp(img, glow(hl, 2))
    d = ImageDraw.Draw(img)
    for i in range(4):
        yy = cb[1] + 60 * S + i * 38 * S
        d.line([(cb[0] + 50 * S, yy), (cb[2] - 50 * S, yy)], fill=hexc("#2e2328"), width=int(5 * S))
    # fireflies over the cove
    ff = layer(); df = ImageDraw.Draw(ff)
    for _ in range(26):
        x, y = rng.uniform(W * 0.08, W * 0.92), rng.uniform(H * 0.36, H * 0.5)
        r_ = rng.uniform(2, 4) * S
        df.ellipse([x - r_, y - r_, x + r_, y + r_], fill=(255, 226, 150, 200))
    comp(img, glow(ff, 3))
    comp(img, ff)
    # radial vignette
    import numpy as np
    yy, xx = np.mgrid[0:H, 0:W]
    dd = np.sqrt(((xx - W / 2) / (W * 0.62)) ** 2 + ((yy - H * 0.55) / (H * 0.7)) ** 2)
    a = (np.clip(dd - 0.55, 0, 1) * 330).clip(0, 170).astype(np.uint8)
    v = Image.fromarray(np.dstack([np.full_like(a, 8), np.full_like(a, 6), np.full_like(a, 8), a]), "RGBA")
    comp(img, v)
