"""Join rendered 3D scenes: crossfades, bloom, upscale, captions/labels, mixed audio -> final mp4."""
import sys, os, json, math, subprocess
sys.path.insert(0, '/home/claude/pro')
import numpy as np, cv2, skia
import engine as E

ROOT = '/home/claude/b3d/bh'
FPS = 24; XF = 0.35
DURS = [3.0, 7.6, 6.4, 5.6, 4.4, 6.0, 6.9, 5.7, 7.3, 1.8]
sys.path.insert(0, '/home/claude/pro')
from black_hole import SCENES, HL
LINES = [ln for _, ln in SCENES]
starts = np.concatenate([[0], np.cumsum(DURS)[:-1]]); total = float(sum(DURS))
caps = []
for i, ln in enumerate(LINES):
    clip = DURS[i] - E.LEAD - E.GAP
    for words, t0, t1 in E.chunk_words(ln, E.word_times(ln, clip)):
        caps.append((words, starts[i] + E.LEAD + t0 - .05, starts[i] + E.LEAD + t1))
metas = [json.load(open(f'{ROOT}/s{i}/meta.json')) for i in range(len(DURS))]
cache = {}
def scene_frame(i, local):
    n = metas[i]['frames']; f = min(n, max(1, int(local * FPS) + 1))
    key = (i, f)
    if key not in cache:
        if len(cache) > 6: cache.clear()
        cache[key] = cv2.imread(f'{ROOT}/s{i}/f_{f:04d}.png', cv2.IMREAD_COLOR).astype(np.float32)
    return cache[key]

def bloom(img):
    br = np.clip(img - 150, 0, None)
    small = cv2.resize(br, (img.shape[1] // 4, img.shape[0] // 4), interpolation=cv2.INTER_AREA)
    g1 = cv2.GaussianBlur(small, (0, 0), 6); g2 = cv2.GaussianBlur(small, (0, 0), 18)
    g = cv2.resize(g1 * .9 + g2 * 1.1, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_LINEAR)
    return np.clip(img + g * .9, 0, 255)

surf = skia.Surface(E.W, E.H); cv = surf.getCanvas()
LBL = skia.Font(E.TF, 66)
def frame(T):
    i = int(np.searchsorted(starts, T, side='right') - 1); i = max(0, min(i, len(DURS) - 1))
    img = scene_frame(i, T - starts[i] + XF)
    if i + 1 < len(DURS) and T > starts[i + 1] - XF:
        u = E.ease((T - (starts[i + 1] - XF)) / XF)
        img = img * (1 - u) + scene_frame(i + 1, T - starts[i + 1] + XF) * u
    img = bloom(img)
    img = cv2.resize(img, (E.W, E.H), interpolation=cv2.INTER_LANCZOS4)
    img = np.clip(img, 0, 255).astype(np.uint8)
    bgra = np.dstack([img, np.full(img.shape[:2], 255, np.uint8)])
    cv.drawImage(skia.Image.fromarray(np.ascontiguousarray(bgra), colorType=skia.kBGRA_8888_ColorType), 0, 0)
    lt = T - starts[i]
    for ov in metas[i]['overlays']:
        a = E.eout((lt - .4) / .5)
        if a <= 0: continue
        x, y = ov['pos'][0] * E.W, min(ov['pos'][1] * E.H, 1640)
        if ov['type'] == 'label':
            r, g, b = ov['color']; w = LBL.measureText(ov['text'])
            cv.drawString(ov['text'], x - w / 2, y, LBL, E.P(E.C(0, 0, 0, 220 * a), 'stroke', 12))
            cv.drawString(ov['text'], x - w / 2, y, LBL, E.P(E.C(r, g, b, 255 * a)))
        elif ov['type'] == 'handle':
            f = skia.Font(E.TF, 80); w = f.measureText('@Hypotheticool')
            cv.drawString('@Hypotheticool', E.W / 2 - w / 2 + 120, y, f, E.P(E.C(0, 0, 0, 220 * a), 'stroke', 14))
            cv.drawString('@Hypotheticool', E.W / 2 - w / 2 + 120, y, f, E.P(E.C(255, 255, 255, 255 * a)))
    for words, t0, t1 in caps:
        if t0 <= T < max(t1, t0 + .25):
            E.caption(cv, words, t0, T, HL, y=1470); break
    return surf.makeImageSnapshot().toarray()

if __name__ == '__main__':
    out = sys.argv[1]
    if len(sys.argv) > 2:      # preview stills at given times
        from PIL import Image
        for t in sys.argv[2:]:
            Image.fromarray(frame(float(t))[..., [2, 1, 0]]).save(f'{ROOT}/comp_{t}.jpg', quality=88)
        sys.exit()
    nf = int(total * FPS)
    p = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s', f'{E.W}x{E.H}', '-r', str(FPS), '-i', '-',
                          '-i', '/home/claude/pro/out/mix.wav', '-map', '0:v', '-map', '1:a', '-c:v', 'libx264', '-preset', 'slow', '-crf', '18',
                          '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', '-shortest', out + '.tmp.mp4'], stdin=subprocess.PIPE)
    for k in range(nf):
        p.stdin.write(frame(k / FPS).tobytes())
    p.stdin.close(); assert p.wait() == 0
    os.replace(out + '.tmp.mp4', out); print('done', os.path.getsize(out))
