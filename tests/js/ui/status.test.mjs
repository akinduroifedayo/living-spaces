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
let lastProps
async function render(Component, props) { if (Component === SpaceView) lastProps = props; await act(async () => view.render(React.createElement(Component, props))) }
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
    assert.doesNotMatch(text, /0 \* \* \* \*/, 'human-readable native schedule replaces raw cron')
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
    assert.match(document.body.textContent, /Hermes no longer has this job/)
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
    assert.match(document.body.textContent, /No upkeep yet/)
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
    // The island carries one phrase: the failure, and how old the data on screen is.
    const header = document.querySelector('.ls-frame-meta').textContent
    assert.match(header, /Refresh failed · data from · relative 1700000000000/)
    const times = document.querySelectorAll('.ls-frame-meta time')
    assert.equal(times.length, 1)
    assert.equal(times[0].title, absolute(1700000000))
    assert.match(document.querySelector('.ls-identity').textContent, /Failed/)
    // The full set of freshness facts, including the source age, lives in Details.
    await click('Details')
    const details = document.querySelector('section[aria-label="Freshness"]').textContent
    assert.ok(details.includes(`Last successful update${absolute(1700000000)}`))
    assert.ok(details.includes(`Source data from${absolute(1699999900)}`))
    const banner = document.querySelector('.ls-banner.ls-failed').textContent
    assert.match(banner, /Refresh failed/)
    assert.ok(banner.includes(`You're seeing data from ${absolute(1700000000)}`))
    assert.match(banner, /Source unavailable/)
    await click('Open history')
    data.runs = data.detail.recent_runs
    await render(SpaceView, props)
    assert.match(document.body.textContent, /Catch-up refresh/)
    assert.match(document.body.textContent, /Missed intervals were not replayed/)
  } finally { await act(async () => view.unmount()) }
})

// Runtime state lives only in the Details drawer: open it from the island's Details control, read its Runtime
// section, close it.
async function q04Details() {
  const opener = [...document.querySelectorAll('.ls-framebar button')].find(button => button.textContent.trim() === 'Details')
  assert.ok(opener, 'the Space island offers Details')
  await act(async () => opener.click())
  const dialog = document.querySelector('[role="dialog"]')
  assert.ok(dialog, 'Details opens a drawer')
  assert.match(dialog.textContent, /Space details/)
  // The Space's mark appears once, as the 96 px hero; the header carries only the title and Close.
  const tiles = [...dialog.querySelectorAll('.ls-tile')]
  assert.equal(tiles.length, 1, 'Details shows the Space mark exactly once')
  assert.ok(tiles[0].closest('section[aria-label="Space"]'), 'the one mark is the hero')
  assert.equal(tiles[0].style.width, '96px')
  assert.equal(dialog.querySelector('.ls-sheet-header .ls-tile'), null, 'the header repeats no mark')
  const facts = Object.fromEntries([...dialog.querySelectorAll('section[aria-label="Runtime"] dl div')].map(row => [row.querySelector('dt').textContent, row.querySelector('dd').textContent]))
  await click('Close')
  assert.equal(document.querySelector('[role="dialog"]'), null)
  return facts
}
const Q04_WORDS = { unknown: 'Not reported', starting: 'Starting', loaded: 'Loaded', failed: 'Failed', faulted: 'Faulted (uncaught error, still running)' }
const q04Guest = async (...states) => {
  const facts = await q04Details()
  assert.equal(facts.Host, 'Available')
  assert.ok(states.map(state => Q04_WORDS[state]).includes(facts['Space app']), `Space app is ${facts['Space app']}, expected ${states.join(' or ')}`)
  if (!states.includes('loaded')) assert.notEqual(facts['Space app'], 'Loaded', 'Details must not claim the app loaded')
  return facts
}
// Runtime and readiness appear nowhere on the canvas; the host has no app-readiness signal at all.
const q04NoAppReadiness = () => {
  assert.doesNotMatch(document.body.textContent, /App readiness|Guest runtime|Space app/i)
}
const q04Log = (lifecycle, entries = []) => ({ entries, ...(lifecycle ? { lifecycle } : {}) })

