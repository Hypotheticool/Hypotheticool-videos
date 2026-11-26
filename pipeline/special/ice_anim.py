"""Animate every scene of "Leo fell through the ice" over its Cycles plates (2D camera moves, cuts, snow, breath, bubbles, diagrams).
python3 ice_anim.py <scene> [still_times...]  ->  ice/s<scene>/f_####.png + meta.json (overlays read by compose.py)"""
import sys, math, json, os
sys.path.insert(0, '/home/claude/pro')
import numpy as np, cv2, skia
import engine as E
ROOT = '/home/claude/b3d/ice'; CFG = json.load(open(f'{ROOT}/topic.json'))
FPS = 24; PAD = .75; XF = .35
idx = int(sys.argv[1]); D = CFG['durs'][idx]; NF = int(math.ceil((D + PAD) * FPS))
W, H = 1080, 1920
ease = lambda t: .5 - .5 * math.cos(math.pi * min(max(t, 0), 1))
eout = lambda t: 1 - (1 - min(max(t, 0), 1)) ** 3
clamp = lambda v, a=0., b=1.: max(a, min(b, v))
YEL, WHITE, BLUE, RED = (255, 222, 40), (255, 255, 255), (130, 200, 255), (255, 110, 90)

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
    """load a plate, upscale, and grade it into the video's palette: deep teal shadows, warm highlights, a touch darker"""
    if name not in PL:
        im = cv2.imread(f'{ROOT}/plates/{name}.png', cv2.IMREAD_COLOR)
        if im.shape[1] != W: im = cv2.resize(im, (W, H), interpolation=cv2.INTER_CUBIC)
        im = im.astype(np.float32); lum = im.mean(2, keepdims=True) / 255
        im = im * .86 + (1 - lum) * np.float32([26, 14, 0]) * .9 - 4     # BGR: teal into the shadows
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
    a = amp * math.exp(-t * decay)
    if a < .5: return img
    return shift(img, a * math.sin(t * 71), a * math.cos(t * 53))
def shiver(img, T, amp=3): return shift(img, amp * math.sin(T * 90), amp * .6 * math.cos(T * 77))
def talk(t, amp=.006): return 1 + amp * (math.sin(t * 17) * .6 + math.sin(t * 11) * .4)

def ptalk(name, t, u, z0, z1, c0=(.5, .5), c1=(.5, .5), amp=.007, snowk=.8):
    img = kb(name, u, z0, z1, c0, c1)
    img = cv2.warpAffine(img, cv2.getRotationMatrix2D((W / 2, H / 2), 0, talk(t, amp)), (W, H), borderMode=cv2.BORDER_REFLECT)
    return snow(img, t, snowk)

rng = np.random.default_rng(5); FL = rng.random((220, 4))
def snow(img, T, k=1.0, vy=60):
    """falling snowflakes, two depths (big blurred near ones, small far ones)"""
    if k <= 0: return img
    lay = np.zeros_like(img)
    for x, y, s, b in FL:
        px = int((x * W + math.sin(T * .8 + y * 11) * 30 + T * 12) % W)
        py = int((y * H + T * vy * (.4 + s)) % H)
        r = 1 + int(s * s * 6); v = (.35 + .65 * b) * k
        cv2.circle(lay, (px, py), r, (235 * v, 240 * v, 245 * v), -1, cv2.LINE_AA)
    return img + cv2.GaussianBlur(lay, (0, 0), 1.6)

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
def breath(img, T, x, y, k=1.0, fast=False):
    """frosty breath puffs from a mouth at (x, y) (fractions): soft white clouds that drift up and fade; fast = gasping"""
    per = .45 if fast else 1.3
    def f(c):
        for j in range(3):
            age = ((T / per + j / 3) % 1.0)
            r = 30 + 160 * age; a = (1 - age) ** 1.5 * .55 * k
            c.drawCircle(W * x + 60 * age + 20 * math.sin(T * 3 + j), H * y - 120 * age, r, E.P(E.C(230, 238, 245, 255 * a), blur=r * .45))
    return sk(img, f)

BUB = np.random.default_rng(3).random((70, 4))
def bubbles(img, T, cx=.5, spread=.35, k=1.0, top=.0):
    def f(c):
        for x, y, s, ph in BUB:
            px = W * (cx + (x - .5) * spread * 2) + 18 * math.sin(T * 3 + ph * 9)
            py = H - ((y * H + T * (260 + 300 * s)) % (H * (1 - top)))
            r = 4 + 14 * s * s
            c.drawCircle(px, py, r, E.P(E.C(210, 240, 250, 170 * k), 'stroke', 2.5))
            c.drawCircle(px - r * .35, py - r * .35, r * .25, E.P(E.C(255, 255, 255, 200 * k)))
    return sk(img, f)

def rays(img, T, x, y, k=1.0, spread=.25):
    """god rays falling from a bright point (the hole) into murky water"""
    def f(c):
        for j in range(7):
            a = (j - 3) * spread / 3 + .05 * math.sin(T * .7 + j)
            pth = skia.Path(); pth.moveTo(W * x - 30, H * y); pth.lineTo(W * x + 30, H * y)
            pth.lineTo(W * x + math.sin(a) * H + 160, H * y + H); pth.lineTo(W * x + math.sin(a) * H - 160, H * y + H); pth.close()
            c.drawPath(pth, E.P(E.C(255, 220, 160, 26 * k * (.6 + .4 * math.sin(T * 1.3 + j * 2))), blur=40, add=True))
    return sk(img, f)

