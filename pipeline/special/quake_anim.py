"""Animate every scene of the Pick-a-scenario "where do you go when an earthquake hits?" over its Cycles plates (quake_plate.py):
2D camera shake with motion blur, falling sprites (books, lamp, frame, TV, bricks, glass), dust, and science graphics.
python3 quake_anim.py <scene> [frames...]  ->  quake/s<scene>/f_####.png + meta.json (overlays read by compose.py)"""
import sys, math, json, os
sys.path.insert(0, '/home/claude/pro')
import numpy as np, cv2, skia
import engine as E
ROOT = '/home/claude/b3d/quake'; CFG = json.load(open(f'{ROOT}/topic.json'))
FPS = 24; PAD = .75; idx = int(sys.argv[1]); D = CFG['durs'][idx]; NF = int(math.ceil((D + PAD) * FPS))
W, H = 1080, 1920
ease = lambda t: .5 - .5 * math.cos(math.pi * min(max(t, 0), 1))
eout = lambda t: 1 - (1 - min(max(t, 0), 1)) ** 3
clamp = lambda t: min(max(t, 0), 1)
GOLD = (255, 205, 70); WHITE = (255, 255, 255); RED = (240, 70, 60); GREEN = (110, 235, 140); TEAL = (110, 200, 210)
rng = np.random.default_rng(5); PR = rng.random((400, 4))

# ---------------- plates and sprites (BGR float)
PL = {}
def plate(name):
    if name not in PL:
        im = cv2.imread(f'{ROOT}/plates/{name}.png', cv2.IMREAD_COLOR).astype(np.float32)
        PL[name] = cv2.resize(im, (W, H), interpolation=cv2.INTER_CUBIC)
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

def jitter(T, amp):
    if amp <= 0: return 0.0, 0.0, 0.0
    dx = amp * (math.sin(T * 37) + .6 * math.sin(T * 61 + 1) + .3 * math.sin(T * 97 + 2))
    dy = amp * (math.sin(T * 43 + 2) + .5 * math.sin(T * 71) + .3 * math.sin(T * 89 + 4)) * .7
    return dx, dy, amp * .0009 * math.sin(T * 29 + 1)
def kb(img, u, z0, z1, c0=(.5, .5), c1=(.5, .5), T=0.0, shake=0.0):
    """Ken Burns push + earthquake shake (two sub-frames averaged = motion blur)"""
    t = ease(u); z = z0 + (z1 - z0) * t
    cx = (c0[0] + (c1[0] - c0[0]) * t) * W; cy = (c0[1] + (c1[1] - c0[1]) * t) * H
    if shake > 0: z = max(z, 1.0) + shake / 400
    outs = []
    for dt in ((0.0, .02) if shake > 0 else (0.0,)):
        dx, dy, rot = jitter(T + dt, shake)
        c, s = math.cos(rot) * z, math.sin(rot) * z
        M = np.float32([[c, -s, W / 2 - c * cx + s * cy + dx], [s, c, H / 2 - s * cx - c * cy + dy]])
        outs.append(cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT))
        view = M
    return (sum(outs) / len(outs)), view
def to_screen(p, M): x, y = p[0] * W, p[1] * H; return (M[0, 0] * x + M[0, 1] * y + M[0, 2], M[1, 0] * x + M[1, 1] * y + M[1, 2])

def paste(img, name, cx, cy, h, ang=0.0, a=1.0, tint=None):
    """composite an RGBA sprite centered at (cx, cy), h px tall, rotated by ang degrees"""
    if a <= 0: return img
    rgb, al = sprite_img(name); s = h / rgb.shape[0]
    hh, ww = rgb.shape[:2]; diag = int(math.hypot(hh, ww) * s) + 4
    M = cv2.getRotationMatrix2D((ww / 2, hh / 2), ang, s); M[0, 2] += diag / 2 - ww / 2; M[1, 2] += diag / 2 - hh / 2
    r = cv2.warpAffine(rgb, M, (diag, diag)); m = cv2.warpAffine(al, M, (diag, diag))[..., None] * a
    if tint is not None: r = r * np.float32(tint)
    x0, y0 = int(cx - diag / 2), int(cy - diag / 2); x1, y1 = x0 + diag, y0 + diag
    X0, Y0, X1, Y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
    if X1 <= X0 or Y1 <= Y0: return img
    sub = img[Y0:Y1, X0:X1]; rr = r[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0]; mm = m[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0]
    img[Y0:Y1, X0:X1] = sub * (1 - mm) + rr * mm; return img

