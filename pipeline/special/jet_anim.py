"""Animate every scene of "The wall of their plane blew out" over its Cycles plates (jet_plate.py):
2D camera moves and cuts, shakes, cabin fog, debris pulled out of the hole, the flying plug, the falling phone, and the graphics.
python3 jet_anim.py <scene> [still_times...]  ->  jet/s<scene>/f_####.png + meta.json (overlays read by compose.py)"""
import sys, math, json, os, random
sys.path.insert(0, '/home/claude/pro')
import numpy as np, cv2, skia
import engine as E
ROOT = '/home/claude/b3d/jet'; CFG = json.load(open(f'{ROOT}/topic.json'))
FPS = 24; PAD = .75; XF = .35
idx = int(sys.argv[1]); D = CFG['durs'][idx]; NF = int(math.ceil((D + PAD) * FPS))
T0 = sum(CFG['durs'][:idx])
W, H = 1080, 1920
ease = lambda t: .5 - .5 * math.cos(math.pi * min(max(t, 0), 1))
eout = lambda t: 1 - (1 - min(max(t, 0), 1)) ** 3
clamp = lambda v, a=0., b=1.: max(a, min(b, v))
YEL, WHITE, BLUE, RED, GREEN, GREY, ORANGE = (255, 222, 40), (255, 255, 255), (130, 200, 255), (255, 95, 80), (120, 235, 150), (170, 178, 190), (255, 150, 50)
import re as _re
def wx(word, end=False, line=None):
    """exact-word cue (punctuation stripped), local scene time"""
    i = idx if line is None else line
    ln = E.shown(CFG['lines'][i]); words = ln.split(); clip = CFG['durs'][i] - E.lead(i) - E.GAP; tt = E.word_times(ln, clip)
    for k, w in enumerate(words):
        if _re.sub(r'[^a-z0-9]', '', w.lower()) == word.lower(): return XF + E.lead(i) + tt[k][1 if end else 0]
    raise KeyError(word)

YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)
VIGM = (1 - .55 * np.clip(((XX / W - .5) ** 2 * 1.6 + (YY / H - .5) ** 2) ** .5 - .25, 0, 1) * 1.6)[..., None]
PL = {}
COLD = {'blowout', 'hole', 'masks', 'cu_leo', 'cu_mia', 'masks_on', 'cu_kai'}
def plate(name):
    """load, upscale and grade into the palette: navy shadows + warm highlights; after the blowout the cabin goes cold blue-teal"""
    if name not in PL:
        im = cv2.imread(f'{ROOT}/plates/{name}.png', cv2.IMREAD_COLOR)
        if im.shape[1] != W: im = cv2.resize(im, (W, H), interpolation=cv2.INTER_CUBIC)
        im = im.astype(np.float32); lum = im.mean(2, keepdims=True) / 255
        if name in COLD: im = 255 * (im / 255) ** 1.25 * np.float32([1.12, 1.0, .86])          # BGR: push blue, pull red
        elif name in ('cabin',): im = 255 * (im / 255) ** 1.15 * np.float32([.9, .98, 1.08])
        elif name == 'exterior': im = 255 * (im / 255) ** 1.6 * np.float32([.78, .74, .78])     # tame the bright cloud deck (bloom)
        im = im * .92 + (1 - lum) * np.float32([24, 10, 0]) - 2
        im = im * (.9 + .12 * lum) * VIGM
        im = cv2.addWeighted(im, 1.25, cv2.GaussianBlur(im, (0, 0), 2.2), -.25, 0)
        PL[name] = np.clip(im, 0, 255)
    return PL[name]
PT = {}
def pts(name):
    if name not in PT:
        d = {}; p = f'{ROOT}/plates/{name}.txt'
        if os.path.exists(p):
            for ln in open(p): k, x, y = ln.split(); d[k] = (float(x) * W, float(y) * H)
        PT[name] = d
    return PT[name]
