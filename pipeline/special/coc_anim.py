"""Animate every scene of "The snow buried their tailpipe" over its Cycles plates (2D camera moves, cuts, snowfall, exhaust, diagrams).
python3 coc_anim.py <scene> [still_times...]  ->  coc/s<scene>/f_####.png + meta.json (overlays read by compose.py)"""
import sys, math, json, os
sys.path.insert(0, '/home/claude/pro')
import numpy as np, cv2, skia
import engine as E
ROOT = '/home/claude/b3d/coc'; CFG = json.load(open(f'{ROOT}/topic.json'))
FPS = 24; PAD = .75; XF = .35
idx = int(sys.argv[1]); D = CFG['durs'][idx]; NF = int(math.ceil((D + PAD) * FPS))
T0 = sum(CFG['durs'][:idx])
W, H = 1080, 1920
ease = lambda t: .5 - .5 * math.cos(math.pi * min(max(t, 0), 1))
eout = lambda t: 1 - (1 - min(max(t, 0), 1)) ** 3
clamp = lambda v, a=0., b=1.: max(a, min(b, v))
YEL, WHITE, BLUE, RED, GREEN, GREY = (255, 222, 40), (255, 255, 255), (130, 200, 255), (255, 95, 80), (120, 235, 150), (170, 178, 190)

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
LIFT = {'jam': 1.45, 'wide': 1.25, 'side': 1.6, 'rear': 1.1, 'dig': 1.1}
def plate(name):
    """load a plate, upscale, grade into the palette: deep navy shadows, warm highlights"""
    if name not in PL:
        im = cv2.imread(f'{ROOT}/plates/{name}.png', cv2.IMREAD_COLOR)
        if im.shape[1] != W: im = cv2.resize(im, (W, H), interpolation=cv2.INTER_CUBIC)
        im = im.astype(np.float32) * LIFT.get(name, 1.0); lum = im.mean(2, keepdims=True) / 255
        im = im * .92 + (1 - lum) * np.float32([22, 8, 0]) - 2
        im = im * (.92 + .1 * lum) * VIGM
        im = cv2.addWeighted(im, 1.25, cv2.GaussianBlur(im, (0, 0), 2.2), -.25, 0)
        PL[name] = np.clip(im, 0, 255)
    return PL[name]

