"""Animate every scene of "What if the Carrington storm hit today?" over its Cycles plates (storm_plate.py), with 2D motion
(push-ins, aurora shimmer, flashes, sparks, flames, blackouts, reentry streaks, an orbit diagram).
python3 storm_anim.py <scene> [frames...]  ->  storm/s<scene>/f_####.png + meta.json (overlays read by compose.py)"""
import sys, math, json, os
sys.path.insert(0, '/home/claude/pro')
import numpy as np, cv2, skia
import engine as E
ROOT = '/home/claude/b3d/storm'; CFG = json.load(open(f'{ROOT}/topic.json'))
FPS = 24; PAD = .75; idx = int(sys.argv[1]); D = CFG['durs'][idx]; NF = int(math.ceil((D + PAD) * FPS))
W, H = 1080, 1920
ease = lambda t: .5 - .5 * math.cos(math.pi * min(max(t, 0), 1))
eout = lambda t: 1 - (1 - min(max(t, 0), 1)) ** 3
clamp = lambda t: min(max(t, 0.0), 1.0)
PL = {}
def plate(name):
    if name not in PL:
        im = cv2.imread(f'{ROOT}/plates/{name}.png', cv2.IMREAD_COLOR)
        if im.shape[1] != W: im = cv2.resize(im, (W, H), interpolation=cv2.INTER_CUBIC)
        PL[name] = im.astype(np.float32)
    return PL[name]

