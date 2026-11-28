"""Story Short: the wall of their plane blew out. One Cycles still per plate (animated in 2D by jet_anim.py: camera moves, cuts,
shakes, fog, debris sucked out of the hole, masks swinging, graphics). Generic, unbranded twin-jet airliner (narrow-body,
3+3 seating, overhead bins, drop-down oxygen masks); helpers from quake_plate.py (exec'd up to its plates section).
python3 jet_plate.py <plate> [res_scale] -> jet/plates/<plate>.png (+ .txt with projected 2D points)
cabin (wide down the aisle at sunset, cast seated, calm), blowout (hook: the hole torn in the wall, masks down, cast scared),
hole (close on the hole: sky + clouds outside, two empty seats beside it), masks (close on the service panel, masks hanging),
cu_leo (Leo, scared, reaching), cu_mia (Mia, mask in hand, angry), masks_on (row: all three wearing masks, calm),
cu_kai (Kai with mask, shouting), exterior (the jet above the clouds at sunset), ext_hole (night, close on the fuselage behind
the wing with the plug hole, cabin light pouring out), phone (a phone lying under a bush by a road, screen lit)"""
import sys, os, math, random
QP = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'quake_plate.py')
src = open(QP).read().split('# ------------------------------------------------------------------ plates')[0]
exec(compile(src, QP, 'exec'))
OUT = '/home/claude/b3d/jet/plates'; os.makedirs(OUT, exist_ok=True)
PLATE = name; R = math.radians

def person(who, loc, yaw=0.0, h=1.35, expr='neutral', arms=None, lean=0.0):
    root, parts = kit.character(who, (0, 0, 0), h)
    parts['face_mat'].node_tree.nodes['expr'].outputs[0].default_value = kit.EXPRS.index(expr)
    for a, r in (arms or {}).items(): parts[a].rotation_euler = tuple(R(v) for v in r)
    root.rotation_euler = (R(lean), 0, R(yaw)); root.location = loc
    return root, parts
def seated(who, loc, yaw=0.0, h=1.15, expr='neutral', arms=None):
    root, parts = person(who, loc, yaw, h, expr, arms)
    for lg in ('leg_l', 'leg_r'): parts[lg].rotation_euler = (R(90), 0, 0)
    return root, parts

# ------------------------------------------------------------------ cabin (front of the plane = -Y; seats face -Y)
CR, CZ = 1.9, .78                 # fuselage inner radius + centre height (floor at z=0 -> ~3.4 m wide at the floor)
PITCH = .82; ROWS = 9; SEATX = (.58, 1.04, 1.48)
def sky_mat(nm='skywin', night=False, k=6.0):
    """window/hole view: sunset sky gradient with soft cloud tops low down"""
    m = bpy.data.materials.new(nm); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); e = N.new('ShaderNodeEmission')
    tc = N.new('ShaderNodeTexCoord'); sep = N.new('ShaderNodeSeparateXYZ'); L.new(tc.outputs['Generated'], sep.inputs[0])
    cr = N.new('ShaderNodeValToRGB'); el = cr.color_ramp.elements
    if night: el[0].color = (.02, .03, .07, 1); el[1].color = (.05, .08, .18, 1)
    else:
        el[0].color = (1.0, .55, .22, 1); el[0].position = .25; el[1].color = (.25, .42, .75, 1); el[1].position = .9
        e2 = cr.color_ramp.elements.new(.5); e2.color = (.95, .7, .5, 1)
    L.new(sep.outputs['Z'], cr.inputs[0])
    nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 4; nz.inputs['Detail'].default_value = 10
    L.new(tc.outputs['Object'], nz.inputs[0]); cl = N.new('ShaderNodeMapRange'); cl.inputs['From Min'].default_value = .5; cl.inputs['From Max'].default_value = .65
    L.new(nz.outputs['Fac'], cl.inputs[0])
    low = N.new('ShaderNodeMath'); low.operation = 'LESS_THAN'; low.inputs[1].default_value = .3; L.new(sep.outputs['Z'], low.inputs[0])
    mm = N.new('ShaderNodeMath'); mm.operation = 'MULTIPLY'; L.new(cl.outputs[0], mm.inputs[0]); L.new(low.outputs[0], mm.inputs[1])
    mx = N.new('ShaderNodeMixRGB'); L.new(mm.outputs[0], mx.inputs['Fac']); L.new(cr.outputs[0], mx.inputs[1]); mx.inputs[2].default_value = (1, .9, .8, 1) if not night else (.08, .1, .16, 1)
    L.new(mx.outputs[0], e.inputs['Color']); e.inputs['Strength'].default_value = k; L.new(e.outputs[0], o.inputs[0]); return m

