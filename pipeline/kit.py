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


# ================================================================== REALISM TOOLKIT FOR NON-SPACE TOPICS
# Same standard as space shots: real data where it exists, physically based everything else.

def sky(sun_elevation=35.0, sun_rotation=200.0, strength=.12, air=1.0, dust=1.0, ozone=1.0, sun_lamp_energy=4.0):
    """Physically based daylight: Blender's Nishita atmosphere model + a matching sun lamp (same direction).
    sun_elevation in degrees above horizon (0-5 = sunrise/sunset glow, negative = twilight), rotation = compass heading."""
    sc = bpy.context.scene; w = bpy.data.worlds.new('sky'); sc.world = w; nt, N, L = nodes(w)
    out = N.new('ShaderNodeOutputWorld'); bg = N.new('ShaderNodeBackground'); st = N.new('ShaderNodeTexSky')
    st.sky_type = 'NISHITA' if 'NISHITA' in [i.identifier for i in st.bl_rna.properties['sky_type'].enum_items] else st.sky_type
    for k, v in (('sun_elevation', math.radians(sun_elevation)), ('sun_rotation', math.radians(sun_rotation)),
                 ('air_density', air), ('dust_density', dust), ('ozone_density', ozone), ('sun_disc', True)):
        if hasattr(st, k): setattr(st, k, v)
    L.new(st.outputs[0], bg.inputs['Color']); bg.inputs['Strength'].default_value = strength; L.new(bg.outputs[0], out.inputs['Surface'])
    el, az = math.radians(sun_elevation), math.radians(sun_rotation)
    d = (math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el))   # direction toward the sun
    warm = (1, .62, .38) if sun_elevation < 8 else (1, .96, .9)
    return sun_lamp(d, sun_lamp_energy if sun_elevation > 0 else .2, warm)

def mat_water(name='water', deep=(.0, .06, .09), clarity=6.0):
    """real water: IOR 1.333, glossy surface, depth absorption (blue-green), for oceans, lakes, drops"""
    m = bpy.data.materials.new(name); nt, N, L = nodes(m)
    o = N.new('ShaderNodeOutputMaterial'); g = N.new('ShaderNodeBsdfGlass'); g.inputs['IOR'].default_value = 1.333; g.inputs['Roughness'].default_value = .02
    g.inputs['Color'].default_value = (.9, .97, 1, 1)
    v = N.new('ShaderNodeVolumeAbsorption'); v.inputs['Color'].default_value = (*deep, 1); v.inputs['Density'].default_value = 1 / clarity
    L.new(g.outputs[0], o.inputs['Surface']); L.new(v.outputs[0], o.inputs['Volume']); return m

