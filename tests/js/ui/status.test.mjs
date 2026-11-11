import test, { before, after } from 'node:test'
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { homedir } from 'node:os'
import { resolve, dirname, join } from 'node:path'
import * as session from '../../../src/desktop/ui/session.mjs'
import * as model from '../../../src/desktop/ui/model.mjs'

const root = resolve(import.meta.dirname, '../../..')
const require = createRequire(join(homedir(), '.hermes/hermes-agent/apps/desktop/node_modules/react/package.json'))
const React = require('react')
const { act } = React
const { createRoot } = require('react-dom/client')
const { JSDOM } = require('jsdom')
let dom, view, data, mounted
const cache = new Map()
function load(path) {
  if (cache.has(path)) return cache.get(path)
  const output = execFileSync('esbuild', ['--loader=jsx', '--format=cjs', '--jsx=automatic'], { input: readFileSync(path), encoding: 'utf8' })
  const module = { exports: {} }
  const imports = name => {
    if (name === '@hermes/plugin-sdk') return sdk
    if (name === './session.mjs') return session
    if (name === './model.mjs') return model
    if (name === '../sandbox/index.js') return { WEBRTC_NOTE: 'Public demo disclosure', mountSpace: (_, options) => { mounted = options; return { destroy() {} } } }
    if (name.startsWith('.')) return load(resolve(dirname(path), name))
    return require(name)
  }
  new Function('require', 'module', 'exports', output)(imports, module, module.exports)
  cache.set(path, module.exports)
  return module.exports
}
const baseSdk = load(resolve(root, 'tests/js/ui/sdk-stub.js'))
const sdk = { ...baseSdk, useQuery(options) {
  const key = options.queryKey[3]
  return { data: data[key], dataUpdatedAt: data.tick || 1, refetch: async () => { data.refetches = (data.refetches || 0) + 1 } }
} }
const { SpaceView } = load(resolve(root, 'src/desktop/ui/space.jsx'))
const { RunRow, HistorySheet } = load(resolve(root, 'src/desktop/ui/history.jsx'))
const { UpkeepSheet } = load(resolve(root, 'src/desktop/ui/upkeep.jsx'))
const { PermissionsSheet, GrantCard } = load(resolve(root, 'src/desktop/ui/permissions.jsx'))
const { absolute } = load(resolve(root, 'src/desktop/ui/components.jsx'))
before(() => {
  dom = new JSDOM('<div id="root"></div>', { url: 'https://demo.invalid' })
  globalThis.window = dom.window
  globalThis.document = dom.window.document
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
})
after(() => dom.window.close())
function setup() { data = {}; view = createRoot(document.getElementById('root')) }
async function render(Component, props) { await act(async () => view.render(React.createElement(Component, props))) }
async function click(label) {
  const button = [...document.querySelectorAll('button')].find(b => b.textContent.trim() === label)
  assert.ok(button, label)
  await act(async () => button.click())
}
const demo = () => ({ id: 'demo-space', name: 'Demo', owner: 'Hermes', status: 'active', head_rev: 2, grants: [{ capability: 'data', status: 'granted' }], freshness: { last_success_at: 1700000000, source_as_of: 1699999900 } })
function spaceProps(bridge = () => ({ ok: true, result: {} })) {
  data.detail = demo()
  return { sid: 'demo-space', ctx: { rest: async (path, options) => {
    if (path.endsWith('/sessions')) return { session: 'demo-session', head_rev: 2, grants: ['data'] }
    if (path.endsWith('/bundle')) return { rev: 2 }
    if (path.endsWith('/bridge')) return bridge(options.body)
    return { closed: true }
  } } }
}
const rejected = op => ({ kind: 'write-rejected', op, error: { code: 'limit', message: 'Bridge message exceeds size limit', limit: 1048576, actual: 1048590 } })
for (const op of ['data.put', 'data.delete', 'data.batch']) {
  test(`local ${op} rejection replaces Saved and exposes typed numbers without Retry save`, async () => {
    setup()
    let calls = 0
    try {
      await render(SpaceView, spaceProps(() => { calls++; return { ok: true, result: {} } }))
      await act(async () => mounted.call('data.put', { collection: 'notes', data: {} }))
      assert.match(document.querySelector('.ls-save').textContent, /Saved /)
      await act(async () => mounted.onEvent(rejected(op)))
      assert.match(document.querySelector('.ls-save').textContent, /Not saved/)
      assert.doesNotMatch(document.querySelector('.ls-save').textContent, /Saved /)
      assert.match(document.body.textContent, /limit/)
      assert.match(document.body.textContent, /1048576/)
      assert.match(document.body.textContent, /1048590/)
      assert.doesNotMatch(document.body.textContent, /Retry save/)
      assert.equal(calls, 1)
    } finally { await act(async () => view.unmount()) }
  })
}
test('local rejection keeps earlier unknown outcome and ignores events after session destruction', async () => {
  let bridge
  const writes = []
  const controller = session.createSpaceSession({ sid: 'demo-space', container: {}, onEvent() {}, onWrite: value => writes.push(value), mount: (_, options) => { bridge = options; return { destroy() {} } }, rest: async path => {
    if (path.endsWith('/sessions')) return { session: 'demo', head_rev: 1, grants: [] }
    if (path.endsWith('/bundle')) return { rev: 1 }
    if (path.endsWith('/bridge')) throw new Error('Lost response')
    return {}
  } })
  await controller.ready
  await bridge.call('data.put', { data: {} })
  const unknown = writes.at(-1)
  bridge.onEvent(rejected('data.batch'))
  assert.equal(writes.at(-1).status, 'unknown')
  controller.dismissWrite(unknown.token)
  assert.equal(writes.at(-1).status, 'failed')
  assert.equal(writes.at(-1).retry, undefined)
  await controller.destroy()
  const count = writes.length
  bridge.onEvent(rejected('data.put'))
  assert.equal(writes.length, count)
})
const dispatch = { scheduled_at: '2026-11-10T10:00:00+00:00', dispatched_at: '2026-11-10T12:00:00+00:00', lateness_seconds: 7200, kind: 'catch_up' }
for (const status of ['succeeded', 'failed']) {
  test(`${status} catch-up history shows both times without changing the outcome or freshness`, async () => {
    setup()
    const space = demo()
    const before = structuredClone(space.freshness)
    const run = { status, trigger: 'schedule', queued_at: 1794312000, error: status === 'failed' ? 'Source unavailable' : null, changed: {}, detail: { dispatch } }
    try {
      await render(RunRow, { run })
      assert.match(document.body.textContent, /Catch-up refresh/)
      assert.match(document.body.textContent, new RegExp(status))
      assert.match(document.body.textContent, /Missed scheduled time/)
      assert.ok(document.body.textContent.includes(absolute(Date.parse(dispatch.scheduled_at) / 1000)))
      assert.ok(document.body.textContent.includes(absolute(Date.parse(dispatch.dispatched_at) / 1000)))
      assert.match(document.body.textContent, /Missed intervals were not replayed\./)
      if (status === 'failed') assert.match(document.body.textContent, /Source unavailable/)
      assert.deepEqual(space.freshness, before)
    } finally { await act(async () => view.unmount()) }
  })
}
for (const kind of ['late', 'on_time']) {
  test(`${kind} dispatch does not become catch-up from ticker slip`, async () => {
    setup()
    try {
      await render(RunRow, { run: { status: 'succeeded', trigger: 'schedule', changed: {}, detail: { dispatch: { ...dispatch, kind, lateness_seconds: 0.25 } } } })
      assert.doesNotMatch(document.body.textContent, /Catch-up|Missed intervals/)
      if (kind === 'late') assert.match(document.body.textContent, /Delayed by 0\.25 s/)
    } finally { await act(async () => view.unmount()) }
  })
}
const job = (patch = {}) => ({ id: 'job1', name: 'living-spaces:demo-space', prompt: 'Update Demo from public sources.', schedule_display: 'every 1h', cadence: '0 * * * *', timezone: 'America/Chicago', enabled: true, state: 'scheduled', next_run_at: '2026-11-11T16:00:00+00:00', last_run_at: '2026-11-11T15:00:00+00:00', last_status: 'ok', last_error: null, uses_model: true, ...patch })
const upkeepPayload = (patch = {}) => ({ link: { cron_job_id: 'job1', kind: 'agent', created_at: 1, created_by: 'agent' }, job: job(), executions: [{ id: 'e1', status: 'succeeded', claimed_at: 1794312000, started_at: 1794312001, finished_at: 1794312010, error: null, scheduled_instant: 1794312000 }, { id: 'e2', status: 'unknown', claimed_at: 1794300000, started_at: 1794300001, finished_at: null, error: null, scheduled_instant: 1794300000 }], missing: false, error: null, ...patch })
const upkeepProps = (calls, reply) => ({ space: demo(), onClose() {}, onChanged() {}, ctx: { rest: async (path, options = {}) => { calls.push({ path, body: options.body }); return reply ? reply(path, options) : {} } } })
test('Upkeep sheet renders the native prompt, cadence, next run and executions', async () => {
  setup()
  data.upkeep = upkeepPayload()
  try {
    await render(UpkeepSheet, upkeepProps([]))
    const text = document.body.textContent
    assert.match(text, /Update Demo from public sources\./)
    assert.match(text, /every 1h/)
    assert.match(text, /0 \* \* \* \*/)
    assert.match(text, /America\/Chicago/)
    assert.ok(text.includes(absolute(Date.parse('2026-11-11T16:00:00+00:00') / 1000)), 'next run')
    assert.match(text, /Succeeded/)
    assert.match(text, /Uses model calls/)
    assert.doesNotMatch(text, /No model calls/)
    assert.equal(document.querySelectorAll('[aria-label="Upkeep executions"] li').length, 2)
  } finally { await act(async () => view.unmount()) }
})
test('unknown execution reads outcome unknown with side-effects copy', async () => {
  setup()
  data.upkeep = upkeepPayload()
  try {
    await render(UpkeepSheet, upkeepProps([]))
    assert.match(document.querySelector('li[data-status="unknown"]').textContent, /Outcome unknown, side effects may have run/)
  } finally { await act(async () => view.unmount()) }
})
test('feed kind shows No model calls and no prompt', async () => {
  setup()
  data.upkeep = upkeepPayload({ link: { cron_job_id: 'job1', kind: 'feed', created_at: 1, created_by: 'agent' }, job: job({ prompt: null, uses_model: false }) })
  try {
    await render(UpkeepSheet, upkeepProps([]))
    assert.match(document.body.textContent, /No model calls/)
    assert.doesNotMatch(document.body.textContent, /Uses model calls/)
  } finally { await act(async () => view.unmount()) }
})
test('native job mode wins over a stale feed link for the model-call disclosure', async () => {
  setup()
  data.upkeep = upkeepPayload({ link: { cron_job_id: 'job1', kind: 'feed', created_at: 1, created_by: 'agent' }, job: job({ prompt: 'Edited in cron', uses_model: true }) })
  try {
    await render(UpkeepSheet, upkeepProps([]))
    assert.match(document.body.textContent, /Uses model calls/)
    assert.match(document.body.textContent, /Edited in cron/)
  } finally { await act(async () => view.unmount()) }
})
test('Refresh now one-shot runs are listed with their native outcome', async () => {
  setup()
  data.upkeep = upkeepPayload({ link: null, job: null, executions: [], one_shots: [{ id: 'once1', uses_model: true, executions: [{ id: 'x1', status: 'unknown', claimed_at: 1794300000, started_at: null, finished_at: null, error: null, scheduled_instant: null }] }] })
  try {
    await render(UpkeepSheet, upkeepProps([]))
    const section = document.querySelector('[data-testid="one-shots"]')
    assert.match(section.textContent, /Refresh now runs/)
    assert.match(section.textContent, /model calls/)
    assert.match(section.querySelector('li[data-status="unknown"]').textContent, /Outcome unknown/)
  } finally { await act(async () => view.unmount()) }
})
test('Upkeep buttons post the right action and re-read', async () => {
  for (const [enabled, label, action] of [[true, 'Pause', 'pause'], [false, 'Resume', 'resume'], [true, 'Run now', 'run']]) {
    setup()
    data.upkeep = upkeepPayload({ job: job({ enabled }) })
    const calls = []
    try {
      await render(UpkeepSheet, upkeepProps(calls))
      await click(label)
      assert.deepEqual(calls, [{ path: '/spaces/demo-space/upkeep', body: { action } }], label)
      assert.equal(data.refetches, 1, `${label} re-reads`)
    } finally { await act(async () => view.unmount()) }
  }
})
test('Remove asks for confirmation, posts remove and re-reads', async () => {
  setup()
  data.upkeep = upkeepPayload()
  const calls = []
  try {
    await render(UpkeepSheet, upkeepProps(calls))
    await click('Remove')
    assert.deepEqual(calls, [])
    assert.match(document.querySelector('[role="alertdialog"]').textContent, /Remove upkeep for Demo\?/)
    const confirm = [...document.querySelectorAll('[role="alertdialog"] button')].find(b => b.textContent.trim() === 'Remove')
    await act(async () => confirm.click())
    assert.deepEqual(calls, [{ path: '/spaces/demo-space/upkeep', body: { action: 'remove' } }])
    assert.equal(data.refetches, 1)
  } finally { await act(async () => view.unmount()) }
})
test('missing job shows the missing copy and Remove link', async () => {
  setup()
  data.upkeep = upkeepPayload({ job: null, missing: true, executions: [] })
  const calls = []
  try {
    await render(UpkeepSheet, upkeepProps(calls))
    assert.match(document.body.textContent, /The linked Hermes job no longer exists/)
    assert.doesNotMatch(document.body.textContent, /Run now|Pause/)
    await click('Remove link')
    assert.match(document.querySelector('[role="alertdialog"]').textContent, /Remove upkeep/)
  } finally { await act(async () => view.unmount()) }
})
test('native cron error shows a banner', async () => {
  setup()
  data.upkeep = upkeepPayload({ job: null, error: 'cron module unavailable' })
  try {
    await render(UpkeepSheet, upkeepProps([]))
    assert.match(document.querySelector('[role="alert"]').textContent, /cron module unavailable/)
  } finally { await act(async () => view.unmount()) }
})
test('no link shows No upkeep scheduled and a CopyPrompt', async () => {
  setup()
  data.upkeep = { link: null, job: null, executions: [], missing: false, error: null }
  try {
    await render(UpkeepSheet, upkeepProps([]))
    assert.match(document.body.textContent, /No upkeep scheduled/)
    const copy = document.querySelector('[data-copy]')
    assert.match(copy.getAttribute('data-copy'), /Hermes, schedule upkeep for Demo/)
    assert.doesNotMatch(document.body.textContent, /Run now|Remove/)
  } finally { await act(async () => view.unmount()) }
})
test('failed action surfaces an error and re-reads', async () => {
  setup()
  data.upkeep = upkeepPayload()
  try {
    await render(UpkeepSheet, upkeepProps([], () => { throw new Error('boom') }))
    await click('Pause')
    assert.match(document.body.textContent, /boom/)
    assert.equal(data.refetches, 1)
  } finally { await act(async () => view.unmount()) }
})
test('Permissions has no Refresh row or schedule approval, even if a stale refresh grant is returned', async () => {
  setup()
  data.grants = { grants: [{ capability: 'data', status: 'granted' }, { capability: 'refresh', status: 'requested', requested_scope: { hosts: ['example.com'] } }] }
  try {
    await render(PermissionsSheet, { space: demo(), ctx: {}, onClose() {}, onChanged() {} })
    const text = document.body.textContent
    assert.doesNotMatch(text, /Refresh|Scheduled upkeep|schedule/i)
    assert.match(text, /Own data/)
  } finally { await act(async () => view.unmount()) }
})
test('refreshReason has no grant clause', () => {
  assert.equal(model.refreshReason({ status: 'active', manifest: { upkeep: { handler: 'feed' } }, grants: [] }), '')
  assert.doesNotMatch(model.refreshReason({ status: 'active', manifest: { upkeep: {} }, grants: [{ capability: 'refresh', status: 'revoked' }] }), /approval|Permissions/)
})
test('Diagnostics discloses the latest 2,000 retained log entries', async () => {
  setup()
  try {
    await render(GrantCard, { grant: { capability: 'logs', status: 'granted' }, onDecide() {} })
    assert.match(document.body.textContent, /Only the latest 2,000 log entries.*retained/)
  } finally { await act(async () => view.unmount()) }
})
for (const native of [false, true]) {
  test(`History incompatible restore explains versions for ${native ? 'native IPC' : 'structured'} error`, async () => {
    setup()
    data.revisions = [{ rev: 1, summary: 'Earlier code' }]
    const detail = { error: { code: 'incompatible', message: 'Data versions differ', from_version: 3, to_version: 1 } }
    const error = native ? new Error(`Error invoking remote method 'hermes:api': Error: 409: ${JSON.stringify(detail)}`) : detail
    try {
      await render(HistorySheet, { space: demo(), ctx: { rest: async () => { throw error } }, onClose() {}, onChanged() {}, initialTab: 'revisions' })
      await click('Restore…')
      await click('Restore as new revision')
      const text = document.querySelector('[role="alert"]').textContent
      assert.match(text, /Incompatible revision/)
      assert.match(text, /current data version 3/i)
      assert.match(text, /target data version 1/i)
      assert.match(text, /Data versions differ/)
      assert.match(text, /current code and records are unchanged/)
      assert.doesNotMatch(text, /from_version|to_version|Error invoking remote method/)
    } finally { await act(async () => view.unmount()) }
  })
}