test('Q04 status dimensions keep host guest save and freshness independent', () => {
  assert.equal(typeof model.statusDimensions, 'function')
  assert.equal(model.PILLS.ready.label, 'Available')
  const freshness = Object.freeze({ last_success_at: 1700000000, last_attempt_status: 'failed', source_as_of: 1699999900 })
  const space = Object.freeze({ ...demo(), freshness, attention: { kind: 'crashed' } })
  assert.deepEqual(model.statusDimensions(space), { host: 'available', guest: 'unknown', save: 'idle', freshness })
  for (const guest of ['unknown', 'starting', 'loaded', 'failed']) {
    for (const save of ['saving', 'saved', 'failed', 'unknown', 'conflict']) {
      assert.deepEqual(model.statusDimensions(space, { guest, write: { status: save } }),
        { host: 'available', guest, save, freshness })
    }
  }
  for (const [patch, options, host] of [
    [{ status: 'building' }, {}, 'building'],
    [{ head_rev: 0 }, {}, 'building'],
    [{ status: 'archived' }, {}, 'archived'],
    [{}, { hostError: true }, 'unavailable']
  ]) {
    assert.deepEqual(model.statusDimensions({ ...space, ...patch }, options),
      { host, guest: 'unknown', save: 'idle', freshness })
  }
  assert.equal(model.statusDimensions({ ...demo(), freshness: null }).freshness, null)
})

for (const [name, message] of [
  ['boot-load text', 'Handled boot entry load warning; retry succeeded'],
  ['repeated ordinary errors', 'Handled validation error']
]) {
  test(`Q04 ${name} never stops a loaded guest`, async () => {
    setup()
    const calls = []
    const props = spaceProps(body => { calls.push(body); return { ok: true, result: { stored: 0 } } })
    try {
      await render(SpaceView, props)
      await act(async () => mounted.call('log', q04Log('loaded')))
      const activeMount = mounted
      const header = document.querySelector('.ls-frame-meta').textContent
      await act(async () => activeMount.call('data.put', { collection: 'notes', data: { note: 'Kept' } }))
      for (let repeat = 0; repeat < 4; repeat++) {
        await act(async () => activeMount.onEvent({ kind: 'error', message, phase: 'runtime', fatal: true }))
        assert.ok(document.querySelector('[data-testid="space-host"]'), `guest survives console error ${repeat + 1}`)
        assert.doesNotMatch(document.body.textContent, /Demo stopped working|uncaught error/)
      }
      assert.equal(document.querySelector('.ls-frame-meta').textContent, header)
      assert.match(document.querySelector('.ls-save').textContent, /Saved /)
      assert.deepEqual(calls.map(call => call.op), ['log', 'data.put'])
      await q04Guest('loaded')
      q04NoAppReadiness()
    } finally { await act(async () => view.unmount()) }
  })
}

test('Q04 an uncaught guest fault after first paint raises runtime attention without stopping the app', async () => {
  setup()
  const calls = []
  try {
    await render(SpaceView, spaceProps(body => { calls.push(body); return { ok: true, result: { stored: 0 } } }))
    const activeMount = mounted
    await act(async () => activeMount.call('log', q04Log('loaded')))
    await act(async () => activeMount.call('data.put', { collection: 'notes', data: { note: 'Kept' } }))
    await act(async () => activeMount.onEvent({ kind: 'fault', count: 1 }))
    assert.ok(document.querySelector('[data-testid="space-host"]'), 'the app stays mounted')
    assert.match(document.body.textContent, /uncaught error/)
    assert.doesNotMatch(document.body.textContent, /Demo stopped working/)
    assert.match(document.querySelector('.ls-save').textContent, /Saved /)
    await q04Guest('faulted')
    q04NoAppReadiness()
    await act(async () => activeMount.call('log', q04Log('loaded')))
    await q04Guest('faulted')
  } finally { await act(async () => view.unmount()) }
})

