"""Join rendered 3D scenes: crossfades, bloom, upscale, captions/labels, mixed audio -> final mp4."""
import sys, os, json, math, subprocess
sys.path.insert(0, '/home/claude/pro')
import numpy as np, cv2, skia
import engine as E

import re
CFG = json.load(open(sys.argv[1]))
ROOT = CFG['root']; FPS = 24; XF = 0.35
DURS = CFG['durs']; LINES = CFG['lines']
HL = {re.sub(r'[^A-Z0-9-]', '', h.upper()) for h in CFG['hl']}
starts = np.concatenate([[0], np.cumsum(DURS)[:-1]]); total = float(sum(DURS))
caps = []
for i, ln in enumerate(LINES):
    clip = DURS[i] - E.lead(i) - E.GAP
    for words, t0, t1 in E.chunk_words(ln, E.word_times(ln, clip)):
        caps.append((words, max(0, starts[i] + E.lead(i) + t0 - .05), starts[i] + E.lead(i) + t1))
metas = [json.load(open(f'{ROOT}/s{i}/meta.json')) for i in range(len(DURS))]
cache = {}
def scene_frame(i, local):
    n = metas[i]['frames']; f = min(n, max(1, int(local * FPS) + 1))
    key = (i, f)
    if key not in cache:
        if len(cache) > 12: cache.clear()
        im = cv2.imread(f'{ROOT}/s{i}/f_{f:04d}.png', cv2.IMREAD_UNCHANGED).astype(np.float32)
        plates = metas[i].get('plates') or []
        if im.shape[2] == 4 and plates:          # transparent foreground over a pre-rendered background plate
            pth = [p for f0, p in plates if f0 <= f][-1] if any(f0 <= f for f0, _ in plates) else plates[0][1]
            if pth not in cache: cache[pth] = cv2.imread(pth, cv2.IMREAD_COLOR).astype(np.float32)
            a = im[..., 3:4] / 255.0; im = im[..., :3] * a + cache[pth] * (1 - a)
        elif im.shape[2] == 4: im = im[..., :3]
        cache[key] = im
    return cache[key]

def bloom(img):
    br = np.clip(img - 150, 0, None)
    small = cv2.resize(br, (img.shape[1] // 4, img.shape[0] // 4), interpolation=cv2.INTER_AREA)
    g1 = cv2.GaussianBlur(small, (0, 0), 6); g2 = cv2.GaussianBlur(small, (0, 0), 18)
    g = cv2.resize(g1 * .9 + g2 * 1.1, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_LINEAR)
    return np.clip(img + g * .9, 0, 255)

surf = skia.Surface(E.W, E.H); cv = surf.getCanvas()
LBL = skia.Font(E.TF, 66)

def fit_font(txt, maxw, size, minsize=34):
    while size > minsize and skia.Font(E.TF, size).measureText(txt) > maxw: size -= 2
    return skia.Font(E.TF, size)
def pill(x, y, w, h, fill, a, r=26):
    rr = skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, y, w, h), r, r)
    cv.drawRRect(rr, E.P(E.C(0, 0, 0, 120 * a), blur=14)); cv.drawRRect(rr, E.P(E.C(*fill, 235 * a)))
    cv.drawRRect(rr, E.P(E.C(255, 255, 255, 90 * a), 'stroke', 4))
def text_c(txt, cx, y, f, col, a):
    w = f.measureText(txt)
    cv.drawString(txt, cx - w / 2, y, f, E.P(E.C(0, 0, 0, 200 * a), 'stroke', 10))
    cv.drawString(txt, cx - w / 2, y, f, E.P(E.C(*col, 255 * a)))
