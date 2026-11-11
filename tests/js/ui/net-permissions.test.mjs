import '../sandbox/env.mjs'
import test, { before, after } from 'node:test'
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { homedir } from 'node:os'
import { resolve, dirname, join } from 'node:path'
import * as model from '../../../src/desktop/ui/model.mjs'
import * as sandbox from '../../../src/desktop/sandbox/index.js'

const root = resolve(import.meta.dirname, '../../..')
const require = createRequire(join(homedir(), '.hermes/hermes-agent/apps/desktop/node_modules/react/package.json'))
const React = require('react')
const { act } = React
const { createRoot } = require('react-dom/client')
const { JSDOM } = require('jsdom')
const cache = new Map()
let dom, data, requests
function load(path) {
  if (cache.has(path)) return cache.get(path)
  const output = execFileSync('esbuild', ['--loader=jsx', '--format=cjs', '--jsx=automatic'], { input: readFileSync(path), encoding: 'utf8' })
  const module = { exports: {} }
  const imports = name => {
    if (name === '@hermes/plugin-sdk') return sdk
    if (name === './model.mjs') return model
    if (name === '../sandbox/index.js') return sandbox
    if (name.startsWith('.')) return load(resolve(dirname(path), name))
    return require(name)
  }
  new Function('require', 'module', 'exports', output)(imports, module, module.exports)
  cache.set(path, module.exports)
  return module.exports
}
const sdk = { ...load(resolve(root, 'tests/js/ui/sdk-stub.js')), useQuery(options) {
  return { data: options.queryKey.at(-1) === 'grants' ? data : null, refetch: async () => {} }
} }
const { PermissionsSheet } = load(resolve(root, 'src/desktop/ui/permissions.jsx'))
const NOTE = "Off is not a complete block. A browser feature called WebRTC can still send data this Space can read. It still can't reach Hermes, your credentials, your files or other Spaces."
before(() => {
  dom = new JSDOM('<div id="root"></div>', { url: 'https://demo.invalid' })
  globalThis.window = dom.window
  globalThis.document = dom.window.document
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
})
after(() => dom.window.close())
async function mounted(status, run, { busyRequest = false } = {}) {
  requests = []
  data = { grants: [{ capability: 'data', status: 'granted' }, { capability: 'logs', status: 'granted' },
    { capability: 'net', status, scope: {}, requested_scope: {} }] }
  const view = createRoot(document.getElementById('root'))
  let finish
  const props = { space: { id: 'demo-space', name: 'Demo', owner: 'Demo' }, onClose() {}, onChanged() {}, ctx: {
    rest: async (path, options) => {
      requests.push({ path, ...options })
      if (busyRequest) await new Promise(resolve => { finish = resolve })
      const capability = path.split('/').at(-1)
      data = { grants: data.grants.map(g => g.capability === capability ? { ...g, status: options.body.decision === 'grant' ? 'granted' : 'revoked' } : g) }
    }
  } }
  try {
    await act(async () => view.render(React.createElement(PermissionsSheet, props)))
    await run(() => finish?.())
  } finally {
    await act(async () => { finish?.(); view.unmount() })
  }
}
const toggle = () => document.querySelector('[role="switch"][aria-labelledby="ls-net-title"]')
const click = async element => { assert.ok(element); await act(async () => element.click()) }

test('Internet access is first, On, accessible, and has no Off warning', async () => {
  await mounted('granted', async () => {
    assert.match(document.querySelector('article').textContent, /Internet access/)
    assert.equal(toggle()?.getAttribute('aria-checked'), 'true')
    assert.match(document.querySelector('article').textContent, /On/)
    assert.match(document.querySelector('article').textContent, /This Space can load content from and send data to the internet/)
    assert.equal(document.querySelector('[data-testid="webrtc-note"]'), null)
  })
})

test('switch revokes through host route and shows the Off warning', async () => {
  await mounted('granted', async () => {
    await click(toggle())
    assert.deepEqual(requests, [{ path: '/spaces/demo-space/grants/net', method: 'POST', body: { decision: 'revoke' } }])
    assert.equal(toggle().getAttribute('aria-checked'), 'false')
    assert.ok(document.querySelector('[data-testid="webrtc-note"]').textContent.includes(NOTE))
  })
})

test('Off switch grants through host approval route and removes the warning', async () => {
  await mounted('revoked', async () => {
    assert.equal(toggle()?.getAttribute('aria-checked'), 'false')
    await click(toggle())
    assert.deepEqual(requests[0].body, { decision: 'grant', requested_scope: {} })
    assert.equal(toggle().getAttribute('aria-checked'), 'true')
    assert.equal(document.querySelector('[data-testid="webrtc-note"]'), null)
  })
})

test('agent re-request stays Off until the host Approve action', async () => {
  await mounted('requested', async () => {
    assert.equal(toggle()?.getAttribute('aria-checked'), 'false')
    const row = document.querySelector('article')
    await click([...row.querySelectorAll('button')].find(b => b.textContent === 'Approve'))
    assert.deepEqual(requests[0].body, { decision: 'grant', requested_scope: {} })
  })
})

test('data revoke control remains available and no Refresh row renders', async () => {
  await mounted('granted', async () => {
    const rows = [...document.querySelectorAll('article')]
    assert.ok(rows.find(r => r.textContent.includes('Own data')).textContent.includes('Revoke'))
    assert.equal(rows.find(r => /Refresh/.test(r.textContent)), undefined)
  })
})

test('switch retains focus and blocks duplicate decisions while busy', async () => {
  await mounted('granted', async finish => {
    const button = toggle()
    button.focus()
    await click(button)
    assert.equal(button.disabled, false)
    assert.equal(button.getAttribute('aria-disabled'), 'true')
    assert.equal(document.activeElement, button)
    await click(button)
    assert.equal(requests.length, 1)
    await act(async () => finish())
    assert.equal(button.getAttribute('aria-disabled'), 'false')
    assert.equal(document.activeElement, button)
    assert.match(document.body.textContent, /Internet access turned off for Demo/)

  }, { busyRequest: true })
})

test('host operation map admits only a granted net capability', () => {
  assert.equal(sandbox.checkGrant('net.fetch', ['net']), null)
  assert.equal(sandbox.checkGrant('net.fetch', [{ capability: 'net', status: 'revoked' }]).code, 'not_granted')
  assert.equal(sandbox.checkGrant('net.fetch', ['data']).capability, 'net')
})
