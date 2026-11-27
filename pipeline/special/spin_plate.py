"""What if Earth suddenly stopped spinning?  One Cycles still per plate (animated in 2D by spin_anim.py, which also draws the
real-data globe itself with a numpy orthographic projection of the Blue Marble maps, so the spin and the stop are true motion).
python3 spin_plate.py <plate> [res_scale]  -> /home/claude/b3d/spin/plates/<plate>.png (+ fx_<plate>.json projected points)
Camera faces north (+Y), so EAST is screen-right: everything that keeps moving flies to the right.
plates: town (prairie town at golden hour, sun low in the west), towncu (close on the car and the house), coast (rough sea + rocky point
  with a lighthouse), desert (the day side: bare land under a high Sun), frozen (the night side: the same kind of farm, frosted, under stars)
sprites (RGBA, 600x600): sp_car, sp_board, sp_tree, sp_roof, sp_bin"""
import sys, math, os, json, random
sys.path.insert(0, '/home/claude/b3d')
import bpy, kit
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
name = sys.argv[1]; S = float(sys.argv[2]) if len(sys.argv) > 2 else .7
OUT = '/home/claude/b3d/spin/plates'; os.makedirs(OUT, exist_ok=True)
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

def farm(frost=0.0):
    """the shared farm layout (town / frozen): road along X, the farmhouse + barn + silo north of it, a second house east, trees, a power line"""
    road_x(0, 7.0, 600); power_line_x(5.5, -100, 140, frost=bool(frost))
    house(-9, 24, R(8), lit=not frost, frost=frost); barn(4, 34, frost)
    house(22, 30, R(-12), wall=(.42, .5, .55), roofc=(.1, .1, .12), lit=not frost, frost=frost, s=.85)
    lm = leaf_mat() if not frost else noise_mat('frostleaf', (.55, .6, .66), (.85, .9, .95), 1.5, .6, .8, 25)
    for k, (x, y, h) in enumerate([(-22, 18, 8), (-17, 30, 9), (12, 20, 7), (30, 22, 8.5), (-34, 40, 10), (40, 44, 9), (16, 52, 8), (-4, 58, 10)]):
        tree(x, y, h, k, mat=lm)
    for k in range(26):   # distant tree line
        tree(-150 + k * 12 + rnd.uniform(-4, 4), 120 + rnd.uniform(-10, 10), rnd.uniform(8, 13), 50 + k, mat=lm)

# ------------------------------------------------------------------ plates
def hills():
    t = kit.terrain(size=1400, height=30, scale=2, kind='grass', seed=2); t.location = (0, 760, -8)
def p_town():
    kit.sky(sun_elevation=2.5, sun_rotation=250, strength=.16, sun_lamp_energy=4.5, dust=2.0)
    ground(); farm(); hills(); car_body((2, -1.6, 0), 0)
    cam((-1.0, -10.5, 1.35), (2, 30, 4.6), 22)
    for k, p in {'car': (2, -1.6, .9), 'house': (-9, 24, 3), 'barn': (4, 34, 4), 'house2': (22, 30, 3), 'tree': (12, 20, 5), 'pole': (8, 5.5, 8)}.items(): proj(k, p)

def p_townempty():
    kit.sky(sun_elevation=2.5, sun_rotation=250, strength=.16, sun_lamp_energy=4.5, dust=2.0)
    ground(); farm(); hills(); cam((-1.0, -10.5, 1.35), (2, 30, 4.6), 22)

def p_towncuempty():
    kit.sky(sun_elevation=2.5, sun_rotation=250, strength=.16, sun_lamp_energy=4.5, dust=2.0)
    ground(); farm(); hills(); cam((7.5, -9.5, 1.1), (1.0, 6, 1.6), 30, 5.6)

def p_towncu():
    kit.sky(sun_elevation=2.5, sun_rotation=250, strength=.16, sun_lamp_energy=4.5, dust=2.0)
    ground(); farm(); hills(); car_body((2, -1.6, 0), 0)
    cam((7.5, -9.5, 1.1), (1.0, 6, 1.6), 30, 5.6)
    for k, p in {'car': (2, -1.6, .9), 'house': (-9, 24, 3), 'tree': (12, 20, 5)}.items(): proj(k, p)

def p_coast():
    kit.sky(sun_elevation=5, sun_rotation=250, strength=.3, sun_lamp_energy=3.5)
    o = kit.ocean(size=60, wave_scale=2.2, wind=16, choppy=1.5, resolution=16); md = o.modifiers['Ocean']; md.repeat_x = md.repeat_y = 10; o.location = (-300, -60, 0)
    rk = noise_mat('rockc', (.05, .05, .055), (.16, .15, .14), 1.2, .9, 1.0, 8)
    for k in range(9):   # the rocky point under the lighthouse
        r_ = random.Random(30 + k); bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=4, radius=r_.uniform(5, 11),
                                                                          location=(30 + k * 7 + r_.uniform(-3, 3), 50 + r_.uniform(-6, 10), r_.uniform(0, 2.5)))
        o = bpy.context.object; o.scale = (1, 1, r_.uniform(.45, .7)); o.data.materials.append(rk)
        d = o.modifiers.new('d', 'DISPLACE'); tx = bpy.data.textures.new('rkt', 'CLOUDS'); tx.noise_scale = 1.2; d.texture = tx; d.strength = 2.5
    lt = kit.link(bpy.data.objects.new('lh', None)); lt.location = (38, 52, 4)
    white = M('lhw', (.85, .85, .82), .6); red = M('lhr', (.55, .06, .05), .6)
    for k in range(5): cyl('lhs', (0, 0, 2 + k * 3.2), 2.2 - k * .2, 3.2, red if k % 2 else white, verts=32, r2=2.0 - k * .2, parent=lt)
    cyl('lamp', (0, 0, 18.8), 1.3, 1.8, kit.mat_emit('lhl', (1, .85, .55), 30), verts=24, parent=lt)
    cyl('cap', (0, 0, 20.4), 1.6, 1.4, M('lhc', (.08, .08, .09), .5), verts=24, r2=.2, parent=lt)
    
    cam((-6, -24, 3.6), (14, 40, 4), 24)
    proj('lighthouse', (38, 52, 14)); proj('sea', (0, 40, 0))

