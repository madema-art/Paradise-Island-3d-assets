# Castaway workshop handoff

Everything for the castaway is in this repo (branch `claude/lucid-cannon-8xjp9h`). The game was **not** touched; the game sources named in the brief were **not** readable from the cloud
and were **not** inspected.

## Layout

| Path | What |
|---|---|
| `assets/castaway/` | Deliverables: `Castaway.glb` (+ `_lod1`, `_lite`), `Castaway_anim_*.glb` packs, `Staff.glb`, JSON tables, proxy props, editable `source/Castaway_rig.blend`, previews, validation reports, `MANIFEST.json`. |
| `tools/castaway/` | Whole pipeline (below). |
| `viewer/castaway.html/.js/.css` | Castaway viewer (clip browser, compare, camera presets, face tester, staff attachment test, upper-body layering, wireframe/skeleton, lighting presets). `viewer/tests/castaway_capture.mjs` is the headless test, `viewer/tests/shot.mjs` the render tool. |
| `docs/CASTAWAY_INTEGRATION.md` | How a game would use the assets (state→clip map, root-motion rules, props, layers, face). |
| `docs/CASTAWAY_ANIMATION_LIBRARY.md` | Every clip with status (generated). |

## Pipeline (all under `tools/castaway/`)

```bash
# model (≈10 min on 4 cores): SDF anatomy → mesh → weights → UVs → textures → hair/beard/brows → maro/mouth → rig → GLB
bash tools/castaway/build_castaway.sh                 # FROM=hair|assemble|… resumes at a stage; CLEAN=1 forces a re-sculpt
# props
/opt/bpy-venv/bin/python tools/castaway/staff_build.py && /opt/bpy-venv/bin/python tools/castaway/proxy_build.py
# LODs (same UVs, decimated skin, fewer hair cards, smaller atlases)
HAIR_TAGS=scalp0,scalp1,fringe,beard0,stache,brow SKIN_RATIO=0.42 python tools/castaway/assemble_castaway.py --out build/castaway/lod/Castaway_lod1.blend --head-res 1024 --body-res 1024
python tools/castaway/export_castaway.py --blend build/castaway/lod/Castaway_lod1.blend --out build/castaway/lod/Castaway_lod1.glb      # lite: ratio 0.17, tags scalp0,beard0,stache, 512
# animation: bake (parallel + cached), packs, metadata, face/grip tables
python tools/castaway/build_library.py && python tools/castaway/export_face_controls.py && python tools/castaway/export_grips.py
python tools/castaway/package_assets.py && python tools/castaway/make_docs.py
python tools/castaway/make_previews.py --install      # reference sheet, UV/atlas/wire sheets, GIFs, per-group contact sheets
```
Run `build_castaway.sh FROM=assemble` after any LOD build: LOD assembles overwrite the runtime texture folder with smaller textures.

### Animation authoring

* `kin.py` / `pose_lib.py` are pure-numpy kinematics that reproduce Blender's bone math (checked against Blender, 0.0055 mm). `params.py` turns a parameter set (spine/head/arms FK or IK/feet/fingers/face/props) into a solved pose; `clipkit.py` bakes at 30 fps, runs the secondary-motion spring chains (`secondary.py`) and the QA metrics.
* Clip modules: `clips_locomotion/transitions/posture/staff/personality/survival/fishing/canoe/wildlife/climb.py`. Helpers: `posekit.py` (keyposes, IK targets in head/chest space), `staffkit.py` (staff/paddle state + hand fitting), `pathgait.py`/`gaitkit.py`/`steps.py` (world-planted foot steps).
* **Reach assist** (`clipkit.reach_assist_offsets`): frames whose IK hand target is out of reach get a small solved forward bend / pelvis drop so hands really touch what they should (the offsets are smoothed, and the clip's authored values stay the source of truth).
* QA tools: `audit_grips.py` (hand-to-shaft distance for prop clips), `reach_diag.py` (where reach errors occur), `montage.py` (skinned contact sheets from the real GLB), `qa_views.py`.
* Bake cache: `build/castaway/bakecache/` keyed by the sources of the clip module + core kinematics + `rest_pose.json`.

## Known limitations (honest list)

* **Anatomy/face quality**: plausible and consistent but stylised: the torso/limb definition is mostly a few millimetres of sculpted relief plus normal-map detail; the face is partly hidden by the (requested) wild hair and beard. It is not a photoscan-level human.
* **Hair** is cards (alpha-masked strand atlas). Edges look best with MSAA / alpha-to-coverage; the strand atlas is procedural and somewhat uniform.
* **Skin textures** are procedural (position-based, seamless), including freckles and sunspots, rough elbows/knees/hands/feet, face wrinkles and creases; they are not hand-painted.
* **In development**: see `docs/CASTAWAY_ANIMATION_LIBRARY.md`, "Clips in development" (water/swim clips are first passes).
* Props `props/*.glb` are proxies. Canoe and rock/boulder/palm geometry in the game will differ: anchored clips (boarding, boulder, rock) assume the dimensions listed in the clip metadata.
* The Artifact host serves no `.glb`; `tools/stage_artifact_viewer.py` publishes identical bytes as `*.glb.wasm`.
* Not tested: in-game performance, the game's own behaviour names, GPU rendering (all checks used SwiftShader).
