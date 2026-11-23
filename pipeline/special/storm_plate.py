"""What if the Carrington storm hit today: one high-res Cycles still per plate (animated in 2D by storm_anim.py).
python3 storm_plate.py <plate> [res_scale]  -> /home/claude/b3d/storm/plates/<plate>.png
plates: earth_aur / earth_dark (North America at night under a Carrington-size auroral oval, city lights on/off),
        sun (the solar surface with a big sunspot group), observatory (1859 telescope projecting the Sun on a screen),
        cme (Sun + expanding CME bubble, Earth far right, NOT to scale), rockies (aurora over a miners' camp),
        poles (telegraph line under the aurora), desk (telegraph key, sounder, paper tape), grid_on / grid_off
        (high-voltage line over snowy land, town lit / dark), transformer (substation transformer at night), starlink."""
import sys, math, os, random
sys.path.insert(0, '/home/claude/b3d')
import bpy, bmesh, kit
from mathutils import Vector
name = sys.argv[1]; S = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
OUT = '/home/claude/b3d/storm/plates'; os.makedirs(OUT, exist_ok=True)
W, H = int(1080 * S), int(1920 * S)
sc = kit.reset(res=(W, H), samples=int(os.environ.get('SAMPLES', 40)))
sc.cycles.adaptive_threshold = 0.03; sc.cycles.max_bounces = 4

def track(o, target):
    c = o.constraints.new('TRACK_TO'); c.target = target; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'

def look(loc, at, lens=32):
    cam, tgt = kit.camera(loc, at, lens=lens); sc.camera = cam; return cam

def dark_world(col=(0.004, 0.008, 0.02), strength=1.0, stars=False):
    if stars: kit.world(strength=.35); return
    w = bpy.data.worlds.new('night'); sc.world = w; nt, N, L = kit.nodes(w)
    o = N.new('ShaderNodeOutputWorld'); bg = N.new('ShaderNodeBackground'); bg.inputs['Color'].default_value = (*col, 1)
    bg.inputs['Strength'].default_value = strength; L.new(bg.outputs[0], o.inputs['Surface'])

def pt(loc, energy, color=(1, .6, .3), r=.1):
    li = bpy.data.lights.new('pt', 'POINT'); li.energy = energy; li.color = color; li.shadow_soft_size = r
    o = kit.link(bpy.data.objects.new('pt', li)); o.location = loc; return o

def area(loc, at, energy, color=(1, 1, 1), size=3):
    li = bpy.data.lights.new('ar', 'AREA'); li.energy = energy; li.color = color; li.size = size
    o = kit.link(bpy.data.objects.new('ar', li)); o.location = loc
    o.rotation_euler = (Vector(at) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler(); return o

def prim(kind, mat, loc, scale=(1, 1, 1), rot=(0, 0, 0), sub=0, bevel=0.0, **kw):
    getattr(bpy.ops.mesh, 'primitive_' + kind + '_add')(**kw); o = bpy.context.object
    o.location = loc; o.scale = scale; o.rotation_euler = rot; o.data.materials.append(mat)
    if sub or bevel: kit.smooth(o, sub, bevel)
    return o

# ------------------------------------------------------------------ aurora: green lower curtains (~100-250 km), red tops (~250-400 km)
def mat_aurora(name='aurora', strength=6.0, ray_scale=60.0, seed=0.0):
    """additive glow (emission + transparent): green at the bottom fading to red at the top, vertical rays from noise on U"""
    m = bpy.data.materials.new(name); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial')
    uv = N.new('ShaderNodeTexCoord'); sep = N.new('ShaderNodeSeparateXYZ'); L.new(uv.outputs['UV'], sep.inputs[0])
    ramp = N.new('ShaderNodeValToRGB'); cr = ramp.color_ramp
    cr.elements[0].position = 0.0; cr.elements[0].color = (.15, 1.0, .35, 1)
    cr.elements[1].position = 1.0; cr.elements[1].color = (.9, .1, .25, 1)
    e1 = cr.elements.new(.42); e1.color = (.25, 1.0, .4, 1); e2 = cr.elements.new(.7); e2.color = (.8, .25, .3, 1)
    L.new(sep.outputs['Y'], ramp.inputs['Fac'])
    # vertical rays: 1D noise along U (stretched), plus a slow large-scale fold
    comb = N.new('ShaderNodeCombineXYZ'); mu = N.new('ShaderNodeMath'); mu.operation = 'MULTIPLY'; mu.inputs[1].default_value = ray_scale
    L.new(sep.outputs['X'], mu.inputs[0]); L.new(mu.outputs[0], comb.inputs['X']); comb.inputs['Y'].default_value = seed
    nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 1.0; nz.inputs['Detail'].default_value = 6; L.new(comb.outputs[0], nz.inputs['Vector'])
    rays = N.new('ShaderNodeMapRange'); rays.inputs['From Min'].default_value = .38; rays.inputs['From Max'].default_value = .72
    L.new(nz.outputs['Fac'], rays.inputs['Value'])
    # vertical profile: sharp bright lower edge, long fade upward
    prof = N.new('ShaderNodeFloatCurve'); cv = prof.mapping.curves[0]
    cv.points[0].location = (0, 0); cv.points[1].location = (1, 0)
    cv.points.new(.06, 1.0); cv.points.new(.3, .55); cv.points.new(.7, .18)
    prof.mapping.update(); L.new(sep.outputs['Y'], prof.inputs['Value'])
    a = N.new('ShaderNodeMath'); a.operation = 'MULTIPLY'; L.new(rays.outputs[0], a.inputs[0]); L.new(prof.outputs[0], a.inputs[1])
    s = N.new('ShaderNodeMath'); s.operation = 'MULTIPLY'; s.inputs[1].default_value = strength; L.new(a.outputs[0], s.inputs[0])
    e = N.new('ShaderNodeEmission'); L.new(ramp.outputs['Color'], e.inputs['Color']); L.new(s.outputs[0], e.inputs['Strength'])
    tr = N.new('ShaderNodeBsdfTransparent'); add = N.new('ShaderNodeAddShader')
    L.new(e.outputs[0], add.inputs[0]); L.new(tr.outputs[0], add.inputs[1]); L.new(add.outputs[0], o.inputs[0])
    try: m.cycles.emission_sampling = 'NONE'
    except Exception: pass
    return m

def ribbon(points, h0, h1, mat, name='rib'):
    """vertical curtain through a list of base points (Vectors) with 'up' vectors; points = [(base, up), ...]"""
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new(); n = len(points); vs = []
    for k, (b, up) in enumerate(points):
        vs.append((bm.verts.new(b + up * h0), bm.verts.new(b + up * h1)))
    for k in range(n - 1):
        f = bm.faces.new((vs[k][0], vs[k + 1][0], vs[k + 1][1], vs[k][1]))
        for lp, (u, v) in zip(f.loops, ((k / n, 0), ((k + 1) / n, 0), ((k + 1) / n, 1), (k / n, 1))): lp[uvl].uv = (u, v)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); me.materials.append(mat)
    o = kit.link(bpy.data.objects.new(name, me)); o.visible_shadow = False; return o

