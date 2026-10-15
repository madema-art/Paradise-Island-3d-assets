# Paradise Island: 3D asset workshop

Asset-creation workshop for the Paradise Island Three.js game. It is independent of the game
repository: nothing here reads from or writes to the game.

## Contents

| Path | What |
|---|---|
| `assets/monkey/` | **Island monkey**: runtime GLBs (full, lite, LOD1), editable `.blend`, textures, 41 animation clips, coconut prop, validation reports and previews. Start with `assets/monkey/README.md`. |
| `assets/monkey/previews/` | Character reference sheet, per-group animation pose sheets, texture atlas overview, UV layout, turntable, clip GIFs. |
| `assets/castaway/` | **Castaway**: rigged 2.00 m human castaway (GLB + LOD1 + lite), `Staff.glb` (walking stick / fishing pole / spear), 142 clips in animation packs with machine-readable metadata, face + grip tables, proxy props, editable `.blend`, previews, validation. Start with `assets/castaway/README.md`. |
| `assets/manta/` | **Giant manta ray**: first Blender-authored version. Skinned 6 m ray (`Manta.glb`, 2,332 tris), 10 in-place clips, behaviour config and headless simulation, editable `.blend`, real pose renders, validation. Start with `assets/manta/README.md`. |
| `docs/MANTA_HANDOFF.md` | Manta handoff to the game repository: integration steps, state machine, noticeability goals, acceptance checks. |
| `viewer/` | Standalone Three.js test viewers (no connection to the game): `python3 -m http.server` in the repo root, open `/viewer/` (monkey), `/viewer/castaway.html` (castaway) or `/viewer/manta.html` (manta). See `viewer/README.md`. |
| `tools/monkey/` | Monkey pipeline (`build_all.sh`). |
| `tools/castaway/` | Castaway pipeline (`build_castaway.sh`, `build_library.py`, clip modules, previews, packaging). |
| `tools/manta/` | Manta pipeline: geometry, clips, textures, bpy build, behaviour simulation, pose renders. |
| `tools/blender/` | Blender/bpy setup and GLB validators. |
| `docs/MONKEY_INTEGRATION.md` | Integration guide for Claude Code. |
| `docs/CASTAWAY_INTEGRATION.md`, `docs/CASTAWAY_ANIMATION_LIBRARY.md`, `docs/CASTAWAY_HANDOFF.md` | Castaway integration guide, every clip with status, rebuild/handoff notes. |
| `docs/HANDOFF.md` | Repo state, rebuild instructions, environment notes. |
| `assets/test/tropical_fish/` | Original proof-of-concept fish. |

## Blender in this environment: status

| Check | Result |
|---|---|
| Full Blender application | **Works.** Blender 4.0.2 (Ubuntu 24.04 archive). Headless `blender -b` runs, Cycles CPU renders, glTF import and export work. |
| Newest full application | **Not installable here.** `download.blender.org` returns 403 from the egress policy. Not worked around. |
| Python API (`bpy`) | **Works.** `bpy` 5.2.2 LTS from PyPI in a venv at `/opt/bpy-venv` (CPython 3.13). Same glTF exporter as the app. |
| Proof-of-concept asset | Low-poly painted tropical fish: builds, saves `.blend`, exports `.glb`, passes both validators. |
| Game-ready pipeline | **Viable for static props and creatures** with the conventions and limits below. The monkey GLBs were verified loading and animating in Three.js r186 (headless); performance inside the real game is **not yet tested**. |

### Limitations

- **`.blend` files are version-locked.** A file saved by bpy 5.2 won't open in Blender 4.0.2 ("not a blend file"). The
  header is `BLENDER17-01v0500`, so it is a format-version issue, not compression. Treat **bpy 5.2.2 as the canonical
  source version**. Don't mix in 4.0.2-saved files.
- **Ephemeral container.** Blender, numpy and the bpy venv are not persistent. Run `tools/blender/setup_blender.sh` at the
  start of each session. Re-runs are fast (about 2 s when everything is present). A cold install needs apt and PyPI access.
- **Headless render caveats.** The Ubuntu 4.0.2 build has no OpenImageDenoiser, so previews render with denoising off. No GPU is
  present. EEVEE needs a GL context and was not tested.
- **No mesh compression.** Draco and MeshOptimizer libraries are absent from the wheel, so the export is uncompressed.
- **Textures are procedural.** The monkey set is painted in Python (see `tools/monkey/paint_textures.py`) and baked to 2048² albedo, normal and ORM maps. The fish uses a 512² base-colour PNG only.
  normal or roughness maps). Fins use a planar side-view UV projection, so they get little texel detail.
- **Deprecation.** `Material.use_nodes` is slated for removal in Blender 6.0. Update the build script when 6.0 lands.

## Test asset: `assets/test/tropical_fish/`

| File | Purpose |
|---|---|
| `TropicalFish.blend` | Editable source (bpy 5.2.2). Texture is packed inside. |
| `TropicalFish.glb` | Export, 1 mesh, 2 materials (`FishPaint` textured, `FishEye`), 251 triangles, 549 glTF vertices. |
| `textures/FishPaint.png` | 512×512 base-colour texture (the same image is packed in the `.blend` and embedded in the `.glb`). |
| `preview.png` | Cycles CPU render from the re-imported `.glb`. |
| `validation_report.json` | Structural check (`validate_glb.py`). |
| `khronos_report.json` | Official Khronos glTF validator output: **0 errors, 0 warnings**. |

Conventions: the fish swims along +X (nose at +X) and is about 1.36 units long from tail to nose. The origin is the body
centre. Export is Y-up (glTF standard). Bounds in glTF space are x −0.86…0.50, y −0.34…0.40, z −0.38…0.38.

## Pipeline

```bash
# 1. Install or verify tooling (idempotent)
bash tools/blender/setup_blender.sh

# 2. Build the .blend and .glb (bpy module; the Blender app works too)
/opt/bpy-venv/bin/python tools/blender/build_tropical_fish.py -- --out assets/test/tropical_fish
#   or: blender -b --factory-startup -P tools/blender/build_tropical_fish.py -- --out assets/test/tropical_fish

# 3. Validate
python3 tools/blender/validate_glb.py assets/test/tropical_fish/TropicalFish.glb
(cd tools/blender && node validate_glb_khronos.js ../../assets/test/tropical_fish/TropicalFish.glb)

# 4. Re-import the .glb in a clean scene and render a preview
/opt/bpy-venv/bin/python tools/blender/render_preview.py -- --glb assets/test/tropical_fish/TropicalFish.glb --out assets/test/tropical_fish/preview.png
```

Structure: `tools/blender/` holds the scripts, `package.json` pins the Khronos validator (`node_modules` is git-ignored),
and `assets/test/` holds retrievable outputs.

## Not yet verified

- Loading the `.glb` in the Three.js game (GLTFLoader) and frame-rate impact.
- Blender 4.0.2 full `build → validate → render` run from a clean install. The 4.0.2 build and render were verified on this
  container after installing numpy, but the setup script's cold path was not re-run from scratch.
- Asset budgets (triangle/texture limits per asset class) and naming/export rules for the wider library.
