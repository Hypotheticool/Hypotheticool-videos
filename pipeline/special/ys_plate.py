"""What if Yellowstone erupted? One Cycles still per plate (animated in 2D by ys_anim.py). Helpers copied from spin_plate.py.
python3 ys_plate.py <plate> [res_scale] -> /home/claude/b3d/ys/plates/<plate>.png (+ fx_<plate>.json)
plates: erupt (night eruption column over pine forest), flow (glowing pyroclastic flow rolling at the camera), town (ash-buried
  Montana street), roof (house with a sagging ash-loaded roof), engine (airliner engine in an ash cloud), macro (ash shards: jagged
  rock + volcanic glass, macro), geyser (hot-spring basin with steam), lava (slow lava-flow front in the forest)"""
import sys, math, os, json, random
sys.path.insert(0, '/home/claude/b3d')
import bpy, kit
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
name = sys.argv[1]; S = float(sys.argv[2]) if len(sys.argv) > 2 else .7
OUT = '/home/claude/b3d/ys/plates'; os.makedirs(OUT, exist_ok=True)
SPRITE = name.startswith('sp_')
W, H = (600, 600) if SPRITE else (int(1080 * S), int(1920 * S))
sc = kit.reset(res=(W, H), samples=int(os.environ.get('SAMPLES', 32)))
sc.cycles.adaptive_threshold = 0.04; sc.cycles.max_bounces = 4; sc.cycles.diffuse_bounces = 2
R = math.radians; FX = {}; rnd = random.Random(5)

def M(nm, col, rough=.5, metal=0.0, coat=0.0): return kit.mat_principled(nm, col, rough=rough, metal=metal, coat=coat)
def box(nm, loc, size, mat, bevel=.01, rot=(0, 0, 0), parent=None):
    bpy.ops.mesh.primitive_cube_add(location=loc); o = bpy.context.object; o.name = nm; o.scale = (size[0] / 2, size[1] / 2, size[2] / 2)
    o.rotation_euler = rot; bpy.ops.object.transform_apply(scale=True); o.data.materials.append(mat)
    if bevel: b = o.modifiers.new('b', 'BEVEL'); b.width = bevel; b.segments = 3
    if parent: o.parent = parent
    return o
def cyl(nm, loc, r, depth, mat, rot=(0, 0, 0), verts=32, r2=None, parent=None):
    if r2 is None: bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=depth, location=loc, rotation=rot, vertices=verts)
    else: bpy.ops.mesh.primitive_cone_add(radius1=r, radius2=r2, depth=depth, location=loc, rotation=rot, vertices=verts)
    o = bpy.context.object; o.name = nm; o.data.materials.append(mat); bpy.ops.object.shade_smooth()
    if parent: o.parent = parent
    return o
def cam(loc, look, lens, fstop=None):
    c, t = kit.camera(loc, look, lens=lens); sc.camera = c
    if fstop: c.data.dof.use_dof = True; c.data.dof.focus_distance = (Vector(loc) - Vector(look)).length; c.data.dof.aperture_fstop = fstop
    return c
def proj(key, p):
    bpy.context.view_layer.update(); v = world_to_camera_view(sc, sc.camera, Vector(p)); FX[key] = [round(v.x, 4), round(1 - v.y, 4)]
