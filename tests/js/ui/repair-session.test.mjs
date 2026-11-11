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

test('F5 close uses the opening backend after a profile switch, including a late open', async () => {
  const opening = Promise.withResolvers()
  const requests = [], closed = []
  let active = 'backend-a'
  const backend = { connectionId: active, profile: 'demo-profile', api: async request => {
    requests.push(request)
    if (request.path.endsWith('/sessions')) return opening.promise
    if (request.method === 'DELETE') { closed.push(request.connectionId); return { closed: true } }
    return { rev: 1 }
  } }
  const f = fixture(() => ({ ok: true }), { backend, rest: async () => { throw new Error('active backend changed') } })
  active = 'backend-b'
  backend.connectionId = active
  await f.session.destroy()
  opening.resolve({ session: 'late-session', head_rev: 1, grants: [] })
  await f.session.ready
  assert.deepEqual(closed, ['backend-a'])
  assert.equal(requests[0].connectionId, 'backend-a')
  assert.equal(requests[1].profile, 'demo-profile')
  assert.equal(requests[1].path, '/api/plugins/living-spaces/spaces/demo-space/sessions/late-session')
})
