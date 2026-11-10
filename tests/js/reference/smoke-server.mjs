import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { resolve, extname, sep } from 'node:path';
import { referenceBundle, mime } from './bundle.mjs';

const root = resolve(import.meta.dirname, '../../..');
const bundles = Object.fromEntries(await Promise.all(['research-desk', 'habit-planner'].map(async name => [name, await referenceBundle(name)])));
const server = createServer(async (request, response) => {
  try {
    const url = new URL(request.url, 'http://localhost');
    if (url.pathname === '/bundle') {
      const bundle = bundles[url.searchParams.get('example') || 'research-desk'];
      if (!bundle) { response.writeHead(404).end(); return; }
      response.setHeader('Content-Type', 'application/json');
      response.end(JSON.stringify(bundle));
      return;
    }
    const pathname = url.pathname === '/' ? '/tests/js/reference/smoke.html' : decodeURIComponent(url.pathname);
    const path = resolve(root, '.' + pathname);
    const allowed = ['tests/js/reference', 'src/desktop/sandbox'].some(prefix => path.startsWith(resolve(root, prefix) + sep));
    if (!allowed || !mime[extname(path)]) { response.writeHead(404).end(); return; }
    response.setHeader('Content-Type', mime[extname(path)]);
    response.end(await readFile(path));
  } catch { response.writeHead(404).end(); }
});
server.listen(0, '127.0.0.1', () => console.log(`Synthetic reference smoke: http://127.0.0.1:${server.address().port}/`));
