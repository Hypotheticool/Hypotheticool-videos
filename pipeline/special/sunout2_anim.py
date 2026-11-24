"""Animate every scene of "The Sun went out, Day 7 (Part 2)" (helpers from Part 1) over its Cycles plates (2D camera moves, cuts, particles, diagrams).
python3 sunout_anim.py <scene> [still_time]  ->  sunout/s<scene>/f_####.png + meta.json (overlays read by compose.py)"""
import sys, math, json, os
sys.path.insert(0, '/home/claude/pro')
import numpy as np, cv2, skia
import engine as E
ROOT = '/home/claude/b3d/sunout2'; CFG = json.load(open(f'{ROOT}/topic.json'))
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

def shake(img, t, amp=10, decay=3.0):
    a = amp * math.exp(-t * decay)
    if a < .5: return img
    dx, dy = a * math.sin(t * 71), a * math.cos(t * 53)
    return cv2.warpAffine(img, np.float32([[1, 0, dx], [0, 1, dy]]), (W, H), borderMode=cv2.BORDER_REFLECT)

def talk(t, amp=.006):   # small zoom bob while a character speaks
    return 1 + amp * (math.sin(t * 17) * .6 + math.sin(t * 11) * .4)

rng = np.random.default_rng(5); MOTES = rng.random((150, 4))
def motes(img, T, col=(120, 190, 255), k=1.0, region=(0, 0, 1, 1)):
    """dust motes drifting in the light (warm in sunlight, cool in the dark)"""
    lay = np.zeros_like(img)
    for x, y, s, b in MOTES:
        px = int((region[0] + x * (region[2] - region[0])) * W + math.sin(T * .6 + y * 9) * 20)
        py = int(((region[1] + y * (region[3] - region[1])) * H - T * 14 * (.3 + s)) % H)
        r = 1 + int(s * 3); v = (.25 + .75 * b * b) * k
        cv2.circle(lay, (px, py), r, tuple(c * v for c in col), -1, cv2.LINE_AA)
    return img + cv2.GaussianBlur(lay, (0, 0), 1.5)

def whip(img, t, dur=.12, dirx=1):
    """motion-blur whip into a new shot"""
    if t >= dur: return img
    k = int(70 * (1 - t / dur)) | 1
    if k < 3: return img
    ker = np.zeros((1, k), np.float32); ker[0, :] = 1 / k
    return cv2.filter2D(img, -1, ker)

def grade(img, mul=(1, 1, 1), add=0.0):
    return img * np.float32(mul)[None, None, :] + add

def vignette(img, s=.45):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = ((xx / W - .5) ** 2 * 1.6 + (yy / H - .5) ** 2) ** .5
    return img * (1 - s * np.clip(d - .25, 0, 1)[..., None] * 1.6)
VIG = None

# ---------------------------------------------------------------- skia drawing on top of a numpy frame
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

def sun_glow(img, x, y, r, k, T):
    """blazing Sun: hot core + corona + soft rays (2D, additive)"""
    def f(c):
        for rr, al, col in ((r * 6, .35, (255, 120, 30)), (r * 3, .6, (255, 170, 60)), (r * 1.6, .9, (255, 220, 150))):
            E.glow(c, x, y, rr * (1 + .03 * math.sin(T * 9)), col, al * k)
        p = E.P(E.C(255, 200, 120, 60 * k), 'stroke', 6, blur=8, add=True)
        for j in range(12):
            a = j / 12 * math.pi * 2 + T * .15; ln = r * (2.4 + .5 * math.sin(T * 5 + j))
            c.drawLine(x + math.cos(a) * r * 1.05, y + math.sin(a) * r * 1.05, x + math.cos(a) * ln, y + math.sin(a) * ln, p)
    return sk(img, f)

def find_sun(name):
    g = plate(name).mean(2); m = g > 245
    ys, xs = np.nonzero(m)
    return float(xs.mean()), float(ys.mean()), float(max(np.ptp(xs), np.ptp(ys)) / 2 + 1)

def earth_sprite(name='earth_dark'):
    """cut Earth's disc out of the earth_dark plate (for the orbit diagram)"""
    im = plate(name); g = im.mean(2); ys, xs = np.nonzero(g > 14)
    return im

# ---------------------------------------------------------------- diagrams
def orbit_diagram(T, u_fly, show_line=True, speed_badge=False, ang=200.0, sun_on=0.0):
    """top-down: where the Sun was (black hole of light), Earth's orbit (dashed), Earth leaving along the tangent. NOT TO SCALE."""
    def f(c):
        c.clear(E.C(4, 5, 12))
        for x, y, s, ph, b in E.STARS[:400]:
            tw = .55 + .45 * math.sin(T * 1.5 + ph); c.drawCircle(x % W, y % H, s * .8, E.P(E.C(220, 225, 255, 200 * b * tw)))
        cx, cy, R = W / 2, H * .4, 300
        c.drawCircle(cx, cy, 60, E.P(E.C(25, 25, 32))); c.drawCircle(cx, cy, 60, E.P(E.C(255, 160, 60, 140), 'stroke', 3))
        if sun_on > 0:
            E.glow(c, cx, cy, 260, (255, 150, 40), sun_on); c.drawCircle(cx, cy, 60, E.P(E.C(255, 230, 170, 255 * sun_on)))
        text(c, 'SUN' if sun_on > .5 else 'SUN (GONE)', cx, cy + 115, 46, (255, 170, 80))
        p = E.P(E.C(150, 180, 255, 150), 'stroke', 4); p.setPathEffect(skia.DashPathEffect.Make([22, 18], 0))
        c.drawCircle(cx, cy, R, p)
        a0 = math.radians(ang); ex, ey = cx + R * math.cos(a0), cy + R * math.sin(a0)
        tx, ty = -math.sin(a0), math.cos(a0)          # tangent (counter-clockwise motion seen from the north)
        if show_line:
            d = 430 * eout(u_fly)
            c.drawLine(ex, ey, ex + tx * d, ey + ty * d, E.P(E.C(255, 222, 40, 230), 'stroke', 7))
            px, py = ex + tx * d, ey + ty * d
        else: px, py = ex, ey
        E.glow(c, px, py, 70, (80, 150, 255), .7)
        c.drawCircle(px, py, 30, E.P(shader=E.radial(px - 8, py - 8, 34, [E.C(120, 180, 255), E.C(30, 80, 190), E.C(10, 30, 90)])))
        text(c, 'EARTH', px + 0, py - 52, 44)
        text(c, 'NOT TO SCALE', W / 2, H * .9, 34, (180, 190, 210), .8)
    return sk(np.zeros((H, W, 3), np.float32), f)

