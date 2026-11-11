// Real Chrome + packaged mountSpace + opaque-origin nested sandbox. No browser package/install.
import {spawn} from 'node:child_process';
import {readFile,writeFile,mkdir,mkdtemp} from 'node:fs/promises';
import {resolve} from 'node:path';
import {setTimeout as delay} from 'node:timers/promises';
const a=process.argv.slice(2),out=a[a.indexOf('--out')+1];
const port=a.includes('--port')?a[a.indexOf('--port')+1]:'8782';
if(!a.includes('--out')||!out?.startsWith('/Volumes/Expansion/'))throw Error('Use --out on /Volumes/Expansion');
await mkdir(out,{recursive:true});const profile=await mkdtemp(resolve(out,'chrome-'));
const chrome=spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',['--headless=new','--remote-debugging-port=0','--user-data-dir='+profile,'--no-first-run','--hide-scrollbars','about:blank'],{stdio:['ignore','ignore','pipe']});
let ws,stderr='',results=[],errors=[];chrome.stderr.on('data',b=>stderr+=b);
const until=async(fn,ms=30000)=>{const end=Date.now()+ms;while(Date.now()<end){const v=await fn();if(v)return v;await delay(80);}throw Error('Wait timed out');};
try{
 const p=await until(async()=>{try{return(await readFile(resolve(profile,'DevToolsActivePort'),'utf8')).trim().split('\n');}catch{return null;}});
 ws=new WebSocket(`ws://127.0.0.1:${p[0]}${p[1]}`);await new Promise((y,n)=>{ws.onopen=y;ws.onerror=n;});
 let id=0;const pending=new Map(),contexts=new Map(),sessions=new Set();
 const send=(method,params={},sessionId)=>new Promise((yes,no)=>{const n=++id,timer=setTimeout(()=>{pending.delete(n);no(Error('CDP timeout '+method));},15000);pending.set(n,{yes,no,timer});ws.send(JSON.stringify({id:n,method,params,...(sessionId?{sessionId}:{})}));});
 const media=s=>send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'},{name:'prefers-color-scheme',value:'dark'}]},s);
 ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id){const p=pending.get(m.id);if(p){clearTimeout(p.timer);pending.delete(m.id);m.error?p.no(Error(JSON.stringify(m.error))):p.yes(m.result);}}
  if(m.method==='Target.attachedToTarget'){const s=m.params.sessionId;sessions.add(s);send('Runtime.enable',{},s).catch(()=>{});send('Target.setAutoAttach',{autoAttach:true,waitForDebuggerOnStart:false,flatten:true},s).catch(()=>{});media(s).catch(()=>{});}
  if(m.method==='Runtime.executionContextCreated'){const c=m.params.context;if(c.auxData?.isDefault)contexts.set(m.sessionId+':'+c.id,{s:m.sessionId,id:c.id});}
  if(m.method==='Runtime.executionContextDestroyed')contexts.delete(m.sessionId+':'+m.params.executionContextId);
  if(m.method==='Runtime.executionContextsCleared')for(const[k,c]of contexts)if(c.s===m.sessionId)contexts.delete(k);
  if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails.exception?.description||m.params.exceptionDetails.text);
 };
 const{targetId}=await send('Target.createTarget',{url:'about:blank'}),{sessionId:s}=await send('Target.attachToTarget',{targetId,flatten:true});sessions.add(s);
 await send('Runtime.enable',{},s);await send('Page.enable',{},s);await send('Target.setAutoAttach',{autoAttach:true,waitForDebuggerOnStart:false,flatten:true},s);
 const evalAt=async(c,expression)=>{const r=await send('Runtime.evaluate',{expression,contextId:c.id,returnByValue:true,awaitPromise:true},c.s);if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);return r.result?.value;};
 const outer=async expr=>{const r=await send('Runtime.evaluate',{expression:expr,returnByValue:true,awaitPromise:true},s);if(r.exceptionDetails)throw Error(r.exceptionDetails.text);return r.result?.value;};
 let guest;const ev=expr=>evalAt(guest,expr);
 const metrics=(width,height=900)=>send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:2,mobile:false},s);
 const navigate=async(name,query='')=>{
  errors=[];guest=null;await metrics(1440);await send('Page.navigate',{url:`http://127.0.0.1:${port}/?name=${name}${query}`},s);
  await until(async()=>{for(const c of[...contexts.values()]){try{if(await evalAt(c,'document.title')===(name==='sky-window'?'Sky Window':'Pair Play')){guest=c;return true;}}catch{}}return false;});
  await media(guest.s);await ev('document.fonts.ready.then(()=>true)');
 };
 const check=(v,label,detail={})=>{results.push({label,passed:!!v,...detail});if(!v)throw Error(label+' '+JSON.stringify(detail));};
 const shot=async(name,full=true)=>{await send('Page.bringToFront',{},s);await ev('window.scrollTo(0,0)');if(full){const h=await ev('document.documentElement.scrollHeight');await metrics(await outer('innerWidth'),Math.min(5000,Math.max(900,h)));await delay(200);}const r=await send('Page.captureScreenshot',{format:'png',fromSurface:true},s);await writeFile(resolve(out,name+'.png'),Buffer.from(r.data,'base64'));};
 const key=async(key,code,n)=>{await send('Input.dispatchKeyEvent',{type:'keyDown',key,code,windowsVirtualKeyCode:n,...(key==='Enter'?{text:'\r',unmodifiedText:'\r'}:{})},s);await send('Input.dispatchKeyEvent',{type:'keyUp',key,code,windowsVirtualKeyCode:n},s);await delay(40);};
 const click=sel=>ev(`document.querySelector(${JSON.stringify(sel)}).click()`);
 const layout=async(name)=>{for(const width of[1440,390,320]){await metrics(width);await delay(250);const info=await ev(`({width:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth,minTarget:Math.min(...[...document.querySelectorAll('button,summary')].filter(e=>e.getBoundingClientRect().height>0).map(e=>e.getBoundingClientRect().height)),running:document.getAnimations().filter(a=>a.playState==='running').length})`);check(info.width>=info.scroll&&info.minTarget>=44&&info.running===0,name+' geometry/targets/reduced-motion '+width,info);await shot(name+'-'+width);}}
 // Dashboard: real public requests, then explicit injected failure/empty/loading branches.
 if(!a.includes('--game-only')) {
 await navigate('sky-window','&delay=1000');
 check(await ev(`document.querySelector('.room').getAttribute('aria-busy')`)==='true','Dashboard loading is real in-flight work');await shot('sky-loading',false);
 await until(()=>ev(`document.body.dataset.state==='live'`),45000);
 const live=await ev(`({cities:[...document.querySelectorAll('.pane')].map(e=>({name:e.dataset.city,temp:e.querySelector('.num').textContent})),rows:document.querySelectorAll('#days tr').length,source:document.querySelector('#source').textContent,domain:[document.querySelector('#ribbon svg').dataset.domainMin,document.querySelector('#ribbon svg').dataset.domainMax]})`);
 check(live.rows===7&&live.cities.length===3&&live.source.includes('UTC'),'Live public forecast populated panes and exact table',live);
 await layout('sky-live');await metrics(1440);
 await ev(`document.querySelector('[data-city="tokyo"] button').focus()`);await key('Enter','Enter',13);
 check(await ev(`document.querySelector('#week-city').textContent`)==='Tokyo','Keyboard city selection changes actual chart');
 const focus=await ev(`getComputedStyle(document.activeElement).outlineStyle`);check(focus==='solid','Visible city keyboard focus');await shot('sky-focus');
 await ev(`document.querySelector('summary').focus()`);await key('Enter','Enter',13);check(await ev(`document.querySelector('details').open`),'Keyboard opens exact-value table');await shot('sky-table');
 const before=await ev(`document.querySelector('#days').textContent`);await outer(`harness.delay=0;harness.fail='net'`);await click('#reload');await until(()=>ev(`document.body.dataset.state==='stale'`));
 await click('#reload');await delay(100);check(await ev(`document.body.dataset.state==='stale'&&document.querySelector('#days').textContent===${JSON.stringify(before)}`),'Repeated failed refresh preserves last-good forecast');await shot('sky-stale');
 // Ambient animation both starts and can be paused independently of OS motion.
 for(const ss of sessions)await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'no-preference'}]},ss).catch(()=>{});
 await delay(150);const running=await ev(`document.getAnimations().filter(a=>a.playState==='running').length`);check(running>0,'Sky ambient motion runs under no-preference');await click('#motion');check(await ev(`document.getAnimations().filter(a=>a.playState==='running').length`)===0,'Sky pause stops all ambient motion');
 await navigate('sky-window','&fault=empty');await until(()=>ev(`document.body.dataset.state==='empty'`));check(await ev(`document.querySelectorAll('#days tr').length`)===0,'Empty forecast invents no values');await shot('sky-empty');
 await navigate('sky-window','&fault=invalid');await until(()=>ev(`document.body.dataset.state==='error'`));await shot('sky-error');await click('#sample');check(await ev(`document.body.dataset.state==='sample'&&document.querySelector('#source').textContent.includes('Synthetic')`),'Sample is opt-in and explicitly labelled');await shot('sky-sample');
 await navigate('sky-window','&fault=off');await until(()=>ev(`document.body.dataset.state==='error'`));check(await ev(`document.querySelector('#status').textContent.includes('Internet access is off')`),'Internet-off response has accurate host recovery');await shot('sky-off');
 }
 // Game: real record bridge; normal input through complete mismatch/match/win/retry/reload loop.
 await navigate('pair-play','&delay=900');await until(()=>ev(`document.querySelectorAll('.card').length===12`));await shot('pair-loading',false);
 await until(()=>ev(`!document.querySelector('#save').textContent.includes('Loading')`));
 const initial=await ev(`document.querySelectorAll('#history li').length`);await layout('pair-ready');await metrics(1440);
 const cards=await ev(`[...document.querySelectorAll('.card')].map((e,i)=>({i,kind:e.querySelector('em').textContent}))`),groups=Object.values(Object.groupBy(cards,c=>c.kind));
 await ev(`document.querySelectorAll('.card')[${groups[0][0].i}].focus()`);await key(' ','Space',32);
 check(await ev(`document.querySelectorAll('.is-up').length`)===1,'Space turns a card');await shot('pair-focus');
 await ev(`document.querySelectorAll('.card')[${groups[1][0].i}].focus()`);await key('Enter','Enter',13);
 check(await ev(`document.querySelector('#turns').textContent`)==='1','Mismatch costs exactly one turn');await shot('pair-mismatch');await delay(1200);check(await ev(`document.querySelectorAll('.is-up').length`)===0,'Mismatch flips back and unlocks');
 await outer(`harness.delay=0;harness.fail='save'`);
 for(const g of groups)for(const c of g){await ev(`document.querySelectorAll('.card')[${c.i}].focus()`);await key('Enter','Enter',13);}
 await until(()=>ev(`document.querySelector('#save').textContent.includes('Round not saved')`));
 check(await ev(`document.querySelector('#pairs').textContent==='6'&&document.querySelector('#turns').textContent==='7'&&!document.querySelector('#win').hidden`),'Complete game loop reaches six pairs in seven turns');await shot('pair-save-error');
 await click('#again');check(await ev(`document.querySelector('#pairs').textContent`)==='6','Failed round retained before redeal');
 await outer(`harness.fail='';harness.delay=700`);await click('#retry');await shot('pair-saving',false);
 await until(()=>ev(`document.querySelector('#save').textContent.includes('verified')`));
 const receipt=await outer(`harness.calls.filter(c=>['data.put','data.get'].includes(c.op)).map(c=>({op:c.op,id:c.args.id,turns:c.args.data?.turns,baseRev:c.args.base_rev}))`);
 check(receipt.some(r=>r.op==='data.get')&&receipt.filter(r=>r.op==='data.put').every(r=>r.baseRev===0),'Finished round written create-only and read back', {receipt});await shot('pair-win');
 await click('#again');check(await ev(`document.querySelector('#pairs').textContent==='0'&&document.querySelector('#turns').textContent==='0'&&document.querySelector('#win').hidden`),'Deal again starts a clean playable round');
 await navigate('pair-play');await until(()=>ev(`document.querySelectorAll('#history li').length>0`));
 check(await ev(`document.querySelector('#history li .t').textContent`)==='7','Saved round survives complete frame reload');await shot('pair-persisted');
 await navigate('pair-play','&fault=query');await until(()=>ev(`document.querySelector('#save').textContent.includes('could not load')`));check(await ev(`document.querySelectorAll('.card').length`)===12,'Scorecard error keeps game playable');await shot('pair-query-error');
 await outer(`harness.fail=''`);await click('#retry');await until(()=>ev(`document.querySelector('#save').textContent==='Scorecard loaded'`));check(await ev(`document.querySelectorAll('#history li').length>0`),'Scorecard retry recovers real records');
 await metrics(1440,1800);await ev(`document.documentElement.style.zoom='2'`);const zoom=await ev(`({w:document.documentElement.clientWidth,s:document.documentElement.scrollWidth})`);check(zoom.s<=zoom.w,'Game CSS 200% geometry (not native zoom)',zoom);
 check(errors.length===0,'No uncaught exceptions in final game context',{errors});
 await writeFile(resolve(out,'verification.json'),JSON.stringify({passed:true,results,scope:'Actual sandbox mount and Space bridge; isolated file-backed verifier storage and live public network. Not Desktop/chat generation or production backend qualification.'},null,2));
 console.log(JSON.stringify({passed:true,checks:results.length,out,initialHistoryCount:initial},null,2));await send('Target.closeTarget',{targetId});
}catch(e){await writeFile(resolve(out,'failure.json'),JSON.stringify({error:e.stack,results,errors,stderr:stderr.slice(-2000)},null,2));throw e;}
finally{ws?.close();chrome.kill('SIGKILL');chrome.stderr.destroy();}
