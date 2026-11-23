"""Story Short: The Sun went out at 8:12 AM (Part 1). One Cycles still per plate (animated in 2D by sunout_anim.py).
python3 sunout_plate.py <plate> [res_scale]  -> sunout/plates/<plate>.png
Kitchen plates: wide_day, wide_dark, cu_kai_day, cu_leo_day, cu_kai_dark, cu_leo_dark, cu_mia_dark, cu_mia_explain, ots_day, ots_dark,
  clock, bowl, window_day, window_moon, window_dark, plant_dark, trio_dark
Space plates: sun_earth (Sun + day-lit Earth), earth_dark (no Sun: only city lights), earth_us, earth_iceland, pole (South Pole winter night)"""
import sys, math, os
sys.path.insert(0, '/home/claude/b3d')
import bpy, kit
kit.CAST['kai']['hair_c'] = (.2, .065, .015)
from mathutils import Vector
name = sys.argv[1]; S = float(sys.argv[2]) if len(sys.argv) > 2 else 0.75
OUT = '/home/claude/b3d/sunout/plates'; os.makedirs(OUT, exist_ok=True)
W, H = int(1080 * S), int(1920 * S)
sc = kit.reset(res=(W, H), samples=int(os.environ.get('SAMPLES', 48)))
sc.cycles.adaptive_threshold = 0.03; sc.cycles.max_bounces = 5; sc.cycles.diffuse_bounces = 3
DAY = name.endswith('_day') or name in ('bowl', 'window_day', 'sun_earth', 'clock', 'clock_820')

def track(o, target):
    c = o.constraints.new('TRACK_TO'); c.target = target; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'

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

def M(nm, col, rough=.5, metal=0.0, coat=0.0):
    return kit.mat_principled(nm, col, rough=rough, metal=metal, coat=coat)

def box(nm, loc, size, mat, bevel=.01, rot=(0, 0, 0), sub=1):
    bpy.ops.mesh.primitive_cube_add(location=loc); o = bpy.context.object; o.name = nm; o.scale = (size[0] / 2, size[1] / 2, size[2] / 2)
    o.rotation_euler = rot; bpy.ops.object.transform_apply(scale=True); o.data.materials.append(mat)
    if bevel: b = o.modifiers.new('b', 'BEVEL'); b.width = bevel; b.segments = 3
    return o

def cyl(nm, loc, r, depth, mat, rot=(0, 0, 0), verts=48):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=depth, location=loc, rotation=rot, vertices=verts); o = bpy.context.object; o.name = nm
    o.data.materials.append(mat); bpy.ops.object.shade_smooth(); return o

def wood_mat(nm='wood', col=(.32, .18, .09), scale=(1, 18, 1)):
    m = bpy.data.materials.new(nm); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled')
    tc = N.new('ShaderNodeTexCoord'); mp = N.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = scale
    nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 6; nz.inputs['Detail'].default_value = 8; nz.inputs['Distortion'].default_value = 3
    L.new(tc.outputs['Object'], mp.inputs[0]); L.new(mp.outputs[0], nz.inputs[0])
    cr = N.new('ShaderNodeValToRGB'); cr.color_ramp.elements[0].color = (col[0] * .6, col[1] * .6, col[2] * .6, 1); cr.color_ramp.elements[1].color = (*col, 1)
    L.new(nz.outputs['Fac'], cr.inputs[0]); L.new(cr.outputs[0], bs.inputs['Base Color']); bs.inputs['Roughness'].default_value = .45
    bs.inputs['Coat Weight'].default_value = .2; L.new(bs.outputs[0], o.inputs[0]); return m

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
    L.new(mx.outputs[0], bs.inputs['Base Color']); bs.inputs['Roughness'].default_value = .55
    L.new(bs.outputs[0], o.inputs[0]); return m

