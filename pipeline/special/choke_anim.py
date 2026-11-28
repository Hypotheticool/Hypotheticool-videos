"""Animate every scene of "Kai started choking at dinner" over its Cycles plates (choke_plate.py):
2D camera moves and cuts, thrust/blow shakes, the flying bite, air flow through the real anatomy, and the first-aid graphics.
python3 choke_anim.py <scene> [still_times...]  ->  choke/s<scene>/f_####.png + meta.json (overlays read by compose.py)"""
import sys, math, json, os
sys.path.insert(0, '/home/claude/pro')
import numpy as np, cv2, skia
import engine as E
ROOT = '/home/claude/b3d/choke'; CFG = json.load(open(f'{ROOT}/topic.json'))
FPS = 24; PAD = .75; XF = .35
idx = int(sys.argv[1]); D = CFG['durs'][idx]; NF = int(math.ceil((D + PAD) * FPS))
T0 = sum(CFG['durs'][:idx])
W, H = 1080, 1920
ease = lambda t: .5 - .5 * math.cos(math.pi * min(max(t, 0), 1))
eout = lambda t: 1 - (1 - min(max(t, 0), 1)) ** 3
clamp = lambda v, a=0., b=1.: max(a, min(b, v))
YEL, WHITE, BLUE, RED, GREEN, GREY, ORANGE = (255, 222, 40), (255, 255, 255), (130, 200, 255), (255, 95, 80), (120, 235, 150), (170, 178, 190), (255, 150, 50)

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
FIREPL = set()
def plate(name):
    """load a plate, upscale, grade into the palette (deep navy shadows, warm highlights); fire plates get crushed blacks + hot orange"""
    if name not in PL:
        im = cv2.imread(f'{ROOT}/plates/{name}.png', cv2.IMREAD_COLOR)
        if im.shape[1] != W: im = cv2.resize(im, (W, H), interpolation=cv2.INTER_CUBIC)
        im = im.astype(np.float32); lum = im.mean(2, keepdims=True) / 255
        if name in FIREPL:
            im = 255 * (im / 255) ** 1.7 * np.float32([.55, .85, 1.25])        # contrast up, push to orange
        im = im * .92 + (1 - lum) * np.float32([22, 8, 0]) - 2
        im = im * (.92 + .1 * lum) * VIGM
        im = cv2.addWeighted(im, 1.25, cv2.GaussianBlur(im, (0, 0), 2.2), -.25, 0)
        PL[name] = np.clip(im, 0, 255)
    return PL[name]
PT = {}
def pts(name):
    if name not in PT:
        d = {}; p = f'{ROOT}/plates/{name}.txt'
        if os.path.exists(p):
            for ln in open(p): k, x, y = ln.split(); d[k] = (float(x) * W, float(y) * H)
        PT[name] = d
    return PT[name]

LASTM = [None]
def kb(name, u, z0, z1, c0=(.5, .5), c1=(.5, .5), rot=0.0, im=None):
    im = plate(name) if im is None else im; t = ease(u); z = z0 + (z1 - z0) * t
    cx = (c0[0] + (c1[0] - c0[0]) * t) * W; cy = (c0[1] + (c1[1] - c0[1]) * t) * H
    M = cv2.getRotationMatrix2D((cx, cy), rot, z); M[0, 2] += W / 2 - cx; M[1, 2] += H / 2 - cy; LASTM[0] = (M, z)
    return cv2.warpAffine(im, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
def sp(name, key):
    """plate point -> screen point under the last kb() transform"""
    M, z = LASTM[0]; x, y = pts(name)[key]; return M[0, 0] * x + M[0, 1] * y + M[0, 2], M[1, 0] * x + M[1, 1] * y + M[1, 2], z

def shift(img, dx, dy): return cv2.warpAffine(img, np.float32([[1, 0, dx], [0, 1, dy]]), (W, H), borderMode=cv2.BORDER_REFLECT)
def shake(img, t, amp=10, decay=3.0):
    a = amp * math.exp(-t * decay)
    if a < .5: return img
    return shift(img, a * math.sin(t * 71), a * math.cos(t * 53))
def talk(t, amp=.006): return 1 + amp * (math.sin(t * 17) * .6 + math.sin(t * 11) * .4)
def ptalk(name, t, u, z0, z1, c0=(.5, .5), c1=(.5, .5), amp=.007):
    img = kb(name, u, z0, z1, c0, c1)
    return cv2.warpAffine(img, cv2.getRotationMatrix2D((W / 2, H / 2), 0, talk(t, amp)), (W, H), borderMode=cv2.BORDER_REFLECT)
def whip(img, t, dur=.12, vertical=False):
    if t >= dur: return img
    k = int(70 * (1 - t / dur)) | 1
    if k < 3: return img
    ker = np.zeros((k, 1) if vertical else (1, k), np.float32); ker[...] = 1 / k
    return cv2.filter2D(img, -1, ker)
def flash(img, t, k=220, decay=7, col=(1, 1, 1)): return img + k * math.exp(-max(t, 0) * decay) * np.float32(col)
def blur(img, s): return cv2.GaussianBlur(img, (0, 0), s) if s > .3 else img
def darken(img, k): return img * (1 - k)
def sk(img, fn):
    a = np.clip(img, 0, 255).astype(np.uint8); bgra = np.dstack([a, np.full(a.shape[:2], 255, np.uint8)])
    s = skia.Surface(W, H); c = s.getCanvas()
    c.drawImage(skia.Image.fromarray(np.ascontiguousarray(bgra), colorType=skia.kBGRA_8888_ColorType), 0, 0)
    fn(c); return s.makeImageSnapshot().toarray()[..., :3].astype(np.float32)
def font(sz): return skia.Font(E.TF, sz)
def text(c, s, x, y, sz, col=WHITE, a=1.0, center=True):
    f = font(sz); w = f.measureText(s) if center else 0
    c.drawString(s, x - w / 2, y, f, E.P(E.C(0, 0, 0, 200 * a), 'stroke', max(6, sz // 8)))
    c.drawString(s, x - w / 2, y, f, E.P(E.C(*col, 255 * a)))
def panel(c, x, y, w, h, a=1.0):
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, y, w, h), 34, 34), E.P(E.C(12, 18, 28, 225 * a)))
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, y, w, h), 34, 34), E.P(E.C(120, 150, 180, 120 * a), 'stroke', 3))

