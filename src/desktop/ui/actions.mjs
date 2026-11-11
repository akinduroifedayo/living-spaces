const routeFields = ['connectionId', 'profile', 'targetProfile', 'mode']
const sameRoute = (a, b) => routeFields.every(key => a?.[key] === b?.[key])
const publicStatus = (action, status, message, answer) => ({ activationId: action?.activation_id, status, message, ...(answer ? { answer } : {}) })
const failure = (message, status = 'failed') => Object.assign(new Error(message), { actionStatus: status })
const refusalReasons = new Set(['permission_denied', 'invalid_params', 'not_found', 'profile_mismatch', 'queue_full', 'runtime_draining'])

export function createBotActions({ host, backend, post, onStatus, isActive, userActivation = () => globalThis.navigator?.userActivation?.isActive === true }) {
  let current = null
  let binding = null
  let release = null
  let heldRoute = null
  let timer = null
  let closed = false
  let requestInFlight = null
  let chain = Promise.resolve()
  const alive = () => {
    if (closed || !isActive()) throw failure('This Space view is closed', 'unknown')
  }
  const publish = value => {
    if (!closed && isActive()) onStatus(value)
    return value
  }
  const serial = work => {
    const next = chain.then(work)
    chain = next.catch(() => {})
    return next
  }
  const pinned = route => route.profile === backend?.profile &&
    (backend.connectionId == null ? route.primary === true : route.connectionId === backend.connectionId)
  async function registered(expected) {
    alive()
    if (!backend?.api || typeof host?.profileRoutes !== 'function' || typeof host?.retainProfile !== 'function' || typeof host?.requestProfile !== 'function') {
      throw failure('Native profile routing is unavailable in this Desktop', 'offline')
    }
    const routes = await host.profileRoutes()
    alive()
    const matches = routes.filter(route => pinned(route) && (!expected || sameRoute(route, expected)))
    if (matches.length !== 1 || routeFields.some(key => typeof matches[0][key] !== 'string' || !matches[0][key])) {
      throw failure('The exact maintaining profile route is unavailable or ambiguous', 'offline')
    }
    return matches[0]
  }
  async function rpc(route, method, params = {}) {
    const fresh = await registered(route)
    alive()
    const value = await host.requestProfile(fresh, method, params).catch(error => {
      const reason = error?.data?.reason
      if (method === 'prompt.submit' && refusalReasons.has(reason)) {
        throw Object.assign(failure(`Native request refused: ${reason}`), { refusalReason: reason })
      }
      if (['permission_denied', 'invalid_params', 'not_found', 'profile_mismatch'].includes(reason)) {
        throw failure(`Native request refused: ${reason}`)
      }
      if (reason === 'admission_conflict') throw failure('Native admission identity is conflicted; admission may already exist', 'unknown')
      if (reason === 'runtime_draining') throw failure('The native runtime is busy shutting down', 'busy')
      throw error
    })
    alive()
    return value
  }
  async function connect(target) {
    const route = await registered(target?.route)
    if (!heldRoute || !sameRoute(route, heldRoute)) {
      release?.(); release = null; heldRoute = null
      const lease = await host.retainProfile(route, { spawnPriority: 'foreground' })
      if (closed || !isActive()) { lease(); alive() }
      release = lease
      heldRoute = route
    }
    const identity = await rpc(route, 'runtime.describe')
    if (identity.profile_id !== binding.profile_id || !identity.capabilities?.includes('durable-admission-v1')) {
      throw failure('Native profile identity does not match this Space’s maintaining bot')
    }
    return route
  }
  async function context(activationId) {
    alive()
    const value = await post('context', activationId ? { activation_id: activationId } : {})
    alive()
    binding = value.maintainer
    return value.action
  }
  function validateReceipt(receipt) {
    if (!receipt || typeof receipt.admission_id !== 'string' || !receipt.admission_id ||
        receipt.ref?.profile_id !== current.target.profile_id || receipt.ref?.session_id !== current.target.session_id ||
        (current.admission_id && receipt.admission_id !== current.admission_id) ||
        !['queued', 'started', 'unknown', 'terminal'].includes(receipt.status)) {
      throw failure('Native admission outcome could not be correlated', 'unknown')
    }
  }
  async function observe(receipt) {
    validateReceipt(receipt)
    current.admission_id = receipt.admission_id
    const recorded = await post('observe', { activation_id: current.activation_id, receipt: {
      admission_id: receipt.admission_id, ref: receipt.ref, status: receipt.status, outcome: receipt.outcome
    } })
    alive()
    const settled = recorded.settled && receipt.status === 'terminal'
    current.settled = settled
    let status = { queued: 'queued', started: 'busy', unknown: 'unknown' }[receipt.status] || 'unknown'
    let message = { queued: 'Queued for the maintaining bot. Uses model calls.', busy: 'The maintaining bot is working.', unknown: 'Native outcome is unknown. No automatic resend.' }[status]
    let answer
    if (settled) {
      status = receipt.outcome === 'completed' ? 'completed' : 'failed'
      message = status === 'completed' ? 'The maintaining bot completed this request.' : `Native request ${receipt.outcome}.`
      const text = receipt.result?.final_response
      if (typeof text === 'string') {
        if (new TextEncoder().encode(text).length <= 16384) answer = text
        else message += ' The answer exceeds the 16 KiB canvas display limit; read it in the native conversation.'
      }
      release?.(); release = null; heldRoute = null
    }
    const value = publish(publicStatus(current, status, message, answer))
    if (!settled && status !== 'unknown') schedule()
    return value
  }
  function schedule() {
    clearTimeout(timer)
    if (!closed) timer = setTimeout(() => { serial(check).catch(report) }, 2000)
  }
  function report(error) {
    release?.(); release = null; heldRoute = null
    const status = error.actionStatus || (current ? 'unknown' : 'offline')
    return publish(publicStatus(current, status, `${error.message || 'Native request unavailable'}. No automatic resend.`))
  }
  async function attach(route, sessionId) {
    const resumed = await rpc(route, 'session.resume', { session_id: sessionId, omit_messages: true })
    if (typeof resumed.session_id !== 'string' || !resumed.session_id || resumed.session_id !== resumed.stored_session_id) {
      throw failure('This native session does not provide canonical durable admission')
    }
    return resumed
  }
  async function check() {
    clearTimeout(timer)
    current = await context(current?.activation_id)
    if (!current) return null
    if (current.refusal_reason) return publish(publicStatus(current, 'failed', `Native request refused: ${current.refusal_reason}. No request was admitted.`))
    const route = await connect(current.target)
    const resumed = await attach(route, current.target.session_id)
    if (resumed.session_id !== current.target.session_id) throw failure('The native activation target changed', 'unknown')
    if (!current.admission_id) {
      const pending = resumed.pending?.find(item => item.input_id === current.input_id)
      if (!pending) return publish(publicStatus(current, 'unknown', 'Admission was not observed. Check again or explicitly retry this same request.'))
      await observe(pending)
    }
    const receipt = await rpc(route, 'prompt.receipt', { session_id: current.target.session_id, admission_id: current.admission_id, include_result: true })
    return observe(receipt)
  }
  async function submit(route, attempt) {
    const identity = await rpc(route, 'runtime.describe')
    if (identity.profile_id !== current.target.profile_id) throw failure('Maintaining profile changed before submission', 'unknown')
    alive()
    publish(publicStatus(current, 'submitted', 'Requesting native admission. Uses model calls.'))
    let receipt
    try {
      receipt = await rpc(route, 'prompt.submit', {
        session_id: current.target.session_id, input_id: current.input_id, text: current.text
      })
    } catch (error) {
      if (!error.refusalReason) throw error
      alive()
      if (attempt === 'retry') throw failure(`${error.message}. The earlier admission remains unknown`, 'unknown')
      try {
        const recorded = await post('reject', {
          activation_id: current.activation_id, input_id: current.input_id, reason: error.refusalReason
        })
        alive()
        if (!recorded.recorded || !recorded.settled || !recorded.action?.settled ||
            recorded.action.activation_id !== current.activation_id || recorded.action.input_id !== current.input_id ||
            recorded.action.admission_id !== null || recorded.action.refusal_reason !== error.refusalReason) {
          throw new Error('The refusal record did not match this activation')
        }
        current = recorded.action
      } catch (persistenceError) {
        throw failure(`${error.message}. Refusal persistence could not be confirmed: ${persistenceError.message}`)
      }
      throw error
    }
    return observe(receipt)
  }
  return {
    restore: () => serial(check).catch(report),
    check: () => serial(check).catch(report),
    request(args) {
      if (!userActivation()) return Promise.resolve(publish(publicStatus(null, 'failed', 'Bot requests need a current user activation. No request was sent.')))
      const payload = JSON.stringify({ text: args.text, records: args.records || [] }, ['text', 'records', 'collection', 'id'])
      if (requestInFlight) {
        const conflict = requestInFlight.activationId === args.activation_id && requestInFlight.payload !== payload
        return Promise.resolve(publish(publicStatus(args, conflict ? 'failed' : 'busy', conflict
          ? 'This activation ID already belongs to a different request. No request was sent.'
          : 'An earlier request is already being handled. This activation did not send a new request.')))
      }
      requestInFlight = { activationId: args.activation_id, payload }
      return serial(async () => {
        clearTimeout(timer)
        current = await context()
        const route = await connect(current?.target)
        const resumed = await attach(route, current?.target.session_id || binding.stored_session_id)
        if (current && resumed.session_id !== current.target.session_id) throw failure('The native activation target changed', 'unknown')
        const target = current?.target || { route: Object.fromEntries(routeFields.map(key => [key, route[key]])), profile_id: binding.profile_id, session_id: resumed.session_id }
        const claim = await post('claim', { ...args, records: args.records || [], target }).catch(error => { throw failure(error.message || 'The activation was rejected') })
        alive()
        current = claim.action
        if (!claim.dispatch) {
          const status = await check()
          return claim.coalesced ? publish({ ...status, message: `An earlier request is already pending or finished. This activation did not send a new request. ${status.message}` }) : status
        }
        return submit(route, 'initial')
      }).catch(report).finally(() => { requestInFlight = null })
    },
    retry() {
      if (!userActivation()) return Promise.resolve(publish(publicStatus(current, 'failed', 'Activate Retry to request native admission again.')))
      return serial(async () => {
        const status = await check()
        if (!current || current.admission_id || current.settled) return status
        const route = await connect(current.target)
        return submit(route, 'retry')
      }).catch(report)
    },
    destroy() {
      closed = true
      clearTimeout(timer)
      release?.(); release = null; heldRoute = null
    }
  }
}
