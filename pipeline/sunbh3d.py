"""3D Short: What if the Sun turned into a black hole?  Usage: python3 sunbh3d.py <scene> still|anim [frac]"""
import sys, math, json, os, random
sys.path.insert(0, '/home/claude/b3d')
import bpy, kit
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

CFG = json.load(open('/home/claude/b3d/sunbh/topic.json'))
FPS = 24; DURS = CFG['durs']; PAD = 0.75; OUT = CFG['root']
idx, mode = int(sys.argv[1]), sys.argv[2]
D = DURS[idx]; NF = int(math.ceil((D + PAD) * FPS))
sc = kit.reset(res=(648, 1152), samples=8)
sc.render.use_persistent_data = True; sc.cycles.adaptive_threshold = 0.05
try:
    sc.cycles.denoising_quality = 'FAST'; sc.cycles.denoising_prefilter = 'FAST'
except Exception: pass
sc.cycles.max_bounces = 4; sc.cycles.diffuse_bounces = 1; sc.cycles.glossy_bounces = 1; sc.cycles.transparent_max_bounces = 6
sc.frame_start, sc.frame_end = 1, NF
F = lambda sec: 1 + int(round((sec + .35) * FPS))     # scene-local seconds -> frame (frames start 0.35 s early for the crossfade)
overlays = []
rng = random.Random(idx + 3)

def kf_input(sock, frame, value):
    sock.default_value = value; sock.keyframe_insert('default_value', frame=frame)

def project(cam, loc, frame):
    sc.frame_set(frame); v = world_to_camera_view(sc, cam, Vector(loc)); return (v.x, 1 - v.y)

CUTS = []
def cuts(*cams_at):
    """cams_at: (camera_object, local_seconds) ... -> hard cuts between cameras"""
    for k, (cam, sec) in enumerate(cams_at):
        CUTS.append((cam, max(1, F(sec) if sec > 0 else 1)))
        m = sc.timeline_markers.new(f'cut{k}', frame=max(1, F(sec) if sec > 0 else 1)); m.camera = cam

def keylights(target):
    for name, loc, col, en in [('key', (2.5, -6, 2), (1, .95, .9), 160), ('rim', (-3, 3, 2), (.5, .65, 1), 260)]:
        li = bpy.data.lights.new(name, 'AREA'); li.energy = en; li.color = col; li.size = 3
        o = kit.link(bpy.data.objects.new(name, li)); o.location = loc
        c = o.constraints.new('TRACK_TO'); c.target = target; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'

def no_ice():
    bpy.data.materials['earth'].node_tree.nodes['ice'].inputs[1].default_value = .95

def big_earth(R=14, z=-15.6, sun=(1, -.3, .25), clouds=False):
    root, sp = kit.earth(R, sun, tilt_deg=15, clouds=clouds, atmo=True); root.location = (0, 6, z); no_ice()
    kit.key(sp, 1, rotation_euler=(0, 0, 0)); kit.key(sp, NF, rotation_euler=(0, 0, math.radians(1.2 * NF / FPS)))
    return root

def debris(n, center, spread, mat_strength=10):
    objs = []
    for i in range(n):
        bpy.ops.mesh.primitive_cube_add(size=rng.uniform(.08, .22), location=(center[0] + rng.uniform(-spread, spread), center[1] + rng.uniform(-spread, spread), center[2] + rng.uniform(-spread, spread)))
        o = bpy.context.object; o.rotation_euler = (rng.random() * 6, rng.random() * 6, rng.random() * 6)
        o.data.materials.append(kit.mat_emit(f'deb{i}', (1, .35 + rng.random() * .25, .08), mat_strength)); objs.append(o)
    return objs

def trail(obj, length=1.6, radius=.06, color=(1, .2, .01), strength=4):
    bpy.ops.mesh.primitive_cone_add(radius1=radius, radius2=0, depth=length, location=(0, 0, length / 2))
    t = bpy.context.object; t.data.materials.append(kit.mat_emit('trail', color, strength)); t.parent = obj; return t

