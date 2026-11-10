// Spaces sandbox host. Plain DOM so it runs in the desktop plugin and in the bare-Electron harness.
//
// Containment, outside in:
//   host page ── iframe A "shell" (srcdoc, sandbox=allow-scripts, opaque origin, CSP frame-src 'none')
//                 └── iframe B "space" (srcdoc, sandbox=allow-scripts, opaque origin, CSP: no network)
// A exists only so its frame-src governs every navigation of B: a Space that sets location/meta refresh
// to an external URL is refused by the embedder's policy, which B cannot touch.
// The only channel out is one MessagePort per mount. The host binds it to one Space id; ops carry no id.

export const BRIDGE_VERSION = 1

// v1 grants. Later grants (agent.ask, tool:<name>, files.read) get their own ops and stay denied
// until the user turns them on for that Space.
export const V1_GRANTS = ['data', 'refresh', 'logs']
const OP_GRANT = {
  'data.get': 'data',
  'data.set': 'data',
  'data.delete': 'data',
  refresh: 'refresh',
  log: 'logs'
}

export const SPACE_CSP = [
  "default-src 'none'",
  "script-src 'unsafe-inline' 'unsafe-eval' blob:",
  "style-src 'unsafe-inline' blob:",
  'img-src blob: data:',
  'font-src blob: data:',
  'media-src blob: data:',
  'worker-src blob:',
  "connect-src 'none'",
  "frame-src 'none'",
  "form-action 'none'",
  "base-uri 'none'",
  "object-src 'none'",
  "manifest-src 'none'",
  // CSP3 webrtc directive: the only in-frame control over STUN/TURN egress, which connect-src does not cover.
  "webrtc 'block'"
].join('; ')

// A srcdoc child inherits its parent's policy, so the shell's policy is the Space's floor. Keep them equal.
export const SHELL_CSP = SPACE_CSP

const VIRTUAL_ROOT = 'https://space.invalid/'

