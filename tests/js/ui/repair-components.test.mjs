import test, { before, after } from 'node:test'
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { readFileSync, mkdirSync, mkdtempSync, rmSync } from 'node:fs'
import { createRequire } from 'node:module'
import { homedir } from 'node:os'
import { resolve, dirname, join } from 'node:path'

const root = resolve(import.meta.dirname, '../../..')
const require = createRequire(join(homedir(), '.hermes/hermes-agent/apps/desktop/node_modules/react/package.json'))
const React = require('react')
const { act } = React
const { createRoot } = require('react-dom/client')
const { JSDOM } = require('jsdom')
const session = await import('../../../src/desktop/ui/session.mjs')
const model = await import('../../../src/desktop/ui/model.mjs')
let temp, dom, view, queries, data, events, mounted
const cache = new Map()
function load(path) {
  if (cache.has(path)) return cache.get(path)
  const output = execFileSync('esbuild', ['--loader=jsx', '--format=cjs', '--jsx=automatic'], { input: readFileSync(path), encoding: 'utf8' })
  const module = { exports: {} }
  cache.set(path, module.exports)
  const imports = name => {
    if (name === '@hermes/plugin-sdk') return sdk
    if (name === './session.mjs') return session
    if (name === './model.mjs') return model
    if (name === '../sandbox/index.js') return { WEBRTC_NOTE: 'Public demo disclosure', mountSpace: (_, options) => { mounted = options; return { destroy() {}, postEvent: (...args) => events.push(args) } } }
    if (name.startsWith('.')) return load(resolve(dirname(path), name))
    return require(name)
  }
  new Function('require', 'module', 'exports', output)(imports, module, module.exports)
  cache.set(path, module.exports)
  return module.exports
}
const baseSdk = load(resolve(root, 'tests/js/ui/sdk-stub.js'))
const sdk = { ...baseSdk, useQuery(options) {
  const key = options.queryKey.at(-1) === 'changes' ? 'changes' : options.queryKey[3]
  queries.set(key, options)
  return { data: data[key], dataUpdatedAt: data.tick || 1, refetch: async () => {
    data.refetches.push(key)
    if (key === 'grants' && data.nextGrants) data.grants = data.nextGrants
  } }
} }
const { PermissionsSheet } = load(resolve(root, 'src/desktop/ui/permissions.jsx'))
const { SpaceView } = load(resolve(root, 'src/desktop/ui/space.jsx'))
const { SpacesPage, renderDirective } = load(resolve(root, 'src/desktop/plugin.src.js'))
const { useScopedContext } = load(resolve(root, 'src/desktop/ui/context.jsx'))
const { SpacesIndex } = load(resolve(root, 'src/desktop/ui/index.jsx'))
const { HistorySheet } = load(resolve(root, 'src/desktop/ui/history.jsx'))
const { UpkeepSheet } = load(resolve(root, 'src/desktop/ui/upkeep.jsx'))
before(() => {
  mkdirSync(resolve('.run'), { recursive: true })
  temp = mkdtempSync(resolve('.run/repair-ui-'))
  process.env.HERMES_HOME = temp
  process.env.LIVING_SPACES_DB = join(temp, 'spaces.db')
  dom = new JSDOM('<div id="root"></div>', { url: 'https://demo.invalid' })
  globalThis.window = dom.window
  globalThis.document = dom.window.document
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
})
after(() => { dom.window.close(); rmSync(temp, { recursive: true, force: true }) })
function setup() {
  queries = new Map(); events = []
  data = { refetches: [], schedule: null }
  view = createRoot(document.getElementById('root'))
}
async function render(Component, props) { await act(async () => view.render(React.createElement(Component, props))) }
async function click(label) {
  const button = [...document.querySelectorAll('button')].find(b => b.textContent.trim() === label)
  assert.ok(button, label)
  await act(async () => button.click())
}