def thermometer(img, T, f_val, f_lo=-110, f_hi=80, x=None):
    """big 2D thermometer: °F on the left, °C on the right; mercury drops to f_val"""
    x = W * .5 if x is None else x; top, bot = H * .2, H * .56
    def yf(fv): return bot - (fv - f_lo) / (f_hi - f_lo) * (bot - top)
    def f(c):
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeLTRB(x - 46, top - 40, x + 46, bot + 30), 46, 46), E.P(E.C(230, 235, 245, 70)))
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeLTRB(x - 46, top - 40, x + 46, bot + 30), 46, 46), E.P(E.C(255, 255, 255, 160), 'stroke', 5))
        c.drawCircle(x, bot + 70, 80, E.P(E.C(60, 170, 255)))
        c.drawRect(skia.Rect.MakeLTRB(x - 22, yf(f_val), x + 22, bot + 40), E.P(E.C(60, 170, 255)))
        E.glow(c, x, yf(f_val), 60, (80, 180, 255), .5)
        for fv in (60, 32, 0, -50, -100):
            yy = yf(fv); c.drawLine(x - 70, yy, x - 50, yy, E.P(E.C(255, 255, 255), 'stroke', 4))
            text(c, f'{fv}°F', x - 150, yy + 14, 40)
        for cv_ in (20, 0, -20, -40, -60, -80):
            fv = cv_ * 9 / 5 + 32; yy = yf(fv); c.drawLine(x + 50, yy, x + 70, yy, E.P(E.C(255, 255, 255), 'stroke', 4))
            text(c, f'{cv_}°C', x + 150, yy + 14, 40)
    return sk(img, f)

def frost(img, k, seed=3):
    """frost creeping in from the edges of the frame (soft, bluish-white, with fine crystal texture)"""
    r = np.random.default_rng(seed)
    n = cv2.GaussianBlur(cv2.resize(r.random((24, 14)).astype(np.float32), (W, H), interpolation=cv2.INTER_CUBIC), (0, 0), 20)
    n2 = cv2.resize(r.random((480, 270)).astype(np.float32), (W, H), interpolation=cv2.INTER_LINEAR)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    edge = np.minimum(np.minimum(xx / W, 1 - xx / W) * 1.6, np.minimum(yy / H, 1 - yy / H) * 2.6)
    m = np.clip((k * .55 - edge + .3 * (n - .5)) * 4, 0, 1)
    m = cv2.GaussianBlur(m, (0, 0), 6)[..., None]
    fro = cv2.GaussianBlur(img, (0, 0), 14) * .15 + np.float32([240, 228, 210]) * (.7 + .15 * n2[..., None])
    return img * (1 - m * .8) + fro * m * .8

def ocean_section(T, zoom=1.0):
    """cross-section: frozen ocean surface (ice) over liquid water (not to scale)"""
    def f(c):
        c.clear(E.C(3, 4, 10))
        for x, y, s, ph, b in E.STARS[:250]:
            if y < H * .3: c.drawCircle(x % W, y % (H * .3), s * .8, E.P(E.C(220, 225, 255, 180 * b)))
        c.save(); c.translate(W / 2, H * .45); c.scale(zoom, zoom); c.translate(-W / 2, -H * .45)
        ice0, ice1 = H * .33, H * .43
        c.drawRect(skia.Rect.MakeLTRB(-200, ice1, W + 200, H + 400), E.P(shader=E.linear((0, ice1), (0, H), [E.C(20, 60, 110), E.C(4, 14, 40)])))
        c.drawRect(skia.Rect.MakeLTRB(-200, ice0, W + 200, ice1), E.P(shader=E.linear((0, ice0), (0, ice1), [E.C(225, 240, 255), E.C(150, 195, 235)])))
        p = E.P(E.C(255, 255, 255, 120), 'stroke', 3)
        for k in range(9):
            x0 = (k * 157 + 40) % W; c.drawLine(x0, ice0 + 6, x0 + 40, ice0 + 60, p); c.drawLine(x0 + 40, ice0 + 60, x0 + 20, ice1 - 8, p)
        c.drawLine(-200, ice0, W + 200, ice0, E.P(E.C(255, 255, 255), 'stroke', 5))
        for j in range(40):   # slow currents/bubbles in the liquid water below
            bx = (j * 97 + T * 30 * (1 + j % 3)) % W; by = ice1 + 60 + (j * 211) % int(H * .5)
            c.drawCircle(bx, by, 3 + j % 4, E.P(E.C(140, 200, 255, 90)))
        c.restore()
    return sk(np.zeros((H, W, 3), np.float32), f)

