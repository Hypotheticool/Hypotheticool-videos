"""Story Short: Their Christmas tree went up in seconds. One Cycles still per plate (animated in 2D by xtree_anim.py, which adds
the flames, smoke, sparks and graphics). Reuses the night living room, bedroom and helpers from quake_plate.py (exec'd up to its plates section).
python3 xtree_plate.py <plate> [res_scale] -> xtree/plates/<plate>.png (+ .txt with projected 2D points)
living room: calm (cozy: tree lit, Kai + Mia on the couch), dry (the same tree, browned, needles on the floor, no cast),
  fire (the tree burning: fire light fills the room, Kai + Mia backing away), wide (high wide angle for the flashover),
  cu_mia (Mia, scared, pointing), cu_kai (Kai shouting), bulb (macro: an old light strand with a frayed wire in dry needles),
  wet / drybr (macro: a green watered branch vs a brown dry branch, same framing)
upstairs: stairs (stairwell from the bottom, smoke goes up in 2D), bed (Leo asleep, door shut), door (outside the shut bedroom door, hall)
outside: house (two-storey house at night in snow, ladder at the upstairs window), safe (Leo in a blanket with Kai + Mia on the snowy lawn)"""
import sys, os, math, random
QP = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'quake_plate.py')
src = open(QP).read().split('# ------------------------------------------------------------------ plates')[0]
exec(compile(src, QP, 'exec'))
OUT = '/home/claude/b3d/xtree/plates'; os.makedirs(OUT, exist_ok=True)
PLATE = name; R = math.radians

# ------------------------------------------------------------------ cast
def person(who, loc, yaw=0.0, h=1.35, expr='neutral', arms=None, lean=0.0):
    root, parts = kit.character(who, (0, 0, 0), h)
    parts['face_mat'].node_tree.nodes['expr'].outputs[0].default_value = kit.EXPRS.index(expr)
    for a, r in (arms or {}).items(): parts[a].rotation_euler = tuple(R(v) for v in r)
    root.rotation_euler = (R(lean), 0, R(yaw)); root.location = loc
    return root, parts
def seated(who, loc, yaw=0.0, h=1.35, expr='neutral', arms=None):
    root, parts = person(who, loc, yaw, h, expr, arms)
    for lg in ('leg_l', 'leg_r'): parts[lg].rotation_euler = (R(90), 0, 0)   # thighs forward over the cushion
    return root, parts

# ------------------------------------------------------------------ the tree
def needle_mat(dry=0.0):
    m = bpy.data.materials.new(f'needles{dry}'); nt, N, L = kit.nodes(m); o = N.new('ShaderNodeOutputMaterial'); bs = N.new('ShaderNodeBsdfPrincipled')
    tc = N.new('ShaderNodeTexCoord'); nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 38; nz.inputs['Detail'].default_value = 10
    L.new(tc.outputs['Object'], nz.inputs[0]); cr = N.new('ShaderNodeValToRGB')
    g0, g1 = (.008, .05, .02), (.03, .16, .06)                 # fresh fir: deep blue-green
    d0, d1 = (.06, .032, .01), (.24, .13, .035)                   # dry: rusty brown / straw
    mix = lambda a, b: tuple(a[i] * (1 - dry) + b[i] * dry for i in range(3))
    cr.color_ramp.elements[0].color = (*mix(g0, d0), 1); cr.color_ramp.elements[1].color = (*mix(g1, d1), 1)
    L.new(nz.outputs['Fac'], cr.inputs[0]); L.new(cr.outputs[0], bs.inputs['Base Color']); bs.inputs['Roughness'].default_value = .7
    bs.inputs['Sheen Weight'].default_value = .5
    bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = .6; L.new(nz.outputs['Fac'], bp.inputs['Height']); L.new(bp.outputs[0], bs.inputs['Normal'])
    L.new(bs.outputs[0], o.inputs[0]); return m
