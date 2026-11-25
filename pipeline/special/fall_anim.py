"""Animate every scene of the WYR (fall from a plane into snow or the ocean) over its Cycles plates, with 2D science graphics.
python3 fall_anim.py <scene> [frames...]  ->  wyrfall/s<scene>/f_####.png + meta.json (overlays read by compose.py)"""
import sys, math, json, os
sys.path.insert(0, '/home/claude/pro')
import numpy as np, cv2, skia
import engine as E
ROOT = '/home/claude/b3d/wyrfall'; CFG = json.load(open(f'{ROOT}/topic.json'))
FPS = 24; PAD = .75; idx = int(sys.argv[1]); D = CFG['durs'][idx]; NF = int(math.ceil((D + PAD) * FPS))
W, H = 1080, 1920
ease = lambda t: .5 - .5 * math.cos(math.pi * min(max(t, 0), 1))
eout = lambda t: 1 - (1 - min(max(t, 0), 1)) ** 3
clamp = lambda t: min(max(t, 0), 1)
GOLD = (255, 205, 70); WHITE = (255, 255, 255); RED = (240, 80, 60); ICE = (170, 225, 255); SEA = (90, 190, 255); ORANGE = (255, 140, 50)
A_COL = (225, 70, 70); B_COL = (60, 130, 235)

GRADE = {   # one palette: deep navy/teal night + warm accents (BGR multipliers)
    'forest': (1.0, .98, .96), 'crater': (1.05, 1.0, .97), 'ocean': (1.0, 1.0, 1.0), 'sea': (1.0, .98, .98), 'bomber': (1.05, 1.0, .95),
    'wreck': (1.08, 1.0, .9), 'europe': (1, 1, 1)}
PL = {}
def plate(name):
    if name not in PL:
        im = cv2.imread(f'{ROOT}/plates/{name}.png')[..., :3]
        im = cv2.resize(im, (W, H), interpolation=cv2.INTER_CUBIC).astype(np.float32) * np.float32(GRADE[name])
        if name == 'wreck':   # dusk grade: cool shadows, keep the warm sunset rim
            t = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]; im = im * (.78 + .1 * t) + np.float32((18, 8, 0)) * (1 - t)
        PL[name] = np.clip(im, 0, 255)
    return PL[name]
PINS = [float(v) for v in open(f'{ROOT}/plates/europe.txt').read().split()]

def kb(name, u, z0, z1, c0=(.5, .5), c1=(.5, .5), img=None):
    im = plate(name) if img is None else img; t = ease(u); z = z0 + (z1 - z0) * t
    cx = (c0[0] + (c1[0] - c0[0]) * t) * W; cy = (c0[1] + (c1[1] - c0[1]) * t) * H
    M = np.float32([[z, 0, W / 2 - cx * z], [0, z, H / 2 - cy * z]])
    return cv2.warpAffine(im, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT), (z, cx, cy)

# ---------------- sprites (Leo = "you"; a dark silhouette = a real person we don't depict)
SP = {}
def sprite_src(name, sil=False):
    k = (name, sil)
    if k not in SP:
        im = cv2.imread(f'{ROOT}/plates/{name}.png', cv2.IMREAD_UNCHANGED).astype(np.float32)
        ys, xs = np.where(im[..., 3] > 8); im = im[ys.min() - 4:ys.max() + 4, xs.min() - 4:xs.max() + 4]
        rgb, a = im[..., :3], im[..., 3:] / 255
        if sil:   # near-black figure with a warm fire rim on one side
            er = cv2.erode((a[..., 0] > .5).astype(np.uint8), np.ones((9, 9), np.uint8)).astype(np.float32)[..., None]
            rim = np.clip(a - er, 0, 1); rgb = rgb * .0 + np.float32((14, 12, 12)) * (1 - rim) + np.float32((60, 150, 255)) * rim
        SP[k] = (rgb, a)
    return SP[k]

def sprite(img, name, cx, cy, h, rot=0.0, sil=False, blur=0):
    rgb, a = sprite_src(name, sil); s = h / rgb.shape[0]
    M = cv2.getRotationMatrix2D((rgb.shape[1] / 2, rgb.shape[0] / 2), rot, s)
    M[0, 2] += cx - rgb.shape[1] / 2; M[1, 2] += cy - rgb.shape[0] / 2
    r = cv2.warpAffine(rgb, M, (W, H), flags=cv2.INTER_LINEAR); al = cv2.warpAffine(a, M, (W, H), flags=cv2.INTER_LINEAR)
    if al.ndim == 2: al = al[..., None]
    if blur: r = cv2.GaussianBlur(r, (0, 0), blur); al = cv2.GaussianBlur(al, (0, 0), blur)[..., None] if al.ndim == 2 else cv2.GaussianBlur(al, (0, 0), blur).reshape(H, W, 1)
    return img * (1 - al) + r * al

