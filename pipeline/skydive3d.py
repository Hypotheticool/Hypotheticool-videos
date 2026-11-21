"""3D Short (pick-a-scenario): Pick a world to skydive into (Mars, Venus, Jupiter, Titan).
Usage: python3 skydive3d.py <scene> still|anim [frac]"""
import sys, math, json, os, random
sys.path.insert(0, '/home/claude/b3d')
import bpy, bmesh, kit
from mathutils import Vector

CFG = json.load(open('/home/claude/b3d/skydive/topic.json'))
FPS = 24; DURS = CFG['durs']; PAD = 0.75; OUT = CFG['root']
idx, mode = int(sys.argv[1]), sys.argv[2]
D = DURS[idx]; NF = int(math.ceil((D + PAD) * FPS))
sc = kit.reset(res=(648, 1152), samples=8)
sc.render.use_persistent_data = True; sc.cycles.adaptive_threshold = 0.05
try:
    sc.cycles.denoising_quality = 'FAST'; sc.cycles.denoising_prefilter = 'FAST'
except Exception: pass
sc.cycles.max_bounces = 4; sc.cycles.diffuse_bounces = 1; sc.cycles.glossy_bounces = 1; sc.cycles.transparent_max_bounces = 12
sc.frame_start, sc.frame_end = 1, NF
F = lambda sec: 1 + int(round((sec + .35) * FPS))
overlays = []
rng = random.Random(idx + 11)
OPTS = ['Mars', 'Venus', 'Jupiter', 'Titan']
YEL, WHITE = (255, 222, 40), (255, 255, 255)

CUTS = []
def cuts(*cams_at):
    for k, (cam, sec) in enumerate(cams_at):
        fr = max(1, F(sec) if sec > 0 else 1); CUTS.append((cam, fr))
        m = sc.timeline_markers.new(f'cut{k}', frame=fr); m.camera = cam

def track(o, target):
    c = o.constraints.new('TRACK_TO'); c.target = target; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'

def area(name, loc, target, energy, color=(1, 1, 1), size=3):
    li = bpy.data.lights.new(name, 'AREA'); li.energy = energy; li.color = color; li.size = size
    o = kit.link(bpy.data.objects.new(name, li)); o.location = loc; track(o, target); return o

def cam_move(a, b, look, lens=32, look_b=None):
    cam, tgt = kit.camera(a, look, lens=lens)
    kit.key(cam, 1, location=a); kit.key(cam, NF, location=b)
    if look_b: kit.key(tgt, 1, location=look); kit.key(tgt, NF, location=look_b)
    return cam

def bg_world(top, bottom, strength=1.0):
    """simple sky gradient (for alien skies: Mars butterscotch, Venus orange gloom, Titan orange haze)"""
    w = bpy.data.worlds.new('alien'); sc.world = w; nt, N, L = kit.nodes(w)
    out = N.new('ShaderNodeOutputWorld'); bg = N.new('ShaderNodeBackground'); tc = N.new('ShaderNodeTexCoord')
    sep = N.new('ShaderNodeSeparateXYZ'); L.new(tc.outputs['Generated'], sep.inputs[0])
    mr = N.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value = .45; mr.inputs['From Max'].default_value = .8; L.new(sep.outputs['Z'], mr.inputs['Value'])
    cr = N.new('ShaderNodeValToRGB'); cr.color_ramp.elements[0].color = (*bottom, 1); cr.color_ramp.elements[1].color = (*top, 1)
    L.new(mr.outputs[0], cr.inputs['Fac']); L.new(cr.outputs['Color'], bg.inputs['Color']); bg.inputs['Strength'].default_value = strength
    L.new(bg.outputs[0], out.inputs['Surface'])

def emit_mat(name, color, strength, alpha=1.0):
    m = bpy.data.materials.new(name); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial')
    e = N.new('ShaderNodeEmission'); e.inputs['Color'].default_value = (*color, 1); e.inputs['Strength'].default_value = strength
    if alpha < 1:
        tr = N.new('ShaderNodeBsdfTransparent'); mx = N.new('ShaderNodeMixShader'); mx.inputs['Fac'].default_value = alpha
        L.new(tr.outputs[0], mx.inputs[1]); L.new(e.outputs[0], mx.inputs[2]); L.new(mx.outputs[0], o.inputs[0])
    else: L.new(e.outputs[0], o.inputs[0])
    return m

# ------------------------------------------------------------------ the jumper
def skydiver(scale=1.0, wings=False):
    """the white astronaut mascot in a belly-down skydiving arch: arms out and bent up, knees bent"""
    a, limbs = kit.astronaut()
    for side in (-1, 1):
        limbs[f'arm{side}'].rotation_euler = (math.radians(-15), -side * math.radians(98), 0)
        limbs[f'leg{side}'].rotation_euler = (math.radians(38), -side * math.radians(14), 0)
    if wings:   # thin fabric wings from wrist to hip (hang-glider fabric over a light frame)
        wm = kit.mat_principled('wing', (1.0, .5, .1), rough=.45); wm.use_backface_culling = False
        try: wm.node_tree.nodes['Principled BSDF'].inputs['Subsurface Weight'].default_value = .2
        except Exception: pass
        for side in (-1, 1):
            me = bpy.data.meshes.new('wing'); bm = bmesh.new()
            pts = [(side * .45, 0, .28), (side * 2.0, .05, .34), (side * 1.7, .1, -.15), (side * .5, .05, -.6)]
            vs = [bm.verts.new(p) for p in pts]; bm.faces.new(vs); bm.to_mesh(me); bm.free()
            w = kit.link(bpy.data.objects.new('wing', me), a); w.data.materials.append(wm)
            sub = w.modifiers.new('s', 'SUBSURF'); sub.levels = sub.render_levels = 2
    root = kit.link(bpy.data.objects.new('diver', None)); a.parent = root
    a.rotation_euler = (math.radians(90), 0, 0)      # belly down: visor faces -Z, head toward -Y
    root.scale = (scale,) * 3
    return root

