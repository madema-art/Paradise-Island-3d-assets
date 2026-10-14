// Headless Three.js screenshots of a GLB (no viewer UI):  node shot.mjs --model assets/castaway/Castaway.glb --out build/x
//   --views "face:0,1.9,0.6,0,1.88,0;body:..."   (camera x,y,z,target x,y,z in three.js coordinates, character faces +Z)
//   [--clip name --t 0.5] [--light studio|sun|dark] [--size 800x800] [--ground 0] [--sheet out.png --cols 3]
import { chromium } from 'playwright-core';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const args = Object.fromEntries(process.argv.slice(2).reduce((a, v, i, arr) => (v.startsWith('--') ? [...a, [v.slice(2), arr[i + 1] && !arr[i + 1].startsWith('--') ? arr[i + 1] : '1']] : a), []));
const [W, H] = (args.size || '800x800').split('x').map(Number);
const out = path.resolve(args.out || 'build/shots'); fs.mkdirSync(out, { recursive: true });
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json', '.glb': 'model/gltf-binary', '.png': 'image/png', '.jpg': 'image/jpeg' };
const server = http.createServer((req, res) => {
  const p = path.join(ROOT, decodeURIComponent(req.url.split('?')[0]));
  if (!p.startsWith(ROOT) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'Content-Type': MIME[path.extname(p)] || 'application/octet-stream' }); fs.createReadStream(p).pipe(res);
}).listen(0);
const browser = await chromium.launch({ executablePath: process.env.CHROME || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--enable-webgl'] });
const page = await browser.newPage({ viewport: { width: W, height: H } });
const errs = []; page.on('console', (m) => { if (['error', 'warning'].includes(m.type())) errs.push(m.text()); }); page.on('pageerror', (e) => errs.push(e.message));
const qs = new URLSearchParams({ model: '/' + args.model, w: W, h: H, light: args.light || 'studio', ground: args.ground ?? '1', fov: args.fov || '30' });
if (args.extra) qs.set('extra', args.extra.split(',').map((e) => '/' + e).join(','));
await page.goto(`http://localhost:${server.address().port}/viewer/tests/shot.html?${qs}`);
await page.waitForFunction(() => document.body.dataset.ready === '1' || document.body.dataset.error, null, { timeout: 120000 });
const err = await page.evaluate(() => document.body.dataset.error); if (err) { console.error('LOAD ERROR', err); process.exit(2); }
const files = [];
const times = args.times ? args.times.split(',').map(Number) : [+(args.t || 0)];
for (const [ti, t] of times.entries()) {
  if (args.clip) await page.evaluate(([c, tt]) => window.shot.pose(c, tt), [args.clip, t]);
  for (const spec of (args.views || '').split(';').filter(Boolean)) {
    const [name, vals] = spec.split(':'); const v = vals.split(',').map(Number);
    await page.evaluate((v) => window.shot.view(v), v);
    const f = path.join(out, times.length > 1 ? `${name}_${String(ti).padStart(2, '0')}.png` : `${name}.png`); await page.screenshot({ path: f }); files.push(f);
  }
}
console.log(files.join('\n'));
if (errs.length) console.log('console:', [...new Set(errs)].slice(0, 8).join(' | '));
await browser.close(); server.close();
