"""Story Short: The avalanche buried Kai. One Cycles still per plate (animated in 2D by aval_anim.py).
python3 aval_plate.py <plate> [res_scale]  -> aval/plates/<plate>.png
Slope plates (backcountry, 38-degree slope, sunset): top_wide, cu_leo, cu_kai, kai_crack, slope_up, kai_caught, cu_nora
Debris plates (runout zone below the slide): debris_hand, leo_debris, nora_debris, nora_beacon, probe, dig_pit, kai_face, group_end"""
import sys, math, os, random
sys.path.insert(0, '/home/claude/b3d')
import bpy, kit
kit.CAST['kai']['hair_c'] = (.07, .03, .012)
kit.CAST['nora']['hair_c'] = (.8, .08, .06)
from mathutils import Vector
name = sys.argv[1]; S = float(sys.argv[2]) if len(sys.argv) > 2 else 0.75
OUT = '/home/claude/b3d/aval/plates'; os.makedirs(OUT, exist_ok=True)
W, H = int(1080 * S), int(1920 * S)
sc = kit.reset(res=(W, H), samples=int(os.environ.get('SAMPLES', 48)))
sc.view_settings.exposure = -0.7; sc.cycles.adaptive_threshold = 0.03; sc.cycles.max_bounces = 6; sc.cycles.diffuse_bounces = 3; sc.cycles.transmission_bounces = 6

def area(nm, loc, aim, energy, color=(1, 1, 1), size=2.0):
    li = bpy.data.lights.new(nm, 'AREA'); li.energy = energy; li.color = color; li.size = size
    o = kit.link(bpy.data.objects.new(nm, li)); o.location = loc
    o.rotation_euler = (Vector(aim) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler(); o.visible_glossy = False; o.visible_transmission = False; return o

def point(nm, loc, energy, color, radius=.05):
    li = bpy.data.lights.new(nm, 'POINT'); li.energy = energy; li.color = color; li.shadow_soft_size = radius
    o = kit.link(bpy.data.objects.new(nm, li)); o.location = loc; return o

def flat_world(col, strength=1.0):
    w = bpy.data.worlds.new('w'); sc.world = w; nt, N, L = kit.nodes(w)
    o = N.new('ShaderNodeOutputWorld'); bg = N.new('ShaderNodeBackground'); bg.inputs['Color'].default_value = (*col, 1)
    bg.inputs['Strength'].default_value = strength; L.new(bg.outputs[0], o.inputs['Surface'])

def M(nm, col, rough=.5, metal=0.0, coat=0.0):
    return kit.mat_principled(nm, col, rough=rough, metal=metal, coat=coat)

def box(nm, loc, size, mat, bevel=.01, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(location=loc); o = bpy.context.object; o.name = nm; o.scale = (size[0] / 2, size[1] / 2, size[2] / 2)
    o.rotation_euler = rot; bpy.ops.object.transform_apply(scale=True); o.data.materials.append(mat)
    if bevel: b = o.modifiers.new('b', 'BEVEL'); b.width = bevel; b.segments = 3
    return o

def cyl(nm, loc, r, depth, mat, rot=(0, 0, 0), verts=48):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=depth, location=loc, rotation=rot, vertices=verts); o = bpy.context.object; o.name = nm
    o.data.materials.append(mat); bpy.ops.object.shade_smooth(); return o

def rod(nm, p0, p1, r, mat, verts=16):
    v = Vector(p1) - Vector(p0); mid = (Vector(p0) + Vector(p1)) / 2
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=v.length, location=mid, vertices=verts); o = bpy.context.object; o.name = nm
    o.rotation_euler = v.to_track_quat('Z', 'Y').to_euler(); o.data.materials.append(mat); bpy.ops.object.shade_smooth(); return o

