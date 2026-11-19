"""Hypotheticool 3D kit (Blender/Cycles): world, black hole, astronaut, lights, camera helpers."""
import bpy, math, bmesh
from mathutils import Vector

def reset(res=(720, 1280), fps=24, samples=16):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.fps = fps
    sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'
    sc.cycles.samples = samples; sc.cycles.use_denoising = True; sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    sc.cycles.max_bounces = 4; sc.cycles.diffuse_bounces = 2; sc.cycles.glossy_bounces = 2; sc.cycles.transmission_bounces = 2
    sc.cycles.use_adaptive_sampling = True
    sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'
    sc.render.film_transparent = False
    return sc

def nodes(mat):
    mat.use_nodes = True; nt = mat.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    return nt, nt.nodes, nt.links

# ------------------------------------------------------------------ world: stars + faint nebula
def world_procedural():
    sc = bpy.context.scene; w = bpy.data.worlds.new('space'); sc.world = w
    nt, N, L = nodes(w)
    out = N.new('ShaderNodeOutputWorld'); bg = N.new('ShaderNodeBackground')
    tc = N.new('ShaderNodeTexCoord')
    vor = N.new('ShaderNodeTexVoronoi'); vor.inputs['Scale'].default_value = 420
    L.new(tc.outputs['Generated'], vor.inputs['Vector'])
    st = N.new('ShaderNodeMapRange'); st.inputs['From Min'].default_value = 0.0; st.inputs['From Max'].default_value = 0.035
    st.inputs['To Min'].default_value = 18.0; st.inputs['To Max'].default_value = 0.0; st.clamp = True
    L.new(vor.outputs['Distance'], st.inputs['Value'])
    vor2 = N.new('ShaderNodeTexVoronoi'); vor2.inputs['Scale'].default_value = 90
    L.new(tc.outputs['Generated'], vor2.inputs['Vector'])
    st2 = N.new('ShaderNodeMapRange'); st2.inputs['From Min'].default_value = 0.0; st2.inputs['From Max'].default_value = 0.02
    st2.inputs['To Min'].default_value = 14.0; st2.inputs['To Max'].default_value = 0.0; st2.clamp = True
    L.new(vor2.outputs['Distance'], st2.inputs['Value'])
    gate = N.new('ShaderNodeMath'); gate.operation = 'GREATER_THAN'; gate.inputs[1].default_value = 0.93
    L.new(vor2.outputs['Color'], gate.inputs[0])
    m2 = N.new('ShaderNodeMath'); m2.operation = 'MULTIPLY'; L.new(st2.outputs[0], m2.inputs[0]); L.new(gate.outputs[0], m2.inputs[1])
    stars = N.new('ShaderNodeMath'); stars.operation = 'ADD'; L.new(st.outputs[0], stars.inputs[0]); L.new(m2.outputs[0], stars.inputs[1])
    neb = N.new('ShaderNodeTexNoise'); neb.inputs['Scale'].default_value = 2.2; neb.inputs['Detail'].default_value = 8
    L.new(tc.outputs['Generated'], neb.inputs['Vector'])
    ramp = N.new('ShaderNodeValToRGB'); r = ramp.color_ramp
    r.elements[0].position = .45; r.elements[0].color = (0.002, 0.002, 0.008, 1)
    r.elements[1].position = .75; r.elements[1].color = (0.09, 0.02, 0.16, 1)
    e = r.elements.new(.62); e.color = (0.01, 0.02, 0.06, 1)
    L.new(neb.outputs['Fac'], ramp.inputs['Fac'])
    starcol = N.new('ShaderNodeMixRGB'); starcol.blend_type = 'ADD'; starcol.inputs['Fac'].default_value = 1
    L.new(ramp.outputs['Color'], starcol.inputs[1])
    sv = N.new('ShaderNodeCombineColor'); [L.new(stars.outputs[0], sv.inputs[i]) for i in range(3)]
    L.new(sv.outputs[0], starcol.inputs[2])
    L.new(starcol.outputs[0], bg.inputs['Color']); bg.inputs['Strength'].default_value = 1.0
    L.new(bg.outputs[0], out.inputs['Surface'])

# ------------------------------------------------------------------ materials
def mat_principled(name, color, rough=.4, metal=0.0, coat=0.0, emit=None, emit_str=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*color, 1); b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    if coat: b.inputs['Coat Weight'].default_value = coat
    if emit: b.inputs['Emission Color'].default_value = (*emit, 1); b.inputs['Emission Strength'].default_value = emit_str
    return m

def mat_emit(name, color, strength):
    m = bpy.data.materials.new(name); nt, N, L = nodes(m)
    o = N.new('ShaderNodeOutputMaterial'); e = N.new('ShaderNodeEmission')
    e.inputs['Color'].default_value = (*color, 1); e.inputs['Strength'].default_value = strength
    L.new(e.outputs[0], o.inputs[0]); return m

def mat_disk(name='disk', strength=4.0, r_in=1.35, r_out=4.2, R=1.0):
    """accretion disk: polar streaks, white-hot inside -> orange -> red outside, alpha falloff"""
    m = bpy.data.materials.new(name); nt, N, L = nodes(m)
    m.blend_method = 'BLEND' if hasattr(m, 'blend_method') else None
    o = N.new('ShaderNodeOutputMaterial'); tc = N.new('ShaderNodeTexCoord')
    sep = N.new('ShaderNodeSeparateXYZ'); L.new(tc.outputs['Object'], sep.inputs[0])
    vl0 = N.new('ShaderNodeVectorMath'); vl0.operation = 'LENGTH'; L.new(tc.outputs['Object'], vl0.inputs[0])
    vl = N.new('ShaderNodeMath'); vl.operation = 'DIVIDE'; vl.inputs[1].default_value = R; L.new(vl0.outputs['Value'], vl.inputs[0])
    ang = N.new('ShaderNodeMath'); ang.operation = 'ARCTAN2'; L.new(sep.outputs['Y'], ang.inputs[0]); L.new(sep.outputs['X'], ang.inputs[1])
    comb = N.new('ShaderNodeCombineXYZ')
    rs = N.new('ShaderNodeMath'); rs.operation = 'MULTIPLY'; rs.inputs[1].default_value = 9.0; L.new(vl.outputs[0], rs.inputs[0])
    an = N.new('ShaderNodeMath'); an.operation = 'MULTIPLY'; an.inputs[1].default_value = 1.2; L.new(ang.outputs[0], an.inputs[0])
    L.new(rs.outputs[0], comb.inputs['X']); L.new(an.outputs[0], comb.inputs['Y'])
    nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 1.6; nz.inputs['Detail'].default_value = 10; nz.inputs['Roughness'].default_value = .62
    L.new(comb.outputs[0], nz.inputs['Vector'])
    # radial profile
    rr = N.new('ShaderNodeMapRange'); rr.inputs['From Min'].default_value = r_in; rr.inputs['From Max'].default_value = r_out
    L.new(vl.outputs[0], rr.inputs['Value'])
    cr = N.new('ShaderNodeValToRGB'); c = cr.color_ramp
    c.elements[0].position = 0; c.elements[0].color = (1.0, 0.8, 0.45, 1)
    c.elements[1].position = 1; c.elements[1].color = (0.35, 0.04, 0.0, 1)
    e = c.elements.new(.25); e.color = (1.0, 0.35, 0.04, 1)
    L.new(rr.outputs[0], cr.inputs['Fac'])
    fall = N.new('ShaderNodeValToRGB'); f = fall.color_ramp
    f.elements[0].position = 0; f.elements[0].color = (0, 0, 0, 1)
    f.elements[1].position = 1; f.elements[1].color = (0, 0, 0, 1)
    e1 = f.elements.new(.04); e1.color = (1, 1, 1, 1); e2 = f.elements.new(.35); e2.color = (.55, .55, .55, 1)
    L.new(rr.outputs[0], fall.inputs['Fac'])
    tex = N.new('ShaderNodeMath'); tex.operation = 'POWER'; tex.inputs[1].default_value = 2.2; L.new(nz.outputs['Fac'], tex.inputs[0])
    tx2 = N.new('ShaderNodeMath'); tx2.operation = 'MULTIPLY'; tx2.inputs[1].default_value = 3.0; L.new(tex.outputs[0], tx2.inputs[0])
    amt = N.new('ShaderNodeMath'); amt.operation = 'MULTIPLY'; L.new(tx2.outputs[0], amt.inputs[0]); L.new(fall.outputs['Color'], amt.inputs[1])
    em = N.new('ShaderNodeEmission'); L.new(cr.outputs['Color'], em.inputs['Color'])
    st = N.new('ShaderNodeMath'); st.operation = 'MULTIPLY'; st.inputs[1].default_value = strength; L.new(amt.outputs[0], st.inputs[0])
    L.new(st.outputs[0], em.inputs['Strength'])
    tr = N.new('ShaderNodeBsdfTransparent'); mix = N.new('ShaderNodeMixShader')
    cl = N.new('ShaderNodeMath'); cl.operation = 'MINIMUM'; cl.inputs[1].default_value = 1.0; L.new(amt.outputs[0], cl.inputs[0])
    L.new(cl.outputs[0], mix.inputs['Fac']); L.new(tr.outputs[0], mix.inputs[1]); L.new(em.outputs[0], mix.inputs[2])
    L.new(mix.outputs[0], o.inputs[0])
    return m

