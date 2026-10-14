"""Bake registered clips and write them into GLBs.

  /opt/bpy-venv/bin/python tools/castaway/bake_clips.py --static build/castaway/Castaway_static.glb --out build/castaway/test.glb --clips test_pose
"""
import argparse
import importlib
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import anim_pack  # noqa: E402
import clipkit as CK  # noqa: E402

MODULES = ["clips_test"]


def load_modules(mods):
    for m in mods:
        importlib.import_module(m)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--static", default="build/castaway/Castaway_static.glb")
    ap.add_argument("--out", default="build/castaway/test.glb")
    ap.add_argument("--clips", default="all")
    ap.add_argument("--modules", default=",".join(MODULES))
    ap.add_argument("--pack", action="store_true")
    a = ap.parse_args()
    load_modules(a.modules.split(","))
    names = list(CK.CLIPS) if a.clips == "all" else a.clips.split(",")
    bakes = []
    for n in names:
        t = time.time()
        B = CK.bake(n)
        print(f"[bake] {n}: {B.quat.shape[0]} frames {time.time() - t:.1f}s  reach={B.metrics['reach_miss_mm']}")
        bakes.append(B)
    fn = anim_pack.write_pack if a.pack else anim_pack.write_main
    st, size = fn(a.static, a.out, bakes)
    print(f"[pack] {a.out} {size / 1e6:.2f} MB {st}")
