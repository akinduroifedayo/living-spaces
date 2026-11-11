import { Badge, EmptyState, ErrorState, Skeleton, Tabs, TabsList, TabsTrigger, useQuery } from '@hermes/plugin-sdk'
import { useState } from 'react'
import { Action, DecisionDialog, Drawer, Icon, StatusPill, Time, absolute } from './components.jsx'
import { dispatchText, errorText, restoreCopy, runResult, spacePath } from './model.mjs'

export function RunRow({ run }) {
  const duration = run.ended_at != null && run.started_at != null ? `${Math.max(0, run.ended_at - run.started_at).toFixed(1)} s` : run.status === 'queued' ? 'Not started' : run.status === 'running' ? 'In progress' : 'No duration reported'
  return <article className="ls-row"><div className="ls-row-top"><strong><Icon name={run.status === 'succeeded' ? 'check' : ['failed', 'blocked'].includes(run.status) ? 'warning' : 'watch'} />{run.status === 'succeeded' ? 'Refresh succeeded' : `Refresh ${run.status}`}</strong><StatusPill status={run.status} /></div><p className="ls-secondary">{run.trigger} · <Time at={run.started_at ?? run.queued_at} /> · {duration}</p><p>{runResult(run)}</p>{run.detail?.dispatch && <p className="ls-secondary">{dispatchText(run.detail.dispatch, absolute)}</p>}</article>
}
export function RevisionRow({ revision, space, onRestore }) {
  return <article className="ls-row"><div className="ls-row-top"><strong>Revision {revision.rev}</strong>{revision.rev === space.head_rev ? <Badge variant="outline">Current</Badge> : <Action onClick={() => onRestore(revision.rev)}>Restore…</Action>}</div><p className="ls-secondary"><Time at={revision.created_at} /></p><p>{revision.author} · {revision.summary}</p></article>
}
export function HistorySheet({ ctx, space, onClose, onChanged, initialTab = 'runs', returnFocus }) {
  const [tab, setTab] = useState(initialTab)
  const [restore, setRestore] = useState(null)
  const base = spacePath(space.id)
  const runs = useQuery({ queryKey: ['living-spaces', ctx.queryScope || null, space.id, 'runs'], queryFn: () => ctx.rest(`${base}/runs`), refetchInterval: 2000 })
  const revisions = useQuery({ queryKey: ['living-spaces', ctx.queryScope || null, space.id, 'revisions'], queryFn: () => ctx.rest(`${base}/revisions`), refetchInterval: 2000 })
  const query = tab === 'runs' ? runs : revisions
  return <><Drawer title="History & revisions" description={`History and code revisions for ${space.name}`} onClose={onClose} returnFocus={returnFocus}>
    <Tabs value={tab} onValueChange={setTab} className="ls-tabs"><TabsList aria-label="History & revisions"><TabsTrigger id="ls-runs-tab" aria-controls="ls-runs-panel" value="runs">Run history</TabsTrigger><TabsTrigger id="ls-revisions-tab" aria-controls="ls-revisions-panel" value="revisions">Revisions</TabsTrigger></TabsList></Tabs>
    <div role="tabpanel" tabIndex={0} id={`ls-${tab === 'runs' ? 'runs' : 'revisions'}-panel`} aria-labelledby={`ls-${tab === 'runs' ? 'runs' : 'revisions'}-tab`}>
      {tab === 'revisions' && <p className="ls-secondary">Restoring code does not rewind records. Your records, notes and statuses stay as they are now.</p>}
      {query.error ? <ErrorState title="History could not be loaded" description={errorText(query.error)}><Action onClick={() => query.refetch()}>Try again</Action></ErrorState> : query.isLoading ? <Skeleton style={{ height: 180 }} /> : !query.data?.length ? <EmptyState title={tab === 'runs' ? 'No refresh runs yet.' : 'No revisions yet.'} /> : query.data.map(row => tab === 'runs' ? <RunRow key={row.id} run={row} /> : <RevisionRow key={row.rev} revision={row} space={space} onRestore={setRestore} />)}
    </div>
  </Drawer>{restore != null && <DecisionDialog title={`Restore revision ${restore}?`} description={restoreCopy(space, restore)} confirmLabel="Restore as new revision" onClose={() => setRestore(null)} onConfirm={async () => { await ctx.rest(`${base}/revisions/${restore}/restore`, { method: 'POST' }); await revisions.refetch(); await onChanged() }} />}</>
}
