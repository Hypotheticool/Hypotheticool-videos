"""Animate every scene of the WYR "gulped by a whale or stuck in quicksand?" over its Cycles plates (2D camera moves, cuts, bubbles,
light shafts, splashes, science diagrams).
python3 whale_anim.py <scene> [still_times...]  ->  whale/s<scene>/f_####.png + meta.json (overlays read by compose.py)"""
import sys, math, json, os
sys.path.insert(0, '/home/claude/pro')
import numpy as np, cv2, skia
import engine as E
ROOT = '/home/claude/b3d/whale'; CFG = json.load(open(f'{ROOT}/topic.json'))
FPS = 24; PAD = .75; XF = .35
idx = int(sys.argv[1]); D = CFG['durs'][idx]; NF = int(math.ceil((D + PAD) * FPS))
W, H = 1080, 1920
ease = lambda t: .5 - .5 * math.cos(math.pi * min(max(t, 0), 1))
eout = lambda t: 1 - (1 - min(max(t, 0), 1)) ** 3
clamp = lambda v, a=0., b=1.: max(a, min(b, v))
YEL, WHITE, BLUE, RED, TEAL = (255, 222, 40), (255, 255, 255), (130, 200, 255), (255, 110, 90), (90, 220, 210)
A_TXT, B_TXT = 'Gulped by a whale', 'Stuck in quicksand'

def wt(word, line=None, end=False):
    """local scene time (s) when `word` is spoken in this scene's line"""
    ln = E.shown(CFG['lines'][idx if line is None else line]); words = ln.split()
    clip = D - E.lead(idx) - E.GAP; tt = E.word_times(ln, clip)
    for k, w in enumerate(words):
        if word.lower() in w.lower(): return XF + E.lead(idx) + tt[k][1 if end else 0]
    raise KeyError(word)

YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)
VIGM = (1 - .55 * np.clip(((XX / W - .5) ** 2 * 1.6 + (YY / H - .5) ** 2) ** .5 - .25, 0, 1) * 1.6)[..., None]
UNDER = {'lunge', 'side', 'diver'}
PL = {}
def plate(name):
    """load a plate, upscale, grade into the palette: deep teal shadows, warm highlights, vignette"""
    if name not in PL:
        im = cv2.imread(f'{ROOT}/plates/{name}.png', cv2.IMREAD_COLOR)
        if im.shape[1] != W: im = cv2.resize(im, (W, H), interpolation=cv2.INTER_CUBIC)
        im = im.astype(np.float32); lum = im.mean(2, keepdims=True) / 255
        im = im * .9 + (1 - lum) * np.float32([24, 12, 0]) * .9                 # BGR: teal into the shadows
        if name in UNDER: im = im * np.float32([1.0, 1.0, .85])                 # underwater: less red
        if name == 'diver':                                                     # distance haze toward the far seafloor (Cape Cod green water)
            haze = np.clip(1 - np.abs(YY / H - .36) / .2, 0, 1)[..., None] ** 1.5
            im = im * (1 - .7 * haze) + np.float32([70, 95, 55]) * .7 * haze
            im = im * (1 - .45 * np.clip((YY / H - .45) / .55, 0, 1)[..., None]) + np.float32([30, 40, 20]) * .3
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
BUB = np.random.default_rng(3).random((140, 4))
def bubbles(img, T, k=1.0, speed=1.0, x0=0.0, x1=1.0):
    """rising air bubbles (two depths), wobbling"""
    def f(c):
        for x, y, s, ph in BUB:
            px = W * (x0 + (x1 - x0) * x) + 14 * math.sin(T * 5 + ph * 20); py = (H * y - T * (160 + 420 * s) * speed) % (H + 80) - 40
            r = 3 + 16 * s * s
            c.drawCircle(px, py, r, E.P(E.C(210, 240, 255, 140 * k), 'stroke', 2 + 2 * s))
            c.drawCircle(px - r * .3, py - r * .3, r * .25, E.P(E.C(255, 255, 255, 200 * k)))
    return sk(img, f)

SN = np.random.default_rng(7).random((200, 4))
def motes(img, T, k=1.0):
    """marine snow / plankton drifting in the light"""
    lay = np.zeros_like(img)
    for x, y, s, b in SN:
        px = int((x * W + math.sin(T * .7 + y * 9) * 18) % W); py = int((y * H + T * 22 * (.3 + s)) % H)
        v = (30 + 90 * b * b) * k; cv2.circle(lay, (px, py), 1 + int(s * 2.4), (v * .9, v, v * .8), -1, cv2.LINE_AA)
    return img + cv2.GaussianBlur(lay, (0, 0), 1.1)

