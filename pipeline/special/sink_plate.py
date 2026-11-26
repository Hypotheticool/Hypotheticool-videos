"""Story Short: the car went into the lake. One Cycles still per plate (animated in 2D by sink_anim.py).
python3 sink_plate.py <plate> [res_scale]  -> sink/plates/<plate>.png
Exterior (December dusk, snowy shore, dark lake): splash (nose plunging in, hook), road (sliding on black ice), float_side (floating, water at the doors),
  nose_down (front sinking, rear up), under (underwater: nose-down car, headlight beams), roof (cast on the roof), shore (cast safe on the snow)
Interior (cartoon sedan sized for the cast): int_wide (from the back seat), cu_leo_door, cu_mia, cu_kai, window_cu (driver window + window hammer),
  int_water (water up to the windows, from the back)"""
import sys, math, os, random
sys.path.insert(0, '/home/claude/b3d')
import bpy, bmesh, kit
from mathutils import Vector
name = sys.argv[1]; S = float(sys.argv[2]) if len(sys.argv) > 2 else 0.6
OUT = '/home/claude/b3d/sink/plates'; os.makedirs(OUT, exist_ok=True)
W, H = int(1080 * S), int(1920 * S)
sc = kit.reset(res=(W, H), samples=int(os.environ.get('SAMPLES', 40)))
sc.cycles.adaptive_threshold = 0.04; sc.cycles.max_bounces = 6; sc.cycles.diffuse_bounces = 2; sc.cycles.transmission_bounces = 6; sc.cycles.transparent_max_bounces = 12

def area(nm, loc, aim, energy, color=(1, 1, 1), size=2.0):
    li = bpy.data.lights.new(nm, 'AREA'); li.energy = energy; li.color = color; li.size = size
    o = kit.link(bpy.data.objects.new(nm, li)); o.location = loc
    o.rotation_euler = (Vector(aim) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler(); o.visible_glossy = False; o.visible_transmission = False; return o

def point(nm, loc, energy, color, radius=.05):
    li = bpy.data.lights.new(nm, 'POINT'); li.energy = energy; li.color = color; li.shadow_soft_size = radius
    o = kit.link(bpy.data.objects.new(nm, li)); o.location = loc; o.visible_camera = False; o.visible_glossy = False; return o

def M(nm, col, rough=.5, metal=0.0, coat=0.0):
    return kit.mat_principled(nm, col, rough=rough, metal=metal, coat=coat)

def box(nm, loc, size, mat, bevel=.01, rot=(0, 0, 0), parent=None):
    bpy.ops.mesh.primitive_cube_add(location=loc); o = bpy.context.object; o.name = nm; o.scale = (size[0] / 2, size[1] / 2, size[2] / 2)
    o.rotation_euler = rot; bpy.ops.object.transform_apply(scale=True); o.data.materials.append(mat)
    if bevel: b = o.modifiers.new('b', 'BEVEL'); b.width = bevel; b.segments = 3
    if parent: o.parent = parent
    return o

def cyl(nm, loc, r, depth, mat, rot=(0, 0, 0), verts=40, parent=None):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=depth, location=loc, rotation=rot, vertices=verts); o = bpy.context.object; o.name = nm
    o.data.materials.append(mat); bpy.ops.object.shade_smooth()
    if parent: o.parent = parent
    return o

def cam(loc, look, lens, fstop=None, focus=None):
    c, t = kit.camera(loc, look, lens=lens)
    if fstop:
        c.data.dof.use_dof = True; c.data.dof.focus_distance = focus or (Vector(loc) - Vector(look)).length; c.data.dof.aperture_fstop = fstop
    return c