CR = np.random.default_rng(11)
CRACKS = []
for j in range(9):
    a = j / 9 * 2 * math.pi + CR.uniform(-.25, .25); pts = [(0.0, 0.0)]; r = 0.0
    for s in range(7):
        r += CR.uniform(40, 90); a += CR.uniform(-.35, .35); pts.append((math.cos(a) * r, math.sin(a) * r * .45))
    CRACKS.append(pts)
def cracks(img, u, x, y, k=1.0, scale=1.0):
    """white fracture lines spreading out from (x, y) across the ice (perspective-squashed), u = growth 0..1"""
    def f(c):
        for pts in CRACKS:
            n = 1 + int(u * (len(pts) - 1)); pth = skia.Path(); pth.moveTo(W * x, H * y)
            for px, py in pts[1:n + 1]: pth.lineTo(W * x + px * scale, H * y + py * scale)
            c.drawPath(pth, E.P(E.C(140, 210, 255, 140 * k), 'stroke', 9, blur=6, add=True))
            c.drawPath(pth, E.P(E.C(235, 248, 255, 255 * k), 'stroke', 3))
    return sk(img, f)

SPL = np.random.default_rng(13).random((60, 4))
def splash(img, t, x, y, k=1.0):
    """water and ice chips thrown up and falling back"""
    def f(c):
        for a_, v, s, ph in SPL:
            age = clamp(t * (.9 + .5 * ph) + .08 * ph)
            ang = -math.pi / 2 + (a_ - .5) * 2.0; sp = 1000 + 1500 * v
            px = W * x + math.cos(ang) * sp * age * .5; py = H * y + math.sin(ang) * sp * age * .6 + 1500 * age * age
            al = (1 - age) * k
            if s > .6: c.drawRect(skia.Rect.MakeXYWH(px, py, 26 + 34 * s, 18 + 20 * s), E.P(E.C(225, 242, 252, 240 * al)))
            else: c.drawOval(skia.Rect.MakeXYWH(px, py, 14 + 20 * s, 22 + 34 * s), E.P(E.C(205, 232, 248, 230 * al), blur=2))
        E.glow(c, W * x, H * y, 200, (200, 235, 255), .5 * k * (1 - clamp(t * 2)))
    return sk(img, f)

# ---------------------------------------------------------------- 2D cards / diagrams
def bg_card(name, T, u, z=1.15, dark=.35, s=10):
    return blur(kb(name, u, z, z + .06), s) * dark

def one_ten_one(T, active, base='hole_leo', u=0.0):
    """the 1-10-1 rule: three timer cards; `active` (float) lights them one by one"""
    img = bg_card(base, T, u)
    items = [('1', 'MINUTE', 'CALM YOUR BREATHING'), ('10', 'MINUTES', 'TO GET OUT'), ('~1', 'HOUR', 'BEFORE YOU PASS OUT')]
    cols = [(120, 210, 255), (255, 222, 40), (255, 120, 90)]
    def f(c):
        for k, (big, unit, sub) in enumerate(items):
            on = clamp(active - k); y = H * (.165 + k * .127)
            if on <= 0 and active < 3.5: a = .3
            else: a = .3 + .7 * on
            x0 = W * .12; c.drawRoundRect(skia.Rect.MakeXYWH(x0, y, W * .76, 230), 30, 30, E.P(E.C(10, 22, 30, 215 * (a * .7 + .3))))
            c.drawRoundRect(skia.Rect.MakeXYWH(x0, y, W * .76, 230), 30, 30, E.P(E.C(*cols[k], 255 * a), 'stroke', 6))
            # a little clock ring filling up
            cx, cy = x0 + 130, y + 115; c.drawCircle(cx, cy, 80, E.P(E.C(255, 255, 255, 50 * a), 'stroke', 14))
            c.drawArc(skia.Rect.MakeXYWH(cx - 80, cy - 80, 160, 160), -90, 360 * eout(on), False, E.P(E.C(*cols[k], 255 * a), 'stroke', 14))
            text(c, big, cx, cy + 34, 96, cols[k], a)
            text(c, unit, x0 + 470, y + 100, 64, (255, 255, 255), a)
            text(c, sub, x0 + 470, y + 170, 42, cols[k], a)
    return snow(sk(img, f), T, .4)

