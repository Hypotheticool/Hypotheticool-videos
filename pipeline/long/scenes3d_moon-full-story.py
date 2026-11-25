"""3D hero scenes for the long video "What If the Moon Disappeared? The Full Story" (16:9).
Usage: python3 scenes3d_moon-full-story.py <line index> still|anim [frac]
Real-data Earth/Moon/Sun/star sky from kit.py, consistent sunlight from +X (slightly toward camera), true or labeled scale."""
import sys, math, json, os, random
sys.path.insert(0, '/home/claude/b3d')
import bpy, kit
from mathutils import Vector

CFG = json.load(open('/home/claude/b3d/moon-full-story/topic.json'))
FPS = 24; DURS = CFG['durs']; PAD = 0.75; OUT = CFG['root']
idx, mode = int(sys.argv[1]), sys.argv[2]
D = DURS[idx]; NF = int(math.ceil((D + PAD) * FPS))
sc = kit.reset(res=(960, 540), samples=8)
sc.render.use_persistent_data = True; sc.cycles.adaptive_threshold = 0.05
try:
    sc.cycles.denoising_quality = 'FAST'; sc.cycles.denoising_prefilter = 'FAST'
except Exception: pass
sc.cycles.max_bounces = 4; sc.cycles.diffuse_bounces = 1; sc.cycles.glossy_bounces = 1; sc.cycles.transparent_max_bounces = 6
sc.frame_start, sc.frame_end = 1, NF
F = lambda sec: 1 + int(round((sec + .35) * FPS))
overlays = []
rng = random.Random(idx + 7)
SUN = (1, -.45, .2)                       # one sun direction for the whole video
EARTH_R = 2.0; MOON_R = EARTH_R * 3475 / 12742      # true relative sizes (Moon ~27% of Earth's width)

def kf(sock, frame, value):
    sock.default_value = value; sock.keyframe_insert('default_value', frame=frame)

def move(obj, a, b, f0=1, f1=None):
    kit.key(obj, f0, location=a); kit.key(obj, f1 or NF, location=b)

def cam(a, b, look, lens=35, look_b=None):
    c, t = kit.camera(a, look, lens=lens); move(c, a, b)
    if look_b: move(t, look, look_b)
    return c, t

CUTS = []
def cuts(*cams_at):
    for k, (cm, sec) in enumerate(cams_at):
        m = sc.timeline_markers.new(f'cut{k}', frame=max(1, F(sec) if sec > 0 else 1)); m.camera = cm; CUTS.append((cm, m.frame))

def no_ice():
    n = bpy.data.materials['earth'].node_tree.nodes.get('ice')
    if n: n.inputs[1].default_value = .95

def earth(R=EARTH_R, loc=(0, 0, 0), face_lon=-80, spin_deg=4, clouds=True, tilt=23.4, sun=SUN):
    root, sp = kit.earth(R, sun, tilt_deg=tilt, clouds=clouds, atmo=True, face_lon=face_lon); root.location = loc; no_ice()
    kit.key(sp, 1, rotation_euler=(0, 0, 0)); kit.key(sp, NF, rotation_euler=(0, 0, math.radians(spin_deg)))
    return root, sp

def moon(R=MOON_R, loc=(0, 0, 0), face_lon=0, spin_deg=2):
    root = kit.moon(R, face_lon=face_lon); root.location = loc
    sp = root.children[0]; kit.key(sp, 1, rotation_euler=(0, 0, 0)); kit.key(sp, NF, rotation_euler=(0, 0, math.radians(spin_deg)))
    for o in root.children_recursive:
        if o.type == 'MESH': o.visible_shadow = False      # Earth-Moon distance is compressed on screen: no fake eclipse shadows
    return root

