import '../sandbox/env.mjs'
import test from 'node:test'
import assert from 'node:assert/strict'
import { createSpaceSession } from '../../../src/desktop/ui/session.mjs'

function fixture({ activation = true, openResult = true } = {}) {
  const notes = [], opened = [], copied = [], restCalls = []
  const state = { connectionId: 'demo-backend', profile: 'demo-profile', activation }
  const host = {
    state: { connectionId: { get: () => state.connectionId }, profile: { get: () => state.profile } },
    notify: note => { notes.push(note); return note.id }
  }
  const os = {
    openExternal: url => { opened.push(url); return state.pendingOpen ?? Promise.resolve(state.openResult ?? openResult) },
    writeClipboard: async text => { copied.push(text); return true }
  }
  let bridge
  const rest = async (path, request = {}) => {
    restCalls.push(path)
    if (path.endsWith('/sessions')) return { session: 'demo-session', head_rev: 1, grants: [] }
    if (path.endsWith('/bundle')) return { rev: 1 }
    if (request.method === 'DELETE') return { closed: true }
    throw new Error(`Unexpected path ${path}`)
  }
  const session = createSpaceSession({ rest, host, os, backend: { connectionId: 'demo-backend', profile: 'demo-profile' }, sid: 'demo-space',
    container: {}, mount: (_, value) => { bridge = value; return { destroy() {}, postEvent() {} } }, onEvent() {},
    userActivation: () => state.activation })
  return { session, notes, opened, copied, restCalls, state, call: (...args) => bridge.call(...args) }
}
const settle = () => new Promise(resolve => setImmediate(resolve))

test('an activated source link shows its exact destination and opens only from the host confirmation', async () => {
  const f = fixture()
  await f.session.ready
  const reply = await f.call('link.open', { url: 'https://example.com/papers/42' })
  assert.deepEqual(reply, { ok: true, result: { status: 'confirming', url: 'https://example.com/papers/42', host: 'example.com' } })
  assert.equal(f.opened.length, 0, 'the guest request alone never opens a destination')
  assert.equal(f.notes.length, 1)
  const note = f.notes[0]
  assert.ok(`${note.title} ${note.message} ${note.detail ?? ''}`.includes('https://example.com/papers/42'))
  assert.equal(note.action.label, 'Open link')
  note.action.onClick()
  await settle()
  assert.deepEqual(f.opened, ['https://example.com/papers/42'])
  note.action.onClick()
  await settle()
  assert.deepEqual(f.opened, ['https://example.com/papers/42'], 'one confirmation opens at most once')
  assert.equal(f.restCalls.some(path => path.endsWith('/bridge')), false, 'links never reach the backend bridge')
})

test('a request without a current user activation is refused without a prompt or an open', async () => {
  const f = fixture({ activation: false })
  await f.session.ready
  const reply = await f.call('link.open', { url: 'https://example.com/' })
  assert.equal(reply.ok, false)
  assert.equal(reply.error.code, 'blocked')
  assert.match(reply.error.message, /click/i)
  assert.equal(f.notes.length, 0)
  assert.equal(f.opened.length, 0)
})

for (const url of ['javascript:alert(1)', 'file:///etc/hosts', 'data:text/plain,demo', 'https://user:pass@example.com/', 'https://example.com/?access_token=fixture', 'http://example.com/', 'not a url']) {
  test(`unsafe destination ${url} is refused before any prompt or native open`, async () => {
    const f = fixture()
    await f.session.ready
    const reply = await f.call('link.open', { url })
    assert.equal(reply.ok, false)
    assert.equal(reply.error.code, 'invalid')
    assert.equal(f.notes.length, 1, 'the refusal is visible')
    assert.equal(f.notes[0].action, undefined, 'a refused destination offers no open action')
    assert.equal(f.opened.length, 0)
  })
}

test('malformed link arguments are refused', async () => {
  const f = fixture()
  await f.session.ready
  for (const args of [{}, { url: 42 }, { url: 'https://example.com/', extra: true }]) {
    const reply = await f.call('link.open', args)
    assert.equal(reply.error.code, 'invalid')
  }
  assert.equal(f.notes.length, 0)
})

test('a confirmation from a closed session cannot open its destination', async () => {
  const f = fixture()
  await f.session.ready
  await f.call('link.open', { url: 'https://example.com/' })
  await f.session.destroy()
  f.notes[0].action.onClick()
  await settle()
  assert.equal(f.opened.length, 0)
  const late = await f.call('link.open', { url: 'https://example.com/' })
  assert.equal(late.error.code, 'session_invalid')
  assert.equal(f.notes.length, 1, 'a late request from the old session shows nothing')
})