def tree(x, y, hgt=2.05, dry=0.0, lights=True, lit=1.0, fire=0.0, seed=3):
    """a cut fir in a stand: stacked, jagged, noise-displaced tiers (droop more when dry), string lights, glass ornaments, a star"""
    r = random.Random(seed); nm = needle_mat(dry); tiers = 11; base_r = .78; z0 = .22
    tx = bpy.data.textures.new('needlen', 'CLOUDS'); tx.noise_scale = .07; tx.noise_depth = 3
    tx2 = bpy.data.textures.new('tiern', 'CLOUDS'); tx2.noise_scale = .35
    cyl('trunk', (x, y, .2), .05, .4, M('bark', (.12, .07, .04), .8))
    cyl('stand', (x, y, .1), .24, .2, M('standp', (.5, .04, .03), .35), r2=.2)
    box('skirt', (x, y, .006), (1.1, 1.1, .012), fabric('skirt', (.55, .05, .05)), .04, rot=(0, 0, R(20)))
    for k in range(tiers):
        f = k / (tiers - 1); zc = z0 + f * (hgt - z0 - .3); rad = base_r * (1 - f * .85) + .05; dep = .38 * (1 - f * .3)
        bpy.ops.mesh.primitive_cone_add(vertices=64, radius1=rad, radius2=rad * .5, depth=dep, location=(x, y, zc + dep / 2))
        o = bpy.context.object; o.name = f'tier{k}'; o.rotation_euler = (0, 0, r.uniform(0, 6.28))
        sb = o.modifiers.new('s', 'SUBSURF'); sb.levels = 2; sb.render_levels = 3
        d = o.modifiers.new('d2', 'DISPLACE'); d.texture = tx2; d.strength = .1 + .05 * dry
        d = o.modifiers.new('d', 'DISPLACE'); d.texture = tx; d.strength = .07
        o.scale = (1, 1, 1 - .15 * dry); o.data.materials.append(nm); bpy.ops.object.shade_smooth()
    PTS['tree_top'] = (x, y, hgt); PTS['tree_mid'] = (x, y, hgt * .5); PTS['tree_low'] = (x, y, .55); PTS['tree_base'] = (x, y, .15)
    PTS['tree_l'] = (x - base_r * .9, y - .1, .7); PTS['tree_r'] = (x + base_r * .9, y - .1, .7)
    fz = (1.0 - z0) / (hgt - z0 - .3); PTS['tip'] = (x + .05, y - (base_r * (1 - fz * .85) + .05) * .85, 1.0); PTS['spark'] = PTS['tip']
    # star
    st = cyl('star', (x, y, hgt + .05), .09, .03, kit.mat_emit('starg', (1, .78, .3), 4 * lit + .3), rot=(R(90), 0, 0), verts=5)
    # ornaments (glass: red, gold, teal), spaced over the cone surface
    cols = [(.6, .03, .02), (.75, .5, .1), (.05, .3, .35), (.7, .7, .72)]
    for k in range(34):
        f = r.uniform(.03, .9); ang = r.uniform(R(-200), R(20)); rad = (base_r * (1 - f * .85) + .05) * .82
        zc = z0 + f * (hgt - z0 - .3) + .1
        o = cyl('orn', (x + math.cos(ang) * rad, y + math.sin(ang) * rad, zc), .045, .001, M('orn', r.choice(cols), .12, .6, 1), verts=8)
        bpy.ops.object.delete(); bpy.ops.mesh.primitive_uv_sphere_add(radius=.04 + .015 * r.random(), location=(x + math.cos(ang) * rad, y + math.sin(ang) * rad, zc))
        ob = bpy.context.object; ob.data.materials.append(M('orn', r.choice(cols), .1, .7, 1)); bpy.ops.object.shade_smooth()
    # string lights: warm bulbs spiralling round the front
    if lights:
        warm = [(1, .7, .35), (1, .55, .2), (1, .25, .15), (.35, .6, 1), (.4, 1, .45)]
        for k in range(70):
            f = k / 70; ang = R(-180) + f * R(360 * 3.5); rad = (base_r * (1 - f * .85) + .05) * .9
            if math.sin(ang) > .55: continue
            zc = z0 + f * (hgt - z0 - .3) + .1; col = warm[k % len(warm)]
            bpy.ops.mesh.primitive_uv_sphere_add(radius=.016, location=(x + math.cos(ang) * rad, y + math.sin(ang) * rad, zc))
            ob = bpy.context.object; ob.data.materials.append(kit.mat_emit('bulb', col, 8 * lit + .05))
        if lit > 0: point('treeglow', (x, y - .7, 1.1), 18 * lit, (1, .62, .32), .4)
    if fire > 0:   # the tree on fire: hot orange light from inside the branches lights the whole room
        point('fire1', (x, y + .05, .8), 420 * fire, (1, .38, .08), .3); point('fire2', (x, y + .05, 1.5), 300 * fire, (1, .45, .12), .3)
        point('fire3', (x, y - .1, 2.35), 220 * fire, (1, .42, .1), .3); point('fire4', (x, y + .5, 1.2), 500 * fire, (1, .4, .1), .4)
    return PTS['tree_mid']
