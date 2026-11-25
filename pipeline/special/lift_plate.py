"""Story Short: The cables snapped on floor 80. One Cycles still per plate (animated in 2D by lift_anim.py).
python3 lift_plate.py <plate> [res_scale]  -> lift/plates/<plate>.png
Car plates: car_wide, car_scared, cu_leo, cu_leo_ask, cu_mia, cu_mia_serious, cu_kai_stairs
Shaft plates: shaft_up (from the car roof up the hoistway), shaft_down (looking down onto the car), shaft_side (car on its rails),
  safety_cu (safety brake jaws on the guide rail), governor (overspeed governor in the machine room), machine (traction sheave + hoist ropes)
History plates: otis (1854 platform demo, New York), esb_fog (Empire State Building in fog, B-25), esb_close (the bomber at the 79th floor),
  old_car (a 1940s elevator car with a brass gate), stairs (cast at the stairwell door)"""
import sys, math, os, random
sys.path.insert(0, '/home/claude/b3d')
import bpy, kit
from mathutils import Vector
kit.CAST['kai']['hair_c'] = (.2, .065, .015)
name = sys.argv[1]; S = float(sys.argv[2]) if len(sys.argv) > 2 else 0.75
OUT = '/home/claude/b3d/lift/plates'; os.makedirs(OUT, exist_ok=True)
W, H = int(1080 * S), int(1920 * S)
sc = kit.reset(res=(W, H), samples=int(os.environ.get('SAMPLES', 40)))
sc.cycles.adaptive_threshold = 0.03; sc.cycles.max_bounces = 5; sc.cycles.diffuse_bounces = 3

def area(nm, loc, aim, energy, color=(1, 1, 1), size=2.0):
    li = bpy.data.lights.new(nm, 'AREA'); li.energy = energy; li.color = color; li.size = size
    o = kit.link(bpy.data.objects.new(nm, li)); o.location = loc
    o.rotation_euler = (Vector(aim) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler(); return o

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

def label3d(txt, loc, size, mat, rot=(math.pi / 2, 0, 0)):
    bpy.ops.object.text_add(location=loc, rotation=rot); t = bpy.context.object; t.data.body = txt; t.data.size = size
    t.data.align_x = 'CENTER'; t.data.align_y = 'CENTER'; t.data.extrude = .002; t.data.materials.append(mat); return t

def cam(loc, look, lens, fstop=None, focus=None):
    c, t = kit.camera(loc, look, lens=lens)
    if fstop:
        c.data.dof.use_dof = True; c.data.dof.focus_distance = focus or (Vector(loc) - Vector(look)).length; c.data.dof.aperture_fstop = fstop
    return c

def brushed(nm='brushed', col=(.55, .57, .6), rough=.32):
    """brushed stainless: anisotropic-looking streaks via stretched noise in roughness + a faint bump"""
    m = bpy.data.materials.new(nm); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled')
    bs.inputs['Base Color'].default_value = (*col, 1); bs.inputs['Metallic'].default_value = 1.0
    tc = N.new('ShaderNodeTexCoord'); mp = N.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (220, 220, 3)
    nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 1.0; nz.inputs['Detail'].default_value = 6
    L.new(tc.outputs['Object'], mp.inputs[0]); L.new(mp.outputs[0], nz.inputs[0])
    mr = N.new('ShaderNodeMapRange'); mr.inputs['To Min'].default_value = rough - .1; mr.inputs['To Max'].default_value = rough + .12
    L.new(nz.outputs['Fac'], mr.inputs[0]); L.new(mr.outputs[0], bs.inputs['Roughness'])
    bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = .04; L.new(nz.outputs['Fac'], bp.inputs['Height']); L.new(bp.outputs[0], bs.inputs['Normal'])
    L.new(bs.outputs[0], o.inputs[0]); return m

def rope_mat():
    """steel wire rope: twisted strands (diagonal bands) with grease darkening"""
    m = bpy.data.materials.new('rope'); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled')
    bs.inputs['Metallic'].default_value = 1.0; bs.inputs['Roughness'].default_value = .45
    tc = N.new('ShaderNodeTexCoord'); wv = N.new('ShaderNodeTexWave'); wv.wave_type = 'BANDS'; wv.bands_direction = 'DIAGONAL'; wv.inputs['Scale'].default_value = 160
    L.new(tc.outputs['Object'], wv.inputs[0]); cr = N.new('ShaderNodeValToRGB'); cr.color_ramp.elements[0].color = (.12, .12, .12, 1); cr.color_ramp.elements[1].color = (.5, .5, .52, 1)
    L.new(wv.outputs['Color'], cr.inputs[0]); L.new(cr.outputs[0], bs.inputs['Base Color'])
    bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = .6; L.new(wv.outputs['Fac'], bp.inputs['Height']); L.new(bp.outputs[0], bs.inputs['Normal'])
    L.new(bs.outputs[0], o.inputs[0]); return m

def haze(density, loc=(0, 0, 1.2), scale=(1.2, 1.2, 1.3)):
    bpy.ops.mesh.primitive_cube_add(location=loc); v = bpy.context.object; v.scale = scale; v.name = 'haze'
    m = bpy.data.materials.new('haze'); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); vs = N.new('ShaderNodeVolumeScatter')
    vs.inputs['Density'].default_value = density; vs.inputs['Anisotropy'].default_value = .5; L.new(vs.outputs[0], o.inputs['Volume']); v.data.materials.append(m)

