# Builds the Kazakh apartment from the user's floor plan and exports it for Unity.
# blender --background --factory-startup --python build_apartment.py
#
# All positions are in Unity's space, X east and Z north on the plan, in metres, floor at Y 0.
# Scale from the plan picture: 190 px = 1 m. Meshes are baked in world space, objects stay at the origin,
# like the old room, because anomalies rotate around a point they are given.
import math
import bmesh
import bpy
from mathutils import Vector

ART = r"F:\Work KZ\One More Night"
OLD_BLEND = ART + r"\ArtSource\Room_Prototype.blend"
BLEND = ART + r"\ArtSource\Apartment.blend"
FBX = ART + r"\Assets\Art\Models\Apartment.fbx"

H = 2.55          # ceiling
DOOR_TOP = 2.05
WINDOW_BOTTOM, WINDOW_TOP = 0.85, 2.25
TEXEL = 1.8       # 256 px = 1.8 m


def to_blender(p):
    return Vector((-p[0], -p[2], p[1]))


bpy.ops.wm.read_factory_settings(use_empty=True)
collection = bpy.data.collections.new("Apartment")
bpy.context.scene.collection.children.link(collection)
bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children["Apartment"]


def material(name):
    m = bpy.data.materials.get(name)
    return m if m else bpy.data.materials.new(name)


class Part:
    """One exported object with one material, added to as quads in Unity space."""
    parts = {}

    def __init__(self, name, mat):
        self.name, self.mat = name, mat
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new("UVMap")
        self.col = self.bm.loops.layers.color.new("Col")
        Part.parts[name] = self

    def quad(self, pts, normal, uvs=None, color=(1, 1, 1)):
        verts = [self.bm.verts.new(to_blender(p)) for p in pts]
        face = self.bm.faces.new(verts)
        face.normal_update()
        if face.normal.dot(to_blender(normal)) < 0:
            face.normal_flip()
        lookup = {v: i for i, v in enumerate(verts)}
        for loop in face.loops:
            i = lookup[loop.vert]
            loop[self.uv].uv = uvs[i] if uvs else (0, 0)
            loop[self.col] = (color[0], color[1], color[2], 1)

    def rect(self, a, b, normal, color=(1, 1, 1), uv=None):
        """Axis-aligned rectangle between opposite corners, with world-scale UVs."""
        a, b = Vector(a), Vector(b)
        flat = [i for i in range(3) if abs(a[i] - b[i]) < 1e-6][0]
        u_axis, v_axis = [i for i in range(3) if i != flat]
        if flat == 0 or flat == 2:      # wall: V goes up
            u_axis, v_axis = (2 if flat == 0 else 0), 1
        else:
            u_axis, v_axis = 0, 2
        def corner(ca, cb):
            p = Vector(a)
            p[u_axis] = ca
            p[v_axis] = cb
            return tuple(p)
        ua, ub, va, vb = a[u_axis], b[u_axis], a[v_axis], b[v_axis]
        pts = [corner(ua, va), corner(ub, va), corner(ub, vb), corner(ua, vb)]
        if uv == "fill":
            uvs = [(0, 0), (1, 0), (1, 1), (0, 1)]
        else:
            s = uv if uv else TEXEL
            uvs = [(p[u_axis] / s, p[v_axis] / s) for p in pts]
        self.quad(pts, normal, uvs, color)

    def box(self, lo, hi, color=(1, 1, 1), skip=(), uv=None):
        x0, y0, z0 = lo
        x1, y1, z1 = hi
        if "x-" not in skip: self.rect((x0, y0, z0), (x0, y1, z1), (-1, 0, 0), color, uv)
        if "x+" not in skip: self.rect((x1, y0, z0), (x1, y1, z1), (1, 0, 0), color, uv)
        if "y-" not in skip: self.rect((x0, y0, z0), (x1, y0, z1), (0, -1, 0), color, uv)
        if "y+" not in skip: self.rect((x0, y1, z0), (x1, y1, z1), (0, 1, 0), color, uv)
        if "z-" not in skip: self.rect((x0, y0, z0), (x1, y1, z0), (0, 0, -1), color, uv)
        if "z+" not in skip: self.rect((x0, y0, z1), (x1, y1, z1), (0, 0, 1), color, uv)

    def slab(self, hinge, angle_deg, width, thickness, y0, y1, color=(1, 1, 1)):
        """A door panel standing on its hinge, turned on the plan. Angle 0 points east, 90 north."""
        a = math.radians(angle_deg)
        d = Vector((math.cos(a), 0, math.sin(a)))
        n = Vector((-math.sin(a), 0, math.cos(a))) * (thickness / 2)
        o = Vector((hinge[0], 0, hinge[1]))
        def at(along, side, y):
            p = o + d * along + side
            return (p.x, y, p.z)
        for side, normal in ((n, n), (-n, -n)):
            pts = [at(0, side, y0), at(width, side, y0), at(width, side, y1), at(0, side, y1)]
            self.quad(pts, tuple(normal), [(0, 0), (1, 0), (1, 1), (0, 1)], color)
        for along, normal in ((0, -d), (width, d)):
            pts = [at(along, n, y0), at(along, -n, y0), at(along, -n, y1), at(along, n, y1)]
            self.quad(pts, tuple(normal), [(0, 0), (0.05, 0), (0.05, 1), (0, 1)], color)
        top = [at(0, n, y1), at(width, n, y1), at(width, -n, y1), at(0, -n, y1)]
        self.quad(top, (0, 1, 0), [(0, 0), (1, 0), (1, 0.05), (0, 0.05)], color)

    def surface(self, rows, inside):
        """rows[j][i] = (position, uv, color). Faces are turned away from the point inside."""
        grid = [[self.bm.verts.new(to_blender(cell[0])) for cell in row] for row in rows]
        core = to_blender(inside)
        for j in range(len(rows) - 1):
            for i in range(len(rows[j]) - 1):
                self.smooth_face([(j, i), (j, i + 1), (j + 1, i + 1), (j + 1, i)], grid, rows, core)
        return grid

    def smooth_face(self, keys, grid, rows, core):
        lookup = {grid[j][i]: rows[j][i] for j, i in keys}
        face = self.bm.faces.new([grid[j][i] for j, i in keys])
        face.smooth = True
        face.normal_update()
        if face.normal.dot(face.calc_center_median() - core) < 0:
            face.normal_flip()
        for loop in face.loops:
            cell = lookup[loop.vert]
            loop[self.uv].uv = cell[1]
            color = cell[2]
            loop[self.col] = (color[0], color[1], color[2], 1)

    def puff(self, center, length, width, thick, tilt_deg, color, n=3):
        """A pillow: puffed on both sides, the two halves joined at the rim, leaning towards +X."""
        tilt = math.radians(tilt_deg)
        cx, cy, cz = center
        keys = list(range(-n, n + 1))

        def place(a, b, side):
            u, v = a / n, b / n
            pull = 1 - 0.1 * (abs(u) * abs(v)) ** 2      # rounded corners
            lx, lz = u * pull * length / 2, v * pull * width / 2
            body = max(0.0, 1 - abs(u) ** 2.6) ** 0.5 * max(0.0, 1 - abs(v) ** 2.6) ** 0.5
            ly = side * thick * body
            return (cx + lx * math.cos(tilt) - ly * math.sin(tilt), cy + ly * math.cos(tilt) + lx * math.sin(tilt), cz + lz)

        def shade(a, b):
            rim = max(abs(a), abs(b)) == n
            m = 0.62 if rim else 1.0
            return (color[0] * m, color[1] * m, color[2] * m)

        verts = {}
        for side in (1, -1):
            for a in keys:
                for b in keys:
                    on_rim = max(abs(a), abs(b)) == n
                    key = (a, b, 0 if on_rim else side)
                    if key not in verts:
                        verts[key] = self.bm.verts.new(to_blender(place(a, b, side)))
        core = to_blender(center)
        for side in (1, -1):
            for a in keys[:-1]:
                for b in keys[:-1]:
                    corners = [(a, b), (a + 1, b), (a + 1, b + 1), (a, b + 1)]
                    pick = [verts[(x, y, 0 if max(abs(x), abs(y)) == n else side)] for x, y in corners]
                    face = self.bm.faces.new(pick)
                    face.smooth = True
                    face.normal_update()
                    if face.normal.dot(face.calc_center_median() - core) < 0:
                        face.normal_flip()
                    for loop in face.loops:
                        x, y = corners[pick.index(loop.vert)]
                        loop[self.uv].uv = ((cx + x * length / (2 * n)) / 0.9, (cz + y * width / (2 * n)) / 0.9)
                        c = shade(x, y)
                        loop[self.col] = (c[0], c[1], c[2], 1)


