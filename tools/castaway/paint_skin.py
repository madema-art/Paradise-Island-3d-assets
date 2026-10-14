"""
Stage 2 for the castaway: paint the skin texture sets procedurally in UV space (head atlas + body atlas).

Same method as the monkey painter: rasterise the unwrapped mesh to get a world position / normal / tangent frame per texel,
then synthesise albedo, tangent-space normal and ORM as functions of that 3D data. Because colour is a continuous function
of world position, UV seams do not show in the albedo.

  /opt/bpy-venv/bin/python tools/castaway/paint_skin.py --mesh build/castaway/mesh.npz --out build/castaway/tex
"""
import argparse
import os
import sys
import time

import numpy as np
from PIL import Image
from scipy import ndimage
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "monkey"))

import hdesign  # noqa: E402
import skin_detail  # noqa: E402
from paint_textures import Noise3, interp, mix, rasterize, smoothstep, strands, triangle_tangents  # noqa: E402
from sdf_sampler import body_sampler  # noqa: E402

P3 = hdesign.P


def sstep(e0, e1, x):
    return smoothstep(e0, e1, x)


def box(x, lo, hi, soft):
    return sstep(lo - soft, lo, x) * (1.0 - sstep(hi, hi + soft, x))


# palette (sRGB, perceptual values)
C = dict(
    tan=np.array([0.440, 0.275, 0.170]),        # sun-exposed skin
    protected=np.array([0.610, 0.440, 0.320]),  # inner arms, armpits, tan lines
    face=np.array([0.500, 0.325, 0.215]),
    red=np.array([0.590, 0.320, 0.235]),        # sun-flushed nose / cheeks / ears
    lip=np.array([0.470, 0.255, 0.230]),
    lip_line=np.array([0.200, 0.095, 0.085]),
    eyelid=np.array([0.420, 0.265, 0.205]),
    lash=np.array([0.110, 0.070, 0.045]),
    waterline=np.array([0.560, 0.250, 0.230]),
    mucosa=np.array([0.430, 0.150, 0.150]),
    nostril=np.array([0.110, 0.050, 0.040]),
    ear=np.array([0.540, 0.320, 0.235]),
    palm=np.array([0.640, 0.470, 0.360]),
    sole=np.array([0.600, 0.450, 0.350]),
    nail=np.array([0.700, 0.520, 0.450]),
    freckle=np.array([0.290, 0.170, 0.105]),
    sunspot=np.array([0.350, 0.225, 0.150]),
    stubble=np.array([0.400, 0.315, 0.200]),
    hair_root=np.array([0.470, 0.355, 0.185]),
    hair_light=np.array([0.800, 0.680, 0.430]),
    body_hair=np.array([0.800, 0.680, 0.450]),
)


# ------------------------------------------------------------------------------------------------ dots (freckles etc.)
def _hash(ix, iy, iz, seed):
    h = (ix.astype(np.uint64) * np.uint64(73856093)) ^ (iy.astype(np.uint64) * np.uint64(19349663)) ^ \
        (iz.astype(np.uint64) * np.uint64(83492791)) ^ np.uint64(seed * 2654435761 % (2 ** 32))
    h &= np.uint64(0xFFFFFFFF)
    out = []
    for k in range(5):
        h = (h * np.uint64(1664525) + np.uint64(1013904223)) & np.uint64(0xFFFFFFFF)
        out.append((h >> np.uint64(8)).astype(np.float32) / np.float32(1 << 24))
    return out


def dots(P, cell, density, rmin, rmax, seed):
    """Scattered soft dots: returns coverage 0..1. density: per-point probability that a cell holds a dot."""
    q = P / cell
    base = np.floor(q).astype(np.int64)
    best = np.full(len(P), 9.0, np.float32)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                ix, iy, iz = base[:, 0] + dx, base[:, 1] + dy, base[:, 2] + dz
                r0, r1, r2, r3, r4 = _hash(ix, iy, iz, seed)
                cen = np.stack([ix + r0, iy + r1, iz + r2], 1) * cell
                rad = rmin + (rmax - rmin) * r3
                keep = r4 < density
                d = np.linalg.norm(P - cen, axis=1) / rad
                d = np.where(keep, d, 9.0)
                best = np.minimum(best, d.astype(np.float32))
    return 1.0 - sstep(0.55, 1.0, best)


# ------------------------------------------------------------------------------------------------ crease heights
def build_crease_trees(classes):
    trees = []
    for name, depth, sigma, polys in classes:
        pts = np.concatenate([skin_detail.resample(p, step=max(sigma * 0.5, 0.0003)) for p in polys])
        trees.append((name, depth, sigma, cKDTree(pts)))
    return trees


def crease_height(P, trees, mask=None):
    h = np.zeros(len(P), np.float32)
    for name, depth, sigma, tree in trees:
        d, _ = tree.query(P, distance_upper_bound=sigma * 3.2)
        d = np.where(np.isfinite(d), d, 1.0)
        h -= (depth * np.exp(-((d / sigma) ** 2))).astype(np.float32)
    return h


