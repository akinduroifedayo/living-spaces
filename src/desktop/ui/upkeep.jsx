import { ErrorState, Skeleton, useQuery } from '@hermes/plugin-sdk'
import { useEffect, useRef, useState } from 'react'
import { Action, Banner, CopyPrompt, DecisionDialog, Drawer, StatusPill, Time, absolute, relative } from './components.jsx'
import { CATCH_UP, errorText, executionLabel, spacePath, toSeconds } from './model.mjs'

export function UpkeepCost({ job, expanded = false }) {
  if (job?.uses_model === false) return <p>Refreshes from public sources. No model calls.</p>
  if (job?.uses_model !== true) return null
  return <div className="ls-upkeep-prompt">{job.prompt && <><h3>What Hermes does each run</h3><p id="ls-upkeep-prompt" className={expanded ? '' : 'ls-clamp-six'}>{job.prompt}</p></>}<p className="ls-secondary">Uses model calls.</p></div>
}

function Executions({ executions }) {
  if (!executions?.length) return <p className="ls-secondary">No runs recorded yet.</p>
  return <ul className="ls-audit" aria-label="Upkeep executions">{executions.map(run => {
    const at = toSeconds(run.finished_at ?? run.started_at ?? run.claimed_at ?? run.scheduled_instant)
    return <li key={run.id} data-status={run.status}>{at != null && <><Time at={at} /> · </>}<strong>{executionLabel(run.status)}</strong>{run.error ? ` · ${run.error}` : ''}</li>
  })}</ul>
}
const isRunning = data => data?.job?.state === 'running' || data?.executions?.some(run => ['running', 'claimed'].includes(run.status)) === true