def ocean(size=60.0, wave_scale=1.2, wind=12.0, time_frames=None, choppy=1.2, foam=True, resolution=12):
    """Blender's spectral ocean simulation (Phillips/JONSWAP-style spectrum): real wave shapes, whitecaps from wind speed (m/s).
    time_frames=(f0, f1) animates it. Returns the ocean object (use with sky() for daylight)."""
    bpy.ops.mesh.primitive_plane_add(size=2); ob = bpy.context.object; ob.name = 'ocean'
    md = ob.modifiers.new('Ocean', 'OCEAN'); md.geometry_mode = 'GENERATE'; md.size = 1.0; md.spatial_size = int(size); md.wave_scale = wave_scale
    md.repeat_x = md.repeat_y = 2
    md.wind_velocity = wind; md.choppiness = choppy; md.resolution = resolution
    if hasattr(md, 'spectrum'): md.spectrum = 'PHILLIPS'
    if foam: md.use_foam = True; md.foam_layer_name = 'foam'; md.foam_coverage = .25
    if time_frames:
        f0, f1 = time_frames; md.time = 1.0; md.keyframe_insert('time', frame=f0); md.time = 1.0 + (f1 - f0) / 24; md.keyframe_insert('time', frame=f1)
        for fc in (ob.animation_data.action.fcurves if hasattr(ob.animation_data.action, 'fcurves') else []):
            for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
    m = bpy.data.materials.new('sea'); nt, N, L = nodes(m)
    o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled')
    bs.inputs['Base Color'].default_value = (.0, .045, .07, 1); bs.inputs['Roughness'].default_value = .04; bs.inputs['IOR'].default_value = 1.333
    bs.inputs['Transmission Weight'].default_value = .0
    if foam:
        at = N.new('ShaderNodeAttribute'); at.attribute_name = 'foam'
        fm = N.new('ShaderNodeMapRange'); fm.inputs['From Min'].default_value = .35; fm.inputs['From Max'].default_value = .9; L.new(at.outputs['Fac'], fm.inputs['Value'])
        mix = N.new('ShaderNodeMixRGB'); L.new(fm.outputs[0], mix.inputs['Fac']); mix.inputs[1].default_value = (.0, .045, .07, 1); mix.inputs[2].default_value = (.85, .88, .9, 1)
        L.new(mix.outputs[0], bs.inputs['Base Color'])
        rr = N.new('ShaderNodeMapRange'); rr.inputs['To Min'].default_value = .04; rr.inputs['To Max'].default_value = .7; L.new(fm.outputs[0], rr.inputs['Value']); L.new(rr.outputs[0], bs.inputs['Roughness'])
    L.new(bs.outputs[0], o.inputs[0]); ob.data.materials.append(m); smooth(ob, 0)
    return ob

def terrain(size=40.0, height=6.0, scale=3.0, detail=12, kind='rock', seed=0, res=7):
    """detailed displaced landscape (fractal ridges + erosion-like detail) with a physically based material:
    kind = 'rock' | 'desert' | 'snow' | 'grass' | 'lava' | 'volcanic' | 'ice' | 'mud'"""
    bpy.ops.mesh.primitive_plane_add(size=size); ob = bpy.context.object; ob.name = f'terrain_{kind}'
    sub = ob.modifiers.new('sub', 'SUBSURF'); sub.subdivision_type = 'SIMPLE'; sub.levels = res; sub.render_levels = res
    tx = bpy.data.textures.new('ter', 'MUSGRAVE') if hasattr(bpy.types, 'MusgraveTexture') else bpy.data.textures.new('ter', 'CLOUDS')
    if hasattr(tx, 'noise_scale'): tx.noise_scale = size / (scale * 2.5)   # big smooth landforms; fine detail comes from the material
    if hasattr(tx, 'noise_depth'): tx.noise_depth = min(detail, 6)
    disp = ob.modifiers.new('disp', 'DISPLACE'); disp.texture = tx; disp.strength = height; disp.mid_level = .5; disp.texture_coords = 'LOCAL'
    if hasattr(tx, 'noise_basis'): tx.noise_basis = 'BLENDER_ORIGINAL'
    ob.location.z = -height * .1
    pal = {'rock': ((.18, .16, .14), (.42, .38, .33), .85), 'desert': ((.55, .36, .2), (.8, .6, .38), .9), 'snow': ((.75, .78, .82), (.95, .97, 1), .45),
           'grass': ((.08, .16, .04), (.22, .3, .1), .8), 'lava': ((.03, .02, .02), (.12, .08, .06), .7), 'volcanic': ((.05, .04, .04), (.2, .17, .15), .9),
           'ice': ((.55, .72, .82), (.85, .93, .98), .15), 'mud': ((.12, .08, .05), (.28, .2, .13), .6)}[kind]
    m = bpy.data.materials.new(kind); nt, N, L = nodes(m); o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled'); tc = N.new('ShaderNodeTexCoord')
    n1 = _noise(N, L, tc.outputs['Object'], 6.0, 15, .62); n2 = _noise(N, L, tc.outputs['Object'], 60.0, 8, .55)
    cr = N.new('ShaderNodeValToRGB'); cr.color_ramp.elements[0].color = (*pal[0], 1); cr.color_ramp.elements[1].color = (*pal[1], 1)
    L.new(n1.outputs['Fac'], cr.inputs['Fac']); L.new(cr.outputs['Color'], bs.inputs['Base Color']); bs.inputs['Roughness'].default_value = pal[2]
    bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = .6; L.new(n2.outputs['Fac'], bp.inputs['Height']); L.new(bp.outputs['Normal'], bs.inputs['Normal'])
    if kind == 'lava':   # glowing cracks
        cr2 = N.new('ShaderNodeTexVoronoi'); cr2.feature = 'DISTANCE_TO_EDGE'; cr2.inputs['Scale'].default_value = 3; L.new(tc.outputs['Object'], cr2.inputs['Vector'])
        mr = N.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value = .04; mr.inputs['From Max'].default_value = 0; L.new(cr2.outputs['Distance'], mr.inputs['Value'])
        bs.inputs['Emission Color'].default_value = (1, .3, .03, 1); ms = N.new('ShaderNodeMath'); ms.operation = 'MULTIPLY'; ms.inputs[1].default_value = 25
        L.new(mr.outputs[0], ms.inputs[0]); L.new(ms.outputs[0], bs.inputs['Emission Strength'])
    if kind in ('snow', 'ice'): bs.inputs['Subsurface Weight'].default_value = .3
    L.new(bs.outputs[0], o.inputs[0]); ob.data.materials.append(m); smooth(ob, 0); return ob

