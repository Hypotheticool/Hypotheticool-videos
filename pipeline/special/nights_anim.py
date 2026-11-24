"""Animate every scene of 'Pick a planet to spend one night on' over its Cycles plates, with 2D science graphics.
python3 nights_anim.py <scene> [frames...]  ->  nights/s<scene>/f_####.png + meta.json (overlays read by compose.py)"""
import sys, math, json, os
sys.path.insert(0, '/home/claude/pro')
import numpy as np, cv2, skia
import engine as E
ROOT = '/home/claude/b3d/nights'; CFG = json.load(open(f'{ROOT}/topic.json'))
FPS = 24; PAD = .75; idx = int(sys.argv[1]); D = CFG['durs'][idx]; NF = int(math.ceil((D + PAD) * FPS))
W, H = 1080, 1920
ease = lambda t: .5 - .5 * math.cos(math.pi * min(max(t, 0), 1))
eout = lambda t: 1 - (1 - min(max(t, 0), 1)) ** 3
cl = lambda t: min(max(t, 0), 1)
GOLD = (255, 205, 70); CYAN = (120, 215, 255); WHITE = (255, 255, 255); RED = (240, 80, 60); ICE = (170, 225, 255); HOT = (255, 120, 40)
OPT_RGB = [(225, 55, 60), (40, 110, 230), (40, 170, 90), (235, 160, 20)]

PL = {}
def plate(name):
    if name not in PL:
        im = cv2.imread(f'{ROOT}/plates/{name}.png')[..., :3]
        PL[name] = cv2.resize(im, (W, H), interpolation=cv2.INTER_CUBIC).astype(np.float32)
    return PL[name]

def kb(name, u, z0, z1, c0=(.5, .5), c1=(.5, .5), rot=0.0, border=cv2.BORDER_REFLECT):
    im = plate(name); t = ease(u); z = z0 + (z1 - z0) * t
    cx = (c0[0] + (c1[0] - c0[0]) * t) * W; cy = (c0[1] + (c1[1] - c0[1]) * t) * H
    M = cv2.getRotationMatrix2D((cx, cy), rot * t, z); M[0, 2] += W / 2 - cx; M[1, 2] += H / 2 - cy
    return cv2.warpAffine(im, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=border)

rng = np.random.default_rng(7); PTS = rng.random((260, 4))
def drift(img, T, k=1.0, col=(255, 240, 220), vx=14, vy=-6):
    """slow drifting dust/haze motes so no shot is ever a still"""
    lay = np.zeros_like(img)
    for x, y, s, b in PTS[:150]:
        px = (x * W + T * vx * (.3 + s)) % W; py = (y * H + T * vy * (.3 + s)) % H
        v = (15 + 60 * b) * k; cv2.circle(lay, (int(px), int(py)), 1 + int(s * 2), (v * col[2] / 255, v * col[1] / 255, v * col[0] / 255), -1, cv2.LINE_AA)
    return img + cv2.GaussianBlur(lay, (0, 0), 1.4)

def twinkle(img, T, k=1.0, ymax=.55):
    lay = np.zeros_like(img)
    for x, y, s, b in PTS[150:]:
        a = .5 + .5 * math.sin(T * (2 + 4 * s) + b * 20)
        v = 120 * a * k * b; cv2.circle(lay, (int(x * W), int(y * H * ymax)), 1 + int(s * 1.5), (v, v, v), -1, cv2.LINE_AA)
    return img + cv2.GaussianBlur(lay, (0, 0), .8)

