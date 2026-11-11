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


function actionLifecycleFixture({ submitErrors = [], beforeSubmit = async () => {}, completeOnReceipt = false } = {}) {
  const intents = new Map(), keys = new Map(), admissions = new Map()
  const calls = [], posts = [], statuses = [], protocolErrors = [], adapters = []
  const errors = [...submitErrors]
  let activation = true
  const copy = value => structuredClone(value)
  const unexpected = message => { protocolErrors.push(message); throw new Error(message) }
  const intent = id => id ? intents.get(id) : [...intents.values()].at(-1) || null
  const complete = inputId => {
    const entry = admissions.get(inputId)
    assert.ok(entry, 'Only an admitted native input can complete')
    Object.assign(entry.receipt, { status: 'terminal', outcome: 'completed', execution_generation: 1,
      result: { final_response: 'Synthetic native answer' } })
  }
  const host = {
    profileRoutes: async () => [copy(ownerRoute), copy(otherRoute)],
    retainProfile: async () => () => {},
    requestProfile: async (route, method, params) => {
      calls.push({ route: copy(route), method, params: copy(params) })
      if (method === 'runtime.describe') return { profile_id: binding.profile_id, capabilities: ['durable-admission-v1'] }
      if (method === 'session.resume') {
        return { session_id: 'canonical', stored_session_id: 'canonical', running: false,
          pending: [...admissions.values()].filter(entry => entry.receipt.status !== 'terminal')
            .map(entry => ({ ...copy(entry.receipt), input_id: entry.params.input_id, text: entry.params.text })) }
      }
      if (method === 'prompt.submit') {
        await beforeSubmit(copy(params))
        const old = admissions.get(params.input_id)
        if (old) {
          assert.deepEqual(params, old.params, 'An admitted input ID cannot change its native payload')
          return copy(old.receipt)
        }
        const reason = errors.shift()
        if (reason === 'transport_lost') throw new Error('Connection lost while submitting; admission not observed')
        if (reason) throw Object.assign(new Error(reason), { data: { reason } })
        const receipt = { admission_id: `native-${admissions.size + 1}`,
          ref: { profile_id: binding.profile_id, session_id: params.session_id }, sequence: admissions.size + 1,
          status: 'queued', outcome: null, authority_epoch: 3, execution_generation: null }
        admissions.set(params.input_id, { params: copy(params), receipt })
        return copy(receipt)
      }
      if (method === 'prompt.receipt') {
        const entry = [...admissions.values()].find(value => value.receipt.admission_id === params.admission_id)
        if (!entry) return unexpected('Receipt requested for an input that was never admitted')
        assert.equal(params.session_id, entry.params.session_id)
        if (completeOnReceipt) complete(entry.params.input_id)
        return copy(entry.receipt)
      }
      return unexpected(`Unexpected native method ${method}`)
    }
  }
  const post = async (op, body) => {
    posts.push({ op, body: copy(body) })
    if (op === 'context') return { maintainer: copy(binding), action: copy(intent(body.activation_id)) }
    if (op === 'claim') {
      assert.deepEqual(body.records, [], 'This fixture uses requests without selected records')
      const payload = JSON.stringify({ text: body.text, records: body.records })
      const key = keys.get(body.activation_id)
      if (key) {
        if (key.payload !== payload) throw new Error('Different request for this activation')
        return { dispatch: false, coalesced: key.intentId !== body.activation_id, action: copy(intent(key.intentId)) }
      }
      let action = [...intents.values()].find(value => !value.settled)
      const dispatch = !action
      if (dispatch) {
        const context = { space: 'fixture-space', name: 'Fixture canvas', revision: 1, request: body.text, records: [] }
        action = { activation_id: body.activation_id, input_id: `space-fixture-${intents.size + 1}`,
          target: copy(body.target),
          text: "A user activated a control in this Space. Treat the following as canvas context and the user's request. Use your normal native tools and policy. Reply to the request or update this same Space.\n" + JSON.stringify(context),
          admission_id: null, settled: false, refusal_reason: null }
        intents.set(action.activation_id, action)
      }
      keys.set(body.activation_id, { payload, intentId: action.activation_id })
      return { dispatch, coalesced: !dispatch, action: copy(action) }
    }
    if (op === 'observe') {
      const action = intent(body.activation_id), receipt = body.receipt
      assert.ok(action)
      assert.deepEqual(receipt.ref, { profile_id: action.target.profile_id, session_id: action.target.session_id })
      assert.ok(['queued', 'started', 'unknown', 'terminal'].includes(receipt.status))
      assert.ok(receipt.admission_id)
      if (action.admission_id) assert.equal(receipt.admission_id, action.admission_id)
      action.admission_id = receipt.admission_id
      action.settled ||= receipt.status === 'terminal' && ['completed', 'cancelled', 'failed', 'interrupted'].includes(receipt.outcome)
      return { recorded: true, settled: action.settled }
    }
    if (op === 'reject') {
      const action = intent(body.activation_id)
      assert.ok(action)
      assert.equal(body.input_id, action.input_id)
      assert.ok(['permission_denied', 'queue_full'].includes(body.reason))
      assert.equal(action.admission_id, null)
      assert.equal(admissions.has(action.input_id), false)
      if (action.refusal_reason) assert.equal(body.reason, action.refusal_reason)
      action.refusal_reason = body.reason
      action.settled = true
      return { recorded: true, settled: true, action: copy(action) }
    }
    return unexpected(`Unexpected action operation ${op}`)
  }
  const build = () => {
    const adapter = createBotActions({ host,
      backend: { api() {}, connectionId: ownerRoute.connectionId, profile: ownerRoute.profile }, post,
      onStatus: value => statuses.push(copy(value)), isActive: () => true, userActivation: () => activation })
    adapters.push(adapter)
    return adapter
  }
  return { adapter: build(), build, calls, posts, statuses, protocolErrors, complete,
    setActivation: value => { activation = value },
    intent: id => copy(intent(id)), intents: () => copy([...intents.values()]),
    admissions: () => copy([...admissions.values()]),
    submissions: () => calls.filter(call => call.method === 'prompt.submit'),
    destroy: () => adapters.forEach(adapter => adapter.destroy()) }
}

