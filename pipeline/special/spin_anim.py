"""Animate every scene of "What if Earth suddenly stopped spinning?" with 2D motion over the Cycles plates (spin_plate.py) and a
real-data globe drawn here: an orthographic projection of the Blue Marble day map, Black Marble night lights, the cloud map and the
ocean-glint mask (the same Solar System Scope / NASA maps kit.earth uses), so the spin, the sudden stop, the year-long day and the
draining oceans are true motion. The Earth turns west to east (features move left to right with north up), as it really does.
python3 spin_anim.py <scene> [frames...]  ->  spin/s<scene>/f_####.png + meta.json (overlays read by compose.py)"""
import sys, math, json, os
sys.path.insert(0, '/home/claude/pro')
import numpy as np, cv2, skia
import engine as E
ROOT = '/home/claude/b3d/spin'; CFG = json.load(open(f'{ROOT}/topic.json')); TEXD = '/home/claude/b3d/assets/textures'
FPS = 24; PAD = .75; idx = int(sys.argv[1]); D = CFG['durs'][idx]; NF = int(math.ceil((D + PAD) * FPS))
W, H = 1080, 1920
ease = lambda t: .5 - .5 * math.cos(math.pi * min(max(t, 0), 1))
eout = lambda t: 1 - (1 - min(max(t, 0), 1)) ** 3
clamp = lambda t: min(max(t, 0.0), 1.0)
XX = np.arange(W, dtype=np.float32)[None, :]; YY = np.arange(H, dtype=np.float32)[:, None]

# ------------------------------------------------------------------ textures (lazy)
TX = {}
def tex(n, gray=False):
    if n not in TX:
        im = cv2.imread(f'{TEXD}/{n}.jpg', cv2.IMREAD_GRAYSCALE if gray else cv2.IMREAD_COLOR)
        TX[n] = im
    return TX[n]

def stars(T=0.0, k=.55, drift=4.0):
    """real Milky Way star map, a dark slice of it as the space backdrop, slowly drifting"""
    if 'bg' not in TX:
        s = tex('stars_milky_way'); sl = s[1100:1100 + 1600, 2600:2600 + 900]
        TX['bg'] = cv2.resize(sl, (W + 200, H + 200), interpolation=cv2.INTER_CUBIC).astype(np.float32)
    b = TX['bg']; ox = int(100 + 60 * math.sin(T * .05 * drift)); oy = int(100 + 40 * math.cos(T * .04 * drift))
    return b[oy:oy + H, ox:ox + W] * k

def latlon_view(lat, lon, lon0, lat0):
    """unit vector in view space (x right, y up, z toward the viewer) of a point on the globe"""
    la, lo, a = math.radians(lat), math.radians(lon - lon0), math.radians(lat0)
    xg, yg, zg = math.cos(la) * math.sin(lo), math.sin(la), math.cos(la) * math.cos(lo)
    return xg, yg * math.cos(a) - zg * math.sin(a), yg * math.sin(a) + zg * math.cos(a)

def gpt(lat, lon, g):
    """screen point of (lat, lon) for globe params g = dict(cx, cy, R, lon0, lat0); returns (x, y, visible)"""
    x, y, z = latlon_view(lat, lon, g['lon0'], g['lat0']); return g['cx'] + x * g['R'], g['cy'] - y * g['R'], z > 0

def globe(img, cx, cy, R, lon0, lat0=10.0, sun=(-.55, .25, .8), clouds=True, cloud_lon=0.0, night=1.0, atmo=1.0, recolor=None,
          kind='earth', glint=True):
    """draw the real-data Earth (or Moon) into img (float BGR) - orthographic, lit by `sun` (view-space direction)"""
    s = np.array(sun, np.float32); s /= np.linalg.norm(s)
    ext = R * 1.12; x0, x1 = int(max(0, cx - ext)), int(min(W, cx + ext)); y0, y1 = int(max(0, cy - ext)), int(min(H, cy + ext))
    if x1 <= x0 or y1 <= y0: return img
    xs = (XX[:, x0:x1] - cx) / R; ys = -(YY[y0:y1] - cy) / R
    r2 = xs * xs + ys * ys; r = np.sqrt(r2); inside = r2 < 1
    z = np.sqrt(np.clip(1 - r2, 0, 1))
    a = math.radians(lat0); ca, sa = math.cos(a), math.sin(a)
    yg = ys * ca + z * sa; zg = -ys * sa + z * ca
    lat = np.degrees(np.arcsin(np.clip(yg, -1, 1))); lon = lon0 + np.degrees(np.arctan2(xs, zg))
    lon = (lon + 180) % 360 - 180
    sub = img[y0:y1, x0:x1]
    dif = xs * s[0] + ys * s[1] + z * s[2]
    if kind == 'moon':
        t = tex('moon'); th, tw = t.shape[:2]
        mu = ((lon + 180) / 360 * tw).astype(np.float32); mv = ((90 - lat) / 180 * th).astype(np.float32)
        col = cv2.remap(t, mu, mv, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP).astype(np.float32)
        out = col * (np.clip(dif, 0, 1) ** .9 * 1.15 + .025)[..., None]
    else:
        t = tex('earth_day'); th, tw = t.shape[:2]
        mu = ((lon + 180) / 360 * tw).astype(np.float32); mv = ((90 - lat) / 180 * th).astype(np.float32)
        col = cv2.remap(t, mu, mv, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP).astype(np.float32)
        sp = tex('earth_specular', True); sh_, sw_ = sp.shape
        water = cv2.remap(sp, mu * sw_ / tw, mv * sh_ / th, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP).astype(np.float32) / 255
        if recolor is not None: col, water = recolor(col, water, lat, lon)
        lit = np.clip(dif, 0, 1)
        term = np.clip(1 - np.abs(dif) * 5, 0, 1) * (dif > -.05)             # warm band along the terminator
        out = col * (lit ** .85 * 1.18 + .018)[..., None]
        out += (term * .25 * lit)[..., None] * np.array([40, 110, 255], np.float32) * .25
        if glint:
            hv = s + np.array([0, 0, 1], np.float32); hv /= np.linalg.norm(hv)
            nh = np.clip(xs * hv[0] + ys * hv[1] + z * hv[2], 0, 1)
            out += (water * nh ** 70 * 210 * (dif > 0))[..., None] * np.array([.95, .9, .8], np.float32)
        if night > 0:
            nl = tex('earth_night'); nn = cv2.remap(nl, mu, mv, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP).astype(np.float32)
            dark = np.clip((.06 - dif) / .22, 0, 1)
            out += nn * np.array([.55, .8, 1.15], np.float32) * (dark * night * 1.4)[..., None]
        if clouds:
            cl = tex('earth_clouds', True); cu = (((lon - cloud_lon + 180) % 360) / 360 * tw).astype(np.float32)
            cc = cv2.remap(cl, cu, mv, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP).astype(np.float32) / 255
            cc = cc ** 1.4 * .92
            out = out * (1 - cc[..., None]) + (cc * (lit ** .9 * 250 + 4))[..., None] * np.array([1, 1, .98], np.float32)
        haze = (1 - z) ** 2.2 * np.clip(dif + .25, 0, 1)                    # blue limb haze inside the disk
        out = out * (1 - .45 * haze[..., None]) + (haze * 150)[..., None] * np.array([1, .62, .3], np.float32) * atmo
    aa = np.clip((1 - r) * R, 0, 1)[..., None]
    res = sub * (1 - aa) + out * aa
    if kind != 'moon' and atmo > 0:   # thin glowing atmosphere just outside the limb, on the day side
        rim = np.exp(-np.clip(r - 1, 0, None) * R / (R * .022)) * (r >= .995)
        nx, ny = xs / np.maximum(r, 1e-3), ys / np.maximum(r, 1e-3)
        dl = np.clip(nx * s[0] + ny * s[1] + .35, 0, 1)
        res += (rim * dl * 190 * atmo)[..., None] * np.array([1, .6, .28], np.float32)
    img = img.copy(); img[y0:y1, x0:x1] = res
    return img