def cast(exprs, poses=None, y=.3, xs=None, height=1.05, turn=None):
    out = {}
    xs = xs or {'leo': -.5, 'kai': 0, 'mia': .5}
    for who, x in xs.items():
        if who not in exprs: continue
        root, parts = kit.character(who, loc=(x, y, 0), height=height)
        root.rotation_euler = (0, 0, math.radians((turn or {'leo': 8, 'kai': 0, 'mia': -8})[who]))
        parts['face_mat'].node_tree.nodes['expr'].outputs[0].default_value = kit.EXPRS.index(exprs[who])
        if poses and who in poses:
            for arm, rot in poses[who].items(): parts[arm].rotation_euler = rot
        out[who] = (root, parts)
    return out

# ================================================================== the modern elevator car (inside: 1.9 m wide, 1.6 m deep, 2.2 m high; doors at -Y)
CW, CD, CH = 1.9, 1.6, 2.2
def car_interior(flicker=False):
    flat_world((.005, .008, .012), 1.0)
    steel = brushed('carsteel', (.5, .53, .56)); dark = M('carfloor', (.03, .03, .035), .7)
    box('floor', (0, 0, -.02), (CW, CD, .04), dark, 0)
    # floor: dark granite-like tile with fine speckle
    fm = bpy.data.materials.new('granite'); nt, N, L = kit.nodes(fm); o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled')
    vo = N.new('ShaderNodeTexVoronoi'); vo.inputs['Scale'].default_value = 300; cr = N.new('ShaderNodeValToRGB')
    cr.color_ramp.elements[0].color = (.01, .01, .012, 1); cr.color_ramp.elements[1].color = (.09, .09, .1, 1)
    L.new(vo.outputs['Distance'], cr.inputs[0]); L.new(cr.outputs[0], bs.inputs['Base Color']); bs.inputs['Roughness'].default_value = .25; L.new(bs.outputs[0], o.inputs[0])
    bpy.data.objects['floor'].data.materials[0] = fm
    # back + side walls made of brushed panels with dark reveal gaps
    for k in range(3):
        box(f'back{k}', (-CW / 3 + k * CW / 3, CD / 2, CH / 2), (CW / 3 - .012, .02, CH - .02), steel, .004)
    for side in (-1, 1):
        for k in range(3):
            box(f'side{side}{k}', (side * CW / 2, -CD / 3 + k * CD / 3, CH / 2), (.02, CD / 3 - .012, CH - .02), steel, .004)
    box('reveal_b', (0, CD / 2 + .015, CH / 2), (CW, .01, CH), M('reveal', (.01, .01, .01), .8), 0)
    # wooden handrail on three walls
    wood = M('rail_wood', (.35, .17, .07), .35, coat=.5)
    rod('rail_b', (-CW / 2 + .1, CD / 2 - .06, .9), (CW / 2 - .1, CD / 2 - .06, .9), .02, wood)
    for side in (-1, 1):
        rod(f'rail_s{side}', (side * (CW / 2 - .06), -CD / 2 + .25, .9), (side * (CW / 2 - .06), CD / 2 - .1, .9), .02, wood)
    # ceiling with a warm light panel + downlights
    box('ceiling', (0, 0, CH), (CW, CD, .04), M('ceil', (.08, .08, .09), .6), 0)
    box('lightpanel', (0, 0, CH - .025), (CW * .7, CD * .6, .01), kit.mat_emit('ceil_led', (1.0, .78, .55), 0.4 if flicker else 1.2), 0)
    area('ceil', (0, 0, CH - .05), (0, 0, 0), 60 if flicker else 160, (1, .78, .55), 1.0)
    # front wall around the door opening (door open: we look in from the landing)
    front = M('front', (.1, .11, .12), .4, metal=.6)
    if name.startswith('cu_'): front = None
    if front:
        box('jamb_l', (-.75, -CD / 2, CH / 2), (.4, .05, CH), front, .005); box('jamb_r', (.75, -CD / 2, CH / 2), (.4, .05, CH), front, .005)
        box('header', (0, -CD / 2, CH - .15), (CW, .05, .3), front, .005)
    # floor indicator on the header (amber digits) + button panel on the right jamb (inside)
    label3d('80', (0, -CD / 2 + .03, CH - .15), .16, kit.mat_emit('digits', (1, .35, .08), 8), rot=(math.pi / 2, 0, math.pi))
    box('cop', (CW / 2 - .015, -CD / 2 + .3, 1.15), (.01, .22, .7), M('cop', (.06, .06, .07), .3, metal=.8), .003)
    for r in range(8):
        for cI in range(2):
            cyl(f'btn{r}{cI}', (CW / 2 - .025, -CD / 2 + .25 + cI * .1, .9 + r * .07), .018, .01,
                kit.mat_emit(f'btnlit{r}{cI}', (1, .5, .15), 2) if (r, cI) == (0, 0) else M('btnm', (.6, .6, .62), .25, 1), rot=(0, math.pi / 2, 0), verts=24)
    area('rim', (-.8, CD / 2 - .2, 1.9), (0, 0, .8), 25, (.35, .55, 1), .6)   # cool rim (moody blue)
    area('landing', (0, -2.4, 1.3), (0, 0, .8), 30 if flicker else 50, (.4, .6, 1.0), 2.5)

