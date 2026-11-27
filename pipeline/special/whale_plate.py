"""WYR: gulped by a whale or stuck in quicksand? One Cycles still per plate (animated in 2D by whale_anim.py).
python3 whale_plate.py <plate> [res_scale]  -> whale/plates/<plate>.png
Ocean plates (procedural humpback, kit.humpback): lunge (mouth wide open toward camera, a diver in front: hook), side (gliding side view),
  diver (diver 45 ft down near the sandy floor), surface (whale head rising through the surface, mouth open), kayak (gulp next to a kayak)
Quicksand plates (tidal flat at dusk, Leo stuck to the waist): flat, leo_cu, tide (water rolling in), lean (Leo leaning back, spread out)"""
import sys, math, os
sys.path.insert(0, '/home/claude/b3d')
import bpy, kit
from mathutils import Vector
name = sys.argv[1]; S = float(sys.argv[2]) if len(sys.argv) > 2 else 0.75
OUT = '/home/claude/b3d/whale/plates'; os.makedirs(OUT, exist_ok=True)
W, H = int(1080 * S), int(1920 * S)
sc = kit.reset(res=(W, H), samples=int(os.environ.get('SAMPLES', 40)))
sc.cycles.adaptive_threshold = 0.03; sc.cycles.max_bounces = 5; sc.cycles.transmission_bounces = 4

def flat_world(col, strength=1.0):
    w = bpy.data.worlds.new('w'); sc.world = w; nt, N, L = kit.nodes(w)
    o = N.new('ShaderNodeOutputWorld'); bg = N.new('ShaderNodeBackground'); bg.inputs['Color'].default_value = (*col, 1)
    bg.inputs['Strength'].default_value = strength; L.new(bg.outputs[0], o.inputs['Surface'])

def sea_world(top=(.12, .42, .5), bottom=(.0, .02, .035), strength=1.0):
    """underwater ambient: bright teal toward the surface, near-black below (gradient on the view direction's Z)"""
    w = bpy.data.worlds.new('sea'); sc.world = w; nt, N, L = kit.nodes(w)
    o = N.new('ShaderNodeOutputWorld'); bg = N.new('ShaderNodeBackground'); tc = N.new('ShaderNodeTexCoord'); sep = N.new('ShaderNodeSeparateXYZ')
    L.new(tc.outputs['Generated'], sep.inputs[0]); mr = N.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value = .35; mr.inputs['From Max'].default_value = .9
    L.new(sep.outputs['Z'], mr.inputs[0]); mx = N.new('ShaderNodeMixRGB'); L.new(mr.outputs[0], mx.inputs['Fac'])
    mx.inputs[1].default_value = (*bottom, 1); mx.inputs[2].default_value = (*top, 1); L.new(mx.outputs[0], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = strength; L.new(bg.outputs[0], o.inputs['Surface'])

def water_volume(loc, size, density=.012, color=(.35, .75, .8), absorb=(.1, .45, .5)):
    bpy.ops.mesh.primitive_cube_add(location=loc); v = bpy.context.object; v.scale = size; v.name = 'watervol'
    m = bpy.data.materials.new('wv'); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); pv = N.new('ShaderNodeVolumePrincipled')
    pv.inputs['Color'].default_value = (*color, 1); pv.inputs['Density'].default_value = density; pv.inputs['Absorption Color'].default_value = (*absorb, 1)
    pv.inputs['Anisotropy'].default_value = .6; L.new(pv.outputs[0], o.inputs['Volume']); v.data.materials.append(m)
    sc.cycles.volume_step_rate = 6.0; sc.cycles.volume_bounces = 0; return v

def sun(direction, energy=4.0, color=(1, .95, .85)): return kit.sun_lamp(direction, energy, color)

