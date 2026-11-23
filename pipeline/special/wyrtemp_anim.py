"""Animate every scene of the WYR (coldest vs hottest day on Earth) over its Cycles plates, with 2D science graphics.
python3 wyrtemp_anim.py <scene> [frames...]  ->  wyrtemp/s<scene>/f_####.png + meta.json (overlays read by compose.py)"""
import sys, math, json, os
sys.path.insert(0, '/home/claude/pro')
import numpy as np, cv2, skia
import engine as E
ROOT = '/home/claude/b3d/wyrtemp'; CFG = json.load(open(f'{ROOT}/topic.json'))
FPS = 24; PAD = .75; idx = int(sys.argv[1]); D = CFG['durs'][idx]; NF = int(math.ceil((D + PAD) * FPS))
W, H = 1080, 1920
ease = lambda t: .5 - .5 * math.cos(math.pi * min(max(t, 0), 1))
eout = lambda t: 1 - (1 - min(max(t, 0), 1)) ** 3
GOLD = (255, 205, 70); CYAN = (120, 215, 255); WHITE = (255, 255, 255); RED = (240, 80, 60); ICE = (170, 225, 255); HOT = (255, 120, 40)

GRADE = {   # per-plate color grade (BGR multipliers) + a vertical gradient: one palette, deep navy cold vs amber heat
    'ice': ((1.05, .95, .85), None), 'iceclose': ((1.05, .97, .9), None), 'plateau': ((1.0, 1.0, 1.0), None), 'pole': ((1.0, .97, .95), None),
    'ant': ((1, 1, 1), None), 'dv': ((1, 1, 1), None),
    'desert': ((.62, .8, 1.12), ((70, 40, 10), (0, 30, 90))), 'salt': ((.82, .9, 1.06), ((60, 30, 0), (0, 25, 60)))}
PL = {}
def plate(name):
    if name not in PL:
        im = cv2.imread(f'{ROOT}/plates/{name}.png')[..., :3]
        im = cv2.resize(im, (W, H), interpolation=cv2.INTER_CUBIC).astype(np.float32)
        mul, grad = GRADE[name]; im = im * np.float32(mul)
        if grad:   # warm-dusk sky grade: teal-navy top -> amber horizon
            t = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
            top, bot = np.float32(grad[0]), np.float32(grad[1])
            im = im * (1 - .35 * (1 - t)) + (top * (1 - t) + bot * t) * .5
        if name in ('desert', 'salt'):   # S-curve contrast
            x = np.clip(im / 255, 0, 1); im = (x * x * (3 - 2 * x) * .6 + x * .4) * 255
        PL[name] = np.clip(im, 0, 255)
    return PL[name]
PIN = {k: [float(v) for v in open(f'{ROOT}/plates/{k}.txt').read().split()] for k in ('ant', 'dv')}

def kb(name, u, z0, z1, c0=(.5, .5), c1=(.5, .5)):
    im = plate(name); t = ease(u); z = z0 + (z1 - z0) * t
    cx = (c0[0] + (c1[0] - c0[0]) * t) * W; cy = (c0[1] + (c1[1] - c0[1]) * t) * H
    M = np.float32([[z, 0, W / 2 - cx * z], [0, z, H / 2 - cy * z]])
    return cv2.warpAffine(im, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT), (z, cx, cy)

rng = np.random.default_rng(11); FLAKES = rng.random((320, 4))
def blowing_snow(img, T, k=1.0, wind=520):
    """wind-driven spindrift streaks low over the snow (polar plateau winds), catching the station light"""
    lay = np.zeros_like(img)
    for x, y, s, b in FLAKES:
        px = (x * W + T * wind * (.5 + s)) % (W + 200) - 100; py = H * (.35 + .65 * y) + math.sin(T * 2 + x * 20) * 8
        L = 6 + 22 * s; v = (30 + 120 * b * b) * k
        cv2.line(lay, (int(px), int(py)), (int(px - L), int(py + 2)), (v, v * .97, v * .9), 1 + int(s * 2), cv2.LINE_AA)
    return img + cv2.GaussianBlur(lay, (0, 0), 1.0)

