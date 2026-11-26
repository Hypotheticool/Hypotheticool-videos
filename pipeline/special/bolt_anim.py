"""Animate every scene of the Pick-a-scenario "where do you hide from lightning?" over its Cycles plates (bolt_plate.py):
a painted 2D storm sky behind each plate, rain, lightning strikes with flash lighting, ground-current ripples and science graphics.
python3 bolt_anim.py <scene> [frames...]  ->  bolt/s<scene>/f_####.png + meta.json (overlays read by compose.py)"""
import sys, math, json, os
sys.path.insert(0, '/home/claude/pro')
import numpy as np, cv2, skia
import engine as E
ROOT = '/home/claude/b3d/bolt'; CFG = json.load(open(f'{ROOT}/topic.json'))
FPS = 24; PAD = .75; idx = int(sys.argv[1]); D = CFG['durs'][idx]; NF = int(math.ceil((D + PAD) * FPS))
W, H = 1080, 1920
ease = lambda t: .5 - .5 * math.cos(math.pi * min(max(t, 0), 1))
eout = lambda t: 1 - (1 - min(max(t, 0), 1)) ** 3
clamp = lambda t: min(max(t, 0), 1)
GOLD = (255, 205, 70); WHITE = (255, 255, 255); RED = (240, 70, 60); BOLT = (190, 215, 255); GREEN = (110, 235, 140)