def seat(x, y, mat_c, mat_f):
    box('cush', (x, y, .45), (.44, .48, .11), mat_c, .03)
    box('back', (x, y + .25, .76), (.44, .1, .6), mat_c, .035, rot=(R(-8), 0, 0))
    box('head', (x, y + .215, .98), (.42, .02, .16), M('cover', (.85, .86, .88), .8), .008, rot=(R(-8), 0, 0))
    box('frame', (x, y + .05, .2), (.4, .4, .05), mat_f, .01)
    for dx in (-.235, .235): box('arm', (x + dx, y + .04, .6), (.05, .46, .05), mat_f, .015)
def cabin(rows=ROWS, hole_row=None, masks=False, y0=-1.0, lights=True, sunset=True, skip=()):
    flat_world((.02, .03, .05), .3)
    wallm = M('wall', (.42, .44, .47), .55); binm = M('bins', (.62, .63, .65), .45); carpet = fabric('carpet', (.08, .1, .16))
    seatc = fabric('seatc', (.06, .12, .26)); seatf = M('seatf', (.3, .31, .33), .35, .6)
    L_ = rows * PITCH + 4
    # floor + curved walls/ceiling (cylinder seen from inside)
    box('floor', (0, y0 + L_ / 2 - 1, -.02), (3.6, L_, .04), carpet, 0)
    bpy.ops.mesh.primitive_cylinder_add(radius=CR, depth=L_, location=(0, y0 + L_ / 2 - 1, CZ), rotation=(R(90), 0, 0), vertices=96, end_fill_type='NOTHING')
    sh = bpy.context.object; sh.data.materials.append(wallm); bpy.ops.object.shade_smooth()
    sol = sh.modifiers.new('s', 'SOLIDIFY'); sol.thickness = .06
    if hole_row is not None:      # cut the plug opening out of the left wall: a ~0.6 x 1.2 m doorway-shaped hole (2 x 4 ft)
        hy = y0 + hole_row * PITCH + .1
        bpy.ops.mesh.primitive_cube_add(location=(-CR, hy, .95)); cutter = bpy.context.object; cutter.scale = (.4, .32, .6)
        bo = sh.modifiers.new('hole', 'BOOLEAN'); bo.object = cutter; bo.operation = 'DIFFERENCE'; cutter.hide_render = True; cutter.display_type = 'WIRE'
        bpy.ops.mesh.primitive_plane_add(size=1, location=(-CR - .9, hy, .95), rotation=(0, R(90), 0)); sk_ = bpy.context.object
        sk_.scale = (3.5, 3.5, 1); sk_.data.materials.append(sky_mat('holesky', k=3.2)); PTS['hole'] = (-CR + .02, hy, .95)
        PTS['hole_top'] = (-CR + .02, hy, 1.55); PTS['hole_bot'] = (-CR + .02, hy, .35)
        for dz in (-.62, .62): box('hframe', (-CR + .08, hy, .95 + dz), (.12, .7, .06), M('alu', (.5, .52, .55), .35, .9), .01)
        for dy in (-.33, .33): box('hframe', (-CR + .08, hy + dy, .95), (.12, .06, 1.3), M('alu2', (.5, .52, .55), .35, .9), .01)
        point('holelight', (-CR + .3, hy, 1.0), 120, (1, .8, .65), .5)
    # windows (one per row, both sides), skipping the hole row
    win = sky_mat('win', k=3.0); bez = M('bezel', (.9, .9, .91), .5)
    for side in (-1, 1):
        for r in range(rows + 2):
            yy = y0 + r * PITCH + .1
            if hole_row is not None and side < 0 and abs(r - hole_row) < 1: continue
            ang = math.acos(min(1, (1.05 - CZ) / CR)); xx = side * (CR * math.sin(ang) - .065)
            bpy.ops.mesh.primitive_plane_add(size=1, location=(xx, yy, 1.05), rotation=(0, R(90) * side - side * (R(90) - ang) * 0 , 0))
            w_ = bpy.context.object; w_.scale = (.34, .24, 1); w_.rotation_euler = (0, side * R(90) + side * R(8), 0); w_.data.materials.append(win)
            bb = box('bezel', (xx - side * .01, yy, 1.05), (.02, .34, .44), bez, .05, rot=(0, side * R(8), 0))
            bb.modifiers['b'].width = .08
    # overhead bins + service units (reading lights, mask doors)
    for side in (-1, 1):
        box('bin', (side * 1.15, y0 + L_ / 2 - 1, 1.95), (1.0, L_, .45), binm, .06, rot=(0, side * R(-18), 0))
        box('psu', (side * 1.12, y0 + L_ / 2 - 1, 1.66), (.8, L_, .04), M('psu', (.75, .76, .78), .5), .01, rot=(0, side * R(-12), 0))
    box('ceil', (0, y0 + L_ / 2 - 1, 2.28), (1.2, L_, .05), M('ceil', (.9, .9, .92), .5), .02)
    if lights:
        glow = kit.mat_emit('cove', (.75, .82, 1.0) if not sunset else (1, .78, .55), 2.5)
        for side in (-1, 1): box('cove', (side * .58, y0 + L_ / 2 - 1, 2.2), (.04, L_, .03), glow, 0)
        for r in range(0, rows + 2, 2): point('cl', (0, y0 + r * PITCH, 2.0), 12, (1, .85, .7), .4)
    # seats
    for r in range(rows):
        yy = y0 + r * PITCH
        for side in (-1, 1):
            for sx in SEATX:
                if (r, side) in skip: continue
                seat(side * sx, yy, seatc, seatf)
    # oxygen masks hanging from the service units
    if masks:
        cup = M('cup', (.95, .78, .1), .45); tube = M('tube', (.85, .9, .95), .1)
        for r in range(rows):
            yy = y0 + r * PITCH - .25
            for side in (-1, 1):
                if (r, side) in skip: continue
                for sx in SEATX:
                    rr = random.Random(r * 10 + int(sx * 10) + side); dz = rr.uniform(-.05, .08); sw = rr.uniform(-.06, .06)
                    x = side * (sx - .02) + sw; ztop = 1.64 - (sx - .5) * .2
                    x += side * .1
                    cyl('tube', (x, yy, (ztop + 1.5 + dz) / 2), .006, ztop - 1.5 - dz, tube, verts=8)
                    cyl('cup', (x, yy, 1.46 + dz), .06, .09, cup, r2=.04, verts=24)
    return y0

