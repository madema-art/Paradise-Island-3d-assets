# Points of interest: handoff to the game repository

**Status:** workshop prototype. Two of the ten named places are redesigned here. Nothing is wired into the game.

Preview (private, owner only): https://claude.ai/artifact/3hAsQBpFrtb6Lfd5fpQHYk

**Rule:** FPS-neutral or better. No more draw calls, lights or shadow casters than the game uses, and no more triangles unless the number is written down.

## 1. What is redesigned

| Place (game name) | Game builder | Redesign in the workshop | Draws | Lights | Shadow casters |
|---|---|---|---|---|---|
| The Sunken Temple (`TEMPLE`, `buildTemple`) | `src/props.js` | `viewer/poi/poi_kit.js` `buildTemple` | 21 → **2** | 1 → 1 | 15 → **1** |
| The Glimmer Ring (`FAIRY`, `buildFairy`) | `src/props.js` | `viewer/poi/poi_kit.js` `buildGlimmerRing` | 71 → **2** | 2 → **1** | 7 → **1** |

Draw, light and shadow-caster counts are exact, counted from the game's source and from the kit's output. The triangle figures are different: the before column is an estimate from the game's primitive parameters (no in-game measurement yet), and the after column is measured.

| | Game (estimate) | Redesign (measured) |
|---|---|---|
| Temple triangles | about 2,900 | 2,050 (stone and eyes) |
| Glimmer Ring triangles | about 4,400 | 3,156 (matte and glow) |

So both POIs are the same size or smaller on triangles, and far cheaper on draw calls. The perf document (`docs/PERFORMANCE.md`) measures renderer CPU at about 9 µs per draw, so about 88 fewer draws per frame when both places are in view is roughly 0.8 ms of CPU time saved (an estimate from that figure; check it with `?perf=1`).

### What changed in the look

- **Temple:** the same four tiers, stairs and shrine, with the same walkable heights. Stone colour is varied per block, moss sits on the upper parts of the tiers, and hanging vines are added on the tier faces. The idol is one stone mesh (with a darker mouth) and its eyes are the only emissive mesh, so they pulse without touching the stone. The torches and their bowls are merged into the stone mesh.
- **Glimmer Ring:** the same ring of mushrooms and seven standing stones. Each cap is a dome with a darker rim, so the ring reads as bioluminescent at night and by day. Stems and stones are one matte mesh; caps are one `MeshBasicMaterial` mesh, so they glow from their own colour and need no light. One light stays at the centre; the second light is removed.

## 2. How the fewer draws are achieved (and the rules that make it safe)

- **One merged mesh per material kind, per place.** Every part is a primitive with per-vertex colour, merged with `mergeGeometries`. The game's `addMesh(mb.build(), stoneMat)` pattern stays.
- **Emissive changes through one shared material.** The game's per-frame `emissiveIntensity` loops (`updaters.push`) become one assignment per frame on one material. The glimmer caps use `MeshBasicMaterial`, so their brightness is `material.color` (one value per frame).
- **The fire and the sparkles are not touched.** The torch flames (`fx.flame`) and the cap sparkles (`fx.sparkle`) are particle systems; keep them where they are.
- **Walkable surfaces and colliders are the same formulas.** `templeSurfaceY` in `poi_kit.js` is the game's `addSurface` function, copied. Keep the game's own `addSurface` and `addCollider` calls. The visual geometry was built to those heights: tier tops at `(i + 1) × 1.75`, tread tops at `(i + 1) × 0.44`, the shrine at `TEMPLE_TOP + 0.4`.
- **Tagging for the inspector stays.** The game tags the stone mesh `'temple'` and the ring stones `'fairyring'` (`tagObject`). Tag the merged meshes the same way, and keep the catalogue entries in `src/catalog.js`.

## 3. Game-side integration (for the local Claude Code session)

Keep the game's rules from CLAUDE.md. The world's random stream is shared, so the new builders must not change what else draws:

1. **Placement and random numbers.** `buildTemple` draws the pillar, standing-stone, broken-column and torch choices from the shared stream (`rr`, `rnd`, `pick`). `buildGlimmerRing` draws the mushroom sizes and cap colours the same way. The kit uses its own `mulberry32` generators, so in the game either:
   - port the kit with its own seeded generator and `burn(n)` the draws the old builder spent (count them first, the way the rules describe), or
   - accept a different arrangement of pillars and mushrooms and check that no other object moved.
   The object ids of the temple and the ring must not change.
2. **Port the geometry.** Use `buildTemple` and `buildGlimmerRing` as the reference. Replace the `MB`, `box`, `jitterGeo` and `mat4` calls with the game's equivalents, or keep `THREE` primitives as above. Place every part on `getHeight(x, z)` for the ground, which the kit assumes is flat at 0.
3. **Lights.** The temple keeps its one light (`il`, 50 intensity, range 22). The ring keeps `l1` (45, range 20) and drops `l2`. Confirm the glimmer's look at night with the second light removed; if it is too dim, raise the cap emissive, not the light count.
4. **Shadows.** Only the stone mesh casts a shadow. The eyes, the caps and the stems do not. The game's idol and torch poles cast shadows today; the redesign drops that, and the perf numbers show the saving.
5. **Check it in the game.** Run `?perf=1`, with the temple and the ring in view, before and after. Also look at both places at night and at eye level.

## 4. Not done in this pass

These named places still use their game builders: **Veil Falls** (mostly water: `src/water.js` and the falls ledge), **the hot spring**, **Pearl Cove**, **the west cascade**, **the reef lagoon**, **the river meadow**, **the jungle clearing**, and **the volcano foothills**. Pick the next one by visual weight (the spring and the cove are visible from the main camera views) and apply the same rule: count the draws before, merge, and keep the surfaces.

## 5. Verified here, and not verified

Verified in the workshop:
- Both builders run with no page errors, in headless Chromium (`viewer/poi/`).
- Draw, light and shadow-caster counts, and triangle counts for the redesign (`renderer.info` and the geometry).
- The temple's walkable formula matches its tiers, treads and shrine by construction; the screenshots show the stair and shrine where the formula puts them.

Not verified:
- Frame time in the game. Software GL cannot measure it, and the game's own harness (`?perf=1`) is the test.
- The look under the game's lighting, fog and night cycle.
- Whether the game's random placement moves. The port must check this (section 3).
- The before triangle counts, which are estimates.