def dust(img, T, k=1.0, n=160):
    """plaster dust and specks falling from the ceiling while it shakes"""
    lay = np.zeros_like(img)
    for x, y, s, b in PR[:n]:
        py = (y * (H + 200) + T * (180 + 420 * s)) % (H + 200) - 100; px = x * W + 14 * math.sin(T * 3 + b * 9)
        v = (60 + 140 * b) * k; cv2.circle(lay, (int(px), int(py)), 1 + int(s * 3), (v * .85, v * .9, v), -1, cv2.LINE_AA)
    return img + cv2.GaussianBlur(lay, (0, 0), 1.2)
def haze(img, k):
    return img * (1 - .18 * k) + np.float32((70, 80, 88)) * .18 * k
def falling(img, T, items, M=None):
    """items: (sprite, x, y (0-1 plate coords), h px, t0, vx px/s, spin deg/s, tint); gravity on screen"""
    for sp, x, y, h, t0, vx, spin, tint in items:
        t = T - t0
        if t < 0: continue
        sx, sy = to_screen((x, y), M) if M is not None else (x * W, y * H)
        img = paste(img, sp, sx + vx * t, sy + 2600 * t * t * .5, h, spin * t, 1.0, tint)
    return img

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

# ---------------- shots
BOOKS = [('sp_book', None), ('sp_book2', None), ('sp_book', (1.3, .7, .5)), ('sp_book2', (.5, 1.1, .6)), ('sp_book', (.4, .9, 1.2))]
def books_from(key, plate_name, t0, n=6, spread=.07, h=120, vx=(-260, 260), seed=1):
    r = np.random.default_rng(seed); p = pts(plate_name)[key]; out = []
    for k in range(n):
        sp, tint = BOOKS[k % len(BOOKS)]
        out.append((sp, p[0] + (r.random() - .5) * spread, p[1] + (r.random() - .5) * .02, h * (.8 + .4 * r.random()), t0 + k * .12 * r.random() + k * .05,
                    vx[0] + (vx[1] - vx[0]) * r.random(), (r.random() - .5) * 700, tint))
    return out

def room(T, u, z0=1.0, z1=1.08, c0=(.5, .5), c1=(.5, .5), sh=16, falls=None):
    img, M = kb(plate('room'), u, z0, z1, c0, c1, T, sh)
    if falls: img = falling(img, T, falls, M)
    return dust(haze(img, .4 * min(1, sh / 16)), T, .8 * min(1, sh / 12))
HOOK_FALLS = None
def hook(T, u):
    global HOOK_FALLS
    if HOOK_FALLS is None:
        HOOK_FALLS = books_from('shelf_top', 'room', -.3, 7, .09, 150, (-420, 120), 3) + books_from('shelf_mid', 'room', -.1, 4, .08, 140, (-380, 60), 4) \
            + [('sp_frame', pts('room')['frame'][0], pts('room')['frame'][1], 230, -.2, -60, -260, None)]
    t = T % 1.6
    return room(t, u * .5 + .25, 1.3, 1.38, (.42, .5), (.4, .48), 26, HOOK_FALLS)
def leocu(T, u, z0=1.0, z1=1.1, sh=12, falls=True):
    img, M = kb(plate('leocu'), u, z0, z1, (.5, .45), (.5, .42), T, sh)
    if falls: img = paste(img, 'sp_book2', W * .85 - 300 * T, 300 + 900 * T * T, 300, -200 * T)
    return dust(img, T, .8)
def door(T, u, z0=1.0, z1=1.1, c0=(.5, .5), c1=(.5, .5), sh=12, falls=None):
    img, M = kb(plate('door'), u, z0, z1, c0, c1, T, sh)
    if falls: img = falling(img, T, falls, M)
    return dust(haze(img, .3), T, .8)