def rays(img, T, k=1.0, src=(.45, -.1)):
    """soft sunlight shafts slanting down from the surface, slowly swaying"""
    def f(c):
        for j in range(7):
            ang = math.radians(-14 + j * 5 + 2.5 * math.sin(T * .6 + j)); x0 = W * src[0] + (j - 3) * 90
            pth = skia.Path(); L = H * 1.3; wd = 40 + 30 * math.sin(j * 1.7 + T * .8)
            pth.moveTo(x0 - wd * .3, H * src[1]); pth.lineTo(x0 + wd * .3, H * src[1])
            pth.lineTo(x0 + wd * 2.4 + L * math.sin(ang), H * src[1] + L * math.cos(ang)); pth.lineTo(x0 - wd * 2.4 + L * math.sin(ang), H * src[1] + L * math.cos(ang)); pth.close()
            c.drawPath(pth, E.P(E.C(180, 245, 235, (22 + 12 * math.sin(T * 1.3 + j * 2)) * k), blur=30, add=True))
    return sk(img, f)

def underwater(img, T, k=1.0, bub=.5):
    img = rays(img, T, k); img = motes(img, T, .9 * k)
    return bubbles(img, T, bub) if bub > 0 else img

SPL = np.random.default_rng(11).random((120, 5))
def splash(img, T, t, cx, cy, k=1.0, spread=1.0):
    """white water exploding up and out from (cx, cy) (fractions), droplets on ballistic arcs + foam sheet; t = time since the burst"""
    def f(c):
        for vx, vy, s, ph, r_ in SPL:
            ang = math.radians(-90 + (vx - .5) * 140 * spread); sp = 700 + 1500 * vy
            x = W * cx + math.cos(ang) * sp * t * .6; y = H * cy + math.sin(ang) * sp * t + 1600 * t * t
            r = 4 + 18 * s * s; a = clamp(1.4 - t * .9) * k
            if a > 0: c.drawCircle(x, y, r, E.P(E.C(240, 248, 255, 230 * a), blur=1.5))
        for j in range(14):   # foam sheet
            ph = j / 14; x = W * (cx + (ph - .5) * .55 * spread * (.5 + t)); y = H * cy - 140 * math.sin(math.pi * ph) * clamp(1 - t * .5) * (1 + t)
            c.drawCircle(x, y, 60 + 40 * math.sin(j * 3.1), E.P(E.C(235, 245, 250, 170 * clamp(1.6 - t) * k), blur=22))
    return sk(img, f)

def drips(img, T, x0, x1, y0, k=1.0):
    """water pouring off an edge (streams falling from y0 between x0..x1)"""
    def f(c):
        for j in range(18):
            x = W * (x0 + (x1 - x0) * j / 17) + 6 * math.sin(j * 7 + T * 3)
            for q in range(4):
                ph = (T * 1.6 + j * .37 + q * .25) % 1; y = H * y0 + ph * ph * 380
                c.drawLine(x, y, x, y + 40 + 30 * ph, E.P(E.C(230, 245, 255, 160 * (1 - ph) * k), 'stroke', 5, blur=1.5))
    return sk(img, f)

# ---------------------------------------------------------------- 2D cards / diagrams
def bg_card(name, u, z=1.15, darkk=.3, s=12): return blur(kb(name, u, z, z + .05), s) * darkk

def hook_frame(T, u=None):
    """the payoff shot: a humpback's jaws wide open, right behind a diver (illustration)"""
    u = (T / 2.6) if u is None else u
    img = kb('lunge', u, 1.5, 1.68, (.52, .56), (.52, .58), rot=1.5 * math.sin(T * 1.3))
    img = underwater(img, T, 1.1, .7)
    return img

def bus_card(T, u):
    """length to scale: adult humpback (~49-52 ft, NOAA) vs a full-size school bus (~40 ft)"""
    img = dim(kb('side', u, 1.25, 1.35, (.52, .48), (.5, .48)), .55); img = underwater(img, T, .7, 0)
    g = eout(clamp(u * 1.8)); gb = eout(clamp(u * 1.8 - .5))
    def f(c):
        x0 = W * .07; s = W * .86 / 50.0; y1, y2 = H * .3, H * .44
        c.drawRoundRect(skia.Rect.MakeXYWH(x0, y1, 50 * s * g, 80), 40, 40, E.P(E.C(*TEAL, 245)))
        text(c, 'HUMPBACK  ~50 FT', x0 + 10, y1 - 26, 62, TEAL, g, center=False)
        c.drawRoundRect(skia.Rect.MakeXYWH(x0, y2, 40 * s * gb, 80), 14, 14, E.P(E.C(255, 175, 0, 250)))
        for k in range(8):
            if (k + 1) / 8 <= gb: c.drawRoundRect(skia.Rect.MakeXYWH(x0 + 30 + k * 40 * s / 8.4, y2 + 12, 40 * s / 8.4 - 16, 30), 6, 6, E.P(E.C(40, 50, 60, 230)))
        text(c, 'SCHOOL BUS  ~40 FT', x0 + 10, y2 - 26, 62, YEL, gb, center=False)
        text(c, 'LENGTHS TO SCALE', W / 2, y2 + 150, 38, (190, 205, 215), gb)
    return sk(img, f)

