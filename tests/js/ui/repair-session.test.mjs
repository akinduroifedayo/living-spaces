import '../sandbox/env.mjs'
import test from 'node:test'
import assert from 'node:assert/strict'
import { createSpaceSession } from '../../../src/desktop/ui/session.mjs'

function fixture(transport, options = {}) {
  const writes = [], calls = []
  let bridge
  const rest = async (path, request = {}) => {
    calls.push({ path, ...structuredClone(request) })
    if (path.endsWith('/sessions')) return { session: 'demo-session', head_rev: 1, grants: ['data'] }
    if (path.endsWith('/bundle')) return { rev: 1 }
    if (path.endsWith('/bridge')) return transport(request.body)
    if (request.method === 'DELETE') return { closed: true }
    throw new Error(`Unexpected path ${path}`)
  }
  const session = createSpaceSession({ rest, sid: 'demo-space', container: {}, mount: (_, value) => { bridge = value; return { destroy() {} } }, onEvent() {}, onWrite: w => writes.push(w), ...options })
  return { session, calls, writes, call: (...args) => bridge.call(...args) }
}

test('closing a session the server already closed is not reported as a failure', async () => {
  const errors = []
  const rest = async (path, request = {}) => {
    if (path.endsWith('/sessions')) return { session: 'demo-session', head_rev: 1, grants: ['data'] }
    if (path.endsWith('/bundle')) return { rev: 1 }
    if (request.method === 'DELETE') throw new Error('403 {"error":{"code":"session_invalid","message":"This Space session is closed"}}')
    throw new Error(`Unexpected path ${path}`)
  }
  const session = createSpaceSession({ rest, sid: 'demo-space', container: {}, mount: () => ({ destroy() {} }), onEvent() {}, onCloseError: error => errors.push(error) })
  await session.ready
  assert.deepEqual(await session.destroy(), { closed: true })
  assert.deepEqual(errors, [])
})

for (const batch of [false, true]) {
  test(`F2 lost ${batch ? 'batch' : 'put'} response reuses create IDs and never overwrites a later edit`, async () => {
    const rows = new Map(), requests = []
    let lost = true
    const f = fixture(body => {
      const { op: operation, args } = body
      requests.push(structuredClone(body))
      if (operation === 'outcome.get') {
        assert.deepEqual(args, { request_id: requests[0].request_id })
        return { ok: false, error: { code: 'ambiguous' }, outcome: { status: 'unknown' } }
      }
      const ops = batch ? args.ops : [args]
      for (const op of ops) {
        const id = op.id ?? `server-${rows.size}`
        const current = rows.get(id)
        if (current && op.base_rev !== current.rev) return { ok: false, error: { code: 'conflict', current } }
      }
      for (const op of ops) rows.set(op.id ?? `server-${rows.size}`, { data: structuredClone(op.data), rev: 1 })
      if (lost) { lost = false; throw new Error('Response lost after commit') }
      return { ok: true, result: {} }
    })
    try {
      await f.session.ready
      const create = { collection: 'notes', data: { text: 'public demo' } }
      const args = batch ? { ops: [{ op: 'put', ...create }, { op: 'put', collection: 'notes', data: { text: 'second' } }] } : create
      await f.call(batch ? 'data.batch' : 'data.put', args)
      const retry = f.writes.at(-1).retry
      const first = batch ? requests[0].args.ops : [requests[0].args]
      for (const op of first) { assert.match(op.id, /^r_[0-9a-f]{12}$/); assert.equal(op.base_rev, 0) }
      assert.equal(new Set(first.map(op => op.id)).size, first.length)
      await retry()
      assert.equal(requests[1].op, 'outcome.get')
      assert.equal(requests.filter(request => request.op.startsWith('data.')).length, 1)
      assert.equal(rows.size, first.length)
      assert.equal(f.writes.at(-1).status, 'unknown')
      const current = rows.get(first[0].id)
      current.rev = 2; current.data.text = 'newer chat note'
      await retry()
      assert.equal(rows.size, first.length)
      assert.equal(current.data.text, 'newer chat note')
      assert.equal(f.writes.at(-1).status, 'unknown')
      assert.equal(requests[2].op, 'outcome.get')
      assert.equal(requests.filter(request => request.op.startsWith('data.')).length, 1)
      assert.equal(create.id, undefined)
    } finally { await f.session.destroy() }
  })
}

