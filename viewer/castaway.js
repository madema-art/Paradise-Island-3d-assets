// Standalone asset-workshop viewer for the Paradise Island castaway.
// Loads Castaway.glb (+ animation packs on demand, Staff.glb, proxy props, castaway_clips.json / _face.json / _grips.json).
// It is NOT connected to the game; it only reads files under ../assets/castaway/ (or the published artifact files).
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import * as SkeletonUtils from 'three/addons/utils/SkeletonUtils.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const params = new URLSearchParams(location.search);
const BASE = params.get('base') || '../assets/castaway/';
const FILES = window.CASTAWAY_FILES || {};
const url = (n) => FILES[n] || BASE + n;
const $ = (id) => document.getElementById(id);
if (params.get('ui') === '0') for (const el of document.querySelectorAll('.panel, #hint')) el.style.display = 'none';

// ------------------------------------------------------------------ renderer / scene
const canvas = $('stage');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: params.has('capture') });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap;
renderer.toneMapping = THREE.NeutralToneMapping;
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(30, 1, 0.02, 80);
camera.position.set(2.2, 1.4, 4.0);
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true; controls.dampingFactor = 0.08; controls.minDistance = 0.12; controls.maxDistance = 14;
controls.target.set(0, 1.0, 0);
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
const hemi = new THREE.HemisphereLight(0xdfe9f2, 0x59624a, 0.5); scene.add(hemi);
const key = new THREE.DirectionalLight(0xfff1dc, 2.4);
key.castShadow = true; key.shadow.mapSize.set(2048, 2048);
Object.assign(key.shadow.camera, { left: -2.6, right: 2.6, top: 2.6, bottom: -2.6, near: 0.1, far: 14 });
key.shadow.bias = -0.0004; key.shadow.normalBias = 0.012;
scene.add(key, key.target);

const LIGHTS = {
  studio:   { bg: 0x1c2228, env: 0.9, key: 2.4, color: 0xfff1dc, pos: [1.8, 3.0, 2.4], hemi: 0.45, fog: 0x1c2228 },
  tropical: { bg: 0x7fb4d8, env: 0.75, key: 3.6, color: 0xffe6b8, pos: [2.6, 3.2, 1.4], hemi: 0.65, fog: 0x9ccbe6 },
  shade:    { bg: 0x2a4a36, env: 0.5, key: 1.5, color: 0xdff2c4, pos: [0.8, 3.2, 1.2], hemi: 1.0, fog: 0x2a4a36 },
  dusk:     { bg: 0xd49a68, env: 0.55, key: 3.0, color: 0xffb070, pos: [-3.0, 1.2, 2.0], hemi: 0.55, fog: 0xd49a68 },
  overcast: { bg: 0x9aa4ab, env: 1.1, key: 0.9, color: 0xe8eef2, pos: [0.4, 3.2, 0.6], hemi: 0.9, fog: 0x9aa4ab },
};
function setLighting(name) {
  const L = LIGHTS[name] || LIGHTS.studio;
  scene.background = new THREE.Color(L.bg);
  scene.fog = new THREE.Fog(L.fog, 8, 24);
  scene.environmentIntensity = L.env;
  key.intensity = L.key; key.color.set(L.color); key.position.set(...L.pos);
  hemi.intensity = L.hemi;
  groundMat.color.set(name === 'studio' ? 0xffffff : 0xffffff);
}

// ground (infinite checker following the character) + water plane
function checker(a, b, cells = 2, size = 256) {
  const c = document.createElement('canvas'); c.width = c.height = size;
  const g = c.getContext('2d'); const s = size / cells;
  for (let y = 0; y < cells; y++) for (let x = 0; x < cells; x++) { g.fillStyle = (x + y) % 2 ? a : b; g.fillRect(x * s, y * s, s, s); }
  g.strokeStyle = 'rgba(255,255,255,0.10)'; g.lineWidth = 2; g.strokeRect(0, 0, size, size);
  const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; return t;
}
const TILE = 0.5;
const groundTex = checker('#5d6a50', '#6a785c'); groundTex.repeat.set(60 / TILE / 2, 60 / TILE / 2);
const groundMat = new THREE.MeshStandardMaterial({ map: groundTex, roughness: 1 });
const ground = new THREE.Mesh(new THREE.PlaneGeometry(60, 60), groundMat);
ground.rotation.x = -Math.PI / 2; ground.receiveShadow = true; scene.add(ground);
const water = new THREE.Mesh(new THREE.PlaneGeometry(60, 60), new THREE.MeshStandardMaterial({ color: 0x2c7f92, transparent: true, opacity: 0.55, roughness: 0.15, metalness: 0.0 }));
water.rotation.x = -Math.PI / 2; water.position.y = 0.06; water.visible = false; scene.add(water);

