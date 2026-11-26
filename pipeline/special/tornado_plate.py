"""Pick where to hide from a tornado. One Cycles still per plate; tornado_anim.py paints the storm sky + the funnel in 2D behind the
(transparent-sky) outdoor plates, adds wind shake, flying debris sprites and the graphics.
python3 tornado_plate.py <plate> [res_scale] -> tornado/plates/<plate>.png (+ .txt with 2D points)
outdoor plates (sky transparent): plains (wide prairie road, Leo), leocu (close on Leo), overpass (Leo climbing under a highway bridge),
  overcu (close under the girders), car (car on the road), ditch (Leo flat in the ditch, car above), mobile (mobile home on tie-downs),
  mobilecu (close on the tie-down straps)
indoor plates: basement (Leo under the workbench), basecu (close, Leo covering his head), bath (small windowless bathroom, Leo in the tub)
sprites (RGBA): sp_board, sp_shingle, sp_metal, sp_car"""
import sys, math, os, random
sys.path.insert(0, '/home/claude/b3d')
import bpy, kit
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
name = sys.argv[1]; S = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
OUT = '/home/claude/b3d/tornado/plates'; os.makedirs(OUT, exist_ok=True)
SPRITE = name.startswith('sp_')
W, H = (int(700 * S), int(700 * S)) if SPRITE else (int(1080 * S), int(1920 * S))
sc = kit.reset(res=(W, H), samples=int(os.environ.get('SAMPLES', 40)))
sc.cycles.adaptive_threshold = 0.03; sc.cycles.max_bounces = 5; sc.cycles.diffuse_bounces = 3
random.seed(7); PTS = {}
OUTDOOR = name in ('plains', 'leocu', 'overpass', 'overcu', 'car', 'ditch', 'mobile', 'mobilecu')
if OUTDOOR: sc.render.film_transparent = True

def M(nm, col, rough=.5, metal=0.0, coat=0.0): return kit.mat_principled(nm, col, rough=rough, metal=metal, coat=coat)
def box(nm, loc, size, mat, bevel=.01, rot=(0, 0, 0), parent=None):
    bpy.ops.mesh.primitive_cube_add(location=loc); o = bpy.context.object; o.name = nm; o.scale = (size[0] / 2, size[1] / 2, size[2] / 2)
    o.rotation_euler = rot; bpy.ops.object.transform_apply(scale=True); o.data.materials.append(mat)
    if bevel: b = o.modifiers.new('b', 'BEVEL'); b.width = bevel; b.segments = 3
    if parent: o.parent = parent
    return o
def cyl(nm, loc, r, depth, mat, rot=(0, 0, 0), verts=48, r2=None):
    if r2 is None: bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=depth, location=loc, rotation=rot, vertices=verts)
    else: bpy.ops.mesh.primitive_cone_add(radius1=r, radius2=r2, depth=depth, location=loc, rotation=rot, vertices=verts)
    o = bpy.context.object; o.name = nm; o.data.materials.append(mat); bpy.ops.object.shade_smooth(); return o
