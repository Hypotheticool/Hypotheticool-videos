"""2D motion-graphics scenes for the long video "What If the Moon Disappeared? The Full Story".
Run with HC_W=1920 HC_H=1080:  python3 scenes2d_moon-full-story.py <line indices...>   (or 'all', or 'still <i> <t>')
Every number on screen is sourced in pipeline/research/2026-11-27-long-moon-full-story.md."""
import sys, json, math, os
sys.path.insert(0, '/home/claude/pro')
import numpy as np, skia
import mg
from mg import text, wrap, panel, bg, ACC, ACC2, INK
from engine import *

CFG = json.load(open('/home/claude/b3d/moon-full-story/topic.json')); D = CFG['durs']; ROOT = CFG['root']
TEX = '/home/claude/b3d/assets/textures/'
WARM, COOL, RED = (255, 170, 70), (120, 200, 255), (255, 110, 90)

# ------------------------------------------------------------ real-texture globes (orthographic, sunlit) for 2D slides
_SPH = {}
def sphere_img(tex, px, lon0=0.0, sun=(-.6, -.35, .7), tilt=0.0, night=None, amb=.04):
    key = (tex, px, round(lon0, 1), sun, tilt)
    if key in _SPH: return _SPH[key]
    from PIL import Image
    if tex not in _SPH: _SPH[tex] = np.asarray(Image.open(TEX + tex).convert('RGB'), np.float32) / 255
    T = _SPH[tex]; th, tw = T.shape[:2]
    yy, xx = np.mgrid[0:px, 0:px].astype(np.float32); x = (xx + .5) / px * 2 - 1; y = 1 - (yy + .5) / px * 2
    r2 = x * x + y * y; m = r2 <= 1; z = np.sqrt(np.clip(1 - r2, 0, 1))
    ct, st = math.cos(math.radians(tilt)), math.sin(math.radians(tilt))
    xr, yr = x * ct + y * st, -x * st + y * ct            # roll the globe by `tilt` (axis lean in the picture plane)
    lat = np.arcsin(np.clip(yr, -1, 1)); lon = np.arctan2(xr, z) + math.radians(lon0)
    u = ((lon / (2 * math.pi) + .5) % 1) * (tw - 1); v = (.5 - lat / math.pi) * (th - 1)
    col = T[v.astype(int), u.astype(int)]
    s = np.array(sun, np.float32); s /= np.linalg.norm(s)
    lam = np.clip(x * s[0] + y * s[1] + z * s[2], 0, 1)
    sh = (amb + (1 - amb) * lam ** .8)[..., None]
    img = col * sh
    if night is not None:
        if night not in _SPH: _SPH[night] = np.asarray(Image.open(TEX + night).convert('RGB'), np.float32) / 255
        N = _SPH[night]; nh, nw = N.shape[:2]
        nl = N[(v / (th - 1) * (nh - 1)).astype(int), (u / (tw - 1) * (nw - 1)).astype(int)]
        img += nl * np.array([1, .8, .5]) * 1.6 * (np.clip(.15 - lam, 0, .15) / .15)[..., None]
    a = np.clip((1 - np.sqrt(r2)) * px * .5, 0, 1) * m
    rgba = np.dstack([np.clip(img, 0, 1) * 255, a * 255]).astype(np.uint8)
    rgba[..., :3] = (rgba[..., :3].astype(np.float32) * a[..., None]).astype(np.uint8)   # premultiplied
    bgra = np.ascontiguousarray(rgba[..., [2, 1, 0, 3]])
    im = skia.Image.fromarray(bgra, colorType=skia.kBGRA_8888_ColorType, alphaType=skia.kPremul_AlphaType)
    _SPH[key] = im; return im

def globe(c, tex, x, y, r, a=1.0, **kw):
    im = sphere_img(tex, int(min(900, max(64, r * 2))), **kw)
    p = skia.Paint(); p.setAlphaf(max(0, min(1, a)))
    c.drawImageRect(im, skia.Rect(x - r, y - r, x + r, y + r), skia.SamplingOptions(skia.FilterMode.kLinear), p)