# ------------------------------------------------------------------ globe plates
R = 4.0; FACE = -95.0
GEO_POLE = (80.8, -72.7)          # geomagnetic north pole (IGRF, mid-2020s)
def oval(spin, gmlat, width_km, top_km, strength, seed, n=480):
    p = kit.latlon(*GEO_POLE, 1.0, FACE).normalized()
    u = p.cross(Vector((0, 0, 1))).normalized(); v = p.cross(u).normalized(); c = math.radians(90 - gmlat)
    pts = []; rng = random.Random(seed)
    for k in range(n + 1):
        th = 2 * math.pi * k / n
        wob = math.radians(1.6 * math.sin(th * 5 + seed) + .8 * math.sin(th * 13 + 2 * seed))
        d = (p * math.cos(c + wob) + (u * math.cos(th) + v * math.sin(th)) * math.sin(c + wob)).normalized()
        pts.append((d * R, d))
    km = R / 6371.0
    o = ribbon(pts, width_km * km, top_km * km, mat_aurora(f'aur{seed}', strength, 220, seed), f'oval{seed}'); o.parent = spin
    return o

def band(spin, lat0, lat1, h_km, strength, n=360):
    """flat diffuse auroral glow (the oval seen from above) between two geomagnetic latitudes, ~h_km up"""
    p = kit.latlon(*GEO_POLE, 1.0, FACE).normalized(); u = p.cross(Vector((0, 0, 1))).normalized(); v = p.cross(u).normalized()
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new(); rows = []
    for j, gl in enumerate((lat0, lat1)):
        c = math.radians(90 - gl); row = []
        for k in range(n):
            th = 2 * math.pi * k / n; d = (p * math.cos(c) + (u * math.cos(th) + v * math.sin(th)) * math.sin(c)).normalized()
            row.append(bm.verts.new(d * (R + h_km * R / 6371)))
        rows.append(row)
    for k in range(n):
        k2 = (k + 1) % n; f = bm.faces.new((rows[0][k], rows[0][k2], rows[1][k2], rows[1][k]))
        for lp, uv in zip(f.loops, ((k / n, 0), ((k + 1) / n, 0), ((k + 1) / n, 1), (k / n, 1))): lp[uvl].uv = uv
    me = bpy.data.meshes.new('band'); bm.to_mesh(me); bm.free()
    m = bpy.data.materials.new('bandm'); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial')
    uv = N.new('ShaderNodeTexCoord'); sep = N.new('ShaderNodeSeparateXYZ'); L.new(uv.outputs['UV'], sep.inputs[0])
    sn = N.new('ShaderNodeMath'); sn.operation = 'SINE'; mu = N.new('ShaderNodeMath'); mu.operation = 'MULTIPLY'; mu.inputs[1].default_value = math.pi
    L.new(sep.outputs['Y'], mu.inputs[0]); L.new(mu.outputs[0], sn.inputs[0])
    nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 14; nz.inputs['Detail'].default_value = 8; L.new(uv.outputs['UV'], nz.inputs['Vector'])
    nz2 = N.new('ShaderNodeMapRange'); nz2.inputs['From Min'].default_value = .4; nz2.inputs['From Max'].default_value = .75; L.new(nz.outputs['Fac'], nz2.inputs['Value'])
    a = N.new('ShaderNodeMath'); a.operation = 'MULTIPLY'; L.new(sn.outputs[0], a.inputs[0]); L.new(nz2.outputs[0], a.inputs[1])
    s_ = N.new('ShaderNodeMath'); s_.operation = 'MULTIPLY'; s_.inputs[1].default_value = strength; L.new(a.outputs[0], s_.inputs[0])
    e = N.new('ShaderNodeEmission'); e.inputs['Color'].default_value = (.2, 1, .4, 1); L.new(s_.outputs[0], e.inputs['Strength'])
    tr = N.new('ShaderNodeBsdfTransparent'); ad = N.new('ShaderNodeAddShader'); L.new(e.outputs[0], ad.inputs[0]); L.new(tr.outputs[0], ad.inputs[1]); L.new(ad.outputs[0], o.inputs[0])
    me.materials.append(m); ob = kit.link(bpy.data.objects.new('band', me)); ob.parent = spin; ob.visible_shadow = False

