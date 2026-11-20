"""3D Short: What if you texted Voyager 1?  Usage: python3 voyager3d.py <scene> still|anim [frac]"""
import sys, math, json, os, random
sys.path.insert(0, '/home/claude/b3d')
import bpy, bmesh, kit
from mathutils import Vector

CFG = json.load(open('/home/claude/b3d/voyager/topic.json'))
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
F = lambda sec: 1 + int(round((sec + .35) * FPS))
overlays = []
rng = random.Random(idx + 7)
SIG = (.45, .8, 1.0)        # radio pulses drawn as soft cyan rings (radio is invisible; stylized)

def kf_input(sock, frame, value):
    sock.default_value = value; sock.keyframe_insert('default_value', frame=frame)

CUTS = []
def cuts(*cams_at):
    for k, (cam, sec) in enumerate(cams_at):
        CUTS.append((cam, max(1, F(sec) if sec > 0 else 1)))
        m = sc.timeline_markers.new(f'cut{k}', frame=max(1, F(sec) if sec > 0 else 1)); m.camera = cam

def keylights(target, key=160, rim=260):
    for name, loc, col, en in [('key', (2.5, -6, 2), (1, .95, .9), key), ('rim', (-3, 3, 2), (.5, .65, 1), rim)]:
        li = bpy.data.lights.new(name, 'AREA'); li.energy = en; li.color = col; li.size = 3
        o = kit.link(bpy.data.objects.new(name, li)); o.location = loc
        c = o.constraints.new('TRACK_TO'); c.target = target; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'

def voyager(size=7.0):
    """official NASA Voyager model; high-gain dish (+Z of the model) turned to face -Y (toward Earth and the Sun)"""
    v = kit.nasa_model('Voyager Probe (A)', size, 'X')
    piv = kit.link(bpy.data.objects.new('vpiv', None)); v.parent = piv
    v.rotation_euler = (math.radians(90), 0, 0)
    k = size / 7.5; v.location = (-1.48 * k, -.6 * k, 0)     # center the dish + bus (not the long boom) on the pivot
    return piv

def ring_mat(name, strength):
    m = bpy.data.materials.new(name); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial')
    e = N.new('ShaderNodeEmission'); e.inputs['Color'].default_value = (*SIG, 1); e.inputs['Strength'].default_value = strength
    tr = N.new('ShaderNodeBsdfTransparent'); mx = N.new('ShaderNodeMixShader'); mx.name = 'mix'; mx.inputs['Fac'].default_value = 1
    L.new(tr.outputs[0], mx.inputs[1]); L.new(e.outputs[0], mx.inputs[2]); L.new(mx.outputs[0], o.inputs[0]); return m

def pulses(origin, direction, n, r0, r1, dist, t0, period, life, strength=6, minor=.025, name='p'):
    """n expanding rings travelling from origin along direction (scene seconds t0 + k*period, each lives `life` s)"""
    d = Vector(direction).normalized(); q = d.to_track_quat('Z', 'Y').to_euler()
    for k in range(n):
        bpy.ops.mesh.primitive_torus_add(major_radius=1, minor_radius=minor, major_segments=128, minor_segments=8)
        t = bpy.context.object; t.rotation_euler = q; m = ring_mat(f'{name}{k}', strength); t.data.materials.append(m)
        t.visible_shadow = False
        fac = m.node_tree.nodes['mix'].inputs['Fac']
        a, b = F(t0 + k * period), F(t0 + k * period + life)
        kit.key(t, 1, location=Vector(origin), scale=(r0,) * 3); kit.key(t, a, location=Vector(origin), scale=(r0,) * 3)
        kit.key(t, b, location=Vector(origin) + d * dist, scale=(r1,) * 3)
        kf_input(fac, 1, 0); kf_input(fac, a, 0); kf_input(fac, a + 3, 1); kf_input(fac, max(a + 4, b - 6), .8); kf_input(fac, b, 0)

