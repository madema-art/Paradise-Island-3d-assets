"""
Stage 1 for the castaway: sculpt (SDF -> marching cubes), close the lips, decimate with detail weighting, derive skin
weights from the primitives that built each surface point (+ face-rig overlays, twist bones, eyelid weights),
and unwrap into two atlases (head+neck, body).

  /opt/bpy-venv/bin/python tools/castaway/build_castaway_mesh.py --cache build/castaway/sculpt.npz --out build/castaway/mesh.npz

Output npz: V (n,3), F (m,3), N (n,3), W (n,nb), bones (nb,), uv (m,3,2), group (m,) 0 = head atlas, 1 = body atlas
"""
import argparse
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "monkey"))

import bpy  # noqa: E402

import hdesign  # noqa: E402
from build_monkey_mesh import adjacency, clean, improve_triangles, unwrap, vertex_normals  # noqa: E402
from hsdf import Grid  # noqa: E402
from meshutil import arrays_from_mesh, mesh_from_arrays, orient_outward  # noqa: E402

NECK_CUT = 1.700          # atlas split plane: above = head atlas
RESIDUAL_GAP = 0.0004     # lips are closed to a 0.8 mm dark mouth line


def sculpt(D, voxel):
    lo, hi = hdesign.mesh_bounds(D)
    g = Grid(lo, hi, voxel)
    t = time.time()
    for op, p, k in D.ops:
        g.apply(p, k, op)
    print(f"[sculpt] grid {g.shape} filled ({time.time() - t:.0f}s)")
    t = time.time()
    V, F = g.mesh()
    F = orient_outward(V, F)
    print(f"[sculpt] voxel={voxel * 1000:.2f}mm -> {len(V)} verts {len(F)} tris ({time.time() - t:.0f}s)")
    return V, F


def squeeze_lips(V):
    """Collapse the sculpted 4.5 mm lip slit to a 0.8 mm mouth line (the lips only; the oral cavity stays open)."""
    z0 = hdesign.MOUTH_Z
    x, f, z = V[:, 0], -V[:, 1], V[:, 2]
    dz = z - z0
    ad = np.abs(dz)
    sq = hdesign.LIP_SQUEEZE - RESIDUAL_GAP
    wz = np.clip(1.0 - (ad - hdesign.LIP_SQUEEZE) / 0.0075, 0.0, 1.0)
    wz = np.where(ad <= hdesign.LIP_SQUEEZE + 1e-6, 1.0, wz)
    wx = np.clip((0.0345 - np.abs(x)) / 0.010, 0.0, 1.0)
    wf = np.clip((f - 0.060) / 0.014, 0.0, 1.0)
    w = wz * wx * wf
    move = np.minimum(ad, sq) * w
    V = V.copy()
    V[:, 2] = z - np.sign(dz) * move
    print(f"[lips] squeezed {int((w > 0).sum())} vertices")
    return V


def decimation_weights(D, V):
    """Per-vertex freedom to collapse: 1 = free, small = protected."""
    w = np.ones(len(V), np.float32)

    def protect(c, r, floor, ramp=0.03):
        d = np.linalg.norm(V - np.asarray(c), axis=1)
        nonlocal w
        w = np.minimum(w, np.clip((d - r) / ramp, 0.0, 1.0) * (1.0 - floor) + floor)

    face = np.array([0.0, -0.045, 1.865])
    protect(face, 0.050, 0.10, 0.060)                        # eyes, nose, brows, lips
    protect(np.array([0.0, -0.05, 1.805]), 0.034, 0.05, 0.030)   # mouth + chin
    for t, s in (("L", 1.0), ("R", -1.0)):
        protect(D.lm[f"eye_{t}"] + np.array([0, -0.010, 0]), 0.026, 0.035, 0.020)
        protect(np.array([s * 0.0775, 0.004, 1.884]), 0.040, 0.14, 0.020)    # ears
    protect(np.array([0.0, 0.0, 1.900]), 0.115, 0.30, 0.080)  # rest of the head
    protect(np.array([0.0, 0.0, 1.700]), 0.060, 0.45, 0.050)  # neck
    Vf = V.astype(np.float32)
    for p in D.prims():
        b = p.bone or ""
        if b.startswith(("f_", "toe", "hallux")):
            cap = 0.40
        elif b.startswith("hand_"):
            cap = 0.60
        elif b.startswith(("forearm", "upper_arm", "shin", "thigh")):
            cap = 0.70
        elif b.startswith("foot_"):
            cap = 0.55
        else:
            continue
        near = p.dist(Vf) < 0.004
        w[near] = np.minimum(w[near], cap)
    # joints deform best with slightly denser meshes
    for key in ("shoulder", "elbow", "wrist", "hip", "knee", "ankle"):
        for t in ("L", "R"):
            protect(D.lm[f"{key}_{t}"], 0.040, 0.50, 0.035)
    return w