def volume_box(loc, scale, col=(.3, .6, .65), dens=.12, absorb=(.25, .55, .6), adens=.35):
    bpy.ops.mesh.primitive_cube_add(location=loc); v = bpy.context.object; v.scale = scale; v.name = 'uwvol'
    m = bpy.data.materials.new('uw'); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial')
    vs = N.new('ShaderNodeVolumeScatter'); vs.inputs['Color'].default_value = (*col, 1); vs.inputs['Density'].default_value = dens; vs.inputs['Anisotropy'].default_value = .65
    ab = N.new('ShaderNodeVolumeAbsorption'); ab.inputs['Color'].default_value = (*absorb, 1); ab.inputs['Density'].default_value = adens
    ad = N.new('ShaderNodeAddShader'); L.new(vs.outputs[0], ad.inputs[0]); L.new(ab.outputs[0], ad.inputs[1]); L.new(ad.outputs[0], o.inputs['Volume']); v.data.materials.append(m)
    return v

def haze(density, loc, scale, col=(.8, .85, 1)):
    bpy.ops.mesh.primitive_cube_add(location=loc); v = bpy.context.object; v.scale = scale; v.name = 'haze'
    m = bpy.data.materials.new('haze'); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); vs = N.new('ShaderNodeVolumeScatter')
    vs.inputs['Density'].default_value = density; vs.inputs['Anisotropy'].default_value = .55; vs.inputs['Color'].default_value = (*col, 1)
    L.new(vs.outputs[0], o.inputs['Volume']); v.data.materials.append(m); return v

def cast(spec, parent=None):
    out = {}
    for who, d in spec.items():
        root, parts = kit.character(who, loc=d['loc'], height=d.get('h', 1.0))
        if parent: root.parent = parent
        rx, ry, rz = d.get('rot', (0, 0, 0))
        if d.get('seated'): rz += 180   # seated cast faces the front of the car (+Y); 'rot' is relative to that
        root.rotation_euler = (math.radians(rx), math.radians(ry), math.radians(rz))
        parts['face_mat'].node_tree.nodes['expr'].outputs[0].default_value = kit.EXPRS.index(d.get('expr', 'neutral'))
        for arm, r in d.get('arms', {}).items(): parts[arm].rotation_euler = tuple(math.radians(a) for a in r)
        if d.get('seated'):
            for lg in ('leg_l', 'leg_r'): parts[lg].rotation_euler = (math.radians(-90), 0, 0)
        out[who] = (root, parts)
    return out

# ------------------------------------------------------------------ materials
def snow_mat(nm='snowfield'):
    m = bpy.data.materials.new(nm); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled')
    bs.inputs['Base Color'].default_value = (.5, .55, .62, 1); bs.inputs['Roughness'].default_value = .6
    bs.inputs['Subsurface Weight'].default_value = .15; bs.inputs['Subsurface Radius'].default_value = (.8, .9, 1)
    tc = N.new('ShaderNodeTexCoord'); nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 3; nz.inputs['Detail'].default_value = 10
    L.new(tc.outputs['Object'], nz.inputs[0]); bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = .3; L.new(nz.outputs['Fac'], bp.inputs['Height']); L.new(bp.outputs[0], bs.inputs['Normal'])
    L.new(bs.outputs[0], o.inputs[0]); return m

def lake_mat(nm='lake'):
    """dark winter lake water (IOR 1.333): glossy, tiny ripples"""
    m = bpy.data.materials.new(nm); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled')
    bs.inputs['Base Color'].default_value = (.004, .016, .02, 1); bs.inputs['Roughness'].default_value = .04; bs.inputs['IOR'].default_value = 1.333
    tc = N.new('ShaderNodeTexCoord'); nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 2.2; nz.inputs['Detail'].default_value = 6
    L.new(tc.outputs['Object'], nz.inputs[0]); wv = N.new('ShaderNodeTexWave'); wv.wave_type = 'RINGS'; wv.inputs['Scale'].default_value = .8; wv.inputs['Distortion'].default_value = 3
    L.new(tc.outputs['Object'], wv.inputs[0]); ad = N.new('ShaderNodeMath'); ad.operation = 'ADD'; L.new(nz.outputs['Fac'], ad.inputs[0]); L.new(wv.outputs['Fac'], ad.inputs[1])
    bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = .18; L.new(ad.outputs[0], bp.inputs['Height']); L.new(bp.outputs[0], bs.inputs['Normal'])
    # see-through near the surface so the submerged car reads (thin transmission)
    bs.inputs['Transmission Weight'].default_value = .55
    L.new(bs.outputs[0], o.inputs[0]); return m

