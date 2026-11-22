"""WYR deepest ocean vs edge of space: one high-res Cycles still per plate (animated in 2D by wyr_anim.py).
blender-less: python3 wyr_plate.py <plate> [res_scale]  -> wyr/plates/<plate>.png
plates: floor (sub lighting the trench floor), sink (sub sinking in dark water), surface (Pacific surface),
        limb (Earth's curve from 100 km), capsule (Freedom 7 suborbital capsule at the edge of space), astro (astronaut floating)"""
import sys, math, os
sys.path.insert(0, '/home/claude/b3d')
import bpy, kit
from mathutils import Vector
name = sys.argv[1]; S = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
OUT = '/home/claude/b3d/wyr/plates'; os.makedirs(OUT, exist_ok=True)
W, H = int(1080 * S), int(1920 * S)
sc = kit.reset(res=(W, H), samples=int(os.environ.get('SAMPLES', 40)))
sc.cycles.adaptive_threshold = 0.03; sc.cycles.max_bounces = 4

def dark_world(col=(0.0, 0.004, 0.008), strength=1.0):
    w = bpy.data.worlds.new('deep'); sc.world = w; nt, N, L = kit.nodes(w)
    o = N.new('ShaderNodeOutputWorld'); bg = N.new('ShaderNodeBackground'); bg.inputs['Color'].default_value = (*col, 1)
    bg.inputs['Strength'].default_value = strength; L.new(bg.outputs[0], o.inputs['Surface'])

