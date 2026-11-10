import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { mountSpace } from '../../../src/desktop/sandbox/index.js'

function environment() {
  const original = { document: globalThis.document, window: globalThis.window, MessageChannel: globalThis.MessageChannel }
  const frames = [], ports = [], listeners = new Set()
  globalThis.MessageChannel = class {
    constructor() {
      for (const key of ['port1', 'port2']) {
        this[key] = { close() { this.closed = true }, postMessage() {} }
        ports.push(this[key])
      }
    }
  }
  globalThis.window = {
    addEventListener: (_name, fn) => listeners.add(fn),
    removeEventListener: (_name, fn) => listeners.delete(fn)
  }
  globalThis.document = { createElement() {
    const frame = new EventTarget()
    Object.assign(frame, { style: {}, setAttribute() {}, remove() { this.removed = true },
      contentWindow: { postMessage(message, _origin, transferred) { frame.boot = message; frame.transferred = transferred } } })
    frames.push(frame)
    return frame
  } }
  return { frames, ports, listeners, restore() { Object.assign(globalThis, original) } }
}

const project = () => ({ space: { id: 'wire-demo', name: 'Wire demo' }, rev: 1, manifest: {}, files: [] })
const valid = () => ({ format: 1, shell_srcdoc: readFileSync('src/living-spaces/guest/space-host.html', 'utf8') })
const invalid = [
  ['missing', undefined], ['null', null], ['array', []], ['string', 'document'], ['number', 1], ['boolean', true],
  ['missing format', { shell_srcdoc: 'document' }], ['missing document', { format: 1 }],
  ['renamed format', { version: 1, shell_srcdoc: 'document' }],
  ['document path', { format: 1, path: 'guest/space-host.html' }],
  ['extra field', { format: 1, shell_srcdoc: 'document', policy: 'override' }],
  ['string format', { format: '1', shell_srcdoc: 'document' }],
  ['null format', { format: null, shell_srcdoc: 'document' }],
  ['boolean format', { format: true, shell_srcdoc: 'document' }],
  ['fractional format', { format: 1.1, shell_srcdoc: 'document' }],
  ['unsupported format', { format: 2, shell_srcdoc: 'document' }],
  ['null document', { format: 1, shell_srcdoc: null }],
  ['object document', { format: 1, shell_srcdoc: {} }],
  ['array document', { format: 1, shell_srcdoc: [] }],
  ['number document', { format: 1, shell_srcdoc: 1 }],
  ['boolean document', { format: 1, shell_srcdoc: true }],
  ['empty document', { format: 1, shell_srcdoc: '' }],
  ['blank document', { format: 1, shell_srcdoc: ' \n\t' }]
]
for (const [name, sandbox] of invalid) test(`sandbox wire rejects ${name} before acquiring resources`, () => {
  const env = environment()
  let mounted
  try {
    assert.throws(() => { mounted = mountSpace({ append() {} }, { bundle: { ...project(), sandbox }, call() {} }) }, /reinstall/i)
    assert.equal(env.frames.length, 0)
    assert.equal(env.ports.length, 0)
    assert.equal(env.listeners.size, 0)
  } finally { mounted?.destroy(); env.restore() }
})

test('sandbox wire boots only project fields and grants through one port', () => {
  const env = environment()
  let mounted
  try {
    const bundle = { ...project(), sandbox: valid(), session: 'injected-session', marker: 'request-marker' }
    mounted = mountSpace({ append() {} }, { bundle, session: 'host-session', grants: ['data'], call() {} })
    const frame = env.frames[0]
    frame.dispatchEvent(new Event('load'))
    assert.equal(frame.srcdoc, bundle.sandbox.shell_srcdoc)
    assert.deepEqual(frame.boot, { type: 'space-boot', v: 1, bundle: project(), grants: ['data'] })
    assert.deepEqual(frame.transferred, [env.ports[1]])
    frame.dispatchEvent(new Event('load'))
    assert.equal(env.listeners.size, 0)
    assert.ok(env.ports.every(port => port.closed))
  } finally { mounted?.destroy(); env.restore() }
})

test('sandbox setup failure releases its frame, both ports and shell listener', () => {
  const env = environment()
  try {
    assert.throws(() => mountSpace({ append() { throw new Error('append failed') } }, {
      bundle: { ...project(), sandbox: valid() }, call() {}
    }), /append failed/)
    assert.equal(env.frames[0].removed, true)
    assert.ok(env.ports.every(port => port.closed))
    assert.equal(env.listeners.size, 0)
  } finally { env.restore() }
})

test('frame creation failure closes both acquired ports without installing a listener', () => {
  const env = environment()
  try {
    document.createElement = () => { throw new Error('frame creation failed') }
    assert.throws(() => mountSpace({ append() {} }, { bundle: { ...project(), sandbox: valid() }, call() {} }), /frame creation failed/)
    assert.ok(env.ports.every(port => port.closed))
    assert.equal(env.listeners.size, 0)
  } finally { env.restore() }
})

test('document assignment failure releases listeners, frame and both acquired ports', () => {
  const env = environment()
  try {
    const create = document.createElement
    document.createElement = () => {
      const frame = create()
      Object.defineProperty(frame, 'srcdoc', { set() { throw new Error('document assignment failed') } })
      return frame
    }
    assert.throws(() => mountSpace({ append() {} }, { bundle: { ...project(), sandbox: valid() }, call() {} }), /document assignment failed/)
    assert.equal(env.frames[0].removed, true)
    assert.ok(env.ports.every(port => port.closed))
    assert.equal(env.listeners.size, 0)
  } finally { env.restore() }
})