// ------------------------------------------------------------------ data + model
const loader = new GLTFLoader();
const [INDEX, FACE, GRIPS] = await Promise.all(['castaway_clips.json', 'castaway_face.json', 'castaway_grips.json'].map((n) => fetch(url(n)).then((r) => r.json())));
const CLIPS = INDEX.clips;
$('loadstate').textContent = 'Loading model…';
const gltf = await loader.loadAsync(url('Castaway.glb'));

const world = new THREE.Group(); scene.add(world);
const charGroup = new THREE.Group(); world.add(charGroup);
const model = gltf.scene; charGroup.add(model);
model.traverse((o) => { if (o.isMesh || o.isSkinnedMesh) { o.castShadow = true; o.receiveShadow = true; o.frustumCulled = false; } });
const hairMeshes = [];
const skinMeshes = [];
model.traverse((o) => {
  if (!(o.isMesh)) return;
  skinMeshes.push(o);
  const ms = Array.isArray(o.material) ? o.material : [o.material];
  for (const m of ms) if (m.name === 'CastawayHair') { m.alphaToCoverage = true; if (!hairMeshes.includes(o)) hairMeshes.push(o); }
});
const bone = (n) => model.getObjectByName(n);
const origMats = new Map(); for (const m of skinMeshes) origMats.set(m, m.material);

const mixer = new THREE.AnimationMixer(model);
const clipCache = new Map();
for (const c of gltf.animations) clipCache.set(c.name, c);
const packLoaded = new Set();
async function ensureClip(name) {
  if (clipCache.has(name)) return clipCache.get(name);
  const base = name.replace(/__upper$/, '');
  const rec = CLIPS[base];
  if (!rec) throw new Error('unknown clip ' + name);
  if (!packLoaded.has(rec.pack)) {
    packLoaded.add(rec.pack);
    $('loadstate').textContent = `Loading pack ${rec.pack}…`;
    const g = await loader.loadAsync(url(`Castaway_anim_${rec.pack}.glb`));
    for (const c of g.animations) clipCache.set(c.name, c);
    $('loadstate').textContent = `${Object.keys(CLIPS).length} clips`;
  }
  return clipCache.get(name);
}

// ------------------------------------------------------------------ props
const staffRoot = new THREE.Group(); staffRoot.visible = false; scene.add(staffRoot);
let staffLoaded = false;
async function ensureStaff() {
  if (staffLoaded) return; staffLoaded = true;
  const g = await loader.loadAsync(url('Staff.glb'));
  g.scene.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.frustumCulled = false; } });
  staffRoot.add(g.scene);
  staffRoot.userData.line = [g.scene.getObjectByName('Staff_line'), g.scene.getObjectByName('Staff_hook')].filter(Boolean);
  applyStaffLine();
}
const PROPS = {};
async function ensureProp(file) {
  if (PROPS[file]) return PROPS[file];
  const g = await loader.loadAsync(url(file));
  g.scene.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
  PROPS[file] = g.scene; return g.scene;
}
const proxyRoot = new THREE.Group(); world.add(proxyRoot);
const paddleHolder = new THREE.Group(); scene.add(paddleHolder);
let coconut, fish;
function makeCoconut() {
  const m = new THREE.Mesh(new THREE.SphereGeometry(0.075, 20, 14), new THREE.MeshStandardMaterial({ color: 0x5a3f27, roughness: 0.95 }));
  m.scale.set(1, 1.12, 1); m.castShadow = true; return m;
}
function makeFish() {
  const g = new THREE.Group();
  const body = new THREE.Mesh(new THREE.SphereGeometry(0.5, 18, 12), new THREE.MeshStandardMaterial({ color: 0x4a8fb0, roughness: 0.35, metalness: 0.2 }));
  body.scale.set(0.05, 0.15, 0.085); g.add(body);
  const tail = new THREE.Mesh(new THREE.ConeGeometry(0.06, 0.1, 10), new THREE.MeshStandardMaterial({ color: 0xd9a441, roughness: 0.5 }));
  tail.position.y = -0.17; tail.rotation.z = Math.PI; tail.scale.set(0.35, 1, 1); g.add(tail);
  g.traverse((o) => { if (o.isMesh) o.castShadow = true; }); return g;
}
coconut = makeCoconut(); fish = makeFish(); scene.add(coconut, fish); coconut.visible = fish.visible = false;

