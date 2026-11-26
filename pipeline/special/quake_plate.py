"""Pick where to be when an earthquake hits. One Cycles still per plate (quake_anim.py shakes the camera in 2D, drops the
falling objects as sprites and adds dust, debris and graphics).
python3 quake_plate.py <plate> [res_scale] -> quake/plates/<plate>.png (+ .txt with 2D points)
room plates (night living room, warm lamp, teal walls): room (wide, Leo scared), leocu (close on Leo), door (Leo braced in the
  doorway), runin (Leo running for the door), trip (Leo fallen on the floor), couch (Leo curled next to the couch, Triangle of Life),
  table (Leo on hands and knees under the sturdy table), tablecu (close under the table), wall (Leo kneeling at an inside wall)
other sets: bed (Leo in bed, pillow over his head), street (brick facade at night, Leo running out), adobe (old collapsed adobe
  house, only the wooden door frame standing)
sprites (RGBA, transparent): sp_book, sp_book2, sp_lamp, sp_frame, sp_tv, sp_brick, sp_glass"""
import sys, math, os, random
sys.path.insert(0, '/home/claude/b3d')
import bpy, kit
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
name = sys.argv[1]; S = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
OUT = '/home/claude/b3d/quake/plates'; os.makedirs(OUT, exist_ok=True)
SPRITE = name.startswith('sp_')
W, H = (int(700 * S), int(700 * S)) if SPRITE else (int(1080 * S), int(1920 * S))
sc = kit.reset(res=(W, H), samples=int(os.environ.get('SAMPLES', 40)))
sc.cycles.adaptive_threshold = 0.03; sc.cycles.max_bounces = 5; sc.cycles.diffuse_bounces = 3
random.seed(7); PTS = {}

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

# ------------------------------------------------------------------ the living room (night)
BOOKS = []
def books_row(x0, x1, y, z, depth, seed):
    r = random.Random(seed); x = x0; cols = [(.5, .08, .06), (.08, .2, .35), (.75, .6, .2), (.12, .3, .15), (.6, .55, .5), (.3, .12, .3), (.85, .4, .1)]
    while x < x1 - .03:
        w = r.uniform(.025, .05); hh = r.uniform(.2, .3)
        if r.random() < .08: x += .05; continue
        b = box('book', (x + w / 2, y, z + hh / 2), (w, depth * r.uniform(.75, .95), hh), M('bk', r.choice(cols), .6), .003)
        BOOKS.append(b); x += w + .002