test('F2 uncertain transport outcome is distinct from a confirmed rejection', async () => {
  let reject = false
  const f = fixture(() => {
    if (!reject) throw new Error('Connection lost')
    return { ok: false, error: { code: 'limit', message: 'Record limit' } }
  })
  try {
    await f.session.ready
    await f.call('data.put', { collection: 'notes', data: {} })
    assert.equal(f.writes.at(-1).status, 'unknown')
    reject = true
    await f.writes.at(-1).retry()
    assert.equal(f.writes.at(-1).status, 'unknown')
    f.session.dismissWrite(f.writes.at(-1).token)
    await f.call('data.put', { collection: 'notes', data: { text: 'new attempt' } })
    assert.equal(f.writes.at(-1).status, 'failed')
  } finally { await f.session.destroy() }
})

test('F2 retry keeps the first draft snapshot and preserves explicit record revisions', async () => {
  const f = fixture(() => { throw new Error('Lost response') })
  try {
    await f.session.ready
    const args = { collection: 'notes', id: 'existing', base_rev: 4, data: { text: 'original' } }
    await f.call('data.put', args)
    args.data.text = 'later local edit'
    await f.writes.at(-1).retry()
    const sent = f.calls.filter(c => c.path.endsWith('/bridge')).map(c => c.body)
    assert.equal(sent[1].op, 'outcome.get')
    assert.deepEqual(sent[1].args, { request_id: sent[0].request_id })
    assert.equal(sent.filter(request => request.op === 'data.put').length, 1)
    assert.equal(sent[0].args.base_rev, 4)
    assert.equal(sent[0].args.id, 'existing')
    assert.equal(sent[0].args.data.text, 'original')
    assert.deepEqual(f.writes.at(-1).args, sent[0].args)
  } finally { await f.session.destroy() }
})

test('F5 cleanup retries transient failures and reports each failed attempt', async () => {
  let attempts = 0
  const errors = []
  const f = fixture(() => ({ ok: true }), {
    rest: async path => {
      if (path.endsWith('/sessions')) return { session: 'demo-session', head_rev: 1, grants: [] }
      if (path.endsWith('/bundle')) return { rev: 1 }
      attempts++
      if (attempts === 1) throw new Error('temporary close failure')
      return { closed: true }
    },
    onCloseError: error => errors.push(error.message)
  })
  await f.session.ready
  await Promise.all([f.session.destroy(), f.session.destroy()])
  assert.equal(attempts, 2)
  assert.deepEqual(errors, ['temporary close failure'])
  await f.session.destroy()
  assert.equal(attempts, 2)
})

test('F5 exhausted cleanup is observable and a later destroy retries', async () => {
  let attempts = 0, failing = true
  const errors = []
  const f = fixture(() => ({ ok: true }), {
    rest: async path => {
      if (path.endsWith('/sessions')) return { session: 'demo-session', head_rev: 1, grants: [] }
      if (path.endsWith('/bundle')) return { rev: 1 }
      attempts++
      if (failing) throw new Error('backend unavailable')
      return { closed: true }
    },
    onCloseError: error => errors.push(error.message)
  })
  await f.session.ready
  await assert.rejects(f.session.destroy(), /backend unavailable/)
  assert.equal(attempts, 3)
  assert.equal(errors.length, 3)
  failing = false
  await f.session.destroy()
  assert.equal(attempts, 4)
})

