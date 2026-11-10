import { h } from 'preact'
import { useCallback, useEffect, useRef, useState } from 'preact/hooks'

export function html(strings, ...values) {
  const input = []
  strings.forEach((part, i) => {
    input.push(...part)
    if (i < values.length) input.push({ value: values[i] })
  })
  let at = 0
  const hole = item => item !== null && typeof item === 'object'
  const starts = text => input.slice(at, at + text.length).join('') === text
  const skip = () => { while (/\s/.test(input[at] || '') && !hole(input[at])) at++ }
  const fail = message => { throw new SyntaxError(`html: ${message}`) }
  const decode = text => text.replace(/&(#x[\da-f]+|#\d+|amp|lt|gt|quot|apos|nbsp);/gi, (match, entity) => {
    if (entity[0] === '#') {
      const point = entity[1].toLowerCase() === 'x' ? parseInt(entity.slice(2), 16) : Number(entity.slice(1))
      return point > 0 && point <= 0x10ffff ? String.fromCodePoint(point) : '\ufffd'
    }
    return { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: '\u00a0' }[entity.toLowerCase()]
  })
  const word = () => {
    if (hole(input[at])) return input[at++].value
    let name = ''
    while (at < input.length && !hole(input[at]) && !/[\s=/>]/.test(input[at])) name += input[at++]
    return name || fail('expected a name')
  }
  const attribute = () => {
    const quote = ['"', "'"].includes(input[at]) ? input[at++] : null
    const parts = []
    let text = ''
    const flush = () => { if (text) { parts.push(decode(text)); text = '' } }
    while (at < input.length && (quote ? input[at] !== quote : hole(input[at]) || !/[\s>]/.test(input[at]) && !starts('/>'))) {
      if (hole(input[at])) { flush(); parts.push(input[at++].value) }
      else text += input[at++]
    }
    flush()
    if (quote && input[at++] !== quote) fail('unclosed attribute')
    return parts.length === 1 ? parts[0] : parts.join('')
  }
  const children = (tag = null) => {
    const result = []
    while (at < input.length) {
      if (starts('<!--')) {
        at += 4
        while (at < input.length && !starts('-->')) at++
        if (at === input.length) fail('unclosed comment')
        at += 3
      } else if (starts('</')) {
        if (tag === null) fail('unexpected closing tag')
        at += 2
        if (input[at] === '/') at++
        else {
          const name = word()
          if (name !== tag) fail(`closing tag does not match ${String(tag)}`)
        }
        skip()
        if (input[at++] !== '>') fail('expected >')
        return result
      } else if (input[at] === '<') {
        at++
        const name = word()
        const props = {}
        skip()
        while (at < input.length && input[at] !== '>' && !starts('/>')) {
          if (starts('...')) {
            at += 3
            if (!hole(input[at])) fail('spread needs an interpolated object')
            Object.assign(props, input[at++].value)
          } else {
            const key = word()
            skip()
            if (input[at] === '=') { at++; skip(); props[key] = attribute() }
            else props[key] = true
          }
          skip()
        }
        const selfClosing = starts('/>')
        if (selfClosing) at += 2
        else if (input[at++] !== '>') fail('unclosed element')
        const voidTag = typeof name === 'string' && /^(area|base|br|col|embed|hr|img|input|link|meta|param|source|track|wbr)$/.test(name)
        result.push(h(name, props, ...(selfClosing || voidTag ? [] : children(name))))
      } else if (hole(input[at])) result.push(input[at++].value)
      else {
        let text = ''
        while (at < input.length && input[at] !== '<' && !hole(input[at])) text += input[at++]
        text = text.replace(/^\s*\n\s*|\s*\n\s*$/g, '').replace(/\s*\n\s*/g, ' ')
        if (text) result.push(decode(text))
      }
    }
    if (tag !== null) fail(`unclosed ${String(tag)}`)
    return result
  }
  const nodes = children()
  return nodes.length === 1 ? nodes[0] : nodes
}

function useQuery(load, key, collection) {
  const [value, setValue] = useState({ records: [], loading: true, error: null })
  const current = useRef(0)
  const active = useRef(false)
  const reload = useCallback(async () => {
    const request = ++current.current
    setValue(previous => ({ ...previous, loading: true, error: null }))
    try {
      const records = await load()
      if (active.current && request === current.current) setValue({ records, loading: false, error: null })
      return records
    } catch (error) {
      if (active.current && request === current.current) setValue(previous => ({ ...previous, loading: false, error }))
    }
  }, [key])
  useEffect(() => {
    active.current = true
    reload()
    const unsubscribe = space.on('change', event => {
      if (event.changes.some(change => change.collection === collection)) reload()
    })
    return () => { active.current = false; current.current++; unsubscribe() }
  }, [reload, collection])
  return { ...value, reload }
}
export function useCollection(collection, options = {}) {
  return useQuery(() => space.query(collection, options), JSON.stringify([collection, options]), collection)
}
export function useRecord(collection, id) {
  const result = useQuery(async () => [await space.get(collection, id)], JSON.stringify([collection, id]), collection)
  return { record: result.records[0] ?? null, loading: result.loading, error: result.error, reload: result.reload }
}
export function useSaveState() {
  const [status, setStatus] = useState({ state: 'idle', message: '', current: null })
  const latest = useRef(0)
  const run = useCallback(async fn => {
    const request = ++latest.current
    setStatus({ state: 'saving', message: 'Saving', current: null })
    try {
      const result = await fn()
      if (request === latest.current) setStatus({ state: 'saved', message: 'Saved', current: null })
      return result
    } catch (error) {
      if (request === latest.current) setStatus({ state: error.code === 'conflict' ? 'conflict' : 'failed', message: error.message || 'Save failed', current: error.current ?? null })
      return undefined
    }
  }, [])
  return { ...status, run }
}