def p_desert():
    kit.sky(sun_elevation=30, sun_rotation=188, strength=.14, sun_lamp_energy=3.2, dust=3.0)
    t = kit.terrain(size=600, height=14, scale=2.5, kind='desert', seed=8); t.location = (0, 330, -4)
    cr = noise_mat('cracked', (.26, .15, .08), (.48, .32, .18), 2.0, .95, 1.2, 9)
    bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 10, -.05)); p = bpy.context.object; p.data.materials.append(cr)
    vo = p.active_material.node_tree; N = vo.nodes; L = vo.links
    v = N.new('ShaderNodeTexVoronoi'); v.feature = 'DISTANCE_TO_EDGE'; v.inputs['Scale'].default_value = .9; L.new(N['Texture Coordinate'].outputs['Object'], v.inputs['Vector'])
    bp = [n for n in N if n.type == 'BUMP'][0]; mr = N.new('ShaderNodeMapRange'); mr.inputs['From Max'].default_value = .06
    L.new(v.outputs['Distance'], mr.inputs['Value']); L.new(mr.outputs[0], bp.inputs['Height']); bp.inputs['Strength'].default_value = 1.0
    # a dead tree and the sun-bleached farmhouse shell
    g = kit.link(bpy.data.objects.new('dead', None)); g.location = (-3, 12, 0); bk = M('dbark', (.22, .17, .12), .9)
    cyl('dt', (0, 0, 2.2), .25, 4.4, bk, verts=10, r2=.12, parent=g)
    for k, (a, e, l) in enumerate([(20, 40, 2.4), (150, 35, 2.0), (260, 50, 1.8), (80, 60, 1.5)]):
        d = Vector((math.cos(R(a)) * math.cos(R(e)), math.sin(R(a)) * math.cos(R(e)), math.sin(R(e)))); st = Vector((0, 0, 2.6 + k * .5))
        o = cyl('br', tuple(st + d * l / 2), .1, l, bk, verts=8, r2=.03, parent=g); o.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    house(14, 46, R(-8), wall=(.62, .55, .45), roofc=(.3, .22, .16), lit=False)
    cam((0, -9, 1.6), (2, 30, 4.5), 22)
    proj('sun_dir', (0, 0, 0)); proj('tree', (-3, 12, 3))

def p_frozen():
    kit.world(strength=.4)
    li = kit.sun_lamp(Vector((-.3, .8, .25)).normalized(), .25, (.6, .7, 1))
    sn = noise_mat('snowg', (.62, .66, .72), (.9, .93, .97), .3, .45, .3, 30)
    ground(mat=sn); farm(frost=1.0); car_body((2, -1.6, 0), 0, col=(.6, .62, .66), lights=False)
    for o in [o for o in bpy.data.objects if o.name.startswith(('road', 'dash'))]: o.data.materials[0] = sn
    area((0, -30, 25), (0, 20, 0), 2500, (.45, .6, 1), 30)
    cam((-1.5, -15, 2.4), (2, 30, 3.2), 22)
    proj('house', (-9, 24, 3)); proj('car', (2, -1.6, .9))

def sprite(kind):
    sc.render.film_transparent = True; kit.sky(sun_elevation=9, sun_rotation=242, strength=.35, sun_lamp_energy=4.0)
    area((3, -4, 3), (0, 0, 0), 150, (1, .8, .6), 3)
    if kind == 'sp_car': car_body((0, 0, 0), 0); return cam((-2, -11, 3.0), (0, 0, .8), 35)
    if kind == 'sp_board':
        box('board', (0, 0, 0), (2.4, .2, .06), M('bd', (.45, .3, .16), .7), .006, rot=(R(20), R(10), R(15))); return cam((0, -5, .6), (0, 0, 0), 40)
    if kind == 'sp_tree': tree(0, 0, 7, 3); return cam((0, -22, 4), (0, 0, 3.6), 35)
    if kind == 'sp_roof':
        box('roofp', (0, 0, 0), (3, 2, .14), M('roof', (.16, .1, .08), .8), .02, rot=(R(55), R(15), R(20))); return cam((0, -8, .5), (0, 0, 0), 40)
    if kind == 'sp_bin':
        cyl('bin', (0, 0, 0), .35, .95, M('binm', (.2, .32, .22), .5, .3), rot=(R(70), 0, R(30)), verts=24); return cam((0, -4, .3), (0, 0, 0), 40)

P = {k[2:]: v for k, v in globals().items() if k.startswith('p_')}
if SPRITE: sprite(name)
else: P[name]()
if FX: json.dump(FX, open(f'{OUT}/fx_{name}.json', 'w'))
sc.render.filepath = f'{OUT}/{name}.png'; bpy.ops.render.render(write_still=True); print('plate', name, 'done')
