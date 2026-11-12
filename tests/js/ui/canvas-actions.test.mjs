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
  const build = () => createBotActions({ host, backend: { connectionId: ownerRoute.connectionId, profile: ownerRoute.profile }, post,
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

test('Space actions refuse stale REST while cleanup uses the captured public route', async () => {
  const calls = [], statuses = [], routed = []
  let mounted, active = ownerRoute
  const host = {
    state: { connectionId: { get: () => active.connectionId }, profile: { get: () => active.profile } },
    profileRoutes: async () => [ownerRoute, otherRoute],
    requestProfile: async (...args) => { routed.push(args); return { closed: true } }
  }
  const rest = async (path, options) => {
    calls.push({ path, ...options, connectionId: active.connectionId, profile: active.profile })
    if (path.endsWith('/sessions')) return { session: 'bridge-session', head_rev: 1, grants: [] }
    if (path.endsWith('/bundle')) return { rev: 1 }
    if (path.endsWith('/actions/context')) throw new Error('No maintaining session is bound')
    throw new Error('Unexpected request')
  }
  const session = createSpaceSession({ host, backend: ownerRoute, sid: 'canvas', rest,
    container: {}, mount: (_container, options) => { mounted = options; return { destroy() {}, postEvent() {} } }, onEvent() {}, onAction: value => statuses.push(value) })
  await session.ready
  await session.checkAction()
  active = otherRoute
  const count = calls.length
  await session.checkAction()
  assert.equal(calls.length, count)
  await session.destroy()
  assert.ok(calls.some(call => call.path.endsWith('/actions/context')))
  assert.ok(calls.every(call => call.connectionId === ownerRoute.connectionId && call.profile === ownerRoute.profile))
  assert.deepEqual(routed, [[ownerRoute, 'plugin.living-spaces.close_session', { space_id: 'canvas', session: 'bridge-session' }, 5000]])
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
      backend: { connectionId: ownerRoute.connectionId, profile: ownerRoute.profile }, post,
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

function completedAdmissionRecoveryFixture(submitSteps) {
  const nativeAdmissions = new Map(), observedReceipts = new Map(), intents = new Map(), keys = new Map()
  const submissions = [], lookups = [], posts = [], statuses = [], protocolErrors = [], adapters = []
  const steps = [...submitSteps]
  const copy = value => structuredClone(value)
  const intent = id => id ? intents.get(id) : [...intents.values()].at(-1) || null
  const requireProtocol = (condition, message) => {
    if (!condition) {
      protocolErrors.push(message)
      throw new Error(message)
    }
  }
  const host = {
    profileRoutes: async () => [copy(ownerRoute)],
    retainProfile: async () => () => {},
    requestProfile: async (route, method, params) => {
      requireProtocol(JSON.stringify(route) === JSON.stringify(ownerRoute), 'Native calls must use the owner route')
      if (method === 'runtime.describe') return { profile_id: binding.profile_id, capabilities: ['durable-admission-v1'] }
      if (method === 'session.resume') {
        requireProtocol(['physical', 'canonical'].includes(params.session_id), 'Resume must use the bound session')
        return { session_id: 'canonical', stored_session_id: 'canonical', running: false, pending: [] }
      }
      if (method === 'prompt.submit') {
        submissions.push(copy(params))
        requireProtocol(params.session_id === 'canonical' && !!params.input_id && !!params.text, 'Submit must carry the canonical session, input ID and text')
        const step = steps.shift() || 'deliver'
        if (step === 'runtime_draining') throw Object.assign(new Error('Runtime is draining before admission lookup'), { data: { reason: step } })
        requireProtocol(['deliver', 'complete_then_drop'].includes(step), 'Unknown synthetic submit step')
        lookups.push(params.input_id)
        let entry = nativeAdmissions.get(params.input_id)
        if (entry) {
          requireProtocol(JSON.stringify(entry.params) === JSON.stringify(params), 'An exact-ID retry must preserve the native payload')
        } else {
          const receipt = { admission_id: `completed-${nativeAdmissions.size + 1}`,
            ref: { profile_id: binding.profile_id, session_id: params.session_id }, sequence: nativeAdmissions.size + 1,
            status: 'terminal', outcome: 'completed', authority_epoch: 3, execution_generation: 1,
            result: { final_response: 'The original native answer.' } }
          entry = { params: copy(params), receipt }
          nativeAdmissions.set(params.input_id, entry)
        }
        if (step === 'complete_then_drop') throw new Error('Response lost after native admission and completion')
        return copy(entry.receipt)
      }
      if (method === 'prompt.receipt') {
        const entry = [...nativeAdmissions.values()].find(value => value.receipt.admission_id === params.admission_id)
        requireProtocol(!!entry && entry.params.session_id === params.session_id, 'Receipt lookup must identify a native admission')
        return copy(entry.receipt)
      }
      requireProtocol(false, `Unexpected native method ${method}`)
    }
  }
  const post = async (op, body) => {
    posts.push({ op, body: copy(body) })
    if (op === 'context') return { maintainer: copy(binding), action: copy(intent(body.activation_id)) }
    if (op === 'claim') {
      requireProtocol(Array.isArray(body.records) && body.records.length === 0, 'Recovery requests have no selected records')
      const payload = JSON.stringify({ text: body.text, records: body.records })
      const key = keys.get(body.activation_id)
      if (key) {
        requireProtocol(key.payload === payload, 'An activation key must preserve its request')
        return { dispatch: false, coalesced: key.intentId !== body.activation_id, action: copy(intent(key.intentId)) }
      }
      let action = [...intents.values()].find(value => !value.settled)
      const dispatch = !action
      if (dispatch) {
        action = { activation_id: body.activation_id, input_id: `recovery-${body.activation_id}`, target: copy(body.target),
          text: `Canvas context\n${JSON.stringify({ request: body.text, records: body.records })}`,
          admission_id: null, settled: false, refusal_reason: null }
        intents.set(action.activation_id, action)
      }
      keys.set(body.activation_id, { payload, intentId: action.activation_id })
      return { dispatch, coalesced: !dispatch, action: copy(action) }
    }
    const action = intent(body.activation_id)
    requireProtocol(!!action, 'Persistence must address an existing intent')
    if (op === 'observe') {
      const receipt = body.receipt
      requireProtocol(receipt.ref?.profile_id === action.target.profile_id && receipt.ref?.session_id === action.target.session_id &&
        !!receipt.admission_id && (!action.admission_id || action.admission_id === receipt.admission_id), 'Observed receipt must correlate to the intent')
      observedReceipts.set(action.activation_id, copy(receipt))
      action.admission_id = receipt.admission_id
      action.settled = receipt.status === 'terminal' && ['completed', 'cancelled', 'failed', 'interrupted'].includes(receipt.outcome)
      return { recorded: true, settled: action.settled }
    }
    if (op === 'reject') {
      requireProtocol(body.input_id === action.input_id && action.admission_id === null && body.reason === 'runtime_draining', 'Refusal must identify the locally unobserved input')
      action.refusal_reason = body.reason
      action.settled = true
      return { recorded: true, settled: true, action: copy(action) }
    }
    requireProtocol(false, `Unexpected persistence operation ${op}`)
  }
  const build = () => {
    const adapter = createBotActions({ host,
      backend: { connectionId: ownerRoute.connectionId, profile: ownerRoute.profile }, post,
      onStatus: value => statuses.push(copy(value)), isActive: () => true, userActivation: () => true })
    adapters.push(adapter)
    return adapter
  }
  return { adapter: build(), build, submissions, lookups, posts, statuses, protocolErrors,
    intent: id => copy(intent(id)), intents: () => copy([...intents.values()]),
    native: () => copy([...nativeAdmissions.values()]), observed: () => copy([...observedReceipts.values()]),
    destroy: () => adapters.forEach(adapter => adapter.destroy()) }
}

test('completed admission with a lost response stays unresolved when an exact-ID retry is refused before lookup', async t => {
  const f = completedAdmissionRecoveryFixture(['complete_then_drop', 'runtime_draining'])
  t.after(() => f.destroy())
  const original = { activation_id: 'lost-original', text: 'Explain the original record', records: [] }
  const initial = await f.adapter.request(original)
  assert.deepEqual(f.protocolErrors, [])
  assert.deepEqual(f.submissions, [{ session_id: 'canonical', input_id: 'recovery-lost-original',
    text: 'Canvas context\n{"request":"Explain the original record","records":[]}' }], 'The actual submit seam must be reached before crediting a regression failure')
  assert.equal(f.native().length, 1)
  assert.equal(f.native()[0].receipt.status, 'terminal')
  assert.equal(f.native()[0].receipt.outcome, 'completed')
  assert.deepEqual(f.observed(), [])
  assert.equal(initial.status, 'unknown')
  const unresolved = f.intent(original.activation_id)
  assert.equal(unresolved.settled, false)
  f.adapter.destroy()
  const reopened = f.build()
  assert.equal((await reopened.restore()).status, 'unknown')
  assert.equal(f.submissions.length, 1, 'Reopening must not submit automatically')
  const retried = await reopened.retry()
  reopened.destroy()
  const restored = await f.build().restore()
  assert.deepEqual(f.protocolErrors, [])
  assert.equal(f.submissions.length, 2, 'The explicit retry must reach prompt.submit')
  assert.deepEqual(f.submissions[1], f.submissions[0])
  assert.deepEqual(f.lookups, [f.submissions[0].input_id], 'Retry refusal must happen before native deduplication lookup')
  assert.equal(f.native().length, 1)
  assert.equal(f.native()[0].receipt.outcome, 'completed')
  assert.deepEqual(f.observed(), [])
  assert.equal(f.posts.filter(post => post.op === 'reject').length, 0, 'A retry refusal cannot durably reject the earlier uncertain attempt')
  assert.deepEqual(f.intent(original.activation_id), unresolved)
  for (const result of [retried, restored]) {
    assert.equal(result.activationId, original.activation_id)
    assert.equal(result.status, 'unknown')
  }
  assert.ok(f.statuses.every(status => !/\bno request was admitted\b/i.test(status.message)), 'Never tell the user that the completed original request was unadmitted')
  assert.ok(!f.statuses.some(status => ['failed', 'completed'].includes(status.status)))
})

test('normal exact-ID retry after response loss recovers the original terminal receipt without another admission', async t => {
  const f = completedAdmissionRecoveryFixture(['complete_then_drop', 'deliver'])
  t.after(() => f.destroy())
  const original = { activation_id: 'recover-original', text: 'Explain the original record', records: [] }
  const initial = await f.adapter.request(original)
  assert.deepEqual(f.protocolErrors, [])
  assert.deepEqual(f.submissions, [{ session_id: 'canonical', input_id: 'recovery-recover-original',
    text: 'Canvas context\n{"request":"Explain the original record","records":[]}' }])
  assert.equal(f.native().length, 1)
  const nativeBefore = f.native()
  assert.equal(nativeBefore[0].receipt.status, 'terminal')
  assert.equal(nativeBefore[0].receipt.outcome, 'completed')
  assert.deepEqual(f.observed(), [])
  assert.equal(initial.status, 'unknown')
  assert.equal(f.intent(original.activation_id).settled, false)
  f.adapter.destroy()
  const reopened = f.build()
  assert.equal((await reopened.restore()).status, 'unknown')
  assert.equal(f.submissions.length, 1)
  const recovered = await reopened.retry()
  assert.deepEqual(f.protocolErrors, [])
  assert.equal(f.submissions.length, 2)
  assert.deepEqual(f.submissions[1], f.submissions[0])
  assert.deepEqual(f.lookups, [f.submissions[0].input_id, f.submissions[0].input_id])
  assert.deepEqual(f.native(), nativeBefore, 'Retry must recover the existing admission without creating another')
  assert.equal(recovered.activationId, original.activation_id)
  assert.equal(recovered.status, 'completed')
  assert.equal(recovered.answer, 'The original native answer.')
  assert.equal(f.statuses.at(-1).status, 'completed')
  assert.deepEqual(f.observed(), [{ admission_id: nativeBefore[0].receipt.admission_id,
    ref: nativeBefore[0].receipt.ref, status: 'terminal', outcome: 'completed' }])
  assert.equal(f.intent(original.activation_id).settled, true)
  assert.equal(f.intent(original.activation_id).admission_id, nativeBefore[0].receipt.admission_id)
  assert.equal(f.intent(original.activation_id).refusal_reason, null)
  assert.equal(f.posts.filter(post => post.op === 'reject').length, 0)
  reopened.destroy()
  const restored = await f.build().restore()
  assert.equal(restored.status, 'completed')
  assert.equal(restored.answer, recovered.answer)
  assert.equal(f.submissions.length, 2)
  assert.deepEqual(f.protocolErrors, [])
})

test('a genuine first-attempt runtime refusal settles and permits a fresh different intent', async t => {
  const f = completedAdmissionRecoveryFixture(['runtime_draining', 'deliver'])
  t.after(() => f.destroy())
  const original = { activation_id: 'first-refused', text: 'Explain the original record', records: [] }
  const refused = await f.adapter.request(original)
  assert.deepEqual(f.protocolErrors, [])
  assert.deepEqual(f.submissions, [{ session_id: 'canonical', input_id: 'recovery-first-refused',
    text: 'Canvas context\n{"request":"Explain the original record","records":[]}' }])
  assert.deepEqual(f.lookups, [])
  assert.deepEqual(f.native(), [])
  assert.deepEqual(f.observed(), [])
  assert.equal(refused.status, 'failed')
  assert.equal(f.statuses.at(-1).status, 'failed')
  assert.deepEqual(f.posts.filter(post => post.op === 'reject').map(post => post.body), [{
    activation_id: original.activation_id, input_id: f.submissions[0].input_id, reason: 'runtime_draining'
  }])
  const settled = f.intent(original.activation_id)
  assert.equal(settled.settled, true)
  assert.equal(settled.refusal_reason, 'runtime_draining')
  assert.equal(settled.admission_id, null)
  f.adapter.destroy()
  const reopened = f.build()
  assert.equal((await reopened.restore()).status, 'failed')
  assert.equal((await reopened.retry()).status, 'failed')
  assert.equal(f.submissions.length, 1, 'A settled first-attempt refusal must not be retried')
  const fresh = await reopened.request({ activation_id: 'fresh-after-draining', text: 'Summarize a different record', records: [] })
  assert.deepEqual(f.protocolErrors, [])
  assert.equal(f.submissions.length, 2)
  assert.deepEqual(f.submissions[1], { session_id: 'canonical', input_id: 'recovery-fresh-after-draining',
    text: 'Canvas context\n{"request":"Summarize a different record","records":[]}' })
  assert.notEqual(f.submissions[1].input_id, f.submissions[0].input_id)
  assert.notEqual(f.submissions[1].text, f.submissions[0].text)
  assert.equal(fresh.activationId, 'fresh-after-draining')
  assert.equal(fresh.status, 'completed')
  assert.equal(f.native().length, 1)
  assert.deepEqual(f.native()[0].params, f.submissions[1])
  assert.equal(f.intents().length, 2)
  assert.equal(f.intent('fresh-after-draining').settled, true)
  assert.deepEqual(f.intent(original.activation_id), settled)
  assert.equal(f.posts.filter(post => post.op === 'reject').length, 1)
})

test('repeated retry refusals preserve uncertainty and block a different activation from dispatching fresh native input', async t => {
  const f = completedAdmissionRecoveryFixture(['complete_then_drop', 'runtime_draining', 'runtime_draining', 'runtime_draining'])
  t.after(() => f.destroy())
  const original = { activation_id: 'repeated-loss', text: 'Explain the original record', records: [] }
  const initial = await f.adapter.request(original)
  assert.deepEqual(f.protocolErrors, [])
  assert.deepEqual(f.submissions, [{ session_id: 'canonical', input_id: 'recovery-repeated-loss',
    text: 'Canvas context\n{"request":"Explain the original record","records":[]}' }])
  assert.equal(f.native().length, 1)
  assert.equal(f.native()[0].receipt.outcome, 'completed')
  assert.deepEqual(f.observed(), [])
  assert.equal(initial.status, 'unknown')
  const unresolved = f.intent(original.activation_id)
  const nativeBefore = f.native()
  f.adapter.destroy()
  let reopened = f.build()
  const results = [await reopened.restore()]
  for (let attempt = 0; attempt < 3; attempt++) {
    results.push(await reopened.retry())
    reopened.destroy()
    reopened = f.build()
    results.push(await reopened.restore())
  }
  const submitsBeforeDifferent = copySubmissions()
  const different = await reopened.request({ activation_id: 'blocked-different', text: 'A different request must wait', records: [] })
  results.push(different)
  assert.deepEqual(f.protocolErrors, [])
  assert.equal(submitsBeforeDifferent.length, 4, 'All three explicit retries must reach prompt.submit after reopening')
  assert.ok(submitsBeforeDifferent.every(params => JSON.stringify(params) === JSON.stringify(f.submissions[0])), 'Every retry must preserve the original exact ID and text')
  assert.deepEqual(f.submissions, submitsBeforeDifferent, 'A different activation must not dispatch any fresh native input')
  assert.deepEqual(f.lookups, [f.submissions[0].input_id])
  assert.deepEqual(f.native(), nativeBefore)
  assert.deepEqual(f.observed(), [])
  assert.equal(f.posts.filter(post => post.op === 'reject').length, 0)
  assert.deepEqual(f.intents(), [unresolved])
  assert.equal(different.activationId, original.activation_id)
  for (const result of results) assert.equal(result.status, 'unknown')
  assert.ok(!f.statuses.some(status => ['failed', 'completed'].includes(status.status)))
  assert.ok(f.statuses.every(status => !/\bno request was admitted\b/i.test(status.message)))

  function copySubmissions() { return structuredClone(f.submissions) }
})