def area(nm, loc, aim, energy, color=(1, 1, 1), size=4.0):
    li = bpy.data.lights.new(nm, 'AREA'); li.energy = energy; li.color = color; li.size = size
    o = kit.link(bpy.data.objects.new(nm, li)); o.location = loc
    o.rotation_euler = (Vector(aim) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler(); return o

def cam(loc, look, lens, fstop=None, focus=None):
    c, t = kit.camera(loc, look, lens=lens)
    if fstop:
        c.data.dof.use_dof = True; c.data.dof.focus_distance = focus or (Vector(loc) - Vector(look)).length; c.data.dof.aperture_fstop = fstop
    return c

def seafloor(z=-14, kind='sand'):
    ter = kit.terrain(size=160, height=1.2, scale=6, kind='desert', seed=2, res=7); ter.location = (0, 0, z)
    return ter

def diver(loc, rot=(0, 0, 0), h=1.0, pose='swim'):
    """a cartoon scuba diver (generic, illustration): black wetsuit + hood, yellow tank, mask, long fins"""
    kit.CAST['diver'] = dict(hair='beanie', hair_c=(.03, .03, .035), shirt=(.04, .045, .05), stripe=None, pants=(.04, .045, .05), voice='am_puck')
    root, parts = kit.character('diver', loc=loc, height=h)
    parts['face_mat'].node_tree.nodes['expr'].outputs[0].default_value = kit.EXPRS.index('scared')
    tank = kit.mat_principled('tank', (.95, .7, .05), .3, coat=.6)
    bpy.ops.mesh.primitive_cylinder_add(radius=.07, depth=.3, location=(0, .15, .45)); t = bpy.context.object; t.parent = root; t.data.materials.append(tank); kit.smooth(t, 1, .02)
    mask = kit.mat_principled('mask', (.02, .05, .07), .05, coat=1)
    bpy.ops.mesh.primitive_cube_add(location=(0, -.2, .83)); m = bpy.context.object; m.scale = (.17, .04, .07); m.parent = root; m.data.materials.append(mask); kit.smooth(m, 2, .02)
    fin = kit.mat_principled('fin', (.02, .02, .02), .5)
    for leg in ('leg_l', 'leg_r'):
        bpy.ops.mesh.primitive_cube_add(location=(0, -.08, -.3)); f = bpy.context.object; f.scale = (.06, .16, .01); f.parent = parts[leg]; f.data.materials.append(fin)
    if pose == 'swim':
        parts['arm_l'].rotation_euler = (math.radians(-60), math.radians(-30), 0); parts['arm_r'].rotation_euler = (math.radians(-40), math.radians(35), 0)
        parts['leg_l'].rotation_euler = (math.radians(20), 0, 0); parts['leg_r'].rotation_euler = (math.radians(-15), 0, 0)
    elif pose == 'flail':
        parts['arm_l'].rotation_euler = (0, math.radians(-150), 0); parts['arm_r'].rotation_euler = (0, math.radians(140), 0)
        parts['leg_l'].rotation_euler = (math.radians(30), math.radians(-20), 0); parts['leg_r'].rotation_euler = (math.radians(-25), math.radians(20), 0)
    root.rotation_euler = tuple(math.radians(a) for a in rot)
    return root, parts

# ------------------------------------------------------------------ quicksand set
def wet_sand_mat():
    """saturated tidal sand: dark wet sand with a glossy water film in the hollows and ripple marks"""
    m = bpy.data.materials.new('wetsand'); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled')
    tc = N.new('ShaderNodeTexCoord')
    wv = N.new('ShaderNodeTexWave'); wv.inputs['Scale'].default_value = .9; wv.inputs['Distortion'].default_value = 6; wv.inputs['Detail'].default_value = 4
    L.new(tc.outputs['Object'], wv.inputs[0])
    nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = .35; nz.inputs['Detail'].default_value = 6; L.new(tc.outputs['Object'], nz.inputs[0])
    wet = N.new('ShaderNodeMapRange'); wet.inputs['From Min'].default_value = .46; wet.inputs['From Max'].default_value = .56; L.new(nz.outputs['Fac'], wet.inputs[0])
    cmix = N.new('ShaderNodeMixRGB'); L.new(wet.outputs[0], cmix.inputs['Fac']); cmix.inputs[1].default_value = (.36, .27, .17, 1); cmix.inputs[2].default_value = (.12, .09, .06, 1)
    L.new(cmix.outputs[0], bs.inputs['Base Color'])
    rr = N.new('ShaderNodeMapRange'); rr.inputs['To Min'].default_value = .7; rr.inputs['To Max'].default_value = .04; L.new(wet.outputs[0], rr.inputs[0]); L.new(rr.outputs[0], bs.inputs['Roughness'])
    gr = N.new('ShaderNodeTexNoise'); gr.inputs['Scale'].default_value = 300; L.new(tc.outputs['Object'], gr.inputs[0])
    ad = N.new('ShaderNodeMath'); ad.operation = 'MULTIPLY_ADD'; L.new(wv.outputs['Fac'], ad.inputs[0]); ad.inputs[1].default_value = .7; L.new(gr.outputs['Fac'], ad.inputs[2])
    bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = .35; L.new(ad.outputs[0], bp.inputs['Height']); L.new(bp.outputs[0], bs.inputs['Normal'])
    L.new(bs.outputs[0], o.inputs[0]); return m

def tidal_flat(water_z=-.25, water_x=-30):
    bpy.ops.mesh.primitive_plane_add(size=240); g = bpy.context.object; g.data.materials.append(wet_sand_mat())
    s = g.modifiers.new('s', 'SUBSURF'); s.subdivision_type = 'SIMPLE'; s.levels = s.render_levels = 6
    tx = bpy.data.textures.new('dunes', 'CLOUDS'); tx.noise_scale = 6; d = g.modifiers.new('d', 'DISPLACE'); d.texture = tx; d.strength = .12; d.mid_level = .5
    # channel water (the sea / tide) as a big flat glossy plane, its edge at water_x
    bpy.ops.mesh.primitive_plane_add(size=1); w = bpy.context.object; w.scale = (100, 200, 1); w.location = (water_x - 100, 0, water_z)
    sea = kit.mat_principled('tidewater', (.02, .05, .06), .03); sea.node_tree.nodes['Principled BSDF'].inputs['IOR'].default_value = 1.333
    w.data.materials.append(sea)
    # ripple bump on the water
    return g, w

def sunk_ring(loc, r=.32):
    """the churned mound of liquefied wet sand around a stuck person's waist (glossy slurry, no hard edge)"""
    m = bpy.data.materials.new('slurry'); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); b = N.new('ShaderNodeBsdfPrincipled')
    b.inputs['Base Color'].default_value = (.16, .115, .075, 1); b.inputs['Roughness'].default_value = .3
    tc = N.new('ShaderNodeTexCoord'); nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 18; nz.inputs['Detail'].default_value = 8
    L.new(tc.outputs['Object'], nz.inputs[0]); bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = .5; L.new(nz.outputs['Fac'], bp.inputs['Height']); L.new(bp.outputs[0], b.inputs['Normal'])
    L.new(b.outputs[0], o.inputs[0])
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=1, location=loc); t = bpy.context.object; t.scale = (r * 1.25, r * 1.25, r * .45)
    d = t.modifiers.new('d', 'DISPLACE'); tx = bpy.data.textures.new('lumps', 'CLOUDS'); tx.noise_scale = .08; d.texture = tx; d.strength = .12
    t.data.materials.append(m); kit.smooth(t, 1); return t

