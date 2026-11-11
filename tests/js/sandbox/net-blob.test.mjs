import './env.mjs'
import test from 'node:test'
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { homedir } from 'node:os'
import { join } from 'node:path'
import { spaceSrcdoc } from '../../../src/guest/document.mjs'

const require = createRequire(join(homedir(), '.hermes/hermes-agent/apps/desktop/node_modules/react/package.json'))
const { JSDOM } = require('jsdom')
const url = 'https://example.com/image.png'
const byteReply = (fields = {}) => ({ status: 200, url, headers: {}, b64: 'AAH/gA==', mime: 'image/png', ...fields })

async function boot(t) {
  const dom = new JSDOM(spaceSrcdoc(), { runScripts: 'outside-only' })
  const { window } = dom
  const messages = [], blobs = [], created = [], revoked = []
  window.Blob = class extends Blob {
    constructor(...args) { super(...args); blobs.push(this) }
  }
  window.URL = class extends URL {
    static createObjectURL(blob) { created.push(blob); return `blob:fixture/${created.length}` }
    static revokeObjectURL(value) { revoked.push(value) }
  }
  t.after(() => dom.window.close())
  window.eval(window.document.querySelector('script').textContent)
  const port = { postMessage: message => messages.push(structuredClone(message)), close() { this.closed = true } }
  const bundle = {
    space: { id: 'net-blob', name: 'Net Blob' }, rev: 1, manifest: {},
    files: [{ path: 'index.html', mime: 'text/html', text: '<html><head></head><body></body></html>' }]
  }
  window.dispatchEvent(new window.MessageEvent('message', {
    source: window.parent, data: { type: 'space-boot', v: 1, bundle, grants: ['net'] }, ports: [port]
  }))
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(window.document.querySelector('[role=alert]'), null, window.document.body.textContent)
  const bootURLs = created.length
  blobs.length = 0
  t.after(() => {
    assert.equal(created.length, bootURLs, 'network calls must not allocate object URLs')
    assert.deepEqual(revoked, [], 'network calls must not manage caller URLs')
  })
  return { window, api: window.space, messages, blobs, port }
}

const reply = (f, result) => f.port.onmessage({ data: { v: 1, id: f.messages.at(-1).id, ok: true, result } })
const refuse = (f, error) => f.port.onmessage({ data: { v: 1, id: f.messages.at(-1).id, ok: false, error } })
const close = f => f.port.onmessage({ data: { v: 1, type: 'event', event: 'session.closed', payload: { reason: 'Closed by host' } } })

test('net.blob sends only existing net.fetch options, forces bytes, and preserves decoded bytes and MIME', async t => {
  const f = await boot(t)
  const options = Object.freeze({ method: 'POST', headers: { Authorization: 'Bearer space-supplied', 'Content-Type': 'text/plain' }, body: 'image query', as: 'json', ignored: true })
  const pending = f.api.net.blob(url, options)
  assert.deepEqual(f.messages, [{ v: 1, id: 1, op: 'net.fetch', args: {
    url, method: 'POST', headers: options.headers, body: 'image query', as: 'bytes'
  } }])
  reply(f, byteReply())
  const blob = await pending
  assert.ok(blob instanceof Blob)
  assert.equal(blob.type, 'image/png')
  assert.equal(blob.size, 4)
  assert.deepEqual([...new Uint8Array(await blob.arrayBuffer())], [0, 1, 255, 128])
  assert.equal(f.blobs.length, 1)
  assert.equal(options.as, 'json')
})

test('net.blob forwards defined falsy options for backend validation and omits undefined fields', async t => {
  const f = await boot(t)
  for (const [options, args] of [
    [undefined, { url, as: 'bytes' }],
    [{ method: undefined, headers: undefined, body: '', as: null }, { url, body: '', as: 'bytes' }],
    [{ method: '', headers: null, body: false }, { url, method: '', headers: null, body: false, as: 'bytes' }],
    [{ method: 42, headers: [], body: 0 }, { url, method: 42, headers: [], body: 0, as: 'bytes' }]
  ]) {
    const pending = f.api.net.blob(url, options)
    assert.deepEqual(f.messages.at(-1), { v: 1, id: f.messages.length, op: 'net.fetch', args })
    refuse(f, { code: 'invalid', message: 'Backend option validation', reason: 'request_options' })
    await assert.rejects(pending, { name: 'SpaceError', code: 'invalid', message: 'Backend option validation', reason: 'request_options' })
  }
  assert.equal(f.blobs.length, 0)
})