def gulp_card(T, u):
    """lunge feeding: water rushing into the open mouth (arrows converging) + a growing water counter"""
    img = kb('lunge', u, 1.25, 1.45, (.52, .6), (.52, .6)); img = underwater(img, T, 1.0, .4)
    def f(c):
        cx, cy = W * .5, H * .66
        for j in range(16):
            ang = j / 16 * 2 * math.pi; ph = (T * .9 + j * .13) % 1
            r = 520 * (1 - ph) + 80
            x = cx + math.cos(ang) * r; y = cy + math.sin(ang) * r * .8
            c.drawLine(x, y, x - math.cos(ang) * 70, y - math.sin(ang) * 56, E.P(E.C(200, 240, 255, 200 * math.sin(math.pi * ph)), 'stroke', 7))
    return sk(img, f)

def depth_card(T, u):
    """water column from the surface to the diver at 45 ft (to scale), Cape Cod green"""
    img = np.zeros((H, W, 3), np.float32); ys = np.linspace(0, 1, H)[:, None]
    img[:] = np.concatenate([(70 - 55 * ys), (110 - 85 * ys), (60 - 50 * ys)], 1)[:, None, :]
    img = motes(rays(img, T, .8, (.5, .12)), T, .8)
    g = eout(clamp(u * 1.6))
    def f(c):
        top, bot = H * .3, H * .9; ft = (bot - top) / 50
        c.drawLine(0, top, W, top, E.P(E.C(*BLUE, 230), 'stroke', 5)); text(c, 'SURFACE', W * .82, top - 18, 38, BLUE)
        for k in range(0, 51, 10):
            y = top + k * ft; c.drawLine(W * .1, y, W * .15, y, E.P(E.C(220, 230, 235, 200), 'stroke', 4)); text(c, f'{k} ft', W * .19, y + 14, 34, (215, 225, 230), 1, False)
        yd = top + 45 * ft * g
        c.drawLine(W * .55, top, W * .55, yd, E.P(E.C(*YEL, 240), 'stroke', 6))
        c.drawCircle(W * .55, yd, 26, E.P(E.C(*YEL, 255))); c.drawCircle(W * .55, yd, 70, E.P(E.C(*YEL, 90), blur=24))
        text(c, f'{45 * g:.0f} FT DOWN', W * .55, yd - 50, 64, YEL, g)
        text(c, 'ABOUT A 4-STORY BUILDING', W * .55, yd + 90, 40, WHITE, clamp(u * 3 - 1.5))
    return sk(img, f)

def dark_mouth(T, u, k_light=1.0):
    """inside the closed mouth: nearly black, a thin line of light through the lips, baleen fringe silhouetted"""
    img = np.zeros((H, W, 3), np.float32) + np.float32([6, 4, 4])
    def f(c):
        y = H * .43 + 10 * math.sin(T * 1.7)
        c.drawRect(skia.Rect.MakeXYWH(-50, y - 6, W + 100, 12), E.P(E.C(170, 230, 220, 200 * k_light), blur=8, add=True))
        c.drawRect(skia.Rect.MakeXYWH(-50, y - 40, W + 100, 80), E.P(E.C(60, 140, 140, 90 * k_light), blur=40, add=True))
        for j in range(28):   # baleen plates hanging down from the top, fringed tips
            x = j * W / 27 + 8 * math.sin(T + j)
            c.drawLine(x, 0, x + 14, y - 30 + 20 * math.sin(j), E.P(E.C(16, 12, 10, 255), 'stroke', 26))
            for q in range(5): c.drawLine(x + 6 + q * 3, y - 60, x + 10 + q * 4, y + 20 + 10 * math.sin(j + q), E.P(E.C(55, 42, 36, 200), 'stroke', 2))
        # the diver, a dark silhouette lit only by the slit
        dx, dy = W * .5 + 30 * math.sin(T * 2), H * .58
        c.drawCircle(dx, dy - 130, 60, E.P(E.C(18, 22, 24, 255))); c.drawRoundRect(skia.Rect.MakeXYWH(dx - 50, dy - 70, 100, 170), 30, 30, E.P(E.C(18, 22, 24, 255)))
        c.drawRect(skia.Rect.MakeXYWH(dx - 50, dy - 150, 100, 30), E.P(E.C(60, 110, 120, 200 * k_light)))   # mask glint
    return motes(sk(img, f), T, .25)

