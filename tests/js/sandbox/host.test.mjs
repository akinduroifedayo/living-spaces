import './env.mjs'
import test from 'node:test'
import assert from 'node:assert/strict'
import { setTimeout as delay } from 'node:timers/promises'
import { BRIDGE_VERSION, WEBRTC_NOTE, validateRequest, checkGrant, OP_GRANT, MAX_REQUEST_SIZE, mountSpace } from '../../../src/desktop/sandbox/index.js'
import { projectResolver } from '../../../src/guest/loader.mjs'
import { SPACE_CSP, SHELL_CSP, spaceSrcdoc, shellSrcdoc } from '../../../src/guest/document.mjs'
import { readFileSync } from 'node:fs'

const sandbox = { format: 1, shell_srcdoc: readFileSync('src/living-spaces/guest/space-host.html', 'utf8') }

const request = (extra = {}) => ({ v: 1, id: 7, op: 'data.query', args: { collection: 'papers' }, ...extra })
for (const [name, message] of [
  ['null', null], ['array', []], ['version', request({ v: 2 })], ['fractional id', request({ id: 1.1 })],
  ['missing id', request({ id: undefined })], ['op', request({ op: 3 })], ['null args', request({ args: null })],
  ['array args', request({ args: [] })], ['string args', request({ args: '' })]
]) test(`validator drops ${name}`, () => assert.equal(typeof validateRequest(message), 'string'))
test('validator accepts the v1 envelope, measures JSON length and catches serialization errors', () => {
  assert.equal(validateRequest(request()), null)
  const circular = {}; circular.self = circular
  assert.match(validateRequest(request({ args: circular })), /serializable/)
  assert.match(validateRequest(request({ args: { value: 1n } })), /serializable/)
  const base = JSON.stringify(request({ args: { text: '' } })).length
  assert.equal(validateRequest(request({ args: { text: 'a'.repeat(MAX_REQUEST_SIZE - base) } })), null)
  assert.match(validateRequest(request({ args: { text: 'a'.repeat(MAX_REQUEST_SIZE - base + 1) } })), /1 MB/)
})
test('grant map exactly covers the frozen v1 operations', () => {
  assert.deepEqual(OP_GRANT, { meta: null, 'data.query': 'data', 'data.get': 'data', 'data.put': 'data', 'data.delete': 'data', 'data.batch': 'data', refresh: 'refresh', 'runs.list': null, log: 'logs' })
  for (const op of Object.keys(OP_GRANT)) {
    assert.equal(checkGrant(op, ['data', 'logs', 'refresh']), null)
    if (OP_GRANT[op] === null) assert.equal(checkGrant(op, []), null)
    else assert.equal(checkGrant(op, []).code, 'not_granted')
  }
  for (const op of ['tool:terminal', 'data.set', '__proto__', 'constructor', 'agent.ask']) assert.equal(checkGrant(op, ['data']).code, 'not_granted')
  assert.equal(checkGrant('refresh', [{ capability: 'refresh', status: 'requested' }]).code, 'not_granted')
  assert.equal(checkGrant('refresh', [{ capability: 'refresh', status: 'granted' }]), null)
})
test('both frames carry identical frozen CSP and the exact disclosure', () => {
  const expected = readFileSync('docs/contracts/CONTRACTS.md', 'utf8').match(/CSP: `([^`]+)`/)[1]
  assert.equal(SPACE_CSP, expected)
  assert.equal(SHELL_CSP, SPACE_CSP)
  for (const source of [spaceSrcdoc(), shellSrcdoc()]) assert.ok(source.includes(`content="${SPACE_CSP}"`))
  assert.equal(BRIDGE_VERSION, 1)
  assert.ok(readFileSync('docs/spec/SPEC.md', 'utf8').includes(WEBRTC_NOTE))
})
test('project resolver handles query strings, fragments, static and computed dynamic imports', () => {
  const r = projectResolver()
  assert.deepEqual(r.resolve('views/main.js', '../images/logo.svg?v=2#mark'), { path: 'images/logo.svg', hash: '#mark' })
  assert.equal(r.moduleRef('views/main.js', './detail.js?v=2#x'), 'https://space.invalid/views/detail.js')
  assert.equal(r.moduleRef('main.js', 'preact'), 'preact')
  const code = r.rewriteImports('views/main.js', `import { h } from 'preact'; export { x } from '../x.js?v=1'; import './side.js#x'; const x = import('./detail.js'); const y = import('./' + name + '.js'); const text = "import('./unchanged.js')"; // import('./comment.js')`)
  assert.ok(code.includes("from 'preact'"))
  assert.ok(code.includes('"https://space.invalid/x.js"'))
  assert.ok(code.includes('"https://space.invalid/views/side.js"'))
  assert.equal(code.match(/__spaceImport/g).length, 2)
  assert.ok(code.includes('"import(\'./unchanged.js\')"'))
  assert.equal(r.resolve('index.html', 'https://elsewhere.invalid/a'), null)
})

