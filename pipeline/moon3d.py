"""3D 'What if the Moon disappeared' Short. Usage: python3 moon3d.py <scene_index> still|anim [frac]"""
import sys, math, json, os, random
sys.path.insert(0, '/home/claude/b3d')
import bpy, kit
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

CFG = json.load(open('/home/claude/b3d/moon/topic.json'))
FPS = 24; DURS = CFG['durs']; PAD = 0.75; OUT = CFG['root']
idx, mode = int(sys.argv[1]), sys.argv[2]
D = DURS[idx]; NF = int(math.ceil((D + PAD) * FPS))
sc = kit.reset(res=(648, 1152), samples=8)
sc.render.use_persistent_data = True; sc.cycles.adaptive_threshold = 0.05
sc.cycles.max_bounces = 4; sc.cycles.diffuse_bounces = 1; sc.cycles.glossy_bounces = 1; sc.cycles.transparent_max_bounces = 6
sc.frame_start, sc.frame_end = 1, NF
F = lambda sec: 1 + int(round(sec * FPS))
overlays = []
random.seed(idx + 7)

def emit_fade(name, color, strength):
    m = bpy.data.materials.new(name); nt, N, L = kit.nodes(m)
    o = N.new('ShaderNodeOutputMaterial'); e = N.new('ShaderNodeEmission'); tr = N.new('ShaderNodeBsdfTransparent'); mx = N.new('ShaderNodeMixShader')
    e.inputs['Color'].default_value = (*color, 1); e.inputs['Strength'].default_value = strength
    L.new(tr.outputs[0], mx.inputs[1]); L.new(e.outputs[0], mx.inputs[2]); L.new(mx.outputs[0], o.inputs[0]); return m, e, mx

def kf_input(sock, frame, value):
    sock.default_value = value; sock.keyframe_insert('default_value', frame=frame)

def project(cam, loc, frame):
    sc.frame_set(frame); v = world_to_camera_view(sc, cam, Vector(loc)); return (v.x, 1 - v.y)

def spin(obj, turns_per_sec=.03):
    kit.key(obj, 1, rotation_euler=(0, 0, 0)); kit.key(obj, NF, rotation_euler=(0, 0, 2 * math.pi * turns_per_sec * NF / FPS))
    if obj.animation_data and obj.animation_data.action:
        try:
            for fc in obj.animation_data.action.fcurves:
                for k in fc.keyframe_points: k.interpolation = 'LINEAR'
        except AttributeError:
            pass

def sun_disc(loc, r=1.2):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc); s = bpy.context.object
    s.data.materials.append(kit.mat_emit('sundisc', (1, .85, .55), 30)); return s

# ======================================================================= scenes
def s0_hook():
    kit.world(); kit.sun_lamp((1, -.7, .4), 4.5)
    cam, tgt = kit.camera((0, -12, .6), (0, 0, .4), lens=34)
    kit.key(cam, 1, location=(0, -12.5, .6)); kit.key(cam, NF, location=(0, -11.2, .5))
    root, sp = kit.earth(2.0, (1, -.7, .4)); root.location = (0, 0, -1.4); spin(sp, .02)
    mo = kit.moon(.55); mo.location = (1.3, -2.5, 2.5)
    tv = D * .62
    kit.key(mo, 1, scale=(1,) * 3); kit.key(mo, F(tv), scale=(1,) * 3); kit.key(mo, F(tv + .25), scale=(.001,) * 3)
    fm, fe, fmx = emit_fade('flash', (.9, .95, 1), 25)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=.6, location=mo.location); fl = bpy.context.object; fl.data.materials.append(fm)
    kit.key(fl, 1, scale=(.01,) * 3); kit.key(fl, F(tv + .1), scale=(.6,) * 3); kit.key(fl, F(tv + .9), scale=(2.2,) * 3)
    kf_input(fmx.inputs['Fac'], 1, 0); kf_input(fmx.inputs['Fac'], F(tv), 0); kf_input(fmx.inputs['Fac'], F(tv + .15), 1); kf_input(fmx.inputs['Fac'], F(tv + .9), 0)