def area(loc, at, energy, color=(1, 1, 1), size=3):
    li = bpy.data.lights.new('ar', 'AREA'); li.energy = energy; li.color = color; li.size = size
    o = kit.link(bpy.data.objects.new('ar', li)); o.location = loc
    o.rotation_euler = (Vector(at) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler(); return o

def noise_mat(nm, c0, c1, scale=.35, rough=.95, bump=.5, bscale=60):
    m = bpy.data.materials.new(nm); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled')
    tc = N.new('ShaderNodeTexCoord'); nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = scale; nz.inputs['Detail'].default_value = 12
    L.new(tc.outputs['Object'], nz.inputs[0]); cr = N.new('ShaderNodeValToRGB')
    cr.color_ramp.elements[0].color = (*c0, 1); cr.color_ramp.elements[1].color = (*c1, 1)
    L.new(nz.outputs['Fac'], cr.inputs[0]); L.new(cr.outputs[0], bs.inputs['Base Color']); bs.inputs['Roughness'].default_value = rough
    n2 = N.new('ShaderNodeTexNoise'); n2.inputs['Scale'].default_value = bscale; L.new(tc.outputs['Object'], n2.inputs[0])
    bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = bump; L.new(n2.outputs['Fac'], bp.inputs['Height']); L.new(bp.outputs[0], bs.inputs['Normal'])
    L.new(bs.outputs[0], o.inputs[0]); return m
def grass(): return bpy.data.materials.get('grass') or noise_mat('grass', (.07, .1, .03), (.2, .22, .07))
def asphalt(): return bpy.data.materials.get('asph') or noise_mat('asph', (.025, .027, .03), (.075, .075, .08), 40, .55, .2, 200)

def ground(size=900, mat=None):
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, -.02)); g = bpy.context.object; g.data.materials.append(mat or grass())
def road_x(y, w=7.0, L=500):
    box('road', (0, y, 0), (L, w, .04), asphalt(), 0); ln = kit.mat_emit('paint', (.9, .75, .25), .15)
    for k in range(-40, 40): box('dash', (k * 6, y, .022), (3, .12, .005), ln, 0)
def power_line_x(y, x0, x1, step=36.0, frost=False):
    wd = M('pole', (.16, .11, .07), .85) if not frost else M('polef', (.55, .58, .62), .7); x = x0; tops = []
    while x < x1:
        cyl('ppole', (x, y, 5), .14, 10, wd, verts=10); box('xarm', (x, y, 9.4), (.14, 2.2, .14), wd, .01); tops.append(x); x += step
    cab = M('cab', (.03, .03, .03), .5)
    for dy in (-.9, .9):
        for a, b in zip(tops[:-1], tops[1:]): box('cable', ((a + b) / 2, y + dy, 9.1), (b - a, .025, .025), cab, 0)
def house(x, y, yaw=0.0, wall=(.55, .52, .46), roofc=(.16, .1, .08), lit=True, frost=0.0, s=1.0):
    base = kit.link(bpy.data.objects.new('house', None)); base.location = (x, y, 0); base.rotation_euler = (0, 0, yaw); base.scale = (s, s, s)
    f = lambda c: tuple(ci * (1 - frost) + .82 * frost for ci in c)
    sid = M('siding', f(wall), .8); roof = M('roof', f(roofc), .8)
    box('fh', (0, 0, 2.2), (9, 7, 4.4), sid, .02, parent=base)
    for sgn in (-1, 1): box('rf', (0, sgn * 1.9, 5.1), (9.8, 4.5, .25), roof, .02, rot=(sgn * R(-32), 0, 0), parent=base)
    box('chim', (2.6, .8, 6.2), (.8, .8, 2.2), M('chim', f((.3, .12, .08)), .9), .01, parent=base)
    win = kit.mat_emit('flit', (1, .62, .3), 3.0) if lit else M('wdark', (.01, .012, .02), .1)
    for xx in (-2.8, 2.8): box('fw', (xx, -3.52, 2.7), (1.1, .05, 1.3), win, 0, parent=base)
    box('door', (0, -3.52, 1.1), (1.0, .06, 2.1), M('door', f((.25, .08, .06)), .6), 0, parent=base)
    box('porch', (0, -4.3, .12), (5, 1.6, .24), M('porchw', f((.3, .22, .15)), .8), .01, parent=base)
    return base