def car_plate():
    E_ = {'car_wide': dict(leo='bored', kai='neutral', mia='smirk'), 'car_scared': dict(leo='scared', kai='scared', mia='surprised'),
          'cu_leo': dict(leo='scared', kai='worried', mia='worried'), 'cu_leo_ask': dict(leo='worried', kai='neutral', mia='neutral'),
          'cu_mia': dict(mia='neutral', kai='worried', leo='scared'), 'cu_mia_serious': dict(mia='worried', kai='surprised', leo='surprised'),
          'cu_kai_stairs': dict(kai='smirk', leo='happy', mia='happy')}[name]
    P = {}
    up = {'arm_l': (0, math.radians(-150), 0), 'arm_r': (0, math.radians(150), 0)}
    if name == 'car_scared': P = {'leo': up, 'kai': {'arm_l': (0, math.radians(-120), 0), 'arm_r': (0, math.radians(120), 0)}}
    if name == 'cu_leo': P = {'leo': {'arm_r': (0, math.radians(160), 0), 'arm_l': (0, math.radians(-40), 0)}}
    if name == 'cu_mia': P = {'mia': {'arm_r': (math.radians(-60), math.radians(40), 0)}}
    car_interior(flicker=name in ('car_scared', 'cu_leo', 'cu_mia'))
    cast(E_, P)
    shots = {
        'car_wide': ((0, -2.6, 1.15), (0, .4, 1.0), 28, 5.6), 'car_scared': ((.15, -2.2, .9), (0, .4, 1.0), 26, 4.0),
        'cu_leo': ((-.68, -1.0, .98), (-.5, .3, .86), 42, 2.0), 'cu_leo_ask': ((-.62, -1.0, 1.0), (-.5, .3, .86), 50, 2.0),
        'cu_mia': ((.38, -1.0, 1.0), (.5, .3, .86), 50, 2.0), 'cu_mia_serious': ((.64, -1.0, 1.0), (.5, .3, .86), 50, 2.0),
        'cu_kai_stairs': ((-.15, -1.0, 1.0), (0, .3, .86), 50, 2.0),
    }
    loc, look, lens, fs = shots[name]; cam(loc, look, lens, fs)

# ================================================================== the hoistway (shaft): concrete walls, T-section guide rails, the car, 6 hoist ropes
def t_rail(x, z0, z1, steel, facing):
    """steel T-rail: a flange bolted to the wall bracket + a blade pointing at the car (the safeties grip the blade)"""
    L_ = z1 - z0; zc = (z0 + z1) / 2
    box(f'rail_fl{x}', (x + facing * -.05, 0, zc), (.012, .12, L_), steel, .002)
    box(f'rail_bl{x}', (x, 0, zc), (.1, .016, L_), steel, .002)
    br = M('bracket', (.15, .14, .12), .6, metal=.6)
    for z in range(int(z0) + 1, int(z1), 3):
        box(f'brk{x}{z}', (x + facing * -.1, 0, z), (.12, .2, .06), br, .004)

def dark_conc(nm, col=(.09, .095, .1)):
    m = bpy.data.materials.new(nm); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled')
    tc = N.new('ShaderNodeTexCoord'); nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 4; nz.inputs['Detail'].default_value = 12
    L.new(tc.outputs['Object'], nz.inputs[0]); cr = N.new('ShaderNodeValToRGB')
    cr.color_ramp.elements[0].color = (col[0] * .55, col[1] * .55, col[2] * .55, 1); cr.color_ramp.elements[1].color = (*col, 1)
    L.new(nz.outputs['Fac'], cr.inputs[0]); L.new(cr.outputs[0], bs.inputs['Base Color']); bs.inputs['Roughness'].default_value = .9
    bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = .4; L.new(nz.outputs['Fac'], bp.inputs['Height']); L.new(bp.outputs[0], bs.inputs['Normal'])
    L.new(bs.outputs[0], o.inputs[0]); return m

