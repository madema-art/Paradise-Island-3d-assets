"""Bake clips and write stick-figure contact sheets: python review.py walk run ..."""
import importlib
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import clipkit as CK  # noqa: E402
import stickfig  # noqa: E402

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    mods = [a.split("=")[1] for a in sys.argv[1:] if a.startswith("--mods=")] or ["clips_locomotion"]
    for m in mods[0].split(","):
        importlib.import_module(m)
    out = "build/castaway/review"
    os.makedirs(out, exist_ok=True)
    names = list(CK.CLIPS) if not args or args == ["all"] else args
    frames = 8
    for n in names:
        t = time.time()
        B = CK.bake(n)
        rep = CK.foot_slide_report(B)
        print(f"{n}: {B.quat.shape[0]}f {time.time() - t:.1f}s reach={B.metrics['reach_miss_mm']} slide={rep} minz={B.metrics['min_z']}")
        stickfig.sheet(B, os.path.join(out, n + ".png"), frames=frames)
