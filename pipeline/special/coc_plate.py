"""Story Short: the snow buried the tailpipe. One Cycles still per plate (animated in 2D by coc_anim.py).
python3 coc_plate.py <plate> [res_scale]  -> coc/plates/<plate>.png
Reuses the cartoon sedan, cast, snow and pine helpers from sink_plate.py (exec'd up to its plates section).
Exterior (blizzard night on a highway): rear (hook: car buried to the bumper, drift over the tailpipe, red taillights), wide (stuck cars in a line),
  pipe (macro: tailpipe under the drift), pipe_clear (dug out, exhaust puff), dig (Kai outside digging at the back), side (safe: window cracked, dome light),
  jam (1978-style: long line of stranded cars and trucks on a highway)
Interior: int (both front seats from the dash), cu_leo (cold/worried), cu_leo_sleepy (eyes heavy), cu_kai (shouting)"""
import sys, os, math, random
SP = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sink_plate.py')
src = open(SP).read().split('# ------------------------------------------------------------------ plates')[0]
exec(compile(src, SP, 'exec'))          # defines kit, bpy, W, H, sc, car(), cast(), seated(), snow_mat(), pine(), area(), point(), cam(), box(), cyl(), haze()
OUT = '/home/claude/b3d/coc/plates'; os.makedirs(OUT, exist_ok=True)

def night_world(col=(.012, .02, .04), strength=1.0):
    w = bpy.data.worlds.new('night'); bpy.context.scene.world = w; nt, N, L = kit.nodes(w)
    out = N.new('ShaderNodeOutputWorld'); bg = N.new('ShaderNodeBackground'); bg.inputs['Color'].default_value = (*col, 1); bg.inputs['Strength'].default_value = strength
    L.new(bg.outputs[0], out.inputs['Surface'])

def lump(nm, loc, scale, mat, rot=0.0, seed=0):
    """a smooth snow drift: squashed, noise-displaced sphere"""
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, location=loc); o = bpy.context.object; o.name = nm; o.scale = scale; o.rotation_euler = (0, 0, rot)
    tx = bpy.data.textures.new(f'dn{nm}', 'CLOUDS'); tx.noise_scale = .6; d = o.modifiers.new('d', 'DISPLACE'); d.texture = tx; d.strength = .12
    o.data.materials.append(mat); bpy.ops.object.shade_smooth(); return o

def ground(mat, z=.1):
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, z)); g = bpy.context.object; g.scale = (300, 300, 1); g.data.materials.append(mat); return g

def highway(sn, y_lanes=(0,), length=400):
    """snow-covered highway: packed snow with dark wheel ruts, snowbanks on both sides, a few reflector posts"""
    rut = M('rut', (.3, .33, .38), .5)
    for x in (-1.2, -.45, .45, 1.2):
        box(f'rut{x}', (x * .6, 0, .105), (.14, length, .005), rut, 0)
    for side in (-1, 1):
        bpy.ops.mesh.primitive_cylinder_add(radius=1.0, depth=length, location=(side * 4.2, 0, .1), rotation=(math.pi / 2, 0, 0), vertices=32)
        b = bpy.context.object; b.scale = (1.6, 1, .55); b.data.materials.append(sn); bpy.ops.object.shade_smooth()
        for k in range(-25, 26):
            box(f'post{side}{k}', (side * 3.4, k * 8.0, .55), (.07, .07, .9), M('post', (.8, .8, .75), .5), .01)
            box(f'refl{side}{k}', (side * 3.4, k * 8.0 - .04, .9), (.05, .02, .08), kit.mat_emit('refl', (1, .55, .15), 3), 0)

def tailpipe(root, clear=False, puff=False):
    """chrome exhaust tip under the rear bumper (car frame: rear = -Y)"""
    steel = M('pipe', (.55, .55, .57), .25, 1.0); sootm = M('soot', (.02, .02, .02), .9)
    p = cyl('tailpipe', (.5, -1.86, .26), .055, .32, steel, rot=(math.pi / 2, 0, 0), parent=root)
    cyl('pipe_in', (.5, -2.0, .26), .045, .06, sootm, rot=(math.pi / 2, 0, 0), parent=root)
    return p

def rear_drift(root_loc, sn, height=.62, seed=1):
    x, y, z = root_loc
    lump('driftR', (x + .1, y - 2.15, .1), (1.7, .95, height), sn, seed=seed)
    lump('driftR2', (x - .9, y - 1.9, .1), (.8, .7, height * .8), sn, seed=seed + 1)
    lump('driftR3', (x + 1.2, y - 1.4, .1), (.6, 1.2, height * .7), sn, seed=seed + 2)

