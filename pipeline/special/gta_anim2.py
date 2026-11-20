"""Animate a scene over its real-Earth plate: slow push-in/pull-back, glowing route drawing, travelling car light,
pins popping on real places. python3 gta_anim.py <scene>  -> gta6/s<scene>/f_####.png + meta.json"""
import sys, math, json, os
import numpy as np, cv2, skia
CFG = json.load(open('/home/claude/b3d/gta6v2/topic.json'))
FPS = 24; PAD = .75; idx = int(sys.argv[1]); D = CFG['durs'][idx]; NF = int(math.ceil((D + PAD) * FPS))
F = lambda sec: 1 + int(round((sec + .35) * FPS))
OW, OH = 1080, 1920
PLATE = [0, 1, 3, 7, 2, 6, 6, 5, 0][idx]   # reuse the real-Earth plates rendered for the first cut
plate = cv2.imread(f'/home/claude/b3d/gta6/plates/p{PLATE}.png'); P = json.load(open(f'/home/claude/b3d/gta6/plates/p{PLATE}.json'))
PW, PH = P['size']; BASE = OW / PW
ease = lambda t: .5 - .5 * math.cos(math.pi * min(max(t, 0), 1))
GOLD = (255, 205, 70); BLUE = (110, 215, 255); WHITE = (255, 255, 255)
SPEC = {
 0: dict(z=(1.0, 1.12), pan=((0, 0), (0, -.04)), route='full', car=(0, 256, 0, 1.0)),
 1: dict(z=(1.14, 1.0), pan=((0, .03), (0, 0)), route='full'),
 2: dict(z=(1.0, 1.08), pan=((0, 0), (0, -.01)), route='none'),
 3: dict(z=(1.0, 1.1), pan=((0, .02), (0, -.03)), route='full', car=(0, 256, 0, 1.0)),
 4: dict(z=(1.0, 1.06), pan=((0, 0), (0, .01)), route='faint', pins=[('miami', .9, GOLD), ('everglades', 3.0, (120, 230, 120)), ('keys', 5.0, BLUE)]),
 5: dict(z=(1.0, 1.05), pan=((0, 0), (0, 0)), route=(.2, 4.6), pins=[('keywest', .2, GOLD), ('pensacola', 4.6, GOLD)]),
 6: dict(z=(1.05, 1.12), pan=((0, 0), (0, -.01)), route='full', car=(0, 60, 0, 1.0)),
 7: dict(z=(1.0, 1.16), pan=((0, -.02), (0, .03)), route='none'),
 8: dict(z=(1.12, 1.0), pan=((0, -.04), (0, 0)), route='full'),
}[idx]
LABELS = {
 0: [], 1: [('THE REAL LEONIDA = FLORIDA', 'center', GOLD, .6)],
 2: [('ROCKSTAR: LEONIDA IS', (.5, .25), WHITE, .3), ('~2x GTA 5\'S MAP', (.5, .30), GOLD, .3)],
 3: [('GTA 6: ~11 MIN', (.5, .25), GOLD, .3), ("ACROSS THE MAP (KOTAKU'S TEST)", (.5, .30), WHITE, .3)],
 4: [('THE REAL LEONIDA', (.5, .2), WHITE, 0), ('VICE CITY = MIAMI', (.5, .255), GOLD, .9), ('GRASSRIVERS = EVERGLADES', (.5, .31), (150, 240, 150), 3.0), ('LEONIDA KEYS = FLORIDA KEYS', (.5, .365), BLUE, 5.0)],
 5: [('KEY WEST', 'keywest', WHITE, .4), ('PENSACOLA', 'pensacola', WHITE, 4.6), ('REAL DRIVE: ~830 MILES', (.5, .24), GOLD, 1.0)],
 6: [('REAL FLORIDA: 12+ HOURS', (.5, .24), GOLD, .2), ('NO STOPS', (.5, .29), WHITE, .9)],
 7: [('65,758 SQ MI', (.5, .24), GOLD, .3), ('1,350 MILES OF COAST', (.5, .29), WHITE, 3.6)],
 8: [],
}[idx]
os.makedirs(f'/home/claude/b3d/gta6v2/s{idx}', exist_ok=True)

def view(f):
    t = ease((f - 1) / max(NF - 1, 1)); z = SPEC['z'][0] + (SPEC['z'][1] - SPEC['z'][0]) * t
    (px0, py0), (px1, py1) = SPEC['pan']; cx = PW * (.5 + px0 + (px1 - px0) * t); cy = PH * (.5 + py0 + (py1 - py0) * t)
    return z, cx, cy
