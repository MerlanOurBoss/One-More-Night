"""Exports the kitchen fridge for Unity from Fridge_source.usda (sand3d-articraft, see CREDITS.md).

Run with the sand3d env: C:/Users/merla/Tools/sand3d-env/Scripts/python.exe ArtSource/export_fridge.py
Writes Assets/Art/Models/Fridge.fbx: three objects, Body and the two doors, each door's origin on its
hinge so that turning it about Y opens it. At rotation 0 in Unity the front looks +X, origin on the floor.
Like the apartment's props, colour is in the vertices (layer "Col") and everything uses M_Prop.
"""
import math
import sys
from pathlib import Path

import bpy
import bmesh  # only importable once bpy is
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "ArtSource" / "Fridge_source.usda"
FBX = ROOT / "Assets" / "Art" / "Models" / "Fridge.fbx"

# Slightly aged, in the apartment's own colour terms: the source's materials are spotless.
COLOR = {
    "plastic__f7fafa": (0.82, 0.82, 0.78),   # doors
    "plastic__edeff2": (0.76, 0.76, 0.72),   # body
    "plastic__d1d4d6": (0.45, 0.45, 0.44),   # gaskets
    "plastic__b3b8bf": (0.62, 0.63, 0.65),   # brackets
    "steel__b3b8bf": (0.62, 0.63, 0.65),     # handles, hinges
    "plastic__303335": (0.1, 0.1, 0.11),     # grille
}
GROUPS = {"freezer_outer_panel_group": "Freezer_Door", "fresh_food_outer_panel_group": "Fresh_Door"}

# The note and magnets of the old fridge, on the fresh food door. (lo, hi, colour) in the source's
# coordinates: the door's face is at y 0.426; they stand 1.2 cm proud, closer than that flickers.
FACE, PROUD = 0.42, 0.438
DOOR_ITEMS = [
    ((-0.1, FACE, 0.98), (0.06, PROUD, 1.18), (0.86, 0.84, 0.72)),    # note
    ((-0.04, FACE, 1.16), (0.0, PROUD + 0.006, 1.2), (0.72, 0.16, 0.14)),  # its red magnet
    ((0.12, FACE, 0.9), (0.18, PROUD, 0.96), (0.2, 0.42, 0.62)),      # blue
    ((0.16, FACE, 1.08), (0.22, PROUD, 1.14), (0.84, 0.66, 0.2)),     # yellow
]

# Blender +Z turn of 90: the source's front (+Y) looks Blender -X, which is Unity +X.
TURN = Matrix.Rotation(math.radians(90), 4, "Z")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.usd_import(filepath=str(SOURCE))
bpy.context.view_layer.update()


def group_of(ob):
    while ob:
        if ob.name in GROUPS:
            return ob
        ob = ob.parent
    return None


parts = {"Body": dict(bm=bmesh.new(), pivot=Vector((0, 0, 0)))}
for name, key in ((n, GROUPS[n]) for n in GROUPS):
    parts[key] = dict(bm=bmesh.new(), pivot=bpy.data.objects[name].matrix_world.translation.copy())


def add_faces(part, positions, faces, colors):
    """`positions` in the source's coordinates; `colors` one per face."""
    bm = part["bm"]
    col = bm.loops.layers.color.get("Col") or bm.loops.layers.color.new("Col")
    verts = [bm.verts.new(TURN @ (Vector(p) - part["pivot"])) for p in positions]
    for indices, c in zip(faces, colors):
        face = bm.faces.new([verts[i] for i in indices])
        face.smooth = False
        for loop in face.loops:
            loop[col] = (c[0], c[1], c[2], 1)


for ob in [o for o in bpy.data.objects if o.type == "MESH"]:
    group = group_of(ob)
    part = parts[GROUPS[group.name]] if group else parts["Body"]
    me = ob.data
    add_faces(part, [ob.matrix_world @ v.co for v in me.vertices], [p.vertices[:] for p in me.polygons],
              [COLOR[me.materials[p.material_index].name] for p in me.polygons])

BOX = ((0, 4, 6, 2), (1, 3, 7, 5), (2, 6, 7, 3), (0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4))  # -x +x +y -z +z -y
for lo, hi, c in DOOR_ITEMS:
    corners = [(hi[0] if i & 1 else lo[0], hi[1] if i & 2 else lo[1], hi[2] if i & 4 else lo[2]) for i in range(8)]
    add_faces(parts["Fresh_Door"], corners, BOX[:5], [c] * 5)  # no face on the door's side

bpy.ops.wm.read_factory_settings(use_empty=True)
prop = bpy.data.materials.new("M_Prop")
scene = bpy.context.scene
total = {}
for name, part in parts.items():
    me = bpy.data.meshes.new(name)
    part["bm"].to_mesh(me)
    part["bm"].free()
    me.materials.append(prop)
    me.color_attributes.active_color = me.color_attributes["Col"]
    ob = bpy.data.objects.new(name, me)
    ob.location = TURN @ part["pivot"]
    scene.collection.objects.link(ob)
    me.calc_loop_triangles()
    total[name] = len(me.loop_triangles)
print("TRIS", total, "TOTAL", sum(total.values()))

bpy.ops.export_scene.fbx(filepath=str(FBX), axis_forward="-Z", axis_up="Y", apply_scale_options="FBX_SCALE_ALL",
                         bake_space_transform=True, mesh_smooth_type="FACE", colors_type="LINEAR",
                         object_types={"MESH"}, bake_anim=False)
print("WROTE", FBX)
