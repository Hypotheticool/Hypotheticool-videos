"""Pick a spot to hide from lightning. One Cycles still per plate (sky left transparent: bolt_anim.py paints the storm sky,
rain and lightning in 2D and animates the shot). python3 bolt_plate.py <plate> [res_scale] -> bolt/plates/<plate>.png (+ .txt with 2D points)
plates: field (wide: storm dusk meadow, one big lone oak), under (Leo sheltering against the trunk, low angle),
        lake (Leo swimming, head and shoulders above dark water, tree line behind), flat (Leo lying flat in wet grass, low side view),
        car (hard-topped sedan parked on a wet country road), leobust (RGBA sprite of Leo for the car window),
        tire (close-up of a wheel and tire on wet asphalt)"""
import sys, math, os, random
sys.path.insert(0, '/home/claude/b3d')
import bpy, kit
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
name = sys.argv[1]; S = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
OUT = '/home/claude/b3d/bolt/plates'; os.makedirs(OUT, exist_ok=True)
W, H = int(1080 * S), int(1920 * S)
sc = kit.reset(res=(W, H), samples=int(os.environ.get('SAMPLES', 32)))
sc.cycles.adaptive_threshold = 0.03; sc.cycles.max_bounces = 4
sc.render.film_transparent = True
random.seed(11)
PTS = {}

def add(prim, mat, loc, scale, rot=(0, 0, 0), bevel=0.0, sub=1, parent=None, **kw):
    getattr(bpy.ops.mesh, prim)(**kw); ob = bpy.context.object; ob.location = loc; ob.scale = scale; ob.rotation_euler = rot
    ob.data.materials.append(mat); kit.smooth(ob, sub, bevel)
    if parent: ob.parent = parent
    return ob