def dusk_sky(elev=6, rot=250, strength=.14, energy=3.2):
    kit.sky(sun_elevation=elev, sun_rotation=rot, strength=strength, sun_lamp_energy=energy)

def leo_stuck(loc=(0, 0, 0), expr='scared', arms='up', lean=0.0, h=1.4):
    root, parts = kit.character('leo', loc=(loc[0], loc[1], loc[2] - .3 * h), height=h)
    parts['face_mat'].node_tree.nodes['expr'].outputs[0].default_value = kit.EXPRS.index(expr)
    if arms == 'up':
        parts['arm_l'].rotation_euler = (0, math.radians(-145), 0); parts['arm_r'].rotation_euler = (0, math.radians(150), math.radians(10))
    elif arms == 'spread':
        parts['arm_l'].rotation_euler = (0, math.radians(-95), 0); parts['arm_r'].rotation_euler = (0, math.radians(95), 0)
    root.rotation_euler = (math.radians(-lean), 0, math.radians(15))
    sunk_ring((loc[0], loc[1], loc[2] + .005), .2 * h)
    return root, parts

# ------------------------------------------------------------------ plates
if name == 'lunge':     # HOOK: humpback lunging up at the camera, jaws wide, a tiny diver in front of the mouth
    sea_world((.1, .4, .48), (.0, .015, .03), 1.0)
    wh, info = kit.humpback(14, gape_deg=62, pouch=.75)
    wh.rotation_euler = (math.radians(4), math.radians(-28), math.radians(-78)); wh.location = (0, 0, 0)
    diver((-.5, -8.6, 3.7), rot=(25, -10, 160), h=1.7, pose='flail')
    sun((.2, .3, 1), 4.0, (.9, 1, .95))
    area('under', (0, -14, -6), (0, -5, 2), 2500, (.3, .7, .8), 10)
    water_volume((0, 0, 0), (60, 60, 40), .016)
    cam((-3.0, -21, 1.6), (-.3, -6, 3.0), 30)

