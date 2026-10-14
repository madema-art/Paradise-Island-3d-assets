"""
Stage 1: sculpt the monkey (SDF -> marching cubes), decimate it with detail weighting,
derive skin weights from the primitives that built each surface point, and unwrap with xatlas.

  /opt/bpy-venv/bin/python tools/monkey/build_monkey_mesh.py --out build/monkey/mesh.npz

Output npz: V (n,3), F (m,3), N (n,3), W (n,nb), bones (nb,), uv (m,3,2), regions...
"""
import argparse
import json
import os
import sys
import time

import numpy as np
import scipy.sparse as sp

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
import xatlas  # noqa: E402

import design  # noqa: E402
from meshutil import arrays_from_mesh, mesh_from_arrays, orient_outward  # noqa: E402
from sdf import Grid  # noqa: E402

MOUTH_Z = 0.2988  # plane where the upper lip meets the lower jaw


def sculpt(D, voxel):
    lo, hi = design.mesh_bounds(D)
    g = Grid(lo, hi, voxel)
    t = time.time()
    for op, p, k in D.ops:
        g.apply(p, k, op)
    V, F = g.mesh()
    F = orient_outward(V, F)
    print(f"[sculpt] voxel={voxel * 1000:.2f}mm grid={g.shape} -> {len(F)} tris ({time.time() - t:.1f}s)")
    return V, F


def decimation_weights(D, V):
    """Per-vertex freedom to collapse: 1 = free, small = protected.
    Eyes/muzzle strongest, a soft falloff over the rest of the head, digits moderate."""
    face = design.P(0, 0.428, 0.315)
    d = np.linalg.norm(V - face, axis=1)
    w = np.clip((d - 0.030) / 0.045, 0.0, 1.0) * 0.94 + 0.06   # 0.06 near the face -> 1.0 beyond 7.5cm
    skull = np.linalg.norm(V - design.P(0, 0.385, 0.328), axis=1)
    w = np.minimum(w, np.clip((skull - 0.045) / 0.050, 0.0, 1.0) * 0.8 + 0.2)   # keep the cranium/ears round
    Vf = V.astype(np.float32)
    for p in D.prims():
        if not p.bone:
            continue
        if p.bone.startswith(("f_", "t_")):
            cap = 0.55
        elif p.bone.startswith("tail_"):
            cap = 0.30            # thin tube: needs rings of triangles to stay round
        elif p.bone.startswith("ear_"):
            cap = 0.25
        elif p.bone.startswith(("forearm", "shin", "upper_arm", "thigh")):
            cap = 0.60
        else:
            continue
        near = p.dist(Vf) < 0.004
        w[near] = np.minimum(w[near], cap)
    return w.astype(np.float32)


def decimate(D, V, F, target, detail=True):
    me = mesh_from_arrays(bpy, "hi", V, F)
    ob = bpy.data.objects.new("hi", me)
    bpy.context.scene.collection.objects.link(ob)
    vg = ob.vertex_groups.new(name="free")
    w = decimation_weights(D, V)
    q = np.round(w * 40) / 40  # quantise so vertex_group.add batches stay small
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
    print(f"[decimate] {len(F)} -> {len(F2)} tris ({time.time() - t:.1f}s)")
    bpy.data.objects.remove(ob)
    return V2, F2


def clean(V, F):
    """Drop degenerate faces and unused vertices, keep winding outward."""
    a, b, c = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    area = np.linalg.norm(np.cross(b - a, c - a), axis=1)
    F = F[area > 1e-12]
    used = np.unique(F)
    remap = -np.ones(len(V), np.int64)
    remap[used] = np.arange(len(used))
    return V[used], remap[F]


