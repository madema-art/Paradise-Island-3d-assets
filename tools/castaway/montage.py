"""Compact review montage: one row per clip (n frames, one or two views), real skinned GLB in Three.js.
  python montage.py out.jpg clipA clipB ... [--frames=5] [--views=a,b] [--cam=a:2.6,1.2,3.4,0,0.95,0] [--prop=Staff]
"""
import importlib
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
import anim_pack  # noqa: E402
import clipkit as CK  # noqa: E402
from pose_lib import RIG  # noqa: E402

ALL_MODS = ["clips_locomotion", "clips_transitions", "clips_posture", "clips_staff", "clips_personality"]
EXTRA_MODS = os.environ.get("CLIP_MODS", "").split(",") if os.environ.get("CLIP_MODS") else []

CAMS = {"a": "a:2.6,1.2,3.4,0,0.95,0", "b": "b:4.2,1.0,0.0,0,0.95,0", "c": "c:-2.6,1.2,3.4,0,0.95,0", "f": "f:0.0,1.3,3.6,0,0.95,0",
        "low": "low:2.8,0.8,3.2,0,0.55,0", "far": "far:4.5,2.0,6.0,0,0.9,0", "u": "u:1.5,1.65,2.2,0,1.55,0", "ub": "ub:2.4,1.6,0.8,0,1.5,0"}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = args[0]
    names = args[1:]
    kw = dict(a[2:].split("=", 1) for a in sys.argv[1:] if a.startswith("--") and "=" in a)
    nf = int(kw.get("frames", 5))
    views = kw.get("views", "a").split(",")
    cam = kw.get("cam")
    size = kw.get("size", "300x400")
    W, H = map(int, size.split("x"))
    for m in ALL_MODS + EXTRA_MODS:
        importlib.import_module(m)
    bakes = [CK.bake(n) for n in names]
    glb = os.path.join(ROOT, "build/castaway/_montage.glb")
    anim_pack.write_main(os.path.join(ROOT, "build/castaway/Castaway_static.glb"), glb, bakes)
    rows = []
    for B in bakes:
        dur = B.spec["seconds"]
        times = [dur * i / nf if B.loop else min(dur * i / (nf - 1), dur - 1.5 / 30) for i in range(nf)]
        d = os.path.join(ROOT, "build/castaway/sheets", "_m_" + B.name)
        os.makedirs(d, exist_ok=True)
        uses = any(np.linalg.norm(p.props["prop_staff"][0] - RIG.sk.head[RIG.sk.i("prop_staff")]) > 1e-3 or abs(p.props["prop_staff"][1][2, 2] - 1) > 1e-3 for p in B.poses)
        extra = ["--extra", "build/castaway/Staff.glb@prop_staff"] if uses else []
        vspec = ";".join((cam if (cam and len(views) == 1 and v == "a") else CAMS[v]) for v in views)
        subprocess.run(["node", os.path.join(ROOT, "viewer/tests/shot.mjs"), "--model", "build/castaway/_montage.glb", "--clip", B.name, *extra,
                        "--times", ",".join(f"{t:.3f}" for t in times), "--views", vspec, "--out", d, "--size", size, "--fov", kw.get("fov", "34")],
                       cwd=ROOT, check=True, capture_output=True)
        row = Image.new("RGB", (W * nf, H * len(views) + 16), (28, 32, 38))
        for i in range(nf):
            for r, v in enumerate(views):
                row.paste(Image.open(os.path.join(d, f"{v}_{i:02d}.png")).convert("RGB"), (i * W, 16 + r * H))
        m = B.metrics["reach_miss_mm"]
        worst = max(m.values()) if m else 0
        ImageDraw.Draw(row).text((6, 2), f"{B.name} {dur:.2f}s {'loop' if B.loop else ''}  reach_miss={worst}mm minz={B.metrics['min_z']}", fill=(255, 255, 255))
        rows.append(row)
    sheet = Image.new("RGB", (max(r.width for r in rows), sum(r.height for r in rows)))
    y = 0
    for r in rows:
        sheet.paste(r, (0, y))
        y += r.height
    sheet.save(out, quality=86)
    print(out, sheet.size)


if __name__ == "__main__":
    main()