def panel_wall_mat(nm='wall', col=(.11, .2, .24)):
    """painted wall with soft vertical panel seams and a little grime (dark teal, moody)"""
    m = bpy.data.materials.new(nm); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled')
    tc = N.new('ShaderNodeTexCoord'); sep = N.new('ShaderNodeSeparateXYZ'); L.new(tc.outputs['Object'], sep.inputs[0])
    fr = N.new('ShaderNodeMath'); fr.operation = 'FRACT'; mul = N.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; mul.inputs[1].default_value = 1 / .6
    L.new(sep.outputs['X'], mul.inputs[0]); L.new(mul.outputs[0], fr.inputs[0])
    seam = N.new('ShaderNodeMath'); seam.operation = 'LESS_THAN'; seam.inputs[1].default_value = .012; L.new(fr.outputs[0], seam.inputs[0])
    nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 3; nz.inputs['Detail'].default_value = 10; L.new(tc.outputs['Object'], nz.inputs[0])
    cr = N.new('ShaderNodeValToRGB'); cr.color_ramp.elements[0].color = (col[0] * .75, col[1] * .75, col[2] * .75, 1); cr.color_ramp.elements[1].color = (*col, 1)
    L.new(nz.outputs['Fac'], cr.inputs[0])
    mx = N.new('ShaderNodeMixRGB'); L.new(seam.outputs[0], mx.inputs['Fac']); L.new(cr.outputs[0], mx.inputs[1]); mx.inputs[2].default_value = (col[0] * .35, col[1] * .35, col[2] * .35, 1)
    L.new(mx.outputs[0], bs.inputs['Base Color']); bs.inputs['Roughness'].default_value = .8
    bump = N.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = .25; L.new(seam.outputs[0], bump.inputs['Height']); L.new(bump.outputs[0], bs.inputs['Normal'])
    L.new(bs.outputs[0], o.inputs[0]); return m

def sky_mat(dark=False, moon=False):
    """what's outside the window: a bright morning sky (day) or black with stars (Sun gone)"""
    m = bpy.data.materials.new('outside'); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); e = N.new('ShaderNodeEmission')
    tc = N.new('ShaderNodeTexCoord'); sep = N.new('ShaderNodeSeparateXYZ'); L.new(tc.outputs['Generated'], sep.inputs[0])
    cr = N.new('ShaderNodeValToRGB')
    if not dark:
        cr.color_ramp.elements[0].color = (1.0, .62, .32, 1); cr.color_ramp.elements[1].color = (.35, .6, 1.0, 1)
        e1 = cr.color_ramp.elements.new(.45); e1.color = (.95, .8, .62, 1)
        L.new(sep.outputs['Z'], cr.inputs[0]); L.new(cr.outputs[0], e.inputs['Color']); e.inputs['Strength'].default_value = 1.5
    else:
        vor = N.new('ShaderNodeTexVoronoi'); vor.inputs['Scale'].default_value = 160; L.new(tc.outputs['Object'], vor.inputs[0])
        st = N.new('ShaderNodeMapRange'); st.inputs['From Min'].default_value = 0; st.inputs['From Max'].default_value = .06
        st.inputs['To Min'].default_value = 9; st.inputs['To Max'].default_value = 0; st.clamp = True; L.new(vor.outputs['Distance'], st.inputs[0])
        gate = N.new('ShaderNodeMath'); gate.operation = 'GREATER_THAN'; gate.inputs[1].default_value = .8; L.new(vor.outputs['Color'], gate.inputs[0])
        mm = N.new('ShaderNodeMath'); mm.operation = 'MULTIPLY'; L.new(st.outputs[0], mm.inputs[0]); L.new(gate.outputs[0], mm.inputs[1])
        base = N.new('ShaderNodeValToRGB'); base.color_ramp.elements[0].color = (.0, .0, .003, 1); base.color_ramp.elements[1].color = (.004, .008, .02, 1)
        L.new(sep.outputs['Z'], base.inputs[0])
        add = N.new('ShaderNodeMixRGB'); add.blend_type = 'ADD'; add.inputs['Fac'].default_value = 1; L.new(base.outputs[0], add.inputs[1])
        cc = N.new('ShaderNodeCombineColor'); [L.new(mm.outputs[0], cc.inputs[i]) for i in range(3)]; L.new(cc.outputs[0], add.inputs[2])
        L.new(add.outputs[0], e.inputs['Color']); e.inputs['Strength'].default_value = 1.0
    L.new(e.outputs[0], o.inputs[0]); return m