def rings(img, T, x, y, col=RED, k=1.0):
    def f(c):
        for j in range(3):
            a = (T * 1.8 + j / 3) % 1; r = 60 + 220 * a
            c.drawCircle(x, y, r, E.P(E.C(*col, 200 * (1 - a) * k), 'stroke', 9))
    return sk(img, f)
def siren(img, T, k=1.0):
    """red/blue flashing light washing over the frame"""
    ph = (T * 2.4) % 1; r_ = max(0, math.sin(ph * 6.28)); b_ = max(0, -math.sin(ph * 6.28))
    return img * (1 - .12 * k) + (np.float32([40, 30, 255]) * r_ + np.float32([255, 90, 30]) * b_) * .18 * k * (.4 + .6 * (1 - YY / H))[..., None]

import re as _re
def wx(word, end=False):
    """exact-word cue (punctuation stripped), local scene time"""
    ln = E.shown(CFG['lines'][idx]); words = ln.split(); clip = D - E.lead(idx) - E.GAP; tt = E.word_times(ln, clip)
    for k, w in enumerate(words):
        if _re.sub(r'[^a-z0-9]', '', w.lower()) == word.lower(): return XF + E.lead(idx) + tt[k][1 if end else 0]
    raise KeyError(word)
def zoomc(img, z, cx=.5, cy=.5):
    M = cv2.getRotationMatrix2D((cx * W, cy * H), 0, z); M[0, 2] += W / 2 - cx * W; M[1, 2] += H / 2 - cy * H
    return cv2.warpAffine(img, M, (W, H), borderMode=cv2.BORDER_REFLECT)
def punch(t, t0, amp=18, decay=9.0):
    """a single hard jolt at t0 (a blow or a thrust)"""
    if t < t0: return 0.0
    return amp * math.exp(-(t - t0) * decay) * math.cos((t - t0) * 40)
def jolt(img, t, hits, amp=18, vertical=True):
    d = sum(punch(t, h, amp) for h in hits)
    if abs(d) < .3: return img
    return shift(img, d * .35, -abs(d) if vertical else d)

# ---------------------------------------------------------------- the choking face: red-to-blue tint, mute icon, pulse rings
def face_tint(img, x, y, r, col, k):
    if k <= 0: return img
    m = np.zeros((H, W), np.float32); cv2.circle(m, (int(x), int(y)), int(r), 1.0, -1, cv2.LINE_AA)
    m = cv2.GaussianBlur(m, (0, 0), r * .35)[..., None] * k
    return img * (1 - m * .45) + np.float32(col)[::-1] * m * .45 * (img / 255 + .35)
def mute_icon(c, x, y, s, a=1.0):
    p = skia.Path(); p.moveTo(x - 40 * s, y - 22 * s); p.lineTo(x - 12 * s, y - 22 * s); p.lineTo(x + 22 * s, y - 52 * s)
    p.lineTo(x + 22 * s, y + 52 * s); p.lineTo(x - 12 * s, y + 22 * s); p.lineTo(x - 40 * s, y + 22 * s); p.close()
    c.drawCircle(x, y, 92 * s, E.P(E.C(12, 18, 28, 220 * a))); c.drawPath(p, E.P(E.C(*WHITE, 255 * a)))
    for d in (-1, 1): c.drawLine(x + 40 * s, y - 28 * s * d, x + 86 * s, y + 28 * s * d, E.P(E.C(*RED, 255 * a), 'stroke', 13 * s))
def corner_timer(img, T):
    """fictional elapsed time since Kai's airway blocked (scene 5 'blocked'), small, top-left"""
    el = T - TBLOCK
    if el < 0: return img
    def f(c):
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(60, 410, 270, 96), 26, 26), E.P(E.C(12, 18, 28, 215)))
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(60, 410, 270, 96), 26, 26), E.P(E.C(*RED, 230), 'stroke', 5))
        c.drawCircle(112, 458, 26, E.P(E.C(*WHITE, 255), 'stroke', 6)); a = math.radians(el * 6 * 6)
        c.drawLine(112, 458, 112 + math.sin(a) * 18, 458 - math.cos(a) * 18, E.P(E.C(*RED, 255), 'stroke', 5))
        text(c, f'{int(el) // 60}:{int(el) % 60:02d}', 155, 482, 66, WHITE, 1, False)
    return sk(img, f)
