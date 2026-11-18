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
def world():
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