def self_rescue(T, u, kick=True):
    """side cross-section (zoomed in at the hole edge): ice sheet, water below; the figure's chest on the edge, arms flat forward on the ice,
    legs kicking behind in the water, then sliding out on the belly (not to scale)"""
    top = H * .45; hx0, hx1 = W * .66, W * 1.2; S_ = 1.75; px0 = W * .6
    def X(x): return px0 + (x - hx0) * S_
    def f(c):
        c.clear(E.C(8, 16, 22))
        c.drawRect(skia.Rect.MakeLTRB(0, top, W, H), E.P(shader=E.linear((0, top), (0, H), [E.C(20, 70, 85), E.C(5, 20, 28)])))
        c.drawRect(skia.Rect.MakeLTRB(0, 0, W, top), E.P(shader=E.linear((0, 0), (0, top), [E.C(40, 50, 70), E.C(120, 90, 80)])))
        c.save(); c.translate(px0, top); c.scale(S_, S_); c.translate(-hx0, -top)
        c.drawRect(skia.Rect.MakeLTRB(-400, top, hx0, top + 60), E.P(E.C(170, 215, 230)))
        c.drawRect(skia.Rect.MakeLTRB(-400, top, hx0, top + 10), E.P(E.C(240, 250, 255)))
        c.drawRect(skia.Rect.MakeLTRB(hx0, top + 6, hx1, top + 12), E.P(E.C(120, 190, 210, 160)))   # water line in the hole
        lift = clamp(u / .45)
        sx = 600 - 150 * eout(clamp((u - .45) / .55))
        body_y = top - 30 + 46 * (1 - lift)
        for j, ph in ((0, 0), (1, math.pi)):
            swing = (.5 + .5 * math.sin(T * 14 + ph)) if (kick and u < .7) else .3
            ly = body_y + 40 + (30 + 70 * (1 - lift)) * swing
            c.drawLine(sx + 180, body_y + 10, sx + 340, ly, E.P(E.C(25, 25, 30), 'stroke', 16))
            c.drawOval(skia.Rect.MakeXYWH(sx + 330, ly - 10, 40, 22), E.P(E.C(25, 25, 30)))
        c.drawRoundRect(skia.Rect.MakeXYWH(sx + 40, body_y - 22, 160, 64), 30, 30, E.P(E.C(240, 180, 30)))
        for k in range(4): c.drawRect(skia.Rect.MakeXYWH(sx + 60 + k * 36, body_y - 22, 14, 64), E.P(E.C(30, 28, 26)))
        c.drawCircle(sx - 10, body_y - 8, 62, E.P(E.C(240, 240, 238)))
        c.drawCircle(sx - 10, body_y - 34, 58, E.P(E.C(230, 110, 30)))
        c.drawLine(sx + 40, body_y + 22, sx - 210, top - 6, E.P(E.C(25, 25, 30), 'stroke', 13))
        if kick and u < .7:
            for k in range(6):   # splashes behind
                a = (T * 3 + k / 6) % 1; c.drawCircle(sx + 330 + 40 * math.sin(k * 2.1), top - 10 - 90 * a, 6 * (1 - a) + 2, E.P(E.C(220, 240, 250, 220 * (1 - a))))
        c.restore()
        a1 = clamp(u * 4); a2 = clamp((u - .2) * 4); a3 = clamp((u - .55) * 4)
        text(c, 'ARMS FLAT ON THE ICE', W * .36, top - 330, 54, YEL, a1)
        E.arrow(c, W * .3, top - 290, X(sx - 140), top - 40, 10, YEL, a1)
        if u < .75:
            text(c, 'KICK', W * .82, top + 340, 66, YEL, a2)
            E.arrow(c, W * .82, top + 280, W * .86, top + 160, 12, YEL, a2)
        text(c, 'SLIDE OUT ON YOUR BELLY', W / 2, top - 460, 56, WHITE, a3)
        E.arrow(c, W * .7, top - 410, W * .3, top - 410, 12, WHITE, a3)
        text(c, 'NOT TO SCALE', W / 2, H * .96, 30, (150, 160, 170), .8)
    return snow(sk(np.zeros((H, W, 3), np.float32), f), T, .35)

def thickness(T, u):
    """cross-section of new clear ice: 4 inches thick (MN DNR minimum for walking), next to a stack of 4 hockey pucks (each 1 in thick)"""
    def f(c):
        c.clear(E.C(8, 14, 20))
        px_in = 115; top = H * .44; bot = top + 4 * px_in
        c.drawRect(skia.Rect.MakeLTRB(0, bot, W, H), E.P(shader=E.linear((0, bot), (0, H), [E.C(15, 55, 70), E.C(4, 14, 20)])))
        grow = eout(clamp(u * 2))
        c.drawRect(skia.Rect.MakeLTRB(-10, bot - 4 * px_in * grow, W * .56, bot), E.P(shader=E.linear((0, top), (0, bot), [E.C(200, 235, 245, 235), E.C(110, 170, 195, 235)])))
        c.drawRect(skia.Rect.MakeLTRB(-10, bot - 4 * px_in * grow, W * .56, bot - 4 * px_in * grow + 10), E.P(E.C(245, 252, 255)))
        for k in range(14):   # trapped bubbles in clear ice
            bx = 40 + (k * 97) % int(W * .5); by = bot - 30 - (k * 53) % int(4 * px_in * grow - 40 + 1)
            c.drawCircle(bx, by, 5 + k % 4, E.P(E.C(255, 255, 255, 120), 'stroke', 2))
        # measure line
        mx = W * .59; a = clamp(u * 2 - .4)
        c.drawLine(mx, bot - 4 * px_in * grow, mx, bot, E.P(E.C(*YEL, 255 * a), 'stroke', 6))
        for yy in (bot - 4 * px_in * grow, bot): c.drawLine(mx - 22, yy, mx + 22, yy, E.P(E.C(*YEL, 255 * a), 'stroke', 6))
        # 4 hockey pucks (1 in thick, 3 in across), dropped in one by one
        for k in range(4):
            pk = clamp(u * 5 - 1.4 - k * .45)
            if pk <= 0: continue
            y1 = bot - (k + 1) * px_in - 300 * (1 - eout(pk)); x0 = W * .64; w = 3 * px_in * .9
            c.drawRoundRect(skia.Rect.MakeXYWH(x0, y1, w, px_in - 6), 18, 18, E.P(E.C(40, 40, 46)))
            c.drawRoundRect(skia.Rect.MakeXYWH(x0, y1, w, px_in - 6), 18, 18, E.P(E.C(170, 175, 185), 'stroke', 4))
            c.drawRoundRect(skia.Rect.MakeXYWH(x0, y1, w, 22), 10, 10, E.P(E.C(60, 60, 68)))
        text(c, 'NEW, CLEAR ICE', W * .28, top - 60, 50, (200, 235, 250), clamp(u * 3))
        text(c, '= 4 HOCKEY PUCKS', W * .78, bot - 4 * px_in - 70, 40, WHITE, clamp(u * 5 - 3.6))
        text(c, 'UNDER THIS: STAY OFF', W / 2, bot + 200, 64, RED, clamp(u * 4 - 2.6))
        text(c, 'GUIDELINE: MINNESOTA DNR', W / 2, H * .955, 32, (160, 175, 190), .9)
    return snow(sk(np.zeros((H, W, 3), np.float32), f), T, .35)

