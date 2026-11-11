// Sky Window — premium showcase reference (data dashboard).
// Concept: one window per city. The sky inside each window is computed from the
// live weather code and the city's local hour; a generated skyline silhouette
// sits on the horizon. No kit CSS, no framework: the kit is optional.
//
// Data: public Open-Meteo forecast through space.net.fetch (the host bridge).
// Standalone preview uses browser fetch. Failures never invent current values;
// a deterministic sample is explicitly opt-in and labelled as not live.

const space = window.space;
const $ = id => document.getElementById(id);
const CITIES = [
  {id: 'chicago', name: 'Chicago', lat: 41.8781, lon: -87.6298},
  {id: 'lisbon', name: 'Lisbon', lat: 38.7223, lon: -9.1393},
  {id: 'tokyo', name: 'Tokyo', lat: 35.6762, lon: 139.6503}
];
const motion = matchMedia('(prefers-reduced-motion: reduce)');
let lead = 'chicago';
let state = {mode: 'loading', data: {}, retrieved: null, problem: null};

// ---------- weather vocabulary ----------
const kind = code => code === 0 ? 'clear' : code <= 2 ? 'fair' : code === 3 ? 'overcast'
  : code <= 48 ? 'fog' : code <= 67 || (code >= 80 && code <= 82) ? 'rain'
  : code <= 77 || code === 85 || code === 86 ? 'snow' : 'storm';
const WORDS = {clear: 'Clear', fair: 'Partly cloudy', overcast: 'Overcast', fog: 'Fog',
  rain: 'Rain', snow: 'Snow', storm: 'Thunderstorm'};

// Sky colour from condition + local hour. Returns [zenith, middle, horizon].
function skyColours(k, hour) {
  const phase = hour < 5 || hour >= 20 ? 'night' : hour < 7 ? 'dawn' : hour < 17 ? 'day' : 'dusk';
  const base = {
    night: ['#060b1f', '#101a3a', '#27305a'],
    dawn: ['#1f2f63', '#7a5a8e', '#f0a27a'],
    day: ['#1f5fa8', '#3f86c9', '#9cc8e6'],
    dusk: ['#1a2350', '#8a3f6b', '#f2925b']
  }[phase];
  const dull = {clear: 0, fair: .15, overcast: .55, fog: .7, rain: .6, snow: .45, storm: .75}[k];
  const grey = phase === 'night' ? '#1b2030' : k === 'snow' ? '#b9c3cf' : '#56606e';
  return {phase, stops: base.map(c => mix(c, grey, dull))};
}
function mix(a, b, t) {
  const p = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
  const [x, y] = [p(a), p(b)];
  return '#' + x.map((v, i) => Math.round(v + (y[i] - v) * t).toString(16).padStart(2, '0')).join('');
}
// Temperature → colour on a cool-to-warm scale (also used by the ribbon).
const tempColour = t => {
  const stops = [[-10, '#6c8cff'], [0, '#7fd3ff'], [10, '#a6f0c6'], [18, '#ffe08a'], [26, '#ff9a5a'], [34, '#ff5a6e']];
  for (let i = 1; i < stops.length; i++) if (t <= stops[i][0]) {
    const [t0, c0] = stops[i - 1], [t1, c1] = stops[i];
    return mix(c0, c1, Math.max(0, (t - t0) / (t1 - t0)));
  }
  return stops.at(-1)[1];
};