def heat_haze(img, T, k=1.0, y0=.25):
    """mirage shimmer: small vertical-phase horizontal displacement, strongest near the ground line"""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    amp = k * 3.2 * np.clip((yy / H - y0) * 3, 0, 1) * np.clip(1.4 - (yy / H), 0, 1)
    dx = amp * np.sin(yy * .09 + T * 9.0) + amp * .5 * np.sin(yy * .23 - T * 13 + xx * .01)
    return cv2.remap(img, xx + dx, yy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

def dust(img, T, k=1.0):
    lay = np.zeros_like(img)
    for x, y, s, b in FLAKES[:160]:
        px = (x * W + T * 40 * (.3 + s)) % W; py = (y * H - T * 25 * s) % H
        v = (20 + 70 * b) * k; cv2.circle(lay, (int(px), int(py)), 1 + int(s * 2), (v * .5, v * .8, v), -1, cv2.LINE_AA)
    return img + cv2.GaussianBlur(lay, (0, 0), 1.5)

FN = None
def frost(img, u, k=1.0):
    """frost creeping in from the frame edges (exposed skin / lens freezing): fine crystalline noise, edges only"""
    global FN
    if FN is None:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        d = np.minimum(np.minimum(xx, W - xx) / W, np.minimum(yy, H - yy) / H)
        n1 = cv2.resize(rng.random((96, 54)).astype(np.float32), (W, H), interpolation=cv2.INTER_CUBIC)
        n2 = cv2.GaussianBlur(cv2.resize(rng.random((480, 270)).astype(np.float32), (W, H), interpolation=cv2.INTER_LINEAR), (0, 0), 2.5)
        FN = (d, n1, n2)
    d, n1, n2 = FN; reach = (.015 + .06 * eout(u)) * k
    m = np.clip((reach - d + .03 * (n1 - .5)) * 14, 0, 1) * np.clip(.4 + 1.2 * (n2 - .3), 0, 1)
    m = m[..., None] * .65
    return img * (1 - m) + np.float32((255, 240, 225)) * m

def split(a_img, b_img, u, tilt=-.12):
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

def pin(img, x, y, T, col=GOLD, a=1.0, label=None):
    surf, c = sk_begin(img)
    for k in range(3):
        ph = (T * .9 + k / 3) % 1; c.drawCircle(x, y, 18 + 120 * ph, P(col, 220 * (1 - ph) * a, 'stroke', 5))
    c.drawCircle(x, y, 13, P(col, 255 * a)); c.drawCircle(x, y, 40, P(col, 120 * a, blur=16))
    if label: text(c, label, x, y - 60, 50, col, 255 * a)
    return sk_end(surf)

def globe(name, T, u, z0, z1, label):
    px, py = PIN[name]; t = ease(u); cc = (.5 + (px - .5) * t, .5 + (py + .06 - .5) * t)
    img, (z, cx, cy) = kb(name, u, z0, z1, (.5, .5), cc)
    X = W / 2 + (px * W - cx) * z; Y = H / 2 + (py * H - cy) * z
    return pin(img, X, Y, T, ICE if name == 'ant' else HOT, min(1, T * 2), label if u > .25 else None)

# ---------------- thermometer: one true-scale °F axis shared by every stat (−150 °F .. +220 °F)
F0, F1 = -150, 220; TY0, TY1 = 1640, 580   # pixel y of F0 and F1
def fy(F): return TY0 + (F - F0) / (F1 - F0) * (TY1 - TY0)
MARKS = {'vostok': (-128.6, '-128.6°F', 'VOSTOK 1983', ICE), 'dryice': (-109.3, '-109°F', 'DRY ICE', (200, 200, 220)),
         'sat': (-144.4, '-144°F', 'SATELLITE LOW', (150, 190, 255)),
         'body': (98.6, '98.6°F', 'YOUR BODY', (255, 170, 150)), 'tub': (104, '104°F', 'HOT TUB MAX', (120, 200, 255)),
         'dv': (134, '134°F', 'DEATH VALLEY 1913', HOT), 'ground': (201, '201°F', 'GROUND 1972', RED), 'egg': (158, '~158°F', 'EGG YOLK SETS', (255, 230, 120)),
         'sauna': (200, '200°F', 'SAUNA', HOT), 'pole100': (-100, '-100°F', 'OUTSIDE', ICE), 'zero': (32, '32°F', 'WATER FREEZES', (180, 220, 255))}
def thermo(T, level, marks, bg='dark', reveal=1.0, zoom=1.0, zc=(.5, .5), bracket=None):
    """level = mercury temperature (°F); marks = list of (key, alpha); bracket = (F_a, F_b, text)"""
    if isinstance(bg, str):
        img = np.zeros((H, W, 3), np.float32); t = np.linspace(0, 1, H, dtype=np.float32)[:, None]
        img[:] = (np.float32((40, 18, 8)) * (1 - t) + np.float32((10, 12, 30)) * t)[:, None, :][:, 0, :][:, None, :]
    else: img = bg * .35
    surf, c = sk_begin(img)
    if zoom != 1.0: c.save(); c.translate(W / 2, H / 2); c.scale(zoom, zoom); c.translate(-zc[0] * W, -zc[1] * H)
    X = 250
    tube = skia.RRect.MakeRectXY(skia.Rect.MakeLTRB(X - 44, TY1 - 60, X + 44, TY0 + 40), 44, 44)
    c.drawRRect(tube, P((30, 36, 48), 235)); c.drawRRect(tube, P(WHITE, 200, 'stroke', 5))
    c.drawCircle(X, TY0 + 80, 78, P((30, 36, 48), 235)); c.drawCircle(X, TY0 + 80, 78, P(WHITE, 200, 'stroke', 5))
    hot = level > 60; col = (255, 90, 50) if hot else (90, 190, 255)
    yl = fy(level); c.drawCircle(X, TY0 + 80, 60, P(col)); c.drawRect(skia.Rect.MakeLTRB(X - 24, yl, X + 24, TY0 + 70), P(col))
    c.drawCircle(X, yl, 40, P(col, 120, blur=18))
    for F in range(-150, 221, 50):
        y = fy(F); c.drawLine(X + 40, y, X + 70, y, P(WHITE, 170, 'stroke', 3)); text(c, f'{F}', X - 62, y + 14, 40, (210, 220, 235), 210, 'r')
    text(c, '°F', X, TY1 - 90, 44, (210, 220, 235), 220)
    ms = sorted([(fy(MARKS[k][0]), k, a) for k, a in marks]); ly = []   # spread labels so they never overlap (>=118 px apart)
    for y, k, a in ms: ly.append(max(y, ly[-1] + 118) if ly else y)
    if ly and ly[-1] > TY0 + 40:
        sh = ly[-1] - (TY0 + 40); ly = [v - sh for v in ly]
        for j in range(len(ly) - 2, -1, -1): ly[j] = min(ly[j], ly[j + 1] - 118)
    for (y, k, a), yl2 in zip(ms, ly):
        F, v, lab, mc = MARKS[k]; aa = 255 * a * reveal
        c.drawLine(X + 50, y, X + 120, y, P(mc, aa, 'stroke', 5)); c.drawLine(X + 120, y, X + 170, yl2, P(mc, aa, 'stroke', 5)); c.drawCircle(X + 170, yl2, 9, P(mc, aa))
        text(c, v, X + 195, yl2 + 8, 66, mc, aa, 'l'); text(c, lab, X + 195, yl2 + 54, 38, WHITE, aa * .9, 'l')
    if bracket:
        Fa, Fb, txt, ba = bracket; ya, yb = fy(Fa), fy(Fb); bx = X + 740; g = eout(ba)
        yb2 = ya + (yb - ya) * g
        c.drawLine(bx, ya, bx, yb2, P(GOLD, 255, 'stroke', 7))
        for yy in (ya, yb2): c.drawLine(bx - 24, yy, bx, yy, P(GOLD, 255, 'stroke', 7))
        text(c, txt, bx - 10, (ya + yb2) / 2 + 22, 64, GOLD, 255 * g, 'r')
    if zoom != 1.0: c.restore()
    return sk_end(surf)

def jugs(T, u):
    """1 gallon (3.8 L) water jug filling: what rangers say to drink per day"""
    img, _ = kb('desert', .5 + .2 * u, 1.15, 1.22, (.5, .55), (.52, .55)); img = heat_haze(img, T, .8) * .55
    surf, c = sk_begin(img)
    x0, y0, w, h = W / 2 - 140, 620, 280, 380; g = eout(u * 1.3)
    body = skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x0, y0, w, h), 50, 50)
    c.save(); c.clipRRect(body); c.drawRect(skia.Rect.MakeLTRB(x0, y0 + h * (1 - g), x0 + w, y0 + h), P((70, 160, 255), 230))
    for k in range(3): c.drawCircle(x0 + w * (.3 + .2 * k), y0 + h * (1 - g) + 8 * math.sin(T * 5 + k), 30, P((140, 200, 255), 160))
    c.restore(); c.drawRRect(body, P(WHITE, 230, 'stroke', 8))
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(W / 2 - 60, y0 - 70, 120, 80), 18, 18), P(WHITE, 230, 'stroke', 8))
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x0 + w - 30, y0 + 40, 90, 200), 40, 40), P(WHITE, 200, 'stroke', 8))
    text(c, '1 GALLON', W / 2, y0 - 150, 84, GOLD); text(c, 'PER DAY (3.8 L)', W / 2, y0 - 95, 44, WHITE)
    return sk_end(surf)