def area(loc, aim, energy, size, color):
    d = bpy.data.lights.new('a', 'AREA'); d.energy = energy; d.size = size; d.color = color
    ob = kit.link(bpy.data.objects.new('a', d)); ob.location = loc
    ob.rotation_euler = (Vector(aim) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler(); return ob

def storm_world(strength=.9):
    """dim blue-grey storm light from all around (the sky itself is painted in 2D)"""
    w = bpy.data.worlds.new('storm'); sc.world = w; nt, N, L = kit.nodes(w)
    bg = N.new('ShaderNodeBackground'); o = N.new('ShaderNodeOutputWorld'); bg.inputs['Color'].default_value = (.06, .08, .11, 1)
    bg.inputs['Strength'].default_value = strength; L.new(bg.outputs[0], o.inputs[0])
    kit.sun_lamp((-.6, .8, .12), 1.4, (1, .55, .3))     # last warm light from a low sunset slit behind the storm
    kit.sun_lamp((.3, -.4, .9), .5, (.55, .68, 1))      # cool skylight from above

def wet_grass(size=200, height=.6, seed=2):
    ter = kit.terrain(size=size, height=height, scale=2, kind='grass', seed=seed, res=8)
    bs = [n for n in ter.data.materials[0].node_tree.nodes if n.type == 'BSDF_PRINCIPLED'][0]; bs.inputs['Roughness'].default_value = .45
    return ter

def grass_blades(n, xr, yr, h=(.15, .35), seed=4):
    random.seed(seed); m = kit.mat_principled('blade', (.05, .13, .03), rough=.5)
    me = bpy.data.meshes.new('blades'); vs = []; fs = []
    for i in range(n):
        x, y = random.uniform(*xr), random.uniform(*yr); hh = random.uniform(*h); lean = random.uniform(-.08, .08); w = .012
        b = len(vs); vs += [(x - w, y, 0), (x + w, y, 0), (x + lean, y + lean * .5, hh)]; fs.append((b, b + 1, b + 2))
    me.from_pydata(vs, [], fs); ob = bpy.data.objects.new('blades', me); kit.link(ob); ob.data.materials.append(m); return ob

LEAF = None; BARK = None
def oak(loc=(0, 0, 0), s=1.0, seed=1, clumps=60):
    """a big lone broadleaf tree (oak-like): thick trunk ~1 m, crooked limbs, a wide domed crown ~18 m tall"""
    global LEAF, BARK
    LEAF = LEAF or kit.mat_pbr('leaf', 'oakleaf'); BARK = BARK or kit.mat_pbr('bark', 'oakbark'); BARK.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (.07, .05, .035, 1)
    LEAF.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (.05, .12, .03, 1)
    random.seed(seed); root = kit.link(bpy.data.objects.new('oak', None)); root.location = loc; root.scale = (s, s, s)
    tr = add('primitive_cone_add', BARK, (0, 0, 3.5), (1, 1, 1), radius1=.75, radius2=.4, depth=7, vertices=24, parent=root)
    dm = tr.modifiers.new('d', 'DISPLACE'); tx = bpy.data.textures.new('bk', 'CLOUDS'); tx.noise_scale = .3; dm.texture = tx; dm.strength = .22
    for k in range(6):   # main limbs spreading out and up (hidden inside the crown)
        a = k / 6 * 2 * math.pi + random.uniform(-.3, .3); el = math.radians(random.uniform(35, 55)); L = random.uniform(3.5, 5.0)
        d = Vector((math.cos(a) * math.cos(el), math.sin(a) * math.cos(el), math.sin(el)))
        p0 = Vector((0, 0, 6.2)); mid = p0 + d * L / 2
        add('primitive_cone_add', BARK, tuple(mid), (1, 1, 1), rot=d.to_track_quat('Z', 'Y').to_euler(), radius1=.32, radius2=.1, depth=L, vertices=12, parent=root)
    for k in range(clumps):  # leafy clumps forming a wide, full dome down to ~7 m
        a = random.uniform(0, 2 * math.pi); r = 6.5 * math.sqrt(random.uniform(0, 1)); z = 8.0 + 5.5 * math.sqrt(max(0, 1 - (r / 7.2) ** 2)) * random.uniform(.3, 1.0)
        cl = add('primitive_ico_sphere_add', LEAF, (math.cos(a) * r, math.sin(a) * r, z), (1, 1, 1), subdivisions=3 if clumps > 20 else 2, radius=random.uniform(2.0, 3.0) * (1 if clumps > 20 else 1.4), sub=0, parent=root)
        cl.scale = (1, 1, .75); dm = cl.modifiers.new('d', 'DISPLACE'); tx = bpy.data.textures.new('lf', 'VORONOI'); tx.noise_scale = .35; dm.texture = tx; dm.strength = .9
    return root

def tree_line(n, xr, y, z=0, seed=5, s=(.5, .9)):
    random.seed(seed)
    for i in range(n): oak((random.uniform(*xr), y + random.uniform(-8, 8), z), random.uniform(*s), seed=seed * 50 + i, clumps=12)

def leo(pose='stand', expr='scared', loc=(0, 0, 0), rot=(0, 0, 0), h=1.0):
    root, parts = kit.character('leo', loc, h); root.rotation_euler = rot
    parts['face_mat'].node_tree.nodes['expr'].outputs[0].default_value = kit.EXPRS.index(expr)
    if pose == 'hug':       # pressed against the trunk, arms pulled in, shoulders up
        for side, nm in ((-1, 'arm_l'), (1, 'arm_r')): parts[nm].rotation_euler = (math.radians(-50), side * math.radians(10), 0)
    elif pose == 'swim':    # arms out to the sides, treading water
        for side, nm in ((-1, 'arm_l'), (1, 'arm_r')): parts[nm].rotation_euler = (math.radians(-10), -side * math.radians(80), 0)
    elif pose == 'flat':    # lying on his back, arms by his sides
        for side, nm in ((-1, 'arm_l'), (1, 'arm_r')): parts[nm].rotation_euler = (0, side * math.radians(20), 0)
    elif pose == 'sit':     # seated, hands in lap
        for side, nm in ((-1, 'arm_l'), (1, 'arm_r')): parts[nm].rotation_euler = (math.radians(-55), side * math.radians(8), 0)
        for nm in ('leg_l', 'leg_r'): parts[nm].rotation_euler = (math.radians(-85), 0, 0)
    return root, parts

def proj(cam, p):
    v = world_to_camera_view(sc, cam, Vector(p)); return (round(v.x, 4), round(1 - v.y, 4))

def sedan(loc=(0, 0, 0), yaw=0.0):
    """a generic hard-topped 4-door sedan (~4.8 m long, 1.45 m tall), deep red paint, unbranded"""
    root = kit.link(bpy.data.objects.new('car', None)); root.location = loc; root.rotation_euler = (0, 0, yaw)
    paint = kit.mat_principled('paint', (.35, .02, .02), rough=.25, metal=.6, coat=1.0)
    glass = kit.mat_principled('glass', (.02, .03, .04), rough=.05, metal=.2)
    chrome = kit.mat_pbr('steel', 'trim'); rub = kit.mat_principled('tire', (.012, .012, .014), rough=.85)
    lamp = kit.mat_emit('headlamp', (1, .92, .8), 6); tail = kit.mat_emit('taillamp', (1, .05, .02), 4)
    add('primitive_cube_add', paint, (0, 0, .62), (2.4, .9, .3), bevel=.14, sub=2, parent=root)                      # lower body (top at ~.92 m)
    glass = kit.mat_pbr('glass', 'carglass'); glass.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (.55, .65, .7, 1)
    glass.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = .02
    add('primitive_cube_add', paint, (-.15, 0, 1.37), (1.05, .78, .045), bevel=.04, sub=1, parent=root)             # hard metal roof
    for sx in (-1, 1):
        add('primitive_cube_add', paint, (.95, sx * .76, 1.15), (.05, .04, .23), rot=(0, math.radians(-35), 0), parent=root)   # A pillar
        add('primitive_cube_add', paint, (-.2, sx * .78, 1.15), (.05, .04, .23), parent=root)                                  # B pillar
        add('primitive_cube_add', paint, (-1.25, sx * .76, 1.15), (.08, .04, .23), rot=(0, math.radians(35), 0), parent=root)  # C pillar
        add('primitive_cube_add', glass, (-.15, sx * .77, 1.15), (1.05, .008, .21), sub=0, parent=root)                        # side windows
    add('primitive_cube_add', glass, (1.07, 0, 1.15), (.01, .74, .26), rot=(0, math.radians(-55), 0), sub=0, parent=root)    # windshield
    add('primitive_cube_add', glass, (-1.38, 0, 1.15), (.01, .72, .24), rot=(0, math.radians(55), 0), sub=0, parent=root)
    seat = kit.mat_principled('seat', (.05, .045, .04), rough=.8)
    for sx in (-.4, .4):
        add('primitive_cube_add', seat, (.2, sx, .98), (.3, .25, .06), bevel=.03, parent=root); add('primitive_cube_add', seat, (-.12, sx, 1.2), (.06, .25, .25), bevel=.03, parent=root)
        add('primitive_cube_add', seat, (-.75, sx, .98), (.3, .25, .06), bevel=.03, parent=root)
    for sx in (-1, 1):
        for wx in (-1.5, 1.5):
            add('primitive_cylinder_add', rub, (wx, sx * .86, .36), (.36, .36, .13), rot=(math.radians(90), 0, 0), vertices=48, bevel=.07, parent=root)
            add('primitive_cylinder_add', chrome, (wx, sx * .995, .36), (.22, .22, .01), rot=(math.radians(90), 0, 0), vertices=32, parent=root)
        add('primitive_cube_add', lamp, (2.38, sx * .62, .72), (.03, .17, .07), parent=root)
        add('primitive_cube_add', tail, (-2.38, sx * .64, .78), (.03, .18, .06), parent=root)
    return root

def wet_road(w=7, L=400):
    m = kit.mat_principled('asphalt', (.03, .03, .035), rough=.12)
    add('primitive_plane_add', m, (0, 0, .001), (L / 2, w / 2, 1), sub=0)
    mk = kit.mat_principled('mark', (.7, .62, .2), rough=.3)
    for k in range(-40, 40): add('primitive_cube_add', mk, (k * 6, 0, .004), (1.5, .06, .002), sub=0)

if name == 'field':
    storm_world(); ter = wet_grass(400, .8)
    t = oak((3.0, 24, 0), 1.0, seed=3); PTS['top'] = (3.0, 24, 14.5); PTS['base'] = (3.0, 24, 0.2)
    tree_line(14, (-160, 160), 150, seed=7, s=(.6, 1.0))
    cam, _ = kit.camera((0, -4, 1.6), (2, 24, 7.0), lens=24)
elif name == 'under':
    storm_world(1.1); ter = wet_grass(200, .3)
    oak((0, 0, 0), 1.0, seed=3)
    leo('hug', 'worried', loc=(.35, -.95, 0), rot=(0, 0, math.radians(15)), h=1.5)
    grass_blades(3000, (-4, 4), (-4, 2), seed=2)
    area((2, -4, 3), (0, -1, 1), 300, 3, (.6, .7, 1))
    cam, _ = kit.camera((1.6, -4.2, .7), (0, -.5, 2.6), lens=22)
    PTS['trunk'] = (0, -.62, 2.2); PTS['leo'] = (.35, -.95, 1.0)
elif name == 'lake':
    storm_world(1.0)
    wm = kit.mat_principled('lakewater', (.005, .02, .03), rough=.06)
    wp = add('primitive_plane_add', wm, (0, 150, 0), (300, 300, 1), sub=0)
    nt = wm.node_tree; N = nt.nodes; bs = N['Principled BSDF']; tx = N.new('ShaderNodeTexNoise'); tx.inputs['Scale'].default_value = 3.0
    bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = .25; nt.links.new(tx.outputs['Fac'], bp.inputs['Height']); nt.links.new(bp.outputs['Normal'], bs.inputs['Normal'])
    shore = wet_grass(600, 1.5, seed=9); shore.location = (0, 380, .2)
    tree_line(16, (-120, 120), 95, z=.5, seed=8, s=(.6, 1.0))
    leo('swim', 'scared', loc=(0, 6, -.98), rot=(0, 0, math.radians(-8)), h=1.5)
    area((2, 2, 3), (0, 6, .3), 250, 3, (.6, .7, 1))
    cam, _ = kit.camera((.3, 2.4, .45), (0, 7, .35), lens=32)
    PTS['leo'] = (0, 6, .35)
elif name == 'flat':
    storm_world(1.0); ter = wet_grass(200, .25, seed=4)
    leo('flat', 'scared', loc=(0, 0, .14), rot=(math.radians(-90), 0, math.radians(90)), h=1.6)
    grass_blades(6000, (-5, 5), (-3, 5), h=(.08, .25), seed=6)
    oak((-14, 60, 0), .9, seed=12); tree_line(10, (-120, 120), 140, seed=3)
    area((0, -4, 3), (0, 0, 0), 110, 4, (.6, .7, 1))
    cam, _ = kit.camera((-.2, -3.3, 1.15), (-.45, 0, .12), lens=19)
    PTS['head'] = (-1.3, 0, .3); PTS['feet'] = (1.3, 0, .2); PTS['ground'] = (0, 2.5, 0)
elif name == 'leobust':   # RGBA sprite: Leo's head and shoulders, warm cabin light (composited into the car window in 2D)
    w = bpy.data.worlds.new('w'); sc.world = w; nt, N, L = kit.nodes(w); bg = N.new('ShaderNodeBackground'); o = N.new('ShaderNodeOutputWorld')
    bg.inputs['Color'].default_value = (.05, .07, .1, 1); bg.inputs['Strength'].default_value = .6; L.new(bg.outputs[0], o.inputs[0])
    leo('sit', 'neutral', loc=(0, 0, 0), h=1.0)
    area((.8, -2, 1.2), (0, 0, .75), 120, 2, (1, .75, .5)); area((-1.2, -1, 1.4), (0, 0, .8), 60, 2, (.5, .65, 1))
    cam, _ = kit.camera((0, -2.4, .8), (0, 0, .72), lens=60)
elif name == 'car':
    storm_world(1.0); ter = wet_grass(400, .05, seed=5); ter.location.z = -.03
    wet_road(); sedan((0, 0, 0), math.radians(0))
    tree_line(12, (-150, 150), 90, seed=4); oak((20, 30, 0), .9, seed=21)
    if True:
        area((3, -8, 5), (0, 0, 1), 450, 6, (.6, .7, 1))
        cam, _ = kit.camera((3.6, -7.2, 1.3), (-.2, 0, .9), lens=28)
        for k, p in enumerate([(2.4, -.9, .4), (2.3, -.9, .95), (1.06, -.8, 1.3), (.6, -.8, 1.38), (-.9, -.8, 1.38), (-1.38, -.8, 1.3), (-2.38, -.9, .95), (-2.4, -.9, .4)]):
            PTS[f'p{k}'] = p
        PTS['w0'] = (1.5, -.9, .0); PTS['w1'] = (-1.5, -.9, .0)
elif name == 'tire':
    storm_world(1.0); wet_road(); sedan((0, 0, 0), 0)
    area((2, -3, 1), (1.5, -.9, .36), 70, 2, (.6, .7, 1)); area((-1, -2, .5), (1.5, -.9, .36), 80, 1, (1, .6, .35))
    cam, _ = kit.camera((2.6, -2.6, .35), (1.5, -.9, .38), lens=40)
if PTS:
    bpy.context.view_layer.update()
    with open(f'{OUT}/{name}.txt', 'w') as f:
        for k, p in PTS.items(): f.write(f'{k} {proj(cam, p)[0]} {proj(cam, p)[1]}\n')
sc.render.filepath = f'{OUT}/{name}.png'; bpy.ops.render.render(write_still=True); print('ok', name)
