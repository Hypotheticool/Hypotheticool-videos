"""Story Short: Leo fell through the ice. One Cycles still per plate (animated in 2D by ice_anim.py).
python3 ice_plate.py <plate> [res_scale]  -> ice/plates/<plate>.png
Pond plates (dusk, frozen pond, snowy bank, pines): pond_wide, pond_leo (Leo out on the ice), hole_leo (Leo in the hole), hole_cu (close-up),
  under_ice (looking up at the hole from under the ice), cu_mia_bank, cu_kai_bank, leo_climb (arms flat, kicking), leo_roll (rolling away),
  bank_group (Leo safe on the snow), cu_leo_ask, cu_mia_serious, long_way (the cast on the path around the pond)
Norway plates: norway (frozen mountain stream by a waterfall, skis by a hole), air_pocket (under stream ice: a silvery air pocket)
Hospital: hospital (heart-lung machine beside an ICU bed)"""
import sys, math, os, random
sys.path.insert(0, '/home/claude/b3d')
import bpy, kit
kit.CAST['kai']['hair_c'] = (.2, .065, .015)
from mathutils import Vector
name = sys.argv[1]; S = float(sys.argv[2]) if len(sys.argv) > 2 else 0.75
OUT = '/home/claude/b3d/ice/plates'; os.makedirs(OUT, exist_ok=True)
W, H = int(1080 * S), int(1920 * S)
sc = kit.reset(res=(W, H), samples=int(os.environ.get('SAMPLES', 48)))
sc.cycles.adaptive_threshold = 0.03; sc.cycles.max_bounces = 6; sc.cycles.diffuse_bounces = 3; sc.cycles.transmission_bounces = 6

def area(nm, loc, aim, energy, color=(1, 1, 1), size=2.0):
    li = bpy.data.lights.new(nm, 'AREA'); li.energy = energy; li.color = color; li.size = size
    o = kit.link(bpy.data.objects.new(nm, li)); o.location = loc
    o.rotation_euler = (Vector(aim) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler(); o.visible_glossy = False; o.visible_transmission = False; return o

def point(nm, loc, energy, color, radius=.05):
    li = bpy.data.lights.new(nm, 'POINT'); li.energy = energy; li.color = color; li.shadow_soft_size = radius
    o = kit.link(bpy.data.objects.new(nm, li)); o.location = loc; return o

def flat_world(col, strength=1.0):
    w = bpy.data.worlds.new('w'); sc.world = w; nt, N, L = kit.nodes(w)
    o = N.new('ShaderNodeOutputWorld'); bg = N.new('ShaderNodeBackground'); bg.inputs['Color'].default_value = (*col, 1)
    bg.inputs['Strength'].default_value = strength; L.new(bg.outputs[0], o.inputs['Surface'])

def M(nm, col, rough=.5, metal=0.0, coat=0.0):
    return kit.mat_principled(nm, col, rough=rough, metal=metal, coat=coat)

def box(nm, loc, size, mat, bevel=.01, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(location=loc); o = bpy.context.object; o.name = nm; o.scale = (size[0] / 2, size[1] / 2, size[2] / 2)
    o.rotation_euler = rot; bpy.ops.object.transform_apply(scale=True); o.data.materials.append(mat)
    if bevel: b = o.modifiers.new('b', 'BEVEL'); b.width = bevel; b.segments = 3
    return o

def cyl(nm, loc, r, depth, mat, rot=(0, 0, 0), verts=48):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=depth, location=loc, rotation=rot, vertices=verts); o = bpy.context.object; o.name = nm
    o.data.materials.append(mat); bpy.ops.object.shade_smooth(); return o

def rod(nm, p0, p1, r, mat, verts=16):
    v = Vector(p1) - Vector(p0); mid = (Vector(p0) + Vector(p1)) / 2
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=v.length, location=mid, vertices=verts); o = bpy.context.object; o.name = nm
    o.rotation_euler = v.to_track_quat('Z', 'Y').to_euler(); o.data.materials.append(mat); bpy.ops.object.shade_smooth(); return o

def tube(nm, pts, r, mat):
    """smooth tube along points (bezier curve with bevel)"""
    cu = bpy.data.curves.new(nm, 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = r; cu.bevel_resolution = 4
    sp = cu.splines.new('BEZIER'); sp.bezier_points.add(len(pts) - 1)
    for p, q in zip(sp.bezier_points, pts): p.co = q; p.handle_left_type = p.handle_right_type = 'AUTO'
    o = kit.link(bpy.data.objects.new(nm, cu)); cu.materials.append(mat); return o

def cam(loc, look, lens, fstop=None, focus=None):
    c, t = kit.camera(loc, look, lens=lens)
    if fstop:
        c.data.dof.use_dof = True; c.data.dof.focus_distance = focus or (Vector(loc) - Vector(look)).length; c.data.dof.aperture_fstop = fstop
    return c

def haze(density, loc, scale, col=(.8, .85, 1)):
    bpy.ops.mesh.primitive_cube_add(location=loc); v = bpy.context.object; v.scale = scale; v.name = 'haze'
    m = bpy.data.materials.new('haze'); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); vs = N.new('ShaderNodeVolumeScatter')
    vs.inputs['Density'].default_value = density; vs.inputs['Anisotropy'].default_value = .55; vs.inputs['Color'].default_value = (*col, 1)
    L.new(vs.outputs[0], o.inputs['Volume']); v.data.materials.append(m); return v