LASTM = [None]
def kb(name, u, z0, z1, c0=(.5, .5), c1=(.5, .5), rot=0.0, im=None):
    im = plate(name) if im is None else im; t = ease(u); z = z0 + (z1 - z0) * t
    if name == 'exterior' and im is PL.get(name): im = fog(im, TG[0], .22, -520, 90)      # clouds streaming past at altitude
    cx = (c0[0] + (c1[0] - c0[0]) * t) * W; cy = (c0[1] + (c1[1] - c0[1]) * t) * H
    M = cv2.getRotationMatrix2D((cx, cy), rot, z); M[0, 2] += W / 2 - cx; M[1, 2] += H / 2 - cy; LASTM[0] = (M, z)
    return cv2.warpAffine(im, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
def sp(name, key):
    M, z = LASTM[0]; x, y = pts(name)[key]; return M[0, 0] * x + M[0, 1] * y + M[0, 2], M[1, 0] * x + M[1, 1] * y + M[1, 2], z
def shift(img, dx, dy): return cv2.warpAffine(img, np.float32([[1, 0, dx], [0, 1, dy]]), (W, H), borderMode=cv2.BORDER_REFLECT)
def rumble(img, T, amp=6):
    return shift(img, amp * (math.sin(T * 37) * .6 + math.sin(T * 61) * .4), amp * .7 * (math.cos(T * 43) * .6 + math.sin(T * 29) * .4))
def shake(img, t, amp=24, decay=3.5):
    a = amp * math.exp(-max(t, 0) * decay)
    if a < .5: return img
    return shift(img, a * math.sin(t * 71), a * math.cos(t * 53))
def talk(t, amp=.006): return 1 + amp * (math.sin(t * 17) * .6 + math.sin(t * 11) * .4)
def ptalk(name, t, u, z0, z1, c0=(.5, .5), c1=(.5, .5), amp=.007):
    img = kb(name, u, z0, z1, c0, c1)
    return cv2.warpAffine(img, cv2.getRotationMatrix2D((W / 2, H / 2), 0, talk(t, amp)), (W, H), borderMode=cv2.BORDER_REFLECT)
def whip(img, t, dur=.12, vertical=False):
    if t >= dur or t < 0: return img
    k = int(70 * (1 - t / dur)) | 1
    if k < 3: return img
    ker = np.zeros((k, 1) if vertical else (1, k), np.float32); ker[...] = 1 / k
    return cv2.filter2D(img, -1, ker)
def flash(img, t, k=220, decay=7, col=(1, 1, 1)): return img + k * math.exp(-max(t, 0) * decay) * np.float32(col)
def blur(img, s): return cv2.GaussianBlur(img, (0, 0), s) if s > .3 else img
def sk(img, fn):
    a = np.clip(img, 0, 255).astype(np.uint8); bgra = np.dstack([a, np.full(a.shape[:2], 255, np.uint8)])
    s = skia.Surface(W, H); c = s.getCanvas()
    c.drawImage(skia.Image.fromarray(np.ascontiguousarray(bgra), colorType=skia.kBGRA_8888_ColorType), 0, 0)
    fn(c); return s.makeImageSnapshot().toarray()[..., :3].astype(np.float32)
def font(sz): return skia.Font(E.TF, sz)
def text(c, s, x, y, sz, col=WHITE, a=1.0, center=True):
    f = font(sz); w = f.measureText(s) if center else 0
    c.drawString(s, x - w / 2, y, f, E.P(E.C(0, 0, 0, 200 * a), 'stroke', max(6, sz // 8)))
    c.drawString(s, x - w / 2, y, f, E.P(E.C(*col, 255 * a)))
def panel(c, x, y, w, h, a=1.0, col=(120, 150, 180)):
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, y, w, h), 34, 34), E.P(E.C(12, 18, 28, 228 * a)))
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, y, w, h), 34, 34), E.P(E.C(*col, 150 * a), 'stroke', 4))
def arrow(c, x0, y0, x1, y1, col, a=1.0, w=14):
    c.drawLine(x0, y0, x1, y1, E.P(E.C(*col, 255 * a), 'stroke', w)); ang = math.atan2(y1 - y0, x1 - x0)
    p = skia.Path(); p.moveTo(x1 + math.cos(ang) * 30, y1 + math.sin(ang) * 30)
    p.lineTo(x1 + math.cos(ang + 2.4) * 40, y1 + math.sin(ang + 2.4) * 40); p.lineTo(x1 + math.cos(ang - 2.4) * 40, y1 + math.sin(ang - 2.4) * 40); p.close(); c.drawPath(p, E.P(E.C(*col, 255 * a)))

# ---------------------------------------------------------------- effects: fog, cold, debris pulled to the hole, flying plug
_rng = np.random.default_rng(4)
FOGT = cv2.resize(cv2.GaussianBlur(_rng.random((96, 54)).astype(np.float32), (0, 0), 3), (W * 2, H * 2), interpolation=cv2.INTER_CUBIC)
FOGT = (FOGT - FOGT.min()) / (FOGT.max() - FOGT.min())
def fog(img, T, k, vx=-60, vy=-20):
    """drifting condensation mist (rapid decompression makes the cabin air fog up)"""
    if k <= 0: return img
    ox = int((T * vx) % W); oy = int((T * vy) % H)
    f = FOGT[oy:oy + H, ox:ox + W]
    m = np.clip((f - .35) * 1.8, 0, 1)[..., None] * k
    return img * (1 - .55 * m) + np.float32([235, 228, 220]) * .55 * m
def cold(img, k):
    if k <= 0: return img
    lum = img.mean(2, keepdims=True)
    return img * (1 - .35 * k) + (lum * np.float32([1.25, 1.05, .8])) * .35 * k + np.float32([18, 6, 0]) * k
def frost(img, k):
    """frosty edges creeping in"""
    if k <= 0: return img
    e = np.clip(1 - ((XX / W - .5) ** 2 * 3.2 + (YY / H - .5) ** 2 * 1.6) ** .5 * 1.4, 0, 1)
    n = np.roll(FOGT[:H, :W], 37, 1); m = np.clip(((1 - e) * 1.6 - .7 + n * .5) * 2, 0, 1)[..., None] * k
    return img * (1 - .6 * m) + np.float32([250, 240, 225]) * .6 * m