def norway(T, u, zoom=1.0, cx=.5, cy=.5, dusk=0.0):
    """stylized valley outside Narvik, Norway, in May: snowy mountains (layered parallax), a frozen stream winding down to a half-frozen
    waterfall, a dark hole in the stream ice and a pair of skis (illustration, not a map)"""
    def f(c):
        c.save(); c.translate(W / 2, H / 2); c.scale(zoom, zoom); c.translate(-W * cx, -H * cy)
        top = E.linear((0, 0), (0, H * .5), [E.C(70, 92, 120), E.C(160, 175, 190)] if dusk < .5 else [E.C(25, 32, 52), E.C(120, 90, 90)])
        c.drawRect(skia.Rect.MakeLTRB(-W, -H, 2 * W, 2 * H), E.P(shader=top))
        def ridge(base, amp, seed, col, par):
            r = np.random.default_rng(seed); xs = np.linspace(-W * .5, W * 1.5, 14); ys = base - amp * r.random(14)
            pth = skia.Path(); pth.moveTo(-W, H * 2); off = par * u * 80
            for x, y in zip(xs, ys): pth.lineTo(x + off, y)
            pth.lineTo(2 * W, H * 2); pth.close(); c.drawPath(pth, E.P(E.C(*col)))
            # snow caps: lighter strokes on the peaks
        ridge(H * .42, 260, 1, (150, 165, 185), .3); ridge(H * .52, 220, 2, (205, 215, 228), .6); ridge(H * .62, 120, 3, (232, 238, 245), 1.0)
        c.drawRect(skia.Rect.MakeLTRB(-W, H * .6, 2 * W, 2 * H), E.P(E.C(236, 241, 247)))
        # waterfall (half frozen) up the valley
        wx = W * .46; c.drawRect(skia.Rect.MakeXYWH(wx - 40, H * .5, 80, H * .11), E.P(shader=E.linear((0, H * .5), (0, H * .61), [E.C(200, 230, 240), E.C(120, 170, 190)])))
        for k in range(5): c.drawLine(wx - 30 + k * 15, H * .5, wx - 30 + k * 15, H * .5 + H * .11 * (.6 + .4 * math.sin(T * 6 + k)), E.P(E.C(255, 255, 255, 160), 'stroke', 4))
        # the frozen stream: a widening ribbon toward us
        pth = skia.Path(); pth.moveTo(wx - 40, H * .61)
        pth.cubicTo(W * .2, H * .68, W * .8, H * .78, W * .3, H * 1.05); pth.lineTo(W * .85, H * 1.05)
        pth.cubicTo(W * 1.1, H * .78, W * .3, H * .68, wx + 40, H * .61); pth.close()
        c.drawPath(pth, E.P(shader=E.linear((0, H * .61), (0, H), [E.C(120, 165, 185), E.C(70, 120, 145)])))
        c.drawPath(pth, E.P(E.C(250, 252, 255, 180), 'stroke', 5))
        # the hole: dark water with a ragged edge
        hx, hy = W * .52, H * .83
        hole = skia.Path(); r = np.random.default_rng(4)
        for k in range(12):
            a = k / 12 * 2 * math.pi; rr = 70 + 25 * r.random()
            (hole.moveTo if k == 0 else hole.lineTo)(hx + math.cos(a) * rr * 1.5, hy + math.sin(a) * rr * .55)
        hole.close(); c.drawPath(hole, E.P(E.C(6, 18, 26))); c.drawPath(hole, E.P(E.C(240, 250, 255), 'stroke', 6))
        # skis left on the snow
        for k in range(2):
            c.save(); c.translate(W * .78 + k * 34, H * .86); c.rotate(-25 + k * 8)
            c.drawRoundRect(skia.Rect.MakeXYWH(-14, -170, 28, 340), 14, 14, E.P(E.C(200, 40, 35))); c.restore()
        # pines on the slopes
        for k in range(14):
            x = (k * 173) % int(W * 1.2) - W * .1; y = H * (.6 + .02 * (k % 4)); s = .6 + .3 * (k % 3)
            if abs(x - W * .5) < 160: continue
            p2 = skia.Path(); p2.moveTo(x, y - 160 * s); p2.lineTo(x - 50 * s, y); p2.lineTo(x + 50 * s, y); p2.close(); c.drawPath(p2, E.P(E.C(20, 50, 45)))
            c.drawCircle(x, y - 120 * s, 14 * s, E.P(E.C(240, 245, 250, 200)))
        c.restore()
    img = sk(np.zeros((H, W, 3), np.float32), f)
    return snow(img * VIGM * .72, T, .7, vy=40)