def streaks(center, spread, n=40, length=.8, speed=(0, 0, 6), color=(1, .85, .6), strength=3, radius=.006):
    """thin glowing dust streaks rushing past (sense of falling speed)"""
    m = emit_mat('streak', color, strength, .7)
    for k in range(n):
        p = Vector(center) + Vector((rng.uniform(-1, 1) * spread[0], rng.uniform(-1, 1) * spread[1], rng.uniform(-1, 1) * spread[2]))
        bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=length, vertices=6, location=p); s = bpy.context.object
        s.data.materials.append(m); s.visible_shadow = False
        d = Vector(speed); s.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
        off = rng.uniform(0, 1)
        kit.key(s, 1, location=p - d * off * .5); kit.key(s, NF, location=p + d * (NF / FPS) - d * off * .5)
        for fc in (s.animation_data.action.fcurves if hasattr(s.animation_data.action, 'fcurves') else []):
            for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'

def parachute(radius, colors, gores=16, lines_to=(0, 0, -2.0), name='chute'):
    """canopy dome with alternating colored gores + suspension lines to a confluence point (local coords, canopy at origin)"""
    root = kit.link(bpy.data.objects.new(name, None))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1, segments=gores * 4, ring_count=24); c = bpy.context.object
    me = c.data; bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < .15], context='VERTS'); bm.to_mesh(me); bm.free()
    c.scale = (radius, radius, radius * .55); c.parent = root
    for p in me.polygons: p.use_smooth = True
    m = bpy.data.materials.new(name + '_m'); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial')
    bs = N.new('ShaderNodeBsdfPrincipled'); bs.inputs['Roughness'].default_value = .6
    tc = N.new('ShaderNodeTexCoord'); g = N.new('ShaderNodeTexGradient'); g.gradient_type = 'RADIAL'; L.new(tc.outputs['Object'], g.inputs['Vector'])
    ml = N.new('ShaderNodeMath'); ml.operation = 'MULTIPLY'; ml.inputs[1].default_value = gores / 2; L.new(g.outputs['Fac'], ml.inputs[0])
    fr = N.new('ShaderNodeMath'); fr.operation = 'FRACT'; L.new(ml.outputs[0], fr.inputs[0])
    st = N.new('ShaderNodeMath'); st.operation = 'GREATER_THAN'; st.inputs[1].default_value = .5; L.new(fr.outputs[0], st.inputs[0])
    mx = N.new('ShaderNodeMixRGB'); L.new(st.outputs[0], mx.inputs['Fac']); mx.inputs[1].default_value = (*colors[0], 1); mx.inputs[2].default_value = (*colors[1], 1)
    L.new(mx.outputs[0], bs.inputs['Base Color'])
    try:
        bs.inputs['Subsurface Weight'].default_value = .25
        bs.inputs['Transmission Weight'].default_value = .0
    except Exception: pass
    L.new(bs.outputs[0], o.inputs[0]); c.data.materials.append(m); m.use_backface_culling = False
    lm = kit.mat_principled('lines', (.85, .85, .82), rough=.6); tip = Vector(lines_to)
    for k in range(gores):
        a = 2 * math.pi * k / gores; rim = Vector((radius * .99 * math.cos(a), radius * .99 * math.sin(a), radius * .55 * .15))
        d = tip - rim; bpy.ops.mesh.primitive_cylinder_add(radius=.008 * radius, depth=d.length, vertices=4, location=(rim + tip) / 2)
        l = bpy.context.object; l.rotation_euler = d.to_track_quat('Z', 'Y').to_euler(); l.data.materials.append(lm); l.parent = root
    return root

