# Castaway technical specification (measured from the packaged GLBs)

All numbers below were measured on the files in `assets/castaway/` with `tools/castaway/measure_glb.py` (reports in `assets/castaway/validation/*_measure.json`).

## Height

| Measurement (bind pose, LOD0) | Value |
|---|---|
| Soles (lowest skin vertex) | y = 0.000 m |
| Crown of the skull skin (highest skin vertex) | y = **2.003 m** |
| Top of the hair cards | y = 2.106 m (hair volume, not anatomy) |

The skinned body is **2.003 m**, i.e. 2.00 m to the millimetre it is displayed in, but **3 mm above an exact 2.000 m**. It was not rescaled afterwards because
every clip, grip table and IK solution is expressed in these units. Treat 2.00 m as the design height and ±3 mm as the tolerance.

## Skeleton (110 joints, one skin, single root)

`root` (feet level, the only node animated for anchored/vertical clips) → `pelvis` → `spine1..4`, `neck1`, `neck2`, `head`; clavicle/upper arm/forearm (+2 twist joints per forearm), 30 finger joints,
legs (thigh, shin, foot per side), 12 toe joints, 19 face joints (jaw, lips, 2 eyes, lids, brows, cheeks), 12 beard/hair chains, 6 cloth joints, `prop_staff` and `prop_aux` (props follow these, children of `root`)
and `attach_hand_L/R` (coconut/food). Groups and the upper-body mask are in `castaway_bones.json`. Conventions: 1 unit = 1 m, +Y up, faces +Z, +X is his left.
Animation tracks use `rest ⊗ basis` rotations in the node-local frames (no axis swizzle), 30 fps, linear.

## Meshes, materials and draw calls

| Material | Meshes (primitives) | Triangles (LOD0) |
|---|---|---|
| `CastawaySkinHead` | 1 | 15,709 |
| `CastawaySkinBody` | 1 | 30,264 |
| `CastawayEye` | 2 (one per eye) | 2,560 |
| `CastawayMouth` | 6 (gums, teeth, tongue) | 1,736 |
| `CastawayHair` (hair, beard, moustache, brows cards; alpha-masked, double-sided) | 1 | 18,534 |
| `CastawayMaro` | 6 (band, strap, front/back, two tails) | 2,840 |
| **Total** | **16 skinned meshes = 16 draw calls** | **71,643** |

* LOD0 is **16 draw calls** (about 32 with a shadow pass), not fewer: the eyes, mouth parts and maro pieces are separate meshes. They share 6 materials and one skeleton, so
  merging them by material in the exporter (not done) would give **6 draw calls** with no visual change. Do that in the game's loader (`BufferGeometryUtils.mergeGeometries` per material)
  if draw calls matter, or ask for a merged export.
* LOD1: 41,417 tris, 16 draw calls. Lite: 24,230 tris, 16 draw calls.
* Hair cards use `alphaMode: MASK`; set `material.alphaToCoverage = true` with MSAA. There is no sorting problem (no blending).
* Materials are glTF PBR metal/rough (albedo, normal, packed ORM); no custom shaders and no extensions beyond core glTF.

## Textures

| Image | LOD0 | LOD1 | Lite | Format in GLB |
|---|---|---|---|---|
| Head albedo / normal | 2048² / 2048² | 1024² | 512² | JPEG |
| Body albedo / normal | 2048² / 2048² | 1024² | 512² | JPEG |
| Head and body ORM | 1024² each | 1024² | 1024² | PNG |
| Hair atlas | 1024² RGBA | same | same | PNG |
| Maro | 1024² RGBA | same | same | PNG |
| Eye 512×256, mouth 256² | | | | PNG |

Decoded GPU memory for LOD0 is roughly **110 MB** with mipmaps (four 2048² RGBA textures ≈ 89 MB, the rest ≈ 20 MB). Convert to KTX2/Basis in the game's build step to cut that
to about a quarter (not done here to keep the GLBs viewable everywhere). Use LOD1 beyond about 6 m and Lite beyond about 15 m (suggested thresholds, untested in the game).

## File sizes

`Castaway.glb` 10.35 MB (model + 6 core clips), `Castaway_lod1.glb`, `Castaway_lite.glb`, `Staff.glb` 1.7 MB, animation packs 0.4 to 4.6 MB each (`MANIFEST.json` has exact bytes and SHA hashes).

## Animation loading requirements (Three.js r186)

1. Load `Castaway.glb` once. It contains the six always-needed clips (`idle_relaxed`, `idle_breathe`, `idle_look_around`, `walk`, `walk_brisk`, `run`).
2. Load a pack **only when its behaviours are needed**; packs are skeleton-only GLBs (no mesh, no textures) and bind by **node name**, so the model clone must keep the original node names
   (`SkeletonUtils.clone` does; do not rename or re-parent bones). `castaway_clips.json → clips[name].pack` names the pack.
3. One `AnimationMixer` per character; clone the model with `SkeletonUtils.clone` (geometry and textures are shared between clones).
4. Cross-fade with the per-clip `blend` values; honour `root_motion.type` (in-place loops scale `timeScale` by speed / `reference_speed_m_s`; anchored clips need the named anchor).
5. Upper-body layers are `<clip>__upper` actions with the overlay weight `w/(1-w)` for a layer weight `w`.
6. Face controls are applied after `mixer.update()` from `castaway_face.json`; staff and paddle attach to `prop_staff` / `prop_aux`.
7. Memory: 142 clips + 31 layers total 13.7 MB on disk across 10 packs; the walk loop is a few hundred KB. Dispose unused actions with `mixer.uncacheClip`.

## Validation

Structural validator (`tools/blender/validate_glb.py`): Castaway, LOD1, Lite and Staff pass. Animation packs have no meshes by design, so the mesh check reports "no meshes in file" for them (expected).
Khronos glTF Validator: **0 errors on all 14 GLBs** (`validation/*_khronos.json`). Warnings: 0 on the animation packs, 3 on `Staff.glb`, 17 on each character model (`MESH_PRIMITIVE_GENERATED_TANGENT_SPACE`: normal-mapped meshes carry no tangents, three.js derives them; `NODE_SKINNED_MESH_NON_ROOT`: skinned meshes are not scene roots, which three.js handles correctly).
