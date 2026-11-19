"""3D Short: What if Hubble fell out of the sky?  Usage: python3 hubble3d.py <scene> still|anim [frac]"""
import sys, math, json, os, random
sys.path.insert(0, '/home/claude/b3d')
import bpy, kit
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

CFG = json.load(open('/home/claude/b3d/hubble/topic.json'))
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
    kit.heat_glow(h, [(1, 1.2 * glow_from), (NF, 1.2 * glow_to)], (1, .3, .05))   # hull glowing hot
    li = bpy.data.lights.new('plasma_light', 'POINT'); li.energy = 1400; li.color = (1, .5, .15); kit.link(bpy.data.objects.new('plasma_light', li)).parent = mover
    keylights(mover)
    cam, tgt = kit.camera(cam_start, (0, 0, .1), lens=30)
    kit.key(cam, 1, location=cam_start); kit.key(cam, NF, location=cam_end)
    return cam, mover, h, parts

# ======================================================================= scenes
def s0_hook():                  # "Two tons of telescope could survive the fall."
    cam, mover, h, parts = reentry_setup(1.0, 1.0)
    for i, o in enumerate(debris(7, (.6, .4, 1.8), 1.4)):
        trail(o, 1.4, .04); o.rotation_euler = Vector((.3, -.1, 1.6)).to_track_quat('Z', 'Y').to_euler()
        kit.key(o, 1, location=o.location); kit.key(o, NF, location=o.location + Vector((-.3, .1, -1.6)))
    cam2, _ = kit.camera((-2.6, -4.2, -.6), (0, 0, .4), lens=36)
    kit.key(cam2, 1, location=(-2.6, -4.2, -.6)); kit.key(cam2, NF, location=(-2.2, -3.9, -.4))
    cuts((cam, 0))

def s1_question():              # "What if the Hubble Space Telescope fell out of the sky?"
    kit.world(); kit.sun_lamp((1, -.6, .5), 4.2)
    root, sp = kit.earth(7, (1, -.6, .5), tilt_deg=15, clouds=True, atmo=True); root.location = (0, 5, -8.6); no_ice()
    kit.key(sp, 1, rotation_euler=(0, 0, 0)); kit.key(sp, NF, rotation_euler=(0, 0, math.radians(3)))
    h, parts = kit.hubble(); h.location = (0, 0, .4)
    kit.key(h, 1, rotation_euler=(0, 0, math.radians(-30))); kit.key(h, NF, rotation_euler=(math.radians(4), 0, math.radians(-18)))
    keylights(h)
    cam, _ = kit.camera((-1.5, -8.5, 1.4), (0, 0, .2), lens=30)
    kit.key(cam, 1, location=(-1.8, -8.8, 1.5)); kit.key(cam, NF, location=(-.8, -8.0, 1.2))
    cam2, _ = kit.camera((3.2, -3.4, -.2), (0, 0, .5), lens=34)
    kit.key(cam2, 1, location=(3.2, -3.4, -.2)); kit.key(cam2, NF, location=(3.0, -3.0, .1))
    cuts((cam, 0))

def s2_drag():                  # "No engine... thin air slowly drags it lower."
    kit.world(); kit.sun_lamp((1, -.5, .4), 4)
    big_earth(R=10, z=-11.8, clouds=True)
    h, parts = kit.hubble(); kit.key(h, 1, location=(0, 0, .5), rotation_euler=(0, 0, math.radians(-12))); kit.key(h, NF, location=(.1, 0, .05), rotation_euler=(0, math.radians(4), math.radians(-8)))
    keylights(h)
    for i in range(26):          # thin-air streaks rushing past the telescope
        y, z = rng.uniform(-1.2, 1.2), rng.uniform(-.9, 1.6)
        bpy.ops.mesh.primitive_cylinder_add(radius=.006, depth=rng.uniform(.8, 1.6), rotation=(0, math.radians(90), 0)); s = bpy.context.object
        s.data.materials.append(kit.mat_emit(f'air{i}', (.6, .8, 1), 2.5))
        x0 = rng.uniform(3, 9); sp = rng.uniform(4, 7)
        kit.key(s, 1, location=(x0, y, z)); kit.key(s, NF, location=(x0 - sp * NF / FPS, y, z))
    cam, _ = kit.camera((-.5, -8.4, 1.0), (0, 0, .2), lens=30)
    kit.key(cam, 1, location=(-.6, -8.6, 1.2)); kit.key(cam, NF, location=(0, -7.8, .6))
    cam2, _ = kit.camera((4.5, -2.0, .6), (0, 0, .3), lens=30)
    kit.key(cam2, 1, location=(4.5, -2.0, .8)); kit.key(cam2, NF, location=(4.0, -2.2, .3))
    cuts((cam, 0), (cam2, 2.8))