test('local rejection can be dismissed without retrying or claiming it was saved', async () => {
  setup()
  let calls = 0
  try {
    await render(SpaceView, spaceProps(() => { calls++; return { ok: true, result: {} } }))
    await act(async () => mounted.onEvent(rejected('data.put')))
    await click('Dismiss')
    assert.equal(calls, 0)
    assert.doesNotMatch(document.body.textContent, /Not saved|Saved |Retry save/)
    await act(async () => mounted.call('data.put', { collection: 'notes', data: { text: 'corrected' } }))
    assert.equal(calls, 1)
    assert.match(document.querySelector('.ls-save').textContent, /Saved /)
  } finally { await act(async () => view.unmount()) }
})

test('failed catch-up in SpaceView preserves last-good header timestamps and failure state', async () => {
  setup()
  const props = spaceProps()
  data.detail = { ...data.detail, freshness: { last_success_at: 1700000000, source_as_of: 1699999900, last_attempt_at: 1794312000, last_attempt_status: 'failed' }, recent_runs: [{ id: 'failed-catch-up', status: 'failed', trigger: 'schedule', error: 'Source unavailable', detail: { dispatch } }] }
  try {
    await render(SpaceView, props)
    const header = document.querySelector('.ls-frame-meta').textContent
    assert.ok(header.includes(`Last successful update ${absolute(1700000000)}`))
    assert.ok(header.includes(`source data from ${absolute(1699999900)}`))
    assert.match(document.querySelector('.ls-identity').textContent, /Failed/)
    const banner = document.querySelector('.ls-banner.ls-failed').textContent
    assert.match(banner, /Refresh failed/)
    assert.ok(banner.includes(`You're seeing data from ${absolute(1700000000)}`))
    assert.match(banner, /Source unavailable/)
    await click('History')
    data.runs = data.detail.recent_runs
    await render(SpaceView, props)
    assert.match(document.body.textContent, /Catch-up refresh/)
    assert.match(document.body.textContent, /Missed intervals were not replayed/)
  } finally { await act(async () => view.unmount()) }
})
