"""Pick a planet to spend one night on (Mercury, Venus, Mars, Uranus): one high-res Cycles still per plate,
animated in 2D by nights_anim.py.   python3 nights_plate.py <plate> [res_scale]  -> nights/plates/<plate>.png
plates: uranus (real-data Uranus at solstice: tipped 97.8°, one whole hemisphere in darkness), lineup (2x2 NOT TO SCALE),
        mercury_globe, venus_globe, mars_globe (each half in night), mercury_sunset (Sun on the horizon, airless black sky),
        mercury_night (starlight + suit lamp), venus_night (dark basalt slabs under murky air, suit lamp),
        mars_night (after sunset: blue afterglow in the west, Earth as the evening star), uranus_clouds (floating in the dark cloud deck)"""
import sys, math, os
sys.path.insert(0, '/home/claude/b3d')
import bpy, kit
from mathutils import Vector
name = sys.argv[1]; S = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
OUT = '/home/claude/b3d/nights/plates'; os.makedirs(OUT, exist_ok=True)
W, H = int(1080 * S), int(1920 * S)
sc = kit.reset(res=(W, H), samples=int(os.environ.get('SAMPLES', 40)))
sc.cycles.adaptive_threshold = 0.03; sc.cycles.max_bounces = 4; sc.cycles.diffuse_bounces = 2

def track(o, target):
    c = o.constraints.new('TRACK_TO'); c.target = target; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'

def spot(loc, aim, energy, angle=40, color=(1, .93, .82), soft=.3):
    d = bpy.data.lights.new('lamp', 'SPOT'); d.energy = energy; d.color = color; d.spot_size = math.radians(angle); d.spot_blend = .6
    d.shadow_soft_size = .05; ob = kit.link(bpy.data.objects.new('lamp', d)); ob.location = loc
    ob.rotation_euler = (Vector(aim) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler(); return ob

def point(loc, energy, color, r=.1):
    d = bpy.data.lights.new('p', 'POINT'); d.energy = energy; d.color = color; d.shadow_soft_size = r
    ob = kit.link(bpy.data.objects.new('p', d)); ob.location = loc; return ob

def emit(name, color, strength):
    return kit.mat_emit(name, color, strength)

def sky_gradient(stops, stars=.35):
    """night sky: real Milky Way star map added over a vertical color gradient (stops = [(pos, rgb), ...] by height)"""
    w = bpy.data.worlds.new('sky'); sc.world = w; nt, N, L = kit.nodes(w)
    out = N.new('ShaderNodeOutputWorld'); bg = N.new('ShaderNodeBackground'); tc = N.new('ShaderNodeTexCoord')
    env = N.new('ShaderNodeTexEnvironment'); env.image = bpy.data.images.load(kit.tex_path('stars_milky_way.jpg'), check_existing=True)
    L.new(tc.outputs['Generated'], env.inputs['Vector'])
    gm = N.new('ShaderNodeGamma'); gm.inputs['Gamma'].default_value = 1.8; L.new(env.outputs['Color'], gm.inputs['Color'])
    sm = N.new('ShaderNodeVectorMath'); sm.operation = 'SCALE'; sm.inputs['Scale'].default_value = stars; L.new(gm.outputs[0], sm.inputs[0])
    sep = N.new('ShaderNodeSeparateXYZ'); L.new(tc.outputs['Generated'], sep.inputs[0])
    cr = N.new('ShaderNodeValToRGB'); L.new(sep.outputs['Z'], cr.inputs['Fac'])
    els = cr.color_ramp.elements
    els[0].position, els[0].color = stops[0][0], (*stops[0][1], 1); els[1].position, els[1].color = stops[1][0], (*stops[1][1], 1)
    for p, c in stops[2:]: e = els.new(p); e.color = (*c, 1)
    ad = N.new('ShaderNodeVectorMath'); ad.operation = 'ADD'; L.new(sm.outputs[0], ad.inputs[0]); L.new(cr.outputs['Color'], ad.inputs[1])
    L.new(ad.outputs[0], bg.inputs['Color']); bg.inputs['Strength'].default_value = 1.0; L.new(bg.outputs[0], out.inputs['Surface'])

def venus_globe(R):
    """featureless pale-yellow sulfuric-acid cloud deck, as in visible-light photos (Mariner 10 / MESSENGER natural color)"""
    m = bpy.data.materials.new('venus'); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled')
    tc = N.new('ShaderNodeTexCoord'); mp = N.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (1, 1, 5); L.new(tc.outputs['Object'], mp.inputs['Vector'])
    nz = kit._noise(N, L, mp.outputs[0], 2.2, 6, .55); cr = N.new('ShaderNodeValToRGB')
    cr.color_ramp.elements[0].color = (.72, .6, .36, 1); cr.color_ramp.elements[1].color = (.93, .86, .62, 1)
    cr.color_ramp.elements[0].position = .3; cr.color_ramp.elements[1].position = .7
    L.new(nz.outputs['Fac'], cr.inputs['Fac']); L.new(cr.outputs['Color'], bs.inputs['Base Color']); bs.inputs['Roughness'].default_value = .95
    bs.inputs['Specular IOR Level'].default_value = .1; L.new(bs.outputs[0], o.inputs[0])
    s = kit._sphere(R); s.data.materials.append(m)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=R * 1.025, segments=128, ring_count=64); at = bpy.context.object
    at.data.materials.append(kit.mat_atmo((.95, .8, .45), 1.2)); at.visible_shadow = False; at.parent = s
    for p in at.data.polygons: p.use_smooth = True
    return s

