import test from 'node:test'
import assert from 'node:assert/strict'
import { registerHooks } from 'node:module'
import { setImmediate as tick } from 'node:timers/promises'

const moduleURL = new URL('../../../src/living-spaces/runtime/kit/motion.mjs', import.meta.url)
let imported
async function capability() {
  imported ??= import(moduleURL.href).then(module => ({ module }), error => ({ error }))
  const result = await imported
  assert.ok(!result.error, `Q06 optional motion capability must import: ${result.error?.message}`)
  assert.equal(typeof result.module.createMotionScope, 'function', 'Q06 exports createMotionScope')
  return result.module.createMotionScope
}

class Signals extends EventTarget {
  listeners = new Map()
  addEventListener(type, callback, options) {
    super.addEventListener(type, callback, options)
    if (!this.listeners.has(type)) this.listeners.set(type, new Set())
    this.listeners.get(type).add(callback)
  }
  removeEventListener(type, callback, options) {
    super.removeEventListener(type, callback, options)
    this.listeners.get(type)?.delete(callback)
  }
  callbacks(type) {
    return [...(this.listeners.get(type) ?? [])]
  }
}

class Animation extends Signals {
  playState = 'running'
  cancelCount = 0
  currentTime = 0
  onfinish = null
  oncancel = null
  constructor(element, keyframes, options) {
    super()
    this.element = element
    this.keyframes = keyframes
    this.options = options
    this.effect = { target: element, getKeyframes: () => keyframes }
    this.finished = new Promise((resolve, reject) => { this.resolve = resolve; this.reject = reject })
    this.finished.catch(() => {})
  }
  queuedFinish() {
    const callbacks = this.callbacks('finish')
    const onfinish = this.onfinish
    return () => {
      const event = new Event('finish')
      onfinish?.call(this, event)
      for (const callback of callbacks) {
        if (typeof callback === 'function') callback.call(this, event)
        else callback.handleEvent(event)
      }
    }
  }
  finish() {
    this.playState = 'finished'
    this.resolve(this)
    queueMicrotask(this.queuedFinish())
  }
  cancel() {
    this.cancelCount++
    this.playState = 'idle'
    this.reject(new DOMException('Animation canceled', 'AbortError'))
    queueMicrotask(() => {
      this.dispatchEvent(new Event('cancel'))
      this.oncancel?.call(this, new Event('cancel'))
    })
  }
  commitStyles() {
    Object.assign(this.element.style, lastFrame(this.keyframes))
  }
}

function firstFrame(keyframes) {
  if (Array.isArray(keyframes)) return keyframes[0]
  return Object.fromEntries(Object.entries(keyframes).map(([key, value]) => [key, Array.isArray(value) ? value[0] : value]))
}
function lastFrame(keyframes) {
  if (Array.isArray(keyframes)) return keyframes.at(-1)
  return Object.fromEntries(Object.entries(keyframes).map(([key, value]) => [key, Array.isArray(value) ? value.at(-1) : value]))
}

