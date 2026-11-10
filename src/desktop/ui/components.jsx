import { Badge, Button, Codicon, CopyButton, Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, fmtDateTime, relativeTime, Tip } from '@hermes/plugin-sdk'
import { useRef, useState } from 'react'
import { accentColor, errorText, iconName, PILLS } from './model.mjs'

export const relative = seconds => relativeTime(seconds * 1000)
export function absolute(seconds) {
  if (seconds == null) return 'Not reported'
  const date = new Date(seconds * 1000)
  const zone = new Intl.DateTimeFormat(undefined, { timeZoneName: 'short' }).formatToParts(date).find(p => p.type === 'timeZoneName')?.value || ''
  return `${fmtDateTime.format(date)} ${zone}`.trim()
}
export function Time({ at, children }) { return <span title={at == null ? undefined : absolute(at)}>{children ?? (at == null ? 'Not reported' : absolute(at))}</span> }
export function Icon({ name, spin = false }) { return <Codicon name={name} aria-hidden="true" className={spin ? 'ls-spin' : undefined} /> }
export function StatusPill({ status, label }) {
  const pill = PILLS[status] || { label: status, icon: 'info', border: 'solid' }
  return <Badge variant="outline" className={`ls-pill ls-${status}`} style={{ borderStyle: pill.border }}><Icon name={pill.icon} spin={['updating', 'running'].includes(status)} />{label || pill.label}</Badge>
}
export function SpaceTile({ space, small = false }) {
  return <span className={`ls-tile${small ? ' ls-tile-small' : ''}`} style={{ '--ls-accent': accentColor(space.accent) }}><Icon name={iconName(space.icon)} /></span>
}
export function OwnerChip({ owner = 'Hermes' }) {
  return <span className="ls-owner"><span className="ls-avatar" aria-hidden="true">{owner.slice(0, 1).toUpperCase()}</span><span>{owner}</span></span>
}
export function Action({ children, icon, primary = false, danger = false, ...props }) {
  return <Button type="button" size="sm" variant={primary ? 'default' : danger ? 'outline' : 'secondary'} className={danger ? 'ls-action ls-danger' : 'ls-action'} {...props}>{icon && <Icon name={icon} spin={icon === 'refresh' && props['aria-busy']} />}{children}</Button>
}
export function DisabledReason({ reason, children }) { return <Tip label={reason || 'Refresh this Space'}>{children}</Tip> }
export function CopyPrompt({ text, label = 'Copy' }) {
  const [error, setError] = useState('')
  return <div className="ls-prompt"><Icon name="comment-discussion" /><q>{text}</q><CopyButton text={text} label={label} showLabel buttonSize="sm" onCopyError={() => setError('Copy failed. Select and copy the prompt.')} />{error && <span role="alert">{error}</span>}</div>
}
export function Banner({ kind = 'info', title, children, actions }) {
  return <div className={`ls-banner ls-${kind}`} role={['failed', 'blocked', 'crashed', 'conflict'].includes(kind) ? 'alert' : 'status'}><Icon name={kind === 'info' ? 'info' : 'warning'} /><div><strong>{title}</strong>{children && <div className="ls-secondary">{children}</div>}{actions && <div className="ls-actions">{actions}</div>}</div></div>
}
export function Drawer({ title, description, children, onClose, note, returnFocus }) {
  const trigger = useRef(returnFocus || (typeof document === 'undefined' ? null : document.activeElement))
  const close = useRef(null)
  return <Dialog open onOpenChange={open => !open && onClose()}><DialogContent className="ls-sheet" bodyClassName="ls-sheet-body" showCloseButton={false}
    onOpenAutoFocus={event => { event.preventDefault(); close.current?.focus() }}
    onCloseAutoFocus={event => { event.preventDefault(); trigger.current?.focus() }}>
    <DialogHeader className="ls-sheet-header"><DialogTitle>{title}</DialogTitle><Button ref={close} onClick={onClose} variant="ghost" size="sm" className="ls-action"><Icon name="close" />Close</Button><DialogDescription className="ls-sr">{description || title}</DialogDescription></DialogHeader>
    {note}<div className="ls-sheet-scroll">{children}</div>
  </DialogContent></Dialog>
}
export function DecisionDialog({ title, description, confirmLabel, cancelLabel = 'Cancel', danger = false, onClose, onConfirm, returnFocus }) {
  const cancel = useRef(null)
  const trigger = useRef(returnFocus || (typeof document === 'undefined' ? null : document.activeElement))
  const [busy, setBusy] = useState(false)
  const pending = useRef(false)
  const [error, setError] = useState('')
  async function confirm() {
    if (pending.current) return
    pending.current = true
    setBusy(true)
    setError('')
    try { await onConfirm(); onClose() }
    catch (e) { setError(errorText(e)) }
    finally { pending.current = false; setBusy(false) }
  }
  return <Dialog open onOpenChange={open => !open && !busy && onClose()}><DialogContent role={danger ? 'alertdialog' : 'dialog'} className="ls-confirm" showCloseButton={false}
    onOpenAutoFocus={event => { event.preventDefault(); cancel.current?.focus() }}
    onCloseAutoFocus={event => { event.preventDefault(); trigger.current?.focus() }}>
    <DialogHeader><DialogTitle>{title}</DialogTitle><DialogDescription>{description}</DialogDescription></DialogHeader>
    {error && <Banner kind="failed" title={error} />}
    <DialogFooter><Button ref={cancel} variant="ghost" className="ls-action" disabled={busy} onClick={onClose}>{cancelLabel}</Button><Action primary={!danger} danger={danger} aria-busy={busy} aria-disabled={busy} onClick={confirm}>{busy ? 'Working…' : confirmLabel}</Action></DialogFooter>
  </DialogContent></Dialog>
}