# ------------------------------------------------------------------ objects
def link(obj, parent=None):
    if obj.name not in bpy.context.scene.collection.objects: bpy.context.scene.collection.objects.link(obj)
    if parent: obj.parent = parent
    return obj

def smooth(obj, sub=2, bevel=0.0):
    if bevel:
        b = obj.modifiers.new('bev', 'BEVEL'); b.width = bevel; b.segments = 4
    s = obj.modifiers.new('sub', 'SUBSURF'); s.levels = sub; s.render_levels = sub
    for p in obj.data.polygons: p.use_smooth = True
    return obj

def annulus(name, r0, r1, seg=256, rings=24):
    mesh = bpy.data.meshes.new(name); bm = bmesh.new()
    verts = [[bm.verts.new((math.cos(2 * math.pi * i / seg) * (r0 + (r1 - r0) * j / rings),
                             math.sin(2 * math.pi * i / seg) * (r0 + (r1 - r0) * j / rings), 0)) for i in range(seg)] for j in range(rings + 1)]
    for j in range(rings):
        for i in range(seg):
            bm.faces.new((verts[j][i], verts[j][(i + 1) % seg], verts[j + 1][(i + 1) % seg], verts[j + 1][i]))
    bm.to_mesh(mesh); bm.free(); return bpy.data.objects.new(name, mesh)

def black_hole(loc=(0, 0, 0), R=1.0, cam=None, tilt_deg=8):
    root = bpy.data.objects.new('BH', None); link(root); root.location = loc
    bpy.ops.mesh.primitive_uv_sphere_add(radius=R, segments=96, ring_count=48); s = bpy.context.object
    s.data.materials.append(mat_emit('void', (0, 0, 0), 0.0)); smooth(s, 1); s.parent = root
    disk = link(annulus('disk', R * 1.35, R * 4.4), root); disk.data.materials.append(mat_disk(R=R))
    disk.rotation_euler = (math.radians(tilt_deg), 0, 0)
    # lensed image of the disk's far side: a ring standing up behind the hole, always facing the camera
    halo_root = bpy.data.objects.new('halo_root', None); link(halo_root, root)
    halo = link(annulus('halo', R * 1.04, R * 1.5, 256, 16), halo_root); halo.data.materials.append(mat_disk('halo_m', 3.5, r_in=1.04, r_out=1.9, R=R))
    halo.rotation_euler = (math.radians(90), 0, 0); halo.location = (0, R * 0.25, 0)
    halo.scale = (1.0, 1, 1.0)
    bpy.ops.mesh.primitive_torus_add(major_radius=R * 1.03, minor_radius=R * .005, major_segments=192, minor_segments=8)
    ring = bpy.context.object; ring.data.materials.append(mat_emit('photon', (1, .6, .3), 5)); ring.parent = halo_root
    ring.rotation_euler = (math.radians(90), 0, 0)
    if cam:
        c = halo_root.constraints.new('TRACK_TO'); c.target = cam; c.track_axis = 'TRACK_NEGATIVE_Y'; c.up_axis = 'UP_Z'
    # warm light the disk casts on nearby things
    li = bpy.data.lights.new('diskglow', 'POINT'); li.energy = 3500 * R * R; li.color = (1, .55, .2); li.shadow_soft_size = R * 2
    link(bpy.data.objects.new('diskglow', li), root)
    return root, disk

def astronaut(name='astro'):
    root = bpy.data.objects.new(name, None); link(root)
    white = mat_principled('suit', (.88, .89, .93), rough=.45, coat=.3)
    grey = mat_principled('suitgrey', (.35, .37, .45), rough=.5)
    visor = mat_principled('visor', (1, .62, .18), rough=.08, metal=1)
    dark = mat_principled('dark', (.04, .05, .09), rough=.35)
    def add(obj, mat, sub=2, bev=0):
        obj.data.materials.append(mat); smooth(obj, sub, bev); obj.parent = root; return obj
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0)); t = bpy.context.object; t.scale = (.7, .5, .68); add(t, white, 2, .2)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, .36, .08)); b = bpy.context.object; b.scale = (.6, .28, .66); add(b, grey, 2, .1)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -.25, .05)); p = bpy.context.object; p.scale = (.34, .06, .2); add(p, dark, 1, .03)
    for i, col in enumerate([(1, .2, .25), (1, .8, .1), (.2, 1, .5)]):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=.035, location=(-.09 + i * .09, -.29, .08)); bt = bpy.context.object
        bt.data.materials.append(mat_emit(f'btn{i}', col, 12)); bt.parent = root
    bpy.ops.mesh.primitive_uv_sphere_add(radius=.43, location=(0, 0, .74), segments=64, ring_count=32); h = bpy.context.object; add(h, white, 1)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=.3, location=(0, -.27, .77), segments=64, ring_count=32); v = bpy.context.object
    v.scale = (1.12, .55, .82); add(v, visor, 1)
    bpy.ops.mesh.primitive_torus_add(major_radius=.4, minor_radius=.05, location=(0, 0, .36)); nk = bpy.context.object; add(nk, grey, 1)
    limbs = {}
    for side in (-1, 1):
        sh = bpy.data.objects.new(f'arm{side}', None); link(sh, root); sh.location = (side * .44, 0, .24)
        bpy.ops.mesh.primitive_cylinder_add(radius=.14, depth=.52, location=(0, 0, -.26)); a = bpy.context.object
        a.data.materials.append(white); smooth(a, 2, .05); a.parent = sh
        bpy.ops.mesh.primitive_uv_sphere_add(radius=.15, location=(0, 0, -.56)); g = bpy.context.object; g.data.materials.append(grey); smooth(g, 1); g.parent = sh
        sh.rotation_euler = (0, -side * math.radians(32), 0); limbs[f'arm{side}'] = sh
        hp = bpy.data.objects.new(f'leg{side}', None); link(hp, root); hp.location = (side * .2, 0, -.36)
        bpy.ops.mesh.primitive_cylinder_add(radius=.17, depth=.44, location=(0, 0, -.22)); l = bpy.context.object
        l.data.materials.append(white); smooth(l, 2, .05); l.parent = hp
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -.05, -.5)); bo = bpy.context.object; bo.scale = (.32, .42, .18)
        bo.data.materials.append(grey); smooth(bo, 2, .06); bo.parent = hp
        hp.rotation_euler = (0, -side * math.radians(7), 0); limbs[f'leg{side}'] = hp
    return root, limbs