def glass_mat(nm='carglass', tint=(.75, .85, .9)):
    """thin automotive glass: transparent + fresnel reflection (no refraction offset)"""
    m = bpy.data.materials.new(nm); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial')
    tr = N.new('ShaderNodeBsdfTransparent'); tr.inputs['Color'].default_value = (*tint, 1)
    gl = N.new('ShaderNodeBsdfGlossy'); gl.inputs['Roughness'].default_value = .03
    fr = N.new('ShaderNodeFresnel'); fr.inputs['IOR'].default_value = 1.52
    mx = N.new('ShaderNodeMixShader'); L.new(fr.outputs[0], mx.inputs[0]); L.new(tr.outputs[0], mx.inputs[1]); L.new(gl.outputs[0], mx.inputs[2]); L.new(mx.outputs[0], o.inputs[0])
    return m

def pine(loc, h, seed=0):
    r = random.Random(seed)
    trunk = bpy.data.materials.get('trunk') or M('trunk', (.08, .05, .03), .9); cyl(f'tr{seed}', (loc[0], loc[1], loc[2] + h * .1), h * .03, h * .2, trunk, verts=8)
    m = bpy.data.materials.get('pinesnow')
    if m is None:
        m = bpy.data.materials.new('pinesnow'); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial')
        g = N.new('ShaderNodeBsdfPrincipled'); g.inputs['Base Color'].default_value = (.015, .045, .035, 1); g.inputs['Roughness'].default_value = .85
        s = N.new('ShaderNodeBsdfPrincipled'); s.inputs['Base Color'].default_value = (.85, .9, .96, 1); s.inputs['Roughness'].default_value = .6
        ge = N.new('ShaderNodeNewGeometry'); sep = N.new('ShaderNodeSeparateXYZ'); L.new(ge.outputs['Normal'], sep.inputs[0])
        mr = N.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value = .45; mr.inputs['From Max'].default_value = .65; L.new(sep.outputs['Z'], mr.inputs[0])
        mx = N.new('ShaderNodeMixShader'); L.new(mr.outputs[0], mx.inputs[0]); L.new(g.outputs[0], mx.inputs[1]); L.new(s.outputs[0], mx.inputs[2]); L.new(mx.outputs[0], o.inputs[0])
    for k in range(4):
        z = loc[2] + h * (.18 + k * .19); rad = h * (.3 - k * .06)
        bpy.ops.mesh.primitive_cone_add(radius1=rad, radius2=0, depth=h * .32, location=(loc[0], loc[1], z + h * .1), vertices=12)
        c = bpy.context.object; c.rotation_euler = (r.uniform(-.04, .04), r.uniform(-.04, .04), r.uniform(0, 6)); c.data.materials.append(m)

