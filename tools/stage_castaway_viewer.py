"""
Stage the castaway viewer plus the REAL packaged GLBs for a private claude.ai Artifact (build/artifact_castaway/).

  python3 tools/stage_castaway_viewer.py       # then publish build/artifact_castaway/index.html + files.json with the Artifact tool (private by default)

viewer/castaway.js, vendor/three and assets/castaway/* are copied byte for byte. The host serves no `.glb`, so every GLB is published as `*.glb.wasm`
(GLTFLoader sniffs the 'glTF' magic, not the name) and the viewer finds them through window.CASTAWAY_FILES. LOD GLBs, the editable .blend and the
previews are not published (the viewer does not use them); every file stays under the 15 MB per-file limit.
"""
import json
import os
import re
import shutil

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "build", "artifact_castaway")
SRC = os.path.join(ROOT, "assets", "castaway")
shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(os.path.join(OUT, "assets", "castaway", "props"))

html = open(os.path.join(ROOT, "viewer", "castaway.html"), encoding="utf8").read()
css = open(os.path.join(ROOT, "viewer", "castaway.css"), encoding="utf8").read()
importmap = re.search(r'<script type="importmap">.*?</script>', html, re.S).group(0)
body = re.search(r"<body>(.*)</body>", html, re.S).group(1).replace('<script type="module" src="castaway.js"></script>', "")

files = {}
mapping = {}
glbs = ["Castaway.glb", "Staff.glb"] + [f for f in sorted(os.listdir(SRC)) if f.startswith("Castaway_anim_")] + ["props/" + f for f in sorted(os.listdir(os.path.join(SRC, "props"))) if f.endswith(".glb")]
for g in glbs:
    dst = f"assets/castaway/{g}.wasm"
    shutil.copy(os.path.join(SRC, g), os.path.join(OUT, dst))
    mapping[g] = dst
for j in ("castaway_clips.json", "castaway_face.json", "castaway_grips.json"):
    shutil.copy(os.path.join(SRC, j), os.path.join(OUT, "assets", "castaway", j))
    mapping[j] = f"assets/castaway/{j}"
page = (f"<title>Castaway Asset Viewer</title>\n<meta name=\"claude:viewport-fit-sides\" content=\"cover\">\n<style>{css}</style>\n{importmap}\n{body}\n"
        f"<script>window.CASTAWAY_FILES = {json.dumps(mapping)};</script>\n<script type=\"module\" src=\"castaway.js\"></script>\n")
open(os.path.join(OUT, "index.html"), "w", encoding="utf8").write(page)
shutil.copy(os.path.join(ROOT, "viewer", "castaway.js"), os.path.join(OUT, "castaway.js"))
shutil.copytree(os.path.join(ROOT, "viewer", "vendor"), os.path.join(OUT, "vendor"))
for d, _, fs in os.walk(OUT):
    for f in fs:
        p = os.path.relpath(os.path.join(d, f), OUT)
        if p != "index.html":
            files[p] = os.path.join("build", "artifact_castaway", p)
big = [(p, os.path.getsize(os.path.join(OUT, p))) for p in files if os.path.getsize(os.path.join(OUT, p)) > 15 * 1024 * 1024]
assert not big, big
json.dump({p: {"from": s, "contentType": "application/wasm"} if p.endswith(".wasm") else s for p, s in files.items()}, open(os.path.join(OUT, "files.json"), "w"), indent=1)
print("staged", len(files) + 1, "files,", sum(os.path.getsize(os.path.join(OUT, p)) for p in files) // 1024, "KB")
