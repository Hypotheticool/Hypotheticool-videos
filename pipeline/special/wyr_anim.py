"""Animate every scene of the WYR (deepest ocean vs edge of space) over its Cycles plates, with 2D science graphics.
python3 wyr_anim.py <scene>  ->  wyr/s<scene>/f_####.png + meta.json (overlays read by compose.py)"""
import sys, math, json, os
sys.path.insert(0, '/home/claude/pro')
import numpy as np, cv2, skia
import engine as E
ROOT = '/home/claude/b3d/wyr'; CFG = json.load(open(f'{ROOT}/topic.json'))
FPS = 24; PAD = .75; idx = int(sys.argv[1]); D = CFG['durs'][idx]; NF = int(math.ceil((D + PAD) * FPS))
W, H = 1080, 1920
ease = lambda t: .5 - .5 * math.cos(math.pi * min(max(t, 0), 1))
eout = lambda t: 1 - (1 - min(max(t, 0), 1)) ** 3
PL = {}
def plate(name):
    if name not in PL:
        im = cv2.imread(f'{ROOT}/plates/{name}.png', cv2.IMREAD_UNCHANGED)
        if name not in ('capsule', 'astro'):
            im = im[..., :3]
            if im.shape[1] != W: im = cv2.resize(im, (W, H), interpolation=cv2.INTER_CUBIC)
        elif im.shape[1] != W: im = cv2.resize(im, (W, H), interpolation=cv2.INTER_CUBIC)
        im = im.astype(np.float32)
        if name == 'limb':   # thin blue airglow band on the horizon + soft haze (what photos from ~100 km show)
            g = im.mean(2); hz = np.array([np.argmax(g[:, x] > 25) for x in range(W)], np.float32)
            xs = np.arange(W, dtype=np.float32); keep = np.ones(W, bool)
            for _ in range(4):   # robust quadratic fit: the true limb is a smooth curve; ignore dark-cloud dips
                cf = np.polyfit(xs[keep], hz[keep], 2); res = hz - np.polyval(cf, xs); keep = np.abs(res) < max(4, np.percentile(np.abs(res[keep]), 60))
            hz = np.polyval(cf, xs).astype(np.float32)
            yy = np.arange(H, dtype=np.float32)[:, None]; d = yy - hz[None, :]
            band = np.exp(-(d / 7) ** 2)[..., None] * np.array([255, 200, 120], np.float32)          # crisp limb line (BGR)
            haze = (np.exp(-np.clip(-d, 0, None) / 38) * (d < 0))[..., None] * np.array([150, 90, 40], np.float32)   # glow fading into black
            low = (np.exp(-np.clip(d, 0, None) / 160) * (d >= 0))[..., None] * np.array([90, 60, 30], np.float32)    # bright haze near the horizon
            im = np.clip(im + band * .9 + haze + low * .6, 0, 255)
            sh = cv2.GaussianBlur(im, (0, 0), 1.2); im = np.clip(im * 1.6 - sh * .6, 0, 255)   # a touch of sharpening
        PL[name] = im
    return PL[name]
PAC = [float(v) for v in open(f'{ROOT}/plates/pacific.txt').read().split()]   # trench position in the pacific plate (0-1)

def kb(name, u, z0, z1, c0=(.5, .5), c1=(.5, .5)):
    """Ken-Burns crop of a plate: zoom z (>=1) around a moving center (fractions of the plate)"""
    im = plate(name); t = ease(u); z = z0 + (z1 - z0) * t
    cx = (c0[0] + (c1[0] - c0[0]) * t) * W; cy = (c0[1] + (c1[1] - c0[1]) * t) * H
    M = np.float32([[z, 0, W / 2 - cx * z], [0, z, H / 2 - cy * z]])
    return cv2.warpAffine(im[..., :3], M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

def paste(bg, name, cx, cy, scale, ang=0.0):
    """alpha-composite a transparent plate (capsule/astro) centered at (cx, cy) px"""
    im = plate(name); h, w = im.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), ang, scale); M[0, 2] += cx - w / 2; M[1, 2] += cy - h / 2
    fg = cv2.warpAffine(im, M, (W, H), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))
    a = fg[..., 3:4] / 255.0; return bg * (1 - a) + fg[..., :3] * a

