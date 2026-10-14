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
const metaPath = path.join(ROOT, 'assets/monkey/monkey_clips.json');
const meta = fs.existsSync(metaPath) ? JSON.parse(fs.readFileSync(metaPath, 'utf8')) : {};
const clips = (args.clips === 'all' ? Object.keys(meta) : (args.clips || 'idle').split(','));
const phases = args.phases ? Number(args.phases) : 0;
const camFor = (c) => (args.cam && args.cam !== 'auto' ? args.cam : ({ climbing: 'Climb' }[meta[c]?.group] || (meta[c]?.pair ? 'Pair' : '3/4')));
const times = (args.times || '0').split(',').map(Number);
const light = args.light || 'studio';
const extra = args.query ? '&' + args.query : '';
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
await page.goto(`http://localhost:${port}/viewer/index.html?ui=0&capture=1&light=${light}${extra}`);
await page.waitForFunction(() => document.body.dataset.ready === '1' || document.body.dataset.error, null, { timeout: 180000 });
const err = await page.evaluate(() => document.body.dataset.error);
if (err) { console.error('LOAD ERROR:', err); await browser.close(); server.close(); process.exit(2); }
console.log(`loaded in ${((Date.now() - t0) / 1000).toFixed(1)} s`);
const info = await page.evaluate(() => ({ clips: window.viewer.clips.length, tris: 0 }));
console.log('clips available:', info.clips);
if (shading !== 'pbr') await page.evaluate((s) => window.viewer.shading(s), shading);
if (args.turntable) {
  const n = Number(args.turntable), c = clips[0], dur = meta[c]?.seconds || 1;
  const dist = Number(args.dist || 1.5), height = Number(args.height || 0.42);
  for (let i = 0; i < n; i++) {
    await page.evaluate(([nm, tt, a, d, h]) => { window.viewer.at(nm, tt); window.viewer.orbit(a, d, h); }, [c, (dur * i / n) % dur, 360 * i / n + Number(args.start || 20), dist, height]);
    await page.screenshot({ path: path.join(out, `turn_${String(i).padStart(3, '0')}.png`) });
  }
  console.log('turntable frames', n);
  await browser.close(); server.close(); process.exit(0);
}
for (const c of clips) {
  const cam = camFor(c);
  const dur = meta[c]?.seconds || 1;
  const ts = phases ? Array.from({ length: phases }, (_, i) => +(dur * i / phases).toFixed(3)) : times;
  for (const [i, t] of ts.entries()) {
    await page.evaluate(([n, tt, cm]) => window.viewer.at(n, tt, cm), [c, t, cam]);
    if (args.camera) {
      const v = args.camera.split(',').map(Number);
      await page.evaluate((v) => { const w = window.viewer; w.camera.position.set(v[0], v[1], v[2]); w.controls.target.set(v[3], v[4], v[5]); w.controls.update(); w.renderer.render(w.scene, w.camera); }, v);
    }
    if (args.focus) {   // --focus bone,azimuthDeg,distance,elevationDeg[,dx,dy,dz]  (azimuth 0 = in front of the monkey, +Z)
      const f = args.focus.split(',');
      await page.evaluate(([bone, az, dist, el, off]) => {
        const w = window.viewer, T = w.THREE; let b = null;
        w.scene.traverse((o) => { if (!b && o.isBone && o.name === bone) b = o; });
        const p = new T.Vector3(); (b || w.scene).getWorldPosition(p); p.x += off[0]; p.y += off[1]; p.z += off[2];
        const a = T.MathUtils.degToRad(az), e = T.MathUtils.degToRad(el);
        w.camera.position.set(p.x + Math.sin(a) * Math.cos(e) * dist, p.y + Math.sin(e) * dist, p.z + Math.cos(a) * Math.cos(e) * dist);
        w.controls.target.copy(p); w.controls.update(); w.renderer.render(w.scene, w.camera);
      }, [f[0], Number(f[1] || 0), Number(f[2] || 0.5), Number(f[3] || 10), [Number(f[4] || 0), Number(f[5] || 0), Number(f[6] || 0)]]);
    }
    const file = path.join(out, phases ? `${c}__${String(i).padStart(2, '0')}.png` : `${c}_${cam.replace('/', '')}_${String(t).replace('.', 'p')}.png`);
    await page.screenshot({ path: file });
    if (!phases) console.log('saved', file);
  }
  if (phases) console.log('captured', c, cam, ts.length);
}
if (errors.length) console.log('console messages:\n' + [...new Set(errors)].slice(0, 12).join('\n'));
await browser.close(); server.close();