def mat_pbr(kind, name=None):
    """physically based material presets with real optical values:
    skin, bone, blood, muscle, organ, glass (IOR 1.5), diamond (2.42), ice (1.31), water (1.333), gold, silver, copper, iron, steel,
    aluminium, rust, concrete, wood, plastic, rubber, fur_brown, feathers, leaf, bark, sand, rock, snow, lava, magma"""
    P = {'skin': dict(c=(.8, .55, .45), r=.45, ss=.35, ssr=(1, .35, .2)), 'bone': dict(c=(.86, .82, .72), r=.6, ss=.1),
         'blood': dict(c=(.35, .0, .01), r=.15, ss=.2), 'muscle': dict(c=(.55, .1, .1), r=.4, ss=.3, ssr=(1, .2, .2)),
         'organ': dict(c=(.55, .2, .2), r=.3, ss=.4, ssr=(1, .3, .3)), 'glass': dict(c=(1, 1, 1), r=0, tr=1, ior=1.5),
         'diamond': dict(c=(1, 1, 1), r=0, tr=1, ior=2.42), 'ice': dict(c=(.85, .95, 1), r=.05, tr=.9, ior=1.31),
         'water': dict(c=(.9, .97, 1), r=.0, tr=1, ior=1.333), 'gold': dict(c=(1.0, .77, .34), r=.2, me=1), 'silver': dict(c=(.97, .96, .91), r=.15, me=1),
         'copper': dict(c=(.95, .64, .54), r=.25, me=1), 'iron': dict(c=(.56, .57, .58), r=.4, me=1), 'steel': dict(c=(.63, .62, .6), r=.3, me=1),
         'aluminium': dict(c=(.91, .92, .92), r=.3, me=1), 'rust': dict(c=(.42, .17, .06), r=.85), 'concrete': dict(c=(.5, .5, .48), r=.9),
         'wood': dict(c=(.35, .2, .1), r=.6), 'plastic': dict(c=(.8, .8, .8), r=.35), 'rubber': dict(c=(.03, .03, .03), r=.8),
         'fur_brown': dict(c=(.3, .18, .09), r=.7, sh=1), 'feathers': dict(c=(.7, .7, .68), r=.6, sh=.6), 'leaf': dict(c=(.12, .3, .05), r=.5, ss=.2, ssr=(.4, 1, .2)),
         'bark': dict(c=(.18, .12, .08), r=.9), 'sand': dict(c=(.76, .6, .42), r=.95), 'rock': dict(c=(.35, .32, .3), r=.85), 'snow': dict(c=(.95, .96, 1), r=.5, ss=.4, ssr=(.8, .9, 1)),
         'lava': dict(c=(.05, .02, .01), r=.6, em=(1, .28, .03), es=12), 'magma': dict(c=(1, .35, .05), r=.4, em=(1, .4, .05), es=30)}[kind]
    m = bpy.data.materials.new(name or kind); m.use_nodes = True; b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*P['c'], 1); b.inputs['Roughness'].default_value = P['r']
    b.inputs['Metallic'].default_value = P.get('me', 0)
    if 'tr' in P: b.inputs['Transmission Weight'].default_value = P['tr']; b.inputs['IOR'].default_value = P['ior']
    if 'ss' in P:
        b.inputs['Subsurface Weight'].default_value = P['ss']
        if 'ssr' in P: b.inputs['Subsurface Radius'].default_value = P['ssr']
    if 'sh' in P: b.inputs['Sheen Weight'].default_value = P['sh']
    if 'em' in P: b.inputs['Emission Color'].default_value = (*P['em'], 1); b.inputs['Emission Strength'].default_value = P['es']
    return m