def s3_odds():                  # "NASA estimates a 50% chance it reenters by the end of 2033."
    kit.world(); kit.sun_lamp((1, -.6, .4), 4.2)
    root, sp = kit.earth(1.6, (1, -.6, .4), tilt_deg=15, clouds=True, atmo=True)
    kit.key(sp, 1, rotation_euler=(0, 0, 0)); kit.key(sp, NF, rotation_euler=(0, 0, math.radians(20)))
    rings = []
    for k in range(4):
        r = 2.6 - k * .22
        bpy.ops.mesh.primitive_torus_add(major_radius=r, minor_radius=.012, major_segments=192, minor_segments=6); t = bpy.context.object
        t.rotation_euler = (math.radians(72), 0, math.radians(10)); t.data.materials.append(kit.mat_emit(f'orb{k}', (1, .75 - k * .15, .3), 3))
        kit.key(t, 1, scale=(.001,) * 3); kit.key(t, F(.3 + k * .7), scale=(.001,) * 3); kit.key(t, F(.6 + k * .7), scale=(1,) * 3); rings.append(t)
    piv = kit.link(bpy.data.objects.new('piv', None)); piv.rotation_euler = (math.radians(72), 0, math.radians(10))
    dot = kit.link(bpy.data.objects.new('dot', None)); dot.parent = piv
    bpy.ops.mesh.primitive_uv_sphere_add(radius=.06); d = bpy.context.object; d.data.materials.append(kit.mat_emit('dot', (1, 1, 1), 30)); d.parent = dot
    for f in range(1, NF + 1, 6):
        u = (f - 1) / NF; r = 2.6 - .66 * u; a = u * 2.2 * math.pi
        kit.key(dot, f, location=(r * math.cos(a), r * math.sin(a), 0))
    cam, _ = kit.camera((0, -9.5, 2.2), (0, 0, 0), lens=36)
    kit.key(cam, 1, location=(0, -10, 2.4)); kit.key(cam, NF, location=(.3, -8.6, 1.8))
    cam2, _ = kit.camera((3.6, -5.5, 4.2), (0, 0, 0), lens=34)
    kit.key(cam2, 1, location=(3.6, -5.5, 4.2)); kit.key(cam2, NF, location=(3.2, -5.0, 3.8))
    cuts((cam, 0), (cam2, 3.0))
    overlays.append({'type': 'label', 'text': '50% CHANCE BY END OF 2033', 'pos': (.5, .16), 'color': (255, 222, 40)})

def s4_bus():                   # "About the size of a school bus, ~12,000 kg."
    kit.world(); kit.sun_lamp((1, -.8, .6), 4.0)
    h, parts = kit.hubble(); h.location = (0, 0, .95); h.rotation_euler = (0, 0, math.radians(-22))
    b = kit.school_bus(); b.location = (-.1, .5, -1.5); b.scale = (.98,) * 3; b.rotation_euler = (0, 0, math.radians(-22))
    kit.key(h, 1, location=(0, 0, 1.1)); kit.key(h, NF, location=(0, 0, .9))
    keylights(h)
    cam, _ = kit.camera((0, -8.4, .6), (0, 0, .0), lens=32)
    kit.key(cam, 1, location=(-.4, -8.8, .7)); kit.key(cam, NF, location=(.2, -8.0, .4))
    cam2, _ = kit.camera((-5.5, -5.5, 2.2), (0, 0, 0), lens=32)
    kit.key(cam2, 1, location=(-5.5, -5.5, 2.2)); kit.key(cam2, NF, location=(-5.0, -5.8, 1.8))
    cuts((cam, 0), (cam2, 2.7))
    overlays.append({'type': 'label', 'text': '≈ 12,000 KG', 'pos': (.5, .2), 'color': (255, 222, 40)})

def s5_burn():                  # "Most of it would burn up... ~27,000 km/h."
    cam, mover, h, parts = reentry_setup(.15, 1.0, cam_start=(2.6, -7.6, 1.3), cam_end=(1.9, -6.6, .9))
    for side, arr in parts.items():
        if not side.startswith('array'): continue
        sgn = 1 if side.endswith('1') else -1
        kit.key(arr, 1, location=arr.location.copy(), rotation_euler=arr.rotation_euler.copy())
        kit.key(arr, F(D * .45), location=arr.location.copy(), rotation_euler=arr.rotation_euler.copy())
        kit.key(arr, NF, location=arr.location + Vector((1.2, sgn * 2.2, 1.4)), rotation_euler=(math.radians(80 * sgn), math.radians(140), math.radians(40)))
    cam2, _ = kit.camera((-1.2, -3.6, -1.4), (0, 0, .5), lens=30)
    kit.key(cam2, 1, location=(-1.2, -3.6, -1.4)); kit.key(cam2, NF, location=(-.9, -3.3, -1.1))
    cuts((cam, 0), (cam2, 3.5))
    overlays.append({'type': 'label', 'text': '~27,000 KM/H', 'pos': (.5, .16), 'color': (255, 140, 60)})

