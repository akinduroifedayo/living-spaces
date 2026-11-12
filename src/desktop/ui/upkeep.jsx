import { ErrorState, Skeleton, useQuery } from '@hermes/plugin-sdk'
import { useEffect, useRef, useState } from 'react'
import { Action, Banner, CopyPrompt, DecisionDialog, Drawer, StatusPill, Time, absolute, relative } from './components.jsx'
import { CATCH_UP, errorText, executionLabel, spacePath, toSeconds } from './model.mjs'

export function UpkeepCost({ job, expanded = false, unavailable }) {
  if (job?.uses_model === false) return <p>Refreshes from public sources. No model calls.</p>
  if (job?.uses_model !== true) return null
  const prompt = unavailable ? job.prompt_preview : job.prompt
  return <div className="ls-upkeep-prompt">{prompt && <><h3>{unavailable ? 'Prompt preview' : 'What Hermes does each run'}</h3><p id="ls-upkeep-prompt" className={expanded ? '' : 'ls-clamp-six'}>{prompt}</p></>}{unavailable && <p className="ls-secondary">{unavailable}</p>}<p className="ls-secondary">Uses model calls.</p></div>
}

function Executions({ executions, unavailable }) {
  if (unavailable) return <p className="ls-secondary">{unavailable}</p>
  if (!executions?.length) return <p className="ls-secondary">No runs recorded yet.</p>
  return <ul className="ls-audit" aria-label="Upkeep executions">{executions.map(run => {
    const at = toSeconds(run.finished_at ?? run.started_at ?? run.claimed_at ?? run.scheduled_instant)
    return <li key={run.id} data-status={run.status}>{at != null && <><Time at={at} /> · </>}<strong>{executionLabel(run.status)}</strong>{run.error ? ` · ${run.error}` : ''}</li>
  })}</ul>
}
const isRunning = data => data?.job?.state === 'running' || data?.executions?.some(run => ['running', 'claimed'].includes(run.status)) === true

