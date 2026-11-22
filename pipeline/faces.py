"""Draws face textures (equirectangular, for a UV-sphere head) for the cartoon cast. python3 faces.py -> assets/faces/<expr>.png
Big expressive eyes with thick outlines, brows and a mouth; face centered at u=0.5 (faces -Y, toward the default camera)."""
import os, math, skia
W, H = 2048, 1024
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets', 'faces'); os.makedirs(OUT, exist_ok=True)
SKIN_TOP, SKIN_BOT = (247, 245, 240), (150, 170, 225)   # the reference look: pale face fading to a cool blue chin shadow
INK = skia.Color(22, 18, 20)
def P(color, style='fill', w=0, cap=True):
    p = skia.Paint(AntiAlias=True, Color=color)
    if style == 'stroke': p.setStyle(skia.Paint.kStroke_Style); p.setStrokeWidth(w); p.setStrokeCap(skia.Paint.kRound_Cap)
    return p
CX, CY = W * .5, H * .5        # face center (front of the head)
def eye(c, x, y, kind, look=(0, 0)):
    rx, ry = 70, 78
    if kind == 'closed':      # happy arcs
        path = skia.Path(); path.moveTo(x - 60, y + 10); path.quadTo(x, y - 55, x + 60, y + 10); c.drawPath(path, P(INK, 'stroke', 18)); return
    if kind == 'half':        # bored / smirk: heavy upper lid
        c.drawOval(skia.Rect(x - rx, y - ry, x + rx, y + ry), P(skia.ColorWHITE)); c.drawCircle(x + look[0] + 10, y + 18 + look[1], 26, P(INK))
        c.drawRect(skia.Rect(x - rx - 4, y - ry - 4, x + rx + 4, y + 4), P(skia.Color(240, 238, 232)))
        c.drawLine(x - rx, y + 2, x + rx, y + 2, P(INK, 'stroke', 16)); c.drawOval(skia.Rect(x - rx, y - ry, x + rx, y + ry), P(INK, 'stroke', 0)); return
    s = 1.25 if kind == 'wide' else 1.0
    r = skia.Rect(x - rx * s, y - ry * s, x + rx * s, y + ry * s)
    c.drawOval(r, P(skia.ColorWHITE)); c.drawOval(r, P(INK, 'stroke', 14))
    pr = 22 if kind == 'wide' else 30
    c.drawCircle(x + look[0], y + look[1], pr, P(INK)); c.drawCircle(x + look[0] - pr * .35, y + look[1] - pr * .4, pr * .3, P(skia.ColorWHITE))
def brow(c, x, y, angle, w=80):
    a = math.radians(angle); dx, dy = math.cos(a) * w / 2, math.sin(a) * w / 2
    c.drawLine(x - dx, y - dy, x + dx, y + dy, P(INK, 'stroke', 20))
def mouth(c, kind):
    x, y = CX, CY + 175
    if kind == 'flat': c.drawLine(x - 45, y, x + 45, y, P(INK, 'stroke', 14))
    elif kind == 'o': c.drawOval(skia.Rect(x - 30, y - 40, x + 30, y + 40), P(skia.Color(110, 30, 35))); c.drawOval(skia.Rect(x - 30, y - 40, x + 30, y + 40), P(INK, 'stroke', 12))
    elif kind == 'smile':
        pth = skia.Path(); pth.moveTo(x - 80, y - 20); pth.quadTo(x, y + 90, x + 80, y - 20); pth.close()
        c.drawPath(pth, P(skia.Color(120, 30, 40))); c.drawPath(pth, P(INK, 'stroke', 12))
    elif kind == 'smirk': pth = skia.Path(); pth.moveTo(x - 50, y + 10); pth.quadTo(x + 20, y + 25, x + 70, y - 20); c.drawPath(pth, P(INK, 'stroke', 14))
    elif kind == 'wavy':
        pth = skia.Path(); pth.moveTo(x - 60, y)
        for k in range(4): pth.quadTo(x - 60 + k * 30 + 15, y + (-18 if k % 2 else 18), x - 60 + (k + 1) * 30, y)
        c.drawPath(pth, P(INK, 'stroke', 12))
    elif kind == 'frown': pth = skia.Path(); pth.moveTo(x - 60, y + 30); pth.quadTo(x, y - 30, x + 60, y + 30); c.drawPath(pth, P(INK, 'stroke', 14))
    elif kind == 'shout':
        pth = skia.Path(); pth.addOval(skia.Rect(x - 60, y - 45, x + 60, y + 70)); c.drawPath(pth, P(skia.Color(110, 25, 30))); c.drawPath(pth, P(INK, 'stroke', 12))
EXPR = {   # eyes, brows (left angle, right angle, height offset), mouth
    'neutral':   ('normal', (0, 0, 0), 'flat'), 'surprised': ('wide', (-8, 8, -40), 'o'),
    'worried':   ('normal', (18, -18, -15), 'wavy'), 'smirk': ('half', (-4, -14, 0), 'smirk'),
    'happy':     ('closed', (-6, 6, -20), 'smile'), 'angry': ('normal', (-20, 20, 10), 'frown'),
    'scared':    ('wide', (22, -22, -35), 'shout'), 'bored': ('half', (0, 0, 5), 'flat'),
}
def face(name):
    surf = skia.Surface(W, H); c = surf.getCanvas()
    sh = skia.GradientShader.MakeLinear([skia.Point(0, H * .25), skia.Point(0, H * .9)], [skia.Color(*SKIN_TOP), skia.Color(*SKIN_BOT)])
    c.drawRect(skia.Rect(0, 0, W, H), skia.Paint(Shader=sh))
    e, (ba, bb, bh), m = EXPR[name]
    c.save(); c.translate(CX, CY); c.scale(1.55, 1.45); c.translate(-CX, -CY)   # big features, like the reference
    for sx, ang in ((-1, ba), (1, bb)):
        ex = CX + sx * 120; eye(c, ex, CY + 20, e, (8 * sx if e == 'wide' else 0, 0))
        if e != 'closed': brow(c, ex, CY - 95 + bh, ang * sx)
    mouth(c, m); c.restore()
    surf.makeImageSnapshot().save(os.path.join(OUT, f'{name}.png'), skia.kPNG)
if __name__ == '__main__':
    for n in EXPR: face(n)
    print('faces:', ', '.join(EXPR))
