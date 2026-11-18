"""FORMAT EXAMPLE ONLY: shows how to build 2D motion-graphics scenes for a long video with mg.py. The numbers in it are placeholders, not checked facts. Run with HC_W=1920 HC_H=1080."""
import sys, json; sys.path.insert(0, '/home/claude/pro')
import mg
cfg = json.load(open('/home/claude/lvtest/topic.json')); D = cfg['durs']
S = {0: mg.title_card('Why do we have tides?', 'The Moon vs the Sun'),
     1: mg.bars('Share of tide-raising force', [('Moon', 69), ('Sun', 31)], unit='%'),
     2: mg.timeline('Tides through time', [('4 billion yrs ago', 'Moon much closer, far bigger tides'), ('Today', 'Moon drifts away about 3.8 cm a year'), ('Future', 'Tides slowly weaken')])}
for i in map(int, sys.argv[1:]): print(i, mg.render_scene(S[i], D[i], .75, f"{cfg['root']}/s{i}"))
