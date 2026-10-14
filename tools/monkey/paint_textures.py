"""
Stage 2: paint the monkey texture set procedurally in UV space.

Rasterises the unwrapped mesh to get a world position / normal / tangent frame per texel, then
synthesises colour, fur relief, ambient occlusion and roughness as functions of that 3D data.
Because colour is a continuous function of world position, UV seams do not show in the albedo.

  /opt/bpy-venv/bin/python tools/monkey/paint_textures.py --mesh build/monkey/mesh.npz --out build/monkey/tex

Outputs (all in --out): monkey_albedo.png, monkey_normal.png, monkey_orm.png (R=AO G=rough B=metal),
eye_albedo.png, plus debug images.  Image rows are flipped so row 0 is v=1 (glTF convention).
"""
import argparse
import os
import sys
import time

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import design  # noqa: E402
from sdf import Grid  # noqa: E402


# ----------------------------------------------------------------------------- helpers
def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def mix(a, b, t):
    t = np.asarray(t)[..., None] if np.ndim(t) else t
    return a + (b - a) * t


class Noise3:
    """Cheap tileable 3D value noise on a random lattice."""

    def __init__(self, seed, size=64):
        self.t = np.random.default_rng(seed).random((size, size, size), dtype=np.float32)
        self.n = size

    def __call__(self, P, cell):
        q = P / cell
        i = np.floor(q).astype(np.int64)
        f = (q - i).astype(np.float32)
        f = f * f * (3.0 - 2.0 * f)
        n = self.n
        x0, y0, z0 = i[:, 0] % n, i[:, 1] % n, i[:, 2] % n
        x1, y1, z1 = (x0 + 1) % n, (y0 + 1) % n, (z0 + 1) % n
        t = self.t
        fx, fy, fz = f[:, 0], f[:, 1], f[:, 2]
        c00 = t[x0, y0, z0] * (1 - fx) + t[x1, y0, z0] * fx
        c10 = t[x0, y1, z0] * (1 - fx) + t[x1, y1, z0] * fx
        c01 = t[x0, y0, z1] * (1 - fx) + t[x1, y0, z1] * fx
        c11 = t[x0, y1, z1] * (1 - fx) + t[x1, y1, z1] * fx
        return (c00 * (1 - fy) + c10 * fy) * (1 - fz) + (c01 * (1 - fy) + c11 * fy) * fz


def strands(noise, P, flow, cell, K, step):
    """Noise smeared along the fur flow direction -> hair-like streaks."""
    acc = np.zeros(len(P), np.float32)
    for k in range(K):
        acc += noise(P + flow * ((k - (K - 1) / 2.0) * step), cell)
    return acc / K


# ----------------------------------------------------------------------------- rasterisation
def rasterize(V, F, N, uv, size):
    """Per-texel triangle id + barycentrics (u,v with v up, row index = v*size)."""
    tri_id = -np.ones((size, size), np.int32)
    bary = np.zeros((size, size, 3), np.float32)
    px = uv.astype(np.float64) * size
    for i in range(len(F)):
        a, b, c = px[i]
        x0 = max(int(np.floor(min(a[0], b[0], c[0]) - 1)), 0)
        x1 = min(int(np.ceil(max(a[0], b[0], c[0]) + 1)), size - 1)
        y0 = max(int(np.floor(min(a[1], b[1], c[1]) - 1)), 0)
        y1 = min(int(np.ceil(max(a[1], b[1], c[1]) + 1)), size - 1)
        if x1 < x0 or y1 < y0:
            continue
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(den) < 1e-12:
            continue
        X, Y = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        l1 = ((b[1] - c[1]) * (X - c[0]) + (c[0] - b[0]) * (Y - c[1])) / den
        l2 = ((c[1] - a[1]) * (X - c[0]) + (a[0] - c[0]) * (Y - c[1])) / den
        l3 = 1.0 - l1 - l2
        eps = 0.01
        m = (l1 >= -eps) & (l2 >= -eps) & (l3 >= -eps)
        if not m.any():
            continue
        ys, xs = np.nonzero(m)
        tri_id[y0 + ys, x0 + xs] = i
        bary[y0 + ys, x0 + xs, 0] = l1[ys, xs]
        bary[y0 + ys, x0 + xs, 1] = l2[ys, xs]
        bary[y0 + ys, x0 + xs, 2] = l3[ys, xs]
    return tri_id, bary