test('a confirmation cannot open after the active profile changes', async () => {
  const f = fixture()
  await f.session.ready
  await f.call('link.open', { url: 'https://example.com/' })
  f.state.profile = 'other-profile'
  f.notes[0].action.onClick()
  await settle()
  assert.equal(f.opened.length, 0)
})

test('a newer link request replaces the earlier confirmation', async () => {
  const f = fixture()
  await f.session.ready
  await f.call('link.open', { url: 'https://example.com/first' })
  await f.call('link.open', { url: 'https://example.com/second' })
  assert.equal(f.notes[0].id, f.notes[1].id, 'one confirmation slot per Space')
  f.notes[0].action.onClick()
  await settle()
  assert.equal(f.opened.length, 0)
  f.notes[1].action.onClick()
  await settle()
  assert.deepEqual(f.opened, ['https://example.com/second'])
})

test('an operating-system open failure is reported with the destination and a copy recovery', async () => {
  const f = fixture({ openResult: false })
  await f.session.ready
  await f.call('link.open', { url: 'https://example.com/' })
  f.notes[0].action.onClick()
  await settle()
  assert.deepEqual(f.opened, ['https://example.com/'])
  const failure = f.notes.at(-1)
  assert.equal(failure.kind, 'error')
  assert.ok(`${failure.title} ${failure.message} ${failure.detail ?? ''}`.includes('https://example.com/'))
  assert.equal(failure.action.label, 'Copy link')
  failure.action.onClick()
  await settle()
  assert.deepEqual(f.copied, ['https://example.com/'])
})

test('a Desktop without the native opener refuses with a typed error', async () => {
  const f = fixture()
  await f.session.ready
  const session = createSpaceSession({ rest: async path => path.endsWith('/sessions') ? { session: 's', head_rev: 1, grants: [] } : { rev: 1 },
    host: { state: { connectionId: { get: () => null }, profile: { get: () => null } }, notify() {} }, os: null, sid: 'demo-space', container: {},
    mount: (_, value) => { session.bridge = value; return { destroy() {} } }, onEvent() {}, userActivation: () => true })
  await session.ready
  const reply = await session.bridge.call('link.open', { url: 'https://example.com/' })
  assert.equal(reply.error.code, 'blocked')
})

test('an open failure that settles after the session closes or a newer link is shown publishes nothing', async () => {
  for (const settleAfter of ['destroy', 'profile', 'newer']) {
    const f = fixture()
    await f.session.ready
    let fail
    f.state.pendingOpen = new Promise(resolve => { fail = () => resolve(false) })
    await f.call('link.open', { url: 'https://example.com/old' })
    f.notes[0].action.onClick()
    await settle()
    delete f.state.pendingOpen
    if (settleAfter === 'destroy') await f.session.destroy()
    if (settleAfter === 'profile') f.state.profile = 'other-profile'
    if (settleAfter === 'newer') await f.call('link.open', { url: 'https://example.com/new' })
    const before = f.notes.length
    fail()
    await settle()
    assert.equal(f.notes.length, before, `${settleAfter}: a stale failure does not replace current state`)
  }
})

test('only the notice currently shown for a Space can act; older Open link or Copy link callbacks do nothing', async () => {
  for (const stale of ['destroy', 'profile', 'backend', 'newer']) {
    const f = fixture({ openResult: false })
    await f.session.ready
    await f.call('link.open', { url: 'https://example.com/old' })
    f.notes.at(-1).action.onClick()
    await settle()
    const failure = f.notes.at(-1)
    assert.equal(failure.action.label, 'Copy link')
    if (stale === 'destroy') await f.session.destroy()
    if (stale === 'profile') f.state.profile = 'other-profile'
    if (stale === 'backend') f.state.connectionId = 'other-backend'
    if (stale === 'newer') await f.call('link.open', { url: 'https://example.com/new' })
    failure.action.onClick()
    await settle()
    assert.deepEqual(f.copied, [], `${stale}: a replaced or orphaned Copy link writes nothing`)
  }
  const f = fixture({ openResult: false })
  await f.session.ready
  await f.call('link.open', { url: 'https://example.com/old' })
  f.notes.at(-1).action.onClick()
  await settle()
  f.notes.at(-1).action.onClick()
  await settle()
  assert.deepEqual(f.copied, ['https://example.com/old'], 'the current failure notice still copies')
})