TB_IDX = 5
def _tblock():
    ln = E.shown(CFG['lines'][TB_IDX]); words = ln.split(); clip = CFG['durs'][TB_IDX] - E.lead(TB_IDX) - E.GAP; tt = E.word_times(ln, clip)
    k = [i for i, w in enumerate(words) if w.lower().startswith('blocked')][0]
    return sum(CFG['durs'][:TB_IDX]) + E.lead(TB_IDX) + tt[k][0] + XF
TBLOCK = _tblock()

# ---------------------------------------------------------------- 2D graphics
def icon_card(c, x, y, w, h, title, sub, col, a, mark=None):
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, y, w, h), 34, 34), E.P(E.C(14, 20, 30, 232 * a)))
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, y, w, h), 34, 34), E.P(E.C(*col, 255 * a), 'stroke', 6))
    text(c, title, x + w / 2, y + h * .45, 70, WHITE, a); text(c, sub, x + w / 2, y + h * .45 + 70, 46, GREY, a)
    if mark == 'x':
        c.drawLine(x + w - 120, y + 40, x + w - 40, y + 120, E.P(E.C(*RED, 255 * a), 'stroke', 16)); c.drawLine(x + w - 40, y + 40, x + w - 120, y + 120, E.P(E.C(*RED, 255 * a), 'stroke', 16))
    if mark == 'ok':
        p = skia.Path(); p.moveTo(x + w - 130, y + 85); p.lineTo(x + w - 95, y + 120); p.lineTo(x + w - 35, y + 45)
        c.drawPath(p, E.P(E.C(*GREEN, 255 * a), 'stroke', 16))
def cough_card(T, u):
    img = blur(kb('choke', .5, 1.15, 1.18, (.5, .45), (.5, .45)), 7) * .35
    def f(c):
        g = eout(clamp(u * 2.5)); icon_card(c, 110, 560 + 40 * (1 - g), 860, 330, 'COUGHING HARD?', 'let them keep coughing', GREEN, g, 'ok')
        g2 = eout(clamp(u * 2.5 - 1.1)); text(c, 'it may clear on its own', 540, 1010, 48, GREY, g2)
    return sk(img, f)
def cant_list(c, n, a=1.0):
    for k, w in enumerate(('COUGH', 'TALK', 'BREATHE')):
        g = eout(clamp(n - k))
        if g <= 0: continue
        y = 560 + k * 150; x = 600 + 80 * (1 - g)
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, y, 400, 118), 30, 30), E.P(E.C(14, 20, 30, 225 * g * a)))
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, y, 400, 118), 30, 30), E.P(E.C(*RED, 255 * g * a), 'stroke', 5))
        text(c, w, x + 40, y + 82, 62, WHITE, g * a, False)
        c.drawLine(x + 320, y + 30, x + 375, y + 88, E.P(E.C(*RED, 255 * g * a), 'stroke', 12)); c.drawLine(x + 375, y + 30, x + 320, y + 88, E.P(E.C(*RED, 255 * g * a), 'stroke', 12))
def person_icon(c, x, y, s, col, a):
    c.drawCircle(x, y - 34 * s, 17 * s, E.P(E.C(*col, 255 * a)))
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x - 19 * s, y - 13 * s, 38 * s, 52 * s), 14 * s, 14 * s), E.P(E.C(*col, 255 * a)))
def deaths(T, u):
    img = blur(kb('dinner', .5 + .3 * u, 1.1, 1.15), 8) * .3
    def f(c):
        panel(c, 70, 440, 940, 900, eout(u * 4))
        n = int(clamp(u * 1.6) * 120)
        for k in range(120):
            r_, q = divmod(k, 12); g = 1.0 if k < n else .0
            person_icon(c, 140 + q * 72, 560 + r_ * 64, .95, (255, 120, 90) if k < n else (70, 80, 95), .35 + .65 * g)
        g2 = eout(clamp(u * 2 - 1.0))
        text(c, '5,923', 540, 1250, 130, YEL, g2); text(c, 'US choking deaths in 2024 (NSC)', 540, 1310, 40, WHITE, g2)
    return sk(img, f)
def stopwatch(c, x, y, r, secs, maxs, a=1.0, col=RED):
    c.drawCircle(x, y, r, E.P(E.C(14, 20, 30, 235 * a))); c.drawCircle(x, y, r, E.P(E.C(*WHITE, 255 * a), 'stroke', 10))
    c.drawRect(skia.Rect.MakeXYWH(x - 22, y - r - 46, 44, 40), E.P(E.C(*WHITE, 255 * a)))
    for k in range(12):
        ang = math.radians(k * 30); c.drawLine(x + math.sin(ang) * r * .82, y - math.cos(ang) * r * .82, x + math.sin(ang) * r * .93, y - math.cos(ang) * r * .93, E.P(E.C(*WHITE, 200 * a), 'stroke', 5))
    pth = skia.Path(); pth.moveTo(x, y); pth.arcTo(skia.Rect.MakeLTRB(x - r * .78, y - r * .78, x + r * .78, y + r * .78), -90, 359.9 * min(secs, maxs) / maxs, False); pth.close()
    c.drawPath(pth, E.P(E.C(*col, 160 * a)))
    ang = math.radians(360 * secs / maxs); c.drawLine(x, y, x + math.sin(ang) * r * .8, y - math.cos(ang) * r * .8, E.P(E.C(*WHITE, 255 * a), 'stroke', 9))
    text(c, f'{int(secs) // 60}:{int(secs) % 60:02d}', x, y + r + 110, 110, YEL, a)
