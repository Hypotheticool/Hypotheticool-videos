"""3D Short (what-if): What if a nuke went off in space?  Usage: python3 nuke3d.py <scene> still|anim [frac]
Facts: arXiv 2611.09827 (1 Mt at 500 km over 20S 35W; ~3% at t=0, 25% day 1, 78% day 3, 98% week 1 of >13,000 LEO sats)
and Starfish Prime (1.4 Mt, 400 km over Johnston Atoll, 8 Jul 1962 Hawaii time). Earth radius here R = 4 units (1 unit ~ 1,593 km)."""
import sys, math, json, os, random
sys.path.insert(0, '/home/claude/b3d')
import bpy, bmesh, kit
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

CFG = json.load(open('/home/claude/b3d/nuke/topic.json'))
FPS = 24; DURS = CFG['durs']; PAD = 0.5; OUT = CFG['root']
idx, mode = int(sys.argv[1]), sys.argv[2]
D = DURS[idx]; NF = int(math.ceil((D + PAD) * FPS))
sc = kit.reset(res=(540, 960), samples=4)
sc.render.use_persistent_data = True; sc.cycles.adaptive_threshold = 0.06
try:
    sc.cycles.denoising_quality = 'FAST'; sc.cycles.denoising_prefilter = 'FAST'
except Exception: pass
sc.cycles.max_bounces = 3; sc.cycles.diffuse_bounces = 1; sc.cycles.glossy_bounces = 1; sc.cycles.transparent_max_bounces = 8
sc.frame_start, sc.frame_end = 1, NF
if os.environ.get('SAMP'): sc.cycles.samples = int(os.environ['SAMP'])
if os.environ.get('NODN'): sc.cycles.use_denoising = False
F = lambda sec: 1 + int(round((sec + .35) * FPS))
overlays = []
R = 4.0; KM = R / 6371.0
YEL, WHITE, GREY = (255, 222, 40), (255, 255, 255), (200, 210, 230)
ALIVE, DEAD = (.55, .85, 1.0, 1), (1.0, .12, .03, 1)
BURST_LAT, BURST_LON = -20.0, -35.0
FACE = -35.0          # South Atlantic faces the camera side (-Y)

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

def kf(sock, frame, value):
    sock.default_value = value; sock.keyframe_insert('default_value', frame=frame)

def emit_mat(name, color, strength, alpha=1.0):
    m = bpy.data.materials.new(name); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial')
    e = N.new('ShaderNodeEmission'); e.name = 'em'; e.inputs['Color'].default_value = (*color[:3], 1); e.inputs['Strength'].default_value = strength
    tr = N.new('ShaderNodeBsdfTransparent'); mx = N.new('ShaderNodeMixShader'); mx.name = 'mix'; mx.inputs['Fac'].default_value = alpha
    L.new(tr.outputs[0], mx.inputs[1]); L.new(e.outputs[0], mx.inputs[2]); L.new(mx.outputs[0], o.inputs[0])
    return m

def P(lat, lon, h_km=0.0):
    return kit.latlon(lat, lon, R, FACE, h_km * KM)

def earth(face=FACE, clouds=True, sun=(1, -.55, .35), spin_deg=1.5):
    kit.world(strength=.45); kit.sun_lamp(sun, 3.6)
    root, sp = kit.earth(R, sun, tilt_deg=0, clouds=clouds and not os.environ.get('NOCLOUD'), atmo=True, face_lon=face)
    kit.key(sp, 1, rotation_euler=(0, 0, 0)); kit.key(sp, NF, rotation_euler=(0, 0, math.radians(spin_deg)))
    return root, sp

# ------------------------------------------------------------------ satellites (one shared mesh, status via object color)
SAT_MAT = None
def sat_mat():
    global SAT_MAT
    if SAT_MAT: return SAT_MAT
    m = bpy.data.materials.new('sat'); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial')
    bs = N.new('ShaderNodeBsdfPrincipled'); bs.inputs['Base Color'].default_value = (.5, .52, .56, 1); bs.inputs['Metallic'].default_value = .6
    bs.inputs['Roughness'].default_value = .35
    oi = N.new('ShaderNodeObjectInfo'); L.new(oi.outputs['Color'], bs.inputs['Emission Color']); bs.inputs['Emission Strength'].default_value = 4
    L.new(bs.outputs[0], o.inputs[0]); SAT_MAT = m; return m

SAT_MESH = None
def sat_mesh():
    """generic LEO satellite: box bus + two solar wings (blue cells) + small dish; ~1 unit long before scaling"""
    global SAT_MESH
    if SAT_MESH: return SAT_MESH
    bm = bmesh.new()
    def box(c, s):
        r = bmesh.ops.create_cube(bm, size=1.0)
        for v in r['verts']: v.co = Vector((v.co.x * s[0] + c[0], v.co.y * s[1] + c[1], v.co.z * s[2] + c[2]))
    box((0, 0, 0), (.22, .22, .3)); box((0, 0, .2), (.06, .06, .12))
    for sgn in (-1, 1): box((sgn * .42, 0, 0), (.55, .01, .2))
    me = bpy.data.meshes.new('sat'); bm.to_mesh(me); bm.free(); me.materials.append(sat_mat()); SAT_MESH = me; return me

def swarm(*a, **k):
    if os.environ.get("NOSWARM"): return []
    return _swarm(*a, **k)