test('Q04 a later boot failure supersedes a runtime fault', async () => {
  setup()
  try {
    await render(SpaceView, spaceProps(body => ({ ok: true, result: { stored: body.args.entries?.length || 0 } })))
    const activeMount = mounted
    await act(async () => activeMount.onEvent({ kind: 'fault', count: 1 }))
    await q04Guest('faulted')
    await act(async () => activeMount.call('log', q04Log('failed', [{ level: 'error', msg: 'Evaluation refused' }])))
    assert.match(document.body.textContent, /Demo stopped working/)
    await q04Guest('failed')
    await act(async () => activeMount.onEvent({ kind: 'fault', count: 2 }))
    await q04Guest('failed')
  } finally { await act(async () => view.unmount()) }
})

test('Q04 session creation and shell boot do not claim guest loaded or app readiness', async () => {
  setup()
  try {
    await render(SpaceView, spaceProps())
    assert.ok(mounted, 'session creation reached the mount seam')
    assert.doesNotMatch(document.body.textContent, /\bReady\b|(?:guest|application|runtime)[^.!?\n]{0,60}\bloaded\b/i)
    await q04Guest('unknown', 'starting')
    await act(async () => mounted.onEvent({ kind: 'booted' }))
    await q04Guest('starting')
    assert.doesNotMatch(document.body.textContent, /(?:guest|application|runtime)[^.!?\n]{0,60}\bloaded\b/i)
    q04NoAppReadiness()
    await act(async () => mounted.call('log', q04Log('loaded')))
    await q04Guest('loaded')
    q04NoAppReadiness()
    assert.doesNotMatch(document.body.textContent, /\bReady\b/i)
  } finally { await act(async () => view.unmount()) }
})

test('Q04 mount lifecycle failed supersedes loaded and stays failed after loaded', async () => {
  setup()
  const calls = []
  try {
    await render(SpaceView, spaceProps(body => { calls.push(body); return { ok: true, result: { stored: body.args.entries?.length || 0 } } }))
    const activeMount = mounted
    await act(async () => activeMount.call('log', q04Log('loaded')))
    assert.ok(document.querySelector('[data-testid="space-host"]'))
    await act(async () => activeMount.call('log', q04Log('failed', [{ level: 'error', msg: 'Evaluation refused' }])))
    assert.deepEqual(calls.map(call => call.args.lifecycle), ['loaded', 'failed'], 'real mount calls reached the bridge')
    assert.match(document.body.textContent, /Demo stopped working/)
    await q04Guest('failed')
    await act(async () => activeMount.call('log', q04Log('loaded')))
    await q04Guest('failed')
    assert.match(document.body.textContent, /Demo stopped working/)
  } finally { await act(async () => view.unmount()) }
})

test('Q04 error log entries without lifecycle do not fail a loaded guest', async () => {
  setup()
  const calls = []
  try {
    await render(SpaceView, spaceProps(body => { calls.push(body); return { ok: true, result: { stored: body.args.entries.length } } }))
    await act(async () => mounted.call('log', q04Log('loaded')))
    const entries = Array.from({ length: 4 }, () => ({ level: 'error', msg: 'Handled boot load failure' }))
    await act(async () => mounted.call('log', q04Log(null, entries)))
    assert.deepEqual(calls.map(call => call.args), [q04Log('loaded'), { entries }])
    assert.ok(document.querySelector('[data-testid="space-host"]'))
    assert.doesNotMatch(document.body.textContent, /Demo stopped working/)
    await q04Guest('loaded')
  } finally { await act(async () => view.unmount()) }
})

test('Q04 old mount events and lifecycle replies cannot change the replacement view', async () => {
  setup()
  let releaseOld
  const props = spaceProps(body => body.op === 'log' && body.args.lifecycle === 'failed'
    ? new Promise(resolve => { releaseOld = resolve }) : { ok: true, result: { stored: 0 } })
  try {
    await render(SpaceView, { ...props, scopeKey: 'old' })
    const oldMount = mounted
    let pending
    await act(async () => { pending = oldMount.call('log', q04Log('failed')) })
    assert.equal(typeof releaseOld, 'function', 'old request reached transport before replacement')
    await render(SpaceView, { ...props, scopeKey: 'replacement' })
    assert.notEqual(mounted, oldMount)
    await act(async () => mounted.call('log', q04Log('loaded')))
    await act(async () => {
      oldMount.onEvent({ kind: 'fault', count: 1 })
      oldMount.onEvent({ kind: 'booted' })
      releaseOld({ ok: true, result: { stored: 0 } })
      await pending
      await oldMount.call('log', q04Log('failed'))
    })
    assert.ok(document.querySelector('[data-testid="space-host"]'))
    assert.doesNotMatch(document.body.textContent, /Demo stopped working|uncaught error/)
    await q04Guest('loaded')
    q04NoAppReadiness()
  } finally {
    releaseOld?.({ ok: true, result: { stored: 0 } })
    await act(async () => view.unmount())
  }
})

