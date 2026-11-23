import './env.mjs'
import test from 'node:test'
import assert from 'node:assert/strict'
import { setTimeout as delay } from 'node:timers/promises'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { createRequire } from 'node:module'
import { homedir } from 'node:os'
import { join } from 'node:path'
import { mountSpace } from '../../../src/desktop/sandbox/index.js'
import { createSpaceSession } from '../../../src/desktop/ui/session.mjs'
import { projectResolver, spaceLoader } from '../../../src/guest/loader.mjs'

const sandbox = { format: 1, shell_srcdoc: readFileSync('src/living-spaces/guest/space-host.html', 'utf8') }
const image = 'data:image/webp;base64,AAAA'
const valid = { v: 1, type: 'snapshot', ok: true, image, width: 640, height: 480 }
async function until(check) {
  const deadline = Date.now() + 2000
  while (!check() && Date.now() < deadline) await delay(2)
  assert.ok(check(), 'expected port message arrived')
}
function hostFixture(boot = true) {
  const originalDocument = globalThis.document
  const originalWindow = globalThis.window
  globalThis.window = new EventTarget()
  let frame
  globalThis.document = { createElement() {
    frame = new EventTarget()
    frame.style = {}
    frame.setAttribute = () => {}
    frame.remove = () => {}
    frame.contentWindow = { postMessage(message, origin, ports) {
      frame.peer = structuredClone(ports[0], { transfer: [ports[0]] })
      frame.peer.onmessage = event => messages.push(event.data)
    } }
    return frame
  } }
  const events = [], messages = [], calls = []
  const mount = mountSpace({ append() {} }, {
    bundle: { space: { id: 'demo', name: 'Demo' }, rev: 1, manifest: {}, files: [], sandbox },
    call: async (...args) => { calls.push(args); return { ok: true, result: null } },
    onEvent: event => events.push(event)
  })
  if (boot) frame.dispatchEvent(new Event('load'))
  return { mount, frame, events, messages, calls, cleanup() {
    mount.destroy()
    frame.peer?.close()
    globalThis.document = originalDocument
    globalThis.window = originalWindow
  } }
}

for (const format of ['webp', 'png', 'jpeg']) test(`host accepts only the matching snapshot reply (${format})`, async () => {
  const f = hostFixture()
  try {
    const pending = f.mount.snapshot()
    await until(() => f.messages.length === 1)
    const request = f.messages[0]
    assert.deepEqual(request, { v: 1, type: 'snapshot', id: request.id, width: 640 })
    assert.ok(Number.isSafeInteger(request.id))
    const reply = { ...valid, id: request.id, image: `data:image/${format};base64,AAAA` }
    f.frame.peer.postMessage(reply)
    assert.deepEqual(await pending, { image: reply.image, width: 640, height: 480 })
    f.frame.peer.postMessage(reply)
    await delay(10)
    assert.equal(f.messages.length, 1, 'duplicate snapshot produces no port reply')
    assert.equal(f.events.some(event => event.kind === 'denied'), false)
    assert.deepEqual(f.calls, [])
  } finally { f.cleanup() }
})

for (const [name, extra] of [
  ['malformed data URL', { image: 'data:image/png;base64,AA!A' }],
  ['svg data URL', { image: 'data:image/svg+xml;base64,AAAA' }],
  ['oversized image', { image: 'data:image/png;base64,' + 'A'.repeat(350000) }],
  ['missing image', { image: undefined }],
  ['empty base64', { image: 'data:image/png;base64,' }],
  ['bad padding', { image: 'data:image/png;base64,AAAA===' }],
  ['low width', { width: 15 }], ['high width', { width: 1025 }],
  ['low height', { height: 15 }], ['high height', { height: 1025 }],
  ['fractional size', { width: 64.5 }], ['string size', { height: '480' }],
  ['wrong version', { v: 2 }], ['non-boolean ok', { ok: 1 }],
  ['capture failure', { ok: false, reason: 'Encoding failed' }]
]) test(`host resolves null for ${name}`, async () => {
  const f = hostFixture()
  try {
    const pending = f.mount.snapshot({ width: 320, timeoutMs: 1000 })
    await until(() => f.messages.length === 1)
    assert.equal(f.messages[0].width, 320)
    f.frame.peer.postMessage({ ...valid, id: f.messages[0].id, ...extra })
    assert.equal(await pending, null)
    assert.deepEqual(f.calls, [])
    assert.equal(f.events.some(event => event.kind === 'denied'), false)
  } finally { f.cleanup() }
})

