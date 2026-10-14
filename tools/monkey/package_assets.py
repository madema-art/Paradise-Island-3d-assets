"""
Final step: gather the build outputs into assets/monkey/ (what a game integrator needs) and write a manifest.

  /opt/bpy-venv/bin/python tools/monkey/package_assets.py
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools", "blender"))

import validate_glb  # noqa: E402


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", default=os.path.join(ROOT, "build", "monkey"))
    ap.add_argument("--out", default=os.path.join(ROOT, "assets", "monkey"))
    a = ap.parse_args()
    B, O = a.build, a.out
    os.makedirs(os.path.join(O, "textures", "source"), exist_ok=True)
    os.makedirs(os.path.join(O, "validation"), exist_ok=True)

    copies = {
        "Monkey.glb": "Monkey.glb", "Monkey_lite.glb": "Monkey_lite.glb", "Monkey_lod1.glb": "Monkey_lod1.glb",
        "coconut/coconut.glb": "coconut.glb", "coconut/Coconut.blend": "Coconut.blend",
        "Monkey_anim.blend": "Monkey.blend", "Monkey_anim_clips.json": "monkey_clips.json",
    }
    for src, dst in copies.items():
        shutil.copy2(os.path.join(B, src), os.path.join(O, dst))
    for f in ("monkey_albedo.jpg", "monkey_normal.jpg", "monkey_orm.png", "eye_albedo.png"):
        shutil.copy2(os.path.join(B, "textures", f), os.path.join(O, "textures", f))
    for f in ("monkey_albedo.png", "monkey_normal.png", "monkey_orm.png"):
        shutil.copy2(os.path.join(B, "tex", f), os.path.join(O, "textures", "source", f))
    for f in ("coconut_albedo.jpg", "coconut_normal.jpg"):
        shutil.copy2(os.path.join(B, "coconut", f), os.path.join(O, "textures", f))

    # bone table from the exported GLB (joints in skin order)
    gltf, _ = validate_glb.read_glb(os.path.join(O, "Monkey.glb"))
    nodes = gltf["nodes"]
    parent = {}
    for i, n in enumerate(nodes):
        for c in n.get("children", []):
            parent[c] = i
    joints = gltf["skins"][0]["joints"]
    bones = [{"name": nodes[j]["name"], "parent": nodes[parent[j]]["name"] if j in parent else None} for j in joints]
    with open(os.path.join(O, "monkey_bones.json"), "w") as f:
        json.dump({"count": len(bones), "bones": bones}, f, indent=1)

    # validation reports
    report = {}
    for glb in ("Monkey.glb", "Monkey_lite.glb", "Monkey_lod1.glb", "coconut.glb"):
        p = os.path.join(O, glb)
        out = os.path.join(O, "validation", glb.replace(".glb", "_structure.json"))
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "blender", "validate_glb.py"), p,
                            "--json", out, "--min-triangles", "500"], capture_output=True, text=True)
        status = json.load(open(out))
        report[glb] = status["status"]
        kh = os.path.join(ROOT, "tools", "blender", "node_modules")
        if os.path.isdir(kh):
            k = subprocess.run(["node", os.path.join(ROOT, "tools", "blender", "validate_glb_khronos.js"), p],
                               capture_output=True, text=True)
            if k.stdout.strip():
                with open(os.path.join(O, "validation", glb.replace(".glb", "_khronos.json")), "w") as f:
                    f.write(k.stdout)
                kr = json.loads(k.stdout)
                report[glb] += f" | khronos errors={kr['errors']} warnings={kr['warnings']}"

    manifest = {"files": {}, "validation": report}
    for dp, _, fs in os.walk(O):
        for fn in sorted(fs):
            p = os.path.join(dp, fn)
            rel = os.path.relpath(p, O)
            if rel.startswith("previews") or rel == "MANIFEST.json":
                continue
            manifest["files"][rel] = {"bytes": os.path.getsize(p), "sha256_16": sha(p)}
    with open(os.path.join(O, "MANIFEST.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    for k, v in report.items():
        print(f"[package] {k}: {v}")
    print(f"[package] {len(manifest['files'])} files -> {O}")


if __name__ == "__main__":
    main()