def triangle_tangents(V, F, uv):
    p0, p1, p2 = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    e1, e2 = p1 - p0, p2 - p0
    d1, d2 = uv[:, 1] - uv[:, 0], uv[:, 2] - uv[:, 0]
    r = d1[:, 0] * d2[:, 1] - d2[:, 0] * d1[:, 1]
    r = np.where(np.abs(r) < 1e-20, 1e-20, r)
    T = (e1 * d2[:, 1:2] - e2 * d1[:, 1:2]) / r[:, None]
    B = (e2 * d1[:, 0:1] - e1 * d2[:, 0:1]) / r[:, None]
    nt = np.linalg.norm(T, axis=1, keepdims=True)
    nb = np.linalg.norm(B, axis=1, keepdims=True)
    return T / np.maximum(nt, 1e-12), B / np.maximum(nb, 1e-12)


def interp(attr_v, F, tri, bary, valid):
    """Interpolate a per-vertex attribute (n,k) onto texels -> (count,k) for valid texels."""
    t = tri[valid]
    b = bary[valid]
    f = F[t]
    return (attr_v[f[:, 0]] * b[:, 0:1] + attr_v[f[:, 1]] * b[:, 1:2] + attr_v[f[:, 2]] * b[:, 2:3])


# ----------------------------------------------------------------------------- anatomy data
def group_masks(D, names, W):
    """Per-vertex 0..1 masks from bone weights."""
    idx = {n: i for i, n in enumerate(names)}

    def grp(pred):
        cols = [i for n, i in idx.items() if pred(n)]
        return W[:, cols].sum(axis=1) if cols else np.zeros(len(W), np.float32)

    return dict(
        ear=grp(lambda n: n.startswith("ear_")),
        head=grp(lambda n: n in ("head", "jaw")),
        palm=grp(lambda n: n.startswith("hand_") or n.startswith("foot_")),
        digit=grp(lambda n: n.startswith("f_") or n.startswith("t_")),
        nail=grp(lambda n: n.endswith(("_3_L", "_3_R")) or n in
                 ("f_thumb_2_L", "f_thumb_2_R", "t_hallux_2_L", "t_hallux_2_R")),
        tail=grp(lambda n: n.startswith("tail_")),
        limb=grp(lambda n: n.startswith(("upper_arm", "forearm", "thigh", "shin", "clavicle"))),
        torso=grp(lambda n: n in ("pelvis", "spine1", "spine2", "spine3", "neck1", "neck2")),
    )


def flow_vectors(D, names, W):
    """Fur lie direction per vertex: backwards on head/torso, distal on limbs, tip-ward on the tail."""
    dirs = np.zeros((len(names), 3), np.float32)
    for i, n in enumerate(names):
        b = D.bones[n]
        d = b["tail"] - b["head"]
        d = d / max(np.linalg.norm(d), 1e-9)
        if n in ("root", "pelvis", "spine1", "spine2", "spine3", "neck1", "neck2", "head", "jaw") \
                or n.startswith(("ear_", "eye_", "clavicle")):
            d = np.array([0.0, 1.0, 0.1])  # +Y is backwards
        dirs[i] = d
    f = W @ dirs
    n = np.linalg.norm(f, axis=1, keepdims=True)
    return (f / np.maximum(n, 1e-9)).astype(np.float32)


def build_sdf_sampler(D, voxel=0.003):
    lo, hi = design.mesh_bounds(D, margin=0.06)
    g = Grid(lo, hi, voxel)
    for op, p, k in D.ops:
        g.apply(p, k, op)
    field = g.field

    def sample(P):
        q = ((P - g.bmin) / g.voxel).T
        return ndimage.map_coordinates(field, q, order=1, mode="nearest")

    return sample


