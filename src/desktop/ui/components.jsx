import { Badge, Button, Codicon, CopyButton, Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, fmtDateTime, relativeTime, Tip } from '@hermes/plugin-sdk'
import { useLayoutEffect, useMemo, useRef, useState } from 'react'
import { ALERT_KINDS, accentColor, errorText, iconName, PILLS } from './model.mjs'
import { parseMarkdown } from './markdown.mjs'

export const relative = seconds => relativeTime(seconds * 1000)
export function absolute(seconds) {
  if (seconds == null || !Number.isFinite(seconds)) return ''
  const date = new Date(seconds * 1000)
  const zone = new Intl.DateTimeFormat(undefined, { timeZoneName: 'short' }).formatToParts(date).find(p => p.type === 'timeZoneName')?.value || ''
  return `${fmtDateTime.format(date)} ${zone}`.trim()
}
const fmtClock = new Intl.DateTimeFormat(undefined, { timeStyle: 'short' })
// A stamp for a notice title: the time alone when it is today, the full stamp otherwise. The tooltip is always absolute.
export function clock(seconds, now = Date.now()) {
  if (!absolute(seconds)) return ''
  const date = new Date(seconds * 1000)
  return date.toDateString() === new Date(now).toDateString() ? fmtClock.format(date) : absolute(seconds)
}
export function Time({ at, children, relative: asRelative = false, short = false }) {
  if (!absolute(at)) return null
  return <time dateTime={new Date(at * 1000).toISOString()} title={absolute(at)}>{children ?? (asRelative ? relative(at) : short ? clock(at) : absolute(at))}</time>
}
export function Freshness({ facts }) {
  return facts.map((fact, index) => <span key={fact.key}>{index > 0 && ' · '}{fact.at == null ? fact.label : <>{fact.label} <Time at={fact.at} relative /></>}</span>)
}
export function Icon({ name, spin = false }) { return <Codicon name={name} aria-hidden="true" className={spin ? 'ls-spin' : undefined} /> }
export function StatusPill({ status, label }) {
  const pill = PILLS[status] || { label: status, icon: 'info', border: 'solid' }
  return <Badge variant="outline" className={`ls-pill ls-${status}`} style={{ borderStyle: pill.border }}><Icon name={pill.icon} spin={['updating', 'running'].includes(status)} />{label || pill.label}</Badge>
}
// A Space names its own icon. A name this host's icon font does not draw renders as nothing, so a Space icon
// that paints no glyph falls back to the contract's default instead of leaving an empty tile.
export function SpaceIcon({ icon }) {
  const name = iconName(icon)
  const [missing, setMissing] = useState(null)
  const ref = useRef(null)
  useLayoutEffect(() => {
    const element = ref.current?.querySelector('.codicon') || ref.current?.firstElementChild
    if (!element || typeof getComputedStyle !== 'function') return
    const content = getComputedStyle(element, '::before').content
    setMissing(content === 'none' ? name : null)
  }, [name])
  return <span ref={ref} className="ls-icon-slot"><Icon name={missing === name ? 'layers' : name} /></span>
}
export function SpaceTile({ space, small = false }) {
  return <span className={`ls-tile${small ? ' ls-tile-small' : ''}`} style={{ '--ls-accent': accentColor(space.accent) }}><SpaceIcon icon={space.icon} /></span>
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
// `noticeKey` names what the notice is about when its title carries changing words, such as a time.
export function Banner({ kind = 'info', title, children, actions, noticeKey }) {
  return <div className={`ls-banner ls-${kind}`} data-notice={noticeKey} role={ALERT_KINDS.includes(kind) ? 'alert' : 'status'}><Icon name={kind === 'info' ? 'info' : kind === 'storage' ? 'database' : 'warning'} /><div><strong>{title}</strong>{children && <div className="ls-secondary">{children}</div>}{actions && <div className="ls-actions">{actions}</div>}</div></div>
}
function Spans({ spans, onOpenLink }) {
  return spans.map((span, index) => span.type === 'break' ? <br key={index} />
    : span.type === 'strong' ? <strong key={index}>{span.text}</strong>
    : span.type === 'em' ? <em key={index}>{span.text}</em>
    : span.type === 'code' ? <code key={index}>{span.text}</code>
    : span.type === 'link' ? <a key={index} href={span.href} onClick={event => { event.preventDefault(); onOpenLink?.(span.href) }}>{span.text}</a>
    : span.text)
}
// Renders a bot answer as elements only; markdown.mjs never yields HTML, so raw tags stay text.
export function Answer({ text, onOpenLink }) {
  const blocks = useMemo(() => parseMarkdown(text), [text])
  return blocks.map((block, index) => block.type === 'code' ? <pre key={index}><code>{block.text}</code></pre>
    : block.type === 'heading' ? <h5 key={index}><Spans spans={block.spans} onOpenLink={onOpenLink} /></h5>
    : block.type === 'list' ? (() => { const List = block.ordered ? 'ol' : 'ul'; return <List key={index}>{block.items.map((item, n) => <li key={n}><Spans spans={item} onOpenLink={onOpenLink} /></li>)}</List> })()
    : <p key={index}><Spans spans={block.spans} onOpenLink={onOpenLink} /></p>)
}
export function Drawer({ title, description, children, onClose, note, returnFocus, heading }) {
  const trigger = useRef(returnFocus || (typeof document === 'undefined' ? null : document.activeElement))
  const close = useRef(null)
  return <Dialog open onOpenChange={open => !open && onClose()}><DialogContent className="ls-sheet" bodyClassName="ls-sheet-body" showCloseButton={false}
    onOpenAutoFocus={event => { event.preventDefault(); close.current?.focus() }}
    onCloseAutoFocus={event => { event.preventDefault(); trigger.current?.focus() }}>
    <DialogHeader className="ls-sheet-header">{heading}<DialogTitle>{title}</DialogTitle><Button ref={close} onClick={onClose} variant="ghost" size="sm" className="ls-action"><Icon name="close" />Close</Button><DialogDescription className="ls-sr">{description || title}</DialogDescription></DialogHeader>
    {note}<div className="ls-sheet-scroll">{children}</div>
  </DialogContent></Dialog>
}
export function DecisionDialog({ title, description, confirmLabel, cancelLabel = 'Cancel', danger = false, onClose, onConfirm, returnFocus, successFocus }) {
  const cancel = useRef(null)
  const trigger = useRef(returnFocus || (typeof document === 'undefined' ? null : document.activeElement))
  const [busy, setBusy] = useState(false)
  const pending = useRef(false)
  const completed = useRef(false)
  const [error, setError] = useState('')
  async function confirm() {
    if (pending.current) return
    pending.current = true
    setBusy(true)
    setError('')
    try { await onConfirm(); completed.current = true; onClose() }
    catch (e) { setError(errorText(e)) }
    finally { pending.current = false; setBusy(false) }
  }
  return <Dialog open onOpenChange={open => !open && !busy && onClose()}><DialogContent role={danger ? 'alertdialog' : 'dialog'} className="ls-confirm" showCloseButton={false}
    onOpenAutoFocus={event => { event.preventDefault(); cancel.current?.focus() }}
    onCloseAutoFocus={event => { event.preventDefault(); (completed.current && successFocus?.current ? successFocus.current : trigger.current)?.focus() }}>
    <DialogHeader><DialogTitle>{title}</DialogTitle><DialogDescription>{description}</DialogDescription></DialogHeader>
    {error && <Banner kind="failed" title={error} />}
    <DialogFooter><Button ref={cancel} variant="ghost" className="ls-action" disabled={busy} onClick={onClose}>{cancelLabel}</Button><Action primary={!danger} danger={danger} aria-busy={busy} aria-disabled={busy} onClick={confirm}>{busy ? 'Working…' : confirmLabel}</Action></DialogFooter>
  </DialogContent></Dialog>
}