A_COL, B_COL = (225, 55, 60), (40, 110, 230)
OPT_COLS = [(225, 55, 60), (40, 110, 230), (40, 170, 90), (235, 160, 20)]
def frame(T):
    i = int(np.searchsorted(starts, T, side='right') - 1); i = max(0, min(i, len(DURS) - 1))
    img = scene_frame(i, T - starts[i] + XF)
    if i + 1 < len(DURS) and T > starts[i + 1] - XF:
        u = E.ease((T - (starts[i + 1] - XF)) / XF)
        img = img * (1 - u) + scene_frame(i + 1, T - starts[i + 1] + XF) * u
    img = bloom(img)
    if img.shape[1] != E.W: img = cv2.resize(img, (E.W, E.H), interpolation=cv2.INTER_LANCZOS4)
    img = np.clip(img, 0, 255).astype(np.uint8)
    bgra = np.dstack([img, np.full(img.shape[:2], 255, np.uint8)])
    cv.drawImage(skia.Image.fromarray(np.ascontiguousarray(bgra), colorType=skia.kBGRA_8888_ColorType), 0, 0)
    lt = T - starts[i]
    for ov in metas[i]['overlays']:
        a = 1.0 if (ov['type'] == 'hook' or ov.get('instant')) else E.eout((lt - ov.get('from', .4)) / .5)   # the hook is on screen from frame 1
        if a <= 0: continue
        x, y = ov['pos'][0] * E.W, min(ov['pos'][1] * E.H, 1640)
        if ov['type'] == 'label':
            r, g, b = ov['color']; w = LBL.measureText(ov['text'])
            cv.drawString(ov['text'], x - w / 2, y, LBL, E.P(E.C(0, 0, 0, 220 * a), 'stroke', 12))
            cv.drawString(ov['text'], x - w / 2, y, LBL, E.P(E.C(r, g, b, 255 * a)))
        elif ov['type'] == 'cta':   # loop-friendly call to action at the top of the last scene (no spoken outro)
            f1, f2 = skia.Font(E.TF, 58), skia.Font(E.TF, 74)
            for txt, f, yy, col in [(ov.get('text', 'FOLLOW FOR MORE WHAT IFS'), f1, E.H * .1, (255, 222, 40)), ('@HypotheticoolHQ', f2, E.H * .1 + 84, (255, 255, 255))]:
                w = f.measureText(txt)
                cv.drawString(txt, E.W / 2 - w / 2, yy, f, E.P(E.C(0, 0, 0, 220 * a), 'stroke', 12))
                cv.drawString(txt, E.W / 2 - w / 2, yy, f, E.P(E.C(*col, 255 * a)))
        elif ov['type'] == 'choice':   # Would You Rather banner: A (red) OR B (blue) at the top; win='a'/'b' dims the other
            top, bw, bh = E.H * .085, E.W * .43, 190
            for k, (lab, txt, colr, x0) in enumerate([('A', ov['a'], A_COL, E.W * .045), ('B', ov['b'], B_COL, E.W * .525)]):
                aa = a * (0.35 if ov.get('win') and ov['win'] != lab.lower() else 1)
                pill(x0, top, bw, bh, colr, aa)
                text_c(lab, x0 + bw / 2, top + 64, skia.Font(E.TF, 58), (255, 255, 255), aa)
                words = txt.upper().split(); l1, l2 = ' '.join(words), ''
                if skia.Font(E.TF, 46).measureText(l1) > bw - 30 and len(words) > 1:
                    m = (len(words) + 1) // 2; l1, l2 = ' '.join(words[:m]), ' '.join(words[m:])
                f = fit_font(max(l1, l2, key=len), bw - 30, 46)
                text_c(l1, x0 + bw / 2, top + (122 if l2 else 140), f, (255, 255, 255), aa)
                if l2: text_c(l2, x0 + bw / 2, top + 170, f, (255, 255, 255), aa)
            cv.drawCircle(E.W / 2, top + bh / 2, 52, E.P(E.C(20, 20, 30, 240 * a)))
            cv.drawCircle(E.W / 2, top + bh / 2, 52, E.P(E.C(255, 222, 40, 255 * a), 'stroke', 5))
            text_c('OR', E.W / 2, top + bh / 2 + 17, skia.Font(E.TF, 46), (255, 222, 40), a)
        elif ov['type'] == 'options':  # Pick a Scenario: 2-4 numbered options stacked at the top; pick=index highlights one
            items = ov['items']; n = len(items); bh = 104 if n > 3 else 118; gap = 16
            top = E.H * .07
            for k, txt in enumerate(items):
                aa = a * (0.35 if ov.get('pick') is not None and ov['pick'] != k else 1)
                yk = top + k * (bh + gap); pill(E.W * .08, yk, E.W * .84, bh, OPT_COLS[k % 4], aa, 30)
                text_c(str(k + 1), E.W * .08 + 58, yk + bh / 2 + 22, skia.Font(E.TF, 64), (255, 255, 255), aa)
                f = fit_font(txt.upper(), E.W * .84 - 150, 50)
                w = f.measureText(txt.upper()); cx = E.W * .08 + 110 + (E.W * .84 - 130) / 2
                text_c(txt.upper(), cx, yk + bh / 2 + 18, f, (255, 255, 255), aa)
        elif ov['type'] == 'prompt':   # big engagement line, e.g. "COMMENT A OR B" (pos sets y)
            f = fit_font(ov['text'].upper(), E.W * .9, 84)
            text_c(ov['text'].upper(), E.W / 2, y, f, tuple(ov.get('color', (255, 222, 40))), a)
        elif ov['type'] == 'countdown':  # 3-2-1 in the middle over the scene's last secs seconds (pos sets center)
            secs = ov.get('secs', 3); left = DURS[i] - lt
            if 0 < left <= secs:
                nnum = int(math.ceil(left)); ph = nnum - left; sc = 1 + .25 * (1 - E.eout(ph * 3))
                f = skia.Font(E.TF, int(220 * sc))
                cv.drawCircle(x, y - 75, 160, E.P(E.C(0, 0, 0, 150), blur=6))
                text_c(str(nnum), x, y, f, (255, 255, 255), 1)
        elif ov['type'] == 'hook':   # big bold on-screen hook (2-6 words) at the top from frame 1, gentle punch-in
            words = ov['text'].upper().split(); rows, cur = [], ''
            for w_ in words:
                t_ = (cur + ' ' + w_).strip()
                if skia.Font(E.TF, 104).measureText(t_) > E.W * .88 and cur: rows.append(cur); cur = w_
                else: cur = t_
            rows.append(cur); sc = 1 + .06 * (1 - E.eout(min(lt / .35, 1))); f = skia.Font(E.TF, int(104 * sc))
            col = tuple(ov.get('color', (255, 222, 40))); y0 = ov.get('y', .11) * E.H
            for k, row in enumerate(rows[:3]): text_c(row, E.W / 2, y0 + k * 112 * sc, f, col if k == len(rows[:3]) - 1 else (255, 255, 255), 1)
        elif ov['type'] == 'handle':
            f = skia.Font(E.TF, 80); w = f.measureText('@HypotheticoolHQ')
            cv.drawString('@HypotheticoolHQ', E.W / 2 - w / 2 + 120, y, f, E.P(E.C(0, 0, 0, 220 * a), 'stroke', 14))
            cv.drawString('@HypotheticoolHQ', E.W / 2 - w / 2 + 120, y, f, E.P(E.C(255, 255, 255, 255 * a)))
    for words, t0, t1 in caps:
        if t0 <= T < max(t1, t0 + .25):
            E.caption(cv, words, t0, T, HL, y=(1470 if E.H > E.W else E.H * .9)); break
    return surf.makeImageSnapshot().toarray()