def cuts(a, b, step, extra=()):
    values = {a, b}
    v = a + step
    while v < b:
        values.add(round(v, 4))
        v += step
    for e in extra:
        if a < e < b:
            values.add(e)
    return sorted(values)


TRIM = (0.86, 0.85, 0.82)


def wall(part, axis, c, a, b, facing, holes=(), depth=0.13, skirting=True, y1=H):
    """Inward-facing wall at x=c or z=c, spanning a..b, cut into small cells so vertex light can vary.
    A hole is (along0, along1, y0, y1); its reveal goes back through the wall by depth."""
    def p(along, y, offset=0.0):
        return (c + offset, y, along) if axis == "x" else (along, y, c + offset)

    normal = (facing, 0, 0) if axis == "x" else (0, 0, facing)
    along_cuts = cuts(a, b, 0.4, [h[0] for h in holes] + [h[1] for h in holes])
    y_cuts = cuts(0.0, y1, 0.45, [h[2] for h in holes] + [h[3] for h in holes])
    for i in range(len(along_cuts) - 1):
        for j in range(len(y_cuts) - 1):
            a0, a1, y0, y2 = along_cuts[i], along_cuts[i + 1], y_cuts[j], y_cuts[j + 1]
            mid_a, mid_y = (a0 + a1) / 2, (y0 + y2) / 2
            if any(h[0] < mid_a < h[1] and h[2] < mid_y < h[3] for h in holes):
                continue
            pts = [p(a0, y0), p(a1, y0), p(a1, y2), p(a0, y2)]
            part.quad(pts, normal, [(a0 / TEXEL, y0 / TEXEL), (a1 / TEXEL, y0 / TEXEL), (a1 / TEXEL, y2 / TEXEL), (a0 / TEXEL, y2 / TEXEL)])

    trim = Part.parts[TRIM_PART]
    back = -facing * depth
    for h0, h1, hy0, hy1 in holes:
        along_normal = (1, 0, 0) if axis == "z" else (0, 0, 1)
        neg = tuple(-v for v in along_normal)
        if depth > 0.0:
            reveal = Part.parts["Reveals"]
            reveal.quad([p(h0, hy0), p(h0, hy1), p(h0, hy1, back), p(h0, hy0, back)], along_normal, color=TRIM)
            reveal.quad([p(h1, hy0), p(h1, hy1), p(h1, hy1, back), p(h1, hy0, back)], neg, color=TRIM)
            reveal.quad([p(h0, hy1), p(h1, hy1), p(h1, hy1, back), p(h0, hy1, back)], (0, -1, 0), color=TRIM)
            if hy0 > 0.01:
                reveal.quad([p(h0, hy0), p(h1, hy0), p(h1, hy0, back), p(h0, hy0, back)], (0, 1, 0), color=TRIM)
        # casing on the room side
        t = 0.05
        o = facing * 0.012
        trim.quad([p(h0 - t, hy0, o), p(h0, hy0, o), p(h0, hy1 + t, o), p(h0 - t, hy1 + t, o)], normal, color=TRIM)
        trim.quad([p(h1, hy0, o), p(h1 + t, hy0, o), p(h1 + t, hy1 + t, o), p(h1, hy1 + t, o)], normal, color=TRIM)
        trim.quad([p(h0, hy1, o), p(h1, hy1, o), p(h1, hy1 + t, o), p(h0, hy1 + t, o)], normal, color=TRIM)

    if skirting:
        spans, start = [], a
        for h in sorted(h for h in holes if h[2] < 0.05):
            spans.append((start, h[0] - 0.05))
            start = h[1] + 0.05
        spans.append((start, b))
        o = facing * 0.015
        for s0, s1 in spans:
            if s1 > s0:
                part_s = Part.parts[TRIM_PART]
                part_s.quad([p(s0, 0, o), p(s1, 0, o), p(s1, 0.07, o), p(s0, 0.07, o)], normal, color=(0.42, 0.36, 0.30))
    # cornice
    o = facing * 0.03
    Part.parts[TRIM_PART].quad([p(a, y1 - 0.06, o), p(b, y1 - 0.06, o), p(b, y1, o), p(a, y1, o)], normal, color=TRIM)


