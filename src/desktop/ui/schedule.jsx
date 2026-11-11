import { useRef, useState } from 'react'
import { Action, Banner, CopyPrompt, Drawer, StatusPill, Time, absolute } from './components.jsx'
import { CATCH_UP, dispatchText, errorText, spacePath } from './model.mjs'

export function UpkeepCost({ space, upkeep = space?.manifest?.upkeep }) {
  return upkeep?.handler === 'agent' ? <><p>Uses model calls. Runs a Hermes agent with the tools enabled for native cron jobs.</p><p className="ls-secondary">The agent is instructed to update only this Space through spaces_* tools and preserve user notes and statuses.</p><div><strong>Upkeep prompt</strong><p style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{upkeep.prompt}</p></div></> : <><p>No model calls. Refreshes use the declared public-source handler and approved hosts.</p><p className="ls-secondary">Feed limit 3 MB · 200 entries per source · 20 s request timeout.</p></>
}

export function ScheduleSheet({ ctx, space, onClose, onChanged, returnFocus }) {
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const lock = useRef(false)
  const schedule = space.schedule
  const refresh = space.grants?.find(grant => grant.capability === 'refresh')
  const permissionReason = schedule?.reason?.match(/Refresh permission (revoked|denied)/i)
  const permissionStatus = ['revoked', 'denied'].includes(refresh?.status) ? refresh.status : permissionReason?.[1]?.toLowerCase()
  const reason = permissionStatus ? refresh?.status === 'granted' ? 'Refresh permission approved. Select Resume upkeep to restart scheduled refreshes.' : 'Refresh permission revoked. Approve Refresh in Permissions, then resume upkeep.' : schedule?.reason
  const nextRun = schedule?.next_run_at ?? space.freshness?.next_run_at
  const overdue = schedule?.status === 'active' && nextRun != null && nextRun < Date.now() / 1000
  async function pause() {
    if (lock.current) return
    lock.current = true
    setBusy(true)
    try { await ctx.rest(`${spacePath(space.id)}/schedule`, { method: 'POST', body: { paused: schedule.status !== 'paused' } }); await onChanged() }
    catch (e) { setError(errorText(e)) }
    finally { lock.current = false; setBusy(false) }
  }
  return <Drawer title={`Schedule · ${space.name}`} description="Schedule, cost and missed-run policy" onClose={onClose} returnFocus={returnFocus}>
    {error && <Banner kind="failed" title={error} />}
    {schedule ? <><StatusPill status={schedule.status === 'active' ? 'ready' : schedule.status === 'paused' ? 'paused' : schedule.status} label={schedule.status === 'active' ? 'Active' : schedule.status === 'disabled' ? 'Disabled' : undefined} /><dl className="ls-facts"><div><dt>Cadence</dt><dd>{schedule.cadence}</dd></div><div><dt>Timezone</dt><dd>{schedule.timezone}</dd></div><div><dt>Purpose</dt><dd>{schedule.purpose}</dd></div><div><dt>Next run</dt><dd>{schedule.status === 'active' ? <>{overdue && "Delayed · awaiting Hermes. Scheduled for "}<Time at={nextRun} /></> : 'Not scheduled while upkeep is inactive'}</dd></div><div><dt>Last attempt</dt><dd><Time at={space.freshness?.last_attempt_at} /> · {space.freshness?.last_attempt_status || 'No attempts'}</dd></div>{reason && <div><dt>Reason</dt><dd>{reason}</dd></div>}{schedule.last_dispatch && <div><dt>Last dispatch</dt><dd>{dispatchText(schedule.last_dispatch, absolute)}</dd></div>}</dl></> : <p>No schedule approved.</p>}
    <section className="ls-section"><h2 className="ls-section-title">Cost</h2><UpkeepCost space={space} /></section>
    <section className="ls-section"><h2 className="ls-section-title">If Hermes is asleep</h2><p>{CATCH_UP}</p><p className="ls-secondary">Background execution depends on Hermes being available.</p></section>
    {schedule && ['active', 'paused'].includes(schedule.status) && <Action disabled={busy || space.status === 'archived' || (schedule.status === 'paused' && refresh?.status !== 'granted')} icon={schedule.status === 'paused' ? 'play' : 'debug-pause'} onClick={pause}>{schedule.status === 'paused' ? 'Resume upkeep' : 'Pause upkeep'}</Action>}
    <div className="ls-section"><CopyPrompt text={`${space.owner}, change the upkeep schedule for ${space.name}. Please confirm the cadence, timezone and purpose before requesting approval.`} label="Change schedule in chat" /></div>
  </Drawer>
}