test('Q04 loaded guest and failed save preserve authoritative failed-refresh freshness', async () => {
  setup()
  const props = spaceProps()
  data.detail = { ...data.detail, freshness: { ...data.detail.freshness, last_attempt_status: 'failed', last_attempt_at: 1794312000 },
    recent_runs: [{ id: 'q04-refresh', status: 'failed', error: 'Source unavailable' }] }
  const freshness = structuredClone(data.detail.freshness)
  try {
    await render(SpaceView, props)
    const header = document.querySelector('.ls-frame-meta').textContent
    await act(async () => mounted.call('log', q04Log('loaded')))
    await act(async () => mounted.onEvent(rejected('data.put')))
    assert.match(document.querySelector('.ls-save').textContent, /Not saved/)
    assert.match(document.body.textContent, /Refresh failed/)
    assert.match(document.body.textContent, /Source unavailable/)
    assert.equal(document.querySelector('.ls-frame-meta').textContent, header)
    assert.deepEqual(data.detail.freshness, freshness)
    assert.ok(document.querySelector('[data-testid="space-host"]'))
    await q04Guest('loaded')
    q04NoAppReadiness()
  } finally { await act(async () => view.unmount()) }
})

test('Q04 revision compatibility requires positive integer versions on both sides', () => {
  assert.equal(typeof model.revisionCompatibility, 'function')
  const revision = version => ({ manifest: { data: { version } } })
  assert.equal(model.revisionCompatibility({ data_version: 3 }, revision(3)), 'compatible')
  assert.equal(model.revisionCompatibility({ data_version: 3 }, revision(1)), 'incompatible')
  assert.equal(model.revisionCompatibility({ data_version: 1 }, revision(3)), 'incompatible')
  for (const version of [undefined, null, 0, -1, 1.5, '3', true, NaN, Infinity]) {
    assert.equal(model.revisionCompatibility({ data_version: version }, revision(3)), 'unknown', `current ${String(version)}`)
    assert.equal(model.revisionCompatibility({ data_version: 3 }, revision(version)), 'unknown', `target ${String(version)}`)
  }
  assert.equal(model.revisionCompatibility({}, {}), 'unknown')
})

test('Q04 incompatible revision displays both versions and offers no mutation', async () => {
  setup()
  data.revisions = [{ rev: 1, summary: 'Version one code', manifest: { data: { version: 1 } } }]
  const calls = []
  try {
    await render(HistorySheet, { space: { ...demo(), data_version: 3 }, initialTab: 'revisions', onClose() {}, onChanged() {},
      ctx: { rest: async (path, options) => { calls.push({ path, options }); return {} } } })
    const row = document.querySelector('article.ls-row')
    assert.ok(row)
    const restore = [...row.querySelectorAll('button')].find(button => /Restore/.test(button.textContent))
    if (restore) await act(async () => restore.click())
    assert.equal(document.querySelector('[role="alertdialog"]'), null, 'known incompatible code cannot open a restore confirmation')
    assert.deepEqual(calls, [])
    assert.match(row.textContent, /incompatible/i)
    assert.match(row.textContent, /current data version\s*3/i)
    assert.match(row.textContent, /target data version\s*1/i)
    assert.match(document.body.textContent, /(?:no|not supported|unsupported|cannot)[\s\S]{0,100}(?:cross.version|migration|restore)|(?:cross.version|migration)[\s\S]{0,100}(?:not supported|unsupported|cannot)/i)
    assert.doesNotMatch(document.body.textContent, /Restore recovery point/i)
  } finally { await act(async () => view.unmount()) }
})