def globe(lights=True):
    kit.world(strength=.4)
    sun = (.35, 1.0, .25)
    kit.sun_lamp(sun, 3.2)
    root, spin = kit.earth(R, sun, tilt_deg=0, clouds=True, atmo=True, face_lon=FACE)
    if not lights:
        for m in bpy.data.materials:
            if m.name.startswith('earth') and m.node_tree:
                for nd in m.node_tree.nodes:
                    if nd.type == 'MATH' and nd.operation == 'MULTIPLY' and abs(nd.inputs[1].default_value - 2.2) < 1e-6: nd.inputs[1].default_value = .04
    # Carrington-size oval: overhead aurora down to ~40-45 deg geomagnetic latitude (rough, labeled as a visualization)
    oval(spin, 47, 95, 420, 5.5, 1); oval(spin, 52, 100, 380, 4.0, 2); oval(spin, 43, 110, 520, 2.2, 3)
    band(spin, 41, 57, 115, .45)
    tgt = kit.latlon(36, -97, R, FACE)
    look(tgt.normalized() * (R + 7.2) + Vector((0, 0, -1.2)), tgt * .82 + Vector((0, 0, .5)), 34)

def p_earth_aur(): globe(True)
def p_earth_dark(): globe(False)

# ------------------------------------------------------------------ the Sun
def tint(s, col=(1, .62, .22)):
    m = s.data.materials[0]; N, L = m.node_tree.nodes, m.node_tree.links
    t = [n for n in N if n.type == 'TEX_IMAGE'][0]; e = [n for n in N if n.type == 'EMISSION'][0]
    mx = N.new('ShaderNodeMixRGB'); mx.blend_type = 'MULTIPLY'; mx.inputs['Fac'].default_value = 1; mx.inputs[2].default_value = (*col, 1)
    L.new(t.outputs['Color'], mx.inputs[1]); L.new(mx.outputs[0], e.inputs['Color'])

def p_sun():
    dark_world((0, 0, 0))
    s = kit.sun_sphere(6.0, 2.6); tint(s)
    # Carrington's large sunspot group (dark umbra + brown penumbra), on the visible disk
    um = kit.mat_emit('umbra', (.2, .02, .0), .04); pen = kit.mat_emit('penumbra', (.35, .08, .01), .35)
    rng = random.Random(4); c = Vector((-.12, -1, .28)).normalized()
    for k in range(6):
        off = Vector((rng.uniform(-.07, .07), 0, rng.uniform(-.04, .04))); d = (c + off).normalized(); r = rng.uniform(.05, .17)
        for rr, m, h in ((r * 1.8, pen, 6.002), (r, um, 6.004)):
            bpy.ops.mesh.primitive_circle_add(vertices=40, radius=rr, fill_type='NGON'); o = bpy.context.object
            o.location = d * h; o.rotation_euler = d.to_track_quat('Z', 'Y').to_euler(); o.data.materials.append(m)
            o.scale = (1, rng.uniform(.6, 1), 1)
    look(c * 6 + Vector((2.6, -8.2, 1.2)), c * 6 + Vector((.6, 0, -.6)), 38)