# ------------------------------------------------------------------ the car (cartoon sedan sized for the 1 m cast; front = +Y in its own frame)
def car(loc=(0, 0, 0), rot_deg=(0, 0, 0), lights=True, occupants=None, interior=True):
    root = kit.link(bpy.data.objects.new('car', None)); root.location = loc; root.rotation_euler = tuple(math.radians(a) for a in rot_deg)
    paint = M('paint', (.42, .05, .04), .25, 0, coat=1.0); trim = M('trim', (.02, .02, .025), .5); chrome = M('chrome', (.8, .8, .82), .15, 1.0)
    # lower body: an open-topped shell (hollow cabin) with rounded edges
    bpy.ops.mesh.primitive_cube_add(location=(0, 0, .55)); lb = bpy.context.object; lb.name = 'body'; lb.scale = (.8, 1.75, .3); bpy.ops.object.transform_apply(scale=True)
    bm = bmesh.new(); bm.from_mesh(lb.data); bm.faces.ensure_lookup_table()
    top = [f for f in bm.faces if f.normal.z > .9]; bmesh.ops.delete(bm, geom=top, context='FACES'); bm.to_mesh(lb.data); bm.free()
    b = lb.modifiers.new('b', 'BEVEL'); b.width = .1; b.segments = 5; b.limit_method = 'ANGLE'
    s = lb.modifiers.new('s', 'SOLIDIFY'); s.thickness = .05; s.offset = -1; s.material_offset = 1; s.material_offset_rim = 1
    lb.data.materials.append(paint); lb.data.materials.append(M('doorcard', (.05, .055, .065), .7)); bpy.ops.object.shade_smooth(); lb.parent = root
    hood = box('hood', (0, 1.2, .83), (1.56, 1.06, .06), paint, .03, parent=root)
    trunk = box('trunkl', (0, -1.47, .83), (1.56, .5, .06), paint, .03, parent=root)
    # greenhouse: tapered box; roof painted, the rest glass, with dark pillars
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        if v.co.z > 0: v.co.x *= 1.36; v.co.y = -.98 if v.co.y < 0 else .22; v.co.z = 1.47
        else: v.co.x *= 1.56; v.co.y = -1.22 if v.co.y < 0 else .64; v.co.z = .86
    bm.faces.ensure_lookup_table(); bmesh.ops.delete(bm, geom=[f for f in bm.faces if abs(f.normal.z) > .9], context='FACES')
    me = bpy.data.meshes.new('gh'); bm.to_mesh(me); bm.free(); gh = kit.link(bpy.data.objects.new('greenhouse', me), root)
    gh.data.materials.append(glass_mat()); gh.data.materials.append(paint)
    for f in gh.data.polygons:
        if f.normal.z > .9: f.material_index = 1
    box('roofskin', (0, -.38, 1.48), (1.38, 1.22, .05), paint, .02, parent=root)
    box('headliner', (0, -.38, 1.43), (1.3, 1.15, .03), M('headliner', (.12, .12, .13), .9), .01, parent=root)
    for x in (-.74, .74):
        for (y0, z0, y1, z1) in ((.64, .86, .22, 1.47), (-.38, .86, -.38, 1.47), (-1.22, .86, -.98, 1.47)):
            v = Vector((0, y1 - y0, z1 - z0)); mid = Vector((x * (1 if abs(y0 - .64) > .01 else 1), (y0 + y1) / 2, (z0 + z1) / 2))
            bpy.ops.mesh.primitive_cylinder_add(radius=.035, depth=v.length, location=(x * (1 - .09 * ((mid.z - .86) / .61)), mid.y, mid.z), vertices=10)
            p = bpy.context.object; p.rotation_euler = v.to_track_quat('Z', 'Y').to_euler(); p.data.materials.append(trim); p.parent = root
    box('beltL', (-.79, -.29, .86), (.05, 1.9, .05), trim, .01, parent=root); box('beltR', (.79, -.29, .86), (.05, 1.9, .05), trim, .01, parent=root)
    # door seams + handles
    for x in (-.81, .81):
        for y in (.62, -.38, -1.2): box(f'seam{x}{y}', (x, y, .56), (.012, .012, .52), trim, 0, parent=root)
        for y in (.1, -.85): box(f'handle{x}{y}', (x * 1.005, y, .74), (.03, .2, .04), chrome, .01, parent=root)
    # wheels
    tire = M('tire', (.02, .02, .02), .8); hub = M('hub', (.55, .56, .58), .3, 1.0)
    for x in (-.74, .74):
        for y in (1.1, -1.1):
            cyl(f'tire{x}{y}', (x, y, .3), .3, .22, tire, rot=(0, math.pi / 2, 0), parent=root)
            cyl(f'hub{x}{y}', (x * 1.08, y, .3), .16, .04, hub, rot=(0, math.pi / 2, 0), parent=root)
    # bumpers, grille, lights
    box('bumperF', (0, 1.76, .38), (1.6, .1, .16), trim, .04, parent=root); box('bumperR', (0, -1.76, .38), (1.6, .1, .16), trim, .04, parent=root)
    box('grille', (0, 1.755, .6), (.7, .02, .16), trim, .01, parent=root)
    for x in (-.55, .55):
        box(f'hl{x}', (x, 1.745, .64), (.34, .04, .14), kit.mat_emit(f'hlm{x}', (1, .92, .75), 25 if lights else .2), .02, parent=root)
        box(f'tl{x}', (x, -1.745, .66), (.34, .04, .12), kit.mat_emit(f'tlm{x}', (1, .05, .03), 12 if lights else .5), .02, parent=root)
        if lights:
            li = bpy.data.lights.new(f'beam{x}', 'SPOT'); li.energy = 900; li.spot_size = math.radians(40); li.spot_blend = .6; li.color = (1, .9, .72); li.shadow_soft_size = .05
            o = kit.link(bpy.data.objects.new(f'beam{x}', li), root); o.location = (x, 1.85, .64); o.rotation_euler = (math.radians(-82), 0, 0)
    if interior:
        seatm = M('seat', (.06, .065, .075), .8); dash = M('dash', (.03, .035, .04), .6)
        for x in (-.38, .38):
            box(f'cush{x}', (x, .05, .44), (.5, .52, .14), seatm, .05, parent=root)
            box(f'back{x}', (x, -.24, .7), (.5, .12, .5), seatm, .05, rot=(math.radians(-10), 0, 0), parent=root)
        box('rcush', (0, -.9, .44), (1.4, .5, .14), seatm, .05, parent=root); box('rback', (0, -1.18, .76), (1.4, .12, .6), seatm, .05, rot=(math.radians(-12), 0, 0), parent=root)
        box('floor', (0, -.2, .33), (1.5, 3.0, .04), M('carpet', (.03, .03, .035), .95), 0, parent=root)
        box('dash', (0, .8, .76), (1.5, .4, .26), dash, .06, parent=root)
        box('gauges', (-.38, .62, .84), (.36, .02, .12), kit.mat_emit('gauge', (1, .55, .2), 4), .01, parent=root)
        box('screen', (0, .6, .82), (.24, .02, .14), kit.mat_emit('cscreen', (.3, .75, 1), 3), .01, parent=root)
        bpy.ops.mesh.primitive_torus_add(major_radius=.17, minor_radius=.022, location=(-.38, .5, .86)); sw = bpy.context.object; sw.rotation_euler = (math.radians(70), 0, 0)
        sw.data.materials.append(trim); sw.parent = root
    out = {}
    if occupants: out = cast(occupants, parent=root)
    return root, out