def area(nm, loc, aim, energy, color=(1, 1, 1), size=2.0):
    li = bpy.data.lights.new(nm, 'AREA'); li.energy = energy; li.color = color; li.size = size
    o = kit.link(bpy.data.objects.new(nm, li)); o.location = loc
    o.rotation_euler = (Vector(aim) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler(); return o
def point(nm, loc, energy, color, radius=.05):
    li = bpy.data.lights.new(nm, 'POINT'); li.energy = energy; li.color = color; li.shadow_soft_size = radius
    o = kit.link(bpy.data.objects.new(nm, li)); o.location = loc; return o
def flat_world(col, strength=1.0):
    w = bpy.data.worlds.new('w'); sc.world = w; nt, N, L = kit.nodes(w)
    o = N.new('ShaderNodeOutputWorld'); bg = N.new('ShaderNodeBackground'); bg.inputs['Color'].default_value = (*col, 1)
    bg.inputs['Strength'].default_value = strength; L.new(bg.outputs[0], o.inputs['Surface'])
def cam(loc, look, lens, fstop=None):
    c, t = kit.camera(loc, look, lens=lens)
    if fstop: c.data.dof.use_dof = True; c.data.dof.focus_distance = (Vector(loc) - Vector(look)).length; c.data.dof.aperture_fstop = fstop
    return c
def proj(c, p):
    v = world_to_camera_view(sc, c, Vector(p)); return (round(v.x, 4), round(1 - v.y, 4))

def wood_mat(nm='wood', col=(.32, .18, .09), scale=(1, 18, 1)):
    m = bpy.data.materials.new(nm); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled')
    tc = N.new('ShaderNodeTexCoord'); mp = N.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = scale
    nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 6; nz.inputs['Detail'].default_value = 8; nz.inputs['Distortion'].default_value = 3
    L.new(tc.outputs['Object'], mp.inputs[0]); L.new(mp.outputs[0], nz.inputs[0])
    cr = N.new('ShaderNodeValToRGB'); cr.color_ramp.elements[0].color = (col[0] * .55, col[1] * .55, col[2] * .55, 1); cr.color_ramp.elements[1].color = (*col, 1)
    L.new(nz.outputs['Fac'], cr.inputs[0]); L.new(cr.outputs[0], bs.inputs['Base Color']); bs.inputs['Roughness'].default_value = .45
    bs.inputs['Coat Weight'].default_value = .25; L.new(bs.outputs[0], o.inputs[0]); return m
def plank_mat():
    m = bpy.data.materials.new('planks'); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled')
    tc = N.new('ShaderNodeTexCoord'); sep = N.new('ShaderNodeSeparateXYZ'); L.new(tc.outputs['Object'], sep.inputs[0])
    mul = N.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; mul.inputs[1].default_value = 1 / .18; L.new(sep.outputs['X'], mul.inputs[0])
    fl = N.new('ShaderNodeMath'); fl.operation = 'FLOOR'; L.new(mul.outputs[0], fl.inputs[0])
    fr = N.new('ShaderNodeMath'); fr.operation = 'FRACT'; L.new(mul.outputs[0], fr.inputs[0])
    seam = N.new('ShaderNodeMath'); seam.operation = 'LESS_THAN'; seam.inputs[1].default_value = .03; L.new(fr.outputs[0], seam.inputs[0])
    wn = N.new('ShaderNodeTexWhiteNoise'); wn.noise_dimensions = '1D'; L.new(fl.outputs[0], wn.inputs['W'])
    nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 3; nz.inputs['Detail'].default_value = 6; nz.inputs['Distortion'].default_value = 4
    mp = N.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (14, 1, 1); L.new(tc.outputs['Object'], mp.inputs[0]); L.new(mp.outputs[0], nz.inputs[0])
    mx0 = N.new('ShaderNodeMath'); mx0.operation = 'MULTIPLY_ADD'; mx0.inputs[1].default_value = .35; L.new(nz.outputs['Fac'], mx0.inputs[0]); L.new(wn.outputs['Value'], mx0.inputs[2])
    cr = N.new('ShaderNodeValToRGB'); cr.color_ramp.elements[0].color = (.12, .06, .03, 1); cr.color_ramp.elements[1].color = (.36, .2, .1, 1)
    L.new(mx0.outputs[0], cr.inputs[0])
    mx = N.new('ShaderNodeMixRGB'); L.new(seam.outputs[0], mx.inputs['Fac']); L.new(cr.outputs[0], mx.inputs[1]); mx.inputs[2].default_value = (.03, .015, .01, 1)
    L.new(mx.outputs[0], bs.inputs['Base Color']); bs.inputs['Roughness'].default_value = .5
    L.new(bs.outputs[0], o.inputs[0]); return m
def wall_mat(nm='wall', col=(.11, .2, .24)):
    m = bpy.data.materials.new(nm); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled')
    tc = N.new('ShaderNodeTexCoord'); nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 3; nz.inputs['Detail'].default_value = 10
    L.new(tc.outputs['Object'], nz.inputs[0]); cr = N.new('ShaderNodeValToRGB')
    cr.color_ramp.elements[0].color = (col[0] * .8, col[1] * .8, col[2] * .8, 1); cr.color_ramp.elements[1].color = (*col, 1)
    L.new(nz.outputs['Fac'], cr.inputs[0]); L.new(cr.outputs[0], bs.inputs['Base Color']); bs.inputs['Roughness'].default_value = .85
    L.new(bs.outputs[0], o.inputs[0]); return m
def fabric(nm, col):
    m = M(nm, col, .9); b = m.node_tree.nodes['Principled BSDF']; b.inputs['Sheen Weight'].default_value = .6; return m
def night_sky_mat():
    m = bpy.data.materials.new('outside'); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); e = N.new('ShaderNodeEmission')
    tc = N.new('ShaderNodeTexCoord'); vor = N.new('ShaderNodeTexVoronoi'); vor.inputs['Scale'].default_value = 90; L.new(tc.outputs['Object'], vor.inputs[0])
    st = N.new('ShaderNodeMapRange'); st.inputs['From Min'].default_value = 0; st.inputs['From Max'].default_value = .05
    st.inputs['To Min'].default_value = 6; st.inputs['To Max'].default_value = 0; st.clamp = True; L.new(vor.outputs['Distance'], st.inputs[0])
    gate = N.new('ShaderNodeMath'); gate.operation = 'GREATER_THAN'; gate.inputs[1].default_value = .85; L.new(vor.outputs['Color'], gate.inputs[0])
    mm = N.new('ShaderNodeMath'); mm.operation = 'MULTIPLY'; L.new(st.outputs[0], mm.inputs[0]); L.new(gate.outputs[0], mm.inputs[1])
    add = N.new('ShaderNodeMath'); add.operation = 'ADD'; add.inputs[1].default_value = .035; L.new(mm.outputs[0], add.inputs[0])
    cc = N.new('ShaderNodeCombineColor'); L.new(add.outputs[0], cc.inputs[0]); L.new(add.outputs[0], cc.inputs[1])
    m2 = N.new('ShaderNodeMath'); m2.operation = 'ADD'; m2.inputs[1].default_value = .06; L.new(add.outputs[0], m2.inputs[0]); L.new(m2.outputs[0], cc.inputs[2])
    L.new(cc.outputs[0], e.inputs['Color']); L.new(e.outputs[0], o.inputs[0]); return m