# ------------------------------------------------------------------ 1859 observatory: refractor projecting the Sun onto a screen
def p_observatory():
    """Carrington projected an 11-inch image of the Sun from his refractor onto a screen and sketched the spots (Redhill, 1 Sept 1859).
    Dark wooden observatory room, sunbeam through the roof slit down the tube, image on a screen behind the eyepiece."""
    dark_world((.008, .006, .005), .4)
    wood = kit.mat_pbr('wood', 'woodwall'); floor = kit.mat_pbr('wood', 'floor'); floor.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (.12, .06, .03, 1)
    brass = kit.mat_principled('brass', (.85, .62, .28), rough=.28, metal=1); iron = kit.mat_principled('iron', (.06, .06, .065), rough=.5, metal=.7)
    paper = kit.mat_principled('paper', (.92, .88, .76), rough=.8); tubem = kit.mat_principled('tube', (.55, .42, .2), rough=.3, metal=1)
    prim('plane', floor, (0, 0, 0), (12, 12, 1), size=1)
    prim('cube', wood, (0, 5, 4), (8, .1, 4), size=1); prim('cube', wood, (-5, 0, 4), (.1, 8, 4), size=1)
    C = Vector((0, 1.2, 2.5)); d = Vector((.3, .8, .45)).normalized()      # tube axis, pointing up at the Sun
    rot = d.to_track_quat('Z', 'Y').to_euler()
    prim('cylinder', tubem, C, (.12, .12, 1.7), rot, vertices=48, sub=1)
    for k in (-1.5, -.2, 1.0): prim('cylinder', brass, C + d * k, (.135, .135, .04), rot, vertices=48)
    prim('cylinder', brass, C + d * 1.72, (.15, .15, .06), rot, vertices=48)         # objective cell
    eye = C - d * 1.85; prim('cylinder', brass, eye, (.04, .04, .18), rot, vertices=24)
    # mount: pier + polar axis block
    prim('cylinder', iron, (C.x, C.y, .6), (.18, .18, .6), vertices=32); prim('cube', iron, (C.x, C.y, 1.3), (.28, .28, .18), size=1, bevel=.03)
    prim('cylinder', iron, (C.x, C.y, 1.65), (.06, .06, .35), vertices=16)
    # sunbeam down the tube (volume) from a spot light at the roof slit
    sl = C + d * 2.6; li = bpy.data.lights.new('sunspot', 'SPOT'); li.energy = 4000; li.spot_size = math.radians(14); li.spot_blend = .3; li.color = (1, .86, .62)
    lo = kit.link(bpy.data.objects.new('sunspot', li)); lo.location = sl; lo.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler(); li.shadow_soft_size = .1
    vb = prim('cylinder', bpy.data.materials.new('beam'), C + d * 3.0, (.5, .5, 1.6), rot, vertices=24)
    m = vb.data.materials[0]; nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); sv = N.new('ShaderNodeVolumeScatter')
    sv.inputs['Density'].default_value = .6; L.new(sv.outputs[0], o.inputs['Volume'])
    # projection screen behind the eyepiece, facing it, with the bright solar disk and the sunspot group
    sc_c = eye - d * .9; n = d
    scr = prim('cylinder', paper, sc_c, (.55, .55, .008), n.to_track_quat('Z', 'Y').to_euler(), vertices=64)
    prim('cylinder', iron, (sc_c.x, sc_c.y, sc_c.z / 2), (.025, .025, sc_c.z / 2), vertices=12)
    bpy.ops.mesh.primitive_circle_add(vertices=96, radius=.42, fill_type='NGON', location=sc_c + n * .02); disc = bpy.context.object
    disc.rotation_euler = n.to_track_quat('Z', 'Y').to_euler(); disc.data.materials.append(kit.mat_emit('proj', (1, .8, .45), 1.6))
    q = n.to_track_quat('Z', 'Y'); ax = q @ Vector((1, 0, 0)); ay = q @ Vector((0, 1, 0))
    sp = kit.mat_principled('spot', (.03, .02, .01), rough=1); rng = random.Random(2)
    for k in range(8):
        pos = sc_c + n * .024 + ax * (-.12 + rng.uniform(-.06, .06)) + ay * (.1 + rng.uniform(-.035, .035))
        bpy.ops.mesh.primitive_circle_add(vertices=24, radius=rng.uniform(.01, .028), fill_type='NGON', location=pos)
        o2 = bpy.context.object; o2.rotation_euler = disc.rotation_euler; o2.data.materials.append(sp)
    pt(sc_c + n * .5, 20, (1, .85, .6), .3)
    # desk: sketch, ink, oil lamp
    prim('cube', wood, (-1.9, -1.3, .78), (.9, .5, .04), size=1, bevel=.02)
    for x in (-2.7, -1.1):
        for y in (-1.7, -.9): prim('cube', wood, (x, y, .38), (.04, .04, .38), size=1)
    prim('plane', paper, (-1.8, -1.35, .83), (.3, .21, 1), (0, 0, -.15), size=1)
    prim('cylinder', iron, (-1.4, -1.1, .86), (.03, .03, .04), vertices=16)
    prim('cylinder', brass, (-2.5, -1.1, .9), (.07, .07, .08), vertices=24)
    prim('uv_sphere', kit.mat_emit('flame', (1, .55, .15), 40), (-2.5, -1.1, 1.04), (.03, .03, .05))
    pt((-2.5, -1.1, 1.12), 40, (1, .55, .2), .05)
    area((4, -4, 4), (0, 0, 1.5), 60, (.45, .55, 1), 4)
    look(sc_c + Vector((1.7, 2.5, .55)), sc_c + Vector((.35, .45, .05)), 28)