def camera(loc, look_at, lens=32, dof=None):
    cam = bpy.data.cameras.new('cam'); cam.lens = lens
    co = link(bpy.data.objects.new('cam', cam)); co.location = loc
    tgt = link(bpy.data.objects.new('cam_tgt', None)); tgt.location = look_at
    c = co.constraints.new('TRACK_TO'); c.target = tgt; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
    if dof:
        cam.dof.use_dof = True; cam.dof.focus_object = dof[0]; cam.dof.aperture_fstop = dof[1]
    bpy.context.scene.camera = co
    return co, tgt

def key(obj, frame, **kw):
    for k, v in kw.items():
        setattr(obj, k, v); obj.keyframe_insert(data_path=k, frame=frame)

def rim_lights(target=(0, 0, 0)):
    for name, loc, col, en in [('rim_blue', (-4, 3, 3), (.4, .6, 1), 600), ('fill', (3, -5, 2), (.8, .85, 1), 120)]:
        li = bpy.data.lights.new(name, 'AREA'); li.energy = en; li.color = col; li.size = 3
        o = link(bpy.data.objects.new(name, li)); o.location = loc
        c = o.constraints.new('TRACK_TO'); t = bpy.data.objects.new(name + '_t', None); link(t); t.location = target
        c.target = t; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'

# ------------------------------------------------------------------ planets
def _noise(N, L, vec, scale, detail=8, rough=.55):
    nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = scale; nz.inputs['Detail'].default_value = detail
    nz.inputs['Roughness'].default_value = rough; L.new(vec, nz.inputs['Vector']); return nz

def mat_earth(sun_dir=(1, 0, 0)):
    """procedural Earth: oceans, continents, ice caps (animatable), city lights on the night side, warmth tint (animatable)"""
    m = bpy.data.materials.new('earth'); nt, N, L = nodes(m)
    o = N.new('ShaderNodeOutputMaterial'); tc = N.new('ShaderNodeTexCoord'); bs = N.new('ShaderNodeBsdfPrincipled')
    land_n = _noise(N, L, tc.outputs['Object'], 1.25, 7, .58)
    landm = N.new('ShaderNodeMapRange'); landm.inputs['From Min'].default_value = .52; landm.inputs['From Max'].default_value = .54
    L.new(land_n.outputs['Fac'], landm.inputs['Value'])
    lc = N.new('ShaderNodeValToRGB'); r = lc.color_ramp
    r.elements[0].position = .5; r.elements[0].color = (.05, .16, .03, 1); r.elements[1].position = .68; r.elements[1].color = (.42, .3, .14, 1)
    e = r.elements.new(.58); e.color = (.12, .24, .05, 1)
    L.new(land_n.outputs['Fac'], lc.inputs['Fac'])
    oc = N.new('ShaderNodeValToRGB'); r2 = oc.color_ramp
    r2.elements[0].position = .35; r2.elements[0].color = (.003, .02, .09, 1); r2.elements[1].position = .53; r2.elements[1].color = (.01, .09, .22, 1)
    L.new(land_n.outputs['Fac'], oc.inputs['Fac'])
    warm = N.new('ShaderNodeMixRGB'); warm.name = 'warm'; warm.blend_type = 'MIX'; warm.inputs['Fac'].default_value = 0.0
    L.new(lc.outputs['Color'], warm.inputs[1]); warm.inputs[2].default_value = (.55, .22, .05, 1)
    surf = N.new('ShaderNodeMixRGB'); L.new(landm.outputs[0], surf.inputs['Fac']); L.new(oc.outputs['Color'], surf.inputs[1]); L.new(warm.outputs[0], surf.inputs[2])
    sep = N.new('ShaderNodeSeparateXYZ'); L.new(tc.outputs['Generated'], sep.inputs[0])
    zc = N.new('ShaderNodeMath'); zc.operation = 'SUBTRACT'; zc.inputs[1].default_value = .5; L.new(sep.outputs['Z'], zc.inputs[0])
    za = N.new('ShaderNodeMath'); za.operation = 'ABSOLUTE'; L.new(zc.outputs[0], za.inputs[0])
    wob = _noise(N, L, tc.outputs['Object'], 4, 4)
    wb = N.new('ShaderNodeMath'); wb.operation = 'MULTIPLY_ADD'; wb.inputs[1].default_value = .06; L.new(wob.outputs['Fac'], wb.inputs[0]); L.new(za.outputs[0], wb.inputs[2])
    ice = N.new('ShaderNodeMath'); ice.name = 'ice'; ice.operation = 'GREATER_THAN'; ice.inputs[1].default_value = .43
    L.new(wb.outputs[0], ice.inputs[0])
    withice = N.new('ShaderNodeMixRGB'); L.new(ice.outputs[0], withice.inputs['Fac']); L.new(surf.outputs[0], withice.inputs[1]); withice.inputs[2].default_value = (.85, .9, .95, 1)
    L.new(withice.outputs[0], bs.inputs['Base Color'])
    rough = N.new('ShaderNodeMapRange'); rough.inputs['To Min'].default_value = .25; rough.inputs['To Max'].default_value = .85
    L.new(landm.outputs[0], rough.inputs['Value']); L.new(rough.outputs[0], bs.inputs['Roughness'])
    # night-side city lights
    geo = N.new('ShaderNodeNewGeometry'); dot = N.new('ShaderNodeVectorMath'); dot.operation = 'DOT_PRODUCT'
    L.new(geo.outputs['Normal'], dot.inputs[0]); dot.inputs[1].default_value = sun_dir
    night = N.new('ShaderNodeMapRange'); night.inputs['From Min'].default_value = 0.05; night.inputs['From Max'].default_value = -0.2
    L.new(dot.outputs['Value'], night.inputs['Value'])
    city = _noise(N, L, tc.outputs['Object'], 38, 2)
    cm = N.new('ShaderNodeMapRange'); cm.inputs['From Min'].default_value = .6; cm.inputs['From Max'].default_value = .72; L.new(city.outputs['Fac'], cm.inputs['Value'])
    m1 = N.new('ShaderNodeMath'); m1.operation = 'MULTIPLY'; L.new(cm.outputs[0], m1.inputs[0]); L.new(landm.outputs[0], m1.inputs[1])
    m2 = N.new('ShaderNodeMath'); m2.operation = 'MULTIPLY'; L.new(m1.outputs[0], m2.inputs[0]); L.new(night.outputs[0], m2.inputs[1])
    m3 = N.new('ShaderNodeMath'); m3.operation = 'MULTIPLY'; m3.inputs[1].default_value = 3.0; L.new(m2.outputs[0], m3.inputs[0])
    bs.inputs['Emission Color'].default_value = (1, .7, .35, 1); L.new(m3.outputs[0], bs.inputs['Emission Strength'])
    L.new(bs.outputs[0], o.inputs[0]); return m

