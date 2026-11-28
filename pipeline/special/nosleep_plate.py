"""WYR: 3 days without sleep or 3 days without water? One Cycles still per plate (animated in 2D by nosleep_anim.py).
Reuses the night-room helpers from quake_plate.py (exec'd up to its plates section).
python3 nosleep_plate.py <plate> [res_scale] -> nosleep/plates/<plate>.png (+ .txt with projected 2D points)
Option A (no sleep, night bedroom, warm lamp + blue moonlight, Kai): bed (wide, Kai sitting up awake at 3 AM, alarm clock),
  bedcu (close on Kai's tired face), bedfoot (from the foot of the bed, Kai scared, dark corners for the hallucinations),
  brain (real BodyParts3D cerebral gyri, cerebellum, brainstem)
Option B (no water, desert under a high sun, Leo): desert (wide, Leo trudging over dunes), desertcu (close on Leo, worried),
  slump (Leo down on his knees in the sand, sun behind: the hook), kidney (real BodyParts3D kidneys, renal vessels, ureters),
  coolroom (Leo lying in bed in a dim, cool bedroom)"""
import sys, os, math, random
QP = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'quake_plate.py')
src = open(QP).read().split('# ------------------------------------------------------------------ plates')[0]
exec(compile(src, QP, 'exec'))
OUT = '/home/claude/b3d/nosleep/plates'; os.makedirs(OUT, exist_ok=True)
PLATE = name; R = math.radians

def person(who, loc, yaw=0.0, h=1.2, expr='neutral', arms=None, legs=None, tilt=(0, 0)):
    root, parts = kit.character(who, (0, 0, 0), h)
    parts['face_mat'].node_tree.nodes['expr'].outputs[0].default_value = kit.EXPRS.index(expr)
    for a, r in (arms or {}).items(): parts[a].rotation_euler = tuple(R(v) for v in r)
    for a, r in (legs or {}).items(): parts[a].rotation_euler = tuple(R(v) for v in r)
    root.rotation_euler = (R(tilt[0]), R(tilt[1]), R(yaw)); root.location = loc
    return root, parts

def bedroom2(cool=False):
    """night bedroom: plank floor, teal wall with a moonlit window, wood bed, nightstand + lamp + alarm clock, a dresser"""
    flat_world((.008, .012, .02), 1.0)
    box('floor', (0, 0, -.01), (7, 7, .02), plank_mat(), 0); wm = wall_mat('bw', (.09, .16, .2) if not cool else (.07, .13, .2))
    box('bwall', (0, 1.45, 1.4), (7, .1, 2.8), wm, 0); box('lwall', (-1.9, 0, 1.4), (.1, 7, 2.8), wm, 0)
    # window on the left wall: night sky + frame + moonlight
    box('sky', (-1.84, .2, 1.5), (.02, 1.0, 1.1), night_sky_mat(), 0)
    fr = M('wframe', (.75, .74, .7), .5)
    for dz in (-.55, .55): box('wf', (-1.83, .2, 1.5 + dz), (.06, 1.08, .06), fr, .005)
    for dy in (-.5, .5, 0): box('wf', (-1.83, .2 + dy, 1.5), (.06, .05, 1.14), fr, .005)
    box('wfm', (-1.83, .2, 1.5), (.06, 1.0, .04), fr, .005)
    wd = wood_mat('bedw', (.3, .17, .08))
    box('head', (0, 1.33, .6), (1.2, .08, 1.2), wd, .02); box('foot', (0, -.75, .35), (1.2, .06, .5), wd, .02)
    box('frame', (0, .3, .2), (1.15, 2.1, .25), wd, .02)
    box('mattress', (0, .3, .42), (1.05, 2.0, .2), fabric('mat', (.85, .85, .82)), .05)
    box('blanket', (0, -.05, .56), (1.12, 1.45, .08), fabric('blank', (.12, .28, .42)), .05)
    pil = box('pillow', (0, 1.12, .62), (.7, .32, .14), fabric('pw', (.92, .92, .9)), .06); pil.rotation_euler = (R(-15), 0, 0)
    box('nst', (.95, 1.1, .3), (.5, .42, .6), wd, .01)
    lamp_m = kit.mat_emit('shade', (1, .68, .36), 2.2) if not cool else M('nl', (.85, .75, .55), .6)
    cyl('nlbase', (1.05, 1.15, .64), .05, .08, M('lb', (.1, .08, .06), .3, .8)); cyl('nlamp', (1.05, 1.15, .82), .12, .2, lamp_m, r2=.08)
    if not cool: point('nl', (1.05, 1.15, .82), 26, (1, .6, .3), .06)
    # alarm clock: dark body, glowing red screen facing the bed/camera
    clk = box('clock', (.82, .98, .66), (.2, .08, .11), M('clkb', (.02, .02, .025), .35), .01, rot=(0, 0, R(-25)))
    box('clkscr', (.81, .955, .665), (.16, .005, .07), kit.mat_emit('clks', (1, .08, .04), 2.5 if not cool else .6), 0, rot=(0, 0, R(-25)))
    PTS['clock'] = (.81, .95, .665)
    # dresser + picture by the back wall
    box('dresser', (-1.25, 1.15, .45), (.8, .5, .9), wd, .01)
    box('pic', (-1.25, 1.39, 1.55), (.5, .03, .4), M('picf', (.05, .04, .03), .4), .005)
    area('moon', (-3.0, .2, 1.9), (0, .4, .6), 140 if not cool else 220, (.4, .55, 1), 1.2)
    area('fill', (1.4, -3, 2.2), (0, .5, .6), 18 if not cool else 40, (.5, .6, 1), 3)
    haze(.012, (0, 0, 1.3), (3, 3, 1.4))