function quatFrom(a) { return new THREE.Quaternion(a[0], a[1], a[2], a[3]); }
function mountStaff() {
  const mode = $('staffMode').value;
  const rec = state.rec;
  const uses = rec && (rec.props.uses || []).includes('staff');
  if (mode === 'off' || (mode === 'auto' && !uses)) { staffRoot.visible = false; return; }
  if (!staffLoaded) { ensureStaff().then(mountStaff); return; }
  let parent; staffRoot.position.set(0, 0, 0); staffRoot.quaternion.identity();
  if (mode === 'auto') parent = bone('prop_staff');
  else { const g = GRIPS.grips[mode]; parent = bone(g.bone); staffRoot.position.set(...g.p); staffRoot.quaternion.copy(quatFrom(g.q)); }
  if (parent && staffRoot.parent !== parent) parent.add(staffRoot);
  staffRoot.visible = true;
}
function applyStaffLine() { for (const o of staffRoot.userData.line || []) o.visible = $('chkStaffLine').checked; }

const PROP_FILES = { canoe: 'props/Canoe.glb', boulder: 'props/Boulder.glb', rock: 'props/Rock.glb', palm: 'props/PalmTrunk.glb', log: 'props/Log.glb' };
async function updateProps() {
  const rec = state.rec; proxyRoot.clear();
  const auto = $('chkAutoProps').checked;
  paddleHolder.visible = false; coconut.visible = fish.visible = false;
  if (!rec || !auto) return;
  const uses = rec.props.uses || [];
  for (const [k, f] of Object.entries(PROP_FILES)) if (uses.includes(k)) proxyRoot.add((await ensureProp(f)).clone());
  if ((rec.extra && rec.extra.fire_pos) || uses.includes('firewood')) {
    const fp = (rec.extra && rec.extra.fire_pos) || [0, -0.8, 0.25];
    const f = (await ensureProp('props/Campfire.glb')).clone(); f.position.set(fp[0], 0, -fp[1]); proxyRoot.add(f);
  }
  if (uses.includes('paddle')) { const p = await ensureProp('props/Paddle.glb'); if (!paddleHolder.children.length) paddleHolder.add(p); const b = bone('prop_aux'); if (b) { b.add(paddleHolder); paddleHolder.visible = true; } }
}
function palmNormal(side) { const g = GRIPS.grips[`${side}_main`]; return new THREE.Vector3(0, 0, 1).applyQuaternion(quatFrom(g.q)); }
function updateAttached() {
  const rec = state.rec; coconut.visible = fish.visible = false;
  if (!rec || !$('chkAutoProps').checked) return;
  const t = state.action ? state.action.time : 0;
  for (const at of rec.props.attach || []) {
    const obj = at.prop === 'coconut' ? coconut : at.prop === 'fish' ? fish : null; if (!obj) continue;
    const side = at.bone.endsWith('_L') ? 'L' : 'R';
    let t0 = at.from_t ?? 0;
    if (at.from_event) { const e = rec.events.find((x) => x.name === at.from_event); t0 = e ? e.t : 0; }
    obj.visible = true;
    if (t >= t0) {
      const b = bone(at.bone); if (b && obj.parent !== b) { b.add(obj); }
      const n = palmNormal(side);
      obj.position.copy(n).multiplyScalar(at.prop === 'fish' ? 0.04 : 0.075);
      obj.quaternion.copy(at.prop === 'fish' ? quatFrom(GRIPS.grips[`${side}_main`].q) : new THREE.Quaternion());
      obj.scale.setScalar(1);
    } else {                                   // not picked up yet: lying on the ground in front of him
      if (obj.parent !== scene) scene.add(obj);
      obj.position.set(-0.12, 0.07, 0.30); obj.quaternion.identity();
    }
  }
}

// ------------------------------------------------------------------ playback state
const state = { name: null, rec: null, action: null, overlay: null, paused: false, repeatHold: 0, lastT: 0, yawBase: 0, cmp: null };
let travelPos = new THREE.Vector3(), travelYaw = 0;
const cmp = { group: new THREE.Group(), model: null, mixer: null, action: null, name: '' };
world.add(cmp.group); cmp.group.visible = false;

async function play(name, opts = {}) {
  const rec = CLIPS[name]; if (!rec) return;
  const clip = await ensureClip(name);
  const fade = opts.instant ? 0 : parseFloat($('fade').value);
  const next = mixer.clipAction(clip);
  next.reset(); next.enabled = true;
  next.setLoop(rec.loop ? THREE.LoopRepeat : THREE.LoopOnce, Infinity); next.clampWhenFinished = true;
  next.timeScale = 1; next.setEffectiveWeight(1);
  if (state.action && state.action !== next) { if (fade > 0) { state.action.fadeOut(fade); next.fadeIn(fade); } else state.action.stop(); }
  next.play();
  state.action = next; state.name = name; state.rec = rec; state.repeatHold = 0; state.lastT = 0;
  state.yawBase = travelYaw;
  if (rec.root_motion.type === 'anchored' || opts.resetPos) { travelPos.set(0, 0, 0); travelYaw = 0; state.yawBase = 0; }
  if (rec.root_motion.type === 'vertical') { travelPos.set(0, 0, 0); }
  applyOverlay();
  document.querySelectorAll('.clip').forEach((b) => b.classList.toggle('active', b.dataset.name === name));
  showInfo(); mountStaff(); updateProps(); history.replaceState(null, '', '#' + name);
  scrub.max = rec.duration_s; scrub.value = 0;
}

