# Start view and lagoon sunset: handoff to the game repository

**Status:** measured in the built game (a copy in the scratchpad, not the repository). Nothing is changed in the game. The change is two constants, so it costs no frame time.

Preview (private, owner only): https://claude.ai/artifact/Ep49EfqyRZRoAyq743CK88

**Rule:** FPS-neutral or better. Measured below: the proposed opening draws fewer calls and triangles than the current one.

## 1. What you asked for, and what the geometry allows

- **Start on the lagoon and the castaway, with the sunrise on the horizon behind the island.** The game's sun is fixed by the time of day: it rises on +X (east) and sets on −X (west). So the camera has to be west of the island, looking east, with the island between it and the sun. The castaway's camp is on the east edge of the west coast (about (4.5, 107)), and the Pearl Cove lagoon is east of it. From the west sea, the island's silhouette sits about one degree above the horizon toward the dawn sun, so the sun rises just above the trees.
- **Sunset viewable from the lagoon.** From the south-east corner of the lagoon, around (60–72, 140–146), the horizon toward the setting sun is open sea (about −2°). The sunset is visible from there, but the sun is then not behind the island.
- **The castaway and the sunrise together are a trade-off.** The sunrise-behind-island view is about 260 m from the camp, and the castaway is only a few pixels tall at that distance. A closer view (about 100 to 120 m) shows the castaway's beach, but there the sun rises over the lagoon, not behind the island. Pick one, or accept a second move later (see section 4).

## 2. Proposed change

`src/main.js`, line 182 (the opening):

```js
// now
const VIEW = { pos: [-230, 60, -20], tgt: [0, 30, -10] };
// proposed: the same spot in the west sea, looking at the lagoon; the island sits between the camera and the rising sun
const VIEW = { pos: [-232, 60, -20], tgt: [30, 0, 112] };
```

The camera keeps its height (60 m) and its position almost exactly. Only the aim changes.

`src/main.js`, the `presets` list (about line 124 onward), a new entry for the sunset:

```js
{ name: 'Lagoon sunset', pos: [66, 2.5, 146], tgt: [-134, 1.5, 202], dur: 4 }
```

This preset shows the sun setting over the sea from the lagoon. It only shows the sun near the horizon, so it is best used around dusk (time of day about 17.5 to 19). The game does not change the time when the camera goes there; decide whether the preset should set the time too (not included here).

## 3. Measured cost (headless Chromium, software GL; counts are exact for each frame)

| View | Draw calls | Triangles | Against now |
|---|---|---|---|
| **Now**: opening at first light | 3,165 | 14.2 M | (baseline) |
| **Proposed opening** | **2,679** | **11.8 M** | fewer calls, fewer triangles |
| Aimed at the castaway (same spot) | 3,118 | 14.3 M | about the same |
| Closer, aimed at the castaway (120 m) | 2,687 | 11.8 M | fewer |
| Lagoon sunset (preset) | 891 | 8.3 M | much fewer |

The proposed opening is cheaper on both counts, so it meets the FPS rule. The frame time itself needs the game's own `?perf=1` run on your machine: software GL cannot measure it.

## 4. Decision for you: castaway in the opening frame

- **Option A (proposed):** the sunrise behind the island, the lagoon in view, the castaway too small to see. He appears as the camera moves on or when you look for him.
- **Option B:** a closer view that shows the castaway's beach. The sun then sits over the lagoon, not behind the island.
- **Option C:** the proposed opening, then a short camera move (a few seconds) that flies in toward the castaway as the sun clears the island. Cheap to run, and it gets both, but it is a sequence change, not a single view.

Recommendation: A now, C later if you want him in the first frame.

## 5. Game-side checks

- Set the opening, then look at the first minute: the sun must come up behind the trees, not over the sea.
- Check the lagoon sunset preset at about time 18.
- Run `?perf=1` with the opening view before and after.
- The constants do not draw random numbers, so placement and object ids do not change (the CLAUDE.md rule is not at risk).

## 6. Files in the workshop

- `docs/start_view/`: the four real renders (now, proposed, the lagoon sunset, the closer alternative).
- `tools/start_view/search_views.mjs`: finds the viewpoints from the game's terrain (horizon angles toward the sun).
- `tools/start_view/render_views.mjs`: renders candidate poses and counts draw calls and triangles. Both take `GAME_URL` (a running copy of the game, for example `node serve.mjs 5190` in a built copy) and write to `build/start_view/` by default.