async function fixture(t, { reduced = false, waapi = 'available' } = {}) {
  const createMotionScope = await capability()
  const observers = new Set(), animations = [], scopes = []
  const media = new Signals()
  media.matches = reduced
  media.media = '(prefers-reduced-motion: reduce)'
  media.addListener = callback => media.addEventListener('change', callback)
  media.removeListener = callback => media.removeEventListener('change', callback)
  const notifyRemoval = (target, removed) => queueMicrotask(() => {
    for (const observer of observers) {
      if (observer.target === target || observer.target?.contains(target)) {
        observer.callback([{ type: 'childList', target, removedNodes: [removed], addedNodes: [] }], observer)
      }
    }
  })
  class Element extends Signals {
    nodeType = 1
    tagName = 'DIV'
    parentNode = null
    children = []
    hidden = false
    inert = false
    disabled = false
    textContent = ''
    attributes = new Map()
    style = {
      transform: '', opacity: '', display: '', color: '',
      setProperty(name, value) { this[name] = String(value) },
      getPropertyValue(name) { return this[name] ?? '' },
      removeProperty(name) { const value = this[name]; this[name] = ''; return value }
    }
    constructor() {
      super()
      this.ownerDocument = document
      if (waapi === 'unavailable') this.animate = undefined
    }
    get childNodes() { return this.children }
    get parentElement() { return this.parentNode }
    get isConnected() { return this === document.documentElement || !!this.parentNode?.isConnected }
    contains(element) { return this === element || this.children.some(child => child.contains(element)) }
    append(...children) {
      for (const child of children) {
        if (child.parentNode) child.remove()
        child.parentNode = this
        this.children.push(child)
      }
    }
    appendChild(child) { this.append(child); return child }
    removeChild(child) {
      this.children.splice(this.children.indexOf(child), 1)
      child.parentNode = null
      notifyRemoval(this, child)
      return child
    }
    remove() { this.parentNode?.removeChild(this) }
    setAttribute(name, value) {
      this.attributes.set(name, String(value))
      if (name === 'hidden' || name === 'inert') this[name] = true
    }
    getAttribute(name) { return this.attributes.get(name) ?? null }
    hasAttribute(name) { return this.attributes.has(name) || ((name === 'hidden' || name === 'inert') && this[name]) }
    removeAttribute(name) {
      this.attributes.delete(name)
      if (name === 'hidden' || name === 'inert') this[name] = false
    }
    toggleAttribute(name, force = !this.hasAttribute(name)) {
      if (force) this.setAttribute(name, '')
      else this.removeAttribute(name)
      return force
    }
    querySelectorAll() { return this.children.flatMap(child => [child, ...child.querySelectorAll()]) }
    getBoundingClientRect() { return { x: 0, y: 0, top: 0, left: 0, right: 200, bottom: 80, width: 200, height: 80 } }
    getAnimations() { return animations.filter(animation => animation.element === this && animation.playState !== 'idle') }
    animate(keyframes, options) {
      if (waapi === 'throwing') throw new DOMException('WAAPI unavailable', 'NotSupportedError')
      const animation = new Animation(this, keyframes, options)
      animations.push(animation)
      return animation
    }
  }
  class MutationObserver {
    constructor(callback) { this.callback = callback }
    observe(target, options) { this.target = target; this.options = options; observers.add(this) }
    disconnect() { observers.delete(this) }
    takeRecords() { return [] }
  }
  const document = { activeElement: null }
  const getComputedStyle = element => {
    const animation = animations.findLast(animation => animation.element === element && animation.playState === 'running')
    const values = { transform: element.style.transform || 'none', opacity: element.style.opacity || '1', ...animation?.sample }
    return { ...values, getPropertyValue: name => values[name] ?? '' }
  }
  const window = { matchMedia: () => media, getComputedStyle, MutationObserver, Element, HTMLElement: Element }
  Object.assign(document, { defaultView: window, createElement: () => new Element() })
  document.documentElement = new Element()
  document.body = new Element()
  document.documentElement.append(document.body)
  const globals = { window, document, matchMedia: window.matchMedia, getComputedStyle, MutationObserver, Element, HTMLElement: Element }
  const descriptors = Object.fromEntries(Object.keys(globals).map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]))
  for (const [key, value] of Object.entries(globals)) Object.defineProperty(globalThis, key, { configurable: true, writable: true, value })
  t.after(() => {
    try { for (const scope of scopes) scope.dispose() }
    finally {
      for (const [key, descriptor] of Object.entries(descriptors)) {
        if (descriptor) Object.defineProperty(globalThis, key, descriptor)
        else delete globalThis[key]
      }
    }
  })
  const root = new Element()
  document.body.append(root)
  const shell = (parent = root) => { const element = new Element(); parent.append(element); return element }
  const scope = (target = root) => { const value = createMotionScope(target); scopes.push(value); return value }
  return {
    root, shell, scope, animations, media, observers, document,
    reduce(value) {
      media.matches = value
      const event = new Event('change')
      Object.defineProperty(event, 'matches', { value })
      media.dispatchEvent(event)
    }
  }
}

function visible(element) {
  assert.equal(element.hidden, false, 'latest open target is visible')
  assert.equal(element.inert, false, 'latest open target accepts input')
}
function closed(element) {
  assert.equal(element.hidden, true, 'latest closed target is hidden')
  assert.equal(element.inert, true, 'latest closed target is inert')
}
function transition(f, scope, element, recipe = 'panel') {
  scope.present(element, { recipe, open: true })
  scope.present(element, { recipe, open: false })
  const animation = f.animations.at(-1)
  assert.ok(animation, 'a changed presence target produces observable motion')
  return animation
}

