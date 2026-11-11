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
const cache = new Map()
let dom, view, data, errors, options, refetches, nextData
function load(path) {
  if (cache.has(path)) return cache.get(path)
  const output = execFileSync('esbuild', ['--loader=jsx', '--format=cjs', '--jsx=automatic'], { input: readFileSync(path), encoding: 'utf8' })
  const module = { exports: {} }
  const imports = name => {
    if (name === '@hermes/plugin-sdk') return sdk
    if (name === './model.mjs') return model
    if (name === './session.mjs') return session
    if (name === '../sandbox/index.js') return { mountSpace: () => ({ destroy() {}, postEvent() {} }) }
    if (name.startsWith('.')) return load(resolve(dirname(path), name))
    return require(name)
  }
  // Only esbuild output from this checkout enters the test module loader.
  new Function('require', 'module', 'exports', output)(imports, module, module.exports)
  cache.set(path, module.exports)
  return module.exports
}
const sdk = { ...load(resolve(root, 'tests/js/ui/sdk-stub.js')), useQuery(query) {
  const key = query.queryKey[3]
  options[key] = query
  return { data: data[key], error: errors[key], dataUpdatedAt: 1700000000000, refetch: async () => {
    refetches.push(key)
    if (nextData[key]) data[key] = nextData[key]
    return { data: data[key], error: errors[key] }
  } }
} }
const { UpkeepSheet } = load(resolve(root, 'src/desktop/ui/upkeep.jsx'))
const { SpaceView } = load(resolve(root, 'src/desktop/ui/space.jsx'))
const { SpaceCard } = load(resolve(root, 'src/desktop/ui/index.jsx'))
const { PermissionsSheet } = load(resolve(root, 'src/desktop/ui/permissions.jsx'))
const { Time, absolute } = load(resolve(root, 'src/desktop/ui/components.jsx'))
before(() => {
  dom = new JSDOM('<div id="root"></div>', { url: 'https://demo.invalid', pretendToBeVisual: true })
  globalThis.window = dom.window
  globalThis.document = dom.window.document
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
})
after(() => dom.window.close())
const space = patch => ({ id: 'demo-space', name: 'Demo', owner: 'Atlas', status: 'active', head_rev: 2, grants: [], freshness: {}, manifest: { upkeep: { handler: 'feed' } }, ...patch })
const job = patch => ({ id: 'j1', enabled: true, state: 'scheduled', prompt: 'Update public research.', uses_model: true, schedule_display: 'Every day at 6:00 AM', timezone: 'America/Chicago', ...patch })
const payload = patch => ({ link: { cron_job_id: 'j1', kind: 'feed' }, job: job(), executions: [], one_shots: [], ...patch })
const props = rest => ({ space: space(), onClose() {}, onChanged() {}, ctx: { rest: rest || (async () => ({})) } })
function setup() { data = {}; errors = {}; options = {}; nextData = {}; refetches = []; view = createRoot(document.getElementById('root')) }
async function render(component, props) { await act(async () => view.render(React.createElement(component, props))) }
async function click(label) {
  const button = [...document.querySelectorAll('button')].find(button => button.textContent.trim() === label)
  assert.ok(button, label)
  await act(async () => button.click())
  return button
}
async function cleanup() { await act(async () => view.unmount()) }

test('accepted Run now does not claim a worker started before native execution', async () => {
  setup(); data.upkeep = payload()
  const calls = []
  try {
    await render(UpkeepSheet, props(async (path, options) => { calls.push({ path, options }); return data.upkeep }))
    await click('Run now')
    assert.equal(calls.length, 1)
    assert.equal(data.upkeep.job.state, 'scheduled')
    assert.deepEqual(data.upkeep.executions, [])
    const feedback = document.querySelector('.ls-upkeep-feedback').textContent
    assert.match(feedback, /Run requested/)
    assert.doesNotMatch(feedback, /Run started|Hermes is working on it/)
  } finally { await cleanup() }
})