def sun_side():
    """warm low sun through the right-hand windows + cool fill"""
    area('sun', (2.6, 2.0, 1.2), (0, 2.0, .8), 600, (1, .7, .45), 3.0)
    area('fill', (0, -3.0, 1.6), (0, 3, 1), 140, (.6, .7, 1), 3.0)

c = None
Y0 = -1.0
def rowy(r): return Y0 + r * PITCH
# cast: row 3, right block (Mia window, Leo middle, Kai aisle)
CAST_ROW = 3
def cast_seated(exprs=('neutral', 'neutral', 'neutral'), arms=({}, {}, {}), masks_on=False, hole_side=False):
    out = {}
    side = -1 if hole_side else 1
    for (who, sx), ex, ar in zip((('kai', SEATX[0]), ('leo', SEATX[1]), ('mia', SEATX[2])), exprs, arms):
        h = {'kai': 1.12, 'leo': 1.06, 'mia': 1.08}[who]
        root, parts = seated(who, (side * sx, rowy(CAST_ROW) - .02, .3), 0, h, ex, ar)
        out[who] = (root, parts, (side * sx, rowy(CAST_ROW) - .02, .3 + .8 * h))
        PTS[who] = out[who][2]; PTS[who + '_mouth'] = (side * sx, rowy(CAST_ROW) - .22, .3 + .72 * h)
        if masks_on:
            cyl('mask', (side * sx, rowy(CAST_ROW) - .24, .3 + .7 * h), .075, .1, M('cupw', (.95, .78, .1), .45), rot=(R(90), 0, 0), r2=.05, verts=24)
            cyl('strap', (side * sx, rowy(CAST_ROW) - .02, .3 + .73 * h), .232, .015, M('strap', (.9, .85, .7), .6), verts=48)
            cyl('tube', (side * sx, rowy(CAST_ROW) - .3, .3 + .7 * h + .32), .006, .6, M('tube2', (.85, .9, .95), .1), verts=8)
    return out