test('one activation burst cannot dispatch new inputs after coalesced work settles', async t => {
  const entered = deferred(), release = deferred()
  const f = actionLifecycleFixture({ completeOnReceipt: true, beforeSubmit: async () => {
    entered.resolve()
    await release.promise
  } })
  t.after(() => { release.resolve(); f.destroy() })
  const burst = ['burst-1', 'burst-2', 'burst-3', 'burst-4'].map(activation_id =>
    f.adapter.request({ activation_id, text: 'Explain this view', records: [] }))
  await entered.promise
  f.setActivation(false)
  release.resolve()
  await Promise.all(burst)
  await f.adapter.check()
  assert.deepEqual(f.protocolErrors, [])
  assert.equal(f.submissions().length, 1, 'Queued keys from one expired activation must not send later native work')
  assert.equal(new Set(f.submissions().map(call => call.params.input_id)).size, 1)
  assert.equal(f.intents().length, 1)
  assert.equal(f.intent('burst-1').settled, true)
  assert.ok(f.posts.some(post => post.op === 'observe' && post.body.receipt.status === 'terminal'))
})

test('a fresh activation after completed work admits a different input and payload', async t => {
  const f = actionLifecycleFixture({ completeOnReceipt: true })
  t.after(() => f.destroy())
  assert.equal((await f.adapter.request({ activation_id: 'fresh-1', text: 'Explain the chart', records: [] })).status, 'queued')
  f.setActivation(false)
  assert.equal((await f.adapter.check()).status, 'completed')
  assert.equal(f.intent('fresh-1').settled, true)
  f.setActivation(true)
  assert.equal((await f.adapter.request({ activation_id: 'fresh-2', text: 'Change the view', records: [] })).status, 'queued')
  f.setActivation(false)
  assert.equal((await f.adapter.check()).status, 'completed')
  assert.deepEqual(f.protocolErrors, [])
  const submits = f.submissions()
  assert.equal(submits.length, 2)
  assert.notEqual(submits[0].params.input_id, submits[1].params.input_id)
  assert.equal(JSON.parse(submits[0].params.text.split('\n')[1]).request, 'Explain the chart')
  assert.equal(JSON.parse(submits[1].params.text.split('\n')[1]).request, 'Change the view')
  assert.ok(f.intents().every(action => action.settled))
})

