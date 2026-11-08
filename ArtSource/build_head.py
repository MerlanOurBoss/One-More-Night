"""A dead woman's head for the anomalies: sculpted from cross-sections, its texture painted in the same coordinates.

Run with the sand3d env: C:/Users/merla/Tools/sand3d-env/Scripts/python.exe ArtSource/build_head.py [--render out.png]
Writes Assets/Art/Models/Head.fbx (one mesh, Head, hair included) and Assets/Art/Textures/T_Head.png. At rotation 0 in
Unity the face looks +X; the origin is under the chin at the head's axis. About 25 cm from chin to crown, in metres.

The scene's Photo Ghost uses Assets/Art/Models/Photo_Ghost.asset: Figure_Lens from the apartment and this head combined into one
mesh, because the photos and the safe switch it with a single renderer.enabled. Combine it again after changing either of them.
"""
import math
import sys
from pathlib import Path

import bpy
import bmesh  # only importable once bpy is
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parent.parent
FBX = ROOT / "Assets" / "Art" / "Models" / "Head.fbx"
PNG = ROOT / "Assets" / "Art" / "Textures" / "T_Head.png"
SIZE = 256

# ---------------------------------------------------------------- the shape
# Cross-sections, crown to neck: height, half width, depth to the front, depth to the back. Gaunt, long in the jaw.
SECTIONS = [
    (0.238, 0.012, 0.012, 0.014),
    (0.228, 0.046, 0.05, 0.056),
    (0.21, 0.068, 0.076, 0.08),
    (0.185, 0.076, 0.088, 0.092),
    (0.16, 0.078, 0.09, 0.098),
    (0.142, 0.076, 0.088, 0.098),
    (0.124, 0.072, 0.082, 0.096),
    (0.106, 0.069, 0.08, 0.09),
    (0.088, 0.064, 0.077, 0.078),
    (0.07, 0.058, 0.073, 0.066),
    (0.054, 0.052, 0.07, 0.058),
    (0.038, 0.046, 0.066, 0.052),
    (0.02, 0.038, 0.058, 0.05),
    (0.004, 0.027, 0.044, 0.048),
    (-0.018, 0.034, 0.034, 0.046),
    (-0.06, 0.038, 0.036, 0.046),
    (-0.1, 0.04, 0.038, 0.048),
]
# Around, in degrees from the front: tight over the features of the face, loose behind.
ANGLES = [0, 9, 24, 40, 60, 85, 115, 150, 180]
AROUND = [-a for a in reversed(ANGLES[1:])] + ANGLES   # -180 .. 180, the seam at the back

Z = np.array([s[0] for s in SECTIONS])
HALF = np.array([s[1] for s in SECTIONS])
FRONT = np.array([s[2] for s in SECTIONS])
BACK = np.array([s[3] for s in SECTIONS])


def profile(z):
    order = np.argsort(Z)
    return (np.interp(z, Z[order], HALF[order]), np.interp(z, Z[order], FRONT[order]), np.interp(z, Z[order], BACK[order]))


def bump(x, z, cx, cz, sx, sz):
    return np.exp(-((x - cx) / sx) ** 2 - ((z - cz) / sz) ** 2)


def both(x, z, cx, cz, sx, sz):
    return bump(x, z, cx, cz, sx, sz) + bump(x, z, -cx, cz, sx, sz)


EYE_X, EYE_Z = 0.033, 0.124
MOUTH_Z = 0.04


def relief(x, z):
    """How far the face stands out from its cross-section, in metres. Positive is towards the viewer."""
    d = 0.0
    d += 0.006 * bump(x, z, 0, 0.142, 0.05, 0.01)                 # brow
    d -= 0.017 * both(x, z, EYE_X, EYE_Z, 0.017, 0.012)           # sockets: deep
    d += 0.022 * bump(x, z, 0, 0.09, 0.011, 0.024)                # nose
    d += 0.008 * bump(x, z, 0, 0.078, 0.014, 0.01)                # its tip
    d += 0.005 * both(x, z, 0.05, 0.098, 0.016, 0.012)            # cheekbones
    d -= 0.011 * both(x, z, 0.047, 0.062, 0.016, 0.018)           # hollow cheeks
    d += 0.003 * bump(x, z, 0, 0.056, 0.02, 0.005)                # upper lip
    d -= 0.02 * bump(x, z, 0, MOUTH_Z, 0.017, 0.012)              # the mouth hangs open
    d += 0.005 * bump(x, z, 0, 0.012, 0.017, 0.008)               # chin
    return d