# ================================================================== the kitchen set
def kitchen(dark):
    flat_world((.01, .015, .025) if dark else (.2, .19, .17), 1.0)
    floor = box('floor', (0, 0, -.01), (8, 8, .02), plank_mat(), bevel=0)
    box('ceiling', (0, 0, 2.6), (8, 8, .02), M('ceil', (.06, .08, .09), .9), 0)
    wall_m = panel_wall_mat()
    # back wall with a window hole (built from 4 pieces) at x in [-.55, .55], z in [.75, 1.85]
    wy = 1.6
    box('wall_l', (-2.3, wy, 1.5), (3.5, .1, 3.0), wall_m, 0); box('wall_r', (2.3, wy, 1.5), (3.5, .1, 3.0), wall_m, 0)
    box('wall_b', (0, wy, .375), (1.1, .1, .75), wall_m, 0); box('wall_t', (0, wy, 2.425), (1.1, .1, 1.15), wall_m, 0)
    box('wall_side', (-2.6, 0, 1.5), (.1, 6, 3.0), wall_m, 0)
    # wainscot strip + skirting
    trim = M('trim', (.06, .08, .09), .6)
    box('chair_rail', (0, wy - .06, .72), (8, .03, .04), trim, .005)
    # window frame (warm white paint) with mullions, sill, glass
    fr = M('frame', (.78, .74, .66), .5)
    for nm_, loc, sz in [('fl', (-.57, wy - .02, 1.3), (.05, .16, 1.16)), ('fr', (.57, wy - .02, 1.3), (.05, .16, 1.16)),
                         ('ft', (0, wy - .02, 1.87), (1.19, .16, .05)), ('fb', (0, wy - .02, .73), (1.19, .16, .05)),
                         ('mv', (0, wy - .02, 1.3), (.03, .1, 1.1)), ('mh', (0, wy - .02, 1.3), (1.1, .1, .03))]:
        box(nm_, loc, sz, fr, .006)
    box('sill', (0, wy - .14, .7), (1.35, .26, .04), fr, .01)
    gl = bpy.data.materials.new('glass'); nt, N, L = kit.nodes(gl); o = N.new('ShaderNodeOutputMaterial'); gb = N.new('ShaderNodeBsdfGlass')
    gb.inputs['IOR'].default_value = 1.5; gb.inputs['Roughness'].default_value = .02; tr = N.new('ShaderNodeBsdfTransparent'); mx = N.new('ShaderNodeMixShader')
    mx.inputs['Fac'].default_value = .12 if DAY else 0.0; L.new(tr.outputs[0], mx.inputs[1]); L.new(gb.outputs[0], mx.inputs[2]); L.new(mx.outputs[0], o.inputs[0])
    pane = box('pane', (0, wy, 1.3), (1.1, .005, 1.1), gl, 0)
    # outside: big emissive sky card far behind the window
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, wy + 3.0, 1.3), rotation=(math.pi / 2, 0, 0)); outside = bpy.context.object
    outside.scale = (9, 6, 1); outside.data.materials.append(sky_mat(dark)); outside.visible_shadow = False
    # a city skyline silhouette in the window (tall dark blocks with a few lit windows at night)
    sky_m = M('bldg', (.05, .06, .08) if not dark else (.01, .012, .016), .8)
    lit = kit.mat_emit('litwin', (1.0, .7, .35), 3.0)
    import random; rnd = random.Random(4)
    for k in range(9):
        x = -1.6 + k * .4 + rnd.uniform(-.08, .08); hgt = rnd.uniform(.4, 1.1)
        b = box(f'b{k}', (x, wy + 2.4, .65 + hgt / 2), (.34, .3, hgt), sky_m, 0); b.visible_shadow = False
        if dark:
            for j in range(6):
                if rnd.random() < .45:
                    box(f'w{k}{j}', (x + rnd.uniform(-.12, .12), wy + 2.24, .75 + rnd.uniform(0, hgt - .1)), (.04, .01, .05), lit, 0)
    # fridge (left) + open shelf with jars (left of the window) + a framed picture
    fw = M('fridge', (.72, .74, .72), .3, coat=.4)
    box('fridge', (-1.75, wy - .42, .85), (.7, .65, 1.7), fw, .04)
    box('fridge_gap', (-1.75, wy - .75, 1.2), (.68, .01, .01), M('gap', (.05, .05, .05), .5), 0)
    for z in (1.0, 1.45): box('handle', (-1.48, wy - .77, z), (.03, .03, .3), M('steel2', (.8, .8, .82), .2, 1), .01)
    sh = M('shelf', (.35, .2, .1), .5)
    for z in (1.15, 1.5): box('shelf', (-.95, wy - .12, z), (.55, .2, .025), sh, .005)
    jar = M('jar', (.9, .55, .2), .2, coat=.5)
    for k, (x, z, h) in enumerate([(-1.12, 1.17, .14), (-.98, 1.17, .1), (-.84, 1.17, .16), (-1.08, 1.52, .12), (-.9, 1.52, .09)]):
        cyl('jar', (x, wy - .12, z + h / 2), .04, h, [jar, mug_m if False else M('jar2', (.2, .45, .5), .2, coat=.5), M('jar3', (.75, .2, .15), .3)][k % 3])
    box('frame_pic', (1.15, wy - .06, 1.12), (.42, .02, .3), M('picframe', (.05, .05, .05), .4), .005)
    box('pic', (1.15, wy - .072, 1.12), (.36, .005, .24), kit.mat_emit('picart', (.9, .45, .2), .25 if dark else .6), 0)
    # table (warm wood) + bowls + mugs
    tw = wood_mat('tablewood', (.45, .26, .12), (1, 10, 1))
    box('table', (0, .25, .44), (1.7, .8, .05), tw, .012)
    for x, y in ((-.78, -.08), (.78, -.08), (-.78, .58), (.78, .58)): box('leg', (x, y, .21), (.05, .05, .42), tw, .006)
    mug_m = M('mug', (.15, .35, .55), .3, coat=.5)
    cer = M('cereal', (.85, .55, .18), .7); milk = M('milk', (.95, .94, .9), .25); bowl_m = M('bowl', (.85, .3, .15), .3, coat=.6)
    for x in (-.45, 0, .45):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=.1, location=(x, .05, .56), segments=48, ring_count=24); bw = bpy.context.object
        bw.scale = (1, 1, .6); bpy.ops.object.transform_apply(scale=True)
        bpy.ops.object.mode_set(mode='EDIT'); import bmesh; bm = bmesh.from_edit_mesh(bw.data)
        for v in [v for v in bm.verts if v.co.z > -0.0]: bm.verts.remove(v)
        bmesh.update_edit_mesh(bw.data); bpy.ops.object.mode_set(mode='OBJECT'); bw.location.z = .525 + .06
        so = bw.modifiers.new('s', 'SOLIDIFY'); so.thickness = .008; bw.data.materials.append(bowl_m); bpy.ops.object.shade_smooth()
        cyl('milk', (x, .05, .57), .092, .005, milk)
        for k in range(16):
            a = k * 2.4; r = .075 * math.sqrt(k / 16)
            bpy.ops.mesh.primitive_torus_add(major_radius=.012, minor_radius=.006, location=(x + r * math.cos(a), .05 + r * math.sin(a), .576))
            c = bpy.context.object; c.rotation_euler = (rnd.uniform(-.5, .5), rnd.uniform(-.5, .5), 0); c.data.materials.append(cer)
        sp = box('spoon', (x + .12, -.04, .475), (.02, .16, .006), M('steel', (.8, .8, .82), .2, 1), .002, rot=(0, 0, .5))
    for x in (-.7, .7):
        cyl('mug', (x, .3, .52), .045, .1, mug_m); cyl('coffee', (x, .3, .565), .04, .005, M('coffee', (.08, .04, .02), .1))
    # wall clock (cream face, black rim) on the back wall, right of the window; hands set by HANDS (hh, mm)
    cx, cz = 1.15, 1.75
    cyl('clock_rim', (cx, wy - .07, cz), .2, .04, M('rim', (.03, .03, .035), .35), rot=(math.pi / 2, 0, 0))
    cyl('clock_face', (cx, wy - .092, cz), .18, .005, M('face', (.93, .9, .82), .6), rot=(math.pi / 2, 0, 0))
    ink = M('ink', (.02, .02, .02), .5)
    for k in range(12):
        a = k / 12 * 2 * math.pi; ln = .035 if k % 3 == 0 else .018
        box('tick', (cx + .15 * math.sin(a), wy - .096, cz + .15 * math.cos(a)), (.008, .002, ln), ink, 0, rot=(0, a, 0))
    return wy, (cx, cz)

