"""What if Yellowstone erupted? Every scene animated in 2D over the Cycles plates (ys_plate.py): procedural puff-particle ash
columns, pyroclastic flows and steam, plus real-data maps (Blue Marble globe from spin_anim.py; US state outlines from us-atlas /
US Census Bureau cartographic boundaries) for the ash footprint, Texas and Rhode Island comparisons.
python3 ys_anim.py <scene> [frames...] -> ys/s<scene>/f_####.png + meta.json"""
import sys, math, json, os
sys.path.insert(0, '/home/claude/pro')
import numpy as np, cv2, skia
import engine as E
ROOT = '/home/claude/b3d/ys'; CFG = json.load(open(f'{ROOT}/topic.json')); TEXD = '/home/claude/b3d/assets/textures'
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


# ================================================================== Yellowstone: procedural ash / steam (puff particles)
ORANGE = (255, 140, 40); ASHC = (170, 165, 160)
def fbm(n, seed, octaves=5, base=4):
    r = np.random.default_rng(seed); out = np.zeros((n, n), np.float32); amp = 1.0; tot = 0.0
    for o in range(octaves):
        s = base * 2 ** o; a = r.random((s + 1, s + 1)).astype(np.float32)
        out += cv2.resize(a, (n, n), interpolation=cv2.INTER_CUBIC) * amp; tot += amp; amp *= .5
    return out / tot
PUFFS = []
def puffs():
    if not PUFFS:
        n = 256; yy, xx = (np.mgrid[0:n, 0:n] / (n - 1) * 2 - 1).astype(np.float32)
        r = np.sqrt(xx ** 2 + yy ** 2)
        for k in range(8):
            f = fbm(n, 100 + k)
            al = np.clip((1 - r) * 2.4, 0, 1) * np.clip((f - .5) * 4 + (1 - r) * 1.6 - .15, 0, 1)
            sh = np.clip(.6 - yy * .5 - xx * .18 + (f - .5) * 1.1, 0, 1.15)
            bot = np.clip((yy + .1) * 1.3, 0, 1)
            PUFFS.append((al, sh, bot))
    return PUFFS
def puff(img, x, y, r, lit, dark, a=1.0, k=0, glow=0.0, gcol=(40, 120, 255)):
    """one billowing puff (BGR colors); glow = incandescent light from below"""
    s = int(2 * r)
    if s < 6 or a <= 0: return
    x0, y0 = int(x - r), int(y - r); X0, Y0, X1, Y1 = max(0, x0), max(0, y0), min(W, x0 + s), min(H, y0 + s)
    if X1 <= X0 or Y1 <= Y0: return
    al, sh, bot = puffs()[k % 8]
    al = cv2.resize(al, (s, s))[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0, None] * a
    sh = cv2.resize(sh, (s, s))[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0, None]
    col = np.array(dark, np.float32) + (np.array(lit, np.float32) - np.array(dark, np.float32)) * sh
    if glow > 0:
        bt = cv2.resize(bot, (s, s))[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0, None]; col = col + np.array(gcol, np.float32) * glow * bt
    sub = img[Y0:Y1, X0:X1]; sub *= (1 - al); sub += col * al
PR = np.random.default_rng(7).random((400, 6))
def ash_column(img, T, vx, vy, scale=1.0, top=None, n=110, umbrella=1.0, dark=1.0, grow=1.0, wide=1.0):
    """Plinian eruption column from vent (vx, vy) up to `top` (y px), umbrella cloud spreading sideways at the top.
    grow < 1 = the column still rising (fraction of its height reached)."""
    top = H * .06 if top is None else top; Hc = (vy - top) * grow
    items = []
    for i in range(n):
        ph, jx, sz, kk, sd, side = PR[i]
        t = (ph + T * (.11 + .05 * sd)) % 1.0
        if t > grow + .02: continue
        hgt = min(t / max(grow, 1e-3), 1) * Hc
        r = (40 + 150 * t ** .8) * scale * (.7 + .6 * sz) * wide
        x = vx + (jx - .5) * r * 1.1 + 14 * math.sin(T * .9 + i)
        y = vy - hgt
        ut = clamp((t - .72) / .28) * umbrella
        if ut > 0:
            x += (1 if side > .5 else -1) * (ut ** .8) * W * .75 * (.5 + sd) * scale; y += ut * 40 * scale; r *= 1 + 1.3 * ut
        g = clamp(1 - t / .35) ** 2
        items.append((t, x, y, r, int(kk * 8), g))
    for t, x, y, r, kk, g in sorted(items, key=lambda q: -q[0]):
        shade = 1 - .35 * dark * clamp(t)
        puff(img, x, y, r, (np.array([118, 122, 130]) * shade), (np.array([24, 26, 30]) * shade), 1.0, kk, glow=g * 1.6, gcol=(30, 110, 255))
    return img
def vent_glow(img, vx, vy, T, k=1.0, w=1.0):
    img = glow(img, vx, vy, 120 * w, 1.6 * k * (1 + .15 * math.sin(T * 13)), (40, 140, 255))
    return glow(img, vx, vy + 10, 360 * w, .5 * k, (20, 80, 230))
def embers(img, T, vx, vy, n=60, a=1.0, spread=1.0):
    lay = np.zeros_like(img); P = np.random.default_rng(4).random((n, 4))
    for u_, v_, s_, p_ in P:
        t = (p_ + T * (.5 + .5 * s_)) % 1.0; ang = (u_ - .5) * 1.6 * spread; sp = 500 + 700 * v_
        x = vx + math.sin(ang) * sp * t; y = vy - math.cos(ang) * sp * t + 600 * t * t
        cv2.circle(lay, (int(x), int(y)), 2 + int(3 * s_), (60, 170, 255), -1, cv2.LINE_AA)
    return img + cv2.GaussianBlur(lay, (0, 0), 2.0) * 2.2 * a
def lightning(img, T, x, y0, y1, t0, seed=1):
    dt = T - t0
    if dt < 0 or dt > .22: return img
    r = random.Random(seed); pts = [(x, y0)]; yy = y0
    while yy < y1: yy += r.uniform(30, 70); pts.append((pts[-1][0] + r.uniform(-45, 45), yy))
    surf, c = sk_begin(img); a = 255 * (1 - dt / .22)
    for k in range(len(pts) - 1):
        c.drawLine(*pts[k], *pts[k + 1], Pn((255, 230, 210), a * .6, 'stroke', 16, blur=10)); c.drawLine(*pts[k], *pts[k + 1], Pn((255, 255, 255), a, 'stroke', 4))
    img = sk_end(surf); return img * (1 + .25 * (1 - dt / .22))