def _swarm(n=260, size=.06, h_lo=450, h_hi=1200, seed=5, prog=None, spin=8.0, near=None):
    """n satellites on random orbit planes (ENLARGED: real ones are meters across). prog = [(sec, fraction_disabled), ...]
    each satellite gets a fixed random threshold u (same seed every scene) and turns red when the fraction passes u."""
    rng = random.Random(seed); sats = []
    planes = []
    for k in range(10):
        e = kit.link(bpy.data.objects.new(f'plane{k}', None))
        e.rotation_euler = (math.radians(rng.uniform(40, 100)) * rng.choice((-1, 1)), 0, math.radians(rng.uniform(0, 360)))
        sp = kit.link(bpy.data.objects.new(f'pspin{k}', None), e)
        w = rng.uniform(.6, 1.2) * spin * rng.choice((-1, 1))
        kit.key(sp, 1, rotation_euler=(0, 0, 0)); kit.key(sp, NF, rotation_euler=(0, 0, math.radians(w)))
        planes.append(sp)
    for k in range(n):
        u = rng.random(); a = rng.uniform(0, 2 * math.pi); h = rng.uniform(h_lo, h_hi) * KM; jit = rng.uniform(-.06, .06)
        o = kit.link(bpy.data.objects.new(f'sat{k}', sat_mesh())); o.parent = planes[k % len(planes)]
        rr = R + h; o.location = (rr * math.cos(a), rr * math.sin(a), jit * rr)
        o.rotation_euler = (rng.uniform(0, 6.3), rng.uniform(0, 6.3), rng.uniform(0, 6.3)); o.scale = (size,) * 3
        o.visible_shadow = False
        dead_at = None
        if prog:
            for (t0, f0), (t1, f1) in zip(prog[:-1], prog[1:]):
                if f0 < u <= f1: dead_at = t0 + (t1 - t0) * (u - f0) / max(f1 - f0, 1e-6); break
            if prog[0][1] >= u: dead_at = -1
        if dead_at is None:
            o.color = ALIVE
        elif dead_at < 0:
            o.color = DEAD
        else:
            fr = F(dead_at); o.color = ALIVE; o.keyframe_insert('color', frame=max(1, fr - 1))
            o.color = (1, .9, .6, 1); o.keyframe_insert('color', frame=fr + 1)      # flicker as it dies
            o.color = DEAD; o.keyframe_insert('color', frame=fr + 4)
        sats.append(o)
    return sats

# ------------------------------------------------------------------ the blast
def glow_mat(name, color, strength, falloff=1.6, noise=True):
    """soft glowing ball: bright core fading to a transparent edge (no hard disc). returns (mat, fade_node, color_socket)"""
    m = bpy.data.materials.new(name); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial')
    e = N.new('ShaderNodeEmission'); e.inputs['Color'].default_value = (*color[:3], 1)
    tr = N.new('ShaderNodeBsdfTransparent'); mx = N.new('ShaderNodeMixShader')
    lw = N.new('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = .5
    inv = N.new('ShaderNodeMath'); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1; L.new(lw.outputs['Facing'], inv.inputs[1])
    pw = N.new('ShaderNodeMath'); pw.operation = 'POWER'; pw.inputs[1].default_value = abs(falloff)
    L.new((lw.outputs['Facing'] if falloff < 0 else inv.outputs[0]), pw.inputs[0])
    inv = pw; src = pw.outputs[0]
    if noise:
        tc = N.new('ShaderNodeTexCoord'); nz = kit._noise(N, L, tc.outputs['Object'], 3.0, 6, .6)
        mr = N.new('ShaderNodeMapRange'); mr.inputs['To Min'].default_value = .55; mr.inputs['To Max'].default_value = 1.25; L.new(nz.outputs['Fac'], mr.inputs['Value'])
        mm = N.new('ShaderNodeMath'); mm.operation = 'MULTIPLY'; L.new(inv.outputs[0], mm.inputs[0]); L.new(mr.outputs[0], mm.inputs[1]); src = mm.outputs[0]
    geo = N.new('ShaderNodeNewGeometry'); bf = N.new('ShaderNodeMath'); bf.operation = 'SUBTRACT'; bf.inputs[0].default_value = 1
    L.new(geo.outputs['Backfacing'], bf.inputs[1]); fm = N.new('ShaderNodeMath'); fm.operation = 'MULTIPLY'; L.new(src, fm.inputs[0]); L.new(bf.outputs[0], fm.inputs[1])
    fade = N.new('ShaderNodeMath'); fade.operation = 'MULTIPLY'; fade.inputs[1].default_value = 1.0; L.new(fm.outputs[0], fade.inputs[0])
    st = N.new('ShaderNodeMath'); st.operation = 'MULTIPLY'; st.inputs[1].default_value = strength; L.new(fade.outputs[0], st.inputs[0])
    cl = N.new('ShaderNodeClamp'); L.new(fade.outputs[0], cl.inputs['Value'])
    L.new(st.outputs[0], e.inputs['Strength']); L.new(cl.outputs[0], mx.inputs['Fac'])
    L.new(tr.outputs[0], mx.inputs[1]); L.new(e.outputs[0], mx.inputs[2]); L.new(mx.outputs[0], o.inputs[0])
    return m, fade.inputs[1], e.inputs['Color']

def glow_ball(loc, r, mat, name):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, segments=48, ring_count=24, location=loc); s = bpy.context.object; s.name = name
    s.data.materials.append(mat); s.visible_shadow = False
    for p in s.data.polygons: p.use_smooth = True
    return s