def clock_hands(c, hh, mm, ss=None):
    cx, cz = c; wy = 1.6; ink = bpy.data.materials['ink']
    for nm_, ang, ln, w in (('hour', (hh % 12 + mm / 60) / 12, .095, .016), ('min', mm / 60, .145, .01)):
        a = ang * 2 * math.pi
        box(nm_, (cx + ln / 2 * math.sin(a), wy - .1 - (.002 if nm_ == 'min' else 0), cz + ln / 2 * math.cos(a)), (w, .002, ln), ink, 0, rot=(0, a, 0))
    if ss is not None:
        a = ss / 60 * 2 * math.pi
        box('sec', (cx + .07 * math.sin(a), wy - .105, cz + .07 * math.cos(a)), (.004, .002, .17), M('red', (.8, .05, .05), .4), 0, rot=(0, a, 0))
    cyl('pin', (cx, wy - .107, cz), .012, .006, ink, rot=(math.pi / 2, 0, 0))

def lamp(dark):
    """warm pendant lamp over the table (on when it's dark)"""
    cyl('cord', (0, .25, 2.4), .006, .9, M('cord', (.02, .02, .02), .5))
    bpy.ops.mesh.primitive_cone_add(radius1=.22, radius2=.05, depth=.18, location=(0, .25, 1.88), vertices=64); sh = bpy.context.object
    so = sh.modifiers.new('s', 'SOLIDIFY'); so.thickness = .006; sh.data.materials.append(M('shade', (.05, .25, .2), .35, .3)); bpy.ops.object.shade_smooth()
    bpy.ops.mesh.primitive_uv_sphere_add(radius=.05, location=(0, .25, 1.8)); bulb = bpy.context.object
    bulb.data.materials.append(kit.mat_emit('bulb', (1, .72, .4), 40 if dark else 0)); bpy.ops.object.shade_smooth()
    if dark:
        p = point('lamp', (0, .25, 1.74), 50, (1, .66, .35), .06)

