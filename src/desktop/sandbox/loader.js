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
  const listeners = { change: new Set(), run: new Set() }
  const logQueue = []
  let dropped = 0
  class SpaceError extends Error {
    constructor(error) {
      super(error.message)
      this.name = 'SpaceError'
      Object.assign(this, error)
    }
  }
  const send = (op, args) => new Promise((resolve, reject) => {
    if (closed) return reject(new SpaceError({ code: 'session_invalid', message: 'Space session is closed' }))
    const id = ++seq
    pending.set(id, { resolve, reject })
    port.postMessage({ v: 1, id, op, args })
  })
  const safeText = value => {
    try {
      return value instanceof Error ? value.stack || String(value) : typeof value === 'string' ? value : JSON.stringify(value)
    } catch {
      return '[unserializable]'
    }
  }
  const pushLog = (level, parts) => {
    if (logQueue.length === 50) { dropped++; return }
    logQueue.push({ level, msg: parts.map(safeText).join(' ').slice(0, 4000) })
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
    if (!port || closed || !logQueue.length) return
    const entries = logQueue.splice(0)
    if (dropped) entries[entries.length - 1] = { level: 'warn', msg: `Space log overflow: dropped ${dropped + 1} entries` }
    const args = { entries }
    dropped = 0
    send('log', args).catch(() => {})
  }, 510)
  const api = {
    meta: null,
    query: async (collection, options = {}) => (await send('data.query', { ...options, collection })).records,
    get: (collection, id) => send('data.get', { collection, id }),
    put: (collection, id, data, { baseRev, merge } = {}) => send('data.put', { collection, id, data, base_rev: baseRev, merge }),
    delete: (collection, id, { baseRev } = {}) => send('data.delete', { collection, id, base_rev: baseRev }),
    batch: ops => send('data.batch', { ops }),
    refresh: () => send('refresh', {}),
    runs: () => send('runs.list', {}),
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
    pushLog('error', ['Space failed to load:', error])
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
    if (doc.title) document.title = doc.title
    for (const node of [...doc.head.childNodes]) document.head.append(document.importNode(node, true))
    for (const attribute of doc.body.attributes) document.body.setAttribute(attribute.name, attribute.value)
    for (const node of [...doc.body.childNodes]) document.body.append(document.importNode(node, true))
    for (const old of scripts) {
      const script = document.createElement('script')
      for (const attribute of old.attributes) script.setAttribute(attribute.name, attribute.value)
      script.textContent = old.type === 'module' ? old.textContent : resolver.rewriteImports(entryPath, old.textContent)
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
        const name = { 'data.changed': 'change', 'run.updated': 'run' }[message.event]
        for (const cb of listeners[name] || []) {
          try { cb(message.payload) } catch (error) { pushLog('error', [error]) }
        }
        return
      }
      const request = pending.get(message.id)
      if (!request) return
      pending.delete(message.id)
      message.ok ? request.resolve(message.result) : request.reject(new SpaceError(message.error))
    }
    boot(e.data.bundle, e.data.grants).catch(showError)
  })
}
