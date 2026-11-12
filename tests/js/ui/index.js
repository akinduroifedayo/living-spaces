const { test, before, after } = require('node:test')
const assert = require('node:assert/strict')
const { mkdtempSync, mkdirSync, rmSync, readFileSync } = require('node:fs')
const { resolve, join } = require('node:path')
const sandbox = { format: 1, shell_srcdoc: readFileSync('src/living-spaces/guest/space-host.html', 'utf8') }
let m, createSpaceSession, mountSpace, temp
before(async () => {
  mkdirSync(resolve('.run'), { recursive: true })
  temp = mkdtempSync(resolve('.run/ui-unit-'))
  process.env.HERMES_HOME = temp
  process.env.LIVING_SPACES_DB = join(temp, 'spaces.db')
  m = await import('../../../src/desktop/ui/model.mjs')
  ;({ mountSpace } = await import('../../../src/desktop/sandbox/index.js'))
  ;({ createSpaceSession } = await import('../../../src/desktop/ui/session.mjs'))
})
after(() => rmSync(temp, { recursive: true, force: true }))
const space = patch => ({ id: 'research-desk', name: 'Research Desk', owner: 'Atlas', status: 'active', head_rev: 7, updated_at: 100, freshness: {}, ...patch })
const deferred = () => Promise.withResolvers()

test('Desktop source and bundle use public SDK APIs without an undeclared query scope', () => {
  const { readdirSync } = require('node:fs')
  function check(directory) {
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
      const path = join(directory, entry.name)
      if (entry.isDirectory()) check(path)
      else assert.doesNotMatch(readFileSync(path, 'utf8'), /\bqueryScope\b|hermesDesktop|\bbackend\.api\b/, path)
    }
  }
  check('src/desktop')
  assert.doesNotMatch(readFileSync('src/living-spaces/desktop/plugin.js', 'utf8'), /\bqueryScope\b|hermesDesktop|\bbackend\.api\b/)
})