def route(img, p0, p1, u, T):
    """glowing NY -> LA arc on the night-side Earth"""
    def f(c):
        (x0, y0), (x1, y1) = p0, p1; mx, my = (x0 + x1) / 2, min(y0, y1) - 160
        path = skia.Path(); path.moveTo(x0, y0); path.quadTo(mx, my, x1, y1)
        meas = skia.PathMeasure(path, False); L = meas.getLength(); seg = skia.Path(); meas.getSegment(0, L * eout(u), seg, True)
        c.drawPath(seg, E.P(E.C(255, 200, 60, 255), 'stroke', 9, blur=6)); c.drawPath(seg, E.P(E.C(255, 240, 180), 'stroke', 4))
        for (x, y) in (p0, p1): E.glow(c, x, y, 50, (255, 200, 80), .8); c.drawCircle(x, y, 9, E.P(E.C(255, 255, 255)))
        if u > 0:
            pos, tan = meas.getPosTan(L * eout(u)); E.glow(c, pos.x(), pos.y(), 70, (255, 230, 160), 1)
    return sk(img, f)

def marker(img, p, T):
    def f(c):
        x, y = p; ph = (T * 1.2) % 1
        c.drawCircle(x, y, 20 + 90 * ph, E.P(E.C(255, 200, 60, 255 * (1 - ph)), 'stroke', 5))
        E.glow(c, x, y, 60, (255, 170, 60), .9); c.drawCircle(x, y, 11, E.P(E.C(255, 255, 255)))
    return sk(img, f)

def pts(name):
    d = json.load(open(f'{ROOT}/plates/{name}.json')); return {k: (v[0] * W, v[1] * H) for k, v in d.items()}

def wilt(img, k):
    """plant losing its green: shift green pixels toward dull brown"""
    hsv = cv2.cvtColor(np.clip(img, 0, 255).astype(np.uint8), cv2.COLOR_BGR2HSV).astype(np.float32)
    green = ((hsv[..., 0] > 30) & (hsv[..., 0] < 90) & (hsv[..., 1] > 50)).astype(np.float32)
    green = cv2.GaussianBlur(green, (0, 0), 2)[..., None]
    brown = img.mean(2, keepdims=True) * np.float32([.45, .7, 1.0])
    return img * (1 - green * k) + brown * green * k

# ================================================================== scenes
# ================================================================== PART 2 helpers
def clock_frame(name, t, T, start_s=0, speed=1.0, zoom=(1.0, 1.08)):
    """clock plate with a sweeping red second hand (drawn in 2D at the clock's center)"""
    img = kb(name, t / 2.5, zoom[0], zoom[1])
    z = zoom[0] + (zoom[1] - zoom[0]) * ease(t / 2.5); cx, cy = W / 2, H / 2; rr = .26 * H * z * .85
    s = start_s + t * speed; a = s / 60 * 2 * math.pi
    def f(c):
        x1, y1 = cx + math.sin(a) * rr, cy - math.cos(a) * rr; x0, y0 = cx - math.sin(a) * rr * .2, cy + math.cos(a) * rr * .2
        c.drawLine(x0 + 4, y0 + 6, x1 + 4, y1 + 6, E.P(E.C(0, 0, 0, 90), 'stroke', 7, blur=4))
        c.drawLine(x0, y0, x1, y1, E.P(E.C(200, 20, 20), 'stroke', 6)); c.drawCircle(cx, cy, 14, E.P(E.C(200, 20, 20)))
    return sk(img, f)

def proj(x, y, u, z0, z1, c0, c1):
    t = ease(u); z = z0 + (z1 - z0) * t; cx = (c0[0] + (c1[0] - c0[0]) * t) * W; cy = (c0[1] + (c1[1] - c0[1]) * t) * H
    return (x - cx) * z + W / 2, (y - cy) * z + H / 2

def ptalk(name, t, u, z0, z1, c0=(.5, .5), c1=(.5, .5), amp=.007, warm=True):
    img = kb(name, u, z0, z1, c0, c1)
    img = cv2.warpAffine(img, cv2.getRotationMatrix2D((W / 2, H / 2), 0, talk(t, amp)), (W, H), borderMode=cv2.BORDER_REFLECT)
    return motes(img, t, (255, 180, 110) if warm else (200, 220, 255), .6)

SRNG = np.random.default_rng(11); PUFFS = SRNG.random((60, 4))
def steam(img, T, srcs, k=1.0, col=(235, 215, 200), rise=110, spread=90, size=70):
    """2D steam drifting up from source points (fractions of the frame): soft additive puffs that grow and fade"""
    lay = np.zeros_like(img)
    for sx, sy in srcs:
        for a, b, c, d in PUFFS:
            ph = (T * .18 + a) % 1.0
            x = sx * W + (b - .5) * spread * (.3 + ph * 2) + math.sin(T * .7 + c * 6) * 25 + ph * 60
            y = sy * H - ph * rise * 6
            r = size * (.35 + ph * 1.6) * (.7 + .6 * d); al = (1 - ph) * ph * 4 * .22 * k
            cv2.circle(lay, (int(x), int(y)), int(r), tuple(cc * al for cc in col), -1, cv2.LINE_AA)
    return img + cv2.GaussianBlur(lay, (0, 0), 28)