SEATED = {'kai': dict(loc=(-.38, .02, .3), seated=True, arms={'arm_l': (-70, 0, -8), 'arm_r': (-70, 0, 8)}),
          'leo': dict(loc=(.38, .02, .3), seated=True),
          'mia': dict(loc=(0, -.86, .3), seated=True)}
def seated(**over):
    sp = {k: dict(v) for k, v in SEATED.items()}
    for who, d in over.items():
        if d is None: sp.pop(who); continue
        sp[who].update(d)
    return sp

# ------------------------------------------------------------------ the lake set (1 unit = 1 m; the cast is ~1 m tall)
def lake_set(water_z=0.0, hole=None, sun_el=.8, sun_rot=200, under=False):
    sun = kit.sky(sun_el, sun_rot, strength=.07, sun_lamp_energy=2.2, dust=2.0)
    lm = lake_mat()
    if hole:   # keep the car's cabin dry: lake made of 4 strips around its footprint
        (x0, y0, x1, y1) = hole; R = 120
        for (a, b_, c, d) in ((-R, y1, R, R), (-R, -R, R, y0), (-R, y0, x0, y1), (x1, y0, R, y1)):
            bpy.ops.mesh.primitive_plane_add(location=((a + c) / 2, (b_ + d) / 2, water_z)); p = bpy.context.object; p.scale = ((c - a) / 2, (d - b_) / 2, 1)
            p.data.materials.append(lm)
    else:
        bpy.ops.mesh.primitive_plane_add(size=240, location=(0, 0, water_z)); p = bpy.context.object; p.name = 'lake'; p.data.materials.append(lm)
    bpy.ops.mesh.primitive_plane_add(size=240, location=(0, 0, water_z - 7)); bd = bpy.context.object; bd.data.materials.append(M('lakebed', (.02, .03, .03), .9))
    if under: volume_box((0, 0, water_z - 3.5), (30, 30, 3.49))
    # far shore: snowy bank with pines and a few warm cabin lights
    sn = snow_mat(); r = random.Random(3)
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 70, water_z + .3)); fb = bpy.context.object; fb.scale = (200, 30, 1); fb.data.materials.append(sn)
    for k in range(40):
        x = r.uniform(-60, 60); y = r.uniform(58, 80); pine((x, y, water_z + .3), r.uniform(5, 11), k)
    for k in range(5):
        x = r.uniform(-30, 30); bpy.ops.mesh.primitive_cube_add(location=(x, 57.5, water_z + 1.3)); w_ = bpy.context.object; w_.scale = (.5, .1, .35)
        w_.data.materials.append(kit.mat_emit(f'cabin{k}', (1, .6, .25), 30))
    haze(.006, (0, 30, 6), (80, 50, 8), (.8, .85, 1))
    return sun

