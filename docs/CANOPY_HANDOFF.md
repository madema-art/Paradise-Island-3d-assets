# Tree canopies: handoff to the game repository

**Status:** workshop prototype only. Nothing is wired into the game. The owner's report: the broadleaf crowns read as "a low-poly broccoli farm", and the banyan leaf cards do not look good either. Goal: better-looking canopies that cost no more frames than today.

Preview (private, owner only): https://claude.ai/artifact/5Fdk3N3E9WyaPnyX2JJhnu

## 1. What is in the workshop

| File | What |
|---|---|
| `viewer/canopy/canopy_kit.js` | `currentCanopy()` (a stand-in for `treeB`'s crown, flat-shaded like the game) and `newCanopy()` (leaf clumps). Pure geometry: one `BufferGeometry` per tree, vertex colours and `aWind`, as the game's `MB` builder does. |
| `viewer/canopy/canopy.js`, `index.html` | Side-by-side comparison, close and low cameras, and a forest test counting draw calls and triangles. |
| `tools/stage_canopy_viewer.py` | Stages the page for the private artifact (`build/artifact_canopy/`). |

## 2. What the game does now (read from the game's source, read-only)

- **Broadleaf crowns** (`src/flora.js`, `treeB`): seven icosphere lobes (detail 1, 80 faces each, `lumpy` 0.3), each scaled `(R, 0.55R, R)`, shaded by height only. About 560 triangles per crown.
- **Banyan** (`src/flora2.js`, `makeBanyan` and `ficusLeaves`): three lobes per limb plus a dense crown, each lobe covered in leaf cards: one small flat-coloured triangle pair per leaf, about `R × 50` leaves per lobe. Those cards are the "leaf cards that do not look good". Each card is flat, unlit in colour and a fixed shape, so from a distance they read as noise, and up close they read as cut paper.
- **Shared mesh builder** (`src/gfx.js`, `MB.build`): calls `computeVertexNormals()` on non-indexed geometry, which gives **one flat normal per triangle**. Every tree built with `MB` is therefore faceted. This is probably a large part of the "low poly" look, and it is cheap to fix (see section 4).

## 3. What the workshop prototype does

Measured in the comparison page (`canopy.js`, headless Chromium with software GL; triangle and draw-call counts are exact, frame times are not):

| | Current style | New clumps |
|---|---|---|
| Canopy triangles | 560 | 1,820 (3.25×) |
| Canopy vertices | 1,680 | 5,460 |
| Draw calls per tree (canopy + trunk) | 2 | 2 |
| Triangles per frame, 100 trees, shadow pass included | 95,108 | 254,988 |
| Draw calls per frame, 100 trees | 299 | 274 |

The draw-call figures differ only by view culling in the test, not by design: both variants are one canopy mesh per tree. The triangle cost is the real trade-off. 100 trees in view add about 160,000 triangles, including their shadows.

How the new canopy is built:
- **Clumps on a domed shell.** Thirty-four clumps spread over the crown disc, lower and higher, with gaps between them. Seventeen on the outer rim are detail-1 spheres; the inner ones are detail 0, which the eye barely sees.
- **Shading in colour, not in lights.** Each vertex is darkened by occlusion (lower and inner parts darker), mottled by low-frequency noise, and warmed towards lime where it faces the sun. Each clump has its own value. The lowest clumps form a dark skirt.
- **Smooth normals** (see section 4), so the clumps read as soft leaf masses instead of facets.
- **Fins dropped.** The first version had folded leaf blades on the rim. They read as spikes, so they were removed.

What the prototype does not yet do: it is not as detailed as a real leaf canopy, the close view is still stylised, and it has no alpha leaf cards. It is a first pass for the owner to judge, not a finished look.

## 4. What the local Claude Code session should do in the game

Do these in order. Keep the game's rules (CLAUDE.md): every new builder uses its own seeded generator and burns the draws the old one used, so placement and object ids do not move.

1. **Smooth normals in `MB.build` (`src/gfx.js`).** Average the face normals per welded position instead of `computeVertexNormals()` on non-indexed geometry. This changes the look of every `MB` object, so check it in the game: trees, shrubs, the castaway's props, the fish. It adds no triangles and no draw calls, and it draws no random numbers. Worth doing first, because it may fix much of the faceting without any new geometry.
2. **Replace the broadleaf crown** (`treeB`, `src/flora.js`) with `newCanopy` from `canopy_kit.js`: port the function into the game's `MB` style (`addGeo` / `tri`), keep `aWind` on every vertex, keep the trunk and the placement code unchanged, and draw the random numbers from a new `mulberry32` stream with a `burn()` for the old draws.
3. **Banyan leaf cards** (`ficusLeaves`, `src/flora2.js`). Try the clump approach for the banyan crowns first, instead of leaf cards. If the owner wants leaves on the banyan, use a few clustered leaf fans per clump rather than one card per leaf. Measure the triangles before keeping any card count.
4. **Shadows.** The canopy casts shadows in the game's shadow pass, which the perf document names as the largest single cost in the jungle view. Test with the canopy casting shadows and with a simpler proxy for the shadow pass (LOD1 below). Keep whichever the shadow budget tolerates.
5. **LOD for distant trees.** `newCanopy(seed, { lod: 1 })` gives 12 coarse clumps and no skirt, about 240 triangles (an eighth of LOD0). Pick the switch distance by the screen-space size of the crown, the way `src/vegetation_lod.js` does for shrubs, with hysteresis.
6. **Double-sided or not.** The prototype uses `DoubleSide`. The clumps are closed, so `FrontSide` is enough, but check the game's wind shader and the banyan's cards before changing it.

## 5. Acceptance checks (in the game, with the owner watching)

- The `?perf=1` benchmark (`src/dev/perf_bench.js`) before and after, on the same scenes listed in `docs/PERFORMANCE.md`: frames per second, draw calls and triangles. The median frame must not get worse by more than the noise (the document reports several frames per second of run-to-run variation).
- The broadleaf crowns look like foliage from the castaway's eye level and from the wide view. The owner signs off the look, not the numbers.
- The banyan crowns no longer read as noise up close or from afar.
- Placement is unchanged: the object ids and positions in a saved world match before and after.

## 6. What was verified here, and what was not

Verified in the workshop:
- The comparison builds and runs with no page errors (`viewer/canopy/`, headless Chromium).
- Triangle and vertex counts for both canopies, and draw calls per tree (both two, one canopy mesh).
- The screenshots: the new crown reads as clumps with depth, the current stand-in reads as the game's faceted blobs.

Not verified:
- Frame rate in the game. The software-GL frame times in the test are meaningless; only the counts are real.
- The look under the game's lighting, fog and tone mapping, and the game's wind shader.
- The banyan (no banyan variant exists in the workshop yet).
- The owner's judgement of the look. The current prototype is a first pass.
