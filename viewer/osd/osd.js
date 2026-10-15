// Interface prototype: a simpler on-screen display and menu, driven from a controller or the keyboard.
// Two modes. PLAY (menu closed): the sticks look and move, left and right cycle creatures, LB and RB cycle the camera views,
// Start opens the menu. MENU (opened with Start or M): the same buttons move through the menu, Start or B closes it.
// The creatures are stand-ins (coloured capsules), so this page tests the controls and the layout, not the animals.
import * as THREE from 'three';
import { cycleFocus, speciesOf, viewOrder } from './cycle.js';

/* ---------------------------------------------------------------- scene and stand-in creatures */

const canvas = document.getElementById('stage');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x9fd3e0);
scene.fog = new THREE.Fog(0x9fd3e0, 90, 220);
const camera = new THREE.PerspectiveCamera(55, 1, 0.1, 400);
scene.add(new THREE.HemisphereLight(0xeaffff, 0x4b6b3a, 1.4));
const sun = new THREE.DirectionalLight(0xfff1d6, 2.2);
sun.position.set(-20, 40, 20);
scene.add(sun);
const ground = new THREE.Mesh(new THREE.CircleGeometry(120, 48), new THREE.MeshStandardMaterial({ color: 0x6b8a4a, roughness: 1 }));
ground.rotation.x = -Math.PI / 2;
scene.add(ground);

// name, category, how many, and a colour for the stand-in
const SPECIES = [
  ['Capuchin monkey', 'Mammals', 3, 0xb08a5a],
  ['Red beach crab', 'Shore life', 3, 0xd9553a],
  ['Bottlenose dolphin', 'Sea life', 2, 0x7fb6d9],
  ['Great frigatebird', 'Birds', 2, 0x2d3a4a],
  ['Greater flamingo', 'Birds', 1, 0xff8fb1],
  ['Pacific boa', 'Reptiles', 1, 0x7a8f3a],
  ['Castaway', 'People', 1, 0xf2d0a4],
];

const creatures = [];
let seed = 7;
const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
for (const [name, cat, count, color] of SPECIES) {
  for (let n = 1; n <= count; n++) {
    const g = new THREE.Group();
    const body = new THREE.Mesh(new THREE.CapsuleGeometry(0.45, 0.9, 4, 8), new THREE.MeshStandardMaterial({ color, roughness: 0.8 }));
    body.position.y = 0.9;
    g.add(body);
    const pos = [(rnd() - 0.5) * 60, 0, (rnd() - 0.5) * 60];
    g.position.set(...pos);
    scene.add(g);
    creatures.push({ id: `${name.toLowerCase().replace(/\s+/g, '-')}-${n}`, name, cat, n, pos, group: g, desc: `${name}, individual ${n}.` });
  }
}
const halo = new THREE.Mesh(new THREE.RingGeometry(1.1, 1.3, 32), new THREE.MeshBasicMaterial({ color: 0xffe08a, side: THREE.DoubleSide, transparent: true, opacity: 0.9 }));
halo.rotation.x = -Math.PI / 2;
halo.visible = false;
scene.add(halo);

/* ---------------------------------------------------------------- state */

const state = {
  menu: false,
  focus: null,                 // the followed creature
  section: 0,                  // menu section index
  item: 0,                     // menu item index inside the section
  view: 1,                     // camera view for LB and RB (0 wide, 1 close, 2 top)
  yaw: 0.6, pitch: 0.35, dist: 9,
  settings: { orbit: false, fov: 56, quality: 2, shadows: true, bloom: true, music: true, musicVol: 0.5, sfxVol: 0.85 },
};
const VIEWS = [
  { name: 'Wide', dist: 22, pitch: 0.55 },
  { name: 'Close', dist: 6.5, pitch: 0.22 },
  { name: 'Top', dist: 26, pitch: 1.35 },
];

/* ---------------------------------------------------------------- the menu: one tree, read by the pad and the keyboard */