def barn(x, y, frost=0.0):
    f = lambda c: tuple(ci * (1 - frost) + .82 * frost for ci in c)
    box('barn', (x, y, 3.5), (8, 10, 7), M('barn', f((.32, .07, .05)), .85), .02)
    for sgn in (-1, 1): box('broof', (x + sgn * 2.2, y, 7.9), (5.2, 10.4, .25), M('broofm', f((.15, .15, .16)), .6, .4), .02, rot=(0, sgn * R(38), 0))
    cyl('silo', (x + 7, y - 3, 7), 2.2, 14, M('silo', f((.5, .52, .55)), .4, .7)); cyl('silotop', (x + 7, y - 3, 14.6), 2.25, 1.4, M('silo2', f((.42, .44, .48)), .4, .7), r2=.3)
def leaf_mat():
    m = bpy.data.materials.get('leafm')
    return m or noise_mat('leafm', (.05, .12, .02), (.22, .3, .06), 1.5, .7, .8, 25)
def tree(x, y, h=7.0, seed=0, parent=None, mat=None):
    r = random.Random(seed); g = kit.link(bpy.data.objects.new('tree', None)); g.location = (x, y, 0)
    if parent: g.parent = parent
    cyl('trunk', (0, 0, h * .25), h * .045, h * .5, M('bark', (.12, .08, .05), .9), verts=10, r2=h * .028, parent=g)
    for k in range(6):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=h * r.uniform(.17, .25),
                                              location=(r.uniform(-.2, .2) * h, r.uniform(-.2, .2) * h, h * r.uniform(.55, .85)))
        o = bpy.context.object; o.data.materials.append(mat or leaf_mat()); o.parent = g
        d = o.modifiers.new('d', 'DISPLACE'); tx = bpy.data.textures.new('fol', 'CLOUDS'); tx.noise_scale = .6; d.texture = tx; d.strength = h * .06
        bpy.ops.object.shade_smooth()
    return g
def car_body(loc=(0, 0, 0), yaw=0.0, col=(.55, .07, .06), lights=True):
    root = kit.link(bpy.data.objects.new('car', None)); root.location = loc; root.rotation_euler = (0, 0, yaw)
    paint = M('paint', col, .25, .3, 1.0); glass = M('cglass', (.02, .03, .04), .05, .5); blk = M('trimb', (.02, .02, .02), .5)
    box('body', (0, 0, .62), (4.5, 1.8, .7), paint, .12, parent=root); box('cab', (-.25, 0, 1.15), (2.3, 1.6, .62), paint, .14, parent=root)
    for s_ in (-1, 1): box('side_glass', (-.25, s_ * .805, 1.17), (2.0, .02, .44), glass, .02, parent=root)
    box('wind', (.93, 0, 1.15), (.06, 1.45, .48), glass, .02, rot=(0, R(-35), 0), parent=root)
    box('rear', (-1.42, 0, 1.15), (.06, 1.45, .45), glass, .02, rot=(0, R(30), 0), parent=root)
    for sx in (-1.45, 1.45):
        for sy in (-.9, .9):
            cyl('tire', (sx, sy, .36), .36, .26, M('tire', (.02, .02, .02), .8), rot=(R(90), 0, 0), parent=root)
            cyl('hub', (sx, sy * 1.005, .36), .2, .27, M('hub', (.6, .6, .62), .3, 1.0), rot=(R(90), 0, 0), parent=root)
    box('bumpf', (2.27, 0, .45), (.1, 1.75, .22), blk, .03, parent=root); box('bumpr', (-2.27, 0, .45), (.1, 1.75, .22), blk, .03, parent=root)
    if lights:
        hl = kit.mat_emit('head', (1, .92, .75), 25); tl = kit.mat_emit('tail', (1, .05, .03), 12)
        for sy in (-.62, .62):
            box('hl', (2.255, sy, .72), (.04, .34, .14), hl, .01, parent=root); box('tl', (-2.255, sy, .72), (.04, .3, .12), tl, .01, parent=root)
    return root
