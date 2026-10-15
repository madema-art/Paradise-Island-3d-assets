// Each pose on a fresh page load (settled). The sun's compass turn comes from PHI on the scratch build (window.__SUN_PHI).
// With sun_turn.patch applied, the game uses its own SUN_TURN constant: leave PHI unset.
// A pose may set fov; the opening itself uses 50 through the game's setFov.
// Each pose on a fresh page load, so the renderer's state (vegetation LOD, shadows) does not depend on earlier poses.
import { chromium } from 'playwright-core';
import fs from 'node:fs';
const OUT = process.env.OUT || 'build/start_view';
fs.mkdirSync(OUT, { recursive: true });
const PHI = Number(process.env.PHI ?? 0);
const POSES = JSON.parse(process.env.POSES || '[]');
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome', args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--no-sandbox'] });
for (const p of POSES) {
  const page = await browser.newPage({ viewport: { width: 960, height: 540 } });
  await page.addInitScript((phi) => { window.__SUN_PHI = phi; }, PHI);
  await page.goto('http://127.0.0.1:5190/index.html', { waitUntil: 'load', timeout: 180000 });
  await page.waitForFunction(() => window.__dbg && window.__dbg.falls && window.__dbg.falls.camp, null, { timeout: 240000 });
  await page.evaluate((p) => { const d = window.__dbg; d.env.speed = 0; d.env.tod = p.tod; window.__goto(p.pos, p.tgt); }, p);
  await new Promise((r) => setTimeout(r, Number(process.env.SETTLE ?? 9000)));
  if (p.fov) { await page.evaluate((f) => { const d = window.__dbg; d.camera.fov = f; d.camera.updateProjectionMatrix(); }, p.fov); await new Promise((r) => setTimeout(r, 6000)); }
  const m = await page.evaluate(() => {
    const d = window.__dbg;
    d.renderer.info.autoReset = false; d.renderer.info.reset();
    d.renderer.render(d.scene, d.camera);
    const r = { calls: d.renderer.info.render.calls, tris: d.renderer.info.render.triangles };
    d.renderer.info.autoReset = true;
    return r;
  });
  await page.screenshot({ path: `${OUT}/${p.name}.png`, timeout: 240000 });
  console.log(JSON.stringify({ name: p.name, ...m }));
  await page.close();
}
await browser.close();