# ---------------- painted storm sky (BGR float), drifting clouds; one sky for the whole video
def _noise(seed, size, oct_=5):
    r = np.random.default_rng(seed); acc = np.zeros(size, np.float32); amp = 1.0; tot = 0
    for o in range(oct_):
        s = 2 ** (o + 2); n = r.random((s * size[0] // size[1] + 2, s + 2)).astype(np.float32)
        acc += cv2.resize(n, (size[1], size[0]), interpolation=cv2.INTER_CUBIC) * amp; tot += amp; amp *= .55
    return acc / tot
CL = _noise(3, (900, 2400)); CL2 = _noise(9, (900, 2400))
def sky(T, horizon=.5, flash=0.0):
    t = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    top = np.float32((40, 24, 14)); mid = np.float32((70, 50, 38)); hz = np.float32((70, 110, 190))   # navy -> slate -> warm slit at the horizon
    y = np.clip(t / max(horizon, .05), 0, 1)[..., None]
    base = top * (1 - y) + mid * y
    glow = np.exp(-((t - horizon) / .025) ** 2)[..., None] * 1.0; base = base * (1 - glow * .6) + hz * glow * .9
    sh = int(T * 18) % 1200; c1 = np.roll(CL, -sh, axis=1)[:, :W]; c2 = np.roll(CL2, -int(T * 30) % 1200, axis=1)[:, :W]
    c = cv2.resize(np.clip((c1 * .7 + c2 * .5 - .45) * 2.2, 0, 1), (W, int(H * horizon) + 2))[:int(H * horizon) + 2]
    img = np.repeat(base[:, None, :], W, 1) if base.ndim == 2 else np.broadcast_to(base, (H, W, 3)).copy()
    img = np.array(img, np.float32); hh = c.shape[0]
    shade = (np.float32((26, 22, 20)) + np.float32((70, 64, 62)) * c[..., None] * (.4 + 1.6 * flash))
    m = (c[..., None] * .85)
    img[:hh] = img[:hh] * (1 - m) + shade * m
    return img + np.float32((255, 230, 210)) * flash * .35 * (1 - t[..., None] * .5)

PL = {}
def plate_rgba(name):
    if name not in PL:
        im = cv2.imread(f'{ROOT}/plates/{name}.png', cv2.IMREAD_UNCHANGED).astype(np.float32)
        im = cv2.resize(im, (W, H), interpolation=cv2.INTER_CUBIC)
        PL[name] = (im[..., :3], np.clip(im[..., 3:] / 255, 0, 1))
    return PL[name]
PTS = {}
def pts(name):
    if name not in PTS:
        d = {}
        p = f'{ROOT}/plates/{name}.txt'
        if os.path.exists(p):
            for ln in open(p):
                k, x, y = ln.split(); d[k] = (float(x), float(y))
        PTS[name] = d
    return PTS[name]
HORIZON = {'field': .62, 'under': .58, 'lake': .3, 'flat': .26, 'car': .45, 'tire': .2}

def scene(name, T, flash=0.0):
    rgb, a = plate_rgba(name); s = sky(T, HORIZON.get(name, .5), flash)
    lit = rgb * (1 + 1.6 * flash) + np.float32((60, 40, 30)) * flash
    return s * (1 - a) + lit * a

def kb(img, u, z0, z1, c0=(.5, .5), c1=(.5, .5)):
    t = ease(u); z = z0 + (z1 - z0) * t
    cx = (c0[0] + (c1[0] - c0[0]) * t) * W; cy = (c0[1] + (c1[1] - c0[1]) * t) * H
    M = np.float32([[z, 0, W / 2 - cx * z], [0, z, H / 2 - cy * z]])
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT), (z, cx, cy)
def to_screen(p, view): z, cx, cy = view; return (W / 2 + (p[0] * W - cx) * z, H / 2 + (p[1] * H - cy) * z)

rng = np.random.default_rng(5); RAIN = rng.random((420, 4))
def rain(img, T, k=1.0, slant=.18, speed=2300):
    lay = np.zeros_like(img)
    for x, y, s, b in RAIN:
        L = 40 + 90 * s; py = (y * (H + 300) + T * speed * (.6 + .6 * s)) % (H + 300) - 150; px = (x * (W + 400) + py * slant) % (W + 400) - 200
        v = (35 + 110 * b * b) * k; cv2.line(lay, (int(px), int(py)), (int(px + L * slant), int(py + L)), (v, v, v * .95), 1 + int(s * 2), cv2.LINE_AA)
    return img + cv2.GaussianBlur(lay, (0, 0), .9)

def ripples(img, T, y0=.55, k=1.0):
    """raindrop rings on water (perspective ellipses, smaller toward the horizon)"""
    lay = np.zeros_like(img)
    for x, y, s, b in RAIN[:160]:
        ph = (T * (1.2 + s) + b) % 1; yy = y0 + (1 - y0) * y; r = (6 + 50 * ph) * (.3 + (yy - y0) / (1 - y0))
        v = 120 * (1 - ph) * k; cv2.ellipse(lay, (int(x * W), int(yy * H)), (int(r * 2.2), max(1, int(r * .5))), 0, 0, 360, (v, v, v), 1, cv2.LINE_AA)
    return img + cv2.GaussianBlur(lay, (0, 0), .7)

# ---------------- lightning
def bolt_path(x0, y0, x1, y1, seed, rough=.22, depth=7):
    r = np.random.default_rng(seed); pts_ = [(x0, y0), (x1, y1)]
    for d in range(depth):
        new = [pts_[0]]
        for (ax, ay), (bx, by) in zip(pts_[:-1], pts_[1:]):
            L = math.hypot(bx - ax, by - ay); off = (r.random() - .5) * L * rough * 2
            nx, ny = -(by - ay) / max(L, 1e-3), (bx - ax) / max(L, 1e-3)
            new += [((ax + bx) / 2 + nx * off, (ay + by) / 2 + ny * off), (bx, by)]
        pts_ = new
    return pts_

def draw_bolt(img, x0, y0, x1, y1, seed, a=1.0, width=1.0, branches=4):
    if a <= 0: return img
    lay = np.zeros((H, W, 3), np.float32); main = bolt_path(x0, y0, x1, y1, seed)
    paths = [(main, 1.0)]; r = np.random.default_rng(seed + 1)
    for b in range(branches):
        i = int(r.integers(len(main) // 6, len(main) * 3 // 4)); bx, by = main[i]; L = math.hypot(x1 - x0, y1 - y0) * (.15 + .25 * r.random())
        ang = math.atan2(y1 - y0, x1 - x0) + (r.random() - .5) * 1.6
        paths.append((bolt_path(bx, by, bx + math.cos(ang) * L, by + math.sin(ang) * L, seed + 10 + b, .3, 5), .45))
    for pth, wk in paths:
        p = np.array(pth, np.int32).reshape(-1, 1, 2)
        cv2.polylines(lay, [p], False, (255, 235, 215), max(1, int(18 * width * wk)), cv2.LINE_AA)
    glow = cv2.GaussianBlur(lay, (0, 0), 28 * width) * 1.4 + cv2.GaussianBlur(lay, (0, 0), 7 * width)
    core = np.zeros_like(lay)
    for pth, wk in paths:
        p = np.array(pth, np.int32).reshape(-1, 1, 2); cv2.polylines(core, [p], False, (255, 255, 255), max(1, int(5 * width * wk)), cv2.LINE_AA)
    return img + (glow * np.float32((1.0, .85, .75)) * .9 + core) * a

def strike_env(T, t0=0.0):
    """a real flash flickers: a few return strokes over ~0.3 s, then fades"""
    t = T - t0
    if t < 0: return 0.0
    pulses = [(0, 1.0), (.08, .55), (.16, .9), (.3, .4)]
    return max([v * math.exp(-max(0, t - s) * 22) if t >= s else 0 for s, v in pulses] + [0])

def sparks(img, T, x, y, k=1.0):
    lay = np.zeros_like(img); t = max(T, 0)
    for xx, yy, s, b in RAIN[:120]:
        ang = math.pi * (1.0 + xx); sp = 300 + 900 * s; r = sp * t
        px = x + math.cos(ang) * r; py = y + math.sin(ang) * r * .8 + 900 * t * t
        v = 255 * b * math.exp(-t * 3) * k; cv2.circle(lay, (int(px), int(py)), 2 + int(4 * s), (v * .5, v * .8, v), -1, cv2.LINE_AA)
    return img + cv2.GaussianBlur(lay, (0, 0), 1.5)

def current_rings(img, T, x, y, k=1.0, squash=.28, n=5, speed=420, col=(255, 200, 120)):
    """current spreading out from the strike point across the ground or water surface (glowing perspective rings)"""
    lay = np.zeros_like(img)
    for j in range(n):
        r = (T * speed + j * 160) % (n * 160); fade = 1 - r / (n * 160)
        cv2.ellipse(lay, (int(x), int(y)), (int(r), max(1, int(r * squash))), 0, 0, 360, tuple(c * fade * k for c in col), 7, cv2.LINE_AA)
    return img + cv2.GaussianBlur(lay, (0, 0), 6) * 1.3 + cv2.GaussianBlur(lay, (0, 0), 1.5) * .6

def arc(img, x0, y0, x1, y1, T, seed=3, k=1.0):
    """side flash: a short crackling arc"""
    return draw_bolt(img, x0, y0, x1, y1, seed + int(T * 30), k, .55, branches=1)

# ---------------- skia helpers
def sk_begin(img):
    bgra = np.dstack([np.clip(img, 0, 255).astype(np.uint8), np.full((H, W), 255, np.uint8)])
    surf = skia.Surface(W, H); c = surf.getCanvas()
    c.drawImage(skia.Image.fromarray(np.ascontiguousarray(bgra), colorType=skia.kBGRA_8888_ColorType), 0, 0); return surf, c
def sk_end(surf): return surf.makeImageSnapshot().toarray()[..., :3].astype(np.float32)
def P(col, a=255, style='fill', w=0, blur=0):
    p = skia.Paint(AntiAlias=True, Color=skia.Color(int(col[0]), int(col[1]), int(col[2]), int(max(0, min(255, a)))))
    if style == 'stroke': p.setStyle(skia.Paint.kStroke_Style); p.setStrokeWidth(w); p.setStrokeCap(skia.Paint.kRound_Cap)
    if blur: p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, blur))
    return p
def text(c, s, x, y, size, col=WHITE, a=255, align='c'):
    f = skia.Font(E.TF, size); w = f.measureText(s); x0 = x - w / 2 if align == 'c' else (x - w if align == 'r' else x)
    c.drawString(s, x0, y, f, P((0, 0, 0), a * .85, 'stroke', size * .14)); c.drawString(s, x0, y, f, P(col, a))
def panel(c, x, y, w, h, a=200):
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, y, w, h), 34, 34), P((14, 20, 30), a))
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, y, w, h), 34, 34), P((120, 150, 180), 120, 'stroke', 3))