def cast(exprs, poses=None):
    """Leo (left), Kai (middle), Mia (right), standing behind the table facing the camera (-Y)"""
    out = {}
    for who, x in (('leo', -.5), ('kai', 0), ('mia', .5)):
        if who not in exprs: continue
        root, parts = kit.character(who, loc=(x, .65, 0), height=1.05)
        root.rotation_euler = (0, 0, math.radians({'leo': 8, 'kai': 0, 'mia': -8}[who]))
        e = exprs[who]; v = parts['face_mat'].node_tree.nodes['expr'].outputs[0]; v.default_value = kit.EXPRS.index(e)
        if poses and who in poses:
            for arm, rot in poses[who].items(): parts[arm].rotation_euler = rot
        out[who] = (root, parts)
    return out

def plant(loc, alive=True):
    """potted houseplant (pothos-like): stems rising from the soil, heart-shaped leaves on short petioles"""
    cyl('pot', (loc[0], loc[1], loc[2] + .06), .065, .12, M('terracotta', (.55, .22, .1), .7))
    cyl('soil', (loc[0], loc[1], loc[2] + .118), .058, .006, M('soil', (.06, .04, .03), .9))
    leaf = M('leaf', (.06, .3, .07) if alive else (.25, .2, .08), .45); leaf.node_tree.nodes['Principled BSDF'].inputs['Subsurface Weight'].default_value = .25
    stem = M('stem', (.12, .3, .08), .6)
    import random; r = random.Random(9)
    for k in range(14):
        a = k * 2.4; tilt = math.radians(r.uniform(15, 50)); ln = r.uniform(.08, .2)
        x0, y0, z0 = loc[0] + .02 * math.cos(a), loc[1] + .02 * math.sin(a), loc[2] + .12
        dx, dy, dz = math.sin(tilt) * math.cos(a), math.sin(tilt) * math.sin(a), math.cos(tilt)
        bpy.ops.mesh.primitive_cylinder_add(radius=.0035, depth=ln, location=(x0 + dx * ln / 2, y0 + dy * ln / 2, z0 + dz * ln / 2)); st = bpy.context.object
        st.rotation_euler = (Vector((dx, dy, dz))).to_track_quat('Z', 'Y').to_euler(); st.data.materials.append(stem)
        tx, ty, tz = x0 + dx * ln, y0 + dy * ln, z0 + dz * ln
        bpy.ops.mesh.primitive_uv_sphere_add(radius=.045, location=(tx + dx * .03, ty + dy * .03, tz + .005), segments=24, ring_count=12); l = bpy.context.object
        l.scale = (1.0, .62, .1); l.rotation_euler = (math.radians(r.uniform(-25, 25)), math.radians(-30 + r.uniform(-10, 10)), a)
        l.data.materials.append(leaf); bpy.ops.object.shade_smooth()

