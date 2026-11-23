// Gallery host chrome: card previews and their fallback, the snapshot lifecycle, the floating notice dock,
// the Details sheet, the one-phrase freshness wording and the narrow island.
import test, { before, after, beforeEach } from 'node:test'
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { homedir } from 'node:os'
import { crc32, deflateSync } from 'node:zlib'
import { resolve, dirname, join } from 'node:path'
import * as session from '../../../src/desktop/ui/session.mjs'
import * as model from '../../../src/desktop/ui/model.mjs'

const root = resolve(import.meta.dirname, '../../..')
const require = createRequire(join(homedir(), '.hermes/hermes-agent/apps/desktop/node_modules/react/package.json'))
const React = require('react')
const { act } = React
const { createRoot } = require('react-dom/client')
const { JSDOM } = require('jsdom')
const cache = new Map()
let dom, view, data, mounts, navigations
let snapshots
function load(path) {
  if (cache.has(path)) return cache.get(path)
  const output = execFileSync('esbuild', ['--loader=jsx', '--format=cjs', '--jsx=automatic'], { input: readFileSync(path), encoding: 'utf8' })
  const module = { exports: {} }
  const imports = name => {
    if (name === '@hermes/plugin-sdk') return sdk
    if (name === './model.mjs') return model
    if (name === './session.mjs') return session
    if (name === './snapshots.mjs') return snapshots
    if (name === '../sandbox/index.js') return { mountSpace: (container, options) => {
      const mount = { options, shots: [], destroy() {}, postEvent() {}, snapshot: async request => { mount.shots.push(request); return mount.reply } }
      mounts.push(mount)
      return mount
    } }
    if (name.startsWith('.')) return load(resolve(dirname(path), name))
    return require(name)
  }
  // Only esbuild output from this checkout enters the test module loader; nothing is interpolated into it.
  new Function('require', 'module', 'exports', output)(imports, module, module.exports)
  cache.set(path, module.exports)
  return module.exports
}
const stub = () => load(resolve(root, 'tests/js/ui/sdk-stub.js'))
const sdk = {}
before(async () => {
  dom = new JSDOM('<div id="root"></div>', { url: 'https://demo.invalid', pretendToBeVisual: true })
  globalThis.window = dom.window
  globalThis.document = dom.window.document
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  globalThis.MutationObserver = dom.window.MutationObserver
  globalThis.requestAnimationFrame = callback => setTimeout(callback, 0)
  Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: dom.window.localStorage })
  snapshots = await import('../../../src/desktop/ui/snapshots.mjs')
  Object.assign(sdk, stub(), {
    host: { navigate: route => navigations.push(route), state: { connectionId: { get: () => 'demo-backend' }, profile: { get: () => 'demo-profile' } } },
    useQuery(query) {
      const key = query.queryKey[3] ?? query.queryKey[2]
      return { data: data[key], error: undefined, dataUpdatedAt: 1, isLoading: false, refetch: async () => ({ status: 'success', data: data[key] }) }
    }
  })
})
after(() => dom.window.close())
beforeEach(() => { localStorage.clear(); data = {}; mounts = []; navigations = [] })

// A real, decodable PNG of the given pixel size (blank grey), so headers and declared sizes can be compared.
function png(width, height) {
  const chunk = (type, body) => { const head = Buffer.alloc(8); head.writeUInt32BE(body.length); head.write(type, 4); const crc = Buffer.alloc(4); crc.writeUInt32BE(crc32(Buffer.concat([Buffer.from(type), body]))); return Buffer.concat([head, body, crc]) }
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(width); ihdr.writeUInt32BE(height, 4); ihdr[8] = 8; ihdr[9] = 0
  const raw = Buffer.alloc((width + 1) * height, 0x80); for (let y = 0; y < height; y++) raw[y * (width + 1)] = 0
  return 'data:image/png;base64,' + Buffer.concat([Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]), chunk('IHDR', ihdr), chunk('IDAT', deflateSync(raw)), chunk('IEND', Buffer.alloc(0))]).toString('base64')
}
const PNG = png(480, 300)
const space = patch => ({ id: 'gbrain-cockpit', name: 'GBrain Cockpit', description: 'Your brain at a glance', owner: 'Hermes', status: 'active', head_rev: 7, accent: 'teal', icon: 'pulse', pinned: false, updated_at: 1700000000, grants: [], freshness: {}, manifest: {}, ...patch })
const ui = () => ({ ...load(resolve(root, 'src/desktop/ui/index.jsx')), ...load(resolve(root, 'src/desktop/ui/space.jsx')) })
async function render(Component, props) { view = createRoot(document.getElementById('root')); await act(async () => view.render(React.createElement(Component, props))) }
async function cleanup() { await act(async () => view.unmount()) }
const button = label => [...document.querySelectorAll('button')].find(node => node.textContent.trim() === label || node.getAttribute('aria-label') === label)
async function click(label) { const node = button(label); assert.ok(node, label); await act(async () => node.click()); return node }
const wait = ms => act(async () => new Promise(done => setTimeout(done, ms)))
const sessionRest = async path => path.endsWith('/sessions') ? { session: 's1', head_rev: 7, grants: [] } : path.endsWith('/bundle') ? { rev: 7 } : {}