def burst(loc, t0=-1.0, r_max=1.2, strength=30, life=4.0, name='burst', light=1200):
    """prompt flash in vacuum: a white-hot core inside a soft expanding glow that cools to orange and fades,
    plus a faint X-ray shell racing outward (stylized). t0 < 0 = already going at frame 1 (hook)."""
    a, b = (1, F(t0 + life)) if t0 < 0 else (F(t0), F(t0 + life))
    m1, f1, c1 = glow_mat(name + 'c', (1, .97, .9), strength * 2.5, 1.5, False)
    core = glow_ball(loc, 1, m1, name + 'core')
    m2, f2, c2 = glow_mat(name + 'g', (1, .8, .55), strength, 3.5, True)
    halo = glow_ball(loc, 1, m2, name + 'halo')
    m3, f3, c3 = glow_mat(name + 's', (.7, .82, 1), 3.0, -4.0, False)
    shell = glow_ball(loc, 1, m3, name + 'shell')
    def onoff(sock, peak, end_val):
        if t0 >= 0: kf(sock, 1, 0.0); kf(sock, a, 0.0); kf(sock, a + 2, peak)
        else: kf(sock, 1, peak)
        kf(sock, b, end_val)
    start = .35 if t0 < 0 else .02
    for o, r0, r1 in ((core, r_max * (.3 if t0 < 0 else .04), r_max * .3), (halo, r_max * start, r_max), (shell, r_max * (1.2 if t0 < 0 else .05), r_max * 6)):
        kit.key(o, 1, scale=(r0,) * 3)
        if t0 >= 0: kit.key(o, a, scale=(r0,) * 3)
    kit.key(core, b, scale=(r_max * .3,) * 3); kit.key(halo, b, scale=(r_max,) * 3)
    kit.key(shell, (a if t0 >= 0 else 1) + int(2.0 * FPS), scale=(r_max * 6,) * 3)
    onoff(f1, 1.0, 0.15); onoff(f2, 1.0, 0.25)
    if t0 >= 0: kf(f3, 1, 0.0); kf(f3, a, 0.0); kf(f3, a + 2, .8)
    else: kf(f3, 1, .6)
    kf(f3, (a if t0 >= 0 else 1) + int(2.0 * FPS), 0.0)
    kf(c2, a if t0 >= 0 else 1, (1, .85, .6, 1)); kf(c2, b, (1, .35, .08, 1))
    li = bpy.data.lights.new(name + 'L', 'POINT'); li.color = (1, .85, .65); li.shadow_soft_size = .3
    lo = kit.link(bpy.data.objects.new(name + 'L', li)); lo.location = loc
    if t0 < 0: kit.key(li, 1, energy=light)
    else: kit.key(li, 1, energy=0); kit.key(li, a, energy=0); kit.key(li, a + 2, energy=light * 1.4)
    kit.key(li, b, energy=light * .1)
    return halo, lo

# ------------------------------------------------------------------ magnetic field (dipole) and trapped electrons
def field_line(Lshell, lon_deg, tilt=10.0, n=80):
    """dipole field line r = L*R*cos^2(lat), in a meridian plane at lon_deg (geomagnetic axis tilted ~10 deg)"""
    pts = []
    lim = math.degrees(math.acos(math.sqrt(1 / Lshell))) * .995
    for k in range(n + 1):
        la = math.radians(-lim + 2 * lim * k / n); r = Lshell * R * math.cos(la) ** 2
        p = Vector((r * math.cos(la), 0, r * math.sin(la)))
        p.rotate(Vector((0, 0, 1)).rotation_difference(Vector((0, 0, 1))))
        pts.append(p)
    rot_lon = math.radians(lon_deg)
    out = []
    for p in pts:
        q = Vector((p.x * math.cos(rot_lon), p.x * math.sin(rot_lon), p.z))
        q.rotate(__import__('mathutils').Euler((math.radians(tilt), 0, 0)))
        out.append(q)
    return out

def curve_obj(pts, name, width=.006, color=(.25, .5, 1), strength=2.0, alpha=.6):
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = width; cu.bevel_resolution = 2
    sp = cu.splines.new('POLY'); sp.points.add(len(pts) - 1)
    for p, v in zip(sp.points, pts): p.co = (v.x, v.y, v.z, 1)
    ob = kit.link(bpy.data.objects.new(name, cu)); ob.data.materials.append(emit_mat(name, color, strength, alpha)); ob.visible_shadow = False
    return ob

def field(n_lon=10, shells=(1.25, 1.55, 2.0), strength=1.6, alpha=.5):
    lines = []
    for Ls in shells:
        for k in range(n_lon):
            lines.append(curve_obj(field_line(Ls, k * 360 / n_lon), f'fl{Ls}_{k}', .005, (.2, .45, 1), strength, alpha))
    return lines

def electrons(n=70, shells=(1.12, 1.25, 1.4), seed=3, t_start=0.0, strength=14, drift=40):
    """electrons bouncing pole-to-pole along field lines while drifting in longitude (what trapped particles really do;
    sizes/speeds stylized)"""
    rng = random.Random(seed); m = emit_mat('e', (.3, .95, 1), strength, 1.0)
    for k in range(n):
        Ls = rng.choice(shells); lon = rng.uniform(0, 360)
        path = field_line(Ls, 0, 10, 120)
        cu = bpy.data.curves.new('ep', 'CURVE'); cu.dimensions = '3D'; sp = cu.splines.new('POLY'); sp.points.add(len(path) - 1)
        for p, v in zip(sp.points, path): p.co = (v.x, v.y, v.z, 1)
        cu.use_path = True; cu.path_duration = NF
        po = kit.link(bpy.data.objects.new('ep', cu))
        kit.key(po, 1, rotation_euler=(0, 0, math.radians(lon))); kit.key(po, NF, rotation_euler=(0, 0, math.radians(lon + drift * rng.uniform(.5, 1.5))))
        bpy.ops.mesh.primitive_uv_sphere_add(radius=.025, segments=8, ring_count=6); e = bpy.context.object; e.data.materials.append(m); e.visible_shadow = False
        c = e.constraints.new('FOLLOW_PATH'); c.target = po; c.use_fixed_location = True
        ph = rng.random(); per = rng.uniform(1.0, 1.8)
        for fr in range(1, NF + 1, 3):
            t = (fr - 1) / FPS / per + ph; tri = abs((t % 2) - 1)       # bounce between mirror points
            c.offset_factor = .08 + .84 * tri; c.keyframe_insert('offset_factor', frame=fr)
        t0 = F(t_start) if t_start > 0 else 1
        kit.key(e, 1, scale=(0.001 if t_start > 0 else 1,) * 3)
        if t_start > 0: kit.key(e, t0 + int(rng.uniform(0, 1.0) * FPS), scale=(.001,) * 3); kit.key(e, t0 + int(rng.uniform(1.0, 1.6) * FPS), scale=(1,) * 3)