if PLATE in ('cabin', 'blowout', 'hole', 'masks', 'cu_leo', 'cu_mia', 'masks_on', 'cu_kai'):
    after = PLATE != 'cabin'
    hole_row = CAST_ROW + 1 if after else None    # the hole is across the aisle, one row behind the cast
    skip = {(CAST_ROW - 1, 1)} if PLATE in ('cu_leo', 'cu_mia', 'masks_on', 'cu_kai', 'masks') else set()
    if PLATE == 'blowout': skip = {(CAST_ROW, -1), (CAST_ROW - 1, -1), (CAST_ROW - 1, 1)}
    cabin(hole_row=hole_row, masks=after, skip=skip)
    if not after: sun_side()
    else:
        area('cold', (0, -3.0, 1.8), (0, 3, 1), 90, (.55, .7, 1), 3.0)
        point('emerg', (0, rowy(CAST_ROW), 2.0), 25, (.8, .9, 1), .3)
    if PLATE == 'cabin':
        cast_seated(('happy', 'smirk', 'neutral'), ({}, {'arm_r': (-50, 0, -15)}, {}))
        c = cam((.1, rowy(CAST_ROW - 2.6), 1.75), (.95, rowy(CAST_ROW + 1.2), .9), 26)
    elif PLATE == 'blowout':
        cast_seated(('scared', 'scared', 'surprised'), ({'arm_l': (0, -140, 0), 'arm_r': (0, 140, 0)}, {'arm_l': (0, -150, 0), 'arm_r': (0, 150, 0)}, {'arm_r': (-90, 0, 70)}))
        c = cam((1.3, rowy(CAST_ROW - 1.0), 1.45), (-1.9, rowy(CAST_ROW + 1.1), .95), 18)
    elif PLATE == 'hole':
        c = cam((.45, rowy(CAST_ROW + .55), 1.2), (-CR, rowy(CAST_ROW + 1) + .1, .95), 28, 4.0)
    elif PLATE == 'masks':
        c = cam((.6, rowy(CAST_ROW - 1.1), 1.2), (1.15, rowy(CAST_ROW) - .25, 1.55), 30, 3.0)
    elif PLATE == 'cu_leo':
        cast_seated(('angry', 'scared', 'worried'), ({}, {'arm_r': (-80, 0, 60)}, {}))
        c = cam((.95, rowy(CAST_ROW - 1.45), 1.25), (1.0, rowy(CAST_ROW), 1.08), 38, 2.4)
    elif PLATE == 'cu_mia':
        cast_seated(('scared', 'worried', 'angry'), ({}, {}, {'arm_r': (-120, 0, 30), 'arm_l': (-60, 0, -30)}))
        c = cam((1.25, rowy(CAST_ROW - 1.45), 1.25), (1.45, rowy(CAST_ROW), 1.08), 38, 2.4)
    elif PLATE == 'masks_on':
        cast_seated(('worried', 'worried', 'neutral'), masks_on=True)
        c = cam((1.0, rowy(CAST_ROW - 2.1), 1.3), (1.0, rowy(CAST_ROW), 1.0), 28, 3.0)
    elif PLATE == 'cu_kai':
        cast_seated(('angry', 'scared', 'worried'), ({'arm_l': (-100, 0, -20)}, {}, {}), masks_on=True)
        c = cam((.45, rowy(CAST_ROW - 1.45), 1.25), (.58, rowy(CAST_ROW), 1.08), 38, 2.4)