def fist(c, cx, cy, s, col=(230, 190, 160), a=1.0):
    """a simple clenched fist (front view): palm block + 4 finger knuckles + thumb"""
    p = E.P(E.C(*col, 255 * a)); o = E.P(E.C(60, 40, 30, 255 * a), 'stroke', 5)
    r = skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(cx - s * .5, cy - s * .35, s, s * .85), s * .18, s * .18); c.drawRRect(r, p); c.drawRRect(r, o)
    for j in range(4):
        rr = skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(cx - s * .5 + j * s / 4, cy - s * .55, s / 4, s * .42), s * .1, s * .1); c.drawRRect(rr, p); c.drawRRect(rr, o)
    th = skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(cx - s * .55, cy - s * .05, s * .6, s * .22), s * .1, s * .1); c.drawRRect(th, p); c.drawRRect(th, o)

def throat_card(T, u, mode='fist'):
    """humpback throat vs a fist, then stretched to ~15 in vs a person's shoulders (~18 in) (front views, same scale)"""
    img = bg_card('side', u, 1.4, .28)
    def f(c):
        cx, cy = W * .5, H * .42
        if mode == 'fist':
            pxin = 52.0; g = eout(clamp(u * 2)); R = 2.2 * pxin * (1 + .02 * math.sin(T * 4))   # fist-sized opening (~4-5 in across)
            c.drawCircle(cx - 220, cy, 2.2 * R, E.P(E.C(60, 14, 16, 230 * g))); c.drawCircle(cx - 220, cy, R, E.P(E.C(5, 2, 2, 255 * g)))
            c.drawCircle(cx - 220, cy, R, E.P(E.C(*RED, 255 * g), 'stroke', 7)); text(c, 'ITS THROAT', cx - 220, cy - 2.2 * R - 40, 56, RED, g)
            a2 = eout(clamp(u * 2 - .5)); fist(c, cx + 230, cy + 20, 4.2 * pxin, a=a2); text(c, 'YOUR FIST', cx + 230, cy - 2.2 * R - 40, 56, WHITE, a2)
        else:
            pxin = 40.0; g = eout(clamp(u * 1.6)); R = (2.2 + (7.5 - 2.2) * g) * pxin
            c.drawCircle(cx, cy, R + 40, E.P(E.C(60, 14, 16, 230))); c.drawCircle(cx, cy, R, E.P(E.C(5, 2, 2, 255))); c.drawCircle(cx, cy, R, E.P(E.C(*RED, 255), 'stroke', 7))
            c.drawLine(cx - R, cy - R - 70, cx + R, cy - R - 70, E.P(E.C(*YEL, 255), 'stroke', 5))
            for d in (-1, 1): c.drawLine(cx + d * R, cy - R - 90, cx + d * R, cy - R - 50, E.P(E.C(*YEL, 255), 'stroke', 5))
            text(c, f'{2 * R / pxin:.0f} IN' if g < .99 else '~15 IN', cx, cy - R - 95, 60, YEL)
            a2 = eout(clamp(u * 2 - .8)); sw = 18 * pxin
            if a2 > 0:   # a person's outline (shoulders ~18 in) trying to fit through
                ol = E.P(E.C(160, 220, 255, 255 * a2), 'stroke', 7)
                c.drawCircle(cx, cy - 175, 95, ol)
                body = skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(cx - sw / 2, cy - 60, sw, 420), 110, 110); c.drawRRect(body, ol)
                for d in (-1, 1):
                    c.drawCircle(cx + d * R, cy + 10, 22, E.P(E.C(*RED, 255 * a2))); c.drawCircle(cx + d * R, cy + 10, 50, E.P(E.C(*RED, 120 * a2), blur=16))
                text(c, 'SHOULDERS ~18 IN', cx, H * .745, 50, (160, 220, 255), a2)
                text(c, "YOU WON'T FIT", cx, H * .8, 76, RED, clamp(u * 3 - 1.8))
    return sk(img, f)