def room():
    flat_world((.01, .015, .025), 1.0)
    box('floor', (0, -.5, -.01), (6, 8, .02), plank_mat(), 0)
    box('ceil', (0, -.5, 2.61), (6, 8, .02), M('ceil', (.08, .1, .11), .9), 0)
    wm = wall_mat(); y = 2.0; t = .12
    for nm, x0, x1, z0, z1 in [('wA', -3, -1.9, 0, 2.6), ('wWb', -1.9, -.9, 0, 1.0), ('wWt', -1.9, -.9, 2.0, 2.6), ('wB', -.9, 1.75, 0, 2.6),
                               ('wDt', 1.75, 2.6, 2.05, 2.6), ('wC', 2.6, 3.0, 0, 2.6)]:
        box(nm, ((x0 + x1) / 2, y + t / 2, (z0 + z1) / 2), (x1 - x0, t, z1 - z0), wm, 0)
    box('wL', (-2.95, -.5, 1.3), (.1, 8, 2.6), wm, 0); box('wR', (2.95, -.5, 1.3), (.1, 8, 2.6), wm, 0)
    trim = M('trim', (.75, .72, .66), .5)
    box('base', (0, y - .01, .05), (6, .02, .1), trim, .003)
    # window over the couch: frame, mullions, night outside
    for (cx, cz, sx, sz) in [(-1.4, 1.0, 1.08, .06), (-1.4, 2.0, 1.08, .06), (-1.92, 1.5, .06, 1.06), (-.88, 1.5, .06, 1.06), (-1.4, 1.5, .03, 1.0), (-1.4, 1.5, 1.0, .03)]:
        box('wf', (cx, y - .02, cz), (sx, .08, sz), trim, .005)
    box('sill', (-1.4, y - .08, .98), (1.2, .16, .04), trim, .005)
    o = box('night', (-1.4, y + 1.0, 1.5), (3, .02, 2), night_sky_mat(), 0)
    # doorway to a dim hall, door open into the room
    for (cx, cz, sx, sz) in [(1.72, 1.03, .07, 2.1), (2.63, 1.03, .07, 2.1), (2.175, 2.08, .98, .07)]:
        box('casing', (cx, y - .03, cz), (sx, .06, sz), trim, .006)
    box('hallfloor', (2.175, y + 1.2, -.005), (.9, 2.4, .01), plank_mat(), 0)
    box('hallL', (1.72, y + 1.2, 1.3), (.04, 2.4, 2.6), wall_mat('hw', (.14, .17, .18)), 0); box('hallR', (2.63, y + 1.2, 1.3), (.04, 2.4, 2.6), wall_mat('hw2', (.14, .17, .18)), 0)
    box('hallend', (2.175, y + 2.4, 1.3), (.9, .04, 2.6), wall_mat('hw3', (.16, .18, .19)), 0)
    point('hall', (2.175, y + 1.6, 2.2), 25, (1, .75, .45), .1)
    door = box('door', (2.6 - .42 * math.cos(math.radians(70)), y - .42 * math.sin(math.radians(70)), 1.02), (.84, .04, 2.02), M('doorp', (.68, .66, .6), .45), .008,
               rot=(0, 0, math.radians(70)))
    # couch (ochre), under the window
    cf = fabric('couch', (.42, .26, .08)); cx, cy = -1.45, 1.52
    box('cbase', (cx, cy, .24), (2.0, .86, .3), cf, .05); box('cback', (cx, cy + .34, .62), (2.0, .2, .55), cf, .07)
    for s in (-1, 1): box('carm', (cx + s * .93, cy, .5), (.16, .86, .3), cf, .06)
    for k in (-1, 0, 1): box('cush', (cx + k * .58, cy - .04, .46), (.56, .72, .16), cf, .06)
    for k in (-1, 1): box('pil', (cx + k * .62, cy + .2, .68), (.38, .14, .36), fabric('pil', (.12, .3, .32)), .06)
    for s in (-1, 1):
        for sy in (-1, 1): cyl('cleg', (cx + s * .9, cy + sy * .35, .05), .025, .1, M('leg', (.05, .03, .02), .4))
    # floor lamp beside the couch (warm)
    lx, ly = -.25, 1.6
    if name == 'couchnl': PTS['lamp'] = (lx, ly, 1.6); PTS['lampbase'] = (lx, ly, 0); point('lamp', (lx, ly, 1.55), 70, (1, .62, .3), .08)
    else: floor_lamp(lx, ly)
def floor_lamp(lx, ly):
    cyl('lbase', (lx, ly, .015), .16, .03, M('lmetal', (.08, .07, .06), .3, .8)); cyl('lpole', (lx, ly, .8), .015, 1.55, M('lmetal2', (.1, .09, .07), .3, .8))
    sh = cyl('lshade', (lx, ly, 1.6), .24, .32, M('shade', (.9, .75, .5), .6), r2=.16, verts=64)
    sh.data.materials[0].node_tree.nodes['Principled BSDF'].inputs['Transmission Weight'].default_value = .4
    sh.modifiers.new('s', 'SOLIDIFY').thickness = .005
    point('lamp', (lx, ly, 1.55), 70, (1, .62, .3), .08); PTS['lamp'] = (lx, ly, 1.6); PTS['lampbase'] = (lx, ly, 0)
