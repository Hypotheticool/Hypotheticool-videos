"""What if the space station fell out of the sky?  One high-res Cycles still per plate (animated in 2D by iss_anim.py).
python3 iss_plate.py <plate> [res_scale]  -> /home/claude/b3d/iss/plates/<plate>.png (+ projected feature points in plates/fx_<plate>.json)
Real data: NASA 3D Resources ISS (IGOAL) and Skylab models, real Earth maps (kit.earth). Earth/ISS distances are NOT to scale
(the station is drawn huge so it reads); the football-field plate IS to scale (ISS ~109 m vs a 109.7 m field incl. end zones).
plates: orbit, hero, field, us, escape, fire, breakup, track, skylab, outback, tug, nemo"""
import sys, math, os, json, random
sys.path.insert(0, '/home/claude/b3d')
import bpy, kit
from mathutils import Vector, Euler
from bpy_extras.object_utils import world_to_camera_view
name = sys.argv[1]; S = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
OUT = '/home/claude/b3d/iss/plates'; os.makedirs(OUT, exist_ok=True)
W, H = int(1080 * S), int(1920 * S)
sc = kit.reset(res=(W, H), samples=int(os.environ.get('SAMPLES', 32)))
sc.cycles.adaptive_threshold = 0.04; sc.cycles.max_bounces = 4
FX = {}
ISS = 'International Space Station (ISS) (D) (IGOAL)'

def look(loc, at, lens=32):
    cam, tgt = kit.camera(loc, at, lens=lens); sc.camera = cam; return cam

def proj(key, p):
    bpy.context.view_layer.update(); v = world_to_camera_view(sc, sc.camera, Vector(p)); FX[key] = [round(v.x, 4), round(1 - v.y, 4)]

