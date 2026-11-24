"""What if you took off your helmet in space?  One high-res Cycles still per plate (animated in 2D by helmet_anim.py).
python3 helmet_plate.py <plate> [res_scale]  -> /home/claude/b3d/helmet/plates/<plate>.png
plates: bare (the mascot with its helmet OFF over the real Earth, scared face), suited (same shot, helmet on),
        helmet (the helmet alone on a transparent background, a sprite that 2D tumbles away),
        lungs (real BodyParts3D lungs + trachea + bronchi), heart (real heart wall, aorta, venae cavae),
        balloon (1960 high-altitude balloon gondola under the balloon, curved Earth below, ILLUSTRATION),
        chamber (inside a large steel vacuum test chamber, a suited test subject, 1960s Houston, ILLUSTRATION)."""
import sys, math, os, random
sys.path.insert(0, '/home/claude/b3d')
import bpy, kit
from mathutils import Vector
name = sys.argv[1]; S = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
OUT = '/home/claude/b3d/helmet/plates'; os.makedirs(OUT, exist_ok=True)
W, H = int(1080 * S), int(1920 * S)
sc = kit.reset(res=(W, H), samples=int(os.environ.get('SAMPLES', 40)))
sc.cycles.adaptive_threshold = 0.03; sc.cycles.max_bounces = 4

def look(loc, at, lens=32):
    cam, tgt = kit.camera(loc, at, lens=lens); sc.camera = cam; return cam

def dark_world(col=(0.004, 0.008, 0.02), strength=1.0):
    w = bpy.data.worlds.new('bg'); sc.world = w; nt, N, L = kit.nodes(w)
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

def delete(objs):
    for o in objs:
        for c in list(o.children_recursive): bpy.data.objects.remove(c, do_unlink=True)
        bpy.data.objects.remove(o, do_unlink=True)

SUN = Vector((-.55, -.75, .55)).normalized()

def helmet_parts(root):
    return [o for o in root.children if o.type == 'MESH' and o.location.z > .6]

def mascot(helmet=True, expr='scared'):
    root, limbs = kit.astronaut('you')
    limbs['arm1'].rotation_euler = (math.radians(-20), -math.radians(60), 0)      # right arm flung up toward the drifting helmet
    limbs['arm-1'].rotation_euler = (math.radians(15), math.radians(28), 0)
    limbs['leg1'].rotation_euler = (math.radians(14), -math.radians(9), 0); limbs['leg-1'].rotation_euler = (math.radians(-10), math.radians(6), 0)
    if not helmet:
        delete(helmet_parts(root))
        h = 1.7; ch, parts = kit.character('kai', loc=(0, 0, .74 - .8 * h), height=h)
        keep = {parts['head']} | {o for o in ch.children if o.type == 'MESH' and o.data.materials and 'hair' in o.data.materials[0].name}
        delete([o for o in list(ch.children) if o not in keep])
        parts['face_mat'].node_tree.nodes['expr'].outputs[0].default_value = kit.EXPRS.index(expr)
        ch.parent = root
    root.rotation_euler = (math.radians(6), math.radians(-8), math.radians(14))
    return root

def space_scene(helmet):
    kit.world(strength=.45)
    kit.sun_lamp(SUN, 4.2)
    er, spin = kit.earth(40, SUN, tilt_deg=0, clouds=True, atmo=True, face_lon=-95); er.location = (6, 70, -44)
    root = mascot(helmet); root.location = (0, 0, .25)
    area((3, -3, -2), (0, 0, .4), 120, (.45, .65, 1), 3)          # blue Earth-shine from below right
    look((0, -6.2, .9), (0, 0, .05), 40)

def p_bare(): space_scene(False)
def p_suited(): space_scene(True)

def p_helmet():
    sc.render.film_transparent = True
    kit.world(strength=.45); kit.sun_lamp(SUN, 4.2)
    root, limbs = kit.astronaut('h'); hp = helmet_parts(root)
    for o in list(root.children):
        if o not in hp and o.type != 'EMPTY': bpy.data.objects.remove(o, do_unlink=True)
    for o in list(root.children):
        if o.type == 'EMPTY': delete([o])
    area((3, -3, -2), (0, 0, .7), 120, (.45, .65, 1), 3)
    root.rotation_euler = (math.radians(-12), 0, math.radians(-28))
    look((0, -3.0, .74), (0, 0, .74), 50)

