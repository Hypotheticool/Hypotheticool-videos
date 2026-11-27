"""Animate every scene of "Their Christmas tree went up in seconds" over its Cycles plates (xtree_plate.py):
2D camera moves and cuts, procedural flames / smoke / sparks, and the science graphics.
python3 xtree_anim.py <scene> [still_times...]  ->  xtree/s<scene>/f_####.png + meta.json (overlays read by compose.py)"""
import sys, math, json, os
sys.path.insert(0, '/home/claude/pro')
import numpy as np, cv2, skia
import engine as E
ROOT = '/home/claude/b3d/xtree'; CFG = json.load(open(f'{ROOT}/topic.json'))
FPS = 24; PAD = .75; XF = .35
idx = int(sys.argv[1]); D = CFG['durs'][idx]; NF = int(math.ceil((D + PAD) * FPS))
T0 = sum(CFG['durs'][:idx])
W, H = 1080, 1920
ease = lambda t: .5 - .5 * math.cos(math.pi * min(max(t, 0), 1))
eout = lambda t: 1 - (1 - min(max(t, 0), 1)) ** 3
clamp = lambda v, a=0., b=1.: max(a, min(b, v))
YEL, WHITE, BLUE, RED, GREEN, GREY, ORANGE = (255, 222, 40), (255, 255, 255), (130, 200, 255), (255, 95, 80), (120, 235, 150), (170, 178, 190), (255, 150, 50)

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
FIREPL = {'hook', 'fire', 'wide', 'cu_kai'}
def plate(name):
    """load a plate, upscale, grade into the palette (deep navy shadows, warm highlights); fire plates get crushed blacks + hot orange"""
    if name not in PL:
        im = cv2.imread(f'{ROOT}/plates/{name}.png', cv2.IMREAD_COLOR)
        if im.shape[1] != W: im = cv2.resize(im, (W, H), interpolation=cv2.INTER_CUBIC)
        im = im.astype(np.float32); lum = im.mean(2, keepdims=True) / 255
        if name in FIREPL:
            im = 255 * (im / 255) ** 1.7 * np.float32([.55, .85, 1.25])        # contrast up, push to orange
        im = im * .92 + (1 - lum) * np.float32([22, 8, 0]) - 2
        im = im * (.92 + .1 * lum) * VIGM
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
    cx = (c0[0] + (c1[0] - c0[0]) * t) * W; cy = (c0[1] + (c1[1] - c0[1]) * t) * H
    M = cv2.getRotationMatrix2D((cx, cy), rot, z); M[0, 2] += W / 2 - cx; M[1, 2] += H / 2 - cy; LASTM[0] = (M, z)
    return cv2.warpAffine(im, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
def sp(name, key):
    """plate point -> screen point under the last kb() transform"""
    M, z = LASTM[0]; x, y = pts(name)[key]; return M[0, 0] * x + M[0, 1] * y + M[0, 2], M[1, 0] * x + M[1, 1] * y + M[1, 2], z

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
def flash(img, t, k=220, decay=7, col=(1, 1, 1)): return img + k * math.exp(-max(t, 0) * decay) * np.float32(col)
def blur(img, s): return cv2.GaussianBlur(img, (0, 0), s) if s > .3 else img
def darken(img, k): return img * (1 - k)
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
def panel(c, x, y, w, h, a=1.0):
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, y, w, h), 34, 34), E.P(E.C(12, 18, 28, 225 * a)))
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, y, w, h), 34, 34), E.P(E.C(120, 150, 180, 120 * a), 'stroke', 3))