def generic(name, T, u, z0=1.0, z1=1.1, c0=(.5, .5), c1=(.5, .5), sh=12, falls=None, k=.8):
    img, M = kb(plate(name), u, z0, z1, c0, c1, T, sh)
    if falls: img = falling(img, T, falls, M)
    return dust(haze(img, .3 * k), T, k)

def adobe(T, u, z0=1.0, z1=1.08, c0=(.5, .5), c1=(.5, .5)):
    """an early earthquake photo, recreated: sepia, grain, soft vignette, white photo border"""
    img, _ = kb(plate('adobe'), u, z0, z1, c0, c1)
    g = img.mean(axis=2, keepdims=True); sep = g * np.float32((.62, .82, 1.05)) * .95 + 10
    r = np.random.default_rng(int(T * 24)); sep = sep + r.normal(0, 7, (H, W, 1)).astype(np.float32)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32); vig = 1 - .55 * (((xx - W / 2) / W) ** 2 + ((yy - H / 2) / H) ** 2) * 2.4
    sep = sep * vig[..., None]
    out = np.full_like(img, 0); out[:] = np.float32((30, 34, 38))
    bx, by, bw, bh = 70, 520, W - 140, 1080
    crop = cv2.resize(sep[(H - 1300) // 2:(H - 1300) // 2 + 1300, :], (bw - 40, bh - 40))
    out[by:by + bh, bx:bx + bw] = np.float32((205, 225, 235)); out[by + 20:by + bh - 20, bx + 20:bx + bw - 20] = crop
    tilt = cv2.getRotationMatrix2D((W / 2, H / 2), -2 + 1.2 * ease(u), 1.0 + .05 * ease(u))
    return cv2.warpAffine(out, tilt, (W, H), borderMode=cv2.BORDER_CONSTANT, borderValue=(30, 34, 38))

def street(T, u, z0=1.0, z1=1.08, c0=(.5, .5), c1=(.5, .5), sh=14, t0=0.0):
    img, M = kb(plate('street'), u, z0, z1, c0, c1, T, sh)
    r = np.random.default_rng(9); p = pts('street'); items = []
    for k in range(14):   # bricks off the cornice and the parapet
        x = p['facade_top'][0] + (r.random() - .5) * .8; items.append(('sp_brick', x, p['facade_top'][1] + .02, 70 + 40 * r.random(), t0 + k * .17, (r.random() - .5) * 200, (r.random() - .5) * 600, None))
    for w in ('win1', 'win2'):   # glass from the upper windows
        for k in range(8):
            items.append(('sp_glass', p[w][0] + (r.random() - .5) * .12, p[w][1] + .04, 60 + 50 * r.random(), t0 + .3 + k * .14, (r.random() - .5) * 300, (r.random() - .5) * 900, None))
    img = falling(img, T, items, M)
    return dust(img, T, .6)

def grid(T, u, hi=None, dim=0.0):
    tiles = [('door', (.62, .45), 1.25), ('street', (.5, .55), 1.0), ('couch', (.4, .6), 1.15), ('table', (.45, .55), 1.15)]
    out = np.zeros((H, W, 3), np.float32); tw, th = W // 2, H // 2
    for k, (nm, cc, z) in enumerate(tiles):
        im, _ = kb(plate(nm), u, z, z * 1.05, cc, cc, T + k, 6)
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

def house_diagram(T, u):
    """a modern wood-frame wall: the doorway is framed like the rest of the wall (diagram, not to scale)"""
    img = door(T, u, 1.1, 1.15, sh=6) * .3; surf, c = sk_begin(img); panel(c, 60, 560, 960, 860)
    wood = (120, 170, 215); g = eout(u * 2.2)
    x0, x1, yb, yt = 130, 950, 1300, 720
    c.drawLine(x0, yb, x1, yb, P(wood, 255, 'stroke', 16)); c.drawLine(x0, yt, x1, yt, P(wood, 255, 'stroke', 16))
    n = 0
    for k in range(12):
        x = x0 + k * (x1 - x0) / 11
        if 560 < x < 760: continue
        if n / 10 < g: c.drawLine(x, yt, x, yb, P(wood, 255, 'stroke', 12))
        n += 1
    c.drawLine(560, yt + 150, 760, yt + 150, P(wood, 255, 'stroke', 16)); c.drawLine(560, yt + 150, 560, yb, P(wood, 255, 'stroke', 14)); c.drawLine(760, yt + 150, 760, yb, P(wood, 255, 'stroke', 14))
    a = 255 * clamp(u * 3 - 1)
    c.drawRect(skia.Rect.MakeLTRB(560, yt + 150, 760, yb), P(GOLD, .35 * a))
    text(c, 'doorway', 660, yb - 220, 46, GOLD, a)
    text(c, 'modern wood-frame wall', 540, 680, 46, WHITE, 255)
    text(c, 'diagram, not to scale', 540, 1380, 34, (180, 190, 205), 200)
    return sk_end(surf)

def couch(T, u, z0=1.0, z1=1.08, c0=(.5, .5), c1=(.5, .5), sh=10, tri=0.0, falls=None):
    img, M = kb(plate('couch'), u, z0, z1, c0, c1, T, sh)
    if falls: img = falling(img, T, falls, M)
    img = dust(haze(img, .3), T, .7)
    if tri > 0:   # the "void" next to the couch the email talks about
        p = pts('couch'); lx, ly = to_screen(p['leo'], M)
        surf, c = sk_begin(img); pth = skia.Path(); pth.moveTo(lx - 330, ly + 120); pth.lineTo(lx + 330, ly + 120); pth.lineTo(lx - 330, ly - 330); pth.close()
        c.drawPath(pth, P(GOLD, 60 * tri)); c.drawPath(pth, P(GOLD, 255 * tri, 'stroke', 8)); img = sk_end(surf)
    return img
def lamp_fall(T, t0):
    """the floor lamp beside the couch tips over (sprite rotates about its base)"""
    p = pts('couchnl')
    def f(img, M):
        t = max(0, T - t0); ang = min(80, 160 * t * t * 2.2)
        bx, by = to_screen(p['lampbase'], M); tx, ty = to_screen(p['lamp'], M); Lh = math.hypot(tx - bx, ty - by) * 1.12
        r = math.radians(ang); cx = bx - math.sin(r) * Lh / 2; cy = by - math.cos(r) * Lh / 2
        return paste(img, 'sp_lamp', cx, cy, Lh, ang)
    return f
def couch_lamp(T, u, t0=.6):
    img, M = kb(plate('couchnl'), u, 1.0, 1.06, (.5, .5), (.5, .5), T, 12)
    img = lamp_fall(T, t0)(img, M)
    return dust(haze(img, .3), T, .8)

def email(T, u):
    img = couch(T, u, 1.1, 1.15, sh=4) * .3; surf, c = sk_begin(img)
    g = eout(u * 3); y0 = 640 + 80 * (1 - g); panel(c, 90, y0, 900, 640, 235 * g)
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(90, y0, 900, 110), 34, 34), P((40, 60, 90), 235 * g))
    text(c, 'FW: FW: FW: Earthquake tip!!', 540, y0 + 72, 50, WHITE, 255 * g)
    for k, ln in enumerate(['Skip duck and cover.', 'Lie NEXT TO the sofa,', 'in the "Triangle of Life".']):
        text(c, ln, 140, y0 + 220 + k * 90, 52, (200, 210, 225), 255 * g, 'l')
    text(c, 'the advice, paraphrased', 140, y0 + 520, 40, (140, 160, 190), 255 * g, 'l')
    s = clamp((u - .48) * 6)
    if s > 0:
        c.save(); c.translate(540, y0 + 330); c.rotate(-12); c.scale(1 + 1.5 * (1 - s), 1 + 1.5 * (1 - s))
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(-370, -85, 740, 170), 20, 20), P(RED, 255 * s, 'stroke', 14))
        f = skia.Font(E.TF, 104); w = f.measureText('DISCREDITED'); c.drawString('DISCREDITED', -w / 2, 38, f, P(RED, 255 * s)); c.restore()
    return sk_end(surf)