DEB = [dict(a=random.Random(k).uniform(0, 6.28), r=random.Random(k + 99).uniform(.25, 1.0), ph=random.Random(k + 7).random(),
            col=random.Random(k + 3).choice([(240, 240, 235), (230, 220, 200), (255, 200, 60), (200, 220, 255), (90, 120, 200)]),
            s=random.Random(k + 5).uniform(14, 34)) for k in range(60)]
def debris(img, T, hx, hy, k=1.0, spread=900):
    """paper, napkins, cups and wrappers streaking toward the hole"""
    if k <= 0: return img
    def f(c):
        for d in DEB:
            u = (T * .9 + d['ph']) % 1; rr = spread * d['r'] * (1 - u) ** 1.6
            x = hx + math.cos(d['a']) * rr; y = hy + math.sin(d['a']) * rr * .8
            dx, dy = hx - x, hy - y; L = math.hypot(dx, dy) + 1e-3; st = 60 * (1 - u) + 10
            c.drawLine(x, y, x - dx / L * st * 1.6, y - dy / L * st * 1.6, E.P(E.C(255, 255, 255, 60 * k * (1 - u)), 'stroke', d['s'] * .4))
            c.save(); c.translate(x, y); c.rotate(T * 400 * d['r'] + d['a'] * 50)
            c.drawRect(skia.Rect.MakeXYWH(-d['s'] / 2, -d['s'] * .35, d['s'], d['s'] * .7), E.P(E.C(*d['col'], 240 * k * min(1, (1 - u) * 4))))
            c.restore()
        for j in range(18):   # air streaks
            u = (T * 1.7 + j / 18) % 1; ang = j * 2.4; rr = spread * 1.1 * (1 - u)
            x = hx + math.cos(ang) * rr; y = hy + math.sin(ang) * rr * .8
            c.drawLine(x, y, x + (hx - x) * .25, y + (hy - y) * .25, E.P(E.C(220, 235, 255, 70 * k * u), 'stroke', 5))
    return sk(img, f)
def hole_glow(img, x, y, r, k=1.0):
    def f(c): E.glow(c, x, y, r, (255, 230, 200), .5 * k)
    return sk(img, f)
def plug_fly(img, x, y, u, s=1.0, a=1.0, dirx=-1, diry=.35):
    """the panel / plug tumbling away from the fuselage"""
    if u <= 0 or u > 1.3: return img
    def f(c):
        px = x + dirx * 700 * u * s; py = y + diry * 600 * u * s + 300 * u * u * s
        c.save(); c.translate(px, py); c.rotate(u * 380); sc_ = s * (1 - .5 * u)
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(-50 * sc_, -95 * sc_, 100 * sc_, 190 * sc_), 14 * sc_, 14 * sc_), E.P(E.C(225, 228, 232, 255 * a)))
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(-50 * sc_, -95 * sc_, 100 * sc_, 190 * sc_), 14 * sc_, 14 * sc_), E.P(E.C(90, 95, 110, 255 * a), 'stroke', 5 * sc_))
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(-24 * sc_, -40 * sc_, 48 * sc_, 64 * sc_), 16 * sc_, 16 * sc_), E.P(E.C(40, 50, 70, 255 * a)))
        c.restore()
        for k in range(14):
            uu = u - k * .02
            if uu > 0: c.drawCircle(x + dirx * 700 * uu * s + math.sin(k * 3) * 20, y + diry * 600 * uu * s + 300 * uu * uu * s, 30 - k * 1.6, E.P(E.C(235, 235, 240, 70 - 4 * k)))
    return sk(img, f)

# ---------------------------------------------------------------- graphics cards
def thermo(c, x, y, h, frac, col, label, val, a):
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x - 34, y, 68, h), 34, 34), E.P(E.C(30, 38, 52, 255 * a)))
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x - 34, y, 68, h), 34, 34), E.P(E.C(*WHITE, 200 * a), 'stroke', 5))
    fh = (h - 40) * frac; c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x - 20, y + h - 20 - fh, 40, fh), 20, 20), E.P(E.C(*col, 255 * a)))
    c.drawCircle(x, y + h + 30, 62, E.P(E.C(*col, 255 * a))); c.drawCircle(x, y + h + 30, 62, E.P(E.C(*WHITE, 200 * a), 'stroke', 5))
    text(c, val, x, y - 40, 84, col, a); text(c, label, x, y + h + 160, 48, WHITE, a)
def temp_card(T, u):
    img = blur(kb('hole', .5, 1.15, 1.2), 9) * .35
    img = frost(img, .6)
    def f(c):
        g = eout(clamp(u * 3)); panel(c, 90, 420, 900, 1060, g)
        g1 = eout(clamp(u * 3 - .3)); thermo(c, 330, 640, 520, .62 * g1 + .02, (140, 200, 255), 'YOUR FREEZER', '0°F', g1)
        g2 = eout(clamp(u * 2.2 - .9)); thermo(c, 750, 640, 520, .02 + .02 * g2, (90, 140, 255), 'OUTSIDE', '-65°F', g2)
        if g2 > 0:
            text(c, '65° COLDER', 540, 1430, 70, YEL, g2)
    return sk(img, f)
