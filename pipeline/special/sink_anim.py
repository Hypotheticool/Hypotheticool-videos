"""Animate every scene of "The car went into the lake" over its Cycles plates (2D camera moves, cuts, splashes, bubbles, diagrams).
python3 sink_anim.py <scene> [still_times...]  ->  sink/s<scene>/f_####.png + meta.json (overlays read by compose.py)"""
import sys, math, json, os
sys.path.insert(0, '/home/claude/pro')
import numpy as np, cv2, skia
import engine as E
ROOT = '/home/claude/b3d/sink'; CFG = json.load(open(f'{ROOT}/topic.json'))
FPS = 24; PAD = .75; XF = .35
idx = int(sys.argv[1]); D = CFG['durs'][idx]; NF = int(math.ceil((D + PAD) * FPS))
T0 = sum(CFG['durs'][:idx])
W, H = 1080, 1920
ease = lambda t: .5 - .5 * math.cos(math.pi * min(max(t, 0), 1))
eout = lambda t: 1 - (1 - min(max(t, 0), 1)) ** 3
clamp = lambda v, a=0., b=1.: max(a, min(b, v))
YEL, WHITE, BLUE, RED, GREEN = (255, 222, 40), (255, 255, 255), (130, 200, 255), (255, 95, 80), (120, 235, 150)

def wt(word, line=None, end=False):
    """local scene time (s) when `word` is spoken in this scene's line"""
    ln = E.shown(CFG['lines'][idx if line is None else line]); words = ln.split()
    clip = D - E.lead(idx) - E.GAP; tt = E.word_times(ln, clip)
    for k, w in enumerate(words):
        if word.lower() in w.lower(): return XF + E.lead(idx) + tt[k][1 if end else 0]
    raise KeyError(word)

YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)
VIGM = (1 - .55 * np.clip(((XX / W - .5) ** 2 * 1.6 + (YY / H - .5) ** 2) ** .5 - .25, 0, 1) * 1.6)[..., None]
PL = {}
def plate(name):
    """load a plate, upscale, grade into the palette: deep teal shadows, warm highlights"""
    if name not in PL:
        im = cv2.imread(f'{ROOT}/plates/{name}.png', cv2.IMREAD_COLOR)
        if im.shape[1] != W: im = cv2.resize(im, (W, H), interpolation=cv2.INTER_CUBIC)
        im = im.astype(np.float32); lum = im.mean(2, keepdims=True) / 255
        im = im * .9 + (1 - lum) * np.float32([24, 12, 0]) * .9 - 3
        im = im * (.92 + .1 * lum) * VIGM
        im = cv2.addWeighted(im, 1.25, cv2.GaussianBlur(im, (0, 0), 2.2), -.25, 0)   # restore crispness after the upscale
        if name == 'shore': im = im * np.clip(1.25 - YY / H * .9, .5, 1)[..., None]   # the near snowbank was too bright
        PL[name] = np.clip(im, 0, 255)
    return PL[name]

def wet_window():
    """the driver window plate with the lake outside up to the lower third of the glass (water reaching the windows)"""
    if 'window_wet' not in PL:
        base = plate('window_cu').copy()
        def f(c):
            c.save(); c.clipRect(skia.Rect.MakeLTRB(0, 0, W * .845, H * .455))
            top = H * .33; pth = skia.Path(); pth.moveTo(0, H)
            for xp in range(0, W + 40, 40): pth.lineTo(xp, top + 10 * math.sin(xp * .015))
            pth.lineTo(W, H); pth.close()
            c.drawPath(pth, E.P(shader=E.linear((0, top), (0, H * .46), [E.C(30, 80, 90, 235), E.C(6, 24, 30, 250)])))
            c.drawPath(pth, E.P(E.C(190, 225, 235, 180), 'stroke', 4)); c.restore()
        PL['window_wet'] = sk(base, f)
    return PL['window_wet']