rng = np.random.default_rng(7); SNOW = rng.random((240, 4))
def snow(img, T, k=1.0, drift=40):
    """marine snow: organic flakes drifting down, catching the light"""
    lay = np.zeros_like(img)
    for x, y, s, b in SNOW:
        px = int((x * W + math.sin(T * .7 + y * 9) * 12) % W); py = int((y * H + T * drift * (.4 + s)) % H)
        r = 1 + int(s * 2.2); v = (25 + 75 * b * b) * k
        cv2.circle(lay, (px, py), r, (v, v * .95, v * .8), -1, cv2.LINE_AA)
    return img + cv2.GaussianBlur(lay, (0, 0), 1.2)

def grade(img, mul):   # darken / tint
    return img * np.float32(mul)

def split(T, a_img, b_img, u):
    """diagonal split screen, B slides in from the right"""
    out = a_img.copy(); xs = (1 - eout(u)) * W
    yy = np.arange(H)[:, None]; xx = np.arange(W)[None, :]
    edge = W * .5 + (yy - H / 2) * -.12 + xs
    m = (xx > edge)[..., None]; out = np.where(m, b_img, out)
    line = (np.abs(xx - edge) < 5)[..., None]; return np.where(line, np.float32(255), out)

# ---------------- skia helpers
def sk_begin(img):
    bgra = np.dstack([np.clip(img, 0, 255).astype(np.uint8), np.full((H, W), 255, np.uint8)])
    surf = skia.Surface(W, H); c = surf.getCanvas()
    c.drawImage(skia.Image.fromarray(np.ascontiguousarray(bgra), colorType=skia.kBGRA_8888_ColorType), 0, 0); return surf, c
def sk_end(surf): return surf.makeImageSnapshot().toarray()[..., :3].astype(np.float32)
def P(col, a=255, style='fill', w=0, blur=0):
    p = skia.Paint(AntiAlias=True, Color=skia.Color(col[0], col[1], col[2], int(max(0, min(255, a)))))
    if style == 'stroke': p.setStyle(skia.Paint.kStroke_Style); p.setStrokeWidth(w); p.setStrokeCap(skia.Paint.kRound_Cap)
    if blur: p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, blur))
    return p
def text(c, s, x, y, size, col=(255, 255, 255), a=255, align='c'):
    f = skia.Font(E.TF, size); w = f.measureText(s); x0 = x - w / 2 if align == 'c' else (x - w if align == 'r' else x)
    c.drawString(s, x0, y, f, P((0, 0, 0), a * .85, 'stroke', size * .14)); c.drawString(s, x0, y, f, P(col, a))
GOLD = (255, 205, 70); CYAN = (110, 215, 255); WHITE = (255, 255, 255); RED = (235, 70, 70)

