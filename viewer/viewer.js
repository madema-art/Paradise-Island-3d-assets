// Standalone asset-workshop viewer for the Paradise Island monkey.
// Loads Monkey.glb (+ coconut.glb, monkey_clips.json), plays every clip, and offers inspection tools.
// It is NOT connected to the game; it only reads files under ../assets/monkey/.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import * as SkeletonUtils from 'three/addons/utils/SkeletonUtils.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const params = new URLSearchParams(location.search);
const MODEL = params.get('model') || '../assets/monkey/Monkey.glb';
const COCONUT = params.get('coconut') || '../assets/monkey/coconut.glb';
const META = params.get('meta') || '../assets/monkey/monkey_clips.json';
if (params.get('ui') === '0') document.body.classList.add('noui');
if (params.get('ui') === '0') for (const el of document.querySelectorAll('.panel, #hint')) el.style.display = 'none';

const GROUPS = [
  ['idle', 'Idle'], ['locomotion', 'Locomotion'], ['climbing', 'Climbing'], ['posture', 'Posture'],
  ['behavior', 'Behaviour'], ['social', 'Social'], ['coconut', 'Coconut'], ['pose', 'Static poses'],
];
const $ = (id) => document.getElementById(id);

// ------------------------------------------------------------------ renderer / scene
const canvas = $('stage');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: params.has('capture') });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap;
renderer.toneMapping = THREE.NeutralToneMapping;

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(32, 1, 0.02, 60);
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.minDistance = 0.15;
controls.maxDistance = 8;
controls.maxPolarAngle = Math.PI * 0.98;

const pmrem = new THREE.PMREMGenerator(renderer);
const envTex = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
scene.environment = envTex;

const hemi = new THREE.HemisphereLight(0xdfe9f2, 0x59624a, 0.5);
scene.add(hemi);
const key = new THREE.DirectionalLight(0xfff1dc, 2.6);
key.castShadow = true;
key.shadow.mapSize.set(2048, 2048);
key.shadow.camera.left = -1.4; key.shadow.camera.right = 1.4; key.shadow.camera.top = 1.4; key.shadow.camera.bottom = -1.4;
key.shadow.camera.near = 0.1; key.shadow.camera.far = 8;
key.shadow.bias = -0.0004; key.shadow.normalBias = 0.01;
scene.add(key, key.target);

const LIGHTS = {
  studio:   { bg: 0x1c2228, env: 0.9, key: 2.4, color: 0xfff1dc, pos: [1.6, 2.6, 1.6], hemi: 0.45, fog: 0x1c2228 },
  sun:      { bg: 0x86b6d6, env: 0.7, key: 3.4, color: 0xffe2b0, pos: [2.2, 2.4, 0.8], hemi: 0.6, fog: 0x86b6d6 },
  jungle:   { bg: 0x1f3a2d, env: 0.45, key: 1.8, color: 0xd9f0c0, pos: [0.8, 3.0, 1.0], hemi: 0.9, fog: 0x1f3a2d },
  overcast: { bg: 0x9aa4ab, env: 1.1, key: 0.9, color: 0xe8eef2, pos: [0.4, 3.2, 0.4], hemi: 0.9, fog: 0x9aa4ab },
};
function setLighting(name) {
  const L = LIGHTS[name] || LIGHTS.studio;
  scene.background = new THREE.Color(L.bg);
  scene.fog = new THREE.Fog(L.fog, 5, 14);
  scene.environmentIntensity = L.env;
  key.intensity = L.key; key.color.set(L.color); key.position.set(...L.pos);
  hemi.intensity = L.hemi;
}