def fade_material(mat_name, frames_alpha):
    """make a material fade out (alpha 1 -> 0) with keyframes [(frame, alpha)]"""
    m = bpy.data.materials[mat_name]; nt = m.node_tree; N, L = nt.nodes, nt.links
    out = next(n for n in N if n.type == 'OUTPUT_MATERIAL'); src = out.inputs[0].links[0].from_socket
    tr = N.new('ShaderNodeBsdfTransparent'); mx = N.new('ShaderNodeMixShader')
    L.new(tr.outputs[0], mx.inputs[1]); L.new(src, mx.inputs[2]); L.new(mx.outputs[0], out.inputs[0])
    for f, a in frames_alpha: kf(mx.inputs['Fac'], f, a)
    return mx

def glow_sphere(loc, R, color, strength, name='glow'):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=R, location=loc, segments=48, ring_count=24); o = bpy.context.object
    o.data.materials.append(kit.mat_emit(name, color, strength)); kit.smooth(o, 1); return o

def axis_line(root, R, color=(1, .85, .4), strength=6):
    bpy.ops.mesh.primitive_cylinder_add(radius=R * .012, depth=R * 3.0); ax = bpy.context.object
    ax.data.materials.append(kit.mat_emit('axis', color, strength)); ax.parent = root; return ax

def tidal_shell(parent, R, stretch=1.18, color=(.25, .55, 1), alpha=.35, name='bulge'):
    """exaggerated ocean-bulge shell (labeled 'not to scale' on screen) stretched along +X (toward the Moon)"""
    bpy.ops.mesh.primitive_uv_sphere_add(radius=R * 1.02, segments=96, ring_count=48); s = bpy.context.object; kit.smooth(s, 1)
    s.scale = (stretch, 1 / math.sqrt(stretch), 1 / math.sqrt(stretch)); s.parent = parent; s.name = name
    m = bpy.data.materials.new(name); nt = kit.nodes(m); N, L = m.node_tree.nodes, m.node_tree.links
    o = N.new('ShaderNodeOutputMaterial'); g = N.new('ShaderNodeBsdfGlass'); g.inputs['Color'].default_value = (*color, 1); g.inputs['IOR'].default_value = 1.05
    e = N.new('ShaderNodeEmission'); e.inputs['Color'].default_value = (*color, 1); e.inputs['Strength'].default_value = .6
    tr = N.new('ShaderNodeBsdfTransparent'); mx = N.new('ShaderNodeMixShader'); mx.inputs['Fac'].default_value = alpha
    L.new(tr.outputs[0], mx.inputs[1]); L.new(e.outputs[0], mx.inputs[2]); L.new(mx.outputs[0], o.inputs[0])
    s.data.materials.append(m); s.visible_shadow = False; return s

def astro(loc, rot=(0, 0, 0), s=.6):
    a, limbs = kit.astronaut(); a.location = loc; a.rotation_euler = tuple(math.radians(v) for v in rot); a.scale = (s, s, s)
    return a, limbs

def fill_light(target, energy=60):
    li = bpy.data.lights.new('fill', 'AREA'); li.energy = energy; li.color = (.55, .65, 1); li.size = 4
    o = kit.link(bpy.data.objects.new('fill', li)); o.location = (-4, -6, 3)
    c = o.constraints.new('TRACK_TO'); c.target = target; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'

# ======================================================================= scenes (one per 3D line index)
def s0_gone():                  # "Tonight, the Moon is gone."  -> the Moon fades away beside Earth
    kit.world(); kit.sun_lamp(SUN, 4)
    earth(loc=(-1.2, 2.5, -.4), face_lon=-95, spin_deg=2)          # the Americas near the evening terminator
    m = moon(loc=(2.2, -.2, .6), face_lon=0); fade_material('moon', [(1, 1.0), (F(.25), 1.0), (F(min(2.0, D * .8)), 0.0)])
    c, t = cam((.6, -9.0, .9), (.9, -8.2, .8), (.6, .9, .2), lens=34)
    overlays.append({'type': 'hook', 'text': 'THE MOON IS GONE'})