# ------------------------------------------------------------------ worlds
def globe(R, kind, sun_dir):
    """Venus: featureless pale-yellow sulfuric-acid cloud deck (as in visible-light photos, e.g. Mariner 10 / MESSENGER natural color);
    Titan: opaque orange haze with a thin blue-ish detached haze at the limb (Cassini natural-color views)."""
    m = bpy.data.materials.new(kind); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled')
    tc = N.new('ShaderNodeTexCoord'); mp = N.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (1, 1, 5) if kind == 'venus' else (1, 1, 3)
    L.new(tc.outputs['Object'], mp.inputs['Vector'])
    nz = kit._noise(N, L, mp.outputs[0], 2.2, 6, .55)
    cr = N.new('ShaderNodeValToRGB')
    if kind == 'venus': c0, c1 = (.72, .6, .36), (.93, .86, .62)
    else: c0, c1 = (.42, .2, .04), (.62, .32, .07)
    cr.color_ramp.elements[0].color = (*c0, 1); cr.color_ramp.elements[1].color = (*c1, 1); cr.color_ramp.elements[0].position = .3; cr.color_ramp.elements[1].position = .7
    L.new(nz.outputs['Fac'], cr.inputs['Fac']); L.new(cr.outputs['Color'], bs.inputs['Base Color']); bs.inputs['Roughness'].default_value = .95
    bs.inputs['Specular IOR Level'].default_value = .1; L.new(bs.outputs[0], o.inputs[0])
    s = kit._sphere(R); s.data.materials.append(m)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=R * 1.025, segments=128, ring_count=64); at = bpy.context.object
    at.data.materials.append(kit.mat_atmo((.95, .8, .45) if kind == 'venus' else (.45, .6, .9), 1.2 if kind == 'venus' else 1.6))
    for p in at.data.polygons: p.use_smooth = True
    at.visible_shadow = False; at.parent = s
    return s

def mars_ground():
    t = kit.terrain(size=160, height=2.2, scale=6, kind='desert', seed=4, res=7); t.location.z = -.6
    cr = [n for n in t.active_material.node_tree.nodes if n.type == 'VALTORGB'][0]
    cr.color_ramp.elements[0].color = (.32, .12, .05, 1); cr.color_ramp.elements[1].color = (.62, .3, .14, 1)   # rust-orange regolith
    return t

def cloud_layer(z, size, color, density_lo=.45, density_hi=.75, scale=1.5, name='layer', alpha=1.0):
    """a cheap cloud deck: a big plane with noise-cut transparency (Jupiter's banded ammonia/ammonium-hydrosulfide decks)"""
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, z)); p = bpy.context.object; p.name = name
    m = bpy.data.materials.new(name); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); tc = N.new('ShaderNodeTexCoord')
    mp = N.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (1, 4, 1); L.new(tc.outputs['Generated'], mp.inputs['Vector'])
    nz = kit._noise(N, L, mp.outputs[0], scale * 6, 6, .55)
    mr = N.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value = density_lo; mr.inputs['From Max'].default_value = density_hi; L.new(nz.outputs['Fac'], mr.inputs['Value'])
    ml = N.new('ShaderNodeMath'); ml.operation = 'MULTIPLY'; ml.inputs[1].default_value = alpha; L.new(mr.outputs[0], ml.inputs[0])
    d = N.new('ShaderNodeBsdfDiffuse'); d.inputs['Color'].default_value = (*color, 1)
    tr = N.new('ShaderNodeBsdfTransparent'); mx = N.new('ShaderNodeMixShader')
    L.new(ml.outputs[0], mx.inputs['Fac']); L.new(tr.outputs[0], mx.inputs[1]); L.new(d.outputs[0], mx.inputs[2]); L.new(mx.outputs[0], o.inputs[0])
    p.data.materials.append(m); p.visible_shadow = False; return p

def titan_ground():
    """Titan's dark dune plains + a dark, glassy liquid methane/ethane lake (like Ligeia Mare), under dim orange light"""
    t = kit.terrain(size=160, height=3.0, scale=6, kind='mud', seed=9, res=7); t.location.z = -.4
    cr = [n for n in t.active_material.node_tree.nodes if n.type == 'VALTORGB'][0]
    cr.color_ramp.elements[0].color = (.12, .07, .03, 1); cr.color_ramp.elements[1].color = (.3, .19, .09, 1)
    bpy.ops.mesh.primitive_plane_add(size=160, location=(0, 0, -.05)); lake = bpy.context.object; lake.name = 'lake'
    lake.data.materials.append(kit.mat_principled('methane', (.02, .015, .01), rough=.03))
    return t

def venus_ground():
    t = kit.terrain(size=120, height=.45, scale=3, kind='volcanic', seed=2, res=7); t.location.z = -.12
    cr = [n for n in t.active_material.node_tree.nodes if n.type == 'VALTORGB'][0]
    cr.color_ramp.elements[0].color = (.07, .05, .04, 1); cr.color_ramp.elements[1].color = (.26, .2, .16, 1)   # dark basalt slabs (Venera 13 panoramas)
    return t

