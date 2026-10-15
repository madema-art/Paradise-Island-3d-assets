"""
Stage the manta viewer plus the REAL packaged GLB and specs for a private claude.ai Artifact (build/artifact_manta/).

  python3 tools/stage_manta_viewer.py       # then publish build/artifact_manta/index.html + files.json with the Artifact tool (private by default)

viewer/manta.js, viewer/manta.css and vendor/three are copied byte for byte. The host serves no `.glb`, so Manta.glb is published as
`Manta.glb.wasm` (GLTFLoader sniffs the 'glTF' magic, not the name) and the viewer finds it through window.MANTA_FILES.
Nothing is modified. The viewer reads the same bytes the game would.
"""
import json
import os
import re
import shutil

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "build", "artifact_manta")
SRC = os.path.join(ROOT, "assets", "manta")
shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(os.path.join(OUT, "assets", "manta"))

html = open(os.path.join(ROOT, "viewer", "manta.html"), encoding="utf8").read()
css = open(os.path.join(ROOT, "viewer", "manta.css"), encoding="utf8").read()
importmap = re.search(r'<script type="importmap">.*?</script>', html, re.S).group(0)
body = re.search(r"<body>(.*)</body>", html, re.S).group(1).replace('<script type="module" src="manta.js"></script>', "")

mapping = {}
shutil.copy(os.path.join(SRC, "Manta.glb"), os.path.join(OUT, "assets", "manta", "Manta.glb.wasm"))
mapping["Manta.glb"] = "assets/manta/Manta.glb.wasm"
for j in ("manta_clips.json", "manta_behavior.json", "behavior_report.json"):
    shutil.copy(os.path.join(SRC, j), os.path.join(OUT, "assets", "manta", j))
    mapping[j] = f"assets/manta/{j}"

page = (f"<meta charset=\"utf-8\">\n<link rel=\"icon\" href=\"data:,\">\n<title>Giant Manta Asset Viewer</title>\n<meta name=\"claude:viewport-fit-sides\" content=\"cover\">\n<style>{css}</style>\n{importmap}\n{body}\n"
        f"<script>window.MANTA_FILES = {json.dumps(mapping)};</script>\n<script type=\"module\" src=\"manta.js\"></script>\n")
open(os.path.join(OUT, "index.html"), "w", encoding="utf8").write(page)
shutil.copy(os.path.join(ROOT, "viewer", "manta.js"), os.path.join(OUT, "manta.js"))
shutil.copytree(os.path.join(ROOT, "viewer", "vendor"), os.path.join(OUT, "vendor"))

files = {}
for d, _, fs in os.walk(OUT):
    for f in fs:
        p = os.path.relpath(os.path.join(d, f), OUT)
        if p != "index.html":
            files[p] = os.path.join("build", "artifact_manta", p)
big = [(p, os.path.getsize(os.path.join(OUT, p))) for p in files if os.path.getsize(os.path.join(OUT, p)) > 15 * 1024 * 1024]
assert not big, big


def _entry(p, s):
    if p.endswith(".wasm"):
        return p, {"from": s, "contentType": "application/wasm"}
    if os.path.splitext(p)[1] == "":          # e.g. vendor/three/LICENSE: the host serves only known extensions, so publish it as text
        return p + ".txt", {"from": s, "contentType": "text/plain"}
    return p, s


json.dump(dict(_entry(p, s) for p, s in files.items()), open(os.path.join(OUT, "files.json"), "w"), indent=1)
print("staged", len(files) + 1, "files,", sum(os.path.getsize(os.path.join(OUT, p)) for p in files) // 1024, "KB")
