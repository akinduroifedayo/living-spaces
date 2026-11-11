import {scoreStore} from './rounds.js';
const $ = id => document.getElementById(id);
const motion = matchMedia('(prefers-reduced-motion: reduce)');
const store = scoreStore(window.space);
const R = '#8a2432', O = '#c4892b', G = '#4d6a3a';
const FRUIT = {
  pear: {name: 'Pear', svg: `<path d="M50 22c-4 0-6 4-6 10 0 8-14 14-14 34a20 20 0 0 0 40 0c0-20-14-26-14-34 0-6-2-10-6-10Z" fill="${O}"/><path d="M50 22c1-6 4-9 8-10" stroke="${G}" stroke-width="3" fill="none" stroke-linecap="round"/><path d="M58 14c8-4 16 0 18 4-8 3-15 2-18-4Z" fill="${G}"/><path d="M40 70c2 8 8 12 14 12" stroke="${R}" stroke-width="2.5" fill="none" stroke-linecap="round" opacity=".7"/>`},
  cherry: {name: 'Cherries', svg: `<path d="M52 18c-2 16-10 30-20 40M52 18c4 16 10 28 18 36" stroke="${G}" stroke-width="3" fill="none" stroke-linecap="round"/><path d="M52 18c8-6 18-6 22 0-8 4-16 4-22 0Z" fill="${G}"/><circle cx="32" cy="68" r="15" fill="${R}"/><circle cx="68" cy="64" r="15" fill="${R}"/><path d="M26 62a7 7 0 0 1 6-5M62 58a7 7 0 0 1 6-5" stroke="#f3ead6" stroke-width="2.5" fill="none" stroke-linecap="round"/>`},
  lemon: {name: 'Lemon', svg: `<path d="M18 52c0-16 14-26 32-26s32 10 32 26-14 26-32 26-32-10-32-26Z" fill="${O}" transform="rotate(-18 50 52)"/><path d="M14 58l-4 2M86 46l4-2" stroke="${O}" stroke-width="5" stroke-linecap="round"/><path d="M34 44c6-6 16-8 24-6" stroke="#f3ead6" stroke-width="2.5" fill="none" stroke-linecap="round" opacity=".8"/><path d="M58 22c6-6 14-6 18-2-6 4-12 4-18 2Z" fill="${G}"/>`},
  plum: {name: 'Plum', svg: `<path d="M50 28c-18 0-28 14-28 28 0 16 12 26 28 26s28-10 28-26c0-14-10-28-28-28Z" fill="${R}"/><path d="M50 30c-4 14-4 34 0 50" stroke="#5e1420" stroke-width="2" fill="none"/><path d="M50 28c0-6 2-10 6-12" stroke="${G}" stroke-width="3" fill="none" stroke-linecap="round"/><path d="M56 16c10-6 20-2 22 4-10 4-18 2-22-4Z" fill="${G}"/><path d="M34 46a14 14 0 0 1 8-8" stroke="#f3ead6" stroke-width="2.5" fill="none" stroke-linecap="round" opacity=".75"/>`},
  fig: {name: 'Fig', svg: `<path d="M50 20c-6 6-8 12-12 18-8 10-16 18-16 30a28 28 0 0 0 56 0c0-12-8-20-16-30-4-6-6-12-12-18Z" fill="${G}"/><path d="M36 64c4-2 8 2 14 0s10-2 14 0" stroke="${O}" stroke-width="2.5" fill="none" stroke-linecap="round"/><ellipse cx="50" cy="70" rx="14" ry="9" fill="${R}"/><path d="M44 70h.1M50 67h.1M56 71h.1M48 74h.1" stroke="${O}" stroke-width="3" stroke-linecap="round"/>`},
  pomegranate: {name: 'Pomegranate', svg: `<circle cx="50" cy="56" r="27" fill="${R}"/><path d="M40 30l4-10 6 8 6-8 4 10Z" fill="${R}"/><path d="M42 30h16" stroke="#5e1420" stroke-width="2"/><path d="M36 46a16 16 0 0 1 10-8" stroke="#f3ead6" stroke-width="2.5" fill="none" stroke-linecap="round" opacity=".75"/><circle cx="58" cy="62" r="3" fill="${O}"/><circle cx="50" cy="68" r="3" fill="${O}"/><circle cx="62" cy="54" r="2.5" fill="${O}"/>`}
};
const KINDS = Object.keys(FRUIT);