def dish70(loc=(0, 0, 0), el=55, az=0):
    """procedural 70 m DSN antenna (like Goldstone DSS-14), 1 unit = 10 m: paraboloid D=70 m, quadripod + subreflector,
    elevation axle on a box alidade over a round concrete pedestal"""
    white = kit.mat_principled('dsn_white', (.72, .73, .74), rough=.5)
    grey = kit.mat_principled('dsn_grey', (.5, .5, .52), rough=.6)
    conc = kit.mat_pbr('concrete')
    root = kit.link(bpy.data.objects.new('dsn', None)); root.location = loc; root.rotation_euler = (0, 0, math.radians(az))
    bpy.ops.mesh.primitive_cylinder_add(radius=1.5, depth=1.2, vertices=64, location=(0, 0, .6)); p = bpy.context.object; p.data.materials.append(conc); p.parent = root
    for s in (-1, 1):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(s * 1.25, 0, 2.3)); t = bpy.context.object; t.scale = (.5, 1.6, 2.4)
        t.data.materials.append(white); kit.smooth(t, 1, .05); t.parent = root
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 1.5)); b = bpy.context.object; b.scale = (3.0, 2.2, .7); b.data.materials.append(white); b.parent = root
    elev = kit.link(bpy.data.objects.new('elev', None), root); elev.location = (0, 0, 3.6); elev.rotation_euler = (math.radians(90 - el), 0, 0)
    bpy.ops.mesh.primitive_cylinder_add(radius=.28, depth=3.0, rotation=(0, math.radians(90), 0)); ax = bpy.context.object; ax.data.materials.append(grey); ax.parent = elev
    # paraboloid z = r^2/(4f), f = 2.3 (23 m), rim radius 3.5
    R, f = 3.5, 2.3
    me = bpy.data.meshes.new('para'); bm = bmesh.new(); rings, seg = 40, 160; verts = []
    for i in range(rings + 1):
        r = R * i / rings; row = []
        for j in range(seg if i else 1):
            a = 2 * math.pi * j / seg; row.append(bm.verts.new((r * math.cos(a), r * math.sin(a), r * r / (4 * f))))
        verts.append(row)
    for j in range(seg): bm.faces.new((verts[0][0], verts[1][j], verts[1][(j + 1) % seg]))
    for i in range(1, rings):
        for j in range(seg): bm.faces.new((verts[i][j], verts[i + 1][j], verts[i + 1][(j + 1) % seg], verts[i][(j + 1) % seg]))
    bm.to_mesh(me); bm.free(); dish = kit.link(bpy.data.objects.new('dish', me)); dish.data.materials.append(white)
    sol = dish.modifiers.new('sol', 'SOLIDIFY'); sol.thickness = .06
    for pgon in dish.data.polygons: pgon.use_smooth = True
    dish.parent = elev; dish.location = (0, 0, .5)
    # panel seams: thin rings on the surface
    for k in range(1, 6):
        r = R * k / 6; bpy.ops.mesh.primitive_torus_add(major_radius=r, minor_radius=.012, major_segments=160, minor_segments=4, location=(0, 0, .5 + r * r / (4 * f) + .01))
        s = bpy.context.object; s.data.materials.append(grey); s.parent = elev
    # back structure (dark truss cone) and quadripod + subreflector at the focus
    bpy.ops.mesh.primitive_cone_add(radius1=.9, radius2=2.0, depth=.9, vertices=48, location=(0, 0, .15)); bc = bpy.context.object; bc.data.materials.append(kit.mat_principled('truss', (.25, .26, .28), rough=.7)); bc.parent = elev
    apex = Vector((0, 0, .5 + f))
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2; foot = Vector((2.4 * math.cos(a), 2.4 * math.sin(a), .5 + 2.4 ** 2 / (4 * f)))
        mid = (foot + apex) / 2; dvec = apex - foot
        bpy.ops.mesh.primitive_cylinder_add(radius=.05, depth=dvec.length, location=mid); lg = bpy.context.object
        lg.rotation_euler = dvec.to_track_quat('Z', 'Y').to_euler(); lg.data.materials.append(white); lg.parent = elev
    bpy.ops.mesh.primitive_cylinder_add(radius=.38, depth=.12, vertices=48, location=apex); sr = bpy.context.object; sr.data.materials.append(white); sr.parent = elev
    bpy.ops.mesh.primitive_cone_add(radius1=.28, radius2=.12, depth=.9, vertices=32, location=(0, 0, .95)); fd = bpy.context.object; fd.data.materials.append(white); fd.parent = elev
    return root, elev, apex

