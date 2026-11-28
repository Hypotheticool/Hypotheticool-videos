"""Story Short: Kai started choking at dinner. One Cycles still per plate (animated in 2D by choke_anim.py: camera moves, cuts,
thrust shakes, the flying bite, breath/air graphics). Reuses the night room (teal walls, warm lamp, sturdy wood table) and helpers
from quake_plate.py (exec'd up to its plates section); the table becomes a Thanksgiving-leftovers dinner.
python3 choke_plate.py <plate> [res_scale] -> choke/plates/<plate>.png (+ .txt with projected 2D points)
dinner (wide: Kai, Mia, Leo seated, Kai laughing), cu_kai (Kai seated, mid-bite laugh), cu_leo (Leo seated, worried),
hook (close: Kai standing, both hands at his throat), choke (wide: Kai standing choking, Mia rising, Leo seated),
side (3/4 side close on Kai's hands at the throat), cu_mia (Mia, determined, pointing), call (Leo with the phone at his ear),
back (Mia behind Kai, arm raised for a back blow, Kai bent forward), thrust (Mia behind Kai, arms round his waist, side view),
relief (Kai breathing again, Mia + Leo beside him), floor (Kai lying on the floor, Mia kneeling, hands on his chest: CPR),
chair (Leo alone, bent over a chair back), anat (real anatomy: trachea, bronchi, lungs, diaphragm; BodyParts3D)"""
import sys, os, math, random
QP = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'quake_plate.py')
src = open(QP).read().split('# ------------------------------------------------------------------ plates')[0]
exec(compile(src, QP, 'exec'))
OUT = '/home/claude/b3d/choke/plates'; os.makedirs(OUT, exist_ok=True)
PLATE = name; R = math.radians

def person(who, loc, yaw=0.0, h=1.35, expr='neutral', arms=None, lean=0.0, arm_len=None):
    root, parts = kit.character(who, (0, 0, 0), h)
    parts['face_mat'].node_tree.nodes['expr'].outputs[0].default_value = kit.EXPRS.index(expr)
    for a, r in (arms or {}).items(): parts[a].rotation_euler = tuple(R(v) for v in r)
    for a, s in (arm_len or {}).items(): parts[a].scale = (1, 1, s)
    root.rotation_euler = (R(lean), 0, R(yaw)); root.location = loc
    return root, parts
def seated(who, loc, yaw=0.0, h=1.3, expr='neutral', arms=None):
    root, parts = person(who, loc, yaw, h, expr, arms)
    for lg in ('leg_l', 'leg_r'): parts[lg].rotation_euler = (R(90), 0, 0)
    return root, parts
def aim(root, parts, arm, target, h):
    """point an arm (pivot at the shoulder, stick along -Z) at a world target; stretch it to reach"""
    bpy.context.view_layer.update(); piv = parts[arm]; piv.rotation_euler = (0, 0, 0); bpy.context.view_layer.update()
    sh = piv.matrix_world.translation; d = Vector(target) - sh
    dl = root.matrix_world.to_3x3().normalized().inverted() @ d
    q = Vector((0, 0, -1)).rotation_difference(dl.normalized()); piv.rotation_mode = 'QUATERNION'; piv.rotation_quaternion = q
    piv.scale = (1, 1, d.length / (.25 * h))
THROAT = {'arm_l': (-100, 0, 27), 'arm_r': (-100, 0, -27)}     # both hands clutched under the chin (the universal choking sign)