def cast(spec, y=0.0):
    """spec: who -> dict(loc, expr, rot (deg xyz), arms {arm: (rx, ry, rz) deg}, h)"""
    out = {}
    for who, d in spec.items():
        root, parts = kit.character(who, loc=d['loc'], height=d.get('h', 1.0))
        rx, ry, rz = d.get('rot', (0, 0, 0)); root.rotation_euler = (math.radians(rx), math.radians(ry), math.radians(rz))
        parts['face_mat'].node_tree.nodes['expr'].outputs[0].default_value = kit.EXPRS.index(d.get('expr', 'neutral'))
        for arm, r in d.get('arms', {}).items(): parts[arm].rotation_euler = tuple(math.radians(a) for a in r)
        out[who] = (root, parts)
    return out

# ------------------------------------------------------------------ materials
def snow_mat(nm='snowfield'):
    m = bpy.data.materials.new(nm); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled')
    bs.inputs['Base Color'].default_value = (.86, .9, .97, 1); bs.inputs['Roughness'].default_value = .6
    bs.inputs['Subsurface Weight'].default_value = .35; bs.inputs['Subsurface Radius'].default_value = (.8, .9, 1)
    tc = N.new('ShaderNodeTexCoord'); nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 3; nz.inputs['Detail'].default_value = 10
    L.new(tc.outputs['Object'], nz.inputs[0]); nz2 = N.new('ShaderNodeTexNoise'); nz2.inputs['Scale'].default_value = 90; L.new(tc.outputs['Object'], nz2.inputs[0])
    mx = N.new('ShaderNodeMath'); mx.operation = 'ADD'; L.new(nz.outputs['Fac'], mx.inputs[0]); L.new(nz2.outputs['Fac'], mx.inputs[1])
    bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = .35; L.new(mx.outputs[0], bp.inputs['Height']); L.new(bp.outputs[0], bs.inputs['Normal'])
    # sparkle: tiny glints
    vo = N.new('ShaderNodeTexVoronoi'); vo.inputs['Scale'].default_value = 900; L.new(tc.outputs['Object'], vo.inputs[0])
    gl = N.new('ShaderNodeMapRange'); gl.inputs['From Min'].default_value = .04; gl.inputs['From Max'].default_value = 0.0; L.new(vo.outputs['Distance'], gl.inputs[0])
    L.new(gl.outputs[0], bs.inputs['Specular IOR Level'])
    L.new(bs.outputs[0], o.inputs[0]); return m

def ice_mat(nm='pondice', white=0.0):
    """new, clear 'black' ice (IOR 1.31): glossy, transmissive, with trapped bubbles, fine surface scratches and patches of powder snow"""
    m = bpy.data.materials.new(nm); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled')
    bs.inputs['Base Color'].default_value = (.25, .4, .45, 1); bs.inputs['IOR'].default_value = 1.31; bs.inputs['Transmission Weight'].default_value = .7
    tc = N.new('ShaderNodeTexCoord')
    sc_ = N.new('ShaderNodeTexNoise'); sc_.inputs['Scale'].default_value = 40; sc_.inputs['Detail'].default_value = 14; L.new(tc.outputs['Object'], sc_.inputs[0])
    rr = N.new('ShaderNodeMapRange'); rr.inputs['To Min'].default_value = .02; rr.inputs['To Max'].default_value = .12; L.new(sc_.outputs['Fac'], rr.inputs[0]); L.new(rr.outputs[0], bs.inputs['Roughness'])
    # powder snow drifts on top
    dn = N.new('ShaderNodeTexNoise'); dn.inputs['Scale'].default_value = .5; dn.inputs['Detail'].default_value = 8; L.new(tc.outputs['Object'], dn.inputs[0])
    dm = N.new('ShaderNodeMapRange'); dm.inputs['From Min'].default_value = .56 - white; dm.inputs['From Max'].default_value = .66 - white; L.new(dn.outputs['Fac'], dm.inputs[0])
    snow = N.new('ShaderNodeBsdfPrincipled'); snow.inputs['Base Color'].default_value = (.85, .9, .96, 1); snow.inputs['Roughness'].default_value = .7
    mix = N.new('ShaderNodeMixShader'); L.new(dm.outputs[0], mix.inputs[0]); L.new(bs.outputs[0], mix.inputs[1]); L.new(snow.outputs[0], mix.inputs[2])
    bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = .08; L.new(sc_.outputs['Fac'], bp.inputs['Height']); L.new(bp.outputs[0], bs.inputs['Normal'])
    L.new(mix.outputs[0], o.inputs[0]); return m

