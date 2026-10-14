# Monkey: integration guide for Paradise Island

Audience: Claude Code running locally against the real game. Nothing in this repository touches the game; this document says
what the asset package is, how it behaves, and what to verify when it is wired in.

> **Not verified here:** the game's current monkey code, its clip/state names and its coordinate/scale conventions were not
> available in this repository. Everything below assumes a standard Three.js scene (Y up, 1 unit = 1 m). Re-check those
> assumptions against the game first.

## 1. Files (`assets/monkey/`)

| File | Use |
|---|---|
| `Monkey.glb` | Hero build: skinned body + eyes + eyelids, 2048² albedo / normal, 1024² ORM, **41 animation clips**. ≈12 MB. |
| `Monkey_lite.glb` | Same rig, same clips, 1024² albedo/normal and 512² ORM. ≈7.6 MB. |
| `Monkey_lod1.glb` | 15k-triangle body + eyes on the **identical skeleton**, no clips, no eyelids. ≈2.3 MB. |
| `coconut.glb` | Static coconut prop (5k tris, 512×256 albedo, normal map). Radius 0.062 m. |
| `monkey_clips.json` | Per-clip metadata (see §4). The runtime should read this, not hard-code it. |
| `monkey_bones.json` | Skeleton hierarchy as exported. |
| `Monkey.blend`, `Coconut.blend` | Editable Blender 5.2.2 sources (rig, IK control bones, baked actions). `textures/` sits next to the blend. |
| `textures/` | Runtime textures, plus lossless sources in `textures/source/`. |
| `previews/`, `validation/`, `MANIFEST.json` | Reference renders, validator reports, file hashes. |

Open `viewer/index.html` (via `python3 -m http.server`) to inspect everything before integrating.

## 2. Conventions

* **Units / orientation:** 1 unit = 1 m. glTF standard: **+Y up, the monkey faces +Z**, its left is +X. Origin is on the ground
  between the feet (the `root` bone sits at the origin). Body ≈ 0.46 m nose-to-rump, ≈ 0.95 m with the tail, ≈ 0.30 m at the shoulder.
* **Nodes:** the GLB contains one `MonkeyRig` armature node (identity transform) with the skeleton and 7 skinned meshes as children:
  `Monkey_Body`, `Monkey_Eye_L/R`, `Monkey_Lid_Up_L/R`, `Monkey_Lid_Low_L/R`. All share **one skin of 102 joints** (max 4 influences/vertex).
* **Bone names use underscores** (`upper_arm_L`, `f_index_2_R`, `tail_7`) so Three.js' name sanitising does not alter them.
* **Materials:** `MonkeyFur` (base colour + normal + ORM: R = AO, G = roughness, B = metal; `KHR_materials_sheen`, `KHR_materials_specular`),
  `MonkeyEye`, `MonkeyLid`, `MonkeyLidEdge`. GLTFLoader builds `MeshPhysicalMaterial` automatically.
  There is **no tangent attribute** on purpose: the normal map was baked against UV-derivative tangents, which is what Three.js
  computes when tangents are absent. Do not add MikkTSpace tangents.
* **Lighting:** fur needs an environment map (sheen + roughness 0.85). The viewer uses `RoomEnvironment` + one directional light
  + `NeutralToneMapping`; those settings are a good starting point.

```js
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
const gltf = await new GLTFLoader().loadAsync('assets/monkey/Monkey.glb');
const monkey = gltf.scene;                       // contains the armature + 7 skinned meshes
monkey.traverse(o => { if (o.isSkinnedMesh) { o.frustumCulled = false; o.castShadow = true; } });
const mixer = new THREE.AnimationMixer(monkey);
const clips = Object.fromEntries(gltf.animations.map(c => [c.name, c]));
mixer.clipAction(clips.idle).play();
```

## 3. Skeleton

`root` → `pelvis` → `spine1..3` → `neck1..2` → `head` → (`jaw`, `ear_L/R`, `eye_L/R`, `lid_up_L/R`, `lid_low_L/R`);
`spine3` → `clavicle_L/R` → `upper_arm` → `forearm` → `hand` → fingers `f_{index,middle,ring,pinky}_{1..3}` and thumb `f_thumb_{0..2}`;
`pelvis` → `thigh` → `shin` → `foot` → toes `t_{index,middle,ring,pinky}_{1..3}` and `t_hallux_{0..2}`; `pelvis` → `tail_1..10`;
`root` → `coconut_attach` (prop bone, see §6). The IK control bones used to author the clips were **not exported**; all limb
motion is baked onto the deform bones, so the runtime needs no IK.

Useful procedural hooks (apply after `mixer.update`, as additive local rotations): `neck1/neck2/head` (look-at), `eye_L/R` (gaze),
`ear_L/R` (flicks), `jaw` (**≤ 10°**, see limitations), `lid_up_*` (+) / `lid_low_*` (−) rotate about the lateral axis to close the eye
(about +55° / −39° shuts it; negative upper / positive lower widens it). Natural blinks are already baked into every non-static clip.