def mat_clouds():
    m = bpy.data.materials.new('clouds'); nt, N, L = nodes(m)
    o = N.new('ShaderNodeOutputMaterial'); tc = N.new('ShaderNodeTexCoord')
    nz = _noise(N, L, tc.outputs['Object'], 3.2, 6, .6)
    mr = N.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value = .6; mr.inputs['From Max'].default_value = .74; L.new(nz.outputs['Fac'], mr.inputs['Value'])
    d = N.new('ShaderNodeBsdfDiffuse'); d.inputs['Color'].default_value = (1, 1, 1, 1); tr = N.new('ShaderNodeBsdfTransparent'); mx = N.new('ShaderNodeMixShader')
    L.new(mr.outputs[0], mx.inputs['Fac']); L.new(tr.outputs[0], mx.inputs[1]); L.new(d.outputs[0], mx.inputs[2]); L.new(mx.outputs[0], o.inputs[0]); return m

def mat_atmo(color=(.25, .55, 1), strength=1.4):
    m = bpy.data.materials.new('atmo'); nt, N, L = nodes(m)
    o = N.new('ShaderNodeOutputMaterial'); lw = N.new('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = .2
    pw = N.new('ShaderNodeMath'); pw.operation = 'POWER'; pw.inputs[1].default_value = 5.0; L.new(lw.outputs['Facing'], pw.inputs[0])
    e = N.new('ShaderNodeEmission'); e.inputs['Color'].default_value = (*color, 1); e.inputs['Strength'].default_value = strength
    tr = N.new('ShaderNodeBsdfTransparent'); mx = N.new('ShaderNodeMixShader')
    L.new(pw.outputs[0], mx.inputs['Fac']); L.new(tr.outputs[0], mx.inputs[1]); L.new(e.outputs[0], mx.inputs[2]); L.new(mx.outputs[0], o.inputs[0]); return m

def earth_procedural(R=2.0, sun_dir=(1, 0, 0), tilt_deg=23.4, axis=False, clouds=True, atmo=True):
    """returns (tilt_root, spin) ; animate spin.rotation_euler.z for rotation, tilt_root.rotation_euler.y for tilt"""
    root = link(bpy.data.objects.new('earth_tilt', None)); root.rotation_euler = (0, math.radians(tilt_deg), 0)
    spin = link(bpy.data.objects.new('earth_spin', None), root)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=R, segments=128, ring_count=64); e = bpy.context.object
    e.data.materials.append(mat_earth(sun_dir)); smooth(e, 0); e.parent = spin
    if clouds:
        bpy.ops.mesh.primitive_uv_sphere_add(radius=R * 1.015, segments=96, ring_count=48); c = bpy.context.object
        c.data.materials.append(mat_clouds()); smooth(c, 0); c.parent = spin; c.rotation_euler = (0, 0, .7)
    for ob in [o for o in spin.children]:          # keep feature sizes the same for any planet radius
        for n in ob.active_material.node_tree.nodes:
            if n.type == 'TEX_NOISE': n.inputs['Scale'].default_value *= 2.0 / R
    if atmo:
        bpy.ops.mesh.primitive_uv_sphere_add(radius=R * 1.05, segments=96, ring_count=48); a = bpy.context.object
        a.data.materials.append(mat_atmo()); smooth(a, 0); a.parent = root
    if axis:
        bpy.ops.mesh.primitive_cylinder_add(radius=R * .018, depth=R * 3.2); ax = bpy.context.object
        ax.data.materials.append(mat_emit('axis', (1, .9, .5), 6)); ax.parent = root
    return root, spin

def moon_procedural(R=.55):
    m = bpy.data.materials.new('moon'); nt, N, L = nodes(m)
    o = N.new('ShaderNodeOutputMaterial'); tc = N.new('ShaderNodeTexCoord'); bs = N.new('ShaderNodeBsdfPrincipled'); bs.inputs['Roughness'].default_value = .95
    mar = _noise(N, L, tc.outputs['Object'], 1.6, 6)
    cr = N.new('ShaderNodeValToRGB'); cr.color_ramp.elements[0].position = .45; cr.color_ramp.elements[0].color = (.1, .1, .11, 1)
    cr.color_ramp.elements[1].position = .6; cr.color_ramp.elements[1].color = (.36, .36, .35, 1); L.new(mar.outputs['Fac'], cr.inputs['Fac']); L.new(cr.outputs['Color'], bs.inputs['Base Color'])
    vo = N.new('ShaderNodeTexVoronoi'); vo.inputs['Scale'].default_value = 9; L.new(tc.outputs['Object'], vo.inputs['Vector'])
    bump = N.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = .5; L.new(vo.outputs['Distance'], bump.inputs['Height']); L.new(bump.outputs['Normal'], bs.inputs['Normal'])
    L.new(bs.outputs[0], o.inputs[0])
    bpy.ops.mesh.primitive_uv_sphere_add(radius=R, segments=96, ring_count=48); mo = bpy.context.object
    mo.data.materials.append(m); smooth(mo, 0); return mo

def sun_lamp(direction=(1, 0, 0), energy=4.0, color=(1, .96, .9)):
    li = bpy.data.lights.new('sun', 'SUN'); li.energy = energy; li.color = color; li.angle = math.radians(1.5)
    o = link(bpy.data.objects.new('sun', li))
    o.rotation_euler = Vector(direction).to_track_quat('-Z', 'Y').to_euler() if False else (Vector((0, 0, 0)) - Vector(direction)).to_track_quat('-Z', 'Y').to_euler()
    return o


# ------------------------------------------------------------------ spacecraft
def mat_panel(name='solarcell', color=(.05, .1, .35)):
    m = bpy.data.materials.new(name); nt, N, L = nodes(m)
    o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled'); tc = N.new('ShaderNodeTexCoord')
    br = N.new('ShaderNodeTexBrick'); br.inputs['Scale'].default_value = 6; br.inputs['Mortar Size'].default_value = .02
    br.inputs['Color1'].default_value = (*color, 1); br.inputs['Color2'].default_value = tuple(c * 1.4 for c in color) + (1,)
    br.inputs['Mortar'].default_value = (.7, .7, .75, 1)
    L.new(tc.outputs['UV'], br.inputs['Vector']); L.new(br.outputs['Color'], bs.inputs['Base Color'])
    bs.inputs['Metallic'].default_value = .3; bs.inputs['Roughness'].default_value = .3
    L.new(bs.outputs[0], o.inputs[0]); return m

def mat_foil(name='foil', color=(.85, .86, .88), rough=.3):
    m = bpy.data.materials.new(name); nt, N, L = nodes(m)
    o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled'); tc = N.new('ShaderNodeTexCoord')
    bs.inputs['Base Color'].default_value = (*color, 1); bs.inputs['Metallic'].default_value = .55; bs.inputs['Roughness'].default_value = rough
    nz = _noise(N, L, tc.outputs['Object'], 9, 3); bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = .25
    L.new(nz.outputs['Fac'], bp.inputs['Height']); L.new(bp.outputs['Normal'], bs.inputs['Normal']); L.new(bs.outputs[0], o.inputs[0]); return m