def air_pocket(T, u):
    """under the stream ice: a silvery air pocket trapped against the ice (seen from below, air looks like a mirror), bubbles rising into it"""
    img = kb('under_empty', u, 1.25, 1.4, (.5, .45), (.5, .43))
    def f(c):
        x, y = W * .5, H * .3
        for k, (rx, ry, a) in enumerate(((300, 46, 220), (260, 34, 160))):
            c.drawOval(skia.Rect.MakeLTRB(x - rx, y - ry, x + rx, y + ry), E.P(shader=E.linear((0, y - ry), (0, y + ry), [E.C(250, 252, 255, a), E.C(150, 190, 205, a)])))
        c.drawOval(skia.Rect.MakeLTRB(x - 300, y - 46, x + 300, y + 46), E.P(E.C(255, 255, 255, 230), 'stroke', 4))
        c.drawOval(skia.Rect.MakeLTRB(x - 160, y - 30, x + 40, y - 8), E.P(E.C(255, 255, 255, 140), blur=8))
        E.glow(c, x, y, 300, (190, 230, 255), .35)
    return bubbles(sk(img, f), T, .5, .25, .9)

def ecg(T, u, flat=0.0, restart=0.0, label=None):
    """heart monitor trace: beats, goes flat (flat 0..1), comes back (restart 0..1)"""
    def f(c):
        c.clear(E.C(4, 10, 10))
        for k in range(0, W, 60): c.drawLine(k, H * .3, k, H * .7, E.P(E.C(20, 60, 45), 'stroke', 2))
        for k in range(int(H * .3), int(H * .7), 60): c.drawLine(0, k, W, k, E.P(E.C(20, 60, 45), 'stroke', 2))
        pth = skia.Path(); y0 = H * .5; first = True
        for xpx in range(0, W, 4):
            tt = T * 1.1 - (W - xpx) / W * 2.2
            beat = (tt % .9)
            v = 0
            amp = 1.0 if (flat <= 0 or xpx < W * (1 - flat)) else 0.0
            if restart > 0 and xpx > W * (1 - restart): amp = 1.0
            if beat < .06: v = -260 * math.sin(beat / .06 * math.pi)
            elif beat < .12: v = 80 * math.sin((beat - .06) / .06 * math.pi)
            elif .3 < beat < .45: v = -50 * math.sin((beat - .3) / .15 * math.pi)
            y = y0 + v * amp
            (pth.moveTo if first else pth.lineTo)(xpx, y); first = False
        c.drawPath(pth, E.P(E.C(60, 255, 140, 120), 'stroke', 14, blur=10, add=True)); c.drawPath(pth, E.P(E.C(150, 255, 190), 'stroke', 5))
        if label: text(c, label[0], W / 2, H * .24, 74, label[1])
    return sk(np.zeros((H, W, 3), np.float32), f)

def thermo(T, u):
    """body temperature falling from a normal 37 C (98.6 F) to 13.7 C (56.7 F)"""
    v = 37 - (37 - 13.7) * eout(clamp(u))
    def f(c):
        c.clear(E.C(8, 14, 22))
        x = W * .32; top = H * .12; bot = H * .5
        def yv(tc): return bot - (tc - 0) / 40 * (bot - top)
        c.drawRoundRect(skia.Rect.MakeLTRB(x - 46, top - 30, x + 46, bot + 40), 46, 46, E.P(E.C(210, 225, 235, 60)))
        c.drawCircle(x, bot + 70, 90, E.P(E.C(255, 90, 70) if v > 25 else E.C(90, 180, 255)))
        col = (255, 90, 70) if v > 25 else (90, 180, 255)
        c.drawRect(skia.Rect.MakeLTRB(x - 26, yv(v), x + 26, bot + 40), E.P(E.C(*col)))
        for tc in range(0, 41, 5):
            c.drawLine(x + 60, yv(tc), x + 100, yv(tc), E.P(E.C(200, 210, 220), 'stroke', 4)); text(c, f'{tc}', x + 150, yv(tc) + 14, 40, (200, 210, 220))
        c.drawLine(x - 70, yv(37), W * .9, yv(37), E.P(E.C(150, 230, 160, 200), 'stroke', 4))
        text(c, 'NORMAL 37°C (98.6°F)', W * .7, yv(37) - 20, 40, (150, 230, 160))
        text(c, f'{v:.1f}°C', W * .68, H * .34, 120, col)
        if u > .95: text(c, '(56.7°F)', W * .68, H * .34 + 75, 56, col)
        text(c, '°C', x + 150, top - 40, 40, (200, 210, 220))
    return sk(np.zeros((H, W, 3), np.float32), f)