async function applyOverlay() {
  if (state.overlay) { state.overlay.stop(); state.overlay = null; }
  const n = $('layerClip').value; if (!n) return;
  const clip = await ensureClip(n + '__upper'); if (!clip) return;
  const a = mixer.clipAction(clip); a.reset(); a.setLoop(THREE.LoopRepeat, Infinity); a.play();
  state.overlay = a; setLayerWeight();
}
function setLayerWeight() {
  const w = parseFloat($('layerW').value); $('layerOut').textContent = w.toFixed(2);
  if (state.overlay) state.overlay.setEffectiveWeight(w / (1 - Math.min(w, 0.995)));
}

// compare character
async function setCompare(name) {
  if (!name) { cmp.group.visible = false; if (cmp.action) cmp.action.stop(); cmp.action = null; charGroup.position.x = 0; return; }
  if (!cmp.model) {
    cmp.model = SkeletonUtils.clone(model); cmp.group.add(cmp.model);
    cmp.model.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.frustumCulled = false; } });
    cmp.mixer = new THREE.AnimationMixer(cmp.model);
  }
  const clip = await ensureClip(name); const rec = CLIPS[name];
  if (cmp.action) cmp.action.stop();
  cmp.action = cmp.mixer.clipAction(clip); cmp.action.reset(); cmp.action.setLoop(rec.loop ? THREE.LoopRepeat : THREE.LoopRepeat, Infinity); cmp.action.play();
  cmp.name = name; cmp.group.visible = true;
  $('chkTravel').checked = false; travelPos.set(0, 0, 0); travelYaw = 0;
  charGroup.position.set(-0.7, 0, 0); cmp.group.position.set(0.7, 0, 0);
}

// ------------------------------------------------------------------ face
const faceW = {}; const faceSliders = {};
for (const c of FACE.controls) faceW[c.key] = 0;
const faceNodes = {}; for (const b of FACE.face_bones) faceNodes[b] = bone(b);
function setFace(values) {
  for (const c of FACE.controls) faceW[c.key] = 0;
  for (const [k, v] of Object.entries(values || {})) faceW[k] = v;
  for (const c of FACE.controls) { const s = faceSliders[c.key]; if (s) { s.input.value = faceW[c.key]; s.out.textContent = faceW[c.key].toFixed(2); } }
}
const qI = new THREE.Quaternion(), qT = new THREE.Quaternion();
let blinkT = 2.0, blinkPhase = -1, talkT = 0, talkTarget = {}, talkCur = {};
function faceBefore() { for (const b of FACE.face_bones) { const n = faceNodes[b]; const r = FACE.rest[b]; if (n) { n.quaternion.set(...r.q); n.position.set(...r.t); } } }
function faceAfter(dt) {
  const w = { ...faceW };
  if ($('chkBlink').checked) {
    blinkT -= dt; if (blinkT < 0 && blinkPhase < 0) { blinkPhase = 0; blinkT = 2.4 + Math.random() * 3.2; }
    if (blinkPhase >= 0) { blinkPhase += dt / 0.16; const b = Math.sin(Math.PI * Math.min(blinkPhase, 1)) ** 0.8; w.blink_L = Math.max(w.blink_L, b); w.blink_R = Math.max(w.blink_R, b); if (blinkPhase >= 1) blinkPhase = -1; }
  }
  if ($('chkTalk').checked) {
    talkT -= dt; const names = Object.keys(FACE.visemes);
    if (talkT < 0) { talkT = 0.09 + Math.random() * 0.14; talkTarget = FACE.visemes[names[1 + Math.floor(Math.random() * (names.length - 1))]]; if (Math.random() < 0.15) talkTarget = {}; }
    for (const c of FACE.controls) { const tv = talkTarget[c.key] || 0; talkCur[c.key] = (talkCur[c.key] || 0) + (tv - (talkCur[c.key] || 0)) * Math.min(1, dt * 18); w[c.key] = (w[c.key] || 0) + talkCur[c.key]; }
  }
  for (const c of FACE.controls) {
    const v = w[c.key]; if (!v || Math.abs(v) < 1e-3) continue;
    const set = v >= 0 ? c.pos : (c.neg || c.pos); const a = Math.abs(v) * (v >= 0 || c.neg ? 1 : -1);
    for (const [bn, d] of Object.entries(set)) {
      const n = faceNodes[bn]; if (!n) continue;
      qT.set(...d.q); qT.slerp(qI.identity(), 0); const qd = new THREE.Quaternion().identity().slerp(qT.set(...d.q), Math.min(Math.abs(a), 1.6) > 1 ? 1 : Math.abs(a));
      n.quaternion.multiply(qd); n.position.x += d.t[0] * a; n.position.y += d.t[1] * a; n.position.z += d.t[2] * a;
    }
  }
}