# ---------------------------------------------------------------- fire, smoke, sparks (procedural 2D)
FR = np.random.default_rng(11).random((420, 6))
S4_ = 4   # fire layer is drawn at 1/4 res and blurred up
def flames(img, T, base, top, width, k=1.0, tongues=1.0, flicker=True, n=420):
    """a fire filling a cone from base (x, y) up to top_y, `width` px wide at the bottom; k = size/intensity 0..1+.
    Built from many small, vertically stretched tongues (yellow core -> orange -> deep red tips), then licked by a moving warp."""
    if k <= 0: return img
    w4, h4 = W // S4_, H // S4_; lay = np.zeros((h4, w4, 3), np.float32)
    bx, by = base; ht = (by - top) * (.35 + .65 * min(k, 1.3))
    for x0, ph, sz, sp_, wob, hue in FR[:int(n * min(1, .35 + .65 * k))]:
        age = (T * (1.1 + 1.6 * sp_) + ph) % 1.0
        side = (x0 - .5) * 2; h0 = hue * .7 * min(1, k)          # tongues start all over the burning cone, not just at its base
        lv = min(1.0, h0 + age * (.3 + .35 * sz) * tongues)
        yy = by - lv * ht
        narrow = (1 - lv) ** 1.0
        xx = bx + side * width * .5 * narrow + math.sin(T * 7 + ph * 20) * 22 * wob * age
        r = (7 + 22 * sz) * math.sin(math.pi * min(.98, .12 + age)) ** .6 * (.7 + .4 * min(k, 1.3)) * (width / 500) ** .5
        if age < .25: colr = (60, 200, 255)          # BGR: yellow core
        elif age < .6: colr = (25, 115, 255)         # orange
        else: colr = (20, 40, 190)                   # deep red tips
        a = (1.0 - .6 * age) * min(1, k * 1.5) * .55
        cv2.ellipse(lay, (int(xx / S4_), int(yy / S4_)), (max(1, int(r * .55 / S4_)), max(1, int(r * 1.9 / S4_))), 0, 0, 360,
                    tuple(v * a for v in colr), -1, cv2.LINE_AA)
    lay = cv2.GaussianBlur(lay, (0, 0), 1.3)
    lay = cv2.resize(lay, (W, H), interpolation=cv2.INTER_LINEAR)
    wx = (np.sin(YY / 37 - T * 14) * 9 + np.sin(YY / 13 - T * 23) * 4).astype(np.float32)
    lay = cv2.remap(lay, XX + wx, YY + (np.sin(XX / 29 + T * 9) * 6).astype(np.float32), cv2.INTER_LINEAR)
    lay = 255 * (1 - np.exp(-lay / 150))                     # soft tone-map: hot but not blown to flat white
    glow = cv2.GaussianBlur(cv2.resize(lay, (W // 8, H // 8)), (0, 0), 6); glow = cv2.resize(glow, (W, H)) * .8
    fl = 1 + (.07 * math.sin(T * 23) + .05 * math.sin(T * 37 + 1)) if flicker else 1
    return img * fl * (1 - lay / 255 * .6) + glow * np.float32([.45, .75, 1.0]) + lay
def ceiling_roll(img, T, y, x0, x1, k=1.0):
    """flashover roll-over: a sheet of flame racing along under the ceiling"""
    if k <= 0: return img
    w4, h4 = W // S4_, H // S4_; lay = np.zeros((h4, w4, 3), np.float32); span = (x1 - x0) * min(1, k)
    for x_, ph, sz, sp_, wob, hue in FR[:300]:
        age = (T * (.9 + 1.2 * sp_) + ph) % 1.0
        xx = x0 + x_ * span + age * 120; yy = y + (sz - .3) * 140 + math.sin(T * 5 + ph * 30) * 25
        r = (14 + 30 * sz) * math.sin(math.pi * min(.98, .1 + age)) ** .6
        colr = (60, 200, 255) if age < .3 else ((25, 115, 255) if age < .65 else (20, 40, 190))
        cv2.ellipse(lay, (int(xx / S4_), int(yy / S4_)), (max(1, int(r * 2.2 / S4_)), max(1, int(r * .7 / S4_))), 0, 0, 360, tuple(v * .5 for v in colr), -1, cv2.LINE_AA)
    lay = cv2.resize(cv2.GaussianBlur(lay, (0, 0), 1.4), (W, H))
    lay = cv2.remap(lay, XX + (np.sin(YY / 21 - T * 12) * 14).astype(np.float32), YY + (np.sin(XX / 17 + T * 15) * 10).astype(np.float32), cv2.INTER_LINEAR)
    lay = 255 * (1 - np.exp(-lay / 150))
    glow = cv2.resize(cv2.GaussianBlur(cv2.resize(lay, (W // 8, H // 8)), (0, 0), 6), (W, H)) * .8
    return img * (1 - lay / 255 * .6) + glow * np.float32([.45, .75, 1.0]) + lay
def sparks(img, T, base, spread=300, k=1.0, n=60):
    if k <= 0: return img
    lay = np.zeros_like(img); bx, by = base
    for x0, ph, sz, sp_, wob, hue in FR[:n]:
        age = (T * (.5 + .8 * sp_) + ph) % 1.0
        x = bx + (x0 - .5) * spread + math.sin(T * 3 + ph * 9) * 60 * age; y = by - age * (500 + 600 * sz)
        v = (1 - age) * k
        cv2.circle(lay, (int(x), int(y)), 2 + int(3 * sz), (80 * v, 200 * v, 255 * v), -1, cv2.LINE_AA)
    return img + cv2.GaussianBlur(lay, (0, 0), 1.5) * 1.5
NZ = cv2.resize(cv2.GaussianBlur(np.random.default_rng(3).random((96, 64)).astype(np.float32), (0, 0), 2.5), (W, H * 2), interpolation=cv2.INTER_CUBIC)
NZ = (NZ - NZ.min()) / (NZ.max() - NZ.min())
def ceiling_smoke(img, T, depth, k=1.0, col=(28, 26, 26)):
    """a thick smoke layer banking down from the top of the frame to `depth` (fraction of H), churning"""
    if k <= 0 or depth <= 0: return img
    off = int(T * 60) % H; n = NZ[off:off + H][..., None]
    edge = depth * H + (n[..., 0] - .5) * 260
    a = np.clip((edge - YY) / 220, 0, 1)[..., None] * (.55 + .45 * n) * min(1, k)
    return img * (1 - a * .92) + np.float32(col) * a * .92
def smoke_puffs(img, T, base, k=1.0, spread=1.0, up=1.0, col=(40, 38, 38), n=40, size=1.0):
    """billowing dark smoke rising from base"""
    if k <= 0: return img
    lay = np.zeros((H // 4, W // 4), np.float32); colr = np.zeros((H // 4, W // 4, 3), np.float32)
    for x0, ph, sz, sp_, wob, hue in FR[100:100 + n]:
        age = (T * (.25 + .25 * sp_) + ph) % 1
        px = base[0] + (x0 - .5) * 260 * spread * (.4 + age) + math.sin(T + ph * 7) * 40; py = base[1] - 1100 * age * up
        r = (60 + 260 * age) * (.6 + .6 * sz) * spread * size
        cv2.circle(lay, (int(px / 4), int(py / 4)), max(1, int(r / 4)), .55 * (1 - age ** 2) * min(1, age * 6), -1, cv2.LINE_AA)
    lay = cv2.resize(cv2.GaussianBlur(lay, (0, 0), 6), (W, H))[..., None] * k
    lay = np.clip(lay, 0, .95)
    return img * (1 - lay) + np.float32(col) * lay
def heat_shimmer(img, T, k=1.0):
    if k <= 0: return img
    dx = (np.sin(YY / 23 + T * 9) * 3.5 * k).astype(np.float32); dy = (np.cos(XX / 31 + T * 7) * 2.0 * k).astype(np.float32)
    return cv2.remap(img, XX + dx, YY + dy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
def ember_grade(img, T, k=1.0):
    """orange fire-light flicker over a whole frame"""
    f = 1 + .08 * k * math.sin(T * 19) + .05 * k * math.sin(T * 31 + 2)
    return img * np.float32([1 - .25 * k, 1 - .05 * k, 1 + .25 * k]) * f
def tree_fire(name, T, u, z0, z1, c0=(.5, .5), c1=(.5, .5), k=1.0, smoke=0.4, sm_depth=.25, spark=1.0):
    img = kb(name, u, z0, z1, c0, c1)
    bx, by, z = sp(name, 'tree_base'); tx, ty, _ = sp(name, 'tree_top'); lx, ly, _ = sp(name, 'tree_l'); rx, ry, _ = sp(name, 'tree_r')
    wd = abs(rx - lx) * 1.15
    img = ceiling_smoke(img, T, sm_depth, smoke)
    img = flames(img, T, (bx, by - 30 * z), ty - 220 * z, wd, k)
    img = sparks(img, T, (bx, (by + ty) / 2), wd * .9, spark * min(1, k))
    return heat_shimmer(img, T, .6 * min(1, k))

# ---------------------------------------------------------------- 2D graphics
def stopwatch(c, x, y, r, secs, a=1.0, maxs=60):
    c.drawCircle(x, y, r, E.P(E.C(14, 20, 30, 235 * a))); c.drawCircle(x, y, r, E.P(E.C(*WHITE, 255 * a), 'stroke', 10))
    c.drawRect(skia.Rect.MakeXYWH(x - 22, y - r - 46, 44, 40), E.P(E.C(*WHITE, 255 * a)))
    for k in range(12):
        ang = math.radians(k * 30); c.drawLine(x + math.sin(ang) * r * .82, y - math.cos(ang) * r * .82, x + math.sin(ang) * r * .93, y - math.cos(ang) * r * .93, E.P(E.C(*WHITE, 200 * a), 'stroke', 5))
    pth = skia.Path(); pth.moveTo(x, y); pth.arcTo(skia.Rect.MakeLTRB(x - r * .78, y - r * .78, x + r * .78, y + r * .78), -90, 360 * min(secs, maxs) / maxs, False); pth.close()
    c.drawPath(pth, E.P(E.C(*ORANGE, 150 * a)))
    ang = math.radians(360 * secs / maxs); c.drawLine(x, y, x + math.sin(ang) * r * .8, y - math.cos(ang) * r * .8, E.P(E.C(*RED, 255 * a), 'stroke', 9))
    text(c, f'{int(secs)} s', x, y + r + 90, 84, YEL, a)
def tree_icon(c, x, y, s, col, a=1.0):
    pth = skia.Path(); pth.moveTo(x, y - 70 * s); pth.lineTo(x + 45 * s, y + 40 * s); pth.lineTo(x - 45 * s, y + 40 * s); pth.close()
    c.drawPath(pth, E.P(E.C(*col, 255 * a))); c.drawRect(skia.Rect.MakeXYWH(x - 8 * s, y + 40 * s, 16 * s, 22 * s), E.P(E.C(120, 80, 50, 255 * a)))
def two_in_five(T, u):
    img = blur(kb('bulb', .5 + .5 * u, 1.15, 1.2), 8) * .35
    def f(c):
        c.translate(0, -220); panel(c, 80, 560, 920, 700, eout(u * 3))
        for k in range(5):
            on = k < 2; g = eout(clamp(u * 3 - .3 - k * .15))
            tree_icon(c, 220 + k * 160, 800, 1.3 * (.6 + .4 * g), (255, 140, 40) if on else (70, 120, 90), g)
            if on and g > .5: E.glow(c, 220 + k * 160, 790, 120, (255, 120, 30), .5 * g)
        text(c, 'MORE THAN 2 IN 5', 540, 1010, 90, YEL, eout(clamp(u * 3 - 1)))
        text(c, 'home Christmas tree fires', 540, 1090, 50, WHITE, eout(clamp(u * 3 - 1.2)))
        text(c, 'involve lights or wiring (NFPA)', 540, 1160, 50, WHITE, eout(clamp(u * 3 - 1.4)))
    return sk(img, f)
def thermo(T, u):
    img = blur(tree_fire('wide', T, .3, 1.25, 1.3, (.5, .35), (.5, .33), 1.2, 1.0, .45), 7) * .35
    def f(c):
        c.translate(0, -220); panel(c, 90, 560, 900, 780, eout(u * 3))
        g = eout(clamp(u * 1.6)); g2 = eout(clamp(u * 1.6 - .5))
        base = 1210; top = 700; hmax = base - top
        for k, (lab, val, col, gg) in enumerate([('ROOM FIRE', 1000, RED, g), ('KITCHEN OVEN', 500, ORANGE, g2)]):
            x = 360 + k * 360; hh = hmax * val / 1000 * gg
            c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeLTRB(x - 70, base - hh, x + 70, base), 18, 18), E.P(E.C(*col, 240)))
            v_ = int(round(val * gg / 10) * 10); s_ = (f'{v_:,}°F+' if gg > .99 else f'{v_:,}°F') if k == 0 else f'~{v_}°F'
            text(c, s_, x, base - hh - 30, 64, WHITE, clamp(gg * 2))
            text(c, lab, x, base + 70, 44, GREY, clamp(gg * 2))
        text(c, '2×', 540, 950, 120, YEL, eout(clamp(u * 2.5 - 1.6)))
    return sk(img, f)
def escape_bars(T, u, phase):
    """17 minutes (UL tests, ~30 years ago) vs ~3 minutes today"""
    bg = kb('calm', .2, 1.1, 1.1) if phase == 0 else tree_fire('fire', T, .5, 1.05, 1.08, k=1.0, smoke=.8, sm_depth=.3)
    img = blur(bg, 7) * .35
    def f(c):
        c.translate(0, -220); panel(c, 70, 560, 940, 760)
        g = eout(clamp(u * 1.8)) if phase == 0 else 1.0; x0 = 140; full = 800
        text(c, 'TIME TO ESCAPE A HOUSE FIRE', 540, 650, 52, WHITE)
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x0, 740, full * g, 120), 24, 24), E.P(E.C(*BLUE, 235)))
        text(c, '~30 YEARS AGO', x0 + 10, 720, 40, GREY, 1, False); text(c, f'{int(round(17 * g))} MIN', x0 + full * g - 110, 825, 62, WHITE, clamp(g * 3))
        if phase == 1:
            g2 = eout(clamp(u * 2.2)); w2 = full * (17 - 14 * g2) / 17
            c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x0, 1000, w2, 120), 24, 24), E.P(E.C(*RED, 240)))
            text(c, 'TODAY (MODERN FURNITURE)', x0 + 10, 980, 40, GREY, 1, False)
            text(c, f'~{max(3, int(round(17 - 14 * g2)))} MIN', x0 + w2 + 120, 1085, 62, YEL, 1)
            text(c, 'UL fire research', 540, 1260, 38, GREY, .9)
    return sk(img, f)
def door_temps(T, u):
    """UL FSRI 'Close Before You Doze': closed-door rooms <100°F vs open-door rooms 1,000°F+"""
    img = blur(kb('door', .5, 1.1, 1.12), 8) * .3
    def f(c):
        c.translate(0, -220); panel(c, 60, 540, 960, 860)
        for k, (lab, val, col, op) in enumerate([('DOOR CLOSED', 'UNDER 100°F', BLUE, False), ('DOOR OPEN', '1,000°F+', RED, True)]):
            g = eout(clamp(u * 2.4 - k * .6)); x = 300 + k * 480; y = 700
            c.drawRect(skia.Rect.MakeXYWH(x - 190, y, 380, 420), E.P(E.C(*((30, 45, 70) if not op else (90, 30, 20)), 255 * g)))
            c.drawRect(skia.Rect.MakeXYWH(x - 190, y, 380, 420), E.P(E.C(*col, 255 * g), 'stroke', 8))
            if op:   # smoke + fire filling the room
                c.drawRect(skia.Rect.MakeXYWH(x - 186, y + 4, 372, 230 * g), E.P(E.C(25, 22, 22, 240 * g)))
                E.glow(c, x, y + 330, 170, (255, 110, 30), .9 * g)
                c.drawLine(x + 190, y + 120, x + 190 + 80 * g, y + 30, E.P(E.C(220, 210, 200, 255 * g), 'stroke', 14))
            else:
                c.drawLine(x + 190, y + 120, x + 190, y + 420, E.P(E.C(220, 210, 200, 255 * g), 'stroke', 14))
                for j in range(3): E.glow(c, x - 60 + j * 60, y + 300, 26, (180, 220, 255), .5 * g)
            text(c, lab, x, y - 40, 50, WHITE, g); text(c, val, x, y + 520, 70, col, g)
        text(c, 'UL fire tests', 540, 1360, 38, GREY, eout(clamp(u * 2.4 - 1.2)))
    return sk(img, f)
def january(T, u):
    img = blur(kb('dry', .5, 1.1, 1.12), 6) * .35
    def f(c):
        g = eout(u * 3); y0 = 560; x0 = 90
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x0, y0, 440, 360), 26, 26), E.P(E.C(235, 235, 240, 255 * g)))
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x0, y0, 440, 110), 26, 26), E.P(E.C(*RED, 255 * g))); c.drawRect(skia.Rect.MakeXYWH(x0, y0 + 80, 440, 30), E.P(E.C(*RED, 255 * g)))
        f_ = font(62); w = f_.measureText('JANUARY'); c.drawString('JANUARY', x0 + 220 - w / 2, y0 + 80, f_, E.P(E.C(*WHITE, 255 * g)))
        for r_ in range(4):
            for q in range(7): c.drawCircle(x0 + 45 + q * 58, y0 + 160 + r_ * 55, 9, E.P(E.C(150, 150, 165, 200 * g)))
        # pie: 36% of home tree fires happen in January
        g2 = eout(clamp(u * 2 - .5)); cx, cy, r = 790, 730, 150
        c.drawCircle(cx, cy, r, E.P(E.C(70, 80, 95, 255 * g2)))
        pth = skia.Path(); pth.moveTo(cx, cy); pth.arcTo(skia.Rect.MakeLTRB(cx - r, cy - r, cx + r, cy + r), -90, 360 * .36 * g2, False); pth.close()
        c.drawPath(pth, E.P(E.C(*ORANGE, 255 * g2)))
        text(c, '36%', cx, cy + r + 95, 90, YEL, g2)
    return sk(img, f)
