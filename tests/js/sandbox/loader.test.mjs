import './env.mjs'
import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { spaceLoader, projectResolver } from '../../../src/guest/loader.mjs'

const tick = () => new Promise(resolve => setImmediate(resolve))
function loaderFixture(files = [], scripts = []) {
  const events = new Map()
  const messages = []
  const timers = []
  const parent = {}
  const element = tag => ({ tag, attributes: [], style: {}, children: [], setAttribute(k, v) { this[k] = v }, append(...nodes) { this.children.push(...nodes) }, replaceChildren(...nodes) { this.children = nodes } })
  const document = {
    head: element('head'), body: element('body'),
    documentElement: element('html'), querySelector() { return null },
    createElement: element,
    addEventListener: (name, cb) => events.set(name, cb)
  }
  const window = { parent, addEventListener: (name, cb) => events.set(name, cb), removeEventListener: name => events.delete(name) }
  const port = { postMessage: message => messages.push(structuredClone(message)), close() { this.closed = true } }
  const DOMParser = class {
    parseFromString() {
      return { title: '', documentElement: element('html'), head: { childNodes: [] },
        body: { attributes: [], childNodes: [] }, querySelectorAll: selector => selector === 'script' ? scripts : [] }
    }
  }
  const context = vm.createContext({ window, document, DOMParser, Map, Set, Error, TypeError, Promise, Object, JSON, String, Uint8Array, Blob, URL, atob, console: Object.fromEntries(['log', 'info', 'warn', 'error', 'debug', 'trace', 'dir', 'table', 'assert'].map(level => [level, () => {}])), setInterval(fn, ms) { timers.push({ fn, ms }); return timers.length }, clearInterval() {} })
  vm.runInContext(`(${spaceLoader.toString()})((${projectResolver.toString()})())`, context)
  events.get('message')({ source: parent, data: { type: 'space-boot', v: 1, grants: ['data'], bundle: { space: { id: 'fixture', name: 'Fixture' }, rev: 3, manifest: { entry: 'index.html' }, files } }, ports: [port] })
  return { api: window.space, port, messages, events, timers, document, context }
}
const reply = (f, message, result) => f.port.onmessage({ data: { v: 1, id: message.id, ok: true, result } })

