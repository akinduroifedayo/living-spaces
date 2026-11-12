import { spacePath } from './model.mjs'
import { createBotActions, profileRoute } from './actions.mjs'

const errorCode = error => [error?.error?.code, error?.body?.error?.code, error?.message, String(error)].filter(Boolean).join(' ')

export function createSpaceSession({ rest, backend, sid, container, mount, onEvent, host, onAction = () => {}, onWrite = () => {}, onCloseError = error => console.warn('Space session cleanup failed', error) }) {
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
  const failures = new Map()
  const retries = new Map()
  const publish = event => onWrite(failures.values().next().value || (pendingWrites ? { status: 'saving' } : event))
  const actions = host ? createBotActions({ host, backend: scope, isActive: () => !closed && active(),
    post: (operation, body) => scopedRequest(`${base}/actions/${operation}`, { method: 'POST', body: { ...body, session } }),
    onStatus: status => {
      if (closed) return
      onAction(status)
      mounted?.postEvent?.('bot.status', status)
    }
  }) : null
  const close = () => {
    if (!session) return Promise.resolve()
    closePromise ??= (async () => {
      for (let attempt = 1; attempt <= 3; attempt++) {
        try {
          if (active()) return await rest(`${base}/sessions/${encodeURIComponent(session)}`, { method: 'DELETE', timeoutMs: 5000 })
          const route = await profileRoute(host, scope)
          const result = await host.requestProfile(route, 'plugin.living-spaces.close_session', { space_id: sid, session }, 5000)
          if (result?.closed !== true) throw new Error(result?.error?.message || 'Space session cleanup was not confirmed')
          return result
        } catch (error) {
          // Archive and delete close sessions on the server first, so the session is already gone.
          if (/session_invalid/.test(errorCode(error))) return { closed: true }
          onCloseError(error)
          if (attempt === 3) throw error
          await new Promise(resolve => setTimeout(resolve, 250 * attempt))
        }
      }
    })().catch(error => { closePromise = null; throw error })
    return closePromise
  }
  const call = async (op, args, retryToken) => {
    if (closed || !active()) return { ok: false, error: { code: 'session_invalid', message: 'This Space session is closed' } }
    if (op === 'bot.request') {
      if (!actions) return { ok: false, error: { code: 'blocked', message: 'Native bot actions are unavailable' } }
      const result = await actions.request(args)
      if (closed || !active()) return { ok: false, error: { code: 'session_invalid', message: 'This Space session is closed' } }
      return { ok: true, result }
    }
    const writing = ['data.put', 'data.delete', 'data.batch'].includes(op)
    if (writing && retryToken == null) {
      args = structuredClone(args)
      const identify = put => {
        if (put.id == null) {
          put.id = 'r_' + Array.from(crypto.getRandomValues(new Uint8Array(6)), byte => byte.toString(16).padStart(2, '0')).join('')
          put.base_rev = 0
        }
      }
      if (op === 'data.put') identify(args)
      if (op === 'data.batch' && Array.isArray(args.ops)) args.ops.forEach(item => { if (item?.op === 'put') identify(item) })
    }
    const token = retryToken ?? ++nextWrite
    if (writing) { pendingWrites++; publish({ status: 'saving', op, args }) }
    let reply
    let unknown = false
    try {
      reply = await scopedRequest(`${base}/bridge`, { method: 'POST', body: { session, op, args } })
    } catch (error) {
      unknown = true
      reply = { ok: false, error: { code: 'unavailable', message: error.message || String(error) } }
    }
    if (closed || !active()) return { ok: false, error: { code: 'session_invalid', message: 'This Space session is closed' } }
    if (writing) {
      pendingWrites--
      const retry = next => {
        if (retries.has(token)) return retries.get(token)
        const promise = call(op, next || args, token).finally(() => retries.delete(token))
        retries.set(token, promise)
        return promise
      }
      unknown ||= failures.get(token)?.status === 'unknown'
      const event = { status: reply.ok ? 'saved' : reply.error?.code === 'conflict' ? 'conflict' : unknown ? 'unknown' : 'failed', token, op, args, reply, at: Date.now() / 1000, retry }
      if (reply.ok) failures.delete(token)
      else failures.set(token, event)
      publish(event)
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
    checkAction() { return actions?.check() },
    retryAction() { return actions?.retry() },
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
