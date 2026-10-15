// Giant manta ray asset viewer: plays every clip in assets/manta/Manta.glb, scrubs them, and lists the behaviour spec.
// Standalone. Serve the repo root (python3 -m http.server) and open /viewer/manta.html.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const FILES = window.MANTA_FILES || {};
const url = (name, fallback) => FILES[name] || fallback;

const canvas = document.getElementById('stage');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0c2233);
scene.fog = new THREE.Fog(0x0c2233, 30, 90);

const camera = new THREE.PerspectiveCamera(40, 1, 0.05, 200);
camera.position.set(4.5, 2.2, 6.5);
const controls = new OrbitControls(camera, canvas);
controls.target.set(0, 0.3, 0);
controls.enableDamping = true;
controls.minDistance = 1.5;
controls.maxDistance = 25;

scene.add(new THREE.HemisphereLight(0xcfe9ff, 0x1b3a4a, 1.0));
const sun = new THREE.DirectionalLight(0xfff3dc, 2.2);
sun.position.set(-4, 8, 5);
sun.castShadow = true;
sun.shadow.mapSize.set(1024, 1024);
sun.shadow.camera.left = -5; sun.shadow.camera.right = 5;
sun.shadow.camera.top = 5; sun.shadow.camera.bottom = -5;
scene.add(sun);

// Seabed disc with a soft grid, so the wingspan reads against something
const floor = new THREE.Mesh(new THREE.CircleGeometry(12, 64), new THREE.MeshStandardMaterial({ color: 0x2b5d6b, roughness: 1 }));
floor.rotation.x = -Math.PI / 2;
floor.position.y = -0.9;
floor.receiveShadow = true;
scene.add(floor);
const grid = new THREE.GridHelper(12, 24, 0x6fb7c9, 0x3d7d8c);
grid.position.y = -0.89;
grid.material.transparent = true;
grid.material.opacity = 0.35;
scene.add(grid);

const el = (id) => document.getElementById(id);
const ui = {
  list: el('cliplist'), search: el('search'), load: el('loadstate'), speed: el('speed'), speedOut: el('speedOut'),
  fade: el('fade'), fadeOut: el('fadeOut'), scrub: el('scrub'), timeOut: el('timeOut'),
  pause: el('btnPause'), restart: el('btnRestart'), prev: el('btnPrev'), next: el('btnNext'), info: el('info'),
  behaviour: el('behaviour'), span: el('span'), wingspan: el('wingspan'),
};

let model = null;
let mixer = null;
let actions = new Map();
let current = null;
let clipNames = [];
let meta = null;
let paused = false;

function resize() {
  const w = canvas.clientWidth, h = canvas.clientHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}
addEventListener('resize', resize);
resize();

function fmt(s) { return `${s.toFixed(2)} s`; }

function playClip(name, { fade = parseFloat(ui.fade.value) } = {}) {
  if (!actions.has(name)) return;
  const next = actions.get(name);
  if (current && current !== next) {
    next.reset().setEffectiveWeight(1).play();
    current.crossFadeTo(next, fade, false);
  } else {
    next.reset().setEffectiveWeight(1).play();
  }
  current = next;
  next.paused = paused;
  document.querySelectorAll('#cliplist button').forEach((b) => b.classList.toggle('on', b.dataset.name === name));
  ui.span.textContent = `${name} · ${fmt(next.getClip().duration)} · ${next.getClip().userData?.loop === false ? 'once' : 'loop'}`;
}

function buildList() {
  ui.list.innerHTML = '';
  const q = ui.search.value.trim().toLowerCase();
  clipNames.forEach((name) => {
    if (q && !name.includes(q)) return;
    const b = document.createElement('button');
    b.dataset.name = name;
    const dur = meta?.clips?.[name]?.duration_s;
    b.innerHTML = `<b>${name}</b><span>${dur ? fmt(dur) : ''} · ${meta?.clips?.[name]?.loop ? 'loop' : 'once'}</span>`;
    b.addEventListener('click', () => playClip(name));
    ui.list.appendChild(b);
  });
}

