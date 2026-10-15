"""
Stage the points of interest (viewer/poi/) for a private claude.ai Artifact (build/artifact_poi/).

  python3 tools/stage_poi_viewer.py   # then publish build/artifact_poi/index.html + files.json with the Artifact tool (private by default)

The page builds the POIs in code (poi_kit.js) and loads no game files. poi.js and poi_kit.js are copied byte for byte,
and the staged page's import map points at ./vendor (the repo page uses ../vendor). poi_kit.js is rewritten to import ./canopy_kit.js.
"""
import json
import os
import shutil

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "build", "artifact_poi")
SRC = os.path.join(ROOT, "viewer", "poi")
shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(OUT)

html = open(os.path.join(SRC, "index.html"), encoding="utf8").read()
assert html.count('"../vendor/') == 2, "import map paths changed; update the rewrite"
# the POI kit imports the canopy kit's seeded random and noise helpers, so stage that file too
shutil.copy(os.path.join(ROOT, "viewer", "canopy", "canopy_kit.js"), os.path.join(OUT, "canopy_kit.js"))
html = html.replace('"../vendor/', '"./vendor/')
open(os.path.join(OUT, "index.html"), "w", encoding="utf8").write(html)
shutil.copy(os.path.join(SRC, "poi.js"), os.path.join(OUT, "poi.js"))
kit = open(os.path.join(SRC, "poi_kit.js"), encoding="utf8").read()
assert kit.count("'../canopy/canopy_kit.js'") == 1, "canopy import changed; update the rewrite"
open(os.path.join(OUT, "poi_kit.js"), "w", encoding="utf8").write(kit.replace("'../canopy/canopy_kit.js'", "'./canopy_kit.js'"))
shutil.copytree(os.path.join(ROOT, "viewer", "vendor"), os.path.join(OUT, "vendor"))

files = {}
for d, _, fs in os.walk(OUT):
    for f in fs:
        p = os.path.relpath(os.path.join(d, f), OUT)
        if p != "index.html":
            files[p] = os.path.join("build", "artifact_poi", p)


def _entry(p, s):
    if os.path.splitext(p)[1] == "":          # e.g. vendor/three/LICENSE: publish extension-less files as text
        return p + ".txt", {"from": s, "contentType": "text/plain"}
    return p, s


json.dump(dict(_entry(p, s) for p, s in files.items()), open(os.path.join(OUT, "files.json"), "w"), indent=1)
print("staged", len(files) + 1, "files,", sum(os.path.getsize(os.path.join(OUT, p)) for p in files) // 1024, "KB")
