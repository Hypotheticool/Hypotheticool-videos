"""Hypotheticool pro renderer: shared look (space backdrop, captions, characters, black hole, audio, encode).
Topic scripts import this, define SCENES = [(draw_fn, narration), ...] and call build(SCENES, name)."""
import math, os, sys, subprocess, re
import numpy as np, skia

W, H, FPS = int(os.environ.get('HC_W', 1080)), int(os.environ.get('HC_H', 1920)), 30
FONT_FILE = '/usr/share/fonts/truetype/google-fonts/ofl/anton/Anton-Regular.ttf'
TTS_DIR = os.environ.get('TTS_DIR', '/home/claude/tts')
VOICE, VOICE_SPEED = 'am_puck', 1.0
XF = 0.35                     # crossfade between scenes (s)
LEAD, GAP = 0.18, 0.30        # silence before each line / after it
rng = np.random.default_rng(11)
TF = skia.Typeface.MakeFromFile(FONT_FILE)

# ---------------------------------------------------------------- helpers
def col(r, g, b, a=1.0): return skia.Color4f(r / 255, g / 255, b / 255, a)
def C(r, g, b, a=255): return skia.Color(int(r), int(g), int(b), int(max(0, min(255, a))))
def ease(u): u = max(0.0, min(1.0, u)); return u * u * (3 - 2 * u)
def eio(u): u = max(0.0, min(1.0, u)); return 4 * u ** 3 if u < .5 else 1 - (-2 * u + 2) ** 3 / 2
def eout(u): u = max(0.0, min(1.0, u)); return 1 - (1 - u) ** 3
def lerp(a, b, u): return a + (b - a) * u

def P(color=None, style='fill', w=0, blur=0, add=False, shader=None, cap=True, alpha=None):
    p = skia.Paint(AntiAlias=True)
    if color is not None: p.setColor(color)
    if shader is not None: p.setShader(shader)
    if style == 'stroke':
        p.setStyle(skia.Paint.kStroke_Style); p.setStrokeWidth(w)
        if cap: p.setStrokeCap(skia.Paint.kRound_Cap); p.setStrokeJoin(skia.Paint.kRound_Join)
    if blur: p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, blur))
    if add: p.setBlendMode(skia.BlendMode.kPlus)
    if alpha is not None: p.setAlphaf(alpha)
    return p

def radial(x, y, r, colors, pos=None):
    return skia.GradientShader.MakeRadial((x, y), max(r, 0.1), colors, pos)
def linear(p0, p1, colors, pos=None):
    return skia.GradientShader.MakeLinear([p0, p1], colors, pos)

def glow(c, x, y, r, color_rgb, a=1.0):
    r_, g_, b_ = color_rgb
    c.drawCircle(x, y, r, P(shader=radial(x, y, r, [C(r_, g_, b_, 255 * a), C(r_, g_, b_, 90 * a), C(r_, g_, b_, 0)], [0, .35, 1]), add=True))

