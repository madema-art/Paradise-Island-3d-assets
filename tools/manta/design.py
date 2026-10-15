"""
Giant manta ray: pure-numpy geometry and rig layout (no Blender needed).

Conventions (match the tropical fish): Z is up, +X is forward (the head), +Y is the right wing tip.
Units are metres. The origin is the centre of the disc on the midline. glTF export converts to Y-up.

Parts (each one becomes a glTF primitive with its own material):
  dorsal   top of the disc and the cephalic lobes
  ventral  underside of the disc
  mouth    dark patch on the underside, front centre
  gill     five dark slits on each side of the underside
  eye      one small dome per side, on top of the disc
  tail     long whip-like tail (dark), no barb

Everything is a closed or capped surface, so bpy can run recalc-normals on it safely.
"""
import math

import numpy as np

WING_TIP_Y = 3.0          # 6.0 m wingspan
RINGS = 8                 # radial rings from the centre to the rim
RIM_SAMPLES = 48          # outline samples around the disc

# Half outline in the top view, from the head centre (+Y side) round to the cloaca.
# Mirrored for -Y. Star-shaped about the origin, so each ring is a radial scale of the rim.
OUTLINE_HALF = [
    (1.10, 0.00),   # head front centre (mouth lip)
    (1.14, 0.42),   # cephalic lobe root, broad head
    (1.06, 0.90),
    (0.88, 1.55),   # leading edge of the pectoral wing, slightly concave behind the head
    (0.52, 2.25),
    (0.08, 2.80),
    (-0.30, 3.00),  # wing tip, swept back
    (-0.46, 2.66),  # trailing edge, concave between tip and cloaca
    (-0.62, 1.98),
    (-0.78, 1.18),
    (-0.92, 0.50),
    (-0.98, 0.00),  # cloaca, tail root
]

TAIL_START = (-0.55, 0.0, 0.0)   # starts inside the body so there is no gap
TAIL_END = (-3.40, 0.0, 0.02)
LOBE_BASE = (1.10, 0.36, 0.00)   # cephalic lobe (horn) root, +Y side

# Material slots, in glTF order
MATERIALS = ["dorsal", "ventral", "mouth", "gill", "eye", "tail"]
MAT = {name: i for i, name in enumerate(MATERIALS)}


# --- outline ------------------------------------------------------------------

def _outline_full():
    half = OUTLINE_HALF
    mirror = [(x, -y) for (x, y) in reversed(half[1:-1])]
    return np.array(half + mirror, dtype=float)


def _catmull_rom_closed(points, per_seg=24):
    n = len(points)
    out = []
    for i in range(n):
        p0, p1, p2, p3 = points[i - 1], points[i], points[(i + 1) % n], points[(i + 2) % n]
        for s in range(per_seg):
            t = s / per_seg
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    return np.array(out)


def rim_outline(samples=RIM_SAMPLES):
    """Resample the closed outline to `samples` points, equally spaced by arc length."""
    dense = _catmull_rom_closed(_outline_full())
    closed = np.vstack([dense, dense[:1]])
    seg = np.linalg.norm(np.diff(closed, axis=0), axis=1)
    arc = np.concatenate([[0.0], np.cumsum(seg)])
    targets = np.linspace(0.0, arc[-1], samples, endpoint=False)
    xs = np.interp(targets, arc, closed[:, 0])
    ys = np.interp(targets, arc, closed[:, 1])
    return np.stack([xs, ys], axis=1)


_RIM = rim_outline()
_ANG = np.arctan2(_RIM[:, 1], _RIM[:, 0])
_RAD = np.hypot(_RIM[:, 0], _RIM[:, 1])
_ORDER = np.argsort(_ANG)
_ANG_S, _RAD_S = _ANG[_ORDER], _RAD[_ORDER]


def rim_radius(theta):
    """Outline distance from the origin in direction theta (periodic)."""
    t = np.mod(theta, 2 * math.pi)
    t = np.where(t > math.pi, t - 2 * math.pi, t)
    return np.interp(t, np.concatenate([_ANG_S[-1:] - 2 * math.pi, _ANG_S, _ANG_S[:1] + 2 * math.pi]),
                     np.concatenate([_RAD_S[-1:], _RAD_S, _RAD_S[:1]]))


