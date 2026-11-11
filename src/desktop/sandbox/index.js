export const BRIDGE_VERSION = 1
export const WEBRTC_NOTE = 'Spaces block ordinary internet connections unless you approve a site or capability. This is not a complete block: a browser feature called WebRTC can still send data that this Space can read. It does not give the Space access to Hermes, credentials, your unapproved files or other Spaces. Only put data in a Space that you trust it to handle.'
export const OP_GRANT = Object.freeze({
  meta: null,
  'net.fetch': 'net',
  'data.query': 'data',
  'data.get': 'data',
  'data.put': 'data',
  'data.delete': 'data',
  'data.batch': 'data',
  refresh: 'refresh',
  'runs.list': null,
  log: 'logs'
})
export const MAX_REQUEST_SIZE = 1024 * 1024

export function validateRequest(message) {
  return requestError(message)?.message ?? null
}

function requestError(message) {
  if (!message || typeof message !== 'object' || Array.isArray(message)) return { code: 'invalid', message: 'request must be an object' }
  if (message.v !== BRIDGE_VERSION) return { code: 'invalid', message: 'unsupported bridge version' }
  if (!Number.isSafeInteger(message.id)) return { code: 'invalid', message: 'id must be an integer' }
  if (typeof message.op !== 'string') return { code: 'invalid', message: 'op must be a string' }
  if (!message.args || typeof message.args !== 'object' || Array.isArray(message.args)) return { code: 'invalid', message: 'args must be an object' }
  try {
    const actual = new TextEncoder().encode(JSON.stringify(message)).byteLength
    if (actual > MAX_REQUEST_SIZE) return { code: 'limit', message: 'request exceeds 1 MB', limit: MAX_REQUEST_SIZE, actual }
  } catch {
    return { code: 'invalid', message: 'request is not JSON serializable' }
  }
  return null
}

export function checkGrant(op, grants) {
  if (!Object.hasOwn(OP_GRANT, op)) return { code: 'not_granted', message: `Operation isn't available: ${op}` }
  const capability = OP_GRANT[op]
  if (capability === null) return null
  if (grants.some(g => typeof g === 'string' ? g === capability : g.capability === capability && g.status === 'granted')) return null
  return { code: 'not_granted', message: `Approve ${capability} in Permissions`, capability }
}

function parseBundle(value) {
  const sandbox = value?.sandbox
  if (!sandbox || typeof sandbox !== 'object' || Array.isArray(sandbox) ||
      Object.keys(sandbox).length !== 2 || !Object.hasOwn(sandbox, 'format') || !Object.hasOwn(sandbox, 'shell_srcdoc') ||
      sandbox.format !== 1 || typeof sandbox.shell_srcdoc !== 'string' || !sandbox.shell_srcdoc.trim()) {
    throw new Error('Living Spaces Desktop and backend are incompatible. Reinstall Living Spaces to load the packaged sandbox.')
  }
  const { space, rev, manifest, files } = value
  return { project: { space, rev, manifest, files }, document: sandbox.shell_srcdoc }
}

export function mountSpace(container, { bundle, grants = [], call, onEvent = () => {} }) {
  const { project, document: shellDocument } = parseBundle(bundle)
  const channel = new MessageChannel()
  const port = channel.port1
  let frame
  let state = 'created'
  let lastLog = -Infinity
  let overflowReported = false
  const overflow = () => {
    if (overflowReported) return
    overflowReported = true
    onEvent({ kind: 'log-overflow' })
  }
  const stop = () => {
    if (state === 'closed') return
    state = 'closed'
    frame?.removeEventListener('load', onLoad)
    port.onmessage = null
    port.close()
    channel.port2.close()
    window.removeEventListener('message', onShellMessage)
  }
  const reloaded = () => {
    if (state !== 'booted') return
    stop()
    onEvent({ kind: 'reloaded' })
  }
  function onShellMessage(e) {
    if (e.source === frame.contentWindow && e.data?.v === 1 && e.data.type === 'space-reloaded') reloaded()
  }
  function onLoad() {
    if (state === 'closed') return
    if (state === 'booted') return reloaded()
    state = 'booted'
    frame.contentWindow.postMessage({ type: 'space-boot', v: 1, bundle: project, grants }, '*', [channel.port2])
    onEvent({ kind: 'booted' })
  }
  port.onmessage = async e => {
    if (state !== 'booted') return
    const m = e.data
    const reply = body => {
      if (state === 'booted' && Number.isSafeInteger(m?.id)) port.postMessage({ v: 1, id: m.id, ...body })
    }
    const reject = error => {
      const op = typeof m?.op === 'string' ? m.op : null
      onEvent({ kind: 'denied', op, reason: error.message })
      if (['data.put', 'data.delete', 'data.batch'].includes(op)) onEvent({ kind: 'write-rejected', op, error })
      reply({ ok: false, error })
    }
    const invalid = requestError(m)
    if (invalid) return reject(invalid)
    const denied = checkGrant(m.op, grants)
    if (denied) return reject(denied)
    let args = m.args
    if (m.op === 'log') {
      if (!Array.isArray(args.entries) || Array.from(args.entries).some(entry =>
        !entry || typeof entry.level !== 'string' || typeof entry.msg !== 'string')) {
        return reject({ code: 'invalid', message: 'Invalid log entries' })
      }
      if (args.entries.length > 50) return reject({ code: 'limit', message: 'Log batch exceeds 50 entries', limit: 50, actual: args.entries.length })
      const oversized = args.entries.find(entry => entry.msg.length > 4000)
      if (oversized) return reject({ code: 'limit', message: 'Log message exceeds 4000 characters', limit: 4000, actual: oversized.msg.length })
      if (args.entries.some(entry => entry.level === 'warn' && entry.msg.startsWith('Space log overflow:'))) overflow()
      const now = performance.now()
      if (now - lastLog < 500) {
        overflow()
        reply({ ok: true, result: { stored: 0 } })
        return
      }
      lastLog = now
      args = { entries: args.entries }
    }
    try {
      const result = await call(m.op, args)
      const revoked = checkGrant(m.op, grants)
      if (revoked && result.ok) reject(revoked)
      else reply(result)
    } catch (error) {
      onEvent({ kind: 'error', message: String(error.message || error) })
      reply({ ok: false, error: { code: error.code || 'blocked', message: String(error.message || error) } })
    }
  }
  try {
    frame = document.createElement('iframe')
    frame.setAttribute('sandbox', 'allow-scripts')
    frame.setAttribute('referrerpolicy', 'no-referrer')
    frame.style.cssText = 'border:0;width:100%;height:100%;display:block;background:transparent'
    frame.title = `Space: ${project.space.name}`
    window.addEventListener('message', onShellMessage)
    frame.addEventListener('load', onLoad)
    frame.srcdoc = shellDocument
    container.append(frame)
  } catch (error) {
    stop()
    frame?.remove()
    throw error
  }
  return {
    postEvent(event, payload) {
      if (state !== 'booted') return
      if (event === 'data.changed' && checkGrant('data.query', grants)) return
      port.postMessage({ v: 1, type: 'event', event, payload })
      if (event === 'session.closed') stop()
    },
    destroy() {
      stop()
      frame.remove()
    }
  }
}
