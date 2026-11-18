"""Narration + music for a topic. Usage: python3 audio_prep.py topic.json  -> writes durs + mix.wav into the topic's folder."""
import sys, json, os, subprocess, re
sys.path.insert(0, '/home/claude/pro')
import numpy as np, soundfile as sf
import engine as E

cfg = json.load(open(sys.argv[1])); out = cfg['root']; os.makedirs(out, exist_ok=True)
clips = E.tts_lines(cfg['lines']); sr = clips[0][1]
durs = [round(len(a) / sr + E.LEAD + E.GAP, 3) for a, _ in clips]
starts = np.concatenate([[0], np.cumsum(durs)[:-1]]); total = float(sum(durs))
n = int(total * sr) + sr; voice = np.zeros(n, np.float32)
for (a, _), s in zip(clips, starts):
    i0 = int((s + E.LEAD) * sr); voice[i0:i0 + len(a)] += a
sf.write(f'{out}/voice_raw.wav', voice, sr)
sf.write(f'{out}/bed.wav', E.music_bed(n, sr, starts[1:], total), sr)
subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', f'{out}/voice_raw.wav', '-i', f'{out}/bed.wav', '-filter_complex',
                '[0]highpass=f=70,equalizer=f=180:t=q:w=1:g=2,equalizer=f=3500:t=q:w=1.2:g=2.5,acompressor=threshold=-20dB:ratio=3:attack=8:release=120:makeup=3,aecho=0.8:0.6:28:0.12,asplit[v][vs];'
                '[1]volume=0.9[m];[m][vs]sidechaincompress=threshold=0.03:ratio=4:attack=20:release=300[md];[v][md]amix=inputs=2:normalize=0,loudnorm=I=-14:TP=-1.2',
                '-ar', '48000', f'{out}/mix.wav'], check=True)
cfg['durs'] = durs; json.dump(cfg, open(sys.argv[1], 'w'), indent=1)
print('durs', durs, 'total', round(total, 1))
