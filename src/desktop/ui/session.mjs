import { spacePath } from './model.mjs'

export function createSpaceSession({ rest, sid, container, mount, onEvent, onWrite = () => {}, onCloseError = () => {} }) {
  const base = spacePath(sid)
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
    closePromise ??= rest(`${base}/sessions/${encodeURIComponent(session)}`, { method: 'DELETE' }).catch(onCloseError)
    return closePromise
  }
  const call = async (op, args, retryToken) => {
    if (closed) return { ok: false, error: { code: 'session_invalid', message: 'This Space session is closed' } }
    const writing = ['data.put', 'data.delete', 'data.batch'].includes(op)
    const token = retryToken ?? ++nextWrite
    if (writing) { pendingWrites++; publish({ status: 'saving', op, args }) }
    let reply
    try {
      reply = await rest(`${base}/bridge`, { method: 'POST', body: { session, op, args } })
    } catch (error) {
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
      const event = { status: reply.ok ? 'saved' : reply.error?.code === 'conflict' ? 'conflict' : 'failed', token, op, args, reply, at: Date.now() / 1000, retry }
      if (reply.ok) failures.delete(token)
      else failures.set(token, event)
      publish(event)
    }
    return reply
  }
  const ready = (async () => {
    const opened = await rest(`${base}/sessions`, { method: 'POST' })
    session = opened.session
    if (closed) return close()
    try {
      const bundle = await rest(`${base}/bundle`)
      if (closed) return close()
      if (bundle.rev !== opened.head_rev) throw new Error('The Space changed while opening. Reload Space to open the current revision.')
      mounted = mount(container, { bundle, grants: opened.grants, call, onEvent: event => !closed && onEvent(event) })
    } catch (error) {
      closed = true
      await close()
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