def day_light():
    """morning sun low through the window: warm key light + a soft shaft of light (volume) + cool sky fill"""
    s = bpy.data.lights.new('sun', 'SUN'); s.energy = 12 if name == 'bowl' else 32; s.color = (1, .78, .5); s.angle = math.radians(1.5)
    o = kit.link(bpy.data.objects.new('sun', s)); o.rotation_euler = (Vector((.22, -1, -.3))).to_track_quat('-Z', 'Y').to_euler()
    area('skyfill', (0, 1.4, 1.3), (0, -1, .8), 60, (.55, .7, 1), 1.1)
    area('front', (.6, -3, 1.6), (0, .6, .8), 55, (1, .85, .7), 3)
    haze(.025)

def dark_light():
    area('front', (.6, -3, 1.6), (0, .6, .8), 12, (.45, .6, 1), 3)    # cool dim fill (moody blue)
    area('rim', (-.8, 1.2, 2.2), (0, .6, .9), 18, (.35, .5, 1), 1)
    haze(.012)

def haze(density):
    bpy.ops.mesh.primitive_cube_add(location=(0, 0, 1.5)); v = bpy.context.object; v.scale = (2.5, 1.9, 1.3); v.location = (0, -.2, 1.3); v.name = 'haze'
    m = bpy.data.materials.new('haze'); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); vs = N.new('ShaderNodeVolumeScatter')
    vs.inputs['Density'].default_value = density; vs.inputs['Anisotropy'].default_value = .5; L.new(vs.outputs[0], o.inputs['Volume']); v.data.materials.append(m)

def cam(loc, look, lens, fstop=None, focus=None):
    c, t = kit.camera(loc, look, lens=lens)
    if fstop:
        c.data.dof.use_dof = True; c.data.dof.focus_distance = focus or (Vector(loc) - Vector(look)).length; c.data.dof.aperture_fstop = fstop
    return c