test('plugin-owned scope keeps cache keys isolated and rejects old callbacks and results', async () => {
  setup()
  const originalConnection = sdk.host.state.connectionId.get
  const originalProfile = sdk.host.state.profile.get
  let connectionId = 'backend-a', profile = 'profile-a', current
  sdk.host.state.connectionId.get = () => connectionId
  sdk.host.state.profile.get = () => profile
  const pending = Promise.withResolvers(), calls = []
  const ctx = { rest: (path, options) => { calls.push({ path, options }); return path === '/pending' ? pending.promise : Promise.resolve({ ok: true }) } }
  function Probe() { current = useScopedContext(ctx); return null }
  try {
    await render(Probe)
    const opening = current
    assert.equal(current.scopeKey, JSON.stringify(['backend-a', 'profile-a']))
    assert.deepEqual(current.scope, { connectionId, profile })
    assert.equal(Object.hasOwn(current.ctx, 'scopeKey'), false)
    assert.deepEqual(Object.keys(ctx), ['rest'])
    await current.ctx.rest('/control')
    const result = current.ctx.rest('/pending')
    profile = 'profile-b'
    await render(Probe)
    assert.notEqual(current.scopeKey, opening.scopeKey)
    assert.deepEqual(current.scope, { connectionId, profile })
    await assert.rejects(opening.ctx.rest('/stale', { method: 'POST' }), /backend changed/)
    pending.resolve({ spaces: [{ id: 'old-space' }] })
    await assert.rejects(result, /backend changed/)
    assert.deepEqual(calls.map(call => call.path), ['/control', '/pending'])
    const otherProfile = current
    connectionId = 'backend-b'
    await render(Probe)
    assert.notEqual(current.scopeKey, otherProfile.scopeKey)
    const props = { ...current, sid: 'demo-space', space: { id: 'demo-space', name: 'Demo' }, onClose() {} }
    for (const [Component, names] of [[SpacesIndex, [undefined]], [SpaceView, ['detail', 'changes']], [HistorySheet, ['runs', 'revisions']], [PermissionsSheet, ['grants']], [UpkeepSheet, ['upkeep']]]) {
      queries.clear()
      await render(Component, props)
      for (const name of names) assert.equal(queries.get(name).queryKey[1], current.scopeKey, `${Component.name} ${name}`)
    }
  } finally {
    await act(async () => view.unmount())
    sdk.host.state.connectionId.get = originalConnection
    sdk.host.state.profile.get = originalProfile
  }
})

test('page and directive use plugin-owned cache scope and remount on profile switches', async () => {
  setup()
  const originalProfile = sdk.host.state.profile.get
  let profile = 'profile-a'
  sdk.host.state.profile.get = () => profile
  data[undefined] = { spaces: [{ id: 'demo-space', name: 'Demo', owner: 'Demo', status: 'active', head_rev: 1 }] }
  const ctx = { rest: async () => ({ spaces: [] }) }
  function Directive() { return renderDirective(ctx, { id: 'demo-space' }) }
  try {
    await render(SpacesPage, { ctx })
    const search = document.querySelector('input')
    assert.ok(search)
    profile = 'profile-b'
    await render(SpacesPage, { ctx })
    assert.notEqual(document.querySelector('input'), search)
    assert.equal(queries.get(undefined).queryKey[1], JSON.stringify(['demo-backend', profile]))
    await render(Directive)
    assert.equal(queries.get('detail').queryKey[1], JSON.stringify(['demo-backend', profile]))
  } finally {
    await act(async () => view.unmount())
    sdk.host.state.profile.get = originalProfile
  }
})

test('the view captures host scope during render, before passive session effects', async () => {
  setup()
  const props = spaceProps([]), calls = []
  const originalConnection = sdk.host.state.connectionId.get
  let connection = 'backend-a'
  sdk.host.state.connectionId.get = () => connection
  const rest = props.ctx.rest
  props.ctx.rest = (path, options) => { calls.push(path); return rest(path, options) }
  function SwitchAfterRender() {
    React.useLayoutEffect(() => { connection = 'backend-b' }, [])
    return React.createElement(SpaceView, props)
  }
  try {
    await render(SwitchAfterRender)
    assert.equal(calls.some(path => path.endsWith('/sessions')), false)
    assert.match(document.body.textContent, /backend changed/)
  } finally {
    await act(async () => view.unmount())
    sdk.host.state.connectionId.get = originalConnection
  }
})

