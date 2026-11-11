import { Badge, ErrorState, Skeleton, useQuery } from '@hermes/plugin-sdk'
import { useRef, useState } from 'react'
import { Action, Banner, DecisionDialog, Drawer, Icon, OwnerChip, StatusPill, Time } from './components.jsx'
import { CATCH_UP, errorText, spacePath } from './model.mjs'

const NET_DESCRIPTION = "This Space can load content from and send data to the internet. It can't reach your Hermes app, your files or other Spaces."
const NET_OFF_DESCRIPTION = "This Space can't load content from or send data to the internet through Internet access."
const NET_OFF_NOTE = "Off is not a complete block. A browser feature called WebRTC can still send data this Space can read. It still can't reach Hermes, your credentials, your files or other Spaces."
const CAPABILITIES = {
  data: { name: 'Own data', icon: 'folder', scope: "This Space's records only. Cannot see other Spaces.", purpose: 'Store your records, notes and statuses.', leaves: 'This grant stays on device. Space-readable data can leave through Internet access or the WebRTC limit when Internet access is off.' },
  refresh: { name: 'Refresh', icon: 'refresh', purpose: 'Keep public-source records current.', leaves: 'Yes · requests the approved public sources through Hermes.' },
  logs: { name: 'Diagnostics', icon: 'info', scope: 'Error logs from this Space, secrets redacted. Only the latest 2,000 log entries are retained.', purpose: 'Let the owner see crashes and repair them.', leaves: 'No ordinary network access. The owner can read these logs in chat.' }
}
const FUTURE = ['Approved sites', 'Camera', 'Microphone', 'Location', 'Hermes tools (per tool)', 'Files and folders', 'Cross-Space access', 'Agent requests']
export function WebRTCNote() {
  return <div className="ls-disclosure" data-testid="webrtc-note"><strong><Icon name="info" /> Before you approve anything</strong><p>{NET_OFF_NOTE}</p></div>
}
function InternetAccess({ grant, onDecide, busy }) {
  const enabled = grant.status === 'granted'
  return <section className="ls-section"><article className="ls-grant" data-testid="internet-access">
    <div className="ls-row-top"><strong>Internet access</strong><Action role="switch" aria-label="Internet access" aria-checked={enabled} aria-describedby="ls-net-description" disabled={busy} onClick={() => onDecide(grant, enabled ? 'revoke' : 'grant')}>{enabled ? 'On' : 'Off'}</Action></div>
    <p id="ls-net-description" className="ls-secondary">{enabled ? NET_DESCRIPTION : NET_OFF_DESCRIPTION}</p>
    {grant.status === 'requested' && <div className="ls-actions"><Action primary disabled={busy} onClick={() => onDecide(grant, 'grant')}>Approve</Action><Action disabled={busy} onClick={() => onDecide(grant, 'deny')}>Deny</Action></div>}
    {!enabled && <WebRTCNote />}
  </article></section>
}
export function GrantCard({ grant, onDecide, busy }) {
  const model = CAPABILITIES[grant.capability]
  if (!model) return null
  const scope = grant.requested_scope || grant.scope || {}
  const scopeText = grant.capability === 'refresh' ? `Host-owned public-source handler. Approved hosts: ${(scope.hosts || []).join(', ') || 'No hosts requested'}.` : model.scope
  return <article className={`ls-grant${grant.status === 'requested' ? ' ls-pending' : ''}`}><div className="ls-row-top"><strong><Icon name={model.icon} />{model.name}</strong><StatusPill status={grant.status} /></div>
    <dl className="ls-facts"><div><dt>Scope</dt><dd>{scopeText}</dd></div><div><dt>Purpose</dt><dd>{grant.purpose || model.purpose}</dd></div><div><dt>Data leaves device</dt><dd>{model.leaves}</dd></div><div><dt>Access</dt><dd>Continuing</dd></div></dl>
    <div className="ls-actions">{grant.status === 'granted' ? <Action danger disabled={busy} onClick={() => onDecide(grant, 'revoke')}>Revoke</Action> : grant.status === 'requested' ? <><Action primary disabled={busy} onClick={() => onDecide(grant, 'grant')}>Approve</Action><Action disabled={busy} onClick={() => onDecide(grant, 'deny')}>Deny</Action></> : grant.capability === 'refresh' ? <><p className="ls-secondary">Refresh permission {grant.status}. Approving Refresh leaves scheduled upkeep paused until you resume it.</p><Action primary disabled={busy} onClick={() => onDecide(grant, 'grant')}>Approve</Action></> : <p className="ls-secondary">{grant.status === 'denied' ? `Denied. The Space shows “${model.name} isn't available” instead of prompting again.` : `${model.name} was revoked. Ask in chat to request access again.`}</p>}</div>
  </article>
}
export function PermissionsContent({ space, grants, audit = [], schedule, onDecide, onSchedule, busy = false }) {
  const net = grants.find(g => g.capability === 'net')
  const pending = grants.filter(g => g.capability !== 'net' && g.status === 'requested')
  const settled = grants.filter(g => g.capability !== 'net' && g.status !== 'requested')
  return <>
    {net && <InternetAccess grant={net} onDecide={onDecide} busy={busy} />}
    <section className="ls-section"><h2 className="ls-section-title">Granted to {space.name}</h2>{settled.map(g => <GrantCard key={g.capability} grant={g} onDecide={onDecide} busy={busy} />)}{!settled.length && <p>No grants approved yet.</p>}</section>
    <section className="ls-section"><h2 className="ls-section-title">Waiting for your decision</h2>{pending.map(g => <GrantCard key={g.capability} grant={g} onDecide={onDecide} busy={busy} />)}
      {schedule?.status === 'requested' && <article className="ls-grant ls-pending"><div className="ls-row-top"><strong><Icon name="watch" />Scheduled upkeep</strong><StatusPill status="requested" /></div><dl className="ls-facts"><div><dt>Cadence</dt><dd>{schedule.cadence}</dd></div><div><dt>Timezone</dt><dd>{schedule.timezone}</dd></div><div><dt>Purpose</dt><dd>{schedule.purpose}</dd></div><div><dt>Owner</dt><dd>{space.owner}</dd></div><div><dt>Cost</dt><dd>No model calls</dd></div></dl><p>{CATCH_UP}</p><div className="ls-actions"><Action primary disabled={busy} onClick={() => onSchedule('approve')}>Approve</Action><Action disabled={busy} onClick={() => onSchedule('deny')}>Deny</Action></div></article>}
      {!pending.length && schedule?.status !== 'requested' && <p className="ls-secondary">Nothing waiting for your decision.</p>}
    </section>
    <section className="ls-section" data-testid="release-two"><h2 className="ls-section-title">Coming in release 2 — not available yet</h2>{FUTURE.map(name => <div className="ls-grant ls-future" key={name}><div className="ls-row-top"><strong>{name}</strong><Badge variant="outline">Not available yet</Badge></div></div>)}<p className="ls-secondary">Camera, microphone and location will start off and also follow Hermes and macOS permission prompts. Release 2 will revisit what Spaces can read before tool and file access is offered.</p></section>
    <section className="ls-section"><h2 className="ls-section-title">Owner</h2><OwnerChip owner={space.owner} /><h2 className="ls-section-title">Audit</h2>{audit.length ? <ul className="ls-audit">{audit.slice(0, 10).map(a => <li key={a.id}><Time at={a.at} /> · {a.actor} · {a.action} {a.capability || ''} · {a.outcome}</li>)}</ul> : <p className="ls-secondary">No permission decisions recorded.</p>}</section>
  </>
}
export function PermissionsSheet({ ctx, space, onClose, onChanged, returnFocus }) {
  const base = spacePath(space.id)
  const query = useQuery({ queryKey: ['living-spaces', ctx.queryScope || null, space.id, 'grants'], queryFn: () => ctx.rest(`${base}/grants`), refetchInterval: 2000 })
  const schedule = useQuery({ queryKey: ['living-spaces', ctx.queryScope || null, space.id, 'schedule'], queryFn: () => ctx.rest(`${base}/schedule`), refetchInterval: 2000 })
  const [revoke, setRevoke] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const lock = useRef(false)
  async function decide(grant, decision) {
    if (decision === 'revoke' && grant.capability !== 'net') { setRevoke(grant); return }
    await change(`${base}/grants/${grant.capability}`, { decision, ...(decision === 'grant' ? { requested_scope: grant.requested_scope ?? grant.scope ?? {} } : {}) })
  }
  async function change(path, body) {
    if (lock.current) return
    lock.current = true
    setBusy(true); setError('')
    try { await ctx.rest(path, { method: 'POST', body }); await Promise.all([query.refetch(), schedule.refetch(), onChanged()]) }
    catch (e) {
      if ((e?.error || e?.body?.error || e)?.code === 'conflict') {
        setError('Permission request changed. Review the new request before approving.')
      } else setError(`${errorText(e)} Review the current request before trying again.`)
      await Promise.all([query.refetch(), schedule.refetch()])
    }
    finally { lock.current = false; setBusy(false) }
  }
  return <><Drawer title={`Permissions · ${space.name}`} description="Review this Space's access and schedule requests." onClose={onClose} returnFocus={returnFocus}>
    {error && <Banner kind="failed" title={error} />}
    {query.error || schedule.error ? <ErrorState title="Permissions could not be loaded" description={errorText(query.error || schedule.error)}><Action onClick={() => { query.refetch(); schedule.refetch() }}>Try again</Action></ErrorState> : query.isLoading ? <Skeleton style={{ height: 180 }} /> : <PermissionsContent space={space} grants={query.data?.grants || []} audit={query.data?.audit || []} schedule={schedule.data} onDecide={decide} onSchedule={decision => change(`${base}/schedule`, { decision })} busy={busy} />}
  </Drawer>{revoke && <DecisionDialog danger title={`Revoke ${CAPABILITIES[revoke.capability].name} for ${space.name}?`} description={revoke.capability === 'refresh' ? "Scheduled upkeep pauses and manual refreshes stop. Approve Refresh in Permissions, then resume upkeep to restart scheduled refreshes. Data already delivered to the Space can't be recalled, and completed requests can't be undone." : `The Space loses ${CAPABILITIES[revoke.capability].name.toLowerCase()} access. Data already delivered to the Space can't be recalled, and completed requests can't be undone.`} cancelLabel="Keep access" confirmLabel="Revoke" onClose={() => setRevoke(null)} onConfirm={async () => { await ctx.rest(`${base}/grants/${revoke.capability}`, { method: 'POST', body: { decision: 'revoke' } }); await query.refetch(); await onChanged() }} />}</>
}