def s1_night():
    kit.world()
    kit.sun_lamp((-.2, 1, .25), 4.0)                                   # sun behind Earth -> we see the night side
    ml = kit.sun_lamp((.4, -1, .5), .55, (.6, .7, 1)); ml.name = 'moonlight'
    ml.data.keyframe_insert('energy', frame=1); ml.data.energy = .55; ml.data.keyframe_insert('energy', frame=F(D * .3))
    ml.data.energy = 0.0; ml.data.keyframe_insert('energy', frame=F(D * .55))
    cam, tgt = kit.camera((0, -10, 1.5), (0, 0, -.2), lens=34)
    kit.key(cam, 1, location=(-.4, -10, 1.6)); kit.key(cam, NF, location=(.3, -9.3, 1.3))
    root, sp = kit.earth(2.3, (-.2, 1, .25)); root.location = (0, 0, -.6); spin(sp, .03)

def s2_tides():
    kit.world(); kit.sun_lamp((-1, -.25, .3), 4.5)
    cam, tgt = kit.camera((0, -10.5, 5.2), (0, 0, -.2), lens=32)
    kit.key(cam, 1, location=(0, -10.5, 5.2)); kit.key(cam, NF, location=(.4, -9.8, 4.8))
    root, sp = kit.earth(1.7, (-1, -.25, .3), tilt_deg=8); spin(sp, .05)
    sun_disc((-9, 2.5, 1.4), 1.3)
    gm, ge, gmx = emit_fade('bulge', (.1, .45, 1), 1.2)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.7, segments=96, ring_count=48); b = bpy.context.object; b.data.materials.append(gm); kit.smooth(b, 0)
    kf_input(gmx.inputs['Fac'], 1, .16)
    kit.key(b, 1, scale=(1.32, 1.04, 1.04)); kit.key(b, F(D * .35), scale=(1.32, 1.04, 1.04)); kit.key(b, F(D * .75), scale=(1.1, 1.03, 1.03))
    mo = kit.moon(.45); mo.location = (4.6, 0, .2)
    kit.key(mo, 1, scale=(1,) * 3); kit.key(mo, F(D * .25), scale=(1,) * 3); kit.key(mo, F(D * .35), scale=(.001,) * 3)

def coral(base, rng, mat, depth=0, length=.55, direction=Vector((0, 0, 1)), r=.07):
    end = base + direction.normalized() * length
    mid = (base + end) / 2
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=length, location=mid, vertices=10)
    c = bpy.context.object; c.rotation_euler = direction.to_track_quat('Z', 'Y').to_euler(); c.data.materials.append(mat)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r * 1.25, location=end, segments=12, ring_count=8); bpy.context.object.data.materials.append(mat)
    if depth < 3:
        for _ in range(rng.choice([2, 2, 3])):
            d = Vector((rng.uniform(-.8, .8), rng.uniform(-.8, .8), rng.uniform(.6, 1.2)))
            coral(end, rng, mat, depth + 1, length * .72, (direction.normalized() + d).normalized(), r * .75)

def fish(name, color):
    root = kit.link(bpy.data.objects.new(name, None))
    mat = kit.mat_principled(name + 'm', color, rough=.35, coat=.4)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=.25, segments=32, ring_count=16); b = bpy.context.object; b.scale = (1.4, .45, .75); b.data.materials.append(mat); kit.smooth(b, 1); b.parent = root
    bpy.ops.mesh.primitive_cone_add(radius1=.22, depth=.3, location=(-.42, 0, 0), rotation=(0, math.radians(90), 0), vertices=16)
    t = bpy.context.object; t.scale = (1, .25, 1); t.data.materials.append(mat); t.parent = root
    bpy.ops.mesh.primitive_uv_sphere_add(radius=.05, location=(.24, -.1, .06)); e = bpy.context.object; e.data.materials.append(kit.mat_principled('eye', (0, 0, 0), .1)); e.parent = root
    return root

