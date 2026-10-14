"""
Stage the workshop viewer plus the REAL packaged GLBs for a private claude.ai Artifact (build/artifact/).

  python3 tools/stage_artifact_viewer.py            # then publish build/artifact/index.html with the Artifact tool (private by default)

Nothing is modified or approximated: the page is viewer/index.html with its stylesheet inlined and the asset paths pointed at
files published next to it. viewer.js, vendor/three and assets/monkey/* are copied byte for byte (path strings aside).
"""
import json
import os
import re
import shutil

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "build", "artifact")
shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(os.path.join(OUT, "assets", "monkey"))

html = open(os.path.join(ROOT, "viewer", "index.html"), encoding="utf8").read()
css = open(os.path.join(ROOT, "viewer", "viewer.css"), encoding="utf8").read()
importmap = re.search(r'<script type="importmap">.*?</script>', html, re.S).group(0)
body = re.search(r"<body>(.*)</body>", html, re.S).group(1)
body = body.replace('<script type="module" src="viewer.js"></script>', "")
page = (f"<title>Monkey Asset Viewer</title>\n<meta name=\"claude:viewport-fit-sides\" content=\"cover\">\n<style>{css}</style>\n"
        f"{importmap}\n{body}\n<script type=\"module\" src=\"viewer.js\"></script>\n")
open(os.path.join(OUT, "index.html"), "w", encoding="utf8").write(page)

# The artifact host serves no .glb extension; the identical bytes are published as *.glb.wasm (GLTFLoader sniffs the 'glTF' magic, not the name).
js = open(os.path.join(ROOT, "viewer", "viewer.js"), encoding="utf8").read()
js = js.replace("'../assets/monkey/Monkey.glb'", "'assets/monkey/Monkey.glb.wasm'").replace("'../assets/monkey/coconut.glb'", "'assets/monkey/coconut.glb.wasm'")
js = js.replace("../assets/monkey/", "assets/monkey/")
open(os.path.join(OUT, "viewer.js"), "w", encoding="utf8").write(js)
shutil.copytree(os.path.join(ROOT, "viewer", "vendor"), os.path.join(OUT, "vendor"))
for f, dst in (("Monkey.glb", "Monkey.glb.wasm"), ("coconut.glb", "coconut.glb.wasm"), ("monkey_clips.json", "monkey_clips.json")):
    shutil.copy(os.path.join(ROOT, "assets", "monkey", f), os.path.join(OUT, "assets", "monkey", dst))

files = {}
for d, _, fs in os.walk(OUT):
    for f in fs:
        p = os.path.relpath(os.path.join(d, f), OUT)
        if p != "index.html":
            files[p] = os.path.join("build", "artifact", p)
json.dump(files, open(os.path.join(OUT, "files.json"), "w"), indent=1)
print("staged", len(files) + 1, "files,", sum(os.path.getsize(os.path.join(OUT, p)) for p in files) // 1024, "KB")