def shaft(car_z=0.0, top=40.0, bottom=-30.0, lights=True):
    flat_world((.0, .0, .0), 1.0)
    conc = dark_conc('shaftconc')
    SW, SD = 2.6, 2.3
    box('wall_back', (0, SD / 2, (top + bottom) / 2), (SW, .1, top - bottom), conc, 0)
    box('wall_front', (0, -SD / 2, (top + bottom) / 2), (SW, .1, top - bottom), conc, 0)
    for s in (-1, 1): box(f'wall_{s}', (s * SW / 2, 0, (top + bottom) / 2), (.1, SD, top - bottom), conc, 0)
    # landing door frames on the front wall every 3.6 m (floor height), with a faint line of light under each door
    dm = M('landing_door', (.2, .21, .22), .4, metal=.7); gl = kit.mat_emit('doorgap', (1, .75, .45), 4)
    z = math.floor(bottom / 3.6) * 3.6
    while z < top:
        box(f'ld{z}', (0, -SD / 2 + .06, z + 1.1), (1.0, .03, 2.2), dm, .005); box(f'lg{z}', (0, -SD / 2 + .075, z + .01), (1.0, .005, .012), gl, 0)
        if lights: point(f'sl{z}', (-SW / 2 + .15, SD / 2 - .15, z + 2.6), 5, (1, .6, .3), .05)
        z += 3.6
    steel = brushed('railsteel', (.45, .46, .48), .4)
    t_rail(-1.12, bottom, top, steel, -1); t_rail(1.12, bottom, top, steel, 1)
    # the car: cab box + sling (two uprights + crosshead) with guide shoes on the rails and the safety blocks under the cab
    frame = M('sling', (.12, .13, .14), .45, metal=.5); cab = M('cab', (.3, .32, .34), .35, metal=.8)
    box('cab', (0, 0, car_z + 1.15), (1.95, 1.65, 2.3), cab, .01)
    for s in (-1, 1):
        box(f'upright{s}', (s * 1.02, 0, car_z + 1.4), (.1, .18, 3.0), frame, .005)
        box(f'safety{s}', (s * 1.07, 0, car_z - .02), (.22, .2, .22), M('safety_red', (.55, .07, .05), .4, metal=.3), .01)
        box(f'shoe_t{s}', (s * 1.07, 0, car_z + 2.85), (.16, .14, .12), frame, .01)
    box('crosshead', (0, 0, car_z + 2.9), (2.15, .2, .18), frame, .01); box('plank', (0, 0, car_z - .04), (2.15, .2, .14), frame, .01)
    # 6 hoist ropes from the crosshead up to the machine
    rm = rope_mat()
    for k in range(6):
        x = -.2 + k * .08
        rod(f'rope{k}', (x, .02, car_z + 3.0), (x * .9, .02, top), .009, rm, 12)
        cyl(f'hitch{k}', (x, .02, car_z + 3.05), .02, .12, frame)
    # governor rope (thin) running down the side next to the rail, tied to the safety linkage
    rod('gov_rope', (1.2, -.12, bottom), (1.2, -.12, top), .005, rm, 8)
    box('gov_arm', (1.15, -.1, car_z + .1), (.1, .04, .25), frame, .005)
    return SW, SD

def shaft_plate():
    if name == 'shaft_up':
        SW, SD = shaft(car_z=0.0, top=60.0, bottom=-20.0)
        area('roofwork', (.6, -.6, 3.6), (0, 0, 8), 25, (1, .62, .32), .6)
        point('carlamp', (-.6, .5, 3.2), 30, (1, .7, .4), .1)
        cam((.35, -.75, 3.25), (0, .1, 40), 18)
    elif name == 'shaft_down':
        shaft(car_z=-14.0, top=10.0, bottom=-40.0)
        point('carroof', (0, 0, -10.6), 40, (1, .62, .32), .3)
        cam((.5, -.8, 6.0), (0, .05, -14), 20)
    elif name == 'shaft_side':
        shaft(car_z=0.0, top=20.0, bottom=-20.0)
        area('k', (1.0, -1.0, 1.5), (1.07, 0, .2), 60, (1, .62, .32), .5); area('f', (-.8, -1.0, 2.5), (0, 0, 1.2), 30, (.4, .6, 1), 1)
        cam((.25, -1.0, -1.7), (1.07, 0, .3), 20)
        area('under', (.3, -.6, -1.2), (1.07, 0, 0), 25, (1, .55, .3), .5)
    elif name == 'safety_cu':
        flat_world((.004, .005, .008), 1.0)
        steel = brushed('railsteel', (.45, .46, .48), .4)
        box('blade', (0, 0, 0), (.1, .016, 4), steel, .002); box('flange', (-.05, 0, 0), (.012, .12, 4), steel, .002)
        box('wall', (-.2, 0, 0), (.05, 2, 4), dark_conc('wallc'), 0)
        hous = M('safety_red', (.55, .07, .05), .4, metal=.3)
        box('hous1', (.04, .075, .0), (.2, .05, .32), hous, .01); box('hous_back', (.13, 0, 0), (.03, .2, .32), hous, .01)
        box('hous_top', (.04, 0, .18), (.2, .2, .04), hous, .01)
        jaw = M('jaw', (.35, .35, .37), .3, metal=1)
        for s in (-1, 1):
            box(f'jaw{s}', (.03, s * .028, 0), (.08, .02, .2), jaw, .002)
            for k in range(9): box(f'tooth{s}{k}', (.03, s * .017, -.08 + k * .02), (.08, .004, .006), jaw, 0)
        rod('linkage', (.12, -.06, .2), (.12, -.06, .6), .008, M('lnk', (.2, .2, .2), .4, 1))
        area('k', (.5, -.6, .4), (0, 0, 0), 30, (1, .62, .32), .4); area('f', (.4, .6, .5), (0, 0, 0), 10, (.4, .6, 1), .5)
        cam((.42, -.5, .3), (.03, 0, .0), 42, 2.8)
    elif False:
        # the safety block around the rail blade, with two hardened wedge jaws (serrated) touching the blade
        jaw = M('jaw', (.35, .35, .37), .3, metal=1)
        for s in (-1, 1):
            j = box(f'jaw{s}', (1.12, s * .022, -.02), (.08, .02, .14), jaw, .002)
            for k in range(7): box(f'tooth{s}{k}', (1.12, s * .012, -.08 + k * .02), (.08, .004, .006), jaw, 0)
        area('k', (.8, -.6, .3), (1.12, 0, 0), 30, (1, .62, .32), .3); area('f', (1.0, .6, .5), (1.12, 0, 0), 12, (.4, .6, 1), .5)
        cam((.92, -.42, .14), (1.1, 0, -.02), 40, 2.8)