def hubble_procedural(name='hubble'):
    """Hubble-like telescope along +X, ~3.3 units long (1 unit ~ 4 m). Returns root; parts dict for animation."""
    root = link(bpy.data.objects.new(name, None)); parts = {}
    foil, white, dark = mat_foil('hst_foil'), mat_principled('hst_white', (.82, .83, .85), .55), mat_principled('hst_dark', (.03, .03, .04), .4)
    def add(o, m, sub=1, bev=0): o.data.materials.append(m); smooth(o, sub, bev); o.parent = root; return o
    bpy.ops.mesh.primitive_cylinder_add(radius=.56, depth=1.25, location=(-1.0, 0, 0), rotation=(0, math.radians(90), 0), vertices=48)
    add(bpy.context.object, foil, 1, .03)
    bpy.ops.mesh.primitive_cylinder_add(radius=.5, depth=2.05, location=(.62, 0, 0), rotation=(0, math.radians(90), 0), vertices=48)
    add(bpy.context.object, white, 1, .02)
    for x in (-.4, .3, 1.0):
        bpy.ops.mesh.primitive_torus_add(major_radius=.5, minor_radius=.015, location=(x, 0, 0), rotation=(0, math.radians(90), 0)); add(bpy.context.object, dark, 0)
    bpy.ops.mesh.primitive_cylinder_add(radius=.47, depth=.04, location=(1.65, 0, 0), rotation=(0, math.radians(90), 0), vertices=48)
    add(bpy.context.object, dark, 0)
    door = link(bpy.data.objects.new('door_hinge', None), root); door.location = (1.66, 0, .5)
    bpy.ops.mesh.primitive_cylinder_add(radius=.5, depth=.04, location=(0, 0, -.5), rotation=(0, math.radians(90), 0), vertices=48)
    d = bpy.context.object; d.data.materials.append(foil); d.parent = door; door.rotation_euler = (0, math.radians(-100), 0)
    panel = mat_panel('hst_cells', (.1, .2, .62))
    for side in (1, -1):
        boom = link(bpy.data.objects.new(f'array{side}', None), root); boom.location = (-.9, side * .58, 0)
        bpy.ops.mesh.primitive_cylinder_add(radius=.025, depth=.35, location=(0, side * .17, 0), rotation=(math.radians(90), 0, 0)); bm = bpy.context.object; bm.data.materials.append(foil); bm.parent = boom
        bpy.ops.mesh.primitive_plane_add(size=1, location=(0, side * 1.25, 0)); p = bpy.context.object
        p.scale = (.65, 1.8, 1); p.data.materials.append(panel); p.parent = boom
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, side * 1.25, -.008)); fr = bpy.context.object; fr.scale = (.68, 1.83, .012)
        fr.data.materials.append(dark); fr.parent = boom
        boom.rotation_euler = (0, math.radians(65), 0); parts[f'array{side}'] = boom
    for z in (1, -1):
        bpy.ops.mesh.primitive_cylinder_add(radius=.02, depth=.6, location=(.1, 0, z * .78)); add(bpy.context.object, foil, 0)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=.22, location=(.1, 0, z * 1.1), segments=24, ring_count=12); dish = bpy.context.object
        dish.scale = (1, 1, .3); add(dish, white, 0)
    parts['door'] = door
    return root, parts

def school_bus(name='bus'):
    root = link(bpy.data.objects.new(name, None))
    yel = mat_principled('bus_yellow', (1, .62, .02), .35, coat=.6); blk = mat_principled('bus_black', (.02, .02, .02), .5); win = mat_principled('bus_glass', (.1, .15, .2), .05, metal=.3)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, .55)); b = bpy.context.object; b.scale = (3.3, .62, .75); b.data.materials.append(yel); smooth(b, 2, .08); b.parent = root
    bpy.ops.mesh.primitive_cube_add(size=1, location=(-.15, 0, .72)); w = bpy.context.object; w.scale = (2.7, .64, .22); w.data.materials.append(win); smooth(w, 1, .03); w.parent = root
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, .3)); s = bpy.context.object; s.scale = (3.32, .64, .04); s.data.materials.append(blk); s.parent = root
    for x in (-1.1, 1.1):
        for y in (-.31, .31):
            bpy.ops.mesh.primitive_cylinder_add(radius=.2, depth=.14, location=(x, y, .18), rotation=(math.radians(90), 0, 0)); t = bpy.context.object; t.data.materials.append(blk); t.parent = root
    return root

def servicer(name='servicer'):
    root = link(bpy.data.objects.new(name, None))
    gold = mat_foil('gold_foil', (1, .62, .2), .35); cells = mat_panel('srv_cells', (.05, .08, .25)); grey = mat_principled('srv_grey', (.5, .52, .58), .4, metal=.6)
    bpy.ops.mesh.primitive_cube_add(size=1); b = bpy.context.object; b.scale = (.7, .6, .6); b.data.materials.append(gold); smooth(b, 1, .03); b.parent = root
    for side in (1, -1):
        bpy.ops.mesh.primitive_plane_add(size=1, location=(0, side * 1.0, 0)); p = bpy.context.object; p.scale = (.5, 1.1, 1); p.rotation_euler = (math.radians(90), 0, 0)
        p.data.materials.append(cells); p.parent = root
    bpy.ops.mesh.primitive_cylinder_add(radius=.06, depth=.6, location=(.6, 0, 0), rotation=(0, math.radians(90), 0)); a = bpy.context.object; a.data.materials.append(grey); a.parent = root
    bpy.ops.mesh.primitive_torus_add(major_radius=.12, minor_radius=.03, location=(.92, 0, 0), rotation=(0, math.radians(90), 0)); r = bpy.context.object; r.data.materials.append(grey); r.parent = root
    bpy.ops.mesh.primitive_cone_add(radius1=.15, depth=.3, location=(-.48, 0, 0), rotation=(0, math.radians(-90), 0)); n = bpy.context.object; n.data.materials.append(grey); n.parent = root
    return root

def fireball(parent, length=3.0, radius=.9, strength=10.0, name='plasma'):
    """glowing reentry plasma sheath + trail around an object; trail extends along +Z of `parent`. 'plasma_fade' node scales it (0..1)"""
    m = bpy.data.materials.new(name); nt, N, L = nodes(m)
    o = N.new('ShaderNodeOutputMaterial'); lw = N.new('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = .45
    tc = N.new('ShaderNodeTexCoord'); nz = _noise(N, L, tc.outputs['Object'], 4.0, 4)
    rim = N.new('ShaderNodeMath'); rim.operation = 'POWER'; rim.inputs[1].default_value = 1.6; L.new(lw.outputs['Facing'], rim.inputs[0])
    nzm = N.new('ShaderNodeMapRange'); nzm.inputs['To Min'].default_value = .35; nzm.inputs['To Max'].default_value = 1.0; L.new(nz.outputs['Fac'], nzm.inputs['Value'])
    a = N.new('ShaderNodeMath'); a.operation = 'MULTIPLY'; L.new(rim.outputs[0], a.inputs[0]); L.new(nzm.outputs[0], a.inputs[1])
    fm = N.new('ShaderNodeMath'); fm.name = 'plasma_fade'; fm.operation = 'MULTIPLY'; fm.inputs[1].default_value = 1.0; L.new(a.outputs[0], fm.inputs[0])
    cl = N.new('ShaderNodeClamp'); L.new(fm.outputs[0], cl.inputs['Value'])
    ramp = N.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].color = (1, .06, .0, 1); ramp.color_ramp.elements[1].color = (1, .32, .02, 1)
    L.new(nz.outputs['Fac'], ramp.inputs['Fac'])
    e = N.new('ShaderNodeEmission'); L.new(ramp.outputs['Color'], e.inputs['Color']); e.inputs['Strength'].default_value = strength
    tr = N.new('ShaderNodeBsdfTransparent'); mx = N.new('ShaderNodeMixShader')
    L.new(cl.outputs[0], mx.inputs['Fac']); L.new(tr.outputs[0], mx.inputs[1]); L.new(e.outputs[0], mx.inputs[2]); L.new(mx.outputs[0], o.inputs[0])
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, segments=48, ring_count=24); s = bpy.context.object; s.scale = (1, 1, length / radius * .5)
    s.location = (0, 0, length * .3); s.data.materials.append(m); smooth(s, 0); s.parent = parent
    return s, m


