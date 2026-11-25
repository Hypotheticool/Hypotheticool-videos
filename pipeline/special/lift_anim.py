"""Animate every scene of "The cables snapped on floor 80" over its Cycles plates (2D camera moves, cuts, sparks, fog, diagrams).
python3 lift_anim.py <scene> [still_times...]  ->  lift/s<scene>/f_####.png + meta.json (overlays read by compose.py)"""
import sys, math, json, os
sys.path.insert(0, '/home/claude/pro')
import numpy as np, cv2, skia
import engine as E
ROOT = '/home/claude/b3d/lift'; CFG = json.load(open(f'{ROOT}/topic.json'))
FPS = 24; PAD = .75; XF = .35
idx = int(sys.argv[1]); D = CFG['durs'][idx]; NF = int(math.ceil((D + PAD) * FPS))
W, H = 1080, 1920
ease = lambda t: .5 - .5 * math.cos(math.pi * min(max(t, 0), 1))
eout = lambda t: 1 - (1 - min(max(t, 0), 1)) ** 3
clamp = lambda v, a=0., b=1.: max(a, min(b, v))

def wt(word, line=None, end=False):
    """local scene time (s) when `word` is spoken in this scene's line"""
    ln = E.shown(CFG['lines'][idx if line is None else line]); words = ln.split()
    clip = D - E.lead(idx) - E.GAP; tt = E.word_times(ln, clip)
    for k, w in enumerate(words):
        if word.lower() in w.lower(): return XF + E.lead(idx) + tt[k][1 if end else 0]
    raise KeyError(word)

PL = {}
def plate(name):
    if name not in PL:
        im = cv2.imread(f'{ROOT}/plates/{name}.png', cv2.IMREAD_COLOR)
        if im.shape[1] != W: im = cv2.resize(im, (W, H), interpolation=cv2.INTER_CUBIC)
        PL[name] = im.astype(np.float32)
    return PL[name]

def kb(name, u, z0, z1, c0=(.5, .5), c1=(.5, .5), rot=0.0, im=None):
    """Ken-Burns move on a plate: zoom z0->z1 around a moving center (fractions of the plate), optional roll (deg)"""
    im = plate(name) if im is None else im; t = ease(u); z = z0 + (z1 - z0) * t
    cx = (c0[0] + (c1[0] - c0[0]) * t) * W; cy = (c0[1] + (c1[1] - c0[1]) * t) * H
    M = cv2.getRotationMatrix2D((cx, cy), rot, z); M[0, 2] += W / 2 - cx; M[1, 2] += H / 2 - cy
    return cv2.warpAffine(im, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

def shift(img, dx, dy):
    return cv2.warpAffine(img, np.float32([[1, 0, dx], [0, 1, dy]]), (W, H), borderMode=cv2.BORDER_REFLECT)

def shake(img, t, amp=10, decay=3.0):
    a = amp * math.exp(-t * decay)
    if a < .5: return img
    return shift(img, a * math.sin(t * 71), a * math.cos(t * 53))

def talk(t, amp=.006): return 1 + amp * (math.sin(t * 17) * .6 + math.sin(t * 11) * .4)

def ptalk(name, t, u, z0, z1, c0=(.5, .5), c1=(.5, .5), amp=.007, warm=True):
    img = kb(name, u, z0, z1, c0, c1)
    img = cv2.warpAffine(img, cv2.getRotationMatrix2D((W / 2, H / 2), 0, talk(t, amp)), (W, H), borderMode=cv2.BORDER_REFLECT)
    return motes(img, t, (255, 180, 110) if warm else (200, 220, 255), .5)

rng = np.random.default_rng(5); MOTES = rng.random((150, 4))
def motes(img, T, col=(120, 190, 255), k=1.0, region=(0, 0, 1, 1), vy=14):
    lay = np.zeros_like(img)
    for x, y, s, b in MOTES:
        px = int((region[0] + x * (region[2] - region[0])) * W + math.sin(T * .6 + y * 9) * 20)
        py = int(((region[1] + y * (region[3] - region[1])) * H - T * vy * (.3 + s)) % H)
        r = 1 + int(s * 3); v = (.25 + .75 * b * b) * k
        cv2.circle(lay, (px, py), r, tuple(c * v for c in col), -1, cv2.LINE_AA)
    return img + cv2.GaussianBlur(lay, (0, 0), 1.5)

def whip(img, t, dur=.12, vertical=False):
    if t >= dur: return img
    k = int(70 * (1 - t / dur)) | 1
    if k < 3: return img
    ker = np.zeros((k, 1) if vertical else (1, k), np.float32); ker[...] = 1 / k
    return cv2.filter2D(img, -1, ker)

def vblur(img, k):   # vertical motion blur (falling)
    k = int(k) | 1
    if k < 3: return img
    ker = np.full((k, 1), 1 / k, np.float32); return cv2.filter2D(img, -1, ker)

def flash(img, t, k=220, decay=7): return img + k * math.exp(-max(t, 0) * decay)
def grade(img, mul=(1, 1, 1), add=0.0): return img * np.float32(mul)[None, None, :] + add
YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)
VIGM = (1 - .55 * np.clip(((XX / W - .5) ** 2 * 1.6 + (YY / H - .5) ** 2) ** .5 - .25, 0, 1) * 1.6)[..., None]
def vignette(img): return img * VIGM