def flail(T): return 7 * math.sin(T * 9) + 3 * math.sin(T * 23)

rng = np.random.default_rng(5); STREAK = rng.random((140, 4)); FLAKE = rng.random((260, 4))
def streaks(img, T, k=1.0, speed=2600):
    """wind lines rushing UP past the camera: we are falling at terminal speed"""
    lay = np.zeros_like(img)
    for x, y, s, b in STREAK:
        py = (y * (H + 600) - T * speed * (.5 + s)) % (H + 600) - 300; px = x * W; L = 80 + 260 * s; v = (25 + 110 * b * b) * k
        cv2.line(lay, (int(px), int(py)), (int(px), int(py + L)), (v, v, v * .95), 1 + int(s * 2.5), cv2.LINE_AA)
    return img + cv2.GaussianBlur(lay, (0, 0), 1.2)

def snowfall(img, T, k=1.0, drift=40, up=0):
    lay = np.zeros_like(img)
    for x, y, s, b in FLAKE:
        px = (x * W + T * drift * (.4 + s) + 20 * math.sin(T + y * 9)) % W; py = (y * H + T * (90 + 140 * s) * (1 if not up else -up)) % H
        v = (40 + 150 * b) * k; cv2.circle(lay, (int(px), int(py)), 1 + int(s * 3), (v, v, v), -1, cv2.LINE_AA)
    return img + cv2.GaussianBlur(lay, (0, 0), 1.0)

def puff(img, T, cx, cy, k=1.0):
    """burst of powder snow thrown up by an impact"""
    lay = np.zeros_like(img); t = max(T, 0)
    for x, y, s, b in FLAKE[:180]:
        ang = math.pi * (1.05 + .9 * x); sp = 300 + 900 * s; r = sp * (1 - math.exp(-t * 2.2)) / 2.2
        px = cx + math.cos(ang) * r; py = cy + math.sin(ang) * r * .7 + 140 * t * t
        v = 220 * b * math.exp(-t * .9) * k; cv2.circle(lay, (int(px), int(py)), 3 + int(9 * s), (v, v, v), -1, cv2.LINE_AA)
    return img + cv2.GaussianBlur(lay, (0, 0), 3)

def splash(img, T, cx, cy, k=1.0):
    """crown splash: white water thrown up and falling back"""
    lay = np.zeros_like(img); t = max(T, 0)
    for x, y, s, b in FLAKE[:220]:
        ang = math.pi * (1.1 + .8 * x); v0 = 700 + 1300 * s * b
        px = cx + math.cos(ang) * v0 * t * .55; py = cy + math.sin(ang) * v0 * t + 1400 * t * t
        if py > cy + 30: continue
        v = 235 * math.exp(-t * .8) * k; cv2.circle(lay, (int(px), int(py)), 3 + int(8 * s), (v, v * .98, v * .95), -1, cv2.LINE_AA)
    return img + cv2.GaussianBlur(lay, (0, 0), 2.5)

def bubbles(img, T, k=1.0):
    lay = np.zeros_like(img)
    for x, y, s, b in FLAKE[:120]:
        px = x * W + 14 * math.sin(T * 3 + y * 20); py = (y * H - T * (120 + 260 * s)) % H
        v = (60 + 160 * b) * k; cv2.circle(lay, (int(px), int(py)), 4 + int(12 * s), (v, v * .95, v * .8), 2, cv2.LINE_AA)
    return img + cv2.GaussianBlur(lay, (0, 0), .8)

def knockout(img, u):
    """vision dims and blurs (losing consciousness)"""
    b = cv2.GaussianBlur(img, (0, 0), 1 + 14 * u)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32); d = np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - H / 2) / H) ** 2)
    v = np.clip(1 - (d * 2.2) ** 2 * (.3 + 1.2 * u), 0, 1)[..., None]
    return b * v * (1 - .55 * u)

FIRE = None
def fire_pos():
    global FIRE
    if FIRE is None:
        im = plate('bomber'); m = (im[..., 2] > 200) & (im[..., 1] > 70) & (im[..., 1] < 200) & (im[..., 0] < 120)
        ys, xs = np.where(m); FIRE = (float(xs.mean()), float(ys.mean())) if len(xs) else (W * .5, H * .5)
    return FIRE