def four_min(T, u):
    img = blur(kb('hook', .5, 1.2, 1.25, (.5, .42), (.5, .42)), 9) * .32
    img = face_tint(img, W * .5, H * .4, 300, (60, 110, 255), .6)
    def f(c):
        secs = 240 * eout(clamp(u * 1.25)); stopwatch(c, 540, 720, 220, secs, 240)
        text(c, 'NO OXYGEN', 540, 470, 64, WHITE, eout(clamp(u * 3)))
    return sk(img, f)
def torso(T, u, stage):
    """front diagram: rib cage, belly button, fist just above it, arrow in and up"""
    img = blur(kb('thrust', .5, 1.2, 1.22, (.5, .45), (.5, .45)), 9) * .3
    def f(c):
        panel(c, 90, 330, 900, 1000, 1)
        cx = 540; c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(cx - 250, 380, 500, 900), 200, 200), E.P(E.C(220, 190, 160, 60)))
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(cx - 250, 380, 500, 900), 200, 200), E.P(E.C(*WHITE, 180), 'stroke', 5))
        for k in range(6):   # ribs
            yy = 470 + k * 62; w = 190 - k * 4
            p = skia.Path(); p.moveTo(cx - 20, yy); p.quadTo(cx - w, yy + 10, cx - w + 15, yy + 70); c.drawPath(p, E.P(E.C(240, 235, 225, 200), 'stroke', 9))
            p = skia.Path(); p.moveTo(cx + 20, yy); p.quadTo(cx + w, yy + 10, cx + w - 15, yy + 70); c.drawPath(p, E.P(E.C(240, 235, 225, 200), 'stroke', 9))
        c.drawRect(skia.Rect.MakeXYWH(cx - 14, 450, 28, 300), E.P(E.C(240, 235, 225, 200)))   # breastbone
        text(c, 'RIBS', cx + 300, 640, 44, GREY, 1, False)
        c.drawCircle(cx, 1010, 14, E.P(E.C(*WHITE, 255))); text(c, 'BELLY BUTTON', cx + 60, 1050, 44, GREY, 1, False)
        g = eout(clamp(u * 2.5))
        if g > 0:
            fy = 900; c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(cx - 75, fy - 50, 150, 100), 40, 40), E.P(E.C(*YEL, 255 * g)))
            for k in range(3): c.drawLine(cx - 40 + k * 40, fy - 40, cx - 40 + k * 40, fy - 5, E.P(E.C(120, 90, 20, 255 * g), 'stroke', 5))
            text(c, 'FIST', cx - 300, 920, 54, YEL, g, False)
        if stage >= 1:
            g2 = eout(clamp(u * 2.5 - .8)); p = skia.Path(); p.moveTo(cx + 210, 960); p.quadTo(cx + 30, 980, cx + 20, 760 + 120 * (1 - g2))
            c.drawPath(p, E.P(E.C(*RED, 255 * g2), 'stroke', 16)); tip_y = 760 + 120 * (1 - g2)
            pp = skia.Path(); pp.moveTo(cx + 20, tip_y - 40); pp.lineTo(cx - 16, tip_y + 10); pp.lineTo(cx + 56, tip_y + 10); pp.close(); c.drawPath(pp, E.P(E.C(*RED, 255 * g2)))
            text(c, 'IN + UP', cx + 230, 900, 60, RED, g2, False)
    return sk(img, f)
BITE = (150, 100, 60)
def anat_air(T, u, flow=0.0, pop=0.0, block=1.0, diaph=0.0):
    img = kb('anat', u, 1.3, 1.4, (.5, .44), (.5, .42))
    tx, ty, z = sp('anat', 'trach_top'); mx, my, _ = sp('anat', 'trach_mid'); dx, dy, _ = sp('anat', 'diaph')
    def f(c):
        if diaph > 0:   # diaphragm pushed up
            for s in (-1, 1):
                x = dx + s * 170; c.drawLine(x, dy + 170, x, dy + 60 - 40 * diaph, E.P(E.C(*YEL, 255 * min(1, diaph * 2)), 'stroke', 14))
                p = skia.Path(); p.moveTo(x, dy + 20 - 40 * diaph); p.lineTo(x - 30, dy + 70 - 40 * diaph); p.lineTo(x + 30, dy + 70 - 40 * diaph); p.close(); c.drawPath(p, E.P(E.C(*YEL, 255 * min(1, diaph * 2))))
        if flow > 0:    # air rushing up the windpipe
            for k in range(26):
                a = (T * 1.6 + k / 26) % 1; px = mx + math.sin(k * 7.1 + T * 3) * 28 * (1 - a); py = dy - 60 - a * (dy - 60 - ty + 80 * pop)
                c.drawCircle(px, py, 9 + 5 * math.sin(k), E.P(E.C(*BLUE, 200 * flow * (1 - a * .6))))
        by = my - 60 - pop * 700; bx = mx + pop * 90
        if block > 0:
            c.drawOval(skia.Rect.MakeXYWH(bx - 34, by - 26, 68, 52), E.P(E.C(*BITE, 255 * block)))
            c.drawOval(skia.Rect.MakeXYWH(bx - 34, by - 26, 68, 52), E.P(E.C(60, 35, 20, 255 * block), 'stroke', 5))
            if pop == 0: E.glow(c, bx, by, 90, (255, 60, 50), .55 * block * (.6 + .4 * math.sin(T * 8)))
    return sk(img, f)