def tube(nm, pts, r, mat):
    """smooth tube along points (bezier curve with bevel)"""
    cu = bpy.data.curves.new(nm, 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = r; cu.bevel_resolution = 4
    sp = cu.splines.new('BEZIER'); sp.bezier_points.add(len(pts) - 1)
    for p, q in zip(sp.bezier_points, pts): p.co = q; p.handle_left_type = p.handle_right_type = 'AUTO'
    o = kit.link(bpy.data.objects.new(nm, cu)); cu.materials.append(mat); return o

def cam(loc, look, lens, fstop=None, focus=None):
    c, t = kit.camera(loc, look, lens=lens)
    if fstop:
        c.data.dof.use_dof = True; c.data.dof.focus_distance = focus or (Vector(loc) - Vector(look)).length; c.data.dof.aperture_fstop = fstop
    return c

def haze(density, loc, scale, col=(.8, .85, 1)):
    bpy.ops.mesh.primitive_cube_add(location=loc); v = bpy.context.object; v.scale = scale; v.name = 'haze'
    m = bpy.data.materials.new('haze'); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); vs = N.new('ShaderNodeVolumeScatter')
    vs.inputs['Density'].default_value = density; vs.inputs['Anisotropy'].default_value = .55; vs.inputs['Color'].default_value = (*col, 1)
    L.new(vs.outputs[0], o.inputs['Volume']); v.data.materials.append(m); return v

def cast(spec, y=0.0):
    """spec: who -> dict(loc, expr, rot (deg xyz), arms {arm: (rx, ry, rz) deg}, h)"""
    out = {}
    for who, d in spec.items():
        root, parts = kit.character(who, loc=d['loc'], height=d.get('h', 1.0))
        rx, ry, rz = d.get('rot', (0, 0, 0)); root.rotation_euler = (math.radians(rx), math.radians(ry), math.radians(rz))
        parts['face_mat'].node_tree.nodes['expr'].outputs[0].default_value = kit.EXPRS.index(d.get('expr', 'neutral'))
        for arm, r in d.get('arms', {}).items(): parts[arm].rotation_euler = tuple(math.radians(a) for a in r)
        out[who] = (root, parts)
    return out

# ------------------------------------------------------------------ materials
def snow_mat(nm='snowfield'):
    m = bpy.data.materials.new(nm); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled')
    bs.inputs['Base Color'].default_value = (.86, .9, .97, 1); bs.inputs['Roughness'].default_value = .6
    bs.inputs['Subsurface Weight'].default_value = .35; bs.inputs['Subsurface Radius'].default_value = (.8, .9, 1)
    tc = N.new('ShaderNodeTexCoord'); nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 3; nz.inputs['Detail'].default_value = 10
    L.new(tc.outputs['Object'], nz.inputs[0]); nz2 = N.new('ShaderNodeTexNoise'); nz2.inputs['Scale'].default_value = 90; L.new(tc.outputs['Object'], nz2.inputs[0])
    mx = N.new('ShaderNodeMath'); mx.operation = 'ADD'; L.new(nz.outputs['Fac'], mx.inputs[0]); L.new(nz2.outputs['Fac'], mx.inputs[1])
    bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = .35; L.new(mx.outputs[0], bp.inputs['Height']); L.new(bp.outputs[0], bs.inputs['Normal'])
    # sparkle: tiny glints
    vo = N.new('ShaderNodeTexVoronoi'); vo.inputs['Scale'].default_value = 900; L.new(tc.outputs['Object'], vo.inputs[0])
    gl = N.new('ShaderNodeMapRange'); gl.inputs['From Min'].default_value = .04; gl.inputs['From Max'].default_value = 0.0; L.new(vo.outputs['Distance'], gl.inputs[0])
    L.new(gl.outputs[0], bs.inputs['Specular IOR Level'])
    L.new(bs.outputs[0], o.inputs[0]); return m