# ------------------------------------------------------------------ Leo with poses
def head_group(root, tilt):
    """keep the head (and hair) upright while the body tilts: reparent everything above the shoulders to a pivot at the neck"""
    piv = kit.link(bpy.data.objects.new('neckpiv', None)); piv.parent = root; piv.location = (0, 0, .6)
    bpy.context.view_layer.update()
    for ch in list(root.children):
        if ch.type == 'MESH' and ch.location.z > .585:
            mw = ch.matrix_world.copy(); ch.parent = piv; ch.matrix_world = mw
    bpy.context.view_layer.update(); piv.rotation_euler = (tilt, 0, 0); return piv
def leo(pose='stand', expr='scared', loc=(0, 0, 0), yaw=0.0, h=1.2):
    root, parts = kit.character('leo', (0, 0, 0), h); R = math.radians
    parts['face_mat'].node_tree.nodes['expr'].outputs[0].default_value = kit.EXPRS.index(expr)
    al, ar, ll, lr = parts['arm_l'], parts['arm_r'], parts['leg_l'], parts['leg_r']
    rot = (0, 0, yaw); z = 0
    if pose == 'panic':                      # standing, hands up by his head
        al.rotation_euler = (0, R(-145), 0); ar.rotation_euler = (0, R(145), 0)
    elif pose == 'brace':                    # arms out, pushing on both sides of the door frame
        al.rotation_euler = (0, R(-100), 0); ar.rotation_euler = (0, R(100), 0)
    elif pose == 'run':
        ll.rotation_euler = (R(-40), 0, 0); lr.rotation_euler = (R(35), 0, 0)
        al.rotation_euler = (R(45), R(-15), 0); ar.rotation_euler = (R(-50), R(15), 0)
        rot = (R(12), 0, yaw)
    elif pose == 'fallen':                   # face down on the floor, arms out in front
        rot = (R(88), 0, yaw); z = .1 * h
        al.rotation_euler = (R(-160), R(-20), 0); ar.rotation_euler = (R(-150), R(20), 0)
        head_group(root, R(-50))
    elif pose == 'curl':                     # lying on his side, knees pulled up (fetal), hands by his face
        rot = (0, R(-90), yaw); z = .17 * h
        ll.rotation_euler = (R(-95), 0, 0); lr.rotation_euler = (R(-85), 0, 0)
        al.rotation_euler = (R(-120), R(10), 0); ar.rotation_euler = (R(-110), R(-10), 0)
    elif pose == 'crawl':                    # hands and knees, head up; one hand holding the table leg
        rot = (R(72), 0, yaw); z = .23 * h
        ll.rotation_euler = (R(-75), 0, 0); lr.rotation_euler = (R(-75), 0, 0)
        al.rotation_euler = (R(-62), 0, 0); ar.rotation_euler = (R(-100), R(25), 0)
        head_group(root, R(-55))
    elif pose == 'kneel':                    # kneeling, curled forward, both arms over the head and neck
        rot = (R(35), 0, yaw); z = .1 * h
        ll.rotation_euler = (R(-120), 0, 0); lr.rotation_euler = (R(-120), 0, 0)
        al.rotation_euler = (R(-160), R(-35), 0); ar.rotation_euler = (R(-160), R(35), 0)
    elif pose == 'bed':                      # on his back, both hands holding the pillow over his head
        rot = (R(-90), 0, yaw); z = .14 * h
        al.rotation_euler = (R(-150), R(-30), 0); ar.rotation_euler = (R(-150), R(30), 0)
    root.rotation_euler = rot; root.location = (loc[0], loc[1], loc[2] + z)
    return root, parts

def brick_mat(scale=2.4):
    m = bpy.data.materials.new('brick'); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled')
    tc = N.new('ShaderNodeTexCoord'); br = N.new('ShaderNodeTexBrick'); br.inputs['Scale'].default_value = scale
    mpb = N.new('ShaderNodeMapping'); mpb.inputs['Rotation'].default_value = (math.pi / 2, 0, 0); L.new(tc.outputs['Object'], mpb.inputs[0])
    br.inputs['Color1'].default_value = (.32, .1, .05, 1); br.inputs['Color2'].default_value = (.22, .07, .04, 1); br.inputs['Mortar'].default_value = (.35, .33, .3, 1)
    br.inputs['Mortar Size'].default_value = .015; L.new(mpb.outputs[0], br.inputs['Vector'])
    L.new(br.outputs['Color'], bs.inputs['Base Color']); bs.inputs['Roughness'].default_value = .9
    bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = .4; L.new(br.outputs['Fac'], bp.inputs['Height']); L.new(bp.outputs[0], bs.inputs['Normal'])
    L.new(bs.outputs[0], o.inputs[0]); return m
R = math.radians
# ------------------------------------------------------------------ outdoor helpers
def storm_world():
    """dark green-grey storm ambient (the sky itself is painted in 2D by tornado_anim.py)"""
    flat_world((.05, .075, .075), 1.3)
    s = bpy.data.lights.new('sun', 'SUN'); s.energy = 1.1; s.color = (.75, .85, .9); s.angle = R(25)
    o = kit.link(bpy.data.objects.new('sun', s)); o.rotation_euler = (R(50), 0, R(30))