// ground + trunk (textures scroll to fake travel)
function checkerTexture(a, b, cells = 2, size = 256) {
  const c = document.createElement('canvas'); c.width = c.height = size;
  const g = c.getContext('2d');
  const s = size / cells;
  for (let y = 0; y < cells; y++) for (let x = 0; x < cells; x++) { g.fillStyle = (x + y) % 2 ? a : b; g.fillRect(x * s, y * s, s, s); }
  g.strokeStyle = 'rgba(255,255,255,0.12)'; g.lineWidth = 2; g.strokeRect(0, 0, size, size);
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping; t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8;
  return t;
}
const TILE = 0.5;                                         // metres per checker period
const groundTex = checkerTexture('#59664a', '#4d5a40');
groundTex.repeat.set(12, 12);
const ground = new THREE.Mesh(new THREE.PlaneGeometry(6, 6), new THREE.MeshStandardMaterial({ map: groundTex, roughness: 1, metalness: 0 }));
ground.rotation.x = -Math.PI / 2;
ground.receiveShadow = true;
scene.add(ground);

const barkTex = (() => {
  const c = document.createElement('canvas'); c.width = 256; c.height = 512; const g = c.getContext('2d');
  g.fillStyle = '#4a3322'; g.fillRect(0, 0, 256, 512);
  for (let i = 0; i < 260; i++) { g.fillStyle = `rgba(${20 + Math.random() * 50},${12 + Math.random() * 30},8,${0.25 + Math.random() * 0.35})`;
    g.fillRect(Math.random() * 256, Math.random() * 512, 2 + Math.random() * 6, 14 + Math.random() * 60); }
  g.fillStyle = 'rgba(255,255,255,0.14)'; for (let y = 0; y < 512; y += 64) g.fillRect(0, y, 256, 3);
  const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8;
  t.repeat.set(3, 6);
  return t;
})();
const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.12, 5, 48, 1, true), new THREE.MeshStandardMaterial({ map: barkTex, roughness: 0.95 }));
trunk.position.set(0, 2.2, 0.12);            // monkey faces +Z, so the trunk is in front of it (Blender y = -0.12)
trunk.castShadow = trunk.receiveShadow = true;
trunk.visible = false;
scene.add(trunk);

// ------------------------------------------------------------------ state
let monkey = null, coconutProp = null, cocoBone = null, mixer = null, partner = null, partnerMixer = null;
let clipsMeta = {};
let actions = {}, partnerActions = {};
let current = null, currentName = '', paused = false, speed = 1, fade = 0.25, scrubbing = false;
let skinned = [], helper = null, shadingMode = 'pbr', wire = false;
const order = [];                                         // clip names in UI order
let lastT = performance.now();
let fpsAcc = 0, fpsN = 0, fps = 0;

// ------------------------------------------------------------------ camera presets (three coordinates, monkey faces +Z)
const CAMS = {
  '3/4':   [[1.05, 0.62, 1.15], [0, 0.22, 0.12]],
  Front:   [[0.0, 0.34, 1.65], [0, 0.22, 0.1]],
  Side:    [[1.65, 0.30, 0.1], [0, 0.22, 0.1]],
  Back:    [[0.0, 0.40, -1.65], [0, 0.22, 0.1]],
  Top:     [[0.0, 2.0, 0.02], [0, 0.0, 0.1]],
  Face:    [[0.32, 0.38, 0.95], [0, 0.31, 0.43]],
  Hands:   [[0.45, 0.22, 0.95], [0.0, 0.04, 0.34]],
  Wide:    [[2.0, 1.1, 2.4], [0, 0.25, 0.2]],
};
const camNames = Object.keys(CAMS);
function setCamera(name) {
  const [p, t] = CAMS[name] || CAMS['3/4'];
  camera.position.set(...p); controls.target.set(...t); controls.update();
}
const camBox = $('camButtons');
camNames.forEach((n, i) => { const b = document.createElement('button'); b.textContent = n; b.title = `${i + 1}`; b.onclick = () => setCamera(n); camBox.appendChild(b); });

