import test from 'node:test'
import assert from 'node:assert/strict'
import { createBotActions } from '../../../src/desktop/ui/actions.mjs'
import { createSpaceSession } from '../../../src/desktop/ui/session.mjs'

const ownerRoute = { connectionId: 'owner-connection', profile: 'owner-desktop', targetProfile: 'owner', mode: 'remote' }
const otherRoute = { connectionId: 'active-connection', profile: 'active-other', targetProfile: 'other', mode: 'remote' }
const binding = { profile_id: '/native/owner', stored_session_id: 'physical', conversation_id: 'conversation', session_key: 'key' }
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }

function fixture(overrides = {}) {
  let action = null
  let receipt = { admission_id: 'native-admission', ref: { profile_id: binding.profile_id, session_id: 'canonical' }, sequence: 1,
    status: 'queued', outcome: null, authority_epoch: 3, execution_generation: null }
  const calls = [], statuses = [], posts = [], keys = new Map()
  let releases = 0
  const host = {
    state: { profile: { get: () => otherRoute.profile }, connectionId: { get: () => otherRoute.connectionId } },
    profileRoutes: async () => [ownerRoute, otherRoute],
    retainProfile: async route => { calls.push(['retain', route]); return () => { releases++ } },
    request: () => { throw new Error('Ambient request forbidden') },
    requestProfile: async (route, method, params) => {
      calls.push([method, structuredClone(route), structuredClone(params)])
      if (overrides.rpc) {
        const result = await overrides.rpc(route, method, params)
        if (result !== undefined) return result
      }
      if (method === 'runtime.describe') return { profile_id: binding.profile_id, capabilities: ['durable-admission-v1'] }
      if (method === 'session.resume') return { session_id: 'canonical', stored_session_id: 'canonical', running: true, pending: [] }
      if (method === 'prompt.submit' || method === 'prompt.receipt') return structuredClone(receipt)
      throw new Error(`Unexpected RPC ${method}`)
    }
  }
  Object.assign(host, overrides.host)
  const post = async (op, body) => {
    posts.push([op, structuredClone(body)])
    if (op === 'context') return { maintainer: binding, action: action && structuredClone(action) }
    if (op === 'claim') {
      const request = JSON.stringify([body.text, body.records])
      if (keys.has(body.activation_id) && keys.get(body.activation_id) !== request) throw new Error('Different request for this activation')
      keys.set(body.activation_id, request)
      if (action) return { dispatch: false, coalesced: action.activation_id !== body.activation_id, action: structuredClone(action) }
      action = { activation_id: body.activation_id, input_id: 'stable-native-input', target: body.target, text: 'immutable context payload', admission_id: null, settled: false }
      return { dispatch: true, action: structuredClone(action) }
    }
    if (op === 'observe') {
      action.admission_id = body.receipt.admission_id
      action.settled = body.receipt.status === 'terminal'
      return { recorded: true, settled: action.settled }
    }
    throw new Error(`Unexpected operation ${op}`)
  }
  const build = () => createBotActions({ host, backend: { api() {}, connectionId: ownerRoute.connectionId, profile: ownerRoute.profile }, post,
    onStatus: value => statuses.push(value), isActive: () => true, userActivation: overrides.userActivation || (() => true) })
  const adapter = build()
  return { adapter, build, calls, statuses, posts, host, setReceipt: value => { receipt = { ...receipt, ...value } }, releases: () => releases, action: () => action }
}
const request = { activation_id: 'click-1', text: 'Explain the selected record', records: [] }

test('a switched active chat/profile cannot replace the pinned owner and queued is not complete', async t => {
  const f = fixture()
  t.after(() => f.adapter.destroy())
  const result = await f.adapter.request(request)
  assert.equal(result.status, 'queued')
  assert.equal(f.calls.filter(([method]) => method === 'prompt.submit').length, 1)
  for (const [, route] of f.calls) assert.deepEqual(route, ownerRoute)
  const submit = f.calls.find(([method]) => method === 'prompt.submit')[2]
  assert.deepEqual(submit, { session_id: 'canonical', input_id: 'stable-native-input', text: 'immutable context payload' })
  assert.ok(!f.statuses.some(item => item.status === 'completed'))
})