def area(loc, at, energy, color=(1, 1, 1), size=3):
    li = bpy.data.lights.new('ar', 'AREA'); li.energy = energy; li.color = color; li.size = size
    o = kit.link(bpy.data.objects.new('ar', li)); o.location = loc
    o.rotation_euler = (Vector(at) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler(); return o

def prim(kind, mat, loc, scale=(1, 1, 1), rot=(0, 0, 0), sub=0, bevel=0.0, parent=None, **kw):
    getattr(bpy.ops.mesh, 'primitive_' + kind + '_add')(**kw); o = bpy.context.object
    o.location = loc; o.scale = scale; o.rotation_euler = rot; o.data.materials.append(mat)
    if sub or bevel: kit.smooth(o, sub, bevel)
    if parent: o.parent = parent
    return o

def station(size=10.0, rot=(0, 0, 0), loc=(0, 0, 0)):
    r = kit.nasa_model(ISS, size, 'X'); r.rotation_euler = tuple(math.radians(a) for a in rot); r.location = loc
    if NOSHADOW:
        for o in meshes(r): o.visible_shadow = False
    return r
NOSHADOW = True

def meshes(root): return [o for o in root.children_recursive if o.type == 'MESH']

def earth_at(R, center, sun, face_lon, clouds=True, lights=None):
    er, spin = kit.earth(R, sun, tilt_deg=0, clouds=clouds, atmo=True, face_lon=face_lon); er.location = center; return er, spin

def dragon(parent=None, s=1.0, tug=False):
    """Crew Dragon-style capsule (ILLUSTRATION): white capsule ~4 m wide with dark windows and nose cap, trunk below
    (half solar cells, two fins). tug=True: a longer service trunk with engine bells (the planned deorbit vehicle is a Dragon with a much larger trunk)."""
    g = kit.link(bpy.data.objects.new('dragon', None)); g.scale = (s, s, s)
    if parent: g.parent = parent
    white = kit.mat_principled('dwhite', (.9, .9, .92), rough=.35, coat=.3); dark = kit.mat_principled('ddark', (.03, .03, .04), rough=.3)
    cells = kit.mat_panel('dcells', (.03, .05, .14)) if hasattr(kit, 'mat_panel') else dark
    prim('cone', white, (0, 0, 1.2), vertices=64, radius1=2.0, radius2=1.0, depth=2.4, parent=g, sub=1)
    prim('uv_sphere', white, (0, 0, 2.45), (1.0, 1.0, .45), segments=48, ring_count=24, parent=g)
    prim('cylinder', dark, (0, 0, -.02), (1, 1, 1), vertices=64, radius=2.02, depth=.08, parent=g)
    for k in range(4):
        a = k * math.pi / 2 + .4; prim('uv_sphere', dark, (1.55 * math.cos(a), 1.55 * math.sin(a), 1.25), (.22, .22, .3), segments=16, ring_count=8,
                                       rot=(0, 0, a), parent=g)
    L = 6.5 if tug else 2.8
    prim('cylinder', white, (0, 0, -L / 2 - .1), vertices=64, radius=1.85, depth=L, parent=g)
    for k in range(10):   # solar cells on half of the trunk
        a = math.pi * k / 10; prim('cube', cells, (1.87 * math.cos(a), 1.87 * math.sin(a), -L / 2 - .1), (.02, .26, L * .45), rot=(0, 0, a), size=2, parent=g)
    for a in (0, math.pi):
        prim('cube', white, (2.1 * math.cos(a), 2.1 * math.sin(a), -L + .5), (.45, .05, .5), rot=(0, 0, a), size=2, parent=g)
    if tug:
        steel = kit.mat_pbr('steel')
        for k in range(4):
            a = k * math.pi / 2 + math.pi / 4
            prim('cone', steel, (1.0 * math.cos(a), 1.0 * math.sin(a), -L - .55), vertices=32, radius1=.45, radius2=.18, depth=.9, parent=g)
    return g

def plume(parent, loc, length, radius, strength=25, color=(1, .65, .3)):
    m = kit.mat_emit('plume', color, strength)
    o = prim('cone', m, loc, vertices=32, radius1=radius, radius2=radius * .15, depth=length, parent=parent)
    return o

# ------------------------------------------------------------------ plates
def p_orbit():
    """ISS over the sunlit Earth (Atlantic / Americas), seen from above and behind"""
    sun = Vector((-.6, -.35, .7)).normalized(); kit.world(strength=.35); kit.sun_lamp(sun, 3.0)
    earth_at(120, (0, 40, -128), sun, -50)
    station(10, (8, -4, -18), (0, 0, 0))
    area((0, -6, -8), (0, 0, 0), 600, (.45, .65, 1), 10)          # blue Earth-shine from below
    look((-3.5, -15.5, 6.0), (0, 1.5, -1.2), 32)

def p_hero():
    """low angle close-up on the modules and trusses against black space and the blue limb"""
    sun = Vector((.7, -.4, .55)).normalized(); kit.world(strength=.3); kit.sun_lamp(sun, 4.5)
    earth_at(200, (0, 60, -214), sun, -20)
    station(10, (0, 0, 32), (0, 0, 0))
    area((0, -5, -6), (0, 0, 0), 500, (.45, .65, 1), 8)
    look((2.2, -6.0, -1.4), (0, 0, .2), 24)

def p_field():
    """TO SCALE: the ISS (~109 m) hovering over an American football field (120 yd = 109.7 m incl. end zones) at dusk"""
    kit.sky(sun_elevation=18, sun_rotation=235, strength=.25, sun_lamp_energy=3.5)
    Lf, Wf = 109.73, 48.77; yd = 0.9144
    grass_a = kit.mat_principled('grassA', (.05, .19, .045), rough=.9); grass_b = kit.mat_principled('grassB', (.065, .23, .055), rough=.9)
    white = kit.mat_emit('lines', (1, 1, 1), 1.2); ez = kit.mat_principled('endzone', (.08, .12, .35), rough=.85)
    ground = kit.mat_principled('ground', (.012, .016, .014), rough=.9)
    prim('plane', ground, (0, 0, -.05), (300, 300, 1), size=1)
    for k in range(20):   # mowing stripes, 5 yd each, between the goal lines
        x0 = -Lf / 2 + 10 * yd + k * 5 * yd; prim('plane', grass_a if k % 2 else grass_b, (x0 + 2.5 * yd, 0, 0), (5 * yd, Wf, 1), size=1)
    for s in (-1, 1): prim('plane', ez, (s * (Lf / 2 - 5 * yd), 0, 0), (10 * yd, Wf, 1), size=1)
    for k in range(21):   # yard lines every 5 yd
        x = -Lf / 2 + 10 * yd + k * 5 * yd; prim('plane', white, (x, 0, .02), (.12 if k % 2 else .2, Wf, 1), size=1)
    for s in (-1, 1):
        prim('plane', white, (0, s * Wf / 2, .02), (Lf, .25, 1), size=1); prim('plane', white, (s * Lf / 2, 0, .02), (.25, Wf, 1), size=1)
    for s in (-1, 1):   # goal posts
        gp = kit.mat_principled('post', (1, .85, .1), rough=.4)
        prim('cylinder', gp, (s * Lf / 2, 0, 3.05), (1, 1, 1), vertices=12, radius=.15, depth=6.1)
        prim('cylinder', gp, (s * Lf / 2, 0, 6.1), (1, 1, 1), rot=(math.pi / 2, 0, 0), vertices=12, radius=.12, depth=5.64)
        for y in (-2.82, 2.82): prim('cylinder', gp, (s * Lf / 2, y, 6.1 + 4.5), (1, 1, 1), vertices=12, radius=.1, depth=9)
    r = station(108.8, (0, 0, 0), (0, 0, 12))
    look((0, -95, 255), (0, 4, 4), 40)
    proj('field_l', (-Lf / 2, 0, 0)); proj('field_r', (Lf / 2, 0, 0)); proj('iss_l', (-54.4, 0, 38)); proj('iss_r', (54.4, 0, 38))
    for x in (-60, 0, 60): area((x, -40, 90), (x, 0, 10), 60000, (1, .85, .7), 40)     # stadium-ish floodlight fill

def p_us():
    """the real Earth turned to North America, daylight; the coast-to-coast path is drawn in 2D from projected points"""
    sun = Vector((-.5, -.8, .35)).normalized(); kit.world(strength=.3); kit.sun_lamp(sun, 4.0)
    R = 10; er, spin = earth_at(R, (0, 0, 0), sun, -97)
    c = kit.latlon(39, -97, 1, -97); look(tuple(c * 25.5), (0, 0, 0), 50)
    path = [(40.71, -74.01), (39.5, -84), (38.6, -95), (37, -105), (35.2, -112), (34.05, -118.24)]
    pts = []
    for (a1, o1), (a2, o2) in zip(path[:-1], path[1:]):
        p1, p2 = kit.latlon(a1, o1, 1, -97), kit.latlon(a2, o2, 1, -97)
        for k in range(8): pts.append(p1.slerp(p2, k / 8) if hasattr(p1, 'slerp') else p1.lerp(p2, k / 8))
    pts.append(kit.latlon(*path[-1], 1, -97))
    FX['route'] = []
    for i, p in enumerate(pts):
        proj('_t', p.normalized() * R * 1.002); FX['route'].append(FX.pop('_t'))
    proj('ny', kit.latlon(40.71, -74.01, R, -97)); proj('la', kit.latlon(34.05, -118.24, R, -97))

def p_escape():
    """the crew pulls away from the station in its capsule (ILLUSTRATION), Earth below"""
    sun = Vector((-.55, -.5, .65)).normalized(); kit.world(strength=.3); kit.sun_lamp(sun, 4.2)
    earth_at(150, (0, 60, -160), sun, -30)
    station(10, (6, 0, -25), (0, 9, 0))
    d = dragon(s=.3); d.location = (1.3, -.6, 1.0); d.rotation_euler = (math.radians(-60), math.radians(15), math.radians(20))
    for k in range(3):   # small Draco thruster puffs
        a = k * 2.1; plume(d, (1.9 * math.cos(a), 1.9 * math.sin(a), 1.6), .9, .12, 8, (.9, .92, 1))
    area((0, -4, -6), (0, 0, 0), 400, (.45, .65, 1), 8)
    look((-1.6, -9.5, 2.4), (.4, 3, -.4), 30)

def reentry_set(sun, face_lon, R=150):
    kit.world(strength=.05); kit.sun_lamp(Vector((0, .75, -.66)).normalized(), 2.5, (1, .75, .5))
    er, spin = earth_at(R, (0, 70, -R - 12), sun, face_lon)
    return er

def p_fire():
    """HOOK: the ISS plunging through the upper atmosphere, wrapped in glowing plasma, over the night side at dawn"""
    sun = Vector((0, .75, -.66)).normalized(); reentry_set(sun, -40)
    r = station(10, (14, 8, -22), (0, 0, 0)); kit.heat_glow(r, [(1, .35)], (1, .38, .08))
    kit.link(bpy.data.objects.new('pt', bpy.data.lights.new('pt', 'POINT'))).location = (0, -2, 2)
    bpy.data.lights['pt'].energy = 4000; bpy.data.lights['pt'].color = (1, .45, .12); bpy.data.lights['pt'].shadow_soft_size = 3
    bpy.data.lights['pt'].use_custom_distance = True; bpy.data.lights['pt'].cutoff_distance = 9
    look((-2.5, -17, 3.5), (0, 3, -.5), 30)
    proj('iss', (0, 0, 0)); proj('wing_l', (-4.5, -.5, -.6)); proj('wing_r', (4.5, .5, .6))

def p_breakup():
    """the station breaking apart ~50 miles up: modules, trusses and wings flying apart, each piece glowing"""
    sun = Vector((0, .75, -.66)).normalized(); reentry_set(sun, -40)
    r = station(10, (14, 8, -22), (0, 0, 0)); bpy.context.view_layer.update()
    rng = random.Random(4); ms = meshes(r)
    ctr = Vector((0, 0, 0))
    for o in ms:
        bb = [o.matrix_world @ Vector(c) for c in o.bound_box]; c = sum(bb, Vector()) / 8
        d = c - ctr; push = d * (.35 + .4 * rng.random()) + Vector((rng.uniform(-.6, .6), rng.uniform(-.2, 1.4), rng.uniform(-.6, .6)))
        mw = o.matrix_world.copy(); o.parent = None; o.matrix_world = mw
        o.location += push; o.rotation_euler.rotate(Euler((rng.uniform(-.5, .5), rng.uniform(-.5, .5), rng.uniform(-.5, .5))))
    kit.heat_glow(r, [(1, .55)], (1, .36, .06))
    for o in ms: pass
    big = sorted(ms, key=lambda o: -max(o.dimensions))[:9]
    for k, o in enumerate(big):
        bb = [o.matrix_world @ Vector(c) for c in o.bound_box]; c = sum(bb, Vector()) / 8
        h = kit.link(bpy.data.objects.new('h', None)); h.location = c; h.rotation_euler = (math.radians(-70), 0, math.radians(-18))
        FX.setdefault('pieces', [])
        bpy.context.view_layer.update(); v = world_to_camera_view(sc, sc.camera, c) if sc.camera else None
        FX['pieces'].append(list(c))
    li = bpy.data.lights.new('pt', 'POINT'); li.energy = 6000; li.color = (1, .45, .12); li.shadow_soft_size = 4; li.use_custom_distance = True; li.cutoff_distance = 10
    kit.link(bpy.data.objects.new('pt', li)).location = (0, -2, 2)
    look((-2.5, -17, 3.5), (0, 3, -.5), 28)
    cs = FX.pop('pieces', [])
    FX['pieces'] = []
    for c in cs:
        proj('_p', c); FX['pieces'].append(FX.pop('_p'))

def p_track():
    """the station's real ground track (51.6 degree orbit, about 3 orbits) on the night-and-day Earth over Africa, Europe and Asia"""
    sun = Vector((-.4, -.85, .3)).normalized(); kit.world(strength=.3); kit.sun_lamp(sun, 4.0)
    R = 10; earth_at(R, (0, 0, 0), sun, 40)
    inc = math.radians(51.6); pts = []
    for k in range(0, 3 * 360 + 1, 6):
        u = math.radians(k); lat = math.degrees(math.asin(math.sin(inc) * math.sin(u)))
        lon = math.degrees(math.atan2(math.cos(inc) * math.sin(u), math.cos(u))) - 22.9 * k / 360 - 20
        pts.append((lat, (lon + 180) % 360 - 180))
    segs = [[pts[0]]]
    for a, b in zip(pts[:-1], pts[1:]):
        if abs(a[1] - b[1]) > 180: segs.append([b])
        else: segs[-1].append(b)
    for i, sg in enumerate(segs):
        if len(sg) > 1: kit.geo_path(sg, R, 40, h=.09, width=.13, color=(1, .78, .25), strength=16, name=f'trk{i}', steps=3)
    for la in (51.6, -51.6):   # the band edges (thin)
        kit.geo_path([(la, lo) for lo in range(-180, 181, 10)], R, 40, h=.085, width=.03, color=(.5, .8, 1), strength=3, name=f'edge{la}', steps=2)
    c = kit.latlon(18, 40, 1, 40); look(tuple(c * 27), (0, 0, 0), 50)

def p_skylab():
    """1979: Skylab (real NASA model) burning up over the night side, Western Australia below"""
    sun = Vector((.1, .8, -.6)).normalized(); kit.world(strength=.05); kit.sun_lamp(sun, .6, (1, .8, .6))
    R = 150; er, spin = earth_at(R, (0, 0, 0), sun, 122)
    c = kit.latlon(-31, 122, 1, 122)
    pos = c * (R + 9)
    r = kit.nasa_model('Skylab', 6, 'X'); r.location = pos; r.rotation_euler = (math.radians(20), math.radians(-25), math.radians(30))
    kit.heat_glow(r, [(1, .45)], (1, .4, .1))
    li = bpy.data.lights.new('pt', 'POINT'); li.energy = 1500; li.color = (1, .45, .12); li.shadow_soft_size = 3; li.use_custom_distance = True; li.cutoff_distance = 5
    kit.link(bpy.data.objects.new('pt', li)).location = pos + c * 3
    look(tuple(pos + c * 5 + Vector((-2.5, -9, 0))), tuple(pos - c * 5), 30)
    proj('esperance', kit.latlon(-33.86, 121.89, R, 122)); proj('skylab', pos)

def p_outback():
    """ILLUSTRATION: a scorched Skylab tank and twisted panel on the red Western Australian scrub at dawn"""
    kit.sky(sun_elevation=9, sun_rotation=80, strength=.3, sun_lamp_energy=3.5)
    t = kit.terrain(size=80, height=.35, scale=4, kind='desert', seed=3)
    cr = [n for n in t.data.materials[0].node_tree.nodes if n.type == 'VALTORGB'][0]
    cr.color_ramp.elements[0].color = (.32, .1, .035, 1); cr.color_ramp.elements[1].color = (.62, .25, .09, 1)
    char = kit.mat_principled('char', (.06, .05, .045), rough=.55, metal=.6)
    burnt = kit.mat_principled('burnt', (.32, .2, .12), rough=.5, metal=.8)
    s = prim('uv_sphere', char, (0, 6, .55), (1.1, 1.1, 1.0), segments=64, ring_count=32, sub=1)
    b = s.modifiers.new('d', 'DISPLACE'); tx = bpy.data.textures.new('dent', 'CLOUDS'); tx.noise_scale = .5; b.texture = tx; b.strength = .12
    prim('cylinder', burnt, (.0, 6, 1.6), (1, 1, 1), vertices=24, radius=.18, depth=.4)
    for k in range(5):   # twisted panel fragments
        p = prim('cube', burnt if k % 2 else char, (-2.5 + 1.4 * k + random.Random(k).uniform(-.3, .3), 3.8 + .6 * (k % 3), .15), (.7, .35, .02),
                 rot=(random.Random(k).uniform(-.5, .5), random.Random(k + 9).uniform(-.4, .4), k), size=2)
        sw = p.modifiers.new('sw', 'SIMPLE_DEFORM'); sw.deform_method = 'TWIST'; sw.angle = .8
    for k in range(40):   # spinifex clumps
        rr = random.Random(100 + k); x, y = rr.uniform(-14, 14), rr.uniform(2, 30)
        prim('ico_sphere', kit.mat_principled('spin', (.35, .33, .15), rough=.9), (x, y, .1), (.5, .5, .25), subdivisions=2)
    look((-.8, -1.5, 2.2), (0, 6, .4), 30)

def p_tug():
    """ILLUSTRATION: the deorbit tug docked at the end of the station, engines firing, over the South Pacific"""
    sun = Vector((-.5, -.55, .65)).normalized(); kit.world(strength=.3); kit.sun_lamp(sun, 4.0)
    earth_at(150, (0, 60, -160), sun, -130)
    r = station(10, (6, 0, -10), (0, 0, 0)); bpy.context.view_layer.update()
    P = [o.matrix_world @ Vector(c) for o in meshes(r) for c in o.bound_box]; ymin = min(p.y for p in P)
    near = [p for p in P if p.y < ymin + .3]; cx = sum(p.x for p in near) / len(near); cz = sum(p.z for p in near) / len(near)
    d = dragon(s=.09, tug=True); d.location = (cx, ymin - 2.9 * .09, cz); d.rotation_euler = (math.radians(-90), 0, 0)
    for k in range(4):
        a = k * math.pi / 2 + math.pi / 4; plume(d, (1.0 * math.cos(a), 1.0 * math.sin(a), -6.5 - 3.2), 4.5, .55, 30)
    area((0, -4, -6), (0, 0, 0), 400, (.45, .65, 1), 8)
    tg = d.location * .62 + Vector((0, 0, -.4)); look(tuple(tg + Vector((-7.5, -7.0, 3.6))), tuple(tg), 30)
    proj('tug', d.location); proj('tug_end', (cx, ymin - 10.4 * .09, cz))

def p_nemo():
    """Point Nemo (48.88 S, 123.39 W), the spot farthest from land, on the real Earth in daylight"""
    sun = Vector((-.5, -.8, .2)).normalized(); kit.world(strength=.3)
    kit.sun_lamp(sun, 2.8); R = 10; er, spin = earth_at(R, (0, 0, 0), sun, -123.4)
    c = kit.latlon(-40, -123.4, 1, -123.4); look(tuple(c * 26), (0, 0, 0), 50)
    proj('nemo', kit.latlon(-48.88, -123.39, R, -123.4))
    for nm, ll in (('ducie', (-24.68, -124.79)), ('motu', (-27.2, -109.4)), ('maher', (-74.0, -102.0))):
        proj(nm, kit.latlon(*ll, R, -123.4))

P = {k[2:]: v for k, v in globals().items() if k.startswith('p_')}
P[name]()
for mt in bpy.data.materials:
    try: mt.cycles.emission_sampling = 'NONE'
    except Exception: pass
    if mt.node_tree:
        for nd in mt.node_tree.nodes:
            if nd.type == 'TEX_IMAGE': nd.interpolation = 'Linear'
for mt in bpy.data.materials:   # keep the emissive plasma/route materials sampled as lights where they matter
    if mt.name.startswith(('plasma', 'pb', 'plume')):
        try: mt.cycles.emission_sampling = 'AUTO'
        except Exception: pass
if FX: json.dump(FX, open(f'{OUT}/fx_{name}.json', 'w'))
sc.render.filepath = f'{OUT}/{name}.png'; bpy.ops.render.render(write_still=True)
print('plate', name, 'done')