## 4. Animation conventions

30 fps. `monkey_clips.json` gives, per clip: `seconds`, `loop`, `group`, `description`, and where relevant `speed_mps`, `travel_m`,
`yaw_deg`, `trunk_side`, `uses_coconut`, `pair` data and QA numbers (`reach_error_mm`, `clamp_shift_mm`).

* **Loops are seamless** (last key == first key); one-shots hold their last pose (`clampWhenFinished`).
* **Locomotion clips are in place.** All four contact points move backwards at `speed_mps`, so there is no foot slide when the entity
  moves at that speed: set `action.timeScale = entitySpeed / speed_mps` (walk 0.37 m/s, scurry 1.19 m/s, branch_walk 0.21 m/s,
  coconut_approach 0.21 m/s, coconut_carry_walk 0.28 m/s, climb_up 0.34 m/s, climb_down −0.30 m/s). Keep the timeScale within about
  0.7–1.4 before switching clips. The viewer's *Simulate travel* option shows the ground scrolling at these speeds.
* **Climb clips are in place too** (contacts slide down the bark at `speed_mps`; move the entity up at that speed; `climb_down` is a
  backing-down climb, root moves down).
* **Clips with baked root motion** (the root bone moves/rotates inside the clip): `hop` (+0.20 m forward), `startled` (0.10 m backwards),
  `turn_in_place_L/R` (±90° yaw about the body centre), `climb_start` / `climb_dismount` (ground ↔ trunk), `sit_down` / `stand_up`
  (pelvis drop, root stays). For these, **do not also translate the entity during the clip**; when the clip ends, either let the root
  bone carry the entity (copy `root` world transform back onto the entity and reset the root) or compensate. The last frame of each is
  the pose the next clip expects (see the chaining table).
* Transition by crossfading 0.15–0.3 s between clips whose end/start poses match (chaining table). Do not crossfade into/out of the
  climb clips from ground clips; use `climb_start` / `climb_dismount`.

### Behaviour → clip map

| Game behaviour | Clips | Notes |
|---|---|---|
| Idle / observe | `idle`, `alert_idle`, `look_around`, `sit_idle`, `curious` | `alert_idle` for threat awareness; `curious` returns to the idle pose |
| Walk, scurry, dart | `walk`, `scurry`, `hop` | blend by speed; `turn_in_place_L/R` before moving off in a new heading |
| Turn / quick direction change | `turn_in_place_L/R`, then locomotion | 0.8 s, ±90° |
| Tree climbing | `climb_start` → `climb_up` / `climb_hang_idle` / `climb_down` → `climb_dismount` | Trunk radius is **0.12 m**, trunk on the monkey's +Z side (it faces the bark) |
| Branch / perch | `branch_walk`, `sit_down` → `sit_idle` | `branch_walk` assumes a ≈4 cm horizontal branch, entity origin on top of the branch |
| Grooming | `sit_down` → `groom` (self-groom), `scratch` | looped; exit with `stand_up` |
| Social | `social_greet`, `pose_present`, `threat_display`, `startled` | `threat_display` has one hand-slap per loop |
| Coconut | `coconut_approach` → `coconut_reach` → `coconut_grab_lift` → `coconut_hold_idle` ⇄ `coconut_inspect` / `coconut_guard`; `coconut_carry_walk`; `coconut_triumph`, `coconut_lose`; `coconut_tug_holder` / `_challenger` | see §6 |
| Static interaction poses | `pose_stand`, `pose_crouch`, `pose_sit`, `pose_present`, `pose_threat`, `pose_coconut_hold` | single-frame clips for blending / formation poses |

### Chaining (end pose → start pose)

`idle` ≈ `pose_stand` ≈ start of `walk`/`scurry`/`hop`/`sit_down`/`curious`/`startled`/`turn_in_place_*`/`coconut_reach`.
`sit_down` ends on `sit_idle` frame 0; `stand_up` ends standing. `coconut_grab_lift` ends on `coconut_hold_idle` frame 0;
`coconut_triumph` starts and ends on that pose. `climb_start` ends on `climb_up` frame 0.

## 5. Climbing setup

Place the entity with its root **0.52 m from the trunk surface**, facing the trunk, then play `climb_start` (root travels to y = −0.13 and
tilts the body 80° upright against the bark). During `climb_up` move the entity up the trunk at the clip speed and keep the entity's
horizontal position fixed relative to the trunk surface. For a trunk of radius R ≠ 0.12 m, shift the entity radially by (R − 0.12) m;
hands/feet are not IK-adjusted at runtime, so very different radii will float or penetrate slightly. For a runtime fix, add a
two-bone IK pass on the arms/legs after the mixer.