GR = np.random.default_rng(13).random((150, 3))
def grains(T, u, flow=0.0):
    """quicksand close-up: packed sand grains with water filling the gaps; flow (0-1) = the grains lose contact and slide (liquefies)"""
    img = np.zeros((H, W, 3), np.float32); img[:] = (40, 26, 14)
    def f(c):
        c.drawRect(skia.Rect.MakeXYWH(0, H * .22, W, H * .4), E.P(E.C(40, 90, 150, 200)))   # pore water
        for k, (x, y, s) in enumerate(GR):
            gx = W * x; gy = H * (.22 + .4 * y)
            if flow > 0: gx += flow * 70 * math.sin(T * 3 + k); gy += flow * (30 * math.sin(T * 2.3 + k * 1.7) + 60 * flow)
            r = 24 + 22 * s
            col = (int(210 - 50 * s), int(165 - 40 * s), int(100 - 30 * s))
            c.drawCircle(gx, gy, r, E.P(E.C(*col, 255))); c.drawCircle(gx - r * .3, gy - r * .3, r * .3, E.P(E.C(255, 235, 190, 120)))
        text(c, 'SAND + WATER' if flow < .3 else 'GRAINS SLIP APART', W / 2, H * .215, 60, YEL)
    return sk(img, f)

def density_card(T, u):
    """quicksand ~2 g/mL vs a human body ~1 g/mL (bars to scale)"""
    img = bg_card('flat', u, 1.2, .3)
    def f(c):
        base = H * .52; s = 190
        for k, (lab, v, col, x) in enumerate((('QUICKSAND', 2.0, (210, 160, 90), W * .3), ('YOU', 1.0, (120, 200, 255), W * .7))):
            g = eout(clamp(u * 1.8 - .35 * k)); hh = v * s * g
            c.drawRoundRect(skia.Rect.MakeXYWH(x - 110, base - hh, 220, hh), 18, 18, E.P(E.C(*col, 240)))
            text(c, f'~{v:.0f} g/mL', x, base - hh - 30, 54, WHITE, g); text(c, lab, x, base + 70, 54, col, g)
        text(c, '2x DENSER', W / 2, H * .25, 80, YEL, clamp(u * 3 - 1.5))
    return sk(img, f)

def waist_card(T, u):
    """cross-section: you float in quicksand, stopping about waist-deep (buoyancy arrow up)"""
    img = np.zeros((H, W, 3), np.float32); ys = np.linspace(0, 1, H)[:, None]
    img[:] = np.concatenate([(150 - 100 * ys), (120 - 50 * ys), (90 + 60 * ys)], 1)[:, None, :]   # dusk sky (BGR)
    g = eout(clamp(u * 1.5)); sink = 330 * g + 6 * math.sin(T * 3)
    def f(c):
        gy = H * .45
        c.drawRect(skia.Rect.MakeXYWH(0, gy, W, H - gy), E.P(E.C(120, 86, 50, 255)))
        # person (front, simple): legs, body, head; sinks until the waist meets the surface
        x = W / 2; top = gy - 560 + sink
        pp = E.P(E.C(245, 190, 40, 255)); hd = E.P(E.C(240, 220, 205, 255)); hair = E.P(E.C(230, 110, 30, 255))
        for d in (-1, 1): c.drawRoundRect(skia.Rect.MakeXYWH(x + d * 40 - 22, top + 400, 44, 260), 20, 20, E.P(E.C(30, 30, 35, 255)))
        c.drawRoundRect(skia.Rect.MakeXYWH(x - 85, top + 180, 170, 240), 50, 50, pp)
        for k in range(5): c.drawRect(skia.Rect.MakeXYWH(x - 85, top + 200 + k * 46, 170, 18), E.P(E.C(30, 25, 20, 255)))
        c.drawCircle(x, top + 95, 100, hd); c.drawCircle(x, top + 20, 70, hair)
        for d in (-1, 1): c.drawLine(x + d * 85, top + 210, x + d * 190, top + 60, E.P(E.C(30, 30, 35, 255), 'stroke', 16))
        # sand in front (covers the legs) with a translucent edge so the cut is readable
        c.drawRect(skia.Rect.MakeXYWH(0, gy, W, H - gy), E.P(E.C(150, 108, 64, 215)))
        c.drawLine(0, gy, W, gy, E.P(E.C(255, 230, 180, 255), 'stroke', 5))
        a2 = clamp(u * 3 - 1.2)
        E.arrow(c, x + 280, gy + 360, x + 280, gy + 120, 16, BLUE, a2); text(c, 'FLOATS', x + 280, gy + 430, 50, BLUE, a2)
    return sk(img, f)