// ---------- data ----------
const url = c => {
  const u = new URL('https://api.open-meteo.com/v1/forecast');
  Object.entries({latitude: c.lat, longitude: c.lon, timezone: 'auto', forecast_days: 7,
    current: 'temperature_2m,apparent_temperature,weather_code,is_day,wind_speed_10m,relative_humidity_2m',
    daily: 'weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset'
  }).forEach(([k, v]) => u.searchParams.set(k, v));
  return u.toString();
};
async function getJSON(href) {
  if (space?.net) {
    const r = await space.net.fetch(href, {as: 'json'});
    if (r.status !== 200) throw Object.assign(new Error('Open-Meteo returned ' + r.status), {code: 'http'});
    return r.json;
  }
  const r = await fetch(href, {credentials: 'omit', referrerPolicy: 'no-referrer'});
  if (!r.ok) throw Object.assign(new Error('Open-Meteo returned ' + r.status), {code: 'http'});
  return r.json();
}
function sample() {
  // Synthetic, deterministic, labelled. Not current weather.
  const make = (code, hour, t, lo, hi, offset) => ({
    sample: true, utc_offset_seconds: offset,
    current: {time: `2026-01-01T${String(hour).padStart(2, '0')}:00`, temperature_2m: t, apparent_temperature: t - 2,
      weather_code: code, is_day: hour >= 7 && hour < 17 ? 1 : 0, wind_speed_10m: 14, relative_humidity_2m: 62},
    daily: {time: [...Array(7)].map((_, i) => `2026-01-0${i + 1}`),
      weather_code: [code, 2, 61, 3, 0, 1, 80],
      temperature_2m_min: lo.map(Number), temperature_2m_max: hi.map(Number),
      precipitation_probability_max: [10, 20, 70, 40, 5, 10, 55],
      sunrise: [...Array(7)].map(() => '2026-01-01T07:10'), sunset: [...Array(7)].map(() => '2026-01-01T16:50')}
  });
  return {
    chicago: make(1, 6, 3, [-2, 0, 2, 1, -3, -1, 2], [5, 7, 6, 4, 2, 6, 8], -21600),
    lisbon: make(0, 12, 17, [11, 12, 12, 13, 11, 10, 12], [18, 19, 17, 16, 18, 19, 17], 0),
    tokyo: make(3, 21, 11, [7, 8, 9, 6, 5, 7, 9], [14, 15, 13, 12, 14, 16, 15], 32400)
  };
}
function validate(d) {
  if (!d || !d.current || !d.daily || !Array.isArray(d.daily.time)) throw Error('Invalid forecast');
  if (!d.daily.time.length) return false;
  const keys=['temperature_2m_min','temperature_2m_max','weather_code','precipitation_probability_max'];
  if (d.daily.time.length !== 7 || keys.some(k=>!Array.isArray(d.daily[k]) || d.daily[k].length!==7 || d.daily[k].some(v=>!Number.isFinite(v)))) throw Error('Incomplete forecast');
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(d.current.time) || ['temperature_2m','apparent_temperature','weather_code','wind_speed_10m','relative_humidity_2m'].some(k=>!Number.isFinite(d.current[k]))) throw Error('Invalid current conditions');
  if (d.daily.temperature_2m_min.some((v,i)=>v>d.daily.temperature_2m_max[i]) || d.daily.precipitation_probability_max.some(v=>v<0||v>100) || !d.daily.sunset?.every(v=>typeof v==='string')) throw Error('Invalid ranges');
  return true;
}
let busy=false;
async function load() {
  if(busy)return; busy=true;
  $('reload').setAttribute('aria-disabled','true');
  document.querySelector('.room').setAttribute('aria-busy','true');
  const hadData=Object.keys(state.data).length>0;
  $('status').textContent=hadData?'Refreshing… previous forecast stays visible.':'Loading the public forecast…';
  try {
    const results=await Promise.all(CITIES.map(c=>getJSON(url(c))));
    const valid=results.map(validate);
    if(valid.some(v=>!v)) {
      if(hadData) throw Error('The source returned no forecast');
      state={mode:'empty',data:{},retrieved:null,problem:null};
      $('status').textContent='The source returned no forecast days. Refresh to try again.';
    } else {
      state={mode:'live',data:Object.fromEntries(CITIES.map((c,i)=>[c.id,results[i]])),retrieved:new Date(),problem:null};
      $('status').textContent='Live public forecast · temperatures in °C';
    }
  } catch(e) {
    state={...state,mode:hadData?(state.mode==='sample'?'sample':'stale'):'error',problem:e.code==='not_granted'?'off':'failed'};
    $('status').textContent=e.code==='not_granted'?'Internet access is off. '+(hadData?'Previous values remain; they are not current.':'No live forecast loaded. Enable access in the host, then refresh.'):(hadData?'Refresh failed. Previous values remain; check the retrieval time.':'Could not load Open-Meteo. Refresh to retry, or explore a labelled synthetic sample.');
  } finally {
    busy=false; $('reload').setAttribute('aria-disabled','false');
    document.querySelector('.room').setAttribute('aria-busy','false');draw();
  }
}