// ------------------------------------------------------------------ inspection shading
const checker = (() => { const t = checkerTexture('#e8e4dc', '#2a3138', 2, 64); t.repeat.set(24, 24); return t; })();
function channelMaterial(tex, mask) {
  const m = new THREE.MeshBasicMaterial({ map: tex });
  m.onBeforeCompile = (sh) => {
    sh.uniforms.uMask = { value: new THREE.Vector3(...mask) };
    sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\nuniform vec3 uMask;')
      .replace('#include <map_fragment>', '#include <map_fragment>\n diffuseColor.rgb = vec3(dot(diffuseColor.rgb, uMask));');
  };
  m.customProgramCacheKey = () => 'mask' + mask.join('');
  return m;
}
function applyShading() {
  for (const m of skinned) {
    if (!m.userData.isBody) continue;
    const o = m.userData.orig;
    let mat = o;
    if (shadingMode === 'albedo') mat = new THREE.MeshBasicMaterial({ map: o.map });
    else if (shadingMode === 'normalmap') mat = new THREE.MeshBasicMaterial({ map: o.normalMap });
    else if (shadingMode === 'ao') mat = channelMaterial(o.aoMap || o.metalnessMap, [1, 0, 0]);
    else if (shadingMode === 'rough') mat = channelMaterial(o.roughnessMap || o.metalnessMap, [0, 1, 0]);
    else if (shadingMode === 'normals') mat = new THREE.MeshNormalMaterial();
    else if (shadingMode === 'uv') mat = new THREE.MeshBasicMaterial({ map: checker });
    m.material = mat;
  }
  for (const m of skinned) m.material.wireframe = wire;
}

// ------------------------------------------------------------------ clips
const usesCoconut = (n) => n.startsWith('coconut_') || n === 'pose_coconut_hold';
function buildClipList() {
  const list = $('cliplist'); list.innerHTML = '';
  const names = (monkey.animations || []).map((c) => c.name);
  const groupOf = (n) => (clipsMeta[n] && clipsMeta[n].group) || (n.startsWith('pose_') ? 'pose' : 'behavior');
  for (const [gid, label] of GROUPS) {
    const inGroup = names.filter((n) => groupOf(n) === gid).sort((a, b) => (clipsMeta[a]?.index ?? 0) - (clipsMeta[b]?.index ?? 0));
    if (!inGroup.length) continue;
    const g = document.createElement('div'); g.className = 'group';
    g.innerHTML = `<h3>${label}</h3>`;
    for (const n of inGroup) {
      order.push(n);
      const b = document.createElement('button'); b.className = 'clip'; b.dataset.clip = n;
      const m = clipsMeta[n] || {};
      const dur = m.seconds ? `${m.seconds.toFixed(1)} s` : '';
      b.innerHTML = `<span>${n.replace(/_/g, ' ')}</span><small>${m.loop === false ? '1×' : (m.loop ? '↻' : '')} ${dur}</small>`;
      b.onclick = () => play(n);
      g.appendChild(b);
    }
    list.appendChild(g);
  }
}

function makeActions(mix, root) {
  const out = {};
  for (const clip of monkey.animations) out[clip.name] = mix.clipAction(clip, root);
  return out;
}

function configure(action, name) {
  const loop = clipsMeta[name]?.loop ?? !/^pose_/.test(name);
  action.reset();
  action.setLoop(loop ? THREE.LoopRepeat : THREE.LoopOnce, Infinity);
  action.clampWhenFinished = true;
  action.enabled = true;
  action.setEffectiveWeight(1);
  action.timeScale = 1;
}

