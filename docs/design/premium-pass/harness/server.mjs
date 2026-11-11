// Design-only showcase harness. Mounts a showcase Space in the real sandbox
// (src/desktop/sandbox mountSpace + guest/space-host.html) with an in-memory
// record store. net.fetch is performed by this server against the real public
// URL (HTTPS only, no cookies), mirroring the host bridge contract. Not Desktop.
import {createServer} from 'node:http';
import {readFile, readdir} from 'node:fs/promises';
import {resolve, extname, relative, sep} from 'node:path';
const root = resolve(import.meta.dirname, '../../../..');
const showcase = resolve(root, 'src/living-spaces/skills/build-space/references/showcase');
const mime = {'.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json',
  '.png': 'image/png', '.webp': 'image/webp', '.svg': 'image/svg+xml', '.woff2': 'font/woff2', '.md': 'text/markdown'};
const text = p => /\.(html|css|m?js|json|svg|md)$/.test(p);
async function walk(dir) {
  const out = [];
  for (const e of await readdir(dir, {withFileTypes: true})) {
    const p = resolve(dir, e.name);
    if (e.isDirectory()) out.push(...await walk(p)); else out.push(p);
  }
  return out;
}
async function bundle(name) {
  const dir = resolve(showcase, name);
  if (!dir.startsWith(showcase + sep)) throw Error('bad name');
  const manifest = JSON.parse(await readFile(resolve(dir, 'space.json'), 'utf8'));
  const files = [];
  for (const p of await walk(dir)) {
    const path = relative(dir, p).split(sep).join('/');
    if (path === 'README.md') continue;
    const m = mime[extname(p)] || 'application/octet-stream';
    files.push(text(p) ? {path, mime: m, text: await readFile(p, 'utf8')} : {path, mime: m, b64: (await readFile(p)).toString('base64')});
  }
  for (const path of ['kit/spaces-kit.mjs', 'kit/spaces-kit.css', 'vendor/preact.mjs', 'vendor/hooks.mjs'])
    files.push({path, mime: mime[extname(path)], text: await readFile(resolve(root, 'src/living-spaces/runtime', path), 'utf8')});
  manifest.imports = {...(manifest.imports || {}), 'preact': 'vendor/preact.mjs', 'preact/hooks': 'vendor/hooks.mjs', 'spaces-kit': 'kit/spaces-kit.mjs'};
  const sandbox = {format: 1, shell_srcdoc: await readFile(resolve(root, 'src/living-spaces/guest/space-host.html'), 'utf8')};
  return {sandbox, space: {id: 'showcase-' + name, name: manifest.name}, rev: 1, manifest, files};
}
createServer(async (req, res) => {
  try {
    const u = new URL(req.url, 'http://localhost');
    if (u.pathname === '/bundle') {
      res.writeHead(200, {'Content-Type': 'application/json', 'Cache-Control': 'no-store'}).end(JSON.stringify(await bundle(u.searchParams.get('name'))));
      return;
    }
    if (u.pathname === '/net') {
      const {url, as} = JSON.parse(await new Promise(r => { let b = ''; req.on('data', c => b += c); req.on('end', () => r(b)); }));
      const target = new URL(url);
      if (target.protocol !== 'https:') { res.writeHead(200, {'Content-Type': 'application/json'}).end(JSON.stringify({ok: false, error: {code: 'invalid', message: 'HTTPS only'}})); return; }
      const r = await fetch(target, {credentials: 'omit', redirect: 'follow', signal: AbortSignal.timeout(12000)});
      const headers = Object.fromEntries(r.headers);
      let result = {status: r.status, url: r.url, headers};
      if (as === 'json') result.json = await r.json().catch(() => null);
      else if (as === 'bytes') result.bytes = {b64: Buffer.from(await r.arrayBuffer()).toString('base64'), mime: headers['content-type']};
      else result.text = await r.text();
      res.writeHead(200, {'Content-Type': 'application/json'}).end(JSON.stringify({ok: true, result}));
      return;
    }
    const p = resolve(root, '.' + (u.pathname === '/' ? '/docs/design/premium-pass/harness/showcase.html' : decodeURIComponent(u.pathname)));
    if (!p.startsWith(root + sep) || !mime[extname(p)]) { res.writeHead(404).end(); return; }
    const body = await readFile(p);
    res.writeHead(200, {'Content-Type': mime[extname(p)], 'Cache-Control': 'no-store'}).end(body);
  } catch (e) { console.error(req.url, e.message); if (!res.headersSent) res.writeHead(500).end(String(e.message)); else res.end(); }
}).listen(Number(process.env.PORT || 8781), '127.0.0.1', () => console.log('showcase harness on', process.env.PORT || 8781));
