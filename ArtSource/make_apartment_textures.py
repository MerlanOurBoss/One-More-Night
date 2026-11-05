# Low-res textures for the Kazakh apartment, painted by code in the style of the user's reference photos.
# blender --background --factory-startup --python make_apartment_textures.py
import os
import bpy
import numpy as np

OUT = r"F:\Work KZ\One More Night\Assets\Art\Textures"
rng = np.random.default_rng(1011)


def save(name, rgb, alpha=None, levels=None):
    rgb = np.clip(rgb, 0, 1)
    if levels:
        rgb = np.round(rgb * levels) / levels
    h, w, _ = rgb.shape
    a = np.ones((h, w)) if alpha is None else alpha
    rgba = np.dstack([rgb, a]).astype(np.float32)
    im = bpy.data.images.new(name, w, h, alpha=True)
    im.pixels.foreach_set(rgba.ravel())
    im.filepath_raw = os.path.join(OUT, name + ".png")
    im.file_format = 'PNG'
    im.save()
    bpy.data.images.remove(im)


def grid(w, h):
    y, x = np.indices((h, w), dtype=float)
    return x, y


def noise(w, h, cells, wrap=True):
    """Smooth value noise in 0..1."""
    cx, cy = cells, max(1, int(cells * h / w))
    g = rng.random((cy + 1, cx + 1))
    if wrap:
        g[-1] = g[0]
        g[:, -1] = g[:, 0]
    x, y = grid(w, h)
    fx, fy = x / w * cx, y / h * cy
    x0, y0 = fx.astype(int), fy.astype(int)
    tx, ty = fx - x0, fy - y0
    tx, ty = tx * tx * (3 - 2 * tx), ty * ty * (3 - 2 * ty)
    a = g[y0, x0] * (1 - tx) + g[y0, x0 + 1] * tx
    b = g[y0 + 1, x0] * (1 - tx) + g[y0 + 1, x0 + 1] * tx
    return a * (1 - ty) + b * ty


def paint(img, mask, color, strength=1.0):
    img[mask] = img[mask] * (1 - strength) + np.array(color) * strength


# --- Bedroom wallpaper: big pale leaves on cream
W = 256
x, y = grid(W, W)
img = np.ones((W, W, 3)) * np.array((0.80, 0.81, 0.74))
img *= (0.97 + 0.05 * noise(W, W, 16))[..., None]
palette = [(0.58, 0.66, 0.56), (0.66, 0.71, 0.62), (0.48, 0.57, 0.50), (0.72, 0.70, 0.56), (0.62, 0.64, 0.60)]
for i in range(26):
    cx, cy = rng.random() * W, rng.random() * W
    angle = 1.2 + rng.normal(0, 0.45)
    length, width = 34 + rng.random() * 22, 9 + rng.random() * 6
    dx = (x - cx + W / 2) % W - W / 2
    dy = (y - cy + W / 2) % W - W / 2
    u = dx * np.cos(angle) + dy * np.sin(angle)
    v = -dx * np.sin(angle) + dy * np.cos(angle)
    leaf = (np.abs(u) < length) & (np.abs(v) < width * (1 - (u / length) ** 2))
    color = palette[i % len(palette)]
    paint(img, leaf, color, 0.8)
    # ribs
    ribs = leaf & (np.abs(((u + np.abs(v) * 1.2) % 12) - 6) < 0.8)
    paint(img, ribs, (0.42, 0.50, 0.44), 0.45)
    paint(img, leaf & (np.abs(v) < 0.8), (0.36, 0.44, 0.38), 0.7)
save("T_WallLeaf", img, levels=20)

# --- Painted plaster: kitchen and hall
img = np.ones((W, W, 3)) * np.array((0.70, 0.71, 0.70))
img *= (0.93 + 0.1 * noise(W, W, 24) + 0.03 * rng.random((W, W)))[..., None]
save("T_WallGrey", img, levels=24)

# --- Ceiling: flat grey-white stretch ceiling
img = np.ones((128, 128, 3)) * np.array((0.68, 0.68, 0.67))
img *= (0.98 + 0.03 * noise(128, 128, 6))[..., None]
save("T_CeilingGrey", img, levels=24)

