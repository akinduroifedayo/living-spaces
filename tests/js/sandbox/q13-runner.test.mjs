import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'
import { setTimeout as delay } from 'node:timers/promises'

test('Q13 inspection host assigns write request ids and can reconcile them', async () => {
  const frames = []
  const document = { body: { style: {}, append() {} }, createElement(tag) {
    if (tag === 'div') return { style: {}, append() {} }
    const frame = new EventTarget()
    frame.style = {}
    frame.setAttribute = () => {}
    frame.remove = () => {}
    frame.contentWindow = { postMessage(message, origin, ports) { frame.peer = ports[0] } }
    frames.push(frame)
    return frame
  } }
  const context = vm.createContext({ document, window: new EventTarget(), MessageChannel, TextEncoder, performance,
    innerWidth: 390, innerHeight: 300, devicePixelRatio: 1, setTimeout, clearTimeout })
  vm.runInContext(readFileSync('src/living-spaces/inspection/runner.js', 'utf8'), context)
  const inspector = context.__lsInspect
  inspector.mount({ space: { id: 'fixture', name: 'Fixture' }, rev: 1, manifest: {}, files: [],
    sandbox: { format: 1, shell_srcdoc: '<html></html>' } }, ['data'])
  frames[0].dispatchEvent(new Event('load'))
  const replies = []
  frames[0].peer.onmessage = e => replies.push(e.data)
  try {
    frames[0].peer.postMessage({ v: 1, id: 1, op: 'data.put', args: { collection: 'notes', id: 'a', data: {} } })
    let queued
    for (let i = 0; i < 50; i++) {
      queued = await inspector.next(10)
      if (queued.requests.length) break
    }
    assert.equal(queued.requests.length, 1)
    assert.match(queued.requests[0].request_id, /^inspect_write_[0-9]+$/)
    inspector.reply(queued.requests[0].id, { ok: true, result: { id: 'a', rev: 1 }, outcome: { status: 'success' } })
    await delay(10)
    assert.equal(replies[0].result.rev, 1)
    assert.equal(replies[0].outcome.status, 'success')
    // Editor saves keep the app's request id through the inspection transport (integration Q10 x Q13).
    frames[0].peer.postMessage({ v: 1, id: 2, op: 'editor.save', request_id: 'editor_probe',
      args: { editor: 'n', schema: 1, collection: 'notes', id: 'a', data: {}, base_rev: 1 } })
    for (let i = 0; i < 50; i++) {
      queued = await inspector.next(10)
      if (queued.requests.length) break
    }
    assert.equal(queued.requests[0].op, 'editor.save')
    assert.equal(queued.requests[0].request_id, 'editor_probe')
  } finally {
    inspector.destroy()
    frames[0].peer.close()
  }
})