test('native receipt alone determines busy and correlated completion with answer', async t => {
  const f = fixture()
  t.after(() => f.adapter.destroy())
  await f.adapter.request(request)
  f.setReceipt({ status: 'started', execution_generation: 5 })
  assert.equal((await f.adapter.check()).status, 'busy')
  f.setReceipt({ status: 'terminal', outcome: 'completed', result: { final_response: 'Here is the explanation.' } })
  const result = await f.adapter.check()
  assert.equal(result.status, 'completed')
  assert.equal(result.answer, 'Here is the explanation.')
  assert.equal(f.releases(), 1)
})

test('unknown admission has no automatic resend; explicit retry preserves exact input and payload', async t => {
  let lose = true
  const f = fixture({ rpc: async (_route, method) => { if (method === 'prompt.submit' && lose) { lose = false; throw new Error('Connection lost after send') } } })
  t.after(() => f.adapter.destroy())
  assert.equal((await f.adapter.request(request)).status, 'unknown')
  await f.adapter.check()
  assert.equal(f.calls.filter(([method]) => method === 'prompt.submit').length, 1)
  await f.adapter.retry()
  const submits = f.calls.filter(([method]) => method === 'prompt.submit')
  assert.equal(submits.length, 2)
  assert.deepEqual(submits[0][2], submits[1][2])
})

test('reload observes a durable intent without submitting again', async t => {
  const f = fixture()
  await f.adapter.request(request)
  f.adapter.destroy()
  const reopened = f.build()
  t.after(() => reopened.destroy())
  assert.equal((await reopened.restore()).status, 'queued')
  assert.equal(f.calls.filter(([method]) => method === 'prompt.submit').length, 1)
})

test('duplicate requests coalesce and changed same-key payload fails visibly', async t => {
  const f = fixture()
  t.after(() => f.adapter.destroy())
  await Promise.all([f.adapter.request(request), f.adapter.request(request), f.adapter.request({ ...request, activation_id: 'click-2' })])
  assert.equal(f.calls.filter(([method]) => method === 'prompt.submit').length, 1)
  const conflict = await f.adapter.request({ ...request, text: 'Something different' })
  assert.equal(conflict.status, 'failed')
  assert.match(conflict.message, /Different request/)
})

test('mount and timer actions without user activation never call native transport', async t => {
  const f = fixture({ userActivation: () => false })
  t.after(() => f.adapter.destroy())
  assert.equal((await f.adapter.request(request)).status, 'failed')
  assert.equal(f.calls.length, 0)
  assert.equal(f.posts.length, 0)
})

test('a missing or ambiguous registered route fails offline without fallback', async t => {
  for (const routes of [[], [ownerRoute, ownerRoute]]) {
    const f = fixture({ host: { profileRoutes: async () => routes } })
    t.after(() => f.adapter.destroy())
    assert.equal((await f.adapter.request(request)).status, 'offline')
    assert.equal(f.calls.length, 0)
  }
})

test('canonical profile mismatch prevents any native submission', async t => {
  const f = fixture({ rpc: async (_route, method) => method === 'runtime.describe' ? { profile_id: '/native/other', capabilities: ['durable-admission-v1'] } : undefined })
  t.after(() => f.adapter.destroy())
  assert.equal((await f.adapter.request(request)).status, 'failed')
  assert.ok(!f.calls.some(([method]) => method === 'prompt.submit'))
})

test('route removed after resume fails the fresh registered-route check', async t => {
  const f = fixture({ rpc: async (_route, method) => { if (method === 'session.resume') f.host.profileRoutes = async () => [otherRoute] } })
  t.after(() => f.adapter.destroy())
  assert.equal((await f.adapter.request(request)).status, 'offline')
  assert.ok(!f.calls.some(([method]) => method === 'prompt.submit'))
})