def roof_snow(root, sn, z=1.5):
    o = lump('roofsnow', (0, -.38, z), (.66, .62, .1), sn); o.parent = root
    o = lump('hoodsnow', (0, 1.2, .86), (.74, .5, .06), sn); o.parent = root
    o = lump('trunksnow', (0, -1.47, .86), (.74, .26, .06), sn); o.parent = root

def stars_haze(): haze(.012, (0, 0, 4), (60, 60, 4), (.75, .82, 1))

def moon_light(e=120, k=1.8): area('moon', (-8, 6, 9), (0, 0, 0), e * k, (.45, .6, 1), 8)

# ------------------------------------------------------------------ plates
sn = snow_mat(); night_world()
if name == 'rear':      # hook: low behind the car, drift over the tailpipe, taillights glowing through the snowfall, cast silhouettes inside
    ground(sn); highway(sn); rt, _ = car((0, 0, 0), (0, 0, 0), lights=True, occupants=seated(mia=None, kai=dict(expr='neutral'), leo=dict(expr='worried')))
    tailpipe(rt); rear_drift((0, 0, 0), sn, .5); roof_snow(rt, sn)
    point('dome', (0, -.4, 1.38), 25, (1, .7, .42), .15); moon_light(150)
    area('red', (0, -3.2, .6), (0, -1.8, .4), 6, (1, .1, .05), 1.5)
    for k in range(3): pine((random.Random(k).uniform(-12, 12), 30 + k * 9, .1), 8, k)
    stars_haze(); cam((.95, -4.6, 1.05), (0, -.9, .62), 24, 4.0)
elif name == 'wide':    # stuck cars in a line on the snowy highway at night
    ground(sn); highway(sn)
    for k, (x, y, rz) in enumerate(((.0, 0, 0), (-1.0, 9.0, 8), (.6, 17.5, -5))):
        rt, _ = car((x, y, 0), (0, 0, rz), lights=True, occupants=(seated(mia=None) if k == 0 else None), interior=(k == 0))
        tailpipe(rt); rear_drift((x, y, 0), sn, .55, seed=k * 3); roof_snow(rt, sn)
    r = random.Random(4)
    for k in range(26): pine((r.choice((-1, 1)) * r.uniform(7, 20), r.uniform(-10, 60), .1), r.uniform(5, 10), k)
    moon_light(200); point('dome', (0, -.4, 1.38), 25, (1, .7, .42), .15); stars_haze()
    cam((-3.2, -9.5, 3.6), (0, 3, .5), 26, 8.0)
elif name in ('pipe', 'pipe_clear'):   # macro on the tailpipe: buried vs dug out
    ground(sn); rt, _ = car((0, 0, 0), (0, 0, 0), lights=True, interior=False); tailpipe(rt)
    if name == 'pipe':
        lump('driftP', (.35, -2.25, .1), (.9, .55, .4), sn); lump('driftP2', (-.4, -2.1, .1), (.8, .5, .5), sn)
    else:
        lump('driftP2', (-.55, -2.1, .1), (.6, .5, .45), sn); lump('pileP', (1.5, -2.6, .1), (.6, .5, .3), sn)
    area('red', (.3, -3.0, .7), (.5, -1.9, .3), 5, (1, .12, .06), 1.0); area('fill', (-1.5, -3.6, 1.6), (.5, -1.9, .3), 90, (.45, .6, 1), 2)
    cam((1.35, -3.75, .62), (.48, -1.95, .28), 40, 2.4)
elif name == 'dig':     # Kai outside at the back, digging the snow away from the tailpipe; driver window open
    ground(sn); highway(sn); rt, _ = car((0, 0, 0), (0, 0, 0), lights=True, occupants=seated(mia=None, kai=None, leo=dict(expr='bored')))
    tailpipe(rt); roof_snow(rt, sn); lump('driftD', (-.6, -2.1, .1), (.8, .6, .5), sn); lump('pileD', (1.4, -2.7, .1), (.6, .5, .35), sn)
    cast({'kai': dict(loc=(.75, -2.45, .1), expr='worried', rot=(15, 0, 150), arms={'arm_l': (-60, 0, -10), 'arm_r': (-60, 0, 10)})})
    point('dome', (0, -.4, 1.38), 25, (1, .7, .42), .15); moon_light(150); area('key', (3, -5, 3), (.5, -2.2, .5), 160, (1, .7, .45), 3)
    stars_haze(); cam((3.0, -5.4, 1.5), (.3, -1.7, .6), 28, 5.0)