def fence_x(y, x0, x1, step=4.0, frost=False):
    wd = M('post', (.2, .14, .09) if not frost else (.6, .63, .66), .85); x = x0
    while x < x1: box('fpost', (x, y, .6), (.12, .12, 1.2), wd, .01); x += step
    for z in (.5, .95): box('wire', ((x0 + x1) / 2, y, z), (x1 - x0, .015, .015), M('wire', (.2, .2, .2), .4, .8), 0)


# ------------------------------------------------------------------ Yellowstone pieces
sc.cycles.volume_step_rate = 3.0; sc.cycles.volume_max_steps = 160
def pine_mat(): return bpy.data.materials.get('pinem') or noise_mat('pinem', (.015, .04, .02), (.05, .1, .04), 2.0, .8, .6, 30)
_PINE = {}
def pine(x, y, h=14.0, seed=0, mat=None, ashy=0.0):
    """lodgepole-style conifer: thin trunk + stacked displaced cones (Yellowstone is ~80% lodgepole pine forest)"""
    key_ = (round(h), mat.name if mat else 'p')
    r = random.Random(seed)
    if key_ not in _PINE:
        g = kit.link(bpy.data.objects.new('pineproto', None)); g.location = (0, 0, -500)
        cyl('ptr', (0, 0, h * .35), h * .018, h * .7, M('pbark', (.1, .07, .05), .9), verts=8, r2=h * .008, parent=g)
        for k in range(5):
            z = h * (.3 + k * .14); rr = h * (.2 - k * .032)
            o = cyl('pc', (0, 0, z), rr, h * .26, mat or pine_mat(), verts=12, r2=rr * .15, parent=g)
            d = o.modifiers.new('d', 'DISPLACE'); tx = bpy.data.textures.new('pn', 'CLOUDS'); tx.noise_scale = .5; d.texture = tx; d.strength = h * .03
        _PINE[key_] = g
    src = _PINE[key_]
    for ch in src.children:
        o = ch.copy(); bpy.context.collection.objects.link(o); o.parent = None
        o.location = (ch.location.x + x, ch.location.y + y, ch.location.z); o.scale = (1 + r.uniform(-.15, .15),) * 2 + (1,)
def forest(x0, x1, y0, y1, n, seed=1, hmin=10, hmax=18, mat=None):
    r = random.Random(seed)
    for k in range(n): pine(r.uniform(x0, x1), r.uniform(y0, y1), r.uniform(hmin, hmax), seed + k, mat)
def column(vx, vy, base=0.0, height=900.0, r0=60.0, r1=170.0, glow=True, umbrella=True, seed=0, dens=1.6):
    """Plinian eruption column: stacked ash volumes widening upward, an umbrella cloud spreading out on top, lit from the vent"""
    r = random.Random(seed); n = 12
    for k in range(n):
        t = k / (n - 1); z = base + 40 + t * height; rr = r0 + (r1 - r0) * t ** 1.3
        ob = kit.volume_cloud((vx + r.uniform(-.25, .25) * rr, vy + r.uniform(-.2, .2) * rr, z), (rr * 1.15, rr, rr * .95), dens, kind='ash', seed=seed + k)
        if glow and t < .45:   # the lower column glows: incandescent ash and gas lit from the vent
            m = ob.data.materials[0].copy(); ob.data.materials[0] = m; pv = m.node_tree.nodes['Principled Volume']
            pv.inputs['Emission Color'].default_value = (1, .32, .06, 1); pv.inputs['Emission Strength'].default_value = .02 * (1 - t / .45) ** 2
    if umbrella:
        for k in range(5):
            kit.volume_cloud((vx + (k - 2) * 260 + r.uniform(-40, 40), vy + r.uniform(-80, 80), base + height + 60 + r.uniform(-30, 30)),
                             (430, 330, 110), dens * .9, kind='ash', seed=seed + 50 + k)
    if glow:
        for k in range(3):
            li = bpy.data.lights.new('vent', 'POINT'); li.energy = 9e7 * (1 - k * .3); li.color = (1, .38, .1); li.shadow_soft_size = 40
            o = kit.link(bpy.data.objects.new('vent', li)); o.location = (vx, vy, base + 20 + k * 120)
        fm = kit.mat_pbr('magma', 'fount')
        for k in range(40):   # incandescent fountain / bombs at the vent
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=r.uniform(3, 10),
                                                  location=(vx + r.uniform(-70, 70), vy + r.uniform(-30, 30), base + r.uniform(0, 160) ** 1.0))
            bpy.context.object.data.materials.append(fm)