// --- snapshot store ---------------------------------------------------------------------------------------

test('a stored snapshot is read back only for its own scope, Space and code revision', () => {
  assert.equal(snapshots.writeSnapshot('scope-a', 'gbrain-cockpit', { image: PNG, width: 480, height: 300, at: 1, rev: 7 }), true)
  assert.equal(snapshots.readSnapshot('scope-a', 'gbrain-cockpit', 7)?.image, PNG)
  assert.equal(snapshots.readSnapshot('scope-b', 'gbrain-cockpit', 7), null, 'another backend or profile never sees it')
  assert.equal(snapshots.readSnapshot('scope-a', 'faultline-atlas', 7), null)
  assert.equal(snapshots.readSnapshot('scope-a', 'gbrain-cockpit', 8), null, 'a capture of older code is not shown')
})

test('only bounded raster data URLs are accepted as snapshots', () => {
  const ok = { image: PNG, width: 480, height: 300, at: 1, rev: 1 }
  for (const bad of [
    { ...ok, image: 'data:image/svg+xml;base64,PHN2Zz4=' },
    { ...ok, image: 'https://example.invalid/shot.png' },
    { ...ok, image: 'data:image/png;base64,<script>' },
    { ...ok, image: 'data:image/png;base64,' + 'A'.repeat(snapshots.SNAPSHOT_LIMITS.maxChars) },
    { ...ok, width: 8 }, { ...ok, height: 4096 }, { ...ok, at: 'now' }, { ...ok, rev: 1.5 },
    { ...ok, image: png(4096, 4096) }, { ...ok, image: png(479, 300) }, { ...ok, image: png(480, 301) },
    { ...ok, image: 'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/' }
  ]) assert.equal(snapshots.writeSnapshot(null, 'demo-space', bad), false, JSON.stringify(bad).slice(0, 80))
  assert.equal(snapshots.readSnapshot(null, 'demo-space'), null)
  localStorage.setItem(snapshots.snapshotKey(null, 'demo-space'), '{"image":"javascript:alert(1)","width":480,"height":300,"at":1}')
  assert.equal(snapshots.readSnapshot(null, 'demo-space'), null, 'a tampered entry is ignored, not rendered')
})

test('a new capture replaces the old one and the oldest previews are evicted at the cap', () => {
  snapshots.writeSnapshot(null, 's-0', { image: PNG, width: 480, height: 300, at: 1, rev: 1 })
  const other = png(480, 300).replace(/.{4}$/, 'AAAA')
  snapshots.writeSnapshot(null, 's-0', { image: other, width: 480, height: 300, at: 2, rev: 1 })
  assert.equal(snapshots.readSnapshot(null, 's-0').image, other)
  for (let n = 1; n <= snapshots.SNAPSHOT_LIMITS.maxEntries; n++) snapshots.writeSnapshot(null, `s-${n}`, { image: PNG, width: 480, height: 300, at: n, rev: 1 })
  assert.equal(snapshots.readSnapshot(null, 's-0'), null, 'oldest evicted')
  assert.ok(snapshots.readSnapshot(null, `s-${snapshots.SNAPSHOT_LIMITS.maxEntries}`))
  const keys = Object.keys(localStorage).filter(key => key.startsWith('living-spaces:snapshot:'))
  assert.equal(keys.length, snapshots.SNAPSHOT_LIMITS.maxEntries)
  snapshots.forgetSnapshot(null, 's-3')
  assert.equal(snapshots.readSnapshot(null, 's-3'), null)
})