def stopwatch(c, x, y, r, secs, maxs, a=1.0, col=RED, label=None):
    c.drawCircle(x, y, r, E.P(E.C(14, 20, 30, 235 * a))); c.drawCircle(x, y, r, E.P(E.C(*WHITE, 255 * a), 'stroke', 10))
    c.drawRect(skia.Rect.MakeXYWH(x - 22, y - r - 46, 44, 40), E.P(E.C(*WHITE, 255 * a)))
    for k in range(12):
        ang = math.radians(k * 30); c.drawLine(x + math.sin(ang) * r * .82, y - math.cos(ang) * r * .82, x + math.sin(ang) * r * .93, y - math.cos(ang) * r * .93, E.P(E.C(*WHITE, 200 * a), 'stroke', 5))
    pth = skia.Path(); pth.moveTo(x, y); pth.arcTo(skia.Rect.MakeLTRB(x - r * .78, y - r * .78, x + r * .78, y + r * .78), -90, 359.9 * min(secs, maxs) / maxs, False); pth.close()
    c.drawPath(pth, E.P(E.C(*col, 160 * a)))
    ang = math.radians(360 * secs / maxs); c.drawLine(x, y, x + math.sin(ang) * r * .8, y - math.cos(ang) * r * .8, E.P(E.C(*WHITE, 255 * a), 'stroke', 9))
    if label: text(c, label, x, y + r + 110, 96, YEL, a)
def tuc_card(T, u, t):
    img = blur(kb('blowout', .5, 1.1, 1.15), 9) * .33
    def f(c):
        g = eout(clamp(u * 4)); text(c, 'USEFUL CONSCIOUSNESS', 540, 390, 56, WHITE, g)
        text(c, 'AT 35,000 FEET', 540, 455, 52, GREY, g)
        secs = 60 * eout(clamp(u * 1.3)); stopwatch(c, 540, 740, 200, secs, 60, g, RED, None)
        # the 30 s - 1 min band
        p = skia.Path(); p.addArc(skia.Rect.MakeLTRB(540 - 230, 740 - 230, 540 + 230, 740 + 230), 90, 180); c.drawPath(p, E.P(E.C(*YEL, 230 * eout(clamp(u * 2 - .4))), 'stroke', 22))
        text(c, '30 s – 1 min', 540, 1060, 90, YEL, eout(clamp(u * 2 - .5)))
    return sk(img, f)
def order_card(T, u):
    img = blur(kb('masks_on', .5, 1.1, 1.12), 8) * .33
    def f(c):
        for k, (n, t1, col) in enumerate([('1', 'YOUR MASK', GREEN), ('2', 'THEN HELP OTHERS', YEL)]):
            g = eout(clamp(u * 3 - k * .7)); y = 560 + k * 300
            c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(110, y, 860, 230), 40, 40), E.P(E.C(14, 20, 30, 235 * g)))
            c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(110, y, 860, 230), 40, 40), E.P(E.C(*col, 255 * g), 'stroke', 7))
            c.drawCircle(220, y + 115, 70, E.P(E.C(*col, 255 * g))); text(c, n, 220, y + 150, 100, (20, 24, 30), g)
            text(c, t1, 330, y + 140, 70, WHITE, g, False)
    return sk(img, f)
def mask_card(T, u):
    """front diagram of a drop-down mask: pull the tube to start the chemical oxygen generator; the bag may stay flat"""
    img = blur(kb('masks', .5, 1.1, 1.12), 8) * .33
    def f(c):
        panel(c, 110, 380, 860, 1080, 1)
        g = eout(clamp(u * 3)); cx = 540
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(cx - 260, 430, 520, 90), 20, 20), E.P(E.C(180, 185, 195, 255 * g)))
        text(c, 'OXYGEN GENERATOR', cx, 492, 40, (30, 34, 44), g)
        c.drawLine(cx, 520, cx, 980, E.P(E.C(220, 235, 250, 255 * g), 'stroke', 9))
        # flat (uninflated) reservoir bag
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(cx + 20, 760, 150, 200), 30, 30), E.P(E.C(200, 230, 245, 150 * g)))
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(cx + 20, 760, 150, 200), 30, 30), E.P(E.C(*WHITE, 200 * g), 'stroke', 4))
        text(c, 'BAG', cx + 95, 1000, 40, GREY, g)
        p = skia.Path(); p.moveTo(cx - 110, 1000); p.lineTo(cx + 110, 1000); p.lineTo(cx + 70, 1150); p.lineTo(cx - 70, 1150); p.close()
        c.drawPath(p, E.P(E.C(*YEL, 255 * g)))
        g2 = eout(clamp(u * 3 - .6))
        if g2 > 0: arrow(c, cx - 250, 760, cx - 250, 960, RED, g2); text(c, 'PULL', cx - 250, 720, 60, RED, g2)
        g3 = clamp(u * 3 - 1.2)
        if g3 > 0:
            for k in range(14):
                a = (T * 1.4 + k / 14) % 1; c.drawCircle(cx + math.sin(k * 5 + T * 4) * 8, 540 + a * 440, 11, E.P(E.C(*BLUE, 230 * g3 * (1 - a * .4))))
            text(c, 'OXYGEN FLOWS', cx, 1290, 66, GREEN, g3); text(c, 'even if the bag stays flat', cx, 1360, 44, WHITE, g3)
    return sk(img, f)
