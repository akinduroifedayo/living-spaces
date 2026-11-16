import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { homedir } from 'node:os';
import { join, resolve } from 'node:path';

const root = resolve(import.meta.dirname, '../../../src/living-spaces/skills/build-space/references/weather-window');
const { JSDOM } = createRequire(join(homedir(), '.hermes/hermes-agent/apps/desktop/node_modules/react/package.json'))('jsdom');
const code = readFileSync(join(root, 'app.js'), 'utf8');
const forecast = temp => ({ current: { time: '2026-11-16T00:00', temperature_2m: temp, weather_code: 0 },
  hourly: { time: Array.from({ length: 24 }, (_, i) => `2026-11-16T${String(i).padStart(2, '0')}:00`), temperature_2m: Array(24).fill(temp), precipitation_probability: Array(24).fill(0) } });
const ok = temp => ({ status: 200, url: 'https://api.open-meteo.com/', headers: {}, json: forecast(temp) });
const settle = async () => { for (let i = 0; i < 12; i++) await Promise.resolve(); };

function boot() {
  const dom = new JSDOM(readFileSync(join(root, 'index.html'), 'utf8'), { runScripts: 'outside-only' });
  const w = dom.window;
  const fetches = [], gets = [], records = new Map();
  w.setTimeout = () => 0;
  w.space = {
    net: { fetch: () => new Promise((resolve, reject) => fetches.push({ resolve, reject })) },
    get: (collection, key) => new Promise(resolve => gets.push({ key, resolve })),
    put: async (collection, key, data, { baseRev }) => {
      const rev = records.get(key)?.rev ?? 0;
      if (rev !== baseRev) throw Object.assign(new Error('conflict'), { code: 'conflict' });
      records.set(key, { rev: rev + 1, data });
    },
  };
  w.eval(code);
  const shown = () => ({ city: w.document.getElementById('city').textContent, temperature: w.document.getElementById('temperature').textContent });
  return { dom, fetches, gets, records, shown, pick: key => w.document.querySelector(`[data-city="${key}"]`).click() };
}

test('a slow save for one city is stored under that city, not the city selected since', async () => {
  const app = boot();
  app.fetches[0].resolve(ok(10)); await settle();
  app.pick('tokyo');
  app.fetches[1].resolve(ok(20)); await settle();
  app.gets[0].resolve(null); await settle();
  app.gets[1].resolve(null); await settle();
  assert.equal(app.records.get('london').data.forecast.current.temperature_2m, 10);
  assert.equal(app.records.get('tokyo').data.forecast.current.temperature_2m, 20);
  assert.deepEqual(app.shown(), { city: 'Tokyo', temperature: '20' });
  app.dom.window.close();
});

test('a saved forecast that arrives after a newer load does not replace it', async () => {
  const app = boot();
  app.fetches[0].reject(Object.assign(new Error('off'), { code: 'not_granted' })); await settle();
  app.pick('tokyo');
  app.fetches[1].resolve(ok(20)); await settle();
  app.gets[1].resolve(null); await settle();
  app.gets[0].resolve({ rev: 1, data: { forecast: forecast(10), retrievedAt: '2026-11-16T00:00:00Z' } }); await settle();
  assert.deepEqual(app.shown(), { city: 'Tokyo', temperature: '20' });
  app.dom.window.close();
});

test('with Internet off, the saved forecast for the city is shown and labelled', async () => {
  const app = boot();
  app.fetches[0].reject(Object.assign(new Error('off'), { code: 'not_granted' })); await settle();
  app.gets[0].resolve({ rev: 1, data: { forecast: forecast(12), retrievedAt: '2026-11-16T00:00:00Z' } }); await settle();
  assert.deepEqual(app.shown(), { city: 'London', temperature: '12' });
  assert.match(app.dom.window.document.getElementById('status').textContent, /Internet access is off for this Space\. Still showing the forecast saved for London\./);
  app.dom.window.close();
});