def body_creases(rig_lm):
    """Anatomical lines for the torso/limbs: collarbones, sternum, linea alba, abdominal tendons, ribs, navel, elbow/knee creases."""
    cls = []
    X = np.array([1.0, 0, 0])
    lines = []
    for s, t in skin_detail.SIDES:
        lines.append(skin_detail.arc(P3(s * 0.020, 0.062, 1.646), P3(s * 0.168, 0.020, 1.634), 0.0, 16))          # clavicle underside shade
        lines.append(skin_detail.arc(P3(s * 0.006, 0.108, 1.505), P3(s * 0.030, 0.112, 1.432), 0.0, 10))         # sternum edge
        lines.append(skin_detail.arc(P3(s * 0.043, 0.113, 1.430), P3(s * 0.114, 0.083, 1.455), 0.006, 16))       # pec lower border
        for z in (1.396, 1.338, 1.282):                                                                          # abdominal tendinous lines
            lines.append(skin_detail.arc(P3(s * 0.0035, 0.1085, z), P3(s * 0.050, 0.1015, z + 0.003), 0.0012, 10))
        lines.append(skin_detail.arc(P3(s * 0.050, 0.103, 1.420), P3(s * 0.055, 0.097, 1.205), 0.0, 20))          # rectus lateral border
        lines.append(skin_detail.arc(P3(s * 0.093, 0.090, 1.395), P3(s * 0.126, 0.060, 1.330), 0.0, 10))         # serratus
        lines.append(skin_detail.arc(P3(s * 0.084, 0.094, 1.370), P3(s * 0.122, 0.070, 1.298), 0.0, 10))
        lines.append(skin_detail.arc(P3(s * 0.110, 0.072, 1.305), P3(s * 0.135, 0.050, 1.240), 0.0, 10))
        lines.append(skin_detail.arc(P3(s * 0.082, 0.020, 1.250), P3(s * 0.138, 0.020, 1.150), 0.0, 14))          # iliac line
        lines.append(skin_detail.arc(P3(s * 0.012, 0.045, 1.640), P3(s * 0.040, 0.072, 1.700), 0.0, 8))          # neck cords
    lines.append(skin_detail.arc(P3(0, 0.103, 1.500), P3(0, 0.105, 1.200), 0.0, 24))                              # linea alba / sternal groove
    lines.append(skin_detail.arc(P3(0, -0.095, 1.600), P3(0, -0.085, 1.100), 0.0, 24))                            # spine groove
    cls.append(("torso_lines", 0.00055, 0.0020, lines))
    navel = [skin_detail.arc(P3(-0.006, 0.0975, 1.2145), P3(0.006, 0.0975, 1.2145), 0.002, 6)]
    cls.append(("navel", 0.0016, 0.0032, navel))
    rings = []
    for t in ("L", "R"):
        E, K = np.array(rig_lm[f"elbow_{t}"]), np.array(rig_lm[f"knee_{t}"])
        s = 1.0 if t == "L" else -1.0
        for dz in (-0.006, 0.0, 0.006):
            rings.append(skin_detail.arc(E + np.array([s * -0.020, -0.028, dz]), E + np.array([s * 0.024, -0.028, dz]), 0.0, 8))   # inner elbow creases
            rings.append(skin_detail.arc(K + np.array([-0.036, 0.046, dz * 1.5]), K + np.array([0.036, 0.046, dz * 1.5]), 0.0, 10))  # back of knee
    cls.append(("limb_creases", 0.00055, 0.0017, rings))
    return cls


MUSCLES = [
    # (name, centre (x, y, z) with y = -forward, radii (rx, ry, rz), amplitude m, mirror)
    ("pec", (0.078, -0.100, 1.495), (0.060, 0.050, 0.040), 0.0060, True),
    ("pec_upper", (0.070, -0.095, 1.560), (0.060, 0.040, 0.022), 0.0030, True),
    ("rectus1", (0.024, -0.104, 1.405), (0.022, 0.05, 0.024), 0.0032, True),
    ("rectus2", (0.024, -0.104, 1.345), (0.022, 0.05, 0.024), 0.0032, True),
    ("rectus3", (0.024, -0.102, 1.285), (0.022, 0.05, 0.024), 0.0030, True),
    ("rectus4", (0.023, -0.100, 1.225), (0.021, 0.05, 0.024), 0.0026, True),
    ("serratus", (0.108, -0.070, 1.350), (0.030, 0.05, 0.070), 0.0030, True),
    ("oblique", (0.115, -0.040, 1.230), (0.035, 0.06, 0.055), 0.0026, True),
    ("deltoid", (0.196, -0.004, 1.585), (0.045, 0.050, 0.060), 0.0045, True),
    ("trap", (0.060, 0.070, 1.625), (0.070, 0.05, 0.040), 0.0042, True),
    ("scapula", (0.090, 0.080, 1.520), (0.050, 0.05, 0.055), 0.0040, True),
    ("lat", (0.105, 0.065, 1.420), (0.055, 0.05, 0.090), 0.0036, True),
    ("erector", (0.026, 0.085, 1.340), (0.020, 0.05, 0.110), 0.0042, True),
    ("quad", (0.115, -0.060, 0.800), (0.045, 0.06, 0.150), 0.0032, True),
    ("calf", (0.098, 0.050, 0.370), (0.035, 0.05, 0.110), 0.0045, True),
    ("calf_front", (0.092, -0.050, 0.350), (0.020, 0.04, 0.130), 0.0022, True),
]