def likely(T, u):
    """what hurts people in US quakes: falling and flying objects, far more often than a collapsing building"""
    img = room(T, u, 1.0, 1.05, sh=5) * .3; surf, c = sk_begin(img); panel(c, 70, 560, 940, 880)
    g = eout(u * 2.5)
    text(c, 'FAR MORE LIKELY', 540, 660, 62, GOLD, 255 * g)
    surf2 = sk_end(surf)
    for k, (sp, h) in enumerate([('sp_tv', 150), ('sp_lamp', 300), ('sp_book2', 170)]):
        surf2 = paste(surf2, sp, 250 + k * 290, 860, h * (.6 + .4 * g), 0, g)
    surf, c = sk_begin(surf2)
    text(c, 'TVs · lamps · bookcases', 540, 1080, 50, WHITE, 255 * g)
    g2 = eout(u * 2.5 - 1)
    c.drawLine(140, 1140, 940, 1140, P((90, 110, 140), 200 * g2, 'stroke', 3))
    text(c, 'LESS LIKELY', 540, 1230, 50, (170, 180, 200), 255 * g2)
    for k in range(3):   # a small collapsed-building pictogram
        c.drawRect(skia.Rect.MakeXYWH(450 + k * 60, 1270 + (k % 2) * 30, 50, 90 - (k % 2) * 30), P((150, 160, 180), 200 * g2))
    text(c, 'a building collapse', 540, 1420, 44, (170, 180, 200), 255 * g2)
    return sk_end(surf)