def ground_scene(sun_el, sun_rot, energy=3.5, strength=.5, night=False):
    if night:
        kit.world(strength=.8); kit.sun_lamp((-.4, -.6, .5), .25, (.7, .8, 1))
    else:
        kit.sky(sun_elevation=sun_el, sun_rotation=sun_rot, strength=strength, sun_lamp_energy=energy)
    t = kit.terrain(size=200, height=.9, scale=8, kind='desert', seed=3, res=6); t.location.z = -.25
    return t

def phone_in_hand(astro_root, limbs):
    arm = limbs['arm1']
    bpy.ops.mesh.primitive_cube_add(size=1); ph = bpy.context.object; ph.scale = (.13, .025, .24); kit.smooth(ph, 1, .02)
    ph.data.materials.append(kit.mat_principled('phone', (.02, .02, .03), rough=.3)); ph.parent = arm; ph.location = (.02, -.12, -.62)
    bpy.ops.mesh.primitive_plane_add(size=1); scr = bpy.context.object; scr.scale = (.11, .21, 1); scr.rotation_euler = (math.radians(90), 0, 0)
    scr.data.materials.append(kit.mat_emit('screen', (.5, .8, 1), 6)); scr.parent = ph; scr.location = (0, -.6, 0)
    return ph

# ======================================================================= scenes
def hook_shot(cam_from, cam_to, lens=34):
    kit.world(); kit.sun_lamp((0, -1, .15), 1.2)
    v = voyager(7.5); v.location = (0, 0, 0)
    kit.key(v, 1, rotation_euler=(0, 0, math.radians(-8))); kit.key(v, NF, rotation_euler=(0, math.radians(2), math.radians(-2)))
    keylights(v, 45, 300)
    pulses((0, -.8, 0), (0, -1, .05), 4, .5, 2.6, 8, -.35, .45, 1.6, 3.5, .012, 'rp')
    cam, _ = kit.camera(cam_from, (0, 0, .3), lens=lens)
    kit.key(cam, 1, location=cam_from); kit.key(cam, NF, location=cam_to)
    return cam

S0_A, S0_B = (-3.2, -6.4, 1.9), (-2.7, -5.6, 1.6)
def s0_hook():                  # "You'd wait two days for a reply."
    hook_shot(S0_A, S0_B)
    overlays.append({'type': 'hook', 'text': '2 DAYS|FOR A REPLY'})

def s1_question():              # "What if you sent a text to Voyager 1?"
    kit.world(); kit.sun_lamp((1, -.7, .5), 4.0)
    root, sp = kit.earth(9, (1, -.7, .5), tilt_deg=15, clouds=True, atmo=True, face_lon=-80); root.location = (0, 8, -10.5)
    kit.key(sp, 1, rotation_euler=(0, 0, 0)); kit.key(sp, NF, rotation_euler=(0, 0, math.radians(2)))
    a, limbs = kit.astronaut(); a.location = (0, 0, .3)
    limbs['arm1'].rotation_euler = (math.radians(-70), math.radians(-20), 0)
    phone_in_hand(a, limbs)
    kit.key(a, 1, rotation_euler=(math.radians(4), 0, math.radians(-14))); kit.key(a, NF, rotation_euler=(math.radians(-2), 0, math.radians(-6)))
    kit.key(a, 1, location=(0, 0, .25)); kit.key(a, NF, location=(0, 0, .4))
    keylights(a)
    cam, _ = kit.camera((1.2, -4.6, 1.3), (0, 0, .5), lens=32)
    kit.key(cam, 1, location=(1.4, -4.9, 1.4)); kit.key(cam, NF, location=(1.0, -4.3, 1.2))

