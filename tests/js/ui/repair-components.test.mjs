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

for (const nativeError of [false, true]) {
test(`F1 approval binds scope and refreshes after ${nativeError ? 'native IPC' : 'structured'} conflict`, async () => {
  setup()
  const displayed = { capability: 'refresh', status: 'requested', requested_scope: { hosts: ['example.com'] } }
  data.grants = { grants: [displayed] }
  data.nextGrants = { grants: [{ ...displayed, requested_scope: { hosts: ['unreviewed.example'] } }] }
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

test('F5 the view pins native session cleanup and notifies after exhaustion', async () => {
  setup()
  const props = spaceProps([{ capability: 'data', status: 'granted' }])
  const requests = [], notifications = []
  const originalConnection = sdk.host.state.connectionId.get
  const originalProfile = sdk.host.state.profile.get
  const originalNotify = sdk.host.notifyError
  const originalWarn = console.warn
  props.ctx.queryScope = JSON.stringify(['backend-a', 'profile-a'])
  let connection = 'backend-b', profile = 'profile-b'
  sdk.host.state.connectionId.get = () => connection
  sdk.host.state.profile.get = () => profile
  sdk.host.notifyError = (...args) => notifications.push(args)
  console.warn = () => {}
  window.hermesDesktop = { api: async request => {
    requests.push(request)
    if (request.path.endsWith('/sessions')) return { session: 'demo-session', head_rev: 1, grants: ['data'] }
    if (request.path.endsWith('/bundle')) return { rev: 1 }
    throw new Error('Cleanup unavailable')
  } }
  try {
    await render(SpaceView, props)
    connection = 'backend-b'; profile = 'profile-b'
    await act(async () => view.unmount())
    await new Promise(resolve => setTimeout(resolve, 850))
    const closes = requests.filter(r => r.method === 'DELETE')
    assert.equal(closes.length, 3)
    assert.ok(requests.every(r => r.connectionId === 'backend-a' && r.profile === 'profile-a'))
    assert.equal(notifications.length, 1)
    assert.match(notifications[0][1], /could not be closed/)
  } finally {
    delete window.hermesDesktop
    sdk.host.state.connectionId.get = originalConnection
    sdk.host.state.profile.get = originalProfile
    sdk.host.notifyError = originalNotify
    console.warn = originalWarn
  }
})
