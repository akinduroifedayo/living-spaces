import { Badge, EmptyState, ErrorState, Skeleton, Tabs, TabsList, TabsTrigger, useQuery } from '@hermes/plugin-sdk'
import { useEffect, useRef, useState } from 'react'
import { Action, Banner, DecisionDialog, Drawer, Icon, StatusPill, Time, absolute } from './components.jsx'
import { readDismissed, writeDismissed } from './dismissal.mjs'
import { dispatchText, errorText, recoveryCompatibility, restoreCopy, revisionCompatibility, runResult, spacePath, storageNotice } from './model.mjs'

export function RunRow({ run }) {
  const duration = run.ended_at != null && run.started_at != null ? `${Math.max(0, run.ended_at - run.started_at).toFixed(1)} s` : run.status === 'queued' ? 'Not started' : run.status === 'running' ? 'In progress' : 'No duration reported'
  return <article className="ls-row"><div className="ls-row-top"><strong><Icon name={run.status === 'succeeded' ? 'check' : ['failed', 'blocked'].includes(run.status) ? 'warning' : 'watch'} />{run.status === 'succeeded' ? 'Refresh succeeded' : `Refresh ${run.status}`}</strong><StatusPill status={run.status} /></div><p className="ls-secondary">{run.trigger} · <Time at={run.started_at ?? run.queued_at} /> · {duration}</p><p>{runResult(run)}</p>{run.detail?.dispatch && <p className="ls-secondary">{dispatchText(run.detail.dispatch, absolute)}</p>}</article>
}
export function RevisionRow({ revision, space, onRestore }) {
  const compatibility = revisionCompatibility(space, revision)
  return <article className="ls-row"><div className="ls-row-top"><strong>Revision {revision.rev}</strong>{revision.rev === space.head_rev ? <Badge variant="outline">Current</Badge> : compatibility !== 'incompatible' && <Action onClick={() => onRestore(revision.rev)}>Restore…</Action>}</div><p className="ls-secondary"><Time at={revision.created_at} /></p><p>{revision.author} · {revision.summary}</p><p className="ls-secondary">Compatibility: {compatibility === 'incompatible' ? `incompatible. Current data version ${space.data_version}; target data version ${revision.manifest.data.version}. Cross-version code restore is not supported.` : compatibility === 'compatible' ? `compatible with current data version ${space.data_version}.` : 'unknown. The backend will check data versions before restoring code.'}</p></article>
}
export function RecoveryPointRow({ point, space }) {
  const compatibility = recoveryCompatibility(space, point)
  return <article className="ls-row" data-testid={`recovery-point-${point.id}`}><strong>Recovery point {point.id}</strong><p>{point.reason}</p><p className="ls-secondary"><Time at={point.created_at} /> · Code revision {point.head_rev}</p><p>Compatibility: {compatibility}. {compatibility === 'incompatible' ? `Current data version ${space.data_version}; point data version ${point.data_version}. Cross-version restore is not supported.` : compatibility === 'compatible' ? `Same data version ${space.data_version}. Use code revision history below for code-only restore.` : 'Data-version compatibility cannot be established.'} Data restore is not supported here. Migration undo and data downgrades are not supported. Current records, notes and statuses stay as they are.</p></article>
}
export function HistorySheet({ ctx, scopeKey = null, space, onClose, onChanged, initialTab = 'runs', returnFocus }) {
  const [tab, setTab] = useState(initialTab)
  const [restore, setRestore] = useState(null)
  const base = spacePath(space.id)
  const runs = useQuery({ queryKey: ['living-spaces', scopeKey, space.id, 'runs'], queryFn: () => ctx.rest(`${base}/runs`), refetchInterval: 2000 })
  const revisions = useQuery({ queryKey: ['living-spaces', scopeKey, space.id, 'revisions'], queryFn: () => ctx.rest(`${base}/revisions`), refetchInterval: 2000 })
  const points = useQuery({ queryKey: ['living-spaces', scopeKey, space.id, 'recovery-points'], queryFn: () => ctx.rest(`${base}/recovery-points`), refetchInterval: 2000 })
  const query = tab === 'runs' ? runs : revisions
  const restoreCompatibility = revisionCompatibility(space, revisions.data?.find(row => row.rev === restore))
  return <><Drawer title="History & revisions" description={`History and code revisions for ${space.name}`} onClose={onClose} returnFocus={returnFocus}>
    <StorageSection key={`${scopeKey}:${space.id}`} ctx={ctx} space={space} onChanged={onChanged} />
    <Tabs value={tab} onValueChange={setTab} className="ls-tabs"><TabsList aria-label="History & revisions"><TabsTrigger id="ls-runs-tab" aria-controls="ls-runs-panel" value="runs">Run history</TabsTrigger><TabsTrigger id="ls-revisions-tab" aria-controls="ls-revisions-panel" value="revisions">Revisions</TabsTrigger></TabsList></Tabs>
    <div role="tabpanel" tabIndex={0} id={`ls-${tab === 'runs' ? 'runs' : 'revisions'}-panel`} aria-labelledby={`ls-${tab === 'runs' ? 'runs' : 'revisions'}-tab`}>
      {tab === 'revisions' && <><p className="ls-secondary">Restoring code does not rewind records. Your records, notes and statuses stay as they are now. Migration undo and data downgrades are not supported.</p><section aria-label="Recovery points"><h3>Recovery points</h3>{points.error ? <ErrorState title="Recovery points could not be loaded" description={errorText(points.error)}><Action onClick={() => points.refetch()}>Try again</Action></ErrorState> : points.isLoading ? <Skeleton style={{ height: 80 }} /> : !points.data?.length ? <p className="ls-secondary">No recovery points recorded.</p> : points.data.map(point => <RecoveryPointRow key={point.id} point={point} space={space} />)}</section><h3>Code revisions</h3></>}
      {query.error ? <ErrorState title="History could not be loaded" description={errorText(query.error)}><Action onClick={() => query.refetch()}>Try again</Action></ErrorState> : query.isLoading ? <Skeleton style={{ height: 180 }} /> : !query.data?.length ? <EmptyState title={tab === 'runs' ? 'No refresh runs yet.' : 'No revisions yet.'} /> : query.data.map(row => tab === 'runs' ? <RunRow key={row.id} run={row} /> : <RevisionRow key={row.rev} revision={row} space={space} onRestore={setRestore} />)}
    </div>
  </Drawer>{restore != null && restoreCompatibility !== 'incompatible' && <DecisionDialog danger title={`Restore revision ${restore}?`} description={restoreCopy(space, restore)} confirmLabel="Restore as new revision" onClose={() => setRestore(null)} onConfirm={async () => { await ctx.rest(`${base}/revisions/${restore}/restore`, { method: 'POST' }); await revisions.refetch(); await onChanged() }} />}</>
}