def near_shore(y0=-6.0, water_z=0.0, road=True):
    """the snowy bank on the camera side (-Y) with the road along it"""
    sn = snow_mat()
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, y0 - 20, water_z + .25)); b = bpy.context.object; b.scale = (120, 40, 1); b.data.materials.append(sn)
    # sloping bank down into the water
    bpy.ops.mesh.primitive_cube_add(location=(0, y0 - 1.2, water_z - .3)); s_ = bpy.context.object; s_.scale = (60, 1.6, .55); s_.rotation_euler = (math.radians(-12), 0, 0); s_.data.materials.append(sn)
    if road:
        asphalt = bpy.data.materials.new('blackice'); nt, N, L = kit.nodes(asphalt); o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled')
        bs.inputs['Base Color'].default_value = (.025, .028, .032, 1); bs.inputs['Roughness'].default_value = .08; bs.inputs['Coat Weight'].default_value = 1.0
        tc = N.new('ShaderNodeTexCoord'); nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 6; L.new(tc.outputs['Object'], nz.inputs[0])
        mr = N.new('ShaderNodeMapRange'); mr.inputs['To Min'].default_value = .03; mr.inputs['To Max'].default_value = .4; L.new(nz.outputs['Fac'], mr.inputs[0]); L.new(mr.outputs[0], bs.inputs['Roughness'])
        L.new(bs.outputs[0], o.inputs[0])
        box('road', (0, y0 - 5.5, water_z + .27), (120, 4.2, .04), asphalt, 0)
        for k in range(-12, 13): box(f'dash{k}', (k * 4.0, y0 - 5.5, water_z + .3), (1.6, .1, .01), kit.mat_emit('roadline', (1, .8, .3), .6), 0)
        for k in range(-10, 11):   # snow-capped posts along the bank
            box(f'post{k}', (k * 3.0, y0 - 3.1, water_z + .65), (.1, .1, .8), M('post', (.85, .85, .8), .5), .01)

def roadside_pines(y0=-6.0, n=30, water_z=0.0):
    r = random.Random(9)
    for k in range(n): pine((r.uniform(-40, 40), y0 - r.uniform(10, 30), water_z + .25), r.uniform(4, 9), k + 300)