def burning(img, T, fx, fy, z=1.0):
    """flickering flames + embers streaming back from the burning wing"""
    lay = np.zeros_like(img); fl = .75 + .25 * math.sin(T * 17) * math.sin(T * 7.3)
    for j in range(5):   # flame tongues streaming back along the wing
        L = (40 + 30 * j) * z * (.8 + .3 * math.sin(T * 13 + j)); cv2.ellipse(lay, (int(fx - L * .7), int(fy - 6 * j * z)), (int(L), int((14 - 2 * j) * z + 3)), 8, 0, 360,
                    (20 * fl, (110 - 15 * j) * fl, (230 - 20 * j) * fl), -1, cv2.LINE_AA)
    for x, y, s, b in FLAKE[:90]:
        ph = (T * (.6 + s) + x) % 1; px = fx - (120 + 500 * ph) * z * (.8 + .4 * y); py = fy - (40 * ph + 30 * math.sin(T * 5 + x * 9)) * z + 200 * ph * ph * z * (y - .5)
        v = 255 * (1 - ph) * b; cv2.circle(lay, (int(px), int(py)), max(1, int((2 + 6 * s) * z * (1 - ph))), (v * .2, v * .6, v), -1, cv2.LINE_AA)
    return img + cv2.GaussianBlur(lay, (0, 0), 6 * z) * .7 + cv2.GaussianBlur(lay, (0, 0), 1.5) * .6

def split(a_img, b_img, u=1.0, tilt=-.12, dim=None):
    if dim == 'a': a_img = a_img * .35
    if dim == 'b': b_img = b_img * .35
    out = a_img.copy(); xs = (1 - eout(u)) * W
    yy = np.arange(H)[:, None]; xx = np.arange(W)[None, :]
    edge = W * .5 + (yy - H / 2) * tilt + xs
    m = (xx > edge)[..., None]; out = np.where(m, b_img, out)
    line = (np.abs(xx - edge) < 5)[..., None]; return np.where(line, np.float32(255), out)

# ---------------- skia helpers
def sk_begin(img):
    bgra = np.dstack([np.clip(img, 0, 255).astype(np.uint8), np.full((H, W), 255, np.uint8)])
    surf = skia.Surface(W, H); c = surf.getCanvas()
    c.drawImage(skia.Image.fromarray(np.ascontiguousarray(bgra), colorType=skia.kBGRA_8888_ColorType), 0, 0); return surf, c
def sk_end(surf): return surf.makeImageSnapshot().toarray()[..., :3].astype(np.float32)
def P(col, a=255, style='fill', w=0, blur=0):
    p = skia.Paint(AntiAlias=True, Color=skia.Color(int(col[0]), int(col[1]), int(col[2]), int(max(0, min(255, a)))))
    if style == 'stroke': p.setStyle(skia.Paint.kStroke_Style); p.setStrokeWidth(w); p.setStrokeCap(skia.Paint.kRound_Cap)
    if blur: p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, blur))
    return p
def text(c, s, x, y, size, col=WHITE, a=255, align='c'):
    f = skia.Font(E.TF, size); w = f.measureText(s); x0 = x - w / 2 if align == 'c' else (x - w if align == 'r' else x)
    c.drawString(s, x0, y, f, P((0, 0, 0), a * .85, 'stroke', size * .14)); c.drawString(s, x0, y, f, P(col, a))
def panel(c, x, y, w, h, a=200):
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, y, w, h), 34, 34), P((14, 20, 30), a))
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, y, w, h), 34, 34), P((120, 150, 180), 120, 'stroke', 3))

def pin(img, x, y, T, col=GOLD, a=1.0, label=None):
    surf, c = sk_begin(img)
    for k in range(3):
        ph = (T * .9 + k / 3) % 1; c.drawCircle(x, y, 18 + 120 * ph, P(col, 220 * (1 - ph) * a, 'stroke', 5))
    c.drawCircle(x, y, 13, P(col, 255 * a)); c.drawCircle(x, y, 40, P(col, 120 * a, blur=16))
    if label: text(c, label, x, y - 60, 50, col, 255 * a)
    return sk_end(surf)

def globe(k, T, u, z0, z1, label, col):
    px, py = PINS[2 * k], PINS[2 * k + 1]; t = ease(u); cc = (.5 + (px - .5) * t, .5 + (py + .05 - .5) * t)
    img, (z, cx, cy) = kb('europe', u, z0, z1, (.5, .5), cc)
    X = W / 2 + (px * W - cx) * z; Y = H / 2 + (py * H - cy) * z
    return pin(img, X, Y, T, col, min(1, T * 2), label if u > .25 else None)

# ---------------- science graphics
VT = 53.6   # terminal velocity, m/s (~120 mph, belly-down; Guinness: 117-125 mph, ~99% after 13-14 s)
def v_of(t): return VT * math.tanh(9.81 * t / VT)

