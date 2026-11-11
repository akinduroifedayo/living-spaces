import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { spaceLoader, projectResolver } from '../../../src/guest/loader.mjs'

// These platform doubles exercise closure ownership. Real event provenance needs Chrome.
function fixture() {
  const messages = []
  const context = vm.createContext({ structuredClone, record: value => messages.push(structuredClone(value)) })
  const driver = vm.runInContext(`(() => {
    const events = new WeakMap(), ports = new WeakMap(), listeners = new Map(), tasks = []
    const get = events.get.bind(events), portGet = ports.get.bind(ports)
    class Event {
      constructor(type) {
        events.set(this, { type, trusted: false, phase: 0 })
        Object.defineProperty(this, 'isTrusted', { get() { return get(this).trusted } })
      }
      get type() { return get(this).type }
      get eventPhase() { return get(this).phase }
      stopImmediatePropagation() { get(this).stopped = true }
    }
    class MessageEvent extends Event {
      constructor(type, fields) { super(type); Object.assign(get(this), fields) }
      get data() { return get(this).data }
      get source() { return get(this).source }
      get ports() { return get(this).ports }
    }
    class MessagePort {
      constructor() { ports.set(this, { handler: null, closed: false }) }
      set onmessage(fn) { portGet(this).handler = fn }
      get onmessage() { return portGet(this).handler }
      postMessage(value) { record(value) }
      close() { portGet(this).closed = true }
    }
    const element = tag => ({ tag, attributes: [], style: {}, children: [], setAttribute(k, v) { this[k] = v }, append(...nodes) { this.children.push(...nodes) }, replaceChildren(...nodes) { this.children = nodes } })
    const window = { parent: {}, setTimeout: fn => tasks.push(fn), addEventListener(name, cb) {
      const list = listeners.get(name) || []; list.push(cb); listeners.set(name, list)
    }, removeEventListener(name, cb) { listeners.set(name, (listeners.get(name) || []).filter(fn => fn !== cb)) } }
    const document = { head: element('head'), body: element('body'), createElement: element, addEventListener() {} }
    Object.assign(globalThis, { Event, MessageEvent, MessagePort, window, document,
      crypto: { randomUUID: () => 'fixture-activation' }, console: { warn() {}, error() {} },
      setInterval() {}, clearInterval() {} })
    const port = new MessagePort()
    const dispatch = event => {
      get(event).phase = 1
      for (const cb of [...(listeners.get(get(event).type) || [])]) {
        cb(event)
        if (get(event).stopped) break
      }
      get(event).phase = 0
    }
    return {
      boot() {
        dispatch(new MessageEvent('message', { source: window.parent, ports: [port], data: {
          type: 'space-boot', v: 1, grants: [], bundle: { space: { id: 'fixture' }, rev: 1, manifest: {}, files: [] }
        } }))
      },
      flush() { while (tasks.length) tasks.shift()() },
      click(fn) {
        const event = new Event('click'); get(event).trusted = true; get(event).phase = 1
        for (const cb of listeners.get('click') || []) cb(event)
        try { fn(event) } finally { get(event).phase = 0 }
        return event
      },
      replay(event, fn) { get(event).trusted = false; get(event).phase = 1; try { fn() } finally { get(event).phase = 0 } },
      reply(data) { portGet(port).handler(new MessageEvent('message', { data })) },
      closed() { return portGet(port).closed }
    }
  })()`, context)
  vm.runInContext(`(${spaceLoader.toString()})((${projectResolver.toString()})())`, context)
  vm.runInContext('globalThis.observedBoot = 0; window.addEventListener("message", () => observedBoot++)', context)
  driver.boot()
  return { context, driver, messages, api: context.window.space, run: source => vm.runInContext(source, context) }
}
const blocked = promise => assert.rejects(promise, error => error.code === 'blocked')
const bots = f => f.messages.filter(message => message.op === 'bot.request')

test('mount, host activation, stale and synthetic events cannot authorize a request', async () => {
  const f = fixture()
  const mount = f.api.ask('mount')
  assert.equal(bots(f).length, 0)
  await blocked(mount)
  f.run('globalThis.navigator = { userActivation: { isActive: true } }')
  await blocked(f.api.ask('unrelated host click plus timer'))
  const event = f.driver.click(() => {})
  await blocked(f.api.ask('later timer'))
  let replay
  f.driver.replay(event, () => { replay = f.api.ask('replayed event') })
  await blocked(replay)
  assert.equal(bots(f).length, 0)
})