// The storage warning for the most-full resource. With a storageKey it can be hidden until a warned
// resource is new or changes percentage; without one (inside the storage section) it only informs.
export function StorageNotice({ storage, onReview, storageKey }) {
  const [stored, setStored] = useState(() => ({ storageKey, value: storageKey ? readDismissed(storageKey) : null }))
  const hidden = !storageKey ? null : stored.storageKey === storageKey ? stored.value : readDismissed(storageKey)
  const notice = storageNotice(storage, hidden)
  if (!notice) return null
  const dismiss = () => {
    writeDismissed(storageKey, notice.key)
    setStored({ storageKey, value: notice.key })
  }
  return <Banner kind="storage" title={notice.title} actions={(onReview || storageKey) && <>
    {onReview && <Action onClick={onReview}>Review</Action>}
    {storageKey && <Action onClick={dismiss}>Hide until it changes</Action>}
  </>}><span className="ls-oneline" title={notice.line}>{notice.line}</span><div className="ls-meter" aria-hidden="true"><i style={{ width: `${notice.pct}%` }} /></div></Banner>
}

export function StorageSection({ ctx, space, onChanged }) {
  const [categories, setCategories] = useState(['revisions', 'logs', 'runs'])
  const [before, setBefore] = useState(() => new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10))
  const [proposal, setProposal] = useState(null)
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [receipt, setReceipt] = useState(null)
  const lifetime = useRef(null)
  useEffect(() => {
    const current = { active: true }
    lifetime.current = current
    return () => { current.active = false }
  }, [ctx, space.id])
  const storage = space.storage
  if (!storage) return null
  const base = spacePath(space.id)
  const reset = () => { setProposal(null); setReceipt(null); setError('') }
  async function preview() {
    if (busy) return
    const request = lifetime.current
    setBusy(true); reset()
    try {
      const result = await ctx.rest(`${base}/retention/propose`, { method: 'POST', body: { scope: { categories, before: new Date(`${before}T00:00:00Z`).getTime() / 1000 } } })
      if (request?.active) setProposal(result)
    } catch (failure) { if (request?.active) setError(errorText(failure)) }
    finally { if (request?.active) setBusy(false) }
  }
  return <section aria-label="Storage"><h3>Storage</h3><StorageNotice storage={storage} />
    <ul>{Object.entries(storage.categories).map(([name, row]) => <li key={name}>{name}: {row.count} · {row.bytes} bytes{row.fields != null && ` · ${row.fields} source fields`}{row.source_details != null && ` · ${row.source_details} source run details`}</li>)}</ul>
    <p className="ls-secondary">{storage.bytes_basis} Native history is native-owned, excluded from these counts and never deleted here. No automatic cleanup is scheduled.</p>
    <details><summary>Propose cleanup</summary><p>Choose categories and a cutoff. Preview lists the exact items to remove and protected work. This does not delete anything.</p>
      <fieldset disabled={busy}><legend>Categories to review</legend>{['revisions', 'records', 'logs', 'runs'].map(name => <label key={name}><input type="checkbox" checked={categories.includes(name)} onChange={event => { reset(); setCategories(event.target.checked ? [...categories, name] : categories.filter(value => value !== name)) }} />{name} </label>)}
        <label>Older than UTC date <input type="date" value={before} onChange={event => { reset(); setBefore(event.target.value) }} /></label>
      </fieldset><Action disabled={busy || !categories.length || !before} aria-busy={busy} onClick={preview}>Preview cleanup</Action>
      {error && <p role="alert">{error}</p>}{receipt && <p role="status">Cleanup completed for {receipt.proposal_id}. Audit receipt {receipt.audit_id}.</p>}
      {proposal && <div><p>Proposal <code style={{ overflowWrap: 'anywhere' }}>{proposal.id}</code></p>
        {proposal.truncated.length > 0 && <p>Bounded batch. More items remain in {proposal.truncated.join(', ')}. Review a new proposal after this batch.</p>}
        {['remove', 'protected'].map(kind => <div key={kind}><h4>{kind === 'remove' ? 'Would remove' : 'Protected, kept'}</h4>{Object.entries(proposal[kind]).map(([name, rows]) => <details key={name}><summary>{name}: {rows.length}</summary><ul>{rows.map((row, index) => <li key={index} style={{ overflowWrap: 'anywhere' }}>{row.collection ? `${row.collection}/` : ''}{row.id ?? row.rev ?? row.sha}{row.reason ? ` · ${row.reason}` : ''}</li>)}</ul></details>)}</div>)}
        <Action danger disabled={!Object.values(proposal.remove).some(rows => rows.length)} onClick={() => setConfirming(true)}>Review deletion…</Action>
      </div>}
    </details>
    {confirming && proposal && <DecisionDialog danger title="Execute retention proposal?" description={`Permanently delete only the listed items in ${space.name} for proposal ${proposal.id}. Protected work and native history stay. Any changed state requires a new preview.`} confirmLabel={<span style={{ overflowWrap: 'anywhere', whiteSpace: 'normal' }}>{`Delete ${proposal.id}`}</span>} onClose={() => setConfirming(false)} onConfirm={async () => {
      const request = lifetime.current
      const result = await ctx.rest(`${base}/retention/execute`, { method: 'POST', body: { scope: proposal.scope, proposal_id: proposal.id, confirm: proposal.confirmation } })
      if (!request?.active) return
      setReceipt(result); setProposal(null)
      await onChanged()
    }} />}
  </section>
}
