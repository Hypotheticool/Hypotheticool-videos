"""Animate every scene of the Pick-a-scenario "where do you hide from a tornado?" over its Cycles plates (tornado_plate.py):
a painted storm sky + rotating funnel behind the transparent-sky outdoor plates, wind shake, rain, flying debris sprites,
lightning, and the science graphics (wind squeeze, 15-20x chart, floor plan, walls, radar, hurricane comparison).
python3 tornado_anim.py <scene> [frames...]  ->  tornado/s<scene>/f_####.png + meta.json (overlays read by compose.py)"""
import sys, math, json, os
sys.path.insert(0, '/home/claude/pro')
import numpy as np, cv2, skia
import engine as E
ROOT = '/home/claude/b3d/tornado'; CFG = json.load(open(f'{ROOT}/topic.json'))
FPS = 24; PAD = .75; idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0; D = CFG['durs'][idx]; NF = int(math.ceil((D + PAD) * FPS))
W, H = 1080, 1920
ease = lambda t: .5 - .5 * math.cos(math.pi * min(max(t, 0), 1))
eout = lambda t: 1 - (1 - min(max(t, 0), 1)) ** 3
clamp = lambda t: min(max(t, 0), 1)
GOLD = (255, 205, 70); WHITE = (255, 255, 255); RED = (240, 70, 60); GREEN = (110, 235, 140)
rng = np.random.default_rng(5); PR = rng.random((500, 4))

# ---------------- storm sky (painted, BGR float)
def _fbm(w, h, seed, octaves=6):
    r = np.random.default_rng(seed); acc = np.zeros((h, w), np.float32); amp = 1.0; tot = 0
    for o in range(octaves):
        s = 2 ** (o + 2); n = r.random((s, max(2, int(s * w / h)))).astype(np.float32)
        acc += cv2.resize(n, (w, h), interpolation=cv2.INTER_CUBIC) * amp; tot += amp; amp *= .55
    acc /= tot; return (acc - acc.min()) / (acc.max() - acc.min() + 1e-6)
CL = _fbm(W * 2, H, 11)
def sky(T, dark=1.0):
    off = int((T * 40) % W); n = CL[:, off:off + W]
    yy = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    top = np.float32((34, 42, 38)); hor = np.float32((120, 158, 150))      # BGR: dark grey-green top, sickly green-grey glow at the horizon
    base = top + (hor - top) * (yy[..., None] ** 1.6)
    img = base * (.65 + .55 * n[..., None])
    return img * dark
# ---------------- tornado funnel (drawn into the sky layer, behind the plate)
def funnel(img, cx, base_y, top_y, wb, wt, T, a=1.0, dust=1.0):
    """rope-to-wedge funnel: narrow at the ground, widening into the cloud base; rotating streak texture; debris cloud at the base"""
    s2 = 2; h2, w2 = H // s2, W // s2
    yy, xx = np.mgrid[0:h2, 0:w2].astype(np.float32); yy *= s2; xx *= s2
    s = np.clip((base_y - yy) / max(base_y - top_y, 1), 0, 1)
    sway = 30 * np.sin(yy * .004 + T * 1.1) * (1 - s) + 18 * np.sin(T * .7)
    half = wb + (wt - wb) * s ** 2.0
    u = (xx - cx - sway) / half
    inside = np.clip((1 - np.abs(u)) * 3, 0, 1) * ((yy < base_y + 10) & (yy > top_y - 200))
    ang = np.arcsin(np.clip(u, -1, 1))
    streak = .5 + .5 * np.sin(ang * 5 + T * 9 - yy * .018) * np.cos(ang * 2.3 - T * 4 + yy * .007)
    shade = .55 + .45 * np.cos(ang - .7)                                          # lit a little from the left
    col = (np.float32((48, 54, 54)) * (.55 + .7 * streak[..., None]) * shade[..., None])
    al = inside * a * np.clip((base_y + 10 - yy) / 40, 0, 1)
    al = cv2.resize(al, (W, H)); col = cv2.resize(col, (W, H))
    img = img * (1 - al[..., None]) + col * al[..., None]
    # cloud base above the funnel (dark rotating wall cloud)
    yy1 = np.arange(H, dtype=np.float32)[:, None]; xx1 = np.arange(W, dtype=np.float32)[None]
    wc = np.clip(1 - ((xx1 - cx) / (wt * 2.6)) ** 2 - ((yy1 - top_y) / 170) ** 2, 0, 1) * a
    img = img * (1 - .85 * wc[..., None]) + np.float32((30, 36, 34)) * .85 * wc[..., None]
    # debris / dust cloud whirling at the ground
    if dust > 0:
        lay = np.zeros((H, W), np.float32)
        for k, (x, y, sz, b) in enumerate(PR[:220]):
            th = x * 6.283 + T * (2 + 3 * b); rr = wb * (1.2 + 2.6 * y)
            px = cx + rr * math.cos(th); py = base_y - 20 - 160 * sz * (1 + y) + .3 * rr * math.sin(th)
            cv2.circle(lay, (int(px), int(py)), 2 + int(sz * 7), .5 + .5 * b, -1, cv2.LINE_AA)
        lay = cv2.GaussianBlur(lay, (0, 0), 7) * a * dust
        dc = np.clip(1 - ((xx1 - cx) / (wb * 4.5)) ** 2 - ((yy1 - base_y + 60) / 110) ** 2, 0, 1) * .8 * a * dust
        m = np.clip(lay * 1.3 + dc, 0, 1)[..., None]
        img = img * (1 - m) + np.float32((45, 60, 75)) * m
    return img