const openingRoute = { connectionId: 'backend-a', profile: 'demo-profile', targetProfile: 'demo', mode: 'remote' }
const described = { profile_id: 'demo', capabilities: ['durable-admission-v1', 'plugin-rpc-v1'] }
const describe = target => [target, 'runtime.describe', {}, 5000]
function routing() {
  let connectionId = openingRoute.connectionId, profile = openingRoute.profile
  const requests = []
  const host = {
    state: { connectionId: { get: () => connectionId }, profile: { get: () => profile } },
    profileRoutes: async () => [openingRoute],
    requestProfile: async (...args) => { requests.push(structuredClone(args)); return args[1] === 'runtime.describe' ? described : { closed: true } }
  }
  return { host, requests, switch() { connectionId = 'backend-b'; profile = 'other-profile' } }
}

test('F5 close uses the opening backend after a profile switch, including a late open', async () => {
  const opening = Promise.withResolvers()
  const route = routing(), requests = []
  const backend = { connectionId: openingRoute.connectionId, profile: openingRoute.profile }
  const f = fixture(() => ({ ok: true }), { backend, host: route.host, rest: async (path, options) => {
    requests.push({ path, ...options })
    assert.equal(route.host.state.connectionId.get(), 'backend-a', 'No REST after the scope switch')
    assert.ok(path.endsWith('/sessions'))
    return opening.promise
  } })
  route.switch()
  backend.connectionId = 'backend-b'; backend.profile = 'other-profile'
  await f.session.destroy()
  opening.resolve({ session: 'late-session', head_rev: 1, grants: [] })
  await f.session.ready
  assert.deepEqual(requests, [{ path: '/spaces/demo-space/sessions', method: 'POST' }])
  assert.deepEqual(route.requests, [describe(openingRoute), [openingRoute, 'plugin.living-spaces.close_session', { space_id: 'demo-space', session: 'late-session' }, 5000]])
})

test('active-scope cleanup uses public REST with the five-second timeout', async () => {
  const route = routing()
  const f = fixture(() => ({ ok: true }), { host: route.host, backend: openingRoute })
  await f.session.ready
  await f.session.destroy()
  assert.deepEqual(f.calls.at(-1), { path: '/spaces/demo-space/sessions/demo-session', method: 'DELETE', timeoutMs: 5000 })
  assert.deepEqual(route.requests, [])
})

test('an opening response after a scope switch is closed without mounting even before unmount', async () => {
  const route = routing(), opening = Promise.withResolvers()
  let mounts = 0
  const f = fixture(() => ({ ok: true }), {
    host: route.host, backend: openingRoute,
    rest: async path => { assert.ok(path.endsWith('/sessions')); return opening.promise },
    mount() { mounts++; return { destroy() {} } }
  })
  route.switch()
  opening.resolve({ session: 'late-session', head_rev: 1, grants: [] })
  await f.session.ready
  assert.equal(mounts, 0)
  assert.deepEqual(route.requests, [describe(openingRoute), [openingRoute, 'plugin.living-spaces.close_session', { space_id: 'demo-space', session: 'late-session' }, 5000]])
})

test('a bundle and writes arriving after a scope switch cannot mount or report saved', async () => {
  for (const phase of ['bundle', 'bridge']) {
    const route = routing(), pending = Promise.withResolvers(), started = Promise.withResolvers(), writes = []
    let mounts = 0, bridge
    const f = fixture(() => ({ ok: true }), {
      host: route.host, backend: openingRoute, onWrite: value => writes.push(value),
      rest: async path => {
        if (path.endsWith('/sessions')) return { session: 'demo-session', head_rev: 1, grants: ['data'] }
        if (path.endsWith(`/${phase}`)) { started.resolve(); return pending.promise }
        if (path.endsWith('/bundle')) return { rev: 1 }
        throw new Error(`Unexpected REST ${path}`)
      },
      mount(_, options) { mounts++; bridge = options; return { destroy() {} } }
    })
    let result
    if (phase === 'bridge') { await f.session.ready; result = bridge.call('data.put', { data: {} }) }
    await started.promise
    route.switch()
    pending.resolve(phase === 'bundle' ? { rev: 1 } : { ok: true, result: {} })
    if (phase === 'bundle') { await assert.rejects(f.session.ready, /backend changed/); assert.equal(mounts, 0) }
    else { assert.equal((await result).error.code, 'session_invalid'); assert.deepEqual(writes.map(value => value.status), ['saving']) }
    await f.session.destroy()
    assert.equal(route.requests.filter(([, method]) => method === 'plugin.living-spaces.close_session').length, 1)
  }
})