def reentry_setup(glow_from=1.0, glow_to=1.0, cam_start=(2.0, -7.2, 1.1), cam_end=(1.6, -6.5, .8)):
    """Hubble plunging (moving down/forward) inside a plasma sheath above Earth's limb"""
    kit.world(); kit.sun_lamp((1, -.3, .25), 3.5)
    big_earth()
    mover = kit.link(bpy.data.objects.new('mover', None)); mover.rotation_euler = (math.radians(-35), math.radians(25), 0)
    h, parts = kit.hubble(); h.parent = mover; h.rotation_euler = (math.radians(20), math.radians(-60), math.radians(10))
    s, m = kit.fireball(mover, length=3.6, radius=.95, strength=6)
    fade = m.node_tree.nodes['plasma_fade'].inputs[1]
    kf_input(fade, 1, glow_from); kf_input(fade, NF, glow_to)
    kit.key(mover, 1, location=(0, 0, .3)); kit.key(mover, NF, location=(-.25, .1, -.15))
    kit.key(h, 1, rotation_euler=(math.radians(20), math.radians(-60), math.radians(10))); kit.key(h, NF, rotation_euler=(math.radians(32), math.radians(-52), math.radians(40)))
    for mn in ('hst_foil', 'hst_white'):            # hull glowing hot
        b = bpy.data.materials[mn].node_tree.nodes['Principled BSDF']; b.inputs['Emission Color'].default_value = (1, .3, .05, 1)
        kf_input(b.inputs['Emission Strength'], 1, 1.2 * glow_from); kf_input(b.inputs['Emission Strength'], NF, 1.2 * glow_to)
    li = bpy.data.lights.new('plasma_light', 'POINT'); li.energy = 1400; li.color = (1, .5, .15); kit.link(bpy.data.objects.new('plasma_light', li)).parent = mover
    keylights(mover)
    cam, tgt = kit.camera(cam_start, (0, 0, .1), lens=30)
    kit.key(cam, 1, location=cam_start); kit.key(cam, NF, location=cam_end)
    return cam, mover, h, parts

NOPLATE = False

def sun_ball(loc=(0, 0, 0), r=1.0, strength=.7, name='sunball'):
    """glowing stylized Sun: granulated emissive surface + soft corona shell. 'sun_fade' node scales brightness."""
    m = bpy.data.materials.new(name); nt, N, L = kit.nodes(m)
    o = N.new('ShaderNodeOutputMaterial'); tc = N.new('ShaderNodeTexCoord')
    nz = kit._noise(N, L, tc.outputs['Object'], 3.5 / r, 8, .6)
    cr = N.new('ShaderNodeValToRGB'); c = cr.color_ramp
    c.elements[0].position = .35; c.elements[0].color = (1, .16, .0, 1); c.elements[1].position = .7; c.elements[1].color = (1, .62, .12, 1)
    L.new(nz.outputs['Fac'], cr.inputs['Fac'])
    e = N.new('ShaderNodeEmission'); L.new(cr.outputs['Color'], e.inputs['Color'])
    f = N.new('ShaderNodeMath'); f.name = 'sun_fade'; f.operation = 'MULTIPLY'; f.inputs[0].default_value = strength; f.inputs[1].default_value = 1.0
    L.new(f.outputs[0], e.inputs['Strength']); L.new(e.outputs[0], o.inputs[0])
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, segments=96, ring_count=48, location=loc); s = bpy.context.object
    s.data.materials.append(m); kit.smooth(s, 0)
    cm = bpy.data.materials.new(name + '_corona'); nt2, N2, L2 = kit.nodes(cm)
    o2 = N2.new('ShaderNodeOutputMaterial'); lw = N2.new('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = .5
    inv = N2.new('ShaderNodeMath'); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0; L2.new(lw.outputs['Facing'], inv.inputs[1])
    pw = N2.new('ShaderNodeMath'); pw.operation = 'POWER'; pw.inputs[1].default_value = 2.5; L2.new(inv.outputs[0], pw.inputs[0])
    e2 = N2.new('ShaderNodeEmission'); e2.inputs['Color'].default_value = (1, .55, .15, 1)
    f2 = N2.new('ShaderNodeMath'); f2.name = 'sun_fade'; f2.operation = 'MULTIPLY'; f2.inputs[0].default_value = .5; f2.inputs[1].default_value = 1.0
    L2.new(f2.outputs[0], e2.inputs['Strength'])
    tr = N2.new('ShaderNodeBsdfTransparent'); mx = N2.new('ShaderNodeMixShader')
    L2.new(pw.outputs[0], mx.inputs['Fac']); L2.new(tr.outputs[0], mx.inputs[1]); L2.new(e2.outputs[0], mx.inputs[2]); L2.new(mx.outputs[0], o2.inputs[0])
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r * 1.35, segments=64, ring_count=32, location=loc); co = bpy.context.object
    co.data.materials.append(cm); kit.smooth(co, 0); co.parent = s; co.location = (0, 0, 0)
    for ob in (s, co):
        for attr in ('visible_shadow',): setattr(ob, attr, False)
    return s, [m.node_tree.nodes['sun_fade'].inputs[1], cm.node_tree.nodes['sun_fade'].inputs[1]]