let deck=[], open=[], found=new Set(), turns=0, startedAt=0, locked=false, rounds=[], pending=null, saving=false, historyFailed=false, mismatchTimer, winTimer;
const field=store.field;
function shuffle(a){ for(let i=a.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[a[i],a[j]]=[a[j],a[i]];} return a; }
function deal(focus=true){
  clearTimeout(mismatchTimer); clearTimeout(winTimer);
  deck=shuffle([...KINDS,...KINDS]); open=[]; found=new Set(); turns=0; startedAt=0; locked=false;
  $('win').hidden=true;
  $('board').replaceChildren(...deck.map((kind,i)=>{
    const b=document.createElement('button'); b.type='button'; b.className='card'; b.dataset.i=i;
    b.style.setProperty('--i',i); b.style.setProperty('--tilt',`${(Math.random()*3-1.5).toFixed(2)}deg`);
    b.setAttribute('aria-label',`Card ${i+1}, face down`);
    b.innerHTML=`<span class="inner"><span class="back" aria-hidden="true"></span><span class="face" aria-hidden="true"><svg viewBox="0 0 100 100">${FRUIT[kind].svg}</svg><em>${FRUIT[kind].name}</em></span></span>`;
    b.onclick=()=>flip(i); return b;
  }));
  $('board').classList.remove('dealt'); void $('board').offsetWidth; $('board').classList.add('dealt');
  paint('New deal. Find six pairs.'); if(focus) cardEl(0).focus();
}
const cardEl=i=>$('board').children[i];
function flip(i){
  if(locked||found.has(i)||open.includes(i))return;
  if(!startedAt) startedAt=performance.now();
  open.push(i); cardEl(i).classList.add('is-up'); cardEl(i).setAttribute('aria-label',`Card ${i+1}, ${FRUIT[deck[i]].name}`);
  if(open.length<2){ paint(`${FRUIT[deck[i]].name}. Choose another card.`); return; }
  turns++; const[a,b]=open;
  if(deck[a]===deck[b]){
    found.add(a);found.add(b);open=[];
    for(const n of[a,b]){cardEl(n).classList.add('is-found');cardEl(n).setAttribute('aria-label',`Card ${n+1}, ${FRUIT[deck[n]].name}, matched`);cardEl(n).setAttribute('aria-disabled','true');}
    paint(`Pair of ${FRUIT[deck[a]].name.toLowerCase()}. ${found.size/2} of 6 pairs.`);
    if(found.size===12) finish();
  }else{
    locked=true;paint('Not a pair. Remember these two.');
    mismatchTimer=setTimeout(()=>{for(const n of[a,b]){cardEl(n).classList.remove('is-up');cardEl(n).setAttribute('aria-label',`Card ${n+1}, face down`);} open=[];locked=false;paint('Choose another pair.');},1100);
  }
}
const best=()=>rounds.length?Math.min(...rounds.map(r=>field(r,'turns'))):null;
function paint(say){
  $('pairs').textContent=found.size/2; $('turns').textContent=turns;
  const b=best(); $('best').textContent=b===null?'—':`${b} turns`;
  $('pips').replaceChildren(...KINDS.map((k,n)=>{const e=document.createElement('span');e.className=n<found.size/2?'on':'';return e;}));
  $('pips').setAttribute('aria-label',`${found.size/2} of 6 pairs found`);
  if(say) $('instructions').textContent=say+' Tab to choose; Enter or Space to turn.';
  const recent=[...rounds].sort((a,b)=>String(field(b,'finished_at')).localeCompare(String(field(a,'finished_at')))).slice(0,8);
  const max=Math.max(12,...recent.map(r=>field(r,'turns')));
  $('history').replaceChildren(...recent.map(r=>{
    const t=field(r,'turns'),li=document.createElement('li');if(t===b)li.className='is-best';
    const date=new Date(field(r,'finished_at')).toLocaleDateString([],{month:'short',day:'numeric'});
    li.innerHTML=`<span class="when">${date}</span><span class="bar"><i style="width:${t/max*100}%"></i></span><span class="t">${t}</span>`;
    li.setAttribute('aria-label',`${date}, ${t} turns${t===b?', best':''}`);return li;
  }));
  $('history-empty').hidden=historyFailed||recent.length>0;
  $('retry').hidden=!(pending||historyFailed);$('retry').textContent=pending?'Retry saving round':'Retry scorecard';
  $('retry').setAttribute('aria-disabled',String(saving));
  $('restart').setAttribute('aria-disabled',String(!!pending||saving));
  $('again').setAttribute('aria-disabled',String(!!pending||saving));
}
async function finish(){
  const seconds=Math.max(0,Math.round((performance.now()-startedAt)/1000)),b=best();
  $('win-title').textContent='All six pairs';$('win-line').textContent=`${turns} turns · ${seconds} s`;
  $('win-best').textContent=b===null?'Your first finished round':turns<b?`New best, by ${b-turns} turns`:`Best: ${b} turns`;
  pending={id:'round-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2),data:{turns,seconds,finished_at:new Date().toISOString()}};
  winTimer=setTimeout(()=>{$('win').hidden=false;$('again').focus();},motion.matches?0:520);
  await saveRound();
}
async function saveRound(){
  if(saving||!pending)return; saving=true; paint();$('save').textContent='Saving round…';
  try{const r=await store.save(pending);rounds=[r,...rounds.filter(x=>x.id!==r.id)];pending=null;$('save').textContent='Round saved · verified in scorecard';}
  catch(e){$('save').textContent='Round not saved. Your result is kept here. Retry saving before dealing again.';}
  finally{saving=false;paint();}
}
async function loadHistory(){
  if(saving)return;saving=true;$('save').textContent='Loading scorecard…';paint();
  try{rounds=await store.list();historyFailed=false;$('save').textContent=rounds.length?'Scorecard loaded':'No finished rounds yet. Play your first.';}
  catch{historyFailed=true;$('save').textContent='Scorecard could not load. You can still play; retry to see saved rounds.';}
  finally{saving=false;paint();}
}
function restart(){if(pending||saving){$('save').textContent='Finish saving this round before dealing again.';return;}deal();}
$('again').onclick=restart;$('restart').onclick=restart;$('retry').onclick=()=>pending?saveRound():loadHistory();
$('instructions').setAttribute('role','status');
deal(false);loadHistory();