# ------------------------------------------------------------------ exterior: a generic twin-jet (about 40 m long, 36 m span)
def jet(white=(.86, .87, .89), belly=(.2, .26, .36)):
    root = kit.link(bpy.data.objects.new('jet', None))
    skin = M('skin', white, .32, .1, .4); bel = M('belly', belly, .4, .1, .3); grey = M('grey', (.55, .57, .6), .35, .8)
    def add(o): o.parent = root; return o
    bpy.ops.mesh.primitive_cylinder_add(radius=1.9, depth=28, location=(0, 0, 0), rotation=(0, R(90), 0), vertices=64)
    fus = add(bpy.context.object); fus.data.materials.append(skin); bpy.ops.object.shade_smooth()
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.9, segments=64, ring_count=32, location=(-14, 0, 0)); nose = add(bpy.context.object)
    nose.scale = (2.4, 1, 1); nose.location = (-13.6, 0, -.15); nose.data.materials.append(skin); bpy.ops.object.shade_smooth()
    bpy.ops.mesh.primitive_cone_add(radius1=1.9, radius2=.35, depth=9, location=(18.5, 0, .55), rotation=(0, R(90), 0), vertices=64); tail = add(bpy.context.object)
    tail.data.materials.append(skin); bpy.ops.object.shade_smooth()
    # cockpit windows + cabin window row
    winm = M('jwin', (.03, .04, .06), .05, .0, 1.0)
    for s_ in (-1, 1):
        for k, a_ in enumerate((50, 58, 66)):   # windshield panes sitting on the nose surface
            ca = math.cos(R(a_)); sa = math.sin(R(a_)); rad = 1.9 * sa * 1.0
            box('cw', (-13.6 - 4.56 * ca + .02, s_ * rad * math.cos(R(28)), rad * math.sin(R(28))), (.42, .04, .26), winm, .02,
                rot=(R(-28) * s_ * -1 + 0, 0, s_ * R(-(90 - a_) * .9))).parent = root
    for k in range(28):
        x = -12 + k * .9
        if abs(x - 9.5) < .5: continue
        for s in (-1, 1): box('w', (x, s * 1.88, .35), (.22, .05, .32), winm, .03).parent = root
    # wings (swept), engines, tail
    def wing(span, root_c, tip_c, sweep, z, thick, y_sign, mat, dihedral=5):
        me = bpy.data.meshes.new('wing'); import bmesh as _bm; bm = _bm.new()
        pts = [(0, 0), (root_c, 0), (sweep + tip_c, span), (sweep, span)]
        vs = []
        for dz in (-thick / 2, thick / 2):
            for (x, y) in pts: vs.append(bm.verts.new((x, y * y_sign, z + dz + y * math.tan(R(dihedral)))))
        bm.faces.new(vs[:4][::-1]); bm.faces.new(vs[4:])
        for k in range(4): bm.faces.new((vs[k], vs[(k + 1) % 4], vs[(k + 1) % 4 + 4], vs[k + 4]))
        bm.normal_update(); bm.to_mesh(me); ob = kit.link(bpy.data.objects.new('wing', me)); ob.data.materials.append(mat); ob.parent = root
        bv = ob.modifiers.new('b', 'BEVEL'); bv.width = .08; bv.segments = 2; return ob
    for s in (-1, 1):
        wing(16.5, 7.0, 1.6, 9.0, -1.0, .35, s, skin)
        wing(6.5, 3.6, 1.2, 5.0, .9, .18, s, skin, 7).location = (14.5, 0, 0)
        bpy.ops.mesh.primitive_cylinder_add(radius=.95, depth=3.6, location=(-1.2 + 2.6, s * 5.6, -1.85), rotation=(0, R(90), 0), vertices=48)
        en = add(bpy.context.object); en.data.materials.append(M('nacelle', (.8, .81, .83), .3, .3)); bpy.ops.object.shade_smooth()
        cyl('intake', (-.4 + 2.6 - .02, s * 5.6, -1.85), .8, .1, M('fan', (.05, .05, .06), .4, .8), rot=(0, R(90), 0)).parent = root
        box('pylon', (2.6 + .4, s * 5.6, -1.25), (2.4, .2, .8), skin, .05).parent = root
    me = bpy.data.meshes.new('fin'); import bmesh as _bm; bm = _bm.new()
    pts = [(14.5, 0, 1.5), (20.5, 0, 1.6), (22.3, 0, 8.0), (19.9, 0, 8.0)]
    vs = [bm.verts.new((x, y + dy, z)) for dy in (-.15, .15) for (x, y, z) in pts]
    bm.faces.new(vs[:4]); bm.faces.new(vs[4:][::-1])
    for k in range(4): bm.faces.new((vs[k], vs[k + 4], vs[(k + 1) % 4 + 4], vs[(k + 1) % 4]))
    bm.normal_update(); bm.to_mesh(me); fin = kit.link(bpy.data.objects.new('fin', me)); fin.data.materials.append(bel); fin.parent = root
    return root
