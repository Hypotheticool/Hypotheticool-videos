"""Animate every scene of "The Sun went out at 8:12 AM" over its Cycles plates (2D camera moves, cuts, particles, diagrams).
python3 sunout_anim.py <scene> [still_time]  ->  sunout/s<scene>/f_####.png + meta.json (overlays read by compose.py)"""
import sys, math, json, os
sys.path.insert(0, '/home/claude/pro')
import numpy as np, cv2, skia
import engine as E
ROOT = '/home/claude/b3d/sunout'; CFG = json.load(open(f'{ROOT}/topic.json'))
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
OV = []
def S0(t, T):   # HOOK: the Sun blazing, then it goes out (frame 1 = the payoff already in motion)
    x, y, r = find_sun('sun_earth'); u = t / (D + PAD)
    off = clamp((t - .95) / .12)
    if t < 1.07:
        img = kb('sun_earth', u, 1.12, 1.2, (.5, .5), (.48, .46))
        k = 1.0 + 1.3 * clamp((t - .55) / .4) ** 2              # flare up just before it dies
        img = sun_glow(img, *proj(x, y, u, 1.12, 1.2, (.5, .5), (.48, .46)), r * 1.18 * (1 - .65 * clamp((t - .7) / .35)), k, T)
        if t > .95: img = img + 255 * (1 - (t - .95) / .12)   # white flash
        return shake(img, max(0, t - .6), 14, 2)
    img = kb('sun_earth_off', u, 1.12, 1.2, (.5, .5), (.48, .46))
    img = img + 120 * math.exp(-(t - 1.07) * 5)
    return shake(img, t - 1.07, 10, 3)

def proj(x, y, u, z0, z1, c0, c1):
    t = ease(u); z = z0 + (z1 - z0) * t; cx = (c0[0] + (c1[0] - c0[0]) * t) * W; cy = (c0[1] + (c1[1] - c0[1]) * t) * H
    return (x - cx) * z + W / 2, (y - cy) * z + H / 2

def S1(t, T):
    c = 1.5
    if t < c: return motes(kb('wide_day', t / c, 1.0, 1.12, (.5, .5), (.5, .55)), T, (90, 170, 255), 1.2, (.25, .3, .75, .7))
    return whip(motes(kb('cu_leo_day', (t - c) / 2, 1.05, 1.13, (.5, .5), (.5, .48)), T, (90, 170, 255), .8), t - c)

def S2(t, T):
    c = 2.4
    if t < c:   # light leaving the Sun and arriving 8 min 20 s later (diagram over the space plate)
        x, y, r = find_sun('sun_earth'); u = t / c
        img = kb('sun_earth', u, 1.0, 1.05, (.5, .5), (.5, .5)) * .8
        xs, ys = proj(x, y, u, 1.0, 1.05, (.5, .5), (.5, .5)); ex, ey = proj(W * .42, H * .58, u, 1.0, 1.05, (.5, .5), (.5, .5))
        img = sun_glow(img, xs, ys, r, 1.0, T)
        def f(cv):
            p = E.P(E.C(255, 230, 160, 200), 'stroke', 4); p.setPathEffect(skia.DashPathEffect.Make([18, 14], -T * 60))
            cv.drawLine(xs, ys, ex, ey, p)
            k = eout(clamp((t - .3) / 1.8)); px, py = xs + (ex - xs) * k, ys + (ey - ys) * k
            E.glow(cv, px, py, 60, (255, 230, 150), 1.0)
            text(cv, '150 MILLION KM', W * .72, H * .53, 54, (255, 222, 40))
        return sk(img, f)
    return whip(clock_frame('clock', t - c, T, start_s=0), t - c)

CLOCK_C = None
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

def S3(t, T):
    c = 2.2
    if t < c: return motes(kb('bowl', t / c, 1.5, 1.7, (.42, .26), (.5, .25)), T, (100, 190, 255), 1.6)
    return whip(motes(kb('cu_kai_day', (t - c) / 2.4, 1.05, 1.12, (.5, .5), (.5, .47)), T, (90, 170, 255), .8), t - c, dirx=-1)