def bypass(T, u):
    """heart-lung (bypass) machine loop: cold blood out of the body -> machine adds oxygen and warms it -> back into the body (simplified)"""
    def f(c):
        c.clear(E.C(8, 12, 16)); c.translate(W / 2, H * .5); c.scale(1.35, 1.35); c.translate(-W / 2, -H * .5)
        bx, by = W * .3, H * .5; mx, my = W * .72, H * .5
        c.drawRoundRect(skia.Rect.MakeXYWH(bx - 150, by - 260, 300, 520), 140, 140, E.P(E.C(40, 70, 100)))
        text(c, 'BODY', bx, by + 20, 60, (200, 225, 255))
        c.drawRoundRect(skia.Rect.MakeXYWH(mx - 140, my - 170, 280, 340), 30, 30, E.P(E.C(90, 95, 105)))
        for k in range(2):
            cx = mx - 60 + k * 120; c.drawCircle(cx, my - 60, 46, E.P(E.C(40, 42, 48)))
            a = T * 6 + k; c.drawLine(cx, my - 60, cx + 40 * math.cos(a), my - 60 + 40 * math.sin(a), E.P(E.C(220, 220, 225), 'stroke', 10))
        text(c, 'HEART-LUNG', mx, my + 60, 44, WHITE); text(c, 'MACHINE', mx, my + 110, 44, WHITE)
        # loop: out the top (cold, blue) and back the bottom (warm, red)
        def flow(y, x0, x1, col):
            c.drawLine(x0, y, x1, y, E.P(E.C(*col, 200), 'stroke', 26))
            for k in range(6):
                p = ((T * .6 + k / 6) % 1); xx = x0 + (x1 - x0) * p
                c.drawCircle(xx, y, 12, E.P(E.C(255, 255, 255, 200)))
        flow(by - 200, bx + 150, mx - 140, (80, 150, 255)); flow(by + 200, mx - 140, bx + 150, (255, 80, 60))
        c.drawLine(mx - 140, by - 200, mx - 140, by - 170, E.P(E.C(80, 150, 255), 'stroke', 26))
        c.drawLine(mx - 140, by + 200, mx - 140, by + 170, E.P(E.C(255, 80, 60), 'stroke', 26))
        text(c, 'COLD BLOOD OUT', W / 2, by - 240, 44, (140, 190, 255), clamp(u * 3))
        text(c, 'WARMED + OXYGEN', W / 2, by + 270, 44, (255, 150, 120), clamp(u * 3 - 1))
        text(c, 'SIMPLIFIED', W / 2, H * .78, 24, (150, 160, 170), .8)
    return sk(np.zeros((H, W, 3), np.float32), f)

# ---------------------------------------------------------------- scenes
def S0(t, T):   # HOOK: Leo crashes through the ice (splash, shake, flash), then the close-up gasp
    if t < 1.0:
        img = kb('hole_leo', t / 1.0, 1.75, 1.5, (.5, .48), (.5, .48))
        img = (img - 110) * 1.2 + 110
        img = splash(img, t + .12, .5, .56, 1.0)
        return snow(shake(flash(img, t + .3, 90, 6), t, 22, 2.5), T, .8)
    u = t - 1.0
    return whip(breath(snow(shake(kb('hole_cu', u / 1.6, 1.05, 1.15, (.5, .42), (.5, .4)), u, 8, 4), T, .8), T, .55, .47, .9, True), u)

def S1(t, T):
    c = 1.7
    if t < c: return snow(kb('pond_wide', t / c, 1.0, 1.12, (.5, .55), (.45, .52)), T, 1.0)
    return whip(snow(kb('pond_leo', (t - c) / 2.5, 1.0, 1.1, (.5, .55), (.5, .5)), T, 1.0), t - c)

def S2(t, T): return shake(ptalk('cu_mia_bank', t, t / (D + PAD), 1.02, 1.12, (.5, .48), (.5, .45), .01), t, 6, 2)

def S3(t, T):   # crack -> the drop -> under the ice
    c = wt('Then') - .1
    if t < c:
        img = kb('pond_leo', t / c, 1.1, 1.22, (.5, .62), (.5, .6))
        return snow(shake(cracks(img, clamp(t / (c * .8)), .5, .74, 1.0, 1.6), t, 6, 1), T, .8)
    u = t - c
    img = kb('under_ice', u / 2, 1.0, 1.14, (.5, .45), (.5, .4))
    img = rays(img, T, .5, .36, 1.0); img = bubbles(img, T + 3, .5, .2, 1.0)
    return whip(flash(img, u, 120, 8), u, vertical=True)

def S4(t, T):   # cold shock: gasping breath
    c = wt('gasp') - .15
    if t < c: return snow(rays(bubbles(kb('under_ice', t / c, 1.14, 1.22, (.5, .4), (.5, .38)), T, .5, .2, .8), T, .5, .36, .8), T, 0)
    u = t - c
    img = shiver(kb('hole_cu', u / 3, 1.0, 1.12, (.5, .42), (.5, .4)), T, 3)
    return whip(snow(breath(img, T, .55, .47, 1.0, True), T, .9), u)

def S5(t, T): return shake(ptalk('cu_kai_bank', t, t / (D + PAD), 1.0, 1.1, (.5, .48), (.5, .45), .01), t, 5, 2)

def S6(t, T):
    c = wt('one,') - .15
    return one_ten_one(T, 3 * clamp((t - c) / 1.6) if t > c else 0, 'hole_leo', t / (D + PAD))