export function UpkeepSheet({ ctx, scopeKey = null, space, onClose, onChanged, returnFocus }) {
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
  const query = useQuery({ queryKey: ['living-spaces', scopeKey, space.id, 'upkeep'], queryFn: () => ctx.rest(`${base}/upkeep`),
    refetchInterval: native => !visible ? false : isRunning(native.state?.data) || recentAction ? 2000 : 5000,
    refetchIntervalInBackground: false, notifyOnChangeProps: ['data', 'error', 'dataUpdatedAt'] })
  const data = query.data
  const link = data?.link
  const job = data?.job
  const orphans = data?.orphan_jobs || []
  const hasRecovery = orphans.length > 0 || !!data?.one_shots?.length
  const ownedJobs = state => [state?.job, ...(state?.orphan_jobs || []), ...(state?.one_shots || [])].filter(Boolean)
  const archived = space.status === 'archived'
  const running = isRunning(data)
  const unavailable = !!data?.error || !!query.error || (!!link && !job && !data?.missing)
  const blocked = archived || unavailable || !!busy
  const cleanupBlocked = !data || unavailable || !!busy
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
    if ((['pause', 'remove'].includes(action) ? cleanupBlocked : blocked) || (action === 'run' && running)) {
      if (action === 'remove') throw new Error('Upkeep is unavailable. Reload the native state before removing it.')
      return
    }
    lock.current = true
    setBusy(action); setError(''); setFeedback(action === 'run' ? 'Starting…' : 'Working…'); setRecentAction(Date.now())
    try {
      const response = await ctx.rest(`${base}/upkeep`, { method: 'POST', body: { action } })
      if (action === 'run' && response?.dispatch?.job?.execution_success === false) throw new Error(response.dispatch.job.execution_error || 'Hermes reports that this execution failed.')
      const [current] = await Promise.all([query.refetch(), onChanged?.()])
      if (current?.error || current?.data?.error) throw new Error(`The action was submitted, but the current native state couldn't be loaded. ${errorText(current.error || current.data.error)}`)
      if (!current?.data || response?.error) throw new Error('Hermes has not confirmed the requested state.')
      const currentJobs = ownedJobs(current.data)
      const returnedJobs = ownedJobs(response)
      if ((action === 'pause' && (currentJobs.some(target => target.enabled !== false)
          || returnedJobs.some(target => target.enabled !== false)
          || [...ownedJobs(data), ...returnedJobs].some(target => !currentJobs.some(job => job.id === target.id && job.enabled === false))))
          || (action === 'resume' && current.data.job?.enabled !== true)
          || (action === 'remove' && (current.data.link || response?.link || currentJobs.length || returnedJobs.length))) throw new Error('Hermes has not confirmed the requested state.')
      const next = toSeconds(current?.data?.job?.next_run_at)
      setFeedback(action === 'run' ? 'Run requested. Execution and delivery are not confirmed by this request; review the last-result metadata below.' : action === 'pause' ? 'Paused. Future runs stop until you resume. Already-running work may finish.' : action === 'resume' ? `Resumed.${next != null ? ` Next run ${absolute(next)}.` : ''}` : `Upkeep removed. ${space.name} is unchanged.`)
    } catch (e) {
      setFeedback('')
      setError(`${action === 'run' ? "Couldn't start the run." : action === 'pause' ? "Couldn't pause upkeep." : action === 'resume' ? "Couldn't resume upkeep." : "Couldn't remove upkeep."} ${errorText(e)} Review the current native state before trying again.`)
      await query.refetch()
      if (action === 'remove') throw e
    } finally { lock.current = false; setBusy(null) }
  }
  const removeButton = <Action danger aria-disabled={cleanupBlocked} onClick={() => !cleanupBlocked && setConfirm(true)}>{data?.missing && !hasRecovery ? 'Remove link' : 'Remove'}</Action>
  const ask = <CopyPrompt text={`${space.owner}, schedule upkeep for ${space.name}. Please confirm the cadence and timezone, then create it as a Hermes cron job.`} label="Copy prompt" />
  const lastAt = toSeconds(job?.last_run_at)
  const lastResult = running ? 'Running now…' : job?.last_status ? executionLabel(['ok', 'success'].includes(job.last_status) ? 'succeeded' : job.last_status === 'error' ? 'failed' : job.last_status) : null
  let body
  if (query.error && !data) body = <ErrorState title="Upkeep couldn't be loaded" description={`Hermes didn't respond. ${errorText(query.error)}`}><Action onClick={() => query.refetch()}>Try again</Action></ErrorState>
  else if (!data) body = <div aria-busy="true" aria-label="Loading upkeep"><Skeleton style={{ width: 80, height: 24 }} />{[1, 2, 3].map(row => <Skeleton key={row} style={{ height: 32, marginTop: 12 }} />)}<Skeleton style={{ height: 32, marginTop: 20 }} /><p role="status">{slow ? 'Still waiting for Hermes…' : 'Loading upkeep…'}</p></div>
  else body = <>
    {query.error && <Banner title={`Showing the last loaded state${query.dataUpdatedAt ? ` from ${relative(query.dataUpdatedAt / 1000)}` : ''}.`} actions={<Action onClick={() => query.refetch()}>Try again</Action>}>{errorText(query.error)}</Banner>}
    {data.error && <Banner kind="failed" title="Hermes cron is unavailable">{errorText(data.error)}</Banner>}
    {data.warning && <Banner kind="blocked" title="Hermes cron notice">{data.warning}</Banner>}
    {archived && <p>Run and Resume are unavailable while this Space is archived. Use Pause or Remove to clean up native work. Already-running work may finish.</p>}
    {!link ? hasRecovery ? <Banner kind="blocked" title="No primary upkeep link">Space-owned jobs below may still run. Pause or remove them before scheduling upkeep again.</Banner> : <><h3>No upkeep yet</h3><p>This Space isn't updated automatically. Ask {space.owner} in chat to set up upkeep as a Hermes cron job.</p>{ask}</> : data.missing ? <>
      <StatusPill status="blocked" label="Job missing" /><Banner kind="blocked" title="Hermes no longer has this job" actions={removeButton}>{hasRecovery ? 'Other Space-owned jobs below may still run. Pause or remove them before scheduling upkeep again.' : `Nothing will run. Ask ${space.owner} in chat to schedule upkeep again.`}</Banner>{!hasRecovery && ask}
    </> : job ? <>
      <StatusPill status={running ? 'running' : !job.enabled ? 'paused' : data.gateway_running === false ? 'blocked' : 'ready'} label={running ? 'Running now' : !job.enabled ? 'Paused' : data.gateway_running === false ? 'Scheduler offline' : 'Active'} />
      <UpkeepCost job={job} expanded={fullPrompt} unavailable={data.unavailable?.prompt} />
      <dl className="ls-facts">
        {(job.schedule_display || job.cadence || job.timezone) && <div><dt>Runs</dt><dd>{job.schedule_display || job.cadence}{job.timezone && <div className="ls-secondary">{job.timezone}</div>}</dd></div>}
        {data.unavailable?.timezone && <div><dt>Timezone</dt><dd>{data.unavailable.timezone}</dd></div>}
        <div><dt>Next run</dt><dd>{!job.enabled ? "Paused. Future runs stop until resumed. Already-running work may finish." : toSeconds(job.next_run_at) != null ? <><Time at={toSeconds(job.next_run_at)} /> · <Time at={toSeconds(job.next_run_at)} relative /></> : 'Waiting for Hermes to schedule it'}</dd></div>
        {(lastResult || lastAt == null) && <div><dt>Last result</dt><dd>{lastResult || (data.unavailable?.executions ? 'No last-result metadata available' : "Hasn't run yet")}{!running && lastAt != null && <> · <Time at={lastAt} /></>}</dd></div>}
      </dl>
      <p className="ls-upkeep-note ls-secondary">{CATCH_UP}</p>
      <div className="ls-actions ls-upkeep-actions">
        <Action aria-busy={busy === 'run'} aria-disabled={blocked || running} title={running ? 'Already running' : undefined} icon="run" onClick={() => act('run')}>Run now</Action>
        <Action primary={!job.enabled} aria-busy={busy === (job.enabled ? 'pause' : 'resume')} aria-disabled={job.enabled ? cleanupBlocked : blocked} icon={job.enabled ? 'debug-pause' : 'play'} onClick={() => act(job.enabled ? 'pause' : 'resume')}>{job.enabled ? 'Pause' : 'Resume'}</Action>
        {removeButton}
      </div>
    </> : !data.error && <Banner kind="blocked" title="Waiting for the native job state" actions={<Action onClick={() => query.refetch()}>Try again</Action>}>Controls are unavailable until Hermes responds.</Banner>}
  </>
  return <><Drawer title={`Upkeep · ${space.name}`} description="The Hermes cron job that keeps this Space current" onClose={onClose} returnFocus={returnFocus}>
    {body}
    {!!orphans.length && <section className="ls-section" data-testid="orphan-jobs"><h3 className="ls-section-title">Unlinked upkeep jobs</h3><p>These native jobs belong to this Space but are not its primary upkeep link. Enabled jobs may run, including duplicate upkeep.</p><ul className="ls-audit">{orphans.map(orphan => <li key={orphan.id}><code>{orphan.id}</code> · {orphan.state || 'Unknown native state'} · {orphan.enabled === true ? 'Enabled' : orphan.enabled === false ? 'Disabled' : 'Enabled state unknown'}</li>)}</ul></section>}
    {hasRecovery && <div className="ls-actions ls-upkeep-actions"><Action aria-busy={busy === 'pause'} aria-disabled={cleanupBlocked} icon="debug-pause" onClick={() => act('pause')}>Pause</Action>{removeButton}</div>}
    <div ref={feedbackNode} tabIndex={-1} role="status" aria-live="polite" className="ls-upkeep-feedback">{feedback}</div>
    {error && <Banner kind="failed" title={error} />}
    {job?.uses_model === true && job.prompt && !data?.unavailable?.prompt && <div className="ls-section"><Action aria-expanded={fullPrompt} aria-controls="ls-upkeep-prompt" onClick={() => setFullPrompt(!fullPrompt)}>{fullPrompt ? 'Show less' : 'Show full prompt'}</Action></div>}
    {job?.last_error && ['failed', 'error'].includes(job.last_status) && <Banner kind="failed" title={`Last run failed${lastAt != null ? ` ${absolute(lastAt)}` : ''}`} actions={<><Action aria-disabled={blocked || running} onClick={() => act('run')}>Run now</Action>{!data?.unavailable?.executions && <Action onClick={() => document.getElementById('ls-upkeep-executions')?.focus()}>View history</Action>}</>}><p id="ls-upkeep-error" className={fullError ? '' : 'ls-clamp-three'}>{job.last_error}</p><Action aria-expanded={fullError} aria-controls="ls-upkeep-error" onClick={() => setFullError(!fullError)}>{fullError ? 'Show less' : 'Show more'}</Action></Banner>}
    {link && <section className="ls-section" id="ls-upkeep-executions" tabIndex={-1}><h3 className="ls-section-title">Executions</h3><Executions executions={data.executions} unavailable={data.unavailable?.executions} />{data.unavailable?.dispatch && <p className="ls-secondary">{data.unavailable.dispatch}</p>}</section>}
    {!!data?.one_shots?.length && <section className="ls-section" data-testid="one-shots"><h3 className="ls-section-title">{data.unavailable?.executions ? 'Refresh now jobs' : 'Refresh now runs'}</h3><p className="ls-secondary">One-time Hermes jobs requested with Refresh now. Each uses model calls. A saved job is not proof that it ran.</p><Executions executions={data.one_shots.flatMap(shot => shot.executions || [])} unavailable={data.unavailable?.executions} /></section>}
  </Drawer>{confirm && <DecisionDialog danger successFocus={feedbackNode} title={`Remove upkeep for ${space.name}?`} description="This deletes this Space's linked job, unlinked upkeep jobs and Refresh now jobs. Future runs stop, but already-running work may finish. The Space and its data are kept." cancelLabel="Keep upkeep" confirmLabel="Remove" onClose={() => setConfirm(false)} onConfirm={() => act('remove')} />}</>
}