// --- cards ------------------------------------------------------------------------------------------------

test('a never-captured Space gets the accent and icon card, never an image', async () => {
  const { SpaceCard } = ui()
  try {
    await render(SpaceCard, { space: space(), scopeKey: 'scope' })
    const preview = document.querySelector('.ls-thumb')
    assert.equal(preview.dataset.preview, 'fallback')
    assert.equal(document.querySelector('.ls-card img'), null)
    assert.equal(document.querySelector('.ls-thumb-mark [data-icon]').dataset.icon, 'pulse')
    assert.match(preview.getAttribute('style'), /--ls-accent/)
  } finally { await cleanup() }
})

test('a captured Space shows its snapshot, and falls back if the image fails to decode', async () => {
  const { SpaceCard } = ui()
  snapshots.writeSnapshot('scope', 'gbrain-cockpit', { image: PNG, width: 480, height: 300, at: 1, rev: 7 })
  try {
    await render(SpaceCard, { space: space(), scopeKey: 'scope' })
    const image = document.querySelector('.ls-card img')
    assert.equal(image.getAttribute('src'), PNG)
    assert.equal(image.getAttribute('alt'), '', 'decorative: the card link carries the name')
    await act(async () => image.dispatchEvent(new dom.window.Event('error')))
    assert.equal(document.querySelector('.ls-card img'), null)
    assert.equal(document.querySelector('.ls-thumb').dataset.preview, 'fallback')
  } finally { await cleanup() }
})

test('a card names the Space, its freshness phrase and pin, and links to it', async () => {
  const { SpaceCard } = ui()
  try {
    await render(SpaceCard, { space: space({ pinned: true, activity: { kind: 'data', actor: 'upkeep:local cockpit sync', at: 1700000000 } }) })
    const card = document.querySelector('a.ls-card')
    assert.equal(card.getAttribute('href'), '#/spaces?space=gbrain-cockpit')
    assert.match(card.querySelector('.ls-card-freshness').textContent, /^Synced by local cockpit sync · relative 1700000000000$/)
    assert.ok(card.querySelector('.ls-pin'))
    assert.match(card.getAttribute('aria-label'), /^GBrain Cockpit, Ready, owner Hermes\..*Pinned$/)
  } finally { await cleanup() }
})

test('the landing shows a create entry point beside the cards, and the empty state without Spaces', async () => {
  const { SpacesIndex } = ui()
  const ctx = { rest: async () => ({}), listActions: () => [{ id: 'session.new', label: 'New chat' }], runAction: () => ({ ok: true }) }
  try {
    data.spaces = { spaces: [space()] }
    await render(SpacesIndex, { ctx })
    assert.equal(document.querySelectorAll('[role="list"] > [role="listitem"]').length, 2)
    assert.match(document.querySelector('.ls-newcard').textContent, /Build a Space in chat/)
    assert.ok(button('Start a new chat'))
    await cleanup()
    data.spaces = { spaces: [] }
    await render(SpacesIndex, { ctx })
    assert.match(document.body.textContent, /Build your first Space in chat/)
    assert.equal(document.querySelector('.ls-newcard'), null)
  } finally { await cleanup() }
})

// --- freshness phrase ------------------------------------------------------------------------------------

test('the island phrase is worded by what last changed the Space', () => {
  const phrase = patch => model.freshnessPhrase(space(patch))
  assert.deepEqual(phrase({ activity: { kind: 'data', actor: 'upkeep:local cockpit sync', at: 50 } }), { key: 'activity', label: 'Synced by local cockpit sync', at: 50 })
  assert.equal(phrase({ activity: { kind: 'data', actor: 'agent:Hermes', at: 50 } }).label, 'Edited in chat by Hermes')
  assert.equal(phrase({ activity: { kind: 'code', actor: 'agent:Hermes', at: 50 } }).label, 'Changed in chat by Hermes')
  assert.equal(phrase({ activity: { kind: 'data', actor: 'app', at: 50 } }).label, 'Edited in this Space')
  assert.equal(phrase({ activity: { kind: 'data', actor: 'upkeep:schedule', at: 50 } }).label, 'Refreshed on schedule')
  const feed = { last_success_at: 100, sources: [{ id: 'usgs', url: 'https://earthquake.usgs.gov/feed.atom' }] }
  assert.deepEqual(phrase({ freshness: feed, activity: { kind: 'data', actor: 'agent:Hermes', at: 100 } }), { key: 'success', label: 'Refreshed from earthquake.usgs.gov', at: 100 })
  assert.equal(phrase({ freshness: feed, activity: { kind: 'data', actor: 'app', at: 400 } }).label, 'Edited in this Space', 'a later edit outranks the refresh')
  assert.equal(phrase({ activity: { kind: 'data', actor: 'mystery', at: 50 } }).label, 'Not refreshed yet', 'an unknown actor is not invented into words')
  assert.equal(phrase({ freshness: { last_success_at: 100, last_attempt_status: 'failed' }, attention: { kind: 'failed' } }).label, 'Refresh failed · data from')
})

