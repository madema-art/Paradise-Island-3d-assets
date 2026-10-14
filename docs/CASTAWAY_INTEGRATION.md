# Castaway: integration guide (for Claude Code running next to the game)

> **Scope and honesty.** This workshop is independent of the game. The game lives at `D:\Paradise Island`, which is **not reachable from Claude Cloud**, so
> `src/human.js`, `src/castaway_mind.js` and `blender/cast_export.py` were **never opened** while building these assets. Nothing in the game was modified and the
> castaway's AI/scheduling logic was **not** rewritten or reproduced here. The state→clip table below uses the behaviour names from the brief
> (survival, fishing, canoe, wildlife, climbing, personality, …); **reconcile them with the real names in `castaway_mind.js` before wiring anything.**
> Do not integrate until the owner asks.

## 1. What to copy

From `assets/castaway/`: `Castaway.glb` (or `Castaway_lod1.glb` / `Castaway_lite.glb`), the `Castaway_anim_*.glb` packs you need, `Staff.glb`, and the three
JSON tables (`castaway_clips.json`, `castaway_face.json`, `castaway_grips.json`). `props/*.glb` are viewer proxies only (canoe, paddle, boulder, rock, log, campfire,
palm trunk); the game has its own canoe/props. Coconut and fish are expected to come from the game or from `assets/monkey/coconut.glb`.

## 2. Loading (Three.js r186, same API as the monkey)

```js
const gltf = await loader.loadAsync('Castaway.glb');            // model + core clips (idle_relaxed, idle_breathe, idle_look_around, walk, walk_brisk, run)
const root = SkeletonUtils.clone(gltf.scene);                   // one clone per castaway (meshes share GPU buffers)
const mixer = new THREE.AnimationMixer(root);
const clips = new Map(gltf.animations.map(c => [c.name, c]));
async function ensurePack(pack) {                                // skeleton-only GLBs: tracks bind by node name
  const g = await loader.loadAsync(`Castaway_anim_${pack}.glb`);
  g.animations.forEach(c => clips.set(c.name, c));
}
hair.material.alphaToCoverage = true;                            // CastawayHair is alphaMode MASK + doubleSided: alpha-to-coverage gives soft edges with MSAA
```
`castaway_clips.json → clips[name].pack` tells you which pack a clip is in. Load packs lazily (they are 0.4 to 4.6 MB each; `Castaway.glb` is 10.3 MB, mostly textures).

## 3. Conventions

* Scale 1 unit = 1 m, **+Y up, the character faces +Z**, +X is his left. The root of the hierarchy is the `root` bone/node at the feet.
* Bone-local frames in the GLB equal the Blender bone frames; animation tracks are therefore plain `rest ⊗ basis` rotations (no axis swizzle). 110 joints, 30 fps, linear keys, loops are closed by repeating the first frame.
* **Root motion (never uncontrolled).** Every clip's `root_motion.type`:
  * `in_place`: the root is fixed. Loops with a `reference_speed_m_s` (walk 1.30, walk_brisk 1.90, run 4.30, sprint 5.4, wade 0.95, walk_staff 1.20 …): move the entity at your speed and set `action.timeScale = speed / reference_speed_m_s`; feet are planted in world space at the reference speed.
  * `path`: starts, stops, turns, cuts. The root does not move; `root_motion.speed_curve_m_s[i]` and `yaw_curve_deg[i]` (30 Hz, relative to the heading at clip start) tell the controller how to move/turn the entity so the planted feet do not slide. Play at timeScale 1.
  * `anchored`: `canoe_board`, `canoe_exit`, `canoe_sit_down`, `climb_onto_boulder`, `climb_down_boulder`, `step_down_rock`. The `root` node is animated relative to a named anchor (`anchor`: `shore`, `canoe`, `boulder_base`, `rock_base`; start/end offsets are in `root_start_m` / `root_end_m`). Place the entity at the anchor frame, play, then **re-parent / re-seat** at the end.
  * `vertical`: `tree_climb_up/down` are in place; move the entity along the trunk at `climb_speed_m_s` (negative = down).
