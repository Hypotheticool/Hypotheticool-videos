"""3D black hole Short. Usage: python3 bh3d.py <scene_index> still|anim"""
import sys, math, json, os
sys.path.insert(0, '/home/claude/b3d')
import bpy, kit
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

FPS = 24
DURS = [3.0, 7.6, 6.4, 5.6, 4.4, 6.0, 6.9, 5.7, 7.3, 1.8]   # from the narration
PAD = 0.75                                                   # extra time for crossfades
OUT = '/home/claude/b3d/bh'
idx, mode = int(sys.argv[1]), sys.argv[2]
NF = int(math.ceil((DURS[idx] + PAD) * FPS))

sc = kit.reset(res=(648, 1152), samples=8)
sc.render.use_persistent_data = True
sc.cycles.adaptive_threshold = 0.05
sc.cycles.max_bounces = 3; sc.cycles.diffuse_bounces = 1; sc.cycles.glossy_bounces = 1
sc.frame_start, sc.frame_end = 1, NF
F = lambda sec: 1 + int(round(sec * FPS))
overlays = []

def emit_fade(name, color, strength):
    m = bpy.data.materials.new(name); nt, N, L = kit.nodes(m)
    o = N.new('ShaderNodeOutputMaterial'); e = N.new('ShaderNodeEmission'); tr = N.new('ShaderNodeBsdfTransparent'); mx = N.new('ShaderNodeMixShader')
    e.inputs['Color'].default_value = (*color, 1); e.inputs['Strength'].default_value = strength
    L.new(tr.outputs[0], mx.inputs[1]); L.new(e.outputs[0], mx.inputs[2]); L.new(mx.outputs[0], o.inputs[0])
    return m, e, mx

def kf_input(sock, frame, value):
    sock.default_value = value; sock.keyframe_insert('default_value', frame=frame)

def spaceship():
    root = bpy.data.objects.new('ship', None); kit.link(root)
    hull = kit.mat_principled('hull', (.85, .87, .92), rough=.3, coat=.5)
    red = kit.mat_principled('shipred', (.9, .12, .18), rough=.35, coat=.4)
    def add(o, m, sub=2, bev=0): o.data.materials.append(m); kit.smooth(o, sub, bev); o.parent = root; return o
    bpy.ops.mesh.primitive_cylinder_add(radius=.38, depth=2.4, rotation=(0, math.radians(90), 0)); add(bpy.context.object, hull, 2, .15)
    bpy.ops.mesh.primitive_cone_add(radius1=.38, depth=.9, location=(1.62, 0, 0), rotation=(0, math.radians(90), 0)); add(bpy.context.object, hull, 2)
    for z in (1, -1):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(-.95, 0, z * .5)); f = bpy.context.object; f.scale = (.7, .06, .55)
        f.rotation_euler = (0, z * math.radians(-25), 0); add(f, red, 1, .03)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(-.95, .45, 0)); f = bpy.context.object; f.scale = (.7, .5, .06); add(f, red, 1, .03)
    for i in range(3):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=.11, location=(.2 + i * .38, -.33, .12)); w = bpy.context.object
        w.data.materials.append(kit.mat_emit(f'win{i}', (.4, .85, 1), 8)); w.parent = root
    bpy.ops.mesh.primitive_cone_add(radius1=.32, depth=1.4, location=(-1.9, 0, 0), rotation=(0, math.radians(-90), 0))
    fl = bpy.context.object; fl.data.materials.append(kit.mat_emit('flame', (.35, .65, 1), 18)); fl.parent = root
    return root

def arrow(name, start, end, radius, color):
    s, e = Vector(start), Vector(end); d = e - s; L = d.length; head = radius * 3.2
    root = bpy.data.objects.new(name, None); kit.link(root); root.location = s
    root.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    m = kit.mat_emit(name + 'm', color, 6)
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=L - head, location=(0, 0, (L - head) / 2)); c = bpy.context.object
    c.data.materials.append(m); c.parent = root
    bpy.ops.mesh.primitive_cone_add(radius1=radius * 2.3, depth=head, location=(0, 0, L - head / 2)); h = bpy.context.object
    h.data.materials.append(m); h.parent = root
    return root