# ----------------------------------------------------------------------------- palette (sRGB)
C = dict(
    dorsal_dark=np.array([0.215, 0.165, 0.105]),
    dorsal_light=np.array([0.385, 0.305, 0.195]),
    flank=np.array([0.470, 0.385, 0.265]),
    belly=np.array([0.690, 0.625, 0.505]),
    gold=np.array([0.620, 0.500, 0.270]),
    tip_dark=np.array([0.100, 0.075, 0.055]),
    crown=np.array([0.170, 0.125, 0.085]),
    ruff=np.array([0.720, 0.650, 0.485]),
    skin_face=np.array([0.610, 0.470, 0.430]),
    skin_dark=np.array([0.300, 0.225, 0.215]),
    eyelid=np.array([0.800, 0.700, 0.640]),
    lip=np.array([0.340, 0.230, 0.220]),
    ear_skin=np.array([0.520, 0.385, 0.345]),
    palm=np.array([0.255, 0.200, 0.195]),
    nail=np.array([0.520, 0.440, 0.370]),
)


def paint(args):
    t0 = time.time()
    z = np.load(args.mesh)
    V, F, N, uv = z["V"].astype(np.float64), z["F"].astype(np.int64), z["N"].astype(np.float64), z["uv"]
    W, names = z["W"], [str(n) for n in z["bones"]]
    D = design.build()
    size = args.size
    os.makedirs(args.out, exist_ok=True)

    tri, bary = rasterize(V, F, N, uv, size)
    valid = tri >= 0
    print(f"[paint] rasterised {valid.sum()} texels ({valid.mean() * 100:.1f}% of {size}^2) in {time.time() - t0:.1f}s")

    Ttri, Btri = triangle_tangents(V, F, uv.astype(np.float64))
    masks = group_masks(D, names, W)
    flow_v = flow_vectors(D, names, W)

    P = interp(V, F, tri, bary, valid)
    Nn = interp(N, F, tri, bary, valid)
    Nn /= np.maximum(np.linalg.norm(Nn, axis=1, keepdims=True), 1e-9)
    Tt = Ttri[tri[valid]]
    Bt = Btri[tri[valid]]
    # orthonormalise tangent frame against the shading normal
    Tt = Tt - Nn * (Tt * Nn).sum(1, keepdims=True)
    Tt /= np.maximum(np.linalg.norm(Tt, axis=1, keepdims=True), 1e-9)
    Bt = np.cross(Nn, Tt) * np.sign((np.cross(Tt, Bt) * Nn).sum(1, keepdims=True) + 1e-12)
    M = {k: interp(v[:, None], F, tri, bary, valid)[:, 0] for k, v in masks.items()}
    flow = interp(flow_v, F, tri, bary, valid)
    flow -= Nn * (flow * Nn).sum(1, keepdims=True)
    fl = np.linalg.norm(flow, axis=1, keepdims=True)
    flow = np.where(fl > 1e-4, flow / np.maximum(fl, 1e-9), Tt)

    x, y, zc = P[:, 0], P[:, 1], P[:, 2]
    fwd = -y                                  # forward distance from the pelvis
    side = np.sign(x + 1e-9)
    nz = Nn[:, 2]
    n_n = len(P)

    # --- noise fields
    nA, nB, nC, nD = Noise3(1), Noise3(2), Noise3(3), Noise3(4)
    h1 = np.empty(n_n, np.float32)
    h2 = np.empty(n_n, np.float32)
    gT = np.empty(n_n, np.float32)
    gB = np.empty(n_n, np.float32)
    patch = np.empty(n_n, np.float32)
    speck = np.empty(n_n, np.float32)
    eps = 0.0004
    chunk = 250_000
    for s in range(0, n_n, chunk):
        e = min(s + chunk, n_n)
        p, f_, tt, bb = P[s:e], flow[s:e], Tt[s:e], Bt[s:e]

        def height(q):
            return 0.62 * strands(nA, q, f_, 0.0011, 5, 0.0011) + 0.38 * strands(nB, q, f_, 0.0028, 4, 0.0028)

        h0 = height(p)
        gT[s:e] = (height(p + tt * eps) - h0) / eps
        gB[s:e] = (height(p + bb * eps) - h0) / eps
        h1[s:e] = h0
        h2[s:e] = strands(nC, p, f_, 0.0016, 4, 0.0016)
        patch[s:e] = nD(p, 0.030) * 0.6 + nD(p + 7.3, 0.011) * 0.4
        speck[s:e] = nC(p + 3.1, 0.0016)
    print(f"[paint] noise fields done ({time.time() - t0:.1f}s)")

    # --- region masks in design space
    fc = design.P(0, 0.430, 0.316)
    dface = np.sqrt(((x - 0) / 0.026) ** 2 + ((fwd - 0.428) / 0.036) ** 2 + ((zc - 0.316) / 0.028) ** 2)
    face = (1 - smoothstep(0.72, 1.06, dface)) * M["head"] * (fwd > 0.405)
    # face fur recedes: a cleaner skin mask under the brow, over the muzzle
    brow_line = smoothstep(0.338, 0.346, zc)                       # forehead hair above the brow
    face *= 1 - brow_line * smoothstep(0.405, 0.42, fwd)
    eye_d = np.minimum(np.sqrt((np.abs(x) - 0.0215) ** 2 + (fwd - 0.4195) ** 2 + (zc - 0.3315) ** 2),
                       9.9)
    eye_ring = 1 - smoothstep(0.011, 0.019, eye_d)
    eye_rim = smoothstep(0.0085, 0.0100, eye_d) * (1 - smoothstep(0.0100, 0.0125, eye_d))
    nose_d = np.sqrt((x / 0.011) ** 2 + ((fwd - 0.451) / 0.012) ** 2 + ((zc - 0.303) / 0.010) ** 2)
    nostril = (1 - smoothstep(0.35, 0.75, np.sqrt(((np.abs(x) - 0.0050) / 0.0030) ** 2
                                                  + ((fwd - 0.4505) / 0.0055) ** 2
                                                  + ((zc - 0.3010) / 0.0036) ** 2)))
    mouth_z = design_mouth_z() + 6.0 * x * x            # corners of the mouth curve up
    mouth_dz = zc - mouth_z
    mouth = (1 - smoothstep(0.0004, 0.0013, np.abs(mouth_dz))) * (fwd > 0.420) \
        * (1 - smoothstep(0.0165, 0.0205, np.abs(x))) * M["head"]
    lip_zone = (1 - smoothstep(0.0025, 0.0075, np.abs(mouth_dz))) * (fwd > 0.420) \
        * (1 - smoothstep(0.0155, 0.0215, np.abs(x))) * M["head"]
    muzzle_dark = (1 - smoothstep(0.55, 1.0, nose_d)) * 0.8 + (1 - smoothstep(0.7, 1.4, dface)) * 0.35
    cheek_ruff = smoothstep(0.016, 0.030, np.abs(x)) * M["head"] * smoothstep(0.370, 0.400, fwd) * (1 - face)

    # --- fur colour -------------------------------------------------------------------------------
    ventral = smoothstep(0.05, -0.55, nz)
    dorsal_mix = np.clip(patch * 1.4 - 0.15, 0, 1)
    fur = mix(C["dorsal_dark"], C["dorsal_light"], dorsal_mix)
    fur = mix(fur, C["flank"], 0.45 * (1 - smoothstep(0.35, 0.85, nz)))
    # darker spine stripe
    fur = mix(fur, C["dorsal_dark"], 0.55 * np.exp(-(x / 0.034) ** 2) * smoothstep(0.30, 0.85, nz) * M["torso"])
    fur = mix(fur, C["belly"], ventral * np.clip(0.55 + 0.45 * M["torso"] + 0.5 * M["limb"], 0, 1))
    # paler inner faces of the limbs
    inner = np.clip(-side * Nn[:, 0], 0, 1)
    fur = mix(fur, C["belly"], 0.65 * inner * np.clip(M["limb"] + M["palm"] * 0.5, 0, 1))
    # forearms and shins grade darker towards the hands and feet
    distal = np.clip(M["digit"] * 0.8 + M["palm"] * 0.8, 0, 1)
    fur = mix(fur, C["dorsal_dark"], 0.55 * distal)
    # tail: dark dorsal, lighter underside, darker tip
    tail_tip = smoothstep(0.30, 0.47, y)
    fur_tail = mix(mix(C["dorsal_dark"], C["flank"], 0.35 * dorsal_mix), C["belly"], 0.55 * ventral)
    fur_tail = mix(fur_tail, C["tip_dark"], 0.6 * tail_tip)
    fur = mix(fur, fur_tail, M["tail"])
    # head hair: dark crown, buff cheek ruff and neck
    crown = smoothstep(0.340, 0.355, zc) * M["head"] * (1 - face)
    fur = mix(fur, C["crown"], 0.9 * crown)
    fur = mix(fur, C["ruff"], 0.85 * cheek_ruff)
    # agouti: warm gold speckle + dark tips along the strands
    gold = np.clip((h1 - 0.5) * 3.0 + (speck - 0.5) * 1.2, 0, 1)
    dark_tip = np.clip((0.5 - h2) * 2.2, 0, 1)
    fur = mix(fur, C["gold"], 0.28 * gold)
    fur = mix(fur, C["tip_dark"], 0.40 * dark_tip)
    fur = fur * (0.80 + 0.40 * h1[:, None])

    # --- bare skin ------------------------------------------------------------------------------
    skin = mix(C["skin_face"], C["skin_dark"], muzzle_dark)
    skin = mix(skin, C["eyelid"], eye_ring * 0.95)
    skin = mix(skin, C["skin_dark"], eye_rim * 0.9)
    skin = mix(skin, C["lip"], np.clip(lip_zone * 0.7, 0, 1))
    skin = mix(skin, C["tip_dark"], np.clip(mouth * 0.9 + nostril * 0.95, 0, 1))
    skin = skin * (0.93 + 0.14 * speck[:, None])
    skin_amt = np.clip(face + eye_ring * 0.9 * M["head"], 0, 1)

    # hands and feet: dark skin, sparse hair on the back
    palm_side = smoothstep(-0.05, -0.55, nz)
    hand_skin = mix(C["skin_dark"], C["palm"], palm_side)
    hand_skin = hand_skin * (0.85 + 0.30 * speck[:, None])
    hands = np.clip(M["palm"] + M["digit"], 0, 1)
    hand_amt = hands * (0.55 + 0.45 * palm_side)
    # ears
    ear_amt = M["ear"] * 0.92
    ear_col = mix(C["ear_skin"], C["skin_dark"], smoothstep(0.0, 0.5, nz) * 0.4)
    nail_amt = np.clip(M["nail"] * 1.4 - 0.4, 0, 1) * smoothstep(0.05, 0.40, nz)

    col = fur
    col = mix(col, hand_skin, hand_amt)
    col = mix(col, ear_col, ear_amt)
    col = mix(col, skin, skin_amt)
    # lips, mouth line and nostrils are painted over everything (they sit on the fur/skin boundary)
    col = mix(col, C["lip"], np.clip(lip_zone * 0.75, 0, 1))
    col = mix(col, C["tip_dark"], np.clip(mouth * 0.95 + nostril * 0.95, 0, 1))
    col = mix(col, C["nail"], nail_amt * 0.9)
    col = np.clip(col, 0, 1)

    # --- ambient occlusion from the SDF -----------------------------------------------------------------
    sdf = build_sdf_sampler(D)
    occ = np.zeros(n_n, np.float32)
    for i, tdist in enumerate((0.0035, 0.008, 0.015, 0.026, 0.04)):
        occ += (tdist - sdf(P + Nn * tdist)).clip(0, None) / tdist / (1.0 + 0.6 * i)
    ao = np.clip(1.0 - 0.55 * occ, 0.30, 1.0).astype(np.float32)
    col = col * (0.55 + 0.45 * ao[:, None])          # a little AO baked into colour for unlit viewers
    print(f"[paint] colour + AO done ({time.time() - t0:.1f}s)")

    # --- roughness ----------------------------------------------------------------------------------------
    rough = 0.86 - 0.10 * h1 + 0.04 * speck
    rough = np.where(skin_amt > 0.5, 0.58 - 0.08 * speck, rough)
    rough = rough + (0.50 - rough) * hand_amt * 0.8
    rough = rough + (0.45 - rough) * nail_amt
    rough = np.clip(rough, 0.25, 1.0)

    # --- normal map ---------------------------------------------------------------------------------------
    fur_amount = 1.0 - np.clip(skin_amt * 0.9 + hand_amt * 0.7 + ear_amt * 0.8, 0, 1)
    amp = 0.55 * fur_amount + 0.07 * (1 - fur_amount)
    amp = amp * (1 - 0.5 * M["tail"])             # tail hair is short
    nx = -gT * amp * 0.0011 * 12.0
    ny = -gB * amp * 0.0011 * 12.0
    # palm creases and finger pads: faint lines along the digit
    crease = np.sin(zc * 900 + y * 500) * 0.04 * palm_side * hands
    ny = ny + crease
    # mouth line: a dent whose slope tilts the normal across the line (vertical direction)
    wd = 0.0007
    dm = -2.0 * mouth_dz / (wd * wd) * np.exp(-(mouth_dz / wd) ** 2) * (fwd > 0.420) \
        * (1 - smoothstep(0.0165, 0.0205, np.abs(x))) * M["head"]
    dent = 0.0008
    nx = nx + dent * dm * Tt[:, 2]
    ny = ny + dent * dm * Bt[:, 2]
    nrm_ts = np.stack([nx, ny, np.ones_like(nx)], axis=1)
    nrm_ts /= np.linalg.norm(nrm_ts, axis=1, keepdims=True)

    def to_img(vals, channels):
        out = np.zeros((size, size, channels), np.float32)
        out[valid] = vals
        return out

    if args.debug:
        items = dict(skin_amt=skin_amt, face=face, mhead=M["head"], hand_amt=hand_amt, ear_amt=ear_amt, h1=h1,
                     ao=ao, nz=nz * 0.5 + 0.5, mtorso=M["torso"], mlimb=M["limb"], patch=patch, cheek=cheek_ruff,
                     ventral=ventral, ruff_crown=crown)
        for k, v in items.items():
            im = np.zeros((size, size, 3), np.float32)
            im[valid] = np.repeat(np.clip(v, 0, 1)[:, None], 3, 1)
            _, (qy, qx) = ndimage.distance_transform_edt(~valid, return_indices=True)
            im = im[qy, qx]
            Image.fromarray((im[::-1] * 255).astype(np.uint8)).save(os.path.join(args.out, f"dbg_{k}.png"))
        fim = np.zeros((size, size, 3), np.float32)
        fim[valid] = np.clip(fur, 0, 1)
        _, (qy, qx) = ndimage.distance_transform_edt(~valid, return_indices=True)
        Image.fromarray((fim[qy, qx][::-1] * 255).astype(np.uint8)).save(os.path.join(args.out, "dbg_fur.png"))
    alb = to_img(col, 3)
    nrm = to_img(nrm_ts * 0.5 + 0.5, 3)
    orm = to_img(np.stack([ao, rough, np.zeros_like(rough)], axis=1), 3)

    # --- gutters: grow charts outward so bilinear/mip sampling never pulls in empty texels ----------------------
    _, (iy, ix) = ndimage.distance_transform_edt(~valid, return_indices=True)
    for arr in (alb, nrm, orm):
        arr[:] = arr[iy, ix]
    flat_n = np.array([0.5, 0.5, 1.0], np.float32)
    far = ndimage.distance_transform_edt(~valid) > 14
    nrm[far] = flat_n
    alb[far] = 0.0

    def save(arr, name, fmt="PNG", **kw):
        img = Image.fromarray((np.clip(arr[::-1], 0, 1) * 255 + 0.5).astype(np.uint8))
        path = os.path.join(args.out, name)
        img.save(path, fmt, **kw)
        print(f"[paint] {name}  {os.path.getsize(path) / 1024:.0f} KB")
        return path

    save(alb, "monkey_albedo.png")
    save(nrm, "monkey_normal.png")
    save(orm, "monkey_orm.png")
    # debug
    dbg = np.zeros((size, size, 3), np.float32)
    dbg[valid] = np.stack([face, M["ear"], M["nail"]], axis=1)
    save(dbg, "debug_regions.png")
    save(to_img(np.repeat(ao[:, None], 3, 1), 3), "debug_ao.png")
    np.savez_compressed(os.path.join(args.out, "texel_cache.npz"), valid=valid)

    paint_eye(args)
    print(f"[paint] total {time.time() - t0:.1f}s")