function play(name, opts = {}) {
  if (!actions[name]) return;
  const next = actions[name];
  const f = opts.instant ? 0 : fade;
  configure(next, name);
  if (current && current !== next && f > 0) next.crossFadeFrom(current, f, false);
  else if (current && current !== next) current.stop();
  next.play();
  current = next; currentName = name;
  next.paused = paused;
  // coconut prop
  if (coconutProp) coconutProp.visible = $('chkCoconut').checked && usesCoconut(name);
  // paired clip -> second monkey
  const meta = clipsMeta[name] || {};
  const wantPartner = meta.partner_clip && actions[meta.partner_clip] && $('chkPartner').checked;
  if (wantPartner) {
    if (!partner) makePartner();
    const o = meta.partner_root_offset || [0, -1.08, 0];
    partner.position.set(o[0], o[2], -o[1]);                 // Blender (x,y,z) -> glTF (x,z,-y)
    partner.rotation.set(0, THREE.MathUtils.degToRad(meta.partner_yaw_deg ?? 180), 0);
    partner.visible = true;
    const pa = partnerActions[meta.partner_clip];
    configure(pa, meta.partner_clip); pa.play(); pa.paused = paused;
    for (const [n, a] of Object.entries(partnerActions)) if (a !== pa) a.stop();
  } else if (partner) {
    partner.visible = false;
    for (const a of Object.values(partnerActions)) a.stop();
  }
  // trunk for climbing clips
  const g = meta.group;
  trunk.visible = g === 'climbing';
  ground.visible = $('chkGround').checked && !(g === 'climbing' && !/start|dismount/.test(name));
  document.querySelectorAll('.clip').forEach((b) => b.classList.toggle('active', b.dataset.clip === name));
  showInfo(name, next);
  const sc = $('scrub'); sc.max = next.getClip().duration; sc.value = 0;
  history.replaceState(null, '', `?${new URLSearchParams({ ...Object.fromEntries(params), clip: name })}`);
}

function makePartner() {
  partner = SkeletonUtils.clone(monkey.scene);
  partner.traverse((o) => { if (o.name === 'CoconutProp') o.parent.remove(o); });
  scene.add(partner);
  partnerMixer = new THREE.AnimationMixer(partner);
  partnerActions = makeActions(partnerMixer, partner);
  partner.traverse((o) => { if (o.isSkinnedMesh) { o.castShadow = true; o.frustumCulled = false; } });
}

function showInfo(name, action) {
  const m = clipsMeta[name] || {};
  const d = action.getClip().duration;
  const lines = [`<b>${name}</b>`, `${d.toFixed(2)} s · ${Math.round(d * 30)} frames @ 30 fps · ${m.loop === false ? 'one-shot' : 'loop'}`];
  if (m.speed_mps) lines.push(`ground speed: <b>${Math.abs(m.speed_mps).toFixed(2)} m/s</b> (timeScale = travel / this)`);
  if (m.travel_m !== undefined) lines.push(`baked root travel: ${m.travel_m} m`);
  if (m.yaw_deg) lines.push(`baked root yaw: ${m.yaw_deg}°`);
  if (m.trunk_side) lines.push(`trunk side: ${m.trunk_side}`);
  if (m.pair) lines.push(`paired: ${m.pair} (${m.role}) with <b>${m.partner_clip}</b>`);
  if (m.reach_error_mm) lines.push(`IK reach error: ${Math.max(...Object.values(m.reach_error_mm)).toFixed(1)} mm`);
  if (m.description) lines.push('', m.description);
  $('clipinfo').innerHTML = lines.join('\n');
}

function step(dir) {
  const i = Math.max(0, order.indexOf(currentName));
  play(order[(i + dir + order.length) % order.length]);
}