def cork(c, x, y, s, u, a=1.0):
    """a bottle with its cork popping out on u 0..1"""
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x - 70 * s, y, 140 * s, 260 * s), 40 * s, 40 * s), E.P(E.C(60, 130, 90, 230 * a)))
    c.drawRect(skia.Rect.MakeXYWH(x - 30 * s, y - 120 * s, 60 * s, 140 * s), E.P(E.C(60, 130, 90, 230 * a)))
    cy = y - 150 * s - 260 * s * eout(u); c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x - 26 * s, cy, 52 * s, 60 * s), 10, 10), E.P(E.C(200, 150, 90, 255 * a)))
    if u > 0:
        for k in range(7):
            ang = math.radians(-70 + k * 23); r = 90 * s * eout(u)
            c.drawLine(x + math.sin(ang) * 30 * s, y - 120 * s - math.cos(ang) * 30 * s, x + math.sin(ang) * (30 * s + r), y - 120 * s - math.cos(ang) * (30 * s + r), E.P(E.C(*WHITE, 220 * a * (1 - u * .5)), 'stroke', 6))
def switch_card(T, u):
    img = blur(kb('back', .5, 1.1, 1.12), 8) * .33
    def f(c):
        for k, (t1, t2, col) in enumerate([('5 BACK', 'BLOWS', ORANGE), ('5 BELLY', 'THRUSTS', YEL)]):
            g = eout(clamp(u * 3 - k * .5)); x = 110 + k * 450
            c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, 600, 410, 320), 40, 40), E.P(E.C(14, 20, 30, 235 * g)))
            c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, 600, 410, 320), 40, 40), E.P(E.C(*col, 255 * g), 'stroke', 7))
            text(c, t1, x + 205, 740, 76, WHITE, g); text(c, t2, x + 205, 830, 60, col, g)
        g = eout(clamp(u * 3 - 1.2)); a_ = T * 3
        for s in (-1, 1):
            p = skia.Path(); p.addArc(skia.Rect.MakeXYWH(390, 420 if s < 0 else 860, 300, 220), 200 if s < 0 else 20, 140); c.drawPath(p, E.P(E.C(*WHITE, 230 * g), 'stroke', 10))
        text(c, 'REPEAT', 540, 1060, 60, GREY, g)
    return sk(img, f)
def year_card(T, u):
    img = blur(kb('relief', .5, 1.1, 1.12), 8) * .3
    def f(c):
        g = eout(clamp(u * 2.5)); panel(c, 140, 520 + 50 * (1 - g), 800, 560, g)
        text(c, 'THE HEIMLICH', 540, 650 + 50 * (1 - g), 70, WHITE, g); text(c, 'MANEUVER', 540, 730 + 50 * (1 - g), 70, WHITE, g)
        g2 = eout(clamp(u * 2.5 - .9)); text(c, '1974', 540, 950, 200 * (.8 + .2 * g2), YEL, g2)
    return sk(img, f)
def news(T, u, z=1.0, stamp=0.0, cx=.5, cy=.45):
    img = blur(kb('dinner', .5, 1.15, 1.18), 10) * .28
    def f(c):
        c.save(); c.translate(cx * W, cy * H); c.scale(z, z); c.rotate(-3 + 2 * u); c.translate(-540, -860)
        c.drawRect(skia.Rect.MakeXYWH(120, 420, 840, 880), E.P(E.C(236, 230, 214, 255)))
        c.drawRect(skia.Rect.MakeXYWH(120, 420, 840, 880), E.P(E.C(90, 80, 60, 255), 'stroke', 4))
        f_ = font(46); col = E.P(E.C(30, 28, 24, 255))
        c.drawString('CINCINNATI · MAY 2016', 170, 500, f_, col); c.drawLine(160, 525, 920, 525, E.P(E.C(30, 28, 24, 255), 'stroke', 4))
        for k, ln in enumerate(['AT 96, DR. HEIMLICH', 'SAVES A CHOKING', 'WOMAN WITH HIS', 'OWN MOVE']):
            c.drawString(ln, 170, 620 + k * 92, font(78), col)
        for k in range(9): c.drawRect(skia.Rect.MakeXYWH(170, 1000 + k * 30, 740 - (k % 3) * 90, 12), E.P(E.C(150, 140, 120, 255)))
        c.restore()
        if stamp > 0:
            g = eout(stamp); c.save(); c.translate(760, 1220); c.rotate(-12); c.scale(1.6 - .6 * g, 1.6 - .6 * g)
            c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(-200, -80, 400, 160), 24, 24), E.P(E.C(*GREEN, 255 * g), 'stroke', 12))
            text(c, 'SHE WAS 87', 0, 25, 64, GREEN, g); c.restore()
    return sk(img, f)