def sun_fade(socks, frame, v):
    for s in socks: kf_input(s, frame, v)

def bh_small(loc, R, cam):
    """Sun-mass black hole with nothing feeding it: a black sphere and a thin ring of lensed starlight (no glowing disk)"""
    root = kit.link(bpy.data.objects.new('BHs', None)); root.location = loc
    bpy.ops.mesh.primitive_uv_sphere_add(radius=R, segments=64, ring_count=32); s = bpy.context.object
    s.data.materials.append(kit.mat_emit('void', (0, 0, 0), 0.0)); kit.smooth(s, 1); s.parent = root; s.visible_shadow = False
    hr = kit.link(bpy.data.objects.new('bh_ring_root', None), root)
    for k, (rr, mr, st) in enumerate([(1.06, .012, 6), (1.3, .09, .25)]):
        bpy.ops.mesh.primitive_torus_add(major_radius=R * rr, minor_radius=R * mr, major_segments=160, minor_segments=8); t = bpy.context.object
        t.data.materials.append(kit.mat_emit(f'bhring{k}', (.75, .85, 1), st)); t.parent = hr; t.rotation_euler = (math.radians(90), 0, 0)
    c = hr.constraints.new('TRACK_TO'); c.target = cam; c.track_axis = 'TRACK_NEGATIVE_Y'; c.up_axis = 'UP_Z'
    return root

def orbit_ring(r, center=(0, 0, 0), tilt=(0, 0, 0), strength=1.5, color=(.6, .8, 1), name='orbit'):
    bpy.ops.mesh.primitive_torus_add(major_radius=r, minor_radius=.012 * max(1, r / 4), major_segments=256, minor_segments=6, location=center); t = bpy.context.object
    t.rotation_euler = tilt; t.data.materials.append(kit.mat_emit(name, color, strength)); return t

def flash(loc, t0, size=.5, color=(1, .9, .7)):
    m = bpy.data.materials.new('flash'); nt, N, L = kit.nodes(m)
    o = N.new('ShaderNodeOutputMaterial'); e = N.new('ShaderNodeEmission'); e.inputs['Color'].default_value = (*color, 1)
    tr = N.new('ShaderNodeBsdfTransparent'); mx = N.new('ShaderNodeMixShader'); e.inputs['Strength'].default_value = 6
    L.new(tr.outputs[0], mx.inputs[1]); L.new(e.outputs[0], mx.inputs[2]); L.new(mx.outputs[0], o.inputs[0])
    bpy.ops.mesh.primitive_uv_sphere_add(radius=size, location=loc); fl = bpy.context.object; fl.data.materials.append(m)
    for a in ('visible_shadow', 'visible_diffuse'): setattr(fl, a, False)
    kit.key(fl, 1, scale=(.05,) * 3); kit.key(fl, F(t0), scale=(.05,) * 3); kit.key(fl, F(t0 + .5), scale=(1.4,) * 3)
    kf_input(mx.inputs['Fac'], 1, 0); kf_input(mx.inputs['Fac'], F(t0), 0); kf_input(mx.inputs['Fac'], F(t0 + .08), .7); kf_input(mx.inputs['Fac'], F(t0 + .5), 0)