test('page scope switches retain late-open tokens only for original-owner RPC cleanup', async () => {
  setup()
  spaceProps([])
  const originalProfile = sdk.host.state.profile.get
  const originalRoutes = sdk.host.profileRoutes
  const originalRequest = sdk.host.requestProfile
  const originalLocation = globalThis.location
  globalThis.location = dom.window.location
  dom.window.location.hash = '#/spaces?space=demo-space'
  let profile = 'profile-a'
  const route = { connectionId: 'demo-backend', profile, targetProfile: 'owner', mode: 'remote' }
  const opening = Promise.withResolvers(), requests = [], routed = []
  sdk.host.state.profile.get = () => profile
  sdk.host.profileRoutes = async () => [route]
  sdk.host.requestProfile = async (...args) => { routed.push(args); return { closed: true } }
  const ctx = { rest: async (path, options = {}) => {
    requests.push({ path, ...options, profile })
    if (path.endsWith('/sessions')) return profile === 'profile-a' ? opening.promise : { session: 'session-b', head_rev: 1, grants: [] }
    if (path.endsWith('/bundle')) return { rev: 1 }
    return { closed: true }
  } }
  try {
    await render(SpacesPage, { ctx })
    profile = 'profile-b'
    await render(SpacesPage, { ctx })
    await act(async () => opening.resolve({ session: 'late-session-a', head_rev: 1, grants: [] }))
    assert.deepEqual(routed, [[route, 'plugin.living-spaces.close_session', { space_id: 'demo-space', session: 'late-session-a' }, 5000]])
    assert.equal(requests.some(request => request.method === 'DELETE'), false)
    await act(async () => view.unmount())
    assert.deepEqual(requests.filter(request => request.method === 'DELETE'), [{ path: '/spaces/demo-space/sessions/session-b', method: 'DELETE', timeoutMs: 5000, profile: 'profile-b' }])
  } finally {
    await act(async () => view.unmount())
    sdk.host.state.profile.get = originalProfile
    sdk.host.profileRoutes = originalRoutes
    sdk.host.requestProfile = originalRequest
    dom.window.location.hash = ''
    if (originalLocation === undefined) delete globalThis.location
    else globalThis.location = originalLocation
  }
})

for (const nativeError of [false, true]) {
test(`F1 approval binds scope and refreshes after ${nativeError ? 'native IPC' : 'structured'} conflict`, async () => {
  setup()
  const displayed = { capability: 'logs', status: 'requested', purpose: 'Reviewed example.com purpose', requested_scope: { hosts: ['example.com'] } }
  data.grants = { grants: [displayed] }
  data.nextGrants = { grants: [{ ...displayed, purpose: 'Changed unreviewed.example purpose', requested_scope: { hosts: ['unreviewed.example'] } }] }
  const calls = []
  const props = { space: { id: 'demo-space', name: 'Demo' }, onClose() {}, onChanged() {}, ctx: { rest: async (path, options) => {
    calls.push(options.body)
    const error = { error: { code: 'conflict', message: 'Request changed', current: data.nextGrants.grants[0] } }
    if (nativeError) throw new Error(`Error invoking remote method 'hermes:api': Error: 409: ${JSON.stringify(error)}`)
    throw error
  } } }
  try {
    await render(PermissionsSheet, props)
    assert.match(document.body.textContent, /example.com/)
    await click('Approve')
    assert.deepEqual(calls, [{ decision: 'grant', requested_scope: displayed.requested_scope }])
    assert.ok(data.refetches.includes('grants'))
    await render(PermissionsSheet, props)
    assert.match(document.body.textContent, /unreviewed.example/)
    assert.match(document.body.textContent, /Review.*request/i)
  } finally { await act(async () => view.unmount()) }
})
}

function spaceProps(grants) {
  data.detail = { id: 'demo-space', name: 'Demo', owner: 'Demo', status: 'active', head_rev: 1, grants, freshness: {} }
  return { sid: 'demo-space', ctx: { rest: async path => {
    if (path.endsWith('/sessions')) return { session: 'demo-session', head_rev: 1, grants: data.detail.grants.filter(g => g.status === 'granted').map(g => g.capability) }
    if (path.endsWith('/bundle')) return { rev: 1 }
    return { closed: true }
  } } }
}
const metadata = { seq: 1, changes: [{ seq: 1, collection: 'private_notes', id: 'public-demo', actor: 'agent:demo', rev: 1, op: 'put', at: 1 }] }
for (const grants of [[], [{ capability: 'data', status: 'revoked' }], [{ capability: 'data', status: 'requested' }]]) {
  test(`F6 ${grants[0]?.status || 'missing'} data grant stops polling and cached event delivery`, async () => {
    setup()
    data.changes = metadata
    const props = spaceProps(grants)
    try {
      await render(SpaceView, props)
      assert.equal(queries.get('changes').enabled, false)
      assert.deepEqual(events.filter(([name]) => name === 'data.changed'), [])
    } finally { await act(async () => view.unmount()) }
  })
}