# ---------------- 2D science scenes
def depth_diagram(T, u_desc, everest=0.0, zoom=1.0, zc=(.5, .5)):
    """ocean cross-section to scale: surface -> 10,935 m trench floor; optional Everest (8,849 m) standing in the trench"""
    img = np.zeros((H, W, 3), np.float32)
    top, bot = 330, 1700; ys = np.linspace(0, 1, bot - top)[:, None]
    col = np.stack([(.55 - .53 * ys ** .5) * 255, (.35 - .34 * ys ** .5) * 255, (.08 - .08 * ys) * 255], -1)[..., ::-1][..., ::-1]
    img[top:bot] = np.array([[ [0, 0, 0] ]], np.float32)
    grad = np.concatenate([(.62 - .6 * ys ** .45) * 255, (.36 - .35 * ys ** .45) * 255, (.08 - .08 * ys) * 255], 1)   # B,G,R
    img[top:bot] = grad[:, None, :]
    img[:top] = np.linspace(40, 8, top)[:, None, None] * np.array([1.0, .55, .25], np.float32)   # dusk sky (BGR)
    surf, c = sk_begin(img)
    if zoom != 1.0: c.save(); c.translate(W / 2, H / 2); c.scale(zoom, zoom); c.translate(-zc[0] * W, -zc[1] * H)
    km = (bot - top) / 10.935; X0 = 150
    # trench walls (to scale vertically)
    path = skia.Path(); path.moveTo(0, top); path.lineTo(0, H + 400); path.lineTo(W, H + 400); path.lineTo(W, top + 6 * km)
    path.lineTo(W * .82, top + 6.2 * km); path.lineTo(W * .68, top + 8.6 * km); path.lineTo(W * .62, bot); path.lineTo(W * .42, bot)
    path.lineTo(W * .32, top + 8.0 * km); path.lineTo(W * .18, top + 5.6 * km); path.lineTo(0, top + 5.2 * km); path.close()
    c.drawPath(path, P((28, 24, 22))); c.drawPath(path, P((90, 80, 70), 255, 'stroke', 4))
    # depth ticks every km
    for k in range(0, 11):
        y = top + k * km; c.drawLine(X0 - 30, y, X0 - 6, y, P(WHITE, 150, 'stroke', 3))
        text(c, f'{k} km', X0 - 40, y + 12, 32, (200, 220, 235), 200, 'r')
    c.drawLine(0, top, W, top, P(CYAN, 220, 'stroke', 4))
    text(c, 'SEA LEVEL', W - 40, top - 18, 38, CYAN, 230, 'r')
    if everest > 0:
        a = 255 * min(everest * 2, 1); ev_top = bot - 8.849 * km; grow = eout(everest)
        et = bot - (bot - ev_top) * grow
        m = skia.Path(); cx = W * .52
        m.moveTo(cx - 300, bot); m.lineTo(cx - 120, et + (bot - et) * .45); m.lineTo(cx - 40, et + (bot - et) * .12); m.lineTo(cx, et)
        m.lineTo(cx + 55, et + (bot - et) * .18); m.lineTo(cx + 140, et + (bot - et) * .4); m.lineTo(cx + 300, bot); m.close()
        c.drawPath(m, P((120, 110, 105), a));
        snowcap = skia.Path(); snowcap.moveTo(cx - 40, et + (bot - et) * .12); snowcap.lineTo(cx, et); snowcap.lineTo(cx + 55, et + (bot - et) * .18); snowcap.close()
        c.drawPath(snowcap, P((240, 245, 250), a))
        text(c, 'EVEREST', cx, et + (bot - et) * .27, 52, WHITE, a); text(c, '8,849 m', cx, et + (bot - et) * .27 + 58, 44, GOLD, a)
        if everest > .6:   # the gap above the summit
            g = (everest - .6) / .4; gx = cx + 230
            c.drawLine(gx, top, gx, top + (et - top) * eout(g), P(GOLD, 255, 'stroke', 6))
            for yy, d in ((top, 1), (top + (et - top) * eout(g), -1)):
                c.drawLine(gx - 16, yy + 18 * d, gx, yy, P(GOLD, 255, 'stroke', 6)); c.drawLine(gx + 16, yy + 18 * d, gx, yy, P(GOLD, 255, 'stroke', 6))
            text(c, '+2 km', gx - 20, top + (et - top) / 2 + 20, 70, GOLD, 255 * min(g * 2, 1), 'r')
            text(c, 'OF WATER', gx - 20, top + (et - top) / 2 + 80, 40, WHITE, 255 * min(g * 2, 1), 'r')
    # the descending sub light
    sy = top + (bot - 26 - top) * ease(u_desc); sx = W * .52
    c.drawCircle(sx, sy, 60, P(CYAN, 120, blur=30)); c.drawCircle(sx, sy, 13, P(WHITE))
    if everest <= 0: c.drawLine(sx, top, sx, sy, P(WHITE, 90, 'stroke', 3))
    if zoom != 1.0: c.restore()
    return sk_end(surf)