# ---------------------------------------------------------------- backdrop
def _nebula():
    w, h = 1400, 2400
    yy, xx = np.mgrid[0:h:4, 0:w:4].astype(np.float32)
    img = np.zeros(xx.shape + (3,), np.float32)
    blobs = [((300, 500), 420, (70, 20, 120)), ((1100, 900), 380, (20, 40, 110)), ((500, 1700), 520, (90, 25, 90)),
             ((1150, 2000), 420, (15, 70, 110)), ((700, 1100), 300, (40, 15, 80))]
    for (bx, by), r, cl in blobs:
        g = np.exp(-((xx - bx) ** 2 + (yy - by) ** 2) / (2 * r * r))
        img += g[..., None] * np.array(cl, np.float32)
    n = np.zeros(xx.shape, np.float32)                      # cheap value noise for wisps
    for s, amp in [(64, .5), (32, .3), (16, .2)]:
        small = rng.random((xx.shape[0] // s + 2, xx.shape[1] // s + 2)).astype(np.float32)
        n += amp * np.kron(small, np.ones((s, s), np.float32))[:xx.shape[0], :xx.shape[1]]
    img *= (0.55 + 0.9 * n)[..., None]
    base = np.array([8, 6, 22], np.float32)
    img = np.clip(img + base, 0, 255).astype(np.uint8)
    a = np.dstack([img[..., 2], img[..., 1], img[..., 0], np.full(img.shape[:2], 255, np.uint8)])  # BGRA
    im = skia.Image.fromarray(np.ascontiguousarray(a), colorType=skia.kBGRA_8888_ColorType)
    s = skia.Surface(w, h); cv = s.getCanvas()
    p = skia.Paint(); p.setImageFilter(skia.ImageFilters.Blur(22, 22))
    cv.drawImageRect(im, skia.Rect(0, 0, w, h), skia.SamplingOptions(skia.FilterMode.kLinear), p)
    return s.makeImageSnapshot()
NEB = _nebula()
STARS = [(rng.uniform(-200, W + 200), rng.uniform(-200, H + 200), rng.choice([1, 1.4, 1.8, 2.4, 3.2], p=[.4, .3, .17, .09, .04]),
          rng.uniform(0, 6.3), rng.uniform(.5, 1.0)) for _ in range(650)]

def backdrop(c, T, par=(0, 0), zoom=1.0, dim=1.0):
    c.clear(C(6, 5, 18))
    c.save(); c.translate(W / 2, H / 2); c.scale(zoom * 1.0, zoom * 1.0); c.translate(-W / 2 + par[0] * .3, -H / 2 + par[1] * .3)
    p = skia.Paint(); p.setAlphaf(0.5 * dim)
    c.drawImageRect(NEB, skia.Rect(-160, -240, W + 160, H + 240), skia.SamplingOptions(skia.FilterMode.kLinear), p)
    c.restore()
    c.save(); c.translate(W / 2, H / 2); c.scale(zoom, zoom); c.translate(-W / 2 + par[0], -H / 2 + par[1])
    for x, y, s, ph, b in STARS:
        a = b * (0.65 + 0.35 * math.sin(T * 1.7 + ph)) * dim
        c.drawCircle(x, y, s, P(C(235, 240, 255, 255 * a)))
        if s > 2.5:
            glow(c, x, y, s * 7, (150, 170, 255), .35 * a)
            st = P(C(220, 230, 255, 110 * a), 'stroke', 1.2)
            c.drawLine(x - s * 6, y, x + s * 6, y, st); c.drawLine(x, y - s * 6, x, y + s * 6, st)
    c.restore()

def vignette(c):
    c.drawRect(skia.Rect(0, 0, W, H), P(shader=radial(W / 2, H * .46, H * .78, [C(0, 0, 0, 0), C(0, 0, 0, 0), C(0, 0, 8, 190)], [0, .55, 1])))

# ---------------------------------------------------------------- black hole (lensed accretion disk)
PARTS = [(rng.uniform(1.55, 4.3), rng.uniform(0, 2 * math.pi), rng.uniform(.05, .22), rng.uniform(1.5, 4.5)) for _ in range(520)]
def disk_rgb(k):            # k = radius / R : hot white-gold inside, deep orange-red outside
    u = min(1, max(0, (k - 1.5) / 2.8))
    return (255, int(lerp(225, 105, u ** .8)), int(lerp(150, 25, u ** .6)))

def black_hole(c, cx, cy, R, T, tilt=.24, spin=1.0, a=1.0, roll=-8):
    c.save(); c.translate(cx, cy); c.rotate(roll)
    c.drawCircle(0, 0, R * 5.5, P(shader=radial(0, 0, R * 5.5, [C(0, 0, 0, 235 * a), C(0, 0, 0, 160 * a), C(0, 0, 0, 0)], [0, .45, 1])))
    glow(c, 0, 0, R * 5.0, (255, 130, 40), .22 * a)
    def disk(half):  # half: -1 = far (upper) side, +1 = near (lower) side
        c.save(); c.scale(1, tilt)
        c.clipRect(skia.Rect(-R * 6, -R * 6 if half < 0 else 0, R * 6, 0 if half < 0 else R * 6))
        for i in range(26):  # smooth body of the disk: blurred rings
            k = 1.55 + i * .11; r_, g_, b_ = disk_rgb(k)
            fall = (1 - (k - 1.55) / 3.0) ** 1.6
            sh = skia.GradientShader.MakeSweep(0, 0, [C(r_, g_, b_, 255 * fall * a), C(r_, g_ * .7, b_ * .5, 90 * fall * a),
                                                       C(r_, g_, b_, 255 * fall * a)], [0, .5, 1])
            m = skia.Matrix(); m.setRotate(180)
            p = P(style='stroke', w=R * .16, blur=R * .05, add=True, shader=sh.makeWithLocalMatrix(m)); p.setAlphaf(.42)
            c.drawCircle(0, 0, k * R, p)
        for k, th0, ln, w in PARTS:  # orbiting streaks (Keplerian speed), brighter on the approaching (left) side
            th = th0 + spin * 1.1 * (k / 1.6) ** -1.5 * T
            s = math.sin(th)
            if (s < 0) != (half < 0): continue
            dop = .45 + .55 * (0.5 - 0.5 * math.cos(th))
            r_, g_, b_ = disk_rgb(k)
            rect = skia.Rect(-k * R, -k * R, k * R, k * R)
            c.drawArc(rect, math.degrees(th), math.degrees(ln), False, P(C(r_, min(255, g_ + 30), min(255, b_ + 40), 200 * dop * a), 'stroke', w * R / 60, add=True))
        c.restore()
    disk(-1)
    # gravitationally lensed image of the far side of the disk, arching over (and under) the shadow
    for i in range(10):
        k = 1.12 + i * .045; r_, g_, b_ = disk_rgb(1.6 + i * .25)
        rect = skia.Rect(-k * R * 1.02, -k * R, k * R * 1.02, k * R)
        c.drawArc(rect, 180, 180, False, P(C(r_, g_, b_, (170 - i * 14) * a), 'stroke', R * .07, blur=R * .025, add=True))
    for i in range(4):
        k = 1.06 + i * .03
        c.drawArc(skia.Rect(-k * R, -k * R, k * R, k * R), 0, 180, False, P(C(255, 170, 90, (90 - i * 20) * a), 'stroke', R * .035, add=True))
    c.drawCircle(0, 0, R * 1.02, P(C(255, 236, 200, 230 * a), 'stroke', R * .035, blur=R * .02, add=True))   # photon ring
    c.drawCircle(0, 0, R, P(C(0, 0, 0, 255 * a)))                                                            # shadow
    c.drawCircle(0, 0, R * .98, P(shader=radial(0, 0, R, [C(0, 0, 0, 255 * a), C(0, 0, 0, 255 * a), C(25, 8, 0, 255 * a)], [0, .85, 1])))
    disk(+1)
    c.restore()

# ---------------------------------------------------------------- astronaut (layered, shaded)
SUIT_HI, SUIT_MID, SUIT_LO = C(250, 251, 255), C(214, 220, 236), C(150, 158, 186)
OUTLINE = C(20, 22, 48, 230)
def _limb(c, pts, w, colr=SUIT_MID):
    path = skia.Path(); path.moveTo(*pts[0])
    for q in pts[1:]: path.lineTo(*q)
    c.drawPath(path, P(OUTLINE, 'stroke', w + 7))
    c.drawPath(path, P(colr, 'stroke', w))
    c.drawPath(path, P(C(255, 255, 255, 120), 'stroke', w * .35))

def astronaut(c, x, y, s=1.0, rot=0, stretch=1.0, tint=(1, 1, 1), alpha=1.0, wave=0.0, T=0.0, visor_reflect=(255, 150, 60)):
    lp = skia.Paint(); lp.setAlphaf(alpha)
    tr, tg, tb = tint
    lp.setColorFilter(skia.ColorFilters.Matrix([tr, 0, 0, 0, 0, 0, tg, 0, 0, 0, 0, 0, tb, 0, 0, 0, 0, 0, 1, 0]))
    c.saveLayer(None, lp)
    c.translate(x, y); c.rotate(rot); c.scale(s / math.sqrt(stretch), s * stretch)
    sw = math.sin(T * 2.2) * 6
    # tether / backpack
    c.drawRoundRect(skia.Rect(-78, -70, 40, 70), 22, 22, P(OUTLINE))
    c.drawRoundRect(skia.Rect(-74, -66, 36, 66), 19, 19, P(shader=linear((-74, 0), (36, 0), [C(120, 128, 160), C(190, 196, 220)])))
    c.drawRoundRect(skia.Rect(-66, -40, -44, 30), 8, 8, P(C(90, 96, 130)))
    # legs (behind body)
    _limb(c, [(-18, 70), (-30, 125 + sw), (-26, 170 + sw)], 40)
    _limb(c, [(22, 70), (38, 122 - sw), (46, 166 - sw)], 40)
    for bx, by in [(-26, 170 + sw), (46, 166 - sw)]:
        c.drawRoundRect(skia.Rect(bx - 28, by - 8, bx + 30, by + 26), 12, 12, P(OUTLINE))
        c.drawRoundRect(skia.Rect(bx - 24, by - 4, bx + 26, by + 22), 10, 10, P(C(90, 98, 140)))
    # back arm
    _limb(c, [(-40, -30), (-78, 18 - sw), (-70, 64 - sw)], 34)
    # torso
    body = skia.RRect.MakeRectXY(skia.Rect(-62, -78, 62, 92), 44, 44)
    c.drawRRect(body, P(OUTLINE, 'stroke', 7))
    c.drawRRect(body, P(shader=linear((-62, 0), (62, 0), [SUIT_HI, SUIT_MID, SUIT_LO], [0, .55, 1])))
    c.drawRoundRect(skia.Rect(-34, -12, 30, 40), 10, 10, P(C(60, 70, 120)))          # chest unit
    for i, cl in enumerate([C(255, 80, 90), C(255, 210, 60), C(80, 230, 160)]):
        c.drawCircle(-18 + i * 17, 4, 5.5, P(cl)); glow(c, -18 + i * 17, 4, 12, (255, 255, 255), .25)
    c.drawRect(skia.Rect(-26, 22, 22, 30), P(C(120, 140, 220)))
    c.drawRoundRect(skia.Rect(-60, 62, 60, 80), 8, 8, P(C(170, 176, 204)))             # belt
    # front arm (waving)
    ang = math.radians(-40 - 50 * wave * (0.5 + 0.5 * math.sin(T * 6)))
    ex, ey = 70 + 44 * math.cos(ang) * .3, -10 + 50 * math.sin(ang)
    _limb(c, [(44, -40), (78, -6), (ex + 30, ey - 10)], 34)
    c.drawCircle(ex + 30, ey - 10, 22, P(OUTLINE)); c.drawCircle(ex + 30, ey - 10, 18, P(C(170, 176, 210)))
    # helmet
    c.drawCircle(0, -140, 80, P(OUTLINE))
    c.drawCircle(0, -140, 75, P(shader=radial(-25, -170, 120, [SUIT_HI, SUIT_MID, SUIT_LO], [0, .6, 1])))
    visor = skia.RRect.MakeRectXY(skia.Rect(-56, -186, 60, -102), 40, 38)
    c.drawRRect(visor, P(C(10, 12, 30)))
    vr, vg, vb = visor_reflect
    c.drawRRect(visor, P(shader=linear((-56, -186), (60, -102), [C(30, 40, 90), C(vr * .5, vg * .4, vb * .5), C(vr, vg, vb)], [0, .6, 1])))
    c.save(); c.clipRRect(visor, True)
    c.drawOval(skia.Rect(-70, -200, 20, -150), P(C(255, 255, 255, 70)))                # sky reflection
    c.drawArc(skia.Rect(-44, -178, 30, -120), 200, 70, False, P(C(255, 255, 255, 190), 'stroke', 7))
    c.restore()
    c.drawRRect(visor, P(OUTLINE, 'stroke', 5))
    c.drawCircle(-38, -205, 9, P(C(255, 255, 255, 200)))
    c.restore()

# ---------------------------------------------------------------- spaceship (for the "far-away friend")
def spaceship(c, x, y, s=1.0, T=0.0, rot=0):
    c.save(); c.translate(x, y); c.rotate(rot); c.scale(s, s)
    fl = 1 + .15 * math.sin(T * 30) + .1 * math.sin(T * 17)
    c.drawOval(skia.Rect(-260 - 120 * fl, -26, -220, 26), P(shader=linear((-380, 0), (-220, 0), [C(80, 160, 255, 0), C(120, 200, 255, 220), C(255, 255, 255)]), add=True))
    glow(c, -230, 0, 90, (90, 170, 255), .7)
    hull = skia.Path(); hull.moveTo(-230, -48); hull.cubicTo(-60, -80, 120, -70, 230, 0); hull.cubicTo(120, 70, -60, 80, -230, 48); hull.close()
    c.drawPath(hull, P(OUTLINE, 'stroke', 8))
    c.drawPath(hull, P(shader=linear((0, -80), (0, 80), [C(240, 244, 255), C(180, 188, 214), C(110, 118, 150)], [0, .5, 1])))
    fin = skia.Path(); fin.moveTo(-170, -40); fin.lineTo(-230, -130); fin.lineTo(-120, -50); fin.close()
    c.drawPath(fin, P(C(255, 90, 110))); c.drawPath(fin, P(OUTLINE, 'stroke', 5))
    fin2 = skia.Path(); fin2.moveTo(-170, 40); fin2.lineTo(-230, 130); fin2.lineTo(-120, 50); fin2.close()
    c.drawPath(fin2, P(C(220, 60, 90))); c.drawPath(fin2, P(OUTLINE, 'stroke', 5))
    c.drawRect(skia.Rect(-120, -6, 120, 6), P(C(255, 90, 110)))
    for i in range(3):
        wx = 40 + i * 52
        c.drawCircle(wx, -14, 15, P(OUTLINE)); c.drawCircle(wx, -14, 11, P(shader=radial(wx - 3, -18, 12, [C(220, 250, 255), C(80, 190, 255)])))
    c.restore()

def clock(c, x, y, r, hand_ang, a=1.0, slow=0.0):
    glow(c, x, y, r * 1.7, (90, 220, 255), .35 * a)
    c.drawCircle(x, y, r, P(C(8, 16, 40, 220 * a)))
    c.drawCircle(x, y, r, P(C(120, 230, 255, 255 * a), 'stroke', 6))
    for i in range(12):
        t = i / 12 * 2 * math.pi
        c.drawLine(x + math.cos(t) * r * .78, y + math.sin(t) * r * .78, x + math.cos(t) * r * .9, y + math.sin(t) * r * .9, P(C(160, 240, 255, 230 * a), 'stroke', 4))
    c.drawLine(x, y, x + math.sin(hand_ang) * r * .7, y - math.cos(hand_ang) * r * .7, P(C(255, 222, 60, 255 * a), 'stroke', 7))
    c.drawCircle(x, y, 7, P(C(255, 222, 60, 255 * a)))

def star(c, x, y, r, T, a=1.0):
    glow(c, x, y, r * 3.2, (255, 170, 60), .5 * a)
    glow(c, x, y, r * 1.8, (255, 220, 120), .6 * a)
    c.drawCircle(x, y, r, P(shader=radial(x - r * .25, y - r * .25, r * 1.2, [C(255, 255, 235, 255 * a), C(255, 220, 110, 255 * a), C(255, 140, 40, 255 * a), C(200, 70, 20, 255 * a)], [0, .35, .8, 1])))
    for i in range(14):  # granulation / sunspots drifting
        th = i * 2.3 + T * .15; rr = r * (.2 + .65 * ((i * 37) % 10) / 10)
        c.drawCircle(x + math.cos(th) * rr, y + math.sin(th) * rr, r * .09, P(C(255, 255, 220, 50 * a), blur=r * .04))

def arrow(c, x0, y0, x1, y1, w, color, a=1.0):
    r_, g_, b_ = color
    ang = math.atan2(y1 - y0, x1 - x0); hl = w * 2.4
    bx, by = x1 - math.cos(ang) * hl, y1 - math.sin(ang) * hl
    c.drawLine(x0, y0, bx, by, P(C(0, 0, 0, 150 * a), 'stroke', w + 10))
    c.drawLine(x0, y0, bx, by, P(C(r_, g_, b_, 255 * a), 'stroke', w))
    head = skia.Path(); head.moveTo(x1, y1)
    head.lineTo(bx + math.cos(ang + 1.57) * w * 1.3, by + math.sin(ang + 1.57) * w * 1.3)
    head.lineTo(bx + math.cos(ang - 1.57) * w * 1.3, by + math.sin(ang - 1.57) * w * 1.3); head.close()
    c.drawPath(head, P(C(0, 0, 0, 150 * a), 'stroke', 10)); c.drawPath(head, P(C(r_, g_, b_, 255 * a)))

# ---------------------------------------------------------------- captions (word-synced chunks)
HL_COLOR, TXT_COLOR = C(255, 222, 40), C(255, 255, 255)
def chunk_words(text, words_t):
    words = text.split(); chunks = []; cur = []
    for i, w in enumerate(words):
        cur.append(i)
        if len(cur) >= 3 or len(' '.join(words[j] for j in cur)) > 15 or re.search(r'[,.!?…]$', w): chunks.append(cur); cur = []
    if cur: chunks.append(cur)
    return [([words[j] for j in ch], words_t[ch[0]][0], words_t[ch[-1]][1]) for ch in chunks]

def caption(c, words, t_in, t, hl, y=1330):
    pop = eout((t - t_in) / .16); sc = .82 + .18 * pop + .06 * math.sin(min(1, (t - t_in) / .16) * math.pi)
    size = 112 if H > W else 74
    font = skia.Font(TF, size)
    txt = [w.upper() for w in words]
    widths = [font.measureText(w + ' ') for w in txt]; total = sum(widths) - font.measureText(' ')
    if total > W * .89:
        size = size * W * .89 / total; font = skia.Font(TF, size)
        widths = [font.measureText(w + ' ') for w in txt]; total = sum(widths) - font.measureText(' ')
    c.save(); c.translate(W / 2, y); c.scale(sc, sc)
    x = -total / 2
    for w, wd in zip(txt, widths):
        key = re.sub(r'[^A-Z0-9-]', '', w) in hl
        c.drawString(w, x + 6, 8, font, P(C(0, 0, 0, 150 * pop), blur=8))
        c.drawString(w, x, 0, font, P(C(0, 0, 0, 255 * pop), 'stroke', 16))
        c.drawString(w, x, 0, font, P(HL_COLOR if key else TXT_COLOR, alpha=pop))
        x += wd
    c.restore()

# ---------------------------------------------------------------- audio
def tts_lines(lines):
    from kokoro_onnx import Kokoro
    k = Kokoro(f'{TTS_DIR}/kokoro-v1.0.onnx', f'{TTS_DIR}/voices-v1.0.bin')
    out = []
    for ln in lines:
        a, sr = k.create(ln, voice=VOICE, speed=VOICE_SPEED, lang='en-us')
        a = np.asarray(a, np.float32); env = np.abs(a) > 0.01
        i0 = max(0, np.argmax(env) - int(.03 * sr)); i1 = min(len(a), len(a) - np.argmax(env[::-1]) + int(.08 * sr))
        out.append((a[i0:i1], sr))
    return out

def word_times(line, dur):
    words = line.split(); wts = [len(re.sub(r'[^\w]', '', w)) + 2.2 + (2.5 if re.search(r'[,.!?…]$', w) else 0) for w in words]
    tot = sum(wts); t = 0; res = []
    for w in wts: res.append((t / tot * dur, (t + w) / tot * dur)); t += w
    return res

def music_bed(n, sr, cuts, total):
    t = np.arange(n) / sr; out = np.zeros(n, np.float32)
    chords = [(110, 130.8, 164.8, 220), (87.3, 110, 130.8, 174.6), (98, 123.5, 146.8, 196), (82.4, 103.8, 123.5, 164.8)]
    seg = 4.0
    for i in range(int(total / seg) + 1):
        ch = chords[i % 4]; s0, s1 = int(i * seg * sr), min(n, int((i + 1) * seg * sr + 1.0 * sr))
        if s0 >= n: break
        tt = t[s0:s1] - i * seg; env = np.clip(tt / 1.2, 0, 1) * np.clip((seg + 1.0 - tt) / 1.0, 0, 1)
        for f in ch:
            out[s0:s1] += env * (np.sin(2 * np.pi * f * tt) + .3 * np.sin(2 * np.pi * f * 2.003 * tt) + .15 * np.sin(2 * np.pi * f * .5 * tt)) * .012
    out += np.sin(2 * np.pi * 41.2 * t) * .02 * (0.7 + 0.3 * np.sin(2 * np.pi * t / 9))
    noise = np.convolve(rng.standard_normal(n), np.ones(200) / 200, 'same').astype(np.float32)
    out += noise * .08 * (0.5 + 0.5 * np.sin(2 * np.pi * t / 6.5))
    for ct in cuts:  # whoosh into each cut
        i = int((ct - .45) * sr); L = int(.7 * sr)
        if 0 <= i and i + L < n:
            nz = np.convolve(rng.standard_normal(L), np.ones(25) / 25, 'same')
            out[i:i + L] += nz * (np.linspace(0, 1, L) ** 2 * np.exp(-np.linspace(0, 5, L) * 0) * np.hanning(L)) * .12
    # cinematic hit at the start
    L = int(1.6 * sr); tt = np.arange(L) / sr
    out[:L] += np.sin(2 * np.pi * (60 - 25 * tt) * tt) * np.exp(-tt * 2.5) * .35
    fade = np.clip((total - t) / 2.0, 0, 1); return out * fade

# ---------------------------------------------------------------- build
def build(SCENES, name, outdir, HL=()):
    import soundfile as sf
    os.makedirs(outdir, exist_ok=True)
    lines = [ln for _, ln in SCENES]
    clips = tts_lines(lines); sr = clips[0][1]
    durs = [len(a) / sr + LEAD + GAP for a, _ in clips]
    starts = np.concatenate([[0], np.cumsum(durs)[:-1]]); total = float(sum(durs))
    caps = []
    for i, ((a, _), ln) in enumerate(zip(clips, lines)):
        for words, t0, t1 in chunk_words(ln, word_times(ln, len(a) / sr)):
            caps.append((words, starts[i] + LEAD + t0 - .05, starts[i] + LEAD + t1))
    mode = sys.argv[1] if len(sys.argv) > 1 else 'render'
    surf = skia.Surface(W, H); cv = surf.getCanvas()

    def frame(T):
        i = int(np.searchsorted(starts, T, side='right') - 1); i = max(0, min(i, len(SCENES) - 1))
        def draw(j, TT):
            fn = SCENES[j][0]; cv.save(); fn(cv, TT - starts[j], durs[j], TT); cv.restore(); vignette(cv)
            return surf.makeImageSnapshot().toarray()
        a = draw(i, T)
        if i + 1 < len(SCENES) and T > starts[i + 1] - XF:
            u = ease((T - (starts[i + 1] - XF)) / XF); b = draw(i + 1, T)
            a = (a.astype(np.float32) * (1 - u) + b.astype(np.float32) * u).astype(np.uint8)
        for words, t0, t1 in caps:
            if t0 <= T < max(t1, t0 + .25):
                img = skia.Image.fromarray(a, colorType=skia.kBGRA_8888_ColorType); cv.drawImage(img, 0, 0)
                caption(cv, words, t0, T, HL); a = surf.makeImageSnapshot().toarray(); break
        return a

    if mode == 'preview':
        ts = [starts[i] + durs[i] * .6 for i in range(len(SCENES))]
        from PIL import Image
        for k, T in enumerate(ts):
            fr = frame(T); Image.fromarray(fr[..., [2, 1, 0]]).save(f'{outdir}/prev{k}.jpg', quality=88)
        print('durations', [round(d, 1) for d in durs], 'total', round(total, 1)); return

    # audio: mastered voice + music bed
    n = int(total * sr) + sr; voice = np.zeros(n, np.float32)
    for (a, _), s in zip(clips, starts):
        i0 = int((s + LEAD) * sr); voice[i0:i0 + len(a)] += a
    sf.write(f'{outdir}/voice_raw.wav', voice, sr)
    sf.write(f'{outdir}/bed.wav', music_bed(n, sr, starts[1:], total), sr)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', f'{outdir}/voice_raw.wav', '-i', f'{outdir}/bed.wav', '-filter_complex',
                    '[0]highpass=f=70,equalizer=f=180:t=q:w=1:g=2,equalizer=f=3500:t=q:w=1.2:g=2.5,acompressor=threshold=-20dB:ratio=3:attack=8:release=120:makeup=3,aecho=0.8:0.6:28:0.12,asplit[v][vs];'
                    '[1]volume=0.9[m];[m][vs]sidechaincompress=threshold=0.03:ratio=4:attack=20:release=300[md];[v][md]amix=inputs=2:normalize=0,loudnorm=I=-14:TP=-1.2',
                    '-ar', '48000', f'{outdir}/mix.wav'], check=True)
    nf = int(total * FPS); tmp = f'{outdir}/{name}.video.tmp.mp4'
    p = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                          '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '14', '-pix_fmt', 'yuv420p', tmp], stdin=subprocess.PIPE)
    for f in range(nf):
        p.stdin.write(frame(f / FPS).tobytes())
        if f % 150 == 0: print(f'frame {f}/{nf}', flush=True)
    p.stdin.close(); assert p.wait() == 0
    os.replace(tmp, f'{outdir}/{name}.video.mp4')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', f'{outdir}/{name}.video.mp4', '-i', f'{outdir}/mix.wav', '-map', '0:v', '-map', '1:a',
                    '-c:v', 'libx264', '-preset', 'slow', '-crf', '19', '-tune', 'animation', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k',
                    '-movflags', '+faststart', '-shortest', f'{outdir}/{name}.mp4'], check=True)
    print('done', total, os.path.getsize(f'{outdir}/{name}.mp4'))