def s1_empty():                 # "No explosion, no warning. It simply isn't there anymore."
    kit.world(); kit.sun_lamp(SUN, 4)
    earth(R=6, loc=(0, 6, -7.0), face_lon=-95, spin_deg=1)
    a, limbs = astro((-.6, -1.0, .2), rot=(8, 0, -35), s=.55)
    kit.key(a, 1, rotation_euler=(math.radians(8), 0, math.radians(-35))); kit.key(a, NF, rotation_euler=(math.radians(12), math.radians(4), math.radians(-28)))
    kit.key(limbs['arm1'], 1, rotation_euler=(0, math.radians(-32), 0)); kit.key(limbs['arm1'], NF, rotation_euler=(math.radians(-70), math.radians(-40), 0))
    fill_light(a, 40)
    dashed = bpy.data.objects.new('empty_spot', None); kit.link(dashed); dashed.location = (2.4, 2.5, 1.0)
    c, t = cam((-2.2, -4.6, .9), (-1.8, -4.1, 1.0), (.3, 1.0, .5), lens=32, look_b=(.8, 1.4, .7))

def s6_scale():                 # "about 3,475 km across, roughly a quarter of Earth's width."  true relative sizes
    kit.world(); kit.sun_lamp(SUN, 4)
    earth(loc=(-1.0, 0, 0), face_lon=-30, spin_deg=4, tilt=0)
    moon(loc=(1.0 + EARTH_R * .25 + MOON_R + .6, 0, 0))
    c, t = cam((.4, -8.6, .5), (.6, -7.9, .4), (.5, 0, 0), lens=36)
    overlays.append({'type': 'label', 'text': 'TRUE SIZES  ·  DISTANCE NOT TO SCALE', 'pos': (.5, .1), 'color': (255, 222, 40)})

def s9_night():                 # "The first change ... the night."  Earth's night side, city lights, no Moon
    kit.world(); kit.sun_lamp((1, .9, .15), 4)
    earth(R=5, loc=(0, 4, -4.2), face_lon=-85, spin_deg=2, sun=(1, .9, .15))
    c, t = cam((-1.0, -5.5, 1.2), (-.4, -5.0, 1.0), (0, 2.5, -.6), lens=30)

def s13_sky():                  # the Milky Way core rising over a dark plain, astronaut watching (view toward +X = galactic center on the map)
    kit.world(strength=3.0, rot_deg=(32, 0, 0))
    for n in bpy.context.scene.world.node_tree.nodes:
        if n.type == 'GAMMA': n.inputs['Gamma'].default_value = 1.25
    bpy.ops.mesh.primitive_plane_add(size=400, location=(0, 0, -.62)); g = bpy.context.object; g.data.materials.append(kit.mat_pbr('rock', 'ground'))
    li = bpy.data.lights.new('starlight', 'SUN'); li.energy = .08; li.color = (.6, .7, 1); kit.link(bpy.data.objects.new('starlight', li)).rotation_euler = (.9, .3, 0)
    a, limbs = astro((2.0, 0, -.1), rot=(0, 0, 95), s=.55)
    kit.key(limbs['arm1'], 1, rotation_euler=(0, math.radians(-32), 0)); kit.key(limbs['arm1'], NF, rotation_euler=(math.radians(-60), math.radians(-30), 0))
    rim = bpy.data.lights.new('rim', 'AREA'); rim.energy = 120; rim.color = (.5, .6, 1); rim.size = 2
    ro = kit.link(bpy.data.objects.new('rim', rim)); ro.location = (4.5, 0, 1.5); ro.rotation_euler = (0, math.radians(110), 0)
    c, t = cam((-1.6, .3, .25), (-1.2, .3, .2), (6, 0, 1.6), lens=20, look_b=(6, 0, 2.2))

