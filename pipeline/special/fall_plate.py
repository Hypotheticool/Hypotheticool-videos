"""WYR: fall from a plane into snow or the ocean. One high-res Cycles still per plate (animated in 2D by fall_anim.py).
python3 fall_plate.py <plate> [res_scale]  -> wyrfall/plates/<plate>.png
plates: faller (RGBA, Leo falling, front), faller34 (RGBA, 3/4 from below),
        forest (aerial: moonlit snowy pine forest at night, looking down), ocean (aerial: open ocean at sunset, looking down),
        sea (low over the waves at sunset), high (sunset above the clouds, ~5 km up), bomber (four-engine WWII bomber burning at night),
        crater (ground level: deep snow among young pines, a body-shaped hole, moonlight + warm fire glow),
        wreck (snowy wooded slope at dusk, the tail section of a twin-jet airliner with a T-tail), europe (real Earth, central Europe)"""
import sys, math, os, random
sys.path.insert(0, '/home/claude/b3d')
import bpy, kit
from mathutils import Vector
name = sys.argv[1]; S = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
OUT = '/home/claude/b3d/wyrfall/plates'; os.makedirs(OUT, exist_ok=True)
W, H = int(1080 * S), int(1920 * S)
sc = kit.reset(res=(W, H), samples=int(os.environ.get('SAMPLES', 40)))
sc.cycles.adaptive_threshold = 0.03; sc.cycles.max_bounces = 4
random.seed(7)

def add(prim, mat, loc, scale, rot=(0, 0, 0), bevel=0.0, sub=1, parent=None, **kw):
    getattr(bpy.ops.mesh, prim)(**kw); ob = bpy.context.object; ob.location = loc; ob.scale = scale; ob.rotation_euler = rot
    ob.data.materials.append(mat); kit.smooth(ob, sub, bevel)
    if parent: ob.parent = parent
    return ob

