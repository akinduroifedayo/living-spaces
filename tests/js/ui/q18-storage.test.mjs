import test, { before, after } from 'node:test'
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { resolve, dirname } from 'node:path'
import { homedir } from 'node:os'
import * as model from '../../../src/desktop/ui/model.mjs'
const root = resolve(import.meta.dirname, '../../..')
const require = createRequire(resolve(homedir(), '.hermes/hermes-agent/apps/desktop/node_modules/react/package.json'))
const React = require('react')
const { act } = React
const { createRoot } = require('react-dom/client')
const { JSDOM } = require('jsdom')
const cache = new Map()
function load(path) {
  if (cache.has(path)) return cache.get(path)
  const output = execFileSync('esbuild', ['--loader=jsx', '--format=cjs', '--jsx=automatic'], { input: readFileSync(path), encoding: 'utf8' })
  const module = { exports: {} }
  const imports = name => name === '@hermes/plugin-sdk' ? sdk : name === './model.mjs' ? model : name.startsWith('.') ? load(resolve(dirname(path), name)) : require(name)
  new Function('require', 'module', 'exports', output)(imports, module, module.exports)
  cache.set(path, module.exports)
  return module.exports
}
const sdk = load(resolve(root, 'tests/js/ui/sdk-stub.js'))
const history = load(resolve(root, 'src/desktop/ui/history.jsx'))
let dom
before(() => { dom = new JSDOM('<div id="root"></div>'); globalThis.window = dom.window; globalThis.document = dom.window.document; globalThis.IS_REACT_ACT_ENVIRONMENT = true })
after(() => dom.window.close())
const storage = { categories: { records: { count: 40000, bytes: 80000 }, revisions: { count: 3, bytes: 100 } }, limits: [], warnings: [{ resource: 'records', used: 40000, limit: 50000 }], native_history: { ownership: 'native-owned', counted: false, deletable: false } }
test('Q18 host storage shows counts and warnings and requires exact proposal confirmation', async () => {
  assert.equal(typeof history.StorageSection, 'function', 'Q18 storage control is missing')
  const view = createRoot(document.getElementById('root'))
  const calls = []
  const proposal = { id: 'proposal-123', scope: { categories: ['logs'], before: 1 }, confirmation: 'delete demo-space proposal-123', remove: { logs: [{ id: 9 }] }, protected: { records: [{ id: 'note', reason: 'user data' }] }, truncated: [] }
  const ctx = { rest: async (path, request) => { calls.push({ path, request }); if (path.endsWith('/propose')) return proposal; throw { error: { code: 'conflict', message: 'Proposal is stale; preview again' } } } }
  const click = async label => { const button = [...document.querySelectorAll('button')].find(b => b.textContent.trim() === label); assert.ok(button, label); await act(async () => button.click()) }
  try {
    await act(async () => view.render(React.createElement(history.StorageSection, { ctx, space: { id: 'demo-space', storage }, onChanged() {} })))
    assert.match(document.body.textContent, /40000/)
    assert.match(document.body.textContent, /50000/)
    assert.match(document.body.textContent, /native-owned/i)
    assert.equal(calls.length, 0)
    await click('Preview cleanup')
    assert.equal(calls.length, 1)
    assert.match(document.body.textContent, /proposal-123/)
    assert.match(document.body.textContent, /note.*user data/s)
    await click('Review deletion…')
    assert.equal(calls.length, 1)
    await click('Delete proposal-123')
    assert.equal(calls.length, 2)
    assert.deepEqual(calls[1], { path: '/spaces/demo-space/retention/execute', request: { method: 'POST', body: { scope: proposal.scope, proposal_id: proposal.id, confirm: proposal.confirmation } } })
    assert.match(document.body.textContent, /stale/i)
    assert.doesNotMatch(document.body.textContent, /Cleanup completed/)
  } finally { await act(async () => view.unmount()) }
})
