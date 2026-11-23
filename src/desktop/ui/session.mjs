import { spacePath } from './model.mjs'
import { createBotActions, profileRoute } from './actions.mjs'
import { linkTarget } from '../sandbox/index.js'

const errorCode = error => [error?.error?.code, error?.body?.error?.code, error?.message, String(error)].filter(Boolean).join(' ')
const freezeDraft = value => {
  if (value && typeof value === 'object') { Object.values(value).forEach(freezeDraft); Object.freeze(value) }
  return value
}
const requestId = () => 'write_' + Array.from(crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2, '0')).join('')

let desktopOs = null
export function bindDesktopOs(os) { desktopOs = os ?? null }
const hasActivation = () => globalThis.navigator?.userActivation?.isActive === true

export function createSpaceSession({ rest, backend, sid, container, mount, onEvent, host, os = desktopOs, userActivation = hasActivation, onAction = () => {}, onWrite = () => {}, onCloseError = error => console.warn('Space session cleanup failed', error) }) {
  const base = spacePath(sid)
  const scope = backend ? Object.freeze({ connectionId: backend.connectionId, profile: backend.profile }) : null
  const active = () => !scope || (host?.state?.connectionId?.get() === scope.connectionId && host?.state?.profile?.get() === scope.profile)
  const requireActive = () => { if (!active()) throw new Error('The active backend changed. Reopen this Space.') }
  const scopedRequest = async (path, options) => {
    requireActive()
    const value = await rest(path, options)
    requireActive()
    return value
  }
  let closed = false
  let session = null
  let mounted = null
  let closePromise = null
  let nextWrite = 0
  let pendingWrites = 0
  let editorWrite = null
  const failures = new Map()
  const retries = new Map()
  const publish = event => { if (!closed && active()) onWrite(failures.values().next().value || (pendingWrites ? { status: 'saving' } : event)) }
  // Statuses published while the user's own bot call runs are marked for the host banner, so a
  // dismissal can never hide what the user just caused. The guest sees the status unchanged.
  let userCalls = 0
  const byUser = async work => { userCalls++; try { return await work() } finally { userCalls-- } }
  const actions = host ? createBotActions({ host, backend: scope, isActive: () => !closed && active(),
    post: (operation, body) => scopedRequest(`${base}/actions/${operation}`, { method: 'POST', body: { ...body, session } }),
    onStatus: status => {
      if (closed) return
      onAction(userCalls ? { ...status, userInitiated: true } : status)
      mounted?.postEvent?.('bot.status', status)
    }
  }) : null
  const linkNotice = `living-spaces:link:${sid}`
  let linkGeneration = null
  const showNotice = (input, label, run) => {
    const generation = linkGeneration = {}
    const action = run && { label, onClick: () => { if (linkGeneration === generation && !closed && active()) run() } }
    host.notify({ id: linkNotice, ...input, action })
  }
  const openLink = args => {
    if (!userActivation()) return { ok: false, error: { code: 'blocked', message: 'Links open only from a click in the Space. Nothing was opened.' } }
    if (!args || Object.keys(args).length !== 1 || typeof args.url !== 'string') return { ok: false, error: { code: 'invalid', message: 'A link request needs exactly one url' } }
    if (typeof os?.openExternal !== 'function' || typeof host?.notify !== 'function') return { ok: false, error: { code: 'blocked', message: 'This Desktop cannot open links from a Space' } }
    const target = linkTarget(args.url)
    if (!target.ok) {
      showNotice({ kind: 'warning', title: 'Link not opened', message: target.reason })
      return { ok: false, error: { code: 'invalid', message: target.reason } }
    }
    showNotice({ kind: 'info', title: `Open ${target.host} in your browser?`, message: target.url,
      detail: 'This Space asked to open the link above outside Hermes.', durationMs: 15000 }, 'Open link', async () => {
      const handoff = linkGeneration = {}
      const opened = await os.openExternal(target.url).catch(() => false)
      if (opened === true || linkGeneration !== handoff || closed || !active()) return
      showNotice({ kind: 'error', title: 'Your browser could not open this link', message: target.url,
        detail: 'Nothing was opened. Copy the link to open it yourself.' }, 'Copy link', () => { os.writeClipboard?.(target.url)?.catch?.(() => {}) })
    })
    return { ok: true, result: { status: 'confirming', url: target.url, host: target.host } }
  }
  const close = () => {
    if (!session) return Promise.resolve()
    closePromise ??= (async () => {
      for (let attempt = 1; attempt <= 3; attempt++) {
        try {
          if (active()) return await rest(`${base}/sessions/${encodeURIComponent(session)}`, { method: 'DELETE', timeoutMs: 5000 })
          const route = await profileRoute(host, scope)
          const identity = await host.requestProfile(route, 'runtime.describe', {}, 5000)
          if (!identity?.capabilities?.includes('plugin-rpc-v1')) {
            throw Object.assign(new Error('The owning gateway does not advertise plugin-rpc-v1, so this Space session stays open until the Space is archived or deleted'), { final: true })
          }
          const result = await host.requestProfile(route, 'plugin.living-spaces.close_session', { space_id: sid, session }, 5000)
          if (result?.closed !== true) throw new Error(result?.error?.message || 'Space session cleanup was not confirmed')
          return result
        } catch (error) {
          // Archive and delete close sessions on the server first, so the session is already gone.
          if (/session_invalid/.test(errorCode(error))) return { closed: true }
          onCloseError(error)
          if (attempt === 3 || error.final) throw error
          await new Promise(resolve => setTimeout(resolve, 250 * attempt))
        }
      }
    })().catch(error => { closePromise = null; throw error })
    return closePromise
  }
  const invalidSession = () => ({ ok: false, error: { code: 'session_invalid', message: 'This Space session is closed' } })
  const send = async body => {
    try {
      return await scopedRequest(`${base}/bridge`, { method: 'POST', body })
    } catch (error) {
      const reply = error?.body || error
      if (reply?.outcome?.status) return reply
      return { ok: false, error: { code: 'unavailable', message: error.message || String(error) }, outcome: { status: 'unknown' } }
    }
  }
  const finishWrite = (attempt, reply, lookup = false) => {
    const certainty = reply?.outcome?.status
    const saved = reply?.ok === true && (certainty == null || ['success', 'confirmed'].includes(certainty)) && (!lookup || ['success', 'confirmed'].includes(certainty))
    const status = certainty === 'unknown' || (lookup && !saved) ? 'unknown' : saved ? 'saved' : certainty !== 'busy' && reply?.error?.code === 'conflict' ? 'conflict' : 'failed'
    attempt.unknown = status === 'unknown'
    if (saved) attempt.confirmed = reply
    const retry = next => {
      if (closed || !active()) return Promise.resolve(invalidSession())
      if (retries.has(attempt.token)) return retries.get(attempt.token)
      let current = attempt
      while (current.next) current = current.next   // latest attempt for this token, as the old token map gave
      if (current.confirmed) return Promise.resolve(current.confirmed)
      const promise = (current.unknown ? reconcile(current) : call(current.op, next || current.args, current.token, undefined, current))
        .finally(() => retries.delete(attempt.token))
      retries.set(attempt.token, promise)
      return promise
    }
    const event = { ...(attempt.op === 'editor.save' ? { editorManaged: true } : {}), status, token: attempt.token, op: attempt.op, args: attempt.args, reply, at: Date.now() / 1000, retry }
    editorWrite = event.editorManaged ? attempt : null
    if (saved || event.editorManaged) failures.delete(attempt.token)
    else failures.set(attempt.token, event)
    publish(event)
  }
  const reconcile = async attempt => {
    if (closed || !active()) return invalidSession()
    pendingWrites++
    const reply = await send({ session: attempt.session, op: 'outcome.get', args: { request_id: attempt.request_id } })
    pendingWrites--
    if (closed || !active()) return invalidSession()
    finishWrite(attempt, reply, true)
    return reply
  }
  const call = async (op, args, retryToken, editorRequestId, supersedes) => {
    if (closed || !active()) return invalidSession()
    if (op === 'link.open') return openLink(args)
    if (op === 'bot.request') {
      if (!actions) return { ok: false, error: { code: 'blocked', message: 'Native bot actions are unavailable' } }
      const result = await byUser(() => actions.request(args))
      if (closed || !active()) return invalidSession()
      return { ok: true, result }
    }
    const writing = ['data.put', 'data.delete', 'data.batch', 'editor.save'].includes(op)
    let attempt
    if (writing) {
      args = structuredClone(args)
      const identify = put => {
        if (put.id == null) {
          put.id = 'r_' + Array.from(crypto.getRandomValues(new Uint8Array(6)), byte => byte.toString(16).padStart(2, '0')).join('')
          put.base_rev = 0
        }
      }
      if (retryToken == null && op === 'data.put') identify(args)
      if (retryToken == null && op === 'data.batch' && Array.isArray(args.ops)) args.ops.forEach(item => { if (item?.op === 'put') identify(item) })
      attempt = { token: retryToken ?? ++nextWrite, op, args: freezeDraft(args), session, request_id: op === 'editor.save' ? editorRequestId : requestId(), unknown: false }
      // Superseded attempts point forward to their replacement, so a held retry closure still resolves the latest
      // attempt. No session-wide map: an attempt (cloned args and reply) lives only while some event closure holds it.
      if (supersedes) supersedes.next = attempt
      pendingWrites++
      publish({ status: 'saving', op, args })
    }
    const reply = await send({ session, op, args, ...(attempt ? { request_id: attempt.request_id } : {}) })
    if (writing) pendingWrites--
    if (closed || !active()) return invalidSession()
    if (attempt) finishWrite(attempt, reply)
    else if (editorWrite && args.editor === editorWrite.args.editor && args.schema === editorWrite.args.schema &&
        args.collection === editorWrite.args.collection && args.id === editorWrite.args.id) {
      if (op === 'outcome.get' && args.request_id === editorWrite.request_id) finishWrite(editorWrite, reply, true)
      else if (op === 'draft.delete' && reply.ok) { editorWrite = null; publish(null) }
    }
    return reply
  }
  const ready = (async () => {
    requireActive()
    const opened = await rest(`${base}/sessions`, { method: 'POST' })
    session = opened.session
    if (closed || !active()) { closed = true; return close() }
    try {
      const bundle = await scopedRequest(`${base}/bundle`)
      if (closed) return close()
      if (bundle.rev !== opened.head_rev) throw new Error('The Space changed while opening. Reload Space to open the current revision.')
      mounted = mount(container, { bundle, grants: opened.grants, call, onEvent: event => {
        if (closed || !active()) return
        if (event.kind === 'write-rejected' && ['data.put', 'data.delete', 'data.batch'].includes(event.op)) {
          const failure = { status: 'failed', token: ++nextWrite, op: event.op, reply: { ok: false, error: event.error } }
          failures.set(failure.token, failure)
          publish(failure)
        }
        onEvent(event)
      } })
      actions?.restore()
    } catch (error) {
      closed = true
      await close().catch(() => {})
      throw error
    }
  })()
  return {
    ready,
    async snapshot(options) {
      if (closed || !active() || !mounted) return null
      try {
        const result = await mounted.snapshot(options)
        return closed || !active() ? null : result
      } catch { return null }
    },
    checkAction() { return actions && byUser(() => actions.check()) },
    openLink(url) { return openLink({ url }) },
    canContinue() { return !!actions?.sessionId() && typeof host?.openSession === 'function' },
    continueInChat() {
      const id = actions?.sessionId()
      if (!id || typeof host?.openSession !== 'function') return false
      return host.openSession(id)
    },
    retryAction() { return actions && byUser(() => actions.retry()) },
    dismissWrite(token) { failures.delete(token); publish(null) },
    postEvent(event, payload) { if (!closed && active()) mounted?.postEvent?.(event, payload) },
    destroy() {
      closed = true
      actions?.destroy()
      mounted?.destroy()
      mounted = null
      return close()
    }
  }
}
