"""3D Short (would-you-rather): a day on the Moon or a day on Mars?  Usage: python3 moonmars3d.py <scene> still|anim [frac]"""
import sys, math, json, os, random
sys.path.insert(0, '/home/claude/b3d')
import bpy, kit
from mathutils import Vector

CFG = json.load(open('/home/claude/b3d/moonmars/topic.json'))
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
rng = random.Random(idx + 11)
CH = {'type': 'choice', 'a': 'A day on the Moon', 'b': 'A day on Mars', 'pos': [.5, .1]}
LBL_Y = .68                                            # on surface shots labels sit low, above the captions, clear of the astronaut

def label(text, y=LBL_Y, color=(255, 222, 40)):
    overlays.append({'type': 'label', 'text': text, 'pos': (.5, y), 'color': color})

# ------------------------------------------------------------------ skies
def mars_sky(sun_dir, sunset=True, strength=1.0):
    """Mars sky: butterscotch dust by day; at sunset a dark brown sky with a BLUE glow around the Sun
    (fine dust forward-scatters blue light near the Sun's direction, as Curiosity photographed in 2015)."""
    w = bpy.data.worlds.new('marsky'); sc.world = w; nt, N, L = kit.nodes(w)
    out = N.new('ShaderNodeOutputWorld'); bg = N.new('ShaderNodeBackground'); tc = N.new('ShaderNodeTexCoord')
    nv = N.new('ShaderNodeVectorMath'); nv.operation = 'NORMALIZE'; L.new(tc.outputs['Generated'], nv.inputs[0])
    S = Vector(sun_dir).normalized()
    dt = N.new('ShaderNodeVectorMath'); dt.operation = 'DOT_PRODUCT'; dt.inputs[1].default_value = tuple(S); L.new(nv.outputs[0], dt.inputs[0])
    mx0 = N.new('ShaderNodeMath'); mx0.operation = 'MAXIMUM'; mx0.inputs[1].default_value = 0; L.new(dt.outputs['Value'], mx0.inputs[0])
    def pw(k):
        p = N.new('ShaderNodeMath'); p.operation = 'POWER'; p.inputs[1].default_value = k; L.new(mx0.outputs[0], p.inputs[0]); return p
    sep = N.new('ShaderNodeSeparateXYZ'); L.new(nv.outputs[0], sep.inputs[0])
    az = N.new('ShaderNodeMath'); az.operation = 'ABSOLUTE'; L.new(sep.outputs['Z'], az.inputs[0])
    hz = N.new('ShaderNodeMapRange'); hz.inputs['From Min'].default_value = 0; hz.inputs['From Max'].default_value = .5
    hz.inputs['To Min'].default_value = 1; hz.inputs['To Max'].default_value = 0; L.new(az.outputs[0], hz.inputs['Value'])
    if sunset:
        base_hi, base_lo, glow, gk, glow2, gk2 = (.012, .008, .007), (.07, .035, .02), (.10, .22, .7), 70, (.45, .65, 1.3), 500
    else:
        base_hi, base_lo, glow, gk, glow2, gk2 = (.26, .16, .09), (.55, .38, .24), (.25, .25, .27), 12, (.5, .52, .55), 200
    mix = N.new('ShaderNodeMix'); mix.data_type = 'RGBA'; L.new(hz.outputs[0], mix.inputs['Factor'])
    mix.inputs['A'].default_value = (*base_hi, 1); mix.inputs['B'].default_value = (*base_lo, 1)
    acc = mix.outputs['Result']
    for col, k in ((glow, gk), (glow2, gk2)):
        p = pw(k); m = N.new('ShaderNodeMix'); m.data_type = 'RGBA'; m.blend_type = 'ADD'; m.inputs['Factor'].default_value = 1
        sc_ = N.new('ShaderNodeVectorMath'); sc_.operation = 'SCALE'; sc_.inputs[0].default_value = col; L.new(p.outputs[0], sc_.inputs['Scale'])
        L.new(acc, m.inputs['A']); L.new(sc_.outputs[0], m.inputs['B']); acc = m.outputs['Result']
    disc = pw(6000); dm = N.new('ShaderNodeMath'); dm.operation = 'MULTIPLY'; dm.inputs[1].default_value = 40; L.new(disc.outputs[0], dm.inputs[0])
    m = N.new('ShaderNodeMix'); m.data_type = 'RGBA'; m.blend_type = 'ADD'; m.inputs['Factor'].default_value = 1
    sc2 = N.new('ShaderNodeVectorMath'); sc2.operation = 'SCALE'; sc2.inputs[0].default_value = (1, .97, .92); L.new(dm.outputs[0], sc2.inputs['Scale'])
    L.new(acc, m.inputs['A']); L.new(sc2.outputs[0], m.inputs['B'])
    L.new(m.outputs['Result'], bg.inputs['Color']); bg.inputs['Strength'].default_value = strength; L.new(bg.outputs[0], out.inputs['Surface'])