def heat_haze(img, T, k=1.0, y0=.3):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    amp = k * 3.0 * np.clip((yy / H - y0) * 3, 0, 1)
    dx = amp * np.sin(yy * .08 + T * 8.0) + amp * .5 * np.sin(yy * .21 - T * 12 + xx * .01)
    return cv2.remap(img, xx + dx, yy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

FN = None
def frost(img, u, k=1.0):
    global FN
    if FN is None:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        d = np.minimum(np.minimum(xx, W - xx) / W, np.minimum(yy, H - yy) / H)
        n1 = cv2.resize(rng.random((96, 54)).astype(np.float32), (W, H), interpolation=cv2.INTER_CUBIC)
        n2 = cv2.GaussianBlur(cv2.resize(rng.random((480, 270)).astype(np.float32), (W, H)), (0, 0), 2.5)
        FN = (d, n1, n2)
    d, n1, n2 = FN; reach = (.015 + .06 * eout(u)) * k
    m = np.clip((reach - d + .03 * (n1 - .5)) * 14, 0, 1) * np.clip(.4 + 1.2 * (n2 - .3), 0, 1)
    m = m[..., None] * .6
    return img * (1 - m) + np.float32((255, 240, 225)) * m

def dim(img, k): return img * k

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
def note(img, s, y=.93, size=40, a=1.0):
    surf, c = sk_begin(img); text(c, s, W / 2, H * y, size, (210, 220, 235), 220 * a); return sk_end(surf)

def pin(img, x, y, T, col=GOLD, a=1.0, label=None, r0=16):
    surf, c = sk_begin(img)
    for k in range(3):
        ph = (T * .9 + k / 3) % 1; c.drawCircle(x, y, r0 + 110 * ph, P(col, 220 * (1 - ph) * a, 'stroke', 5))
    if label: text(c, label, x, y - 70, 54, col, 255 * a)
    return sk_end(surf)

# ---------------- shared graphics
def counter(img, T, u, v0, v1, unit, col=GOLD, y=.43, fmt='{:.0f}', sub=None):
    """big ticking number (e.g. days of darkness)"""
    surf, c = sk_begin(img); v = v0 + (v1 - v0) * eout(cl(u * 1.25))
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(W * .14, H * y - 190, W * .72, 300), 40, 40), P((8, 12, 20), 170))
    text(c, fmt.format(v), W / 2, H * y + 20, 190, col); text(c, unit, W / 2, H * y + 85, 52, WHITE)
    if sub: text(c, sub, W / 2, H * y - 130, 42, (200, 210, 225))
    return sk_end(surf)

# true-scale °C thermometer (−200 .. +500 °C)
C0, C1 = -200, 500; TY0, TY1 = 1700, 600
def cy_(t): return TY0 + (t - C0) / (C1 - C0) * (TY1 - TY0)
MARKS = {'merc': (-180, '-180°C', 'MERCURY NIGHT', ICE), 'dry': (-78.5, '-78.5°C', 'DRY ICE', (200, 200, 220)),
         'body': (37, '37°C', 'YOUR BODY', (255, 170, 150)), 'water': (100, '100°C', 'WATER BOILS', (120, 200, 255)),
         'lead': (327.5, '327°C', 'LEAD MELTS', (190, 190, 205)), 'venus': (470, '~470°C', 'VENUS NIGHT', HOT),
         'mars': (-70, '~-70°C', 'MARS NIGHT', (255, 140, 90))}