# ================================================================== plates
def kitchen_plate():
    dark = not DAY
    wy, ck = kitchen(dark); lamp(dark)
    (day_light if not dark else dark_light)()
    T = {'clock': (8, 12, None), 'clock_820': (8, 20, None), 'wide_day': (8, 12, None), 'cu_kai_day': (8, 14, None), 'cu_leo_day': (8, 15, None), 'ots_day': (8, 20, None), 'bowl': (8, 14, None)}.get(name, (8, 21, None))
    clock_hands(ck, *T)
    plant((.42, wy - .14, .72), alive=True)
    E = {'wide_day': dict(leo='happy', kai='neutral', mia='smirk'), 'wide_dark': dict(leo='scared', kai='surprised', mia='worried'),
         'cu_kai_day': dict(kai='happy', leo='happy', mia='smirk'), 'cu_leo_day': dict(leo='happy', kai='neutral', mia='smirk'),
         'cu_kai_dark': dict(kai='surprised', leo='scared', mia='worried'), 'cu_leo_dark': dict(leo='scared', kai='worried', mia='worried'),
         'cu_mia_dark': dict(mia='worried', kai='surprised', leo='scared'), 'cu_mia_explain': dict(mia='neutral', kai='worried', leo='worried'),
         'ots_day': dict(kai='neutral', leo='happy', mia='happy'), 'ots_dark': dict(kai='surprised', leo='scared', mia='worried'),
         'trio_dark': dict(kai='worried', leo='scared', mia='smirk'), 'fridge_dark': dict(kai='worried', leo='scared', mia='worried'), 'cu_kai_ask': dict(kai='worried', leo='worried', mia='neutral')}.get(name)
    if E:
        P = {}
        if name in ('cu_leo_dark', 'wide_dark'): P['leo'] = {'arm_l': (0, math.radians(-150), 0), 'arm_r': (0, math.radians(150), 0)}   # hands up in panic
        if name == 'cu_mia_explain': P['mia'] = {'arm_r': (math.radians(-60), math.radians(40), 0)}
        if name == 'trio_dark': P['mia'] = {'arm_r': (math.radians(-80), math.radians(20), 0)}
        cast(E, P)
    if name in ('window_day', 'window_moon', 'window_dark'):
        if name == 'window_moon':   # the waning Moon low in the morning sky, seen through the window
            mo = kit.moon(R=.2, real=True, face_lon=0); mo.location = (.3, wy + 1.4, 1.62)
            s = bpy.data.lights.new('moonsun', 'SUN'); s.energy = 4; o = kit.link(bpy.data.objects.new('ms', s)); o.rotation_euler = (math.radians(60), math.radians(-50), 0)
            o.rotation_euler = (Vector((-1, .3, -.2))).to_track_quat('-Z', 'Y').to_euler()
        cam((0, wy - 1.7, 1.25), (0, wy, 1.32), 40)
    shots = {
        'wide_day': ((0, -2.9, 1.15), (0, .9, .95), 30, 5.6), 'wide_dark': ((0, -2.9, 1.15), (0, .9, .95), 30, 5.6),
        'cu_kai_day': ((.05, -.6, 1.02), (0, .65, .86), 50, 2.0), 'cu_kai_dark': ((.05, -.6, 1.02), (0, .65, .86), 50, 2.0),
        'cu_kai_ask': ((-.2, -.6, 1.0), (0, .65, .86), 50, 2.0),
        'cu_leo_day': ((-.6, -.55, 1.0), (-.5, .65, .86), 50, 2.0), 'cu_leo_dark': ((-.62, -.6, .98), (-.5, .65, .88), 45, 2.0),
        'cu_mia_dark': ((.6, -.55, 1.0), (.5, .65, .86), 50, 2.0), 'cu_mia_explain': ((.4, -.6, 1.0), (.5, .65, .86), 50, 2.0),
        'ots_day': ((-.35, -.15, 1.05), (.2, 1.6, 1.25), 26, 4.0), 'ots_dark': ((-.35, -.15, 1.05), (.2, 1.6, 1.25), 26, 4.0),
        'trio_dark': ((-.9, -1.6, .85), (0, .7, .85), 34, 4.0),
        'clock': ((1.15, .5, 1.75), (1.15, 1.6, 1.75), 50, None), 'clock_820': ((1.15, .5, 1.75), (1.15, 1.6, 1.75), 50, None),
        'fridge_dark': ((-1.0, -.6, 1.2), (-1.75, 1.1, 1.15), 32, 4.0),
        'bowl': ((0, -.42, .62), (0, .05, .55), 55, 1.6),
        'plant_dark': ((.38, wy - .95, .98), (.42, wy - .14, .86), 55, 2.8),
    }
    if name in shots:
        loc, look, lens, fs = shots[name]; cam(loc, look, lens, fs)