def ice_mat(nm='pondice', white=0.0):
    """new, clear 'black' ice (IOR 1.31): glossy, transmissive, with trapped bubbles, fine surface scratches and patches of powder snow"""
    m = bpy.data.materials.new(nm); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled')
    bs.inputs['Base Color'].default_value = (.25, .4, .45, 1); bs.inputs['IOR'].default_value = 1.31; bs.inputs['Transmission Weight'].default_value = .7
    tc = N.new('ShaderNodeTexCoord')
    sc_ = N.new('ShaderNodeTexNoise'); sc_.inputs['Scale'].default_value = 40; sc_.inputs['Detail'].default_value = 14; L.new(tc.outputs['Object'], sc_.inputs[0])
    rr = N.new('ShaderNodeMapRange'); rr.inputs['To Min'].default_value = .02; rr.inputs['To Max'].default_value = .12; L.new(sc_.outputs['Fac'], rr.inputs[0]); L.new(rr.outputs[0], bs.inputs['Roughness'])
    # powder snow drifts on top
    dn = N.new('ShaderNodeTexNoise'); dn.inputs['Scale'].default_value = .5; dn.inputs['Detail'].default_value = 8; L.new(tc.outputs['Object'], dn.inputs[0])
    dm = N.new('ShaderNodeMapRange'); dm.inputs['From Min'].default_value = .56 - white; dm.inputs['From Max'].default_value = .66 - white; L.new(dn.outputs['Fac'], dm.inputs[0])
    snow = N.new('ShaderNodeBsdfPrincipled'); snow.inputs['Base Color'].default_value = (.85, .9, .96, 1); snow.inputs['Roughness'].default_value = .7
    mix = N.new('ShaderNodeMixShader'); L.new(dm.outputs[0], mix.inputs[0]); L.new(bs.outputs[0], mix.inputs[1]); L.new(snow.outputs[0], mix.inputs[2])
    bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = .08; L.new(sc_.outputs['Fac'], bp.inputs['Height']); L.new(bp.outputs[0], bs.inputs['Normal'])
    L.new(mix.outputs[0], o.inputs[0]); return m

def dark_water(nm='pondwater'):
    m = bpy.data.materials.new(nm); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled')
    bs.inputs['Base Color'].default_value = (.003, .012, .016, 1); bs.inputs['Roughness'].default_value = .03; bs.inputs['IOR'].default_value = 1.333
    tc = N.new('ShaderNodeTexCoord'); wv = N.new('ShaderNodeTexWave'); wv.wave_type = 'RINGS'; wv.inputs['Scale'].default_value = 3.5; wv.inputs['Distortion'].default_value = 4
    L.new(tc.outputs['Object'], wv.inputs[0]); bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = .25; L.new(wv.outputs['Fac'], bp.inputs['Height']); L.new(bp.outputs[0], bs.inputs['Normal'])
    L.new(bs.outputs[0], o.inputs[0]); return m

def pine(loc, h, seed=0):
    r = random.Random(seed)
    trunk = M('trunk', (.08, .05, .03), .9); cyl(f'tr{seed}', (loc[0], loc[1], loc[2] + h * .1), h * .03, h * .2, trunk, verts=10)
    m = bpy.data.materials.get('pinesnow')
    if m is None:
        m = bpy.data.materials.new('pinesnow'); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial')
        g = N.new('ShaderNodeBsdfPrincipled'); g.inputs['Base Color'].default_value = (.015, .045, .035, 1); g.inputs['Roughness'].default_value = .85
        s = N.new('ShaderNodeBsdfPrincipled'); s.inputs['Base Color'].default_value = (.85, .9, .96, 1); s.inputs['Roughness'].default_value = .6
        ge = N.new('ShaderNodeNewGeometry'); sep = N.new('ShaderNodeSeparateXYZ'); L.new(ge.outputs['Normal'], sep.inputs[0])
        nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 12; tc = N.new('ShaderNodeTexCoord'); L.new(tc.outputs['Object'], nz.inputs[0])
        ad = N.new('ShaderNodeMath'); ad.operation = 'ADD'; L.new(sep.outputs['Z'], ad.inputs[0]); L.new(nz.outputs['Fac'], ad.inputs[1])
        mr = N.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value = .95; mr.inputs['From Max'].default_value = 1.15; L.new(ad.outputs[0], mr.inputs[0])
        mx = N.new('ShaderNodeMixShader'); L.new(mr.outputs[0], mx.inputs[0]); L.new(g.outputs[0], mx.inputs[1]); L.new(s.outputs[0], mx.inputs[2]); L.new(mx.outputs[0], o.inputs[0])
    for k in range(5):
        z = loc[2] + h * (.18 + k * .16); rad = h * (.32 - k * .055)
        bpy.ops.mesh.primitive_cone_add(radius1=rad, radius2=0, depth=h * .3, location=(loc[0], loc[1], z + h * .1), vertices=14)
        c = bpy.context.object; c.rotation_euler = (r.uniform(-.04, .04), r.uniform(-.04, .04), r.uniform(0, 6)); c.data.materials.append(m)