def dark_water(nm='pondwater'):
    m = bpy.data.materials.new(nm); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled')
    bs.inputs['Base Color'].default_value = (.003, .012, .016, 1); bs.inputs['Roughness'].default_value = .03; bs.inputs['IOR'].default_value = 1.333
    tc = N.new('ShaderNodeTexCoord'); wv = N.new('ShaderNodeTexWave'); wv.wave_type = 'RINGS'; wv.inputs['Scale'].default_value = 3.5; wv.inputs['Distortion'].default_value = 4
    L.new(tc.outputs['Object'], wv.inputs[0]); bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = .25; L.new(wv.outputs['Fac'], bp.inputs['Height']); L.new(bp.outputs[0], bs.inputs['Normal'])
    L.new(bs.outputs[0], o.inputs[0]); return m

def pine(loc, h, seed=0):
    r = random.Random(seed)
    trunk = M('trunk', (.08, .05, .03), .9); cyl(f'tr{seed}', (loc[0], loc[1], loc[2] + h * .1), h * .03, h * .2, trunk, verts=10)
    m = bpy.data.materials.get('pinesnow')
    if m is None:
        m = bpy.data.materials.new('pinesnow'); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial')
        g = N.new('ShaderNodeBsdfPrincipled'); g.inputs['Base Color'].default_value = (.015, .045, .035, 1); g.inputs['Roughness'].default_value = .85
        s = N.new('ShaderNodeBsdfPrincipled'); s.inputs['Base Color'].default_value = (.85, .9, .96, 1); s.inputs['Roughness'].default_value = .6
        ge = N.new('ShaderNodeNewGeometry'); sep = N.new('ShaderNodeSeparateXYZ'); L.new(ge.outputs['Normal'], sep.inputs[0])
        nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 12; tc = N.new('ShaderNodeTexCoord'); L.new(tc.outputs['Object'], nz.inputs[0])
        ad = N.new('ShaderNodeMath'); ad.operation = 'ADD'; L.new(sep.outputs['Z'], ad.inputs[0]); L.new(nz.outputs['Fac'], ad.inputs[1])
        mr = N.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value = .95; mr.inputs['From Max'].default_value = 1.15; L.new(ad.outputs[0], mr.inputs[0])
        mx = N.new('ShaderNodeMixShader'); L.new(mr.outputs[0], mx.inputs[0]); L.new(g.outputs[0], mx.inputs[1]); L.new(s.outputs[0], mx.inputs[2]); L.new(mx.outputs[0], o.inputs[0])
    for k in range(5):
        z = loc[2] + h * (.18 + k * .16); rad = h * (.32 - k * .055)
        bpy.ops.mesh.primitive_cone_add(radius1=rad, radius2=0, depth=h * .3, location=(loc[0], loc[1], z + h * .1), vertices=14)
        c = bpy.context.object; c.rotation_euler = (r.uniform(-.04, .04), r.uniform(-.04, .04), r.uniform(0, 6)); c.data.materials.append(m)