test('F6 revocation suppresses a late changes response while approved Spaces receive changes', async () => {
  setup()
  data.changes = metadata
  const props = spaceProps([{ capability: 'data', status: 'granted' }])
  try {
    await render(SpaceView, props)
    assert.equal(queries.get('changes').enabled, true)
    assert.equal(events.filter(([name]) => name === 'data.changed').length, 1)
    events.length = 0
    data.detail = { ...data.detail, grants: [{ capability: 'data', status: 'revoked' }] }
    data.changes = { seq: 2, changes: [{ ...metadata.changes[0], seq: 2, id: 'later-record' }] }
    data.tick = 2
    await render(SpaceView, props)
    assert.equal(queries.get('changes').enabled, false)
    assert.deepEqual(events.filter(([name]) => name === 'data.changed'), [])
  } finally { await act(async () => view.unmount()) }
})


test('F2 the host shows uncertainty and Retry save after a lost response', async () => {
  setup()
  const props = spaceProps([{ capability: 'data', status: 'granted' }])
  const original = props.ctx.rest
  props.ctx.rest = (path, options) => path.endsWith('/bridge') ? Promise.reject(new Error('Lost response')) : original(path, options)
  try {
    await render(SpaceView, props)
    await act(async () => mounted.call('data.put', { collection: 'notes', data: { text: 'Public demo' } }))
    assert.match(document.body.textContent, /Save outcome unknown/)
    assert.match(document.body.textContent, /may have been stored/)
    assert.doesNotMatch(document.body.textContent, /this change was not stored/)
    await click('Retry save')
    assert.match(document.body.textContent, /Save outcome unknown/)
  } finally { await act(async () => view.unmount()) }
})

test('F5 the view pins public session cleanup and notifies after exhaustion', async () => {
  setup()
  const props = spaceProps([{ capability: 'data', status: 'granted' }])
  const requests = [], notifications = []
  const originalConnection = sdk.host.state.connectionId.get
  const originalProfile = sdk.host.state.profile.get
  const originalNotify = sdk.host.notifyError
  const originalRoutes = sdk.host.profileRoutes
  const originalRequest = sdk.host.requestProfile
  const originalWarn = console.warn
  props.scope = { connectionId: 'backend-a', profile: 'profile-a' }
  props.scopeKey = JSON.stringify(['backend-a', 'profile-a'])
  const route = { ...props.scope, targetProfile: 'owner', mode: 'remote' }
  let connection = 'backend-a', profile = 'profile-a'
  sdk.host.state.connectionId.get = () => connection
  sdk.host.state.profile.get = () => profile
  sdk.host.profileRoutes = async () => [route]
  sdk.host.requestProfile = async (...args) => { requests.push(args); throw new Error('Cleanup unavailable') }
  sdk.host.notifyError = (...args) => notifications.push(args)
  console.warn = () => {}
  try {
    await render(SpaceView, props)
    connection = 'backend-b'; profile = 'profile-b'
    await act(async () => view.unmount())
    await new Promise(resolve => setTimeout(resolve, 850))
    assert.equal(requests.length, 3)
    assert.ok(requests.every(([target, method, params, timeout]) => target === route && method === 'plugin.living-spaces.close_session' && params.space_id === props.sid && params.session === 'demo-session' && timeout === 5000))
    assert.equal(notifications.length, 1)
    assert.match(notifications[0][1], /could not be closed/)
  } finally {
    sdk.host.state.connectionId.get = originalConnection
    sdk.host.state.profile.get = originalProfile
    sdk.host.profileRoutes = originalRoutes
    sdk.host.requestProfile = originalRequest
    sdk.host.notifyError = originalNotify
    console.warn = originalWarn
  }
})