def needles_floor(x, y, n=700, seed=5):
    r = random.Random(seed); m = M('fallen', (.42, .22, .06), .7)
    for k in range(n):
        a = r.uniform(0, 6.28); d = r.uniform(.15, 1.1)
        box('ndl', (x + math.cos(a) * d, y + math.sin(a) * d * .8, .004), (.07, .008, .008), m, 0, rot=(0, 0, r.uniform(0, 3.14)))

# ------------------------------------------------------------------ sets
TX, TY = -.15, 1.25        # tree in the living room (between the couch and the bookcase)
def living(lamp_light=True):
    global name
    keep = name; name = 'couchnl'; room(); name = keep          # 'couchnl' = room without the floor-lamp geometry (light only)
    room2(); haze(.010, (0, -.2, 1.3), (3, 2.5, 1.3))
    for o in list(bpy.data.objects):      # no coffee table: keep the floor clear in front of the tree
        if o.name.split('.')[0] in ('ttop', 'apron', 'apron2', 'tleg', 'rug'): bpy.data.objects.remove(o, do_unlink=True)
def stairs_set():
    flat_world((.01, .015, .025), 1.0); wm = wall_mat('sw', (.12, .19, .23)); trim = M('trim', (.75, .72, .66), .5)
    box('floor', (0, 0, -.01), (4, 6, .02), plank_mat(), 0)
    box('wl', (-.62, 1.5, 2.4), (.1, 6, 4.8), wm, 0); box('wr', (.62, 1.5, 2.4), (.1, 6, 4.8), wall_mat('sw2', (.1, .16, .2)), 0)
    wd = wood_mat('stair', (.34, .19, .09))
    for k in range(14):
        box('tread', (0, .3 + k * .27, .1 + k * .19), (1.1, .3, .04), wd, .006); box('riser', (0, .16 + k * .27, .01 + k * .19), (1.1, .02, .19), trim, 0)
    box('rail', (.48, 2.1, 2.0), (.05, 4.2, .05), wd, .01, rot=(R(-35), 0, 0))
    box('landing', (0, 4.6, 2.66), (1.2, 1.4, .04), wd, .006); box('topwall', (0, 5.3, 3.8), (1.4, .1, 2.6), wm, 0)
    box('topdoor', (-.1, 5.24, 3.68), (.8, .04, 2.0), M('doorp', (.68, .66, .6), .45), .008); cyl('knob', (.2, 5.2, 3.6), .03, .05, M('brass', (.8, .6, .25), .3, 1), rot=(R(90), 0, 0))
    point('fireglow', (0, -1.2, 1.0), 260, (1, .42, .12), .5); area('cool', (0, 4.3, 4.4), (0, 4, 2), 25, (.4, .55, 1), 1.2)
    PTS['top'] = (0, 4.8, 3.3); PTS['mid'] = (0, 2.4, 1.8); PTS['door'] = (-.1, 5.2, 3.7)
    return cam((.25, -1.7, 1.25), (0, 3.4, 2.3), 22)
