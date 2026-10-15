// Lagoon coral, redesigned for the FPS-neutral rule.
//
// The game draws each coral kind as ONE InstancedMesh (flora.js, flora2.js), so draw calls are already low. The cost is triangles:
// the instanced mesh is culled per mesh, so every coral head is drawn whenever any of them is in view. From the game's parameters, a
// reef head averages about 140 triangles (900 heads, about 126,000) and a south-seas head about 322 (520 heads, about 168,000).
//
// legacyGeometry(kind) rebuilds the game's coral (coralGeo / coralTable / coralCauli) from the same primitives, flat shaded, so its
// triangle counts follow the game's parameters (the game's rnd()-driven shape jitter is left out; it does not change the counts).
// newCoral(kind) is the redesign: fewer, smoother triangles, scalloped rims and ridges, one vertex-colour gradient, and the same five kinds.
import * as THREE from 'three';
import { mergeGeometries, mergeVertices } from 'three/addons/utils/BufferGeometryUtils.js';
import { mulberry32, noise3 } from '../canopy/canopy_kit.js';

const TAU = Math.PI * 2;
const clamp = (x, a, b) => Math.min(b, Math.max(a, x));

/* ---------------------------------------------------------------- the game's coral, rebuilt from the same primitives (flat shaded, as in the game) */