def limb_height(P):
    """Relief along the arms (biceps/triceps/forearm bellies, elbow bone) and legs (knee cap, shin crest) from the rest-pose landmarks."""
    return 0.0 * P[:, 0]


def muscle_height(P):
    h = np.zeros(len(P))
    for name, c, r, a, mir in MUSCLES:
        for s in ((1.0, -1.0) if mir else (1.0,)):
            cc = np.array([c[0] * s, c[1], c[2]])
            d = (P - cc) / np.array(r)
            # restrict each bump to its own side of the body (front muscles do not leak to the back)
            side = 1.0 / (1.0 + np.exp(-(np.sign(c[1]) * -(P[:, 1] - 0.0) * 0 + (np.sign(c[1]) * (P[:, 1] - c[1] * 0.0))) / 0.02)) if False else 1.0
            h += a * np.exp(-(d[:, 0] ** 2 + (d[:, 1] * 0.55) ** 2 + d[:, 2] ** 2)) * side
    return h


def digit_rings(D):
    """Skin creases around finger / toe joints (rings perpendicular to the digit axis)."""
    out_f, out_k = [], []
    for name, b in D.bones.items():
        if not name.startswith(("f_", "toe", "hallux")):
            continue
        a, c = b["head"], b["tail"]
        ax = (c - a) / np.linalg.norm(c - a)
        radius = 0.0090 if name.startswith("f_") else 0.0085
        u = np.cross(ax, [0.0, 0.0, 1.0])
        if np.linalg.norm(u) < 1e-4:
            u = np.cross(ax, [1.0, 0.0, 0.0])
        u /= np.linalg.norm(u)
        v = np.cross(ax, u)
        for off in (-0.0016, 0.0, 0.0016):
            ang = np.linspace(0, 2 * np.pi, 22)
            ring = [a + ax * off + (u * np.cos(t) + v * np.sin(t)) * radius for t in ang]
            (out_f if name.startswith("f_") else out_k).append(ring)
    return [("finger_rings", 0.00028, 0.00060, out_f), ("toe_rings", 0.00030, 0.00065, out_k)]