def bedroom_set(shot):
    flat_world((.01, .015, .025), 1.0)
    box('floor', (0, 0, -.01), (5, 5, .02), plank_mat(), 0); wm = wall_mat('bw', (.1, .17, .22))
    box('bwall', (0, 1.4, 1.3), (5, .1, 2.6), wm, 0); box('swall', (1.6, 0, 1.3), (.1, 5, 2.6), wm, 0)
    trim = M('trim', (.75, .72, .66), .5)
    box('door', (1.54, -.9, 1.02), (.04, .84, 2.02), M('doorp', (.68, .66, .6), .45), .008); cyl('knob', (1.5, -.6, 1.0), .03, .05, M('brass', (.8, .6, .25), .3, 1), rot=(0, R(90), 0))
    for (cy, cz, sy, sz) in [(-1.35, 1.05, .07, 2.1), (-.45, 1.05, .07, 2.1), (-.9, 2.1, .98, .07)]: box('casing', (1.55, cy, cz), (.06, sy, sz), trim, .006)
    box('gap', (1.53, -.9, .008), (.02, .8, .012), kit.mat_emit('undergap', (1, .45, .15), 1.5), 0)   # fire glow under the shut door
    # window behind the bed
    for (cx, cz, sx, sz) in [(-.9, 1.0, .9, .06), (-.9, 2.0, .9, .06), (-1.33, 1.5, .06, 1.06), (-.47, 1.5, .06, 1.06), (-.9, 1.5, .03, 1.0)]:
        box('wf', (cx, 1.33, cz), (sx, .08, sz), trim, .005)
    box('night', (-.9, 1.6, 1.5), (2, .02, 2), night_sky_mat(), 0)
    wd = wood_mat('bedw', (.3, .17, .08))
    box('head', (0, 1.3, .55), (1.1, .08, 1.1), wd, .02); box('frame', (0, .3, .2), (1.05, 2.05, .25), wd, .02)
    box('mattress', (0, .3, .42), (1.0, 2.0, .2), fabric('mat', (.85, .85, .82)), .05)
    box('nst', (.85, 1.1, .3), (.45, .4, .6), wd, .01)
    root, parts = kit.character('leo', (0, 0, 0), 1.05)
    parts['face_mat'].node_tree.nodes['expr'].outputs[0].default_value = kit.EXPRS.index('bored' if shot == 'bed' else 'scared')
    root.rotation_euler = (R(-90), R(180), 0); root.location = (0, .22, .64)
    box('pillow', (0, 1.08, .56), (.6, .36, .12), fabric('pw', (.92, .92, .9)), .06)
    box('blanket', (0, .15, .6), (1.06, 1.35, .1), fabric('blank', (.12, .28, .42)), .05)
    area('moon', (-.9, 2.6, 2.2), (0, .5, .5), 120, (.45, .6, 1), 1.5); area('fill', (1.2, -2.5, 2), (0, .5, .5), 22, (.6, .7, 1), 3)
    point('gapglow', (1.45, -.9, .05), 6, (1, .45, .15), .1)
    PTS['leo'] = (0, .95, .85); PTS['door'] = (1.54, -.9, 1.0); PTS['gap'] = (1.53, -.9, .02)
    return cam((-.75, -1.05, 1.55), (.15, .55, .62), 26, 5.0)