def thermo(T, level, marks, bg=None, bracket=None, zoom=1.0, zc=(.5, .5)):
    if bg is None:
        img = np.zeros((H, W, 3), np.float32); t = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
        img[:] = np.float32((40, 20, 10)) * (1 - t) + np.float32((12, 10, 26)) * t
    else: img = bg * .32
    surf, c = sk_begin(img)
    if zoom != 1.0: c.save(); c.translate(W / 2, H / 2); c.scale(zoom, zoom); c.translate(-zc[0] * W, -zc[1] * H)
    X = 250
    tube = skia.RRect.MakeRectXY(skia.Rect.MakeLTRB(X - 44, TY1 - 60, X + 44, TY0 + 40), 44, 44)
    c.drawRRect(tube, P((30, 36, 48), 235)); c.drawRRect(tube, P(WHITE, 200, 'stroke', 5))
    c.drawCircle(X, TY0 + 80, 78, P((30, 36, 48), 235)); c.drawCircle(X, TY0 + 80, 78, P(WHITE, 200, 'stroke', 5))
    col = (255, 90, 50) if level > 40 else (90, 190, 255)
    yl = cy_(level); c.drawCircle(X, TY0 + 80, 60, P(col)); c.drawRect(skia.Rect.MakeLTRB(X - 24, yl, X + 24, TY0 + 70), P(col))
    c.drawCircle(X, yl, 40, P(col, 120, blur=18))
    for t_ in range(-200, 501, 100):
        y = cy_(t_); c.drawLine(X + 40, y, X + 70, y, P(WHITE, 170, 'stroke', 3)); text(c, f'{t_}', X - 62, y + 14, 40, (210, 220, 235), 210, 'r')
    text(c, '°C', X, TY1 - 90, 44, (210, 220, 235), 220)
    ms = sorted([(cy_(MARKS[k][0]), k, a) for k, a in marks]); ly = []
    for y, k, a in ms: ly.append(max(y, ly[-1] + 118) if ly else y)
    if ly and ly[-1] > TY0 + 40:
        sh = ly[-1] - (TY0 + 40); ly = [v - sh for v in ly]
        for j in range(len(ly) - 2, -1, -1): ly[j] = min(ly[j], ly[j + 1] - 118)
    for (y, k, a), yl2 in zip(ms, ly):
        t_, v, lab, mc = MARKS[k]; aa = 255 * cl(a)
        c.drawLine(X + 50, y, X + 120, y, P(mc, aa, 'stroke', 5)); c.drawLine(X + 120, y, X + 170, yl2, P(mc, aa, 'stroke', 5)); c.drawCircle(X + 170, yl2, 9, P(mc, aa))
        text(c, v, X + 195, yl2 + 8, 66, mc, aa, 'l'); text(c, lab, X + 195, yl2 + 54, 38, WHITE, aa * .9, 'l')
    if bracket:
        ta, tb, txt, ba = bracket; ya, yb = cy_(ta), cy_(tb); bx = X + 720; g = eout(ba)
        yb2 = ya + (yb - ya) * g
        c.drawLine(bx, ya, bx, yb2, P(GOLD, 255, 'stroke', 7))
        for yy in (ya, yb2): c.drawLine(bx - 24, yy, bx, yy, P(GOLD, 255, 'stroke', 7))
        text(c, txt, bx - 10, (ya + yb2) / 2 + 22, 64, GOLD, 255 * g, 'r')
    if zoom != 1.0: c.restore()
    return sk_end(surf)

# lineup: planet centers in the plate (2x2 grid), for selection rings and X marks
GRID = [(.29, .355), (.71, .355), (.29, .603), (.71, .603)]
LCY = .40   # view center: shifts the grid down so the top row clears the options list
def lineup(T, u, z0=.84, z1=.88, ring=None, xs=(), win=None):
    img = twinkle(kb('lineup', u, z0, z1, (.5, LCY), (.5, LCY), border=cv2.BORDER_CONSTANT), T, .6)
    surf, c = sk_begin(img); z = z0 + (z1 - z0) * ease(u)
    for k, (gx, gy) in enumerate(GRID):
        x = W / 2 + (gx - .5) * W * z; y = H / 2 + (gy - LCY) * H * z; r = 194 * z
        if ring is not None and ring == k:
            c.drawCircle(x, y, r + 14, P(OPT_RGB[k], 255, 'stroke', 12)); c.drawCircle(x, y, r + 14, P(OPT_RGB[k], 140, 'stroke', 30, blur=14))
        if k in xs:
            g = eout(xs[k]) if isinstance(xs, dict) else 1
            c.drawLine(x - r * .7 * g, y - r * .7 * g, x + r * .7 * g, y + r * .7 * g, P(RED, 240, 'stroke', 22))
            c.drawLine(x + r * .7 * g, y - r * .7 * g, x - r * .7 * g, y + r * .7 * g, P(RED, 240, 'stroke', 22))
        if win == k:
            g = eout(u * 2); c.drawCircle(x, y, r + 20, P(GOLD, 255 * g, 'stroke', 14)); c.drawCircle(x, y, r + 30, P(GOLD, 120 * g, 'stroke', 40, blur=18))
        text(c, str(k + 1), x - r * .82, y - r * .72, 64, OPT_RGB[k])
    text(c, 'NOT TO SCALE', W / 2, H * .95, 38, (200, 210, 225), 200)
    return sk_end(surf)