# ------------------------------------------------------------------------------------------------ main painter
def paint_group(z, D, sampler, group, size, outdir, tag, seed, debug=False):
    t0 = time.time()
    V, F, N, uv, grp = z["V"].astype(np.float64), z["F"].astype(np.int64), z["N"].astype(np.float64), z["uv"], z["group"]
    W, names = z["W"], [str(n) for n in z["bones"]]
    sel = np.nonzero(grp == group)[0]
    Fg, uvg = F[sel], uv[sel].astype(np.float64)
    tri, bary = rasterize(V, Fg, N, uvg, size)
    valid = tri >= 0
    print(f"[skin:{tag}] rasterised {valid.sum()} texels ({valid.mean() * 100:.1f}%) {time.time() - t0:.0f}s")
    Tt_f, Bt_f = triangle_tangents(V, Fg, uvg)
    P = interp(V, Fg, tri, bary, valid)
    Nn = interp(N, Fg, tri, bary, valid)
    Nn /= np.maximum(np.linalg.norm(Nn, axis=1, keepdims=True), 1e-9)
    Tt = Tt_f[tri[valid]]
    Bt = Bt_f[tri[valid]]
    Tt = Tt - Nn * (Tt * Nn).sum(1, keepdims=True)
    Tt /= np.maximum(np.linalg.norm(Tt, axis=1, keepdims=True), 1e-9)
    Bt = np.cross(Nn, Tt) * np.sign((np.cross(Tt, Bt) * Nn).sum(1, keepdims=True) + 1e-12)
    n_n = len(P)
    x, y, zc = P[:, 0], P[:, 1], P[:, 2]
    f = -y
    ax = np.abs(x)
    side = np.where(x >= 0, 1.0, -1.0)
    nz, nx_, nf = Nn[:, 2], Nn[:, 0], -Nn[:, 1]

    # vertex-level masks from skin weights
    idx = {n: i for i, n in enumerate(names)}

    def vmask(pred):
        cols = [i for n, i in idx.items() if pred(n)]
        return W[:, cols].sum(axis=1).astype(np.float64) if cols else np.zeros(len(W))

    def tmask(pred):
        return interp(vmask(pred)[:, None], Fg, tri, bary, valid)[:, 0]

    m_hand = tmask(lambda n: n.startswith(("hand_", "f_")))
    m_digit_f = tmask(lambda n: n.startswith("f_"))
    m_foot = tmask(lambda n: n.startswith(("foot_", "toe", "hallux")))
    m_toes = tmask(lambda n: n.startswith(("toe", "hallux")))
    m_nail = tmask(lambda n: (n.startswith("f_") and n.split("_")[2] == "3") or n.startswith("f_thumb_3")
                   or n.startswith(("toe2_1", "toe3_1", "toe4_1", "toe5_1", "hallux_2")))
    m_head = tmask(lambda n: n in ("head", "jaw") or n.startswith(("lid_", "brow_", "cheek_", "lip_", "eye_")))
    m_arm = tmask(lambda n: n.startswith(("upper_arm", "forearm", "clavicle")))
    m_leg = tmask(lambda n: n.startswith(("thigh", "shin")))

    # ----- noise
    nA, nB, nC, nD = Noise3(11 + seed), Noise3(12 + seed), Noise3(13 + seed), Noise3(14 + seed)
    patch = np.empty(n_n, np.float32)
    mott = np.empty(n_n, np.float32)
    pore = np.empty(n_n, np.float32)
    pore2 = np.empty(n_n, np.float32)
    flowv = np.zeros((n_n, 3))
    flowv[:, 2] = -1.0
    flowv = flowv - Nn * (flowv * Nn).sum(1, keepdims=True)
    fl = np.linalg.norm(flowv, axis=1, keepdims=True)
    flowv = np.where(fl > 0.05, flowv / np.maximum(fl, 1e-9), Tt)
    hair_h = np.empty(n_n, np.float32)
    ch = 300_000
    for s0 in range(0, n_n, ch):
        e0 = min(s0 + ch, n_n)
        p = P[s0:e0]
        patch[s0:e0] = nA(p, 0.045) * 0.55 + nA(p + 4.1, 0.016) * 0.45
        mott[s0:e0] = nB(p, 0.0075) * 0.6 + nB(p + 2.3, 0.0027) * 0.4
        pore[s0:e0] = nC(p, 0.00085)
        pore2[s0:e0] = nC(p + 9.1, 0.0022)
        hair_h[s0:e0] = 0.6 * strands(nD, p, flowv[s0:e0], 0.0012, 5, 0.0011) + 0.4 * strands(nD, p + 1.7, flowv[s0:e0], 0.0030, 4, 0.0028)
    print(f"[skin:{tag}] noise ({time.time() - t0:.0f}s)")

    # ----- anatomy / feature masks
    ear_c = {1.0: P3(0.0775, -0.004, 1.884), -1.0: P3(-0.0775, -0.004, 1.884)}
    m_face = box(f, 0.015, 0.20, 0.03) * box(zc, 1.742, 1.97, 0.02) * (m_head > 0.3)
    m_ear = np.zeros(n_n)
    for s_, c in ear_c.items():
        d = np.sqrt(((x - c[0]) / 0.020) ** 2 + ((y - c[1]) / 0.026) ** 2 + ((zc - c[2]) / 0.040) ** 2)
        m_ear = np.maximum(m_ear, (1 - sstep(0.85, 1.25, d)) * (side == s_))
    nose_d = np.sqrt((ax / 0.016) ** 2 + ((f - 0.104) / 0.024) ** 2 + ((zc - 1.836) / 0.026) ** 2)
    m_nose = 1 - sstep(0.7, 1.15, nose_d)
    m_nose_tip = 1 - sstep(0.55, 1.0, np.sqrt((ax / 0.013) ** 2 + ((f - 0.113) / 0.014) ** 2 + ((zc - 1.833) / 0.014) ** 2))
    m_cheek = (1 - sstep(0.7, 1.3, np.sqrt(((ax - 0.050) / 0.026) ** 2 + ((f - 0.058) / 0.030) ** 2 + ((zc - 1.842) / 0.026) ** 2))) * (f > 0.02)
    eye_d = {t: np.sqrt(((x - D.lm[f"eye_{t}"][0]) / 0.030) ** 2 + ((f - 0.082) / 0.030) ** 2 + ((zc - D.lm[f"eye_{t}"][2]) / 0.022) ** 2)
             for t in ("L", "R")}
    m_eye = np.maximum(1 - sstep(0.6, 1.1, eye_d["L"]), 1 - sstep(0.6, 1.1, eye_d["R"]))
    under_eye = np.zeros(n_n)
    for t in ("L", "R"):
        ec = D.lm[f"eye_{t}"]
        under_eye = np.maximum(under_eye, np.exp(-(((x - ec[0]) / 0.020) ** 2 + ((f - 0.078) / 0.020) ** 2 + ((zc - (ec[2] - 0.015)) / 0.008) ** 2)))
    # lips, mouth line, mouth interior
    mz = hdesign.MOUTH_Z
    lip_core = (1 - sstep(0.020, 0.0245, ax)) * (f > 0.080)
    m_lip = lip_core * (1 - sstep(0.0102, 0.0122, np.abs(zc - mz)))
    mouth_line = lip_core * (1 - sstep(0.0005, 0.0012, np.abs(zc - mz)))
    cav = next(p for op, p, k in D.ops if op == "sub" and p.name == "oral_cavity")
    mouth_in = (1 - sstep(0.0015, 0.0050, cav.dist(P.astype(np.float32)))) * (f < 0.084)
    # brows
    brow = np.zeros(n_n)
    for s_, t in ((1.0, "L"), (-1.0, "R")):
        for (x0, z0, x1, z1) in ((0.010, 1.9025, 0.030, 1.9055), (0.030, 1.9055, 0.052, 1.8985)):
            a = np.array([s_ * x0, z0])
            b = np.array([s_ * x1, z1])
            pq = np.stack([x, zc], 1) - a
            ab = b - a
            tt = np.clip((pq @ ab) / (ab @ ab), 0, 1)
            dd = np.linalg.norm(pq - tt[:, None] * ab, axis=1)
            brow = np.maximum(brow, np.exp(-(dd / 0.0075) ** 2) * (f > 0.05))
    # beard / scalp
    ear_gap = np.ones(n_n)
    for s_, c in ear_c.items():
        ear_gap *= 1 - (1 - sstep(0.020, 0.036, np.sqrt((x - c[0]) ** 2 + (y - c[1]) ** 2 + (zc - c[2]) ** 2))) * (side == s_)
    hairline_z = 1.936 - 0.030 * sstep(0.020, 0.075, ax)
    scalp_front = sstep(hairline_z + 0.002, hairline_z + 0.014, zc) * (f > -0.02)
    scalp_back = sstep(1.800, 1.830, zc) * (f <= 0.015)
    m_scalp = np.clip(np.maximum(scalp_front, scalp_back), 0, 1) * (m_head > 0.25) * ear_gap * (1 - m_face * sstep(0.080, 0.095, f) * sstep(1.935, 1.90, zc))
    cheek_line = 1.856 - 0.012 * sstep(0.020, 0.055, ax)
    m_beard = sstep(cheek_line, cheek_line - 0.016, zc) * (f > -0.045) * (zc > 1.690) * ear_gap * (m_head > 0.15) * (1 - m_lip * 0.97) \
        * (1 - mouth_in) * (1 - m_nose * 0.9)
    m_beard = np.clip(m_beard, 0, 1) * (1 - sstep(1.725, 1.690, zc))
    neck_blend = sstep(1.775, 1.735, zc)
    m_beard_neck = m_beard * neck_blend
    m_stache = (1 - sstep(0.026, 0.040, ax)) * box(zc, mz + 0.0009, 1.826, 0.004) * (f > 0.060) * (1 - m_nose * 0.8)
    m_hairy = np.clip(np.maximum.reduce([m_scalp, m_beard, m_stache, brow]), 0, 1)

    # landmarks for rough/dark skin areas
    lm = D.lm
    rough_pts = []
    for t in ("L", "R"):
        rough_pts += [(np.array(lm[f"elbow_{t}"]) + np.array([0, 0.030, 0.0]), 0.040), (np.array(lm[f"knee_{t}"]) + np.array([0, -0.030, 0.0]), 0.042),
                      (np.array(lm[f"knee_{t}"]) + np.array([0, 0.040, 0.0]), 0.040), (np.array(lm[f"ankle_{t}"]) + np.array([0, 0.040, -0.040]), 0.045)]
    m_rough = np.zeros(n_n)
    for c, r in rough_pts:
        m_rough = np.maximum(m_rough, 1 - sstep(0.4 * r, r, np.linalg.norm(P - c, axis=1)))
    # knuckles (back of hands) and toe tops
    m_knuckle = np.zeros(n_n)
    for t in ("L", "R"):
        for fn in ("index", "middle", "ring", "pinky"):
            c = D.bones[f"f_{fn}_1_{t}"]["head"]
            m_knuckle = np.maximum(m_knuckle, 1 - sstep(0.004, 0.014, np.linalg.norm(P - c, axis=1)))
    m_heel = np.zeros(n_n)
    for t in ("L", "R"):
        c = np.array(lm[f"ankle_{t}"]) + np.array([0, 0.056, -0.060])
        m_heel = np.maximum(m_heel, 1 - sstep(0.012, 0.034, np.linalg.norm(P - c, axis=1)))
    # palms / soles: surfaces whose normal faces the palm / ground
    palm_n = np.where((x >= 0)[:, None], np.array(D.lm["hand_frame_L"][2]), np.array(D.lm["hand_frame_R"][2]))
    palm_side = sstep(0.15, 0.65, (Nn * palm_n).sum(1))
    m_palm = np.clip(m_hand * palm_side, 0, 1)
    m_sole = m_foot * sstep(-0.15, -0.65, nz)
    # tan lines: the maro covers hips -> the skin underneath stays pale
    m_cover = box(zc, float(hdesign.zmap(0.915)), float(hdesign.zmap(1.115)), 0.035) * (1 - sstep(0.205, 0.245, ax)) * (1 - m_arm)
    m_cover = np.clip(m_cover * (0.55 + 0.45 * patch), 0, 1)

    # ----- albedo
    sun = sstep(-0.35, 0.85, nz) * 0.75 + 0.25
    inner = np.clip(-side * nx_, 0, 1) * np.clip(m_arm + m_leg * 0.8, 0, 1)
    under = sstep(0.0, -0.8, nz) * 0.55
    sun = np.clip(sun - 0.60 * inner - under, 0.0, 1.0)
    chest = box(zc, 1.30, 1.62, 0.05) * (f > 0.0)
    sun *= 1.0 - 0.18 * chest * (m_arm < 0.4)
    col = mix(C["protected"], C["tan"], sun)
    col = mix(col, C["face"], np.clip(m_face + m_head * 0.7, 0, 1) * 0.85)
    col = col * (1.0 + 0.10 * (patch[:, None] - 0.5)) * (1.0 + 0.045 * (mott[:, None] - 0.5))
    col = mix(col, C["red"], np.clip(0.55 * m_nose_tip + 0.34 * m_cheek + 0.15 * m_nose, 0, 1))
    col = mix(col, C["red"], 0.30 * np.clip(box(zc, 1.54, 1.665, 0.03) * sstep(0.02, 0.10, ax) * (nz > 0.2), 0, 1))
    col = mix(col, C["ear"], m_ear * 0.9)
    col = mix(col, C["eyelid"], np.clip(m_eye * 0.55 + under_eye * 0.45, 0, 1) * (m_head > 0.3))
    col = mix(col, C["protected"], 0.65 * m_cover)
    # dry, darker skin over joints; callused soles / palms
    col = col * (1 - 0.14 * np.clip(m_rough + m_knuckle * 0.7 + m_heel * 0.8, 0, 1))[:, None]
    col = mix(col, C["palm"], np.clip(m_palm * 0.9, 0, 1))
    col = mix(col, C["sole"], np.clip(m_sole * 0.92, 0, 1))
    col = col * (1 - 0.12 * np.clip(m_heel * m_sole, 0, 1))[:, None]
    # lips
    lip_tone = mix(C["lip"], C["lip"] * 1.08, (zc < mz) * 1.0)
    col = mix(col, lip_tone, np.clip(m_lip * 0.88, 0, 1))
    col = mix(col, C["lip_line"], np.clip(mouth_line * 0.92, 0, 1))
    col = mix(col, C["mucosa"], np.clip(mouth_in * 1.0, 0, 1))
    # nostrils and lash lines from the carving primitives
    for t in ("L", "R"):
        nost = next(p for op, p, k in D.ops if op == "sub" and p.name == f"nostril_{t}")
        dn = nost.dist(P.astype(np.float32))
        col = mix(col, C["nostril"], (1 - sstep(0.0, 0.0030, dn)) * 0.95)
        slit = next(p for op, p, k in D.ops if op == "sub" and p.name == f"palpebral_{t}")
        ds = slit.dist(P.astype(np.float32))
        lash = (1 - sstep(0.0009, 0.0026, np.abs(ds))) * (f > 0.05)
        wl = (1 - sstep(0.0005, 0.0020, ds + 0.0004)) * (ds < 0.0016) * (f > 0.05)
        col = mix(col, C["waterline"], np.clip(wl * 0.8, 0, 1))
        col = mix(col, C["lash"], np.clip(lash * 0.85, 0, 1))
    # freckles + sunspots (sun-exposed, fair-skinned places)
    freck_d = np.clip(0.55 * m_nose + 0.45 * m_cheek + 0.30 * m_face * 0.6 + 0.50 * box(zc, 1.50, 1.68, 0.04) * (nz > 0.15)
                      + 0.40 * m_arm * sstep(0.2, 0.9, nz) + 0.30 * box(zc, 1.38, 1.62, 0.05) * (nz < -0.2) + 0.15 * chest, 0, 1)
    freck_d = freck_d * (0.55 + 0.9 * patch) * (1 - m_hairy)
    fr = np.zeros(n_n, np.float32)
    for s_i in range(2):
        fr = np.maximum(fr, dots(P, 0.0026, np.clip(freck_d * (1.0 - 0.3 * s_i), 0, 1) * (0.35 + 1.3 * mott), 0.00030, 0.00095, seed + 3 + s_i))
    sp = dots(P, 0.011, np.clip((freck_d * 0.55 + 0.20 * m_arm + 0.15 * m_hand * (1 - palm_side)) * (0.6 + patch), 0, 1) * 0.55, 0.0018, 0.0048, seed + 9)
    col = mix(col, C["sunspot"], np.clip(sp * 0.50, 0, 1))
    col = mix(col, C["freckle"], np.clip(fr * 0.40, 0, 1))
    # nails
    dorsal = np.where((m_toes > 0.4)[:, None] | (m_foot > 0.4)[:, None], (nz > 0.35)[:, None] * 1.0, ((Nn * palm_n).sum(1) < -0.25)[:, None] * 1.0)[:, 0]
    nail_amt = np.clip((m_nail - 0.55) * 4.0, 0, 1) * dorsal
    nail_col = mix(C["nail"], np.array([0.84, 0.70, 0.62]), 0.5 * hair_h)
    col = mix(col, nail_col, nail_amt * 0.92)
    # hairy areas: sun-bleached body hair on limbs/chest, hair roots under scalp/beard/brows
    body_hair_d = np.clip(0.75 * (m_arm * box(zc, 0.9, 1.28, 0.05)) + 0.8 * m_leg * box(zc, 0.12, 1.05, 0.05) + 0.45 * chest * (m_arm < 0.3)
                          + 0.35 * m_hand * (1 - palm_side) + 0.25 * m_foot * (1 - m_sole), 0, 1) * (1 - m_head) * (1 - m_palm) * (1 - m_nail * 0.9)
    bh = np.clip((hair_h - 0.46) * 5.0, 0, 1) * body_hair_d * (0.55 + 0.7 * patch)
    col = mix(col, C["body_hair"] * (0.9 + 0.25 * hair_h[:, None]), np.clip(bh * 0.55, 0, 1))
    scalp_col = mix(C["hair_root"], C["hair_light"], np.clip(hair_h * 1.3 - 0.15, 0, 1) * 0.6 + 0.25 * patch)
    stub = mix(C["stubble"], C["hair_light"], np.clip(hair_h * 1.2 - 0.2, 0, 1) * 0.5 + 0.1)
    col = mix(col, stub, np.clip(m_beard * 0.74 + m_stache * 0.8, 0, 1) * (1 - 0.25 * m_beard_neck))
    col = mix(col, scalp_col, np.clip(m_scalp * 0.95, 0, 1))
    col = mix(col, C["hair_root"] * (0.75 + 0.5 * hair_h[:, None]), np.clip(brow * 0.9, 0, 1))
    col = np.clip(col, 0, 1)
    print(f"[skin:{tag}] albedo ({time.time() - t0:.0f}s)")

    # ----- AO
    occ = np.zeros(n_n, np.float32)
    s0 = sampler.dist(P)                       # the coarse field is ~2 mm off the true surface: calibrate each probe
    for i, td in enumerate((0.010, 0.020, 0.036, 0.060, 0.090)):
        occ += (td - (sampler.dist(P + Nn * td) - s0)).clip(0, None) / td / (1.0 + 0.7 * i)
    ao = np.clip(1.0 - 0.40 * occ, 0.42, 1.0).astype(np.float32)
    col = col * (0.86 + 0.14 * ao[:, None])

    # ----- roughness
    rough = 0.64 - 0.06 * pore2 + 0.04 * mott
    rough = rough - 0.13 * np.clip(m_nose * 0.8 + sstep(1.915, 1.96, zc) * m_face * 0.6, 0, 1)
    rough = rough + 0.16 * np.clip(m_rough + m_heel + m_knuckle * 0.5, 0, 1)
    rough = rough + 0.10 * (m_palm + m_sole)
    rough = rough + (0.88 - rough) * np.clip(m_hairy, 0, 1) * 0.9
    rough = rough + (0.40 - rough) * np.clip(m_lip, 0, 1)
    rough = rough + (0.28 - rough) * np.clip(mouth_in + nail_amt * 0.4, 0, 1)
    rough = np.clip(rough, 0.22, 1.0).astype(np.float32)

    # ----- height field -> normal map
    eps = 0.00045

    def micro(q, amp_scale):
        return amp_scale

    def height(q, with_creases=True):
        # pores
        hh = np.empty(len(q), np.float32)
        for s0 in range(0, len(q), ch):
            e0 = min(s0 + ch, len(q))
            p = q[s0:e0]
            pores = nC(p, 0.00085) * 0.55 + nC(p + 9.1, 0.0022) * 0.45
            hh[s0:e0] = (pores - 0.5) * 0.000085
            if group == 1 and with_creases:
                hh[s0:e0] += muscle_height(p) * 0.55 + limb_height(p)
        return hh

    h0 = height(P)
    hT = height(P + Tt * eps)
    hB = height(P + Bt * eps)
    # amplitude modulation: smoother lips/nails, rougher cheeks/nose/hands, creased joints
    amp = 1.0 + 0.6 * m_nose + 0.4 * m_rough + 0.3 * m_knuckle - 0.8 * np.clip(m_lip, 0, 1) - 0.7 * nail_amt
    gT = (hT - h0) / eps * amp
    gB = (hB - h0) / eps * amp
    # creases (face on the head atlas, torso/limb lines + digit rings on the body atlas)
    classes = skin_detail.face_classes() if group == 0 else body_creases(D.lm) + digit_rings(D)
    trees = build_crease_trees(classes)
    c0 = crease_height(P, trees)
    cT = crease_height(P + Tt * eps, trees)
    cB = crease_height(P + Bt * eps, trees)
    crease_amp = 1.0 - 0.8 * np.clip(m_hairy * 0.7, 0, 1)
    gT += (cT - c0) / eps * crease_amp
    gB += (cB - c0) / eps * crease_amp
    # stubble relief
    st = dots(P, 0.0016, np.clip(m_beard + m_stache, 0, 1) * 0.9, 0.00030, 0.00060, seed + 21)
    stT = dots(P + Tt * eps, 0.0016, np.clip(m_beard + m_stache, 0, 1) * 0.9, 0.00030, 0.00060, seed + 21)
    stB = dots(P + Bt * eps, 0.0016, np.clip(m_beard + m_stache, 0, 1) * 0.9, 0.00030, 0.00060, seed + 21)
    gT += (stT - st) / eps * 0.00012
    gB += (stB - st) / eps * 0.00012
    # mouth line dent
    dm = -2.0 * (zc - mz) / (0.0007 ** 2) * np.exp(-(((zc - mz) / 0.0007) ** 2)) * lip_core
    gT += 0.0006 * dm * Tt[:, 2]
    gB += 0.0006 * dm * Bt[:, 2]
    k = 1.0
    nrm_ts = np.stack([-gT * k, -gB * k, np.ones_like(gT)], 1)
    nrm_ts /= np.linalg.norm(nrm_ts, axis=1, keepdims=True)
    print(f"[skin:{tag}] normal ({time.time() - t0:.0f}s)")

    def to_img(vals, c):
        out = np.zeros((size, size, c), np.float32)
        out[valid] = vals
        return out

    alb = to_img(col, 3)
    nrm = to_img(nrm_ts * 0.5 + 0.5, 3)
    orm = to_img(np.stack([ao, rough, np.zeros_like(rough)], axis=1), 3)
    _, (iy, ix) = ndimage.distance_transform_edt(~valid, return_indices=True)
    for arr in (alb, nrm, orm):
        arr[:] = arr[iy, ix]
    far = ndimage.distance_transform_edt(~valid) > 14
    nrm[far] = np.array([0.5, 0.5, 1.0], np.float32)
    alb[far] = 0.0
    os.makedirs(outdir, exist_ok=True)

    def save(arr, name):
        img = Image.fromarray((np.clip(arr[::-1], 0, 1) * 255 + 0.5).astype(np.uint8))
        path = os.path.join(outdir, name)
        img.save(path, "PNG")
        print(f"[skin:{tag}] {name} {os.path.getsize(path) / 1024:.0f} KB")

    save(alb, f"skin_{tag}_albedo.png")
    save(nrm, f"skin_{tag}_normal.png")
    save(orm, f"skin_{tag}_orm.png")
    if debug:
        for nm, v in dict(face=m_face, lip=m_lip, beard=m_beard, scalp=m_scalp, brow=brow, nail=nail_amt, rough=m_rough,
                          cover=m_cover, palm=m_palm, sole=m_sole, ear=m_ear, hairy=m_hairy, bodyhair=bh, freck=fr).items():
            im = np.zeros((size, size, 3), np.float32)
            im[valid] = np.repeat(np.clip(v, 0, 1)[:, None], 3, 1)
            im = im[iy, ix]
            Image.fromarray((im[::-1] * 255).astype(np.uint8)).save(os.path.join(outdir, f"dbg_{tag}_{nm}.png"))
    print(f"[skin:{tag}] total {time.time() - t0:.0f}s")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mesh", default="build/castaway/mesh.npz")
    ap.add_argument("--out", default="build/castaway/tex")
    ap.add_argument("--size", type=int, default=2048)
    ap.add_argument("--groups", default="head,body")
    ap.add_argument("--debug", action="store_true")
    a = ap.parse_args()
    z = np.load(a.mesh)
    D = hdesign.build()
    sampler = body_sampler()
    for tag, g in (("head", 0), ("body", 1)):
        if tag in a.groups.split(","):
            paint_group(z, D, sampler, g, a.size, a.out, tag, seed=7 * (g + 1), debug=a.debug)


if __name__ == "__main__":
    main()