def door_set():
    """upstairs hall, the shut bedroom door at the end; smoke and fire glow come from the stairs (2D)"""
    flat_world((.01, .015, .025), 1.0); wm = wall_mat('hw', (.13, .18, .2)); trim = M('trim', (.75, .72, .66), .5)
    box('floor', (0, 1, -.01), (3, 6, .02), plank_mat(), 0); box('ceil', (0, 1, 2.61), (3, 6, .02), M('ceil', (.08, .1, .11), .9), 0)
    box('wl', (-.75, 1, 1.3), (.1, 6, 2.6), wm, 0); box('wr', (.75, 1, 1.3), (.1, 6, 2.6), wm, 0); box('end', (0, 3.2, 1.3), (1.5, .1, 2.6), wm, 0)
    box('door', (0, 3.13, 1.02), (.84, .04, 2.02), M('doorp', (.68, .66, .6), .45), .008); cyl('knob', (.3, 3.09, 1.0), .03, .05, M('brass', (.8, .6, .25), .3, 1), rot=(R(90), 0, 0))
    for (cx, cz, sx, sz) in [(-.45, 1.05, .07, 2.1), (.45, 1.05, .07, 2.1), (0, 2.1, .98, .07)]: box('casing', (cx, 3.12, cz), (sx, .06, sz), trim, .006)
    for k in range(3): box('panel', (0, 3.1, .5 + k * .6), (.6, .01, .42), M('dpan', (.6, .58, .53), .5), .01)
    box('frame', (-.7, 1.8, 1.6), (.03, .4, .5), M('fr', (.05, .04, .03), .4), .005); box('pic', (-.685, 1.8, 1.6), (.004, .34, .44), M('pic', (.2, .35, .5), .6), 0)
    point('fireglow', (.0, -1.2, .6), 220, (1, .42, .12), .5); area('cool', (0, 2.6, 2.5), (0, 3.2, 1), 10, (.45, .6, 1), .8)
    PTS['door'] = (0, 3.1, 1.0); PTS['gap'] = (0, 3.1, .02); PTS['top'] = (0, 2.0, 2.5)
    return cam((.25, -.9, 1.35), (0, 3.1, 1.0), 26)