def flip_pass(V, F):
    """One parallel pass of Delaunay edge flips (cot criterion); returns number of flips applied."""
    m, n = len(F), len(V)
    a = F.ravel()
    b = F[:, [1, 2, 0]].ravel()
    fid = np.repeat(np.arange(m), 3)
    loc = np.tile(np.arange(3), m)
    key, rkey = a * n + b, b * n + a
    order = np.argsort(key)
    sk = key[order]
    pos = np.clip(np.searchsorted(sk, rkey), 0, len(sk) - 1)
    has = sk[pos] == rkey
    opp = np.where(has, order[pos], -1)
    sel = np.nonzero(has & (fid < fid[np.clip(opp, 0, None)]))[0]
    he_i, he_j = sel, opp[sel]
    i, j = fid[he_i], fid[he_j]
    A, B = a[he_i], b[he_i]
    C = F[i, (loc[he_i] + 2) % 3]
    Dv = F[j, (loc[he_j] + 2) % 3]

    def cot(p, q, r):
        u, w = V[q] - V[p], V[r] - V[p]
        return (u * w).sum(1) / np.maximum(np.linalg.norm(np.cross(u, w), axis=1), 1e-18)

    crit = cot(C, A, B) + cot(Dv, B, A)
    cand = np.nonzero(crit < -1e-9)[0]
    existing = set((np.minimum(a, b) * n + np.maximum(a, b)).tolist())
    nrm = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    used = np.zeros(m, bool)
    flips = 0
    for k in cand[np.argsort(crit[cand])]:
        ii, jj = i[k], j[k]
        if used[ii] or used[jj]:
            continue
        c_, d_, a_, b_ = C[k], Dv[k], A[k], B[k]
        ekey = min(c_, d_) * n + max(c_, d_)
        if c_ == d_ or ekey in existing:
            continue
        t1, t2 = (a_, d_, c_), (d_, b_, c_)
        n1 = np.cross(V[t1[1]] - V[t1[0]], V[t1[2]] - V[t1[0]])
        n2 = np.cross(V[t2[1]] - V[t2[0]], V[t2[2]] - V[t2[0]])
        if n1 @ nrm[ii] <= 0 or n2 @ nrm[jj] <= 0 or n1 @ (nrm[ii] + nrm[jj]) <= 0 or n2 @ (nrm[ii] + nrm[jj]) <= 0:
            continue
        F[ii], F[jj] = t1, t2
        used[ii] = used[jj] = True
        existing.add(ekey)
        flips += 1
    return flips


def improve_triangles(V, F, passes=40):
    F = F.copy()
    total = 0
    for _ in range(passes):
        f = flip_pass(V, F)
        total += f
        if f == 0:
            break
    tri = V[F]
    area = 0.5 * np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1)
    e = np.stack([np.linalg.norm(tri[:, 1] - tri[:, 0], axis=1), np.linalg.norm(tri[:, 2] - tri[:, 1], axis=1),
                  np.linalg.norm(tri[:, 0] - tri[:, 2], axis=1)], 1)
    ar = e.max(1) / np.maximum(2 * area / e.max(1), 1e-12)
    print(f"[flips] {total} edge flips; sliver triangles (aspect>12): {(ar > 12).sum()}")
    return F


def vertex_normals(V, F):
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    N = np.zeros_like(V)
    for k in range(3):
        np.add.at(N, F[:, k], fn)
    n = np.linalg.norm(N, axis=1, keepdims=True)
    return N / np.maximum(n, 1e-12)


def adjacency(F, n):
    i = np.concatenate([F[:, 0], F[:, 1], F[:, 2], F[:, 1], F[:, 2], F[:, 0]])
    j = np.concatenate([F[:, 1], F[:, 2], F[:, 0], F[:, 0], F[:, 1], F[:, 2]])
    A = sp.coo_matrix((np.ones(len(i), np.float32), (i, j)), shape=(n, n)).tocsr()
    A.data[:] = 1.0
    return A