def globe(kind, R, loc=(0, 0, 0), face_lon=0.0):
    if kind == 'venus': ob = venus_globe(R); ob.location = loc; ob.rotation_euler = (math.radians(177), 0, 0); return ob
    tilt = {'mercury': .03, 'mars': 25.2, 'uranus': 97.8}[kind]
    root, spin, s = kit.planet(kind, R, tilt, face_lon=face_lon); root.location = loc
    if kind in ('mars', 'uranus'):
        a = kit._sphere(R * 1.02, 128, 64); a.data.materials.append(kit.mat_atmo((.85, .45, .3) if kind == 'mars' else (.55, .85, .95), .9 if kind == 'mars' else 1.6))
        a.parent = root; a.visible_shadow = False
    return root

def grey_ground(seed=3, size=160):
    """Mercury: grey, cratered, airless regolith (MESSENGER color views are grey-brown)"""
    t = kit.terrain(size=size, height=1.3, scale=5, kind='rock', seed=seed, res=7); t.location.z = -.4
    cr = [n for n in t.active_material.node_tree.nodes if n.type == 'VALTORGB'][0]
    cr.color_ramp.elements[0].color = (.16, .15, .14, 1); cr.color_ramp.elements[1].color = (.42, .4, .37, 1)
    rock = kit.mat_principled('boulder', (.3, .29, .27), rough=.9)
    import random; r = random.Random(seed)
    for k in range(26):   # boulders and small crater rims
        x, y = r.uniform(-9, 9), r.uniform(3, 40); s_ = r.uniform(.15, .6)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=s_, location=(x, y, -.25)); b = bpy.context.object
        b.scale = (1, r.uniform(.7, 1.3), r.uniform(.4, .8)); b.data.materials.append(rock); kit.smooth(b, 1)
    for k in range(5):
        x, y = r.uniform(-12, 12), r.uniform(10, 50); rr = r.uniform(1.5, 4)
        bpy.ops.mesh.primitive_torus_add(major_radius=rr, minor_radius=rr * .16, location=(x, y, -.35)); tr = bpy.context.object
        tr.scale = (1, 1, .35); tr.data.materials.append(rock); kit.smooth(tr, 1)
    TER.append(t); return t

TER = []
def gz(x, y):
    """ground height under (x, y) on the displaced terrain (ray cast from above), so feet and cameras sit on the ground"""
    if not TER: return 0.0
    bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get()
    hit, loc, *_ = sc.ray_cast(dg, Vector((x, y, 50)), Vector((0, 0, -1)))
    return loc.z if hit else 0.0

def cam_on(x, y, h, look, lens):
    z = gz(x, y) + h; return kit.camera((x, y, z), (look[0], look[1], gz(look[0], look[1]) + look[2]), lens=lens)

def astro(loc, rot_z=0.0, scale=1.0, lamp=True, lamp_aim=None, lamp_e=60):
    root, limbs = kit.astronaut('astro'); loc = (loc[0], loc[1], gz(loc[0], loc[1]) + .93 * scale + loc[2]); root.location = loc; root.rotation_euler = (0, 0, rot_z); root.scale = (scale,) * 3
    if lamp:   # helmet lamp (suit light)
        hl = kit.mat_emit('hlamp', (1, .95, .85), 30)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=.06, location=(.22, -.26, 1.0)); b = bpy.context.object; b.data.materials.append(hl); b.parent = root
        bpy.context.view_layer.update()
        wl = root.matrix_world @ Vector((.22, -.4, 1.0))
        spot(tuple(wl), lamp_aim or tuple(wl + Vector((0, -6, -2.5))), lamp_e * 10, 38)
    return root, limbs