def house_set(shot):
    flat_world((.012, .02, .04), 1.0); sn = kit.mat_pbr('snow') if hasattr(kit, 'mat_pbr') else M('snow', (.8, .85, .9), .6)
    box('ground', (0, 0, -.05), (60, 60, .1), sn, 0)
    wall = M('siding', (.32, .36, .38), .8); trim = M('trim', (.85, .83, .78), .5); roofm = M('roof', (.06, .07, .08), .7)
    hx, hy, hw, hd, hh = 0, 4, 6.0, 5.0, 5.2
    box('house', (hx, hy, hh / 2), (hw, hd, hh), wall, .02)
    import bmesh as _bm
    me = bpy.data.meshes.new('roof'); bm = _bm.new(); rw, rd, rh = hw / 2 + .35, hd / 2 + .35, 1.9
    v = [bm.verts.new(p) for p in [(-rw, -rd, 0), (rw, -rd, 0), (0, -rd, rh), (-rw, rd, 0), (rw, rd, 0), (0, rd, rh)]]
    for f in [(0, 1, 2), (3, 5, 4), (0, 2, 5, 3), (1, 4, 5, 2), (0, 3, 4, 1)]: bm.faces.new([v[i] for i in f])
    bm.to_mesh(me); ro = kit.link(bpy.data.objects.new('roof', me)); ro.location = (hx, hy, hh); ro.data.materials.append(roofm)
    snr = kit.link(bpy.data.objects.new('roofsnow', me.copy())); snr.location = (hx, hy, hh + .06); snr.scale = (1.0, 1.0, 1.0); snr.data.materials[0] = sn
    lit = kit.mat_emit('firelit', (1, .45, .12), 7); win = kit.mat_emit('dimwin', (.05, .07, .1), .3); lamp = kit.mat_emit('upwin', (1, .7, .4), 1.2)
    for k, xc in enumerate((-1.8, 0, 1.8)):
        box('dwin', (xc, hy - hd / 2 - .01, 1.5), (1.0, .02, 1.3), lit if k != 1 else win, 0)
        box('uwin', (xc, hy - hd / 2 - .01, 3.9), (.9, .02, 1.1), (lamp if k == 2 else win), 0)
        for (cx, cz, sx, sz) in [(xc, 1.5, 1.08, .07), (xc, 3.9, .98, .07)]: box('mull', (cx, hy - hd / 2 - .03, cz), (sx, .02, sz), trim, 0)
    box('frontdoor', (0, hy - hd / 2 - .01, 1.1), (.9, .02, 2.1), M('fdoor', (.4, .05, .04), .4), 0)
    point('firein', (-1.8, hy - hd / 2 + .6, 1.4), 900, (1, .42, .1), .6); point('firein2', (1.8, hy - hd / 2 + .6, 1.4), 600, (1, .42, .1), .6)
    for k in range(6):   # snow-covered shrubs
        bpy.ops.mesh.primitive_uv_sphere_add(radius=.5, location=(-2.7 + k * 1.08, hy - hd / 2 - .5, .15)); o = bpy.context.object; o.scale = (1, .8, .6); o.data.materials.append(sn)
    area('moon', (-8, -10, 9), (0, 4, 2), 400, (.45, .6, 1), 8)
    if shot == 'house':
        wd = M('ladder', (.75, .75, .72), .4, .8)    # an aluminium ladder up to the right upstairs window
        for s in (-.28, .28): box('rail', (1.8 + s, hy - hd / 2 - .9, 1.95), (.06, .06, 4.2), wd, .01, rot=(R(-12), 0, 0))
        for k in range(12): box('rung', (1.8, hy - hd / 2 - 1.3 + k * .08, .3 + k * .33), (.56, .04, .04), wd, .005, rot=(R(-12), 0, 0))
        PTS['upwin'] = (1.8, hy - hd / 2, 3.9); PTS['dwin'] = (-1.8, hy - hd / 2, 1.5); PTS['roof'] = (0, hy, hh + 1.6)
        return cam((-2.2, -6.2, 1.5), (.4, 3, 3.1), 22)
    # safe: Leo wrapped in a blanket on the lawn, Kai and Mia beside him, house glowing behind (out of focus)
    CY = -3.2
    leo_r, lp = person('leo', (0, CY, 0), 10, 1.3, 'happy', {'arm_l': (-80, 0, 20), 'arm_r': (-80, 0, -20)})
    bpy.ops.mesh.primitive_cone_add(vertices=48, radius1=.33, radius2=.2, depth=.62, location=(0, CY - .02, .55)); bl = bpy.context.object
    bl.data.materials.append(fabric('blanket2', (.55, .08, .06))); sb = bl.modifiers.new('s', 'SUBSURF'); sb.levels = 2; bpy.ops.object.shade_smooth()
    person('kai', (-.75, CY + .25, 0), 25, 1.38, 'worried', {'arm_r': (-40, 0, 30)}); person('mia', (.75, CY + .25, 0), -25, 1.33, 'happy', {'arm_l': (-40, 0, -30)})
    area('key', (2.5, CY - 3.4, 2.5), (0, CY, 1), 45, (1, .6, .35), 3); area('rim', (0, CY + 2.5, 3), (0, CY, 1), 160, (1, .45, .15), 4)
    PTS['leo'] = (0, CY, 1.2)
    return cam((.2, CY - 3.6, 1.15), (0, CY, 1.05), 40, 2.4)
