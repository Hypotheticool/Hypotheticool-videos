"""Animate every scene of "What if the space station fell out of the sky?" over its Cycles plates (iss_plate.py) with 2D motion:
push-ins, reentry plasma (bow glow + trail + sparks), camera shake, air-drag wisps, speed streaks, coast-to-coast route draw-on with a
moving dot and a minute counter, a debris-streak rain, ground-track pulse, the Esperance littering ticket + PAID stamp, the tug's engine
glow, and a Point Nemo marker.
python3 iss_anim.py <scene> [frames...]  ->  iss/s<scene>/f_####.png + meta.json (overlays read by compose.py)"""
import sys, math, json, os
sys.path.insert(0, '/home/claude/pro')
import numpy as np, cv2, skia
import engine as E
ROOT = '/home/claude/b3d/iss'; CFG = json.load(open(f'{ROOT}/topic.json'))
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
        im = im.astype(np.float32)
        if name in ('fire', 'breakup', 'skylab'):   # night-side grade: the dim Earth goes near-black, bright station/plasma stays
            lum = im.mean(2, keepdims=True); k = np.clip((lum - 55) / 90, 0, 1); k = k * k * (3 - 2 * k)
            im = im * (.32 + .68 * k)
            im[..., 0] *= 1.08                         # slightly cooler shadows (BGR)
        PL[name] = im
    return PL[name]
FXD = {}
def fx(pl, k, d=(.5, .5)):
    if pl not in FXD:
        p = f'{ROOT}/plates/fx_{pl}.json'; FXD[pl] = json.load(open(p)) if os.path.exists(p) else {}
    return FXD[pl].get(k, d)

def cclamp(cx, cy, z):
    m = 14 / max(z, 1e-3)   # keep the zoomed view inside the plate (room for shake)
    hx, hy = W / (2 * z) + m, H / (2 * z) + m
    if hx < W / 2: cx = min(max(cx, hx), W - hx)
    if hy < H / 2: cy = min(max(cy, hy), H - hy)
    return cx, cy