// The game's tubes (rings x sides, no caps), the same icosphere and fan primitives, and the same cylinder stems. Counts follow the
// parameters: a tube of R rings and S sides has (R - 1) x S x 2 triangles. Shape jitter is left out (it does not change the counts).
function legacyTubeGeo(centres, radii, seg) {
  const rings = centres.map((c, i) => {
    const a = centres[Math.max(0, i - 1)], b = centres[Math.min(centres.length - 1, i + 1)];
    const T = b.clone().sub(a).normalize();
    const U = new THREE.Vector3().crossVectors(T, new THREE.Vector3(0, 0, 1)).normalize();
    if (U.lengthSq() < 0.01) U.set(1, 0, 0);
    const V = new THREE.Vector3().crossVectors(T, U).normalize();
    const out = [];
    for (let j = 0; j < seg; j++) {
      const t = (j / seg) * TAU;
      out.push(c.clone().addScaledVector(U, Math.cos(t) * radii[i]).addScaledVector(V, Math.sin(t) * radii[i]));
    }
    return out;
  });
  const pos = [];
  for (let i = 0; i < rings.length - 1; i++) {
    for (let j = 0; j < seg; j++) {
      const j2 = (j + 1) % seg;
      const a = rings[i][j], b = rings[i][j2], c = rings[i + 1][j2], d = rings[i + 1][j];
      pos.push(a.x, a.y, a.z, d.x, d.y, d.z, b.x, b.y, b.z, b.x, b.y, b.z, d.x, d.y, d.z, c.x, c.y, c.z);
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  return g;
}

// table coral's disc, as the game builds it: sixteen segments, two bands (an inner band from the centre, an outer band to the rim),
// two triangles per band per segment. The inner band's first triangle is degenerate (both inner points are the centre), as in the game.
function legacyDiscGeo(R, y) {
  const pos = [];
  const pt = (r, i, yy) => { const a = (i / 16) * TAU; return [Math.cos(a) * r, yy, Math.sin(a) * r]; };
  const put = (...p) => pos.push(...p.flat());
  for (let i = 0; i < 16; i++) {
    const C = [0, y, 0];
    const p0 = pt(0, i, y + 0.02), p1 = pt(0, i + 1, y + 0.02);       // the centre
    const q0 = pt(R * 0.55, i, y + 0.02), q1 = pt(R * 0.55, i + 1, y + 0.02);
    const r0 = pt(R, i, y - 0.02), r1 = pt(R, i + 1, y - 0.02);
    put(p0, q0, p1, p1, q0, q1);                                       // inner band
    put(q0, r0, q1, q1, r0, r1);                                       // outer band
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  return g;
}

export function legacyGeometry(kind) {
  const parts = [];
  if (kind === 0) {
    for (let b = 0; b < 5; b++) {
      const a = (b / 5) * TAU, tilt = 0.35, h = 0.42;
      const cen = [new THREE.Vector3(), new THREE.Vector3(Math.cos(a) * tilt * h * 0.4, h * 0.5, Math.sin(a) * tilt * h * 0.4),
        new THREE.Vector3(Math.cos(a) * tilt * h, h, Math.sin(a) * tilt * h)];
      parts.push(legacyTubeGeo(cen, [0.06, 0.04, 0.012], 6));
      for (let t = 0; t < 2; t++) {
        const s = cen[1].clone().lerp(cen[2], 0.5);
        const tip = s.clone().add(new THREE.Vector3(Math.cos(a) * 0.14, 0.15, Math.sin(a) * 0.14));
        parts.push(legacyTubeGeo([s, tip], [0.03, 0.01], 5));
      }
    }
  } else if (kind === 1) {
    parts.push(new THREE.IcosahedronGeometry(1, 2).scale(0.26, 0.17, 0.26).translate(0, 0.12, 0));
  } else if (kind === 2) {
    parts.push(new THREE.CircleGeometry(0.22, 10, 0, Math.PI), new THREE.CircleGeometry(0.22, 10, 0, Math.PI).rotateY(1.57));
  } else if (kind === 'table') {
    parts.push(new THREE.CylinderGeometry(0.05, 0.08, 0.28, 6).translate(0, 0.14, 0), legacyDiscGeo(0.45, 0.28));
  } else if (kind === 'cauli') {
    for (let c = 0; c < 12; c++) {
      const a = (c / 12) * TAU, r = 0.14;
      parts.push(new THREE.IcosahedronGeometry(0.1, 1).translate(Math.cos(a) * r, 0.11, Math.sin(a) * r));
    }
  } else throw new Error('unknown coral kind ' + kind);
  // flat per-face normals, as the game's MB.build gives (non-indexed)
  const flat = parts.map((g) => (g.index ? g.toNonIndexed() : g));
  for (const g of flat) { g.deleteAttribute('uv'); g.deleteAttribute('normal'); }
  const merged = mergeGeometries(flat, false);
  merged.computeVertexNormals();
  // the game's MB colours every vertex: white, shaded by height (flat, 0.75 to 1.1)
  merged.computeBoundingBox();
  const bb = merged.boundingBox, h = Math.max(1e-6, bb.max.y - bb.min.y), p = merged.attributes.position;
  const c = new Float32Array(p.count * 3);
  for (let i = 0; i < p.count; i++) {
    const k = 0.75 + 0.35 * clamp((p.getY(i) - bb.min.y) / h, 0, 1);
    c.set([k, k, k], i * 3);
  }
  merged.setAttribute('color', new THREE.BufferAttribute(c, 3));
  return merged;
}

export function legacyTriangles(kind) {
  return triangles(legacyGeometry(kind));
}

/* ---------------------------------------------------------------- the redesign: smooth, lighter, one vertex-colour gradient */

// the geometries are welded (so their normals are smooth) and coloured by height: darker at the base, lighter at the tips
function finish(geo, seed) {
  geo.deleteAttribute('uv');
  geo.deleteAttribute('normal');                                       // so vertices with the same position weld
  const welded = mergeVertices(geo, 1e-4);
  welded.computeVertexNormals();
  welded.computeBoundingBox();
  const bb = welded.boundingBox, h = Math.max(1e-6, bb.max.y - bb.min.y);
  const p = welded.attributes.position, c = new Float32Array(p.count * 3), v = new THREE.Vector3();
  const base = new THREE.Color('#e9dcd8'), tip = new THREE.Color('#ffffff');
  for (let i = 0; i < p.count; i++) {
    v.fromBufferAttribute(p, i);
    const t = clamp((v.y - bb.min.y) / h, 0, 1);
    const k = 0.92 + 0.12 * noise3(v.x * 3 + seed, v.y * 3, v.z * 3, 7);
    const col = base.clone().lerp(tip, t).multiplyScalar(k);
    c.set([col.r, col.g, col.b], i * 3);
  }
  welded.setAttribute('color', new THREE.BufferAttribute(c, 3));
  return welded;
}

// push each vertex in or out along its radius by noise of its angle: scalloped rims and ruffled plates, no extra triangles
function scallop(geo, amt, seed) {
  const p = geo.attributes.position, v = new THREE.Vector3();
  for (let i = 0; i < p.count; i++) {
    v.fromBufferAttribute(p, i);
    const r = Math.hypot(v.x, v.z);
    if (r < 1e-4) continue;
    const a = Math.atan2(v.z, v.x);
    const k = 1 + amt * noise3(Math.cos(a) * 2.2 + seed, v.y * 4, Math.sin(a) * 2.2, 9) * (r > 0.2 ? 1 : 0.5);                 // the centre moves less than the rim
    p.setXYZ(i, v.x * k, v.y, v.z * k);
  }
  geo.computeVertexNormals();
  return geo;
}

function jitterSphere(detail, amt, seed, radii = [1, 1, 1]) {
  const g = new THREE.IcosahedronGeometry(1, detail);
  const p = g.attributes.position, v = new THREE.Vector3();
  for (let i = 0; i < p.count; i++) {
    v.fromBufferAttribute(p, i);
    const n = 1 + amt * noise3(v.x * 2 + seed, v.y * 2, v.z * 2, 3);
    p.setXYZ(i, v.x * n * radii[0], v.y * n * radii[1], v.z * n * radii[2]);
  }
  return g;
}

export function newCoral(kind, seed = 1) {
  const rnd = mulberry32(seed * 911 + 5);
  if (kind === 0) {
    // branching: three thick branches, each with one twig; sixty-odd triangles
    const parts = [];
    for (let b = 0; b < 3; b++) {
      const a = (b / 3) * TAU + rnd() * 0.5, h = 0.42 + rnd() * 0.1;
      const cen = [new THREE.Vector3(), new THREE.Vector3(Math.cos(a) * 0.12, h * 0.5, Math.sin(a) * 0.12), new THREE.Vector3(Math.cos(a) * 0.22, h, Math.sin(a) * 0.22)];
      parts.push(tubeGeo(cen, [0.06, 0.042, 0.016], 5));
      const s = cen[1].clone().lerp(cen[2], 0.6);
      const tip = s.clone().add(new THREE.Vector3(Math.cos(a + 0.8) * 0.12, 0.13, Math.sin(a + 0.8) * 0.12));
      parts.push(tubeGeo([s, tip], [0.03, 0.01], 4));
    }
    return finish(mergeGeometries(parts.map((g) => g.toNonIndexed()), false), seed);
  }
  if (kind === 1) {
    // massive: a dome with soft ridges, detail 1 (80 faces) instead of 320
    // ridges: a higher-frequency noise on the same detail-1 sphere (80 triangles)
    const g = jitterSphere(1, 0.18, seed, [0.26, 0.17, 0.26]);
    return finish(g.translate(0, 0.12, 0), seed);
  }
  if (kind === 2) {
    // plate: two crossed fans of eight segments
    const f = new THREE.CircleGeometry(0.22, 8, 0, Math.PI);
    const a = scallop(f.clone(), 0.14, seed), b = scallop(f.clone(), 0.14, seed + 3).rotateY(1.57);
    return finish(mergeGeometries([a, b].map((g) => g.toNonIndexed()), false).translate(0, 0.02, 0), seed);
  }
  if (kind === 'table') {
    // table coral: a short stem and a flat disc with a raised rim, about 14 segments
    const stem = new THREE.CylinderGeometry(0.06, 0.09, 0.26, 6, 1).translate(0, 0.13, 0);
    const disc = scallop(new THREE.CylinderGeometry(0.4, 0.46, 0.06, 12, 1, false), 0.12, seed).translate(0, 0.29, 0);
    return finish(mergeGeometries([stem, disc].map((g) => g.toNonIndexed()), false), seed);
  }
  // cauliflower: four lumpy icospheres of detail 0 in a small cluster
  const parts = [];
  for (let i = 0; i < 4; i++) {
    const g = jitterSphere(0, 0.35, seed * 13 + i, [0.12, 0.12, 0.12]);
    const a = rnd() * TAU, r = rnd() * 0.13;
    parts.push(g.translate(Math.cos(a) * r, 0.11 + (i % 2) * 0.05, Math.sin(a) * r));
  }
  return finish(mergeGeometries(parts.map((g) => g.toNonIndexed()), false), seed);
}

// a tapered tube (indexed), like the game's tube but with indexed positions so the result welds cleanly
function tubeGeo(centres, radii, seg) {
  const rings = centres.map((c, i) => {
    const a = centres[Math.max(0, i - 1)], b = centres[Math.min(centres.length - 1, i + 1)];
    const T = b.clone().sub(a).normalize();
    const U = new THREE.Vector3().crossVectors(T, new THREE.Vector3(0, 0, 1)).normalize();
    if (U.lengthSq() < 0.01) U.set(1, 0, 0);
    const V = new THREE.Vector3().crossVectors(T, U).normalize();
    const out = [];
    for (let j = 0; j < seg; j++) {
      const t = (j / seg) * TAU;
      out.push(c.clone().addScaledVector(U, Math.cos(t) * radii[i]).addScaledVector(V, Math.sin(t) * radii[i]));
    }
    return out;
  });
  const pos = [], idx = [];
  const add = (v) => { pos.push(v.x, v.y, v.z); return pos.length / 3 - 1; };
  const ids = rings.map((ring) => ring.map(add));
  for (let i = 0; i < rings.length - 1; i++) {
    for (let j = 0; j < seg; j++) {
      const j2 = (j + 1) % seg;
      idx.push(ids[i][j], ids[i + 1][j], ids[i][j2], ids[i][j2], ids[i + 1][j], ids[i + 1][j2]);
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setIndex(idx);
  return g;
}

export function triangles(geo) {
  return (geo.index ? geo.index.count : geo.attributes.position.count) / 3;
}

export const KINDS = [0, 1, 2, 'table', 'cauli'];
// the game's mix in the south seas (weights from flora2.js) and its reef split (even thirds of three kinds)
export const SOUTH_SEAS_WEIGHTS = { table: 0.3, 0: 0.27, cauli: 0.22, 1: 0.13, 2: 0.08 };