def kb(name, u, z0, z1, c0=(.5, .5), c1=(.5, .5), src=None):
    """Ken-Burns crop of a plate: zoom z (>=1) around a moving center (fractions of the plate)"""
    im = plate(name) if src is None else src; t = ease(u); z = z0 + (z1 - z0) * t
    cx = (c0[0] + (c1[0] - c0[0]) * t) * W; cy = (c0[1] + (c1[1] - c0[1]) * t) * H
    M = np.float32([[z, 0, W / 2 - cx * z], [0, z, H / 2 - cy * z]])
    return cv2.warpAffine(im, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

def kb_pt(px, py, u, z0, z1, c0=(.5, .5), c1=(.5, .5)):
    """where a plate point (fractions) lands on screen for the same Ken-Burns move"""
    t = ease(u); z = z0 + (z1 - z0) * t
    cx = (c0[0] + (c1[0] - c0[0]) * t) * W; cy = (c0[1] + (c1[1] - c0[1]) * t) * H
    return W / 2 + (px * W - cx) * z, H / 2 + (py * H - cy) * z, z

XX = np.arange(W, dtype=np.float32)[None, :]; YY = np.arange(H, dtype=np.float32)[:, None]
def shimmer(img, T, k=1.0):
    """aurora shimmer: green/red sky pixels ripple in brightness with travelling vertical rays"""
    b, g, r = img[..., 0], img[..., 1], img[..., 2]
    m = np.clip((np.maximum(g, r) - b - 25) / 60, 0, 1) * np.clip((np.maximum(g, r) - 40) / 80, 0, 1)
    wave = .5 + .5 * np.sin(XX / 23 + T * 2.6 + 1.7 * np.sin(XX / 140 - T * .9)) * np.sin(XX / 61 - T * 1.3)
    gain = 1 + k * (.55 * wave - .18) * m
    return img * gain[..., None]

RNG = np.random.default_rng(11); MOTES = RNG.random((150, 4))
def dust(img, T, col=(150, 190, 255), k=1.0, drift=(8, -14)):
    lay = np.zeros_like(img)
    for x, y, s, b in MOTES:
        px = int((x * W + T * drift[0] * (.5 + s) + 14 * math.sin(T * .6 + y * 7)) % W); py = int((y * H + T * drift[1] * (.5 + s)) % H)
        v = (20 + 60 * b * b) * k; cv2.circle(lay, (px, py), 1 + int(s * 2.4), (col[0] * v / 255, col[1] * v / 255, col[2] * v / 255), -1, cv2.LINE_AA)
    return img + cv2.GaussianBlur(lay, (0, 0), 1.4)

def glow(img, x, y, r, a, col=(210, 245, 255)):
    """additive radial glow (BGR col)"""
    if a <= 0: return img
    x0, x1 = int(max(0, x - 3 * r)), int(min(W, x + 3 * r)); y0, y1 = int(max(0, y - 3 * r)), int(min(H, y + 3 * r))
    if x1 <= x0 or y1 <= y0: return img
    d2 = ((XX[:, x0:x1] - x) ** 2 + (YY[y0:y1] - y) ** 2) / (r * r)
    g = (np.exp(-d2 * 2.2) * 1.0 + np.exp(-d2 * .35) * .35) * a
    img[y0:y1, x0:x1] += g[..., None] * np.array(col, np.float32)
    return img

def sparks(img, x, y, T, spread=60, n=14, a=1.0, seed=0):
    """crackling electric sparks: short jagged bright arcs that re-randomize every 2 frames"""
    fr = int(T * 12); rng = np.random.default_rng(seed * 1000 + fr); lay = np.zeros_like(img)
    for k in range(n):
        if rng.random() < .35: continue
        px, py = x + rng.normal(0, spread * .4), y + rng.normal(0, spread * .4)
        pts = [(px, py)]
        for j in range(5): px += rng.normal(0, spread * .25); py += rng.normal(0, spread * .25); pts.append((px, py))
        pts = np.int32(pts); cv2.polylines(lay, [pts], False, (255, 235, 200), 2, cv2.LINE_AA)
    lay = lay * a
    img += cv2.GaussianBlur(lay, (0, 0), 5) * 2.2 + lay
    return glow(img, x, y, spread * .7, .5 * a * (.6 + .4 * math.sin(T * 40)), (255, 220, 170))

def flames(img, x, y, T, size=40, a=1.0, seed=0):
    """small fire: flickering orange tongues rising from a point"""
    lay = np.zeros_like(img); rng = np.random.default_rng(seed)
    ph = rng.random(12) * 6.28
    for k in range(12):
        t = (T * 1.6 + k / 12) % 1.0; dx = math.sin(T * 7 + ph[k]) * size * .25 * (1 + t)
        px, py = int(x + dx + (k - 6) * size * .07), int(y - t * size * 1.6); rr = int(size * .35 * (1 - t) + 2)
        col = (30, 120 + 100 * (1 - t), 255)
        cv2.circle(lay, (px, py), rr, (col[0] * (1 - t), col[1] * (1 - t), col[2] * (1 - t)), -1, cv2.LINE_AA)
    img += cv2.GaussianBlur(lay, (0, 0), size * .18) * 1.6 * a
    return glow(img, x, y - size * .4, size * 1.2, .35 * a, (60, 150, 255))

def shaft(img, T, tx, ty):
    """soft sunbeam from the top-right roof slit down onto the telescope objective (tx, ty), with drifting dust"""
    sx, sy = W * 1.05, -H * .05; lay = np.zeros_like(img)
    d = np.array([tx - sx, ty - sy]); L_ = np.linalg.norm(d); d /= L_; nrm = np.array([-d[1], d[0]])
    px = (XX - sx) * d[0] + (YY - sy) * d[1]; pz = (XX - sx) * nrm[0] + (YY - sy) * nrm[1]
    wid = 40 + 60 * np.clip(px / L_, 0, 1.2)
    m = np.exp(-(pz / wid) ** 2) * np.clip(px / L_ * 1.3, 0, 1) * (px < L_ * 1.05)
    m = m * (.85 + .15 * np.sin(px / 40 - T * 2))
    return img + m[..., None] * np.array([70, 140, 210], np.float32) * .55

NOISE = None
def blackout(lit, dark, u, T, seed=3, region=None):
    """the lights go out region by region (chunky noise threshold) with a brief flicker at each switch"""
    global NOISE
    if NOISE is None:
        rng = np.random.default_rng(seed); n = rng.random((24, 14)).astype(np.float32)
        NOISE = cv2.resize(n, (W, H), interpolation=cv2.INTER_CUBIC); NOISE = (NOISE - NOISE.min()) / (NOISE.max() - NOISE.min())
    m = np.clip((u * 1.25 - NOISE) * 8, 0, 1)
    flick = (np.abs(u * 1.25 - NOISE) < .04) * (.5 + .5 * math.sin(T * 60))
    m = np.clip(m + flick * .0, 0, 1) * (1 - flick * .6) + flick * .6 * (math.sin(T * 60) > 0)
    if region is not None: m = m * region
    return lit * (1 - m[..., None]) + dark * m[..., None]

def streaks(img, T, u, n=9, seed=4):
    """satellites re-entering: glowing orange streaks with trails, angled down"""
    lay = np.zeros_like(img); rng = np.random.default_rng(seed)
    for k in range(n):
        t0 = rng.random() * .6; p = (u - t0) / .45
        if p <= 0 or p > 1: continue
        x0, y0 = rng.uniform(.1, .9) * W, rng.uniform(.25, .5) * H; L = 380
        hx, hy = x0 + p * 420, y0 + p * 520
        for j in range(10):
            f = j / 10; cv2.line(lay, (int(hx - 0.7 * L * f), int(hy - .85 * L * f)), (int(hx - .7 * L * (f + .1)), int(hy - .85 * L * (f + .1))),
                                 (40 * (1 - f), 140 * (1 - f), 255 * (1 - f)), int(7 * (1 - f)) + 1, cv2.LINE_AA)
        img = glow(img, hx, hy, 14, .9, (170, 220, 255))
    return img + cv2.GaussianBlur(lay, (0, 0), 4) * 1.5 + lay * .8

# ---------------- skia helpers (2D diagram)
def sk_begin(img):
    bgra = np.dstack([np.clip(img, 0, 255).astype(np.uint8), np.full((H, W), 255, np.uint8)])
    surf = skia.Surface(W, H); c = surf.getCanvas()
    c.drawImage(skia.Image.fromarray(np.ascontiguousarray(bgra), colorType=skia.kBGRA_8888_ColorType), 0, 0); return surf, c
def sk_end(surf): return surf.makeImageSnapshot().toarray()[..., :3].astype(np.float32)
def Pn(col, a=255, style='fill', w=0, blur=0):
    p = skia.Paint(AntiAlias=True, Color=skia.Color(int(col[0]), int(col[1]), int(col[2]), int(max(0, min(255, a)))))
    if style == 'stroke': p.setStyle(skia.Paint.kStroke_Style); p.setStrokeWidth(w); p.setStrokeCap(skia.Paint.kRound_Cap)
    if blur: p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, blur))
    return p
