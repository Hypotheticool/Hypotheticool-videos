"""Animate every scene of "What if you took off your helmet in space?" over its Cycles plates (helmet_plate.py) with 2D motion:
push-ins, the helmet sprite tumbling away, sun glare/UV, exhale vapor, swelling (bulge warp), rising vapor bubbles, leak hiss,
blackout blur, and stopwatch rings (15 s, 14 s, 90 s, 2 min).
python3 helmet_anim.py <scene> [frames...]  ->  helmet/s<scene>/f_####.png + meta.json (overlays read by compose.py)"""
import sys, math, json, os
sys.path.insert(0, '/home/claude/pro')
import numpy as np, cv2, skia
import engine as E
ROOT = '/home/claude/b3d/helmet'; CFG = json.load(open(f'{ROOT}/topic.json'))
FPS = 24; PAD = .75; idx = int(sys.argv[1]); D = CFG['durs'][idx]; NF = int(math.ceil((D + PAD) * FPS))
W, H = 1080, 1920
ease = lambda t: .5 - .5 * math.cos(math.pi * min(max(t, 0), 1))
eout = lambda t: 1 - (1 - min(max(t, 0), 1)) ** 3
clamp = lambda t: min(max(t, 0.0), 1.0)
PL = {}
def plate(name):
    if name not in PL:
        im = cv2.imread(f'{ROOT}/plates/{name}.png', cv2.IMREAD_UNCHANGED)
        if name != 'helmet' and im.shape[2] == 4: im = im[..., :3]
        if im.shape[1] != W: im = cv2.resize(im, (W, H), interpolation=cv2.INTER_CUBIC)
        PL[name] = im.astype(np.float32)
    return PL[name]