def s3_coast():
    w = bpy.data.worlds.new('sea'); sc.world = w; w.use_nodes = True
    nt = w.node_tree; bg = nt.nodes['Background']; grad = nt.nodes.new('ShaderNodeTexGradient'); tc = nt.nodes.new('ShaderNodeTexCoord')
    mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Rotation'].default_value = (0, math.radians(-90), 0)
    nt.links.new(tc.outputs['Generated'], mp.inputs[0]); nt.links.new(mp.outputs[0], grad.inputs[0])
    ramp = nt.nodes.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].color = (.035, .24, .32, 1); ramp.color_ramp.elements[1].color = (.004, .03, .06, 1)
    nt.links.new(grad.outputs['Fac'], ramp.inputs['Fac']); nt.links.new(ramp.outputs['Color'], bg.inputs['Color'])
    kit.sun_lamp((.2, -.3, 1), 1.6, (.7, .95, 1))
    cam, tgt = kit.camera((0, -4.8, -.7), (0, .5, -1.0), lens=24)
    kit.key(cam, 1, location=(-.5, -4.8, -.7)); kit.key(cam, NF, location=(.5, -4.3, -.75))
    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, -1.6)); fl = bpy.context.object
    sand = bpy.data.materials.new('sand'); nt2, N, L = kit.nodes(sand); o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled')
    bs.inputs['Base Color'].default_value = (.42, .36, .25, 1); tcc = N.new('ShaderNodeTexCoord')
    camd = N.new('ShaderNodeCameraData'); mist = N.new('ShaderNodeMapRange'); mist.inputs['From Min'].default_value = 2.5; mist.inputs['From Max'].default_value = 9
    L.new(camd.outputs['View Distance'], mist.inputs['Value'])
    fogc = N.new('ShaderNodeEmission'); fogc.inputs['Color'].default_value = (.02, .16, .22, 1); fogc.inputs['Strength'].default_value = 1
    fmix = N.new('ShaderNodeMixShader'); L.new(mist.outputs[0], fmix.inputs['Fac']); L.new(fogc.outputs[0], fmix.inputs[2]); nz = kit._noise(N, L, tcc.outputs['Object'], 3, 6)
    bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = .6; L.new(nz.outputs['Fac'], bp.inputs['Height']); L.new(bp.outputs['Normal'], bs.inputs['Normal'])
    wv = N.new('ShaderNodeTexWave'); wv.inputs['Scale'].default_value = 2.2; wv.inputs['Distortion'].default_value = 4; L.new(tcc.outputs['Object'], wv.inputs['Vector'])
    bp2 = N.new('ShaderNodeBump'); bp2.inputs['Strength'].default_value = .35; L.new(wv.outputs['Fac'], bp2.inputs['Height']); L.new(bp.outputs['Normal'], bp2.inputs['Normal']); L.new(bp2.outputs['Normal'], bs.inputs['Normal'])
    vo = N.new('ShaderNodeTexVoronoi'); vo.voronoi_dimensions = '4D'; vo.feature = 'DISTANCE_TO_EDGE'; vo.inputs['Scale'].default_value = 1.4
    dn = kit._noise(N, L, tcc.outputs['Object'], 1.5, 3); dv = N.new('ShaderNodeVectorMath'); dv.operation = 'MULTIPLY_ADD'; dv.inputs[1].default_value = (.35, .35, .35)
    L.new(dn.outputs['Color'], dv.inputs[0]); L.new(tcc.outputs['Object'], dv.inputs[2]); L.new(dv.outputs[0], vo.inputs['Vector']); kf_input(vo.inputs['W'], 1, 0.0); kf_input(vo.inputs['W'], NF, NF / FPS * .35)
    ca = N.new('ShaderNodeMapRange'); ca.inputs['From Min'].default_value = 0.0; ca.inputs['From Max'].default_value = .018; ca.inputs['To Min'].default_value = 1.1; ca.inputs['To Max'].default_value = 0
    L.new(vo.outputs['Distance'], ca.inputs['Value']); bs.inputs['Emission Color'].default_value = (.55, .9, 1, 1); L.new(ca.outputs[0], bs.inputs['Emission Strength'])
    L.new(bs.outputs[0], fmix.inputs[1]); L.new(fmix.outputs[0], o.inputs[0]); fl.data.materials.append(sand)
    rng = random.Random(3)
    cols = [(.95, .3, .45), (1, .55, .15), (.65, .3, .95), (.95, .85, .3), (.2, .8, .7)]
    for i in range(11):
        base = Vector((rng.uniform(-3.0, 3.0), rng.uniform(-1.6, 3.5), -1.6))
        coral(base, rng, kit.mat_principled(f'coral{i}', cols[i % 5], .5, emit=cols[i % 5], emit_str=.12), length=rng.uniform(.45, .75), r=.1)
    for i in range(6):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=rng.uniform(.25, .45), location=(rng.uniform(-3, 3), rng.uniform(-1.2, 3), -1.6), segments=32, ring_count=16)
        bc = bpy.context.object; bc.scale = (1, 1, .7); kit.smooth(bc, 0)
        bm = kit.mat_principled(f'brain{i}', cols[(i + 2) % 5], .6); nb = bm.node_tree.nodes; bwv = nb.new('ShaderNodeTexWave'); bwv.inputs['Scale'].default_value = 9; bwv.inputs['Distortion'].default_value = 8
        bbp = nb.new('ShaderNodeBump'); bbp.inputs['Strength'].default_value = .7; bm.node_tree.links.new(bwv.outputs['Fac'], bbp.inputs['Height']); bm.node_tree.links.new(bbp.outputs['Normal'], nb['Principled BSDF'].inputs['Normal'])
        bc.data.materials.append(bm)
    for i in range(7):
        bpy.ops.mesh.primitive_ico_sphere_add(radius=rng.uniform(.3, .7), location=(rng.uniform(-4, 4), rng.uniform(-1, 4), -1.6), subdivisions=2)
        rk = bpy.context.object; rk.scale = (1, 1, .5); rk.data.materials.append(kit.mat_principled(f'rock{i}', (.25, .23, .22), .9))
    fcols = [(1, .5, .05), (.1, .5, 1), (1, .85, .1), (.95, .95, .95)]
    for i in range(9):
        f = fish(f'fish{i}', fcols[i % 4]); z = rng.uniform(-1.0, .3); y = rng.uniform(-.8, 2.5); sp = rng.uniform(.5, 1.0)
        x0 = rng.uniform(-5, -1); s = rng.uniform(.6, 1.1); f.scale = (s,) * 3
        for k in range(0, NF + 1, 12):
            t = k / FPS
            kit.key(f, k + 1, location=(x0 + sp * t, y, z + .12 * math.sin(t * 2 + i)), rotation_euler=(0, .08 * math.sin(t * 2 + i), .15 * math.sin(t * 6 + i)))