test('frame API translates collection methods into the frozen envelopes', async () => {
  const f = loaderFixture()
  const query = f.api.query('papers', { where: { status: 'reading' }, order: '-updated_at', limit: 10 })
  assert.deepEqual(f.messages[0], { v: 1, id: 1, op: 'data.query', args: { collection: 'papers', where: { status: 'reading' }, order: '-updated_at', limit: 10 } })
  reply(f, f.messages[0], { records: [{ id: 'demo' }], seq: 9, total: 1 })
  assert.deepEqual(await query, [{ id: 'demo' }])
  const operations = [
    ['data.get', () => f.api.get('papers', 'demo'), { collection: 'papers', id: 'demo' }],
    ['data.put', () => f.api.put('papers', 'demo', { note: 'demo' }, { baseRev: 2, merge: false }), { collection: 'papers', id: 'demo', data: { note: 'demo' }, base_rev: 2, merge: false }],
    ['data.delete', () => f.api.delete('papers', 'demo', { baseRev: 2 }), { collection: 'papers', id: 'demo', base_rev: 2 }],
    ['data.batch', () => f.api.batch([{ op: 'delete', collection: 'papers', id: 'demo', base_rev: 2 }]), { ops: [{ op: 'delete', collection: 'papers', id: 'demo', base_rev: 2 }] }],
    ['refresh', () => f.api.refresh(), {}], ['runs.list', () => f.api.runs(), {}]
  ]
  for (const [op, invoke, args] of operations) {
    const result = invoke()
    const message = f.messages.at(-1)
    assert.equal(message.op, op)
    assert.deepEqual(message.args, args)
    reply(f, message, { confirmed: true })
    assert.deepEqual(await result, { confirmed: true })
  }
  assert.equal(f.api.meta.space.rev, 3)
  assert.equal(f.api.meta.space.id, 'fixture')
  assert.equal(f.api.field({ data: { x: 0, y: false, z: '' }, source: { x: 2, y: 2, z: 2 } }, 'x'), 0)
  assert.equal(f.api.field({ data: { x: null }, source: { x: 'source' } }, 'x'), 'source')
})
test('frame API throws SpaceError with conflict code and current record', async () => {
  const f = loaderFixture()
  const pending = f.api.put('papers', 'demo', { note: 'mine' }, { baseRev: 1 })
  f.port.onmessage({ data: { v: 1, id: 1, ok: false, error: { code: 'conflict', message: 'Changed elsewhere', current: { id: 'demo', rev: 2 } } } })
  await assert.rejects(pending, error => error.name === 'SpaceError' && error.code === 'conflict' && error.current.rev === 2)
})
test('frame events dispatch only v1 messages and unsubscribe removes listeners', () => {
  const f = loaderFixture()
  const changes = []
  const runs = []
  const unsubscribe = f.api.on('change', payload => changes.push(payload))
  f.api.on('run', run => runs.push(run))
  const event = { type: 'event', event: 'data.changed', payload: { seq: 1, changes: [] } }
  f.port.onmessage({ data: { v: 2, ...event } })
  f.port.onmessage({ data: { v: 1, ...event } })
  unsubscribe()
  f.port.onmessage({ data: { v: 1, ...event } })
  f.port.onmessage({ data: { v: 1, type: 'event', event: 'run.updated', payload: { status: 'running' } } })
  assert.equal(changes.length, 1)
  assert.equal(runs[0].status, 'running')
  assert.throws(() => f.api.on('unknown', () => {}), /Unknown/)
})
test('session.closed rejects pending and future operations without forwarding', async () => {
  const f = loaderFixture()
  const pending = f.api.get('papers', 'demo')
  f.port.onmessage({ data: { v: 1, type: 'event', event: 'session.closed', payload: { reason: 'closed by host' } } })
  await assert.rejects(pending, error => error.code === 'session_invalid')
  await assert.rejects(f.api.refresh(), error => error.code === 'session_invalid')
  assert.equal(f.messages.length, 1)
  assert.equal(f.port.closed, true)
})
test('missing entry produces a visible error screen and a bounded diagnostic', async () => {
  const f = loaderFixture()
  await tick()
  const panel = f.document.body.children[0]
  assert.equal(panel.role, 'alert')
  assert.equal(panel.children[0].textContent, 'This Space could not load')
  assert.equal(panel.children[1].textContent, 'Entry not found: index.html')
  assert.ok(f.timers[0].ms >= 500)
  f.timers[0].fn()
  const log = f.messages.at(-1)
  assert.equal(log.op, 'log')
  assert.ok(log.args.entries[0].msg.includes('Entry not found'))
  assert.equal(log.args.lifecycle, 'failed')
  assert.ok(Number.isInteger(log.id))
})
test('console, errors, rejected promises and CSP diagnostics share a fifty-entry batch', async () => {
  const f = loaderFixture()
  await tick()
  f.timers[0].fn()
  reply(f, f.messages.at(-1), { stored: f.messages.at(-1).args.entries.length })
  await tick()
  f.events.get('error')({ message: 'Public demo failure', filename: 'demo.js', lineno: 1 })
  f.events.get('unhandledrejection')({ reason: 'Public demo rejection' })
  f.events.get('securitypolicyviolation')({ effectiveDirective: 'connect-src', blockedURI: 'http://127.0.0.1:9/x' })
  vm.runInContext('for (let i = 0; i < 100; i++) console.log("public demo", i)', f.context)
  f.timers[0].fn()
  const batch = f.messages.at(-1)
  assert.equal(batch.args.entries.length, 50)
  assert.equal(batch.args.entries.at(-1).msg, 'Space log overflow: dropped 54 entries')
  assert.equal(batch.args.dropped, 54)
  assert.equal(batch.args.unconfirmed, 0)
  assert.ok(batch.args.entries.some(entry => entry.msg.includes('connect-src')))
  assert.ok(batch.args.entries.some(entry => entry.msg.includes('unhandled rejection')))
})

test('entry module scripts load from a blob URL so the browser fires load', async () => {
  const script = { attributes: [{ name: 'type', value: 'module' }], type: 'module', textContent: 'import "https://space.invalid/app.js"', remove() {} }
  const f = loaderFixture([{ path: 'index.html', mime: 'text/html', text: '<main>Demo</main>' }], [script])
  await tick()
  const appended = f.document.body.children.at(-1)
  assert.equal(appended.type, 'module')
  assert.match(appended.src || '', /^blob:/, 'browsers fire no load event for inline module scripts')
  assert.equal(appended.textContent || '', '')
})

test('entry module scripts keep a non-relative src instead of replacing it with their inline text', async () => {
  const script = { attributes: [{ name: 'type', value: 'module' }, { name: 'src', value: 'https://cdn.example.test/app.js' }], type: 'module', textContent: '', remove() {} }
  const f = loaderFixture([{ path: 'index.html', mime: 'text/html', text: '<main>Demo</main>' }], [script])
  await tick()
  const appended = f.document.body.children.at(-1)
  assert.equal(appended.type, 'module')
  assert.equal(appended.getAttribute ? appended.getAttribute('src') : appended.src, 'https://cdn.example.test/app.js')
})