function fixture(call = async () => ({ ok: true, result: { records: [] } }), grants = ['data', 'logs']) {
  const originalDocument = globalThis.document
  const originalWindow = globalThis.window
  const target = new EventTarget()
  const frames = []
  globalThis.window = target
  globalThis.document = {
    createElement() {
      const frame = new EventTarget()
      frame.style = {}
      frame.attributes = {}
      frame.setAttribute = (k, v) => { frame.attributes[k] = v }
      frame.remove = () => { frame.removed = true }
      frame.contentWindow = { postMessage(message, origin, ports) { frame.boot = structuredClone(message); frame.peer = structuredClone(ports[0], { transfer: [ports[0]] }) } }
      frames.push(frame)
      return frame
    }
  }
  const events = []
  const calls = []
  const mount = mountSpace({ append() {} }, {
    bundle: { space: { id: 'demo', name: 'Demo' }, rev: 1, manifest: {}, files: [], sandbox }, grants,
    call: async (op, args) => { calls.push([op, args]); return call(op, args) }, onEvent: e => events.push(e)
  })
  const frame = frames[0]
  frame.dispatchEvent(new Event('load'))
  const replies = []
  frame.peer.onmessage = e => replies.push(e.data)
  return {
    frame, mount, events, calls, replies,
    cleanup() { mount.destroy(); frame.peer.close(); globalThis.document = originalDocument; globalThis.window = originalWindow }
  }
}
test('mount binds boot to host session, forwards replies and emits versioned events', async () => {
  const f = fixture()
  try {
    assert.equal(f.frame.attributes.sandbox, 'allow-scripts')
    assert.equal(Object.hasOwn(f.frame.boot, 'session'), false)
    assert.equal(Object.hasOwn(f.frame.boot.bundle, 'sandbox'), false)
    assert.equal(f.frame.boot.v, 1)
    f.frame.peer.postMessage(request())
    await delay(20)
    assert.equal(f.calls.length, 1)
    assert.deepEqual(f.replies[0], { v: 1, id: 7, ok: true, result: { records: [] } })
    f.mount.postEvent('data.changed', { seq: 2, changes: [] })
    await delay(20)
    assert.deepEqual(f.replies[1], { v: 1, type: 'event', event: 'data.changed', payload: { seq: 2, changes: [] } })
  } finally { f.cleanup() }
})
test('invalid envelopes and ungranted ops never reach call', async () => {
  const f = fixture()
  try {
    f.frame.peer.postMessage(request({ v: 99 }))
    f.frame.peer.postMessage(request({ op: 'refresh' }))
    await delay(20)
    assert.equal(f.calls.length, 0)
    assert.equal(f.events.filter(e => e.kind === 'denied').length, 2)
    assert.equal(f.replies[0].error.code, 'not_granted')
  } finally { f.cleanup() }
})
test('reload closes the port, stops late calls and suppresses in-flight results', async () => {
  let complete
  const f = fixture(() => new Promise(resolve => { complete = resolve }))
  try {
    f.frame.peer.postMessage(request())
    await delay(20)
    f.frame.dispatchEvent(new Event('load'))
    complete({ ok: true, result: 'late' })
    f.frame.peer.postMessage(request({ id: 8 }))
    f.mount.postEvent('run.updated', { status: 'succeeded' })
    await delay(20)
    assert.equal(f.calls.length, 1)
    assert.equal(f.replies.length, 0)
    assert.equal(f.events.filter(e => e.kind === 'reloaded').length, 1)
  } finally { f.cleanup() }
})
test('shell reload signals only from this frame and session.closed stops forwarding', async () => {
  const f = fixture()
  try {
    window.dispatchEvent(new MessageEvent('message', { data: { v: 1, type: 'space-reloaded' } }))
    assert.equal(f.events.filter(e => e.kind === 'reloaded').length, 0)
    f.mount.postEvent('session.closed', { reason: 'revoked' })
    f.frame.peer.postMessage(request())
    await delay(20)
    assert.equal(f.calls.length, 0)
    assert.deepEqual(f.replies[0], { v: 1, type: 'event', event: 'session.closed', payload: { reason: 'revoked' } })
  } finally { f.cleanup() }
})
test('host limits log batches and reports flooding once', async () => {
  const f = fixture()
  try {
    for (let id = 1; id <= 3; id++) f.frame.peer.postMessage(request({ id, op: 'log', args: { entries: [{ level: 'warn', msg: 'Space log overflow: dropped 4 entries' }] } }))
    f.frame.peer.postMessage(request({ id: 4, op: 'log', args: { entries: Array(51).fill({ level: 'log', msg: 'demo' }) } }))
    await delay(20)
    assert.equal(f.calls.length, 1)
    assert.deepEqual(f.calls[0][1], { entries: [{ level: 'warn', msg: 'Space log overflow: dropped 4 entries' }] })
    assert.equal(f.events.filter(e => e.kind === 'log-overflow').length, 1)
    assert.equal(f.events.filter(e => e.kind === 'denied').length, 1)
  } finally { f.cleanup() }
})