# ================================================================== REAL-DATA ASSETS (accuracy upgrade)
# Planet maps: Solar System Scope textures (CC BY 4.0, built from NASA mission data) in pipeline/assets/textures.
# Spacecraft: NASA-3D-Resources glTF models (github.com/nasa/NASA-3D-Resources, free for non-commercial and commercial use
# under NASA media guidelines), downloaded on demand. Credit line for video descriptions is in pipeline/assets/CREDITS.md.
import os, sys, urllib.parse, urllib.request
_HERE = os.path.dirname(os.path.abspath(__file__))
_TEX_DIRS = [os.path.join(_HERE, 'assets', 'textures'), '/home/claude/hypotheticool-videos/pipeline/assets/textures',
             '/home/claude/b3d/assets/textures']
NASA_CACHE = '/home/claude/nasa_cache'

def tex_path(name):
    for d in _TEX_DIRS:
        p = os.path.join(d, name)
        if os.path.exists(p): return p
    raise FileNotFoundError(f'texture {name} not found in {_TEX_DIRS} (clone the repo: pipeline/assets/textures)')

def _img(N, name, noncolor=False, vec=None, L=None, ext='REPEAT'):
    t = N.new('ShaderNodeTexImage'); im = bpy.data.images.load(tex_path(name), check_existing=True)
    if noncolor: im.colorspace_settings.name = 'Non-Color'
    t.image = im; t.interpolation = 'Cubic'; t.extension = ext
    if vec is not None: L.new(vec, t.inputs['Vector'])
    return t

def _sun_factor(N, L, sun_dir, lo, hi):
    """0..1 ramp on the dot(normal, sun) — use lo>hi for the night side"""
    geo = N.new('ShaderNodeNewGeometry'); dot = N.new('ShaderNodeVectorMath'); dot.operation = 'DOT_PRODUCT'
    L.new(geo.outputs['Normal'], dot.inputs[0]); dot.inputs[1].default_value = Vector(sun_dir).normalized()
    mr = N.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value = lo; mr.inputs['From Max'].default_value = hi
    L.new(dot.outputs['Value'], mr.inputs['Value']); return mr

def mat_earth_real(sun_dir=(1, 0, 0), lights=2.2):
    """Real Earth: NASA Blue Marble-based day map, ocean glint from the specular map, terrain normal map,
    real city lights (Black Marble-based) only on the night side. Keeps the animatable nodes 'warm' and 'ice'."""
    m = bpy.data.materials.new('earth'); nt, N, L = nodes(m)
    o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled'); uv = N.new('ShaderNodeTexCoord')
    day = _img(N, 'earth_day.jpg', vec=uv.outputs['UV'], L=L)
    spec = _img(N, 'earth_specular.jpg', True, uv.outputs['UV'], L)
    nrm = _img(N, 'earth_normal.jpg', True, uv.outputs['UV'], L)
    night = _img(N, 'earth_night.jpg', vec=uv.outputs['UV'], L=L)
    warm = N.new('ShaderNodeMixRGB'); warm.name = 'warm'; warm.inputs['Fac'].default_value = 0.0
    L.new(day.outputs['Color'], warm.inputs[1]); warm.inputs[2].default_value = (.55, .22, .05, 1)
    sep = N.new('ShaderNodeSeparateXYZ'); gen = N.new('ShaderNodeTexCoord'); L.new(gen.outputs['Generated'], sep.inputs[0])
    zc = N.new('ShaderNodeMath'); zc.operation = 'SUBTRACT'; zc.inputs[1].default_value = .5; L.new(sep.outputs['Z'], zc.inputs[0])
    za = N.new('ShaderNodeMath'); za.operation = 'ABSOLUTE'; L.new(zc.outputs[0], za.inputs[0])
    ice = N.new('ShaderNodeMath'); ice.name = 'ice'; ice.operation = 'GREATER_THAN'; ice.inputs[1].default_value = 1.0  # >0.5 = no extra ice
    L.new(za.outputs[0], ice.inputs[0])
    withice = N.new('ShaderNodeMixRGB'); L.new(ice.outputs[0], withice.inputs['Fac']); L.new(warm.outputs[0], withice.inputs[1])
    withice.inputs[2].default_value = (.85, .9, .95, 1); L.new(withice.outputs[0], bs.inputs['Base Color'])
    rough = N.new('ShaderNodeMapRange'); rough.inputs['To Min'].default_value = .82; rough.inputs['To Max'].default_value = .32
    L.new(spec.outputs['Color'], rough.inputs['Value']); L.new(rough.outputs[0], bs.inputs['Roughness'])
    bs.inputs['Specular IOR Level'].default_value = .6
    nm = N.new('ShaderNodeNormalMap'); nm.inputs['Strength'].default_value = .6; L.new(nrm.outputs['Color'], nm.inputs['Color'])
    L.new(nm.outputs['Normal'], bs.inputs['Normal'])
    nightf = _sun_factor(N, L, sun_dir, .08, -.18)
    em = N.new('ShaderNodeMixRGB'); em.blend_type = 'MULTIPLY'; em.inputs['Fac'].default_value = 1
    L.new(night.outputs['Color'], em.inputs[1]); em.inputs[2].default_value = (1, .78, .5, 1)
    L.new(em.outputs[0], bs.inputs['Emission Color'])
    es = N.new('ShaderNodeMath'); es.operation = 'MULTIPLY'; es.inputs[1].default_value = lights; L.new(nightf.outputs[0], es.inputs[0])
    L.new(es.outputs[0], bs.inputs['Emission Strength'])
    L.new(bs.outputs[0], o.inputs[0]); return m

def mat_clouds_real(sun_dir=(1, 0, 0)):
    m = bpy.data.materials.new('clouds'); nt, N, L = nodes(m); m.blend_method = 'HASHED' if hasattr(m, 'blend_method') else None
    o = N.new('ShaderNodeOutputMaterial'); uv = N.new('ShaderNodeTexCoord')
    c = _img(N, 'earth_clouds.jpg', True, uv.outputs['UV'], L)
    g = N.new('ShaderNodeMath'); g.operation = 'POWER'; g.inputs[1].default_value = 1.4; L.new(c.outputs['Color'], g.inputs[0])
    d = N.new('ShaderNodeBsdfDiffuse'); d.inputs['Color'].default_value = (1, 1, 1, 1)
    tr = N.new('ShaderNodeBsdfTransparent'); mx = N.new('ShaderNodeMixShader')
    L.new(g.outputs[0], mx.inputs['Fac']); L.new(tr.outputs[0], mx.inputs[1]); L.new(d.outputs[0], mx.inputs[2]); L.new(mx.outputs[0], o.inputs[0]); return m