def area(loc, aim, energy, size, color):
    d = bpy.data.lights.new('a', 'AREA'); d.energy = energy; d.size = size; d.color = color
    ob = kit.link(bpy.data.objects.new('a', d)); ob.location = loc
    ob.rotation_euler = (Vector(aim) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler(); return ob

def point(loc, energy, color, r=.1):
    d = bpy.data.lights.new('p', 'POINT'); d.energy = energy; d.color = color; d.shadow_soft_size = r
    ob = kit.link(bpy.data.objects.new('p', d)); ob.location = loc; return ob

def night_world(horizon=(.03, .07, .12), zenith=(.0, .005, .016), stars=.5, glow=None):
    w = bpy.data.worlds.new('night'); sc.world = w; nt, N, L = kit.nodes(w)
    out = N.new('ShaderNodeOutputWorld'); bg = N.new('ShaderNodeBackground'); tc = N.new('ShaderNodeTexCoord')
    env = N.new('ShaderNodeTexEnvironment'); env.image = bpy.data.images.load(kit.tex_path('stars_milky_way.jpg'), check_existing=True)
    L.new(tc.outputs['Generated'], env.inputs['Vector'])
    gm = N.new('ShaderNodeGamma'); gm.inputs['Gamma'].default_value = 1.8; L.new(env.outputs['Color'], gm.inputs['Color'])
    sm = N.new('ShaderNodeVectorMath'); sm.operation = 'SCALE'; sm.inputs['Scale'].default_value = stars; L.new(gm.outputs[0], sm.inputs[0])
    sep = N.new('ShaderNodeSeparateXYZ'); L.new(tc.outputs['Generated'], sep.inputs[0])
    cr = N.new('ShaderNodeValToRGB'); L.new(sep.outputs['Z'], cr.inputs['Fac'])
    cr.color_ramp.elements[0].position = 0.0; cr.color_ramp.elements[0].color = (*(glow or horizon), 1)
    cr.color_ramp.elements[1].position = .4; cr.color_ramp.elements[1].color = (*zenith, 1)
    if glow: e = cr.color_ramp.elements.new(.08); e.color = (*horizon, 1)
    ad = N.new('ShaderNodeVectorMath'); ad.operation = 'ADD'; L.new(sm.outputs[0], ad.inputs[0]); L.new(cr.outputs['Color'], ad.inputs[1])
    L.new(ad.outputs[0], bg.inputs['Color']); L.new(bg.outputs[0], out.inputs['Surface'])

def snow_ground(size=300, height=3, seed=3, scale=3):
    ter = kit.terrain(size=size, height=height, scale=scale, kind='snow', seed=seed, res=8)
    bs = [n for n in ter.data.materials[0].node_tree.nodes if n.type == 'BSDF_PRINCIPLED'][0]; bs.inputs['Roughness'].default_value = .8
    return ter

PINE = None
def pine_proto():
    """a young spruce/pine: stacked drooping cones of dark needles, each tier capped with snow, plus a bark trunk"""
    global PINE
    if PINE: return PINE
    col = bpy.data.collections.new('pine'); bpy.context.scene.collection.children.link(col)
    needles = kit.mat_principled('needles', (.02, .07, .045), rough=.8); snow = kit.mat_pbr('snow', 'pinesnow'); bark = kit.mat_pbr('bark', 'pinebark')
    objs = []
    bpy.ops.mesh.primitive_cylinder_add(radius=.12, depth=2.2, location=(0, 0, 1.1), vertices=10); t = bpy.context.object; t.data.materials.append(bark); objs.append(t)
    for k in range(6):
        z = .8 + k * 1.05; r = 2.0 * (1 - k / 6.8)
        bpy.ops.mesh.primitive_cone_add(radius1=r, depth=1.7, location=(0, 0, z), vertices=14); c = bpy.context.object; c.data.materials.append(needles)
        dm = c.modifiers.new('d', 'DISPLACE'); tx = bpy.data.textures.new('pn', 'CLOUDS'); tx.noise_scale = .25; dm.texture = tx; dm.strength = .25; objs.append(c)
        bpy.ops.mesh.primitive_cone_add(radius1=r * .82, depth=.7, location=(0, 0, z + .42), vertices=14); s = bpy.context.object; s.data.materials.append(snow)
        dm = s.modifiers.new('d', 'DISPLACE'); dm.texture = tx; dm.strength = .15; objs.append(s)
    for o in objs:
        for c0 in o.users_collection: c0.objects.unlink(o)
        col.objects.link(o)
    col.hide_render = False; PINE = col
    bpy.context.view_layer.layer_collection.children['pine'].exclude = True
    return col

def forest(n, area_xy, z_of=None, scale=(.7, 1.4), avoid=None, seed=1):
    random.seed(seed); col = pine_proto(); out = []
    for i in range(n):
        x = random.uniform(*area_xy[0]); y = random.uniform(*area_xy[1])
        if avoid and (x - avoid[0]) ** 2 + (y - avoid[1]) ** 2 < avoid[2] ** 2: continue
        ob = bpy.data.objects.new(f'pine{i}', None); ob.instance_type = 'COLLECTION'; ob.instance_collection = col
        s = random.uniform(*scale); ob.scale = (s, s, s * random.uniform(.9, 1.2)); ob.rotation_euler = (random.uniform(-.05, .05), random.uniform(-.05, .05), random.uniform(0, 6.28))
        ob.location = (x, y, z_of(x, y) if z_of else 0); kit.link(ob); out.append(ob)
    return out

def leo_falling(face='scared', who='leo'):
    """Leo (the jumpy one) falling, cartoon convention: facing the viewer, arms flung up and out, legs splayed"""
    root, parts = kit.character(who, (0, 0, 0), 1.0)
    for side, nm in ((-1, 'arm_l'), (1, 'arm_r')):
        parts[nm].rotation_euler = (math.radians(-15), -side * math.radians(140), 0)
    for side, nm in ((-1, 'leg_l'), (1, 'leg_r')):
        parts[nm].rotation_euler = (math.radians(-20), -side * math.radians(24), 0)
    kit.set_expr(parts, 1, face)
    return root, parts

def far_sea(oc):
    """flat sea out to the horizon beyond the simulated patch (same material), so the horizon never shows an edge"""
    md = oc.modifiers['Ocean']; md.repeat_x = md.repeat_y = 8
    bpy.ops.mesh.primitive_plane_add(size=60000, location=(0, 0, -4.0)); p = bpy.context.object; p.data.materials.append(oc.data.materials[0])

if name in ('faller', 'faller34', 'silfaller'):
    sc.render.film_transparent = True
    w = bpy.data.worlds.new('w'); sc.world = w; nt, N, L = kit.nodes(w); bg = N.new('ShaderNodeBackground'); o = N.new('ShaderNodeOutputWorld')
    bg.inputs['Color'].default_value = (.05, .08, .12, 1); bg.inputs['Strength'].default_value = .6; L.new(bg.outputs[0], o.inputs[0])
    root, parts = leo_falling(who='nora' if name == 'silfaller' else 'leo')   # silfaller: rendered only as a dark silhouette (round flying-helmet-like head)
    kit.sun_lamp((.4, -.6, .6), 3.0, (1, .75, .5))                  # warm key (sunset)
    area((-2, 1, -1.5), (0, 0, 0), 120, 3, (.4, .65, 1))            # cool bounce from below (snow/sea)
    area((1.5, 2.5, 1.5), (0, 0, .3), 200, 2, (1, .6, .35))         # rim
    if name == 'faller': cam, _ = kit.camera((0, -3.2, .2), (0, 0, .52), lens=75)
    elif name == 'silfaller': cam, _ = kit.camera((1.2, -2.9, .6), (0, 0, .52), lens=75)
    else: cam, _ = kit.camera((1.9, -2.5, -.4), (0, 0, .52), lens=75)

elif name == 'forest':
    night_world(stars=.5, glow=(.09, .07, .08))
    kit.sun_lamp((-.5, .4, .55), 1.1, (.55, .7, 1.0))              # moonlight
    ter = snow_ground(400, 8, seed=5, scale=1.5)
    forest(900, ((-60, 60), (-30, 110)), scale=(.8, 1.6), seed=3)
    point((25, 70, 3), 60000, (1, .45, .15), 4)                     # a burning wreck far off (warm accent)
    cam, _ = kit.camera((0, -38, 70), (0, 40, 0), lens=30)

elif name == 'ocean':
    kit.sky(sun_elevation=3, sun_rotation=10, strength=.18, dust=2.0, sun_lamp_energy=4.0)
    oc = kit.ocean(size=200, wave_scale=1.0, wind=12, choppy=1.1, foam=False, resolution=16); oc.scale = (5, 5, 5); far_sea(oc)
    cam, _ = kit.camera((0, -20, 160), (0, 180, 0), lens=26)

elif name == 'sea':
    kit.sky(sun_elevation=2.5, sun_rotation=10, strength=.18, dust=2.0, sun_lamp_energy=4.0)
    oc = kit.ocean(size=60, wave_scale=1.0, wind=11, choppy=1.0, foam=False, resolution=18); oc.scale = (2, 2, 2); far_sea(oc)
    cam, _ = kit.camera((0, -6, 7), (0, 30, 0), lens=24)

elif name == 'high':
    kit.sky(sun_elevation=1.5, sun_rotation=0, strength=.2, dust=1.5, sun_lamp_energy=3.0)
    for k in range(7):
        x = (k - 3) * 9 + random.uniform(-3, 3); y = 18 + random.uniform(0, 40)
        kit.volume_cloud(loc=(x, y, -6 + random.uniform(-1, 1)), size=(10, 8, 2.4), density=2.0, kind='cloud', seed=k)
    sc.cycles.volume_step_rate = 4.0; sc.cycles.volume_bounces = 0
    cam, _ = kit.camera((0, -8, 2), (0, 40, -4), lens=24)

elif name == 'bomber':
    night_world(horizon=(.06, .1, .16), zenith=(.0, .006, .018), stars=.7)
    kit.sun_lamp((-.6, .3, .5), .9, (.55, .7, 1.0))
    # four-engine WWII heavy bomber (generic, built to Lancaster-like proportions: 31 m span, 21 m long, twin oval fins)
    root = kit.link(bpy.data.objects.new('bomber', None))
    skin = kit.mat_principled('skin', (.05, .055, .05), rough=.55, metal=.2); glass = kit.mat_principled('glass', (.2, .3, .35), rough=.05, metal=.5)
    add('primitive_cylinder_add', skin, (0, 0, 0), (1.0, 1.0, 10.5), rot=(math.radians(90), 0, 0), vertices=32, bevel=.0, parent=root)
    add('primitive_uv_sphere_add', skin, (0, -10.5, 0), (.95, 1.4, .95), parent=root)
    add('primitive_uv_sphere_add', skin, (0, 10.6, 0), (.6, 1.4, .6), parent=root)
    add('primitive_cube_add', skin, (0, -2.0, -.2), (15.5, 2.2, .22), bevel=.15, parent=root)                 # main wing
    add('primitive_cube_add', skin, (0, 9.2, .3), (5.0, 1.0, .12), bevel=.08, parent=root)                    # tailplane
    for sx in (-5.0, 5.0):
        add('primitive_uv_sphere_add', skin, (sx, 9.5, 1.3), (.15, 1.2, 1.9), parent=root)                    # twin oval fins
    eng = []
    for sx in (-8.2, -3.9, 3.9, 8.2):
        e = add('primitive_cylinder_add', skin, (sx, -3.4, -.25), (.6, .6, 1.8), rot=(math.radians(90), 0, 0), vertices=24, bevel=.0, parent=root)
        add('primitive_cone_add', skin, (sx, -5.6, -.25), (.6, .6, .5), rot=(math.radians(90), 0, 0), vertices=24, parent=root)
        eng.append(e)
    root.location = (0, 0, 0); root.rotation_euler = (math.radians(-6), math.radians(12), math.radians(-28))
    fire = kit.mat_emit('fire', (1, .32, .04), 9)
    for k in range(5):   # burning inner starboard wing + engine, flames streaming back
        add('primitive_uv_sphere_add', fire, (-3.9 + random.uniform(-.6, .6), -1.0 + k * 1.6, .3 + random.uniform(0, .4)), (.7 - k * .08, 1.4, .55 - k * .06), parent=root)
    point((-4, 0, 1.5), 9000, (1, .4, .1), 2.5)
    sc.cycles.volume_step_rate = 3.0; sc.cycles.volume_bounces = 0
    cam, _ = kit.camera((-52, -14, 10), (0, 1, 0), lens=42)

elif name == 'crater':
    night_world(stars=.45, glow=(.12, .08, .07))
    kit.sun_lamp((-.5, .5, .45), 1.0, (.55, .7, 1.0))
    ter = snow_ground(120, .12, seed=8, scale=4)
    # the hole: a sunken, roughly body-sized pit pressed into deep snow
    snow = kit.mat_pbr('snow', 'pitsnow')
    pit = add('primitive_uv_sphere_add', kit.mat_principled('pitshadow', (.35, .42, .55), rough=.9), (0, 4, -.05), (1.1, .6, .35), segments=48, ring_count=24, sub=1)
    rim = add('primitive_torus_add', snow, (0, 4, .05), (1.15, .7, .6), major_radius=1, minor_radius=.25, sub=2)
    dm = rim.modifiers.new('d', 'DISPLACE'); tx = bpy.data.textures.new('rimn', 'CLOUDS'); tx.noise_scale = .2; dm.texture = tx; dm.strength = .2
    for x, y, s in ((-1.6, 5.5, .55), (1.8, 6.0, .6), (-3.0, 9, .9), (2.8, 11, 1.0), (.4, 13, 1.1), (-5, 14, 1.2), (5.5, 15, 1.2)):
        ob = bpy.data.objects.new('p', None); ob.instance_type = 'COLLECTION'; ob.instance_collection = pine_proto(); ob.scale = (s, s, s); ob.location = (x, y, 0); kit.link(ob)
    forest(200, ((-30, 30), (16, 60)), scale=(.9, 1.5), seed=5)
    for k in range(9):   # snapped branch bits on the snow
        add('primitive_cylinder_add', kit.mat_pbr('bark', 'twig'), (random.uniform(-1.6, 1.6), random.uniform(2.6, 5.6), .08), (.03, .03, random.uniform(.2, .5)),
            rot=(math.radians(90), 0, random.uniform(0, 3)), vertices=8, sub=0)
    point((6, 30, 4), 20000, (1, .45, .15), 3)
    cam, _ = kit.camera((0, -.8, 2.6), (0, 4.6, -.2), lens=24)

elif name == 'wreck':
    kit.sky(sun_elevation=1.5, sun_rotation=250, strength=.3, dust=1.2, sun_lamp_energy=1.2)
    kit.sun_lamp((.4, .3, .6), .6, (.55, .7, 1.0))                     # cool skylight fill
    ter = snow_ground(300, 1.2, seed=12, scale=1.6); TH = math.radians(10); ter.rotation_euler = (TH, 0, 0)
    z_of = lambda x, y: math.sin(TH) * y
    # tail section of a twin-jet airliner (DC-9 layout: T-tail, two engines on the rear fuselage); unbranded
    root = kit.link(bpy.data.objects.new('tail', None))
    white = kit.mat_principled('fus', (.7, .72, .75), rough=.4, metal=.2); stripe = kit.mat_principled('stripe', (.05, .12, .35), rough=.4)
    dark = kit.mat_principled('inside', (.02, .02, .025), rough=.9); win = kit.mat_principled('win', (.05, .07, .1), rough=.1)
    add('primitive_cylinder_add', white, (0, 0, 0), (1.6, 1.6, 4.5), rot=(math.radians(90), 0, 0), vertices=48, parent=root, end_fill_type='NOTHING')
    add('primitive_cylinder_add', dark, (0, .3, 0), (1.5, 1.5, 4.3), rot=(math.radians(90), 0, 0), vertices=48, parent=root)          # dark cabin inside the torn-open end
    for k in range(10):   # jagged torn metal around the open end
        a_ = k / 10 * 2 * math.pi; add('primitive_cone_add', white, (1.55 * math.cos(a_), -4.6 - .25 * (k % 3), 1.55 * math.sin(a_)), (.25, .25, .5 + .2 * (k % 2)),
                                        rot=(math.radians(90), 0, 0), vertices=4, sub=0, parent=root)
    add('primitive_cone_add', white, (0, 6.0, .35), (1.55, 1.55, 3.0), rot=(math.radians(-90), 0, 0), vertices=48, parent=root)
    add('primitive_cube_add', white, (0, 6.8, 3.6), (.18, 1.9, 2.9), rot=(math.radians(-28), 0, 0), bevel=.1, parent=root)          # tall swept fin
    add('primitive_cube_add', white, (0, 8.3, 6.2), (3.8, .9, .12), bevel=.08, parent=root)                                         # T-tail stabilizer on top
    for sx in (-2.3, 2.3):
        add('primitive_cylinder_add', white, (sx, 3.6, .9), (.6, .6, 1.9), rot=(math.radians(90), 0, 0), vertices=32, parent=root)   # rear-mounted engines
        add('primitive_cube_add', white, (sx * .7, 3.6, .9), (.6, .4, .1), parent=root)
    for k in range(7):
        for sx in (-1.58, 1.58): add('primitive_cube_add', win, (sx, -3.6 + k * .9, .55), (.02, .16, .22), sub=0, parent=root)
    for sx in (-1.62, 1.62): add('primitive_cube_add', stripe, (sx, -.5, .1), (.02, 4.0, .12), sub=0, parent=root)
    root.location = (0, 20, z_of(0, 20) + 1.0); root.rotation_euler = (math.radians(-6), math.radians(-10), math.radians(118))
    forest(300, ((-60, 60), (32, 120)), z_of=z_of, scale=(.8, 1.4), seed=9)
    forest(40, ((12, 50), (-5, 32)), z_of=z_of, scale=(.8, 1.3), seed=4); forest(30, ((-50, -14), (0, 32)), z_of=z_of, scale=(.8, 1.3), seed=6)
    cam, _ = kit.camera((-12, -7, z_of(0, -7) + 5.0), (-3.5, 20, z_of(0, 20) + 2.6), lens=34)

elif name == 'europe':
    R = 10.0; FL = 11.0
    kit.world(strength=.12)
    a = kit.latlon(51.15, 8.40, R, FL, 0); b = kit.latlon(50.82, 14.35, R, FL, 0); tgt = (a + b) / 2; n = tgt.normalized()
    north = (kit.latlon(52.5, 11.4, R, FL, 0) - tgt).normalized()
    sun = (n * .7 + north.cross(n) * .6 + north * .3).normalized()     # afternoon light from the west-southwest
    root, spin = kit.earth(R, tuple(sun), tilt_deg=0, face_lon=FL, clouds=True, atmo=True)
    kit.sun_lamp(tuple(sun), 4.0)
    cam, _ = kit.camera(tuple(tgt + n * 7.0 - north * 3.0), tuple(tgt + north * .3), lens=30)
    from bpy_extras.object_utils import world_to_camera_view
    bpy.context.view_layer.update()
    va, vb = world_to_camera_view(sc, cam, a), world_to_camera_view(sc, cam, b)
    open(f'{OUT}/{name}.txt', 'w').write(f'{va.x} {1 - va.y} {vb.x} {1 - vb.y}')

sc.render.filepath = f'{OUT}/{name}.png'; bpy.ops.render.render(write_still=True); print('ok', name)