def room2():
    y = 2.0
    # bookcase with books + TV on the middle shelf
    wd = wood_mat('case', (.3, .17, .08)); bx0, bx1, by = .45, 1.45, 1.8; bz = 1.95; d = .34
    box('cside1', (bx0, by, bz / 2), (.04, d, bz), wd, .004); box('cside2', (bx1, by, bz / 2), (.04, d, bz), wd, .004)
    box('cback', (( bx0 + bx1) / 2, by + d / 2 - .01, bz / 2), (bx1 - bx0, .02, bz), wd, 0)
    shelves = [.04, .45, .9, 1.3, 1.92]
    for k, zz in enumerate(shelves): box('shelf', ((bx0 + bx1) / 2, by, zz), (bx1 - bx0, d, .035), wd, .003)
    books_row(bx0 + .03, bx1 - .03, by - .02, .06, d * .8, 1); books_row(bx0 + .03, bx1 - .03, by - .02, .92, d * .8, 2); books_row(bx0 + .03, bx1 - .03, by - .02, 1.32, d * .8, 3)
    tv = box('tv', ((bx0 + bx1) / 2, by - .02, .47 + .23), (.78, .05, .45), M('tvb', (.015, .015, .02), .3), .01)
    box('scr', ((bx0 + bx1) / 2, by - .046, .47 + .23), (.74, .004, .41), kit.mat_emit('screen', (.06, .14, .26), .5), 0)
    box('tvfoot', ((bx0 + bx1) / 2, by - .02, .48), (.25, .15, .02), M('tvf', (.02, .02, .02), .3), 0)
    PTS['shelf_top'] = ((bx0 + bx1) / 2, by - .1, 1.45); PTS['shelf_mid'] = ((bx0 + bx1) / 2, by - .1, 1.05); PTS['tv'] = ((bx0 + bx1) / 2, by - .05, .7)
    # picture frames on the wall
    for (fx, fz, fw, fh, c) in [(-.35, 1.55, .38, .5, (.55, .35, .2)), (.05, 1.75, .3, .3, (.2, .35, .5))]:
        box('frame', (fx, y - .02, fz), (fw, .03, fh), M('fr', (.05, .04, .03), .4), .005)
        box('pic', (fx, y - .036, fz), (fw - .06, .004, fh - .06), M('pic', c, .6), 0)
    PTS['frame'] = (-.35, y - .03, 1.55)
    # the sturdy table (solid wood, thick legs) on a rug
    tw = wood_mat('table', (.38, .21, .1)); tx, ty = .15, .15
    box('rug', (tx, ty, .004), (2.4, 1.7, .008), fabric('rug', (.35, .1, .08)), .01)
    box('ttop', (tx, ty, .78), (1.5, .86, .06), tw, .01)
    for s in (-1, 1):
        box('apron', (tx, ty + s * .38, .71), (1.36, .04, .1), tw, .004); box('apron2', (tx + s * .7, ty, .71), (.04, .76, .1), tw, .004)
        for sy in (-1, 1): box('tleg', (tx + s * .68, ty + sy * .36, .37), (.09, .09, .74), tw, .006)
    PTS['tabletop'] = (tx, ty, .81)
    # light: lamp + hall + cool moonlight through the window + soft cool fill
    area('moon', (-1.4, 3.2, 2.4), (-.8, 0, .5), 140, (.45, .6, 1), 1.0)
    area('fill', (.8, -3.5, 2.0), (0, 1, .9), 60, (.55, .65, 1), 4)
    area('warm', (-1.5, -2.0, 2.4), (0, .5, .5), 25, (1, .7, .45), 3)
def haze(density, loc=(0, 0, 1.3), scale=(3, 3, 1.3)):
    bpy.ops.mesh.primitive_cube_add(location=loc); v = bpy.context.object; v.scale = scale
    m = bpy.data.materials.new('haze'); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); vs = N.new('ShaderNodeVolumeScatter')
    vs.inputs['Density'].default_value = density; vs.inputs['Anisotropy'].default_value = .4; L.new(vs.outputs[0], o.inputs['Volume']); v.data.materials.append(m)