def machine_room(kind):
    flat_world((.003, .004, .006), 1.0)
    conc = dark_conc('mrconc', (.12, .12, .12)); box('mr_floor', (0, 0, -.05), (8, 8, .1), conc, 0)
    box('mr_back', (0, 2.5, 1.5), (8, .1, 3), M('mrwall', (.1, .16, .18), .8), 0)
    paint = M('machine_paint', (.06, .22, .2), .4, coat=.3); steel = brushed('mrsteel', (.55, .56, .58), .35); rm = rope_mat()
    # traction machine: motor drum + big grooved sheave with 6 ropes dropping through the floor slot
    cyl('motor', (-1.0, .6, .55), .38, .9, paint, rot=(0, math.pi / 2, 0), verts=64)
    cyl('sheave', (-.25, .6, .55), .42, .16, steel, rot=(0, math.pi / 2, 0), verts=96)
    for k in range(6):
        bpy.ops.mesh.primitive_torus_add(major_radius=.425, minor_radius=.009, location=(-.31 + k * .024, .6, .55), rotation=(0, math.pi / 2, 0), major_segments=96)
        t = bpy.context.object; t.data.materials.append(rm)
        rod(f'mr_rope{k}', (-.31 + k * .024, .6 - .425, .55), (-.31 + k * .024, .6 - .425, -1), .009, rm, 12)
    box('brake', (-.62, .6, .55), (.18, .9, .3), M('brake_yel', (.75, .55, .05), .4), .01)
    box('slot', (-.25, .15, -.0), (.3, .2, .02), M('slot', (0, 0, 0), .9), 0)
    # overspeed governor: a grooved wheel on a small frame with two flyweights on its face, rope looping down
    gx = 1.0
    box('gov_base', (gx, .4, .15), (.4, .3, .3), paint, .01)
    cyl('gov_wheel', (gx, .4, .62), .22, .06, steel, rot=(math.pi / 2, 0, 0), verts=96)
    for s in (-1, 1):
        box(f'flyw{s}', (gx + s * .08, .36, .62), (.1, .03, .05), M('flyweight', (.75, .12, .08), .35, metal=.4), .008, rot=(0, s * .5, 0))
    cyl('gov_hub', (gx, .36, .62), .03, .03, steel, rot=(math.pi / 2, 0, 0))
    for s in (-1, 1): rod(f'gov_rope{s}', (gx + s * .22, .4, .62), (gx + s * .22, .4, -1), .005, rm, 8)
    label3d('GOVERNOR', (gx, .24, .2), .045, kit.mat_emit('tag', (.9, .9, .85), .8), rot=(math.pi / 2, 0, 0))
    area('work', (.3, -1.2, 2.2), (0, .5, .5), 70, (1, .62, .32), 1.2); area('cool', (-2, 2, 2.5), (0, .5, .5), 40, (.35, .55, 1), 2)
    if kind == 'governor': cam((gx + .35, -.75, .95), (gx, .4, .58), 45, 2.8)
    else: cam((.4, -1.1, .45), (-.3, .6, .4), 32, 4.0)