def earth_mat_nodes():
    nt = bpy.data.materials['earth'].node_tree
    night = [n for n in nt.nodes if n.type == 'MAP_RANGE' and abs(n.inputs['From Max'].default_value + 0.2) < 1e-6][0]
    return nt.nodes['ice'].inputs[1], night

def dim_cities(v=1.3):
    for n in bpy.data.materials['earth'].node_tree.nodes:
        if n.type == 'MATH' and n.operation == 'MULTIPLY' and abs(n.inputs[1].default_value - 3.0) < 1e-6: n.inputs[1].default_value = v

def dark_earth(R=2.4, loc=(0, 0, 0), ice=.30, atmo_str=.55):
    """Earth after the light is gone: night everywhere (city lights), faint starlight fill, ice spreading"""
    root, sp = kit.earth(R, (0, 1, 0), tilt_deg=20, clouds=True, atmo=True); root.location = loc
    icei, night = earth_mat_nodes(); icei.default_value = ice
    night.inputs['From Min'].default_value = 1.0; night.inputs['From Max'].default_value = .9   # every side is the night side
    bpy.data.materials['atmo'].node_tree.nodes['Emission'].inputs['Strength'].default_value = atmo_str
    dim_cities()
    return root, sp, icei

HOOK_CAM = ((-1.2, -9.0, 1.6), (-1.5, -8.2, 1.3))      # s0 camera start/end; s8 ends on HOOK_CAM[0] for the loop
def hook_set(ice):
    kit.world()
    kit.sun_lamp((-.6, -.5, .6), 1.1, (.55, .65, 1))                     # faint starlight fill so the planet still reads
    root, sp, icei = dark_earth(2.4, (.9, 0, -2.2), ice)
    kit.key(sp, 1, rotation_euler=(0, 0, 0)); kit.key(sp, NF, rotation_euler=(0, 0, math.radians(2)))
    cam, _ = kit.camera(HOOK_CAM[0], (-.4, 0, 1.0), lens=32)
    bh = bh_small((-2.4, 9, 4.2), .55, cam)
    orbit_ring(14, (-2.4, 9, 4.2), (math.radians(78), 0, math.radians(18)), 1.2)
    return cam, icei

# ======================================================================= scenes
def s0_hook():                  # "Earth would keep orbiting, in the dark."
    cam, icei = hook_set(.30)
    kit.key(cam, 1, location=HOOK_CAM[0]); kit.key(cam, NF, location=HOOK_CAM[1])

def s1_question():              # "What if the Sun suddenly turned into a black hole?"
    kit.world(); SD = (Vector((2.6, 0, 2.4)) - Vector((-1.4, -3.2, -1.8))).normalized(); kit.sun_lamp(tuple(SD), 4.2)
    root, sp = kit.earth(1.0, tuple(SD), tilt_deg=20, clouds=True, atmo=True); root.location = (-1.4, -3.2, -1.8)
    cam, _ = kit.camera((-1.0, -9.5, -.8), (.4, 0, .4), lens=30)
    kit.key(cam, 1, location=(-1.2, -9.8, -.9)); kit.key(cam, NF, location=(-.8, -9.0, -.7))
    s, socks = sun_ball((2.6, 0, 2.4), 1.2)
    tc = D * .5
    kit.key(s, 1, scale=(1,) * 3); kit.key(s, F(tc - .9), scale=(1,) * 3); kit.key(s, F(tc), scale=(.02,) * 3)
    sun_fade(socks, F(tc - .9), 1); sun_fade(socks, F(tc), 4)
    bh = bh_small((2.6, 0, 2.4), .26, cam)
    kit.key(bh, 1, scale=(.001,) * 3); kit.key(bh, F(tc - .05), scale=(.001,) * 3); kit.key(bh, F(tc + .3), scale=(1,) * 3)
    flash((2.6, 0, 2.4), tc - .1, .7)

