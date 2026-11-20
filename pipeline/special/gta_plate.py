"""Render one high-res real-Earth plate per scene + projected pixel coords of the real places/route.
python3 gta_plate.py <scene>  ->  gta6/plates/p<scene>.png + p<scene>.json
(Animation is done in gta_anim.py as slow camera push-ins over the plate: same look, ~50x faster than per-frame 3D.)"""
import sys, math, json, os
sys.path.insert(0, '/home/claude/b3d')
import bpy, kit
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
idx = int(sys.argv[1]); OUT = '/home/claude/b3d/gta6/plates'; os.makedirs(OUT, exist_ok=True)
W, H = 1350, 2400
sc = kit.reset(res=(W, H), samples=int(os.environ.get('SAMPLES', 20)))
sc.cycles.adaptive_threshold = 0.03; sc.cycles.max_bounces = 3; sc.cycles.diffuse_bounces = 1; sc.cycles.glossy_bounces = 1
R = 10.0; FL = 0.0
LL = lambda lat, lon, h=0.0: kit.latlon(lat, lon, R, FL, h)
kit.world(strength=.5)
n = LL(27.6, -82.5).normalized(); z = Vector((0, 0, 1)); e = z.cross(n).normalized()
SUN = (n * 1.0 - e * .55 + z * .35).normalized(); kit.sun_lamp(tuple(SUN), 4.2)
root, spin = kit.earth(R, tuple(SUN), tilt_deg=0, face_lon=FL, clouds=False, atmo=True)
_b = [n_ for n_ in bpy.data.materials['earth'].node_tree.nodes if n_.type == 'BSDF_PRINCIPLED'][0]
_b.inputs['Specular IOR Level'].default_value = .08   # soften the sun-glint hotspot so the map stays readable
for _n in bpy.data.materials['earth'].node_tree.nodes:
    if _n.type == 'MAP_RANGE' and abs(_n.inputs['To Max'].default_value - .32) < 1e-3: _n.inputs['To Max'].default_value = .62
CAMS = {   # lat, lon, height, look_lat, look_lon, lens
    'hook': (24.2, -80.7, 1.1, 26.7, -81.45, 24), 'state': (23.9, -82.6, 3.6, 27.6, -83.0, 26),
    'map': (27.6, -83.7, 2.75, 27.6, -83.7, 30), 'area': (23.8, -82.6, 2.9, 27.6, -82.6, 28),
    'ns': (26.8, -79.0, 2.6, 27.7, -82.4, 28), 'coast': (26.9, -79.4, 1.35, 25.9, -80.25, 26),
    'drive': (24.4, -83.0, 3.0, 27.9, -83.9, 28), 'follow': (26.8, -81.1, 1.55, 28.8, -82.4, 26)}
SCENE_CAM = ['hook', 'state', 'map', 'area', 'ns', 'coast', 'drive', 'follow', 'hook']
c = CAMS[SCENE_CAM[idx]]
if c[0] == c[3] and c[1] == c[4]:   # straight down: look at the point from directly above, north up
    cam, tgt = kit.camera(tuple(LL(c[0], c[1], c[2])), tuple(LL(c[0], c[1], 0)), lens=c[5])
    cam.constraints[0].up_axis = 'UP_Y'
    up = kit.link(bpy.data.objects.new('up', None)); up.location = tuple(LL(c[0] + 5, c[1], c[2]))
    cam.constraints.clear(); d = (LL(c[0], c[1], 0) - LL(c[0], c[1], c[2])).normalized(); north = (LL(c[0] + .01, c[1]) - LL(c[0], c[1])).normalized()
    from mathutils import Matrix
    zc = -d; yc = (north - zc * north.dot(zc)).normalized(); xc = yc.cross(zc)
    cam.matrix_world = Matrix((xc, yc, zc)).transposed().to_4x4() @ Matrix.Identity(4); cam.location = tuple(LL(c[0], c[1], c[2]))
else:
    cam, tgt = kit.camera(tuple(LL(c[0], c[1], c[2])), tuple(LL(c[3], c[4], 0)), lens=c[5])
bpy.context.view_layer.update()
ROUTE = [(24.555, -81.780), (24.71, -81.09), (25.09, -80.45), (25.45, -80.48), (25.76, -80.19), (26.14, -80.33), (26.14, -81.10),
         (26.14, -81.79), (26.64, -81.87), (27.34, -82.53), (27.95, -82.46), (28.55, -82.39), (29.19, -82.14), (30.19, -82.64),
         (30.44, -84.28), (30.75, -86.57), (30.42, -87.22)]
def dense(pts, steps=16):
    out = []
    for (a1, o1), (a2, o2) in zip(pts[:-1], pts[1:]):
        for k in range(steps): t = k / steps; out.append((a1 + (a2 - a1) * t, o1 + (o2 - o1) * t))
    return out + [pts[-1]]
def px(lat, lon, h=0.0):
    v = world_to_camera_view(sc, cam, LL(lat, lon, h)); return [v.x * W, (1 - v.y) * H, v.z]
PLACES = {'keywest': (24.555, -81.78), 'pensacola': (30.42, -87.22), 'miami': (25.76, -80.19), 'keys': (24.71, -81.09),
          'everglades': (25.55, -80.90), 'n_end': (31.0, -82.2), 's_end': (24.55, -82.2), 'center': (27.8, -81.7)}
info = {'size': [W, H], 'route': [px(*p) for p in dense(ROUTE)], 'route_idx': [k * 16 for k in range(len(ROUTE))],
        'ns': [px(*p) for p in dense([(31.0, -82.2), (24.55, -82.2)], 60)], 'places': {k: px(*v) for k, v in PLACES.items()}}
json.dump(info, open(f'{OUT}/p{idx}.json', 'w'))
sc.render.filepath = f'{OUT}/p{idx}.png'; bpy.ops.render.render(write_still=True)