# ------------------------------------------------------------------ CME
def p_cme():
    kit.world(strength=.3)
    s = kit.sun_sphere(6.0, 2.6); s.location = (0, 2, -11.5); tint(s)
    m = bpy.data.materials.new('cme'); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial')
    lw = N.new('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = .5
    tc = N.new('ShaderNodeTexCoord'); nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 2.5; nz.inputs['Detail'].default_value = 10
    nz.inputs['Roughness'].default_value = .62; L.new(tc.outputs['Object'], nz.inputs['Vector'])
    iv = N.new('ShaderNodeMath'); iv.operation = 'ADD'; iv.inputs[1].default_value = 0; L.new(lw.outputs['Facing'], iv.inputs[0])
    f = N.new('ShaderNodeMath'); f.operation = 'POWER'; f.inputs[1].default_value = 2.2; L.new(iv.outputs[0], f.inputs[0])
    mr = N.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value = .35; mr.inputs['From Max'].default_value = .75; L.new(nz.outputs['Fac'], mr.inputs['Value'])
    mul = N.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; L.new(f.outputs[0], mul.inputs[0]); L.new(mr.outputs[0], mul.inputs[1])
    s2 = N.new('ShaderNodeMath'); s2.operation = 'MULTIPLY'; s2.inputs[1].default_value = 2.4; L.new(mul.outputs[0], s2.inputs[0])
    ramp = N.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].color = (1, .18, .04, 1); ramp.color_ramp.elements[1].color = (1, .6, .3, 1)
    L.new(nz.outputs['Fac'], ramp.inputs['Fac'])
    e = N.new('ShaderNodeEmission'); L.new(ramp.outputs['Color'], e.inputs['Color']); L.new(s2.outputs[0], e.inputs['Strength'])
    tr = N.new('ShaderNodeBsdfTransparent'); ad = N.new('ShaderNodeAddShader'); L.new(e.outputs[0], ad.inputs[0]); L.new(tr.outputs[0], ad.inputs[1])
    L.new(ad.outputs[0], o.inputs[0])
    for k, (z, r, sx) in enumerate(((-1.5, 3.4, 1.0), (-.6, 4.0, .95), (-2.8, 2.6, 1.05))):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=r, segments=96, ring_count=48, location=(.3 * k - .3, 1.5, z)); b = bpy.context.object
        b.scale = (sx, 1, 1.12); b.data.materials.append(m); b.visible_shadow = False; kit.smooth(b, 0)
    kit.sun_lamp((0, 0, -1), 3.0)
    root, spin = kit.earth(.7, (0, 0, -1), tilt_deg=23.4, clouds=False, atmo=True, face_lon=-10); root.location = (.8, 0, 8.2)
    look((0, -19, -.5), (0, 0, -.3), 30)

# ------------------------------------------------------------------ night landscapes under the aurora
def sky_curtains(z0=14, rows=((60, 0), (75, 1), (95, 2)), strength=3.5, span=90, scale=1.0):
    for dist, seed in rows:
        pts = []
        for k in range(161):
            x = -span + 2 * span * k / 160; y = dist + 9 * math.sin(k * .07 + seed) + 4 * math.sin(k * .21 + 2 * seed)
            pts.append((Vector((x, y, z0)), Vector((0, 0, 1))))
        ribbon(pts, 0, (34 + 10 * seed) * scale, mat_aurora(f'sky{seed}', strength * (1 - .2 * seed), 30, seed * 3.1), f'cur{seed}')
    area((0, 70, 40), (0, 0, 0), 1500, (.3, 1, .45), 60)

