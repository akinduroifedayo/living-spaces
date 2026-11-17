import './env.mjs'
import test from 'node:test'
import assert from 'node:assert/strict'
import { setImmediate as tick } from 'node:timers/promises'
import { h, render, options } from 'preact'
import * as kit from '../../../src/living-spaces/runtime/kit/spaces-kit.mjs'

options.requestAnimationFrame = callback => queueMicrotask(callback)
options.debounceRendering = callback => queueMicrotask(callback)

test('q15 freshness helper uses the durable summary without consulting recent runs', async () => {
  const previous = globalThis.space
  const summary = { last_success_at: 100, sources: [{ id: 'alpha', last_attempt_at: 200, last_success_at: 100, source_as_of: 90, failure_reason: 'Offline' }] }
  let reads = 0
  globalThis.space = { freshness: async () => { reads++; return summary }, runs: () => { throw Error('Recent history is not freshness') } }
  try {
    assert.equal(typeof kit.readFreshness, 'function')
    assert.deepEqual(await kit.readFreshness(), summary)
    assert.equal(reads, 1)
  } finally { globalThis.space = previous }
})

test('q15 freshness hook retains last-good summary on failure and unsubscribes', async () => {
  assert.equal(typeof kit.useFreshness, 'function')
  const previous = globalThis.space
  const listeners = new Set()
  const summary = { last_success_at: 100, sources: [{ id: 'alpha', last_success_at: 100 }] }
  let fail = false
  globalThis.space = {
    freshness: async () => { if (fail) throw Error('Unavailable'); return summary },
    on(event, callback) { assert.equal(event, 'run'); listeners.add(callback); return () => listeners.delete(callback) }
  }
  const container = { nodeType: 1, childNodes: [] }
  let value
  function Capture() { value = kit.useFreshness(); return null }
  try {
    render(h(Capture), container)
    await tick()
    assert.deepEqual(value.freshness, summary)
    fail = true
    for (const listener of listeners) listener({ status: 'failed' })
    await tick()
    assert.equal(value.error.message, 'Unavailable')
    assert.deepEqual(value.freshness, summary)
  } finally { render(null, container); globalThis.space = previous }
  assert.equal(listeners.size, 0)
})
