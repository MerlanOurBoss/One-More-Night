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

    def lathe(self, cx, cz, rings, first="out", n=12):
        """rings = (radius x, radius z, y, squareness 0..1, color), followed along the surface.
        Radius 0 closes the shape at a point. first says which way the first band faces: out or up.
        Squareness needs n divisible by 8, so the rectangle's corners land on vertices."""

        def point(ring, i):
            rx, rz, y, square, _ = ring
            a = 2 * math.pi * i / n
            c, d = math.cos(a), math.sin(a)
            edge = max(abs(c), abs(d))
            e = 2 / 2.6
            round_x = math.copysign(abs(c) ** e, c)
            round_z = math.copysign(abs(d) ** e, d)
            return (cx + rx * (round_x + (c / edge - round_x) * square), y, cz + rz * (round_z + (d / edge - round_z) * square))

        grid = []
        for ring in rings:
            if ring[0] == 0:
                grid.append([self.bm.verts.new(to_blender((cx, ring[2], cz)))] * n)
            else:
                grid.append([self.bm.verts.new(to_blender(point(ring, i))) for i in range(n)])

        a, b, d = grid[0][0].co, grid[0][1].co, grid[1][0].co
        probe = (b - a).cross(d - a)
        mid = (a + b) / 2
        want = Vector((mid.x + cx, mid.y + cz, 0)) if first == "out" else Vector((0, 0, 1))
        flip = probe.dot(want) < 0

        for j in range(len(rings) - 1):
            for i in range(n):
                k = (i + 1) % n
                cells = [(j, i), (j, k), (j + 1, k), (j + 1, i)]
                seen, verts, colors = set(), [], []
                for rj, ri in cells:
                    v = grid[rj][ri]
                    if v not in seen:
                        seen.add(v)
                        verts.append(v)
                        colors.append(rings[rj][4])
                if flip:
                    verts.reverse()
                    colors.reverse()
                face = self.bm.faces.new(verts)
                face.smooth = True
                lookup = dict(zip(verts, colors))
                for loop in face.loops:
                    c = lookup[loop.vert]
                    loop[self.uv].uv = (0, 0)
                    loop[self.col] = (c[0], c[1], c[2], 1)

    def loft(self, rows, centers, wrap=False):
        """rows[j][i] = (position, uv, color). Faces point away from centers[j].
        With wrap, the last column closes onto the first: same vertices, its own UVs, so no seam in the shading."""
        count = len(rows[0]) - (1 if wrap else 0)
        verts = [[self.bm.verts.new(to_blender(cell[0])) for cell in row[:count]] for row in rows]
        for j in range(len(rows) - 1):
            middle = to_blender(tuple((centers[j][k] + centers[j + 1][k]) / 2 for k in range(3)))
            for i in range(len(rows[j]) - 1):
                k = (i + 1) % count if wrap else i + 1
                pick = [(j, i, i % count), (j, i + 1, k), (j + 1, i + 1, k), (j + 1, i, i % count)]
                face = self.bm.faces.new([verts[a][c] for a, _, c in pick])
                face.smooth = True
                face.normal_update()
                if face.normal.dot(face.calc_center_median() - middle) < 0:
                    face.normal_flip()
                lookup = {verts[a][c]: rows[a][b] for a, b, c in pick}
                for loop in face.loops:
                    cell = lookup[loop.vert]
                    loop[self.uv].uv = cell[1]
                    loop[self.col] = (cell[2][0], cell[2][1], cell[2][2], 1)
        return verts

    def cap(self, ring, center, uv, color, inside):
        """Closes an open ring of vertices with a fan to one point."""
        tip = self.bm.verts.new(to_blender(center))
        away = to_blender(inside)
        for i in range(len(ring)):
            face = self.bm.faces.new([ring[i], ring[(i + 1) % len(ring)], tip])
            face.smooth = True
            face.normal_update()
            if face.normal.dot(face.calc_center_median() - away) < 0:
                face.normal_flip()
            for loop in face.loops:
                loop[self.uv].uv = uv
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
HANDLE_METAL = (0.42, 0.42, 0.44)


def door_handles(part, hinge, angle_deg, width, thickness):
    """A lever on each face, built in the door's own plane so it turns with it."""
    a = math.radians(angle_deg)
    d = Vector((math.cos(a), 0, math.sin(a)))
    n = Vector((-math.sin(a), 0, math.cos(a)))
    o = Vector((hinge[0], 0, hinge[1]))

    def block(a0, a1, s0, s1, y0, y1):
        def at(along, side, y):
            p = o + d * along + n * side
            return (p.x, y, p.z)
        faces = (
            ([at(a0, s1, y0), at(a1, s1, y0), at(a1, s1, y1), at(a0, s1, y1)], n),
            ([at(a0, s0, y0), at(a1, s0, y0), at(a1, s0, y1), at(a0, s0, y1)], -n),
            ([at(a0, s0, y1), at(a1, s0, y1), at(a1, s1, y1), at(a0, s1, y1)], Vector((0, 1, 0))),
            ([at(a0, s0, y0), at(a1, s0, y0), at(a1, s1, y0), at(a0, s1, y0)], Vector((0, -1, 0))),
            ([at(a1, s0, y0), at(a1, s1, y0), at(a1, s1, y1), at(a1, s0, y1)], d),
            ([at(a0, s0, y0), at(a0, s1, y0), at(a0, s1, y1), at(a0, s0, y1)], -d),
        )
        for pts, normal in faces:
            part.quad(pts, tuple(normal), [(0, 0)] * 4, HANDLE_METAL)

    t = thickness / 2
    grip = width - 0.07
    for side in (1, -1):
        s = sorted((side * t, side * (t + 0.05)))
        block(grip - 0.015, grip + 0.015, s[0], s[1], 0.97, 1.0)           # neck
        s = sorted((side * (t + 0.04), side * (t + 0.06)))
        block(grip - 0.11, grip + 0.015, s[0], s[1], 0.975, 0.995)         # lever
Part("Doors_Kitchen", door_mat).slab((-0.31, -0.13), 125, 0.78, 0.04, 0, DOOR_TOP - 0.01)      # kitchen, into the kitchen
Part("Doors_Hall", door_mat).slab((-1.52, -2.21), 225, 0.72, 0.04, 0, DOOR_TOP - 0.01)       # bathroom, opens into the bathroom
Part("Doors_Bedroom", door_mat).slab((0.08, -1.97), 12, 0.8, 0.04, 0, DOOR_TOP - 0.01)           # bedroom, into the bedroom
door_handles(Part.parts["Doors_Kitchen"], (-0.31, -0.13), 125, 0.78, 0.04)
door_handles(Part.parts["Doors_Hall"], (-1.52, -2.21), 225, 0.72, 0.04)
door_handles(Part.parts["Doors_Bedroom"], (0.08, -1.97), 12, 0.8, 0.04)
# The strip on the hinge side of each opening: without it a closed door leaves a slit of light.
stops = Part.parts["Reveals"]
stops.box((-0.312, 0.0, -0.165), (-0.284, DOOR_TOP, -0.11), TRIM)
stops.box((-1.545, 0.0, -2.237), (-1.49, DOOR_TOP, -2.212), TRIM)
stops.box((0.045, 0.0, -2.0), (0.1, DOOR_TOP, -1.972), TRIM)

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
# wardrobe, south wall
oak.box((0.547, 0.0, -3.0), (3.258, 2.45, -2.474), (0.22, 0.17, 0.12))
WARDROBE_DOORS = 5
WARDROBE_STEP = (3.258 - 0.547) / WARDROBE_DOORS
for i in range(WARDROBE_DOORS):
    x0 = 0.547 + i * WARDROBE_STEP + 0.006
    x1 = x0 + WARDROBE_STEP - 0.012
    oak.box((x0, 0.09, -2.474), (x1, 2.4, -2.458), (0.92, 0.9, 0.86), uv=0.7)
