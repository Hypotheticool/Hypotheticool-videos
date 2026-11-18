"""Hypotheticool motion-graphics kit (skia) for long-form 16:9 explainers.
Each factory returns draw(c, t, d, T) for a scene of length d. Set HC_W=1920 HC_H=1080 before importing engine."""
import math, skia
from engine import *

ACC, ACC2, INK = (255, 222, 40), (120, 220, 255), (255, 255, 255)
def _font(sz): return skia.Font(TF, sz)

def text(c, s, x, y, sz, color=INK, a=1.0, align='center', stroke=10):
    f = _font(sz); w = f.measureText(s)
    if align == 'center': x -= w / 2
    elif align == 'right': x -= w
    if stroke: c.drawString(s, x, y, f, P(C(0, 0, 0, 230 * a), 'stroke', stroke))
    c.drawString(s, x, y, f, P(C(*color, 255 * a)))
    return w

def wrap(s, sz, maxw):
    f = _font(sz); words = s.split(); lines = []; cur = ''
    for w in words:
        t = (cur + ' ' + w).strip()
        if f.measureText(t) > maxw and cur: lines.append(cur); cur = w
        else: cur = t
    if cur: lines.append(cur)
    return lines

def panel(c, x, y, w, h, a=1.0, r=28):
    c.drawRoundRect(skia.Rect(x, y, x + w, y + h), r, r, P(C(10, 12, 34, 200 * a)))
    c.drawRoundRect(skia.Rect(x, y, x + w, y + h), r, r, P(C(120, 140, 255, 90 * a), 'stroke', 3))

def bg(c, T, t):
    backdrop(c, T, par=(-8 * t, -4 * t), zoom=1.03 + .01 * t, dim=.75)

def title_card(title, sub='', color=ACC):
    def draw(c, t, d, T):
        bg(c, T, t); a = eout(t / .5); s = .9 + .1 * a
        c.save(); c.translate(W / 2, H * .45); c.scale(s, s); c.translate(-W / 2, -H * .45)
        glow(c, W / 2, H * .42, 520, (120, 80, 255), .25 * a)
        for i, ln in enumerate(wrap(title.upper(), 120, W * .8)):
            text(c, ln, W / 2, H * .42 + i * 130, 120, color, a, stroke=14)
        if sub: text(c, sub.upper(), W / 2, H * .42 + 130 * len(wrap(title.upper(), 120, W * .8)) + 30, 56, INK, eout((t - .35) / .5))
        c.restore()
    return draw

def stat(value, label, color=ACC, note=''):
    def draw(c, t, d, T):
        bg(c, T, t); a = eout(t / .45)
        glow(c, W / 2, H * .4, 420, color, .22 * a)
        sc = .6 + .4 * eout(t / .4)
        c.save(); c.translate(W / 2, H * .45); c.scale(sc, sc); c.translate(-W / 2, -H * .45)
        text(c, value, W / 2, H * .47, 230, color, a, stroke=16); c.restore()
        text(c, label.upper(), W / 2, H * .6, 60, INK, eout((t - .3) / .5))
        if note: text(c, note, W / 2, H * .68, 40, (190, 200, 230), eout((t - .6) / .5), stroke=6)
    return draw

def bars(title, items, unit='', color=ACC2, maxv=None):
    """items: [(label, value)]"""
    def draw(c, t, d, T):
        bg(c, T, t); a = eout(t / .4)
        text(c, title.upper(), W / 2, H * .17, 72, ACC, a)
        n = len(items); mv = maxv or max(v for _, v in items); x0, x1 = W * .32, W * .86
        bh = min(110, H * .55 / n - 24); y = H * .27
        for i, (lab, v) in enumerate(items):
            u = eio((t - .3 - i * .25) / .9)
            yy = y + i * (bh + 28)
            text(c, lab.upper(), x0 - 30, yy + bh * .72, 50, INK, eout((t - .2 - i * .25) / .4), align='right', stroke=6)
            c.drawRoundRect(skia.Rect(x0, yy, x1, yy + bh), 14, 14, P(C(255, 255, 255, 25 * a)))
            wv = (x1 - x0) * (v / mv) * u
            if wv > 2:
                c.drawRoundRect(skia.Rect(x0, yy, x0 + wv, yy + bh), 14, 14, P(shader=linear((x0, 0), (x0 + wv + 1, 0), [C(*color, 200), C(*color, 255)])))
                glow(c, x0 + wv, yy + bh / 2, bh, color, .35 * u)
            if u > .05:
                val = v * u; s = f'{val:,.0f}' if mv >= 10 else f'{val:.1f}'
                inside = x0 + wv + 20 + _font(50).measureText(s + unit) > x1
                text(c, s + unit, (x0 + wv - 20) if inside else (x0 + wv + 20), yy + bh * .72, 50, (20, 20, 40) if inside else ACC, u, align='right' if inside else 'left', stroke=0 if inside else 6)
    return draw

