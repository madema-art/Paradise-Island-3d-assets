"""
Stage the on-screen display prototype (viewer/osd/) for a private claude.ai Artifact (build/artifact_osd/).

  python3 tools/stage_osd_viewer.py   # then publish build/artifact_osd/index.html + files.json with the Artifact tool (private by default)

The page builds its scene in code and loads no game files. osd.js and cycle.js are copied byte for byte,
and the staged page's import map points at ./vendor (the repo page uses ../vendor), so the layout matches the repo.
"""
import json
import os
import shutil

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "build", "artifact_osd")
SRC = os.path.join(ROOT, "viewer", "osd")
shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(OUT)

html = open(os.path.join(SRC, "index.html"), encoding="utf8").read()
assert html.count('"../vendor/') == 2, "import map paths changed; update the rewrite"
html = html.replace('"../vendor/', '"./vendor/')
open(os.path.join(OUT, "index.html"), "w", encoding="utf8").write(html)
for name in ("osd.js", "cycle.js"):
    shutil.copy(os.path.join(SRC, name), os.path.join(OUT, name))
shutil.copytree(os.path.join(ROOT, "viewer", "vendor"), os.path.join(OUT, "vendor"))

files = {}
for d, _, fs in os.walk(OUT):
    for f in fs:
        p = os.path.relpath(os.path.join(d, f), OUT)
        if p != "index.html":
            files[p] = os.path.join("build", "artifact_osd", p)


def _entry(p, s):
    if os.path.splitext(p)[1] == "":          # e.g. vendor/three/LICENSE: publish extension-less files as text
        return p + ".txt", {"from": s, "contentType": "text/plain"}
    return p, s


json.dump(dict(_entry(p, s) for p, s in files.items()), open(os.path.join(OUT, "files.json"), "w"), indent=1)
print("staged", len(files) + 1, "files,", sum(os.path.getsize(os.path.join(OUT, p)) for p in files) // 1024, "KB")