// ------------------------------------------------------------------ camera presets
const CAMS = [
  ['Full', null, 4.6, 28, 10, [0, 0.98, 0]], ['Front', null, 4.6, 0, 6, [0, 0.98, 0]], ['Side', null, 4.6, 90, 6, [0, 0.98, 0]], ['Back', null, 4.6, 180, 8, [0, 0.98, 0]],
  ['Face', 'head', 0.85, 18, 6, [0, 0.07, 0.02]], ['Profile', 'head', 0.9, 90, 4, [0, 0.07, 0.02]], ['Hands', 'hands', 1.1, 20, 20, [0, 0, 0]], ['Feet', 'feet', 1.3, 25, 18, [0, 0.06, 0]], ['Top', null, 4.0, 0, 80, [0, 0.9, 0]],
];
let camIdx = 0;
function camTarget(c) {
  const out = new THREE.Vector3();
  if (c[1] === 'head') { const b = bone('head'); b.getWorldPosition(out); out.add(new THREE.Vector3(...c[5])); }
  else if (c[1] === 'hands') { const a = new THREE.Vector3(), b = new THREE.Vector3(); bone('attach_hand_L').getWorldPosition(a); bone('attach_hand_R').getWorldPosition(b); out.addVectors(a, b).multiplyScalar(0.5); }
  else if (c[1] === 'feet') { const a = new THREE.Vector3(), b = new THREE.Vector3(); bone('foot_L').getWorldPosition(a); bone('foot_R').getWorldPosition(b); out.addVectors(a, b).multiplyScalar(0.5).add(new THREE.Vector3(...c[5])); }
  else { out.set(...c[5]).add(charGroup.position); }
  return out;
}
function setCamera(i, snap = true) {
  camIdx = i; const c = CAMS[i]; const tgt = camTarget(c);
  const az = THREE.MathUtils.degToRad(c[3]) + travelYaw, el = THREE.MathUtils.degToRad(c[4]);
  const d = c[2];
  camera.position.set(tgt.x + d * Math.sin(az) * Math.cos(el), tgt.y + d * Math.sin(el), tgt.z + d * Math.cos(az) * Math.cos(el));
  controls.target.copy(tgt);
  document.querySelectorAll('#camButtons button').forEach((b, k) => b.classList.toggle('active', k === i));
}
const camBtns = $('camButtons');
CAMS.forEach((c, i) => { const b = document.createElement('button'); b.textContent = `${i + 1} ${c[0]}`; b.onclick = () => setCamera(i); camBtns.append(b); });

// ------------------------------------------------------------------ UI
const scrub = $('scrub');
const tiers = [...new Set(Object.values(CLIPS).map((c) => c.tier))];
for (const t of tiers) { const o = document.createElement('option'); o.value = t; o.textContent = t.replace(/_/g, ' '); $('fTier').append(o); }
const TIER_LABEL = { base_loop: 'Base loops', transition: 'Transitions', interaction_action: 'Interaction actions', emotional_reaction: 'Emotional reactions', personality_action: 'Personality actions' };
let order = [];
function buildList() {
  const q = $('search').value.trim().toLowerCase(), ft = $('fTier').value, fs = $('fStatus').value;
  const root = $('cliplist'); root.innerHTML = ''; order = [];
  const byTier = {};
  for (const [n, r] of Object.entries(CLIPS)) {
    if (ft && r.tier !== ft) continue; if (fs && r.status !== fs) continue;
    if (q && !(n.includes(q) || r.description.toLowerCase().includes(q) || r.group.includes(q))) continue;
    ((byTier[r.tier] ||= {})[r.group] ||= []).push(n);
  }
  for (const t of Object.keys(TIER_LABEL)) {
    if (!byTier[t]) continue;
    const g = document.createElement('div'); g.className = 'group'; g.innerHTML = `<h3>${TIER_LABEL[t]}</h3>`;
    for (const [grp, names] of Object.entries(byTier[t])) {
      g.insertAdjacentHTML('beforeend', `<h4>${grp}</h4>`);
      for (const n of names) {
        const r = CLIPS[n]; const b = document.createElement('button'); b.className = 'clip' + (n === state.name ? ' active' : ''); b.dataset.name = n;
        b.innerHTML = `<span>${n}</span><small class="${r.status === 'verified' ? '' : 'dev'}">${r.duration_s.toFixed(1)}s${r.loop ? ' ⟳' : ''}${r.status === 'verified' ? '' : ' ⚠'}</small>`;
        b.title = r.description; b.onclick = () => play(n); g.append(b); order.push(n);
      }
    }
    root.append(g);
  }
}
$('search').oninput = buildList; $('fTier').onchange = buildList; $('fStatus').onchange = buildList;
for (const sel of ['layerClip', 'cmpClip']) {
  for (const [n, r] of Object.entries(CLIPS)) { if (sel === 'layerClip' && !r.upper_body_variant) continue; const o = document.createElement('option'); o.value = n; o.textContent = n; $(sel).append(o); }
}
$('layerClip').onchange = applyOverlay; $('layerW').oninput = setLayerWeight; $('cmpClip').onchange = (e) => setCompare(e.target.value);