# ------------------------------------------------------------------ plates + camera moves
PL = {}
def plate(name):
    if name not in PL:
        im = cv2.imread(f'{ROOT}/plates/{name}.png', cv2.IMREAD_COLOR)
        if im.shape[1] != W: im = cv2.resize(im, (W, H), interpolation=cv2.INTER_CUBIC)
        PL[name] = im.astype(np.float32)
    return PL[name]
FXD = {}
def fx(pl, k, d=(.5, .5)):
    if pl not in FXD:
        p = f'{ROOT}/plates/fx_{pl}.json'; FXD[pl] = json.load(open(p)) if os.path.exists(p) else {}
    return FXD[pl].get(k, d)
def cclamp(cx, cy, z):
    m = 14 / max(z, 1e-3); hx, hy = W / (2 * z) + m, H / (2 * z) + m
    if hx < W / 2: cx = min(max(cx, hx), W - hx)
    if hy < H / 2: cy = min(max(cy, hy), H - hy)
    return cx, cy
def kb(name, u, z0, z1, c0=(.5, .5), c1=(.5, .5), src=None, shake=0.0, T=0.0, rot=0.0):
    im = plate(name) if src is None else src; t = ease(u); z = z0 + (z1 - z0) * t
    cx = (c0[0] + (c1[0] - c0[0]) * t) * W; cy = (c0[1] + (c1[1] - c0[1]) * t) * H; cx, cy = cclamp(cx, cy, z)
    sx = shake * (math.sin(T * 47) + .6 * math.sin(T * 83 + 1)) * 9; sy = shake * (math.sin(T * 53 + 2) + .6 * math.sin(T * 71)) * 9
    Mt = cv2.getRotationMatrix2D((cx, cy), rot, z); Mt[0, 2] += W / 2 - cx + sx; Mt[1, 2] += H / 2 - cy + sy
    return cv2.warpAffine(im, Mt, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
def kb_pt(px, py, u, z0, z1, c0=(.5, .5), c1=(.5, .5)):
    t = ease(u); z = z0 + (z1 - z0) * t
    cx = (c0[0] + (c1[0] - c0[0]) * t) * W; cy = (c0[1] + (c1[1] - c0[1]) * t) * H; cx, cy = cclamp(cx, cy, z)
    return W / 2 + (px * W - cx) * z, H / 2 + (py * H - cy) * z, z

# ------------------------------------------------------------------ effects
def glow(img, x, y, r, a, col=(210, 245, 255)):
    if a <= 0: return img
    x0, x1 = int(max(0, x - 3 * r)), int(min(W, x + 3 * r)); y0, y1 = int(max(0, y - 3 * r)), int(min(H, y + 3 * r))
    if x1 <= x0 or y1 <= y0: return img
    d2 = ((XX[:, x0:x1] - x) ** 2 + (YY[y0:y1] - y) ** 2) / (r * r)
    g = (np.exp(-d2 * 2.2) + np.exp(-d2 * .35) * .35) * a
    img = img.copy(); img[y0:y1, x0:x1] += g[..., None] * np.array(col, np.float32); return img
RNG = np.random.default_rng(11); MOTES = RNG.random((160, 4))
def dust(img, T, col=(150, 190, 255), k=1.0, drift=(8, -14)):
    lay = np.zeros_like(img)
    for x, y, s, b in MOTES:
        px = int((x * W + T * drift[0] * (.5 + s) + 14 * math.sin(T * .6 + y * 7)) % W); py = int((y * H + T * drift[1] * (.5 + s)) % H)
        v = (20 + 60 * b * b) * k; cv2.circle(lay, (px, py), 1 + int(s * 2.4), (col[0] * v / 255, col[1] * v / 255, col[2] * v / 255), -1, cv2.LINE_AA)
    return img + cv2.GaussianBlur(lay, (0, 0), 1.4)
def wind(img, T, a=1.0, n=45, seed=3, col=(120, 150, 175), speed=2.2, y0=0, y1=H):
    """horizontal wind/dust streaks racing east (screen right)"""
    if a <= 0: return img
    lay = np.zeros_like(img); P = np.random.default_rng(seed).random((n, 4))
    for u, v, s, ph in P:
        t = (u + T * speed * (.5 + s)) % 1.0; sx = -400 + t * (W + 800); sy = y0 + v * (y1 - y0) + 30 * math.sin(T * 3 + ph * 9)
        L = 120 + 360 * s; cv2.line(lay, (int(sx), int(sy)), (int(sx - L), int(sy + L * .04)), col, 1 + int(3 * s * s), cv2.LINE_AA)
    return img + cv2.GaussianBlur(lay, (0, 0), 4.5) * .4 * a
def haze(img, a, col=(95, 130, 165)):
    if a <= 0: return img
    g = np.clip((YY / H - .25) * 1.6, 0, 1)[..., None] * 0 + 1
    return img * (1 - a) + (img.mean(2, keepdims=True) * .35 + np.array(col, np.float32) * .65) * a
def tint(img, col, a): return img * (1 - a) + (img.mean(2, keepdims=True) * np.array(col, np.float32) / 255) * a
def desat(img, a, dark=0.0): g = img.mean(2, keepdims=True); return (img * (1 - a) + g * a) * (1 - dark)
def vignette(img, a):
    m = np.clip(((XX / W - .5) ** 2 + (YY / H - .5) ** 2 * .45) * 3.2, 0, 1); return img * (1 - m[..., None] * a)
def blurdim(img, a):
    if a <= 0: return img
    b = cv2.GaussianBlur(img, (0, 0), 3 + 22 * a); return vignette(b * (1 - .55 * a), a)
def flash(img, a): return img + 255 * max(a, 0)
def grade_gold(img, a=1.0):   # golden-hour plates pushed into the channel palette: teal shadows, warm highlights
    lum = img.mean(2, keepdims=True) / 255
    return img * (1 - .25 * a) + a * .25 * (lum * np.array([60, 170, 255], np.float32) + (1 - lum) * np.array([70, 45, 15], np.float32))

# ------------------------------------------------------------------ debris sprites (RGBA renders) flying east
SP = {}
def sprite(n):
    if n not in SP:
        p = f'{ROOT}/plates/sp_{n}.png'; im = cv2.imread(p, cv2.IMREAD_UNCHANGED)
        if im is None: im = np.zeros((600, 600, 4), np.uint8)
        ys_, xs_ = np.nonzero(im[..., 3] > 8)
        if len(xs_): im = im[max(0, ys_.min() - 4):ys_.max() + 5, max(0, xs_.min() - 4):xs_.max() + 5]
        SP[n] = im.astype(np.float32)
    return SP[n]
def paste(img, spr, x, y, w, ang=0.0, blur=0, a=1.0, dark=0.0):
    h = int(spr.shape[0] * w / spr.shape[1]); w = int(w)
    if w < 4 or h < 4: return img
    s = cv2.resize(spr, (w, h), interpolation=cv2.INTER_AREA)
    D_ = int(math.hypot(w, h)) + 4; can = np.zeros((D_, D_, 4), np.float32); ox, oy = (D_ - w) // 2, (D_ - h) // 2; can[oy:oy + h, ox:ox + w] = s
    Mr = cv2.getRotationMatrix2D((D_ / 2, D_ / 2), ang, 1); can = cv2.warpAffine(can, Mr, (D_, D_))
    if blur > 1:   # horizontal motion blur
        k = np.zeros((1, int(blur)), np.float32); k[:] = 1 / int(blur); can = cv2.filter2D(can, -1, k)
    x0, y0 = int(x - D_ / 2), int(y - D_ / 2); X0, Y0 = max(0, x0), max(0, y0); X1, Y1 = min(W, x0 + D_), min(H, y0 + D_)
    if X1 <= X0 or Y1 <= Y0: return img
    c = can[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0]; al = c[..., 3:4] / 255 * a
    img = img.copy(); img[Y0:Y1, X0:X1] = img[Y0:Y1, X0:X1] * (1 - al) + c[..., :3] * (1 - dark) * al; return img
DEB = np.random.default_rng(21).random((26, 6))
KINDS = ['board', 'roof', 'bin', 'board', 'tree', 'roof', 'board', 'bin']
def debris(img, T, a=1.0, n=14, scale=1.0, y0=.4, y1=.64, speed=1.0, include=None):
    """boards, roof panels, bins and whole trees tumbling east (right) at speed, with motion blur"""
    for k in range(n):
        u, v, s, ph, sp_, rr = DEB[k % len(DEB)]; kd = include[k % len(include)] if include else KINDS[k % len(KINDS)]
        t = (ph + T * (.55 + .5 * sp_) * speed) % 1.25 - .15
        x = -250 + t * (W + 500); y = (y0 + (y1 - y0) * v) * H - 120 * t * (rr - .3)
        wpx = (40 + 90 * s) * scale * (2.2 if kd == 'tree' else 1)
        img = paste(img, sprite(kd), x, y, wpx, ang=(T * (200 + 300 * rr) * (1 if k % 2 else -1)) % 360, blur=22 + 40 * sp_, a=a, dark=.25)
    return img

# ------------------------------------------------------------------ skia helpers
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
def text(c, s, x, y, size, col=(255, 255, 255), a=255, align='c', outline=True):
    f = skia.Font(E.TF, size); w = f.measureText(s); x0 = x - w / 2 if align == 'c' else (x - w if align == 'r' else x)
    if outline: c.drawString(s, x0, y, f, Pn((0, 0, 0), a * .85, 'stroke', size * .14))
    c.drawString(s, x0, y, f, Pn(col, a))
GOLD = (255, 205, 70); CYAN = (110, 215, 255); WHITE = (255, 255, 255); RED = (255, 80, 60); GREY = (200, 200, 200); BLUE = (90, 170, 255)
def arrow(c, x0, y0, x1, y1, col, a, w=8, head=22):
    c.drawLine(x0, y0, x1, y1, Pn(col, a, 'stroke', w)); ang = math.atan2(y1 - y0, x1 - x0)
    pth = skia.Path(); pth.moveTo(x1 + math.cos(ang) * head * .4, y1 + math.sin(ang) * head * .4)
    pth.lineTo(x1 - math.cos(ang - .5) * head, y1 - math.sin(ang - .5) * head); pth.lineTo(x1 - math.cos(ang + .5) * head, y1 - math.sin(ang + .5) * head); pth.close()
    c.drawPath(pth, Pn(col, a))

# ------------------------------------------------------------------ globe shots
def G(cx=W / 2, cy=H * .47, R=430, lon0=10.0, lat0=12.0): return dict(cx=cx, cy=cy, R=R, lon0=lon0, lat0=lat0)
SPIN_DPS = 26.0   # degrees of longitude per second on screen (sped up for the eye; labeled)
def earth(T, g, sun=(-.55, .25, .8), spin=True, k_bg=.55, **kw):
    img = stars(T, k_bg); lon0 = g['lon0'] - (SPIN_DPS * T if spin is True else (spin if spin else 0))
    gg = dict(g, lon0=lon0)
    return globe(img, g['cx'], g['cy'], g['R'], lon0, g['lat0'], sun, cloud_lon=-2 * T if spin else 0, **kw), gg
def spin_arrows(img, g, a=1.0, T=0.0, lats=(0,), col=GOLD, lens=None):
    """curved arrows along latitude circles on the visible face, pointing east (direction of rotation)"""
    surf, c = sk_begin(img)
    for k, la in enumerate(lats):
        L = (lens[k] if lens else 50) * clamp(a * 1.4)
        ph = (T * 14) % 30
        for s0 in range(-60, 60, 40):
            lo0 = g['lon0'] + s0 + ph - 15; pts = [gpt(la, lo0 + d, g) for d in np.linspace(0, L, 14)]
            pts = [(x, y) for x, y, v in pts if v]
            if len(pts) < 3: continue
            pth = skia.Path(); pth.moveTo(*pts[0])
            for q in pts[1:]: pth.lineTo(*q)
            c.drawPath(pth, Pn(col, 255 * a, 'stroke', 9)); arrow(c, *pts[-2], *pts[-1], col, 255 * a, 9, 26)
    return sk_end(surf)
def latline(img, g, lat, col=GOLD, a=1.0, w=6, glow_=True):
    surf, c = sk_begin(img); pts = [gpt(lat, g['lon0'] + d, g) for d in np.linspace(-95, 95, 120)]
    pth = skia.Path(); first = True
    for x, y, v in pts:
        if not v: first = True; continue
        if first: pth.moveTo(x, y); first = False
        else: pth.lineTo(x, y)
    if glow_: c.drawPath(pth, Pn(col, 120 * a, 'stroke', w * 3, blur=10))
    c.drawPath(pth, Pn(col, 255 * a, 'stroke', w)); return sk_end(surf)
def marker(img, x, y, T, a=1.0, col=(80, 220, 255), lab=None):
    surf, c = sk_begin(img)
    for k in range(3):
        t = (T * .7 + k / 3) % 1.0; c.drawCircle(x, y, 16 + 80 * t, Pn(col, 255 * a * (1 - t), 'stroke', 5))
    c.drawCircle(x, y, 12, Pn(col, 255 * a)); c.drawCircle(x, y, 24, Pn(col, 160 * a, blur=10))
    if lab: text(c, lab, x, y - 40, 46, WHITE, 255 * a)
    return sk_end(surf)
def bars(img, u, rows, title=None, maxv=1100, y0=H * .2):
    """comparison bars: rows = [(label, value, color, text)]"""
    surf, c = sk_begin(img); a = 255 * eout(u * 3)
    c.drawRoundRect(skia.Rect.MakeXYWH(60, y0 - 90, W - 120, 120 + 150 * len(rows)), 30, 30, Pn((8, 12, 20), 200 * a / 255))
    if title: text(c, title, W / 2, y0 - 22, 44, GREY, a)
    for k, (lab, v, col, tx) in enumerate(rows):
        yy = y0 + 40 + 150 * k; p = eout(u * 1.8 - k * .25); L = (W - 240) * v / maxv * p
        text(c, lab, 120, yy, 44, WHITE, a, 'l')
        c.drawRoundRect(skia.Rect.MakeXYWH(120, yy + 18, max(L, 1), 50), 25, 25, Pn(col, a))
        text(c, tx, min(120 + L + 20, W - 330), yy + 60, 46, col, a * clamp(p * 2), 'l')
    return sk_end(surf)

# ------------------------------------------------------------------ scene-specific graphics
def field_lines(img, g, T, a=1.0, fade=0.0):
    """Earth's magnetic field as a dipole (r = L cos^2 lat) with flowing dashes; the solar wind streams in from the Sun (left) and
    is turned aside at the field's edge - or, with fade -> 1, gets through to the surface"""
    surf, c = sk_begin(img); R = g['R']; cx, cy = g['cx'], g['cy']; al = 255 * a * (1 - .85 * fade)
    for Lsh in (1.35, 1.8, 2.4, 3.2):
        for sgn in (-1, 1):
            pth = skia.Path(); first = True
            for la in np.linspace(-1.2, 1.2, 80):
                r = Lsh * math.cos(la) ** 2
                if r < 1.0: first = True; continue
                x, y = cx + sgn * r * math.cos(la) * R, cy - r * math.sin(la) * R
                if first: pth.moveTo(x, y); first = False
                else: pth.lineTo(x, y)
            p = Pn(BLUE, al, 'stroke', 5); p.setPathEffect(skia.DashPathEffect.Make([26, 18], -T * 60)); c.drawPath(pth, p)
            c.drawPath(pth, Pn(BLUE, al * .35, 'stroke', 14, blur=8))
    rng = np.random.default_rng(5); P = rng.random((40, 3))
    for u, v, s in P:   # solar wind from the left
        t = (u + T * (.6 + .4 * s)) % 1.0; y = cy + (v - .5) * R * 4.4; x = -100 + t * (cx - R * (3.0 - 2.0 * fade) + 100) * 1.0
        if abs(y - cy) < R * (3.2 - 2.2 * fade) and x > cx - R * (3.3 - 2.3 * fade):
            continue
        c.drawLine(x, y, x - 80 - 60 * s, y, Pn((255, 210, 120), 200 * a, 'stroke', 4))
    if fade > 0:
        for u, v, s in P[:18]:
            t = (u + T * (.8 + .4 * s)) % 1.0; y = cy + (v - .5) * R * 1.6; x = cx - R * 2.6 + t * R * 1.7
            if (x - cx) ** 2 + (y - cy) ** 2 < R * R: c.drawCircle(x, y, 10, Pn(RED, 220 * fade, blur=6)); continue
            c.drawLine(x, y, x - 70, y, Pn((255, 150, 90), 230 * fade, 'stroke', 5))
    return sk_end(surf)

def bulge(img, g, u, T, part='shell'):
    """cross-section: the ocean layer pushed out at the equator by the spin (thickness EXAGGERATED), measured against the poles"""
    surf, c = sk_begin(img); R = g['R']; cx, cy = g['cx'], g['cy']; a = 255 * eout(u * 2.5); ex = .16 * eout(u * 1.6)
    pth = skia.Path()
    for k, th in enumerate(np.linspace(0, 2 * math.pi, 200)):
        rr = R * (1.02 + ex * math.cos(th) ** 2); x, y = cx + rr * math.cos(th), cy - rr * math.sin(th)
        (pth.moveTo if k == 0 else pth.lineTo)(x, y)
    pth.close()
    if part == 'shell':
        c.drawPath(pth, Pn((40, 120, 255), a * .75)); c.drawPath(pth, Pn((120, 200, 255), a, 'stroke', 5)); return sk_end(surf)
    c.drawLine(cx - R * 1.35, cy, cx + R * 1.35, cy, Pn(GOLD, a * .8, 'stroke', 3))
    text(c, 'EQUATOR', cx + R * .62, cy - 18, 38, GOLD, a)
    xr = cx + R * (1.02 + ex) + 18
    if ex > .02:
        c.drawLine(xr + 14, cy, xr + 14, cy - R * ex, Pn(WHITE, a, 'stroke', 4)); c.drawLine(cx + R * 1.02 + 4, cy, xr + 30, cy, Pn(WHITE, a, 'stroke', 3))
    text(c, 'THICKNESS EXAGGERATED', W / 2, cy + R * 1.38, 38, GREY, a)
    return sk_end(surf)

def drain(t):
    """oceans flowing to the poles (SIMPLIFIED after Esri's model): t 0 -> 1, today's oceans near the equator drain,
    the high latitudes flood, leaving one land belt around the middle"""
    thr = 90 - 42 * eout(t)   # final water boundary ~48 deg (simplified)
    def rec(col, water, lat, lon):
        al = np.abs(lat); noise = (col.mean(2) / 255)
        band = (al < thr - 6).astype(np.float32); edge = np.clip((al - (thr - 6)) / 6, 0, 1)
        seabed = np.stack([noise * 60 + 45, noise * 90 + 80, noise * 110 + 110], -1).astype(np.float32)   # exposed sea floor (BGR tan-grey)
        drained = water * np.clip(t * 1.6, 0, 1) * band
        col = col * (1 - drained[..., None]) + seabed * drained[..., None]
        polar = np.clip((al - thr) / 4, 0, 1) * (t > 0)
        sea = np.array([70, 32, 8], np.float32) + (col.mean(2, keepdims=True) * .1)
        col = col * (1 - polar[..., None]) + sea * polar[..., None]
        return col, np.clip(water * (1 - drained) + polar, 0, 1)
    return rec

def clock18(img, u, T):
    """a 24-hour dial with today's day vs the 18-hour day of 1.4 billion years ago"""
    surf, c = sk_begin(img); cx, cy, Rr = W / 2, H * .37, 260; a = 255 * eout(u * 3)
    c.drawCircle(cx, cy, Rr + 40, Pn((8, 12, 20), 215 * a / 255)); c.drawCircle(cx, cy, Rr, Pn((80, 90, 110), a, 'stroke', 30))
    ov = skia.Rect.MakeXYWH(cx - Rr, cy - Rr, 2 * Rr, 2 * Rr); p = eout(u * 1.5)
    c.drawArc(ov, -90, 360 * 18 / 24 * p, False, Pn(GOLD, a, 'stroke', 30))
    for h in range(24):
        ang = math.radians(h * 15 - 90); r0 = Rr - 40 if h % 6 == 0 else Rr - 26
        c.drawLine(cx + math.cos(ang) * r0, cy + math.sin(ang) * r0, cx + math.cos(ang) * (Rr - 14), cy + math.sin(ang) * (Rr - 14), Pn(WHITE, a * .7, 'stroke', 4))
    text(c, '18 HRS', cx, cy + 20, 100, GOLD, a); text(c, 'TODAY: 24', cx, cy + 90, 44, GREY, a)
    return sk_end(surf)

def ms_counter(img, u, T):
    surf, c = sk_begin(img); a = 255 * eout(u * 3)
    c.drawRoundRect(skia.Rect.MakeXYWH(W / 2 - 330, H * .27, 660, 170), 30, 30, Pn((10, 14, 22), 215 * a / 255))
    v = 0.0017 * eout(u * 1.4)
    text(c, f'+{v:.4f} s', W / 2, H * .27 + 110, 96, GOLD, a, outline=False)
    text(c, 'PER DAY, EVERY 100 YEARS', W / 2, H * .27 + 160, 34, GREY, a, outline=False)
    return sk_end(surf)

def year_counter(img, u, T, days=None):
    surf, c = sk_begin(img); a = 255 * eout(u * 3)
    c.drawRoundRect(skia.Rect.MakeXYWH(W / 2 - 300, H * .25, 600, 150), 30, 30, Pn((10, 14, 22), 215 * a / 255))
    d = days if days is not None else int(1 + 364 * eout(u * 1.2))
    text(c, 'SUNRISE TO SUNSET + NIGHT', W / 2, H * .25 + 56, 40, GREY, a, outline=False)
    text(c, f'{d} DAYS', W / 2, H * .25 + 128, 76, GOLD, a, outline=False)
    return sk_end(surf)

def tide(img, gE, gM, u, a=1.0):
    """the tidal bulge (EXAGGERATED) pulled toward the Moon, dragged slightly ahead by the spin - friction slows the Earth"""
    surf, c = sk_begin(img); R = gE['R']; al = 255 * a * eout(u * 2.5)
    ang = math.atan2(gM['cy'] - gE['cy'], gM['cx'] - gE['cx']) - math.radians(12)
    c.save(); c.translate(gE['cx'], gE['cy']); c.rotate(math.degrees(ang))
    c.drawOval(skia.Rect.MakeXYWH(-R * 1.22, -R * 1.04, R * 2.44, R * 2.08), Pn((40, 130, 255), al * .4))
    c.drawOval(skia.Rect.MakeXYWH(-R * 1.22, -R * 1.04, R * 2.44, R * 2.08), Pn((120, 200, 255), al, 'stroke', 5))
    c.restore()
    return sk_end(surf)

# ------------------------------------------------------------------ shots
def shots():
    TC = fx('town', 'car', (.6, .63)); TH = fx('town', 'house', (.2, .55)); CC = fx('towncu', 'car', (.55, .6))
    LH = fx('coast', 'lighthouse', (.75, .45))
    def town(T, u, z0, z1, c0=(.5, .5), c1=(.5, .5), name='town', shake=0.0, storm=0.0):
        img = grade_gold(kb(name, u, z0, z1, c0, c1, shake=shake, T=T))
        if storm: img = haze(img, .35 * storm, (60, 85, 110)) * (1 - .25 * storm)
        return vignette(img, .45)
    def chaos(T, u, z0, z1, c0=(.5, .5), c1=(.5, .5), name='townempty', n=14, a=1.0, scale=1.0, shake=1.0, car=None):
        img = town(T, u, z0, z1, c0, c1, name, shake, 1.0)
        img = wind(img, T, 1.0, 45, 3, (120, 150, 175), 2.4, int(H * .3), int(H * .72))
        img = debris(img, T, a, n, scale)
        if car is not None:   # the car itself, swept off the road and tumbling east
            t0, cx, cy, w = car; k = eout(max(T - t0, 0) / 1.6); x, y, _ = kb_pt(cx, cy, u, z0, z1, c0, c1)
            img = paste(img, sprite('car'), x + k * W * 1.1, y - k * H * .07, w, -30 * k, 6 + 40 * k, dark=.15)
        return dust(img, T, (140, 175, 205), .6, (60, -4))
    def sea(T, u, z0, z1, c0=(.5, .5), c1=(.5, .5), storm=0.0, rot=0.0):
        img = kb('coast', u, z0, z1, c0, c1, shake=storm * 1.2, T=T, rot=rot)
        img = tint(img, (175, 200, 215), .25 + .3 * storm) * (1 - .3 * storm)
        if storm: img = wind(img, T, storm * .8, 50, 7, (200, 210, 220), 3.2, int(H * .5), int(H * .95))
        return vignette(img, .5)
    def desert(T, u, z0, z1):
        img = kb('desert', u, z0, z1, (.5, .45), (.5, .42)); img = glow(img, W * .62, H * .14, 160, .9 + .1 * math.sin(T * 3), (180, 235, 255))
        sh = np.sin(YY / 9 + T * 9) * 2.5 * (YY > H * .45); Mx = (XX + sh).astype(np.float32); My = np.repeat(YY, W, 1).astype(np.float32)
        img = cv2.remap(img, np.broadcast_to(Mx, (H, W)).astype(np.float32), My, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        return vignette(tint(img, (120, 190, 255), .3) * .72, .55)
    def frozen(T, u, z0, z1):
        img = kb('frozen', u, z0, z1, (.5, .5), (.5, .48)); img = tint(img, (255, 200, 150), .35)
        return dust(vignette(img, .5), T, (255, 240, 220), .8, (4, 10))
    gEq = G(lon0=12, lat0=14); gNY = G(lon0=-70, lat0=32); gPole = G(cy=H * .5, R=440, lon0=-40, lat0=62)
    def eq_dot(img, g, T, lon_off=0.0):
        x, y, v = gpt(0, g['lon0'] + lon_off, g); return glow(img, x, y, 22, 1.4, (120, 230, 255)) if v else img
    def hook(T, u):
        img = town(T, u, 1.08, 1.2, (.55, .55), (.6, .55), 'townempty', 1.4, 1.0)
        img = wind(img, T, 1.0, 45, 3, (120, 150, 175), 2.6, int(H * .3), int(H * .72))
        img = debris(img, T + 1.2, 1.0, 16, 1.3)
        img = paste(img, sprite('roof'), W * (.62 + .5 * T / 2.2), H * (.4 - .03 * T), 300, 40 + 160 * T, 30)
        img = paste(img, sprite('car'), W * (.26 + .5 * T / 2.2), H * (.54 - .05 * T), 560, -12 - 34 * T, 34, dark=.1)
        return dust(img * 1.18, T, (140, 175, 205), .8, (90, -4))
    def eq_shot(T):
        img, gg = earth(T, gEq); img = latline(img, gg, 0)
        for lo in (-40, -10, 20):
            img = eq_dot(img, gg, T, lo - gg['lon0'])
        return img
    def stopping(T, u, g, tstop, z0=1.0, z1=1.0, shake_a=1.0):
        """spinning globe that stops dead at tstop (seconds into the shot): flash + shake + a shock ring"""
        ang = SPIN_DPS * min(T, tstop)
        img, gg = earth(T, g, spin=ang)
        if T > tstop:
            k = max(0, 1 - (T - tstop) * 2.5); img = flash(img, .3 * k)
            surf, c = sk_begin(img); rr = g['R'] * (1.0 + (T - tstop) * 1.2)
            c.drawCircle(g['cx'], g['cy'], rr, Pn((255, 220, 160), 230 * k, 'stroke', 18, blur=6)); img = sk_end(surf)
            sx = shake_a * k * 22 * math.sin(T * 61); img = np.roll(img, int(sx), 1)
        else:
            img = spin_arrows(img, gg, .9, T, lats=(0,), lens=[46])
        return img
    S = {
     0: [(0, lambda T, u: hook(T, u))],
     1: [(0, lambda T, u: spin_arrows(*earth(T, gEq), .9, T, lats=(0, 35, -35), lens=[46, 38, 38])),
         (1.45, lambda T, u: stopping(T, u, G(R=520, lon0=-10, lat0=10), 1.0))],
     2: [(0, lambda T, u: eq_shot(T)),
         (2.4, lambda T, u: latline(earth(T + 2.4, G(cy=H * .62, R=900, lon0=-20, lat0=8))[0], G(cy=H * .62, R=900, lon0=-20 - SPIN_DPS * (T + 2.4), lat0=8), 0))],
     3: [(0, lambda T, u: bars(blurdim(earth(T + 5, gEq)[0], .6), u, [('SPEED OF SOUND', 761, CYAN, '~760 MPH'), ('GROUND AT THE EQUATOR', 1037, GOLD, '1,037 MPH')], 'AT SEA LEVEL'))],
     4: [(0, lambda T, u: (lambda im, gg: marker(im, *gpt(40.71, -74.0, gg)[:2], T, 1.0, (80, 220, 255), 'NEW YORK'))(*earth(T, gNY, spin=SPIN_DPS * .25 * T))),
         (2.2, lambda T, u: (lambda im, gg: latline(marker(im, *gpt(40.71, -74.0, gg)[:2], T, 1.0), gg, 40.71, CYAN, 1.0, 5))(*earth(T, G(cy=H * .55, R=820, lon0=-74, lat0=36), spin=SPIN_DPS * .2 * (T + 2))))],
     5: [(0, lambda T, u: dust(town(T, u, 1.0, 1.1, (.5, .5), (.52, .5)), T, (180, 220, 255), .4, (10, -3))),
         (1.7, lambda T, u: dust(town(T, u, 1.05, 1.15, (.55, .55), (.5, .52), 'towncu'), T, (180, 220, 255), .4, (10, -3)))],
     6: [(0, lambda T, u: stopping(T, u, G(R=470, lon0=30, lat0=12), .9, shake_a=1.3)),
         (1.6, lambda T, u: chaos(T, u, 1.0, 1.06, n=6, a=clamp(T * 1.2), shake=.6, car=(.3, TC[0], TC[1], 300)))],
     7: [(0, lambda T, u: chaos(T + 2, u, 1.0, 1.08, n=16)),
         (2.0, lambda T, u: chaos(T + 4, u, 1.1, 1.2, CC, CC, 'towncuempty', n=8, car=(0.2, CC[0], CC[1], 640))),
         (4.1, lambda T, u: chaos(T + 7, u, 1.3, 1.45, TH, TH, n=16, scale=1.4))],
     8: [(0, lambda T, u: wind(haze(chaos(T + 9, u, 1.0, 1.1, n=8), .45, (70, 95, 120)), T, 1.0, 70, 12, (140, 165, 185), 3.5)),
         (1.8, lambda T, u: wind(haze(chaos(T + 11, u, 1.2, 1.3, (.5, .6), (.5, .62), 'towncuempty', n=6), .55, (70, 95, 120)), T, 1.0, 80, 13, (140, 165, 185), 3.8))],
     9: [(0, lambda T, u: bars(blurdim(wind(haze(town(T, u, 1.0, 1.05, name='townempty', storm=1.0), .5), T, 1.0, 60), .55), u,
                               [('STRONGEST TORNADO MEASURED', 318, CYAN, '~300+ MPH'), ('STOPPED EARTH, EQUATOR', 1037, GOLD, '~1,000 MPH')], 'WIND SPEED')),
         (3.0, lambda T, u: wind(haze(chaos(T + 13, u, 1.25, 1.35, (.4, .55), (.45, .55), n=14, scale=1.2), .4), T, 1.0, 60, 14))],
     10: [(0, lambda T, u: sea(T, u, 1.05, 1.2, (.5, .55), (.5, .5), 1.0, rot=4 * math.sin(T * 1.3))),
          (1.75, lambda T, u: sea(T, u, 1.45, 1.6, LH, LH, 1.0, rot=-5 * math.sin(T * 1.1 + 1)))],
     11: [(0, lambda T, u: (lambda im, gg: spin_arrows(im, gg, 1.0, T, lats=(0, 40, 70, 85), col=GOLD, lens=[52, 40, 18, 5]))(*earth(T, gPole)))],
     12: [(0, lambda T, u: glow(earth(T, G(cx=W * .58, R=410), sun=(-1, 0, .08), spin=0)[0], -40, H * .47, 260, 1.4, (150, 225, 255))),
          (1.7, lambda T, u: year_counter(glow(earth(T, G(cx=W * .58, R=410, lon0=10 - 40 * eout(u)), sun=(-1, 0, .08), spin=0)[0], -40, H * .47, 260, 1.4, (150, 225, 255)), u, T))],
     13: [(0, lambda T, u: glow(earth(T, G(cx=W * .5, R=470, lon0=-60), sun=(-.15, .1, 1), spin=-8 * T)[0], W * .5, H * .1, 120, .6, (150, 225, 255))),
          (1.75, lambda T, u: earth(T, G(cx=W * .5, R=470, lon0=120), sun=(.15, .1, -1), spin=-8 * T)[0])],
     14: [(0, lambda T, u: desert(T, u, 1.0, 1.1)), (1.6, lambda T, u: frozen(T, u, 1.05, 1.15))],
     15: [(0, lambda T, u: field_lines(earth(T, G(R=250, cy=H * .5, lon0=0, lat0=15), sun=(-1, .1, .3))[0], G(R=250, cy=H * .5), T, eout(u * 3))),
          (2.2, lambda T, u: field_lines(earth(T + 2, G(R=250, cy=H * .5, lon0=0, lat0=15), sun=(-1, .1, .3))[0], G(R=250, cy=H * .5), T + 2, 1.0, eout(T / 1.6)))],
     16: [(0, lambda T, u: bulge_shot(T, u, 1.0)), (3.0, lambda T, u: bulge_shot(T + 3, 1.0, 1.35))],
     17: [(0, lambda T, u: earth(T, G(R=440, lon0=-30, lat0=20), spin=0, clouds=False, recolor=drain(clamp(T / 3.2)))[0]),
          (3.3, lambda T, u: earth(T, G(R=440, lon0=60 - 10 * T, lat0=-12), spin=0, clouds=False, recolor=drain(1.0))[0])],
     18: [(0, lambda T, u: tide_shot(T, u, 1.0)), (2.4, lambda T, u: tide_shot(T + 2.4, u, 1.6)), (4.8, lambda T, u: ms_counter(blurdim(tide_shot(T + 4.8, 1, 1.0), .55), u, T))],
     19: [(0, lambda T, u: fast_globe(T, u)), (2.3, lambda T, u: clock18(blurdim(fast_globe(T + 2.3, 1), .6), u, T))],
     20: [(0, lambda T, u: spin_arrows(*earth(T, G(R=470, lon0=-90, lat0=18), spin=SPIN_DPS * .5 * T), .8, T, lats=(0,), lens=[40])),
          (3.3, lambda T, u: town(T, u, 1.0, 1.08, TC, (.6, .55)))],
    }
    return S[idx]
def bulge_shot(T, u, zoom):
    g = G(R=360 * zoom, cy=H * .5, lon0=-20 - 6 * T, lat0=0); img = stars(T, .55)
    img = bulge(img, g, u, T, 'shell')
    img = globe(img, g['cx'], g['cy'], g['R'], g['lon0'], 0, (-.4, .2, .9), cloud_lon=0)
    return bulge(img, g, u, T, 'labels')
def tide_shot(T, u, zoom):
    gE = G(cx=W * .42, cy=H * .5, R=300 * zoom, lon0=10 - SPIN_DPS * .4 * T, lat0=10); gM = dict(cx=W * .42 + 520 * zoom, cy=H * .34, R=82 * zoom, lon0=0, lat0=0)
    img = stars(T, .55); img = tide(img, gE, gM, min(u * 2, 1) if zoom == 1.0 else 1)
    img = globe(img, gE['cx'], gE['cy'], gE['R'], gE['lon0'], 10, (-.6, .3, .75), cloud_lon=0)
    return globe(img, gM['cx'], gM['cy'], gM['R'], 0, 0, (-.6, .3, .75), kind='moon', clouds=False, atmo=0)
def fast_globe(T, u):
    img, gg = earth(T * 1.33, G(R=470, lon0=40, lat0=15)); return tint(img, (255, 210, 160), .3)   # the 18-hour day: the same spin, 1.33x faster

YEL, WH, GR = [255, 222, 40], [255, 255, 255], [200, 200, 200]
NASA = {'type': 'label', 'text': 'SPIN SPED UP', 'color': GR, 'pos': [.75, .955], 'from': .1}
ILL = {'type': 'label', 'text': 'ILLUSTRATION', 'color': GR, 'pos': [.8, .955], 'from': .1}
OV = {
 0: [{'type': 'hook', 'text': 'IF EARTH STOPPED|YOU FLY 1,000 MPH'}, dict(ILL, instant=True)],
 1: [{'type': 'label', 'text': 'EARTH SPINS WEST TO EAST', 'color': WH, 'pos': [.5, .13], 'from': .2}, NASA],
 2: [{'type': 'badge', 'value': '1,037', 'unit': 'mph', 'pos': [.5, .15], 'from': .5},
     {'type': 'label', 'text': 'GROUND SPEED AT THE EQUATOR', 'color': WH, 'pos': [.5, .225], 'from': .9}, NASA],
 3: [],
 4: [{'type': 'badge', 'value': '~790', 'unit': 'mph', 'pos': [.5, .15], 'from': .6}, NASA],
 5: [{'type': 'label', 'text': 'GROUND, AIR AND OCEANS', 'color': WH, 'pos': [.5, .13], 'from': .2},
     {'type': 'label', 'text': 'ALL MOVE TOGETHER', 'color': YEL, 'pos': [.5, .19], 'from': .7}, ILL],
 6: [{'type': 'label', 'text': 'THE PLANET STOPS...', 'color': WH, 'pos': [.5, .13], 'from': .1},
     {'type': 'label', 'text': '...NOTHING ON IT DOES', 'color': YEL, 'pos': [.5, .19], 'from': 1.6}, ILL],
 7: [{'type': 'label', 'text': 'EVERYTHING FLIES EAST', 'color': YEL, 'pos': [.5, .13], 'from': .3},
     {'type': 'badge', 'value': 'UP TO 1,000', 'unit': 'mph', 'pos': [.5, .21], 'from': 1.2}, ILL],
 8: [{'type': 'label', 'text': 'THE AIR KEEPS GOING', 'color': YEL, 'pos': [.5, .13], 'from': .3}, ILL],
 9: [ILL],
 10: [{'type': 'label', 'text': 'OCEANS SLOSH EAST', 'color': YEL, 'pos': [.5, .13], 'from': .3},
      {'type': 'label', 'text': 'GIANT TSUNAMIS', 'color': WH, 'pos': [.5, .19], 'from': 1.6}, ILL],
 11: [{'type': 'label', 'text': 'SLOWER NEAR THE POLES', 'color': YEL, 'pos': [.5, .1], 'from': .3}, NASA],
 12: [{'type': 'label', 'text': 'SUN', 'color': YEL, 'pos': [.12, .41], 'from': .3},
      {'type': 'label', 'text': '1 DAY = 1 YEAR', 'color': YEL, 'pos': [.5, .13], 'from': 1.2}, NASA],
 13: [{'type': 'label', 'text': '6 MONTHS OF SUNLIGHT', 'color': YEL, 'pos': [.5, .1], 'from': .3},
      {'type': 'label', 'text': '6 MONTHS OF DARKNESS', 'color': [110, 215, 255], 'pos': [.5, .16], 'from': 1.9}, NASA],
 14: [{'type': 'label', 'text': 'DAY SIDE BAKES', 'color': [255, 150, 60], 'pos': [.5, .13], 'from': .2},
      {'type': 'label', 'text': 'NIGHT SIDE FREEZES', 'color': [110, 215, 255], 'pos': [.5, .2], 'from': 1.8}, ILL],
 15: [{'type': 'label', 'text': 'MAGNETIC SHIELD', 'color': [110, 215, 255], 'pos': [.5, .13], 'from': .3},
      {'type': 'label', 'text': 'MIGHT FADE', 'color': YEL, 'pos': [.5, .19], 'from': 2.4}, ILL],
 16: [{'type': 'badge', 'value': '~5', 'unit': 'miles high', 'pos': [.5, .14], 'from': 2.0},
      {'type': 'label', 'text': 'ALMOST AS TALL AS EVEREST', 'color': WH, 'pos': [.5, .22], 'from': 3.1}],
 17: [{'type': 'label', 'text': 'OCEANS FLOW TO THE POLES', 'color': YEL, 'pos': [.5, .12], 'from': .3},
      {'type': 'label', 'text': 'ONE GIANT CONTINENT', 'color': WH, 'pos': [.5, .18], 'from': 3.4},
      {'type': 'label', 'text': 'SIMPLIFIED (ESRI MODEL)', 'color': GR, 'pos': [.5, .955], 'from': .1}],
 18: [{'type': 'label', 'text': 'MOON\'S TIDES = BRAKES', 'color': YEL, 'pos': [.5, .13], 'from': .3},
      {'type': 'label', 'text': 'NOT TO SCALE', 'color': GR, 'pos': [.8, .955], 'from': .1}],
 19: [{'type': 'datestamp', 'text': '1.4 BILLION YEARS AGO', 'from': .2}, ILL],
 20: [{'type': 'label', 'text': 'IT WILL NEVER FULLY STOP', 'color': YEL, 'pos': [.5, .25], 'from': .8}, {'type': 'cta'}],
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
