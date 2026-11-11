import { spacePath } from './model.mjs'

const errorCode = error => [error?.error?.code, error?.body?.error?.code, error?.message, String(error)].filter(Boolean).join(' ')

export function createSpaceSession({ rest, backend, sid, container, mount, onEvent, onWrite = () => {}, onCloseError = error => console.warn('Space session cleanup failed', error) }) {
  const base = spacePath(sid)
  const { api, connectionId, profile } = backend || {}
  const lifecycleRest = api ? (path, options = {}) => api({ ...options, path: `/api/plugins/living-spaces${path}`, connectionId, profile, timeoutMs: options.method === 'DELETE' ? 5000 : undefined }) : rest
  let closed = false
  let session = null
  let mounted = null
  let closePromise = null
  let nextWrite = 0
  let pendingWrites = 0
  const failures = new Map()
  const retries = new Map()
  const publish = event => onWrite(failures.values().next().value || (pendingWrites ? { status: 'saving' } : event))
  const close = () => {
    if (!session) return Promise.resolve()
    closePromise ??= (async () => {
      for (let attempt = 1; attempt <= 3; attempt++) {
        try {
          return await lifecycleRest(`${base}/sessions/${encodeURIComponent(session)}`, { method: 'DELETE' })
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
    if (closed) return { ok: false, error: { code: 'session_invalid', message: 'This Space session is closed' } }
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
      reply = await rest(`${base}/bridge`, { method: 'POST', body: { session, op, args } })
    } catch (error) {
      unknown = true
      reply = { ok: false, error: { code: 'unavailable', message: error.message || String(error) } }
    }
    if (closed) return { ok: false, error: { code: 'session_invalid', message: 'This Space session is closed' } }
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
    const opened = await lifecycleRest(`${base}/sessions`, { method: 'POST' })
    session = opened.session
    if (closed) return close()
    try {
      const bundle = await lifecycleRest(`${base}/bundle`)
      if (closed) return close()
      if (bundle.rev !== opened.head_rev) throw new Error('The Space changed while opening. Reload Space to open the current revision.')
      mounted = mount(container, { bundle, grants: opened.grants, call, onEvent: event => {
        if (closed) return
        if (event.kind === 'write-rejected' && ['data.put', 'data.delete', 'data.batch'].includes(event.op)) {
          const failure = { status: 'failed', token: ++nextWrite, op: event.op, reply: { ok: false, error: event.error } }
          failures.set(failure.token, failure)
          publish(failure)
        }
        onEvent(event)
      } })
    } catch (error) {
      closed = true
      await close().catch(() => {})
      throw error
    }
  })()
  return {
    ready,
    dismissWrite(token) { failures.delete(token); publish(null) },
    postEvent(event, payload) { if (!closed) mounted?.postEvent?.(event, payload) },
    destroy() {
      closed = true
      mounted?.destroy()
      mounted = null
      return close()
    }
  }
}