test('an unrelated receipt cannot complete or release the activation', async t => {
  const f = fixture()
  t.after(() => f.adapter.destroy())
  await f.adapter.request(request)
  f.setReceipt({ status: 'terminal', outcome: 'completed', ref: { profile_id: '/native/other', session_id: 'other' } })
  assert.equal((await f.adapter.check()).status, 'unknown')
  assert.equal(f.action().settled, false)
})

test('closing during admission suppresses late observation and delivery', async () => {
  const pending = deferred(), entered = deferred()
  const f = fixture({ rpc: async (_route, method) => { if (method === 'prompt.submit') { entered.resolve(); return pending.promise } } })
  const result = f.adapter.request(request)
  await entered.promise
  f.adapter.destroy()
  const count = f.statuses.length
  pending.resolve({ admission_id: 'late', status: 'terminal', outcome: 'completed', ref: { profile_id: binding.profile_id, session_id: 'canonical' } })
  await result
  assert.equal(f.statuses.length, count)
  assert.equal(f.posts.filter(([op]) => op === 'observe').length, 0)
  assert.equal(f.releases(), 1)
})

test('native denial remains visible and never reports completion', async t => {
  const f = fixture({ rpc: async (_route, method) => { if (method === 'prompt.submit') throw Object.assign(new Error('permission_denied'), { data: { reason: 'permission_denied' } }) } })
  t.after(() => f.adapter.destroy())
  const result = await f.adapter.request(request)
  assert.equal(result.status, 'failed')
  assert.match(result.message, /permission_denied/)
  assert.equal(f.calls.filter(([method]) => method === 'prompt.submit').length, 1)
})

test('Space action REST and cleanup stay on the captured backend after ambient switch', async () => {
  const calls = [], statuses = []
  let mounted
  const backend = { connectionId: ownerRoute.connectionId, profile: ownerRoute.profile, api: async args => {
    calls.push(args)
    if (args.path.endsWith('/sessions')) return { session: 'bridge-session', head_rev: 1, grants: [] }
    if (args.path.endsWith('/bundle')) return { rev: 1 }
    if (args.path.endsWith('/actions/context')) throw new Error('No maintaining session is bound')
    if (args.method === 'DELETE') return { closed: true }
    throw new Error('Unexpected request')
  } }
  const session = createSpaceSession({ host: {}, backend, sid: 'canvas', rest: () => { throw new Error('Ambient REST forbidden') },
    container: {}, mount: (_container, options) => { mounted = options; return { destroy() {}, postEvent() {} } }, onEvent() {}, onAction: value => statuses.push(value) })
  await session.ready
  await session.checkAction()
  await session.destroy()
  assert.ok(calls.some(call => call.path.endsWith('/actions/context')))
  assert.ok(calls.every(call => call.connectionId === ownerRoute.connectionId && call.profile === ownerRoute.profile))
  assert.equal((await mounted.call('bot.request', request)).error.code, 'session_invalid')
})


test('coalescing a different activation explicitly says no new request was sent', async t => {
  const f = fixture()
  t.after(() => f.adapter.destroy())
  await f.adapter.request(request)
  const result = await f.adapter.request({ ...request, activation_id: 'second', text: 'A different question' })
  assert.equal(result.activationId, 'click-1')
  assert.match(result.message, /did not send a new request/)
  assert.equal(f.calls.filter(([method]) => method === 'prompt.submit').length, 1)
})

test('legacy runtime identity is refused without creating a replacement session', async t => {
  const f = fixture({ rpc: async (_route, method) => method === 'session.resume' ? { session_id: 'ephemeral', stored_session_id: 'physical' } : undefined })
  t.after(() => f.adapter.destroy())
  assert.equal((await f.adapter.request(request)).status, 'failed')
  assert.ok(!f.calls.some(([method]) => ['prompt.submit', 'session.create'].includes(method)))
})