def kb(name, u, z0, z1, c0=(.5, .5), c1=(.5, .5), src=None):
    im = plate(name) if src is None else src; t = ease(u); z = z0 + (z1 - z0) * t
    cx = (c0[0] + (c1[0] - c0[0]) * t) * W; cy = (c0[1] + (c1[1] - c0[1]) * t) * H
    M = np.float32([[z, 0, W / 2 - cx * z], [0, z, H / 2 - cy * z]])
    return cv2.warpAffine(im, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

def kb_pt(px, py, u, z0, z1, c0=(.5, .5), c1=(.5, .5)):
    t = ease(u); z = z0 + (z1 - z0) * t
    cx = (c0[0] + (c1[0] - c0[0]) * t) * W; cy = (c0[1] + (c1[1] - c0[1]) * t) * H
    return W / 2 + (px * W - cx) * z, H / 2 + (py * H - cy) * z, z

XX = np.arange(W, dtype=np.float32)[None, :]; YY = np.arange(H, dtype=np.float32)[:, None]
RNG = np.random.default_rng(11); MOTES = RNG.random((150, 4))
def dust(img, T, col=(150, 190, 255), k=1.0, drift=(8, -14)):
    lay = np.zeros_like(img)
    for x, y, s, b in MOTES:
        px = int((x * W + T * drift[0] * (.5 + s) + 14 * math.sin(T * .6 + y * 7)) % W); py = int((y * H + T * drift[1] * (.5 + s)) % H)
        v = (20 + 60 * b * b) * k; cv2.circle(lay, (px, py), 1 + int(s * 2.4), (col[0] * v / 255, col[1] * v / 255, col[2] * v / 255), -1, cv2.LINE_AA)
    return img + cv2.GaussianBlur(lay, (0, 0), 1.4)

def glow(img, x, y, r, a, col=(210, 245, 255)):
    if a <= 0: return img
    x0, x1 = int(max(0, x - 3 * r)), int(min(W, x + 3 * r)); y0, y1 = int(max(0, y - 3 * r)), int(min(H, y + 3 * r))
    if x1 <= x0 or y1 <= y0: return img
    d2 = ((XX[:, x0:x1] - x) ** 2 + (YY[y0:y1] - y) ** 2) / (r * r)
    g = (np.exp(-d2 * 2.2) * 1.0 + np.exp(-d2 * .35) * .35) * a
    img[y0:y1, x0:x1] += g[..., None] * np.array(col, np.float32)
    return img

def bulge(img, cx, cy, r, k):
    """swell a round region: magnify by up to (1+k) at the center, falling off smoothly to 1 at radius r"""
    if k <= 0: return img
    dx, dy = XX - cx, YY - cy; d = np.sqrt(dx * dx + dy * dy) / r
    f = np.where(d < 1, 1 / (1 + k * (1 - d * d) ** 2), 1.0).astype(np.float32)
    mx = (cx + dx * f).astype(np.float32); my = (cy + dy * f).astype(np.float32)
    mx = np.broadcast_to(mx, (H, W)).copy(); my = np.broadcast_to(my, (H, W)).copy()
    return cv2.remap(img, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

def sprite(img, name, x, y, scale, ang):
    """alpha-composite a transparent plate (the helmet) centred at (x, y), scaled and rotated"""
    sp = plate(name); M = cv2.getRotationMatrix2D((W / 2, H * .5), ang, scale); M[0, 2] += x - W / 2; M[1, 2] += y - H * .5
    w = cv2.warpAffine(sp, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    a = w[..., 3:4] / 255.0
    return img * (1 - a) + w[..., :3] * a

def bubbles(img, T, x0, x1, y0, y1, n=40, a=1.0, seed=3, speed=120):
    """rising vapor bubbles: small bright rings drifting up and wobbling"""
    lay = np.zeros_like(img); rng = np.random.default_rng(seed); P = rng.random((n, 4))
    for px, py, s, ph in P:
        yy = y1 - ((py * (y1 - y0) + T * speed * (.6 + s)) % (y1 - y0)); xx = x0 + px * (x1 - x0) + 10 * math.sin(T * 3 + ph * 6)
        r = int(4 + 10 * s); cv2.circle(lay, (int(xx), int(yy)), r, (255, 235, 210), 2, cv2.LINE_AA); cv2.circle(lay, (int(xx - r * .3), int(yy - r * .3)), max(1, r // 4), (255, 255, 255), -1, cv2.LINE_AA)
    return img + (cv2.GaussianBlur(lay, (0, 0), 1.2) * .9 + cv2.GaussianBlur(lay, (0, 0), 6) * .6) * a

def puff(img, x, y, T, a=1.0, dirx=-1):
    """exhaled breath: a short burst of cold vapor flashing out of the mouth"""
    lay = np.zeros_like(img); rng = np.random.default_rng(7)
    for k in range(30):
        t = (T * 1.2 + k / 30) % 1.0; ang = math.radians(rng.uniform(-35, 35) + (180 if dirx < 0 else 0)); d = 30 + 260 * t
        px, py = x + math.cos(ang) * d, y - 40 * t + math.sin(ang) * d * .5; r = int(8 + 30 * t)
        v = 230 * (1 - t); cv2.circle(lay, (int(px), int(py)), r, (v, v, v), -1, cv2.LINE_AA)
    return img + cv2.GaussianBlur(lay, (0, 0), 10) * 1.8 * a

def hiss(img, x, y, T, a=1.0, seed=5):
    """air leaking out: fast streaks spraying from a point"""
    lay = np.zeros_like(img); rng = np.random.default_rng(seed + int(T * 12))
    for k in range(26):
        ang = rng.uniform(-.9, .9) - .4; L = rng.uniform(60, 220); x0 = x + rng.uniform(0, 30)
        cv2.line(lay, (int(x0), int(y)), (int(x0 + math.cos(ang) * L), int(y + math.sin(ang) * L)), (230, 235, 240), 2, cv2.LINE_AA)
    return img + cv2.GaussianBlur(lay, (0, 0), 3) * .8 * a

def tint(img, col, a):
    return img * (1 - a) + (img.mean(2, keepdims=True) * np.array(col, np.float32) / 255) * a

def desat(img, a, dark=0.0):
    g = img.mean(2, keepdims=True); return (img * (1 - a) + g * a) * (1 - dark)

def vignette(img, a):
    m = np.clip(((XX / W - .5) ** 2 + (YY / H - .5) ** 2 * .45) * 3.2, 0, 1)
    return img * (1 - m[..., None] * a)

def blurdim(img, a):
    if a <= 0: return img
    b = cv2.GaussianBlur(img, (0, 0), 3 + 22 * a); return vignette(b * (1 - .55 * a), a)

def flare(img, T, a=1.0):
    """harsh unfiltered sunlight from the top-left"""
    img = glow(img, W * .05, H * .06, 260, 1.3 * a * (.95 + .05 * math.sin(T * 8)), (235, 250, 255))
    img = glow(img, W * .05, H * .06, 90, 1.6 * a, (255, 255, 255))
    return img

# ---------------- skia helpers (stopwatch rings)
def sk_begin(img):
    bgra = np.dstack([np.clip(img, 0, 255).astype(np.uint8), np.full((H, W), 255, np.uint8)])
    surf = skia.Surface(W, H); c = surf.getCanvas()
    c.drawImage(skia.Image.fromarray(np.ascontiguousarray(bgra), colorType=skia.kBGRA_8888_ColorType), 0, 0); return surf, c
def sk_end(surf): return surf.makeImageSnapshot().toarray()[..., :3].astype(np.float32)
def Pn(col, a=255, style='fill', w=0, blur=0):
    p = skia.Paint(AntiAlias=True, Color=skia.Color(int(col[0]), int(col[1]), int(col[2]), int(max(0, min(255, a)))))
    if style == 'stroke': p.setStyle(skia.Paint.kStroke_Style); p.setStrokeWidth(w); p.setStrokeCap(skia.Paint.kRound_Cap)
    if blur: p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, blur))
    return p
def text(c, s, x, y, size, col=(255, 255, 255), a=255, align='c'):
    f = skia.Font(E.TF, size); w = f.measureText(s); x0 = x - w / 2 if align == 'c' else (x - w if align == 'r' else x)
    c.drawString(s, x0, y, f, Pn((0, 0, 0), a * .85, 'stroke', size * .14)); c.drawString(s, x0, y, f, Pn(col, a))
GOLD = (255, 205, 70); CYAN = (110, 215, 255); WHITE = (255, 255, 255); RED = (255, 70, 60)

def stopwatch(img, secs_shown, frac, label, col=GOLD, cy=.38, a=1.0, brush=False):
    """ring timer: frac of the ring filled, big time readout in the middle"""
    surf, c = sk_begin(img); cx, cyp, R = W / 2, H * cy, 250
    c.drawCircle(cx, cyp, R + 40, Pn((5, 8, 16), 190 * a))
    c.drawCircle(cx, cyp, R, Pn((70, 80, 100), 200 * a, 'stroke', 26))
    oval = skia.Rect.MakeXYWH(cx - R, cyp - R, 2 * R, 2 * R)
    c.drawArc(oval, -90, 360 * clamp(frac), False, Pn(col, 255 * a, 'stroke', 26))
    c.drawRect(skia.Rect.MakeXYWH(cx - 22, cyp - R - 92, 44, 40), Pn((180, 190, 205), 255 * a))   # stopwatch crown
    text(c, secs_shown, cx, cyp + 50, 150, WHITE, 255 * a)
    text(c, label, cx, cyp + 135, 44, col, 255 * a)
    if brush:   # simple toothbrush icon under the ring
        y = cyp + R + 110; c.drawRoundRect(skia.Rect.MakeXYWH(cx - 190, y - 16, 300, 32), 16, 16, Pn((90, 170, 255), 255 * a))
        c.drawRoundRect(skia.Rect.MakeXYWH(cx + 100, y - 36, 100, 24), 6, 6, Pn((235, 240, 250), 255 * a))
        for k in range(8): c.drawRect(skia.Rect.MakeXYWH(cx + 106 + k * 12, y - 66, 7, 30), Pn((235, 240, 250), 255 * a))
    return sk_end(surf)

# feature positions in the plates (fractions of the frame, measured on the stills)
FX = json.load(open(f'{ROOT}/plates/fx.json')) if os.path.exists(f'{ROOT}/plates/fx.json') else {}
def fx(k, d=(.5, .5)): return FX.get(k, d)

def shots():
    HEAD = fx('head', (.47, .3)); GL = fx('glove_l', (.26, .51)); GR = fx('glove_r', (.79, .44)); MOUTH = fx('mouth', (.48, .35))
    SUBJ = fx('subj_helmet', (.5, .49)); PILOT = fx('pilot', (.5, .72)); HS = fx('helmet_scale', .5)
    def bare(T, u, z0, z1, c0=(.5, .5), c1=(.5, .5), helmet=None, src='bare'):
        img = dust(kb(src, u, z0, z1, c0, c1), T, k=.5)
        if helmet is not None:   # helmet drifting off from the head, tumbling, up and to the right
            p = helmet(T); hx, hy, z = kb_pt(HEAD[0] + .32 * p, HEAD[1] - .1 * p - .02, u, z0, z1, c0, c1)
            img = sprite(img, 'helmet', hx, hy, HS * z * (1 - .25 * p), -25 - 140 * p)
        return img
    def suited(T, u, z0, z1, c0=(.5, .5), c1=(.5, .5)): return bare(T, u, z0, z1, c0, c1, src='suited')
    def face(T, u, z0, z1, extra=None):
        c0 = (HEAD[0], HEAD[1] + .03); img = bare(T, u, z0, z1, c0, c0)
        return extra(img, T, u, c0) if extra else img
    def lungs(T, u, z0, z1, c0=(.5, .45), c1=(.5, .43), swell=0.0, red=0.0):
        img = kb('lungs', u, z0, z1, c0, c1) * .85
        if swell > 0:
            for px in (.38, .62):
                x, y, z = kb_pt(px, .46, u, z0, z1, c0, c1); img = bulge(img, x, y, 260 * z, swell)
        if red > 0:
            for k, px in enumerate((.37, .63)):
                x, y, z = kb_pt(px, .52, u, z0, z1, c0, c1); img = glow(img, x, y, 150 * z, red * (.6 + .4 * math.sin(T * 9 + k)), (40, 40, 255))
        return dust(img, T, (120, 160, 255), .4)
    def heart(T, u, z0, z1, c0=(.5, .45), c1=(.5, .42), bub=0.0, fade=0.0):
        img = kb('heart', u, z0, z1, c0, c1)
        beat = .04 * max(0, math.sin(T * 7.5)) ** 8 * (1 - fade)
        x, y, z = kb_pt(.5, .48, u, z0, z1, c0, c1); img = bulge(img, x, y, 420 * z, beat)
        if bub > 0: img = bubbles(img, T, W * .2, W * .8, H * .15, H * .7, 46, bub)
        if fade > 0: img = desat(img, fade, .6 * fade)
        return img
    def balloon(T, u, z0, z1, c0=(.5, .5), c1=(.5, .5), swell=0.0):
        img = kb('balloon', u, z0, z1, c0, c1)
        img = img + (np.exp(-((YY / H - .8) / .05) ** 2) * .0)[..., None]
        if swell > 0:
            x, y, z = kb_pt(PILOT[0] + .03, PILOT[1] + .01, u, z0, z1, c0, c1); img = bulge(img, x, y, 70 * z, swell)
        return dust(img, T, k=.4)
    def chamber(T, u, z0, z1, c0=(.5, .5), c1=(.5, .5), leak=0.0, out=0.0, air=0.0, alarm=0.0):
        img = kb('chamber', u, z0, z1, c0, c1) * .72
        if alarm > 0: img = tint(img, (255, 90, 70), alarm * (.25 + .2 * math.sin(T * 9)))
        if leak > 0:
            x, y, z = kb_pt(SUBJ[0] + .05, SUBJ[1] + .04, u, z0, z1, c0, c1); img = hiss(img, x, y, T, leak)
            img = bubbles(img, T, x - 140 * z, x + 40 * z, y - 120 * z, y + 30 * z, 14, leak * .8, 9, 60)
        if air > 0: img = dust(img, T, (220, 230, 255), 2.5 * air, (-260, 0))
        return blurdim(dust(img, T, (200, 210, 230), .5, (2, -4)), out)
    def watch(T, u, base, secs, label, col=GOLD, brush=False, total=None):
        p = clamp(u * 1.15); v = secs * p
        shown = f'{int(v // 60)}:{int(v % 60):02d}' if (total or secs) >= 60 else f'{int(v)}'
        return stopwatch(base(T, u), shown, p * secs / (total or secs), label, col, brush=brush)
    help_off = lambda T: .35 + .65 * eout(T / 2.6)    # helmet already off at frame 1, drifting away
    help_loop = lambda T: .33 * ease(T / 2.9)         # last scene: starts back at the head (loops into scene 0)
    return {
     0: [(0, lambda T, u: flare(bare(T, u, 1.12, 1.22, (.5, .4), (.52, .38), help_off), T, .5))],
     1: [(0, lambda T, u: suited(T, u, 1.0, 1.1, (.5, .45), (.5, .42))), (1.4, lambda T, u: face(T, u, 2.0, 2.25))],
     2: [(0, lambda T, u: bare(T, u, 1.3, 1.15, (.5, .4), (.5, .42)) * (1 + .25 * max(0, 1 - T * 2)))],
     3: [(0, lambda T, u: bare(T, u, 2.0, 2.2, GL, GL)), (1.5, lambda T, u: bare(T, u, 1.0, 1.08, (.5, .45), (.5, .43)))],
     4: [(0, lambda T, u: tint(face(T, u, 1.8, 1.95), (150, 200, 255), .35)), (1.2, lambda T, u: bare(T, u, 1.1, 1.0, (.5, .5), (.5, .45)))],
     5: [(0, lambda T, u: glow(bare(T, u, 1.0, 1.1, (.5, .45), (.5, .42)), W * .5, H * .42, 330, .16 + .05 * math.sin(T * 3), (60, 120, 255))),
         (1.6, lambda T, u: glow(face(T, u, 1.6, 1.8), W * .5, H * .45, 420, .14, (60, 120, 255)))],
     6: [(0, lambda T, u: flare(bare(T, u, 1.05, 1.15, (.45, .4), (.42, .38)), T, 1.0)),
         (1.9, lambda T, u: face(T, u, 2.3, 2.5, lambda im, T, u, c: tint(flare(im, T, .8), (210, 140, 255), .25 + .1 * math.sin(T * 6))))],
     7: [(0, lambda T, u: lungs(T, u, 1.0, 1.1)), (1.4, lambda T, u: lungs(T, u, 1.5, 1.6, (.5, .2), (.5, .25)))],
     8: [(0, lambda T, u: lungs(T, u, 1.0, 1.05, swell=.25 * eout(u * 1.5))),
         (1.8, lambda T, u: lungs(T, u, 1.3, 1.45, (.5, .5), (.5, .5), swell=.25 + .15 * eout(u), red=clamp(u * 2)))],
     9: [(0, lambda T, u: face(T, u, 2.1, 2.3, lambda im, T, u, c: puff(im, *kb_pt(*MOUTH, u, 2.1, 2.3, c, c)[:2], T, clamp(T * 2), 1))),
         (1.3, lambda T, u: watch(T, u, lambda T, u: blurdim(bare(T, u, 1.1, 1.2), .4), max(D - 1.3, .5), 'SECONDS', GOLD, total=15))],
     10: [(0, lambda T, u: heart(T, u, 1.0, 1.1, bub=clamp(T))), (1.5, lambda T, u: heart(T, u, 1.5, 1.7, (.5, .4), (.48, .4), bub=1)),
          (3.0, lambda T, u: bubbles(bare(T, u, 1.4, 1.5, (.5, .45), (.5, .43)), T, W * .3, W * .7, H * .2, H * .6, 30, .8))],
     11: [(0, lambda T, u: bulge(bare(T, u, 1.5, 1.6, (HEAD[0], HEAD[1] + .05), (HEAD[0], HEAD[1] + .05)), *kb_pt(HEAD[0], HEAD[1], u, 1.5, 1.6, (HEAD[0], HEAD[1] + .05), (HEAD[0], HEAD[1] + .05))[:2], 330, .45 * eout(u * 1.3))),
          (1.8, lambda T, u: bulge(bare(T, u, 2.2, 2.3, GL, GL), W / 2, H / 2, 260, .3 + .25 * eout(u)))],
     12: [(0, lambda T, u: balloon(T, u, 1.0, 1.08, (.5, .55), (.5, .5))), (1.8, lambda T, u: balloon(T, u, 1.25, 1.35, (.5, .3), (.5, .25))),
          (3.6, lambda T, u: balloon(T, u, 1.9, 2.05, PILOT, (PILOT[0], PILOT[1] - .01)))],
     13: [(0, lambda T, u: balloon(T, u, 2.2, 2.35, PILOT, PILOT, swell=.6 * eout(u * 1.3))),
          (1.7, lambda T, u: balloon(T, u, 1.4, 1.5, (.5, .62), (.5, .6), swell=.6))],
     14: [(0, lambda T, u: chamber(T, u, 1.0, 1.06, (.5, .5), (.5, .48))), (2.0, lambda T, u: chamber(T, u, 1.4, 1.55, (.5, .45), (.5, .47))),
          (4.0, lambda T, u: chamber(T, u, 1.9, 2.05, SUBJ, SUBJ, leak=clamp(T * 2), alarm=clamp(T * 2)))],
     15: [(0, lambda T, u: chamber(T, u, 2.4, 2.6, SUBJ, SUBJ, leak=1, alarm=1)), (1.9, lambda T, u: chamber(T, u, 1.5, 1.6, (.5, .48), (.5, .48), leak=1, alarm=1))],
     16: [(0, lambda T, u: chamber(T, u, 1.8, 2.0, SUBJ, SUBJ, leak=.6, alarm=1, out=clamp(u * 1.2))),
          (1.6, lambda T, u: watch(T, u, lambda T, u: chamber(T, u, 1.2, 1.3, alarm=1, out=1), 14, 'SECONDS', RED))],
     17: [(0, lambda T, u: chamber(T, u, 1.3, 1.2, (.5, .5), (.5, .5), out=1 - clamp(u * 1.3), air=1)), (2.0, lambda T, u: chamber(T, u, 1.0, 1.08, air=.4))],
     18: [(0, lambda T, u: watch(T, u, lambda T, u: blurdim(kb('heart', u, 1.0, 1.05), .7), 90, 'MIN : SEC', (120, 230, 140))),
          (2.5, lambda T, u: heart(T, u, 1.2, 1.3))],
     19: [(0, lambda T, u: heart(T, u, 1.3, 1.4, fade=clamp(u * 1.2))), (1.6, lambda T, u: desat(bare(T, u, 1.2, 1.3, (.5, .42), (.5, .4)), .8, .4 * u))],
     20: [(0, lambda T, u: watch(T, u, lambda T, u: blurdim(bare(T, u, 1.0, 1.05), .8), 120, 'MINUTES', CYAN, brush=True)),
          (1.5, lambda T, u: stopwatch(blurdim(bare(T, u, 1.05, 1.1), .8), '2:00', 1, 'MINUTES', CYAN, brush=True))],
     21: [(0, lambda T, u: flare(bare(T, u, 1.0, 1.12, (.5, .45), (.5, .4), help_loop), T, .4 * u))],
    }[idx]

YEL, WH, GREY = [255, 222, 40], [255, 255, 255], [200, 200, 200]
OV = {
 0: [{'type': 'hook', 'text': '15 SECONDS|AT MOST'}, {'type': 'label', 'text': 'ILLUSTRATION', 'color': GREY, 'pos': [.8, .955], 'instant': True}],
 1: [],
 2: [{'type': 'label', 'text': 'YOU WOULD NOT EXPLODE', 'color': YEL, 'pos': [.5, .16], 'from': .5}],
 3: [{'type': 'label', 'text': 'SKIN HOLDS YOU TOGETHER', 'color': WH, 'pos': [.5, .16], 'from': .4}],
 4: [{'type': 'label', 'text': 'NO INSTANT FREEZE', 'color': [140, 210, 255], 'pos': [.5, .16], 'from': .4}],
 5: [{'type': 'label', 'text': 'VACUUM = POOR HEAT CONDUCTOR', 'color': WH, 'pos': [.5, .16], 'from': .4}],
 6: [{'type': 'label', 'text': 'UNFILTERED ULTRAVIOLET', 'color': [215, 150, 255], 'pos': [.5, .2], 'from': .8}],
 7: [{'type': 'label', 'text': 'THE REAL DANGER', 'color': YEL, 'pos': [.5, .13], 'from': .3},
     {'type': 'label', 'text': 'REAL ANATOMY: BODYPARTS3D', 'color': GREY, 'pos': [.72, .955], 'from': .2}],
 8: [{'type': 'label', 'text': "DON'T HOLD YOUR BREATH", 'color': [255, 90, 80], 'pos': [.5, .13], 'from': .5}],
 9: [{'type': 'label', 'text': 'EXHALE', 'color': WH, 'pos': [.5, .16], 'from': .3},
     {'type': 'label', 'text': '~15 S = 1/5 OF THIS VIDEO', 'color': YEL, 'pos': [.5, .13], 'from': 1.6}],
 10: [{'type': 'label', 'text': 'EBULLISM', 'color': YEL, 'pos': [.5, .13], 'from': .4},
      {'type': 'label', 'text': 'BODY WATER -> VAPOR', 'color': WH, 'pos': [.5, .19], 'from': 1.2}],
 11: [{'type': 'badge', 'value': 'up to 2x', 'unit': 'size', 'pos': [.5, .15], 'from': .8}],
 12: [{'type': 'datestamp', 'text': '1960 · HIGH-ALTITUDE BALLOON', 'from': .2},
      {'type': 'label', 'text': 'JOE KITTINGER', 'color': YEL, 'pos': [.5, .2], 'from': .9},
      {'type': 'label', 'text': 'ILLUSTRATION', 'color': GREY, 'pos': [.8, .955], 'from': .2}],
 13: [{'type': 'badge', 'value': '~2x', 'unit': 'hand size', 'pos': [.5, .15], 'from': .6}],
 14: [{'type': 'datestamp', 'text': 'HOUSTON, TEXAS · 1966', 'from': .2},
      {'type': 'label', 'text': 'NASA VACUUM CHAMBER', 'color': YEL, 'pos': [.5, .2], 'from': 1.6},
      {'type': 'label', 'text': 'ILLUSTRATION', 'color': GREY, 'pos': [.8, .955], 'from': .2}],
 15: [{'type': 'bubble', 'text': '"I could feel the saliva on', 'pos': [.5, .13], 'size': 52, 'from': .8},
      {'type': 'bubble', 'text': 'my tongue starting to bubble"', 'pos': [.5, .205], 'size': 52, 'from': 1.0},
      {'type': 'label', 'text': '- JIM LEBLANC', 'color': WH, 'pos': [.5, .28], 'from': 1.2}],
 16: [{'type': 'label', 'text': 'PASSED OUT', 'color': [255, 90, 80], 'pos': [.5, .12], 'from': 1.0}],
 17: [{'type': 'label', 'text': 'AIR BACK IN', 'color': WH, 'pos': [.5, .14], 'from': .3},
      {'type': 'label', 'text': 'NO LASTING HARM', 'color': YEL, 'pos': [.5, .2], 'from': 2.2}],
 18: [{'type': 'label', 'text': 'ANIMAL TESTS (DOGS)', 'color': WH, 'pos': [.5, .12], 'from': .2},
      {'type': 'label', 'text': 'RESCUED IN 90 S: ALMOST ALL SURVIVED', 'color': YEL, 'pos': [.5, .17], 'from': 2.6}],
 19: [{'type': 'badge', 'value': '~2', 'unit': 'minutes', 'pos': [.5, .15], 'from': .4}],
 20: [{'type': 'label', 'text': '= BRUSHING YOUR TEETH', 'color': YEL, 'pos': [.5, .12], 'from': .3}],
 21: [{'type': 'cta'}],
}[idx]

if __name__ == '__main__':
    out = f'{ROOT}/s{idx}'; os.makedirs(out, exist_ok=True)
    SH = shots(); bounds = [s for s, _ in SH] + [D + PAD]
    only = [int(a) for a in sys.argv[2:]]
    for f in (only or range(1, NF + 1)):
        T = (f - 1) / FPS - .35
        Tc = max(T, 0); k = max(j for j in range(len(SH)) if SH[j][0] <= Tc or j == 0)
        t0, t1 = bounds[k], bounds[k + 1]; u = (Tc - t0) / max(t1 - t0, .1)
        img = SH[k][1](T - t0 + (.35 if k == 0 else 0), u)
        cv2.imwrite(f'{out}/f_{f:04d}.png', np.clip(img, 0, 255).astype(np.uint8), [cv2.IMWRITE_PNG_COMPRESSION, 1])
    json.dump({'frames': NF, 'overlays': OV}, open(f'{out}/meta.json', 'w'))
    print('scene', idx, NF)