SN = np.random.default_rng(21).random((400, 3))
def snowfall(img, T, k=1.0, speed=120, n=400):
    lay = np.zeros_like(img)
    for x, y, s in SN[:n]:
        px = int((x * W + math.sin(T * 1.3 + y * 20) * 30) % W); py = int((y * H + T * speed * (.5 + s)) % H)
        cv2.circle(lay, (px, py), 1 + int(s * 4), (230 * k, 235 * k, 245 * k), -1, cv2.LINE_AA)
    return img + cv2.GaussianBlur(lay, (0, 0), 1.2)

def twinkle(img, T, k=1.0, n=500, region=(0, 0, 1, .55)):
    def f(c):
        for x, y, s, ph, b in E.STARS[:n]:
            xx = region[0] * W + (x % W) / W * (region[2] - region[0]) * W; yy = region[1] * H + (y % H) / H * (region[3] - region[1]) * H
            tw = .5 + .5 * math.sin(T * 2.2 + ph * 7); c.drawCircle(xx, yy, s * .9, E.P(E.C(225, 230, 255, 230 * b * tw * k)))
    mask = (cv2.GaussianBlur(img.mean(2), (0, 0), 4) < 30).astype(np.float32)[..., None]
    return img + sk(np.zeros_like(img), f) * mask

def section(T, u=1.0, habitat=False):
    """cross-section under Iceland: magma chamber heats rock and groundwater; a well brings the hot water up (NOT TO SCALE)"""
    def f(c):
        c.clear(E.C(3, 4, 10))
        for x, y, s, ph, b in E.STARS[:200]:
            if y % H < H * .22: c.drawCircle(x % W, y % (H * .22), s * .8, E.P(E.C(220, 225, 255, 180 * b)))
        g0 = H * .26
        layers = [(g0, H * .3, (225, 232, 240)), (H * .3, H * .44, (52, 46, 44)), (H * .44, H * .6, (38, 50, 66)), (H * .6, H * .78, (40, 32, 30)), (H * .78, H * 1.1, (60, 18, 8))]
        for y0, y1, col in layers: c.drawRect(skia.Rect.MakeLTRB(0, y0, W, y1), E.P(E.C(*col)))
        # magma chamber glow
        E.glow(c, W * .5, H * .9, 520, (255, 90, 20), .9 * (.85 + .15 * math.sin(T * 3)))
        c.drawOval(skia.Rect.MakeLTRB(W * .18, H * .8, W * .82, H * 1.0), E.P(shader=E.radial(W * .5, H * .9, 380, [E.C(255, 200, 90), E.C(240, 80, 15), E.C(120, 25, 5)])))
        # heat rising through rock into groundwater (wavy arrows)
        for j in range(5):
            x0 = W * (.25 + j * .125); ph = (T * .5 + j * .2) % 1
            pth = skia.Path(); pth.moveTo(x0, H * .8)
            for k in range(1, 13): pth.lineTo(x0 + 16 * math.sin(k * 1.3 + T * 4), H * .8 - k * H * .016)
            c.drawPath(pth, E.P(E.C(255, 140, 50, 200 * u), 'stroke', 6, blur=3))
        # groundwater layer gets hot: orange shimmer in the aquifer
        c.drawRect(skia.Rect.MakeLTRB(0, H * .44, W, H * .6), E.P(E.C(255, 120, 40, int(70 * u))))
        # well + steam up to the surface
        wx = W * .66; c.drawRect(skia.Rect.MakeLTRB(wx - 14, H * .22, wx + 14, H * .55), E.P(E.C(190, 195, 205)))
        for k in range(6):
            yy = H * .55 - ((T * 220 + k * 90) % (H * .3)); c.drawCircle(wx, yy, 10, E.P(E.C(255, 200, 120, 220)))
        c.drawRect(skia.Rect.MakeLTRB(wx - 60, H * .2, wx + 60, H * .265), E.P(E.C(120, 125, 135)))
        for k in range(4):
            ph = (T * .4 + k * .25) % 1; E.glow(c, wx + 30 * ph, H * .2 - ph * 160, 40 + 60 * ph, (240, 225, 210), .4 * (1 - ph))
        # home with warm windows, pipe from the well
        hx = W * .25; c.drawRect(skia.Rect.MakeLTRB(hx - 90, H * .2, hx + 90, H * .265), E.P(E.C(70, 60, 55)))
        pth = skia.Path(); pth.moveTo(hx - 110, H * .2); pth.lineTo(hx, H * .155); pth.lineTo(hx + 110, H * .2); pth.close(); c.drawPath(pth, E.P(E.C(140, 40, 30)))
        for dx in (-45, 45): c.drawRect(skia.Rect.MakeLTRB(hx + dx - 22, H * .215, hx + dx + 22, H * .245), E.P(E.C(255, 190, 90)))
        c.drawLine(hx + 90, H * .255, wx - 60, H * .255, E.P(E.C(255, 150, 60), 'stroke', 8))
        if habitat:
            c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeLTRB(W * .12, H * .48, W * .45, H * .56), 30, 30), E.P(E.C(90, 95, 105)))
            for k in range(4): c.drawRect(skia.Rect.MakeLTRB(W * (.15 + k * .07), H * .505, W * (.19 + k * .07), H * .53), E.P(E.C(255, 200, 110)))
        for y_, s_, col in ((H * .37, 'ROCK', (200, 200, 205)), (H * .53, 'HOT WATER', (255, 190, 120)), (H * .72, 'HOT ROCK', (230, 170, 140)), (H * .93, 'MAGMA', (255, 230, 160))):
            text(c, s_, W * .86 if s_ != 'MAGMA' else W * .5, y_, 40, col)
        text(c, 'NOT TO SCALE', W / 2, H * .965, 30, (190, 195, 210), .8)
    return sk(np.zeros((H, W, 3), np.float32), f)