import random
def ashfall(img, T, k=1.0, n=220, fall=110, drift=25, seed=5, size=1.0):
    lay = np.zeros_like(img); P = np.random.default_rng(seed).random((n, 4))
    for u_, v_, s_, p_ in P:
        x = (u_ * W + T * drift * (.5 + s_) + 20 * math.sin(T * 1.3 + p_ * 9)) % W; y = (v_ * H + T * fall * (.4 + s_)) % H
        v = 55 + 120 * p_; cv2.circle(lay, (int(x), int(y)), max(1, int((1 + 3 * s_ * s_) * size)), (v * .95, v, v * 1.02), -1, cv2.LINE_AA)
    return img + cv2.GaussianBlur(lay, (0, 0), 1.2) * .9 * k
def flow_front(img, T, u, x0, x1, yfar, ynear, speed=1.0, n=60, scale=1.0):
    """ground-hugging pyroclastic flow: puffs born far away racing toward the camera, growing, glowing at the base"""
    items = []
    for i in range(n):
        ph, jx, sz, kk, sd, side = PR[i + 120]
        t = (ph + T * .22 * speed) % 1.0; d = t ** 1.6
        x = x0 + (x1 - x0) * jx; x = W / 2 + (x - W / 2) * (1 + 1.6 * d)
        y = yfar + (ynear - yfar) * d - (40 + 260 * sz) * (1 + 2.5 * d) * .4
        r = (60 + 90 * sz) * (1 + 3.5 * d) * scale
        items.append((d, x, y, r, int(kk * 8)))
    for d, x, y, r, kk in sorted(items, key=lambda q: q[0]):
        puff(img, x, y, r, (110, 115, 122), (18, 20, 24), 1.0, kk, glow=.9 + .6 * (1 - d), gcol=(25, 100, 255))
    return img
def steam_blast(img, T, vx, vy, t0=0.0, scale=1.0, n=70):
    dt = T - t0
    if dt < 0: return img
    items = []
    for i in range(n):
        ph, jx, sz, kk, sd, side = PR[i + 200]
        t = clamp(dt * (.8 + .5 * sd) - ph * .25)
        if t <= 0: continue
        ang = (jx - .5) * 1.5; sp = (300 + 650 * sz) * scale
        x = vx + math.sin(ang) * sp * eout(t); y = vy - math.cos(ang) * sp * eout(t) * 1.4 + 120 * t * t
        r = (40 + 110 * t) * scale * (.6 + .8 * sz)
        items.append((t, x, y, r, int(kk * 8)))
    for t, x, y, r, kk in sorted(items, key=lambda q: -q[0]):
        puff(img, x, y, r, (250, 250, 248), (150, 150, 155), clamp(1.4 - t * .7), kk)
    lay = np.zeros_like(img)   # rock fragments thrown out ballistically
    for i in range(30):
        ph, jx, sz, kk, sd, side = PR[i + 300]; t = clamp(dt * 1.1 - ph * .2)
        if t <= 0: continue
        ang = (jx - .5) * 1.8; sp = (250 + 600 * sz) * scale
        x = vx + math.sin(ang) * sp * t * 1.3; y = vy - math.cos(ang) * sp * t * 2.0 + 900 * t * t * scale
        cv2.circle(lay, (int(x), int(y)), 3 + int(5 * sd), (30, 32, 36), -1, cv2.LINE_AA)
    al = (lay.sum(2, keepdims=True) > 0).astype(np.float32); return img * (1 - al) + lay
LAVA_TX = {}
def lava_tongue(img, T, u, x0, y0, x1, y1, adv):
    """slow lava flow: dark crust broken by glowing cracks, a lobed glowing front creeping toward the camera"""
    if 'c' not in LAVA_TX:
        f = fbm(512, 77, 6, 8); rid = 1 - np.abs(f - .5) * 2; LAVA_TX['c'] = cv2.resize(rid, (W, H)); LAVA_TX['n'] = cv2.resize(fbm(256, 78), (W, H))
    rid, nz = LAVA_TX['c'], LAVA_TX['n']
    yfront = y0 + (y1 - y0) * adv + 40 * np.sin(XX / 65 + 1.3) + 25 * np.sin(XX / 23)
    t = np.clip((YY - y0) / max(y1 - y0, 1), 0, 1); halfw = (x1 - x0) / 2 * (.55 + .7 * t)
    cx_ = (x0 + x1) / 2 + 40 * np.sin(YY / 120)
    m = ((np.abs(XX - cx_) < halfw * (.9 + .25 * nz)) & (YY < yfront) & (YY > y0 - 40)).astype(np.float32)
    m = cv2.GaussianBlur(m, (0, 0), 5)[..., None]
    crack = np.clip((rid - .8) * 6, 0, 1) * (.6 + .4 * math.sin(T * 2.5))
    edge = np.clip(1 - (yfront - YY) / 45, 0, 1) * (YY < yfront)
    hot = np.clip(crack + edge, 0, 1)[..., None]
    crust = np.array([30, 33, 40], np.float32) * (.6 + .9 * nz[..., None])
    col = crust * (1 - hot) + hot * np.array([30, 140, 255], np.float32) * 1.5
    out = img * (1 - m) + col * m
    return glow(out, (x0 + x1) / 2, float(np.mean(yfront)), 300, .35, (30, 110, 255))
# ================================================================== maps (us-atlas state outlines, real-data globe)
TOPO = json.load(open('/home/claude/geo/package/states-10m.json'))
def _arcs():
    sx, sy = TOPO['transform']['scale']; tx, ty = TOPO['transform']['translate']; out = []
    for arc in TOPO['arcs']:
        a = np.cumsum(np.array(arc, np.float64), 0); out.append(np.stack([a[:, 0] * sx + tx, a[:, 1] * sy + ty], 1))
    return out
ARCS = _arcs()
def _ring(idx):
    pts = []
    for i in idx:
        a = ARCS[i] if i >= 0 else ARCS[~i][::-1]
        pts.append(a if not pts else a[1:])
    return np.concatenate(pts)