if __name__ == '__main__':
    out = sys.argv[2]
    if len(sys.argv) > 3:      # preview stills at given times
        from PIL import Image
        for t in sys.argv[3:]:
            Image.fromarray(frame(float(t))[..., [2, 1, 0]]).save(f'{ROOT}/comp_{t}.jpg', quality=88)
        sys.exit()
    nf = int(total * FPS); master = out + '.master.mp4'
    p = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s', f'{E.W}x{E.H}', '-r', str(FPS), '-i', '-',
                          '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '14', '-pix_fmt', 'yuv420p', master + '.tmp.mp4'], stdin=subprocess.PIPE)
    for k in range(nf):
        p.stdin.write(frame(k / FPS).tobytes())
    p.stdin.close(); assert p.wait() == 0; os.replace(master + '.tmp.mp4', master)
    # final encode: quality CRF 18, but cap the file under ~95 MB (GitHub raw limit) with a 2-pass bitrate if needed
    vb = int((95e6 * 8 / total - 160e3) * .97)
    args = ['-c:v', 'libx264', '-preset', 'slow', '-tune', 'animation', '-pix_fmt', 'yuv420p']
    if vb < 8e6:
        for ps in (1, 2):
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', master, '-i', f'{ROOT}/mix.wav', '-map', '0:v', '-map', '1:a'] + args +
                           ['-b:v', str(vb), '-maxrate', str(int(vb * 1.5)), '-bufsize', str(vb * 2), '-pass', str(ps), '-passlogfile', f'{ROOT}/x264',
                            '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', '-shortest'] + (['-f', 'mp4', '/dev/null'] if ps == 1 else [out + '.tmp.mp4']), check=True)
    else:
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', master, '-i', f'{ROOT}/mix.wav', '-map', '0:v', '-map', '1:a'] + args +
                       ['-crf', '18', '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', '-shortest', out + '.tmp.mp4'], check=True)
    os.replace(out + '.tmp.mp4', out); print('done', os.path.getsize(out))
    if CFG.get('chapters'):
        for ch in CFG['chapters']:
            st = int(starts[ch['line']]); print(f'CHAPTER {st // 60}:{st % 60:02d} {ch["title"]}')
