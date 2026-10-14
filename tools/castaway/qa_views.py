"""Render head close-ups + full-body QA views of a castaway GLB and tile them. python qa_views.py <glb> <outdir>"""
import subprocess, sys, os
from PIL import Image
glb, out = sys.argv[1], sys.argv[2]
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
views = "front:0,1.0,4.6,0,0.98,0;side:4.6,1.0,0,0,0.98,0;back:0,1.0,-4.6,0,0.98,0;face:0.0,1.86,0.95,0,1.84,0;face34:0.7,1.9,0.75,0,1.83,0;faceside:0.9,1.85,0.1,0,1.83,0"
subprocess.run(["node", os.path.join(ROOT, "viewer/tests/shot.mjs"), "--model", glb, "--views", views, "--out", out, "--size", "520x640", "--fov", "28"], cwd=ROOT, check=True, capture_output=True)
for name, ks in (("body", ("front", "side", "back")), ("face", ("face", "face34", "faceside"))):
    ims = [Image.open(os.path.join(out, f"{k}.png")).convert("RGB") for k in ks]
    s = Image.new("RGB", (sum(i.width for i in ims), ims[0].height)); x = 0
    for i in ims:
        s.paste(i, (x, 0)); x += i.width
    s.save(os.path.join(out, f"{name}.jpg"), quality=90)
print(out)