# ---------------- shots
def field(T, u, z0=1.0, z1=1.1, c0=(.5, .5), c1=(.5, .5), strike=None, rk=1.0, every=None):
    if every and strike is not None and T > strike: T_ = strike + (T - strike) % every
    else: T_ = T
    fl = strike_env(T_, strike) if strike is not None else .15 * strike_env(T % 2.3, 1.6)
    img = scene('field', T, fl); img, view = kb(img, u, z0, z1, c0, c1)
    if strike is not None and T >= strike:
        tx, ty = to_screen(pts('field')['top'], view); n_ = int((T - strike) / every) if every else 0
        img = draw_bolt(img, tx + 120, -60, tx - 10, ty + 40, 7 + n_, min(1, fl * 1.6 + (.25 if every else 0)), 1.2)
        img = sparks(img, (T_ - strike) * .6, tx, ty + 60, .8)
    return rain(img, T, rk)

def hook(T, u):   # frame 1 = the payoff: a huge bolt hitting the lone tree, the whole field lit up
    t = T % 1.1
    img = scene('field', T, .9 * strike_env(t, 0) + .25); img, view = kb(img, u, 1.25, 1.4, (.53, .48), (.53, .46))
    tx, ty = to_screen(pts('field')['top'], view)
    img = draw_bolt(img, tx + 160, -80, tx - 10, ty + 60, 7 + int(T / 1.1), max(.35, min(1, 1.2 * strike_env(t, 0) + .35)), 1.4)
    img = sparks(img, t * .8, tx, ty + 80, 1.0)
    return rain(img, T, .9)