def tips(T, u, n):
    img = kb('calm', u, 1.05, 1.12, (.45, .5), (.42, .5)) * .45
    labels = [('WATER IT', 'every day', BLUE), ('3 FEET', 'from heat', ORANGE), ('LIGHTS OFF', 'at night', YEL)]
    def f(c):
        for k in range(3):
            g = eout(clamp(n - k)); y = 360 + k * 230
            if g <= 0: continue
            c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(140 + 60 * (1 - g), y, 800, 190), 40, 40), E.P(E.C(14, 20, 30, 230 * g)))
            c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(140 + 60 * (1 - g), y, 800, 190), 40, 40), E.P(E.C(*labels[k][2], 255 * g), 'stroke', 6))
            c.drawCircle(240, y + 95, 58, E.P(E.C(*labels[k][2], 255 * g)))
            f_ = font(64); w = f_.measureText(str(k + 1)); c.drawString(str(k + 1), 240 - w / 2, y + 118, f_, E.P(E.C(20, 20, 20, 255 * g)))
            text(c, labels[k][0], 330, y + 92, 72, WHITE, g, False); text(c, labels[k][1], 330, y + 155, 46, GREY, g, False)
    return sk(img, f)
def rings(img, T, x, y, col=RED, k=1.0):
    def f(c):
        for j in range(3):
            a = (T * 1.8 + j / 3) % 1; r = 60 + 220 * a
            c.drawCircle(x, y, r, E.P(E.C(*col, 200 * (1 - a) * k), 'stroke', 9))
    return sk(img, f)
