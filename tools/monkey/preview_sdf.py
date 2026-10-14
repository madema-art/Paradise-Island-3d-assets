"""
Dev tool: build the SDF monkey at a chosen voxel size and render clay views (Workbench).

  /opt/bpy-venv/bin/python tools/monkey/preview_sdf.py --voxel 0.004 --out /tmp/sdf_preview.png
"""
import argparse
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
from PIL import Image  # noqa: E402

import design  # noqa: E402
from meshutil import mesh_from_arrays, orient_outward  # noqa: E402
from sdf import Grid  # noqa: E402


def build_mesh(voxel):
    D = design.build()
    lo, hi = design.mesh_bounds(D)
    g = Grid(lo, hi, voxel)
    t = time.time()
    for op, p, k in D.ops:
        g.apply(p, k, op)
    print(f"[sdf] grid {g.shape} filled in {time.time() - t:.1f}s")
    t = time.time()
    V, F = g.mesh()
    F = orient_outward(V, F)
    print(f"[sdf] marching cubes {len(V)} verts / {len(F)} tris in {time.time() - t:.1f}s")
    return D, V, F


D_BONES = {}


def render_views(V, F, out, size=640, views=None, focus=None):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    me = mesh_from_arrays(bpy, "m", V, F)
    ob = bpy.data.objects.new("m", me)
    sc = bpy.context.scene
    sc.collection.objects.link(ob)
    for p in me.polygons:
        p.use_smooth = True
    ob.color = (0.72, 0.62, 0.5, 1.0)
    for nm, b in D_BONES.items():
        if nm.startswith("eye_"):
            bpy.ops.mesh.primitive_uv_sphere_add(radius=design.EYE_R, location=tuple(b["head"]), segments=32, ring_count=16)
            eye = bpy.context.active_object
            eye.color = (0.05, 0.03, 0.02, 1.0)
            bpy.ops.object.shade_smooth()
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light, sh.color_type = "STUDIO", "OBJECT"
    sh.show_cavity = True
    sc.display.shading.show_object_outline = False
    sc.render.resolution_x = sc.render.resolution_y = size
    sc.render.film_transparent = False
    sc.world = bpy.data.worlds.new("w")
    sc.world.color = (0.8, 0.82, 0.85)
    cam_d = bpy.data.cameras.new("c")
    cam_d.type = "ORTHO"
    cam = bpy.data.objects.new("c", cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    ctr = np.array([0.0, 0.0, 0.25]) if focus is None else np.array(focus[0])
    scale = 1.15 if focus is None else focus[1]
    cam_d.ortho_scale = scale
    # (name, camera direction from centre, rotation euler)
    all_views = {
        "side": ((1, 0, 0), (90, 0, 90)),
        "front": ((0, -1, 0), (90, 0, 0)),
        "back": ((0, 1, 0), (90, 0, 180)),
        "top": ((0, 0, 1), (0, 0, 0)),
        "three_quarter": ((0.8, -0.6, 0.35), None),
    }
    names = views or ["side", "front", "back", "top"]
    tiles = []
    for nm in names:
        direction, rot = all_views[nm]
        d = np.array(direction, float)
        d /= np.linalg.norm(d)
        cam.location = ctr + d * 3.0
        if rot is None:
            look = -d
            q = __import__("mathutils").Vector(look).to_track_quat("-Z", "Y")
            cam.rotation_mode = "QUATERNION"
            cam.rotation_quaternion = q
        else:
            cam.rotation_mode = "XYZ"
            cam.rotation_euler = [np.radians(a) for a in rot]
        path = f"{out}.{nm}.png"
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        tiles.append(Image.open(path).convert("RGB"))
        os.remove(path)
    w = sum(t.width for t in tiles)
    sheet = Image.new("RGB", (w, tiles[0].height))
    x = 0
    for t in tiles:
        sheet.paste(t, (x, 0))
        x += t.width
    sheet.save(out)
    print(f"[preview] {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voxel", type=float, default=0.004)
    ap.add_argument("--out", default="/tmp/sdf_preview.png")
    ap.add_argument("--views", default="side,front,back,top")
    ap.add_argument("--focus", default=None, help="cx,cy,cz,scale for a close-up")
    ap.add_argument("--size", type=int, default=640)
    a = ap.parse_args()
    D, V, F = build_mesh(a.voxel)
    D_BONES.update(D.bones)
    focus = None
    if a.focus:
        v = [float(x) for x in a.focus.split(",")]
        focus = (v[:3], v[3])
    render_views(V, F, a.out, size=a.size, views=a.views.split(","), focus=focus)


if __name__ == "__main__":
    main()