# ------------------------------------------------------------------ the pond set (1 unit = 1 m; characters ~1 m tall, cartoon scale)
POND_R = 9.0; HOLE = (0.0, 3.0)
def pond_set(hole=True, sun_el=1.5, sun_rot=20, leo_spot=None):
    sun = kit.sky(sun_el, sun_rot, strength=.09, sun_lamp_energy=3.0, dust=2.0)
    # ice sheet, 0.1 m (4 in) thick, top at z = 0
    bpy.ops.mesh.primitive_cylinder_add(radius=POND_R, depth=.1, location=(0, 0, -.05), vertices=160); ice = bpy.context.object; ice.name = 'ice'
    ice.data.materials.append(ice_mat())
    if hole:
        bpy.ops.mesh.primitive_cylinder_add(radius=.5, depth=.4, location=(HOLE[0], HOLE[1], 0), vertices=11); cutter = bpy.context.object
        r = random.Random(4)
        for v in cutter.data.vertices: v.co.x *= r.uniform(.8, 1.25); v.co.y *= r.uniform(.75, 1.2)
        bo = ice.modifiers.new('hole', 'BOOLEAN'); bo.object = cutter; bo.operation = 'DIFFERENCE'
        bpy.context.view_layer.objects.active = ice; bpy.ops.object.modifier_apply(modifier='hole'); bpy.data.objects.remove(cutter)
        # broken slabs floating in and tilted at the edge
        shard = ice_mat('shard', white=-.15)
        for k in range(7):
            a = k / 7 * 2 * math.pi + r.uniform(-.3, .3); d = r.uniform(.2, .48)
            box(f'shard{k}', (HOLE[0] + d * math.cos(a), HOLE[1] + d * math.sin(a), -.03), (r.uniform(.12, .3), r.uniform(.1, .25), .1), shard, .006,
                rot=(r.uniform(-.5, .5), r.uniform(-.5, .5), a))
    # dark water just under the ice (visible in the hole)
    bpy.ops.mesh.primitive_circle_add(radius=POND_R, fill_type='NGON', location=(0, 0, -.06)); wat = bpy.context.object; wat.data.materials.append(dark_water())
    bpy.ops.mesh.primitive_cylinder_add(radius=POND_R + .5, depth=4, location=(0, 0, -2.1)); bed = bpy.context.object; bed.name = 'pondbed'; bed.data.materials.append(M('bed', (.004, .01, .012), .9))
    # snowy bank: an annulus around the pond plus soft mounds further out
    sn = snow_mat()
    bpy.ops.mesh.primitive_circle_add(radius=60, fill_type='NGON', location=(0, 0, .0)); g = bpy.context.object
    bpy.ops.mesh.primitive_cylinder_add(radius=POND_R - .02, depth=1, location=(0, 0, 0), vertices=160); cutter = bpy.context.object
    bo = g.modifiers.new('cut', 'BOOLEAN'); bo.object = cutter; bo.operation = 'DIFFERENCE'
    bpy.context.view_layer.objects.active = g; bpy.ops.object.modifier_apply(modifier='cut'); bpy.data.objects.remove(cutter)
    g.data.materials.append(sn); g.location.z = .04
    r = random.Random(7)
    for k in range(26):
        a = r.uniform(0, 2 * math.pi); d = r.uniform(POND_R + 1.5, POND_R + 7)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=(d * math.cos(a), d * math.sin(a), -.4)); mnd = bpy.context.object
        mnd.scale = (r.uniform(1.5, 3.5), r.uniform(1.5, 3.5), r.uniform(.5, .9)); mnd.data.materials.append(sn); bpy.ops.object.shade_smooth()
    # pines all around (denser behind the pond = +Y)
    for k in range(70):
        a = r.uniform(0, 2 * math.pi); d = r.uniform(POND_R + 3, POND_R + 26)
        if math.sin(a) < -.5 and d < POND_R + 9: continue   # keep the camera side open
        pine((d * math.cos(a), d * math.sin(a), 0), r.uniform(3.5, 8), k)
    haze(.012, (0, 0, 4), (45, 45, 5), (.75, .8, 1))
    return sun

