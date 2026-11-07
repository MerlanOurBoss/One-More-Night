"""Exports the kitchen washing machine, written in sand3d (its programs/washing_machine.py), for Unity.

Run with the sand3d env: C:/Users/merla/Tools/sand3d-env/Scripts/python.exe ArtSource/export_washer.py [--render]
Writes ArtSource/Washer.glb (sand3d's own export, metres) and Assets/Art/Models/Washer.fbx,
re-imported from the GLB so each part stays its own object: door, drum, drawer, dial.
Like the apartment's props, colour is in the vertices (layer "Col") and every part uses M_Prop.
"""
import sys
from pathlib import Path

import bpy
import bmesh  # only importable once bpy is

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

glb = ROOT / "ArtSource" / "Washer.glb"
fbx = ROOT / "Assets" / "Art" / "Models" / "Washer.fbx"

s3d.export(washer(**SIZE), str(glb))

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(glb))

prop = bpy.data.materials.new("M_Prop")
count = {}
for ob in bpy.context.scene.objects:
    if ob.type != "MESH":
        continue
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    col = bm.loops.layers.color.new("Col")
    c = COLOR[ob.name]
    for face in bm.faces:
        for loop in face.loops:
            loop[col] = (c[0], c[1], c[2], 1)
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.color_attributes.active_color = ob.data.color_attributes["Col"]
    ob.data.color_attributes.render_color_index = ob.data.color_attributes.active_color_index
    ob.data.materials.clear()
    ob.data.materials.append(prop)
    ob.data.calc_loop_triangles()
    count[ob.name] = len(ob.data.loop_triangles)
print("TRIS", count, "TOTAL", sum(count.values()))

if "--render" in sys.argv:
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.color_type = "VERTEX"
    scene.display.shading.show_object_outline = True
    scene.render.resolution_x, scene.render.resolution_y = 640, 640
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.location = (1.6, -1.1, 1.3)  # Blender Z up after glTF import
    cam.rotation_euler = (1.15, 0, 0.98)
    scene.render.filepath = str(ROOT / "ArtSource" / "Washer_preview.png")
    bpy.ops.render.render(write_still=True)
    scene.collection.objects.unlink(cam)

bpy.ops.export_scene.fbx(
    filepath=str(fbx),
    apply_scale_options="FBX_SCALE_UNITS",
    object_types={"EMPTY", "MESH"},
    mesh_smooth_type="FACE",
    colors_type="LINEAR",
    bake_anim=False,
)
print("WROTE", fbx)