elif name == 'side':    # safe: side view, window cracked, dome light on, both awake
    ground(sn); highway(sn); rt, _ = car((0, 0, 0), (0, 0, 90), lights=True, occupants=seated(mia=None, kai=dict(expr='neutral'), leo=dict(expr='happy')))
    tailpipe(rt); roof_snow(rt, sn); lump('pileS', (2.6, -1.2, .1), (.6, .5, .3), sn)
    point('dome', (0, -.4, 1.38), 40, (1, .7, .42), .15); moon_light(150)
    stars_haze(); cam((-1.0, -6.0, 1.1), (0, 0, .85), 30, 6.0)
elif name == 'jam':     # a long line of stranded cars and trucks on a snowed-in highway (illustration of 1978)
    ground(sn); highway(sn); r = random.Random(7)
    paints = [(.42, .05, .04), (.05, .12, .3), (.3, .3, .32), (.08, .2, .1), (.5, .38, .1)]
    for k in range(7):
        for lane in (-1.1, 1.1):
            y = k * 6.5 + r.uniform(-1, 1); rt, _ = car((lane, y, 0), (0, 0, r.uniform(-12, 12)), lights=(r.random() < .4), interior=False)
            pc = r.choice(paints)
            for ob in rt.children_recursive:
                for m in (ob.data.materials if ob.type == 'MESH' else []):
                    if m and m.name.startswith('paint'):
                        for nd in m.node_tree.nodes:
                            if nd.type == 'BSDF_PRINCIPLED': nd.inputs['Base Color'].default_value = (*pc, 1)
            roof_snow(rt, sn, 1.52); lump(f'dj{k}{lane}', (lane + .2, y - 2.0, .1), (1.4, .8, r.uniform(.5, .8)), sn)
    for k in range(18): pine((r.choice((-1, 1)) * r.uniform(7, 25), r.uniform(-5, 70), .1), r.uniform(5, 10), k)
    moon_light(260); stars_haze(); cam((5.5, -9, 7), (0, 16, 0), 30)
else:                   # interior: car frame = world, both front seats from the dash
    ground(sn, .1); rt, _ = car((0, 0, 0), (0, 0, 0), lights=True, occupants=seated(mia=None, **{
        'int': dict(kai=dict(expr='neutral', rot=(0, 0, -10)), leo=dict(expr='worried', rot=(0, 0, 10))),
        'cu_leo': dict(leo=dict(expr='worried', rot=(0, 0, 15), arms={'arm_l': (-60, 0, 40), 'arm_r': (-60, 0, -40)})),
        'cu_leo_sleepy': dict(leo=dict(expr='bored', rot=(0, 8, 22))),
        'cu_kai': dict(kai=dict(expr='scared', rot=(0, 0, -30), arms={'arm_r': (-100, 0, -40)}), leo=dict(expr='bored', rot=(0, 8, 22))),
    }[name]))
    roof_snow(rt, sn)
    for x in (-1.0, 1.0): lump(f'sideDrift{x}', (x * 1.5, -.5, .1), (.8, 2.4, .95), sn)   # snow banked against the doors
    lump('backDrift', (0, -2.3, .1), (1.6, .9, 1.0), sn)
    point('dome', (0, -.4, 1.38), 32, (1, .7, .42), .15); point('dashglow', (0, .55, .95), 10, (1, .6, .3), .1); area('moon', (-3, 2, 3), (0, 0, 1), 120, (.45, .6, 1), 3)
    shots = {'int': ((0, .7, 1.26), (0, -.3, .95), 13, None), 'cu_leo': ((.12, .6, 1.12), (.38, 0, 1.05), 26, 2.8),
             'cu_leo_sleepy': ((.14, .6, 1.12), (.38, 0, 1.03), 26, 2.6), 'cu_kai': ((-.12, .6, 1.13), (-.38, 0, 1.05), 26, 2.8)}
    l, k, ln, fs = shots[name]; cam(l, k, ln, fs)
sc.render.filepath = f'{OUT}/{name}.png'
bpy.ops.render.render(write_still=True)
print('WROTE', sc.render.filepath)