def s2_cant():                  # "it can't... the Sun isn't massive enough, and it will end as a white dwarf."
    kit.world()
    s, socks = sun_ball((0, 0, 0), 1.6)
    cam, _ = kit.camera((0, -9, .8), (0, 0, 0), lens=34)
    kit.key(cam, 1, location=(-.4, -9.4, .9)); kit.key(cam, NF, location=(.3, -8.4, .6))
    tw = D * .5
    kit.key(s, 1, scale=(1,) * 3); kit.key(s, F(tw - 1.2), scale=(1,) * 3); kit.key(s, F(tw), scale=(.001,) * 3)
    # white dwarf: small, white-hot, plus a faint drifting shell of the shed outer layers
    bpy.ops.mesh.primitive_uv_sphere_add(radius=.16, segments=48, ring_count=24); wd = bpy.context.object
    wd.data.materials.append(kit.mat_emit('wd', (.75, .85, 1), 40))
    kit.key(wd, 1, scale=(.001,) * 3); kit.key(wd, F(tw - .5), scale=(.001,) * 3); kit.key(wd, F(tw), scale=(1,) * 3)
    bpy.ops.mesh.primitive_torus_add(major_radius=1, minor_radius=.025, major_segments=128, minor_segments=8); neb = bpy.context.object
    neb.rotation_euler = (math.radians(70), 0, math.radians(20)); neb.data.materials.append(kit.mat_emit('neb', (.3, .7, 1), .4))
    kit.key(neb, 1, scale=(.001,) * 3); kit.key(neb, F(tw - .8), scale=(.6,) * 3); kit.key(neb, NF, scale=(2.2,) * 3)
    cam2, _ = kit.camera((1.6, -4.2, 1.4), (0, 0, 0), lens=34)
    kit.key(cam2, 1, location=(1.6, -4.4, 1.4)); kit.key(cam2, NF, location=(1.4, -3.9, 1.2))
    cuts((cam, 0), (cam2, tw + .3))
    overlays.append({'type': 'label', 'text': 'THE SUN WILL BECOME A WHITE DWARF', 'pos': (.5, .16), 'color': (170, 215, 255)})

def s3_crush():                 # "all of its mass crushed into a ball only about six kilometers wide."
    kit.world()
    cam, _ = kit.camera((0, -8.5, .4), (0, 0, 0), lens=34)
    kit.key(cam, 1, location=(0, -9.2, .5)); kit.key(cam, NF, location=(0, -7.6, .3))
    s, socks = sun_ball((0, 0, 0), 2.0)
    tc = D * .55
    kit.key(s, 1, scale=(1,) * 3); kit.key(s, F(tc), scale=(.04,) * 3); sun_fade(socks, 1, 1); sun_fade(socks, F(tc), 3)
    kit.key(s, F(tc + .15), scale=(.001,) * 3)
    bh = bh_small((0, 0, 0), .3, cam)
    kit.key(bh, 1, scale=(.001,) * 3); kit.key(bh, F(tc), scale=(.001,) * 3); kit.key(bh, F(tc + .4), scale=(1,) * 3)
    flash((0, 0, 0), tc - .05, .6)
    overlays.append({'type': 'label', 'text': '≈ 6 KM WIDE', 'pos': (.5, .2), 'color': (255, 222, 40)})