def to_out(p, z, cx, cy): return ((p[0] - cx) * BASE * z + OW / 2, (p[1] - cy) * BASE * z + OH / 2)

def glow_path(cv, pts, col, w, alpha=1.0, glow=True):
    if len(pts) < 2: return
    path = skia.Path(); path.moveTo(*pts[0])
    for p in pts[1:]: path.lineTo(*p)
    if glow:
        cv.drawPath(path, skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=w * 4, StrokeCap=skia.Paint.kRound_Cap, StrokeJoin=skia.Paint.kRound_Join,
                                     Color=skia.Color(*col, int(110 * alpha)), MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, w * 2.2)))
    cv.drawPath(path, skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=w, StrokeCap=skia.Paint.kRound_Cap, StrokeJoin=skia.Paint.kRound_Join, Color=skia.Color(255, 250, 225, int(255 * alpha))))

def dot(cv, p, r, col, a=1.0):
    cv.drawCircle(p[0], p[1], r * 3.2, skia.Paint(AntiAlias=True, Color=skia.Color(*col, int(120 * a)), MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, r * 1.8)))
    cv.drawCircle(p[0], p[1], r, skia.Paint(AntiAlias=True, Color=skia.Color(255, 255, 245, int(255 * a))))

meta_labels = []
for f in range(1, NF + 1):
    z, cx, cy = view(f); s = BASE * z
    M = np.float32([[s, 0, OW / 2 - cx * s], [0, s, OH / 2 - cy * s]])
    img = cv2.warpAffine(plate, M, (OW, OH), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
    rgba = cv2.cvtColor(img, cv2.COLOR_BGR2RGBA)
    surf = skia.Surface(rgba, colorType=skia.kRGBA_8888_ColorType); cv = surf.getCanvas()
    route = [to_out(p, z, cx, cy) for p in P['route'] if p[2] > 0]
    r = SPEC['route']
    if r == 'full': glow_path(cv, route, GOLD, 5.5)
    elif r == 'faint': glow_path(cv, route, GOLD, 4, .45, glow=False)
    elif isinstance(r, tuple):
        k = ease((f - F(r[0])) / max(F(r[1]) - F(r[0]), 1)); n = max(2, int(len(route) * k)) if f >= F(r[0]) else 0
        glow_path(cv, route[:n], GOLD, 6.5)
        if 1 < n < len(route): dot(cv, route[n - 1], 7, GOLD)
    if 'ns' in SPEC:
        a, b = SPEC['ns']; k = ease((f - F(a)) / max(F(b) - F(a), 1)); ns = [to_out(p, z, cx, cy) for p in P['ns']]
        n = int(len(ns) * k) if f >= F(a) else 0
        if n > 1: glow_path(cv, ns[:n], BLUE, 6.5)
    if 'car' in SPEC:
        i0, i1, t0, t1 = SPEC['car']; k = (f - 1) / max(NF - 1, 1); i = int(i0 + (i1 - i0) * k)
        p = P['route'][min(i, len(P['route']) - 1)]; dot(cv, to_out(p, z, cx, cy), 7, WHITE)
    for name, sec, col in SPEC.get('pins', []):
        if f >= F(sec):
            pop = min((f - F(sec)) / 6, 1); sc_ = 1 + .6 * math.sin(math.pi * pop) if pop < 1 else 1
            dot(cv, to_out(P['places'][name], z, cx, cy), 9 * sc_, col)
    out = cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGR)
    cv2.imwrite(f'/home/claude/b3d/gta6v2/s{idx}/f_{f:04d}.png', out)
# labels: anchored to the real place at the moment they appear (compose fades them in)
z, cx, cy = view(NF // 2)
ovs = []
for text, where, col, sec in LABELS:
    if isinstance(where, str):
        x, y = to_out(P['places'][where], z, cx, cy); x = min(max(x / OW, .22), .78); y = min(max(y / OH - .035, .16), .62)
    else: x, y = where
    ovs.append({'type': 'label', 'text': text, 'pos': [x, y], 'color': list(col), 'from': sec})
if idx == 0: ovs.append({'type': 'versus', 'left': ['GTA 6', '~11 MIN'], 'right': ['REAL FLORIDA', '12+ HRS'], 'instant': True})
if idx == 8: ovs.append({'type': 'cta'})
json.dump({'frames': NF, 'overlays': ovs}, open(f'/home/claude/b3d/gta6v2/s{idx}/meta.json', 'w'))
print('scene', idx, 'frames', NF)