const guideItems = () => {
  const cats = ['People', 'Mammals', 'Birds', 'Reptiles', 'Sea life', 'Shore life'];
  const out = [];
  for (const cat of cats) {
    const names = [...new Set(creatures.filter((c) => c.cat === cat).map((c) => c.name))];
    if (!names.length) continue;
    out.push({ type: 'head', label: cat });
    for (const name of names) out.push({ type: 'species', label: name, count: speciesOf(creatures, name).length, name });
  }
  return out;
};
const menuSections = () => [
  { title: 'View', items: [
    { type: 'action', label: 'Wide view', run: () => setView(0) },
    { type: 'action', label: 'Close view', run: () => setView(1) },
    { type: 'action', label: 'Top view', run: () => setView(2) },
    { type: 'toggle', label: 'Slow auto-orbit', key: 'orbit' },
    { type: 'slider', label: 'Field of view', key: 'fov', min: 20, max: 90, step: 2 },
  ] },
  { title: 'World', items: [
    { type: 'choice', label: 'Quality', key: 'quality', options: ['Low', 'Medium', 'High'] },
    { type: 'toggle', label: 'Shadows', key: 'shadows' },
    { type: 'toggle', label: 'Bloom glow', key: 'bloom' },
  ] },
  { title: 'Sound', items: [
    { type: 'toggle', label: 'Music', key: 'music' },
    { type: 'slider', label: 'Music volume', key: 'musicVol', min: 0, max: 1, step: 0.05 },
    { type: 'slider', label: 'Effects volume', key: 'sfxVol', min: 0, max: 1, step: 0.05 },
  ] },
  { title: 'Guide', items: guideItems() },
  { title: 'Journal', items: [{ type: 'info', label: 'Secrets found', value: '0 of 3' }] },
];
let sections = menuSections();

function setView(i) {
  state.view = i;
  const v = VIEWS[i];
  state.dist = v.dist;
  state.pitch = v.pitch;
}

function followCreature(c) {
  state.focus = c;
  halo.visible = !!c;
  if (c) {
    const species = speciesOf(creatures, c.name);
    if (species.length > 1) state.dist = Math.max(6.5, state.dist);
  }
}

// one activation of the highlighted item (A on the pad, Enter on the keyboard)
function activate() {
  const sec = sections[state.section];
  const it = sec.items[state.item];
  if (!it) return;
  if (it.type === 'action') it.run();
  else if (it.type === 'toggle') state.settings[it.key] = !state.settings[it.key];
  else if (it.type === 'species') {
    const list = speciesOf(creatures, it.name);
    const best = list.slice().sort((a, b) => dist2cam(a) - dist2cam(b))[0];
    followCreature(best);
    setMenu(false);
  }
}

// left or right on the highlighted item: change a slider or a choice
function adjust(dir) {
  const it = sections[state.section].items[state.item];
  if (!it) return;
  if (it.type === 'slider') {
    // snap to steps counted from the minimum, so 20, 22, 24 ... and not the other way round
    const steps = Math.round((state.settings[it.key] - it.min) / it.step) + dir;
    state.settings[it.key] = Math.min(it.max, Math.max(it.min, it.min + steps * it.step));
  } else if (it.type === 'choice') {
    const n = it.options.length;
    state.settings[it.key] = (state.settings[it.key] + dir + n) % n;
  }
}

function moveItem(dir) {
  const items = sections[state.section].items;
  if (!items.length) return;
  let i = state.item;
  for (let k = 0; k < items.length; k++) {
    i = (i + dir + items.length) % items.length;
    if (items[i].type !== 'head') break;
  }
  state.item = i;
}

function moveSection(dir) {
  state.section = (state.section + dir + sections.length) % sections.length;
  state.item = 0;
  if (sections[state.section].items[0]?.type === 'head') moveItem(1);
}

function setMenu(open) {
  state.menu = open;
  document.body.dataset.mode = open ? 'menu' : 'play';
  if (open) { sections = menuSections(); state.item = 0; if (sections[state.section].items[0]?.type === 'head') moveItem(1); }
  renderMenu();
  renderHints();
}

const dist2cam = (c) => Math.hypot(c.pos[0] - camera.position.x, c.pos[1] - camera.position.y, c.pos[2] - camera.position.z);

/* ---------------------------------------------------------------- the display: two small boxes in play, one menu box when open */