def s4_pull():                  # "Same mass, same distance, so its pull on Earth would stay the same."
    kit.world(); kit.sun_lamp((-1, -.25, .2), 4.0)
    cam, _ = kit.camera((.4, -10, 2.2), (.4, 0, 0), lens=30)
    kit.key(cam, 1, location=(.2, -10.4, 2.4)); kit.key(cam, NF, location=(.6, -9.4, 2.0))
    bh = bh_small((-2.6, 0, .6), .3, cam)
    root, sp = kit.earth(1.0, (-1, -.25, .2), tilt_deg=20, clouds=True, atmo=True); root.location = (2.6, 0, -.6)
    # gravity tether: dashes flowing from Earth toward the black hole
    a, b = Vector((2.6, 0, -.6)), Vector((-2.6, 0, .6)); d = (b - a); n = 14
    for i in range(n):
        bpy.ops.mesh.primitive_cylinder_add(radius=.035, depth=.22); c = bpy.context.object
        c.rotation_euler = d.to_track_quat('Z', 'Y').to_euler(); c.data.materials.append(kit.mat_emit(f'g{i}', (1, .8, .3), 5))
        u0 = i / n
        for f in range(1, NF + 1, 4):
            u = (u0 + (f - 1) / FPS * .12) % 1.0; u = .16 + u * .7
            kit.key(c, f, location=a + d * u)
    kit.key(sp, 1, rotation_euler=(0, 0, 0)); kit.key(sp, NF, rotation_euler=(0, 0, math.radians(8)))
    overlays.append({'type': 'label', 'text': 'SAME MASS = SAME PULL', 'pos': (.5, .2), 'color': (255, 222, 40)})

def s5_circle():                # "Earth wouldn't get sucked in. It would keep circling, just like today."
    global NOPLATE; NOPLATE = True
    kit.world()
    li = bpy.data.lights.new('lastlight', 'POINT'); li.energy = 60000; li.color = (1, .95, .88); li.shadow_soft_size = .3
    kit.link(bpy.data.objects.new('lastlight', li)).location = (0, 0, 0)       # sunlight still arriving from where the Sun was
    cam, _ = kit.camera((0, -10, 6.5), (.6, 0, 0), lens=36)
    kit.key(cam, 1, location=(.4, -10.6, 7.0)); kit.key(cam, NF, location=(1.0, -9.6, 6.2))
    bh_small((0, 0, 0), .35, cam)
    R = 2.9; orbit_ring(R, (0, 0, 0), (0, 0, 0), 1.6)
    root, sp = kit.earth(.5, (-math.cos(.05), -math.sin(.05), 0), tilt_deg=20, clouds=True, atmo=True)
    for f in range(1, NF + 1, 3):
        ang = math.radians(-25) + (f - 1) / NF * math.radians(55)
        kit.key(root, f, location=(R * math.cos(ang), R * math.sin(ang), 0))
    kit.key(sp, 1, rotation_euler=(0, 0, 0)); kit.key(sp, NF, rotation_euler=(0, 0, math.radians(60)))

