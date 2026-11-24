import { answerSummary } from './markdown.mjs'
export const SPACE_ID = /^[a-z0-9][a-z0-9-]{1,47}$/
export const isSpaceId = value => typeof value === 'string' && SPACE_ID.test(value)
export const spacePath = sid => `/spaces/${encodeURIComponent(sid)}`
export const spaceRoute = sid => `/spaces?space=${encodeURIComponent(sid)}`
export function routeSpace(hash) {
  const id = new URLSearchParams((hash || '').split('?')[1] || '').get('space')
  return isSpaceId(id) ? id : null
}

export const ACCENTS = { blue: '#0053fd', green: '#55a583', amber: '#e0a06c', purple: '#9e94d5', teal: '#4c9fb0', rose: '#e75e78', orange: '#e08a64', grey: '#8a8a93' }
export const accentColor = accent => Object.hasOwn(ACCENTS, accent) ? ACCENTS[accent] : ACCENTS.blue
export const PILLS = {
  ready: { label: 'Available', icon: 'check', border: 'solid' },
  building: { label: 'Building', icon: 'tools', border: 'dashed' },
  updating: { label: 'Updating', icon: 'refresh', border: 'solid' },
  failed: { label: 'Failed', icon: 'error', border: 'solid' },
  blocked: { label: 'Blocked', icon: 'circle-slash', border: 'solid' },
  archived: { label: 'Archived', icon: 'archive', border: 'dotted' },
  crashed: { label: 'Crashed', icon: 'error', border: 'solid' },
  paused: { label: 'Paused', icon: 'debug-pause', border: 'solid' },
  granted: { label: 'Allowed', icon: 'check', border: 'solid' },
  requested: { label: 'Needs your decision', icon: 'warning', border: 'dashed' },
  denied: { label: 'Denied', icon: 'circle-slash', border: 'solid' },
  revoked: { label: 'Revoked', icon: 'circle-slash', border: 'solid' },
  succeeded: { label: 'Succeeded', icon: 'check', border: 'solid' },
  queued: { label: 'Queued', icon: 'watch', border: 'solid' },
  running: { label: 'Running', icon: 'refresh', border: 'solid' },
  canceled: { label: 'Canceled', icon: 'circle-slash', border: 'solid' }
}
export const inFlight = status => status === 'queued' || status === 'running'
export function spaceStatus(space, frame = false) {
  if (space.status === 'archived') return 'archived'
  if (space.status === 'building' || !space.head_rev) return 'building'
  if (space.attention?.kind === 'crashed') return frame ? 'crashed' : 'failed'
  if (inFlight(space.freshness?.last_attempt_status)) return 'updating'
  if (space.attention?.kind) return space.attention.kind
  if (['failed', 'blocked'].includes(space.freshness?.last_attempt_status)) return space.freshness.last_attempt_status
  return 'ready'
}
export function statusDimensions(space, { guest = 'unknown', write = null, hostError = false } = {}) {
  const host = hostError ? 'unavailable' : space.status === 'archived' ? 'archived' : space.status === 'building' || !space.head_rev ? 'building' : 'available'
  return { host, guest, save: write?.status || 'idle', freshness: space.freshness }
}
const BOT_RETRY = ['unknown', 'failed', 'offline']
const BOT_SETTLED = ['completed', 'failed', 'offline', 'unknown']
export const botDismissKey = action => action?.activationId ? `${action.activationId}:${action.status}` : null
// A dismissal is { id, statuses }: one activation and every status the user dismissed it in.
// Anything else, including the earlier 'id:status' string form, is no dismissal.
export function parseBotDismissal(value) {
  let record
  try { record = JSON.parse(value) } catch { return null }
  if (typeof record?.id !== 'string' || !Array.isArray(record.statuses) || !record.statuses.every(status => typeof status === 'string')) return null
  return { id: record.id, statuses: record.statuses }
}
// A dismissed activation stays hidden at the statuses it was dismissed in, and through offline/unknown,
// which only mean the outcome could not be observed (restore() reports them when a route is down).
// A different observed outcome is new information, and a status the user just caused always shows.
export function botDismissed(action, record) {
  if (!action?.activationId || action.userInitiated === true || record?.id !== action.activationId) return false
  return record.statuses.includes(action.status) || ['offline', 'unknown'].includes(action.status)
}
export function dismissBot(record, action) {
  const statuses = record?.id === action.activationId ? record.statuses : []
  return { id: action.activationId, statuses: [...new Set([...statuses, action.status])] }
}
const botKind = status => status === 'completed' ? 'reply' : BOT_RETRY.includes(status) ? 'failed' : 'progress'
// The host notice for one bot status. Failed kinds carry a one-line reason and never collapse;
// a reply carries the answer, collapsed to its first sentence until the user reads it.
// A failed request is titled by what is known about delivery, never by a raw status word. Only an unbound
// Space is known not to have received it: an offline or unknown status can follow a request that did arrive.
function failureCopy(action, who) {
  if (action.reason === 'unbound') return { label: `${who} didn't receive the request`, reason: `No chat is keeping this Space. Ask ${who} in chat to bind it.` }
  const label = { offline: `Couldn't reach ${who}`, unknown: `Not sure ${who} received the request` }[action.status] || `The request to ${who} failed`
  return { label, reason: action.message || null }
}
export function botBanner(action, { dismissed = false, expanded = false, owner = null } = {}) {
  if (!action || dismissed) return null
  const kind = botKind(action.status)
  const answer = kind === 'reply' && typeof action.answer === 'string' && action.answer.trim() ? action.answer : null
  const failure = kind === 'failed' ? failureCopy(action, typeof owner === 'string' && owner.trim() ? owner.trim() : 'Hermes') : null
  return {
    status: action.status,
    kind,
    label: kind === 'reply' ? 'Hermes replied' : failure ? failure.label : `Bot request: ${action.status}`,
    reason: answer ? null : failure ? failure.reason : action.message || null,
    detail: failure && typeof action.detail === 'string' && action.detail ? action.detail : null,
    summary: answer ? answerSummary(answer) : '',
    answer,
    at: Number.isFinite(action.at) ? action.at : null,
    expanded: !!answer && expanded,
    collapsible: !!answer,
    canRetry: !!action.activationId && kind === 'failed',
    canDismiss: BOT_SETTLED.includes(action.status)
  }
}
const STORAGE_SUBJECT = { source_bytes: 'source data', source_metadata_bytes: 'source metadata', data_bytes: 'records', records: 'records', project_bytes: 'project files', project_files: 'project files', file_bytes: 'the largest file' }
const trimmed = value => Number.isInteger(value) ? String(value) : value.toFixed(1).replace(/\.0$/, '')
export function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${trimmed(bytes / 1024)} KB`
  return `${trimmed(bytes / 1024 / 1024)} MB`
}
// The storage warning for the most-full resource the user has not hidden at its current percentage,
// in words: never the raw resource key or byte counts. `hidden` is a stored `key`: hiding a notice hides
// every current warning at its current percentage, so a new or changed resource still shows.
export function storageNotice(storage, hidden = null) {
  const percent = row => Math.round(row.used / row.limit * 100)
  const rows = (storage?.warnings || []).filter(row => Number.isFinite(row?.used) && Number.isFinite(row?.limit) && row.limit > 0)
    .map(row => ({ row, id: `${row.resource}:${percent(row)}` }))
  const skip = new Set(String(hidden ?? '').split(','))
  const shown = rows.filter(({ id }) => !skip.has(id)).map(({ row }) => row)
  if (!shown.length) return null
  const row = shown.reduce((top, next) => next.used / next.limit > top.used / top.limit ? next : top)
  const pct = percent(row)
  const key = rows.map(({ id }) => id).sort().join(',')
  const bytes = /_bytes$/.test(row.resource)
  const amount = value => bytes ? formatBytes(value) : value.toLocaleString('en-US')
  const subject = STORAGE_SUBJECT[row.resource] || String(row.resource).replace(/_bytes$/, '').replace(/_/g, ' ')
  return { pct, key, title: `Storage ${pct}% full`, line: `${amount(row.used)} of ${amount(row.limit)} used by ${subject}. Writes stop at the limit.` }
}
export const GUEST_WORDS = { unknown: 'Not reported', starting: 'Starting', loaded: 'Loaded', failed: 'Failed', faulted: 'Faulted (uncaught error, still running)' }
export const guestWord = state => GUEST_WORDS[state] || String(state)
export function needsAttention(space) {
  return space.status !== 'archived' && ['failed', 'blocked', 'crashed'].includes(spaceStatus(space, true))
}
export function summaryCounts(spaces) {
  return { active: spaces.filter(s => s.status !== 'archived').length, attention: spaces.filter(needsAttention).length }
}
export function visibleSpaces(spaces, search, filter) {
  const q = search.trim().toLocaleLowerCase()
  return spaces.filter(s => filter === 'archived' ? s.status === 'archived' : s.status !== 'archived' && (filter !== 'attention' || needsAttention(s)) && (filter !== 'pinned' || s.pinned))
    .filter(s => `${s.name} ${s.owner}`.toLocaleLowerCase().includes(q))
    .sort((a, b) => Number(Boolean(b.pinned)) - Number(Boolean(a.pinned)) || (b.last_opened_at ?? 0) - (a.last_opened_at ?? 0) || b.updated_at - a.updated_at || a.id.localeCompare(b.id))
}
export function headerFacts(space) {
  const f = space.freshness || {}
  if (space.status === 'archived') return [{ key: 'archive', label: 'Archived', at: space.archived_at ?? space.updated_at }]
  if (space.status === 'building' || !space.head_rev) return [{ key: 'building', label: 'Building the first version' }]
  if (f.last_success_at == null) return [{ key: 'success', label: ['failed', 'blocked'].includes(f.last_attempt_status) ? 'No successful update yet' : 'Not refreshed yet' }]
  const facts = [{ key: 'success', label: 'Updated', at: f.last_success_at }]
  if (f.source_as_of != null && Math.abs(f.source_as_of - f.last_success_at) >= 60) facts.push({ key: 'source', label: 'Source data from', at: f.source_as_of })
  return facts
}
// Who an actor string names, in words. Actors are stored as user, app, agent:<name> or upkeep:<name|schedule>.
// An upkeep actor names its source by id. Show the name a person knows it by when the Space reports one; a
// Space's own sync job (named by the Space id) has no other name, so it is not repeated back as a slug.
function sourceName(space, id) {
  if (id === space.id) return ''
  const source = (space.freshness?.sources || []).find(item => item?.id === id)
  return source?.name || source?.label || sourceHost(source?.url) || id
}
function actorWords(actor, space = {}) {
  const [kind, ...rest] = String(actor || '').split(':')
  const name = kind === 'upkeep' && rest.join(':').trim() !== 'schedule' ? sourceName(space, rest.join(':').trim()) : rest.join(':').trim()
  if (kind === 'user') return { verb: 'Edited by you' }
  if (kind === 'app') return { verb: 'Edited in this Space' }
  if (kind === 'agent') return { verb: name ? `Edited in chat by ${name}` : 'Edited in chat' }
  if (kind === 'upkeep') return { verb: rest.join(':').trim() === 'schedule' || !rest.join(':').trim() ? 'Refreshed on schedule' : name ? `Synced by ${name}` : 'Synced' }
  return null
}
const sourceHost = url => { try { return new URL(url).hostname.replace(/^www\./, '') } catch { return '' } }
// The one freshness phrase the Space header shows, worded by what last changed the Space. It never names a
// source or time the backend did not report; the full set of freshness facts lives in Details.
export function freshnessPhrase(space) {
  const f = space.freshness || {}
  const state = spaceStatus(space, true)
  if (state === 'archived') return { key: 'archive', label: 'Archived', at: space.archived_at ?? space.updated_at }
  if (state === 'building') return { key: 'building', label: 'Building the first version' }
  if (state === 'updating') return { key: 'updating', label: 'Refreshing now…' }
  // A failed or blocked refresh still says how old the data on screen is: the last good update, when there is one.
  if (state === 'failed' || state === 'blocked') {
    const verb = state === 'failed' ? 'Refresh failed' : 'Refresh blocked'
    return f.last_success_at != null ? { key: state, label: `${verb} · data from`, at: f.last_success_at } : { key: state, label: `${verb} · no successful update yet` }
  }
  const activity = space.activity
  const words = activity && Number.isFinite(activity.at) ? actorWords(activity.actor, space) : null
  const host = (f.sources || []).map(source => sourceHost(source?.url)).find(Boolean)
  const refreshed = f.last_success_at != null ? { key: 'success', label: host ? `Refreshed from ${host}` : 'Updated', at: f.last_success_at } : null
  // A refresh that wrote records also records an upkeep or agent change at about the same moment: prefer the refresh wording.
  if (words && (!refreshed || activity.at > refreshed.at + 60)) {
    const verb = activity.kind === 'code' && activity.actor?.startsWith('agent:') ? words.verb.replace('Edited in chat', 'Changed in chat') : words.verb
    return { key: 'activity', label: verb, at: activity.at }
  }
  if (refreshed) return refreshed
  return { key: 'success', label: f.last_attempt_status === 'failed' || f.last_attempt_status === 'blocked' ? 'No successful update yet' : 'Not refreshed yet' }
}
// Which notice kinds are failures: they are announced as alerts and drawn in the danger tone.
export const ALERT_KINDS = ['failed', 'blocked', 'crashed', 'conflict']
export function freshnessFacts(space, format) {
  const f = space.freshness || {}
  return [
    { key: 'success', label: 'Last successful update', at: f.last_success_at },
    { key: 'attempt', label: 'Last attempt', at: f.last_attempt_at },
    { key: 'source', label: 'Source data from', at: f.source_as_of },
    { key: 'next', label: 'Next refresh', at: f.next_run_at }
  ].filter(fact => fact.at != null).map(fact => ({ ...fact, value: `${format(fact.at)}${fact.key === 'attempt' && f.last_attempt_status ? ` · ${f.last_attempt_status}` : ''}` }))
}
export function cardLines(space, format) {
  const f = space.freshness || {}
  const at = value => value == null ? '' : ` ${format(value)}`
  const state = spaceStatus(space)
  if (state === 'building') return [`${space.owner} is building the first version`, space.created_at != null ? `Started${at(space.created_at)}` : '']
  if (state === 'archived') return [`Archived${at(space.archived_at ?? space.updated_at)}`, 'Future upkeep paused']
  if (space.attention?.kind === 'crashed') return [`Stopped working${at(f.last_attempt_at)}`, space.attention.message || '']
  if (state === 'updating') return ['Refreshing now…', f.last_success_at != null ? `Last good update${at(f.last_success_at)}` : '']
  if (state === 'failed') return [`Refresh failed${at(f.last_attempt_at)}`, f.last_success_at != null ? `Showing last good data from${at(f.last_success_at)}` : 'No successful update yet']
  if (state === 'blocked') return [`Refresh blocked${at(f.last_attempt_at)}`, space.attention?.message || 'Review the last run for details']
  return [f.last_success_at == null ? 'Not refreshed yet' : `Updated${at(f.last_success_at)}`, space.upkeep?.enabled === false ? 'Upkeep paused' : f.next_run_at != null ? `Next refresh${at(f.next_run_at)}` : '']
}
export function advanceCursor(cursor, page) {
  const changes = (page?.changes || []).filter(c => Number.isSafeInteger(c.seq) && c.seq > cursor).sort((a, b) => a.seq - b.seq)
  // The API's seq is the latest cursor, including rows beyond a limited page.
  const seq = changes.length ? changes.at(-1).seq : cursor
  return { seq, changes }
}
export function refreshReason(space) {
  if (space.status === 'archived') return 'This Space is archived. Restore it to refresh.'
  if (!space.manifest?.upkeep) return 'No refresh handler is declared. Ask the owner in chat to add one.'
  if (spaceStatus(space) === 'blocked') return space.attention?.message || 'Refresh is blocked. Review Permissions.'
  return ''
}
// The Refresh line in Details. A Space with no refresh handler is not broken, so the absence is never worded as a
// fault. The backend records only the latest change, not who will keep the Space current, so this states the
// absence neutrally and names no ongoing updater.
export function refreshFact(space) {
  const reason = refreshReason(space)
  if (space.manifest?.upkeep || space.status === 'archived') return reason || 'Use Refresh now in the top bar.'
  return 'This Space has no refresh of its own. It changes when you, chat or a connected source update it.'
}
export function runResult(run) {
  if (run.status === 'failed') return run.error || 'Refresh failed'
  if (run.status === 'blocked') return `Blocked: ${run.detail?.reason || 'Review Permissions'}`
  if (run.status === 'canceled') return 'Refresh canceled'
  if (inFlight(run.status)) return run.status === 'queued' ? 'Waiting to start' : 'Refreshing now…'
  const c = run.changed || {}
  return (c.added || c.updated || c.removed) ? `${c.added || 0} added · ${c.updated || 0} updated · ${c.unchanged || 0} unchanged` : `no change · ${c.unchanged || 0} unchanged`
}
export function dispatchText(dispatch, format) {
  if (!dispatch) return ''
  const at = value => value == null ? '' : format(typeof value === 'number' ? value : Date.parse(value) / 1000)
  const catchUp = dispatch.kind === 'catch_up'
  const delay = ['late', 'catch_up'].includes(dispatch.kind) && dispatch.lateness_seconds != null ? ` Delayed by ${dispatch.lateness_seconds} s.` : ''
  const scheduled = at(dispatch.scheduled_at)
  const actual = at(dispatch.dispatched_at)
  return `${catchUp ? 'Catch-up refresh. ' : ''}${scheduled ? `${catchUp ? 'Missed scheduled time' : 'Scheduled time'} ${scheduled}. ` : ''}${actual ? `Actual dispatch ${actual}.` : ''}${delay}${catchUp ? ' Missed intervals were not replayed.' : ''}`.trim()
}
export const CATCH_UP = 'Missed runs follow native Hermes cron policy. Current catch-up settings are unavailable here.'
export const EXECUTION_LABELS = { succeeded: 'Succeeded', failed: 'Failed', running: 'Running', claimed: 'Claimed', queued: 'Queued', unknown: 'Outcome unknown, side effects may have run' }
export const executionLabel = status => EXECUTION_LABELS[status] || String(status ?? '')
export const toSeconds = value => value == null ? null : typeof value === 'number' ? value : Number.isFinite(Date.parse(value)) ? Date.parse(value) / 1000 : null
export const PROMPTS = [
  'Build Research Desk: an overview, a searchable library and a reading queue. Keep my notes and reading status.',
  'Build a weekly fitness planner with a progress chart. Refresh it every Monday.'
]
function dataVersionCompatibility(current, target) {
  if (!Number.isInteger(current) || current <= 0 || !Number.isInteger(target) || target <= 0) return 'unknown'
  return current === target ? 'compatible' : 'incompatible'
}
export function revisionCompatibility(space, revision) {
  return dataVersionCompatibility(space.data_version, revision?.manifest?.data?.version)
}
export function recoveryCompatibility(space, point) {
  return dataVersionCompatibility(space.data_version, point.data_version)
}
export function restoreCopy(space, rev) {
  const kept = space.head_rev > rev + 1 ? `Revisions ${rev + 1}–${space.head_rev} stay in history.` : `Revision ${space.head_rev} stays in history.`
  return `Restore revision ${rev}? This brings back the Space's earlier code as a new revision ${space.head_rev + 1}. ${kept} Your records, notes and statuses stay as they are now. Migration undo and data downgrades are not supported.`
}
// The backend's error object for a failure. The desktop IPC wraps a REST error as
// "Error invoking remote method 'hermes:api': Error: 423: {json}", so the object is parsed back out of the message.
function backendError(error) {
  let detail = error?.error || error?.body?.error || error
  if (!detail?.code && typeof detail?.message === 'string') {
    const json = detail.message.indexOf('{')
    if (json >= 0) {
      try { detail = JSON.parse(detail.message.slice(json)).error || detail } catch {}
    }
  }
  return detail
}
const IPC_WRAPPER = /^Error invoking remote method '[^']*': (?:Error: )?/
const DIAGNOSTIC_FIELDS = ['code', 'reason', 'message']
// Only a structured error's code, reason and message reach diagnostics: any other field may hold a credential.
function diagnosticFields(value) {
  return Object.fromEntries(Object.entries(value ?? {}).filter(([key, field]) => DIAGNOSTIC_FIELDS.includes(key) && ['string', 'number'].includes(typeof field)))
}
// The text behind Copy details. A wrapped JSON error envelope is rebuilt from its allowed fields, keeping the wrapper.
function diagnosticSource(error, detail) {
  const text = typeof error === 'string' ? error : error?.message
  if (typeof text !== 'string' || !text) return JSON.stringify(diagnosticFields(detail))
  const json = text.indexOf('{')
  if (json < 0) return text
  try {
    const body = JSON.parse(text.slice(json))
    // Only the backend's error envelope is rebuilt; any other JSON is free text and masked as such.
    return body?.error && typeof body.error === 'object' ? text.slice(0, json) + JSON.stringify({ error: diagnosticFields(body.error) }) : text
  } catch { return text }
}
// A failure in words for the user, plus the raw text for diagnostics. Never the IPC wrapper in the words.
export function failureParts(error) {
  const detail = backendError(error)
  const raw = diagnosticText(diagnosticSource(error, detail))
  // Strip the wrapper from whichever text wins: a plain or non-JSON failure carries it in its own message.
  const words = (typeof detail?.message === 'string' && detail.message.trim() ? detail.message.trim() : raw).replace(IPC_WRAPPER, '')
  return { message: diagnosticText(words), code: detail?.code ?? null, reason: detail?.reason ?? null, raw }
}
export function errorText(error) {
  const detail = backendError(error)
  const message = detail?.message || String(error)
  if (detail?.code === 'incompatible' || /incompatible/.test(message)) {
    const versions = detail.from_version != null && detail.to_version != null ? ` Current data version ${detail.from_version}; target data version ${detail.to_version}.` : ''
    return `Incompatible revision: ${message}.${versions} Your current code and records are unchanged.`
  }
  if (detail?.code === 'limit') return `limit: ${message}${detail.limit != null ? ` · limit ${detail.limit}` : ''}${detail.actual != null ? ` · actual ${detail.actual}` : ''}`
  return message
}
// Free text cannot say where a credential ends: commas, quotes, escapes and newlines can all sit inside one.
// So everything after the first credential key or Bearer is redacted. JSON \u escapes are decoded first so a key cannot hide.
const SECRET = /(?:api[_-]?key|token|passw(?:or)?d|secret|authorization|cookie)\\?["']?\s*[:=]\s*|\bBearer\s+/i
export function diagnosticText(value) {
  const text = String(value).replace(/\\u([0-9a-f]{4})/gi, (_, hex) => String.fromCharCode(parseInt(hex, 16))).slice(0, 2000)
  const secret = SECRET.exec(text)
  return secret ? `${text.slice(0, secret.index + secret[0].length)}[redacted]` : text
}
export function scopedRest(rest, currentScope, expected) {
  const requireScope = () => {
    if (currentScope() !== expected) throw new Error('The active Hermes backend changed. Reopen this Space.')
  }
  return async (path, options) => {
    requireScope()
    const result = await rest(path, options)
    requireScope()
    return result
  }
}