## 6. Coconut

* `coconut.glb` is a static mesh centred on its origin. **Parent it to the `coconut_attach` bone** (`bone.add(coconut)`); the clips key
  that bone so the nut follows the hands. Show it only for clips with `uses_coconut: true` in `monkey_clips.json`; otherwise hide it
  (the bone is parked inside the torso).
* `coconut_reach` expects the nut resting on the ground **0.56 m in front of the root** (root-local (0, 0.062, 0.56) in glTF axes).
* **Tug of war:** play `coconut_tug_holder` on monkey A and `coconut_tug_challenger` on monkey B simultaneously (same start time,
  same `timeScale`). Place B at `A.position + A.forward × 1.08 m`, rotated 180° about Y, i.e. facing A. The coconut is at the identical
  world position in both clips at every frame, so parent one prop to either monkey's `coconut_attach`. The holder pulls when the
  nut moves towards it (±3 cm travel, three tugs per 1.2 s loop). The metadata fields `partner_clip`, `partner_root_offset`
  (Blender axes: `[0, −1.08, 0]`) and `partner_yaw_deg` describe this.
* A third monkey can use `coconut_approach`, `threat_display`, `startled`, `pose_threat` etc. around the pair.

## 7. LODs, budgets, variants

| Build | Tris (body) | Draw calls | Texture memory (uncompressed GPU) | File |
|---|---|---|---|---|
| `Monkey.glb` LOD0 | 56,000 (+ eyes/lids ≈ 4,300) | 7 meshes / 4 materials | ≈ 50 MB | 12.0 MB |
| `Monkey_lite.glb` | same | same | ≈ 13 MB | 7.6 MB |
| `Monkey_lod1.glb` | ≈ 15,100 (+ eyes) | 3 meshes / 2 materials | ≈ 13 MB (lite textures) | 2.3 MB |

Suggested: LOD0 within ≈ 5 m, LOD1 beyond; use the lite textures when more than a handful of monkeys are on screen. LOD1 carries no
clips: create a second `SkinnedMesh` from `Monkey_lod1.glb` and drive it with the **same clips** (matched by bone name), e.g. a second
`AnimationMixer` on the LOD1 scene using the clips loaded from the hero file. The fur material does most of the visual work, so check that
materials are shared between monkeys to keep draw calls down. Merging the four lid/eye meshes into the body is possible but would
cost the blink; consider hiding the lid meshes beyond ~3 m.

GPU texture compression (KTX2/Basis) was **not** applied; do it in the game's asset pipeline (e.g. `gltf-transform ktx2`) if memory matters.

## 8. Known limitations

* **No mouth interior or teeth.** The jaw bone moves the chin and stretches the painted lip seam; keep `jaw` rotations ≲ 10°. Threat
  "gape" is implied by head posture, ears and tail, not a visible open mouth.
* **Fur is texture-only** (flow-aligned strands in albedo + normal map, sheen). The silhouette is soft/clean, no fur cards or shells.
* **Eyelids are shells**, good for blinks, squints and wide-eye; they bulge slightly when closed at very close range.
* **Texture atlas:** 2048² with ≈ 270 charts and 63 % utilisation; seams are invisible in albedo (painted continuously in 3D) but mip
  bleed is possible at long distance with aggressive mip bias.
* Hands/feet follow baked IK. Contact is exact in the authored world frame (reach error ≤ 15 mm in all clips; see `monkey_clips.json`),
  but there is no runtime IK, so uneven ground or different trunk radii need a runtime pass.
* The hop and startle bake root motion; the turn clips bake yaw. Plan entity movement accordingly (see §4).
* Validators report benign warnings: runtime-generated tangents and "skinned mesh node is not root" (children of the identity armature node).
* **Tested only in headless Chromium with software WebGL (SwiftShader).** Real-GPU frame rate, mobile, WebGPU and the actual game were not tested.

## 9. Verification checklist for the integration session

1. Load `Monkey.glb`; confirm orientation (+Z forward) and scale (0.30 m shoulder height) against the game's other animals.
2. Play every clip once; compare with `previews/pose_sheets/*.jpg` and `previews/gifs/*.gif`.
3. Drive `walk`, `scurry`, `branch_walk` at their `speed_mps` and watch for foot slide; adjust `timeScale` limits.
4. Run the climb chain on a trunk of radius 0.12 m, then your real trunk radius.
5. Run the paired tug with two entities; check the nut stays between both monkeys' hands.
6. Switch to `Monkey_lod1.glb` with the same mixers (matched by name) and check there is no pop at the LOD boundary.
7. Profile a scene with N monkeys on target hardware; decide on the lite textures / KTX2.
8. Map the game's existing monkey behaviours onto the clip table in §4 and remove any assumptions about the old model's bones.