test('host accepts exact image and dimension limits', async () => {
  const f = hostFixture()
  try {
    const pending = f.mount.snapshot({ width: 1024 })
    await until(() => f.messages.length === 1)
    const prefix = 'data:image/png;base64,'
    const reply = { ...valid, id: f.messages[0].id, image: prefix + 'A'.repeat(350000 - prefix.length), width: 16, height: 1024 }
    f.frame.peer.postMessage(reply)
    assert.deepEqual(await pending, { image: reply.image, width: 16, height: 1024 })
  } finally { f.cleanup() }
})

for (const wrongId of [12345, '1', 1.5, Number.MAX_SAFE_INTEGER + 1]) test(`host ignores unmatched snapshot id ${wrongId}`, async () => {
  const f = hostFixture()
  try {
    const pending = f.mount.snapshot({ timeoutMs: 60 })
    await until(() => f.messages.length === 1)
    f.frame.peer.postMessage({ ...valid, id: wrongId })
    assert.equal(await pending, null)
    assert.equal(f.messages.length, 1)
    assert.equal(f.events.some(event => event.kind === 'denied'), false)
    assert.deepEqual(f.calls, [])
  } finally { f.cleanup() }
})

test('host snapshot times out without a reply', async () => {
  const f = hostFixture()
  try { assert.equal(await f.mount.snapshot({ timeoutMs: 10 }), null) }
  finally { f.cleanup() }
})

test('unsolicited snapshot messages never become bridge requests or replies', async () => {
  const f = hostFixture()
  try {
    f.frame.peer.postMessage({ ...valid, id: 99, op: 'data.put', args: {} })
    f.frame.peer.postMessage({ v: 99, type: 'snapshot', id: 100 })
    await delay(20)
    assert.deepEqual(f.messages, [])
    assert.deepEqual(f.calls, [])
    assert.equal(f.events.some(event => event.kind === 'denied'), false)
  } finally { f.cleanup() }
})

for (const action of ['destroy', 'close', 'reload']) test(`pending snapshots settle null after ${action}`, async () => {
  const f = hostFixture()
  try {
    const first = f.mount.snapshot()
    const second = f.mount.snapshot()
    await until(() => f.messages.length === 2)
    assert.notEqual(f.messages[0].id, f.messages[1].id)
    if (action === 'destroy') f.mount.destroy()
    if (action === 'close') f.mount.postEvent('session.closed', { reason: 'closed' })
    if (action === 'reload') f.frame.dispatchEvent(new Event('load'))
    assert.deepEqual(await Promise.all([first, second]), [null, null])
    assert.equal(await f.mount.snapshot(), null)
  } finally { f.cleanup() }
})

test('unbooted host snapshot returns null without sending', async () => {
  const f = hostFixture(false)
  try {
    assert.equal(await f.mount.snapshot(), null)
    assert.deepEqual(f.messages, [])
  } finally { f.cleanup() }
})

test('host refuses invalid capture options without sending', async () => {
  const f = hostFixture()
  try {
    for (const width of [63, 1025, 64.5, '640', NaN]) assert.equal(await f.mount.snapshot({ width }), null)
    for (const timeoutMs of [-1, Infinity, '10', NaN]) assert.equal(await f.mount.snapshot({ timeoutMs }), null)
    assert.deepEqual(f.messages, [])
  } finally { f.cleanup() }
})

test('concurrent snapshots settle independently even out of order', async () => {
  const f = hostFixture()
  try {
    const first = f.mount.snapshot({ width: 64 })
    const second = f.mount.snapshot({ width: 1024 })
    await until(() => f.messages.length === 2)
    f.frame.peer.postMessage({ ...valid, id: f.messages[1].id, width: 1024 })
    assert.deepEqual(await second, { image, width: 1024, height: 480 })
    f.frame.peer.postMessage({ ...valid, id: f.messages[0].id, width: 64 })
    assert.deepEqual(await first, { image, width: 64, height: 480 })
  } finally { f.cleanup() }
})

function sessionFixture(snapshot = async () => ({ image, width: 640, height: 480 })) {
  const state = { connectionId: 'backend', profile: 'profile' }
  const calls = []
  const host = { state: { connectionId: { get: () => state.connectionId }, profile: { get: () => state.profile } } }
  const session = createSpaceSession({ host, backend: { ...state }, sid: 'demo', container: {}, onEvent() {},
    rest: async (path, request = {}) => {
      if (request.method === 'DELETE') return { closed: true }
      if (path.endsWith('/sessions')) return { session: 'session', head_rev: 1, grants: [] }
      if (path.endsWith('/bundle')) return { rev: 1 }
      throw new Error(`Unexpected path ${path}`)
    },
    mount: () => ({ destroy() {}, snapshot(options) { calls.push(options); return snapshot(options) } })
  })
  return { session, state, calls }
}