STATES = {}
for g_ in TOPO['objects']['states']['geometries']:
    polys = g_['arcs'] if g_['type'] == 'MultiPolygon' else [g_['arcs']]
    STATES[g_['properties']['name']] = [[_ring(r) for r in poly] for poly in polys]
def proj_pts(lonlat, g):
    lon, lat = np.radians(lonlat[:, 0] - g['lon0']), np.radians(lonlat[:, 1]); a = math.radians(g['lat0'])
    xg, yg, zg = np.cos(lat) * np.sin(lon), np.sin(lat), np.cos(lat) * np.cos(lon)
    y = yg * math.cos(a) - zg * math.sin(a); z = yg * math.sin(a) + zg * math.cos(a)
    return np.stack([g['cx'] + xg * g['R'], g['cy'] - y * g['R']], 1), z > 0
def state_lines(img, g, a=1.0, col=(255, 255, 255), w=2.0, names=None, fill=None):
    surf, c = sk_begin(img)
    for nm, polys in STATES.items():
        if names and nm not in names: continue
        for poly in polys:
            for ring in poly:
                p, v = proj_pts(ring, g)
                if not v.all(): continue
                pth = skia.Path(); pth.moveTo(*p[0])
                for q in p[1:]: pth.lineTo(*q)
                pth.close()
                if fill is not None: c.drawPath(pth, Pn(fill[:3], fill[3] * a))
                c.drawPath(pth, Pn(col, 255 * a * .55, 'stroke', w))
    return sk_end(surf)
def state_mask(nm, g, offset=(0, 0)):
    m = np.zeros((H, W), np.uint8)
    for poly in STATES[nm]:
        p, v = proj_pts(poly[0], g); cv2.fillPoly(m, [np.round(p + np.array(offset)).astype(np.int32)], 255)
    return m.astype(np.float32) / 255
YS = (44.55, -110.55)   # Yellowstone Caldera, approximate center
CITIES = {'Billings': (45.78, -108.50), 'Chicago': (41.88, -87.63), 'New York': (40.71, -74.01), 'Miami': (25.76, -80.19),
          'Los Angeles': (34.05, -118.24), 'Casper': (42.87, -106.31)}
LL = {}
def latlon_grid(g):
    key_ = tuple(round(v, 3) for v in (g['cx'], g['cy'], g['R'], g['lon0'], g['lat0']))
    if key_ not in LL:
        xs = (XX - g['cx']) / g['R']; ys = -(YY - g['cy']) / g['R']; r2 = xs * xs + ys * ys; z = np.sqrt(np.clip(1 - r2, 0, 1))
        a = math.radians(g['lat0']); yg = ys * math.cos(a) + z * math.sin(a); zg = -ys * math.sin(a) + z * math.cos(a)
        lat = np.degrees(np.arcsin(np.clip(yg, -1, 1))); lon = g['lon0'] + np.degrees(np.arctan2(xs, zg))
        if len(LL) > 6: LL.clear()
        LL[key_] = (lat.astype(np.float32), lon.astype(np.float32), r2 < 1)
    return LL[key_]
def dist_km(lat, lon, p):
    la1, lo1 = np.radians(lat), np.radians(lon); la2, lo2 = math.radians(p[0]), math.radians(p[1])
    h = np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * math.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371 * np.arcsin(np.sqrt(np.clip(h, 0, 1)))
NZ = {}
def noise_screen(seed=3):
    if seed not in NZ: NZ[seed] = cv2.resize(fbm(256, seed, 5, 3), (W, H), interpolation=cv2.INTER_CUBIC)
    return NZ[seed]
def ash_footprint(img, g, reach_km, a=1.0, zones=True):
    """simplified isopach bull's-eye after the USGS ash model (Mastin et al. 2014): meters near the park, centimeters in the Midwest,
    millimeters on the coasts; the cloud spreads in every direction, even upwind"""
    lat, lon, ins = latlon_grid(g); d = dist_km(lat, lon, YS) * (1 + .12 * (noise_screen(3) - .5))
    m = np.clip((reach_km - d) / 120, 0, 1) * ins
    thick = np.clip(1 - d / 3600, 0, 1) ** 1.6                       # 1 near the park -> 0 at ~3,600 km
    col = np.array([40, 42, 46], np.float32) * thick[..., None] + np.array([150, 150, 150], np.float32) * (1 - thick[..., None])
    al = (m * (.25 + .7 * thick))[..., None] * a
    out = img * (1 - al) + col * al
    if zones:
        surf, c = sk_begin(out); yx, yy_, _ = gpt(*YS, g)
        for rk in (300, 900, 1800):
            if rk > reach_km: continue
            pts = [gpt(*geo_offset(YS, rk, b), g) for b in np.linspace(0, 360, 90)]
            pth = skia.Path(); pth.moveTo(pts[0][0], pts[0][1])
            for q in pts[1:]: pth.lineTo(q[0], q[1])
            pth.close(); c.drawPath(pth, Pn((255, 235, 200), 120 * a, 'stroke', 3))
        out = sk_end(surf)
    return out
def geo_offset(p, km, bearing):
    la, lo, d, b = math.radians(p[0]), math.radians(p[1]), km / 6371, math.radians(bearing)
    la2 = math.asin(math.sin(la) * math.cos(d) + math.cos(la) * math.sin(d) * math.cos(b))
    lo2 = lo + math.atan2(math.sin(b) * math.sin(d) * math.cos(la), math.cos(d) - math.sin(la) * math.sin(la2))
    return math.degrees(la2), math.degrees(lo2)
def city(img, nm, g, a=1.0, col=WHITE, size=40, dy=-26, dot=GOLD):
    x, y, v = gpt(*CITIES[nm], g)
    if not v: return img
    surf, c = sk_begin(img); c.drawCircle(x, y, 9, Pn(dot, 255 * a)); c.drawCircle(x, y, 9, Pn((0, 0, 0), 255 * a, 'stroke', 3))
    text(c, nm.upper(), x, y + dy, size, col, 255 * a); return sk_end(surf)
