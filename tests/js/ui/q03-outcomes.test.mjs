import test from 'node:test'
import assert from 'node:assert/strict'
import { createSpaceSession } from '../../../src/desktop/ui/session.mjs'

const put = () => ({ collection: 'notes', id: 'existing', base_rev: 4, data: { text: 'original draft' } })
const confirmed = () => ({ ok: true, result: { rev: 5 }, outcome: { status: 'success' } })
const uncertain = code => ({ ok: false, error: { code, message: 'Effect is not confirmed' }, outcome: { status: 'unknown' } })

function fixture(transport, options = {}) {
  const bridges = [], writes = [], events = []
  let guest
  const rest = async (path, request = {}) => {
    if (path.endsWith('/sessions') && request.method === 'POST') return { session: 'q03-session', head_rev: 1, grants: ['data'] }
    if (path.endsWith('/bundle')) return { rev: 1 }
    if (path.endsWith('/actions/context')) return { maintainer: null, action: null }
    if (path.endsWith('/bridge')) {
      bridges.push(structuredClone(request.body))
      return transport(request.body, bridges.length)
    }
    if (request.method === 'DELETE') return { closed: true }
    throw new Error(`Unexpected Q03 request ${path}`)
  }
  const session = createSpaceSession({
    sid: 'q03-space', container: {}, rest,
    mount: (_container, value) => {
      guest = value
      return { destroy() {}, postEvent: (...args) => events.push(args) }
    },
    onEvent: event => events.push(event),
    onWrite: event => writes.push(event),
    ...options
  })
  return { session, bridges, writes, events, call: (...args) => guest.call(...args) }
}

function openingBackend() {
  const route = { connectionId: 'backend-a', profile: 'profile-a', targetProfile: 'target-a', mode: 'remote' }
  let active = true
  const requests = []
  return {
    backend: route,
    host: {
      state: {
        connectionId: { get: () => active ? route.connectionId : 'backend-b' },
        profile: { get: () => active ? route.profile : 'profile-b' }
      },
      profileRoutes: async () => [route],
      requestProfile: async (...args) => {
        requests.push(structuredClone(args))
        return args[1] === 'runtime.describe'
          ? { profile_id: 'target-a', capabilities: ['plugin-rpc-v1'] }
          : { closed: true }
      }
    },
    requests,
    switch() { active = false }
  }
}

async function unknownRetry(t, op, args) {
  const original = structuredClone(args)
  const f = fixture((_body, count) => {
    if (count === 1) throw new Error('Q03 response lost after possible commit')
    return uncertain('unavailable')
  })
  t.after(() => f.session.destroy())
  await f.session.ready
  await f.call(op, args)
  const failure = f.writes.at(-1)
  assert.equal(failure.status, 'unknown')
  assert.deepEqual(failure.args, original)
  const edited = structuredClone(original)
  if (op === 'data.batch') {
    edited.ops[0].data.text = 'edited after uncertainty'
    edited.ops[0].base_rev = 999
    args.ops[0].data.text = 'later caller mutation'
  } else {
    edited.base_rev = 999
    if (edited.data) {
      edited.data.text = 'edited after uncertainty'
      args.data.text = 'later caller mutation'
    }
  }
  await failure.retry(edited)
  assert.deepEqual(f.bridges.map(body => body.op), [op, 'outcome.get'], 'Unknown retry must look up, never replay the mutation')
  const [attempt, lookup] = f.bridges
  assert.equal(typeof attempt.request_id, 'string')
  assert.ok(attempt.request_id.length > 0)
  assert.deepEqual(lookup.args, { request_id: attempt.request_id })
  assert.equal(lookup.session, attempt.session)
  assert.deepEqual(attempt.args, original)
  assert.deepEqual(failure.args, original, 'Retry must not replace the frozen draft with an edited draft')
  assert.equal(f.writes.at(-1).status, 'unknown')
}

test('Q03 legacy confirmed success and definite rejection controls keep their host states', async t => {
  const rows = [
    [{ ok: true, result: { rev: 5 } }, 'saved'],
    [{ ok: false, error: { code: 'limit', message: 'Record limit' } }, 'failed'],
    [{ ok: false, error: { code: 'conflict', current: { rev: 5 } } }, 'conflict']
  ]
  for (const [reply, status] of rows) {
    const f = fixture(() => reply)
    t.after(() => f.session.destroy())
    await f.session.ready
    assert.deepEqual(await f.call('data.put', put()), reply)
    assert.deepEqual(f.writes.map(event => event.status), ['saving', status])
    assert.equal(f.bridges.length, 1)
  }
})

test('Q03 typed unknown overrides not_granted conflict and blocked code fallbacks', async t => {
  const observed = []
  for (const code of ['not_granted', 'conflict', 'blocked']) {
    const f = fixture(() => uncertain(code))
    t.after(() => f.session.destroy())
    await f.session.ready
    await f.call('data.put', put())
    observed.push([code, f.writes.at(-1).status])
    assert.equal(f.bridges.length, 1)
  }
  assert.deepEqual(observed, [['not_granted', 'unknown'], ['conflict', 'unknown'], ['blocked', 'unknown']])
})