def bars(T, u):
    """sunlight vs Earth's own heat, per square meter (areas of the squares are to scale)"""
    def f(c):
        c.clear(E.C(4, 6, 14))
        for x, y, s, ph, b in E.STARS[:250]: c.drawCircle(x % W, y % H, s * .7, E.P(E.C(220, 225, 255, 120 * b)))
        k = eout(clamp(u)); side = 620 * k; x0, y0 = W / 2 - 310, H * .2
        c.drawRect(skia.Rect.MakeLTRB(x0, y0, x0 + side, y0 + side), E.P(shader=E.linear((x0, y0), (x0 + 620, y0 + 620), [E.C(255, 220, 120), E.C(255, 140, 40)])))
        E.glow(c, W / 2, y0 + 310, 420, (255, 170, 60), .25 * k)
        text(c, 'SUNLIGHT', W / 2, y0 + 300, 72, (255, 255, 255), k)
        text(c, '~240 W PER m²', W / 2, y0 + 380, 50, (255, 255, 255), k)
        # Earth's heat: 0.09 W/m² -> square side = 620 * sqrt(0.09/240) ≈ 12 px
        s2 = 620 * math.sqrt(.09 / 240); yy = H * .555; kk = clamp((u - .5) / .3)
        if kk > 0:
            c.drawRect(skia.Rect.MakeLTRB(W / 2 - s2 / 2, yy, W / 2 + s2 / 2, yy + s2), E.P(E.C(255, 90, 40, 255 * kk)))
            E.glow(c, W / 2, yy + s2 / 2, 60, (255, 90, 40), .6 * kk)
            c.drawLine(W / 2, yy + s2 + 10, W / 2, H * .69, E.P(E.C(255, 255, 255, 200 * kk), 'stroke', 3))
            text(c, "EARTH'S OWN HEAT", W / 2, H * .73, 52, (255, 180, 140), kk)
            text(c, '~0.09 W PER m²', W / 2, H * .77, 44, (255, 255, 255), kk)
        text(c, 'AREAS TO SCALE', W / 2, H * .95, 32, (190, 195, 210), .8)
    return sk(np.zeros((H, W, 3), np.float32), f)

def thermo2(img, T, f_val, x=None):
    """deep-cold thermometer: +60 °F down to -420 °F (absolute zero is -460 °F)"""
    f_lo, f_hi = -420, 60; x = W * .5 if x is None else x; top, bot = H * .2, H * .56
    def yf(fv): return bot - (fv - f_lo) / (f_hi - f_lo) * (bot - top)
    def f(c):
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeLTRB(x - 46, top - 40, x + 46, bot + 30), 46, 46), E.P(E.C(230, 235, 245, 70)))
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeLTRB(x - 46, top - 40, x + 46, bot + 30), 46, 46), E.P(E.C(255, 255, 255, 160), 'stroke', 5))
        c.drawCircle(x, bot + 70, 80, E.P(E.C(150, 120, 255)))
        c.drawRect(skia.Rect.MakeLTRB(x - 22, yf(f_val), x + 22, bot + 40), E.P(E.C(150, 120, 255)))
        E.glow(c, x, yf(f_val), 60, (160, 140, 255), .5)
        for fv in (32, -100, -200, -300, -400):
            yy = yf(fv); c.drawLine(x - 70, yy, x - 50, yy, E.P(E.C(255, 255, 255), 'stroke', 4)); text(c, f'{fv}°F', x - 165, yy + 14, 40)
        for cv_ in (0, -100, -200):
            fv = cv_ * 9 / 5 + 32; yy = yf(fv); c.drawLine(x + 50, yy, x + 70, yy, E.P(E.C(255, 255, 255), 'stroke', 4)); text(c, f'{cv_}°C', x + 165, yy + 14, 40)
        yy = yf(-400); c.drawLine(x + 50, yy, x + 70, yy, E.P(E.C(255, 255, 255), 'stroke', 4)); text(c, '−240°C', x + 170, yy + 14, 40)
    return sk(img, f)

def thermo_frame(bg, T, f_val):
    def f(c):
        pass
    return thermometer(bg, T, f_val)

def shimmer(img, T, cx, cy, w, h, k=1.0):
    """heat haze: warp a region with a moving sine field"""
    x0, x1 = int(max(0, (cx - w / 2) * W)), int(min(W, (cx + w / 2) * W)); y0, y1 = int(max(0, (cy - h / 2) * H)), int(min(H, (cy + h / 2) * H))
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    dx = 6 * k * np.sin(yy * .05 + T * 9); dy = 3 * k * np.sin(xx * .04 + T * 7)
    out = img.copy(); out[y0:y1, x0:x1] = cv2.remap(img, xx + dx, yy + dy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT); return out

def smoke(img, T, sx, sy, k=1.0):
    """black-smoker plume: dark mineral-laden water billowing up (subtractive), with a hot glow at the orifice"""
    lay = np.zeros(img.shape[:2], np.float32)
    for a, b, c_, d in PUFFS:
        ph = (T * .35 + a) % 1.0
        x = sx * W + (b - .5) * 60 * (.3 + ph * 2) + math.sin(T * 1.3 + c_ * 6) * 20; y = sy * H - ph * 650
        r = 40 * (.4 + ph * 2.2) * (.7 + .6 * d); cv2.circle(lay, (int(x), int(y)), int(r), min(1.0, (1 - ph) * 1.6), -1, cv2.LINE_AA)
    lay = np.clip(cv2.GaussianBlur(lay, (0, 0), 18), 0, 1)[..., None] * k
    out = img * (1 - lay * .95) + np.float32([8, 9, 10]) * lay * .95
    def f(c): E.glow(c, sx * W, sy * H, 70, (255, 140, 50), .7 * k)
    return sk(out, f)