def venera(scale=1.0):
    """Venera 13 lander (simplified from Lavochkin/NSSDC photos): spherical pressure vessel on a ring landing collar,
    disc-shaped aerobrake ('drag plate') above, antenna on top"""
    root = kit.link(bpy.data.objects.new('venera', None))
    met = kit.mat_principled('ven_metal', (.62, .6, .55), rough=.35, metal=.6); dark = kit.mat_principled('ven_dark', (.12, .12, .13), rough=.5)
    def add(o, m, sub=1):
        o.data.materials.append(m); kit.smooth(o, sub); o.parent = root; return o
    bpy.ops.mesh.primitive_torus_add(major_radius=.75, minor_radius=.16, location=(0, 0, .16)); add(bpy.context.object, met)
    for k in range(8):
        a = k * math.pi / 4; bpy.ops.mesh.primitive_cylinder_add(radius=.04, depth=.7, location=(.42 * math.cos(a), .42 * math.sin(a), .5))
        s = bpy.context.object; s.rotation_euler = (math.radians(-28) * math.sin(a), math.radians(28) * math.cos(a), 0); add(s, met, 0)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=.5, location=(0, 0, .9)); add(bpy.context.object, met, 1)
    bpy.ops.mesh.primitive_cylinder_add(radius=.18, depth=.5, location=(0, 0, 1.45)); add(bpy.context.object, dark, 0)
    bpy.ops.mesh.primitive_cylinder_add(radius=1.05, depth=.05, vertices=48, location=(0, 0, 1.68)); add(bpy.context.object, met, 0)
    bpy.ops.mesh.primitive_cone_add(radius1=.3, radius2=.05, depth=.6, location=(0, 0, 2.0)); add(bpy.context.object, met, 0)
    for s in (-1, 1):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(s * .55, -.35, .75)); b = bpy.context.object; b.scale = (.25, .12, .2); add(b, dark, 0)
    root.scale = (scale,) * 3; return root

def capsule_under_chute(kind):
    """Perseverance in its aeroshell (white conical backshell + tan 70-deg heat shield, 4.5 m) / Galileo descent module"""
    root = kit.link(bpy.data.objects.new(kind, None))
    if kind == 'mars2020':
        bpy.ops.mesh.primitive_cone_add(radius1=1.0, radius2=.45, depth=.75, vertices=64, location=(0, 0, .37)); b = bpy.context.object
        b.data.materials.append(kit.mat_principled('backshell', (.85, .85, .82), rough=.5)); kit.smooth(b, 1); b.parent = root
        bpy.ops.mesh.primitive_cone_add(radius1=1.0, radius2=.12, depth=.36, vertices=64, location=(0, 0, -.18), rotation=(math.pi, 0, 0)); h = bpy.context.object
        h.data.materials.append(kit.mat_principled('heatshield', (.36, .24, .14), rough=.8)); kit.smooth(h, 1); h.parent = root
        top = (0, 0, .78)
    else:   # Galileo probe descent module: squat aluminium body with gold-foil insulation
        bpy.ops.mesh.primitive_cylinder_add(radius=.34, depth=.42, vertices=48, location=(0, 0, 0)); b = bpy.context.object
        b.data.materials.append(kit.mat_foil('gfoil', (1.0, .75, .35))); kit.smooth(b, 1, .03); b.parent = root
        bpy.ops.mesh.primitive_uv_sphere_add(radius=.32, location=(0, 0, .16)); d = bpy.context.object; d.scale = (1, 1, .55)
        d.data.materials.append(kit.mat_principled('alu', (.75, .76, .78), rough=.35, metal=.6)); kit.smooth(d, 1); d.parent = root
        top = (0, 0, .34)
    return root, Vector(top)

def chute_rig(kind, chute_r, height, colors, loc):
    rig = kit.link(bpy.data.objects.new('rig', None)); rig.location = loc
    body, top = capsule_under_chute(kind); body.parent = rig
    ch = parachute(chute_r, colors, 16, lines_to=(0, 0, -height), name='chute'); ch.parent = rig; ch.location = top + Vector((0, 0, height))
    return rig

# ======================================================================= scenes
def titan_flight(cam_a, cam_b, y0=0.0):
    """the payoff: the mascot gliding on strapped-on wings high above Titan's dunes and methane lake (dim orange daylight)"""
    bg_world((.16, .07, .02), (.5, .26, .07), .65)
    kit.sun_lamp((.3, -.6, .7), 1.1, (1, .6, .26))
    titan_ground()
    Z = 16.0
    for hz, al in ((4.0, .22),):       # haze between the jumper and the ground (Titan's thick hazy air)
        bpy.ops.mesh.primitive_plane_add(size=300, location=(0, 0, hz)); hp = bpy.context.object
        hp.data.materials.append(emit_mat(f'haze{hz}', (.55, .3, .09), .8, al)); hp.visible_shadow = False
    d = skydiver(1.0, wings=True)
    for o in [d] + list(d.children_recursive): o.visible_shadow = False
    ra, rb = (math.radians(-14), math.radians(-10), math.radians(-6)), (math.radians(-10), math.radians(8), math.radians(4))
    if y0: ra, rb = rb, ra
    kit.key(d, 1, location=(0, y0, Z + (.3 if y0 else 0)), rotation_euler=ra)
    kit.key(d, NF, location=(0, y0 - 1.6, Z - (0 if y0 else .3)), rotation_euler=rb)
    area('key', (2.5, -5, Z + 4), d, 320, (1, .88, .7)); area('rim', (-3, 4, Z + 3), d, 260, (.55, .7, 1)); area('under', (1, -4, Z - 3), d, 260, (1, .6, .3))
    return cam_move(cam_a, cam_b, (0, y0 + .2, Z + .9), 30, (0, y0 - 1.4, Z + .7))

S0A, S0B = (2.6, -5.2, 14.9), (2.0, -4.6, 15.1)
def s0_hook():                  # "Only one of these jumps survives."
    titan_flight(S0A, S0B)
    overlays.append({'type': 'hook', 'text': 'ONLY 1 JUMP|SURVIVES'})

