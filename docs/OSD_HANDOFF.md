# On-screen display and controller menu: handoff to the game repository

**Status:** workshop prototype. It tests the controls, the cycling rule and the layout with stand-in creatures. Nothing is wired into the game.

Preview (private, owner only): https://claude.ai/artifact/Af3zD75NLkM7tabUBBgs9N

**Rule:** FPS-neutral or better. Fewer boxes, no backdrop blur, and no per-frame DOM work.

## 1. What is wrong now (from the game's markup and code)

- Up to **seven translucent boxes** on screen at once: the title card, the five-tab side panel (View, Field guide, Inspect, Notebook, Secrets), the nine-button preset dock, the help card, the follow card (with its relative bar), the walk hint, and the toast. Plus floating labels and the weather line.
- Every `.glass` box uses `backdrop-filter: blur(14px) saturate(1.4)` (`index.html` line 22). The browser blurs whatever is behind each box on every frame, while the 3D scene is changing. That is a real GPU cost, and the box count multiplies it.
- The controller map (`src/camera.js`, around lines 412 to 418) gives the d-pad left and right the camera presets, the bumpers the nearby-creature cycle, Start a show or hide of the whole interface, and Back the walk or fly switch. The menu has no controller path at all: the side panel is mouse and keyboard only.
- The creature cycle (`cycleTarget` and `nearby`, lines 233 to 265) only looks at creatures within 260 m, and it does not know about species.
- The weather line is rewritten with `innerHTML` every 0.5 s, and the follow card's description with `textContent` every 0.8 s, even when nothing has changed.

## 2. What the prototype does

| | Game now | Prototype |
|---|---|---|
| Boxes in play | up to 7 | 2 (focus card, hint bar) |
| Boxes in menu | the same 7, plus the side panel | 3 (focus card, hint bar, one menu box) |
| Backdrop blur | on every `.glass` box | none (solid background) |
| DOM writes per frame | timers on the weather line and follow card | only when the text changes |
| Menu on the pad | none | full: d-pad, A, B, LB and RB, Start |

Measured in the workshop (headless, with a fake controller): mode switching, creature cycling in both rules, the menu sections, the settings, and no errors. The blur count is read from the browser's computed style (0 for all three boxes). The frame rate is not measured here; `?perf=1` in the game is the test.

## 3. Controller map

**Play (menu closed)**

| Button | Action |
|---|---|
| Left stick | move (walk mode) or nothing (fly mode, as now) |
| Right stick | look or orbit (as now) |
| D-pad left / right | **previous / next creature** (rule in section 4) |
| D-pad up / down | lens: zoom in / out (as now) |
| LB / RB | **previous / next camera view** (Wide, Close, Top; these were the d-pad's job) |
| Y | follow the nearest creature (as the lock-on does now) |
| B (hold) | let go of the creature (as now) |
| A (hold) | run (as now); X (hold) precise (as now) |
| **Start** | **open the menu** (Start used to hide the interface; Hide interface is now a menu item) |
| Back | walk or fly (as now) |

**Menu (opened with Start)**

| Button | Action |
|---|---|
| D-pad up / down | move between items (skips the section headings) |
| D-pad left / right | change the highlighted slider or choice |
| LB / RB | previous / next section |
| A | activate: run a view, flip a toggle, or follow a species (and close the menu) |
| B | close the menu |
| Start | close the menu |

The keyboard matches: arrows move and adjust, Enter is A, Backspace is B, Q and E are LB and RB, M or Escape open and close the menu. The keyboard's own play controls are unchanged (the arrows still turn the view in play mode, as they do now; the prototype uses them for creature cycling, so the game port should decide which one the arrows keep).

## 4. The creature cycle

Left and right, in play, from the controller or the keyboard:

1. **Focused on a creature whose species has more than one individual:** left and right go to the previous and next individual of that species, in a fixed order, wrapping round. Example from the test: crab 3, right, crab 1, right, crab 2.
2. **Otherwise** (not focused, or the species has one individual): left and right go through the views of **all** creatures, in one fixed order: category, then species name, then individual number. From nothing, the first press starts at the creature nearest the camera. Example: the flamingo (one individual), right, the Pacific boa.

The logic is in `viewer/osd/cycle.js` (pure functions, no three.js): `nextInSpecies`, `nextView`, `cycleFocus`. Port it as a new module (for example `src/creature_cycle.js`). It must **not** be range-limited the way `nearby` is: the global cycle covers all creatures on show (`c.group.visible`). Creatures already carry the fields it needs: `c.name` is the species and `c.cat` the category; the individual number is not stored yet, so either add one at spawn (in order) or use the order of `creatures`.

## 5. The menu tree

| Section | Items |
|---|---|
| **View** | Wide view, Close view, Top view (go to the view), Slow auto-orbit (toggle), Field of view (slider) |
| **World** | Quality (Low, Medium, High), Shadows (toggle), Bloom glow (toggle) |
| **Sound** | Music (toggle), Music volume, Effects volume, and the music library as a sub-list (Next, Previous, Restore removed) |
| **Guide** | the species by category, with the count of individuals; A follows the nearest individual and closes the menu |
| **Journal** | Secrets found (count), Notebook (the notes list), Inspect (the current inspected object) |

The old side panel's **Hide interface** is a View item. Everything the old panel had is still there; only the layout and the boxes change.

## 6. Game-side changes (for the local Claude Code session)

1. **`index.html`**: remove `backdrop-filter` (and `-webkit-backdrop-filter`) from `.glass` (line 22) and from `.sv-card` (line 242); keep the look with the solid `--glass` colour and a 1 px border. Replace the seven boxes with the three in the prototype. Keep the ids the code uses (`#dock`, `#side`, `#follow`, `#relbar`, `#unfollow`, `#walkhint`, `#whmsg`, `#toast`, `#help`) or update the code that uses them in the same change.
2. **`src/camera.js`**: rebuild the pad block (lines 410 to 418) to the map in section 3. Add a menu state (`menuOpen`): when it is open, the play actions are skipped and the menu reads the buttons. Survival mode does not run this function (its comment says so): the menu has to be reachable there too, or survival keeps its own button map.
3. **`src/camera.js`**: replace `cycleTarget` (lines 258 to 265) with the rule in section 4, and keep `lockOn` for Y.
4. **`src/ui.js`**: build the menu from one tree (section 5). Keep `initUI`'s tabs as the menu sections. The Guide, Inspect and Notebook panes keep their logic; only their containers change. Write the weather line and the follow card's description only when their text changes (today both are rewritten on a timer, every 0.5 s and every 0.8 s).
5. **`src/gamepad.js`**: no change needed. Its `pollPad` already gives the edges (`pressed`) for each button.
6. **Specimen viewer**: the Field Guide's specimen viewer and the inspection use their own WebGL context (CLAUDE.md). Keep them closed unless the Guide or Inspect section is open. That is an FPS saving too, and it should be measured with `?perf=1`.

## 7. What is not done, and what to check

- **The real content** of the Guide and Journal panes (the specimen view, the species facts, the notebook list) is not in the prototype: it shows names and counts only.
- **Accessibility**: the prototype gives the highlighted row a border and the focused tab a border. Check with the game's real colours, and with the controller only (no mouse) from a cold start.
- **Survival mode** has its own HUD (`src/survival/hud.js`); it is out of scope here.
- **FPS**: the blur removal and the box count are the expected wins. Measure with `?perf=1` before and after, with the menu closed and open. Expect the difference to be small on a fast GPU and larger on a slow one.
- **The random stream**: none of this draws random numbers, so placement and object ids do not move (CLAUDE.md's rule is not at risk).