test('local cleanup selects only the unique primary route in the captured profile', async () => {
  const route = routing()
  route.host.state.connectionId.get = () => null
  const primary = { ...openingRoute, primary: true }
  route.host.profileRoutes = async () => [{ ...primary, profile: 'other-profile' }, primary]
  const f = fixture(() => ({ ok: true }), { host: route.host, backend: { connectionId: null, profile: openingRoute.profile } })
  await f.session.ready
  route.switch()
  await f.session.destroy()
  assert.deepEqual(route.requests, [describe(primary), [primary, 'plugin.living-spaces.close_session', { space_id: 'demo-space', session: 'demo-session' }, 5000]])
})

test('cross-scope cleanup checks plugin-rpc-v1 on the opening route before calling the plugin method', async () => {
  const route = routing()
  const f = fixture(() => ({ ok: true }), { host: route.host, backend: openingRoute })
  await f.session.ready
  route.switch()
  await f.session.destroy()
  assert.deepEqual(route.requests, [
    describe(openingRoute),
    [openingRoute, 'plugin.living-spaces.close_session', { space_id: 'demo-space', session: 'demo-session' }, 5000]
  ])
})

test('cross-scope cleanup on a gateway without plugin-rpc-v1 reports why and never calls the plugin method', async () => {
  const route = routing(), errors = []
  route.host.requestProfile = async (...args) => {
    route.requests.push(structuredClone(args))
    if (args[1] === 'runtime.describe') return { profile_id: 'demo', capabilities: ['durable-admission-v1'] }
    return { closed: true }
  }
  const f = fixture(() => ({ ok: true }), { host: route.host, backend: openingRoute, onCloseError: error => errors.push(error) })
  await f.session.ready
  route.switch()
  await assert.rejects(f.session.destroy(), /plugin-rpc-v1/)
  assert.deepEqual(route.requests.map(([, method]) => method), ['runtime.describe'])
  assert.equal(errors.length, 1)
  assert.match(errors[0].message, /plugin-rpc-v1/)
  assert.equal(f.calls.filter(call => call.method === 'DELETE').length, 0)
})

for (const failure of ['missing', 'ambiguous', 'unsupported', 'error-result']) {
  test(`cross-scope cleanup fails closed when the public route is ${failure}`, async () => {
    const route = routing(), errors = []
    const f = fixture(() => ({ ok: true }), { host: route.host, backend: openingRoute, onCloseError: error => errors.push(error) })
    await f.session.ready
    route.switch()
    if (failure === 'missing') route.host.profileRoutes = async () => []
    if (failure === 'ambiguous') route.host.profileRoutes = async () => [openingRoute, { ...openingRoute, targetProfile: 'other' }]
    const plugin = answer => async (target, method) => method === 'runtime.describe' ? described : answer()
    if (failure === 'unsupported') route.host.requestProfile = plugin(() => { throw Object.assign(new Error('Method not found'), { code: -32601 }) })
    if (failure === 'error-result') route.host.requestProfile = plugin(() => ({ error: { code: 'blocked', message: 'Cleanup blocked' } }))
    await assert.rejects(f.session.destroy())
    assert.equal(errors.length, 3)
    assert.equal(f.calls.filter(call => call.method === 'DELETE').length, 0)
  })
}

const harness = async plan => {
  const v8 = await import('node:v8'), vm = await import('node:vm')
  v8.setFlagsFromString('--expose_gc')
  const gc = vm.runInNewContext('gc')
  const requests = [], heldReplies = []
  let bridge, last = null
  const rest = async (path, request = {}) => {
    if (path.endsWith('/sessions')) return { session: 'demo-session', head_rev: 1, grants: ['data'] }
    if (path.endsWith('/bundle')) return { rev: 1 }
    if (request.method === 'DELETE') return { closed: true }
    const body = request.body
    requests.push({ op: body.op, request_id: body.op === 'outcome.get' ? body.args.request_id : body.request_id, args: body.args })
    const reply = await plan(body, requests.length)
    if (reply && typeof reply === 'object') heldReplies.push(new WeakRef(reply))
    return reply
  }
  const session = createSpaceSession({ rest, sid: 'demo-space', container: {}, mount: (_, v) => { bridge = v; return { destroy() {} } },
    onEvent() {}, onWrite: w => { if (w) last = w } })
  await session.ready
  const collect = async () => { for (let i = 0; i < 3; i++) { await new Promise(r => setTimeout(r, 0)); gc() } }
  return { session, requests, heldReplies, collect, put: args => bridge.call('data.put', args), last: () => last, clear: () => { last = null } }
}