oak.box((0.547, 0.0, -2.474), (3.258, 0.08, -2.462), (0.3, 0.24, 0.18), uv=0.7)
oak.box((0.547, 2.4, -2.49), (3.258, 2.47, -2.45), (0.8, 0.76, 0.7), uv=0.7)
oak.box((0.063, 0.12, -0.5), (0.43, 0.52, 0.5), (0.8, 0.76, 0.7), uv=0.7)
oak.box((0.063, 0.52, -0.52), (0.45, 0.55, 0.52), uv=0.7)
for z0, z1 in ((-0.49, -0.005), (0.005, 0.49)):
    oak.box((0.43, 0.14, z0), (0.444, 0.5, z1), (0.92, 0.9, 0.86), uv=0.7)
Part("Oak_Hall", material("M_Oak")).box((-0.11, 0.0, -3.8), (-0.074, 2.4, -2.26))   # wardrobe doors in the hall
oak_kitchen = Part("Oak_Kitchen", material("M_Oak"))
TABLE_LEG = (0.42, 0.33, 0.24)
for lx, lz in ((-0.92, 1.49), (-0.16, 1.49), (-0.92, 2.32), (-0.16, 2.32)):
    oak_kitchen.box((lx, 0.0, lz), (lx + 0.05, 0.72, lz + 0.05), TABLE_LEG, skip=("y+", "y-"))
oak_kitchen.box((-0.87, 0.65, 1.5), (-0.16, 0.72, 1.53), TABLE_LEG, skip=("y+",))
oak_kitchen.box((-0.87, 0.65, 2.33), (-0.16, 0.72, 2.36), TABLE_LEG, skip=("y+",))
oak_kitchen.box((-0.91, 0.65, 1.54), (-0.88, 0.72, 2.32), TABLE_LEG, skip=("y+",))
oak_kitchen.box((-0.15, 0.65, 1.54), (-0.12, 0.72, 2.32), TABLE_LEG, skip=("y+",))
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

CURTAIN_Z = 3.36      # back of the fold at 3.41
TULLE_Z = 3.415       # back of the fold at 3.435, clear of the sill
RAIL = (0.16, 0.16, 0.16)
curtains = Part("Curtains", material("M_CurtainGreen"))
curtain(curtains, 0.2, 0.84, CURTAIN_Z, 0.03, 2.45)
curtain(curtains, 2.55, 3.22, CURTAIN_Z, 0.03, 2.45)
tulle = Part("Tulle", material("M_Tulle"))
curtain(tulle, 0.8, 2.6, TULLE_Z, 0.03, 2.45, folds=8, depth=0.02)


def curtain_rail(name, x0, x1, brackets):
    rail = Part(name, material("M_Prop"))
    rail.box((x0, 2.45, 3.355), (x1, 2.48, 3.445), RAIL)
    for x in brackets:
        rail.box((x - 0.015, 2.455, 3.445), (x + 0.015, 2.475, 3.568), RAIL)


curtain_rail("Rod_Bedroom", 0.1, 3.25, (0.3, 1.66, 3.05))
curtain_rail("Rod_Kitchen", -2.62, -0.12, (-2.45, -1.37, -0.3))

props = Part("Props_Bedroom", material("M_Prop"))
# TV bracket and air conditioner
props.box((3.04, 2.06, 1.2), (3.258, 2.32, 1.95), (0.84, 0.84, 0.82))
props.box((0.063, 1.1, -0.1), (0.072, 1.4, 0.3), (0.05, 0.05, 0.05))
BED_METAL = (0.6, 0.6, 0.6)
BED_DARK = (0.06, 0.06, 0.07)
# Air conditioner: louvre and a small light.
props.box((3.03, 2.08, 1.24), (3.045, 2.13, 1.91), (0.5, 0.5, 0.5))
props.box((3.03, 2.25, 1.8), (3.04, 2.27, 1.84), (0.2, 0.7, 0.3))
# Wardrobe handles.
for i in range(WARDROBE_DOORS):
    x = 0.547 + i * WARDROBE_STEP + (WARDROBE_STEP - 0.05 if i % 2 == 0 else 0.03)
    props.box((x, 0.95, -2.458), (x + 0.02, 1.35, -2.44), BED_METAL)
# Drawer handles on the nightstands.
for zc in (1.24, -1.15):
    props.box((2.788, 0.16, zc - 0.06), (2.805, 0.18, zc + 0.06), BED_METAL)
    props.box((2.788, 0.36, zc - 0.06), (2.805, 0.38, zc + 0.06), BED_METAL)
# Bedside lamp and a book on one stand; an alarm clock and a glass on the other.
props.lathe(3.06, 1.26, [
    (0.07, 0.07, 0.5, 0.0, (0.4, 0.3, 0.2)),
    (0.06, 0.06, 0.52, 0.0, (0.46, 0.34, 0.22)),
    (0.018, 0.018, 0.55, 0.0, (0.46, 0.34, 0.22)),
    (0.018, 0.018, 0.74, 0.0, (0.46, 0.34, 0.22)),
    (0, 0, 0.74, 0.0, (0.46, 0.34, 0.22)),
], n=8)
props.lathe(3.06, 1.26, [
    (0.13, 0.13, 0.72, 0.0, (0.96, 0.84, 0.62)),
    (0.08, 0.08, 0.91, 0.0, (0.9, 0.78, 0.56)),
    (0, 0, 0.91, 0.0, (0.8, 0.68, 0.48)),
], n=12)
props.box((2.87, 0.5, 1.08), (3.0, 0.535, 1.27), (0.42, 0.14, 0.12), skip=("y-",))
props.box((3.1, 0.5, -1.34), (3.22, 0.6, -1.2), (0.12, 0.12, 0.13), skip=("y-",))
props.box((3.092, 0.525, -1.325), (3.1, 0.58, -1.215), (0.62, 0.1, 0.08))
props.lathe(2.92, -1.3, [
    (0.03, 0.03, 0.5, 0.0, (0.62, 0.68, 0.7)),
    (0.036, 0.036, 0.62, 0.0, (0.76, 0.82, 0.84)),
    (0.03, 0.03, 0.62, 0.0, (0.42, 0.5, 0.54)),
    (0, 0, 0.58, 0.0, (0.3, 0.36, 0.4)),
], n=8)
# Under the TV: console legs and handles, a set-top box, a remote and a framed photo.
for lx, lz in ((0.1, -0.46), (0.38, -0.46), (0.1, 0.42), (0.38, 0.42)):
    props.box((lx, 0.0, lz), (lx + 0.03, 0.12, lz + 0.03), BED_METAL, skip=("y+", "y-"))
for z in (-0.06, 0.06):
    props.box((0.444, 0.28, z - 0.012), (0.46, 0.38, z + 0.012), BED_METAL)
props.box((0.12, 0.55, -0.12), (0.34, 0.6, 0.12), (0.1, 0.1, 0.11), skip=("y-",))
props.box((0.34, 0.565, -0.09), (0.346, 0.58, -0.07), (0.2, 0.7, 0.3))
props.box((0.3, 0.55, 0.22), (0.35, 0.57, 0.38), (0.06, 0.06, 0.07), skip=("y-",))
props.box((0.12, 0.55, -0.42), (0.14, 0.76, -0.24), (0.3, 0.22, 0.16), skip=("y-",))
props.box((0.13, 0.57, -0.405), (0.154, 0.74, -0.255), (0.74, 0.72, 0.66))
props.box((0.15, 0.6, -0.355), (0.168, 0.7, -0.305), (0.08, 0.08, 0.09))
# Wall shelf of books, and two family photos with nobody you can make out.
props.box((0.063, 1.42, 1.1), (0.27, 1.45, 2.3), (0.34, 0.26, 0.18))
BOOKS = ((0.05, 0.27, (0.46, 0.14, 0.12)), (0.04, 0.23, (0.2, 0.3, 0.4)), (0.06, 0.25, (0.62, 0.56, 0.36)),
         (0.035, 0.2, (0.2, 0.36, 0.24)), (0.05, 0.26, (0.3, 0.24, 0.3)), (0.045, 0.22, (0.6, 0.3, 0.16)),
         (0.04, 0.27, (0.16, 0.16, 0.2)), (0.055, 0.24, (0.5, 0.46, 0.42)), (0.04, 0.21, (0.46, 0.14, 0.12)),
         (0.05, 0.25, (0.2, 0.3, 0.4)))