test('Q04 compatible revision restore explains code-only and unsupported migration undo', async () => {
  setup()
  data.revisions = [{ rev: 1, summary: 'Earlier code', manifest: { data: { version: 3 } } }]
  const calls = []
  let changed = 0
  try {
    await render(HistorySheet, { space: { ...demo(), data_version: 3 }, initialTab: 'revisions', onClose() {}, onChanged() { changed++ },
      ctx: { rest: async (path, options) => { calls.push({ path, method: options?.method }); return { rev: 3 } } } })
    assert.match(document.querySelector('article.ls-row').textContent, /\bcompatible\b/i)
    await click('Restore…')
    assert.deepEqual(calls, [])
    const dialog = document.querySelector('[role="alertdialog"]')
    assert.ok(dialog)
    assert.match(dialog.textContent, /earlier code.*new revision 3/i)
    assert.match(dialog.textContent, /records, notes and statuses stay as they are now/i)
    assert.match(document.body.textContent, /(?:migration|downgrade)[\s\S]{0,60}(?:not supported|unsupported|cannot|not undone)|(?:no|cannot|not supported)[\s\S]{0,60}(?:migration|downgrade)/i)
    assert.doesNotMatch(document.body.textContent, /Restore recovery point/i)
    await click('Restore as new revision')
    assert.deepEqual(calls, [{ path: '/spaces/demo-space/revisions/1/restore', method: 'POST' }])
    assert.equal(changed, 1)
    assert.equal(data.refetches, 1)
  } finally { await act(async () => view.unmount()) }
})

test('Q04 unknown revision compatibility stays explicit and backend refusal remains authoritative', async () => {
  setup()
  data.revisions = [{ rev: 1, summary: 'Manifest unavailable' }]
  const calls = []
  try {
    await render(HistorySheet, { space: { ...demo(), data_version: 3 }, initialTab: 'revisions', onClose() {}, onChanged() {},
      ctx: { rest: async path => { calls.push(path); throw { error: { code: 'incompatible', message: 'Data versions differ', from_version: 3, to_version: 1 } } } } })
    assert.match(document.querySelector('article.ls-row').textContent, /(?:compatibility[^.!?\n]{0,40}unknown|unknown[^.!?\n]{0,40}compatibility)/i)
    await click('Restore…')
    await click('Restore as new revision')
    assert.deepEqual(calls, ['/spaces/demo-space/revisions/1/restore'])
    const alert = document.querySelector('[role="alert"]').textContent
    assert.match(alert, /current data version 3/i)
    assert.match(alert, /target data version 1/i)
    assert.match(alert, /current code and records are unchanged/i)
  } finally { await act(async () => view.unmount()) }
})

for (const [version, expected] of [[1, 'incompatible'], [2, 'compatible'], [null, 'unknown']]) {
  test(`Q04 actual recovery point metadata is ${expected} without offering data undo`, async () => {
    setup()
    data.revisions = [{ rev: 2, summary: 'Current code', manifest: { data: { version: 2 } } }]
    data['recovery-points'] = [{ id: 7, head_rev: 1, data_version: version, reason: 'Before migration', created_at: 1700000000 }]
    const calls = []
    try {
      await render(HistorySheet, { space: { ...demo(), data_version: 2 }, initialTab: 'revisions', onClose() {}, onChanged() {},
        ctx: { rest: async (...args) => { calls.push(args); return {} } } })
      const point = document.querySelector('[data-testid="recovery-point-7"]')
      assert.ok(point, 'Real recovery metadata needs its own row, not a renamed revision')
      assert.match(point.textContent, new RegExp(`Compatibility: ${expected}\\b`, 'i'))
      assert.match(point.textContent, /Before migration/)
      assert.match(point.textContent, /code revision 1/i)
      assert.match(point.textContent, /(?:no data restore|data restore is not supported)/i)
      assert.equal(point.querySelectorAll('button').length, 0)
      assert.deepEqual(calls, [])
      if (expected === 'incompatible') {
        assert.match(point.textContent, /current data version 2/i)
        assert.match(point.textContent, /point data version 1/i)
        assert.match(point.textContent, /cross-version restore is not supported/i)
      }
    } finally { await act(async () => view.unmount()) }
  })
}