def pressure(T, base, u):
    """columns of water pushing down: falling chevrons + a squeezing ring"""
    surf, c = sk_begin(base)
    for k in range(7):
        x = W * (.1 + .8 * k / 6)
        for j in range(4):
            y = ((T * 420 + j * 180 + k * 37) % 760) + 320
            a = 200 * math.sin(math.pi * (y - 320) / 760)
            pth = skia.Path(); pth.moveTo(x - 34, y - 26); pth.lineTo(x, y + 8); pth.lineTo(x + 34, y - 26)
            c.drawPath(pth, P(CYAN, a, 'stroke', 9))
    return sk_end(surf)

def bars(T, u):
    """pressure you feel now (1x) vs the trench floor (~1,000x), bars to scale by area"""
    img = np.zeros((H, W, 3), np.float32); img[:] = (30, 14, 6)
    surf, c = sk_begin(img)
    g = eout(u); top = 360; bot = 1560
    # 1,000 small squares (each = the air pressure on you now)
    n = int(1000 * g); s = 30; cols = 31
    for k in range(n):
        x = 75 + (k % cols) * s; y = bot - (k // cols + 1) * s
        c.drawRect(skia.Rect.MakeXYWH(x, y, s - 5, s - 5), P(CYAN if k else GOLD, 235))
    text(c, f'{max(1, n):,}x', W / 2, top - 30, 120, GOLD)
    text(c, 'each square = the pressure on you right now', W / 2, bot + 80, 40, (210, 225, 235))
    return sk_end(surf)

def people(T, u, mode):
    """dot people: 600+ who have flown to space vs 27 who reached Challenger Deep"""
    img = np.zeros((H, W, 3), np.float32); img[:] = (18, 10, 4)
    surf, c = sk_begin(img)
    def person(x, y, s, col, a):
        c.drawCircle(x, y - s * .55, s * .26, P(col, a)); r = skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x - s * .3, y - s * .25, s * .6, s * .62), s * .2, s * .2); c.drawRRect(r, P(col, a))
    g = eout(u)
    if mode == 'space':
        n = int(600 * g); cols = 24; s = 38
        for k in range(n): person(80 + (k % cols) * s, 520 + (k // cols) * (s + 6), s * .95, (120, 200, 255), 235)
        text(c, f'{n}+' if n >= 600 else f'{n}', W / 2, 430, 130, CYAN)
        text(c, 'PEOPLE IN SPACE', W / 2, 1720, 64, WHITE)
    else:
        cols = 24; s = 38
        for k in range(600): person(80 + (k % cols) * s, 520 + (k // cols) * (s + 6), s * .95, (120, 200, 255), 70 + 160 * (1 - g))
        for k in range(27):
            x = 80 + (k % cols) * s; y = 520 + (k // cols) * (s + 6)
            person(x, y, s * .95, GOLD, 255); c.drawCircle(x, y - 10, 30, P(GOLD, 120 * g, blur=12))
        text(c, '27', W * .3, 1700, 120, GOLD, 255 * g); text(c, 'DEEPEST', W * .3, 1770, 46, WHITE, 255 * g)
        text(c, '600+', W * .7, 1700, 120, CYAN, 255 * g); text(c, 'SPACE', W * .7, 1770, 46, WHITE, 255 * g)
    return sk_end(surf)

def trench_pin(img, T, x, y, a=1.0, z=1.0):
    surf, c = sk_begin(img)
    for k in range(3):
        ph = (T * .9 + k / 3) % 1; c.drawCircle(x, y, 20 + 140 * ph * z, P(GOLD, 220 * (1 - ph) * a, 'stroke', 5))
    c.drawCircle(x, y, 14, P(GOLD, 255 * a)); c.drawCircle(x, y, 40, P(GOLD, 120 * a, blur=16))
    return sk_end(surf)

def horizon_glow(img, y=None):
    """thin blue airglow band where black sky meets the atmosphere (plate's own limb + a little 2D bloom)"""
    return img

# ---------------- scene table: list of (start_sec, render_fn(T_local_in_shot, u_shot))
def shots():
    sinkd = lambda T, u, k: snow(grade(kb('sink', u, 1.0 + .1 * k, 1.12 + .1 * k, (.56, .44 + .02 * k), (.58, .45 + .02 * k)), 1 - .28 * k), T, 1 - .3 * k)
    floor = lambda T, u, z0, z1, c0, c1: snow(kb('floor', u, z0, z1, c0, c1), T, 1.0, 25)
    limb = lambda T, u, z0, z1, c0, c1: kb('limb', u, z0, z1, c0, c1)
    px, py = PAC
    def pac(T, u, z0, z1):
        t = ease(u); z = z0 + (z1 - z0) * t; c0 = (.5, .5); cc = (.5 + (px - .5) * t, .5 + (py + .08 - .5) * t)
        img = kb('pacific', u, z0, z1, c0, cc); X = W / 2 + (px * W - cc[0] * W) * z; Y = H / 2 + (py * H - cc[1] * H) * z
        return trench_pin(img, T, X, Y, min(1, T * 2))
    def ab(T, u):   # A (deep) vs B (space) split
        return split(T, snow(kb('floor', .5, 1.15, 1.15, (.42, .42)), T), kb('limb', u, 1.05, 1.12, (.5, .45)), min(1, u * 3))
    def capsule(T, u, z):
        bg = kb('limb', u, 1.05, 1.15, (.5, .5), (.5, .47)); y = H * (.95 - .42 * eout(u * 1.2))
        return paste(bg, 'capsule', W * .5, y, .78 * z, -8 + 6 * u)
    def astro(T, u):
        bg = kb('limb', u, 1.2, 1.28, (.45, .52), (.5, .5)); return paste(bg, 'astro', W * (.47 + .06 * u), H * (.47 - .03 * math.sin(u * 3)), .8, -10 + 22 * u)
    return {
     0: [(0, lambda T, u: floor(T, u, 1.0, 1.1, (.45, .42), (.5, .42))), (1.5, lambda T, u: floor(T, u, 1.55, 1.7, (.5, .42), (.56, .42)))],
     1: [(0, lambda T, u: sinkd(T, u, 0)), (2.5, lambda T, u: limb(T, u, 1.0, 1.1, (.5, .5), (.5, .46))), (4.2, ab)],
     2: [(0, ab)],
     3: [(0, lambda T, u: pac(T, u, 1.0, 1.25)), (2.2, lambda T, u: pac(T, u, 1.7, 2.3))],
     4: [(0, lambda T, u: depth_diagram(T, u * .9))],
     5: [(0, lambda T, u: depth_diagram(T, 1, everest=min(1, u * 1.6))), (2.4, lambda T, u: depth_diagram(T, 1, 1, 1.35 + .1 * u, (.6, .38)))],
     6: [(0, lambda T, u: sinkd(T, u, 0)), (2.1, lambda T, u: sinkd(T, u, 1)), (4.2, lambda T, u: sinkd(T, u, 2))],
     7: [(0, lambda T, u: pressure(T, floor(T, u, 1.15, 1.25, (.5, .42), (.5, .42)), u)), (2.6, lambda T, u: pressure(T, floor(T, u, 1.7, 1.85, (.55, .42), (.58, .42)), u))],
     8: [(0, lambda T, u: bars(T, min(1, u * 1.3)))],
     9: [(0, lambda T, u: limb(T, u, 1.0, 1.1, (.5, .6), (.5, .5))), (2.1, lambda T, u: limb(T, u, 1.3, 1.42, (.35, .45), (.45, .45)))],
     10: [(0, lambda T, u: capsule(T, u, 1.0)), (2.8, lambda T, u: capsule(T, .6 + u * .4, 1.35))],
     11: [(0, lambda T, u: limb(T, u, 1.15, 1.0, (.5, .4), (.5, .48))), (2.1, lambda T, u: limb(T, u, 1.5, 1.6, (.62, .5), (.42, .5)))],
     12: [(0, astro)],
     13: [(0, lambda T, u: people(T, min(1, u * 1.5), 'space'))],
     14: [(0, lambda T, u: people(T, 1, 'space')), (1.2, lambda T, u: people(T, min(1, u * 1.4), 'both'))],
     15: [(0, lambda T, u: floor(T, u, 1.0, 1.12, (.5, .42), (.47, .42))), (1.7, lambda T, u: pac(T, u, 1.4, 1.7))],
     16: [(0, lambda T, u: sinkd(T, u, 1)), (1.4, lambda T, u: sinkd(T, u, 2.4))],
    }[idx]

GL = 'GOLD'
OV = {   # compose.py overlays per scene
 0: [{'type': 'hook', 'text': 'ONLY 27 PEOPLE|HAVE BEEN HERE'}],
 1: [{'type': 'choice', 'a': 'Deepest ocean', 'b': 'Edge of space', 'from': .3}],
 2: [{'type': 'choice', 'a': 'Deepest ocean', 'b': 'Edge of space', 'instant': True},
     {'type': 'prompt', 'text': 'Comment A or B', 'pos': [.5, .52], 'from': .1}, {'type': 'countdown', 'secs': 2, 'pos': [.5, .4]}],
 3: [{'type': 'datestamp', 'text': 'A · Mariana Trench · Pacific', 'y': .09, 'from': .2}],
 4: [{'type': 'badge', 'value': '10,935', 'unit': 'm deep', 'pos': [.5, .12], 'from': .5}],
 5: [{'type': 'badge', 'value': '+2', 'unit': 'km deeper', 'pos': [.5, .12], 'from': 1.6}],
 6: [{'type': 'label', 'text': 'SUNLIGHT FADES', 'color': [255, 222, 40], 'pos': [.5, .14], 'from': .3},
     {'type': 'label', 'text': 'HOURS IN THE DARK', 'color': [255, 255, 255], 'pos': [.5, .2], 'from': 3.0}],
 7: [{'type': 'badge', 'value': '8 tons', 'unit': 'per sq inch', 'pos': [.5, .13], 'from': 1.0}],
 8: [],
 9: [{'type': 'datestamp', 'text': 'B · Edge of space · 100 km up', 'y': .09, 'from': .2},
     {'type': 'measure', 'x': .9, 'y0': .78, 'y1': .3, 'from': .6}],
 10: [{'type': 'badge', 'value': '~10', 'unit': 'min trip', 'pos': [.5, .13], 'from': 2.4}],
 11: [{'type': 'label', 'text': 'BLACK SKY', 'color': [255, 255, 255], 'pos': [.5, .2], 'from': .6},
      {'type': 'label', 'text': "EARTH'S CURVE", 'color': [255, 222, 40], 'pos': [.5, .62 if False else .44], 'from': 2.3}],
 12: [{'type': 'label', 'text': 'WEIGHTLESS', 'color': [255, 222, 40], 'pos': [.5, .16], 'from': .5}],
 13: [],
 14: [{'type': 'badge', 'value': '20x', 'unit': 'more', 'pos': [.5, .12], 'from': 1.6}],
 15: [{'type': 'choice', 'a': 'Deepest ocean', 'b': 'Edge of space', 'win': 'a', 'instant': True},
      {'type': 'prompt', 'text': 'The rarer trip: A', 'pos': [.5, .3], 'from': .8}],
 16: [{'type': 'cta', 'text': 'FOLLOW FOR MORE WOULD YOU RATHERS'}],
}[idx]

if __name__ == '__main__':
    out = f'{ROOT}/s{idx}'; os.makedirs(out, exist_ok=True)
    SH = shots(); bounds = [s for s, _ in SH] + [D + PAD]
    only = [int(a) for a in sys.argv[2:]]   # optional: render only these frames (preview)
    for f in (only or range(1, NF + 1)):
        T = (f - 1) / FPS - .35          # compose samples scene time T + XF; frame 1 = .35 s before the line starts
        Tc = max(T, 0); k = max(j for j in range(len(SH)) if SH[j][0] <= Tc or j == 0)
        t0, t1 = bounds[k], bounds[k + 1]; u = (Tc - t0) / max(t1 - t0, .1)
        img = SH[k][1](T - t0 + (.35 if k == 0 else 0), u)
        cv2.imwrite(f'{out}/f_{f:04d}.png', np.clip(img, 0, 255).astype(np.uint8), [cv2.IMWRITE_PNG_COMPRESSION, 1])
    json.dump({'frames': NF, 'overlays': OV}, open(f'{out}/meta.json', 'w'))
    print('scene', idx, NF)