def earth2d(c, x, y, r, a=1.0, lon0=-80, **kw): globe(c, 'earth_day.jpg', x, y, r, a, lon0=lon0, night='earth_night.jpg', **kw)
def moon2d(c, x, y, r, a=1.0, **kw): globe(c, 'moon.jpg', x, y, r, a, **kw)
def atmo(c, x, y, r, a=1.0): c.drawCircle(x, y, r * 1.04, P(C(110, 170, 255, 90 * a), 'stroke', r * .03, blur=r * .03))
def label(c, s, x, y, sz=44, color=INK, a=1.0, align='center'): text(c, s, x, y, sz, color, a, align=align, stroke=7)
def heading(c, s, t, y=H * .14, color=ACC): text(c, s.upper(), W / 2, y, 76, color, eout(t / .4))
def dashed(c, x0, y0, x1, y1, color, a, w=4, on=18, off=12):
    p = P(C(*color, 255 * a), 'stroke', w); p.setPathEffect(skia.DashPathEffect.Make([on, off], 0)); c.drawLine(x0, y0, x1, y1, p)

# ------------------------------------------------------------ custom scenes
def scene_meet():                       # 4  "First, let's meet what we'd be losing."
    def draw(c, t, d, T):
        bg(c, T, t); a = eout(t / .6)
        glow(c, W * .5, H * .44, 420, (200, 210, 255), .18 * a)
        moon2d(c, W * .5, H * .44, 300 * (.9 + .1 * eout(t / d)), a, lon0=8 * t / d, sun=(-.5, .3, .8))
        label(c, 'OUR MOON', W / 2, H * .86 - 40, 64, ACC, eout((t - .4) / .5))
    return draw

def scene_size():                       # (2D backup for 6) true-scale widths
    def draw(c, t, d, T):
        bg(c, T, t); heading(c, 'True scale: widths', t)
        Re = 300; Rm = Re * 3475 / 12742
        earth2d(c, W * .38, H * .5, Re, eout(t / .5), lon0=-60, sun=(-.6, .3, .75)); atmo(c, W * .38, H * .5, Re, eout(t / .5))
        moon2d(c, W * .38 + Re + 80 + Rm, H * .5, Rm, eout((t - .4) / .5), sun=(-.6, .3, .75))
    return draw

def scene_reflect():                    # 10 albedo ~ a tenth
    def draw(c, t, d, T):
        bg(c, T, t); heading(c, 'Moonlight = reflected sunlight', t)
        u = eio((t - .3) / 1.6)
        star(c, W * .1, H * .48, 90, T, eout(t / .4))
        mx = W * .52; moon2d(c, mx, H * .48, 150, eout((t - .2) / .5), sun=(-1, 0, .25))
        arrow(c, W * .1 + 110, H * .48, lerp(W * .1 + 110, mx - 170, u), H * .48, 16, WARM, u)
        label(c, '100% OF SUNLIGHT', W * .25, H * .4, 40, WARM, u)
        v = eio((t - 1.8) / 1.2)
        arrow(c, mx - 150, H * .56, lerp(mx - 150, W * .3, v), lerp(H * .56, H * .74, v), 6, (210, 215, 230), v)
        text(c, '~10%', W * .27, H * .66, 110, ACC, v, stroke=12)
        label(c, 'REFLECTED BACK', W * .27, H * .78, 40, INK, v)
        label(c, 'THE SURFACE IS ABOUT AS DARK AS WORN ASPHALT', W * .72, H * .74, 38, INK, eout((t - 2.4) / .5))
    return draw

def scene_nights():                     # 12 full-moon night vs moonless night
    def draw(c, t, d, T):
        bg(c, T, t)
        for k, (x, title, lit) in enumerate([(W * .06, 'FULL-MOON NIGHT', 1), (W * .53, 'EVERY NIGHT, NO MOON', 0)]):
            a = eout((t - k * .5) / .5); w, h = W * .41, H * .62; y = H * .14
            c.save(); c.clipRect(skia.Rect(x, y, x + w, y + h))
            c.drawRect(skia.Rect(x, y, x + w, y + h), P(shader=linear((0, y), (0, y + h), [C(20, 34, 70, 255 * a) if lit else C(2, 3, 10, 255 * a), C(6, 10, 24, 255 * a)])))
            for i in range(90 if not lit else 25):
                sx = x + (i * 97 % 1000) / 1000 * w; sy = y + (i * 61 % 700) / 1000 * h
                c.drawCircle(sx, sy, 1.6 + (i % 3) * .6, P(C(240, 240, 255, (150 + 100 * math.sin(T * 2 + i)) * a * .6)))
            if lit:
                moon2d(c, x + w * .75, y + h * .25, 50, a, sun=(0, 0, 1)); glow(c, x + w * .75, y + h * .25, 160, (190, 200, 255), .3 * a)
            hill = skia.Path(); hill.moveTo(x, y + h)
            for j in range(21): hill.lineTo(x + w * j / 20, y + h * (.72 + .06 * math.sin(j * .9) + .03 * math.sin(j * 2.3)))
            hill.lineTo(x + w, y + h); hill.close()
            c.drawPath(hill, P(C(40, 55, 75, 255 * a) if lit else C(5, 6, 9, 255 * a)))
            c.restore(); panel(c, x, y, w, h, a * .4)
            label(c, title, x + w / 2, y + h + 70, 52, ACC2 if lit else ACC, a)
    return draw