def branch_macro(dry):
    """macro on one branch: a twig with needles, a light bulb on its wire"""
    flat_world((.01, .012, .02), 1.0); r = random.Random(2); nm = needle_mat(dry); bark = M('bark', (.14, .08, .04), .8)
    cyl('twig', (0, 0, 0), .012, 1.4, bark, rot=(0, R(80), R(10)), verts=16)
    for k in range(190):
        t = r.uniform(-.65, .65); x = t * math.cos(R(10)); y = t * math.sin(R(10)); z = -t * math.sin(R(10)) * .2
        a = r.uniform(0, 6.28); L_ = .07 + .02 * r.random(); droop = R(25 + 55 * dry)
        o = cyl('needle', (x + math.cos(a) * L_ / 2, y, z + math.sin(a) * L_ / 2 - (.02 * dry)), .0022, L_, nm, rot=(0, R(90) - a, 0), verts=6)
        o.rotation_euler = (droop * (1 if math.sin(a) > 0 else -1) * .3, R(90) - a, r.uniform(-.4, .4))
    if dry:
        fallen = M('fallen', (.3, .17, .05), .7)
        for k in range(40): box('fn', (r.uniform(-.5, .5), r.uniform(-.1, .2), -.32), (.08, .003, .003), fallen, 0, rot=(0, 0, r.uniform(0, 3.14)))
        box('floor', (0, 0, -.335), (3, 3, .01), plank_mat(), 0)
    else: box('floor', (0, 0, -.335), (3, 3, .01), plank_mat(), 0)
    area('key', (.6, -1.2, .8), (0, 0, 0), 30, (1, .7, .45), 1.2); area('rim', (-.8, 1.0, .6), (0, 0, 0), 25, (.45, .6, 1), 1.0)
    PTS['tip'] = (.1, 0, 0); PTS['mid'] = (0, 0, 0)
    return cam((.08, -.62, .14), (.02, 0, -.01), 50, 3.2)
def bulb_macro():
    """an old light strand: a hot bulb in dry needles and a frayed, scorched wire"""
    flat_world((.01, .012, .02), 1.0); r = random.Random(4); nm = needle_mat(.85); bark = M('bark', (.14, .08, .04), .8)
    cyl('twig', (0, .05, -.02), .012, 1.4, bark, rot=(0, R(80), R(10)), verts=16)
    for k in range(160):
        t = r.uniform(-.6, .6); a = r.uniform(0, 6.28); L_ = .07 + .02 * r.random()
        o = cyl('needle', (t + math.cos(a) * L_ / 2, .05, -.02 + math.sin(a) * L_ / 2), .0022, L_, nm, verts=6); o.rotation_euler = (0, R(90) - a, r.uniform(-.4, .4))
    wire = M('wire', (.03, .09, .03), .5); copper = M('cu', (.8, .45, .25), .3, 1.0); soot = M('soot', (.02, .015, .01), .9)
    cyl('wireA', (-.25, -.02, .03), .006, .5, wire, rot=(0, R(90), R(-6)), verts=12); cyl('wireB', (.17, -.02, .03), .006, .2, wire, rot=(0, R(90), R(4)), verts=12)
    for k in range(5): cyl('strand', (.04 + k * .004, -.02 + (k - 2) * .002, .03), .0012, .07, copper, rot=(0, R(90 + (k - 2) * 12), 0), verts=6)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=.03, location=(.05, -.02, .031)); s = bpy.context.object; s.scale = (2.2, 1.4, 1.4); s.data.materials.append(soot)
    cyl('socket', (-.08, -.03, .07), .012, .03, M('sock', (.05, .15, .05), .5), verts=16)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=.016, location=(-.08, -.03, .1)); b = bpy.context.object; b.scale = (1, 1, 1.6); b.data.materials.append(kit.mat_emit('hot', (1, .55, .2), 14))
    point('bulbl', (-.08, -.06, .1), 1.2, (1, .55, .2), .02)
    area('rim', (-.8, 1.0, .6), (0, 0, 0), 18, (.45, .6, 1), 1.0); area('fill', (.4, -1, .5), (0, 0, 0), 6, (1, .6, .35), 1)
    PTS['spark'] = (.05, -.02, .04); PTS['bulb'] = (-.08, -.03, .1)
    return cam((.02, -.42, .16), (0, 0, .04), 50, 2.6)