def stopwatch(T, u, bg):
    img = bg * .45; surf, c = sk_begin(img)
    t = 14 * clamp(u * 1.25); v = v_of(t) * 2.23694
    cx, cy, R = W / 2, H * .385, 200
    c.drawCircle(cx, cy, R + 30, P((14, 20, 30), 230)); c.drawCircle(cx, cy, R + 30, P(WHITE, 200, 'stroke', 6))
    c.drawRect(skia.Rect.MakeXYWH(cx - 40, cy - R - 80, 80, 50), P(WHITE, 220))
    for k in range(60):
        a = k / 60 * 2 * math.pi; r0 = R - (26 if k % 5 == 0 else 12)
        c.drawLine(cx + math.sin(a) * r0, cy - math.cos(a) * r0, cx + math.sin(a) * R, cy - math.cos(a) * R, P(WHITE, 200, 'stroke', 4 if k % 5 == 0 else 2))
    arc = skia.Path(); arc.addArc(skia.Rect.MakeXYWH(cx - R + 40, cy - R + 40, 2 * R - 80, 2 * R - 80), -90, 360 * t / 60)
    c.drawPath(arc, P(GOLD, 230, 'stroke', 26))
    a = t / 60 * 2 * math.pi; c.drawLine(cx, cy, cx + math.sin(a) * (R - 30), cy - math.cos(a) * (R - 30), P(RED, 255, 'stroke', 8)); c.drawCircle(cx, cy, 16, P(RED))
    text(c, f'{t:4.1f} s', cx, cy + 125, 76, GOLD)
    text(c, f'{v:3.0f} mph', cx, cy + R + 105, 84, WHITE)
    return sk_end(surf)

def speedbars(T, u, bg):
    img = bg * .4; surf, c = sk_begin(img)
    x0, x1 = 120, 960; sc_ = (x1 - x0) / 130
    rows = [('HIGHWAY', 65, (150, 200, 255)), ('YOU, FALLING', 120, ORANGE)]
    for k, (lab, v, col) in enumerate(rows):
        y = H * .36 + k * 260; g = eout(u * 1.6 - k * .35)
        text(c, lab, x0, y - 30, 56, WHITE, 255 * clamp(u * 3 - k), 'l')
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x0, y, (x1 - x0), 80), 40, 40), P((30, 40, 55), 200))
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x0, y, max(80, v * sc_ * g), 80), 40, 40), P(col, 240))
        text(c, f'{int(round(v * g))} mph', x0 + max(80, v * sc_ * g) - 20, y + 62, 54, (20, 20, 20) if g > .6 else WHITE, 255 * clamp(g * 2), 'r')
    if u > .7:
        text(c, 'ALMOST 2x', W / 2, H * .36 + 560, 90, GOLD, 255 * clamp((u - .7) * 4))
    return sk_end(surf)

def gauge(T, u, bg):
    img = bg; surf, c = sk_begin(img)
    cx, cy, R = W / 2, H * .41, 270; v = 120 * eout(u * 1.3)
    c.drawCircle(cx, cy, R + 20, P((14, 20, 30), 200))
    arc = skia.Path(); arc.addArc(skia.Rect.MakeXYWH(cx - R, cy - R, 2 * R, 2 * R), 150, 240); c.drawPath(arc, P((60, 70, 90), 255, 'stroke', 28))
    arc2 = skia.Path(); arc2.addArc(skia.Rect.MakeXYWH(cx - R, cy - R, 2 * R, 2 * R), 150, 240 * v / 140); c.drawPath(arc2, P(ORANGE, 255, 'stroke', 28))
    for k in range(0, 141, 20):
        a = math.radians(150 + 240 * k / 140); text(c, str(k), cx + math.cos(a) * (R - 70), cy + math.sin(a) * (R - 70) + 16, 40, WHITE, 220)
    a = math.radians(150 + 240 * v / 140); c.drawLine(cx, cy, cx + math.cos(a) * (R - 40), cy + math.sin(a) * (R - 40), P(RED, 255, 'stroke', 10)); c.drawCircle(cx, cy, 20, P(RED))
    text(c, f'{v:3.0f}', cx, cy + 170, 120, GOLD); text(c, 'mph', cx, cy + 230, 50, WHITE)
    return sk_end(surf)