def s2_lightday():              # "This week, it became the first spacecraft one light-day from Earth, ~16 billion miles away."
    kit.world(); kit.sun_lamp((0, -1, .1), 1.4)
    v = voyager(6.0)
    kit.key(v, 1, rotation_euler=(0, 0, math.radians(-4))); kit.key(v, NF, rotation_euler=(0, 0, math.radians(3)))
    keylights(v, 80, 260)
    # the Sun from 173 AU: a dazzling point of light far beyond the dish (Earth too close to it to see)
    s = kit.sun_sphere(.35, 60); s.location = (22, -140, 16)
    cam, _ = kit.camera((1.6, 7.5, 2.0), (0, -4, .5), lens=30)
    kit.key(cam, 1, location=(1.9, 8.2, 2.2)); kit.key(cam, NF, location=(1.2, 6.8, 1.6))
    cam2, _ = kit.camera((-5.5, -1.5, 1.2), (0, -1, 0), lens=30)
    kit.key(cam2, 1, location=(-5.6, -1.2, 1.3)); kit.key(cam2, NF, location=(-5.0, -2.0, 1.0))
    cuts((cam, 0), (cam2, 3.5))
    overlays.append({'type': 'label', 'text': '1 LIGHT-DAY', 'pos': (.5, .12), 'color': (255, 222, 40)})
    overlays.append({'type': 'label', 'text': '≈ 16 BILLION MILES', 'pos': (.5, .18), 'color': (255, 255, 255), 'from': .9})

def s3_dish():                  # "Your message would leave one of NASA's giant radio dishes, at the speed of light."
    ground_scene(5.0, 120, 2.6, .07)
    root, elev, apex = dish70((0, 0, 0), el=50, az=35)
    bpy.context.view_layer.update()
    w = elev.matrix_world; o = w @ (apex + Vector((0, 0, .3))); d = (w.to_3x3() @ Vector((0, 0, 1))).normalized()
    pulses(o, d, 6, .5, 2.2, 12, .9, .75, 1.7, 5, .03, 'up')
    a, limbs = kit.astronaut(); a.location = (3.2, -4.5, -.35); a.scale = (.18,) * 3; a.rotation_euler = (0, 0, math.radians(200))   # 1.8 m person for scale
    cam, _ = kit.camera((9, -13, 1.2), (0, 0, 3.6), lens=28)
    kit.key(cam, 1, location=(9.5, -13.8, 1.0)); kit.key(cam, NF, location=(8.2, -12.2, 1.5))
    cam2, _ = kit.camera((-4, -9, 1.4), (0, 0, 5.0), lens=24)
    kit.key(cam2, 1, location=(-4.2, -9.2, 1.4)); kit.key(cam2, NF, location=(-3.6, -8.4, 1.6))
    cuts((cam, 0), (cam2, 3.2))
    overlays.append({'type': 'label', 'text': '70-METER DISH', 'pos': (.5, .14), 'color': (255, 222, 40)})

def s4_travel():                # "And it would still take a full 24 hours just to reach it."
    kit.world(); kit.sun_lamp((1, -.3, .3), 4.0)
    root, sp = kit.earth(1.4, (1, -.3, .3), tilt_deg=23.4, clouds=True, atmo=True, face_lon=-100)
    kit.key(sp, 1, rotation_euler=(0, 0, 0)); kit.key(sp, NF, rotation_euler=(0, 0, math.radians(6)))
    for k in range(3):     # a train of pulses heading out into the dark (toward the camera side)
        bpy.ops.mesh.primitive_torus_add(major_radius=1, minor_radius=.008, major_segments=128, minor_segments=8); t = bpy.context.object
        t.rotation_euler = Vector((0, -1, .12)).to_track_quat('Z', 'Y').to_euler(); t.data.materials.append(kit.mat_emit(f'tr{k}', SIG, 3))
        t.visible_shadow = False
        kit.key(t, 1, location=(0, -2.2 - k * 1.6, .3 + k * .19), scale=(.6 + k * .25,) * 3)
        kit.key(t, NF, location=(0, -6.8 - k * 1.6, .85 + k * .19), scale=(1.2 + k * .25,) * 3)
    cam, _ = kit.camera((1.6, -9.5, 1.5), (0, -3, .4), lens=32)
    kit.key(cam, 1, location=(1.6, -9.0, 1.4)); kit.key(cam, NF, location=(1.9, -12.5, 1.9))
    overlays.append({'type': 'label', 'text': '24 HOURS ONE WAY', 'pos': (.5, .14), 'color': (255, 222, 40)})
    overlays.append({'type': 'label', 'text': 'NOT TO SCALE', 'pos': (.5, .2), 'color': (200, 210, 230), 'from': .8})