// ---------- rendering ----------
const el = (tag, props = {}, ...kids) => {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) k === 'class' ? n.className = v : k.startsWith('on') ? n.addEventListener(k.slice(2), v) : k === 'style' ? n.style.cssText = v : n.setAttribute(k, v);
  n.append(...kids.filter(k => k !== null && k !== undefined));
  return n;
};
const svg = (tag, attrs = {}, ...kids) => {
  const n = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  n.append(...kids); return n;
};
const localHour = d => Number(d.current.time.slice(11, 13)) + Number(d.current.time.slice(14, 16)) / 60;
const fmtHour = h => `${String(Math.floor(h)).padStart(2, '0')}:${String(Math.round((h % 1) * 60)).padStart(2, '0')}`;

function pane(c) {
  const d = state.data[c.id];
  const k = kind(d.current.weather_code);
  const hour = localHour(d);
  const {phase, stops} = skyColours(k, hour);
  const lo = d.daily.temperature_2m_min[0], hi = d.daily.temperature_2m_max[0], now = d.current.temperature_2m;
  // Sun/moon travels an arc across the pane: 06:00 left → 18:00 right (moon at night).
  const arcT = phase === 'night' ? ((hour + 6) % 24) / 12 : (hour - 6) / 12;
  const x = Math.min(92, Math.max(8, arcT * 100)), y = 58 - Math.sin(Math.PI * Math.min(1, Math.max(0, arcT))) * 44;
  const isLead = c.id === lead;
  const range = Math.max(1, hi - lo), pos = Math.min(100, Math.max(0, (now - lo) / range * 100));
  const button = el('button', {class: 'pane-hit', type: 'button', 'aria-pressed': String(isLead),
    'aria-label': `${c.name}: ${WORDS[k]}, ${Math.round(now)} degrees. Show its week.`, onclick: () => { lead = c.id; draw(true); }});
  return el('article', {class: `pane ${isLead ? 'is-lead' : ''}`, 'data-city': c.id, 'data-phase': phase, 'data-kind': k,
      style: `--z:${stops[0]};--m:${stops[1]};--h:${stops[2]};--orb-x:${x}%;--orb-y:${y}%`},
    el('div', {class: 'sky', 'aria-hidden': 'true'},
      el('div', {class: 'stars'}), el('div', {class: 'orb'}), el('div', {class: 'clouds'}), el('div', {class: 'weather'}),
      el('div', {class: 'skyline'}), el('div', {class: 'windows-lit'})),
    el('div', {class: 'reading'},
      el('h3', {}, c.name, el('span', {class: 'local'}, ` ${fmtHour(hour)} local`)),
      el('p', {class: 'temp'}, el('span', {class: 'num', 'data-to': String(Math.round(now))}, String(Math.round(now))), el('span', {class: 'deg'}, '°C')),
      el('p', {class: 'cond'}, WORDS[k], el('span', {class: 'feels'}, ` · feels ${Math.round(d.current.apparent_temperature)}°`)),
      el('div', {class: 'range', role: 'img', 'aria-label': `Today ${Math.round(lo)} to ${Math.round(hi)} degrees; now ${Math.round(now)}`, style: `--lo:${tempColour(lo)};--hi:${tempColour(hi)};--pos:${pos}%`},
        el('span', {class: 'lo'}, `${Math.round(lo)}°`), el('span', {class: 'bar'}, el('i', {})), el('span', {class: 'hi'}, `${Math.round(hi)}°`)),
      isLead ? el('dl', {class: 'facts'},
        el('div', {}, el('dt', {}, 'Rain chance today'), el('dd', {}, `${d.daily.precipitation_probability_max[0] ?? '—'}%`)),
        el('div', {}, el('dt', {}, 'Wind'), el('dd', {}, `${Math.round(d.current.wind_speed_10m)} km/h`)),
        el('div', {}, el('dt', {}, 'Humidity'), el('dd', {}, `${d.current.relative_humidity_2m}%`)),
        el('div', {}, el('dt', {}, 'Sunset'), el('dd', {}, d.daily.sunset[0].slice(11, 16)))) : null),
    button);
}