def text(c, s, x, y, size, col=(255, 255, 255), a=255, align='c'):
    f = skia.Font(E.TF, size); w = f.measureText(s); x0 = x - w / 2 if align == 'c' else (x - w if align == 'r' else x)
    c.drawString(s, x0, y, f, Pn((0, 0, 0), a * .85, 'stroke', size * .14)); c.drawString(s, x0, y, f, Pn(col, a))
GOLD = (255, 205, 70); CYAN = (110, 215, 255); WHITE = (255, 255, 255); ORANGE = (255, 120, 40)

STARS = np.random.default_rng(2).random((260, 3))
def orbit(T, u, mode):
    """July 2012: the CME crosses Earth's orbit where Earth had been about a week earlier (1 week = ~6.9 deg of orbit).
    Sun at the bottom centre, orbit arc above; angles true, sizes of Sun/Earth NOT to scale."""
    img = np.zeros((H, W, 3), np.float32)
    for x, y, b in STARS: cv2.circle(img, (int(x * W), int(y * H)), 1, (90 + 120 * b,) * 3, -1)
    img = glow(img, W / 2, H * .88, 150, 1.0, (60, 170, 255)); img = glow(img, W / 2, H * .88, 60, 1.2, (170, 235, 255))
    surf, c = sk_begin(img); cx, cy, Ro = W / 2, H * .88, H * .52
    c.drawCircle(cx, cy, 70, Pn((255, 190, 90)))
    oval = skia.Rect.MakeXYWH(cx - Ro, cy - Ro, 2 * Ro, 2 * Ro)
    c.drawArc(oval, 200, 140, False, Pn(CYAN, 170, 'stroke', 5))
    deg_week = 360 / 365.25 * 7
    ang_hit = 270 - 4                       # where the CME crossed the orbit (screen degrees, 270 = straight up)
    ang_earth = ang_hit + deg_week if mode == 'now' else ang_hit + deg_week * (1 - eout(u))   # Earth had moved on a week later
    # CME fan from the Sun through the crossing point
    grow = eout(u * 1.3) if mode == 'now' else 1.0
    path = skia.Path(); path.moveTo(cx, cy)
    for a in (ang_hit - 3, ang_hit + 3):
        rr = Ro * 1.15 * grow; path.lineTo(cx + rr * math.cos(math.radians(a)), cy + rr * math.sin(math.radians(a)))
    path.close(); c.drawPath(path, Pn(ORANGE, 110, blur=18)); c.drawPath(path, Pn((255, 160, 80), 140, 'stroke', 3))
    ex, ey = cx + Ro * math.cos(math.radians(ang_earth)), cy + Ro * math.sin(math.radians(ang_earth))
    c.drawCircle(ex, ey, 34, Pn((60, 130, 255), 90, blur=14)); c.drawCircle(ex, ey, 22, Pn((70, 140, 255)))
    text(c, 'EARTH', ex + 40, ey + 14, 46, WHITE, 255, 'l')
    if mode == 'week':   # ghost: where Earth was one week earlier, inside the blast
        hx, hy = cx + Ro * math.cos(math.radians(ang_hit)), cy + Ro * math.sin(math.radians(ang_hit))
        a = 255 * clamp(u * 2)
        c.drawCircle(hx, hy, 22, Pn((255, 80, 60), a * .9, 'stroke', 5))
        text(c, 'EARTH, 1 WEEK EARLIER', hx, hy - 110, 46, GOLD, a, 'c')
        if u > .4:
            p = eout((u - .4) / .4); bx = hx - 6 + (ex - hx) * p
            c.drawLine(hx, hy + 52, ex, ey + 52, Pn(GOLD, a * .8, 'stroke', 4))
    text(c, 'SUN', cx - 130, cy + 16, 46, WHITE, 255, 'r')
    text(c, "EARTH'S ORBIT", cx + 250, cy - Ro * .985 + 80, 40, CYAN, 220)
    text(c, 'NOT TO SCALE', W - 40, H - 60, 30, (200, 200, 200), 200, 'r')
    return sk_end(surf)