// ------------------------------------------------------------------ UI wiring
function wire_ui() {
  $('btnPause').onclick = togglePause;
  $('btnRestart').onclick = () => play(currentName, { instant: true });
  $('btnPrev').onclick = () => step(-1);
  $('btnNext').onclick = () => step(1);
  $('speed').oninput = (e) => { speed = +e.target.value; $('speedOut').textContent = speed.toFixed(2) + '×'; };
  $('fade').oninput = (e) => { fade = +e.target.value; $('fadeOut').textContent = fade.toFixed(2) + ' s'; };
  const sc = $('scrub');
  sc.addEventListener('pointerdown', () => { scrubbing = true; });
  sc.addEventListener('pointerup', () => { scrubbing = false; });
  sc.oninput = (e) => seek(+e.target.value);
  $('chkSpin').onchange = (e) => { controls.autoRotate = e.target.checked; controls.autoRotateSpeed = 1.6; };
  $('shading').onchange = (e) => { shadingMode = e.target.value; applyShading(); };
  $('lighting').onchange = (e) => setLighting(e.target.value);
  $('exposure').oninput = (e) => { renderer.toneMappingExposure = +e.target.value; };
  $('chkWire').onchange = (e) => { wire = e.target.checked; applyShading(); };
  $('chkBones').onchange = (e) => { if (helper) helper.visible = e.target.checked; };
  $('chkGround').onchange = (e) => { ground.visible = e.target.checked; };
  $('chkShadow').onchange = (e) => { key.castShadow = e.target.checked; };
  $('chkCoconut').onchange = () => { if (coconutProp) coconutProp.visible = $('chkCoconut').checked && usesCoconut(currentName); };
  $('chkPartner').onchange = () => play(currentName, { instant: true });
  window.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'SELECT') return;
    if (e.code === 'Space') { e.preventDefault(); togglePause(); }
    else if (e.code === 'ArrowRight') step(1);
    else if (e.code === 'ArrowLeft') step(-1);
    else if (e.key === 'r' || e.key === 'R') { const c = $('chkSpin'); c.checked = !c.checked; c.onchange({ target: c }); }
    else if (e.key === 'w' || e.key === 'W') { const c = $('chkWire'); c.checked = !c.checked; c.onchange({ target: c }); }
    else if (e.key === 's' || e.key === 'S') { const c = $('chkBones'); c.checked = !c.checked; c.onchange({ target: c }); }
    else if (/^[1-8]$/.test(e.key)) setCamera(camNames[+e.key - 1]);
  });
}
function togglePause() {
  paused = !paused; $('btnPause').textContent = paused ? 'Play' : 'Pause';
  if (current) current.paused = paused;
  for (const a of Object.values(partnerActions)) if (a.isRunning()) a.paused = paused;
}
function seek(t) {
  if (!current) return;
  current.time = t; current.paused = true;
  const meta = clipsMeta[currentName] || {};
  if (partner && meta.partner_clip) { const pa = partnerActions[meta.partner_clip]; pa.time = t; pa.paused = true; }
  mixer.update(0); if (partnerMixer) partnerMixer.update(0);
  current.paused = paused;
  if (partner && meta.partner_clip) partnerActions[meta.partner_clip].paused = paused;
}

// ------------------------------------------------------------------ main loop
function resize() {
  const w = window.innerWidth, h = window.innerHeight;
  renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
}
window.addEventListener('resize', resize);

function frame() {
  const nowT = performance.now();
  const dt = Math.min((nowT - lastT) / 1000, 0.1);
  lastT = nowT;
  const eff = paused ? 0 : speed;
  if (mixer) mixer.update(dt * eff);
  if (partnerMixer && partner?.visible) partnerMixer.update(dt * eff);
  // travel simulation: scroll the surface opposite to the clip's ground speed
  const meta = clipsMeta[currentName] || {};
  if ($('chkTravel').checked && meta.speed_mps && !paused) {
    const d = meta.speed_mps * eff * dt / TILE / 2;
    if (meta.group === 'climbing') barkTex.offset.y += d * (barkTex.repeat.y / 1) * 0.5 / 3;
    else groundTex.offset.y -= d * 1.0;
  }
  if (current && !scrubbing) { const sc = $('scrub'); sc.value = current.time; $('timeOut').textContent = current.time.toFixed(2) + ' s'; }
  controls.update();
  renderer.render(scene, camera);
  fpsAcc += dt; fpsN++;
  if (fpsAcc > 0.5) { fps = fpsN / fpsAcc; fpsAcc = 0; fpsN = 0; updateStats(); }
  requestAnimationFrame(frame);
}