// --- open Space: island, capture, notices, Details ------------------------------------------------------

test('the island holds name, one freshness phrase, Details and overflow, and nothing else at rest', async () => {
  const { SpaceView } = ui()
  data.detail = space({ activity: { kind: 'data', actor: 'upkeep:local cockpit sync', at: 1700000000 } })
  try {
    await render(SpaceView, { sid: 'gbrain-cockpit', ctx: { rest: sessionRest } })
    const bar = document.querySelector('.ls-framebar')
    assert.equal(bar.querySelector('h1').textContent, 'GBrain Cockpit')
    assert.equal(bar.querySelector('.ls-frame-meta').textContent, 'Synced by local cockpit sync · relative 1700000000000')
    assert.deepEqual([...bar.querySelectorAll('button')].map(node => node.getAttribute('aria-label') || node.textContent.trim()), ['Back to Spaces', 'Details', 'More Space actions'])
  } finally { await cleanup() }
})

test('the open Space captures a snapshot once it settles and again when the user leaves', async () => {
  const { SpaceView } = ui()
  data.detail = space()
  const realTimeout = globalThis.setTimeout
  try {
    await render(SpaceView, { sid: 'gbrain-cockpit', scopeKey: 'scope', ctx: { rest: sessionRest } })
    await wait(20)
    const mount = mounts.at(-1)
    assert.ok(mount, 'the Space mounted')
    mount.reply = { image: PNG, width: 480, height: 300 }
    await wait(2600)
    assert.equal(mount.shots.length, 1, 'captured after settling')
    assert.equal(mount.shots[0].width, snapshots.SNAPSHOT_LIMITS.width)
    const stored = snapshots.readSnapshot('scope', 'gbrain-cockpit', 7)
    assert.equal(stored.image, PNG)
    assert.equal(stored.rev, 7)
    mount.reply = null
    await click('Back to Spaces')
    await wait(20)
    assert.equal(mount.shots.length, 2, 'captured again on leave')
    assert.equal(snapshots.readSnapshot('scope', 'gbrain-cockpit', 7).image, PNG, 'a failed capture keeps the previous preview')
    assert.deepEqual(navigations, ['/spaces'])
  } finally { globalThis.setTimeout = realTimeout; await cleanup() }
})

test('a Space that never boots is never captured and leaving still navigates', async () => {
  const { SpaceView } = ui()
  data.detail = space({ status: 'building', head_rev: 0 })
  try {
    await render(SpaceView, { sid: 'gbrain-cockpit', ctx: { rest: sessionRest } })
    await click('Back to Spaces')
    await wait(10)
    assert.equal(mounts.length, 0)
    assert.equal(snapshots.readSnapshot(null, 'gbrain-cockpit'), null)
    assert.deepEqual(navigations, ['/spaces'])
  } finally { await cleanup() }
})