def usmap(T, u, R=1500, lon0=-100, lat0=40, cy=H * .47, cx=W / 2, k_bg=.5, dim=.75, drift=True):
    g = G(cx=cx, cy=cy, R=R * (1 + .03 * u if drift else 1), lon0=lon0 + (1.2 * u if drift else 0), lat0=lat0)
    img = stars(T, k_bg); img = globe(img, g['cx'], g['cy'], g['R'], g['lon0'], g['lat0'], sun=(-.25, .35, .9), clouds=False, night=0)
    img = img * dim; img = state_lines(img, g, .8, (230, 235, 240), 1.6); return img, g
def ys_marker(img, g, T, a=1.0, lab=None):
    x, y, v = gpt(*YS, g); return marker(img, x, y, T, a, (60, 150, 255), lab) if v else img

# ------------------------------------------------------------------ diagrams
def iso_cube(c, x, y, s, col, a):
    """isometric cube with its front-bottom corner at (x, y), edge s px"""
    dx, dy = s * .866, s * .5
    top = [(x, y - s), (x + dx, y - s - dy), (x, y - s - 2 * dy), (x - dx, y - s - dy)]
    left = [(x, y), (x, y - s), (x - dx, y - s - dy), (x - dx, y - dy)]
    right = [(x, y), (x, y - s), (x + dx, y - s - dy), (x + dx, y - dy)]
    for pts, k in ((left, .55), (right, .75), (top, 1.0)):
        pth = skia.Path(); pth.moveTo(*pts[0]); [pth.lineTo(*q) for q in pts[1:]]; pth.close()
        c.drawPath(pth, Pn(tuple(int(v * k) for v in col), a)); c.drawPath(pth, Pn((255, 255, 255), a * .35, 'stroke', 2))
def cubes(img, u, T):
    surf, c = sk_begin(blurdim(img, .7)); a = 255 * eout(u * 4)
    big = 360 * eout(clamp(u * 1.6 - .15)); sm = big / 2500 ** (1 / 3)
    by = H * .53
    iso_cube(c, W * .58, by, max(big, 2), (120, 110, 105), a)
    iso_cube(c, W * .15, by, max(sm, 2) if big > 2 else 35, (255, 160, 70), a)
    text(c, 'ST. HELENS', W * .15, by - 70, 40, GOLD, a); text(c, '1980', W * .15, by - 25 - 80, 40, GOLD, a) if False else text(c, '1980', W * .15, by - 115, 40, GOLD, a)
    if big > 50: text(c, 'YELLOWSTONE, 2.1 MILLION YEARS AGO', W * .5, by + 70, 40, WHITE, a * clamp(u * 3 - .6))
    return sk_end(surf)
def texas(T, u):
    img, g = usmap(T, u, R=1700, lon0=-100, lat0=36, cy=H * .44)
    m = state_mask('Texas', g); f = clamp(u * 1.5)
    sweep = np.clip((f * (H * .75) - (YY - H * .28)) / 60, 0, 1)   # ash fills Texas from the top down
    tex_ = (90 + 70 * noise_screen(5))[..., None] * np.array([1, 1, 1.03], np.float32)
    al = (m * sweep)[..., None] * .92; img = img * (1 - al) + tex_ * al
    surf, c = sk_begin(img); x, y, _ = gpt(31.5, -99.3, g); text(c, 'TEXAS', x, y, 64, WHITE, 255 * clamp(u * 3)); img = sk_end(surf)
    return img
def ash_side(img, u, T, depth_in=40, title=None):
    """side view: ash piling up next to a kitchen counter (36 in) and a person (5 ft 9 in); 1 in = 11 px"""
    px = 8.0; floor = H * .58; surf, c = sk_begin(blurdim(img, .75)); a = 255 * eout(u * 4)
    c.drawRect(skia.Rect.MakeXYWH(90, floor - 36 * px, 300, 36 * px), Pn((70, 95, 120), a)); c.drawRect(skia.Rect.MakeXYWH(70, floor - 36 * px - 22, 340, 22), Pn((180, 190, 200), a))
    text(c, 'KITCHEN COUNTER', 245, floor - 36 * px - 50, 36, WHITE, a); text(c, '36 IN', 245, floor - 18 * px, 44, WHITE, a)
    hx = W * .74; hh = 69 * px   # simple person silhouette
    c.drawCircle(hx, floor - hh + 40, 40, Pn((235, 235, 240), a)); c.drawRoundRect(skia.Rect.MakeXYWH(hx - 55, floor - hh + 88, 110, hh * .45), 32, 32, Pn((235, 235, 240), a))
    c.drawRoundRect(skia.Rect.MakeXYWH(hx - 48, floor - hh * .5, 40, hh * .5), 16, 16, Pn((235, 235, 240), a)); c.drawRoundRect(skia.Rect.MakeXYWH(hx + 8, floor - hh * .5, 40, hh * .5), 16, 16, Pn((235, 235, 240), a))
    img = sk_end(surf); lvl = depth_in * px * eout(clamp(u * 1.4 - .1))
    m = ((YY > floor - lvl) & (YY < floor + 4)).astype(np.float32)[..., None] * np.ones((1, W, 1), np.float32)
    img = img * (1 - m * .93) + (95 + 60 * noise_screen(7))[..., None] * m * .93
    surf, c = sk_begin(img); c.drawLine(40, floor, W - 40, floor, Pn((255, 255, 255), a, 'stroke', 4))
    if lvl > 20: c.drawLine(40, floor - lvl, W - 40, floor - lvl, Pn(GOLD, a, 'stroke', 4)); text(c, 'ASH: OVER 3 FT', W / 2, floor - lvl - 22, 50, GOLD, a)
    return sk_end(surf)
def melt_gauge(img, u, T):
    surf, c = sk_begin(blurdim(img, .7)); a = 255 * eout(u * 4); x0, x1, y = 110, W - 110, H * .5
    text(c, 'HOW MUCH OF THE MAGMA IS MELTED', W / 2, y - 120, 42, GREY, a)
    c.drawRoundRect(skia.Rect.MakeLTRB(x0, y - 40, x1, y + 40), 40, 40, Pn((40, 48, 60), a))
    lo, hi = x0 + (x1 - x0) * .35, x0 + (x1 - x0) * .50
    c.drawRect(skia.Rect.MakeLTRB(lo, y - 40, hi, y + 40), Pn((255, 90, 70), a * .55))
    f = (x1 - x0) * .2 * eout(clamp(u * 2.2))
    c.drawRoundRect(skia.Rect.MakeLTRB(x0, y - 40, x0 + max(f, 40), y + 40), 40, 40, Pn((60, 150, 255), a))
    text(c, '16-20%', x0 + 110, y + 105, 52, (60, 150, 255), a * clamp(u * 3 - .5)); text(c, 'TODAY', x0 + 110, y + 155, 36, WHITE, a * clamp(u * 3 - .5))
    ua = a * clamp(u * 2.5 - 1.2); text(c, '35-50%', (lo + hi) / 2, y - 60, 52, (255, 90, 70), ua); text(c, 'LIKELY NEEDED TO ERUPT', (lo + hi) / 2 + 40, y + 105, 34, WHITE, ua)
    return sk_end(surf)