def scene_bulge():                      # 16 two tidal bulges (not to scale)
    def draw(c, t, d, T):
        bg(c, T, t); heading(c, 'Why there are two tidal bulges', t)
        ex, ey, R = W * .33, H * .5, 190; u = eio((t - .6) / 2.2)
        sx, sy = 1 + .28 * u, 1 - .1 * u
        c.save(); c.translate(ex, ey); c.scale(sx, sy)
        c.drawCircle(0, 0, R * 1.12, P(C(40, 120, 255, 150 * eout(t / .5)))); c.restore()
        earth2d(c, ex, ey, R, eout(t / .5), lon0=-30, sun=(0, 0, 1))
        moon2d(c, W * .85, ey, 60, eout((t - .2) / .5), sun=(0, 0, 1))
        for k, (dy, ln, col) in enumerate([(0, 1, (255, 222, 40))]):
            pass
        v = eout((t - 1.0) / .6)
        for px, ln, lab in [(ex + R * .9, 120, 'STRONGER PULL'), (ex, 85, ''), (ex - R * .9, 55, 'WEAKER PULL')]:
            arrow(c, px, ey - R * 1.7 + 40, px + ln * v, ey - R * 1.7 + 40, 10, ACC, v)
            if lab: label(c, lab, px + 40, ey - R * 1.7 - 10, 32, INK, v)
        label(c, 'BULGE', ex + R * 1.62, ey + 10, 40, COOL, u); label(c, 'BULGE', ex - R * 1.62, ey + 10, 40, COOL, u)
        label(c, 'TO THE MOON', W * .85, ey + 120, 36, INK, eout((t - .4) / .5))
        label(c, 'BULGES EXAGGERATED, NOT TO SCALE', W / 2, H * .82, 32, (180, 190, 220), eout((t - 1.5) / .5))
    return draw

def scene_phases():                     # 19 spring / neap tides with the phases
    def draw(c, t, d, T):
        bg(c, T, t); heading(c, 'Spring and neap tides', t)
        items = [('NEW MOON', 'SPRING TIDE', 'biggest', 1), ('FIRST QUARTER', 'NEAP TIDE', 'smallest', 0),
                 ('FULL MOON', 'SPRING TIDE', 'biggest', 1), ('LAST QUARTER', 'NEAP TIDE', 'smallest', 0)]
        suns = [(0, 0, -1), (-1, 0, 0), (0, 0, 1), (1, 0, 0)]
        for i, ((ph, tide, word, big), s) in enumerate(zip(items, suns)):
            x = W * (.14 + .24 * i); a = eout((t - .3 - i * .45) / .45)
            if a <= 0: continue
            moon2d(c, x, H * .36, 90, a, sun=(s[0] * .99 + .001, .001, s[2] * .99 + .001), amb=.06)
            label(c, ph, x, H * .36 + 150, 40, INK, a)
            hgt = (150 if big else 55) * a
            c.drawRoundRect(skia.Rect(x - 60, H * .78 - hgt, x + 60, H * .78), 10, 10, P(C(*(COOL if big else (90, 120, 200)), 230 * a)))
            label(c, tide, x, H * .78 + 0 - hgt - 20, 36, ACC if big else INK, a)
        label(c, 'TIDAL RANGE', W * .03, H * .78 - 70, 30, (170, 180, 210), eout(t / .5), align='left')
    return draw

