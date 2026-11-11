import './env.mjs'
import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { worker, nested } from '../../../harness/fixtures/hosting/probes.mjs'

for (const shared of [false, true]) test(`hosting ${shared ? 'SharedWorker' : 'Worker'} fixture executes its generated fetch probe`, async t => {
  let source
  let revoked = false
  const calls = []
  t.mock.method(URL, 'createObjectURL', blob => { source = blob.text(); return 'blob:fixture' })
  t.mock.method(URL, 'revokeObjectURL', url => { assert.equal(url, 'blob:fixture'); revoked = true })
  class MockWorker {
    constructor() {
      this.port = { start() {}, close() {} }
      source.then(code => {
        const send = data => (shared ? this.port : this).onmessage({ data })
        const context = vm.createContext({ fetch: url => { calls.push(url); return Promise.reject(new TypeError('blocked')) }, postMessage: send })
        vm.runInContext(code, context)
        if (shared) context.onconnect({ ports: [{ postMessage: send }] })
      }).catch(error => this.onerror({ message: String(error) }))
    }
    terminate() {}
  }
  const key = shared ? 'SharedWorker' : 'Worker'
  const previous = Object.getOwnPropertyDescriptor(globalThis, key)
  Object.defineProperty(globalThis, key, { configurable: true, value: MockWorker })
  t.after(() => previous ? Object.defineProperty(globalThis, key, previous) : delete globalThis[key])
  const result = await worker({ http: 'http://127.0.0.1:12345' }, shared)
  assert.equal(result.outcome, 'blocked')
  assert.deepEqual(calls, [`http://127.0.0.1:12345/${shared ? 'shared-worker' : 'worker'}`])
  assert.equal(revoked, true)
})

test('fresh srcdoc fixture reports execution and all network attempts', async t => {
  const listeners = new Set()
  const fetches = []
  let frame
  const previous = new Map(['window', 'document'].map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]))
  t.after(() => {
    for (const [key, descriptor] of previous) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor)
      else delete globalThis[key]
    }
  })
  const node = () => ({ remove() {}, getBoundingClientRect() {} })
  const childDocument = { createElement: node, body: { append() {} }, head: { append() {} } }
  const child = {
    document: childDocument,
    navigator: { sendBeacon: () => false },
    fetch: url => { fetches.push(url); return Promise.reject(new TypeError('blocked')) },
    XMLHttpRequest: class { open() {} send() { this.onerror() } },
    EventSource: class { close() {} },
    WebSocket: class { close() {} },
    setTimeout: fn => queueMicrotask(fn),
    parent: { postMessage: data => { for (const callback of listeners) callback({ source: frame.contentWindow, data }) } }
  }
  Object.defineProperty(globalThis, 'window', { configurable: true, value: {
    addEventListener: (_, callback) => listeners.add(callback),
    removeEventListener: (_, callback) => listeners.delete(callback)
  } })
  Object.defineProperty(globalThis, 'document', { configurable: true, value: {
    addEventListener() {}, removeEventListener() {},
    createElement: () => frame = { contentWindow: {}, remove() {} },
    body: { append() {
      const script = frame.srcdoc.match(/<script>([\s\S]*)<\/script>/)[1]
      vm.runInNewContext(script, child)
    } }
  } })
  const result = await nested({ http: 'http://127.0.0.1:12345', ws: 'ws://127.0.0.1:12346' }, 'srcdoc')
  assert.equal(result.started, true)
  assert.equal(result.executed, true)
  assert.deepEqual(fetches, ['http://127.0.0.1:12345/srcdoc/fetch'])
  assert.deepEqual(Array.from(result.rows, row => row.name), ['fetch', 'xhr', 'beacon', 'eventsource', 'websocket', 'image', 'link', 'script', 'css-url', 'css-import', 'font'])
  assert.equal(listeners.size, 0)
})