def sepia(img, k=1.0):
    g = img.mean(2, keepdims=True); s = g * np.float32([.72, .9, 1.12]) + np.float32([0, 4, 14])
    return img * (1 - k) + s * k

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

SPK = np.random.default_rng(9).random((90, 4))
def sparks(img, T, x, y, k=1.0, spread=1.0, down=True):
    """hot sparks spraying from a point (friction of steel on steel): additive streaks with gravity"""
    def f(c):
        for a_, v, life, ph in SPK:
            age = ((T * 1.7 + ph) % 1.0)
            ang = (a_ - .5) * math.pi * 1.4 * spread + (math.pi / 2 if down else -math.pi / 2)
            sp = 500 + 900 * v; px = x + math.cos(ang) * sp * age; py = y + math.sin(ang) * sp * age + 900 * age * age
            tx, ty = math.cos(ang) * sp * .03, math.sin(ang) * sp * .03 + 60 * age
            al = (1 - age) * k
            c.drawLine(px, py, px - tx, py - ty, E.P(E.C(255, 200, 90, 255 * al), 'stroke', 3 + 3 * v, add=True))
        E.glow(c, x, y, 120, (255, 150, 50), .8 * k)
    return sk(img, f)

FOG = None
def fog(img, T, k=.6, col=(178, 168, 155)):
    """drifting fog layers (two scrolling soft noise fields)"""
    global FOG
    if FOG is None:
        r = np.random.default_rng(2); n = r.random((60, 34)).astype(np.float32)
        FOG = cv2.resize(cv2.GaussianBlur(n, (0, 0), 2.2), (W * 2, H), interpolation=cv2.INTER_CUBIC); FOG = (FOG - FOG.min()) / (np.ptp(FOG) + 1e-6)
    o1 = int(T * 40) % W; o2 = int(T * 75 + 300) % W
    f = (FOG[:, o1:o1 + W] * .6 + FOG[:, o2:o2 + W] * .4)[..., None]
    a = np.clip(k * (.45 + .8 * f), 0, .95)
    return img * (1 - a) + np.float32(col) * a

# ---------------------------------------------------------------- props + diagrams (2D)
def indicator(T, floor, arrow_k=1.0, red=False, glitch=0.0):
    """close-up of the car's floor indicator: amber dot-matrix digits behind dark glass, a down arrow"""
    def f(c):
        c.clear(E.C(8, 9, 11))
        c.drawRect(skia.Rect.MakeXYWH(90, 560, 900, 620), E.P(shader=E.linear((0, 560), (0, 1180), [E.C(46, 48, 52), E.C(20, 21, 24)])))
        c.drawRect(skia.Rect.MakeXYWH(140, 610, 800, 520), E.P(E.C(4, 3, 3)))
        col = (255, 40, 30) if red else (255, 140, 30)
        s = f'{floor:d}'
        if glitch > 0 and (int(T * 30) % 3 == 0): s = '--'
        fo = font(400); w = fo.measureText(s)
        for b in (26, 8):
            c.drawString(s, 540 - w / 2 + 70, 1010, fo, E.P(E.C(*col, 160), blur=b, add=True))
        c.drawString(s, 540 - w / 2 + 70, 1010, fo, E.P(E.C(*col)))
        if arrow_k > 0:
            ax, ay = 250, 860 + 25 * math.sin(T * 9)
            pth = skia.Path(); pth.moveTo(ax - 70, ay - 40); pth.lineTo(ax + 70, ay - 40); pth.lineTo(ax, ay + 70); pth.close()
            c.drawPath(pth, E.P(E.C(*col, 255 * arrow_k)))
        # dot-matrix mesh + glass glare
        for yy in range(610, 1130, 9): c.drawLine(140, yy, 940, yy, E.P(E.C(0, 0, 0, 120), 'stroke', 3))
        c.drawRect(skia.Rect.MakeXYWH(140, 610, 800, 160), E.P(E.C(255, 255, 255, 14)))
    return sk(np.zeros((H, W, 3), np.float32), f)