def altimeter(img, alt, a=1.0):
    def f(c):
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(200, 470, 680, 250), 40, 40), E.P(E.C(12, 18, 28, 230 * a)))
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(200, 470, 680, 250), 40, 40), E.P(E.C(*GREEN, 230 * a), 'stroke', 6))
        text(c, 'ALTITUDE', 540, 540, 46, GREY, a); text(c, f'{int(alt):,} FT', 540, 670, 120, GREEN if alt <= 10000 else WHITE, a)
    return sk(img, f)
def bolt_card(T, u):
    """the plug from the inside: four bolt positions, all empty"""
    img = blur(kb('ext_hole', .5, 1.2, 1.25, (.5, .5), (.5, .5)), 8) * .35
    def f(c):
        g = eout(clamp(u * 3)); panel(c, 140, 420, 800, 1000, g)
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(330, 520, 420, 800), 60, 60), E.P(E.C(215, 220, 226, 255 * g)))
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(330, 520, 420, 800), 60, 60), E.P(E.C(80, 88, 100, 255 * g), 'stroke', 6))
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(450, 700, 180, 260), 50, 50), E.P(E.C(60, 70, 90, 255 * g)))
        text(c, 'DOOR PLUG', 540, 500, 50, WHITE, g)
        spots = [(300, 600), (780, 600), (300, 1240), (780, 1240)]
        for k, (x, y) in enumerate(spots):
            gk = eout(clamp(u * 3.2 - .8 - k * .35))
            c.drawCircle(x, y, 40, E.P(E.C(20, 24, 32, 255 * g))); c.drawCircle(x, y, 40, E.P(E.C(*WHITE, 200 * g), 'stroke', 5))
            if gk > 0:
                c.drawLine(x - 30, y - 30, x + 30, y + 30, E.P(E.C(*RED, 255 * gk), 'stroke', 12)); c.drawLine(x + 30, y - 30, x - 30, y + 30, E.P(E.C(*RED, 255 * gk), 'stroke', 12))
        g5 = eout(clamp(u * 3 - 2.3)); text(c, '4 BOLTS MISSING', 540, 1385, 70, RED, g5)
    return sk(img, f)
def zero_card(T, u):
    img = blur(kb('hole', .5, 1.2, 1.22), 8) * .35
    def f(c):
        g = eout(clamp(u * 3)); panel(c, 190, 620, 700, 460, g, GREEN)
        text(c, '0', 540, 900, 260 * (.8 + .2 * g), GREEN, g); text(c, 'DEATHS', 540, 1010, 70, WHITE, g)
    return sk(img, f)
def belt_sign(c, x, y, s, a=1.0, on=False):
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x - 160 * s, y - 110 * s, 320 * s, 220 * s), 30 * s, 30 * s), E.P(E.C(20, 24, 30, 240 * a)))
    col = (255, 255, 255) if on else (90, 96, 106)
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x - 160 * s, y - 110 * s, 320 * s, 220 * s), 30 * s, 30 * s), E.P(E.C(*col, 255 * a), 'stroke', 6 * s))
    c.drawCircle(x, y - 45 * s, 24 * s, E.P(E.C(*col, 255 * a)))
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x - 30 * s, y - 15 * s, 60 * s, 80 * s), 16 * s, 16 * s), E.P(E.C(*col, 255 * a)))
    c.drawLine(x - 80 * s, y + 30 * s, x + 80 * s, y + 30 * s, E.P(E.C(*col, 255 * a), 'stroke', 10 * s))
    c.drawRect(skia.Rect.MakeXYWH(x - 20 * s, y + 16 * s, 40 * s, 28 * s), E.P(E.C(*col, 255 * a)))
def phone_fall(img, T, u, x0=540, y0=300):
    if u <= 0: return img
    def f(c):
        py = y0 + 1500 * u * u; px = x0 + 60 * math.sin(u * 9)
        for k in range(10):
            uu = u - k * .015
            if uu > 0: c.drawCircle(x0 + 60 * math.sin(uu * 9), y0 + 1500 * uu * uu, 18 - k * 1.5, E.P(E.C(255, 255, 255, 60 - 5 * k)))
        c.save(); c.translate(px, py); c.rotate(u * 900)
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(-30, -60, 60, 120), 12, 12), E.P(E.C(20, 22, 26, 255)))
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(-25, -54, 50, 108), 8, 8), E.P(E.C(90, 140, 230, 255)))
        c.restore()
    return sk(img, f)