def steps(img, n, u):
    """DROP / COVER / HOLD ON pictogram chips at the top of the middle band"""
    surf, c = sk_begin(img); labels = ['DROP', 'COVER', 'HOLD ON']
    for k in range(3):
        on = k < n; x = 200 + k * 340; y = 560
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x - 150, y - 60, 300, 120), 60, 60), P(GOLD if on else (30, 36, 48), 235))
        f = skia.Font(E.TF, 56); w = f.measureText(labels[k]); c.drawString(labels[k], x - w / 2, y + 20, f, P((20, 20, 20) if on else (140, 150, 170)))
    return sk_end(surf)
def table(T, u, z0=1.0, z1=1.08, c0=(.5, .5), c1=(.5, .5), sh=10, name='table', slide=0.0, n=0):
    img, M = kb(plate(name), u, z0, z1, (c0[0] - slide * math.sin(T * 5) * .02, c0[1]), (c1[0] - slide * math.sin(T * 5) * .02, c1[1]), T, sh)
    img = dust(haze(img, .25), T, .6)
    return steps(img, n, u) if n else img

def october(T, u):
    img = table(T, u, 1.05, 1.1, sh=3) * .3; surf, c = sk_begin(img); panel(c, 90, 560, 900, 860)
    g = eout(u * 2.5)
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(330, 620, 420, 330), 26, 26), P((235, 235, 240), 255 * g))
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(330, 620, 420, 100), 26, 26), P(RED, 255 * g)); c.drawRect(skia.Rect.MakeXYWH(330, 690, 420, 30), P(RED, 255 * g))
    f = skia.Font(E.TF, 60); w = f.measureText('OCTOBER'); c.drawString('OCTOBER', 540 - w / 2, 695, f, P(WHITE, 255 * g))
    for k in range(5): c.drawLine(360 + k * 90, 760, 360 + k * 90, 920, P((180, 180, 190), 160 * g, 'stroke', 2))
    text(c, 'Great ShakeOut drill', 540, 1020, 50, WHITE, 255 * g)
    n = int(clamp(u * 1.6 - .2) * 60)
    for k in range(60):   # a growing crowd of drillers under their desks
        x = 150 + (k % 12) * 71; y = 1110 + (k // 12) * 58; a = 255 if k < n else 30
        c.drawCircle(x, y, 13, P(GOLD, a)); c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x - 18, y + 15, 36, 26), 10, 10), P(GOLD, a))
    text(c, 'millions practice every year', 540, 1440, 44, (190, 200, 215), 255 * clamp(u * 2 - .6))
    return sk_end(surf)

