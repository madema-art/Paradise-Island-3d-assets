// Broadleaf tree canopy: the current game style (a stand-in for treeB's crown) and a new leaf-clump canopy.
// Both return ONE BufferGeometry per tree with vertex colours and an aWind attribute, as the game's MB builder does, so each tree stays
// one draw call. Pure geometry, no scene: the comparison page (canopy.js) and the workshop build use the same functions.
import * as THREE from 'three';

/* ---------------------------------------------------------------- seeded random and noise */

export function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function hash3(x, y, z, s) {
  const h = Math.sin(x * 127.1 + y * 311.7 + z * 74.7 + s * 19.19) * 43758.5453;
  return h - Math.floor(h);
}

// smooth value noise in [-1, 1]
export function noise3(x, y, z, s = 0) {
  const xi = Math.floor(x), yi = Math.floor(y), zi = Math.floor(z);
  const xf = x - xi, yf = y - yi, zf = z - zi;
  const u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf), w = zf * zf * (3 - 2 * zf);
  const l = (a, b, t) => a + (b - a) * t;
  const n = (dx, dy, dz) => hash3(xi + dx, yi + dy, zi + dz, s);
  const x0 = l(n(0, 0, 0), n(1, 0, 0), u), x1 = l(n(0, 1, 0), n(1, 1, 0), u);
  const x2 = l(n(0, 0, 1), n(1, 0, 1), u), x3 = l(n(0, 1, 1), n(1, 1, 1), u);
  return l(l(x0, x1, v), l(x2, x3, v), w) * 2 - 1;
}

const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
const shadeCol = (c, k) => new THREE.Color(c.r * k, c.g * k, c.b * k);

/* ---------------------------------------------------------------- mesh accumulator (same shape as the game's MB) */

class Acc {
  constructor() { this.pos = []; this.col = []; this.wind = []; }
  vert(p, c, w) { this.pos.push(p.x, p.y, p.z); this.col.push(c.r, c.g, c.b); this.wind.push(w); }
  tri(a, b, c, ca, cb = ca, cc = ca, wa = 0, wb = wa, wc = wa) {
    this.vert(a, ca, wa); this.vert(b, cb, wb); this.vert(c, cc, wc);
  }
  // an icosphere (detail 1, 80 faces) pushed by noise, scaled and turned, with a colour function of the final position
  blob(rc, sy, centre, rot, amp, seed, colourOf, wind, detail = 1) {
    const g = new THREE.IcosahedronGeometry(1, detail);
    const p = g.attributes.position, v = new THREE.Vector3();
    const cs = Math.cos(rot), sn = Math.sin(rot);
    const pts = [];
    for (let i = 0; i < p.count; i++) {
      v.fromBufferAttribute(p, i);
      const n = 1 + amp * noise3(v.x * 1.7 + seed, v.y * 1.7, v.z * 1.3 - seed, 3);
      v.multiplyScalar(n);
      const x = v.x * cs - v.z * sn, z = v.x * sn + v.z * cs;   // turn about y
      pts.push(new THREE.Vector3(centre.x + x * rc, centre.y + v.y * rc * sy, centre.z + z * rc));
    }
    for (let i = 0; i < pts.length; i += 3) {
      const a = pts[i], b = pts[i + 1], c = pts[i + 2];
      const ca = colourOf(a), cb = colourOf(b), cc = colourOf(c);
      this.tri(a, b, c, ca, cb, cc, wind, wind, wind);
    }
    g.dispose();
  }
  // a folded leaf fin: base on the clump rim, pointing out and down
  blade(base, dir, len, width, down, colBase, colTip, wind) {
    const side = new THREE.Vector3().crossVectors(dir, new THREE.Vector3(0, 1, 0)).normalize();
    const bl = base.clone().addScaledVector(side, -width * 0.5);
    const br = base.clone().addScaledVector(side, width * 0.5);
    const mid = base.clone().addScaledVector(dir, len * 0.5).add(new THREE.Vector3(0, -down * 0.5, 0));
    const tip = base.clone().addScaledVector(dir, len).add(new THREE.Vector3(0, -down, 0));
    const cm = colBase.clone().lerp(colTip, 0.5);
    this.tri(bl, mid, tip, colBase, cm, colTip, wind, wind, wind);
    this.tri(mid, br, tip, cm, colBase, colTip, wind, wind, wind);
  }
  // Smooth normals: the triangles stay as they are, but each vertex gets the area-weighted average of the faces that share its position.
  // (computeVertexNormals on non-indexed geometry gives one flat normal per face, which is what makes a crown read as faceted.)
  geometry(smooth = true) {
    const g = new THREE.BufferGeometry();
    if (!smooth) {                                                    // the game's MB.build: flat normals per face
      g.setAttribute('position', new THREE.Float32BufferAttribute(this.pos, 3));
      g.setAttribute('color', new THREE.Float32BufferAttribute(this.col, 3));
      g.setAttribute('aWind', new THREE.Float32BufferAttribute(this.wind, 1));
      g.computeVertexNormals();
      return g;
    }
    const n = this.pos.length / 3;
    const key = (i) => `${Math.round(this.pos[3 * i] * 1e4)},${Math.round(this.pos[3 * i + 1] * 1e4)},${Math.round(this.pos[3 * i + 2] * 1e4)}`;
    const sum = new Map();
    for (let t = 0; t < n; t += 3) {
      const a = new THREE.Vector3(this.pos[3 * t], this.pos[3 * t + 1], this.pos[3 * t + 2]);
      const b = new THREE.Vector3(this.pos[3 * t + 3], this.pos[3 * t + 4], this.pos[3 * t + 5]);
      const c = new THREE.Vector3(this.pos[3 * t + 6], this.pos[3 * t + 7], this.pos[3 * t + 8]);
      const fn = new THREE.Vector3().subVectors(b, a).cross(new THREE.Vector3().subVectors(c, a));   // length = 2 x area
      for (let j = 0; j < 3; j++) {
        const k = key(t + j);
        const s = sum.get(k) || new THREE.Vector3();
        sum.set(k, s.add(fn));
      }
    }
    const normals = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) {
      const s = sum.get(key(i)).normalize();
      normals[3 * i] = s.x; normals[3 * i + 1] = s.y; normals[3 * i + 2] = s.z;
    }
    g.setAttribute('position', new THREE.Float32BufferAttribute(this.pos, 3));
    g.setAttribute('normal', new THREE.Float32BufferAttribute(normals, 3));
    g.setAttribute('color', new THREE.Float32BufferAttribute(this.col, 3));
    g.setAttribute('aWind', new THREE.Float32BufferAttribute(this.wind, 1));
    return g;
  }
}