test('notices float in a dock over the canvas that minimises to a pill and comes back for a new notice', async () => {
  const { SpaceView } = ui()
  data.detail = space({ storage: { warnings: [{ resource: 'source_bytes', used: 60000, limit: 65536 }] } })
  try {
    await render(SpaceView, { sid: 'gbrain-cockpit', ctx: { rest: sessionRest } })
    const dock = document.querySelector('.ls-content > .ls-notices')
    assert.ok(dock, 'the dock is inside the canvas region, not in the header flow')
    assert.ok(dock.previousElementSibling.classList.contains('ls-sandbox'))
    assert.match(dock.textContent, /Storage 92% full/)
    assert.equal(document.querySelector('.ls-notice-pill'), null)
    await click('Minimise')
    assert.equal(document.querySelector('.ls-notice-list').hidden, true, 'the expanded notices no longer cover the canvas')
    const pill = document.querySelector('.ls-notice-pill')
    assert.equal(pill.textContent, 'Storage 92% full')
    assert.equal(pill.getAttribute('aria-expanded'), 'false')
    await act(async () => mounts.at(-1)?.options.onEvent?.({ kind: 'fault', count: 1 }))
    assert.equal(document.querySelector('.ls-notice-list').hidden, false, 'a new notice expands the dock')
    assert.match(document.querySelector('.ls-notice-list').textContent, /uncaught error/)
    await act(async () => document.querySelector('.ls-notices').dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true })))
    const two = document.querySelector('.ls-notice-pill')
    assert.match(two.textContent, /2 notices/)
    assert.ok(two.classList.contains('ls-alert'), 'a failure in the stack tints the pill')
    await act(async () => two.click())
    assert.equal(document.querySelector('.ls-notice-list').hidden, false)
  } finally { await cleanup() }
})

test('the dock takes pointer input only on its own notices and is absent with none', async () => {
  const { styles } = load(resolve(root, 'src/desktop/ui/styles.js'))
  assert.match(styles, /\.ls-notices\{[^}]*pointer-events:none/)
  assert.match(styles, /\.ls-notices>\*\{pointer-events:auto\}/)
  assert.match(styles, /\.ls-notices\[data-empty\]\{display:none\}/)
  const { SpaceView } = ui()
  data.detail = space()
  try {
    await render(SpaceView, { sid: 'gbrain-cockpit', ctx: { rest: sessionRest } })
    assert.equal(document.querySelector('.ls-notices').dataset.empty, 'true')
    assert.equal(button('Minimise'), undefined)
  } finally { await cleanup() }
})

test('dismissing a notice still uses the shared notice contract inside the dock', async () => {
  const { SpaceView } = ui()
  data.detail = space({ storage: { warnings: [{ resource: 'source_bytes', used: 60000, limit: 65536 }] } })
  try {
    await render(SpaceView, { sid: 'gbrain-cockpit', ctx: { rest: sessionRest } })
    await click('Hide until it changes')
    assert.doesNotMatch(document.body.textContent, /Storage 92% full/)
    assert.equal(document.querySelector('.ls-notices').dataset.empty, 'true')
  } finally { await cleanup() }
})

test('Details holds freshness, storage, access, history and runtime with their manage actions', async () => {
  const { SpaceView } = ui()
  data.detail = space({
    manifest: { upkeep: { handler: 'feed' } },
    freshness: { last_success_at: 1700000000, source_as_of: 1699990000, sources: [{ id: 'usgs-bulletins', url: 'https://earthquake.usgs.gov/feed.atom' }] },
    activity: { kind: 'data', actor: 'agent:Hermes', at: 1700000000 },
    grants: [{ capability: 'net', status: 'granted' }, { capability: 'data', status: 'granted' }],
    storage: { warnings: [{ resource: 'source_bytes', used: 60000, limit: 65536 }] },
    recent_runs: [{ id: 'r1', status: 'succeeded', changed: { added: 2, unchanged: 3 }, ended_at: 1700000000 }]
  })
  try {
    await render(SpaceView, { sid: 'gbrain-cockpit', ctx: { rest: sessionRest } })
    await click('Details')
    const dialog = document.querySelector('[role="dialog"]')
    const sections = [...dialog.querySelectorAll('section')].map(node => node.getAttribute('aria-label'))
    assert.deepEqual(sections, ['Freshness', 'Storage use', 'Access', 'History', 'Runtime'])
    const text = id => dialog.querySelector(`section[aria-label="${id}"]`).textContent
    assert.match(text('Freshness'), /Latest changeRefreshed from earthquake\.usgs\.gov/)
    assert.match(text('Freshness'), /Sourceusgs-bulletins · earthquake\.usgs\.gov/)
    assert.match(text('Storage use'), /Storage 92% full.*Writes stop at the limit/)
    assert.doesNotMatch(text('Storage use'), /60000|65536/, 'no raw byte counts')
    assert.match(text('Access'), /InternetOn.*RecordsAllowed/)
    assert.match(text('History'), /Revision7.*Last refresh2 added/)
    assert.match(text('Runtime'), /HostAvailable.*Space app/)
    for (const label of ['Manage upkeep', 'Review storage', 'Manage access', 'Open history']) assert.ok(button(label), label)
    await click('Manage access')
    assert.match(document.querySelector('[role="dialog"] h2').textContent, /Permissions · GBrain Cockpit/)
  } finally { await cleanup() }
})