def shots():
    fly = books_from('shelf_top', 'door', .3, 6, .06, 120, (150, 520), 11) + books_from('shelf_mid', 'door', .7, 3, .06, 120, (180, 480), 12)
    door_items = fly + [('sp_frame', .08, .3, 200, 1.0, 360, 300, None)]
    return {
     0: [(0, hook), (1.25, lambda T, u: leocu(T, u, 1.05, 1.15, 14))],
     1: [(0, lambda T, u: room(T, u, 1.0, 1.1, (.5, .5), (.45, .5), 14)), (1.6, lambda T, u: grid(T, u))],
     2: [(0, lambda T, u: grid(T, u, hi=0)), (.85, lambda T, u: grid(T, u, hi=1)), (1.55, lambda T, u: grid(T, u, hi=2)), (2.45, lambda T, u: grid(T, u, hi=3))],
     3: [(0, lambda T, u: grid(T, u, dim=.45))],
     4: [(0, lambda T, u: door(T, u, 1.0, 1.1, (.5, .5), (.6, .5), 12)), (1.9, lambda T, u: door(T, u, 1.45, 1.6, (.66, .45), (.66, .43), 10))],
     5: [(0, lambda T, u: adobe(T, u, 1.0, 1.06)), (3.0, lambda T, u: adobe(T, u, 1.35, 1.5, (.5, .5), (.5, .47)))],
     6: [(0, house_diagram), (2.2, lambda T, u: door(T, u, 1.15, 1.25, (.6, .45), (.62, .45), 8))],
     7: [(0, lambda T, u: door(T, u, 1.05, 1.15, (.55, .5), (.6, .5), 14, door_items)), (2.5, lambda T, u: leocu(T, u, 1.0, 1.08, 12))],
     8: [(0, lambda T, u: generic('runin', T, u, 1.0, 1.12, (.5, .5), (.55, .48), 14)), (1.8, lambda T, u: street(T, u, 1.0, 1.06, (.5, .55), (.5, .55), 10, 9))],
     9: [(0, lambda T, u: generic('runin', T, u, 1.15, 1.25, (.55, .5), (.55, .5), 26)), (1.7, lambda T, u: generic('trip', T, u, 1.0, 1.1, (.5, .5), (.55, .5), 16))],
     10: [(0, lambda T, u: street(T, u, 1.0, 1.08, (.5, .55), (.5, .5), 14, .2)), (2.4, lambda T, u: street(T, u, 1.35, 1.45, (.5, .45), (.5, .47), 12, -.2))],
     11: [(0, lambda T, u: couch(T, u, 1.0, 1.1, (.5, .5), (.45, .55), 10)), (2.3, lambda T, u: couch(T, u, 1.1, 1.15, (.45, .55), (.45, .55), 6, tri=clamp(u * 3)))],
     12: [(0, email)],
     13: [(0, lambda T, u: couch_lamp(T, u, .4)), (2.7, likely)],
     14: [(0, lambda T, u: table(T, u, 1.0, 1.1, (.5, .5), (.5, .52), 10)), (1.8, lambda T, u: table(T, u, 1.0, 1.06, (.5, .5), (.5, .5), 8, 'tablecu'))],
     15: [(0, lambda T, u: table(T, u, 1.0, 1.08, (.5, .55), (.5, .55), 8, 'tablecu', n=1)), (1.65, lambda T, u: table(T, u, 1.1, 1.18, (.5, .55), (.5, .55), 10, n=1))],
     16: [(0, lambda T, u: table(T, u, 1.05, 1.12, (.5, .55), (.5, .55), 10, 'tablecu', n=2)), (1.5, lambda T, u: table(T, u, 1.12, 1.2, (.5, .55), (.5, .55), 12, 'tablecu', n=3)),
          (2.6, lambda T, u: table(T, u, 1.1, 1.1, (.5, .52), (.5, .52), 14, slide=1.0, n=3))],
     17: [(0, lambda T, u: generic('wall', T, u, 1.0, 1.1, (.5, .5), (.55, .5), 10)), (2.1, lambda T, u: generic('wall', T, u, 1.3, 1.4, (.6, .5), (.6, .5), 8))],
     18: [(0, lambda T, u: generic('bed', T, u, 1.0, 1.1, (.5, .5), (.5, .45), 8, k=.5)), (1.9, lambda T, u: generic('bed', T, u, 1.6, 1.75, (.55, .38), (.55, .36), 6, k=.4))],
     19: [(0, october), (2.5, lambda T, u: table(T, u, 1.0, 1.08, (.5, .5), (.5, .52), 4, n=3))],
     20: [(0, lambda T, u: room(T, u, 1.0, 1.15, (.5, .5), (.45, .5), 6 + 12 * u)), (2.3, lambda T, u: hook(T, u * .3))],
    }[idx]