def floor_rect(part, x0, x1, z0, z1, y=0.0, up=True, step=0.5, uv=TEXEL):
    normal = (0, 1 if up else -1, 0)
    xs, zs = cuts(x0, x1, step), cuts(z0, z1, step)
    for i in range(len(xs) - 1):
        for j in range(len(zs) - 1):
            a, b, c, d = xs[i], xs[i + 1], zs[j], zs[j + 1]
            part.quad([(a, y, c), (b, y, c), (b, y, d), (a, y, d)], normal, [(a / uv, c / uv), (b / uv, c / uv), (b / uv, d / uv), (a / uv, d / uv)])


def curtain(part, x0, x1, z, y0, y1, folds=4, depth=0.05, facing=-1):
    """Shallow zigzag cloth along X."""
    n = folds * 2
    for i in range(n):
        a, b = x0 + (x1 - x0) * i / n, x0 + (x1 - x0) * (i + 1) / n
        za = z + (depth if i % 2 else 0)
        zb = z + (0 if i % 2 else depth)
        u0, u1 = i / n * 2, (i + 1) / n * 2
        part.quad([(a, y0, za), (b, y0, zb), (b, y1, zb), (a, y1, za)], (0, 0, facing), [(u0, 0), (u1, 0), (u1, 2.2), (u0, 2.2)])


for room_name in ("Bedroom", "Kitchen", "Hall", "Bath"):
    Part("Trim_" + room_name, material("M_Prop"))
TRIM_PART = "Trim_Bedroom"
Part("Reveals", material("M_Reveal"))   # the inside of openings: belongs to two rooms, so both rooms light it

# ---------------------------------------------------------------- rooms
# Bedroom
bed_w = Part("Walls_Bedroom", material("M_WallLeaf"))
BEDROOM_DOOR = (-2.0, -1.168, 0, DOOR_TOP)
wall(bed_w, "x", 0.063, -2.13, 3.568, 1, [BEDROOM_DOOR], 0.0)
wall(bed_w, "x", 0.547, -3.026, -2.13, 1)
wall(bed_w, "z", -2.13, 0.063, 0.547, 1)
wall(bed_w, "z", -3.026, 0.547, 3.258, 1, skirting=False)
wall(bed_w, "x", 3.258, -3.026, 3.568, -1)
WINDOW_HOLE = (0.837, 1.679, WINDOW_BOTTOM, WINDOW_TOP)
BALCONY_DOOR = (1.679, 2.547, 0, WINDOW_TOP)
wall(bed_w, "z", 3.568, 0.063, 3.258, -1, [WINDOW_HOLE, BALCONY_DOOR], 0.316)
f = Part("Floor_Bedroom", material("M_Laminate"))
floor_rect(f, 0.063, 3.258, -2.13, 3.568)
floor_rect(f, 0.547, 3.258, -3.026, -2.13)
c = Part("Ceiling_Bedroom", material("M_CeilingGrey"))
floor_rect(c, 0.063, 3.258, -2.13, 3.568, H, up=False)
floor_rect(c, 0.547, 3.258, -3.026, -2.13, H, up=False)

# Kitchen
TRIM_PART = "Trim_Kitchen"
kit_w = Part("Walls_Kitchen", material("M_WallGrey"))
KITCHEN_DOOR = (-1.084, -0.284, 0, DOOR_TOP)
KITCHEN_WINDOW = (-2.426, -0.689, WINDOW_BOTTOM, WINDOW_TOP)
wall(kit_w, "x", -3.268, -0.147, 3.568, 1)
wall(kit_w, "x", -0.074, -0.147, 3.568, -1)
wall(kit_w, "z", -0.147, -3.268, -0.074, 1, [KITCHEN_DOOR], 0.011)
wall(kit_w, "z", 3.568, -3.268, -0.074, -1, [KITCHEN_WINDOW], 0.248)
f = Part("Floor_Kitchen", material("M_Laminate"))
floor_rect(f, -3.268, -0.074, -0.147, 3.568)
c = Part("Ceiling_Kitchen", material("M_CeilingGrey"))
floor_rect(c, -3.268, -0.074, -0.147, 3.568, H, up=False)

# Hall
TRIM_PART = "Trim_Hall"
hall_w = Part("Walls_Hall", material("M_WallGrey"))
BATH_DOOR = (-2.237, -1.5, 0, DOOR_TOP)
ENTRY = (-1.137, -0.268, 0, DOOR_TOP)
wall(hall_w, "x", -1.358, -3.816, -0.158, 1, [BATH_DOOR], 0.137)
wall(hall_w, "x", -0.074, -3.816, -0.158, -1, [BEDROOM_DOOR], 0.137)
wall(hall_w, "z", -0.158, -1.358, -0.074, -1, [KITCHEN_DOOR], 0.0)
wall(hall_w, "z", -3.816, -1.358, -0.074, 1, [ENTRY], 0.14)
f = Part("Floor_Hall", material("M_Laminate"))
floor_rect(f, -1.358, -0.074, -3.816, -0.158)
# thresholds, so no gap shows through the door openings
floor_rect(f, -1.084, -0.284, -0.158, -0.147, step=1)
floor_rect(f, -0.074, 0.063, -2.0, -1.168, step=1)
floor_rect(f, -1.495, -1.358, -2.237, -1.5, step=1)
c = Part("Ceiling_Hall", material("M_CeilingGrey"))
floor_rect(c, -1.358, -0.074, -3.816, -0.158, H, up=False)