def cloud_deck(z=-60, sunset=True):
    m = bpy.data.materials.new('deck'); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled')
    tc = N.new('ShaderNodeTexCoord'); nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = .02; nz.inputs['Detail'].default_value = 12; nz.inputs['Roughness'].default_value = .62
    L.new(tc.outputs['Object'], nz.inputs[0]); cr = N.new('ShaderNodeValToRGB'); cr.color_ramp.elements[0].color = (.5, .52, .62, 1); cr.color_ramp.elements[1].color = (1, .97, .94, 1)
    cr.color_ramp.elements[0].position = .4; cr.color_ramp.elements[1].position = .7
    L.new(nz.outputs['Fac'], cr.inputs[0]); L.new(cr.outputs[0], bs.inputs['Base Color']); bs.inputs['Roughness'].default_value = 1
    bs.inputs['Subsurface Weight'].default_value = .3
    disp = N.new('ShaderNodeDisplacement'); disp.inputs['Scale'].default_value = 30; L.new(nz.outputs['Fac'], disp.inputs['Height'])
    L.new(bs.outputs[0], o.inputs[0]); L.new(disp.outputs[0], o.inputs['Displacement']); m.displacement_method = 'BUMP'
    bpy.ops.mesh.primitive_plane_add(size=80000, location=(0, 0, z)); d = bpy.context.object; d.data.materials.append(m); return d

if PLATE == 'exterior':
    kit.sky(sun_elevation=4, sun_rotation=250, strength=.5, sun_lamp_energy=5.0)
    cloud_deck(-70); j = jet(); j.rotation_euler = (R(3), R(-5), R(22))
    bpy.context.view_layer.update(); PTS['jet'] = tuple(j.matrix_world @ Vector((0, 0, 0))); PTS['plug'] = tuple(j.matrix_world @ Vector((9.5, -1.9, .35))); PTS['nose'] = tuple(j.matrix_world @ Vector((-17, 0, 0)))
    c = cam((-30, -30, 3), (-3.5, -1, -1.0), 30); c.data.clip_end = 200000