test('narrow and compact islands keep every control, as icons with their accessible names', async () => {
  const { styles } = load(resolve(root, 'src/desktop/ui/styles.js'))
  const hidden = styles.match(/([^{}]*\.ls-island-button \.ls-label[^{}]*)\{([^}]*)\}/)
  assert.ok(hidden, 'a rule hides island labels')
  for (const mode of ['compact', 'narrow']) assert.ok(hidden[1].includes(`.ls-frame[data-header-mode=${mode}] .ls-island-button .ls-label`), `${mode} labels are covered`)
  assert.match(hidden[2], /position:absolute;width:1px;height:1px;overflow:hidden;clip:rect\(0,0,0,0\)/, 'visually hidden, not display:none')
  assert.doesNotMatch(styles, /\.ls-island-button[^{}]*\{[^}]*display:none/, 'no island control is removed at any width')
  assert.ok(styles.includes('.ls-frame[data-header-mode=narrow] .ls-notices{right:8px;left:8px;bottom:8px;width:auto}'))
  const { SpaceView } = ui()
  data.detail = space({ manifest: { upkeep: { handler: 'feed' } }, grants: [{ capability: 'net', status: 'granted' }] })
  const style = document.createElement('style')
  style.textContent = styles
  document.head.append(style)
  try {
    await render(SpaceView, { sid: 'gbrain-cockpit', ctx: { rest: sessionRest } })
    const frame = document.querySelector('.ls-frame')
    assert.equal(frame.dataset.headerMode, 'narrow', 'without a measurement the frame starts narrow')
    for (const label of ['Back to Spaces', 'Internet on', 'Refresh now', 'Details', 'More Space actions']) {
      const node = button(label)
      assert.ok(node, label)
      assert.notEqual(window.getComputedStyle(node).display, 'none', `${label} stays in the bar`)
    }
    assert.equal(window.getComputedStyle(document.querySelector('.ls-frame-meta-text')).position, 'absolute', 'the phrase text is kept for assistive tech while the dot stays visible')
  } finally { style.remove(); await cleanup() }
})

test('floating surfaces are tinted from the opaque system canvas colour so text keeps contrast over any Space', () => {
  const { styles } = load(resolve(root, 'src/desktop/ui/styles.js'))
  const token = name => Number(styles.match(new RegExp(`--${name}:color-mix\\(in srgb,Canvas (\\d+)%,transparent\\)`))?.[1])
  assert.ok(token('ls-glass') >= 75, 'islands')
  assert.ok(token('ls-glass-strong') >= 90, 'notices float over arbitrary content and need a near-opaque surface')
  assert.match(styles, /\.ls-banner\{[^}]*background:var\(--ls-glass-strong\)/)
  assert.match(styles, /\.ls-notice-pill\{[^}]*background:var\(--ls-glass-strong\)/)
  assert.doesNotMatch(styles, /ui-bg-elevated[^;]*\) 70%,transparent/, 'no glass mixed from a translucent host token')
})

// --- review regressions ------------------------------------------------------------------------------------

test('a Space cannot get an oversized image stored by declaring a small size', () => {
  assert.deepEqual(snapshots.encodedSize(png(4096, 4096)), { width: 4096, height: 4096 })
  assert.equal(snapshots.writeSnapshot(null, 'demo-space', { image: png(4096, 4096), width: 480, height: 300, at: 1, rev: 1 }), false)
  // WebP headers as Chromium's canvas encoder writes them: lossy, lossless and extended.
  const webp = (chunk, bytes) => 'data:image/webp;base64,' + Buffer.concat([Buffer.from('RIFF\0\0\0\0WEBP' + chunk), Buffer.alloc(4), Buffer.from(bytes), Buffer.alloc(8)]).toString('base64')
  assert.deepEqual(snapshots.encodedSize(webp('VP8 ', [0, 0, 0, 0x9d, 0x01, 0x2a, 480 & 255, 480 >> 8, 300 & 255, 300 >> 8])), { width: 480, height: 300 })
  assert.deepEqual(snapshots.encodedSize(webp('VP8X', [0, 0, 0, 0, 479 & 255, 479 >> 8, 0, 299 & 255, 299 >> 8, 0])), { width: 480, height: 300 })
  const w = 479, h = 299
  assert.deepEqual(snapshots.encodedSize(webp('VP8L', [0x2f, w & 255, (w >> 8) | ((h & 3) << 6), (h >> 2) & 255, (h >> 10) & 15])), { width: 480, height: 300 })
})