def S4(t, T):
    img = kb('cu_leo_day', t / (D + PAD), 1.22, 1.3, (.48, .45), (.5, .44))
    return motes(cv2.warpAffine(img, cv2.getRotationMatrix2D((W / 2, H / 2), 0, talk(t)), (W, H), borderMode=cv2.BORDER_REFLECT), T, (90, 170, 255), .8)

def S5(t, T):
    c1 = 1.7; cb = wt('black')
    if t < c1: return clock_frame('clock_820', t, T, start_s=11 + 9 * 0, speed=5.3, zoom=(1.05, 1.15))   # sweeps up to :20
    if t < cb: return whip(motes(kb('ots_day', (t - c1) / 2.5, 1.0, 1.06), T, (90, 170, 255), 1.0), t - c1)
    img = kb('ots_dark', (t - c1) / 2.5, 1.0, 1.06)
    img = img + 200 * math.exp(-(t - cb) * 9)
    return shake(img, t - cb, 16, 4)

def S6(t, T):
    img = kb('cu_kai_dark', eout(t / 1.2), 1.0, 1.18, (.5, .5), (.5, .47))
    img = cv2.warpAffine(img, cv2.getRotationMatrix2D((W / 2, H / 2), 0, talk(t, .008)), (W, H), borderMode=cv2.BORDER_REFLECT)
    return shake(motes(img, T, (255, 180, 110), .6), t, 8, 2.5)

def S7(t, T):
    m = clamp((t - wt('dark')) / .5)
    img = kb('window_moon', t / (D + PAD), 1.05, 1.25, (.5, .5), (.6, .42)) * (1 - m) + kb('window_dark', t / (D + PAD), 1.05, 1.25, (.5, .5), (.6, .42)) * m
    return img

def S8(t, T):
    img = kb('cu_mia_explain', t / (D + PAD), 1.04, 1.12, (.52, .5), (.5, .47))
    return motes(cv2.warpAffine(img, cv2.getRotationMatrix2D((W / 2, H / 2), 0, talk(t)), (W, H), borderMode=cv2.BORDER_REFLECT), T, (255, 180, 110), .6)

def S9(t, T):
    return motes(kb('wide_dark', t / (D + PAD), 1.15, 1.0, (.5, .55), (.5, .5), rot=-1.5 * (1 - ease(t / (D + PAD)))), T, (255, 180, 110), .7)

def S10(t, T):
    c = 2.6
    if t < c: return orbit_diagram(T, 0, show_line=False, ang=150 + 50 * t / c, sun_on=1 - clamp((t - .7) / .15))
    return whip(kb('earth_dark', (t - c) / 3.5, 1.0, 1.1, (.5, .5), (.47, .5)), t - c)

def S11(t, T):
    c = 1.6
    if t < c:   # Earth hurtling through space: star streaks
        img = kb('earth_dark', t / c, 1.1, 1.16, (.47, .5), (.45, .5))
        def f(cv):
            for x, y, s, ph, b in E.STARS[:220]:
                xx = (x - t * 900 * (.5 + b)) % W; cv.drawLine(xx, y % H, xx + 60 * (.5 + b), y % H, E.P(E.C(200, 215, 255, 120 * b), 'stroke', s * .7))
        lay = sk(np.zeros_like(img), f); mask = (cv2.GaussianBlur(img.mean(2), (0, 0), 6) < 12).astype(np.float32)[..., None]
        return img + lay * mask
    return whip(orbit_diagram(T, (t - c) / 1.8), t - c)

P_US = None
def S12(t, T):
    p = pts('earth_us'); img = kb('earth_us', 0, 1.0, 1.0)
    return route(img, p['ny'], p['la'], clamp((t - .4) / 2.4), T)

def S13(t, T):
    img = kb('cu_leo_dark', eout(t / 1.0), 1.0, 1.12, (.5, .5), (.5, .47))
    img = cv2.warpAffine(img, cv2.getRotationMatrix2D((W / 2, H / 2), 0, talk(t, .01)), (W, H), borderMode=cv2.BORDER_REFLECT)
    return shake(img, t, 9, 1.5)