def space_black(strength=.035):
    kit.world(strength=strength)          # real star map, very dim: in daylight the lunar sky is black

# ------------------------------------------------------------------ ground
def recolor(ob, lo, hi, rough=.92, bump=.9):
    m = ob.active_material; nt = m.node_tree
    for n in nt.nodes:
        if n.type == 'VALTORGB': n.color_ramp.elements[0].color = (*lo, 1); n.color_ramp.elements[1].color = (*hi, 1)
        if n.type == 'BUMP': n.inputs['Strength'].default_value = bump
        if n.type == 'BSDF_PRINCIPLED': n.inputs['Roughness'].default_value = rough

def craters(n, area, rmin, rmax, mat):
    """shallow bowl craters with raised rims, scattered on the regolith"""
    for i in range(n):
        r = rng.uniform(rmin, rmax); x, y = rng.uniform(-area, area), rng.uniform(-area * .2, area)
        bpy.ops.mesh.primitive_torus_add(major_radius=r, minor_radius=r * .22, major_segments=64, minor_segments=12, location=(x, y, 0))
        t = bpy.context.object; t.location.z = ground_z(x, y) - .02; t.scale = (1, 1, .28); t.data.materials.append(mat); kit.smooth(t, 1)

def rocks(n, area, smin, smax, mat, center=(0, 0)):
    for i in range(n):
        s = rng.uniform(smin, smax)
        x, y = center[0] + rng.uniform(-area, area), center[1] + rng.uniform(-area * .3, area); z = ground_z(x, y) - s * .3
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=s, location=(x, y, z))
        o = bpy.context.object; o.scale = (rng.uniform(.8, 1.4), rng.uniform(.8, 1.3), rng.uniform(.5, .8)); o.rotation_euler = (0, 0, rng.random() * 6)
        dm = o.modifiers.new('d', 'DISPLACE'); tx = bpy.data.textures.new('rk', 'CLOUDS'); tx.noise_scale = s * .6; dm.texture = tx; dm.strength = s * .35
        o.data.materials.append(mat); kit.smooth(o, 0)

def regolith_mat(name, lo, hi, rough=.93):
    m = bpy.data.materials.new(name); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled'); tc = N.new('ShaderNodeTexCoord')
    n1 = kit._noise(N, L, tc.outputs['Object'], .35, 12, .62); n2 = kit._noise(N, L, tc.outputs['Object'], 9.0, 10, .6); n3 = kit._noise(N, L, tc.outputs['Object'], 60.0, 6, .55)
    mx = N.new('ShaderNodeMix'); mx.inputs['Factor'].default_value = .35; L.new(n1.outputs['Fac'], mx.inputs['A']); L.new(n2.outputs['Fac'], mx.inputs['B'])
    cr = N.new('ShaderNodeValToRGB'); cr.color_ramp.elements[0].position = .3; cr.color_ramp.elements[1].position = .7
    cr.color_ramp.elements[0].color = (*lo, 1); cr.color_ramp.elements[1].color = (*hi, 1)
    L.new(mx.outputs['Result'], cr.inputs['Fac']); L.new(cr.outputs['Color'], bs.inputs['Base Color']); bs.inputs['Roughness'].default_value = rough
    bs.inputs['Specular IOR Level'].default_value = .15
    bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = .7; bp.inputs['Distance'].default_value = .02
    L.new(n3.outputs['Fac'], bp.inputs['Height']); L.new(bp.outputs['Normal'], bs.inputs['Normal'])
    L.new(bs.outputs[0], o.inputs[0]); return m

