"""WYR coldest vs hottest day on Earth: one high-res Cycles still per plate (animated in 2D by wyrtemp_anim.py).
python3 wyrtemp_plate.py <plate> [res_scale]  -> wyrtemp/plates/<plate>.png
plates: ice (Vostok-style station on the polar plateau, polar night), iceclose (frosted weather screen + station lights),
        plateau (endless East Antarctic ice sheet in noon twilight, July), ant (real Earth: Antarctica in July polar night),
        dv (real Earth: Death Valley, California), desert (Death Valley dunes + Panamint-style range in fierce heat),
        salt (Badwater-style salt polygons below sea level), pole (South Pole ceremonial pole at night, sauna door, steam)"""
import sys, math, os
sys.path.insert(0, '/home/claude/b3d')
import bpy, kit
from mathutils import Vector
name = sys.argv[1]; S = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
OUT = '/home/claude/b3d/wyrtemp/plates'; os.makedirs(OUT, exist_ok=True)
W, H = int(1080 * S), int(1920 * S)
sc = kit.reset(res=(W, H), samples=int(os.environ.get('SAMPLES', 48)))
sc.cycles.adaptive_threshold = 0.03; sc.cycles.max_bounces = 4

def add(prim, mat, loc, scale, rot=(0, 0, 0), bevel=0.0, sub=1, parent=None, **kw):
    getattr(bpy.ops.mesh, prim)(**kw); ob = bpy.context.object; ob.location = loc; ob.scale = scale; ob.rotation_euler = rot
    ob.data.materials.append(mat); kit.smooth(ob, sub, bevel)
    if parent: ob.parent = parent
    return ob

def darken(ob, col):
    bs = [n for n in ob.data.materials[0].node_tree.nodes if n.type == 'BSDF_PRINCIPLED'][0]
    for lk in list(bs.inputs['Base Color'].links): ob.data.materials[0].node_tree.links.remove(lk)
    bs.inputs['Base Color'].default_value = (*col, 1)