def volume_cloud(loc=(0, 0, 0), size=(4, 4, 2), density=3.0, color=(1, 1, 1), kind='cloud', seed=0):
    """volumetric cloud / smoke / ash / fog / storm cell (real light scattering, not a flat card).
    kind = 'cloud' | 'storm' | 'smoke' | 'ash' | 'fog' | 'steam' | 'dust'"""
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=1, location=loc); ob = bpy.context.object; ob.scale = size; ob.name = kind
    pre = {'cloud': ((1, 1, 1), .0, 2.5), 'storm': ((.35, .37, .42), .0, 4.0), 'smoke': ((.25, .24, .23), .0, 2.0), 'ash': ((.18, .16, .15), .0, 5.0),
           'fog': ((.85, .88, .9), .0, .35), 'steam': ((1, 1, 1), .0, 1.2), 'dust': ((.7, .55, .38), .0, 1.5)}[kind]
    m = bpy.data.materials.new(kind); nt, N, L = nodes(m); o = N.new('ShaderNodeOutputMaterial'); pv = N.new('ShaderNodeVolumePrincipled')
    pv.inputs['Color'].default_value = (*(color if color != (1, 1, 1) else pre[0]), 1); pv.inputs['Anisotropy'].default_value = .4
    tc = N.new('ShaderNodeTexCoord'); nz = _noise(N, L, tc.outputs['Object'], 2.2, 10, .62); [setattr(i, 'default_value', seed) for i in nz.inputs if i.name == 'W']
    ln = N.new('ShaderNodeVectorMath'); ln.operation = 'LENGTH'; L.new(tc.outputs['Object'], ln.inputs[0])
    fall = N.new('ShaderNodeMapRange'); fall.inputs['From Min'].default_value = 1.0; fall.inputs['From Max'].default_value = .35; L.new(ln.outputs['Value'], fall.inputs['Value'])
    sh = N.new('ShaderNodeMath'); sh.operation = 'MULTIPLY'; L.new(nz.outputs['Fac'], sh.inputs[0]); L.new(fall.outputs[0], sh.inputs[1])
    th = N.new('ShaderNodeMapRange'); th.inputs['From Min'].default_value = .28; th.inputs['From Max'].default_value = .55; th.inputs['To Max'].default_value = density * pre[2]
    L.new(sh.outputs[0], th.inputs['Value']); L.new(th.outputs[0], pv.inputs['Density']); L.new(pv.outputs[0], o.inputs['Volume'])
    ob.data.materials.append(m); return ob