def curve_obj(name, pts, bevel, mat, radii=None):
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = bevel; cu.bevel_resolution = 3
    sp = cu.splines.new('POLY'); sp.points.add(len(pts) - 1)
    for i, p in enumerate(pts):
        sp.points[i].co = (*p, 1)
        if radii: sp.points[i].radius = radii[i]
    ob = kit.link(bpy.data.objects.new(name, cu)); ob.data.materials.append(mat); return ob

def project(cam, loc, frame):
    sc.frame_set(frame); v = world_to_camera_view(sc, cam, Vector(loc)); return (v.x, 1 - v.y)

# ======================================================================= scenes
def s0_hook():
    kit.world()
    cam, tgt = kit.camera((0, -14, 1.2), (0, 0, .2), lens=34)
    bh, disk = kit.black_hole((0, 0, 0), 1.6, cam=cam, tilt_deg=13)
    a, limbs = kit.astronaut(); a.scale = (.42,) * 3; kit.rim_lights((-.3, -8.6, -.4))
    kit.key(cam, 1, location=(0, -14, 1.2)); kit.key(cam, NF, location=(.4, -12.0, .9))
    kit.key(disk, 1, rotation_euler=(math.radians(13), 0, 0)); kit.key(disk, NF, rotation_euler=(math.radians(13), 0, math.radians(-12 * NF / FPS)))
    kit.key(a, 1, location=(-.36, -8.6, -.5), rotation_euler=(math.radians(12), math.radians(-20), math.radians(20)))
    kit.key(a, NF, location=(-.22, -8.5, -.28), rotation_euler=(math.radians(4), math.radians(-8), math.radians(40)))
    kit.key(limbs['arm1'], 1, rotation_euler=(0, math.radians(-32), 0)); kit.key(limbs['arm1'], NF, rotation_euler=(math.radians(-40), math.radians(-80), 0))
    li = bpy.data.lights.new('key', 'AREA'); li.energy = 70; li.size = 1.5; li.color = (1, .8, .65)
    o = kit.link(bpy.data.objects.new('key', li)); o.location = (1.2, -11, .5)
    c = o.constraints.new('TRACK_TO'); c.target = a; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'

def s1_star():
    kit.world()
    cam, tgt = kit.camera((0, -14, .5), (0, 0, 0), lens=34)
    kit.key(cam, 1, location=(0, -14, .5)); kit.key(cam, NF, location=(0, -12.5, .4))
    t_col = DURS[1] * .42
    # the star
    m = bpy.data.materials.new('starm'); nt, N, L = kit.nodes(m)
    o = N.new('ShaderNodeOutputMaterial'); e = N.new('ShaderNodeEmission'); nz = N.new('ShaderNodeTexNoise')
    nz.inputs['Scale'].default_value = 7; nz.inputs['Detail'].default_value = 8
    cr = N.new('ShaderNodeValToRGB'); cr.color_ramp.elements[0].color = (1, .25, .02, 1); cr.color_ramp.elements[1].color = (1, .9, .55, 1)
    L.new(nz.outputs['Fac'], cr.inputs['Fac']); L.new(cr.outputs['Color'], e.inputs['Color']); L.new(e.outputs[0], o.inputs[0])
    kf_input(e.inputs['Strength'], 1, 5.0); kf_input(e.inputs['Strength'], F(t_col), 7.0)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=2.3, segments=96, ring_count=48); star = bpy.context.object
    star.data.materials.append(m); kit.smooth(star, 1)
    kit.key(star, 1, scale=(1, 1, 1), rotation_euler=(0, 0, 0)); kit.key(star, F(t_col - .6), scale=(.92, .92, .92))
    kit.key(star, F(t_col + .35), scale=(.01, .01, .01), rotation_euler=(0, 0, math.radians(40)))
    # flash + shockwave
    fm, fe, fmx = emit_fade('flash', (1, .92, .8), 30)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1, segments=48, ring_count=24); fl = bpy.context.object; fl.data.materials.append(fm)
    kit.key(fl, 1, scale=(.01,) * 3); kit.key(fl, F(t_col + .3), scale=(.3,) * 3); kit.key(fl, F(t_col + 1.2), scale=(4,) * 3)
    kf_input(fmx.inputs['Fac'], 1, 0); kf_input(fmx.inputs['Fac'], F(t_col + .3), 1); kf_input(fmx.inputs['Fac'], F(t_col + 1.3), 0)
    sm, se, smx = emit_fade('shock', (1, .55, .25), 8)
    bpy.ops.mesh.primitive_torus_add(major_radius=1, minor_radius=.025, major_segments=192, minor_segments=8, rotation=(math.radians(80), 0, 0))
    sh = bpy.context.object; sh.data.materials.append(sm)
    kit.key(sh, 1, scale=(.01,) * 3); kit.key(sh, F(t_col + .3), scale=(.3,) * 3); kit.key(sh, F(t_col + 2.2), scale=(5,) * 3)
    kf_input(smx.inputs['Fac'], 1, 0); kf_input(smx.inputs['Fac'], F(t_col + .3), 1); kf_input(smx.inputs['Fac'], F(t_col + 2.2), 0)
    # black hole grows out of the collapse
    bh, disk = kit.black_hole((0, 0, 0), 1.2, cam=cam, tilt_deg=13)
    kit.key(bh, 1, scale=(.001,) * 3); kit.key(bh, F(t_col + .4), scale=(.001,) * 3); kit.key(bh, F(t_col + 2.0), scale=(1,) * 3)
    kit.key(disk, 1, rotation_euler=(math.radians(13), 0, 0)); kit.key(disk, NF, rotation_euler=(math.radians(13), 0, math.radians(-60)))