const elFocus = document.getElementById('focus');
const elHint = document.getElementById('hint');
const elMenu = document.getElementById('menu');
let lastFocusText = '';
function renderFocus() {
  const c = state.focus;
  let meta = '';
  if (c) {
    const species = speciesOf(creatures, c.name);
    meta = c.cat + (species.length > 1 ? ` · ${species.indexOf(c) + 1} of ${species.length}` : '');
  }
  const text = c ? `${c.name}|${meta}` : '';
  if (text === lastFocusText) return;               // only touch the DOM when the text changes
  lastFocusText = text;
  elFocus.hidden = !c;
  elFocus.querySelector('.name').textContent = c ? c.name : '';
  elFocus.querySelector('.meta').textContent = meta;
}
let lastHint = '';
function renderHints() {
  const text = state.menu
    ? '▲▼ move · ◀▶ change · LB RB section · A select · B close'
    : '◀▶ creature · LB RB view · Y nearest · B let go · Start menu';
  if (text === lastHint) return;
  lastHint = text;
  elHint.textContent = text;
}
function renderMenu() {
  elMenu.hidden = !state.menu;
  if (!state.menu) return;
  const tabs = sections.map((s, i) => `<button class="tab${i === state.section ? ' on' : ''}" data-s="${i}">${s.title}</button>`).join('');
  const sec = sections[state.section];
  const rows = sec.items.map((it, i) => {
    const on = i === state.item ? ' on' : '';
    if (it.type === 'head') return `<div class="head">${it.label}</div>`;
    let right = '';
    if (it.type === 'toggle') right = `<span class="val ${state.settings[it.key] ? 'yes' : 'no'}">${state.settings[it.key] ? 'On' : 'Off'}</span>`;
    if (it.type === 'slider') right = `<span class="val">${Math.round(state.settings[it.key] * (it.max <= 1 ? 100 : 1))}${it.max <= 1 ? '%' : ''}</span>`;
    if (it.type === 'choice') right = `<span class="val">${it.options[state.settings[it.key]]}</span>`;
    if (it.type === 'species') right = `<span class="val">${it.count > 1 ? '×' + it.count : ''}</span>`;
    if (it.type === 'info') right = `<span class="val">${it.value}</span>`;
    return `<div class="row${on}">${it.label}${right}</div>`;
  }).join('');
  elMenu.innerHTML = `<div class="tabs">${tabs}</div><div class="rows">${rows}</div>`;
}

/* ---------------------------------------------------------------- controller (standard layout) and keyboard */

const BTN = { A: 0, B: 1, X: 2, Y: 3, LB: 4, RB: 5, BACK: 8, START: 9, UP: 12, DOWN: 13, LEFT: 14, RIGHT: 15 };
let prev = new Array(17).fill(false);
function pollPad() {
  const list = navigator.getGamepads ? navigator.getGamepads() : [];
  const gp = list && [...list].find((p) => p && p.connected);
  if (!gp) { prev.fill(false); return null; }
  const pressed = [];
  for (let i = 0; i < 17; i++) {
    const down = !!(gp.buttons[i] && gp.buttons[i].pressed);
    pressed[i] = down && !prev[i];
    prev[i] = down;
  }
  return { pressed, lx: gp.axes[0] || 0, rx: gp.axes[2] || 0, ry: gp.axes[3] || 0 };
}

function press(action) {
  if (action === 'menu') { setMenu(!state.menu); return; }
  if (state.menu) {
    if (action === 'up') moveItem(-1);
    else if (action === 'down') moveItem(1);
    else if (action === 'left') adjust(-1);
    else if (action === 'right') adjust(1);
    else if (action === 'lb') moveSection(-1);
    else if (action === 'rb') moveSection(1);
    else if (action === 'a') activate();
    else if (action === 'b') setMenu(false);
  } else {
    if (action === 'left' || action === 'right') {
      const next = cycleFocus(creatures, state.focus, action === 'right' ? 1 : -1, [camera.position.x, camera.position.y, camera.position.z]);
      if (next) followCreature(next);
    } else if (action === 'lb' || action === 'rb') {
      setView((state.view + (action === 'rb' ? 1 : -1) + VIEWS.length) % VIEWS.length);
    } else if (action === 'y') {
      const near = viewOrder(creatures).slice().sort((a, b) => dist2cam(a) - dist2cam(b))[0];
      followCreature(near);
    } else if (action === 'b') followCreature(null);
  }
  renderFocus();
  renderMenu();
}