test('session snapshot delegates options and returns null before mount and after close', async () => {
  const f = sessionFixture()
  assert.equal(await f.session.snapshot(), null)
  await f.session.ready
  const options = { width: 320, timeoutMs: 1234 }
  assert.deepEqual(await f.session.snapshot(options), { image, width: 640, height: 480 })
  assert.deepEqual(f.calls, [options])
  await f.session.destroy()
  assert.equal(await f.session.snapshot(), null)
  assert.equal(f.calls.length, 1)
})

for (const key of ['profile', 'connectionId']) test(`session snapshot returns null for an inactive ${key}`, async () => {
  const f = sessionFixture()
  await f.session.ready
  f.state[key] = 'other'
  assert.equal(await f.session.snapshot(), null)
  assert.deepEqual(f.calls, [])
  f.state[key] = key === 'profile' ? 'profile' : 'backend'
  await f.session.destroy()
})

test('session withholds a capture that completes after close or a scope change', async () => {
  for (const action of ['close', 'profile']) {
    let complete
    const f = sessionFixture(() => new Promise(resolve => { complete = resolve }))
    await f.session.ready
    const pending = f.session.snapshot()
    if (action === 'close') await f.session.destroy()
    else f.state.profile = 'other'
    complete({ image, width: 640, height: 480 })
    assert.equal(await pending, null)
    if (action !== 'close') { f.state.profile = 'profile'; await f.session.destroy() }
  }
})

test('session converts a mounted capture failure to null', async () => {
  const f = sessionFixture(async () => { throw new Error('Renderer unavailable') })
  await f.session.ready
  assert.equal(await f.session.snapshot(), null)
  await f.session.destroy()
})

// This VM exercises the real loader's protocol, not browser SVG rasterization.
function guestFixture() {
  const events = new Map(), messages = []
  const parent = {}
  let captures = 0
  const element = () => ({ style: {}, setAttribute() {}, append() {}, replaceChildren() {} })
  const document = { head: element(), body: element(), createElement: element, addEventListener() {},
    documentElement: { cloneNode() { captures++; throw new Error('Capture unavailable '.repeat(30)) } } }
  const window = { parent, innerWidth: 800, innerHeight: 600, scrollX: 0, scrollY: 0,
    addEventListener: (name, cb) => events.set(name, cb), removeEventListener: name => events.delete(name) }
  const port = { postMessage: message => messages.push(structuredClone(message)), close() {} }
  const context = vm.createContext({ window, document, console: { log() {} }, setInterval() {}, clearInterval() {} })
  vm.runInContext(`(${spaceLoader.toString()})((${projectResolver.toString()})())`, context)
  events.get('message')({ source: parent, data: { v: 1, type: 'space-boot', grants: [],
    bundle: { space: { id: 'demo', name: 'Demo' }, rev: 1, manifest: {}, files: [] } }, ports: [port] })
  return { window, port, messages, captures: () => captures }
}

test('guest replies to a capture failure with the matching id and bounded reason', async () => {
  const f = guestFixture()
  f.port.onmessage({ data: { v: 1, type: 'snapshot', id: 7, width: 640 } })
  await until(() => f.messages.length === 1)
  assert.deepEqual(Object.keys(f.messages[0]).sort(), ['id', 'ok', 'reason', 'type', 'v'])
  assert.equal(f.messages[0].id, 7)
  assert.equal(f.messages[0].v, 1)
  assert.equal(f.messages[0].type, 'snapshot')
  assert.equal(f.messages[0].ok, false)
  assert.ok(f.messages[0].reason.length > 0 && f.messages[0].reason.length <= 200)
  assert.equal(f.captures(), 1)
})

test('guest rejects invalid widths, ignores unusable ids and never consumes an API reply', async () => {
  const f = guestFixture()
  const pending = f.window.space.get('papers', 'one')
  const id = f.messages[0].id
  for (const width of [63, 1025, 1.5, '640']) f.port.onmessage({ data: { v: 1, type: 'snapshot', id, width } })
  f.port.onmessage({ data: { v: 1, type: 'snapshot', id: 'bad', width: 640 } })
  f.port.onmessage({ data: { v: 2, type: 'snapshot', id, width: 640 } })
  await until(() => f.messages.length === 5)
  assert.equal(f.captures(), 0)
  assert.ok(f.messages.slice(1).every(message => message.ok === false && message.id === id))
  f.port.onmessage({ data: { v: 1, id, ok: true, result: { id: 'one' } } })
  assert.deepEqual(await pending, { id: 'one' })
})