def car_card(T, u):
    """pulling a foot straight up out of quicksand vs lifting a car (Bonn et al., Nature 2005)"""
    img = bg_card('leo_cu', u, 1.2, .3)
    def f(c):
        g = eout(clamp(u * 2))
        # left: a boot stuck in sand with an upward arrow straining
        bx, by = W * .28, H * .42
        c.drawRect(skia.Rect.MakeXYWH(bx - 200, by, 400, 230), E.P(E.C(140, 100, 60, 255)))
        c.drawRoundRect(skia.Rect.MakeXYWH(bx - 45, by - 220 + 10 * math.sin(T * 20) * g, 90, 300), 30, 30, E.P(E.C(40, 40, 45, 255)))
        c.drawRect(skia.Rect.MakeXYWH(bx - 200, by, 400, 70), E.P(E.C(140, 100, 60, 235)))
        E.arrow(c, bx, by - 240, bx, by - 400, 20, YEL, g)
        text(c, 'PULL ONE FOOT', bx, H * .56, 46, WHITE, g)
        # right: a car being lifted
        a2 = eout(clamp(u * 2 - .6)); cx, cy = W * .73, H * .42 - 60 * a2
        car = E.P(E.C(220, 60, 50, 255 * a2))
        c.drawRoundRect(skia.Rect.MakeXYWH(cx - 150, cy, 300, 90), 26, 26, car); c.drawRoundRect(skia.Rect.MakeXYWH(cx - 90, cy - 70, 180, 80), 24, 24, car)
        for d in (-1, 1): c.drawCircle(cx + d * 90, cy + 92, 34, E.P(E.C(20, 20, 24, 255 * a2)))
        E.arrow(c, cx, cy - 90, cx, cy - 220, 20, YEL, a2)
        text(c, 'LIFT A CAR', cx, H * .56, 46, WHITE, a2)
        text(c, '=', W / 2, H * .44, 120, YEL, a2)
    return sk(img, f)

def tide_frame(T, u):
    """the tide creeping in across the flat toward Leo (animated water edge over the tide plate)"""
    img = kb('tide', u, 1.1, 1.25, (.45, .55), (.55, .55))
    edge = .62 - .12 * ease(u)
    def f(c):
        for j in range(5):
            y = H * (edge + .015 * j) + 6 * math.sin(T * 2 + j)
            pth = skia.Path(); pth.moveTo(0, y)
            for x in range(0, W + 40, 40): pth.lineTo(x, y + 10 * math.sin(x * .02 + T * 3 + j))
            c.drawPath(pth, E.P(E.C(220, 240, 250, 150 - 25 * j), 'stroke', 5, blur=2))
        sea = skia.Path(); sea.moveTo(0, H * edge - 2); sea.lineTo(0, -10); sea.lineTo(W * .2, -10); sea.lineTo(W * .0, H * edge); sea.close()
    return sk(img, f)

# ---------------------------------------------------------------- scenes
def S0(t, T): return hook_frame(T)

def S1(t, T):
    c = wt('stuck') - .1
    if t < c: return underwater(kb('lunge', t / c, 1.2, 1.32, (.5, .55), (.5, .58)), T, 1.0, .5)
    return whip(kb('flat', (t - c) / 2.5, 1.0, 1.12, (.5, .55), (.52, .6)), t - c)

def S2(t, T):
    """A | B split, pulsing"""
    a = underwater(kb('lunge', .5, 1.35, 1.35, (.5, .58)), T, 1.0, .3); b = kb('leo_cu', .5, 1.05, 1.05, (.5, .45))
    xx = W * .5 + (YY - H / 2) * -.12 + 8 * math.sin(T * 2)
    out = np.where((XX > xx)[..., None], b, a); return np.where((np.abs(XX - xx) < 5)[..., None], np.float32(255), out)

def S3(t, T):
    c = wt('humpback') - .1
    if t < c: return underwater(kb('side', t / c, 1.15, 1.22, (.5, .48), (.47, .48)), T, .9, .2)
    return whip(bus_card(T, (t - c) / 3.0), t - c)

def S4(t, T):
    c = wt('gulping') - .2
    if t < c: return whip(underwater(kb('lunge', t / c, 1.0, 1.2, (.5, .55), (.52, .6)), T, 1.0, .4), t, .15)
    return whip(gulp_card(T, (t - c) / 2.5), t - c)

def S5(t, T):
    c = wt('Diver') - .1; c2 = wt('forty-five') - .2
    if t < c: return whip(kb('diver', t / c, 1.3, 1.2, (.5, .4), (.5, .45)), t)
    if t < c2: return whip(underwater(kb('diver', (t - c) / (c2 - c), 1.55, 1.75, (.45, .33), (.45, .3)), T, .7, .25), t - c)
    return whip(depth_card(T, (t - c2) / 2.2), t - c2, vertical=True)