def grass_mat():
    m = bpy.data.materials.new('grass'); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled')
    tc = N.new('ShaderNodeTexCoord'); nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = .35; nz.inputs['Detail'].default_value = 12
    L.new(tc.outputs['Object'], nz.inputs[0]); cr = N.new('ShaderNodeValToRGB')
    cr.color_ramp.elements[0].color = (.06, .08, .025, 1); cr.color_ramp.elements[1].color = (.2, .2, .07, 1)
    L.new(nz.outputs['Fac'], cr.inputs[0]); L.new(cr.outputs[0], bs.inputs['Base Color']); bs.inputs['Roughness'].default_value = .95
    n2 = N.new('ShaderNodeTexNoise'); n2.inputs['Scale'].default_value = 60; L.new(tc.outputs['Object'], n2.inputs[0])
    bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = .5; L.new(n2.outputs['Fac'], bp.inputs['Height']); L.new(bp.outputs[0], bs.inputs['Normal'])
    L.new(bs.outputs[0], o.inputs[0]); return m
def asphalt():
    m = bpy.data.materials.new('asph'); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled')
    tc = N.new('ShaderNodeTexCoord'); nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 40; nz.inputs['Detail'].default_value = 10
    L.new(tc.outputs['Object'], nz.inputs[0]); cr = N.new('ShaderNodeValToRGB')
    cr.color_ramp.elements[0].color = (.025, .027, .03, 1); cr.color_ramp.elements[1].color = (.07, .07, .075, 1)
    L.new(nz.outputs['Fac'], cr.inputs[0]); L.new(cr.outputs[0], bs.inputs['Base Color']); bs.inputs['Roughness'].default_value = .55
    L.new(bs.outputs[0], o.inputs[0]); return m
def concrete(nm='conc', col=(.42, .42, .4)):
    m = wall_mat(nm, col); m.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = .92; return m
def ground(size=600):
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, -.02)); g = bpy.context.object; g.data.materials.append(grass_mat())
def road_y(x, w=7.0, L=400, y0=0):   # a two-lane road running along Y
    box('road', (x, y0, 0), (w, L, .04), asphalt(), 0)
    ln = kit.mat_emit('paint', (.9, .75, .25), .15)
    for k in range(-60, 120): box('dash', (x, y0 + k * 6, .022), (.12, 3, .005), ln, 0)
def road_x(y, w=7.0, L=400, z=0.0):
    box('roadx', (0, y, z), (L, w, .04), asphalt(), 0)
    ln = kit.mat_emit('paintx', (.9, .75, .25), .15)
    for k in range(-60, 60): box('dashx', (k * 6, y, z + .022), (3, .12, .005), ln, 0)
def fence(x, y0, y1, step=4.0):
    wd = wood_mat('post', (.2, .14, .09), (1, 1, 10)); y = y0
    while y < y1:
        box('fpost', (x, y, .6), (.12, .12, 1.2), wd, .01); y += step
    for z in (.5, .95): box('wire', (x, (y0 + y1) / 2, z), (.015, y1 - y0, .015), M('wire', (.2, .2, .2), .4, .8), 0)
def power_line(x, y0, y1, step=40.0):
    wd = wood_mat('pole', (.18, .12, .08), (1, 1, 6)); y = y0; tops = []
    while y < y1:
        cyl('ppole', (x, y, 5), .14, 10, wd); box('xarm', (x, y, 9.4), (2.2, .14, .14), wd, .01); tops.append(y); y += step
    for dx in (-.9, .9):
        for a, b in zip(tops[:-1], tops[1:]): box('cable', (x + dx, (a + b) / 2, 9.2), (.02, b - a, .02), M('cab', (.03, .03, .03), .5), 0)
def farmhouse(x, y, yaw=0.0):
    base = kit.link(bpy.data.objects.new('farm', None)); base.location = (x, y, 0); base.rotation_euler = (0, 0, yaw)
    sid = M('siding', (.55, .52, .46), .8); roof = M('roof', (.12, .1, .1), .8)
    box('fh', (0, 0, 2.2), (9, 7, 4.4), sid, .02, parent=base)
    for s in (-1, 1): box('rf', (0, s * 1.9, 5.1), (9.6, 4.4, .25), roof, .02, rot=(s * R(-32), 0, 0), parent=base)
    lit = kit.mat_emit('flit', (1, .62, .3), 3.0)
    for xx in (-2.8, 0, 2.8): box('fw', (xx, -3.52, 2.6), (1.1, .05, 1.4), lit, 0, parent=base)
    box('barn', (14, 6, 3.5), (8, 10, 7), M('barn', (.32, .07, .05), .85), .02, parent=base)
    cyl('silo', (21, 3, 7), 2.2, 14, M('silo', (.5, .52, .55), .4, .7)).parent = base