book_z = 1.16
for width, height, col in BOOKS:
    props.box((0.08, 1.45, book_z), (0.25, 1.45 + height, book_z + width), col, skip=("y-",))
    book_z += width + 0.003
props.lathe(0.16, 2.14, [
    (0.05, 0.05, 1.45, 0.0, (0.72, 0.72, 0.78)),
    (0.07, 0.07, 1.58, 0.0, (0.72, 0.72, 0.78)),
    (0.05, 0.05, 1.68, 0.0, (0.62, 0.62, 0.7)),
    (0, 0, 1.66, 0.0, (0.1, 0.1, 0.1)),
], n=8)
for z0, z1, y0, y1 in ((2.5, 2.86, 1.32, 1.8), (2.94, 3.26, 1.42, 1.8)):
    props.box((0.063, y0, z0), (0.082, y1, z1), (0.2, 0.15, 0.1))
    props.box((0.082, y0 + 0.03, z0 + 0.03), (0.097, y1 - 0.03, z1 - 0.03), (0.66, 0.64, 0.56))
    zc = (z0 + z1) / 2
    props.box((0.09, y0 + 0.03, zc - 0.05), (0.111, y0 + 0.24, zc + 0.05), (0.1, 0.1, 0.11))
# Vase with flowers by the window.
props.lathe(0.37, 3.22, [
    (0.07, 0.07, 0.0, 0.0, (0.6, 0.62, 0.72)),
    (0.1, 0.1, 0.14, 0.0, (0.72, 0.74, 0.84)),
    (0.05, 0.05, 0.3, 0.0, (0.68, 0.7, 0.8)),
    (0.065, 0.065, 0.36, 0.0, (0.72, 0.74, 0.84)),
    (0.05, 0.05, 0.36, 0.0, (0.2, 0.22, 0.26)),
    (0, 0, 0.3, 0.0, (0.1, 0.1, 0.12)),
], n=12)
for dx, dz, top, col in ((0.0, 0.0, 0.8, (0.76, 0.34, 0.46)), (0.1, 0.05, 0.72, (0.84, 0.72, 0.42)), (-0.09, 0.04, 0.76, (0.6, 0.5, 0.76)), (0.03, -0.09, 0.68, (0.82, 0.8, 0.74))):
    props.lathe(0.37 + dx, 3.22 + dz, [
        (0.01, 0.01, 0.34, 0.0, (0.18, 0.3, 0.18)),
        (0.008, 0.008, top - 0.02, 0.0, (0.22, 0.38, 0.22)),
        (0, 0, top, 0.0, (0.22, 0.38, 0.22)),
    ], n=4)
    props.lathe(0.37 + dx, 3.22 + dz, [
        (0.02, 0.02, top - 0.03, 0.0, (0.18, 0.3, 0.18)),
        (0.065, 0.065, top + 0.03, 0.0, col),
        (0.05, 0.05, top + 0.07, 0.0, col),
        (0, 0, top + 0.08, 0.0, (col[0] * 0.8, col[1] * 0.7, col[2] * 0.5)),
    ], n=8)
# Slippers left by the bed: in a part with no collider, so nobody trips and climbs on them.
for z, shift in ((-1.0, 0.0), (-1.15, 0.05)):
    Part.parts["Trim_Bedroom"].lathe(2.02 + shift, z, [
        (0.13, 0.052, 0.014, 0.0, (0.3, 0.2, 0.26)),
        (0.125, 0.048, 0.05, 0.0, (0.5, 0.32, 0.42)),
        (0.09, 0.03, 0.06, 0.0, (0.5, 0.32, 0.42)),
        (0, 0, 0.055, 0.0, (0.2, 0.14, 0.16)),
    ], n=8)
# Switch by the door, socket by the console.
props.box((0.063, 1.05, -1.1), (0.08, 1.16, -1.02), (0.85, 0.85, 0.85))
props.box((0.063, 0.28, 0.58), (0.08, 0.36, 0.66), (0.85, 0.85, 0.85))
# ---- kitchen, grey fronts under a dark top
props = Part("Props_Kitchen", material("M_Prop"))
GREY = (0.34, 0.35, 0.37)
FRONT = (0.44, 0.45, 0.47)
UPPER = (0.56, 0.57, 0.58)
UPPER_FRONT = (0.66, 0.67, 0.67)
TOP = (0.20, 0.18, 0.16)
PLINTH = (0.08, 0.08, 0.09)
STEEL = (0.58, 0.6, 0.62)
HANDLE = (0.7, 0.72, 0.74)
KITCHEN_DARK = (0.05, 0.05, 0.06)

# Fridge: freezer below, long handles, a few magnets and a note.
props.box((-3.268, 0.0, 2.568), (-2.584, 1.72, 3.5), (0.5, 0.51, 0.52), skip=("x+",))
props.rect((-2.584, 0.0, 2.568), (-2.584, 0.66, 3.5), (1, 0, 0), (0.42, 0.43, 0.44))
props.rect((-2.584, 0.66, 2.568), (-2.584, 1.72, 3.5), (1, 0, 0), (0.54, 0.55, 0.56))
props.box((-2.6, 0.65, 2.568), (-2.57, 0.67, 3.5), (0.2, 0.2, 0.2))
props.box((-2.584, 0.76, 2.62), (-2.56, 1.3, 2.65), HANDLE)
props.box((-2.584, 0.3, 2.62), (-2.56, 0.58, 2.65), HANDLE)
props.box((-2.592, 1.22, 2.96), (-2.572, 1.42, 3.12), (0.86, 0.84, 0.72))
props.box((-2.592, 1.4, 3.02), (-2.566, 1.44, 3.06), (0.72, 0.16, 0.14))
props.box((-2.592, 1.1, 3.22), (-2.566, 1.16, 3.28), (0.2, 0.42, 0.62))
props.box((-2.592, 1.34, 3.26), (-2.566, 1.4, 3.32), (0.84, 0.66, 0.2))

# Microwave on top: window, buttons, handle.
props.box((-3.2, 1.72, 2.72), (-2.68, 2.0, 3.32), (0.78, 0.78, 0.78))
props.box((-2.69, 1.75, 2.78), (-2.665, 1.97, 3.15), (0.1, 0.1, 0.1))
props.box((-2.69, 1.75, 3.2), (-2.667, 1.97, 3.3), (0.3, 0.3, 0.32))
props.box((-2.69, 1.75, 3.155), (-2.645, 1.97, 3.185), HANDLE)
for y in (1.9, 1.83, 1.77):
    props.box((-2.667, y, 3.22), (-2.654, y + 0.035, 3.28), (0.82, 0.82, 0.8))

# Runs of cabinets on a recessed plinth.
props.box((-3.268, 0.0, 1.0), (-2.77, 0.1, 2.568), PLINTH, skip=("y+", "y-"))
props.box((-3.268, 0.1, 1.0), (-2.72, 0.86, 2.568), GREY, skip=("y+",))
props.box((-3.268, 0.86, 0.99), (-2.68, 0.9, 2.568), TOP)
props.box((-3.268, 0.0, -0.147), (-1.37, 0.1, 0.345), PLINTH, skip=("y+", "y-"))
props.box((-3.268, 0.1, -0.147), (-1.32, 0.86, 0.395), GREY, skip=("y+",))
for z0, z1 in ((1.01, 1.49), (2.31, 2.56)):
    zc = (z0 + z1) / 2
    props.box((-2.72, 0.12, z0), (-2.705, 0.84, z1), FRONT)
    props.box((-2.705, 0.68, zc - 0.07), (-2.683, 0.7, zc + 0.07), HANDLE)
for x0, x1 in ((-2.6, -2.17), (-2.15, -1.74), (-1.72, -1.33)):
    xc = (x0 + x1) / 2
    props.box((x0, 0.12, 0.395), (x1, 0.84, 0.41), FRONT)
    props.box((xc - 0.07, 0.68, 0.41), (xc + 0.07, 0.7, 0.432), HANDLE)

