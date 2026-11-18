import sys, math
sys.path.insert(0, '/home/claude/pro')
from engine import *

BHX, BHY = W / 2, 820

def s_hook(c, t, d, T):          # slow push toward a lensed black hole, astronaut drifting in
    z = 1 + .06 * t
    backdrop(c, T, par=(-10 * t, -6 * t), zoom=z)
    c.save(); c.translate(W / 2, BHY); c.scale(z, z); c.translate(-W / 2, -BHY)
    black_hole(c, BHX, BHY, 150, T)
    astronaut(c, 250 + 40 * t, 1130 - 40 * t, .62, rot=-28 + 6 * math.sin(T), T=T)
    c.restore()

def s_star(c, t, d, T):          # giant star collapses -> flash -> black hole forms
    backdrop(c, T, par=(0, 10), zoom=1.02)
    u = t / d; col_t = .45
    if u < col_t:
        r = 260 * (1 - .12 * eio(u / col_t)) * (1 + .02 * math.sin(T * 9))
        star(c, BHX, BHY, r, T)
    else:
        v = (u - col_t) / (1 - col_t)
        r = 260 * max(0.0, 1 - eout(v * 6))
        if r > 2: star(c, BHX, BHY, r, T)
        glow(c, BHX, BHY, 700 * eout(v * 3), (255, 240, 210), max(0, 1 - v * 2.2))           # flash
        for k in range(3):                                                                    # shockwaves
            rr = 900 * eout(v * 1.4 - k * .08)
            if rr > 0: c.drawCircle(BHX, BHY, rr, P(C(255, 200, 140, 200 * max(0, 1 - v * 1.3)), 'stroke', 18 - k * 5, blur=6, add=True))
        black_hole(c, BHX, BHY, 120 * eout(v * 1.6), T, a=min(1, v * 2))

def light_paths(R, n=11):
    paths = []
    for i in range(n):
        b = (i - (n - 1) / 2) * .62 * R                  # impact parameter
        x, y, vx, vy = -W, b, 1.0, 0.0; pts = []; captured = False
        for _ in range(900):
            rr = math.hypot(x, y)
            if rr < R: captured = True; break
            if x > W: break
            k = 2.2 * R * R / rr ** 3 * 2.2
            vx -= k * x; vy -= k * y; m = math.hypot(vx, vy); vx, vy = vx / m, vy / m
            x += vx * 6; y += vy * 6; pts.append((x, y))
        paths.append((pts, captured))
    return paths
LP = light_paths(130)

def s_light(c, t, d, T):         # light rays bend around and fall into the event horizon
    backdrop(c, T, zoom=1.04)
    black_hole(c, BHX, BHY, 130, T, a=.85)
    prog = eio(t / (d * .85))
    for k, (pts, cap) in enumerate(LP):
        n = int(len(pts) * min(1, prog * 1.15 - k * .01))
        if n < 2: continue
        path = skia.Path(); path.moveTo(BHX + pts[0][0], BHY + pts[0][1])
        for x, y in pts[1:n]: path.lineTo(BHX + x, BHY + y)
        clr = C(255, 120, 120) if cap else C(140, 230, 255)
        c.drawPath(path, P(clr, 'stroke', 14, blur=10, add=True, alpha=.6))
        c.drawPath(path, P(C(255, 255, 255, 230), 'stroke', 4))
        hx, hy = pts[n - 1]; glow(c, BHX + hx, BHY + hy, 40, (200, 240, 255))
    c.drawCircle(BHX, BHY, 132, P(C(255, 230, 120, 255 * (.5 + .5 * math.sin(T * 4))), 'stroke', 5))   # event horizon highlight

def s_fall(c, t, d, T):          # you fall in; your friend watches from a ship, your clock slows
    backdrop(c, T, par=(0, -20 * t), zoom=1.0)
    black_hole(c, BHX + 120, 980, 125, T)
    u = 1 - math.exp(-t / 1.6)
    ax, ay = 300 + 260 * u, 560 + 300 * u
    astronaut(c, ax, ay, .5, rot=25 + 10 * u, T=T)
    clock(c, ax - 150, ay - 150, 62, T * 4.5 * (1 - u) + 1.2)
    spaceship(c, 250, 1540, .9, T, rot=-6)
    c.drawString('YOUR FRIEND', 120, 1700, skia.Font(TF, 46), P(C(150, 230, 255, 220)))

def s_freeze(c, t, d, T):        # dimmer, redder, frozen at the edge
    backdrop(c, T, zoom=1.08)
    black_hole(c, BHX, BHY, 190, T, spin=.6)
    k = ease(t / (d * .9))
    astronaut(c, BHX + 230, BHY - 40, .42, rot=40, T=T * (1 - k), tint=(1, 1 - .75 * k, 1 - .9 * k), alpha=1 - .55 * k)
    clock(c, BHX + 230, BHY - 260, 50, 1.2 + 2 * (1 - k) * t * .3, a=1 - .5 * k)

def s_you(c, t, d, T):           # from your view: normal time, you cross without noticing
    z = 1.1 + .25 * eio(t / d)
    backdrop(c, T, zoom=z)
    c.save(); c.translate(W / 2, BHY); c.scale(z, z); c.translate(-W / 2, -BHY)
    black_hole(c, BHX, BHY + 60, 260, T, spin=.8)
    c.restore()
    astronaut(c, W / 2, 960 + 30 * math.sin(T * 1.3), .72, rot=-8 + 6 * math.sin(T), wave=1, T=T, visor_reflect=(255, 170, 70))
    clock(c, W / 2 + 230, 760, 58, T * 4.5)

