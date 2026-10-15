// Lagoon coral comparison: the game's coral (flat shaded, rebuilt from its primitives) next to the redesign, with the same
// south-seas mix and per-instance colours. Triangles and draw calls are counted by the renderer, one side at a time.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { legacyGeometry, newCoral, triangles, SOUTH_SEAS_WEIGHTS } from './lagoon_kit.js';
import { mulberry32 } from '../canopy/canopy_kit.js';

const canvas = document.getElementById('stage');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.shadowMap.enabled = false;            // the game's coral does not cast shadows (cast: false)

const scene = new THREE.Scene();
const water = new THREE.Color(0x3fb8c9);
scene.background = water;
scene.fog = new THREE.Fog(water, 60, 150);

const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 400);
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;

scene.add(new THREE.HemisphereLight(0xcdf5ff, 0x2a6f7a, 1.6));
const sun = new THREE.DirectionalLight(0xfff4dc, 1.8);
sun.position.set(-20, 40, 15);
scene.add(sun);

const sand = new THREE.Mesh(new THREE.CircleGeometry(60, 48), new THREE.MeshStandardMaterial({ color: 0xd9c49a, roughness: 1 }));
sand.rotation.x = -Math.PI / 2;
sand.position.y = -1.6;
scene.add(sand);

const coralCols = ['#ff6f91', '#ff9a3c', '#c05cff', '#ffd23f', '#59e0c8', '#ff5a5a', '#8ad14a'];
const pick = (rnd, a) => a[Math.floor(rnd() * a.length)];

// the south-seas mix: heads by weight, over the reef disc (radius 16, as the game's reef)
function scatter(seed, count) {
  const rnd = mulberry32(seed);
  const kinds = Object.keys(SOUTH_SEAS_WEIGHTS);
  const lists = Object.fromEntries(kinds.map((k) => [k, []]));
  for (let i = 0; i < count; i++) {
    let u = rnd(), k = 0;
    while (k < kinds.length - 1 && u > SOUTH_SEAS_WEIGHTS[kinds[k]]) { u -= SOUTH_SEAS_WEIGHTS[kinds[k]]; k++; }
    const a = rnd() * Math.PI * 2, r = 16 * Math.sqrt(rnd());
    lists[kinds[k]].push({ x: Math.cos(a) * r, z: Math.sin(a) * r, rot: rnd() * Math.PI * 2, sc: 0.85 + 0.35 * rnd(), tilt: (rnd() - 0.5) * 0.24, color: pick(rnd, coralCols) });
  }
  return lists;
}

// the kinds come in as strings from the object keys; the kit wants numbers for the first three
const kindKey = (k) => (k === '0' || k === '1' || k === '2' ? Number(k) : k);

function placeKinds(lists, makeGeo, material, originX, seed) {
  const group = new THREE.Group();
  group.position.x = originX;
  const rnd = mulberry32(seed);
  const draws = [];
  for (const [kind, list] of Object.entries(lists)) {
    if (!list.length) continue;
    const geo = makeGeo(kindKey(kind));
    const im = new THREE.InstancedMesh(geo, material, list.length);
    const m = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler(), p = new THREE.Vector3(), s = new THREE.Vector3();
    list.forEach((a, i) => {
      e.set(a.tilt, a.rot, (rnd() - 0.5) * 0.24);
      q.setFromEuler(e);
      m.compose(p.set(a.x, -1.55, a.z), q, s.set(a.sc, a.sc, a.sc));
      im.setMatrixAt(i, m);
      im.setColorAt(i, new THREE.Color(a.color));
    });
    im.instanceColor.needsUpdate = true;
    group.add(im);
    draws.push({ kind, im });
  }
  scene.add(group);
  return { group, draws };
}

const LISTS = scatter(21, 520);
const legacyMat = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.7, flatShading: true, side: THREE.DoubleSide, emissive: 0x111111 });
const newMat = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.6, flatShading: false, side: THREE.DoubleSide, emissive: 0x111111 });
const legacy = placeKinds(LISTS, (k) => legacyGeometry(k), legacyMat, -20, 3);
const redesign = placeKinds(LISTS, (k) => newCoral(k, 5), newMat, 20, 3);

const $ = (id) => document.getElementById(id);
const ui = { show: $('show'), cam: $('cam'), stats: $('stats'), status: $('status') };
const presets = {
  overview: { pos: [0, 26, 52], target: [0, -1, 0] },
  legacy: { pos: [-20, 4, 16], target: [-20, -0.5, 0] },
  redesign: { pos: [20, 4, 16], target: [20, -0.5, 0] },
  low: { pos: [0, -0.2, 12], target: [0, -0.8, 0] },
  redesignClose: { pos: [20, 1.6, 6], target: [20, -1.3, -2] },
  legacyClose: { pos: [-20, 1.6, 6], target: [-20, -1.3, -2] },
};
function setCam(name) {
  const p = presets[name];
  camera.position.set(...p.pos);
  controls.target.set(...p.target);
  controls.update();
}
function applyShow() {
  const v = ui.show.value;
  legacy.group.visible = v !== 'redesign';
  redesign.group.visible = v !== 'legacy';
}
ui.show.addEventListener('change', applyShow);
ui.cam.addEventListener('change', () => setCam(ui.cam.value));

function resize() {
  const w = canvas.clientWidth, h = canvas.clientHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}
addEventListener('resize', resize);

// the coral triangles of each side, from its own geometries and instance counts (exact), and the renderer's count of a frame
function sideTriangles(side) {
  return side.draws.reduce((t, { im }) => t + triangles(im.geometry) * im.count, 0);
}
const perKind = (side) => Object.fromEntries(side.draws.map(({ kind, im }) => [kind, triangles(im.geometry)]));
const stats = {
  heads: Object.fromEntries(Object.entries(LISTS).map(([k, v]) => [k, v.length])),
  legacy: { draws: legacy.draws.length, trianglesPerHead: perKind(legacy), trianglesInScene: sideTriangles(legacy) },
  redesign: { draws: redesign.draws.length, trianglesPerHead: perKind(redesign), trianglesInScene: sideTriangles(redesign) },
};
stats.trianglesRatio = +(stats.redesign.trianglesInScene / stats.legacy.trianglesInScene).toFixed(3);
window.__lagoonStats = stats;

function frame() {
  controls.update();
  renderer.render(scene, camera);
  requestAnimationFrame(frame);
}

resize();
setCam('overview');
applyShow();
ui.stats.textContent = JSON.stringify(stats, null, 1);
ui.status.textContent = 'The game coral (left) and the redesign (right), same placement and colours.';
frame();