def S6(t, T):
    c = wt('bump') - .05; c2 = wt('dark') - .25
    if t < c: return underwater(kb('diver', t / c, 1.3, 1.4, (.5, .4), (.5, .38)), T, .8, .2)
    if t < c2:
        img = underwater(kb('lunge', (t - c) / 1.5, 1.7, 1.95, (.5, .55), (.5, .52)), T, 1.0, 1.0)
        return shake(flash(img, t - c, 120, 9), t - c, 30, 4)
    return dim(underwater(kb('lunge', 1, 1.95, 2.1, (.5, .52), (.5, .5)), T, .5, 0), max(0, 1 - (t - c2) * 2.2))

def S7(t, T): return dark_mouth(T, t / (D + PAD), clamp(.3 + t))

def S8(t, T):
    c = wt('throat') - .2
    if t < c: return dark_mouth(T, 0, 1.0)
    return whip(throat_card(T, (t - c) / 2.4, 'fist'), t - c)

def S9(t, T): return throat_card(T, t / (D + PAD - .3), 'stretch')

def S10(t, T):
    c = wt('surfaced') - .15
    if t < c: return dark_mouth(T, 0, 1.0 + 2 * t)
    u = t - c; img = kb('surface', u / 2.6, 1.3, 1.45, (.35, .52), (.36, .5))
    img = splash(img, T, u, .3, .66, 1.0, 1.2); img = drips(img, T, .1, .3, .62, .8)
    return shake(flash(img, u, 160, 6), u, 22, 3)

def S11(t, T):
    img = kb('surface', t / (D + PAD), 1.8, 1.95, (.4, .49), (.41, .48)); return drips(img, T, .3, .45, .62, .5)

def S12(t, T):
    c = wt('Sand') - .1
    if t < c: return whip(kb('flat', t / c, 1.15, 1.05, (.5, .5), (.5, .55)), t)
    return whip(grains(T, (t - c) / 3, 0.0), t - c)

def S13(t, T):
    c = wt('runny') - .1; c2 = wt('legs') - .1
    if t < c: return grains(T, 1, 0.0)
    if t < c2: return grains(T, 1, clamp((t - c) * 1.5))
    u = t - c2; return whip(shake(kb('leo_cu', u / 2, 1.05, 1.2, (.5, .42), (.5, .5)), u, 14, 3), u)

def S14(t, T):
    c = wt('float') - .3
    if t < c: return density_card(T, t / c)
    return whip(kb('flat', (t - c) / 1.5, 1.25, 1.3, (.5, .5), (.5, .48)), t - c)

def S15(t, T): return waist_card(T, t / (D + PAD - .3))

def S16(t, T): return car_card(T, t / (D + PAD - .2))

def S17(t, T):
    c = wt('tide') - .2
    if t < c: return kb('leo_cu', t / c, 1.2, 1.3, (.5, .45), (.5, .43))
    return whip(tide_frame(T, (t - c) / 2.8), t - c)

def S18(t, T):
    img = kb('lean', t / (D + PAD), 1.05, 1.18, (.5, .5), (.5, .47))
    def f(c):
        for k, (w, lab) in enumerate((('lean', 'LEAN BACK'), ('spread', 'SPREAD OUT'), ('wiggle', 'WIGGLE SLOWLY'))):
            a = clamp((t - wt(w) + .1) * 3)
            if a > 0: text(c, f'{k + 1}. {lab}', W / 2, H * (.25 + .065 * k), 64, YEL, a)
    return sk(img, f)

def S19(t, T):
    c = wt('kayaker') - .3; c2 = wt('popped') - .2
    if t < c: return kb('kayak', t / c, 1.0, 1.12, (.5, .55), (.55, .55))
    if t < c2:
        u = t - c; img = kb('kayak', u / 2, 1.3, 1.45, (.62, .55), (.62, .55))
        return shake(splash(img, T, u, .55, .64, .8, .9), u, 16, 3)
    u = t - c2; img = kb('kayak', u / 2, 1.6, 1.7, (.76, .6), (.78, .6)); return whip(drips(img, T, .75, .95, .6, .5), u)

def S20(t, T):
    c = wt('Both') - .15
    if t < c:
        a = underwater(kb('lunge', t / c, 1.3, 1.36, (.5, .58)), T, 1.0, .3); b = dim(kb('leo_cu', t / c, 1.05, 1.08, (.5, .45)), .45)
        xx = W * .5 + (YY - H / 2) * -.12
        out = np.where((XX > xx)[..., None], b, a); return np.where((np.abs(XX - xx) < 5)[..., None], np.float32(255), out)
    u = t - c
    def f(cn):
        text(cn, 'UNDER 1 MINUTE', W / 2, H * .3, 84, YEL, clamp(u * 3)); text(cn, 'BOTH TIMES', W / 2, H * .36, 54, WHITE, clamp(u * 3 - .3))
    return whip(sk(kb('surface', u / 2.5, 1.2, 1.3, (.45, .5), (.45, .48)), f), u)

