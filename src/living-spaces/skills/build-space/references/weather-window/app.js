// Public, credential-free forecast. No kit, framework, storage or permission UI.
const cities = {london:{name:'London',lat:51.5072,lon:-.1276},copenhagen:{name:'Copenhagen',lat:55.6761,lon:12.5683},tokyo:{name:'Tokyo',lat:35.6762,lon:139.6503}};
const $ = id => document.getElementById(id);
const describe = code => code === 0 ? 'Clear sky' : code <= 3 ? 'Partly cloudy' : code <= 48 ? 'Foggy' : code <= 67 ? 'Rain expected' : code <= 77 ? 'Snow expected' : code <= 82 ? 'Rain showers' : 'Wintry or stormy conditions';
let selected='london', active=null, last=null, sequence=0;
const liveAvailable = !window.space; // Standalone only until a qualified host API lands.
if (!liveAvailable) {
  $('sample').classList.add('weather-primary');
  $('refresh').classList.remove('weather-primary');
  $('refresh').disabled=true;
  $('refresh').textContent=window.space?.meta?.network==='off' ? 'Internet is off' : 'Live unavailable';
}
const time = value => new Date(value.endsWith('Z') ? value : value+'Z');
const hh = value => time(value).toLocaleTimeString('en-GB',{timeZone:'UTC',hour:'2-digit',minute:'2-digit'});
const text = (id,value) => {$(id).textContent=value;};
const node = (tag,attrs={},value) => {const n=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,v);if(value!==undefined)n.textContent=value;return n;};
function render(data,city,sample=false){
  if(!Number.isFinite(data.current?.temperature_2m) || !Array.isArray(data.hourly?.time)) throw new Error('Forecast data is incomplete.');
  const start=time(data.current.time).getTime();
  const values=data.hourly.time.map((t,i)=>({t,temp:data.hourly.temperature_2m?.[i],rain:data.hourly.precipitation_probability?.[i]})).filter(v=>time(v.t).getTime()>=start && Number.isFinite(v.temp)).slice(0,12);
  if(values.length!==12) throw new Error('Twelve hourly values are not available.');
  last={data,city,sample};
  text('city',city.name);text('conditions',describe(data.current.weather_code));text('temperature',Math.round(data.current.temperature_2m));
  text('observed',(sample?'Synthetic sample · ':'Forecast valid · ')+hh(data.current.time)+' UTC');
  text('table-caption',`${city.name} · ${sample?'synthetic sample':'Open-Meteo forecast'} · ${data.current.time.slice(0,10)} · UTC`);
  $('hourly').replaceChildren(...values.map(v=>{const tr=document.createElement('tr');for(const val of [hh(v.t),v.temp.toFixed(1),Number.isFinite(v.rain)?v.rain:'Not available']){const td=document.createElement('td');td.textContent=val;tr.append(td);}return tr;}));
  // True linear temperature scale with labelled extent; no invented smooth curve.
  const low=Math.floor(Math.min(...values.map(v=>v.temp))/5)*5-5;
  const high=Math.ceil(Math.max(...values.map(v=>v.temp))/5)*5+5;
  const width = Math.min(550, Math.max(260, $('chart').clientWidth));
  const x=i=>40+i*(width-64)/11,y=v=>190-(v-low)/(high-low)*150;
  const svg=node('svg',{viewBox:`0 0 ${width} 240`,role:'img','aria-labelledby':'forecast-title forecast-desc'});
  svg.append(node('title',{id:'forecast-title'},`${city.name}: temperature in degrees Celsius, next twelve hours`),node('desc',{id:'forecast-desc'},`Hourly forecast ranges from ${Math.min(...values.map(v=>v.temp))} to ${Math.max(...values.map(v=>v.temp))} degrees Celsius. Exact values in the following table.`));
  for(const v of [low,(low+high)/2,high]){svg.append(node('line',{x1:40,x2:width-24,y1:y(v),y2:y(v),class:'grid'}),node('text',{x:28,y:y(v)+4,'text-anchor':'end',class:'axis'},v));}
  for(const i of (width < 440 ? [0,6,11] : [0,3,6,9,11])) svg.append(node('text',{x:x(i),y:220,'text-anchor':'middle',class:'axis'},hh(values[i].t)));
  svg.append(node('polyline',{points:values.map((v,i)=>`${x(i)},${y(v.temp)}`).join(' '),class:'curve'}));
  const peak=values.reduce((best,v,i)=>v.temp>values[best].temp?i:best,0);
  svg.append(node('circle',{cx:x(peak),cy:y(values[peak].temp),r:6,class:'point'}),node('text',{x:x(peak),y:y(values[peak].temp)-16,'text-anchor':'middle',class:'point-label'},values[peak].temp.toFixed(1)+'°'));
  $('chart').replaceChildren(svg);
  $('provenance').replaceChildren();
  if(sample) text('provenance','Synthetic forecast sample · illustrative values, not current weather');
  else {const a=document.createElement('a');a.href='https://open-meteo.com/';a.target='_blank';a.rel='noopener noreferrer';a.textContent='Open-Meteo';$('provenance').append('Public forecast from ',a,' · retrieved '+new Date().toLocaleTimeString('en-GB',{timeZone:'UTC'})+' UTC');}
}
async function load(){
  const id=++sequence,city=cities[selected];active?.abort();active=new AbortController();
  const timer=setTimeout(()=>active?.abort(),12000);$('refresh').disabled=true;$('chart').setAttribute('aria-busy','true');
  text('status',`Loading ${city.name} from Open-Meteo…${last?' Previous forecast stays visible.':''}`);
  try{
    if(window.space?.meta?.network==='off') {const e=new Error('Internet is off for this Space. Local sample exploration is still available.');e.off=true;throw e;}
    // A standalone browser can demonstrate the public source. A hosted Space
    // must use the network API qualified by its host, not bypass its policy.
    if(window.space) {const e=new Error('Live forecasts are not available in this runtime. Explore the labelled local sample.');e.unavailable=true;throw e;}
    const u=new URL('https://api.open-meteo.com/v1/forecast');
    for(const [k,v] of Object.entries({latitude:city.lat,longitude:city.lon,current:'temperature_2m,weather_code',hourly:'temperature_2m,precipitation_probability',forecast_days:2,timezone:'GMT'}))u.searchParams.set(k,v);
    const response=await fetch(u,{signal:active.signal,credentials:'omit',referrerPolicy:'no-referrer'});
    if(!response.ok)throw new Error('Forecast source returned '+response.status);
    const data=await response.json();if(id!==sequence)return;render(data,city);text('status','Live public forecast loaded. No account or location permission used.');
  }catch(e){if(id!==sequence)return;text('status',e.off || e.unavailable ? e.message :`${city.name} couldn’t load. ${last?`Still showing ${last.sample?'the sample for ':''}${last.city.name}. `:''}The source or connection may be unavailable, or internet access may be off. Retry or explore the labelled sample.`);}
  finally{clearTimeout(timer);if(id===sequence){$('refresh').disabled=!liveAvailable;$('chart').removeAttribute('aria-busy');}}
}
for(const b of document.querySelectorAll('[data-city]'))b.onclick=()=>{selected=b.dataset.city;for(const c of document.querySelectorAll('[data-city]'))c.setAttribute('aria-pressed',String(c===b));load();};
$('refresh').onclick=load;
$('sample').onclick=()=>{
  sequence++;active?.abort();$('refresh').disabled=!liveAvailable;$('chart').removeAttribute('aria-busy');
  const base=new Date();base.setUTCMinutes(0,0,0);const times=Array.from({length:24},(_,i)=>new Date(base.getTime()+i*3600000).toISOString());
  render({current:{time:times[0],temperature_2m:14,weather_code:2},hourly:{time:times,temperature_2m:[14,15,17,18,18,17,16,15,13,12,11,10,10,9,8,8,9,10,11,12,13,14,14,15],precipitation_probability:Array.from({length:24},(_,i)=>i<6?10:i<12?35:20)}},cities[selected],true);
  text('status','Synthetic sample. These values are illustrative, not current weather. '+(liveAvailable ? 'Load forecast to return to live data.' : 'Local exploration works without live access.'));
};
let resizeTimer;
window.addEventListener('resize',()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(()=>{if(last)render(last.data,last.city,last.sample);},120);});
load();