test('closed guest ignores subsequent snapshot requests', async () => {
  const f = guestFixture()
  f.port.onmessage({ data: { v: 1, type: 'event', event: 'session.closed', payload: { reason: 'closed' } } })
  f.port.onmessage({ data: { v: 1, type: 'snapshot', id: 7, width: 640 } })
  await delay(10)
  assert.deepEqual(f.messages, [])
  assert.equal(f.captures(), 0)
})

const require = createRequire(join(homedir(), '.hermes/hermes-agent/apps/desktop/node_modules/react/package.json'))
const { JSDOM } = require('jsdom')
// jsdom has no rasterizer. Only Image.decode and canvas rendering are replaced.
async function renderingFixture(t, { webp = true, decode = async () => {} } = {}) {
  const dom = new JSDOM('<!doctype html><html><head></head><body></body></html>', { runScripts: 'outside-only' })
  t.after(() => dom.window.close())
  const { window } = dom
  const messages = [], encodings = [], draws = [], decoded = []
  window.URL.createObjectURL = () => 'blob:fixture'
  window.eval(`(${spaceLoader.toString()})((${projectResolver.toString()})())`)
  const port = { postMessage: message => messages.push(structuredClone(message)), close() {} }
  window.dispatchEvent(new window.MessageEvent('message', { source: window.parent, ports: [port], data: {
    v: 1, type: 'space-boot', grants: [], bundle: { space: { id: 'demo', name: 'Demo' }, rev: 1, manifest: {},
      files: [{ path: 'index.html', mime: 'text/html', text: '<html><head></head><body></body></html>' }] }
  } }))
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(window.document.querySelector('[role=alert]'), null)
  window.Image = class {
    async decode() { decoded.push(this.src); await decode() }
  }
  window.HTMLCanvasElement.prototype.getContext = function () {
    return { drawImage: (...args) => {
      if (args[0].id === 'broken-image') throw new Error('Unreadable image')
      draws.push({ canvas: this, args })
    } }
  }
  window.HTMLCanvasElement.prototype.toDataURL = function (type, quality) {
    encodings.push({ id: this.id, type, quality, width: this.width, height: this.height })
    return this.id === 'live-canvas' ? 'data:image/png;base64,Q0FOVkFT' : `data:image/${type === 'image/webp' && webp ? 'webp' : 'png'};base64,AAAA`
  }
  window.fetch = () => { assert.fail('Snapshots must not fetch resources') }
  return { window, port, messages, encodings, draws, decoded }
}