def bite_fly(img, T, x, y, u, a=1.0, dirx=-1):
    """the bite of turkey shooting out of Kai's mouth (u 0..1)"""
    if u <= 0 or u > 1.2: return img
    def f(c):
        px = x + dirx * 650 * u; py = y - 650 * u + 520 * u * u; r = 30
        c.save(); c.translate(px, py); c.rotate(u * 520)
        c.drawOval(skia.Rect.MakeXYWH(-r * 1.3, -r, r * 2.6, r * 2), E.P(E.C(*BITE, 255 * a))); c.drawOval(skia.Rect.MakeXYWH(-r * 1.3, -r, r * 2.6, r * 2), E.P(E.C(70, 45, 25, 255), 'stroke', 5))
        c.restore()
        for k in range(5):
            uu = u - k * .03
            if uu > 0: c.drawCircle(x + dirx * 650 * uu, y - 650 * uu + 520 * uu * uu, 18 - k * 3, E.P(E.C(*WHITE, 80 - 15 * k)))
    return sk(img, f)
def arrow(c, x0, y0, x1, y1, col, a=1.0, w=14):
    c.drawLine(x0, y0, x1, y1, E.P(E.C(*col, 255 * a), 'stroke', w)); ang = math.atan2(y1 - y0, x1 - x0)
    p = skia.Path(); p.moveTo(x1 + math.cos(ang) * 30, y1 + math.sin(ang) * 30)
    p.lineTo(x1 + math.cos(ang + 2.4) * 40, y1 + math.sin(ang + 2.4) * 40); p.lineTo(x1 + math.cos(ang - 2.4) * 40, y1 + math.sin(ang - 2.4) * 40); p.close(); c.drawPath(p, E.P(E.C(*col, 255 * a)))

# ---------------------------------------------------------------- scenes
def hook_shot(t, T, z0=1.0, z1=1.12, tint=.25, mute=1.0):
    img = kb('hook', clamp(t / 3.0), z0, z1, (.5, .45), (.5, .43))
    fx, fy, z = sp('hook', 'face'); hx, hy, _ = sp('hook', 'hands')
    img = face_tint(img, fx, fy, 260 * z, (90, 120, 255), tint)
    img = rings(img, T, hx, hy, RED, .9)
    img = shift(img, 3 * math.sin(T * 31), 2 * math.cos(T * 27))      # trembling
    if mute > 0:
        mx, my, _ = sp('hook', 'mouth')
        img = sk(img, lambda c: mute_icon(c, min(W - 130, mx + 270), my + 40, .85, mute))
    return img
def S0(t, T): return flash(hook_shot(t, T), t + .2, 60, 6)

def S1(t, T):
    c = wx('kai') - .1
    if t < c: return kb('dinner', t / c, 1.0, 1.1, (.5, .55), (.5, .5))
    u = t - c; return whip(ptalk('cu_kai', T, u / (D + PAD - c), 1.0, 1.1, (.5, .45), (.5, .42), .012), u)

def S2(t, T): return ptalk('cu_leo', T, t / (D + PAD), 1.0, 1.08, (.55, .45), (.52, .43), .012)

def S3(t, T):
    c = wx('thats') - .15
    if t < c: return jolt(kb('choke', t / c, 1.0, 1.25, (.5, .5), (.42, .45)), t, [.25], 22)
    return whip(hook_shot(t - c, T, 1.1, 1.2, .2, 0), t - c)

def S4(t, T): return cough_card(T, clamp(t / 2.0))

def S5(t, T):
    c = wx('airway') - .15
    if t < c:
        n = 0
        for k, w in enumerate(('cough', 'talk', 'breathe')):
            if t > wx(w) - .1: n = k + clamp((t - wx(w) + .1) / .3)
        img = blur(hook_shot(t, T, 1.15, 1.22, .35, 0), 2) * .8
        return sk(img, lambda cv: cant_list(cv, n))
    u = t - c; return whip(anat_air(T, u / (D + PAD - c), block=1.0), u)

def S6(t, T): return corner_timer(deaths(T, clamp(t / 2.6)), T)

def S7(t, T):
    c = wx('ive') - .15
    if t < c: return corner_timer(ptalk('cu_mia', T, t / c, 1.0, 1.08, (.45, .45), (.45, .43), .014), T)
    u = t - c; img = kb('call', u / (D + PAD - c), 1.0, 1.08, (.45, .45), (.43, .45))
    px, py, z = sp('call', 'phone')
    img = sk(img, lambda cv: (cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(px - 20, py - 260, 330, 130), 30, 30), E.P(E.C(14, 20, 30, 230))),
                              text(cv, '9-1-1', px + 145, py - 172, 72, GREEN, 1)))
    return corner_timer(whip(img, u), T)

def S8(t, T): return corner_timer(four_min(T, clamp(t / (D - .3))), T)