def belt(alpha=.35, strength=3.0, t_in=0.0, color=(1, .35, .6)):
    """artificial radiation belt: a hazy glowing volume (emission-only volume, noise-modulated) around the magnetic
    equator, L ~1.06-1.4 (radiation is invisible; stylized)"""
    objs = []
    sc.cycles.volume_step_rate = 6.0; sc.cycles.volume_max_steps = 64
    bpy.ops.mesh.primitive_torus_add(major_radius=1.22 * R, minor_radius=.17 * R, major_segments=96, minor_segments=24, rotation=(math.radians(10), 0, 0))
    t = bpy.context.object; t.visible_shadow = False; t.scale = (1, 1, .7)
    m = bpy.data.materials.new('belt'); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial')
    tc = N.new('ShaderNodeTexCoord'); nz = kit._noise(N, L, tc.outputs['Object'], .9, 5, .6)
    mr = N.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value = .35; mr.inputs['From Max'].default_value = .75; L.new(nz.outputs['Fac'], mr.inputs['Value'])
    # density falls off toward the tube's edge: distance from the tube centerline
    sep = N.new('ShaderNodeSeparateXYZ'); L.new(tc.outputs['Object'], sep.inputs[0])
    xy = N.new('ShaderNodeCombineXYZ'); L.new(sep.outputs['X'], xy.inputs['X']); L.new(sep.outputs['Y'], xy.inputs['Y'])
    ln = N.new('ShaderNodeVectorMath'); ln.operation = 'LENGTH'; L.new(xy.outputs[0], ln.inputs[0])
    d1 = N.new('ShaderNodeMath'); d1.operation = 'SUBTRACT'; L.new(ln.outputs['Value'], d1.inputs[0]); d1.inputs[1].default_value = 1.22 * R
    cz = N.new('ShaderNodeCombineXYZ'); L.new(d1.outputs[0], cz.inputs['X']); L.new(sep.outputs['Z'], cz.inputs['Y'])
    l2 = N.new('ShaderNodeVectorMath'); l2.operation = 'LENGTH'; L.new(cz.outputs[0], l2.inputs[0])
    fo = N.new('ShaderNodeMapRange'); fo.inputs['From Min'].default_value = 0; fo.inputs['From Max'].default_value = .17 * R
    fo.inputs['To Min'].default_value = 1; fo.inputs['To Max'].default_value = 0; L.new(l2.outputs['Value'], fo.inputs['Value'])
    m1 = N.new('ShaderNodeMath'); m1.operation = 'MULTIPLY'; L.new(mr.outputs[0], m1.inputs[0]); L.new(fo.outputs[0], m1.inputs[1])
    m2 = N.new('ShaderNodeMath'); m2.operation = 'MULTIPLY'; L.new(m1.outputs[0], m2.inputs[0]); m2.inputs[1].default_value = strength * .12
    e = N.new('ShaderNodeEmission'); e.inputs['Color'].default_value = (*color, 1); L.new(m2.outputs[0], e.inputs['Strength'])
    L.new(e.outputs[0], o.inputs['Volume'])
    if t_in > 0: kf(m2.inputs[1], 1, 0.0); kf(m2.inputs[1], F(t_in), 0.0); kf(m2.inputs[1], F(t_in + 1.5), strength * .12)
    t.data.materials.append(m); objs.append(t)
    return objs

def screen(cam, p):
    bpy.context.view_layer.update(); v = world_to_camera_view(sc, cam, Vector(p)); return (round(v.x, 3), round(1 - v.y, 3))