# ------------------------------------------------------------------ other sets
def bedroom():
    flat_world((.01, .015, .025), 1.0)
    box('floor', (0, 0, -.01), (5, 5, .02), plank_mat(), 0); wm = wall_mat('bw', (.1, .17, .22))
    box('bwall', (0, 1.4, 1.3), (5, .1, 2.6), wm, 0)
    wd = wood_mat('bedw', (.3, .17, .08))
    box('head', (0, 1.3, .55), (1.1, .08, 1.1), wd, .02)
    box('frame', (0, .3, .2), (1.05, 2.05, .25), wd, .02)
    box('mattress', (0, .3, .42), (1.0, 2.0, .2), fabric('mat', (.85, .85, .82)), .05)
    box('blanket', (0, .05, .55), (1.06, 1.5, .08), fabric('blank', (.12, .28, .42)), .05)
    box('nst', (.85, 1.1, .3), (.45, .4, .6), wd, .01); cyl('nlamp', (.85, 1.1, .72), .1, .2, M('nl', (.9, .75, .5), .6), r2=.07)
    point('nl', (.85, 1.1, .7), 18, (1, .62, .3), .05)
    root, parts = leo('bed', 'scared', loc=(0, .95, .5), yaw=0, h=1.05)
    pil = box('pillow', (0, 1.08, .78), (.6, .42, .14), fabric('pw', (.92, .92, .9)), .06); pil.rotation_euler = (math.radians(-8), 0, 0)
    area('moon', (-1.5, -1, 2.5), (0, .6, .5), 60, (.45, .6, 1), 2); area('fill', (1.2, -2.5, 2), (0, .5, .5), 30, (.6, .7, 1), 3)
    PTS['pillow'] = (0, 1.0, .8); PTS['lamp'] = (.85, 1.1, .82)
    return cam((.9, -1.5, 1.9), (0, .65, .55), 30, 5.0)

def brick_mat(scale=2.4):
    m = bpy.data.materials.new('brick'); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled')
    tc = N.new('ShaderNodeTexCoord'); br = N.new('ShaderNodeTexBrick'); br.inputs['Scale'].default_value = scale
    mpb = N.new('ShaderNodeMapping'); mpb.inputs['Rotation'].default_value = (math.pi / 2, 0, 0); L.new(tc.outputs['Object'], mpb.inputs[0])
    br.inputs['Color1'].default_value = (.32, .1, .05, 1); br.inputs['Color2'].default_value = (.22, .07, .04, 1); br.inputs['Mortar'].default_value = (.35, .33, .3, 1)
    br.inputs['Mortar Size'].default_value = .015; L.new(mpb.outputs[0], br.inputs['Vector'])
    L.new(br.outputs['Color'], bs.inputs['Base Color']); bs.inputs['Roughness'].default_value = .9
    bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = .4; L.new(br.outputs['Fac'], bp.inputs['Height']); L.new(bp.outputs[0], bs.inputs['Normal'])
    L.new(bs.outputs[0], o.inputs[0]); return m
