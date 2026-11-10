"""The player, for the photos she ends up in: an ordinary living woman, so that she cannot be taken for the ghost.
Chestnut hair in a ponytail, a warm ochre jumper, dark jeans, light trainers. Low-poly, one texture of flat swatches.

Run with the sand3d env: C:/Users/merla/Tools/sand3d-env/Scripts/python.exe ArtSource/build_player.py [--render out.png]
Writes Assets/Art/Models/Player.fbx (one mesh, Player) and Assets/Art/Textures/T_Player.png.
In Unity she faces +Z with her origin between her feet, 1.66 m tall, in metres.
"""
import math
import sys
from pathlib import Path

import bpy
import bmesh  # only importable once bpy is
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parent.parent
FBX = ROOT / "Assets" / "Art" / "Models" / "Player.fbx"
PNG = ROOT / "Assets" / "Art" / "Textures" / "T_Player.png"
SIZE = 128
CELL = 32

# Swatches: cell column and row of the 4x4 grid, row 0 at the bottom. The face takes the 2x2 block at the bottom right.
SWATCH = {
    "jumper": (0, 3), "cuff": (1, 3), "jeans": (2, 3), "shoe": (3, 3),
    "skin": (0, 2), "hair": (1, 2), "sole": (2, 2), "tie": (3, 2),
}
FACE = (2, 0, 2)   # column, row, cells across


def cell_rect(name):
    c, r = SWATCH[name]
    pad = 1.0 / SIZE
    return c / 4 + pad, r / 4 + pad, 0.25 - 2 * pad, 0.25 - 2 * pad


# ---------------------------------------------------------------- texture
def noise(rng, size, cells):
    grid = rng.random((cells + 1, cells + 1))
    xs = np.linspace(0, cells, size)
    i = np.minimum(xs.astype(int), cells - 1)
    f = xs - i
    f = f * f * (3 - 2 * f)
    ix, iy = np.meshgrid(i, i)
    fx, fy = np.meshgrid(f, f)
    return (grid[iy, ix] * (1 - fx) + grid[iy, ix + 1] * fx) * (1 - fy) + (grid[iy + 1, ix] * (1 - fx) + grid[iy + 1, ix + 1] * fx) * fy


def ellipse(x, y, cx, cy, rx, ry):
    r = np.sqrt(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2)
    return np.clip((1.0 - r) / 0.25, 0, 1)


