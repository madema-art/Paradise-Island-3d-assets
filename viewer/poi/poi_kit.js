// Points of interest, redesigned for the FPS-neutral rule. Built at the origin (the game places them at TEMPLE / FAIRY).
//
// Rule of this kit: no more draw calls, lights or shadow casters than the game's builder used, and no more triangles unless
// the number is written down. Every POI is a few merged meshes:
//   temple:  stone (blocks, idol, torches, pillars, vines; one vertex-coloured material) + eyes (one emissive mesh)
//   glimmer: matte (stems and stones) + glow (mushroom caps, MeshBasic: lit by its own colour, no light cost)
// The walkable surfaces and colliders are the same formulas as the game (world.js / props.js), copied here so the visuals match them.
import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { mulberry32, noise3 } from '../canopy/canopy_kit.js';

const TAU = Math.PI * 2;
const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
const col = (hex) => new THREE.Color(hex);
const shade = (c, k) => new THREE.Color(c.r * k, c.g * k, c.b * k);

/* ---------------------------------------------------------------- geometry helpers */

// a primitive, turned and moved into place, with its own per-vertex colour and no uv (so every part merges)
function part(geo, x, y, z, { ry = 0, rx = 0, rz = 0, sx = 1, sy = 1, sz = 1, colourOf } = {}) {
  let g = geo.index ? geo.toNonIndexed() : geo;
  g.deleteAttribute('uv');
  g.scale(sx, sy, sz);
  g.rotateX(rx); g.rotateY(ry); g.rotateZ(rz);
  g.translate(x, y, z);
  const p = g.attributes.position, c = new Float32Array(p.count * 3), v = new THREE.Vector3();
  for (let i = 0; i < p.count; i++) {
    v.fromBufferAttribute(p, i);
    const k = colourOf ? colourOf(v) : null;
    c[i * 3] = k ? k.r : 1; c[i * 3 + 1] = k ? k.g : 1; c[i * 3 + 2] = k ? k.b : 1;
  }
  g.setAttribute('color', new THREE.BufferAttribute(c, 3));
  return g;
}

// move vertices by noise (keeps the top plane flat when horizontalOnly is set)
function jitter(geo, amt, seed, horizontalOnly = false) {
  const p = geo.attributes.position, v = new THREE.Vector3();
  for (let i = 0; i < p.count; i++) {
    v.fromBufferAttribute(p, i);
    const dx = amt * noise3(v.x * 0.9 + seed, v.y * 0.9, v.z * 0.9, 11);
    const dz = amt * noise3(v.x * 0.9, v.y * 0.9, v.z * 0.9 + seed, 12);
    const dy = horizontalOnly ? 0 : amt * 0.5 * noise3(v.x * 0.9, v.y * 0.9 + seed, v.z * 0.9, 13);
    p.setXYZ(i, v.x + dx, v.y + dy, v.z + dz);
  }
  geo.computeVertexNormals();
  return geo;
}

function merge(parts) {
  const g = mergeGeometries(parts, false);
  g.computeBoundingSphere();
  return g;
}

/* ---------------------------------------------------------------- the sunken temple */

// The game's stepped surface, copied from props.js buildTemple (local coordinates: the temple centre at 0, base at y 0).
export const TEMPLE_TIERS = 4, TIER_H = 1.75;
export const TEMPLE_TOP = TEMPLE_TIERS * TIER_H;
export function templeSurfaceY(dx, dz) {
  const ax = Math.abs(dx), az = Math.abs(dz);
  if (ax > 10 || az > 12) return null;
  let y = null;
  for (let i = 0; i < TEMPLE_TIERS; i++) { const hs = (19 - i * 4.2) / 2; if (ax < hs && az < hs) y = (i + 1) * TIER_H; }
  if (ax < 2.2 && dz > 3.2 && dz < 11.5) {
    const i = Math.min(TEMPLE_TIERS * 4 - 1, Math.max(0, Math.round((11.2 - dz) / 0.5)));
    y = Math.max(y ?? -1e9, (i + 1) * 0.44);
  }
  if (ax < 3.1 && az < 3.1) y = Math.max(y ?? -1e9, TEMPLE_TOP + 0.4);
  return y;
}