def normalised_radius(x, y):
    """s = 0 at the centre, 1 on the rim, in the direction of (x, y)."""
    r = np.hypot(x, y)
    return r / np.maximum(rim_radius(np.arctan2(y, x)), 1e-6)


# --- heights -------------------------------------------------------------------

def top_height(s, y):
    """Dorsal surface: a gentle dome, and the wing tips curl up."""
    tip = 0.42 * (np.abs(y) / WING_TIP_Y) ** 3 * s * s
    return 0.14 * (1.0 - s * s) + tip


def bottom_height(s, y):
    """Ventral surface: flatter, with a little rim thickness so the edge is not zero-area."""
    tip = 0.42 * (np.abs(y) / WING_TIP_Y) ** 3 * s * s
    return -0.06 * (1.0 - s * s) ** 0.8 - 0.025 * s ** 4 + tip


# --- mesh pieces ----------------------------------------------------------------

def _disc(height_fn, flip, mat_of_face=None):
    """Triangulated disc: a centre vertex, RINGS rings of RIM_SAMPLES verts, and a fan + quads."""
    verts = [(0.0, 0.0, float(height_fn(0.0, 0.0)))]
    for j in range(1, RINGS + 1):
        s = j / RINGS
        for k in range(RIM_SAMPLES):
            x, y = s * _RIM[k]
            verts.append((x, y, float(height_fn(s, y))))
    faces = []

    def idx(j, k):
        return 1 + (j - 1) * RIM_SAMPLES + (k % RIM_SAMPLES)

    for k in range(RIM_SAMPLES):
        faces.append((0, idx(1, k + 1), idx(1, k)) if flip else (0, idx(1, k), idx(1, k + 1)))
    for j in range(1, RINGS):
        for k in range(RIM_SAMPLES):
            a, b, c, d = idx(j, k), idx(j, k + 1), idx(j + 1, k + 1), idx(j + 1, k)
            faces.append((a, d, c, b) if flip else (a, b, c, d))
    return np.array(verts), faces


def _tube(centre_fn, radius_fn, segs=8, rings=12):
    """Swept tube along centre_fn(t), t in [0, 1], with capped ends."""
    ts = np.linspace(0.0, 1.0, rings)
    pts = np.array([centre_fn(t) for t in ts])
    verts = []
    for i, t in enumerate(ts):
        p = pts[i]
        d = (pts[min(i + 1, rings - 1)] - pts[max(i - 1, 0)])
        d = d / max(np.linalg.norm(d), 1e-9)
        side = np.cross(d, [0.0, 0.0, 1.0])
        if np.linalg.norm(side) < 1e-6:
            side = np.array([0.0, 1.0, 0.0])
        side /= np.linalg.norm(side)
        up = np.cross(side, d)
        r = radius_fn(t)
        for k in range(segs):
            a = 2 * math.pi * k / segs
            verts.append(p + r * (math.cos(a) * side + math.sin(a) * up))
    verts = [np.array(v) for v in verts]
    cap0 = len(verts)
    verts.append(pts[0])
    cap1 = len(verts)
    verts.append(pts[-1])

    def ring(i, k):
        return i * segs + (k % segs)

    faces = []
    for i in range(rings - 1):
        for k in range(segs):
            faces.append((ring(i, k), ring(i, k + 1), ring(i + 1, k + 1), ring(i + 1, k)))
    for k in range(segs):
        faces.append((cap0, ring(0, k + 1), ring(0, k)))
        faces.append((cap1, ring(rings - 1, k), ring(rings - 1, k + 1)))
    return np.array(verts), faces


def _bezier(p0, p1, p2, p3):
    p0, p1, p2, p3 = map(np.array, (p0, p1, p2, p3))
    return lambda t: ((1 - t) ** 3) * p0 + 3 * ((1 - t) ** 2) * t * p1 + 3 * (1 - t) * t * t * p2 + t ** 3 * p3


def _lobe_centre(sign):
    return _bezier(LOBE_BASE, (1.55, 0.50, 0.02), (1.72, 0.36, 0.02), (1.45, 0.10, 0.00)) if sign > 0 else \
        _bezier((LOBE_BASE[0], -LOBE_BASE[1], LOBE_BASE[2]), (1.55, -0.50, 0.02), (1.72, -0.36, 0.02),
                (1.45, -0.10, 0.00))


