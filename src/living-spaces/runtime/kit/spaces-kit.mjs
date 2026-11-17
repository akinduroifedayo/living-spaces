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
export function queryPage(collection, options = {}) {
  return space.queryPage(collection, options)
}
export function useCollection(collection, options = {}) {
  return useQuery(() => space.query(collection, options), JSON.stringify([collection, options]), collection)
}
export function useRecord(collection, id) {
  const result = useQuery(async () => [await space.get(collection, id)], JSON.stringify([collection, id]), collection)
  return { record: result.records[0] ?? null, loading: result.loading, error: result.error, reload: result.reload }
}
export function readFreshness() {
  return space.freshness()
}
export function useFreshness() {
  const [value, setValue] = useState({ freshness: null, loading: true, error: null })
  const current = useRef(0)
  const active = useRef(false)
  const reload = useCallback(async () => {
    const request = ++current.current
    setValue(previous => ({ ...previous, loading: true, error: null }))
    try {
      const freshness = await readFreshness()
      if (active.current && request === current.current) setValue({ freshness, loading: false, error: null })
      return freshness
    } catch (error) {
      if (active.current && request === current.current) setValue(previous => ({ ...previous, loading: false, error }))
    }
  }, [])
  useEffect(() => {
    active.current = true
    reload()
    const unsubscribe = space.on('run', reload)
    return () => { active.current = false; current.current++; unsubscribe() }
  }, [reload])
  return { ...value, reload }
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

// Optional DOM bindings. Pair destroy() with the author's component cleanup.
let controlId = 0
const layerManagers = new WeakMap()
const identify = element => element.id || (element.id = `space-control-${++controlId}`)
const enabled = element => !element.matches(':disabled, [aria-disabled="true"]')
function available(element) {
  if (!element?.isConnected || !enabled(element)) return false
  for (let node = element; node?.nodeType === 1; node = node.parentElement) {
    if (node.hidden || node.hasAttribute('inert')) return false
    if (node.localName === 'dialog' && !node.open) return false
    if (node.localName === 'details' && !node.open && !node.querySelector('summary')?.contains(element)) return false
    const style = node.ownerDocument.defaultView.getComputedStyle(node)
    if (style.display === 'none' || style.visibility === 'hidden') return false
  }
  return true
}
const focusable = content => [...content.querySelectorAll('button, input, select, textarea, a[href], summary, [tabindex], [contenteditable="true"]')]
  .filter(element => element.tabIndex >= 0 && available(element))
function nameControl(content, { label, labelledBy }) {
  if (labelledBy) {
    content.setAttribute('aria-labelledby', labelledBy)
    content.removeAttribute('aria-label')
  } else if (typeof label === 'string' && label.trim()) content.setAttribute('aria-label', label)
  else if (!content.getAttribute('aria-label')?.trim() && !content.getAttribute('aria-labelledby')?.trim()) {
    throw new TypeError('A control requires label or labelledBy')
  }
}
function controlListeners() {
  const removals = []
  return {
    on(element, type, listener) {
      element.addEventListener(type, listener)
      removals.push(() => element.removeEventListener(type, listener))
    },
    destroy() { removals.splice(0).forEach(remove => remove()) }
  }
}
function layerManager(doc) {
  if (layerManagers.has(doc)) return layerManagers.get(doc)
  const stack = []
  const blocked = new Map()
  const modal = () => stack.findLast(layer => layer.modal)
  function unblock() {
    for (const [element, value] of blocked) {
      if (value === null) element.removeAttribute('inert')
      else element.setAttribute('inert', value)
    }
    blocked.clear()
  }
  function update() {
    unblock()
    for (let node = modal()?.content; node && node !== doc.body; node = node.parentElement) {
      for (const sibling of node.parentElement?.children || []) {
        if (sibling === node) continue
        blocked.set(sibling, sibling.getAttribute('inert'))
        sibling.setAttribute('inert', '')
      }
    }
  }
  function enter(layer) {
    const target = layer.initialFocus
    const first = target && layer.content.contains(target) && available(target) ? target
      : focusable(layer.content)[0] || layer.content
    first.focus()
  }
  function keyboard(event) {
    if (event.isComposing || event.keyCode === 229) return
    const top = stack.at(-1)
    if (event.key === 'Escape' && top) {
      event.preventDefault()
      event.stopImmediatePropagation()
      top.close()
    } else if (event.key === 'Tab' && modal() && !event.defaultPrevented) {
      const content = modal().content
      const items = focusable(content)
      const index = items.indexOf(doc.activeElement)
      if (!items.length || event.shiftKey && index <= 0 || !event.shiftKey && (index < 0 || index === items.length - 1)) {
        event.preventDefault()
        ;(event.shiftKey ? items.at(-1) : items[0] || content)?.focus()
        if (!items.length) content.focus()
      }
    }
  }
  function focus(event) {
    const layer = modal()
    if (layer && !layer.content.contains(event.target)) enter(layer)
  }
  function click(event) {
    const layer = modal()
    if (layer && !layer.content.contains(event.target)) {
      event.preventDefault()
      event.stopImmediatePropagation()
    }
  }
  const observer = new doc.defaultView.MutationObserver(() => {
    const detached = stack.find(layer => !layer.content.isConnected)
    if (detached) detached.close()
    update()
  })
  const manager = {
    add(layer) {
      if (!stack.length) {
        doc.addEventListener('keydown', keyboard, true)
        doc.addEventListener('focusin', focus, true)
        doc.addEventListener('click', click, true)
        observer.observe(doc.body, { childList: true, subtree: true })
      }
      layer.returns = [layer.trigger, ...stack.slice().reverse().flatMap(entry => entry.returns)]
      stack.push(layer)
      update()
    },
    remove(layer, restore = true) {
      const index = stack.indexOf(layer)
      if (index < 0) return
      // Closing an ancestor dismisses its descendants before returning focus.
      for (const child of stack.slice(index + 1).reverse()) {
        if (layer.content.contains(child.content) || layer.content.contains(child.trigger)) child.close(false)
      }
      stack.splice(index, 1)
      update()
      if (!stack.length) {
        observer.disconnect()
        doc.removeEventListener('keydown', keyboard, true)
        doc.removeEventListener('focusin', focus, true)
        doc.removeEventListener('click', click, true)
      }
      if (restore) {
        const target = layer.returns.find(available)
        if (target) target.focus()
        else if (modal()) enter(modal())
      }
    },
    enter,
    dismiss() { stack.at(-1)?.close() }
  }
  layerManagers.set(doc, manager)
  return manager
}

function bindLayer({ trigger, content, label, labelledBy, initialFocus }, kind) {
  const isDialog = kind === 'dialog'
  if (isDialog && content.localName !== 'dialog') throw new TypeError('Use a native dialog element')
  nameControl(content, { label, labelledBy })
  const manager = layerManager(content.ownerDocument)
  const listeners = controlListeners()
  let opened = false
  let destroyed = false
  trigger.setAttribute('aria-controls', identify(content))
  trigger.setAttribute('aria-haspopup', kind)
  trigger.setAttribute('aria-expanded', 'false')
  content.setAttribute('role', kind)
  content.setAttribute('tabindex', '-1')
  content.hidden = true
  if (isDialog) content.setAttribute('aria-modal', 'true')
  const ownedItems = () => [...content.querySelectorAll('[role="menuitem"]')].filter(item => item.closest('[role="menu"]') === content)
  const items = () => ownedItems().filter(available)
  function rove(item) {
    for (const other of ownedItems()) other.tabIndex = other === item ? 0 : -1
    ;(item || content).focus()
  }
  const layer = { content, trigger, modal: isDialog, initialFocus, close }
  function open(last = false) {
    if (opened || destroyed || !available(trigger)) return
    opened = true
    content.hidden = false
    trigger.setAttribute('aria-expanded', 'true')
    if (isDialog) {
      if (typeof content.showModal === 'function') content.showModal()
      else content.open = true
    }
    manager.add(layer)
    if (isDialog) manager.enter(layer)
    else {
      const choices = items()
      rove(last ? choices.at(-1) : choices[0])
    }
  }
  function close(restore = true) {
    if (!opened) return
    opened = false
    if (isDialog) {
      if (typeof content.close === 'function') content.close()
      else content.open = false
    }
    content.hidden = true
    trigger.setAttribute('aria-expanded', 'false')
    manager.remove(layer, restore)
  }
  listeners.on(trigger, 'click', () => { if (opened) close(); else open() })
  listeners.on(content, 'click', event => {
    const closer = event.target.closest(isDialog ? '[data-close]' : '[role="menuitem"]')
    const owner = closer?.closest(isDialog ? 'dialog' : '[role="menu"]')
    if (owner === content && enabled(closer)) close()
  })
  if (isDialog) {
    listeners.on(content, 'cancel', event => {
      // The document stack handles keyboard Escape, including nested menus.
      event.preventDefault()
      manager.dismiss()
    })
    listeners.on(content, 'close', () => { if (!content.open) close() })
  } else {
    for (const item of ownedItems()) item.tabIndex = -1
    listeners.on(trigger, 'keydown', event => {
      if (['ArrowDown', 'ArrowUp'].includes(event.key)) {
        event.preventDefault()
        open(event.key === 'ArrowUp')
      }
    })
    listeners.on(content, 'keydown', event => {
      if (event.defaultPrevented || event.isComposing || event.altKey || event.ctrlKey || event.metaKey || event.target.closest('[role="menu"]') !== content) return
      const choices = items()
      const index = choices.indexOf(content.ownerDocument.activeElement)
      let next
      if (event.key === 'ArrowDown') next = choices[(index + 1) % choices.length]
      else if (event.key === 'ArrowUp') next = choices[(index - 1 + choices.length) % choices.length]
      else if (event.key === 'Home') next = choices[0]
      else if (event.key === 'End') next = choices.at(-1)
      else if (event.key === 'Tab') { close(); return }
      else if (['Enter', ' '].includes(event.key) && choices[index]) {
        event.preventDefault()
        choices[index].click()
        return
      } else if (event.key.length === 1 && event.key.trim()) {
        next = [...choices.slice(index + 1), ...choices.slice(0, index + 1)]
          .find(item => (item.getAttribute('aria-label') || item.textContent).trim().toLowerCase().startsWith(event.key.toLowerCase()))
      }
      if (next) { event.preventDefault(); rove(next) }
    })
  }
  return { open, close, destroy() {
    if (destroyed) return
    destroyed = true
    close()
    listeners.destroy()
  } }
}
export function bindDialog(options) { return bindLayer(options, 'dialog') }
export function bindDrawer(options) { return bindLayer(options, 'dialog') }
export function bindMenu(options) { return bindLayer(options, 'menu') }

export function bindTabs({ list, tabs, panels, label, labelledBy, orientation = 'horizontal' }) {
  if (!tabs.length || tabs.length !== panels.length || !['horizontal', 'vertical'].includes(orientation)) {
    throw new TypeError('Tabs require matching tabs and panels and a valid orientation')
  }
  nameControl(list, { label, labelledBy })
  const listeners = controlListeners()
  list.setAttribute('role', 'tablist')
  list.setAttribute('aria-orientation', orientation)
  tabs.forEach((tab, index) => {
    tab.setAttribute('role', 'tab')
    tab.setAttribute('aria-controls', identify(panels[index]))
    panels[index].setAttribute('role', 'tabpanel')
    panels[index].setAttribute('aria-labelledby', identify(tab))
    panels[index].tabIndex = 0
  })
  function select(tab, focus = false) {
    tabs.forEach((item, index) => {
      item.tabIndex = item === tab ? 0 : -1
      item.setAttribute('aria-selected', String(item === tab))
      panels[index].hidden = item !== tab
    })
    if (focus) tab?.focus()
  }
  select(tabs.find(tab => enabled(tab) && tab.getAttribute('aria-selected') === 'true') || tabs.find(enabled))
  listeners.on(list, 'click', event => {
    const tab = tabs.find(item => item.contains(event.target))
    if (tab && enabled(tab)) select(tab, true)
  })
  listeners.on(list, 'keydown', event => {
    if (event.isComposing || event.altKey || event.ctrlKey || event.metaKey) return
    const choices = tabs.filter(available)
    const current = choices.indexOf(list.ownerDocument.activeElement)
    if (current < 0) return
    const previous = orientation === 'vertical' ? 'ArrowUp' : 'ArrowLeft'
    const next = orientation === 'vertical' ? 'ArrowDown' : 'ArrowRight'
    let tab
    if (event.key === previous) tab = choices[(current - 1 + choices.length) % choices.length]
    else if (event.key === next) tab = choices[(current + 1) % choices.length]
    else if (event.key === 'Home') tab = choices[0]
    else if (event.key === 'End') tab = choices.at(-1)
    if (tab) { event.preventDefault(); select(tab, true) }
  })
  return { destroy: listeners.destroy }
}

export function bindDisclosure({ content }) {
  const trigger = content.querySelector(':scope > summary')
  if (content.localName !== 'details' || !trigger) throw new TypeError('Use details with a direct summary')
  const manager = layerManager(content.ownerDocument)
  const listeners = controlListeners()
  let registered = false
  let destroyed = false
  const layer = { content, trigger, modal: false, close }
  function sync() {
    if (destroyed) return
    if (content.open && !registered) { registered = true; manager.add(layer) }
    else if (!content.open && registered) { registered = false; manager.remove(layer) }
  }
  function open() { if (!destroyed) { content.open = true; sync() } }
  function close(restore = true) {
    content.open = false
    if (registered) { registered = false; manager.remove(layer, restore) }
  }
  listeners.on(content, 'toggle', sync)
  listeners.on(trigger, 'click', () => queueMicrotask(sync))
  sync()
  return { open, close, destroy() {
    if (destroyed) return
    destroyed = true
    close()
    listeners.destroy()
  } }
}