def orbit_ring(r, mat_strength=.8):
    bpy.ops.mesh.primitive_torus_add(major_radius=r, minor_radius=.012, major_segments=256, minor_segments=6)
    t = bpy.context.object; t.data.materials.append(kit.mat_emit('orbit', (.6, .7, 1), mat_strength)); return t

def ref_line(h=6.0):
    bpy.ops.mesh.primitive_cylinder_add(radius=.012, depth=h); c = bpy.context.object; c.data.materials.append(kit.mat_emit('ref', (.7, .75, .9), 1.2)); return c

def s4_tilt():
    kit.world(); kit.sun_lamp((1, -.6, .3), 4.2)
    cam, tgt = kit.camera((0, -12, 1.6), (0, 0, .2), lens=36)
    kit.key(cam, 1, location=(0, -12, 1.6)); kit.key(cam, NF, location=(.3, -11.2, 1.4))
    root, sp = kit.earth(1.6, (1, -.6, .3), tilt_deg=23.4, axis=True); spin(sp, .08)
    ref_line(5.4)
    ring = orbit_ring(3.8); ring.rotation_euler = (math.radians(6), 0, 0)
    piv = kit.link(bpy.data.objects.new('mpiv', None)); piv.rotation_euler = (math.radians(6), 0, 0)
    mo = kit.moon(.42); mo.location = (3.8, 0, 0); mo.parent = piv
    kit.key(piv, 1, rotation_euler=(math.radians(6), 0, math.radians(-30))); kit.key(piv, NF, rotation_euler=(math.radians(6), 0, math.radians(150)))
    tip = (math.sin(math.radians(23.4)) * 2.6, 0, math.cos(math.radians(23.4)) * 2.6)
    overlays.append({'type': 'label', 'text': '23.5°', 'pos': project(cam, (tip[0] + .9, 0, tip[2] + .1), F(D * .5)), 'color': (255, 222, 40)})