def S14(t, T):
    c = 1.7
    if t < c: return motes(kb('cu_mia_dark', t / c, 1.04, 1.12, (.5, .5), (.5, .47)), T, (255, 180, 110), .6)
    return whip(motes(kb('trio_dark', (t - c) / 2.2, 1.0, 1.08, (.5, .5), (.5, .5)), T, (255, 180, 110), .6), t - c)

def S15(t, T):
    c = 2.6
    if t < c: return wilt(kb('plant_dark', t / c, 1.0, 1.1, (.5, .5), (.5, .48)), .15 * t / c)
    return whip(wilt(kb('plant_dark', (t - c) / 3, 1.25, 1.35, (.5, .45), (.5, .44)), .4 + .5 * clamp((t - c) / 2.5)), t - c)

def S16(t, T):
    c = 2.3
    if t < c: return frost(kb('window_dark', t / c, 1.05, 1.15), .25 + .5 * t / c)
    bg = frost(cv2.GaussianBlur(kb('wide_dark', 0, 1.1, 1.1), (0, 0), 14) * .55, .5)
    fv = 70 - 70 * eout(clamp((t - c) / 1.8))
    return whip(thermometer(bg, T, fv), t - c)

def S17(t, T):
    return frost(kb('fridge_dark', t / (D + PAD), 1.0, 1.1, (.5, .5), (.47, .5)), .42 + .12 * t / (D + PAD))

def S18(t, T):
    c = 2.5
    if t < c:
        bg = frost(cv2.GaussianBlur(kb('wide_dark', 0, 1.1, 1.1), (0, 0), 14) * .5, .62)
        return thermometer(bg, T, -100 * eout(clamp(t / 1.9)))
    return whip(motes(kb('pole', (t - c) / 3.5, 1.0, 1.1, (.5, .5), (.52, .48)), T, (200, 220, 255), .7), t - c)

def S19(t, T):
    c = 2.6
    if t < c: return ocean_section(T, 1.0 + .05 * t / c)
    return whip(ocean_section(T, 1.25 + .1 * (t - c) / 2.5), t - c)

def S20(t, T):
    img = kb('cu_kai_ask', t / (D + PAD), 1.03, 1.12, (.5, .5), (.5, .47))
    return motes(cv2.warpAffine(img, cv2.getRotationMatrix2D((W / 2, H / 2), 0, talk(t)), (W, H), borderMode=cv2.BORDER_REFLECT), T, (255, 180, 110), .6)

def S21(t, T):
    c = wt('They') - .1
    if t < c:
        img = kb('cu_mia_explain', t / c, 1.15, 1.2, (.5, .46), (.5, .45))
        return cv2.warpAffine(img, cv2.getRotationMatrix2D((W / 2, H / 2), 0, talk(t)), (W, H), borderMode=cv2.BORDER_REFLECT)
    p = pts('earth_iceland'); return whip(marker(kb('earth_iceland', 0, 1.0, 1.0) * 1.5, p['reykjavik'], T), t - c)

def S22(t, T):
    c = wt('All') - .15
    if t < c: return motes(kb('trio_dark', t / c, 1.08, 1.15, (.5, .5), (.5, .48)), T, (255, 180, 110), .6)
    # loop: back to the blazing Sun (matches the first frame)
    x, y, r = find_sun('sun_earth'); u = 0
    img = kb('sun_earth', u, 1.12, 1.12, (.5, .5), (.5, .5))
    return whip(sun_glow(img, *proj(x, y, 0, 1.12, 1.12, (.5, .5), (.5, .5)), r * 1.18, 1.0, T), t - c)