# ================================================================== 1854: Otis's platform demonstration (New York, Crystal Palace exhibition hall)
def otis_plate():
    flat_world((.01, .012, .018), 1.0)
    floor = box('hall_floor', (0, 0, -.05), (30, 30, .1), M('boards', (.2, .12, .06), .6), 0)
    wood = M('tower_wood', (.32, .18, .08), .55); iron = M('iron', (.08, .08, .09), .45, metal=.8)
    # two tall guide posts with a toothed ratchet strip on the inner faces (the safety's spring catches these teeth)
    for s in (-1, 1):
        box(f'post{s}', (s * .9, 0, 3), (.18, .18, 6), wood, .01)
        for k in range(40): box(f'tooth{s}{k}', (s * .8, 0, .4 + k * .14), (.03, .12, .05), iron, 0, rot=(0, s * .5, 0))
    box('beam', (0, 0, 6.05), (2.2, .2, .2), wood, .01)
    cyl('pulley', (0, -.05, 6.25), .25, .08, iron, rot=(math.pi / 2, 0, 0))
    # the platform (a wide open hoist with a rail), raised high, loaded with crates; the spring + pawls under it; the cut rope above
    pz = 3.2
    box('platform', (0, 0, pz), (1.6, 1.2, .08), wood, .01)
    for s_ in (-1, 1):
        box(f'pawl{s_}', (s_ * .74, 0, pz - .08), (.12, .1, .06), iron, .005)
        rod(f'railp{s_}', (s_ * .78, -.55, pz), (s_ * .78, -.55, pz + .5), .015, iron, 8)
    rod('railtop', (-.78, -.55, pz + .5), (.78, -.55, pz + .5), .015, iron, 8)
    box('spring', (0, 0, pz + .1), (1.5, .06, .04), iron, .003)
    crate = M('crate', (.42, .28, .12), .7)
    box('crate1', (-.45, .15, pz + .22), (.4, .4, .36), crate, .01); box('crate2', (-.42, .2, pz + .55), (.3, .3, .3), crate, .01)
    cyl('barrel', (.05, .3, pz + .25), .16, .42, M('barrel', (.3, .17, .07), .6))
    rope = M('hemp', (.55, .45, .3), .8)
    rod('rope_top', (0, 0, 6.0), (0, 0, 5.0), .02, rope, 12)
    rod('rope_bot', (0, 0, 4.6), (0, 0, pz + .95), .02, rope, 12)
    for s_ in (-1, 1): rod(f'bridle{s_}', (0, 0, pz + .95), (s_ * .72, 0, pz + .05), .012, rope, 8)
    # a gentleman in a top hat standing on the platform beside the crates (no face detail), one arm raised
    coat = M('coat', (.03, .03, .035), .7)
    gx = .5
    cyl('body', (gx, 0, pz + .7), .14, .8, coat); bpy.ops.mesh.primitive_uv_sphere_add(radius=.12, location=(gx, 0, pz + 1.22)); h = bpy.context.object; h.data.materials.append(M('skin', (.55, .35, .25), .6))
    cyl('hat', (gx, 0, pz + 1.45), .1, .26, coat); cyl('brim', (gx, 0, pz + 1.32), .17, .02, coat)
    for s_ in (-1, 1): cyl(f'leg{s_}', (gx + s_ * .06, 0, pz + .2), .04, .4, coat)
    rod('arm', (gx + .12, 0, pz + .95), (gx + .3, -.1, pz + 1.35), .03, coat)
    # the exhibition hall behind: iron arches and glowing glass panes
    glass = kit.mat_emit('panes', (.45, .6, .75), .22)
    for k in range(9):
        x = -8 + k * 2
        box(f'col{k}', (x, 8, 4), (.15, .15, 8), iron, 0); box(f'pane{k}', (x + 1, 8.1, 4.5), (1.8, .02, 6), glass, 0)
    # crowd silhouettes in the foreground
    r = random.Random(3)
    for k in range(14):
        x = -3 + k * .45 + r.uniform(-.1, .1); y = -3.2 + r.uniform(-.3, .3); hh = r.uniform(1.5, 1.8)
        cyl(f'pb{k}', (x, y, hh * .4), .18, hh * .8, coat); bpy.ops.mesh.primitive_uv_sphere_add(radius=.12, location=(x, y, hh * .86)); o = bpy.context.object; o.data.materials.append(coat)
        if k % 3 == 0: cyl(f'ph{k}', (x, y, hh + .06), .1, .2, coat)
    for x in (-2.5, 2.5): point(f'gas{x}', (x, -1, 3.0), 300, (1, .6, .28), .1)
    area('key', (2, -3, 5), (0, 0, 3.5), 400, (1, .65, .35), 2); area('back', (0, 6, 6), (0, 0, 3), 250, (.4, .6, 1), 4)
    cam((-1.2, -6.0, 2.2), (0, 0, 3.9), 30)