def surface(angle_deg, z):
    """A point on the skin: x across, y towards the face, z up."""
    a = math.radians(angle_deg)
    half, front, back = (float(v) for v in profile(z))
    x = half * math.sin(a)
    y = (front if math.cos(a) > 0 else back) * math.cos(a)
    if math.cos(a) > 0:
        y += float(relief(x, z)) * math.cos(a)
    return Vector((x, y, z))


# ---------------------------------------------------------------- texture space
# Skin takes the upper part of the texture and the front of the head most of its width; hair has the strip below it.
SKIN_V0 = 0.22
Z_LOW, Z_HIGH = -0.11, 0.245


def to_u(angle_deg):
    # -90..90 over the middle 72%, the rest of the way round in the edges.
    a = abs(angle_deg)
    u = a / 90 * 0.36 if a <= 90 else 0.36 + (a - 90) / 90 * 0.14
    return 0.5 + (u if angle_deg >= 0 else -u)


def to_angle(u):
    d = np.abs(u - 0.5)
    a = np.where(d <= 0.36, d / 0.36 * 90, 90 + (d - 0.36) / 0.14 * 90)
    return np.where(u >= 0.5, a, -a)


def to_v(z):
    return SKIN_V0 + (z - Z_LOW) / (Z_HIGH - Z_LOW) * (1 - SKIN_V0)


def smooth_noise(rng, size, cells):
    grid = rng.random((cells + 1, cells + 1))
    xs = np.linspace(0, cells, size)
    i = np.minimum(xs.astype(int), cells - 1)
    f = xs - i
    f = f * f * (3 - 2 * f)
    ix, iy = np.meshgrid(i, i)
    fx, fy = np.meshgrid(f, f)
    return (grid[iy, ix] * (1 - fx) + grid[iy, ix + 1] * fx) * (1 - fy) + (grid[iy + 1, ix] * (1 - fx) + grid[iy + 1, ix + 1] * fx) * fy


def ellipse(x, z, cx, cz, rx, rz):
    """1 inside, 0 outside, soft over a pixel or so."""
    r = np.sqrt(((x - cx) / rx) ** 2 + ((z - cz) / rz) ** 2)
    return np.clip((1.0 - r) / 0.15, 0, 1)