def mat_atmo_real(sun_dir=(1, 0, 0), color=(.3, .58, 1), strength=2.2):
    """thin blue limb glow, bright on the day side and fading into the night side (like real photos from orbit)"""
    m = bpy.data.materials.new('atmo'); nt, N, L = nodes(m)
    o = N.new('ShaderNodeOutputMaterial'); lw = N.new('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = .25
    pw = N.new('ShaderNodeMath'); pw.operation = 'POWER'; pw.inputs[1].default_value = 4.0; L.new(lw.outputs['Facing'], pw.inputs[0])
    dayf = _sun_factor(N, L, sun_dir, -.35, .25)
    mul = N.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; L.new(pw.outputs[0], mul.inputs[0]); L.new(dayf.outputs[0], mul.inputs[1])
    e = N.new('ShaderNodeEmission'); e.inputs['Color'].default_value = (*color, 1); e.inputs['Strength'].default_value = strength
    tr = N.new('ShaderNodeBsdfTransparent'); mx = N.new('ShaderNodeMixShader')
    L.new(mul.outputs[0], mx.inputs['Fac']); L.new(tr.outputs[0], mx.inputs[1]); L.new(e.outputs[0], mx.inputs[2]); L.new(mx.outputs[0], o.inputs[0]); return m

def _sphere(R, seg=192, rings=96):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=R, segments=seg, ring_count=rings); s = bpy.context.object
    smooth(s, 0); return s

def earth(R=2.0, sun_dir=(1, 0, 0), tilt_deg=23.4, axis=False, clouds=True, atmo=True, real=True, face_lon=-80.0):
    """Real-data Earth. returns (tilt_root, spin); animate spin.rotation_euler.z to rotate.
    face_lon = longitude (deg, east +) that faces the -Y direction (the default camera side) at rotation 0,
    e.g. -80 shows the Americas, 15 Europe/Africa, 100 Asia."""
    if not real: return earth_procedural(R, sun_dir, tilt_deg, axis, clouds, atmo)
    root = link(bpy.data.objects.new('earth_tilt', None)); root.rotation_euler = (0, math.radians(tilt_deg), 0)
    spin = link(bpy.data.objects.new('earth_spin', None), root)
    e = _sphere(R); e.name = 'earth'; e.data.materials.append(mat_earth_real(sun_dir)); e.parent = spin
    e.rotation_euler = (0, 0, math.radians(-90 - face_lon))
    if clouds:
        c = _sphere(R * 1.006, 128, 64); c.name = 'clouds'; c.data.materials.append(mat_clouds_real(sun_dir)); c.parent = spin
        c.rotation_euler = (0, 0, math.radians(-90 - face_lon))
    if atmo:
        a = _sphere(R * 1.035, 128, 64); a.name = 'atmo'; a.data.materials.append(mat_atmo_real(sun_dir)); a.parent = root
        a.visible_shadow = False
    if axis:
        bpy.ops.mesh.primitive_cylinder_add(radius=R * .018, depth=R * 3.2); ax = bpy.context.object
        ax.data.materials.append(mat_emit('axis', (1, .9, .5), 6)); ax.parent = root
    return root, spin

PLANETS = {   # name: (texture, roughness, bump strength)
    'moon': ('moon.jpg', .95, .35), 'mars': ('mars.jpg', .9, .25), 'mercury': ('mercury.jpg', .95, .3),
    'venus_surface': ('venus_surface.jpg', .9, .15), 'jupiter': ('jupiter.jpg', .8, 0), 'saturn': ('saturn.jpg', .8, 0),
    'uranus': ('uranus.jpg', .7, 0), 'neptune': ('neptune.jpg', .7, 0)}

