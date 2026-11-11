import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import {resolve, extname, sep} from 'node:path';
import {referenceBundle} from '../../../tests/js/reference/bundle.mjs';
const root = resolve(import.meta.dirname, '../../..');
const mime = {'.html':'text/html','.css':'text/css','.js':'text/javascript','.mjs':'text/javascript','.json':'application/json','.png':'image/png','.woff2':'font/woff2'};
const server = createServer(async (req,res) => {
  try {
    const u = new URL(req.url,'http://localhost');
    if (u.pathname === '/bundle') {
      const b = await referenceBundle(u.searchParams.get('example') || 'research-desk');
      res.writeHead(200,{'Content-Type':'application/json','Cache-Control':'no-store'}).end(JSON.stringify(b)); return;
    }
    const p=resolve(root,'.'+(u.pathname==='/'?'/docs/design/space-kit/preview.html':decodeURIComponent(u.pathname)));
    if (!p.startsWith(root+sep) || !mime[extname(p)]) {res.writeHead(404).end();return;}
    res.writeHead(200,{'Content-Type':mime[extname(p)],'Cache-Control':'no-store'}).end(await readFile(p));
  } catch(e) {res.writeHead(404).end(String(e.message));}
});
server.listen(8767,'127.0.0.1',()=>console.log('Design-only synthetic reference preview: http://127.0.0.1:8767'));