def siren(img, T, k=1.0):
    """red/blue flashing light washing over the frame"""
    ph = (T * 2.4) % 1; r_ = max(0, math.sin(ph * 6.28)); b_ = max(0, -math.sin(ph * 6.28))
    return img * (1 - .12 * k) + (np.float32([40, 30, 255]) * r_ + np.float32([255, 90, 30]) * b_) * .18 * k * (.4 + .6 * (1 - YY / H))[..., None]
def small_flame(img, T, x, y, k, grow=0.0):
    return flames(img, T, (x, y), y - 260 - 700 * grow, 90 + 500 * grow, k * (.5 + grow), flicker=False)

# ---------------------------------------------------------------- scenes
def S0(t, T):   # HOOK: the tree fully ablaze, sparks, ceiling smoke, slight push
    img = tree_fire('hook', T, t / 2.8, 1.12, 1.2, (.5, .5), (.5, .47), 1.3, .7, .2 + .03 * t)
    return shake(flash(img, t + .25, 70, 6, (.5, .8, 1)), t, 10, 2.5)

def S1(t, T):
    c = wt('Nobody') - .1
    if t < c: return kb('calm', t / c, 1.0, 1.1, (.5, .52), (.55, .5))
    u = t - c
    return whip(kb('dry', u / (D + PAD - c), 1.0, 1.15, (.5, .55), (.5, .62)), u)