def sun_path(T, u, bg):
    """Venus sky: the Sun crosses from WEST to EAST and sets in the east (Venus spins backwards)"""
    img = bg * .5; surf, c = sk_begin(img)
    hy = H * .7; c.drawLine(W * .06, hy, W * .94, hy, P((230, 200, 160), 220, 'stroke', 6))
    text(c, 'W', W * .1, hy + 80, 70, WHITE); text(c, 'E', W * .9, hy + 80, 70, GOLD)
    cx, R = W / 2, W * .4; a0 = math.radians(150); a1 = math.radians(-8); a = a0 + (a1 - a0) * ease(cl(u * 1.2))
    pth = skia.Path(); pth.addArc(skia.Rect.MakeLTRB(cx - R, hy - R, cx + R, hy + R), 180, 180)
    c.drawPath(pth, P(GOLD, 120, 'stroke', 4))
    sx, sy = cx + R * math.cos(a), hy - R * math.sin(a)
    c.save(); c.clipRect(skia.Rect.MakeLTRB(0, 0, W, hy)); c.drawCircle(sx, sy, 70, P((255, 210, 110), 140, blur=30)); c.drawCircle(sx, sy, 44, P((255, 235, 170))); c.restore()
    E.arrow(c, cx + R * math.cos(a0 - .5), hy - R * math.sin(a0 - .5) - 40, cx + R * math.cos(a0 - 1.1), hy - R * math.sin(a0 - 1.1) - 40, 8, (255, 222, 40), 1.0)
    text(c, 'SUN SETS IN THE EAST', W / 2, H * .82, 62, GOLD, 255 * cl(u * 3 - 1.6))
    return sk_end(surf)

def pressure(T, u, bg):
    """90 bars of air vs 1: each column = Earth's sea-level air pressure"""
    img = heat_haze(bg, T, .6) * .38; surf, c = sk_begin(img)
    n = int(90 * eout(cl(u * 1.4))); cols, x0, y0, s = 15, W * .2, H * .78, 42
    for k in range(n):
        x = x0 + (k % cols) * s; y = y0 - (k // cols) * s
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, y, s - 8, s - 8), 6, 6), P(HOT, 230))
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(W * .2, H * .84, s - 8, s - 8), 6, 6), P(CYAN, 240))
    text(c, '= EARTH', W * .2 + 60, H * .84 + 30, 44, CYAN, 255, 'l')
    text(c, f'{n}×', W / 2, H * .48, 150, GOLD)
    return sk_end(surf)

def day_clock(T, u, bg):
    """Earth day 24 h 00 min vs Mars day (sol) 24 h 40 min"""
    img = bg * .4; surf, c = sk_begin(img)
    for k, (x, lab, mins, col) in enumerate(((W * .28, 'EARTH', 0, CYAN), (W * .72, 'MARS', 40, (255, 140, 90)))):
        y = H * .5; r = 175; c.drawCircle(x, y, r, P((15, 18, 28), 230)); c.drawCircle(x, y, r, P(col, 255, 'stroke', 8))
        g = eout(cl(u * 1.3)); full = 2 * math.pi * g + (2 * math.pi * mins / (24 * 60) * 12 * cl(u * 1.3 - .7) if mins else 0)
        p = skia.Path(); p.moveTo(x, y); p.arcTo(skia.Rect.MakeLTRB(x - r + 14, y - r + 14, x + r - 14, y + r - 14), -90, math.degrees(min(full, 2 * math.pi * 1.33)), False); p.close()
        c.drawPath(p, P(col, 110))
        text(c, lab, x, y - r - 40, 60, col)
        tot = (24 * 60 + mins) * eout(cl(u * 1.3)); hh, mm = divmod(int(tot), 60)
        text(c, f'{hh}h {mm:02d}m', x, y + r + 90, 70, WHITE)
    return sk_end(surf)