def swing(T, u, phase):
    """the 300 Club's 300-degree swing on the same °F axis: sauna 200 -> outside -100"""
    lvl = 200 if phase == 0 else 200 - 300 * ease(u)
    marks = [('sauna', 1), ('pole100', 1 if phase else 0)]
    return thermo(T, lvl, marks, bg=kb('pole', u, 1.1, 1.2, (.5, .5), (.48, .5))[0], bracket=(200, -100, '300°', u) if phase == 2 else None)

# ---------------- scene table: list of (start_sec, render_fn(T_local_in_shot, u_shot))
def shots():
    ice = lambda T, u, z0, z1, c0=(.5, .5), c1=(.5, .5), k=1.0: blowing_snow(kb('ice', u, z0, z1, c0, c1)[0], T, k)
    icec = lambda T, u, z0, z1, c0=(.5, .5), c1=(.5, .5): blowing_snow(kb('iceclose', u, z0, z1, c0, c1)[0], T, .8, 700)
    plat = lambda T, u, z0, z1, c0=(.5, .5), c1=(.5, .5): blowing_snow(kb('plateau', u, z0, z1, c0, c1)[0], T, .6, 380)
    des = lambda T, u, z0, z1, c0=(.5, .5), c1=(.5, .5): dust(heat_haze(kb('desert', u, z0, z1, c0, c1)[0], T), T, .7)
    salt = lambda T, u, z0, z1, c0=(.5, .5), c1=(.5, .5): heat_haze(kb('salt', u, z0, z1, c0, c1)[0], T, 1.3, .35)
    pole = lambda T, u, z0, z1, c0=(.5, .5), c1=(.5, .5): blowing_snow(kb('pole', u, z0, z1, c0, c1)[0], T, .7, 300)
    def ab(T, u, win=None, uu=1.0):
        a = ice(T, u, 1.12, 1.2, (.45, .5), (.47, .5)); b = des(T, u, 1.12, 1.2, (.55, .55), (.53, .55))
        if win == 'b': a = a * .45
        return split(a, b, uu)
    def hook(T, u):   # frame 1 = the payoff: both extremes at once, split already open, pushing in
        return split(ice(T, u, 1.25, 1.45, (.45, .52), (.42, .52)), des(T, u, 1.25, 1.45, (.6, .58), (.62, .58)), 1.0)
    def hook2(T, u):
        return split(icec(T, u, 1.15, 1.3, (.42, .5), (.42, .5)), salt(T, u, 1.1, 1.25, (.5, .6), (.5, .62)), 1.0, .15)
    def plat_dark(T, u):   # noon in July at 78°S: the Sun stays ~9° below the horizon, only a faint glow
        img = plat(T, u, 1.0, 1.12, (.5, .5), (.5, .47)); surf, c = sk_begin(img)
        y = H * .47; c.drawLine(W * .55, y + 60, W * .55, y + 60 + 40 * math.sin(T), P(GOLD, 0))
        text(c, 'SUN: BELOW THE HORIZON', W / 2, H * .44, 62, GOLD, 255 * min(1, T * 1.5))
        return sk_end(surf)
    def sat(T, u):   # satellite thermal scan sweeping the ice sheet (Landsat 8 / MODIS skin temperature)
        img, _ = kb('ant', u, 1.6, 1.9, (PIN['ant'][0], PIN['ant'][1] + .04), (PIN['ant'][0] + .03, PIN['ant'][1] + .05))
        surf, c = sk_begin(img); y = H * (.2 + .6 * (u * 1.4 % 1))
        c.drawRect(skia.Rect.MakeLTRB(0, y - 90, W, y), P((110, 200, 255), 50)); c.drawLine(0, y, W, y, P((150, 220, 255), 230, 'stroke', 4))
        for k in range(5):
            x = W * (.25 + .12 * k); yy = H * (.42 + .05 * math.sin(k * 2.1))
            if yy < y: c.drawCircle(x, yy, 26 + 6 * math.sin(T * 4 + k), P((90, 160, 255), 200, 'stroke', 4)); c.drawCircle(x, yy, 7, P((150, 200, 255)))
        return sk_end(surf)
    def freeze(T, u): return frost(icec(T, u, 1.0, 1.1, (.45, .5), (.42, .5)), u)
    def freeze2(T, u): return frost(ice(T, u, 1.6, 1.75, (.42, .55), (.44, .55)), .6 + .4 * u, 1.2)
    def cold_fast(T, u): return frost(ice(T, u, 1.0, 1.15, (.5, .5), (.5, .52), 1.4), u * .8, 1.0) * (1 - .25 * u)
    return {
     0: [(0, hook), (1.9, hook2)],
     1: [(0, lambda T, u: ice(T, u, 1.0, 1.12)), (2.0, lambda T, u: des(T, u, 1.0, 1.12, (.5, .5), (.52, .52)))],
     2: [(0, lambda T, u: ab(T, u))],
     3: [(0, lambda T, u: globe('ant', T, u, 1.0, 1.55, 'VOSTOK')), (2.4, lambda T, u: ice(T, u, 1.05, 1.2, (.5, .5), (.42, .5)))],
     4: [(0, lambda T, u: thermo(T, 60 - 188.6 * eout(min(1, u * 1.6)), [('vostok', min(1, u * 3)), ('dryice', max(0, min(1, u * 3 - 1.2)))])),
         (2.6, lambda T, u: thermo(T, -128.6, [('vostok', 1), ('dryice', 1)], zoom=1.35, zc=(.52, .78), bracket=(-109.3, -128.6, '-19°', u)))],
     5: [(0, plat_dark), (1.5, lambda T, u: plat(T, u, 1.5, 1.65, (.62, .48), (.6, .48)))],
     6: [(0, freeze), (1.8, freeze2)],
     7: [(0, lambda T, u: globe('ant', T, .7 + .3 * u, 1.0, 1.55, 'VOSTOK')), (1.6, sat),
         (3.3, lambda T, u: thermo(T, -144.4, [('vostok', 1), ('sat', eout(u * 2))]))],
     8: [(0, lambda T, u: globe('dv', T, u, 1.0, 1.7, 'DEATH VALLEY')), (2.3, lambda T, u: des(T, u, 1.0, 1.15, (.5, .5), (.55, .5)))],
     9: [(0, lambda T, u: thermo(T, 60 + 74 * eout(min(1, u * 1.6)), [('dv', min(1, u * 3))])),
         (2.5, lambda T, u: des(T, u, 1.35, 1.55, (.55, .55), (.6, .55)))],
     10: [(0, lambda T, u: thermo(T, 134, [('dv', 1), ('tub', eout(u * 2))], bracket=(104, 134, '+30°', max(0, u * 1.6 - .4))))],
     11: [(0, lambda T, u: salt(T, u, 1.0, 1.15, (.5, .55), (.5, .6))),
          (1.8, lambda T, u: thermo(T, 134 + 67 * eout(min(1, u * 1.8)), [('dv', 1), ('egg', eout(u * 2.2 - .4)), ('ground', eout(u * 2.2 - .8))]))],
     12: [(0, jugs)],
     13: [(0, lambda T, u: ab(T, u, None, 1.0)), (1.6, lambda T, u: ab(T, u, 'b', 1.0))],
     14: [(0, lambda T, u: des(T, u, 1.0, 1.1, (.5, .52), (.5, .5))), (1.7, lambda T, u: salt(T, u, 1.2, 1.32, (.45, .6), (.5, .6)))],
     15: [(0, cold_fast), (2.2, lambda T, u: frost(icec(T, u, 1.1, 1.3, (.42, .5), (.42, .48)), .7 + .3 * u, 1.3))],
     16: [(0, lambda T, u: pole(T, u, 1.0, 1.15, (.5, .5), (.48, .48))), (1.8, lambda T, u: pole(T, u, 1.6, 1.8, (.6, .45), (.62, .43)))],
     17: [(0, lambda T, u: swing(T, u, 0)), (1.6, lambda T, u: swing(T, u, 1)), (3.6, lambda T, u: pole(T, u, 1.3, 1.45, (.6, .42), (.58, .44)))],
     18: [(0, lambda T, u: swing(T, 1, 2) if u < .55 else swing(T, 1, 2)), (1.7, lambda T, u: hook(T, u * .3))],   # ends on the hook frame: seamless loop
    }[idx]

