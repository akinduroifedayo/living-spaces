import './env.mjs'
import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { spaceLoader, projectResolver } from '../../../src/guest/loader.mjs'

// Synthetic bounded DOM/message-port fixtures following loader.test.mjs, never native evidence.
const tick = () => new Promise(resolve => setImmediate(resolve))
function loaderFixture() {
  const events = new Map()
  const messages = []
  const timers = []
  const parent = {}
  const element = tag => ({
    tag, attributes: [], style: {}, children: [],
    setAttribute(name, value) { this[name] = value },
    append(...nodes) { this.children.push(...nodes) },
    replaceChildren(...nodes) { this.children = nodes }
  })
  const document = {
    head: element('head'), body: element('body'), documentElement: element('html'),
    querySelector() { return null }, createElement: element,
    addEventListener: (name, callback) => events.set(name, callback)
  }
  const window = {
    parent, addEventListener: (name, callback) => events.set(name, callback),
    removeEventListener: name => events.delete(name)
  }
  const port = {
    postMessage: message => messages.push(structuredClone(message)),
    close() { this.closed = true }
  }
  const DOMParser = class {
    parseFromString() {
      return {
        title: '', documentElement: element('html'), head: { childNodes: [] },
        body: { attributes: [], childNodes: [] }, querySelectorAll: () => []
      }
    }
  }
  const context = vm.createContext({
    window, document, DOMParser, Map, Set, Error, TypeError, Promise, Object, JSON, String,
    Uint8Array, Blob, URL, atob,
    console: Object.fromEntries(['log', 'info', 'warn', 'error', 'debug', 'trace', 'dir', 'table', 'assert']
      .map(level => [level, () => {}])),
    setInterval(fn, ms) { timers.push({ fn, ms }); return timers.length },
    clearInterval() {}
  })
  vm.runInContext(`(${spaceLoader.toString()})((${projectResolver.toString()})())`, context)
  events.get('message')({
    source: parent,
    data: {
      type: 'space-boot', v: 1, grants: ['data'],
      bundle: {
        space: { id: 'q14-fixture', name: 'Q14 Fixture' }, rev: 1,
        manifest: { entry: 'index.html' },
        files: [{ path: 'index.html', mime: 'text/html', text: '<main>Q14 fixture</main>' }]
      }
    },
    ports: [port]
  })
  return { api: window.space, port, messages }
}

const cursor = {
  v: 1, space: 'q14-fixture', created_at: 10, seq: 12, offset: 2, query: 'a'.repeat(64)
}
const firstPage = {
  records: [{ id: 'a', data: { rank: 7 } }, { id: 'b', data: { rank: 7 } }],
  total: 3, seq: 12, has_more: true, next_cursor: cursor
}
const lastPage = {
  records: [{ id: 'c', data: { rank: 7 } }], total: 3, seq: 12,
  has_more: false, next_cursor: null
}
const reply = (fixture, request, result) => fixture.port.onmessage({
  data: { v: 1, id: request.id, ok: true, result }
})
const requirePage = fixture => assert.equal(typeof fixture.api.queryPage, 'function', 'new page capability absent')

test('Q14 legacy query still returns an array from exactly one request', async () => {
  const f = loaderFixture()
  const options = { where: { status: 'reading' }, order: 'rank', offset: 1, limit: 2 }
  const pending = f.api.query('papers', options)
  assert.deepEqual(f.messages, [{ v: 1, id: 1, op: 'data.query', args: { ...options, collection: 'papers' } }])
  const records = [{ id: 'b' }, { id: 'c' }]
  reply(f, f.messages[0], { records, total: 3, seq: 12 })
  assert.deepEqual(await pending, records)
  assert.equal(Array.isArray(await pending), true)
  await tick()
  assert.equal(f.messages.length, 1)
})

