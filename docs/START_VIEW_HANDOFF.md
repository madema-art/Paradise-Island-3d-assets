# Start view: turn the sun, open on the lagoon, sunset from the lagoon

**Status:** measured in a built copy of the game (kept in the scratchpad; the repository's game is untouched). The change is one constant in `src/core.js`, two view numbers in `src/main.js`, and no new geometry, lights or draws.

Preview (private, owner only): https://claude.ai/artifact/Ep49EfqyRZRoAyq743CK88

**Rule:** FPS-neutral or better. Measured below: the new opening draws fewer calls and triangles than today's opening.

## 1. What you asked for

The game should open on the view from your screenshot, the lagoon in the foreground with the island and the volcano behind it, with the sun rising behind the island. The sun currently rises in the east, which puts it beside that view, not behind it. So the island's orientation on the compass changes: the sun rises in the north instead.

Turning the island itself would move every placed object, and the placement and the object ids depend on their coordinates (the seeded placement, saved notes and the inspector all rely on them). So the change turns the sun's daily arc instead: the sun and the moon rise and set on a different compass bearing, and the island stays where it is. From the player's side the result is the same: the island is oriented differently against the sun.

## 2. The change

### 2.1 `src/core.js`: turn the sun's and the moon's daily arc

The patch is `docs/start_view/sun_turn.patch` (line endings kept). In short, in `applyTimeOfDay`:

```js
// The compass turn of the sun's daily arc, in radians about the vertical axis.
// 0 rises in the east and sets in the west (the old orientation); -PI/2 rises in the north and sets in the south.
export const SUN_TURN = -Math.PI / 2;
const _tc = Math.cos(SUN_TURN), _ts = Math.sin(SUN_TURN);
const turned = (x, y, z) => new THREE.Vector3(x * _tc - z * _ts, y, x * _ts + z * _tc).normalize();

// in applyTimeOfDay:
env.sunDir.copy(turned(Math.cos(a), Math.sin(a), 0.28));
// ...
env.moonDir.copy(turned(Math.cos(a + e), Math.sin(a + e), 0.28));
```

Sunrise moves to the north (`(0.28, 0, -1)`) and sunset to the south (`(0.28, 0, 1)`). The sun, the moon, the sky, the shadows and the water lighting all read `env.sunDir` or `env.moonDir`, so they all turn together.

### 2.2 `src/main.js`: the opening view (line 182)

```js
// now
const VIEW = { pos: [-230, 60, -20], tgt: [0, 30, -10] };
// proposed: from the south sea, looking north at the lagoon, the island and the volcano (your screenshot)
const VIEW = { pos: [0, 60, 254], tgt: [5, 20, 40] };
```

### 2.3 `src/main.js`: a lagoon sunset preset (in the `presets` list, about line 124)

```js
{ name: 'Lagoon sunset', pos: [30, 3, 120], tgt: [12, 1.5, 230], dur: 4 }
```

It shows the sun setting over the open sea to the south. The sun is only near the horizon around the dusk hours (time of day 17.5 to 19), so the preset is most useful then. The game does not change the time when the camera goes there.

## 3. Measured (headless Chromium, software GL; counts are exact for each frame)

| View | Draw calls | Triangles | Against now |
|---|---|---|---|
| **Now**: the current opening | 3,165 | 14.2 M | (baseline) |
| **Proposed opening** (0, 60, 254) | **2,842** | **12.0 M** | fewer calls and triangles |
| Alternative, closer (12, 60, 242) | 3,177 | 14.0 M | about the same |
| Alternative, (0, 35, 254) | 3,133 | 11.6 M | fewer triangles, more calls |
| Lagoon sunset preset (30, 3, 120) | 1,731 | 10.4 M | much fewer |

The proposed opening is cheaper on both counts. Frame time needs your `?perf=1` run on your machine: software GL cannot measure it.

## 4. Checks in the game

- Open the game at dawn: the sun should come up behind the volcano and the island, not over the sea beside it.
- Check the sunset from the lagoon preset around time 18.
- The shadows now fall along a north-south axis (the sun's new arc). That is intended, and it is a lighting result, not a cost.
- The prevailing wind is still `north-west`. The wind is not turned; say if you want it turned to match.
- Nothing in placement changes. The constant draws no random numbers, and object ids are unchanged.
- Run `?perf=1` at the opening, before and after.

## 5. Files in the workshop

- `docs/start_view/sun_turn.patch`: the change to `src/core.js`, against the game's current file.
- `docs/start_view/reference_screenshot.png`: your screenshot, for comparison.
- `docs/start_view/now_dawn_start.png`: the current opening, for comparison.
- `docs/start_view/south_dawn_proposed.png`: the proposed opening, rendered from the built game with the sun turned.
- `docs/start_view/lagoon_sunset_proposed.png`: the proposed lagoon sunset.
- `tools/start_view/search_south.mjs` and `tools/start_view/render_views.mjs`: search for open horizons and render candidate poses, counting draw calls and triangles. Both take `GAME_URL` for a running build.