# Bathroom
TRIM_PART = "Trim_Bath"
bath_w = Part("Walls_Bath", material("M_BathTile"))
wall(bath_w, "x", -3.268, -3.026, -0.589, 1, skirting=False)
wall(bath_w, "x", -1.495, -3.026, -0.589, -1, [BATH_DOOR], 0.0, skirting=False)
wall(bath_w, "z", -3.026, -3.268, -1.495, 1, skirting=False)
wall(bath_w, "z", -0.589, -3.268, -1.495, -1, skirting=False)
f = Part("Floor_Bath", material("M_HexTile"))
floor_rect(f, -3.268, -1.495, -3.026, -0.589)
c = Part("Ceiling_Bath", material("M_CeilingGrey"))
floor_rect(c, -3.268, -1.495, -3.026, -0.589, H, up=False)

# Balcony, seen through the door and window. Glazed all round; the panes are the sky.
TRIM_PART = "Trim_Bedroom"
bal = Part("Balcony", material("M_WallGrey"))
wall(bal, "z", 3.884, 0.089, 3.39, 1, [WINDOW_HOLE, BALCONY_DOOR], 0.0, skirting=False)
floor_rect(bal, 0.089, 3.39, 3.884, 4.763)
floor_rect(bal, 0.089, 3.39, 3.884, 4.763, H, up=False)
# outside the kitchen window: the floor of the reveal is enough, the pane closes it
sky = Part("Window_Panes", material("M_Pane"))
sky.rect((0.089, 0, 4.763), (3.39, H, 4.763), (0, 0, -1))
sky.rect((0.089, 0, 3.884), (0.089, H, 4.763), (1, 0, 0))
sky.rect((3.39, 0, 3.884), (3.39, H, 4.763), (-1, 0, 0))
sky.rect((-2.6, 0.7, 3.816), (-0.5, 2.4, 3.816), (0, 0, -1))

# ---------------------------------------------------------------- frames in the window holes
trim = Part.parts["Trim_Bedroom"]
WHITE = (0.86, 0.86, 0.84)
FRAME = 0.045


def window_frame(part, x0, x1, y0, y1, z, bars=()):
    x0, x1, y0, y1 = x0 - 0.01, x1 + 0.01, y0 - 0.01, y1 + 0.01
    part.box((x0, y0, z), (x1, y0 + FRAME, z + 0.05), WHITE)
    part.box((x0, y1 - FRAME, z), (x1, y1, z + 0.05), WHITE)
    part.box((x0, y0, z), (x0 + FRAME, y1, z + 0.05), WHITE)
    part.box((x1 - FRAME, y0, z), (x1, y1, z + 0.05), WHITE)
    for b in bars:
        part.box((b - FRAME / 2, y0, z), (b + FRAME / 2, y1, z + 0.05), WHITE)


window_frame(Part.parts["Trim_Kitchen"], -2.426, -0.689, WINDOW_BOTTOM, WINDOW_TOP, 3.68, [-1.56])
window_frame(trim, 0.837, 1.679, WINDOW_BOTTOM, WINDOW_TOP, 3.72)
window_frame(trim, 1.679, 2.547, 0.0, WINDOW_TOP, 3.72)
Part.parts["Trim_Kitchen"].box((-2.5, WINDOW_BOTTOM - 0.04, 3.45), (-0.6, WINDOW_BOTTOM, 3.568), WHITE)   # kitchen sill
trim.box((0.78, WINDOW_BOTTOM - 0.04, 3.45), (1.68, WINDOW_BOTTOM, 3.568), WHITE)   # bedroom sill

# ---------------------------------------------------------------- doors that stand open, as on the plan
door_mat = material("M_DoorWhite")
Part("Doors_Kitchen", door_mat).slab((-0.31, -0.13), 125, 0.78, 0.04, 0, DOOR_TOP - 0.01)      # kitchen, into the kitchen
Part("Doors_Hall", door_mat).slab((-1.33, -2.21), -70, 0.72, 0.04, 0, DOOR_TOP - 0.01)       # bathroom, into the hall
Part("Doors_Bedroom", door_mat).slab((0.08, -1.97), 12, 0.8, 0.04, 0, DOOR_TOP - 0.01)           # bedroom, into the bedroom

# The way out. An anomaly swings it around Door Hinge at (-1.137, -3.79).
entry = Part("Door", material("M_DoorEntry"))
entry.box((-1.137, 0.0, -3.81), (-0.268, DOOR_TOP - 0.005, -3.77), skip=(), uv="fill")

# ---------------------------------------------------------------- bedroom furniture
oak = Part("Oak_Bedroom", material("M_Oak"))
# bed frame
for lx, lz in ((1.25, -0.8), (1.25, 0.87), (3.12, -0.8), (3.12, 0.87)):
    oak.box((lx, 0.0, lz), (lx + 0.06, 0.13, lz + 0.06), (0.8, 0.78, 0.76))
oak.box((1.24, 0.12, -0.81), (3.19, 0.31, -0.775))
oak.box((1.24, 0.12, 0.895), (3.19, 0.31, 0.93))
oak.box((1.24, 0.12, -0.775), (1.275, 0.31, 0.895))
# headboard: posts and a top rail around a panel set back from them
oak.box((3.19, 0.0, -0.84), (3.258, 1.0, -0.77))
oak.box((3.19, 0.0, 0.90), (3.258, 1.0, 0.97))
oak.box((3.19, 0.92, -0.77), (3.258, 1.0, 0.90))
oak.box((3.215, 0.0, -0.77), (3.258, 0.92, 0.90), (0.84, 0.82, 0.8))
oak.box((2.82, 0.0, 1.01), (3.25, 0.5, 1.47))                         # nightstands
oak.box((2.82, 0.0, -1.38), (3.25, 0.5, -0.92))
for z0, z1 in ((1.03, 1.45), (-1.36, -0.94)):
    oak.box((2.805, 0.08, z0), (2.83, 0.26, z1), (0.55, 0.45, 0.32))
    oak.box((2.805, 0.28, z0), (2.83, 0.46, z1), (0.55, 0.45, 0.32))