def s2_light():
    kit.world()
    cam, tgt = kit.camera((0, -12, .9), (0, 0, 0), lens=34)
    kit.key(cam, 1, location=(0, -12.5, .9)); kit.key(cam, NF, location=(.3, -11.2, .7))
    R = 1.2
    bh, disk = kit.black_hole((0, 0, 0), R, cam=cam, tilt_deg=13)
    kit.key(disk, 1, rotation_euler=(math.radians(13), 0, 0)); kit.key(disk, NF, rotation_euler=(math.radians(13), 0, math.radians(-50)))
    cyan = kit.mat_emit('beam', (.55, .9, 1), 14); red = kit.mat_emit('beam_in', (1, .45, .35), 14)
    n = 9
    for i in range(n):
        b = (i - (n - 1) / 2) * .62 * R
        x, z, vx, vz = -9.0, b, 1.0, 0.0; pts = []; cap = False
        for _ in range(3000):
            r = math.hypot(x, z)
            if r < R * 1.02: cap = True; break
            if x > 9: break
            k = 1.35 * R * R / r ** 3 * .02
            vx -= k * x; vz -= k * z; mm = math.hypot(vx, vz); vx, vz = vx / mm, vz / mm
            x += vx * .02; z += vz * .02
            if _ % 6 == 0: pts.append((x, -.6, z))
        ob = curve_obj(f'ray{i}', pts, .022, red if cap else cyan)
        cu = ob.data; cu.bevel_factor_mapping_end = 'SPLINE'
        cu.bevel_factor_end = 0; cu.keyframe_insert('bevel_factor_end', frame=1 + i * 3)
        cu.bevel_factor_end = 1; cu.keyframe_insert('bevel_factor_end', frame=F(DURS[2] * .8) + i * 3)