def molecules(T, u, bg, kind='water'):
    """box cross-section: water molecules packed shoulder to shoulder vs snow = ice crystals with mostly air between"""
    img = bg * .35; surf, c = sk_begin(img)
    x, y, w, h = 160, 760, 760, 330; panel(c, x - 30, y - 190, w + 60, h + 220)
    c.drawRect(skia.Rect.MakeXYWH(x, y, w, h), P((30, 50, 80) if kind == 'water' else (35, 40, 55), 230))
    push = (40 * math.sin(T * 9) * clamp(u * 3)) if kind == 'water' else 150 * eout(u * 1.2)
    if kind == 'water':
        r = 20; n = 0
        for j in range(int(h / (2 * r)) - 1):
            for i in range(int(w / (2 * r)) - 1):
                cx = x + 30 + i * 2 * r + (r if j % 2 else 0) + 3 * math.sin(T * 4 + i + j); cy = y + 34 + j * 2 * r * .9 + max(0, push) * .02
                if cx > x + w - 20: continue
                c.drawCircle(cx, cy, r * .82, P((90, 170, 255), 235)); n += 1
        c.drawRect(skia.Rect.MakeXYWH(x - 10, y - 50 + max(0, push) * .05, w + 20, 40), P((200, 200, 210), 255))   # piston barely moves
        text(c, 'WATER', W / 2, y - 125, 68, SEA)
        text(c, 'barely compresses', W / 2, y - 68, 44, WHITE)
    else:
        rr = np.random.default_rng(4); top = y + push
        for k in range(55):
            cx = x + 30 + rr.random() * (w - 60); cy = top + 30 + rr.random() * (h - push - 60)
            s = 14 + 22 * rr.random(); a0 = rr.random() * 3
            for arm in range(3):   # six-armed ice crystal
                a = a0 + arm * math.pi / 3; c.drawLine(cx - math.cos(a) * s, cy - math.sin(a) * s, cx + math.cos(a) * s, cy + math.sin(a) * s, P(ICE, 235, 'stroke', 4))
        c.drawRect(skia.Rect.MakeXYWH(x - 10, top - 50, w + 20, 40), P((200, 200, 210), 255))
        text(c, 'SNOW', W / 2, y - 125, 68, ICE)
        text(c, 'mostly air: it squashes', W / 2, y - 68, 44, WHITE)
    return sk_end(surf)

def stopping(T, u, bg):
    """same speed, two surfaces: the stop is short in water, longer in deep snow (diagram, not to scale)"""
    img = bg * .35; surf, c = sk_begin(img)
    cols = [('WATER', SEA, (25, 55, 95), .12), ('DEEP SNOW', ICE, (200, 210, 225), .55)]
    for k, (lab, col, fill, depth) in enumerate(cols):
        x = 110 + k * 460; w = 400; surf_y = 980
        text(c, lab, x + w / 2, 520, 64, col)
        c.drawRect(skia.Rect.MakeXYWH(x, surf_y, w, 560), P(fill, 230))
        t = clamp(u * 1.3); fall = 1 - min(1, t / .45)
        sink = 0 if t < .45 else depth * 500 * eout((t - .45) / (.12 if k == 0 else .45))
        by = surf_y - 360 * fall + sink - 120
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x + w / 2 - 50, by, 100, 120), 26, 26), P(ORANGE, 255))
        if t > .45:
            c.drawLine(x + w + 14, surf_y, x + w + 14, surf_y + sink, P(GOLD, 255, 'stroke', 7))
            text(c, 'short stop' if k == 0 else 'longer stop', x + w / 2, surf_y + 640, 52, RED if k == 0 else (120, 255, 160), 255 * clamp((t - .5) * 5))
            if k == 0 and t < .62: c.drawCircle(x + w / 2, surf_y, 120 * (t - .45) / .17 + 20, P(WHITE, 255 * (1 - (t - .45) / .17), 'stroke', 10))
    text(c, 'diagram, not to scale', W / 2, 1720, 34, (180, 190, 205), 200)
    return sk_end(surf)

def graph(T, u, bg):
    """speed vs time: the fall is fine; the sudden stop at the end is what hurts"""
    img = bg * .35; surf, c = sk_begin(img)
    x0, x1, y0, y1 = 150, 940, 1180, 620; panel(c, 90, 470, 900, 860)
    c.drawLine(x0, y0, x1, y0, P(WHITE, 220, 'stroke', 4)); c.drawLine(x0, y0, x0, y1 - 30, P(WHITE, 220, 'stroke', 4))
    text(c, 'speed', x0 + 10, y1 - 50, 42, WHITE, 220, 'l'); text(c, 'time', x1, y0 + 60, 42, WHITE, 220, 'r')
    path = skia.Path(); n = 120; end = clamp(u * 1.4)
    for k in range(int(n * end) + 1):
        f = k / n; tt = f * 60
        v = v_of(tt) if f < .93 else v_of(56) * max(0, 1 - (f - .93) / .012)
        X = x0 + f * (x1 - x0); Y = y0 - v / 60 * (y0 - y1)
        path.moveTo(X, Y) if k == 0 else path.lineTo(X, Y)
    c.drawPath(path, P(GOLD, 255, 'stroke', 9))
    if end > .95:
        c.drawCircle(x0 + .935 * (x1 - x0), (y0 + y1) / 2, 80, P(RED, 255, 'stroke', 8))
        text(c, 'THE STOP', x0 + .8 * (x1 - x0), y1 - 20, 64, RED, 255 * clamp((end - .95) * 20))
    return sk_end(surf)