function updateStats() {
  if (!monkey) return;
  let tris = 0, verts = 0, bones = 0, tex = [];
  const seen = new Set();
  monkey.scene.traverse((o) => {
    if (o.isSkinnedMesh) {
      tris += (o.geometry.index ? o.geometry.index.count : o.geometry.attributes.position.count) / 3;
      verts += o.geometry.attributes.position.count;
      bones = Math.max(bones, o.skeleton.bones.length);
      const mats = Array.isArray(o.userData.orig) ? o.userData.orig : [o.userData.orig];
      for (const mm of mats) for (const k of ['map', 'normalMap', 'metalnessMap', 'emissiveMap']) {
        const t = mm && mm[k]; if (t && t.image && !seen.has(t.uuid)) { seen.add(t.uuid); tex.push(`${k.replace('Map', '')} ${t.image.width}×${t.image.height}`); }
      }
    }
  });
  $('stats').innerHTML = `<b>${Math.round(tris).toLocaleString()}</b> triangles · ${verts.toLocaleString()} vertices\n<b>${bones}</b> bones · ${monkey.animations.length} clips\n${tex.join('\n')}\n${fps.toFixed(0)} fps · ${renderer.info.render.calls} draw calls`;
}

// ------------------------------------------------------------------ boot
async function boot() {
  const loader = new GLTFLoader();
  $('loadstate').textContent = 'Loading model…';
  const [gltf, coco, meta] = await Promise.all([
    loader.loadAsync(MODEL),
    loader.loadAsync(COCONUT).catch(() => null),
    fetch(META).then((r) => (r.ok ? r.json() : {})).catch(() => ({})),
  ]);
  monkey = gltf; clipsMeta = meta;
  let idx = 0; for (const k of Object.keys(meta)) meta[k].index = idx++;
  scene.add(gltf.scene);
  gltf.scene.traverse((o) => {
    if (o.isSkinnedMesh) {
      o.castShadow = true; o.receiveShadow = true; o.frustumCulled = false;
      o.userData.orig = o.material; o.userData.isBody = /Body/.test(o.name);
      skinned.push(o);
      for (const k of ['map']) if (o.material[k]) o.material[k].anisotropy = 8;
      if (o.material.normalMap) o.material.normalMap.anisotropy = 8;
    }
    if (o.isBone && o.name === 'coconut_attach') cocoBone = o;
  });
  if (coco && cocoBone) {
    coconutProp = coco.scene; coconutProp.name = 'CoconutProp';
    coconutProp.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
    cocoBone.add(coconutProp); coconutProp.visible = false;
  }
  helper = new THREE.SkeletonHelper(gltf.scene); helper.visible = false; scene.add(helper);
  mixer = new THREE.AnimationMixer(gltf.scene);
  actions = makeActions(mixer, gltf.scene);
  buildClipList(); wire_ui(); resize(); setLighting(params.get('light') || 'studio'); $('lighting').value = params.get('light') || 'studio';
  setCamera(params.get('cam') || '3/4');
  if (params.get('shading')) { shadingMode = params.get('shading'); $('shading').value = shadingMode; applyShading(); }
  if (params.has('paused')) { paused = true; $('btnPause').textContent = 'Play'; }
  const first = params.get('clip') && actions[params.get('clip')] ? params.get('clip') : (actions.idle ? 'idle' : order[0]);
  play(first, { instant: true });
  $('loadstate').textContent = `${gltf.animations.length} clips · ${skinned.length} skinned meshes`;
  updateStats();
  window.viewer = {
    ready: true, play, seek, setCamera, clips: order.slice(), scene, camera, controls, renderer, THREE,
    // deterministic frame for automated capture: play `name`, jump to t seconds, render once
    at(name, t, cam) {
      paused = true; play(name, { instant: true });
      current.paused = false; seek(t); paused = true; current.paused = true;
      if (partner?.visible) { const pa = partnerActions[clipsMeta[name].partner_clip]; pa.paused = true; }
      if (cam) setCamera(cam);
      controls.update(); renderer.render(scene, camera);
    },
    shading(mode) { shadingMode = mode; applyShading(); renderer.render(scene, camera); },
    lighting(name) { setLighting(name); },
  };
  document.body.dataset.ready = '1';
  requestAnimationFrame(frame);
}
boot().catch((e) => { console.error(e); $('loadstate').textContent = 'Failed to load: ' + e.message; document.body.dataset.error = e.message; });