oak.box((0.547, 0.0, -3.0), (3.258, 2.45, -2.474))                    # wardrobe, south wall
for i in range(1, 5):
    x = 0.547 + (3.258 - 0.547) * i / 5
    oak.box((x - 0.006, 0.05, -2.48), (x + 0.006, 2.4, -2.46), (0.25, 0.2, 0.15))
Part("Oak_Hall", material("M_Oak")).box((-0.11, 0.0, -3.8), (-0.074, 2.4, -2.26))   # wardrobe doors in the hall
oak_kitchen = Part("Oak_Kitchen", material("M_Oak"))
oak_kitchen.box((-0.75, 0.0, 1.46), (-0.72, 0.72, 1.5), (0.5, 0.4, 0.28))     # table legs and top
oak_kitchen.box((-0.75, 0.0, 2.36), (-0.72, 0.72, 2.40), (0.5, 0.4, 0.28))
oak_kitchen.box((-0.95, 0.72, 1.46), (-0.08, 0.76, 2.40), (0.62, 0.46, 0.30))

bed = Part("Bed", material("M_Blanket"))
BED_X0, BED_X1, BED_Z0, BED_Z1 = 1.22, 3.19, -0.83, 0.96
BED_TOP = 0.55
TURN_BACK = 2.62      # where the blanket is folded back from the pillows


def blanket_drop(inset):
    """Height of the blanket by how far in from the bed's edge: it falls off the mattress to a hem."""
    points = ((-0.015, 0.285), (0.0, 0.46), (0.03, 0.53), (0.09, BED_TOP), (9.0, BED_TOP))
    for (a, ya), (b, yb) in zip(points, points[1:]):
        if inset <= b:
            return ya + (yb - ya) * (inset - a) / (b - a)
    return BED_TOP


blanket_x = [BED_X0 - 0.015, BED_X0, BED_X0 + 0.03, BED_X0 + 0.09, 1.75, 2.2, TURN_BACK - 0.1, TURN_BACK, TURN_BACK + 0.1, BED_X1]
blanket_z = [BED_Z0 - 0.015, BED_Z0, BED_Z0 + 0.03, BED_Z0 + 0.09, -0.3, 0.065, 0.43, BED_Z1 - 0.09, BED_Z1 - 0.03, BED_Z1, BED_Z1 + 0.015]


def blanket_at(x, z):
    """Height and shade of the blanket at a point on the plan."""
    inset = min(x - BED_X0, z - BED_Z0, BED_Z1 - z)
    y = blanket_drop(inset)
    cloth = min(1.0, max(0.0, inset / 0.09))
    # Slow folds across the top, a wavy hem, and the fold turned back below the pillows.
    y += cloth * (0.012 * math.sin(x * 5.0 + z * 3.0) + 0.008 * math.sin(z * 9.0 - x * 2.0 + 1.0))
    ridge = math.exp(-((x - TURN_BACK) / 0.07) ** 2) * cloth
    y += ridge * 0.03
    if inset <= -0.01:
        y += 0.015 * math.sin(x * 13.0 + z * 11.0)
    fold = 0.9 + 0.1 * math.sin(x * 7.0 - z * 5.0)
    light = (0.72 + 0.28 * cloth) * fold
    if x > TURN_BACK + 0.05:
        light *= 0.82            # the shaded part under the pillows
    light *= 1 + 0.2 * ridge
    return y, (light, light, light)


blanket_rows = []
for z in blanket_z:
    row = []
    for x in blanket_x:
        y, tint = blanket_at(x, z)
        row.append(((x, y, z), (x / 0.9, z / 0.9), tint))
    blanket_rows.append(row)
bed.surface(blanket_rows, (2.2, 0.1, 0.065))

# Someone lying under that same blanket, on the right side seen from the foot of the bed.
# Same cloth, same texture lined up with it; the rim sinks into the blanket so no edge shows.
BODY_Z = -0.36
BODY_X = [1.32, 1.42, 1.6, 1.8, 1.98, 2.2, 2.4, 2.55, 2.68]
BODY_RISE = [0.0, 0.15, 0.11, 0.16, 0.21, 0.19, 0.25, 0.18, 0.0]    # feet, shins, thighs, hips, chest, shoulders
BODY_HALF = [0.10, 0.15, 0.16, 0.20, 0.26, 0.24, 0.30, 0.28, 0.20]
body_rows = []
for dz in (-0.34, -0.24, -0.12, 0.0, 0.12, 0.24, 0.34):
    row = []
    for x, rise, half in zip(BODY_X, BODY_RISE, BODY_HALF):
        z = BODY_Z + dz
        y, tint = blanket_at(x, z)
        across = abs(dz) / half
        lift = rise * max(0.0, 1 - across * across) ** 0.6 - 0.012
        # The flanks fall into shade, so the shape reads even though the cloth is the same.
        flank = 1 - 0.3 * math.sin(math.pi * min(across, 1.0)) if rise > 0 else 1.0
        row.append(((x, y + lift, z), (x / 0.9, z / 0.9), tuple(c * flank for c in tint)))
    body_rows.append(row)
Part("Futon_Body", material("M_Blanket")).surface(body_rows, (2.0, 0.1, BODY_Z))

PILLOW = (0.8, 0.92, 0.78)
bed.puff((2.88, 0.665, -0.36), 0.52, 0.74, 0.085, 28, PILLOW)
bed.puff((2.88, 0.665, 0.49), 0.52, 0.74, 0.085, 28, PILLOW)

