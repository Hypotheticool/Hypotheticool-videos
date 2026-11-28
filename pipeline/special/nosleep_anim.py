"""Animate every scene of the WYR "3 days without sleep or 3 days without water?" over its Cycles plates (2D camera moves, cuts,
heat shimmer, sweat, blinks/microsleeps, hallucination shadows, science cards: BAC gauge, day counter, body water, soda cans, ECG).
python3 nosleep_anim.py <scene> [still_times...]  ->  nosleep/s<scene>/f_####.png + meta.json (overlays read by compose.py)"""
import sys, math, json, os
sys.path.insert(0, '/home/claude/pro')
import numpy as np, cv2, skia
import engine as E
ROOT = '/home/claude/b3d/nosleep'; CFG = json.load(open(f'{ROOT}/topic.json'))
FPS = 24; PAD = .75; XF = .35
idx = int(sys.argv[1]); D = CFG['durs'][idx]; NF = int(math.ceil((D + PAD) * FPS))
W, H = 1080, 1920
ease = lambda t: .5 - .5 * math.cos(math.pi * min(max(t, 0), 1))
eout = lambda t: 1 - (1 - min(max(t, 0), 1)) ** 3
clamp = lambda v, a=0., b=1.: max(a, min(b, v))
YEL, WHITE, BLUE, RED, TEAL, ORANGE = (255, 222, 40), (255, 255, 255), (130, 200, 255), (255, 90, 80), (90, 220, 210), (255, 150, 40)
A_TXT, B_TXT = '3 days, no sleep', '3 days, no water'

def wt(word, line=None, end=False):
    """local scene time (s) when `word` is spoken in this scene's line"""
    ln = E.shown(CFG['lines'][idx if line is None else line]); words = ln.split()
    clip = D - E.lead(idx) - E.GAP; tt = E.word_times(ln, clip)
    for k, w in enumerate(words):
        if word.lower() in w.lower(): return XF + E.lead(idx) + tt[k][1 if end else 0]
    raise KeyError(word)

def pts(name):
    p = {}
    fn = f'{ROOT}/plates/{name}.txt'
    if os.path.exists(fn):
        for l in open(fn):
            k, x, y = l.split(); p[k] = (float(x), float(y))
    return p

YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)
VIGM = (1 - .55 * np.clip(((XX / W - .5) ** 2 * 1.6 + (YY / H - .5) ** 2) ** .5 - .25, 0, 1) * 1.6)[..., None]
HOT = {'desert', 'desertcu', 'slump'}
PL = {}
def plate(name):
    """load a plate, upscale, grade into the palette: teal shadows; desert plates get a hot amber grade, night plates stay cool"""
    if name not in PL:
        im = cv2.imread(f'{ROOT}/plates/{name}.png', cv2.IMREAD_COLOR)
        if im.shape[1] != W: im = cv2.resize(im, (W, H), interpolation=cv2.INTER_CUBIC)
        im = im.astype(np.float32); lum = im.mean(2, keepdims=True) / 255
        im = im * .9 + (1 - lum) * np.float32([24, 12, 0]) * .9                    # BGR: teal into the shadows
        if name in HOT:
            im = im * np.float32([.74, .86, 1.02]) + np.float32([0, 6, 18]) * lum     # harsh amber heat
            im = np.clip((im - 128) * 1.08 + 118, 0, 255)                             # a bit more contrast, no blow-out
        elif name not in ('brain', 'kidney'): im = im * 1.4 + 4                         # night plates: lift so faces read on phones
        im = im * (.92 + .08 * lum) * VIGM
        PL[name] = np.clip(im, 0, 255)
    return PL[name]

