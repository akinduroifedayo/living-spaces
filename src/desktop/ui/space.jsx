import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger, ErrorState, Skeleton, host, useQuery } from '@hermes/plugin-sdk'
import { useEffect, useRef, useState } from 'react'
import { Action, Banner, CopyPrompt, DecisionDialog, Drawer, Icon, OwnerChip, SpaceTile, StatusPill, Freshness, DisabledReason, absolute } from './components.jsx'
import { HistorySheet } from './history.jsx'
import { PermissionsSheet } from './permissions.jsx'
import { UpkeepSheet } from './upkeep.jsx'
import { advanceCursor, diagnosticText, errorText, headerFacts, inFlight, refreshReason, runResult, spacePath, spaceStatus } from './model.mjs'
import { createSpaceSession } from './session.mjs'
import { mountSpace } from '../sandbox/index.js'

function SaveStatus({ write, announcement }) {
  const labels = { saving: 'Saving…', saved: `Saved ${write?.at ? absolute(write.at) : ''}`, failed: 'Not saved — this change was rejected', unknown: 'Save outcome unknown — the change may have been stored', conflict: 'Conflict — this record changed elsewhere' }
  return <span className="ls-save" role="status" aria-live="polite" aria-atomic="true">{write && <><Icon name={write.status === 'saving' ? 'refresh' : ['failed', 'unknown', 'conflict'].includes(write.status) ? 'warning' : 'check'} spin={write.status === 'saving'} />{labels[write.status]}</>}{announcement && <span>{announcement}</span>}</span>
}
function WriteBanner({ write, setWrite, onCompare, onUpdated, onDismiss }) {
  if (!write || !['failed', 'unknown', 'conflict'].includes(write.status)) return null
  const current = write.reply?.error?.current
  const canKeep = write.op === 'data.put' && current?.rev != null
  return <Banner kind={write.status === 'conflict' ? 'conflict' : 'failed'} title={write.status === 'conflict' ? 'Conflict — this record changed elsewhere' : write.status === 'unknown' ? 'Save outcome unknown — the change may have been stored' : 'Not saved — this change was rejected'}
    actions={write.status === 'conflict' ? <>{canKeep && <Action onClick={() => write.retry({ ...write.args, base_rev: current.rev })}>Keep my note</Action>}<Action onClick={() => { setWrite(null); onUpdated(current) }}>Use updated record</Action><Action onClick={onCompare}>Compare</Action></> : write.retry ? <Action onClick={() => write.retry()}>Retry save</Action> : <Action onClick={onDismiss}>Dismiss</Action>}>
    {write.reply?.error ? errorText(write.reply.error) : 'Your change is kept in this view until you choose how to continue.'}
  </Banner>
}
export function SpaceView({ ctx, sid }) {
  const base = spacePath(sid)
  const detail = useQuery({ queryKey: ['living-spaces', ctx.queryScope || null, sid, 'detail'], queryFn: () => ctx.rest(base), refetchInterval: 2000, notifyOnChangeProps: ['data', 'error', 'dataUpdatedAt'] })
  const space = detail.data
  const [sheet, setSheet] = useState(null)
  const [confirmation, setConfirmation] = useState(null)
  const [reload, setReload] = useState(0)
  const [crash, setCrash] = useState(null)
  const [ignoredCrashRev, setIgnoredCrashRev] = useState(null)
  const [write, setWrite] = useState(null)
  const [announcement, setAnnouncement] = useState('')
  const [actionError, setActionError] = useState('')
  const [refreshPending, setRefreshPending] = useState(false)
  const [ready, setReady] = useState(false)
  const refreshLock = useRef(false)
  const actionLock = useRef(false)
  const content = useRef(null)
  const overflow = useRef(null)
  const confirmationTrigger = useRef(null)
  const controller = useRef(null)
  const cursor = useRef(0)
  const seenRun = useRef(null)
  const grantsKey = JSON.stringify(space?.grants || [])
  const hasData = space?.grants?.some(grant => grant.capability === 'data' && grant.status === 'granted') === true
  const building = !space || space.status === 'building' || !space.head_rev
  const archived = space?.status === 'archived'
  const remoteCrash = space?.attention?.kind === 'crashed' && ignoredCrashRev !== space?.head_rev
  const status = crash || remoteCrash ? 'crashed' : space ? spaceStatus(ignoredCrashRev === space.head_rev ? { ...space, attention: null } : space, true) : 'building'
  const lastRun = space?.recent_runs?.[0]
  const runKey = JSON.stringify(lastRun || null)

  useEffect(() => {
    let disposed = false
    ctx.rest(`${base}/opened`, { method: 'POST' }).catch(e => { if (!disposed) setActionError(`Could not mark this Space as opened. ${errorText(e)}`) })
    return () => { disposed = true }
  }, [ctx, base])

  useEffect(() => {
    if (building || archived || crash || remoteCrash || !content.current) return
    let disposed = false
    let errors = 0
    cursor.current = 0
    setReady(false)
    const [connectionId, profile] = ctx.queryScope ? JSON.parse(ctx.queryScope) : [host.state.connectionId.get(), host.state.profile.get()]
    const backend = { api: window.hermesDesktop?.api, connectionId, profile }
    const session = createSpaceSession({ backend, rest: (path, options) => ctx.rest(path, options), sid, container: content.current, mount: mountSpace,
      onWrite: event => !disposed && setWrite(event),
      onEvent: event => {
        if (disposed) return
        if (event.kind === 'reloaded') setReload(n => n + 1)
        if (event.kind === 'booted') setReady(true)
        if (event.kind === 'denied') setAnnouncement('A Space request was denied. Review Permissions for access details.')
        if (event.kind === 'log-overflow') setAnnouncement('Some diagnostic entries were dropped because the log limit was reached.')
        if (event.kind === 'error' && (event.fatal || event.phase === 'load' || /load|entry|boot/i.test(event.message || '') || ++errors >= 3)) setCrash(diagnosticText(`${event.message || event.error || 'Repeated runtime errors'}${event.location || event.filename ? `\nLocation: ${event.location || event.filename}` : ''}`))
      }
    })
    controller.current = session
    session.ready.then(() => { if (!disposed) setReady(true) }).catch(e => { if (!disposed) setCrash(diagnosticText(errorText(e))) })
    return () => {
      disposed = true
      setReady(false)
      session.postEvent('session.closed', { reason: 'Space view closed or reloaded' })
      session.destroy().catch(e => host.notifyError(e, 'A Space session could not be closed after retries.'))
      if (controller.current === session) controller.current = null
    }
  }, [ctx, sid, space?.head_rev, grantsKey, building, archived, crash, remoteCrash, reload])

  const changes = useQuery({ queryKey: ['living-spaces', ctx.queryScope || null, sid, 'changes', space?.head_rev, grantsKey, reload], queryFn: () => ctx.rest(`${base}/changes?since=${cursor.current}`), enabled: hasData && ready && !building && !archived && !crash, refetchInterval: 1500 })
  useEffect(() => {
    if (!hasData || !ready || !changes.data || !controller.current) return
    const page = advanceCursor(cursor.current, changes.data)
    if (page.changes.length) { controller.current.postEvent('data.changed', page); cursor.current = page.seq }
  }, [hasData, ready, changes.data, changes.dataUpdatedAt])
  useEffect(() => {
    if (!lastRun) return
    if (ready) controller.current?.postEvent('run.updated', lastRun)
    if (seenRun.current && seenRun.current !== runKey && !inFlight(lastRun.status)) setAnnouncement(lastRun.status === 'succeeded' ? `Refresh succeeded: ${runResult(lastRun)}` : `Refresh ${lastRun.status}: ${runResult(lastRun)}`)
    seenRun.current = runKey
  }, [runKey, ready])
  useEffect(() => { if (crash && space?.head_rev) { setCrash(null) } }, [space?.head_rev])

  async function refresh() {
    if (refreshLock.current || refreshPending || status === 'updating' || inFlight(lastRun?.status) || refreshReason(space)) return
    refreshLock.current = true
    setRefreshPending(true); setActionError(''); setAnnouncement('Refreshing…')
    try {
      const run = await ctx.rest(`${base}/refresh`, { method: 'POST' })
      if (run?.kind === 'cron') setAnnouncement('Refresh started in Hermes')
      else {
        controller.current?.postEvent('run.updated', run)
        if (!inFlight(run.status)) setAnnouncement(`Refresh ${run.status}: ${runResult(run)}`)
      }
      await detail.refetch()
    } catch (e) { setActionError(errorText(e)); setAnnouncement('Refresh failed') }
    finally { refreshLock.current = false; setRefreshPending(false) }
  }
  async function act(path, body) {
    if (actionLock.current) return
    actionLock.current = true
    setActionError('')
    try { await ctx.rest(`${base}/${path}`, { method: 'POST', ...(body ? { body } : {}) }); await detail.refetch() }
    catch (e) { setActionError(errorText(e)) }
    finally { actionLock.current = false }
  }
  if (!space) return <div className="ls-page">{detail.error ? <ErrorState title="This Space could not be opened" description={errorText(detail.error)}><Action onClick={() => detail.refetch()}>Try again</Action><Action onClick={() => host.navigate('/spaces')}>Spaces</Action></ErrorState> : <Skeleton style={{ height: 400 }} />}</div>
  const upkeep = space.upkeep
  const busy = refreshPending || inFlight(lastRun?.status) || status === 'updating'
  const reason = refreshReason(space)
  const opener = () => document.activeElement?.getAttribute('role') === 'menuitem' ? overflow.current : document.activeElement
  const openSheet = (kind, tab) => setSheet({ kind, tab, returnFocus: opener() })
  const openHistory = tab => openSheet('history', tab || 'runs')
  const askConfirmation = kind => { confirmationTrigger.current = opener(); setConfirmation(kind) }
  const crashMessage = diagnosticText(crash || space.attention?.message || 'The Space hit repeated runtime errors.')
  return <div className="ls-frame" data-testid="space-view"><header className="ls-framebar"><Action icon="chevron-left" onClick={() => host.navigate('/spaces')}>Spaces</Action><div className="ls-identity"><SpaceTile space={space} small /><div><div className="ls-name-row"><h1>{space.name}</h1><StatusPill status={status} /></div><div className="ls-frame-meta"><OwnerChip owner={space.owner} /><span> · <Freshness facts={headerFacts(space)} /></span></div></div></div>
    <div className="ls-frame-actions"><SaveStatus write={write} announcement={announcement} />
      {!building && <div className="ls-upkeep-action"><Action icon="watch" onClick={() => openSheet('upkeep')}>{!upkeep ? 'Upkeep: none' : upkeep.missing ? 'Upkeep: job missing' : upkeep.enabled === true ? 'Upkeep: on' : upkeep.enabled === false ? 'Upkeep: paused' : 'Upkeep'}</Action></div>}
      <span className="ls-wide-only"><Action onClick={() => openHistory()}>History</Action></span>
      {!building && <><Action onClick={() => openSheet('permissions')}>Permissions</Action><DisabledReason reason={reason}><Action primary icon="refresh" aria-busy={busy} aria-disabled={!!reason || busy} title={reason || undefined} onClick={refresh}>{busy ? 'Refreshing…' : 'Refresh now'}</Action></DisabledReason></>}
      <DropdownMenu><DropdownMenuTrigger asChild><Action ref={overflow} aria-label="More Space actions" icon="ellipsis" /></DropdownMenuTrigger><DropdownMenuContent align="end"><div className="ls-compact-only"><DropdownMenuItem onSelect={() => openHistory()}>History</DropdownMenuItem></div>{!building && <><div className="ls-upkeep-compact"><DropdownMenuItem onSelect={() => openSheet('upkeep')}>Upkeep</DropdownMenuItem></div><DropdownMenuSeparator /><DropdownMenuItem onSelect={() => act('pin', { pinned: !space.pinned })}>{space.pinned ? 'Unpin Space' : 'Pin Space'}</DropdownMenuItem><DropdownMenuItem onSelect={() => archived ? act('unarchive') : askConfirmation('archive')}>{archived ? 'Restore Space' : 'Archive Space…'}</DropdownMenuItem>{archived && <DropdownMenuItem onSelect={() => askConfirmation('delete')}>Delete…</DropdownMenuItem>}</>}</DropdownMenuContent></DropdownMenu>
    </div></header>
    {actionError && <Banner kind="failed" title={actionError} />}
    {detail.error && <Banner kind="failed" title="Space status could not be refreshed. You're seeing the last loaded state." actions={<Action onClick={() => detail.refetch()}>Try again</Action>}>{errorText(detail.error)}</Banner>}
    {changes.error && <Banner kind="failed" title="Live record updates are delayed. Your displayed data may be out of date." actions={<Action onClick={() => changes.refetch()}>Retry live updates</Action>}>{errorText(changes.error)}</Banner>}
    <WriteBanner write={write} setWrite={setWrite} onDismiss={() => controller.current?.dismissWrite(write.token)} onCompare={() => openSheet('compare')} onUpdated={() => { controller.current?.dismissWrite(write.token); setReload(n => n + 1) }} />
    {archived ? <Banner title="This Space is archived. Future upkeep is paused." actions={<><Action onClick={() => act('unarchive')}>Restore Space</Action><Action danger onClick={() => askConfirmation('delete')}>Delete…</Action></>}>Restore it to open the canvas, then resume upkeep separately. Already-running work may finish. Delete removes it and its data permanently.</Banner> : status === 'failed' ? <Banner kind="failed" title={`Refresh failed${space.freshness?.last_attempt_at != null ? ` at ${absolute(space.freshness.last_attempt_at)}` : ''}. ${space.freshness?.last_success_at != null ? `You're seeing data from ${absolute(space.freshness.last_success_at)}.` : 'No successful update yet.'}`} actions={<><Action onClick={() => openHistory()}>View run details</Action><Action onClick={refresh}>Try again</Action></>}>{lastRun?.error || space.attention?.message || 'The source did not respond.'} Your notes and statuses are unchanged. {space.freshness?.next_run_at ? `Next automatic try ${absolute(space.freshness.next_run_at)}.` : 'No automatic try is scheduled.'}</Banner> : status === 'blocked' ? <Banner kind="blocked" title={`Refresh is blocked: ${space.attention?.message || reason || 'Review Permissions'}`} actions={<Action onClick={() => openSheet('permissions')}>Review permissions</Action>}>The Space still opens and your data is safe. <CopyPrompt text={`${space.owner}, ${space.name} is blocked. Please review its last run and help me restore upkeep.`} /></Banner> : null}
    <section className="ls-content" aria-label="Space content"><div className={`ls-sandbox${status === 'failed' ? ' ls-stale' : ''}`}>
      {building ? <div className="ls-building"><p role="status">{space.owner} is building the first version. This opens automatically when it's ready.</p><Skeleton style={{ height: 100 }} /><Skeleton style={{ height: 180 }} /></div> : status === 'crashed' ? <div className="ls-crash"><ErrorState title={`${space.name} stopped working`} description="The Space hit an error and was stopped. Your records are safe and weren't changed by the crash." /><pre className="ls-diagnostic">{`Revision ${space.head_rev}\n${crashMessage}\nLogged to this Space only. Common credential values redacted.`}</pre><div className="ls-actions"><Action primary onClick={() => { setCrash(null); setIgnoredCrashRev(space.head_rev); setReload(n => n + 1) }}>Reload Space</Action><Action onClick={() => openHistory('revisions')}>Restore revision…</Action></div><CopyPrompt text={`${space.owner}, ${space.name} crashed. Please read its error log and fix it.`} /><p className="ls-secondary">Repairs happen in chat. {space.owner} can read this error and apply a new revision.</p></div> : archived ? <div className="ls-building"><p>Restore Space to open its content. Your records and revisions are kept.</p></div> : <div ref={content} className="ls-mount" data-testid="space-host" />}
    </div></section>
    {sheet?.kind === 'permissions' && <PermissionsSheet returnFocus={sheet.returnFocus} ctx={ctx} space={space} onClose={() => setSheet(null)} onChanged={() => detail.refetch()} />}
    {sheet?.kind === 'history' && <HistorySheet returnFocus={sheet.returnFocus} ctx={ctx} space={space} initialTab={sheet.tab} onClose={() => setSheet(null)} onChanged={() => detail.refetch()} />}
    {sheet?.kind === 'upkeep' && <UpkeepSheet returnFocus={sheet.returnFocus} ctx={ctx} space={space} onClose={() => setSheet(null)} onChanged={() => detail.refetch()} />}
    {sheet?.kind === 'compare' && write && <Drawer returnFocus={sheet.returnFocus} title="Compare record changes" description="Your submitted change and the latest stored record" onClose={() => setSheet(null)}><div className="ls-compare"><h2>Your change</h2><pre className="ls-diagnostic">{JSON.stringify(write.args, null, 2)}</pre><h2>Updated record</h2><pre className="ls-diagnostic">{JSON.stringify(write.reply?.error?.current, null, 2)}</pre></div></Drawer>}
    {confirmation && <DecisionDialog returnFocus={confirmationTrigger.current} danger title={confirmation === 'delete' ? `Delete ${space.name}?` : `Archive ${space.name}?`} description={confirmation === 'delete' ? "Delete removes this Space, all its records and revisions permanently and stops future upkeep. Already-running work may finish. Exported copies aren't recalled." : 'Archiving pauses future upkeep. Already-running work may finish. Your records and revisions are kept. Restoring this Space does not resume upkeep.'} confirmLabel={confirmation === 'delete' ? 'Delete Space' : 'Archive Space'} onClose={() => setConfirmation(null)} onConfirm={async () => { if (confirmation === 'delete') { await ctx.rest(`${base}?confirm=${encodeURIComponent(sid)}`, { method: 'DELETE' }); host.navigate('/spaces') } else { await ctx.rest(`${base}/archive`, { method: 'POST' }); await detail.refetch() } }} />}
  </div>
}