# Oven under the hob, with a towel on its handle.
props.box((-2.72, 0.12, 1.5), (-2.705, 0.84, 2.3), STEEL)
props.box((-2.705, 0.2, 1.58), (-2.692, 0.6, 2.22), KITCHEN_DARK)
props.box((-2.705, 0.65, 1.58), (-2.665, 0.675, 2.22), HANDLE)
for z in (1.62, 1.78, 2.02, 2.18):
    props.box((-2.705, 0.74, z - 0.02), (-2.68, 0.79, z + 0.02), (0.2, 0.2, 0.22))
props.box((-2.664, 0.4, 1.74), (-2.652, 0.68, 1.96), (0.7, 0.34, 0.26))

# The counter top has a real hole with the sink sunk into it.
props.box((-3.268, 0.86, -0.147), (-1.3, 0.9, 0.42), TOP, skip=("y+",))
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
props.box((-1.84, 0.87, 0.09), (-1.76, 0.884, 0.17), KITCHEN_DARK, skip=("y-",))       # drain
# Tall arched tap with a lever.
props.lathe(-1.8, -0.11, [
    (0.03, 0.03, 0.9, 0.0, STEEL),
    (0.018, 0.018, 0.94, 0.0, STEEL),
    (0.014, 0.014, 1.2, 0.0, STEEL),
    (0, 0, 1.2, 0.0, STEEL),
], n=8)
props.box((-1.815, 1.18, -0.125), (-1.785, 1.205, 0.075), STEEL)
props.box((-1.815, 1.13, 0.05), (-1.785, 1.18, 0.075), STEEL)
props.box((-1.875, 0.97, -0.12), (-1.82, 0.985, -0.1), STEEL)

# Things left out on the counter.
props.lathe(-1.4, 0.2, [
    (0.03, 0.03, 0.9, 0.0, (0.26, 0.56, 0.3)),
    (0.03, 0.03, 1.03, 0.0, (0.3, 0.62, 0.34)),
    (0.012, 0.012, 1.06, 0.0, (0.86, 0.86, 0.84)),
    (0, 0, 1.08, 0.0, (0.86, 0.86, 0.84)),
], n=8)
props.box((-1.47, 0.9, -0.06), (-1.37, 0.93, 0.02), (0.82, 0.72, 0.26), skip=("y-",))  # sponge
props.lathe(-2.42, 0.22, [                                                             # mug
    (0.038, 0.038, 0.9, 0.0, (0.86, 0.84, 0.76)),
    (0.042, 0.042, 1.0, 0.0, (0.88, 0.86, 0.78)),
    (0.034, 0.034, 1.0, 0.0, (0.5, 0.42, 0.34)),
    (0, 0, 0.96, 0.0, (0.2, 0.14, 0.1)),
], n=8)
props.box((-2.385, 0.93, 0.21), (-2.36, 0.98, 0.23), (0.86, 0.84, 0.76))
props.box((-2.75, 0.9, -0.125), (-2.38, 1.27, -0.105), (0.62, 0.48, 0.32))             # cutting board
props.box((-3.2, 0.9, -0.1), (-3.06, 1.12, 0.06), (0.3, 0.22, 0.16))                   # knife block
for k, z in enumerate((-0.07, -0.02, 0.03)):
    props.box((-3.16, 1.12, z - 0.012), (-3.1, 1.2, z + 0.012), (0.1, 0.1, 0.1))
# Pot and pan on the hob.
props.lathe(-2.96, 1.72, [
    (0.1, 0.1, 0.918, 0.0, STEEL),
    (0.105, 0.105, 1.05, 0.0, STEEL),
    (0.108, 0.108, 1.06, 0.0, (0.66, 0.68, 0.7)),
    (0.03, 0.03, 1.09, 0.0, (0.66, 0.68, 0.7)),
    (0.015, 0.015, 1.12, 0.0, (0.12, 0.12, 0.12)),
    (0, 0, 1.125, 0.0, (0.12, 0.12, 0.12)),
], n=12)
props.lathe(-2.96, 2.08, [
    (0.09, 0.09, 0.918, 0.0, (0.14, 0.14, 0.15)),
    (0.115, 0.115, 0.965, 0.0, (0.16, 0.16, 0.17)),
    (0.105, 0.105, 0.965, 0.0, (0.1, 0.1, 0.11)),
    (0, 0, 0.93, 0.0, (0.08, 0.08, 0.09)),
], n=12)
props.box((-2.85, 0.95, 2.065), (-2.62, 0.97, 2.095), (0.12, 0.12, 0.12))
# Detergent on the washing machine.
props.lathe(-3.0, 0.7, [
    (0.055, 0.055, 0.84, 0.0, (0.2, 0.34, 0.62)),
    (0.055, 0.055, 1.02, 0.0, (0.24, 0.4, 0.7)),
    (0.022, 0.022, 1.05, 0.0, (0.8, 0.8, 0.8)),
    (0, 0, 1.07, 0.0, (0.8, 0.8, 0.8)),
], n=8)

# Tiled splashback along both walls, tile by tile.
for i in range(9):
    for j in range(2):
        shade = 1.0 if (i + j) % 2 else 0.86
        tile = (0.3 * shade, 0.32 * shade, 0.34 * shade)
        z0, z1 = -0.135 + i * 0.3, min(2.568, -0.135 + (i + 1) * 0.3)
        props.rect((-3.255, 0.9 + j * 0.3, z0), (-3.255, 1.2 + j * 0.3, z1), (1, 0, 0), tile)
for i in range(7):
    for j in range(2):
        shade = 1.0 if (i + j) % 2 else 0.86
        tile = (0.3 * shade, 0.32 * shade, 0.34 * shade)
        x0, x1 = -3.255 + i * 0.3, min(-1.32, -3.255 + (i + 1) * 0.3)
        props.rect((x0, 0.9 + j * 0.3, -0.135), (x1, 1.2 + j * 0.3, -0.135), (0, 0, 1), tile)

# Wall cabinets over the sink and in the corner.
props.box((-3.268, 1.55, -0.147), (-1.32, 2.3, 0.16), UPPER)
for x0, x1 in ((-3.25, -2.78), (-2.76, -2.29), (-2.27, -1.81), (-1.79, -1.34)):
    xc = (x0 + x1) / 2
    props.box((x0, 1.57, 0.16), (x1, 2.28, 0.172), UPPER_FRONT)
    props.box((xc - 0.05, 1.61, 0.172), (xc + 0.05, 1.625, 0.19), HANDLE)
props.box((-3.268, 1.55, 0.16), (-2.96, 2.3, 0.85), UPPER)
props.box((-2.96, 1.57, 0.18), (-2.948, 2.28, 0.83), UPPER_FRONT)
props.box((-2.948, 1.61, 0.46), (-2.93, 1.625, 0.56), HANDLE)

# Shelf on brackets, and an extractor hood over the hob.
props.box((-3.268, 1.58, 0.9), (-3.0, 1.61, 2.5), (0.42, 0.34, 0.26))
for z in (1.05, 2.3):
    props.box((-3.255, 1.47, z), (-3.22, 1.58, z + 0.03), (0.2, 0.2, 0.2))
props.box((-3.268, 1.86, 1.55), (-2.82, 1.96, 2.25), STEEL)
props.box((-3.268, 1.96, 1.75), (-3.05, H, 2.05), STEEL)

# Heating radiator under the window, section by section, and its pipe.
RADIATOR = (0.82, 0.82, 0.78)
for i in range(10):
    x0 = -2.25 + i * 0.128
    props.box((x0, 0.14, 3.47), (x0 + 0.11, 0.72, 3.555), RADIATOR, skip=("z+",))
props.box((-2.42, 0.2, 3.495), (-0.97, 0.228, 3.525), RADIATOR)

# Stools: a round seat on three legs.
for z in (1.16, 2.62):
    for dx, dz in ((-0.11, -0.09), (0.11, -0.09), (0.0, 0.13)):
        props.box((-0.55 + dx - 0.014, 0.0, z + dz - 0.014), (-0.55 + dx + 0.014, 0.44, z + dz + 0.014), (0.14, 0.14, 0.15), skip=("y+", "y-"))
    props.lathe(-0.55, z, [
        (0.16, 0.16, 0.44, 0.0, (0.54, 0.45, 0.28)),
        (0.17, 0.17, 0.465, 0.0, (0.72, 0.62, 0.38)),
        (0.15, 0.15, 0.485, 0.0, (0.76, 0.66, 0.42)),
        (0, 0, 0.49, 0.0, (0.76, 0.66, 0.42)),
    ], n=12)