test('leaving waits for the capture but never navigates once the view is gone', async () => {
  const { SpaceView } = ui()
  data.detail = space()
  try {
    await render(SpaceView, { sid: 'gbrain-cockpit', ctx: { rest: sessionRest } })
    await wait(20)
    mounts.at(-1).snapshot = () => new Promise(() => {})
    await click('Back to Spaces')
    await cleanup()
    navigations.push('/another-page')
    await act(async () => new Promise(done => setTimeout(done, 800)))
    assert.deepEqual(navigations, ['/another-page'], 'the stale leave does not redirect the new page')
  } finally { if (document.getElementById('root').childNodes.length) await cleanup() }
})

test('minimising from the dock\'s own toggle moves focus to the pill, not into the hidden list', async () => {
  const { SpaceView } = ui()
  data.detail = space({ storage: { warnings: [{ resource: 'source_bytes', used: 60000, limit: 65536 }] } })
  try {
    await render(SpaceView, { sid: 'gbrain-cockpit', ctx: { rest: sessionRest } })
    const toggle = button('Minimise'); toggle.focus()
    await act(async () => toggle.click()); await wait(10)
    assert.equal(document.activeElement, document.querySelector('.ls-notice-pill'))
    await act(async () => document.activeElement.click()); await wait(10)
    assert.equal(document.activeElement, button('Minimise'))
    await act(async () => document.activeElement.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))); await wait(10)
    assert.equal(document.activeElement, document.querySelector('.ls-notice-pill'), 'Escape on the toggle does the same')
  } finally { await cleanup() }
})

test('at narrow width save feedback stays announced, only its words are visually hidden', () => {
  const { styles } = load(resolve(root, 'src/desktop/ui/styles.js'))
  assert.doesNotMatch(styles, /data-header-mode=narrow\] \.ls-save\{display:none/)
  assert.match(styles, /data-header-mode=narrow\] \.ls-save-text\{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect\(0,0,0,0\)/)
})

test('a notice republished with a new time keeps the dock minimised; a new notice reopens it and keeps focus', async () => {
  const { NoticeDock } = ui()
  const { Banner } = load(resolve(root, 'src/desktop/ui/components.jsx'))
  const dock = (title, key) => React.createElement(NoticeDock, {}, React.createElement(Banner, { title, noticeKey: key }))
  try {
    view = createRoot(document.getElementById('root'))
    await act(async () => view.render(dock('Bot request: busy · 8:13 PM', 'bot:a1:busy')))
    const toggle = button('Minimise'); toggle.focus()
    await act(async () => toggle.click()); await wait(10)
    assert.equal(document.activeElement, document.querySelector('.ls-notice-pill'))
    await act(async () => view.render(dock('Bot request: busy · 8:14 PM', 'bot:a1:busy'))); await wait(10)
    assert.equal(document.querySelector('.ls-notice-list').hidden, true, 'same notice, new minute: stays minimised')
    assert.equal(document.activeElement, document.querySelector('.ls-notice-pill'))
    await act(async () => view.render(dock('Bot replied · 8:15 PM', 'bot:a1:replied'))); await wait(10)
    assert.equal(document.querySelector('.ls-notice-list').hidden, false, 'a new status reopens the dock')
    assert.equal(document.activeElement, button('Minimise'), 'focus moves with the pill to the toggle, never to the body')
  } finally { await cleanup() }
})

test('the failure tint always resolves: the danger token ends in a literal colour, so a failure notice is never transparent', () => {
  const { styles } = load(resolve(root, 'src/desktop/ui/styles.js'))
  const chain = styles.match(/--ls-danger:([^;]+);/)[1]
  assert.match(chain, /var\(--color-destructive,#[0-9a-f]{6}\)/i, 'falls back to the host token, then a literal')
  assert.match(styles, /\.ls-banner\.ls-failed[^{]*\{background:color-mix\(in srgb,var\(--ls-danger\) \d+%,var\(--ls-glass-strong\)\)\}/)
})
