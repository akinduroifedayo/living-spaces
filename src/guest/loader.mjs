export function projectResolver() {
  const root = 'https://space.invalid/'
  const resolve = (base, ref) => {
    const url = new URL(ref, root + base)
    return url.origin + '/' === root ? { path: decodeURIComponent(url.pathname.slice(1)), hash: url.hash } : null
  }
  const relative = ref => !/^[a-z][a-z0-9+.-]*:/i.test(ref) && !ref.startsWith('//') && !ref.startsWith('#')
  const moduleRef = (base, ref) => {
    if (!/^(\.{1,2}\/|\/)/.test(ref) || !relative(ref)) return ref
    const target = resolve(base, ref)
    return target ? root + target.path : ref
  }
  const rewriteImports = (base, source) => {
    const tokens = []
    let at = 0
    const add = (start, end) => tokens.push({ 0: source.slice(start, end), index: start })
    const quoted = quote => {
      const start = at++
      while (at < source.length) {
        if (source[at] === '\\') at += 2
        else if (source[at++] === quote) break
      }
      add(start, at)
    }
    const scan = (nested = false) => {
      let depth = 0
      while (at < source.length) {
        const start = at
        const char = source[at]
        if (/\s/.test(char)) { at++; continue }
        if (source.startsWith('//', at)) {
          while (at < source.length && source[at] !== '\n') at++
          continue
        }
        if (source.startsWith('/*', at)) {
          const end = source.indexOf('*/', at + 2)
          at = end < 0 ? source.length : end + 2
          continue
        }
        if (char === '"' || char === "'") { quoted(char); continue }
        if (char === '`') {
          at++
          while (at < source.length) {
            if (source[at] === '\\') at += 2
            else if (source[at] === '`') { at++; break }
            else if (source.startsWith('${', at)) { at += 2; scan(true) }
            else at++
          }
          continue
        }
        const previous = tokens.at(-1)?.[0]
        if (char === '/' && (!previous || /^(return|throw|case|typeof|void|delete|yield|await|=>|[=(:,;!&|?{\[])$/.test(previous))) {
          at++
          let inClass = false
          while (at < source.length) {
            if (source[at] === '\\') at += 2
            else {
              const next = source[at++]
              if (next === '[') inClass = true
              if (next === ']') inClass = false
              if (next === '/' && !inClass) break
            }
          }
          while (/[a-z]/i.test(source[at] || '')) at++
          add(start, at)
          continue
        }
        if (nested && char === '}' && depth === 0) { at++; return }
        if (char === '{') depth++
        if (char === '}') depth--
        if (source.startsWith('=>', at)) { at += 2; add(start, at); continue }
        if (/[\w$]/.test(char)) {
          while (/[\w$]/.test(source[at] || '')) at++
        } else at++
        add(start, at)
      }
    }
    scan()
    const edits = []
    for (let i = 0; i < tokens.length; i++) {
      const token = tokens[i][0]
      if (!['import', 'export'].includes(token) || tokens[i - 1]?.[0] === '.') continue
      if (token === 'import' && tokens[i + 1]?.[0] === '(') {
        edits.push([tokens[i].index, tokens[i].index + 6, `globalThis.__spaceImport.bind(null,${JSON.stringify(base)})`])
        continue
      }
      if (tokens[i + 1]?.[0] === '.') continue
      let spec = token === 'import' && /^["']/.test(tokens[i + 1]?.[0] || '') ? tokens[i + 1] : null
      if (!spec) {
        for (let j = i + 1; j < tokens.length && ![';', 'import', 'export'].includes(tokens[j][0]); j++) {
          if (tokens[j][0] === 'from' && /^["']/.test(tokens[j + 1]?.[0] || '')) {
            spec = tokens[j + 1]
            break
          }
        }
      }
      if (spec) {
        const ref = spec[0].slice(1, -1)
        if (/^(\.{1,2}\/|\/)/.test(ref) && relative(ref)) edits.push([spec.index, spec.index + spec[0].length, JSON.stringify(moduleRef(base, ref))])
      }
    }
    for (const [start, end, text] of edits.sort((a, b) => b[0] - a[0])) source = source.slice(0, start) + text + source.slice(end)
    return source
  }
  return { root, resolve, relative, moduleRef, rewriteImports }
}

export function spaceLoader(resolver) {
  const parent = window.parent
  // srcdoc inherits the host's base URL, so fragment links need an explicit same-document target.
  document.addEventListener('click', event => {
    const anchor = event.target?.closest?.('a[href]')
    const href = anchor?.getAttribute('href')
    if (!href?.startsWith('#') || event.defaultPrevented || event.button > 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
    if (anchor.target && anchor.target !== '_self') return
    event.preventDefault()
    window.location.hash = href.slice(1)
  })
  let port = null
  let closed = false
  let seq = 0
  const pending = new Map()
  const listeners = { change: new Set(), run: new Set(), bot: new Set() }
  const logQueue = []
  let dropped = 0
  let unconfirmed = 0
  let lifecycle = null
  let reportedLifecycle = null
  let reportedDropped = 0
  let reportedUnconfirmed = 0
  let logInFlight = false
  let logsDenied = false
  class SpaceError extends Error {
    constructor(error) {
      super(error.message)
      this.name = 'SpaceError'
      Object.assign(this, error)
    }
  }
  const send = (op, args, requestId) => new Promise((resolve, reject) => {
    if (closed) return reject(new SpaceError({ code: 'session_invalid', message: 'Space session is closed' }))
    const id = ++seq
    pending.set(id, { resolve, reject, op })
    port.postMessage({ v: 1, id, op, args, ...(requestId ? { request_id: requestId } : {}) })
  })
  const responseBlob = reply => {
    if (closed) throw new SpaceError({ code: 'session_invalid', message: 'Space session is closed' })
    const invalid = () => new SpaceError({ code: 'invalid', message: 'Malformed network byte response' })
    if (!reply || !Number.isInteger(reply.status) || typeof reply.url !== 'string' ||
        !reply.headers || typeof reply.headers !== 'object' || Array.isArray(reply.headers) ||
        Object.values(reply.headers).some(value => typeof value !== 'string')) throw invalid()
    if (reply.status < 200 || reply.status >= 300) {
      throw new SpaceError({ code: 'http_status', message: `HTTP ${reply.status}`, status: reply.status, url: reply.url, headers: reply.headers })
    }
    if (typeof reply.b64 !== 'string' || typeof reply.mime !== 'string' ||
        reply.b64.length % 4 !== 0 || /[^A-Za-z0-9+/=]/.test(reply.b64)) throw invalid()
    let decoded
    try { decoded = atob(reply.b64) } catch { throw invalid() }
    return new Blob([Uint8Array.from(decoded, char => char.charCodeAt(0))], { type: reply.mime })
  }
  const safeText = value => {
    try {
      return value instanceof Error ? value.stack || String(value) : typeof value === 'string' ? value : JSON.stringify(value)
    } catch {
      return '[unserializable]'
    }
  }
  const pushLog = (level, parts, priority = false) => {
    if (logQueue.length === 50) {
      dropped++
      if (!priority) return
      logQueue.pop()
    }
    let msg = parts.map(safeText).join(' ')
    if (msg.length > 4000) {
      const marker = ` [truncated; original ${msg.length} chars]`
      msg = msg.slice(0, 4000 - marker.length) + marker
    }
    if (priority) logQueue.unshift({ level, msg })
    else logQueue.push({ level, msg })
  }
  for (const level of Object.getOwnPropertyNames(console).filter(name => typeof console[name] === 'function')) {
    const original = console[level].bind(console)
    console[level] = (...parts) => {
      if (level !== 'assert' || !parts[0]) pushLog(level, parts)
      original(...parts)
    }
  }
  window.addEventListener('error', e => pushLog('error', [e.error || `${e.message} @${e.filename}:${e.lineno}`]))
  window.addEventListener('unhandledrejection', e => pushLog('error', ['unhandled rejection:', e.reason]))
  document.addEventListener('securitypolicyviolation', e => pushLog('warn', [`blocked by sandbox policy: ${e.effectiveDirective} ${e.blockedURI}`]))
  const logTimer = setInterval(() => {
    if (!port || closed || logInFlight || logsDenied) return
    if (!logQueue.length && dropped === reportedDropped && unconfirmed === reportedUnconfirmed && lifecycle === reportedLifecycle) return
    const entries = logQueue.splice(0)
    const overflow = dropped > reportedDropped
    if (overflow) {
      if (entries.length === 50) { entries.pop(); dropped++ }
      entries.push({ level: 'warn', msg: `Space log overflow: dropped ${dropped} entries` })
    }
    const originals = entries.length - Number(overflow)
    const args = { entries, dropped, unconfirmed }
    if (lifecycle !== reportedLifecycle) args.lifecycle = lifecycle
    logInFlight = true
    send('log', args).then(result => {
      if (result.throttled || (result.stored === 0 && entries.length)) {
        dropped += originals
        return
      }
      if (result.stored !== entries.length) throw new Error('Unconfirmed log delivery')
      reportedDropped = args.dropped
      reportedUnconfirmed = args.unconfirmed
      if (args.lifecycle) reportedLifecycle = args.lifecycle
    }).catch(error => {
      // The host refused Diagnostics for this session; retrying cannot succeed.
      if (error?.code === 'not_granted') { logsDenied = true; logQueue.length = 0; return }
      // A failed reply cannot tell us whether the backend stored the batch.
      unconfirmed += originals
    }).finally(() => { logInFlight = false })
  }, 510)
  const api = {
    meta: null,
    drafts: {
      get: key => send('draft.get', key),
      put: args => send('draft.put', args),
      delete: key => send('draft.delete', key)
    },
    editor: {
      save: ({ request_id, ...args }) => send('editor.save', args, request_id),
      outcome: args => send('outcome.get', args)
    },
    query: async (collection, options = {}) => (await send('data.query', { ...options, collection })).records,
    get: (collection, id) => send('data.get', { collection, id }),
    put: (collection, id, data, { baseRev, merge } = {}) => send('data.put', { collection, id, data, base_rev: baseRev, merge }),
    delete: (collection, id, { baseRev } = {}) => send('data.delete', { collection, id, base_rev: baseRev }),
    batch: ops => send('data.batch', { ops }),
    ask: (text, { activationId = crypto.randomUUID(), records = [] } = {}) => send('bot.request', { activation_id: activationId, text, records }),
    refresh: () => send('refresh', {}),
    runs: () => send('runs.list', {}),
    net: {
      fetch: (url, { method, headers, body, as } = {}) => send('net.fetch', Object.fromEntries(
        Object.entries({ url, method, headers, body, as }).filter(([, value]) => value !== undefined)
      )),
      blob: (url, { method, headers, body } = {}) => send('net.fetch', Object.fromEntries(
        Object.entries({ url, method, headers, body, as: 'bytes' }).filter(([, value]) => value !== undefined)
      )).then(responseBlob)
    },
    on(event, cb) {
      if (!listeners[event]) throw new TypeError(`Unknown Space event: ${event}`)
      listeners[event].add(cb)
      return () => listeners[event].delete(cb)
    },
    field: (record, name) => record.data?.[name] ?? record.source?.[name]
  }
  Object.defineProperty(window, 'space', { value: api, enumerable: true })
  Object.defineProperty(window, '__spaceImport', { value: (base, ref, options) => import(resolver.moduleRef(base, String(ref)), options) })

  const showError = error => {
    pushLog('error', ['Space failed to load:', error], true)
    const panel = document.createElement('section')
    panel.setAttribute('role', 'alert')
    panel.style.cssText = 'padding:24px;font:16px system-ui;color:#971b1b;background:#fff4f4'
    const title = document.createElement('h1')
    title.textContent = 'This Space could not load'
    const detail = document.createElement('p')
    detail.textContent = error.message || String(error)
    panel.append(title, detail)
    document.body.replaceChildren(panel)
  }
  async function boot(bundle, grants) {
    api.meta = { space: { id: bundle.space.id, name: bundle.space.name, rev: bundle.rev }, grants }
    const files = new Map(bundle.files.map(f => [f.path, f]))
    const urls = new Map()
    const bytes = f => f.text !== undefined ? f.text : Uint8Array.from(atob(f.b64), c => c.charCodeAt(0))
    const blob = (f, body = bytes(f)) => URL.createObjectURL(new Blob([body], { type: f.mime }))
    for (const f of files.values()) {
      if (!/\.(css|m?js)$/.test(f.path)) urls.set(f.path, blob(f))
    }
    const assetUrl = (base, ref) => {
      if (!resolver.relative(ref)) return null
      const target = resolver.resolve(base, ref)
      if (!target || !urls.has(target.path)) return null
      return urls.get(target.path) + target.hash
    }
    api.asset = path => {
      if (typeof path !== 'string') return null
      try { return assetUrl('', path) } catch { return null }
    }
    const rewriteCss = (base, css) => css.replace(/url\(\s*(['"]?)([^'"\)]+)\1\s*\)/g, (match, quote, ref) => {
      const url = assetUrl(base, ref.trim())
      return url ? `url("${url}")` : match
    })
    for (const f of files.values()) {
      if (f.path.endsWith('.css')) urls.set(f.path, blob(f, rewriteCss(f.path, f.text)))
    }
    const imports = {}
    for (const f of files.values()) {
      if (/\.m?js$/.test(f.path)) {
        const url = blob({ mime: 'text/javascript' }, resolver.rewriteImports(f.path, f.text))
        urls.set(f.path, url)
        imports[resolver.root + f.path] = url
      }
    }
    for (const [name, path] of Object.entries(bundle.manifest.imports || {})) {
      const target = resolver.resolve('index.html', path)
      if (target && urls.has(target.path)) imports[name] = urls.get(target.path)
    }
    const entryPath = bundle.manifest.entry || 'index.html'
    const entry = files.get(entryPath)
    if (!entry) throw new Error(`Entry not found: ${entryPath}`)
    const doc = new DOMParser().parseFromString(entry.text, 'text/html')
    const scripts = [...doc.querySelectorAll('script')]
    for (const el of doc.querySelectorAll('[src],link[href]')) {
      const attr = el.hasAttribute('src') ? 'src' : 'href'
      const ref = el.getAttribute(attr)
      if (!resolver.relative(ref)) continue
      if (el.tagName === 'SCRIPT' && el.type === 'module') {
        el.removeAttribute('src')
        const target = resolver.resolve(entryPath, ref)
        el.textContent = `import ${JSON.stringify(target ? resolver.root + target.path : ref)}`
      } else {
        const url = assetUrl(entryPath, ref)
        if (url) el.setAttribute(attr, url)
      }
    }
    for (const el of doc.querySelectorAll('script[type=module]')) el.textContent = resolver.rewriteImports(entryPath, el.textContent)
    for (const el of doc.querySelectorAll('style')) el.textContent = rewriteCss(entryPath, el.textContent)
    for (const el of doc.querySelectorAll('[style]')) el.setAttribute('style', rewriteCss(entryPath, el.getAttribute('style')))
    for (const script of scripts) script.remove()
    const map = document.createElement('script')
    map.type = 'importmap'
    map.textContent = JSON.stringify({ imports })
    document.head.append(map)
    for (const { name, value } of doc.documentElement.attributes) {
      if (['lang', 'dir', 'class', 'style'].includes(name) || name.startsWith('data-')) document.documentElement.setAttribute(name, value)
    }
    const theme = bundle.manifest.theme
    if (theme !== undefined) {
      const object = value => value !== null && typeof value === 'object' && !Array.isArray(value)
      let invalid = !object(theme)
      const declarations = []
      if (!invalid) {
        if (theme.preset !== undefined) {
          if (['editorial', 'terminal', 'playful', 'minimal', 'data', 'journal', 'game'].includes(theme.preset)) document.documentElement.setAttribute('data-theme', theme.preset)
          else invalid = true
        }
        if (theme.tokens !== undefined) {
          if (!object(theme.tokens)) invalid = true
          else for (const [index, [name, value]] of Object.entries(theme.tokens).entries()) {
            if (index >= 64 || !/^[a-z][a-z0-9-]{0,39}$/.test(name) || typeof value !== 'string' || [...value].length > 200 || /[;{}<>\\]|url\(|@import|expression\(/i.test(value)) {
              invalid = true
              continue
            }
            declarations.push(`--space-${name}:${value};`)
          }
        }
      }
      if (declarations.length) {
        const style = document.createElement('style')
        style.setAttribute('data-space-theme', '')
        style.textContent = `:root{${declarations.join('')}}`
        document.head.append(style)
      }
      if (invalid) console.warn('Skipped invalid manifest theme settings')
    }
    if (doc.title) document.title = doc.title
    for (const node of [...doc.head.childNodes]) {
      const copy = document.importNode(node, true)
      const themeStyle = document.querySelector('style[data-space-theme]')
      if (node.nodeName === 'LINK' && node.getAttribute('href') === urls.get('kit/spaces-kit.css') && themeStyle) document.head.insertBefore(copy, themeStyle)
      else document.head.append(copy)
    }
    for (const attribute of doc.body.attributes) document.body.setAttribute(attribute.name, attribute.value)
    for (const node of [...doc.body.childNodes]) document.body.append(document.importNode(node, true))
    for (const old of scripts) {
      const script = document.createElement('script')
      for (const attribute of old.attributes) script.setAttribute(attribute.name, attribute.value)
      const hasSrc = [...old.attributes].some(attribute => attribute.name === 'src')
      // Browsers fire no load event for inline module scripts, so serve inline module text from a blob URL.
      if (old.type === 'module' && !hasSrc) script.src = blob({ mime: 'text/javascript' }, old.textContent)
      else if (old.type === 'module') script.textContent = old.textContent
      else script.textContent = resolver.rewriteImports(entryPath, old.textContent)
      const done = script.src || script.type === 'module' ? new Promise((resolve, reject) => {
        script.onload = resolve
        script.onerror = () => reject(new Error(`Script failed: ${old.getAttribute('src') || 'entry module'}`))
      }) : null
      document.body.append(script)
      if (done) await done
    }
  }
  window.addEventListener('message', function onBoot(e) {
    if (e.source !== parent || e.data?.type !== 'space-boot' || e.data.v !== 1 || !e.ports[0]) return
    window.removeEventListener('message', onBoot)
    port = e.ports[0]
    port.onmessage = event => {
      const message = event.data
      if (message?.v !== 1 || closed) return
      if (message.type === 'event') {
        if (message.event === 'session.closed') {
          closed = true
          clearInterval(logTimer)
          for (const { reject } of pending.values()) reject(new SpaceError({ code: 'session_invalid', message: message.payload.reason }))
          pending.clear()
          port.close()
          return
        }
        const name = { 'data.changed': 'change', 'run.updated': 'run', 'bot.status': 'bot' }[message.event]
        for (const cb of listeners[name] || []) {
          try { cb(message.payload) } catch (error) { pushLog('error', [error]) }
        }
        return
      }
      const request = pending.get(message.id)
      if (!request) return
      pending.delete(message.id)
      const confirmed = message.ok && (request.op !== 'editor.save' || !message.outcome || ['success', 'confirmed'].includes(message.outcome.status))
      confirmed ? request.resolve(message.result) : request.reject(new SpaceError({ ...(request.op === 'editor.save' ? { message: 'Save outcome unknown' } : {}), ...message.error, ...(message.outcome ? { outcome: message.outcome } : {}) }))
    }
    boot(e.data.bundle, e.data.grants).then(() => {
      lifecycle = 'loaded'
    }, error => {
      lifecycle = 'failed'
      showError(error)
    })
  })
}