def lineup(zc=0.0):
    """2x2 grid in option order (1 Mars, 2 Venus / 3 Jupiter, 4 Titan); same size on screen (NOT TO SCALE label)"""
    kit.world(); kit.sun_lamp((1, -.6, .3), 3.2)
    xs = [(-1.2, zc + 1.15, 'mars'), (1.2, zc + 1.15, 'venus'), (-1.2, zc - 1.15, 'jupiter'), (1.2, zc - 1.15, 'titan')]
    objs = []
    for x, z, nme in xs:
        if nme in ('mars', 'jupiter'):
            root, spin, s = kit.planet(nme, 1.0, 25.2 if nme == 'mars' else 3.1); root.location = (x, 0, z)
            kit.key(spin, 1, rotation_euler=(0, 0, 0)); kit.key(spin, NF, rotation_euler=(0, 0, math.radians(14)))
        else:
            s = globe(1.0, nme, (1, -.6, .3)); s.location = (x, 0, z)
        objs.append(s)
    return objs

def s1_options():               # "Pick one: a world to skydive into."
    lineup()
    d = skydiver(.3); d.location = (0, -2.0, 0)
    kit.key(d, 1, rotation_euler=(math.radians(-10), 0, math.radians(-5))); kit.key(d, NF, rotation_euler=(math.radians(-4), 0, math.radians(8)))
    area('k', (1, -5, 1), d, 15, (1, .85, .7))
    c1 = cam_move((0, -9.6, .3), (0, -8.9, .25), (0, 0, 1.0), 30)
    c2 = cam_move((-2.6, -7.8, -1.6), (-2.2, -7.2, -1.3), (0, 0, .9), 30)
    cuts((c1, 0), (c2, 1.5))
    overlays.append({'type': 'options', 'items': OPTS})
    overlays.append({'type': 'label', 'text': 'NOT TO SCALE', 'pos': (.5, .9), 'color': (200, 210, 230), 'from': .6})

def s2_count():                 # "Pick one, two, three or four, and comment. Think about it."
    lineup()
    d = skydiver(.45); d.location = (0, -3.2, -.2)
    kit.key(d, 1, rotation_euler=(0, 0, math.radians(-30))); kit.key(d, NF, rotation_euler=(math.radians(10), 0, math.radians(40)))
    area('k', (1, -6, 1), d, 25, (1, .85, .7))
    c1 = cam_move((1.2, -7.4, .9), (.8, -6.8, .7), (0, 0, 1.1), 30)
    c2 = cam_move((-1.0, -10.5, -.4), (-.6, -9.8, -.3), (0, 0, .9), 30)
    cuts((c1, 0), (c2, 2.0))
    overlays.append({'type': 'options', 'items': OPTS})
    overlays.append({'type': 'countdown', 'secs': 3, 'pos': [.5, .58]})

def s3_mars():                  # "One, Mars. The air is less than one percent as thick as Earth's."
    kit.world(); kit.sun_lamp((1, -.4, .4), 3.6)
    root, spin, s = kit.planet('mars', 6.0, 25.2, face_lon=-60); root.location = (0, 0, -7.2)
    kit.key(spin, 1, rotation_euler=(0, 0, 0)); kit.key(spin, NF, rotation_euler=(0, 0, math.radians(3)))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=6.08, segments=128, ring_count=64, location=(0, 0, -7.2)); at = bpy.context.object
    at.data.materials.append(kit.mat_atmo((.85, .55, .35), .6)); at.visible_shadow = False   # Mars' faint, thin atmosphere
    d = skydiver(.7); d.location = (0, 0, .2)
    kit.key(d, 1, location=(0, 0, .5)); kit.key(d, NF, location=(0, 0, -.1))
    area('key', (2, -3, 3), d, 60, (1, .85, .7)); area('rim', (-2, 3, 2), d, 120, (.6, .7, 1))
    c1 = cam_move((0, -5.2, 1.6), (0, -4.6, 1.1), (0, 0, -.6), 30)
    c2 = cam_move((1.8, -1.2, 3.6), (1.4, -1.0, 3.0), (0, 0, -.5), 24)
    cuts((c1, 0), (c2, 2.2))
    overlays.append({'type': 'options', 'items': OPTS, 'pick': 0})
    overlays.append({'type': 'badge', 'value': '<1%', 'unit': "of Earth's air", 'pos': [.5, .4], 'from': 1.4})