def reservoir(img, u, T):
    """cross-section: surface, crust, the partly molten magma reservoir ~5 km (3 mi) down: mostly solid crystals, a little melt"""
    surf, c = sk_begin(img * .25); a = 255 * eout(u * 4); gy = H * .3
    c.drawRect(skia.Rect.MakeLTRB(0, gy, W, H), Pn((28, 32, 38), a))
    for k in range(40): c.drawLine(k * 30, gy, k * 30 + 12, gy - 40 - 30 * (k % 3), Pn((20, 60, 30), a, 'stroke', 10))
    img = sk_end(surf)
    cy = H * .3 + 5 * 120 + 120   # 1 km = 120 px
    m = ((((XX - W / 2) / 420) ** 2 + ((YY - cy) / 170) ** 2) < 1 + .25 * (noise_screen(9) - .5)).astype(np.float32)
    if 'cry' not in NZ:
        v = cv2.resize(fbm(512, 21, 3, 48), (W, H), interpolation=cv2.INTER_LINEAR); NZ['cry'] = (v > np.percentile(v, 20)).astype(np.float32)
    crystal = NZ['cry']
    col = (crystal[..., None] * np.array([70, 80, 95], np.float32) + (1 - crystal[..., None]) * np.array([30, 110, 255], np.float32) * (.8 + .2 * math.sin(T * 3)))
    m = cv2.GaussianBlur(m, (0, 0), 3)[..., None] * eout(u * 3); img = img * (1 - m) + col * m
    surf, c = sk_begin(img); c.drawLine(W * .12, gy, W * .12, cy - 170, Pn(GOLD, a, 'stroke', 5)); text(c, '~5 KM', W * .12 + 15, (gy + cy) / 2, 46, GOLD, a, 'l')
    text(c, '(3 MILES)', W * .12 + 15, (gy + cy) / 2 + 50, 36, GOLD, a, 'l'); text(c, 'MAGMA RESERVOIR', W / 2, cy + 230, 46, WHITE, a)
    return sk_end(surf)
def odds(img, u, T):
    surf, c = sk_begin(blurdim(img, .65)); a = 255 * eout(u * 4)
    text(c, 'ODDS PER YEAR', W / 2, H * .3, 46, GREY, a); n = int(730000 * eout(clamp(u * 2.5)) / 1000) * 1000
    text(c, f'1 IN {n:,}', W / 2, H * .4, 104, GOLD, a)
    return sk_end(surf)
def asteroid(img, x, y, r, T, a=1.0, trail=1.0):
    surf, c = sk_begin(img)
    for k in range(18):
        t = k / 18; c.drawCircle(x - 260 * t * trail, y - 160 * t * trail, r * (1 - .7 * t), Pn((255, 170 - 80 * t, 80), 120 * (1 - t) * a, blur=18))
    pth = skia.Path(); rr = random.Random(5)
    for k in range(14):
        ang = k / 14 * 2 * math.pi; q = r * rr.uniform(.75, 1.1); (pth.moveTo if k == 0 else pth.lineTo)(x + q * math.cos(ang), y + q * math.sin(ang))
    pth.close(); c.drawPath(pth, Pn((95, 88, 82), 255 * a)); c.drawCircle(x - r * .3, y - r * .2, r * .25, Pn((70, 64, 60), 255 * a))
    return sk_end(surf)
def haze_globe(img, g, f, T):
    """sulfate aerosol veil spreading around the globe (dims the sunlight)"""
    lat, lon, ins = latlon_grid(g); d = dist_km(lat, lon, YS)
    m = np.clip((f * 22000 - d) / 2500, 0, 1) * ins * (.6 + .4 * noise_screen(13))
    col = np.array([150, 195, 215], np.float32) * (.45 + .55 * np.clip(img.mean(2, keepdims=True) / 120, 0, 1)); al = (m * .8)[..., None]
    return img * (1 - al * .8) + col * al * .8

def steam_plume(img, T, vx, vy, scale=1.0, n=40, a=1.0):
    items = []
    for i in range(n):
        ph, jx, sz, kk, sd, side = PR[i + 60]; t = (ph + T * .12) % 1.0
        x = vx + (jx - .5) * 80 * scale * (1 + 2 * t) + 60 * t * scale * math.sin(T * .5 + i); y = vy - t * 700 * scale
        items.append((t, x, y, (30 + 120 * t) * scale * (.6 + .8 * sz), int(kk * 8)))
    for t, x, y, r, kk in sorted(items, key=lambda q: -q[0]):
        puff(img, x, y, r, (245, 245, 243), (170, 172, 178), a * (1 - t) ** .7 * .8, kk)
    return img
def wind_arrows(img, g, u, T, a=1.0):
    surf, c = sk_begin(img); al = 255 * a * clamp(u * 4)
    for la in (49, 41, 33):
        ph = (T * .25) % 1.0
        for lo in (-122, -104, -86):
            x0, y0, _ = gpt(la, lo + 8 * ph, g); x1, y1, _ = gpt(la, lo + 8 * ph + 9, g); arrow(c, x0, y0, x1, y1, (235, 240, 255), al * .8, 7, 22)
    return sk_end(surf)