def phobos(img, T, u, x0=.5, y0=.6, x1=.75, y1=.2):
    """Phobos: small grey lumpy moon rising from the western horizon and racing up the sky"""
    surf, c = sk_begin(img); t = ease(u); x = (x0 + (x1 - x0) * t) * W; y = (y0 + (y1 - y0) * t) * H
    for k in range(10):   # motion trail
        tt = max(0, t - k * .025); xx = (x0 + (x1 - x0) * tt) * W; yy = (y0 + (y1 - y0) * tt) * H
        c.drawCircle(xx, yy, 22, P((200, 195, 185), 40 - 4 * k))
    c.save(); c.translate(x, y); c.rotate(T * 20); c.scale(1.25, 1.0)
    c.drawCircle(0, 0, 24, P((150, 145, 138))); c.drawCircle(-8, -7, 6, P((110, 105, 100))); c.drawCircle(9, 5, 5, P((115, 110, 105)))
    c.restore(); c.drawCircle(x, y, 40, P((220, 220, 230), 50, blur=16))
    text(c, 'PHOBOS', x, y - 50, 48, WHITE, 255 * cl(u * 4))
    E.arrow(c, W * .14, H * .56, W * .14, H * .46, 7, (255, 222, 40), cl(u * 3)); text(c, 'RISES IN THE WEST', W * .14 + 20, H * .44, 40, GOLD, 255 * cl(u * 3), 'l')
    return sk_end(surf)

def tilt_diagram(T, u):
    """Uranus at solstice: axis tipped 98°, one pole faces the Sun, the other is in a night that lasts decades"""
    img = twinkle(kb('uranus', .5, 1.0, 1.0), T, .5) * .35; surf, c = sk_begin(img)
    sx = W * .1; c.drawCircle(sx, H * .5, 70, P((255, 210, 110))); c.drawCircle(sx, H * .5, 120, P((255, 200, 90), 120, blur=40))
    for k in range(5):
        y = H * (.42 + .04 * k); c.drawLine(sx + 90, y, W * .42, y, P((255, 220, 130), 140, 'stroke', 4))
    cx, cy, r = W * .64, H * .5, 230
    c.drawCircle(cx, cy, r, P((60, 95, 105)))
    c.save(); c.clipRect(skia.Rect.MakeLTRB(cx - r, cy - r, cx, cy + r)); c.drawCircle(cx, cy, r, P((165, 225, 230))); c.restore()
    ang = math.radians(98) * eout(cl(u * 1.4))     # axis swings from upright to 98°
    dx, dy = math.sin(ang) * (r + 110), -math.cos(ang) * (r + 110)
    c.drawLine(cx + dx, cy + dy, cx - dx, cy - dy, P(GOLD, 255, 'stroke', 6))
    c.drawCircle(cx - dx * .78, cy - dy * .78, 14, P(GOLD)); text(c, 'POLE', cx - dx * .78 - 10, cy - dy * .78 - 30, 40, GOLD, 255 * cl(u * 2), 'r')
    text(c, f'{98 * eout(cl(u * 1.4)):.0f}°', cx + 40, cy - r - 60, 70, GOLD)
    text(c, 'DAY', cx - r * .5, cy + 18, 54, (40, 60, 70), 255 * cl(u * 2 - .6))
    text(c, 'NIGHT', cx + r * .5, cy + 18, 54, WHITE, 255 * cl(u * 2 - .6))
    text(c, 'NOT TO SCALE', W / 2, H * .95, 38, (200, 210, 225), 200)
    return sk_end(surf)

def age(T, u):
    img = drift(dim(kb('uranus_clouds', u, 1.05, 1.15, (.5, .5), (.5, .48)), .45), T, .7, (180, 230, 240), 20, -4)
    surf, c = sk_begin(img); g = eout(cl(u * 1.15)); a = 20 + 42 * g
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(W * .12, H * .3, W * .76, 420), 40, 40), P((8, 12, 20), 180))
    text(c, 'YOUR AGE', W / 2, H * .3 + 80, 50, (200, 215, 230)); text(c, f'{a:.0f}', W / 2, H * .3 + 300, 230, GOLD)
    yrs = int(42 * g); text(c, f'NIGHT: YEAR {max(1, yrs)} OF ~42', W / 2, H * .3 + 380, 44, WHITE)
    return sk_end(surf)