* Clips that are seated in the canoe lift the root by 0.12 m themselves (hull floor); the thwart seat is 0.30 m above the water line. Rocks/logs for `rest_on_rock` etc. are 0.50 m.

## 4. State → clip map (names from the brief; verify against the game)

| Game behaviour (brief) | Clips | Notes |
|---|---|---|
| Idle / standing | `idle_relaxed`, `idle_breathe`, `idle_weight_shift`, `idle_look_around` | pick randomly every 8 to 10 s, cross-fade 0.3 s |
| Walk / brisk / run, start, stop, turn, direction change | `walk`, `walk_brisk`, `run`, `sprint_away`, `walk_start`, `run_start`, `walk_stop`, `walk_brisk_stop`, `run_stop`, `turn_left_90`, `turn_right_90`, `turn_180`, `run_cut_left/right` | starts end at loop phase 0, stops begin at phase 0 (see `start_pose`/`end_pose`); use the exported speed/yaw curves |
| Wading, swimming, floating | `wade`, `swim_crawl`*, `swim_breaststroke`*, `float_on_back`, `tread_water`* | water clips are authored for a water line near the pelvis (`swim_height`); \*in development |
| Walking with the staff | `walk_staff`, `walk_staff_start`, `walk_staff_stop`, `idle_staff`, `idle_staff_lean`, `staff_pickup` | the staff follows the `prop_staff` bone |
| Sit / kneel / lie / sleep / wake | `sit_down`, `sit_idle`, `stand_up`, `kneel_down`, `kneel_idle`, `kneel_rise`, `lie_down`, `fall_asleep`, `sleep_loop`, `wake_up`, `stretch_after_sleep`, `sit_on_rock`, `rest_on_rock`, `rise_from_rock` | transitions are one-shots with exact start/end poses |
| Drinking, eating, coconuts | `drink_cupped_hands`, `wipe_mouth`, `coconut_pickup`, `coconut_crack`, `coconut_drink`, `eat_food`, `prepare_food` | attach coconut/food to `attach_hand_R/L` at the listed events (`props.attach`) |
| Fire, rain, rest | `tend_fire`, `turn_fish_on_fire`, `rest_by_fire`, `shelter_from_rain`, `sit_watching_rain` | fire position (`extra.fire_pos`) is 0.8 m ahead; the clips `look` at it |
| Fishing (pole) | `fish_prepare_rod`, `fish_cast`, `fish_wait_stand`, `fish_bite_reaction`, `fish_reel_in`, `fish_lift_catch`, `fish_inspect_catch`, `fish_celebrate`, `fish_fail`, `fish_reset` | pole = `Staff.glb`, show the optional line + hook nodes; events `line_release`, `tip_dip`, `set_hook` |
| Spearfishing | `spear_stance_idle`, `spear_aim`, `spear_thrust`, `spear_recover_miss`, `spear_catch_lift` | staff as spear (`staff_use: spear`) |
| Outrigger canoe | `canoe_board`, `canoe_sit_down`, `canoe_sit_idle`, `canoe_paddle` (right) / `canoe_paddle_left` / `canoe_paddle_hard`, `canoe_drift`, `canoe_fish_seated`, `canoe_reel_in`, `canoe_exit`, `canoe_pull_on_land` | paddle on `prop_aux` |
| Wildlife | `observe_animal`, `birdwatch`, `look_up_sky`, `track_animals`, `approach_carefully`, `stalk_rat`, `spear_thrust_ground`, `spear_ground_recover`, `startled`, `sprint_away`, `run_look_back`, `catch_breath`, `chase_monkey`, `laugh_after_chase`, `curious_reaction` | the monkey chase uses `chase_monkey` (3.9 m/s); reuse `laugh_after_chase` afterwards |
| Climbing / terrain | `climb_approach_tree`, `reach_for_handhold`, `tree_climb_up/down`, `tree_hold_rest`, `clamber_rocks`, `balance_uneven`, `high_lookout`, `look_down_from_height`, `climb_onto_boulder`, `climb_down_boulder`, `step_down_rock` | |
| Personality | `laugh_quiet`, `laugh_hearty`, `frustration`, `disappointment`, `excitement`, `surprise`, `confusion`, `head_scratch`, `contemplation`, `sigh`, `stretch_standing`, `yawn`, `whistle`, `hum_sing`, `shout`, `talk_to_self`, `celebrate`, `embarrassed_recover`, `dance_sway/hop/stomp/hula/twist`, `clap`, `wave_hello`, `shrug`, `nod_yes`, `shake_no`, `look_curious`, `lounge_sit_back`, `lounge_recline`, `play_toss_catch`, `play_kick_sand`, `play_flex_pose`, `play_skip` | |