OPTS = ['In a doorway', 'Run outside', 'Next to the couch', 'Under a sturdy table']
def opts(pick=None, instant=True, **kw):
    d = {'type': 'options', 'items': OPTS, 'instant': instant}
    if pick is not None: d['pick'] = pick
    d.update(kw); return d
Y = [255, 222, 40]; R_ = [255, 100, 80]; G_ = [120, 235, 140]
OV = {
 0: [{'type': 'hook', 'text': 'ONLY 1 OF THESE|IS THE RIGHT MOVE', 'y': .11}],
 1: [opts(instant=False, **{'from': 1.6})],
 2: [opts()],
 3: [opts(), {'type': 'countdown', 'secs': 3, 'pos': [.5, .55]}],
 4: [opts(0), {'type': 'label', 'text': 'A MYTH', 'color': R_, 'pos': [.5, .37], 'from': 2.4}],
 5: [{'type': 'label', 'text': 'AN EARLY EARTHQUAKE PHOTO', 'color': Y, 'pos': [.5, .22], 'from': .3}, {'type': 'label', 'text': 'ONLY THE DOOR FRAME STOOD', 'color': [235, 235, 235], 'pos': [.5, .80], 'from': 3.4}],
 6: [opts(0), {'type': 'label', 'text': 'NO STRONGER THAN THE REST', 'color': Y, 'pos': [.5, .33], 'from': 1.2}],
 7: [opts(0), {'type': 'label', 'text': 'FALLING & FLYING OBJECTS', 'color': R_, 'pos': [.5, .37], 'from': 2.0}],
 8: [opts(1)],
 9: [opts(1), {'type': 'label', 'text': 'THE FLOOR IS MOVING', 'color': Y, 'pos': [.5, .37], 'from': .4}],
 10: [opts(1), {'type': 'label', 'text': 'GLASS · BRICKS · FACADES', 'color': R_, 'pos': [.5, .37], 'from': 1.0}],
 11: [opts(2), {'type': 'label', 'text': '"TRIANGLE OF LIFE"', 'color': Y, 'pos': [.5, .37], 'from': 2.4}],
 12: [opts(2)],
 13: [opts(2)],
 14: [opts(3), {'type': 'label', 'text': 'WINNER', 'color': G_, 'pos': [.5, .37], 'from': 1.7}],
 15: [opts(3)],
 16: [opts(3), {'type': 'label', 'text': 'IF IT SLIDES, MOVE WITH IT', 'color': Y, 'pos': [.5, .37], 'from': 2.7}],
 17: [{'type': 'label', 'text': 'NO TABLE?', 'color': Y, 'pos': [.5, .2], 'from': .1}, {'type': 'label', 'text': 'NEXT TO AN INSIDE WALL', 'color': [235, 235, 235], 'pos': [.5, .27], 'from': 1.0}],
 18: [{'type': 'label', 'text': 'IN BED? STAY THERE', 'color': Y, 'pos': [.5, .2], 'from': .2}, {'type': 'label', 'text': 'PILLOW OVER YOUR HEAD', 'color': [235, 235, 235], 'pos': [.5, .27], 'from': 1.6}],
 19: [{'type': 'label', 'text': 'DROP · COVER · HOLD ON', 'color': Y, 'pos': [.5, .22], 'from': .1}],
 20: [{'type': 'cta', 'text': 'FOLLOW FOR MORE SCENARIOS'}],
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