ANATOMY_COLORS = [   # (regex, material kind, base color) – textbook/real tissue colors
    (r'skin', 'skin', (.8, .55, .45)), (r'bone|femur|tibia|fibula|humerus|radius|ulna|vertebra|rib|sternum|skull|cranial|mandible|maxilla|clavicle|scapula|pelvis|hip bone|sacrum|patella|carpal|tarsal|phalan|metacarp|metatars', 'bone', (.86, .82, .72)),
    (r'heart|myocard|ventricle|atrium', 'organ', (.55, .12, .1)), (r'aorta|artery|arterial', 'organ', (.7, .08, .06)), (r'vein|vena', 'organ', (.18, .2, .45)),
    (r'lung|bronch|trachea', 'organ', (.85, .55, .55)), (r'liver', 'organ', (.42, .12, .08)), (r'kidney', 'organ', (.45, .15, .1)),
    (r'brain|cerebr|cortex|gyrus|lobule|pons|medulla|thalamus|cerebell|midbrain|hindbrain', 'organ', (.85, .7, .65)), (r'spleen', 'organ', (.38, .1, .15)),
    (r'stomach|intestin|colon|duoden|jejun|ileum|esophag|rectum', 'organ', (.8, .5, .45)), (r'muscle|tendon', 'muscle', (.55, .1, .1)),
    (r'eye', 'organ', (.95, .95, .95)), (r'nerve|spinal cord', 'organ', (.95, .9, .6)), (r'cartilage|disc', 'bone', (.75, .8, .82)), (r'.', 'organ', (.7, .45, .4))]

def anatomy(*patterns, size=None, smooth_sub=0):
    """Real human anatomy from BodyParts3D (scanned/segmented reference male, CC BY-SA 2.1 JP — credit required).
    patterns: regexes matched against part names in assets/anatomy_parts.txt, e.g. anatomy('wall of heart', 'aorta'),
    anatomy('lobe of .* lung'), anatomy('femur'). Real proportions (mm -> m). Returns an empty holding all parts;
    size=<units> rescales so the whole group's longest side = size. Downloads parts once to NASA_CACHE/anatomy."""
    import re, numpy as np
    cat = [l.rstrip('\n').split('\t') for l in open(os.path.join(os.path.dirname(tex_path('earth_day.jpg')), '..', 'anatomy_parts.txt'))]
    picks = [(fid, nm) for fid, nm in cat if any(re.search(p, nm, re.I) for p in patterns)]
    if not picks: raise ValueError(f'no anatomy part matches {patterns}')
    cdir = os.path.join(NASA_CACHE, 'anatomy'); os.makedirs(cdir, exist_ok=True)
    root = link(bpy.data.objects.new('anatomy', None)); holder = link(bpy.data.objects.new('anatomy_holder', None), root)
    mats = {}
    for fid, nm in picks:
        p = os.path.join(cdir, fid + '.stl')
        if not os.path.exists(p):
            urllib.request.urlretrieve(f'https://raw.githubusercontent.com/Kevin-Mattheus-Moerman/BodyParts3D/HEAD/assets/BodyParts3D_data/stl/{fid}.stl', p + '.part'); os.replace(p + '.part', p)
        bpy.ops.wm.stl_import(filepath=p); ob = bpy.context.selected_objects[0]; ob.name = nm[:60]; ob.parent = holder; ob.scale = (.001, .001, .001)
        for rx, kind, col in ANATOMY_COLORS:
            if re.search(rx, nm, re.I):
                key = (kind, col)
                if key not in mats: mats[key] = mat_pbr(kind, f'anat_{kind}_{len(mats)}'); mats[key].node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (*col, 1)
                ob.data.materials.append(mats[key]); break
        smooth(ob, smooth_sub)
    bpy.context.view_layer.update()
    P = np.array([ob.matrix_world @ Vector(c) for ob in holder.children for c in ob.bound_box])
    lo, hi = P.min(0), P.max(0); ctr = (lo + hi) / 2; k = (size / max(hi - lo)) if size else 1.0
    holder.location = Vector(-ctr * k); holder.scale = (k, k, k)
    return root

def scale_ref(height_m=1.8, loc=(0, 0, 0)):
    """the white astronaut mascot scaled to a real person's height, for honest size comparisons"""
    root, limbs = astronaut(); bpy.context.view_layer.update()
    pts = [root.matrix_world @ Vector(c) for o in root.children_recursive if o.type == 'MESH' for c in o.bound_box]
    h = max(p.z for p in pts) - min(p.z for p in pts); s = height_m / h if h else 1
    root.scale = (s, s, s); root.location = loc; return root, limbs