# ------------------------------------------------------------------ props
def telstar(size=1.0):
    """Telstar 1 (Bell Labs, 1962): 0.88 m 72-faceted sphere covered in solar cells, with a belt of small antenna
    apertures around the middle and a helical command antenna on top"""
    root = kit.link(bpy.data.objects.new('telstar', None))
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=.5); b = bpy.context.object; b.parent = root
    cells = kit.mat_panel('tcells', (.03, .06, .22)) if hasattr(kit, 'mat_panel') else kit.mat_principled('tcells', (.03, .06, .2), rough=.25)
    b.data.materials.append(cells)
    for p in b.data.polygons: p.use_smooth = False
    met = kit.mat_principled('tmetal', (.8, .8, .82), rough=.25, metal=1)
    bpy.ops.mesh.primitive_cylinder_add(radius=.505, depth=.12, vertices=72); band = bpy.context.object; band.parent = root; band.data.materials.append(met)
    dark = kit.mat_principled('tdark', (.05, .05, .06), rough=.4)
    for k in range(36):
        a = 2 * math.pi * k / 36; bpy.ops.mesh.primitive_cube_add(size=1, location=(.51 * math.cos(a), .51 * math.sin(a), 0))
        c = bpy.context.object; c.scale = (.018, .03, .07); c.rotation_euler = (0, 0, a); c.data.materials.append(dark); c.parent = root
    # helical antenna on top
    pts = [Vector((.05 * math.cos(t * .7), .05 * math.sin(t * .7), .5 + t * .012)) for t in range(30)]
    cu = bpy.data.curves.new('helix', 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = .006; sp = cu.splines.new('POLY'); sp.points.add(len(pts) - 1)
    for p, v in zip(sp.points, pts): p.co = (v.x, v.y, v.z, 1)
    h = kit.link(bpy.data.objects.new('helix', cu)); h.data.materials.append(met); h.parent = root
    root.scale = (size,) * 3; return root

def warhead(size=1.0):
    """stylized warhead/re-entry vehicle: dark blunt cone with a ring seam (no real design details)"""
    root = kit.link(bpy.data.objects.new('wh', None))
    bpy.ops.mesh.primitive_cone_add(radius1=.28, radius2=.06, depth=1.0, vertices=64, location=(0, 0, .5)); c = bpy.context.object
    c.data.materials.append(kit.mat_principled('rv', (.12, .12, .13), rough=.35, metal=.4)); kit.smooth(c, 1); c.parent = root
    bpy.ops.mesh.primitive_uv_sphere_add(radius=.06, location=(0, 0, 1.0)); t = bpy.context.object; t.data.materials.append(c.data.materials[0]); t.parent = root
    bpy.ops.mesh.primitive_cylinder_add(radius=.285, depth=.12, vertices=64, location=(0, 0, -.04)); b = bpy.context.object
    b.data.materials.append(kit.mat_principled('rvb', (.3, .3, .32), rough=.3, metal=.8)); b.parent = root
    li = bpy.data.lights.new('blink', 'POINT'); li.color = (1, .2, .1); lo = kit.link(bpy.data.objects.new('blink', li), root); lo.location = (.3, 0, .2)
    for fr in range(1, NF + 1, 12): kit.key(li, fr, energy=8); kit.key(li, fr + 3, energy=0)
    root.scale = (size,) * 3; return root

def iss(size=.6):
    return kit.nasa_model('International Space Station (ISS) (B)', size, 'X')

# ======================================================================= scenes
BURST = P(BURST_LAT, BURST_LON, 500)
S0A, S0B = (2.2, -9.0, -.9), (1.7, -8.0, -.8)
def s0_hook():                  # "One bomb could kill nearly every satellite."
    earth(sun=(.6, .8, .2))        # night-side South Atlantic: the flash is the main light
    burst(BURST, t0=-.6, r_max=.5, strength=60, life=3.2)
    swarm(240, .05, 350, 1300, prog=[(0, .0), (.2, .02), (D + .5, .2)], spin=10)
    c1 = cam_move(S0A, S0B, BURST + Vector((0, 0, .3)), 30)
    c2 = cam_move((-2.6, -7.6, 1.2), (-2.2, -7.0, 1.0), BURST, 34)
    cuts((c1, 0), (c2, 1.6))
    overlays.append({'type': 'hook', 'text': '1 BOMB COULD KILL|98% OF SATELLITES'})

def s1_question():              # "What if a nuke went off in space?"
    earth(sun=(1, -.5, .3))
    a, limbs = kit.astronaut(); a.location = (0, -6.6, 1.3); a.scale = (.35,) * 3
    limbs['arm1'].rotation_euler = (math.radians(-60), math.radians(-30), 0)
    kit.key(a, 1, rotation_euler=(math.radians(6), 0, math.radians(200))); kit.key(a, NF, rotation_euler=(math.radians(-4), 0, math.radians(190)))
    area('ak', (1.5, -8.5, 2.5), a, 40, (1, .9, .8), 1); area('ar', (-1.5, -5.2, 2.2), a, 60, (.5, .65, 1), 1)
    w = warhead(.5); w.location = (.7, -5.4, 1.0)
    kit.key(w, 1, location=(.95, -5.3, .85), rotation_euler=(math.radians(70), 0, math.radians(30)))
    kit.key(w, NF, location=(.7, -5.5, 1.15), rotation_euler=(math.radians(76), math.radians(8), math.radians(40)))
    area('wk', (2.5, -6.5, 2), w, 30, (1, .8, .6), 1)
    swarm(160, .05, 400, 1200, spin=8)
    c1 = cam_move((-.6, -8.4, 1.6), (-.4, -8.0, 1.5), (.3, -5.8, 1.1), 34)
    c2 = cam_move((2.4, -6.6, 1.5), (2.2, -6.2, 1.4), (.8, -5.4, 1.0), 40)
    cuts((c1, 0), (c2, 1.2))

def s2_sim():                   # "This month, scientists simulated one megaton, five hundred kilometers up."
    earth()
    ground = P(BURST_LAT, BURST_LON, 0)
    pin = curve_obj([ground, BURST], 'pin', .014, (1, .78, .3), 12, 1.0)
    pin.data.bevel_factor_end = 0; pin.data.keyframe_insert('bevel_factor_end', frame=F(1.0)); pin.data.bevel_factor_end = 1
    pin.data.keyframe_insert('bevel_factor_end', frame=F(1.8))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=.04, location=ground); g = bpy.context.object; g.data.materials.append(emit_mat('gp', (1, .78, .3), 10)); g.visible_shadow = False
    burst(BURST, t0=3.3, r_max=.45, strength=50, life=2.5)
    swarm(200, .05, 400, 1200, spin=8)
    c1 = cam_move((0, -15.5, -2.6), (0, -13.5, -2.2), (0, 0, -1.2), 34, (0, 0, -1.3))
    n = BURST.normalized(); side = n.cross(Vector((0, 0, 1))).normalized()
    c2pos = BURST + n * 2.4 + side * 2.4 + Vector((0, 0, .3))
    c2 = cam_move(c2pos, c2pos + (ground - c2pos) * .08, (ground + BURST) / 2, 30)
    cuts((c1, 0), (c2, 2.6))
    sc.frame_set(F(3.2)); sc.camera = c2
    sg, sb = screen(c2, ground), screen(c2, BURST)
    overlays.append({'type': 'datestamp', 'text': 'SOUTH ATLANTIC · SIMULATION', 'from': .2})
    overlays.append({'type': 'badge', 'value': '1', 'unit': 'megaton', 'pos': [.5, .3], 'from': 1.3})
    overlays.append({'type': 'badge', 'value': '500', 'unit': 'km up', 'pos': [.5, .38], 'from': 2.9})
    sc.frame_set(1)