# ---------------- plates and sprites
PL = {}
def plate(name):
    if name not in PL:
        im = cv2.imread(f'{ROOT}/plates/{name}.png', cv2.IMREAD_UNCHANGED).astype(np.float32)
        im = cv2.resize(im, (W, H), interpolation=cv2.INTER_CUBIC)
        if im.shape[2] == 4: PL[name] = (im[..., :3], im[..., 3:] / 255)
        else: PL[name] = (im, None)
    return PL[name]
SP = {}
def sprite_img(name):
    if name not in SP:
        im = cv2.imread(f'{ROOT}/plates/{name}.png', cv2.IMREAD_UNCHANGED).astype(np.float32)
        ys, xs = np.where(im[..., 3] > 6); im = im[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        SP[name] = (im[..., :3], im[..., 3:] / 255)
    return SP[name]
PT = {}
def pts(name):
    if name not in PT:
        d = {}; p = f'{ROOT}/plates/{name}.txt'
        if os.path.exists(p):
            for ln in open(p): k, x, y = ln.split(); d[k] = (float(x), float(y))
        PT[name] = d
    return PT[name]
HZ = {}
def horizon(name, x):
    """first opaque row in plate column x (0-1): where the ground/structure meets the sky"""
    if name not in HZ:
        _, al = plate(name); m = al[..., 0] > .5
        HZ[name] = np.where(m.any(0), m.argmax(0), H).astype(np.float32)
    return float(HZ[name][int(min(max(x, 0), .999) * W)])

def jitter(T, amp):
    if amp <= 0: return 0.0, 0.0, 0.0
    dx = amp * (math.sin(T * 23) + .6 * math.sin(T * 41 + 1) + .3 * math.sin(T * 67 + 2))
    dy = amp * (math.sin(T * 29 + 2) + .5 * math.sin(T * 53) + .3 * math.sin(T * 71 + 4)) * .6
    return dx, dy, amp * .0006 * math.sin(T * 19 + 1)
def affine(u, z0, z1, c0, c1, T, shake):
    t = ease(u); z = z0 + (z1 - z0) * t
    cx = (c0[0] + (c1[0] - c0[0]) * t) * W; cy = (c0[1] + (c1[1] - c0[1]) * t) * H
    if shake > 0: z = max(z, 1.0) + shake / 400
    dx, dy, rot = jitter(T, shake); c, s = math.cos(rot) * z, math.sin(rot) * z
    return np.float32([[c, -s, W / 2 - c * cx + s * cy + dx], [s, c, H / 2 - s * cx - c * cy + dy]])
def warp(img, M): return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
def to_screen(p, M): x, y = p[0] * W, p[1] * H; return (M[0, 0] * x + M[0, 1] * y + M[0, 2], M[1, 0] * x + M[1, 1] * y + M[1, 2])

def paste(img, name, cx, cy, h, ang=0.0, a=1.0, tint=None):
    if a <= 0: return img
    rgb, al = sprite_img(name); s = h / max(rgb.shape[:2])
    hh, ww = rgb.shape[:2]; diag = int(math.hypot(hh, ww) * s) + 4
    M = cv2.getRotationMatrix2D((ww / 2, hh / 2), ang, s); M[0, 2] += diag / 2 - ww / 2; M[1, 2] += diag / 2 - hh / 2
    r = cv2.warpAffine(rgb, M, (diag, diag)); m = cv2.warpAffine(al, M, (diag, diag))[..., None] * a
    if tint is not None: r = r * np.float32(tint)
    x0, y0 = int(cx - diag / 2), int(cy - diag / 2); x1, y1 = x0 + diag, y0 + diag
    X0, Y0, X1, Y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
    if X1 <= X0 or Y1 <= Y0: return img
    sub = img[Y0:Y1, X0:X1]; rr = r[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0]; mm = m[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0]
    img[Y0:Y1, X0:X1] = sub * (1 - mm) + rr * mm; return img

def rain(img, T, k=1.0):
    lay = np.zeros((H, W), np.float32)
    for x, y, s, b in PR[:260]:
        py = (y * (H + 300) + T * (1500 + 900 * s)) % (H + 300) - 150; px = (x * (W + 400) + T * 700) % (W + 400) - 200
        cv2.line(lay, (int(px), int(py)), (int(px - 26), int(py - 60)), .35 + .4 * b, 1 + int(s * 2), cv2.LINE_AA)
    return img + cv2.GaussianBlur(lay, (0, 0), .8)[..., None] * np.float32((150, 165, 170)) * .5 * k
DEB = ['sp_board', 'sp_shingle', 'sp_metal', 'sp_board', 'sp_shingle']
def debris(img, T, n=8, seed=1, speed=1400, size=(120, 280), band=(.15, .7), k=1.0):
    """boards, shingles and sheet metal flying across in the wind"""
    r = np.random.default_rng(seed)
    for j in range(n):
        ph, yb, sz, sp = r.random(4)
        x = ((ph * (W + 900) + T * speed * (.6 + .6 * sp)) % (W + 900)) - 450
        y = (band[0] + (band[1] - band[0]) * yb) * H + 90 * math.sin(T * 3 + j) - 40 * (x / W)
        img = paste(img, DEB[j % len(DEB)], x, y, (size[0] + (size[1] - size[0]) * sz), (T * (400 + 500 * sp) + 90 * j) % 360, k)
    return img
def flash(img, T, times=(), k=1.0):
    for t0 in times:
        d = T - t0
        if 0 <= d < .25: img = img * (1 + k * (1.6 if d < .06 or .12 < d < .16 else .4)) + 18 * k
    return img
def grade(img, k=.0):
    g = img.mean(axis=2, keepdims=True); return img * (1 - k) + g * k

def outdoor(name, T, u, z0=1.0, z1=1.08, c0=(.5, .5), c1=(.5, .5), sh=6, fx=.6, fsc=1.0, fn=None, deb=6, rn=1.0, fl=(), dark=1.0, base_dy=0):
    """storm sky + funnel behind the plate; the plate's own alpha keeps the structures in front"""
    M = affine(u, z0, z1, c0, c1, T, sh)
    rgb, al = plate(name)
    sk = sky(T, dark)
    if fn is not False:
        hy = horizon(name, fx) + base_dy; top = max(-50, hy - 1600 * fsc)
        sk = funnel(sk, fx * W, hy, top, 26 * fsc, 260 * fsc, T)
    img = rgb * al + sk * (1 - al)
    img = warp(img, M)
    if deb: img = debris(img, T, deb, seed=len(name))
    img = rain(img, T, rn)
    return flash(img, T, fl), M
def indoor(name, T, u, z0=1.0, z1=1.08, c0=(.5, .5), c1=(.5, .5), sh=2, rumble=True):
    M = affine(u, z0, z1, c0, c1, T, sh); img = warp(plate(name)[0], M)
    if rumble:   # dust sifting down from the joists while the storm passes overhead
        lay = np.zeros((H, W), np.float32)
        for x, y, s, b in PR[:120]:
            py = (y * (H + 200) + T * (120 + 260 * s)) % (H + 200) - 100; cv2.circle(lay, (int(x * W + 10 * math.sin(T * 2 + b * 9)), int(py)), 1 + int(s * 2), .6 * b, -1, cv2.LINE_AA)
        img = img + cv2.GaussianBlur(lay, (0, 0), 1)[..., None] * np.float32((120, 140, 160))
    return img, M

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
def panel(c, x, y, w, h, a=215):
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, y, w, h), 34, 34), P((14, 20, 30), a))
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, y, w, h), 34, 34), P((120, 150, 180), 120, 'stroke', 3))
def arrow(c, x0, y0, x1, y1, col, a, w=12):
    c.drawLine(x0, y0, x1, y1, P(col, a, 'stroke', w)); ang = math.atan2(y1 - y0, x1 - x0); L = w * 3
    pth = skia.Path(); pth.moveTo(x1 + math.cos(ang) * L * .6, y1 + math.sin(ang) * L * .6)
    pth.lineTo(x1 + math.cos(ang + 2.5) * L, y1 + math.sin(ang + 2.5) * L); pth.lineTo(x1 + math.cos(ang - 2.5) * L, y1 + math.sin(ang - 2.5) * L); pth.close()
    c.drawPath(pth, P(col, a))