def desert(sun_el=38, sun_rot=150):
    kit.sky(sun_elevation=sun_el, sun_rotation=sun_rot, strength=.16, sun_lamp_energy=5.0)
    sc.view_settings.exposure = float(os.environ.get('EXPO', -1.7))
    ter = kit.terrain(size=120, height=3.2, scale=2.2, kind='desert', seed=5, res=8); ter.location = (0, 30, -1.6)
    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0)); g = bpy.context.object
    s = g.modifiers.new('s', 'SUBSURF'); s.subdivision_type = 'SIMPLE'; s.levels = s.render_levels = 6
    tx = bpy.data.textures.new('ripples', 'CLOUDS'); tx.noise_scale = .9; d = g.modifiers.new('d', 'DISPLACE'); d.texture = tx; d.strength = .08
    g.data.materials.append(kit.mat_pbr('sand'))
    return ter

def leo_walk(loc, yaw, h=1.25, expr='worried'):
    return person('leo', loc, yaw, h, expr, {'arm_l': (40, -10, 0), 'arm_r': (-100, 0, -30)}, {'leg_l': (-28, 0, 0), 'leg_r': (24, 0, 0)}, (8, 0))

c = None
if PLATE in ('bed', 'bedcu', 'bedfoot'):
    bedroom2()
    expr = {'bed': 'worried', 'bedcu': 'bored', 'bedfoot': 'scared'}[PLATE]
    h = 1.15; z = .52 - .22 * h
    kr, kp = person('kai', (0, .95, z), 0, h, expr, {'arm_l': (-35, 0, 15), 'arm_r': (-35, 0, -15)} if PLATE != 'bedfoot' else {'arm_l': (-60, 0, 25), 'arm_r': (-60, 0, -25)},
                    {'leg_l': (90, 0, 0), 'leg_r': (90, 0, 0)})
    PTS['kai'] = (0, .95, z + .8 * h); PTS['face'] = (0, .78, z + .8 * h)
    if PLATE == 'bed': c = cam((.5, -1.9, 1.4), (.15, .75, .9), 28)
    elif PLATE == 'bedcu': c = cam((.25, -.45, 1.3), (0, .95, z + .8 * h), 45, 2.0)
    else: c = cam((-.3, -1.9, 1.05), (0, .9, .95), 30, 4.0)