def under(T, u, z0=1.0, z1=1.12, c0=(.5, .5), c1=(.5, .5), side=None, rk=1.0):
    T_ = side + (T - side) % .8 if side is not None and T > side else T
    fl = strike_env(T_, side) if side is not None else .12 * strike_env(T % 2.0, 1.2)
    img = scene('under', T, fl); img, view = kb(img, u, z0, z1, c0, c1)
    if side is not None and T >= side:
        p = pts('under'); x0, y0 = to_screen(p['trunk'], view); x1, y1 = to_screen(p['leo'], view)
        img = arc(img, x0, y0, x1 - 30, y1, T, 5, min(1, fl * 1.8 + .45))
        img = draw_bolt(img, x0 + 40, -50, x0, y0 - 300, 21, min(1, fl * 1.5), .9, 2)
    return rain(img, T, rk)

def lake(T, u, z0=1.0, z1=1.1, c0=(.5, .5), c1=(.5, .5), strike=None):
    fl = strike_env(T, strike) if strike is not None else .1 * strike_env(T % 2.1, 1.3)
    img = scene('lake', T, fl); img, view = kb(img, u, z0, z1, c0, c1)
    img = ripples(img, T, .34)
    if strike is not None and T >= strike:
        sx, sy = to_screen((.8, .56), view); img = draw_bolt(img, sx - 80, -60, sx, sy, 31, min(1, fl * 1.6 + .2 * clamp(1 - (T - strike))), 1.0)
        img = current_rings(img, T - strike, sx, sy + 10, min(1, (T - strike) * 3), squash=.18, n=6, speed=520, col=(255, 220, 160))
    return rain(img, T, .9)

def flat(T, u, z0=1.0, z1=1.1, c0=(.5, .5), c1=(.5, .5), strike=None):
    fl = strike_env(T, strike) if strike is not None else .1 * strike_env(T % 2.2, 1.4)
    img = scene('flat', T, fl); img, view = kb(img, u, z0, z1, c0, c1)
    if strike is not None and T >= strike:
        gx, gy = to_screen(pts('flat')['ground'], view); gx += 160
        img = draw_bolt(img, gx + 60, -60, gx, gy, 41, min(1, fl * 1.6 + .2), 1.0)
        img = current_rings(img, T - strike, gx, gy, min(1, (T - strike) * 3), squash=.2, n=6, speed=560)
    return rain(img, T, .9)

def car(T, u, z0=1.0, z1=1.1, c0=(.5, .5), c1=(.5, .5), strike=None):
    fl = strike_env(T, strike) if strike is not None else .1 * strike_env(T % 2.4, 1.5)
    img = scene('car', T, fl); img, view = kb(img, u, z0, z1, c0, c1)
    if strike is not None and T >= strike:
        p = pts('car'); rx, ry = to_screen(p['p3'], view)
        img = draw_bolt(img, rx + 70, -60, rx, ry, 51, min(1, fl * 1.6 + .25 * clamp(1 - (T - strike) * 2)), 1.0)
        t = T - strike   # current runs over the metal shell, down to the wheels, into the road
        lay = np.zeros_like(img)
        for chain in (['p3', 'p2', 'p1', 'p0', 'w0'], ['p3', 'p4', 'p5', 'p6', 'p7', 'w1']):
            P_ = [to_screen(p[k], view) for k in chain]; seg = clamp(t * 2.2) * (len(P_) - 1)
            for j in range(int(seg) + 1):
                if j >= len(P_) - 1: break
                f = min(1, seg - j); a0, a1 = P_[j], P_[j + 1]; e = (a0[0] + (a1[0] - a0[0]) * f, a0[1] + (a1[1] - a0[1]) * f)
                cv2.line(lay, (int(a0[0]), int(a0[1])), (int(e[0]), int(e[1])), (255, 225, 170), 9, cv2.LINE_AA)
        pulse = .7 + .3 * math.sin(T * 40)
        img = img + (cv2.GaussianBlur(lay, (0, 0), 10) * 1.4 + lay * .5) * pulse * clamp(2.2 - t)
        if t > .45:
            for k in ('w0', 'w1'):
                wx, wy = to_screen(p[k], view); img = current_rings(img, t - .45, wx, wy, clamp(1.6 - t), squash=.18, n=4, speed=300)
    return rain(img, T, .9)