def ash_ground(c0=(.16, .155, .15), c1=(.32, .31, .3)): return bpy.data.materials.get('ashg') or noise_mat('ashg', c0, c1, .8, .95, .25, 50)
def ash_mat(): return bpy.data.materials.get('ashm') or noise_mat('ashm', (.24, .235, .23), (.42, .41, .4), 3.0, .97, .3, 90)
def ash_cap(o, th=.25):
    """drape a layer of grey ash on the top of an object (a flattened displaced copy of its upper surface)"""
    bpy.context.view_layer.update(); bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
    xs_ = [p.x for p in bb]; ys_ = [p.y for p in bb]; zt = max(p.z for p in bb)
    box('ashcap', ((min(xs_) + max(xs_)) / 2, (min(ys_) + max(ys_)) / 2, zt + th / 2 - .02), (max(xs_) - min(xs_) + .1, max(ys_) - min(ys_) + .1, th), ash_mat(), th * .45)

def gloom(col=(.16, .13, .1), strength=.6, sun=.6):
    w = bpy.data.worlds.new('gloom'); sc.world = w; nt, N, L = kit.nodes(w); o = N.new('ShaderNodeOutputWorld'); bg = N.new('ShaderNodeBackground')
    bg.inputs['Color'].default_value = (*col, 1); bg.inputs['Strength'].default_value = strength; L.new(bg.outputs[0], o.inputs[0])
    li = kit.sun_lamp(Vector((-.3, -.5, .8)).normalized(), sun, (1, .8, .6)); li.data.angle = R(25)
def p_erupt():
    kit.sky(sun_elevation=-3, sun_rotation=250, strength=.05, sun_lamp_energy=.2)
    ground(4000, noise_mat('fl', (.02, .025, .02), (.05, .06, .04), .05, .95, .3, 20))
    t = kit.terrain(size=3000, height=180, scale=2.0, kind='rock', seed=4); t.location = (0, 2700, -20)
    for k in range(3):
        li = bpy.data.lights.new('vent', 'POINT'); li.energy = 5e7; li.color = (1, .38, .1); li.shadow_soft_size = 80
        o = kit.link(bpy.data.objects.new('vent', li)); o.location = (-150 + k * 150, 900, 250 + k * 150)
    forest(-140, 140, -40, 260, 160, 1, 14, 26)
    forest(-500, 500, 300, 800, 220, 9, 20, 30)
    kit.sun_lamp(Vector((.3, -.6, .5)).normalized(), .35, (.55, .65, 1))
    cam((0, -120, 4), (0, 900, 560), 20)
    proj('vent', (0, 900, 40)); proj('top', (0, 900, 1100)); proj('mid', (0, 900, 500))

def p_flow():
    kit.sky(sun_elevation=-3, sun_rotation=250, strength=.05, sun_lamp_energy=.2)
    ground(4000, noise_mat('fl', (.02, .025, .02), (.05, .06, .04), .05, .95, .3, 20))
    t = kit.terrain(size=3000, height=180, scale=2.0, kind='rock', seed=4); t.location = (0, 2700, -20)
    for k in range(6):
        li = bpy.data.lights.new('pf', 'POINT'); li.energy = 1.5e7; li.color = (1, .35, .08); li.shadow_soft_size = 30
        o = kit.link(bpy.data.objects.new('pf', li)); o.location = (-300 + k * 120, 360, 6)
    forest(-120, 120, -20, 300, 150, 2, 12, 24)
    kit.sun_lamp(Vector((.3, -.6, .5)).normalized(), .35, (.55, .65, 1))
    cam((0, -60, 5), (0, 400, 90), 22)
    proj('front', (0, 380, 40))