def S21(t, T):
    c = (D + PAD) - 1.0
    if t < c: return throat_card(T, .2 + .3 * t / c, 'fist')
    return whip(hook_frame(T - t + (t - c), (t - c) / 2.6), t - c, vertical=True)   # loop: the first frame again

# ---------------------------------------------------------------- overlays
def choice(win=None, from_=0.0, instant=True):
    o = {'type': 'choice', 'a': A_TXT, 'b': B_TXT, 'from': from_}
    if instant: o['instant'] = True
    if win: o['win'] = win
    return o

def overlays():
    o = []
    if idx == 0: o += [{'type': 'hook', 'text': "HE WAS INSIDE|A WHALE'S MOUTH", 'y': .11}]
    if idx == 1: o += [choice(from_=.3, instant=False)]
    if 2 <= idx <= 19: o += [choice()]
    if idx == 2: o += [{'type': 'prompt', 'text': 'Comment A or B', 'pos': [.5, .3], 'from': .1}, {'type': 'countdown', 'secs': 3, 'pos': [.5, .5]}]
    if idx == 3: o += [{'type': 'datestamp', 'text': 'A · HUMPBACK WHALE', 'y': .2, 'from': .1}]
    if idx == 4: o += [{'type': 'badge', 'value': '5,000+', 'unit': 'GALLONS', 'pos': [.5, .25], 'from': wt('five') - .1},
                       {'type': 'label', 'text': 'IN ONE GULP', 'pos': [.5, .31], 'color': WHITE, 'from': wt('once') - .2}]
    if idx == 5: o += [{'type': 'datestamp', 'text': 'CAPE COD, MASSACHUSETTS · JUNE 2021', 'y': .2, 'from': .1}]
    if idx == 7: o += [{'type': 'bubble', 'text': "Oh my God, I'm in a whale's mouth.", 'pos': [.5, .27], 'from': wt('Oh') - .1, 'size': 48},
                       {'type': 'label', 'text': '- MICHAEL PACKARD', 'pos': [.5, .335], 'color': (200, 210, 220), 'from': wt('Oh') + .3}]
    if idx == 8: o += [{'type': 'badge', 'value': 'FIST', 'unit': 'SIZED', 'pos': [.5, .25], 'from': wt('fist') - .1}]
    if idx == 10: o += [{'type': 'badge', 'value': '~30-40', 'unit': 'SECONDS', 'pos': [.5, .25], 'from': wt('thirty') - .1}]
    if idx == 11: o += [{'type': 'label', 'text': 'BADLY BRUISED', 'pos': [.5, .26], 'color': WHITE, 'from': wt('bruised') - .2},
                        {'type': 'label', 'text': 'NO BROKEN BONES', 'pos': [.5, .32], 'color': YEL, 'from': wt('broken') - .2}]
    if idx == 12: o += [{'type': 'datestamp', 'text': 'B · QUICKSAND', 'y': .2, 'from': .1}]
    if idx == 15: o += [{'type': 'label', 'text': 'STOPS AT YOUR WAIST', 'pos': [.5, .26], 'color': YEL, 'from': wt('waist') - .2}]
    if idx == 16: o += [{'type': 'label', 'text': 'NATURE STUDY, 2005', 'pos': [.5, .26], 'color': (200, 210, 220), 'from': .2}]
    if idx == 17: o += [{'type': 'label', 'text': 'THE REAL DANGER: THE TIDE', 'pos': [.5, .26], 'color': RED, 'from': wt('tide') - .1}]
    if idx == 19: o += [{'type': 'datestamp', 'text': 'STRAIT OF MAGELLAN, CHILE · FEB 2025', 'y': .2, 'from': .1},
                        {'type': 'bubble', 'text': 'I thought I was dead.', 'pos': [.5, .3], 'from': wt('popped') - .1, 'size': 56},
                        {'type': 'label', 'text': '- ADRIAN SIMANCAS', 'pos': [.5, .365], 'color': (220, 225, 230), 'from': wt('popped') + .3}]
    if idx == 20: o += [choice(win='a', from_=wt('wins') - .3, instant=False)]
    if idx == 21: o += [{'type': 'cta', 'text': 'FOLLOW FOR MORE WOULD YOU RATHERS', 'from': .1}]
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