def decimate(D, V, F, target):
    me = mesh_from_arrays(bpy, "hi", V, F)
    ob = bpy.data.objects.new("hi", me)
    bpy.context.scene.collection.objects.link(ob)
    vg = ob.vertex_groups.new(name="free")
    w = decimation_weights(D, V)
    q = np.round(w * 40) / 40
    for val in np.unique(q):
        vg.add(np.nonzero(q == val)[0].tolist(), float(max(val, 0.025)), "REPLACE")
    mod = ob.modifiers.new("dec", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = target / len(F)
    mod.vertex_group = "free"
    mod.vertex_group_factor = 1.0
    t = time.time()
    dg = bpy.context.evaluated_depsgraph_get()
    me2 = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    V2, F2 = arrays_from_mesh(me2)
    print(f"[decimate] {len(F)} -> {len(F2)} tris ({time.time() - t:.0f}s)")
    bpy.data.objects.remove(ob)
    return V2, F2


def gauss(d, r):
    return np.exp(-2.0 * (d / r) ** 2)


def skin_weights(D, V, F):
    names = [n for n, b in D.bones.items() if b["deform"] and not n.startswith(("hair_", "cloth_"))]
    bidx = {b: i for i, b in enumerate(names)}
    prims = D.prims()
    Vf = V.astype(np.float32)
    S = np.empty((len(V), len(prims)), np.float32)
    for j, p in enumerate(prims):
        S[:, j] = -p.dist(Vf) / p.T
    S -= S.max(axis=1, keepdims=True)
    E = np.exp(S)
    W = np.zeros((len(V), len(names)), np.float32)
    for j, p in enumerate(prims):
        W[:, bidx[p.bone]] += E[:, j]
    W /= W.sum(axis=1, keepdims=True)

    x, f, z = V[:, 0], -V[:, 1], V[:, 2]
    # --- lips: no jaw weight above the mouth plane, no head weight below it (centre of the mouth only)
    jaw, head = bidx["jaw"], bidx["head"]
    ramp = np.clip((z - (hdesign.MOUTH_Z - 0.0010)) / 0.0020, 0.0, 1.0)
    zone = (np.abs(x) < 0.034) & (f > 0.012) & (np.abs(z - hdesign.MOUTH_Z) < 0.022)
    zone_w = np.clip((0.034 - np.abs(x)) / 0.008, 0.0, 1.0) * zone
    target_jaw = 1.0 - ramp                   # 1 below the mouth plane, 0 above
    cur = W[:, jaw] + W[:, head]
    new_jaw = cur * target_jaw
    W[:, jaw] = W[:, jaw] * (1 - zone_w) + new_jaw * zone_w
    W[:, head] = W[:, head] * (1 - zone_w) + (cur - new_jaw) * zone_w
    W /= W.sum(axis=1, keepdims=True)

    # --- smooth over the surface first, then lay the face-rig overlays on top
    A = adjacency(F, len(V))
    deg = np.asarray(A.sum(axis=1)).ravel()
    for _ in range(2):
        nb = (A @ W) / np.maximum(deg, 1)[:, None]
        W = 0.65 * W + 0.35 * nb

    O = np.zeros_like(W)                       # overlay weights (each column independent)
    frontal = f > 0.020
    for t, s in (("L", 1.0), ("R", -1.0)):
        ec = D.lm[f"eye_{t}"]
        # brow bones: skin above the lids, in front of the skull
        for part, r in (("in", 0.0150), ("mid", 0.0170), ("out", 0.0160)):
            hb = D.bones[f"brow_{part}_{t}"]["head"]
            d = np.linalg.norm(V - hb, axis=1)
            O[:, bidx[f"brow_{part}_{t}"]] = 0.92 * gauss(d, r) * frontal * (z > ec[2] + 0.008)
        hb = D.bones[f"cheek_{t}"]["head"]
        d = np.linalg.norm(V - hb, axis=1)
        O[:, bidx[f"cheek_{t}"]] = 0.80 * gauss(d, 0.024) * frontal
        hb = D.bones[f"lip_corner_{t}"]["head"]
        d = np.linalg.norm(V - hb, axis=1)
        O[:, bidx[f"lip_corner_{t}"]] = 0.95 * gauss(d, 0.0125) * (f > 0.045)
        # eyelids: skin on the sphere around the eyeball, weighted by elevation angle from the eye centre
        rel = V - ec
        fwd = -rel[:, 1]
        elev = np.degrees(np.arctan2(rel[:, 2], np.maximum(fwd, 1e-4)))
        lat = np.clip((0.0235 - np.abs(rel[:, 0])) / 0.0075, 0.0, 1.0)
        reach = np.clip((0.034 - np.linalg.norm(rel, axis=1)) / 0.012, 0.0, 1.0)
        front = fwd > -0.002
        up = np.clip((60.0 - elev) / 34.0, 0.0, 1.0) * (elev > 8.0)
        lo = np.clip((52.0 + elev) / 32.0, 0.0, 1.0) * (elev < -8.0)
        O[:, bidx[f"lid_up_{t}"]] = 0.98 * up * lat * reach * front
        O[:, bidx[f"lid_low_{t}"]] = 0.98 * lo * lat * reach * front
    # centre lips: only on the correct side of the mouth plane
    d = np.linalg.norm((V - np.array([0, -0.091, 1.807])) / np.array([0.017, 0.013, 0.0095]), axis=1)
    O[:, bidx["lip_up"]] = 0.95 * np.exp(-2.0 * d * d) * (z > hdesign.MOUTH_Z + 0.0002) * (f > 0.050)
    d = np.linalg.norm((V - np.array([0, -0.089, 1.783])) / np.array([0.017, 0.013, 0.0095]), axis=1)
    O[:, bidx["lip_low"]] = 0.95 * np.exp(-2.0 * d * d) * (z < hdesign.MOUTH_Z - 0.0002) * (f > 0.050)

    # a vertex gets at most one dominant overlay family; keep their sum <= 0.98
    tot = O.sum(axis=1, keepdims=True)
    O = np.where(tot > 0.98, O * (0.98 / np.maximum(tot, 1e-9)), O)
    tot = O.sum(axis=1, keepdims=True)
    W = W * (1.0 - tot) + O

    # --- forearm twist chain: forearm -> tw1 -> tw2 -> hand along the elbow-wrist axis
    for t in ("L", "R"):
        E_, W_ = D.lm[f"elbow_{t}"], D.lm[f"wrist_{t}"]
        ax = W_ - E_
        L2 = float(ax @ ax)
        u = ((V - E_) @ ax) / L2
        near = np.linalg.norm(V - (E_ + np.clip(u, -0.05, 1.1)[:, None] * ax), axis=1) < 0.060
        fa, tw1, tw2, ha = (bidx[f"forearm_{t}"], bidx[f"forearm_tw1_{t}"], bidx[f"forearm_tw2_{t}"], bidx[f"hand_{t}"])
        pool = W[:, fa] + W[:, tw1] + W[:, tw2]
        # share of the pool by position along the forearm (tent functions)
        s1 = np.clip(1.0 - np.abs(u - 0.38) / 0.33, 0.0, 1.0)
        s2 = np.clip(1.0 - np.abs(u - 0.72) / 0.30, 0.0, 1.0)
        s0 = np.clip(1.0 - u / 0.40, 0.0, 1.0) * (u < 0.40)
        s0 = np.where(u <= 0.0, 1.0, s0)
        tot = np.maximum(s0 + s1 + s2, 1e-6)
        mask = near & (u > 0.0) & (u < 0.98) & (pool > 0.2)
        # only move weight that belonged to the forearm family
        W[mask, fa] = (pool * s0 / tot)[mask]
        W[mask, tw1] = (pool * s1 / tot)[mask]
        W[mask, tw2] = (pool * s2 / tot)[mask]

    W[W < 0.012] = 0.0
    order = np.argsort(-W, axis=1)
    keep = np.zeros_like(W, dtype=bool)
    rows = np.arange(len(W))[:, None]
    keep[rows, order[:, :4]] = True
    W = np.where(keep, W, 0.0)
    W /= W.sum(axis=1, keepdims=True)
    return names, W.astype(np.float32)


def split_unwrap(V, F, res_head, res_body):
    """Unwrap the head+neck and the rest of the body into their own atlases. Returns uv (m,3,2), group (m,)."""
    cz = V[F][:, :, 2].mean(axis=1)
    group = np.where(cz > NECK_CUT, 0, 1).astype(np.int32)
    uv = np.zeros((len(F), 3, 2), np.float32)
    for g, res in ((0, res_head), (1, res_body)):
        idx = np.nonzero(group == g)[0]
        sub = F[idx]
        used = np.unique(sub)
        remap = -np.ones(len(V), np.int64)
        remap[used] = np.arange(len(used))
        vm, idx2, uv2 = unwrap(V[used], remap[sub], res)
        if not np.array_equal(vm[idx2], remap[sub]):
            raise SystemExit("xatlas reordered triangles")
        uv[idx] = uv2[idx2]
    return uv, group


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voxel", type=float, default=0.0015)
    ap.add_argument("--tris", type=int, default=46000)
    ap.add_argument("--res", type=int, default=2048)
    ap.add_argument("--out", default="build/castaway/mesh.npz")
    ap.add_argument("--cache", default=None)
    a = ap.parse_args()

    D = hdesign.build()
    if a.cache and os.path.exists(a.cache):
        z = np.load(a.cache)
        V, F = z["V"], z["F"]
        print(f"[sculpt] loaded cache {a.cache}: {len(F)} tris")
    else:
        V, F = sculpt(D, a.voxel)
        if a.cache:
            os.makedirs(os.path.dirname(os.path.abspath(a.cache)), exist_ok=True)
            np.savez(a.cache, V=V, F=F)
    V = squeeze_lips(V)
    V, F = decimate(D, V, F, a.tris)
    V, F = clean(V, F)
    F = orient_outward(V, F)
    F = improve_triangles(V, F)
    print(f"[mesh] {len(V)} verts, {len(F)} tris; head tris (z>{NECK_CUT}): {(V[F][:, :, 2].mean(1) > NECK_CUT).sum()}")
    names, W = skin_weights(D, V, F)
    N = vertex_normals(V, F)
    uv, group = split_unwrap(V, F, a.res, a.res)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    np.savez_compressed(a.out, V=V.astype(np.float32), F=F.astype(np.int32), N=N.astype(np.float32), W=W,
                        bones=np.array(names), uv=uv, group=group)
    print(f"[done] {a.out}")


if __name__ == "__main__":
    main()
