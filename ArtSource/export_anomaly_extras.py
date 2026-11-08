"""The things that show up with the appliance anomalies: darkness, hair, fingers, a hand. Faces are Head.fbx, from build_head.py.

Run with the sand3d env: C:/Users/merla/Tools/sand3d-env/Scripts/python.exe ArtSource/export_anomaly_extras.py
Writes Assets/Art/Models/Anomaly_Extras.fbx. Every mesh is in Unity's axes, in the space of what it is parented to in
the scene: a model's root (its front looks +X, origin on the floor) or a door (origin on the hinge, door shut).
Everything uses M_Prop with vertex colours.
"""
import random
from pathlib import Path

import bpy
import bmesh  # only importable once bpy is
from mathutils import Vector

ROOT = Path(__file__).resolve().parent.parent
FBX = ROOT / "Assets" / "Art" / "Models" / "Anomaly_Extras.fbx"

BLACK = (0.02, 0.02, 0.02)
HAIR = (0.025, 0.022, 0.025)
SKIN = (0.8, 0.74, 0.66)
NAIL = (0.26, 0.15, 0.13)
BOX = ((0, 4, 6, 2), (1, 3, 7, 5), (2, 6, 7, 3), (0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4))

random.seed(7)     # the same strands every export


def strands(count, z0, z1, make):
    """Thin strands in a clump: thick in the middle, a few strays at the sides."""
    middle, half = (z0 + z1) / 2, (z1 - z0) / 2
    out = []
    for _ in range(count):
        z = middle + max(-1.0, min(1.0, random.gauss(0, 0.45))) * half
        out.append(make(z, random.uniform(0.006, 0.016)))
    return out


def fall(x, top, bottom, thick=0.005):
    """Hair hanging straight down at x, of uneven length."""
    def make(z, width):
        return ((x + random.uniform(0, 0.006), bottom + random.uniform(0, 0.3) * (top - bottom), z - width / 2),
                (x + 0.006 + thick, top, z + width / 2), HAIR)
    return make


def fingers(y0, step, width, x_inner, x_outer, z_edge, reach):
    """Four fingers from behind a door's edge at z_edge, reaching onto its face towards +z."""
    out = []
    for i in range(4):
        y = y0 + i * step
        out.append(((x_inner - 0.012, y, z_edge), (x_inner, y + width, z_edge + 0.04), SKIN))      # on the inner side, what you see of an open door
        out.append(((x_inner - 0.012, y, z_edge - 0.012), (x_outer, y + width, z_edge), SKIN))     # round the edge
        out.append(((x_outer - 0.014, y, z_edge), (x_outer, y + width, z_edge + reach), SKIN))     # on the face
        out.append(((x_outer - 0.014, y + 0.003, z_edge + reach), (x_outer, y + width - 0.003, z_edge + reach + 0.012), NAIL))
    return out


def hand(x0, x1, z, y):
    """A hand flat against glass, as if pressed from the other side."""
    items = [((x0, y - 0.06, z), (x1, y + 0.03, z + 0.08), SKIN)]                          # palm
    items.append(((x0, y - 0.04, z + 0.08), (x1, y + 0.02, z + 0.1), SKIN))                # thumb
    for i, length in enumerate((0.06, 0.08, 0.09, 0.075)):
        fz = z + 0.002 + i * 0.02
        items.append(((x0, y + 0.03, fz), (x1, y + 0.03 + length, fz + 0.015), SKIN))
    return items


