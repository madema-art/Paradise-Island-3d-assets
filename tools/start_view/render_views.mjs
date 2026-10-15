import { chromium } from 'playwright-core';
import fs from 'node:fs';
const OUT = process.env.OUT || 'build/start_view';
fs.mkdirSync(OUT, { recursive: true });
const POSES = JSON.parse(process.env.POSES || '[]');
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome', args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--no-sandbox'] });
const page = await browser.newPage({ viewport: { width: 960, height: 540 } });
await page.goto('' + (process.env.GAME_URL || 'http://127.0.0.1:5190/index.html') + '', { waitUntil: 'load', timeout: 180000 });
await page.waitForFunction(() => window.__dbg && window.__dbg.falls && window.__dbg.falls.camp, null, { timeout: 240000 });
await new Promise((r) => setTimeout(r, 2500));
const results = [];
for (const p of POSES) {
  await page.evaluate((p) => { const d = window.__dbg; d.env.speed = 0; d.env.tod = p.tod; window.__goto(p.pos, p.tgt); }, p);
  await new Promise((r) => setTimeout(r, 4000));
  const m = await page.evaluate(() => {
    const d = window.__dbg;
    d.renderer.info.autoReset = false; d.renderer.info.reset();
    d.renderer.render(d.scene, d.camera);
    const r = { calls: d.renderer.info.render.calls, tris: d.renderer.info.render.triangles, cam: d.camera.position.toArray().map((v) => +v.toFixed(1)), tod: d.env.tod };
    d.renderer.info.autoReset = true;
    return r;
  });
  await page.screenshot({ path: `${OUT}/${p.name}.png`, timeout: 240000 });
  results.push({ name: p.name, ...m });
  console.log(JSON.stringify({ name: p.name, ...m }));
}
await browser.close();