const GLYPH = {
  clear: 'M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10Zm0-5v3m0 14v3M2 12h3m14 0h3M4.9 4.9l2.1 2.1m10 10 2.1 2.1M4.9 19.1 7 17m10-10 2.1-2.1',
  fair: 'M8 6a4 4 0 0 1 7.5 1.5M4 4l1.4 1.4M8 1v2M17 18H7a4 4 0 1 1 1-7.9A5 5 0 0 1 17.5 12 3 3 0 0 1 17 18Z',
  overcast: 'M17 19H7a4.5 4.5 0 1 1 1.2-8.8A5.5 5.5 0 0 1 18.4 12 3.5 3.5 0 0 1 17 19Z',
  fog: 'M4 9h16M2 13h20M5 17h14',
  rain: 'M17 14H7a4 4 0 1 1 1-7.9A5 5 0 0 1 17.5 8 3 3 0 0 1 17 14ZM8 17l-1 3m5-3-1 3m5-3-1 3',
  snow: 'M17 13H7a4 4 0 1 1 1-7.9A5 5 0 0 1 17.5 7 3 3 0 0 1 17 13Zm-9 4h.01M12 19h.01M16 17h.01',
  storm: 'M17 13H7a4 4 0 1 1 1-7.9A5 5 0 0 1 17.5 7 3 3 0 0 1 17 13Zm-5 1-2 4h4l-2 4'
};

function ribbon(c) {
  const d=state.data[c.id],W=Math.max(640,Math.min(1200,$('ribbon').clientWidth)),H=246,padX=48;
  const lows=d.daily.temperature_2m_min,highs=d.daily.temperature_2m_max;
  const min=Math.floor(Math.min(...lows)/5)*5-5,max=Math.ceil(Math.max(...highs)/5)*5+5;
  const x=i=>padX+i*(W-padX*2)/6,y=t=>46+(max-t)/(max-min)*142;
  const day=t=>new Date(t+'T12:00:00Z').toLocaleDateString('en-GB',{weekday:'short',month:'short',day:'numeric',timeZone:'UTC'});
  const art=svg('svg',{viewBox:`0 0 ${W} ${H}`,width:'100%',class:'ribbon-svg','aria-hidden':'true','data-domain-min':min,'data-domain-max':max});
  for(let tick=min;tick<=max;tick+=5){art.append(svg('line',{x1:28,x2:W-16,y1:y(tick),y2:y(tick),stroke:'#68748e','stroke-opacity':'.4'}),svg('text',{x:22,y:y(tick)+4,'text-anchor':'end',fill:'#b4bdd3','font-size':11},String(tick)));}
  d.daily.time.forEach((t,i)=>{
    art.append(svg('text',{x:x(i),y:20,'text-anchor':'middle',class:'dname'},day(t)),
      svg('line',{x1:x(i),x2:x(i),y1:y(highs[i]),y2:y(lows[i]),stroke:tempColour((lows[i]+highs[i])/2),'stroke-width':12,'stroke-linecap':'round'}),
      svg('text',{x:x(i)+12,y:y(highs[i])+4,class:'hi'},`${Math.round(highs[i])}°`),
      svg('text',{x:x(i)+12,y:y(lows[i])+4,class:'lo'},`${Math.round(lows[i])}°`),
      svg('rect',{x:x(i)-14,y:210,width:28,height:6,rx:3,class:'rain-track'}),
      svg('rect',{x:x(i)-14,y:210,width:28*d.daily.precipitation_probability_max[i]/100,height:6,rx:3,class:'rain-fill'}),
      svg('text',{x:x(i),y:238,'text-anchor':'middle',class:'rain'},`${d.daily.precipitation_probability_max[i]}%`));
  });
  $('ribbon').replaceChildren(art);
  $('ribbon').setAttribute('aria-label',`${c.name}, daily low to high, degrees Celsius. Shared scale ${min} to ${max}. Exact values in Daily values.`);
  $('week-city').textContent=c.name;
  $('days').replaceChildren(...d.daily.time.map((t,i)=>el('tr',{},el('th',{'scope':'row'},t),el('td',{},WORDS[kind(d.daily.weather_code[i])]),el('td',{},lows[i].toFixed(1)),el('td',{},highs[i].toFixed(1)),el('td',{},String(d.daily.precipitation_probability_max[i])))));
}

