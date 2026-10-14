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