test('optional motion imports offline without a framework or DOM at import time', async t => {
  if (typeof globalThis.fetch === 'function') {
    t.mock.method(globalThis, 'fetch', () => { throw new Error('Optional motion must import without network access') })
  }
  const hooks = registerHooks({
    resolve(specifier, context, next) {
      if (/^(?:https?:|react(?:\/|$)|preact(?:\/|$)|vue(?:\/|$)|svelte(?:\/|$)|solid-js(?:\/|$))/.test(specifier)
          || /\/vendor\/(?:preact|hooks)\.mjs$/.test(specifier)) {
        throw new Error(`Optional motion must not require framework or network import ${specifier}`)
      }
      return next(specifier, context)
    }
  })
  try { await capability() }
  finally { hooks.deregister() }
})

test('scope exposes the four public operations without a framework mount', async t => {
  const f = await fixture(t)
  const scope = f.scope()
  for (const name of ['press', 'present', 'beginConfirmation', 'dispose']) assert.equal(typeof scope[name], 'function')
})

test('initial open panel and disclosure settle without an entrance', async t => {
  const f = await fixture(t), scope = f.scope()
  for (const recipe of ['panel', 'disclosure']) {
    const element = f.shell()
    element.hidden = element.inert = true
    scope.present(element, { recipe, open: true })
    visible(element)
  }
  assert.equal(f.animations.length, 0)
})

test('initial closed panel and disclosure settle without an exit', async t => {
  const f = await fixture(t), scope = f.scope()
  for (const recipe of ['panel', 'disclosure']) {
    const element = f.shell()
    scope.present(element, { recipe, open: false })
    closed(element)
  }
  assert.equal(f.animations.length, 0)
})

test('opening accepts input synchronously while closing hides only after completion', async t => {
  const f = await fixture(t), scope = f.scope(), element = f.shell()
  scope.present(element, { recipe: 'panel', open: false })
  scope.present(element, { recipe: 'panel', open: true })
  visible(element)
  assert.ok(f.animations.length > 0)
  f.animations.at(-1).finish()
  await tick()
  scope.present(element, { recipe: 'panel', open: false })
  assert.equal(element.inert, true)
  assert.equal(element.hidden, false, 'a closing panel stays painted until its completion')
  f.animations.at(-1).finish()
  await tick()
  closed(element)
})

test('equivalent targets are no-ops during a transition and after completion', async t => {
  const f = await fixture(t), scope = f.scope(), element = f.shell()
  const animation = transition(f, scope, element)
  const count = f.animations.length
  scope.present(element, { recipe: 'panel', open: false })
  assert.equal(f.animations.length, count)
  assert.equal(animation.cancelCount, 0)
  animation.finish()
  await tick()
  scope.present(element, { recipe: 'panel', open: false })
  assert.equal(f.animations.length, count)
  closed(element)
})

test('polling equivalent mounted targets never replays entrances or confirmations', async t => {
  const f = await fixture(t), scope = f.scope()
  const list = [f.shell(), f.shell(), f.shell()]
  for (const element of list) scope.present(element, { recipe: 'disclosure', open: true })
  for (let refresh = 0; refresh < 20; refresh++) {
    for (const element of list) scope.present(element, { recipe: 'disclosure', open: true })
  }
  await tick()
  assert.equal(f.animations.length, 0)
  list.forEach(visible)
})

test('repeated panel and disclosure reversals settle only the newest target', async t => {
  const f = await fixture(t), scope = f.scope()
  for (const recipe of ['panel', 'disclosure']) {
    const element = f.shell()
    scope.present(element, { recipe, open: false })
    const obsolete = []
    for (const open of [true, false, true, false, true]) {
      scope.present(element, { recipe, open })
      const latest = f.animations.at(-1)
      assert.ok(latest)
      obsolete.push({ animation: latest, deliver: latest.queuedFinish() })
    }
    const newest = obsolete.pop().animation
    assert.ok(obsolete.every(({ animation }) => animation.cancelCount > 0))
    newest.finish()
    await tick()
    for (const old of obsolete.reverse()) { old.animation.finish(); old.deliver() }
    await tick()
    visible(element)
    scope.present(element, { recipe, open: false })
    f.animations.at(-1).finish()
    await tick()
    closed(element)
  }
})