elif PLATE == 'asleep':     # Kai finally asleep: on his back, head on the pillow, lamp still on
    bedroom2()
    person('kai', (0, -.2, .66), 0, 1.15, 'bored', {'arm_l': (0, -8, 0), 'arm_r': (0, 8, 0)}, None, (-90, 0))
    box('blanket2', (0, .05, .7), (1.0, 1.0, .06), fabric('blank2', (.12, .28, .42)), .04)
    PTS['kai'] = (0, .95, .8)
    c = cam((.9, -1.2, 1.5), (0, .6, .6), 30, 4.0)
elif PLATE == 'coolroom':
    bedroom2(cool=True)
    lr, lp = person('leo', (0, -.22, .66), 0, 1.15, 'bored', {'arm_l': (0, -10, 0), 'arm_r': (0, 10, 0)}, None, (-90, 0))
    PTS['leo'] = (0, 1.0, .75)
    c = cam((1.4, -1.8, 1.8), (0, .5, .55), 28)
elif PLATE in ('desert', 'desertcu', 'slump'):
    desert(22, 165) if PLATE == 'slump' else desert()
    if PLATE == 'desert':
        leo_walk((0, 0, 0), 20, 1.25, 'worried')
        # footprints trailing behind him
        fp = M('fprint', (.33, .21, .11), .9)
        for k in range(12):
            box('fp', (.25 * (k % 2) - .12 + .2 * k, .9 + .55 * k, .005), (.09, .22, .01), fp, .02, rot=(0, 0, R(20)))
        PTS['leo'] = (0, 0, 1.0)
        c = cam((1.6, -4.2, 1.6), (0, 1.5, .8), 26)
    elif PLATE == 'desertcu':
        leo_walk((0, 0, 0), 15, 1.25, 'worried')
        PTS['face'] = (0, -.05, 1.0)
        c = cam((.35, -1.25, 1.05), (0, 0, .98), 45, 2.2)
    else:
        # kneeling in the sand, one hand down, head up toward the sun
        lr, lp = person('leo', (0, 0, .1 * 1.25), 12, 1.25, 'scared', {'arm_l': (-20, -20, 0), 'arm_r': (-60, 0, -20)},
                        {'leg_l': (-100, 0, 0), 'leg_r': (-100, 0, 0)}, (10, 0))
        PTS['face'] = (0, -.1, 1.05)
        c = cam((.25, -2.1, .75), (0, 0, .85), 32, 3.0)
elif PLATE == 'brain':
    flat_world((.006, .01, .018), 1.0)
    an = kit.anatomy(r'gyrus|gyri|lobule|occipital lobe|cerebellum|^pons$|medulla oblongata|midbrain|insula', size=2.4)
    an.rotation_euler = (0, 0, R(-25))
    area('key', (2.0, -3.0, 2.6), (0, 0, 0), 300, (1, .78, .6), 2.5); area('rim', (-2.4, 2.4, 1.8), (0, 0, 0), 420, (.45, .6, 1), 2.5)
    area('fill', (-2, -3, -1), (0, 0, 0), 70, (.5, .65, 1), 3)
    c = cam((1.6, -4.4, 2.6), (0, 0, .05), 50, 5.6)
elif PLATE == 'kidney':
    flat_world((.006, .01, .018), 1.0)
    an = kit.anatomy(r'kidney$', r'renal (artery|vein)', r'ureter', r'inferior vena cava', size=3.2)
    area('key', (1.5, -3.5, 2.0), (0, 0, 0), 280, (1, .75, .55), 2.5); area('rim', (-2.2, 2.5, 1.5), (0, 0, 0), 360, (.45, .6, 1), 2.5)
    area('fill', (-2, -3, -1), (0, 0, 0), 60, (.5, .65, 1), 3)
    c = cam((0, -5.6, .9), (0, 0, .6), 50, 6.0)
if PTS and c:
    bpy.context.view_layer.update()
    with open(f'{OUT}/{PLATE}.txt', 'w') as f:
        for k, p in PTS.items(): f.write(f'{k} {proj(c, p)[0]} {proj(c, p)[1]}\n')
sc.render.filepath = f'{OUT}/{PLATE}.png'; bpy.ops.render.render(write_still=True); print('ok', PLATE)
