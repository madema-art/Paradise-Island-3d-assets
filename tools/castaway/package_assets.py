"""Collect the castaway deliverables into assets/castaway/ (GLBs, animation packs, props, metadata, source blend) and write MANIFEST.json.

  /opt/bpy-venv/bin/python tools/castaway/package_assets.py        # after build_castaway.sh, build_library.py, proxy/staff builders, LOD builds
"""
import hashlib
import json
import os
import shutil
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
B = os.path.join(ROOT, "build/castaway")
OUT = os.path.join(ROOT, "assets/castaway")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()[:16]


def glb_stats(path):
    from glb_tools import Glb
    g = Glb(path)
    j = g.json
    tris = 0
    skin_tris = 0
    for me in j.get("meshes", []):
        for p in me["primitives"]:
            if "indices" in p:
                n = j["accessors"][p["indices"]]["count"] // 3
                tris += n
                if me["name"] == "CastawaySkinMesh":
                    skin_tris += n
    imgs = []
    for im in j.get("images", []):
        bv = j["bufferViews"][im["bufferView"]]
        imgs.append((im.get("name"), bv["byteLength"]))
    return dict(triangles=tris, skin_triangles=skin_tris, nodes=len(j["nodes"]), animations=len(j.get("animations", [])), images=len(imgs))


def main():
    sys.path.insert(0, HERE)
    import importlib
    import anim_pack
    import clipkit as CK
    for m in ("clips_locomotion", "clips_transitions", "clips_posture", "clips_staff", "clips_personality", "clips_survival", "clips_fishing", "clips_canoe", "clips_wildlife", "clips_climb"):
        importlib.import_module(m)
    import build_library as BL
    shutil.rmtree(OUT, ignore_errors=True)
    for d in ("props", "source", "previews", "validation"):
        os.makedirs(os.path.join(OUT, d))
    lib = os.path.join(B, "lib")
    for f in sorted(os.listdir(lib)):
        shutil.copy(os.path.join(lib, f), os.path.join(OUT, f))
    # LOD GLBs carry the core clips too
    bk = CK.bake_many(BL.CORE, verbose=False)
    for name in ("lod1", "lite"):
        src = os.path.join(B, "lod", f"Castaway_{name}.glb")
        anim_pack.write_main(src, os.path.join(OUT, f"Castaway_{name}.glb"), [bk[n] for n in BL.CORE])
    shutil.copy(os.path.join(B, "Staff.glb"), os.path.join(OUT, "Staff.glb"))
    shutil.copy(os.path.join(ROOT, "build/staff/staff_points.json"), os.path.join(OUT, "staff_points.json"))
    for f in os.listdir(os.path.join(B, "props")):
        shutil.copy(os.path.join(B, "props", f), os.path.join(OUT, "props", f))
    # bones table
    rest = json.load(open(os.path.join(HERE, "rest_pose.json")))
    from pose_lib import RIG
    sk = RIG.sk
    names = list(sk.names)
    groups = {"spine": [n for n in names if n.startswith(("spine", "pelvis", "neck", "root"))] + ["head"],
              "arms": [n for n in names if n.startswith(("clavicle", "upper_arm", "forearm", "hand_"))],
              "twist": [n for n in names if "_tw" in n], "fingers": [n for n in names if n.startswith("f_")],
              "legs": [n for n in names if n.startswith(("thigh", "shin", "foot"))], "toes": [n for n in names if n.startswith(("toe", "hallux"))],
              "face": [n for n in names if n.startswith(("jaw", "eye_", "lid_", "brow_", "cheek_", "lip_"))],
              "hair_beard_secondary": [n for n in names if n.startswith(("hair_", "beard_"))], "cloth_secondary": [n for n in names if n.startswith("cloth_")],
              "props": ["prop_staff", "prop_aux"], "attach": [n for n in names if n.startswith("attach_")]}
    json.dump(dict(bones=[dict(name=n, parent=(names[sk.parent[i]] if sk.parent[i] >= 0 else None), head=[round(float(x), 4) for x in sk.head[i]],
                               tail=[round(float(x), 4) for x in sk.tail[i]], deform=bool(sk.deform[i])) for i, n in enumerate(names)],
                   groups=groups, upper_body_mask=BL.upper_mask(),
                   note="positions are Blender rest coordinates (z up, the character faces -Y); GLB nodes use glTF axes (y up, faces +Z) with the same node-local frames."),
              open(os.path.join(OUT, "castaway_bones.json"), "w"), indent=1)
    # editable source (images packed so the blend is self-contained)
    import subprocess
    code = ("import bpy; bpy.ops.wm.open_mainfile(filepath=%r); bpy.ops.file.pack_all(); bpy.ops.wm.save_as_mainfile(filepath=%r, compress=True)"
            % (os.path.join(B, "Castaway_rig.blend"), os.path.join(OUT, "source", "Castaway_rig.blend")))
    subprocess.run([sys.executable, "-c", code], check=True, capture_output=True)
    for f in ("Staff",):
        pass
    man = {}
    for d, _, fs in os.walk(OUT):
        for f in sorted(fs):
            p = os.path.join(d, f)
            rel = os.path.relpath(p, OUT)
            if rel == "MANIFEST.json":
                continue
            rec = dict(bytes=os.path.getsize(p), sha256_16=sha(p))
            if f.endswith(".glb"):
                rec.update(glb_stats(p))
            man[rel] = rec
    json.dump(dict(generator="tools/castaway/package_assets.py", files=man), open(os.path.join(OUT, "MANIFEST.json"), "w"), indent=1)
    tot = sum(v["bytes"] for v in man.values())
    print(f"[package] {len(man)} files, {tot / 1e6:.1f} MB -> {OUT}")


if __name__ == "__main__":
    main()