def ground(kind):
    """gently rolling regolith plain (metres): broad undulation + small-scale lumps, real-photo colours"""
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=260, y_subdivisions=260, size=140); t = bpy.context.object; t.name = 'ground'
    for nm, ns, st in (('big', 14.0, 1.6), ('mid', 2.5, .25), ('fine', .5, .05)):
        tx = bpy.data.textures.new(nm, 'CLOUDS'); tx.noise_scale = ns; tx.noise_depth = 4
        dm = t.modifiers.new(nm, 'DISPLACE'); dm.texture = tx; dm.strength = st; dm.mid_level = .5; dm.texture_coords = 'LOCAL'
    if kind == 'moon':
        m = regolith_mat('moonsoil', (.11, .11, .105), (.34, .335, .32), .95)       # grey lunar regolith (Apollo photos)
        rm = kit.mat_pbr('rock', 'moonrock'); rm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (.2, .195, .19, 1)
        t.data.materials.append(m); kit.smooth(t, 0); t.location.z = -ground_z_raw(t)
        craters(8, 24, 1.0, 4.0, m); rocks(30, 16, .05, .35, rm)
    else:
        m = regolith_mat('marssoil', (.26, .10, .04), (.58, .29, .14), .92)         # rust-orange Martian regolith (Curiosity/Perseverance photos)
        rm = kit.mat_pbr('rock', 'marsrock'); rm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (.17, .085, .05, 1)
        t.data.materials.append(m); kit.smooth(t, 0); t.location.z = -ground_z_raw(t)
        rocks(40, 16, .05, .4, rm)
    return t

def ground_z_raw(t):
    dg = bpy.context.evaluated_depsgraph_get(); bpy.context.view_layer.update()
    hit, loc, *_ = sc.ray_cast(dg, Vector((0, 0, 50)), Vector((0, 0, -1)))
    return loc.z if hit else 0.0

def ground_z(x, y):
    dg = bpy.context.evaluated_depsgraph_get(); bpy.context.view_layer.update()
    hit, loc, *_ = sc.ray_cast(dg, Vector((x, y, 50)), Vector((0, 0, -1)))
    return loc.z if hit else 0.0

def astro_at(x, y, yaw=0.0):
    z = ground_z(x, y)
    root, limbs = kit.scale_ref(1.8, (x, y, 0)); bpy.context.view_layer.update()
    lo = min((root.matrix_world.inverted() @ (o.matrix_world @ Vector(c))).z for o in root.children_recursive if o.type == 'MESH' for c in o.bound_box)
    base = z - lo * root.scale.z; root.location = (x, y, base); root.rotation_euler = (0, 0, yaw)
    return root, limbs, base

def sun_disc(direction, dist=400, ang_deg=.35, strength=60, color=(1, .97, .92)):
    d = Vector(direction).normalized(); r = dist * math.tan(math.radians(ang_deg))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=tuple(d * dist)); s = bpy.context.object
    s.data.materials.append(kit.mat_emit('sundisc', color, strength))
    for a in ('visible_shadow', 'visible_diffuse', 'visible_glossy'): setattr(s, a, False)
    return s

def sundir(elev, az):
    el, a = math.radians(elev), math.radians(az)
    return (math.sin(a) * math.cos(el), math.cos(a) * math.cos(el), math.sin(el))

# ------------------------------------------------------------------ sets
SUNSET_DIR = sundir(2.5, 8)
HOOK_CAM = ((.9, -5.2, 1.05), (.7, -4.3, 1.0))        # s0 start/end; s10 ends on HOOK_CAM[0] for the loop
def sunset_set():
    mars_sky(SUNSET_DIR, sunset=True, strength=1.0)
    kit.sun_lamp(SUNSET_DIR, 1.6, (.75, .8, 1))
    ground('mars')
    sun_disc(SUNSET_DIR, ang_deg=.23, strength=30)     # the Sun looks ~2/3 as wide from Mars
    a, limbs, base = astro_at(-.5, 4.2, math.radians(170))
    cam, tgt = kit.camera(HOOK_CAM[0], (2.2, 30, 2.4), lens=26)
    return cam, tgt, a

def globes(mars_x=.95, moon_x=-1.3, z=-.6, sun=(1, -.55, .35)):
    kit.world(strength=.5); kit.sun_lamp(sun, 4.5)
    # true relative size: Moon radius 1,737 km vs Mars 3,390 km (0.51x)
    mr, ms, mm = kit.planet('mars', 1.0, 25.2, face_lon=-60)
    mr.location = (mars_x, 0, z)
    lr = kit.moon(.512, face_lon=0); lr.location = (moon_x, 0, z)
    return mr, ms, lr

# ======================================================================= scenes
def s0_hook():                  # "One of them has blue sunsets."
    cam, tgt, a = sunset_set()
    kit.key(cam, 1, location=HOOK_CAM[0]); kit.key(cam, NF, location=HOOK_CAM[1])
    overlays.append({'type': 'hook', 'text': 'ONE HAS BLUE SUNSETS', 'pos': [.5, .11]})