towels = Part("Bed_Towels", material("M_Prop"))
towels.box((1.44, 0.54, 0.44), (1.86, 0.585, 0.82), (0.74, 0.72, 0.66), skip=("y-",))
towels.box((1.45, 0.585, 0.455), (1.85, 0.625, 0.805), (0.3, 0.52, 0.5), skip=("y-",))
towels.box((1.46, 0.625, 0.45), (1.84, 0.655, 0.81), (0.78, 0.78, 0.74), skip=("y-",))
towels.box((1.47, 0.655, 0.465), (1.83, 0.69, 0.795), (0.46, 0.64, 0.6), skip=("y-",))

carpet = Part("Carpet", material("M_Carpet"))
carpet.rect((0.705, 0.012, -1.395), (2.653, 0.012, 1.484), (0, 1, 0), uv="fill")

curtains = Part("Curtains", material("M_CurtainGreen"))
curtain(curtains, 0.2, 0.84, 3.46, 0.03, 2.45)
curtain(curtains, 2.55, 3.22, 3.46, 0.03, 2.45)
tulle = Part("Tulle", material("M_Tulle"))
curtain(tulle, 0.8, 2.6, 3.52, 0.03, 2.45, folds=8, depth=0.02)
Part("Rod_Bedroom", material("M_Prop")).box((0.1, 2.45, 3.44), (3.25, 2.48, 3.54), (0.16, 0.16, 0.16))
Part("Rod_Kitchen", material("M_Prop")).box((-3.1, 2.45, 3.44), (-0.2, 2.48, 3.54), (0.16, 0.16, 0.16))

props = Part("Props_Bedroom", material("M_Prop"))
# TV bracket and air conditioner
props.box((3.04, 2.06, 1.2), (3.258, 2.32, 1.95), (0.84, 0.84, 0.82))
props.box((0.063, 1.1, -0.1), (0.072, 1.4, 0.3), (0.05, 0.05, 0.05))
# vase with flowers by the window
props.box((0.28, 0.0, 3.13), (0.46, 0.32, 3.31), (0.72, 0.72, 0.8))
for dx, dz, col in ((0.0, 0.0, (0.72, 0.42, 0.52)), (0.1, 0.06, (0.8, 0.72, 0.5)), (-0.08, 0.05, (0.62, 0.55, 0.72))):
    props.box((0.33 + dx, 0.32, 3.2 + dz), (0.40 + dx, 0.72, 3.24 + dz), (0.2, 0.32, 0.2))
    lift = (dx + 0.08) * 0.5
    props.box((0.28 + dx, 0.72 + lift, 3.15 + dz), (0.45 + dx, 0.86 + lift, 3.29 + dz), col)
# ---- kitchen, grey fronts under a dark top
props = Part("Props_Kitchen", material("M_Prop"))
GREY = (0.34, 0.35, 0.37)
TOP = (0.20, 0.18, 0.16)
props.box((-3.268, 0.0, 2.568), (-2.584, 1.72, 3.5), (0.5, 0.51, 0.52), skip=("x+",))   # fridge
props.rect((-2.584, 0.0, 2.568), (-2.584, 0.66, 3.5), (1, 0, 0), (0.42, 0.43, 0.44))
props.rect((-2.584, 0.66, 2.568), (-2.584, 1.72, 3.5), (1, 0, 0), (0.54, 0.55, 0.56))
props.box((-2.6, 0.65, 2.568), (-2.57, 0.67, 3.5), (0.2, 0.2, 0.2))
props.box((-2.6, 0.9, 2.62), (-2.57, 1.05, 2.66), (0.2, 0.2, 0.2))
props.box((-3.2, 1.72, 2.72), (-2.68, 2.0, 3.32), (0.78, 0.78, 0.78))                  # microwave
props.box((-2.69, 1.75, 2.78), (-2.665, 1.97, 3.2), (0.1, 0.1, 0.1))                   # its door
props.box((-3.268, 0.0, 1.0), (-2.72, 0.86, 2.568), GREY)                              # west run
props.box((-3.268, 0.86, 0.99), (-2.68, 0.9, 2.568), TOP)
props.box((-3.268, 0.0, -0.147), (-1.32, 0.86, 0.395), GREY)                           # south run
props.box((-3.268, 0.86, -0.147), (-1.3, 0.9, 0.42), TOP, skip=("y+",))
# The counter top has a real hole with the sink sunk into it.
props.rect((-3.268, 0.9, -0.147), (-2.1, 0.9, 0.42), (0, 1, 0), TOP)
props.rect((-1.5, 0.9, -0.147), (-1.3, 0.9, 0.42), (0, 1, 0), TOP)
props.rect((-2.1, 0.9, -0.147), (-1.5, 0.9, -0.08), (0, 1, 0), TOP)
props.rect((-2.1, 0.9, 0.34), (-1.5, 0.9, 0.42), (0, 1, 0), TOP)
SINK = (0.42, 0.42, 0.44)
props.rect((-2.1, 0.87, -0.08), (-1.5, 0.87, 0.34), (0, 1, 0), (0.3, 0.3, 0.32))
props.rect((-2.1, 0.87, -0.08), (-1.5, 0.9, -0.08), (0, 0, 1), SINK)
props.rect((-2.1, 0.87, 0.34), (-1.5, 0.9, 0.34), (0, 0, -1), SINK)
props.rect((-2.1, 0.87, -0.08), (-2.1, 0.9, 0.34), (1, 0, 0), SINK)
props.rect((-1.5, 0.87, -0.08), (-1.5, 0.9, 0.34), (-1, 0, 0), SINK)
props.box((-1.84, 0.9, -0.125), (-1.79, 1.12, -0.09), (0.6, 0.6, 0.62))                # tap
props.box((-1.84, 1.08, -0.09), (-1.79, 1.11, 0.05), (0.6, 0.6, 0.62))
props.rect((-3.255, 0.9, -0.147), (-3.255, 1.5, 2.568), (1, 0, 0), (0.17, 0.17, 0.18)) # splashback
props.box((-3.268, 1.58, 0.9), (-3.0, 1.61, 2.5), (0.42, 0.34, 0.26))                  # shelf
# stools
for z in (1.16, 2.62):
    props.box((-0.68, 0.0, z - 0.02), (-0.65, 0.44, z + 0.02), (0.15, 0.15, 0.15))
    props.box((-0.45, 0.0, z - 0.02), (-0.42, 0.44, z + 0.02), (0.15, 0.15, 0.15))
    props.box((-0.72, 0.44, z - 0.17), (-0.38, 0.48, z + 0.17), (0.72, 0.62, 0.38))