def S2(t, T):
    c = wt('smoking') - .25
    if t < c: return ptalk('cu_mia', t, t / c, 1.0, 1.06, (.5, .45), (.5, .44), .01)
    u = t - c; img = kb('bulb', u / (D + PAD - c), 1.0, 1.12)
    x, y, _ = sp('bulb', 'spark')
    img = smoke_puffs(img, T, (x, y), .9, .5, .5, (150, 150, 155), 30, .6)
    return whip(sparks(img, T, (x, y), 120, .8, 24), u)

def S3(t, T):
    c = wt('two') - .3
    if t < c:
        img = kb('bulb', t / c, 1.12, 1.3, (.5, .5), (.52, .52)); x, y, _ = sp('bulb', 'spark')
        img = smoke_puffs(img, T, (x, y), 1.0, .5, .5, (150, 150, 155), 30, .6)
        return small_flame(sparks(img, T, (x, y), 140, 1.0, 30), T, x, y, clamp((t - .6) / 1.2) * .6)
    return whip(two_in_five(T, clamp((t - c) / 1.4)), t - c)

def S4(t, T):
    c = wt('dry') - .2
    if t < c:   # watered branch: a lighter flame touches it and goes out
        img = kb('wet', t / c, 1.0, 1.1); x, y, _ = sp('wet', 'tip')
        k = clamp(t / .4) * clamp((c - .4 - t) / .8 + .3)
        return small_flame(img, T, x, y + 40, k * .6)
    u = t - c; img = kb('drybr', u / (D + PAD - c), 1.0, 1.15); x, y, _ = sp('drybr', 'tip')
    return whip(small_flame(img, T, x, y + 40, .8, clamp(u / 1.6) * 1.2), u)