def studio(col=(.003, .006, .016)):
    dark_world(col, 1.0)
    area((-4, -5, 4), (0, 0, 0), 900, (1, .82, .7), 4)       # warm key
    area((5, 3, 2), (0, 0, 0), 700, (.35, .6, 1), 3)         # cool rim
    area((0, -6, -4), (0, 0, 0), 150, (.6, .7, 1), 4)

def p_lungs():
    studio()
    a = kit.anatomy(r'lobe of .*lung', r'middle lobe of lung', r'^trachea$', r'^bronchus$', size=3.0)
    look((0, -9.5, .5), (0, 0, -.55), 55)

def p_heart():
    studio((.004, .004, .012))
    a = kit.anatomy(r'^wall of heart$', r'ascending aorta', r'arch of aorta', r'superior vena cava', size=2.7)
    look((0, -9.5, .5), (0, 0, -.55), 55)

def p_balloon():
    """1960 open-gondola high-altitude balloon flight: the gondola hangs from load lines under a huge thin polyethylene balloon,
    ~31 km up: black sky, thin blue limb, curved Earth. Scales: gondola ~2 m, the balloon tens of meters (cropped)."""
    kit.world(strength=.35); kit.sun_lamp(SUN, 4.0)
    er, spin = kit.earth(100, SUN, tilt_deg=0, clouds=True, atmo=True, face_lon=-106)
    er.location = (0, 6, -105)      # stylized: the curve is exaggerated vs the real ~31 km view (labeled ILLUSTRATION)
    film = bpy.data.materials.new('poly'); nt, N, L = kit.nodes(film); o = N.new('ShaderNodeOutputMaterial')
    bs = N.new('ShaderNodeBsdfPrincipled'); bs.inputs['Base Color'].default_value = (.92, .93, .95, 1); bs.inputs['Roughness'].default_value = .25
    bs.inputs['Transmission Weight'].default_value = .55; bs.inputs['Alpha'].default_value = .85; L.new(bs.outputs[0], o.inputs[0])
    G = Vector((0, 6, .0))     # gondola center
    b = prim('uv_sphere', film, G + Vector((0, 0, 9.5)), (4.2, 4.2, 5.0), segments=96, ring_count=48); kit.smooth(b, 1)
    # vertical gores (seams) on the balloon
    seam = kit.mat_principled('seam', (.75, .76, .8), rough=.4)
    for k in range(16):
        a = 2 * math.pi * k / 16
        pts = [G + Vector((4.22 * math.sin(t) * math.cos(a), 4.22 * math.sin(t) * math.sin(a), 9.5 - 5.02 * math.cos(t))) for t in [i / 30 * math.pi for i in range(31)]]
        cd = bpy.data.curves.new('s', 'CURVE'); cd.dimensions = '3D'; cd.bevel_depth = .015; sp = cd.splines.new('POLY'); sp.points.add(len(pts) - 1)
        for p_, q in zip(sp.points, pts): p_.co = (*q, 1)
        kit.link(bpy.data.objects.new('seam', cd)).data.materials.append(seam)
    rope = kit.mat_principled('rope', (.55, .5, .4), rough=.8)
    for k in range(8):   # load lines from the balloon base down to the gondola top ring
        a = 2 * math.pi * k / 8; top = G + Vector((1.2 * math.cos(a), 1.2 * math.sin(a), 4.7)); bot = G + Vector((.6 * math.cos(a), .6 * math.sin(a), 1.25))
        d = top - bot; bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=.012, depth=d.length, location=(top + bot) / 2)
        c = bpy.context.object; c.rotation_euler = d.to_track_quat('Z', 'Y').to_euler(); c.data.materials.append(rope)
    al = kit.mat_principled('alu', (.75, .76, .78), rough=.35, metal=1); pad = kit.mat_principled('pad', (.85, .82, .7), rough=.8)
    prim('cube', pad, G + Vector((0, 0, -.35)), (1.0, 1.0, .5), size=1, bevel=.05)          # insulated open gondola (seat box)
    for x in (-.5, .5):
        for y in (-.5, .5): prim('cylinder', al, G + Vector((x, y, .45)), (.03, .03, .8), vertices=8)
    prim('cube', al, G + Vector((0, 0, 1.25)), (1.05, 1.05, .04), size=1)
    prim('cube', kit.mat_principled('inst', (.1, .1, .12), rough=.5), G + Vector((0, .45, .45)), (.6, .08, .35), size=1, bevel=.02)
    you, limbs = kit.astronaut('pilot'); you.scale = (.62, .62, .62); you.location = G + Vector((0, -.05, .45))
    for s in (1, -1): limbs[f'leg{s}'].rotation_euler = (math.radians(80), 0, 0)
    you.rotation_euler = (0, 0, math.radians(-20))
    area((3, 2, 0), G, 60, (.4, .6, 1), 3)
    look(G + Vector((3.6, -6.8, .3)), G + Vector((0, 0, 1.0)), 26)