def planet(name, R=1.0, tilt_deg=0.0, rings=None, face_lon=0.0):
    """textured real-data planet/moon. returns (tilt_root, spin, mesh). Saturn gets its rings automatically.
    Real axial tilts: Mercury 0.03, Venus 177, Earth 23.4, Mars 25.2, Jupiter 3.1, Saturn 26.7, Uranus 97.8, Neptune 28.3 (deg)."""
    texn, rough, bump = PLANETS[name]
    m = bpy.data.materials.new(name); nt, N, L = nodes(m)
    o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled'); uv = N.new('ShaderNodeTexCoord')
    t = _img(N, texn, vec=uv.outputs['UV'], L=L); L.new(t.outputs['Color'], bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = rough; bs.inputs['Specular IOR Level'].default_value = .2
    if bump:
        bw = N.new('ShaderNodeRGBToBW'); L.new(t.outputs['Color'], bw.inputs[0])
        b = N.new('ShaderNodeBump'); b.inputs['Strength'].default_value = bump; b.inputs['Distance'].default_value = .02 * R
        L.new(bw.outputs[0], b.inputs['Height']); L.new(b.outputs['Normal'], bs.inputs['Normal'])
    L.new(bs.outputs[0], o.inputs[0])
    root = link(bpy.data.objects.new(f'{name}_tilt', None)); root.rotation_euler = (0, math.radians(tilt_deg), 0)
    spin = link(bpy.data.objects.new(f'{name}_spin', None), root)
    s = _sphere(R); s.name = name; s.data.materials.append(m); s.parent = spin; s.rotation_euler = (0, 0, math.radians(-90 - face_lon))
    if rings or (rings is None and name == 'saturn'): saturn_rings(R, root)
    return root, spin, s

def saturn_rings(R, parent):
    """real ring brightness/transparency profile (C ring to A ring incl. the Cassini Division), 1.24–2.27 Saturn radii"""
    r0, r1 = 1.24 * R, 2.27 * R
    ob = link(annulus('rings', r0, r1, 256, 8)); ob.parent = parent
    m = bpy.data.materials.new('rings'); nt, N, L = nodes(m)
    o = N.new('ShaderNodeOutputMaterial'); tc = N.new('ShaderNodeTexCoord')
    ln = N.new('ShaderNodeVectorMath'); ln.operation = 'LENGTH'; L.new(tc.outputs['Object'], ln.inputs[0])
    u = N.new('ShaderNodeMapRange'); u.inputs['From Min'].default_value = r0; u.inputs['From Max'].default_value = r1; L.new(ln.outputs['Value'], u.inputs['Value'])
    cx = N.new('ShaderNodeCombineXYZ'); L.new(u.outputs[0], cx.inputs['X']); cx.inputs['Y'].default_value = .5
    t = _img(N, 'saturn_ring.png', vec=cx.outputs[0], L=L, ext='EXTEND')
    d = N.new('ShaderNodeBsdfDiffuse'); L.new(t.outputs['Color'], d.inputs['Color'])
    tr = N.new('ShaderNodeBsdfTransparent'); mx = N.new('ShaderNodeMixShader')
    L.new(t.outputs['Alpha'], mx.inputs['Fac']); L.new(tr.outputs[0], mx.inputs[1]); L.new(d.outputs[0], mx.inputs[2]); L.new(mx.outputs[0], o.inputs[0])
    ob.data.materials.append(m); return ob

def moon(R=.55, real=True, face_lon=0.0):
    """real LRO-based Moon map (near side faces -Y by default, as seen from Earth)"""
    if not real: return moon_procedural(R)
    root, spin, s = planet('moon', R, 6.7, face_lon=face_lon)
    return root

def sun_sphere(R=1.0, strength=12.0):
    m = bpy.data.materials.new('sun_surface'); nt, N, L = nodes(m)
    o = N.new('ShaderNodeOutputMaterial'); uv = N.new('ShaderNodeTexCoord'); t = _img(N, 'sun.jpg', vec=uv.outputs['UV'], L=L)
    e = N.new('ShaderNodeEmission'); e.inputs['Strength'].default_value = strength; L.new(t.outputs['Color'], e.inputs['Color']); L.new(e.outputs[0], o.inputs[0])
    s = _sphere(R, 128, 64); s.name = 'sun_body'; s.data.materials.append(m); return s

def world(real=True, strength=.55, rot_deg=(0, 0, 0)):
    """real night sky: ESO/Gaia-style Milky Way star map (equirectangular). rot_deg rotates the sky."""
    if not real: return world_procedural()
    sc = bpy.context.scene; w = bpy.data.worlds.new('space'); sc.world = w; nt, N, L = nodes(w)
    out = N.new('ShaderNodeOutputWorld'); bg = N.new('ShaderNodeBackground'); tc = N.new('ShaderNodeTexCoord'); mp = N.new('ShaderNodeMapping')
    mp.inputs['Rotation'].default_value = tuple(math.radians(a) for a in rot_deg); L.new(tc.outputs['Generated'], mp.inputs['Vector'])
    env = N.new('ShaderNodeTexEnvironment'); env.image = bpy.data.images.load(tex_path('stars_milky_way.jpg'), check_existing=True)
    L.new(mp.outputs[0], env.inputs['Vector'])
    gm = N.new('ShaderNodeGamma'); gm.inputs['Gamma'].default_value = 1.6; L.new(env.outputs['Color'], gm.inputs['Color'])   # deep blacks, crisp stars
    L.new(gm.outputs[0], bg.inputs['Color']); bg.inputs['Strength'].default_value = strength; L.new(bg.outputs[0], out.inputs['Surface'])

def nasa_model(name, size=3.0, align='X'):
    """Import an official NASA 3D model by folder name (see pipeline/assets/nasa_models.txt, e.g. 'Hubble Space Telescope (B)',
    'International Space Station (ISS) (B)', 'James Webb Space Telescope (A)', 'Voyager Probe (A)', 'Apollo Lunar Module',
    'Saturn V', 'Space Shuttle (A)', 'Cassini-Huygens (A)', 'Parker Solar Probe', 'Juno (A)', 'Mars 2020 Perseverance Rover').
    Downloads to NASA_CACHE once. Returns an empty that holds the model, centered, longest side = size, longest axis along `align`."""
    os.makedirs(NASA_CACHE, exist_ok=True)
    catalog = [l.strip() for l in open(os.path.join(os.path.dirname(tex_path('earth_day.jpg')), '..', 'nasa_models.txt'))]
    rel = next((c for c in catalog if c.split('/')[0] == name and c.endswith('.glb') and c.split('/')[1].startswith(name.split(' (')[0])), None) \
        or next((c for c in catalog if c.split('/')[0] == name), None)
    if not rel: raise ValueError(f'unknown NASA model {name}')
    path = os.path.join(NASA_CACHE, rel.replace('/', '__'))
    if not os.path.exists(path):
        url = 'https://raw.githubusercontent.com/nasa/NASA-3D-Resources/master/' + urllib.parse.quote('3D Models/' + rel)
        tmp = path + '.part'; urllib.request.urlretrieve(url, tmp); os.replace(tmp, path)
    plain = path[:-4] + '.plain.glb'
    if not os.path.exists(plain):     # pip bpy has no Draco bridge: decode once with DracoPy (pip install DracoPy pygltflib)
        sys.path.insert(0, _HERE); import undraco; undraco.undraco(path, plain + '.part'); os.replace(plain + '.part', plain)
    before = set(bpy.data.objects); bpy.ops.import_scene.gltf(filepath=plain)
    new = [o for o in bpy.data.objects if o not in before]
    root = link(bpy.data.objects.new(name.split(' (')[0].replace(' ', '_') + '_root', None))
    holder = link(bpy.data.objects.new('holder', None), root)
    for o in new:
        if o.parent is None: o.parent = holder
    bpy.context.view_layer.update()
    import numpy as np                 # robust bounds: ignore stray far-off parts some NASA files include
    P = []
    for o in new:
        if o.type != 'MESH' or not len(o.data.vertices): continue
        co = np.empty(len(o.data.vertices) * 3, np.float32); o.data.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
        if len(co) > 4000: co = co[np.linspace(0, len(co) - 1, 4000).astype(int)]
        M = np.array(o.matrix_world); P.append(co @ M[:3, :3].T + M[:3, 3])
    P = np.concatenate(P); lo = Vector(np.percentile(P, 1, 0)); hi = Vector(np.percentile(P, 99, 0))
    ext = hi - lo; k = size / max(ext); ctr = (lo + hi) / 2
    holder.location = -ctr * k; holder.scale = (k, k, k)
    longest = max(range(3), key=lambda i: ext[i]); want = 'XYZ'.index(align)
    if longest != want:   # rotate the longest axis onto the wanted one
        rot = {(0, 1): (0, 0, 90), (1, 0): (0, 0, -90), (2, 0): (0, -90, 0), (0, 2): (0, 90, 0), (1, 2): (-90, 0, 0), (2, 1): (90, 0, 0)}[(longest, want)]
        root.rotation_euler = tuple(math.radians(a) for a in rot)
        outer = link(bpy.data.objects.new(root.name + '_o', None)); root.parent = outer; root = outer
    for o in new:
        if o.type == 'MESH':
            for s in o.material_slots:
                if s.material and s.material.use_nodes:
                    b = s.material.node_tree.nodes.get('Principled BSDF')
                    if not b: continue
                    if b.inputs['Roughness'].default_value > .95: b.inputs['Roughness'].default_value = .55
                    if not b.inputs['Metallic'].is_linked and b.inputs['Metallic'].default_value > .5:   # pure metal reflects black space -> looks black
                        b.inputs['Metallic'].default_value = .35; b.inputs['Roughness'].default_value = max(.35, b.inputs['Roughness'].default_value)
    return root

def materials_of(root):
    """all materials under a model root (e.g. to make a NASA model glow hot during reentry)"""
    out = set(); stack = [root]
    while stack:
        o = stack.pop(); stack += list(o.children)
        if o.type == 'MESH': out |= {s.material for s in o.material_slots if s.material}
    return list(out)

def heat_glow(root, frames_strengths, color=(1, .35, .05)):
    """keyframe an emissive glow on every material of a model: frames_strengths = [(frame, strength), ...]"""
    for m in materials_of(root):
        b = m.node_tree.nodes.get('Principled BSDF') if m.use_nodes else None
        if not b: continue
        b.inputs['Emission Color'].default_value = (*color, 1)
        for f, s in frames_strengths:
            b.inputs['Emission Strength'].default_value = s; b.inputs['Emission Strength'].keyframe_insert('default_value', frame=f)


def hubble(name='hubble', real=True, size=3.3):
    """official NASA Hubble model (default) along +X; returns (root, parts). parts holds empties 'door', 'array1', 'array-1'
    for script compatibility (the NASA model is one rigid piece). real=False gives the old stylized one."""
    if not real: return hubble_procedural(name)
    root = nasa_model('Hubble Space Telescope (A)', size, 'X'); root.name = name
    parts = {k: link(bpy.data.objects.new(k, None), root) for k in ('door', 'array1', 'array-1')}
    return root, parts
