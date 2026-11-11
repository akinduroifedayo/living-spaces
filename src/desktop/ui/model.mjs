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
export const iconName = icon => typeof icon === 'string' && /^[a-z][a-z0-9-]{0,63}$/.test(icon) ? icon : 'layers'
export const PILLS = {
  ready: { label: 'Ready', icon: 'check', border: 'solid' },
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
export function needsAttention(space) {
  return space.status !== 'archived' && ['failed', 'blocked', 'crashed'].includes(spaceStatus(space, true))
}
export function summaryCounts(spaces) {
  return { active: spaces.filter(s => s.status !== 'archived').length, attention: spaces.filter(needsAttention).length }
}
export function visibleSpaces(spaces, search, filter) {
  const q = search.trim().toLocaleLowerCase()
  return spaces.filter(s => filter === 'archived' ? s.status === 'archived' : s.status !== 'archived' && (filter !== 'attention' || needsAttention(s)))
    .filter(s => `${s.name} ${s.owner}`.toLocaleLowerCase().includes(q))
    .sort((a, b) => Number(Boolean(b.pinned)) - Number(Boolean(a.pinned)) || (b.last_opened_at ?? 0) - (a.last_opened_at ?? 0) || b.updated_at - a.updated_at || a.id.localeCompare(b.id))
}
export function freshnessFacts(space, format) {
  const f = space.freshness || {}
  const at = value => value == null ? 'Never' : format(value)
  return [
    { key: 'success', label: 'Last successful update', value: at(f.last_success_at), at: f.last_success_at },
    { key: 'attempt', label: 'Last attempt', value: f.last_attempt_at == null ? 'Never' : `${format(f.last_attempt_at)} · ${f.last_attempt_status || 'Unknown'}`, at: f.last_attempt_at },
    { key: 'source', label: 'Source data from', value: f.source_as_of == null ? 'Not reported' : format(f.source_as_of), at: f.source_as_of },
    { key: 'next', label: 'Next refresh', value: f.next_run_at == null ? 'Not scheduled' : format(f.next_run_at), at: f.next_run_at }
  ]
}
export function cardLines(space, format) {
  const f = space.freshness || {}
  const at = value => value == null ? 'not yet available' : format(value)
  const state = spaceStatus(space)
  if (state === 'building') return [`${space.owner} is building the first version`, `Started ${at(space.created_at ?? space.updated_at)}`]
  if (state === 'archived') return [`Archived ${at(space.archived_at ?? space.updated_at)}`, 'Schedules stopped']
  if (space.attention?.kind === 'crashed') return [`Stopped working ${at(f.last_attempt_at)}`, space.attention.message]
  if (state === 'updating') return ['Refreshing now…', `Last good update ${at(f.last_success_at)}`]
  if (state === 'failed') return [`Refresh failed ${at(f.last_attempt_at)}`, `Showing last good data from ${at(f.last_success_at)}`]
  if (state === 'blocked') return [`Refresh blocked ${at(f.last_attempt_at)}`, space.attention?.message || 'Refresh needs your approval in Permissions']
  return [f.last_success_at == null ? 'No successful update yet' : `Updated ${at(f.last_success_at)}`, space.schedule?.status === 'paused' ? 'Upkeep paused' : `Next refresh ${f.next_run_at == null ? 'not scheduled' : format(f.next_run_at)}`]
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
  if (!space.grants?.some(g => g.capability === 'refresh' && g.status === 'granted')) return 'Refresh needs your approval in Permissions'
  if (spaceStatus(space) === 'blocked') return space.attention?.message || 'Refresh is blocked. Review Permissions.'
  return ''
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
  const at = value => value == null ? 'Not reported' : format(typeof value === 'number' ? value : Date.parse(value) / 1000)
  const catchUp = dispatch.kind === 'catch_up'
  const delay = ['late', 'catch_up'].includes(dispatch.kind) && dispatch.lateness_seconds != null ? ` Delayed by ${dispatch.lateness_seconds} s.` : ''
  return `${catchUp ? 'Catch-up refresh. Missed scheduled time' : 'Scheduled time'} ${at(dispatch.scheduled_at)}. Actual dispatch ${at(dispatch.dispatched_at)}.${delay}${catchUp ? ' Missed intervals were not replayed.' : ''}`
}
export const CATCH_UP = "Runs one current refresh when Hermes wakes. Missed intervals aren't replayed."
export const PROMPTS = [
  'Build Research Desk: an overview, a searchable library and a reading queue. Keep my notes and reading status.',
  'Build a weekly fitness planner with a progress chart. Refresh it every Monday.'
]
export function restoreCopy(space, rev) {
  const kept = space.head_rev > rev + 1 ? `Revisions ${rev + 1}–${space.head_rev} stay in history.` : `Revision ${space.head_rev} stays in history.`
  return `Restore revision ${rev}? This brings back the Space's earlier code as a new revision ${space.head_rev + 1}. ${kept} Your records, notes and statuses stay as they are now.`
}
export function errorText(error) {
  let detail = error?.error || error?.body?.error || error
  if (!detail?.code && typeof detail?.message === 'string') {
    const json = detail.message.indexOf('{')
    if (json >= 0) {
      try { detail = JSON.parse(detail.message.slice(json)).error || detail } catch {}
    }
  }
  const message = detail?.message || String(error)
  if (detail?.code === 'incompatible' || /incompatible/.test(message)) {
    const versions = detail.from_version != null && detail.to_version != null ? ` Current data version ${detail.from_version}; target data version ${detail.to_version}.` : ''
    return `Incompatible revision: ${message}.${versions} Your current code and records are unchanged.`
  }
  if (detail?.code === 'limit') return `limit: ${message}${detail.limit != null ? ` · limit ${detail.limit}` : ''}${detail.actual != null ? ` · actual ${detail.actual}` : ''}`
  return message
}
export function diagnosticText(value) {
  return String(value).replace(/\b(Bearer)\s+\S+/gi, '$1 [redacted]').replace(/\b(api[_-]?key|token|password|secret|authorization)(["']?\s*[:=]\s*["']?)[^\s,"';}]+/gi, '$1$2[redacted]').slice(0, 2000)
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