def street():
    flat_world((.015, .025, .045), 1.0)
    box('road', (0, -4, -.02), (30, 12, .04), M('asph', (.03, .03, .035), .35), 0)
    box('walk', (0, -.9, .06), (30, 2.4, .12), M('conc', (.22, .22, .21), .85), .01)
    bm = brick_mat(); fy = .3
    box('facade', (0, fy + .2, 3.2), (12, .4, 6.4), bm, 0)
    glass = M('winglass', (.02, .03, .04), .05, .3); lit = kit.mat_emit('winlit', (1, .62, .32), .9); trim = M('wtrim', (.8, .78, .72), .5)
    for row, zc in enumerate((1.5, 4.4)):
        for k, xc in enumerate((-4.4, -2.4, 2.4, 4.4)):
            box('win', (xc, fy - .005, zc), (1.0, .02, 1.5), lit if (k + row) % 3 else glass, 0)
            box('sill', (xc, fy - .06, zc - .8), (1.2, .12, .08), trim, .005); box('lint', (xc, fy - .03, zc + .82), (1.2, .06, .14), trim, .005)
            for dx in (-.25, .25): box('mul', (xc + dx, fy - .03, zc), (.03, .02, 1.5), trim, 0)
    box('cornice', (0, fy - .1, 6.3), (12.2, .3, .25), trim, .02)
    # open front door with warm light inside, steps
    box('doorlight', (0, fy + .35, 1.15), (1.1, .02, 2.3), kit.mat_emit('inside', (1, .72, .42), 3.0), 0)
    for (cx, cz, sx, sz) in [(-.6, 1.2, .12, 2.4), (.6, 1.2, .12, 2.4), (0, 2.45, 1.3, .14)]: box('dcase', (cx, fy - .04, cz), (sx, .1, sz), trim, .006)
    for k in range(3): box('step', (0, fy - .25 - k * .3, .3 - k * .1 + .02), (1.6, .3, .1 + (2 - k) * 0), M('stp', (.3, .3, .29), .8), .01)
    box('lead_step', (0, -.15, .2), (1.6, .9, .2), M('stp2', (.3, .3, .29), .8), .01)
    # street lamp
    cyl('pole', (2.0, -1.8, 2.0), .06, 4.0, M('pole', (.05, .06, .07), .4, .7)); cyl('lamphead', (2.0, -1.8, 4.05), .2, .3, M('lh', (.05, .06, .07), .4, .7), r2=.1)
    point('streetlamp', (2.0, -1.8, 3.85), 400, (1, .7, .4), .15)
    area('moon', (-6, -8, 8), (0, 0, 2), 300, (.45, .6, 1), 6); area('door', (0, -.3, 1.6), (0, -3, 1), 60, (1, .7, .4), 1.2)
    root, parts = leo('run', 'scared', loc=(-.15, -.9, .12), yaw=math.radians(-10), h=1.25)
    PTS['facade_top'] = (0, fy - .1, 6.2); PTS['win1'] = (-2.4, fy, 4.4); PTS['win2'] = (2.4, fy, 4.4); PTS['leo'] = (-.15, -.9, 1.2); PTS['walk'] = (0, -1.2, .12)
    return cam((.4, -4.9, 1.3), (0, 0, 2.4), 24)

def mud_mat():
    m = kit.mat_pbr('sand', 'mud'); b = m.node_tree.nodes.get('Principled BSDF')
    if b: b.inputs['Base Color'].default_value = (.42, .28, .17, 1)
    return m
def adobe():
    kit.sky(sun_elevation=28, sun_rotation=150, strength=.06, sun_lamp_energy=2.2)
    ter = kit.terrain(size=120, height=.4, scale=2, kind='desert', seed=3, res=7)
    mud = M('adobe', (.45, .3, .18), .95); r = random.Random(4)
    dm_tex = bpy.data.textures.new('mudn', 'CLOUDS'); dm_tex.noise_scale = .25
    def rough(o, s=.06):
        d = o.modifiers.new('d', 'DISPLACE'); d.texture = dm_tex; d.strength = s; sb = o.modifiers.new('s', 'SUBSURF'); sb.levels = 2; sb.render_levels = 2; o.modifiers.move(1, 0)
    # broken wall stubs (thick mud-brick walls, jagged tops)
    for (x, y, w, d, h) in [(-2.4, 1.2, .5, 3.0, .9), (2.6, .6, .5, 2.2, .6), (-1.2, 2.6, 2.0, .5, .7), (1.6, 2.7, 1.6, .5, .45)]:
        o = box('stub', (x, y, h / 2), (w, d, h), mud, 0); rough(o)
    # rubble: mounds and scattered mud bricks
    for k in range(5):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=(r.uniform(-2.5, 2.5), r.uniform(0, 3), -.2)); mo = bpy.context.object
        mo.scale = (r.uniform(.8, 1.5), r.uniform(.7, 1.2), r.uniform(.4, .7)); mo.data.materials.append(mud); rough(mo, .2)
    for k in range(140):
        x, y = r.uniform(-3.5, 3.5), r.uniform(-1.5, 3.5)
        if abs(x) < .6 and abs(y - .9) < .35: continue
        o = box('mb', (x, y, r.uniform(.05, .5)), (.36, .2, .1), mud, .01, rot=(r.uniform(-.6, .6), r.uniform(-.6, .6), r.uniform(0, 3)))
    # the door frame still standing (wood posts + lintel)
    wd = wood_mat('oldwood', (.25, .16, .09), (1, 1, 14))
    for sx in (-.52, .52): box('post', (sx, .9, 1.05), (.14, .2, 2.1), wd, .01)
    box('lintel', (0, .9, 2.16), (1.36, .24, .16), wd, .01)
    box('threshold', (0, .9, .04), (1.2, .22, .08), wd, .01)
    PTS['frame'] = (0, .9, 1.2); PTS['lintel'] = (0, .9, 2.16)
    return cam((.8, -4.6, 1.3), (0, 1.2, 1.0), 30)