# true-scale altitude chart (feet): 0 at y=1560, 35,000 ft at y=520
def ay(ft): return 1560 - ft / 35000 * 1040
def altitude(T, u, bg, phase):
    img = bg * .35; surf, c = sk_begin(img)
    for ft in range(0, 35001, 5000):
        y = ay(ft); c.drawLine(110, y, 990, y, P(WHITE, 50, 'stroke', 2)); text(c, f'{ft // 1000}k ft' if ft else '0', 100, y + 12, 34, (200, 210, 225), 200, 'r')
    # Everest (29,032 ft) as a mountain silhouette, true height on the same axis
    ev = clamp(u * 2.5) if phase >= 1 else 0
    if ev > 0:
        m = skia.Path(); m.moveTo(560, ay(0)); m.lineTo(700, ay(18000)); m.lineTo(745, ay(24000)); m.lineTo(790, ay(29032)); m.lineTo(860, ay(22000)); m.lineTo(1000, ay(0)); m.close()
        c.drawPath(m, P((110, 120, 140), 230 * ev)); c.drawPath(m, P(WHITE, 160 * ev, 'stroke', 3))
        text(c, 'EVEREST', 790, ay(29032) - 60, 48, WHITE, 255 * ev); text(c, '29,032 ft', 790, ay(29032) - 15, 40, (220, 225, 235), 255 * ev)
    bars = [(250, 18000, 'ALKEMADE', '18,000 ft', ORANGE, 1.0 if phase >= 1 else eout(u * 1.6)),
            (440, 33333, 'VULOVIĆ', '33,333 ft', GOLD, eout(u * 1.4 - .3) if phase == 0 else 1.0)]
    for x, ft, lab, val, col, g in bars:
        if g <= 0: continue
        top = ay(0) - (ay(0) - ay(ft)) * g
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeLTRB(x - 55, top, x + 55, ay(0)), 14, 14), P(col, 235))
        text(c, val, x, top - 20, 44, col, 255 * g); text(c, lab, x, ay(0) + 60, 40, WHITE, 255 * g)
    return sk_end(surf)