def S5(t, T):   # lab test: the dry tree goes from a spark to fully ablaze; stopwatch counts 0 -> 30 s (time compressed)
    u = clamp(t / (D - .2)); secs = 30 * u
    img = tree_fire('dry', T, u, 1.0, 1.08, (.5, .5), (.5, .48), k=.15 + 1.1 * u ** 1.5, smoke=u, sm_depth=.25 * u, spark=u)
    def f(c): stopwatch(c, 820, 460, 120, secs, 1.0, 60)
    return sk(img, f)

def S6(t, T):
    u = t / (D + PAD)
    kx, ky = pts('fire')['kai']; cc = (kx / W - .08, ky / H)
    img = tree_fire('fire', T, u, 1.9, 2.0, cc, (cc[0], cc[1] - .01), 1.1, .7, .18)
    img = cv2.warpAffine(img, cv2.getRotationMatrix2D((W / 2, H / 2), 0, talk(t, .012)), (W, H), borderMode=cv2.BORDER_REFLECT)
    return shake(flash(ember_grade(img, T, .5), t, 50, 6, (.5, .8, 1)), t, 14, 2.5)

def S7(t, T):
    c = wt('flash') - .25
    if t < c: return tree_fire('fire', T, t / c, 1.0, 1.08, (.5, .5), (.52, .5), 1.1, .9, .2 + .1 * t / c)
    u = t - c; uu = u / (D + PAD - c)
    img = tree_fire('wide', T, uu, 1.0, 1.08, (.5, .5), (.5, .48), 1.3 + .4 * uu, 1.0, .32 + .1 * uu)
    img = ceiling_roll(img, T, H * .2, W * .1, W * .95, clamp((u - .1) * 2.2))
    for k, (px, py, wd) in enumerate([(.24, .6, 420), (.85, .55, 300), (.62, .58, 260)]):   # flashover: the furniture ignites
        img = flames(img, T + k * .3, (W * px, H * py), H * py - 380, wd, clamp((u - .3 - .15 * k) * 3) * .8, flicker=False, n=260)
    return whip(flash(img, u, 160, 5, (.5, .8, 1)), u)