def s1_question():              # "Would you rather spend a day on the Moon, or a day on Mars?"
    mr, ms, lr = globes()
    kit.key(ms, 1, rotation_euler=(0, 0, 0)); kit.key(ms, NF, rotation_euler=(0, 0, math.radians(10)))
    cam, _ = kit.camera((0, -9.2, .2), (0, 0, -.35), lens=46)
    kit.key(cam, 1, location=(-.3, -9.8, .3)); kit.key(cam, NF, location=(.2, -9.0, .1))
    overlays.append(CH); label('TRUE RELATIVE SIZE', .27, (200, 215, 235))

def s2_comment():               # "Comment A or B. Take a second, and think about it."
    mr, ms, lr = globes(1.55, -1.55, -1.35)
    kit.key(ms, 1, rotation_euler=(0, 0, math.radians(10))); kit.key(ms, NF, rotation_euler=(0, 0, math.radians(18)))
    cam, _ = kit.camera((0, -9.6, .2), (0, 0, -.45), lens=44)
    kit.key(cam, 1, location=(0, -9.8, .25)); kit.key(cam, NF, location=(0, -9.3, .15))
    overlays.extend([CH, {'type': 'prompt', 'text': 'Comment A or B', 'pos': [.5, .42]}, {'type': 'countdown', 'secs': 3, 'pos': [.5, .55]}])

def s3_weight():                # "On the Moon, you'd weigh about one sixth..."
    SD = sundir(14, 120); space_black(); kit.sun_lamp(SD, 5.0)
    ground('moon')
    a, limbs, base = astro_at(0, 2, math.radians(-30))
    # slow, high lunar hop: same push as on Earth goes ~6x higher and hangs in the air (h = v^2 / 2g)
    t0, t1 = .3, D + .3; peak = 1.1
    for f in range(1, NF + 1, 2):
        s = (f - 1) / FPS - .35; u = min(max((s - t0) / (t1 - t0), 0), 1)
        kit.key(a, f, location=(0, 2, base + peak * 4 * u * (1 - u)))
    for side in (-1, 1):
        kit.key(limbs[f'arm{side}'], 1, rotation_euler=(0, -side * math.radians(32), 0)); kit.key(limbs[f'arm{side}'], NF, rotation_euler=(0, -side * math.radians(70), 0))
    cam, _ = kit.camera((3.6, -5.6, 1.0), (0, 2, 2.0), lens=28)
    kit.key(cam, 1, location=(3.8, -5.9, 1.0)); kit.key(cam, NF, location=(3.3, -5.2, 1.1))
    overlays.append(CH); label('≈ 1/6 OF EARTH\'S GRAVITY')

def s4_twoweeks():              # "But the Sun stays up for about two weeks, in a pitch black sky."
    SD = sundir(6, 45); space_black(); kit.sun_lamp(SD, 5.0)
    sun_disc(SD, ang_deg=.27, strength=80)
    ground('moon')
    a, limbs, base = astro_at(-.6, 4, math.radians(200))
    cam, _ = kit.camera((-1.5, -4.0, 1.0), (1.0, 30, 2.2), lens=24)
    kit.key(cam, 1, location=(-1.8, -4.4, 1.0)); kit.key(cam, NF, location=(-1.2, -3.6, 1.0))
    overlays.append(CH); label('DAYLIGHT LASTS ≈ 2 WEEKS')

def s5_hot():                   # "And in that sunlight, the ground can reach about 250 degrees Fahrenheit."
    SD = sundir(62, 150); space_black(); kit.sun_lamp(SD, 6.0)
    ground('moon')
    a, limbs, base = astro_at(.4, 1.2, math.radians(-20))
    cam, _ = kit.camera((-2.6, -4.4, .5), (.4, 1.2, 1.3), lens=28)
    kit.key(cam, 1, location=(-2.8, -4.7, .45)); kit.key(cam, NF, location=(-2.4, -4.1, .55))
    overlays.append(CH); label('UP TO ≈ 250°F (121°C)', color=(255, 140, 60))

