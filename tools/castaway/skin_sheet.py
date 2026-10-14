"""Skinned contact sheet of a baked clip rendered in Three.js (real GLB). Usage:
  python skin_sheet.py <clip> [clip ...]   (needs build/castaway/Castaway_static.glb; bakes the clip packs on the fly)
"""
import importlib
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
from PIL import Image, ImageDraw  # noqa: E402

import numpy as np  # noqa: E402
import anim_pack  # noqa: E402
from pose_lib import RIG  # noqa: E402
import clipkit as CK  # noqa: E402

MODS = "clips_locomotion,clips_transitions,clips_posture,clips_staff"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    mods = [a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--mods=")] or [MODS]
    n_frames = 6
    for m in mods[0].split(","):
        importlib.import_module(m)
    bakes = [CK.bake(n) for n in args]
    out_glb = os.path.join(ROOT, "build/castaway/_sheet.glb")
    anim_pack.write_main(os.path.join(ROOT, "build/castaway/Castaway_static.glb"), out_glb, bakes)
    for B in bakes:
        dur = B.spec["seconds"]
        times = [dur * i / n_frames if B.loop else min(dur * i / (n_frames - 1), dur - 1.5 / 30) for i in range(n_frames)]
        d = os.path.join(ROOT, "build/castaway/sheets", B.name)
        os.makedirs(d, exist_ok=True)
        cx = 0.0
        view = lambda name, x, z, y=1.05, tx=0.0, ty=0.95: f"{name}:{x},{y},{z},{tx},{ty},0"
        views = f"a:2.6,1.2,3.4,0,0.95,0;b:4.2,1.0,0.0,0,0.95,0"
        uses_staff = any(np.linalg.norm(p.props["prop_staff"][0] - RIG.sk.head[RIG.sk.i("prop_staff")]) > 1e-3 or abs(p.props["prop_staff"][1][2, 2] - 1) > 1e-3 for p in B.poses)
        extra = ["--extra", "build/castaway/Staff.glb@prop_staff"] if uses_staff else []
        subprocess.run(["node", os.path.join(ROOT, "viewer/tests/shot.mjs"), "--model", "build/castaway/_sheet.glb", "--clip", B.name, *extra,
                        "--times", ",".join(f"{t:.3f}" for t in times), "--views", views, "--out", d, "--size", "420x560", "--fov", "34"],
                       cwd=ROOT, check=True, capture_output=True)
        W, H = 420, 560
        sheet = Image.new("RGB", (W * n_frames, H * 2 + 22), (28, 32, 38))
        for i in range(n_frames):
            for r, v in enumerate("ab"):
                sheet.paste(Image.open(os.path.join(d, f"{v}_{i:02d}.png")).convert("RGB"), (i * W, 22 + r * H))
        ImageDraw.Draw(sheet).text((8, 4), f"{B.name} {dur:.2f}s {'loop' if B.loop else 'one-shot'}  t={[round(t, 2) for t in times]}", fill=(255, 255, 255))
        path = os.path.join(ROOT, "build/castaway/sheets", f"{B.name}.jpg")
        sheet.save(path, quality=88)
        print(path)


if __name__ == "__main__":
    main()