def S9(t, T):
    s = wx('five'); hits = [s + .1 + k * (wx('blades', True) - s - .2) / 4.5 for k in range(5)]
    c = wx('between') - .1
    if t < c: img = kb('back', t / c, 1.0, 1.08, (.5, .5), (.48, .48))
    else: img = whip(kb('back', (t - c) / (D + PAD - c), 1.3, 1.38, (.38, .45), (.38, .45)), t - c)
    img = jolt(img, t, hits, 20, False)
    n = sum(1 for h in hits if t >= h)
    if n:
        bx, by, z = sp('back', 'blow'); h0 = max(h for h in hits if t >= h)
        img = flash(img, t - h0, 50, 10)
        img = sk(img, lambda cv: (E.glow(cv, bx, by, 140, (255, 200, 80), .7 * math.exp(-(t - h0) * 6)), text(cv, f'{n}', bx + 10, by - 160, 120, YEL, 1)))
    return corner_timer(img, T)

def S10(t, T):
    k = clamp((t - wx('blue') + .6) / 1.2)
    img = kb('hook', t / (D + PAD), 1.35, 1.5, (.5, .5), (.5, .52))
    fx, fy, z = sp('hook', 'mouth'); img = face_tint(img, fx, fy, 160 * z, (70, 110, 255), .35 + .55 * k)
    img = shift(img, 3 * math.sin(T * 31), 2 * math.cos(T * 27))
    return corner_timer(img, T)

def S11(t, T):
    c1 = wx('a') - .15; c2 = wx('pulled') - .1
    if t < c1: img = kb('thrust', t / c1, 1.0, 1.1, (.5, .5), (.5, .52))
    elif t < c2: img = whip(torso(T, clamp((t - c1) / 1.6), 0), t - c1)
    else:
        u = t - c2; img = torso(T, clamp(u / 1.3), 1)
    return corner_timer(img, T)

def S12(t, T):
    c = wx('like') - .15
    if t < c:
        u = t / c; return anat_air(T, u, flow=clamp(t / .6), pop=0, block=1.0, diaph=clamp(t / .5))
    u = t - c; img = anat_air(T, .9, flow=1.0, pop=clamp(u / .8), block=1.0, diaph=1.0)
    img = blur(img, 4) * .45
    return whip(sk(img, lambda cv: (panel(cv, 300, 560, 480, 720), cork(cv, 540, 940, 1.2, clamp((u - .25) / .5)))), u)

def S13(t, T):
    s = wx('third') - .1; shot = wx('shot')
    hits = [.2, (s + .2) / 2, s]
    img = kb('thrust', t / (D + PAD), 1.1, 1.25, (.45, .5), (.45, .45))
    img = jolt(img, t, [h for h in hits if h < shot], 22)
    for k, h in enumerate(hits):
        if t >= h:
            fx, fy, z = sp('thrust', 'fist')
            img = sk(img, lambda cv, k=k: text(cv, f'{k + 1}', fx - 160, fy - 40, 120, YEL, clamp(1 - (t - h) * .4)))
    mx, my, z = sp('thrust', 'mouth')
    if t >= shot - .1: img = flash(img, t - shot + .1, 90, 7)
    return bite_fly(img, T, mx, my, clamp((t - shot + .1) / .7))

def S14(t, T): return ptalk('relief', T, t / (D + PAD), 1.0, 1.1, (.5, .45), (.5, .42), .012)

def S15(t, T):
    c = wx('if') - .15
    if t < c: return switch_card(T, clamp(t / 1.6))
    u = t - c; img = kb('floor', u / (D + PAD - c), 1.0, 1.12, (.5, .55), (.47, .55))
    img = jolt(img, u, [k * .5 + .3 for k in range(8)], 8)
    return whip(img, u)

def S16(t, T): return ptalk('cu_leo', T, t / (D + PAD), 1.12, 1.2, (.55, .45), (.55, .43), .014)

def S17(t, T):
    c = wx('thrust') - .1
    img = kb('chair', t / (D + PAD), 1.0, 1.25, (.45, .5), (.43, .5))
    if t >= c:
        img = jolt(img, t, [c + .2, c + .9, c + 1.6], 16)
        bx, by, z = sp('chair', 'belly'); rx, ry, _ = sp('chair', 'rail')
        img = sk(img, lambda cv: arrow(cv, bx - 220, by - 40, bx - 30, by, RED, clamp((t - c) * 3)))
    return img

def S18(t, T):
    c = wx('doctor') - .15
    if t < c: return kb('relief', t / c, 1.1, 1.2, (.5, .45), (.5, .45))
    return whip(year_card(T, clamp((t - c) / 1.8)), t - c)

def S19(t, T):
    u = clamp(t / (D + PAD)); return news(T, u, .85 + .15 * eout(clamp(t / 1.2)) + .08 * u)

def S20(t, T):
    s = clamp((t - .3) / .5)
    return news(T, 1, 1.15 + .1 * clamp(t / (D + PAD)), s, .5, .5)

def S21(t, T):
    c = (D + PAD) - .9
    if t < c:
        c1 = wx('one') - .1
        if t < c1: return kb('relief', t / c1, 1.0, 1.1, (.5, .5), (.5, .48))
        return whip(kb('dinner', (t - c1) / (c - c1), 1.05, 1.2, (.5, .5), (.5, .45)), t - c1)
    u = t - c; return whip(hook_shot(0, T), u, vertical=True)