# ---------------------------------------------------------------- scenes
def hook_shot(t, T, z0=1.45, z1=1.65, k=1.0):
    img = kb('blowout', clamp(t / 3.0), z0, z1, (.56, .5), (.58, .49))
    hx, hy, z = sp('blowout', 'hole')
    img = hole_glow(img, hx, hy, 200 * z, .5)
    img = fog(img, T, .55 * k); img = debris(img, T, hx, hy, k, 1000)
    return rumble(img, T, 7)
def S0(t, T): return flash(hook_shot(t, T), t + .15, 70, 6)

def S1(t, T):
    c = wx('the') - .1
    if t < c: return kb('exterior', t / c, 1.05, 1.15, (.5, .5), (.5, .47))
    return whip(kb('cabin', (t - c) / (D + PAD - c), 1.0, 1.1, (.5, .5), (.52, .47)), t - c)

def S2(t, T):
    c = wx('at') - .1
    if t < c: return kb('cabin', t / c, 1.12, 1.35, (.55, .45), (.62, .42))
    img = kb('exterior', (t - c) / (D + PAD - c), 1.2, 1.05, (.48, .45), (.5, .5))
    return whip(img, t - c)

def S3(t, T):
    b = wx('bang') - .05; c = wx('a', line=None) if False else wx('panel') - .15
    if t < c:
        img = kb('cabin', t / c, 1.35, 1.42, (.62, .42), (.62, .42))
        img = shake(img, t - b, 30, 3) if t >= b else img
        return flash(img, t - b, 160, 9) if t >= b else img
    u = t - c; img = kb('exterior', clamp(u / 2.5), 1.6, 1.75, (.55, .55), (.58, .55))
    px, py, z = sp('exterior', 'plug')
    img = sk(img, lambda cv: (E.glow(cv, px, py, 90, (255, 240, 220), .8 * math.exp(-u * 2))))
    img = plug_fly(img, px, py, clamp(u / 1.6), 1.3, 1, -1, .5)
    return whip(shake(img, u, 16, 4), u)

def S4(t, T):
    c = wx('fog') - .15; c2 = wx('and') - .1
    if t < c: return hook_shot(t + 1.0, T, 1.2, 1.35, .8)
    u = t - c
    img = kb('hole', u / (D + PAD - c), 1.0, 1.12, (.4, .5), (.35, .5))
    hx, hy, z = sp('hole', 'hole')
    img = debris(img, T, hx, hy, .7, 800); img = fog(img, T, clamp(.4 + u * .5, 0, .85))
    img = cold(img, clamp((t - c2) / 1.0)); img = frost(img, .7 * clamp((t - c2) / 1.2))
    return whip(rumble(img, T, 5), u)

def S5(t, T):
    c = wx('way') - .15
    if t < c:
        img = kb('hole', t / c, 1.15, 1.4, (.35, .48), (.3, .47)); hx, hy, z = sp('hole', 'hole')
        img = fog(img, T, .45); img = cold(img, .8); img = frost(img, .5)
        return rumble(img, T, 4)
    return whip(temp_card(T, clamp((t - c) / 1.8)), t - c)

def S6(t, T):
    c = wx('cant') - .25
    if t < c: return tuc_card(T, clamp(t / (c - .2)), t)
    u = t - c; img = kb('cu_leo', u / (D + PAD - c), 1.0, 1.1, (.5, .45), (.5, .43))
    img = fog(img, T, .35); img = cold(img, .6)
    dbl = shift(img, 18 * math.sin(T * 3), 0); img = img * .6 + dbl * .4          # foggy double vision (hypoxia)
    img = blur(img, 2 + 2 * math.sin(T * 2) ** 2)
    return whip(img, u)

def S7(t, T):
    img = ptalk('cu_leo', T, t / (D + PAD), 1.12, 1.22, (.5, .45), (.5, .43), .014)
    return rumble(cold(fog(img, T, .3), .5), T, 4)
def S8(t, T):
    img = ptalk('cu_mia', T, t / (D + PAD), 1.0, 1.15, (.5, .45), (.5, .43), .014)
    return whip(rumble(cold(fog(img, T, .3), .5), T, 4), t)

def S9(t, T):
    c = wx('help') - .1
    if t < c: return kb('cu_mia', t / c, 1.15, 1.22, (.5, .43), (.5, .42))
    u = t - c; img = order_card(T, clamp(u / 1.4))
    p = wx('pass') - .1
    if t > p: img = img * (1 - .5 * clamp((t - p) / 1.0) * (1 - VIGM[..., 0:1] ** 3))
    return whip(img, u)

def S10(t, T):
    c = wx('the', line=None) if False else wx('bag') - .15
    if t < c:
        img = kb('masks', t / c, 1.15, 1.45, (.42, .62), (.4, .66))
        img = shift(img, 0, 14 * math.sin(T * 4))        # masks swinging
        img = sk(img, lambda cv: (arrow(cv, 840, 760, 840, 1020, RED, clamp(t * 3)), text(cv, 'PULL DOWN', 840, 720, 64, RED, clamp(t * 3))))
        return cold(fog(img, T, .25), .4)
    return whip(mask_card(T, clamp((t - c) / 1.6)), t - c)

