// Chart recipes for the optional `plot` library group (Observable Plot 0.6.19 + D3 7.9.2).
// Copy the recipe you need into the Space and select `plot` in `libraries`. Each recipe returns
// {node, summary}: `node` is the chart, or an honest empty state when no value is eligible, and
// `summary` is a plain-text alternative. Domains come from the data, so negative values and gaps stay
// visible, and every axis names its unit.
import * as Plot from 'plot'

const finite = value => typeof value === 'number' && Number.isFinite(value)
const NARROW = 360

function empty(doc, message) {
  const node = doc.createElement('p')
  node.className = 'chart-empty'
  node.setAttribute('role', 'status')
  node.textContent = message
  return {node, summary: message}
}

function frame(doc, plot, summary) {
  const figure = doc.createElement('figure')
  figure.append(plot)
  const caption = doc.createElement('figcaption')
  caption.textContent = summary
  figure.append(caption)
  plot.setAttribute('role', 'img')
  plot.setAttribute('aria-label', summary)
  return figure
}

const fmt = (value, unit) => `${Number(value.toFixed(2))} ${unit}`

// Signed categorical values. A zero rule keeps negative bars truthful.
export function barChart(rows, {x, y, unit, label = y, width = 640, document: doc = globalThis.document}) {
  const eligible = rows.filter(row => finite(row[y]))
  if (!eligible.length) return empty(doc, `No ${label} to chart yet.`)
  const narrow = width <= NARROW
  const summary = `${label} by ${x}: ` + eligible.map(row => `${row[x]} ${fmt(row[y], unit)}`).join('; ') + '.'
  const plot = Plot.plot({
    document: doc, width, height: narrow ? 260 : 320, marginLeft: narrow ? 48 : 64,
    x: {label: null, tickRotate: narrow ? -45 : 0},
    y: {label: `${label} (${unit})`, grid: true},
    marks: [
      Plot.barY(eligible, {x, y, fill: d => (d[y] < 0 ? 'var(--sk-negative, #b4442c)' : 'var(--sk-accent, currentColor)'),
        title: d => `${d[x]}: ${fmt(d[y], unit)}`}),
      Plot.ruleY([0]),
    ],
  })
  return {node: frame(doc, plot, summary), summary}
}

// Distribution of one measure. Missing values are excluded and counted in the summary.
export function distribution(values, {unit, label, thresholds = 10, width = 640, document: doc = globalThis.document}) {
  const eligible = values.filter(finite)
  if (!eligible.length) return empty(doc, `No ${label} values to chart yet.`)
  const missing = values.length - eligible.length
  const sorted = [...eligible].sort((a, b) => a - b)
  const median = sorted.length % 2 ? sorted[(sorted.length - 1) / 2] : (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2
  const summary = `${eligible.length} ${label} values from ${fmt(sorted[0], unit)} to ${fmt(sorted.at(-1), unit)}, median ${fmt(median, unit)}`
    + (missing ? `; ${missing} missing value${missing === 1 ? '' : 's'} not shown.` : '.')
  const plot = Plot.plot({
    document: doc, width, height: width <= NARROW ? 220 : 280,
    x: {label: `${label} (${unit})`}, y: {label: 'Count', grid: true},
    marks: [Plot.rectY(eligible, Plot.binX({y: 'count'}, {x: d => d, thresholds, fill: 'var(--sk-accent, currentColor)'})),
      Plot.ruleY([0])],
  })
  return {node: frame(doc, plot, summary), summary}
}

// Two categorical axes and one measure. A diverging scheme centred on zero keeps sign readable.
export function heatmap(cells, {x, y, value, unit, label = value, width = 640, document: doc = globalThis.document}) {
  const eligible = cells.filter(cell => finite(cell[value]))
  if (!eligible.length) return empty(doc, `No ${label} to chart yet.`)
  const values = eligible.map(cell => cell[value])
  const signed = Math.min(...values) < 0
  const lo = eligible.reduce((a, b) => (b[value] < a[value] ? b : a))
  const hi = eligible.reduce((a, b) => (b[value] > a[value] ? b : a))
  const summary = `${label} for ${eligible.length} cells; lowest ${lo[y]} ${lo[x]} at ${fmt(lo[value], unit)},`
    + ` highest ${hi[y]} ${hi[x]} at ${fmt(hi[value], unit)}`
    + (cells.length > eligible.length ? `; ${cells.length - eligible.length} cells have no value.` : '.')
  const plot = Plot.plot({
    document: doc, width, padding: 0.05, marginLeft: 72,
    x: {label: null, tickRotate: width <= NARROW ? -45 : 0}, y: {label: null},
    color: signed ? {type: 'diverging', pivot: 0, scheme: 'BuRd', legend: true, label: `${label} (${unit})`}
      : {scheme: 'blues', legend: true, label: `${label} (${unit})`},
    marks: [Plot.cell(eligible, {x, y, fill: value, title: d => `${d[y]} ${d[x]}: ${fmt(d[value], unit)}`})],
  })
  return {node: frame(doc, plot, summary), summary}
}

// A measure over time. A missing value breaks the line instead of being interpolated.
export function timeSeries(points, {date, value, unit, label = value, width = 640, document: doc = globalThis.document}) {
  // Sort by time so a missing reading always falls between its neighbours and breaks the line there.
  const dated = points.filter(point => point[date] instanceof Date && !Number.isNaN(+point[date]))
    .sort((a, b) => a[date] - b[date])
  const eligible = dated.filter(point => finite(point[value]))
  if (!eligible.length) return empty(doc, `No ${label} recorded yet.`)
  const gaps = dated.length - eligible.length
  const first = eligible[0], last = eligible.at(-1)
  const day = d => d.toISOString().slice(0, 10)
  const summary = `${label} from ${day(first[date])} (${fmt(first[value], unit)}) to ${day(last[date])} (${fmt(last[value], unit)})`
    + (gaps ? `; ${gaps} missing reading${gaps === 1 ? '' : 's'} shown as gaps.` : '.')
  const plot = Plot.plot({
    document: doc, width, height: width <= NARROW ? 220 : 300,
    x: {label: null, ticks: width <= NARROW ? 3 : undefined}, y: {label: `${label} (${unit})`, grid: true},
    marks: [
      Plot.ruleY([0]),
      Plot.lineY(dated, {x: date, y: d => (finite(d[value]) ? d[value] : NaN), stroke: 'var(--sk-accent, currentColor)'}),
      Plot.dot(eligible, {x: date, y: value, r: 2, fill: 'var(--sk-accent, currentColor)',
        title: d => `${day(d[date])}: ${fmt(d[value], unit)}`}),
    ],
  })
  return {node: frame(doc, plot, summary), summary}
}