def s_tidal(c, t, d, T):         # small black hole: feet pulled much harder than head
    backdrop(c, T, zoom=1.02)
    black_hole(c, BHX, 1680, 105, T, a=.95)
    st = 1 + .6 * eio(t / d)
    astronaut(c, BHX - 60, 820, .95, stretch=st, T=T)
    a = eout(t / .6)
    hy, fy = 820 - 200 * .95 * st, 820 + 190 * .95 * st
    arrow(c, BHX + 250, hy - 40, BHX + 250, hy + 40, 22, (120, 220, 255), a)
    arrow(c, BHX + 250, fy - 150, BHX + 250, fy + 70, 36, (255, 90, 90), a)
    f = skia.Font(TF, 64)
    c.drawString('HEAD', BHX + 300, hy + 22, f, P(C(170, 235, 255, 255 * a)))
    c.drawString('FEET', BHX + 300, fy + 30, f, P(C(255, 140, 140, 255 * a)))

def s_spag(c, t, d, T):          # stretched like a noodle, spiralling in
    backdrop(c, T, zoom=1.05)
    c.save(); c.translate(BHX, BHY); c.rotate(-6 * t); c.translate(-BHX, -BHY)
    black_hole(c, BHX, BHY, 150, T, spin=1.3)
    prog = eio(min(1, t / (d * .85)))
    for j in range(3):  # noodle strands
        path = skia.Path(); first = True
        for i in range(140):
            a = i / 139
            if a > prog: break
            ang = 3.2 * a * 2 * math.pi + j * .18 + T * .4
            r = 700 * (1 - a) ** 1.1 + 160
            x, y = BHX + r * math.cos(ang), BHY + r * .42 * math.sin(ang)
            path.moveTo(x, y) if first else path.lineTo(x, y); first = False
        c.drawPath(path, P(C(255, 170, 80), 'stroke', 34 - j * 8, blur=12, add=True, alpha=.5))
        c.drawPath(path, P(shader=linear((BHX - 700, 0), (BHX + 700, 0), [C(255, 255, 255), C(255, 220, 160), C(255, 150, 70)]), style='stroke', w=16 - j * 4))
    c.restore()
    if t < d * .35: astronaut(c, 230, 520, .45, stretch=1.6 + 3 * t / d, rot=-40, T=T, alpha=1 - t / (d * .35))

def s_sing(c, t, d, T):          # inside: every path leads to the singularity
    c.clear(C(4, 2, 10))
    for i in range(26):
        ph = (i / 26 + T * .35) % 1
        r = 40 + 1500 * ph ** 2.2
        r_, g_, b_ = (lerp(255, 120, ph), lerp(140, 40, ph), lerp(60, 200, ph))
        c.drawCircle(W / 2, 900, r, P(C(r_, g_, b_, 230 * (1 - ph) * min(1, ph * 6)), 'stroke', 6 + 30 * ph, blur=4 + 10 * ph, add=True))
    for k in range(60):
        th = k * 2.4; ph = (k * .137 + T * .9) % 1
        r0 = 1400 * (1 - ph); r1 = r0 * .82
        c.drawLine(W / 2 + math.cos(th) * r0, 900 + math.sin(th) * r0, W / 2 + math.cos(th) * r1, 900 + math.sin(th) * r1,
                   P(C(220, 200, 255, 200 * ph), 'stroke', 3, add=True))
    pulse = .8 + .2 * math.sin(T * 8)
    glow(c, W / 2, 900, 260 * pulse, (255, 255, 255), .9)
    glow(c, W / 2, 900, 520, (180, 120, 255), .5)
    c.drawCircle(W / 2, 900, 14, P(C(255, 255, 255)))

def s_outro(c, t, d, T):
    backdrop(c, T, zoom=1.0)
    black_hole(c, BHX, 760, 120, T)
    astronaut(c, W / 2 - 250, 1060, .5, rot=-12, wave=1, T=T)
    a = eout(t / .5)
    c.drawString('@Hypotheticool', W / 2 - 110, 1090, skia.Font(TF, 72), P(C(255, 255, 255, 255 * a)))

SCENES = [
    (s_hook, "What would actually happen if you fell into a black hole?"),
    (s_star, "Black holes form when a giant star collapses, squeezing more mass than our Sun into a ball just a few dozen miles wide."),
    (s_light, "Its gravity is so strong that past a boundary called the event horizon, not even light can escape."),
    (s_fall, "Now imagine you're falling in. To a friend watching from far away, you'd seem to slow down..."),
    (s_freeze, "grow dimmer and redder, and appear to freeze at the edge, never quite crossing."),
    (s_you, "But for you, time feels completely normal. You'd drift across the horizon without noticing a thing."),
    (s_tidal, "That is, if the black hole is a giant one. Near a small one, gravity pulls on your feet far harder than on your head."),
    (s_spag, "You'd be stretched thinner and thinner, like a noodle. Scientists really call this spaghettification."),
    (s_sing, "And once inside, every path leads to one place: the singularity, where the laws of physics as we know them break down."),
    (s_outro, "Follow for more what ifs!"),
]
HL = {'BLACK', 'HOLE?', 'HOLE', 'COLLAPSES,', 'COLLAPSES', 'SUN', 'LIGHT', 'EVENT', 'HORIZON,', 'HORIZON', 'FRIEND', 'SLOW', 'DOWN', 'REDDER,', 'FREEZE',
      'NORMAL.', 'NOTHING', 'GIANT', 'FEET', 'HEAD.', 'NOODLE.', 'SPAGHETTIFICATION.', 'SINGULARITY,', 'PHYSICS', 'BREAK', 'WHAT', 'IFS!'}
HL = {re.sub(r'[^A-Z0-9-]', '', h) for h in HL}

if __name__ == '__main__':
    build(SCENES, 'black_hole_pro', '/home/claude/pro/out', HL)
