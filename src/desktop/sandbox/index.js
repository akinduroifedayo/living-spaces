import { spaceLoader, projectResolver } from './loader.js'

export const BRIDGE_VERSION = 1
export const WEBRTC_NOTE = 'Spaces block ordinary internet connections unless you approve a site or capability. This is not a complete block: a browser feature called WebRTC can still send data that this Space can read. It does not give the Space access to Hermes, credentials, your unapproved files or other Spaces. Only put data in a Space that you trust it to handle.'
export const OP_GRANT = Object.freeze({
  meta: null,
  'data.query': 'data',
  'data.get': 'data',
  'data.put': 'data',
  'data.delete': 'data',
  'data.batch': 'data',
  refresh: 'refresh',
  'runs.list': null,
  log: 'logs'
})
export const SPACE_CSP = "default-src 'none'; script-src 'unsafe-inline' 'unsafe-eval' blob:; style-src 'unsafe-inline' blob:; img-src blob: data:; font-src blob: data:; media-src blob: data:; worker-src blob:; connect-src 'none'; frame-src 'none'; form-action 'none'; base-uri 'none'; object-src 'none'; manifest-src 'none'; webrtc 'block'"
// The shell's policy is the inner frame's immutable navigation floor.
export const SHELL_CSP = SPACE_CSP
export const MAX_REQUEST_SIZE = 1024 * 1024

export function validateRequest(message) {
  if (!message || typeof message !== 'object' || Array.isArray(message)) return 'request must be an object'
  if (message.v !== BRIDGE_VERSION) return 'unsupported bridge version'
  if (!Number.isSafeInteger(message.id)) return 'id must be an integer'
  if (typeof message.op !== 'string') return 'op must be a string'
  if (!message.args || typeof message.args !== 'object' || Array.isArray(message.args)) return 'args must be an object'
  try {
    if (JSON.stringify(message).length > MAX_REQUEST_SIZE) return 'request exceeds 1 MB'
  } catch {
    return 'request is not JSON serializable'
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

function shellRelay(spaceSrcdoc) {
  window.addEventListener('message', function onBoot(e) {
    if (e.source !== window.parent || e.data?.type !== 'space-boot' || e.data.v !== 1 || !e.ports[0]) return
    window.removeEventListener('message', onBoot)
    const f = document.createElement('iframe')
    f.setAttribute('sandbox', 'allow-scripts')
    f.setAttribute('referrerpolicy', 'no-referrer')
    f.style.cssText = 'border:0;width:100%;height:100%;display:block'
    f.title = 'Space'
    let booted = false
    f.addEventListener('load', () => {
      if (booted) {
        window.parent.postMessage({ type: 'space-reloaded', v: 1 }, '*')
        return
      }
      booted = true
      f.contentWindow.postMessage(e.data, '*', [e.ports[0]])
    })
    f.srcdoc = spaceSrcdoc
    document.body.append(f)
  })
}

const scriptJson = value => JSON.stringify(value).replace(/</g, '\\u003c')
export function spaceSrcdoc() {
  return '<!doctype html><html><head><meta charset="utf-8">' +
    `<meta http-equiv="Content-Security-Policy" content="${SPACE_CSP}">` +
    '<meta name="referrer" content="no-referrer">' +
    `<script>(${spaceLoader.toString()})((${projectResolver.toString()})())</script></head><body></body></html>`
}
export function shellSrcdoc() {
  return '<!doctype html><html><head><meta charset="utf-8">' +
    `<meta http-equiv="Content-Security-Policy" content="${SHELL_CSP}">` +
    '<style>html,body{margin:0;height:100%;overflow:hidden;background:transparent}</style>' +
    `<script>(${shellRelay.toString()})(${scriptJson(spaceSrcdoc())})</script></head><body></body></html>`
}

export function mountSpace(container, { bundle, session, grants = [], call, onEvent = () => {} }) {
  const channel = new MessageChannel()
  const port = channel.port1
  const frame = document.createElement('iframe')
  frame.setAttribute('sandbox', 'allow-scripts')
  frame.setAttribute('referrerpolicy', 'no-referrer')
  frame.style.cssText = 'border:0;width:100%;height:100%;display:block;background:transparent'
  frame.title = `Space: ${bundle.space.name}`
  let state = 'created'
  let lastLog = -Infinity
  let overflowReported = false
  const overflow = () => {
    if (overflowReported) return
    overflowReported = true
    onEvent({ kind: 'log-overflow' })
  }
  const stop = () => {
    state = 'closed'
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
  window.addEventListener('message', onShellMessage)
  frame.addEventListener('load', () => {
    if (state === 'closed') return
    if (state === 'booted') return reloaded()
    state = 'booted'
    frame.contentWindow.postMessage({ type: 'space-boot', v: 1, session, bundle, grants }, '*', [channel.port2])
    onEvent({ kind: 'booted' })
  })
  port.onmessage = async e => {
    if (state !== 'booted') return
    const m = e.data
    const reason = validateRequest(m)
    if (reason) {
      onEvent({ kind: 'denied', op: typeof m?.op === 'string' ? m.op : null, reason })
      return
    }
    const reply = body => {
      if (state === 'booted') port.postMessage({ v: 1, id: m.id, ...body })
    }
    const denied = checkGrant(m.op, grants)
    if (denied) {
      onEvent({ kind: 'denied', op: m.op, reason: denied.message })
      reply({ ok: false, error: denied })
      return
    }
    let args = m.args
    if (m.op === 'log') {
      if (!Array.isArray(args.entries) || args.entries.length > 50 || args.entries.some(entry =>
        !entry || typeof entry.level !== 'string' || typeof entry.msg !== 'string' || entry.msg.length > 4000)) {
        onEvent({ kind: 'denied', op: 'log', reason: 'invalid log entries' })
        reply({ ok: false, error: { code: 'invalid', message: 'Invalid log entries' } })
        return
      }
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
      if (revoked && result.ok) {
        onEvent({ kind: 'denied', op: m.op, reason: revoked.message })
        reply({ ok: false, error: revoked })
      } else reply(result)
    } catch (error) {
      onEvent({ kind: 'error', message: String(error.message || error) })
      reply({ ok: false, error: { code: error.code || 'blocked', message: String(error.message || error) } })
    }
  }
  frame.srcdoc = shellSrcdoc()
  container.append(frame)
  return {
    postEvent(event, payload) {
      if (state !== 'booted') return
      port.postMessage({ v: 1, type: 'event', event, payload })
      if (event === 'session.closed') stop()
    },
    destroy() {
      stop()
      frame.remove()
    }
  }
}