# ------------------------------------------------------------------ plates
def exterior():
    if name == 'splash':   # hook: the nose plunging into the lake, headlights glowing under the surface
        lake_set(0.0, under=True); near_shore(-7.0)
        car((0, 0, -.75), (-30, 0, 205), occupants=seated(kai=dict(expr='scared'), leo=dict(expr='scared', arms={'arm_l': (-150, 0, -20), 'arm_r': (-150, 0, 20)}), mia=dict(expr='scared')))
        area('key', (-3, -4, 3), (0, 0, .6), 400, (1, .62, .35), 3); area('rim', (4, 3, 2), (0, 0, .5), 250, (.4, .6, 1), 3)
        cam((-2.4, -4.4, .6), (0, 0, .05), 28, 4.0)
    elif name == 'road':   # the car sliding sideways on the black-ice road above the lake
        lake_set(0.0); near_shore(-6.0); roadside_pines(-6.0)
        car((1.0, -11.5, .29), (0, 0, 64), occupants=seated(kai=dict(expr='scared'), leo=dict(expr='scared')))
        area('key', (-4, -15, 4), (1, -11.5, .6), 500, (1, .62, .35), 4); area('rim', (4, -6, 3), (1, -11.5, .6), 300, (.4, .6, 1), 4)
        cam((-6.5, -16.5, 2.4), (.8, -10.5, .4), 30, 5.6)
    elif name in ('float_side', 'nose_down', 'roof'):
        lake_set(0.0, under=(name == 'nose_down'))
        if name == 'float_side':
            car((0, 0, -.42), (0, 0, 90), occupants=seated(kai=dict(expr='scared'), leo=dict(expr='worried'), mia=dict(expr='angry')))
            area('key', (-2, -4, 2.5), (0, 0, .6), 350, (1, .62, .35), 3); area('rim', (3, 4, 2), (0, 0, .5), 200, (.4, .6, 1), 3)
            cam((-.8, -5.2, .55), (0, 0, .45), 30, 5.6)
        elif name == 'nose_down':
            car((0, 0, -.6), (-24, 0, 90), occupants=seated(kai=dict(expr='scared'), leo=dict(expr='scared'), mia=dict(expr='scared')))
            area('key', (-2, -4, 2.5), (0, 0, .6), 350, (1, .62, .35), 3); area('rim', (3, 4, 2), (0, 0, .5), 200, (.4, .6, 1), 3)
            cam((-.2, -5.6, .4), (0, 0, .1), 28, 5.6)
        else:
            rt, _ = car((0, 0, -.62), (-6, 0, 90), lights=False)
            cast({'mia': dict(loc=(-.55, -.2, .9), expr='worried', rot=(0, 0, -20), arms={'arm_r': (0, 70, 0)}),
                  'kai': dict(loc=(.15, .15, .9), expr='scared', rot=(0, 0, 10)),
                  'leo': dict(loc=(.75, -.1, .82), expr='scared', rot=(0, 0, 25), arms={'arm_l': (-160, 0, -10), 'arm_r': (-160, 0, 10)})})
            area('key', (-2, -4, 3), (0, 0, 1.2), 400, (1, .62, .35), 3); area('rim', (3, 4, 2.5), (0, 0, 1.2), 250, (.4, .6, 1), 3)
            cam((-.6, -4.8, 1.0), (0, 0, 1.15), 30, 5.6)
    elif name == 'under':   # underwater: the car hanging nose-down, headlight beams into the murk, last air at the back
        lake_set(0.0, under=True)
        car((0, 0, -2.0), (-55, 0, 90), occupants=seated(kai=dict(expr='scared'), leo=dict(expr='scared'), mia=dict(expr='scared')))
        for ob in bpy.data.objects:
            if ob.type == 'LIGHT' and ob.data.type == 'SUN': ob.data.energy = .6
        point('fill', (-2, -3, -1), 300, (.3, .7, .75), 1.0)
        li = bpy.data.lights.new('surf', 'AREA'); li.energy = 1500; li.size = 10; li.color = (.7, .85, .9); o = kit.link(bpy.data.objects.new('surf', li)); o.location = (0, 0, -.2)
        cam((-1.5, -6.0, -2.6), (0, 0, -1.8), 24)
    elif name == 'shore':   # the cast safe on the snowy bank, the lake behind them, ripples where the car went down
        lake_set(0.0); near_shore(-2.0, road=False)
        BY = -4.2
        cast({'leo': dict(loc=(-.6, BY, .25), expr='worried', rot=(0, 0, -15), h=.95, arms={'arm_l': (-60, 0, 40), 'arm_r': (-60, 0, -40)}),
              'mia': dict(loc=(.15, BY - .1, .25), expr='worried', rot=(0, 0, 10)),
              'kai': dict(loc=(.85, BY + .1, .25), expr='neutral', rot=(0, 0, 25))})
        area('key', (1.5, BY - 3, 2.2), (0, BY, .7), 140, (1, .66, .4), 3); area('rim', (-1, BY + 3, 2), (0, BY, .8), 200, (.4, .6, 1), 3)
        point('torch', (-1.2, BY - .6, .5), 40, (1, .55, .25), .05)
        cam((.1, BY - 3.3, 1.0), (0, BY, .7), 32, 4.0)