def S8(t, T):
    c = wt('About') - .2
    if t < c:
        img = tree_fire('wide', T, t / c, 1.15, 1.35, (.5, .4), (.5, .3), 1.5, 1.0, .4)
        return heat_shimmer(img, T, 1.2)
    return whip(thermo(T, clamp((t - c) / 2.0)), t - c)

def S9(t, T): return escape_bars(T, clamp(t / 3.0), 0)
def S10(t, T):
    c = .5
    if t < c: return escape_bars(T, 0, 1)
    return escape_bars(T, clamp((t - c) / 1.8), 1)

def S11(t, T):
    img = tree_fire('fire', T, t / (D + PAD), 1.55, 1.65, (.62, .5), (.63, .49), 1.2, .9, .22)
    return cv2.warpAffine(img, cv2.getRotationMatrix2D((W / 2, H / 2), 0, talk(t, .01)), (W, H), borderMode=cv2.BORDER_REFLECT)

def S12(t, T):
    c = wt('smoke') - .2
    if t < c: return kb('bed', t / c, 1.0, 1.1, (.45, .5), (.42, .5))
    u = t - c; img = kb('stairs', u / (D + PAD - c), 1.0, 1.12, (.5, .55), (.5, .45))
    img = smoke_puffs(img, T, (W * .5, H * .95), 1.0, 1.6, 1.2, (100, 104, 112), 46, 1.2)
    return whip(ceiling_smoke(img, T, .25 + .08 * u, .8, (70, 70, 74)), u)

def S13(t, T):
    img = kb('door', t / (D + PAD), 1.0, 1.12, (.5, .5), (.5, .48))
    img = smoke_puffs(img, T, (W * .5, H * 1.05), 1.0, 2.0, .9, (100, 104, 112), 46, 1.3)
    return ceiling_smoke(img, T, .3 + .05 * t, 1.0, (70, 70, 74))

def S14(t, T):
    c = wt('shut') - .2
    if t < c:
        img = kb('door', t / c, 1.12, 1.25, (.5, .48), (.5, .5))
        return ceiling_smoke(smoke_puffs(img, T, (W * .5, H * 1.05), 1.0, 2.0, .9, (100, 104, 112), 46, 1.3), T, .36, 1.0, (70, 70, 74))
    u = t - c; img = kb('bed', u / (D + PAD - c), 1.05, 1.15, (.6, .55), (.62, .55))
    return whip(img, u)

def S15(t, T): return door_temps(T, clamp(t / 3.2))

def S16(t, T):
    c = wt('Firefighters') - .2
    if t < c:
        img = kb('bed', t / c, 1.15, 1.25, (.45, .45), (.45, .45)); x, y, _ = sp('bed', 'leo')
        return rings(img, T, W * .82, H * .3, RED, 1.0)
    u = t - c; img = kb('house', u / (D + PAD - c), 1.0, 1.1, (.5, .5), (.55, .45)) * np.float32([.8, .7, .66])
    for key in ('dwin',):
        x, y, z = sp('house', key); img = smoke_puffs(img, T, (x, y - 80), .8, 1.0, 1.0, (60, 58, 60), 30, .8)
    return whip(siren(img, T, 1.0), u)