def p_chamber():
    """inside a big steel thermal-vacuum test chamber (1960s Houston, ILLUSTRATION): ribbed cylindrical walls, grated floor,
    a suited test subject on a stand with an umbilical hose, viewport windows, cold floodlights."""
    dark_world((.003, .004, .007), 1.0)
    steel = kit.mat_pbr('steel'); grate = kit.mat_principled('grate', (.18, .19, .2), rough=.5, metal=1)
    Rr, Ln = 4.0, 14.0
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=Rr, depth=Ln, location=(0, 4, 2.2), rotation=(math.pi / 2, 0, 0), end_fill_type='NOTHING')
    cyl = bpy.context.object; cyl.data.materials.append(steel)
    sol = cyl.modifiers.new('s', 'SOLIDIFY'); sol.thickness = .1
    for k in range(12):   # stiffening rings
        y = -2.5 + k * 1.2
        bpy.ops.mesh.primitive_torus_add(major_radius=Rr - .04, minor_radius=.07, location=(0, y, 2.2), rotation=(math.pi / 2, 0, 0), major_segments=96)
        bpy.context.object.data.materials.append(steel)
    bpy.ops.mesh.primitive_circle_add(vertices=96, radius=Rr, fill_type='NGON', location=(0, 11, 2.2), rotation=(math.pi / 2, 0, 0)); bpy.context.object.data.materials.append(steel)
    prim('cube', grate, (0, 4, -1.0), (2.9, 7, .04), size=2)
    for k in range(-14, 15):
        prim('cube', grate, (k * .2, 4, -.95), (.012, 7, .03), size=2)
    # viewports on the back wall (warm control-room light behind)
    win = kit.mat_emit('port', (1, .78, .5), 4.0)
    for x, z in ((1.6, 3.4),):
        bpy.ops.mesh.primitive_circle_add(vertices=48, radius=.42, fill_type='NGON', location=(x, 10.95, z), rotation=(math.pi / 2, 0, 0)); bpy.context.object.data.materials.append(win)
        bpy.ops.mesh.primitive_torus_add(major_radius=.46, minor_radius=.06, location=(x, 10.93, z), rotation=(math.pi / 2, 0, 0)); bpy.context.object.data.materials.append(steel)
    # test subject: suited figure on a low stand, umbilical hose to the wall
    you, limbs = kit.astronaut('subject'); you.location = (0, 5.0, .05); you.scale = (1.05, 1.05, 1.05)
    prim('cylinder', grate, (0, 5.0, -.75), (.6, .6, .18), vertices=32)
    hose = kit.mat_principled('hose', (.12, .12, .13), rough=.6)
    pts = [Vector((0.2, 4.75, .2)), Vector((1.2, 4.3, -.4)), Vector((2.4, 5.0, -.7)), Vector((3.6, 6.0, .4))]
    cd = bpy.data.curves.new('hose', 'CURVE'); cd.dimensions = '3D'; cd.bevel_depth = .06; sp = cd.splines.new('NURBS'); sp.points.add(len(pts) - 1)
    for p_, q in zip(sp.points, pts): p_.co = (*q, 1)
    sp.use_endpoint_u = True; sp.order_u = 3; kit.link(bpy.data.objects.new('hose', cd)).data.materials.append(hose)
    for x, col, e in ((-2.6, (.7, .82, 1), 900), (2.6, (.7, .82, 1), 700)):
        area((x, 1.0, 5.4), (0, 5, .4), e, col, 1.2)
    area((0, 10.5, 3), (0, 5, .5), 120, (1, .75, .45), 3)
    pt((0, 3.5, 4.5), 120, (.8, .9, 1), .5)
    look((-1.2, -1.6, .55), (0, 5, .55), 24)

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