def speedo(T, u):
    """impact-speed gauge: falling at 72 mph; a perfect jump (about 7 mph) only takes it to 65 mph"""
    v = 72 - 7 * eout(clamp(u))
    def f(c):
        c.clear(E.C(6, 10, 16))
        cx, cy, R = W / 2, H * .37, 380
        p = E.P(E.C(60, 75, 95), 'stroke', 26); a0, a1 = 150, 390
        c.drawArc(skia.Rect.MakeXYWH(cx - R, cy - R, 2 * R, 2 * R), a0, a1 - a0, False, p)
        for mph in range(0, 81, 10):
            a = math.radians(a0 + (a1 - a0) * mph / 80); x0, y0 = cx + math.cos(a) * (R - 40), cy + math.sin(a) * (R - 40)
            c.drawLine(x0, y0, cx + math.cos(a) * (R - 5), cy + math.sin(a) * (R - 5), E.P(E.C(200, 210, 225), 'stroke', 6))
            text(c, str(mph), cx + math.cos(a) * (R - 95), cy + math.sin(a) * (R - 95) + 16, 44, (200, 210, 225))
        # red danger zone above 55 mph
        a55 = a0 + (a1 - a0) * 55 / 80
        c.drawArc(skia.Rect.MakeXYWH(cx - R, cy - R, 2 * R, 2 * R), a55, a1 - a55, False, E.P(E.C(230, 50, 40, 220), 'stroke', 26))
        a = math.radians(a0 + (a1 - a0) * v / 80 + 1.2 * math.sin(T * 40))
        c.drawLine(cx, cy, cx + math.cos(a) * (R - 60), cy + math.sin(a) * (R - 60), E.P(E.C(255, 222, 40), 'stroke', 14))
        c.drawCircle(cx, cy, 30, E.P(E.C(255, 222, 40)))
        text(c, f'{v:.0f} MPH', cx, cy + 210, 120, (255, 255, 255))
        text(c, 'IMPACT SPEED', cx, cy + 290, 48, (170, 190, 215))
        text(c, 'FROM 165 FT (50 m)', cx, H * .15, 56, (255, 222, 40))
    return sk(np.zeros((H, W, 3), np.float32), f)

def gov_diagram(T, u_fast, lock):
    """overspeed governor, front view: sheave spins; past the trip speed the flyweights swing out and catch the ratchet; the rope stops"""
    spin = T * (3 + 9 * u_fast) * (1 - lock)
    def f(c):
        c.clear(E.C(7, 11, 15))
        cx, cy, R = W / 2, H * .44, 330
        # outer ratchet ring (fixed)
        c.drawCircle(cx, cy, R + 60, E.P(E.C(40, 46, 54), 'stroke', 26))
        for k in range(24):
            a = k / 24 * 2 * math.pi; x0, y0 = cx + math.cos(a) * (R + 46), cy + math.sin(a) * (R + 46)
            pth = skia.Path(); pth.moveTo(x0, y0); pth.lineTo(cx + math.cos(a + .1) * (R + 16), cy + math.sin(a + .1) * (R + 16)); pth.lineTo(cx + math.cos(a + .2) * (R + 46), cy + math.sin(a + .2) * (R + 46)); pth.close()
            c.drawPath(pth, E.P(E.C(90, 98, 110)))
        # sheave with spokes
        c.drawCircle(cx, cy, R, E.P(shader=E.radial(cx - 80, cy - 80, R * 1.3, [E.C(170, 175, 185), E.C(95, 100, 110), E.C(55, 58, 66)])))
        c.drawCircle(cx, cy, R - 30, E.P(E.C(30, 33, 38), 'stroke', 10))
        for k in range(5):
            a = spin + k / 5 * 2 * math.pi
            c.drawLine(cx, cy, cx + math.cos(a) * (R - 40), cy + math.sin(a) * (R - 40), E.P(E.C(60, 64, 72), 'stroke', 22))
        # two flyweights pivoting outward with speed
        out = 30 + 240 * eout(u_fast)
        for s in (0, math.pi):
            a = spin + s; px, py = cx + math.cos(a) * 60, cy + math.sin(a) * 60
            ex, ey = cx + math.cos(a + .35) * (60 + out), cy + math.sin(a + .35) * (60 + out)
            c.drawLine(px, py, ex, ey, E.P(E.C(220, 50, 40), 'stroke', 46))
            c.drawCircle(ex, ey, 30, E.P(E.C(240, 70, 55)))
        c.drawCircle(cx, cy, 44, E.P(E.C(200, 205, 215)))
        # rope dropping to the car (moves while spinning)
        for x in (cx - R + 6, cx + R - 6):
            c.drawLine(x, cy, x, H, E.P(E.C(150, 150, 155), 'stroke', 12))
            for k in range(12):
                yy = (cy + k * 120 + (spin * 120) % 120)
                c.drawLine(x - 6, yy, x + 6, yy + 14, E.P(E.C(70, 70, 75), 'stroke', 4))
        if lock > 0:
            E.glow(c, cx + R + 30, cy, 120, (255, 170, 60), lock)
            text(c, 'LOCKED', cx, cy + R + 190, 90, (255, 222, 40), lock)
        text(c, 'TOO FAST' if u_fast > .2 else 'NORMAL SPEED', cx, H * .14, 70, (255, 120, 90) if u_fast > .2 else (150, 220, 160))
    return sk(np.zeros((H, W, 3), np.float32), f)