def microbes(img, T, k=1.0):
    def f(c):
        for j in range(90):
            x = (j * 137.5) % W + 20 * math.sin(T * 1.7 + j); y = H * .3 + (j * 211) % int(H * .45) + 15 * math.cos(T * 1.3 + j * .7)
            c.drawCircle(x, y, 5 + j % 4, E.P(E.C(140, 255, 200, 200 * k)))
            E.glow(c, x, y, 16, (120, 255, 190), .25 * k)
    return sk(img, f)

def badge_dark(img, k=.5): return img * (1 - k)

def icy(img, k):
    img = cv2.morphologyEx(img, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))   # no city lights millions of years later
    g = img.mean(2, keepdims=True); ice = g * np.float32([1.35, 1.15, .95]) + np.float32([30, 18, 8])
    return img * (1 - k) + ice * k

# ================================================================== scenes
STEAM_EXT = [(.585, .49), (.635, .47), (.79, .5)]   # stack tops in the plant_ext plate (fractions)
def ext_frame(t, T, u, z0=1.0, z1=1.12, c0=(.5, .5), c1=(.55, .45)):
    img = kb('plant_ext', u, z0, z1, c0, c1) * .82
    zz = z0 + (z1 - z0) * ease(u)
    srcs = [proj(x * W, y * H, u, z0, z1, c0, c1) for x, y in STEAM_EXT]
    img = steam(img, T, [(x / W, y / H) for x, y in srcs], 1.0, size=70 * zz)
    return snowfall(img, T, .45, 120, 220)

def S0(t, T):   # HOOK: the geothermal plant blazing with steam in the black, sunless "noon"
    c = 1.45
    if t < c: return shake(ext_frame(t, T, t / 3.0, 1.18, 1.32, (.6, .5), (.62, .46)), t, 6, 1.5)
    img = kb('plant_cast', (t - c) / 2.2, 1.02, 1.1, (.5, .55), (.5, .5))
    return whip(snowfall(steam(img, T, [(.62, .38), (.82, .35)], .8), T, .45, 120, 220), t - c)

def S1(t, T):
    x, y, r = find_sun('sun_earth'); co = wt('out') + .05; cn = wt('Now') - .1
    if t < co:
        u = t / 2; img = kb('sun_earth', u, 1.0, 1.06)
        return sun_glow(img, *proj(x, y, u, 1.0, 1.06, (.5, .5), (.5, .5)), r * 1.15, 1.0, T)
    if t < cn:
        img = kb('sun_earth_off', t / 2, 1.0, 1.06) + 220 * math.exp(-(t - co) * 7)
        return shake(img, t - co, 12, 3)
    p = pts('earth_iceland'); rf = (p['reykjavik'][0] / W, p['reykjavik'][1] / H); u = (t - cn) / 2.5
    img = kb('earth_iceland', u, 1.0, 1.15, (.5, .5), rf) * 1.6
    return whip(marker(img, proj(p['reykjavik'][0], p['reykjavik'][1], u, 1.0, 1.15, (.5, .5), rf), T), t - cn)

def S2(t, T):
    c = 2.0
    if t < c: return frost(snowfall(steam(kb('window_ice', t / c, 1.05, 1.15), T, [(.42, .48), (.58, .47)], .6, size=40), T, .5, 60), .12 + .12 * t / c)
    bg = frost(cv2.GaussianBlur(kb('wide_ice', 0, 1.1, 1.1), (0, 0), 14) * .5, .25)
    return whip(thermometer(bg, T, 40 - 50 * eout(clamp((t - c) / 1.8))), t - c)

def S3(t, T):
    c = 1.25
    if t < c: return clock_frame('clock_noon', t, T, start_s=0, speed=1.0, zoom=(1.05, 1.12))
    img = kb('cu_leo_noon', eout((t - c) / .9), 1.0, 1.12, (.5, .5), (.5, .47))
    img = cv2.warpAffine(img, cv2.getRotationMatrix2D((W / 2, H / 2), 0, talk(t, .01)), (W, H), borderMode=cv2.BORDER_REFLECT)
    return whip(shake(img, t - c, 9, 1.5), t - c)

def S4(t, T):
    c = wt('stars') - .25
    if t < c: return ptalk('cu_mia_explain', t, t / c, 1.04, 1.12, (.52, .5), (.5, .47))
    return whip(twinkle(kb('sky_noon', (t - c) / 2.5, 1.0, 1.1, (.5, .55), (.5, .45)), T, 1.0, 700, (0, 0, 1, .62)), t - c)

def S5(t, T):
    img = kb('wide_ice', t / (D + PAD), 1.12, 1.0, (.5, .55), (.5, .5), rot=-1.2 * (1 - ease(t / (D + PAD))))
    return motes(steam(img, T, [(.42, .5), (.56, .49)], .35, size=30), T, (255, 180, 110), .8)

def S6(t, T):
    z = 1.0 + .08 * ease(t / (D + PAD))
    img = section(T, clamp(t / 1.2))
    return cv2.warpAffine(img, cv2.getRotationMatrix2D((W / 2, H * .5), 0, z), (W, H), borderMode=cv2.BORDER_REFLECT)