def _tail_centre(t):
    x = TAIL_START[0] + (TAIL_END[0] - TAIL_START[0]) * t
    z = TAIL_START[2] + (TAIL_END[2] - TAIL_START[2]) * t + 0.03 * math.sin(math.pi * t)
    return np.array([x, 0.0, z])


def _tail_radius(t):
    return 0.05 * (1.0 - t) ** 0.8 + 0.008 * t


def _eye_sphere(cx, cy, cz, rad=0.07, segs=10, rings=6):
    verts = [(cx, cy, cz + 0.55 * rad)]
    faces = []
    for j in range(1, rings):
        t = math.pi * j / rings
        for k in range(segs):
            p = 2 * math.pi * k / segs
            verts.append((cx + rad * math.sin(t) * math.cos(p), cy + rad * math.sin(t) * math.sin(p),
                          cz + 0.55 * rad * math.cos(t)))
    verts.append((cx, cy, cz - 0.55 * rad))
    last = len(verts) - 1

    def ring(j, k):
        return 1 + (j - 1) * segs + (k % segs)

    for k in range(segs):
        faces.append((0, ring(1, k), ring(1, k + 1)))
    for j in range(1, rings - 1):
        for k in range(segs):
            faces.append((ring(j, k), ring(j + 1, k), ring(j + 1, k + 1), ring(j, k + 1)))
    for k in range(segs):
        faces.append((last, ring(rings - 1, k + 1), ring(rings - 1, k)))
    return np.array(verts), faces


def _quad(corners):
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = corners
    vs = np.array([(x, y, 0.0) for (x, y) in corners])
    for i, (x, y) in enumerate(corners):
        s = float(normalised_radius(x, y))
        vs[i, 2] = float(bottom_height(s, y)) - 0.004
    return vs, [(0, 1, 2, 3)]


def build_parts():
    """Return [(verts (N,3), faces list of index tuples, material index per face)], one entry per part."""
    parts = []

    dorsal_v, dorsal_f = _disc(lambda s, y: top_height(s, y) if s > 0 else 0.14, flip=False)
    dorsal_mats = [MAT["dorsal"]] * len(dorsal_f)

    ventral_v, ventral_f = _disc(lambda s, y: bottom_height(s, y) if s > 0 else -0.06, flip=True)
    ventral_mats = []
    for f in ventral_f:
        cx = np.mean(ventral_v[list(f), 0])
        cy = np.mean(ventral_v[list(f), 1])
        ventral_mats.append(MAT["mouth"] if (cx > 0.85 and abs(cy) < 0.40) else MAT["ventral"])

    parts.append((dorsal_v, dorsal_f, dorsal_mats))
    parts.append((ventral_v, ventral_f, ventral_mats))

    # Rim strip joins the dorsal and ventral shells along the outline (welded in merged_mesh)
    ring0 = 1 + (RINGS - 1) * RIM_SAMPLES
    top_rim = dorsal_v[ring0:ring0 + RIM_SAMPLES]
    bot_rim = ventral_v[ring0:ring0 + RIM_SAMPLES]
    rim_v = np.vstack([top_rim, bot_rim])
    rim_f = []
    for k in range(RIM_SAMPLES):
        a, b = k, (k + 1) % RIM_SAMPLES
        rim_f.append((a, b, RIM_SAMPLES + b, RIM_SAMPLES + a))
    parts.append((rim_v, rim_f, [MAT["ventral"]] * len(rim_f)))

    # Gill slits: five thin dark quads on each side of the underside
    gill_v, gill_f, gill_m = [], [], []
    offset = 0
    for side in (+1, -1):
        for i in range(5):
            yc = side * (0.56 + 0.12 * i)
            xc = -0.30 - 0.02 * i
            corners = [(xc - 0.03, yc - 0.012), (xc + 0.03, yc - 0.012), (xc + 0.03, yc + 0.012), (xc - 0.03, yc + 0.012)]
            vs, fs = _quad(corners)
            gill_v.append(vs)
            gill_f += [tuple(i_ + offset for i_ in f) for f in fs]
            gill_m += [MAT["gill"]] * len(fs)
            offset += len(vs)
    parts.append((np.vstack(gill_v), gill_f, gill_m))

    # Eyes: one per side, on top of the disc, near the front of the wing
    for side in (+1, -1):
        ev, ef = _eye_sphere(0.62, side * 1.12, float(top_height(0.6, side * 1.12)) + 0.012)
        parts.append((ev, ef, [MAT["eye"]] * len(ef)))

    # Cephalic lobes (dorsal colour)
    for side in (+1, -1):
        lv, lf = _tube(_lobe_centre(side), lambda t: 0.085 * (1.0 - t) + 0.02 * t)
        parts.append((lv, lf, [MAT["dorsal"]] * len(lf)))

    # Tail
    tv, tf = _tube(_tail_centre, _tail_radius)
    parts.append((tv, tf, [MAT["tail"]] * len(tf)))
    return parts


