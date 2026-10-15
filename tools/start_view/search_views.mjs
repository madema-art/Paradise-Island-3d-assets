import { chromium } from 'playwright-core';
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome', args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--no-sandbox'] });
const page = await browser.newPage({ viewport: { width: 960, height: 540 } });
await page.goto('' + (process.env.GAME_URL || 'http://127.0.0.1:5190/index.html') + '', { waitUntil: 'load', timeout: 180000 });
await page.waitForFunction(() => window.__dbg && window.__dbg.falls && window.__dbg.falls.camp, null, { timeout: 240000 });
await new Promise((r) => setTimeout(r, 2000));
const res = await page.evaluate(() => {
  const W = window.__dbg.WORLD, d = window.__dbg;
  const h = (x, z) => W.getHeight(x, z);
  // sun direction in the game: a = (tod-6)/24*2pi, dir = normalize(cos a, sin a, 0.28)
  const sunDir = (tod) => { const a = ((tod - 6) / 24) * Math.PI * 2; const v = [Math.cos(a), Math.sin(a), 0.28]; const n = Math.hypot(...v); return v.map((c) => c / n); };
  const elevOf = (s) => Math.asin(s[1]) * 180 / Math.PI;
  // highest terrain angle (deg) seen from eye (ex,ey,ez) along the horizontal azimuth of direction (dx,dz)
  const horizon = (ex, ey, ez, dx, dz) => {
    const L = Math.hypot(dx, dz); dx /= L; dz /= L;
    let best = -90;
    for (let t = 15; t <= 900; t += 6) {
      const x = ex + dx * t, z = ez + dz * t, y = h(x, z);
      const e = Math.atan2(y - ey, t) * 180 / Math.PI;
      if (e > best) best = e;
    }
    return best;
  };
  const camp = d.falls.camp;
  const dawnS = sunDir(6.0), duskS = sunDir(18.0);
  const isWater = (x, z) => h(x, z) < -0.3;
  // OPENING: sea points west of the island; sun rising from the east must be hidden behind the island at first
  const opening = [];
  for (let x = -260; x <= -40; x += 14) for (let z = -20; z <= 200; z += 14) {
    if (!isWater(x, z)) continue;
    for (const eyeH of [30, 60]) {
      const ey = Math.max(eyeH, 0) + Math.max(0, h(x, z));
      const hz = horizon(x, ey, z, dawnS[0], dawnS[2]);     // terrain elevation toward the dawn sun from the eye
      const toCamp = Math.hypot(camp.x - x, camp.z - z);
      if (toCamp < 120 || toCamp > 320) continue;
      // the camp should be roughly in front (the sun behind it, so the camera looks at the island with the sun beyond it)
      const ang = Math.acos(((camp.x - x) * dawnS[0] + (camp.z - z) * dawnS[2]) / toCamp / Math.hypot(dawnS[0], dawnS[2])) * 180 / Math.PI;
      opening.push({ x, z, eyeH, ey: +ey.toFixed(1), toCamp: +toCamp.toFixed(0), horizonToDawnSunDeg: +hz.toFixed(2), sunAngleFromCampDeg: +(180 - ang).toFixed(1) });
    }
  }
  // score: the island blocks the rising sun only slightly (horizon elevation near 0 to 3 degrees), and the sun is roughly behind the camp
  const good = opening.filter((o) => o.horizonToDawnSunDeg > -6 && o.horizonToDawnSunDeg < 3 && o.sunAngleFromCampDeg > 150).sort((a, b) => Math.abs(a.horizonToDawnSunDeg - 1) - Math.abs(b.horizonToDawnSunDeg - 1));
  // SUNSET from the lagoon: lagoon water near the cove, the sun setting in the west must have an open horizon
  const lagoon = [];
  for (let x = 0; x <= 80; x += 6) for (let z = 80; z <= 150; z += 6) {
    if (!isWater(x, z)) continue;
    for (const eyeH of [1.5, 3]) {
      const ey = h(x, z) + eyeH;
      const hz = horizon(x, ey, z, duskS[0], duskS[2]);
      lagoon.push({ x, z, eyeH, horizonToSunsetDeg: +hz.toFixed(2) });
    }
  }
  const lagoonOpen = lagoon.filter((o) => o.horizonToSunsetDeg < 0.5).sort((a, b) => a.horizonToSunsetDeg - b.horizonToSunsetDeg);
  return {
    camp: [camp.x, camp.z], dawnSunElevDeg: +elevOf(dawnS).toFixed(2), duskSunElevDeg: +elevOf(duskS).toFixed(2),
    openingCount: opening.length, openingHorizonRange: [Math.min(...opening.map(o=>o.horizonToDawnSunDeg)).toFixed(2), Math.max(...opening.map(o=>o.horizonToDawnSunDeg)).toFixed(2)], openingSunAngleRange: [Math.min(...opening.map(o=>o.sunAngleFromCampDeg)), Math.max(...opening.map(o=>o.sunAngleFromCampDeg))], openingSample: opening.filter((o)=>o.sunAngleFromCampDeg>150).slice(0,12), openingGood: good.slice(0, 12), lagoonCount: lagoon.length, lagoonOpen: lagoonOpen.slice(0, 4),
    waterSampleDepths: [[40, 116], [20, 110], [30, 125]].map(([x, z]) => [x, z, +h(x, z).toFixed(2)]),
  };
});
console.log(JSON.stringify(res, null, 1));
await browser.close();
