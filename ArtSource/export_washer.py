"""Exports the kitchen washing machine, written in sand3d (its programs/washing_machine.py), for Unity.

Run with the sand3d env: C:/Users/merla/Tools/sand3d-env/Scripts/python.exe ArtSource/export_washer.py
Writes ArtSource/Washer.glb (sand3d's own export, metres) and Assets/Art/Models/Washer.fbx: Body, Door with its origin on
the hinge (an anomaly needs one renderer and one collider on what it turns) and Drum with its origin on its axle, its local
X, with paddles added or its spin would not show. At rotation 0 in Unity the front looks +X, origin on the floor.
Like the apartment's props, colour is in the vertices and everything uses M_Prop.
"""
import math
import sys
from pathlib import Path

import bpy
import bmesh  # only importable once bpy is
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path.home() / "Tools" / "sand3d" / "programs"))
import sand3d as s3d  # noqa: E402
from sand3d import _core  # noqa: E402
from washing_machine import washer  # noqa: E402

# sand3d's circles get 24-64 pieces a turn (~3k tris for this washer); items in this
# game get 50-500, so every circle is a PS1-style 12-gon and every fillet 3 steps.
_core.TURN_MIN = _core.TURN_MAX = 12

# The program's own size, in mm: 600 deep (`w`, along the front's normal), 600 across, 850 high.
# build_apartment.py leaves it a slot in the kitchen: x -3.25..-2.65, z 0.42..1.02.
SIZE = dict(w=600, d=600, h=850)

# Vertex colours, in the apartment's own terms (the old washer's body was 0.82, 0.82, 0.8).
COLOR = {
    "cabinet": (0.82, 0.82, 0.8),
    "drum": (0.42, 0.43, 0.45),
    "ring": (0.16, 0.17, 0.19),
    "glass": (0.24, 0.29, 0.31),
    "handle": (0.55, 0.55, 0.55),
    "drawer": (0.74, 0.74, 0.72),
    "dial": (0.74, 0.74, 0.72),
}
DOOR = {"ring", "glass", "handle"}
HINGE = Vector((0.345, -0.24, 0.4))     # the program's door_hinge, in metres
AXLE = Vector((0, 0, 0.4))              # the program's drum_spin axis runs along X through here
PIVOTS = {"Door": HINGE, "Drum": AXLE, "Body": Vector((0, 0, 0))}
PADDLE = (0.3, 0.31, 0.33)
FRONT_X = Matrix.Rotation(math.radians(180), 4, "Z")   # its front (+X) to Blender -X, which is Unity +X

glb = ROOT / "ArtSource" / "Washer.glb"
fbx = ROOT / "Assets" / "Art" / "Models" / "Washer.fbx"

s3d.export(washer(**SIZE), str(glb))

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(glb))
bpy.context.view_layer.update()

parts = {"Body": [], "Door": [], "Drum": []}
for ob in [o for o in bpy.data.objects if o.type == "MESH"]:
    me = ob.data
    group = "Door" if ob.name in DOOR else "Drum" if ob.name == "drum" else "Body"
    parts[group].append(
        ([(ob.matrix_world @ v.co).copy() for v in me.vertices], [tuple(p.vertices) for p in me.polygons], COLOR[ob.name]))

# Four paddles inside the drum, across its axis.
BOX = ((0, 4, 6, 2), (1, 3, 7, 5), (2, 6, 7, 3), (0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4))
for y0, y1, z0, z1 in ((-0.02, 0.02, 0.555, 0.59), (-0.02, 0.02, 0.21, 0.245), (0.155, 0.19, 0.38, 0.42), (-0.19, -0.155, 0.38, 0.42)):
    corners = [Vector((0.26 if i & 1 else -0.07, y1 if i & 2 else y0, z1 if i & 4 else z0)) for i in range(8)]
    parts["Drum"].append((corners, BOX, PADDLE))

bpy.ops.wm.read_factory_settings(use_empty=True)
prop = bpy.data.materials.new("M_Prop")
count = {}
for name, pieces in parts.items():
    pivot = PIVOTS[name]
    bm = bmesh.new()
    col = bm.loops.layers.color.new("Col")
    for positions, faces, c in pieces:
        verts = [bm.verts.new(FRONT_X @ (p - pivot)) for p in positions]
        for indices in faces:
            face = bm.faces.new([verts[i] for i in indices])
            face.smooth = False
            for loop in face.loops:
                loop[col] = (c[0], c[1], c[2], 1)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(prop)
    me.color_attributes.active_color = me.color_attributes["Col"]
    ob = bpy.data.objects.new(name, me)
    ob.location = FRONT_X @ pivot
    bpy.context.scene.collection.objects.link(ob)
    me.calc_loop_triangles()
    count[name] = len(me.loop_triangles)
print("TRIS", count, "TOTAL", sum(count.values()))

bpy.ops.export_scene.fbx(filepath=str(fbx), axis_forward="-Z", axis_up="Y", apply_scale_options="FBX_SCALE_ALL",
                         bake_space_transform=True, mesh_smooth_type="FACE", colors_type="LINEAR",
                         object_types={"MESH"}, bake_anim=False)
print("WROTE", fbx)