test('one request per genuine click, with a fresh opportunity on the next click', async () => {
  const f = fixture()
  let first, duplicate
  f.driver.click(() => { first = f.api.ask('first'); duplicate = f.api.ask('duplicate') })
  assert.equal(bots(f).length, 1)
  await blocked(duplicate)
  f.driver.reply({ v: 1, id: bots(f)[0].id, ok: true, result: { accepted: true } })
  assert.deepEqual(await first, { accepted: true })
  let next
  f.driver.click(() => { next = f.api.ask('next click') })
  assert.equal(bots(f).length, 2)
  f.driver.reply({ v: 1, id: bots(f)[1].id, ok: true, result: {} })
  await next
})

test('captured native getters ignore poisoned event properties and prototype hooks', async () => {
  const f = fixture()
  let saved
  f.driver.click(event => { saved = event })
  f.context.saved = saved
  f.run(`
    Object.defineProperty(saved, 'eventPhase', { value: 2 })
    Object.defineProperty(Event.prototype, 'eventPhase', { get() { return 2 } })
    Object.defineProperty(Event.prototype, 'type', { get() { return 'click' } })
    window.event = saved
  `)
  const stale = f.api.ask('poisoned stale event')
  assert.equal(bots(f).length, 0)
  await blocked(stale)
})

test('port, Promise and Map poisoning cannot capture authority or replay an executor', async () => {
  const f = fixture()
  f.run(`
    globalThis.captured = []
    MessagePort.prototype.postMessage = function() { captured.push(this) }
    Object.defineProperty(MessageEvent.prototype, 'data', { get() { captured.push(this); return {} } })
    Map.prototype.set = function() { captured.push(this) }
    globalThis.Promise = function(executor) { captured.push(executor) }
    Reflect.apply = function() { throw Error('poisoned apply') }
    Function.prototype.call = function() { throw Error('poisoned call') }
  `)
  let result
  f.driver.click(() => { result = f.api.ask('native path') })
  assert.equal(bots(f).length, 1)
  f.driver.reply({ v: 1, id: bots(f)[0].id, ok: true, result: {} })
  await result
  assert.equal(f.context.captured.length, 0)
  await blocked(f.api.ask('executor replay unavailable'))
  assert.equal(bots(f).length, 1)
})

test('boot stops message observers and does not execute guest startup in its dispatch', () => {
  const f = fixture()
  assert.equal(f.context.observedBoot, 0)
  assert.equal(f.api.meta, null)
  f.driver.flush()
  assert.equal(f.api.meta.space.id, 'fixture')
})

test('a replayed boot cannot replace the private port or schedule another startup', () => {
  const f = fixture()
  f.driver.flush()
  const meta = f.api.meta
  f.driver.boot()
  f.driver.flush()
  assert.equal(f.api.meta, meta)
  assert.equal(f.context.observedBoot, 1)
})

test('session closure rejects pending and future requests and closes the private port', async () => {
  const f = fixture()
  let pending
  f.driver.click(() => { pending = f.api.ask('pending') })
  f.driver.reply({ v: 1, type: 'event', event: 'session.closed', payload: { reason: 'host closed' } })
  await assert.rejects(pending, error => error.code === 'session_invalid')
  let future
  f.driver.click(() => { future = f.api.ask('after close') })
  await assert.rejects(future, error => error.code === 'session_invalid')
  assert.equal(bots(f).length, 1)
  assert.equal(f.driver.closed(), true)
})

test('closure before deferred startup prevents guest boot', () => {
  const f = fixture()
  f.driver.reply({ v: 1, type: 'event', event: 'session.closed', payload: { reason: 'closed before startup' } })
  f.driver.flush()
  assert.equal(f.api.meta, null)
  assert.equal(f.driver.closed(), true)
})

test('accepted weaker contract permits a nested callback to consume the current click', async () => {
  const f = fixture()
  let nested, outer
  f.driver.click(() => {
    const syntheticCallback = () => { nested = f.api.ask('nested callback') }
    syntheticCallback()
    outer = f.api.ask('outer callback')
  })
  assert.equal(bots(f).length, 1)
  await blocked(outer)
  f.driver.reply({ v: 1, id: bots(f)[0].id, ok: true, result: {} })
  await nested
})