def bullets(title, points, icon_color=ACC):
    def draw(c, t, d, T):
        bg(c, T, t); a = eout(t / .4)
        text(c, title.upper(), W / 2, H * .18, 80, ACC, a)
        panel(c, W * .12, H * .25, W * .76, H * .62, a)
        y = H * .35; step = (H * .5) / max(1, len(points))
        for i, p in enumerate(points):
            u = eout((t - .4 - i * (d * .6 / max(1, len(points)))) / .45)
            if u <= 0: continue
            c.drawCircle(W * .18, y + i * step - 18, 14 * u, P(C(*icon_color)))
            for j, ln in enumerate(wrap(p, 54, W * .62)[:2]):
                text(c, ln, W * .21 + (1 - u) * 40, y + i * step + j * 60, 54, INK, u, align='left', stroke=6)
    return draw

def compare(left, right, lcol=ACC2, rcol=(255, 120, 90)):
    """left/right: (heading, [points])"""
    def draw(c, t, d, T):
        bg(c, T, t)
        for k, ((head, pts), col, x) in enumerate([(left, lcol, W * .06), (right, rcol, W * .53)]):
            a = eout((t - k * .35) / .5)
            panel(c, x, H * .14, W * .41, H * .72, a)
            text(c, head.upper(), x + W * .205, H * .25, 76, col, a)
            for i, p in enumerate(pts):
                u = eout((t - .5 - k * .35 - i * .3) / .4)
                for j, ln in enumerate(wrap(p, 46, W * .35)[:2]):
                    text(c, ln, x + W * .205, H * .37 + i * 130 + j * 52, 46, INK, u, stroke=6)
        text(c, 'VS', W / 2, H * .52, 90, ACC, eout((t - .6) / .4), stroke=12)
    return draw

def timeline(title, events):
    """events: [(when, what)]"""
    def draw(c, t, d, T):
        bg(c, T, t); a = eout(t / .4)
        text(c, title.upper(), W / 2, H * .18, 76, ACC, a)
        x0, x1, y = W * .08, W * .92, H * .5
        u = eio((t - .2) / (d * .55))
        c.drawLine(x0, y, x0 + (x1 - x0) * u, y, P(C(*ACC2), 'stroke', 8))
        n = len(events)
        for i, (when, what) in enumerate(events):
            px = x0 + (x1 - x0) * (i + .5) / n
            v = eout((t - .2 - (i + .5) / n * d * .55) / .4)
            if v <= 0: continue
            c.drawCircle(px, y, 18 * v, P(C(*ACC))); glow(c, px, y, 60, ACC, .4 * v)
            up = i % 2 == 0
            text(c, when.upper(), px, y - 70 if up else y + 100, 54, ACC, v, stroke=8)
            for j, ln in enumerate(wrap(what, 38, (x1 - x0) / n * 1.6)[:3]):
                text(c, ln, px, (y - 130 - 46 * (len(wrap(what, 38, (x1 - x0) / n * 1.6)[:3]) - 1 - j)) if up else (y + 160 + j * 46), 38, INK, v, stroke=5)
    return draw

def quote(line, who=''):
    def draw(c, t, d, T):
        bg(c, T, t); a = eout(t / .5)
        text(c, '"', W * .12, H * .38, 300, ACC, a * .8, align='left', stroke=0)
        for i, ln in enumerate(wrap(line, 78, W * .72)):
            text(c, ln, W / 2, H * .42 + i * 92, 78, INK, eout((t - .2 - i * .15) / .5))
        if who: text(c, '— ' + who, W / 2, H * .42 + 92 * len(wrap(line, 78, W * .72)) + 40, 46, ACC2, eout((t - .8) / .5), stroke=6)
    return draw

def render_scene(fn, d, pad, outdir):
    """write PNG frames f_0001.png.. for a 2D scene (same layout the 3D scenes use)"""
    import os
    from PIL import Image
    os.makedirs(outdir, exist_ok=True)
    nf = int(math.ceil((d + pad) * 24)); surf = skia.Surface(W, H); cv = surf.getCanvas()
    for k in range(nf):
        t = k / 24 - .35
        cv.save(); fn(cv, max(0.0, t), d, t + 100); cv.restore(); vignette(cv)
        a = surf.makeImageSnapshot().toarray()
        Image.fromarray(a[..., [2, 1, 0]]).save(f'{outdir}/f_{k + 1:04d}.png', compress_level=1)
    return nf