def esb_section(T, u_fall, show_lib=0.0):
    """side elevation of the Empire State Building (to proportion: 102 floors, ~3.8 m each; 1,250 ft to the roof), the elevator falling 75 floors"""
    def f(c):
        c.clear(E.C(16, 22, 28))
        base, top = H * .9, H * .12          # ground .. 102nd floor
        fl = (base - top) / 102
        def yz(n): return base - n * fl
        tiers = [(0, 6, 420), (6, 72, 300), (72, 81, 250), (81, 86, 210), (86, 102, 70)]
        for n0, n1, w in tiers:
            c.drawRect(skia.Rect.MakeLTRB(W / 2 - w / 2 - 60, yz(n1), W / 2 + w / 2 - 60, yz(n0)), E.P(E.C(70, 80, 88)))
        c.drawLine(W / 2 - 60, yz(102), W / 2 - 60, yz(102) - 60, E.P(E.C(70, 80, 88), 'stroke', 8))
        for n in range(0, 102, 2): c.drawLine(W / 2 - 210, yz(n), W / 2 + 90, yz(n), E.P(E.C(40, 48, 56), 'stroke', 2))
        # the shaft and the car
        sx = W / 2 - 60
        c.drawRect(skia.Rect.MakeLTRB(sx - 22, yz(80), sx + 22, base + 10), E.P(E.C(10, 12, 14)))
        f_now = 80 - 75 * (u_fall ** 2)          # accelerates
        cy = yz(f_now)
        c.drawRect(skia.Rect.MakeLTRB(sx - 20, cy - fl * 1.3, sx + 20, cy), E.P(E.C(255, 200, 80)))
        E.glow(c, sx, cy - fl * .6, 60, (255, 170, 60), .8)
        if u_fall > 0: c.drawLine(sx, yz(80), sx, cy - fl * 1.3, E.P(E.C(255, 200, 80, 90), 'stroke', 4))
        # crash zone at floors 78-80 (north face)
        c.drawRect(skia.Rect.MakeLTRB(W / 2 - 210, yz(80), W / 2 - 150, yz(78)), E.P(E.C(255, 120, 40)))
        E.glow(c, W / 2 - 180, yz(79), 70, (255, 120, 40), .9)
        text(c, 'FLOOR 80', W / 2 - 330, yz(80) + 10, 40, (255, 200, 120))
        text(c, 'SUB-BASEMENT', W / 2 - 330, base + 50, 36, (200, 210, 220))
        # measure line
        mx = W * .86
        c.drawLine(mx, yz(80), mx, base, E.P(E.C(255, 222, 40), 'stroke', 6))
        for yy in (yz(80), base): c.drawLine(mx - 24, yy, mx + 24, yy, E.P(E.C(255, 222, 40), 'stroke', 6))
        # Statue of Liberty for scale: 305 ft ground to torch, stacked 3x is still shorter than the fall (1,000+ ft)
        if show_lib > 0:
            ft = (yz(80) - base) / -1000.0 * 1000 / 1000   # px per ft below
            pxft = (base - yz(80)) / 1000.0
            for k in range(3):
                y0 = base - k * 305 * pxft; y1 = y0 - 305 * pxft * eout(clamp(show_lib * 3 - k))
                lx = W * .7
                c.drawRect(skia.Rect.MakeLTRB(lx - 26, y1 + (y0 - y1) * .45, lx + 18, y0), E.P(E.C(90, 160, 140, 230)))   # pedestal
                c.drawLine(lx - 40, y0, lx + 40, y0, E.P(E.C(20, 30, 30), 'stroke', 4))
                c.drawRect(skia.Rect.MakeLTRB(lx - 10, y1 + (y0 - y1) * .08, lx + 10, y1 + (y0 - y1) * .45), E.P(E.C(110, 190, 165, 230)))  # statue
                c.drawLine(lx + 8, y1 + (y0 - y1) * .1, lx + 14, y1, E.P(E.C(110, 190, 165, 230), 'stroke', 5))
            text(c, '3 STATUES OF LIBERTY', W * .7, base - 3 * 305 * pxft - 30, 36, (150, 230, 200), clamp(show_lib * 3 - 2))
            text(c, '(915 FT)', W * .7, base - 3 * 305 * pxft + 10, 32, (150, 230, 200), clamp(show_lib * 3 - 2))
        text(c, 'NOT EVERY FLOOR SHOWN', W / 2, H * .965, 30, (150, 160, 170), .8)
    return sk(np.zeros((H, W, 3), np.float32), f)