# ------------------------------------------------------------------ plates
if name == 'uranus':
    kit.world(strength=.18)
    u = globe('uranus', 3.0)                       # axis -> ~+X; Sun along +X = northern summer solstice: south half in 42-year night
    kit.sun_lamp((1, -.25, .05), 4.2, (1, .98, .95))
    cam, _ = kit.camera((-4.2, -17.5, 1.2), (.4, 0, .3), lens=58)

elif name == 'lineup':
    kit.world(strength=.16)
    for kind, x, z in (('mercury', -1.2, 1.25), ('venus', 1.2, 1.25), ('mars', -1.2, -1.25), ('uranus', 1.2, -1.25)):
        globe(kind, 1.0, (x, 0, z))
    kit.sun_lamp((1, -.55, .25), 4.0)
    cam, _ = kit.camera((0, -17, -.2), (0, 0, -.2), lens=60)

elif name in ('mercury_globe', 'venus_globe', 'mars_globe'):
    kit.world(strength=.18); k = name.split('_')[0]
    globe(k, 3.0, face_lon={'mercury': 40, 'venus': 0, 'mars': -60}[k])
    kit.sun_lamp((1, -.35, .15), 4.2 if k != 'venus' else 3.2)
    cam, _ = kit.camera((-2.8, -17.5, .6), (.6, 0, .2), lens=58)

elif name == 'mercury_sunset':
    kit.world(strength=.22)                         # no air: black sky, stars, no glow around the Sun
    grey_ground(3)
    sun = kit.sun_sphere(1.3, 40); sun.location = (5.5, 70, 2.3)        # disc sitting on the horizon, straight ahead
    kit.sun_lamp((.08, 1, .035), 7.0, (1, .97, .92))                     # grazing light from ahead: very long shadows toward us
    kit.sun_lamp((-.3, -.6, .6), .06, (.6, .7, 1.0))
    astro((0.6, 4.0, 0), rot_z=math.radians(170), lamp=False)
    cam, _ = cam_on(-1.6, -2.4, 1.2, (2.6, 30, 2.0), 26)

elif name == 'mercury_night':
    kit.world(strength=.32)
    grey_ground(3)
    kit.sun_lamp((-.3, .5, .8), .12, (.55, .65, 1.0))                    # starlight only (brightened so the eye can read the ground)
    kit.sun_lamp((-1, -.3, .3), .25, (.6, .7, 1.0))                       # cool rim on the suit
    astro((0.4, 4.0, 0), rot_z=math.radians(200), lamp=True, lamp_aim=(1.2, 10, -.4), lamp_e=120)
    cam, _ = cam_on(-2.2, -2.6, 1.4, (.6, 6, 1.0), 30)