# ---- bathroom
props = Part("Props_Bath", material("M_Prop"))
props.box((-3.26, 0.0, -1.30), (-1.52, 0.55, -0.60), (0.82, 0.82, 0.80), skip=("y+",))  # tub
props.rect((-3.26, 0.55, -1.30), (-3.17, 0.55, -0.60), (0, 1, 0), (0.86, 0.86, 0.84))
props.rect((-1.61, 0.55, -1.30), (-1.52, 0.55, -0.60), (0, 1, 0), (0.86, 0.86, 0.84))
props.rect((-3.17, 0.55, -1.30), (-1.61, 0.55, -1.21), (0, 1, 0), (0.86, 0.86, 0.84))
props.rect((-3.17, 0.55, -0.69), (-1.61, 0.55, -0.60), (0, 1, 0), (0.86, 0.86, 0.84))
props.rect((-3.17, 0.25, -1.21), (-1.61, 0.25, -0.69), (0, 1, 0), (0.70, 0.72, 0.74))
for pts, n in (((-3.17, 0.25, -1.21), (0, 0, 1)),):
    props.rect((-3.17, 0.25, -1.21), (-1.61, 0.55, -1.21), (0, 0, 1), (0.74, 0.74, 0.74))
    props.rect((-3.17, 0.25, -0.69), (-1.61, 0.55, -0.69), (0, 0, -1), (0.74, 0.74, 0.74))
    props.rect((-3.17, 0.25, -1.21), (-3.17, 0.55, -0.69), (1, 0, 0), (0.74, 0.74, 0.74))
    props.rect((-1.61, 0.25, -1.21), (-1.61, 0.55, -0.69), (-1, 0, 0), (0.74, 0.74, 0.74))
props.box((-3.268, 0.0, -2.18), (-2.82, 0.76, -1.42), (0.78, 0.77, 0.72))              # washbasin
props.box((-3.268, 0.76, -2.22), (-2.78, 0.84, -1.38), (0.88, 0.88, 0.86))
props.box((-3.22, 0.0, -2.84), (-2.92, 0.82, -2.46), (0.84, 0.84, 0.82))               # toilet cistern
props.box((-2.92, 0.0, -2.8), (-2.48, 0.42, -2.5), (0.86, 0.86, 0.84))
props.box((-3.268, 2.2, -2.2), (-3.25, 2.45, -1.95), (0.6, 0.6, 0.6))                  # vent
# ---- hall: a switch and a small picture
props = Part("Props_Hall", material("M_Prop"))
props.box((-1.358, 1.05, -1.1), (-1.34, 1.16, -1.02), (0.85, 0.85, 0.85))
props.box((-1.358, 1.25, -3.4), (-1.335, 1.75, -2.95), (0.35, 0.28, 0.2))
props.box((-1.345, 1.3, -3.36), (-1.32, 1.7, -2.99), (0.45, 0.42, 0.34))

washer = Part("Washer", material("M_Washer"))
washer.rect((-2.65, 0.0, 0.42), (-2.65, 0.84, 0.98), (1, 0, 0), uv="fill")
Part.parts["Props_Kitchen"].box((-3.268, 0.0, 0.42), (-2.65, 0.84, 0.98), (0.82, 0.82, 0.8), skip=("x+",))
hob = Part("Hob", material("M_Hob"))
hob.rect((-3.2, 0.918, 1.5), (-2.72, 0.918, 2.3), (0, 1, 0), uv="fill")
Part.parts["Props_Kitchen"].box((-3.2, 0.9, 1.5), (-2.72, 0.918, 2.3), (0.1, 0.1, 0.1), skip=("y+", "y-"))

runner = Part("Runner", material("M_Runner"))
runner.rect((-2.52, 0.012, 0.45), (-1.32, 0.012, 3.3), (0, 1, 0), uv="fill")
mat = Part("Bath_Mat", material("M_BathMat"))
mat.rect((-2.65, 0.012, -2.2), (-2.05, 0.012, -1.4), (0, 1, 0), uv="fill")

kcur = Part("Curtains_Kitchen", material("M_CurtainGrey"))
curtain(kcur, -3.0, -2.42, 3.46, 0.03, 2.45)
curtain(kcur, -0.7, -0.2, 3.46, 0.03, 2.45)
ktul = Part("Tulle_Kitchen", material("M_Tulle"))
curtain(ktul, -2.45, -0.68, 3.52, 0.82, 2.45, folds=8, depth=0.02)

# Ceiling spots, which glow with the light. One mesh, because an anomaly tints them together.
lamp = Part("Lamp", material("M_Lamp"))
SPOTS = [(1.0, 2.0), (2.6, 2.0), (1.0, -1.1), (2.6, -1.1), (-1.7, 1.7), (-0.7, -2.0), (-2.4, -1.8)]
for x, z in SPOTS:
    r = 0.06
    lamp.quad([(x - r, H - 0.012, z - r), (x + r, H - 0.012, z - r), (x + r, H - 0.012, z + r), (x - r, H - 0.012, z + r)], (0, -1, 0))

# ---------------------------------------------------------------- pieces that only an anomaly shows
tv = Part("TV", material("M_TV"))
tv.rect((0.09, 1.0, -0.34), (0.09, 1.52, 0.54), (1, 0, 0), uv="fill")
tv_case = Part("TV_Case", material("M_Prop"))
tv_case.box((0.07, 1.0, -0.34), (0.09, 1.52, 0.54), (0.04, 0.04, 0.04), skip=("x+",))