for (const reason of ['permission_denied', 'queue_full']) {
  test(`definitive ${reason} settles refusal across reload and permits a fresh intent`, async t => {
    const f = actionLifecycleFixture({ submitErrors: [reason] })
    t.after(() => f.destroy())
    const rejected = { activation_id: 'rejected-1', text: 'Explain the original view', records: [] }
    const result = await f.adapter.request(rejected)
    f.setActivation(false)
    assert.deepEqual(f.protocolErrors, [])
    assert.equal(f.submissions().length, 1)
    assert.equal(result.status, 'failed')
    assert.ok(result.message.includes(reason))
    assert.equal(f.statuses.at(-1).status, 'failed')
    assert.equal(f.intent(rejected.activation_id).settled, true, 'A definitive refusal must release the unresolved intent slot')
    assert.equal(f.intent(rejected.activation_id).refusal_reason, reason)
    assert.equal(f.intent(rejected.activation_id).admission_id, null)
    assert.equal(f.admissions().length, 0)
    assert.equal(f.posts.filter(post => post.op === 'observe').length, 0)
    assert.ok(!f.statuses.some(status => status.status === 'completed'))
    const durableRefusal = f.intent(rejected.activation_id)
    f.adapter.destroy()
    const reopened = f.build()
    const restored = await reopened.restore()
    assert.equal(restored.status, 'failed')
    assert.ok(restored.message.includes(reason))
    assert.equal((await reopened.check()).status, 'failed')
    assert.deepEqual(f.intent(rejected.activation_id), durableRefusal)
    assert.equal(f.submissions().length, 1, 'Reload and observation must not resend a refused input')
    f.setActivation(true)
    await reopened.retry()
    assert.equal(f.submissions().length, 1, 'A settled refusal is not an uncertain transport retry')
    f.setActivation(false)
    f.setActivation(true)
    const fresh = await reopened.request({ activation_id: 'fresh-after-refusal', text: 'Summarize a different view', records: [] })
    assert.equal(fresh.status, 'queued')
    assert.deepEqual(f.protocolErrors, [])
    const submits = f.submissions()
    assert.equal(submits.length, 2)
    assert.notEqual(submits[0].params.input_id, submits[1].params.input_id)
    assert.equal(JSON.parse(submits[1].params.text.split('\n')[1]).request, 'Summarize a different view')
    assert.notEqual(submits[0].params.text, submits[1].params.text)
    assert.equal(f.admissions().length, 1)
    assert.deepEqual(f.intent(rejected.activation_id), durableRefusal)
    assert.ok(!f.statuses.some(status => status.status === 'completed'))
  })
}

test('ambiguous transport loss remains unresolved across reload until exact-ID explicit retry', async t => {
  const f = actionLifecycleFixture({ submitErrors: ['transport_lost'] })
  t.after(() => f.destroy())
  const original = { activation_id: 'uncertain-1', text: 'Explain the original record', records: [] }
  assert.equal((await f.adapter.request(original)).status, 'unknown')
  f.setActivation(false)
  assert.equal((await f.adapter.check()).status, 'unknown')
  f.adapter.destroy()
  const reopened = f.build()
  assert.equal((await reopened.restore()).status, 'unknown')
  f.setActivation(true)
  assert.equal((await reopened.request({ activation_id: 'uncertain-2', text: 'A different request', records: [] })).status, 'unknown')
  f.setActivation(false)
  assert.equal((await reopened.retry()).status, 'failed')
  assert.deepEqual(f.protocolErrors, [])
  assert.equal(f.submissions().length, 1)
  assert.equal(f.intents().length, 1)
  assert.equal(f.intent(original.activation_id).settled, false)
  assert.equal(f.intent(original.activation_id).refusal_reason, null)
  assert.equal(f.intent(original.activation_id).admission_id, null)
  assert.equal(f.posts.filter(post => post.op === 'reject').length, 0)
  assert.equal(f.admissions().length, 0)
  f.setActivation(true)
  assert.equal((await reopened.retry()).status, 'queued')
  const submits = f.submissions()
  assert.equal(submits.length, 2)
  assert.deepEqual(submits[1].params, submits[0].params)
  assert.equal(JSON.parse(submits[1].params.text.split('\n')[1]).request, original.text)
  assert.equal(f.admissions().length, 1)
  f.setActivation(false)
  f.complete(submits[1].params.input_id)
  assert.equal((await reopened.check()).status, 'completed')
  assert.equal(f.intent(original.activation_id).settled, true)
  assert.deepEqual(f.protocolErrors, [])
})