def cushion(T, u):
    """why she lived (likely): the falling car squeezes the air below it in a narrow shaft, and the snapped cables pile up in a coil at the bottom"""
    def f(c):
        c.clear(E.C(12, 16, 22))
        x0, x1 = W / 2 - 200, W / 2 + 200; bot = H * .86
        c.drawRect(skia.Rect.MakeLTRB(x0 - 40, H * .05, x0, bot + 40), E.P(E.C(60, 66, 72))); c.drawRect(skia.Rect.MakeLTRB(x1, H * .05, x1 + 40, bot + 40), E.P(E.C(60, 66, 72)))
        c.drawRect(skia.Rect.MakeLTRB(x0 - 40, bot, x1 + 40, bot + 40), E.P(E.C(60, 66, 72)))
        cy = H * .12 + (bot - H * .12 - 470) * eout(clamp(u * 1.15))
        # squeezed air: denser blue below the car, arrows pushing up
        a_k = clamp(u * 1.4)
        c.drawRect(skia.Rect.MakeLTRB(x0, cy + 300, x1, bot), E.P(shader=E.linear((0, cy + 300), (0, bot), [E.C(80, 160, 255, 40 + 110 * a_k), E.C(120, 190, 255, 60 + 160 * a_k)])))
        for k in range(5):
            ax = x0 + 50 + k * 75; ay = bot - 60 - ((T * 160 + k * 70) % max(60, (bot - cy - 380)))
            E.arrow(c, ax, ay + 40, ax, ay - 40, 10, (170, 220, 255), .9 * a_k)
        # coiled cables at the bottom (a spring)
        coil_h = 120 * clamp(u * 2)
        for k in range(9):
            yy = bot - 14 - k * coil_h / 9
            c.drawOval(skia.Rect.MakeLTRB(x0 + 30, yy - 16, x1 - 30, yy + 16), E.P(E.C(175, 175, 180), 'stroke', 8))
        # the car
        c.drawRect(skia.Rect.MakeLTRB(x0 + 10, cy, x1 - 10, cy + 300), E.P(shader=E.linear((0, cy), (0, cy + 300), [E.C(210, 160, 80), E.C(150, 100, 45)])))
        c.drawRect(skia.Rect.MakeLTRB(x0 + 10, cy, x1 - 10, cy + 300), E.P(E.C(255, 220, 150), 'stroke', 6))
        text(c, 'SQUEEZED AIR', W / 2, bot - 200, 52, (180, 225, 255), a_k)
        text(c, 'COILED CABLES', W / 2, bot + 110, 52, (230, 230, 235), clamp(u * 2 - .6))
        text(c, 'NOT TO SCALE', W / 2, H * .97, 30, (150, 160, 170), .8)
    return sk(np.zeros((H, W, 3), np.float32), f)

def snap_fx(img, T, t, x=.5, y0=0.0, k=1.0):
    """snapped hoist-rope ends whipping loose above the car: six bright strands flailing at different lengths + a flash"""
    def f(c):
        for j in range(6):
            xx = W * x + (j - 2.5) * 34; ph = j * 1.7
            ln = H * (.18 + .05 * (j % 3)) * (1 - .4 * eout(clamp(t * 2)))
            sw = (120 + 60 * (j % 2)) * math.sin(T * 9 + ph) * (1 - .5 * clamp(t))
            pth = skia.Path(); pth.moveTo(xx, H * y0); pth.cubicTo(xx + sw * .3, H * y0 + ln * .35, xx - sw * .6, H * y0 + ln * .7, xx + sw, H * y0 + ln)
            c.drawPath(pth, E.P(E.C(225, 225, 232, 235 * k), 'stroke', 7))
            c.drawCircle(xx + sw, H * y0 + ln, 9, E.P(E.C(255, 210, 140, 255 * k)))   # frayed hot end
            E.glow(c, xx + sw, H * y0 + ln, 40, (255, 170, 70), .6 * k)
        E.glow(c, W * x, H * (y0 + .04), 220, (255, 200, 120), k * math.exp(-t * 4))
    return sk(img, f)

