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
    const f = fixture(({ args }) => {
      requests.push(structuredClone(args))
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
      const first = batch ? requests[0].ops : [requests[0]]
      for (const op of first) { assert.match(op.id, /^r_[0-9a-f]{12}$/); assert.equal(op.base_rev, 0) }
      assert.equal(new Set(first.map(op => op.id)).size, first.length)
      await retry()
      assert.deepEqual(requests[1], requests[0])
      assert.equal(rows.size, first.length)
      assert.equal(f.writes.at(-1).status, 'conflict')
      const current = rows.get(first[0].id)
      current.rev = 2; current.data.text = 'newer chat note'
      await retry()
      assert.equal(rows.size, first.length)
      assert.equal(current.data.text, 'newer chat note')
      assert.equal(f.writes.at(-1).status, 'conflict')
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
    const sent = f.calls.filter(c => c.path.endsWith('/bridge')).map(c => c.body.args)
    assert.deepEqual(sent[1], sent[0])
    assert.equal(sent[1].base_rev, 4)
    assert.equal(sent[1].id, 'existing')
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
function routing() {
  let connectionId = openingRoute.connectionId, profile = openingRoute.profile
  const requests = []
  const host = {
    state: { connectionId: { get: () => connectionId }, profile: { get: () => profile } },
    profileRoutes: async () => [openingRoute],
    requestProfile: async (...args) => { requests.push(structuredClone(args)); return { closed: true } }
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
  assert.deepEqual(route.requests, [[openingRoute, 'plugin.living-spaces.close_session', { space_id: 'demo-space', session: 'late-session' }, 5000]])
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
  assert.deepEqual(route.requests, [[openingRoute, 'plugin.living-spaces.close_session', { space_id: 'demo-space', session: 'late-session' }, 5000]])
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
    assert.equal(route.requests.length, 1)
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
  assert.deepEqual(route.requests, [[primary, 'plugin.living-spaces.close_session', { space_id: 'demo-space', session: 'demo-session' }, 5000]])
})

for (const failure of ['missing', 'ambiguous', 'unsupported', 'error-result']) {
  test(`cross-scope cleanup fails closed when the public route is ${failure}`, async () => {
    const route = routing(), errors = []
    const f = fixture(() => ({ ok: true }), { host: route.host, backend: openingRoute, onCloseError: error => errors.push(error) })
    await f.session.ready
    route.switch()
    if (failure === 'missing') route.host.profileRoutes = async () => []
    if (failure === 'ambiguous') route.host.profileRoutes = async () => [openingRoute, { ...openingRoute, targetProfile: 'other' }]
    if (failure === 'unsupported') route.host.requestProfile = async () => { throw Object.assign(new Error('Method not found'), { code: -32601 }) }
    if (failure === 'error-result') route.host.requestProfile = async () => ({ error: { code: 'blocked', message: 'Cleanup blocked' } })
    await assert.rejects(f.session.destroy())
    assert.equal(errors.length, 3)
    assert.equal(f.calls.filter(call => call.method === 'DELETE').length, 0)
  })
}