TX, TY, TZ = .15, .15, .81       # tabletop centre (quake_plate room2)
def chair(x, y, yaw=0.0, zs=1.0):
    wd = wood_mat('chair', (.3, .16, .07)); c, s = math.cos(R(yaw)), math.sin(R(yaw))
    P = lambda dx, dy: (x + dx * c - dy * s, y + dx * s + dy * c)
    box('seat', (*P(0, 0), .46 * zs), (.44, .42, .04), wd, .008, rot=(0, 0, R(yaw)))
    for dx in (-.19, .19):
        for dy in (-.17, .17): box('cleg', (*P(dx, dy), .22 * zs), (.04, .04, .44 * zs), wd, .004, rot=(0, 0, R(yaw)))
    for dx in (-.19, .19): box('post', (*P(dx, .19), .72 * zs), (.04, .04, .52 * zs), wd, .004, rot=(0, 0, R(yaw)))
    box('rail', (*P(0, .19), .94 * zs), (.42, .035, .09), wd, .006, rot=(0, 0, R(yaw))); box('rail2', (*P(0, .19), .72 * zs), (.42, .03, .05), wd, .004, rot=(0, 0, R(yaw)))
def dinner_table(candles=True):
    """Thanksgiving leftovers: a linen runner, plates with turkey slices, mashed potatoes, cranberry sauce, glasses, candles"""
    r = random.Random(3)
    for o in list(bpy.data.objects):
        if o.name.split('.')[0] == 'rug': bpy.data.objects.remove(o, do_unlink=True)
    box('runner', (TX, TY, TZ - .025), (1.5, .4, .004), fabric('runner', (.6, .5, .35)), 0)
    plate_m = M('china', (.85, .84, .8), .25, 0, .4); turkey = kit.mat_pbr('wood') if False else M('turkey', (.62, .4, .2), .55)
    mash = M('mash', (.86, .8, .62), .7); cran = M('cran', (.45, .02, .05), .25, 0, .5); green = M('beans', (.12, .3, .08), .6)
    glass = bpy.data.materials.new('glass'); glass.use_nodes = True; bs = glass.node_tree.nodes['Principled BSDF']
    bs.inputs['Transmission Weight'].default_value = 1; bs.inputs['Roughness'].default_value = .02; bs.inputs['IOR'].default_value = 1.5
    for (px, py) in [(-.5, .5), (.15, .52), (.8, .5), (-.5, -.2), (.8, -.2)]:
        if py < 0 and False: continue
        cyl('plate', (TX + px * .85, TY + (py - .15) * .55, TZ - .01), .13, .015, plate_m, verts=64)
        for k in range(3): box('slice', (TX + px * .85 - .03 + k * .03, TY + (py - .15) * .55 + .02, TZ + .008), (.07, .05, .012), turkey, .006, rot=(0, 0, R(20 + 15 * k)))
        bpy.ops.mesh.primitive_uv_sphere_add(radius=.035, location=(TX + px * .85 + .05, TY + (py - .15) * .55 - .04, TZ + .01)); o = bpy.context.object; o.scale = (1, 1, .55); o.data.materials.append(mash); bpy.ops.object.shade_smooth()
        for k in range(6): cyl('bean', (TX + px * .85 - .06 + .01 * k, TY + (py - .15) * .55 - .05, TZ + .01), .005, .05, green, rot=(0, R(90), R(30 * k)), verts=8)
        cyl('glassw', (TX + px * .85 + .14, TY + (py - .15) * .55 + .1, TZ + .06), .03, .12, glass, verts=32)
    cyl('platter', (TX, TY + .02, TZ), .2, .02, plate_m, verts=64)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=.13, location=(TX, TY + .02, TZ + .06)); o = bpy.context.object; o.scale = (1.3, .95, .65); o.data.materials.append(M('roast', (.45, .22, .07), .4, 0, .6)); bpy.ops.object.shade_smooth()
    cyl('cranb', (TX + .35, TY + .05, TZ + .02), .06, .04, glass, verts=32); cyl('cranj', (TX + .35, TY + .05, TZ + .02), .052, .032, cran, verts=32)
    if candles:
        for dx in (-.4, -.25):
            cyl('candle', (TX + dx, TY + .05, TZ + .1), .018, .2, M('wax', (.9, .86, .78), .5), verts=24)
            bpy.ops.mesh.primitive_uv_sphere_add(radius=.012, location=(TX + dx, TY + .05, TZ + .22)); f = bpy.context.object; f.scale = (1, 1, 1.9); f.data.materials.append(kit.mat_emit('flame', (1, .6, .25), 30))
            point('candle', (TX + dx, TY + .05, TZ + .26), 6, (1, .6, .3), .02)
    point('pend', (TX, TY, 2.1), 55, (1, .66, .38), .25)      # warm light over the table
    PTS['table'] = (TX, TY, TZ)

