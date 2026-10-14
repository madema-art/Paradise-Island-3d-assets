// Headless Three.js capture of the monkey viewer (software WebGL).
//   node viewer/tests/capture.mjs --clips walk,idle --times 0,0.5 --cam 3/4 --out build/monkey/threejs --size 640x480
// Requires: npm i playwright-core  (and a Chromium; set CHROME=/path/to/chrome if not at the default location)
import { chromium } from 'playwright-core';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const args = Object.fromEntries(process.argv.slice(2).reduce((a, v, i, arr) => (v.startsWith('--') ? [...a, [v.slice(2), arr[i + 1] && !arr[i + 1].startsWith('--') ? arr[i + 1] : '1']] : a), []));
const clips = (args.clips || 'idle').split(',');
const times = (args.times || '0').split(',').map(Number);
const cam = args.cam || '3/4';
const light = args.light || 'studio';
const shading = args.shading || 'pbr';
const out = path.resolve(args.out || 'build/monkey/threejs');
const [W, H] = (args.size || '640x480').split('x').map(Number);
const CHROME = process.env.CHROME || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
fs.mkdirSync(out, { recursive: true });

const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.glb': 'model/gltf-binary', '.png': 'image/png', '.jpg': 'image/jpeg' };
const server = http.createServer((req, res) => {
  const p = path.join(ROOT, decodeURIComponent(req.url.split('?')[0]));
  if (!p.startsWith(ROOT) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'Content-Type': MIME[path.extname(p)] || 'application/octet-stream' });
  fs.createReadStream(p).pipe(res);
}).listen(0);
const port = server.address().port;

const browser = await chromium.launch({ executablePath: CHROME, args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--enable-webgl'] });
const page = await browser.newPage({ viewport: { width: W, height: H } });
const errors = [];
page.on('console', (m) => { if (['error', 'warning'].includes(m.type())) errors.push(`[${m.type()}] ${m.text()}`); });
page.on('pageerror', (e) => errors.push(`[pageerror] ${e.message}`));
const t0 = Date.now();
await page.goto(`http://localhost:${port}/viewer/index.html?ui=0&capture=1&light=${light}`);
await page.waitForFunction(() => document.body.dataset.ready === '1' || document.body.dataset.error, null, { timeout: 180000 });
const err = await page.evaluate(() => document.body.dataset.error);
if (err) { console.error('LOAD ERROR:', err); await browser.close(); server.close(); process.exit(2); }
console.log(`loaded in ${((Date.now() - t0) / 1000).toFixed(1)} s`);
const info = await page.evaluate(() => ({ clips: window.viewer.clips.length, tris: 0 }));
console.log('clips available:', info.clips);
if (shading !== 'pbr') await page.evaluate((s) => window.viewer.shading(s), shading);
for (const c of clips) {
  for (const t of times) {
    await page.evaluate(([n, tt, cm]) => window.viewer.at(n, tt, cm), [c, t, cam]);
    const file = path.join(out, `${c}_${cam.replace('/', '')}_${String(t).replace('.', 'p')}.png`);
    await page.screenshot({ path: file });
    console.log('saved', file);
  }
}
if (errors.length) console.log('console messages:\n' + [...new Set(errors)].slice(0, 12).join('\n'));
await browser.close(); server.close();