function draw(fromClick = false) {
  $('sample').hidden=state.mode==='live';
  document.body.dataset.state=state.mode;
  if(!Object.keys(state.data).length){
    const empty=state.mode==='empty';
    $('windows').replaceChildren(el('section',{class:'is-empty'},el('h2',{},empty?'No forecast days returned':'The windows are waiting'),el('p',{},empty?'No values have been invented. Try refreshing the public forecast.':'No current values are available. Your next refresh will try Open-Meteo again.')));
    $('ribbon').replaceChildren();$('ribbon').setAttribute('aria-label','No forecast available');$('week-city').textContent='No forecast';$('days').replaceChildren();
    $('source').textContent='No live data loaded';return;
  }
  const ordered = [CITIES.find(c => c.id === lead), ...CITIES.filter(c => c.id !== lead)];
  const wrap = $('windows');
  wrap.replaceChildren(...ordered.map(pane));
  wrap.dataset.mode = state.mode;
  ribbon(ordered[0]);
  if (fromClick) wrap.querySelector('.is-lead .pane-hit')?.focus({preventScroll: true});
  const src = $('source');
  src.replaceChildren();
  if (state.mode === 'sample') src.append('Synthetic sample sky · illustrative values, not current weather');
  else {
    const a = el('a', {href: 'https://open-meteo.com/', target: '_blank', rel: 'noopener noreferrer'}, 'Open-Meteo');
    src.append('Forecast from ', a, ` · updated ${state.retrieved.toISOString().replace('T',' ').slice(0,16)+' UTC'}`);
  }
  $('clock').textContent = state.mode === 'sample' ? 'Synthetic sample · not live' : state.mode === 'stale' ? 'Previous forecast · refresh failed' : 'Three public city forecasts';
}

$('reload').addEventListener('click',load);
$('sample').onclick=()=>{if(busy)return;state={mode:'sample',data:sample(),retrieved:null,problem:null};$('status').textContent='Synthetic sample · January 2026 · not current weather';draw();};
$('motion').onclick=()=>{const paused=document.body.dataset.motion!=='none';document.body.dataset.motion=paused?'none':'';$('motion').setAttribute('aria-pressed',String(paused));$('motion').textContent=paused?'Resume sky motion':'Pause sky motion';};

let resizeTimer;
addEventListener('resize', () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(() => state.data[lead] && ribbon(CITIES.find(c => c.id === lead)), 150); });
load();
