# Finds faces that will fight for the same pixels: same direction, almost the same plane, overlapping.
# blender --background ArtSource/Apartment.blend --python ArtSource/check_apartment_overlaps.py
from collections import defaultdict
import bpy
import numpy as np

GAP = 0.012     # vertex snapping makes anything closer than this flicker
faces = []
for obj in bpy.data.objects:
    if obj.type != 'MESH':
        continue
    mesh = obj.data
    for poly in mesh.polygons:
        if poly.area < 1e-5:
            continue
        pts = [np.array((-mesh.vertices[i].co.x, mesh.vertices[i].co.z, -mesh.vertices[i].co.y)) for i in poly.vertices]
        n = np.array((-poly.normal.x, poly.normal.z, -poly.normal.y))
        faces.append((obj.name, n, pts))

found = defaultdict(list)
for i, (name_a, na, pa) in enumerate(faces):
    axis = int(np.argmax(np.abs(na)))
    if abs(na[axis]) < 0.999:
        continue
    others = [k for k in range(3) if k != axis]
    a = np.array(pa)
    for name_b, nb, pb in faces[i + 1:]:
        if np.dot(na, nb) < 0.999:
            continue
        b = np.array(pb)
        gap = abs(a[0, axis] - b[0, axis])
        if gap >= GAP:
            continue
        overlap = 1.0
        for k in others:
            overlap *= max(0.0, min(a[:, k].max(), b[:, k].max()) - max(a[:, k].min(), b[:, k].min()))
        if overlap > 1e-4:
            key = tuple(sorted((name_a, name_b)))
            found[key].append((round(float(gap), 4), round(float(a[0, axis]), 3), "xyz"[axis], round(overlap, 4)))

print("RESULT pairs", len(found))
for key, items in sorted(found.items(), key=lambda kv: -len(kv[1])):
    items.sort(key=lambda t: -t[3])
    print("RESULT", key, "count", len(items), "largest", items[:3])