test('Q03 record attempt identities live in the bridge envelope and differ for new attempts', async t => {
  const f = fixture(() => confirmed())
  t.after(() => f.session.destroy())
  await f.session.ready
  const args = put()
  const original = structuredClone(args)
  await f.call('data.put', args)
  await f.call('data.put', { ...put(), data: { text: 'explicit new attempt' } })
  assert.equal(f.bridges.length, 2)
  assert.deepEqual(args, original)
  assert.deepEqual(f.bridges[0].args, original)
  assert.equal(Object.hasOwn(f.bridges[0].args, 'request_id'), false)
  for (const body of f.bridges) {
    assert.equal(typeof body.request_id, 'string', 'A write needs a stable lookup identity outside operation args')
    assert.ok(body.request_id.length > 0)
  }
  assert.notEqual(f.bridges[0].request_id, f.bridges[1].request_id)
})

test('Q03 unknown put retry looks up the original attempt despite an edited draft', async t => {
  await unknownRetry(t, 'data.put', put())
})

test('Q03 unknown delete retry looks up the original attempt without resending deletion', async t => {
  await unknownRetry(t, 'data.delete', { collection: 'notes', id: 'existing', base_rev: 4 })
})

test('Q03 unknown batch retry looks up the original attempt without resending any operation', async t => {
  await unknownRetry(t, 'data.batch', { ops: [
    { op: 'put', ...put() },
    { op: 'delete', collection: 'notes', id: 'second', base_rev: 2 }
  ] })
})

test('Q03 receipt-missing unknown cannot be displayed Saved even when the lookup envelope is ok', async t => {
  const f = fixture((_body, count) => {
    if (count === 1) throw new Error('Q03 original response lost')
    return { ok: true, result: { found: false }, outcome: { status: 'unknown' } }
  })
  t.after(() => f.session.destroy())
  await f.session.ready
  await f.call('data.put', put())
  const failure = f.writes.at(-1)
  assert.equal(failure.status, 'unknown')
  await failure.retry()
  assert.equal(f.writes.at(-1).status, 'unknown', 'An absent receipt is not proof of a saved write')
  assert.equal(f.writes.some(event => event?.status === 'saved'), false)
  assert.deepEqual(f.bridges.map(body => body.op), ['data.put', 'outcome.get'])
})

test('Q03 authorized positive reconciliation clears uncertainty without another mutation', async t => {
  const f = fixture((body, count) => {
    if (count === 1) throw new Error('Q03 original response lost')
    return body.op === 'outcome.get' ? confirmed() : uncertain('blocked')
  })
  t.after(() => f.session.destroy())
  await f.session.ready
  await f.call('data.put', put())
  const failure = f.writes.at(-1)
  assert.equal(failure.status, 'unknown')
  await failure.retry()
  assert.equal(f.writes.at(-1).status, 'saved')
  assert.deepEqual(f.bridges.map(body => body.op), ['data.put', 'outcome.get'])
  assert.deepEqual(f.bridges[1].args, { request_id: f.bridges[0].request_id })
})

test('Q03 late retry confirmation after session close cannot publish Saved or enable another send', async t => {
  const pending = Promise.withResolvers(), started = Promise.withResolvers()
  const f = fixture((_body, count) => {
    if (count === 1) throw new Error('Q03 original response lost')
    started.resolve()
    return pending.promise
  })
  t.after(() => f.session.destroy())
  await f.session.ready
  await f.call('data.put', put())
  const failure = f.writes.at(-1)
  assert.equal(failure.status, 'unknown')
  const retry = failure.retry()
  await started.promise
  await f.session.destroy()
  const notificationCount = f.writes.length
  pending.resolve(confirmed())
  assert.equal((await retry).error.code, 'session_invalid')
  assert.equal(f.writes.length, notificationCount)
  assert.equal(f.writes.some(event => event?.status === 'saved'), false)
  const requestCount = f.bridges.length
  await failure.retry()
  assert.equal(f.bridges.length, requestCount)
})

test('Q03 late retry confirmation after backend switch stays in the opening scope and cannot publish Saved', async t => {
  const route = openingBackend()
  const pending = Promise.withResolvers(), started = Promise.withResolvers()
  const f = fixture((_body, count) => {
    if (count === 1) throw new Error('Q03 original response lost')
    started.resolve()
    return pending.promise
  }, { host: route.host, backend: route.backend })
  t.after(() => f.session.destroy())
  await f.session.ready
  await f.call('data.put', put())
  const failure = f.writes.at(-1)
  assert.equal(failure.status, 'unknown')
  const retry = failure.retry()
  await started.promise
  route.switch()
  const notificationCount = f.writes.length
  pending.resolve(confirmed())
  assert.equal((await retry).error.code, 'session_invalid')
  assert.equal(f.writes.length, notificationCount)
  assert.equal(f.writes.some(event => event?.status === 'saved'), false)
  const requestCount = f.bridges.length
  await failure.retry()
  assert.equal(f.bridges.length, requestCount)
  await f.session.destroy()
  const close = route.requests.filter(([, method]) => method === 'plugin.living-spaces.close_session')
  assert.deepEqual(close, [[route.backend, 'plugin.living-spaces.close_session', { space_id: 'q03-space', session: 'q03-session' }, 5000]])
})
