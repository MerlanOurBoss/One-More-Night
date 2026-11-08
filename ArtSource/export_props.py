"""Exports the air conditioner, microwave, oven and safe for Unity, from ArtSource/props_source (see CREDITS.md).

Run with the sand3d env: C:/Users/merla/Tools/sand3d-env/Scripts/python.exe ArtSource/export_props.py
Writes Assets/Art/Models/{Aircon,Microwave,Oven,Safe}.fbx. Hidden small parts are dropped and round ones become
low n-gons, so that items stay in budget. Colour is in the vertices (layer "Col"), everything uses M_Prop.

Except for the safe, at rotation 0 in Unity the front looks +X and a moving part's origin is on its hinge.
The safe is baked in world space, like the rest of the apartment, because its anomaly moves it around a point:
meshes Safe, Safe_Door_Closed and Safe_Door_Open, for the object Apartment/Safe that SafeLock and the anomaly use.
"""
import math
from pathlib import Path

import bpy
import bmesh  # only importable once bpy is
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "ArtSource" / "props_source"
MODELS = ROOT / "Assets" / "Art" / "Models"
BOX = ((0, 4, 6, 2), (1, 3, 7, 5), (2, 6, 7, 3), (0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4))  # -x +x +y -z +z -y

FRONT_Y = Matrix.Rotation(math.radians(90), 4, "Z")   # the source's +Y looks Blender -X, which is Unity +X


def box(lo, hi):
    return [(hi[0] if i & 1 else lo[0], hi[1] if i & 2 else lo[1], hi[2] if i & 4 else lo[2]) for i in range(8)], BOX


def cylinder(lo, hi, axis, sides):
    """An n-gon prism filling a bounding box along `axis` (0, 1 or 2)."""
    u, v = (axis + 1) % 3, (axis + 2) % 3
    positions = []
    for end in (lo[axis], hi[axis]):
        for i in range(sides):
            t = 2 * math.pi * i / sides
            p = [0, 0, 0]
            p[axis] = end
            p[u] = (lo[u] + hi[u]) / 2 + (hi[u] - lo[u]) / 2 * math.cos(t)
            p[v] = (lo[v] + hi[v]) / 2 + (hi[v] - lo[v]) / 2 * math.sin(t)
            positions.append(p)
    faces = [tuple(range(sides - 1, -1, -1)), tuple(range(sides, 2 * sides))]
    faces += [(i, (i + 1) % sides, (i + 1) % sides + sides, i + sides) for i in range(sides)]
    return positions, faces


def collect(source, groups, drop, round_parts, palette, by_name):
    """Reads the USDA: {group: [(positions, faces, colours)]} in the source's coordinates."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.usd_import(filepath=str(SOURCES / source))
    bpy.context.view_layer.update()
    parts = {}
    for ob in [o for o in bpy.data.objects if o.type == "MESH"]:
        if ob.name in drop:
            continue
        me = ob.data
        if ob.name in by_name:
            colors = [by_name[ob.name]] * len(me.polygons)
        else:
            colors = [palette[me.materials[p.material_index].name] for p in me.polygons]
        if ob.name in round_parts:
            axis, sides = round_parts[ob.name]
            pts = [ob.matrix_world @ v.co for v in me.vertices]
            lo = [min(p[a] for p in pts) for a in range(3)]
            hi = [max(p[a] for p in pts) for a in range(3)]
            positions, faces = cylinder(lo, hi, axis, sides)
            colors = [colors[0]] * len(faces)
        else:
            positions = [tuple(ob.matrix_world @ v.co) for v in me.vertices]
            faces = [tuple(p.vertices) for p in me.polygons]
        names = [g for g, members in groups.items() if ob.name in members] or ["Body"]
        for g in names:
            parts.setdefault(g, []).append((positions, faces, colors))
    return parts


def write(name, parts, place, location):
    """`place(group, point)` maps a source point to Blender; `location(group)` is the object's origin there."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    prop = bpy.data.materials.new("M_Prop")
    count = {}
    for group, pieces in parts.items():
        bm = bmesh.new()
        col = bm.loops.layers.color.new("Col")
        for positions, faces, colors in pieces:
            verts = [bm.verts.new(place(group, p)) for p in positions]
            for indices, c in zip(faces, colors):
                face = bm.faces.new([verts[i] for i in indices])
                face.smooth = False
                for loop in face.loops:
                    loop[col] = (c[0], c[1], c[2], 1)
        me = bpy.data.meshes.new(group)
        bm.to_mesh(me)
        bm.free()
        me.materials.append(prop)
        me.color_attributes.active_color = me.color_attributes["Col"]
        ob = bpy.data.objects.new(group, me)
        ob.location = location(group)
        bpy.context.scene.collection.objects.link(ob)
        me.calc_loop_triangles()
        count[group] = len(me.loop_triangles)
    print("TRIS", name, count, "TOTAL", sum(count.values()))
    bpy.ops.export_scene.fbx(filepath=str(MODELS / f"{name}.fbx"), axis_forward="-Z", axis_up="Y",
                             apply_scale_options="FBX_SCALE_ALL", bake_space_transform=True,
                             mesh_smooth_type="FACE", colors_type="LINEAR", object_types={"MESH"}, bake_anim=False)


def turned(name, parts, pivots):
    """Front +Y to Unity +X, each group's origin on its pivot."""
    def pivot(group):
        return Vector(pivots.get(group, (0, 0, 0)))
    write(name, parts, lambda g, p: FRONT_Y @ (Vector(p) - pivot(g)), lambda g: FRONT_Y @ pivot(g))


def add(parts, group, items):
    for lo, hi, c in items:
        positions, faces = box(lo, hi)
        parts.setdefault(group, []).append((positions, faces, [c] * len(faces)))


