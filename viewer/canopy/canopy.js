// Canopy comparison: the current game style next to the new leaf-clump canopy, with draw calls and triangles counted by the renderer.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { currentCanopy, newCanopy, trunkGeometry, triangleCount } from './canopy_kit.js';

const canvas = document.getElementById('stage');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap;

const scene = new THREE.Scene();
const sky = new THREE.Color(0xbcd8e6);
scene.background = sky;
scene.fog = new THREE.Fog(sky, 60, 180);

const camera = new THREE.PerspectiveCamera(36, 1, 0.1, 400);
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;

scene.add(new THREE.HemisphereLight(0xdff3ff, 0x3d5a2c, 1.25));
const sun = new THREE.DirectionalLight(0xfff1d6, 2.6);
sun.position.set(-18, 30, 14);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
Object.assign(sun.shadow.camera, { left: -60, right: 60, top: 60, bottom: -60, near: 1, far: 120 });
sun.shadow.bias = -0.0008;
scene.add(sun);

const ground = new THREE.Mesh(new THREE.CircleGeometry(160, 48), new THREE.MeshStandardMaterial({ color: 0x5e7a3a, roughness: 1 }));
ground.rotation.x = -Math.PI / 2;
ground.receiveShadow = true;
scene.add(ground);

const leafMat = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.82, metalness: 0, side: THREE.DoubleSide });
const trunkMat = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.95 });

const TREE_H = 8.0, RC = 6.2;
const variants = {
  current: { canopy: () => currentCanopy(3, { Rc: RC, H: TREE_H }) },
  new: { canopy: () => newCanopy(3, { Rc: RC, H: TREE_H }) },
};
const geoStats = {};
for (const [k, v] of Object.entries(variants)) {
  const g = v.canopy();
  geoStats[k] = { triangles: Math.round(triangleCount(g)), vertices: g.attributes.position.count };
  v.geometry = g;
}
const trunk = trunkGeometry(TREE_H);
geoStats.trunk = { triangles: Math.round(triangleCount(trunk)) };

function tree(variant, x, z) {
  const g = new THREE.Group();
  g.position.set(x, 0, z);
  const t = new THREE.Mesh(trunk, trunkMat);
  t.castShadow = true;
  const c = new THREE.Mesh(variants[variant].geometry, leafMat);
  c.castShadow = true;
  c.receiveShadow = true;
  g.add(t, c);
  return g;
}

// two trees side by side for the hero view
const heroCurrent = tree('current', -7.5, 0);
const heroNew = tree('new', 7.5, 0);
scene.add(heroCurrent, heroNew);

const $ = (id) => document.getElementById(id);
const ui = { mode: $('mode'), cam: $('cam'), forest: $('forest'), stats: $('stats'), status: $('status') };
let forestGroup = null;

const presets = {
  hero: { pos: [0, 9, 30], target: [0, 6, 0] },
  close: { pos: [-2.5, 6.5, 13], target: [-7.5, 6.8, 0] },
  closeNew: { pos: [2.5, 6.5, 13], target: [7.5, 6.8, 0] },
  top: { pos: [0, 40, 0.01], target: [0, 0, 0] },
  low: { pos: [0, 2.2, 26], target: [0, 6, 0] },
};

function setCam(name) {
  const p = presets[name];
  camera.position.set(...p.pos);
  controls.target.set(...p.target);
  controls.update();
}

function applyMode() {
  const m = ui.mode.value;
  heroCurrent.visible = m !== 'new';
  heroNew.visible = m !== 'current';
}

function resize() {
  const w = canvas.clientWidth, h = canvas.clientHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}
addEventListener('resize', resize);

ui.mode.addEventListener('change', applyMode);
ui.cam.addEventListener('change', () => setCam(ui.cam.value));

/* ---- forest stress: N trees of one variant on a grid (draw calls and triangles per frame, the game's bottleneck) */
function buildForest(variant, n) {
  if (forestGroup) { scene.remove(forestGroup); forestGroup = null; }
  forestGroup = new THREE.Group();
  const side = Math.ceil(Math.sqrt(n));
  let placed = 0;
  for (let i = 0; i < side && placed < n; i++) {
    for (let j = 0; j < side && placed < n; j++) {
      const x = (i - side / 2) * 9 + (j % 2) * 1.5, z = (j - side / 2) * 9;
      forestGroup.add(tree(variant, x, z));
      placed++;
    }
  }
  scene.add(forestGroup);
  heroCurrent.visible = heroNew.visible = false;
  return placed;
}

function measure(frames = 24) {
  return new Promise((resolve) => {
    const times = [];
    let calls = 0, tris = 0, last = performance.now(), k = 0;
    function step(now) {
      renderer.render(scene, camera);
      if (k >= 5) {                                          // skip the first frames (shader and buffer upload)
        times.push(now - last);
        calls = renderer.info.render.calls;
        tris = renderer.info.render.triangles;
      }
      last = now;
      k++;
      if (k < frames + 5) requestAnimationFrame(step);
      else {
        times.sort((a, b) => a - b);
        resolve({ drawCalls: calls, triangles: tris, medianFrameMs: +times[times.length >> 1].toFixed(2) });
      }
    }
    requestAnimationFrame(step);
  });
}

ui.forest.addEventListener('click', async () => {
  const variant = ui.mode.value === 'new' ? 'new' : 'current';
  const n = 100;
  const placed = buildForest(variant, n);
  setCam('top');
  camera.position.set(0, 60, 0.01);
  controls.target.set(0, 0, 0);
  controls.update();
  ui.status.textContent = `measuring ${placed} ${variant} trees...`;
  await new Promise((r) => setTimeout(r, 300));
  const m = await measure();
  forestResults[variant] = { trees: placed, ...m, drawCallsPerTree: +(m.drawCalls / placed).toFixed(2), trianglesPerTree: Math.round(m.triangles / placed) };
  ui.stats.textContent = JSON.stringify(forestResults, null, 1);
  ui.status.textContent = `forest of ${placed} ${variant} trees measured (software GL; relative numbers only)`;
  scene.remove(forestGroup); forestGroup = null;
  applyMode(); setCam('hero');
  window.__canopyForest = forestResults;
});
const forestResults = {};

function frame() {
  controls.update();
  renderer.render(scene, camera);
  requestAnimationFrame(frame);
}

resize();
setCam('hero');
applyMode();
ui.stats.textContent = JSON.stringify({ geometry: geoStats }, null, 1);
window.__canopyGeo = geoStats;
frame();