const PAD_MAP = [[BTN.A, 'a'], [BTN.B, 'b'], [BTN.Y, 'y'], [BTN.LB, 'lb'], [BTN.RB, 'rb'], [BTN.START, 'menu'], [BTN.UP, 'up'], [BTN.DOWN, 'down'], [BTN.LEFT, 'left'], [BTN.RIGHT, 'right']];
const KEY_MAP = { Enter: 'a', Backspace: 'b', KeyY: 'y', KeyQ: 'lb', KeyE: 'rb', KeyM: 'menu', Escape: 'menu', ArrowUp: 'up', ArrowDown: 'down', ArrowLeft: 'left', ArrowRight: 'right' };
window.addEventListener('keydown', (e) => {
  const a = KEY_MAP[e.code];
  if (!a) return;
  e.preventDefault();
  press(a);
});
elMenu.addEventListener('click', (e) => {
  const t = e.target.closest('.tab');
  if (t) { state.section = +t.dataset.s; state.item = 0; renderMenu(); }
});

/* ---------------------------------------------------------------- camera: follow the focus, orbit with the right stick or a drag */

let dragging = null;
canvas.addEventListener('pointerdown', (e) => { dragging = { x: e.clientX, y: e.clientY }; });
addEventListener('pointerup', () => { dragging = null; });
addEventListener('pointermove', (e) => {
  if (!dragging) return;
  state.yaw -= (e.clientX - dragging.x) * 0.006;
  state.pitch = Math.min(1.45, Math.max(-0.2, state.pitch + (e.clientY - dragging.y) * 0.004));
  dragging = { x: e.clientX, y: e.clientY };
});

const target = new THREE.Vector3();
function updateCamera(dt, pad) {
  if (pad && !state.menu) {
    state.yaw -= pad.rx * dt * 2.2;
    state.pitch = Math.min(1.45, Math.max(-0.2, state.pitch - pad.ry * dt * 1.2));
  }
  if (state.settings.orbit && !state.menu) state.yaw += dt * 0.12;
  camera.fov = state.settings.fov;
  camera.updateProjectionMatrix();
  if (state.focus) target.lerp(new THREE.Vector3(...state.focus.pos).setY(1.2), Math.min(1, dt * 4));
  else target.lerp(new THREE.Vector3(0, 1, 0), Math.min(1, dt * 2));
  const off = new THREE.Vector3(Math.sin(state.yaw) * Math.cos(state.pitch), Math.sin(state.pitch), Math.cos(state.yaw) * Math.cos(state.pitch)).multiplyScalar(state.dist);
  camera.position.copy(target).add(off);
  camera.lookAt(target);
  halo.position.set(target.x, 0.05, target.z);
  if (state.focus) halo.position.set(state.focus.pos[0], 0.05, state.focus.pos[2]);
}

/* ---------------------------------------------------------------- loop */

function resize() {
  const w = canvas.clientWidth, h = canvas.clientHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}
addEventListener('resize', resize);
let last = performance.now();
function frame(now) {
  const dt = Math.min((now - last) / 1000, 0.1);
  last = now;
  const pad = pollPad();
  if (pad) {
    const map = PAD_MAP.filter(([i]) => pad.pressed[i]);
    for (const [, a] of map) press(a);
  }
  updateCamera(dt, pad);
  renderer.render(scene, camera);
  requestAnimationFrame(frame);
}

// state for the tests and the handoff (read-only)
Object.defineProperty(window, '__osd', { get: () => ({ mode: state.menu ? 'menu' : 'play', focus: state.focus && state.focus.id, section: sections[state.section].title, view: VIEWS[state.view].name, settings: state.settings, visibleBoxes: [elFocus, elHint, elMenu].filter((e) => !e.hidden).length, backdropFilterBoxes: [elFocus, elHint, elMenu].filter((e) => getComputedStyle(e).backdropFilter !== 'none').length }) });

resize();
setMenu(false);
renderFocus();
renderHints();
requestAnimationFrame(frame);
