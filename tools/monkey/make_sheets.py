"""Assemble per-clip strips (from viewer/tests/capture.mjs --phases N) into labelled contact sheets."""
import argparse
import glob
import os

from PIL import Image, ImageDraw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="build/monkey/threejs/phases")
    ap.add_argument("--out", default="build/monkey/threejs/sheets")
    ap.add_argument("--cols", type=int, default=6)
    ap.add_argument("--tile", type=int, default=0, help="resize tiles to this width (0 = keep)")
    ap.add_argument("--group", default="", help="comma list of clip name prefixes to include, e.g. coconut_,pose_")
    ap.add_argument("--stack", default="", help="write a stacked sheet with this file name")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    clips = sorted({os.path.basename(f).rsplit("__", 1)[0] for f in glob.glob(os.path.join(a.src, "*__*.png"))})
    prefixes = [p for p in a.group.split(",") if p]
    if prefixes:
        clips = [c for c in clips if any(c.startswith(p) for p in prefixes)]
    strips = []
    for c in clips:
        files = sorted(glob.glob(os.path.join(a.src, f"{c}__*.png")))
        ims = [Image.open(f).convert("RGB") for f in files]
        if a.tile:
            ims = [i.resize((a.tile, int(i.height * a.tile / i.width)), Image.LANCZOS) for i in ims]
        w, h = ims[0].size
        rows = (len(ims) + a.cols - 1) // a.cols
        sheet = Image.new("RGB", (w * min(len(ims), a.cols), h * rows))
        for i, im in enumerate(ims):
            sheet.paste(im, ((i % a.cols) * w, (i // a.cols) * h))
        ImageDraw.Draw(sheet).text((8, 6), c, fill=(255, 255, 255))
        sheet.save(os.path.join(a.out, f"sheet_{c}.png"))
        strips.append(sheet)
    if a.stack and strips:
        W = max(s.width for s in strips)
        H = sum(s.height for s in strips)
        big = Image.new("RGB", (W, H))
        y = 0
        for s in strips:
            big.paste(s, (0, y))
            y += s.height
        big.save(os.path.join(a.out, a.stack))
        print("stack", a.stack, big.size)
    print("sheets:", len(strips))


if __name__ == "__main__":
    main()