def paint():
    rng = np.random.default_rng(23)
    px = np.arange(SIZE) + 0.5
    uu, vv = np.meshgrid(px / SIZE, px / SIZE)     # row 0 is the bottom, as Blender's pixels are
    angle = to_angle(uu)
    z = Z_LOW + (vv - SKIN_V0) / (1 - SKIN_V0) * (Z_HIGH - Z_LOW)
    half, _, _ = profile(z)
    x = half * np.sin(np.radians(angle))
    front = np.abs(angle) < 90

    blotch = smooth_noise(rng, SIZE, 16) - 0.5
    grain = smooth_noise(rng, SIZE, 90) - 0.5
    skin = np.stack([np.full_like(x, 0.72), np.full_like(x, 0.69), np.full_like(x, 0.6)], axis=-1)
    skin *= (1 + 0.16 * blotch + 0.1 * grain)[..., None]
    # Grey-green in the hollows, yellower on the bones.
    bones = both(x, z, 0.05, 0.098, 0.02, 0.014) + bump(x, z, 0, 0.15, 0.05, 0.02) + bump(x, z, 0, 0.09, 0.012, 0.03)
    skin += np.clip(bones, 0, 1)[..., None] * np.array([0.06, 0.05, 0.02])

    shade = np.ones_like(x)
    shade -= 0.5 * both(x, z, EYE_X, EYE_Z, 0.024, 0.019) * front           # around the eyes
    shade -= 0.35 * both(x, z, 0.047, 0.062, 0.016, 0.02) * front           # hollow cheeks
    shade -= 0.3 * bump(x, z, 0, 0.066, 0.012, 0.006) * front               # under the nose
    shade -= 0.35 * both(x, z, 0.03, 0.04, 0.012, 0.02) * front             # beside the mouth
    shade -= 0.4 * np.clip((0.0 - z) / 0.03, 0, 1)                           # under the jaw and the neck
    shade -= 0.25 * np.clip((np.abs(angle) - 70) / 40, 0, 1)                 # the sides turn away
    skin *= np.clip(shade, 0.12, 1)[..., None]

    # Veins, faint: thin dark threads at the temples and on the neck.
    veins = np.abs(smooth_noise(rng, SIZE, 22) - 0.5) < 0.012
    where = (both(x, z, 0.06, 0.15, 0.025, 0.03) + bump(x, z, 0, -0.05, 0.04, 0.05)) > 0.3
    skin[veins & where] *= np.array([0.68, 0.72, 0.8])

    def over(mask, color):
        m = (mask * front)[..., None]
        skin[...] = skin * (1 - m) + np.array(color) * m

    # Brows, thin.
    for side in (1, -1):
        brow = ellipse(x, z - 0.012 * ((x * side - 0.03) / 0.03) ** 2, side * 0.032, 0.143, 0.024, 0.0032)
        over(brow * 0.75, (0.1, 0.09, 0.08))
    # Eyes: black, a wet line round them, and the small pale point that looks at you.
    for side in (1, -1):
        over(ellipse(x, z, side * EYE_X, EYE_Z, 0.0165, 0.0095), (0.22, 0.05, 0.05))
        over(ellipse(x, z, side * EYE_X, EYE_Z, 0.0135, 0.0072), (0.01, 0.01, 0.012))
        over(ellipse(x, z, side * (EYE_X - 0.003), EYE_Z + 0.0005, 0.0026, 0.0026), (0.85, 0.83, 0.74))
    # Nostrils.
    for side in (1, -1):
        over(ellipse(x, z, side * 0.008, 0.071, 0.0042, 0.0026), (0.03, 0.02, 0.02))
    # Mouth: dark lips round a black hole, a few teeth at the top.
    over(ellipse(x, z, 0, MOUTH_Z, 0.0215, 0.0145), (0.26, 0.1, 0.1))
    over(ellipse(x, z, 0, MOUTH_Z, 0.0165, 0.0105), (0.01, 0.005, 0.005))
    teeth = (np.abs(z - (MOUTH_Z + 0.0078)) < 0.0024) & (np.abs(x) < 0.012) & ((np.floor((x + 0.02) / 0.0052) % 2) == 0)
    over(teeth * 1.0, (0.62, 0.58, 0.44))
    # Something dark has run from the eyes and the mouth.
    runs = np.zeros_like(x)
    for cx, top, length, w in ((EYE_X, EYE_Z - 0.006, 0.05, 0.0018), (-EYE_X + 0.002, EYE_Z - 0.006, 0.036, 0.0015),
                               (0.009, MOUTH_Z - 0.012, 0.04, 0.0022), (-0.006, MOUTH_Z - 0.012, 0.028, 0.0016)):
        wander = 0.0024 * np.sin((z - top) * 180 + cx * 90)
        inside = (np.abs(x - cx - wander) < w) & (z < top) & (z > top - length)
        runs = np.maximum(runs, inside * np.clip((z - (top - length)) / length * 1.6, 0, 1))
    over(runs * 0.9, (0.1, 0.03, 0.03))

    image = np.ones((SIZE, SIZE, 4))
    image[..., :3] = np.clip(skin, 0, 1)
    # Hair: below the skin in the texture, long black strands that show only where the light catches them.
    rows = vv < SKIN_V0
    strands = smooth_noise(rng, SIZE, 64)
    streak = np.interp(uu.ravel(), np.linspace(0, 1, SIZE), strands[SIZE // 2]).reshape(uu.shape)
    tone = 0.006 + 0.012 * streak ** 2
    hair = np.stack([tone * 1.02, tone * 0.98, tone * 0.98], axis=-1)
    image[..., :3][rows] = hair[rows]
    return image


# ---------------------------------------------------------------- hair
HAIR_U = 0.5
HAIR_LOW, HAIR_TOP = 0.02, 0.18


def hair_point(angle_deg, z, swell, rng_jitter=0.0):
    a = math.radians(angle_deg)
    # Read a little lower than it sits, so that it clears the skull all the way to the crown.
    half, front, back = (float(v) for v in profile(max(z - 0.012, -0.02)))
    if z > 0.244:     # closes the very top
        half, front, back, swell = 0.004, 0.004, 0.004, 0.0
    # It falls from the widest part of the head instead of following the jaw in.
    if z < 0.14:
        fall = min(1.0, (0.14 - z) / 0.1)
        half = half + (0.082 - half) * fall
        back = back + (0.096 - back) * fall
        front = front + (0.06 - front) * fall
    x = (half + swell) * math.sin(a)
    y = (front + swell if math.cos(a) > 0 else back + swell) * math.cos(a)
    return Vector((x + rng_jitter, y, z))


def build(bm):
    uv = bm.loops.layers.uv.new("UV")
    col = bm.loops.layers.color.new("Col")

    def face(corners, uvs):
        verts = [bm.verts.new(c) for c in corners]
        uv_of = dict(zip(verts, uvs))
        f = bm.faces.new(verts)
        f.smooth = True
        # These quads stand alone, so nothing else tells them which way is out: away from the head's axis.
        f.normal_update()
        center = f.calc_center_median()
        if f.normal.dot(Vector((center.x, center.y, 0))) < 0:
            f.normal_flip()
        for loop in f.loops:
            loop[uv].uv = uv_of[loop.vert]
            loop[col] = (1, 1, 1, 1)

    # Skin, one shared vertex per grid point so that it shades smooth.
    rows = []
    for s in SECTIONS:
        rows.append([bm.verts.new(surface(a, s[0])) for a in AROUND[:-1]])
    n = len(AROUND) - 1
    for i in range(len(rows) - 1):
        for j in range(n):
            k = (j + 1) % n
            f = bm.faces.new((rows[i][j], rows[i + 1][j], rows[i + 1][k], rows[i][k]))
            f.smooth = True
            a0, a1 = AROUND[j], AROUND[j + 1]
            for loop, (ang, z) in zip(f.loops, ((a0, SECTIONS[i][0]), (a0, SECTIONS[i + 1][0]), (a1, SECTIONS[i + 1][0]), (a1, SECTIONS[i][0]))):
                loop[uv].uv = (to_u(ang), to_v(z))
                loop[col] = (1, 1, 1, 1)

    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))    # the skin is one shell, so this makes it face out

    # Hair: a cap over the skull and sheets that hang past the jaw, open at the face. Each column ends at its own length.
    cap_z = [0.247, 0.238, 0.222, 0.2, 0.18, 0.166]
    hang_z = [0.14, 0.1, 0.06, 0.02, -0.03, -0.09, -0.15, -0.21]
    rng = np.random.default_rng(5)
    length = {a: -0.1 - float(rng.random()) * 0.14 for a in AROUND}
    length[180] = length[-180]
    heights = cap_z + hang_z
    for i in range(len(heights) - 1):
        z0, z1 = heights[i], heights[i + 1]
        for j in range(n):
            a0, a1 = AROUND[j], AROUND[j + 1]
            # Open at the face below the hairline.
            if z0 <= 0.166 and abs((a0 + a1) / 2) < 50:
                continue
            bottom = max(length[a0], length[a1])
            if z0 <= bottom:
                continue
            def p(a, z):
                return hair_point(a, max(z, length[a]), 0.006 if z > 0.17 else 0.009)
            uvs = [(to_u(a0) * 0.98 + 0.01, (z0 + 0.25) / 0.5 * SKIN_V0), (to_u(a0) * 0.98 + 0.01, (z1 + 0.25) / 0.5 * SKIN_V0),
                   (to_u(a1) * 0.98 + 0.01, (z1 + 0.25) / 0.5 * SKIN_V0), (to_u(a1) * 0.98 + 0.01, (z0 + 0.25) / 0.5 * SKIN_V0)]
            face([p(a0, z0), p(a0, z1), p(a1, z1), p(a1, z0)], uvs)
    # Two locks fall across the face from the hairline, lying on the skin: each down its own line, narrowing to a point.
    def on_skin(x, z, lift):
        half, front, _ = (float(v) for v in profile(z))
        y = front * math.sqrt(max(0.04, 1 - (x / half) ** 2)) + float(relief(x, z))
        return Vector((x, y + lift, z))

    for side, line in ((1, ((0.05, 0.172, 0.014), (0.044, 0.14, 0.012), (0.04, 0.1, 0.008), (0.034, 0.05, 0.002))),
                       (-1, ((0.055, 0.172, 0.012), (0.053, 0.14, 0.01), (0.05, 0.11, 0.003)))):
        for (x0, z0, w0), (x1, z1, w1) in zip(line, line[1:]):
            corners = [on_skin(side * x0 - w0, z0, 0.013), on_skin(side * x1 - w1, z1, 0.013),
                       on_skin(side * x1 + w1, z1, 0.013), on_skin(side * x0 + w0, z0, 0.013)]
            face(corners, [(0.3, 0.2), (0.3, 0.02), (0.36, 0.02), (0.36, 0.2)])