def dining():
    room(); room2(); haze(.010, (0, -.2, 1.3), (3, 2.5, 1.3)); dinner_table()
# seats: Kai on the far side (faces camera), Leo at the left end, Mia at the right end
KAI_S, LEO_S, MIA_S = (TX, TY + .62), (TX - .95, TY), (TX + .95, TY)

c = None
if PLATE == 'anat':
    flat_world((.006, .01, .018), 1.0)
    an = kit.anatomy('trachea', 'bronchus', 'lobe of .* lung', 'middle lobe of lung', 'diaphragm', size=2.0, smooth_sub=0)
    bpy.context.view_layer.update()
    area('key', (1.5, -3.5, 2.0), (0, 0, 0), 260, (1, .75, .55), 2.5); area('rim', (-2.2, 2.5, 1.5), (0, 0, 0), 320, (.45, .6, 1), 2.5)
    area('fill', (-2, -3, -1), (0, 0, 0), 60, (.5, .65, 1), 3)
    import numpy as np
    for o in bpy.data.objects:
        if o.type == 'MESH': print('PART', o.name, [round(v, 2) for v in (o.matrix_world @ Vector(o.bound_box[0]))], [round(v, 2) for v in (o.matrix_world @ Vector(o.bound_box[6]))])
    obs = [o for o in bpy.data.objects if o.type == 'MESH']
    def bb(pred):
        P = np.array([o.matrix_world @ Vector(cc) for o in obs if pred(o.name) for cc in o.bound_box]); return P.min(0), P.max(0)
    lo, hi = bb(lambda n: True); tl, th = bb(lambda n: n.startswith('trachea')); dl, dh = bb(lambda n: n.startswith('diaphragm'))
    PTS['trach_top'] = ((tl[0] + th[0]) / 2, (tl[1] + th[1]) / 2, th[2]); PTS['trach_mid'] = ((tl[0] + th[0]) / 2, (tl[1] + th[1]) / 2, (tl[2] + th[2]) / 2 + .1)
    PTS['diaph'] = ((dl[0] + dh[0]) / 2, (dl[1] + dh[1]) / 2, dh[2]); PTS['diaph_lo'] = ((dl[0] + dh[0]) / 2, dl[1], dl[2])
    PTS['lung_l'] = (lo[0] * .6, 0, 0); PTS['lung_r'] = (hi[0] * .6, 0, 0)
    c = cam((0, -5.2, .25), (0, 0, .1), 50)
