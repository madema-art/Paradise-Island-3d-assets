# Lagoon coral: handoff to the game repository

**Status:** workshop prototype. The lagoon's coral reef is redesigned here; the water and the sand are not touched. Nothing is wired into the game.

Preview (private, owner only): https://claude.ai/artifact/NQtVbK86ozevgzeBDmD2sx

**Rule:** FPS-neutral or better. No more draw calls, lights or shadow casters than the game uses, and fewer triangles.

## 1. Why the lagoon costs what it does

The coral is built in two places in the game: the reef (`src/flora.js`, `coralGeo` in the "underwater life" section, 900 heads) and the south-seas garden (`src/flora2.js`, `buildSouthSeas`, 520 heads: tables, branching, cauliflower, massive, plate, plus anemones, starfish and urchins).

- Each coral **kind** is one `InstancedMesh`, so draw calls are already low (3 for the reef, 5 for the garden).
- The cost is **triangles**. The perf document (`docs/PERFORMANCE.md`) says instanced meshes are culled per mesh, not per instance, so every head of a kind is drawn whenever any head of that kind is on screen.
- From the game's parameters: a reef head averages about **140 triangles** (about **126,000** for 900 heads), and a south-seas head about **322** (about **168,000** for 520 heads). The cauliflower head alone is twelve icospheres (960 triangles).

## 2. What is redesigned

| Kind | Game (triangles per head) | Redesign | Note |
|---|---|---|---|
| Branching | 220 | 84 | three thick branches and one twig each; smooth shading |
| Massive / brain | 180 | 80 | detail-1 sphere with noise ridges |
| Plate / fan | 20 | 16 | two crossed fans, ruffled edges |
| Table | 88 | 72 | a stem and a disc with a scalloped rim |
| Cauliflower | 960 | 80 | four lumpy detail-0 spheres |

On the same placement (the game's south-seas mix, 520 heads), the viewer measures **168,248** coral triangles for the game's shapes and **37,540** for the redesign: about **22%**. The draw calls stay at five. Shape and colour: smooth normals, ridges and scallops on the same triangle budget, and the same vertex-colour gradient (darker at the base, lighter at the tips). The instance colours (the game's `coralCols`) still apply.

## 3. Game-side integration (for the local Claude Code session)

Keep the game's rules from CLAUDE.md: the world's random stream is shared, so the new geometry must not change what else draws.

1. **Random numbers.** `coralGeo`, `coralTable` and `coralCauli` draw from the shared stream (`rnd`, `rr`) for their shape jitter, and `buildSouthSeas` draws the placements. The redesign uses its own `mulberry32` generator (`newCoral`, seed-based). Either port the geometry with its own generator and `burn(n)` the draws the old builders spent (count them first), or accept a different arrangement of coral shapes and check that no other object moved. Object ids of the coral heads must not change.
2. **Port the geometry.** Use `newCoral` as the reference. Replace `THREE.` calls with the game's `MB` pattern if you prefer. Keep `instanced(geo, cMat, list, { inspect: 'coral', ... })` and the `coralSpots` list (the fish schools steer around it).
3. **Material.** `cMat` is `flatShading: true` in the game. The redesign relies on smooth normals, so set `flatShading: false` for the coral material. The anemones, starfish and urchins share `cMat`; check them after the change (they may want to stay flat, in which case give the coral its own material).
4. **Instance culling (the bigger win, not built here).** The coral is one `InstancedMesh` per kind, so all 900 heads are drawn whenever any is in view. Splitting each kind into a few area chunks (the perf document's "instanced chunking") would let the off-screen chunks go, so the lagoon costs what is on screen. This is a separate change and needs its own measurement with `?perf=1`.
5. **Check it in the game.** Run `?perf=1` with the reef in view, before and after, on the scenes listed in `docs/PERFORMANCE.md` (the lagoon scene is the demanding one: "schools over the reef"). Look at the reef in daylight and at dusk.

## 4. Not done in this pass

- **The water.** `src/water.js` and the lagoon's colour. The lagoon colour is what makes it read as a lagoon; it is the next thing to look at.
- **The sand floor** (`src/terrain.js`, the shore colouring).
- **Anemones, starfish and urchins** (the same material, unchanged here).
- **The chunking** in section 3, step 4.

## 5. Verified here, and not verified

Verified in the workshop:
- The game's coral is rebuilt from its primitives (`legacyGeometry`), and its triangle counts follow the game's parameters: 220, 180, 20, 88 and 960 per head.
- The redesign's counts, its draw calls (five), and the ratio on the same placement (22%).
- The pages run with no errors in headless Chromium, and the close-ups show the shapes as described.

Not verified:
- Frame time in the game (software GL cannot measure it; the game's `?perf=1` harness is the test).
- The look under the game's lighting, the water and the night cycle.
- The game's own coral: the workshop rebuilds the shapes from the primitives and leaves out the shape jitter, so the numbers are exact for the counts but the shapes are a faithful reconstruction, not a copy.