def s6_eight():                 # "For about eight minutes, nobody would notice..."
    global NOPLATE; NOPLATE = True
    kit.world()
    li = bpy.data.lights.new('lastlight', 'POINT'); li.color = (1, .95, .88); li.shadow_soft_size = .3
    lo = kit.link(bpy.data.objects.new('lastlight', li)); lo.location = (-4.6, 0, .4)
    li.energy = 30000; li.keyframe_insert('energy', frame=1); li.keyframe_insert('energy', frame=F(D * .82)); li.energy = 400; li.keyframe_insert('energy', frame=NF)
    cam, _ = kit.camera((.2, -9.5, 1.2), (.2, 0, .2), lens=30)
    kit.key(cam, 1, location=(0, -10, 1.3)); kit.key(cam, NF, location=(.4, -9.2, 1.1))
    bh_small((-4.6, 0, .4), .3, cam)
    root, sp = kit.earth(1.1, (-1, 0, 0), tilt_deg=20, clouds=True, atmo=True); root.location = (2.1, 0, -.2)
    kit.key(sp, 1, rotation_euler=(0, 0, 0)); kit.key(sp, NF, rotation_euler=(0, 0, math.radians(10)))
    # the last sunlight still in flight: photon streaks travelling right; none are emitted after the collapse, so a dark gap chases them to Earth
    x0, x1 = -4.3, 1.0; speed = (x1 - x0) / (D * .8)
    for i in range(40):
        y, z = rng.uniform(-.7, .7), rng.uniform(-.5, .9)
        bpy.ops.mesh.primitive_cylinder_add(radius=.018, depth=.45, rotation=(0, math.radians(90), 0)); p = bpy.context.object
        p.data.materials.append(kit.mat_emit(f'ph{i}', (1, .85, .45), 9))
        start = x0 + (i / 40) * (x1 - x0)            # evenly filled stream at t=0
        t_hit = (x1 - start) / speed
        kit.key(p, 1, location=(start, y, z)); kit.key(p, max(2, F(t_hit)), location=(x1, y, z * .6))
        kit.key(p, 1, scale=(1, 1, 1)); kit.key(p, max(2, F(t_hit) - 1), scale=(1, 1, 1)); kit.key(p, max(3, F(t_hit)), scale=(.001,) * 3)
        try:
            for fc in p.animation_data.action.fcurves:
                for k in fc.keyframe_points: k.interpolation = 'LINEAR'
        except AttributeError: pass
    overlays.append({'type': 'label', 'text': '≈ 8 MIN 20 S', 'pos': (.5, .2), 'color': (255, 222, 40)})

def s7_dark():                  # "Then the sky goes black. Within about a week, Earth's surface could fall below zero F."
    global NOPLATE; NOPLATE = True
    kit.world()
    sl = kit.sun_lamp((-1, -.5, .3), 4.0)
    sl.data.keyframe_insert('energy', frame=1); sl.data.keyframe_insert('energy', frame=F(.3)); sl.data.energy = 0.0; sl.data.keyframe_insert('energy', frame=F(1.6))
    fill = kit.sun_lamp((-.6, -.5, .6), 1.1, (.55, .65, 1))
    root, sp = kit.earth(2.2, (-1, -.5, .3), tilt_deg=20, clouds=True, atmo=True); root.location = (0, 0, -.4)
    icei, night = earth_mat_nodes()
    kf_input(night.inputs['From Min'], 1, .05); kf_input(night.inputs['From Min'], F(.4), .05); kf_input(night.inputs['From Min'], F(1.8), 1.0)
    kf_input(night.inputs['From Max'], 1, -.2); kf_input(night.inputs['From Max'], F(.4), -.2); kf_input(night.inputs['From Max'], F(1.8), .9)
    kf_input(icei, 1, .43); kf_input(icei, F(1.6), .43); kf_input(icei, NF, .36)
    atm = bpy.data.materials['atmo'].node_tree.nodes['Emission'].inputs['Strength']
    kf_input(atm, 1, 1.4); kf_input(atm, F(1.6), .55)
    kit.key(sp, 1, rotation_euler=(0, 0, 0)); kit.key(sp, NF, rotation_euler=(0, 0, math.radians(14)))
    cam, _ = kit.camera((0, -9.2, 1.2), (0, 0, -.2), lens=32)
    kit.key(cam, 1, location=(-.4, -9.6, 1.4)); kit.key(cam, NF, location=(.3, -8.6, 1.0))
    overlays.append({'type': 'label', 'text': 'BELOW 0°F IN ABOUT A WEEK', 'pos': (.5, .16), 'color': (150, 205, 255)})

def s8_loop():                  # "The oceans would start freezing from the top down, while" -> loops into the hook
    cam, icei = hook_set(.30)
    kit.key(cam, 1, location=(-.6, -10.4, 2.1)); kit.key(cam, NF, location=HOOK_CAM[0])
    overlays.append({'type': 'cta', 'pos': (.5, .1)})

[s0_hook, s1_question, s2_cant, s3_crush, s4_pull, s5_circle, s6_eight, s7_dark, s8_loop][idx]()
for o in bpy.data.objects:
    for m in getattr(o, 'modifiers', []):
        if m.type == 'SUBSURF': m.render_levels = 1