def S11(t, T):
    img = kb('masks_on', t / (D + PAD), 1.0, 1.15, (.5, .5), (.5, .46))
    img = cold(fog(img, T, .2), .3)
    tm = 600 - 9 * (t + T0 - sum(CFG['durs'][:11]))
    def f(c):
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(300, 1380, 480, 190), 34, 34), E.P(E.C(12, 18, 28, 225)))
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(300, 1380, 480, 190), 34, 34), E.P(E.C(*GREEN, 230), 'stroke', 6))
        text(c, 'OXYGEN LEFT', 540, 1440, 42, GREY, 1); text(c, f'{int(tm) // 60}:{int(tm) % 60:02d}', 540, 1540, 92, GREEN, 1)
    return rumble(sk(img, f), T, 2)

def S12(t, T):
    c = wx('where') - .1
    alt = 35000 - 25000 * ease(clamp((t - .3) / (D - .3)))
    img = kb('exterior', t / (D + PAD), 1.1, 1.3, (.5, .45), (.5, .55), rot=-6 * ease(clamp(t / 1.2)))
    img = altimeter(img, alt)
    if t > c: img = sk(img, lambda cv: text(cv, 'BREATHABLE AIR', 540, 800, 64, GREEN, clamp((t - c) * 3)))
    return img

def S13(t, T):
    img = ptalk('cu_kai', T, t / (D + PAD), 1.0, 1.15, (.5, .45), (.5, .43), .012)
    img = cold(fog(img, T, .3), .4)
    img = debris(img, T, -150, 700, .8, 1200)
    return rumble(img, T, 5)

def S14(t, T):
    img = kb('cabin', t / (D + PAD), 1.0, 1.08)
    g = np.repeat(img.mean(2, keepdims=True), 3, 2); k = clamp(t / .6)
    return flash(img * (1 - k * .7) + g * k * .7, t, 90, 6) * (1 - .3 * k)

def S15(t, T):
    c = wx('alaska') - .1
    img = kb('ext_hole', t / (D + PAD), 1.0, 1.15, (.55, .5), (.6, .48))
    px, py, z = sp('ext_hole', 'plug')
    return img if t < c else img
def S16(t, T):
    b = wx('blew') - .1
    img = kb('ext_hole', t / (D + PAD), 1.2, 1.45, (.6, .48), (.68, .48))
    px, py, z = sp('ext_hole', 'plug')
    img = hole_glow(img, px, py, 120 * z, .4)
    if t > b: img = plug_fly(shake(img, t - b, 14, 4), px, py, clamp((t - b) / 1.4), 1.2, 1, -.6, .9)
    return img

def S17(t, T):
    c = wx('nobody') - .1
    if t < c:
        img = kb('hole', t / c, 1.0, 1.15, (.45, .55), (.42, .58))
        return img
    return whip(zero_card(T, clamp((t - c) / 1.0)), t - c)

def S18(t, T): return bolt_card(T, clamp(t / (D - .2)))

def S19(t, T):
    c = wx('landed') - .1
    if t < c:
        img = kb('exterior', t / c, 1.3, 1.45, (.55, .5), (.55, .52))
        px, py, z = sp('exterior', 'plug')
        return phone_fall(img, T, clamp(t / c), px, py)
    u = t - c; img = kb('phone', u / (D + PAD - c), 1.05, 1.35, (.5, .5), (.5, .62))
    return whip(img, u, vertical=True)

def S20(t, T):
    c = (D + PAD) - .9
    if t < c:
        img = kb('cabin', t / c, 1.0, 1.12, (.5, .5), (.55, .45))
        e = wx('even') - .1
        on = t < e or (int(t * 4) % 2 == 0 and t < e + 1.0)
        return sk(img, lambda cv: belt_sign(cv, 540, 560, 1.5, clamp(t * 3), on))
    u = t - c; return whip(hook_shot(0, T), u, vertical=True)

