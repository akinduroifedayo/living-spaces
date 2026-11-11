// Isolated local reference verifier, not Desktop or a production store.
// Run: node .../server.mjs --out /Volumes/Expansion/.../showcase-store [--port 8782]
import {createServer} from 'node:http';
import {readFile,readdir,mkdir,writeFile,rename} from 'node:fs/promises';
import {resolve,extname,relative,sep} from 'node:path';
const args=process.argv.slice(2), value=(k,d)=>args.includes(k)?args[args.indexOf(k)+1]:d;
const output=value('--out');
if(!output?.startsWith('/Volumes/Expansion/'))throw Error('--out must be on /Volumes/Expansion');
await mkdir(output,{recursive:true});
const root=resolve(import.meta.dirname,'../../../../../..'),showcase=resolve(import.meta.dirname,'..');
const mime={'.html':'text/html','.css':'text/css','.js':'text/javascript','.mjs':'text/javascript','.json':'application/json','.png':'image/png','.webp':'image/webp','.svg':'image/svg+xml','.woff2':'font/woff2','.md':'text/markdown'};
const names=['sky-window','pair-play','chromatic-current'];
const valid=n=>{if(!names.includes(n))throw Error('Unknown reference');return n;};
async function walk(dir){const all=[];for(const e of await readdir(dir,{withFileTypes:true})){const p=resolve(dir,e.name);if(e.isDirectory())all.push(...await walk(p));else all.push(p);}return all;}
async function bundle(n){
 const dir=resolve(showcase,valid(n)),manifest=JSON.parse(await readFile(resolve(dir,'space.json'),'utf8')),files=[];
 for(const p of await walk(dir)){const path=relative(dir,p).split(sep).join('/');const m=mime[extname(p)]||'application/octet-stream';files.push(/\.(html|css|m?js|json|svg|md)$/.test(p)?{path,mime:m,text:await readFile(p,'utf8')}:{path,mime:m,b64:(await readFile(p)).toString('base64')});}
 const sandbox={format:1,shell_srcdoc:await readFile(resolve(root,'src/living-spaces/guest/space-host.html'),'utf8')};
 return {sandbox,space:{id:'reference-'+n,name:manifest.name},rev:1,manifest,files};
}
const readBody=async req=>{let b='';for await(const c of req){b+=c;if(b.length>1000000)throw Error('Body too large');}return JSON.parse(b);};
const ok=result=>({ok:true,result}),err=(code,message,extra={})=>({ok:false,error:{code,message,...extra}});
async function records(n,op,a){
 const file=resolve(output,valid(n)+'-rounds.json');let rows=[];
 try{rows=JSON.parse(await readFile(file,'utf8'));}catch(e){if(e.code!=='ENOENT')throw e;}
 if(op==='data.query')return ok({records:rows.filter(r=>r.collection===a.collection).slice(a.offset||0,(a.offset||0)+(a.limit||500)),total:rows.length,seq:rows.length});
 const current=rows.find(r=>r.collection===a.collection&&r.id===a.id);
 if(op==='data.get')return current?ok(current):err('not_found','Record not found');
 if(op!=='data.put'||a.collection!==(n==='chromatic-current'?'compositions':'rounds')||typeof a.id!=='string')return err('invalid','Unsupported record operation');
 if((current?.rev||0)!==a.base_rev)return err('conflict','Record revision changed',{current});
 const r={collection:a.collection,id:a.id,data:a.data,rev:(current?.rev||0)+1,updated_at:Date.now()/1000};
 rows=[r,...rows.filter(x=>x!==current)];await writeFile(file+'.next',JSON.stringify(rows,null,2));await rename(file+'.next',file);return ok(r);
}
const recordQueues=new Map();
function serializedRecords(name,op,args){
 const n=valid(name),previous=recordQueues.get(n)||Promise.resolve();
 const next=previous.catch(()=>{}).then(()=>records(n,op,args));
 recordQueues.set(n,next);return next;
}
createServer(async(req,res)=>{
 const json=v=>res.writeHead(200,{'Content-Type':'application/json','Cache-Control':'no-store'}).end(JSON.stringify(v));
 try{
  const u=new URL(req.url,'http://localhost');
  if(u.pathname==='/bundle')return json(await bundle(u.searchParams.get('name')));
  if(u.pathname==='/records'){const{op,args}=await readBody(req);return json(await serializedRecords(u.searchParams.get('name'),op,args));}
  if(u.pathname==='/net'){
   const{url,as}=await readBody(req),target=new URL(url);
   if(target.protocol!=='https:'||target.hostname!=='api.open-meteo.com'||target.pathname!=='/v1/forecast'||as!=='json')return json(err('not_granted','Reference harness allows only public Open-Meteo forecast JSON'));
   const r=await fetch(target,{credentials:'omit',redirect:'error',signal:AbortSignal.timeout(12000)});
   const result={status:r.status,url:r.url,json:await r.json()};
   await writeFile(resolve(output,'last-public-forecast-'+target.searchParams.get('latitude')+'.json'),JSON.stringify({retrieved:new Date().toISOString(),...result},null,2));
   return json(ok(result));
  }
  const p=resolve(root,'.'+(u.pathname==='/'?'/src/living-spaces/runtime/kit/showcase/harness/index.html':decodeURIComponent(u.pathname)));
  if(!p.startsWith(root+sep)||!mime[extname(p)]){res.writeHead(404).end();return;}
  const bytes=await readFile(p);res.writeHead(200,{'Content-Type':mime[extname(p)],'Cache-Control':'no-store'}).end(bytes);
 }catch(e){if(!res.headersSent)json(err('unavailable',String(e.message)));else res.end();}
}).listen(Number(value('--port','8782')),'127.0.0.1',()=>console.log('Isolated showcase: http://127.0.0.1:'+value('--port','8782')));