def car_body(loc=(0, 0, 0), yaw=0.0, col=(.55, .07, .06), lights=True, driver=False):
    root = kit.link(bpy.data.objects.new('car', None)); root.location = loc; root.rotation_euler = (0, 0, yaw)
    paint = M('paint', col, .25, .3, 1.0); glass = M('cglass', (.02, .03, .04), .05, .5); blk = M('trimb', (.02, .02, .02), .5)
    b = box('body', (0, 0, .62), (4.5, 1.8, .7), paint, .12, parent=root)
    cab = box('cab', (-.25, 0, 1.15), (2.3, 1.6, .62), paint, .14, parent=root)
    for s in (-1, 1): box('side_glass', (-.25, s * .805, 1.17), (2.0, .02, .44), glass, .02, parent=root)
    box('wind', (.93, 0, 1.15), (.06, 1.45, .48), glass, .02, rot=(0, R(-35), 0), parent=root)
    box('rear', (-1.42, 0, 1.15), (.06, 1.45, .45), glass, .02, rot=(0, R(30), 0), parent=root)
    for sx in (-1.45, 1.45):
        for sy in (-.9, .9):
            w = cyl('tire', (sx, sy, .36), .36, .26, M('tire', (.02, .02, .02), .8), rot=(R(90), 0, 0)); w.parent = root
            h = cyl('hub', (sx, sy * 1.005, .36), .2, .27, M('hub', (.6, .6, .62), .3, 1.0), rot=(R(90), 0, 0)); h.parent = root
    box('bumpf', (2.27, 0, .45), (.1, 1.75, .22), blk, .03, parent=root); box('bumpr', (-2.27, 0, .45), (.1, 1.75, .22), blk, .03, parent=root)
    if lights:
        hl = kit.mat_emit('head', (1, .92, .75), 25); tl = kit.mat_emit('tail', (1, .05, .03), 12)
        for sy in (-.62, .62):
            box('hl', (2.255, sy, .72), (.04, .34, .14), hl, .01, parent=root); box('tl', (-2.255, sy, .72), (.04, .3, .12), tl, .01, parent=root)
    if driver:
        r_, p_ = leo('panic', 'scared', (0, 0, 0), 0, .95); r_.parent = root; r_.location = (-.2, .35, .45); r_.rotation_euler = (0, 0, R(90))
    return root

def wedge(nm, x0, x1, y0, y1, z0, z1, mat):
    """sloped embankment: height z0 at x0 rising to z1 at x1"""
    me = bpy.data.meshes.new(nm); v = [(x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0), (x0, y0, z0), (x1, y0, z1), (x1, y1, z1), (x0, y1, z0)]
    f = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    me.from_pydata(v, [], f); o = kit.link(bpy.data.objects.new(nm, me)); o.data.materials.append(mat); return o
def overpass():
    """a highway bridge (deck + girders) over a two-lane road, with concrete-paved slopes that climb up under the deck"""
    storm_world(); ground(); road_y(0, 7.5, 400, 100)
    cm = concrete('slab', (.4, .4, .38)); cm2 = concrete('slope', (.33, .33, .31))
    for s in (-1, 1):
        o = wedge('emb', s * 4.5, s * 10.5, -6.5, 6.5, 0, 5.0, cm2)
        if s < 0: 
            for p in o.data.polygons: p.flip()
        box('abut', (s * 11.2, 0, 2.6), (1.4, 13, 5.2), cm, .03)
        box('berm', (s * 40, 0, 2.6), (58, 13, 5.2), grass_mat(), 0)
    box('deck', (0, 0, 5.75), (110, 12.6, .55), cm, .04)
    for k in range(6):
        yy = -5.2 + k * 2.08; box('girder', (0, yy, 5.15), (23.4, .45, .75), concrete('gird', (.45, .45, .43)), .02)
        box('flange', (0, yy, 4.8), (23.4, .7, .1), concrete('gird2', (.45, .45, .43)), .01)
    for s in (-1, 1):
        box('rail', (0, s * 6.1, 6.45), (110, .3, .85), cm, .04)
    cyl('lp', (8, -7, 8.5), .1, 5, M('lp', (.3, .3, .32), .4, .7))
    if name == 'overpass':
        leo('crawl', 'scared', (-8.4, -5.4, 3.35), R(-90), 1.4); PTS['leo'] = (-8.4, -5.4, 3.8)
        PTS['gap'] = (0, 0, 2.6); PTS['under'] = (-7.0, 0, 4.4); PTS['top'] = (0, 0, 6.2)
        return cam((-.5, -19, 3.2), (-5.0, 0, 3.2), 24)
    leo('crawl', 'scared', (-8.6, -1.2, 3.55), R(-90), 1.4); PTS['leo'] = (-8.6, -1.2, 4.0); PTS['under'] = (-7.0, 0, 4.4)
    area('under', (-5.5, -4.5, 3.0), (-8.6, -1.2, 4.0), 50, (.65, .8, .85), 3.0)
    return cam((-4.6, -6.8, 3.0), (-8.5, -1.0, 4.0), 30, 4.0)