def p_town():
    gloom()
    ground(900, ash_ground()); road_x(0, 9)
    for o in [o for o in bpy.data.objects if o.name.startswith('road')]: o.data.materials[0] = noise_mat('ashroad', (.2, .19, .18), (.33, .32, .31), 1.5, .95, .4, 40)
    for o in [o for o in bpy.data.objects if o.name.startswith('dash')]: bpy.data.objects.remove(o)
    for k, x in enumerate((-36, -18, 0, 18, 36, 54)):
        hb = house(x, 14, 0, wall=[(.55, .5, .42), (.42, .48, .52), (.6, .58, .5)][k % 3], lit=True)
        box('ashroof', (x, 14, 6.35), (9.6, 7.6, .5), ash_mat(), .2)
    for k, x in enumerate((-30, -10, 12, 30)):
        house(x, -16, math.pi, wall=[(.5, .45, .4), (.45, .5, .55)][k % 2], lit=True); box('ashroof2', (x, -16, 6.35), (9.6, 7.6, .5), ash_mat(), .2)
    for x, col in ((-6, (.12, .2, .4)), (8, (.5, .06, .05))):
        cb = car_body((x, 2.2, 0), 0, col, lights=(x > 0)); box('ashcar', (x - .2, 2.2, 1.55), (2.4, 1.7, .22), ash_mat(), .1); box('ashhood', (x + 1.4, 2.2, 1.03), (1.6, 1.8, .14), ash_mat(), .06)
    for x in (-26, -2, 22, 46):   # street lights on in the daytime gloom
        cyl('pole', (x, 6, 4), .12, 8, M('polem', (.2, .2, .2), .5, .6), verts=10)
        li = bpy.data.lights.new('sl', 'POINT'); li.energy = 3000; li.color = (1, .7, .4); o = kit.link(bpy.data.objects.new('sl', li)); o.location = (x, 5, 7.8)
        box('lamp', (x, 5.2, 8), (.6, .9, .2), kit.mat_emit('lampm', (1, .75, .45), 20), .05)
    forest(-80, 80, 40, 120, 30, 4, 10, 16, ash_mat())
    for o in [o for o in bpy.data.objects if o.name.startswith('pc')]: o.data.materials[0] = ash_mat()
    cam((-14, -6, 1.7), (14, 12, 3.2), 24)
    proj('car', (8, 2.2, 1.2)); proj('roof', (0, 14, 6.5)); proj('street', (10, 0, 0))

def p_roof():
    gloom()
    ground(400, ash_ground())
    hb = house(0, 0, 0, wall=(.55, .5, .42), lit=True)
    for sgn in (-1, 1):
        a = box('ashload', (0, sgn * 1.85, 5.55), (9.9, 4.4, .9), ash_mat(), .4, rot=(sgn * R(-32), 0, 0))
        a.modifiers.new('sub', 'SUBSURF').levels = 2
        d = a.modifiers.new('d', 'DISPLACE'); tx = bpy.data.textures.new('al', 'CLOUDS'); tx.noise_scale = 1.2; d.texture = tx; d.strength = .35
    car_body((7.5, -7, 0), R(10), (.12, .2, .4), lights=False); box('ashcar', (7.3, -6.95, 1.55), (2.4, 1.7, .22), ash_mat(), .1)
    forest(-50, 50, 20, 70, 20, 6, 10, 16, ash_mat())
    for o in [o for o in bpy.data.objects if o.name.startswith('pc')]: o.data.materials[0] = ash_mat()
    area((-12, -16, 8), (0, 0, 4), 1500, (1, .75, .5), 6)
    cam((-9, -17, 2.0), (0, 0, 4.2), 30)
    proj('roof', (0, -1.8, 5.6))