# ------------------------------------------------------------------ the slope set (1 unit = 1 m; cast ~1 m tall, cartoon scale)
TAN = math.tan(math.radians(38)); RIDGE = 3.0
def zs(y):
    """slope height: 38 degrees below the ridge line (y < RIDGE), then rounding over to a gentle crest"""
    if y < RIDGE: return y * TAN
    d = y - RIDGE; return RIDGE * TAN + d * TAN * math.exp(-d / 1.5) * .9

def grid(nm, xs, ys, nx, ny, fz, mat):
    import bmesh
    bm = bmesh.new(); vs = []
    for j in range(ny + 1):
        row = []
        for i in range(nx + 1):
            x = xs[0] + (xs[1] - xs[0]) * i / nx; y = ys[0] + (ys[1] - ys[0]) * j / ny
            row.append(bm.verts.new((x, y, fz(x, y))))
        vs.append(row)
    for j in range(ny):
        for i in range(nx): bm.faces.new((vs[j][i], vs[j][i + 1], vs[j + 1][i + 1], vs[j + 1][i]))
    me = bpy.data.meshes.new(nm); bm.to_mesh(me); bm.free(); o = kit.link(bpy.data.objects.new(nm, me)); me.materials.append(mat)
    for p in me.polygons: p.use_smooth = True
    return o

def skis(x, y, z, color=(.75, .1, .08), yaw=0.0, nm='ski'):
    sm = M(nm, color, .3, coat=.6)
    for k, dy in enumerate((-.06, .06)):
        box(f'{nm}{k}', (x, y + dy, z + .012), (1.3, .07, .02), sm, .008, rot=(0, 0, yaw))
        box(f'{nm}tip{k}', (x + .68 * math.cos(yaw), y + dy + .68 * math.sin(yaw), z + .04), (.1, .07, .02), sm, .008, rot=(0, -.5, yaw))

def poles(x, y, z, spread=.34):
    pm = M('pole', (.12, .12, .14), .35, 1)
    for s in (-1, 1): rod(f'pole{s}{x}', (x + s * .3, y + .05, z - .05), (x + s * .27, y + .02, z + .5), .008, pm, 8)

def peaks(seed=5):
    for k, (x, y, h, sz) in enumerate(((-60, 140, 55, 160), (70, 170, 70, 180), (0, 220, 90, 260))):
        t = kit.terrain(size=sz, height=h, scale=1.6, kind='snow', seed=seed + k, res=6); t.location = (x, y, -10)

def slope_set(sun_el=3.0, sun_rot=205):
    sun = kit.sky(sun_el, sun_rot, strength=.28, sun_lamp_energy=3.2, dust=2.2)
    sn = snow_mat()
    r = random.Random(3)
    def fz(x, y): return zs(y) + .06 * math.sin(x * 1.3 + y * .7) + .04 * math.sin(x * 3.1 - y * 2.3)
    grid('slope', (-30, 30), (-45, 14), 120, 140, fz, sn)
    peaks()
    # pines down the left edge of the slide path (trees grow where avalanches don't run every year)
    for k in range(40):
        x = -r.uniform(5.5, 22); y = r.uniform(-40, 10); pine((x, y, zs(y) - .1), r.uniform(3, 6.5), k)
    for k in range(18):
        x = r.uniform(9, 24); y = r.uniform(-40, 4); pine((x, y, zs(y) - .1), r.uniform(3, 6), k + 60)
    haze(.008, (0, 20, 8), (70, 70, 12), (1, .85, .75))
    return sun