def fit(c, src0, src1, dst0, dst1):
    """map the graphic's vertical span src0-src1 into dst0-dst1 (keeps it between the top overlays and the captions)"""
    s = (dst1 - dst0) / (src1 - src0); c.save(); c.translate(540, (dst0 + dst1) / 2); c.scale(s, s); c.translate(-540, -(src0 + src1) / 2)

# ---------------- shots
FX = {'plains': .64, 'overpass': .58, 'car': .2, 'ditch': .25, 'mobile': .3, 'leocu': .8, 'overcu': .85, 'mobilecu': .7}
def S(name, **kw):
    def f(T, u):
        k = dict(fx=FX.get(name, .6)); k.update(kw); return outdoor(name, T, u, **k)[0]
    return f
def hook(T, u):
    img, M = outdoor('plains', T, u * .5 + .2, 1.12, 1.24, (.47, .47), (.49, .45), 9, fx=.62, fsc=1.35, deb=9, fl=(.15,))
    return img
def grid(T, u, hi=None, dim=0.0):
    tiles = [('overpass', dict(c=(.42, .4), z=1.25)), ('car', dict(c=(.5, .5), z=1.3)), ('mobile', dict(c=(.5, .47), z=1.35)), ('basement', dict(c=(.5, .5), z=1.1))]
    out = np.zeros((H, W, 3), np.float32); tw, th = W // 2, H // 2
    for k, (nm, d) in enumerate(tiles):
        if nm == 'basement': im = indoor(nm, T + k, u, d['z'], d['z'] * 1.04, d['c'], d['c'], 1, False)[0]
        else: im = outdoor(nm, T + k, u, d['z'], d['z'] * 1.04, d['c'], d['c'], 4, fx=FX[nm], deb=3)[0]
        tile = cv2.resize(im, (tw, th), interpolation=cv2.INTER_AREA)
        if hi is not None and k != hi: tile = tile * .35
        elif dim: tile = tile * (1 - dim)
        out[(k // 2) * th:(k // 2) * th + th, (k % 2) * tw:(k % 2) * tw + tw] = tile
    surf, c = sk_begin(out)
    for k in range(4):
        x, y = (k % 2) * tw, (k // 2) * th
        c.drawRect(skia.Rect.MakeXYWH(x + 3, y + 3, tw - 6, th - 6), P(GOLD if k == hi else (20, 25, 35), 255, 'stroke', 10 if k == hi else 6))
        c.drawCircle(x + 70, y + th - 80, 46, P((14, 20, 30), 230)); text(c, str(k + 1), x + 70, y + th - 58, 64, GOLD if k == hi else WHITE)
    return sk_end(surf)

def squeeze(T, u):
    """wind squeezing through the gap under the bridge (concept diagram)"""
    img = outdoor('overpass', T, u, 1.05, 1.1, sh=3, fx=.58, deb=0)[0] * .4
    p = pts('overpass'); gx, gy = p['gap'][0] * W, p['gap'][1] * H
    surf, c = sk_begin(img); g = eout(u * 2)
    for k in range(7):
        ph = (T * 1.6 + k / 7) % 1; y = gy - 260 + k * 85; x0 = -60 + ph * 300
        sq = gy - 40 + (y - gy) * .35
        pth = skia.Path(); pth.moveTo(x0 - 200, y); pth.cubicTo(x0 + 150, y, gx - 250, sq, gx, sq); pth.cubicTo(gx + 250, sq, W - x0 - 150, y, W - x0 + 200, y)
        c.drawPath(pth, P((150, 220, 235), 200 * g, 'stroke', 7))
    for k in range(3):
        xx = (gx - 180 + ((T * 900 + k * 260) % 520)); arrow(c, xx - 60, gy - 40 + (k - 1) * 30, xx + 40, gy - 40 + (k - 1) * 30, GOLD, 255 * g, 10)
    text(c, 'concept, not to scale', 540, 1450, 36, (190, 200, 215), 200 * g)
    return sk_end(surf)

def car_toss(T, u):
    img, M = outdoor('plains', T, u, 1.15, 1.22, (.6, .45), (.62, .44), 8, fx=.62, fsc=1.2, deb=7)
    t = T; x = W * .35 + 520 * t; y = H * .42 - 380 * t + 260 * t * t
    return paste(img, 'sp_car', x, y, 380, -170 * t)

def chart_mobile(T, u):
    img = outdoor('mobile', T, u, 1.05, 1.1, sh=3, fx=.3, deb=2)[0] * .3
    surf, c = sk_begin(img); fit(c, 560, 1440, 330, 1090); panel(c, 80, 560, 920, 880); g = eout(u * 2.2)
    text(c, 'RISK OF DYING IN A TORNADO', 540, 650, 50, WHITE)
    base = 1300; bw = 220
    # house = 1 unit; mobile home = 15-20 units (range shown as a solid bar to 15 and a lighter cap to 20)
    unit = 22
    hh = unit * g; c.drawRect(skia.Rect.MakeLTRB(230, base - hh, 230 + bw, base), P((150, 170, 190)))
    h15 = unit * 15 * g; h20 = unit * 20 * eout(u * 2.2 - .35)
    c.drawRect(skia.Rect.MakeLTRB(630, base - h20, 630 + bw, base), P(RED, 110)); c.drawRect(skia.Rect.MakeLTRB(630, base - h15, 630 + bw, base), P(RED))
    text(c, '1x', 340, base - hh - 24, 56, WHITE, 255 * g); text(c, '15-20x', 740, base - max(h15, h20) - 24, 64, GOLD, 255 * clamp(u * 2.2 - .4))
    text(c, 'regular house', 340, base + 60, 42, (200, 210, 225)); text(c, 'mobile home', 740, base + 60, 42, (200, 210, 225))
    text(c, 'source: National Weather Service', 540, 1420, 32, (160, 175, 195), 220)
    c.restore(); return sk_end(surf)

def floorplan(T, u):
    """lowest floor, seen from above: a small room in the middle, no windows, walls all around it"""
    img = indoor('bath', T, u, 1.1, 1.15, sh=1, rumble=False)[0] * .2
    surf, c = sk_begin(img); fit(c, 560, 1440, 540, 1100); panel(c, 80, 560, 920, 880); g = eout(u * 2.2)
    x0, y0, x1, y1 = 180, 660, 900, 1320
    c.drawRect(skia.Rect.MakeLTRB(x0, y0, x1, y1), P((190, 205, 220), 255 * g, 'stroke', 14))
    for (a, b) in [((x0, 900), (440, 900)), ((640, y0), (640, 860)), ((640, 1060), (x1, 1060)), ((440, 1100), (440, y1))]:
        c.drawLine(*a, *b, P((150, 165, 185), 255 * g, 'stroke', 8))
    for (wx, wy, ww, wh) in [(260, y0 - 6, 120, 12), (740, y0 - 6, 120, 12), (x1 - 6, 1180, 12, 100), (x0 - 6, 1000, 12, 100), (560, y1 - 6, 140, 12)]:
        c.drawRect(skia.Rect.MakeXYWH(wx, wy, ww, wh), P((120, 200, 240), 255 * g))     # windows on the outside walls
    k = clamp(u * 2.5 - .6); rx0, ry0, rx1, ry1 = 470, 930, 610, 1070
    c.drawRect(skia.Rect.MakeLTRB(rx0, ry0, rx1, ry1), P(GREEN, 120 * k)); c.drawRect(skia.Rect.MakeLTRB(rx0, ry0, rx1, ry1), P(GREEN, 255 * k, 'stroke', 10))
    text(c, 'small inside room', 540, 1400, 64, GREEN, 255 * k);
    text(c, 'windows', 320, y0 - 22, 44, (120, 200, 240), 255 * g)
    c.restore(); return sk_end(surf)

def walls(T, u):
    """as many walls as possible between you and the outside: nested walls, debris stopped by each one"""
    img = indoor('basement', T, u, 1.1, 1.14, sh=1, rumble=False)[0] * .25
    surf, c = sk_begin(img); cx, cy = 540, 1000; fit(c, 640, 1490, 450, 1100)
    n = 1 + int(clamp(u * 1.4) * 3 - 1e-6)
    for k in range(3):
        a = 255 if k < n else 40; r = 120 + k * 110
        c.drawRect(skia.Rect.MakeLTRB(cx - r, cy - r, cx + r, cy + r), P((190, 205, 220), a, 'stroke', 14))
    c.drawCircle(cx, cy - 20, 26, P(GOLD)); c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(cx - 30, cy + 10, 60, 50), 14, 14), P(GOLD))
    for j in range(6):    # debris flying in from the left, stopped at the outermost standing wall
        ph = (T * .9 + j / 6) % 1; stop = cx - (120 + (n - 1) * 110) - 20; x = -50 + (stop + 50) * min(1, ph * 1.6)
        y = cy - 250 + j * 100; c.save(); c.translate(x, y); c.rotate(T * 300 + j * 60); c.drawRect(skia.Rect.MakeXYWH(-40, -8, 80, 16), P((190, 140, 90), 230)); c.restore()
    text(c, f'{n} wall' + ('s' if n > 1 else ''), 540, 1470, 70, GOLD)
    c.restore(); return sk_end(surf)

def radar(T, u):
    """Doppler radar scope: the sweep finds the tornado's tight rotation (concept)"""
    img = outdoor('plains', T, u, 1.2, 1.25, sh=3, fx=.6, fsc=1.2, deb=0)[0] * .25
    surf, c = sk_begin(img); cx, cy, R = 540, 1000, 400; fit(c, 590, 1550, 560, 1100)
    c.drawCircle(cx, cy, R, P((10, 30, 20), 230))
    for k in range(1, 5): c.drawCircle(cx, cy, R * k / 4, P((60, 140, 90), 140, 'stroke', 2))
    c.drawLine(cx - R, cy, cx + R, cy, P((60, 140, 90), 120, 'stroke', 2)); c.drawLine(cx, cy - R, cx, cy + R, P((60, 140, 90), 120, 'stroke', 2))
    tx, ty = cx + 140, cy - 120
    for k in range(10):   # inbound (green) and outbound (red) side by side = rotation
        a = k / 10 * 6.283 + T * 3; rr = 18 + 4 * k
        c.drawCircle(tx - 24 + rr * .3 * math.cos(a), ty + rr * .3 * math.sin(a), 22 - k * 1.5, P((60, 230, 90), 200))
        c.drawCircle(tx + 24 + rr * .3 * math.cos(-a), ty + rr * .3 * math.sin(-a), 22 - k * 1.5, P((240, 60, 60), 200))
    ang = (T * 2.4) % (2 * math.pi)
    for k in range(18):
        a2 = ang - k * .03; c.drawLine(cx, cy, cx + R * math.cos(a2), cy + R * math.sin(a2), P((90, 255, 140), 140 * (1 - k / 18), 'stroke', 6))
    text(c, 'Doppler on Wheels radar', 540, cy + R + 80, 44, (190, 230, 200)); text(c, 'concept', 540, cy + R + 130, 32, (150, 170, 160))
    c.restore(); return sk_end(surf)

def hurricane(T, u):
    img = outdoor('plains', T, u, 1.2, 1.25, sh=3, fx=.6, fsc=1.2, deb=0)[0] * .28
    surf, c = sk_begin(img); fit(c, 560, 1440, 330, 1090); panel(c, 80, 560, 920, 880); g = eout(u * 2.2); g2 = eout(u * 2.2 - .4)
    text(c, 'WIND SPEED', 540, 650, 54, WHITE)
    base = 1300; s = 1.6
    h1 = 157 * s * g; h2 = 302 * s * g2
    c.drawRect(skia.Rect.MakeLTRB(220, base - h1, 460, base), P((110, 170, 230)))
    c.drawRect(skia.Rect.MakeLTRB(620, base - h2, 860, base), P(GOLD))
    text(c, '157+ mph', 340, base - h1 - 22, 54, WHITE, 255 * g); text(c, '~300 mph', 740, base - h2 - 22, 60, GOLD, 255 * g2)
    text(c, 'Category 5', 340, base + 56, 42, (200, 210, 225)); text(c, 'hurricane (minimum)', 340, base + 100, 34, (170, 185, 205))
    text(c, '1999 tornado', 740, base + 56, 42, (200, 210, 225)); text(c, '(radar estimate)', 740, base + 100, 34, (170, 185, 205))
    c.restore(); return sk_end(surf)

def shots():
    return {
     0: [(0, hook), (1.3, S('leocu', z0=1.0, z1=1.08, c0=(.5, .42), c1=(.5, .4), sh=8, deb=7, fl=(.5,)))],
     1: [(0, S('plains', z0=1.0, z1=1.1, c0=(.5, .5), c1=(.52, .47), sh=6, fsc=1.1)), (1.7, lambda T, u: grid(T, u))],
     2: [(0, lambda T, u: grid(T, u, hi=0)), (1.0, lambda T, u: grid(T, u, hi=1)), (1.85, lambda T, u: grid(T, u, hi=2)), (3.0, lambda T, u: grid(T, u, hi=3))],
     3: [(0, lambda T, u: grid(T, u, dim=.45))],
     4: [(0, S('overpass', z0=1.0, z1=1.1, c0=(.5, .5), c1=(.45, .47), sh=4, fsc=1.0)), (2.4, S('overpass', z0=1.6, z1=1.75, c0=(.3, .45), c1=(.3, .44), sh=4))],
     5: [(0, squeeze), (2.3, S('overcu', z0=1.0, z1=1.08, sh=10, deb=12, rn=1.4))],
     6: [(0, lambda T, u: grade(S('overpass', z0=1.1, z1=1.2, c0=(.5, .5), c1=(.5, .48), sh=3, deb=4, dark=.8)(T, u), .55) * .8),
         (2.8, lambda T, u: grade(S('overcu', z0=1.05, z1=1.12, sh=3, deb=5, dark=.8)(T, u), .55) * .75)],
     7: [(0, S('car', z0=1.0, z1=1.08, sh=4, fsc=.9)), (1.6, S('car', z0=1.4, z1=1.5, c0=(.42, .55), c1=(.42, .54), sh=6, fsc=.9))],
     8: [(0, S('car', z0=1.1, z1=1.2, c0=(.45, .52), c1=(.45, .5), sh=9, fsc=1.1, deb=8, fl=(1.0,))), (2.6, car_toss)],
     9: [(0, S('ditch', z0=1.0, z1=1.08, sh=6, deb=6)), (2.3, S('ditch', z0=1.5, z1=1.62, c0=(.45, .6), c1=(.45, .6), sh=6, deb=8))],
     10: [(0, S('mobile', z0=1.0, z1=1.1, c0=(.5, .5), c1=(.52, .49), sh=7, fsc=1.0, deb=7)), (2.6, S('mobilecu', z0=1.0, z1=1.1, c0=(.5, .55), c1=(.48, .58), sh=6, deb=5))],
     11: [(0, chart_mobile)],
     12: [(0, lambda T, u: indoor('basement', T, u, 1.0, 1.08)[0])],
     13: [(0, lambda T, u: indoor('basement', T, u, 1.1, 1.2, (.5, .55), (.48, .58))[0]), (1.9, lambda T, u: indoor('basecu', T, u, 1.0, 1.08)[0])],
     14: [(0, floorplan), (2.8, lambda T, u: indoor('bath', T, u, 1.0, 1.1, (.5, .5), (.5, .45))[0] * .62)],
     15: [(0, walls)],
     16: [(0, lambda T, u: indoor('basecu', T, u, 1.08, 1.18, (.5, .45), (.5, .43), 3)[0]), (1.9, S('plains', z0=1.3, z1=1.4, c0=(.5, .45), c1=(.5, .44), sh=9, fsc=1.2, deb=14))],
     17: [(0, S('plains', z0=1.15, z1=1.25, c0=(.55, .42), c1=(.57, .4), sh=6, fsc=1.4, fl=(.9,))), (2.2, radar)],
     18: [(0, hurricane)],
     19: [(0, S('plains', z0=1.0, z1=1.15, c0=(.5, .5), c1=(.55, .46), sh=6, fsc=1.0)), (2.2, lambda T, u: hook(T, u * .3))],
    }[idx]

OPTS = ['Under an overpass', 'In your car', 'In a mobile home', 'In the basement']
def opts(pick=None, instant=True, **kw):
    d = {'type': 'options', 'items': OPTS, 'instant': instant}
    if pick is not None: d['pick'] = pick
    d.update(kw); return d
Y = [255, 222, 40]; R_ = [255, 100, 80]; G_ = [120, 235, 140]; Wt = [235, 235, 235]
OV = {
 0: [{'type': 'hook', 'text': 'ONLY 1 OF THESE|IS THE SAFE SPOT', 'y': .11}],
 1: [opts(instant=False, **{'from': 1.7})],
 2: [opts()],
 3: [opts(), {'type': 'countdown', 'secs': 3, 'pos': [.5, .55]}],
 4: [opts(0), {'type': 'label', 'text': 'FEELS LIKE A BUNKER', 'color': Y, 'pos': [.5, .37], 'from': 2.4}],
 5: [opts(0), {'type': 'label', 'text': 'WIND CAN SPEED UP', 'color': R_, 'pos': [.5, .37], 'from': .6}, {'type': 'label', 'text': '+ FLYING DEBRIS', 'color': R_, 'pos': [.5, .42], 'from': 2.4}],
 6: [{'type': 'datestamp', 'text': 'OKLAHOMA · MAY 3, 1999', 'y': .1}, {'type': 'label', 'text': 'PEOPLE DIED UNDER OVERPASSES', 'color': R_, 'pos': [.5, .3], 'from': 1.6}],
 7: [opts(1)],
 8: [opts(1), {'type': 'label', 'text': 'NEVER TRY TO OUTRUN IT', 'color': R_, 'pos': [.5, .37], 'from': .3}],
 9: [opts(1), {'type': 'label', 'text': 'CAUGHT? LIE FLAT IN A DITCH', 'color': Y, 'pos': [.5, .37], 'from': .5}],
 10: [opts(2), {'type': 'label', 'text': 'EVEN TIED DOWN', 'color': R_, 'pos': [.5, .37], 'from': 2.8}],
 11: [],
 12: [opts(3), {'type': 'label', 'text': 'WINNER', 'color': G_, 'pos': [.5, .37], 'from': 1.5}],
 13: [opts(3), {'type': 'label', 'text': 'UNDER SOMETHING STURDY', 'color': Y, 'pos': [.5, .37], 'from': .3}, {'type': 'label', 'text': 'AWAY FROM WINDOWS', 'color': Wt, 'pos': [.5, .42], 'from': 2.2}],
 14: [{'type': 'label', 'text': 'NO BASEMENT?', 'color': Y, 'pos': [.5, .2], 'from': .1}, {'type': 'label', 'text': 'LOWEST FLOOR · SMALL INSIDE ROOM', 'color': Wt, 'pos': [.5, .26], 'from': 1.0}],
 15: [{'type': 'label', 'text': 'AS MANY WALLS AS YOU CAN', 'color': Y, 'pos': [.5, .2], 'from': .1}],
 16: [{'type': 'label', 'text': 'COVER YOUR HEAD', 'color': Y, 'pos': [.5, .2], 'from': .1}, {'type': 'label', 'text': 'FLYING DEBRIS: THE GREATEST DANGER', 'color': R_, 'pos': [.5, .26], 'from': 1.9}],
 17: [{'type': 'datestamp', 'text': 'BRIDGE CREEK, OKLAHOMA · MAY 3, 1999', 'y': .1}, {'type': 'badge', 'value': '~300', 'unit': 'mph', 'pos': [.5, .25], 'from': 1.4}],
 18: [],
 19: [{'type': 'cta', 'text': 'FOLLOW FOR MORE SCENARIOS'}],
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
