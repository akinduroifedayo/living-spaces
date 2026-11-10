import './env.mjs'
import test from 'node:test'
import assert from 'node:assert/strict'
import { setImmediate as tick } from 'node:timers/promises'
import { h, render, options } from 'preact'
import { useSaveState, useCollection, useRecord, RefreshButton, Nav, hashRouter } from '../../../src/living-spaces/runtime/kit/spaces-kit.mjs'

options.requestAnimationFrame = callback => queueMicrotask(callback)
options.debounceRendering = callback => queueMicrotask(callback)
const deferred = () => {
  let resolve, reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
function fixture(hook, api = {}) {
  const original = globalThis.space
  const subscriptions = { change: new Set(), run: new Set() }
  globalThis.space = {
    on(event, cb) { subscriptions[event].add(cb); return () => subscriptions[event].delete(cb) }, ...api
  }
  const container = { nodeType: 1, childNodes: [] }
  let value
  function Capture() { value = hook(); return null }
  const rerender = () => render(h(Capture, { stamp: {} }), container)
  rerender()
  return {
    get value() { return value }, rerender, subscriptions,
    emit(event, payload) { for (const cb of subscriptions[event]) cb(payload) },
    cleanup() { render(null, container); globalThis.space = original }
  }
}
test('useSaveState waits for confirmation and maps failed and conflicted writes', async () => {
  const f = fixture(useSaveState)
  try {
    assert.equal(f.value.state, 'idle')
    const backend = deferred()
    const saved = f.value.run(() => backend.promise)
    await tick()
    assert.equal(f.value.state, 'saving')
    backend.resolve({ rev: 2 })
    assert.deepEqual(await saved, { rev: 2 })
    await tick()
    assert.equal(f.value.state, 'saved')
    await f.value.run(async () => { throw new Error('Backend unavailable') })
    await tick()
    assert.equal(f.value.state, 'failed')
    assert.equal(f.value.message, 'Backend unavailable')
    const current = { id: 'demo', rev: 3 }
    await f.value.run(async () => { throw Object.assign(new Error('Record changed'), { code: 'conflict', current }) })
    await tick()
    assert.equal(f.value.state, 'conflict')
    assert.equal(f.value.current, current)
  } finally { f.cleanup() }
})
test('useSaveState keeps the newest save outcome when confirmations arrive out of order', async () => {
  const f = fixture(useSaveState)
  try {
    const old = deferred()
    const latest = deferred()
    const first = f.value.run(() => old.promise)
    const second = f.value.run(() => latest.promise)
    latest.resolve('latest')
    await second
    old.reject(new Error('Old failure'))
    await first
    await tick()
    assert.equal(f.value.state, 'saved')
  } finally { f.cleanup() }
})
test('useCollection subscribes by collection, preserves errors and unsubscribes on unmount', async () => {
  const calls = []
  const pending = []
  const f = fixture(() => useCollection('papers', { limit: 10 }), { query(collection, opts) { calls.push([collection, opts]); const job = deferred(); pending.push(job); return job.promise } })
  try {
    await tick()
    assert.equal(f.value.loading, true)
    assert.deepEqual(calls, [['papers', { limit: 10 }]])
    pending[0].resolve([{ id: 'one' }])
    await tick()
    assert.deepEqual(f.value.records, [{ id: 'one' }])
    assert.equal(f.value.loading, false)
    f.emit('change', { changes: [{ collection: 'other' }] })
    assert.equal(calls.length, 1)
    f.emit('change', { changes: [{ collection: 'papers' }] })
    pending[1].reject(new Error('Query unavailable'))
    await tick()
    assert.equal(f.value.error.message, 'Query unavailable')
    assert.deepEqual(f.value.records, [{ id: 'one' }])
    const reload = f.value.reload()
    pending[2].resolve([{ id: 'two' }])
    await reload
    await tick()
    assert.deepEqual(f.value.records, [{ id: 'two' }])
    assert.equal(f.value.error, null)
    assert.equal(f.subscriptions.change.size, 1)
  } finally { f.cleanup() }
  assert.equal(f.subscriptions.change.size, 0)
})
test('useCollection ignores stale query completions and old collection results', async () => {
  const jobs = []
  let collection = 'papers'
  const f = fixture(() => useCollection(collection), { query() { const job = deferred(); jobs.push(job); return job.promise } })
  try {
    await tick()
    f.emit('change', { changes: [{ collection: 'papers' }] })
    jobs[1].resolve([{ id: 'new' }])
    await tick()
    jobs[0].resolve([{ id: 'stale' }])
    await tick()
    assert.deepEqual(f.value.records, [{ id: 'new' }])
    collection = 'queue'
    f.rerender()
    await tick()
    jobs[2].resolve([{ id: 'queue' }])
    await tick()
    assert.deepEqual(f.value.records, [{ id: 'queue' }])
    assert.equal(f.subscriptions.change.size, 1)
  } finally { f.cleanup() }
})
test('useRecord loads one record and follows collection changes', async () => {
  let rev = 1
  const f = fixture(() => useRecord('papers', 'demo'), { async get(collection, id) { return { collection, id, rev } } })
  try {
    await tick()
    assert.equal(f.value.record.id, 'demo')
    assert.equal(f.value.record.rev, 1)
    rev = 2
    f.emit('change', { changes: [{ collection: 'papers', id: 'demo' }] })
    await tick()
    assert.equal(f.value.record.rev, 2)
  } finally { f.cleanup() }
})
test('RefreshButton follows run events and handles not_granted with actionable text', async () => {
  let denied = false
  const f = fixture(RefreshButton, { async refresh() {
    if (denied) throw Object.assign(new Error('Denied'), { code: 'not_granted' })
    return { id: 'run-1', status: 'queued' }
  } })
  const button = () => f.value.props.children[0]
  const status = () => f.value.props.children[2].props.children
  try {
    await tick()
    await button().props.onClick()
    await tick()
    assert.equal(button().props.disabled, true)
    assert.equal(status(), 'Refresh queued')
    f.emit('run', { id: 'run-1', status: 'running' })
    await tick()
    assert.equal(status(), 'Refreshing')
    f.emit('run', { id: 'run-1', status: 'failed', error: 'Demo refresh failed' })
    await tick()
    assert.equal(status(), 'Demo refresh failed')
    assert.equal(button().props.disabled, false)
    denied = true
    await button().props.onClick()
    await tick()
    assert.equal(status(), "Refresh isn't available: approve Refresh in Permissions")
  } finally { f.cleanup() }
  assert.equal(f.subscriptions.run.size, 0)
})
test('RefreshButton keeps a terminal run event newer than the refresh reply', async () => {
  const pending = deferred()
  const f = fixture(RefreshButton, { refresh: () => pending.promise })
  try {
    await tick()
    const request = f.value.props.children[0].props.onClick()
    f.emit('run', { id: 'run-1', status: 'succeeded' })
    pending.resolve({ id: 'run-1', status: 'queued' })
    await request
    await tick()
    assert.equal(f.value.props.children[2].props.children, 'Refresh complete')
  } finally { f.cleanup() }
})
test('Nav uses regular hash links and aria-current for the selected view', async () => {
  const original = globalThis.location
  globalThis.location = { hash: '#/library' }
  const router = hashRouter({ '/library': () => null })
  const f = fixture(() => Nav({ items: [{ path: '/', label: 'Overview' }, { path: '/library', label: 'Library' }] }))
  try {
    await tick()
    const links = f.value.props.children
    assert.equal(f.value.props['aria-label'], 'Views')
    assert.equal(links[1].props.href, '#/library')
    assert.equal(links[1].props['aria-current'], 'page')
    assert.equal(links[0].props['aria-current'], undefined)
  } finally { f.cleanup(); router.destroy(); globalThis.location = original }
})