def s15_tides():                # "Tides ... the Moon is the main reason they happen."
    kit.world(); kit.sun_lamp(SUN, 4)
    root, sp = earth(loc=(-1.6, 0, 0), face_lon=0, spin_deg=6, tilt=0)
    sh = tidal_shell(root, EARTH_R, 1.0, alpha=.18)
    kit.key(sh, 1, scale=(1, 1, 1)); kit.key(sh, F(D * .7), scale=(1.12, .945, .945))
    moon(loc=(3.6, .4, .2))
    c, t = cam((.6, -8.5, 2.2), (.9, -7.8, 1.8), (.6, 0, 0), lens=34)
    overlays.append({'type': 'label', 'text': 'OCEAN BULGES EXAGGERATED · NOT TO SCALE', 'pos': (.5, .1), 'color': (120, 220, 255)})

def s20_ocean():                # "that two-week rhythm would disappear."  dark sea under starlight
    kit.world(strength=1.0, rot_deg=(70, 0, 0))
    o = kit.ocean(size=40, wave_scale=.8, wind=7, time_frames=(1, NF), resolution=10); o.scale = (30, 30, 1)
    li = bpy.data.lights.new('sky', 'SUN'); li.energy = .25; li.color = (.55, .65, 1); kit.link(bpy.data.objects.new('sky', li)).rotation_euler = (math.radians(70), 0, math.radians(30))
    glow = bpy.data.lights.new('horizon', 'AREA'); glow.energy = 3000; glow.size = 40; glow.color = (.25, .35, .7)
    go = kit.link(bpy.data.objects.new('horizon', glow)); go.location = (0, 60, 6); go.rotation_euler = (math.radians(-95), 0, 0)
    c, t = cam((0, -6, 1.6), (0, -4, 1.5), (0, 20, .8), lens=30)

def s35_eclipse():              # "Eclipses would end forever."  the Moon sliding off the Sun's disk, corona fading
    kit.world(strength=.3)
    sun = kit.sun_sphere(1.0, 14); sun.location = (0, 40, 0)
    bpy.ops.mesh.primitive_plane_add(size=9, location=(0, 40.5, 0), rotation=(math.radians(90), 0, 0)); cor = bpy.context.object
    m = bpy.data.materials.new('corona'); kit.nodes(m); N, L = m.node_tree.nodes, m.node_tree.links
    o = N.new('ShaderNodeOutputMaterial'); tc = N.new('ShaderNodeTexCoord'); ln = N.new('ShaderNodeVectorMath'); ln.operation = 'LENGTH'
    L.new(tc.outputs['Object'], ln.inputs[0]); mr = N.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value = .5; mr.inputs['From Max'].default_value = 3.0
    mr.inputs['To Min'].default_value = 1; mr.inputs['To Max'].default_value = 0; L.new(ln.outputs['Value'], mr.inputs['Value'])
    pw = N.new('ShaderNodeMath'); pw.operation = 'POWER'; pw.inputs[1].default_value = 3; L.new(mr.outputs[0], pw.inputs[0])
    e = N.new('ShaderNodeEmission'); e.inputs['Color'].default_value = (1, .93, .85, 1)
    mul = N.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; L.new(pw.outputs[0], mul.inputs[0]); L.new(mul.outputs[0], e.inputs['Strength'])
    tr = N.new('ShaderNodeBsdfTransparent'); ad = N.new('ShaderNodeAddShader'); L.new(e.outputs[0], ad.inputs[0]); L.new(tr.outputs[0], ad.inputs[1]); L.new(ad.outputs[0], o.inputs[0])
    cor.data.materials.append(m); str_ = mul.inputs[1]
    mo = moon(R=.79, loc=(0, 30, 0), face_lon=180)      # same apparent size as the Sun (as in a real total eclipse); unlit side faces us
    move(mo, (0, 30, 0), (1.7, 30, .25), F(D * .35), NF)
    kf(str_, 1, 1.0); kf(str_, F(D * .35), 1.0); kf(str_, F(D * .6), 0.0)      # corona only shows during totality
    c, t = cam((0, -1, 0), (0, -.6, 0), (0, 40, 0), lens=120)
    overlays.append({'type': 'label', 'text': 'TOTAL SOLAR ECLIPSE', 'pos': (.5, .1), 'color': (255, 222, 40)})