def paint():
    rng = np.random.default_rng(31)
    img = np.zeros((SIZE, SIZE, 3))
    px = np.arange(CELL) + 0.5
    xx, yy = np.meshgrid(px, px)

    def fill(name, color, pattern):
        c, r = SWATCH[name]
        block = np.array(color)[None, None, :] * pattern[..., None]
        img[r * CELL:(r + 1) * CELL, c * CELL:(c + 1) * CELL] = block

    soft = noise(rng, CELL, 4) - 0.5
    fine = noise(rng, CELL, 16) - 0.5
    # Knit: vertical ribs, a little uneven.
    fill("jumper", (0.56, 0.4, 0.17), 1 + 0.1 * np.sin(xx * 1.6) + 0.12 * soft + 0.06 * fine)
    fill("cuff", (0.42, 0.29, 0.12), 1 + 0.16 * np.sin(xx * 2.4) + 0.08 * fine)
    # Denim: a diagonal weave and worn, lighter patches.
    fill("jeans", (0.17, 0.21, 0.31), 1 + 0.08 * np.sin((xx + yy) * 1.9) + 0.18 * soft + 0.05 * fine)
    fill("shoe", (0.8, 0.79, 0.75), 1 + 0.08 * soft + 0.04 * fine)
    fill("sole", (0.36, 0.34, 0.32), 1 + 0.06 * fine)
    fill("skin", (0.8, 0.62, 0.5), 1 + 0.06 * soft + 0.03 * fine)
    # Hair: strands run along v.
    strands = np.interp(xx.ravel(), np.linspace(0, CELL, CELL), noise(rng, CELL, 12)[CELL // 2]).reshape(xx.shape)
    fill("hair", (0.21, 0.12, 0.07), 0.75 + 0.5 * strands ** 2 + 0.05 * fine)
    fill("tie", (0.08, 0.08, 0.09), np.ones_like(xx))

    # The face, in its own 64 px block: u across from her right to her left, v from chin to above the brows.
    c, r, n = FACE
    size = CELL * n
    fx, fy = np.meshgrid((np.arange(size) + 0.5) / size, (np.arange(size) + 0.5) / size)
    face = np.ones((size, size, 3)) * np.array([0.8, 0.62, 0.5])
    face *= (1 + 0.05 * (noise(rng, size, 6) - 0.5))[..., None]
    # Warmth in the cheeks, shade under the brow and along the nose, as a living face has.
    face += (ellipse(fx, fy, 0.3, 0.42, 0.13, 0.09) + ellipse(fx, fy, 0.7, 0.42, 0.13, 0.09))[..., None] * np.array([0.06, -0.01, -0.01])
    face *= (1 - 0.18 * (ellipse(fx, fy, 0.38, 0.6, 0.11, 0.06) + ellipse(fx, fy, 0.62, 0.6, 0.11, 0.06)))[..., None]
    face *= (1 - 0.12 * ellipse(fx, fy, 0.5, 0.4, 0.035, 0.06))[..., None]

    def over(mask, color):
        face[...] = face * (1 - mask[..., None]) + np.array(color) * mask[..., None]

    for side in (0.36, 0.64):
        over(ellipse(fx, fy, side, 0.69, 0.075, 0.014), (0.22, 0.14, 0.09))      # brows
        over(ellipse(fx, fy, side, 0.6, 0.05, 0.026), (0.92, 0.9, 0.86))         # whites
        over(ellipse(fx, fy, side, 0.6, 0.026, 0.026), (0.24, 0.15, 0.09))       # brown irises
        over(ellipse(fx, fy, side - 0.008, 0.61, 0.008, 0.008), (0.95, 0.95, 0.92))
        over(ellipse(fx, fy, side, 0.625, 0.055, 0.008) * 0.8, (0.18, 0.1, 0.07))  # lashes
    over(ellipse(fx, fy, 0.5, 0.36, 0.045, 0.015) * 0.5, (0.55, 0.38, 0.3))     # under the nose
    over(ellipse(fx, fy, 0.5, 0.25, 0.1, 0.03), (0.68, 0.34, 0.33))            # lips, full
    over(ellipse(fx, fy, 0.5, 0.25, 0.07, 0.005) * 0.8, (0.4, 0.2, 0.18))       # between them
    # Her hair comes down to the brow and frames the temples.
    hairline = (fy > 0.84 - 0.06 * np.cos((fx - 0.5) * 6)) | (fx < 0.08) | (fx > 0.92)
    face[hairline] = np.array([0.21, 0.12, 0.07]) * (0.85 + 0.3 * noise(rng, size, 10)[hairline])[..., None]
    img[r * CELL:r * CELL + size, c * CELL:c * CELL + size] = face

    out = np.ones((SIZE, SIZE, 4))
    out[..., :3] = np.clip(img, 0, 1)
    return out


# ---------------------------------------------------------------- shape
# Blender here: x across (her left is +x), front is -y, z up. A section: height, centre x, centre y, half width, depth in front, depth behind.
def ring_point(sec, angle):
    z, cx, cy, rx, ryf, ryb = sec
    a = math.radians(angle)
    x = cx + rx * math.sin(a)
    y = cy - (ryf if math.cos(a) > 0 else ryb) * math.cos(a)
    return Vector((x, y, z))


class Builder:
    def __init__(self):
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new("UV")
        self.col = self.bm.loops.layers.color.new("Col")

    def quad(self, corners, uvs, inside):
        verts = [self.bm.verts.new(c) for c in corners]
        f = self.bm.faces.new(verts)
        f.smooth = True
        f.normal_update()
        # Every part is built apart, so out is away from the part's own axis.
        if f.normal.dot(f.calc_center_median() - inside(f.calc_center_median())) < 0:
            f.normal_flip()
        uv_of = dict(zip(verts, uvs))
        for loop in f.loops:
            loop[self.uv].uv = uv_of[loop.vert]
            loop[self.col] = (1, 1, 1, 1)

    def loft(self, sections, bands, sides, skip=None, uv_for=None, cap_top=False, cap_bottom=False):
        """A tube through the sections, bottom to top. bands[i] is the swatch between section i and i+1."""
        angles = [-180 + 360 * j / sides for j in range(sides + 1)]
        for i in range(len(sections) - 1):
            s0, s1 = sections[i], sections[i + 1]
            for j in range(sides):
                a0, a1 = angles[j], angles[j + 1]
                if skip and skip(s0, s1, a0, a1):
                    continue
                corners = [ring_point(s0, a0), ring_point(s0, a1), ring_point(s1, a1), ring_point(s1, a0)]
                if uv_for and uv_for(s0, s1, a0, a1):
                    uvs = uv_for(s0, s1, a0, a1)
                else:
                    u0, v0, w, h = cell_rect(bands[i])
                    uvs = [(u0 + w * (a0 + 180) / 360, v0), (u0 + w * (a1 + 180) / 360, v0),
                           (u0 + w * (a1 + 180) / 360, v0 + h), (u0 + w * (a0 + 180) / 360, v0 + h)]
                axis = lambda p, s0=s0, s1=s1: Vector((s0[1] + (s1[1] - s0[1]) * 0.5, s0[2] + (s1[2] - s0[2]) * 0.5, p.z))
                self.quad(corners, uvs, axis)
        for cap, sec, band, down in ((cap_bottom, sections[0], bands[0], True), (cap_top, sections[-1], bands[-1], False)):
            if not cap:
                continue
            centre = Vector((sec[1], sec[2], sec[0]))
            u0, v0, w, h = cell_rect(band)
            mid = (u0 + w / 2, v0 + h / 2)
            for j in range(sides):
                p0, p1 = ring_point(sec, angles[j]), ring_point(sec, angles[j + 1])
                verts = [self.bm.verts.new(c) for c in (centre, p0, p1)]
                f = self.bm.faces.new(verts)
                f.smooth = False
                f.normal_update()
                # The bottom cap looks down, the top one up.
                if (f.normal.z > 0) == down:
                    f.normal_flip()
                for loop in f.loops:
                    loop[self.uv].uv = mid
                    loop[self.col] = (1, 1, 1, 1)

    def box(self, lo, hi, swatch, bottom_swatch, toe_drop=0.0):
        x0, y0, z0 = lo
        x1, y1, z1 = hi
        # y0 is the toe (front, -y): its top comes down a little.
        p = [Vector((x0, y0, z0)), Vector((x1, y0, z0)), Vector((x1, y1, z0)), Vector((x0, y1, z0)),
             Vector((x0, y0, z1 - toe_drop)), Vector((x1, y0, z1 - toe_drop)), Vector((x1, y1, z1)), Vector((x0, y1, z1))]
        centre = (Vector(lo) + Vector(hi)) / 2
        u0, v0, w, h = cell_rect(swatch)
        full = [(u0, v0), (u0 + w, v0), (u0 + w, v0 + h), (u0, v0 + h)]
        su0, sv0, sw, sh = cell_rect(bottom_swatch)
        sole = [(su0, sv0), (su0 + sw, sv0), (su0 + sw, sv0 + sh), (su0, sv0 + sh)]
        for idx, uvs in (((0, 1, 2, 3), sole), ((4, 5, 6, 7), full), ((0, 1, 5, 4), full), ((1, 2, 6, 5), full),
                         ((2, 3, 7, 6), full), ((3, 0, 4, 7), full)):
            self.quad([p[i] for i in idx], uvs, lambda q: centre)


def build():
    b = Builder()

    # Legs, in jeans, from the ankle up into the hips.
    for side in (-1, 1):
        x = side * 0.085
        legs = [(0.08, x, 0.0, 0.04, 0.043, 0.045), (0.3, x, 0.0, 0.047, 0.048, 0.052), (0.47, x * 0.98, -0.005, 0.05, 0.052, 0.05),
                (0.62, x * 0.95, 0.0, 0.068, 0.07, 0.074), (0.76, x * 0.9, 0.0, 0.08, 0.08, 0.085)]
        b.loft(legs, ["jeans"] * 4, 8, cap_bottom=True)
        # Trainers: heel behind the ankle, toe in front.
        b.box((x - 0.045, -0.17, 0.0), (x + 0.045, 0.055, 0.085), "shoe", "sole", toe_drop=0.03)

    # Hips in jeans, then the jumper over them down to a ribbed hem.
    hips = [(0.7, 0.0, 0.0, 0.16, 0.092, 0.1), (0.84, 0.0, 0.0, 0.17, 0.097, 0.106)]
    b.loft(hips, ["jeans"], 12, cap_bottom=True)
    torso = [(0.8, 0.0, 0.0, 0.178, 0.104, 0.11), (0.85, 0.0, 0.0, 0.174, 0.1, 0.106), (0.96, 0.0, 0.0, 0.152, 0.088, 0.09),
             (1.08, 0.0, 0.0, 0.15, 0.096, 0.084), (1.17, 0.0, -0.004, 0.152, 0.116, 0.084), (1.27, 0.0, 0.0, 0.152, 0.092, 0.084),
             (1.32, 0.0, 0.005, 0.15, 0.072, 0.074), (1.365, 0.0, 0.005, 0.105, 0.06, 0.062), (1.39, 0.0, 0.005, 0.058, 0.044, 0.046)]
    b.loft(torso, ["cuff", "jumper", "jumper", "jumper", "jumper", "jumper", "jumper", "cuff"], 12, cap_bottom=True)

    # Arms hang a little off the body, jumper to a ribbed cuff, then hands.
    for side in (-1, 1):
        # Narrow shoulders: the sleeve starts inside the jumper's shoulder line.
        # Top to bottom here: from inside the shoulder's slope, out and down.
        arm = [(1.36, side * 0.118, 0.005, 0.03, 0.036, 0.036), (1.3, side * 0.162, 0.005, 0.043, 0.044, 0.044), (1.15, side * 0.178, 0.01, 0.04, 0.04, 0.04),
               (0.98, side * 0.19, -0.005, 0.035, 0.035, 0.035), (0.935, side * 0.192, -0.007, 0.033, 0.033, 0.033)]
        arm.reverse()
        b.loft(arm, ["cuff", "jumper", "jumper", "jumper"], 8)
        hand = [(0.75, side * 0.198, -0.012, 0.015, 0.02, 0.018), (0.81, side * 0.198, -0.012, 0.027, 0.027, 0.024),
                (0.94, side * 0.193, -0.008, 0.027, 0.026, 0.026)]
        b.loft(hand, ["skin", "skin"], 6, cap_bottom=True)

    # Neck and head. The front of the head maps onto the face block.
    neck = [(1.36, 0.0, 0.008, 0.034, 0.034, 0.036), (1.46, 0.0, 0.006, 0.033, 0.033, 0.035)]
    b.loft(neck, ["skin"], 8)
    # Rounder and shorter than the ghost's long gaunt head, with a soft chin.
    head = [(1.44, 0.0, -0.004, 0.024, 0.028, 0.025), (1.452, 0.0, -0.006, 0.043, 0.056, 0.045), (1.482, 0.0, -0.004, 0.06, 0.076, 0.07),
            (1.518, 0.0, 0.0, 0.071, 0.085, 0.084), (1.555, 0.0, 0.0, 0.074, 0.088, 0.09), (1.59, 0.0, 0.0, 0.073, 0.085, 0.091),
            (1.616, 0.0, 0.0, 0.065, 0.074, 0.085), (1.636, 0.0, 0.0, 0.047, 0.052, 0.062), (1.647, 0.0, 0.0, 0.017, 0.017, 0.022)]
    z_chin, z_brow = 1.445, 1.625
    fc, fr, fn = FACE
    fu0, fv0, fw = fc / 4 + 1 / SIZE, fr / 4 + 1 / SIZE, fn / 4 - 2 / SIZE

    def face_uv(s0, s1, a0, a1):
        if max(abs(a0), abs(a1)) > 75:
            return None
        u = lambda a: fu0 + fw * (0.5 - a / 150)    # her right (-x, negative angle) on the left of the image
        v = lambda z: fv0 + fw * np.clip((z - z_chin) / (z_brow - z_chin), 0, 1)
        return [(u(a0), v(s0[0])), (u(a1), v(s0[0])), (u(a1), v(s1[0])), (u(a0), v(s1[0]))]

    b.loft(head, ["skin"] * (len(head) - 1), 12, uv_for=face_uv, cap_top=True)

    # Hair: a shell over the skull, open over the face below the hairline, longer at the back.
    grow = lambda s, more: (s[0], s[1], s[2], s[3] + more, s[4] + more, s[5] + more)
    # From the jaw up: at the sides it falls to the jawline, framing the face.
    shell = [grow(s, 0.011) for s in head[1:]]
    b.loft(shell, ["hair"] * (len(shell) - 1), 12, skip=lambda s0, s1, a0, a1: s1[0] <= 1.616 and abs((a0 + a1) / 2) < 70, cap_top=True)
    # The ponytail: tied at the back of the head, hanging to between the shoulder blades.
    tail = [(1.575, 0.0, 0.1, 0.022, 0.022, 0.022), (1.55, 0.0, 0.114, 0.027, 0.027, 0.027), (1.49, 0.0, 0.114, 0.031, 0.029, 0.031),
            (1.41, 0.0, 0.106, 0.027, 0.025, 0.027), (1.33, 0.0, 0.1, 0.017, 0.017, 0.017), (1.29, 0.0, 0.098, 0.004, 0.004, 0.004)]
    b.loft(tail, ["tie", "hair", "hair", "hair", "hair"], 6, cap_top=True)
    return b.bm


# ---------------------------------------------------------------- bake it all
bpy.ops.wm.read_factory_settings(use_empty=True)
pixels = paint()
image = bpy.data.images.new("T_Player", SIZE, SIZE)
image.pixels[:] = pixels.ravel()
image.filepath_raw = str(PNG)
image.file_format = "PNG"
image.save()

mat = bpy.data.materials.new("M_Player")
mat.use_nodes = True
tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
tex.image = image
tex.interpolation = "Closest"
mat.node_tree.links.new(tex.outputs["Color"], mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"])

bm = build()
me = bpy.data.meshes.new("Player")
bm.to_mesh(me)
bm.free()
me.materials.append(mat)
me.color_attributes.active_color = me.color_attributes["Col"]
ob = bpy.data.objects.new("Player", me)
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
    scene.render.resolution_x, scene.render.resolution_y = 300, 600
    scene.world = bpy.data.worlds.new("w")
    scene.world.color = (0.12, 0.12, 0.13)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 1.85
    tiles = []
    for k, (ax, ay) in enumerate(((0, -1), (-0.7, -0.7), (-1, 0), (0, 1))):
        target = Vector((0, 0, 0.85))
        cam.location = target + Vector((ax, ay, 0.12)).normalized() * 4
        cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
        path = f"{out}_{k}.png"
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        tile = bpy.data.images.load(path)
        tiles.append(np.array(tile.pixels[:]).reshape(600, 300, -1))
    # And her face up close.
    cam.data.ortho_scale = 0.36
    target = Vector((0, 0, 1.55))
    cam.location = target + Vector((0, -4, 0))
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = f"{out}_face.png"
    bpy.ops.render.render(write_still=True)
    sheet = np.concatenate(tiles, axis=1)
    img = bpy.data.images.new("sheet", sheet.shape[1], sheet.shape[0])
    img.pixels[:] = sheet.ravel()
    img.filepath_raw = out
    img.file_format = "PNG"
    img.save()
    print("WROTE", out)

# Built facing Blender -y, which the exporter turns into Unity +z.
bpy.context.view_layer.objects.active = ob
ob.select_set(True)
bpy.ops.export_scene.fbx(filepath=str(FBX), axis_forward="-Z", axis_up="Y", apply_scale_options="FBX_SCALE_ALL",
                         bake_space_transform=True, mesh_smooth_type="FACE", colors_type="LINEAR",
                         object_types={"MESH"}, bake_anim=False, path_mode="STRIP")
print("WROTE", FBX)