# ================================================================== 1945: Empire State Building in fog with the B-25 (daytime, gray)
def esb(xc=0, yc=0):
    """stylized Empire State Building (to proportion): 5-floor base, setbacks, the main tower to the 86th floor and the mast. 1 unit = 10 m"""
    stone = bpy.data.materials.new('limestone'); nt, N, L = kit.nodes(stone); o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled')
    tc = N.new('ShaderNodeTexCoord'); br = N.new('ShaderNodeTexBrick'); br.inputs['Scale'].default_value = 1.0
    br.inputs['Color1'].default_value = (.05, .06, .07, 1); br.inputs['Color2'].default_value = (.07, .08, .09, 1); br.inputs['Mortar'].default_value = (.42, .42, .4, 1)
    br.inputs['Mortar Size'].default_value = .35; br.offset = 0; br.squash = 1
    mp = N.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (2.6, 2.6, 2.75)   # window grid ~ 3.8 m per floor
    L.new(tc.outputs['Object'], mp.inputs[0]); L.new(mp.outputs[0], br.inputs['Vector']); L.new(br.outputs['Color'], bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = .6; L.new(bs.outputs[0], o.inputs[0])
    tiers = [(0, 2.3, 13.0, 6.0), (2.3, 6.0, 9.5, 4.9), (6.0, 27.4, 7.5, 4.0), (27.4, 31.0, 6.3, 3.4), (31.0, 32.0, 5.2, 2.9)]
    for k, (z0, z1, w, d) in enumerate(tiers):
        box(f'esb{k}', (xc, yc, (z0 + z1) / 2), (w, d, z1 - z0), stone, .02)
    # vertical piers on the main shaft (Art Deco lines)
    pier = M('pier', (.35, .35, .33), .6)
    for k in range(9): box(f'pier{k}', (xc - 3.4 + k * .85, yc - 2.03, 16.7), (.12, .08, 21.4), pier, 0)
    cyl('mast1', (xc, yc, 33.0), 1.3, 2.0, pier); cyl('mast2', (xc, yc, 35.0), .8, 2.0, pier); cyl('mast3', (xc, yc, 37.3), .35, 2.6, pier)
    cyl('needle', (xc, yc, 39.5), .08, 2.0, pier)

def b25(loc, heading=0.0, s=.16):
    """North American B-25 Mitchell, simplified: slim fuselage, high-mounted wing, two engine nacelles, twin vertical tails. s = units per meter /10"""
    olive = M('olive', (.17, .19, .11), .55); glass = M('canopy', (.3, .4, .45), .1, metal=.2)
    root = kit.link(bpy.data.objects.new('b25', None)); root.location = loc; root.rotation_euler = (0, math.radians(-4), math.radians(heading))
    def P(o): o.parent = root; return o
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=(0, 0, 0), segments=48, ring_count=24); f = P(bpy.context.object); f.scale = (8 * s, .8 * s, .9 * s); f.data.materials.append(olive); bpy.ops.object.shade_smooth()
    P(box('wing', (.6 * s, 0, .35 * s), (2.4 * s, 20.6 * s, .25 * s), olive, .004))
    for side in (-1, 1):
        n = P(cyl(f'nac{side}', (1.6 * s, side * 2.6 * s, .1 * s), .55 * s, 4.2 * s, olive, rot=(0, math.pi / 2, 0)))
        P(cyl(f'prop{side}', (3.75 * s, side * 2.6 * s, .1 * s), 1.8 * s, .05 * s, M('propblur', (.05, .05, .05), .6), rot=(0, math.pi / 2, 0)))
        P(box(f'tail{side}', (-7.4 * s, side * 3.1 * s, .9 * s), (1.4 * s, .15 * s, 2.4 * s), olive, .003))
    P(box('hstab', (-7.4 * s, 0, .55 * s), (1.4 * s, 6.6 * s, .15 * s), olive, .003))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=(5.0 * s, 0, .55 * s)); c = P(bpy.context.object); c.scale = (1.4 * s, .55 * s, .45 * s); c.data.materials.append(glass)
    return root

def city(n=40, seed=2):
    r = random.Random(seed); m = M('bldgs', (.08, .09, .1), .7)
    for k in range(n):
        x, y = r.uniform(-40, 40), r.uniform(-10, 40)
        if abs(x) < 9 and abs(y) < 6: continue
        h = r.uniform(4, 16); box(f'cb{k}', (x, y, h / 2), (r.uniform(3, 6), r.uniform(3, 6), h), m, 0)

def esb_plate():
    flat_world((.36, .42, .46), 1.0)     # overcast fog light (gray-teal); more fog is layered in 2D
    box('ground', (0, 0, -.05), (200, 200, .1), M('street', (.1, .1, .11), .8), 0)
    esb(0, 0); city()
    s = bpy.data.lights.new('sky', 'SUN'); s.energy = 1.6; s.color = (.85, .9, 1); s.angle = math.radians(25)
    o = kit.link(bpy.data.objects.new('sky', s)); o.rotation_euler = (math.radians(40), 0, math.radians(30))
    haze(.03, (0, 0, 20), (60, 60, 22))
    # floor 79 is ~ 30.2 units up (3.8 m per floor). The plane comes in from the north (we look from the north-west)
    if name in ('esb_fog', 'esb_clear'):
        if name == 'esb_fog': b25((-12, -14, 29.6), heading=48)
        cam((-38, -52, 6), (0, 0, 22), 30)
    else:
        b25((-3.6, -6.0, 29.9), heading=58, s=.16)
        point('fire', (0, -2.2, 30.0), 0, (1, .5, .2), 1)
        cam((-14, -20, 25), (-1, -2, 29.8), 40, 5.6, 22)