def kb(name, u, z0, z1, c0=(.5, .5), c1=(.5, .5), rot=0.0, im=None):
    im = plate(name) if im is None else im; t = ease(u); z = z0 + (z1 - z0) * t
    cx = (c0[0] + (c1[0] - c0[0]) * t) * W; cy = (c0[1] + (c1[1] - c0[1]) * t) * H
    M = cv2.getRotationMatrix2D((cx, cy), rot, z); M[0, 2] += W / 2 - cx; M[1, 2] += H / 2 - cy
    return cv2.warpAffine(im, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

def shift(img, dx, dy): return cv2.warpAffine(img, np.float32([[1, 0, dx], [0, 1, dy]]), (W, H), borderMode=cv2.BORDER_REFLECT)
def shake(img, t, amp=10, decay=3.0):
    a = amp * math.exp(-max(t, 0) * decay)
    if a < .5: return img
    return shift(img, a * math.sin(t * 71), a * math.cos(t * 53))
def whip(img, t, dur=.12, vertical=False):
    if t >= dur or t < 0: return img
    k = int(70 * (1 - t / dur)) | 1
    if k < 3: return img
    ker = np.zeros((k, 1) if vertical else (1, k), np.float32); ker[...] = 1 / k
    return cv2.filter2D(img, -1, ker)
def flash(img, t, k=220, decay=7): return img + k * math.exp(-max(t, 0) * decay)
def blur(img, s): return cv2.GaussianBlur(img, (0, 0), s) if s > .3 else img
def dim(img, k): return img * np.float32(k)

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

# ---------------------------------------------------------------- effects
def heat(img, T, k=1.0, y0=.35):
    """heat shimmer: wavy refraction strongest near the ground, plus a hot sun glare at the top"""
    dx = (k * 5 * np.sin(YY * .045 + T * 9) * np.clip((YY / H - y0) / .3, 0, 1)).astype(np.float32)
    dy = (k * 2 * np.sin(XX * .03 + T * 7)).astype(np.float32)
    out = cv2.remap(img, XX + dx, YY + dy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    glare = np.exp(-(((XX - W * .8) / (W * .35)) ** 2 + ((YY - H * .08) / (H * .12)) ** 2))[..., None]
    return out + glare * np.float32([60, 150, 255]) * .35 * k * (1 + .08 * math.sin(T * 3))

DR = np.random.default_rng(5).random((40, 4))
def sweat(img, T, cx, cy, r, k=1.0):
    """sweat drops running down from around (cx, cy) (fractions)"""
    def f(c):
        for x, y, s, ph in DR[:14]:
            a = 2 * math.pi * x; px = W * cx + math.cos(a) * r * (.8 + .3 * y); py0 = H * cy + math.sin(a) * r * .5 - r * .3
            u = (T * (.35 + .4 * s) + ph) % 1; py = py0 + u * u * 160
            rr = 7 + 7 * s
            c.drawCircle(px, py, rr, E.P(E.C(200, 235, 255, 200 * k * (1 - u))))
            c.drawCircle(px - rr * .3, py - rr * .35, rr * .3, E.P(E.C(255, 255, 255, 230 * k * (1 - u))))
    return sk(img, f)

def blink(img, t0, t, dur=.5, close=1.0):
    """eyelids: black bars closing from top and bottom and opening again (a microsleep)"""
    u = (t - t0) / dur
    if u < 0 or u > 1: return img
    k = math.sin(math.pi * u) * close; hh = int(H * .5 * k)
    out = img.copy()
    if hh > 0:
        out[:hh] *= .03; out[H - hh:] *= .03
        e0, e1 = max(0, hh - 40), min(H, hh + 40); out[e0:e1] *= .4; out[max(0, H - hh - 40):H - hh + 40] *= .4
    return out

def hallucinate(img, T, k=1.0):
    """day-3 sleep loss: the room breathes and warps, colors drift, shadow figures waver in the dark corners"""
    dx = (k * 14 * np.sin(YY * .012 + T * 2.2)).astype(np.float32); dy = (k * 10 * np.sin(XX * .01 + T * 1.7)).astype(np.float32)
    out = cv2.remap(img, XX + dx, YY + dy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    out = out * (1 - .25 * k) + out[..., [1, 2, 0]] * .25 * k
    def f(c):
        for j, (x, y, s) in enumerate(((.12, .34, 1.0), (.88, .3, .85), (.2, .8, .7))):
            a = k * (.55 + .35 * math.sin(T * 2 + j * 2)); px = W * x + 18 * math.sin(T * 1.3 + j); py = H * y
            sc = 260 * s
            c.drawCircle(px, py - sc * 1.2, sc * .35, E.P(E.C(0, 0, 0, 230 * a), blur=18))
            c.drawRoundRect(skia.Rect.MakeXYWH(px - sc * .45, py - sc * .85, sc * .9, sc * 1.9), sc * .4, sc * .4, E.P(E.C(0, 0, 0, 210 * a), blur=26))
            c.drawRoundRect(skia.Rect.MakeXYWH(px - sc * .5, py - sc * 1.6, sc, sc * 2.7), sc * .5, sc * .5, E.P(E.C(140, 60, 200, 60 * a), blur=60, add=True))
            for e in (-1, 1):
                c.drawCircle(px + e * sc * .12, py - sc * 1.22, 12, E.P(E.C(255, 220, 120, 255 * a)))
                c.drawCircle(px + e * sc * .12, py - sc * 1.22, 30, E.P(E.C(255, 200, 80, 120 * a), blur=12, add=True))
    return sk(out, f)

def zzz(img, T, x, y, k=1.0):
    def f(c):
        for j in range(3):
            u = (T * .5 + j / 3) % 1
            text(c, 'Z', W * x + 60 * u + 20 * math.sin(T * 2 + j), H * y - 220 * u, 60 + 50 * u, (200, 220, 255), k * math.sin(math.pi * u))
    return sk(img, f)

def bg_card(name, u, z=1.15, darkk=.3, s=12): return blur(kb(name, u, z, z + .05), s) * darkk

def clock_digits(c, x, y, s, txt, a=1.0, col=(255, 40, 30)):
    """glowing red alarm-clock digits"""
    f = font(s); w = f.measureText(txt)
    c.drawString(txt, x - w / 2, y, f, E.P(E.C(*col, 160 * a), blur=14, add=True)); c.drawString(txt, x - w / 2, y, f, E.P(E.C(*col, 255 * a)))

def bed_frame(name, u, z0=1.0, z1=1.1, c0=(.5, .5), c1=(.5, .5), time_txt='3:00', T=0.0):
    """a bedroom plate with the alarm clock reading time_txt (digits drawn on the clock's projected screen)"""
    img = kb(name, u, z0, z1, c0, c1); p = pts(name).get('clock')
    if p and time_txt:
        t = ease(u); z = z0 + (z1 - z0) * t; cx = (c0[0] + (c1[0] - c0[0]) * t); cy = (c0[1] + (c1[1] - c0[1]) * t)
        X = W / 2 + (p[0] * W - cx * W) * z; Y = H / 2 + (p[1] * H - cy * H) * z
        img = sk(img, lambda c: clock_digits(c, X, Y + 9 * z, 26 * z, time_txt))
    return img

# ---------------------------------------------------------------- 2D cards
def clock_card(T, u, h_to=17):
    """big alarm clock counting the hours awake up to h_to"""
    img = bg_card('bed', u, 1.25, .32)
    hrs = h_to * eout(clamp(u * 1.4))
    def f(c):
        bx, by, bw, bh = W * .12, H * .3, W * .76, H * .17
        c.drawRoundRect(skia.Rect.MakeXYWH(bx, by, bw, bh), 40, 40, E.P(E.C(14, 14, 16, 250)))
        c.drawRoundRect(skia.Rect.MakeXYWH(bx + 30, by + 30, bw - 60, bh - 60), 24, 24, E.P(E.C(30, 4, 4, 255)))
        clock_digits(c, W / 2, by + bh * .72, 210, f'{int(hrs):02d}:{int((hrs % 1) * 60):02d}')
        text(c, 'HOURS AWAKE', W / 2, by + bh + 80, 60, WHITE)
    return sk(img, f)

def bac_card(T, u, v0, v1, show_limit=False):
    """dial gauge for blood alcohol concentration; needle eases from v0 to v1 (%); red zone from the US 0.08 limit"""
    img = bg_card('bedcu', u, 1.2, .3)
    v = v0 + (v1 - v0) * eout(clamp(u * 1.6)) + .0015 * math.sin(T * 9)
    def f(c):
        cx, cy, R = W / 2, H * .43, 330; vmax = .14
        ang = lambda x: math.radians(200 - 220 * x / vmax)
        for k in range(60):
            x0 = vmax * k / 60; x1 = vmax * (k + 1) / 60
            col = RED if x0 >= .08 else (YEL if x0 >= .05 else TEAL)
            a0, a1 = ang(x0), ang(x1)
            c.drawLine(cx + R * math.cos(a0), cy - R * math.sin(a0), cx + R * math.cos(a1), cy - R * math.sin(a1), E.P(E.C(*col, 235), 'stroke', 34, cap=False))
        for x in (0, .02, .04, .06, .08, .10, .12, .14):
            a = ang(x); c.drawLine(cx + (R - 40) * math.cos(a), cy - (R - 40) * math.sin(a), cx + (R - 75) * math.cos(a), cy - (R - 75) * math.sin(a), E.P(E.C(230, 230, 235, 230), 'stroke', 5))
            text(c, f'{x:.2f}', cx + (R - 125) * math.cos(a), cy - (R - 125) * math.sin(a) + 14, 34, (220, 225, 230))
        if show_limit:
            a = ang(.08); al = clamp(u * 3 - .3)
            c.drawLine(cx + (R + 25) * math.cos(a), cy - (R + 25) * math.sin(a), cx + (R + 90) * math.cos(a), cy - (R + 90) * math.sin(a), E.P(E.C(*RED, 255 * al), 'stroke', 9))
            text(c, 'RED = OVER THE U.S. LIMIT (0.08)', W / 2, H * .73, 46, RED, al)
        a = ang(v); c.drawLine(cx, cy, cx + (R - 30) * math.cos(a), cy - (R - 30) * math.sin(a), E.P(E.C(255, 255, 255, 255), 'stroke', 14))
        c.drawCircle(cx, cy, 34, E.P(E.C(240, 240, 245, 255)))
        text(c, 'BLOOD ALCOHOL %', cx, cy + 190, 52, WHITE)
    return sk(img, f)

def day_card(T, u, d_to=11):
    """day counter for Randy Gardner's record: calendar pages flipping 1..d_to + hours"""
    img = bg_card('bed', u, 1.2, .3)
    d = 1 + (d_to - 1) * eout(clamp(u * 1.5)); dd = int(round(d))
    def f(c):
        bx, by, bw, bh = W * .27, H * .25, W * .46, H * .22
        c.drawRoundRect(skia.Rect.MakeXYWH(bx, by, bw, bh), 30, 30, E.P(E.C(210, 206, 198, 250)))
        c.drawRoundRect(skia.Rect.MakeXYWH(bx, by, bw, bh * .25), 30, 30, E.P(E.C(*RED, 255)))
        c.drawRect(skia.Rect.MakeXYWH(bx, by + bh * .15, bw, bh * .1), E.P(E.C(*RED, 255)))
        f1 = font(64); s = 'DAY'; c.drawString(s, W / 2 - f1.measureText(s) / 2, by + bh * .19, f1, E.P(E.C(255, 255, 255, 255)))
        f2 = font(230); s = str(dd); c.drawString(s, W / 2 - f2.measureText(s) / 2, by + bh * .85, f2, E.P(E.C(25, 25, 30, 255)))
    return sk(img, f)

def body_water_card(T, u):
    """a human silhouette filling with water to ~60% (USGS: up to 60% of the adult body is water)"""
    img = bg_card('desert', u, 1.2, .28)
    lvl = .6 * eout(clamp(u * 1.4))
    sil = np.zeros((H, W), np.uint8); cx = W // 2
    cv2.circle(sil, (cx, int(H * .22)), 85, 255, -1)
    cv2.ellipse(sil, (cx, int(H * .36)), (150, 120), 0, 180, 360, 255, -1); cv2.rectangle(sil, (cx - 150, int(H * .36)), (cx + 150, int(H * .5)), 255, -1)
    for d in (-1, 1):
        cv2.line(sil, (cx + d * 140, int(H * .32)), (cx + d * 205, int(H * .5)), 255, 62)
        cv2.line(sil, (cx + d * 65, int(H * .5)), (cx + d * 80, int(H * .7)), 255, 80)
    top, bot = H * .14, H * .72; wl = bot - (bot - top) * lvl
    wave = wl + 10 * np.sin(XX * .02 + T * 4)
    m = (sil[..., None] > 0).astype(np.float32); water = (YY > wave)[..., None].astype(np.float32) * m
    out = img * (1 - m * .5) + m * np.float32([60, 50, 45]) * .5
    out = out * (1 - water) + water * (np.float32([230, 150, 40]) * (.75 + .25 * np.sin(YY * .05 + T * 3)[..., None]))
    edge = cv2.morphologyEx(sil, cv2.MORPH_GRADIENT, np.ones((7, 7), np.uint8))[..., None] / 255.
    out = out * (1 - edge) + edge * 255
    def f(c): text(c, f'{lvl * 100:.0f}% WATER', W / 2, H * .785, 70, BLUE)
    return sk(out, f)

def can(c, x, y, s, a=1.0):
    """a generic 12-oz soda can (no brand)"""
    p = E.P(E.C(220, 40, 40, 255 * a)); c.drawRoundRect(skia.Rect.MakeXYWH(x - s * .33, y - s, s * .66, s * 1.25), s * .1, s * .1, p)
    c.drawRoundRect(skia.Rect.MakeXYWH(x - s * .3, y - s * 1.06, s * .6, s * .1), s * .04, s * .04, E.P(E.C(200, 205, 210, 255 * a)))
    c.drawRoundRect(skia.Rect.MakeXYWH(x - s * .3, y + s * .2, s * .6, s * .08), s * .04, s * .04, E.P(E.C(200, 205, 210, 255 * a)))
    c.drawRect(skia.Rect.MakeXYWH(x - s * .33, y - s * .55, s * .66, s * .3), E.P(E.C(255, 255, 255, 200 * a)))
    c.drawRect(skia.Rect.MakeXYWH(x - s * .22, y - s * .9, s * .1, s * .95), E.P(E.C(255, 255, 255, 60 * a)))

def cans_card(T, u):
    img = sweat(heat(dim(kb('desertcu', .5 + .2 * u, 1.3, 1.36, (.5, .4)), .45), T, .6), T, .5, .33, 260, .8)
    def f(c):
        for k in range(3):
            g = eout(clamp(u * 3.2 - k * .45)); can(c, W * (.25 + .25 * k), H * .44 + 60 * (1 - g), 210 * (.6 + .4 * g), g)
        text(c, '3 x 12 OZ  ~  1 LITER', W / 2, H * .53, 54, WHITE, clamp(u * 3 - 1.4))
    return sk(img, f)

def ecg_card(T, u, bpm):
    """heart racing: an ECG trace scrolling, rate rising"""
    img = bg_card('desertcu', u, 1.3, .25)
    def f(c):
        y0 = H * .42; pth = skia.Path(); period = 60.0 / bpm * 260
        for x in range(0, W + 6, 6):
            ph = ((x + T * 520) % period) / period
            yy = y0
            if .30 < ph < .34: yy -= 40 * math.sin((ph - .30) / .04 * math.pi)
            elif .40 < ph < .42: yy += 30
            elif .42 < ph < .45: yy -= 230 * (1 - abs(ph - .435) / .015)
            elif .45 < ph < .47: yy += 50
            elif .55 < ph < .65: yy -= 50 * math.sin((ph - .55) / .1 * math.pi)
            (pth.moveTo if x == 0 else pth.lineTo)(x, yy)
        c.drawPath(pth, E.P(E.C(90, 255, 140, 255), 'stroke', 7, blur=1)); c.drawPath(pth, E.P(E.C(90, 255, 140, 120), 'stroke', 20, blur=14, add=True))
        hx, hy = W / 2, H * .27; s = 1 + .12 * max(0, math.sin(T * bpm / 60 * 2 * math.pi)) ** 8
        heart = skia.Path(); heart.moveTo(hx, hy + 70 * s); heart.cubicTo(hx - 150 * s, hy - 20 * s, hx - 70 * s, hy - 120 * s, hx, hy - 50 * s)
        heart.cubicTo(hx + 70 * s, hy - 120 * s, hx + 150 * s, hy - 20 * s, hx, hy + 70 * s); c.drawPath(heart, E.P(E.C(*RED, 255)))
    return sk(img, f)

def drop_card(T, u):
    """blood volume dropping: a big blood drop draining"""
    img = bg_card('desertcu', u, 1.25, .25)
    lv = 1 - .45 * eout(clamp(u * 1.4))
    def f(c):
        cx, cy, r = W / 2, H * .42, 190
        drop = skia.Path(); drop.moveTo(cx, cy - r * 1.9); drop.cubicTo(cx + r * .3, cy - r, cx + r, cy - r * .4, cx + r, cy + r * .2)
        drop.arcTo(skia.Rect.MakeXYWH(cx - r, cy - r * .8, 2 * r, 2 * r), 0, 180, False); drop.cubicTo(cx - r, cy - r * .4, cx - r * .3, cy - r, cx, cy - r * 1.9)
        c.save(); c.clipPath(drop, doAntiAlias=True)
        top = cy + r * 1.2 - (r * 3.1) * lv
        c.drawRect(skia.Rect.MakeXYWH(cx - r - 10, top + 8 * math.sin(T * 4), 2 * r + 20, r * 4), E.P(E.C(150, 10, 20, 255)))
        c.restore(); c.drawPath(drop, E.P(E.C(255, 255, 255, 230), 'stroke', 8))
        E.arrow(c, cx + r + 110, cy - 150, cx + r + 110, cy + 120, 18, RED, clamp(u * 3))
        text(c, 'BLOOD VOLUME', cx, cy + r + 150, 56, WHITE)
    return sk(img, f)

def weight_card(T, u):
    """10% of body weight lost as water = ~2 gallons (for a ~170 lb adult: 17 lb ~ 2 gal)"""
    img = bg_card('slump', u, 1.2, .28)
    def f(c):
        g = eout(clamp(u * 2.0))
        bw = W * .76; x0 = W * .12; y = H * .3
        c.drawRoundRect(skia.Rect.MakeXYWH(x0, y, bw, 70), 35, 35, E.P(E.C(60, 70, 80, 230)))
        for k in range(10):
            col = BLUE if (k == 9 and g > .2) else (200, 210, 220)
            c.drawRoundRect(skia.Rect.MakeXYWH(x0 + 8 + k * (bw - 16) / 10, y + 8, (bw - 16) / 10 - 8, 54), 18, 18, E.P(E.C(*col, 255 if k < 9 else 255 * (1 - .7 * g))))
        text(c, '1/10 OF YOUR WEIGHT', W / 2, y - 30, 56, WHITE)
        a2 = eout(clamp(u * 2.4 - .9))
        for k in range(2):
            jx = W * (.38 + .24 * k); jy = H * .45
            c.drawRoundRect(skia.Rect.MakeXYWH(jx - 90, jy - 150 + 40 * (1 - a2), 180, 240), 40, 40, E.P(E.C(210, 235, 255, 200 * a2)))
            c.drawRoundRect(skia.Rect.MakeXYWH(jx - 84, jy - 60 + 40 * (1 - a2), 168, 144), 34, 34, E.P(E.C(90, 170, 255, 220 * a2)))
            c.drawRoundRect(skia.Rect.MakeXYWH(jx - 30, jy - 190 + 40 * (1 - a2), 60, 50), 12, 12, E.P(E.C(230, 240, 250, 230 * a2)))
        text(c, '~2 GALLONS', W / 2, H * .555, 62, BLUE, a2)
    return sk(img, f)

def record_card(T, u):
    """the sleep-deprivation record book with a stamp: no longer tracked"""
    img = bg_card('bed', u, 1.2, .3)
    def f(c):
        c.save(); c.rotate(-4, W / 2, H * .4)
        c.drawRoundRect(skia.Rect.MakeXYWH(W * .17, H * .25, W * .66, H * .26), 20, 20, E.P(E.C(200, 190, 166, 250)))
        f1 = font(48);
        for k, s in enumerate(('RECORD:', 'LONGEST TIME', 'WITHOUT SLEEP')):
            c.drawString(s, W / 2 - f1.measureText(s) / 2, H * .31 + k * 70, f1, E.P(E.C(40, 35, 30, 255)))
        c.restore()
        g = eout(clamp(u * 2.5 - .5))
        if g > 0:
            c.save(); c.translate(W / 2, H * .45); c.rotate(-14); s = 1.6 - .6 * g; c.scale(s, s)
            c.drawRoundRect(skia.Rect.MakeXYWH(-330, -70, 660, 140), 20, 20, E.P(E.C(*RED, 255 * g), 'stroke', 12))
            f2 = font(66); t = 'NO LONGER TRACKED'; c.drawString(t, -f2.measureText(t) / 2, 24, f2, E.P(E.C(*RED, 255 * g))); c.restore()
    return sk(img, f)

def kidney_fail(T, u):
    img = kb('kidney', u, 1.15, 1.35, (.5, .45), (.5, .42))
    k = clamp(u * 2)
    gray = img.mean(2, keepdims=True); img = img * (1 - .6 * k) + gray * np.float32([.6, .6, 1.3]) * .6 * k
    pulse = .5 + .5 * math.sin(T * 10)
    return img * (1 - .15 * k * pulse) + np.float32([0, 0, 90]) * k * pulse * .35

def split(a, b, T, wob=8):
    xx = W * .5 + (YY - H / 2) * -.12 + wob * math.sin(T * 2)
    out = np.where((XX > xx)[..., None], b, a); return np.where((np.abs(XX - xx) < 5)[..., None], np.float32(255), out)

def hook_frame(T, u=None):
    """payoff on frame 1: tired Kai at 3 AM | Leo collapsed in the desert heat"""
    u = (T / 2.6) if u is None else u
    a = bed_frame('bedcu', u, 1.0, 1.06, (.78, .42), (.78, .40), None)
    b = heat(kb('slump', u, 1.15, 1.25, (.3, .42), (.3, .40)), T, 1.2)
    b = sweat(b, T, .74, .3, 170, .9)
    return split(a, b, T)

# ---------------------------------------------------------------- scenes
def S0(t, T):
    c = 1.25
    if t < c: return hook_frame(T)
    u = t - c; return whip(sweat(heat(kb('slump', u / 2, 1.35, 1.55, (.5, .4), (.5, .38)), T, 1.3), T, .5, .32, 260, 1.0), u)

def S1(t, T):
    c = wt('water') - .15
    if t < c: return bed_frame('bed', t / c, 1.0, 1.12, (.5, .48), (.47, .46), '3:00', T)
    u = t - c; return whip(heat(kb('desert', u / 2.5, 1.0, 1.12, (.5, .55), (.5, .52)), T, 1.0), u)

def S2(t, T):
    a = bed_frame('bedcu', .5, 1.03, 1.03, (.78, .41), (.78, .41), None); b = heat(kb('slump', .5, 1.2, 1.2, (.3, .41)), T, 1.0)
    return split(a, b, T)

def S3(t, T):
    c = wt('seventeen') - .15; c2 = wt('brain') - .2
    if t < c: return whip(bed_frame('bed', t / c, 1.12, 1.0, (.47, .46), (.5, .48), '3:00', T), t)
    if t < c2: return whip(clock_card(T, (t - c) / 1.4, 17), t - c)
    u = t - c2; return whip(kb('brain', u / 2.5, 1.05, 1.2, (.5, .48), (.52, .46)), u)

def S4(t, T):
    c = wt('blood') - .2
    if t < c: return blink(bed_frame('bedcu', t / c, 1.0, 1.08, (.45, .42), (.45, .4), None), .2, t, .45, .8)
    return whip(bac_card(T, (t - c) / 2.4, 0, .05), t - c)

def S5(t, T):
    c = wt('Over') - .15
    if t < c: return bac_card(T, t / c, .05, .10, True)
    u = t - c; img = bac_card(T, 1, .10, .10, True); return shake(flash(img * (1 + .25 * math.sin(T * 12)), u, 80, 6), u, 14, 3)

def S6(t, T):
    c = wt('seconds') - .15; c2 = wt('notice') - .3
    if t < c: return whip(kb('brain', t / c, 1.2, 1.32, (.5, .46), (.5, .45)), t)
    if t < c2:
        img = bed_frame('bedcu', (t - c) / (c2 - c), 1.08, 1.18, (.45, .4), (.45, .38), None)
        img = blink(img, 0, t - c, 1.2, 1.0); return whip(blink(img, 1.3, t - c, .9, 1.0), t - c)
    u = t - c2; return whip(bed_frame('bed', u / 2, 1.15, 1.25, (.45, .45), (.45, .44), '3:47', T), u)

def S7(t, T):
    c = wt('seeing') - .2
    if t < c: return whip(hallucinate(kb('bedfoot', t / c, 1.0, 1.08, (.5, .45)), T, .25 * t / c), t)
    u = t - c; return hallucinate(kb('bedfoot', u / 2.5, 1.08, 1.22, (.5, .45), (.5, .42)), T, .4 + .6 * clamp(u * 1.5))

def S8(t, T):
    c = wt('Randy') - .2; c2 = wt('tries') - .2
    if t < c: return whip(bed_frame('bed', t / c, 1.05, 1.15, (.5, .5), (.52, .48), '3:00', T), t, .15)
    if t < c2:
        img = bg_card('bed', (t - c) / 2, 1.2, .3)
        def f(cn):
            g = eout(clamp((t - c) * 3))
            cn.drawRoundRect(skia.Rect.MakeXYWH(W * .15, H * .3, W * .7, H * .2), 24, 24, E.P(E.C(196, 186, 162, 245 * g)))
            text(cn, 'RANDY GARDNER', W / 2, H * .37, 76, (40, 35, 30), g); text(cn, 'AGE 17', W / 2, H * .43, 64, RED, g)
        return whip(sk(img, f), t - c)
    u = t - c2; return whip(blink(bed_frame('bedcu', u / 2, 1.1, 1.2, (.42, .4), (.42, .38), None), .6, u, .6, .7), u)

def S9(t, T):
    c = wt('Moody') - .2
    if t < c: return day_card(T, t / c, 11)
    u = t - c; img = hallucinate(kb('bedfoot', u / 3, 1.1, 1.2, (.5, .45), (.5, .43)), T, .3)
    def f(cn):
        for k, (w, lab) in enumerate((('Moody', 'MOODY'), ('forgetful', 'FORGETFUL'), ('paranoid', 'PARANOID'))):
            a = clamp((t - wt(w) + .1) * 4)
            if a > 0: text(cn, lab, W / 2, H * (.29 + .07 * k), 80, (YEL, ORANGE, RED)[k], a)
    return whip(sk(img, f), u)

def S10(t, T):
    c = wt('recovers') - .25
    if t < c:
        img = bed_frame('asleep', t / c, 1.0, 1.1, (.5, .5), (.5, .47), None); return zzz(dim(img, .85), T, .45, .42)
    u = t - c; img = bed_frame('bed', u / 2, 1.1, 1.18, (.5, .45), (.5, .44), '9:00', T)
    return whip(img * np.float32([1.0, 1.08, 1.2]) + 18, u)     # morning: warmer, brighter

def S11(t, T): return record_card(T, t / (D + PAD - .3))

def S12(t, T):
    c = wt('body') - .2
    if t < c: return whip(heat(kb('desert', t / c, 1.15, 1.05, (.5, .5), (.5, .55)), T, 1.0), t)
    return whip(body_water_card(T, (t - c) / 2.2), t - c)

def S13(t, T):
    c = wt('liter') - .3; c2 = wt('three') - .2
    if t < c: return sweat(heat(kb('desertcu', t / c, 1.0, 1.12, (.5, .45), (.5, .42)), T, 1.0), T, .5, .33, 260, 1.0)
    if t < c2: return whip(sweat(heat(kb('desertcu', (t - c) / 1.6, 1.25, 1.4, (.5, .36), (.5, .34)), T, 1.0), T, .5, .3, 320, 1.0), t - c)
    return whip(cans_card(T, (t - c2) / 1.8), t - c2)

def S14(t, T):
    c = wt('heart') - .15; c2 = wt('brain') - .15
    if t < c: return whip(drop_card(T, t / c), t)
    if t < c2: return whip(ecg_card(T, (t - c) / 1.5, 90 + 60 * clamp((t - c) / 1.2)), t - c)
    u = t - c2; s = 1.0 - .03 * eout(clamp(u * 1.5))
    img = kb('brain', u / 2, 1.15 * s, 1.15 * s - .02, (.5, .47))
    def f(cn): text(cn, 'BRAIN CELLS SHRINK', W / 2, H * .3, 64, ORANGE, clamp(u * 3))
    return whip(sk(img, f), u)

def S15(t, T):
    c = wt('fail') - .2
    if t < c: return whip(kb('kidney', t / c, 1.0, 1.15, (.5, .48), (.5, .45)), t)
    u = t - c; return shake(kidney_fail(T, u / 1.6), u, 10, 3)

def S16(t, T):
    c = wt('danger') - .3
    if t < c: return weight_card(T, t / c)
    u = t - c; img = sweat(heat(kb('slump', u / 2, 1.25, 1.4, (.5, .4), (.5, .38)), T, 1.2), T, .5, .32, 250, 1.0)
    red = np.clip(((XX / W - .5) ** 2 + (YY / H - .5) ** 2) ** .5 * 1.8 - .2, 0, 1)[..., None]
    return whip(img * (1 - .5 * red) + red * np.float32([20, 20, 200]) * .5 * (.7 + .3 * math.sin(T * 6)), u)

def S17(t, T):
    c = wt('extreme') - .2
    if t < c: return kb('coolroom', t / c, 1.0, 1.12, (.5, .5), (.5, .47)) * np.float32([1.1, 1.0, .9])
    u = t - c; return whip(sweat(heat(kb('slump', u / 2.2, 1.15, 1.3, (.5, .45), (.5, .42)), T, 1.4), T, .5, .33, 230, 1.0), u)

def S18(t, T):
    c = wt('miserable') - .3; c2 = wt('bounce') - .25
    if t < c:
        a = bed_frame('bedcu', t / c, 1.0, 1.05, (.78, .42), (.78, .4), None); b = dim(heat(kb('slump', t / c, 1.2, 1.24, (.3, .42)), T, .8), .45)
        return split(a, b, T)
    if t < c2: return whip(blink(bed_frame('bedcu', (t - c) / 1.5, 1.12, 1.2, (.42, .4), (.42, .38), None), .1, t - c, .7, .8), t - c)
    u = t - c2; img = bed_frame('bed', u / 2, 1.0, 1.08, (.5, .45), (.5, .44), '9:00', T) * np.float32([1.0, 1.08, 1.2]) + 18
    return whip(img, u)

def S19(t, T):
    c = (D + PAD) - 1.05
    if t < c: return dim(heat(kb('slump', t / c, 1.4, 1.5, (.5, .4), (.5, .4)), T, 1.0), .8)
    return whip(hook_frame(T - t + (t - c), (t - c) / 2.6), t - c, vertical=True)   # loop: the first frame again

# ---------------------------------------------------------------- overlays
def choice(win=None, from_=0.0, instant=True):
    o = {'type': 'choice', 'a': A_TXT, 'b': B_TXT, 'from': from_}
    if instant: o['instant'] = True
    if win: o['win'] = win
    return o

def overlays():
    o = []
    if idx == 0: o += [{'type': 'hook', 'text': 'ONE OF THESE CAN|KILL YOU IN HOURS', 'y': .11}]
    if idx == 1: o += [choice(from_=.3, instant=False)]
    if 2 <= idx <= 17: o += [choice()]
    if idx == 2: o += [{'type': 'prompt', 'text': 'Comment A or B', 'pos': [.5, .3], 'from': .1}, {'type': 'countdown', 'secs': 3, 'pos': [.5, .5]}]
    if idx == 3: o += [{'type': 'datestamp', 'text': 'A · NO SLEEP', 'y': .2, 'from': .1}]
    if idx == 4: o += [{'type': 'badge', 'value': '17 HRS', 'unit': '≈ 0.05% BAC', 'pos': [.5, .25], 'from': wt('point') - .1},
                       {'type': 'label', 'text': 'SOURCE: CDC / NIOSH', 'pos': [.5, .78], 'color': (200, 210, 220), 'from': .6}]
    if idx == 5: o += [{'type': 'badge', 'value': '24 HRS', 'unit': '≈ 0.10% BAC', 'pos': [.5, .25], 'from': .2}]
    if idx == 6: o += [{'type': 'label', 'text': 'MICROSLEEPS', 'pos': [.5, .27], 'color': YEL, 'from': wt('seconds') - .1}]
    if idx == 7: o += [{'type': 'badge', 'value': 'DAY 3', 'unit': 'HALLUCINATIONS', 'pos': [.5, .25], 'from': wt('three') - .1},
                       {'type': 'label', 'text': '2018 REVIEW OF 21 STUDIES', 'pos': [.5, .78], 'color': (200, 210, 220), 'from': .8}]
    if idx == 8: o += [{'type': 'datestamp', 'text': 'SAN DIEGO · DEC 1963', 'y': .2, 'from': .1}]
    if idx == 9: o += [{'type': 'badge', 'value': '264', 'unit': 'HOURS AWAKE', 'pos': [.5, .2], 'from': wt('eleven') - .1}]
    if idx == 10: o += [{'type': 'badge', 'value': '14+', 'unit': 'HOURS ASLEEP', 'pos': [.5, .25], 'from': wt('fourteen') - .1}]
    if idx == 12: o += [{'type': 'datestamp', 'text': 'B · NO WATER', 'y': .2, 'from': .1}]
    if idx == 13: o += [{'type': 'badge', 'value': '1+ LITER', 'unit': 'SWEAT PER HOUR', 'pos': [.5, .25], 'from': wt('liter') - .2}]
    if idx == 15: o += [{'type': 'label', 'text': 'KIDNEYS FAIL', 'pos': [.5, .27], 'color': RED, 'from': wt('fail') - .1}]
    if idx == 17: o += [{'type': 'badge', 'value': '~1 WEEK', 'unit': 'COOL ROOM', 'pos': [.5, .25], 'from': wt('week') - .2}]
    if idx == 18: o += [choice(win='a', from_=wt('wins') - .3, instant=False)]
    if idx == 19: o += [{'type': 'cta', 'text': 'FOLLOW FOR MORE WOULD YOU RATHERS', 'from': .1}]
    return o

FN = globals()[f'S{idx}']
os.makedirs(f'{ROOT}/s{idx}', exist_ok=True)
if len(sys.argv) > 2:
    for ts in sys.argv[2:]:
        t = float(ts); img = FN(t, t + sum(CFG['durs'][:idx])); cv2.imwrite(f'{ROOT}/still_{idx}_{ts}.jpg', np.clip(img, 0, 255).astype(np.uint8)[::2, ::2], [cv2.IMWRITE_JPEG_QUALITY, 85])
    sys.exit()
for f in range(1, NF + 1):
    t = (f - 1) / FPS; img = FN(t, t + sum(CFG['durs'][:idx]))
    cv2.imwrite(f'{ROOT}/s{idx}/f_{f:04d}.png', np.clip(img, 0, 255).astype(np.uint8), [cv2.IMWRITE_PNG_COMPRESSION, 1])
json.dump({'frames': NF, 'overlays': overlays()}, open(f'{ROOT}/s{idx}/meta.json', 'w'))
print('scene', idx, 'frames', NF)