def design_mouth_z():
    return 0.2988


def paint_eye(args, size=512):
    """Equirect texture for the eyeball: u = angle around the gaze axis, v = angle from the gaze pole."""
    rng = np.random.default_rng(7)
    u = (np.arange(size) + 0.5) / size
    v = (np.arange(size // 2) + 0.5) / (size // 2)
    U, Vv = np.meshgrid(u, v)
    theta = Vv * np.pi                    # 0 at the gaze pole
    phi = U * 2 * np.pi
    pupil = 1 - smoothstep(0.070 * np.pi, 0.088 * np.pi, theta)
    iris_r = 0.335 * np.pi
    iris = 1 - smoothstep(iris_r - 0.012, iris_r + 0.008, theta)
    limbus = smoothstep(iris_r - 0.060, iris_r - 0.005, theta) * (1 - smoothstep(iris_r, iris_r + 0.04, theta))
    # radial fibres: many fine spokes with slow irregular modulation (no wavy pattern)
    fib = rng.random(size)
    fib = np.convolve(np.tile(fib, 3), np.ones(3) / 3, mode="same")[size:2 * size]
    fibres = fib[(U * size).astype(int) % size]
    fibres2 = rng.random(size)[(U * size / 4).astype(int) % size]
    spokes = 0.55 * fibres + 0.45 * fibres2
    rad = np.clip((theta - 0.088 * np.pi) / (iris_r - 0.088 * np.pi), 0, 1)
    amber = np.array([0.60, 0.36, 0.12])
    brown = np.array([0.20, 0.10, 0.04])
    iris_col = mix(amber, brown, np.clip(rad * 1.25 + (spokes - 0.5) * 0.9, 0, 1))
    collarette = np.exp(-((rad - 0.28) / 0.07) ** 2)[..., None] * np.array([0.25, 0.18, 0.06])
    iris_col = np.clip(iris_col + collarette * 0.5, 0, 1)
    sclera = mix(np.array([0.62, 0.50, 0.40]), np.array([0.40, 0.28, 0.22]), smoothstep(0.30 * np.pi, 0.6 * np.pi, theta))
    col = mix(sclera, iris_col, iris)
    col = mix(col, np.array([0.035, 0.02, 0.015]), limbus * 0.8)
    col = mix(col, np.array([0.005, 0.005, 0.005]), pupil)
    img = Image.fromarray((np.clip(col, 0, 1) * 255 + 0.5).astype(np.uint8))
    path = os.path.join(args.out, "eye_albedo.png")
    img.save(path)
    print(f"[paint] eye_albedo.png {size}x{size // 2}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mesh", default="build/monkey/mesh.npz")
    ap.add_argument("--out", default="build/monkey/tex")
    ap.add_argument("--size", type=int, default=2048)
    ap.add_argument("--debug", action="store_true")
    paint(ap.parse_args())