def s38_artemis():              # "Artemis II flew around it, farther from Earth than any humans before them."
    kit.world(); kit.sun_lamp(SUN, 4.5)
    moon(R=3, loc=(0, 4, -2.6), face_lon=180, spin_deg=3)          # the far side, as the Artemis II crew saw it
    earth(R=.35, loc=(-3.0, 30, 2.2), face_lon=-20, spin_deg=1, clouds=True)
    c, t = cam((.8, -4.0, .8), (-.2, -3.5, .7), (-.8, 10, .3), lens=30)
    overlays.append({'type': 'label', 'text': 'ARTEMIS II · APRIL 2026', 'pos': (.5, .1), 'color': (255, 222, 40)})

def s42_tilt():                 # "Today our axis leans about 23.4 degrees"
    kit.world(); kit.sun_lamp((1, -.2, 0), 4)
    root, sp = earth(loc=(0, 0, 0), face_lon=-40, spin_deg=25, tilt=23.4, sun=(1, -.2, 0))
    axis_line(root, EARTH_R)
    bpy.ops.mesh.primitive_cylinder_add(radius=EARTH_R * .006, depth=EARTH_R * 3.0); v = bpy.context.object; v.data.materials.append(kit.mat_emit('vert', (.7, .75, 1), 2))
    c, t = cam((0, -9.6, .4), (.5, -9.0, .5), (0, 0, 0), lens=34)
    overlays.append({'type': 'label', 'text': 'TILT ≈ 23.4°', 'pos': (.5, .1), 'color': (255, 222, 40)})

def s45_chaos():                # "1993 study: tilt could swing chaotically, from almost zero to about 85 degrees"
    kit.world(); kit.sun_lamp((1, -.2, 0), 4)
    root, sp = earth(loc=(0, 0, 0), face_lon=-40, spin_deg=40, tilt=23.4, sun=(1, -.2, 0))
    axis_line(root, EARTH_R, (1, .45, .3), 8)
    seq = [(1, 23.4), (F(D * .25), 60), (F(D * .5), 8), (F(D * .75), 80), (NF, 35)]
    for f, deg in seq: kit.key(root, f, rotation_euler=(0, math.radians(deg), 0))
    c, t = cam((0, -9.8, .6), (.3, -9.2, .5), (0, 0, 0), lens=34)
    overlays.append({'type': 'label', 'text': 'ILLUSTRATION OF A 1993 SIMULATION: 0° TO ~85° · SPEED NOT REAL', 'pos': (.5, .1), 'color': (255, 140, 90)})

def s48_spin():                 # "the tides act like a slow brake on our planet"
    kit.world(); kit.sun_lamp(SUN, 4)
    root, sp = earth(loc=(-1.4, 0, 0), face_lon=0, spin_deg=60, tilt=0)
    pivot = kit.link(bpy.data.objects.new('bulge_piv', None)); pivot.location = (-1.4, 0, 0); pivot.rotation_euler = (0, 0, math.radians(12))
    tidal_shell(pivot, EARTH_R, 1.12, alpha=.18)          # bulge carried slightly ahead of the Earth-Moon line by Earth's spin
    moon(loc=(3.8, 0, 0))
    c, t = cam((0, -7.6, 4.2), (.3, -7.0, 3.8), (.4, 0, 0), lens=34)
    overlays.append({'type': 'label', 'text': 'TIDAL BULGES EXAGGERATED · NOT TO SCALE', 'pos': (.5, .1), 'color': (120, 220, 255)})

def young_earth(R=EARTH_R, loc=(0, 0, 0)):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=R, location=loc, segments=128, ring_count=64); e = bpy.context.object; kit.smooth(e, 1)
    e.data.materials.append(kit.mat_pbr('lava', 'young_earth'))
    m = e.data.materials[0]; nt = m.node_tree; N, L = nt.nodes, nt.links; b = N['Principled BSDF']
    vor = N.new('ShaderNodeTexVoronoi'); vor.feature = 'DISTANCE_TO_EDGE'; vor.inputs['Scale'].default_value = 22
    mr = N.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value = .025; mr.inputs['From Max'].default_value = 0; L.new(vor.outputs['Distance'], mr.inputs['Value'])
    mul = N.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; mul.inputs[1].default_value = 10; L.new(mr.outputs[0], mul.inputs[0]); L.new(mul.outputs[0], b.inputs['Emission Strength'])
    return e

