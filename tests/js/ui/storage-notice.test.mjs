import test, { before, after } from 'node:test'
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { homedir } from 'node:os'
import { resolve, dirname, join } from 'node:path'
import * as model from '../../../src/desktop/ui/model.mjs'

const root = resolve(import.meta.dirname, '../../..')
const require = createRequire(join(homedir(), '.hermes/hermes-agent/apps/desktop/node_modules/react/package.json'))
const React = require('react')
const { act } = React
const { createRoot } = require('react-dom/client')
const { JSDOM } = require('jsdom')
const session = { createSpaceSession: () => ({ ready: Promise.resolve(), postEvent() {}, destroy: async () => {} }) }
let dom, view, data
const cache = new Map()
function load(path) {
  if (cache.has(path)) return cache.get(path)
  const output = execFileSync('esbuild', ['--loader=jsx', '--format=cjs', '--jsx=automatic'], { input: readFileSync(path), encoding: 'utf8' })
  const module = { exports: {} }
  const imports = name => {
    if (name === '@hermes/plugin-sdk') return sdk
    if (name === './session.mjs') return session
    if (name === './model.mjs') return model
    if (name === '../sandbox/index.js') return { WEBRTC_NOTE: 'Public demo disclosure', mountSpace: () => ({ destroy() {} }) }
    if (name.startsWith('.')) return load(resolve(dirname(path), name))
    return require(name)
  }
  new Function('require', 'module', 'exports', output)(imports, module, module.exports)
  cache.set(path, module.exports)
  return module.exports
}
const baseSdk = load(resolve(root, 'tests/js/ui/sdk-stub.js'))
const sdk = { ...baseSdk, useQuery(options) { return { data: data[options.queryKey[3]], dataUpdatedAt: 1, refetch: async () => {} } } }
const { SpaceView } = load(resolve(root, 'src/desktop/ui/space.jsx'))
const { StorageSection } = load(resolve(root, 'src/desktop/ui/history.jsx'))

before(() => {
  dom = new JSDOM('<div id="root"></div>', { url: 'https://demo.invalid' })
  globalThis.window = dom.window
  globalThis.document = dom.window.document
  Object.defineProperty(globalThis, 'localStorage', { value: dom.window.localStorage, configurable: true, writable: true })
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
})
after(() => dom.window.close())

const KEY = 'living-spaces:storage-dismissed:demo-backend:demo-profile:demo-space'
const source = used => ({ categories: {}, limits: [], warnings: [{ resource: 'source_bytes', used, limit: 65536, approaching: true }] })
const button = label => [...document.querySelectorAll('button')].find(b => b.textContent.trim() === label)
const notice = () => [...document.querySelectorAll('.ls-banner')].find(node => /Storage \d+% full/.test(node.textContent))
async function show(storage) {
  data.detail = { id: 'demo-space', name: 'Demo', owner: 'Hermes', status: 'active', head_rev: 2, grants: [], freshness: {}, storage }
  await act(async () => view.render(React.createElement(SpaceView, { sid: 'demo-space', ctx: { rest: async () => ({}) } })))
}
function fresh() { data = {}; localStorage.clear(); view = createRoot(document.getElementById('root')) }
const unmount = () => act(async () => view.unmount())

test('storageNotice describes the most-full resource in words with a rounded percentage', () => {
  assert.equal(model.storageNotice(null), null)
  assert.equal(model.storageNotice({ warnings: [] }), null)
  assert.deepEqual(model.storageNotice(source(59904)), { pct: 91, key: 'source_bytes:91', title: 'Storage 91% full', line: '58.5 KB of 64 KB used by source data. Writes stop at the limit.' })
  assert.deepEqual(model.storageNotice({ warnings: [{ resource: 'records', used: 40000, limit: 50000 }, { resource: 'source_bytes', used: 62259, limit: 65536 }] }),
    { pct: 95, key: 'records:80,source_bytes:95', title: 'Storage 95% full', line: '60.8 KB of 64 KB used by source data. Writes stop at the limit.' })
  assert.equal(model.storageNotice({ warnings: [{ resource: 'records', used: 40000, limit: 50000 }] }).line, '40,000 of 50,000 used by records. Writes stop at the limit.')
  assert.equal(model.storageNotice({ warnings: [{ resource: 'project_bytes', used: 22 * 1024 * 1024, limit: 25 * 1024 * 1024 }] }).line, '22 MB of 25 MB used by project files. Writes stop at the limit.')
  assert.equal(model.storageNotice({ warnings: [{ resource: 'data_bytes', used: 220000, limit: 262144 }] }).line, '214.8 KB of 256 KB used by records. Writes stop at the limit.')
  assert.equal(model.formatBytes(512), '512 B')
  assert.equal(model.formatBytes(64 * 1024), '64 KB')
})