LEO = None
def window(T, u):
    """close on the side window: Leo sitting inside, calm, rain running down the glass"""
    global LEO
    img, view = kb(scene('car', T, .08 * strike_env(T % 2.0, 1.1)), u, 2.5, 2.65, (.47, .47), (.46, .47))
    if LEO is None:
        im = cv2.imread(f'{ROOT}/plates/leobust.png', cv2.IMREAD_UNCHANGED).astype(np.float32)
        ys, xs = np.where(im[..., 3] > 8); im = im[ys.min():ys.max(), xs.min():xs.max()]; LEO = (im[..., :3], im[..., 3:] / 255)
    rgb, a = LEO; p = pts('car'); x0, y0 = to_screen(p['p4'], view); x1, _ = to_screen(p['p3'], view)
    h = 520; s = h / rgb.shape[0]; cx = (x0 + x1) / 2 + 40; top = y0 + 40
    r = cv2.resize(rgb, None, fx=s, fy=s); al = cv2.resize(a, None, fx=s, fy=s)[..., None]
    ys_, xs_ = int(top), int(cx - r.shape[1] / 2); y1_ = min(H, ys_ + r.shape[0]); x1_ = min(W, xs_ + r.shape[1])
    win_bottom = int(y0 + (to_screen(p['p1'], view)[1] - y0) * .95)
    clipH = max(0, min(y1_, win_bottom) - ys_)
    if clipH > 0:
        sub = img[ys_:ys_ + clipH, xs_:x1_]; rr = r[:clipH, :x1_ - xs_] * np.float32((.85, .9, 1.0)); aa = al[:clipH, :x1_ - xs_] * .9
        img[ys_:ys_ + clipH, xs_:x1_] = sub * (1 - aa) + rr * aa
    lay = np.zeros_like(img)   # drops running down the glass
    for x, y, s_, b in RAIN[:60]:
        px = x * W; py = (y * H + T * (60 + 200 * s_)) % H; cv2.circle(lay, (int(px), int(py)), 3 + int(5 * s_), (90 * b, 95 * b, 100 * b), -1, cv2.LINE_AA)
    return rain(img + cv2.GaussianBlur(lay, (0, 0), 1.2), T, .6)

def tire(T, u, z0=1.0, z1=1.15, c0=(.55, .55), c1=(.58, .58), x_from=None):
    img = scene('tire', T, .1 * strike_env(T % 2.0, .9)); img, view = kb(img, u, z0, z1, c0, c1)
    img = rain(img, T, .7)
    if x_from is not None and T > x_from:
        g = eout((T - x_from) * 4); surf, c = sk_begin(img); cx, cy, R = W * .55, H * .55, 300 * g
        c.drawLine(cx - R, cy - R, cx + R, cy + R, P(RED, 240, 'stroke', 34)); c.drawLine(cx + R, cy - R, cx - R, cy + R, P(RED, 240, 'stroke', 34))
        img = sk_end(surf)
    return img

