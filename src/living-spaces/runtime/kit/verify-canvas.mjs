// Local specimen verification, not Desktop/chat/API qualification.
// Node >=24 + installed Chrome; no packages, services or network required.
// --out is mandatory: browser profiles and evidence never default to the repo.
import {spawn} from 'node:child_process';
import {readFile,writeFile,mkdir,mkdtemp} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {setTimeout as delay} from 'node:timers/promises';
const args=process.argv.slice(2), out=args[args.indexOf('--out')+1];
if(!args.includes('--out')||!out||out.startsWith('--')) throw Error('Supply --out /absolute/evidence/directory');
const dir=resolve(out);
await mkdir(dir,{recursive:true});
const profile=await mkdtemp(resolve(dir,'chrome-'));
const chrome=spawn(process.env.CHROME||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', ['--headless=new','--remote-debugging-port=0','--user-data-dir='+profile,'--no-first-run','--hide-scrollbars','about:blank'],{stdio:['ignore','ignore','pipe']});
let stderr=''; chrome.stderr.on('data',b=>{stderr+=b;});
chrome.on('error',e=>{stderr+=e.message;});
let ws;
try {
 let port;
 for(let i=0;i<200;i++){try{port=(await readFile(resolve(profile,'DevToolsActivePort'),'utf8')).trim().split('\n');break;}catch{await delay(100);}}
 if(!port)throw Error('Chrome did not start: '+stderr);
 ws=new WebSocket(`ws://127.0.0.1:${port[0]}${port[1]}`); await new Promise((yes,no)=>{ws.onopen=yes;ws.onerror=no;});
 let id=0; const pending=new Map(); let errors=[];
 ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id){const p=pending.get(m.id);if(p){clearTimeout(p.timer);pending.delete(m.id);m.error?p.no(Error(JSON.stringify(m.error))):p.yes(m.result);}}if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails.exception?.description||m.params.exceptionDetails.text);};
 const send=(method,params={},sessionId)=>new Promise((yes,no)=>{const n=++id;const timer=setTimeout(()=>{pending.delete(n);no(Error('Timeout '+method));},20000);pending.set(n,{yes,no,timer});ws.send(JSON.stringify({id:n,method,params,...(sessionId?{sessionId}:{})}));});
 const {targetId}=await send('Target.createTarget',{url:'about:blank'});
 const {sessionId:s}=await send('Target.attachToTarget',{targetId,flatten:true});
 await send('Runtime.enable',{},s);await send('Page.enable',{},s);
 const ev=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true},s);if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);return r.result?.value;};
 const base=pathToFileURL(resolve(import.meta.dirname,'canvas-gallery.html')).href;
 const navigate=async look=>{errors=[];await send('Page.navigate',{url:base+'?look='+look},s);await delay(150);await ev('document.fonts.ready.then(()=>true)');};
 const metrics=(width,height=900)=>send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:2,mobile:false},s);
 const shot=async file=>{const r=await send('Page.captureScreenshot',{format:'png'},s);await writeFile(resolve(dir,file),Buffer.from(r.data,'base64'));};
 const key=async (key,code,n)=>{await send('Input.dispatchKeyEvent',{type:'keyDown',key,code,windowsVirtualKeyCode:n,...(key==='Enter'?{text:'\r',unmodifiedText:'\r'}:{})},s);await send('Input.dispatchKeyEvent',{type:'keyUp',key,code,windowsVirtualKeyCode:n},s);await delay(50);};
 const assert=(value,message)=>{if(!value)throw Error(message);};
 const results=[];
 // Token contrast is a floor, not a certificate for arbitrary images/gradients.
 const contrast=()=>{
  const b=getComputedStyle(document.body), ctx=document.createElement('canvas').getContext('2d');
  function rgb(value){ctx.fillStyle=value;const color=ctx.fillStyle;if(color.startsWith('#'))return color.slice(1).match(/../g).map(v=>parseInt(v,16));return color.match(/[\d.]+/g).slice(0,3).map(Number);}
  function lum(c){return c.map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4;}).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);}
  function ratio(a,z){const x=lum(rgb(a)),y=lum(rgb(z));return (Math.max(x,y)+.05)/(Math.min(x,y)+.05);}
  const t=n=>b.getPropertyValue('--space-'+n).trim();
  return {text:ratio(t('text'),t('bg')),muted:ratio(t('muted'),t('bg')),action:ratio(t('on-action'),t('action')),surfaceText:ratio(t('text'),t('surface'))};
 };
 for(const look of ['observatory','letterpress','blueprint','felt','daybreak','enamel'])for(const width of [1440,390,320])for(const scheme of ['dark','light']){
  await metrics(width);
  await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:scheme},{name:'prefers-reduced-motion',value:'reduce'}]},s);
  await navigate(look);
  const info=await ev(`(()=>{const d=document.documentElement,b=getComputedStyle(document.body),h=document.querySelector('h1'),p=document.querySelector('.space-panel');return {width:d.clientWidth,scrollWidth:d.scrollWidth,height:d.scrollHeight,title:h.textContent,headingFont:getComputedStyle(h).fontFamily,panelBackground:getComputedStyle(p).backgroundColor,bodyBackground:b.backgroundColor,animations:document.getAnimations().filter(a=>a.playState==='running').length,minTarget:Math.min(...[...document.querySelectorAll('button,nav a,select,summary')].filter(e=>e.getBoundingClientRect().height>0).map(e=>e.getBoundingClientRect().height)),contrast:(${contrast})()};})()`);
  assert(info.scrollWidth<=info.width,`Overflow ${look} ${width}`);
  assert(!info.animations,`Reduced motion left animation ${look}`);
  assert(info.minTarget>=44,`Target below 44px ${look}`);
  assert(Object.values(info.contrast).every(c=>c>=4.5),`Token contrast ${look}: ${JSON.stringify(info.contrast)}`);
  assert(!errors.length,errors.join('\n'));
  if(scheme==='dark'&&(width===1440||width===390&&['observatory','letterpress','felt'].includes(look))){await metrics(width,Math.min(5000,Math.max(900,info.height)));await shot(`after-${look}-${width}.png`);}
  results.push({kind:'material-width-scheme',look,width,scheme,...info,errors:[...errors]});
 }
 for(const look of ['observatory','letterpress','felt']){
  await metrics(390,1100);await navigate(look);
  for(const state of ['empty','loading','error']){
   const info=await ev(`(()=>{const c=document.querySelector('#state');c.value='${state}';c.dispatchEvent(new Event('change'));return {state:document.body.dataset.state,text:document.querySelector('#state-message').textContent,overflow:document.documentElement.scrollWidth>document.documentElement.clientWidth};})()`);
   assert(info.state===state&&!info.overflow,'State check failed');await shot(`state-${look}-${state}.png`);results.push({kind:'simulated-state',look,...info});
  }
  await ev(`document.querySelector('#recover').click()`);assert(await ev('document.body.dataset.state')==='ready','Recovery failed');
  await ev(`document.querySelector('#state').focus()`);await key('Tab','Tab',9);
  const focus=await ev(`({tag:document.activeElement.tagName,outline:getComputedStyle(document.activeElement).outlineStyle})`);
  assert(focus.outline==='solid','No visible keyboard focus');results.push({kind:'keyboard-focus',look,...focus});
 }
 await navigate('felt');await ev(`document.querySelector('.studio-tile').focus()`);await key(' ','Space',32);
 const selected=await ev(`document.querySelector('.studio-tile').getAttribute('aria-pressed')`);assert(selected==='true','Space did not select tile');
 await ev(`document.querySelector('#reset').click()`);assert(await ev(`document.querySelectorAll('.studio-tile[aria-pressed="true"]').length`)===0,'Reset failed');results.push({kind:'keyboard-tile-and-reset',passed:true});
 await navigate('letterpress');await ev(`document.querySelector('[data-abstract]').focus()`);await key('Enter','Enter',13);
 assert(await ev(`document.querySelector('[data-abstract]').getAttribute('aria-expanded')`)==='true','Enter did not expand abstract');results.push({kind:'keyboard-abstract',passed:true});
 await navigate('observatory');await ev(`document.querySelector('summary').focus()`);await key('Enter','Enter',13);
 assert(await ev(`document.querySelector('details').open`),'Enter did not expand data table');
 const ranges=await ev(`({min,max,span,rows:days.length,widths:days.map(d=>(d.high-d.low)/span*100)})`);
 assert(ranges.min===-2&&ranges.max===21&&ranges.rows===7&&ranges.widths.every(w=>w>=0&&w<=100),'Range domain failed');results.push({kind:'range-domain-and-keyboard-table',...ranges});
 // Both OS reduced motion and explicit opt-out: test a live shimmer and draw.
 await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'no-preference'}]},s);
 await ev(`document.body.dataset.motion='none';document.body.insertAdjacentHTML('beforeend','<div class="space-reveal">Motion fixture</div><div class="space-skeleton space-skeleton--shimmer"></div>')`);await delay(100);
 const motion=await ev(`({running:document.getAnimations().filter(a=>a.playState==='running').length,drawOffset:getComputedStyle(document.querySelector('.space-draw')).strokeDashoffset})`);
 assert(motion.running===0&&parseFloat(motion.drawOffset)===0,'Motion opt-out failed: '+JSON.stringify(motion));results.push({kind:'explicit-motion-opt-out',...motion});
 for(const look of ['observatory','letterpress','felt']){
  await metrics(1440,1800);await navigate(look);await ev(`document.documentElement.style.zoom='2'`);
  const zoom=await ev(`({width:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth})`);
  assert(zoom.scroll<=zoom.width,'CSS zoom reflow failed');results.push({kind:'css-200-percent-geometry-not-browser-zoom',look,...zoom});
 }
 await navigate('letterpress');
 const aliases=await ev(`(()=>{const panel=document.querySelector('.space-panel'),body=getComputedStyle(document.body);const before=getComputedStyle(panel).backgroundColor;document.documentElement.style.setProperty('--space-panel-bg','#123456');document.documentElement.style.setProperty('--space-display-font','monospace');document.querySelector('h1').classList.add('space-display');return {before,card:body.getPropertyValue('--space-card').trim(),custom:getComputedStyle(panel).backgroundColor,font:getComputedStyle(document.querySelector('h1')).fontFamily};})()`);
 assert(aliases.before==='rgb(251, 245, 231)'&&aliases.custom==='rgb(18, 52, 86)'&&aliases.font==='monospace','Inherited token override failed');results.push({kind:'theme-alias-and-inherited-override',...aliases});
 await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-transparency',value:'reduce'}]},s);
 const transparency=await ev(`getComputedStyle(document.querySelector('.space-panel')).backdropFilter`);
 assert(transparency==='none','Reduced transparency failed');results.push({kind:'reduced-transparency',passed:true});
 await writeFile(resolve(dir,'verification.json'),JSON.stringify(results,null,2));
 const viewport=results.filter(r=>r.kind==='material-width-scheme');
 console.log(JSON.stringify({checks:results.length,passed:true,viewportChecks:viewport.length,minTarget:Math.min(...viewport.map(r=>r.minTarget)),minTokenContrast:Math.min(...viewport.flatMap(r=>Object.values(r.contrast))),maxHorizontalOverflow:Math.max(...viewport.map(r=>r.scrollWidth-r.width)),report:resolve(dir,'verification.json'),scope:'Local synthetic specimen; not Desktop or chat-generated qualification'},null,2));
 await send('Target.closeTarget',{targetId});
} finally {if(ws)ws.close();chrome.kill('SIGKILL');chrome.stderr.destroy();}