// The game's colliders: the pillars and the standing stones (positions are re-seeded here; the game port must keep its own stream).
export function buildTemple(seed = 7) {
  const rnd = mulberry32(seed);
  const rr = (a, b) => a + (b - a) * rnd();
  const stone = [col('#8a8a78'), col('#7c7d6c'), col('#6f7364')];
  const moss = col('#4d7f35'), vine = col('#2f6a2a'), wood = col('#5b3d24'), dark = col('#3b2a1c');
  const pick = (a) => a[Math.floor(rnd() * a.length)];
  const parts = [], eyes = [];
  const stoneOf = (base, topY, mossAmt) => (v) => {
    const k = 0.9 + 0.16 * noise3(v.x * 0.6, v.y * 0.6, v.z * 0.6, 4);
    const c = base.clone().multiplyScalar(k);
    if (v.y > topY - 0.5) c.lerp(moss, mossAmt * clamp(0.5 + noise3(v.x * 0.5, 0, v.z * 0.5, 6), 0, 1));
    return c;
  };
  const block = (w, h, d, x, y, z, ry, mossAmt = 0.4) => {
    const base = pick(stone);
    parts.push(part(jitter(new THREE.BoxGeometry(w, h, d), 0.12, x + z), x, y, z, { ry, colourOf: stoneOf(base, y + h / 2, mossAmt) }));
  };

  // tiers: four stepped blocks, the tops exactly where the game's surface expects them
  for (let i = 0; i < TEMPLE_TIERS; i++) {
    const s = 19 - i * 4.2;
    block(s, TIER_H, s, 0, TIER_H * 0.5 + i * TIER_H, 0, 0, 0.6);
  }
  // stairs on the south face: sixteen treads, and cheek walls either side
  for (let i = 0; i < TEMPLE_TIERS * 4; i++) {
    const h = (i + 1) * 0.44, z = 11.2 - i * 0.5;
    block(4.4, h, 0.6, 0, h * 0.5, z, 0, 0.3);
  }
  for (const sx of [-2.5, 2.5]) block(0.5, 1.8, 9.2, sx, 0.9, 7.6, 0, 0.5);
  // shrine on top: slab, four columns, a stepped roof
  block(6.2, 0.4, 6.2, 0, TEMPLE_TOP + 0.2, 0, 0, 0.5);
  for (const [cx, cz] of [[-2.5, -2.5], [2.5, -2.5], [-2.5, 2.5], [2.5, 2.5]]) block(0.8, 3.2, 0.8, cx, TEMPLE_TOP + 2.0, cz, 0, 0.2);
  block(6.6, 0.7, 6.6, 0, TEMPLE_TOP + 3.8, 0, 0, 0.8);
  block(4.8, 0.6, 4.8, 0, TEMPLE_TOP + 4.4, 0, 0, 0.9);
  block(2.0, 0.6, 2.0, 0, TEMPLE_TOP + 4.9, 0, 0, 0.9);
  block(5.2, 3.0, 0.6, 0, TEMPLE_TOP + 1.9, -2.7, 0, 0.2);

  // the idol on the shrine: a stone head, a brow, a nose, a mouth, a base and a crown (one stone colour, darker mouth)
  const iy = TEMPLE_TOP + 0.4, iz = -0.6, sc = 0.9;
  const idolStone = pick(stone);
  const idolCol = (v) => shade(idolStone, 0.95 + 0.1 * noise3(v.x, v.y, v.z, 8));
  const headG = jitter(new THREE.IcosahedronGeometry(1, 1), 0.06, 5);
  parts.push(part(headG, 0, iy + 1.6 * sc, iz, { sx: 1.35 * sc, sy: 1.62 * sc, sz: 1.28 * sc, colourOf: idolCol }));
  parts.push(part(new THREE.BoxGeometry(1, 1, 1), 0, iy + 2.15 * sc, iz + 0.9 * sc, { sx: 2.3 * sc, sy: 0.4 * sc, sz: 0.8 * sc, colourOf: idolCol }));
  parts.push(part(new THREE.BoxGeometry(1, 1, 1), 0, iy + 1.55 * sc, iz + 1.1 * sc, { sx: 0.5 * sc, sy: 0.9 * sc, sz: 0.7 * sc, colourOf: idolCol }));
  parts.push(part(new THREE.BoxGeometry(1, 1, 1), 0, iy + 0.95 * sc, iz + 1.05 * sc, { sx: 1.2 * sc, sy: 0.28 * sc, sz: 0.5 * sc, colourOf: () => dark }));
  parts.push(part(new THREE.BoxGeometry(1, 1, 1), 0, iy + 0.25 * sc, iz, { sx: 2.4 * sc, sy: 0.5 * sc, sz: 2.0 * sc, colourOf: idolCol }));
  parts.push(part(new THREE.ConeGeometry(1, 1, 5), 0, iy + 3.4 * sc, iz, { sx: 1.1 * sc, sy: 1.3 * sc, sz: 1.1 * sc, colourOf: idolCol }));
  // the eyes: the only emissive mesh, so they can pulse without touching the stone
  for (const ex of [-0.55, 0.55]) eyes.push(part(new THREE.SphereGeometry(0.18, 8, 6), ex * sc, iy + 1.95 * sc, iz + 1.18 * sc, { colourOf: () => col('#ffb040') }));

  // tiki torches on the plaza: pole and bowl, in the stone material (wood colour)
  for (const [tx, tz] of [[-3.6, 12], [3.6, 12], [-9, 6], [9, 6], [-8, -9], [8, -9]]) {
    parts.push(part(new THREE.CylinderGeometry(0.07, 0.1, 2.4, 6), tx, 1.2, tz, { colourOf: () => wood }));
    parts.push(part(new THREE.CylinderGeometry(0.25, 0.12, 0.3, 8), tx, 2.45, tz, { colourOf: () => dark }));
  }
  // plaza pillars: twelve around the court, half of them broken (positions are this kit's, not the game's)
  for (let i = 0; i < 12; i++) {
    const a = (i / 12) * TAU, r = 14.5 + rr(-1, 1);
    const px = Math.cos(a) * r, pz = Math.sin(a) * r;
    if (pz > 6 && Math.abs(px) < 4.5) continue;
    const broken = rnd() < 0.45;
    const h = broken ? rr(1.3, 3) : rr(4.6, 5.6);
    const base = pick(stone);
    parts.push(part(jitter(new THREE.CylinderGeometry(0.62, 0.72, h, 7, 1), 0.1, i), px, h * 0.5 - 0.2, pz, { colourOf: stoneOf(base, h, 0.35) }));
    if (!broken) parts.push(part(new THREE.BoxGeometry(1.5, 0.5, 1.5), px, h - 0.1, pz, { colourOf: () => shade(base, 1.05) }));
    else parts.push(part(new THREE.CylinderGeometry(0.6, 0.66, 2.4, 7, 1), px + 1.8, 0.55, pz + 1.2, { rz: Math.PI / 2 + 0.15, ry: rnd() * 3, colourOf: () => shade(base, 0.95) }));
  }
  // standing stones on the approach
  for (let i = 0; i < 5; i++) {
    const px = rr(-5, 5), pz = rr(16, 24), h = rr(1.8, 3);
    parts.push(part(jitter(new THREE.BoxGeometry(0.9, h, 0.5), 0.12, i), px, h * 0.5 - 0.1, pz, { ry: rr(-0.1, 0.1), colourOf: () => shade(pick(stone), 0.95) }));
  }
  // vines: thin hanging strips on the tier faces, from the top edge down
  for (let i = 0; i < 40; i++) {
    const t = Math.floor(rnd() * TEMPLE_TIERS), s = 19 - t * 4.2, half = s / 2 + 0.03;
    const y0 = (t + 1) * TIER_H - 0.1, L = rr(0.8, 2.6);
    const side = Math.floor(rnd() * 4), u = rr(-half * 0.8, half * 0.8);
    const [x, z, ry] = side === 0 ? [u, half, 0] : side === 1 ? [u, -half, 0] : side === 2 ? [half, u, Math.PI / 2] : [-half, u, Math.PI / 2];
    parts.push(part(new THREE.BoxGeometry(0.12, L, 0.04), x, y0 - L * 0.5, z, { ry, colourOf: () => vine }));
  }

  const stoneGeo = merge(parts);
  const eyeGeo = merge(eyes);
  return {
    stone: stoneGeo,           // one matte, vertex-coloured mesh
    eyes: eyeGeo,              // one emissive mesh
    lights: [{ color: 0xffa030, intensity: 50, distance: 22, decay: 2, position: [0, TEMPLE_TOP + 3.2, 2.2] }],
    counts: { draws: 2, lights: 1, shadowCasters: 1 },   // the stone mesh casts; the eyes do not
  };
}

