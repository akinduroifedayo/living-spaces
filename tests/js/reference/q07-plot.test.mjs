import assert from 'node:assert/strict'
import test from 'node:test'
import { createRequire } from 'node:module'
import { homedir } from 'node:os'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

// Offline DOM fixtures over the real vendored bundle. Not native or visual evidence.
const require = createRequire(resolve(homedir(), '.hermes/hermes-agent/apps/desktop/node_modules/react/package.json'))
const { JSDOM } = require('jsdom')
const doc = () => new JSDOM('<!doctype html><body></body>').window.document
// jsdom has no canvas; Plot draws continuous legend ramps on one. Stub only that context for the heatmap.
const canvasDoc = () => {
  const document = doc(), proto = document.defaultView.HTMLCanvasElement.prototype
  proto.getContext = () => ({fillRect() {}, set fillStyle(_) {}})
  proto.toDataURL = () => 'data:image/png;base64,'
  return document
}
const recipes = await import('../../../src/living-spaces/skills/build-space/references/charts/recipes.mjs')
const Plot = await import('plot')

test('the plot bundle is self-contained: no imports, network or Node built-ins', () => {
  const source = readFileSync('src/living-spaces/runtime/vendor/plot.mjs', 'utf8')
  assert.doesNotMatch(source, /\bimport\s*[\s{*"'(]|\brequire\(|\bfetch\(|XMLHttpRequest|process\.|https?:\/\/(?!www\.w3\.org\/)/)
  assert.equal(typeof Plot.plot, 'function')
  for (const mark of ['barY', 'rectY', 'binX', 'cell', 'lineY', 'dot', 'ruleY']) assert.equal(typeof Plot[mark], 'function', mark)
})

const ticks = node => [...node.querySelectorAll('[aria-label$="tick label"] text, g[aria-label*="axis"] text')].map(t => t.textContent)
const axisLabels = node => [...node.querySelectorAll('svg text')].map(t => t.textContent)

test('bar chart keeps negative values truthful with a unit and a zero rule', () => {
  const rows = [{m: 'Jan', net: 120}, {m: 'Feb', net: -45}, {m: 'Mar', net: null}, {m: 'Apr', net: 30}]
  const {node, summary} = recipes.barChart(rows, {x: 'm', y: 'net', unit: 'USD', label: 'Net', document: doc()})
  assert.match(summary, /Feb -45 USD/)
  assert.doesNotMatch(summary, /Mar/)
  const svg = node.querySelector('svg')
  assert.equal(svg.getAttribute('role'), 'img')
  assert.equal(svg.getAttribute('aria-label'), summary)
  assert.ok(axisLabels(node).some(text => text.includes('Net (USD)')), 'unit on the axis')
  assert.ok(ticks(node).some(text => /^[−-]\d/.test(text)), 'domain extends below zero')
  const bars = [...node.querySelectorAll('rect')].filter(r => r.querySelector('title'))
  assert.equal(bars.length, 3)
  const feb = bars.find(r => r.querySelector('title').textContent.startsWith('Feb'))
  assert.equal(feb.getAttribute('fill'), 'var(--sk-negative, #b4442c)')
  assert.ok(node.querySelector('line'), 'zero rule drawn')
})

test('time series breaks the line at a missing reading instead of interpolating', () => {
  const d = day => new Date(Date.UTC(2026, 0, day))
  const points = [{t: d(1), v: 2}, {t: d(2), v: -1}, {t: d(3), v: null}, {t: d(4), v: 3}]
  const {node, summary} = recipes.timeSeries(points, {date: 't', value: 'v', unit: '°C', label: 'Temperature', document: doc()})
  assert.match(summary, /2026-01-01 \(2 °C\) to 2026-01-04 \(3 °C\); 1 missing reading shown as gaps/)
  const path = node.querySelector('g[aria-label="line"] path').getAttribute('d')
  assert.equal((path.match(/M/g) || []).length, 2, 'two segments around the gap')
  assert.equal(node.querySelectorAll('circle').length, 3)
  assert.ok(axisLabels(node).some(text => text.includes('Temperature (°C)')))
})

test('distribution counts only finite values and reports what was excluded', () => {
  const {node, summary} = recipes.distribution([1, 2, 2, 3, NaN, null, 10], {unit: 'min', label: 'Commute', document: doc()})
  assert.match(summary, /^5 Commute values from 1 min to 10 min, median 2 min; 2 missing values not shown\.$/)
  assert.ok(axisLabels(node).some(text => text.includes('Commute (min)')))
  assert.ok(axisLabels(node).some(text => text.includes('Count')))
})

test('heatmap centres a diverging scale on zero for signed data and names extremes', () => {
  const cells = [{w: 'Mon', h: 'AM', d: -3}, {w: 'Mon', h: 'PM', d: 5}, {w: 'Tue', h: 'AM', d: 0}, {w: 'Tue', h: 'PM', d: undefined}]
  const {node, summary} = recipes.heatmap(cells, {x: 'w', y: 'h', value: 'd', unit: 'kWh', label: 'Delta', document: canvasDoc()})
  assert.match(summary, /lowest AM Mon at -3 kWh, highest PM Mon at 5 kWh; 1 cells have no value\./)
  assert.equal([...node.querySelectorAll('rect')].filter(r => r.querySelector('title')).length, 3)
  assert.ok(axisLabels(node).some(text => text.includes('Delta (kWh)')), 'legend names the unit')
})

test('every recipe shows an honest empty state instead of a fabricated chart', () => {
  const cases = [
    recipes.barChart([{m: 'Jan', net: null}], {x: 'm', y: 'net', unit: 'USD', label: 'Net', document: doc()}),
    recipes.distribution([], {unit: 'min', label: 'Commute', document: doc()}),
    recipes.heatmap([], {x: 'w', y: 'h', value: 'd', unit: 'kWh', document: doc()}),
    recipes.timeSeries([{t: new Date(0), v: null}], {date: 't', value: 'v', unit: '°C', label: 'Temperature', document: doc()}),
  ]
  for (const {node, summary} of cases) {
    assert.equal(node.tagName, 'P')
    assert.equal(node.getAttribute('role'), 'status')
    assert.equal(node.textContent, summary)
    assert.match(summary, /^No /)
    assert.equal(node.querySelector('svg'), null)
  }
})

test('narrow canvases keep a usable chart at 320 px', () => {
  const rows = Array.from({length: 12}, (_, i) => ({m: `Month ${i + 1} long label`, net: i - 5}))
  for (const width of [390, 320]) {
    const {node} = recipes.barChart(rows, {x: 'm', y: 'net', unit: 'USD', label: 'Net', width, document: doc()})
    const svg = node.querySelector('svg')
    assert.equal(Number(svg.getAttribute('width')), width)
    if (width <= 360) assert.ok([...node.querySelectorAll('text')].some(t => /rotate\(-45/.test(t.getAttribute('transform') || '')
      || /rotate\(-45/.test(t.parentNode.getAttribute('transform') || '')), 'labels rotate rather than overlap')
  }
})