def s4_rover():                 # "Even under its parachute, NASA's rover was still falling at two hundred miles an hour."
    bg_world((.42, .3, .22), (.75, .55, .38), .9)            # butterscotch Martian sky
    kit.sun_lamp((.6, -.4, .6), 3.2, (1, .9, .78))
    mars_ground()
    rig = chute_rig('mars2020', 4.8, 9.0, ((.85, .2, .1), (.95, .95, .92)), (0, 0, 14))   # 21.5 m chute vs 4.5 m aeroshell
    kit.key(rig, 1, location=(0, 0, 15.5), rotation_euler=(0, math.radians(5), 0)); kit.key(rig, NF, location=(0, 0, 11.5), rotation_euler=(0, math.radians(-4), 0))
    streaks((0, 0, 13), (6, 6, 8), 50, 1.0, (0, 0, 9), (1, .8, .6), .8, .004)
    c1 = cam_move((7, -12, 9), (6.5, -11, 7.6), (0, 0, 17), 30, (0, 0, 15))
    c2 = cam_move((1.6, -4.5, 7), (1.3, -4.0, 5.6), (0, 0, 14.5), 22, (0, 0, 12.0))
    c3 = cam_move((0, -26, 4.0), (0, -24, 3.5), (0, 0, 9), 30, (0, 0, 8))
    cuts((c1, 0), (c2, 1.9), (c3, 3.8))
    overlays.append({'type': 'options', 'items': OPTS, 'pick': 0})
    overlays.append({'type': 'badge', 'value': '200', 'unit': 'mph', 'pos': [.5, .4], 'from': 2.4})
    overlays.append({'type': 'label', 'text': '≈ 3× HIGHWAY SPEED', 'pos': (.5, .46), 'color': WHITE, 'from': 3.0})

def s5_venus():                 # "Two, Venus. Below its acid clouds, the air pressure is ninety times Earth's."
    kit.world(); kit.sun_lamp((1, -.5, .3), 3.4)
    v = globe(6.0, 'venus', (1, -.5, .3)); v.location = (0, 0, -7.2)
    kit.key(v, 1, rotation_euler=(0, 0, 0)); kit.key(v, NF, rotation_euler=(0, 0, math.radians(-4)))
    d = skydiver(.7); d.location = (0, 0, .2)
    kit.key(d, 1, location=(0, 0, .5)); kit.key(d, NF, location=(0, 0, -.2))
    area('key', (2, -3, 3), d, 60, (1, .85, .6)); area('rim', (-2, 3, 2), d, 120, (.6, .7, 1))
    c1 = cam_move((-1.5, -5.0, 1.2), (-1.1, -4.4, .9), (0, 0, -.5), 30)
    # second shot: down inside the gloomy lower atmosphere (dim orange, clouds above)
    c2 = cam_move((200, -5, 1.0), (200, -4.2, .9), (200, 3, 1.6), 24)
    cuts((c1, 0), (c2, 2.6))
    overlays.append({'type': 'options', 'items': OPTS, 'pick': 1})
    overlays.append({'type': 'badge', 'value': '90×', 'unit': "Earth's pressure", 'pos': [.5, .4], 'from': 2.9})
    overlays.append({'type': 'label', 'text': '≈ 1 KM UNDERWATER', 'pos': (.5, .46), 'color': WHITE, 'from': 3.4})
    return c2

def venus_surface_set(off=(0, 0, 0)):
    g = venus_ground(); g.location = Vector(off) + Vector((0, 0, -.3))
    deck = cloud_layer(off[2] + 14, 200, (.75, .5, .2), .3, .7, 1.2, 'vdeck'); deck.location.x = off[0]
    return g

def s6_lander():                # "It's hot enough to melt lead. The toughest lander lasted about two hours."
    bg_world((.2, .09, .03), (.6, .3, .1), .7)
    kit.sun_lamp((.2, -.3, 1), 1.4, (1, .62, .3))
    venus_ground()
    v = venera(1.0); v.location = (0, 0, .25); v.rotation_euler = (0, 0, math.radians(20))
    area('heat', (0, 0, -.2), v, 0)
    li = bpy.data.lights.new('glow', 'POINT'); li.energy = 400; li.color = (1, .4, .1); lo = kit.link(bpy.data.objects.new('glow', li)); lo.location = (2, -2, .6)
    kit.key(li, 1, energy=150); kit.key(li, NF, energy=600)
    streaks((0, 0, 1.5), (4, 4, 1.5), 40, .05, (0, 0, .5), (1, .5, .15), 6, .015)    # rising heat sparks
    c1 = cam_move((4.2, -6.4, 2.2), (3.6, -5.6, 1.9), (0, 0, .5), 28)
    c2 = cam_move((-2.6, -4.0, .9), (-2.2, -3.4, .9), (0, 0, .9), 26)
    cuts((c1, 0), (c2, 2.4))
    overlays.append({'type': 'options', 'items': OPTS, 'pick': 1})
    overlays.append({'type': 'badge', 'value': '465°C', 'unit': 'melts lead', 'pos': [.5, .4], 'from': .3})
    overlays.append({'type': 'datestamp', 'text': 'VENERA 13 · 1982', 'from': 2.4})
    overlays.append({'type': 'badge', 'value': '127', 'unit': 'minutes', 'pos': [.5, .47], 'from': 3.0})