# ================================================================== scenes
def S0(t, T):   # HOOK: looking up the shaft as the cables snap (sparks, flash), then the scared cast
    c = 1.35
    if t < c:
        img = grade(kb('shaft_up', t / 2.5, 1.12, 1.3, (.5, .5), (.5, .42)), (.62, .68, .8))
        img = snap_fx(img, T, t + .25, .5, .44, 1.0)
        img = sparks(img, T + .4, W * .5, H * .46, 1.0, 1.4)
        return shake(flash(img, t - .5, 70, 9) if t > .5 else img, t + .3, 18, 1.0)
    img = kb('car_scared', (t - c) / 2, 1.08, 1.18, (.5, .52), (.5, .5))
    return whip(shake(img, t - c, 14, 1.5), t - c, vertical=True)

def S1(t, T):
    c = wt('Kai') - .15
    if t < c: return indicator(T, 80, 1.0)
    return whip(motes(kb('car_wide', (t - c) / 3, 1.0, 1.08, (.5, .5), (.5, .52)), T, (255, 190, 120), .5), t - c)

def S2(t, T):
    c = wt('Then') - .1
    if t < c:
        img = kb('car_wide', .9, 1.0, 1.08, (.5, .5), (.5, .52)) * (.6 + .4 * (int(T * 20) % 2))
        return shake(flash(img, t - .3, 140, 8), t - .3, 22, 2)
    u = t - c
    img = indicator(T, max(65, int(80 - u * 9)), 1.0, red=True, glitch=1.0)
    img = shift(img, 0, -120 * eout(u * 2))
    return vblur(shake(img, u, 12, 1), 8 + 30 * clamp(u))

def S3(t, T):
    img = kb('cu_leo', eout(t / 1.0), 1.0, 1.1, (.5, .5), (.5, .46))
    img = cv2.warpAffine(img, cv2.getRotationMatrix2D((W / 2, H / 2), 0, talk(t, .01)), (W, H), borderMode=cv2.BORDER_REFLECT)
    return shake(img, T, 5, 0)

def S4(t, T): return shake(ptalk('cu_mia', t, t / (D + PAD), 1.03, 1.12, (.5, .5), (.5, .47)), T, 4, 0)

def S5(t, T):
    c1 = 1.9; c2 = wt('seventy-two') - .2
    if t < c1:
        img = kb('shaft_down', t / c1, 1.0, 1.3, (.5, .5), (.5, .58)) * 1.9
        return vblur(img, 10)
    if t < c2:
        return whip(speedo(T, 0), t - c1)
    return speedo(T, (t - c2 - .9) / 1.4)

def S6(t, T):
    c = wt('called') - .2
    if t < c: return vblur(shake(kb('shaft_up', t / c, 1.0, 1.15, (.5, .5), (.5, .4)), T, 6, 0), 6)
    return whip(motes(kb('governor', (t - c) / 2.2, 1.0, 1.12, (.5, .5), (.5, .45)), T, (255, 190, 120), .6), t - c)

def S7(t, T):
    lk = wt('lock') - .1
    u = clamp((t - .3) / max(.5, lk - .6)); lock = clamp((t - lk) / .2)
    img = gov_diagram(T, u, lock)
    return shake(img, t - lk, 10, 4) if t > lk else img

def S8(t, T):
    c = wt('Steel') - .15
    if t < c:
        img = kb('shaft_side', t / c, 1.0, 1.12, (.5, .6), (.55, .62))
        return vblur(img, 14 * (1 - t / c) + 2)
    img = kb('safety_cu', (t - c) / 2.4, 1.0, 1.15, (.5, .5), (.47, .5))
    img = sparks(img, T, W * .45, H * .5, clamp(1.2 - (t - c) / 2.2), .9)
    return whip(shake(img, t - c, 14, 2), t - c)

def S9(t, T):
    c = wt('they') - .2
    if t < c:
        img = sparks(kb('shaft_side', 1, 1.0, 1.12, (.5, .6), (.55, .62)), T, W * .58, H * .6, 1.0, 1.2)
        return shake(img, t, 16, 1.2)
    img = kb('car_scared', (t - c) / 2, 1.0, 1.05)
    return whip(shake(img, t - c, 20, 4), t - c, vertical=True)