SPOT = {'nora': (-1.3, -.2), 'leo': (0.0, -.9), 'kai': (1.4, -1.7)}
def on_slope(who, expr, rot=(0, 0, 0), arms=None, dx=0, dy=0, sink=.08):
    x, y = SPOT[who]; x += dx; y += dy; z = zs(y) - sink
    skis(x, y, z + sink - .03, nm=f'ski_{who}', color={'nora': (.1, .35, .8), 'leo': (.95, .55, .05), 'kai': (.75, .1, .08)}[who])
    poles(x, y, z + sink)
    return {who: dict(loc=(x, y, z + .04), expr=expr, rot=rot, arms=arms or {'arm_l': (0, -30, 0), 'arm_r': (0, 30, 0)})}

def slope_plate():
    slope_set()
    warm, cool = (1, .66, .4), (.45, .6, 1)
    if name == 'top_wide':
        sp = {}; sp.update(on_slope('nora', 'neutral', (0, 0, 10))); sp.update(on_slope('leo', 'worried', (0, 0, -5))); sp.update(on_slope('kai', 'smirk', (0, 0, -20)))
        cast(sp); area('key', (4, -5, 1.5), (0, -1, .5), 260, warm, 4); area('rim', (-3, 3, 4), (0, -1, .5), 160, cool, 4)
        cam((1.5, -4.9, zs(-4.9) + 1.0), (.35, -.9, zs(-.9) + .5), 28, 5.6, 4.0)
    elif name == 'cu_leo':
        cast(on_slope('leo', 'worried', (0, 0, -10), {'arm_l': (-40, 0, 30), 'arm_r': (-40, 0, -30)}))
        x, y = SPOT['leo']; z = zs(y)
        area('key', (x + 1.2, y - 1.5, z + 1.5), (x, y, z + .7), 90, warm, 1.5); area('rim', (x - 1, y + 1.5, z + 1.8), (x, y, z + .8), 80, cool, 1.5)
        cam((x + .15, y - 1.35, z + .85), (x, y, z + .78), 50, 2.0)
    elif name == 'cu_kai':
        cast(on_slope('kai', 'smirk', (0, 0, 15), {'arm_l': (0, -20, 0), 'arm_r': (-50, 60, 0)}))
        x, y = SPOT['kai']; z = zs(y)
        area('key', (x - 1.2, y - 1.5, z + 1.5), (x, y, z + .7), 90, warm, 1.5); area('rim', (x + 1, y + 1.5, z + 1.8), (x, y, z + .8), 80, cool, 1.5)
        cam((x - .15, y - 1.35, z + .85), (x, y, z + .78), 50, 2.0)
    elif name == 'kai_crack':
        cast(on_slope('kai', 'surprised', (0, 0, -15), {'arm_l': (0, -70, 0), 'arm_r': (0, 70, 0)}))
        x, y = SPOT['kai']; z = zs(y)
        area('key', (x + 2, y - 3, z + 1.5), (x, y, z + .5), 160, warm, 2); area('rim', (x - 2, y + 2, z + 2), (x, y, z + .7), 100, cool, 2)
        cam((x + .3, y - 2.5, zs(y - 2.5) + .75), (x, y + .6, z + .5), 28, 5.6, 2.6)
    elif name == 'slope_up':   # looking straight up the empty slide path from far below
        area('key', (6, -30, zs(-30) + 4), (0, -12, zs(-12)), 400, warm, 8)
        cam((1.0, -34, zs(-34) + 1.4), (0, -4, zs(-4) + 1.0), 24)
    elif name == 'kai_caught':   # Kai knocked over in moving snow, arm up
        x, y = SPOT['kai']; y -= 6; z = zs(y)
        cast({'kai': dict(loc=(x, y, z - .45), expr='scared', rot=(55, 0, 20), arms={'arm_l': (-170, 0, -20), 'arm_r': (-150, 40, 0)})})
        sm = snow_mat('chunks'); rr = random.Random(9)
        for k in range(40):
            cx = x + rr.uniform(-2.5, 2.5); cy = y + rr.uniform(-2, 3); s = rr.uniform(.08, .35)
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=s, location=(cx, cy, zs(cy) + s * .3)); ch = bpy.context.object
            ch.scale = (1, rr.uniform(.6, 1.2), rr.uniform(.5, 1)); ch.rotation_euler = (rr.uniform(0, 3), rr.uniform(0, 3), 0); ch.data.materials.append(sm)
        area('key', (x + 2, y - 3, z + 2), (x, y, z), 160, warm, 2); area('rim', (x - 2, y + 2, z + 2), (x, y, z + .4), 120, cool, 2)
        cam((x + .8, y - 2.6, zs(y - 2.6) + .9), (x, y + .3, z + .2), 30, 4.0)
    elif name == 'cu_nora':
        cast(on_slope('nora', 'angry', (0, 0, -40), {'arm_l': (-150, 0, -15), 'arm_r': (-160, 0, 15)}))
        x, y = SPOT['nora']; z = zs(y)
        area('key', (x + 1.2, y - 1.5, z + 1.5), (x, y, z + .7), 100, warm, 1.5); area('rim', (x - 1, y + 1.5, z + 1.8), (x, y, z + .8), 80, cool, 1.5)
        cam((x - .1, y - 1.4, z + .8), (x, y, z + .8), 45, 2.0)