def s3_fall():
    kit.world()
    cam, tgt = kit.camera((0, -13, 1.2), (0, 0, 0), lens=32)
    kit.key(cam, 1, location=(0, -13, 1.2)); kit.key(cam, NF, location=(-.3, -12.2, 1.0))
    bh, disk = kit.black_hole((.6, 0, -.4), 1.25, cam=cam, tilt_deg=14)
    kit.key(disk, 1, rotation_euler=(math.radians(14), 0, 0)); kit.key(disk, NF, rotation_euler=(math.radians(14), 0, math.radians(-50)))
    a, limbs = kit.astronaut(); a.scale = (.45,) * 3
    kit.key(a, 1, location=(-1.6, -5.5, 2.3), rotation_euler=(math.radians(20), math.radians(30), math.radians(-160)))
    kit.key(a, NF, location=(-.35, -2.6, .9), rotation_euler=(math.radians(60), math.radians(50), math.radians(-120)))
    for fc in a.animation_data.action.fcurves if hasattr(a.animation_data.action, 'fcurves') else []:
        for kp in fc.keyframe_points: kp.interpolation = 'SINE'; kp.easing = 'EASE_OUT'
    ship = spaceship(); ship.scale = (.55,) * 3
    kit.key(ship, 1, location=(-.45, -8.6, -1.3), rotation_euler=(math.radians(-6), math.radians(4), math.radians(14)))
    kit.key(ship, NF, location=(-.3, -8.6, -1.25), rotation_euler=(math.radians(-4), math.radians(2), math.radians(16)))
    kit.rim_lights((-1, -6, 0))
    overlays.append({'type': 'label', 'text': 'YOUR FRIEND', 'pos': project(cam, (-.4, -8.6, -1.8), F(DURS[3] * .5)), 'color': (150, 230, 255)})

def s4_freeze():
    kit.world()
    cam, tgt = kit.camera((0, -7.5, .7), (.35, 0, .1), lens=36)
    kit.key(cam, 1, location=(0, -7.5, .7)); kit.key(cam, NF, location=(.15, -7.0, .6))
    bh, disk = kit.black_hole((0, 0, 0), 1.6, cam=cam, tilt_deg=12)
    kit.key(disk, 1, rotation_euler=(math.radians(12), 0, 0)); kit.key(disk, NF, rotation_euler=(math.radians(12), 0, math.radians(-25)))
    a, limbs = kit.astronaut(); a.scale = (.3,) * 3; a.location = (1.2, -2.6, .55)
    kit.key(a, 1, rotation_euler=(math.radians(40), math.radians(20), math.radians(-150)))
    kit.key(a, F(DURS[4] * .9), rotation_euler=(math.radians(48), math.radians(24), math.radians(-140)))
    kit.rim_lights((1.2, -2.6, .55))
    li = bpy.data.lights.new('key', 'AREA'); li.energy = 60; li.size = 1.5
    o = kit.link(bpy.data.objects.new('key', li)); o.location = (1.5, -5, 1.2)
    c = o.constraints.new('TRACK_TO'); c.target = a; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
    suit = bpy.data.materials['suit'].node_tree.nodes['Principled BSDF']; grey = bpy.data.materials['suitgrey'].node_tree.nodes['Principled BSDF']
    kf_input(suit.inputs['Base Color'], 1, (.88, .89, .93, 1)); kf_input(suit.inputs['Base Color'], F(DURS[4] * .85), (.35, .02, .01, 1))
    kf_input(grey.inputs['Base Color'], 1, (.35, .37, .45, 1)); kf_input(grey.inputs['Base Color'], F(DURS[4] * .85), (.15, .01, .0, 1))

def s5_you():
    kit.world()
    cam, tgt = kit.camera((0, -9.5, .2), (0, 0, .35), lens=30)
    bh, disk = kit.black_hole((0, 6, .9), 3.2, cam=cam, tilt_deg=10)
    kit.key(disk, 1, rotation_euler=(math.radians(10), 0, 0)); kit.key(disk, NF, rotation_euler=(math.radians(10), 0, math.radians(-30)))
    a, limbs = kit.astronaut(); a.scale = (.62,) * 3
    kit.key(cam, 1, location=(0, -9.5, .2)); kit.key(cam, NF, location=(0, -7.6, .25))
    kit.key(a, 1, location=(0, -7.4, -.45), rotation_euler=(math.radians(-6), 0, math.radians(8)))
    kit.key(a, NF, location=(0, -5.5, -.35), rotation_euler=(math.radians(4), 0, math.radians(-6)))
    for i, f in enumerate(range(1, NF + 1, 12)):
        kit.key(limbs['arm1'], f, rotation_euler=(0, math.radians(-150 if i % 2 else -115), 0))
    li = bpy.data.lights.new('key', 'AREA'); li.energy = 180; li.size = 2; li.color = (1, .85, .7)
    o = kit.link(bpy.data.objects.new('key', li)); o.location = (1.5, -9, 1.5)
    c = o.constraints.new('TRACK_TO'); c.target = a; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
    kit.rim_lights((0, -6, 0))

