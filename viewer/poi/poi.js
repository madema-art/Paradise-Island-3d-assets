// Points of interest viewer: the redesigned Sunken Temple and Glimmer Ring, with draw calls, lights and triangles counted by the renderer.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { buildTemple, buildGlimmerRing, BEFORE } from './poi_kit.js';

const canvas = document.getElementById('stage');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap;

const scene = new THREE.Scene();
const sky = new THREE.Color(0x1d3b4a);            // evening, as the glow reads best at dusk
scene.background = sky;
scene.fog = new THREE.Fog(sky, 70, 200);

const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 500);
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;

scene.add(new THREE.HemisphereLight(0x9fc4d6, 0x2d3a22, 0.9));
const sun = new THREE.DirectionalLight(0xffe2b8, 1.6);
sun.position.set(-30, 40, 20);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
Object.assign(sun.shadow.camera, { left: -60, right: 60, top: 60, bottom: -60, near: 1, far: 160 });
scene.add(sun);

const ground = new THREE.Mesh(new THREE.CircleGeometry(160, 48), new THREE.MeshStandardMaterial({ color: 0x3f5a2e, roughness: 1 }));
ground.rotation.x = -Math.PI / 2;
ground.receiveShadow = true;
scene.add(ground);

// one material per kind, shared by every POI (no per-frame material churn)
const stoneMat = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.95 });
const eyeMat = new THREE.MeshStandardMaterial({ vertexColors: true, emissive: 0xff8a10, emissiveIntensity: 2.5, roughness: 0.4 });
const matteMat = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.9 });
const glowMat = new THREE.MeshBasicMaterial({ vertexColors: true });

const TEMPLE_AT = new THREE.Vector3(-24, 0, 0);
const RING_AT = new THREE.Vector3(26, 0, 0);

const temple = buildTemple(7);
const ring = buildGlimmerRing(9);
const groups = { temple: new THREE.Group(), ring: new THREE.Group() };
groups.temple.position.copy(TEMPLE_AT);
groups.ring.position.copy(RING_AT);

const tStone = new THREE.Mesh(temple.stone, stoneMat);
const tEyes = new THREE.Mesh(temple.eyes, eyeMat);
tStone.castShadow = true; tStone.receiveShadow = true;
groups.temple.add(tStone, tEyes);

const rMatte = new THREE.Mesh(ring.matte, matteMat);
const rGlow = new THREE.Mesh(ring.glow, glowMat);
rMatte.castShadow = true; rMatte.receiveShadow = true;
groups.ring.add(rMatte, rGlow);
scene.add(groups.temple, groups.ring);

const lights = [];
for (const [spec, owner] of [[temple.lights[0], groups.temple], [ring.lights[0], groups.ring]]) {
  const l = new THREE.PointLight(spec.color, spec.intensity, spec.distance, spec.decay);
  l.position.set(...spec.position);
  owner.add(l);
  lights.push({ light: l, base: spec.intensity, owner: owner === groups.temple ? 'temple' : 'ring' });
}

const $ = (id) => document.getElementById(id);
const ui = { show: $('show'), cam: $('cam'), stats: $('stats'), status: $('status') };
const presets = {
  overview: { pos: [0, 22, 58], target: [0, 5, 0] },
  temple: { pos: [-24, 9, 42], target: [-24, 6, 0] },
  ring: { pos: [26, 6, 18], target: [26, 1.5, 0] },
  ringLow: { pos: [26, 1.2, 9], target: [26, 1.4, 0] },
  templeSteps: { pos: [-24, 3, 28], target: [-24, 2.5, 8] },
};
function setCam(name) {
  const p = presets[name];
  camera.position.set(...p.pos);
  controls.target.set(...p.target);
  controls.update();
}
function applyShow() {
  const v = ui.show.value;
  groups.temple.visible = v !== 'ring';
  groups.ring.visible = v !== 'temple';
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

// the animation the game does: eyes pulse, the glow caps breathe, the two lights flicker (one material each, no per-object work)
function animate(tm) {
  eyeMat.emissiveIntensity = 2.5 + 1.2 * Math.sin(tm * 1.6);
  glowMat.color.setScalar(0.85 + 0.2 * Math.sin(tm * 1.4));
  for (const L of lights) L.light.intensity = L.base * (0.8 + 0.2 * Math.sin(tm * (L.owner === 'temple' ? 3.1 : 1.3)));
}

const stats = {
  draws: { temple: temple.counts.draws, ring: ring.counts.draws },
  lights: { temple: temple.counts.lights, ring: ring.counts.lights },
  shadowCasters: { temple: temple.counts.shadowCasters, ring: ring.counts.shadowCasters },
  triangles: {
    temple: Math.round(temple.stone.attributes.position.count / 3 + temple.eyes.attributes.position.count / 3),
    ring: Math.round(ring.matte.attributes.position.count / 3 + ring.glow.attributes.position.count / 3),
  },
  before: BEFORE,
};
window.__poiStats = stats;

function frame(now) {
  animate(now / 1000);
  controls.update();
  renderer.render(scene, camera);
  requestAnimationFrame(frame);
}

resize();
setCam('overview');
applyShow();
ui.stats.textContent = JSON.stringify(stats, null, 1);
ui.status.textContent = 'Temple (left) and Glimmer Ring (right) at game scale.';
requestAnimationFrame(frame);