def p_engine():
    gloom((.1, .09, .08), .4, .3)
    al = M('nac', (.75, .76, .78), .3, .9); dark = M('fan', (.06, .06, .07), .35, .9); ti = M('spin', (.15, .15, .16), .25, 1.0)
    g = kit.link(bpy.data.objects.new('eng', None))
    bpy.ops.mesh.primitive_torus_add(major_radius=1.45, minor_radius=.16, major_segments=96, minor_segments=24, location=(0, 0, 0), rotation=(R(90), 0, 0))
    lip = bpy.context.object; lip.data.materials.append(al); bpy.ops.object.shade_smooth()
    bpy.ops.mesh.primitive_cone_add(radius1=1.6, radius2=1.35, depth=3.2, location=(0, 1.6, 0), rotation=(R(90), 0, 0), vertices=96, end_fill_type='NOTHING'); o = bpy.context.object; o.data.materials.append(al); bpy.ops.object.shade_smooth()
    bpy.ops.mesh.primitive_cylinder_add(radius=1.33, depth=1.8, location=(0, .9, 0), rotation=(R(90), 0, 0), vertices=96, end_fill_type='NOTHING')
    o = bpy.context.object; o.data.materials.append(dark); bpy.ops.object.shade_smooth()
    cyl('core', (0, 1.6, 0), .55, .2, dark, rot=(R(90), 0, 0), verts=48)
    bpy.ops.mesh.primitive_cone_add(radius1=.42, radius2=.0, depth=.9, location=(0, .25, 0), rotation=(R(90), 0, 0), vertices=48)
    sp = bpy.context.object; sp.data.materials.append(ti); bpy.ops.object.shade_smooth()
    for k in range(22):   # wide-chord fan blades
        a = k / 22 * 2 * math.pi
        b = box('blade', (math.cos(a) * .85, .75, math.sin(a) * .85), (.86, .04, .3), M('bl', (.55, .56, .58), .25, 1.0), .01)
        b.rotation_euler = (R(35), -a, 0)
    pyl = box('pylon', (0, 2.4, 2.0), (.5, 3.4, 1.2), al, .1)
    li = bpy.data.lights.new('ll', 'SPOT'); li.energy = 4000; li.spot_size = R(40); li.color = (1, .9, .75)
    o = kit.link(bpy.data.objects.new('ll', li)); o.location = (2.5, -1, -1.5); o.rotation_euler = Vector((0, -1, .1)).to_track_quat('-Z', 'Y').to_euler()
    area((-6, -8, 4), (0, 0, 0), 900, (.7, .8, 1), 5); area((5, -3, -4), (0, 0, 0), 500, (1, .6, .35), 4)
    cam((-1.9, -4.6, -.5), (0, .7, 0), 30, 3.2)
    proj('fan', (0, .75, 0))

def p_macro():
    gloom((.05, .06, .08), .5, .0)
    r = random.Random(3); gl = kit.mat_pbr('glass', 'vglass'); gl.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (.75, .72, .62, 1)
    rk = noise_mat('shardrock', (.08, .075, .07), (.25, .23, .21), 8.0, .7, .8, 120)
    for k in range(70):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=r.uniform(.15, .55), location=(r.uniform(-3, 3), r.uniform(-1, 5), r.uniform(-2.5, 3.5)))
        o = bpy.context.object
        for v in o.data.vertices: v.co *= r.uniform(.45, 1.5)
        o.scale = (r.uniform(.3, 1), r.uniform(.3, 1), r.uniform(.8, 2.2)); o.rotation_euler = (r.random() * 6, r.random() * 6, r.random() * 6)
        o.data.materials.append(gl if k % 3 == 0 else rk)
    area((0, 8, 3), (0, 0, 0), 2500, (1, .62, .3), 4); area((-6, -3, 2), (0, 0, 0), 600, (.4, .6, 1), 3); area((4, -4, -2), (0, 0, 0), 300, (1, .8, .6), 3)
    c = cam((0, -7, .4), (0, 1, .4), 60, 1.6); c.data.dof.focus_distance = 7.0
    proj('c', (0, 0, 0))

