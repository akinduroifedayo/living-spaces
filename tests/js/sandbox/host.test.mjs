import './env.mjs'
import test from 'node:test'
import assert from 'node:assert/strict'
import { setTimeout as delay } from 'node:timers/promises'
import { BRIDGE_VERSION, WEBRTC_NOTE, validateRequest, checkGrant, OP_GRANT, MAX_REQUEST_SIZE, mountSpace } from '../../../src/desktop/sandbox/index.js'
import { projectResolver, spaceLoader } from '../../../src/guest/loader.mjs'
import vm from 'node:vm'
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
  assert.deepEqual(OP_GRANT, { meta: null, 'data.query': 'data', 'data.get': 'data', 'data.put': 'data', 'data.delete': 'data', 'data.batch': 'data', refresh: null, 'runs.list': null, 'bot.request': null, log: 'logs', 'net.fetch': 'net' })
  for (const op of Object.keys(OP_GRANT)) {
    assert.equal(checkGrant(op, ['data', 'logs', 'refresh', 'net']), null)
    if (OP_GRANT[op] === null) assert.equal(checkGrant(op, []), null)
    else assert.equal(checkGrant(op, []).code, 'not_granted')
  }
  for (const op of ['tool:terminal', 'data.set', '__proto__', 'constructor', 'agent.ask']) assert.equal(checkGrant(op, ['data']).code, 'not_granted')
  assert.equal(checkGrant('refresh', []), null, 'refresh is no longer a capability; the host decides')
})
test('both frames carry identical frozen CSP and the exact disclosure', () => {
  const expected = readFileSync('docs/contracts/CONTRACTS.md', 'utf8').match(/CSP: `([^`]+)`/)[1]
  assert.equal(SPACE_CSP, expected)
  assert.equal(SHELL_CSP, SPACE_CSP)
  for (const source of [spaceSrcdoc(), shellSrcdoc()]) assert.ok(source.includes(`content="${SPACE_CSP}"`))
  assert.equal(BRIDGE_VERSION, 1)
  assert.ok(readFileSync('docs/spec/history/SPEC-v5.1.md', 'utf8').includes(WEBRTC_NOTE))
  assert.match(readFileSync('docs/spec/SPEC.md', 'utf8'), /WebRTC remains a disclosed exception: Off is not a promise of zero outbound data/)
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
async function until(check, ms = 2000) {
  const end = Date.now() + ms
  while (!check() && Date.now() < end) await delay(5)
}
test('mount binds boot to host session, forwards replies and emits versioned events', async () => {
  const f = fixture()
  try {
    assert.equal(f.frame.attributes.sandbox, 'allow-scripts')
    assert.equal(Object.hasOwn(f.frame.boot, 'session'), false)
    assert.equal(Object.hasOwn(f.frame.boot.bundle, 'sandbox'), false)
    assert.equal(f.frame.boot.v, 1)
    f.frame.peer.postMessage(request())
    await until(() => f.replies.length >= 1)
    assert.equal(f.calls.length, 1)
    assert.deepEqual(f.replies[0], { v: 1, id: 7, ok: true, result: { records: [] } })
    f.mount.postEvent('data.changed', { seq: 2, changes: [] })
    await until(() => f.replies.length >= 2)
    assert.deepEqual(f.replies[1], { v: 1, type: 'event', event: 'data.changed', payload: { seq: 2, changes: [] } })
  } finally { f.cleanup() }
})
test('invalid envelopes and ungranted ops never reach call', async () => {
  const f = fixture()
  try {
    f.frame.peer.postMessage(request({ v: 99 }))
    f.frame.peer.postMessage(request({ op: 'net.fetch' }))
    await delay(20)
    assert.equal(f.calls.length, 0)
    assert.equal(f.events.filter(e => e.kind === 'denied').length, 2)
    assert.deepEqual(f.replies.map(r => r.error.code), ['invalid', 'not_granted'])
  } finally { f.cleanup() }
})
test('oversized or malformed requests with a usable id settle with an error instead of hanging', async () => {
  const f = fixture()
  try {
    f.frame.peer.postMessage(request({ id: 11, args: { text: 'a'.repeat(MAX_REQUEST_SIZE) } }))
    f.frame.peer.postMessage(request({ id: 12, args: [] }))
    f.frame.peer.postMessage(request({ id: 'x', args: { text: 'a'.repeat(MAX_REQUEST_SIZE) } }))
    await delay(20)
    assert.equal(f.calls.length, 0)
    assert.deepEqual(f.replies.map(r => [r.id, r.ok, r.error.code]), [[11, false, 'limit'], [12, false, 'invalid']])
    assert.equal(f.events.filter(e => e.kind === 'denied').length, 3)
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

test('validator measures the complete UTF-8 envelope at the byte boundary', () => {
  const base = request({ op: 'data.put', args: { text: '' } })
  const overhead = Buffer.byteLength(JSON.stringify(base), 'utf8')
  const text = 'é'.repeat(Math.floor((MAX_REQUEST_SIZE - overhead) / 2)) + 'a'.repeat((MAX_REQUEST_SIZE - overhead) % 2)
  const exact = { ...base, args: { text } }
  assert.equal(Buffer.byteLength(JSON.stringify(exact), 'utf8'), MAX_REQUEST_SIZE)
  assert.equal(validateRequest(exact), null)
  assert.match(validateRequest({ ...base, args: { text: text + 'a' } }), /1 MB/)
  assert.match(validateRequest({ ...base, args: { text: '😀'.repeat(MAX_REQUEST_SIZE / 4) } }), /1 MB/)
})

test('oversized writes reply with exact UTF-8 envelope bytes and notify the host without dispatch', async () => {
  const f = fixture()
  try {
    const messages = ['data.put', 'data.delete', 'data.batch'].map((op, i) => request({
      id: i + 20, op, args: { text: ['a', 'é', '😀'][i].repeat(MAX_REQUEST_SIZE / (i + 1)) }
    }))
    for (const message of messages) f.frame.peer.postMessage(message)
    await delay(40)
    assert.equal(f.calls.length, 0)
    assert.equal(f.replies.length, messages.length)
    for (const message of messages) {
      const reply = f.replies.find(r => r.id === message.id)
      assert.equal(reply.ok, false)
      assert.equal(reply.error.code, 'limit')
      assert.equal(reply.error.limit, MAX_REQUEST_SIZE)
      assert.equal(reply.error.actual, Buffer.byteLength(JSON.stringify(message), 'utf8'))
      assert.deepEqual(f.events.find(e => e.kind === 'write-rejected' && e.op === message.op), {
        kind: 'write-rejected', op: message.op, error: reply.error
      })
    }
    assert.equal(f.events.filter(e => e.kind === 'denied').length, messages.length)
  } finally { f.cleanup() }
})

test('all malformed envelopes with usable ids settle invalid and never dispatch', async () => {
  const circular = {}; circular.self = circular
  const malformed = [
    { v: 99 }, { v: undefined }, { op: 3 }, { args: null }, { args: [] }, { args: '' },
    { args: circular }, { args: { value: 1n } }
  ]
  const f = fixture()
  try {
    for (const [index, extra] of malformed.entries()) f.frame.peer.postMessage(request({ id: index + 30, ...extra }))
    f.frame.peer.postMessage(request({ id: 'unusable', args: null }))
    await delay(30)
    assert.equal(f.calls.length, 0)
    assert.deepEqual(f.replies.map(r => [r.id, r.ok, r.error.code]), malformed.map((_, index) => [index + 30, false, 'invalid']))
    assert.equal(f.events.filter(e => e.kind === 'denied').length, malformed.length + 1)
    assert.equal(f.events.filter(e => e.kind === 'write-rejected').length, 0)
  } finally { f.cleanup() }
})

test('malformed local writes report full typed rejection errors even without a usable id', async () => {
  const f = fixture()
  try {
    const messages = [
      request({ id: 40, op: 'data.put', args: null }),
      request({ id: 41, op: 'data.delete', v: 99 }),
      request({ id: 'unusable', op: 'data.batch', args: [] })
    ]
    for (const message of messages) f.frame.peer.postMessage(message)
    await delay(30)
    assert.equal(f.calls.length, 0)
    const rejected = f.events.filter(e => e.kind === 'write-rejected')
    assert.deepEqual(rejected.map(e => [e.op, e.error.code]), messages.map(m => [m.op, 'invalid']))
    assert.deepEqual(f.replies.map(r => r.id), [40, 41])
    for (const [index, reply] of f.replies.entries()) assert.deepEqual(rejected[index].error, reply.error)
    assert.equal(typeof rejected[2].error.message, 'string')
  } finally { f.cleanup() }
})

test('ungranted writes notify the host with the complete permission error without dispatch', async () => {
  const f = fixture(undefined, [])
  try {
    const ops = ['data.put', 'data.delete', 'data.batch']
    for (const [id, op] of ops.entries()) f.frame.peer.postMessage(request({ id, op }))
    await delay(30)
    assert.equal(f.calls.length, 0)
    assert.equal(f.replies.length, ops.length)
    const rejected = f.events.filter(e => e.kind === 'write-rejected')
    assert.equal(rejected.length, ops.length)
    for (const [index, op] of ops.entries()) {
      assert.deepEqual(rejected[index], { kind: 'write-rejected', op, error: f.replies[index].error })
      assert.equal(rejected[index].error.code, 'not_granted')
      assert.equal(rejected[index].error.capability, 'data')
    }
  } finally { f.cleanup() }
})

test('allowed writes still dispatch and do not emit local write rejections', async () => {
  const f = fixture(async () => ({ ok: true, result: { saved: true } }))
  try {
    for (const [id, op] of ['data.put', 'data.delete', 'data.batch'].entries()) f.frame.peer.postMessage(request({ id, op }))
    await delay(30)
    assert.equal(f.calls.length, 3)
    assert.equal(f.replies.length, 3)
    assert.ok(f.replies.every(r => r.ok))
    assert.equal(f.events.filter(e => e.kind === 'write-rejected').length, 0)
  } finally { f.cleanup() }
})

test('log count and message length violations return numeric limits without dispatch', async () => {
  const f = fixture()
  try {
    f.frame.peer.postMessage(request({ id: 50, op: 'log', args: { entries: Array(51).fill({ level: 'log', msg: 'demo' }) } }))
    f.frame.peer.postMessage(request({ id: 51, op: 'log', args: { entries: [{ level: 'warn', msg: 'é'.repeat(4001) }] } }))
    await delay(30)
    assert.equal(f.calls.length, 0)
    assert.deepEqual(f.replies.map(r => [r.id, r.ok, r.error.code, r.error.limit, r.error.actual]), [
      [50, false, 'limit', 50, 51], [51, false, 'limit', 4000, 4001]
    ])
    assert.equal(f.events.filter(e => e.kind === 'denied').length, 2)
    assert.equal(f.events.filter(e => e.kind === 'write-rejected').length, 0)
  } finally { f.cleanup() }
})

test('malformed log entries stay invalid while exact log limits still dispatch', async () => {
  const f = fixture()
  try {
    const entries = [null, {}, [null], [{ level: 2, msg: 'x' }], [{ level: 'log', msg: null }]]
    for (const [id, value] of entries.entries()) f.frame.peer.postMessage(request({ id, op: 'log', args: { entries: value } }))
    f.frame.peer.postMessage(request({ id: 60, op: 'log', args: { entries: Array(50).fill({ level: 'log', msg: 'é'.repeat(4000) }) } }))
    await delay(40)
    assert.equal(f.calls.length, 1)
    assert.equal(f.calls[0][1].entries.length, 50)
    assert.equal(f.calls[0][1].entries[0].msg.length, 4000)
    assert.deepEqual(f.replies.slice(0, entries.length).map(r => r.error.code), entries.map(() => 'invalid'))
    assert.equal(f.replies.at(-1).ok, true)
  } finally { f.cleanup() }
})

test('data change metadata requires a live data grant while run events remain available', async () => {
  for (const grants of [[], ['logs'], [{ capability: 'data', status: 'requested' }], [{ capability: 'data', status: 'revoked' }]]) {
    const f = fixture(undefined, grants)
    try {
      f.mount.postEvent('data.changed', { seq: 12, changes: [{ collection: 'private', id: 'hidden' }] })
      f.mount.postEvent('run.updated', { status: 'running' })
      await delay(20)
      assert.deepEqual(f.replies.map(r => r.event), ['run.updated'])
    } finally { f.cleanup() }
  }
  const grants = [{ capability: 'data', status: 'granted' }]
  const f = fixture(undefined, grants)
  try {
    f.mount.postEvent('data.changed', { seq: 1, changes: [] })
    grants[0].status = 'revoked'
    f.mount.postEvent('data.changed', { seq: 2, changes: [{ id: 'hidden' }] })
    await delay(20)
    assert.deepEqual(f.replies.map(r => r.payload.seq), [1])
  } finally { f.cleanup() }
})

function consoleFixture() {
  const events = new Map()
  const messages = []
  const timers = []
  const parent = {}
  const element = () => ({ style: {}, setAttribute() {}, append() {}, replaceChildren() {} })
  const document = { head: element(), body: element(), createElement: element, addEventListener() {} }
  const window = { parent, addEventListener: (name, fn) => events.set(name, fn), removeEventListener: name => events.delete(name) }
  const port = { postMessage: message => messages.push(structuredClone(message)) }
  const context = vm.createContext({
    window, document, console: { log() {} },
    setInterval(fn) { timers.push(fn) }, clearInterval() {}
  })
  vm.runInContext(`(${spaceLoader.toString()})((${projectResolver.toString()})())`, context)
  events.get('message')({ source: parent, data: {
    v: 1, type: 'space-boot', grants: ['logs'],
    bundle: { space: { id: 'fixture', name: 'Fixture' }, rev: 1, manifest: {}, files: [] }
  }, ports: [port] })
  return { context, messages, flush: () => timers[0]() }
}

test('guest console makes truncation visible within the 4000-character cap and preserves original counts', async () => {
  const f = consoleFixture()
  await new Promise(resolve => setImmediate(resolve))
  f.flush()
  const source = ['x'.repeat(4001), 'é'.repeat(12345), '😀'.repeat(3000)]
  for (const text of source) {
    f.context.input = text
    vm.runInContext('console.log(input)', f.context)
  }
  f.flush()
  const entries = f.messages.at(-1).args.entries
  assert.equal(entries.length, source.length)
  for (const [index, entry] of entries.entries()) {
    assert.ok(entry.msg.length <= 4000)
    assert.ok(entry.msg.startsWith(source[index].slice(0, 100)))
    assert.match(entry.msg, /truncated/i)
    assert.ok(entry.msg.includes(String(source[index].length)))
  }
})

test('guest console preserves messages at the cap and reports the combined count for multi-part messages', async () => {
  const f = consoleFixture()
  await new Promise(resolve => setImmediate(resolve))
  f.flush()
  vm.runInContext('console.log("x".repeat(4000)); console.log("a".repeat(3000), "b".repeat(2000))', f.context)
  f.flush()
  const entries = f.messages.at(-1).args.entries
  assert.equal(entries[0].msg, 'x'.repeat(4000))
  assert.ok(entries[1].msg.length <= 4000)
  assert.match(entries[1].msg, /truncated/i)
  assert.ok(entries[1].msg.includes('5001'))
})

test('sparse log entries settle invalid without dispatch', async () => {
  const f = fixture()
  try {
    f.frame.peer.postMessage(request({ id: 80, op: 'log', args: { entries: Array(1) } }))
    await delay(30)
    assert.equal(f.calls.length, 0)
    assert.deepEqual(f.replies.map(r => [r.id, r.ok, r.error.code]), [[80, false, 'invalid']])
    assert.equal(f.events.filter(e => e.kind === 'denied').length, 1)
  } finally { f.cleanup() }
})

test('revoking an in-flight write grant emits the full local rejection', async () => {
  for (const op of ['data.put', 'data.delete', 'data.batch']) {
    let complete
    const grants = [{ capability: 'data', status: 'granted' }]
    const f = fixture(() => new Promise(resolve => { complete = resolve }), grants)
    try {
      f.frame.peer.postMessage(request({ op }))
      await delay(20)
      assert.equal(f.calls.length, 1)
      grants[0].status = 'revoked'
      complete({ ok: true, result: { saved: true } })
      await delay(20)
      assert.equal(f.replies[0].error.code, 'not_granted')
      assert.equal(f.replies[0].error.capability, 'data')
      assert.deepEqual(f.events.filter(e => e.kind === 'write-rejected'), [
        { kind: 'write-rejected', op, error: f.replies[0].error }
      ])
    } finally { f.cleanup() }
  }
})