def p_rockies():
    dark_world((.003, .006, .016), 1.0); kit.world(strength=.25)
    t = kit.terrain(200, 34, 1.6, 8, 'snow', 3); t.location = (0, 135, -6)
    g = kit.terrain(70, 1.0, 4, 6, 'grass', 1); g.location = (0, 20, -.8)
    sky_curtains(30, rows=((150, 0), (170, 1), (195, 2)), strength=4.0, span=180)
    kit.sun_lamp((0, 1, .35), .5, (.35, 1, .5))
    # canvas tent + campfire
    canvas = kit.mat_principled('canvas', (.62, .55, .42), rough=.9)
    bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=1.6, depth=2.0, location=(-2.2, 2.5, .4)); tent = bpy.context.object
    tent.rotation_euler = (0, 0, math.radians(30)); tent.data.materials.append(canvas)
    logs = kit.mat_pbr('bark')
    for a in (0, 60, 120):
        prim('cylinder', logs, (.6, 1.0, -.25), (.06, .06, .5), (math.radians(80), 0, math.radians(a)), vertices=12)
    prim('cone', kit.mat_emit('fire', (1, .3, .05), 6), (.6, 1.0, -.05), (.18, .18, .3), vertices=12)
    pt((.6, 1.0, .35), 300, (1, .5, .18), .3)
    prim('cylinder', kit.mat_principled('pan', (.05, .05, .05), rough=.4, metal=.8), (.6, 1.0, .25), (.25, .25, .02), vertices=24)
    look((3.0, -5.5, .9), (-.8, 8, 5.6), 22)

def pole_line(x0=-30, x1=30, y=4.0, step=7.5, h=6.0, wire=True):
    wood = kit.mat_pbr('wood', 'pole'); cu = kit.mat_principled('wire', (.1, .08, .06), rough=.4, metal=.8)
    xs = []; x = x0
    while x <= x1:
        prim('cylinder', wood, (x, y, h / 2), (.13, .13, h / 2), vertices=12)
        prim('cube', wood, (x, y, h - .4), (.06, .9, .08), size=1); xs.append(x); x += step
    if wire:
        for yy in (-.7, .7):
            for a, b in zip(xs[:-1], xs[1:]):
                pts = [Vector((a + (b - a) * t, y + yy, h - .3 - .55 * 4 * t * (1 - t))) for t in [i / 16 for i in range(17)]]
                cd = bpy.data.curves.new('w', 'CURVE'); cd.dimensions = '3D'; cd.bevel_depth = .015; sp = cd.splines.new('POLY'); sp.points.add(len(pts) - 1)
                for p_, q in zip(sp.points, pts): p_.co = (*q, 1)
                ob = kit.link(bpy.data.objects.new('wire', cd)); ob.data.materials.append(cu)

def p_poles():
    dark_world((.003, .006, .016), 1.0); kit.world(strength=.25)
    g = kit.terrain(200, 2.5, 4, 6, 'grass', 2); g.location = (0, 30, -.6)
    sky_curtains(16, strength=3.2)
    pole_line(-40, 40, 4.0, 8.0)
    look((-9, -9.5, 1.6), (6, 12, 6.5), 22)

def p_desk():
    dark_world((.006, .005, .004), .4)
    wood = kit.mat_pbr('wood', 'desk'); brass = kit.mat_principled('brass', (.85, .62, .28), rough=.25, metal=1)
    blk = kit.mat_principled('ebonite', (.02, .02, .02), rough=.35); paper = kit.mat_principled('tape', (.9, .86, .74), rough=.8)
    cu = kit.mat_principled('coil', (.55, .25, .08), rough=.35, metal=1)
    prim('cube', wood, (0, 0, -.05), (3, 2, .05), size=1)
    # key: wooden base, brass lever on a pivot, black knob
    prim('cube', wood, (0, 0, .03), (.45, .16, .03), size=1, bevel=.01)
    prim('cube', brass, (.05, 0, .12), (.36, .03, .02), (0, math.radians(-4), 0), size=1, bevel=.005)
    prim('cylinder', brass, (-.05, 0, .1), (.04, .04, .06), (math.pi / 2, 0, 0), vertices=24)
    prim('cylinder', blk, (.4, 0, .17), (.07, .07, .025), vertices=32, sub=1, bevel=.01)
    prim('cylinder', brass, (.32, 0, .085), (.012, .012, .05), vertices=12)
    # sounder: two coils + armature
    for y in (-.06, .06): prim('cylinder', cu, (-.6, .35 + y, .14), (.045, .045, .1), vertices=24)
    prim('cube', brass, (-.6, .35, .27), (.2, .03, .015), size=1); prim('cube', wood, (-.6, .35, .02), (.28, .16, .02), size=1)
    # paper tape register
    prim('cube', kit.mat_principled('reg', (.3, .25, .2), rough=.5, metal=.3), (.55, .55, .12), (.2, .12, .12), size=1, bevel=.01)
    bpy.ops.mesh.primitive_plane_add(size=1, location=(.0, .62, .002)); tp = bpy.context.object; tp.scale = (1.1, .035, 1)
    tp.rotation_euler = (0, 0, math.radians(-12)); tp.data.materials.append(paper)
    # window behind with the aurora
    prim('plane', kit.mat_emit('win', (.1, .55, .25), .35), (0, 2.4, 1.2), (2.2, 1, 1.4), (math.pi / 2, 0, 0), size=1)
    prim('cube', wood, (0, 2.38, 1.2), (.04, .02, 1.4), size=1); prim('cube', wood, (0, 2.38, 1.2), (2.2, .02, .04), size=1)
    area((0, 2.2, 1.4), (0, 0, 0), 40, (.3, 1, .5), 2.5)
    prim('cylinder', brass, (-1.1, -.2, .12), (.09, .09, .12), vertices=24)
    prim('uv_sphere', kit.mat_emit('flame', (1, .55, .15), 40), (-1.1, -.2, .3), (.03, .03, .055))
    pt((-1.1, -.2, .4), 30, (1, .55, .2), .05); area((.6, -.6, 1.2), (.1, .1, .1), 8, (1, .75, .5), .8)
    cam = look((.7, -.95, .55), (.1, .12, .1), 42); cam.data.dof.use_dof = True; cam.data.dof.focus_distance = 1.15; cam.data.dof.aperture_fstop = 2.0

