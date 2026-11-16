const cities = {london:{name:'London',lat:51.5072,lon:-.1276},copenhagen:{name:'Copenhagen',lat:55.6761,lon:12.5683},tokyo:{name:'Tokyo',lat:35.6762,lon:139.6503}};
const $ = id => document.getElementById(id);
const describe = code => code === 0 ? 'Clear sky' : code <= 3 ? 'Partly cloudy' : code <= 48 ? 'Foggy' : code <= 67 ? 'Rain expected' : code <= 77 ? 'Snow expected' : code <= 82 ? 'Rain showers' : 'Wintry or stormy conditions';
let selected='london', last=null, sequence=0;
const liveAvailable = typeof window.space?.net?.fetch === 'function';
if (!liveAvailable) {
  $('sample').classList.add('weather-primary');
  $('refresh').classList.remove('weather-primary');
  $('refresh').disabled=true;
  $('refresh').textContent='Live unavailable';
}
const time = value => new Date(value.endsWith('Z') ? value : value+'Z');
const hh = value => time(value).toLocaleTimeString('en-GB',{timeZone:'UTC',hour:'2-digit',minute:'2-digit'});
const text = (id,value) => {$(id).textContent=value;};
const node = (tag,attrs={},value) => {const n=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,v);if(value!==undefined)n.textContent=value;return n;};
function render(data,city,sample=false,retrievedAt=null){
  if(!Number.isFinite(data.current?.temperature_2m) || !Array.isArray(data.hourly?.time)) throw new Error('Forecast data is incomplete.');
  const start=time(data.current.time).getTime();
  const values=data.hourly.time.map((t,i)=>({t,temp:data.hourly.temperature_2m?.[i],rain:data.hourly.precipitation_probability?.[i]})).filter(v=>time(v.t).getTime()>=start && Number.isFinite(v.temp)).slice(0,12);
  if(values.length!==12) throw new Error('Twelve hourly values are not available.');
  last={data,city,sample,retrievedAt:retrievedAt || (last?.data === data ? last.retrievedAt : new Date().toISOString())};
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
  else {const a=document.createElement('a');a.href='https://open-meteo.com/';a.target='_blank';a.rel='noopener noreferrer';a.textContent='Open-Meteo';$('provenance').append('Public forecast from ',a,' · retrieved '+new Date(last.retrievedAt).toLocaleString('en-GB',{timeZone:'UTC',dateStyle:'medium',timeStyle:'short'})+' UTC');}
}
const saved = async key => { try { return await window.space.get('forecasts', key); } catch { return null; } };
async function showSaved(key, city){
  const record = await saved(key);
  if(!record || last?.city === city && !last.sample) return false;
  render(record.data.forecast, city, false, record.data.retrievedAt);
  return true;
}
const timeout = ms => new Promise((_,reject)=>setTimeout(()=>reject(Object.assign(new Error('timeout'),{code:'timeout'})),ms));
async function load(){
  const id=++sequence,city=cities[selected];
  $('refresh').disabled=true;$('chart').setAttribute('aria-busy','true');
  text('status',`Loading ${city.name} from Open-Meteo…${last?' Previous forecast stays visible.':''}`);
  try{
    if(!liveAvailable) {const e=new Error('Live forecasts need the Space runtime. Explore the labelled local sample.');e.unavailable=true;throw e;}
    const u=new URL('https://api.open-meteo.com/v1/forecast');
    for(const [k,v] of Object.entries({latitude:city.lat,longitude:city.lon,current:'temperature_2m,weather_code',hourly:'temperature_2m,precipitation_probability',forecast_days:2,timezone:'GMT'}))u.searchParams.set(k,v);
    const response=await Promise.race([window.space.net.fetch(u.href,{as:'json'}),timeout(12000)]);
    if(id!==sequence)return;
    if(response.status<200 || response.status>=300)throw new Error('Forecast source returned '+response.status);
    render(response.json,city);text('status','Live public forecast loaded. No account or location permission used.');
    const prior = await saved(selected);
    window.space.put('forecasts', selected, {forecast: response.json, retrievedAt: last.retrievedAt}, {baseRev: prior?.rev ?? 0, merge: false}).catch(() => {});
  }catch(e){
    if(id!==sequence)return;
    if(liveAvailable && await showSaved(selected, city) && id!==sequence)return;
    const kept = last?`Still showing ${last.sample?'the sample for ':'the forecast saved for '}${last.city.name}. `:'';
    text('status', e.code==='not_granted' ? `Internet access is off for this Space. ${kept}Turn it on in Permissions to load live forecasts, or explore the labelled sample.`
      : e.unavailable ? e.message
      : `${city.name} couldn’t load. ${kept}The source or connection may be unavailable. Retry or explore the labelled sample.`);
  }
  finally{if(id===sequence){$('refresh').disabled=!liveAvailable;$('chart').removeAttribute('aria-busy');}}
}
for(const b of document.querySelectorAll('[data-city]'))b.onclick=()=>{selected=b.dataset.city;for(const c of document.querySelectorAll('[data-city]'))c.setAttribute('aria-pressed',String(c===b));load();};
$('refresh').onclick=load;
$('sample').onclick=()=>{
  sequence++;$('refresh').disabled=!liveAvailable;$('chart').removeAttribute('aria-busy');
  const base=new Date();base.setUTCMinutes(0,0,0);const times=Array.from({length:24},(_,i)=>new Date(base.getTime()+i*3600000).toISOString());
  render({current:{time:times[0],temperature_2m:14,weather_code:2},hourly:{time:times,temperature_2m:[14,15,17,18,18,17,16,15,13,12,11,10,10,9,8,8,9,10,11,12,13,14,14,15],precipitation_probability:Array.from({length:24},(_,i)=>i<6?10:i<12?35:20)}},cities[selected],true);
  text('status','Synthetic sample. These values are illustrative, not current weather. '+(liveAvailable ? 'Load forecast to return to live data.' : 'Local exploration works without live access.'));
};
let resizeTimer;
window.addEventListener('resize',()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(()=>{if(last)render(last.data,last.city,last.sample);},120);});
load();