def latlon(lat, lon, R, face_lon=-80.0, h=0.0):
    """position of a real latitude/longitude on kit.earth(R, face_lon=...) in the earth's SPIN frame
    (parent objects to the returned `spin` empty, or use with tilt_deg=0 and no spin rotation). h = height above surface."""
    la, lo = math.radians(lat), math.radians(lon - 90 - face_lon)
    return Vector((math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la))) * (R + h)

def geo_path(points, R, face_lon=-80.0, h=0.004, width=0.012, color=(1, .78, .25), strength=8.0, name='route', steps=24):
    """glowing route along real lat/lon waypoints, hugging the globe (great-circle interpolation between waypoints).
    Animate obj.data.bevel_factor_end 0->1 to draw it."""
    pts = []
    for (a1, o1), (a2, o2) in zip(points[:-1], points[1:]):
        p1, p2 = latlon(a1, o1, 1, face_lon), latlon(a2, o2, 1, face_lon)
        for k in range(steps):
            t = k / steps; v = p1.slerp(p2, t) if hasattr(p1, 'slerp') else (p1 * (1 - t) + p2 * t)
            pts.append(v.normalized() * (R + h))
    pts.append(latlon(*points[-1], R, face_lon, h))
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = width; cu.bevel_resolution = 3
    cu.use_fill_caps = True; sp = cu.splines.new('POLY'); sp.points.add(len(pts) - 1)
    for p, v in zip(sp.points, pts): p.co = (v.x, v.y, v.z, 1)
    ob = link(bpy.data.objects.new(name, cu)); ob.data.materials.append(mat_emit(name + '_m', color, strength)); return ob


# ================================================================== CARTOON CAST (story style like the user's 2nd reference)
# Recurring characters: big round heads with expressive faces, simple stick bodies, bold colored clothes.
# Faces are textures from faces.py (assets/faces/<expr>.png): neutral, surprised, worried, smirk, happy, angry, scared, bored.
CAST = {   # name: hair style, hair color, shirt color, stripe color (or None), pants color, voice for dialogue
    'kai':  dict(hair='spiky', hair_c=(.28, .12, .05), shirt=(.32, .38, .12), stripe=None, pants=(.08, .08, .09), voice='am_michael'),
    'leo':  dict(hair='curly', hair_c=(.85, .35, .07), shirt=(.95, .7, .1), stripe=(.08, .07, .06), pants=(.08, .08, .09), voice='am_echo'),
    'mia':  dict(hair='bob', hair_c=(.15, .08, .05), shirt=(.75, .15, .2), stripe=None, pants=(.1, .12, .25), voice='af_heart'),
    'nora': dict(hair='beanie', hair_c=(.9, .25, .08), shirt=(.2, .45, .75), stripe=(.95, .95, .95), pants=(.15, .15, .15), voice='af_nova'),
}
EXPRS = ['neutral', 'surprised', 'worried', 'smirk', 'happy', 'angry', 'scared', 'bored']

def _face_mat(name):
    """head material holding all expressions; switch with set_expr(char, frame, 'surprised')"""
    m = bpy.data.materials.new(f'{name}_face'); nt, N, L = nodes(m)
    o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled'); bs.inputs['Roughness'].default_value = .55
    bs.inputs['Subsurface Weight'].default_value = .08
    uv = N.new('ShaderNodeTexCoord'); val = N.new('ShaderNodeValue'); val.name = 'expr'; val.outputs[0].default_value = 0
    prev = None
    for k, ex in enumerate(EXPRS):
        t = N.new('ShaderNodeTexImage'); t.image = bpy.data.images.load(os.path.join(os.path.dirname(tex_path('earth_day.jpg')), '..', 'faces', f'{ex}.png'), check_existing=True)
        L.new(uv.outputs['UV'], t.inputs['Vector'])
        if prev is None: prev = t.outputs['Color']; continue
        cmp = N.new('ShaderNodeMath'); cmp.operation = 'COMPARE'; cmp.inputs[1].default_value = k; cmp.inputs[2].default_value = .5
        L.new(val.outputs[0], cmp.inputs[0])
        mx = N.new('ShaderNodeMixRGB'); L.new(cmp.outputs[0], mx.inputs['Fac']); L.new(prev, mx.inputs[1]); L.new(t.outputs['Color'], mx.inputs[2]); prev = mx.outputs[0]
    L.new(prev, bs.inputs['Base Color']); L.new(bs.outputs[0], o.inputs[0]); return m