# ---------------------------------------------------------------- overlays
def overlays():
    wo = lambda *a, **k: wx(*a, **k) - XF
    o = []
    if idx == 0: o += [{'type': 'hook', 'text': 'A HOLE IN THE PLANE|AT 35,000 FEET', 'y': .11}]
    if idx == 1: o += [{'type': 'label', 'text': 'SUNDAY AFTER THANKSGIVING', 'pos': [.5, .12], 'color': YEL, 'from': .2},
                       {'type': 'label', 'text': 'BUSIEST DAY TO FLY (TSA)', 'pos': [.5, .175], 'color': WHITE, 'from': wo('busiest') - .1}]
    if idx == 2: o += [{'type': 'badge', 'value': '35,000', 'unit': 'FEET', 'pos': [.5, .13], 'from': wo('thirtyfive') - .1, 'size': 80},
                       {'type': 'label', 'text': '~24 EMPIRE STATE BUILDINGS', 'pos': [.5, .2], 'color': WHITE, 'from': wo('feet')}]
    if idx == 3: o += [{'type': 'label', 'text': 'BANG!', 'pos': [.5, .12], 'color': RED, 'from': wo('bang') - .05, 'to': wo('panel') - .2}]
    if idx == 4: o += [{'type': 'label', 'text': 'AIR RUSHING OUT', 'pos': [.5, .12], 'color': WHITE, 'from': .1, 'to': wo('fog') - .2},
                       {'type': 'label', 'text': 'CABIN FOG', 'pos': [.5, .12], 'color': BLUE, 'from': wo('fog') - .1}]
    if idx == 5: o += [{'type': 'badge', 'value': '-65', 'unit': '°F OUTSIDE', 'pos': [.5, .13], 'from': wo('minus') - .1, 'to': wo('way') - .2, 'size': 80}]
    if idx == 7: o += [{'type': 'label', 'text': 'LEO', 'pos': [.5, .12], 'color': YEL, 'from': .1}]
    if idx == 8: o += [{'type': 'label', 'text': 'MIA', 'pos': [.5, .12], 'color': RED, 'from': .1}]
    if idx == 9: o += [{'type': 'label', 'text': 'YOUR MASK FIRST', 'pos': [.5, .12], 'color': GREEN, 'from': .1}]
    if idx == 11: o += [{'type': 'badge', 'value': '10+', 'unit': 'MINUTES OF OXYGEN', 'pos': [.5, .13], 'from': wo('ten') - .1, 'size': 80}]
    if idx == 12: o += [{'type': 'label', 'text': 'EMERGENCY DESCENT', 'pos': [.5, .12], 'color': YEL, 'from': .1}]
    if idx == 13: o += [{'type': 'label', 'text': 'KAI', 'pos': [.5, .12], 'color': GREEN, 'from': .1}]
    if idx == 14: o += [{'type': 'label', 'text': 'THE TWIST', 'pos': [.5, .12], 'color': YEL, 'from': .1},
                        {'type': 'label', 'text': 'THIS REALLY HAPPENED', 'pos': [.5, .175], 'color': WHITE, 'from': wo('this') - .1}]
    if idx == 15: o += [{'type': 'datestamp', 'text': 'PORTLAND, OREGON · JAN 5, 2024'},
                        {'type': 'label', 'text': 'ALASKA AIRLINES FLIGHT 1282', 'pos': [.5, .175], 'color': WHITE, 'from': wo('alaska') - .1}]
    if idx == 16: o += [{'type': 'badge', 'value': '14,830', 'unit': 'FEET (NTSB)', 'pos': [.5, .13], 'from': wo('fifteen') - .1, 'size': 80},
                        {'type': 'label', 'text': 'DOOR PLUG: AN UNUSED EXIT', 'pos': [.5, .2], 'color': WHITE, 'from': wo('plug') - .1}]
    if idx == 17: o += [{'type': 'label', 'text': '2 SEATS BY THE HOLE: EMPTY', 'pos': [.5, .12], 'color': YEL, 'from': .2, 'to': wo('nobody') - .2}]
    if idx == 18: o += [{'type': 'label', 'text': 'NTSB INVESTIGATION', 'pos': [.5, .12], 'color': WHITE, 'from': .1}]
    if idx == 19: o += [{'type': 'badge', 'value': '~2.8', 'unit': 'MILE FALL', 'pos': [.5, .13], 'from': wo('fell') - .1, 'size': 80},
                        {'type': 'label', 'text': 'STILL WORKED, IN AIRPLANE MODE', 'pos': [.5, .2], 'color': GREEN, 'from': wo('still') - .1}]
    if idx == 20: o += [{'type': 'cta', 'text': 'FOLLOW FOR MORE STORIES', 'from': .2}]
    return o

TG = [0.0]
FN = globals()[f'S{idx}']
os.makedirs(f'{ROOT}/s{idx}', exist_ok=True)
if len(sys.argv) > 2:
    for ts in sys.argv[2:]:
        t = float(ts); TG[0] = t + T0; img = FN(t, t + T0); cv2.imwrite(f'{ROOT}/still_{idx}_{ts}.jpg', np.clip(img, 0, 255).astype(np.uint8)[::2, ::2], [cv2.IMWRITE_JPEG_QUALITY, 85])
    sys.exit()
for f in (range(1, NF + 1) if not os.environ.get('META_ONLY') else []):
    t = (f - 1) / FPS; TG[0] = t + T0; img = FN(t, t + T0)
    cv2.imwrite(f'{ROOT}/s{idx}/f_{f:04d}.png', np.clip(img, 0, 255).astype(np.uint8), [cv2.IMWRITE_PNG_COMPRESSION, 1])
json.dump({'frames': NF, 'overlays': overlays()}, open(f'{ROOT}/s{idx}/meta.json', 'w'))
print('scene', idx, 'frames', NF)