for (const [freshness, expected, count] of [
  [{}, 'Not refreshed yet', 0],
  [{ last_attempt_status: 'failed' }, 'No successful update yet', 0],
  [{ last_success_at: 1700000000 }, 'Updated', 1],
  [{ last_success_at: 1700000000, source_as_of: 1699999950 }, 'Updated', 1],
  [{ last_success_at: 1700000000, source_as_of: 1699999940 }, 'Source data from', 2]
]) {
  test(`frame freshness ${JSON.stringify(freshness)} omits absent facts`, async () => {
    setup()
    data.detail = space({ freshness })
    try {
      await render(SpaceView, { sid: 'demo-space', ctx: { rest: async () => ({}) } })
      const header = document.querySelector('.ls-frame-meta')
      assert.match(header.textContent, new RegExp(expected))
      assert.equal(header.querySelectorAll('time').length, count)
      assert.doesNotMatch(header.textContent, /Not reported|Unknown|N\/A|—/)
      for (const time of header.querySelectorAll('time')) { assert.ok(time.dateTime); assert.ok(time.title); assert.match(time.textContent, /relative/) }
      assert.equal(document.querySelector('.ls-save').textContent, '')
      assert.equal(document.querySelector('.ls-caption'), null)
      assert.doesNotMatch(document.body.textContent, /running in a sandbox|No unsaved changes|Pause upkeep/)
      assert.match(document.querySelector('.ls-frame-actions').textContent, /Upkeep: none/)
    } finally { await cleanup() }
  })
}
test('a busy host refresh cannot submit another native run', async () => {
  setup(); data.detail = space({ freshness: { last_attempt_status: 'running' } })
  const calls = []
  const ctx = { rest: async path => { calls.push(path); return path.endsWith('/sessions') ? { session: 'demo', head_rev: 2, grants: [] } : path.endsWith('/bundle') ? { rev: 2 } : {} } }
  try {
    await render(SpaceView, { ctx, sid: 'demo-space' })
    const button = await click('Refreshing…')
    assert.equal(button.getAttribute('aria-disabled'), 'true')
    assert.deepEqual(calls.filter(path => path.endsWith('/refresh')), [])
  } finally { await cleanup() }
})
test('relative freshness advances on an unchanged native detail response', async () => {
  setup()
  const { QueryClient, QueryClientProvider, useQuery } = require('@tanstack/react-query')
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const originalQuery = sdk.useQuery
  const originalRelative = sdk.relativeTime
  sdk.useQuery = useQuery
  sdk.relativeTime = at => `age ${Math.floor((Date.now() - at) / 1000)}`
  const current = space({ freshness: { last_success_at: 1700000000 } })
  const ctx = { rest: async path => path === '/spaces/demo-space' ? current : path.endsWith('/sessions') ? { session: 'demo', head_rev: 2, grants: [] } : path.endsWith('/bundle') ? { rev: 2 } : {} }
  try {
    await render(QueryClientProvider, { client, children: React.createElement(SpaceView, { ctx, sid: 'demo-space' }) })
    await act(async () => new Promise(resolve => setTimeout(resolve, 30)))
    assert.ok(document.querySelector('.ls-frame-meta'), 'native detail has rendered before measuring freshness')
    const before = document.querySelector('.ls-frame-meta').textContent
    await act(async () => new Promise(resolve => setTimeout(resolve, 2200)))
    assert.notEqual(document.querySelector('.ls-frame-meta').textContent, before)
    assert.equal(client.getQueryData(['living-spaces', null, 'demo-space', 'detail']), current)
  } finally { await cleanup(); client.clear(); sdk.useQuery = originalQuery; sdk.relativeTime = originalRelative }
})
test('cards keep useful never-refreshed copy and omit absent source metadata', async () => {
  setup()
  try {
    await render(SpaceCard, { space: space() })
    assert.match(document.body.textContent, /Not refreshed yet/)
    assert.doesNotMatch(document.body.textContent, /Source data from|Not reported|Unknown|N\/A/)
  } finally { await cleanup() }
})
test('missing Time is absent even when a child was provided', async () => {
  setup()
  try { assert.equal(absolute(null), ''); await render(Time, { at: null, children: 'Missing' }); assert.equal(document.getElementById('root').textContent, '') } finally { await cleanup() }
})
for (const linked of [false, true]) {
  test(`cron unavailability is visible with ${linked ? 'a link' : 'no link'}, and cannot mutate native state`, async () => {
    setup()
    data.upkeep = payload({ link: linked ? { cron_job_id: 'j1' } : null, job: linked ? job() : null, error: 'cron module unavailable', one_shots: [{ executions: [{ id: 'once', status: 'unknown' }] }] })
    const calls = []
    try {
      await render(UpkeepSheet, props(async (...args) => calls.push(args)))
      assert.match(document.querySelector('[role="alert"]').textContent, /Hermes cron is unavailable.*cron module unavailable/)
      assert.match(document.querySelector('[data-testid="one-shots"]').textContent, /Outcome unknown/)
      if (linked) {
        for (const label of ['Run now', 'Pause', 'Remove']) { const button = await click(label); assert.equal(button.getAttribute('aria-disabled'), 'true') }
      }
      assert.deepEqual(calls, [])
    } finally { await cleanup() }
  })
}
test('running native job blocks another run but Pause remains available', async () => {
  setup()
  data.upkeep = payload({ job: job({ state: 'running' }) })
  nextData.upkeep = payload({ job: job({ state: 'running', enabled: false }) })
  const calls = []
  try {
    await render(UpkeepSheet, props(async (_, value) => calls.push(value.body)))
    assert.match(document.body.textContent, /Running now/)
    const run = await click('Run now')
    assert.equal(run.getAttribute('aria-disabled'), 'true')
    assert.equal(run.title, 'Already running')
    assert.deepEqual(calls, [])
    await click('Pause')
    assert.deepEqual(calls, [{ action: 'pause' }])
    assert.match(document.body.textContent, /Future runs stop.*Already-running work may finish/)
  } finally { await cleanup() }
})
test('busy upkeep keeps focus, deduplicates, and reports the read-back result', async () => {
  setup()
  data.upkeep = payload()
  nextData.upkeep = payload({ job: job({ enabled: false }) })
  const request = Promise.withResolvers()
  let calls = 0
  try {
    await render(UpkeepSheet, props(async () => { calls++; await request.promise }))
    const pause = [...document.querySelectorAll('button')].find(button => button.textContent === 'Pause')
    pause.focus()
    await click('Pause')
    assert.equal(document.activeElement, pause)
    assert.equal(pause.disabled, false)
    assert.equal(pause.getAttribute('aria-disabled'), 'true')
    await click('Pause')
    assert.equal(calls, 1)
    await act(async () => request.resolve())
    assert.equal(document.activeElement, pause)
    assert.equal(pause.textContent, 'Resume')
    assert.match(document.body.textContent, /Paused\. Future runs stop/)
    assert.deepEqual(refetches, ['upkeep'])
  } finally { request.resolve(); await cleanup() }
})
for (const [patch, queryError, expected] of [
  [null, null, 'Loading upkeep'],
  [null, new Error('offline'), "Upkeep couldn't be loaded"],
  [payload(), new Error('offline'), 'Showing the last loaded state'],
  [payload({ link: null, job: null }), null, 'No upkeep yet'],
  [payload({ job: null, missing: true }), null, 'Hermes no longer has this job'],
  [payload({ job: job({ enabled: false }) }), null, 'Paused. Future runs stop'],
  [payload({ job: job({ last_error: 'Source timed out', last_status: 'failed' }) }), null, 'Last run failed']
]) {
  test(`upkeep state ${expected} retains honest controls`, async () => {
    setup(); data.upkeep = patch; errors.upkeep = queryError
    try {
      await render(UpkeepSheet, props())
      assert.ok(document.body.textContent.includes(expected))
      assert.doesNotMatch(document.body.textContent, /Not reported|N\/A|—/)
      if (queryError && patch) { assert.match(document.body.textContent, /Update public research/); assert.equal([...document.querySelectorAll('button')].find(b => b.textContent === 'Run now').getAttribute('aria-disabled'), 'true') }
    } finally { await cleanup() }
  })
}
test('archived upkeep disables Run, Resume and Remove without claiming cancellation', async () => {
  setup(); data.upkeep = payload({ job: job({ enabled: false }) })
  const calls = []
  try {
    await render(UpkeepSheet, { ...props(async (...args) => calls.push(args)), space: space({ status: 'archived' }) })
    for (const label of ['Run now', 'Resume', 'Remove']) { assert.equal((await click(label)).getAttribute('aria-disabled'), 'true') }
    assert.deepEqual(calls, [])
    assert.match(document.body.textContent, /Already-running work may finish/)
  } finally { await cleanup() }
})
for (const action of ['pause', 'resume', 'remove']) {
  test(`unconfirmed ${action} never announces success`, async () => {
    setup(); data.upkeep = payload({ job: job({ enabled: action !== 'resume' }) })
    try {
      await render(UpkeepSheet, props())
      if (action === 'remove') {
        await click('Remove')
        const confirmation = document.querySelector('[role="alertdialog"]')
        assert.match(confirmation.textContent, /Keep upkeep/)
        await act(async () => [...confirmation.querySelectorAll('button')].find(b => b.textContent === 'Remove').click())
      } else await click(action === 'pause' ? 'Pause' : 'Resume')
      assert.match(document.body.textContent, /Hermes has not confirmed/)
      assert.doesNotMatch(document.querySelector('.ls-upkeep-feedback').textContent, /Paused\.|Resumed\.|Upkeep removed/)
    } finally { await cleanup() }
  })
}
test('Remove keeps the Space, reads back the absent link and announces removal', async () => {
  setup(); data.upkeep = payload()
  nextData.upkeep = payload({ link: null, job: null })
  const calls = []
  try {
    await render(UpkeepSheet, props(async (_, request) => calls.push(request.body)))
    await click('Remove')
    assert.deepEqual(calls, [])
    const confirmation = document.querySelector('[role="alertdialog"]')
    assert.match(confirmation.textContent, /already-running work may finish/)
    await act(async () => [...confirmation.querySelectorAll('button')].find(b => b.textContent === 'Remove').click())
    assert.deepEqual(calls, [{ action: 'remove' }])
    assert.match(document.body.textContent, /No upkeep yet/)
    assert.match(document.querySelector('.ls-upkeep-feedback').textContent, /Upkeep removed\. Demo is unchanged/)
    assert.deepEqual(refetches, ['upkeep'])
  } finally { await cleanup() }
})
test('a native feed job wins over a stale agent link and does not expose an obsolete prompt', async () => {
  setup(); data.upkeep = payload({ link: { kind: 'agent' }, job: job({ uses_model: false, prompt: 'Obsolete agent prompt' }) })
  try {
    await render(UpkeepSheet, props())
    assert.match(document.body.textContent, /Refreshes from public sources\. No model calls\./)
    assert.doesNotMatch(document.body.textContent, /Obsolete agent prompt|Uses model calls/)
    const facts = document.querySelector('dl').textContent
    assert.match(facts, /RunsEvery day at 6:00 AMAmerica\/Chicago/)
    assert.doesNotMatch(facts, /Kind|Cadence|Timezone|State/)
  } finally { await cleanup() }
})
test('native upkeep actions precede disclosure toggles in focus order', async () => {
  setup(); data.upkeep = payload()
  try {
    await render(UpkeepSheet, props())
    assert.deepEqual([...document.querySelectorAll('button')].map(button => button.textContent.trim()).slice(0, 5), ['Close', 'Run now', 'Pause', 'Remove', 'Show full prompt'])
  } finally { await cleanup() }
})
test('long native prompts expand and collapse accessibly', async () => {
  setup(); data.upkeep = payload({ job: job({ prompt: 'Public research context.\n'.repeat(8) }) })
  try {
    await render(UpkeepSheet, props())
    const expand = await click('Show full prompt')
    assert.equal(expand.getAttribute('aria-expanded'), 'true')
    assert.equal(document.querySelector('#ls-upkeep-prompt').className, '')
    await click('Show less')
    assert.equal(expand.getAttribute('aria-expanded'), 'false')
  } finally { await cleanup() }
})
test('upkeep polling speeds up for running jobs and pauses with document visibility', async () => {
  setup(); data.upkeep = payload()
  try {
    await render(UpkeepSheet, props())
    assert.equal(options.upkeep.refetchInterval({ state: { data: data.upkeep } }), 5000)
    assert.equal(options.upkeep.refetchInterval({ state: { data: payload({ job: job({ state: 'running' }) }) } }), 2000)
    Object.defineProperty(document, 'hidden', { value: true, configurable: true })
    await act(async () => document.dispatchEvent(new dom.window.Event('visibilitychange')))
    assert.equal(options.upkeep.refetchInterval({ state: { data: data.upkeep } }), false)
  } finally { Object.defineProperty(document, 'hidden', { value: false, configurable: true }); await cleanup() }
})
test('Internet failure keeps the switch focused, reads back truth and does not announce success', async () => {
  setup(); data.grants = { grants: [{ capability: 'net', status: 'revoked' }] }
  try {
    await render(PermissionsSheet, { ...props(async () => { throw new Error('offline') }) })
    const button = document.querySelector('[role="switch"]')
    button.focus()
    await act(async () => button.click())
    assert.equal(document.activeElement, button)
    assert.equal(button.getAttribute('aria-checked'), 'false')
    assert.equal(button.disabled, false)
    assert.match(document.querySelector('[role="alert"]').textContent, /Couldn't turn Internet access on.*offline/)
    assert.doesNotMatch(document.body.textContent, /Internet access turned on/)
    assert.deepEqual(refetches, ['grants'])
    assert.equal(document.querySelector('[data-testid="release-two"]'), null)
  } finally { await cleanup() }
})
test('loading announces a delayed native response after eight seconds', async t => {
  setup(); t.mock.timers.enable({ apis: ['setTimeout'] })
  try {
    await render(UpkeepSheet, props())
    assert.doesNotMatch(document.body.textContent, /Still waiting/)
    await act(async () => t.mock.timers.tick(8000))
    assert.match(document.body.textContent, /Still waiting for Hermes/)
    assert.ok(document.querySelector('[aria-busy="true"]'))
  } finally { await cleanup() }
})
test('upkeep success feedback expires after eight seconds', async t => {
  setup(); t.mock.timers.enable({ apis: ['setTimeout'] }); data.upkeep = payload()
  nextData.upkeep = payload({ job: job({ enabled: false }) })
  try {
    await render(UpkeepSheet, props())
    await click('Pause')
    assert.match(document.querySelector('.ls-upkeep-feedback').textContent, /Paused/)
    await act(async () => t.mock.timers.tick(8000))
    assert.equal(document.querySelector('.ls-upkeep-feedback').textContent, '')
  } finally { await cleanup() }
})
test('cached Internet settings stay visible but cannot be toggled while native state is unavailable', async () => {
  setup(); data.grants = { grants: [{ capability: 'net', status: 'granted' }] }; errors.grants = new Error('offline')
  let calls = 0
  try {
    await render(PermissionsSheet, props(async () => { calls++ }))
    assert.match(document.body.textContent, /Showing the last loaded access settings/)
    const button = document.querySelector('[role="switch"]')
    assert.equal(button.getAttribute('aria-checked'), 'true')
    assert.equal(button.getAttribute('aria-disabled'), 'true')
    await act(async () => button.click())
    assert.equal(calls, 0)
  } finally { await cleanup() }
})
test('a requested Internet switch stays Off and cannot bypass Approve or Deny', async () => {
  setup(); data.grants = { grants: [{ capability: 'net', status: 'requested' }] }
  let calls = 0
  try {
    await render(PermissionsSheet, props(async () => { calls++ }))
    const button = document.querySelector('[role="switch"]')
    assert.equal(button.getAttribute('aria-checked'), 'false')
    assert.equal(button.getAttribute('aria-disabled'), 'true')
    assert.match(document.body.textContent, /Atlas is asking to turn this on/)
    await act(async () => button.click())
    assert.equal(calls, 0)
    nextData.grants = { grants: [{ capability: 'net', status: 'denied' }] }
    await click('Deny')
    assert.equal(calls, 1)
  } finally { await cleanup() }
})

function dialogWithFocusLifecycle(DialogContent) {
  return function FocusDialogContent(props) {
    React.useEffect(() => {
      props.onOpenAutoFocus?.({ preventDefault() {} })
      return () => props.onCloseAutoFocus?.({ preventDefault() {} })
    }, [])
    return React.createElement(DialogContent, props)
  }
}

for (const status of [null, 'requested', 'denied', 'revoked', 'granted']) {
  test(`Space header shows Internet on only for net granted: ${status ?? 'absent'}`, async () => {
    setup()
    data.detail = space({ grants: [{ capability: 'logs', status: 'granted' }, ...(status ? [{ capability: 'net', status }] : [])] })
    try {
      await render(SpaceView, { sid: 'demo-space', ctx: { rest: async () => ({}) } })
      const header = document.querySelector('.ls-framebar')
      const controls = [...header.querySelectorAll('button')].filter(button => button.textContent.trim() === 'Internet on')
      assert.equal(controls.length, status === 'granted' ? 1 : 0)
      if (status === 'granted') {
        assert.equal(controls[0].disabled, false)
        assert.notEqual(controls[0].getAttribute('aria-disabled'), 'true')
      } else assert.doesNotMatch(header.textContent, /Internet on/)
    } finally { await cleanup() }
  })
}

for (const label of ['Permissions', 'Internet on']) {
  test(`${label} opens existing Permissions and returns focus to its opener`, async () => {
    setup()
    data.detail = space({ grants: [{ capability: 'net', status: 'granted' }] })
    data.grants = { grants: data.detail.grants }
    const originalDialogContent = sdk.DialogContent
    sdk.DialogContent = dialogWithFocusLifecycle(originalDialogContent)
    try {
      await render(SpaceView, { sid: 'demo-space', ctx: { rest: async () => ({}) } })
      const opener = [...document.querySelectorAll('.ls-framebar button')].find(button => button.textContent.trim() === label)
      assert.ok(opener, label)
      opener.focus()
      await click(label)
      const dialogs = document.querySelectorAll('[role="dialog"]')
      assert.equal(dialogs.length, 1)
      assert.equal(dialogs[0].querySelector('h2').textContent, 'Permissions · Demo')
      assert.equal(dialogs[0].querySelector('[role="switch"]').getAttribute('aria-checked'), 'true')
      const close = [...dialogs[0].querySelectorAll('button')].find(button => button.textContent.trim() === 'Close')
      assert.equal(document.activeElement, close)
      await click('Close')
      assert.equal(document.querySelector('[role="dialog"]'), null)
      assert.equal(document.activeElement, opener)
    } finally {
      try { await cleanup() } finally { sdk.DialogContent = originalDialogContent }
    }
  })
}

for (const status of [null, 'requested', 'denied', 'revoked']) {
  test(`Space detail update removes stale Internet on when net becomes ${status ?? 'absent'}`, async () => {
    setup()
    const otherGrant = { capability: 'logs', status: 'granted' }
    data.detail = space({ grants: [otherGrant, { capability: 'net', status: 'granted' }] })
    const viewProps = { sid: 'demo-space', ctx: { rest: async () => ({}) } }
    try {
      await render(SpaceView, viewProps)
      assert.ok([...document.querySelectorAll('.ls-framebar button')].some(button => button.textContent.trim() === 'Internet on'))
      data.detail = { ...data.detail, grants: [otherGrant, ...(status ? [{ capability: 'net', status }] : [])] }
      await render(SpaceView, viewProps)
      assert.doesNotMatch(document.querySelector('.ls-framebar').textContent, /Internet on/)
    } finally { await cleanup() }
  })
}

test('revoking Internet in Permissions refreshes Space detail and removes Internet on', async () => {
  setup()
  data.detail = space({ grants: [{ capability: 'net', status: 'granted' }] })
  data.grants = { grants: data.detail.grants }
  nextData.detail = { ...data.detail, grants: [{ capability: 'net', status: 'revoked' }] }
  nextData.grants = { grants: nextData.detail.grants }
  const calls = []
  try {
    await render(SpaceView, { sid: 'demo-space', ctx: { rest: async (path, request) => { calls.push({ path, request }); return {} } } })
    await click('Internet on')
    const toggle = document.querySelector('[role="switch"]')
    assert.equal(toggle.getAttribute('aria-checked'), 'true')
    await act(async () => toggle.click())
    assert.deepEqual(calls.filter(call => call.path === '/spaces/demo-space/grants/net'), [{ path: '/spaces/demo-space/grants/net', request: { method: 'POST', body: { decision: 'revoke' } } }])
    assert.deepEqual(refetches, ['grants', 'detail'])
    assert.equal(toggle.getAttribute('aria-checked'), 'false')
    await render(SpaceView, { sid: 'demo-space', ctx: { rest: async (path, request) => { calls.push({ path, request }); return {} } } })
    assert.doesNotMatch(document.querySelector('.ls-framebar').textContent, /Internet on/)
  } finally { await cleanup() }
})

for (const [label, title, startWidth, endWidth, hidden] of [
  ['History', 'History & revisions', 900, 640, true],
  ['History', 'History & revisions', 1000, 900, false],
  ['Upkeep: none', 'Upkeep · Demo', 640, 599, true],
  ['Upkeep: none', 'Upkeep · Demo', 900, 600, false]
]) {
  test(`${label} drawer returns focus to ${hidden ? 'overflow when its connected opener is hidden' : 'its still-visible opener'} after panel resize ${startWidth} to ${endWidth}`, async t => {
    setup()
    data.detail = space()
    data.runs = []
    data.upkeep = payload({ link: null, job: null })
    const originalDialogContent = sdk.DialogContent
    const globals = ['ResizeObserver', 'getComputedStyle'].map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)])
    const stylesheet = document.createElement('style')
    let panelWidth = startWidth
    let resize
    const originalRect = dom.window.Element.prototype.getBoundingClientRect
    const hasRenderedBox = element => {
      if (!element.isConnected) return false
      for (let ancestor = element; ancestor; ancestor = ancestor.parentElement) {
        const style = window.getComputedStyle(ancestor)
        if (style.display === 'none' || style.visibility === 'hidden' || style.visibility === 'collapse') return false
      }
      return true
    }
    try {
      stylesheet.textContent = load(resolve(root, 'src/desktop/ui/styles.js')).styles
      document.head.append(stylesheet)
      globalThis.getComputedStyle = window.getComputedStyle.bind(window)
      globalThis.ResizeObserver = class {
        constructor(callback) { resize = callback }
        observe() {}
        disconnect() {}
      }
      t.mock.method(dom.window.Element.prototype, 'getBoundingClientRect', function () {
        return this.classList.contains('ls-frame') ? new dom.window.DOMRect(0, 0, panelWidth, 800) : originalRect.call(this)
      })
      sdk.DialogContent = dialogWithFocusLifecycle(originalDialogContent)
      await render(SpaceView, { sid: 'demo-space', ctx: { rest: async () => ({}) } })
      const opener = [...document.querySelectorAll('.ls-framebar button')].find(button => button.textContent.trim() === label)
      const overflow = document.querySelector('button[aria-label="More Space actions"]')
      assert.ok(opener, label)
      assert.ok(overflow)
      for (const element of [opener, overflow]) {
        const focus = element.focus
        t.mock.method(element, 'getClientRects', () => hasRenderedBox(element) ? [new dom.window.DOMRect(0, 0, 100, 32)] : [])
        t.mock.method(element, 'getBoundingClientRect', () => hasRenderedBox(element) ? new dom.window.DOMRect(0, 0, 100, 32) : new dom.window.DOMRect())
        t.mock.method(element, 'focus', function (...args) {
          if (hasRenderedBox(this)) focus.apply(this, args)
        })
      }
      assert.ok(hasRenderedBox(opener), 'the direct opener is visible before opening the drawer')
      opener.focus()
      assert.equal(document.activeElement, opener)
      await click(label)
      const dialog = document.querySelector('[role="dialog"]')
      assert.ok(dialog)
      assert.equal(dialog.querySelector('h2').textContent, title)
      const close = [...dialog.querySelectorAll('button')].find(button => button.textContent.trim() === 'Close')
      assert.ok(close)
      assert.equal(document.activeElement, close)
      assert.equal(typeof resize, 'function')
      await act(async () => { panelWidth = endWidth; resize() })
      assert.equal(document.querySelector('[role="dialog"]'), dialog, 'the drawer stays open during the panel resize')
      assert.equal(opener.isConnected, true, 'responsive CSS retains the original opener in the document')
      assert.equal(hasRenderedBox(opener), !hidden, 'actual responsive CSS determines opener visibility')
      assert.equal(opener.getClientRects().length, hidden ? 0 : 1, 'JSDOM layout is modeled for hidden and visible controls')
      assert.ok(hasRenderedBox(overflow), 'overflow remains a visible focus destination')
      if (hidden) {
        opener.focus()
        assert.equal(document.activeElement, close, 'modeled browser focus ignores an opener under display:none')
      }
      await click('Close')
      assert.equal(document.querySelector('[role="dialog"]'), null)
      assert.ok(document.activeElement === (hidden ? overflow : opener), 'drawer close restores focus to the visible destination')
    } finally {
      try { await cleanup() } finally {
        sdk.DialogContent = originalDialogContent
        t.mock.restoreAll()
        stylesheet.remove()
        for (const [key, descriptor] of globals) {
          if (descriptor) Object.defineProperty(globalThis, key, descriptor)
          else delete globalThis[key]
        }
      }
    }
  })
}