def s7_jupiter():               # "Three, Jupiter. There's no ground. You'd just keep falling into crushing heat."
    kit.world(); kit.sun_lamp((1, -.4, .3), 3.6)
    root, spin, s = kit.planet('jupiter', 9.0, 3.1, face_lon=0); root.location = (0, 0, -10.2)
    root.rotation_euler = (math.radians(78), math.radians(3.1), 0)   # turn the banded equator (not the bluish pole) toward the camera
    kit.key(spin, 1, rotation_euler=(0, 0, 0)); kit.key(spin, NF, rotation_euler=(0, 0, math.radians(4)))
    d = skydiver(.7); d.location = (0, 0, .2)
    kit.key(d, 1, location=(0, 0, .6)); kit.key(d, NF, location=(0, 0, -.2))
    area('key', (2, -3, 3), d, 60, (1, .85, .65)); area('rim', (-2, 3, 2), d, 120, (.6, .7, 1))
    c1 = cam_move((1.5, -5.0, 1.6), (1.1, -4.4, 1.1), (0, 0, -.8), 30)
    # inside: banded cloud decks, darker and redder with depth (lit from above, glowing warm from below)
    for k, (z, col) in enumerate([(12, (.92, .86, .74)), (-3, (.85, .66, .45)), (-8, (.65, .42, .24)), (-14, (.42, .22, .1))]):
        cl = cloud_layer(z, 120, col, .45 + k * .03, .75, 1.4, f'jl{k}'); cl.location.x = 300
    bpy.ops.mesh.primitive_uv_sphere_add(radius=55, location=(300, 0, 0)); bd = bpy.context.object
    bd.data.materials.append(emit_mat('jsky', (.42, .25, .12), .7)); bd.visible_shadow = False
    for p in bd.data.polygons: p.use_smooth = True
    li = bpy.data.lights.new('deep', 'AREA'); li.energy = 4000; li.color = (1, .35, .08); li.size = 40
    lo = kit.link(bpy.data.objects.new('deep', li)); lo.location = (300, 0, -18); lo.rotation_euler = (math.pi, 0, 0)
    d2 = skydiver(.8); d2.location = (300, 0, 2)
    kit.key(d2, 1, location=(300, 0, 3.0)); kit.key(d2, NF, location=(300, 0, -1.5))
    area('k2', (302, -3, 6), d2, 50, (1, .85, .65))
    streaks((300, 0, 1), (5, 5, 6), 50, 1.0, (0, 0, 8), (1, .8, .6), 1.5, .008)
    c2 = cam_move((301.5, -4.5, 4.5), (301.2, -4.0, 1.5), (300, 0, 2.2), 26, (300, 0, -1.2))
    cuts((c1, 0), (c2, 2.3))
    overlays.append({'type': 'options', 'items': OPTS, 'pick': 2})
    overlays.append({'type': 'badge', 'value': 'NO', 'unit': 'solid surface', 'pos': [.5, .4], 'from': 1.3})

def s8_galileo():               # "NASA's Galileo probe tried it in nineteen ninety five, and went silent after about an hour."
    bg_world((.55, .38, .22), (.25, .12, .05), .8)
    kit.sun_lamp((.3, -.4, 1), 2.4, (1, .9, .78))
    for k, (z, col) in enumerate([(14, (.92, .85, .72)), (-4, (.7, .48, .3)), (-12, (.42, .22, .1))]):
        cloud_layer(z, 200, col, .35 + k * .05, .72, 1.1, f'gl{k}')
    rig = chute_rig('galileo', 1.25, 3.4, ((.95, .95, .92), (.95, .5, .15)), (0, 0, 4))    # 2.5 m main chute
    kit.key(rig, 1, location=(0, 0, 5), rotation_euler=(0, math.radians(4), 0)); kit.key(rig, NF, location=(0, 0, 2), rotation_euler=(0, math.radians(-5), math.radians(20)))
    area('k', (3, -4, 7), rig, 120, (1, .85, .65))
    streaks((0, 0, 4), (5, 5, 6), 40, .6, (0, 0, 5), (1, .8, .6), .8, .004)
    c1 = cam_move((3.2, -6.5, 6.5), (2.8, -5.8, 5.2), (0, 0, 6.5), 30, (0, 0, 3.8))
    c2 = cam_move((-1.2, -3.0, 3.2), (-1.0, -2.6, 1.5), (0, 0, 5.4), 24, (0, 0, 2.6))
    c3 = cam_move((0, -14, 1), (0, -13, .5), (0, 0, 4), 30, (0, 0, 2))
    cuts((c1, 0), (c2, 2.2), (c3, 4.3))
    overlays.append({'type': 'options', 'items': OPTS, 'pick': 2})
    overlays.append({'type': 'datestamp', 'text': 'JUPITER · 7 DEC 1995', 'from': .3})
    overlays.append({'type': 'badge', 'value': '58', 'unit': 'minutes of data', 'pos': [.5, .4], 'from': 3.6})
    return rig

def s9_titan():                 # "Four, Titan. Thick air and tiny gravity mean you fall slowly."
    kit.world(); kit.sun_lamp((1, -.3, .25), 3.4)
    t = globe(5.0, 'titan', (1, -.3, .25)); t.location = (0, 0, -6.2)
    root, spin, s = kit.planet('saturn', 9.0, 0.0); root.location = (-24, 75, 3.0); root.rotation_euler = (math.radians(2.5), 0, 0)   # Titan orbits in the ring plane: rings seen almost edge-on
    d = skydiver(.7); d.location = (0, 0, .2)
    kit.key(d, 1, location=(0, 0, .35), rotation_euler=(0, 0, 0)); kit.key(d, NF, location=(0, 0, .15), rotation_euler=(0, 0, math.radians(12)))
    area('key', (2, -3, 3), d, 60, (1, .8, .55)); area('rim', (-2, 3, 2), d, 120, (.6, .7, 1))
    c1 = cam_move((1.0, -5.2, 1.0), (.8, -4.6, .9), (-1.2, 0, .2), 30)
    c2 = cam_move((-2.2, -2.4, 2.2), (-1.9, -2.0, 1.9), (0, 0, .1), 26)
    cuts((c1, 0), (c2, 2.2))
    overlays.append({'type': 'options', 'items': OPTS, 'pick': 3})
    overlays.append({'type': 'badge', 'value': '1/7', 'unit': "Earth's gravity", 'pos': [.5, .4], 'from': 2.2})
    overlays.append({'type': 'badge', 'value': '1.5×', 'unit': "Earth's air pressure", 'pos': [.5, .47], 'from': 1.2})