export function UpkeepSheet({ ctx, space, onClose, onChanged, returnFocus }) {
  const base = spacePath(space.id)
  const [busy, setBusy] = useState(null)
  const [feedback, setFeedback] = useState('')
  const [error, setError] = useState('')
  const [confirm, setConfirm] = useState(false)
  const [recentAction, setRecentAction] = useState(0)
  const [slow, setSlow] = useState(false)
  const [fullError, setFullError] = useState(false)
  const [fullPrompt, setFullPrompt] = useState(false)
  const [visible, setVisible] = useState(() => typeof document === 'undefined' || !document.hidden)
  const lock = useRef(false)
  const feedbackNode = useRef(null)
  const query = useQuery({ queryKey: ['living-spaces', ctx.queryScope || null, space.id, 'upkeep'], queryFn: () => ctx.rest(`${base}/upkeep`),
    refetchInterval: native => !visible ? false : isRunning(native.state?.data) || recentAction ? 2000 : 5000,
    refetchIntervalInBackground: false, notifyOnChangeProps: ['data', 'error', 'dataUpdatedAt'] })
  const data = query.data
  const link = data?.link
  const job = data?.job
  const archived = space.status === 'archived'
  const running = isRunning(data)
  const unavailable = !!data?.error || !!query.error || (!!link && !job && !data?.missing)
  const blocked = archived || unavailable || !!busy
  useEffect(() => {
    const update = () => setVisible(!document.hidden)
    document.addEventListener('visibilitychange', update)
    return () => document.removeEventListener('visibilitychange', update)
  }, [])
  useEffect(() => {
    if (data || query.error) { setSlow(false); return }
    const timer = setTimeout(() => setSlow(true), 8000)
    return () => clearTimeout(timer)
  }, [!!data, !!query.error])
  useEffect(() => {
    if (!recentAction) return
    const timer = setTimeout(() => setRecentAction(0), 60000)
    return () => clearTimeout(timer)
  }, [recentAction])
  useEffect(() => {
    if (!feedback || busy) return
    const timer = setTimeout(() => setFeedback(''), 8000)
    return () => clearTimeout(timer)
  }, [feedback, busy])
  async function act(action) {
    if (lock.current) return
    if (blocked || (action === 'run' && running)) {
      if (action === 'remove') throw new Error('Upkeep is unavailable. Reload the native state before removing it.')
      return
    }
    lock.current = true
    setBusy(action); setError(''); setFeedback(action === 'run' ? 'Starting…' : 'Working…'); setRecentAction(Date.now())
    try {
      await ctx.rest(`${base}/upkeep`, { method: 'POST', body: { action } })
      const [current] = await Promise.all([query.refetch(), onChanged?.()])
      if (current?.error || current?.data?.error) throw new Error(`The action was submitted, but the current native state couldn't be loaded. ${errorText(current.error || current.data.error)}`)
      if (current?.data && ((action === 'pause' && current.data.job?.enabled !== false) || (action === 'resume' && current.data.job?.enabled !== true) || (action === 'remove' && current.data.link))) throw new Error('Hermes has not confirmed the requested state.')
      const next = toSeconds(current?.data?.job?.next_run_at)
      setFeedback(action === 'run' ? 'Run requested. Check native execution history for progress.' : action === 'pause' ? 'Paused. Future runs stop until you resume. Already-running work may finish.' : action === 'resume' ? `Resumed.${next != null ? ` Next run ${absolute(next)}.` : ''}` : `Upkeep removed. ${space.name} is unchanged.`)
    } catch (e) {
      setFeedback('')
      setError(`${action === 'run' ? "Couldn't start the run." : action === 'pause' ? "Couldn't pause upkeep." : action === 'resume' ? "Couldn't resume upkeep." : "Couldn't remove upkeep."} ${errorText(e)} Review the current native state before trying again.`)
      await query.refetch()
      if (action === 'remove') throw e
    } finally { lock.current = false; setBusy(null) }
  }
  const removeButton = <Action danger aria-disabled={blocked} onClick={() => !blocked && setConfirm(true)}>{data?.missing ? 'Remove link' : 'Remove'}</Action>
  const ask = <CopyPrompt text={`${space.owner}, schedule upkeep for ${space.name}. Please confirm the cadence and timezone, then create it as a Hermes cron job.`} label="Copy prompt" />
  const lastAt = toSeconds(job?.last_run_at)
  const lastResult = running ? 'Running now…' : job?.last_status ? executionLabel(['ok', 'success'].includes(job.last_status) ? 'succeeded' : job.last_status === 'error' ? 'failed' : job.last_status) : null
  let body
  if (query.error && !data) body = <ErrorState title="Upkeep couldn't be loaded" description={`Hermes didn't respond. ${errorText(query.error)}`}><Action onClick={() => query.refetch()}>Try again</Action></ErrorState>
  else if (!data) body = <div aria-busy="true" aria-label="Loading upkeep"><Skeleton style={{ width: 80, height: 24 }} />{[1, 2, 3].map(row => <Skeleton key={row} style={{ height: 32, marginTop: 12 }} />)}<Skeleton style={{ height: 32, marginTop: 20 }} /><p role="status">{slow ? 'Still waiting for Hermes…' : 'Loading upkeep…'}</p></div>
  else body = <>
    {query.error && <Banner title={`Showing the last loaded state${query.dataUpdatedAt ? ` from ${relative(query.dataUpdatedAt / 1000)}` : ''}.`} actions={<Action onClick={() => query.refetch()}>Try again</Action>}>{errorText(query.error)}</Banner>}
    {data.error && <Banner kind="failed" title="Hermes cron is unavailable">{errorText(data.error)}</Banner>}
    {archived && <p>Archived Spaces don't run upkeep. Restore the Space to use it. Already-running work may finish.</p>}
    {!link ? <><h3>No upkeep yet</h3><p>This Space isn't updated automatically. Ask {space.owner} in chat to set up upkeep as a Hermes cron job.</p>{ask}</> : data.missing ? <>
      <StatusPill status="blocked" label="Job missing" /><Banner kind="blocked" title="Hermes no longer has this job" actions={removeButton}>Nothing will run. Ask {space.owner} in chat to schedule upkeep again.</Banner>{ask}
    </> : job ? <>
      <StatusPill status={running ? 'running' : job.enabled ? 'ready' : 'paused'} label={running ? 'Running now' : job.enabled ? 'Active' : 'Paused'} />
      <UpkeepCost job={job} expanded={fullPrompt} />
      <dl className="ls-facts">
        {(job.schedule_display || job.cadence || job.timezone) && <div><dt>Runs</dt><dd>{job.schedule_display || job.cadence}{job.timezone && <div className="ls-secondary">{job.timezone}</div>}</dd></div>}
        <div><dt>Next run</dt><dd>{!job.enabled ? "Paused. Future runs stop until resumed. Already-running work may finish." : toSeconds(job.next_run_at) != null ? <><Time at={toSeconds(job.next_run_at)} /> · <Time at={toSeconds(job.next_run_at)} relative /></> : 'Waiting for Hermes to schedule it'}</dd></div>
        {(lastResult || lastAt == null) && <div><dt>Last result</dt><dd>{lastResult || "Hasn't run yet"}{!running && lastAt != null && <> · <Time at={lastAt} /></>}</dd></div>}
      </dl>
      <p className="ls-upkeep-note ls-secondary">{CATCH_UP}</p>
      <div className="ls-actions ls-upkeep-actions">
        <Action aria-busy={busy === 'run'} aria-disabled={blocked || running} title={running ? 'Already running' : undefined} icon="run" onClick={() => act('run')}>Run now</Action>
        <Action primary={!job.enabled} aria-busy={busy === (job.enabled ? 'pause' : 'resume')} aria-disabled={blocked} icon={job.enabled ? 'debug-pause' : 'play'} onClick={() => act(job.enabled ? 'pause' : 'resume')}>{job.enabled ? 'Pause' : 'Resume'}</Action>
        {removeButton}
      </div>
    </> : !data.error && <Banner kind="blocked" title="Waiting for the native job state" actions={<Action onClick={() => query.refetch()}>Try again</Action>}>Controls are unavailable until Hermes responds.</Banner>}
  </>
  return <><Drawer title={`Upkeep · ${space.name}`} description="The Hermes cron job that keeps this Space current" onClose={onClose} returnFocus={returnFocus}>
    {body}
    <div ref={feedbackNode} tabIndex={-1} role="status" aria-live="polite" className="ls-upkeep-feedback">{feedback}</div>
    {error && <Banner kind="failed" title={error} />}
    {job?.uses_model === true && job.prompt && <div className="ls-section"><Action aria-expanded={fullPrompt} aria-controls="ls-upkeep-prompt" onClick={() => setFullPrompt(!fullPrompt)}>{fullPrompt ? 'Show less' : 'Show full prompt'}</Action></div>}
    {job?.last_error && ['failed', 'error'].includes(job.last_status) && <Banner kind="failed" title={`Last run failed${lastAt != null ? ` ${absolute(lastAt)}` : ''}`} actions={<><Action aria-disabled={blocked || running} onClick={() => act('run')}>Run now</Action><Action onClick={() => document.getElementById('ls-upkeep-executions')?.focus()}>View history</Action></>}><p id="ls-upkeep-error" className={fullError ? '' : 'ls-clamp-three'}>{job.last_error}</p><Action aria-expanded={fullError} aria-controls="ls-upkeep-error" onClick={() => setFullError(!fullError)}>{fullError ? 'Show less' : 'Show more'}</Action></Banner>}
    {link && <section className="ls-section" id="ls-upkeep-executions" tabIndex={-1}><h3 className="ls-section-title">Executions</h3><Executions executions={data.executions} /></section>}
    {!!data?.one_shots?.length && <section className="ls-section" data-testid="one-shots"><h3 className="ls-section-title">Refresh now runs</h3><p className="ls-secondary">One-time Hermes agent runs started with Refresh now. Each uses model calls.</p><Executions executions={data.one_shots.flatMap(shot => shot.executions || [])} /></section>}
  </Drawer>{confirm && <DecisionDialog danger successFocus={feedbackNode} title={`Remove upkeep for ${space.name}?`} description="This deletes the Hermes cron job. Future runs stop, but already-running work may finish. The Space and its data are kept." cancelLabel="Keep upkeep" confirmLabel="Remove" onClose={() => setConfirm(false)} onConfirm={() => act('remove')} />}</>
}
