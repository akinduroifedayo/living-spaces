import { ErrorState, Skeleton, useQuery } from '@hermes/plugin-sdk'
import { useRef, useState } from 'react'
import { Action, Banner, CopyPrompt, DecisionDialog, Drawer, StatusPill, Time } from './components.jsx'
import { CATCH_UP, errorText, executionLabel, spacePath, toSeconds } from './model.mjs'

export function UpkeepCost({ job, kind }) {
  return (job ? job.uses_model : kind === 'agent')
    ? <><p>Uses model calls. Runs a Hermes agent with the tools enabled for native cron jobs.</p><div><strong>Upkeep prompt</strong><p style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{job?.prompt}</p></div></>
    : <p>No model calls. Refreshes use the declared public-source handler and approved hosts.</p>
}

function Executions({ executions }) {
  if (!executions?.length) return <p className="ls-secondary">No runs recorded yet.</p>
  return <ul className="ls-audit" aria-label="Upkeep executions">{executions.map(run => <li key={run.id} data-status={run.status}>
    <Time at={toSeconds(run.finished_at ?? run.started_at ?? run.claimed_at ?? run.scheduled_instant)} /> · <strong>{executionLabel(run.status)}</strong>{run.error ? ` · ${run.error}` : ''}
  </li>)}</ul>
}

export function UpkeepSheet({ ctx, space, onClose, onChanged, returnFocus }) {
  const base = spacePath(space.id)
  const query = useQuery({ queryKey: ['living-spaces', ctx.queryScope || null, space.id, 'upkeep'], queryFn: () => ctx.rest(`${base}/upkeep`), refetchInterval: 5000 })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [confirm, setConfirm] = useState(false)
  const lock = useRef(false)
  const data = query.data
  const link = data?.link
  const job = data?.job
  const archived = space.status === 'archived'
  async function act(action) {
    if (lock.current) return
    lock.current = true
    setBusy(true); setError('')
    try { await ctx.rest(`${base}/upkeep`, { method: 'POST', body: { action } }); await Promise.all([query.refetch(), onChanged?.()]) }
    catch (e) { setError(errorText(e)); await query.refetch() }
    finally { lock.current = false; setBusy(false) }
  }
  const removeButton = <Action danger disabled={busy} onClick={() => setConfirm(true)}>{data?.missing ? 'Remove link' : 'Remove'}</Action>
  let body
  if (query.error && !data) body = <ErrorState title="Upkeep could not be loaded" description={errorText(query.error)}><Action onClick={() => query.refetch()}>Try again</Action></ErrorState>
  else if (!data) body = <Skeleton style={{ height: 180 }} />
  else if (!link) body = <><p>No upkeep scheduled</p><div className="ls-section"><CopyPrompt text={`${space.owner}, schedule upkeep for ${space.name}. Please confirm the cadence and timezone, then create it as a Hermes cron job.`} label="Ask in chat" /></div></>
  else body = <>
    {data.error && <Banner kind="failed" title="Hermes cron is unavailable">{data.error}</Banner>}
    {data.missing ? <><Banner kind="blocked" title="The linked Hermes job no longer exists" actions={removeButton}>Nothing will run. Ask {space.owner} in chat to schedule upkeep again.</Banner><div className="ls-section"><CopyPrompt text={`${space.owner}, the Hermes cron job for ${space.name} no longer exists. Please schedule upkeep again.`} label="Ask in chat" /></div></> : job && <>
      <StatusPill status={job.enabled ? 'ready' : 'paused'} label={job.enabled ? 'Active' : 'Paused'} />
      <dl className="ls-facts">
        <div><dt>Kind</dt><dd>{job.uses_model ? 'Agent' : 'Feed'}</dd></div>
        <div><dt>Schedule</dt><dd>{job.schedule_display || job.cadence}</dd></div>
        <div><dt>Cadence</dt><dd>{job.cadence}</dd></div>
        <div><dt>Timezone</dt><dd>{job.timezone}</dd></div>
        <div><dt>State</dt><dd>{job.enabled ? 'Enabled' : 'Disabled'} · {job.state}</dd></div>
        <div><dt>Next run</dt><dd>{job.enabled && job.next_run_at ? <Time at={toSeconds(job.next_run_at)} /> : 'Not scheduled'}</dd></div>
        <div><dt>Last run</dt><dd>{job.last_run_at ? <><Time at={toSeconds(job.last_run_at)} /> · {job.last_status || 'No status'}</> : 'Never'}</dd></div>
        {job.last_error && <div><dt>Last error</dt><dd>{job.last_error}</dd></div>}
      </dl>
      <section className="ls-section"><h2 className="ls-section-title">Cost</h2><UpkeepCost job={job} kind={link.kind} /></section>
      <section className="ls-section"><h2 className="ls-section-title">If Hermes is asleep</h2><p>{CATCH_UP}</p></section>
      <div className="ls-actions">
        <Action disabled={busy || (!job.enabled && archived)} icon={job.enabled ? 'debug-pause' : 'play'} onClick={() => act(job.enabled ? 'pause' : 'resume')}>{job.enabled ? 'Pause' : 'Resume'}</Action>
        <Action disabled={busy || archived} icon="run" onClick={() => act('run')}>Run now</Action>
        {removeButton}
      </div>
    </>}
    <section className="ls-section"><h2 className="ls-section-title">Executions</h2><Executions executions={data.executions} /></section>
  </>
  const oneShots = data?.one_shots || []
  const refreshes = oneShots.length > 0 && <section className="ls-section" data-testid="one-shots"><h2 className="ls-section-title">Refresh now runs</h2><p className="ls-secondary">One-time Hermes agent runs started with Refresh now. Each uses model calls.</p><Executions executions={oneShots.flatMap(shot => shot.executions)} /></section>
  return <><Drawer title={`Upkeep · ${space.name}`} description="The Hermes cron job that keeps this Space current" onClose={onClose} returnFocus={returnFocus}>
    {error && <Banner kind="failed" title={error} />}
    {body}
    {refreshes}
  </Drawer>{confirm && <DecisionDialog danger title={`Remove upkeep for ${space.name}?`} description="This deletes the Hermes cron job. The Space and its data are kept." confirmLabel="Remove" onClose={() => setConfirm(false)} onConfirm={async () => { await ctx.rest(`${base}/upkeep`, { method: 'POST', body: { action: 'remove' } }); await Promise.all([query.refetch(), onChanged?.()]) }} />}</>
}