def s6_tidal():
    kit.world()
    cam, tgt = kit.camera((0, -8.2, -.4), (0, 0, -.7), lens=32)
    kit.key(cam, 1, location=(0, -8.2, -.4)); kit.key(cam, NF, location=(.2, -7.8, -.5))
    bh, disk = kit.black_hole((0, 0, -3.3), .8, cam=cam, tilt_deg=16)
    kit.key(disk, 1, rotation_euler=(math.radians(16), 0, 0)); kit.key(disk, NF, rotation_euler=(math.radians(16), 0, math.radians(-90)))
    a, limbs = kit.astronaut(); a.location = (-.35, 0, .2)
    kit.key(a, 1, scale=(.75, .75, .75), rotation_euler=(0, 0, math.radians(15)))
    kit.key(a, NF, scale=(.62, .62, 1.25), rotation_euler=(0, 0, math.radians(25)))
    kit.rim_lights((0, 0, 0))
    li = bpy.data.lights.new('key', 'AREA'); li.energy = 150; li.size = 2
    o = kit.link(bpy.data.objects.new('key', li)); o.location = (2, -6, 1)
    c = o.constraints.new('TRACK_TO'); c.target = a; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
    ha = arrow('head_arrow', (1.1, -.3, 1.75), (1.1, -.3, 1.35), .04, (.35, .75, 1))
    fa = arrow('feet_arrow', (1.1, -.3, -.3), (1.1, -.3, -1.8), .07, (1, .2, .2))
    for ar in (ha, fa):
        kit.key(ar, 1, scale=(.001,) * 3); kit.key(ar, F(.6), scale=(1,) * 3)
    fr = F(DURS[6] * .6)
    overlays.append({'type': 'label', 'text': 'HEAD', 'pos': project(cam, (1.4, -.3, 1.55), fr), 'color': (150, 220, 255)})
    overlays.append({'type': 'label', 'text': 'FEET', 'pos': project(cam, (1.4, -.3, -1.05), fr), 'color': (255, 130, 130)})

def s7_spag():
    kit.world()
    rig = kit.link(bpy.data.objects.new('rig', None))
    cam, tgt = kit.camera((0, -10, 6.0), (0, 0, -.3), lens=30); cam.parent = rig
    kit.key(rig, 1, rotation_euler=(0, 0, 0)); kit.key(rig, NF, rotation_euler=(0, 0, math.radians(25)))
    bh, disk = kit.black_hole((0, 0, 0), 1.3, cam=cam, tilt_deg=8)
    kit.key(disk, 1, rotation_euler=(math.radians(8), 0, 0)); kit.key(disk, NF, rotation_euler=(math.radians(8), 0, math.radians(-70)))
    noodle = kit.mat_emit('noodle', (1, .55, .22), 2.6)
    for j in range(3):
        pts, radii = [], []
        for i in range(260):
            u = i / 259
            ang = 2.6 * 2 * math.pi * u + j * .22 + 2.2
            r = 6.5 * (1 - u) ** 1.15 + 1.25
            pts.append((r * math.cos(ang), r * math.sin(ang), 2.4 * (1 - u) ** 2 + .05 * j)); radii.append(1.0 - .75 * u)
        ob = curve_obj(f'noodle{j}', pts, .07 - .015 * j, noodle, radii)
        cu = ob.data; cu.bevel_factor_mapping_start = cu.bevel_factor_mapping_end = 'SPLINE'
        cu.bevel_factor_end = 0.02; cu.keyframe_insert('bevel_factor_end', frame=1 + j * 4)
        cu.bevel_factor_end = 1.0; cu.keyframe_insert('bevel_factor_end', frame=F(DURS[7] * .75) + j * 4)
        cu.bevel_factor_start = 0.0; cu.keyframe_insert('bevel_factor_start', frame=F(DURS[7] * .2))
        cu.bevel_factor_start = 0.55; cu.keyframe_insert('bevel_factor_start', frame=NF)
    kit.rim_lights((0, 0, 1))

