# Prompt for Claude Code (desktop app) — integrate the monkey into Paradise Island

Open Claude Code in the **Paradise Island game repository**, then paste everything below the line.

---

I want you to integrate a new, finished monkey asset into this game (Paradise Island, Three.js). The asset was built in a separate
asset-workshop repository and is complete; your job is the game-side integration only.

## Source of the asset

- Repo: https://github.com/madema-art/Paradise-Island-3d-assets, branch `claude/lucid-cannon-8xjp9h` (no PR exists; that branch is the handoff).
- Clone it OUTSIDE this game repo (for example `git clone --branch claude/lucid-cannon-8xjp9h --single-branch <url> ../paradise-island-3d-assets`).
- Read these first, in order: `docs/MONKEY_INTEGRATION.md` (your main guide), `assets/monkey/README.md` (files, spec, per-clip table
  with speeds and QA numbers), `assets/monkey/monkey_clips.json` (per-clip metadata), `docs/HANDOFF.md`, `viewer/README.md`.
- Run the workshop viewer (`python3 -m http.server` in that repo, open `/viewer/`) to see every clip before wiring anything. It is
  the reference for how the asset is supposed to look and move, including paired clips, climbing and travel simulation.

## Rules

1. Treat the workshop repo as read-only. Copy files out of it; do not edit its GLBs, clips or tools. If the asset needs a change
   (a clip is wrong, proportions are off, a bone is missing), do not patch the GLB by hand. Write a precise bug report (clip or bone,
   what is wrong, a screenshot or numbers) for me to take back to the asset workshop.
2. Work on a new branch in the game repo (for example `feature/new-monkey`). Do not commit to the main branch. Do not push or open a
   PR until I say so.
3. Before changing anything, inspect how monkeys currently work in the game: the model/mesh construction, state machine or AI, animation
   code, coconut logic, tree climbing, collisions, rendering and performance settings. Summarise what you found and your integration
   plan, then proceed unless something is risky or ambiguous. Ask me only about decisions that are really mine (for example removing
   the old monkey for good).
4. Keep the old monkey implementation working until the new one is verified (behind a flag or switch), then remove it only after I confirm.
5. Do not change unrelated gameplay, other creatures, or visuals beyond what this integration needs.

## What to build

1. **Assets:** copy `Monkey.glb`, `Monkey_lite.glb`, `Monkey_lod1.glb`, `coconut.glb` and `monkey_clips.json` into the game's asset
   folder (follow the game's existing conventions). The GLBs are self-contained (embedded textures); the standalone textures under
   `assets/monkey/textures/` are only needed if the game's loader pipeline wants them separate.
2. **Loading/instancing:** load with GLTFLoader (add DRACO/KTX2 only if the game already uses them), then create each monkey with
   `SkeletonUtils.clone`. Share geometry, materials and textures between instances. Use an `AnimationMixer` per monkey and the clip
   names from `monkey_clips.json`. The asset faces +Z, is in metres, about 0.46 m head-to-body; scale to the game's world.
3. **Animation controller:** a small state machine that maps game behaviour to clips with crossfades, using the behaviour-to-clip
   table and chaining rules in `MONKEY_INTEGRATION.md`. Important conventions from that guide:
   - Locomotion clips are in-place. Drive speed with `action.timeScale = actualSpeed / clip.speed_mps` so feet do not slide.
   - `turn_in_place_*` bake yaw into the root: apply the yaw to the character heading when the clip ends.
   - `hop` bakes +0.20 m forward; `startled` bakes a small backwards move; check the notes for each root-motion clip.
   - Climbing: `climb_start` → `climb_up` / `climb_down` / `climb_hang_idle` → `climb_dismount`. The trunk is on the monkey's front side
     at 0.12 m radius; if the game's palm trunks differ, position the monkey at the trunk surface and report the mismatch rather than
     retuning clips.
   - Blinking is already baked into the clips. Do not add procedural eyelid animation unless needed.
4. **Coconut interaction:** attach `coconut.glb` to the `coconut_attach` bone only while a clip with `uses_coconut: true` plays. For
   two monkeys contesting one coconut, use the paired clips `coconut_tug_holder` and `coconut_tug_challenger` with the spacing
   described in the guide; use `coconut_approach`, `coconut_reach`, `coconut_grab_lift`, `coconut_hold_idle`, `coconut_inspect`,
   `coconut_guard`, `coconut_triumph`, `coconut_lose` and `coconut_carry_walk` for the rest of the sequence. Several monkeys must be
   able to converge, guard, inspect and contest one coconut plausibly.
5. **LOD and quality tiers:** use `Monkey.glb` near the camera, `Monkey_lite.glb` for lower quality settings, and `Monkey_lod1.glb`
   for distant monkeys (it has no clips; bind the main skeleton's clips as the guide explains, or freeze it at a pose if that is
   not practical). Add culling or throttled mixer updates for monkeys off-screen or far away.
6. **Lighting/material check:** the fur uses MeshPhysicalMaterial with sheen and an ORM map. Verify it looks right under the game's
   lights, tone mapping and colour space (outputColorSpace sRGB; textures already flagged correctly in the GLB). Adjust only the
   game's lighting if needed, not the asset's textures.

## Verification (do all of this and report real results)

- Run the game and confirm: the monkey loads without console errors or warnings; every clip plays; transitions look sane; no foot
  sliding at game speeds; climbing contacts the trunk; coconut attaches and detaches cleanly; two or more monkeys can contest a coconut
  without interpenetrating.
- Take screenshots (or use the built-in browser) of at least: idle, walk, climbing, grooming, coconut hold, and the paired tug, in the actual game scene.
- Measure frame time and draw calls with 1, 5 and 15 monkeys, at both quality tiers. Report numbers and anything that regressed.
- Run the game's existing tests/lint/build. Fix anything this integration broke.

## Final report

Tell me: what files you changed or added; how the controller maps behaviours to clips; which clips you verified in-game and how;
what did not work or looks wrong (with screenshots/numbers); performance results; any bug reports to take back to the asset
workshop; and what is left before the old monkey can be removed.