test('directive IDs accept only the frozen slug grammar', () => {
  for (const id of ['ab', 'a-2', 'a'.repeat(48), '0a']) assert.equal(m.isSpaceId(id), true, id)
  for (const id of [undefined, null, 34, '', 'a', 'a'.repeat(49), '../research', 'Research', 'ab?x=1', 'ab\n', 'ab/xx', 'ab%00', '<script>']) assert.equal(m.isSpaceId(id), false, String(id))
})
test('hash routing validates decoded IDs and ignores unrelated parameters', () => {
  assert.equal(m.routeSpace('#/spaces?space=research-desk&other=1'), 'research-desk')
  assert.equal(m.routeSpace('#/spaces?space=%2Fetc'), null)
  assert.equal(m.routeSpace('#/spaces'), null)
  assert.equal(m.spaceRoute('research-desk'), '/spaces?space=research-desk')
})
test('status hierarchy preserves archive and building before transient runs', () => {
  assert.equal(m.spaceStatus(space({ status: 'archived', attention: { kind: 'failed' } })), 'archived')
  assert.equal(m.spaceStatus(space({ head_rev: 0 })), 'building')
  assert.equal(m.spaceStatus(space({ freshness: { last_attempt_status: 'running' }, attention: { kind: 'failed' } })), 'updating')
  assert.equal(m.spaceStatus(space({ attention: { kind: 'crashed' } })), 'failed')
  assert.equal(m.spaceStatus(space({ attention: { kind: 'crashed' } }), true), 'crashed')
})
test('pill models communicate status with words, glyphs and border patterns', () => {
  for (const status of ['ready', 'building', 'updating', 'failed', 'blocked', 'archived', 'crashed']) {
    assert.ok(m.PILLS[status].label)
    assert.ok(m.PILLS[status].icon)
  }
  assert.equal(m.PILLS.building.border, 'dashed')
  assert.equal(m.PILLS.archived.border, 'dotted')
})
test('attention counts exclude archived errors and distinguish blocked from running', () => {
  assert.deepEqual(m.summaryCounts([space(), space({ attention: { kind: 'failed' } }), space({ freshness: { last_attempt_status: 'blocked' } }), space({ status: 'archived', attention: { kind: 'crashed' } }), space({ freshness: { last_attempt_status: 'running' } })]), { active: 4, attention: 2 })
})
test('pinned cards precede recently used cards and search matches owners', () => {
  const spaces = [space({ id: 'recent', last_opened_at: 500 }), space({ id: 'pinned', pinned: true, last_opened_at: 1 }), space({ id: 'old', owner: 'Kit', last_opened_at: 10 }), space({ id: 'archived', status: 'archived' })]
  assert.deepEqual(m.visibleSpaces(spaces, '', 'all').map(s => s.id), ['pinned', 'recent', 'old'])
  assert.deepEqual(m.visibleSpaces(spaces, ' kit ', 'all').map(s => s.id), ['old'])
  assert.deepEqual(m.visibleSpaces(spaces, '', 'archived').map(s => s.id), ['archived'])
})
test('freshness keeps success, attempt, source and next run as separate facts', () => {
  const facts = m.freshnessFacts(space({ freshness: { last_success_at: 10, last_attempt_at: 20, last_attempt_status: 'failed', source_as_of: 5, next_run_at: 30 } }), t => `time ${t}`)
  assert.deepEqual(facts.map(f => f.value), ['time 10', 'time 20 · failed', 'time 5', 'time 30'])
  assert.deepEqual(facts.map(f => f.at), [10, 20, 5, 30])
  assert.deepEqual(m.freshnessFacts(space(), String), [])
})
test('failed card never presents a failed attempt as a good update', () => {
  assert.deepEqual(m.cardLines(space({ freshness: { last_success_at: 10, last_attempt_at: 20, last_attempt_status: 'failed' } }), String), ['Refresh failed 20', 'Showing last good data from 10'])
})
test('change cursor advances through delivered rows, not past a truncated page', () => {
  assert.deepEqual(m.advanceCursor(3, { seq: 100, changes: [{ seq: 5, id: 'b' }, { seq: 4, id: 'a' }] }), { seq: 5, changes: [{ seq: 4, id: 'a' }, { seq: 5, id: 'b' }] })
  assert.deepEqual(m.advanceCursor(5, { seq: 100, changes: [{ seq: 5 }] }), { seq: 5, changes: [] })
  assert.deepEqual(m.advanceCursor(5, { seq: 100, changes: [] }), { seq: 5, changes: [] })
})
test('no-change refreshes remain successful results', () => {
  assert.equal(m.runResult({ status: 'succeeded', changed: { unchanged: 23 } }), 'no change · 23 unchanged')
  assert.equal(m.runResult({ status: 'succeeded', changed: { added: 2, updated: 3 } }), '2 added · 3 updated · 0 unchanged')
  assert.equal(m.runResult({ status: 'blocked', detail: { reason: 'not_granted' } }), 'Blocked: not_granted')
})
test('refresh reasons cover handler and archived restrictions only', () => {
  assert.match(m.refreshReason(space()), /No refresh handler/)
  assert.match(m.refreshReason(space({ status: 'archived' })), /archived/)
  assert.equal(m.refreshReason(space({ manifest: { upkeep: {} } })), '')
})
test('restore confirmation makes retained history and records explicit', () => {
  assert.equal(m.restoreCopy(space(), 5), "Restore revision 5? This brings back the Space's earlier code as a new revision 8. Revisions 6–7 stay in history. Your records, notes and statuses stay as they are now.")
  assert.match(m.errorText({ error: { code: 'incompatible', message: 'Data versions differ' } }), /Incompatible revision.*unchanged/)
})
test('manifest identity falls back without injecting a style or icon', () => {
  assert.equal(m.accentColor('constructor'), '#0053fd')
  assert.equal(m.accentColor('rose'), '#e75e78')
  assert.equal(m.iconName('book'), 'book')
  assert.equal(m.iconName('book" onclick="bad'), 'layers')
})
test('diagnostics bound output and redact common credential values', () => {
  assert.equal(m.diagnosticText('token=demo-secret Bearer demo-value'), 'token=[redacted] Bearer [redacted]')
  assert.equal(m.diagnosticText('x'.repeat(4000)).length, 2000)
})