# ---------------------------------------------------------------- overlays per scene (compose.py draws them at full res)
YEL, WHITE, BLUE = (255, 222, 40), (255, 255, 255), (130, 200, 255)
def overlays():
    o = []
    if idx == 0: o += [{'type': 'hook', 'text': 'THE SUN|WENT OUT', 'y': .11}]
    if idx == 1: o += [{'type': 'datestamp', 'text': '8:12 AM · A NORMAL MORNING', 'y': .08, 'from': .3}]
    if idx == 2: o += [{'type': 'badge', 'value': '8 MIN', 'unit': '20 SEC', 'pos': [.5, .2], 'from': 1.0}]
    if idx == 5: o += [{'type': 'datestamp', 'text': '8:20:20 AM', 'y': .08, 'from': .3}]
    if idx == 10: o += [{'type': 'label', 'text': 'GRAVITY ALSO MOVES', 'pos': [.5, .14], 'color': WHITE, 'from': .4},
                        {'type': 'label', 'text': 'AT LIGHT SPEED', 'pos': [.5, .19], 'color': YEL, 'from': .6}]
    if idx == 11: o += [{'type': 'badge', 'value': '18', 'unit': 'MILES PER SECOND', 'pos': [.5, .16], 'from': 1.7},
                        {'type': 'label', 'text': '(30 KM/S)', 'pos': [.5, .225], 'color': WHITE, 'from': 1.9}]
    if idx == 12:
        p = json.load(open(f'{ROOT}/plates/earth_us.json'))
        o += [{'type': 'label', 'text': 'NEW YORK', 'pos': [min(.85, p['ny'][0]), p['ny'][1] + .05], 'color': WHITE, 'from': .3},
              {'type': 'label', 'text': 'LOS ANGELES', 'pos': [max(.25, p['la'][0] + .05), p['la'][1] + .05], 'color': WHITE, 'from': .3},
              {'type': 'badge', 'value': '≈2', 'unit': 'MINUTES', 'pos': [.5, .16], 'from': 1.6}]
    if idx == 15: o += [{'type': 'label', 'text': 'PHOTOSYNTHESIS: OFF', 'pos': [.5, .15], 'color': YEL, 'from': .4},
                        {'type': 'badge', 'value': 'WEEKS', 'unit': 'MOST PLANTS DIE', 'pos': [.5, .22], 'from': 3.0, 'size': 64}]
    if idx == 16: o += [{'type': 'datestamp', 'text': 'DAY 7', 'y': .08, 'from': .2},
                        {'type': 'badge', 'value': '0°F', 'unit': '(−18°C)', 'pos': [.5, .7], 'from': 3.2}]
    if idx == 17: o += [{'type': 'label', 'text': '= INSIDE A FREEZER', 'pos': [.5, .16], 'color': BLUE, 'from': .3},
                        {'type': 'badge', 'value': '0°F', 'unit': '(−18°C)', 'pos': [.5, .23], 'from': .5}]
    if idx == 18: o += [{'type': 'datestamp', 'text': 'DAY 365', 'y': .08, 'from': .2},
                        {'type': 'badge', 'value': '−100°F', 'unit': '(−73°C)', 'pos': [.5, .7], 'from': 1.6},
                        {'type': 'label', 'text': 'SOUTH POLE WINTER: ABOUT −60°C', 'pos': [.5, .16], 'color': WHITE, 'from': 2.9}]
    if idx == 19: o += [{'type': 'label', 'text': 'ICE', 'pos': [.5, .4], 'color': (255, 255, 255), 'from': .5},
                        {'type': 'label', 'text': 'LIQUID WATER', 'pos': [.5, .52], 'color': BLUE, 'from': 1.2},
                        {'type': 'label', 'text': 'NOT TO SCALE', 'pos': [.5, .93], 'color': (180, 190, 210), 'from': .5}]
    if idx == 21: o += [{'type': 'label', 'text': 'ICELAND', 'pos': [.5, .15], 'color': YEL, 'from': wt('They') + .1},
                        {'type': 'badge', 'value': '~9 IN 10', 'unit': 'HOMES: GEOTHERMAL HEAT', 'pos': [.5, .22], 'from': wt('They') + .4, 'size': 64}]
    if idx == 22: o += [{'type': 'prompt', 'text': 'PART 2?', 'pos': [.5, .42], 'from': .2}, {'type': 'cta', 'text': 'FOLLOW FOR PART 2', 'from': .3}]
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