let routes = {}
const routeListeners = new Set()
let listening = false
function readRoute() {
  const path = (globalThis.location?.hash || '#/').slice(1).split('?')[0] || '/'
  for (const [pattern, component] of Object.entries(routes)) {
    const names = []
    const expression = pattern.split('/').map(part => {
      if (part.startsWith(':')) { names.push(part.slice(1)); return '([^/]+)' }
      return part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    }).join('/')
    const match = path.match(new RegExp(`^${expression}/?$`))
    if (match) {
      let params
      try { params = Object.fromEntries(names.map((name, i) => [name, decodeURIComponent(match[i + 1])])) }
      catch { continue }
      return { path, params, component, pattern }
    }
  }
  return { path, params: {}, component: routes['*'] ?? null, pattern: null }
}
const routeChanged = () => { for (const cb of routeListeners) cb(readRoute()) }
export function hashRouter(nextRoutes) {
  routes = nextRoutes
  if (!listening && globalThis.addEventListener) {
    globalThis.addEventListener('hashchange', routeChanged)
    listening = true
  }
  routeChanged()
  return {
    get route() { return readRoute() },
    navigate(path) { globalThis.location.hash = '#' + path },
    destroy() {
      if (listening) globalThis.removeEventListener('hashchange', routeChanged)
      listening = false
      routes = {}
      routeChanged()
    }
  }
}
export function useRoute() {
  const [route, setRoute] = useState(readRoute)
  useEffect(() => {
    routeListeners.add(setRoute)
    setRoute(readRoute())
    return () => routeListeners.delete(setRoute)
  }, [])
  return route
}

export function SaveIndicator({ state = 'idle', message }) {
  const labels = { idle: 'Ready', saving: 'Saving', saved: 'Saved', failed: 'Save failed', conflict: 'Changes conflict' }
  const icons = { idle: '○', saving: '◌', saved: '✓', failed: '!', conflict: '!' }
  return html`<span role="status" class=${`space-save space-save-${state}`}><span aria-hidden="true">${icons[state]}</span> ${message || labels[state]}</span>`
}
export function ConflictBanner({ current, onKeepMine, onUseUpdated, message = 'This record changed elsewhere. Choose which version to use.' }) {
  return html`<section role="alert" class="space-conflict"><p>${message}</p><button type="button" onClick=${() => onKeepMine(current)}>Keep mine</button> <button type="button" onClick=${() => onUseUpdated(current)}>Use updated</button></section>`
}
export function EmptyState({ title = 'Nothing here yet', children, action }) {
  return html`<section class="space-empty"><h2>${title}</h2>${children}${action}</section>`
}
export function Nav({ items, label = 'Views' }) {
  const route = useRoute()
  return html`<nav aria-label=${label} class="space-nav">${items.map(item => html`<a href=${'#' + item.path} aria-current=${route.path === item.path ? 'page' : undefined}>${item.label}</a>`)}</nav>`
}
export function RefreshButton() {
  const [run, setRun] = useState(null)
  const [message, setMessage] = useState('')
  const [requesting, setRequesting] = useState(false)
  const observed = useRef(null)
  useEffect(() => space.on('run', update => {
    observed.current = update
    setRun(update)
    setMessage(update.status === 'failed' ? update.error || 'Refresh failed' : update.status === 'blocked' ? 'Refresh is blocked. Check Permissions.' : '')
  }), [])
  const refresh = async () => {
    setRequesting(true)
    setMessage('')
    const before = observed.current
    try {
      const next = await space.refresh()
      if (observed.current === before || observed.current.id !== next.id) setRun(next)
    } catch (error) {
      setMessage(error.code === 'not_granted' ? "Refresh isn't available: approve Refresh in Permissions" : error.message || 'Refresh failed')
    } finally { setRequesting(false) }
  }
  const busy = requesting || ['queued', 'running'].includes(run?.status)
  const labels = { queued: 'Refresh queued', running: 'Refreshing', succeeded: 'Refresh complete', failed: 'Refresh failed', canceled: 'Refresh canceled', blocked: 'Refresh blocked' }
  return html`<span class="space-refresh"><button type="button" disabled=${busy} onClick=${refresh}>${requesting ? 'Requesting refresh' : 'Refresh'}</button> <span role="status">${message || labels[run?.status] || ''}</span></span>`
}