def interior():
    """camera inside the car (car frame = world frame, level). water outside at the door middle (early) or at the windows (int_water)."""
    wz = {'int_water': .95, 'window_cu': .93}.get(name, .55)
    lake_set(wz - .42 + .42, hole=(-.82, -1.8, .82, 1.8)) if name != 'int_water' else lake_set(wz)
    over = {'cu_leo_door': dict(leo=dict(expr='scared', rot=(0, 0, -20), arms={'arm_r': (0, 95, 0), 'arm_l': (-80, 0, 30)})),
            'cu_mia': dict(mia=dict(expr='angry', arms={'arm_r': (-120, 0, 10), 'arm_l': (-40, 0, -10)})),
            'cu_kai': dict(kai=dict(expr='scared', arms={'arm_l': (0, -100, 0)})),
            'int_wide': dict(kai=dict(expr='scared', rot=(0, 0, -20)), leo=dict(expr='scared', rot=(0, 0, 20)), mia=dict(expr='worried')),
            'window_cu': dict(kai=None, mia=None),
            'int_water': dict(kai=dict(expr='scared'), leo=dict(expr='scared'), mia=dict(expr='scared'))}[name]
    root, ppl = car((0, 0, 0), (0, 0, 0), occupants=seated(**over))
    # cabin light: warm dome light + cool moonlight from outside
    point('dome', (0, -.4, 1.38), 35, (1, .72, .45), .15); point('dashglow', (0, .55, .95), 8, (1, .6, .3), .1)
    area('moon', (-3, -2, 3), (0, 0, 1), 200, (.45, .6, 1), 3)
    if name == 'window_cu':
        # red window hammer in Kai's reach, pointed at the lower front corner of his side window
        red = M('hammer', (.8, .05, .04), .35); steel = M('steel', (.7, .7, .72), .2, 1.0)
        hd = kit.link(bpy.data.objects.new('hammer', None)); hd.location = (-.58, .05, .95); hd.rotation_euler = (0, math.radians(-15), math.radians(10))
        cyl('handle', (.0, 0, -.09), .02, .18, red, parent=hd); box('head', (-.03, 0, .01), (.16, .045, .045), steel, .01, parent=hd)
        bpy.ops.mesh.primitive_cone_add(radius1=.028, depth=.05, location=(-.135, 0, 0), rotation=(0, -math.pi / 2, 0)); cn = bpy.context.object; cn.data.materials.append(steel); cn.parent = hd
    shots = {'int_wide': ((0, .62, 1.22), (0, -.9, .95), 18, None), 'cu_leo_door': ((-.1, .6, 1.15), (.38, 0, 1.05), 26, 2.8),
             'cu_mia': ((.0, .1, 1.12), (0, -.86, 1.0), 26, 2.8), 'cu_kai': ((-.05, .62, 1.13), (-.38, 0, 1.05), 26, 2.8),
             'window_cu': ((-.15, -.1, 1.08), (-.85, .25, .86), 26, 4.0), 'int_water': ((0, .62, 1.25), (0, -.9, .95), 18, None)}
    l, k, ln, fs = shots[name]; cam(l, k, ln, fs)

if name in ('splash', 'road', 'float_side', 'nose_down', 'roof', 'under', 'shore'): exterior()
else: interior()
sc.render.filepath = f'{OUT}/{name}.png'
bpy.ops.render.render(write_still=True)
print('WROTE', sc.render.filepath)
