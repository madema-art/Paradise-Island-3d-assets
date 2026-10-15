# Start view: turn the sun, open on the lagoon, sunset from the lagoon

**Status:** measured in a built copy of the game (kept in the scratchpad; the repository's game is untouched). The change is one constant in `src/core.js`, two view numbers in `src/main.js`, and no new geometry, lights or draws.

Preview (private, owner only): https://claude.ai/artifact/Ep49EfqyRZRoAyq743CK88

**Rule:** FPS-neutral or better. Measured below: the new opening draws fewer calls and triangles than today's opening.

## 1. What you asked for

The game should open on the view from your screenshot: the lagoon in the foreground, the island, and the volcano behind it. The sun should come up on the horizon near the centre of that frame, not hidden behind the volcano. The compass names are only a means to that: the sun's arc is turned until the sunrise lands there.

Turning the island itself would move every placed object, and the placement and the object ids depend on their coordinates (the seeded placement, saved notes and the inspector all rely on them). So the change turns the sun's daily arc instead: the sun and the moon rise and set on a different compass bearing, and the island stays where it is. From the player's side the result is the same: the island is oriented differently against the sun.

## 2. The change

### 2.1 `src/core.js`: turn the sun's and the moon's daily arc

The patch is `docs/start_view/sun_turn.patch` (line endings kept). In short, in `applyTimeOfDay`:

```js
// The compass turn of the sun's daily arc, in radians about the vertical axis.
// 0 rises in the east and sets in the west (the old orientation). -7*PI/12 (-105 degrees) puts sunrise on the horizon
// just left of the centre of the opening view, clear of the volcano.
export const SUN_TURN = -(7 * Math.PI) / 12;
const _tc = Math.cos(SUN_TURN), _ts = Math.sin(SUN_TURN);
const turned = (x, y, z) => new THREE.Vector3(x * _tc - z * _ts, y, x * _ts + z * _tc).normalize();

// in applyTimeOfDay:
env.sunDir.copy(turned(Math.cos(a), Math.sin(a), 0.28));
// ...
env.moonDir.copy(turned(Math.cos(a + e), Math.sin(a + e), 0.28));
```

With this angle the sunrise is the direction `(0.01, 0, -1)` and the sunset `(-0.01, 0, 1)`, so both stay on the north-south line. The sun and the moon turn together. The sun, the moon, the sky, the shadows and the water lighting all read `env.sunDir` or `env.moonDir`, so they all turn together.

### 2.2 `src/main.js`: the opening view (line 182)

```js
// now
const VIEW = { pos: [-230, 60, -20], tgt: [0, 30, -10] };
// proposed: the view from your screenshot, from the south sea, looking north at the lagoon and the island.
// Call setFov(50) after flyTo (imported from camera.js): the lens eases to 50, which keeps the same framing with less in view.
const VIEW = { pos: [0, 70, 270], tgt: [5, 20, 40] };
flyTo(VIEW.pos, VIEW.tgt, 0.05); setFov(50);
```

### 2.3 `src/main.js`: a lagoon sunset preset (in the `presets` list, about line 124)

```js
{ name: 'Lagoon sunset', pos: [30, 3, 120], tgt: [12, 1.5, 230], dur: 4 }   // unchanged; open sea to the south at this angle
```

It shows the sun setting over the open sea to the south. The sun is only near the horizon around the dusk hours (time of day 17.5 to 19), so the preset is most useful then. The game does not change the time when the camera goes there.

## 3. Measured (headless Chromium, software GL; each pose on a fresh, settled page)

| View | Draw calls | Triangles | Against now |
|---|---|---|---|
| **Now**: the current opening | 3,052 | 13.6 M | (baseline) |
| **Proposed opening** (0, 70, 270), fov 50 | **2,995** | **13.3 M** | fewer calls and triangles |
| Same position, fov 55 | 3,091 | 13.8 M | more (so the 50 lens is what keeps it at or below now) |
| Lagoon sunset preset (30, 3, 120) | 1,536 | 11.1 M | much fewer |

The proposed opening is cheaper than the current one on both counts. Earlier figures in this file were taken on pages that had already rendered other poses; the vegetation LOD keeps some state between poses, so those numbers were not comparable. The numbers above are from fresh pages. Frame time needs your `?perf=1` run on your machine: software GL cannot measure it.

## 4. Checks in the game

- Open the game at dawn: the sun should come up on the horizon near the centre of the view, to the left of the volcano, not behind it. The position of the sunrise is the thing to tune: `SUN_TURN` moves it left and right (a smaller magnitude moves it right, a larger one left).
- Check the sunset from the lagoon preset around time 18.
- The shadows fall along the sun's new arc. That is a lighting result, not a cost.
- The prevailing wind is still `north-west`. The wind is not turned; say if you want it turned to match.
- Nothing in placement changes. The constant draws no random numbers, and object ids are unchanged.
- Run `?perf=1` at the opening, before and after.

## 5. Files in the workshop

- `docs/start_view/sun_turn.patch`: the change to `src/core.js`, against the game's current file.
- `docs/start_view/reference_screenshot.png`: your screenshot, for comparison.
- `docs/start_view/now_dawn_start.png`: the current opening, for comparison.
- `docs/start_view/opening_sun_centre.png`: the proposed opening, rendered from the built game with the sun turned to -105 degrees and fov 50.
- `docs/start_view/lagoon_sunset_proposed.png`: the proposed lagoon sunset.
- `tools/start_view/render_fresh.mjs`: renders each pose on a fresh page and counts draw calls and triangles. `tools/start_view/search_south.mjs` searches for open horizons. Both take `GAME_URL` for a running build.