# ------------------------------------------------------------------ the debris set: the runout zone at the bottom of the slide (flat, z = 0)
def debris_set(sun_el=2.5, sun_rot=205, dusk=False):
    sun = kit.sky(sun_el, sun_rot, strength=.24 if not dusk else .12, sun_lamp_energy=2.6 if not dusk else 1.2, dust=2.5)
    sn = snow_mat(); r = random.Random(21)
    def fz(x, y):   # flat runout, slope rising behind (+Y) from y = 10
        base = 0.0 if y < 10 else (y - 10) * TAN * min(1, (y - 10) / 4)
        return base + .05 * math.sin(x * 1.1 + y * .6)
    grid('ground', (-40, 40), (-30, 60), 110, 130, fz, sn)
    peaks(8)
    db = snow_mat('debris')
    def clear(x, y): return -2.6 < x < 2.6 and -4.5 < y < 4.4   # keep the cast / camera area open (only small chunks there)
    for k in range(520):   # avalanche debris: hard rounded blocks and snowballs piled in a tongue, small chunks everywhere
        x = r.gauss(0, 4.0); y = r.uniform(-5, 13)
        s = r.uniform(.05, .13) if clear(x, y) else r.uniform(.1, .38)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=s, location=(x, y, s * .2 + .03)); ch = bpy.context.object
        ch.scale = (r.uniform(.8, 1.4), r.uniform(.8, 1.3), r.uniform(.45, .75)); ch.rotation_euler = (r.uniform(-.4, .4), r.uniform(-.4, .4), r.uniform(0, 3))
        ch.data.materials.append(db); bpy.ops.object.shade_smooth()
    br = M('branch', (.12, .08, .05), .9)
    for k in range(8):
        x0, y0 = r.uniform(-5, 5), r.uniform(3.5, 10); rod(f'br{k}', (x0, y0, .15), (x0 + r.uniform(-.8, .8), y0 + r.uniform(-.5, .5), .3), .025, br, 6)
    for k in range(40):
        x = r.choice((-1, 1)) * r.uniform(8, 25); y = r.uniform(-15, 40); pine((x, y, fz(x, y) - .1), r.uniform(3, 6.5), k + 200)
    haze(.008, (0, 20, 6), (70, 70, 10), (1, .85, .75))
    return sun

def buried_kai(z=-.95, arm_out=True):
    """Kai buried upright in the debris with his right hand pushed up through the surface"""
    cast({'kai': dict(loc=(0, 3, z), expr='scared', rot=(10, 0, 0), arms={'arm_r': (-175, 0, 8) if arm_out else (-120, 0, 0), 'arm_l': (-100, 0, -30)})})