def S7(t, T):
    a1, a2, a3 = wt('One'), wt('Ten'), wt('About')
    act = 0 if t < a1 else (1 if t < a2 else (2 if t < a3 else 3))
    base = ['hole_cu', 'hole_cu', 'leo_climb', 'under_empty'][act]
    img = one_ten_one(T, act if act < 3 else 3, base, t / (D + PAD))
    return whip(img, t - [0, a1, a2, a3][act])

def S8(t, T):
    c = wt('That') - .1
    if t < c: return shake(ptalk('cu_mia_bank', t, t / c, 1.08, 1.16, (.5, .45), (.5, .44), .01), t, 4, 2)
    u = t - c
    img = kb('hole_leo', u / 2, 1.05, 1.15, (.5, .55), (.5, .58))
    def f(cn):   # dotted path: the footsteps he came on, back toward the bank
        for k in range(9):
            p = k / 8; yy = H * (.56 + .38 * p); xx = W * (.5 + .05 * math.sin(p * 3))
            cn.drawCircle(xx, yy, 10 + 10 * p, E.P(E.C(*YEL, 255 * clamp(u * 3 - p))))
        E.arrow(cn, W * .5, H * .62, W * .52, H * .9, 16, YEL, clamp(u * 2))
    return whip(snow(sk(img, f), T, .8), u)

def S9(t, T):
    c = wt('Kick') - .15
    if t < c: return snow(kb('leo_climb', t / c, 1.05, 1.15, (.5, .5), (.48, .5)), T, .8)
    return whip(self_rescue(T, .35 * clamp((t - c) / 1.6) + .1), t - c)

def S10(t, T):
    c = wt('Roll') - .15
    if t < c: return self_rescue(T, .45 + .45 * clamp(t / c), kick=False)
    u = t - c
    img = kb('leo_roll', u / 2, 1.0, 1.1, (.55, .55), (.45, .55), rot=-6 * math.sin(u * 4))
    return whip(snow(img, T, .8), u)

def S11(t, T):
    img = shiver(kb('bank_group', t / (D + PAD), 1.0, 1.12, (.5, .5), (.47, .5)), T, 2)
    return snow(breath(img, T, .38, .53, .8, True), T, 1.0)

def S12(t, T): return ptalk('cu_leo_ask', t, t / (D + PAD), 1.02, 1.1, (.5, .45), (.5, .43), .01)

def S13(t, T):
    c = wt('inches') - .5
    if t < c: return ptalk('cu_mia_serious', t, t / c, 1.04, 1.12, (.5, .45), (.5, .43))
    return whip(thickness(T, clamp((t - c) / 2.4)), t - c)

def S14(t, T):
    c = wt('under') - .2
    if t < c: return ptalk('cu_leo_ask', t, t / c, 1.12, 1.2, (.5, .44), (.5, .42), .01)
    u = t - c
    return whip(rays(bubbles(kb('under_empty', u / 2, 1.0, 1.12), T, .5, .3, .6), T, .5, .36, .7), u, vertical=True)

def S15(t, T): return ptalk('cu_mia_serious', t, t / (D + PAD), 1.12, 1.28, (.5, .44), (.5, .42), .006)

def S16(t, T):   # Norway, May 1999
    c1 = wt('Skier') - .1; c2 = wt('fell') - .1
    if t < c1: return norway(T, t / c1, 1.0, .5, .5)
    if t < c2: return whip(norway(T, (t - c1) / 2, 1.0 + .5 * ease((t - c1) / 2.5), .5, .62), t - c1)
    u = t - c2
    img = norway(T, 1, 2.2 + .4 * ease(u / 2), .52, .82)
    return whip(splash(img, u, .5, .5, 1.0), u)

def S17(t, T):
    c = wt('Then') - .1
    if t < c: return air_pocket(T, t / c)
    u = t - c
    return whip(ecg(T, u, flat=clamp(u / .8)), u)

def S18(t, T):
    img = norway(T, 1, 1.6 + .2 * ease(t / (D + PAD)), .52, .74, dusk=1.0)
    def f(cn):   # rescuers' torch beams sweeping across the hole
        for k in range(2):
            a = math.sin(T * 1.3 + k * 2) * .3; x0 = W * (.2 + .6 * k)
            pth = skia.Path(); pth.moveTo(x0, H * .45); pth.lineTo(W * .5 + math.sin(a) * 300 - 120, H * .8); pth.lineTo(W * .5 + math.sin(a) * 300 + 120, H * .8); pth.close()
            cn.drawPath(pth, E.P(E.C(255, 230, 170, 60), blur=20, add=True))
    return sk(img, f)

def S19(t, T):
    c = wt('Normal') - .1
    return thermo(T, clamp((t - .3) / max(.5, c - .4)))

def S20(t, T):
    c = wt('warming') - .1
    if t < c:
        img = kb('hospital', t / c, 1.0, 1.12, (.5, .5), (.55, .48))
        def f(cn): E.glow(cn, W * .62, H * .42, 220, (255, 170, 90), .35 + .1 * math.sin(T * 5))
        return sk(img, f)
    return whip(bypass(T, clamp((t - c) / 2)), t - c)

def S21(t, T):
    c = wt('became') - .1
    if t < c: return ecg(T, 1, flat=1.0, restart=clamp(t / max(.6, c - .2)), label=('HEARTBEAT BACK', (150, 255, 190)))
    u = t - c
    img = grade(kb('hospital', u / 3, 1.1, 1.2, (.45, .48), (.42, .47)), (1.0, 1.06, 1.15), 6)
    return whip(img, u)