# ---------------- scene table
def shots():
    def forest(T, u, z0, z1, c0=(.5, .55), c1=(.5, .55)): return snowfall(kb('forest', u, z0, z1, c0, c1)[0], T, .7)
    def ocean(T, u, z0, z1, c0=(.5, .6), c1=(.5, .6)): return kb('ocean', u, z0, z1, c0, c1)[0]
    def sea(T, u, z0, z1, c0=(.5, .55), c1=(.5, .55)): return kb('sea', u, z0, z1, c0, c1)[0]
    def crater(T, u, z0, z1, c0=(.5, .5), c1=(.5, .5)): return snowfall(kb('crater', u, z0, z1, c0, c1)[0], T, .6)
    def wreck(T, u, z0, z1, c0=(.5, .5), c1=(.5, .5)): return snowfall(kb('wreck', u, z0, z1, c0, c1)[0], T, .5)
    def bomber(T, u, z0, z1, c0=(.5, .5), c1=(.5, .5)):
        img, (z, cx, cy) = kb('bomber', u, z0, z1, c0, c1); fx, fy = fire_pos()
        return burning(img, T, W / 2 + (fx - cx) * z, H / 2 + (fy - cy) * z, z)
    def you_over(bgf, T, u, h=900, y=.47, sil=False, name='faller', spd=1.0):
        img = streaks(bgf, T, .9 * spd)
        return sprite(img, name, W / 2 + 30 * math.sin(T * 1.3), H * y + 20 * math.sin(T * 2.1), h * (1 + .06 * u), flail(T) - (8 if sil else 0), sil)
    def hook(T, u):   # frame 1 = the payoff: a figure plunging into a snowy pine forest at night, ground rushing up
        return you_over(forest(T, u, 1.15, 1.75, (.5, .55), (.5, .6)), T, u, 760, .46, sil=True, name='silfaller', spd=1.3)
    def hook2(T, u): return puff(crater(T, u, 1.2, 1.35, (.5, .5), (.5, .52)), T * 1.4, W * .5, H * .62, 1.2)
    def ab(T, u, dim=None, you=True):
        a = forest(T, u, 1.1, 1.18, (.5, .55), (.5, .55)); b = ocean(T, u, 1.1, 1.18, (.5, .6), (.5, .6))
        img = split(a, b, 1.0, dim=dim)
        return sprite(img, 'faller', W / 2, H * .5, 520, flail(T)) if you else img
    def under(T, u):   # under the surface: dim blue-green water, bubbles rising, light from above
        img = cv2.flip(kb('sea', u, 1.3, 1.45, (.5, .75), (.5, .7))[0], 0) * np.float32((1.0, .8, .45)) * .9
        t = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]; img = img * (1.5 - t) + np.float32((150, 110, 30)) * (1 - t) ** 2
        surf, c = sk_begin(img)
        for k in range(6):   # light shafts from the surface
            x = W * (.1 + .17 * k) + 40 * math.sin(T * .7 + k); pth = skia.Path(); pth.moveTo(x - 30, 0); pth.lineTo(x + 30, 0); pth.lineTo(x + 160, H * .8); pth.lineTo(x + 60, H * .8); pth.close()
            c.drawPath(pth, P((255, 240, 200), 28 + 14 * math.sin(T * 2 + k), blur=30))
        img = sk_end(surf)
        return knockout(bubbles(img, T), .15 + .2 * u)
    return {
     0: [(0, hook), (1.3, lambda T, u: you_over(forest(T, u, 1.8, 2.3, (.5, .6), (.5, .62)), T, u, 520, .4, sil=True, name='silfaller', spd=1.6))],
     1: [(0, lambda T, u: you_over(forest(T, u, 1.0, 1.15), T, u, 950, .5)), (1.7, lambda T, u: ab(T, u))],
     2: [(0, lambda T, u: ab(T, u))],
     3: [(0, lambda T, u: you_over(ocean(T, u, 1.0, 1.1), T, u, 950, .5)), (1.9, lambda T, u: stopwatch(T, u, ocean(T, u, 1.1, 1.15)))],
     4: [(0, lambda T, u: gauge(T, u, streaks(forest(T, u, 1.0, 1.08) * .5, T))), (2.2, lambda T, u: speedbars(T, u, ocean(T, u, 1.05, 1.1)))],
     5: [(0, lambda T, u: sea(T, u, 1.0, 1.15, (.5, .5), (.5, .55))), (1.6, lambda T, u: you_over(ocean(T, u, 1.2, 1.5), T, u, 700, .45))],
     6: [(0, lambda T, u: molecules(T, u, sea(T, u, 1.1, 1.15), 'water')),
         (2.6, lambda T, u: splash(sea(T, u, 1.3, 1.5, (.5, .6), (.5, .62)) * (1 + .6 * math.exp(-T * 6)), T, W * .5, H * .62))],
     7: [(0, lambda T, u: splash(sea(T, u, 1.5, 1.6, (.5, .6), (.5, .6)), T + .4, W * .5, H * .6)), (1.7, lambda T, u: knockout(sea(T, u, 1.6, 1.8, (.5, .62), (.5, .62)), u))],
     8: [(0, under)],
     9: [(0, lambda T, u: crater(T, u, 1.0, 1.12, (.5, .5), (.5, .45))), (1.9, lambda T, u: molecules(T, u, crater(T, u, 1.1, 1.15), 'snow'))],
     10: [(0, lambda T, u: stopping(T, u, crater(T, u, 1.15, 1.2)))],
     11: [(0, lambda T, u: you_over(forest(T, u, 1.3, 1.6), T, u, 800, .45)), (1.5, lambda T, u: graph(T, u, forest(T, u, 1.6, 1.65)))],
     12: [(0, lambda T, u: globe(0, T, u, 1.0, 1.9, 'GERMANY', ORANGE)), (2.0, lambda T, u: bomber(T, u, 1.4, 1.6, (.5, .5), (.47, .48))),
          (3.9, lambda T, u: bomber(T, u, 1.1, 1.15))],
     13: [(0, lambda T, u: bomber(T, u, 2.2, 2.6, fire_pos_n(), fire_pos_n())),
          (2.7, lambda T, u: you_over(snowfall(plate('bomber') * .55, T, .4), T, u, 700, .5, sil=True, name='silfaller'))],
     14: [(0, lambda T, u: you_over(forest(T, u, 1.6, 2.6, (.5, .6), (.5, .62)), T, u, 380 + 300 * u, .5, sil=True, name='silfaller', spd=1.5)),
          (1.5, lambda T, u: puff(crater(T, u, 1.15, 1.25, (.5, .52), (.5, .52)), T, W * .5, H * .62))],
     15: [(0, lambda T, u: crater(T, u, 1.0, 1.1, (.5, .5), (.5, .55))), (1.9, lambda T, u: crater(T, u, 1.5, 1.65, (.5, .56), (.5, .58)))],
     16: [(0, lambda T, u: globe(1, T, u, 1.0, 1.9, 'CZECHOSLOVAKIA', GOLD)), (2.6, lambda T, u: altitude(T, u, wreck(T, u, 1.0, 1.05), 0))],
     17: [(0, lambda T, u: altitude(T, u, wreck(T, u, 1.05, 1.1), 1)), (2.9, lambda T, u: wreck(T, u, 1.0, 1.15, (.5, .48), (.5, .5)))],
     18: [(0, lambda T, u: wreck(T, u, 1.15, 1.3, (.5, .5), (.5, .48))), (2.3, lambda T, u: wreck(T, u, 1.7, 1.85, (.6, .53), (.63, .53)))],
     19: [(0, lambda T, u: ab(T, u)), (2.6, lambda T, u: ab(T, u, dim='b', you=False))],
     20: [(0, lambda T, u: crater(T, u, 1.0, 1.08)), (1.0, lambda T, u: hook(T, u * .3))],   # ends on the hook frame: seamless loop
    }[idx]