def _cloth(name, color, stripe=None, scale=9.0):
    m = bpy.data.materials.new(name); nt, N, L = nodes(m); o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled')
    bs.inputs['Roughness'].default_value = .8; bs.inputs['Sheen Weight'].default_value = .4
    if stripe:
        tc = N.new('ShaderNodeTexCoord'); wv = N.new('ShaderNodeTexWave'); wv.wave_type = 'BANDS'; wv.bands_direction = 'Z'; wv.inputs['Scale'].default_value = scale
        L.new(tc.outputs['Object'], wv.inputs['Vector']); st = N.new('ShaderNodeMath'); st.operation = 'GREATER_THAN'; st.inputs[1].default_value = .5
        L.new(wv.outputs['Fac'], st.inputs[0]); mx = N.new('ShaderNodeMixRGB'); L.new(st.outputs[0], mx.inputs['Fac'])
        mx.inputs[1].default_value = (*color, 1); mx.inputs[2].default_value = (*stripe, 1); L.new(mx.outputs[0], bs.inputs['Base Color'])
    else: bs.inputs['Base Color'].default_value = (*color, 1)
    L.new(bs.outputs[0], o.inputs[0]); return m

def character(who='kai', loc=(0, 0, 0), height=1.0):
    """a cartoon cast member (head ~ 0.45 of the height, like the reference). returns (root, parts):
    parts = head, face_mat, arm_l, arm_r, leg_l, leg_r, body. Pose arms with rotation_euler on the arm empties (pivot at the shoulder)."""
    c = CAST[who]; root = link(bpy.data.objects.new(f'{who}', None)); root.location = loc; root.scale = (height, height, height)
    ink = mat_principled(f'{who}_ink', (.03, .03, .035), .6)
    # body
    bpy.ops.mesh.primitive_cylinder_add(radius=.12, depth=.32, location=(0, 0, .42)); body = bpy.context.object; body.parent = root
    bev = body.modifiers.new('b', 'BEVEL'); bev.width = .05; bev.segments = 6; body.data.materials.append(_cloth(f'{who}_shirt', c['shirt'], c['stripe'])); smooth(body, 1)
    bpy.ops.mesh.primitive_cylinder_add(radius=.115, depth=.08, location=(0, 0, .24)); hip = bpy.context.object; hip.parent = root; hip.data.materials.append(mat_principled(f'{who}_pants', c['pants'], .7))
    # legs and arms: thin dark sticks (pivot empties so they can swing)
    parts = {'body': body}
    for side, nm in ((-1, 'leg_l'), (1, 'leg_r')):
        piv = link(bpy.data.objects.new(f'{who}_{nm}', None), root); piv.location = (side * .055, 0, .22)
        bpy.ops.mesh.primitive_cylinder_add(radius=.018, depth=.22, location=(0, 0, -.11)); lg = bpy.context.object; lg.parent = piv; lg.data.materials.append(ink)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=.04, location=(side * .01, -.02, -.23)); ft = bpy.context.object; ft.scale = (1, 1.6, .6); ft.parent = piv; ft.data.materials.append(ink)
        parts[nm] = piv
    for side, nm in ((-1, 'arm_l'), (1, 'arm_r')):
        piv = link(bpy.data.objects.new(f'{who}_{nm}', None), root); piv.location = (side * .125, 0, .55)
        bpy.ops.mesh.primitive_cylinder_add(radius=.016, depth=.24, location=(0, 0, -.12)); ar = bpy.context.object; ar.parent = piv; ar.data.materials.append(ink)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=.03, location=(0, 0, -.25)); hd = bpy.context.object; hd.parent = piv; hd.data.materials.append(ink)
        piv.rotation_euler = (0, side * math.radians(12), 0); parts[nm] = piv
    # neck + big head with the face texture
    bpy.ops.mesh.primitive_cylinder_add(radius=.025, depth=.06, location=(0, 0, .6)); nk = bpy.context.object; nk.parent = root; nk.data.materials.append(ink)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=.22, segments=64, ring_count=32, location=(0, 0, .8)); head = bpy.context.object; head.parent = root
    head.scale = (1, .95, .92); head.rotation_euler = (0, 0, math.radians(-90)); fm = _face_mat(who); head.data.materials.append(fm); smooth(head, 1); parts['head'] = head; parts['face_mat'] = fm
    # hair
    hm = mat_principled(f'{who}_hair', c['hair_c'], .75)
    if c['hair'] == 'curly':
        for k in range(26):
            a = k / 26 * 2 * math.pi; z = .93 + .06 * math.sin(3 * a)
            bpy.ops.mesh.primitive_uv_sphere_add(radius=.06, location=(.17 * math.cos(a), .14 * math.sin(a) + .03, z)); b = bpy.context.object; b.parent = root; b.data.materials.append(hm)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=.2, location=(0, .03, .9)); cap = bpy.context.object; cap.scale = (1, 1, .55); cap.parent = root; cap.data.materials.append(hm)
    elif c['hair'] == 'spiky':
        bpy.ops.mesh.primitive_uv_sphere_add(radius=.215, location=(0, .03, .86)); cap = bpy.context.object; cap.scale = (1.02, 1, .62); cap.parent = root; cap.data.materials.append(hm)
        for k in range(9):
            a = math.radians(-70 + k * 17.5); bpy.ops.mesh.primitive_cone_add(radius1=.05, depth=.14, location=(.15 * math.sin(a), .05 + .06 * math.cos(a), .99))
            sp = bpy.context.object; sp.rotation_euler = (math.radians(-25), math.radians(35 * math.sin(a)), 0); sp.parent = root; sp.data.materials.append(hm)
    elif c['hair'] == 'beanie':
        bpy.ops.mesh.primitive_uv_sphere_add(radius=.225, location=(0, .02, .88)); cap = bpy.context.object; cap.scale = (1, 1, .7); cap.parent = root
        cap.data.materials.append(_cloth(f'{who}_beanie', c['hair_c'], (min(1, c['hair_c'][0] * .8), c['hair_c'][1] * .8, c['hair_c'][2] * .8), 28))
    else:   # bob
        bpy.ops.mesh.primitive_uv_sphere_add(radius=.235, location=(0, .04, .82)); cap = bpy.context.object; cap.scale = (1.02, 1, .85); cap.parent = root; cap.data.materials.append(hm)
    for o in (cap,): smooth(o, 1)
    return root, parts

def set_expr(parts, frame, expr):
    """switch a character's face at a frame (instant, like the reference's quick reaction cuts)"""
    v = parts['face_mat'].node_tree.nodes['expr'].outputs[0]; v.default_value = EXPRS.index(expr); v.keyframe_insert('default_value', frame=frame)
    for fc in getattr(parts['face_mat'].node_tree.animation_data.action, 'fcurves', []):
        for kp in fc.keyframe_points: kp.interpolation = 'CONSTANT'

def talk(parts, f0, f1, amp=6):
    """small head bobs while a character speaks"""
    h = parts['head']; base = tuple(h.rotation_euler)
    for k, f in enumerate(range(f0, f1, 5)): h.rotation_euler = (base[0] + math.radians(amp * (k % 2)), base[1], base[2] + math.radians(amp * .5 * ((k + 1) % 2))); h.keyframe_insert('rotation_euler', frame=f)
    h.rotation_euler = base; h.keyframe_insert('rotation_euler', frame=f1)