function showInfo() {
  const r = state.rec; if (!r) return;
  const rm = r.root_motion; const ev = r.events.filter((e) => !e.auto).map((e) => `${e.t.toFixed(2)}s ${e.name}`).join(', ') || '—';
  const foot = r.events.filter((e) => e.auto).length;
  const lines = [
    `<b>${r.name}</b>  ${r.duration_s.toFixed(2)} s · ${r.frames} frames @ ${r.fps} fps${r.loop ? ' · loop' : ''}`,
    r.description, '',
    `<b>Status</b> ${r.status === 'verified' ? 'verified' : '<span class="warn">in development</span>'} — ${r.status_note}`,
    `<b>Tier</b> ${r.tier.replace(/_/g, ' ')} · <b>group</b> ${r.group} · <b>pack</b> ${r.pack}`,
    `<b>Poses</b> ${r.start_pose || '—'} → ${r.end_pose || '—'}${r.next_clip ? ` (next: ${r.next_clip} @ phase ${r.next_phase})` : ''}`,
    `<b>Blend</b> in ${r.blend.blend_in_s}s · out ${r.blend.blend_out_s}s · interruptible: ${r.interruptible}`,
    `<b>Root motion</b> ${rm.type}${rm.reference_speed_m_s ? ` · ref ${rm.reference_speed_m_s} m/s` : ''}${rm.distance_m != null ? ` · ${rm.distance_m} m` : ''}${rm.climb_speed_m_s ? ` · climb ${rm.climb_speed_m_s} m/s` : ''}${rm.anchor ? ` · anchor ${rm.anchor}` : ''}`,
    `<b>Props</b> ${(r.props.uses || []).join(', ') || '—'}${r.props.staff_use ? ` (staff as ${r.props.staff_use})` : ''}`,
    `<b>Events</b> ${ev}${foot ? ` · ${foot} auto foot events` : ''}`,
    `<b>QA</b> IK reach miss ${r.qa.reach_miss_mm} mm · min height ${r.qa.min_z_m} m · ${r.qa.keyframe_count} keys`,
    r.upper_body_variant ? `<b>Upper-body layer</b> ${r.upper_body_variant}` : '',
  ];
  $('clipinfo').innerHTML = lines.filter((x) => x !== undefined).join('\n');
}

function stats() {
  let tris = 0, joints = 0; const tex = new Set(); const mats = new Set();
  model.traverse((o) => {
    if (o.isMesh) { const g = o.geometry; tris += (g.index ? g.index.count : g.attributes.position.count) / 3; if (o.skeleton) joints = Math.max(joints, o.skeleton.bones.length); }
    if (o.isMesh) for (const m of (Array.isArray(o.material) ? o.material : [o.material])) {
      mats.add(m.name);
      for (const k of ['map', 'normalMap', 'metalnessMap', 'roughnessMap', 'aoMap', 'emissiveMap']) if (m[k] && m[k].image) tex.add(`${m[k].image.width}×${m[k].image.height}`);
    }
  });
  const f = INDEX.files; const c = INDEX.counts;
  $('stats').innerHTML = [`<b>Triangles</b> ${Math.round(tris).toLocaleString()} · <b>joints</b> ${joints}`, `<b>Materials</b> ${[...mats].join(', ')}`, `<b>Texture sizes</b> ${[...tex].join(', ')}`,
    `<b>Clips</b> ${c.total} (${c.verified} verified, ${c.in_development} in development) + ${c.upper_variants} upper-body layers`,
    `<b>Files</b> Castaway.glb ${(f['Castaway.glb'] / 1e6).toFixed(1)} MB · packs ${(Object.entries(f).filter(([k]) => k.startsWith('Castaway_anim')).reduce((s, [, v]) => s + v, 0) / 1e6).toFixed(1)} MB`].join('\n');
}