function fixture(overrides = {}) {
  const requests = [], events = [], writes = []
  let bridge
  const mounted = { destroyed: 0, postEvent: (...args) => events.push(args), destroy() { this.destroyed++ } }
  const rest = async (path, options = {}) => {
    requests.push({ path, ...options })
    if (overrides.rest) { const result = overrides.rest(path, options); if (result !== undefined) return result }
    if (path.endsWith('/sessions')) return { session: 'demo-session', head_rev: 7, grants: ['data'] }
    if (path.endsWith('/bundle')) return { space: space(), rev: 7, manifest: {}, files: [], sandbox }
    if (options.method === 'DELETE') return { closed: true }
    if (path.endsWith('/bridge')) return { ok: true, result: { rev: 1 } }
    throw new Error(`Unexpected request ${path}`)
  }
  const session = createSpaceSession({ rest, sid: 'research-desk', container: {}, mount: (_container, options) => { bridge = options; if (overrides.mount) return overrides.mount(options); return mounted }, onEvent: e => events.push(e), onWrite: e => writes.push(e) })
  return { session, requests, events, writes, mounted, bridge: () => bridge }
}
test('mount opens a session first and binds every bridge call to that session and Space', async () => {
  const f = fixture()
  await f.session.ready
  assert.deepEqual(f.requests.map(r => r.path), ['/spaces/research-desk/sessions', '/spaces/research-desk/bundle'])
  assert.equal(Object.hasOwn(f.bridge(), 'session'), false)
  await f.bridge().call('data.put', { collection: 'notes', data: { note: 'public demo' }, space: 'other' })
  assert.deepEqual(f.requests[2], { path: '/spaces/research-desk/bridge', method: 'POST', body: { session: 'demo-session', op: 'data.put', args: { collection: 'notes', data: { note: 'public demo' }, space: 'other', id: f.requests[2].body.args.id, base_rev: 0 } } })
  assert.deepEqual(f.writes.map(w => w.status), ['saving', 'saved'])
  await f.session.destroy()
})
test('unmount closes once, destroys the frame and prevents calls and events', async () => {
  const f = fixture()
  await f.session.ready
  f.session.postEvent('data.changed', { seq: 1, changes: [] })
  assert.deepEqual(f.events, [['data.changed', { seq: 1, changes: [] }]])
  await f.session.destroy()
  await f.session.destroy()
  const count = f.requests.length
  assert.equal((await f.bridge().call('data.query', {})).error.code, 'session_invalid')
  f.session.postEvent('run.updated', {})
  assert.equal(f.requests.length, count)
  assert.equal(f.requests.filter(r => r.method === 'DELETE').length, 1)
  assert.equal(f.mounted.destroyed, 1)
  assert.equal(f.events.length, 1)
})
test('session opened after navigation is closed without mounting', async () => {
  const opening = deferred()
  const f = fixture({ rest: path => path.endsWith('/sessions') ? opening.promise : undefined })
  await f.session.destroy()
  opening.resolve({ session: 'late-session', head_rev: 7, grants: [] })
  await f.session.ready
  assert.equal(f.bridge(), undefined)
  assert.deepEqual(f.requests.map(r => r.method || 'GET'), ['POST', 'DELETE'])
})
test('bundle returned after navigation cannot mount', async () => {
  const bundle = deferred(), started = deferred()
  const f = fixture({ rest: path => { if (path.endsWith('/bundle')) { started.resolve(); return bundle.promise } } })
  await started.promise
  await f.session.destroy()
  bundle.resolve({ rev: 7 })
  await f.session.ready
  assert.equal(f.bridge(), undefined)
  assert.equal(f.requests.filter(r => r.method === 'DELETE').length, 1)
})
test('revision changed while opening closes the stale session', async () => {
  const f = fixture({ rest: path => path.endsWith('/bundle') ? { rev: 8 } : undefined })
  await assert.rejects(f.session.ready, /changed while opening/)
  assert.equal(f.bridge(), undefined)
  assert.equal(f.requests.at(-1).method, 'DELETE')
})
test('mount failure closes its backend session', async () => {
  const f = fixture({ mount: () => { throw new Error('entry load failed') } })
  await assert.rejects(f.session.ready, /entry load failed/)
  assert.equal(f.requests.at(-1).method, 'DELETE')
})
test('results arriving after session closure are not delivered as saved', async () => {
  const response = deferred()
  const f = fixture({ rest: path => path.endsWith('/bridge') ? response.promise : undefined })
  await f.session.ready
  const pending = f.bridge().call('data.put', { data: { note: 'demo' } })
  await f.session.destroy()
  response.resolve({ ok: true, result: {} })
  assert.equal((await pending).error.code, 'session_invalid')
  assert.deepEqual(f.writes.map(w => w.status), ['saving'])
})
test('a failed write keeps its draft and can explicitly retry', async () => {
  let calls = 0
  const f = fixture({ rest: path => path.endsWith('/bridge') ? (++calls === 1 ? { ok: false, error: { code: 'limit', message: 'Record limit' } } : { ok: true, result: {} }) : undefined })
  await f.session.ready
  await f.bridge().call('data.put', { data: { note: 'public demo draft' } })
  const failure = f.writes.at(-1)
  assert.equal(failure.status, 'failed')
  assert.equal(failure.args.data.note, 'public demo draft')
  await failure.retry()
  assert.equal(f.writes.at(-1).status, 'saved')
  assert.equal(calls, 2)
  await f.session.destroy()
})
test('concurrent writes are not labelled saved while another write is pending', async () => {
  const a = deferred(), b = deferred()
  let calls = 0
  const f = fixture({ rest: path => path.endsWith('/bridge') ? (++calls === 1 ? a.promise : b.promise) : undefined })
  await f.session.ready
  const first = f.bridge().call('data.put', { data: { note: 'first' } })
  const second = f.bridge().call('data.put', { data: { note: 'second' } })
  a.resolve({ ok: true, result: {} })
  await first
  assert.equal(f.writes.at(-1).status, 'saving')
  b.resolve({ ok: true, result: {} })
  await second
  assert.equal(f.writes.at(-1).status, 'saved')
  await f.session.destroy()
})
test('an unrelated successful write does not hide an unresolved conflict', async () => {
  let calls = 0
  const f = fixture({ rest: path => path.endsWith('/bridge') ? (++calls === 1 ? { ok: false, error: { code: 'conflict', current: { rev: 2 } } } : { ok: true, result: {} }) : undefined })
  await f.session.ready
  await f.bridge().call('data.put', { data: { note: 'first' } })
  const conflict = f.writes.at(-1)
  await f.bridge().call('data.put', { data: { note: 'second' } })
  assert.equal(f.writes.at(-1).status, 'conflict')
  await conflict.retry({ data: { note: 'first' }, base_rev: 2 })
  assert.equal(f.requests.at(-1).body.args.base_rev, 2)
  assert.equal(f.writes.at(-1).status, 'saved')
  await f.session.destroy()
})
test('network write errors are not labelled saved and preserve retry', async () => {
  const f = fixture({ rest: path => path.endsWith('/bridge') ? Promise.reject(new Error('offline')) : undefined })
  await f.session.ready
  const reply = await f.bridge().call('data.put', { data: { note: 'demo' } })
  assert.equal(reply.ok, false)
  assert.equal(f.writes.at(-1).status, 'unknown')
  assert.equal(typeof f.writes.at(-1).retry, 'function')
  await f.session.destroy()
})
test('repeated Retry save activation shares one pending request', async () => {
  const response = deferred()
  let calls = 0
  const f = fixture({ rest: path => path.endsWith('/bridge') ? (++calls === 1 ? { ok: false, error: { code: 'unavailable' } } : response.promise) : undefined })
  await f.session.ready
  await f.bridge().call('data.put', { data: { note: 'demo' } })
  const failure = f.writes.at(-1)
  const first = failure.retry()
  const second = failure.retry()
  assert.equal(calls, 2)
  response.resolve({ ok: true, result: {} })
  assert.deepEqual(await first, await second)
  assert.equal(f.writes.at(-1).status, 'saved')
  await f.session.destroy()
})
test('old backend callbacks cannot send requests after a backend switch', async () => {
  let scope = 'backend-a', calls = 0
  const rest = m.scopedRest(async () => { calls++; return { ok: true } }, () => scope, 'backend-a')
  await rest('/spaces')
  scope = 'backend-b'
  await assert.rejects(rest('/spaces/research-desk/grants/refresh', { method: 'POST' }), /backend changed/)
  assert.equal(calls, 1)
})
test('old backend results cannot populate the new backend view', async () => {
  let scope = 'backend-a'
  const result = deferred()
  const rest = m.scopedRest(() => result.promise, () => scope, 'backend-a')
  const pending = rest('/spaces')
  scope = 'backend-b'
  result.resolve({ spaces: [{ id: 'old-space' }] })
  await assert.rejects(pending, /backend changed/)
})

for (const [name, wire] of [['missing', undefined], ['unsupported', { ...sandbox, format: 2 }]]) {
  test(`${name} sandbox wire closes the backend session with an actionable error`, async () => {
    const f = fixture({
      rest: path => path.endsWith('/bundle') ? { space: space(), rev: 7, manifest: {}, files: [], sandbox: wire } : undefined,
      mount: options => mountSpace({}, options)
    })
    await assert.rejects(f.session.ready, /Desktop and backend.*Reinstall Living Spaces/)
    assert.deepEqual(f.requests.at(-1), { path: '/spaces/research-desk/sessions/demo-session', method: 'DELETE', timeoutMs: 5000 })
    await f.session.destroy()
    assert.equal(f.requests.filter(r => r.method === 'DELETE').length, 1)
    assert.equal((await f.bridge().call('data.query', {})).error.code, 'session_invalid')
  })
}