test('a finish already queued before reversal cannot hide the newly opened panel', async t => {
  const f = await fixture(t), scope = f.scope(), element = f.shell()
  const old = transition(f, scope, element)
  old.finish()
  scope.present(element, { recipe: 'panel', open: true })
  await tick()
  visible(element)
  f.animations.at(-1).finish()
  await tick()
  visible(element)
})

test('replacement starts from the currently painted transform and opacity', async t => {
  const f = await fixture(t), scope = f.scope(), element = f.shell()
  const old = transition(f, scope, element)
  old.sample = { transform: 'matrix(1, 0, 0, 1, 0, 7)', opacity: '0.37' }
  scope.present(element, { recipe: 'panel', open: true })
  const replacement = f.animations.at(-1)
  assert.notEqual(replacement, old)
  assert.equal(old.cancelCount, 1)
  const start = firstFrame(replacement.keyframes)
  assert.equal(start.transform, old.sample.transform)
  assert.equal(Number(start.opacity), 0.37)
})

test('press feedback never disables an immediate repeated action', async t => {
  const f = await fixture(t), scope = f.scope(), button = f.shell()
  let accepted = 0
  button.addEventListener('click', () => { scope.press(button, true); accepted++ })
  button.dispatchEvent(new Event('click'))
  button.dispatchEvent(new Event('click'))
  assert.equal(accepted, 2)
  assert.equal(button.disabled, false)
  assert.equal(button.inert, false)
  assert.equal(button.hidden, false)
  assert.ok(f.animations.length > 0)
  assert.ok(f.animations.some(animation => animation.playState === 'running'), 'actions arrive before motion completes')
})

test('repeated press targets do not restart and release survives an obsolete completion', async t => {
  const f = await fixture(t), scope = f.scope(), element = f.shell()
  scope.press(element, true)
  const pressed = f.animations.at(-1)
  assert.ok(pressed)
  const oldFinish = pressed.queuedFinish(), count = f.animations.length
  scope.press(element, true)
  assert.equal(f.animations.length, count)
  assert.equal(pressed.cancelCount, 0)
  scope.press(element, false)
  const released = f.animations.at(-1)
  assert.notEqual(released, pressed)
  assert.ok(pressed.cancelCount > 0)
  released.finish()
  await tick()
  const settled = { transform: element.style.transform, opacity: element.style.opacity }
  oldFinish()
  pressed.finish()
  await tick()
  assert.deepEqual({ transform: element.style.transform, opacity: element.style.opacity }, settled)
  assert.equal(element.disabled, false)
})

test('confirmation waits for an explicit authoritative report and pulses exactly once', async t => {
  const f = await fixture(t), scope = f.scope(), decoration = f.shell()
  decoration.textContent = 'Saving'
  const report = scope.beginConfirmation(decoration)
  assert.equal(typeof report, 'function')
  await tick()
  assert.equal(f.animations.length, 0)
  decoration.textContent = 'Saved'
  report('confirmed')
  assert.equal(f.animations.length, 1)
  report('confirmed')
  report('failed')
  assert.equal(f.animations.length, 1)
  f.animations[0].finish()
  await tick()
  report('confirmed')
  assert.equal(f.animations.length, 1)
  assert.equal(decoration.textContent, 'Saved')
})

test('failed reports never celebrate and consume their one-shot reporter', async t => {
  const f = await fixture(t), scope = f.scope(), decoration = f.shell()
  decoration.textContent = 'Save failed'
  const report = scope.beginConfirmation(decoration)
  report('failed')
  report('confirmed')
  await tick()
  assert.equal(f.animations.length, 0)
  assert.equal(decoration.textContent, 'Save failed')
  scope.beginConfirmation(decoration)('confirmed')
  assert.equal(f.animations.length, 1, 'the same fixture can observe genuine confirmed feedback')
})

test('conflict reports never celebrate or rewrite the authoritative status', async t => {
  const f = await fixture(t), scope = f.scope(), decoration = f.shell()
  decoration.textContent = 'Record changed. Review before retrying.'
  const report = scope.beginConfirmation(decoration)
  report('conflict')
  report('confirmed')
  await tick()
  assert.equal(f.animations.length, 0)
  assert.equal(decoration.textContent, 'Record changed. Review before retrying.')
  scope.beginConfirmation(decoration)('confirmed')
  assert.equal(f.animations.length, 1)
})

