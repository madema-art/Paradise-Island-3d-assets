# Giant manta ray (`assets/manta/`)

First Blender-authored giant manta: a skinned 6 m wingspan ray with ten in-place clips and a behaviour spec. It replaces a procedurally generated version in the game. **Not integrated into the game.** The integration handoff and the noticeability goals are in `docs/MANTA_HANDOFF.md`.

Preview (private): https://claude.ai/artifact/SkuLE4corUxLQ1qRcA6Y37

| File | What | Size |
|---|---|---|
| `Manta.glb` | Skinned model (13 bones), 10 animation clips, 2,332 triangles, 1,208 vertices, one LOD | 0.74 MB |
| `manta_clips.json` | Clip durations, loop flags, frame counts (30 fps), axis probe results, bone list | 0.002 MB |
| `manta_behavior.json` | Behaviour config: states, ranges, speeds, timers, cooldowns, clip mapping, noticeability, integration steps | 0.003 MB |
| `behavior_report.json` | Headless simulation: 20 runs, 1 h, 3 mantas each | 0.000 MB |
| `Manta.blend` | Editable source (bpy 5.2.2). Textures packed. | 0.48 MB |
| `textures/` | Dorsal (512²) and ventral (256²) base colour PNGs, procedural | |
| `previews/` | Real renders from the saved `.blend`: cruise, flap, feed, breach and top view | |
| `validation/` | Structural and Khronos glTF validator reports (both PASS, 0 errors, 0 warnings) | |

## Clips

| Clip | s | Loop |
|---|---|---|
| `glide_cruise` | 2.4 | yes |
| `glide_gentle` | 5.0 | yes |
| `flap_power` | 1.1 | yes |
| `feed_open` | 5.0 | yes |
| `curious_approach` | 4.0 | yes |
| `turn_left` | 2.4 | no |
| `turn_right` | 2.4 | no |
| `startle_burst` | 1.2 | no |
| `breach_rise` | 3.0 | no |
| `breach_fall` | 2.5 | no |

All clips are in place (no root motion). Units are metres, Y-up in the glTF. Origin at the disc centre.

## Source

- `tools/manta/design.py`: disc geometry, cephalic lobes, tail, eyes, rig layout, skin weights.
- `tools/manta/clips.py`: the ten clips as functions of time.
- `tools/manta/textures.py`: procedural base colours.
- `tools/manta/build_manta.py`: bpy build (mesh, materials, rig, probe, actions, GLB and `.blend` export).
- `tools/manta/behavior.py`: behaviour config and headless simulation.
- `tools/manta/render_poses.py`: pose renders for review.
- `tools/stage_manta_viewer.py` and `viewer/manta.html`: the private preview artifact.

Rebuild commands are in `docs/MANTA_HANDOFF.md`, section 9.
