# Castaway (`assets/castaway/`)

Rigged human castaway for Paradise Island: 2.00 m, lanky, lean and fit, deeply suntanned, with a long wild sun-bleached beard and hair, a frayed maro (loincloth) and bare chest/feet; a separate reusable walking staff / fishing pole / spear; 142 clips in animation packs. Built independently in this repository (Blender 5.2 `bpy` + numpy kinematics). **Not integrated into the game.**

| File | What | Size |
|---|---|---|
| `Castaway.glb` | Model (LOD0) + core clips (idle, walk, brisk walk, run) · 71,643 tris | 10.35 MB |
| `Castaway_anim_canoe.glb` | Animation pack (skeleton only) | 0.92 MB |
| `Castaway_anim_climbing.glb` | Animation pack (skeleton only) | 1.03 MB |
| `Castaway_anim_fishing.glb` | Animation pack (skeleton only) | 1.33 MB |
| `Castaway_anim_locomotion.glb` | Animation pack (skeleton only) | 1.18 MB |
| `Castaway_anim_personality.glb` | Animation pack (skeleton only) | 4.60 MB |
| `Castaway_anim_posture.glb` | Animation pack (skeleton only) | 0.88 MB |
| `Castaway_anim_staff.glb` | Animation pack (skeleton only) | 0.47 MB |
| `Castaway_anim_survival.glb` | Animation pack (skeleton only) | 1.60 MB |
| `Castaway_anim_water.glb` | Animation pack (skeleton only) | 0.38 MB |
| `Castaway_anim_wildlife.glb` | Animation pack (skeleton only) | 1.34 MB |
| `Castaway_lite.glb` | Lite: skin 7.8k tris, 512² atlases, core hair cards · 24,230 tris | 5.51 MB |
| `Castaway_lod1.glb` | LOD1: skin 19k tris, 1024² skin atlases, fewer hair cards · 41,417 tris | 6.96 MB |
| `Staff.glb` | Walking staff / fishing pole / spear (2.10 m) with attach empties, grip wraps, line guides, optional line + hook · 22,746 tris | 1.71 MB |
| `castaway_bones.json` | Skeleton, bone groups, upper-body mask | 0.02 MB |
| `castaway_clips.json` | Machine-readable metadata for every clip | 0.25 MB |
| `castaway_face.json` | Face controls, expression and viseme presets | 0.02 MB |
| `castaway_grips.json` | Staff mount transforms (hands, back) | 0.03 MB |
| `staff_points.json` | Staff attach points | 0.00 MB |
| `props/*.glb` | Low-poly **proxy** props for viewer tests (canoe, paddle, boulder, rock, log, campfire, palm trunk): not final art | |
| `source/Castaway_rig.blend` | Editable rig/model source (bpy 5.2.2, images packed) | |
| `previews/` | Reference sheet, UV layouts, texture atlases, wireframes, staff sheet, turntable and clip GIFs, per-group animation contact sheets | |
| `validation/` | Structural + Khronos validator reports | |

See `docs/CASTAWAY_ANIMATION_LIBRARY.md` (every clip), `docs/CASTAWAY_INTEGRATION.md` (how to wire it into a game) and `docs/CASTAWAY_HANDOFF.md` (rebuild + status).