def scene_coral():                      # 23 coral spawning
    def draw(c, t, d, T):
        bg(c, T, t, ); heading(c, 'Great Barrier Reef mass spawning', t)
        c.drawRect(skia.Rect(0, H * .2, W, H * .86), P(shader=linear((0, H * .2), (0, H * .86), [C(5, 25, 55, 230), C(2, 8, 20, 240)])))
        moon2d(c, W * .82, H * .32, 60, eout(t / .5), sun=(0, 0, 1)); glow(c, W * .82, H * .32, 180, (180, 200, 255), .3)
        for i in range(180):            # rising egg-sperm bundles (pink/orange dots)
            ph = (i * .618) % 1; sp = .06 + .05 * ((i * 37) % 10) / 10
            yy = H * .82 - ((T * sp + ph) % 1) * H * .55; xx = (i * 211 % 1000) / 1000 * W + 12 * math.sin(T + i)
            c.drawCircle(xx, yy, 4 + i % 3, P(C(255, 150 + (i % 4) * 20, 160, 200 * eout((t - .3) / .6))))
        for i in range(14):             # simple coral silhouettes on the reef floor
            x = W * (i + .5) / 14; hh = 60 + 50 * ((i * 7) % 5) / 5
            for k in range(5):
                ang = -math.pi / 2 + (k - 2) * .35
                c.drawLine(x, H * .86, x + math.cos(ang) * hh, H * .86 + math.sin(ang) * hh, P(C(200, 110, 120, 220), 'stroke', 10))
        tl = [('OCT', 'after full Moon'), ('NOV', 'after full Moon'), ('DEC', 'after full Moon')]
        for i, (m, s) in enumerate(tl):
            a = eout((t - .6 - i * .4) / .4); x = W * (.2 + .2 * i)
            panel(c, x - 120, H * .26, 240, 120, a); label(c, m, x, H * .26 + 60, 52, ACC, a); label(c, '1-6 NIGHTS ' + s.upper(), x, H * .26 + 105, 24, INK, a)
    return draw

def scene_turtle():                     # 26 hatchlings head for the brighter sea horizon
    def draw(c, t, d, T):
        bg(c, T, t, ); heading(c, 'Hatchlings head for the brightest horizon', t)
        c.drawRect(skia.Rect(0, H * .2, W, H * .5), P(shader=linear((0, H * .2), (0, H * .5), [C(20, 35, 75), C(60, 85, 130)])))
        c.drawRect(skia.Rect(0, H * .5, W, H * .62), P(shader=linear((0, H * .5), (0, H * .62), [C(70, 100, 150), C(25, 45, 80)])))
        for k in range(6):
            yy = H * .62 + k * 6 + 4 * math.sin(T * 1.5 + k)
            c.drawLine(0, yy, W, yy, P(C(200, 220, 255, 60), 'stroke', 2))
        c.drawRect(skia.Rect(0, H * .64, W, H * .86), P(shader=linear((0, H * .64), (0, H * .86), [C(70, 62, 50), C(30, 26, 22)])))
        for i in range(9):
            u = eio((t - .3 - i * .15) / (d * .8)); x = W * (.1 + .09 * i); y = lerp(H * .84, H * .67, u)
            c.save(); c.translate(x, y); c.drawOval(skia.Rect(-14, -18, 14, 18), P(C(35, 30, 25)))
            for sgn in (-1, 1): c.drawLine(0, -6, sgn * 22, -14 + 6 * math.sin(T * 9 + i), P(C(35, 30, 25), 'stroke', 6))
            c.restore()
        arrow(c, W * .5, H * .8, W * .5, H * .58, 10, ACC, eout((t - 1) / .5)); label(c, 'BRIGHTER SEA HORIZON', W * .5, H * .54, 40, ACC, eout((t - 1.2) / .5))
    return draw