# ---------------- feature positions in the plates (fractions of the frame, measured on the stills)
FX = json.load(open(f'{ROOT}/plates/fx.json')) if os.path.exists(f'{ROOT}/plates/fx.json') else {}
def fx(k, d=(.5, .5)): return FX.get(k, d)

def shots():
    def earth(T, u, z0, z1, c0=(.5, .5), c1=(.5, .5), name='earth_aur'):
        if name == 'earth_dark': return earth_out(T, 1, z0, z1, c0, c1, 1, 1)
        return dust(shimmer(kb(name, u, z0, z1, c0, c1), T, .8), T, k=.5)
    US = (np.exp(-(((XX / W - .47) / .36) ** 2 + ((YY / H - .47) / .13) ** 2) ** 2)).astype(np.float32)   # contiguous US on the earth plates
    def earth_out(T, u, z0, z1, c0=(.5, .5), c1=(.5, .5), speed=1.0, lo=0.0):   # US city lights blink out
        src = blackout(plate('earth_aur'), plate('earth_dark'), lo + (1 - lo) * clamp(u * speed), T, region=US)
        return dust(shimmer(kb('earth_aur', u, z0, z1, c0, c1, src=src), T, .8), T, k=.5)
    def grid_out(T, u, z0, z1, c0=(.5, .5), c1=(.5, .5), speed=1.0, start=0.0):   # the town goes dark in a sweep, with a flicker
        lit = kb('grid_on', u, z0, z1, c0, c1); dk = kb('grid_off', u, z0, z1, c0, c1); v = clamp((u - start) * speed)
        edge = -0.2 + 1.4 * v; m = np.clip((edge - XX / W) / .2, 0, 1)
        if 0 < v < 1 and int(T * 20) % 3 == 0: m = np.maximum(m, .35)
        m = np.broadcast_to(m, (H, W))[..., None]
        return dust(shimmer(lit * (1 - m) + dk * m, T), T, k=.6)
    def sunflash(T, u, z0, z1, a_fn):
        img = kb('sun', u, z0, z1, (.45, .45), (.42, .42)); x, y, z = kb_pt(*fx('sun_spot', (.33, .4)), u, z0, z1, (.45, .45), (.42, .42))
        a = a_fn(T); img = glow(img, x - 30 * z, y, 38 * z, a, (215, 250, 255)); img = glow(img, x + 34 * z, y + 18 * z, 30 * z, a * .9, (215, 250, 255))
        return img
    def screen(T, u, z0, z1, c0, c1, a_fn):
        img = shaft(kb('observatory', u, z0, z1, c0, c1), T, *kb_pt(*fx('obs_obj', (.75, .36)), u, z0, z1, c0, c1)[:2]); x, y, z = kb_pt(*fx('obs_spot', (.3, .62)), u, z0, z1, c0, c1)
        a = a_fn(T); img = glow(img, x - 10 * z, y, 22 * z, a, (215, 250, 255)); img = glow(img, x + 16 * z, y + 10 * z, 18 * z, a * .9, (215, 250, 255))
        return dust(img, T, (120, 190, 255), .9, (4, -6))
    flash_on = lambda t0: (lambda T: clamp((T - t0) / .25) * (.85 + .15 * math.sin(T * 30)))
    def cme(T, u, z0, z1, c0=(.5, .55), c1=(.5, .45)):
        return dust(kb('cme', u, z0, z1, c0, c1), T, (80, 160, 255), .6, (0, -40))
    def rockies(T, u, z0, z1, c0, c1):
        img = shimmer(kb('rockies', u, z0, z1, c0, c1), T, 1.0); x, y, z = kb_pt(*fx('fire', (.39, .79)), u, z0, z1, c0, c1)
        return flames(img, x, y, T, 26 * z)
    def poles(T, u, z0, z1, c0, c1, spark=0.0):
        img = shimmer(kb('poles', u, z0, z1, c0, c1), T, 1.0)
        if spark > 0:
            for k, key in enumerate(('pole1', 'pole2')):
                x, y, z = kb_pt(*fx(key, (.47 + .35 * k, .72)), u, z0, z1, c0, c1); img = sparks(img, x, y, T, 40 * z, 10, spark, k)
        return img
    def desk(T, u, z0, z1, c0, c1, spark=0.0, fire=0.0):
        img = kb('desk', u, z0, z1, c0, c1)
        if spark > 0:
            x, y, z = kb_pt(*fx('key', (.45, .6)), u, z0, z1, c0, c1); img = sparks(img, x, y, T, 70 * z, 16, spark, 5)
        if fire > 0:
            x, y, z = kb_pt(*fx('tape', (.55, .52)), u, z0, z1, c0, c1); img = flames(img, x, y, T, 34 * z, fire, 2)
        return dust(img, T, (120, 170, 255), .7, (3, -5))
    def transformer(T, u, z0, z1, c0, c1):
        img = shimmer(kb('transformer', u, z0, z1, c0, c1), T, .8)
        for k, key in enumerate(('bush1', 'bush2')):
            x, y, z = kb_pt(*fx(key, (.4 + .25 * k, .3)), u, z0, z1, c0, c1); img = sparks(img, x, y, T, 55 * z, 14, 1.0, 7 + k)
        return img
    def starlink(T, u, z0, z1, c0, c1, re=True):
        img = kb('starlink', u, z0, z1, c0, c1)
        return streaks(img, T, u) if re else img
    return {
     0: [(0, lambda T, u: earth_out(T, u, 1.12, 1.22, (.5, .45), (.5, .47), 1.3, .15)), (1.6, lambda T, u: grid_out(T, u, 1.15, 1.25, (.45, .5), (.5, .5), 1.6, .1))],
     1: [(0, lambda T, u: sunflash(T, u, 1.05, 1.2, flash_on(.3))), (1.8, lambda T, u: earth(T, u, 1.0, 1.08))],
     2: [(0, lambda T, u: screen(T, u, 1.0, 1.1, (.5, .5), (.47, .52), lambda T: 0)), (1.8, lambda T, u: screen(T, u, 1.35, 1.5, (.5, .5), (.47, .48), lambda T: 0))],
     3: [(0, lambda T, u: screen(T, u, 1.9, 2.2, (.47, .47), (.47, .46), flash_on(.8))), (2.0, lambda T, u: sunflash(T, u, 1.3, 1.5, lambda T: .95 + .05 * math.sin(T * 30)))],
     4: [(0, lambda T, u: sunflash(T, u, 1.5, 1.6, lambda T: max(0, 1 - T / 1.4))), (1.2, lambda T, u: screen(T, u, 2.2, 2.3, (.47, .46), (.47, .46), lambda T: 0))],
     5: [(0, lambda T, u: cme(T, u, 1.0, 1.15, (.5, .7), (.5, .62))), (2.2, lambda T, u: cme(T, u, 1.35, 1.5, (.5, .5), (.5, .4)))],
     6: [(0, lambda T, u: cme(T, u, 1.0, 1.08, (.5, .55), (.5, .45))), (2.1, lambda T, u: cme(T, u, 1.45, 1.7, (.55, .2), (.56, .12)))],
     7: [(0, lambda T, u: earth(T, u, 1.25, 1.4, (.5, .35), (.5, .4))), (1.8, lambda T, u: poles(T, u, 1.0, 1.1, (.5, .4), (.5, .38)))],
     8: [(0, lambda T, u: rockies(T, u, 1.0, 1.1, (.5, .45), (.5, .42))), (1.7, lambda T, u: rockies(T, u, 1.6, 1.8, (.42, .72), (.4, .74))),
         (3.3, lambda T, u: rockies(T, u, 1.15, 1.2, (.5, .3), (.5, .28)))],
     9: [(0, lambda T, u: poles(T, u, 1.15, 1.3, (.55, .55), (.6, .56), 1.0)), (1.8, lambda T, u: desk(T, u, 1.1, 1.25, (.5, .55), (.47, .57), 1.0)),
         (3.2, lambda T, u: desk(T, u, 1.4, 1.55, (.52, .52), (.54, .52), .6, clamp(u * 3)))],
     10: [(0, lambda T, u: desk(T, u, 1.0, 1.12, (.5, .5), (.45, .55))), (2.0, lambda T, u: poles(T, u, 1.0, 1.15, (.5, .45), (.45, .45))),
          (3.4, lambda T, u: desk(T, u, 1.6, 1.75, (.47, .6), (.45, .6), .25))],
     11: [(0, lambda T, u: grid_out(T, u, 1.0, 1.15, (.5, .5), (.5, .45), 0))],
     12: [(0, lambda T, u: grid_out(T, u, 1.05, 1.15, (.5, .5), (.48, .5), 2.2, .2)), (2.4, lambda T, u: grid_out(T, u, 1.4, 1.5, (.6, .6), (.62, .58), 1, -1) * .9)],
     13: [(0, lambda T, u: starlink(T, u, 1.0, 1.1, (.5, .5), (.52, .45), False)), (1.9, lambda T, u: starlink(T, u, 1.15, 1.3, (.5, .5), (.5, .55)))],
     14: [(0, lambda T, u: transformer(T, u, 1.0, 1.1, (.5, .45), (.5, .4))), (2.2, lambda T, u: transformer(T, u, 1.5, 1.7, (.45, .32), (.48, .3))),
          (4.2, lambda T, u: transformer(T, u, 1.1, 1.15, (.5, .55), (.5, .55)))],
     15: [(0, lambda T, u: earth_out(T, u, 1.0, 1.1, (.5, .45), (.5, .48), 1.3)), (2.4, lambda T, u: grid_out(T, u, 1.1, 1.2, (.5, .5), (.5, .5), 1, -1)),
          (4.4, lambda T, u: earth(T, u, 1.3, 1.45, (.45, .5), (.45, .52), 'earth_dark'))],
     16: [(0, lambda T, u: earth(T, u, 1.45, 1.6, (.5, .5), (.5, .45), 'earth_dark')), (2.6, lambda T, u: grid_out(T, u, 1.25, 1.35, (.55, .5), (.6, .5), 1, -1))],
     17: [(0, lambda T, u: orbit(T, u, 'now'))],
     18: [(0, lambda T, u: orbit(T, u, 'week'))],
     19: [(0, lambda T, u: earth(T, u, 1.0, 1.15, (.5, .5), (.5, .45))), (2.0, lambda T, u: cme(T, u, 1.3, 1.45, (.55, .3), (.55, .25)))],
     20: [(0, lambda T, u: sunflash(T, u, 1.0, 1.12, lambda T: .5 + .5 * math.sin(T * 3) ** 2)), (2.4, lambda T, u: earth(T, u, 1.05, 1.15, (.5, .45), (.5, .43)))],
     21: [(0, lambda T, u: earth_out(T, u, 1.0, 1.12, (.5, .43), (.5, .45), .3))],
    }[idx]

