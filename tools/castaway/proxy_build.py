"""Low-poly proxy props for viewer testing of interaction clips (NOT final art): Canoe, Paddle, Boulder, Campfire, PalmTrunk, Log, Rock.

  /opt/bpy-venv/bin/python tools/castaway/proxy_build.py [--outdir build/castaway/props]
All use the castaway frame: Y up in the GLB, units metres. Each GLB has attach/marker empties (hand holds etc.) as child nodes.
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "monkey"))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
from staff_build import tube, merge  # noqa: E402


def loft(sections, ring_n=18):
    """sections: list of (y, [(x,z) ring points])"""
    V, F = [], []
    for y, ring in sections:
        for (x, z) in ring:
            V.append((x, y, z))
    n = len(sections[0][1])
    for i in range(len(sections) - 1):
        for j in range(n):
            a, b = i * n + j, i * n + (j + 1) % n
            c, d = (i + 1) * n + (j + 1) % n, (i + 1) * n + j
            F += [(a, b, c), (a, c, d)]
    return np.array(V), np.array(F)


def ellipsoid(c, r, nu=16, nv=10):
    V, F = [], []
    for i in range(nv + 1):
        th = np.pi * i / nv
        for j in range(nu):
            ph = 2 * np.pi * j / nu
            V.append((c[0] + r[0] * np.sin(th) * np.cos(ph), c[1] + r[1] * np.cos(th), c[2] + r[2] * np.sin(th) * np.sin(ph)))
    for i in range(nv):
        for j in range(nu):
            a, b = i * nu + j, i * nu + (j + 1) % nu
            F += [(a, b, b + nu), (a, b + nu, a + nu)]
    return np.array(V), np.array(F)


def noise_ellipsoid(c, r, seed, amp=0.12, nu=28, nv=18):
    V, F = ellipsoid((0, 0, 0), (1, 1, 1), nu, nv)
    rng = np.random.default_rng(seed)
    # low-frequency radial noise from a few random directions
    dirs = rng.standard_normal((9, 3))
    dirs /= np.linalg.norm(dirs, axis=1, keepdims=True)
    ph = rng.uniform(0, 6.28, 9)
    fr = rng.uniform(1.0, 3.0, 9)
    d = np.zeros(len(V))
    for k in range(9):
        d += np.sin((V @ dirs[k]) * fr[k] * 2.0 + ph[k])
    V = V * (1 + amp * d / 3.0)[:, None] * np.array(r) + np.array(c)
    return V, F


def build_canoe():
    L, W = 4.6, 0.70
    secs = []
    for y in np.linspace(-L / 2, L / 2, 30):
        u = y / (L / 2)
        k = np.sqrt(max(1 - abs(u) ** 3.2, 0.0))
        w = max(W * 0.5 * k, 0.012)
        rise = 0.22 * np.clip((abs(u) - 0.55) / 0.45, 0, 1) ** 1.5 * (1.0 if u < 0 else 0.7)    # bow/stern lift
        rail = 0.40 + rise
        keel = 0.02 + 0.5 * rise
        fl = 0.12 + 0.6 * rise
        t = min(0.04, w * 0.6)
        ring = [(w, rail), (w * 0.96, 0.24), (w * 0.5, keel + 0.01), (0.0, keel), (-w * 0.5, keel + 0.01), (-w * 0.96, 0.24), (-w, rail),
                (-(w - t), rail), (-(w - t) * 0.92, fl + 0.10), (-(w - t) * 0.4, fl), (0.0, fl - 0.005), ((w - t) * 0.4, fl), ((w - t) * 0.92, fl + 0.10), (w - t, rail)]
        secs.append((y, ring))
    hull = loft(secs)
    seat = tube(np.array([[-0.34, 0.0, 0.28], [0.34, 0.0, 0.28]]), np.array([0.06, 0.06]), sides=8)
    boom = merge([tube(np.array([[0.34, y, 0.42], [1.30, y, 0.30]]), np.array([0.025, 0.025]), sides=8) for y in (-0.9, 0.9)])
    fl = ellipsoid((1.30, 0.0, 0.20), (0.11, 1.60, 0.11), 16, 12)
    return {"Canoe_hull": (hull[0], hull[1], "wood_dark"), "Canoe_seat": (seat[0], seat[1], "wood"), "Canoe_booms": (boom[0], boom[1], "wood"),
            "Canoe_float": (fl[0], fl[1], "wood_dark")}, {"seat": (0, 0, 0.30), "bow": (0, -2.3, 0.4), "stern": (0, 2.3, 0.4), "gunwale_R": (-0.35, 0, 0.42), "gunwale_L": (0.35, 0, 0.42),
                                                            "rope_bow": (0, -2.35, 0.40), "floor": (0, 0, 0.12)}


def build_paddle():
    # Y-up GLB: blade tip at the origin, shaft along +Y, T-grip at the top
    L = 1.45
    shaft = tube(np.array([[0, 0.40, 0], [0, L, 0]]), np.array([0.017, 0.017]), sides=10)
    tgrip = tube(np.array([[-0.08, L, 0], [0.08, L, 0]]), np.array([0.018, 0.018]), sides=8)
    blade_secs = []
    for y in np.linspace(0, 0.48, 12):
        w = 0.075 * np.sin(np.pi * (0.15 + 0.85 * y / 0.48) ** 1.0) + 0.012 if y < 0.46 else 0.012
        w = 0.07 * (1 - ((y - 0.24) / 0.26) ** 4) + 0.012
        ring = [(w * np.cos(t), 0.012 * np.sin(t) * 1.0) for t in np.linspace(0, 2 * np.pi, 12, endpoint=False)]
        blade_secs.append((y, ring))
    blade = loft(blade_secs)
    return {"Paddle": (*merge([(blade[0], blade[1], np.zeros((len(blade[0]), 2))), (shaft[0], shaft[1], shaft[2]), (tgrip[0], tgrip[1], tgrip[2])])[:2], "wood")}, \
        {"grip_lower": (0, 0.55, 0), "grip_upper": (0, 1.25, 0), "tip": (0, 0, 0)}


def build_boulder():
    V, F = noise_ellipsoid((0, 0.30, 1.12), (0.85, 0.46, 0.70), 5, 0.10)
    V[:, 1] = np.maximum(V[:, 1], 0.0)
    marks = {"hold_1": (0.45, 0.55, 0.65), "hold_2": (-0.35, 0.85, 0.70), "lip": (0.0, 0.76, 0.46), "top": (0, 0.78, 1.12), "stand_base": (0.0, 0.0, 0.0)}
    return {"Boulder": (V, F, "stone")}, marks


def build_rock():
    V, F = noise_ellipsoid((0, 0.25, 0), (0.45, 0.26, 0.38), 11, 0.14)
    V[:, 1] = np.maximum(V[:, 1], 0.0)
    return {"Rock": (V, F, "stone")}, {"seat_top": (0, 0.50, 0.0)}


def build_log():
    pts = np.array([[x, 0.25, 0.0] for x in np.linspace(-0.7, 0.7, 12)])
    t = tube(pts, np.full(12, 0.22), sides=14)
    return {"Log": (t[0], t[1], "wood_dark")}, {"seat_top": (0, 0.47, 0.0)}


def build_campfire():
    parts = {}
    stones = []
    for k in range(9):
        a = 2 * np.pi * k / 9
        V, F = noise_ellipsoid((0.38 * np.cos(a), 0.07, 0.38 * np.sin(a)), (0.11, 0.08, 0.10), k + 3, 0.15, 12, 8)
        stones.append((V, F, np.zeros((len(V), 2))))
    st = merge(stones)
    parts["Fire_stones"] = (st[0], st[1], "stone")
    logs = []
    for k in range(4):
        a = np.pi * k / 4
        pts = np.array([[0.30 * np.cos(a) * s, 0.12 + 0.10 * (1 - abs(s)), 0.30 * np.sin(a) * s] for s in np.linspace(-1, 1, 6)])
        logs.append(tube(pts, np.full(6, 0.035), sides=8))
    lg = merge(logs)
    parts["Fire_logs"] = (lg[0], lg[1], "wood_dark")
    # flame: stacked cones
    fl = []
    for h, r in ((0.55, 0.17), (0.40, 0.12)):
        pts = np.array([[0.0, 0.14 + h * s, 0.0] for s in np.linspace(0, 1, 8)])
        rad = r * (1 - np.linspace(0, 1, 8) ** 1.5) + 0.002
        fl.append(tube(pts, rad, sides=10))
    fm = merge(fl)
    parts["Fire_flame"] = (fm[0], fm[1], "flame")
    return parts, {"flame_centre": (0, 0.35, 0), "tend_spot": (0, 0.1, 0.8)}


def build_palm():
    H = 5.2
    zs = np.linspace(0, H, 40)
    # trunk surface stays 0.36 m in front of the climber's axis (the clips' TRUNK_F); only the axis drifts sideways, so hands/feet meet bark at any height
    rad = 0.17 - 0.06 * (zs / H) + 0.008 * np.sin(zs * 18.0)
    pts = np.stack([0.30 * (zs / H) ** 2 * 1.0 + 0.05 * np.sin(zs * 0.8), zs, 0.36 + rad], 1)
    t = tube(pts, rad, sides=14, v_scale=1.0)
    fronds = []
    for k in range(9):
        a = 2 * np.pi * k / 9
        p0 = pts[-1]
        fp = np.array([p0 + np.array([np.cos(a), 0.0, np.sin(a)]) * (1.9 * s) + np.array([0, 0.5 * np.sin(np.pi * s * 0.8) - 0.9 * s ** 2, 0]) for s in np.linspace(0, 1, 8)])
        fronds.append(tube(fp, np.linspace(0.04, 0.005, 8), sides=5))
    fr = merge(fronds)
    marks = {f"hold_{i}": tuple(pts[int(i * 4 + 3)] + np.array([0, 0, -0.16])) for i in range(9)}
    marks["top"] = tuple(pts[-1] + np.array([0.0, 0.2, 0.0]))
    return {"Palm_trunk": (t[0], t[1], "wood"), "Palm_fronds": (fr[0], fr[1], "frond")}, marks


MATS = {"wood": (0.42, 0.29, 0.17, 0.8), "wood_dark": (0.26, 0.17, 0.10, 0.85), "stone": (0.30, 0.29, 0.27, 0.95), "frond": (0.18, 0.40, 0.14, 0.7),
        "flame": (1.0, 0.45, 0.08, 0.5)}


def export(name, parts, marks, outdir, native=False):
    import bpy
    from meshutil import mesh_from_arrays
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mats = {}
    for k, (r, g, b, ro) in MATS.items():
        m = bpy.data.materials.new(f"Proxy_{k}")
        m.use_nodes = True
        bs = m.node_tree.nodes["Principled BSDF"]
        bs.inputs["Base Color"].default_value = (r, g, b, 1)
        bs.inputs["Roughness"].default_value = ro
        if k == "flame":
            bs.inputs["Emission Color"].default_value = (1.0, 0.5, 0.1, 1)
            bs.inputs["Emission Strength"].default_value = 2.0
        mats[k] = m
    root = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(root)
    tri = 0
    for pn, (V, F, mk_) in parts.items():
        if not native:
            V = np.stack([V[:, 0], -V[:, 2], V[:, 1]], 1)         # authored Y-up -> Blender Z-up
        me = mesh_from_arrays(bpy, pn, V, F)
        me.materials.append(mats[mk_])
        for p in me.polygons:
            p.use_smooth = True
        ob = bpy.data.objects.new(pn, me)
        bpy.context.collection.objects.link(ob)
        ob.parent = root
        tri += len(F)
    for mn, pos in marks.items():
        e = bpy.data.objects.new(mn, None)
        e.location = tuple(pos) if native else (pos[0], -pos[2], pos[1])
        e.parent = root
        bpy.context.collection.objects.link(e)
    for o in bpy.data.objects:
        o.select_set(True)
    out = os.path.join(outdir, f"{name}.glb")
    bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", use_selection=True, export_yup=True, export_apply=False)
    print(f"[proxy] {out} {os.path.getsize(out) / 1024:.0f} KB {tri} tris")
    return tri


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default=os.path.join(ROOT, "build/castaway/props"))
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    info = {}
    for name, fn in (("Canoe", build_canoe), ("Paddle", build_paddle), ("Boulder", build_boulder), ("Rock", build_rock), ("Log", build_log), ("Campfire", build_campfire), ("PalmTrunk", build_palm)):
        parts, marks = fn()
        info[name] = dict(triangles=export(name, parts, marks, a.outdir, native=(name == 'Canoe')), markers={k: [float(x) for x in v] for k, v in marks.items()})
    json.dump(info, open(os.path.join(a.outdir, "proxies.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