test('revoking a host grant withholds an in-flight successful result', async () => {
  let complete
  const grants = [{ capability: 'data', status: 'granted' }]
  const f = fixture(() => new Promise(resolve => { complete = resolve }), grants)
  try {
    f.frame.peer.postMessage(request())
    await delay(20)
    grants[0].status = 'revoked'
    complete({ ok: true, result: 'must not be delivered' })
    await delay(20)
    assert.equal(f.replies[0].ok, false)
    assert.equal(f.replies[0].error.code, 'not_granted')
    assert.equal(f.events.at(-1).kind, 'denied')
  } finally { f.cleanup() }
})
test('import rewriting leaves comments, strings, regexes and bare dynamic imports intact', () => {
  const resolver = projectResolver()
  const source = "const a = /import('data')/; const b = () => /import('data')/; const c = \"import('text')\"; const n = 4 / 2; import('preact');"
  const rewritten = resolver.rewriteImports('views/main.js', source)
  assert.ok(rewritten.includes("/import('data')/"))
  assert.equal(rewritten.match(/__spaceImport/g).length, 1)
  assert.ok(rewritten.includes("4 / 2"))
  assert.equal(resolver.moduleRef('main.js', 'preact'), 'preact')
  const template = resolver.rewriteImports('main.js', '`result: ${await import("./view.mjs")} imported`')
  assert.equal(template.match(/__spaceImport/g).length, 1)
})

test('the shell can report an inner reload but other senders cannot close the port', async () => {
  const f = fixture()
  try {
    const signal = new Event('message')
    Object.assign(signal, { source: f.frame.contentWindow, data: { v: 1, type: 'space-reloaded' } })
    window.dispatchEvent(signal)
    f.frame.peer.postMessage(request())
    await delay(20)
    assert.equal(f.calls.length, 0)
    assert.equal(f.events.filter(e => e.kind === 'reloaded').length, 1)
  } finally { f.cleanup() }
})
