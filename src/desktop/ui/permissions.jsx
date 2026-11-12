import { ErrorState, Skeleton, useQuery } from '@hermes/plugin-sdk'
import { useRef, useState } from 'react'
import { Action, Banner, DecisionDialog, Drawer, Icon, OwnerChip, StatusPill, Time } from './components.jsx'
import { errorText, spacePath } from './model.mjs'

const NET_DESCRIPTION = "This Space can load content from and send data to the internet. It can't reach your Hermes app, your files or other Spaces."
const NET_OFF_DESCRIPTION = "This Space can't load content from or send data to the internet through Internet access."
const NET_OFF_NOTE = "Off is not a complete block. A browser feature called WebRTC can still send data this Space can read. It still can't reach Hermes, your credentials, your files or other Spaces."
const CAPABILITIES = {
  data: { name: 'Own data', icon: 'folder', scope: "This Space's records only. Cannot see other Spaces.", purpose: 'Store your records, notes and statuses.', leaves: 'This grant stays on device. Space-readable data can leave through Internet access or the WebRTC limit when Internet access is off.' },
  logs: { name: 'Diagnostics', icon: 'info', scope: 'Error logs from this Space, secrets redacted. Only the latest 2,000 log entries are retained.', purpose: 'Let the owner see crashes and repair them.', leaves: 'No ordinary network access. The owner can read these logs in chat.' }
}
export function WebRTCNote() {
  return <p className="ls-disclosure ls-secondary" id="ls-net-note" data-testid="webrtc-note"><Icon name="info" /> {NET_OFF_NOTE}</p>
}
function InternetAccess({ grant, owner, onDecide, busy, pending }) {
  const enabled = grant.status === 'granted'
  const requested = grant.status === 'requested'
  return <section className="ls-section"><article className="ls-grant ls-internet" data-testid="internet-access" aria-busy={busy}>
    <div className="ls-row-top"><strong id="ls-net-title">Internet access</strong><div className="ls-switch-value"><span aria-hidden="true">{enabled ? 'On' : 'Off'}</span><button type="button" className="ls-switch" role="switch" aria-labelledby="ls-net-title" aria-checked={enabled} aria-describedby={`ls-net-description${!enabled ? ' ls-net-note' : ''}`} aria-busy={busy} aria-disabled={busy || requested} onClick={() => !busy && !requested && onDecide(grant, enabled ? 'revoke' : 'grant')}><span className="ls-switch-track"><span className="ls-switch-thumb" /></span></button></div></div>
    <p id="ls-net-description" className="ls-secondary">{enabled ? NET_DESCRIPTION : NET_OFF_DESCRIPTION}</p>
    {!enabled && <WebRTCNote />}
    {busy && pending?.capability === 'net' && <p role="status">{pending.decision === 'grant' ? 'Turning on…' : pending.decision === 'revoke' ? 'Turning off…' : 'Denying request…'}</p>}
    {requested && <><p>{owner} is asking to turn this on.</p><div className="ls-actions"><Action primary aria-disabled={busy} onClick={() => !busy && onDecide(grant, 'grant')}>Approve</Action><Action aria-disabled={busy} onClick={() => !busy && onDecide(grant, 'deny')}>Deny</Action></div></>}
  </article></section>
}
export function GrantCard({ grant, onDecide, busy }) {
  const model = CAPABILITIES[grant.capability]
  if (!model) return null
  const scopeText = model.scope
  return <article className={`ls-grant${grant.status === 'requested' ? ' ls-pending' : ''}`}><div className="ls-row-top"><strong><Icon name={model.icon} />{model.name}</strong><StatusPill status={grant.status} /></div>
    <dl className="ls-facts"><div><dt>Scope</dt><dd>{scopeText}</dd></div><div><dt>Purpose</dt><dd>{grant.purpose || model.purpose}</dd></div><div><dt>Data leaves device</dt><dd>{model.leaves}</dd></div><div><dt>Access</dt><dd>Continuing</dd></div></dl>
    <div className="ls-actions">{grant.status === 'granted' ? <Action danger disabled={busy} onClick={() => onDecide(grant, 'revoke')}>Revoke</Action> : grant.status === 'requested' ? <><Action primary disabled={busy} onClick={() => onDecide(grant, 'grant')}>Approve</Action><Action disabled={busy} onClick={() => onDecide(grant, 'deny')}>Deny</Action></> : <p className="ls-secondary">{grant.status === 'denied' ? `Denied. The Space shows “${model.name} isn't available” instead of prompting again.` : `${model.name} was revoked. Ask in chat to request access again.`}</p>}</div>
  </article>
}
export function PermissionsContent({ space, grants: all, audit = [], onDecide, busy = false, pending: pendingAction }) {
  const grants = all.filter(g => g.capability === 'net' || CAPABILITIES[g.capability])
  const net = grants.find(g => g.capability === 'net')
  const pending = grants.filter(g => g.capability !== 'net' && g.status === 'requested')
  const settled = grants.filter(g => g.capability !== 'net' && g.status !== 'requested')
  return <>
    {net && <InternetAccess grant={net} owner={space.owner} onDecide={onDecide} busy={busy} pending={pendingAction} />}
    <section className="ls-section"><h2 className="ls-section-title">Granted to {space.name}</h2>{settled.map(g => <GrantCard key={g.capability} grant={g} onDecide={onDecide} busy={busy} />)}{!settled.length && <p>No grants approved yet.</p>}</section>
    <section className="ls-section"><h2 className="ls-section-title">Waiting for your decision</h2>{pending.map(g => <GrantCard key={g.capability} grant={g} onDecide={onDecide} busy={busy} />)}
      {!pending.length && <p className="ls-secondary">Nothing waiting for your decision.</p>}
    </section>
    <section className="ls-section"><h2 className="ls-section-title">Your canvas and its bot</h2><p>Ask {space.owner} in a normal Hermes chat to build or change this canvas, use connected tools, or bring in files. Bot actions follow Hermes's native rules, not extra per-site, per-tool or device permissions here.</p><p className="ls-secondary">Canvas controls that ask their maintaining bot need a working native bot connection. This panel does not submit a bot request.</p></section>
    <section className="ls-section"><h2 className="ls-section-title">Owner</h2><OwnerChip owner={space.owner} /><h2 className="ls-section-title">Audit</h2>{audit.length ? <ul className="ls-audit">{audit.slice(0, 10).map(a => <li key={a.id}><Time at={a.at} /> · {a.actor} · {a.action} {a.capability || ''} · {a.outcome}</li>)}</ul> : <p className="ls-secondary">No permission decisions recorded.</p>}</section>
  </>
}
export function PermissionsSheet({ ctx, scopeKey = null, space, onClose, onChanged, returnFocus }) {
  const base = spacePath(space.id)
  const query = useQuery({ queryKey: ['living-spaces', scopeKey, space.id, 'grants'], queryFn: () => ctx.rest(`${base}/grants`), refetchInterval: 2000 })
  const [revoke, setRevoke] = useState(null)
  const [pending, setPending] = useState(null)
  const busy = !!pending
  const [feedback, setFeedback] = useState('')
  const [error, setError] = useState('')
  const lock = useRef(false)
  async function decide(grant, decision) {
    if (decision === 'revoke' && grant.capability !== 'net') { setRevoke(grant); return }
    await change(grant, `${base}/grants/${grant.capability}`, { decision, ...(decision === 'grant' ? { requested_scope: grant.requested_scope ?? grant.scope ?? {} } : {}) })
  }
  async function change(grant, path, body) {
    if (lock.current) return
    lock.current = true
    setPending({ capability: grant.capability, decision: body.decision }); setError(''); setFeedback('')
    try {
      await ctx.rest(path, { method: 'POST', body })
      const [current] = await Promise.all([query.refetch(), onChanged()])
      if (current?.error) throw current.error
      const state = current?.data?.grants?.find(item => item.capability === grant.capability)?.status
      if (current?.data && state !== ({ grant: 'granted', revoke: 'revoked', deny: 'denied' })[body.decision]) throw new Error('Hermes has not confirmed the requested setting.')
      setFeedback(grant.capability === 'net' ? body.decision === 'deny' ? 'Internet access request denied.' : `Internet access turned ${body.decision === 'grant' ? 'on' : 'off'} for ${space.name}.` : 'Access updated.')
    }
    catch (e) {
      if ((e?.error || e?.body?.error || e)?.code === 'conflict') setError('Permission request changed. Review the new request before approving.')
      else {
        const [current] = await Promise.all([query.refetch(), onChanged()])
        const net = current?.data?.grants?.find(item => item.capability === 'net')
        const still = grant.capability === 'net' && !current?.error && net ? ` It's ${net.status === 'granted' ? 'on' : 'off'}.` : ''
        setError(`${grant.capability === 'net' ? body.decision === 'deny' ? "Couldn't deny the Internet access request. " : `Couldn't turn Internet access ${body.decision === 'grant' ? 'on' : 'off'}. ` : ''}${errorText(e)}${still} Review the current setting before trying again.`)
        return
      }
      await Promise.all([query.refetch(), onChanged()])
    }
    finally { lock.current = false; setPending(null) }
  }
  return <><Drawer title={`Permissions · ${space.name}`} description="Review this Space's access." onClose={onClose} returnFocus={returnFocus}>
    {error && <Banner kind="failed" title={error} />}
    <div role="status" aria-live="polite">{feedback}</div>
    {query.error && query.data && <Banner kind="failed" title="Showing the last loaded access settings. Controls are unavailable until Hermes responds." actions={<Action onClick={() => query.refetch()}>Try again</Action>}>{errorText(query.error)}</Banner>}
    {query.error && !query.data ? <ErrorState title="Permissions could not be loaded" description={errorText(query.error)}><Action onClick={() => { query.refetch() }}>Try again</Action></ErrorState> : query.isLoading ? <Skeleton style={{ height: 180 }} /> : <PermissionsContent space={space} grants={query.data?.grants || []} audit={query.data?.audit || []} onDecide={decide} busy={busy || !!query.error} pending={pending} />}
  </Drawer>{revoke && <DecisionDialog danger title={`Revoke ${CAPABILITIES[revoke.capability].name} for ${space.name}?`} description={`The Space loses ${CAPABILITIES[revoke.capability].name.toLowerCase()} access. Data already delivered to the Space can't be recalled, and completed requests can't be undone.`} cancelLabel="Keep access" confirmLabel="Revoke" onClose={() => setRevoke(null)} onConfirm={async () => { await ctx.rest(`${base}/grants/${revoke.capability}`, { method: 'POST', body: { decision: 'revoke' } }); await query.refetch(); await onChanged() }} />}</>
}