def debris_plate():
    warm, cool = (1, .66, .4), (.45, .6, 1)
    dusk = name == 'group_end'
    debris_set(dusk=dusk)
    if name == 'debris_hand':
        rod('sleeve', (.125, 3.0, -.35), (.125, 3.0, .2), .035, M('sleeve', (.32, .38, .12), .8), 12)

        bpy.ops.mesh.primitive_uv_sphere_add(radius=.075, location=(.125, 3.0, .3)); g = bpy.context.object; g.scale = (1, .7, 1.5); g.data.materials.append(M('glove', (.75, .1, .08), .7))
        area('key', (1.5, 1.2, 1.2), (0, 3, .1), 90, warm, 1.5); area('rim', (-1.5, 5, 1.2), (0, 3, .2), 70, cool, 1.5)
        cam((.6, 1.2, .45), (.1, 3.0, .15), 40, 2.8)
    elif name in ('leo_debris', 'nora_debris'):
        who = 'leo' if name == 'leo_debris' else 'nora'
        spec = {'leo': dict(loc=(-.8, -.5, .15), expr='scared', rot=(0, 0, 160), arms={'arm_l': (-80, 0, 40), 'arm_r': (-80, 0, -40)}),
                'nora': dict(loc=(.5, -.4, .15), expr='angry', rot=(0, 0, 200), arms={'arm_r': (-90, 0, -20), 'arm_l': (0, -20, 0)})}
        cast(spec)
        x, y = spec[who]['loc'][:2]
        area('key', (x + (1.3 if who == 'leo' else -1.3), y + 1.6, 1.6), (x, y, .8), 90, warm, 1.5); area('rim', (x, y - 1.6, 1.8), (x, y, .8), 60, cool, 1.5)
        cam((x + (.15 if who == 'leo' else -.15), y + 1.4, .95), (x, y, .92), 48, 2.0)
    elif name == 'nora_beacon':
        cast({'nora': dict(loc=(.4, 1.2, .2), expr='worried', rot=(12, 0, 15), arms={'arm_r': (-75, 0, -25), 'arm_l': (-75, 0, 25)})})
        # the beacon in her hands: a small yellow box with a glowing screen
        bb = box('beacon', (.4, .95, .58), (.11, .05, .17), M('beaconcase', (.95, .7, .05), .4), .01, rot=(math.radians(-40), 0, 0))
        box('beaconscr', (.4, .925, .61), (.08, .01, .07), kit.mat_emit('scr', (.4, 1, .6), 4), 0, rot=(math.radians(-40), 0, 0))
        area('key', (1.4, -.4, 1.6), (.4, 1.2, .6), 100, warm, 1.5); area('rim', (-.8, 2.8, 1.6), (.4, 1.2, .8), 80, cool, 1.5)
        point('scrglow', (.4, .85, .66), 2, (.4, 1, .6), .03)
        cam((.75, -.35, .85), (.4, 1.1, .55), 34, 2.8)
    elif name == 'probe':
        cast({'leo': dict(loc=(.4, 2.4, .2), expr='worried', rot=(15, 0, 15), arms={'arm_r': (-55, 0, -35), 'arm_l': (-55, 0, 35)})})
        pr = M('probe', (.75, .76, .78), .3, 1); rod('probe', (.33, 2.0, -.9), (.38, 2.17, .6), .012, pr, 8)
        area('key', (1.6, .6, 1.5), (.3, 2.6, .4), 100, warm, 1.5); area('rim', (-1, 4.2, 1.5), (.3, 2.8, .6), 80, cool, 1.5)
        cam((1.3, .9, .5), (.25, 2.7, .3), 32, 4.0)
    elif name in ('dig_pit', 'kai_face'):
        # a dug pit: dark cut walls going down to Kai's face
        pit = M('pitwall', (.55, .68, .85), .6); pit.node_tree.nodes['Principled BSDF'].inputs['Subsurface Weight'].default_value = .4
        bpy.ops.mesh.primitive_cylinder_add(radius=.6, depth=1.4, location=(0, 3, -.5), vertices=10); c_ = bpy.context.object
        g = bpy.data.objects['ground']; bo = g.modifiers.new('pit', 'BOOLEAN'); bo.object = c_; bo.operation = 'DIFFERENCE'
        bpy.context.view_layer.objects.active = g; bpy.ops.object.modifier_apply(modifier='pit'); c_.hide_render = True
        for ob in list(bpy.data.objects):   # clear debris lumps inside the pit
            if ob.name.startswith('Icosphere') and (Vector(ob.location[:2]) - Vector((0, 3))).length < .75: bpy.data.objects.remove(ob)
        bpy.ops.mesh.primitive_cylinder_add(radius=.6, depth=1.2, location=(0, 3, -.6), vertices=10, end_fill_type='NOTHING'); wall = bpy.context.object
        wall.data.materials.append(pit); wall.scale = (1, 1, 1)
        bpy.ops.mesh.primitive_cylinder_add(radius=.6, depth=.9, location=(0, 3, -.98), vertices=24); fill = bpy.context.object; fill.data.materials.append(snow_mat('fill'))
        bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.flip_normals(); bpy.ops.object.mode_set(mode='OBJECT')
        cast({'kai': dict(loc=(0, 3.1, -1.05), expr='worried' if name == 'dig_pit' else 'happy', rot=(-25, 0, 0), arms={'arm_r': (-170, 0, 8), 'arm_l': (-60, 0, -20)})})
        sh = M('shovel', (.15, .3, .75), .35, .6); hd = M('handle', (.1, .1, .12), .4, .8)
        if name == 'dig_pit':
            cast({'nora': dict(loc=(-.75, 3.75, .1), expr='worried', rot=(22, 0, -25), arms={'arm_r': (60, 0, -10), 'arm_l': (60, 0, 10)}),
                  'leo': dict(loc=(.8, 3.7, .1), expr='scared', rot=(22, 0, 25), arms={'arm_r': (60, 0, -10), 'arm_l': (60, 0, 10)})})
            rod('sh1', (-.6, 3.5, .45), (-.3, 3.25, .0), .012, hd); box('blade1', (-.27, 3.22, -.03), (.2, .02, .24), sh, .01, rot=(-.6, 0, -.7))
            rod('sh2', (.65, 3.45, .45), (.35, 3.25, .0), .012, hd); box('blade2', (.32, 3.22, -.03), (.2, .02, .24), sh, .01, rot=(-.6, 0, .7))
            area('key', (1.4, 1.0, 2.2), (0, 3, -.3), 160, warm, 2); area('rim', (-1.2, 4.6, 1.8), (0, 3, 0), 80, cool, 1.5)
            cam((.2, .2, 2.0), (0, 2.95, -.35), 30, 4.0)
        else:
            area('key', (.7, 2.0, .6), (0, 3.1, -.3), 70, warm, 1.0); area('rim', (-.5, 3.8, .4), (0, 3.1, -.3), 40, cool, 1.0)
            cam((.1, 2.45, .25), (0, 3.08, -.3), 38, 1.6)
    elif name == 'group_end':
        cast({'kai': dict(loc=(0, 1.0, .15), expr='bored', rot=(0, 0, 0), arms={'arm_l': (0, -15, 0), 'arm_r': (0, 15, 0)}),
              'nora': dict(loc=(-.75, 1.15, .15), expr='neutral', rot=(0, 0, -15), arms={'arm_r': (-40, 0, -40)}),
              'leo': dict(loc=(.75, 1.1, .15), expr='smirk', rot=(0, 0, 20), arms={'arm_l': (-40, 0, 40)})})
        area('key', (1.8, -1.5, 2), (0, 1.1, .7), 160, warm, 3); area('rim', (-1, 3.5, 2), (0, 1.1, .8), 100, cool, 3)
        point('lamp', (.4, .3, .5), 20, (1, .6, .3), .05)
        cam((0, -2.0, 1.0), (0, 1.1, .66), 32, 4.0)

if name in ('top_wide', 'cu_leo', 'cu_kai', 'kai_crack', 'slope_up', 'kai_caught', 'cu_nora'): slope_plate()
else: debris_plate()
sc.render.filepath = f'{OUT}/{name}.png'
bpy.ops.render.render(write_still=True)
print('WROTE', sc.render.filepath)