def plains():
    storm_world(); ground(); road_y(0, 7.0, 600, 250); fence(-5.5, -20, 200); power_line(6.5, -30, 400)
    farmhouse(-26, 70, R(10))
    if name == 'plains':
        leo('panic', 'scared', (-.5, -3.2, 0), R(-15), 1.4); PTS['leo'] = (-.5, -3.2, 1.2)
        PTS['funnel_base'] = (6, 160, 0); PTS['farm'] = (-26, 70, 3)
        return cam((.6, -7.4, 1.3), (-.6, 20, 4.8), 20)
    leo('panic', 'scared', (-.5, -3.2, 0), R(-15), 1.4); PTS['leo'] = (-.5, -3.2, 1.1)
    return cam((.4, -6.0, 1.15), (-.45, -3.2, 1.05), 40, 2.5)

def car_set():
    storm_world(); ground(); road_x(0, 7.0); power_line(-30, -6.5, 400) if False else None
    fence_x = wood_mat('post', (.2, .14, .09), (1, 1, 10))
    for k in range(-30, 30): box('fpost', (k * 4, 6, .6), (.12, .12, 1.2), fence_x, .01)
    if name == 'car':
        car_body((0, -1.8, 0), R(0), driver=True); PTS['car'] = (0, -1.8, .9)
        return cam((5.0, -7.6, 1.35), (-.3, -1.4, 1.1), 28)
    # ditch: the road is raised, a ditch runs beside it, Leo lies flat in it, hands over his head, the car stopped above
    bpy.data.objects['roadx'].location.z = .55
    for o in [o for o in bpy.data.objects if o.name.startswith('dashx')]: o.location.z = .577
    wedge('shoulder', -200, 200, -3.6, -3.5, .55, .55, grass_mat())
    me = bpy.data.meshes.new('ditch'); v = []
    prof = [(-3.5, .55), (-4.4, .1), (-5.0, -.25), (-5.6, -.25), (-6.3, .1), (-7.5, .3)]
    for x in (-200, 200):
        for yy, zz in prof: v.append((x, yy, zz))
    n = len(prof); f = [(i, i + 1, n + i + 1, n + i) for i in range(n - 1)]
    me.from_pydata(v, [], f); o = kit.link(bpy.data.objects.new('ditch', me)); o.data.materials.append(grass_mat())
    box('fill', (0, -1.75, .27), (400, 3.6, .55), grass_mat(), 0); box('fill2', (0, 1.75 + 3.5, .27), (400, 3.6, .55), grass_mat(), 0)
    car_body((1.5, -1.6, .55), R(0), lights=True); PTS['car'] = (1.5, -1.6, 1.4)
    leo('fallen', 'scared', (-.6, -5.3, -.25), R(90), 1.35); PTS['leo'] = (-.6, -5.3, 0)
    return cam((.4, -9.8, 2.3), (-.3, -4.6, .05), 26)

def siding():
    m = bpy.data.materials.new('mhside'); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled')
    tc = N.new('ShaderNodeTexCoord'); wv = N.new('ShaderNodeTexWave'); wv.wave_type = 'BANDS'; wv.bands_direction = 'Z'; wv.inputs['Scale'].default_value = 4
    L.new(tc.outputs['Object'], wv.inputs[0]); bs.inputs['Base Color'].default_value = (.72, .72, .68, 1); bs.inputs['Roughness'].default_value = .5
    bs.inputs['Metallic'].default_value = .4
    bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = .3; L.new(wv.outputs['Fac'], bp.inputs['Height']); L.new(bp.outputs[0], bs.inputs['Normal'])
    L.new(bs.outputs[0], o.inputs[0]); return m
def mobile():
    storm_world(); ground()
    sd = siding(); trim = M('mtrim', (.18, .3, .38), .5); lit = kit.mat_emit('mlit', (1, .62, .3), 2.5); steel = M('strap', (.6, .6, .62), .35, 1.0)
    z0 = .75; Lx, Wy, Hz = 14.0, 4.2, 2.6
    box('mh', (0, 0, z0 + Hz / 2), (Lx, Wy, Hz), sd, .03)
    box('mroof', (0, 0, z0 + Hz + .08), (Lx + .2, Wy + .25, .16), M('mroof', (.5, .5, .5), .4, .6), .03)
    box('skirt', (0, 0, z0 / 2), (Lx - .2, Wy - .2, z0), M('skirt', (.3, .32, .32), .8), 0)
    for k, xx in enumerate((-5, -2.4, 2.6, 5.2)): box('mwin', (xx, -Wy / 2 - .01, z0 + 1.5), (1.1, .02, .9), lit, 0); box('shut', (xx - .7, -Wy / 2 - .02, z0 + 1.5), (.25, .03, .95), trim, .005); box('shut2', (xx + .7, -Wy / 2 - .02, z0 + 1.5), (.25, .03, .95), trim, .005)
    box('mdoor', (0, -Wy / 2 - .01, z0 + 1.0), (.9, .03, 2.0), trim, .01)
    for k in range(3): box('mstep', (0, -Wy / 2 - .3 - k * .28, z0 - .12 - k * .25), (1.3, .3, .1), wood_mat('st', (.3, .2, .12)), .01)
    # tie-down straps: from the frame down to ground anchors
    for xx in (-6, -2, 2, 6):
        a = Vector((xx, -Wy / 2 + .1, z0 - .05)); b = Vector((xx - .9, -Wy / 2 - 1.3, .02)); mid = (a + b) / 2; d = b - a
        cyl('strap', tuple(mid), .03, d.length, steel, rot=tuple(d.to_track_quat('Z', 'Y').to_euler()), verts=12)
        cyl('anchor', (b.x, b.y, .03), .07, .08, steel); cyl('anchorhead', (b.x, b.y, .1), .025, .2, steel)
    PTS['strap'] = (-2.45, -Wy / 2 - .65, .4); PTS['mh'] = (0, 0, 2.0); PTS['roof'] = (0, 0, z0 + Hz)
    cyl('tree', (-11, 8, 3), .25, 6, M('bark', (.12, .08, .05), .9))
    for k in range(3): bpy.ops.mesh.primitive_ico_sphere_add(radius=2.2 - k * .4, location=(-11, 8, 5.5 + k * 1.2), subdivisions=3); bpy.context.object.data.materials.append(M('leaf', (.05, .09, .03), .8))
    if name == 'mobile': return cam((10.5, -15.5, 2.4), (0, 0, 2.2), 26)
    return cam((-1.2, -5.1, .75), (-2.45, -2.7, .35), 30, 3.0)