function renderBehaviour(spec, report) {
  if (!spec) { ui.behaviour.textContent = 'Behaviour spec not found.'; return; }
  const r = spec.ranges_m, sp = spec.speed_mps;
  const row = (k, v) => `<tr><th>${k}</th><td>${v}</td></tr>`;
  ui.behaviour.innerHTML = `
    <table>
      ${row('Wingspan', `${spec.wingspan_m} m`)}
      ${row('Patrol speed', `${sp.patrol} m/s, depth ${spec.depth_m.patrol_min}–${spec.depth_m.patrol_max} m`)}
      ${row('Notice / curious / startle', `${r.notice} / ${r.curious_enter} / ${r.startle} m`)}
      ${row('Shadow pass height', `${r.shadow_pass_height} m`)}
      ${row('Breach range', `${r.breach_player_min}–${r.breach_player_max} m player distance`)}
      ${row('Flee speed', `${sp.flee} m/s for ${spec.timers_s.flee_hold} s`)}
      ${row('Breach cooldown', `${spec.cooldowns_s.breach_per_manta[0]}–${spec.cooldowns_s.breach_per_manta[1]} s per manta, ≥${spec.cooldowns_s.breach_global} s world-wide`)}
    </table>
    <h3>Simulated (20 runs × 1 h × 3 mantas)</h3>
    <table>
      ${row('Visible within 90 m', report ? `${(report.seen_fraction_mean * 100).toFixed(0)} % of the time` : '–')}
      ${row('Breaches per manta-hour', report ? report.per_manta_per_hour_means.breach : '–')}
      ${row('Curious / shadow pass / feed per manta-hour', report ? `${report.per_manta_per_hour_means.curious} / ${report.per_manta_per_hour_means.shadow_pass} / ${report.per_manta_per_hour_means.feed}` : '–')}
      ${row('Max speed seen', report ? `${report.speed_mps_max_over_runs} m/s` : '–')}
    </table>
    ${['silhouette', 'shadow', 'sound'].map((k) => `<p class="note">${spec.noticeability[k]}.</p>`).join('')}
    <p class="note">Status: ${spec.integration.status}. Not in the game yet.</p>`;
}

async function loadJSON(name, fallback) {
  try { return await (await fetch(url(name, fallback))).json(); } catch { return null; }
}

async function main() {
  ui.load.textContent = 'Loading…';
  const gltf = await new GLTFLoader().loadAsync(url('Manta.glb', 'assets/manta/Manta.glb'));
  model = gltf.scene;
  model.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
  scene.add(model);

  meta = await loadJSON('manta_clips.json', 'assets/manta/manta_clips.json');
  const spec = await loadJSON('manta_behavior.json', 'assets/manta/manta_behavior.json');
  const report = await loadJSON('behavior_report.json', 'assets/manta/behavior_report.json');
  renderBehaviour(spec, report);
  if (ui.wingspan && spec) ui.wingspan.textContent = `${spec.wingspan_m} m wingspan`;

  mixer = new THREE.AnimationMixer(model);
  const bounds = new THREE.Box3().setFromObject(model);
  const size = bounds.getSize(new THREE.Vector3());
  ui.info.textContent = `${gltf.animations.length} clips · bounds ${size.x.toFixed(2)} × ${size.y.toFixed(2)} × ${size.z.toFixed(2)} m · ${gltf.scene.children.length} root node(s)`;

  for (const clip of gltf.animations) {
    const meta_ = meta?.clips?.[clip.name];
    clip.userData = { loop: meta_ ? meta_.loop : true };
    const action = mixer.clipAction(clip);
    action.setLoop(clip.userData.loop ? THREE.LoopRepeat : THREE.LoopOnce, Infinity);
    action.clampWhenFinished = !clip.userData.loop;
    actions.set(clip.name, action);
  }
  clipNames = [...actions.keys()].sort();
  buildList();
  ui.load.textContent = `${clipNames.length} clips loaded from the packaged GLB`;
  playClip(clipNames.includes('glide_cruise') ? 'glide_cruise' : clipNames[0]);
  ui.span.dataset.ready = '1';
}

ui.search.addEventListener('input', buildList);
ui.speed.addEventListener('input', () => { ui.speedOut.textContent = `${parseFloat(ui.speed.value).toFixed(2)}×`; });
ui.fade.addEventListener('input', () => { ui.fadeOut.textContent = `${parseFloat(ui.fade.value).toFixed(2)} s`; });
ui.pause.addEventListener('click', () => {
  paused = !paused;
  ui.pause.textContent = paused ? 'Play' : 'Pause';
  if (current) current.paused = paused;
});
ui.restart.addEventListener('click', () => { if (current) { current.reset().play(); } });
const step = (dir) => {
  const i = clipNames.indexOf(current?.getClip().name);
  playClip(clipNames[(i + dir + clipNames.length) % clipNames.length]);
};
ui.prev.addEventListener('click', () => step(-1));
ui.next.addEventListener('click', () => step(1));
addEventListener('keydown', (e) => {
  if (e.target.matches('input, select, textarea')) return;
  if (e.code === 'Space') { e.preventDefault(); ui.pause.click(); }
  if (e.code === 'ArrowLeft') step(-1);
  if (e.code === 'ArrowRight') step(1);
});
ui.scrub.addEventListener('input', () => {
  if (!current) return;
  const d = current.getClip().duration;
  current.paused = true;
  current.time = parseFloat(ui.scrub.value) * d;
  mixer.update(0);
});

let last = performance.now();
function frame(now = performance.now()) {
  const dt = Math.min((now - last) / 1000, 0.1) * parseFloat(ui.speed.value);
  last = now;
  if (mixer && !paused) mixer.update(dt);
  if (current && !paused) {
    const d = current.getClip().duration;
    ui.scrub.value = String((current.time % d) / d);
    ui.timeOut.textContent = fmt(current.time % d);
  }
  controls.update();
  renderer.render(scene, camera);
  requestAnimationFrame(frame);
}
frame();

main().catch((err) => {
  ui.load.textContent = `Failed to load: ${err.message}`;
  console.error(err);
});