def s51_past():                 # "go back about four and a half billion years."  molten young Earth, Theia approaching
    kit.world(); kit.sun_lamp(SUN, 3)
    e = young_earth(loc=(0, 2, 0)); kit.key(e, 1, rotation_euler=(0, 0, 0)); kit.key(e, NF, rotation_euler=(0, 0, math.radians(10)))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=EARTH_R * .53, segments=96, ring_count=48); th = bpy.context.object; kit.smooth(th, 1)
    th.data.materials.append(kit.mat_pbr('rock', 'theia'))          # Mars-sized impactor (illustration; Theia's real look is unknown)
    move(th, (5.2, -2.6, 1.3), (3.6, -1.3, .9))
    c, t = cam((-1.5, -9.5, 1.4), (-1.0, -8.8, 1.2), (1.5, 0.5, .3), lens=30)
    overlays.append({'type': 'label', 'text': '~4.5 BILLION YEARS AGO · ARTIST\'S IMPRESSION', 'pos': (.5, .1), 'color': (255, 170, 70)})

def s52_impact():               # "a Mars-sized world ... slammed into the young Earth, and the Moon formed from the debris."
    kit.world(); kit.sun_lamp(SUN, 3)
    e = young_earth(loc=(0, 0, 0)); kit.key(e, 1, rotation_euler=(0, 0, 0)); kit.key(e, NF, rotation_euler=(0, 0, math.radians(25)))
    flash = glow_sphere((1.6, -.8, .6), .5, (1, .7, .35), 0, 'flash')
    s_ = flash.data.materials[0].node_tree.nodes['Emission'].inputs['Strength']
    kf(s_, 1, 0); kf(s_, F(.3), 80); kf(s_, F(1.1), 0)
    kit.key(flash, 1, scale=(.2,) * 3); kit.key(flash, F(1.0), scale=(1.6,) * 3); kit.key(flash, F(1.15), scale=(0,) * 3)
    fl = bpy.data.lights.new('flashlight', 'POINT'); fo = kit.link(bpy.data.objects.new('flashlight', fl)); fo.location = (2.2, -1.4, .9)
    kf_e = lambda f, v: (setattr(fl, 'energy', v), fl.keyframe_insert('energy', frame=f))
    kf_e(1, 0); kf_e(F(.3), 30000); kf_e(F(1.5), 0)
    piv = kit.link(bpy.data.objects.new('disk', None)); piv.rotation_euler = (math.radians(12), 0, 0)
    kit.key(piv, 1, rotation_euler=(math.radians(12), 0, 0)); kit.key(piv, NF, rotation_euler=(math.radians(12), 0, math.radians(70)))
    for i in range(260):        # the debris disk the Moon later gathered from (illustration)
        r = rng.uniform(2.6, 5.2); a = rng.uniform(0, 2 * math.pi); z = rng.gauss(0, .08)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=rng.uniform(.02, .07), location=(r * math.cos(a), r * math.sin(a), z)); p = bpy.context.object
        p.data.materials.append(kit.mat_emit(f'deb{i % 6}', (1, .45 + .1 * (i % 6) / 6, .12), 3 + (i % 4))); p.parent = piv
        kit.key(p, 1, scale=(0,) * 3); kit.key(p, F(.5 + 1.5 * r / 5.2), scale=(1,) * 3)
    c, t = cam((0, -12, 4.5), (.4, -11, 4.0), (0, 0, 0), lens=30)
    overlays.append({'type': 'label', 'text': 'GIANT-IMPACT IDEA · ARTIST\'S IMPRESSION', 'pos': (.5, .1), 'color': (255, 170, 70)})