os.makedirs(f'{OUT}/s{idx}', exist_ok=True)
# --- background plates: the planet barely moves within a shot, so render it once per camera and
#     render everything else with a transparent film on top (compose.py stacks them). Big speed-up.
plates = []
earth_objs = [o for o in bpy.data.objects if o.active_material and o.active_material.name.split('.')[0] in ('earth', 'clouds', 'atmo')]
if earth_objs and not NOPLATE:
    segs = CUTS or [(sc.camera, 1)]
    others = [o for o in bpy.data.objects if o not in earth_objs and o.type == 'MESH']
    markers = [(m.name, m.frame, m.camera) for m in sc.timeline_markers]
    for k, (cam, f0) in enumerate(segs):
        f1 = segs[k + 1][1] if k + 1 < len(segs) else NF + 1
        sc.timeline_markers.clear(); sc.camera = cam; sc.frame_set((f0 + f1) // 2)
        for o in others: o.hide_render = True
        sc.cycles.samples = 16
        path = f'{OUT}/s{idx}/plate_{k}.exr'; sc.render.filepath = path
        sc.render.image_settings.file_format = 'OPEN_EXR'; sc.render.image_settings.color_depth = '16'
        bpy.ops.render.render(write_still=True)
        for o in others: o.hide_render = False
        plates.append((cam, f0, f1, path))
    for n, fr, c in markers:
        mm = sc.timeline_markers.new(n, frame=fr); mm.camera = c
    for o in earth_objs: o.hide_render = True
    sc.cycles.samples = 8; sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_depth = '8'
    for k, (cam, f0, f1, path) in enumerate(plates):   # camera-locked backdrop card showing the plate (linear EXR -> exact match)
        d = 80.0; hgt = d * 36.0 / cam.data.lens; wid = hgt * sc.render.resolution_x / sc.render.resolution_y
        bpy.ops.mesh.primitive_plane_add(size=1); pl = bpy.context.object; pl.parent = cam; pl.location = (0, 0, -d); pl.rotation_euler = (0, 0, 0)
        pl.scale = (wid, hgt, 1)
        m = bpy.data.materials.new(f'plate{k}'); nt, N, L = kit.nodes(m); o_ = N.new('ShaderNodeOutputMaterial'); e = N.new('ShaderNodeEmission')
        tex = N.new('ShaderNodeTexImage'); tex.image = bpy.data.images.load(path); tex.image.colorspace_settings.name = 'Linear Rec.709' if 'Linear Rec.709' in [i.name for i in bpy.types.ColorManagedInputColorspaceSettings.bl_rna.properties['name'].enum_items] else tex.image.colorspace_settings.name
        L.new(tex.outputs['Color'], e.inputs['Color']); e.inputs['Strength'].default_value = 1.0; L.new(e.outputs[0], o_.inputs[0])
        pl.data.materials.append(m)
        for attr in ('visible_diffuse', 'visible_glossy', 'visible_transmission', 'visible_volume_scatter', 'visible_shadow'):
            setattr(pl, attr, False)
        pl.hide_render = True; pl.keyframe_insert('hide_render', frame=1)
        pl.hide_render = False; pl.keyframe_insert('hide_render', frame=f0)
        pl.hide_render = True; pl.keyframe_insert('hide_render', frame=f1)
        plates[k] = [f0, path]
json.dump({'frames': NF, 'overlays': overlays}, open(f'{OUT}/s{idx}/meta.json', 'w'))
if mode == 'still':
    sc.frame_set(int(NF * (float(sys.argv[3]) if len(sys.argv) > 3 else .6))); sc.render.filepath = f'{OUT}/still_{idx}.png'; bpy.ops.render.render(write_still=True)
else:
    if os.environ.get('FR'): sc.frame_start, sc.frame_end = map(int, os.environ['FR'].split(','))
    sc.render.image_settings.file_format = 'PNG'; sc.render.filepath = f'{OUT}/s{idx}/f_'; bpy.ops.render.render(animation=True)