test('uncertain reports never celebrate or turn uncertainty into Saved', async t => {
  const f = await fixture(t), scope = f.scope(), decoration = f.shell()
  decoration.textContent = 'Confirmation unavailable'
  const report = scope.beginConfirmation(decoration)
  report('uncertain')
  report('confirmed')
  await tick()
  assert.equal(f.animations.length, 0)
  assert.equal(decoration.textContent, 'Confirmation unavailable')
  scope.beginConfirmation(decoration)('confirmed')
  assert.equal(f.animations.length, 1)
})

test('superseded confirmation reporters cannot pulse before or after the newest report', async t => {
  const f = await fixture(t), scope = f.scope(), decoration = f.shell()
  const stale = scope.beginConfirmation(decoration)
  const latest = scope.beginConfirmation(decoration)
  stale('confirmed')
  assert.equal(f.animations.length, 0)
  latest('confirmed')
  assert.equal(f.animations.length, 1)
  stale('confirmed')
  assert.equal(f.animations.length, 1)
})

test('a new attempt cancels an existing pulse and late completion cannot corrupt its successor', async t => {
  const f = await fixture(t), scope = f.scope(), decoration = f.shell()
  scope.beginConfirmation(decoration)('confirmed')
  const old = f.animations.at(-1)
  assert.ok(old)
  const deliver = old.queuedFinish()
  const latest = scope.beginConfirmation(decoration)
  assert.ok(old.cancelCount > 0)
  latest('confirmed')
  const current = f.animations.at(-1)
  assert.notEqual(current, old)
  deliver()
  old.finish()
  await tick()
  assert.equal(current.cancelCount, 0)
  assert.equal(current.playState, 'running')
})

test('confirmation attempts on different decorations remain independent', async t => {
  const f = await fixture(t), scope = f.scope(), first = f.shell(), second = f.shell()
  const a = scope.beginConfirmation(first), b = scope.beginConfirmation(second)
  b('failed')
  a('confirmed')
  assert.equal(f.animations.length, 1)
  assert.equal(f.animations[0].element, first)
})

test('dispose settles the latest semantic target and invalidates queued callbacks and reporters', async t => {
  const f = await fixture(t), scope = f.scope(), closing = f.shell(), opening = f.shell(), decoration = f.shell()
  const closeAnimation = transition(f, scope, closing)
  scope.present(opening, { recipe: 'panel', open: false })
  scope.present(opening, { recipe: 'panel', open: true })
  const owned = [...f.animations], callbacks = owned.map(animation => animation.queuedFinish())
  const report = scope.beginConfirmation(decoration)
  const count = f.animations.length
  scope.dispose()
  closed(closing)
  visible(opening)
  assert.ok(owned.every(animation => animation.cancelCount > 0))
  report('confirmed')
  for (const callback of callbacks) callback()
  closeAnimation.finish()
  await tick()
  assert.equal(f.animations.length, count)
  closed(closing)
  visible(opening)
})

test('dispose is idempotent and removes its preference listeners and removal observers', async t => {
  const f = await fixture(t), scope = f.scope(), element = f.shell()
  const animation = transition(f, scope, element)
  assert.ok(f.media.callbacks('change').length > 0, 'live preference changes have a listener')
  scope.dispose()
  const cancellations = animation.cancelCount
  assert.doesNotThrow(() => scope.dispose())
  assert.equal(animation.cancelCount, cancellations)
  assert.equal(f.media.callbacks('change').length, 0)
  assert.equal(f.observers.size, 0)
  const count = f.animations.length
  f.reduce(true)
  f.reduce(false)
  await tick()
  assert.equal(f.animations.length, count)
  closed(element)
})

test('late disposed reporters cannot reach a replacement scope on the same shell', async t => {
  const f = await fixture(t), first = f.scope(), decoration = f.shell()
  const late = first.beginConfirmation(decoration)
  first.dispose()
  const replacement = f.scope()
  const current = replacement.beginConfirmation(decoration)
  late('confirmed')
  assert.equal(f.animations.length, 0)
  current('confirmed')
  assert.equal(f.animations.length, 1)
})

