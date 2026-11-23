// Space marks: string icons, object icons, a checked generated image, a broken image, failed checks and the fixed
// fallback order image → kit glyph → sigil. A mark is never blank and never fetches anything but its own Space's icon.
import test, { before, after, beforeEach } from 'node:test'
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { homedir } from 'node:os'
import { resolve, dirname, join } from 'node:path'
import * as model from '../../../src/desktop/ui/model.mjs'
import * as marks from '../../../src/desktop/ui/marks.mjs'

const root = resolve(import.meta.dirname, '../../..')
const require = createRequire(join(homedir(), '.hermes/hermes-agent/apps/desktop/node_modules/react/package.json'))
const React = require('react')
const { act } = React
const { createRoot } = require('react-dom/client')
const { JSDOM } = require('jsdom')
const cache = new Map()
let dom, view, served, requests
function load(path) {
  if (cache.has(path)) return cache.get(path)
  const output = execFileSync('esbuild', ['--loader=jsx', '--format=cjs', '--jsx=automatic'], { input: readFileSync(path), encoding: 'utf8' })
  const module = { exports: {} }
  const imports = name => {
    if (name === '@hermes/plugin-sdk') return sdk
    if (name === './model.mjs') return model
    if (name === './marks.mjs') return marks
    if (name.startsWith('.')) return load(resolve(dirname(path), name))
    return require(name)
  }
  // Only esbuild output from this checkout enters the test module loader; nothing is interpolated into it.
  new Function('require', 'module', 'exports', output)(imports, module, module.exports)
  cache.set(path, module.exports)
  return module.exports
}
const sdk = {}
before(() => {
  dom = new JSDOM('<div id="root"></div>', { url: 'https://demo.invalid', pretendToBeVisual: true })
  globalThis.window = dom.window
  globalThis.document = dom.window.document
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  Object.assign(sdk, load(resolve(root, 'tests/js/ui/sdk-stub.js')), {
    // Synchronous query double: records what a mark asks for and answers from `served`.
    useQuery({ queryKey, queryFn, enabled = true }) {
      if (!enabled) return { data: undefined }
      requests.push(queryKey)
      queryFn()
      return { data: served }
    }
  })
})
after(() => dom.window.close())
beforeEach(() => { served = undefined; requests = [] })

const IMAGE = 'data:image/webp;base64,UklGRhYAAABXRUJQVlA4IAoAAAAwAQCdASoBAAEAAQAcJaQAA3AA/v3AgAA='
const passed = { path: 'assets/icon.webp', sha: 'a'.repeat(64), pass: true, fails: [], attempt: 1 }
const failed = { ...passed, pass: false, fails: ['mark contrast 1.67:1 < 3:1'], attempt: 2 }
const space = patch => ({ id: 'faultline-atlas', name: 'Faultline Atlas', accent: 'purple', icon: 'globe', icon_image: null, ...patch })
const ui = () => load(resolve(root, 'src/desktop/ui/components.jsx'))
const restCalls = []
const source = { rest: async path => { restCalls.push(path); return served }, scopeKey: 'scope' }
async function render(element) { view = createRoot(document.getElementById('root')); await act(async () => view.render(element)) }
async function cleanup() { await act(async () => view.unmount()) }
async function mark(props, withSource = true) {
  const { SpaceMark, IconSource } = ui()
  const element = React.createElement(SpaceMark, props)
  await render(withSource ? React.createElement(IconSource.Provider, { value: source }, element) : element)
  return document.querySelector('svg.ls-mark')
}
const painted = svg => svg.querySelectorAll('path, image').length > 0

test('a legacy string icon resolves through the alias table to a kit glyph', async () => {
  try {
    const svg = await mark({ space: space({ icon: 'globe' }), size: 40 })
    assert.equal(svg.dataset.mark, 'glyph')
    assert.equal(svg.dataset.glyph, 'seismo', 'Codicon "globe" maps to the seismograph glyph')
    assert.equal(requests.length, 0, 'no image named: nothing is requested')
  } finally { await cleanup() }
})

test('a kit glyph name draws that glyph directly', async () => {
  try {
    assert.equal((await mark({ space: space({ icon: 'plane' }), size: 24 })).dataset.glyph, 'plane')
  } finally { await cleanup() }
})

test('an image that passed the checks is read from its own Space and drawn inside the host squircle', async () => {
  served = { sha: passed.sha, image: IMAGE }
  try {
    const svg = await mark({ space: space({ icon_image: passed }), size: 72 })
    assert.equal(svg.dataset.mark, 'image')
    assert.equal(svg.querySelector('image').getAttribute('href'), IMAGE)
    assert.ok(svg.querySelector('clipPath path'), 'the host clips it to the squircle')
    assert.ok(svg.querySelector('linearGradient'), 'the host lays its ramp over the flat field')
    assert.deepEqual(restCalls.at(-1), '/spaces/faultline-atlas/icon', 'the only request is this Space\'s local icon route')
  } finally { await cleanup() }
})