def pond_plate():
    spec = {}; up = (0, 0, 0)
    if name == 'pond_wide':
        pond_set(hole=False)
        spec = {'leo': dict(loc=(-.5, -5.6, 0), expr='happy', rot=(0, 0, 165), arms={'arm_l': (0, -35, 0), 'arm_r': (0, 35, 0)}),
                'kai': dict(loc=(1.0, -POND_R - .6, .04), expr='worried', rot=(0, 0, 195)), 'mia': dict(loc=(.1, -POND_R - .4, .04), expr='worried', rot=(0, 0, 175),
                arms={'arm_r': (-80, 30, 0)})}
        cast(spec); area('keyL', (-2, -2, 3), (-.5, 2.5, .6), 60, (1, .7, .45), 2)
        area('rimK', (3, -6, 3), (1, -10, .6), 80, (1, .6, .35), 2)
        cam((1.0, -POND_R - 2.8, 1.1), (-.4, -5.6, .5), 32, 5.6, 6.0)
    elif name == 'pond_leo':
        pond_set(hole=False)
        cast({'leo': dict(loc=(HOLE[0], HOLE[1], 0), expr='worried', rot=(0, 0, -15), arms={'arm_l': (0, -45, 0), 'arm_r': (0, 45, 0)})})
        area('key', (1.5, 1.0, 1.8), (0, 3, .6), 70, (1, .7, .45), 1.5); area('rim', (-1, 5.5, 1.6), (0, 3, .7), 50, (.4, .6, 1), 1.5)
        cam((.5, 1.1, .55), (0, 3.0, .45), 32, 4.0)
    elif name in ('hole_leo', 'hole_cu'):
        pond_set(hole=True)
        cast({'leo': dict(loc=(HOLE[0], HOLE[1], -.42), expr='scared', rot=(0, 0, -12), arms={'arm_l': (20, -125, 0), 'arm_r': (20, 125, 0)})})
        area('key', (1.2, .9, 1.6), (0, 3, .1), 80, (1, .7, .45), 1.5); area('rim', (-1.2, 5, 1.4), (0, 3, .1), 60, (.4, .6, 1), 1.5)
        if name == 'hole_leo': cam((.9, -.2, .9), (0, 3.0, .0), 30, 4.0)
        else: cam((.25, 1.95, .2), (0, 3.0, .17), 45, 2.2)
    elif name in ('under_ice', 'under_empty'):
        pond_set(hole=True)
        if name == 'under_ice': cast({'leo': dict(loc=(HOLE[0], HOLE[1], -.42), expr='scared', rot=(0, 0, -12), arms={'arm_l': (20, -125, 0), 'arm_r': (20, 125, 0)},
              arms_=None)} if False else {'leo': dict(loc=(HOLE[0], HOLE[1], -.42), expr='scared', rot=(0, 0, -12), arms={'arm_l': (20, -125, 0), 'arm_r': (20, 125, 0)})})
        keep = ('ice', 'leo', 'shard')
        for ob in list(bpy.data.objects):
            if ob.type in ('MESH',) and not (ob.name.startswith(keep) or (ob.parent and ob.parent.name.startswith('leo')) or ob.name.startswith('leo')):
                bpy.data.objects.remove(ob)
        for ob in list(bpy.data.objects):
            if ob.type == 'LIGHT' and ob.data.type == 'SUN': ob.data.energy = 1.0
        flat_world((.02, .08, .1), 1.0)
        dk = bpy.data.materials.new('ice_under'); nt, N, L = kit.nodes(dk); o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled')
        bs.inputs['Base Color'].default_value = (.03, .1, .12, 1); bs.inputs['Roughness'].default_value = .25; bs.inputs['Subsurface Weight'].default_value = .0
        tc = N.new('ShaderNodeTexCoord'); nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 6; nz.inputs['Detail'].default_value = 10; L.new(tc.outputs['Object'], nz.inputs[0])
        bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = .5; L.new(nz.outputs['Fac'], bp.inputs['Height']); L.new(bp.outputs[0], bs.inputs['Normal'])
        L.new(bs.outputs[0], o.inputs[0])
        for ob in bpy.data.objects:
            if ob.name.startswith(('ice', 'shard')): ob.data.materials[0] = dk
        # the bright winter dusk seen through the hole
        bpy.ops.mesh.primitive_circle_add(radius=6, fill_type='NGON', location=(HOLE[0], HOLE[1], 2.5)); sky_ = bpy.context.object; sky_.data.materials.append(kit.mat_emit('dusk', (1, .62, .35), 6))
        bpy.ops.mesh.primitive_cube_add(location=(0, 0, -2.2)); v = bpy.context.object; v.scale = (12, 12, 2.15)
        m = bpy.data.materials.new('uw'); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); vs = N.new('ShaderNodeVolumeScatter')
        vs.inputs['Color'].default_value = (.45, .8, .85, 1); vs.inputs['Density'].default_value = .09; vs.inputs['Anisotropy'].default_value = .7
        ab = N.new('ShaderNodeVolumeAbsorption'); ab.inputs['Color'].default_value = (.35, .7, .75, 1); ab.inputs['Density'].default_value = .25
        ad = N.new('ShaderNodeAddShader'); L.new(vs.outputs[0], ad.inputs[0]); L.new(ab.outputs[0], ad.inputs[1]); L.new(ad.outputs[0], o.inputs['Volume']); v.data.materials.append(m)
        s_ = bpy.data.lights.new('shaft', 'SPOT'); s_.energy = 3000; s_.spot_size = math.radians(14); s_.color = (1, .78, .55); s_.shadow_soft_size = .2
        so = kit.link(bpy.data.objects.new('shaft', s_)); so.location = (HOLE[0] + .5, HOLE[1] + .6, 2.2); so.rotation_euler = (Vector((HOLE[0], HOLE[1], -4)) - so.location).to_track_quat('-Z', 'Y').to_euler()
        point('fillUW', (1.5, 1.0, -1.2), 60, (.3, .75, .8), .5)
        cam((.7, 1.9, -1.9), (0, 3.0, .0), 20, None)
    elif name in ('cu_mia_bank', 'cu_kai_bank', 'cu_leo_ask', 'cu_mia_serious', 'bank_group'):
        pond_set(hole=True)
        BY = -POND_R - 1.0
        if name == 'cu_mia_bank':
            cast({'mia': dict(loc=(0, BY, .04), expr='scared', rot=(0, 0, 165), arms={'arm_r': (0, 105, 0), 'arm_l': (0, -30, 0)}),
                  'kai': dict(loc=(.75, BY - .3, .04), expr='worried', rot=(0, 0, 180))})
            area('key', (-1.2, BY - 1.6, 1.6), (0, BY, .8), 70, (1, .7, .45), 1.5); area('rim', (.5, BY + 2, 1.6), (0, BY, .8), 60, (.4, .6, 1), 1.5)
            cam((-.3, BY + 1.6, .8), (0, BY, .72), 40, 2.4)
        elif name == 'cu_kai_bank':
            cast({'kai': dict(loc=(0, BY, .04), expr='angry', rot=(0, 0, 195), arms={'arm_r': (-160, 0, 10), 'arm_l': (-160, 0, -10)}),
                  'mia': dict(loc=(-.7, BY - .3, .04), expr='worried', rot=(0, 0, 180))})
            area('key', (1.2, BY - 1.6, 1.6), (0, BY, .8), 70, (1, .7, .45), 1.5); area('rim', (-.5, BY + 2, 1.6), (0, BY, .8), 60, (.4, .6, 1), 1.5)
            cam((.3, BY + 1.6, .8), (0, BY, .72), 40, 2.4)
        elif name in ('cu_leo_ask', 'cu_mia_serious', 'bank_group'):
            BY2 = -POND_R - 1.6
            cast({'leo': dict(loc=(-.45, BY2, .04), expr='surprised' if name == 'cu_leo_ask' else 'worried', rot=(0, 0, -25), h=.95,
                              arms={'arm_l': (-60, 0, 40), 'arm_r': (-60, 0, -40)}),
                  'mia': dict(loc=(.4, BY2 - .1, .04), expr='worried' if name == 'cu_mia_serious' else 'neutral', rot=(0, 0, 25)),
                  'kai': dict(loc=(.05, BY2 + .55, .04), expr='worried', rot=(0, 0, 0))})
            area('key', (1.5, BY2 - 2, 2), (0, BY2, .7), 90, (1, .68, .42), 2); area('rim', (-1, BY2 + 2.5, 1.8), (0, BY2, .8), 70, (.4, .6, 1), 2)
            point('lantern', (.9, BY2 - .6, .25), 25, (1, .55, .25), .05)
            shots = {'bank_group': ((0, BY2 - 2.6, 1.0), (0, BY2, .65), 30, 4.0), 'cu_leo_ask': ((-.6, BY2 - 1.2, .85), (-.45, BY2, .78), 50, 2.0),
                     'cu_mia_serious': ((.55, BY2 - 1.25, .88), (.4, BY2, .8), 50, 2.0)}
            l, k, ln, fs = shots[name]; cam(l, k, ln, fs)
    elif name == 'leo_climb':
        pond_set(hole=True)
        # Leo flat on his chest, head away from the hole (back toward the way he came = -Y), arms forward on the ice, legs in the water behind
        cast({'leo': dict(loc=(HOLE[0], HOLE[1] + .1, -.03), expr='worried', rot=(68, 0, 0), arms={'arm_l': (165, 0, -22), 'arm_r': (165, 0, 22)},
                          )})
        area('key', (1.5, 1.2, 1.4), (0, 2.4, .1), 70, (1, .7, .45), 1.5); area('rim', (-1.5, 4.5, 1.2), (0, 2.6, .1), 60, (.4, .6, 1), 1.5)
        cam((.9, .75, .42), (0, 2.55, .12), 30, 4.0)
    elif name == 'leo_roll':
        pond_set(hole=True)
        cast({'leo': dict(loc=(HOLE[0] - .1, HOLE[1] - 1.5, .1), expr='worried', rot=(90, 0, 90), arms={'arm_l': (0, -10, 0), 'arm_r': (0, 10, 0)})})
        area('key', (1.5, .5, 1.6), (0, 1.5, .1), 70, (1, .7, .45), 1.5); area('rim', (-1.5, 3.5, 1.2), (0, 1.6, .1), 60, (.4, .6, 1), 1.5)
        cam((.4, -1.2, .95), (.25, 1.5, .1), 32, 4.0)
    elif name == 'long_way':
        pond_set(hole=True, sun_el=1.0)
        BY = -POND_R - 2.4
        cast({'kai': dict(loc=(-1.6, BY, .04), expr='smirk', rot=(0, 0, -95), arms={'arm_l': (20, 0, 0), 'arm_r': (-20, 0, 0)}),
              'leo': dict(loc=(-.6, BY - .2, .04), expr='happy', rot=(0, 0, -95), h=.95, arms={'arm_l': (-20, 0, 0), 'arm_r': (20, 0, 0)}),
              'mia': dict(loc=(.4, BY - .05, .04), expr='happy', rot=(0, 0, -95), arms={'arm_l': (20, 0, 0), 'arm_r': (-20, 0, 0)})})
        area('key', (0, BY - 3, 2.2), (0, BY, .7), 110, (1, .66, .4), 3); area('rim', (0, BY + 3, 2), (0, BY, .8), 80, (.4, .6, 1), 3)
        cam((-3.4, BY - 1.6, .95), (-.5, BY, .62), 32, 5.6, 3.2)