// Runs inside B. Receives the project once, materializes files as frame-local blob: URLs, installs an
// import map over virtual absolute URLs (so ESM relative imports and bare vendored names resolve with
// no network), renders the entry HTML, and exposes window.space.
function spaceLoader(VIRTUAL_ROOT) {
  const parent = window.parent
  let port = null
  let seq = 0
  const pending = new Map()
  const dataListeners = new Set()
  const state = { data: {}, revs: {} }
  const logQueue = []

  const send = (op, args) =>
    new Promise((resolve, reject) => {
      const id = ++seq
      pending.set(id, { resolve, reject })
      port.postMessage({ v: 1, id, op, args })
    })

  const flushLogs = () => {
    if (port && logQueue.length) {
      port.postMessage({ v: 1, op: 'log', args: { entries: logQueue.splice(0) } })
    }
  }
  const pushLog = (level, parts) => {
    const msg = parts
      .map(p => (p instanceof Error ? p.stack || String(p) : typeof p === 'string' ? p : safeJson(p)))
      .join(' ')
    logQueue.push({ level, msg: msg.slice(0, 4000) })
    if (logQueue.length > 40) logQueue.splice(0, logQueue.length - 40)
    queueMicrotask(flushLogs)
  }
  const safeJson = v => {
    try {
      return JSON.stringify(v)
    } catch {
      return String(v)
    }
  }
  for (const level of ['log', 'info', 'warn', 'error']) {
    const orig = console[level].bind(console)
    console[level] = (...a) => {
      pushLog(level, a)
      orig(...a)
    }
  }
  window.addEventListener('error', e => pushLog('error', [e.error || e.message + ' @' + e.filename + ':' + e.lineno]))
  window.addEventListener('unhandledrejection', e => pushLog('error', ['unhandled rejection:', e.reason]))
  document.addEventListener('securitypolicyviolation', e =>
    pushLog('warn', ['blocked by sandbox policy: ' + e.effectiveDirective + ' ' + e.blockedURI])
  )

  const applyData = data => {
    state.data = {}
    state.revs = {}
    for (const [k, rec] of Object.entries(data || {})) {
      state.data[k] = rec.value
      state.revs[k] = rec.rev
    }
    for (const cb of dataListeners) {
      try {
        cb(state.data)
      } catch (err) {
        pushLog('error', [err])
      }
    }
  }

  const api = {
    version: 1,
    manifest: null,
    grants: [],
    get data() {
      return state.data
    },
    get: key => state.data[key],
    async set(key, value) {
      const res = await send('data.set', { key, value, base_rev: state.revs[key] ?? 0 })
      if (res && res.conflict) {
        state.data[key] = res.current.value
        state.revs[key] = res.current.rev
        const err = new Error('stale write: ' + key + ' changed elsewhere; reloaded current value')
        err.conflict = res.current
        throw err
      }
      state.data[key] = value
      state.revs[key] = res.rev
      return res
    },
    delete: key => send('data.delete', { key }),
    refresh: () => send('refresh', {}),
    call: (op, args) => send(op, args),
    onData(cb) {
      dataListeners.add(cb)
      return () => dataListeners.delete(cb)
    }
  }
  Object.defineProperty(window, 'space', { value: api, enumerable: true })

  const resolvePath = (base, rel) => {
    const u = new URL(rel, VIRTUAL_ROOT + base)
    return u.origin + '/' === VIRTUAL_ROOT ? decodeURIComponent(u.pathname.slice(1)) : null
  }
  const isRelative = s => !/^[a-z][a-z0-9+.-]*:/i.test(s) && !s.startsWith('//') && !s.startsWith('#')

  async function boot(bundle) {
    api.manifest = bundle.manifest
    api.grants = bundle.grants
    const files = new Map(bundle.files.map(f => [f.path, f]))
    const urls = new Map()
    const blobOf = (f, body) => URL.createObjectURL(new Blob([body], { type: f.mime }))
    const bytes = f => (f.text !== undefined ? f.text : Uint8Array.from(atob(f.b64), c => c.charCodeAt(0)))

    for (const f of files.values()) {
      if (!/\.(css|m?js|html?)$/.test(f.path)) urls.set(f.path, blobOf(f, bytes(f)))
    }
    const assetUrl = (base, ref) => {
      if (!isRelative(ref)) return null
      const p = resolvePath(base, ref.split('#')[0].split('?')[0])
      return p && urls.get(p)
    }
    const rewriteCss = (base, css) =>
      css.replace(/url\(\s*(['"]?)([^'")]+)\1\s*\)/g, (m, q, ref) => {
        const u = assetUrl(base, ref.trim())
        return u ? `url("${u}")` : m
      })
    for (const f of files.values()) {
      if (f.path.endsWith('.css')) urls.set(f.path, blobOf(f, rewriteCss(f.path, f.text)))
    }
    const rewriteImports = (base, src) =>
      src.replace(
        /(\bimport\s*(?:[\w*{}\s,$]+?\s*from\s*)?|\bexport\s*[\w*{}\s,$]+?\s*from\s*|\bimport\s*\(\s*)(['"])(\.{1,2}\/[^'"]+|\/[^'"]+)\2/g,
        (m, head, q, spec) => {
          const p = resolvePath(base, spec)
          return p ? head + q + VIRTUAL_ROOT + p + q : m
        }
      )
    const imports = {}
    for (const f of files.values()) {
      if (/\.m?js$/.test(f.path)) {
        const u = blobOf({ mime: 'text/javascript' }, rewriteImports(f.path, f.text))
        urls.set(f.path, u)
        imports[VIRTUAL_ROOT + f.path] = u
      }
    }
    for (const [name, path] of Object.entries(bundle.manifest.imports || {})) {
      if (urls.has(path)) imports[name] = urls.get(path)
    }

    const entryPath = bundle.manifest.entry || 'index.html'
    const entry = files.get(entryPath)
    if (!entry) throw new Error('entry not found: ' + entryPath)
    const doc = new DOMParser().parseFromString(entry.text, 'text/html')
    for (const el of doc.querySelectorAll('[src],link[href]')) {
      const attr = el.hasAttribute('src') ? 'src' : 'href'
      const ref = el.getAttribute(attr)
      if (!isRelative(ref)) continue
      const p = resolvePath(entryPath, ref)
      if (el.tagName === 'SCRIPT' && el.type === 'module') {
        el.removeAttribute('src')
        el.textContent = `import ${JSON.stringify(VIRTUAL_ROOT + p)}`
      } else if (urls.has(p)) el.setAttribute(attr, urls.get(p))
    }
    for (const el of doc.querySelectorAll('script[type=module]:not([src])')) {
      el.textContent = rewriteImports(entryPath, el.textContent)
    }
    for (const el of doc.querySelectorAll('style')) el.textContent = rewriteCss(entryPath, el.textContent)

    const map = document.createElement('script')
    map.type = 'importmap'
    map.textContent = JSON.stringify({ imports })
    document.head.append(map)
    if (doc.title) document.title = doc.title
    const scripts = []
    const adopt = (from, to) => {
      for (const node of [...from.childNodes]) {
        if (node.nodeName === 'SCRIPT') scripts.push(node)
        else to.append(document.importNode(node, true))
      }
    }
    adopt(doc.head, document.head)
    for (const a of doc.body.attributes) document.body.setAttribute(a.name, a.value)
    adopt(doc.body, document.body)
    for (const old of scripts) {
      const s = document.createElement('script')
      for (const a of old.attributes) s.setAttribute(a.name, a.value)
      s.textContent = old.textContent
      const done = s.src && s.type !== 'module' ? new Promise(r => ((s.onload = r), (s.onerror = r))) : null
      document.body.append(s)
      if (done) await done
    }
  }

  window.addEventListener('message', function onBoot(e) {
    if (e.source !== parent || !e.data || e.data.type !== 'space-boot' || !e.ports[0]) return
    window.removeEventListener('message', onBoot)
    port = e.ports[0]
    port.onmessage = ev => {
      const m = ev.data || {}
      if (m.type === 'data') return applyData(m.data)
      const p = pending.get(m.id)
      if (!p) return
      pending.delete(m.id)
      m.ok ? p.resolve(m.result) : p.reject(new Error(m.error))
    }
    applyData(e.data.bundle.data)
    boot(e.data.bundle).catch(err => pushLog('error', ['space failed to load:', err]))
  })
}

// Runs inside A. Creates B, hands it the bundle and the port, then steps aside.
function shellRelay(spaceSrcdoc) {
  window.addEventListener('message', function onBoot(e) {
    if (e.source !== window.parent || !e.data || e.data.type !== 'space-boot' || !e.ports[0]) return
    window.removeEventListener('message', onBoot)
    const f = document.createElement('iframe')
    f.setAttribute('sandbox', 'allow-scripts')
    f.setAttribute('referrerpolicy', 'no-referrer')
    f.style.cssText = 'border:0;width:100%;height:100%;display:block'
    f.title = 'Space'
    let booted = false
    f.addEventListener('load', () => {
      if (booted) return
      booted = true
      f.contentWindow.postMessage(e.data, '*', [e.ports[0]])
    })
    f.srcdoc = spaceSrcdoc
    document.body.append(f)
  })
}

const scriptJson = value => JSON.stringify(value).replace(/</g, '\\u003c')

export function spaceSrcdoc() {
  return (
    `<!doctype html><html><head><meta charset="utf-8">` +
    `<meta http-equiv="Content-Security-Policy" content="${SPACE_CSP}">` +
    `<meta name="referrer" content="no-referrer">` +
    `<script>(${spaceLoader.toString()})(${scriptJson(VIRTUAL_ROOT)})</script></head><body></body></html>`
  )
}

export function shellSrcdoc() {
  return (
    `<!doctype html><html><head><meta charset="utf-8">` +
    `<meta http-equiv="Content-Security-Policy" content="${SHELL_CSP}">` +
    `<style>html,body{margin:0;height:100%;overflow:hidden;background:transparent}</style>` +
    `<script>(${shellRelay.toString()})(${scriptJson(spaceSrcdoc())})</script></head><body></body></html>`
  )
}

// Host side. `call(op, args)` reaches the plugin backend for THIS space; it never sees an id from the frame.
export function mountSpace(container, { bundle, grants = V1_GRANTS, call, onEvent = () => {} }) {
  const channel = new MessageChannel()
  const port = channel.port1
  const frame = document.createElement('iframe')
  frame.setAttribute('sandbox', 'allow-scripts')
  frame.setAttribute('referrerpolicy', 'no-referrer')
  frame.style.cssText = 'border:0;width:100%;height:100%;display:block;background:transparent'
  frame.title = `Space: ${bundle.name}`
  let booted = false
  frame.addEventListener('load', () => {
    if (booted) return onEvent({ kind: 'reloaded' })
    booted = true
    frame.contentWindow.postMessage(
      { type: 'space-boot', bundle: { ...bundle, grants: [...grants] } },
      '*',
      [channel.port2]
    )
  })

  port.onmessage = async ev => {
    const m = ev.data
    if (!m || m.v !== BRIDGE_VERSION || typeof m.op !== 'string') return
    const grant = OP_GRANT[m.op]
    const reply = msg => m.id !== undefined && port.postMessage({ id: m.id, ...msg })
    if (!grant || !grants.includes(grant)) {
      onEvent({ kind: 'denied', op: m.op })
      return reply({ ok: false, error: `not granted: ${m.op}` })
    }
    try {
      const args = m.args && typeof m.args === 'object' ? m.args : {}
      reply({ ok: true, result: await call(m.op, args) })
    } catch (err) {
      reply({ ok: false, error: String(err && err.message ? err.message : err) })
    }
  }

  frame.srcdoc = shellSrcdoc()
  container.append(frame)
  return {
    frame,
    pushData: data => port.postMessage({ type: 'data', data }),
    destroy() {
      port.close()
      frame.remove()
    }
  }
}