def basement():
    flat_world((.01, .012, .015), 1.0)
    box('bfloor', (0, 0, -.01), (6, 6, .02), concrete('bfl', (.3, .3, .29)), 0); box('bceil', (0, 0, 2.31), (6, 6, .02), wood_mat('joist', (.25, .17, .1)), 0)
    for k in range(9): box('joist', (-2.4 + k * .6, 0, 2.2), (.06, 6, .2), wood_mat('j', (.3, .2, .12)), .005)
    blk = brick_mat(1.2)
    for nd in blk.node_tree.nodes:
        if nd.type == 'TEX_BRICK': nd.inputs['Color1'].default_value = (.3, .3, .29, 1); nd.inputs['Color2'].default_value = (.25, .25, .24, 1); nd.inputs['Mortar'].default_value = (.38, .38, .36, 1)
    box('bwall', (0, 2.0, 1.15), (6, .2, 2.3), blk, 0); box('bwallL', (-2.4, 0, 1.15), (.2, 6, 2.3), blk, 0); box('bwallR', (2.6, 0, 1.15), (.2, 6, 2.3), blk, 0)
    # small high window (far right), cool storm light
    box('bwin', (1.6, 1.89, 1.95), (.8, .02, .35), kit.mat_emit('bwinl', (.35, .5, .5), 1.2), 0)
    area('winl', (1.6, 1.6, 1.9), (1.0, 0, .3), 25, (.5, .7, .75), .8)
    # stairs up (left)
    wd = wood_mat('stair', (.32, .2, .1))
    for k in range(8): box('tread', (-1.75, 1.3 - k * .27, .2 + k * .27), (.9, .27, .04), wd, .005)
    box('stringer', (-2.22, .35, 1.1), (.05, 2.8, .25), wd, 0, rot=(R(45), 0, 0))
    # sturdy workbench, shelves with cans
    tw = wood_mat('bench', (.36, .22, .1)); bx, by = .45, 1.25
    box('btop', (bx, by, .86), (1.9, .8, .08), tw, .008)
    for s in (-1, 1):
        for sy in (-1, 1): box('bleg', (bx + s * .85, by + sy * .33, .41), (.1, .1, .82), tw, .006)
    box('bshelf', (bx, by, .18), (1.8, .7, .03), tw, .004)
    for k in range(5): cyl('can', (bx - .7 + k * .32, by + .1, 1.0), .08, .2, M('can', [(.6, .1, .05), (.1, .3, .5), (.7, .6, .1), (.3, .3, .3), (.1, .4, .2)][k], .4, .6))
    box('mattress', (-.95, 1.6, .75), (.25, .9, 1.5), fabric('mattr', (.82, .8, .74)), .05, rot=(0, R(-12), 0))
    cyl('cord', (.4, .3, 2.0), .005, .4, M('cordm', (.02, .02, .02), .5)); bpy.ops.mesh.primitive_uv_sphere_add(radius=.06, location=(.4, .3, 1.76))
    bpy.context.object.data.materials.append(kit.mat_emit('bulb', (1, .8, .5), 40)); point('bulbl', (.4, .3, 1.74), 60, (1, .7, .4), .05)
    area('fillb', (.5, -3, 1.6), (0, 1, .6), 25, (.55, .65, 1), 3)
    leo('kneel', 'worried', (bx - .1, by - .05, 0), R(-15), 1.05); PTS['leo'] = (bx - .1, by, .45); PTS['window'] = (1.6, 1.9, 1.95)
    PTS['bench'] = (bx, by, .9)
    if name == 'basement': return cam((.9, -2.6, 1.35), (.1, 1.1, .55), 22)
    return cam((.55, -.6, .5), (.32, 1.15, .45), 30, 2.8)