def scene_beetle():                     # 28 dung beetles and polarized moonlight
    def draw(c, t, d, T):
        bg(c, T, t); heading(c, 'Dung beetles steer by moonlight', t)
        moon2d(c, W * .5, H * .3, 70, eout(t / .5), sun=(0, 0, 1)); glow(c, W * .5, H * .3, 200, (190, 200, 255), .3)
        for k in range(1, 6):            # polarization rings around the Moon
            p = P(C(150, 190, 255, 70), 'stroke', 3); c.drawCircle(W * .5, H * .3, 70 + k * 60 + 10 * math.sin(T + k), p)
        u = eio((t - .4) / (d * .8)); bx = lerp(W * .15, W * .8, u); by = H * .75
        c.drawLine(W * .15, by + 30, bx - 40, by + 30, P(C(255, 222, 40, 160), 'stroke', 4))
        c.drawCircle(bx, by, 34, P(C(95, 70, 45))); c.drawOval(skia.Rect(bx - 90, by - 4, bx - 34, by + 30), P(C(20, 22, 28)))
        label(c, 'STRAIGHT LINE', W * .42, by + 80, 36, ACC, eout((t - 1) / .5))
        label(c, 'POLARIZED MOONLIGHT: ~1 MILLION TIMES DIMMER THAN SUNLIGHT\'S', W / 2, H * .55, 34, INK, eout((t - 1.6) / .5))
    return draw

def scene_bary():                       # 40 barycenter inside Earth
    def draw(c, t, d, T):
        bg(c, T, t); heading(c, 'The shared balance point', t)
        ex, ey, R = W * .4, H * .5, 260
        earth2d(c, ex, ey, R, eout(t / .5), lon0=20, sun=(-.5, .3, .8)); atmo(c, ex, ey, R, eout(t / .5))
        bx = ex + R * 4700 / 6371; v = eout((t - .8) / .5)
        c.drawLine(ex, ey, bx, ey, P(C(255, 255, 255, 200 * v), 'stroke', 4))
        c.drawCircle(bx, ey, 14 * v, P(C(*ACC))); glow(c, bx, ey, 60, ACC, .5 * v)
        label(c, '~4,700 KM FROM THE CENTER', ex + R * .35, ey - 30, 34, ACC, v)
        dashed(c, ex + R + 20, ey, W * .93, ey, (200, 200, 230), eout((t - 1.2) / .5))
        moon2d(c, W * .93, ey, 40, eout((t - .4) / .5), sun=(-.5, .3, .8))
        label(c, 'TO THE MOON (DISTANCE NOT TO SCALE)', W * .8, ey + 90, 30, INK, eout((t - 1.4) / .5))
        label(c, "STILL INSIDE EARTH (RADIUS ~6,371 KM)", W / 2, H * .84, 38, INK, eout((t - 1.8) / .5))
    return draw

def scene_wobble():                     # 41 Earth wobbles around the balance point
    def draw(c, t, d, T):
        bg(c, T, t); heading(c, 'A monthly wobble', t)
        cx, cy = W * .5, H * .5; ang = T * 1.4
        r_e, r_m = 70, 420
        ex, ey = cx - r_e * math.cos(ang), cy - r_e * math.sin(ang) * .5
        mx, my = cx + r_m * math.cos(ang), cy + r_m * math.sin(ang) * .5
        c.drawOval(skia.Rect(cx - r_e, cy - r_e * .5, cx + r_e, cy + r_e * .5), P(C(255, 222, 40, 140), 'stroke', 3))
        c.drawOval(skia.Rect(cx - r_m, cy - r_m * .5, cx + r_m, cy + r_m * .5), P(C(200, 200, 230, 90), 'stroke', 2))
        earth2d(c, ex, ey, 150, eout(t / .5), lon0=20, sun=(-.5, .3, .8))
        moon2d(c, mx, my, 40, eout(t / .5), sun=(-.5, .3, .8))
        c.drawCircle(cx, cy, 10, P(C(*ACC)))
        label(c, 'WOBBLE EXAGGERATED, NOT TO SCALE', W / 2, H * .84, 32, (180, 190, 220), eout((t - 1) / .5))
    return draw

