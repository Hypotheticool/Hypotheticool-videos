"""Animate every scene of "The avalanche buried Kai" over its Cycles plates (2D camera moves, cuts, snow billows, cracks, diagrams).
python3 aval_anim.py <scene> [still_times...]  ->  aval/s<scene>/f_####.png + meta.json (overlays read by compose.py)"""
import sys, math, json, os
sys.path.insert(0, '/home/claude/pro')
import numpy as np, cv2, skia
import engine as E
ROOT = '/home/claude/b3d/aval'; CFG = json.load(open(f'{ROOT}/topic.json'))
FPS = 24; PAD = .75; XF = .35
idx = int(sys.argv[1]); D = CFG['durs'][idx]; NF = int(math.ceil((D + PAD) * FPS))
W, H = 1080, 1920
ease = lambda t: .5 - .5 * math.cos(math.pi * min(max(t, 0), 1))
eout = lambda t: 1 - (1 - min(max(t, 0), 1)) ** 3
clamp = lambda v, a=0., b=1.: max(a, min(b, v))
YEL, WHITE, BLUE, RED = (255, 222, 40), (255, 255, 255), (130, 200, 255), (255, 110, 90)

def wt(word, line=None, end=False):
    """local scene time (s) when `word` is spoken in this scene's line"""
    ln = E.shown(CFG['lines'][idx if line is None else line]); words = ln.split()
    clip = D - E.lead(idx) - E.GAP; tt = E.word_times(ln, clip)
    for k, w in enumerate(words):
        if word.lower() in w.lower(): return XF + E.lead(idx) + tt[k][1 if end else 0]
    raise KeyError(word)

YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)
VIGM = (1 - .55 * np.clip(((XX / W - .5) ** 2 * 1.6 + (YY / H - .5) ** 2) ** .5 - .25, 0, 1) * 1.6)[..., None]
PL = {}
def plate(name):
    """load a plate, upscale, and grade it into the video's palette: deep teal shadows, warm highlights, a touch darker"""
    if name not in PL:
        im = cv2.imread(f'{ROOT}/plates/{name}.png', cv2.IMREAD_COLOR)
        if im.shape[1] != W: im = cv2.resize(im, (W, H), interpolation=cv2.INTER_CUBIC)
        im = im.astype(np.float32); lum = im.mean(2, keepdims=True) / 255
        im = im * .86 + (1 - lum) * np.float32([26, 14, 0]) * .9 - 4     # BGR: teal into the shadows
        im = im * (.92 + .08 * lum) * VIGM
        im = (im - 128) * 1.12 + 128 - 34   # snow is very bright: pull it down so bloom doesn't wash the frame
        PL[name] = np.clip(im, 0, 255)
    return PL[name]