def kb(name, u, z0, z1, c0=(.5, .5), c1=(.5, .5), rot=0.0, im=None):
    im = plate(name) if im is None else im; t = ease(u); z = z0 + (z1 - z0) * t
    cx = (c0[0] + (c1[0] - c0[0]) * t) * W; cy = (c0[1] + (c1[1] - c0[1]) * t) * H
    M = cv2.getRotationMatrix2D((cx, cy), rot, z); M[0, 2] += W / 2 - cx; M[1, 2] += H / 2 - cy
    return cv2.warpAffine(im, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

def shift(img, dx, dy): return cv2.warpAffine(img, np.float32([[1, 0, dx], [0, 1, dy]]), (W, H), borderMode=cv2.BORDER_REFLECT)
def shake(img, t, amp=10, decay=3.0):
    a = amp * math.exp(-t * decay)
    if a < .5: return img
    return shift(img, a * math.sin(t * 71), a * math.cos(t * 53))
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
def dark(fn): return sk(np.zeros((H, W, 3), np.float32), fn)

# ---------------------------------------------------------------- effects
rng = np.random.default_rng(5); FL = rng.random((220, 4))
def snow(img, T, k=1.0, vy=110, wind=70):
    """blizzard snowfall, blown sideways"""
    if k <= 0: return img
    lay = np.zeros_like(img)
    for x, y, s, b in FL:
        px = int((x * W + math.sin(T * .8 + y * 11) * 30 + T * wind * (.5 + s)) % W); py = int((y * H + T * vy * (.4 + s)) % H)
        r = 1 + int(s * s * 7); v = (.35 + .65 * b) * k
        cv2.circle(lay, (px, py), r, (235 * v, 240 * v, 245 * v), -1, cv2.LINE_AA)
    return img + cv2.GaussianBlur(lay, (0, 0), 1.4)

SM = np.random.default_rng(8).random((40, 4))
def smoke(img, T, x, y, k=1.0, spread=1.0, col=(150, 150, 155), up=1.0):
    """exhaust puffs rising/drifting from (x, y)"""
    def f(c):
        for a_, v, s, ph in SM:
            age = (T * (.35 + .25 * v) + ph) % 1
            px = W * x + (a_ - .5) * 160 * spread * age + 120 * age * spread; py = H * y - 420 * age * up
            r = (30 + 140 * age) * (.6 + .6 * s) * spread
            c.drawCircle(px, py, r, E.P(E.C(*col, 70 * (1 - age) * k), blur=22))
    return sk(img, f)

def haze(img, k):
    """grey, invisible-in-reality gas shown as a faint haze (labelled as illustration in scene 5)"""
    if k <= 0: return img
    n = cv2.GaussianBlur(np.random.default_rng(1).random((H // 16, W // 16)).astype(np.float32), (0, 0), 2)
    n = cv2.resize(n, (W, H))[..., None]
    return img * (1 - .35 * k) + (95 + 80 * n) * .35 * k

def darken(img, k): return img * (1 - k)
def blink(img, u):
    """eyelids closing: black bars from top and bottom"""
    def f(c):
        h = H * .5 * eout(u)
        c.drawRect(skia.Rect.MakeLTRB(0, 0, W, h), E.P(E.C(0, 0, 0, 255))); c.drawRect(skia.Rect.MakeLTRB(0, H - h, W, H), E.P(E.C(0, 0, 0, 255)))
    return sk(img, f)

def pulse(img, T, x, y, k=1.0):
    """throbbing headache rings"""
    def f(c):
        for j in range(3):
            a = (T * 1.6 + j / 3) % 1; r = 180 + 260 * a
            c.drawCircle(W * x, H * y, r, E.P(E.C(*RED, 160 * (1 - a) * k), 'stroke', 10))
    return sk(img, f)

def snowpile(img, u, top_y, k=1.0):
    """2D snow drift creeping up the frame bottom to top_y (fraction of H)"""
    def f(c):
        pth = skia.Path(); pth.moveTo(0, H); y0 = H * (1 - (1 - top_y) * eout(u))
        for xp in range(0, W + 60, 60): pth.lineTo(xp, y0 + 40 * math.sin(xp * .008) + 25 * math.sin(xp * .021 + 1))
        pth.lineTo(W, H); pth.close()
        c.drawPath(pth, E.P(shader=E.linear((0, y0), (0, H), [E.C(205, 215, 235, 245 * k), E.C(120, 135, 165, 250 * k)])))
    return sk(img, f)

# ---------------------------------------------------------------- 2D diagrams
def car_side(c, x, y, s=1.0, col=(150, 25, 20)):
    c.save(); c.translate(x, y); c.scale(s, s)
    c.drawRoundRect(skia.Rect.MakeXYWH(-330, -40, 660, 150), 40, 40, E.P(E.C(*col)))
    pth = skia.Path(); pth.moveTo(-230, -40); pth.lineTo(-170, -170); pth.lineTo(150, -170); pth.lineTo(230, -40); pth.close()
    c.drawPath(pth, E.P(E.C(40, 70, 90))); c.drawPath(pth, E.P(E.C(40, 40, 45), 'stroke', 10))
    c.drawLine(-10, -170, -10, -40, E.P(E.C(40, 40, 45), 'stroke', 12))
    for xw in (-210, 210): c.drawCircle(xw, 110, 62, E.P(E.C(20, 20, 22)))
    c.drawRect(skia.Rect.MakeXYWH(-372, 70, 50, 22), E.P(E.C(170, 170, 175)))     # tailpipe at the back (left)
    c.restore()

def exhaust_flow(T, u):
    """side view: tailpipe buried in a drift, exhaust has nowhere to go and seeps up into the cabin (simplified)"""
    def f(c):
        c.clear(E.C(8, 14, 24))
        cx, cy = W * .55, H * .45
        c.drawRect(skia.Rect.MakeLTRB(0, cy + 170, W, H), E.P(shader=E.linear((0, cy + 170), (0, H), [E.C(110, 122, 145), E.C(30, 38, 52)])))
        car_side(c, cx, cy)
        dr = skia.Path(); dr.moveTo(0, cy + 175); dr.cubicTo(W * .05, cy - 20, W * .18, cy - 10, W * .3, cy + 175); dr.close()
        c.drawPath(dr, E.P(E.C(175, 188, 210)))
        text(c, 'SNOW', W * .12, cy + 120, 46, (60, 70, 90), clamp(u * 3))
        g = clamp(u * 1.5 - .3)
        for j in range(14):     # grey gas leaking up and forward into the cabin
            a = ((T * .45 + j / 14) % 1)
            px = cx - 330 + 180 * a + 40 * math.sin(j * 3 + T * 2); py = cy + 80 - 260 * a
            c.drawCircle(px, py, 26 + 40 * a, E.P(E.C(160, 160, 168, 120 * g * (1 - a * .6)), blur=10))
        c.save(); c.clipRect(skia.Rect.MakeLTRB(cx - 230, cy - 170, cx + 230, cy - 40))
        c.drawRect(skia.Rect.MakeLTRB(cx - 230, cy - 40 - 130 * eout(clamp(u * 1.3 - .4)), cx + 230, cy - 40), E.P(E.C(150, 150, 158, 150)))
        c.restore()
        E.arrow(c, cx - 300, cy + 40, cx - 150, cy - 60, 14, YEL, g)
        text(c, 'NOWHERE TO GO', W * .5, H * .25, 64, YEL, clamp(u * 3 - .3))
        text(c, 'EXHAUST BUILDS UP INSIDE', W * .5, H * .31, 52, WHITE, g)
        text(c, 'SIMPLIFIED', W / 2, H * .955, 30, (150, 160, 170), .8)
    return dark(f)

def co_molecule(c, x, y, s=1.0, a=1.0):
    c.drawLine(x - 60 * s, y, x + 60 * s, y, E.P(E.C(220, 220, 220, 255 * a), 'stroke', 14 * s))
    c.drawCircle(x - 70 * s, y, 70 * s, E.P(E.C(55, 58, 64, 255 * a))); text(c, 'C', x - 70 * s, y + 24 * s, int(70 * s), WHITE, a)
    c.drawCircle(x + 80 * s, y, 78 * s, E.P(E.C(220, 50, 45, 255 * a))); text(c, 'O', x + 80 * s, y + 24 * s, int(70 * s), WHITE, a)

def alarm_test(T, u, t):
    """CO alarm prop: digital stopwatch runs to 1:24 and the alarm flashes (Maplewood FD test, 2016)"""
    img = blur(kb('int', u, 1.15, 1.22), 12) * .35
    def f(c):
        x, y = W / 2, H * .36
        c.drawRoundRect(skia.Rect.MakeXYWH(x - 260, y - 260, 520, 520), 90, 90, E.P(E.C(235, 238, 242)))
        c.drawRoundRect(skia.Rect.MakeXYWH(x - 190, y - 150, 380, 150), 20, 20, E.P(E.C(25, 40, 35)))
        secs = min(84, 84 * eout(clamp(u * 1.25))); on = secs >= 83.5
        text(c, f'{int(secs) // 60}:{int(secs) % 60:02d}', x, y - 30, 110, (120, 255, 160) if not on else RED)
        for k in range(3): c.drawCircle(x - 70 + k * 70, y + 120, 18, E.P(E.C(60, 60, 66)))
        col = RED if on and int(T * 6) % 2 == 0 else (90, 30, 30)
        c.drawCircle(x, y + 190, 30, E.P(E.C(*col)))
        if on:
            E.glow(c, x, y + 190, 260, RED, .7 if int(T * 6) % 2 == 0 else .2)
            text(c, 'ALARM: 90 PPM', x, y + 380, 70, RED)
        text(c, 'CO ALARM', x, y - 200, 36, (40, 50, 60))
        text(c, 'FIRE DEPT TEST · CAR STUCK IN SNOW', x, H * .955, 30, (170, 180, 190), .9)
    return sk(img, f)

def symptoms(T, act, u):
    img = blur(kb('cu_leo', u, 1.1, 1.18), 12) * .32
    items = [('HEADACHE', RED), ('DIZZINESS', YEL), ('CONFUSION', BLUE), ('SLEEPINESS', GREY)]
    def f(c):
        for k, (s, col) in enumerate(items):
            on = clamp(act - k); a = .2 + .8 * on; y = H * (.12 + k * .115) + 30 * (1 - eout(on))
            c.drawRoundRect(skia.Rect.MakeXYWH(W * .12, y, W * .76, 170), 30, 30, E.P(E.C(10, 18, 30, 225)))
            c.drawRoundRect(skia.Rect.MakeXYWH(W * .12, y, W * .76, 170), 30, 30, E.P(E.C(*col, 255 * a), 'stroke', 6))
            text(c, s, W / 2, y + 112, 80, WHITE, a)
        text(c, 'OFTEN MISTAKEN FOR THE FLU', W / 2, H * .6, 44, GREY, clamp(act - 3))
    return sk(img, f)

def blood(T, u):
    """a red blood cell's hemoglobin: CO takes the oxygen seats (illustration). CO binds >200x more strongly (ATSDR; UKHSA 245x)"""
    def f(c):
        c.clear(E.C(30, 6, 10))
        x, y = W / 2, H * .4
        c.drawOval(skia.Rect.MakeXYWH(x - 380, y - 230, 760, 460), E.P(E.C(190, 30, 35)))
        c.drawOval(skia.Rect.MakeXYWH(x - 220, y - 120, 440, 240), E.P(E.C(150, 18, 25)))
        seats = [(x - 250, y - 110), (x + 250, y - 110), (x - 250, y + 110), (x + 250, y + 110)]
        for k, (sx, sy) in enumerate(seats):
            c.drawCircle(sx, sy, 62, E.P(E.C(255, 220, 220, 120), 'stroke', 6))
            g = eout(clamp(u * 2.2 - k * .25))
            # CO molecules fly in and lock on; O2 bounced away
            cx_ = sx + (1 - g) * (600 if sx > x else -600); cy_ = sy - (1 - g) * 300
            co_molecule(c, cx_, cy_, .45, clamp(u * 3))
            ox = sx + g * (sx - x) * 1.2; oy = sy + g * 380 * (1 if sy > y else -1)
            c.drawCircle(ox - 30, oy, 34, E.P(E.C(*BLUE, 255 * (1 - g * .7)))); c.drawCircle(ox + 30, oy, 34, E.P(E.C(*BLUE, 255 * (1 - g * .7))))
        text(c, 'O2', W * .1, H * .54, 60, BLUE, clamp(u * 3)); text(c, 'CO', W * .9, H * .54, 60, (230, 230, 235), clamp(u * 3))
        text(c, 'IT TAKES THE SEATS', W / 2, H * .215, 70, YEL, clamp(u * 2 - .6))
        text(c, 'OXYGEN NEEDS', W / 2, H * .26, 70, YEL, clamp(u * 2 - .6))
        text(c, 'HEMOGLOBIN IN A RED BLOOD CELL · ILLUSTRATION', W / 2, H * .955, 30, (200, 170, 170), .9)
    return dark(f)

def body_o2(T, u):
    """breathing normally, but the oxygen gauge drops"""
    img = blur(kb('cu_leo_sleepy', u, 1.05, 1.12), 14) * .3
    def f(c):
        x, y = W / 2, H * .3; br = 1 + .08 * math.sin(T * 3.2)
        for s in (-1, 1):   # lungs
            c.save(); c.translate(x + s * 120, y); c.scale(br, br)
            c.drawOval(skia.Rect.MakeXYWH(-95, -170, 190, 340), E.P(E.C(230, 140, 150, 230))); c.restore()
        c.drawRect(skia.Rect.MakeXYWH(x - 14, y - 260, 28, 120), E.P(E.C(230, 140, 150, 230)))
        text(c, 'BREATHING', x, y - 290, 56, WHITE)
        lvl = 1 - .55 * eout(clamp(u * 1.3)); bx, by, bw = W * .15, H * .5, W * .7
        c.drawRoundRect(skia.Rect.MakeXYWH(bx, by, bw, 56), 28, 28, E.P(E.C(255, 255, 255, 50)))
        col = BLUE if lvl > .7 else (RED if lvl < .55 else YEL)
        c.drawRoundRect(skia.Rect.MakeXYWH(bx, by, bw * lvl, 56), 28, 28, E.P(E.C(*col)))
        text(c, 'OXYGEN REACHING THE BODY', W / 2, by - 30, 46, col)
        text(c, 'ILLUSTRATION', W / 2, H * .955, 30, (150, 160, 170), .8)
    return sk(img, f)

def nws(T, act, u):
    """National Weather Service: stranded in a car"""
    img = blur(kb('side', u, 1.1, 1.18), 12) * .3
    items = [('STAY WITH YOUR CAR', GREEN), ('RUN IT ~10 MIN AN HOUR', YEL)]
    def f(c):
        for k, (s, col) in enumerate(items):
            on = clamp(act - k); a = .2 + .8 * on; y = H * (.13 + k * .13) + 30 * (1 - eout(on))
            c.drawRoundRect(skia.Rect.MakeXYWH(W * .07, y, W * .86, 180), 30, 30, E.P(E.C(10, 18, 30, 225)))
            c.drawRoundRect(skia.Rect.MakeXYWH(W * .07, y, W * .86, 180), 30, 30, E.P(E.C(*col, 255 * a), 'stroke', 6))
            text(c, s, W / 2, y + 115, 66, WHITE, a)
        a = clamp(act - 1)
        if a > 0:   # clock face: 10 minutes of every hour
            x, y, r = W / 2, H * .5, 150
            c.drawCircle(x, y, r, E.P(E.C(20, 30, 45, 230 * a))); c.drawCircle(x, y, r, E.P(E.C(255, 255, 255, 230 * a), 'stroke', 6))
            pth = skia.Path(); pth.moveTo(x, y); pth.arcTo(skia.Rect.MakeLTRB(x - r, y - r, x + r, y + r), -90, 60 * eout(a), False); pth.close()
            c.drawPath(pth, E.P(E.C(*YEL, 230 * a)))
            text(c, '10 MIN', x, y + r + 70, 50, YEL, a)
    return sk(img, f)

def window_vs_pipe(T, u):
    """cracked window alone: not enough (X). clear tailpipe: yes (check)."""
    img = blur(kb('pipe_clear', u, 1.05, 1.12), 10) * .35
    def f(c):
        for k, (x, title, ok) in enumerate(((W * .27, 'WINDOW ONLY', False), (W * .73, 'PIPE CLEAR', True))):
            a = clamp(u * 3 - k * 1.1)
            if a <= 0: continue
            y = H * .3
            c.drawRoundRect(skia.Rect.MakeXYWH(x - 210, y - 170, 420, 340), 30, 30, E.P(E.C(10, 18, 30, 225 * a)))
            if ok:
                c.drawRect(skia.Rect.MakeXYWH(x - 140, y - 20, 200, 40), E.P(E.C(180, 180, 185, 255 * a)))
                for j in range(4):
                    aa = (T * .7 + j / 4) % 1; c.drawCircle(x - 160 - 140 * aa, y + 40 * math.sin(j + T), 22 + 30 * aa, E.P(E.C(160, 160, 168, 140 * (1 - aa) * a), blur=8))
                pth = skia.Path(); pth.moveTo(x - 70, y + 110); pth.lineTo(x - 20, y + 150); pth.lineTo(x + 80, y + 70)
                c.drawPath(pth, E.P(E.C(*GREEN, 255 * a), 'stroke', 18))
            else:
                c.drawRect(skia.Rect.MakeXYWH(x - 120, y - 120, 240, 160), E.P(E.C(150, 200, 220, 120 * a)))
                c.drawRect(skia.Rect.MakeXYWH(x - 120, y - 120, 240, 22), E.P(E.C(10, 18, 30, 255 * a)))
                for s in (1, -1): c.drawLine(x - 90, y + (70 if s > 0 else 150), x + 90, y + (150 if s > 0 else 70), E.P(E.C(*RED, 255 * a), 'stroke', 18))
            text(c, title, x, y - 200, 54, GREEN if ok else RED, a)
        text(c, 'NOT ENOUGH ON ITS OWN', W * .27, H * .45, 34, RED, clamp(u * 3 - .5))
    return sk(img, f)

def count3500(T, u, base='jam'):
    img = kb(base, u, 1.0, 1.1, (.5, .45), (.5, .42))
    def f(c):
        n = int(3500 * eout(clamp(u * 1.8)))
        text(c, f'~{n:,}', W / 2, H * .36, 200, YEL)
        text(c, 'CARS AND TRUCKS STUCK', W / 2, H * .42, 60, WHITE); text(c, 'ROUTE 128 NEAR BOSTON', W / 2, H * .465, 46, BLUE)
    return sk(img, f)

def archive(img, k=1.0):
    g = img.mean(2, keepdims=True)
    return img * (1 - k) + (g * np.float32([.85, .95, 1.08]) + np.float32([0, 4, 10])) * k

# ---------------------------------------------------------------- scenes
def S0(t, T):   # HOOK: car buried to the bumper, taillights glowing, exhaust smothered by the drift, blizzard
    img = kb('rear', t / 2.2, 1.55, 1.38, (.5, .5), (.5, .5))
    img = smoke(img, T, .42, .62, 1.0, 1.4)
    return snow(shake(flash(img, t + .3, 60, 6), t, 12, 2.5), T, 1.0)

def S1(t, T):
    c = wt('Kai') - .1
    if t < c: return snow(kb('wide', t / c, 1.0, 1.15, (.5, .5), (.52, .55)), T, 1.0)
    u = t - c
    return whip(snow(kb('int', u / (D + PAD - c), 1.05, 1.14, (.5, .5), (.5, .48)), T, .25), u)

def S2(t, T):
    img = ptalk('cu_leo', t, t / (D + PAD), 1.02, 1.12, (.5, .45), (.5, .42), .01)
    def f(c):   # heater vents glowing warm
        E.glow(c, W * .5, H * .95, 520, (255, 150, 60), .45 + .1 * math.sin(T * 5))
    return sk(img, f)

def S3(t, T):
    c = wt('tailpipe') - .9
    if t < c:
        img = kb('rear', t / c, 1.25, 1.45, (.5, .58), (.47, .62))
        return snow(snowpile(img, t / c, .78, .9), T, 1.0)
    u = t - c
    return whip(snow(kb('pipe', u / (D + PAD - c), 1.0, 1.12, (.55, .55), (.55, .58)), T, .9), u)

def S4(t, T):
    c = wt('builds') - .2
    if t < c: return whip(exhaust_flow(T, clamp(t / 2.2)), t)
    u = t - c
    return whip(haze(kb('int', u / (D + PAD - c), 1.1, 1.2, (.5, .5), (.5, .47)), .35 + .3 * clamp(u / 2)), u)

def S5(t, T):
    c = wt('No') - .15
    img = haze(kb('int', t / (D + PAD), 1.2, 1.3, (.5, .48), (.5, .46)), .6)
    if t < c:
        def f(cn): co_molecule(cn, W / 2, H * .3, 1.4, eout(clamp(t / .4)))
        return sk(blur(img, 6) * .6, f)
    u = t - c
    def g(cn):
        co_molecule(cn, W / 2, H * .25, 1.0, 1.0)
        text(cn, 'NO COLOR', W / 2, H * .38, 80, WHITE, clamp(u * 4)); text(cn, 'NO SMELL', W / 2, H * .45, 80, WHITE, clamp(u * 4 - 2.5))
    return whip(sk(blur(img, 6) * .55, g), u)

def S6(t, T):
    c = wt('alarm') - .4
    if t < c: return snow(kb('pipe', t / c, 1.12, 1.2, (.55, .58), (.55, .6)), T, .8)
    u = t - c
    return whip(alarm_test(T, clamp(u / (D + PAD - c - .4)), u), u)

def S7(t, T):
    img = ptalk('cu_leo', t, t / (D + PAD), 1.18, 1.28, (.5, .42), (.5, .4), .01)
    return pulse(haze(img, .25), T, .5, .3, .8)

def S8(t, T):
    ws = [wt(w) for w in ('Headache', 'Dizziness', 'Confusion', 'sleepiness')]
    act = sum(clamp((t - w) / .3) for w in ws)
    img = symptoms(T, act, t / (D + PAD))
    if t > ws[1]: img = cv2.warpAffine(img, cv2.getRotationMatrix2D((W / 2, H / 2), 1.5 * math.sin(T * 2.5), 1.0), (W, H), borderMode=cv2.BORDER_REFLECT)
    return img

def S9(t, T):
    c = wt('two') - .2
    if t < c: return kb('cu_leo_sleepy', t / c, 1.05, 1.12, (.5, .45), (.5, .43))
    return whip(blood(T, clamp((t - c) / 2.6)), t - c)

def S10(t, T): return body_o2(T, clamp(t / 3.0))

def S11(t, T):
    img = haze(ptalk('cu_leo_sleepy', t, t / (D + PAD), 1.12, 1.2, (.55, .42), (.55, .41), .006), .3)
    return blink(img, clamp((t - (D - .6)) / .8) * .7)

def S12(t, T):
    c = wt('die') - .2
    if t < c: return darken(haze(kb('int', t / c, 1.2, 1.28, (.5, .46), (.5, .45)), .5), .25 + .2 * t / c)
    u = t - c
    img = kb('rear', u / (D + PAD - c), 1.3, 1.45, (.5, .5), (.5, .52))
    return whip(snow(smoke(darken(img, .15), T, .42, .62, .8, 1.2), T, 1.0), u)

def S13(t, T):
    img = shake(ptalk('cu_kai', t, t / (D + PAD), 1.05, 1.15, (.47, .45), (.47, .43), .012), t, 16, 2.5)
    return flash(img, t, 50, 6)

def S14(t, T):
    c1 = wt('opens') - .1; c2 = wt('digs') - .1; c3 = wt('tailpipe') - .15
    if t < c1: return kb('int', t / c1, 1.12, 1.04, (.5, .5), (.5, .5))
    if t < c2: return whip(snow(kb('side', (t - c1) / (c2 - c1), 1.15, 1.25, (.48, .45), (.5, .45)), T, .9), t - c1)
    if t < c3: return whip(snow(shake(kb('dig', (t - c2) / (c3 - c2), 1.1, 1.2, (.5, .5), (.5, .55)), t - c2, 6, 1), T, 1.0), t - c2)
    u = t - c3
    return whip(snow(kb('pipe_clear', u / (D + PAD - c3), 1.15, 1.05, (.52, .55), (.52, .55)), T, .8), u)

def S15(t, T):
    a1, a2 = wt('stay'), wt('Run')
    if t < a1 - .3: return snow(kb('side', t / a1, 1.0, 1.08, (.5, .5), (.5, .48)), T, .8)
    act = clamp((t - a1 + .1) / .35) + clamp((t - a2 + .1) / .35)
    return whip(nws(T, act, t / (D + PAD)), t - a1 + .3)

def S16(t, T):
    c = wt('cracked') - .15
    if t < c: return snow(smoke(kb('pipe_clear', t / c, 1.0, 1.1, (.52, .55), (.5, .57)), T, .35, .6, .9, .8, up=.3), T, .7)
    return whip(window_vs_pipe(T, clamp((t - c) / 2.2)), t - c)

def S17(t, T): return snow(ptalk('side', t, t / (D + PAD), 1.35, 1.45, (.56, .42), (.56, .41), .008), T, .6)

def S18(t, T):
    c = wt('about') - .15
    if t < c: return archive(snow(kb('jam', t / c, 1.15, 1.0, (.5, .5), (.5, .45)), T, 1.0), .5)
    return whip(snow(archive(count3500(T, clamp((t - c) / 3.0)), .3), T, .8), t - c)

def S19(t, T):
    c = wt('buried') - .2; c2 = wt('died') - .15
    if t < c: return archive(snow(kb('jam', t / c, 1.4, 1.6, (.3, .62), (.3, .66)), T, 1.0), .6)
    if t < c2: return whip(archive(snow(snowpile(kb('pipe', (t - c) / (c2 - c), 1.0, 1.1), (t - c) / (c2 - c), .5), T, 1.0), .6), t - c)
    u = t - c2
    return whip(archive(darken(snow(kb('rear', u / 2.5, 1.5, 1.6, (.5, .5), (.5, .52)), T, 1.0), .25), .75), u)

def S20(t, T):
    c = (D + PAD) - .9
    if t < c: return snow(ptalk('cu_kai', t, t / c, 1.15, 1.22, (.45, .43), (.45, .42), .01), T, .2)
    u = t - c   # loop: back to the first frame (the buried car)
    img = smoke(kb('rear', 0, 1.55, 1.55), T, .42, .62, 1.0, 1.4)
    return whip(snow(img, T, 1.0), u, vertical=True)

# ---------------------------------------------------------------- overlays
def overlays():
    o = []
    if idx == 0: o += [{'type': 'hook', 'text': 'SNOW BURIED|THE TAILPIPE', 'y': .11}]
    if idx == 1: o += [{'type': 'datestamp', 'text': 'BLIZZARD · 11:40 PM', 'y': .08, 'from': .1}]
    if idx == 2: o += [{'type': 'label', 'text': 'HEATER ON · ENGINE RUNNING', 'pos': [.5, .12], 'color': YEL, 'from': .3}]
    if idx == 3: o += [{'type': 'label', 'text': 'TAILPIPE', 'pos': [.5, .12], 'color': RED, 'from': wt('tailpipe') - .9}]
    if idx == 5: o += [{'type': 'label', 'text': 'CARBON MONOXIDE (CO)', 'pos': [.5, .12], 'color': YEL, 'from': .2},
                       {'type': 'label', 'text': 'REAL CO IS INVISIBLE', 'pos': [.5, .555], 'color': GREY, 'from': wt('No')}]
    if idx == 6: o += [{'type': 'badge', 'value': '1:24', 'unit': 'MIN:SEC TO ALARM', 'pos': [.5, .13], 'from': wt('alarm') - .2}]
    if idx == 7: o += [{'type': 'label', 'text': 'SYMPTOM #1', 'pos': [.5, .12], 'color': RED, 'from': .3}]
    if idx == 9: o += [{'type': 'badge', 'value': '200×+', 'unit': 'STRONGER GRIP THAN OXYGEN', 'pos': [.5, .12], 'from': wt('two') - .1, 'size': 80}]
    if idx == 12: o += [{'type': 'label', 'text': 'ASLEEP = NO WARNING', 'pos': [.5, .12], 'color': RED, 'from': .3}]
    if idx == 14: o += [{'type': 'label', 'text': 'ENGINE OFF · WINDOW · DIG', 'pos': [.5, .12], 'color': GREEN, 'from': .3}]
    if idx == 15: o += [{'type': 'label', 'text': 'NATIONAL WEATHER SERVICE ADVICE', 'pos': [.5, .085], 'color': WHITE, 'from': .2}]
    if idx == 16: o += [{'type': 'label', 'text': 'CLEAR THE PIPE FIRST', 'pos': [.5, .12], 'color': GREEN, 'from': .2}]
    if idx == 18: o += [{'type': 'datestamp', 'text': 'MASSACHUSETTS · FEB 1978', 'y': .08, 'from': .1},
                        {'type': 'label', 'text': 'ILLUSTRATION', 'pos': [.5, .955], 'color': GREY, 'from': 0}]
    if idx == 19: o += [{'type': 'label', 'text': 'CARBON MONOXIDE DEATHS', 'pos': [.5, .12], 'color': RED, 'from': wt('died') - .1},
                        {'type': 'label', 'text': 'IN SNOWBOUND CARS', 'pos': [.5, .175], 'color': WHITE, 'from': wt('died') - .1}]
    if idx == 20: o += [{'type': 'cta', 'text': 'FOLLOW FOR MORE STORIES', 'from': .2}]
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