def scene_tilt_range():                 # 43 22.1 to 24.5 degrees, ~41,000 years
    def draw(c, t, d, T):
        bg(c, T, t); heading(c, "Earth's tilt over the last million years", t)
        cx, cy, R = W * .3, H * .52, 210; tilt = 23.3 + 1.2 * math.sin(T * .9)
        earth2d(c, cx, cy, R, eout(t / .5), lon0=-40, sun=(-.6, .2, .8), tilt=-tilt); atmo(c, cx, cy, R)
        a = math.radians(tilt); L = R * 1.45
        c.drawLine(cx - math.sin(a) * L, cy + math.cos(a) * L, cx + math.sin(a) * L, cy - math.cos(a) * L, P(C(255, 230, 140), 'stroke', 5))
        dashed(c, cx, cy + L, cx, cy - L, (200, 200, 230), 1)
        for k, (val, lab) in enumerate([('22.1°', 'MINIMUM'), ('24.5°', 'MAXIMUM'), ('~41,000', 'YEARS PER CYCLE')]):
            v = eout((t - .5 - k * .4) / .4); y = H * (.33 + .2 * k)
            text(c, val, W * .68, y, 100, ACC if k < 2 else ACC2, v, stroke=10); label(c, lab, W * .68, y + 50, 36, INK, v)
    return draw

def scene_milder():                     # 46 Laskar vs later simulations
    return mg.compare(('1993 study', ['Tilt could swing chaotically', 'From almost 0° to about 85°']),
                      ('Later simulations', ['A much milder wander', 'Range of about 20-25°', 'Over hundreds of millions of years']))

def scene_earlyday():                   # 53 timeline
    return mg.timeline('Our days keep getting longer', [('~4.5 billion yrs ago', 'Moon forms after a giant impact (leading idea)'),
                                                        ('~1.4 billion yrs ago', 'A day lasts just over 18 hours'),
                                                        ('Today', 'A day lasts 24 hours'),
                                                        ('Every century', 'About 2 ms longer')])

def scene_tidecurve():                  # 20 the two-week spring-neap rhythm vanishes
    def draw(c, t, d, T):
        bg(c, T, t); heading(c, 'Tides over one month (simplified)', t)
        x0, x1 = W * .08, W * .92; days = 29.5
        for k, (yc, lab, moonA, col) in enumerate([(H * .38, 'TODAY: MOON + SUN', 1.0, COOL), (H * .66, 'NO MOON: SUN ONLY', 0.0, ACC)]):
            a = eout((t - k * .6) / .5); u = eio((t - .2 - k * .6) / 2.0)
            label(c, lab, x0, yc - 105, 40, col, a, align='left')
            c.drawLine(x0, yc, x1, yc, P(C(255, 255, 255, 40 * a), 'stroke', 2))
            path = skia.Path(); n = 1400
            for j in range(int(n * u) + 1):
                dd = j / n * days; hgt = moonA * math.cos(2 * math.pi * dd / 1.035 * 2) + .46 * math.cos(2 * math.pi * dd * 2)
                x = x0 + (x1 - x0) * j / n; y = yc - hgt * 52
                (path.moveTo if j == 0 else path.lineTo)(x, y)
            c.drawPath(path, P(C(*col, 230 * a), 'stroke', 2.2))
        v = eout((t - 2.4) / .5)
        for dd, lab in [(0, 'SPRING'), (7.4, 'NEAP'), (14.8, 'SPRING'), (22.1, 'NEAP')]:
            label(c, lab, x0 + (x1 - x0) * dd / days + 40, H * .38 + 110, 30, INK, v)
        label(c, 'SIMPLIFIED: MAIN MOON AND SUN TIDES ONLY', W / 2, H * .83, 30, (180, 190, 220), v)
    return draw