// face UI
{
  const ps = $('presetButtons'), vs = $('visemeButtons'), sl = $('faceSliders');
  for (const [n, v] of Object.entries(FACE.presets)) { const b = document.createElement('button'); b.textContent = n.replace('_', ' '); b.onclick = () => setFace(v); ps.append(b); }
  for (const [n, v] of Object.entries(FACE.visemes)) { const b = document.createElement('button'); b.textContent = n; b.title = 'viseme'; b.onclick = () => setFace(v); vs.append(b); }
  for (const c of FACE.controls) {
    const l = document.createElement('label'); const out = document.createElement('output'); out.textContent = '0.00';
    const input = document.createElement('input'); input.type = 'range'; input.min = c.min; input.max = c.max; input.step = 0.01; input.value = 0;
    input.oninput = () => { faceW[c.key] = parseFloat(input.value); out.textContent = faceW[c.key].toFixed(2); };
    l.append(c.label + ' ', out, input); sl.append(l); faceSliders[c.key] = { input, out };
  }
  $('btnFaceReset').onclick = () => setFace({});
}

// look
for (const id of ['lighting']) $(id).onchange = () => setLighting($(id).value);
$('exposure').oninput = () => { renderer.toneMappingExposure = parseFloat($('exposure').value); };
$('chkShadow').onchange = () => { key.castShadow = $('chkShadow').checked; };
$('chkGround').onchange = () => { ground.visible = $('chkGround').checked; };
$('chkWater').onchange = () => { water.visible = $('chkWater').checked; };
$('chkHair').onchange = () => { for (const m of hairMeshes) m.visible = $('chkHair').checked; };
$('chkWire').onchange = () => { for (const m of skinMeshes) for (const mm of (Array.isArray(m.material) ? m.material : [m.material])) mm.wireframe = $('chkWire').checked; };
let helper; $('chkBones').onchange = () => { if (!helper) { helper = new THREE.SkeletonHelper(model); helper.material.depthTest = false; helper.renderOrder = 10; scene.add(helper); } helper.visible = $('chkBones').checked; };
$('chkStaffLine').onchange = applyStaffLine; $('staffMode').onchange = mountStaff; $('chkAutoProps').onchange = () => { updateProps(); };
$('shading').onchange = () => {
  const mode = $('shading').value;
  for (const m of skinMeshes) {
    const orig = origMats.get(m);
    if (mode === 'pbr') m.material = orig;
    else if (mode === 'albedo') m.material = Array.isArray(orig) ? orig.map((o) => new THREE.MeshBasicMaterial({ map: o.map, alphaTest: o.alphaTest, side: o.side })) : new THREE.MeshBasicMaterial({ map: orig.map, alphaTest: orig.alphaTest, side: orig.side });
    else m.material = new THREE.MeshNormalMaterial({ side: THREE.DoubleSide });
  }
};

// playback controls
$('btnPause').onclick = () => { state.paused = !state.paused; $('btnPause').textContent = state.paused ? 'Play' : 'Pause'; };
$('btnRestart').onclick = () => { if (state.action) { state.action.reset(); state.action.play(); } };
$('btnReset').onclick = () => { travelPos.set(0, 0, 0); travelYaw = 0; state.yawBase = 0; };
const names = () => order.length ? order : Object.keys(CLIPS);
const step = (d) => { const n = names(); const i = n.indexOf(state.name); play(n[(i + d + n.length) % n.length]); };
$('btnNext').onclick = () => step(1); $('btnPrev').onclick = () => step(-1);
$('speed').oninput = () => { mixer.timeScale = parseFloat($('speed').value); if (cmp.mixer) cmp.mixer.timeScale = mixer.timeScale; $('speedOut').textContent = mixer.timeScale.toFixed(2) + '×'; };
$('fade').oninput = () => { $('fadeOut').textContent = parseFloat($('fade').value).toFixed(2) + ' s'; };
let scrubbing = false;
scrub.oninput = () => { scrubbing = true; if (state.action) { state.paused = true; $('btnPause').textContent = 'Play'; state.action.paused = false; state.action.time = parseFloat(scrub.value); } };
scrub.onchange = () => { scrubbing = false; };
window.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
  if (e.code === 'Space') { e.preventDefault(); $('btnPause').click(); }
  else if (e.key === 'ArrowRight') step(1); else if (e.key === 'ArrowLeft') step(-1);
  else if (e.key >= '1' && e.key <= '9') setCamera(parseInt(e.key) - 1);
  else if (e.key === 'w' || e.key === 'W') { $('chkWire').checked = !$('chkWire').checked; $('chkWire').onchange(); }
  else if (e.key === 's' || e.key === 'S') { $('chkBones').checked = !$('chkBones').checked; $('chkBones').onchange(); }
  else if (e.key === 'r' || e.key === 'R') { controls.autoRotate = !controls.autoRotate; $('chkSpin').checked = controls.autoRotate; }
});
$('chkSpin').onchange = () => { controls.autoRotate = $('chkSpin').checked; controls.autoRotateSpeed = 1.5; };

