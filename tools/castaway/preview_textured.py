"""EEVEE preview of the painted skin on the built mesh (head/body atlases).  Dev tool.

  /opt/bpy-venv/bin/python tools/castaway/preview_textured.py --out build/castaway/t1.png --views face,face_tq
"""
import argparse
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "monkey"))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402
from PIL import Image  # noqa: E402

from meshutil import mesh_from_arrays  # noqa: E402
import hdesign  # noqa: E402

VIEWS = {
    "face": ((0.0, -1.0, 0.05), (0, -0.05, 1.865), 0.62),
    "face_tq": ((0.62, -0.78, 0.08), (0, -0.05, 1.865), 0.62),
    "face_side": ((1, 0, 0.02), (0, -0.04, 1.86), 0.62),
    "head_back": ((0.3, 1.0, 0.1), (0, 0, 1.86), 0.7),
    "full": ((0.45, -0.9, 0.12), (0, 0, 1.0), 4.3),
    "front": ((0, -1, 0.04), (0, 0, 1.0), 4.3),
    "back": ((0, 1, 0.04), (0, 0, 1.0), 4.3),
    "torso": ((0.5, -0.85, 0.1), (0, 0, 1.42), 1.7),
    "torso_back": ((0.3, 0.9, 0.1), (0, 0, 1.42), 1.7),
    "hand": ((0.6, -0.7, 0.35), (0.40, -0.06, 0.88), 0.62),
    "hand_back": ((0.9, 0.0, 0.35), (0.40, -0.06, 0.88), 0.62),
    "foot": ((0.7, -0.6, 0.45), (0.1, -0.07, 0.06), 0.72),
    "legs": ((0.5, -0.85, 0.1), (0, 0, 0.55), 2.2),
    "arm": ((0.7, -0.7, 0.1), (0.28, 0, 1.40), 1.2),
    "upper": ((0.0, -1.0, 0.05), (0, 0, 1.5), 1.6),
}


def mat_for(name, alb, nrm, orm):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]

    def img(path, cs):
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = bpy.data.images.load(path)
        n.image.colorspace_settings.name = cs
        return n

    a = img(alb, "sRGB")
    nt.links.new(a.outputs["Color"], b.inputs["Base Color"])
    n = img(nrm, "Non-Color")
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(n.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
    o = img(orm, "Non-Color")
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(o.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Green"], b.inputs["Roughness"])
    if "Subsurface Weight" in b.inputs:
        b.inputs["Subsurface Weight"].default_value = 0.12
        b.inputs["Subsurface Radius"].default_value = (0.9, 0.35, 0.2)
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mesh", default="build/castaway/mesh.npz")
    ap.add_argument("--tex", default="build/castaway/tex")
    ap.add_argument("--out", default="build/castaway/t.png")
    ap.add_argument("--views", default="face,face_tq")
    ap.add_argument("--size", type=int, default=800)
    ap.add_argument("--samples", type=int, default=24)
    a = ap.parse_args()
    z = np.load(a.mesh)
    V, F, N, uv, grp = z["V"].astype(np.float64), z["F"].astype(np.int64), z["N"], z["uv"], z["group"]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    me = mesh_from_arrays(bpy, "Skin", V, F)
    layer = me.uv_layers.new(name="UVMap")
    layer.data.foreach_set("uv", uv.reshape(-1).astype(np.float32))
    for p in me.polygons:
        p.use_smooth = True
    try:
        me.normals_split_custom_set_from_vertices(N.astype(np.float32).tolist())
    except Exception as e:
        print("custom normals:", e)
    mh = mat_for("Head", *(os.path.join(a.tex, f"skin_head_{k}.png") for k in ("albedo", "normal", "orm")))
    mb_paths = [os.path.join(a.tex, f"skin_body_{k}.png") for k in ("albedo", "normal", "orm")]
    mb = mat_for("Body", *mb_paths) if all(os.path.exists(p) for p in mb_paths) else bpy.data.materials.new("BodyPlain")
    me.materials.append(mh)
    me.materials.append(mb)
    me.polygons.foreach_set("material_index", grp.astype(np.int32))
    ob = bpy.data.objects.new("Skin", me)
    sc = bpy.context.scene
    sc.collection.objects.link(ob)
    # eyes
    D = hdesign.build()
    for t in ("L", "R"):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=hdesign.EYE_R, location=tuple(D.lm[f"eye_{t}"]), segments=32, ring_count=16)
        e = bpy.context.active_object
        em = bpy.data.materials.new("eye")
        em.use_nodes = True
        em.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.85, 0.80, 0.72, 1)
        em.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.1
        e.data.materials.append(em)
        bpy.ops.object.shade_smooth()
    # lights + world
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.55, 0.62, 0.70, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.9
    sc.world = w
    for nm, en, rot in (("key", 3.0, (math.radians(55), 0, math.radians(35))), ("fill", 0.8, (math.radians(70), 0, math.radians(-120))),
                        ("rim", 1.6, (math.radians(115), 0, math.radians(160)))):
        ld = bpy.data.lights.new(nm, "SUN")
        ld.energy = en
        lo = bpy.data.objects.new(nm, ld)
        lo.rotation_euler = rot
        sc.collection.objects.link(lo)
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x = sc.render.resolution_y = a.size
    try:
        sc.eevee.taa_render_samples = a.samples
    except Exception:
        pass
    sc.view_settings.view_transform = "Standard"
    cd = bpy.data.cameras.new("c")
    cd.lens = 85
    cam = bpy.data.objects.new("c", cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    tiles = []
    for nm in a.views.split(","):
        direction, ctr, dist = VIEWS[nm]
        d = Vector(direction).normalized()
        cam.location = Vector(ctr) + d * dist * 1.0
        cam.rotation_mode = "QUATERNION"
        cam.rotation_quaternion = (-d).to_track_quat("-Z", "Y")
        sc.render.filepath = f"{a.out}.{nm}.png"
        bpy.ops.render.render(write_still=True)
        tiles.append(Image.open(f"{a.out}.{nm}.png").convert("RGB"))
        os.remove(f"{a.out}.{nm}.png")
    sheet = Image.new("RGB", (sum(t.width for t in tiles), tiles[0].height))
    x = 0
    for t in tiles:
        sheet.paste(t, (x, 0))
        x += t.width
    sheet.save(a.out)
    print("[preview]", a.out)


if __name__ == "__main__":
    main()