test('Q14 loader returns complete pages and continues only on explicit queryPage', async () => {
  const f = loaderFixture()
  requirePage(f)
  const options = { where: { status: 'reading' }, order: 'rank', limit: 2, offset: 0 }
  const original = structuredClone(options)
  const pending = f.api.queryPage('papers', options)
  assert.deepEqual(f.messages, [{
    v: 1, id: 1, op: 'data.query', args: { ...options, collection: 'papers', page: true }
  }])
  reply(f, f.messages[0], firstPage)
  assert.deepEqual(await pending, firstPage)
  assert.deepEqual(options, original)
  await tick()
  assert.equal(f.messages.length, 1, 'a nonterminal page must not prefetch or materialize the collection')

  const continuation = { where: { status: 'reading' }, order: 'rank', limit: 2, cursor }
  const next = f.api.queryPage('papers', continuation)
  assert.deepEqual(f.messages[1], {
    v: 1, id: 2, op: 'data.query', args: { ...continuation, collection: 'papers', page: true }
  })
  reply(f, f.messages[1], lastPage)
  assert.deepEqual(await next, lastPage)
  await tick()
  assert.equal(f.messages.length, 2, 'terminal pages must not issue an empty follow-up request')
})

test('Q14 loader forces page mode and retains an empty terminal envelope', async () => {
  const f = loaderFixture()
  requirePage(f)
  const pending = f.api.queryPage('papers', { page: false, limit: 2 })
  assert.deepEqual(f.messages[0], {
    v: 1, id: 1, op: 'data.query', args: { page: true, limit: 2, collection: 'papers' }
  })
  const empty = { records: [], total: 0, seq: 12, has_more: false, next_cursor: null }
  reply(f, f.messages[0], empty)
  assert.deepEqual(await pending, empty)
  await tick()
  assert.equal(f.messages.length, 1)
})

test('Q14 loader propagates typed expiry unchanged without a hidden restart', async () => {
  const f = loaderFixture()
  requirePage(f)
  const options = { where: { status: 'reading' }, order: 'rank', limit: 2, cursor }
  const pending = f.api.queryPage('papers', options)
  assert.deepEqual(f.messages[0], {
    v: 1, id: 1, op: 'data.query', args: { ...options, collection: 'papers', page: true }
  })
  const expiry = {
    code: 'cursor_expired', message: 'Collection changed during enumeration',
    restart_required: true, reason: 'changed'
  }
  const rejection = assert.rejects(pending, error => {
    assert.equal(error.name, 'SpaceError')
    for (const [key, value] of Object.entries(expiry)) assert.equal(error[key], value)
    assert.equal('records' in error, false)
    assert.equal('next_cursor' in error, false)
    return true
  })
  f.port.onmessage({ data: { v: 1, id: 1, ok: false, error: expiry } })
  await rejection
  await tick()
  assert.equal(f.messages.length, 1)
})

test('Q14 loader closes a pending page before a late reply and refuses future queries', async () => {
  const f = loaderFixture()
  requirePage(f)
  const pending = f.api.queryPage('papers', { order: 'rank', limit: 2 })
  assert.deepEqual(f.messages[0], {
    v: 1, id: 1, op: 'data.query', args: { order: 'rank', limit: 2, collection: 'papers', page: true }
  })
  const settlements = []
  const observed = pending.then(
    value => settlements.push({ resolved: value }),
    error => { assert.equal(error.name, 'SpaceError'); settlements.push({ rejected: error.code }) }
  )
  f.port.onmessage({ data: {
    v: 1, type: 'event', event: 'session.closed', payload: { reason: 'synthetic fixture close' }
  } })
  await observed
  assert.deepEqual(settlements, [{ rejected: 'session_invalid' }])
  assert.equal(f.port.closed, true)
  reply(f, f.messages[0], firstPage)
  await tick()
  assert.deepEqual(settlements, [{ rejected: 'session_invalid' }])
  await assert.rejects(f.api.queryPage('papers', { order: 'rank', limit: 2, cursor }),
    error => error.name === 'SpaceError' && error.code === 'session_invalid')
  assert.equal(f.messages.length, 1, 'late replies and closed calls must not dispatch another query')
})