def nights_chart(T, u):
    """how long one night lasts (log scale, labeled): Mars ~12 h, Venus ~58 d, Mercury ~88 d, Uranus pole ~42 yr"""
    img = np.zeros((H, W, 3), np.float32); t = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    img[:] = np.float32((30, 16, 8)) * (1 - t) + np.float32((14, 10, 24)) * t
    surf, c = sk_begin(img)
    rows = [('MARS', 12, '~12 HOURS', OPT_RGB[2]), ('VENUS', 58 * 24, '~58 DAYS', OPT_RGB[1]), ('MERCURY', 88 * 24, '~88 DAYS', OPT_RGB[0]), ('URANUS', 42 * 8766, '~42 YEARS', OPT_RGB[3])]
    lo, hi = math.log10(6), math.log10(42 * 8766 * 1.3)
    for k, (nm, hrs, lab, col) in enumerate(rows):
        y = H * .36 + k * 190; g = eout(cl(u * 1.6 - k * .12)); w = (math.log10(hrs) - lo) / (hi - lo) * W * .62 * g
        text(c, nm, W * .08, y - 18, 48, WHITE, 255, 'l')
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(W * .08, y, max(w, 8), 70), 16, 16), P(col, 240))
        text(c, lab, W * .08 + w + 20, y + 52, 46, col, 255 * g, 'l')
        if nm == 'MARS': c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(W * .08 - 10, y - 80, W * .86, 170), 24, 24), P(GOLD, 255 * cl(u * 3 - 1), 'stroke', 6))
    text(c, 'ONE NIGHT LASTS…', W / 2, H * .3, 60, GOLD); text(c, 'log scale', W / 2, H * .95, 36, (200, 210, 225), 200)
    return sk_end(surf)