else:
    dining()
    if PLATE in ('dinner', 'cu_kai', 'cu_leo'):
        chair(*KAI_S, 180); chair(*LEO_S, -90); chair(*MIA_S, 90)
        k_r, kp = seated('kai', (KAI_S[0], KAI_S[1], .17), 0, 1.3, 'happy', {'arm_r': (-70, 0, -10)})
        seated('leo', (LEO_S[0], LEO_S[1], .17), 70, 1.24, 'happy' if PLATE == 'dinner' else 'worried', {'arm_l': (-60, 0, 10)})
        seated('mia', (MIA_S[0], MIA_S[1], .17), -70, 1.26, 'smirk', {'arm_r': (-55, 0, -10)})
        PTS['kai'] = (KAI_S[0], KAI_S[1], 1.35); PTS['leo'] = (LEO_S[0], LEO_S[1], 1.3); PTS['mia'] = (MIA_S[0], MIA_S[1], 1.32)
        PTS['kai_mouth'] = (KAI_S[0], KAI_S[1] - .25, 1.2)
        if PLATE == 'dinner': c = cam((.25, -3.0, 1.3), (.1, .35, .95), 24)
        elif PLATE == 'cu_kai': c = cam((.0, -1.35, 1.3), (KAI_S[0], KAI_S[1], 1.25), 40, 2.4)
        else: c = cam((-.2, -1.25, 1.3), (LEO_S[0], LEO_S[1], 1.2), 40, 2.4)
    elif PLATE in ('hook', 'choke', 'side', 'cu_mia', 'call'):
        chair(*LEO_S, -90); chair(TX + .95, TY + .45, 120); chair(TX - .35, TY - .65, 25)
        KX, KY = TX - .35, TY - .95          # Kai has stood up from his chair, in front of the table
        person('kai', (KX, KY, 0), 8, 1.38, 'scared', THROAT, -4)
        PTS['kai'] = (KX, KY, 1.15); PTS['mouth'] = (KX, KY - .27, 1.0); PTS['hands'] = (KX, KY - .24, .85); PTS['face'] = (KX, KY - .2, 1.12)
        if PLATE == 'call':
            lr, lp = seated('leo', (LEO_S[0], LEO_S[1], .17), 15, 1.24, 'scared', {'arm_r': (-40, 0, -10)})
            ear = (LEO_S[0] - .3, LEO_S[1] - .02, 1.12)
            ph = box('phone', ear, (.05, .1, .2), M('phoneb', (.02, .02, .025), .25), .01, rot=(0, 0, R(15)))
            box('phscr', (ear[0] - .026, ear[1], ear[2]), (.004, .085, .17), kit.mat_emit('phs', (.4, .7, 1), 3), 0, rot=(0, 0, R(15)))
            aim(lr, lp, 'arm_l', (ear[0], ear[1], ear[2] - .08), 1.24); PTS['phone'] = ear
        else: seated('leo', (LEO_S[0], LEO_S[1], .17), 60, 1.24, 'scared', {'arm_l': (0, -60, 0), 'arm_r': (0, 60, 0)})
        person('mia', (TX + .65, TY - .55, 0), -55, 1.33, 'angry' if PLATE == 'cu_mia' else 'surprised',
               {'arm_r': (-90, 0, 40)} if PLATE == 'cu_mia' else {'arm_l': (0, -50, 0), 'arm_r': (0, 50, 0)})
        PTS['leo'] = (LEO_S[0], LEO_S[1], 1.3); PTS['mia'] = (TX + .65, TY - .55, 1.1)
        if PLATE == 'hook': c = cam((KX + .15, KY - 1.25, 1.12), (KX, KY, 1.0), 40, 2.0)
        elif PLATE == 'choke': c = cam((.0, -3.1, 1.3), (.0, -.3, .9), 28)
        elif PLATE == 'side': c = cam((KX - .95, KY - .7, 1.0), (KX, KY - .1, .95), 45, 2.2)
        elif PLATE == 'cu_mia': c = cam((TX + .15, TY - 1.95, 1.15), (TX + .65, TY - .55, 1.05), 40, 2.4)
        else: c = cam((LEO_S[0] - .3, LEO_S[1] - 1.3, 1.2), (LEO_S[0] - .08, LEO_S[1], 1.12), 32, 2.4)
    elif PLATE in ('back', 'thrust', 'relief'):
        chair(*LEO_S, -90)
        KX, KY = TX - .2, TY - 1.05
        if PLATE == 'back':
            person('kai', (KX, KY, 0), 0, 1.38, 'scared', THROAT, 16)
            mr, mp = person('mia', (KX + .03, KY + .5, 0), 0, 1.33, 'angry', {'arm_r': (0, 15, 0)})
            aim(mr, mp, 'arm_l', (KX - .38, KY + .62, 1.42), 1.33)
            PTS['blow'] = (KX, KY + .14, .92); PTS['mouth'] = (KX, KY - .45, .95); PTS['face'] = (KX, KY - .4, 1.05); PTS['hand'] = (KX - .1, KY + .45, 1.35)
            c = cam((KX - 2.4, KY + .1, 1.05), (KX, KY + .15, .85), 32, 3.2)
        elif PLATE == 'thrust':
            person('kai', (KX, KY, 0), 0, 1.38, 'scared', THROAT, 8)
            mr, mp = person('mia', (KX + .42, KY + .4, 0), -20, 1.33, 'angry', {}, 4)
            aim(mr, mp, 'arm_l', (KX - .02, KY - .2, .52), 1.33); aim(mr, mp, 'arm_r', (KX + .04, KY - .19, .5), 1.33)
            PTS['fist'] = (KX, KY - .2, .52); PTS['mouth'] = (KX, KY - .3, .98); PTS['face'] = (KX, KY - .25, 1.1); PTS['kai'] = (KX, KY, 1.1)
            c = cam((KX + 1.2, KY - 1.9, 1.05), (KX + .15, KY + .1, .82), 32, 3.2)
        else:
            person('kai', (KX, KY, 0), 10, 1.38, 'happy', {'arm_r': (-40, 0, -35)}, 3)
            person('mia', (KX + .6, KY + .2, 0), -25, 1.33, 'happy', {'arm_l': (-50, 0, -40)})
            person('leo', (KX - .6, KY + .25, 0), 25, 1.3, 'surprised', {'arm_r': (-20, 0, 160)})
            PTS['kai'] = (KX, KY, 1.15); PTS['mouth'] = (KX, KY - .27, 1.0)
            c = cam((KX + .1, KY - 2.3, 1.2), (KX, KY + .1, 1.0), 32, 2.8)
    elif PLATE == 'floor':
        KX, KY = TX - .3, TY - 1.2
        k_r, kp = person('kai', (0, 0, 0), 0, 1.38, 'bored', {'arm_l': (0, -15, 0), 'arm_r': (0, 15, 0)})
        k_r.rotation_euler = (R(-90), 0, R(90)); k_r.location = (KX + .4, KY, .17)
        CH = (KX - .3, KY - .05, .3)
        m_r, mp = person('mia', (KX - .3, KY + .5, -.2), 0, 1.33, 'angry', {}, 22)
        aim(m_r, mp, 'arm_l', (CH[0] - .02, CH[1], CH[2] + .05), 1.33); aim(m_r, mp, 'arm_r', (CH[0] + .02, CH[1], CH[2] + .05), 1.33)
        PTS['chest'] = CH; PTS['kai'] = (KX - .7, KY, .3)
        c = cam((KX + .3, KY - 2.2, 1.5), (KX - .3, KY + .15, .4), 30, 3.0)
    elif PLATE == 'chair':
        chair(-1.0, -.6, 180, .62)
        person('leo', (-1.0, -.6 - .36, 0), 180, 1.3, 'scared', {'arm_l': (-40, 0, 20), 'arm_r': (-40, 0, -20)}, 32)
        PTS['belly'] = (-1.0, -.79, .55); PTS['leo'] = (-1.0, -.85, .95); PTS['rail'] = (-1.0, -.79, .58)
        c = cam((-2.8, -.85, .95), (-1.0, -.8, .62), 24, 3.2)
if PTS:
    bpy.context.view_layer.update()
    with open(f'{OUT}/{PLATE}.txt', 'w') as f:
        for k, p in PTS.items(): f.write(f'{k} {proj(c, p)[0]} {proj(c, p)[1]}\n')
sc.render.filepath = f'{OUT}/{PLATE}.png'; bpy.ops.render.render(write_still=True); print('ok', PLATE)