def s3_hiroshima():             # "That's about seventy Hiroshimas, above the Space Station."
    # side view of the limb: the globe is turned so the South Atlantic point is straight up (+Z), heights true to scale
    root, sp = earth(sun=(.3, -1, .6), spin_deg=0)
    root.rotation_euler = (math.radians(-110), 0, 0)
    top = Vector((0, 0, R)); bz = Vector((.22, 0, R + 500 * KM)); iz = Vector((-.3, 0, R + 410 * KM))
    st = iss(.07); st.location = iz
    kit.key(st, 1, location=iz); kit.key(st, NF, location=iz + Vector((.05, 0, 0)))
    area('ik', iz + Vector((.3, -.6, .3)), st, 3, (1, .95, .85), .3)
    m = emit_mat('hb', (1, .55, .2), 5)
    rng = random.Random(4)
    for k in range(70):        # 70 Hiroshima-size sparks (~15 kt each) merging into one 1,000 kt blast
        bpy.ops.mesh.primitive_uv_sphere_add(radius=.006, segments=10, ring_count=6); bb = bpy.context.object; bb.data.materials.append(m); bb.visible_shadow = False
        p0 = bz + Vector((rng.uniform(-1, 1), rng.uniform(-.6, .6), rng.uniform(-.6, 1))) * .22
        kit.key(bb, 1, location=p0); kit.key(bb, F(.4 + k * .02), location=p0); kit.key(bb, F(2.3), location=bz, scale=(.3,) * 3)
    cm, cf, cc = glow_mat('core', (1, .9, .7), 40, 2.0, True); core = glow_ball(bz, .05, cm, 'core')
    kit.key(core, 1, scale=(.01,) * 3); kit.key(core, F(2.1), scale=(.01,) * 3); kit.key(core, F(2.6), scale=(1,) * 3)
    li = bpy.data.lights.new('cl', 'POINT'); li.color = (1, .8, .6); lo = kit.link(bpy.data.objects.new('cl', li)); lo.location = bz
    kit.key(li, 1, energy=0); kit.key(li, F(2.1), energy=0); kit.key(li, F(2.5), energy=60)
    c1 = cam_move(bz + Vector((-.25, -.75, .06)), bz + Vector((-.2, -.62, .05)), bz + Vector((-.05, 0, -.02)), 30)
    mid = Vector((-.04, 0, R + .2))
    c2 = cam_move(mid + Vector((.1, -1.55, .12)), mid + Vector((.08, -1.4, .1)), mid, 36)
    cuts((c1, 0), (c2, 2.2))
    overlays.append({'type': 'badge', 'value': '≈70×', 'unit': 'Hiroshima', 'pos': [.5, .28], 'from': .5})
    overlays.append({'type': 'label', 'text': 'ISS ENLARGED', 'pos': (.5, .9), 'color': GREY, 'from': 2.3})
    sc.frame_set(F(3.0)); sc.camera = c2
    si, sb, sg = screen(c2, iz), screen(c2, bz), screen(c2, Vector((bz.x, 0, R)))
    overlays.append({'type': 'label', 'text': 'ISS ~400 KM', 'pos': (si[0], min(.8, si[1] + .06)), 'color': WHITE, 'from': 2.4})
    overlays.append({'type': 'label', 'text': 'BLAST 500 KM', 'pos': (sb[0], max(.36, sb[1] - .05)), 'color': YEL, 'from': 2.6})
    overlays.append({'type': 'measure', 'x': min(.92, sb[0] + .12), 'y0': sb[1], 'y1': sg[1], 'from': 2.6})
    sc.frame_set(1)

def s4_flash():                 # "The flash alone knocks out about three percent of satellites."
    earth(sun=(.6, .8, .2))
    burst(BURST, t0=.15, r_max=.5, strength=60, life=3.0)
    swarm(320, .05, 350, 1300, prog=[(0, 0), (.4, 0), (.75, .03), (D + 1, .03)], spin=10)
    c1 = cam_move(BURST + Vector((3.5, -6.5, 1.5)), BURST + Vector((3.0, -5.6, 1.3)), BURST, 30)
    c2 = cam_move((0, -17, 2.0), (0, -16, 1.8), (0, 0, -.6), 34)
    cuts((c1, 0), (c2, 2.0))
    overlays.append({'type': 'badge', 'value': '3%', 'unit': 'disabled instantly', 'pos': [.5, .3], 'from': .9})
    overlays.append({'type': 'label', 'text': 'SATELLITES ENLARGED', 'pos': (.5, .9), 'color': GREY, 'from': 2.2})

def s5_electrons():             # "But the real killer: electrons, trapped in Earth's magnetic field."
    earth(face=-60)
    field(10, (1.2, 1.5, 1.9), 2.2, .5)
    electrons(90, (1.12, 1.2, 1.3, 1.45), t_start=.2, drift=50)
    c1 = cam_move((-4.5, -13.5, 3.0), (-3.6, -12.5, 2.6), (0, 0, 0), 30)
    c2 = cam_move((3.2, -6.6, 1.5), (2.8, -6.1, 1.6), (4.4, 0, .6), 30)
    cuts((c1, 0), (c2, 2.4))
    overlays.append({'type': 'label', 'text': 'MAGNETIC FIELD', 'pos': (.5, .16), 'color': (120, 170, 255), 'from': .3})
    overlays.append({'type': 'label', 'text': 'TRAPPED ELECTRONS', 'pos': (.5, .22), 'color': YEL, 'from': 1.3})
    overlays.append({'type': 'label', 'text': 'VISUALIZATION', 'pos': (.5, .9), 'color': GREY, 'from': .8})

def s6_belt():                  # "They form a radiation belt, and every orbit through it adds damage."
    earth(face=-60)
    belt(.3, 4.5, t_in=.2)
    electrons(50, (1.15, 1.25, 1.35), drift=60, strength=10)
    swarm(260, .05, 450, 1300, prog=[(0, .03), (D, .12)], spin=18)
    c1 = cam_move((0, -16.5, 2.2), (0, -15.2, 2.0), (0, 0, 0), 32)
    c2 = cam_move((5.8, -4.2, 1.0), (5.4, -3.6, 1.2), (3.0, 3.0, .2), 28)
    cuts((c1, 0), (c2, 2.4))
    overlays.append({'type': 'label', 'text': 'NEW RADIATION BELT', 'pos': (.5, .16), 'color': (255, 120, 180), 'from': .5})

def s7_days():                  # "After one day, a quarter are disabled. After three days, seventy eight percent."
    earth(face=-60, spin_deg=25)
    belt(.26, 4.0)
    swarm(320, .075, 400, 1300, prog=[(0, .05), (1.8, .25), (2.6, .25), (4.6, .78), (D + 1, .78)], spin=40)
    c1 = cam_move((-3.0, -15.0, 3.0), (-2.6, -14.0, 2.8), (0, 0, -.2), 32)
    c2 = cam_move((4.6, -9.5, -1.6), (4.0, -8.8, -1.3), (0, 0, .2), 30)
    c3 = cam_move((0, -9.0, 6.5), (0, -8.2, 6.0), (0, 0, 0), 30)
    cuts((c1, 0), (c2, 2.1), (c3, 3.9))
    overlays.append({'type': 'badge', 'value': 'DAY 1', 'unit': '25% disabled', 'pos': [.5, .28], 'from': .4})
    overlays.append({'type': 'badge', 'value': 'DAY 3', 'unit': '78% disabled', 'pos': [.5, .36], 'from': 2.7})