# ------------------------------------------------------------------ Norway, May 1999: a frozen mountain stream below a waterfall (daylight, overcast)
def norway_plate():
    kit.sky(8, 160, strength=.06, sun_lamp_energy=1.2, dust=1.5)
    sn = snow_mat()
    g = kit.terrain(size=90, height=1.0, scale=5, kind='snow', seed=2); g.data.materials[0] = sn
    for k, (x, h) in enumerate(((-55, 16), (55, 20))):
        t = kit.terrain(size=80, height=h, scale=2.0, kind='snow', seed=k + 3); t.location = (x, 30, -2)
    m2 = kit.terrain(size=220, height=55, scale=1.6, kind='snow', seed=5); m2.location = (0, 130, -10)
    # the stream: a continuous winding ribbon of new ice, slightly sunk into the snow, with a dark open hole
    cu = bpy.data.curves.new('stream', 'CURVE'); cu.dimensions = '3D'; cu.extrude = .05; cu.bevel_depth = 0
    sp = cu.splines.new('BEZIER'); pts = [(0, -6, .25), (.6, -1, .25), (-.5, 4, .25), (.8, 10, .25), (-.6, 18, .3), (0, 26, .35)]
    sp.bezier_points.add(len(pts) - 1)
    for p_, q in zip(sp.bezier_points, pts): p_.co = q; p_.handle_left_type = p_.handle_right_type = 'AUTO'
    st = kit.link(bpy.data.objects.new('stream', cu)); cu.materials.append(ice_mat('streamice', white=.05))
    cu.bevel_mode = 'PROFILE'; cu.bevel_depth = 1.2; cu.bevel_resolution = 0
    st.scale = (1, 1, 1)
    # flatten: a profile curve-free trick: squash the bevel to a ribbon
    st.scale.z = .04; st.location.z = .22
    bpy.ops.mesh.primitive_circle_add(radius=.55, fill_type='NGON', location=(.45, 0.2, .275), vertices=9); hl = bpy.context.object; hl.data.materials.append(dark_water())
    rock = kit.mat_pbr('rock', 'wet_rock')
    for k in range(9):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=1, location=(-2.2 + k * .55, 26.5 + (k % 2) * .4, .8)); rk = bpy.context.object
        rk.scale = (.8, .6, 1.4 + .5 * (k % 3)); rk.data.materials.append(rock)
    falls = kit.mat_pbr('ice', 'falls_ice')
    for k in range(6): cyl(f'icicle{k}', (-1.3 + k * .5, 26.0, 2.0), .2 + .06 * (k % 2), 3.6, falls, verts=12)
    ski = M('ski', (.75, .1, .08), .3, coat=.6)
    box('ski1', (1.9, -.6, .32), (.08, 1.7, .02), ski, .01, rot=(0, 0, .4)); box('ski2', (2.2, -.3, .32), (.08, 1.7, .02), ski, .01, rot=(0, 0, .2))
    rod('pole', (2.4, -1.2, .3), (2.9, .1, .35), .012, M('pole', (.1, .1, .1), .4, 1))
    for k in range(40):
        r = random.Random(k); x = r.choice((-1, 1)) * r.uniform(4, 25); y = r.uniform(2, 50)
        pine((x, y, 0), r.uniform(3, 7), k + 100)
    haze(.01, (0, 40, 6), (60, 60, 8), (.85, .9, 1))
    area('fill', (4, -4, 4), (0, 2, 0), 200, (1, .75, .5), 6)
    cam((2.8, -6.5, 2.0), (.2, 4, .6), 26, 8, 7.0)