test('net.blob permits mount and timer retrieval without user activation and accepts empty and non-image bodies', async t => {
  const f = await boot(t)
  for (const mime of ['application/octet-stream', 'text/plain', '']) {
    const pending = f.api.net.blob(url)
    assert.deepEqual(f.messages.at(-1).args, { url, as: 'bytes' })
    reply(f, byteReply({ status: 204, b64: '', mime }))
    const blob = await pending
    assert.equal(blob.size, 0)
    assert.equal(blob.type, mime)
  }
  const pending = await new Promise(resolve => f.window.setTimeout(() => resolve({ result: f.api.net.blob(url) }), 0))
  assert.deepEqual(f.messages.at(-1), { v: 1, id: 4, op: 'net.fetch', args: { url, as: 'bytes' } })
  reply(f, byteReply({ status: 299 }))
  assert.equal((await pending.result).type, 'image/png')
})

test('net.fetch still returns raw text, json, bytes and HTTP failure replies unchanged', async t => {
  const f = await boot(t)
  for (const [options, args, response] of [
    [undefined, { url }, { status: 200, url, headers: {}, text: 'hello' }],
    [{ as: 'json' }, { url, as: 'json' }, { status: 200, url, headers: {}, json: { hello: true } }],
    [{ as: 'bytes' }, { url, as: 'bytes' }, byteReply()],
    [{ as: 'text' }, { url, as: 'text' }, { status: 404, url, headers: {}, text: 'missing' }]
  ]) {
    const pending = f.api.net.fetch(url, options)
    assert.deepEqual(f.messages.at(-1), { v: 1, id: f.messages.length, op: 'net.fetch', args })
    reply(f, response)
    assert.strictEqual(await pending, response)
  }
  assert.equal(f.blobs.length, 0)
})

test('net.blob rejects non-2xx HTTP status with response details before decoding or allocating a Blob', async t => {
  const f = await boot(t)
  for (const status of [199, 300, 404, 500]) {
    const pending = f.api.net.blob(url)
    const response = { status, url: 'https://example.com/final.png', headers: { 'content-type': 'text/plain' } }
    reply(f, response)
    await assert.rejects(pending, { name: 'SpaceError', code: 'http_status', status, url: response.url, headers: response.headers })
  }
  assert.equal(f.blobs.length, 0)
})

test('net.blob preserves typed bridge failures and all their details', async t => {
  const f = await boot(t)
  for (const code of ['not_granted', 'session_invalid', 'blocked', 'invalid', 'limit']) {
    const error = { code, message: 'Host refusal', reason: 'host_detail', limit: 123, actual: 456, detail: { scope: 'net' } }
    const pending = f.api.net.blob(url)
    refuse(f, error)
    await assert.rejects(pending, { name: 'SpaceError', ...error })
  }
  assert.equal(f.blobs.length, 0)
})

test('net.blob rejects malformed reply fields and base64 before constructing a Blob', async t => {
  const f = await boot(t)
  const malformed = [null, undefined, {}, [],
    ...['status', 'url', 'headers', 'b64', 'mime'].map(field => {
      const response = byteReply()
      delete response[field]
      return response
    }),
    ...[{ status: '200' }, { status: NaN }, { status: 200.5 }, { url: null },
      { headers: null }, { headers: [] }, { headers: 'invalid' }, { headers: { x: 1 } },
      { b64: null }, { b64: 123 }, { mime: null }, { mime: {} }].map(byteReply),
    ...['!!!!', 'A', 'AA', 'A===', 'AA=A', '====', 'AA==AAAA', 'AA==\n', '💥=='].map(b64 => byteReply({ b64 }))
  ]
  for (const response of malformed) {
    const pending = f.api.net.blob(url)
    reply(f, response)
    await assert.rejects(pending, { name: 'SpaceError', code: 'invalid' })
  }
  assert.equal(f.blobs.length, 0)
})

test('session closure rejects pending and future net.blob calls without delivering a Blob', async t => {
  const f = await boot(t)
  const pending = f.api.net.blob(url)
  close(f)
  reply(f, byteReply())
  await assert.rejects(pending, { name: 'SpaceError', code: 'session_invalid', message: 'Closed by host' })
  await assert.rejects(f.api.net.blob(url), { name: 'SpaceError', code: 'session_invalid' })
  assert.equal(f.port.closed, true)
  assert.equal(f.messages.length, 1)
  assert.equal(f.blobs.length, 0)
})

test('session closure after bridge resolution but before Blob conversion rejects completion', async t => {
  const f = await boot(t)
  const pending = f.api.net.blob(url)
  reply(f, byteReply())
  close(f)
  await assert.rejects(pending, { name: 'SpaceError', code: 'session_invalid' })
  assert.equal(f.blobs.length, 0)
})