def s5_bulb():                  # "Voyager talks back with a radio about as strong as a fridge light bulb."
    kit.world(); kit.sun_lamp((0, -1, .2), 1.2)
    v = voyager(9.0)
    kit.key(v, 1, rotation_euler=(0, 0, math.radians(14))); kit.key(v, NF, rotation_euler=(0, 0, math.radians(6)))
    keylights(v, 55, 300)
    pulses((0, -.95, 0), (0, -1, 0), 4, .6, 1.8, 6, .5, 1.1, 1.8, 1.8, .01, 'weak')
    cam, _ = kit.camera((2.6, -4.6, 1.0), (0, -.2, .4), lens=30)
    kit.key(cam, 1, location=(2.9, -5.0, 1.1)); kit.key(cam, NF, location=(2.2, -4.2, .8))
    cam2, _ = kit.camera((-1.8, -5.6, -.6), (0, 0, .4), lens=34)
    kit.key(cam2, 1, location=(-1.8, -5.6, -.6)); kit.key(cam2, NF, location=(-1.4, -5.1, -.3))
    cuts((cam, 0), (cam2, 2.6))
    overlays.append({'type': 'label', 'text': '~20 WATTS', 'pos': (.5, .13), 'color': (255, 222, 40)})
    overlays.append({'type': 'label', 'text': '≈ A FRIDGE LIGHT BULB', 'pos': (.5, .19), 'color': (255, 255, 255), 'from': 1.2})

def s6_whisper():               # "By the time it gets here, the signal is < a billionth of a trillionth of a watt."
    ground_scene(0, 0, night=True)
    root, elev, apex = dish70((0, 0, 0), el=50, az=-30)
    bpy.context.view_layer.update()
    w = elev.matrix_world; o = w @ (apex + Vector((0, 0, .3))); d = (w.to_3x3() @ Vector((0, 0, 1))).normalized()
    pulses(o + d * 16, -d, 3, 2.6, .3, 15.5, .2, 1.5, 2.6, 2.5, .015, 'faint')    # very faint rings sinking into the dish
    li = bpy.data.lights.new('fill', 'AREA'); li.energy = 500; li.size = 12; li.color = (.6, .7, 1)
    lo = kit.link(bpy.data.objects.new('fill', li)); lo.location = (8, -12, 9)
    c = lo.constraints.new('TRACK_TO'); c.target = root; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
    cam, _ = kit.camera((-8, -12, 1.5), (0, 0, 4.0), lens=26)
    kit.key(cam, 1, location=(-8.6, -12.8, 1.4)); kit.key(cam, NF, location=(-7.4, -11.4, 1.8))
    cam2, _ = kit.camera((3, -6, 9), (0, 0, 3.6), lens=28)
    kit.key(cam2, 1, location=(3.2, -6.4, 9.2)); kit.key(cam2, NF, location=(2.8, -5.8, 8.6))
    cuts((cam, 0), (cam2, 2.9))
    overlays.append({'type': 'label', 'text': '0.0000000000000000000001 W', 'pos': (.5, .14), 'color': (255, 222, 40)})
    overlays.append({'type': 'label', 'text': '1/10 BILLIONTH OF A TRILLIONTH', 'pos': (.5, .2), 'color': (255, 255, 255), 'from': 1.0})

def s7_fly():                   # "Meanwhile, Voyager has flown almost two million miles farther away."
    kit.world(); kit.sun_lamp((0, -1, .2), 1.2)
    v = voyager(8.0)
    kit.key(v, 1, location=(-3.2, 2.0, 0), rotation_euler=(0, 0, math.radians(-6))); kit.key(v, NF, location=(3.0, 5.0, .3), rotation_euler=(0, 0, math.radians(4)))
    keylights(v, 50, 260)
    cam, _ = kit.camera((0, -7.5, .9), (0, 2.5, .2), lens=30)
    kit.key(cam, 1, location=(-.4, -7.6, .9)); kit.key(cam, NF, location=(.5, -7.2, .7))
    overlays.append({'type': 'label', 'text': '+1.8 MILLION MILES', 'pos': (.5, .13), 'color': (255, 222, 40)})
    overlays.append({'type': 'label', 'text': 'IN 2 DAYS (~38,000 MPH)', 'pos': (.5, .19), 'color': (255, 255, 255), 'from': 1.0})