test('removing a shell cancels its motion and releases ownership for a new scope', async t => {
  const f = await fixture(t), first = f.scope(), element = f.shell()
  const old = transition(f, first, element), deliver = old.queuedFinish()
  const late = first.beginConfirmation(f.shell(element))
  element.remove()
  await tick()
  assert.ok(old.cancelCount > 0)
  const count = f.animations.length
  late('confirmed')
  assert.equal(f.animations.length, count)
  f.root.append(element)
  const next = f.scope()
  assert.doesNotThrow(() => next.present(element, { recipe: 'panel', open: true }))
  deliver()
  old.finish()
  await tick()
  visible(element)
})

test('removing a subtree cleans every owned descendant but preserves a mounted sibling', async t => {
  const f = await fixture(t), scope = f.scope(), group = f.shell(), child = f.shell(group), sibling = f.shell()
  const removed = transition(f, scope, child)
  const surviving = transition(f, scope, sibling)
  group.remove()
  await tick()
  assert.ok(removed.cancelCount > 0)
  assert.equal(surviving.cancelCount, 0)
  assert.equal(surviving.playState, 'running')
  surviving.finish()
  await tick()
  closed(sibling)
})

test('already detached or out-of-root elements cannot acquire motion work', async t => {
  const f = await fixture(t), scope = f.scope(), detached = f.shell(), outside = f.shell(f.document.body)
  detached.remove()
  for (const element of [detached, outside]) {
    const before = { hidden: element.hidden, inert: element.inert, transform: element.style.transform }
    for (const call of [
      () => scope.press(element, true),
      () => scope.present(element, { recipe: 'panel', open: false }),
      () => { const report = scope.beginConfirmation(element); if (typeof report === 'function') report('confirmed') }
    ]) {
      try { call() } catch (error) { assert.ok(error instanceof Error) }
    }
    assert.deepEqual({ hidden: element.hidden, inert: element.inert, transform: element.style.transform }, before)
  }
  assert.equal(f.animations.length, 0)
  scope.press(f.shell(), true)
  assert.ok(f.animations.length > 0)
})

test('reduced motion before mount settles every recipe without forced movement', async t => {
  const f = await fixture(t, { reduced: true }), scope = f.scope(), element = f.shell(), decoration = f.shell()
  for (const recipe of ['panel', 'disclosure']) {
    scope.present(element, { recipe, open: false })
    closed(element)
    scope.present(element, { recipe, open: true })
    visible(element)
  }
  scope.press(f.shell(), true)
  scope.press(f.shell(), false)
  decoration.textContent = 'Saved'
  scope.beginConfirmation(decoration)('confirmed')
  await tick()
  assert.equal(f.animations.length, 0)
  assert.equal(decoration.textContent, 'Saved')
})

test('live reduced-motion changes synchronously cancel work and settle the latest targets', async t => {
  const f = await fixture(t), scope = f.scope(), element = f.shell(), decoration = f.shell()
  transition(f, scope, element)
  scope.beginConfirmation(decoration)('confirmed')
  const owned = [...f.animations], callbacks = owned.map(animation => animation.queuedFinish())
  f.reduce(true)
  closed(element)
  assert.ok(owned.every(animation => animation.cancelCount > 0))
  const count = f.animations.length
  scope.present(element, { recipe: 'panel', open: true })
  visible(element)
  scope.beginConfirmation(decoration)('confirmed')
  for (const callback of callbacks) callback()
  await tick()
  assert.equal(f.animations.length, count)
  visible(element)
  f.reduce(false)
  assert.equal(f.animations.length, count, 'preference changes alone never replay motion')
  scope.present(element, { recipe: 'panel', open: false })
  assert.ok(f.animations.length > count, 'future deliberate changes may animate again')
})