# ---------------------------------------------------------------- overlays
def overlays():
    wo = lambda *a, **k: wx(*a, **k) - XF
    o = []
    if idx == 0: o += [{'type': 'hook', 'text': 'REAL CHOKING|IS SILENT', 'y': .11}]
    if idx == 1: o += [{'type': 'label', 'text': 'SATURDAY NIGHT', 'pos': [.5, .12], 'color': YEL, 'from': .2, 'to': wo('kai') - .2},
                       {'type': 'label', 'text': 'THANKSGIVING LEFTOVERS', 'pos': [.5, .12], 'color': WHITE, 'from': wo('kai')}]
    if idx == 3: o += [{'type': 'label', 'text': 'UNIVERSAL CHOKING SIGN', 'pos': [.5, .12], 'color': RED, 'from': wo('thats')}]
    if idx == 5: o += [{'type': 'label', 'text': 'AIRWAY BLOCKED', 'pos': [.5, .12], 'color': RED, 'from': wo('airway')}]
    if idx == 6: o += [{'type': 'label', 'text': 'EVERY YEAR IN THE US', 'pos': [.5, .12], 'color': WHITE, 'from': .2},
                       {'type': 'badge', 'value': '~1', 'unit': 'DEATH EVERY 90 MINUTES', 'pos': [.5, .185], 'from': 1.6, 'size': 70}]
    if idx == 8: o += [{'type': 'label', 'text': 'BRAIN DAMAGE CAN START', 'pos': [.5, .12], 'color': RED, 'from': wo('brain') - .1},
                       {'type': 'badge', 'value': '~4', 'unit': 'MINUTES', 'pos': [.5, .185], 'from': wo('four') - .1, 'size': 80}]
    if idx == 9: o += [{'type': 'label', 'text': '5 BACK BLOWS', 'pos': [.5, .12], 'color': YEL, 'from': wo('five') - .1},
                       {'type': 'label', 'text': 'HEEL OF THE HAND', 'pos': [.5, .175], 'color': WHITE, 'from': wo('between') - .1}]
    if idx == 10: o += [{'type': 'label', 'text': 'LIPS TURNING BLUE', 'pos': [.5, .12], 'color': BLUE, 'from': wo('lips') - .1}]
    if idx == 11: o += [{'type': 'label', 'text': '5 ABDOMINAL THRUSTS', 'pos': [.5, .12], 'color': YEL, 'from': .2}]
    if idx == 12: o += [{'type': 'label', 'text': 'AIR FORCED UP', 'pos': [.5, .12], 'color': BLUE, 'from': .3, 'to': wo('like') - .2},
                        {'type': 'label', 'text': 'LIKE A CORK', 'pos': [.5, .12], 'color': YEL, 'from': wo('like')}]
    if idx == 14: o += [{'type': 'label', 'text': 'AIRWAY CLEAR', 'pos': [.5, .12], 'color': GREEN, 'from': .2}]
    if idx == 15: o += [{'type': 'label', 'text': 'PASSED OUT? CALL 911 + CPR', 'pos': [.5, .12], 'color': RED, 'from': wo('if')}]
    if idx == 17: o += [{'type': 'label', 'text': 'ALONE? USE A CHAIR BACK', 'pos': [.5, .12], 'color': YEL, 'from': .2}]
    if idx == 18: o += [{'type': 'label', 'text': 'THE TWIST', 'pos': [.5, .12], 'color': YEL, 'from': .1}]
    if idx == 19: o += [{'type': 'badge', 'value': '96', 'unit': 'YEARS OLD', 'pos': [.5, .13], 'from': wo('ninetysix') - .1, 'size': 80}]
    if idx == 20: o += [{'type': 'label', 'text': 'IT WORKED RIGHT AWAY', 'pos': [.5, .12], 'color': GREEN, 'from': wo('worked') - .1}]
    if idx == 21: o += [{'type': 'cta', 'text': 'FOLLOW FOR MORE STORIES', 'from': .2}]
    return o

FN = globals()[f'S{idx}']
os.makedirs(f'{ROOT}/s{idx}', exist_ok=True)
if len(sys.argv) > 2:
    for ts in sys.argv[2:]:
        t = float(ts); img = FN(t, t + T0); cv2.imwrite(f'{ROOT}/still_{idx}_{ts}.jpg', np.clip(img, 0, 255).astype(np.uint8)[::2, ::2], [cv2.IMWRITE_JPEG_QUALITY, 85])
    sys.exit()
for f in (range(1, NF + 1) if not os.environ.get('META_ONLY') else []):
    t = (f - 1) / FPS; img = FN(t, t + T0)
    cv2.imwrite(f'{ROOT}/s{idx}/f_{f:04d}.png', np.clip(img, 0, 255).astype(np.uint8), [cv2.IMWRITE_PNG_COMPRESSION, 1])
json.dump({'frames': NF, 'overlays': overlays()}, open(f'{ROOT}/s{idx}/meta.json', 'w'))
print('scene', idx, 'frames', NF)