# ================================================================== a 1940s elevator car: wood panels, brass scissor gate, lever controller
def old_car_plate():
    flat_world((.008, .006, .005), 1.0)
    wood = M('veneer', (.28, .14, .06), .35, coat=.4); brass = M('brass', (.78, .55, .22), .25, metal=1)
    box('o_floor', (0, 0, -.02), (1.8, 1.6, .04), M('o_floor', (.12, .08, .05), .6), 0)
    for k in range(3): box(f'o_back{k}', (-.6 + k * .6, .8, 1.1), (.58, .03, 2.2), wood, .006)
    for s in (-1, 1): box(f'o_side{s}', (s * .9, 0, 1.1), (.03, 1.6, 2.2), wood, .006)
    box('o_ceiling', (0, 0, 2.2), (1.8, 1.6, .04), wood, 0)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=.08, location=(0, 0, 2.08)); b = bpy.context.object; b.data.materials.append(kit.mat_emit('o_bulb', (1, .7, .4), 30))
    point('o_bulb', (0, 0, 2.0), 40, (1, .62, .3), .08)
    # lever controller on the left wall (operator's switch)
    cyl('ctrl', (-.87, -.45, 1.15), .12, .05, brass, rot=(0, math.pi / 2, 0)); rod('lever', (-.85, -.45, 1.15), (-.75, -.45, 1.38), .015, brass, 12)
    # brass scissor gate across the front (diagonal lattice), partly folded open
    for k in range(10):
        x = -.85 + k * .09
        rod(f'gA{k}', (x, -.8, .05), (x + .09, -.8, 2.1), .008, brass, 8); rod(f'gB{k}', (x + .09, -.8, .05), (x, -.8, 2.1), .008, brass, 8)
    for z in (.05, 2.1): rod(f'gbar{z}', (-.86, -.8, z), (.06, -.8, z), .012, brass, 8)
    area('o_fill', (.5, -2.0, 1.3), (0, .4, 1.0), 25, (.4, .55, .9), 2)
    cam((.25, -2.4, 1.2), (0, .5, 1.1), 30, 4.0)

def stairs_plate():
    flat_world((.004, .006, .01), 1.0)
    box('h_floor', (0, 0, -.02), (8, 8, .04), M('h_floor', (.06, .06, .07), .4), 0)
    box('h_wall', (0, 1.0, 1.5), (8, .1, 3), M('h_wall', (.08, .15, .17), .8), 0)
    box('door', (.9, .94, 1.05), (.95, .04, 2.1), M('firedoor', (.45, .12, .08), .45, coat=.3), .01)
    rod('push', (.55, .9, 1.05), (1.25, .9, 1.05), .02, M('bar', (.7, .7, .72), .3, 1))
    box('exit_box', (.9, .93, 2.35), (.42, .06, .18), M('exitbox', (.05, .05, .05), .4), .01)
    label3d('EXIT', (.9, .895, 2.35), .11, kit.mat_emit('exit', (1, .08, .05), 3), rot=(math.pi / 2, 0, 0))
    label3d('STAIRS', (.9, .915, 1.75), .07, M('stairs_txt', (.9, .9, .9), .5), rot=(math.pi / 2, 0, 0))
    box('elev_l', (-1.1, .95, 1.05), (1.1, .04, 2.1), brushed('hdoor'), .005)
    cast(dict(kai='smirk', leo='happy', mia='happy'), {'kai': {'arm_r': (math.radians(-70), math.radians(30), 0)}}, y=.25, xs={'leo': -.65, 'kai': .05, 'mia': -.25},
         turn={'leo': 20, 'kai': -15, 'mia': 10})
    point('exitglow', (.9, .7, 2.3), 15, (1, .1, .05), .1)
    area('key', (1.5, -2, 2), (0, .3, .8), 70, (1, .7, .45), 2); area('rim', (-1.5, .6, 2.4), (0, .3, .9), 25, (.35, .55, 1), 1)
    cam((.1, -2.4, 1.05), (.15, .5, 1.05), 30, 5.0)

if name.startswith(('car_', 'cu_')): car_plate()
elif name.startswith(('shaft_', 'safety')): shaft_plate()
elif name in ('governor', 'machine'): machine_room(name)
elif name == 'otis': otis_plate()
elif name.startswith('esb'): esb_plate()
elif name == 'old_car': old_car_plate()
elif name == 'stairs': stairs_plate()
sc.render.filepath = f'{OUT}/{name}.png'
bpy.ops.render.render(write_still=True)
print('WROTE', sc.render.filepath)