elif name == 'venus_night':
    sky_gradient([(0.0, (.05, .02, .006)), (.15, (.02, .008, .003)), (.4, (.006, .003, .001))], stars=0.0)   # no stars: overcast acid clouds
    t = kit.terrain(size=120, height=.45, scale=3, kind='volcanic', seed=2, res=7); t.location.z = -.12
    bs = [n for n in t.active_material.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'][0]
    cr = [n for n in t.active_material.node_tree.nodes if n.type == 'VALTORGB'][0]
    cr.color_ramp.elements[0].color = (.07, .05, .04, 1); cr.color_ramp.elements[1].color = (.26, .2, .16, 1)   # dark basalt slabs (Venera 13 panoramas)
    TER.append(t)
    bs.inputs['Emission Color'].default_value = (1, .18, .04, 1); bs.inputs['Emission Strength'].default_value = .025  # faint thermal glow of ~740 K rock
    astro((0.2, 3.6, 0), rot_z=math.radians(195), lamp=True, lamp_aim=(1.0, 9, -.6), lamp_e=90)
    point((0, 2, 4), 60, (1, .5, .2), 3); kit.sun_lamp((-1, -.3, .4), .12, (1, .55, .3))
    cam, _ = cam_on(-2.3, -2.8, 1.3, (.5, 6, .9), 30)
    bpy.ops.mesh.primitive_cube_add(size=60, location=(0, 25, 10)); v = bpy.context.object      # thick murky lower atmosphere
    mv = bpy.data.materials.new('murk'); nt, N, L = kit.nodes(mv); o = N.new('ShaderNodeOutputMaterial'); pv = N.new('ShaderNodeVolumePrincipled')
    pv.inputs['Color'].default_value = (1, .6, .3, 1); pv.inputs['Density'].default_value = .02; L.new(pv.outputs[0], o.inputs['Volume']); v.data.materials.append(mv)
    sc.cycles.volume_step_rate = 6.0; sc.cycles.volume_bounces = 0

elif name == 'mars_night':
    # ~40 min after sunset: Mars twilight is blue near the set Sun (Curiosity/InSight sunset images), dusty butterscotch-grey above
    sky_gradient([(0.0, (.07, .12, .2)), (.06, (.035, .06, .1)), (.16, (.012, .018, .03)), (.4, (.002, .003, .006))], stars=.6)
    t = kit.terrain(size=160, height=2.2, scale=6, kind='desert', seed=4, res=7); t.location.z = -.6
    cr = [n for n in t.active_material.node_tree.nodes if n.type == 'VALTORGB'][0]
    cr.color_ramp.elements[0].color = (.32, .12, .05, 1); cr.color_ramp.elements[1].color = (.62, .3, .14, 1)   # rust-orange regolith
    TER.append(t)
    kit.sun_lamp((.1, 1, .05), .5, (.45, .6, 1.0))                       # faint blue afterglow from the west (ahead of camera)
    kit.sun_lamp((-.4, -.3, .8), .06, (.7, .75, 1.0))
    e = kit.mat_emit('earthdot', (.75, .85, 1.0), 400)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=.35, location=(-5, 70, 9)); bpy.context.object.data.materials.append(e)   # Earth: evening star in the west
    astro((-0.2, 3.6, 0), rot_z=math.radians(180), lamp=False)
    cam, _ = cam_on(-1.9, -2.6, 1.1, (-.9, 30, 4.0), 24)

elif name == 'uranus_clouds':
    sky_gradient([(0.0, (.008, .025, .03)), (.15, (.004, .012, .018)), (.4, (.0, .002, .004))], stars=.25)
    def layer(z, size, color, lo, hi, sc_, alpha):
        bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, z)); p = bpy.context.object
        m = bpy.data.materials.new('cl'); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); tc = N.new('ShaderNodeTexCoord')
        mp = N.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (1, 3, 1); L.new(tc.outputs['Generated'], mp.inputs['Vector'])
        nz = kit._noise(N, L, mp.outputs[0], sc_ * 6, 6, .55)
        mr = N.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value = lo; mr.inputs['From Max'].default_value = hi; L.new(nz.outputs['Fac'], mr.inputs['Value'])
        ml = N.new('ShaderNodeMath'); ml.operation = 'MULTIPLY'; ml.inputs[1].default_value = alpha; L.new(mr.outputs[0], ml.inputs[0])
        d = N.new('ShaderNodeBsdfDiffuse'); d.inputs['Color'].default_value = (*color, 1)
        tr = N.new('ShaderNodeBsdfTransparent'); mx = N.new('ShaderNodeMixShader')
        L.new(ml.outputs[0], mx.inputs['Fac']); L.new(tr.outputs[0], mx.inputs[1]); L.new(d.outputs[0], mx.inputs[2]); L.new(mx.outputs[0], o.inputs[0])
        p.data.materials.append(m); p.visible_shadow = False; return p
    for k, (z, a) in enumerate(((-3.0, 1.0), (-1.6, .8), (-.6, .55), (2.5, .35), (4.5, .5))):
        layer(z, 220, (.55, .8, .85), .4, .72, 1.2 + k * .4, a)          # methane-ice / hydrogen-sulfide haze decks, pale cyan
    kit.sun_lamp((-.2, .4, .9), .04, (.6, .85, .95))                      # no sunlight: only faint starlight from above
    astro((0, 3.0, .6), rot_z=math.radians(200), lamp=True, lamp_aim=(.6, 9, -1.6), lamp_e=90)
    cam, _ = kit.camera((-2.4, -2.6, 1.6), (.3, 5, .6), lens=28)

sc.render.filepath = f'{OUT}/{name}.png'; bpy.ops.render.render(write_still=True); print('ok', name)