def s54_laser():                # "Lasers bounced off reflectors left by Apollo astronauts ... 3.8 cm a year."
    kit.world(); kit.sun_lamp(SUN, 4)
    earth(loc=(-3.2, 1.0, -.2), face_lon=-108, spin_deg=3)       # North America facing the Moon side
    moon(loc=(3.2, 0, .4))
    a = Vector((-3.2 + EARTH_R * .9, 1.0 - .5, .45)); b = Vector((3.2 - MOON_R * .95, 0, .45))
    mid = (a + b) / 2; dvec = b - a
    bpy.ops.mesh.primitive_cylinder_add(radius=.012, depth=dvec.length, location=mid); beam = bpy.context.object
    beam.rotation_euler = dvec.to_track_quat('Z', 'Y').to_euler(); beam.data.materials.append(kit.mat_emit('laser', (.1, 1, .15), 20))
    kit.key(beam, 1, scale=(1, 1, .0)); kit.key(beam, F(1.0), scale=(1, 1, 1))
    c, t = cam((0, -10.5, 1.6), (.2, -9.6, 1.4), (0, 0, 0), lens=30)
    overlays.append({'type': 'label', 'text': 'LUNAR LASER RANGING · DISTANCE NOT TO SCALE', 'pos': (.5, .1), 'color': (120, 255, 140)})

def s56_look():                 # "So the next time you look up..." astronaut with Earth and Moon (beauty shot)
    kit.world(); kit.sun_lamp(SUN, 4)
    earth(R=5, loc=(-1.5, 7, -5.2), face_lon=10, spin_deg=2)
    moon(R=.6, loc=(4.2, 9, 1.2))
    a, limbs = astro((-.4, -.8, .1), rot=(5, 0, -20), s=.5)
    kit.key(a, 1, location=(-.4, -.8, .1)); kit.key(a, NF, location=(-.35, -.8, .25))
    fill_light(a, 40)
    c, t = cam((-1.6, -4.4, .5), (-1.2, -3.8, .6), (.6, 4, .5), lens=30)

def s57_end():                  # "Thanks for watching, and follow for more what ifs!"
    kit.world(); kit.sun_lamp(SUN, 4)
    earth(R=EARTH_R, loc=(-1.2, 1.5, -.2), face_lon=-80, spin_deg=4)
    m = moon(loc=(2.4, -.4, .7))
    move(m, (2.4, -.4, .7), (2.2, -.6, .75))
    c, t = cam((.9, -8.2, .8), (.6, -9.0, .9), (.6, .9, .2), lens=34)
    overlays.append({'type': 'cta', 'text': 'FOLLOW FOR MORE WHAT IFS'})

SCENES = {0: s0_gone, 1: s1_empty, 6: s6_scale, 9: s9_night, 13: s13_sky, 15: s15_tides, 35: s35_eclipse,
          38: s38_artemis, 42: s42_tilt, 45: s45_chaos, 48: s48_spin, 51: s51_past, 52: s52_impact, 54: s54_laser, 56: s56_look, 57: s57_end}
if __name__ == '__main__':
    SCENES[idx]()
    for o in bpy.data.objects:
        for m in getattr(o, 'modifiers', []):
            if m.type == 'SUBSURF': m.render_levels = min(m.render_levels, 1)
    os.makedirs(f'{OUT}/s{idx}', exist_ok=True)
    json.dump({'frames': NF, 'overlays': overlays}, open(f'{OUT}/s{idx}/meta.json', 'w'))
    if mode == 'still':
        sc.frame_set(max(1, int(NF * (float(sys.argv[3]) if len(sys.argv) > 3 else .6)))); sc.render.filepath = f'{OUT}/still_{idx}.png'
        bpy.ops.render.render(write_still=True)
    else:
        if os.environ.get('FR'): sc.frame_start, sc.frame_end = map(int, os.environ['FR'].split(','))
        sc.render.image_settings.file_format = 'PNG'; sc.render.filepath = f'{OUT}/s{idx}/f_'; bpy.ops.render.render(animation=True)