def spot(loc, aim, energy, size_deg=38, blend=.6, color=(.85, .93, 1.0)):
    d = bpy.data.lights.new('spot', 'SPOT'); d.energy = energy; d.spot_size = math.radians(size_deg); d.spot_blend = blend; d.color = color
    d.shadow_soft_size = .05
    ob = kit.link(bpy.data.objects.new('spot', d)); ob.location = loc
    ob.rotation_euler = (Vector(aim) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler(); return ob

def submersible(loc=(0, 0, 0), rot_z=0.0, lights_on=True, energy=900):
    """generic deep-diving research sub (no real brand): pressure hull sphere inside a white syntactic-foam body,
    orange trim, thrusters, front lamps and a viewport"""
    root = kit.link(bpy.data.objects.new('sub', None)); root.location = loc; root.rotation_euler = (0, 0, rot_z)
    white = kit.mat_principled('subwhite', (.86, .87, .84), rough=.42, coat=.2)
    orange = kit.mat_principled('suborange', (.95, .38, .05), rough=.38)
    metal = kit.mat_principled('submetal', (.55, .56, .58), rough=.3, metal=1)
    glass = kit.mat_principled('subglass', (.02, .04, .05), rough=.03, coat=1)
    dark = kit.mat_principled('subdark', (.04, .04, .045), rough=.5)
    def add(prim, mat, loc_, scale, rot=(0, 0, 0), bevel=0.0, sub=2, **kw):
        getattr(bpy.ops.mesh, prim)(**kw); ob = bpy.context.object; ob.location = loc_; ob.scale = scale; ob.rotation_euler = rot
        ob.data.materials.append(mat); kit.smooth(ob, sub, bevel); ob.parent = root; return ob
    add('primitive_uv_sphere_add', white, (0, 0, .05), (1.65, .62, .62), segments=64, ring_count=32, sub=1)   # foam body (Alvin-like hull)
    add('primitive_cube_add', orange, (-.1, 0, .62), (.9, .22, .05), bevel=.04, sub=1)              # orange top deck
    add('primitive_cube_add', white, (-.3, 0, .82), (.38, .09, .18), bevel=.06, sub=2)             # vertical fin / mast
    add('primitive_cube_add', orange, (-.3, 0, 1.0), (.38, .1, .02), bevel=.01, sub=1)
    add('primitive_uv_sphere_add', metal, (1.35, 0, -.05), (.42, .42, .42), segments=48, ring_count=24, sub=1)   # titanium crew sphere nose
    for y in (-.2, .2):
        add('primitive_uv_sphere_add', glass, (1.72, y, -.02), (.08, .08, .08), segments=32, ring_count=16, sub=1)   # viewports
    add('primitive_cube_add', dark, (0, 0, -.66), (1.1, .42, .05), bevel=.03, sub=1)               # skids
    for x, y, z in ((-1.5, .32, .1), (-1.5, -.32, .1), (-1.6, 0, -.25)):
        add('primitive_cylinder_add', dark, (x, y, z), (.14, .14, .12), rot=(0, math.pi / 2, 0), vertices=32, sub=1)
        add('primitive_torus_add', orange, (x, y, z), (.15, .15, .15), rot=(0, math.pi / 2, 0), major_radius=1, minor_radius=.12, sub=1)
    lamps = []
    for y in (-.48, .48):
        add('primitive_cube_add', metal, (1.2, y * .9, .42), (.18, .05, .05), bevel=.01, sub=1)
        lp = add('primitive_cylinder_add', kit.mat_emit('lamp', (.9, .95, 1), 60 if lights_on else 0), (1.36, y * .9, .42), (.07, .07, .04), rot=(0, math.pi / 2, 0), vertices=24, sub=0)
        lamps.append(lp)
    bpy.context.view_layer.update()
    spots = []
    if lights_on:
        for y in (-.48, .48):
            p = root.matrix_world @ Vector((1.46, y * .9, .42)); a = root.matrix_world @ Vector((6, y * 2.2, -2.2))
            spots.append(spot(tuple(p), tuple(a), energy))
    return root, spots

if name in ('floor', 'sink'):
    dark_world((0.0, .006, .012) if name == 'floor' else (0.0, .018, .04), 1.0)
    if name == 'floor':
        ter = kit.terrain(size=40, height=.9, scale=2.0, kind='mud', seed=4, res=7); ter.location = (4, 0, -1.55)
        for k, (x, y, s) in enumerate(((6, -2.5, .9), (9, 3, 1.4), (4.5, 2.2, .5), (12, -4, 2.0), (7.5, .6, .35))):   # scattered sediment-covered rocks
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=4); r = bpy.context.object; r.location = (x, y, -1.5); r.scale = (s, s * .8, s * .45)
            d = r.modifiers.new('d', 'DISPLACE'); t = bpy.data.textures.new(f'rk{k}', 'CLOUDS'); t.noise_scale = .5; d.texture = t; d.strength = .35 * s
            r.data.materials.append(ter.data.materials[0])
        sub, spots = submersible((0, 0, -.2), rot_z=math.radians(-12), energy=1100)
        cam, _ = kit.camera((5.2, -6.0, .5), (1.2, .3, -.8), lens=30)
        fill = bpy.data.lights.new('fill', 'AREA'); fill.energy = 40; fill.size = 4; fill.color = (.4, .6, 1)
        fo = kit.link(bpy.data.objects.new('fill', fill)); fo.location = (-3, -3, 4); fo.rotation_euler = (math.radians(35), 0, math.radians(-30))
    else:
        sub, spots = submersible((0, 0, 0), rot_z=math.radians(25), energy=700)
        sub.rotation_euler = (math.radians(4), math.radians(14), math.radians(25))   # nose down a little: descending
        cam, _ = kit.camera((3.8, -5.6, 3.2), (.2, 0, -.3), lens=34)
        top = bpy.data.lights.new('top', 'AREA'); top.energy = 160; top.size = 8; top.color = (.35, .65, 1)   # last faint light from far above
        to = kit.link(bpy.data.objects.new('top', top)); to.location = (0, 0, 9)
    # thin water volume so the lamp beams show (slow-ish but it's one still)
    bpy.ops.mesh.primitive_cube_add(size=30); vol = bpy.context.object; vol.location = (4, 0, 2)
    m = bpy.data.materials.new('water_vol'); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); v = N.new('ShaderNodeVolumePrincipled')
    v.inputs['Color'].default_value = (.55, .8, 1, 1); v.inputs['Density'].default_value = .035 if name == 'floor' else .025
    v.inputs['Absorption Color'].default_value = (.15, .45, .6, 1); L.new(v.outputs[0], o.inputs['Volume']); vol.data.materials.append(m)
    sc.cycles.volume_step_rate = 4.0; sc.cycles.volume_bounces = 0