def s10_huygens():              # "Its Huygens probe drifted down for nearly two and a half hours."
    bg_world((.22, .1, .03), (.6, .33, .1), .7)
    kit.sun_lamp((.3, -.6, .7), 1.4, (1, .62, .28))
    titan_ground()
    rig = kit.link(bpy.data.objects.new('hrig', None)); rig.location = (0, 0, 9)
    h = kit.nasa_model('Cassini-Huygens (A)', 1.3, 'X'); h.parent = rig
    ch = parachute(1.6, ((.95, .95, .92), (.95, .45, .1)), 16, lines_to=(0, 0, -3.6), name='hchute'); ch.parent = rig; ch.location = (0, 0, 4.0)
    kit.key(rig, 1, location=(0, 0, 9.4), rotation_euler=(0, 0, 0)); kit.key(rig, NF, location=(0, 0, 8.6), rotation_euler=(0, 0, math.radians(30)))
    area('k', (3, -4, 11), rig, 140, (1, .8, .55)); area('r', (-3, 4, 10), rig, 160, (.6, .7, 1))
    c1 = cam_move((3.2, -6.0, 10.5), (2.8, -5.2, 9.8), (0, 0, 10.4), 30, (0, 0, 9.8))
    c2 = cam_move((0, -22, 3.5), (0, -20.5, 3.8), (0, 0, 8.5), 34, (0, 0, 8.0))
    cuts((c1, 0), (c2, 2.1))
    overlays.append({'type': 'options', 'items': OPTS, 'pick': 3})
    overlays.append({'type': 'datestamp', 'text': 'TITAN · 14 JAN 2005', 'from': .3})
    overlays.append({'type': 'badge', 'value': '2 h 27 min', 'unit': 'under parachute', 'pos': [.5, .4], 'from': 1.6, 'size': 72})

def s11_fly():                  # "Strap on wings, and scientists think you might even fly." -> loops into the hook
    titan_flight((3.4, -4.4, 14.6), S0A, 1.6)
    overlays.append({'type': 'cta', 'text': 'FOLLOW FOR MORE SCENARIOS', 'pos': (.5, .1)})

[s0_hook, s1_options, s2_count, s3_mars, s4_rover, s5_venus, s6_lander, s7_jupiter, s8_galileo, s9_titan, s10_huygens, s11_fly][idx]()
if idx == 5:     # Venus lower-atmosphere set for the 2nd shot (placed far off to the side of the globe shot)
    g = venus_surface_set((200, 0, 0)); g.scale = (1, 1, 1)
    li = bpy.data.lights.new('vglow', 'AREA'); li.energy = 3000; li.color = (1, .5, .18); li.size = 40
    lo = kit.link(bpy.data.objects.new('vglow', li)); lo.location = (200, 0, 12); lo.rotation_euler = (0, 0, 0)
    d2 = skydiver(.6); d2.location = (200, 0, 3.2)
    kit.key(d2, 1, location=(200, 0, 3.6)); kit.key(d2, NF, location=(200, 0, 2.6))
    area('vk', (202, -3, 6), d2, 40, (1, .7, .4))
    # world stays the starfield for shot 1; the gloom set gets its own big dim-orange backdrop sphere around it
    bpy.ops.mesh.primitive_uv_sphere_add(radius=45, location=(200, 0, 0)); bd = bpy.context.object
    bd.data.materials.append(emit_mat('vsky', (.55, .28, .08), .9)); bd.visible_shadow = False
    for p in bd.data.polygons: p.use_smooth = True
for o in bpy.data.objects:
    for m in getattr(o, 'modifiers', []):
        if m.type == 'SUBSURF' and not o.name.startswith('terrain'): m.render_levels = min(m.render_levels, 1)
os.makedirs(f'{OUT}/s{idx}', exist_ok=True)
json.dump({'frames': NF, 'overlays': overlays}, open(f'{OUT}/s{idx}/meta.json', 'w'))
if mode == 'still':
    fr = float(sys.argv[3]) if len(sys.argv) > 3 else .6
    sc.frame_set(max(1, int(NF * fr))); sc.render.filepath = f'{OUT}/still_{idx}_{fr}.png'; bpy.ops.render.render(write_still=True)
else:
    if os.environ.get('FR'): sc.frame_start, sc.frame_end = map(int, os.environ['FR'].split(','))
    sc.render.image_settings.file_format = 'PNG'; sc.render.filepath = f'{OUT}/s{idx}/f_'; bpy.ops.render.render(animation=True)