def p_geyser():
    kit.sky(sun_elevation=6, sun_rotation=240, strength=.2, sun_lamp_energy=3.0)
    ground(900, noise_mat('sinter', (.55, .52, .46), (.75, .72, .66), .3, .9, .3, 40))
    m = bpy.data.materials.new('pool'); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled')
    tc = N.new('ShaderNodeTexCoord'); g = N.new('ShaderNodeTexGradient'); g.gradient_type = 'SPHERICAL'
    mp = N.new('ShaderNodeVectorMath'); mp.operation = 'SCALE'; mp.inputs[3].default_value = 1 / 60; L.new(tc.outputs['Object'], mp.inputs[0]); L.new(mp.outputs[0], g.inputs[0])
    cr = N.new('ShaderNodeValToRGB'); e = cr.color_ramp.elements
    e[0].position = 0; e[0].color = (.55, .2, .05, 1); e[1].position = .25; e[1].color = (.85, .5, .08, 1)
    for p_, c_ in ((.4, (.75, .75, .2, 1)), (.5, (.15, .5, .35, 1)), (.62, (.02, .25, .55, 1)), (.9, (.0, .12, .4, 1))):
        el = e.new(p_); el.color = c_
    L.new(g.outputs['Fac'], cr.inputs[0]); L.new(cr.outputs[0], bs.inputs['Base Color']); bs.inputs['Roughness'].default_value = .08; L.new(bs.outputs[0], o.inputs[0])
    bpy.ops.mesh.primitive_circle_add(radius=60, fill_type='NGON', vertices=128, location=(0, 90, .02)); pl = bpy.context.object; pl.scale = (1, .8, 1)
    pl.data.materials.append(m)
    forest(-200, 200, 220, 320, 80, 3, 14, 22)
    cam((-6, -10, 34), (0, 85, 0), 26)
    proj('pool', (0, 90, 0)); proj('vent', (0, 90, 4))

def p_lava():
    kit.sky(sun_elevation=-2, sun_rotation=250, strength=.06, sun_lamp_energy=.2)
    ground(900, noise_mat('fl', (.02, .025, .02), (.05, .06, .04), .05, .95, .3, 20))
    t = kit.terrain(size=120, height=4, scale=4, kind='lava', seed=2); t.location = (0, 70, 1.0); t.scale = (1, .6, 1)
    for n in t.data.materials[0].node_tree.nodes:
        if n.type == 'MATH' and n.operation == 'MULTIPLY': n.inputs[1].default_value = 2.5
        if n.type == 'TEX_VORONOI': n.inputs['Scale'].default_value = 14
    forest(-60, 60, -10, 15, 40, 5, 10, 18); forest(-80, 80, 120, 180, 50, 8, 12, 20)
    for k in range(4):
        li = bpy.data.lights.new('lv', 'POINT'); li.energy = 1.5e5; li.color = (1, .35, .08); o = kit.link(bpy.data.objects.new('lv', li)); o.location = (-45 + k * 30, 50, 3)
    cam((0, 18, 5), (0, 50, 0), 28)
    proj('front', (0, 40, 0))

P = {k[2:]: v for k, v in globals().items() if k.startswith('p_')}
P[name]()
if FX: json.dump(FX, open(f'{OUT}/fx_{name}.json', 'w'))
sc.render.filepath = f'{OUT}/{name}.png'; bpy.ops.render.render(write_still=True); print('plate', name, 'done')