def shots():
    V = fx('erupt', 'vent', (.5, .78)); FR = fx('flow', 'front', (.5, .7)); GV = fx('geyser', 'vent', (.5, .55))
    RF = fx('roof', 'roof', (.5, .4)); FN = fx('engine', 'fan', (.5, .5)); CAR = fx('town', 'car', (.6, .6))
    def erupt(T, u, z0, z1, c0=(.5, .5), c1=(.5, .5), grow=1.0, shake=.0, lt=(), wide=1.9, emb=1.0):
        img = kb('erupt', u, z0, z1, c0, c1, shake=shake, T=T) * .9; vx, vy, z = kb_pt(V[0], V[1], u, z0, z1, c0, c1)
        img = vent_glow(img, vx, vy, T, .55, z * min(wide, 1.6))
        img = ash_column(img, T, vx, vy, scale=z * .9, top=H * .03, grow=grow, wide=wide, n=160)
        img = embers(img, T, vx, vy, 70, emb, 1.0)
        for k, t0 in enumerate(lt): img = lightning(img, T, vx + (-120 + 90 * k) * z, vy - 900 * z, vy - 380 * z, t0, k + 1)
        return vignette(img, .5)
    def geyser(T, u, z0, z1, c0=(.5, .55), c1=(.5, .55), a=1.0):
        img = kb('geyser', u, z0, z1, c0, c1); vx, vy, z = kb_pt(GV[0], GV[1], u, z0, z1, c0, c1)
        img = grade_gold(img, .5); return steam_plume(img, T, vx, vy, z * .8, a=a)
    def flow(T, u, z0, z1, c0=(.5, .55), c1=(.5, .55), speed=1.0):
        img = kb('flow', u, z0, z1, c0, c1, shake=.4, T=T) * .9
        img = ash_column(img, T, W * .5, H * .62, scale=.55, top=H * .05, umbrella=.6)
        img = flow_front(img, T, u, W * .05, W * .95, H * .62, H * 1.05, speed)
        return embers(vignette(img, .45), T, W * .5, H * .7, 40, .6, 1.8)
    def town(T, u, z0, z1, c0=(.5, .5), c1=(.5, .5), k=1.0):
        img = kb('town', u, z0, z1, c0, c1); img = haze(img, .3, (70, 80, 92)); img = ashfall(img, T, k, 260, 140, 30)
        return vignette(ashfall(img, T + 3, k * .7, 80, 220, 40, 9, 2.0), .5)
    def roof(T, u, z0, z1, c0=(.5, .45), c1=(.5, .45), shake=.0):
        img = kb('roof', u, z0, z1, c0, c1, shake=shake, T=T); img = haze(img, .25, (70, 80, 92))
        return vignette(ashfall(img, T, 1.0, 260, 150, 25), .5)
    def engine(T, u, z0, z1, c0=(.5, .5), c1=(.5, .5), hot=0.0):
        img = kb('engine', u, z0, z1, c0, c1, shake=.25, T=T); x, y, z = kb_pt(FN[0], FN[1], u, z0, z1, c0, c1)
        if hot: img = glow(img, x + 10 * z, y + 10 * z, 70 * z, hot * (1 + .3 * math.sin(T * 17)), (40, 150, 255))
        img = wind(img, T, 1.0, 70, 5, (150, 150, 150), 2.6) if False else img
        lay = np.zeros_like(img); P = np.random.default_rng(3).random((140, 3))   # ash streaking into the intake
        for a_, r_, s_ in P:
            t = (s_ + T * 1.6) % 1.0; ang = a_ * 2 * math.pi; rr = (1 - t) * 900 + 60
            p0 = (x + math.cos(ang) * rr, y + math.sin(ang) * rr); p1 = (x + math.cos(ang) * (rr + 90), y + math.sin(ang) * (rr + 90))
            cv2.line(lay, (int(p0[0]), int(p0[1])), (int(p1[0]), int(p1[1])), (150, 150, 155), 2, cv2.LINE_AA)
        return vignette(img + cv2.GaussianBlur(lay, (0, 0), 1.5) * .9, .5)
    def macro(T, u, z0, z1, c0=(.5, .5), c1=(.5, .5)):
        img = kb('macro', u, z0, z1, c0, c1, rot=3 * u); return dust(vignette(img, .5), T, (200, 200, 205), .6, (6, 18))
    def us_ash(T, u, r0, r1, cities=(), lab=None, wind_=False, upwind=0.0):
        img, g = usmap(T, u); img = ash_footprint(img, g, r0 + (r1 - r0) * eout(u))
        img = ys_marker(img, g, T, 1.0)
        if wind_: img = wind_arrows(img, g, u, T)
        if upwind:
            surf, c = sk_begin(img); x0, y0, _ = gpt(*YS, g); x1, y1, _ = gpt(YS[0] - 2, YS[1] - 13 * eout(clamp(u * 2)), g)
            arrow(c, x0, y0, x1, y1, GOLD, 255 * upwind, 10, 30); img = sk_end(surf)
        for nm in cities: img = city(img, nm, g)
        return img
    def globe_haze(T, u, f0, f1, R=430, dimsun=0.0):
        g = G(cx=W * .5, cy=H * .47, R=R, lon0=-100 - 3 * T, lat0=30); img = stars(T, .5)
        img = glow(img, W * .05, H * .2, 220, 1.3 * (1 - .6 * dimsun), (170, 230, 255))
        img = globe(img, g['cx'], g['cy'], g['R'], g['lon0'], g['lat0'], sun=(-.6, .35, .7), cloud_lon=-2 * T)
        return haze_globe(img, g, f0 + (f1 - f0) * u, T) * (1 - .25 * dimsun)
    def caldera_map(T, u):
        g = G(cx=W * .31, cy=H * .42, R=40000 * (1 + .04 * u), lon0=YS[1], lat0=YS[0])
        img = (np.array([38, 30, 22], np.float32) + 30 * noise_screen(15)[..., None] * np.array([1, 1.1, 1.2], np.float32))
        surf, c = sk_begin(img)
        for k in range(0, W + 1, 90): c.drawLine(k, 0, k, H, Pn((255, 255, 255), 18, 'stroke', 2))
        for k in range(0, H + 1, 90): c.drawLine(0, k, W, k, Pn((255, 255, 255), 18, 'stroke', 2))
        img = sk_end(surf)
        img = state_lines(img, g, 1.0, (255, 255, 255), 4, names={'Montana', 'Idaho', 'Wyoming'})
        surf, c = sk_begin(img)
        for nm, (la, lo) in (('MONTANA', (45.05, -110.6)), ('WYOMING', (43.9, -109.9)), ('IDAHO', (44.3, -111.6))):
            x, y, _ = gpt(la, lo, g); text(c, nm, x, y, 34, GREY, 200)
        img = sk_end(surf)
        kmpx = g['R'] / 6371; surf, c = sk_begin(img); a = 255 * eout(u * 3)
        rect = skia.Rect.MakeXYWH(-40 * kmpx, -27.5 * kmpx, 80 * kmpx, 55 * kmpx)
        c.save(); c.translate(g['cx'], g['cy']); c.rotate(-25); c.drawOval(rect, Pn((40, 120, 255), a * .35)); c.drawOval(rect, Pn((60, 160, 255), a, 'stroke', 6)); c.restore()
        text(c, 'CALDERA', g['cx'], g['cy'] - 230, 44, (255, 180, 90), a); text(c, '~35 x 50 MI (USGS)', g['cx'], g['cy'] + 270, 40, WHITE, a)
        ri = STATES['Rhode Island']; big = max(ri, key=lambda p: len(p[0]))[0]; ctr = big.mean(0); f = clamp(u * 2.2 - .5)
        for poly in ri:
            ring = poly[0]; dx = (ring[:, 0] - ctr[0]) * 111.32 * math.cos(math.radians(ctr[1])) * kmpx; dy = -(ring[:, 1] - ctr[1]) * 110.57 * kmpx
            pth = skia.Path(); ox, oy = W * .76, H * .42
            pth.moveTo(ox + dx[0], oy + dy[0]); [pth.lineTo(ox + p, oy + q) for p, q in zip(dx[1:], dy[1:])]; pth.close()
            c.drawPath(pth, Pn((255, 205, 70), 120 * f)); c.drawPath(pth, Pn((255, 205, 70), 255 * f, 'stroke', 4))
        text(c, 'RHODE ISLAND', W * .76, H * .42 - 290, 40, GOLD, 255 * f); text(c, 'SAME SCALE', W * .76, H * .42 + 300, 34, GREY, 255 * f)
        return sk_end(surf)
    def texas_close(T, u):
        img, g = usmap(T, u, R=3200, lon0=-99, lat0=31.3, cy=H * .45, drift=False)
        m = state_mask('Texas', g)[..., None]; tex_ = (90 + 70 * noise_screen(5))[..., None]; return img * (1 - m * .92) + tex_ * m * .92
    S = {
     0: [(0, lambda T, u: erupt(T, u, 1.0, 1.1, (.5, .45), (.5, .42), lt=(.55,), shake=.6)),
         (1.25, lambda T, u: erupt(T + 1.3, u, 1.6, 1.75, (V[0], .62), (V[0], .6), shake=.9, lt=(.3,)))],
     1: [(0, lambda T, u: ys_marker(*usmap(T, u), T, 1.0, 'YELLOWSTONE')),
         (1.8, lambda T, u: geyser(T, u, 1.0, 1.12))],
     2: [(0, lambda T, u: erupt(T, u, 1.15, 1.0, (.5, .5), (.5, .45), grow=.15 + .85 * eout(u), shake=.7, lt=(1.2,))),
         (2.2, lambda T, u: cubes(erupt(T + 2, 1, 1.0, 1.0), u, T))],
     3: [(0, lambda T, u: texas(T, u)), (2.6, lambda T, u: texas_close(T, u))],
     4: [(0, lambda T, u: erupt(T, u, 1.25, 1.35, (V[0], .66), (V[0], .64), grow=.25 + .4 * u, shake=1.2, wide=2.4, emb=1.5)),
         (2.1, lambda T, u: caldera_map(T, u))],
     5: [(0, lambda T, u: flow(T, u, 1.0, 1.12)),
         (2.7, lambda T, u: bars(blurdim(flow(T + 2.7, 1, 1.12, 1.15), .6), u,
                                 [('GLOWING AVALANCHES', 850, (255, 140, 40), '700-850 °C'), ('ALUMINUM MELTS', 660, GREY, '660 °C')], 'TEMPERATURE', 1000, H * .3))],
     6: [(0, lambda T, u: us_ash(T, u, 0, 1300, wind_=True, upwind=1.0)), (2.0, lambda T, u: us_ash(T + 2, u, 1300, 2600, wind_=True, upwind=1.0))],
     7: [(0, lambda T, u: town(T, u, 1.0, 1.12, (.5, .5), (CAR[0], .52))), (2.4, lambda T, u: ash_side(town(T + 2.4, 1, 1.12, 1.12, (.5, .5), (CAR[0], .52)), u, T))],
     8: [(0, lambda T, u: us_ash(T, u, 2600, 3000, cities=('Billings', 'Chicago'))),
         (2.0, lambda T, u: us_ash(T + 2, u, 3000, 3700, cities=('Billings', 'Chicago', 'New York', 'Miami')))],
     9: [(0, lambda T, u: macro(T, u, 1.0, 1.15)), (2.0, lambda T, u: macro(T + 2, u, 1.5, 1.7, (.45, .55), (.5, .5)))],
     10: [(0, lambda T, u: roof(T, u, 1.0, 1.1, shake=.3)), (1.6, lambda T, u: roof(T + 1.6, u, 1.45, 1.6, (RF[0], RF[1]), (RF[0], RF[1] + .02), shake=1.0))],
     11: [(0, lambda T, u: engine(T, u, 1.0, 1.08)), (1.8, lambda T, u: engine(T + 1.8, u, 1.5, 1.65, FN, FN, hot=1.2))],
     12: [(0, lambda T, u: globe_haze(T, u, .0, .55)), (2.0, lambda T, u: globe_haze(T + 2, u, .55, 1.0, 470, dimsun=u))],
     13: [(0, lambda T, u: bars(blurdim(globe_haze(T, 1, 1, 1, 470, 1), .55), u,
                                [('PINATUBO 1991', .7, (110, 215, 255), '~0.7 °C'), ('YELLOWSTONE*', 1.5, (255, 140, 40), 'UP TO ~1.5 °C')], 'GLOBAL COOLING', 2.0, H * .28)),
          (3.0, lambda T, u: globe_haze(T + 3, u, 1, 1, 520, 1))],
     14: [(0, lambda T, u: geyser(T, u, 1.0, 1.08)), (1.9, lambda T, u: geyser(T + 1.9, u, 1.35, 1.45, (GV[0], .5), (GV[0], .48)))],
     15: [(0, lambda T, u: odds(geyser(T, u, 1.1, 1.15), u, T)),
          (2.6, lambda T, u: asteroid(globe_haze(T, u, 0, 0, 380), W * (.25 + .25 * u), H * (.15 + .12 * u), 40, T)),
          (4.6, lambda T, u: asteroid(globe_haze(T, u, 0, 0, 470), W * (.55 + .05 * u), H * (.27 + .03 * u), 46, T))],
     16: [(0, lambda T, u: reservoir(geyser(T, u, 1.0, 1.0), u, T)), (3.0, lambda T, u: melt_gauge(reservoir(geyser(T, 1, 1.0, 1.0), 1, T), u, T))],
     17: [(0, lambda T, u: (lambda im: steam_blast(im, T, W * GV[0], H * GV[1], .2, 1.1))(geyser(T, u, 1.05, 1.15, a=.6))),
          (2.4, lambda T, u: lava_tongue(kb('flow', u, 1.1, 1.18) * .8, T, u, W * .25, H * .6, W * .75, H * 1.0, .3 + .45 * u))],
     18: [(0, lambda T, u: erupt(T, u, 1.0, 1.1, (.5, .47), (.5, .45), shake=.6, lt=(1.4,)))],
    }
    return S[idx]

