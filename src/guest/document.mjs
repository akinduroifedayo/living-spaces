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