# ---------------- scene table: list of (start_sec, render_fn(T_local_in_shot, u_shot))
def shots():
    ura = lambda T, u, z0, z1, c0=(.5, .5), c1=(.5, .5): twinkle(kb('uranus', u, z0, z1, c0, c1), T, .7)
    glb = lambda n: (lambda T, u, z0=1.0, z1=1.12, c0=(.5, .5), c1=(.5, .5): twinkle(kb(n, u, z0, z1, c0, c1), T, .6))
    mg, vg, mag = glb('mercury_globe'), glb('venus_globe'), glb('mars_globe')
    msun = lambda T, u, z0, z1, c0=(.5, .5), c1=(.5, .5): drift(kb('mercury_sunset', u, z0, z1, c0, c1), T, .4)
    mnig = lambda T, u, z0, z1, c0=(.5, .5), c1=(.5, .5): twinkle(drift(kb('mercury_night', u, z0, z1, c0, c1), T, .35), T, .5, .35)
    vnig = lambda T, u, z0, z1, c0=(.5, .5), c1=(.5, .5): drift(heat_haze(kb('venus_night', u, z0, z1, c0, c1), T, .9), T, .8, (255, 170, 110), 25, -10)
    mars = lambda T, u, z0, z1, c0=(.5, .5), c1=(.5, .5): twinkle(drift(kb('mars_night', u, z0, z1, c0, c1), T, .3, (255, 190, 150)), T, .5, .4)
    ucl = lambda T, u, z0, z1, c0=(.5, .5), c1=(.5, .5): drift(kb('uranus_clouds', u, z0, z1, c0, c1), T, .8, (180, 230, 240), 30, -5)
    # Earth's position in the mars_night plate (found from the render), for zooms and the pin
    EX, EY = [float(v) for v in open(f'{ROOT}/plates/earth_xy.txt').read().split()]
    def earth_zoom(T, u, z0, z1):
        img = mars(T, u, z0, z1, (.5, .5), (EX, EY)); z = z0 + (z1 - z0) * ease(u); cx = .5 + (EX - .5) * ease(u); cy = .5 + (EY - .5) * ease(u)
        X = W / 2 + (EX * W - cx * W) * z; Y = H / 2 + (EY * H - cy * H) * z
        return pin(img, X, Y, T, CYAN, cl(u * 3), 'EARTH' if u > .15 else None)
    def hook(T, u): return ura(T, u, 1.12, 1.32, (.47, .5), (.42, .52))
    return {
     0: [(0, hook), (1.5, lambda T, u: ura(T, u, 1.5, 1.7, (.3, .55), (.27, .57)))],
     1: [(0, lambda T, u: lineup(T, u, .82, .86)), (2.5, lambda T, u: lineup(T, u, .86, .9))],
     2: [(0, lambda T, u: mnig(T, u, 1.0, 1.12, (.5, .55), (.5, .52))), (1.7, lambda T, u: mars(T, u, 1.0, 1.1, (.5, .5), (.48, .48)))],
     3: [(0, lambda T, u: lineup(T, u, .84, .88, ring=int(T * 4) % 4))],
     4: [(0, lambda T, u: mg(T, u, 1.0, 1.2, (.5, .5), (.45, .5))), (1.9, lambda T, u: msun(T, u, 1.0, 1.12, (.5, .45), (.55, .44))),
         (3.7, lambda T, u: counter(dim(msun(T, 1, 1.12, 1.2, (.55, .44), (.55, .44)), .6), T, u, 0, 88, 'EARTH DAYS IN THE DARK', GOLD, .45))],
     5: [(0, lambda T, u: mnig(T, u, 1.1, 1.25, (.5, .5), (.52, .55))),
         (2.0, lambda T, u: thermo(T, 20 - 200 * eout(cl(u * 1.6)), [('merc', cl(u * 3 - .5))])),
         (3.9, lambda T, u: frost(mnig(T, u, 1.3, 1.45, (.52, .5), (.52, .52)), u, 1.2))],
     6: [(0, lambda T, u: thermo(T, -180, [('merc', 1), ('dry', cl(u * 3))], bracket=(-78.5, -180, '~100°', cl(u * 1.8 - .4)))),
         (2.0, lambda T, u: thermo(T, -180, [('merc', 1), ('dry', 1)], bracket=(-78.5, -180, '~100°', 1), zoom=1.3, zc=(.55, .8)))],
     7: [(0, lambda T, u: vg(T, u, 1.0, 1.2, (.5, .5), (.47, .5))), (1.9, lambda T, u: sun_path(T, u, kb('venus_globe', 1, 1.2, 1.25))),
         (3.8, lambda T, u: counter(dim(vnig(T, u, 1.0, 1.1), .6), T, u, 0, 58, 'EARTH DAYS OF NIGHT', GOLD, .45))],
     8: [(0, lambda T, u: vnig(T, u, 1.0, 1.15, (.5, .5), (.47, .52))),
         (1.8, lambda T, u: thermo(T, 20 + 450 * eout(cl(u * 1.6)), [('venus', cl(u * 3 - .5)), ('body', cl(u * 3 - .2))])),
         (3.7, lambda T, u: vnig(T, u, 1.3, 1.5, (.45, .5), (.43, .52)))],
     9: [(0, lambda T, u: thermo(T, 470, [('venus', 1), ('lead', cl(u * 3)), ('water', cl(u * 3 - .5))])),
         (2.2, lambda T, u: pressure(T, u, kb('venus_night', u, 1.1, 1.2)))],
     10: [(0, lambda T, u: mag(T, u, 1.0, 1.2, (.5, .5), (.47, .5))), (1.8, lambda T, u: day_clock(T, u, kb('mars_globe', 1, 1.2, 1.25))),
          (3.7, lambda T, u: mars(T, u, 1.0, 1.1, (.5, .5), (.46, .5)))],
     11: [(0, lambda T, u: thermo(T, 20 - 90 * eout(cl(u * 1.6)), [('mars', cl(u * 3 - .3)), ('merc', cl(u * 3 - 1.2)), ('venus', cl(u * 3 - 1.4))])),
          (2.6, lambda T, u: mars(T, u, 1.2, 1.35, (.4, .55), (.4, .52)))],
     12: [(0, lambda T, u: phobos(mars(T, u, 1.0, 1.05, (.5, .5), (.5, .47)), T, u * .55, .42, .5, .6, .3)),
          (2.6, lambda T, u: phobos(mars(T, u, 1.05, 1.12, (.5, .47), (.5, .45)), T, .55 + .45 * u, .42, .5, .6, .3))],
     13: [(0, lambda T, u: earth_zoom(T, u, 1.0, 1.35)), (2.3, lambda T, u: earth_zoom(T, u, 1.6, 2.2))],
     14: [(0, lambda T, u: ura(T, u, 1.0, 1.15, (.5, .5), (.45, .5))), (2.2, lambda T, u: ucl(T, u, 1.0, 1.12, (.5, .5), (.5, .52)))],
     15: [(0, tilt_diagram), (2.7, lambda T, u: counter(dim(ura(T, u, 1.4, 1.6, (.3, .55), (.28, .56)), .7), T, u, 0, 42, 'YEARS OF NIGHT', CYAN, .45, sub='NEAR THE POLES'))],
     16: [(0, age)],
     17: [(0, nights_chart), (1.9, lambda T, u: earth_zoom(T, u, 1.15, 1.35))],
     18: [(0, lambda T, u: lineup(T, u, .84, .88, xs={0: cl(u * 3), 1: cl(u * 3 - .4), 3: cl(u * 3 - .8)}, win=2)),
          (2.2, lambda T, u: hook(T, u * .25))],      # ends on the hook frame: seamless loop
    }[idx]