# ------------------------------------------------------------------ sprites (RGBA, transparent background)
def sprite_light():
    flat_world((.05, .06, .08), .6); area('k', (1.5, -2, 2), (0, 0, 0), 120, (1, .78, .55), 2); area('f', (-2, -1.5, 1), (0, 0, 0), 60, (.55, .65, 1), 2)
def sprite(kind):
    sc.render.film_transparent = True; sprite_light(); r = random.Random(3)
    if kind == 'sp_book':
        box('cover', (0, 0, 0), (.3, .045, .22), M('bc', (.5, .08, .06), .5), .004); box('pages', (.004, 0, 0), (.29, .035, .205), M('pg', (.9, .87, .78), .8), .002)
        return cam((.2, -.9, .3), (0, 0, 0), 50)
    if kind == 'sp_book2':
        box('cover', (0, 0, 0), (.24, .06, .3), M('bc2', (.08, .22, .4), .5), .004); box('pages', (.004, 0, 0), (.23, .05, .29), M('pg2', (.9, .87, .78), .8), .002)
        return cam((.3, -.9, .25), (0, 0, 0), 50)
    if kind == 'sp_lamp':   # the floor lamp (same as in the room), for the fall
        cyl('lbase', (0, 0, .015), .16, .03, M('lm', (.08, .07, .06), .3, .8)); cyl('lpole', (0, 0, .8), .015, 1.55, M('lm2', (.1, .09, .07), .3, .8))
        cyl('lshade', (0, 0, 1.6), .24, .32, kit.mat_emit('lsh', (1, .7, .4), 1.5), r2=.16, verts=64)
        return cam((0, -6, .9), (0, 0, .9), 50)
    if kind == 'sp_frame':
        box('frame', (0, 0, 0), (.38, .03, .5), M('fr', (.05, .04, .03), .4), .005); box('pic', (0, -.016, 0), (.32, .004, .44), M('pic', (.55, .35, .2), .6), 0)
        return cam((.1, -1.2, .05), (0, 0, 0), 50)
    if kind == 'sp_tv':
        box('tv', (0, 0, 0), (.78, .05, .45), M('tvb', (.015, .015, .02), .3), .01); box('scr', (0, -.026, 0), (.74, .004, .41), kit.mat_emit('screen', (.15, .3, .5), 1.2), 0)
        return cam((.3, -2.0, .2), (0, 0, 0), 50)
    if kind == 'sp_brick':
        o = box('brick', (0, 0, 0), (.22, .1, .07), M('brk', (.33, .1, .05), .9), .008, rot=(.3, .4, .2)); return cam((0, -1.0, .1), (0, 0, 0), 50)
    if kind == 'sp_glass':
        bpy.ops.mesh.primitive_plane_add(size=.3); g = bpy.context.object; g.rotation_euler = (1.2, .3, .5)
        me = g.data; me.vertices[0].co.x -= .08; me.vertices[3].co.y += .06
        m = M('shard', (.75, .9, 1), .02, 0); b = m.node_tree.nodes['Principled BSDF']; b.inputs['Transmission Weight'].default_value = .55; b.inputs['Coat Weight'].default_value = 1; b.inputs['IOR'].default_value = 1.5
        g.data.materials.append(m); return cam((0, -1.0, .1), (0, 0, 0), 50)