test('the canvas storage notice shows a meter, reviews history and never prints the raw resource', async () => {
  fresh()
  try {
    await show(source(59904))
    const banner = notice()
    assert.ok(banner)
    assert.equal(banner.querySelector('strong').textContent, 'Storage 91% full')
    assert.match(banner.textContent, /58\.5 KB of 64 KB used by source data\. Writes stop at the limit\./)
    const meter = banner.querySelector('.ls-meter')
    assert.equal(meter.getAttribute('aria-hidden'), 'true')
    assert.equal(meter.querySelector('i').style.width, '91%')
    assert.doesNotMatch(document.body.textContent, /source_bytes|59904|65536/)
    assert.ok(button('Review'))
    assert.ok(button('Hide until it changes'))
    await act(async () => button('Review').click())
    assert.match(document.querySelector('[role="dialog"]').textContent, /History & revisions/)
  } finally { await unmount() }
})

test('hiding the storage notice lasts across reopen until the percentage changes', async () => {
  fresh()
  try {
    await show(source(59904))
    await act(async () => button('Hide until it changes').click())
    assert.equal(notice(), undefined)
    assert.equal(localStorage.getItem(KEY), 'source_bytes:91')
    await show(source(59950))
    assert.equal(notice(), undefined, 'the same rounded percentage stays hidden')
    await unmount()
    view = createRoot(document.getElementById('root'))
    await show(source(59904))
    assert.equal(notice(), undefined, 'the dismissal survives a reopen')
    await show(source(62259))
    assert.equal(notice()?.querySelector('strong').textContent, 'Storage 95% full')
  } finally { await unmount() }
})

test('hiding one storage notice never hides a different resource at its limit', async () => {
  fresh()
  const records = { resource: 'records', used: 42500, limit: 50000, approaching: true }
  const project = { resource: 'project_bytes', used: 25 * 1024 * 1024, limit: 25 * 1024 * 1024, approaching: true }
  try {
    await show({ categories: {}, limits: [], warnings: [records] })
    await act(async () => button('Hide until it changes').click())
    assert.equal(notice(), undefined)
    await show({ categories: {}, limits: [], warnings: [records, project] })
    assert.equal(notice()?.querySelector('strong').textContent, 'Storage 100% full')
    assert.match(notice().textContent, /25 MB of 25 MB used by project files\. Writes stop at the limit\./)
  } finally { await unmount() }
})

test('a newly full resource shows even while a hidden resource is just as full', async () => {
  fresh()
  const full = (resource, limit) => ({ resource, used: limit, limit, approaching: true })
  try {
    await show({ categories: {}, limits: [], warnings: [full('records', 50000)] })
    await act(async () => button('Hide until it changes').click())
    assert.equal(notice(), undefined)
    await show({ categories: {}, limits: [], warnings: [full('records', 50000), full('source_bytes', 65536)] })
    assert.equal(notice()?.querySelector('strong').textContent, 'Storage 100% full')
  } finally { await unmount() }
})

test('the storage notice inside the storage section only informs', async () => {
  fresh()
  try {
    await act(async () => view.render(React.createElement(StorageSection, { ctx: { rest: async () => ({}) }, space: { id: 'demo-space', storage: source(59904) }, onChanged() {} })))
    assert.equal(notice().querySelector('strong').textContent, 'Storage 91% full')
    assert.equal(button('Review'), undefined)
    assert.equal(button('Hide until it changes'), undefined)
    assert.doesNotMatch(document.body.textContent, /source_bytes/)
  } finally { await unmount() }
})
