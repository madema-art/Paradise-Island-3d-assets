"""Export the castaway rig blend to a static GLB (mesh + skeleton + materials), then patch materials in the GLB JSON.

  /opt/bpy-venv/bin/python tools/castaway/export_castaway.py --blend build/castaway/Castaway_rig.blend --out build/castaway/Castaway_static.glb
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402

from glb_tools import Glb  # noqa: E402


def export(blend, out, lite=False, lod1=False):
    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(blend))
    rig = bpy.data.objects["CastawayRig"]
    meshes = [o for o in bpy.data.objects if o.type == "MESH" and o.parent == rig and o.name.startswith("Castaway_")]
    for o in bpy.data.objects:
        o.select_set(False)
    for o in [rig] + meshes:
        o.hide_set(False)
        o.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.scene.frame_set(1)
    bpy.ops.export_scene.gltf(
        filepath=os.path.abspath(out), export_format="GLB", use_selection=True, export_yup=True, export_apply=False,
        export_skins=True, export_def_bones=False, export_influence_nb=4, export_animations=False,
        export_image_format="AUTO", export_tangents=False, export_morph=False, export_extras=True)
    print(f"[export] {out} {os.path.getsize(out) / 1e6:.2f} MB")


def patch(path):
    g = Glb(path)
    for m in g.json.get("materials", []):
        nm = m.get("name", "")
        if nm in ("CastawayHair",) or nm.startswith("CastawayMaro"):
            m["alphaMode"] = "MASK"
            m["alphaCutoff"] = 0.42 if nm == "CastawayHair" else 0.5
            m["doubleSided"] = True
        if nm.startswith("CastawaySkin"):
            m["doubleSided"] = False
    g.save(path)
    print(f"[patch] materials patched in {path}")
    return g


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend", default="build/castaway/Castaway_rig.blend")
    ap.add_argument("--out", default="build/castaway/Castaway_static.glb")
    a = ap.parse_args()
    export(a.blend, a.out)
    patch(a.out)