def skin_weights(D, V, F):
    names = list(D.bones.keys())
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

    # Upper lip / face must not follow the jaw: kill jaw weight above the mouth plane
    f_fwd = -V[:, 1]
    z = V[:, 2]
    jaw = bidx["jaw"]
    ramp = np.clip((z - (MOUTH_Z - 0.0012)) / 0.0024, 0.0, 1.0)
    ramp = np.where(f_fwd > 0.385, ramp, 0.0)
    moved = W[:, jaw] * ramp
    W[:, jaw] -= moved
    W[:, bidx["head"]] += moved

    W /= W.sum(axis=1, keepdims=True)
    # smooth over the surface, but never across the head/jaw lip line
    A = adjacency(F, len(V))
    deg = np.asarray(A.sum(axis=1)).ravel()
    for _ in range(3):
        nb = (A @ W) / np.maximum(deg, 1)[:, None]
        W = 0.6 * W + 0.4 * nb
    W[W < 0.015] = 0.0
    # keep strongest 4 influences
    order = np.argsort(-W, axis=1)
    keep = np.zeros_like(W, dtype=bool)
    rows = np.arange(len(W))[:, None]
    keep[rows, order[:, :4]] = True
    W = np.where(keep, W, 0.0)
    W /= W.sum(axis=1, keepdims=True)
    return names, W.astype(np.float32)


def unwrap(V, F, resolution):
    """xatlas unwrap into ONE square atlas: pick the largest texel density that still fits."""
    tri = V[F]
    area = 0.5 * np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1).sum()
    co = xatlas.ChartOptions()
    co.max_iterations = 2
    co.normal_deviation_weight = 0.4
    co.normal_seam_weight = 0.5
    tpu = np.sqrt(0.74 * resolution * resolution / area)
    for attempt in range(8):
        atlas = xatlas.Atlas()
        atlas.add_mesh(V.astype(np.float32), F.astype(np.uint32))
        po = xatlas.PackOptions()
        po.resolution = resolution
        po.texels_per_unit = float(tpu)
        po.padding = 6
        po.bilinear = True
        po.create_image = False
        atlas.generate(co, po)
        if atlas.atlas_count == 1 and atlas.width <= resolution and atlas.height <= resolution:
            break
        tpu *= 0.94
    vmapping, idx, uvs = atlas[0]
    uvs = np.asarray(uvs, np.float32)  # xatlas already returns 0..1 for a square atlas
    assert uvs.min() >= -1e-4 and uvs.max() <= 1.0 + 1e-4 and uvs.max() > 0.9, (uvs.min(), uvs.max())
    print(f"[xatlas] charts={atlas.chart_count} atlases={atlas.atlas_count} used={atlas.width}x{atlas.height} "
          f"of {resolution}^2 utilization={atlas.utilization:.3f} texels/mm={tpu / 1000:.2f}")
    return vmapping.astype(np.int64), idx.astype(np.int64), uvs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voxel", type=float, default=0.0015)
    ap.add_argument("--tris", type=int, default=30000)
    ap.add_argument("--res", type=int, default=2048)
    ap.add_argument("--out", default="build/monkey/mesh.npz")
    ap.add_argument("--cache", default=None, help="npz cache for the sculpted high-res mesh")
    a = ap.parse_args()

    D = design.build()
    cache = a.cache
    if cache and os.path.exists(cache):
        z = np.load(cache)
        V, F = z["V"], z["F"]
        print(f"[sculpt] loaded cache {cache}: {len(F)} tris")
    else:
        V, F = sculpt(D, a.voxel)
        if cache:
            np.savez(cache, V=V, F=F)
    V, F = decimate(D, V, F, a.tris)
    V, F = clean(V, F)
    F = orient_outward(V, F)
    F = improve_triangles(V, F)
    print(f"[mesh] {len(V)} verts, {len(F)} tris")

    names, W = skin_weights(D, V, F)
    N = vertex_normals(V, F)

    vmapping, idx2, uv2 = unwrap(V, F, a.res)
    # xatlas keeps triangle order; verify so UVs can be stored per corner on the welded mesh
    if not np.array_equal(vmapping[idx2], F):
        raise SystemExit("xatlas reordered triangles; per-corner mapping not implemented")
    uv = uv2[idx2]  # (m,3,2)

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    np.savez_compressed(a.out, V=V.astype(np.float32), F=F.astype(np.int32), N=N.astype(np.float32),
                        W=W, bones=np.array(names), uv=uv.astype(np.float32))
    print(f"[done] {a.out}")


if __name__ == "__main__":
    main()