# ---- bathroom
props = Part("Props_Bath", material("M_Prop"))
ENAMEL = (0.9, 0.9, 0.88)
ENAMEL_IN = (0.8, 0.82, 0.83)
ENAMEL_LOW = (0.62, 0.65, 0.67)
CHROME = (0.56, 0.58, 0.6)
DARK = (0.06, 0.06, 0.07)

# Bathtub: panel in front, the top a single rim that curves down into the basin.
props.box((-3.26, 0.0, -1.30), (-1.52, 0.55, -0.60), (0.78, 0.78, 0.76), skip=("y+",))
props.lathe(-2.39, -0.95, [
    (0.87, 0.35, 0.55, 1.0, ENAMEL),
    (0.80, 0.28, 0.565, 0.6, ENAMEL),
    (0.76, 0.24, 0.54, 0.35, ENAMEL_IN),
    (0.72, 0.21, 0.30, 0.3, ENAMEL_IN),
    (0.60, 0.14, 0.19, 0.15, ENAMEL_LOW),
    (0.05, 0.05, 0.18, 0.0, ENAMEL_LOW),
    (0.025, 0.025, 0.178, 0.0, DARK),
    (0, 0, 0.178, 0.0, DARK),
], first="up", n=16)
# Taps, hose and shower head on the end wall.
props.box((-3.268, 0.70, -1.06), (-3.25, 0.80, -0.90), CHROME)
props.box((-3.25, 0.72, -1.00), (-3.06, 0.75, -0.96), CHROME)
props.box((-3.25, 0.78, -1.07), (-3.20, 0.83, -1.03), CHROME)
props.box((-3.25, 0.78, -0.93), (-3.20, 0.83, -0.89), CHROME)
props.box((-3.255, 0.80, -0.99), (-3.235, 1.92, -0.97), CHROME)
props.box((-3.255, 1.92, -0.99), (-3.12, 1.945, -0.97), CHROME)
props.lathe(-3.13, -0.98, [
    (0.02, 0.02, 1.95, 0.0, CHROME),
    (0.08, 0.08, 1.90, 0.0, CHROME),
    (0.075, 0.075, 1.88, 0.0, (0.34, 0.35, 0.36)),
    (0, 0, 1.88, 0.0, (0.2, 0.2, 0.22)),
], n=8)
# Shower curtain on a rod, half drawn: you can't see the end of the tub behind it.
props.box((-3.26, 2.02, -1.215), (-1.52, 2.04, -1.195), CHROME)
for i in range(16):
    x0, x1 = -3.24 + i * 0.055, -3.24 + (i + 1) * 0.055
    z0, z1 = (-1.19, -1.22) if i % 2 else (-1.22, -1.19)
    shade = 0.82 if i % 2 else 1.0
    tint = (0.62 * shade, 0.68 * shade, 0.66 * shade)
    props.quad([(x0, 0.6, z0), (x1, 0.6, z1), (x1, 2.02, z1), (x0, 2.02, z0)], (0, 0, -1), color=tint)

# Vanity: a cabinet on a dark plinth, two doors, and a top with the basin sunk into it.
CABINET = (0.76, 0.74, 0.68)
props.box((-3.268, 0.0, -2.16), (-2.84, 0.08, -1.44), (0.14, 0.13, 0.12))
props.box((-3.268, 0.08, -2.18), (-2.80, 0.82, -1.42), CABINET, skip=("y+",))   # open on top: the basin sinks into it
for z0, z1, handle in ((-2.165, -1.81, -1.85), (-1.79, -1.435, -1.75)):
    props.box((-2.80, 0.11, z0), (-2.782, 0.79, z1), (0.86, 0.84, 0.78))
    props.box((-2.782, 0.58, handle - 0.012), (-2.762, 0.72, handle + 0.012), CHROME)
props.box((-3.268, 0.82, -2.22), (-2.775, 0.86, -1.38), ENAMEL, skip=("y+",))
props.lathe(-3.0215, -1.8, [
    (0.2465, 0.42, 0.86, 1.0, ENAMEL),
    (0.18, 0.26, 0.865, 0.2, ENAMEL),
    (0.16, 0.235, 0.84, 0.1, ENAMEL_IN),
    (0.11, 0.16, 0.79, 0.0, ENAMEL_IN),
    (0.05, 0.06, 0.77, 0.0, ENAMEL_LOW),
    (0.035, 0.035, 0.768, 0.0, DARK),
    (0, 0, 0.768, 0.0, DARK),
], first="up", n=16)
props.box((-3.25, 0.865, -1.83), (-3.215, 0.98, -1.77), CHROME)        # tap
props.box((-3.215, 0.95, -1.815), (-3.06, 0.975, -1.785), CHROME)
props.box((-3.255, 0.98, -1.815), (-3.21, 1.0, -1.785), CHROME)
props.lathe(-3.19, -1.5, [                                             # cup with toothbrushes
    (0.03, 0.03, 0.865, 0.0, (0.36, 0.5, 0.62)),
    (0.038, 0.038, 0.97, 0.0, (0.42, 0.56, 0.68)),
    (0.03, 0.03, 0.97, 0.0, (0.2, 0.28, 0.34)),
    (0, 0, 0.93, 0.0, (0.1, 0.14, 0.18)),
], n=8)
props.box((-3.2, 0.93, -1.51), (-3.19, 1.08, -1.5), (0.72, 0.24, 0.2))
props.box((-3.19, 0.93, -1.495), (-3.18, 1.06, -1.485), (0.24, 0.54, 0.36))

# Mirror frame, shelf and light. The glass itself is the Mirror part.
for lo, hi in (((-3.268, 1.025, -2.225), (-3.235, 1.05, -1.375)), ((-3.268, 1.75, -2.225), (-3.235, 1.775, -1.375)),
               ((-3.268, 1.05, -2.225), (-3.235, 1.75, -2.2)), ((-3.268, 1.05, -1.4), (-3.235, 1.75, -1.375))):
    props.box(lo, hi, CHROME)
props.box((-3.268, 0.98, -2.1), (-3.16, 1.0, -1.5), (0.74, 0.78, 0.78))
props.lathe(-3.215, -1.95, [
    (0.032, 0.032, 1.0, 0.0, (0.76, 0.5, 0.56)),
    (0.032, 0.032, 1.11, 0.0, (0.76, 0.5, 0.56)),
    (0.012, 0.012, 1.14, 0.0, (0.9, 0.9, 0.88)),
    (0, 0, 1.15, 0.0, (0.9, 0.9, 0.88)),
], n=8)
props.lathe(-3.215, -1.68, [
    (0.026, 0.026, 1.0, 0.0, (0.84, 0.82, 0.62)),
    (0.026, 0.026, 1.09, 0.0, (0.84, 0.82, 0.62)),
    (0.01, 0.01, 1.11, 0.0, (0.3, 0.45, 0.6)),
    (0, 0, 1.12, 0.0, (0.3, 0.45, 0.6)),
], n=8)
props.box((-3.268, 1.84, -2.08), (-3.2, 1.9, -1.52), (1.0, 0.98, 0.9))