def S10(t, T):
    c = wt('Far') - .2
    if t < c: return ptalk('cu_mia_serious', t, t / c, 1.03, 1.1, (.5, .5), (.5, .47))
    return whip(motes(kb('machine', (t - c) / 2.4, 1.0, 1.12, (.5, .5), (.47, .5)), T, (255, 190, 120), .6), t - c)

def S11(t, T):
    c = wt('rope') - .1; held = wt('held') - .05
    img = sepia(kb('otis', t / (D + PAD), 1.0, 1.25, (.5, .55), (.5, .45)), .55)
    def f(cn):
        if t > c:   # the rope parts: the cut ends spring apart
            u = eout((t - c) / .35); x = W * .5 - 10
            cn.drawLine(x, H * .28, x, H * .28 - 60 * u, E.P(E.C(255, 230, 160, 230), 'stroke', 5))
        if t > held: E.glow(cn, W * .5, H * .5, 260, (255, 200, 120), .35 * math.exp(-(t - held) * 2))
    img = sk(img, f)
    return motes(shake(img, t - c, 7, 3) if t > c else img, T, (255, 200, 140), .6)

def S12(t, T):
    img = kb('cu_leo_ask', eout(t / 1.0), 1.0, 1.1, (.5, .5), (.5, .47))
    return motes(cv2.warpAffine(img, cv2.getRotationMatrix2D((W / 2, H / 2), 0, talk(t, .008)), (W, H), borderMode=cv2.BORDER_REFLECT), T, (255, 190, 120), .5)

def S13(t, T): return ptalk('cu_mia_serious', t, t / (D + PAD), 1.12, 1.22, (.52, .47), (.5, .45))

def S14(t, T):
    c = wt('bomber') - .2
    if t < c: return fog(kb('esb_clear', t / c, 1.0, 1.12, (.5, .55), (.5, .45)), T, .45)
    u = (t - c) / (D + PAD - c); img = kb('esb_close', u, 1.0, 1.2, (.45, .45), (.5, .43))
    hit = wt('Empire') - c
    if t - c > hit:
        def f(cn):
            k = clamp((t - c - hit) / .3); E.glow(cn, W * .56, H * .43, 380, (255, 120, 40), k); E.glow(cn, W * .56, H * .43, 150, (255, 220, 140), k)
        img = shake(sk(img, f), t - c - hit, 16, 2)
    return whip(fog(img, T, .3), t - c)

def S15(t, T):
    c = wt('was') - .15
    if t < c:
        img = sepia(kb('old_car', t / c, 1.0, 1.1, (.5, .5), (.5, .47)), .4)
        return motes(img, T, (200, 190, 170), 1.2, vy=30)
    img = fog(kb('esb_close', (t - c) / 2.5, 1.35, 1.5, (.55, .43), (.56, .43)), T, .25, (120, 110, 100))
    def f(cn): E.glow(cn, W * .5, H * .5, 420, (255, 110, 40), .7 + .2 * math.sin(T * 13))
    return whip(sk(img, f), t - c)

def S16(t, T):
    c = wt('Its') - .1
    if t < c: return motes(sepia(kb('old_car', t / c, 1.1, 1.2, (.5, .45), (.5, .5)), .5), T, (200, 190, 170), 1.2, vy=30)
    u = t - c
    img = sepia(kb('shaft_up', u / 2, 1.2, 1.35, (.5, .45), (.5, .42)), .6)
    img = snap_fx(img, T, u, .5, .4, 1.0)
    return shake(flash(img, u, 160, 6), u, 18, 1.5)

def S17(t, T):
    u = clamp((t - .2) / 1.8)
    return esb_section(T, u, clamp((t - 1.9) / 1.5))

def S18(t, T):
    return cushion(T, clamp((t - .2) / (D - .6)))

def S19(t, T):
    c = wt('Still') - .2
    if t < c: return fog(kb('esb_clear', t / c, 1.2, 1.3, (.5, .45), (.5, .42)), T, .35)
    return whip(fog(kb('esb_clear', (t - c) / 2.4, 1.0, 1.06, (.5, .52), (.5, .5)), T, .25), t - c)

def S20(t, T):
    c = wt('taking') - .2
    if t < c: return ptalk('cu_kai_stairs', t, t / c, 1.03, 1.1, (.5, .5), (.5, .47))
    return whip(motes(kb('stairs', (t - c) / 2, 1.0, 1.08, (.5, .5), (.47, .5)), T, (255, 190, 120), .5), t - c)