BOXES = {
    # Fridge. Body: x -0.37 back, 0.37 front, z +-0.358 inside, fresh food y 0.12..1.325. Fresh_Door: hinge at its origin,
    # the latch edge at z -0.77, its outer face at x 0.042.
    # The dark inside: a lining seen from within (see LININGS), open at the front.
    "Fridge_Fingers": fingers(0.1, 0.034, 0.024, -0.012, 0.056, -0.77, 0.03),
    # Microwave. Cavity: x up to 0.16, y 0.02..0.27, z -0.118..0.225. Its base stands on the fridge, whose door face is 0.424 ahead.
    "Microwave_Hair": strands(16, -0.06, 0.17, lambda z, w: ((0.1, 0.022, z - w / 2), (0.44, 0.028, z + w / 2), HAIR))
    + strands(24, -0.06, 0.17, fall(0.436, 0.028, -0.5)),
    # Oven. Its body: the door's hinge at x 0.2725, y 0.057; the floor is y -0.18. Hair runs out under the door and down to the floor.
    "Oven_Hair": strands(26, -0.2, 0.2, fall(0.284, 0.06, -0.18)),
    # Washer. Door: hinge at its origin, the glass's face at x -0.015, centre at z +0.24.
    "Washer_Hand": hand(-0.009, -0.003, 0.2, 0.0),
    # Its body: front at x 0.3, the porthole's bottom at y 0.18.
    "Washer_Hair": strands(14, -0.13, 0.13, lambda z, w: ((0.05, 0.186, z - w / 2), (0.319, 0.192, z + w / 2), HAIR))
    + strands(24, -0.13, 0.13, fall(0.313, 0.192, -0.02)),
    # Air conditioner. Vent: x 0.17, y 0.05, z +-0.4. The clump hangs from its middle.
    "Aircon_Hair_Short": strands(28, -0.3, 0.3, fall(0.17, 0.09, -0.42)),
    "Aircon_Hair_Long": strands(30, -0.26, 0.26, fall(0.18, 0.09, -2.0)),
}
# name: (lo, hi): a box seen from within, with no front (+X) face. It hides the bright insides, and a head fits in it.
LININGS = {
    "Fridge_Void": ((-0.338, 0.125, -0.352), (0.35, 1.32, 0.352)),
    "Microwave_Void": ((-0.15, 0.028, -0.11), (0.15, 0.264, 0.218)),
}


def to_blender(p):
    return Vector((-p[0], -p[2], p[1]))


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
prop = bpy.data.materials.new("M_Prop")
count = {}


def add(name, bm, material):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(material)
    if me.color_attributes:
        me.color_attributes.active_color = me.color_attributes[0]
    scene.collection.objects.link(bpy.data.objects.new(name, me))
    me.calc_loop_triangles()
    count[name] = len(me.loop_triangles)


for name, items in BOXES.items():
    bm = bmesh.new()
    col = bm.loops.layers.color.new("Col")
    for lo, hi, c in items:
        verts = [bm.verts.new(to_blender((hi[0] if i & 1 else lo[0], hi[1] if i & 2 else lo[1], hi[2] if i & 4 else lo[2]))) for i in range(8)]
        for indices in BOX:
            face = bm.faces.new([verts[i] for i in reversed(indices)])   # Unity's axes are left-handed
            face.smooth = False
            for loop in face.loops:
                loop[col] = (c[0], c[1], c[2], 1)
    add(name, bm, prop)

for name, (lo, hi) in LININGS.items():
    bm = bmesh.new()
    col = bm.loops.layers.color.new("Col")
    verts = [bm.verts.new(to_blender((hi[0] if i & 1 else lo[0], hi[1] if i & 2 else lo[1], hi[2] if i & 4 else lo[2]))) for i in range(8)]
    for k, indices in enumerate(BOX):
        if k == 1:      # the +x face stays open
            continue
        face = bm.faces.new([verts[i] for i in indices])     # not reversed: it faces inwards
        face.smooth = False
        for loop in face.loops:
            loop[col] = (BLACK[0], BLACK[1], BLACK[2], 1)
    add(name, bm, prop)

print("TRIS", count, "TOTAL", sum(count.values()))
bpy.ops.export_scene.fbx(filepath=str(FBX), axis_forward="-Z", axis_up="Y", apply_scale_options="FBX_SCALE_ALL",
                         bake_space_transform=True, mesh_smooth_type="FACE", colors_type="LINEAR",
                         object_types={"MESH"}, bake_anim=False)
print("WROTE", FBX)
