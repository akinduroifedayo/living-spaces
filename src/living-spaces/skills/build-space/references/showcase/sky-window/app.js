// Sky Window — premium showcase reference (data dashboard).
// Concept: one window per city. The sky inside each window is computed from the
// live weather code and the city's local hour; a generated skyline silhouette
// sits on the horizon. No kit CSS, no framework: the kit is optional.
//
// Data: public Open-Meteo forecast through space.net.fetch (the host bridge).
// Standalone preview (no window.space) uses browser fetch. When internet is off
// or the source fails, a clearly labelled synthetic sample keeps it explorable.

const space = window.space;
const $ = id => document.getElementById(id);
const CITIES = [
  {id: 'chicago', name: 'Chicago', lat: 41.8781, lon: -87.6298},
  {id: 'lisbon', name: 'Lisbon', lat: 38.7223, lon: -9.1393},
  {id: 'tokyo', name: 'Tokyo', lat: 35.6762, lon: 139.6503}
];
const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
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
async function load() {
  $('reload').disabled = true;
  document.querySelector('.room').setAttribute('aria-busy', 'true');
  const hadData = Object.keys(state.data).length > 0;
  $('status').textContent = hadData ? 'Refreshing the skies… current views stay up.' : 'Opening the windows…';
  try {
    const results = await Promise.all(CITIES.map(c => getJSON(url(c))));
    state = {mode: 'live', data: Object.fromEntries(CITIES.map((c, i) => [c.id, results[i]])), retrieved: new Date(), problem: null};
    $('status').textContent = 'Live forecast';
  } catch (e) {
    const off = e?.code === 'not_granted';
    state = {mode: hadData && state.mode === 'live' ? 'stale' : 'sample',
      data: hadData && state.mode === 'live' ? state.data : sample(), retrieved: state.retrieved,
      problem: off ? 'off' : 'failed'};
    $('status').textContent = off
      ? 'Internet access is off for this Space. Showing a labelled sample sky.'
      : state.mode === 'stale' ? 'Couldn’t reach Open-Meteo. Still showing the last forecast.'
      : 'Couldn’t reach Open-Meteo. Showing a labelled sample sky.';
  } finally {
    $('reload').disabled = false;
    document.querySelector('.room').removeAttribute('aria-busy');
    draw();
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
  const d = state.data[c.id];
  const box = $('ribbon');
  const W = Math.max(320, Math.min(1100, box.clientWidth || 900)), H = 260, padX = W < 520 ? 22 : 40;
  const n = d.daily.time.length;
  const lows = d.daily.temperature_2m_min, highs = d.daily.temperature_2m_max;
  const min = Math.floor(Math.min(...lows) - 2), max = Math.ceil(Math.max(...highs) + 2);
  const x = i => padX + i * (W - padX * 2) / (n - 1);
  const y = t => 70 + (max - t) / (max - min) * 120;
  const day = s => new Date(s + 'T12:00:00Z').toLocaleDateString('en-GB', {weekday: 'short', timeZone: 'UTC'});
  // Band between the daily low and high lines: smooth only for the drawing, points are exact.
  const curve = pts => pts.map((p, i) => {
    if (!i) return `M${p[0]},${p[1]}`;
    const [px, py] = pts[i - 1], mx = (px + p[0]) / 2;
    return `C${mx},${py} ${mx},${p[1]} ${p[0]},${p[1]}`;
  }).join('');
  const top = highs.map((t, i) => [x(i), y(t)]), bottom = lows.map((t, i) => [x(i), y(t)]).reverse();
  const band = curve(top) + 'L' + curve(bottom).slice(1) + 'Z';
  const grad = svg('linearGradient', {id: 'warm', x1: 0, y1: 0, x2: 0, y2: 1},
    svg('stop', {offset: '0', 'stop-color': tempColour(max)}), svg('stop', {offset: '1', 'stop-color': tempColour(min)}));
  const art = svg('svg', {viewBox: `0 0 ${W} ${H}`, width: '100%', 'aria-hidden': 'true', class: 'ribbon-svg'},
    svg('defs', {}, grad, svg('linearGradient', {id: 'warmY', gradientUnits: 'userSpaceOnUse', x1: 0, y1: y(max), x2: 0, y2: y(min)},
      svg('stop', {offset: '0', 'stop-color': tempColour(max)}), svg('stop', {offset: '1', 'stop-color': tempColour(min)}))),
    svg('path', {d: band, fill: 'url(#warmY)', class: 'band'}));
  d.daily.time.forEach((t, i) => {
    const k = kind(d.daily.weather_code[i]), rain = d.daily.precipitation_probability_max[i] ?? 0;
    const g = svg('g', {class: 'day' + (i === 0 ? ' today' : ''), style: `--i:${i}`});
    g.append(
      svg('text', {x: x(i), y: 22, class: 'dname', 'text-anchor': 'middle'}, i === 0 ? 'Today' : day(t)),
      svg('path', {d: GLYPH[k], transform: `translate(${x(i) - 10},${30}) scale(.84)`, class: 'glyph'}),
      svg('line', {x1: x(i), x2: x(i), y1: y(highs[i]), y2: y(lows[i]), class: 'stem'}),
      svg('circle', {cx: x(i), cy: y(highs[i]), r: 4, class: 'dot'}),
      svg('circle', {cx: x(i), cy: y(lows[i]), r: 4, class: 'dot'}),
      svg('text', {x: x(i), y: y(highs[i]) - 10, class: 'hi', 'text-anchor': 'middle'}, `${Math.round(highs[i])}°`),
      svg('text', {x: x(i), y: y(lows[i]) + 20, class: 'lo', 'text-anchor': 'middle'}, `${Math.round(lows[i])}°`),
      // Rain: a drop that fills from the bottom, with the exact percentage.
      svg('rect', {x: x(i) - 14, y: 222, width: 28, height: 6, rx: 3, class: 'rain-track'}),
      svg('rect', {x: x(i) - 14, y: 222, width: 28 * rain / 100, height: 6, rx: 3, class: 'rain-fill'}),
      svg('text', {x: x(i), y: 246, class: 'rain', 'text-anchor': 'middle'}, `${rain}%`));
    art.append(g);
  });
  box.replaceChildren(art);
  box.setAttribute('aria-label', `${c.name}, next seven days. Lows ${Math.round(Math.min(...lows))} to highs ${Math.round(Math.max(...highs))} degrees Celsius. Exact values in Daily values.`);
  $('week-city').textContent = c.name;
  $('days').replaceChildren(...d.daily.time.map((t, i) => el('tr', {},
    el('td', {}, i === 0 ? 'Today' : day(t)), el('td', {}, WORDS[kind(d.daily.weather_code[i])]),
    el('td', {}, lows[i].toFixed(1)), el('td', {}, highs[i].toFixed(1)), el('td', {}, String(d.daily.precipitation_probability_max[i] ?? '—')))));
}

function countUp(root) {
  if (reduced) return;
  root.querySelectorAll('.num').forEach(n => {
    const to = Number(n.dataset.to), from = to - Math.sign(to || 1) * Math.min(12, Math.abs(to) + 6), t0 = performance.now();
    const step = t => { const p = Math.min(1, (t - t0) / 700), e = 1 - Math.pow(2, -10 * p);
      n.textContent = String(Math.round(from + (to - from) * e)); if (p < 1) requestAnimationFrame(step); };
    requestAnimationFrame(step);
  });
}

function draw(fromClick = false) {
  const ordered = [CITIES.find(c => c.id === lead), ...CITIES.filter(c => c.id !== lead)];
  const wrap = $('windows');
  wrap.replaceChildren(...ordered.map(pane));
  wrap.dataset.mode = state.mode;
  ribbon(ordered[0]);
  if (!fromClick) countUp(wrap);
  else wrap.querySelector('.is-lead .pane-hit')?.focus({preventScroll: true});
  const src = $('source');
  src.replaceChildren();
  if (state.mode === 'sample') src.append('Synthetic sample sky · illustrative values, not current weather');
  else {
    const a = el('a', {href: 'https://open-meteo.com/', target: '_blank', rel: 'noopener noreferrer'}, 'Open-Meteo');
    src.append('Forecast from ', a, ` · updated ${state.retrieved.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})}`);
  }
  $('clock').textContent = state.mode === 'sample' ? 'Sample skies · not live' : 'Three skies, right now';
}

$('reload').addEventListener('click', load);
let resizeTimer;
addEventListener('resize', () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(() => state.data[lead] && ribbon(CITIES.find(c => c.id === lead)), 150); });
load();
