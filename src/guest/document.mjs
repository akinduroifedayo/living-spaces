import { spaceLoader, projectResolver } from './loader.mjs'

export const SPACE_CSP = "default-src 'none'; script-src 'unsafe-inline' 'unsafe-eval' blob:; style-src 'unsafe-inline' blob:; img-src blob: data:; font-src blob: data:; media-src blob: data:; worker-src blob:; connect-src 'none'; frame-src 'none'; form-action 'none'; base-uri 'none'; object-src 'none'; manifest-src 'none'; webrtc 'block'"
// The shell's policy is the inner frame's immutable navigation floor.
export const SHELL_CSP = SPACE_CSP

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
export function spaceSrcdoc(policy = SPACE_CSP) {
  return '<!doctype html><html><head><meta charset="utf-8">' +
    `<meta http-equiv="Content-Security-Policy" content="${policy}">` +
    '<meta name="referrer" content="no-referrer">' +
    `<script>(${spaceLoader.toString()})((${projectResolver.toString()})())</script></head><body></body></html>`
}
const HTTPS_CSP = "default-src 'none'; script-src 'unsafe-inline' 'unsafe-eval' blob: https:; style-src 'unsafe-inline' blob: https:; img-src blob: data: https:; font-src blob: data: https:; media-src blob: data: https:; worker-src blob:; connect-src https:; frame-src 'none'; form-action 'none'; base-uri 'none'; object-src 'none'; manifest-src 'none'; webrtc 'block'"

function partitionShell(innerDocument) {
  const queue = []
  let queuedBytes = 0
  let waiting = null
  let port = null
  let state = 'created'
  const take = () => {
    queuedBytes = 0
    return queue.splice(0)
  }
  const enqueue = message => {
    const size = new TextEncoder().encode(JSON.stringify(message)).byteLength
    if (queue.length >= 64 || queuedBytes + size > 4 * 1024 * 1024) {
      state = 'closed'
      port?.close()
      queue.splice(0)
      queue.push({ kind: 'fatal', message: 'Space transport queue exceeded its limit' })
    } else {
      queue.push(message)
      queuedBytes += size
    }
    if (waiting) {
      const finish = waiting
      waiting = null
      finish(take())
    }
  }
  Object.defineProperties(window, {
    __lsBoot: { value: boot => {
      if (state !== 'created') throw new Error('Space transport already booted')
      state = 'booting'
      const channel = new MessageChannel()
      port = channel.port1
      port.onmessage = event => {
        if (state !== 'active') return
        try { enqueue({ kind: 'request', message: event.data }) }
        catch { enqueue({ kind: 'fatal', message: 'Invalid Space transport payload' }) }
      }
      const frame = document.createElement('iframe')
      frame.setAttribute('sandbox', 'allow-scripts')
      frame.setAttribute('referrerpolicy', 'no-referrer')
      frame.style.cssText = 'border:0;width:100%;height:100%;display:block'
      frame.title = 'Space'
      frame.addEventListener('load', () => {
        if (state !== 'booting') {
          if (state === 'active') enqueue({ kind: 'reloaded' })
          state = 'closed'
          port.close()
          return
        }
        state = 'active'
        frame.contentWindow.postMessage(boot, '*', [channel.port2])
        enqueue({ kind: 'booted' })
      })
      frame.srcdoc = innerDocument
      document.body.append(frame)
      return true
    } },
    __lsDrain: { value: () => {
      if (queue.length) return Promise.resolve(take())
      if (state === 'closed') return Promise.resolve([{ kind: 'fatal', message: 'Space transport closed' }])
      if (waiting) throw new Error('Space drain already pending')
      return new Promise(resolve => {
        const finish = value => { clearTimeout(timer); resolve(value) }
        const timer = setTimeout(() => { if (waiting === finish) { waiting = null; resolve([]) } }, 1000)
        waiting = finish
      })
    } },
    __lsDeliver: { value: message => {
      if (state !== 'active') return false
      port.postMessage(message)
      return true
    } }
  })
}

export function partitionSrcdoc(internet = false) {
  const policy = internet ? HTTPS_CSP : SPACE_CSP
  return '<!doctype html><html><head><meta charset="utf-8">' +
    `<meta http-equiv="Content-Security-Policy" content="${policy}">` +
    '<meta name="referrer" content="no-referrer">' +
    '<style>html,body{margin:0;height:100%;overflow:hidden;background:transparent}</style>' +
    `<script>(${partitionShell.toString()})(${scriptJson(spaceSrcdoc(policy))})</script></head><body></body></html>`
}

export function shellSrcdoc() {
  return '<!doctype html><html><head><meta charset="utf-8">' +
    `<meta http-equiv="Content-Security-Policy" content="${SHELL_CSP}">` +
    '<style>html,body{margin:0;height:100%;overflow:hidden;background:transparent}</style>' +
    `<script>(${shellRelay.toString()})(${scriptJson(spaceSrcdoc())})</script></head><body></body></html>`
}