def grid(T, u, hi=None, dim=0.0):
    """2x2 of the four options (numbered); hi = index highlighted"""
    tiles = [('field', (.53, .42), 1.25, lambda im, T: rain(im, T, .5)), ('lake', (.5, .45), 1.6, lambda im, T: ripples(im, T, .34)),
             ('flat', (.4, .5), 1.7, lambda im, T: im), ('car', (.5, .5), 1.7, lambda im, T: im)]
    out = np.zeros((H, W, 3), np.float32); tw, th = W // 2, H // 2
    for k, (nm, cc, z, fx) in enumerate(tiles):
        im = scene(nm, T); im, _ = kb(im, u, z, z * 1.05, cc, cc); im = fx(im, T)
        if nm == 'field': im = draw_bolt(im, W * .6, -40, W * .52, H * .4, 70 + int(T * 2), .5 * strike_env(T % 1.7, .3) + .1, .8)
        tile = cv2.resize(im[H // 4:H // 4 + H // 2 + 1, :][:, :], (tw, th))
        if hi is not None and k != hi: tile = tile * .35
        elif dim: tile = tile * (1 - dim)
        out[(k // 2) * th:(k // 2) * th + th, (k % 2) * tw:(k % 2) * tw + tw] = tile
    surf, c = sk_begin(out)
    for k in range(4):
        x, y = (k % 2) * tw, (k // 2) * th
        c.drawRect(skia.Rect.MakeXYWH(x + 3, y + 3, tw - 6, th - 6), P(GOLD if k == hi else (20, 25, 35), 255, 'stroke', 10 if k == hi else 6))
        c.drawCircle(x + 70, y + th - 80, 46, P((14, 20, 30), 230)); text(c, str(k + 1), x + 70, y + th - 58, 64, GOLD if k == hi else WHITE)
    return sk_end(surf)

def lie_diagram(T, u):
    """standing with feet together touches the ground in one spot; lying flat spans the ground the current is crossing"""
    img = flat(T, u, 1.1, 1.15, (.4, .5), (.4, .5)) * .35; surf, c = sk_begin(img)
    gy = 1070; panel(c, 70, 520, 940, 900)
    c.drawRect(skia.Rect.MakeXYWH(110, gy, 860, 200), P((40, 70, 35), 230))
    for j in range(5):   # current spreading through the ground from the left
        x = 110 + ((T * 260 + j * 170) % 860); c.drawLine(x, gy + 20, x, gy + 180, P(GOLD, 200 * (1 - (x - 110) / 860), 'stroke', 6))
    c.drawLine(110, gy + 100, 970, gy + 100, P(GOLD, 90, 'stroke', 3))
    text(c, 'current in the ground  →', 540, gy + 270, 54, GOLD)
    # crouched figure (feet together) vs lying figure
    c.drawCircle(300, gy - 300, 60, P(WHITE)); c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(255, gy - 235, 90, 160), 36, 36), P(WHITE))
    c.drawLine(288, gy - 80, 294, gy, P(WHITE, 255, 'stroke', 20)); c.drawLine(312, gy - 80, 306, gy, P(WHITE, 255, 'stroke', 20))
    c.drawLine(270, gy + 4, 330, gy + 4, P(GREEN, 255, 'stroke', 10))
    lx = 560; c.drawCircle(lx, gy - 48, 48, P(WHITE)); c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(lx + 40, gy - 84, 330, 84), 36, 36), P(WHITE))
    c.drawLine(lx - 48, gy + 4, lx + 370, gy + 4, P(RED, 255, 'stroke', 12))
    text(c, 'feet together', 300, 640, 58, GREEN); text(c, 'lying flat', 735, 640, 58, RED)
    text(c, 'diagram, not to scale', 540, 1400, 36, (180, 190, 205), 200)
    return sk_end(surf)

def thermo(T, u):
    """air heated by lightning vs the Sun's surface, same scale"""
    img = field(T, u, 1.2, 1.25, (.5, .45), (.5, .45)) * .35; surf, c = sk_begin(img)
    panel(c, 90, 520, 900, 900); base = 1330; top = 700; sc_ = (base - top) / 50000
    for k, (lab, val, col, x) in enumerate([("SUN'S SURFACE", 10000, (90, 170, 255), 330), ('AIR IN A BOLT', 50000, BOLT, 750)]):
        g = eout(u * 1.8 - k * .35); hh = val * sc_ * g
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeLTRB(x - 90, base - hh, x + 90, base), 22, 22), P(col, 240))
        text(c, f'~{int(round(val * g / 1000.0)) * 1000:,}°F', x, base - hh - 24, 50, col, 255 * clamp(g * 2))
        text(c, lab, x, base + 60, 42, WHITE, 255 * clamp(u * 3 - k))
    return sk_end(surf)