CH = {'a': 'Coldest day ever', 'b': 'Hottest day ever'}
def choice(**kw): return dict({'type': 'choice', 'a': CH['a'], 'b': CH['b'], 'instant': True}, **kw)
OV = {   # compose.py overlays per scene (choice banner sits in the top ~18%; badges/stamps go just below it)
 0: [{'type': 'hook', 'text': 'COLDER THAN DRY ICE|OR 134°F?', 'y': .11}],
 1: [choice(instant=False, **{'from': .3})],
 2: [choice(), {'type': 'prompt', 'text': 'Comment A or B', 'pos': [.5, .3], 'from': .1}, {'type': 'countdown', 'secs': 3, 'pos': [.5, .5]}],
 3: [choice(), {'type': 'datestamp', 'text': 'A · Vostok Station, Antarctica · 21 July 1983', 'y': .2, 'from': .2}],
 4: [choice(), {'type': 'badge', 'value': '-89.2°C', 'unit': '(-128.6°F)', 'pos': [.5, .24], 'from': .4}],
 5: [choice(), {'type': 'label', 'text': 'POLAR NIGHT', 'color': [255, 222, 40], 'pos': [.5, .24], 'from': .3}],
 6: [choice(), {'type': 'label', 'text': 'SKIN FREEZES IN MINUTES', 'color': [255, 255, 255], 'pos': [.5, .24], 'from': .5}],
 7: [choice(), {'type': 'badge', 'value': '~-98°C', 'unit': 'by satellite', 'pos': [.5, .24], 'from': 1.0}],
 8: [choice(), {'type': 'datestamp', 'text': 'B · Death Valley, California · 10 July 1913', 'y': .2, 'from': .2}],
 9: [choice(), {'type': 'badge', 'value': '134°F', 'unit': '(56.7°C) world record', 'pos': [.5, .24], 'from': .4}],
 10: [choice()],
 11: [choice(), {'type': 'label', 'text': 'GROUND: 201°F', 'color': [255, 222, 40], 'pos': [.5, .24], 'from': .4}],
 12: [choice()],
 13: [choice(win='b'), {'type': 'prompt', 'text': 'Safer: B', 'pos': [.5, .3], 'from': 1.6}],
 14: [choice(win='b'), {'type': 'label', 'text': 'SHADE + WATER', 'color': [255, 222, 40], 'pos': [.5, .24], 'from': .4}],
 15: [choice(win='b'), {'type': 'label', 'text': 'NO POLAR GEAR = NO CHANCE', 'color': [255, 255, 255], 'pos': [.5, .24], 'from': .5}],
 16: [{'type': 'datestamp', 'text': 'South Pole · the 300 Club', 'y': .1, 'from': .2}],
 17: [],
 18: [{'type': 'cta', 'text': 'FOLLOW FOR MORE WOULD YOU RATHERS'}],
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