# ------------------------------------------------------------------ the modern grid
def lattice_tower(x, y, h=24.0, mat=None):
    """high-voltage lattice tower: 4 tapered legs, cross-bracing, two cross-arms with insulator strings"""
    legs = []
    def strut(a, b, r=.06):
        a, b = Vector(a), Vector(b); d = b - a
        bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=r, depth=d.length, location=(a + b) / 2); o = bpy.context.object
        o.rotation_euler = d.to_track_quat('Z', 'Y').to_euler(); o.data.materials.append(mat)
    w0, w1 = 2.6, .7
    lv = [0, h * .25, h * .5, h * .72, h]
    hw = lambda z: w0 + (w1 - w0) * z / h
    for sx, sy in ((1, 1), (1, -1), (-1, -1), (-1, 1)):
        for z0, z1 in zip(lv[:-1], lv[1:]): strut((x + sx * hw(z0), y + sy * hw(z0), z0), (x + sx * hw(z1), y + sy * hw(z1), z1), .09)
    for z0, z1 in zip(lv[:-1], lv[1:]):
        for (ax, ay), (bx, by) in (((1, 1), (1, -1)), ((1, -1), (-1, -1)), ((-1, -1), (-1, 1)), ((-1, 1), (1, 1))):
            strut((x + ax * hw(z0), y + ay * hw(z0), z0), (x + bx * hw(z1), y + by * hw(z1), z1), .045)
            strut((x + bx * hw(z0), y + by * hw(z0), z0), (x + ax * hw(z1), y + ay * hw(z1), z1), .045)
    arms = []
    for za, L_ in ((h * .72, 7.0), (h * .9, 5.2)):
        for sy in (1, -1): strut((x, y + sy * .6, za), (x, y + sy * L_, za), .08); strut((x, y + sy * .6, za - 1.0), (x, y + sy * L_, za), .05)
        for sy in (1, -1):
            strut((x, y + sy * L_, za), (x, y + sy * L_, za - 2.0), .07); arms.append((y + sy * L_, za - 2.0))
    return arms

def grid(lit=True):
    dark_world((.004, .007, .016), 1.0); kit.world(strength=.3)
    t = kit.terrain(300, 1.2, 5, 6, 'snow', 4); t.location = (0, 60, -.5)
    steel = kit.mat_principled('steel', (.45, .46, .48), rough=.45, metal=1); cable = kit.mat_principled('cable', (.08, .08, .09), rough=.4, metal=.8)
    xs = [-75, -25, 25, 75]; arms = None
    for x in xs: arms = lattice_tower(x, 12, 26, steel)
    for yy, zz in arms:
        for a, b in zip(xs[:-1], xs[1:]):
            pts = [Vector((a + (b - a) * t_, yy, zz - 5.5 * 4 * t_ * (1 - t_))) for t_ in [i / 24 for i in range(25)]]
            cd = bpy.data.curves.new('c', 'CURVE'); cd.dimensions = '3D'; cd.bevel_depth = .05; sp = cd.splines.new('POLY'); sp.points.add(len(pts) - 1)
            for p_, q in zip(sp.points, pts): p_.co = (*q, 1)
            ob = kit.link(bpy.data.objects.new('cable', cd)); ob.data.materials.append(cable)
    # distant town: warm windows and streetlights scattered along a valley
    rng = random.Random(8); lm = kit.mat_emit('town', (1, .7, .35), 60 if lit else 0.0); hm = kit.mat_principled('house', (.12, .1, .09), rough=.8)
    for k in range(260):
        x = rng.uniform(-40, 60); y = rng.uniform(28, 70); z = .1
        if rng.random() < .35:
            prim('cube', hm, (x, y, .8), (rng.uniform(1, 2.5), rng.uniform(1, 2.5), .9), size=1)
        prim('uv_sphere', lm, (x, y - 1.3, rng.uniform(.6, 2.2)), (.25, .25, .25), segments=8, ring_count=6)
    if lit:
        for k in range(12): pt((rng.uniform(-35, 55), rng.uniform(30, 68), 5), 5000, (1, .65, .35), 2)
    kit.sun_lamp((.2, .6, .3), .25, (.6, .7, 1))     # moonlight on the snow
    sky_curtains(30, rows=((180, 0), (200, 1)), strength=2.2, span=220, scale=1.6)
    look((-36, -4, 7.0), (0, 45, 5), 22)