/* ---------------------------------------------------------------- trunk (shared by both variants, so the comparison is the crown only) */

export function trunkGeometry(H) {
  const g = new THREE.CylinderGeometry(0.42, 0.7, H, 7, 1, false);
  g.translate(0, H / 2, 0);
  g.setAttribute('aWind', new THREE.Float32BufferAttribute(new Float32Array(g.attributes.position.count), 1));
  g.setAttribute('color', new THREE.Float32BufferAttribute(new Float32Array(g.attributes.position.count * 3).fill(0.42), 3));
  for (let i = 0; i < g.attributes.position.count; i++) {
    const y = g.attributes.position.getY(i);
    g.attributes.color.setXYZ(i, 0.36 + 0.06 * (y / H), 0.29 + 0.04 * (y / H), 0.22 + 0.03 * (y / H));
  }
  return g;
}

/* ---------------------------------------------------------------- the current game style, reproduced */

const GREENS_OLD = ['#1f6a2e', '#2a7a34', '#1c5c2c', '#34883a'].map((h) => new THREE.Color(h));

// treeB's crown: seven smooth icosphere lobes (detail 1, noise 0.3), each scaled (R, 0.55R, R), shaded by height only.
export function currentCanopy(seed = 1, { Rc = 6.2, H = 8.0 } = {}) {
  const rnd = mulberry32(seed);
  const acc = new Acc();
  const top = new THREE.Vector3(0, H, 0);
  for (let i = 0; i < 7; i++) {
    const a = (i / 7) * Math.PI * 2 + rnd();
    const r0 = i === 0 ? 0 : 0.6 * Rc + rnd() * 0.3 * Rc;
    const c = new THREE.Vector3(top.x + Math.cos(a) * r0, top.y + (rnd() * 2.6 - 1.2) * 0.2 * Rc, top.z + Math.sin(a) * r0);
    const R = (0.68 + rnd() * 0.32) * Rc;
    const base = GREENS_OLD[Math.floor(rnd() * GREENS_OLD.length)];
    const colourOf = (v) => shadeCol(base, 0.78 + 0.4 * clamp(((v.y - c.y) / R) * 0.9 + 0.5, 0, 1));
    acc.blob(R, 0.55, c, rnd() * 6.28, 0.3, i * 1.7, colourOf, 0.9);
  }
  return acc.geometry(false);
}