def s5_wobble():
    kit.world(); kit.sun_lamp((1, -.6, .3), 4.2)
    cam, tgt = kit.camera((0, -12, 1.6), (0, 0, .2), lens=36)
    root, sp = kit.earth(1.6, (1, -.6, .3), tilt_deg=23.4, axis=True); spin(sp, .08)
    ref_line(5.4)
    seq = [(0, 23.4), (.18, 6), (.36, 58), (.52, 12), (.72, 80), (.9, 35), (1.0, 45)]
    for u, deg in seq: kit.key(root, F(D * u), rotation_euler=(0, math.radians(deg), 0))
    kit.key(cam, 1, location=(0, -12, 1.6)); kit.key(cam, NF, location=(-.3, -11, 1.3))

def s6_extreme():
    kit.world(); kit.sun_lamp((1, -.5, .2), 4.5)
    cam, tgt = kit.camera((0, -9, .8), (0, 0, 0), lens=34)
    kit.key(cam, 1, location=(0, -9.5, .9)); kit.key(cam, NF, location=(0, -8.6, .7))
    root, sp = kit.earth(2.0, (1, -.5, .2), tilt_deg=50); spin(sp, .1)
    nt = bpy.data.materials['earth'].node_tree; ice = nt.nodes['ice']; warm = nt.nodes['warm']
    kf_input(ice.inputs[1], 1, .43); kf_input(ice.inputs[1], F(D * .4), .12); kf_input(ice.inputs[1], F(D * .55), .12); kf_input(ice.inputs[1], F(D * .9), .55)
    kf_input(warm.inputs['Fac'], 1, 0); kf_input(warm.inputs['Fac'], F(D * .55), 0); kf_input(warm.inputs['Fac'], F(D * .9), .85)
    sun_disc((7.5, 4, 2.5), .9)

def s7_thanks():
    kit.world(); kit.sun_lamp((1, -.3, .5), 4.2)
    cam, tgt = kit.camera((0, -10, .2), (0, 0, .9), lens=36)
    kit.key(cam, 1, location=(0, -10, .1)); kit.key(cam, NF, location=(0, -9.4, .3))
    root, sp = kit.earth(9, (1, -.3, .5), tilt_deg=10); root.location = (0, 2, -9.4); spin(sp, .004)
    mo = kit.moon(1.25); kit.key(mo, 1, location=(.6, 3, .4)); kit.key(mo, NF, location=(.6, 3, 1.5))
    spin(mo, .01)

def s8_outro():
    kit.world(); kit.sun_lamp((1, -.6, .4), 4.2)
    cam, tgt = kit.camera((0, -12, .6), (0, 0, 0), lens=34)
    root, sp = kit.earth(1.6, (1, -.6, .4)); root.location = (0, 0, .8); spin(sp, .04)
    mo = kit.moon(.4); mo.location = (2.6, -1, 1.9)
    a, limbs = kit.astronaut(); a.scale = (.36,) * 3; a.location = (-.5, -8.4, -1.0); a.rotation_euler = (0, 0, math.radians(15))
    for i, f in enumerate(range(1, NF + 1, 10)): kit.key(limbs['arm1'], f, rotation_euler=(0, math.radians(-150 if i % 2 else -115), 0))
    li = bpy.data.lights.new('key', 'AREA'); li.energy = 120; li.size = 2
    o = kit.link(bpy.data.objects.new('key', li)); o.location = (1, -11, 0)
    c = o.constraints.new('TRACK_TO'); c.target = a; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
    overlays.append({'type': 'handle', 'pos': project(cam, (.35, -8.4, -.95), 10)})

[s0_hook, s1_night, s2_tides, s3_coast, s4_tilt, s5_wobble, s6_extreme, s7_thanks, s8_outro][idx]()
for o in bpy.data.objects:
    for m in getattr(o, 'modifiers', []):
        if m.type == 'SUBSURF': m.render_levels = 1
os.makedirs(f'{OUT}/s{idx}', exist_ok=True)
json.dump({'frames': NF, 'overlays': overlays}, open(f'{OUT}/s{idx}/meta.json', 'w'))
if mode == 'still':
    sc.frame_set(int(NF * (float(sys.argv[3]) if len(sys.argv) > 3 else .6))); sc.render.filepath = f'{OUT}/still_{idx}.png'; bpy.ops.render.render(write_still=True)
else:
    sc.render.image_settings.file_format = 'PNG'; sc.render.filepath = f'{OUT}/s{idx}/f_'; bpy.ops.render.render(animation=True)