test('unavailable WAAPI preserves immediate usable semantic end states', async t => {
  const f = await fixture(t, { waapi: 'unavailable' }), scope = f.scope(), element = f.shell(), decoration = f.shell()
  for (const recipe of ['panel', 'disclosure']) {
    assert.doesNotThrow(() => scope.present(element, { recipe, open: true }))
    visible(element)
    assert.doesNotThrow(() => scope.present(element, { recipe, open: false }))
    closed(element)
  }
  assert.doesNotThrow(() => { scope.press(decoration, true); scope.press(decoration, false) })
  decoration.textContent = 'Saved'
  assert.doesNotThrow(() => scope.beginConfirmation(decoration)('confirmed'))
  assert.equal(decoration.textContent, 'Saved')
  assert.equal(decoration.disabled, false)
  assert.equal(f.animations.length, 0)
})

test('throwing WAAPI preserves immediate semantic end states without false save feedback', async t => {
  const f = await fixture(t, { waapi: 'throwing' }), scope = f.scope(), element = f.shell(), decoration = f.shell()
  scope.present(element, { recipe: 'panel', open: false })
  assert.doesNotThrow(() => scope.present(element, { recipe: 'panel', open: true }))
  visible(element)
  assert.doesNotThrow(() => scope.present(element, { recipe: 'panel', open: false }))
  closed(element)
  assert.doesNotThrow(() => scope.press(decoration, true))
  decoration.textContent = 'Save failed'
  assert.doesNotThrow(() => scope.beginConfirmation(decoration)('failed'))
  assert.equal(decoration.textContent, 'Save failed')
  assert.doesNotThrow(() => scope.beginConfirmation(decoration)('confirmed'))
  assert.equal(decoration.textContent, 'Save failed', 'decoration never authors essential status text')
})

test('a shell has exclusive ownership across concurrent scopes until its owner disposes', async t => {
  const f = await fixture(t), first = f.scope(), second = f.scope(), element = f.shell(), other = f.shell()
  const owned = transition(f, first, element), count = f.animations.length
  assert.throws(() => second.present(element, { recipe: 'panel', open: true }))
  assert.equal(f.animations.length, count)
  assert.equal(owned.cancelCount, 0)
  assert.doesNotThrow(() => second.press(other, true))
  first.dispose()
  assert.doesNotThrow(() => second.present(element, { recipe: 'panel', open: true }))
  visible(element)
})

test('cleanup and supersession preserve unrelated animations on the same shell', async t => {
  const f = await fixture(t), scope = f.scope(), element = f.shell()
  const unrelated = element.animate([{ color: 'red' }, { color: 'blue' }], { duration: 1000 })
  transition(f, scope, element)
  scope.present(element, { recipe: 'panel', open: true })
  assert.equal(unrelated.cancelCount, 0)
  const removed = f.shell()
  const removedUnrelated = removed.animate([{ color: 'red' }, { color: 'blue' }], { duration: 1000 })
  const removedOwned = transition(f, scope, removed)
  removed.remove()
  await tick()
  assert.ok(removedOwned.cancelCount > 0)
  assert.equal(removedUnrelated.cancelCount, 0)
  scope.dispose()
  await tick()
  assert.equal(unrelated.cancelCount, 0)
  assert.equal(unrelated.playState, 'running')
  assert.equal(removedUnrelated.cancelCount, 0)
  unrelated.cancel()
  removedUnrelated.cancel()
})

test('motion changes only transform and opacity while preserving caller focus ARIA and styles', async t => {
  const f = await fixture(t), scope = f.scope(), element = f.shell(), trigger = f.shell(), decoration = f.shell()
  element.style.color = 'rebeccapurple'
  element.setAttribute('aria-labelledby', 'caller-label')
  trigger.setAttribute('aria-expanded', 'true')
  f.document.activeElement = trigger
  transition(f, scope, element, 'disclosure')
  scope.press(f.shell(), true)
  scope.beginConfirmation(decoration)('confirmed')
  for (const animation of f.animations) {
    const frames = Array.isArray(animation.keyframes) ? animation.keyframes : [animation.keyframes]
    for (const frame of frames) {
      for (const property of Object.keys(frame)) {
        assert.ok(['transform', 'opacity', 'offset', 'easing', 'composite'].includes(property), `unexpected animated property ${property}`)
      }
    }
  }
  scope.dispose()
  await tick()
  assert.equal(element.style.color, 'rebeccapurple')
  assert.equal(element.getAttribute('aria-labelledby'), 'caller-label')
  assert.equal(trigger.getAttribute('aria-expanded'), 'true')
  assert.equal(f.document.activeElement, trigger)
  closed(element)
})
