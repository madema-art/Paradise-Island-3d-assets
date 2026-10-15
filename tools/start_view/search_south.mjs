// Searches the sea south of the island for the opening (horizon toward the rising sun) and the lagoon sunset (open horizon).
// PHI is the experiment hook used on the scratch build (window.__SUN_PHI); with the sun_turn.patch applied, leave it unset.
import { chromium } from 'playwright-core';
const PHI = Number(process.env.PHI ?? -Math.PI / 2);
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome', args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--no-sandbox'] });
const page = await browser.newPage({ viewport: { width: 960, height: 540 } });
await page.addInitScript((phi) => { window.__SUN_PHI = phi; }, PHI);
await page.goto((process.env.GAME_URL || 'http://127.0.0.1:5190/index.html'), { waitUntil: 'load', timeout: 180000 });
await page.waitForFunction(() => window.__dbg && window.__dbg.falls && window.__dbg.falls.camp, null, { timeout: 240000 });
await new Promise((r) => setTimeout(r, 1500));
const res = await page.evaluate((PHI) => {
  const W = window.__dbg.WORLD, d = window.__dbg;
  const h = (x, z) => W.getHeight(x, z);
  const sunAt = (tod) => { const a = ((tod - 6) / 24) * Math.PI * 2; const c = Math.cos(PHI), s = Math.sin(PHI); const x = Math.cos(a), z = 0.28; return [x * c - z * s, Math.sin(a), x * s + z * c]; };
  const horizon = (ex, ey, ez, dx, dz) => {
    const L = Math.hypot(dx, dz); dx /= L; dz /= L; let best = -90;
    for (let t = 15; t <= 900; t += 6) { const e = Math.atan2(h(ex + dx * t, ez + dz * t) - ey, t) * 180 / Math.PI; if (e > best) best = e; }
    return best;
  };
  const sr = sunAt(6.0), ss = sunAt(18.0);
  const out = { PHI_deg: +(PHI * 180 / Math.PI).toFixed(1), sunriseDir: sr.map((v) => +v.toFixed(2)), sunsetDir: ss.map((v) => +v.toFixed(2)) };
  // OPENING candidates in the sea south of the island, looking north: the island (horizon) blocks the rising sun a little
  const open = [];
  for (let x = -120; x <= 120; x += 12) for (let z = 170; z <= 320; z += 12) {
    if (h(x, z) > -0.3) continue;
    for (const eyeH of [20, 35, 60]) {
      const ey = eyeH;
      const hz = horizon(x, ey, z, sr[0], sr[2]);
      open.push({ x, z, eyeH, horizonToSunriseDeg: +hz.toFixed(2) });
    }
  }
  out.openCount = open.length;
  out.openNearIsland = open.filter((o) => o.horizonToSunriseDeg > -4 && o.horizonToSunriseDeg < 3).sort((a, b) => Math.hypot(a.x - 0, a.z - 240) - Math.hypot(b.x - 0, b.z - 240)).slice(0, 12);
  // SUNSET candidates in the lagoon (cove water) looking south
  const lag = [];
  for (let x = 0; x <= 80; x += 6) for (let z = 80; z <= 170; z += 6) {
    if (h(x, z) > -0.3) continue;
    for (const eyeH of [1.5, 3]) lag.push({ x, z, eyeH, horizonToSunsetDeg: +horizon(x, h(x, z) + eyeH, z, ss[0], ss[2]).toFixed(2) });
  }
  out.lagoonOpen = lag.filter((o) => o.horizonToSunsetDeg < 0.5).sort((a, b) => a.horizonToSunsetDeg - b.horizonToSunsetDeg).slice(0, 8);
  out.lagoonCount = lag.length;
  return out;
}, PHI);
console.log(JSON.stringify(res, null, 1));
await browser.close();