test('the image is drawn at every host size, with the optical zoom shrinking as the mark grows', async () => {
  served = { sha: passed.sha, image: IMAGE }
  const widths = {}
  for (const size of [16, 24, 40, 72, 96]) {
    try {
      const svg = await mark({ space: space({ icon_image: passed }), size })
      assert.equal(svg.dataset.mark, 'image', `${size}px`)
      assert.equal(svg.getAttribute('width'), String(size))
      widths[size] = Number(svg.querySelector('image').getAttribute('width'))
    } finally { await cleanup() }
  }
  assert.ok(widths[16] > widths[24] && widths[24] > widths[40] && widths[40] > widths[72], JSON.stringify(widths))
  assert.equal(widths[96], 24)
})

test('a broken image falls back to the glyph instead of showing a broken tile', async () => {
  served = { sha: passed.sha, image: IMAGE }
  try {
    const svg = await mark({ space: space({ icon_image: passed }), size: 40 })
    await act(async () => svg.querySelector('image').dispatchEvent(new window.Event('error')))
    const after = document.querySelector('svg.ls-mark')
    assert.equal(after.dataset.mark, 'glyph')
    assert.equal(after.dataset.glyph, 'seismo')
    assert.equal(after.querySelector('image'), null)
  } finally { await cleanup() }
})

test('an image whose save-time checks failed is never requested or shown', async () => {
  served = { sha: failed.sha, image: IMAGE }
  try {
    const svg = await mark({ space: space({ icon_image: failed }), size: 72 })
    assert.equal(svg.dataset.mark, 'glyph')
    assert.equal(requests.length, 0)
  } finally { await cleanup() }
})

test('a reply for an older image or a non-raster payload is not drawn', async () => {
  for (const reply of [{ sha: 'b'.repeat(64), image: IMAGE }, { sha: passed.sha, image: 'https://example.invalid/icon.png' },
    { sha: passed.sha, image: 'data:image/svg+xml;base64,PHN2Zz4=' }]) {
    served = reply
    try {
      assert.equal((await mark({ space: space({ icon_image: passed }), size: 40 })).dataset.mark, 'glyph', JSON.stringify(reply).slice(0, 60))
    } finally { await cleanup() }
  }
})

test('fallback order: image, then glyph, then a sigil seeded by the Space id; never blank', async () => {
  served = { sha: passed.sha, image: IMAGE }
  const cases = [
    [space({ icon_image: passed }), 'image'],
    [space({ icon_image: passed }), 'glyph', false],
    [space({ icon_image: null }), 'glyph'],
    [space({ icon: 'layers' }), 'sigil'],
    [space({ icon: 'not-a-glyph', icon_image: failed }), 'sigil'],
    [space({ icon: undefined }), 'sigil'],
  ]
  for (const [value, expected, withSource = true] of cases) {
    try {
      const svg = await mark({ space: value, size: 40 }, withSource)
      assert.equal(svg.dataset.mark, expected, JSON.stringify({ icon: value.icon, image: value.icon_image?.pass, withSource }))
      assert.ok(painted(svg), 'something is drawn')
    } finally { await cleanup() }
  }
})

test('the sigil is deterministic per Space and differs between Spaces', () => {
  const a = marks.resolveMark({ id: 'plant-swap', icon: 'layers' }), b = marks.resolveMark({ id: 'plant-swap', icon: 'layers' })
  const c = marks.resolveMark({ id: 'job-hunt', icon: 'layers' })
  assert.deepEqual(a, b)
  assert.notDeepEqual(a.shapes, c.shapes)
  for (const id of ['a', 'pair-play', 'thailand-readiness', 'x'.repeat(48)]) {
    const { shapes } = marks.sigil(id)
    assert.ok(shapes.length >= 2 && shapes.some(s => s.t === 1), id)
  }
})

test('the 16 px tier keeps the coloured tile, not a bare silhouette', async () => {
  for (const size of [16, 24]) {
    try {
      const svg = await mark({ space: space({ icon: 'book' }), size })
      assert.ok([...svg.querySelectorAll('path')].some(p => p.getAttribute('d') === marks.SQUIRCLE && p.getAttribute('fill')?.startsWith('url(')), `${size}px`)
    } finally { await cleanup() }
  }
})

test('every ramp keeps a white glyph at 3:1 or better on its lightest stop', () => {
  for (const accent of Object.keys(model.ACCENTS)) assert.ok(marks.ramp(accent).glyphContrast >= 3, accent)
})

test('the shell kit and the core\'s fallback names agree', () => {
  const python = execFileSync(join(homedir(), '.hermes/hermes-agent/venv/bin/python'), ['-I', '-c',
    'import json,sys; sys.path.insert(0, sys.argv[1]); from living_spaces_core import icons; print(json.dumps({"kit": list(icons.KIT), "legacy": icons.LEGACY}))',
    resolve(root, 'src/living-spaces')], { encoding: 'utf8' })
  const core = JSON.parse(python)
  assert.deepEqual(core.kit, Object.keys(marks.KIT))
  assert.deepEqual(core.legacy, marks.LEGACY)
  for (const target of Object.values(marks.LEGACY)) assert.ok(Object.hasOwn(marks.KIT, target), target)
})
