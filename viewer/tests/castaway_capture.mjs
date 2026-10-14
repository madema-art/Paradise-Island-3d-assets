// Headless capture/test of the castaway viewer page (software WebGL).
//   node viewer/tests/castaway_capture.mjs --query "clip=walk&cam=0" --out build/castaway/viewer_test/a.png --size 1600x900
//   [--eval "window.viewerAPI.play('wade')"] [--wait 1500] [--page castaway.html]
// Exits non-zero when the page logs errors.
import { chromium } from 'playwright-core';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const args = Object.fromEntries(process.argv.slice(2).reduce((a, v, i, arr) => (v.startsWith('--') ? [...a, [v.slice(2), arr[i + 1] && !arr[i + 1].startsWith('--') ? arr[i + 1] : '1']] : a), []));
const [W, H] = (args.size || '1600x900').split('x').map(Number);
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.glb': 'model/gltf-binary', '.wasm': 'application/wasm', '.png': 'image/png', '.jpg': 'image/jpeg' };
const root = path.resolve(ROOT, args.root || '.');
const server = http.createServer((req, res) => {
  const p = path.join(root, decodeURIComponent(req.url.split('?')[0]));
  if (!p.startsWith(root) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'Content-Type': MIME[path.extname(p)] || 'application/octet-stream' }); fs.createReadStream(p).pipe(res);
}).listen(0);
const browser = await chromium.launch({ executablePath: process.env.CHROME || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--enable-webgl'] });
const page = await browser.newPage({ viewport: { width: W, height: H } });
const errs = [];
page.on('console', (m) => { if (['error'].includes(m.type())) errs.push(m.text()); });
page.on('pageerror', (e) => errs.push('pageerror: ' + e.message));
const pg = args.page || (args.root ? 'index.html' : 'viewer/castaway.html');
await page.goto(`http://localhost:${server.address().port}/${pg}?capture=1&${args.query || ''}`);
await page.waitForFunction(() => document.body.dataset.ready === '1', null, { timeout: 180000 });
for (const ev of (args.eval || '').split('||').filter(Boolean)) { await page.evaluate(`(async()=>{${ev}})()`); await page.waitForTimeout(+(args.wait || 1200)); }
await page.waitForTimeout(+(args.wait || 1200));
const out = path.resolve(args.out || 'build/castaway/viewer_test/shot.png'); fs.mkdirSync(path.dirname(out), { recursive: true });
await page.screenshot({ path: out });
const info = await page.evaluate(() => ({ clip: window.viewerAPI?.state?.name, t: window.viewerAPI?.state?.action?.time }));
console.log(out, JSON.stringify(info));
const real = errs.filter((e) => !/404|PCFSoftShadowMap/.test(e));
if (real.length) { console.log('ERRORS:\n' + real.join('\n')); process.exitCode = 1; }
await browser.close(); server.close();