def S22(t, T):
    c = wt('taking') - .2
    img = kb('long_way', t / (D + PAD), 1.02, 1.1, (.5, .5), (.47, .5))
    img = shift(img, 0, 6 * abs(math.sin(T * 6)))   # walking bob
    return snow(img, T, 1.0)

def S23(t, T):
    c = (D + PAD) - 1.0
    if t < c * .45: return snow(kb('long_way', t / c, 1.1, 1.18, (.5, .5), (.44, .5)), T, 1.0)
    if t < c:
        u = (t - c * .45) / (c * .55)
        img = kb('pond_leo', u, 1.1, 1.22, (.5, .62), (.5, .6))
        return whip(snow(cracks(img, clamp(u * 1.2), .5, .74, 1.0, 1.6), T, .8), t - c * .45)
    img = (kb('hole_leo', 0, 1.75, 1.75, (.5, .48), (.5, .48)) - 110) * 1.2 + 110   # loop: the first frame again
    return whip(snow(splash(img, .12, .5, .56, 1.0), T, .8), t - c, vertical=True)

# ---------------------------------------------------------------- overlays
def overlays():
    o = []
    if idx == 0: o += [{'type': 'hook', 'text': 'HE FELL THROUGH|THE ICE', 'y': .11}]
    if idx == 1: o += [{'type': 'datestamp', 'text': 'DECEMBER · A FROZEN POND', 'y': .08, 'from': .1}]
    if idx == 3: o += [{'type': 'label', 'text': 'CRACK', 'pos': [.5, .14], 'color': WHITE, 'from': .3}]
    if idx == 4: o += [{'type': 'label', 'text': 'COLD SHOCK', 'pos': [.5, .12], 'color': BLUE, 'from': wt('cold') - .1},
                       {'type': 'label', 'text': 'GASPING · FAST BREATHING', 'pos': [.5, .17], 'color': WHITE, 'from': wt('gasp') - .1}]
    if idx == 6: o += [{'type': 'label', 'text': 'THE 1-10-1 RULE', 'pos': [.5, .1], 'color': YEL, 'from': .2},
                       {'type': 'label', 'text': 'TAUGHT BY DR. GORDON GIESBRECHT', 'pos': [.5, .15], 'color': WHITE, 'from': .5}]
    if idx == 8: o += [{'type': 'label', 'text': 'GO BACK THE WAY YOU CAME', 'pos': [.5, .12], 'color': YEL, 'from': wt('That') - .1}]
    if idx == 10: o += [{'type': 'label', 'text': "DON'T STAND · ROLL AWAY", 'pos': [.5, .12], 'color': YEL, 'from': wt('Roll') - .1}]
    if idx == 13: o += [{'type': 'badge', 'value': '4 IN', 'unit': 'MINIMUM FOR WALKING', 'pos': [.5, .12], 'from': wt('inches') - .1}]
    if idx == 15: o += [{'type': 'badge', 'value': '80', 'unit': 'MINUTES', 'pos': [.5, .12], 'from': wt('eighty') - .1}]
    if idx == 16: o += [{'type': 'datestamp', 'text': 'NEAR NARVIK, NORWAY · MAY 20, 1999', 'y': .08, 'from': .2},
                        {'type': 'label', 'text': 'ANNA BÅGENHOLM, 29', 'pos': [.5, .175], 'color': YEL, 'from': wt('Skier') - .1}]
    if idx == 17: o += [{'type': 'label', 'text': 'AIR POCKET', 'pos': [.5, .12], 'color': WHITE, 'from': wt('air') - .1},
                        {'type': 'badge', 'value': '~40', 'unit': 'MINUTES CONSCIOUS', 'pos': [.5, .2], 'from': wt('forty') - .1, 'size': 64}]
    if idx == 18: o += [{'type': 'badge', 'value': '80 MIN', 'unit': 'IN ICE WATER', 'pos': [.5, .12], 'from': wt('eighty') - .1, 'size': 70},
                        {'type': 'label', 'text': '≈ ALMOST A FULL SOCCER MATCH', 'pos': [.5, .2], 'color': WHITE, 'from': wt('eighty') + .3}]
    if idx == 19: o += [{'type': 'label', 'text': 'ONE OF THE LOWEST EVER SURVIVED', 'pos': [.5, .085], 'color': YEL, 'from': wt('Normal') + .2}]
    if idx == 20: o += [{'type': 'badge', 'value': '100+', 'unit': 'DOCTORS + NURSES', 'pos': [.3, .1], 'from': wt('hundred') - .1, 'size': 64},
                        {'type': 'badge', 'value': '9', 'unit': 'HOURS', 'pos': [.74, .1], 'from': wt('nine') - .1, 'size': 64}]
    if idx == 21: o += [{'type': 'label', 'text': 'TROMSØ UNIVERSITY HOSPITAL', 'pos': [.5, .12], 'color': WHITE, 'from': wt('became') - .1},
                        {'type': 'label', 'text': 'LATER: RADIOLOGIST THERE', 'pos': [.5, .17], 'color': YEL, 'from': wt('radiologist') - .1}]
    if idx == 23: o += [{'type': 'cta', 'text': 'FOLLOW FOR MORE STORIES', 'from': .2}]
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