# ------------------------------------------------------------ the scene table (2D lines only)
S = {
    2: mg.title_card('What if the Moon disappeared?', 'The full story'),
    3: mg.timeline('What would change', [('Right away', 'Darker nights'), ('Soon after', 'Smaller tides'), ('Every season', 'Life loses its Moon clock'), ('Millions of years', 'Tilt, spin and climate')]),
    4: scene_meet(),
    5: mg.stat('384,400 KM', 'average distance from Earth', ACC, 'about 239,000 miles'),
    7: mg.bars('Mass compared', [('Earth', 81), ('Moon', 1)], unit='', color=ACC2),
    8: mg.bullets('What the Moon does for us', ['Lights our nights', 'Raises most of our tides', 'Sets the rhythm for many animals', 'May help steady our tilt']),
    10: scene_reflect(),
    11: mg.stat('~400,000×', 'brighter: the Sun vs a full Moon', WARM, 'yet moonlight is what lights a moonlit night'),
    12: scene_nights(),
    14: mg.stat('1 in 3', 'people cannot see the Milky Way', ACC, 'from where they live, due to light pollution (Falchi et al., 2016)'),
    16: scene_bulge(),
    17: mg.bars('Tide-raising force (Moon = 100)', [('Moon', 100), ('Sun', 46)], unit='%', color=ACC2),
    18: mg.compare(('With the Moon', ['Moon + Sun raise tides', "Today's tidal range"]), ('Without the Moon', ['Only the Sun raises tides', 'Roughly 1/3 to 1/2 as big'])),
    19: scene_phases(),
    20: scene_tidecurve(),
    21: mg.bullets('The shore between the tides', ['Tide pools', 'Mudflats', 'All squeezed into a much narrower strip']),
    22: mg.title_card('Life on a Moon schedule', 'corals, turtles, beetles, lions, fish'),
    23: scene_coral(),
    24: mg.quote('A light-sensing gene in corals switches on under the faint blue light of the full Moon.', 'Levy et al., Science, 2007'),
    25: mg.stat('OUT OF SYNC', 'a shared clock could be lost', RED),
    26: scene_turtle(),
    27: mg.bullets('Sea turtle hatchlings', ['Guided by moonlight and starlight over the water', 'Bright beach lights can send them the wrong way']),
    28: scene_beetle(),
    29: mg.stat('MILKY WAY', 'first animal known to steer by it', COOL, 'dung beetle Scarabaeus satyrus (Dacke et al., 2013)'),
    30: mg.compare(('Lions', ['Hunt most successfully', 'on the darkest nights']), ('Many rodents & bats', ['Lie low', 'when the Moon is bright'])),
    31: mg.bullets('California grunion', ['Spawn on beaches on the highest tides of the month', 'For a few nights from each full and new Moon']),
    32: mg.title_card('Change, or break', 'rhythms built around the Moon'),
    33: mg.title_card('Human history', 'calendars, eclipses, footprints'),
    34: mg.bullets('The Moon in our calendars', ['"Month" shares an old root with "Moon"', 'Islamic months begin with the first thin crescent']),
    36: mg.timeline('The last eclipses we would get', [('Aug 12, 2026', 'Total: Greenland, Iceland, Spain'), ('Aug 2, 2027', 'Total: southern Spain, North Africa'), ('Near Luxor', 'Over 6 minutes of totality'), ('No Moon', 'No more eclipses, ever')]),
    37: mg.stat('12', 'people have walked on the Moon', ACC, 'six Apollo landings, 1969-1972'),
    39: mg.title_card('The slow changes', 'over millions of years'),
    40: scene_bary(),
    41: scene_wobble(),
    43: scene_tilt_range(),
    44: mg.bullets('A steadier planet', ['Many scientists think the Moon helps keep Earth\'s tilt steady', 'Steady tilt = steady seasons']),
    46: scene_milder(),
    47: mg.bullets('Still debated', ['How much the Moon matters', 'More tilt = stronger seasons', 'Even a milder wander could reshape climates']),
    49: mg.stat('~2 MS', 'longer day, every century', ACC, 'thousandths of a second (measured about 1.8 ms)'),
    50: mg.compare(('With the Moon', ['Moon and Sun tides brake Earth', 'Day lengthens ~2 ms per century']), ('Without the Moon', ['Only the Sun\'s tides', 'Days stretch far more slowly'])),
    53: scene_earlyday(),
    55: mg.stat('3.8 CM', 'per year: the Moon drifting away', ACC2, 'about 1.5 inches, measured with lasers'),
}

if __name__ == '__main__':
    args = sys.argv[1:]
    if args and args[0] == 'still':          # quick check frame: still <i> <t>
        from PIL import Image
        i, tt = int(args[1]), float(args[2]); surf = skia.Surface(W, H); cv = surf.getCanvas()
        S[i](cv, tt, D[i], tt + 100); vignette(cv)
        Image.fromarray(surf.makeImageSnapshot().toarray()[..., [2, 1, 0]]).save(f'{ROOT}/check2d_{i}.png'); sys.exit()
    idx = sorted(S) if (not args or args[0] == 'all') else list(map(int, args))
    for i in idx:
        nf = mg.render_scene(S[i], D[i], .75, f'{ROOT}/s{i}')
        json.dump({'frames': nf, 'overlays': []}, open(f'{ROOT}/s{i}/meta.json', 'w')); print(i, nf, flush=True)