def s6_debris():                # "An earlier NASA study: ~2 tons could survive, path over 1,000 km long."
    kit.world(); kit.sun_lamp((1, -.3, .5), 3.8)
    root, sp = kit.earth(30, (1, -.3, .5), tilt_deg=10, clouds=True, atmo=True); root.location = (0, 18, -30.6); no_ice()
    kit.key(sp, 1, rotation_euler=(0, 0, 0)); kit.key(sp, NF, rotation_euler=(0, 0, math.radians(.5)))
    pieces = debris(9, (0, 0, 0), .1, 6)
    for i, o in enumerate(pieces):
        x0 = -3.2 + i * .75 + rng.uniform(-.2, .2); y0 = 2 + i * 1.2
        trail(o, rng.uniform(1.5, 2.6), .05)
        o.rotation_euler = Vector((-1.5, 0, 4.25)).to_track_quat('Z', 'Y').to_euler()
        t0 = F(i * .25)
        kit.key(o, 1, location=(x0 - 1.5, y0, 3.8)); kit.key(o, t0, location=(x0 - 1.5, y0, 3.8)); kit.key(o, min(NF, t0 + 72), location=(x0, y0, -.45))
    # glowing footprint strip on the ground, growing with the impacts
    bpy.ops.mesh.primitive_plane_add(size=1, location=(.2, 6.8, -.58)); strip = bpy.context.object
    strip.rotation_euler = (0, 0, math.atan2(9.6, 6)); strip.scale = (.001, .25, 1)
    strip.data.materials.append(kit.mat_emit('strip', (1, .4, .1), 4))
    kit.key(strip, 1, scale=(.001, .25, 1)); kit.key(strip, F(D * .85), scale=(11.5, .25, 1))
    cam, _ = kit.camera((-4.5, -6.5, 3.4), (0, 4, -.3), lens=30)
    kit.key(cam, 1, location=(-4.8, -6.8, 3.6)); kit.key(cam, NF, location=(-3.8, -5.8, 3.0))
    cam2, _ = kit.camera((5.5, -2.5, 1.2), (-1, 5, 0), lens=28)
    kit.key(cam2, 1, location=(5.5, -2.5, 1.2)); kit.key(cam2, NF, location=(5.0, -1.8, 1.0))
    cuts((cam, 0), (cam2, 4.5))
    overlays.append({'type': 'label', 'text': '~2 TONS COULD SURVIVE', 'pos': (.5, .14), 'color': (255, 222, 40)})

def s7_rescue():                # "NASA is asking companies to boost it higher, or bring it down safely."
    kit.world(); kit.sun_lamp((1, -.6, .5), 4.2)
    root, sp = kit.earth(7, (1, -.6, .5), tilt_deg=15, clouds=True, atmo=True); root.location = (0, 5, -8.8); no_ice()
    h, parts = kit.hubble(); h.rotation_euler = (0, 0, math.radians(-20))
    s = kit.servicer(); s.scale = (.75,) * 3; s.rotation_euler = (0, 0, math.radians(-20))
    aft = Vector((-1.62 * math.cos(math.radians(-20)), -1.62 * math.sin(math.radians(-20)), 0))
    dock = aft + Vector((-.95 * math.cos(math.radians(-20)), -.95 * math.sin(math.radians(-20)), 0))
    kit.key(s, 1, location=dock + Vector((-2.6, -1.2, 1.4))); kit.key(s, F(D * .5), location=dock)
    flame_m = kit.mat_emit('flame2', (.4, .7, 1), 0.0)
    bpy.ops.mesh.primitive_cone_add(radius1=.13, depth=.8, location=(-.75, 0, 0), rotation=(0, math.radians(-90), 0)); fl = bpy.context.object
    fl.data.materials.append(flame_m); fl.parent = s
    emis = flame_m.node_tree.nodes['Emission'].inputs['Strength']
    kf_input(emis, 1, 0); kf_input(emis, F(D * .55), 0); kf_input(emis, F(D * .62), 25)
    for o, base in ((h, Vector((0, 0, 0))), (s, dock)):
        kit.key(o, F(D * .58), location=base); kit.key(o, NF, location=base + Vector((0, 0, .9)))
    keylights(h)
    cam, _ = kit.camera((.5, -9, 1.6), (-.6, 0, .4), lens=28)
    kit.key(cam, 1, location=(.3, -9.4, 1.8)); kit.key(cam, NF, location=(.6, -8.6, 1.6))
    cam2, _ = kit.camera((-5.2, -3.2, .2), (-.8, 0, .5), lens=32)
    kit.key(cam2, 1, location=(-5.2, -3.2, .2)); kit.key(cam2, NF, location=(-4.8, -3.0, .8))
    cuts((cam, 0), (cam2, 2.9))

def s8_loop():                  # "Because if nobody catches it in time," -> loops into the hook
    cam, mover, h, parts = reentry_setup(.0, 1.0, cam_start=(1.6, -6.5, .8), cam_end=(2.0, -7.2, 1.1))
    overlays.append({'type': 'cta', 'pos': (.5, .1)})

[s0_hook, s1_question, s2_drag, s3_odds, s4_bus, s5_burn, s6_debris, s7_rescue, s8_loop][idx]()
for o in bpy.data.objects:
    for m in getattr(o, 'modifiers', []):
        if m.type == 'SUBSURF': m.render_levels = 1
os.makedirs(f'{OUT}/s{idx}', exist_ok=True)
# --- background plates: the planet barely moves within a shot, so render it once per camera and
#     render everything else with a transparent film on top (compose.py stacks them). Big speed-up.
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