def air_pocket_plate():
    flat_world((.3, .45, .5), 1.6)
    ic = ice_mat('ceilice', white=.1)
    box('ceiling', (0, 0, .1), (30, 30, .2), ic, 0)
    # air pocket trapped under the ice: from below it looks like a silver mirror (total internal reflection), with bubbles
    air = bpy.data.materials.new('air'); nt, N, L = kit.nodes(air); o = N.new('ShaderNodeOutputMaterial'); gl = N.new('ShaderNodeBsdfGlass')
    gl.inputs['IOR'].default_value = 1 / 1.333; gl.inputs['Roughness'].default_value = .02; L.new(gl.outputs[0], o.inputs[0])
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=(.3, 1.2, -.02), segments=64, ring_count=32); ap = bpy.context.object; ap.scale = (1.6, 1.1, .12)
    ap.data.materials.append(air); bpy.ops.object.shade_smooth()
    for k in range(40):
        r = random.Random(k); bpy.ops.mesh.primitive_uv_sphere_add(radius=r.uniform(.01, .05), location=(r.uniform(-3, 3), r.uniform(-1, 4), r.uniform(-.12, -.03)))
        b = bpy.context.object; b.scale.z = .5; b.data.materials.append(air)
    bpy.ops.mesh.primitive_cube_add(location=(0, 0, -3.0)); v = bpy.context.object; v.scale = (15, 15, 3.0)
    m = bpy.data.materials.new('uw'); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); vs = N.new('ShaderNodeVolumePrincipled')
    vs.inputs['Color'].default_value = (.2, .5, .55, 1); vs.inputs['Density'].default_value = .3; vs.inputs['Anisotropy'].default_value = .7
    vs.inputs['Absorption Color'].default_value = (.15, .4, .45, 1); L.new(vs.outputs[0], o.inputs['Volume']); v.data.materials.append(m)
    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, -5.9)); bd = bpy.context.object; bd.data.materials.append(kit.mat_pbr('rock', 'stones'))
    li = bpy.data.lights.new('day', 'SUN'); li.energy = 9.0; li.color = (.85, .92, 1); li.angle = math.radians(30)
    kit.link(bpy.data.objects.new('day', li)).rotation_euler = (math.radians(15), 0, math.radians(20))
    cam((-.4, -2.4, -1.4), (.3, 1.4, -.05), 24)