YEL, WH, GR = [255, 222, 40], [255, 255, 255], [200, 200, 200]
ILL = {'type': 'label', 'text': 'ILLUSTRATION', 'color': GR, 'pos': [.8, .955], 'from': .1}
USGS = {'type': 'label', 'text': 'SIMPLIFIED FROM USGS ASH MODEL', 'color': GR, 'pos': [.5, .955], 'from': .1}
OV = {
 0: [{'type': 'hook', 'text': 'IF YELLOWSTONE BLEW|ASH ACROSS AMERICA'}, dict(ILL, instant=True)],
 1: [{'type': 'datestamp', 'text': 'YELLOWSTONE · WYOMING, USA', 'from': .2}],
 2: [{'type': 'badge', 'value': '~2,500x', 'unit': 'Mount St. Helens', 'pos': [.5, .15], 'from': 2.6},
     {'type': 'label', 'text': '2,450 CUBIC KM OF ROCK + ASH', 'color': WH, 'pos': [.5, .23], 'from': 3.2}, ILL],
 3: [{'type': 'label', 'text': 'ENOUGH TO BURY TEXAS', 'color': YEL, 'pos': [.5, .12], 'from': .3},
     {'type': 'badge', 'value': '11', 'unit': 'feet deep', 'pos': [.5, .2], 'from': 1.4}],
 4: [{'type': 'label', 'text': 'THE GROUND TEARS OPEN', 'color': YEL, 'pos': [.5, .12], 'from': .2}, dict(ILL, to=2.0),
     {'type': 'label', 'text': 'CALDERA OUTLINE APPROXIMATE', 'color': GR, 'pos': [.5, .955], 'from': 2.2}],
 5: [{'type': 'label', 'text': 'GLOWING AVALANCHES', 'color': YEL, 'pos': [.5, .12], 'from': .3},
     {'type': 'label', 'text': 'OF ROCK AND GAS', 'color': WH, 'pos': [.5, .18], 'from': .8}, ILL],
 6: [{'type': 'label', 'text': 'ASH SPREADS EVERY WAY', 'color': YEL, 'pos': [.5, .1], 'from': .3},
     {'type': 'label', 'text': 'EVEN AGAINST THE WIND', 'color': WH, 'pos': [.5, .16], 'from': 1.6}, USGS],
 7: [{'type': 'datestamp', 'text': 'BILLINGS, MONTANA', 'from': .2},
     {'type': 'badge', 'value': '3+', 'unit': 'feet of ash', 'pos': [.5, .2], 'from': .9}, ILL],
 8: [{'type': 'label', 'text': 'MIDWEST: A FEW INCHES', 'color': YEL, 'pos': [.5, .1], 'from': .3},
     {'type': 'label', 'text': 'COASTS: MILLIMETERS', 'color': WH, 'pos': [.5, .16], 'from': 2.1}, USGS],
 9: [{'type': 'label', 'text': 'VOLCANIC ASH =', 'color': WH, 'pos': [.5, .12], 'from': .3},
     {'type': 'label', 'text': 'JAGGED ROCK + GLASS', 'color': YEL, 'pos': [.5, .18], 'from': 1.2}, ILL],
 10: [{'type': 'badge', 'value': '~4', 'unit': 'inches', 'pos': [.5, .14], 'from': .4},
      {'type': 'label', 'text': 'CAN COLLAPSE WEAK ROOFS', 'color': WH, 'pos': [.5, .22], 'from': .8}, ILL],
 11: [{'type': 'label', 'text': 'ASH MELTS INSIDE', 'color': YEL, 'pos': [.5, .12], 'from': .3},
      {'type': 'label', 'text': 'JET ENGINES', 'color': WH, 'pos': [.5, .18], 'from': .7}, ILL],
 12: [{'type': 'label', 'text': 'SULFUR HAZE', 'color': YEL, 'pos': [.5, .1], 'from': .3},
      {'type': 'label', 'text': 'DIMS THE SUN FOR YEARS', 'color': WH, 'pos': [.5, .16], 'from': 1.4}, ILL],
 13: [{'type': 'label', 'text': '*NASA-LED STUDY, 2024', 'color': GR, 'pos': [.5, .955], 'from': .3}],
 14: [{'type': 'label', 'text': 'GOOD NEWS:', 'color': WH, 'pos': [.5, .12], 'from': .2},
      {'type': 'label', 'text': 'NOT OVERDUE (USGS)', 'color': YEL, 'pos': [.5, .18], 'from': 1.2}],
 15: [{'type': 'label', 'text': '≈ A BIG ASTEROID HITTING EARTH', 'color': YEL, 'pos': [.5, .12], 'from': 2.8}],
 16: [{'type': 'label', 'text': 'NOT TO SCALE', 'color': GR, 'pos': [.8, .955], 'from': .1}],
 17: [{'type': 'label', 'text': 'MORE LIKELY: STEAM BLAST', 'color': WH, 'pos': [.5, .12], 'from': .3},
      {'type': 'label', 'text': 'OR A SLOW LAVA FLOW', 'color': YEL, 'pos': [.5, .18], 'from': 2.5}, ILL],
 18: [{'type': 'cta'}, ILL],
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
