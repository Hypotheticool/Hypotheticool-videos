"""On the 2nd line of each option (scenes 4, 6, 8, 10) swap the tall 4-row options list for one slim colored tag,
so the 3D subject isn't hidden behind the list (the full list stays on each option's first line)."""
import json
OPTS = ['MARS', 'VENUS', 'JUPITER', 'TITAN']
for i in (4, 6, 8, 10):
    p = f'/home/claude/b3d/skydive/s{i}/meta.json'; m = json.load(open(p))
    for ov in m['overlays']:
        if ov['type'] == 'options' and ov.get('pick') is not None and 'num' not in ov:
            k = ov['pick']; ov.clear(); ov.update({'type': 'options', 'items': [OPTS[k]], 'pick': 0, 'instant': True, 'num': k + 1})
        if ov.get('type') == 'datestamp': ov['y'] = .145
    json.dump(m, open(p, 'w'))