Every clip has `blend.blend_in_s/blend_out_s`, `interruptible` (`any`, `after_step`, `none`), `events` (author events plus automatic `foot_down_L/R` / `foot_up_L/R` for footstep sounds), `qa`, `status` and `props` in `castaway_clips.json`. Cross-fade with the recommended times; for gait clips start the next loop at the phase named in `start_pose`/`next_phase`.

## 5. Props and attachments

* **Staff / pole / spear**: add `Staff.glb` as a child of the **`prop_staff` bone** and do nothing else: the clips move that bone so the hands grip the shaft. Hold it without a clip using `castaway_grips.json` (`R_main`, `R_upper`, `L_main`, `back_sling`, …: bone, position `p`, quaternion `q` for the staff root). Shaft = local +Y (2.10 m, butt at the origin), guide side = local +Z. Attach empties (`attach_grip_*`, `attach_tip`, `attach_line`, `attach_guide_1..4`) and `Staff_line` / `Staff_hook` (hidden by default) are in the GLB; positions in `staff_points.json`.
* **Paddle**: child of the **`prop_aux`** bone (blade tip at the origin, shaft +Y).
* **Coconut / fish / food**: parent to `attach_hand_R` or `attach_hand_L` when the clip event named in `props.attach[].from_event` fires (`attach_coconut_R` in `coconut_pickup`), using the palm normal from `castaway_grips.json` for the offset.
* The staff bone parks at (0, −0.3, 0.97) when unused: **hide `Staff.glb` unless the clip lists `staff` in `props.uses`.**

## 6. Layers, face, secondary motion

* **Upper-body layers**: 31 standing clips have a `<name>__upper` animation containing only the spine/arm/neck/head/face/hair bones (`upper_body_mask`). Play a base loop (idle, walk) at weight 1 and the layer on top; for a layer weight *w* give the overlay action weight `w/(1-w)` (three.js blends per property). The viewer's "Upper-body layer" control does exactly this.
* **Face**: `castaway_face.json` lists 19 controls (jaw, smiles, brows, blinks, pucker, lips, squint, cheek, gaze) with node-local rotation/translation deltas; apply `quaternion = clip ⊗ slerp(I, q, w)` and `position += w·t` after `mixer.update()`; reset those bones before the update. Presets: `friendly`, `grin`, `anger`, `surprise`, `laugh`, `sun_squint`, `whistle`, … and 10 visemes (`AA EE IH OH OO FV MBP TH L sil`). The viewer's face tester is the reference implementation.
* **Secondary motion** (hair back/side chains, beard chains, maro tails/hem) is **baked** into the clips by a spring simulation with a floor clamp, so it plays back identically in any engine; there is no runtime simulation to run.

## 7. Budget

LOD0: skin 46.0k tris + hair/beard cards 18.5k + maro 2.8k + mouth/eyes ≈ 72k tris, 110 joints, 4 draw groups (skin head, skin body, hair, eyes/maro/mouth); 2048² head and body atlases (JPEG albedo/normal, 1024 PNG ORM). LOD1: 41k tris (skin 19k, 1024²). Lite: 24k tris (skin 7.8k, 512²). Keep animation packs unloaded until a behaviour needs them.

## 8. What is verified and what is not

See `docs/CASTAWAY_ANIMATION_LIBRARY.md` for the per-clip status. Everything was tested in headless Three.js r186 (software WebGL) against the real GLBs; **in-game performance, collision, and the real behaviour names are untested.**