# Toilet: tank with a lid and a button, a turned bowl with a seat, and the lid raised.
props.box((-3.25, 0.42, -2.84), (-3.03, 0.82, -2.46), ENAMEL)
props.box((-3.26, 0.82, -2.86), (-3.02, 0.85, -2.44), (0.94, 0.94, 0.92))
props.box((-3.17, 0.85, -2.69), (-3.09, 0.865, -2.61), CHROME)
props.box((-3.06, 0.2, -2.74), (-2.95, 0.42, -2.56), ENAMEL)
SEAT = (0.96, 0.95, 0.9)
props.lathe(-2.78, -2.65, [
    (0.15, 0.13, 0.0, 0.0, (0.82, 0.82, 0.8)),
    (0.13, 0.11, 0.12, 0.0, ENAMEL),
    (0.2, 0.16, 0.27, 0.0, ENAMEL),
    (0.26, 0.19, 0.37, 0.0, ENAMEL),
    (0.265, 0.195, 0.395, 0.0, SEAT),
    (0.255, 0.185, 0.425, 0.0, SEAT),
    (0.19, 0.125, 0.425, 0.0, SEAT),
    (0.17, 0.11, 0.395, 0.0, ENAMEL_IN),
    (0.11, 0.075, 0.30, 0.0, ENAMEL_LOW),
    (0.07, 0.05, 0.27, 0.0, (0.24, 0.34, 0.36)),
    (0, 0, 0.27, 0.0, (0.2, 0.3, 0.32)),
], n=12)
props.box((-3.015, 0.43, -2.82), (-2.99, 0.84, -2.48), SEAT)
props.lathe(-3.15, -2.52, [                                            # spare roll on the tank
    (0.05, 0.05, 0.85, 0.0, (0.92, 0.92, 0.88)),
    (0.05, 0.05, 0.955, 0.0, (0.92, 0.92, 0.88)),
    (0.018, 0.018, 0.955, 0.0, (0.45, 0.38, 0.28)),
    (0, 0, 0.92, 0.0, (0.2, 0.17, 0.12)),
], n=8)
props.lathe(-3.16, -2.94, [                                            # brush in its holder
    (0.05, 0.05, 0.0, 0.0, (0.8, 0.8, 0.78)),
    (0.055, 0.055, 0.22, 0.0, (0.86, 0.86, 0.84)),
    (0.018, 0.018, 0.24, 0.0, (0.5, 0.5, 0.5)),
    (0.012, 0.012, 0.44, 0.0, CHROME),
    (0, 0, 0.45, 0.0, CHROME),
], n=8)

# The riser every flat has in the corner, a heated towel rail, a towel, a bin and the vent.
props.lathe(-3.225, -2.985, [
    (0.028, 0.028, 0.0, 0.0, (0.7, 0.7, 0.68)),
    (0.028, 0.028, H, 0.0, (0.7, 0.7, 0.68)),
], n=8)
for x in (-2.32, -1.78):
    props.box((x - 0.012, 0.92, -3.026), (x + 0.012, 1.56, -2.97), CHROME)
for y in (1.0, 1.25, 1.5):
    props.box((-2.32, y - 0.012, -2.985), (-1.78, y + 0.012, -2.96), CHROME)
TOWEL = (0.34, 0.5, 0.5)
towel_rows = []
for y, band in ((1.53, 1.0), (1.4, 1.0), (1.2, 1.0), (1.0, 1.0), (0.88, 1.0), (0.85, 1.35), (0.78, 1.35)):
    row = []
    for k, x in enumerate((-2.24, -2.16, -2.08, -2.0, -1.92, -1.84)):
        fold = 0.9 if k % 2 else 1.05
        z = -2.945 + (0.012 if k % 2 else 0.0)
        row.append(((x, y, z), (0, 0), (TOWEL[0] * fold * band, TOWEL[1] * fold * band, TOWEL[2] * fold * band)))
    towel_rows.append(row)
props.surface(towel_rows, (-2.04, 1.15, -3.2))
props.lathe(-1.74, -2.83, [
    (0.085, 0.085, 0.0, 0.0, (0.2, 0.2, 0.22)),
    (0.11, 0.11, 0.3, 0.0, (0.26, 0.26, 0.28)),
    (0.1, 0.1, 0.3, 0.0, (0.14, 0.14, 0.15)),
    (0.09, 0.09, 0.06, 0.0, DARK),
    (0, 0, 0.06, 0.0, DARK),
], n=8)
props.box((-3.268, 2.2, -2.2), (-3.25, 2.45, -1.95), (0.72, 0.72, 0.7))
for y in (2.24, 2.29, 2.34, 2.39):
    props.box((-3.26, y, -2.17), (-3.235, y + 0.02, -1.98), (0.3, 0.3, 0.3))
# ---- hall: a switch and a small picture
props = Part("Props_Hall", material("M_Prop"))
# An old red phone on the wall, its cord hanging down.
phone = Part("Phone", material("M_Prop"))
PHONE_RED = (0.55, 0.12, 0.1)
phone.box((-1.358, 1.15, -0.84), (-1.3, 1.36, -0.64), PHONE_RED, skip=("x-",))
phone.box((-1.3, 1.31, -0.87), (-1.255, 1.36, -0.61), (0.42, 0.08, 0.07), skip=("x-",))
phone.box((-1.3, 1.29, -0.88), (-1.262, 1.31, -0.84), (0.42, 0.08, 0.07))
phone.box((-1.3, 1.29, -0.64), (-1.262, 1.31, -0.6), (0.42, 0.08, 0.07))
phone.box((-1.3, 1.19, -0.79), (-1.288, 1.27, -0.69), (0.86, 0.84, 0.78), skip=("x-",))
phone.box((-1.288, 1.225, -0.745), (-1.282, 1.235, -0.735), (0.1, 0.1, 0.1))
phone.box((-1.29, 0.8, -0.875), (-1.28, 1.29, -0.865), (0.2, 0.06, 0.05))
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
# The left one starts at the fridge's front, not inside the fridge.
curtain(kcur, -2.56, -2.3, CURTAIN_Z, 0.03, 2.45, folds=2)
curtain(kcur, -0.84, -0.2, CURTAIN_Z, 0.03, 2.45)
ktul = Part("Tulle_Kitchen", material("M_Tulle"))
curtain(ktul, -2.5, -0.62, TULLE_Z, 0.88, 2.45, folds=8, depth=0.02)   # short: ends just above the sill

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
mirror.rect((-3.25, 1.05, -2.2), (-3.25, 1.75, -1.4), (1, 0, 0), uv="fill")

table = Part("Table_Items", material("M_Prop"))
KETTLE = (0.84, 0.84, 0.82)
table.lathe(-0.22, 2.27, [                                                # stand
    (0.1, 0.1, 0.76, 0.0, (0.1, 0.1, 0.11)),
    (0.1, 0.1, 0.778, 0.0, (0.14, 0.14, 0.15)),
    (0.085, 0.085, 0.778, 0.0, (0.14, 0.14, 0.15)),
    (0.09, 0.09, 0.8, 0.0, KETTLE),                                       # kettle
    (0.082, 0.082, 0.92, 0.0, KETTLE),
    (0.05, 0.05, 0.97, 0.0, (0.78, 0.78, 0.76)),
    (0.055, 0.055, 0.98, 0.0, (0.2, 0.2, 0.22)),
    (0.015, 0.015, 0.985, 0.0, (0.2, 0.2, 0.22)),
    (0.012, 0.012, 1.0, 0.0, (0.12, 0.12, 0.13)),
    (0, 0, 1.005, 0.0, (0.12, 0.12, 0.13)),
], n=12)
table.box((-0.335, 0.82, 2.26), (-0.315, 0.96, 2.28), (0.12, 0.12, 0.13))  # handle
table.box((-0.335, 0.96, 2.26), (-0.26, 0.98, 2.28), (0.12, 0.12, 0.13))
table.box((-0.335, 0.8, 2.26), (-0.29, 0.82, 2.28), (0.12, 0.12, 0.13))
table.box((-0.155, 0.9, 2.25), (-0.095, 0.93, 2.29), KETTLE)              # spout
table.lathe(-0.86, 1.57, [                                                # pot plant
    (0.05, 0.05, 0.76, 0.0, (0.5, 0.3, 0.2)),
    (0.07, 0.07, 0.87, 0.0, (0.58, 0.34, 0.22)),
    (0.06, 0.06, 0.87, 0.0, (0.2, 0.14, 0.1)),
    (0, 0, 0.85, 0.0, (0.1, 0.07, 0.05)),
], n=8)
for dx, dz, top, tone in ((0.0, 0.0, 1.14, 0.42), (0.03, 0.02, 1.08, 0.5), (-0.03, 0.02, 1.05, 0.46), (0.02, -0.03, 1.02, 0.38), (-0.02, -0.03, 1.1, 0.34)):
    table.lathe(-0.86 + dx, 1.57 + dz, [
        (0.018, 0.018, 0.85, 0.0, (0.12, 0.26, 0.14)),
        (0.016, 0.016, (0.85 + top) / 2, 0.0, (0.18, tone, 0.2)),
        (0, 0, top, 0.0, (0.22, tone + 0.1, 0.24)),
    ], n=4)