elif PLATE == 'ext_hole':
    flat_world((.01, .015, .035), .4)
    j = jet((.8, .81, .84)); kit.sun_lamp((-.4, -.7, .6), .35, (.55, .65, 1))
    bpy.ops.mesh.primitive_plane_add(size=3000, location=(0, 0, -900)); g = bpy.context.object
    lm = bpy.data.materials.new('city'); nt, N, L = kit.nodes(lm); o = N.new('ShaderNodeOutputMaterial'); e = N.new('ShaderNodeEmission')
    vor = N.new('ShaderNodeTexVoronoi'); vor.inputs['Scale'].default_value = 1.2; tc = N.new('ShaderNodeTexCoord'); L.new(tc.outputs['Object'], vor.inputs[0])
    st = N.new('ShaderNodeMapRange'); st.inputs['From Min'].default_value = 0; st.inputs['From Max'].default_value = .08; st.inputs['To Min'].default_value = 25; st.inputs['To Max'].default_value = 0
    L.new(vor.outputs['Distance'], st.inputs[0]); e.inputs['Color'].default_value = (1, .62, .3, 1); L.new(st.outputs[0], e.inputs['Strength']); L.new(e.outputs[0], o.inputs[0])
    g.data.materials.append(lm)
    # the open plug hole (behind the wing, left side) with warm cabin light pouring out; cabin windows lit
    hole = box('plughole', (9.5, -1.9, .25), (.62, .14, 1.22), kit.mat_emit('cabinlight', (1, .85, .62), 4), .05)
    for o in bpy.data.objects:
        if o.name.startswith('w') and o.type == 'MESH' and o.dimensions.x < .3: o.data.materials[0] = kit.mat_emit('winlit', (1, .8, .55), 6) if False else o.data.materials[0]
    point('spill', (9.5, -2.6, .25), 90, (1, .8, .55), .4)
    PTS['plug'] = (9.5, -1.9, .25)
    c = cam((14.0, -8.2, 1.2), (9.0, -1.9, .1), 32)
elif PLATE == 'phone':
    kit.sky(sun_elevation=12, sun_rotation=200, strength=.12, sun_lamp_energy=2.0)
    ground = kit.terrain(size=12, height=.05, scale=6, kind='grass', seed=4); ground.location = (0, 0, 0)
    road = box('road', (0, 1.6, .02), (12, 1.6, .03), M('asph', (.08, .08, .09), .8), 0)
    leaf = M('leaf', (.06, .16, .05), .55)
    r_ = random.Random(5)
    leaf2 = M('leaf2', (.1, .22, .06), .5)
    for k in range(900):   # a low bush: hundreds of small leaves on a dome
        a = r_.uniform(0, 6.28); rr = r_.uniform(0, 1) ** .5
        x, y = -.25 + .75 * rr * math.cos(a), .35 + .5 * rr * math.sin(a); z = .55 * (1 - rr * rr) ** .5 + r_.uniform(-.05, .05)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=.035, segments=8, ring_count=6, location=(x, y, max(.04, z)))
        o = bpy.context.object; o.scale = (1, .45, .12); o.rotation_euler = (r_.uniform(0, 3), r_.uniform(0, 3), r_.uniform(0, 3)); o.data.materials.append(leaf if k % 2 else leaf2)
    for k in range(6): cyl('twig', (-.25 + r_.uniform(-.3, .3), .35 + r_.uniform(-.2, .2), .2), .012, .4, M('bark', (.15, .1, .06), .8), rot=(r_.uniform(-.5, .5), r_.uniform(-.5, .5), 0), verts=8)
    for k in range(160):
        x, y = r_.uniform(-3, 3), r_.uniform(-2.5, .8)
        bpy.ops.mesh.primitive_cone_add(radius1=.004, depth=r_.uniform(.03, .08), location=(x, y, .03)); o = bpy.context.object; o.data.materials.append(M('grass', (.12, .2, .07), .7)); o.rotation_euler = (r_.uniform(-.4, .4), r_.uniform(-.4, .4), 0)
    ph = box('phone', (.05, -.55, .045), (.075, .155, .009), M('phb', (.03, .03, .035), .25, .6), .006, rot=(0, 0, R(25)))
    box('scr', (.05, -.55, .0505), (.066, .142, .002), kit.mat_emit('phscr', (.25, .45, .9), .7), 0.002, rot=(0, 0, R(25)))
    PTS['phone'] = (.05, -.55, .05)
    c = cam((.35, -1.25, .42), (.05, -.5, .05), 45, 2.2)

if PTS:
    bpy.context.view_layer.update()
    with open(f'{OUT}/{PLATE}.txt', 'w') as f:
        for k, p in PTS.items(): f.write(f'{k} {proj(c, p)[0]} {proj(c, p)[1]}\n')
sc.render.filepath = f'{OUT}/{PLATE}.png'; bpy.ops.render.render(write_still=True); print('ok', PLATE)