def s8_week():                  # "After a week, ninety eight percent of satellites in low orbit."
    earth(face=-60, spin_deg=30)
    belt(.22, 3.6)
    swarm(380, .075, 400, 1300, prog=[(0, .78), (2.2, .98), (D + 1, .98)], spin=40)
    c1 = cam_move((0, -18.5, 1.0), (0, -20.5, 1.4), (0, 0, 0), 34)
    c2 = cam_move((-5.5, -6.5, 3.5), (-5.0, -5.9, 3.2), (-1, 1, 1), 28)
    cuts((c1, 0), (c2, 2.2))
    overlays.append({'type': 'badge', 'value': '98%', 'unit': 'in one week', 'pos': [.5, .28], 'from': .6})
    overlays.append({'type': 'label', 'text': '13,000+ SATELLITES', 'pos': (.5, .36), 'color': WHITE, 'from': 1.4})

JOHN = (16.73, -169.53)      # Johnston Atoll
def s9_before():                # "And it's happened before."
    earth(face=-165, sun=(.4, 1, .25))     # night over the central Pacific
    g = kit.latlon(*JOHN, R, -165, 0); top = kit.latlon(*JOHN, R, -165, 400 * KM)
    trail = curve_obj([g + (top - g) * k / 20 for k in range(21)], 'trail', .012, (1, .7, .35), 14, 1.0)
    trail.data.bevel_factor_end = 0; trail.data.keyframe_insert('bevel_factor_end', frame=1); trail.data.bevel_factor_end = 1
    trail.data.keyframe_insert('bevel_factor_end', frame=F(1.6))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=.03, location=g); d = bpy.context.object; d.data.materials.append(emit_mat('jd', (1, .8, .3), 12))
    nn = g.normalized(); sd = nn.cross(Vector((0, 0, 1))).normalized()
    c1 = cam_move(g + nn * 1.2 + sd * 1.6, g + nn * 1.0 + sd * 1.3, (g + top) / 2, 30)
    cuts((c1, 0))
    overlays.append({'type': 'datestamp', 'text': 'JOHNSTON ATOLL · JULY 1962', 'from': .2})

def s10_starfish():             # "In 1962, Starfish Prime lit up the Pacific sky and knocked out hundreds of Hawaii's streetlights."
    # shot 1: from space, the 1.4 Mt burst 400 km over Johnston Atoll, aurora glow running along the field lines
    earth(face=-165, sun=(.4, 1, .25))
    top = kit.latlon(*JOHN, R, -165, 400 * KM)
    burst(top, t0=.1, r_max=.7, strength=40, life=2.5)
    c1 = cam_move(top + Vector((1.2, -4.8, 1.8)), top + Vector((1.0, -4.2, 1.6)), top, 30)
    # shot 2+3: Hawaii shoreline at night, sky glowing green -> yellow -> red (SciAm), streetlights going dark
    O = Vector((300, 0, 0))
    bpy.ops.mesh.primitive_plane_add(size=400, location=O + Vector((0, 60, -.02))); sea = bpy.context.object
    sea.data.materials.append(kit.mat_principled('sea', (.01, .02, .03), rough=.08))
    bpy.ops.mesh.primitive_plane_add(size=60, location=O + Vector((0, -20, 0))); land = bpy.context.object
    land.data.materials.append(kit.mat_principled('road', (.05, .05, .055), rough=.8))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=150, segments=64, ring_count=32, location=O); dome = bpy.context.object
    for p in dome.data.polygons: p.use_smooth = True
    m = bpy.data.materials.new('aurora'); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); e = N.new('ShaderNodeEmission')
    tc = N.new('ShaderNodeTexCoord'); sep = N.new('ShaderNodeSeparateXYZ'); L.new(tc.outputs['Generated'], sep.inputs[0])
    mr = N.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value = .5; mr.inputs['From Max'].default_value = .75; L.new(sep.outputs['Z'], mr.inputs['Value'])
    inv = N.new('ShaderNodeMath'); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1; L.new(mr.outputs[0], inv.inputs[1])
    pw = N.new('ShaderNodeMath'); pw.operation = 'POWER'; pw.inputs[1].default_value = 1.6; L.new(inv.outputs[0], pw.inputs[0])
    nz = kit._noise(N, L, tc.outputs['Generated'], 6, 4, .5)
    mx = N.new('ShaderNodeMath'); mx.operation = 'MULTIPLY'; L.new(pw.outputs[0], mx.inputs[0]); L.new(nz.outputs['Fac'], mx.inputs[1])
    ml = N.new('ShaderNodeMath'); ml.operation = 'MULTIPLY'; L.new(mx.outputs[0], ml.inputs[0]); ml.inputs[1].default_value = 1.0
    L.new(ml.outputs[0], e.inputs['Strength']); L.new(e.outputs[0], o.inputs[0]); dome.data.materials.append(m)
    t2 = 2.4
    kf(e.inputs['Color'], 1, (.2, 1, .45, 1)); kf(e.inputs['Color'], F(t2), (.2, 1, .45, 1)); kf(e.inputs['Color'], F(t2 + 1.4), (1, .85, .2, 1))
    kf(e.inputs['Color'], F(t2 + 2.6), (1, .45, .1, 1)); kf(e.inputs['Color'], F(D + .7), (.95, .12, .08, 1))
    kf(ml.inputs[1], 1, 2.2); kf(ml.inputs[1], F(D + .7), 1.4)
    # streetlights along a coastal road (they go out one by one)
    lamp_on = []
    for k in range(9):
        x = -12 + k * 3.0; base = O + Vector((x, -2.0 - k * .55, 0))
        bpy.ops.mesh.primitive_cylinder_add(radius=.06, depth=4.0, location=base + Vector((0, 0, 2.0))); pole = bpy.context.object
        pole.data.materials.append(kit.mat_principled('pole', (.2, .2, .22), rough=.5, metal=.6))
        bpy.ops.mesh.primitive_cube_add(size=1, location=base + Vector((.45, 0, 4.0))); arm = bpy.context.object; arm.scale = (1.0, .12, .1)
        arm.data.materials.append(pole.data.materials[0])
        bpy.ops.mesh.primitive_uv_sphere_add(radius=.22, location=base + Vector((.85, 0, 3.85))); bulb = bpy.context.object
        lm = emit_mat(f'bulb{k}', (1, .72, .35), 30); bulb.data.materials.append(lm); bulb.visible_shadow = False
        li = bpy.data.lights.new(f'sl{k}', 'SPOT'); li.color = (1, .7, .35); li.spot_size = math.radians(110)
        lo = kit.link(bpy.data.objects.new(f'sl{k}', li)); lo.location = base + Vector((.85, 0, 3.7))
        toff = 4.4 + k * .22
        kit.key(li, 1, energy=900); kit.key(li, F(toff), energy=900); kit.key(li, F(toff) + 2, energy=0)
        em = lm.node_tree.nodes['em']; kf(em.inputs['Strength'], 1, 30); kf(em.inputs['Strength'], F(toff), 30); kf(em.inputs['Strength'], F(toff) + 2, .05)
    c2 = cam_move(O + Vector((14, -24, 2.2)), O + Vector((13, -22, 2.0)), O + Vector((-2, 10, 9)), 26)
    c3 = cam_move(O + Vector((-15, -12, 1.6)), O + Vector((-13.5, -11, 1.5)), O + Vector((2, -5, 2.6)), 26)
    cuts((c1, 0), (c2, t2), (c3, 4.6))
    overlays.append({'type': 'datestamp', 'text': 'STARFISH PRIME · 8 JULY 1962', 'from': .2})
    overlays.append({'type': 'badge', 'value': '1.4', 'unit': 'megatons', 'pos': [.5, .22], 'from': .8})
    overlays.append({'type': 'label', 'text': 'HAWAII', 'pos': (.5, .31), 'color': WHITE, 'from': t2 + .3})
    overlays.append({'type': 'label', 'text': 'HUNDREDS OF STREETLIGHTS OUT', 'pos': (.5, .37), 'color': YEL, 'from': 4.8})

