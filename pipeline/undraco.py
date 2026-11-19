"""Rewrite a Draco-compressed .glb as a plain .glb (the pip bpy build lacks Blender's Draco bridge).
usage: python3 undraco.py in.glb out.glb   (needs: pip install DracoPy pygltflib)"""
import sys, struct
import numpy as np, DracoPy, pygltflib
from pygltflib import GLTF2, Accessor, BufferView

def undraco(src, dst):
    g = GLTF2().load_binary(src); blob = bytearray(g.binary_blob() or b'')
    def add(arr, ctype, typ, target):
        arr = np.ascontiguousarray(arr); pad = (-len(blob)) % 4; blob.extend(b'\0' * pad); off = len(blob); blob.extend(arr.tobytes())
        g.bufferViews.append(BufferView(buffer=0, byteOffset=off, byteLength=arr.nbytes, target=target))
        acc = Accessor(bufferView=len(g.bufferViews) - 1, componentType=ctype, count=len(arr), type=typ)
        if typ == 'VEC3' and ctype == 5126: acc.min = arr.min(0).tolist(); acc.max = arr.max(0).tolist()
        g.accessors.append(acc); return len(g.accessors) - 1
    n = 0
    for mesh in g.meshes:
        for p in mesh.primitives:
            ext = (p.extensions or {}).get('KHR_draco_mesh_compression')
            if not ext: continue
            bv = g.bufferViews[ext['bufferView']]; data = bytes(blob[(bv.byteOffset or 0):(bv.byteOffset or 0) + bv.byteLength])
            d = DracoPy.decode(data)
            pts = np.asarray(d.points, np.float32).reshape(-1, 3); faces = np.asarray(d.faces, np.uint32).reshape(-1)
            p.attributes = pygltflib.Attributes(POSITION=add(pts, 5126, 'VEC3', 34962))
            if d.normals is not None and len(d.normals): p.attributes.NORMAL = add(np.asarray(d.normals, np.float32).reshape(-1, 3), 5126, 'VEC3', 34962)
            tc = getattr(d, 'tex_coord', None)
            if tc is not None and len(tc) and 'TEXCOORD_0' in ext['attributes']: p.attributes.TEXCOORD_0 = add(np.asarray(tc, np.float32).reshape(-1, 2), 5126, 'VEC2', 34962)
            p.indices = add(faces, 5125, 'SCALAR', 34963)
            p.extensions = {k: v for k, v in p.extensions.items() if k != 'KHR_draco_mesh_compression'}; n += 1
    for lst in ('extensionsUsed', 'extensionsRequired'):
        v = getattr(g, lst) or []; setattr(g, lst, [e for e in v if e != 'KHR_draco_mesh_compression'])
    g.buffers[0].byteLength = len(blob); g.set_binary_blob(bytes(blob)); g.save_binary(dst); return n

if __name__ == '__main__':
    print(undraco(sys.argv[1], sys.argv[2]), 'primitives decoded')