def space_plate():
    if name in ('sun_earth', 'sun_earth_off'):
        kit.world(real=True, strength=.35)
        sun = kit.sun_sphere(R=1.5, strength=30.0); sun.location = (1.4, 9, 2.6)
        if name == 'sun_earth_off': sun.hide_render = True
        e, _ = kit.earth(R=1.6, sun_dir=(.18, .9, .42), face_lon=-75, real=True); e.location = (-.4, 0, -1.6)
        if name == 'sun_earth': kit.sun_lamp(direction=(.18, .9, .42), energy=6.0)
        cam((0, -5.5, -.4), (.2, 3, .6), 30)
    elif name in ('earth_dark', 'earth_us', 'earth_iceland'):
        kit.world(real=True, strength=.45)
        face = {'earth_dark': -40, 'earth_us': -96, 'earth_iceland': -19}[name]
        e, spin = kit.earth(R=2.0, sun_dir=(0, 1, 0), face_lon=face, real=True, tilt_deg=0)   # Sun "behind" Earth: the whole visible face is night
        tilt = {'earth_dark': 20, 'earth_us': 38, 'earth_iceland': 62}[name]
        e.rotation_euler.x += math.radians(-tilt * .0)
        for ob in bpy.data.objects:
            if ob.type == 'LIGHT': ob.data.energy = 0
        latc = {'earth_dark': 20, 'earth_us': 38, 'earth_iceland': 64}[name]
        d = 7.2 if name == 'earth_dark' else 5.0
        a = math.radians(latc); cam((0, -d * math.cos(a), d * math.sin(a)), (0, 0, 0), {'earth_dark': 35, 'earth_us': 36, 'earth_iceland': 50}[name])
        bpy.context.view_layer.update()
        from bpy_extras.object_utils import world_to_camera_view
        import json
        pts = {'ny': (40.71, -74.01), 'la': (34.05, -118.24), 'reykjavik': (64.15, -21.94)}
        res = {}
        for k, (la_, lo_) in pts.items():
            v = spin.matrix_world @ kit.latlon(la_, lo_, 2.0, face_lon=face)
            p = world_to_camera_view(sc, sc.camera, v); res[k] = [p.x, 1 - p.y, p.z]
        json.dump(res, open(f'{OUT}/{name}.json', 'w')); print('PTS', res)
    elif name == 'pole':
        flat_world((.002, .004, .012), 1.0); kit.world(real=True, strength=.6)
        t = kit.terrain(size=40, height=1.2, scale=2.5, kind='snow', seed=3)
        m = bpy.data.lights.new('starlight', 'SUN'); m.energy = .25; m.color = (.5, .65, 1); o = kit.link(bpy.data.objects.new('sl', m)); o.rotation_euler = (math.radians(70), 0, math.radians(30))
        t.scale = (1, 1, .25)   # the polar plateau is nearly flat
        a = area('station', (5, 14, 1.2), (0, 0, 0), 300, (1, .7, .4), 2)
        f = area('fill', (-6, -6, 6), (0, 4, 0), 150, (.4, .55, 1), 8)
        stripe = kit._cloth('polestripe', (.85, .1, .1), (.95, .95, .95), 7)
        cyl('pole', (0, 0, .6), .045, 1.2, stripe)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=.16, location=(0, 0, 1.33), segments=64, ring_count=32); bl = bpy.context.object
        bl.data.materials.append(M('chrome', (.95, .95, .97), .04, 1)); bpy.ops.object.shade_smooth()
        cyl('base', (0, 0, .02), .2, .06, M('basew', (.3, .3, .32), .5))
        # distant research station on stilts with warm windows
        box('station', (5, 16, 1.0), (4, 1.2, .8), M('stw', (.2, .22, .25), .6), .02)
        for k in range(10): box('win', (3.3 + k * .38, 15.38, 1.05), (.18, .02, .12), kit.mat_emit('stwin', (1, .7, .35), 6), 0)
        for x in (3.4, 5, 6.6): box('stilt', (x, 16, .3), (.12, .12, .6), M('stilt', (.15, .15, .17), .5), 0)
        cam((-.9, -3.2, .9), (.4, 6, 1.0), 26, 8.0, 3.3)

if name in ('sun_earth', 'sun_earth_off', 'earth_dark', 'earth_us', 'earth_iceland', 'pole'): space_plate()
else: kitchen_plate()
sc.render.filepath = f'{OUT}/{name}.png'
bpy.ops.render.render(write_still=True)
print('WROTE', sc.render.filepath)
