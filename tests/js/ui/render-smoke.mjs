import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { existsSync, mkdirSync, mkdtempSync, writeFileSync } from 'node:fs'
import { homedir } from 'node:os'
import { resolve, join } from 'node:path'
import { createRequire } from 'node:module'

const root = resolve(import.meta.dirname, '../../..')
const modules = join(homedir(), '.hermes', 'hermes-agent', 'apps', 'desktop', 'node_modules')
const require = createRequire(join(modules, 'react-dom', 'package.json'))
let server
try { server = require('react-dom/server') }
catch { console.log('SKIP: Hermes react-dom/server is not available'); process.exit(0) }
mkdirSync(join(root, '.run'), { recursive: true })
const temp = mkdtempSync(join(root, '.run/ui-render-'))
process.env.HERMES_HOME = temp
process.env.LIVING_SPACES_DB = join(temp, 'spaces.db')
const entry = join(temp, 'entry.jsx')
writeFileSync(entry, [
  `export { default as plugin, renderDirective } from ${JSON.stringify(join(root, 'src/desktop/plugin.src.js'))}`,
  `export { SpacesIndex } from ${JSON.stringify(join(root, 'src/desktop/ui/index.jsx'))}`,
  `export { SpaceView } from ${JSON.stringify(join(root, 'src/desktop/ui/space.jsx'))}`,
  `export { PermissionsSheet } from ${JSON.stringify(join(root, 'src/desktop/ui/permissions.jsx'))}`,
  `export { HistorySheet } from ${JSON.stringify(join(root, 'src/desktop/ui/history.jsx'))}`,
  `export { ScheduleSheet } from ${JSON.stringify(join(root, 'src/desktop/ui/schedule.jsx'))}`,
  `export { styles } from ${JSON.stringify(join(root, 'src/desktop/ui/styles.js'))}`,
  `export { resetQueries, settleQueries } from ${JSON.stringify(join(root, 'tests/js/ui/sdk-stub.js'))}`
].join('\n'))
const out = join(temp, 'render.cjs')
const esbuild = existsSync('/opt/homebrew/bin/esbuild') ? '/opt/homebrew/bin/esbuild' : join(modules, '.bin', 'esbuild')
execFileSync(esbuild, [entry, '--bundle', '--platform=node', '--format=cjs', '--jsx=automatic', `--alias:@hermes/plugin-sdk=${join(root, 'tests/js/ui/sdk-stub.js')}`, `--alias:react=${join(modules, 'react')}`, `--external:${join(modules, 'react')}/*`, `--external:${join(modules, 'react')}`, `--outfile=${out}`], { stdio: 'pipe' })
const ui = require(out)
const React = require('react')
const render = (component, props) => server.renderToStaticMarkup(React.createElement(component, props))
let assertions = 0
function check(condition, message) { assert.ok(condition, message); assertions++ }
const calls = []
const base = { id: 'research-desk', name: 'Research Desk', owner: 'Atlas', description: 'A public research reading system', status: 'active', head_rev: 7, accent: 'blue', icon: 'book', pinned: true, updated_at: 1794343200, freshness: { last_success_at: 1794343200, last_attempt_at: 1794343500, last_attempt_status: 'succeeded', source_as_of: 1794342900, next_run_at: 1794346800 }, manifest: { upkeep: { handler: 'feed' } }, grants: [{ capability: 'data', status: 'granted', scope: {} }, { capability: 'logs', status: 'granted', scope: {} }, { capability: 'refresh', status: 'requested', scope: { hosts: ['public.example'] }, purpose: 'Read public papers' }], schedule: { status: 'requested', cadence: '0 7 * * *', timezone: 'America/Chicago', purpose: 'Keep public papers current' }, recent_runs: [{ id: 'demo-run', status: 'succeeded', trigger: 'manual', queued_at: 1794343199, started_at: 1794343200, ended_at: 1794343201, changed: { unchanged: 3 } }] }
function context(space = base, spaces = [space]) {
  return { listActions: () => [{ id: 'session.new', label: 'New chat' }], runAction: () => ({ ok: true }), rest: async (path, options) => {
    calls.push([path, options])
    if (path === '/spaces') return { spaces, seq_global: 5 }
    if (path === '/spaces/research-desk') return space
    if (path.endsWith('/grants')) return { grants: space.grants, future: [], audit: [{ id: 1, at: 1794343200, actor: 'user', action: 'grant', capability: 'data', outcome: 'granted' }] }
    if (path.endsWith('/schedule')) return space.schedule
    if (path.endsWith('/runs')) return space.recent_runs
    if (path.endsWith('/revisions')) return [{ rev: 7, created_at: 1794343200, author: 'agent:Atlas', summary: 'Current app' }, { rev: 5, created_at: 1794340000, author: 'agent:Atlas', summary: 'Earlier app' }]
    throw new Error(`Unexpected REST call ${path}`)
  } }
}
async function ready(component, props) { ui.resetQueries(); render(component, props); await ui.settleQueries(); return render(component, props) }
function save(name, markup) { writeFileSync(join(temp, `${name}.html`), `<!doctype html><html><head><meta charset="utf-8"><style>:root{--ui-text-primary:#f2f2f4;--ui-text-secondary:#b4b4bb;--ui-bg-primary:#0d0d0e;--ui-bg-secondary:#161618;--ui-bg-card:#161618;--ui-bg-quaternary:#252528;--ui-stroke-secondary:#44444b;--ui-accent:#0053fd;--destructive:#e75e78}body{background:var(--ui-bg-primary);color:var(--ui-text-primary);margin:0}button{font:inherit;color:inherit;background:var(--ui-bg-quaternary);border:1px solid var(--ui-stroke-secondary)}${ui.styles}</style></head><body><div class="ls-root">${markup}</div></body></html>`) }
const index = await ready(ui.SpacesIndex, { ctx: context() })
check(index.includes('data-testid="spaces-index"'), 'index rendered')
check(index.includes('Search Spaces or owner'), 'search label')
check(index.includes('1 active · 0 need attention'), 'summary counts')
check(index.includes('aria-label="Research Desk, Ready, owner Atlas.'), 'whole-card accessible label')
check(index.includes('href="#/spaces?space=research-desk"'), 'card route')
check(index.includes('Last attempt') && index.includes('Source data from'), 'separate freshness facts')
save('index', index)
const empty = await ready(ui.SpacesIndex, { ctx: context(base, []) })
check(empty.includes('Build your first Space in chat'), 'first-use title')
check(empty.includes('Keep my notes and reading status.'), 'copyable example prompt')
check(empty.includes('Start a new chat'), 'new-chat action')
save('empty', empty)
const active = { ...base, grants: base.grants.map(g => ({ ...g, status: 'granted' })) }
const view = await ready(ui.SpaceView, { ctx: context(active), sid: base.id })
check(view.includes('aria-label="Space content"'), 'labelled sandbox')
check(view.includes('data-testid="space-host"'), 'mount region')
check(view.includes('Refresh now') && view.includes('Permissions'), 'primary actions')
check(!view.includes('Saved '), 'no saved claim without a write')
check(view.includes('Last successful update') && view.includes('source data from'), 'frame freshness')
save('space', view)
const permissions = await ready(ui.PermissionsSheet, { ctx: context(), space: base, onClose() {}, onChanged() {} })
check(permissions.indexOf('Before you approve anything') < permissions.indexOf('Granted to Research Desk'), 'WebRTC note before grants')
check(permissions.indexOf('Spaces block ordinary internet connections') < permissions.indexOf('ls-sheet-scroll'), 'WebRTC note is outside the scrolling body')
check(permissions.includes('Spaces block ordinary internet connections unless you approve a site or capability. This is not a complete block: a browser feature called WebRTC can still send data that this Space can read. It does not give the Space access to Hermes, credentials, your unapproved files or other Spaces. Only put data in a Space that you trust it to handle.'), 'complete exact disclosure')
const future = permissions.split('data-testid="release-two"')[1].split('</section>')[0]
check(!/<button|<input|role="switch"/.test(future), 'release-two rows have no controls')
check((future.match(/Not available yet/g) || []).length === 8, 'all future rows labelled')
check(permissions.includes('No model calls') && permissions.includes('America/Chicago'), 'pending schedule scope and cost')
check(permissions.includes("Missed intervals aren&#x27;t replayed."), 'catch-up policy')
check(!permissions.includes('Approve narrower'), 'no invented narrower scopes')
save('permissions', permissions)
for (const [name, patch, expected] of [
  ['building', { status: 'building', head_rev: 0 }, 'Atlas is building the first version'],
  ['failed', { attention: { kind: 'failed', message: 'Source timed out' }, freshness: { ...base.freshness, last_attempt_status: 'failed' } }, 'ls-stale'],
  ['blocked', { attention: { kind: 'blocked', message: 'Refresh was revoked in Permissions' }, freshness: { ...base.freshness, last_attempt_status: 'blocked' } }, 'Refresh is blocked'],
  ['crashed', { attention: { kind: 'crashed', message: 'Demo entry load failed' } }, 'Research Desk stopped working'],
  ['archived', { status: 'archived' }, 'This Space is archived. Refreshes and schedules are off.']
]) {
  const html = await ready(ui.SpaceView, { ctx: context({ ...active, ...patch }), sid: base.id })
  check(html.includes(expected), `${name} state rendered`)
  if (name === 'blocked' || name === 'archived') check(html.includes('aria-disabled="true"'), `${name} refresh disabled with reason`)
  if (name === 'building') check(!html.includes('Refresh now') && !html.includes('>Permissions<'), 'building exposes only History')
  save(name, html)
}
const history = await ready(ui.HistorySheet, { ctx: context(), space: base, onClose() {}, onChanged() {} })
check(history.includes('no change · 3 unchanged') && history.includes('Succeeded'), 'no-change history success')
save('history', history)
const revisions = await ready(ui.HistorySheet, { ctx: context(), space: base, initialTab: 'revisions', onClose() {}, onChanged() {} })
check(revisions.includes('Restoring code does not rewind records.'), 'restoration note')
check(revisions.includes('Current') && revisions.includes('Restore…'), 'revision controls')
save('revisions', revisions)
const schedule = await ready(ui.ScheduleSheet, { ctx: context(), space: base, onClose() {}, onChanged() {} })
check(schedule.includes('No model calls.') && schedule.includes('Change schedule in chat'), 'schedule controls and cost')
save('schedule', schedule)
check(ui.renderDirective(context(), { id: '../invalid' }) === null, 'invalid directive renders nothing')
ui.resetQueries()
render(() => ui.renderDirective(context(), { id: base.id }), {})
await ui.settleQueries()
const directive = render(() => ui.renderDirective(context(), { id: base.id }), {})
check(directive.includes('Open Space') && directive.includes('Revision 7') && directive.includes('Atlas'), 'Open Space directive metadata')
ui.resetQueries()
render(ui.SpacesIndex, { ctx: { ...context(), queryScope: 'backend-a' } })
await ui.settleQueries()
render(ui.SpacesIndex, { ctx: { ...context({ ...base, name: 'Other Public Desk', owner: 'Kit' }), queryScope: 'backend-b' } })
await ui.settleQueries()
const switched = render(ui.SpacesIndex, { ctx: { ...context({ ...base, name: 'Other Public Desk', owner: 'Kit' }), queryScope: 'backend-b' } })
check(switched.includes('Other Public Desk'), 'new backend data renders with colliding Space ID')
check(!switched.includes('Research Desk'), 'old backend cache is not reused')
const registrations = []
ui.plugin.register({ registerMany: rows => registrations.push(...rows) })
check(registrations.length === 3 && registrations[2].data.name === 'living-space', 'route, sidebar and directive registered')
check(calls.some(([path]) => path === '/spaces/research-desk'), 'Space render uses fake ctx.rest')
console.log(`PASS: ${assertions} render assertions; 12 HTML fixtures in ${temp}`)