OPTS = ['Mercury', 'Venus', 'Mars', 'Uranus']
def opts(pick=None, slim=False, **kw):
    if slim: return dict({'type': 'options', 'items': [OPTS[pick]], 'pick': 0, 'instant': True, 'num': pick + 1}, **kw)
    d = {'type': 'options', 'items': OPTS, 'instant': True}
    if pick is not None: d['pick'] = pick
    return dict(d, **kw)
OV = {   # compose.py overlays per scene (full options list fills the top ~32%; a slim tag the top ~13%)
 0: [{'type': 'hook', 'text': 'ONE NIGHT LASTS|42 YEARS', 'y': .11}],
 1: [opts(instant=False, **{'from': .5})],
 2: [opts()],
 3: [opts(), {'type': 'countdown', 'secs': 3, 'pos': [.5, .55]}],
 4: [opts(0), {'type': 'badge', 'value': '~88', 'unit': 'Earth days of night', 'pos': [.5, .37], 'from': .6}],
 5: [opts(0, True), {'type': 'badge', 'value': '-180°C', 'unit': '(-290°F)', 'pos': [.5, .2], 'from': .5}],
 6: [opts(0, True)],
 7: [opts(1), {'type': 'badge', 'value': '~58', 'unit': 'Earth days of night', 'pos': [.5, .37], 'from': .6}],
 8: [opts(1, True), {'type': 'badge', 'value': '~470°C', 'unit': '(~880°F) day AND night', 'pos': [.5, .2], 'from': .5}],
 9: [opts(1, True), {'type': 'badge', 'value': '90×', 'unit': "Earth's air pressure", 'pos': [.5, .2], 'from': 2.2}],
 10: [opts(2), {'type': 'badge', 'value': '24h 40m', 'unit': 'one Mars day', 'pos': [.5, .37], 'from': .6}],
 11: [opts(2, True), {'type': 'badge', 'value': '~-70°C', 'unit': '(-94°F)', 'pos': [.5, .2], 'from': .5}],
 12: [opts(2, True)],
 13: [opts(2, True), {'type': 'datestamp', 'text': 'Curiosity rover · Mars · 31 Jan 2014', 'y': .145, 'from': .4}],
 14: [opts(3), {'type': 'label', 'text': 'NO SOLID GROUND', 'color': [255, 222, 40], 'pos': [.5, .37], 'from': 1.0}],
 15: [opts(3, True), {'type': 'badge', 'value': '~98°', 'unit': 'tilt', 'pos': [.5, .2], 'from': .3}],
 16: [opts(3, True)],
 17: [opts(2, True), {'type': 'label', 'text': 'WINNER: MARS', 'color': [255, 222, 40], 'pos': [.5, .2], 'from': .3}],
 18: [{'type': 'cta', 'text': 'FOLLOW FOR MORE SCENARIOS'}],
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