def s6_sol():                   # "On Mars, one day lasts about 24 hours and 40 minutes. Almost like home."
    kit.world(strength=.5); kit.sun_lamp((1, -.6, .2), 4.5)
    mr, ms, mm = kit.planet('mars', 1.6, 25.2, face_lon=-40)
    kit.key(ms, 1, rotation_euler=(0, 0, 0)); kit.key(ms, NF, rotation_euler=(0, 0, math.radians(40)))
    cam, _ = kit.camera((0, -7.6, .9), (0, 0, .25), lens=38)
    kit.key(cam, 1, location=(-.3, -8.0, 1.0)); kit.key(cam, NF, location=(.2, -7.2, .8))
    overlays.append(CH); label('1 SOL ≈ 24 H 40 MIN', .28); label('ROTATION SPED UP', .325, (200, 215, 235))

def s7_air():                   # "You'd weigh about 38 percent... thin air is mostly carbon dioxide."
    SD = sundir(40, 140); mars_sky(SD, sunset=False, strength=1.0); kit.sun_lamp(SD, 3.4, (1, .93, .85))
    ground('mars'); sun_disc(SD, ang_deg=.23, strength=40)
    a, limbs, base = astro_at(0, 2.2, math.radians(-35))
    for side in (-1, 1):
        kit.key(limbs[f'leg{side}'], 1, rotation_euler=(side * math.radians(10), -side * math.radians(7), 0))
        kit.key(limbs[f'leg{side}'], NF, rotation_euler=(-side * math.radians(10), -side * math.radians(7), 0))
    cam, _ = kit.camera((3.2, -4.4, 1.1), (0, 2.6, 1.9), lens=28)
    kit.key(cam, 1, location=(3.5, -4.7, 1.0)); kit.key(cam, NF, location=(2.9, -4.1, 1.2))
    overlays.append(CH); label('≈ 38% OF EARTH\'S GRAVITY', .225); label('AIR ≈ 95% CO2, <1% PRESSURE', .262, (255, 255, 255))

def s8_cold():                  # "And on average, it's around minus 80 degrees Fahrenheit."
    SD = sundir(12, 40); mars_sky(SD, sunset=False, strength=.6); kit.sun_lamp(SD, 2.2, (.95, .92, .9))
    t = ground('mars')
    a, limbs, base = astro_at(1.0, 5, math.radians(160))
    cam, _ = kit.camera((-2.2, -2.5, 1.6), (1.0, 8, 1.3), lens=26)
    kit.key(cam, 1, location=(-2.4, -2.9, 1.7)); kit.key(cam, NF, location=(-1.9, -2.1, 1.5))
    overlays.append(CH); label('AVERAGE ≈ −80°F (−60°C)', color=(150, 205, 255))

def s9_verdict():               # "You'd need a spacesuit on both, but Mars gives you a much more Earth-like day."
    mr, ms, lr = globes()
    kit.key(ms, 1, rotation_euler=(0, 0, math.radians(18))); kit.key(ms, NF, rotation_euler=(0, 0, math.radians(26)))
    cam, tgt = kit.camera((0, -9.2, .2), (0, 0, -.35), lens=46)
    kit.key(cam, 1, location=(-.2, -9.4, .2)); kit.key(cam, NF, location=(.5, -7.6, 0))
    kit.key(tgt, 1, location=(0, 0, -.35)); kit.key(tgt, NF, location=(.9, 0, -.35))
    overlays.append(dict(CH, win='b'))

def s10_loop():                 # "And when the Sun goes down there, here's the twist." -> loops into the hook
    cam, tgt, a = sunset_set()
    kit.key(cam, 1, location=(1.6, -7.0, 1.3)); kit.key(cam, NF, location=HOOK_CAM[0])
    overlays.append({'type': 'cta', 'text': 'FOLLOW FOR MORE WOULD YOU RATHERS', 'pos': (.5, .1)})

[s0_hook, s1_question, s2_comment, s3_weight, s4_twoweeks, s5_hot, s6_sol, s7_air, s8_cold, s9_verdict, s10_loop][idx]()
os.makedirs(f'{OUT}/s{idx}', exist_ok=True)
json.dump({'frames': NF, 'overlays': overlays}, open(f'{OUT}/s{idx}/meta.json', 'w'))
if mode == 'still':
    sc.frame_set(int(NF * (float(sys.argv[3]) if len(sys.argv) > 3 else .6))); sc.render.filepath = f'{OUT}/still_{idx}.png'; bpy.ops.render.render(write_still=True)
else:
    if os.environ.get('FR'): sc.frame_start, sc.frame_end = map(int, os.environ['FR'].split(','))
    sc.render.image_settings.file_format = 'PNG'; sc.render.filepath = f'{OUT}/s{idx}/f_'; bpy.ops.render.render(animation=True)