# ---------------------------------------------------------------- air conditioner: the flap moves
WHITE = (0.84, 0.84, 0.82)
parts = collect(
    "aircon.usda", {"Flap": {"hinge_rod"}},
    {"vane_0_shaft", "vane_1_shaft", "vane_0_lower_mount", "vane_0_upper_mount", "vane_1_lower_mount", "vane_1_upper_mount"},
    {}, {"plastic__f2f2ed": WHITE, "plastic__ebebe6": (0.78, 0.78, 0.76), "plastic__a1a8b0": (0.4, 0.4, 0.42)}, {})
add(parts, "Body", [((0.36, 0.228, 0.19), (0.385, 0.25, 0.205), (0.2, 0.7, 0.3))])     # the small green light
turned("Aircon", parts, {"Flap": (0, 0.181, 0.063)})

# ---------------------------------------------------------------- microwave: an old dorm one, the door moves
RAIL, BODY = (0.55, 0.55, 0.54), (0.74, 0.74, 0.7)
parts = collect(
    "microwave.usda", {"Door": {"bottom_rail", "door_glass", "door_handle", "hinge_stile", "latch_stile", "top_rail"}},
    {"knob_shaft"}, {"knob_body": (1, 12)},
    {"steel__2e3036_metallic_0_5_roughness_0_65": BODY,
     "painted_metal__1c1f22_metallic_0_5_roughness_0_65": (0.2, 0.2, 0.21),
     "aluminium__80878f_roughness_0_45": RAIL,
     "aluminium__80878f_metallic_0_5_roughness_0_65": (0.6, 0.6, 0.58),
     "aluminium__80878f": RAIL,
     "aluminium__b8bdc2_metallic_0_5_roughness_0_65": (0.35, 0.35, 0.36),
     "glass__2e383f_roughness_0_45": (0.1, 0.11, 0.12),
     "plastic__d4d6db_roughness_0_45": (0.7, 0.7, 0.68),
     "plastic__d4d6db": (0.85, 0.85, 0.82),
     "painted_metal__f02e24": (0.72, 0.16, 0.14)}, {})
turned("Microwave", parts, {"Door": (-0.227, 0.18, 0.018)})

# ---------------------------------------------------------------- oven: the door drops, with the old towel on its handle
STEEL = (0.58, 0.6, 0.62)
parts = collect(
    "oven.usda", {"Door": {"door_panel", "glass_panel", "handle_bar", "handle_left_post", "handle_right_post"}},
    {"glass_reflection", "left_hinge_knuckle", "right_hinge_knuckle", "left_hinge_pin", "right_hinge_pin"},
    {"handle_bar": (0, 8)},
    {"steel__bdc2c7": STEEL, "ceramic__1a1a1c": (0.05, 0.05, 0.06), "glass__14191f_opacity_0_78": (0.06, 0.06, 0.07),
     "glass__38424d_opacity_0_38": (0.08, 0.1, 0.12), "brushed_steel__d1d6db": (0.7, 0.72, 0.74)}, {})
add(parts, "Door", [((-0.11, 0.349, 0.25), (0.11, 0.361, 0.54), (0.7, 0.34, 0.26))])    # towel
add(parts, "Body", [((x - 0.02, 0.27, 0.59), (x + 0.02, 0.295, 0.635), (0.2, 0.2, 0.22)) for x in (-0.24, -0.17, 0.17, 0.24)])  # hob knobs
turned("Oven", parts, {"Door": (0, 0.2725, 0.057)})

# ---------------------------------------------------------------- safe: baked where it stands, in front of the bedroom wardrobe
SAFE_X, SAFE_BACK_Z, HINGE, OPEN = 1.0, -2.44, (0, -0.309), math.radians(-100)
DOOR = {"door_shell", "dial_bezel", "dial_grip", "dial_hub", "dial_index", "hinge_knuckle_1", "hinge_knuckle_2", "hinge_knuckle_3"}
parts = collect(
    "safe.usda", {"Safe_Door_Closed": DOOR, "Safe_Door_Open": DOOR},
    {"drawer_back", "drawer_bottom", "drawer_front", "drawer_left_side", "drawer_pull", "drawer_right_side", "left_runner",
     "right_runner", "left_jamb_stop", "right_jamb_stop", "threshold_stop", "top_stop"},
    {"dial_bezel": (0, 12), "dial_hub": (0, 8), "hinge_knuckle_1": (2, 6), "hinge_knuckle_2": (2, 6), "hinge_knuckle_3": (2, 6)},
    {"painted_metal__2e3036": (0.2, 0.21, 0.2), "painted_metal__4d4f57": (0.27, 0.28, 0.27),
     "painted_metal__42444d": (0.15, 0.15, 0.15), "painted_metal__ccced1": (0.6, 0.6, 0.58),
     "steel__ccced1": (0.6, 0.6, 0.58), "plastic__1a1c1f": (0.09, 0.09, 0.09)}, {})
parts["Safe"] = parts.pop("Body")


def safe_place(group, p):
    x, y, z = p
    if group == "Safe_Door_Open":      # about the hinge, out towards the room
        dx, dy = x - HINGE[0], y - HINGE[1]
        x = HINGE[0] + dx * math.cos(OPEN) - dy * math.sin(OPEN)
        y = HINGE[1] + dx * math.sin(OPEN) + dy * math.cos(OPEN)
    # The source's +X is the front, which looks Unity +Z; +Y is Unity -X; centre at its height. Unity to Blender: (-x, -z, y).
    ux, uy, uz = SAFE_X - y, z + 0.24, SAFE_BACK_Z + x + 0.251
    return Vector((-ux, -uz, uy))


write("Safe", parts, safe_place, lambda g: Vector((0, 0, 0)))
print("DONE")