def fire_pos_n(): fx, fy = fire_pos(); return (fx / W + .03, fy / H)

CH = {'a': 'Land in snow', 'b': 'Land in the ocean'}
def choice(**kw): return dict({'type': 'choice', 'a': CH['a'], 'b': CH['b'], 'instant': True}, **kw)
OV = {
 0: [{'type': 'hook', 'text': 'HE FELL 3 MILES|AND LIVED', 'y': .11}],
 1: [choice(instant=False, **{'from': .3})],
 2: [choice(), {'type': 'prompt', 'text': 'Comment A or B', 'pos': [.5, .3], 'from': .1}, {'type': 'countdown', 'secs': 3, 'pos': [.5, .5]}],
 3: [choice()],
 4: [choice(), {'type': 'badge', 'value': '~120 mph', 'unit': '(~195 km/h)', 'pos': [.5, .24], 'from': .3}],
 5: [choice(), {'type': 'label', 'text': 'B: THE OCEAN', 'color': [120, 200, 255], 'pos': [.5, .25], 'from': .2}],
 6: [choice(), {'type': 'label', 'text': 'ALMOST LIKE CONCRETE', 'color': [255, 222, 40], 'pos': [.5, .25], 'from': 2.7}],
 7: [choice(), {'type': 'label', 'text': 'KNOCKED OUT', 'color': [255, 255, 255], 'pos': [.5, .25], 'from': .6}],
 8: [choice(), {'type': 'label', 'text': 'THEN: DROWNING RISK', 'color': [255, 255, 255], 'pos': [.5, .25], 'from': .6}],
 9: [choice(), {'type': 'badge', 'value': 'up to 95%', 'unit': 'air', 'pos': [.5, .24], 'from': 2.0}],
 10: [choice()],
 11: [choice()],
 12: [choice(), {'type': 'datestamp', 'text': 'Over Germany · March 1944', 'y': .2, 'from': .2}, {'type': 'badge', 'value': '18,000 ft', 'unit': 'up', 'pos': [.5, .29], 'from': 4.0}],
 13: [choice(), {'type': 'label', 'text': 'PARACHUTE ON FIRE', 'color': [255, 160, 60], 'pos': [.5, .25], 'from': .5}],
 14: [choice(), {'type': 'label', 'text': 'PINES, THEN DEEP SNOW', 'color': [200, 235, 255], 'pos': [.5, .25], 'from': .4}],
 15: [choice(), {'type': 'badge', 'value': '0', 'unit': 'broken bones', 'pos': [.5, .25], 'from': 1.9}],
 16: [choice(), {'type': 'datestamp', 'text': 'Czechoslovakia · 26 January 1972', 'y': .2, 'from': .2}],
 17: [choice(), {'type': 'badge', 'value': '33,333 ft', 'unit': '(10,160 m)', 'pos': [.5, .25], 'from': 3.0}],
 18: [choice(), {'type': 'badge', 'value': 'WORLD RECORD', 'unit': 'Guinness', 'pos': [.5, .25], 'from': 2.4, 'size': 70}],
 19: [choice(win='a', **{'from': 2.6}), {'type': 'prompt', 'text': 'Snow wins: A', 'pos': [.5, .3], 'from': 3.4}],
 20: [{'type': 'cta', 'text': 'FOLLOW FOR MORE WOULD YOU RATHERS'}],
}[idx]

if __name__ == '__main__':
    out = f'{ROOT}/s{idx}'; os.makedirs(out, exist_ok=True)
    SH = shots(); bounds = [s for s, _ in SH] + [D + PAD]
    only = [int(a) for a in sys.argv[2:]]
    for f in (only or range(1, NF + 1)):
        T = (f - 1) / FPS - .35          # compose samples scene time T + XF; frame 1 = .35 s before the line starts
        Tc = max(T, 0); k = max(j for j in range(len(SH)) if SH[j][0] <= Tc or j == 0)
        t0, t1 = bounds[k], bounds[k + 1]; u = (Tc - t0) / max(t1 - t0, .1)
        img = SH[k][1](T - t0 + (.35 if k == 0 else 0), u)
        cv2.imwrite(f'{out}/f_{f:04d}.png', np.clip(img, 0, 255).astype(np.uint8), [cv2.IMWRITE_PNG_COMPRESSION, 1])
    json.dump({'frames': NF, 'overlays': OV}, open(f'{out}/meta.json', 'w'))
    print('scene', idx, NF)