def s8_record():                # "It's been flying since 1977, and it's still listening."
    kit.world(); kit.sun_lamp((0, -1, .2), 2.6)
    v = voyager(10.0)
    kit.key(v, 1, rotation_euler=(0, 0, math.radians(110))); kit.key(v, NF, rotation_euler=(0, 0, math.radians(80)))
    keylights(v, 160, 280)
    cam, _ = kit.camera((3.0, -3.8, 1.6), (0, 0, .2), lens=32)
    kit.key(cam, 1, location=(3.2, -4.1, 1.7)); kit.key(cam, NF, location=(2.6, -3.5, 1.3))
    overlays.append({'type': 'label', 'text': 'LAUNCHED 1977', 'pos': (.5, .14), 'color': (255, 222, 40)})

def s9_loop():                  # "So if you texted it hello today," -> loops into the hook
    hook_shot((-3.7, -7.2, 2.2), S0_A)
    overlays.append({'type': 'cta', 'pos': (.5, .1)})

[s0_hook, s1_question, s2_lightday, s3_dish, s4_travel, s5_bulb, s6_whisper, s7_fly, s8_record, s9_loop][idx]()
for o in bpy.data.objects:
    for m in getattr(o, 'modifiers', []):
        if m.type == 'SUBSURF' and not o.name.startswith('terrain'): m.render_levels = 1
os.makedirs(f'{OUT}/s{idx}', exist_ok=True)
# --- background plates for Earth (same trick as hubble3d.py): render the planet once per camera, show it on a camera-locked card
plates = []
earth_objs = [o for o in bpy.data.objects if o.active_material and o.active_material.name.split('.')[0] in ('earth', 'clouds', 'atmo')]
if earth_objs:
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
    for k, (cam, f0, f1, path) in enumerate(plates):
        d = 80.0; hgt = d * 36.0 / cam.data.lens; wid = hgt * sc.render.resolution_x / sc.render.resolution_y
        bpy.ops.mesh.primitive_plane_add(size=1); pl = bpy.context.object; pl.parent = cam; pl.location = (0, 0, -d); pl.rotation_euler = (0, 0, 0)
        pl.scale = (wid, hgt, 1)
        m = bpy.data.materials.new(f'plate{k}'); nt, N, L = kit.nodes(m); o_ = N.new('ShaderNodeOutputMaterial'); e = N.new('ShaderNodeEmission')
        tex = N.new('ShaderNodeTexImage'); tex.image = bpy.data.images.load(path)
        L.new(tex.outputs['Color'], e.inputs['Color']); e.inputs['Strength'].default_value = 1.0; L.new(e.outputs[0], o_.inputs[0])
        pl.data.materials.append(m)
        for attr in ('visible_diffuse', 'visible_glossy', 'visible_transmission', 'visible_volume_scatter', 'visible_shadow'):
            setattr(pl, attr, False)
        pl.hide_render = True; pl.keyframe_insert('hide_render', frame=1)
        pl.hide_render = False; pl.keyframe_insert('hide_render', frame=f0)
        pl.hide_render = True; pl.keyframe_insert('hide_render', frame=f1)
json.dump({'frames': NF, 'overlays': overlays}, open(f'{OUT}/s{idx}/meta.json', 'w'))
if mode == 'still':
    sc.frame_set(int(NF * (float(sys.argv[3]) if len(sys.argv) > 3 else .6))); sc.render.filepath = f'{OUT}/still_{idx}.png'; bpy.ops.render.render(write_still=True)
else:
    if os.environ.get('FR'): sc.frame_start, sc.frame_end = map(int, os.environ['FR'].split(','))
    sc.render.image_settings.file_format = 'PNG'; sc.render.filepath = f'{OUT}/s{idx}/f_'; bpy.ops.render.render(animation=True)