# ------------------------------------------------------------------ plates
c = None
if SPRITE: c = sprite(name)
elif name == 'bed': c = bedroom()
elif name == 'street': c = street()
elif name == 'adobe': c = adobe()
else:
    room(); room2(); haze(.012, (0, -.2, 1.3), (3, 2.5, 1.3)); R = math.radians
    if name == 'room':
        leo('panic', 'scared', (-.55, -.75, 0), R(10), 1.4); PTS['leo'] = (-.55, -.75, 1.25); PTS['head'] = (-.55, -.75, 1.12)
        c = cam((.05, -3.3, 1.25), (.15, 1.0, 1.0), 24)
    elif name == 'leocu':
        leo('panic', 'scared', (-.55, -.75, 0), R(10), 1.4); PTS['leo'] = (-.55, -.75, 1.12)
        c = cam((-.25, -2.25, 1.2), (-.55, -.75, 1.12), 45, 2.2)
    elif name == 'door':
        leo('brace', 'worried', (2.175, 1.98, 0), 0, 1.45); PTS['leo'] = (2.175, 1.98, 1.2); PTS['head'] = (2.175, 1.98, 1.16)
        c = cam((1.0, -1.1, 1.25), (1.75, 1.7, 1.0), 26)
    elif name == 'runin':
        leo('run', 'scared', (1.6, -.3, 0), R(165), 1.4); PTS['leo'] = (1.6, -.3, 1.0)
        c = cam((1.2, -2.9, 1.25), (1.95, 1.6, 1.0), 26)
    elif name == 'trip':
        leo('fallen', 'scared', (1.75, -.2, 0), R(150), 1.4); PTS['leo'] = (1.75, -.2, .3)
        c = cam((.75, -2.1, .85), (1.9, .7, .35), 26)
    elif name == 'couch':
        leo('curl', 'scared', (-1.45, .82, 0), R(0), 1.3); PTS['leo'] = (-1.45, .82, .25); PTS['void'] = (-1.45, .9, .2)
        c = cam((-1.35, -1.25, .85), (-1.55, 1.0, .42), 26)
    elif name == 'couchnl':
        leo('curl', 'scared', (-1.45, .82, 0), R(0), 1.3); PTS['leo'] = (-1.45, .82, .25)
        c = cam((-1.15, -1.45, .9), (-.95, 1.0, .55), 24)
    elif name == 'table':
        leo('crawl', 'worried', (.25, .42, 0), R(-10), 1.05); PTS['leo'] = (.25, .2, .4)
        c = cam((.65, -2.3, .75), (.15, .2, .55), 26)
    elif name == 'tablecu':
        leo('crawl', 'worried', (.25, .42, 0), R(-10), 1.05); PTS['leo'] = (.25, .2, .4)
        c = cam((.5, -1.45, .55), (.2, .25, .42), 30, 3.0)
    elif name == 'wall':
        leo('kneel', 'worried', (2.5, .3, 0), R(-70), 1.35); PTS['leo'] = (2.5, .3, .6)
        area('wallk', (1.2, -.8, 1.8), (2.5, .3, .5), 18, (1, .75, .5), 1.5)
        c = cam((.9, -1.95, 1.1), (2.4, .5, .6), 26)
if PTS:
    bpy.context.view_layer.update()
    with open(f'{OUT}/{name}.txt', 'w') as f:
        for k, p in PTS.items(): f.write(f'{k} {proj(c, p)[0]} {proj(c, p)[1]}\n')
sc.render.filepath = f'{OUT}/{name}.png'; bpy.ops.render.render(write_still=True); print('ok', name)