def kb(name, u, z0, z1, c0=(.5, .5), c1=(.5, .5), rot=0.0, im=None):
    im = (wet_window() if name == 'window_wet' else plate(name)) if im is None else im; t = ease(u); z = z0 + (z1 - z0) * t
    cx = (c0[0] + (c1[0] - c0[0]) * t) * W; cy = (c0[1] + (c1[1] - c0[1]) * t) * H
    M = cv2.getRotationMatrix2D((cx, cy), rot, z); M[0, 2] += W / 2 - cx; M[1, 2] += H / 2 - cy
    return cv2.warpAffine(im, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

def shift(img, dx, dy): return cv2.warpAffine(img, np.float32([[1, 0, dx], [0, 1, dy]]), (W, H), borderMode=cv2.BORDER_REFLECT)
def shake(img, t, amp=10, decay=3.0):
    a = amp * math.exp(-t * decay)
    if a < .5: return img
    return shift(img, a * math.sin(t * 71), a * math.cos(t * 53))
def bob(img, T, amp=6): return shift(img, amp * .4 * math.sin(T * 1.3), amp * math.sin(T * 1.9))   # floating car rocking
def talk(t, amp=.006): return 1 + amp * (math.sin(t * 17) * .6 + math.sin(t * 11) * .4)
def ptalk(name, t, u, z0, z1, c0=(.5, .5), c1=(.5, .5), amp=.007):
    img = kb(name, u, z0, z1, c0, c1)
    return cv2.warpAffine(img, cv2.getRotationMatrix2D((W / 2, H / 2), 0, talk(t, amp)), (W, H), borderMode=cv2.BORDER_REFLECT)

def whip(img, t, dur=.12, vertical=False):
    if t >= dur: return img
    k = int(70 * (1 - t / dur)) | 1
    if k < 3: return img
    ker = np.zeros((k, 1) if vertical else (1, k), np.float32); ker[...] = 1 / k
    return cv2.filter2D(img, -1, ker)
def flash(img, t, k=220, decay=7): return img + k * math.exp(-max(t, 0) * decay)
def blur(img, s): return cv2.GaussianBlur(img, (0, 0), s) if s > .3 else img
def grade(img, mul=(1, 1, 1), add=0.0): return img * np.float32(mul)[None, None, :] + add

def sk(img, fn):
    a = np.clip(img, 0, 255).astype(np.uint8); bgra = np.dstack([a, np.full(a.shape[:2], 255, np.uint8)])
    s = skia.Surface(W, H); c = s.getCanvas()
    c.drawImage(skia.Image.fromarray(np.ascontiguousarray(bgra), colorType=skia.kBGRA_8888_ColorType), 0, 0)
    fn(c); return s.makeImageSnapshot().toarray()[..., :3].astype(np.float32)
def font(sz): return skia.Font(E.TF, sz)
def text(c, s, x, y, sz, col=(255, 255, 255), a=1.0, center=True):
    f = font(sz); w = f.measureText(s) if center else 0
    c.drawString(s, x - w / 2, y, f, E.P(E.C(0, 0, 0, 200 * a), 'stroke', max(6, sz // 8)))
    c.drawString(s, x - w / 2, y, f, E.P(E.C(*col, 255 * a)))

# ---------------------------------------------------------------- effects
rng = np.random.default_rng(5); FL = rng.random((160, 4))
def snow(img, T, k=1.0, vy=60):
    if k <= 0: return img
    lay = np.zeros_like(img)
    for x, y, s, b in FL:
        px = int((x * W + math.sin(T * .8 + y * 11) * 30 + T * 12) % W); py = int((y * H + T * vy * (.4 + s)) % H)
        r = 1 + int(s * s * 6); v = (.35 + .65 * b) * k
        cv2.circle(lay, (px, py), r, (235 * v, 240 * v, 245 * v), -1, cv2.LINE_AA)
    return img + cv2.GaussianBlur(lay, (0, 0), 1.6)

SPL = np.random.default_rng(13).random((90, 4))
def splash(img, t, x, y, k=1.0, spread=2.4, size=1.0):
    """a wall of white water thrown up and falling back"""
    def f(c):
        for a_, v, s, ph in SPL:
            age = clamp(t * (.8 + .5 * ph) + .05 * ph)
            ang = -math.pi / 2 + (a_ - .5) * spread; sp = (1100 + 1700 * v) * size
            px = W * x + math.cos(ang) * sp * age * .55; py = H * y + math.sin(ang) * sp * age * .7 + 1700 * age * age
            al = (1 - age) * k
            c.drawOval(skia.Rect.MakeXYWH(px, py, (16 + 30 * s) * size, (24 + 44 * s) * size), E.P(E.C(215, 235, 248, 235 * al), blur=2))
        E.glow(c, W * x, H * y, 260 * size, (210, 235, 255), .55 * k * (1 - clamp(t * 1.5)))
    return sk(img, f)

BUB = np.random.default_rng(3).random((70, 4))
def bubbles(img, T, cx=.5, spread=.35, k=1.0, top=.0):
    def f(c):
        for x, y, s, ph in BUB:
            px = W * (cx + (x - .5) * spread * 2) + 18 * math.sin(T * 3 + ph * 9); py = H - ((y * H + T * (260 + 300 * s)) % (H * (1 - top)))
            r = 4 + 14 * s * s
            c.drawCircle(px, py, r, E.P(E.C(210, 240, 250, 170 * k), 'stroke', 2.5)); c.drawCircle(px - r * .35, py - r * .35, r * .25, E.P(E.C(255, 255, 255, 200 * k)))
    return sk(img, f)

def ripples(img, T, x, y, k=1.0, n=4):
    def f(c):
        for j in range(n):
            a = ((T * .5 + j / n) % 1); r = 60 + 420 * a
            c.drawOval(skia.Rect.MakeLTRB(W * x - r, H * y - r * .22, W * x + r, H * y + r * .22), E.P(E.C(200, 230, 245, 150 * (1 - a) * k), 'stroke', 4))
    return sk(img, f)

def beams(img, T, pts, k=1.0):
    """headlight beams fanning into murky water from points [(x, y, angle_deg)]"""
    def f(c):
        for (x, y, ang) in pts:
            a = math.radians(ang); L = H * .9
            for j in range(3):
                spr = .18 + .08 * j; pth = skia.Path(); pth.moveTo(W * x, H * y)
                pth.lineTo(W * x + math.cos(a - spr) * L, H * y + math.sin(a - spr) * L); pth.lineTo(W * x + math.cos(a + spr) * L, H * y + math.sin(a + spr) * L); pth.close()
                c.drawPath(pth, E.P(E.C(255, 235, 190, (40 - 10 * j) * k * (.85 + .15 * math.sin(T * 7 + j))), blur=30, add=True))
            E.glow(c, W * x, H * y, 90, (255, 240, 200), .9 * k)
    return sk(img, f)

def water_rise(img, level, T, k=1.0):
    """murky water filling the frame from the bottom up to `level` (fraction of H from the top), wavy surface"""
    def f(c):
        pth = skia.Path(); pth.moveTo(0, H)
        for xp in range(0, W + 40, 40): pth.lineTo(xp, H * level + 14 * math.sin(xp * .012 + T * 4) + 8 * math.sin(xp * .03 - T * 6))
        pth.lineTo(W, H); pth.close()
        c.drawPath(pth, E.P(shader=E.linear((0, H * level), (0, H), [E.C(30, 85, 95, 185 * k), E.C(5, 25, 32, 235 * k)])))
        c.drawPath(pth, E.P(E.C(210, 240, 250, 200 * k), 'stroke', 5))
    return sk(img, f)

def timer(img, secs, a=1.0):
    """countdown chip, top right: the ~1 minute the car floats (story clock, not a measured time)"""
    s = max(0, int(math.ceil(secs)))
    def f(c):
        x, y = W * .83, H * .065; col = RED if s <= 15 else YEL
        c.drawRoundRect(skia.Rect.MakeXYWH(x - 120, y - 58, 240, 104), 30, 30, E.P(E.C(8, 16, 22, 215 * a)))
        c.drawRoundRect(skia.Rect.MakeXYWH(x - 120, y - 58, 240, 104), 30, 30, E.P(E.C(*col, 255 * a), 'stroke', 5))
        text(c, f'0:{s:02d}', x, y + 26, 72, col, a)
    return sk(img, f)
T_START = sum(CFG['durs'][:2]); T_END = sum(CFG['durs'][:17])
def clock(img, T):
    if not (2 <= idx <= 16): return img
    return timer(img, 60 - (T - T_START) * 55 / (T_END - T_START))

# ---------------------------------------------------------------- 2D diagrams
def dark(fn):
    return sk(np.zeros((H, W, 3), np.float32), fn)

def door_pressure(T, u):
    """cross-section of a car door, water outside pushing in with many arrows; air inside (simplified)"""
    def f(c):
        c.clear(E.C(8, 14, 20))
        wl = H * .34
        c.drawRect(skia.Rect.MakeLTRB(0, wl, W * .55, H), E.P(shader=E.linear((0, wl), (0, H), [E.C(25, 80, 95), E.C(4, 18, 26)])))
        for xp in range(0, int(W * .55), 30): c.drawCircle(xp, wl + 6 * math.sin(xp * .03 + T * 5), 3, E.P(E.C(220, 245, 255, 160)))
        dx = W * .56; c.drawRoundRect(skia.Rect.MakeXYWH(dx, H * .2, 60, H * .6), 20, 20, E.P(E.C(150, 25, 20)))
        c.drawRoundRect(skia.Rect.MakeXYWH(dx, H * .2, 60, H * .6), 20, 20, E.P(E.C(255, 140, 120), 'stroke', 4))
        c.drawRect(skia.Rect.MakeLTRB(dx + 60, H * .2, W, H * .8), E.P(E.C(30, 34, 40)))
        text(c, 'WATER', W * .27, wl + 120, 60, BLUE, clamp(u * 3)); text(c, 'INSIDE: AIR', W * .8, H * .5, 46, (200, 205, 215), clamp(u * 3))
        text(c, 'DOOR', dx + 30, H * .18, 40, (255, 170, 150), clamp(u * 3))
        n = 6; g = eout(clamp(u * 1.6))
        for k in range(n):
            y = wl + 70 + k * (H * .8 - wl - 120) / (n - 1); ln = (90 + 120 * (k / (n - 1))) * g; pul = 10 * math.sin(T * 8 + k)
            E.arrow(c, dx - 30 - ln - pul, y, dx - 12, y, 12 + 6 * k / n, YEL, clamp(u * 3 - .3))
        text(c, 'SIMPLIFIED', W / 2, H * .955, 30, (150, 160, 170), .8)
    return dark(f)

def phases(T, u):
    """floating -> water at the windows: a level car settling, with a 1-minute bar"""
    def f(c):
        c.clear(E.C(8, 14, 20))
        y0 = H * .5; lvl = 40 + 150 * eout(clamp(u))
        c.save(); c.translate(W / 2, y0 - 40)
        c.drawRoundRect(skia.Rect.MakeXYWH(-330, -40, 660, 150), 40, 40, E.P(E.C(150, 25, 20)))
        pth = skia.Path(); pth.moveTo(-230, -40); pth.lineTo(-170, -170); pth.lineTo(150, -170); pth.lineTo(230, -40); pth.close()
        c.drawPath(pth, E.P(E.C(160, 200, 215, 180))); c.drawPath(pth, E.P(E.C(40, 40, 45), 'stroke', 10))
        c.drawLine(-10, -170, -10, -40, E.P(E.C(40, 40, 45), 'stroke', 12))
        for xw in (-210, 210): c.drawCircle(xw, 110, 62, E.P(E.C(20, 20, 22)))
        c.restore()
        wy = y0 + 150 - lvl
        c.drawRect(skia.Rect.MakeLTRB(0, wy, W, H), E.P(shader=E.linear((0, wy), (0, H), [E.C(30, 90, 105, 215), E.C(5, 22, 30, 245)])))
        c.drawLine(0, wy, W, wy, E.P(E.C(210, 240, 250), 'stroke', 5))
        bx, bw = W * .12, W * .76; by = H * .72
        c.drawRoundRect(skia.Rect.MakeXYWH(bx, by, bw, 50), 25, 25, E.P(E.C(255, 255, 255, 60)))
        c.drawRoundRect(skia.Rect.MakeXYWH(bx, by, bw * eout(clamp(u)), 50), 25, 25, E.P(E.C(*YEL)))
        text(c, 'FLOATING: ABOUT 1 MINUTE', W / 2, by - 30, 50, YEL, clamp(u * 3))
        text(c, 'WATER REACHES THE WINDOWS', W / 2, by + 130, 44, WHITE, clamp(u * 2 - 1))
        text(c, 'TYPICAL TIME · NOT TO SCALE', W / 2, H * .955, 30, (150, 160, 170), .8)
    return dark(f)

def swo(T, act, base='int_wide', u=0.0):
    """the 3 steps as cards: Seatbelts, Windows, Out; `act` lights them"""
    img = blur(kb(base, u, 1.1, 1.16), 10) * .32
    items = [('1', 'SEATBELTS', 'OFF'), ('2', 'WINDOWS', 'OPEN OR BREAK'), ('3', 'OUT', 'RIGHT AWAY')]
    cols = [BLUE, YEL, GREEN]
    def f(c):
        for k, (n, big, sub) in enumerate(items):
            on = clamp(act - k); a = .25 + .75 * on; y = H * (.2 + k * .14) + 40 * (1 - eout(on))
            x0 = W * .1; c.drawRoundRect(skia.Rect.MakeXYWH(x0, y, W * .8, 220), 30, 30, E.P(E.C(10, 22, 30, 225)))
            c.drawRoundRect(skia.Rect.MakeXYWH(x0, y, W * .8, 220), 30, 30, E.P(E.C(*cols[k], 255 * a), 'stroke', 6))
            c.drawCircle(x0 + 115, y + 110, 72, E.P(E.C(*cols[k], 255 * a))); text(c, n, x0 + 115, y + 140, 90, (10, 20, 28), a)
            text(c, big, x0 + 500, y + 105, 78, WHITE, a); text(c, sub, x0 + 500, y + 170, 44, cols[k], a)
    return sk(img, f)

def glass_compare(T, u, base='window_cu'):
    """laminated windshield (glass + plastic layer: cracks but holds) vs tempered side window (shatters into small pieces)"""
    img = blur(kb(base, u, 1.1, 1.15), 12) * .3
    def f(c):
        for k, (x, title, sub, col) in enumerate(((W * .27, 'WINDSHIELD', 'LAMINATED', RED), (W * .73, 'SIDE WINDOW', 'USUALLY TEMPERED', GREEN))):
            a = clamp(u * 3 - k * .9)
            if a <= 0: continue
            y = H * .26; w, h = 380, 520
            c.drawRoundRect(skia.Rect.MakeXYWH(x - w / 2, y, w, h), 24, 24, E.P(E.C(160, 205, 220, 120 * a)))
            c.drawRoundRect(skia.Rect.MakeXYWH(x - w / 2, y, w, h), 24, 24, E.P(E.C(230, 245, 255, 220 * a), 'stroke', 6))
            if k == 0:   # layered edge + spiderweb cracks that stay in place
                c.drawRect(skia.Rect.MakeXYWH(x - w / 2 - 50, y, 14, h), E.P(E.C(200, 230, 240, 255 * a))); c.drawRect(skia.Rect.MakeXYWH(x - w / 2 - 36, y, 10, h), E.P(E.C(255, 200, 90, 255 * a)))
                c.drawRect(skia.Rect.MakeXYWH(x - w / 2 - 26, y, 14, h), E.P(E.C(200, 230, 240, 255 * a)))
                cx, cy = x, y + h * .45
                for j in range(10):
                    an = j / 10 * 2 * math.pi; c.drawLine(cx, cy, cx + math.cos(an) * 170, cy + math.sin(an) * 170, E.P(E.C(255, 255, 255, 230 * a), 'stroke', 3))
                for r in (50, 100, 150): c.drawCircle(cx, cy, r, E.P(E.C(255, 255, 255, 140 * a), 'stroke', 2))
                text(c, 'NOT THIS', x, y + h + 120, 70, RED, a)
            else:        # breaks apart into small cubes
                g = clamp(u * 3 - 1.4)
                r = np.random.default_rng(2)
                for j in range(60):
                    px = x - w / 2 + 25 + (j % 6) * 60 + r.uniform(-6, 6); py = y + 25 + (j // 6) * 50
                    py += 500 * g * g * r.uniform(.6, 1.2); px += 120 * g * r.uniform(-1, 1)
                    c.drawRect(skia.Rect.MakeXYWH(px, py, 34, 30), E.P(E.C(200, 235, 248, 230 * a * (1 - .6 * g)), 'stroke', 3))
                text(c, 'BREAK THIS', x, y + h + 120, 70, GREEN, a)
            text(c, title, x, y - 80, 52, WHITE, a); text(c, sub, x, y - 25, 44, col, a)
    return sk(img, f)

def target(img, T, x, y, a=1.0):
    def f(c):
        r = 70 + 8 * math.sin(T * 9)
        c.drawCircle(W * x, H * y, r, E.P(E.C(*YEL, 255 * a), 'stroke', 7)); c.drawCircle(W * x, H * y, 12, E.P(E.C(*YEL, 255 * a)))
        for an in range(4):
            q = an * math.pi / 2; c.drawLine(W * x + math.cos(q) * (r - 20), H * y + math.sin(q) * (r - 20), W * x + math.cos(q) * (r + 30), H * y + math.sin(q) * (r + 30), E.P(E.C(*YEL, 255 * a), 'stroke', 7))
    return sk(img, f)

SH = np.random.default_rng(21).random((80, 4))
def shatter(img, t, x, y, k=1.0):
    """tempered glass bursting into small cube-like pieces"""
    def f(c):
        for a_, v, s, ph in SH:
            age = clamp(t * (1.1 + .6 * ph)); ang = a_ * 2 * math.pi; sp = 500 + 900 * v
            px = W * x + math.cos(ang) * sp * age; py = H * y + math.sin(ang) * sp * age * .8 + 900 * age * age
            sz = 10 + 18 * s; al = (1 - age) * k
            c.save(); c.translate(px, py); c.rotate(age * 400 * (ph - .5))
            c.drawRect(skia.Rect.MakeXYWH(-sz / 2, -sz / 2, sz, sz), E.P(E.C(215, 240, 250, 240 * al))); c.restore()
        E.glow(c, W * x, H * y, 220, (220, 240, 255), .8 * k * (1 - clamp(t * 3)))
    return sk(img, f)

CR = np.random.default_rng(11); CRACKS = []
for j in range(10):
    a = j / 10 * 2 * math.pi + CR.uniform(-.25, .25); pts = [(0.0, 0.0)]; r = 0.0
    for s in range(6): r += CR.uniform(40, 90); a += CR.uniform(-.35, .35); pts.append((math.cos(a) * r, math.sin(a) * r))
    CRACKS.append(pts)
def cracks(img, u, x, y, k=1.0):
    def f(c):
        for pts in CRACKS:
            n = 1 + int(u * (len(pts) - 1)); pth = skia.Path(); pth.moveTo(W * x, H * y)
            for px, py in pts[1:n + 1]: pth.lineTo(W * x + px, H * y + py)
            c.drawPath(pth, E.P(E.C(140, 210, 255, 140 * k), 'stroke', 9, blur=6, add=True)); c.drawPath(pth, E.P(E.C(240, 250, 255, 255 * k), 'stroke', 3))
    return sk(img, f)

def hammer(img, u, x, y, k=1.0):
    """red window hammer swinging into the glass at (x, y); u 0..1 = the swing"""
    def f(c):
        an = -55 + 55 * eout(u); c.save(); c.translate(W * x + 260, H * y + 360); c.rotate(an)
        c.drawRoundRect(skia.Rect.MakeXYWH(-26, -380, 52, 300), 20, 20, E.P(E.C(210, 30, 25, 255 * k)))
        c.drawRoundRect(skia.Rect.MakeXYWH(-90, -440, 180, 70), 16, 16, E.P(E.C(190, 195, 200, 255 * k)))
        pth = skia.Path(); pth.moveTo(-90, -440); pth.lineTo(-150, -405); pth.lineTo(-90, -370); pth.close(); c.drawPath(pth, E.P(E.C(220, 225, 230, 255 * k)))
        c.restore()
    return sk(img, f)

def tilt_diagram(T, u):
    """side view: the car tipping nose-down (engine end heavier), the last air trapped at the back"""
    def f(c):
        c.clear(E.C(6, 18, 26))
        c.drawRect(skia.Rect.MakeLTRB(0, H * .3, W, H), E.P(shader=E.linear((0, H * .3), (0, H), [E.C(25, 80, 95), E.C(3, 14, 20)])))
        c.drawLine(0, H * .3, W, H * .3, E.P(E.C(210, 240, 250), 'stroke', 5))
        ang = -32 * eout(clamp(u * 1.4)); c.save(); c.translate(W * .5, H * .46); c.rotate(-ang)
        c.drawRoundRect(skia.Rect.MakeXYWH(-360, -40, 720, 150), 40, 40, E.P(E.C(150, 25, 20)))
        pth = skia.Path(); pth.moveTo(-250, -40); pth.lineTo(-190, -170); pth.lineTo(130, -170); pth.lineTo(220, -40); pth.close()
        c.drawPath(pth, E.P(E.C(40, 100, 115)))
        # trapped air: the highest corner of the cabin (the back, here on the left)
        air = skia.Path(); air.moveTo(-250, -40); air.lineTo(-190, -170); air.lineTo(-40, -170); air.lineTo(-120, -40); air.close()
        c.drawPath(air, E.P(E.C(235, 245, 250, 230 * clamp(u * 3 - 1))))
        c.drawPath(pth, E.P(E.C(40, 40, 45), 'stroke', 10))
        c.drawRoundRect(skia.Rect.MakeXYWH(150, -20, 170, 100), 20, 20, E.P(E.C(70, 72, 80)))   # engine block at the front (right)
        text(c, 'ENGINE', 235, 50, 34, WHITE)
        for xw in (-240, 240): c.drawCircle(xw, 110, 62, E.P(E.C(20, 20, 22)))
        c.restore()
        E.arrow(c, W * .78, H * .5, W * .8, H * .64, 16, YEL, clamp(u * 3)); text(c, 'NOSE DOWN', W * .78, H * .7, 56, YEL, clamp(u * 3))
        text(c, 'LAST AIR', W * .27, H * .2, 60, WHITE, clamp(u * 3 - 1)); E.arrow(c, W * .27, H * .22, W * .4, H * .34, 12, WHITE, clamp(u * 3 - 1))
        text(c, 'SIMPLIFIED', W / 2, H * .955, 30, (150, 160, 170), .8)
    return bubbles(dark(f), T, .5, .3, .5)

def stats(T, u):
    """about 400 deaths a year in North America; up to 1 in 10 drownings (10 figures, 1 lit)"""
    img = blur(kb('under', u, 1.1, 1.18), 10) * .35
    def f(c):
        n = int(400 * eout(clamp(u * 1.6))); text(c, f'~{n}', W / 2, H * .35, 230, YEL)
        text(c, 'DEATHS A YEAR', W / 2, H * .41, 64, WHITE); text(c, 'IN SINKING CARS · NORTH AMERICA', W / 2, H * .455, 42, BLUE)
        a = clamp(u * 3 - 1.2)
        for k in range(10):
            x = W * (.14 + k * .08); y = H * .56; col = RED if k == 0 else (150, 160, 170)
            c.drawCircle(x, y, 26, E.P(E.C(*col, 255 * a))); c.drawRoundRect(skia.Rect.MakeXYWH(x - 26, y + 34, 52, 90), 22, 22, E.P(E.C(*col, 255 * a)))
        text(c, 'UP TO 1 IN 10 DROWNINGS', W / 2, H * .7, 56, RED, a)
    return sk(img, f)

def kids(T, u):
    """children out first, oldest to youngest: 3 figures by size, numbered, moving toward an open window"""
    img = blur(kb('int_wide', u, 1.1, 1.15), 12) * .3
    def f(c):
        wx, wy = W * .8, H * .36
        c.drawRoundRect(skia.Rect.MakeXYWH(wx - 120, wy - 150, 240, 300), 30, 30, E.P(E.C(160, 205, 220, 90)))
        c.drawRoundRect(skia.Rect.MakeXYWH(wx - 120, wy - 150, 240, 300), 30, 30, E.P(E.C(230, 245, 255), 'stroke', 6))
        text(c, 'OPEN WINDOW', wx, wy - 180, 40, WHITE)
        for k, s in enumerate((1.0, .8, .62)):
            a = clamp(u * 3 - k * .5); x = W * (.2 + k * .17) + 60 * eout(clamp(u * 2 - k * .3)); y = H * .52
            c.drawCircle(x, y - 150 * s, 48 * s, E.P(E.C(255, 222, 180, 255 * a))); c.drawRoundRect(skia.Rect.MakeXYWH(x - 45 * s, y - 95 * s, 90 * s, 170 * s), 30 * s, 30 * s, E.P(E.C(*[BLUE, YEL, GREEN][k], 255 * a)))
            c.drawCircle(x, y + 150, 46, E.P(E.C(*YEL, 255 * a))); text(c, str(k + 1), x, y + 170, 60, (10, 20, 28), a)
        E.arrow(c, W * .2, H * .68, W * .7, H * .68, 14, WHITE, clamp(u * 3 - 1)); text(c, 'OLDEST  →  YOUNGEST', W * .45, H * .74, 52, WHITE, clamp(u * 3 - 1))
    return sk(img, f)

def bigx(img, a=1.0):
    def f(c):
        for s in (1, -1): c.drawLine(W * .2, H * (.3 if s > 0 else .62), W * .8, H * (.62 if s > 0 else .3), E.P(E.C(*RED, 235 * a), 'stroke', 40))
    return sk(img, f)

# ---------------------------------------------------------------- scenes
def S0(t, T):   # HOOK: the nose plunging in, splash, headlights under the surface
    img = kb('splash', t / 1.9, 1.35, 1.18, (.47, .5), (.47, .5))
    img = (img - 100) * 1.15 + 100
    img = beams(img, T, [(.36, .56, 120), (.5, .58, 110)], .8)
    img = splash(img, t + .15, .3, .6, 1.0, size=1.4)
    return snow(shake(flash(img, t + .3, 80, 6), t, 20, 2.5), T, .6)

def S1(t, T):
    c = wt('slid') - .1
    if t < c:   # sliding across black ice
        u = t / c; img = kb('road', u, 1.15, 1.3, (.42, .55), (.6, .55), rot=-4 * ease(u))
        return snow(whip(img, .06), T, .9)
    u = t - c
    img = bob(kb('float_side', u / 2.4, 1.3, 1.1, (.5, .52), (.5, .5)), T, 5)
    return whip(snow(splash(img, u * .8 + .3, .5, .55, .6), T, .7), u)

def S2(t, T): return clock(shake(ptalk('cu_leo_door', t, t / (D + PAD), 1.02, 1.12, (.55, .45), (.55, .42), .01), t * .3, 9, .8), T)

def S3(t, T):
    c = wt('hundreds') - .2
    if t < c: return clock(bob(kb('float_side', t / c, 1.2, 1.32, (.5, .55), (.5, .56)), T, 4), T)
    return clock(whip(door_pressure(T, clamp((t - c) / 1.5)), t - c), T)

def S4(t, T):
    img = ptalk('cu_leo_door', t, t / (D + PAD), 1.15, 1.25, (.55, .42), (.55, .4), .01)
    def f(c):   # Leo's phone glowing in the cabin
        x, y = W * .7, H * .62; c.drawRoundRect(skia.Rect.MakeXYWH(x - 70, y - 130, 140, 260), 24, 24, E.P(E.C(20, 20, 25)))
        c.drawRoundRect(skia.Rect.MakeXYWH(x - 60, y - 118, 120, 236), 18, 18, E.P(E.C(120, 200, 255))); text(c, '911', x, y + 20, 56, (10, 30, 50))
        E.glow(c, x, y, 220, (120, 200, 255), .5)
    return clock(sk(img, f), T)

def S5(t, T):
    c = wt('We') - .1
    img = ptalk('cu_mia', t, t / (D + PAD), 1.05, 1.15, (.5, .45), (.5, .42), .01)
    return clock(shake(img, t, 6, 2), T)

def S6(t, T):
    c = 1.2
    if t < c: return clock(bob(kb('float_side', t / c, 1.0, 1.08, (.5, .52), (.48, .52)), T, 5), T)
    return clock(whip(phases(T, clamp((t - c) / 2.4)), t - c), T)

def S7(t, T):
    a1, a2, a3 = wt('Seatbelts'), wt('Windows'), wt('Out')
    act = 0 if t < a1 else (1 + 2 * clamp((t - a1) / .3) * 0 if t < a2 else (2 if t < a3 else 3))
    act = 0 if t < a1 else (clamp((t - a1) / .35) if t < a2 else (1 + clamp((t - a2) / .35) if t < a3 else 2 + clamp((t - a3) / .35)))
    return clock(swo(T, act, 'int_wide', t / (D + PAD)), T)

def S8(t, T):
    c = wt('Now') - .1
    if t < c: return clock(shake(ptalk('cu_mia', t, t / c, 1.15, 1.22, (.5, .44), (.5, .42), .01), t, 5, 2), T)
    u = t - c
    img = kb('int_wide', u / 1.5, 1.05, 1.12, (.5, .55), (.5, .55))
    def f(cn):   # belt buckles popping
        for x in (.28, .72):
            a = clamp(1 - u * 1.5); cn.drawCircle(W * x, H * .7, 40 + 80 * u, E.P(E.C(*BLUE, 200 * a), 'stroke', 6))
            text(cn, 'CLICK', W * x, H * .66, 48, BLUE, a)
    return clock(whip(sk(img, f), u), T)

def S9(t, T):
    c1 = wt('Power') - .1; c2 = wt('thirty') - .1
    if t < c1: return clock(kb('cu_kai', t / c1, 1.05, 1.15, (.45, .45), (.42, .45)), T)
    if t < c2: return clock(whip(kb('window_wet', (t - c1) / 1.5, 1.0, 1.08, (.5, .5), (.55, .45)), t - c1), T)
    u = t - c2
    return clock(whip(kb('window_wet', u / 2.5, 1.12, 1.25, (.55, .42), (.6, .4)), u), T)

def S10(t, T):
    img = shake(kb('cu_kai', t / (D + PAD), 1.2, 1.3, (.42, .44), (.42, .42)), t, 12, 2)
    return clock(grade(img, (1, 1, 1.2)) + 25 * math.exp(-t * 4) * np.float32([0, 0, 1]), T)

def S11(t, T):
    c = wt('side') - .1
    if t < c: return clock(kb('window_wet', t / c, 1.15, 1.05, (.5, .45), (.55, .45)), T)
    u = t - c
    img = kb('window_wet', u / 2, 1.1, 1.3, (.78, .43), (.78, .43))
    return clock(whip(target(img, T, .5, .5, clamp(u * 3)), u), T)

def S12(t, T):
    return clock(glass_compare(T, clamp(t / 2.6)), T)

def S13(t, T):
    c = wt('window') - .1
    if t < c: return clock(ptalk('cu_mia', t, t / c, 1.2, 1.28, (.5, .43), (.5, .42), .012), T)
    u = t - c
    return clock(whip(kb('window_wet', u, 1.05, 1.15, (.45, .5), (.7, .45)), u), T)

def S14(t, T):
    c = .45
    img = kb('window_wet', t / (D + PAD), 1.15, 1.2, (.7, .45), (.7, .45))
    if t < c: return clock(hammer(img, t / c, .59, .48), T)
    u = t - c
    img = cracks(img, clamp(u * 5), .59, .48, 1.0 - clamp((u - .4) * 3))
    img = shatter(img, max(0, u - .25), .59, .48, 1.0)
    img = water_rise(img, .62 + .3 * (1 - eout(clamp((u - .3) / 2))), T, clamp((u - .3) * 2) * .7)
    return clock(shake(flash(img, u, 120, 8), u, 14, 4), T)

def S15(t, T):
    c1 = wt('nose') - .1; c2 = wt('last') - .2
    if t < c1: return clock(bob(kb('nose_down', t / c1, 1.0, 1.08, (.5, .5), (.5, .52)), T, 4), T)
    if t < c2:
        img = kb('under', (t - c1) / 2, 1.0, 1.1, (.5, .5), (.52, .55)); img = beams(img, T, [(.53, .63, 100)], .6)
        return clock(whip(bubbles(img, T, .45, .2, .8), t - c1, vertical=True), T)
    return clock(whip(tilt_diagram(T, clamp((t - c2) / 1.6)), t - c2), T)

def S16(t, T):
    c1 = wt('onto') - .1; c2 = wt('swim') - .1
    if t < c1:
        img = shake(kb('float_side', t / c1, 1.25, 1.35, (.45, .5), (.42, .48)), t, 6, 2)
        return clock(splash(img, t * .7 + .2, .42, .5, .5, size=.6), T)
    if t < c2: return clock(whip(bob(kb('roof', (t - c1) / 1.5, 1.05, 1.15, (.5, .45), (.5, .43)), T, 6), t - c1), T)
    u = t - c2
    img = kb('shore', u / 2, 1.2, 1.08, (.5, .5), (.5, .5))
    return whip(snow(img, T, .8), u)

def S17(t, T): return snow(ptalk('shore', t, t / (D + PAD), 1.45, 1.55, (.36, .46), (.36, .45), .01), T, .7)
def S18(t, T): return snow(ptalk('shore', t, t / (D + PAD), 1.45, 1.55, (.52, .46), (.52, .45), .01), T, .7)

def S19(t, T): return whip(stats(T, clamp(t / 3.2)), t)

def S20(t, T):
    c = wt('wait') - .1
    img = kb('int_water', t / (D + PAD), 1.0, 1.12, (.5, .52), (.5, .5))
    img = water_rise(img, .7 - .25 * clamp((t - c) / 3), T, .55)
    return bubbles(img, T, .5, .4, .5 * clamp(t - c))

def S21(t, T):
    c = wt('By') - .1
    if t < c:
        img = grade(kb('int_water', t / c, 1.12, 1.18, (.5, .5), (.5, .48)), (.8, .85, .9))
        img = water_rise(img, .45, T, .6)
        return bigx(img, eout(clamp((t - .3) / .4)))
    u = t - c
    img = kb('under', u / 2.5, 1.1, 1.25, (.5, .5), (.5, .45)); img = beams(img, T, [(.53, .63, 100)], .4)
    return whip(bubbles(img, T, .5, .15, .9), u, vertical=True)

def S22(t, T):
    c = wt('Unbuckle') - .2
    if t < c: return ptalk('cu_mia', t, t / c, 1.05, 1.1, (.5, .45), (.5, .44))
    return whip(kids(T, clamp((t - c) / 2.8)), t - c)

def S23(t, T):
    c = (D + PAD) - .9
    if t < c: return snow(ptalk('shore', t, t / c, 1.4, 1.5, (.68, .46), (.68, .45), .01), T, .7)
    u = t - c   # loop: back to the first frame (the plunge)
    img = (kb('splash', 0, 1.35, 1.35, (.47, .5), (.47, .5)) - 100) * 1.15 + 100
    img = beams(img, T, [(.36, .56, 120), (.5, .58, 110)], .8)
    return whip(splash(img, .15, .3, .6, 1.0, size=1.4), u, vertical=True)

# ---------------------------------------------------------------- overlays
def overlays():
    o = []
    if idx == 0: o += [{'type': 'hook', 'text': 'ABOUT 1 MINUTE|TO GET OUT', 'y': .11}]
    if idx == 1: o += [{'type': 'datestamp', 'text': 'DECEMBER · BLACK ICE', 'y': .08, 'from': .1}]
    if idx == 2: o += [{'type': 'label', 'text': "DOOR WON'T OPEN", 'pos': [.42, .12], 'color': RED, 'from': .3}]
    if idx == 3: o += [{'type': 'badge', 'value': '100s', 'unit': 'POUNDS OF FORCE', 'pos': [.42, .14], 'from': wt('hundreds') - .1},
                       {'type': 'label', 'text': '≈ A GROWN MAN LEANING ON IT, OR MORE', 'pos': [.5, .225], 'color': WHITE, 'from': wt('force') - .1}]
    if idx == 5: o += [{'type': 'label', 'text': "DON'T CALL UNTIL YOU'RE OUT", 'pos': [.42, .12], 'color': YEL, 'from': .3}]
    if idx == 7: o += [{'type': 'label', 'text': 'WHAT RESCUE EXPERTS TEACH', 'pos': [.42, .13], 'color': YEL, 'from': .2}]
    if idx == 9: o += [{'type': 'badge', 'value': '30–60 S', 'unit': 'POWER WINDOWS USUALLY WORK', 'pos': [.42, .14], 'from': wt('thirty') - .1, 'size': 70}]
    if idx == 11: o += [{'type': 'label', 'text': 'HIT NEAR A CORNER', 'pos': [.42, .12], 'color': YEL, 'from': wt('corner') - .1}]
    if idx == 15: o += [{'type': 'label', 'text': 'ENGINE END SINKS FIRST', 'pos': [.42, .12], 'color': YEL, 'from': wt('nose') - .1}]
    if idx == 16: o += [{'type': 'label', 'text': 'OUT THE WINDOW → ROOF → SHORE', 'pos': [.45, .135], 'color': GREEN, 'from': .2}]
    if idx == 20: o += [{'type': 'label', 'text': 'OLD ADVICE: WAIT FOR IT TO FILL', 'pos': [.5, .12], 'color': WHITE, 'from': .3}]
    if idx == 21: o += [{'type': 'label', 'text': 'WRONG', 'pos': [.5, .12], 'color': RED, 'from': .2},
                        {'type': 'label', 'text': 'ALMOST NO AIR LEFT', 'pos': [.5, .18], 'color': WHITE, 'from': wt('almost') - .1}]
    if idx == 22: o += [{'type': 'label', 'text': 'KIDS OUT FIRST', 'pos': [.5, .12], 'color': YEL, 'from': wt('first') - .1}]
    if idx == 23: o += [{'type': 'cta', 'text': 'FOLLOW FOR MORE STORIES', 'from': .2}]
    return o

FN = globals()[f'S{idx}']
os.makedirs(f'{ROOT}/s{idx}', exist_ok=True)
if len(sys.argv) > 2:
    for ts in sys.argv[2:]:
        t = float(ts); img = FN(t, t + T0); cv2.imwrite(f'{ROOT}/still_{idx}_{ts}.jpg', np.clip(img, 0, 255).astype(np.uint8)[::2, ::2], [cv2.IMWRITE_JPEG_QUALITY, 85])
    sys.exit()
for f in (range(1, NF + 1) if not os.environ.get('META_ONLY') else []):
    t = (f - 1) / FPS; img = FN(t, t + T0)
    cv2.imwrite(f'{ROOT}/s{idx}/f_{f:04d}.png', np.clip(img, 0, 255).astype(np.uint8), [cv2.IMWRITE_PNG_COMPRESSION, 1])
json.dump({'frames': NF, 'overlays': overlays()}, open(f'{ROOT}/s{idx}/meta.json', 'w'))
print('scene', idx, 'frames', NF)
