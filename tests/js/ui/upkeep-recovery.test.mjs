import test, { before, after, beforeEach, afterEach } from 'node:test'
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { homedir } from 'node:os'
import { resolve, dirname, join } from 'node:path'

const root = resolve(import.meta.dirname, '../../..')
const require = createRequire(join(homedir(), '.hermes/hermes-agent/apps/desktop/node_modules/react/package.json'))
const React = require('react')
const { act } = React
const { createRoot } = require('react-dom/client')
const { JSDOM } = require('jsdom')
const model = await import('../../../src/desktop/ui/model.mjs')
const session = await import('../../../src/desktop/ui/session.mjs')
const cache = new Map()
let dom, view, state, calls
function load(path) {
  if (cache.has(path)) return cache.get(path)
  const output = execFileSync('esbuild', ['--loader=jsx', '--format=cjs', '--jsx=automatic'], { input: readFileSync(path), encoding: 'utf8' })
  const module = { exports: {} }
  const imports = name => {
    if (name === '@hermes/plugin-sdk') return sdk
    if (name === './model.mjs') return model
    if (name === './session.mjs') return session
    if (name.startsWith('.')) return load(resolve(dirname(path), name))
    return require(name)
  }
  new Function('require', 'module', 'exports', output)(imports, module, module.exports)
  cache.set(path, module.exports)
  return module.exports
}
const baseSdk = load(resolve(root, 'tests/js/ui/sdk-stub.js'))
const sdk = { ...baseSdk, useQuery: () => ({ data: state, refetch: async () => ({ data: state }), dataUpdatedAt: 1 }) }
const { UpkeepSheet } = load(resolve(root, 'src/desktop/ui/upkeep.jsx'))
const orphan = () => ({ id: 'a5-orphan', name: 'living-spaces:a5-space', state: 'scheduled', enabled: true, uses_model: true })
const buttons = label => [...document.querySelectorAll('button')].filter(node => node.textContent.trim() === label)
async function click(label, last = false) {
  const found = buttons(label)
  assert.ok(found.length, `Missing ${label} action`)
  await act(async () => (last ? found.at(-1) : found[0]).click())
}
async function render(status = 'active') {
  const ctx = { rest: async (_path, options) => {
    if (options?.method === 'POST') {
      calls.push(options.body.action)
      if (options.body.action === 'remove') state = { ...state, link: null, job: null, orphan_jobs: [], one_shots: [], missing: false }
      if (options.body.action === 'pause') state = { ...state, orphan_jobs: state.orphan_jobs.map(job => ({ ...job, enabled: false, state: 'paused' })) }
    }
    return state
  } }
  await act(async () => view.render(React.createElement(UpkeepSheet, {
    ctx, space: { id: 'a5-space', name: 'Recovery space', owner: 'owner', status }, onClose() {}, onChanged: async () => {},
  })))
}
before(() => {
  dom = new JSDOM('<div id="root"></div>', { url: 'https://demo.invalid' })
  globalThis.window = dom.window
  globalThis.document = dom.window.document
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
})
after(() => dom.window.close())
beforeEach(() => {
  calls = []
  state = { link: null, job: null, orphan_jobs: [orphan()], one_shots: [], executions: [], missing: false, error: null }
  view = createRoot(document.getElementById('root'))
})
afterEach(async () => { await act(async () => view.unmount()) })

test('orphan-only upkeep shows its ID and never claims there is no automatic work', async () => {
  await render()
  assert.match(document.body.textContent, /a5-orphan/)
  assert.doesNotMatch(document.body.textContent, /No upkeep yet|isn't updated automatically|Nothing will run/)
})

test('a missing primary job does not hide enabled recovery work', async () => {
  state.link = { cron_job_id: 'a5-missing', kind: 'agent' }
  state.missing = true
  await render()
  assert.match(document.body.textContent, /a5-orphan/)
  assert.doesNotMatch(document.body.textContent, /Nothing will run/)
})

test('orphan-only pause succeeds after every native recovery job is confirmed paused', async () => {
  await render()
  await click('Pause')
  assert.deepEqual(calls, ['pause'])
  assert.equal(state.orphan_jobs.every(job => job.enabled === false), true)
  assert.match(document.body.textContent, /Paused\. Future runs stop/)
  assert.doesNotMatch(document.body.textContent, /Couldn't pause|not confirmed/)
})

test('archived orphan-only upkeep can be removed after confirmation', async () => {
  state.orphan_jobs[0] = { ...orphan(), enabled: false, state: 'paused' }
  await render('archived')
  assert.notEqual(buttons('Remove')[0]?.getAttribute('aria-disabled'), 'true')
  await click('Remove')
  await click('Remove', true)
  assert.deepEqual(calls, ['remove'])
  assert.deepEqual(state.orphan_jobs, [])
  assert.match(document.body.textContent, /Upkeep removed/)
  assert.doesNotMatch(document.body.textContent, /Couldn't remove|not confirmed/)
})