def S17(t, T): return siren(ptalk('safe', t, t / (D + PAD), 1.0, 1.08, (.5, .48), (.5, .46), .01) * np.float32([.75, .62, .58]), T, .7)

def S18(t, T):
    c = wt('third') - .3
    if t < c: return kb('dry', t / c, 1.15, 1.05, (.5, .55), (.5, .55))
    return whip(january(T, clamp((t - c) / 2.0)), t - c)

def S19(t, T):
    c = wt('bone') - .2
    if t < c: return kb('dry', t / c, 1.2, 1.4, (.5, .7), (.5, .78))
    return whip(kb('drybr', (t - c) / (D + PAD - c), 1.05, 1.18), t - c)

def S20(t, T):
    n = 0
    for k, w in enumerate(('water', 'three', 'lights')):
        if t > wt(w) - .15: n = k + clamp((t - wt(w) + .15) / .35)
    return tips(T, t / (D + PAD), n)

def S21(t, T):
    c = (D + PAD) - .9
    if t < c: return kb('calm', t / c, 1.0, 1.15, (.5, .5), (.55, .5))
    u = t - c   # loop: back to the burning tree on frame 1
    return whip(tree_fire('hook', T, 0, 1.12, 1.12, k=1.15, smoke=.7, sm_depth=.2), u, vertical=True)

# ---------------------------------------------------------------- overlays
def overlays():
    wo = lambda *a, **k: wt(*a, **k) - XF      # overlay clock (compose) = scene clock - crossfade lead
    o = []
    if idx == 0: o += [{'type': 'hook', 'text': 'A DRY TREE|BURNS IN SECONDS', 'y': .11}]
    if idx == 1: o += [{'type': 'label', 'text': 'UP SINCE THANKSGIVING', 'pos': [.5, .12], 'color': YEL, 'from': .3},
                       {'type': 'label', 'text': 'NOT WATERED IN WEEKS', 'pos': [.5, .12], 'color': RED, 'from': wo('Nobody')}]
    if idx == 3: o += [{'type': 'label', 'text': 'OLD, DAMAGED LIGHTS', 'pos': [.5, .12], 'color': RED, 'from': .3, 'to': wo('two') - .3}]
    if idx == 4: o += [{'type': 'label', 'text': 'WATERED', 'pos': [.5, .12], 'color': GREEN, 'from': .3, 'to': wo('dry') - .2},
                       {'type': 'label', 'text': 'DRY', 'pos': [.5, .12], 'color': RED, 'from': wo('dry') - .2}]
    if idx == 5: o += [{'type': 'label', 'text': 'FIRE LAB TEST', 'pos': [.5, .1], 'color': YEL, 'from': .1},
                       {'type': 'badge', 'value': '<30', 'unit': 'SECONDS TO FULLY ABLAZE', 'pos': [.5, .17], 'from': wo('thirty') - .2, 'size': 80}]
    if idx == 7: o += [{'type': 'badge', 'value': '~1', 'unit': 'MINUTE TO FLASHOVER', 'pos': [.5, .13], 'from': .4, 'size': 80},
                       {'type': 'label', 'text': 'FLASHOVER', 'pos': [.5, .2], 'color': RED, 'from': wo('flash')}]
    if idx == 12: o += [{'type': 'label', 'text': 'UPSTAIRS · ASLEEP', 'pos': [.5, .12], 'color': WHITE, 'from': .3}]
    if idx == 13: o += [{'type': 'label', 'text': 'SMOKE KILLS MORE', 'pos': [.5, .12], 'color': RED, 'from': .3},
                        {'type': 'label', 'text': 'THAN FLAMES', 'pos': [.5, .175], 'color': WHITE, 'from': .5}]
    if idx == 14: o += [{'type': 'label', 'text': 'DOOR SHUT', 'pos': [.5, .12], 'color': GREEN, 'from': wo('shut') - .2}]
    if idx == 16: o += [{'type': 'label', 'text': 'SMOKE ALARM', 'pos': [.5, .12], 'color': RED, 'from': .2, 'to': wo('Firefighters') - .2}]
    if idx == 18: o += [{'type': 'label', 'text': 'OF HOME TREE FIRES (NFPA)', 'pos': [.5, .12], 'color': WHITE, 'from': wo('third')}]
    if idx == 19: o += [{'type': 'label', 'text': 'BONE DRY', 'pos': [.5, .12], 'color': RED, 'from': wo('bone') - .2}]
    if idx == 21: o += [{'type': 'cta', 'text': 'FOLLOW FOR MORE STORIES', 'from': .2}]
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
