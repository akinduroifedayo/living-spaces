import {draw,palettes} from './art.js';
const $=s=>document.querySelector(s),canvas=$('#art'),reduce=matchMedia('(prefers-reduced-motion: reduce)');
const initial={seed:42,palette:'tidal',phase:0};let state={...initial},saved=null,undo=null,rev=0,ready=false,busy=false,dirty=false,paused=reduce.matches,raf=0,last=0;
const valid=d=>d&&Number.isSafeInteger(d.seed)&&d.seed>=1&&d.seed<=999999&&Object.hasOwn(palettes,d.palette)&&Number.isFinite(d.phase)&&d.phase>=0&&d.phase<100000;
const unpack=r=>Object.fromEntries(['seed','palette','phase'].map(k=>[k,window.space.field(r,k)]));
const status=t=>$('#status').textContent=t;
function paint(){draw(canvas,state);}
function describe(){canvas.setAttribute('aria-label',`Original abstract weave in ${palettes[state.palette].description}. Variation ${state.seed}. ${paused?'Still composition.':'Slowly moving ribbons.'}`);}
function size(){const r=canvas.getBoundingClientRect(),d=Math.min(devicePixelRatio||1,1.5);canvas.width=Math.round(r.width*d);canvas.height=Math.round(r.height*d);paint();}
function tick(now){if(paused||document.hidden){raf=0;last=0;return;}if(!last)last=now;if(now-last>=50){state.phase=(state.phase+Math.min(now-last,100)/1000)%100000;last=now;paint();}raf=requestAnimationFrame(tick);}
function motion(){cancelAnimationFrame(raf);raf=0;last=0;$('#motion').textContent=paused?'Resume motion':'Pause motion';$('#motion-note').textContent=paused?(reduce.matches?'Still · reduced motion':'Motion paused'):'Motion on';paint();describe();if(!paused&&!document.hidden)raf=requestAnimationFrame(tick);}
function ui(){document.body.dataset.state=busy?'saving':ready?'ready':'loading';$('#edition').textContent=`Variation ${state.seed}`;for(const r of document.querySelectorAll('[name=palette]'))r.checked=r.value===state.palette;$('#save').setAttribute('aria-disabled',String(!ready||busy));$('#save').textContent=busy?'Keeping…':saved?'Replace kept composition':'Keep composition';$('#motion').setAttribute('aria-disabled',String(busy));$('#undo').disabled=!undo||busy;$('#vary').disabled=busy;for(const r of document.querySelectorAll('[name=palette]'))r.disabled=busy;$('#restore').hidden=!saved||!ready;$('#restore').disabled=busy;paint();describe();}
function change(next){if(busy)return;undo={...state};state=next;dirty=true;status(ready?'Not kept yet. Keep composition to return to this weave.':'Preview only. Saved composition has not loaded.');ui();}
$('#vary').onclick=()=>change({...state,seed:(state.seed*1664525+1013904223)%999999+1,phase:0});
$('#undo').onclick=()=>{if(!undo||busy)return;state=undo;undo=null;dirty=true;status('Previous composition restored. Not kept yet.');ui();};
for(const r of document.querySelectorAll('[name=palette]'))r.onchange=()=>change({...state,palette:r.value});
$('#motion').onclick=()=>{if(busy)return;paused=!paused;if(!paused){dirty=true;if(saved)status('Playing a preview. The kept composition is unchanged.');}motion();};
reduce.addEventListener('change',()=>{if(reduce.matches){paused=true;motion();}});
document.addEventListener('visibilitychange',motion);
$('#restore').onclick=()=>{if(!saved||!ready||busy)return;undo={...state};state={...saved};dirty=false;paused=true;status('Saved composition restored. Motion paused.');ui();motion();};
async function load(){
 if(busy)return;ready=false;$('#retry').hidden=true;status('Loading saved composition…');ui();
 try{
  if(!window.space)throw Error('bridge');
  let r;try{r=await window.space.get('compositions','current');}catch(e){if(e.code!=='not_found')throw e;}
  if(r){const d=unpack(r);if(!valid(d))throw Error('invalid');saved=d;rev=r.rev;if(!dirty){state={...d};paused=true;}status(dirty?'Saved composition loaded. Your preview is unchanged.':'Saved composition loaded. Motion paused.');}
  else{rev=0;saved=null;status(dirty?'Not kept yet. Keep composition to save this preview.':'No saved composition yet. Make this one yours.');}
  ready=true;
 }catch(e){status(e.message==='invalid'?'Saved composition is unreadable. Preview is intact; saving is blocked to protect it. Retry loading.':'Could not load saved composition. Preview still works. Retry loading before saving.');$('#retry').hidden=false;}
 ui();motion();
}
$('#retry').onclick=load;
$('#save').onclick=async()=>{
 if(!ready||busy)return;
 const draft={...state};paused=true;motion();busy=true;status('Keeping this composition…');ui();
 try{
  await window.space.put('compositions','current',draft,{baseRev:rev});
  const r=await window.space.get('compositions','current'),d=unpack(r);
  if(!valid(d)||Object.keys(draft).some(k=>d[k]!==draft[k]))throw Error('readback');
  saved={...d};rev=r.rev;dirty=false;status('Composition kept and verified. It will return when you reopen.');
 }catch(e){
  // Never overwrite a concurrent change or retry an uncertain write blindly.
  ready=false;$('#retry').hidden=false;dirty=true;
  status(e.code==='conflict'?'Another view kept a composition first. Your preview is intact. Retry loading to see the saved version.':'Could not verify the save. Your preview is intact. Retry loading to check what was kept.');
 }finally{busy=false;ui();}
};
new ResizeObserver(size).observe(canvas);size();motion();load();