# ---------------------------------------------------------------- bake it all
bpy.ops.wm.read_factory_settings(use_empty=True)
pixels = paint()
image = bpy.data.images.new("T_Head", SIZE, SIZE)
image.pixels[:] = pixels.ravel()
image.filepath_raw = str(PNG)
image.file_format = "PNG"
image.save()

mat = bpy.data.materials.new("M_Head")
mat.use_nodes = True
tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
tex.image = image
tex.interpolation = "Closest"
mat.node_tree.links.new(tex.outputs["Color"], mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"])

bm = bmesh.new()
build(bm)
me = bpy.data.meshes.new("Head")
bm.to_mesh(me)
bm.free()
me.materials.append(mat)
me.color_attributes.active_color = me.color_attributes["Col"]
ob = bpy.data.objects.new("Head", me)
bpy.context.scene.collection.objects.link(ob)
me.calc_loop_triangles()
print("TRIS", len(me.loop_triangles))

if "--render" in sys.argv:
    out = sys.argv[sys.argv.index("--render") + 1]
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    shading = scene.display.shading
    shading.color_type = "TEXTURE"
    shading.light = "STUDIO"
    shading.show_specular_highlight = False
    scene.render.resolution_x, scene.render.resolution_y = 360, 480
    scene.world = bpy.data.worlds.new("w")
    scene.world.color = (0.12, 0.12, 0.13)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 0.52
    tiles = []
    for k, (ax, ay) in enumerate(((0, 1), (0.7, 0.8), (1, 0), (0, -1))):
        target = Vector((0, 0, 0.05))
        cam.location = target + Vector((ax, ay, 0.05)).normalized() * 2
        cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
        path = f"{out}_{k}.png"
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        tile = bpy.data.images.load(path)
        tiles.append(np.array(tile.pixels[:]).reshape(480, 360, -1))
    sheet = np.concatenate(tiles, axis=1)
    img = bpy.data.images.new("sheet", sheet.shape[1], sheet.shape[0])
    img.pixels[:] = sheet.ravel()
    img.filepath_raw = out
    img.file_format = "PNG"
    img.save()
    print("WROTE", out)

# Blender (x, y, z) here has the face towards +y. Turn it so that it looks Unity +X, which is Blender -X.
ob.rotation_euler = (0, 0, math.radians(90))
bpy.context.view_layer.update()
bpy.context.view_layer.objects.active = ob
ob.select_set(True)
bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
bpy.ops.export_scene.fbx(filepath=str(FBX), axis_forward="-Z", axis_up="Y", apply_scale_options="FBX_SCALE_ALL",
                         bake_space_transform=True, mesh_smooth_type="FACE", colors_type="LINEAR",
                         object_types={"MESH"}, bake_anim=False, path_mode="STRIP")
print("WROTE", FBX)