elif name == 'pacific':
    R = 10.0; FL = 145.0
    kit.world(strength=.12)
    tgt = kit.latlon(11.35, 142.2, R, FL, 0); n = tgt.normalized()
    north = (kit.latlon(12.35, 142.2, R, FL, 0) - tgt).normalized(); side = n.cross(north)
    sun = (n * .8 + side * .5 + north * .3).normalized(); kit.sun_lamp(tuple(sun), 4.2)
    root, spin = kit.earth(R, tuple(sun), tilt_deg=0, face_lon=FL, clouds=True, atmo=True)
    cam, _ = kit.camera(tuple(tgt + n * 4.2 - north * 2.2), tuple(tgt + north * .4), lens=30)
    from bpy_extras.object_utils import world_to_camera_view
    bpy.context.view_layer.update(); v = world_to_camera_view(sc, cam, tgt)
    open(f'{OUT}/pacific.txt', 'w').write(f'{v.x} {1 - v.y}')

elif name == 'surface':
    kit.sky(sun_elevation=24, sun_rotation=150, strength=.16, sun_lamp_energy=4.5)
    oc = kit.ocean(size=80, wave_scale=1.6, wind=11, choppy=1.3); oc.scale = (60, 60, 1)
    cam, _ = kit.camera((0, -10, 2.2), (0, 30, -.4), lens=26)

elif name == 'limb':
    R = 10.0; FL = 145.0   # face the western Pacific (Mariana region)
    kit.world(strength=.08)
    h = .157   # 100 km, in units where Earth's radius = 10
    base = kit.latlon(12.0, 143.0, R, FL, h)
    n = base.normalized(); fwd = (kit.latlon(14.5, 143.0, R, FL, 0) - kit.latlon(12.0, 143.0, R, FL, 0)).normalized()
    fwd = (fwd - n * fwd.dot(n)).normalized(); side = n.cross(fwd)
    sun = (n * .55 + fwd * .55 + side * .6).normalized(); kit.sun_lamp(tuple(sun), 4.5)
    root, spin = kit.earth(R, tuple(sun), tilt_deg=0, face_lon=FL, clouds=True, atmo=True)
    a = bpy.data.objects['atmo']; s_ = 1.0115 / 1.035; a.scale = (s_, s_, s_)   # glow shell at ~75 km so the 100 km camera sits above it
    cam, _ = kit.camera(tuple(base), tuple(base + fwd * 3.0 - n * float(os.environ.get('DIP', .2))), lens=18)
    cam.data.clip_start = .0005; cam.data.clip_end = 100

elif name in ('capsule', 'astro'):   # real NASA model on a transparent film, composited over the limb plate in 2D
    sc.render.film_transparent = True
    kit.world(strength=.05)
    kit.sun_lamp((.9, -.25, .38), 4.5)
    bl = bpy.data.lights.new('earthshine', 'AREA'); bl.energy = 300; bl.size = 10; bl.color = (.35, .6, 1)
    bo = kit.link(bpy.data.objects.new('es', bl)); bo.location = (0, 0, -8)
    obj = kit.nasa_model('Redstone 3 (Freedom 7)' if name == 'capsule' else 'Astronaut', size=3.0, align='Z')
    if name == 'capsule':
        obj.rotation_euler = (math.radians(-28), math.radians(10), 0)
        shingle = kit.mat_principled('beryllium_shingles', (.16, .17, .18), rough=.42, metal=.7)   # Mercury capsules wore dark shingles
        for o in obj.children_recursive:
            if o.type == 'MESH':
                o.data.materials.clear(); o.data.materials.append(shingle)
    else: obj.rotation_euler = (math.radians(-65), math.radians(20), math.radians(30))
    cam, _ = kit.camera((0, -9, 1.0), (0, 0, 0), lens=50)

sc.render.filepath = f'{OUT}/{name}.png'; bpy.ops.render.render(write_still=True); print('ok', name)
