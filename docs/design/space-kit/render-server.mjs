import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import {resolve, extname, sep} from 'node:path';
import {referenceBundle} from '../../../tests/js/reference/bundle.mjs';
const root = resolve(import.meta.dirname, '../../..');
const mime = {'.html':'text/html','.css':'text/css','.js':'text/javascript','.mjs':'text/javascript','.json':'application/json','.png':'image/png','.woff2':'font/woff2'};
const server = createServer(async (req,res) => {
  try {
    const u = new URL(req.url,'http://localhost');
    if (u.pathname === '/weather-off.html') {
      const base='/src/living-spaces/skills/build-space/references/weather-window/';
      let html=await readFile(resolve(root,'.'+base+'index.html'),'utf8');
      html=html.replace('<head>','<head><base href="'+base+'">').replace('<body>','<body><aside style="padding:8px 20px;font:12px/1.5 system-ui;border-bottom:1px solid currentColor">Design fixture · simulated host Internet Off · actual reference code · no network attempted</aside><script>window.space={meta:{network:"off"}};</script>');
      res.writeHead(200,{'Content-Type':'text/html','Cache-Control':'no-store'}).end(html);return;
    }
    if (u.pathname === '/bundle') {
      const example=u.searchParams.get('example') || 'research-desk';
      let b;
      if (example === 'weather-window') {
        b=await referenceBundle('research-desk');
        const dir=resolve(root,'src/living-spaces/skills/build-space/references/weather-window');
        b.manifest=JSON.parse(await readFile(resolve(dir,'space.json'),'utf8'));
        b.space={id:'weather-reference',name:b.manifest.name};
        b.files=await Promise.all(['index.html','app.js','styles.css'].map(async path=>({path,mime:mime[extname(path)],text:await readFile(resolve(dir,path),'utf8')})));
      } else b = await referenceBundle(example);
      res.writeHead(200,{'Content-Type':'application/json','Cache-Control':'no-store'}).end(JSON.stringify(b)); return;
    }
    const p=resolve(root,'.'+(u.pathname==='/'?'/docs/design/space-kit/preview.html':decodeURIComponent(u.pathname)));
    if (!p.startsWith(root+sep) || !mime[extname(p)]) {res.writeHead(404).end();return;}
    res.writeHead(200,{'Content-Type':mime[extname(p)],'Cache-Control':'no-store'}).end(await readFile(p));
  } catch(e) {res.writeHead(404).end(String(e.message));}
});
const port=Number(process.env.PORT || 8767);
server.listen(port,'127.0.0.1',()=>console.log('Design-only synthetic reference preview: http://127.0.0.1:'+port));