/* ---------------------------------------------------------------- the glimmer ring */

// Mushrooms in a ring of twenty-two, nine inside and one great centre cap; seven standing stones on a circle of radius 8.4.
export function buildGlimmerRing(seed = 9) {
  const rnd = mulberry32(seed);
  const rr = (a, b) => a + (b - a) * rnd();
  const stemCol = col('#e8e2cf'), stoneCol = col('#6f7a68');
  const caps = [col('#4ff0e0'), col('#ff62d8'), col('#9a7bff'), col('#7dff6a')];
  const matte = [], glow = [];
  const mushroom = (x, z, s) => {
    const c = caps[Math.floor(rnd() * caps.length)].clone();
    matte.push(part(new THREE.CylinderGeometry(0.1 * s, 0.14 * s, 0.8 * s, 6), x, 0.4 * s, z, { colourOf: () => stemCol }));
    // the cap is brightest on top and darker at the rim, so it reads as a dome
    const dome = (v) => c.clone().multiplyScalar(0.5 + 0.5 * clamp(((v.y - 0.78 * s) / (0.5 * s * 0.75)) + 0.6, 0, 1));
    glow.push(part(new THREE.SphereGeometry(0.5 * s, 8, 5, 0, TAU, 0, Math.PI * 0.55), x, 0.78 * s, z, { sy: 0.75, colourOf: dome }));
  };
  for (let i = 0; i < 22; i++) {
    const a = (i / 22) * TAU + rr(-0.1, 0.1), r = 5.2 + rr(-0.6, 0.7);
    mushroom(Math.cos(a) * r, Math.sin(a) * r, rr(0.7, 1.5));
  }
  for (let i = 0; i < 9; i++) {
    const a = rnd() * TAU, r = rr(0, 3.2);
    mushroom(Math.cos(a) * r, Math.sin(a) * r, rr(0.5, 0.9));
  }
  mushroom(0, 0, 2.6);
  // seven standing stones, leaning in
  for (let i = 0; i < 7; i++) {
    const a = (i / 7) * TAU, r = 8.4;
    const h = rr(1.4, 2.4);
    matte.push(part(jitter(new THREE.BoxGeometry(0.8, h, 0.55), 0.1, i), Math.cos(a) * r, h * 0.5 - 0.1, Math.sin(a) * r,
      { rx: rr(-0.1, 0.1), ry: a + rr(-0.2, 0.2), rz: rr(-0.1, 0.1), colourOf: (v) => stoneCol.clone().multiplyScalar(0.9 + 0.2 * noise3(v.x, v.y, v.z, 3)) }));
  }
  return {
    matte: merge(matte),       // stems and stones: one matte mesh
    glow: merge(glow),         // caps: one MeshBasic mesh, lit by its own colour
    lights: [{ color: 0x58f0e8, intensity: 45, distance: 20, decay: 2, position: [0, 2.2, 0] }],
    counts: { draws: 2, lights: 1, shadowCasters: 1 },   // the stones cast; the caps and stems do not
  };
}

// Before, counted from the game's source (props.js, buildTemple and buildFairy). Used for the comparison table only.
// Triangles are ESTIMATES from the game's primitive parameters (box segments 2, cylinder 6-8 sides, sphere 10x6 to 10x8); the
// draw, light and shadow counts are exact from the source. Measure the real numbers with ?perf=1 before trusting the triangle column.
export const BEFORE = {
  temple: { draws: 21, lights: 1, shadowCasters: 15, trianglesEstimate: 2900, note: 'stone mesh, 8 idol meshes, 12 torch meshes (6 poles, 6 bowls); 6 torch bowls and poles cast shadows' },
  glimmer: { draws: 71, lights: 2, shadowCasters: 7, trianglesEstimate: 4400, note: '32 mushrooms in 2 meshes each (64), 7 stones; 2 point lights; 4 emissive materials updated every frame' },
};