# ------------------------------------------------------------------ hospital: ICU bed + heart-lung (bypass) machine
def hospital_plate():
    flat_world((.01, .015, .02), 1.0)
    box('floor', (0, 0, -.02), (12, 12, .04), M('vinyl', (.12, .16, .17), .3), 0)
    box('wall', (0, 2.5, 1.6), (12, .1, 3.2), M('wall', (.16, .22, .24), .8), 0)
    # bed with a blanket over a body shape (no face shown)
    frame = M('bedframe', (.7, .72, .74), .3, 1)
    box('mattress', (-.6, .6, .62), (2.0, .95, .2), M('sheet', (.82, .85, .88), .7), .04)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=(-.75, .6, .78)); bl = bpy.context.object; bl.scale = (.85, .38, .14); bl.data.materials.append(M('blanket', (.28, .45, .62), .85)); bpy.ops.object.shade_smooth()
    box('pillow', (.25, .6, .78), (.4, .6, .1), M('pillow', (.9, .92, .94), .7), .04)
    for x in (-1.5, .3):
        for y in (.2, 1.0): rod(f'leg{x}{y}', (x, y, 0), (x, y, .52), .025, frame)
    # heart-lung machine: steel console on wheels, 4 roller-pump heads with clear covers, an oxygenator, a warm control screen
    steel = M('console', (.6, .62, .64), .35, .8)
    box('console', (1.55, .1, .55), (1.1, .7, .7), steel, .02)
    for k in range(4):
        cyl(f'pump{k}', (1.15 + k * .27, -.26, .95), .11, .12, M('pumpbody', (.15, .16, .17), .4, .5), rot=(math.pi / 2, 0, 0))
        cyl(f'pumpcov{k}', (1.15 + k * .27, -.33, .95), .115, .03, kit.mat_pbr('glass', f'cov{k}'), rot=(math.pi / 2, 0, 0))
    cyl('oxygenator', (2.05, -.05, 1.35), .09, .45, kit.mat_pbr('plastic', 'oxy'))
    rod('mast', (1.9, .2, .9), (1.9, .2, 2.1), .025, steel); box('screen', (1.9, .05, 1.85), (.5, .05, .36), M('bezel', (.05, .05, .06), .4), .01)
    box('screen_glow', (1.9, .02, 1.85), (.44, .01, .3), kit.mat_emit('screen', (1, .62, .25), 3), 0)
    blood = M('blood_tube', (.32, .01, .02), .15); blood.node_tree.nodes['Principled BSDF'].inputs['Coat Weight'].default_value = 1.0
    tube('line_a', [(1.2, -.3, .95), (.9, -.4, .9), (.4, -.1, .8), (.0, .3, .78)], .018, blood)
    tube('line_b', [(1.9, -.15, 1.2), (1.3, -.6, 1.05), (.6, -.3, .85), (-.1, .45, .8)], .018, blood)
    box('monitor', (-1.9, 1.9, 1.7), (.6, .06, .42), M('bezel2', (.05, .05, .06), .4), .01)
    box('monitor_glow', (-1.9, 1.86, 1.7), (.54, .01, .36), kit.mat_emit('mon', (.2, 1, .6), 2), 0)
    area('lamp', (0, -.5, 2.8), (0, .3, .6), 160, (1, .78, .55), 1.2); area('cool', (-3, -2, 2), (0, .5, .8), 60, (.4, .6, 1), 3)
    haze(.03, (0, 0, 1.4), (4, 4, 1.5), (1, .9, .8))
    cam((2.7, -3.0, 1.55), (.7, .3, .9), 30, 4.0)

if name.startswith(('pond', 'hole', 'under', 'cu_', 'leo_', 'bank', 'long')): pond_plate()
elif name == 'norway': norway_plate()
elif name == 'hospital': hospital_plate()
sc.render.filepath = f'{OUT}/{name}.png'
bpy.ops.render.render(write_still=True)
print('WROTE', sc.render.filepath)