def kb(name, u, z0, z1, c0=(.5, .5), c1=(.5, .5), src=None, shake=0.0, T=0.0):
    im = plate(name) if src is None else src; t = ease(u); z = z0 + (z1 - z0) * t
    cx = (c0[0] + (c1[0] - c0[0]) * t) * W; cy = (c0[1] + (c1[1] - c0[1]) * t) * H; cx, cy = cclamp(cx, cy, z)
    sx = shake * (math.sin(T * 47) + .6 * math.sin(T * 83 + 1)) * 9; sy = shake * (math.sin(T * 53 + 2) + .6 * math.sin(T * 71)) * 9
    M = np.float32([[z, 0, W / 2 - cx * z + sx], [0, z, H / 2 - cy * z + sy]])
    return cv2.warpAffine(im, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

def kb_pt(px, py, u, z0, z1, c0=(.5, .5), c1=(.5, .5)):
    t = ease(u); z = z0 + (z1 - z0) * t
    cx = (c0[0] + (c1[0] - c0[0]) * t) * W; cy = (c0[1] + (c1[1] - c0[1]) * t) * H; cx, cy = cclamp(cx, cy, z)
    return W / 2 + (px * W - cx) * z, H / 2 + (py * H - cy) * z, z

XX = np.arange(W, dtype=np.float32)[None, :]; YY = np.arange(H, dtype=np.float32)[:, None]
RNG = np.random.default_rng(11); MOTES = RNG.random((150, 4))
def dust(img, T, col=(150, 190, 255), k=1.0, drift=(8, -14)):
    lay = np.zeros_like(img)
    for x, y, s, b in MOTES:
        px = int((x * W + T * drift[0] * (.5 + s) + 14 * math.sin(T * .6 + y * 7)) % W); py = int((y * H + T * drift[1] * (.5 + s)) % H)
        v = (20 + 60 * b * b) * k; cv2.circle(lay, (px, py), 1 + int(s * 2.4), (col[0] * v / 255, col[1] * v / 255, col[2] * v / 255), -1, cv2.LINE_AA)
    return img + cv2.GaussianBlur(lay, (0, 0), 1.4)

def glow(img, x, y, r, a, col=(210, 245, 255)):
    if a <= 0: return img
    x0, x1 = int(max(0, x - 3 * r)), int(min(W, x + 3 * r)); y0, y1 = int(max(0, y - 3 * r)), int(min(H, y + 3 * r))
    if x1 <= x0 or y1 <= y0: return img
    d2 = ((XX[:, x0:x1] - x) ** 2 + (YY[y0:y1] - y) ** 2) / (r * r)
    g = (np.exp(-d2 * 2.2) * 1.0 + np.exp(-d2 * .35) * .35) * a
    img[y0:y1, x0:x1] += g[..., None] * np.array(col, np.float32)
    return img

HOT = (60, 150, 255); CORE = (200, 235, 255)     # BGR: orange plasma, white-yellow core
def plasma(img, x, y, dx, dy, size, T, a=1.0, seed=1, trail=3.2, sparks=60):
    """cropped wrapper: does the work only in the box around the plasma"""
    if a <= 0: return img
    n = math.hypot(dx, dy); ux, uy = dx / n, dy / n; ext = size * (trail * 1.3 + 2.5) + 60
    xs = [x + size * 2.5 + 60, x - size * 2.5 - 60, x - ux * ext, x + ux * size * 2.5]; ys = [y + size * 2.5 + 60, y - size * 2.5 - 60, y - uy * ext, y + uy * size * 2.5]
    x0, x1 = int(max(0, min(xs))), int(min(W, max(xs))); y0, y1 = int(max(0, min(ys))), int(min(H, max(ys)))
    if x1 - x0 < 4 or y1 - y0 < 4: return img
    img = img.copy(); sub = np.ascontiguousarray(img[y0:y1, x0:x1])
    img[y0:y1, x0:x1] = _plasma(sub, x - x0, y - y0, dx, dy, size, T, a, seed, trail, sparks)
    return glow(img, x, y, size * 1.4, .55 * a, (90, 170, 255))

def _plasma(img, x, y, dx, dy, size, T, a=1.0, seed=1, trail=3.2, sparks=60):
    """reentry plasma: a bright bow of shock-heated air on the leading side (direction dx,dy), a long flickering trail behind,
    and sparks streaming off. size in px ~ object radius."""
    if a <= 0: return img
    n = math.hypot(dx, dy); dx, dy = dx / n, dy / n; px, py = -dy, dx
    lay = np.zeros_like(img); rng = np.random.default_rng(seed)
    for k in range(26):   # trail blobs
        t = k / 25; fl = .75 + .25 * math.sin(T * 23 + k * 1.7)
        cx = x - dx * size * trail * t + px * size * .18 * math.sin(T * 9 + k); cy = y - dy * size * trail * t + py * size * .18 * math.sin(T * 9 + k)
        r = size * (.85 + .5 * t); v = (1 - t) ** 1.6 * fl
        cv2.circle(lay, (int(cx), int(cy)), int(r), (HOT[0] * v, HOT[1] * v, HOT[2] * v), -1, cv2.LINE_AA)
    bow = np.zeros_like(img)
    cv2.ellipse(bow, (int(x + dx * size * .35), int(y + dy * size * .35)), (int(size * 1.15), int(size * .55)), math.degrees(math.atan2(dy, dx)) + 90, 180, 360,
                CORE, int(size * .25), cv2.LINE_AA)
    img = img + cv2.GaussianBlur(lay, (0, 0), size * .45) * .9 * a + cv2.GaussianBlur(bow, (0, 0), size * .18) * 1.2 * a
    sp = np.zeros_like(img)
    P = rng.random((sparks, 4))
    for u, v, s, ph in P:
        t = (u + T * (1.2 + s)) % 1.0; off = (v - .5) * size * 1.6
        sx = x - dx * size * trail * 1.3 * t + px * off; sy = y - dy * size * trail * 1.3 * t + py * off
        L = 10 + 30 * s; b = (1 - t) * (180 + 75 * s)
        cv2.line(sp, (int(sx), int(sy)), (int(sx - dx * L), int(sy - dy * L)), (b * .55, b * .85, b), 2, cv2.LINE_AA)
    return img + cv2.GaussianBlur(sp, (0, 0), 1.2) * a + cv2.GaussianBlur(sp, (0, 0), 6) * .8 * a

def streaks(img, T, n=50, a=1.0, dirv=(-.45, 1.0), seed=4, col=(120, 200, 255), x0=0, x1=W, y0=0, y1=H):
    """falling debris streaks (meteor-like trails)"""
    if a <= 0: return img
    lay = np.zeros_like(img); rng = np.random.default_rng(seed); P = rng.random((n, 4)); d = np.array(dirv) / np.hypot(*dirv)
    for u, v, s, ph in P:
        t = (ph + T * (.35 + .4 * s)) % 1.0
        sx = x0 + u * (x1 - x0) + d[0] * t * (y1 - y0) * .9; sy = y0 + v * (y1 - y0) * .3 + d[1] * t * (y1 - y0) * .9
        L = 40 + 140 * s; b = 255 * math.sin(math.pi * t)
        cv2.line(lay, (int(sx), int(sy)), (int(sx - d[0] * L), int(sy - d[1] * L)), (col[0] * b / 255, col[1] * b / 255, col[2] * b / 255), 2 + int(2 * s), cv2.LINE_AA)
        cv2.circle(lay, (int(sx), int(sy)), 3 + int(3 * s), (b * .8, b * .95, b), -1, cv2.LINE_AA)
    return img + cv2.GaussianBlur(lay, (0, 0), 1.5) * a + cv2.GaussianBlur(lay, (0, 0), 8) * .9 * a

def wisps(img, T, a=1.0, dirv=(1, -.25), seed=2):
    """faint streaming air past the station (drag)"""
    lay = np.zeros_like(img); rng = np.random.default_rng(seed); P = rng.random((60, 3)); d = np.array(dirv) / np.hypot(*dirv)
    for u, v, s in P:
        t = (u + T * (.5 + .5 * s)) % 1.0; sx = -200 + t * (W + 400); sy = v * H + (sx - W / 2) * d[1] / d[0]
        L = 120 + 260 * s; cv2.line(lay, (int(sx), int(sy)), (int(sx - d[0] * L), int(sy - d[1] * L)), (255, 235, 210), 2, cv2.LINE_AA)
    return img + cv2.GaussianBlur(lay, (0, 0), 3) * .35 * a

def tint(img, col, a): return img * (1 - a) + (img.mean(2, keepdims=True) * np.array(col, np.float32) / 255) * a
def desat(img, a, dark=0.0): g = img.mean(2, keepdims=True); return (img * (1 - a) + g * a) * (1 - dark)
def vignette(img, a):
    m = np.clip(((XX / W - .5) ** 2 + (YY / H - .5) ** 2 * .45) * 3.2, 0, 1); return img * (1 - m[..., None] * a)
def blurdim(img, a):
    if a <= 0: return img
    b = cv2.GaussianBlur(img, (0, 0), 3 + 22 * a); return vignette(b * (1 - .55 * a), a)
def flash(img, a): return img + 255 * a

# ---------------- skia helpers
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
def text(c, s, x, y, size, col=(255, 255, 255), a=255, align='c', outline=True):
    f = skia.Font(E.TF, size); w = f.measureText(s); x0 = x - w / 2 if align == 'c' else (x - w if align == 'r' else x)
    if outline: c.drawString(s, x0, y, f, Pn((0, 0, 0), a * .85, 'stroke', size * .14))
    c.drawString(s, x0, y, f, Pn(col, a))
GOLD = (255, 205, 70); CYAN = (110, 215, 255); WHITE = (255, 255, 255); RED = (255, 70, 60); GREY = (200, 200, 200)

def route(img, u, T, kbargs):
    """coast-to-coast path NY -> LA drawn on, with a glowing dot (the station) and a minute counter (great circle ~2,450 mi at 17,500 mph = ~8.4 min)"""
    pts = [kb_pt(p[0], p[1], *kbargs)[:2] for p in fx('us', 'route', [[.7, .4], [.3, .45]])]
    p = clamp(u * 1.25); n = len(pts) - 1; m = p * n; k = int(min(m, n - 1)); fr = m - k
    surf, c = sk_begin(img)
    path = skia.Path(); path.moveTo(*pts[0])
    for q in pts[1:k + 1]: path.lineTo(*q)
    hx, hy = pts[k][0] + (pts[k + 1][0] - pts[k][0]) * fr, pts[k][1] + (pts[k + 1][1] - pts[k][1]) * fr; path.lineTo(hx, hy)
    c.drawPath(path, Pn((255, 190, 60), 120, 'stroke', 22, blur=10)); c.drawPath(path, Pn((255, 222, 90), 255, 'stroke', 8))
    c.drawCircle(hx, hy, 26, Pn((255, 255, 255), 200, blur=12)); c.drawCircle(hx, hy, 12, Pn((255, 255, 255), 255))
    for (x, y), lab in ((pts[0], 'NEW YORK'), (pts[-1], 'LOS ANGELES')):
        c.drawCircle(x, y, 10, Pn(GOLD, 255)); text(c, lab, min(max(x, 170), W - 170), y - 30, 40, WHITE, 255)
    mins = 8.4 * p
    c.drawRoundRect(skia.Rect.MakeXYWH(W / 2 - 230, H * .2, 460, 150), 30, 30, Pn((10, 14, 22), 210))
    text(c, f'{int(mins)}:{int((mins % 1) * 60):02d}', W / 2, H * .2 + 112, 104, GOLD, 255, outline=False)
    return sk_end(surf)

def ticket(img, u, T, paid=0.0):
    """the littering ticket Esperance issued to NASA (ILLUSTRATION of the notice: $400 fine for littering, 1979)"""
    surf, c = sk_begin(img); a = 255 * eout(u * 2.5)
    c.save(); c.translate(W / 2, H * .36); c.rotate(-4 + 2 * math.sin(T * .8)); s = .9 + .1 * eout(u * 2.5); c.scale(s, s)
    c.drawRoundRect(skia.Rect.MakeXYWH(-370, -300, 740, 560), 18, 18, Pn((0, 0, 0), a * .5, blur=24))
    c.drawRoundRect(skia.Rect.MakeXYWH(-360, -310, 720, 560), 12, 12, Pn((246, 240, 222), a))
    c.drawRect(skia.Rect.MakeXYWH(-360, -310, 720, 96), Pn((170, 40, 35), a))
    text(c, 'INFRINGEMENT NOTICE', 0, -246, 52, WHITE, a, outline=False)
    text(c, 'SHIRE OF ESPERANCE', 0, -150, 46, (40, 40, 45), a, outline=False)
    c.drawLine(-300, -120, 300, -120, Pn((120, 120, 120), a, 'stroke', 2))
    text(c, 'TO: NASA', -300, -60, 44, (40, 40, 45), a, 'l', outline=False)
    text(c, 'OFFENCE: LITTERING', -300, 0, 44, (40, 40, 45), a, 'l', outline=False)
    text(c, 'YEAR: 1979', -300, 60, 44, (40, 40, 45), a, 'l', outline=False)
    text(c, 'FINE: $400', 0, 180, 100, (170, 40, 35), a, outline=False)
    if paid > 0:
        k = eout(paid * 2); c.save(); c.translate(150, 40); c.rotate(-18); sc = 1.6 - .6 * k; c.scale(sc, sc)
        c.drawRoundRect(skia.Rect.MakeXYWH(-210, -80, 420, 160), 20, 20, Pn((30, 150, 70), 255 * k, 'stroke', 14))
        text(c, 'PAID', 0, 10, 96, (30, 150, 70), 255 * k, outline=False); text(c, '2009', 0, 64, 48, (30, 150, 70), 255 * k, outline=False)
        c.restore()
    c.restore(); return sk_end(surf)

def cars(img, u, T):
    """weight comparison: rows of car icons (each icon = 10 cars), 32 icons = 320 cars"""
    surf, c = sk_begin(img)
    for k in range(32):
        r, q = divmod(k, 8); x = W * .5 + (q - 3.5) * 118; y = H * .36 + r * 88; a = 255 * eout((u * 1.4 - k / 40) * 4)
        if a <= 0: continue
        body = skia.Path(); body.moveTo(x - 48, y + 10); body.lineTo(x - 44, y - 10); body.lineTo(x - 22, y - 12); body.lineTo(x - 10, y - 30)
        body.lineTo(x + 18, y - 30); body.lineTo(x + 32, y - 12); body.lineTo(x + 48, y - 8); body.lineTo(x + 48, y + 10); body.close()
        c.drawPath(body, Pn((255, 196, 60), a)); c.drawCircle(x - 26, y + 12, 11, Pn((25, 25, 30), a)); c.drawCircle(x + 28, y + 12, 11, Pn((25, 25, 30), a))
    text(c, 'EACH ICON = 10 CARS', W / 2, H * .36 + 4 * 88 + 20, 40, GREY, 255 * eout(u * 3))
    return sk_end(surf)

def marker(img, x, y, T, a=1.0, col=(80, 220, 255)):
    surf, c = sk_begin(img)
    for k in range(3):
        t = (T * .7 + k / 3) % 1.0; c.drawCircle(x, y, 20 + 110 * t, Pn(col, 255 * a * (1 - t), 'stroke', 5))
    c.drawCircle(x, y, 14, Pn(col, 255 * a)); c.drawCircle(x, y, 26, Pn(col, 160 * a, blur=10))
    return sk_end(surf)

def iss_icon(img, x, y, s, a=1.0):
    """tiny white station glyph (truss + 8 wings + modules) with a soft glow"""
    surf, c = sk_begin(img); p = Pn((255, 255, 255), 255 * a)
    c.drawCircle(x, y, 40 * s, Pn((200, 230, 255), 110 * a, blur=16))
    c.drawRect(skia.Rect.MakeXYWH(x - 60 * s, y - 3 * s, 120 * s, 6 * s), p)
    for dx in (-55, -42, 42, 55):
        c.drawRect(skia.Rect.MakeXYWH(x + dx * s - 4 * s, y - 26 * s, 8 * s, 22 * s), p); c.drawRect(skia.Rect.MakeXYWH(x + dx * s - 4 * s, y + 4 * s, 8 * s, 22 * s), p)
    c.drawRect(skia.Rect.MakeXYWH(x - 5 * s, y - 24 * s, 10 * s, 48 * s), p)
    return sk_end(surf)

def ring_pct(img, u):
    """10-40% of the mass survives: a ring with the 10-40% band filled"""
    surf, c = sk_begin(img); cx, cy, R = W / 2, H * .36, 220; a = 255 * eout(u * 3)
    c.drawCircle(cx, cy, R + 50, Pn((5, 8, 16), 190 * a / 255))
    c.drawCircle(cx, cy, R, Pn((70, 80, 100), a, 'stroke', 34))
    oval = skia.Rect.MakeXYWH(cx - R, cy - R, 2 * R, 2 * R); p = clamp(u * 1.6)
    c.drawArc(oval, -90, 36 * min(1, p * 2), False, Pn((255, 196, 60), a, 'stroke', 34))
    if p > .5: c.drawArc(oval, -90 + 36, 108 * (p - .5) * 2, False, Pn((255, 196, 60), a * .45, 'stroke', 34))
    text(c, '10-40%', cx, cy + 30, 104, GOLD, a); text(c, 'CAN SURVIVE', cx, cy + 100, 40, WHITE, a)
    return sk_end(surf)

def shots():
    ISS = fx('fire', 'iss', (.45, .5)); WL = fx('fire', 'wing_l', (.25, .45)); WR = fx('fire', 'wing_r', (.75, .5))
    SKY = fx('skylab', 'skylab', (.55, .55)); ESP = fx('skylab', 'esperance', (.42, .71)); TUG = fx('tug', 'tug', (.8, .45)); TE = fx('tug', 'tug_end', (.9, .46))
    NEMO = fx('nemo', 'nemo', (.5, .6)); FL, FR = fx('field', 'field_l', (.1, .5)), fx('field', 'field_r', (.9, .5))
    def fire(T, u, z0, z1, c0=ISS, c1=ISS, a=1.0, shake=.5, size=150):
        img = kb('fire', u, z0, z1, c0, c1, shake=shake, T=T)
        x, y, z = kb_pt(ISS[0], ISS[1], u, z0, z1, c0, c1)
        img = plasma(img, x + 40 * z, y + 30 * z, .55, .8, size * z, T, a)
        return dust(img, T, (120, 180, 255), .3)
    def breakup(T, u, z0, z1, c0=(.5, .45), c1=(.5, .45), a=1.0):
        img = kb('breakup', u, z0, z1, c0, c1, shake=.6, T=T)
        for k, p in enumerate(fx('breakup', 'pieces', [])[:9]):
            x, y, z = kb_pt(p[0], p[1], u, z0, z1, c0, c1); img = plasma(img, x, y, .55, .8, (26 + 10 * (k % 3)) * z, T, a, seed=k + 3, trail=4, sparks=14)
        return img
    def orbit(T, u, z0, z1, c0=(.5, .45), c1=(.5, .45), name='orbit'): return dust(kb(name, u, z0, z1, c0, c1), T, k=.35)
    def skylab(T, u, z0, z1, c0=SKY, c1=SKY):
        img = kb('skylab', u, z0, z1, c0, c1, shake=.3, T=T); x, y, z = kb_pt(SKY[0], SKY[1], u, z0, z1, c0, c1)
        return plasma(img, x + 20 * z, y + 30 * z, .45, .9, 110 * z, T, 1.0, seed=7)
    def outback(T, u, z0, z1, c0=(.5, .5), c1=(.5, .5)): return dust(kb('outback', u, z0, z1, c0, c1), T, (190, 210, 235), .35, (14, -3))
    def tug(T, u, z0, z1, c0=(.6, .45), c1=(.62, .45)):
        img = orbit(T, u, z0, z1, c0, c1, 'tug'); x, y, z = kb_pt(TE[0], TE[1], u, z0, z1, c0, c1); tx, ty, _ = kb_pt(TUG[0], TUG[1], u, z0, z1, c0, c1)
        d = (x - tx, y - ty); n = math.hypot(*d) or 1
        for k in range(6):
            img = glow(img, x + d[0] / n * k * 26 * z, y + d[1] / n * k * 26 * z, (34 - 4 * k) * z, (.9 - .12 * k) * (.85 + .15 * math.sin(T * 30 + k)), (120, 200, 255))
        return img
    def nemo(T, u, z0, z1, c0=NEMO, c1=NEMO, a=1.0):
        img = kb('nemo', u, z0, z1, c0, c1); x, y, z = kb_pt(NEMO[0], NEMO[1], u, z0, z1, c0, c1)
        return marker(img, x, y, T, a)
    def field(T, u, z0, z1, c0=(.5, .45), c1=(.5, .45)):
        img = vignette(kb('field', u, z0, z1, c0, c1), .5)
        surf, c = sk_begin(img); a = 255 * eout(u * 3)
        for (p0, p1, yy, lab, col) in ((fx('field', 'iss_l'), fx('field', 'iss_r'), -.085, 'STATION: 357 FT', GOLD), (FL, FR, .06, 'FIELD: 360 FT', CYAN)):
            x0, y0, _ = kb_pt(p0[0], p0[1] + yy, u, z0, z1, c0, c1); x1, y1, _ = kb_pt(p1[0], p1[1] + yy, u, z0, z1, c0, c1)
            c.drawLine(x0, y0, x1, y1, Pn(col, a, 'stroke', 6))
            for xx, yy2 in ((x0, y0), (x1, y1)): c.drawLine(xx, yy2 - 22, xx, yy2 + 22, Pn(col, a, 'stroke', 6))
            text(c, lab, (x0 + x1) / 2, (y0 + y1) / 2 - 24, 46, col, a)
        return sk_end(surf)
    def track(T, u, z0, z1, c0=(.5, .5), c1=(.5, .5)):
        img = kb('track', u, z0, z1, c0, c1); return img * (1 + .12 * math.sin(T * 4) ** 2)
    def us(T, u, z0, z1, c0=(.5, .5), c1=(.5, .5)): return kb('us', u, z0, z1, c0, c1)
    return {
     0: [(0, lambda T, u: fire(T, u, 1.28, 1.42))],
     1: [(0, lambda T, u: wisps(orbit(T, u, 1.0, 1.12, (.5, .5), (.5, .45)), T, .5)), (1.7, lambda T, u: orbit(T, u, 1.05, 1.2, (.5, .45), (.48, .4), 'hero'))],
     2: [(0, lambda T, u: field(T, u, 1.18, 1.05, (.5, .42), (.5, .42)))],
     3: [(0, lambda T, u: orbit(T, u, 1.3, 1.45, (.5, .45), (.52, .42), 'hero')), (1.2, lambda T, u: cars(blurdim(orbit(T, u, 1.1, 1.2, (.5, .5), (.5, .45), 'hero'), .7), u, T))],
     4: [(0, lambda T, u: wisps(orbit(T, u, 1.15, 1.3, (.5, .4), (.55, .42)), T, 1.0, (1, -.15))), (2.0, lambda T, u: us(T, u, 1.0, 1.1))],
     5: [(0, lambda T, u: route(us(T, u, 1.0, 1.06, (.5, .47), (.5, .45)), u, T, (u, 1.0, 1.06, (.5, .47), (.5, .45))))],
     6: [(0, lambda T, u: wisps(orbit(T, u, 1.0, 1.1, (.5, .45), (.5, .5)), T, 1.4)), (2.3, lambda T, u: wisps(orbit(T, u, 1.4, 1.55, (.5, .42), (.5, .47), 'hero'), T, 1.2))],
     7: [(0, lambda T, u: orbit(T, u, 1.0, 1.15, (.55, .45), (.6, .42), 'escape')), (2.5, lambda T, u: desat(orbit(T, u, 1.15, 1.25, (.5, .45), (.5, .4), 'hero'), .6, .25))],
     8: [(0, lambda T, u: fire(T, u, 1.0, 1.12, (.5, .5), (.5, .48), shake=.3)), (2.4, lambda T, u: fire(T, u, 1.7, 1.9, size=170))],
     9: [(0, lambda T, u: fire(T, u, 2.0, 2.3, WL, WL, shake=.9)), (1.2, lambda T, u: flash(fire(T, u, 2.0, 2.2, WR, WR, shake=1.0), .5 * max(0, 1 - T * 4)))],
     10: [(0, lambda T, u: flash(breakup(T, u, 1.0, 1.1), .6 * max(0, 1 - T * 3))), (1.8, lambda T, u: breakup(T, u, 1.5, 1.65, (.5, .45), (.5, .5)))],
     11: [(0, lambda T, u: streaks(breakup(T, u, 1.1, 1.0), T, 30, .8)), (2.2, lambda T, u: ring_pct(blurdim(breakup(T, u, 1.0, 1.05), .75), u))],
     12: [(0, lambda T, u: streaks(desat(kb('track', u, 1.4, 1.55), .3, .45), T, 70, 1.0, (-.3, 1.0), 8))],
     13: [(0, lambda T, u: track(T, u, 1.0, 1.08)), (1.8, lambda T, u: track(T, u, 1.25, 1.35, (.5, .4), (.5, .45)))],
     14: [(0, lambda T, u: skylab(T, u, 1.0, 1.1)), (2.0, lambda T, u: skylab(T, u, 1.6, 1.75)), (3.9, lambda T, u: glow(kb('skylab', u, 1.2, 1.3, ESP, ESP), *kb_pt(ESP[0], ESP[1], u, 1.2, 1.3, ESP, ESP)[:2], 60, .8 + .2 * math.sin(T * 6), (80, 200, 255)))],
     15: [(0, lambda T, u: outback(T, u, 1.0, 1.1, (.5, .5), (.48, .52))), (2.3, lambda T, u: outback(T, u, 1.5, 1.65, (.45, .55), (.45, .57)))],
     16: [(0, lambda T, u: ticket(blurdim(outback(T, u, 1.1, 1.15), .7), u, T))],
     17: [(0, lambda T, u: ticket(blurdim(outback(T, u, 1.15, 1.2), .7), 1, T + 5, clamp((T - .6) / 1.2)))],
     18: [(0, lambda T, u: tug(T, u, 1.0, 1.1)), (2.6, lambda T, u: tug(T, u, 1.8, 2.0, TUG, TUG))],
     19: [(0, lambda T, u: nemo(T, u, 1.0, 1.08, (.5, .5), (.5, .52))), (2.4, lambda T, u: nemo(T, u, 1.35, 1.5)),
          (4.6, lambda T, u: iss_icon(nemo(T, u, 1.15, 1.2), W * .5 + 140 * math.sin(u * 1.5), H * .27, 1.2))],
     20: [(0, lambda T, u: fire(T, u, 1.05, 1.28, (.5, .48), ISS, a=clamp(u * 1.6)))],
    }[idx]

YEL, WH, GR = [255, 222, 40], [255, 255, 255], [200, 200, 200]
ILL = {'type': 'label', 'text': 'ILLUSTRATION', 'color': GR, 'pos': [.8, .955], 'from': .1}
OV = {
 0: [{'type': 'hook', 'text': 'WHAT IF THE|SPACE STATION FELL?'}, dict(ILL, instant=True)],
 1: [{'type': 'label', 'text': 'INTERNATIONAL SPACE STATION', 'color': WH, 'pos': [.5, .14], 'from': .2},
     {'type': 'label', 'text': 'NASA 3D MODEL · NOT TO SCALE', 'color': GR, 'pos': [.6, .955], 'from': .1}],
 2: [{'type': 'label', 'text': 'TO SCALE', 'color': YEL, 'pos': [.5, .12], 'from': .2}],
 3: [{'type': 'badge', 'value': '925,335', 'unit': 'lb', 'pos': [.5, .2], 'from': .3}],
 4: [{'type': 'badge', 'value': '17,500', 'unit': 'mph', 'pos': [.5, .15], 'from': .4},
     {'type': 'label', 'text': '~250 MILES UP · 16 ORBITS A DAY', 'color': WH, 'pos': [.5, .23], 'from': .9}],
 5: [{'type': 'label', 'text': 'COAST TO COAST', 'color': WH, 'pos': [.5, .14], 'from': .2}],
 6: [{'type': 'label', 'text': 'THIN AIR = DRAG', 'color': YEL, 'pos': [.5, .14], 'from': .4},
     {'type': 'label', 'text': 'IT SINKS WITHOUT BOOSTS', 'color': WH, 'pos': [.5, .2], 'from': 2.4}],
 7: [{'type': 'label', 'text': 'CREW CAPSULE = LIFEBOAT', 'color': YEL, 'pos': [.5, .14], 'from': .4}, ILL],
 8: [{'type': 'label', 'text': 'SQUEEZED AIR GLOWS', 'color': YEL, 'pos': [.5, .14], 'from': .3},
     {'type': 'label', 'text': 'HOTTER THAN LAVA', 'color': [255, 140, 60], 'pos': [.5, .2], 'from': 2.6}, ILL],
 9: [{'type': 'label', 'text': 'SOLAR WINGS RIP OFF', 'color': YEL, 'pos': [.5, .14], 'from': .3}, ILL],
 10: [{'type': 'badge', 'value': '~50', 'unit': 'miles up', 'pos': [.5, .15], 'from': .4}, ILL],
 11: [{'type': 'label', 'text': 'MOST BURNS UP', 'color': WH, 'pos': [.5, .14], 'from': .3}, ILL],
 12: [{'type': 'badge', 'value': 'TENS', 'unit': 'of tons', 'pos': [.5, .2], 'from': .3}, ILL],
 13: [{'type': 'label', 'text': 'ITS REAL PATH: 51.6 N TO 51.6 S', 'color': YEL, 'pos': [.5, .14], 'from': .3},
      {'type': 'label', 'text': 'MOST OF HUMANITY LIVES UNDER IT', 'color': WH, 'pos': [.5, .2], 'from': 1.6}],
 14: [{'type': 'datestamp', 'text': 'SKYLAB · JULY 1979', 'from': .2},
      {'type': 'badge', 'value': '77', 'unit': 'metric tons', 'pos': [.5, .25], 'from': 1.6},
      {'type': 'label', 'text': 'ESPERANCE', 'color': [110, 215, 255], 'pos': [.5, .82], 'from': 4.0},
      {'type': 'label', 'text': 'NASA 3D MODEL · ILLUSTRATION', 'color': GR, 'pos': [.6, .955], 'from': .1}],
 15: [{'type': 'datestamp', 'text': 'WESTERN AUSTRALIA', 'from': .2},
      {'type': 'label', 'text': 'NOBODY WAS HURT', 'color': YEL, 'pos': [.5, .2], 'from': 2.5}, ILL],
 16: [{'type': 'label', 'text': '$400 FOR LITTERING', 'color': YEL, 'pos': [.5, .12], 'from': .5}, ILL],
 17: [{'type': 'label', 'text': 'PAID BY A U.S. RADIO HOST', 'color': YEL, 'pos': [.5, .12], 'from': .5}, ILL],
 18: [{'type': 'label', 'text': 'U.S. DEORBIT VEHICLE (SPACEX)', 'color': YEL, 'pos': [.5, .14], 'from': .3},
      {'type': 'badge', 'value': '~2030', 'unit': '', 'pos': [.5, .22], 'from': 3.4}, ILL],
 19: [{'type': 'label', 'text': 'POINT NEMO', 'color': [110, 215, 255], 'pos': [.5, .14], 'from': .3},
      {'type': 'label', 'text': '1,670 MILES FROM THE NEAREST LAND', 'color': WH, 'pos': [.5, .2], 'from': 1.6},
      {'type': 'label', 'text': 'ASTRONAUTS: ~250 MILES OVERHEAD', 'color': YEL, 'pos': [.5, .35], 'from': 4.7}],
 20: [{'type': 'cta'}],
}[idx]

if __name__ == '__main__':
    out = f'{ROOT}/s{idx}'; os.makedirs(out, exist_ok=True)
    SH = shots(); bounds = [s for s, _ in SH] + [D + PAD]
    only = [int(a) for a in sys.argv[2:]]
    for f in (only or range(1, NF + 1)):
        T = (f - 1) / FPS - .35
        Tc = max(T, 0); k = max(j for j in range(len(SH)) if SH[j][0] <= Tc or j == 0)
        t0, t1 = bounds[k], bounds[k + 1]; u = (Tc - t0) / max(t1 - t0, .1)
        img = SH[k][1](T - t0 + (.35 if k == 0 else 0), u)
        cv2.imwrite(f'{out}/f_{f:04d}.png', np.clip(img, 0, 255).astype(np.uint8), [cv2.IMWRITE_PNG_COMPRESSION, 1])
    json.dump({'frames': NF, 'overlays': OV}, open(f'{out}/meta.json', 'w'))
    print('scene', idx, NF)