def p_grid_on(): grid(True)
def p_grid_off(): grid(False)

def p_transformer():
    dark_world((.004, .006, .014), 1.0); kit.world(strength=.25)
    con = kit.mat_pbr('concrete'); grey = kit.mat_principled('tank', (.32, .36, .34), rough=.55, metal=.6)
    por = kit.mat_principled('porcelain', (.42, .18, .1), rough=.15, coat=.6); cu = kit.mat_pbr('copper')
    prim('cube', con, (0, 0, -.25), (28, 28, .5), size=1)
    prim('cube', grey, (0, 0, 2.2), (5.2, 3.2, 4.4), size=1, bevel=.08)                       # main tank
    prim('cube', grey, (0, 0, 4.5), (4.6, 2.6, .2), size=1, bevel=.05)                         # lid
    prim('cylinder', grey, (-1.0, -1.0, 5.6), (.5, .5, 1.6), (0, math.pi / 2, 0), vertices=32, sub=1)   # conservator tank
    for x in (-2.2, .2): prim('cylinder', grey, (x, -1.0, 5.0), (.08, .08, .5), vertices=12)
    for k in range(12):   # radiator fins on both sides
        for sy in (1, -1): prim('cube', grey, (-2.3 + k * .42, sy * 2.1, 2.2), (.06, 1.0, 3.4), size=1)
    for k, x in enumerate((-1.4, 0, 1.4)):    # HV bushings: stacked porcelain sheds + copper caps
        for j in range(9): prim('cylinder', por, (x, .4, 4.9 + j * .32), (.28 - .01 * j, .28 - .01 * j, .06), vertices=32, sub=0)
        prim('cylinder', por, (x, .4, 6.4), (.14, .14, 1.5), vertices=24)
        prim('cylinder', cu, (x, .4, 8.0), (.18, .18, .12), vertices=24)
    for k, x in enumerate((-1.2, 0, 1.2)):
        for j in range(5): prim('cylinder', por, (x, -.8, 4.9 + j * .3), (.2, .2, .05), vertices=24)
    # fence + floodlights
    steel = kit.mat_principled('fence', (.4, .4, .42), rough=.5, metal=1)
    for x in range(-10, 11, 2): prim('cylinder', steel, (x, -7, 1.2), (.04, .04, 1.2), vertices=8)
    prim('cube', steel, (0, -7, 2.3), (20, .04, .04), size=1)
    area((-8, -6, 9), (0, 0, 3), 900, (1, .7, .4), 2); area((7, 4, 7), (0, 0, 3), 400, (.5, .65, 1), 5)
    sky_curtains(30, rows=((90, 0), (110, 1)), strength=2.0, span=150)
    look((7.5, -9.5, 1.4), (-.3, 0, 4.6), 24)

def p_starlink():
    kit.world(strength=.4); sun = (-.4, -.5, .75)
    kit.sun_lamp(sun, 4.0)
    root, spin = kit.earth(6.0, sun, tilt_deg=0, clouds=True, atmo=True, face_lon=-60); root.location = (0, 0, -6.6)
    panel = kit.mat_principled('bus', (.55, .56, .6), rough=.3, metal=.8); cell = kit.mat_panel('cells', (.02, .04, .16))
    rng = random.Random(3)
    panel = kit.mat_principled('bus', (.8, .8, .82), rough=.25, metal=1)
    for k in range(13):   # a fresh "train" of flat-panel satellites just after deployment (ENLARGED, not to scale)
        t = k / 12; x = -3.0 + 6.4 * t; z = .75 - .35 * t + .05 * math.sin(k * 1.7); y = .6 + 1.6 * t
        r = kit.link(bpy.data.objects.new('sat', None)); r.location = (x, y, z); r.rotation_euler = (rng.uniform(-.3, .3), rng.uniform(-.2, .2), rng.uniform(-.4, .4))
        b = prim('cube', panel, (0, 0, 0), (.4, .25, .04), size=1, bevel=.01); b.parent = r
        a = prim('cube', cell, (.0, .62, .0), (.3, .9, .008), size=1); a.parent = r
        b.visible_shadow = False; a.visible_shadow = False
    look((-.8, -3.6, 1.05), (.2, 1.2, .35), 28)

P = {k[2:]: v for k, v in globals().items() if k.startswith('p_')}
P[name]()
for mt in bpy.data.materials:
    try: mt.cycles.emission_sampling = 'NONE'
    except Exception: pass
    if mt.node_tree:
        for nd in mt.node_tree.nodes:
            if nd.type == 'TEX_IMAGE': nd.interpolation = 'Linear'
sc.render.filepath = f'{OUT}/{name}.png'; bpy.ops.render.render(write_still=True)
print('plate', name, 'done')