def merged_mesh(weld=1e-6):
    """Single (verts, faces, material) list, ready for bmesh. Indices are global.

    Vertices at the same position (across parts, e.g. the rim strip and the shells) are welded so the
    body is one closed surface.
    """
    all_v, all_f, all_m = [], [], []
    index_of = {}
    unique = []
    for v, f, m in build_parts():
        remap = []
        for p in v:
            key = tuple(np.round(p / weld).astype(np.int64))
            if key not in index_of:
                index_of[key] = len(unique)
                unique.append(p)
            remap.append(index_of[key])
        for face, mat in zip(f, m):
            all_f.append(tuple(remap[int(i)] for i in face))
            all_m.append(mat)
    return np.array(unique), all_f, all_m


# --- rig ------------------------------------------------------------------------

# name: (head, tail, parent). Bones are set in rest pose; animation rotates them about local axes.
BONES = {
    "root":    ((0.00, 0.0, 0.00), (0.30, 0.0, 0.00), None),
    "body":    ((0.30, 0.0, 0.00), (0.95, 0.0, 0.00), "root"),
    "head_L":  ((1.00, 0.30, 0.00), (1.60, 0.30, 0.00), "body"),
    "head_R":  ((1.00, -0.30, 0.00), (1.60, -0.30, 0.00), "body"),
    "wing_L1": ((0.45, 0.30, 0.00), (0.40, 1.45, 0.00), "body"),
    "wing_L2": ((0.40, 1.45, 0.00), (0.10, 2.30, 0.00), "wing_L1"),
    "wing_L3": ((0.10, 2.30, 0.00), (-0.38, 3.00, 0.00), "wing_L2"),
    "wing_R1": ((0.45, -0.30, 0.00), (0.40, -1.45, 0.00), "body"),
    "wing_R2": ((0.40, -1.45, 0.00), (0.10, -2.30, 0.00), "wing_R1"),
    "wing_R3": ((0.10, -2.30, 0.00), (-0.38, -3.00, 0.00), "wing_R2"),
    "tail1":   ((-0.90, 0.0, 0.00), (-1.80, 0.0, 0.00), "root"),
    "tail2":   ((-1.80, 0.0, 0.00), (-2.60, 0.0, 0.01), "tail1"),
    "tail3":   ((-2.60, 0.0, 0.01), (-3.40, 0.0, 0.02), "tail2"),
}
BONE_NAMES = list(BONES)


def _seg_dist(p, a, b):
    ab = b - a
    t = np.clip(((p - a) @ ab) / max(ab @ ab, 1e-9), 0.0, 1.0)
    return np.linalg.norm(p - (a + t[:, None] * ab), axis=1)


def skin_weights(verts, sigma=0.38, keep=4):
    """Per-vertex bone weights: Gaussian falloff from each bone segment, top `keep` kept, normalised.

    Returns (joints (N, keep) int, weights (N, keep) float), as glTF expects.
    """
    p = np.asarray(verts, dtype=float)
    dists = np.zeros((len(p), len(BONE_NAMES)))
    for i, name in enumerate(BONE_NAMES):
        head, tail, _ = BONES[name]
        dists[:, i] = _seg_dist(p, np.array(head), np.array(tail))
    # Wings and lobes are separate limbs: a vertex sitting far out on the wing should not drift to the body
    w = np.exp(-(dists / sigma) ** 2)
    order = np.argsort(-w, axis=1)[:, :keep]
    top = np.take_along_axis(w, order, axis=1)
    top = top / np.maximum(top.sum(axis=1, keepdims=True), 1e-12)
    return order.astype(np.int32), top.astype(np.float32)


if __name__ == "__main__":
    v, f, m = merged_mesh()
    print("verts", len(v), "tris", sum(len(x) - 2 for x in f))
    print("bounds", v.min(axis=0).round(3), v.max(axis=0).round(3))
    print("material counts", {name: m.count(i) for name, i in MAT.items()})