mirror = Part("Mirror", material("M_Mirror"))
mirror.rect((-3.255, 1.05, -2.2), (-3.255, 1.75, -1.4), (1, 0, 0), uv="fill")

table = Part("Table_Items", material("M_Prop"))
table.box((-0.72, 0.76, 2.0), (-0.52, 1.0, 2.18), (0.86, 0.86, 0.84))    # kettle
table.box((-0.5, 0.82, 2.04), (-0.46, 0.94, 2.14), (0.8, 0.8, 0.78))
table.box((-0.32, 0.76, 1.6), (-0.2, 0.84, 1.72), (0.3, 0.26, 0.24))     # pot plant
table.box((-0.34, 0.84, 1.58), (-0.18, 1.0, 1.74), (0.24, 0.42, 0.24))

shelf = Part("Shelf_Items", material("M_Prop"))
shelf.box((-3.22, 1.61, 1.5), (-3.0, 1.74, 1.78), (0.45, 0.1, 0.08))     # red pot
shelf.box((-3.2, 1.74, 1.56), (-3.02, 1.77, 1.72), (0.36, 0.08, 0.07))
shelf.box((-3.2, 1.61, 1.14), (-3.1, 1.78, 1.24), (0.78, 0.74, 0.5))     # jars
shelf.box((-3.2, 1.61, 1.28), (-3.1, 1.74, 1.38), (0.45, 0.55, 0.6))


# ---------------------------------------------------------------- finish our own parts
def finish(part):
    mesh = bpy.data.meshes.new(part.name)
    part.bm.to_mesh(mesh)
    part.bm.free()
    mesh.materials.append(part.mat)
    obj = bpy.data.objects.new(part.name, mesh)
    collection.objects.link(obj)
    return obj


for part in Part.parts.values():
    finish(part)

# ---------------------------------------------------------------- bring over the scary pieces from the old room
with bpy.data.libraries.load(OLD_BLEND, link=False) as (src, dst):
    wanted = ["Black_Sphere", "Safe", "Poster", "Window_Ghost", "Prints_1", "Prints_2", "Prints_3", "Door_Void", "Door_Face",
              "Door_Fingers", "Futon_Hair", "Futon_Hand", "Figure_Corner", "Figure_Lens"]
    dst.objects = [n for n in src.objects if n in wanted]

# name: (turn on the plan in degrees, dx, dy, dz) applied in Unity space, about the old room's origin.
# A turn of 90 sends the old east-facing door onto the new north-facing entrance.
MOVES = {
    "Black_Sphere": (0, -0.9, 0, 1.0),
    "Safe": (0, -0.8, 0, -0.7),
    "Poster": (90, 1.46, 0.55, -0.78),
    "Window_Ghost": (180, 0.9, 0.22, 1.93),
    "Prints_1": (0, 1.01, 0, 1.6),
    "Prints_2": (0, 1.01, 0.25, 1.6),
    "Prints_3": (0, 1.01, 0.25, 1.6),
    "Door_Void": (90, -0.237, 0, -1.6),
    "Door_Face": (90, -0.237, 0.33, -1.58),
    "Door_Fingers": (90, -0.237, 0.33, -1.58),
    "Futon_Hair": (90, 2.6, 0.51, -2.06),
    "Futon_Hand": (90, 2.6, 0.26, -2.01),
    "Figure_Corner": (0, 1.55, 0, -1.85),
    "Figure_Lens": (0, 0, 0, 0),
}
for obj in dst.objects:
    if obj is None:
        continue
    collection.objects.link(obj)
    obj.data = obj.data.copy()
    turn, dx, dy, dz = MOVES[obj.name]
    a = math.radians(turn)
    world = obj.matrix_world.copy()
    for v in obj.data.vertices:
        b = world @ v.co
        ux, uy, uz = -b.x, b.z, -b.y
        nx = ux * math.cos(a) - uz * math.sin(a) + dx
        nz = ux * math.sin(a) + uz * math.cos(a) + dz
        v.co = to_blender((nx, uy + dy, nz))
    obj.matrix_world = obj.matrix_world.Identity(4)
    obj.parent = None
    if obj.name == "Door_Void":
        # the old door was shorter: fill the whole opening
        for v in obj.data.vertices:
            u = (-v.co.x, v.co.z, -v.co.y)
            v.co = to_blender((-1.137 if u[0] < -0.7 else -0.268, 0.0 if u[1] < 0.8 else 2.05, u[2]))

bpy.ops.wm.save_as_mainfile(filepath=BLEND)

tris = {}
for obj in collection.objects:
    obj.data.calc_loop_triangles()
    tris[obj.name] = len(obj.data.loop_triangles)
print("RESULT tris total", sum(tris.values()))
print("RESULT", sorted(tris.items(), key=lambda kv: -kv[1])[:12])
print("RESULT missing old:", [n for n in MOVES if n not in tris])
for name in ("Poster", "Window_Ghost", "Door_Void", "Door_Face", "Door_Fingers", "Futon_Body", "Safe", "Prints_1", "Prints_3", "Figure_Corner"):
    o = bpy.data.objects[name]
    vs = [Vector((-v.co.x, v.co.z, -v.co.y)) for v in o.data.vertices]
    lo = [min(p[i] for p in vs) for i in range(3)]
    hi = [max(p[i] for p in vs) for i in range(3)]
    print("RESULT", name, "unity min", [round(x, 2) for x in lo], "max", [round(x, 2) for x in hi], "mat", [m.name for m in o.data.materials])

bpy.ops.export_scene.fbx(filepath=FBX, use_active_collection=True, axis_forward='-Z', axis_up='Y', apply_scale_options='FBX_SCALE_ALL',
                         bake_space_transform=True, mesh_smooth_type='FACE', colors_type='LINEAR')
print("RESULT exported")