def s11_telstar():              # "Its radiation helped kill Telstar, the first satellite to relay live TV."
    earth(face=-40, sun=(1, -.6, .4))
    belt(.22, 2.4)
    t = telstar(.9); t.location = (0, -7.0, 1.6)
    kit.key(t, 1, rotation_euler=(math.radians(10), 0, 0)); kit.key(t, NF, rotation_euler=(math.radians(10), 0, math.radians(70)))
    area('tk', (1.5, -9, 2.6), t, 60, (1, .92, .8), 1.5); area('tr', (-1.4, -5.2, 2.4), t, 80, (1, .4, .6), 1.5)
    # radiation hits: little sparks striking the hull
    electrons(40, (1.12, 1.25), drift=40, strength=10)
    m = emit_mat('hit', (1, .45, .7), 25); rng = random.Random(9)
    for k in range(14):
        a, b = rng.uniform(0, 6.28), rng.uniform(-1.2, 1.2)
        p = Vector((math.cos(a) * math.cos(b), math.sin(a) * math.cos(b), math.sin(b))) * .41 + Vector((0, -7.0, 1.6))
        bpy.ops.mesh.primitive_uv_sphere_add(radius=.02, location=p); s = bpy.context.object; s.data.materials.append(m); s.visible_shadow = False
        tt = F(rng.uniform(.3, D)); kit.key(s, 1, scale=(.01,) * 3); kit.key(s, tt, scale=(.01,) * 3); kit.key(s, tt + 2, scale=(2,) * 3); kit.key(s, tt + 6, scale=(.01,) * 3)
    c1 = cam_move((1.3, -9.4, 2.1), (1.0, -8.9, 2.0), (0, -7.0, 1.55), 45)
    c2 = cam_move((-2.4, -10.5, .6), (-2.0, -10.0, .7), (0, -7.0, 1.4), 30)
    cuts((c1, 0), (c2, 2.6))
    overlays.append({'type': 'datestamp', 'text': 'TELSTAR 1 · 1962', 'from': .3})
    overlays.append({'type': 'label', 'text': 'FIRST LIVE TV RELAY', 'pos': (.5, .24), 'color': YEL, 'from': 2.8})

def s12_loop():                 # "So today," -> loops into the hook
    earth(sun=(.6, .8, .2))
    burst(BURST, t0=D + .15, r_max=.5, strength=60, life=3.2)
    swarm(240, .05, 350, 1300, spin=10)
    cam_move((3.2, -10.6, -1.1), S0A, BURST + Vector((0, 0, .3)), 30)
    overlays.append({'type': 'cta', 'pos': (.5, .1)})

[s0_hook, s1_question, s2_sim, s3_hiroshima, s4_flash, s5_electrons, s6_belt, s7_days, s8_week, s9_before, s10_starfish, s11_telstar, s12_loop][idx]()
if sc.world:
    try: sc.world.cycles.sampling_method = 'NONE'
    except Exception: pass
sc.cycles.max_bounces = 2; sc.cycles.diffuse_bounces = 1; sc.cycles.glossy_bounces = 1; sc.cycles.transmission_bounces = 1
for mt in bpy.data.materials:       # emissive meshes (city lights, glows, satellites) are not sampled as lights: big speedup
    try: mt.cycles.emission_sampling = 'NONE'
    except Exception: pass
    if mt.node_tree:
        for nd in mt.node_tree.nodes:
            if nd.type == 'TEX_IMAGE': nd.interpolation = 'Linear'     # cubic 8K lookups are slow on 2 CPUs
for o in bpy.data.objects:
    for m in getattr(o, 'modifiers', []):
        if m.type == 'SUBSURF': m.render_levels = min(m.render_levels, 1)
os.makedirs(f'{OUT}/s{idx}', exist_ok=True)
json.dump({'frames': NF, 'overlays': overlays}, open(f'{OUT}/s{idx}/meta.json', 'w'))
if mode == 'still':
    fr = float(sys.argv[3]) if len(sys.argv) > 3 else .6
    sc.frame_set(max(1, int(NF * fr))); sc.render.filepath = f'{OUT}/still_{idx}_{fr}.png'; bpy.ops.render.render(write_still=True)
else:
    if os.environ.get('FR'): sc.frame_start, sc.frame_end = map(int, os.environ['FR'].split(','))
    sc.render.image_settings.file_format = 'PNG'; sc.render.filepath = f'{OUT}/s{idx}/f_'; bpy.ops.render.render(animation=True)