elif name == 'side':
    sea_world((.1, .38, .46), (.0, .02, .035), 1.0)
    wh, info = kit.humpback(14, 0, 0)
    wh.rotation_euler = (math.radians(6), math.radians(4), math.radians(-8)); wh.location = (0, 0, 0)
    sun((.1, .35, 1), 4.5, (.9, 1, .95)); area('under', (0, -10, -10), (0, 0, 0), 2000, (.3, .65, .75), 12)
    water_volume((0, 0, 0), (60, 60, 30), .012)
    cam((-1, -27, -1.2), (-.5, 0, -.6), 30)

elif name == 'diver':
    sea_world((.16, .42, .38), (.0, .03, .03), 1.0)     # Cape Cod water: greener
    seafloor(-1.6)
    dv, dp = diver((0, 0, 0), rot=(8, 15, 25), h=1.0); dp['face_mat'].node_tree.nodes['expr'].outputs[0].default_value = kit.EXPRS.index('neutral')
    # lobster trap on the floor
    tr = kit.mat_principled('trap', (.15, .4, .2), .6)
    bpy.ops.mesh.primitive_cube_add(location=(1.2, 1.5, -1.25)); b = bpy.context.object; b.scale = (.45, .3, .25); b.data.materials.append(tr)
    w = b.modifiers.new('w', 'WIREFRAME'); w.thickness = .02
    sun((.2, .2, 1), 4.0, (.85, 1, .9)); area('fill', (-3, -3, 2), (0, 0, 0), 260, (.5, .8, .7), 4)
    water_volume((0, 0, 0), (40, 40, 20), .07, (.35, .7, .55), (.2, .55, .45))
    cam((-.6, -3.8, .5), (.1, 0, -.1), 32, 3.5)

elif name in ('surface', 'kayak'):   # whale head breaking the surface, mouth open
    kit.sky(sun_elevation=14, sun_rotation=210, strength=.14, sun_lamp_energy=4.0)
    oc = kit.ocean(size=50, wave_scale=1.3, wind=7, choppy=1.3, resolution=14); md = oc.modifiers['Ocean']; md.repeat_x = md.repeat_y = 8; oc.location = (-200, -60, 0)
    wh, info = kit.humpback(14, gape_deg=58, pouch=.8, skin_top=(.006, .007, .009))
    wh.rotation_euler = (0, math.radians(float(os.environ.get('PITCH', -64))), math.radians(float(os.environ.get('YAW', 15)))); wh.location = (0, 10, -3.0)
    if name == 'kayak':
        k = kit.mat_principled('kayak', (.95, .25, .05), .3, coat=.6)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24); ky = bpy.context.object; ky.scale = (1.8, .32, .16); ky.location = (4.6, 6.4, .15)
        ky.rotation_euler = (math.radians(8), math.radians(-6), math.radians(25)); ky.data.materials.append(k); kit.smooth(ky, 1)
        root, parts = kit.character('kai', loc=(4.6, 6.4, -.02), height=.9)   # stand-in paddler (illustration)
        parts['face_mat'].node_tree.nodes['expr'].outputs[0].default_value = kit.EXPRS.index('scared')
        parts['arm_l'].rotation_euler = (0, math.radians(-140), 0); parts['arm_r'].rotation_euler = (0, math.radians(135), 0)
        cam((-.5, -3.5, 1.8), (2.6, 9, 1.9), 30)
    else:
        diver((3.4, 7.6, 2.4), rot=(70, 30, 40), h=1.7, pose='flail')
        cam((-.5, -3.5, 1.8), (2.4, 9, 2.4), 30)

elif name in ('flat', 'tide', 'leo_cu', 'lean'):
    dusk_sky(7, 250, .14, 3.4)
    water_x = -2.5 if name == 'tide' else -40
    g, w = tidal_flat(water_z=.04 if name == 'tide' else -.25, water_x=water_x)
    if name == 'lean':
        leo_stuck((0, 0, 0), 'worried', 'spread', lean=38)
        cam((2.4, -3.8, 2.2), (0, 0, .55), 30)
    else:
        leo_stuck((0, 0, 0), 'scared' if name != 'flat' else 'surprised', 'up')
        if name == 'leo_cu': cam((.5, -2.2, .9), (0, 0, .75), 40, 2.8)
        elif name == 'tide': cam((3.5, -5.5, 1.5), (-1.5, 0, .6), 26)
        else: cam((3.2, -6.5, 1.9), (-.4, 0, .5), 26)

sc.render.filepath = f'{OUT}/{name}.png'; bpy.ops.render.render(write_still=True); print('ok', name)