def S7(t, T):
    c = 2.0
    if t < c:
        img = kb('plant_pipes', t / c, 1.0, 1.1, (.5, .5), (.55, .5))
        return snowfall(steam(img, T, [(.7, .42), (.85, .4)], .7), T, .7)
    return whip(ext_frame(t - c, T, (t - c) / 2.6, 1.0, 1.08, (.5, .5), (.55, .48)), t - c)

def S8(t, T):
    c = 2.3
    if t < c: return shimmer(motes(kb('rad_cu', t / c, 1.0, 1.1, (.5, .5), (.48, .55)) * .6, T, (255, 180, 110), 1.0), T, .5, .3, 1.0, .25, .8)
    return whip(motes(kb('wide_ice', (t - c) / 3, 1.0, 1.08, (.5, .5), (.5, .52)), T, (255, 180, 110), .8), t - c)

def S9(t, T): return ptalk('cu_kai_ask', t, t / (D + PAD), 1.03, 1.12, (.5, .5), (.5, .47))

def S10(t, T):
    c = wt("Earth") - .2
    if t < c: return ptalk('cu_mia_explain', t, t / c, 1.15, 1.22, (.5, .46), (.5, .45))
    return whip(bars(T, (t - c) / 2.0), t - c)

def S11(t, T):
    img = kb('cu_leo_ask', eout(t / 1.0), 1.0, 1.1, (.5, .5), (.5, .47))
    return motes(cv2.warpAffine(img, cv2.getRotationMatrix2D((W / 2, H / 2), 0, talk(t, .008)), (W, H), borderMode=cv2.BORDER_REFLECT), T, (255, 180, 110), .6)

def S12(t, T):
    c1 = 2.0; c2 = wt('underground') - .15
    if t < c1: return vignette(kb('sub_wide', t / c1, 1.0, 1.08, (.5, .5), (.47, .5)) * .8, .7)
    if t < c2: return whip(vignette(kb('sub_cu', (t - c1) / 2, 1.0, 1.08, (.5, .5), (.52, .5)) * .85, .6), t - c1)
    return whip(section(T, 1.0, habitat=True), t - c2)

def S13(t, T):
    c = 2.6
    if t < c:
        img = kb('vent_wide', t / c, 1.0, 1.1, (.5, .55), (.5, .5))
        return smoke(img, T, .5, .25, 1.0)
    return whip(microbes(kb('vent_worms', (t - c) / 3.5, 1.0, 1.1, (.5, .5), (.47, .52)), T, .0), t - c)

def S14(t, T):
    img = kb('vent_worms', t / (D + PAD), 1.15, 1.35, (.47, .52), (.5, .5))
    return microbes(img * .75, T, clamp((t - .4) / .8))

def S15(t, T):
    c = wt('Hot') - .2
    if t < c:
        img = kb('vent_wide', t / c, 1.4, 1.75, (.5, .38), (.5, .33))
        return shimmer(smoke(img, T, .5, .42, 1.0), T, .5, .3, .4, .3, 1.0)
    img = kb('vent_wide', (t - c) / 2.5, 1.9, 2.1, (.5, .34), (.5, .33))
    return whip(smoke(img, T, .5, .5, 1.0), t - c)

def S16(t, T):
    return frost(snowfall(twinkle(kb('tree', t / (D + PAD), 1.0, 1.15, (.5, .55), (.5, .45)), T, .8, 400, (0, 0, 1, .4)), T, .9), .25)

def S17(t, T):
    img = kb('cu_kai_cold', eout(t / 1.0), 1.0, 1.12, (.5, .5), (.5, .47))
    img = cv2.warpAffine(img, cv2.getRotationMatrix2D((W / 2, H / 2), 0, talk(t, .009)), (W, H), borderMode=cv2.BORDER_REFLECT)
    return frost(shake(img, t, 6, 2), .3)

def S18(t, T):
    c = wt('As') - .2
    bg = icy(cv2.GaussianBlur(kb('earth_dark', 0, 1.0, 1.0), (0, 0), 10) * .55, .6)
    if t < c: return thermo2(bg, T, 0 - 400 * eout(clamp((t - .3) / 2.6)))
    return whip(icy(kb('earth_dark', (t - c) / 2.5, 1.0, 1.1), .3 + .4 * clamp((t - c) / 2)), t - c)

def S19(t, T):
    c = 1.4
    if t < c: return icy(kb('earth_dark', t / c, 1.1, 1.2, (.5, .5), (.5, .48)), .75)
    img = icy(kb('tree', (t - c) / 2.5, 1.5, 1.65, (.5, .7), (.5, .72)), .5)
    return whip(snowfall(snowfall(img, T, 1.0, 260), T + 3, .7, 140), t - c)

def S20(t, T):
    c = 2.1
    if t < c: return ext_frame(t, T, t / 3.5, 1.0, 1.08, (.5, .5), (.55, .47))
    return whip(motes(kb('trio_ice', (t - c) / 2.5, 1.0, 1.08), T, (255, 180, 110), .8), t - c)

def S21(t, T):
    c = (D + PAD) - .75
    if t < c: return ptalk('cu_mia_warm', t, t / c, 1.03, 1.12, (.5, .5), (.5, .47))
    return whip(shake(ext_frame(0, T, 0, 1.18, 1.18, (.6, .5), (.6, .5)), 0, 6, 1.5), t - c)   # loop: the first frame again