def area(loc, aim, energy, size, color):
    d = bpy.data.lights.new('a', 'AREA'); d.energy = energy; d.size = size; d.color = color
    ob = kit.link(bpy.data.objects.new('a', d)); ob.location = loc
    ob.rotation_euler = (Vector(aim) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler(); return ob

def point(loc, energy, color, r=.1):
    d = bpy.data.lights.new('p', 'POINT'); d.energy = energy; d.color = color; d.shadow_soft_size = r
    ob = kit.link(bpy.data.objects.new('p', d)); ob.location = loc; return ob

def night_world(horizon=(.02, .05, .09), zenith=(.0, .004, .012), glow=None, stars=.35):
    """polar-night sky: real Milky Way star map over a navy gradient; optional low twilight glow band (noon twilight in July at 78°S)"""
    w = bpy.data.worlds.new('night'); sc.world = w; nt, N, L = kit.nodes(w)
    out = N.new('ShaderNodeOutputWorld'); bg = N.new('ShaderNodeBackground'); tc = N.new('ShaderNodeTexCoord')
    env = N.new('ShaderNodeTexEnvironment'); env.image = bpy.data.images.load(kit.tex_path('stars_milky_way.jpg'), check_existing=True)
    L.new(tc.outputs['Generated'], env.inputs['Vector'])
    gm = N.new('ShaderNodeGamma'); gm.inputs['Gamma'].default_value = 1.8; L.new(env.outputs['Color'], gm.inputs['Color'])
    sm = N.new('ShaderNodeVectorMath'); sm.operation = 'SCALE'; sm.inputs['Scale'].default_value = stars; L.new(gm.outputs[0], sm.inputs[0])
    sep = N.new('ShaderNodeSeparateXYZ'); L.new(tc.outputs['Generated'], sep.inputs[0])
    cr = N.new('ShaderNodeValToRGB'); L.new(sep.outputs['Z'], cr.inputs['Fac'])
    cr.color_ramp.elements[0].position = 0.0; cr.color_ramp.elements[0].color = (*horizon, 1)
    cr.color_ramp.elements[1].position = .35; cr.color_ramp.elements[1].color = (*zenith, 1)
    if glow:
        e = cr.color_ramp.elements.new(.0); e.color = (*glow, 1); cr.color_ramp.elements[0].position = 0.0
        cr.color_ramp.elements[1].position = .06; cr.color_ramp.elements[1].color = (*horizon, 1)
        e2 = cr.color_ramp.elements.new(.4); e2.color = (*zenith, 1)
    ad = N.new('ShaderNodeVectorMath'); ad.operation = 'ADD'; L.new(sm.outputs[0], ad.inputs[0]); L.new(cr.outputs['Color'], ad.inputs[1])
    L.new(ad.outputs[0], bg.inputs['Color']); bg.inputs['Strength'].default_value = 1.0; L.new(bg.outputs[0], out.inputs['Surface'])

def snowfield(size=200, height=.35, seed=3, sastrugi=True):
    """flat polar plateau: gentle undulation + wind-carved sastrugi ridges (stretched noise), snow PBR with subsurface"""
    ter = kit.terrain(size=size, height=height, scale=8, kind='snow', seed=seed, res=8)
    m = ter.data.materials[0]; nt = m.node_tree; N, L = nt.nodes, nt.links; bs = [n for n in N if n.type == 'BSDF_PRINCIPLED'][0]
    if sastrugi:
        tc = N.new('ShaderNodeTexCoord'); mp = N.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (.35, 3.0, 1)
        L.new(tc.outputs['Object'], mp.inputs['Vector'])
        wv = N.new('ShaderNodeTexWave'); wv.inputs['Scale'].default_value = 1.6; wv.inputs['Distortion'].default_value = 9; wv.inputs['Detail'].default_value = 6
        L.new(mp.outputs[0], wv.inputs['Vector'])
        bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = .6; L.new(wv.outputs['Fac'], bp.inputs['Height'])
        L.new(bp.outputs['Normal'], bs.inputs['Normal'])
    bs.inputs['Base Color'].default_value = (.82, .88, .95, 1)
    for n in list(N):
        if n.type == 'VALTORGB':
            for lk in list(n.outputs['Color'].links): L.remove(lk)
    bs.inputs['Roughness'].default_value = .85; return ter

def station(loc=(0, 0, 0), rot=0.0):
    """generic inland Antarctic station (not a copy of any real building): raised modules on stilts, lit windows,
    a radio mast, fuel tanks and a white louvered weather screen"""
    root = kit.link(bpy.data.objects.new('station', None)); root.location = loc; root.rotation_euler = (0, 0, rot)
    wall = kit.mat_principled('wall', (.55, .1, .07), rough=.55)          # red-painted modules (common on polar stations)
    roof = kit.mat_principled('roof', (.75, .77, .8), rough=.4, metal=.4)
    steel = kit.mat_principled('steel', (.35, .36, .38), rough=.35, metal=1)
    win = kit.mat_emit('window', (1, .62, .28), 9)
    for k, (x, y, l) in enumerate(((0, 0, 7), (8.2, 1.2, 5), (-6.8, -1.5, 4.5))):
        add('primitive_cube_add', wall, (x, y, 2.2), (l / 2, 1.5, 1.1), bevel=.08, parent=root)
        add('primitive_cube_add', roof, (x, y, 3.35), (l / 2 + .1, 1.6, .08), bevel=.03, parent=root)
        for j in range(int(l / 1.4)):
            add('primitive_cube_add', win, (x - l / 2 + .8 + j * 1.4, y - 1.52, 2.35), (.32, .02, .28), sub=0, parent=root)
        for sx in (-l / 2 + .4, l / 2 - .4):
            for sy in (-1.2, 1.2): add('primitive_cylinder_add', steel, (x + sx, y + sy, .55), (.09, .09, .6), vertices=16, parent=root)
    add('primitive_cylinder_add', steel, (3.5, 2.5, 6), (.05, .05, 6), vertices=12, parent=root)              # radio mast
    for h in (4, 8, 11.5): add('primitive_torus_add', steel, (3.5, 2.5, h), (.35, .35, .35), major_radius=1, minor_radius=.04, parent=root)
    red = kit.mat_emit('beacon', (1, .1, .05), 40); add('primitive_uv_sphere_add', red, (3.5, 2.5, 12.1), (.12, .12, .12), parent=root)
    tank = kit.mat_principled('tank', (.7, .72, .74), rough=.35, metal=.6)
    for k in range(3): add('primitive_cylinder_add', tank, (-12 + k * 2.4, 3.5, 1.1), (1, 1, 1.1), rot=(0, 0, 0), vertices=48, bevel=.05, parent=root)
    for x, y in ((-2, -1.6), (2.5, -1.6), (9.5, -.3)): point(root.matrix_world @ Vector((x, y - .8, 2.3)), 300, (1, .6, .3), .4)
    return root

def weather_screen(loc, scale=1.0):
    """white louvered thermometer screen (Stevenson-type) on legs, frosted"""
    root = kit.link(bpy.data.objects.new('screen', None)); root.location = loc; root.scale = (scale, scale, scale)
    white = kit.mat_principled('screenwhite', (.88, .9, .92), rough=.5); frost = kit.mat_pbr('snow', 'frost')
    leg = kit.mat_principled('leg', (.25, .26, .27), rough=.4, metal=.8)
    add('primitive_cube_add', white, (0, 0, 1.45), (.38, .32, .3), bevel=.02, parent=root)
    for k in range(9): add('primitive_cube_add', white, (0, -.325, 1.2 + k * .06), (.36, .012, .02), rot=(math.radians(35), 0, 0), sub=0, parent=root)
    add('primitive_cube_add', frost, (0, 0, 1.79), (.44, .37, .045), bevel=.03, sub=2, parent=root)          # snow cap on the roof
    for sx in (-.3, .3):
        for sy in (-.25, .25): add('primitive_cylinder_add', leg, (sx, sy, .6), (.025, .025, .6), vertices=12, sub=0, parent=root)
    return root

if name in ('ice', 'iceclose'):
    night_world(horizon=(.03, .07, .12), zenith=(.0, .005, .016), glow=(.05, .09, .13), stars=.55)
    moon = kit.sun_lamp((-.6, .5, .25), .9, (.55, .7, 1.0))                     # cold moonlight
    ter = snowfield(); st = station((0, 14, 0), math.radians(-8))
    ws = weather_screen((-3.0, 2.0, 0), 1.0)
    if name == 'ice': cam, _ = kit.camera((-6.5, -2.5, 1.2), (1.5, 14, 3.4), lens=24)
    else:
        cam, _ = kit.camera((-4.4, -.9, 1.35), (-3.0, 2.0, 1.55), lens=45, dof=None)
        cam.data.dof.use_dof = True; cam.data.dof.focus_object = ws; cam.data.dof.aperture_fstop = 2.0
        area((-1.6, .8, 2.4), (-3, 2, 1.4), 25, 1.0, (1, .65, .35))               # warm spill from a station window
    sc.view_settings.look = 'AgX - Medium High Contrast' if 'AgX - Medium High Contrast' in [i.identifier for i in sc.view_settings.bl_rna.properties['look'].enum_items] else sc.view_settings.look

elif name == 'plateau':
    night_world(horizon=(.07, .12, .17), zenith=(.0, .006, .02), glow=(.42, .26, .16), stars=.45)   # sun ~9° below the horizon at noon (July, 78°S)
    kit.sun_lamp((0, 1, .02), .5, (.9, .55, .35))                                # faint warm twilight from the north
    kit.sun_lamp((-.3, -.6, .4), .25, (.45, .6, 1.0))
    ter = snowfield(size=400, height=.6, seed=9)
    st = station((40, 160, 0), math.radians(10)); st.scale = (1, 1, 1)            # tiny far away: scale of the emptiness
    cam, _ = kit.camera((0, -10, 3.0), (0, 60, 1.0), lens=22)

elif name in ('ant', 'dv'):
    R = 10.0
    kit.world(strength=.12)
    if name == 'ant':
        FL = 106.84; tgt = kit.latlon(-78.46, 106.84, R, FL, 0); n = tgt.normalized()
        # July: the Sun sits over ~20°N, so all of inland Antarctica is in polar night (terminator near 70°S)
        sun = kit.latlon(20.5, 106.84 + 40, 1, FL, 0).normalized()
        north = (kit.latlon(-75, 106.84, R, FL, 0) - tgt).normalized()
        cam, _ = kit.camera(tuple(tgt + n * 13 + north * 6.5), tuple(tgt + north * 3.2), lens=30)
        root, spin = kit.earth(R, tuple(sun), tilt_deg=0, face_lon=FL, clouds=True, atmo=True)
        kit.sun_lamp(tuple(sun), 4.0)
    else:
        FL = -116.87; tgt = kit.latlon(36.46, -116.87, R, FL, 0); n = tgt.normalized()
        north = (kit.latlon(37.46, -116.87, R, FL, 0) - tgt).normalized(); side = n.cross(north)
        sun = (n * .85 + side * .35 + north * .35).normalized()                     # midsummer afternoon over the US Southwest
        root, spin = kit.earth(R, tuple(sun), tilt_deg=0, face_lon=FL, clouds=True, atmo=True)
        kit.sun_lamp(tuple(sun), 4.2)
        cam, _ = kit.camera(tuple(tgt + n * 5.5 - north * 2.8), tuple(tgt + north * .3), lens=30)
    from bpy_extras.object_utils import world_to_camera_view
    bpy.context.view_layer.update(); v = world_to_camera_view(sc, cam, tgt)
    open(f'{OUT}/{name}.txt', 'w').write(f'{v.x} {1 - v.y}')

elif name == 'desert':
    kit.sky(sun_elevation=5, sun_rotation=250, strength=.16, dust=1.0, sun_lamp_energy=6.0)
    dunes = kit.terrain(size=120, height=3.2, scale=2.2, kind='desert', seed=5, res=8); dunes.location = (0, 30, -.8)
    m = dunes.data.materials[0]; bs = [n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'][0]; bs.inputs['Roughness'].default_value = .95
    rng = kit.terrain(size=260, height=40, scale=1.2, kind='volcanic', seed=11, res=8); rng.location = (0, 300, -4); darken(rng, (.16, .1, .07))
    cam, _ = kit.camera((0, -8, 2.0), (4, 40, 2.6), lens=28)
    bpy.ops.mesh.primitive_cube_add(size=400); vol = bpy.context.object; vol.location = (0, 150, 30)   # hot dusty haze for depth
    mv = bpy.data.materials.new('haze'); nt, N, L = kit.nodes(mv); o = N.new('ShaderNodeOutputMaterial'); pv = N.new('ShaderNodeVolumePrincipled')
    pv.inputs['Color'].default_value = (1, .78, .55, 1); pv.inputs['Density'].default_value = .0009; L.new(pv.outputs[0], o.inputs['Volume']); vol.data.materials.append(mv)
    sc.cycles.volume_step_rate = 8.0; sc.cycles.volume_bounces = 0

elif name == 'salt':
    kit.sky(sun_elevation=9, sun_rotation=240, strength=.14, dust=3.0, sun_lamp_energy=5.0)
    bpy.ops.mesh.primitive_plane_add(size=400); fl = bpy.context.object
    m = bpy.data.materials.new('saltflat'); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled')
    tc = N.new('ShaderNodeTexCoord'); vo = N.new('ShaderNodeTexVoronoi'); vo.feature = 'DISTANCE_TO_EDGE'; vo.inputs['Scale'].default_value = .55
    L.new(tc.outputs['Object'], vo.inputs['Vector'])
    ridge = N.new('ShaderNodeMapRange'); ridge.inputs['From Min'].default_value = .0; ridge.inputs['From Max'].default_value = .08
    ridge.inputs['To Min'].default_value = 1; ridge.inputs['To Max'].default_value = 0; L.new(vo.outputs['Distance'], ridge.inputs['Value'])
    nz = kit._noise(N, L, tc.outputs['Object'], 9, 10, .6)
    mx = N.new('ShaderNodeMath'); mx.operation = 'ADD'; L.new(ridge.outputs[0], mx.inputs[0]); mul = N.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; mul.inputs[1].default_value = .25
    L.new(nz.outputs['Fac'], mul.inputs[0]); L.new(mul.outputs[0], mx.inputs[1])
    bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = .8; bp.inputs['Distance'].default_value = .2; L.new(mx.outputs[0], bp.inputs['Height'])
    cr = N.new('ShaderNodeValToRGB'); cr.color_ramp.elements[0].color = (.62, .58, .52, 1); cr.color_ramp.elements[1].color = (.93, .92, .9, 1)
    L.new(nz.outputs['Fac'], cr.inputs['Fac']); L.new(cr.outputs['Color'], bs.inputs['Base Color']); bs.inputs['Roughness'].default_value = .8
    L.new(bp.outputs['Normal'], bs.inputs['Normal']); L.new(bs.outputs[0], o.inputs[0]); fl.data.materials.append(m)
    disp = fl.modifiers.new('sub', 'SUBSURF'); disp.subdivision_type = 'SIMPLE'; disp.levels = disp.render_levels = 6
    rng = kit.terrain(size=300, height=44, scale=1.1, kind='volcanic', seed=21, res=8); rng.location = (0, 290, -4); darken(rng, (.2, .14, .11))
    cam, _ = kit.camera((0, -4, 1.3), (0, 30, .2), lens=24)

elif name == 'pole':
    night_world(horizon=(.04, .07, .11), zenith=(.0, .004, .014), glow=(.12, .12, .16), stars=.6)
    kit.sun_lamp((.5, .6, .2), .6, (.55, .7, 1.0))
    ter = snowfield(size=200, height=.25, seed=14)
    # ceremonial South Pole: red-and-white striped barber pole topped with a mirror sphere, ringed by flags (generic colors)
    stripes = bpy.data.materials.new('barber'); nt, N, L = kit.nodes(stripes); o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled')
    tc = N.new('ShaderNodeTexCoord'); wv = N.new('ShaderNodeTexWave'); wv.wave_type = 'BANDS'; wv.bands_direction = 'Z' if hasattr(wv, 'bands_direction') else wv.bands_direction
    wv.inputs['Scale'].default_value = 3.0; L.new(tc.outputs['Object'], wv.inputs['Vector'])
    cr = N.new('ShaderNodeValToRGB'); cr.color_ramp.interpolation = 'CONSTANT'; cr.color_ramp.elements[0].color = (.7, .03, .03, 1); cr.color_ramp.elements[1].position = .5
    cr.color_ramp.elements[1].color = (.92, .92, .92, 1); L.new(wv.outputs['Fac'], cr.inputs['Fac']); L.new(cr.outputs['Color'], bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = .25; bs.inputs['Coat Weight'].default_value = .6; L.new(bs.outputs[0], o.inputs[0])
    pole = add('primitive_cylinder_add', stripes, (0, 0, .75), (.07, .07, .75), vertices=48, sub=1)
    add('primitive_uv_sphere_add', kit.mat_pbr('silver', 'mirror'), (0, 0, 1.7), (.2, .2, .2), segments=64, ring_count=32, sub=1)
    add('primitive_cylinder_add', kit.mat_principled('base', (.2, .2, .22), rough=.5, metal=.6), (0, 0, .05), (.25, .25, .05), vertices=32)
    cols = [(.05, .15, .6), (.75, .05, .05), (.9, .9, .9), (.05, .45, .15), (.95, .65, .05), (.55, .0, .05), (.1, .35, .75), (.9, .45, .05)]
    for k in range(12):
        a = math.radians(k * 30); x, y = math.cos(a) * 4.2, math.sin(a) * 4.2
        add('primitive_cylinder_add', kit.mat_principled('fpole', (.7, .7, .72), rough=.3, metal=.8), (x, y, 1.5), (.03, .03, 1.5), vertices=12)
        fl = add('primitive_plane_add', kit.mat_principled(f'flag{k}', cols[k % len(cols)], rough=.7), (x + .45 * math.cos(a + 1.57), y + .45 * math.sin(a + 1.57), 2.65), (.45, .3, 1),
                 rot=(math.radians(90), 0, a + 1.57), sub=0)
        sw = fl.modifiers.new('w', 'WAVE'); sw.height = .05; sw.width = .4; sw.time_offset = k * 7
    # a building with an open, glowing door + steam (sauna side), off to the left
    bld = add('primitive_cube_add', kit.mat_principled('bld', (.3, .32, .36), rough=.5, metal=.3), (-9, 6, 2.2), (4, 3, 2.2), bevel=.1)
    door = add('primitive_cube_add', kit.mat_emit('door', (1, .55, .25), 14), (-6.6, 2.98, 1.1), (.6, .02, 1.05), sub=0)
    point((-6.6, 2.2, 1.4), 900, (1, .55, .25), .5)
    kit.volume_cloud(loc=(-6.4, 1.6, 1.8), size=(1.4, 1.0, 1.6), density=.5, kind='steam', seed=3)
    sc.cycles.volume_step_rate = 2.0; sc.cycles.volume_bounces = 0
    cam, _ = kit.camera((1.0, -2.7, 1.25), (-.6, .6, 1.35), lens=26)

sc.render.filepath = f'{OUT}/{name}.png'; bpy.ops.render.render(write_still=True); print('ok', name)