// ------------------------------------------------------------------ main loop
const clock = new THREE.Clock();
const tmp = new THREE.Vector3(), prevTarget = new THREE.Vector3();
function resize() { const w = window.innerWidth, h = window.innerHeight; renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); }
window.addEventListener('resize', resize); resize();

function travel(dt) {
  const r = state.rec; if (!r || !$('chkTravel').checked || state.paused || !state.action) return;
  const rm = r.root_motion; const ts = mixer.timeScale; const t = state.action.time;
  let v = 0, vy = 0;
  if (rm.type === 'in_place' && rm.reference_speed_m_s) v = rm.reference_speed_m_s * ts;
  else if (rm.type === 'path' && rm.speed_curve_m_s) {
    const i = Math.min(Math.floor(t * 30), rm.speed_curve_m_s.length - 1); v = rm.speed_curve_m_s[i] * ts;
    travelYaw = state.yawBase + THREE.MathUtils.degToRad(rm.yaw_curve_deg[i]);
  } else if (rm.type === 'vertical') vy = (rm.climb_speed_m_s || 0) * ts;
  travelPos.x += Math.sin(travelYaw) * v * dt; travelPos.z += Math.cos(travelYaw) * v * dt; travelPos.y += vy * dt;
  if (rm.type === 'vertical' && (travelPos.y > 4.2 || travelPos.y < -0.2)) travelPos.y = vy > 0 ? 0 : 4.0;
}
function frame() {
  const dt = Math.min(clock.getDelta(), 0.05);
  faceBefore();
  const r = state.rec;
  if (!state.paused) {
    mixer.update(dt);
    if (cmp.mixer && cmp.action) {
      cmp.mixer.update(dt);
      if ($('chkSync').checked && state.action) cmp.action.time = state.action.time % cmp.action.getClip().duration;
    }
  }
  faceAfter(state.paused ? 0 : dt);
  if (state.action && r) {
    const t = state.action.time;
    if (!scrubbing) scrub.value = t;
    $('timeOut').textContent = `${t.toFixed(2)} s`;
    // restart detection (a looping path clip or a repeating one-shot)
    if (t < state.lastT - 0.05) state.yawBase = travelYaw;
    state.lastT = t;
    if (!r.loop && $('chkRepeat').checked && !state.paused && t >= r.duration_s - 0.04) {
      state.repeatHold += dt; if (state.repeatHold > 0.6) { state.action.reset(); state.action.play(); state.repeatHold = 0; state.yawBase = travelYaw; if (r.root_motion.type === 'anchored') { travelPos.set(0, 0, 0); } }
    }
    updateAttached();
  }
  if (!state.paused) travel(dt);
  charGroup.position.set(cmp.group.visible ? -0.7 : travelPos.x, travelPos.y, cmp.group.visible ? 0 : travelPos.z);
  charGroup.rotation.y = cmp.group.visible ? 0 : travelYaw;
  ground.position.set(Math.round(charGroup.position.x / TILE) * TILE, 0, Math.round(charGroup.position.z / TILE) * TILE);
  water.position.x = ground.position.x; water.position.z = ground.position.z;
  key.target.position.copy(charGroup.position); key.position.copy(charGroup.position).add(new THREE.Vector3(...(LIGHTS[$('lighting').value] || LIGHTS.studio).pos));
  // camera follow
  if ($('chkFollow').checked) {
    const tgt = camTarget(CAMS[camIdx]); tmp.copy(tgt).sub(controls.target);
    const k = CAMS[camIdx][1] ? 0.35 : 1.0; tmp.multiplyScalar(k); controls.target.add(tmp); camera.position.add(tmp);
  }
  controls.update();
  renderer.render(scene, camera);
  requestAnimationFrame(frame);
}

// ------------------------------------------------------------------ start
buildList(); stats(); setLighting(params.get('light') || 'studio'); $('lighting').value = params.get('light') || 'studio';
$('loadstate').textContent = `${Object.keys(CLIPS).length} clips`;
const startClip = (location.hash.slice(1) && CLIPS[location.hash.slice(1)]) ? location.hash.slice(1) : (params.get('clip') || 'idle_relaxed');
await play(startClip, { instant: true, resetPos: true });
setCamera(parseInt(params.get('cam') || '0'));
if (params.has('t')) { state.paused = true; state.action.time = parseFloat(params.get('t')); mixer.update(0); }
requestAnimationFrame(frame);
window.viewerAPI = { play, setCamera, setLighting, setFace, state, mixer, model, THREE, camera, controls, ready: true, CLIPS, FACE };
document.body.dataset.ready = '1';