def S21(t, T):
    c = (D + PAD) - .8
    if t < c: return motes(kb('car_wide', t / c, 1.12, 1.0, (.5, .5), (.5, .5)), T, (255, 190, 120), .5)
    img = kb('shaft_up', 0, 1.12, 1.3)   # loop: the first frame again
    return whip(snap_fx(grade(img, (.62, .68, .8)), T, .25, .5, .44, 1.0), t - c, vertical=True)

# ---------------------------------------------------------------- overlays
YEL, WHITE, BLUE, RED = (255, 222, 40), (255, 255, 255), (130, 200, 255), (255, 110, 90)
def overlays():
    o = []
    if idx == 0: o += [{'type': 'hook', 'text': 'THE CABLES SNAPPED|ON FLOOR 80', 'y': .11}]
    if idx == 1: o += [{'type': 'datestamp', 'text': '12:00 AM · FLOOR 80', 'y': .08, 'from': .1}]
    if idx == 5: o += [{'type': 'label', 'text': 'A PERFECT JUMP ≈ 7 MPH', 'pos': [.5, .075], 'color': WHITE, 'from': wt('jump') - .1},
                       {'type': 'badge', 'value': '65 MPH', 'unit': '≈ HIGHWAY SPEED', 'pos': [.5, .78], 'from': wt('miles') - .1, 'size': 64}]
    if idx == 6: o += [{'type': 'label', 'text': 'OVERSPEED GOVERNOR', 'pos': [.5, .12], 'color': YEL, 'from': wt('governor') - .1}]
    if idx == 8: o += [{'type': 'label', 'text': 'SAFETY BRAKES', 'pos': [.5, .12], 'color': YEL, 'from': wt('safety') - .1},
                       {'type': 'label', 'text': 'JAWS GRIP THE GUIDE RAIL', 'pos': [.5, .17], 'color': WHITE, 'from': wt('jaws') - .1}]
    if idx == 9: o += [{'type': 'label', 'text': 'STOPPED', 'pos': [.5, .12], 'color': YEL, 'from': wt('stopped') - .1}]
    if idx == 10: o += [{'type': 'label', 'text': 'SEVERAL STEEL CABLES', 'pos': [.5, .12], 'color': WHITE, 'from': wt('Far') - .1},
                        {'type': 'label', 'text': 'FAR MORE THAN NEEDED', 'pos': [.5, .17], 'color': YEL, 'from': wt('more') - .1}]
    if idx == 11: o += [{'type': 'datestamp', 'text': 'NEW YORK · 1854 · ELISHA OTIS', 'y': .08, 'from': .2},
                        {'type': 'label', 'text': 'IT HELD', 'pos': [.5, .16], 'color': YEL, 'from': wt('held') - .1}]
    if idx == 14: o += [{'type': 'datestamp', 'text': 'NEW YORK · JULY 28, 1945 · 9:40 AM', 'y': .08, 'from': .2},
                        {'type': 'label', 'text': 'B-25 BOMBER', 'pos': [.5, .16], 'color': WHITE, 'from': wt('bomber') - .1}]
    if idx == 15: o += [{'type': 'label', 'text': 'BETTY LOU OLIVER, 20', 'pos': [.5, .12], 'color': YEL, 'from': wt('Betty') - .1},
                        {'type': 'label', 'text': 'ELEVATOR OPERATOR', 'pos': [.5, .17], 'color': WHITE, 'from': wt('Betty') + .2}]
    if idx == 17: o += [{'type': 'badge', 'value': '75', 'unit': 'STORIES', 'pos': [.3, .1], 'from': wt('seventy-five') - .1},
                        {'type': 'badge', 'value': '1,000+', 'unit': 'FEET', 'pos': [.72, .1], 'from': wt('thousand') - .1}]
    if idx == 18: o += [{'type': 'label', 'text': 'WHY SHE LIVED (LIKELY)', 'pos': [.5, .08], 'color': YEL, 'from': .2}]
    if idx == 19: o += [{'type': 'label', 'text': 'BROKEN NECK, BACK + PELVIS', 'pos': [.5, .12], 'color': WHITE, 'from': .3},
                        {'type': 'badge', 'value': 'WORLD RECORD', 'unit': 'LONGEST ELEVATOR FALL SURVIVED', 'pos': [.5, .2], 'from': wt('Still') - .1, 'size': 60}]
    if idx == 21: o += [{'type': 'cta', 'text': 'FOLLOW FOR MORE STORIES', 'from': .2}]
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