test('guest serializes current styles, pixels, form values and scroll offset without changing the live DOM', async t => {
  const f = await renderingFixture(t)
  const { document } = f.window
  document.head.innerHTML = '<style>.initial {color: red}</style><link rel="stylesheet" href="blob:sheet"><meta http-equiv="refresh" content="1">'
  document.styleSheets[0].insertRule('.current {color: blue}', 1)
  const sheets = [...document.styleSheets, { get cssRules() { throw new Error('Unreadable sheet') } }]
  Object.defineProperty(document, 'styleSheets', { value: sheets })
  document.body.innerHTML = '<canvas id="live-canvas" width="320" height="200"></canvas><img id="blob-image" src="blob:fixture" srcset="blob:other 2x"><img id="data-image" src="data:image/png;base64,AAAA"><img id="broken-image" src="blob:broken"><input value="old"><input type="checkbox" checked><textarea>old</textarea><select><option selected>old</option><option>current</option></select><script>neverRuns()</script>'
  for (const img of document.images) {
    Object.defineProperties(img, { naturalWidth: { value: 32 }, naturalHeight: { value: 24 } })
  }
  document.querySelector('input').value = 'current input'
  document.querySelector('[type=checkbox]').checked = false
  document.querySelector('textarea').value = 'current textarea'
  document.querySelector('select').selectedIndex = 1
  Object.assign(f.window, { innerWidth: 800, innerHeight: 600, scrollX: 12, scrollY: 34 })
  const original = document.documentElement.outerHTML
  f.port.onmessage({ data: { v: 1, type: 'snapshot', id: 3, width: 640 } })
  await until(() => f.messages.length === 1)
  assert.deepEqual(f.messages[0], { ...valid, id: 3 })
  assert.equal(f.decoded.length, 1)
  assert.match(f.decoded[0], /^data:image\/svg\+xml/)
  const svg = new f.window.DOMParser().parseFromString(decodeURIComponent(f.decoded[0].split(',')[1]), 'image/svg+xml')
  assert.equal(svg.querySelector('parsererror'), null)
  assert.equal(svg.documentElement.getAttribute('width'), '800')
  assert.equal(svg.documentElement.getAttribute('height'), '600')
  const clone = svg.querySelector('foreignObject > html')
  assert.equal(clone.querySelectorAll('script,meta[http-equiv],link[rel=stylesheet],canvas').length, 0)
  assert.equal(clone.querySelectorAll('style').length, 1)
  assert.ok(clone.querySelector('style').textContent.includes(sheets[0].cssRules[1].cssText))
  assert.equal(clone.querySelector('#live-canvas').localName, 'img')
  assert.equal(clone.querySelector('#live-canvas').getAttribute('src'), 'data:image/png;base64,Q0FOVkFT')
  assert.equal(clone.querySelector('#blob-image').getAttribute('srcset'), null)
  for (const id of ['blob-image', 'data-image']) assert.equal(clone.querySelector(`#${id}`).getAttribute('src'), 'data:image/png;base64,AAAA')
  assert.equal(clone.querySelector('#broken-image').getAttribute('src'), 'blob:broken', 'unreadable images are skipped')
  assert.equal(clone.querySelector('input').getAttribute('value'), 'current input')
  assert.equal(clone.querySelector('[type=checkbox]').hasAttribute('checked'), false)
  assert.equal(clone.querySelector('textarea').textContent, 'current textarea')
  assert.equal(clone.querySelector('option').hasAttribute('selected'), false)
  assert.equal(clone.querySelectorAll('option')[1].hasAttribute('selected'), true)
  assert.match(clone.getAttribute('style'), /left: -12px !important/)
  assert.match(clone.getAttribute('style'), /top: -34px !important/)
  assert.deepEqual(f.encodings.at(-1), { id: '', type: 'image/webp', quality: 0.72, width: 640, height: 480 })
  assert.deepEqual(f.draws.at(-1).args.slice(1), [0, 0, 640, 480])
  assert.equal(document.documentElement.outerHTML, original)
})

test('guest falls back to PNG when WebP encoding is unavailable', async t => {
  const f = await renderingFixture(t, { webp: false })
  f.port.onmessage({ data: { v: 1, type: 'snapshot', id: 4, width: 64 } })
  await until(() => f.messages.length === 1)
  assert.equal(f.messages[0].ok, true)
  assert.equal(f.messages[0].image, 'data:image/png;base64,AAAA')
  assert.deepEqual(f.encodings.map(encoding => encoding.type), ['image/webp', 'image/png'])
})

for (const [innerHeight, expected] of [[1, 16], [100000, 1024]]) test(`guest clamps output height to ${expected}`, async t => {
  const f = await renderingFixture(t)
  Object.assign(f.window, { innerWidth: 800, innerHeight })
  f.port.onmessage({ data: { v: 1, type: 'snapshot', id: 5, width: 640 } })
  await until(() => f.messages.length === 1)
  assert.equal(f.messages[0].height, expected)
  assert.equal(f.messages[0].width, 640)
})

test('guest reports SVG decode failures and suppresses late capture replies after closure', async t => {
  const f = await renderingFixture(t, { decode: async () => { throw new Error('SVG decode failed') } })
  f.port.onmessage({ data: { v: 1, type: 'snapshot', id: 6, width: 640 } })
  await until(() => f.messages.length === 1)
  assert.deepEqual(f.messages[0], { v: 1, type: 'snapshot', id: 6, ok: false, reason: 'SVG decode failed' })
  assert.deepEqual(f.encodings, [])
  let complete
  const late = await renderingFixture(t, { decode: () => new Promise(resolve => { complete = resolve }) })
  late.port.onmessage({ data: { v: 1, type: 'snapshot', id: 7, width: 640 } })
  assert.equal(typeof complete, 'function')
  late.port.onmessage({ data: { v: 1, type: 'event', event: 'session.closed', payload: { reason: 'closed' } } })
  complete()
  await new Promise(resolve => setImmediate(resolve))
  assert.deepEqual(late.messages, [])
})
