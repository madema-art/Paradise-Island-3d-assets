"""
Dev tool: sculpt the castaway at a chosen voxel size and render clay views (Workbench, orthographic).

  /opt/bpy-venv/bin/python tools/castaway/preview_sculpt.py --voxel 0.004 --out /tmp/c.png --views front,side,face
"""
import argparse
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
import mathutils  # noqa: E402
from PIL import Image  # noqa: E402

import hdesign  # noqa: E402
from hsdf import Grid  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(HERE), "monkey"))
from meshutil import mesh_from_arrays, orient_outward  # noqa: E402


REGIONS = {
    "head": ((-0.11, -0.17, 1.68), (0.11, 0.13, 2.04)),
    "hand": ((0.28, -0.20, 0.72), (0.58, 0.20, 1.02)),
    "foot": ((0.0, -0.28, -0.01), (0.20, 0.12, 0.20)),
    "torso": ((-0.30, -0.16, 0.90), (0.30, 0.16, 1.72)),
    "arm": ((0.10, -0.12, 1.20), (0.50, 0.12, 1.72)),
    "leg": ((-0.02, -0.28, 0.0), (0.24, 0.16, 1.05)),
}


def sculpt(D, voxel, region=None):
    lo, hi = hdesign.mesh_bounds(D)
    if region:
        lo, hi = np.array(REGIONS[region][0]), np.array(REGIONS[region][1])
    g = Grid(lo, hi, voxel)
    t = time.time()
    for op, p, k in D.ops:
        g.apply(p, k, op)
    print(f"[sdf] grid {g.shape} filled in {time.time() - t:.1f}s")
    t = time.time()
    V, F = g.mesh()
    F = orient_outward(V, F)
    print(f"[sdf] marching cubes {len(V)} verts / {len(F)} tris in {time.time() - t:.1f}s")
    return V, F


# name -> (direction from centre to camera [blender world], centre, ortho scale)
def view_table(D):
    head = np.array([0.0, -0.04, 1.89])
    return {
        "front": ((0, -1, 0), (0, 0, 1.0), 2.25),
        "side": ((1, 0, 0), (0, 0, 1.0), 2.25),
        "back": ((0, 1, 0), (0, 0, 1.0), 2.25),
        "tq": ((0.7, -0.7, 0.15), (0, 0, 1.0), 2.25),
        "face": ((0, -1, 0.05), head, 0.34),
        "face_tq": ((0.62, -0.78, 0.08), head, 0.34),
        "face_side": ((1, 0, 0.02), head, 0.34),
        "upper": ((0, -1, 0), (0, 0, 1.5), 1.1),
        "upper_back": ((0, 1, 0), (0, 0, 1.5), 1.1),
        "upper_tq": ((0.6, -0.8, 0.1), (0, 0, 1.45), 1.1),
        "hand": ((0.7, -0.7, 0.3), D.lm["wrist_L"] + np.array([0.04, -0.02, -0.08]), 0.34),
        "hand_back": ((1, 0.0, 0.3), D.lm["wrist_L"] + np.array([0.04, -0.02, -0.08]), 0.34),
        "foot": ((0.8, -0.6, 0.3), np.array([0.10, -0.08, 0.06]), 0.40),
        "foot_side": ((1, 0, 0.1), np.array([0.10, -0.08, 0.06]), 0.40),
        "legs": ((0.5, -0.8, 0.1), (0, 0, 0.55), 1.2),
        "legs_side": ((1, 0, 0.1), (0, 0, 0.55), 1.2),
        "torso_tq": ((0.75, -0.65, 0.15), (0, 0, 1.30), 1.0),
        "top": ((0, 0, 1), (0, 0, 1.9), 0.5),
        "face_lo": ((0, -1, -0.15), head, 0.30),
        "eye": ((0.25, -1, 0.05), np.array([0.032, -0.06, 1.88]), 0.12),
        "mouth": ((0.2, -1, 0.0), np.array([0.0, -0.09, 1.79]), 0.14),
        "nose_side": ((1, 0, 0.0), np.array([0.0, -0.07, 1.85]), 0.20),
        "hip": ((0.6, -0.8, 0.1), (0, 0, 1.02), 0.60),
        "hip_back": ((0.4, 0.9, 0.1), (0, 0, 1.02), 0.60),
        "knee": ((0.7, -0.7, 0.1), (0.098, -0.02, 0.52), 0.30),
        "shoulder": ((0.6, -0.8, 0.2), (0.17, 0, 1.60), 0.40),
        "shoulder_back": ((0.4, 0.9, 0.2), (0.17, 0, 1.60), 0.40),
    }


def render(D, V, F, out, names, size=640, eyes=True):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    me = mesh_from_arrays(bpy, "m", V, F)
    ob = bpy.data.objects.new("m", me)
    sc = bpy.context.scene
    sc.collection.objects.link(ob)
    for p in me.polygons:
        p.use_smooth = True
    ob.color = (0.74, 0.60, 0.48, 1.0)
    if eyes:
        for t in ("L", "R"):
            bpy.ops.mesh.primitive_uv_sphere_add(radius=hdesign.EYE_R, location=tuple(D.lm[f"eye_{t}"]), segments=32, ring_count=16)
            e = bpy.context.active_object
            e.color = (0.95, 0.93, 0.9, 1.0)
            bpy.ops.object.shade_smooth()
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light, sh.color_type = "STUDIO", "OBJECT"
    sh.show_cavity = True
    sc.display.shading.show_object_outline = False
    sc.render.resolution_x = sc.render.resolution_y = size
    sc.world = bpy.data.worlds.new("w")
    sc.world.color = (0.8, 0.82, 0.85)
    cd = bpy.data.cameras.new("c")
    cd.type = "ORTHO"
    cam = bpy.data.objects.new("c", cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    table = view_table(D)
    tiles = []
    for nm in names:
        direction, ctr, scale = table[nm]
        d = np.array(direction, float)
        d /= np.linalg.norm(d)
        cd.ortho_scale = scale
        cam.location = np.array(ctr) + d * 6.0
        cam.rotation_mode = "QUATERNION"
        cam.rotation_quaternion = mathutils.Vector(-d).to_track_quat("-Z", "Y")
        sc.render.filepath = f"{out}.{nm}.png"
        bpy.ops.render.render(write_still=True)
        tiles.append(Image.open(f"{out}.{nm}.png").convert("RGB"))
        os.remove(f"{out}.{nm}.png")
    sheet = Image.new("RGB", (sum(t.width for t in tiles), tiles[0].height))
    x = 0
    for t in tiles:
        sheet.paste(t, (x, 0))
        x += t.width
    sheet.save(out)
    print("[preview]", out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--voxel", type=float, default=0.004)
    ap.add_argument("--out", default="/tmp/c.png")
    ap.add_argument("--views", default="front,side,back")
    ap.add_argument("--size", type=int, default=640)
    ap.add_argument("--cache", default=None)
    ap.add_argument("--region", default=None)
    ap.add_argument("--mesh", default=None, help="render a built mesh.npz instead of sculpting")
    a = ap.parse_args()
    D = hdesign.build()
    if a.mesh:
        z = np.load(a.mesh)
        V, F = z["V"].astype(np.float64), z["F"].astype(np.int64)
    elif a.cache and os.path.exists(a.cache):
        z = np.load(a.cache)
        V, F = z["V"], z["F"]
    else:
        V, F = sculpt(D, a.voxel, a.region)
        if a.cache:
            np.savez(a.cache, V=V, F=F)
    render(D, V, F, a.out, a.views.split(","), a.size)