test('successful entry reports loaded once after entry scripts settle', async () => {
  const script = { attributes: [{ name: 'type', value: 'module' }], type: 'module', textContent: 'export {}', remove() {} }
  const f = loaderFixture([{ path: 'index.html', mime: 'text/html', text: '<main>Demo</main>' }], [script])
  await tick()
  f.timers[0].fn()
  assert.equal(f.messages.length, 0)
  f.document.body.children.at(-1).onload()
  await tick()
  f.timers[0].fn()
  const report = f.messages.at(-1)
  assert.deepEqual(report.args, { entries: [], dropped: 0, unconfirmed: 0, lifecycle: 'loaded' })
  reply(f, report, { stored: 0 })
  await tick()
  f.timers[0].fn()
  assert.equal(f.messages.length, 1)
  assert.equal(f.events.has('message'), false)
})

test('script failure reports failed with its existing loader message even after console flooding', async () => {
  const script = { attributes: [{ name: 'type', value: 'module' }], type: 'module', textContent: 'broken import', remove() {}, getAttribute() { return null } }
  const f = loaderFixture([{ path: 'index.html', mime: 'text/html', text: '' }], [script])
  vm.runInContext('for (let i = 0; i < 60; i++) console.log("noise", i)', f.context)
  f.document.body.children.at(-1).onerror()
  await tick()
  f.timers[0].fn()
  const report = f.messages.at(-1)
  assert.equal(report.args.lifecycle, 'failed')
  assert.equal(report.args.entries.length, 50)
  assert.match(report.args.entries[0].msg, /Space failed to load:.*Script failed: entry module/s)
  assert.equal(report.args.dropped, 12)
})

test('throttled batches retain lifecycle and cumulative dropped counts until acknowledged', async () => {
  const f = loaderFixture()
  await tick()
  f.timers[0].fn()
  const first = f.messages.at(-1)
  reply(f, first, { stored: 0, throttled: true })
  await tick()
  f.timers[0].fn()
  const retry = f.messages.at(-1)
  assert.equal(retry.args.lifecycle, 'failed')
  assert.equal(retry.args.dropped, first.args.entries.length)
  assert.equal(retry.args.unconfirmed, 0)
  reply(f, retry, { stored: retry.args.entries.length })
  await tick()
  f.timers[0].fn()
  assert.equal(f.messages.length, 2)
})

test('failed sends report unconfirmed entries separately from known drops and bound in-flight batches', async () => {
  const f = loaderFixture()
  await tick()
  f.timers[0].fn()
  const first = f.messages.at(-1)
  vm.runInContext('for (let i = 0; i < 60; i++) console.log("noise", i)', f.context)
  f.timers[0].fn()
  assert.equal(f.messages.length, 1)
  f.port.onmessage({ data: { v: 1, id: first.id, ok: false, error: { code: 'blocked', message: 'Unavailable' } } })
  await tick()
  f.timers[0].fn()
  const retry = f.messages.at(-1)
  assert.equal(retry.args.lifecycle, 'failed')
  assert.equal(retry.args.unconfirmed, first.args.entries.length)
  assert.equal(retry.args.dropped, 11)
  assert.equal(retry.args.entries.length, 50)
})

test('a terminal not_granted reply stops log delivery instead of retrying every tick', async () => {
  const f = loaderFixture()
  await tick()
  f.timers[0].fn()
  assert.equal(f.messages.length, 1)
  const first = f.messages[0]
  assert.equal(first.op, 'log')
  f.port.onmessage({ data: { v: 1, id: first.id, ok: false, error: { code: 'not_granted', message: 'Approve logs in Permissions', capability: 'logs' } } })
  await tick()
  for (let i = 0; i < 5; i++) f.timers[0].fn()
  vm.runInContext('console.error("after denial")', f.context)
  for (let i = 0; i < 5; i++) f.timers[0].fn()
  assert.equal(f.messages.length, 1)
})

test('a transient log failure still retries', async () => {
  const f = loaderFixture()
  await tick()
  f.timers[0].fn()
  const first = f.messages[0]
  f.port.onmessage({ data: { v: 1, id: first.id, ok: false, error: { code: 'busy', message: 'Try again' } } })
  await tick()
  f.timers[0].fn()
  assert.equal(f.messages.length, 2)
  assert.equal(f.messages[1].op, 'log')
})