def kb(name, u, z0, z1, c0=(.5, .5), c1=(.5, .5), rot=0.0, im=None):
    im = plate(name) if im is None else im; t = ease(u); z = z0 + (z1 - z0) * t
    cx = (c0[0] + (c1[0] - c0[0]) * t) * W; cy = (c0[1] + (c1[1] - c0[1]) * t) * H
    M = cv2.getRotationMatrix2D((cx, cy), rot, z); M[0, 2] += W / 2 - cx; M[1, 2] += H / 2 - cy
    return cv2.warpAffine(im, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

def shift(img, dx, dy): return cv2.warpAffine(img, np.float32([[1, 0, dx], [0, 1, dy]]), (W, H), borderMode=cv2.BORDER_REFLECT)
def shake(img, t, amp=10, decay=3.0):
    a = amp * math.exp(-t * decay)
    if a < .5: return img
    return shift(img, a * math.sin(t * 71), a * math.cos(t * 53))
def shiver(img, T, amp=3): return shift(img, amp * math.sin(T * 90), amp * .6 * math.cos(T * 77))
def talk(t, amp=.006): return 1 + amp * (math.sin(t * 17) * .6 + math.sin(t * 11) * .4)

def ptalk(name, t, u, z0, z1, c0=(.5, .5), c1=(.5, .5), amp=.007, snowk=.8):
    img = kb(name, u, z0, z1, c0, c1)
    img = cv2.warpAffine(img, cv2.getRotationMatrix2D((W / 2, H / 2), 0, talk(t, amp)), (W, H), borderMode=cv2.BORDER_REFLECT)
    return snow(img, t, snowk)

rng = np.random.default_rng(5); FL = rng.random((220, 4))
def snow(img, T, k=1.0, vy=60):
    """falling snowflakes, two depths (big blurred near ones, small far ones)"""
    if k <= 0: return img
    lay = np.zeros_like(img)
    for x, y, s, b in FL:
        px = int((x * W + math.sin(T * .8 + y * 11) * 30 + T * 12) % W)
        py = int((y * H + T * vy * (.4 + s)) % H)
        r = 1 + int(s * s * 6); v = (.35 + .65 * b) * k
        cv2.circle(lay, (px, py), r, (235 * v, 240 * v, 245 * v), -1, cv2.LINE_AA)
    return img + cv2.GaussianBlur(lay, (0, 0), 1.6)

def whip(img, t, dur=.12, vertical=False):
    if t >= dur: return img
    k = int(70 * (1 - t / dur)) | 1
    if k < 3: return img
    ker = np.zeros((k, 1) if vertical else (1, k), np.float32); ker[...] = 1 / k
    return cv2.filter2D(img, -1, ker)

def flash(img, t, k=220, decay=7): return img + k * math.exp(-max(t, 0) * decay)
def blur(img, s): return cv2.GaussianBlur(img, (0, 0), s) if s > .3 else img
def grade(img, mul=(1, 1, 1), add=0.0): return img * np.float32(mul)[None, None, :] + add

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

# ---------------------------------------------------------------- effects
def breath(img, T, x, y, k=1.0, fast=False):
    """frosty breath puffs from a mouth at (x, y) (fractions): soft white clouds that drift up and fade; fast = gasping"""
    per = .45 if fast else 1.3
    def f(c):
        for j in range(3):
            age = ((T / per + j / 3) % 1.0)
            r = 30 + 160 * age; a = (1 - age) ** 1.5 * .55 * k
            c.drawCircle(W * x + 60 * age + 20 * math.sin(T * 3 + j), H * y - 120 * age, r, E.P(E.C(230, 238, 245, 255 * a), blur=r * .45))
    return sk(img, f)


# ---------------------------------------------------------------- avalanche effects
BL = np.random.default_rng(17).random((90, 5))
def billow(img, T, front, k=1.0, top=-.2, warm=1.0):
    """the powder cloud of a moving avalanche: big soft churning white-blue puffs filling everything above `front` (fraction of H),
    rolling toward the camera; front moves down the frame as it arrives"""
    def f(c):
        for x, y, s, ph, sp in BL:
            yy = top + (front - top) * y; r = (90 + 260 * s) * (.6 + .5 * y)
            px = W * (x * 1.3 - .15) + 60 * math.sin(T * (1.5 + sp) + ph * 9); py = H * yy + 40 * math.sin(T * (2 + sp) + ph * 5)
            shade = .78 + .22 * math.sin(ph * 7)
            col = (int(195 * shade * warm + 30 * (1 - warm)), int(200 * shade), int(212 * shade + 10))
            c.drawCircle(px, py, r, E.P(E.C(*col, 215 * k), blur=r * .35))
        # leading edge spray
        for x, y, s, ph, sp in BL[:40]:
            px = W * x + 40 * math.sin(T * 4 + ph * 11); py = H * front + 60 * math.sin(T * 3 + ph * 4) - 40 * s
            c.drawCircle(px, py, 30 + 80 * s, E.P(E.C(240, 245, 250, 200 * k), blur=30))
    return sk(img, f)

SPR = np.random.default_rng(23).random((80, 4))
def spray(img, T, k=1.0, dirx=1.0):
    """flying snow chunks and powder streaks (motion-blurred) across the frame"""
    def f(c):
        for x, y, s, ph in SPR:
            px = (W * x + T * 1400 * (.6 + s) * dirx) % (W + 200) - 100; py = (H * y + T * 900 * (.4 + s)) % H
            ln = 30 + 90 * s
            c.drawLine(px, py, px - ln * dirx, py - ln * .6, E.P(E.C(240, 245, 252, 220 * k), 'stroke', 4 + 10 * s * s, blur=3))
    return sk(img, f)

CRK = np.random.default_rng(31)
CROWN = []
for j in range(2):
    pts = [(0.0, 0.0)]; x = 0.0
    for s in range(14): x += CRK.uniform(40, 80); pts.append((x, CRK.uniform(-14, 14)))
    CROWN.append(pts)
def crown(img, u, x, y, k=1.0, gap=0.0):
    """the crown fracture: a dark crack zipping across the slope in both directions from (x, y); gap opens it (the slab drops)"""
    def f(c):
        for d, pts in zip((1, -1), CROWN):
            n = 1 + int(u * (len(pts) - 1)); pth = skia.Path(); pth.moveTo(W * x, H * y)
            for px, py in pts[1:n + 1]: pth.lineTo(W * x + d * px, H * y + py)
            c.drawPath(pth, E.P(E.C(10, 25, 45, 255 * k), 'stroke', 10 + 26 * gap))
            c.drawPath(pth, E.P(E.C(150, 210, 255, 180 * k), 'stroke', 3, blur=3, add=True))
    return sk(img, f)

def slab_drop(img, u):
    """everything below the crack line slides down the frame"""
    out = img.copy(); cut = int(H * .5); dy = int(240 * eout(u) ** 1.2)
    if dy > 0: out[cut + dy:] = img[cut:H - dy]; out[cut:cut + dy] = img[cut:cut + 1] * .4
    return out

# ---------------------------------------------------------------- 2D cards / diagrams
def bg_card(name, u, z=1.15, dark=.35, s=10): return blur(kb(name, u, z, z + .06), s) * dark

def angle_card(T, u, base='top_wide'):
    """slope-angle gauge: an arc from 0 to 60 degrees, the 30-45 band in red, a needle swinging to 38"""
    img = bg_card(base, u, dark=.3)
    def f(c):
        cx, cy, R = W * .2, H * .62, W * .62
        c.drawLine(cx, cy, cx + R * 1.05, cy, E.P(E.C(200, 210, 220), 'stroke', 6))
        for a0, a1, col, al in ((0, 30, (120, 200, 255), 120), (30, 45, (255, 90, 70), 255), (45, 60, (120, 200, 255), 120)):
            c.drawArc(skia.Rect.MakeXYWH(cx - R, cy - R, 2 * R, 2 * R), -a1, a1 - a0, False, E.P(E.C(*col, al * clamp(u * 3)), 'stroke', 46))
        for a in range(0, 61, 15):
            r1, r2 = R + 30, R + 60; ar = math.radians(a)
            c.drawLine(cx + r1 * math.cos(ar), cy - r1 * math.sin(ar), cx + r2 * math.cos(ar), cy - r2 * math.sin(ar), E.P(E.C(220, 225, 230), 'stroke', 5))
            text(c, f'{a}°', cx + (R + 120) * math.cos(ar), cy - (R + 120) * math.sin(ar) + 18, 46, WHITE)
        ang = max(0.0, 38 * eout(clamp((u - .1) * 2.2)) + 2 * math.sin(T * 7) * (1 - clamp((u - .1) * 2.2)))
        ar = math.radians(ang)
        # the slope itself as a white wedge
        pth = skia.Path(); pth.moveTo(cx, cy); pth.lineTo(cx + R * math.cos(ar), cy - R * math.sin(ar)); pth.lineTo(cx + R * math.cos(ar), cy); pth.close()
        c.drawPath(pth, E.P(E.C(235, 242, 250, 230)))
        c.drawLine(cx, cy, cx + R * 1.02 * math.cos(ar), cy - R * 1.02 * math.sin(ar), E.P(E.C(*YEL), 'stroke', 10))
        text(c, f'{ang:.0f}°', cx + R * .55, cy - R * .12, 90, YEL)
        text(c, 'DANGER ZONE: 30–45°', W / 2, H * .3, 62, RED, clamp(u * 3 - .4))
        text(c, 'TYPICAL START ZONE (SIMPLIFIED)', W / 2, cy + 120, 32, (160, 175, 190), .9)
    return snow(sk(img, f), T, .3)

def speedo(T, u, base='slope_up'):
    """speedometer sweeping to 80 mph next to a car icon: highway speed"""
    img = bg_card(base, u, dark=.32)
    v = 80 * eout(clamp(u * 1.4))
    def f(c):
        cx, cy, R = W / 2, H * .5, 330
        c.drawArc(skia.Rect.MakeXYWH(cx - R, cy - R, 2 * R, 2 * R), 150, 240, False, E.P(E.C(60, 70, 85), 'stroke', 40))
        c.drawArc(skia.Rect.MakeXYWH(cx - R, cy - R, 2 * R, 2 * R), 150, 240 * v / 100, False, E.P(E.C(255, 120, 60), 'stroke', 40))
        for m in range(0, 101, 20):
            a = math.radians(150 + 240 * m / 100); text(c, str(m), cx + (R - 90) * math.cos(a), cy + (R - 90) * math.sin(a) + 16, 44, (200, 210, 220))
        a = math.radians(150 + 240 * v / 100)
        c.drawLine(cx, cy, cx + (R - 30) * math.cos(a), cy + (R - 30) * math.sin(a), E.P(E.C(*YEL), 'stroke', 12)); c.drawCircle(cx, cy, 26, E.P(E.C(*YEL)))
        text(c, f'{v:.0f}', cx, cy + 190, 150, WHITE); text(c, 'MPH', cx, cy + 260, 54, (200, 210, 220))
        # little car icon zooming past
        a2 = clamp(u * 2 - .6)
        if a2 > 0:
            x0 = W * (1.1 - 1.3 * ((T * .9) % 1)); y0 = H * .82
            c.drawRoundRect(skia.Rect.MakeXYWH(x0, y0, 200, 60), 18, 18, E.P(E.C(220, 60, 50, 255 * a2)))
            c.drawRoundRect(skia.Rect.MakeXYWH(x0 + 40, y0 - 40, 110, 50), 16, 16, E.P(E.C(220, 60, 50, 255 * a2)))
            for wx in (40, 150): c.drawCircle(x0 + wx, y0 + 62, 22, E.P(E.C(20, 20, 24, 255 * a2)))
            for k in range(4): c.drawLine(x0 + 220, y0 + 10 + k * 14, x0 + 320 + k * 30, y0 + 10 + k * 14, E.P(E.C(255, 255, 255, 140 * a2), 'stroke', 4))
    return spray(sk(img, f), T, .35)

def nine_of_ten(T, u, base='top_wide'):
    """10 skier icons; 9 turn red one after another = triggered by the victim or their group"""
    img = bg_card(base, u, dark=.3)
    def f(c):
        for k in range(10):
            col_, row = k % 5, k // 5; x = W * (.17 + .165 * col_); y = H * (.36 + .17 * row)
            on = clamp(u * 14 - k * 1.0 - .5) if k < 9 else 0
            cl = (255, 90, 70) if on > .5 else (200, 210, 220)
            c.drawCircle(x, y - 70, 34, E.P(E.C(*cl)))
            c.drawRoundRect(skia.Rect.MakeXYWH(x - 26, y - 30, 52, 90), 20, 20, E.P(E.C(*cl)))
            c.drawLine(x - 60, y + 70, x + 60, y + 70, E.P(E.C(*cl), 'stroke', 8))
        text(c, '9 OUT OF 10', W / 2, H * .72, 110, RED, clamp(u * 3 - 1.2))
        text(c, 'SET OFF BY THE VICTIM OR THEIR GROUP', W / 2, H * .77, 40, WHITE, clamp(u * 3 - 1.5))
    return snow(sk(img, f), T, .3)

def section(T, u, hand=1.0, air=1.0, concrete=0.0, probe=0.0, depth=0.0, base='debris_hand'):
    """side cross-section of the debris: the surface line, Kai buried upright about a meter down, hand reaching up,
    an air space in front of his mouth; concrete hatching; a probe coming down (simplified, not to scale)"""
    img = bg_card(base, u, dark=.25, s=14)
    def f(c):
        sy = H * .3
        c.drawRect(skia.Rect.MakeLTRB(0, 0, W, sy), E.P(shader=E.linear((0, 0), (0, sy), [E.C(30, 40, 70, 200), E.C(200, 130, 90, 200)])))
        c.drawRect(skia.Rect.MakeLTRB(0, sy, W, H), E.P(shader=E.linear((0, sy), (0, H), [E.C(205, 222, 238, 245), E.C(120, 150, 180, 245)])))
        r = np.random.default_rng(2)
        for k in range(40):   # snow blocks in the debris
            x = r.random() * W; y = sy + 40 + r.random() * (H - sy); s = 20 + 50 * r.random()
            c.drawRoundRect(skia.Rect.MakeXYWH(x, y, s * 1.6, s), 12, 12, E.P(E.C(180, 200, 222, 160)))
        if concrete > 0:
            for k in range(0, 2 * W, 46): c.drawLine(k, sy, k - H, sy + H, E.P(E.C(90, 100, 115, 120 * concrete), 'stroke', 4))
        c.drawLine(0, sy, W, sy, E.P(E.C(255, 255, 255), 'stroke', 8))
        kx, ky = W * .5, H * .62
        # Kai (simple silhouette in his colors)
        c.drawRoundRect(skia.Rect.MakeXYWH(kx - 60, ky - 20, 120, 220), 40, 40, E.P(E.C(82, 97, 31)))
        c.drawCircle(kx, ky - 110, 95, E.P(E.C(240, 236, 230))); c.drawCircle(kx, ky - 150, 88, E.P(E.C(70, 31, 13)))
        c.drawCircle(kx - 30, ky - 105, 10, E.P(E.C(20, 20, 20))); c.drawCircle(kx + 30, ky - 105, 10, E.P(E.C(20, 20, 20)))
        # arm reaching up toward / through the surface
        hy = ky - 40 - (ky - 40 - (sy - 60)) * eout(clamp(hand))
        arm = skia.Path(); arm.moveTo(kx + 55, ky); arm.lineTo(kx + 130, ky - 40); arm.lineTo(kx + 130, min(hy, ky - 40)); c.drawPath(arm, E.P(E.C(25, 25, 30), 'stroke', 16)); c.drawCircle(kx + 130, min(hy, ky - 40), 22, E.P(E.C(190, 30, 25)))
        if air > 0:   # the air space in front of his face
            c.drawOval(skia.Rect.MakeXYWH(kx - 190, ky - 160, 150, 110), E.P(E.C(20, 40, 60, 220 * air)))
            c.drawOval(skia.Rect.MakeXYWH(kx - 190, ky - 160, 150, 110), E.P(E.C(*YEL, 255 * air), 'stroke', 6))
            E.arrow(c, W * .15, H * .5, kx - 150, ky - 110, 10, YEL, air)
            text(c, 'AIR SPACE', W * .2, H * .48, 50, YEL, air)
        if probe > 0:
            px = kx - 20; py = sy - 200 + (ky - 200 - (sy - 200)) * eout(clamp(probe))
            c.drawLine(px, sy - 260, px, py, E.P(E.C(210, 215, 222), 'stroke', 9))
            for m in range(int((py - sy) // 60) + 1): c.drawLine(px - 14, sy + m * 60, px + 14, sy + m * 60, E.P(E.C(40, 40, 40), 'stroke', 3))
        if depth > 0:
            mx = W * .86; c.drawLine(mx, sy, mx, ky - 200, E.P(E.C(*YEL, 255 * depth), 'stroke', 7))
            for yy in (sy, ky - 200): c.drawLine(mx - 24, yy, mx + 24, yy, E.P(E.C(*YEL, 255 * depth), 'stroke', 7))
        text(c, 'SIMPLIFIED · NOT TO SCALE', W / 2, H * .96, 30, (60, 70, 85), .9)
    return sk(img, f)

def timer15(T, u, base='debris_hand'):
    """15:00 countdown ring (most buried people have less than 15 minutes)"""
    img = bg_card(base, u, dark=.35)
    rem = 15 * 60 - 140 * u   # ticking (fast, illustrative)
    def f(c):
        cx, cy, R = W / 2, H * .47, 300
        c.drawCircle(cx, cy, R, E.P(E.C(255, 255, 255, 40), 'stroke', 34))
        c.drawArc(skia.Rect.MakeXYWH(cx - R, cy - R, 2 * R, 2 * R), -90, 360 * rem / 900, False, E.P(E.C(255, 90, 70), 'stroke', 34))
        mm, ss = int(rem // 60), int(rem % 60); text(c, f'{mm:02d}:{ss:02d}', cx, cy + 50, 150, WHITE)
        text(c, 'LACK OF AIR = #1 KILLER', cx, cy + R + 130, 52, YEL, clamp(u * 3))
    return sk(img, f)

def bars(T, u):
    """average rescue times in a Swiss study (Eurac / JAMA Netw Open 2024): rescue team ~90 min vs companions ~10 min"""
    img = bg_card('debris_hand', u, dark=.28)
    def f(c):
        maxw = W * .52; x0 = W * .1
        for k, (lab, v, col) in enumerate((('RESCUE TEAM', 90, (255, 110, 90)), ('FRIENDS ON SITE', 10, (120, 230, 150)))):
            y = H * (.36 + k * .17); g = eout(clamp(u * 2.2 - k * .4))
            text(c, lab, x0, y - 20, 50, WHITE, g, center=False)
            c.drawRoundRect(skia.Rect.MakeXYWH(x0, y, maxw * v / 90 * g + 8, 90), 20, 20, E.P(E.C(*col)))
            text(c, f'~{v} MIN', x0 + maxw * v / 90 * g + 30, y + 66, 56, col, g, center=False)
        text(c, 'AVERAGE TIME TO DIG OUT (SWISS DATA)', W / 2, H * .7, 34, (170, 185, 200), .9)
    return snow(sk(img, f), T, .3)

def beacon_ui(T, u, mode='search', dist=None):
    """close-up of the beacon screen: SEND switches to SEARCH, an arrow and a falling distance"""
    img = bg_card('nora_beacon', u, z=1.4, dark=.4, s=6)
    def f(c):
        bx, by, bw, bh = W * .2, H * .2, W * .6, H * .5
        c.drawRoundRect(skia.Rect.MakeXYWH(bx - 30, by - 30, bw + 60, bh + 60), 70, 70, E.P(E.C(240, 180, 20)))
        c.drawRoundRect(skia.Rect.MakeXYWH(bx, by, bw, bh * .7), 40, 40, E.P(E.C(10, 30, 22)))
        sx, sy = bx + bw / 2, by + bh * .3
        if mode == 'send' or (mode == 'switch' and u < .45):
            for k in range(3):
                a = ((T * 1.5 + k / 3) % 1); c.drawCircle(sx, sy, 40 + 220 * a, E.P(E.C(120, 255, 170, 255 * (1 - a)), 'stroke', 8))
            text(c, 'SEND', sx, by + bh * .62, 90, (120, 255, 170))
        else:
            ang = math.sin(T * 2) * 12
            c.save(); c.translate(sx, sy); c.rotate(ang)
            pth = skia.Path(); pth.moveTo(0, -150); pth.lineTo(90, 0); pth.lineTo(35, 0); pth.lineTo(35, 120); pth.lineTo(-35, 120); pth.lineTo(-35, 0); pth.lineTo(-90, 0); pth.close()
            c.drawPath(pth, E.P(E.C(120, 255, 170))); c.restore()
            text(c, 'SEARCH' if dist is None else f'{dist:.1f} m', sx, by + bh * .62, 90, (120, 255, 170))
        c.drawCircle(bx + bw * .3, by + bh * .86, 46, E.P(E.C(30, 30, 34))); c.drawCircle(bx + bw * .7, by + bh * .86, 46, E.P(E.C(30, 30, 34)))
    return snow(sk(img, f), T, .5)

def curve(T, u, base='group_end'):
    """survival vs time buried (simplified from the Swiss curve in CMAJ 2011): ~90%+ early, a steep drop, ~1 in 3 by 35 min"""
    img = bg_card(base, u, dark=.28)
    pts = [(0, 100), (5, 97), (10, 93), (15, 91), (18, 90), (22, 70), (26, 52), (30, 41), (35, 34), (45, 28), (60, 22)]
    def X(m): return W * .14 + m / 60 * W * .74
    def Y(p): return H * .7 - p / 100 * H * .38
    def f(c):
        c.drawLine(X(0), Y(0), X(60), Y(0), E.P(E.C(200, 210, 220), 'stroke', 5)); c.drawLine(X(0), Y(0), X(0), Y(100), E.P(E.C(200, 210, 220), 'stroke', 5))
        for m in (0, 10, 35, 60): text(c, f'{m}', X(m), Y(0) + 60, 40, (200, 210, 220))
        text(c, 'MINUTES BURIED', W / 2, Y(0) + 120, 38, (200, 210, 220))
        g = clamp(u * 1.6); pth = skia.Path(); lim = 60 * g; first = True
        for (m0, p0), (m1, p1) in zip(pts, pts[1:]):
            if m0 > lim: break
            if first: pth.moveTo(X(m0), Y(p0)); first = False
            mm = min(m1, lim); pp = p0 + (p1 - p0) * (mm - m0) / (m1 - m0); pth.lineTo(X(mm), Y(pp))
        c.drawPath(pth, E.P(E.C(*YEL), 'stroke', 12))
        if lim >= 10:
            c.drawCircle(X(10), Y(93), 18, E.P(E.C(120, 230, 150))); text(c, 'MOST SURVIVE', X(10) + 190, Y(93) - 40, 46, (120, 230, 150))
        if lim >= 35:
            c.drawCircle(X(35), Y(34), 18, E.P(E.C(*RED))); text(c, '~1 IN 3', X(35) + 40, Y(34) - 50, 60, RED)
        text(c, 'SIMPLIFIED · SWISS DATA (CMAJ 2011)', W / 2, H * .82, 30, (160, 175, 190), .9)
    return snow(sk(img, f), T, .3)

def hook_frame(t, T):
    """the hook / loop shot: the powder cloud swallowing Kai"""
    img = kb('kai_caught', t / 2.2, 1.75, 1.55, (.47, .5), (.48, .51), rot=-4 + 3 * t)
    img = (img - 120) * 1.35 + 100
    img = billow(img, T, .1 + .05 * t, .95, top=-.45)
    img = spray(img, T, .35)
    return shake(img, t + .3, 16, 1.2)

# ---------------------------------------------------------------- scenes
def S0(t, T):   # HOOK: the avalanche swallowing Kai -> his arm in the churning snow
    if t < 1.05: return hook_frame(t, T)
    u = t - 1.05
    img = kb('kai_caught', u / 1.6, 1.0, 1.12, (.5, .5), (.55, .48), rot=6 * math.sin(u * 5))
    return whip(spray(billow(img, T, .3 + .1 * u, .9), T, .9), u)

def S1(t, T):
    c = wt('Nora') - .15
    if t < c: return snow(kb('slope_up', t / c, 1.0, 1.15, (.5, .55), (.5, .5)), T, .5)
    return whip(snow(kb('top_wide', (t - c) / 2.4, 1.05, 1.15, (.5, .55), (.52, .52)), T, .5), t - c)

def S2(t, T): return ptalk('cu_leo', t, t / (D + PAD), 1.02, 1.12, (.5, .45), (.5, .43), .01, .4)
def S3(t, T): return ptalk('cu_kai', t, t / (D + PAD), 1.04, 1.1, (.5, .45), (.5, .44), .008, .4)

def S4(t, T):
    c1 = wt('thirty') - .2; c2 = wt('Like') - .1
    if t < c1: return snow(kb('top_wide', t / c1, 1.1, 1.2, (.5, .55), (.5, .52)), T, .4)
    if t < c2: return whip(angle_card(T, (t - c1) / max(1, c2 - c1)), t - c1)
    return whip(snow(kb('kai_crack', (t - c2) / 2, 1.0, 1.1, (.5, .5), (.5, .47)), T, .4), t - c2)

def S5(t, T):
    c = wt('The') - .1
    if t < c:
        img = kb('kai_crack', t / c, 1.1, 1.18, (.5, .5), (.5, .5))
        return shake(crown(img, clamp(t / (c * .6)), .5, .56, 1.0), t, 12, 3)
    u = t - c; g = eout(clamp(u / 2.6))
    img = crown(kb('kai_crack', 1, 1.18, 1.18, (.5, .5), (.5, .5)), 1, .5, .56, 1.0, clamp(u * 2))
    img = shift(img, 0, 420 * g ** 1.4)
    if g > .05:
        k = int(1 + 60 * g) | 1; ker = np.zeros((k, 1), np.float32); ker[...] = 1 / k; img = cv2.filter2D(img, -1, ker)
    return shake(spray(img, T, clamp(u)), u, 10, 1)

def S6(t, T):
    c = wt('eighty') - .4
    if t < c: return shake(billow(kb('slope_up', t / c, 1.0, 1.2, (.5, .5), (.5, .55)), T, .15 + .55 * ease(t / c), 1.0), t, 6, .5)
    return whip(speedo(T, clamp((t - c) / 1.8)), t - c)

def S7(t, T):
    c = wt('victim') + .6
    if t < c: return nine_of_ten(T, t / c)
    return whip(snow(kb('cu_kai', (t - c) / 2, 1.1, 1.2, (.5, .45), (.5, .44)), T, .4), t - c)

def S8(t, T):
    img = ptalk('cu_nora', t, t / (D + PAD), 1.04, 1.14, (.5, .45), (.5, .44), .012, .3)
    return spray(shake(img, t, 8, 1.5), T, .5)

def S9(t, T):
    c1 = wt('side') - .1; c2 = wt('swim') - .1
    if t < c1: return spray(billow(kb('kai_caught', t / c1, 1.15, 1.25, (.5, .5), (.5, .5), rot=4 * math.sin(t * 4)), T, .25, .9), T, .8)
    if t < c2:
        u = t - c1; img = kb('slope_up', u / 2, 1.1, 1.18, (.5, .5), (.45, .5))
        def f(cn):
            E.arrow(cn, W * .5, H * .55, W * .12, H * .5, 18, YEL, clamp(u * 3))
        return whip(billow(sk(img, f), T, .3, .8), u)
    u = t - c2; img = kb('kai_caught', u / 2, 1.0, 1.1, (.5, .52), (.5, .45), rot=-5 * math.sin(u * 6))
    return whip(spray(billow(shift(img, 0, -40 * math.sin(u * 8)), T, .22, .8), T, .7), u)

def S10(t, T):
    c = wt('clear') - .1
    if t < c: return section(T, t / (D + PAD), hand=clamp(t / c), air=0.0)
    return section(T, t / (D + PAD), hand=1.0, air=clamp((t - c) * 2.5))

def S11(t, T):
    c = wt('And') - .1
    if t < c:
        img = kb('debris_hand', t / c, 1.12, 1.0, (.5, .5), (.5, .5)); return shake(snow(img, T, .3), t, 14, 4)
    u = t - c; return whip(section(T, u / 2.5, 1.0, 1.0, concrete=clamp(u * 2)), u)

def S12(t, T): return shake(ptalk('leo_debris', t, t / (D + PAD), 1.02, 1.12, (.5, .45), (.5, .43), .012, .3), t, 5, 2)
def S13(t, T): return ptalk('nora_debris', t, t / (D + PAD), 1.06, 1.14, (.5, .45), (.5, .43), .01, .3)

def S14(t, T):
    c = wt('Most', 14) if False else None
    c = 2.4
    if t < c: return section(T, t / c, 1.0, .4 + .6 * abs(math.sin(T * 2)), base='debris_hand')
    return whip(timer15(T, (t - c) / 3), t - c)

def S15(t, T):
    c = wt('So') - .15
    if t < c: return bars(T, t / c)
    return whip(snow(kb('nora_beacon', (t - c) / 2, 1.0, 1.1, (.5, .5), (.5, .47)), T, .4), t - c)

def S16(t, T):
    c = wt('Nora') - .1
    if t < c: return beacon_ui(T, t / (D + PAD), 'send')
    return whip(beacon_ui(T, t / (D + PAD), 'switch' if t - c < 1.2 else 'search'), t - c) if (t - c) < 1.4 else snow(kb('nora_beacon', (t - c - 1.4) / 2, 1.1, 1.18, (.5, .5), (.5, .48)), T, .4)

def S17(t, T):
    c = 1.0
    if t < c: return beacon_ui(T, t / (D + PAD), 'search', 6.0 - 4.0 * t)
    return whip(ptalk('nora_beacon', t, (t - c) / 2, 1.12, 1.2, (.5, .45), (.5, .43), .01, .4), t - c)

def S18(t, T):
    c = wt('three') - .3
    if t < c: return snow(kb('probe', t / c, 1.0, 1.14, (.5, .5), (.5, .55)), T, .4)
    return whip(section(T, (t - c) / 2, 1.0, 1.0, probe=clamp((t - c) * 1.8), depth=clamp((t - c) * 2 - .6)), t - c)

def S19(t, T):
    c = wt('Digging') - .1
    img = kb('dig_pit', t / (D + PAD), 1.0, 1.12, (.5, .5), (.5, .55))
    if t > c: img = spray(img, T, .8, -1.0)
    return shake(snow(img, T, .3), (t - c) if t > c else 5, 6, 2)

def S20(t, T):
    c = wt('face') - .25; c2 = wt('space') - .1
    if t < c: return snow(kb('debris_hand', t / c, 1.1, 1.25, (.5, .5), (.52, .52)), T, .3)
    img = kb('kai_face', (t - c) / 3, 1.0, 1.1, (.5, .48), (.5, .45))
    img = breath(img, T, .5, .52, .9, True)
    if t > c2:
        def f(cn): E.glow(cn, W * .5, H * .53, 120, (255, 200, 120), .15)
        img = sk(img, f)
    return whip(img, t - c)

def S21(t, T):
    c = wt('only') + .8
    if t < c: return curve(T, t / c)
    return whip(snow(kb('group_end', (t - c) / 2, 1.0, 1.06, (.5, .5), (.5, .48)), T, .4), t - c)

def S22(t, T):
    c = (D + PAD) - 1.0
    if t < c * .55: return snow(kb('group_end', t / c, 1.06, 1.14, (.5, .5), (.6, .48)), T, .4)
    if t < c:
        u = (t - c * .55) / (c * .45)
        return whip(snow(kb('cu_kai', u, 1.1, 1.2, (.5, .45), (.5, .44)), T, .4), t - c * .55)
    return whip(hook_frame(0, T), t - c, vertical=True)   # loop: the first frame again

# ---------------------------------------------------------------- overlays
def overlays():
    o = []
    if idx == 0: o += [{'type': 'hook', 'text': 'BURIED BY|AN AVALANCHE', 'y': .11}]
    if idx == 1: o += [{'type': 'datestamp', 'text': 'BACKCOUNTRY · FRESH SNOW', 'y': .08, 'from': .1}]
    if idx == 4: o += [{'type': 'badge', 'value': '30–45°', 'unit': 'WHERE MOST START', 'pos': [.5, .12], 'from': wt('thirty') - .1, 'size': 70}]
    if idx == 5: o += [{'type': 'label', 'text': 'CRACK', 'pos': [.5, .14], 'color': WHITE, 'from': .1}]
    if idx == 6: o += [{'type': 'badge', 'value': '~80', 'unit': 'MPH', 'pos': [.5, .12], 'from': wt('eighty') - .1},
                       {'type': 'label', 'text': '≈ A CAR ON THE HIGHWAY', 'pos': [.5, .2], 'color': WHITE, 'from': wt('eighty') + .3}]
    if idx == 9: o += [{'type': 'label', 'text': 'GET TO THE SIDE', 'pos': [.5, .1], 'color': YEL, 'from': wt('side') - .1},
                       {'type': 'label', 'text': 'GRAB A TREE', 'pos': [.5, .15], 'color': YEL, 'from': wt('tree') - .1},
                       {'type': 'label', 'text': 'SWIM HARD', 'pos': [.5, .2], 'color': YEL, 'from': wt('swim') - .1}]
    if idx == 10: o += [{'type': 'label', 'text': 'HAND UP', 'pos': [.5, .1], 'color': YEL, 'from': wt('hand') - .1}]
    if idx == 11: o += [{'type': 'label', 'text': 'SETS LIKE CONCRETE', 'pos': [.5, .12], 'color': WHITE, 'from': wt('concrete') - .2}]
    if idx == 14: o += [{'type': 'badge', 'value': '<15', 'unit': 'MINUTES FOR MOST', 'pos': [.5, .12], 'from': wt('fifteen') - .1}]
    if idx == 16: o += [{'type': 'label', 'text': 'AVALANCHE BEACON', 'pos': [.5, .12], 'color': YEL, 'from': wt('beacon') - .1}]
    if idx == 18: o += [{'type': 'badge', 'value': '~3 FT', 'unit': 'DOWN', 'pos': [.5, .12], 'from': wt('three') - .1}]
    if idx == 19: o += [{'type': 'label', 'text': 'SHOVEL FAST', 'pos': [.5, .12], 'color': YEL, 'from': wt('Digging') - .1}]
    if idx == 22: o += [{'type': 'cta', 'text': 'FOLLOW FOR MORE STORIES', 'from': .2}]
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