YEL, WH = [255, 222, 40], [255, 255, 255]
OV = {   # compose.py overlays per scene
 0: [{'type': 'hook', 'text': 'UP TO 40 MILLION|IN THE DARK'}, {'type': 'label', 'text': 'VISUALIZATION', 'color': [200, 200, 200], 'pos': [.8, .955], 'instant': True}],
 1: [{'type': 'label', 'text': 'THE CARRINGTON EVENT', 'color': YEL, 'pos': [.5, .2], 'from': 1.9}],
 2: [{'type': 'datestamp', 'text': 'REDHILL, NEAR LONDON · 1 SEPT 1859', 'from': .2}],
 3: [{'type': 'bubble', 'text': '"two patches of intensely', 'pos': [.5, .13], 'size': 54, 'from': 1.0},
     {'type': 'bubble', 'text': 'bright and white light"', 'pos': [.5, .205], 'size': 54, 'from': 1.2},
     {'type': 'label', 'text': '- CARRINGTON, 1859', 'color': WH, 'pos': [.5, .28], 'from': 1.4}],
 4: [{'type': 'badge', 'value': '5', 'unit': 'minutes', 'pos': [.5, .16], 'from': .2}],
 5: [{'type': 'label', 'text': 'MAGNETIZED PLASMA (CME)', 'color': YEL, 'pos': [.5, .16], 'from': .6},
     {'type': 'label', 'text': 'NOT TO SCALE', 'color': [200, 200, 200], 'pos': [.82, .955], 'from': .3}],
 6: [{'type': 'label', 'text': 'USUALLY: DAYS', 'color': WH, 'pos': [.5, .15], 'from': .2},
     {'type': 'badge', 'value': '17.6', 'unit': 'hours', 'pos': [.5, .22], 'from': 1.6}],
 7: [{'type': 'label', 'text': 'AURORAS AS FAR SOUTH AS', 'color': WH, 'pos': [.5, .15], 'from': .3},
     {'type': 'label', 'text': 'CUBA & HAWAII', 'color': YEL, 'pos': [.5, .21], 'from': .9}],
 8: [{'type': 'datestamp', 'text': 'ROCKY MOUNTAINS · 2 SEPT 1859', 'from': .2},
     {'type': 'label', 'text': 'AT NIGHT, NOT MORNING', 'color': YEL, 'pos': [.5, .2], 'from': 2.6}],
 9: [{'type': 'label', 'text': 'TELEGRAPH LINES', 'color': YEL, 'pos': [.5, .16], 'from': .3}],
 10: [{'type': 'label', 'text': 'BATTERIES UNPLUGGED', 'color': YEL, 'pos': [.5, .16], 'from': .5},
      {'type': 'label', 'text': 'BOSTON - PORTLAND, MAINE', 'color': WH, 'pos': [.5, .22], 'from': 2.1}],
 11: [{'type': 'label', 'text': 'NOW: 2026', 'color': YEL, 'pos': [.5, .18], 'from': .1}],
 12: [{'type': 'datestamp', 'text': 'QUEBEC · 13 MARCH 1989', 'from': .2},
      {'type': 'badge', 'value': '6 million', 'unit': 'people', 'pos': [.5, .17], 'from': 1.6},
      {'type': 'badge', 'value': '9', 'unit': 'hours', 'pos': [.5, .25], 'from': 2.9}],
 13: [{'type': 'datestamp', 'text': 'LOW EARTH ORBIT · FEB 2022', 'from': .2},
      {'type': 'badge', 'value': 'up to 40', 'unit': 'satellites lost', 'pos': [.5, .17], 'from': 2.2},
      {'type': 'label', 'text': 'ENLARGED · NOT TO SCALE', 'color': [200, 200, 200], 'pos': [.75, .955], 'from': .3}],
 14: [{'type': 'label', 'text': 'GIANT TRANSFORMERS', 'color': YEL, 'pos': [.5, .15], 'from': .4},
      {'type': 'badge', 'value': '1+ year', 'unit': 'to replace', 'pos': [.5, .22], 'from': 3.0}],
 15: [{'type': 'badge', 'value': '20-40 million', 'unit': 'Americans', 'pos': [.5, .15], 'from': .6},
      {'type': 'label', 'text': '= UP TO ALL OF CALIFORNIA', 'color': WH, 'pos': [.5, .23], 'from': 2.6},
      {'type': 'label', 'text': 'WEEKS TO YEARS', 'color': YEL, 'pos': [.5, .29], 'from': 4.4}],
 16: [{'type': 'badge', 'value': '$2.6', 'unit': 'trillion', 'pos': [.5, .15], 'from': .5},
      {'type': 'label', 'text': '= $7,000+ PER AMERICAN', 'color': YEL, 'pos': [.5, .23], 'from': 2.8}],
 17: [{'type': 'datestamp', 'text': '23 JULY 2012', 'from': .2}],
 18: [{'type': 'badge', 'value': '1', 'unit': 'week', 'pos': [.5, .14], 'from': .3}],
 19: [{'type': 'bubble', 'text': '"If it had hit, we would', 'pos': [.5, .13], 'size': 54, 'from': .5},
      {'type': 'bubble', 'text': 'still be picking up the pieces"', 'pos': [.5, .205], 'size': 54, 'from': .7},
      {'type': 'label', 'text': '- DANIEL BAKER, CU BOULDER', 'color': WH, 'pos': [.5, .28], 'from': 1.0}],
 20: [{'type': 'badge', 'value': '~12%', 'unit': 'per decade', 'pos': [.5, .16], 'from': 1.8},
      {'type': 'label', 'text': 'ONE ESTIMATE (RILEY, 2012)', 'color': WH, 'pos': [.5, .24], 'from': 2.2}],
 21: [{'type': 'cta'}],
}[idx]

if __name__ == '__main__':
    out = f'{ROOT}/s{idx}'; os.makedirs(out, exist_ok=True)
    SH = shots(); bounds = [s for s, _ in SH] + [D + PAD]
    only = [int(a) for a in sys.argv[2:]]   # optional: render only these frames (preview)
    for f in (only or range(1, NF + 1)):
        T = (f - 1) / FPS - .35          # compose samples scene time T + XF; frame 1 = .35 s before the line starts
        Tc = max(T, 0); k = max(j for j in range(len(SH)) if SH[j][0] <= Tc or j == 0)
        t0, t1 = bounds[k], bounds[k + 1]; u = (Tc - t0) / max(t1 - t0, .1)
        img = SH[k][1](T - t0 + (.35 if k == 0 else 0), u)
        cv2.imwrite(f'{out}/f_{f:04d}.png', np.clip(img, 0, 255).astype(np.uint8), [cv2.IMWRITE_PNG_COMPRESSION, 1])
    json.dump({'frames': NF, 'overlays': OV}, open(f'{out}/meta.json', 'w'))
    print('scene', idx, NF)