def tally(T, u):
    """Roy Sullivan, park ranger: 7 strikes survived (1942-1977)"""
    img = field(T, u, 1.05, 1.12, (.5, .5), (.5, .48)) * .55; n = min(7, int(u * 9.5))
    surf, c = sk_begin(img)
    for k in range(7):
        x = 150 + (k % 4) * 260 + (130 if k >= 4 else 0); y = 760 + (k // 4) * 300; on = k < n
        pth = skia.Path(); pts_ = [(0, -110), (-50, 10), (-5, 10), (-40, 120), (55, -20), (8, -20), (40, -110)]
        pth.moveTo(x + pts_[0][0], y + pts_[0][1]); [pth.lineTo(x + a, y + b) for a, b in pts_[1:]]; pth.close()
        if on: c.drawPath(pth, P(GOLD, 120, blur=18))
        c.drawPath(pth, P(GOLD if on else (70, 80, 95), 255 if on else 160))
    text(c, f'{n} / 7', W / 2, 1420, 110, GOLD)
    return sk_end(surf)

def people(T, u):
    """about 9 in 10 people struck by lightning survive"""
    img = field(T, u, 1.0, 1.05) * .4; surf, c = sk_begin(img); n = min(10, int(u * 16) + 1)
    for k in range(10):
        x = 160 + (k % 5) * 190; y = 780 + (k // 5) * 330; on = k < n; col = (WHITE if k < 9 else RED)
        a = 255 if on else 40
        c.drawCircle(x, y, 44, P(col, a)); c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x - 56, y + 56, 112, 160), 50, 50), P(col, a))
    text(c, '9 in 10 survive', W / 2, 1480, 84, GOLD, 255 * clamp(u * 2 - .6))
    return sk_end(surf)

def shots():
    return {
     0: [(0, hook), (1.35, lambda T, u: under(T, u, 1.05, 1.15, (.5, .48), (.5, .5), side=0.0))],
     1: [(0, lambda T, u: field(T, u, 1.0, 1.12, (.5, .5), (.5, .47))), (1.55, lambda T, u: grid(T, u))],
     2: [(0, lambda T, u: grid(T, u, hi=0)), (.95, lambda T, u: grid(T, u, hi=1)), (1.75, lambda T, u: grid(T, u, hi=2)), (2.75, lambda T, u: grid(T, u, hi=3))],
     3: [(0, lambda T, u: grid(T, u, dim=.45))],
     4: [(0, lambda T, u: under(T, u, 1.0, 1.15, (.5, .5), (.48, .55))), (1.9, lambda T, u: field(T, u, 1.35, 1.5, (.53, .45), (.53, .45)))],
     5: [(0, lambda T, u: field(T, u, 1.5, 1.65, (.53, .42), (.53, .45), strike=1.2)), (2.6, lambda T, u: under(T, u, 1.2, 1.3, (.5, .45), (.5, .45)))],
     6: [(0, lambda T, u: field(T, u, 1.15, 1.3, (.53, .5), (.53, .47), strike=.3)), (1.9, lambda T, u: under(T, u, 1.1, 1.25, (.5, .55), (.5, .52), side=.25))],
     7: [(0, lambda T, u: lake(T, u, 1.0, 1.12, (.5, .45), (.5, .42))), (1.6, lambda T, u: lake(T, u, 1.15, 1.25, (.6, .4), (.55, .42), strike=.3))],
     8: [(0, lambda T, u: flat(T, u, 1.3, 1.5, (.35, .5), (.33, .5))), (1.9, lambda T, u: flat(T, u, 1.0, 1.1, (.45, .45), (.45, .47)))],
     9: [(0, lambda T, u: flat(T, u, 1.1, 1.2, (.45, .45), (.45, .45), strike=.4)), (2.6, lambda T, u: flat(T, u, 1.4, 1.55, (.4, .5), (.4, .5), strike=0.0))],
     10: [(0, lie_diagram)],
     11: [(0, lambda T, u: car(T, u, 1.0, 1.15, (.5, .5), (.5, .52))), (2.0, window)],
     12: [(0, lambda T, u: tire(T, u, x_from=1.3)), (2.4, lambda T, u: tire(T, u, 1.25, 1.35, (.6, .6), (.6, .6), x_from=0.0))],
     13: [(0, lambda T, u: car(T, u, 1.15, 1.25, (.48, .5), (.48, .5), strike=.25)), (2.6, lambda T, u: car(T, u, 1.0, 1.05, (.5, .5), (.5, .5), strike=0.0))],
     14: [(0, lambda T, u: field(T, u, 1.7, 1.9, (.53, .4), (.53, .42), strike=.2, every=.75)), (2.4, thermo)],
     15: [(0, lambda T, u: car(T, u, 1.05, 1.2, (.5, .5), (.5, .5))), (2.0, window)],
     16: [(0, tally)],
     17: [(0, people), (3.3, lambda T, u: hook(T, u * .3))],    # ends on the hook frame: seamless loop
    }[idx]