# --- Laminate: grey-brown planks along X
img = np.zeros((W, W, 3))
plank = 32
for row in range(W // plank):
    base = np.array((0.44, 0.38, 0.32)) * (0.86 + 0.26 * rng.random())
    grain = np.cumsum(rng.normal(0, 0.02, W))
    grain -= np.linspace(grain[0], grain[-1], W)
    band = np.tile(grain, (plank, 1)) + rng.normal(0, 0.012, (plank, W))
    img[row * plank:(row + 1) * plank] = base * (1 + band)[..., None]
    img[row * plank] = base * 0.55
    shift = int(rng.integers(0, W))
    img[row * plank:(row + 1) * plank, shift] = base * 0.55
save("T_Laminate", img, levels=24)

# --- Bathroom wall: long beige bricks
img = np.zeros((W, W, 3))
bh, bw = 32, 64
for r in range(W // bh):
    off = (r % 2) * bw // 2
    for c in range(-1, W // bw + 1):
        tone = np.array((0.74, 0.70, 0.62)) * (0.92 + 0.14 * rng.random())
        x0, x1 = max(0, c * bw + off), min(W, (c + 1) * bw + off)
        if x1 <= x0:
            continue
        img[r * bh:(r + 1) * bh, x0:x1] = tone
        img[r * bh:(r + 1) * bh, x0] = (0.55, 0.52, 0.47)
    img[r * bh] = (0.55, 0.52, 0.47)
img *= (0.985 + 0.03 * noise(W, W, 30))[..., None]
# One darker band of tile, at about chest height; the texture repeats above the ceiling.
band = img[5 * bh:6 * bh].copy()
band[np.mean(band, axis=2) > 0.6] *= np.array((0.8, 0.62, 0.5))
img[5 * bh:6 * bh] = band
save("T_BathTile", img, levels=24)

# --- Bathroom floor: pale hexagons
x, y = grid(W, W)
size = 21.0
qx = x / (size * np.sqrt(3))
ry = y / (size * 1.5)
row = np.round(ry)
col = np.round(qx - (row % 2) * 0.5)
cx = (col + (row % 2) * 0.5) * size * np.sqrt(3)
cy = row * size * 1.5
best = np.hypot(x - cx, y - cy)
for dr in (-1, 1):
    r2 = row + dr
    c2 = np.round(qx - (r2 % 2) * 0.5)
    d2 = np.hypot(x - (c2 + (r2 % 2) * 0.5) * size * np.sqrt(3), y - r2 * size * 1.5)
    best = np.minimum(best, d2)
img = np.ones((W, W, 3)) * np.array((0.74, 0.72, 0.66))
img *= (0.94 + 0.1 * noise(W, W, 18))[..., None]
paint(img, best > size * 0.82, (0.47, 0.45, 0.40), 1.0)
save("T_HexTile", img, levels=24)

# --- Bedroom carpet: cream, red and navy medallion with paisley and a border
CW, CH = 256, 384
x, y = grid(CW, CH)
u, v = (x - CW / 2) / (CW / 2), (y - CH / 2) / (CH / 2)
img = np.ones((CH, CW, 3)) * np.array((0.74, 0.69, 0.58))
img *= (0.94 + 0.1 * rng.random((CH, CW)))[..., None]
for i in range(70):
    px, py = rng.random() * CW, rng.random() * CH
    a = rng.random() * 6.28
    dx, dy = x - px, y - py
    p = dx * np.cos(a) + dy * np.sin(a)
    q = -dx * np.sin(a) + dy * np.cos(a)
    r = np.hypot(p / 13, q / 7)
    color = [(0.46, 0.14, 0.12), (0.17, 0.25, 0.20), (0.44, 0.34, 0.20), (0.15, 0.18, 0.28)][i % 4]
    paint(img, r < 1, color, 0.85)
    paint(img, (r < 0.62) & (r > 0.32), (0.76, 0.70, 0.56), 0.9)
r = np.hypot(u * CW / CH * 1.0, v)
theta = np.arctan2(v, u * CW / CH)
petal = 0.46 + 0.05 * np.cos(theta * 12)
paint(img, r < petal, (0.66, 0.58, 0.44), 1.0)
paint(img, r < petal - 0.04, (0.20, 0.20, 0.26), 1.0)
paint(img, r < 0.33 + 0.03 * np.cos(theta * 16), (0.70, 0.62, 0.48), 1.0)
paint(img, r < 0.25, (0.46, 0.15, 0.13), 1.0)
paint(img, (r < 0.2) & (np.abs(np.sin(theta * 8)) > 0.6), (0.74, 0.66, 0.50), 1.0)
paint(img, r < 0.07, (0.18, 0.18, 0.24), 1.0)
edge = np.minimum(np.minimum(x, CW - 1 - x), np.minimum(y, CH - 1 - y))
paint(img, edge < 22, (0.30, 0.24, 0.20), 1.0)
paint(img, (edge < 18) & (edge > 6), (0.68, 0.60, 0.46), 1.0)
paint(img, (edge < 15) & (edge > 9) & ((x + y) % 14 < 7), (0.42, 0.15, 0.13), 1.0)
paint(img, edge < 3, (0.82, 0.78, 0.66), 1.0)
save("T_Carpet", img, levels=16)

# --- Kitchen runner: cream with black mandalas and violet dots
RW, RH = 128, 256
x, y = grid(RW, RH)
img = np.ones((RH, RW, 3)) * np.array((0.74, 0.74, 0.70))
img *= (0.95 + 0.08 * rng.random((RH, RW)))[..., None]
for i in range(26):
    px, py = rng.random() * RW, rng.random() * RH
    rad = 6 + rng.random() * 18
    d = np.hypot(x - px, y - py)
    kind = i % 3
    if kind == 0:
        paint(img, d < rad, (0.10, 0.10, 0.11), 1.0)
        paint(img, (d < rad * 0.72) & (d > rad * 0.62), (0.42, 0.42, 0.42), 1.0)
    elif kind == 1:
        paint(img, d < rad, (0.55, 0.55, 0.54), 1.0)
        paint(img, (d < rad * 0.7) & (np.abs(np.sin(np.arctan2(y - py, x - px) * 8)) > 0.5), (0.26, 0.26, 0.27), 1.0)
    else:
        paint(img, d < rad * 0.45, (0.30, 0.13, 0.40), 1.0)
edge = np.minimum(x, RW - 1 - x)
paint(img, edge < 2, (0.30, 0.30, 0.30), 1.0)
save("T_Runner", img, levels=16)

# --- Bath mat: stripes
img = np.zeros((128, 64, 3))
colors = [(0.55, 0.25, 0.22), (0.72, 0.68, 0.52), (0.22, 0.28, 0.30), (0.74, 0.52, 0.32), (0.32, 0.42, 0.34), (0.60, 0.58, 0.60)]
i = 0
row = 0
while row < 128:
    h = int(rng.integers(5, 11))
    img[row:row + h] = colors[i % len(colors)]
    row += h
    i += 1
img *= (0.88 + 0.2 * rng.random((128, 64)))[..., None]
save("T_BathMat", img, levels=16)


# --- Curtains: folds down the cloth
def curtain(name, color):
    x, y = grid(64, 64)
    folds = 0.72 + 0.28 * np.sin(x / 64 * 6.283 * 4 + 0.6 * np.sin(y / 64 * 6.283))
    img = np.array(color) * (folds * (0.96 + 0.06 * rng.random((64, 64))))[..., None]
    save(name, img, levels=20)


curtain("T_CurtainGreen", (0.13, 0.27, 0.19))
curtain("T_CurtainGrey", (0.50, 0.46, 0.50))

# --- Tulle: see-through mesh of pale thread. Cut out by alpha.
x, y = grid(64, 64)
img = np.ones((64, 64, 3)) * np.array((0.86, 0.85, 0.82))
alpha = ((x % 2 == 0) & (y % 2 == 0)).astype(float)
save("T_Tulle", img, alpha)

# --- Interior door: pale with ribbed panels
DW, DH = 128, 256
x, y = grid(DW, DH)
img = np.ones((DH, DW, 3)) * np.array((0.80, 0.77, 0.68))
img *= (0.96 + 0.05 * noise(DW, DH, 10))[..., None]
for y0, y1 in ((22, 112), (144, 234)):
    panel = (x > 22) & (x < 106) & (y > y0) & (y < y1)
    rim = panel & ((x < 25) | (x > 103) | (y < y0 + 3) | (y > y1 - 3))
    paint(img, rim, (0.60, 0.57, 0.50), 1.0)
for r in range(236, 250, 4):
    img[r:r + 1, 30:98] = (0.58, 0.55, 0.48)
for r in range(6, 18, 4):
    img[r:r + 1, 30:98] = (0.58, 0.55, 0.48)
save("T_DoorWhite", img, levels=20)

# --- Entrance door: dark brown steel
img = np.ones((DH, DW, 3)) * np.array((0.26, 0.17, 0.12))
img *= (0.92 + 0.14 * noise(DW, DH, 14) + 0.04 * rng.random((DH, DW)))[..., None]
paint(img, (x > 14) & (x < 114) & (y > 18) & (y < 238) & ((x < 17) | (x > 111) | (y < 21) | (y > 235)), (0.14, 0.09, 0.07), 1.0)
save("T_DoorEntry", img, levels=20)

# --- Light oak furniture
x, y = grid(128, 128)
# Fine and quiet, or a large area of it turns into stripes.
grain = np.sin(y / 128 * 6.283 * 19 + 3 * noise(128, 128, 4)) * 0.5 + 0.5
img = np.array((0.68, 0.56, 0.40)) * (0.94 + 0.08 * grain)[..., None]
img *= (0.97 + 0.05 * rng.random((128, 128)))[..., None]
save("T_Oak", img, levels=20)

# --- Green plush blanket
img = np.array((0.24, 0.38, 0.22)) * (0.82 + 0.32 * noise(128, 128, 12) + 0.1 * rng.random((128, 128)))[..., None]
save("T_Blanket", img, levels=16)

# --- Washing machine front
x, y = grid(64, 64)
img = np.ones((64, 64, 3)) * np.array((0.82, 0.82, 0.80))
d = np.hypot(x - 32, y - 26)
paint(img, d < 21, (0.50, 0.52, 0.54), 1.0)
paint(img, d < 18, (0.10, 0.11, 0.13), 1.0)
paint(img, (d < 12) & (d > 9), (0.30, 0.30, 0.34), 1.0)
paint(img, (y > 54) & (y < 60) & (x > 6) & (x < 58), (0.62, 0.62, 0.62), 1.0)
paint(img, (y > 55) & (y < 59) & (x > 26) & (x < 40), (0.10, 0.10, 0.12), 1.0)
save("T_Washer", img, levels=16)

# --- Gas hob
x, y = grid(64, 128)
img = np.ones((128, 64, 3)) * np.array((0.12, 0.12, 0.13))
for px, py in ((20, 34), (44, 34), (20, 94), (44, 94)):
    d = np.hypot(x - px, y - py)
    paint(img, (d < 13) & (d > 11), (0.40, 0.40, 0.42), 1.0)
    paint(img, d < 6, (0.26, 0.26, 0.28), 1.0)
save("T_Hob", img, levels=16)

# --- TV: off, then something on the static. Face comes from the window ghost.
ghost = bpy.data.images.load(r"F:\Work KZ\One More Night\Assets\Art\Textures\T_Ghost.png")
gw, gh = ghost.size
gpx = np.array(ghost.pixels[:]).reshape(gh, gw, 4)
TW, TH = 128, 72


def face_on(img, cx, cy, size, tint=1.0):
    """Blends the ghost face into img, sampled with nearest neighbour."""
    for yy in range(img.shape[0]):
        for xx in range(img.shape[1]):
            gx = int((xx - cx) / size * gw + gw / 2)
            gy = int((yy - cy) / size * gh + gh / 2)
            if 0 <= gx < gw and 0 <= gy < gh and gpx[gy, gx, 3] > 0.5:
                img[yy, xx] = gpx[gy, gx, :3] * tint


off = np.ones((TH, TW, 3)) * np.array((0.03, 0.03, 0.035))
off[:TH // 2] += 0.012
frame = np.zeros((TH, TW), bool)
frame[:2] = frame[-2:] = True
frame[:, :2] = frame[:, -2:] = True
off[frame] = (0.01, 0.01, 0.01)
save("T_TV", off)
static = (0.22 + 0.5 * rng.random((TH, TW)))[..., None] * np.array((0.9, 0.95, 1.0))
s1 = static.copy()
s1[frame] = (0.01, 0.01, 0.01)
save("T_TV_1", s1, levels=8)
s2 = static.copy() * 0.65
x, y = grid(TW, TH)
paint(s2, np.hypot((x - 64) / 16, (y - 28) / 24) < 1, (0.02, 0.02, 0.02), 0.92)
paint(s2, (np.abs(x - 64) < 26) & (y < 18), (0.02, 0.02, 0.02), 0.92)
s2[frame] = (0.01, 0.01, 0.01)
save("T_TV_2", s2, levels=8)
s3 = static.copy() * 0.3
face_on(s3, 64, 36, 66, 1.0)
s3[frame] = (0.01, 0.01, 0.01)
save("T_TV_3", s3, levels=8)

# --- Bathroom mirror: silvered glass, the room dim in it, and someone standing behind you
MW, MH = 128, 128
x, y = grid(MW, MH)
fall = (y / MH)[..., None]
base = np.array((0.42, 0.48, 0.5)) + fall * np.array((0.2, 0.22, 0.23))
door = (x > 62) & (x < 102) & (y < 96)                    # the doorway it faces
paint(base, door, (0.24, 0.26, 0.27), 0.8)
paint(base, ((x > 60) & (x < 104) & (y < 99)) & ~door, (0.58, 0.6, 0.58), 0.7)
streak = np.abs(((x + y * 0.6) % 96) - 30) < 7             # the sheen on the glass
paint(base, streak, (0.82, 0.86, 0.88), 0.16)
paint(base, np.abs(((x + y * 0.6) % 96) - 46) < 2, (0.82, 0.86, 0.88), 0.12)
base *= (0.95 + 0.08 * noise(MW, MH, 8))[..., None]
edge = np.minimum(np.minimum(x, MW - 1 - x), np.minimum(y, MH - 1 - y))
base *= np.clip(0.55 + edge / 14, 0, 1)[..., None]         # silver gone dark at the edge
save("T_Mirror", base, levels=20)


def figure_in(img, cx, height, width):
    body = (np.abs(x - cx) < width * (0.45 + 0.7 * (1 - y / MH))) & (y < height)
    head = np.hypot((x - cx) / (width * 0.8), (y - height) / (width * 1.05)) < 1
    paint(img, body | head, (0.03, 0.03, 0.04), 1.0)


m1 = base.copy()
figure_in(m1, 82, 62, 8)
save("T_Mirror_1", m1, levels=20)
m2 = base.copy()
figure_in(m2, 72, 90, 20)
save("T_Mirror_2", m2, levels=20)
m3 = base.copy() * 0.6
face_on(m3, 64, 62, 120, 1.0)
save("T_Mirror_3", m3, levels=20)
# --- The woman's atlas. Left half: the nightgown, hem at the bottom. Top right: hair, ragged at the bottom, cut out by alpha.
# Bottom right: her face, plain skin at the edges for the arms and legs.
FS = 256
fig_rng = np.random.default_rng(1978)
x, y = grid(FS, FS)
atlas = np.ones((FS, FS, 3)) * np.array((0.66, 0.67, 0.67))
atlas_alpha = np.ones((FS, FS))
cloth = x < 128
folds = np.sin(x / 128 * 6.283 * 7 + 2.4 * noise(FS, FS, 5)) * 0.5 + 0.5
atlas[cloth] *= (0.84 + 0.18 * folds[cloth] + 0.05 * fig_rng.random(cloth.sum()))[..., None]
# dragged along floors: filthy from the hem up
dirt = np.clip((90 - y) / 90, 0, 1) * (0.45 + 0.55 * noise(FS, FS, 14))
atlas[cloth] = atlas[cloth] * (1 - dirt[cloth] * 0.55)[..., None] + (np.array((0.27, 0.22, 0.17)) * (dirt[cloth] * 0.55)[..., None])
# old stains where the hands rest: soft and broken up, never a clean shape
blotch = noise(FS, FS, 26)
for sx, sy, rx, ry in ((12, 118, 12, 30), (116, 104, 11, 34), (46, 40, 22, 12)):
    amount = np.clip(1.3 - np.hypot((x - sx) / rx, (y - sy) / ry), 0, 1) * np.clip((blotch - 0.35) * 3, 0, 1) * 0.5
    atlas[cloth] = atlas[cloth] * (1 - amount[cloth])[..., None] + np.array((0.3, 0.17, 0.14)) * amount[cloth][..., None]

hair = (x >= 128) & (y >= 128)
strand = fig_rng.random(128)
for _ in range(2):
    strand = (strand + np.roll(strand, 1) + np.roll(strand, -1)) / 3
strand = (strand - strand.min()) / (strand.max() - strand.min())
wave = (x + 3 * np.sin(y / 17.0) + 2 * noise(FS, FS, 8)).astype(int) % 128
atlas[hair] = np.array((0.025, 0.024, 0.03)) + (0.075 * strand[wave[hair]])[..., None]
ends = 128 + (fig_rng.random(128) * 13).astype(int)
atlas_alpha[hair & (y < ends[np.clip(x - 128, 0, 127).astype(int)])] = 0
# wisps along both sides of the parting, so it is not a ruled line down her face
wisp = noise(FS, FS, 40)[:, 0]
atlas_alpha[hair & (x - 128 < 2 + 11 * np.abs(np.sin(y / 9.0)) * wisp[y.astype(int)])] = 0
atlas_alpha[hair & (255 - x < 2 + 11 * np.abs(np.sin(y / 7.0 + 1.0)) * wisp[255 - y.astype(int)])] = 0

face = (x >= 128) & (y < 128)
fx, fy = x - 128.0, y.astype(float)
atlas[face] = np.array((0.74, 0.76, 0.73))
atlas[face] *= (0.95 + 0.08 * noise(FS, FS, 20)[face] + 0.02 * fig_rng.random(face.sum()))[..., None]


def soft(cx, cy, rx, ry, amount, tone):
    """Fades towards a tone, so features sink into the skin instead of sitting on it like stickers."""
    k = amount * np.exp(-(((fx - cx) / rx) ** 2 + ((fy - cy) / ry) ** 2))
    atlas[face] = atlas[face] * (1 - k[face])[..., None] + np.array(tone) * k[face][..., None]


# hollow cheeks and temples
for side in (-1, 1):
    soft(64 + side * 34, 44, 12, 24, 0.45, (0.36, 0.37, 0.38))
    soft(64 + side * 38, 92, 10, 18, 0.3, (0.4, 0.4, 0.42))
# eyes sunk right in, almost nothing left but the dark and a wet point
for side, shift in ((-1, 0), (1, 3)):
    cx, cy = 64 + side * 21, 78 + shift
    soft(cx, cy, 20, 14, 0.55, (0.2, 0.17, 0.2))
    soft(cx, cy, 13, 8.5, 1.0, (0.02, 0.015, 0.02))
    paint(atlas, face & (np.hypot((fx - (cx - side * 2)) / 2.2, (fy - cy) / 1.8) < 1), (0.62, 0.62, 0.56), 1.0)
soft(64, 62, 5, 9, 0.3, (0.36, 0.36, 0.38))
soft(64, 54, 8, 3, 0.45, (0.24, 0.22, 0.24))
# the mouth a little open, dark, dried at the corner
soft(64, 31, 16, 10, 0.5, (0.26, 0.2, 0.22))
soft(64, 31, 9.5, 5.5, 1.0, (0.015, 0.01, 0.01))
paint(atlas, face & (np.abs(fx - 71) < 1.6) & (fy > 8) & (fy < 28), (0.2, 0.08, 0.07), 0.7)
save("T_Figure", atlas, atlas_alpha, levels=24)
print("RESULT textures ok")
