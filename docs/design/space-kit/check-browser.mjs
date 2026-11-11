// Design-only Chromium checks. Uses real kit/references and synthetic smoke API.
// Run with render-server.mjs on PORT=8769. Never connects to Hermes Desktop.
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {readFile, writeFile, mkdir, mkdtemp} from 'node:fs/promises';
import {resolve} from 'node:path';
import {setTimeout as delay} from 'node:timers/promises';
import {replayForms} from '../../../tests/js/reference/forms-replay.mjs';
const out=resolve('docs/design/space-kit/screens');await mkdir(out,{recursive:true});
const scratch=process.env.SPACE_KIT_BROWSER_TMP;
if(!scratch)throw Error('Set SPACE_KIT_BROWSER_TMP to an approved temporary directory');
await mkdir(scratch,{recursive:true});
const profile=await mkdtemp(resolve(scratch,'chrome-'));
const chrome=spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',['--headless=new','--remote-debugging-port=0','--remote-debugging-address=127.0.0.1','--user-data-dir='+profile,'--no-first-run','--no-default-browser-check','about:blank'],{stdio:['ignore','ignore','pipe']});
let stderr='',ws,id=0;chrome.stderr.on('data',x=>{stderr=(stderr+x).slice(-4000);});
const until=async(fn,label)=>{const end=Date.now()+15000;while(Date.now()<end){const value=await fn();if(value)return value;await delay(70);}throw Error('Timed out: '+label);};
const results={provenance:'Real reference code, synthetic in-memory records and explicitly labelled weather sample. Not Desktop, real chat, durable storage or network-boundary qualification.',pages:[],checks:[],screens:[],failures:[]};
const pending=new Map(),contexts=new Map(),attached=new Set();
const root='http://127.0.0.1:8769';
let send;
try{
 const endpoint=await until(async()=>{try{return(await readFile(resolve(profile,'DevToolsActivePort'),'utf8')).trim().split('\n');}catch{return null;}},'Chrome endpoint');
 ws=new WebSocket(`ws://127.0.0.1:${endpoint[0]}${endpoint[1]}`);await new Promise((yes,no)=>{ws.onopen=yes;ws.onerror=no;});
 send=(method,params={},sessionId)=>new Promise((yes,no)=>{const n=++id;pending.set(n,{yes,no});ws.send(JSON.stringify({id:n,method,params,...(sessionId?{sessionId}:{})}));});
 ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id){const p=pending.get(m.id);pending.delete(m.id);if(m.error)p.no(Error(JSON.stringify(m.error)));else p.yes(m.result);}if(m.method==='Runtime.executionContextCreated')contexts.set(m.sessionId+':'+m.params.context.id,{...m.params.context,sessionId:m.sessionId});if(m.method==='Runtime.executionContextDestroyed')contexts.delete(m.sessionId+':'+m.params.executionContextId);};
 results.browser=(await send('Browser.getVersion')).product;
 const evaluate=async(expression,ctx)=>{const r=await send('Runtime.evaluate',{expression,contextId:ctx?.id,returnByValue:true,awaitPromise:true},ctx.sessionId);if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);return r.result.value;};
 async function open(path,width=1440,mode='light',reduced=false){
  const {targetId}=await send('Target.createTarget',{url:'about:blank'});
  const {sessionId}=await send('Target.attachToTarget',{targetId,flatten:true});
  await send('Runtime.enable',{},sessionId);await send('Page.enable',{},sessionId);
  await send('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:false},sessionId);
  await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:mode},{name:'prefers-reduced-motion',value:reduced?'reduce':'no-preference'}]},sessionId);
  await send('Page.navigate',{url:root+path},sessionId);
  const hostCtx={sessionId};
  const pageSessions=new Set([sessionId]),pageFrames=new Set([targetId]);
  await until(()=>evaluate('document.readyState === "complete"',hostCtx),'document');
  let ctx=hostCtx;
  if(path.startsWith('/?')){
   ctx=await until(async()=>{
    for(const target of(await send('Target.getTargets')).targetInfos.filter(t=>t.type==='iframe'&&pageFrames.has(t.parentFrameId)&&!attached.has(t.targetId))){attached.add(target.targetId);pageFrames.add(target.targetId);const child=await send('Target.attachToTarget',{targetId:target.targetId,flatten:true});pageSessions.add(child.sessionId);await send('Runtime.enable',{},child.sessionId);}
    for(const context of contexts.values()){if(!context.auxData?.isDefault || !pageSessions.has(context.sessionId))continue;try{if(await evaluate('Boolean(window.space?.meta && document.querySelector("main"))',context))return context;}catch{}}
   },'inner application for current page only');
  }
  await delay(200);
  const app=expression=>evaluate(expression,ctx),host=expression=>evaluate(expression,hostCtx);
  return{targetId,sessionId,app,host,ctx,path,width,mode,close:()=>send('Target.closeTarget',{targetId})};
 }
 async function capture(p,name,full=false){
  await send('Page.bringToFront',{},p.sessionId);
  // Force OOPIF surface recomposition; DOM-ready alone gave blank captures.
  await send('Emulation.setDeviceMetricsOverride',{width:p.width < 680 ? 800 : 680,height:1000,deviceScaleFactor:1,mobile:false},p.sessionId);
  await delay(300);
  await send('Emulation.setDeviceMetricsOverride',{width:p.width,height:1000,deviceScaleFactor:1,mobile:false},p.sessionId);
  await p.app('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))');
  // Opaque-origin child DOM can be ready before its compositor surface appears.
  await delay(1000);
  const options={format:'png',captureBeyondViewport:true};
  if(full){const metrics=await send('Page.getLayoutMetrics',{},p.sessionId);options.clip={x:0,y:0,width:p.width,height:metrics.cssContentSize.height,scale:1};}
  const shot=await send('Page.captureScreenshot',options,p.sessionId);
  const file=name+'.png';await writeFile(resolve(out,file),Buffer.from(shot.data,'base64'));results.screens.push(file);
 }
 async function measure(p,label){
  const m=await p.app(`(() => {const d=document.documentElement;return {width:d.clientWidth,scrollWidth:d.scrollWidth,bg:getComputedStyle(document.body).backgroundColor,text:getComputedStyle(document.body).color,theme:document.body.dataset.theme||d.dataset.theme||'default',targets:[...document.querySelectorAll('button,a.space-button,.space-nav a,summary,input:not([type=checkbox]),select')].filter(n=>n.getClientRects().length&&!n.disabled).map(n=>({text:(n.textContent||n.getAttribute('aria-label')||n.type).trim().slice(0,50),height:n.getBoundingClientRect().height,width:n.getBoundingClientRect().width})),missingLabels:[...document.querySelectorAll('input,select,textarea')].filter(n=>!n.labels?.length&&!n.getAttribute('aria-label')).length};})()`);
  results.pages.push({label,path:p.path,mode:p.mode,...m});assert.ok(m.scrollWidth<=m.width+1,label+' page overflow');assert.equal(m.missingLabels,0,label+' input labels');return m;
 }
 for(const mode of ['light','dark']){
  for(const example of ['research-desk','habit-planner']){
   const p=await open('/?example='+example,1440,mode);await measure(p,example+' desktop');await capture(p,example+'-'+mode);
   if(example==='research-desk'){
    assert.equal(await p.app('document.querySelector("[aria-current=page]")?.textContent'),'Overview');
    await p.app('document.querySelector(\'a[href="#/library"]\').click()');await until(()=>p.app('!!document.querySelector("input[type=search]")'),'Library');
    await p.app('document.querySelector(".paper-list button").click()');await until(()=>p.app('!!document.querySelector("textarea")'),'Editor');
    await capture(p,'research-library-'+mode);
   }
   await p.close();
  }
  const g=await open('/src/living-spaces/skills/build-space/references/kit-gallery.html',1440,mode);await measure(g,'gallery desktop');await capture(g,'gallery-'+mode,true);await g.close();
  const w=await open('/weather-off.html',1440,mode);await measure(w,'weather simulated off');assert.match(await w.app('document.getElementById("status").textContent'),/Internet is off/);await capture(w,'weather-off-'+mode);
  await w.app('document.getElementById("sample").click()');assert.equal(await w.app('document.querySelectorAll("#hourly tr").length'),12);assert.match(await w.app('document.getElementById("provenance").textContent'),/Synthetic/);await capture(w,'weather-sample-'+mode);await w.close();
 }
 // Purpose-built input/confirmation regression using the existing real browser replay.
 for(const example of ['research-desk','habit-planner']){
  const p=await open('/?example='+example);const replay=await replayForms({host:p.host,app:p.app,cdp:send,sessionId:p.sessionId,example});assert.equal(replay.status,'PASS');results.checks.push(replay);await p.close();
 }
 // Draft lifetime: leave the route and select the record again; no write until Save.
 const d=await open('/?example=research-desk');
 await d.app('document.querySelector(\'a[href="#/library"]\').click()');await until(()=>d.app('!!document.querySelector(".paper-list button")'),'Library');
 await d.app('document.querySelector(".paper-list button").click()');await until(()=>d.app('!!document.querySelector("textarea")'),'Editor');
 await d.app('const t=document.querySelector("textarea");t.value="Unsaved navigation fixture";t.dispatchEvent(new Event("input",{bubbles:true}));');
 await delay(100);await d.app('document.querySelector(\'a[href="#/overview"]\').click()');await delay(150);await d.app('document.querySelector(\'a[href="#/library"]\').click()');await delay(150);await d.app('document.querySelector(".paper-list button").click()');await delay(150);
 assert.equal(await d.app('document.querySelector("textarea").value'),'Unsaved navigation fixture');assert.equal(await d.host('reference.calls.filter(x=>x.op==="data.put").length'),0);results.checks.push({name:'unsaved notes survive route remount; no automatic write',status:'PASS'});await d.close();
 for(const width of [390,320,720]){
  for(const name of ['research-desk','habit-planner','gallery','weather']){
   const path=name==='gallery'?'/src/living-spaces/skills/build-space/references/kit-gallery.html':name==='weather'?'/weather-off.html':'/?example='+name;
   const p=await open(path,width,'dark',true);
   if(name==='weather')await p.app('document.getElementById("sample").click()');
   const m=await measure(p,name+' narrow '+width);if(width<=390){const small=m.targets.filter(t=>t.height<43.5);if(small.length)results.failures.push({label:name+' '+width,issue:'target <44px',small});}
   if(width===390)await capture(p,name+'-mobile-dark',name==='gallery');
   await p.close();
  }
 }
 const u=await open('/?example=weather-window');assert.match(await u.app('document.getElementById("status").textContent'),/not available in this runtime/);await u.app('document.getElementById("sample").click()');assert.equal(await u.app('document.querySelectorAll("#hourly tr").length'),12);assert.deepEqual(await u.host('reference.logs.filter(x=>x.level==="error")'),[]);await capture(u,'weather-sandbox-sample');await u.close();
 // Each palette renders with its actual type and geometry, not only token values.
 for(const theme of ['editorial','terminal','playful','minimal','data','journal','game']){
  const p=await open('/src/living-spaces/skills/build-space/references/kit-gallery.html?theme='+theme,1440,'light');await measure(p,'preset '+theme);await capture(p,'preset-'+theme);await p.close();
 }
 const r=await open('/src/living-spaces/skills/build-space/references/kit-gallery.html',390,'dark',true);
 const animation=await r.app('getComputedStyle(document.querySelector(".space-spinner")).animationName');assert.equal(animation,'none');results.checks.push({name:'reduced-motion preserves static loading cue',status:'PASS'});
 await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},r.sessionId);await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},r.sessionId);
 assert.equal(await r.app('document.activeElement.matches(":focus-visible")'),true);results.checks.push({name:'actual Tab produces visible keyboard focus',status:'PASS'});await r.close();
 results.status=results.failures.length?'ISSUES':'PASS';
}catch(e){results.status='FAIL';results.error=e.stack;results.stderr=stderr;process.exitCode=1;}
finally{
 await writeFile(resolve('docs/design/space-kit/passes/browser-checks.json'),JSON.stringify(results,null,2));
 console.log(JSON.stringify({status:results.status,pages:results.pages.length,screens:results.screens.length,checks:results.checks.map(x=>({name:x.name||x.example,status:x.status})),failures:results.failures,error:results.error},null,2));
 if(send)try{await send('Browser.close');}catch{}ws?.close();if(chrome.exitCode===null)chrome.kill('SIGTERM');
}
