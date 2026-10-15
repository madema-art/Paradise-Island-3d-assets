# Giant manta ray: handoff to the game repository

**Status:** asset workshop only. Nothing here is wired into the game. The last step (replacing the game's procedural manta and making it noticeable in play) is for the local Claude Code session that works in the game repository.

**Why this exists:** the game's original manta was generated procedurally in code. This is the first Blender-authored version: a skinned, rigged mesh with ten clips, plus a behaviour spec designed to make the manta easy to notice from the player's side of the lagoon.

Preview (private, owner only): https://claude.ai/artifact/SkuLE4corUxLQ1qRcA6Y37

## 1. What to take

| File | Use in the game |
|---|---|
| `assets/manta/Manta.glb` | The creature. One skinned mesh, 13 bones, 10 animation clips, two embedded textures. Load with the game's glTF loader. |
| `assets/manta/manta_clips.json` | Clip durations, loop flags and frame counts (30 fps). Use it to check that every name the game expects exists. |
| `assets/manta/manta_behavior.json` | **The behaviour config.** States, ranges, speeds, timers, cooldowns, clip mapping and noticeability notes. Read it, don't hard-code copies of it. |
| `assets/manta/behavior_report.json` | Headless simulation of the config (20 runs × 1 h × 3 mantas). Shows what the numbers produce. |
| `assets/manta/Manta.blend` | Editable source (bpy 5.2.2). Regenerate the GLB from `tools/manta/build_manta.py`, don't hand-edit it. |
| `assets/manta/validation/` | Structural and Khronos validator reports: both PASS, 0 errors, 0 warnings. |
| `tools/manta/` | Geometry (`design.py`), textures, clips (`clips.py`), the Blender build, behaviour and the pose renderer. |

## 2. The creature

Units are metres, Y-up in the glTF. The origin is the disc centre on the midline; the rig is in place (no root motion baked in).

| Measure | Value |
|---|---|
| Wingspan (wing tip to wing tip) | 6.0 m |
| Length (head to tail tip) | 5.0 m (disc about 2.6 m, tail about 2.5 m) |
| Height (wing tips curl up) | 0.49 m |
| Triangles / vertices | 2,332 / 1,208 (one LOD) |
| Materials | 6: dorsal (textured), ventral (textured), mouth, gill, eye, tail |
| Textures | dorsal 512², ventral 256², both embedded as PNG |
| File size | 0.74 MB |

Anatomy, for the animator and for reading the clips: two pectoral wings that form the disc, two cephalic lobes (the curled horns at the front, `head_L` / `head_R`), a dark mouth patch on the underside, five gill slits per side, dark eyes on top, and a long thin tail with no fin.

Bones: `root`, `body`, `head_L`, `head_R`, `wing_L1–3`, `wing_R1–3`, `tail1–3`. The skin uses at most four weights per vertex, with a smooth falloff so the wings bend without tearing.

## 3. Clips

Every clip is in place. The game owns heading, speed, depth and position. Loop clips repeat seamlessly (their last key equals their first).

| Clip | Length | Loop | What it is | Use it for |
|---|---|---|---|---|
| `glide_cruise` | 2.4 s | yes | Slow flap, a travelling wave along the wings, tail sway | Default patrol |
| `glide_gentle` | 5.0 s | yes | Almost still, slow ripple | Hovering, waiting, distant or sleepy |
| `flap_power` | 1.1 s | yes | Strong beats | Fleeing, chasing, fast travel |
| `feed_open` | 5.0 s | yes | Lobes unroll, wings cup up, disc tilts up | Feeding in a bloom |
| `curious_approach` | 4.0 s | yes | Head up, lobes curl and uncurl | Investigating a slow player |
| `turn_left` / `turn_right` | 2.4 s | no | Bank into the turn, wings counter-dip | Heading change above about 25° |
| `startle_burst` | 1.2 s | no | Wings snap up, lobes fold back, tail whips | Bolting (then `flap_power`) |
| `breach_rise` | 3.0 s | no | Nose-up leap, wings spread, tail trails | Breach, step 1 |
| `breach_fall` | 2.5 s | no | Drops back, wings flutter open, settles | Breach, step 3 (re-entry) |

Blend between clips with a short crossfade (0.2–0.3 s). Breach clips play once and hold on the last frame until the game switches them.

## 4. Behaviour

The state machine lives in `assets/manta/manta_behavior.json`. Summary:

| State | Entered when | Motion | Leaves when |
|---|---|---|---|
| `patrol` | default | Glide at 1.4 m/s between waypoints in a 150 m disc round its home reef, depth 6–14 m | A trigger fires, or a bolt |
| `curious` | player within 32 m, moving under 2.5 m/s, cooldown done | Orbit at 7–10 m, 0.9 m/s, 12–20 s | Hold ends, or player moves over 4 m/s |
| `shadow_pass` | player 25–60 m away, cooldown done | Glide over the player at 6 m depth, 9 s | Hold ends |
| `feed` | a bloom zone exists and cooldown done | Drift at 0.45 m/s inside the bloom, 20–40 s | Hold ends |
| `breach` | player 25–80 m away, roll succeeds, cooldown done, world breach cooldown done | `breach_rise` → hang → `breach_fall`, 5.8 s total | Clip ends |
| `flee` | player within 6 m, or a thrown or speared object within 12 m | Bolt at 4.0 m/s for 12 s, `startle_burst` then `flap_power` | Hold ends |

Cooldowns (per manta unless noted): curious 600 s, shadow pass 240 s, breach 240–420 s, feed 1200 s. **Breach is also limited to one anywhere in the world every 90 s.**

Triggers are rolled per second while eligible (`rates_per_s_when_eligible`): breach 1/40, curious 1/45, shadow pass 1/90, feed 1/90. Priority when several are eligible: breach, curious, shadow pass, feed.

### What the simulation says (20 runs, 1 h, 3 mantas each)

| Measure | Result |
|---|---|
| Time a player spends with a manta within 90 m | **about 21%** (simulated; see caveats below) |
| Breaches per manta-hour | about 6.5 (one about every 9 min per manta) |
| Curious / shadow pass / feed per manta-hour | about 0.9 / 1.8 / 3.0 (feed is at its cooldown cap) |
| Shortest gap between two breaches anywhere | 91 s (cap is 90 s) |
| Speed | median 1.4 m/s, maximum 4.0 m/s (only while fleeing) |

The simulation is a stand-in for the game's world. It places the player on a random walk around the lagoon and does not model the game's terrain, obstacles, line of sight or the real player's path. Treat its numbers as tuning starting points, not as measurements of the game.

## 5. Noticeability: what makes it stand out in play

These are the reasons for the design. Keep them when you wire the game:

1. **Silhouette.** Pale underside against a dark back, with wings held wide, reads at 90 m against both sand and deep water. Keep the creature's scale true: don't shrink it to fit a path.
2. **Shadow.** Project a soft dark blob the size of the wingspan onto the seabed while altitude is under 12 m, fading out by 20 m. This is the cue that announces the manta before the body is clear.
3. **Sound.** A spatialised wing-beat on every flap (about every 2.4 s cruising, every 1.1 s when powered), audible to about 60 m. This is the cue that makes a player look up.
4. **Event cues.** A splash and a ripple ring on breach, and a short whoosh when it bolts. Breaches are the moment the manta is most noticed: give them the strongest cue.
5. **Frequency.** A manta is in view about a fifth of the time an explorer is in the lagoon, and a breach comes about every 6–10 minutes per manta while explorers are around. If playtesting says it's too rare, raise the breach roll before shortening cooldowns: that keeps breaches special.

## 6. Integration steps for the game repository

Do these in order, in the game repository. Keep the existing procedural manta behind a flag until the new one passes the checks in section 7.

1. **Load the GLB.** Add `Manta.glb` to the game's assets. Check that it loads through the game's glTF loader, that the skin and all 10 clips are present, and that the names match `manta_clips.json`.
2. **Swap the mesh, keep the spawner.** Replace the procedural mesh with the GLB but leave the spawn points, counts and placement alone for this step. This isolates the visual change.
3. **Wire the clips.** Map states to clips as in section 4. Crossfade 0.2–0.3 s. Play one-shots once, then hold.
4. **Root motion stays in code.** Apply heading and speed to the entity's transform. Never bake travel into a clip. The head points to +X in the glTF (the tail to −X), so the entity's forward is +X when the heading is zero. Blender's Y becomes glTF −Z and Blender's Z becomes glTF +Y.
5. **Implement the state machine** from `manta_behavior.json`. Read every number from the file (or copy them into the game's data once, with a comment pointing at the file). Keep the cooldowns, the world-wide 90 s breach limit and the trigger priority.
6. **Add the noticeability layer:** the seabed shadow, the spatial wing-beat sound, the breach splash and ripple, and the bolt whoosh. These can come after the core state machine, but they are part of the goal.
7. **Tune in the workshop first.** If a number needs to change, change it in `manta_behavior.json`, re-run `python3 tools/manta/behavior.py`, check `behavior_report.json`, then copy it into the game.
8. **Remove the procedural manta** only after the checks in section 7 pass.

## 7. Acceptance checks

- The GLB loads in the game with no console errors, and all 10 clips are present.
- Each state plays its clip, with no pop at loop points and no tearing at the wings or lobes in any clip.
- The manta is visible from about 90 m against sand and deep water, with the silhouette and the shadow both legible.
- Breaches never come closer than 90 s apart anywhere in the world, and the per-manta breach cooldown holds.
- A player who sprints at a manta triggers a bolt inside 6 m, and the bolt speed never exceeds 4.0 m/s.
- Frame time: one manta at 1,208 vertices and 2,332 triangles should cost little. Check it with three or more mantas on screen before adding more.
- Turn off the procedural manta flag and confirm nothing else in the game references it.

## 8. What was verified here, and what was not

Verified in this workshop:
- The build runs end to end in bpy 5.2.2 and writes the GLB and `.blend` (`tools/manta/build_manta.py`).
- The rig's rest-frame conventions match `clips.py` (a probe in the build checks each axis).
- Structural validator: PASS. Khronos glTF validator: 0 errors, 0 warnings (4 info notes about unused UVs on untextured materials).
- Poses were rendered from the saved `.blend` (`assets/manta/previews/`). The wing flap, nose-up breach and cupped feeding pose read as intended.
- The viewer (`viewer/manta.html`) loads the packaged GLB in headless Chromium and plays all ten clips with no page errors.
- The behaviour config runs headless and produces the numbers in section 4.

Not verified:
- The game's current manta code. The game repository is not attached to this session, so these numbers are designed from scratch and haven't been compared with the procedural version's scale or speed.
- Real-time performance in the game and on target hardware.
- Look and feel in the game's lighting, water and camera. The previews use a simple studio scene.
- Spears and thrown objects. The `spear_startle` rule (12 m) is in the config, but the simulation never produces a spear, so its effect on the numbers is untested.
- Playtesting. The 21% visibility and breach rates are simulation results only.

## 9. Rebuilding

```bash
bash tools/blender/setup_blender.sh                                   # bpy 5.2.2 in /opt/bpy-venv (idempotent)
/opt/bpy-venv/bin/python tools/manta/build_manta.py -- --out assets/manta
python3 tools/manta/behavior.py                                       # behaviour report
python3 tools/blender/validate_glb.py assets/manta/Manta.glb --json assets/manta/validation/Manta_structure.json
(cd tools/blender && node validate_glb_khronos.js ../../assets/manta/Manta.glb > ../../assets/manta/validation/Manta_khronos.json)
/opt/bpy-venv/bin/python tools/manta/render_poses.py -- --blend assets/manta/Manta.blend --out build/manta_poses
python3 tools/stage_manta_viewer.py                                   # then publish build/artifact_manta/ (see CLAUDE.md)
```