# ------------------------------------------------------------------ plates
c = None
if PLATE == 'stairs': c = stairs_set()
elif PLATE in ('bed',): c = bedroom_set(PLATE)
elif PLATE == 'door': c = door_set()
elif PLATE in ('house', 'safe'): c = house_set(PLATE)
else:
    living()
    if PLATE == 'calm':
        tree(TX, TY, dry=.25, lit=1.0)
        seated('kai', (-1.75, 1.32, .38), 0, 1.2, 'happy'); seated('mia', (-1.15, 1.32, .38), 0, 1.15, 'neutral')
        c = cam((.1, -2.6, 1.15), (-.75, 1.2, 1.05), 24)
    elif PLATE == 'dry':
        tree(TX, TY, dry=1.0, lit=.8); needles_floor(TX, TY)
        c = cam((.3, -1.8, 1.1), (TX, TY, .95), 28, 5.0)
    elif PLATE == 'hook':
        tree(TX, TY, dry=1.0, lit=0.0, fire=1.0)
        c = cam((.2, -1.45, .95), (TX, TY, 1.2), 22)
    elif PLATE in ('fire', 'wide'):
        tree(TX, TY, dry=1.0, lit=0.0, fire=1.0)
        if PLATE == 'fire':
            person('kai', (.85, -.1, 0), -25, 1.38, 'scared', {'arm_l': (0, -100, 0), 'arm_r': (0, 100, 0)}, -8)
            person('mia', (1.45, .25, 0), -35, 1.33, 'scared', {'arm_l': (0, -140, 0), 'arm_r': (0, 140, 0)}, -6)
            PTS['kai'] = (.85, -.1, 1.1); PTS['mia'] = (1.45, .25, 1.05)
            c = cam((.45, -3.4, 1.15), (.25, 1.0, 1.1), 22)
        else: c = cam((1.5, -2.0, 2.0), (-.35, 1.1, 1.05), 22)
    elif PLATE in ('wet', 'drybr', 'bulb'):    # close on the tree's branches: fresh, bone dry, and a hot old bulb in dry needles
        dr = {'wet': 0.0, 'drybr': 1.0, 'bulb': .85}[PLATE]; tree(TX, TY, dry=dr, lit=(1.0 if PLATE == 'bulb' else .35))
        if PLATE == 'drybr': needles_floor(TX, TY)
        c = cam((TX + .35, TY - 1.15, 1.05), (TX, TY - .3, .95), 45, 2.8)
    elif PLATE == 'cu_mia':
        tree(TX, TY, dry=1.0, lit=1.0)
        person('mia', (.55, -.2, 0), -20, 1.33, 'scared', {'arm_l': (0, -140, 0), 'arm_r': (0, 140, 0)})
        c = cam((1.05, -1.95, 1.12), (.4, -.1, 1.0), 40, 2.4)
    elif PLATE == 'cu_kai':
        tree(TX, TY, dry=1.0, lit=0.0, fire=.8)
        person('kai', (.85, -.4, 0), -15, 1.38, 'angry', {'arm_l': (0, -120, 0), 'arm_r': (0, 120, 0)})
        c = cam((1.25, -2.25, 1.1), (.8, -.3, 1.0), 40, 2.4)
if PTS:
    bpy.context.view_layer.update()
    with open(f'{OUT}/{PLATE}.txt', 'w') as f:
        for k, p in PTS.items(): f.write(f'{k} {proj(c, p)[0]} {proj(c, p)[1]}\n')
sc.render.filepath = f'{OUT}/{PLATE}.png'; bpy.ops.render.render(write_still=True); print('ok', PLATE)