# ---------------------------------------------------------------- overlays
YEL, WHITE, BLUE = (255, 222, 40), (255, 255, 255), (130, 200, 255)
def overlays():
    o = []
    if idx == 0: o += [{'type': 'hook', 'text': 'NO SUN FOR 7 DAYS|STILL ALIVE', 'y': .11}]
    if idx == 1: o += [{'type': 'label', 'text': 'PREVIOUSLY…', 'pos': [.5, .1], 'color': WHITE, 'from': .1},
                       {'type': 'label', 'text': 'ICELAND', 'pos': [.5, .16], 'color': YEL, 'from': wt('Iceland') - .1}]
    if idx == 2: o += [{'type': 'datestamp', 'text': 'DAY 7 · ICELAND', 'y': .08, 'from': .2},
                       {'type': 'badge', 'value': 'BELOW 0°F', 'unit': '(−18°C) EARTH AVERAGE', 'pos': [.5, .7], 'from': 2.6, 'size': 64}]
    if idx == 3: o += [{'type': 'datestamp', 'text': '12:00 PM · NOON', 'y': .08, 'from': .1}]
    if idx == 4: o += [{'type': 'label', 'text': 'NO SUNLIGHT = NO BLUE SKY', 'pos': [.5, .14], 'color': WHITE, 'from': wt('blue') - .2}]
    if idx == 6: o += [{'type': 'label', 'text': 'UNDER ICELAND', 'pos': [.5, .1], 'color': YEL, 'from': .2}]
    if idx == 7: o += [{'type': 'datestamp', 'text': 'HELLISHEIÐI POWER PLANT · ICELAND', 'y': .08, 'from': .2}]
    if idx == 8: o += [{'type': 'badge', 'value': '~9 IN 10', 'unit': 'HOMES HEATED BY THE EARTH', 'pos': [.5, .16], 'from': .5, 'size': 64}]
    if idx == 10: o += [{'type': 'label', 'text': 'THOUSANDS OF TIMES WEAKER', 'pos': [.5, .1], 'color': YEL, 'from': wt('thousands') - .1}]
    if idx == 12: o += [{'type': 'label', 'text': 'DEEP SUBMARINES', 'pos': [.5, .14], 'color': WHITE, 'from': .4},
                        {'type': 'label', 'text': 'NUCLEAR-POWERED SHELTERS', 'pos': [.5, .1], 'color': YEL, 'from': wt('underground')}]
    if idx == 13: o += [{'type': 'datestamp', 'text': 'GALÁPAGOS RIFT · FEB 1977', 'y': .08, 'from': .2},
                        {'type': 'label', 'text': 'NO SUNLIGHT DOWN HERE', 'pos': [.5, .14], 'color': WHITE, 'from': 2.8}]
    if idx == 14: o += [{'type': 'label', 'text': 'CHEMICALS → FOOD', 'pos': [.5, .14], 'color': YEL, 'from': .5},
                        {'type': 'label', 'text': '(CHEMOSYNTHESIS)', 'pos': [.5, .19], 'color': WHITE, 'from': .8}]
    if idx == 15: o += [{'type': 'badge', 'value': '~400°C', 'unit': '(750°F)', 'pos': [.5, .16], 'from': wt('four') - .1},
                        {'type': 'label', 'text': 'LEAD MELTS AT 327°C', 'pos': [.5, .25], 'color': YEL, 'from': wt('lead') - .2}]
    if idx == 16: o += [{'type': 'badge', 'value': 'DECADES', 'unit': 'BIG TREES LIVE ON STORED SUGAR', 'pos': [.5, .16], 'from': wt('decades') - .1, 'size': 64}]
    if idx == 18: o += [{'type': 'datestamp', 'text': 'MILLIONS OF YEARS LATER', 'y': .08, 'from': .2},
                        {'type': 'badge', 'value': '−400°F', 'unit': '(−240°C)', 'pos': [.5, .72], 'from': 2.4},
                        {'type': 'label', 'text': 'PLUTO: ABOUT −375 TO −400°F', 'pos': [.5, .16], 'color': BLUE, 'from': wt('Pluto') - .2}]
    if idx == 19: o += [{'type': 'label', 'text': 'NITROGEN + OXYGEN FREEZE', 'pos': [.5, .14], 'color': BLUE, 'from': .4}]
    if idx == 20: o += [{'type': 'badge', 'value': '100s', 'unit': 'OF YEARS OF VOLCANIC HEAT', 'pos': [.5, .16], 'from': wt('hundreds') - .1, 'size': 64}]
    if idx == 21: o += [{'type': 'cta', 'text': 'FOLLOW FOR MORE STORIES', 'from': .2}]
    return o

FN = globals()[f'S{idx}']
os.makedirs(f'{ROOT}/s{idx}', exist_ok=True)
if len(sys.argv) > 2:
    for ts in sys.argv[2:]:
        t = float(ts); img = FN(t, t); cv2.imwrite(f'{ROOT}/still_{idx}_{ts}.jpg', np.clip(img, 0, 255).astype(np.uint8)[::2, ::2], [cv2.IMWRITE_JPEG_QUALITY, 85])
    sys.exit()
for f in range(1, NF + 1):
    t = (f - 1) / FPS; img = FN(t, t + sum(CFG['durs'][:idx]))
    cv2.imwrite(f'{ROOT}/s{idx}/f_{f:04d}.png', np.clip(img, 0, 255).astype(np.uint8), [cv2.IMWRITE_PNG_COMPRESSION, 1])
json.dump({'frames': NF, 'overlays': overlays()}, open(f'{ROOT}/s{idx}/meta.json', 'w'))
print('scene', idx, 'frames', NF)