def s8_sing():
    w = bpy.data.worlds.new('void'); sc.world = w; w.use_nodes = True; w.node_tree.nodes['Background'].inputs[0].default_value = (0, 0, 0, 1)
    cam, tgt = kit.camera((0, 0, 0), (0, 50, 0), lens=24)
    kit.key(cam, 1, location=(0, 0, 0)); kit.key(cam, NF, location=(0, 11, 0))
    for i in range(36):
        y = 2 + i * 1.4; u = i / 35
        col = (1, .45 + .3 * (1 - u), .15 + .7 * u) if u < .5 else (.75 + .25 * (1 - u), .3, 1)
        bpy.ops.mesh.primitive_torus_add(major_radius=2.4, minor_radius=.035, major_segments=96, minor_segments=6, location=(0, y, 0), rotation=(math.radians(90), 0, 0))
        t = bpy.context.object; t.data.materials.append(kit.mat_emit(f'ring{i}', col, 1.8 * (1 - .4 * u)))
    for k in range(70):
        ang = k * 2.39996; rad = 1.6 + (k % 5) * .15; y = 3 + (k * 7.3) % 45
        bpy.ops.mesh.primitive_cylinder_add(radius=.012, depth=2.5, location=(rad * math.cos(ang), y, rad * math.sin(ang)), rotation=(math.radians(90), 0, 0))
        bpy.context.object.data.materials.append(kit.mat_emit(f'streak{k}', (.75, .6, 1), 6))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=.6, location=(0, 56, 0)); core = bpy.context.object
    core.data.materials.append(kit.mat_emit('core', (1, 1, 1), 80))
    kit.key(core, 1, scale=(1,) * 3); kit.key(core, NF, scale=(1.8,) * 3)

def s9_outro():
    kit.world()
    cam, tgt = kit.camera((0, -12.5, 1.0), (0, 0, -.6), lens=34)
    bh, disk = kit.black_hole((0, 0, .4), 1.25, cam=cam, tilt_deg=13)
    kit.key(disk, 1, rotation_euler=(math.radians(13), 0, 0)); kit.key(disk, NF, rotation_euler=(math.radians(13), 0, math.radians(-20)))
    a, limbs = kit.astronaut(); a.scale = (.36,) * 3; a.location = (-.55, -8.4, -1.25)
    a.rotation_euler = (0, 0, math.radians(15))
    for i, f in enumerate(range(1, NF + 1, 10)):
        kit.key(limbs['arm1'], f, rotation_euler=(0, math.radians(-150 if i % 2 else -115), 0))
    kit.rim_lights((-.5, -8.4, -1.2))
    li = bpy.data.lights.new('key', 'AREA'); li.energy = 120; li.size = 2
    o = kit.link(bpy.data.objects.new('key', li)); o.location = (1, -11, 0)
    c = o.constraints.new('TRACK_TO'); c.target = a; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
    overlays.append({'type': 'handle', 'pos': project(cam, (.35, -8.4, -1.2), 10)})

[s0_hook, s1_star, s2_light, s3_fall, s4_freeze, s5_you, s6_tidal, s7_spag, s8_sing, s9_outro][idx]()
for o in bpy.data.objects:          # keep subdivision light for render speed
    for m in getattr(o, 'modifiers', []):
        if m.type == 'SUBSURF': m.render_levels = 1
os.makedirs(f'{OUT}/s{idx}', exist_ok=True)
json.dump({'frames': NF, 'overlays': overlays}, open(f'{OUT}/s{idx}/meta.json', 'w'))
if mode == 'still':
    sc.frame_set(int(NF * .6)); sc.render.filepath = f'{OUT}/still_{idx}.png'; bpy.ops.render.render(write_still=True)
else:
    sc.render.image_settings.file_format = 'PNG'; sc.render.filepath = f'{OUT}/s{idx}/f_'
    bpy.ops.render.render(animation=True)