# ---- the kitchen computer: an old beige CRT, keyboard and mouse, the tower under the table
pc = Part("Computer", material("M_Prop"))
BEIGE = (0.78, 0.75, 0.66)
BEIGE_DARK = (0.62, 0.59, 0.52)
pc.box((-0.6, 0.76, 1.56), (-0.4, 0.775, 1.76), BEIGE_DARK, skip=("y-",))
pc.box((-0.53, 0.775, 1.6), (-0.47, 0.8, 1.72), BEIGE_DARK, skip=("y-",))
pc.box((-0.7, 0.8, 1.52), (-0.3, 1.13, 1.86), BEIGE)
pc.box((-0.63, 0.84, 1.42), (-0.37, 1.09, 1.52), BEIGE_DARK, skip=("z+",))
pc.box((-0.67, 0.83, 1.86), (-0.33, 1.1, 1.872), (0.04, 0.045, 0.05), skip=("z-",))
pc.box((-0.345, 0.808, 1.86), (-0.33, 0.818, 1.868), (0.2, 0.75, 0.3), skip=("z-",))
pc.box((-0.68, 0.76, 1.96), (-0.32, 0.785, 2.11), BEIGE, skip=("y-",))
pc.box((-0.665, 0.785, 1.975), (-0.335, 0.797, 2.095), (0.52, 0.5, 0.45), skip=("y-",))
pc.box((-0.27, 0.76, 1.98), (-0.22, 0.785, 2.06), BEIGE, skip=("y-",))
pc.box((-0.42, 0.0, 1.6), (-0.22, 0.42, 2.0), BEIGE, skip=("y-",))
pc.box((-0.432, 0.34, 1.68), (-0.42, 0.36, 1.92), (0.12, 0.12, 0.12), skip=("x+",))
pc.box((-0.432, 0.26, 1.76), (-0.42, 0.29, 1.84), BEIGE_DARK, skip=("x+",))
pc.box((-0.432, 0.1, 1.86), (-0.42, 0.13, 1.89), (0.2, 0.75, 0.3), skip=("x+",))
# The picture itself, clear of the glass. 16:9, like the camera's photos.
screen = Part("Computer_Screen", material("M_Screen"))
screen.rect((-0.655, 0.878, 1.885), (-0.345, 1.052, 1.885), (0, 0, 1), uv="fill")

shelf = Part("Shelf_Items", material("M_Prop"))
RED = (0.56, 0.12, 0.1)
shelf.lathe(-3.11, 1.64, [                                                # red pot
    (0.1, 0.1, 1.61, 0.0, (0.4, 0.08, 0.07)),
    (0.105, 0.105, 1.73, 0.0, RED),
    (0.11, 0.11, 1.74, 0.0, (0.46, 0.1, 0.08)),
    (0.03, 0.03, 1.765, 0.0, RED),
    (0.016, 0.016, 1.79, 0.0, (0.1, 0.1, 0.1)),
    (0, 0, 1.795, 0.0, (0.1, 0.1, 0.1)),
], n=12)
for z, top, glass, lid in ((1.19, 1.78, (0.78, 0.68, 0.36), (0.8, 0.8, 0.78)), (1.33, 1.74, (0.45, 0.55, 0.6), (0.3, 0.3, 0.32))):
    shelf.lathe(-3.15, z, [                                               # jars
        (0.05, 0.05, 1.61, 0.0, glass),
        (0.05, 0.05, top - 0.03, 0.0, glass),
        (0.04, 0.04, top - 0.02, 0.0, glass),
        (0.042, 0.042, top, 0.0, lid),
        (0, 0, top, 0.0, lid),
    ], n=8)


# ---------------------------------------------------------------- the woman
# Last tenant of this flat. Faces +Z. One atlas, T_Figure: left half cloth, top right hair, bottom right face and skin.
SKIN_UV = (0.52, 0.02)


