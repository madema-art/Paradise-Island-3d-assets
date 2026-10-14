# Workshop handoff

State of the repository for the next session (or for Claude Code running locally).

## Where the work lives

- Everything is on branch **`claude/lucid-cannon-8xjp9h`** of `madema-art/Paradise-Island-3d-assets`. It is the only branch on the
  remote: the repository has no default/base branch, so **a pull request could not be opened** (a PR needs a base with shared
  history). The pushed branch is the safe handoff. Never force-push or rewrite it.
- A snapshot tag could not be pushed (the git proxy only permits pushing the designated branch; the tag push returned 403).
  Not worked around.
- To open a PR later: create a base branch (for example `main`) at the first commit `8992186` (or an empty initial commit)
  from GitHub's UI, then PR this branch into it.

## History

| Commit | Content |
|---|---|
| `8992186` | Blender toolchain (`tools/blender/`), low-poly painted tropical fish proof of concept (`assets/test/tropical_fish/`). |
| `b624915`, `9ef8f15` | Monkey pipeline: SDF sculpt, decimation, skin weights, xatlas UVs, procedural fur textures, rig assembly. |
| `fd649be` | Animation library (41 clips), coconut prop, GLB export, Three.js viewer. |
| later commits | Eyelids/blink, tail/head fixes, lite and LOD1 builds, packaging, previews, docs. |

## Rebuilding

```bash
tools/blender/setup_blender.sh        # Blender 4.0.2, bpy 5.2.2 venv at /opt/bpy-venv, gltf-validator
/opt/bpy-venv/bin/pip install scikit-image scipy xatlas pillow numpy   # sculpt/paint/UV dependencies
bash tools/monkey/build_all.sh        # ~10 min: mesh, textures, coconut, assemble, animate, export, package
FROM=animate bash tools/monkey/build_all.sh   # resume from a later stage (SKIP_SCULPT=1 reuses the cached sculpt)
cd viewer/tests && npm install && cd ../.. && python3 tools/monkey/make_previews.py && python3 tools/monkey/make_readme.py
```

`build/` is git-ignored scratch space; `assets/monkey/` is the committed output.

## Environment notes (cloud container)

- Everything outside the repo is ephemeral; rerun the setup script every session.
- `.blend` files saved by bpy 5.2 do not open in Blender 4.0.2. Treat bpy 5.2.2 as the canonical version.
- Headless GL needs Mesa (installed by the setup script); no GPU. Previews are rendered with Three.js through headless Chromium
  (SwiftShader) via `viewer/tests/capture.mjs`.
- blender.org downloads are blocked by the egress policy.

## Not in this repository

The Paradise Island game itself. Nothing here reads from or changes it. Integration steps are in `MONKEY_INTEGRATION.md`.
