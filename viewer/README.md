# Monkey asset viewer

Standalone Three.js viewer for the redesigned monkey. It only reads files from `../assets/monkey/` and is not connected to
the game. Three.js r186.1 is vendored in `vendor/three/` so everything works offline.

```bash
# from the repository root
python3 -m http.server 8000
# open http://localhost:8000/viewer/
```

URL parameters: `?clip=walk&cam=Face&light=sun&shading=albedo&paused&ui=0`, `?model=path.glb` to load another build.

Features: orbit / zoom / pan, 41 clips grouped by category with crossfade and speed control, scrubber, camera presets
(keys 1-8), shading inspector (albedo, normal map, AO, roughness, geometry normals, UV checker), wireframe, skeleton overlay,
four light presets, coconut prop attached to the `coconut_attach` bone, paired clips (the tug of war spawns the partner
monkey at the offset stored in `monkey_clips.json`), and a *travel simulation* that scrolls the ground/trunk at each clip's
ground speed so foot sliding is visible.

Automated capture (headless Chromium, software WebGL):

```bash
cd viewer/tests && npm install
node capture.mjs --clips walk,idle --times 0,0.4 --cam 3/4 --out ../../build/monkey/threejs
```

## Castaway viewer

`viewer/castaway.html` (same server, `/viewer/castaway.html`): clip browser for the 142 castaway clips (lazy-loaded animation packs), compare mode (second character), crossfade/speed/scrub, travel simulation from the exported speed/yaw curves, camera presets (full, front, side, back, face, profile, hands, feet, top; 1 to 9), neutral and tropical lighting, wireframe, skeleton, hair toggle, water plane, staff attachment test (follow clip, either hand, back sling, optional line and hook), upper-body layering, hand-pose override and a face tester (19 controls, presets, visemes, lip-sync demo). Headless test: `node viewer/tests/castaway_capture.mjs --query "clip=walk&cam=0" --out build/x.png`.