def build_woman(part, ox, oz, pale=1.0):
    def place(v):
        return (ox + v[0], v[1], oz + v[2])

    def add(a, b, t=1.0):
        return (a[0] + b[0] * t, a[1] + b[1] * t, a[2] + b[2] * t)

    def tint(c, k=1.0):
        return (c[0] * pale * k, c[1] * pale * k, c[2] * pale * k)

    def ring(center, ax, ay, n, color, uv=SKIN_UV):
        """n+1 points, starting at -ay: on the body that is the back, where the seam belongs."""
        out = []
        for i in range(n + 1):
            a = -math.pi / 2 + 2 * math.pi * i / n
            out.append((place(add(add(center, ax, math.cos(a)), ay, math.sin(a))), uv, color))
        return out

    def limb(points, n, color_of, flat=1.0, end=True):
        """A thin tube along points = (center, radius)."""
        rows, centers = [], []
        for j, (c, r) in enumerate(points):
            rows.append(ring(c, (r, 0, 0), (0, 0, r * flat), n, color_of(j)))
            centers.append(place(c))
        verts = part.loft(rows, centers, wrap=True)
        if end:
            part.cap(verts[-1], place(add(points[-1][0], (0, -points[-1][1], 0))), SKIN_UV, color_of(len(points) - 1), centers[-2])

    # --- Dress: a thin nightgown, the folds fading out towards the hips.
    FOLDS = {0.1: 0.1, 0.22: 0.08, 0.42: 0.05, 0.62: 0.025}
    dress = [(0.1, 0.25, 0.2, 0.012), (0.22, 0.235, 0.18, 0.01), (0.42, 0.205, 0.155, 0.006), (0.62, 0.18, 0.135, 0.003),
             (0.8, 0.165, 0.12, 0.0), (0.97, 0.125, 0.092, 0.0), (1.14, 0.14, 0.1, 0.008), (1.27, 0.155, 0.1, 0.012),
             (1.36, 0.16, 0.08, 0.005), (1.42, 0.08, 0.06, 0.008)]
    rows, centers = [], []
    n = 14
    for y, rx, rz, zc in dress:
        row = []
        for i in range(n + 1):
            a = -math.pi / 2 + 2 * math.pi * i / n
            ripple = 1 + FOLDS.get(y, 0.0) * math.sin(5 * a + y * 4)
            hem = 0.018 * math.sin(7 * a + 1.0) if y == 0.1 else 0.0
            # the shoulders sit crooked
            lean = 0.03 * (y - 0.9) * math.cos(a) if y > 1.2 else 0.0
            shade = 1 - 0.14 * max(0.0, math.sin(5 * a + y * 4)) * (FOLDS.get(y, 0.0) * 10)
            row.append((place((rx * ripple * math.cos(a), y + hem + lean, zc + rz * ripple * math.sin(a))),
                        (0.49 * i / n + 0.005, min(0.99, y / 1.45)), tint((1, 1, 1), shade)))
        rows.append(row)
        centers.append(place((0, y, zc)))
    verts = part.loft(rows, centers, wrap=True)
    part.cap(verts[0], place((0, 0.1, 0.012)), (0.25, 0.02), (0.1, 0.1, 0.1), place((0, 0.7, 0)))
    part.cap(verts[-1], place((0, 1.43, 0.008)), SKIN_UV, tint((0.7, 0.72, 0.7)), place((0, 1.2, 0)))

    # --- Legs and bare feet under the hem.
    SK = tint((1, 1, 1))
    for side in (-1, 1):
        lx = side * 0.075
        limb([((lx, 0.3, 0.0), 0.03), ((lx, 0.1, 0.0), 0.026), ((lx, 0.045, 0.005), 0.03)], 6, lambda j: SK, end=False)
        foot = []
        centers = []
        for z, w, h, tone in ((-0.04, 0.026, 0.024, 1.0), (0.03, 0.033, 0.03, 1.0), (0.11, 0.038, 0.017, 0.95), (0.16, 0.03, 0.009, 0.7)):
            c = (lx + side * 0.01, 0.002 + h, z)
            foot.append(ring(c, (w, 0, 0), (0, h, 0), 6, tint((1, 1, 1), tone)))
            centers.append(place(c))
        v = part.loft(foot, centers, wrap=True)
        part.cap(v[0], place((lx + side * 0.01, 0.026, -0.055)), SKIN_UV, SK, place((lx, 0.03, 0.05)))
        part.cap(v[-1], place((lx + side * 0.01, 0.008, 0.175)), SKIN_UV, tint((0.5, 0.42, 0.42)), place((lx, 0.02, 0.05)))

    # --- Arms hanging too long, hands past the hips. The nails and fingertips are torn.
    for side, drop in ((-1, 0.0), (1, 0.04)):
        wrist = (side * 0.232, 0.6 - drop, 0.03)
        limb([((side * 0.125, 1.33, 0.0), 0.034), ((side * 0.18, 1.12, -0.008), 0.03), ((side * 0.21, 0.95, -0.004), 0.027),
              ((side * 0.222, 0.78, 0.012), 0.024), (wrist, 0.018)], 6, lambda j: tint((1, 1, 1), 1 if j < 4 else 0.94), end=False)
        palm = []
        centers = []
        for dy, w, t in ((0.0, 0.019, 0.015), (0.05, 0.033, 0.013), (0.09, 0.033, 0.011)):
            c = add(wrist, (0, -dy, 0.005))
            palm.append(ring(c, (w, 0, 0), (0, 0, t), 6, tint((1, 1, 1), 0.92)))
            centers.append(place(c))
        v = part.loft(palm, centers, wrap=True)
        base = add(wrist, (0, -0.09, 0.005))
        part.cap(v[-1], place(add(base, (0, -0.005, 0))), SKIN_UV, tint((1, 1, 1), 0.9), place(wrist))
        for k, length in enumerate((0.13, 0.15, 0.145, 0.115)):
            fx = (k - 1.5) * 0.019
            f0 = add(base, (fx, 0.003, 0))
            f1 = add(f0, (fx * 0.15, -length * 0.5, 0.012))
            f2 = add(f0, (fx * 0.3, -length, 0.03))
            limb([(f0, 0.0085), (f1, 0.0075), (f2, 0.005)], 3,
                 lambda j: tint((1, 1, 1), 0.95) if j < 2 else (0.3, 0.05, 0.04))
        t0 = add(wrist, (-side * 0.028, -0.035, 0.012))
        t2 = add(t0, (-side * 0.012, -0.085, 0.02))
        limb([(t0, 0.009), (add(t0, (-side * 0.006, -0.042, 0.01)), 0.008), (t2, 0.005)], 3,
             lambda j: tint((1, 1, 1), 0.95) if j < 2 else (0.3, 0.05, 0.04))

    # --- Neck and bowed head: tipped forward and over to one side.
    HEAD = (0.03, 1.585, 0.05)
    bow, roll = math.radians(24), math.radians(-11)

    def in_head(x, y, z):
        y1 = y * math.cos(bow) - z * math.sin(bow)
        z1 = y * math.sin(bow) + z * math.cos(bow)
        x2 = x * math.cos(roll) - y1 * math.sin(roll)
        y2 = x * math.sin(roll) + y1 * math.cos(roll)
        return (HEAD[0] + x2, HEAD[1] + y2, HEAD[2] + z1)

    limb([((0.0, 1.39, 0.005), 0.042), ((0.012, 1.46, 0.015), 0.036), (in_head(0, -0.09, -0.015), 0.036)], 6, lambda j: tint((1, 1, 1), 0.86), end=False)
    RX, RY, RZ = 0.088, 0.122, 0.098
    n = 10
    rows, centers = [], []
    for lat in (-78, -52, -26, 0, 26, 52, 76):
        la = math.radians(lat)
        ly = math.sin(la) * RY
        k = math.cos(la)
        # a narrow jaw
        jaw = 1 - 0.28 * max(0.0, -ly / RY)
        row = []
        for i in range(n + 1):
            a = -math.pi / 2 + 2 * math.pi * i / n
            lx = RX * k * jaw * math.cos(a)
            lz = RZ * k * math.sin(a)
            uv = (0.75 + 0.24 * max(-1.0, min(1.0, lx / RX)), 0.25 + 0.24 * ly / RY)
            row.append((place(in_head(lx, ly, lz)), uv, tint((1, 1, 1))))
        rows.append(row)
        centers.append(place(in_head(0, ly, 0)))
    verts = part.loft(rows, centers, wrap=True)
    middle = place(HEAD)
    part.cap(verts[0], place(in_head(0, -RY, 0)), SKIN_UV, tint((0.8, 0.8, 0.8)), middle)
    part.cap(verts[-1], place(in_head(0, RY, 0)), SKIN_UV, tint((0.8, 0.8, 0.8)), middle)

    # --- Hair: over the skull, then straight down to the waist. It parts over one side of the face,
    # so you see an eye and half the mouth, and from every other side nothing at all.
    n = 18
    PART_AT = math.pi / 2 + 0.34
    HAIR_DIM = (0.3, 0.3, 0.32, 0.5, 0.8, 1, 1, 1, 1, 1)
    # (center, half width, half depth, half the gap in radians)
    fall = []
    for lat, gap in ((72, 0.08), (50, 0.16), (22, 0.27), (-8, 0.42), (-38, 0.46)):
        la = math.radians(lat)
        fall.append((in_head(0, math.sin(la) * RY * 1.08, -0.008), RX * math.cos(la) * 1.2 + 0.006, RZ * math.cos(la) * 1.2 + 0.006, gap))
    fall += [((0.02, 1.43, 0.012), 0.125, 0.105, 0.42), ((0.012, 1.3, 0.008), 0.178, 0.112, 0.42), ((0.006, 1.12, 0.004), 0.15, 0.108, 0.44),
             ((0.0, 0.96, 0.0), 0.128, 0.098, 0.48), ((0.0, 0.84, -0.004), 0.118, 0.09, 0.52)]
    fall.reverse()
    rows, centers = [], []
    for j, (c, hx, hz, gap) in enumerate(fall):
        row = []
        for i in range(n + 1):
            uneven = gap * (1 + 0.2 * math.sin(j * 2.1))
            a = PART_AT + uneven + (2 * math.pi - 2 * uneven) * i / n
            sway = 0.01 * math.sin(i * 2.3 + j) if j < 5 else 0.0
            row.append((place(add(c, (hx * math.cos(a) + sway, 0, hz * math.sin(a)))), (0.505 + 0.485 * i / n, 0.505 + 0.49 * j / (len(fall) - 1)), (HAIR_DIM[j],) * 3))
        rows.append(row)
        centers.append(place(c))
    verts = part.loft(rows, centers, wrap=False)
    crown = in_head(0, RY * 1.22, -0.008)
    tip = part.bm.verts.new(to_blender(place(crown)))
    away = to_blender(place(HEAD))
    top = verts[-1]
    for i in range(len(top)):
        face = part.bm.faces.new([top[i], top[(i + 1) % len(top)], tip])
        face.smooth = True
        face.normal_update()
        if face.normal.dot(face.calc_center_median() - away) < 0:
            face.normal_flip()
        for loop in face.loops:
            loop[part.uv].uv = (0.75, 0.97)
            loop[part.col] = (1, 1, 1, 1)


build_woman(Part("Figure_Corner", material("M_Figure")), -0.42, -3.35, pale=0.86)   # clear of the hall wardrobe
build_woman(Part("Figure_Lens", material("M_Figure")), 0.0, 0.0, pale=1.0)

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
    wanted = ["Safe", "Poster", "Window_Ghost", "Prints_1", "Prints_2", "Prints_3", "Door_Void", "Door_Face",
              "Door_Fingers", "Futon_Hair", "Futon_Hand"]
    dst.objects = [n for n in src.objects if n in wanted]

# name: (turn on the plan in degrees, dx, dy, dz) applied in Unity space, about the old room's origin.
# A turn of 90 sends the old east-facing door onto the new north-facing entrance.
MOVES = {
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