test('settled and dismissed writes are not retained by the session', async () => {
  let failNext = 0
  const h = await harness(body => {
    if (failNext && body.op === 'data.put') { failNext--; return { ok: false, error: { code: 'invalid', message: 'no' }, outcome: { status: 'rejected' }, pad: 'z'.repeat(64 * 1024) } }
    return { ok: true, result: { pad: 'x'.repeat(64 * 1024) } }
  })
  try {
    for (let i = 0; i < 50; i++) await h.put({ collection: 'notes', data: { text: `n${i}`, pad: 'y'.repeat(64 * 1024) } })
    failNext = 20
    for (let i = 0; i < 20; i++) {
      await h.put({ collection: 'notes', data: { text: `f${i}` } })
      h.session.dismissWrite(h.last().token)
    }
    h.clear()
    await h.collect()
    assert.ok(h.heldReplies.filter(ref => ref.deref()).length <= 1, 'settled or dismissed write replies must be collectable')
  } finally { await h.session.destroy() }
})

test('a held retry closure follows the latest attempt for its token and never replays superseded arguments', async () => {
  let mode = 'conflict'
  const h = await harness(body => {
    if (body.op === 'outcome.get') return { ok: false, error: { code: 'ambiguous' }, outcome: { status: 'unknown' } }
    if (mode === 'conflict') { mode = 'lose'; return { ok: false, error: { code: 'conflict', message: 'stale' }, outcome: { status: 'rejected' } } }
    if (mode === 'lose') { mode = 'ok'; throw new Error('Response lost after commit') }
    return { ok: true, result: {} }
  })
  try {
    await h.put({ collection: 'notes', id: 'r1', base_rev: 1, data: { text: 'mine' } })
    const conflict = h.last()
    assert.equal(conflict.status, 'conflict')
    await conflict.retry({ ...conflict.args, base_rev: 2 })            // corrected retry; response lost -> unknown
    const unknown = h.last()
    assert.equal(unknown.status, 'unknown')
    h.session.dismissWrite(unknown.token)
    const puts = h.requests.filter(r => r.op === 'data.put').length
    await conflict.retry()                                              // the ORIGINAL event's closure
    assert.equal(h.requests.at(-1).op, 'outcome.get', 'must reconcile the latest unknown attempt, not resend')
    assert.equal(h.requests.at(-1).request_id, h.requests.filter(r => r.op === 'data.put').at(-1).request_id)
    assert.equal(h.requests.filter(r => r.op === 'data.put').length, puts)
  } finally { await h.session.destroy() }
})

test('after a successful retry, an older closure returns the confirmation instead of resending', async () => {
  let mode = 'fail'
  const h = await harness(body => {
    if (mode === 'fail') { mode = 'ok'; return { ok: false, error: { code: 'invalid', message: 'no' }, outcome: { status: 'rejected' } } }
    return { ok: true, result: { saved: true } }
  })
  try {
    await h.put({ collection: 'notes', data: { text: 'x' } })
    const failed = h.last()
    assert.equal(failed.status, 'failed')
    const ok = await failed.retry()
    assert.equal(ok.ok, true)
    const puts = h.requests.filter(r => r.op === 'data.put').length
    const again = await failed.retry()
    assert.deepEqual(again, ok)
    assert.equal(h.requests.filter(r => r.op === 'data.put').length, puts, 'a confirmed write must not be resent')
  } finally { await h.session.destroy() }
})