/* ---------------------------------------------------------------- the new canopy: leaf clumps with fins, shaded for depth */

const LEAF = {
  deep: new THREE.Color('#163f1c'),
  mid: new THREE.Color('#2a6a2a'),
  bright: new THREE.Color('#3f8a36'),
  lime: new THREE.Color('#9cc24c'),
  gap: new THREE.Color('#0f2c14'),
};

// Clumps sit on a domed shell with ragged gaps, each a noisy icosphere with a ring of leaf fins at its rim. Shading is in the colours:
// the underside and the inside of the crown are dark, the sunlit tops and fin tips warm and lime, each clump has its own value.
export function newCanopy(seed = 1, { Rc = 6.2, H = 8.0, lod = 0 } = {}) {
  const rnd = mulberry32(seed * 7919 + 17);
  const acc = new Acc();
  const centre = new THREE.Vector3(0, H, 0);
  const nClump = lod === 0 ? 34 : 12;
  const golden = Math.PI * (3 - Math.sqrt(5));

  // ambient-occlusion-like shading from the shell position and the normal direction (inner and lower parts darker)
  const shadeAt = (p, base, nrm) => {
    const dx = p.x - centre.x, dz = p.z - centre.z;
    const inner = clamp(Math.hypot(dx, dz) / Rc, 0, 1);            // 0 at the trunk, 1 at the rim
    const up = clamp(nrm.y * 0.5 + 0.5, 0, 1);
    const ao = (0.7 + 0.3 * up) * (0.82 + 0.18 * inner);
    const mottle = 0.9 + 0.16 * noise3(p.x * 1.9, p.y * 1.9, p.z * 1.9, 5);
    const c = base.clone().multiplyScalar(ao * mottle);
    c.lerp(LEAF.lime, clamp((nrm.y - 0.55) * 0.9, 0, 0.35));        // sun on the top of the crown
    return c;
  };

  const clumps = [];
  for (let i = 0; i < nClump; i++) {
    const f = Math.sqrt((i + 0.5) / nClump);                        // radial fraction, even spread over the disc
    const a = i * golden + rnd() * 0.4;
    const dome = 0.55 * (1 - f * f) - 0.1;
    const c = new THREE.Vector3(
      Math.cos(a) * f * Rc * 0.92,
      centre.y + dome * Rc + (rnd() - 0.5) * 0.35 * Rc,
      Math.sin(a) * f * Rc * 0.92,
    );
    const rc = Rc * (0.25 + 0.09 * rnd()) * (1.0 - 0.3 * f);
    clumps.push({ c, rc, a, f });
  }
  clumps.sort((p, q) => p.c.y - q.c.y);                              // lower clumps first (no effect on shading, keeps the order stable)

  for (const k of clumps) {
    const base = [LEAF.deep, LEAF.mid, LEAF.bright][Math.floor(rnd() * 3)].clone();
    base.multiplyScalar(0.9 + 0.2 * rnd());                           // value variation per clump
    const colourOf = (v) => {
      const n = v.clone().sub(k.c).normalize();                      // approximate normal of the lobe at this point
      return shadeAt(v, base, n);
    };
    // inner clumps are mostly hidden: a coarse sphere there, detail on the rim the eye sees
    const detail = lod === 0 && k.f > 0.7 ? 1 : 0;
    acc.blob(k.rc, 0.7, k.c, rnd() * 6.28, detail ? 0.36 : 0.3, k.a * 3.1, colourOf, 0.6, detail);
  }
  if (lod === 0) {                                                    // a few dark hanging clumps under the belly break up the flat bottom
    for (let i = 0; i < 6; i++) {
      const a = rnd() * Math.PI * 2, f = 0.55 + 0.4 * rnd();
      const c = new THREE.Vector3(Math.cos(a) * f * Rc * 0.8, centre.y - 0.25 * Rc + rnd() * 0.2 * Rc, Math.sin(a) * f * Rc * 0.8);
      const rc = Rc * (0.14 + 0.05 * rnd());
      acc.blob(rc, 0.8, c, rnd() * 6.28, 0.3, 40 + i, (v) => LEAF.gap.clone().lerp(LEAF.deep, clamp((v.y - c.y) / rc + 0.5, 0, 1)), 0.7, 0);
    }
  }
  return acc.geometry();
}

export function triangleCount(geometry) {
  return (geometry.index ? geometry.index.count : geometry.attributes.position.count) / 3;
}
