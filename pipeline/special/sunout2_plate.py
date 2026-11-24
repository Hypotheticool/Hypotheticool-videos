"""Story Short: The Sun went out, Day 7 (Part 2). Built on the Part 1 set/helpers (sunout_plate.py). One Cycles still per plate (animated in 2D by sunout_anim.py).
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
OUT = '/home/claude/b3d/sunout2/plates'; os.makedirs(OUT, exist_ok=True)
W, H = int(1080 * S), int(1920 * S)
sc = kit.reset(res=(W, H), samples=int(os.environ.get('SAMPLES', 48)))
sc.cycles.adaptive_threshold = 0.03; sc.cycles.max_bounces = 5; sc.cycles.diffuse_bounces = 3
DAY = name in ('sun_earth',)

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

# ================================================================== PART 2 plates (Iceland, day 7)
import random
def strip_kitchen():
    """turn the Part 1 kitchen into the Iceland room: no cereal, no city skyline (a dark lava field + plant lights outside instead)"""
    for o in list(bpy.data.objects):
        n = o.name
        if n.startswith(('Sphere', 'milk', 'Torus', 'spoon', 'b0', 'b1', 'b2', 'b3', 'b4', 'b5', 'b6', 'b7', 'b8', 'w')) and not n.startswith(('wall', 'win')):
            bpy.data.objects.remove(o, do_unlink=True)
    wy = 1.6
    # outside: low dark ridge (Hengill) + far plant lights + glowing steam columns lit from below
    ridge = M('ridge', (.006, .007, .01), .9)
    for k in range(7):
        x = -2.6 + k * .85; h = .25 + .18 * math.sin(k * 1.7) ** 2
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=(x, wy + 2.6, .55)); r = bpy.context.object; r.scale = (.7, .2, h); r.data.materials.append(ridge); r.visible_shadow = False
    lit = kit.mat_emit('plantlight', (1.0, .62, .3), 8.0)
    for k in range(14):
        box(f'pl{k}', (-.5 + k * .075, wy + 2.3, .72 + .02 * (k % 3)), (.025, .01, .018), lit, 0)
    return wy

def radiator(wy):
    """white panel radiator under the window (geothermal hot water) with a warm glow"""
    rm = M('radiator', (.85, .84, .8), .35, coat=.3)
    for k in range(16):
        box(f'fin{k}', (-.45 + k * .06, wy - .16, .42), (.04, .07, .5), rm, .012)
    box('rad_top', (0, wy - .16, .68), (1.0, .08, .02), rm, .005)
    cyl('pipe_in', (-.55, wy - .16, .2), .015, .4, M('pipecopper', (.8, .45, .25), .3, 1))
    cyl('valve', (-.55, wy - .21, .3), .03, .04, M('valve', (.75, .12, .1), .4), rot=(math.pi / 2, 0, 0))
    point('radglow', (0, wy - .35, .45), 25, (1, .55, .3), .4)

def iceland_room(exprs=None, poses=None, clock=None):
    wy, ck = kitchen(True); strip_kitchen(); radiator(wy); lamp(True); dark_light()
    clock_hands(ck, *(clock or (12, 0, None)))
    plant((.42, wy - .14, .72), alive=True)
    for x in (-.45, .45): cyl('mug', (x, .15, .52), .045, .1, M('mug2', (.75, .3, .12), .3, coat=.5))
    box('map', (-1.0, wy - .055, 1.95), (.5, .01, .32), kit.mat_emit('mapart', (.25, .45, .6), .35), 0)  # a wall map
    if exprs: cast(exprs, poses)
    return wy, ck

def room_plate():
    E_ = {'wide_ice': dict(leo='worried', kai='neutral', mia='smirk'), 'cu_leo_noon': dict(leo='scared', kai='surprised', mia='neutral'),
          'cu_leo_ask': dict(leo='worried', kai='worried', mia='neutral'), 'cu_mia_explain': dict(mia='neutral', kai='worried', leo='worried'),
          'cu_mia_warm': dict(mia='happy', kai='smirk', leo='happy'), 'cu_kai_ask': dict(kai='worried', leo='worried', mia='neutral'),
          'cu_kai_cold': dict(kai='scared', leo='scared', mia='worried'), 'trio_ice': dict(kai='happy', leo='happy', mia='smirk'),
          'window_ice': None, 'rad_cu': None, 'clock_noon': None}[name]
    P = {}
    if name == 'cu_leo_noon': P['leo'] = {'arm_l': (0, math.radians(-150), 0), 'arm_r': (0, math.radians(150), 0)}
    if name == 'cu_mia_explain': P['mia'] = {'arm_r': (math.radians(-60), math.radians(40), 0)}
    if name == 'trio_ice': P['mia'] = {'arm_r': (math.radians(-80), math.radians(20), 0)}
    wy, ck = iceland_room(E_, P)
    shots = {
        'wide_ice': ((0, -2.9, 1.15), (0, .9, .95), 30, 5.6),
        'cu_kai_ask': ((-.2, -.6, 1.0), (0, .65, .86), 50, 2.0), 'cu_kai_cold': ((.05, -.6, 1.02), (0, .65, .86), 50, 2.0),
        'cu_leo_noon': ((-.62, -.6, .98), (-.5, .65, .88), 45, 2.0), 'cu_leo_ask': ((-.6, -.55, 1.0), (-.5, .65, .86), 50, 2.0),
        'cu_mia_explain': ((.4, -.6, 1.0), (.5, .65, .86), 50, 2.0), 'cu_mia_warm': ((.6, -.55, 1.0), (.5, .65, .86), 50, 2.0),
        'trio_ice': ((-.9, -1.6, .85), (0, .7, .85), 34, 4.0),
        'window_ice': ((0, wy - 1.7, 1.15), (0, wy, 1.22), 38, None),
        'rad_cu': ((.35, wy - .85, .62), (0, wy - .16, .45), 45, 2.2),
        'clock_noon': ((1.15, .5, 1.75), (1.15, 1.6, 1.75), 50, None),
    }
    loc, look, lens, fs = shots[name]; cam(loc, look, lens, fs)

# ---------------------------------------------------------------- Hellisheiði-style geothermal plant at night (lava field, snow, pipelines, steam)
def geo_plant(cast_out=False):
    kit.world(real=True, strength=.5, rot_deg=(0, 25, 140))
    t = kit.terrain(size=120, height=.9, scale=6, kind='volcanic', seed=2); t.location.z = -.4
    sn = kit.terrain(size=120, height=.9, scale=6, kind='snow', seed=2); sn.location.z = -.37
    # snow sits on the lava field in patches: give the snow layer holes with a noise-driven alpha
    sm = sn.data.materials[0]; nt = sm.node_tree; N, L = nt.nodes, nt.links; bs = N['Principled BSDF']; outn = N['Material Output']
    tc = N.new('ShaderNodeTexCoord'); nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = .35; nz.inputs['Detail'].default_value = 8
    L.new(tc.outputs['Object'], nz.inputs[0]); cr = N.new('ShaderNodeMapRange'); cr.inputs['From Min'].default_value = .45; cr.inputs['From Max'].default_value = .52
    L.new(nz.outputs['Fac'], cr.inputs[0]); tr = N.new('ShaderNodeBsdfTransparent'); mx = N.new('ShaderNodeMixShader')
    L.new(cr.outputs[0], mx.inputs['Fac']); L.new(tr.outputs[0], mx.inputs[1]); L.new(bs.outputs[0], mx.inputs[2]); L.new(mx.outputs[0], outn.inputs[0])
    # distant mountains (dark silhouettes)
    mt = M('mtn', (.03, .035, .045), .9)
    for k in range(6):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=(-40 + k * 16, 55, 0)); m_ = bpy.context.object; m_.scale = (14, 6, 6 + 4 * (k % 3)); m_.data.materials.append(mt)
    # main power house: long box with a glass front lit warm, plus a taller turbine hall
    wall = M('plantwall', (.12, .13, .14), .6); glass = kit.mat_emit('plantglass', (1.0, .66, .35), 2.2)
    box('hall', (0, 14, 2.2), (16, 6, 4.4), wall, .05); box('hall2', (-3, 14, 5.2), (7, 5, 2.0), wall, .05)
    for k in range(18): box(f'gw{k}', (-7.4 + k * .87, 10.97, 2.6), (.7, .05, 2.2), glass, 0)
    box('roofline', (0, 10.95, 4.45), (16.2, .1, .12), kit.mat_emit('roofled', (1, .8, .55), 3), 0)
    # silencers / steam stacks (round concrete towers venting steam) to the right
    conc = kit.mat_pbr('concrete', 'conc')
    stacks = [(9, 18, 7), (12.5, 21, 9), (6, 24, 6), (15, 16, 6.5)]
    for k, (x, y, h) in enumerate(stacks):
        cyl(f'stack{k}', (x, y, h / 2), 1.1, h, conc, verts=64)
        for j in range(3):
            kit.volume_cloud(loc=(x + .8 + j * 1.3, y + .5 * j, h + 2.5 + j * 4.2), size=(1.8 + j * 1.1, 1.8 + j * 1.1, 3.2 + j), density=1.1 - j * .25, kind='steam', seed=k * 3 + j)
    # insulated pipelines (aluminium-clad) on supports, zig-zagging across the field toward camera
    alu = kit.mat_pbr('aluminium', 'alu'); sup = M('support', (.25, .22, .2), .7)
    def pipe(p0, p1, r=.45):
        v = Vector(p1) - Vector(p0); mid = (Vector(p0) + Vector(p1)) / 2
        bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=v.length, location=mid, vertices=48); o = bpy.context.object
        o.rotation_euler = v.to_track_quat('Z', 'Y').to_euler(); o.data.materials.append(alu); bpy.ops.object.shade_smooth()
        n = int(v.length / 4)
        for j in range(1, n):
            q = Vector(p0) + v * (j / n); box('sup', (q.x, q.y, q.z / 2), (.25, .9, q.z), sup, .02)
    pipe((-14, -4, 1.2), (-4, 4, 1.2)); pipe((-4, 4, 1.2), (6, 4, 1.2)); pipe((6, 4, 1.2), (10, 14, 1.2))
    pipe((-14, -2.6, 1.2), (-4.6, 5.4, 1.2), .3)
    # warm floodlights on the plant + cool starlight
    for x in (-6, 0, 6): area(f'fl{x}', (x, 6, 7), (x, 14, 1), 1500, (1, .62, .3), 3)
    area('stackfl', (11, 12, 2), (12, 20, 10), 4000, (1, .55, .28), 4)
    s = bpy.data.lights.new('star', 'SUN'); s.energy = .12; s.color = (.5, .62, 1); o = kit.link(bpy.data.objects.new('st', s)); o.rotation_euler = (math.radians(50), 0, math.radians(20))
    if cast_out:
        for who, x in (('leo', -1.7), ('kai', -1.2), ('mia', -.7)):
            root, parts = kit.character(who, loc=(x, -6.5, -.25), height=1.1); root.rotation_euler = (0, 0, math.radians(180 + 15))
            parts['face_mat'].node_tree.nodes['expr'].outputs[0].default_value = kit.EXPRS.index('surprised')
        area('castrim', (-1.2, -4.5, 2), (-1.2, -6.5, .5), 60, (1, .6, .3), 2)

def plant_plate():
    if name == 'plant_ext':
        geo_plant(); cam((-13, -7, 1.6), (3, 14, 6.5), 26)
    elif name == 'plant_pipes':
        geo_plant(); cam((-8.5, -1.2, 1.6), (-2, 4.8, 1.6), 32, 4.0, 8.5)
    elif name == 'plant_cast':
        geo_plant(cast_out=True); cam((-1.2, -10.5, .9), (1.5, 14, 4.2), 26, 6.0, 4.2)

# ---------------------------------------------------------------- stars at noon: snowy yard, the cast seen from behind looking up
def sky_noon():
    kit.world(real=True, strength=.9, rot_deg=(20, -35, 60))
    bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 0, 0)); g = bpy.context.object; g.data.materials.append(kit.mat_pbr('snow', 'yardsnow'))
    d = g.modifiers.new('sub', 'SUBSURF'); d.subdivision_type = 'SIMPLE'; d.levels = d.render_levels = 6
    dd = g.modifiers.new('d', 'DISPLACE'); tx = bpy.data.textures.new('sn', 'CLOUDS'); tx.noise_scale = 1.5; dd.texture = tx; dd.strength = .12
    for who, x in (('leo', -.45), ('kai', 0), ('mia', .45)):
        root, parts = kit.character(who, loc=(x, 0, 0), height=1.05); root.rotation_euler = (math.radians(-8), 0, math.radians(180))
    area('porch', (0, -2.5, 2.2), (0, 0, .7), 70, (1, .62, .32), 2); area('rimstar', (0, 4, 3), (0, 0, .8), 40, (.4, .55, 1), 3)
    s = bpy.data.lights.new('star', 'SUN'); s.energy = .2; s.color = (.5, .62, 1); o = kit.link(bpy.data.objects.new('st', s)); o.rotation_euler = (math.radians(40), 0, math.radians(200))
    cam((0, -2.6, .5), (0, 4, 3.4), 22, 8.0, 2.6)

# ---------------------------------------------------------------- deep sea: black smoker chimney + tube worms (Riftia), submarine
def deep_world(col=(.0, .008, .02)):
    flat_world(col, 1.0)
    bpy.ops.mesh.primitive_cube_add(location=(0, 0, 3)); v = bpy.context.object; v.scale = (30, 30, 12)
    m = bpy.data.materials.new('sea_vol'); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); vs = N.new('ShaderNodeVolumePrincipled')
    vs.inputs['Color'].default_value = (.2, .55, .7, 1); vs.inputs['Density'].default_value = .045; vs.inputs['Anisotropy'].default_value = .6
    vs.inputs['Absorption Color'].default_value = (.05, .5, .6, 1); L.new(vs.outputs[0], o.inputs['Volume']); v.data.materials.append(m)

def chimney(loc, h=4.0, r=.55, seed=1):
    rr = random.Random(seed); rock = bpy.data.materials.new('sulfide'); nt, N, L = kit.nodes(rock)
    o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled'); tc = N.new('ShaderNodeTexCoord')
    nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 3; nz.inputs['Detail'].default_value = 12; L.new(tc.outputs['Object'], nz.inputs[0])
    cr = N.new('ShaderNodeValToRGB'); cr.color_ramp.elements[0].color = (.04, .035, .03, 1); cr.color_ramp.elements[1].color = (.32, .22, .12, 1)  # dark sulfides with rusty-ochre staining
    L.new(nz.outputs['Fac'], cr.inputs[0]); L.new(cr.outputs[0], bs.inputs['Base Color']); bs.inputs['Roughness'].default_value = .9
    bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = .9; L.new(nz.outputs['Fac'], bp.inputs['Height']); L.new(bp.outputs[0], bs.inputs['Normal'])
    L.new(bs.outputs[0], o.inputs[0])
    z = 0
    while z < h:
        seg = rr.uniform(.5, .8); rad = r * (1 - z / h * .55) * rr.uniform(.9, 1.1)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=(loc[0] + rr.uniform(-.08, .08), loc[1] + rr.uniform(-.08, .08), loc[2] + z + seg / 2), segments=32, ring_count=16)
        b = bpy.context.object; b.scale = (rad, rad * rr.uniform(.85, 1.1), seg * 1.1); b.data.materials.append(rock)
        d = b.modifiers.new('d', 'DISPLACE'); tx = bpy.data.textures.new('ct', 'CLOUDS'); tx.noise_scale = .12; d.texture = tx; d.strength = .22; b.modifiers.new('ss','SUBSURF').levels = 2
        bpy.ops.object.shade_smooth(); z += seg * .5
    # hot orifice glow at the top (shimmering water is drawn in 2D)
    point('orifice', (loc[0], loc[1] - .2, loc[2] + h + .1), 40, (1, .5, .2), .2)

def tube_worms(cx, cy, cz, n=70, spread=1.3, seed=3):
    rr = random.Random(seed); tube = M('tube', (.9, .9, .86), .5); plume = M('plume', (.85, .03, .05), .35)
    plume.node_tree.nodes['Principled BSDF'].inputs['Subsurface Weight'].default_value = .4
    for k in range(n):
        a = rr.uniform(0, 2 * math.pi); d = spread * math.sqrt(rr.random()); x, y = cx + d * math.cos(a), cy + d * math.sin(a)
        ln = rr.uniform(.4, 1.3); tx, ty = rr.uniform(-.25, .25), rr.uniform(-.25, .25)
        dirv = Vector((tx, ty, 1)).normalized()
        bpy.ops.mesh.primitive_cylinder_add(radius=.035, depth=ln, location=(x + dirv.x * ln / 2, y + dirv.y * ln / 2, cz + dirv.z * ln / 2), vertices=16)
        tb = bpy.context.object; tb.rotation_euler = dirv.to_track_quat('Z', 'Y').to_euler(); tb.data.materials.append(tube); bpy.ops.object.shade_smooth()
        top = Vector((x, y, cz)) + dirv * ln
        bpy.ops.mesh.primitive_cylinder_add(radius=.05, depth=.2, location=top + dirv * .08, vertices=24); p = bpy.context.object
        p.rotation_euler = tb.rotation_euler; p.data.materials.append(plume)
        sb = p.modifiers.new('s', 'SUBSURF'); sb.levels = sb.render_levels = 3
        dp = p.modifiers.new('d', 'DISPLACE'); tx = bpy.data.textures.new('fr', 'CLOUDS'); tx.noise_scale = .012; dp.texture = tx; dp.strength = .03
        bpy.ops.object.shade_smooth()

def vent_plate():
    deep_world()
    t = kit.terrain(size=40, height=.35, scale=3, kind='volcanic', seed=4); t.location.z = -.3
    t.data.materials[0] = M('basalt', (.025, .022, .02), .85)
    chimney((0, 3, -.2), 4.2, .6, 1); chimney((-2.4, 6, -.2), 3.0, .45, 2); chimney((2.6, 7, -.2), 5.0, .7, 3)
    tube_worms(-.6, 1.6, -.15, 80, 1.1, 3); tube_worms(1.2, 2.2, -.15, 50, .8, 5)
    # crabs (white galatheid-like blobs)
    for k in range(10):
        r = random.Random(k); bpy.ops.mesh.primitive_uv_sphere_add(radius=.06, location=(r.uniform(-2, 2), r.uniform(.5, 3), -.1)); c = bpy.context.object
        c.scale = (1.3, 1, .45); c.data.materials.append(M('crab', (.85, .82, .75), .5))
    area('sublight', (-1.5, -3, 3), (0, 2, 1), 160, (.85, .95, 1), 1.5)   # the sub's floodlights (cool white)
    area('fill', (3, -2, 1), (0, 3, 1.5), 40, (.3, .6, .8), 3)
    if name == 'vent_wide': cam((-.5, -5.5, 1.6), (0, 4, 2.2), 26, 6.0, 7)
    else: cam((-1.6, -2.4, .9), (-.4, 1.8, .7), 40, 2.8, 3.9)

def sub_plate():
    deep_world((.0, .01, .03))
    hull = M('hull', (.04, .045, .05), .45, coat=.2)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=(0, 0, 0), segments=64, ring_count=32); h = bpy.context.object
    h.scale = (9, 1, 1); h.data.materials.append(hull); bpy.ops.object.shade_smooth()
    box('sail', (2.8, 0, 1.25), (2.2, .5, 1.4), hull, .2)
    box('sailplanes', (2.9, 0, 1.4), (.6, 2.6, .08), hull, .03)
    for r in ((0, 0, 0), (math.pi / 2, 0, 0)):
        box('fin', (-8.0, 0, 0), (1.0, .08, 3.0), hull, .03, rot=r)
    cyl('prop', (-8.9, 0, 0), .5, .15, M('bronze', (.6, .42, .2), .3, 1), rot=(0, math.pi / 2, 0))
    area('moon_down', (0, -6, 14), (0, 0, 0), 2500, (.4, .65, .9), 12); area('subrim', (-6, 8, 3), (0, 0, 0), 900, (.3, .7, .9), 6); area('subkey', (8, -8, 2), (0, 0, 0), 700, (.9, .95, 1), 4)
    point('nav', (2.8, 0, 2.05), 30, (1, .3, .2), .05)
    for ob in bpy.data.objects:
        if ob.type == 'LIGHT': ob.visible_camera = False
    if name == 'sub_wide': cam((7, -11, -1.0), (0, 0, .3), 32, 8.0, 13)
    else: cam((5.5, -4.2, .6), (2.5, 0, .9), 35, 4.0, 5)

# ---------------------------------------------------------------- a big conifer alone in the dark snow under the stars
def tree_plate():
    kit.world(real=True, strength=.7, rot_deg=(10, -20, 30))
    t = kit.terrain(size=60, height=1.2, scale=4, kind='snow', seed=9); t.location.z = -.2
    bark = kit.mat_pbr('bark'); ndl = M('needles', (.03, .1, .05), .7)
    def conifer(x, y, h, seed):
        cyl('trunk', (x, y, h * .25), h * .025, h * .5, bark)
        rr = random.Random(seed)
        for k in range(9):
            z = h * (.18 + k * .09); r = h * .28 * (1 - k / 9.5)
            bpy.ops.mesh.primitive_cone_add(radius1=r, depth=h * .16, location=(x, y, z), vertices=40); c = bpy.context.object
            c.rotation_euler.z = rr.uniform(0, 6.28); d = c.modifiers.new('d', 'DISPLACE'); tx = bpy.data.textures.new('nd', 'CLOUDS'); tx.noise_scale = .08
            d.texture = tx; d.strength = h * .04; c.modifiers.new('ss','SUBSURF').levels = 2; c.data.materials.append(ndl)
    conifer(0, 4, 9, 1)
    for k, (x, y, h) in enumerate([(-7, 12, 7), (8, 14, 8), (-12, 20, 9), (13, 22, 7)]): conifer(x, y, h, k + 2)
    area('lamp', (-3, 0, 3), (0, 4, 3), 400, (1, .62, .32), 2)
    s = bpy.data.lights.new('star', 'SUN'); s.energy = .25; s.color = (.5, .62, 1); o = kit.link(bpy.data.objects.new('st', s)); o.rotation_euler = (math.radians(45), 0, math.radians(160))
    cam((0, -6.5, .8), (0, 4, 4.2), 26)

# ---------------------------------------------------------------- space plates (same set-up as Part 1)
def space_plate():
    if name in ('sun_earth', 'sun_earth_off'):
        kit.world(real=True, strength=.35)
        sun = kit.sun_sphere(R=1.5, strength=30.0); sun.location = (1.4, 9, 2.6)
        if name == 'sun_earth_off': sun.hide_render = True
        e, _ = kit.earth(R=1.6, sun_dir=(.18, .9, .42), face_lon=-75, real=True); e.location = (-.4, 0, -1.6)
        if name == 'sun_earth': kit.sun_lamp(direction=(.18, .9, .42), energy=6.0)
        cam((0, -5.5, -.4), (.2, 3, .6), 30)
    else:   # earth_iceland / earth_dark: the night side only (no Sun), city lights
        kit.world(real=True, strength=.45)
        face = {'earth_dark': -40, 'earth_iceland': -19}[name]
        e, spin = kit.earth(R=2.0, sun_dir=(0, 1, 0), face_lon=face, real=True, tilt_deg=0)
        for ob in bpy.data.objects:
            if ob.type == 'LIGHT': ob.data.energy = 0
        latc = {'earth_dark': 20, 'earth_iceland': 64}[name]; d = 7.2 if name == 'earth_dark' else 5.0
        a = math.radians(latc); cam((0, -d * math.cos(a), d * math.sin(a)), (0, 0, 0), {'earth_dark': 35, 'earth_iceland': 50}[name])
        bpy.context.view_layer.update()
        from bpy_extras.object_utils import world_to_camera_view
        import json
        pts = {'reykjavik': (64.15, -21.94), 'hellisheidi': (64.04, -21.40)}
        res = {}
        for k, (la_, lo_) in pts.items():
            v = spin.matrix_world @ kit.latlon(la_, lo_, 2.0, face_lon=face)
            p = world_to_camera_view(sc, sc.camera, v); res[k] = [p.x, 1 - p.y, p.z]
        json.dump(res, open(f'{OUT}/{name}.json', 'w')); print('PTS', res)

if name in ('sun_earth', 'sun_earth_off', 'earth_dark', 'earth_iceland'): space_plate()
elif name.startswith('plant_'): plant_plate()
elif name == 'sky_noon': sky_noon()
elif name.startswith('vent_'): vent_plate()
elif name.startswith('sub_'): sub_plate()
elif name == 'tree': tree_plate()
else: room_plate()
sc.render.filepath = f'{OUT}/{name}.png'
bpy.ops.render.render(write_still=True)
print('WROTE', sc.render.filepath)
