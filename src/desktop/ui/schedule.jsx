import { useRef, useState } from 'react'
import { Action, Banner, CopyPrompt, Drawer, StatusPill, Time } from './components.jsx'
import { CATCH_UP, errorText, spacePath } from './model.mjs'

export function ScheduleSheet({ ctx, space, onClose, onChanged, returnFocus }) {
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const lock = useRef(false)
  const schedule = space.schedule
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
    {schedule ? <><StatusPill status={schedule.status === 'active' ? 'ready' : schedule.status === 'paused' ? 'paused' : schedule.status} label={schedule.status === 'active' ? 'Active' : schedule.status === 'disabled' ? 'Disabled' : undefined} /><dl className="ls-facts"><div><dt>Cadence</dt><dd>{schedule.cadence}</dd></div><div><dt>Timezone</dt><dd>{schedule.timezone}</dd></div><div><dt>Purpose</dt><dd>{schedule.purpose}</dd></div><div><dt>Next run</dt><dd>{schedule.status === 'active' ? <Time at={schedule.next_run_at ?? space.freshness?.next_run_at} /> : 'Not scheduled while upkeep is inactive'}</dd></div><div><dt>Last attempt</dt><dd><Time at={space.freshness?.last_attempt_at} /> · {space.freshness?.last_attempt_status || 'No attempts'}</dd></div></dl></> : <p>No schedule approved.</p>}
    <section className="ls-section"><h2 className="ls-section-title">Cost</h2><p>No model calls. Refreshes use the declared public-source handler and approved hosts.</p><p className="ls-secondary">Feed limit 3 MB · 200 entries per source · 20 s request timeout.</p></section>
    <section className="ls-section"><h2 className="ls-section-title">If Hermes is asleep</h2><p>{CATCH_UP}</p><p className="ls-secondary">Background execution depends on Hermes being available.</p></section>
    {schedule && ['active', 'paused'].includes(schedule.status) && <Action disabled={busy || space.status === 'archived'} icon={schedule.status === 'paused' ? 'play' : 'debug-pause'} onClick={pause}>{schedule.status === 'paused' ? 'Resume upkeep' : 'Pause upkeep'}</Action>}
    <div className="ls-section"><CopyPrompt text={`${space.owner}, change the upkeep schedule for ${space.name}. Please confirm the cadence, timezone and purpose before requesting approval.`} label="Change schedule in chat" /></div>
  </Drawer>
}