def bath():
    flat_world((.01, .012, .015), 1.0)
    tile = brick_mat(9)
    for nd in tile.node_tree.nodes:
        if nd.type == 'TEX_BRICK':
            nd.inputs['Color1'].default_value = (.55, .62, .62, 1); nd.inputs['Color2'].default_value = (.5, .58, .58, 1); nd.inputs['Mortar'].default_value = (.75, .75, .72, 1); nd.offset = 0
    box('flr', (0, 0, -.01), (2.4, 3, .02), M('flr', (.12, .12, .13), .6), 0); box('cl', (0, 0, 2.41), (2.4, 3, .02), M('clg', (.6, .6, .58), .9), 0)
    box('wb', (0, 1.25, 1.2), (2.4, .1, 2.4), tile, 0); box('wl', (-.95, 0, 1.2), (.1, 3, 2.4), tile, 0); box('wr', (.95, 0, 1.2), (.1, 3, 2.4), tile, 0)
    por = M('porc', (.92, .92, .9), .15, 0, 1.0)
    box('tubbot', (0, .82, .04), (1.8, .76, .08), por, .02); box('tubf', (0, .48, .28), (1.8, .1, .56), por, .04); box('tubb', (0, 1.16, .28), (1.8, .1, .56), por, .04)
    box('tubl', (-.85, .82, .28), (.1, .76, .56), por, .04); box('tubr', (.85, .82, .28), (.1, .76, .56), por, .04)
    cyl('toilet', (.6, -.6, .22), .2, .44, por); box('tank', (.83, -.6, .62), (.2, .45, .4), por, .03)
    box('sink', (-.75, -.7, .82), (.35, .5, .12), por, .03); box('mirror', (-.89, -.7, 1.5), (.02, .5, .6), M('mir', (.8, .85, .9), .02, 1.0), .01)
    box('towel', (.89, .3, 1.2), (.03, .5, .7), fabric('tw', (.8, .4, .2)), .02)
    box('lightfix', (0, 0, 2.38), (.4, .4, .04), kit.mat_emit('fix', (1, .85, .65), 6), .01); area('ceil', (0, 0, 2.3), (0, 0, 0), 60, (1, .78, .55), .5)
    area('fill', (0, -2.5, 1.5), (0, 1, .6), 15, (.55, .65, 1), 2)
    leo('kneel', 'worried', (-.1, .84, .08), R(-10), 1.0); PTS['leo'] = (-.1, .84, .6)
    return cam((.35, -1.4, 1.75), (-.05, .7, .45), 20)

# ------------------------------------------------------------------ sprites
def sprite_light():
    flat_world((.05, .06, .08), .6); area('k', (1.5, -2, 2), (0, 0, 0), 120, (.85, .9, 1), 2); area('f', (-2, -1.5, 1), (0, 0, 0), 60, (.55, .65, .7), 2)
def sprite(kind):
    sc.render.film_transparent = True; sprite_light()
    if kind == 'sp_board':
        box('board', (0, 0, 0), (1.2, .09, .04), wood_mat('bd', (.45, .3, .16), (1, 20, 1)), .004, rot=(0, 0, .15))
        for x in (-.5, .45): cyl('nail', (x, -.01, .03), .005, .08, M('nl', (.5, .5, .5), .3, 1))
        return cam((0, -2.0, .8), (0, 0, 0), 50)
    if kind == 'sp_shingle':
        box('sh', (0, 0, 0), (.9, .3, .01), M('shg', (.12, .1, .09), .9), .002, rot=(R(70), .3, .2)); return cam((0, -2.0, .1), (0, 0, 0), 50)
    if kind == 'sp_metal':
        bpy.ops.mesh.primitive_plane_add(size=1); g = bpy.context.object; g.scale = (.9, .5, 1); bpy.ops.object.transform_apply(scale=True)
        sb = g.modifiers.new('s', 'SUBSURF'); sb.subdivision_type = 'SIMPLE'; sb.levels = 5; sb.render_levels = 5
        tx = bpy.data.textures.new('corr', 'WOOD'); tx.wood_type = 'BANDS'; tx.noise_basis_2 = 'SIN'; d = g.modifiers.new('d', 'DISPLACE'); d.texture = tx; d.strength = .025
        bd = g.modifiers.new('bend', 'SIMPLE_DEFORM'); bd.deform_method = 'BEND'; bd.angle = R(50)
        g.rotation_euler = (R(65), R(15), R(10)); g.data.materials.append(M('tin', (.6, .62, .62), .3, 1.0)); return cam((0, -2.6, .3), (0, 0, 0), 50)
    if kind == 'sp_car':
        car_body((0, 0, 0), 0, lights=False); return cam((0, -12, 2.0), (0, 0, .8), 35)

# ------------------------------------------------------------------ plates
c = None
if SPRITE: c = sprite(name)
elif name in ('plains', 'leocu'): c = plains()
elif name in ('overpass', 'overcu'): c = overpass()
elif name in ('car', 'ditch'): c = car_set()
elif name in ('mobile', 'mobilecu'): c = mobile()
elif name in ('basement', 'basecu'): c = basement()
elif name == 'bath': c = bath()
if PTS:
    bpy.context.view_layer.update()
    with open(f'{OUT}/{name}.txt', 'w') as f:
        for k, p in PTS.items(): f.write(f'{k} {proj(c, p)[0]} {proj(c, p)[1]}\n')
sc.render.filepath = f'{OUT}/{name}.png'; bpy.ops.render.render(write_still=True); print('ok', name)