OPTS = ['Under a tree', 'In a lake', 'Flat on the ground', 'Inside a car']
def opts(pick=None, instant=True, **kw):
    d = {'type': 'options', 'items': OPTS, 'instant': instant}
    if pick is not None: d['pick'] = pick
    d.update(kw); return d
OV = {
 0: [{'type': 'hook', 'text': '3 OF THESE ARE|LIGHTNING TRAPS', 'y': .11}],
 1: [opts(instant=False, **{'from': 1.0})],
 2: [opts()],
 3: [opts(), {'type': 'countdown', 'secs': 3, 'pos': [.5, .55]}],
 4: [opts(0), {'type': 'label', 'text': 'DRY... AND EXPOSED', 'color': [255, 222, 40], 'pos': [.5, .37], 'from': 2.0}],
 5: [opts(0), {'type': 'badge', 'value': '#2', 'unit': 'cause of lightning casualties', 'pos': [.5, .37], 'from': .8}],
 6: [opts(0), {'type': 'label', 'text': 'SIDE FLASH', 'color': [190, 215, 255], 'pos': [.5, .37], 'from': 2.3}],
 7: [opts(1), {'type': 'label', 'text': 'CURRENT SPREADS', 'color': [255, 222, 40], 'pos': [.5, .37], 'from': 2.2}],
 8: [opts(2)],
 9: [opts(2), {'type': 'badge', 'value': '3–5%', 'unit': 'of injuries: direct hits', 'pos': [.5, .37], 'from': 1.0}],
 10: [opts(2), {'type': 'label', 'text': 'NEVER LIE FLAT', 'color': [255, 100, 80], 'pos': [.5, .33], 'from': 1.6}],
 11: [opts(3), {'type': 'label', 'text': 'HARD METAL ROOF', 'color': [255, 222, 40], 'pos': [.5, .37], 'from': .6}],
 12: [opts(3), {'type': 'badge', 'value': '0', 'unit': 'protection from rubber tires', 'pos': [.5, .37], 'from': 1.4}],
 13: [opts(3), {'type': 'label', 'text': 'AROUND YOU, INTO THE GROUND', 'color': [255, 222, 40], 'pos': [.5, .37], 'from': 1.2}],
 14: [{'type': 'badge', 'value': '50,000°F', 'unit': 'air heated by a bolt', 'pos': [.5, .2], 'from': .5}, {'type': 'label', 'text': '5× THE SUN\'S SURFACE', 'color': [255, 222, 40], 'pos': [.5, .29], 'from': 3.2}],
 15: [opts(3), {'type': 'label', 'text': 'WINNER: THE CAR', 'color': [255, 222, 40], 'pos': [.5, .37], 'from': .3}, {'type': 'label', 'text': 'NOT A CONVERTIBLE', 'color': [255, 100, 80], 'pos': [.5, .44], 'from': 2.0}],
 16: [{'type': 'datestamp', 'text': 'Shenandoah National Park, Virginia · 1942–1977', 'y': .14, 'from': .2}, {'type': 'badge', 'value': '7 strikes', 'unit': 'Guinness record', 'pos': [.5, .25], 'from': 2.5}],
 17: [{'type': 'cta', 'text': 'FOLLOW FOR MORE SCENARIOS'}],
}[idx]

if __name__ == '__main__':
    out = f'{ROOT}/s{idx}'; os.makedirs(out, exist_ok=True)
    SH = shots(); bounds = [s for s, _ in SH] + [D + PAD]
    only = [int(a) for a in sys.argv[2:]]
    for f in (only or range(1, NF + 1)):
        T = (f - 1) / FPS - .35          # compose samples scene time T + XF; frame 1 = .35 s before the line starts
        Tc = max(T, 0); k = max(j for j in range(len(SH)) if SH[j][0] <= Tc or j == 0)
        t0, t1 = bounds[k], bounds[k + 1]; u = (Tc - t0) / max(t1 - t0, .1)
        img = SH[k][1](T - t0 + (.35 if k == 0 else 0), u)
        cv2.imwrite(f'{out}/f_{f:04d}.png', np.clip(img, 0, 255).astype(np.uint8), [cv2.IMWRITE_PNG_COMPRESSION, 1])
    json.dump({'frames': NF, 'overlays': OV}, open(f'{out}/meta.json', 'w'))
    print('scene', idx, NF)
