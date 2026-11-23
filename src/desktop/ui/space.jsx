import { CopyButton, DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger, ErrorState, Skeleton, host, useQuery, useQueryClient } from '@hermes/plugin-sdk'
import { useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { Action, Answer, Banner, CopyPrompt, DecisionDialog, Drawer, Icon, SpaceTile, StatusPill, DisabledReason, Time, absolute } from './components.jsx'
import { readDismissed, writeDismissed } from './dismissal.mjs'
import { HistorySheet, StorageNotice } from './history.jsx'
import { PermissionsSheet } from './permissions.jsx'
import { UpkeepSheet } from './upkeep.jsx'
import { advanceCursor, botBanner, botDismissed, botDismissKey, diagnosticText, dismissBot, errorText, freshnessFacts, freshnessPhrase, guestWord, inFlight, parseBotDismissal, PILLS, refreshFact, refreshReason, runResult, spacePath, spaceStatus, statusDimensions, storageNotice } from './model.mjs'
import { createSpaceSession } from './session.mjs'
import { SNAPSHOT_LIMITS, forgetSnapshot, writeSnapshot } from './snapshots.mjs'
import { mountSpace } from '../sandbox/index.js'

function useHeaderMode(hasSpace) {
  const frame = useRef(null)
  const [mode, setMode] = useState('narrow')
  useLayoutEffect(() => {
    const element = frame.current
    if (!element || typeof ResizeObserver === 'undefined') return
    const measure = () => {
      const width = element.getBoundingClientRect().width
      setMode(width < 600 ? 'narrow' : width < 900 ? 'compact' : 'wide')
    }
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(element)
    return () => observer.disconnect()
  }, [hasSpace])
  return [frame, mode]
}

function BotBanner({ action, storageKey, controller, owner }) {
  const replyId = useId()
  const key = botDismissKey(action)
  const [stored, setStored] = useState(() => ({ storageKey, value: readDismissed(storageKey) }))
  const record = parseBotDismissal(stored.storageKey === storageKey ? stored.value : readDismissed(storageKey))
  const [dismissedAction, setDismissedAction] = useState(null)
  const [expandedFor, setExpandedFor] = useState(null)
  const identity = key ?? action
  // The stored record hides passive republishes; the in-memory action covers the status on screen,
  // which a user-initiated status would otherwise keep showing.
  const banner = botBanner(action, { owner, dismissed: dismissedAction === action || (!!key && botDismissed(action, record)), expanded: expandedFor === identity })
  if (!banner) return null
  const dismiss = () => {
    setDismissedAction(action)
    if (!key) return
    const value = JSON.stringify(dismissBot(record, action))
    writeDismissed(storageKey, value)
    setStored({ storageKey, value })
  }
  const failed = banner.kind === 'failed'
  const canContinue = banner.collapsible && controller.current?.canContinue?.() === true
  // A passive poll republishes the same status with a new time; it is the same notice, so it must not reopen the dock.
  return <Banner noticeKey={`bot:${key ?? 'current'}:${action.status}`} kind={failed ? 'failed' : 'info'} title={<>{banner.label}{banner.at != null && <> · <Time at={banner.at} short /></>}</>} actions={<>
    {banner.collapsible && <Action aria-expanded={banner.expanded} aria-controls={replyId} onClick={() => setExpandedFor(banner.expanded ? null : identity)}>{banner.expanded ? 'Collapse' : 'Read reply'}</Action>}
    {banner.kind !== 'reply' && <Action onClick={() => controller.current?.checkAction()}>Check status</Action>}
    {banner.canRetry && <Action onClick={() => controller.current?.retryAction()}>Retry same request</Action>}
    {banner.canDismiss && <Action aria-label={banner.kind === 'reply' ? 'Dismiss reply' : undefined} onClick={dismiss}>Dismiss</Action>}
    {banner.detail && <CopyButton text={`${banner.detail}${banner.at != null ? `\n${absolute(banner.at)}` : ''}`} label="Copy details" showLabel buttonSize="sm" />}
  </>}>
    {banner.reason && <span className="ls-reason" title={banner.reason}>{banner.reason}</span>}
    {banner.collapsible && <>
      {!banner.expanded && <p className="ls-oneline ls-answer-summary" title={banner.summary}>{banner.summary}</p>}
      <div id={replyId} className="ls-collapse" data-open={banner.expanded}><div inert={!banner.expanded || undefined} aria-hidden={!banner.expanded}>
        <div className="ls-answer" tabIndex={0} role="region" aria-label="Hermes reply"><Answer text={banner.answer} onOpenLink={href => controller.current?.openLink(href)} /></div>
        <div className="ls-actions">{canContinue && <Action icon="comment-discussion" onClick={() => controller.current?.continueInChat()}>Continue in chat</Action>}<CopyButton text={banner.answer} label="Copy" showLabel buttonSize="sm" /></div>
      </div></div>
    </>}
  </Banner>
}

const GRANT_WORDS = { net: 'Internet', data: 'Records', logs: 'Diagnostic log', bot: 'Bot requests', files: 'Files', tools: 'Private tools' }
const sourceHost = url => { try { return new URL(url).hostname.replace(/^www\./, '') } catch { return '' } }
// Everything the island leaves out: freshness facts, storage, access, history and runtime, each with its manage action.
function SpaceDetails({ space, dimensions, upkeepLabel, building, onOpen, onClose, returnFocus }) {
  const phrase = freshnessPhrase(space)
  const facts = freshnessFacts(space, absolute)
  const reason = refreshReason(space)
  const notice = storageNotice(space.storage)
  const grants = space.grants || []
  const net = grants.find(grant => grant.capability === 'net')
  const lastRun = space.recent_runs?.[0]
  const sources = space.freshness?.sources || []
  return <Drawer returnFocus={returnFocus} title="Space details" description={`Freshness, storage, access, history and runtime for ${space.name}`} onClose={onClose} heading={<SpaceTile space={space} size={24} />}>
    <section aria-label="Space" className="ls-detail ls-detail-hero"><SpaceTile space={space} size={96} /><div><strong>{space.name}</strong>{space.description && <p className="ls-secondary">{space.description}</p>}</div></section>
    <section aria-label="Freshness" className="ls-detail"><h3>Freshness</h3><dl className="ls-facts">
      <div><dt>Latest change</dt><dd>{phrase.label}{phrase.at != null && <> · <Time at={phrase.at} /></>}</dd></div>
      {facts.map(fact => <div key={fact.key}><dt>{fact.label}</dt><dd>{fact.value}</dd></div>)}
      {sources.map(source => <div key={source.id}><dt>Source</dt><dd>{[source.id, sourceHost(source.url), source.failure_reason].filter(Boolean).join(' · ')}</dd></div>)}
      {!building && <div><dt>Refresh</dt><dd>{refreshFact(space)}</dd></div>}
      {!building && <div><dt>Upkeep</dt><dd>{upkeepLabel}</dd></div>}
    </dl>{!building && <div className="ls-actions"><Action onClick={() => onOpen('upkeep')}>Manage upkeep</Action></div>}</section>
    {space.storage && <section aria-label="Storage use" className="ls-detail"><h3>Storage</h3>
      {notice ? <><p>{notice.title}</p><p className="ls-secondary">{notice.line}</p><div className="ls-meter" aria-hidden="true"><i style={{ width: `${notice.pct}%` }} /></div></> : <p className="ls-secondary">Within this Space's storage limits.</p>}
      <div className="ls-actions"><Action onClick={() => onOpen('history')}>Review storage</Action></div></section>}
    {!building && <section aria-label="Access" className="ls-detail"><h3>Access</h3><dl className="ls-facts">
      <div><dt>Internet</dt><dd>{net?.status === 'granted' ? 'On' : net ? PILLS[net.status]?.label || net.status : 'Not requested'}</dd></div>
      {grants.filter(grant => grant.capability !== 'net').map(grant => <div key={grant.capability}><dt>{GRANT_WORDS[grant.capability] || grant.capability}</dt><dd>{PILLS[grant.status]?.label || grant.status}</dd></div>)}
    </dl><div className="ls-actions"><Action onClick={() => onOpen('permissions')}>Manage access</Action></div></section>}
    <section aria-label="History" className="ls-detail"><h3>History</h3><dl className="ls-facts">
      <div><dt>Revision</dt><dd>{space.head_rev || 'None yet'}</dd></div>
      {lastRun && <div><dt>Last refresh</dt><dd>{runResult(lastRun)}{(lastRun.ended_at ?? lastRun.queued_at) != null && <> · <Time at={lastRun.ended_at ?? lastRun.queued_at} /></>}</dd></div>}
    </dl><div className="ls-actions"><Action icon="history" onClick={() => onOpen('history')}>Open history</Action></div></section>
    <section aria-label="Runtime" className="ls-detail"><h3>Runtime</h3><dl className="ls-facts">
      <div><dt>Host</dt><dd>{PILLS[dimensions.host === 'available' ? 'ready' : dimensions.host]?.label || dimensions.host}</dd></div>
      <div><dt>Space app</dt><dd>{guestWord(dimensions.guest)}</dd></div>
    </dl></section>
  </Drawer>
}

function SaveStatus({ write, announcement }) {
  const labels = { saving: 'Saving…', saved: `Saved ${write?.at ? absolute(write.at) : ''}`, failed: 'Not saved — this change was rejected', unknown: 'Save outcome unknown — the change may have been stored', conflict: 'Conflict — this record changed elsewhere' }
  return <span className="ls-save" data-status={write?.status} role="status" aria-live="polite" aria-atomic="true">{write && <><Icon name={write.status === 'saving' ? 'refresh' : ['failed', 'unknown', 'conflict'].includes(write.status) ? 'warning' : 'check'} spin={write.status === 'saving'} /><span className="ls-save-text">{labels[write.status]}</span></>}{announcement && <span className="ls-save-text">{announcement}</span>}</span>
}
function WriteBanner({ write, setWrite, onCompare, onUpdated, onDismiss }) {
  if (!write || !['failed', 'unknown', 'conflict'].includes(write.status)) return null
  if (write.editorManaged) return <Banner kind={write.status === 'conflict' ? 'conflict' : 'failed'} title={write.status === 'unknown' ? 'Save outcome unknown' : write.status === 'conflict' ? 'Changes conflict' : 'Not saved'}>Your draft is preserved. Continue in the app editor to resolve this save.</Banner>
  const current = write.reply?.error?.current
  const canKeep = write.op === 'data.put' && current?.rev != null
  return <Banner kind={write.status === 'conflict' ? 'conflict' : 'failed'} title={write.status === 'conflict' ? 'Conflict — this record changed elsewhere' : write.status === 'unknown' ? 'Save outcome unknown — the change may have been stored' : 'Not saved — this change was rejected'}
    actions={write.status === 'conflict' ? <>{canKeep && <Action onClick={() => write.retry({ ...write.args, base_rev: current.rev })}>Keep my note</Action>}<Action onClick={() => { setWrite(null); onUpdated(current) }}>Use updated record</Action><Action onClick={onCompare}>Compare</Action></> : write.retry ? <Action onClick={() => write.retry()}>Retry save</Action> : <Action onClick={onDismiss}>Dismiss</Action>}>
    {write.reply?.error ? errorText(write.reply.error) : 'Your change is kept in this view until you choose how to continue.'}
  </Banner>
}
// Floating notices. They sit over the bottom of the canvas, so they must always give it back: an expanded dock
// collapses to one compact pill on its own after a few seconds (paused while the pointer or focus is inside it), by
// its button, by Escape, or when the user starts using the canvas. Only a notice the dock has not shown before
// expands it again. Collapsing never dismisses: a failure stays as the alert pill until the user dismisses it.
// Only the notices themselves take pointer input; the canvas around them stays usable, and nothing traps focus.
export const NOTICE_COLLAPSE_MS = 8000
const pillLabel = ({ count, alerts }) => count === 1 ? (alerts ? '1 failed' : '1 notice') : alerts === count ? `${count} failed` : `${count} notices`
export function NoticeDock({ children, minimiseSignal, collapseAfterMs = NOTICE_COLLAPSE_MS }) {
  const dock = useRef(null)
  const list = useRef(null)
  const pill = useRef(null)
  const minimiser = useRef(null)
  const [minimised, setMinimised] = useState(false)
  const [opened, setOpened] = useState(0)
  const [hovered, setHovered] = useState(false)
  const [focused, setFocused] = useState(false)
  const [summary, setSummary] = useState({ count: 0, alerts: 0, titles: [], keys: '' })
  const seen = useRef(new Set())
  const id = useId()
  useLayoutEffect(() => {
    const element = list.current
    if (!element) return
    const read = () => {
      const notices = [...element.querySelectorAll('.ls-banner')]
      const titles = notices.map(node => node.querySelector('strong')?.textContent || '')
      const keys = notices.map((node, index) => node.dataset.notice || titles[index])
      const next = { count: notices.length, alerts: notices.filter(node => node.getAttribute('role') === 'alert').length, titles, keys: titles.join('\n') }
      setSummary(current => current.keys === next.keys && current.count === next.count && current.alerts === next.alerts ? current : next)
      // A notice the user has not seen yet brings the dock back. Focus on the pill moves with it to the toggle.
      if (keys.some(key => !seen.current.has(key))) {
        if (pill.current && document.activeElement === pill.current) requestAnimationFrame(() => minimiser.current?.focus())
        setMinimised(false)
        setOpened(n => n + 1)
      }
      seen.current = new Set(keys)
      // A dismissed notice can take the focused control with it, and no blur reaches the dock; trust where focus is now.
      if (!dock.current?.contains(document.activeElement)) setFocused(false)
    }
    read()
    if (typeof MutationObserver === 'undefined') return
    const observer = new MutationObserver(read)
    observer.observe(element, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ['role'] })
    return () => observer.disconnect()
  }, [])
  useEffect(() => { if (minimiseSignal) setMinimised(true) }, [minimiseSignal])
  const empty = summary.count === 0
  // The collapse timer runs only while the expanded dock is left alone; touching it pauses, leaving starts it over.
  useEffect(() => {
    if (minimised || empty || hovered || focused || !(collapseAfterMs > 0)) return
    const timer = setTimeout(() => setMinimised(true), collapseAfterMs)
    return () => clearTimeout(timer)
  }, [minimised, empty, hovered, focused, opened, collapseAfterMs])
  const minimise = () => {
    const inside = dock.current?.contains(document.activeElement)
    setMinimised(true)
    if (inside) requestAnimationFrame(() => pill.current?.focus())
  }
  const expand = () => { setMinimised(false); setOpened(n => n + 1); requestAnimationFrame(() => minimiser.current?.focus()) }
  // The accessible name starts with the visible label (label-in-name), then carries every full title.
  const full = `${pillLabel(summary)}: ${summary.titles.join('; ')}`
  return <div ref={dock} className="ls-notices" data-minimised={minimised || undefined} data-empty={empty || undefined}
    onPointerEnter={() => setHovered(true)} onPointerLeave={() => setHovered(false)}
    onFocus={() => setFocused(true)} onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) setFocused(false) }}
    onKeyDown={event => { if (event.key === 'Escape' && !minimised && !empty) { event.stopPropagation(); minimise() } }}>
    {minimised && !empty && <button ref={pill} type="button" className={`ls-notice-pill${summary.alerts ? ' ls-alert' : ''}`} aria-expanded="false" aria-controls={id}
      aria-label={`${full}. Show ${summary.count === 1 ? 'notice' : 'notices'}`} title={summary.titles.join('\n')} onClick={expand}>
      <Icon name={summary.alerts ? 'warning' : 'bell'} /><span className="ls-num">{pillLabel(summary)}</span>
    </button>}
    <div id={id} className="ls-notice-list" hidden={minimised || undefined} aria-label="Space notices" role="group">
      {!empty && <div className="ls-notice-tools"><button ref={minimiser} type="button" className="ls-notice-minimise" aria-expanded="true" aria-controls={id} onClick={minimise}><Icon name="chevron-down" />Minimise</button></div>}
      <div ref={list} className="ls-notice-stack">{children}</div>
    </div>
  </div>
}

export function SpaceView({ ctx, scopeKey = null, scope, openingSessionRest, sid }) {
  const { connectionId, profile } = useMemo(() => scope || { connectionId: host.state.connectionId.get(), profile: host.state.profile.get() }, [scope, ctx, scopeKey, sid])
  const base = spacePath(sid)
  const queryClient = useQueryClient()
  const detail = useQuery({ queryKey: ['living-spaces', scopeKey, sid, 'detail'], queryFn: () => ctx.rest(base), refetchInterval: 2000, notifyOnChangeProps: ['data', 'error', 'dataUpdatedAt'] })
  const space = detail.data
  const [frame, headerMode] = useHeaderMode(!!space)
  const [sheet, setSheet] = useState(null)
  const [confirmation, setConfirmation] = useState(null)
  const [reload, setReload] = useState(0)
  const [guest, setGuest] = useState({ status: 'unknown', diagnostic: null })
  const crash = guest.diagnostic
  const [ignoredCrashRev, setIgnoredCrashRev] = useState(null)
  const [write, setWrite] = useState(null)
  const [announcement, setAnnouncement] = useState('')
  const [actionError, setActionError] = useState('')
  const [botAction, setBotAction] = useState(null)
  const [refreshPending, setRefreshPending] = useState(false)
  const [ready, setReady] = useState(false)
  const [canvasFocus, setCanvasFocus] = useState(0)
  const refreshLock = useRef(null)
  const refreshLifetime = useRef(null)
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

  useLayoutEffect(() => {
    const lifetime = { active: true }
    refreshLifetime.current = lifetime
    return () => {
      lifetime.active = false
      if (refreshLock.current?.lifetime === lifetime) {
        refreshLock.current = null
        setRefreshPending(false)
        setAnnouncement('')
      }
    }
  }, [ctx, openingSessionRest, connectionId, profile, scopeKey, sid, space?.head_rev, grantsKey, building, archived, crash, remoteCrash, reload])

  useEffect(() => {
    if (building || archived || crash || remoteCrash || !content.current) return
    let disposed = false
    cursor.current = 0
    setReady(false)
    setGuest({ status: 'starting', diagnostic: null })
    setBotAction(null)
    const current = () => !disposed && host.state.connectionId.get() === connectionId && host.state.profile.get() === profile
    const fail = message => setGuest({ status: 'failed', diagnostic: diagnosticText(message || 'The guest could not be loaded.') })
    const backend = { connectionId, profile }
    const session = createSpaceSession({ backend, host, onAction: event => current() && setBotAction({ ...event, at: Date.now() / 1000 }), rest: openingSessionRest || ((path, options) => ctx.rest(path, options)), sid, container: content.current,
      mount: (container, options) => mountSpace(container, { ...options, call: async (op, args) => {
        const reply = await options.call(op, args)
        if (current() && op === 'log' && reply?.ok === true) {
          if (args.lifecycle === 'failed') fail('The guest reported a load or runtime failure. Review this Space\'s diagnostic log for details.')
          if (args.lifecycle === 'loaded') setGuest(value => ['failed', 'faulted'].includes(value.status) ? value : { status: 'loaded', diagnostic: null })
        }
        return reply
      } }),
      onWrite: event => current() && setWrite(event),
      onEvent: event => {
        if (!current()) return
        if (event.kind === 'reloaded') setReload(n => n + 1)
        if (event.kind === 'booted') setReady(true)
        if (event.kind === 'denied') setAnnouncement('A Space request was denied. Review Permissions for access details.')
        if (event.kind === 'log-overflow') setAnnouncement('Some diagnostic entries were dropped because the log limit was reached.')
        if (event.kind === 'fault') setGuest(value => value.status === 'failed' ? value : { status: 'faulted', diagnostic: null })
      }
    })
    controller.current = session
    session.ready.then(() => { if (current()) setReady(true) }).catch(e => {
      if (disposed) return
      if (current()) fail(errorText(e))
      else setActionError(errorText(e))
    })
    return () => {
      disposed = true
      setReady(false)
      session.postEvent('session.closed', { reason: 'Space view closed or reloaded' })
      session.destroy().catch(e => host.notifyError(e, 'A Space session could not be closed after retries.'))
      if (controller.current === session) controller.current = null
    }
  }, [ctx, openingSessionRest, connectionId, profile, scopeKey, sid, space?.head_rev, grantsKey, building, archived, crash, remoteCrash, reload])

  const changes = useQuery({ queryKey: ['living-spaces', scopeKey, sid, 'changes', space?.head_rev, grantsKey, reload], queryFn: () => ctx.rest(`${base}/changes?since=${cursor.current}`), enabled: hasData && ready && !building && !archived && !crash, refetchInterval: 1500 })
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
  useLayoutEffect(() => {
    setGuest({ status: 'unknown', diagnostic: null })
    setIgnoredCrashRev(null)
  }, [connectionId, profile, scopeKey, sid, space?.head_rev])

  // Card previews: once the canvas has settled, and again when the user leaves, the Space renders a downscaled
  // snapshot of itself inside its sandbox. It is stored only in this Desktop and replaced on the next capture.
  const capture = useRef(null)
  capture.current = async () => {
    const session = controller.current
    const rev = space?.head_rev
    if (!session?.snapshot || !ready || !rev || ['failed', 'faulted'].includes(guest.status)) return
    const shot = await session.snapshot({ width: SNAPSHOT_LIMITS.width, timeoutMs: 2500 })
    if (shot && controller.current === session && host.state.connectionId.get() === connectionId && host.state.profile.get() === profile) writeSnapshot(scopeKey, sid, { ...shot, at: Date.now() / 1000, rev })
  }
  useEffect(() => {
    if (!ready || building || archived || crash || remoteCrash || ['failed', 'faulted'].includes(guest.status)) return
    const settle = setTimeout(() => capture.current?.(), 2500)
    const again = setInterval(() => { if (document.visibilityState !== 'hidden') capture.current?.() }, 60000)
    return () => { clearTimeout(settle); clearInterval(again) }
  }, [ready, building, archived, crash, remoteCrash, guest.status, space?.head_rev])
  // Using the canvas minimises floating notices. Pointer and focus inside the sandbox are not visible to the host,
  // but the host window blurs and the frame becomes the active element.
  useEffect(() => {
    const onBlur = () => setTimeout(() => {
      const active = document.activeElement
      if (active?.tagName === 'IFRAME' && content.current?.contains(active)) setCanvasFocus(n => n + 1)
    }, 0)
    window.addEventListener('blur', onBlur)
    return () => window.removeEventListener('blur', onBlur)
  }, [])
  const leaving = useRef(false)
  const mounted = useRef(true)
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  async function leave() {
    if (leaving.current) return
    leaving.current = true
    try { await Promise.race([capture.current?.(), new Promise(resolve => setTimeout(resolve, 700))]) } catch {}
    // The capture wait is short but real: if the user went elsewhere or switched profile meanwhile, stay out of it.
    if (!mounted.current || host.state.connectionId.get() !== connectionId || host.state.profile.get() !== profile) return
    host.navigate('/spaces')
  }
  async function refresh() {
    if (refreshLock.current || refreshPending || status === 'updating' || inFlight(lastRun?.status) || refreshReason(space)) return
    const request = { lifetime: refreshLifetime.current, controller: controller.current }
    const current = () => request.lifetime?.active && refreshLifetime.current === request.lifetime && controller.current === request.controller
      && host.state.connectionId.get() === connectionId && host.state.profile.get() === profile
    if (!current()) return
    refreshLock.current = request
    setRefreshPending(true); setActionError(''); setAnnouncement('Refreshing…')
    try {
      let reply
      try { reply = await ctx.rest(`${base}/refresh`, { method: 'POST' }) }
      catch (error) {
        reply = error?.body || error
        if (!reply?.outcome?.status) reply = { outcome: { status: 'unknown' } }
      }
      if (!current()) return
      const certainty = reply?.outcome?.status
      if (certainty === 'unknown') { setAnnouncement('Refresh outcome unknown'); return }
      if (certainty === 'busy' || certainty === 'rejected') {
        setActionError(errorText(reply.error || reply))
        setAnnouncement(certainty === 'busy' ? 'Refresh busy' : 'Refresh failed')
        return
      }
      const run = reply?.result || reply
      if (reply?.ok === false || (!run?.id && run?.kind !== 'cron')) { setAnnouncement('Refresh outcome unknown'); return }
      if (run.kind === 'cron') setAnnouncement('Refresh started in Hermes')
      else {
        request.controller?.postEvent('run.updated', run)
        if (!inFlight(run.status) && run.status) setAnnouncement(`Refresh ${run.status}: ${runResult(run)}`)
      }
      await detail.refetch().catch(error => { if (current()) setActionError(errorText(error)) })
    } finally {
      if (refreshLock.current === request) { refreshLock.current = null; setRefreshPending(false) }
    }
  }
  const listKey = ['living-spaces', scopeKey, 'spaces']
  // Only a successful refetch is fresh: a failed one keeps the cached (pre-action) detail.
  const fresh = result => result?.status === 'success' ? result.data : null
  async function syncList(fresh) {
    // A fetch started after the mutation is authoritative and supersedes any older in-flight list request.
    // The row patch only makes the index correct before that fetch returns, so it needs fresh detail.
    if (fresh) {
      await queryClient.cancelQueries({ queryKey: listKey })
      queryClient.setQueryData(listKey, list => list?.spaces ? { ...list, spaces: list.spaces.map(row => row.id === sid ? Object.fromEntries(Object.keys(row).map(key => [key, key in fresh ? fresh[key] : row[key]])) : row) } : list)
    }
    queryClient.invalidateQueries({ queryKey: listKey, refetchType: 'all' })
  }
  async function act(path, body) {
    if (actionLock.current) return
    actionLock.current = true
    setActionError('')
    try { await ctx.rest(`${base}/${path}`, { method: 'POST', ...(body ? { body } : {}) }); await syncList(fresh(await detail.refetch())) }
    catch (e) { setActionError(errorText(e)) }
    finally { actionLock.current = false }
  }
  if (!space) return <div className="ls-page">{detail.error ? <ErrorState title="This Space could not be opened" description={errorText(detail.error)}><Action onClick={() => detail.refetch()}>Try again</Action><Action onClick={() => host.navigate('/spaces')}>Spaces</Action></ErrorState> : <Skeleton style={{ height: 400 }} />}</div>
  const dimensions = statusDimensions(space, { guest: remoteCrash ? 'failed' : guest.status, write })
  const upkeep = space.upkeep
  const busy = refreshPending || inFlight(lastRun?.status) || status === 'updating'
  const reason = refreshReason(space)
  const opener = () => {
    const element = document.activeElement?.getAttribute('role') === 'menuitem' ? overflow.current : document.activeElement
    return { focus: () => {
      if (element?.isConnected) {
        element.focus()
        if (document.activeElement === element) return
      }
      overflow.current?.focus()
    } }
  }
  const openSheet = (kind, tab) => setSheet({ kind, tab, returnFocus: opener() })
  const openHistory = tab => { detail.refetch(); openSheet('history', tab || 'runs') }
  const askConfirmation = kind => { confirmationTrigger.current = opener(); setConfirmation(kind) }
  const crashMessage = diagnosticText(crash || space.attention?.message || 'The guest reported a fatal error.')
  const phrase = freshnessPhrase(space)
  const upkeepLabel = !upkeep ? 'None' : upkeep.missing ? 'Job missing' : upkeep.enabled === true ? 'On' : upkeep.enabled === false ? 'Paused' : 'Linked'
  const netOn = space.grants?.some(grant => grant.capability === 'net' && grant.status === 'granted')
  const refreshable = !building && !!space.manifest?.upkeep
  const tone = ['failed', 'blocked', 'crashed'].includes(status) ? 'danger' : status === 'updating' ? 'busy' : phrase.key === 'success' && !space.freshness?.last_success_at ? 'idle' : 'good'
  return <div ref={frame} className="ls-frame" data-header-mode={headerMode} data-testid="space-view"><header className="ls-framebar">
    <div className="ls-island ls-island-identity"><Action className="ls-action ls-icon-button" icon="arrow-left" aria-label="Back to Spaces" title="Back to Spaces" onClick={leave} />
      <div className="ls-identity"><SpaceTile space={space} size={24} /><h1 title={space.name}>{space.name}</h1>{status !== 'ready' && <StatusPill status={status} />}</div></div>
    <div className="ls-island ls-frame-actions">
      <span className="ls-frame-meta" title={phrase.at != null ? `${phrase.label} · ${absolute(phrase.at)}` : phrase.label}><span className="ls-dot" data-tone={tone} aria-hidden="true" /><span className="ls-frame-meta-text">{phrase.label}{phrase.at != null && <> · <Time at={phrase.at} relative /></>}</span></span>
      <SaveStatus write={write} announcement={announcement} />
      {netOn && <Action className="ls-action ls-island-button" icon="globe" title="Internet access is on. Manage it in Permissions." onClick={() => openSheet('permissions')}><span className="ls-label">Internet on</span></Action>}
      {refreshable && <DisabledReason reason={reason}><Action className="ls-action ls-island-button" icon="refresh" aria-busy={busy} aria-disabled={!!reason || busy} title={reason || undefined} onClick={refresh}><span className="ls-label">{busy ? 'Refreshing…' : 'Refresh now'}</span></Action></DisabledReason>}
      <Action className="ls-action ls-island-button" icon="settings" onClick={() => openSheet('details')}><span className="ls-label">Details</span></Action>
      <DropdownMenu><DropdownMenuTrigger asChild><Action ref={overflow} className="ls-action ls-overflow" aria-label="More Space actions" icon="ellipsis" /></DropdownMenuTrigger><DropdownMenuContent align="end"><DropdownMenuItem onSelect={() => openHistory()}>History</DropdownMenuItem>{!building && <><DropdownMenuItem onSelect={() => openSheet('upkeep')}>Upkeep</DropdownMenuItem><DropdownMenuItem onSelect={() => openSheet('permissions')}>Permissions</DropdownMenuItem><DropdownMenuSeparator /><DropdownMenuItem onSelect={() => act('pin', { pinned: !space.pinned })}>{space.pinned ? 'Unpin Space' : 'Pin Space'}</DropdownMenuItem><DropdownMenuItem onSelect={() => archived ? act('unarchive') : askConfirmation('archive')}>{archived ? 'Restore Space' : 'Archive Space…'}</DropdownMenuItem>{archived && <DropdownMenuItem onSelect={() => askConfirmation('delete')}>Delete…</DropdownMenuItem>}</>}</DropdownMenuContent></DropdownMenu>
    </div></header>
    <section className="ls-content" aria-label="Space content"><div className={`ls-sandbox${status === 'failed' ? ' ls-stale' : ''}`}>
      {building ? <div className="ls-building"><p role="status">{space.owner} is building the first version. This opens automatically when it's ready.</p><Skeleton style={{ height: 100 }} /><Skeleton style={{ height: 180 }} /></div> : status === 'crashed' ? <div className="ls-crash"><ErrorState title={`${space.name} stopped working`} description="The guest hit an error and was stopped. Already-written records remain; stopping the guest does not undo changes. Check the save status for any pending change." /><pre className="ls-diagnostic">{`Revision ${space.head_rev}\n${crashMessage}\nLogged to this Space only. Common credential values redacted.`}</pre><div className="ls-actions"><Action primary onClick={() => { setGuest({ status: 'unknown', diagnostic: null }); setIgnoredCrashRev(space.head_rev); setReload(n => n + 1) }}>Reload Space</Action><Action onClick={() => openHistory('revisions')}>Restore revision…</Action></div><CopyPrompt text={`${space.owner}, ${space.name} crashed. Please read its error log and fix it.`} /><p className="ls-secondary">Repairs happen in chat. {space.owner} can read this error and apply a new revision.</p></div> : archived ? <div className="ls-building"><p>Restore Space to open its content. Your records and revisions are kept.</p></div> : <div ref={content} className="ls-mount" data-testid="space-host" />}
    </div>
    <NoticeDock minimiseSignal={canvasFocus}>
      <StorageNotice storage={space.storage} onReview={() => openHistory()} storageKey={`living-spaces:storage-dismissed:${connectionId}:${profile}:${sid}`} />
      {botAction && <BotBanner action={botAction} controller={controller} owner={space.owner} storageKey={`living-spaces:bot-dismissed:${connectionId}:${profile}:${sid}`} />}
      {guest.status === 'faulted' && <Banner kind="failed" title="This Space hit an uncaught error"><span role="status">It is still open and may keep working. Saved records are unaffected. Review this Space's diagnostic log for details.</span></Banner>}
      {actionError && <Banner kind="failed" title={actionError} />}
      {detail.error && <Banner kind="failed" title="Space status could not be refreshed. You're seeing the last loaded state." actions={<Action onClick={() => detail.refetch()}>Try again</Action>}>{errorText(detail.error)}</Banner>}
      {changes.error && <Banner kind="failed" title="Live record updates are delayed. Your displayed data may be out of date." actions={<Action onClick={() => changes.refetch()}>Retry live updates</Action>}>{errorText(changes.error)}</Banner>}
      <WriteBanner write={write} setWrite={setWrite} onDismiss={() => controller.current?.dismissWrite(write.token)} onCompare={() => openSheet('compare')} onUpdated={() => { controller.current?.dismissWrite(write.token); setReload(n => n + 1) }} />
      {archived ? <Banner title="This Space is archived. Future upkeep is paused." actions={<><Action onClick={() => act('unarchive')}>Restore Space</Action><Action danger onClick={() => askConfirmation('delete')}>Delete…</Action></>}>Restore it to open the canvas, then resume upkeep separately. Already-running work may finish. Delete removes it and its data permanently.</Banner> : status === 'failed' ? <Banner kind="failed" title={`Refresh failed${space.freshness?.last_attempt_at != null ? ` at ${absolute(space.freshness.last_attempt_at)}` : ''}. ${space.freshness?.last_success_at != null ? `You're seeing data from ${absolute(space.freshness.last_success_at)}.` : 'No successful update yet.'}`} actions={<><Action onClick={() => openHistory()}>View run details</Action><Action onClick={refresh}>Try again</Action></>}>{lastRun?.error || space.attention?.message || 'The source did not respond.'} Your notes and statuses are unchanged. {space.freshness?.next_run_at ? `Next automatic try ${absolute(space.freshness.next_run_at)}.` : 'No automatic try is scheduled.'}</Banner> : status === 'blocked' ? <Banner kind="blocked" title={`Refresh is blocked: ${space.attention?.message || reason || 'Review Permissions'}`} actions={<Action onClick={() => openSheet('permissions')}>Review permissions</Action>}>The Space still opens and your data is safe. <CopyPrompt text={`${space.owner}, ${space.name} is blocked. Please review its last run and help me restore upkeep.`} /></Banner> : null}
    </NoticeDock></section>
    {sheet?.kind === 'details' && <SpaceDetails returnFocus={sheet.returnFocus} space={space} dimensions={dimensions} upkeepLabel={upkeepLabel} building={building} onOpen={kind => { if (kind === 'history') detail.refetch(); setSheet({ kind, tab: kind === 'history' ? 'runs' : undefined, returnFocus: sheet.returnFocus }) }} onClose={() => setSheet(null)} />}
    {sheet?.kind === 'permissions' && <PermissionsSheet returnFocus={sheet.returnFocus} ctx={ctx} scopeKey={scopeKey} space={space} onClose={() => setSheet(null)} onChanged={() => detail.refetch()} />}
    {sheet?.kind === 'history' && <HistorySheet returnFocus={sheet.returnFocus} ctx={ctx} scopeKey={scopeKey} space={space} initialTab={sheet.tab} onClose={() => setSheet(null)} onChanged={() => detail.refetch()} />}
    {sheet?.kind === 'upkeep' && <UpkeepSheet returnFocus={sheet.returnFocus} ctx={ctx} scopeKey={scopeKey} space={space} onClose={() => setSheet(null)} onChanged={() => detail.refetch()} />}
    {sheet?.kind === 'compare' && write && <Drawer returnFocus={sheet.returnFocus} title="Compare record changes" description="Your submitted change and the latest stored record" onClose={() => setSheet(null)}><div className="ls-compare"><h2>Your change</h2><pre className="ls-diagnostic">{JSON.stringify(write.args, null, 2)}</pre><h2>Updated record</h2><pre className="ls-diagnostic">{JSON.stringify(write.reply?.error?.current, null, 2)}</pre></div></Drawer>}
    {confirmation && <DecisionDialog returnFocus={confirmationTrigger.current} danger title={confirmation === 'delete' ? `Delete ${space.name}?` : `Archive ${space.name}?`} description={confirmation === 'delete' ? "Delete removes this Space, all its records and revisions permanently and stops future upkeep. Already-running work may finish. Exported copies aren't recalled." : 'Archiving pauses future upkeep. Already-running work may finish. Your records and revisions are kept. Restoring this Space does not resume upkeep.'} confirmLabel={confirmation === 'delete' ? 'Delete Space' : 'Archive Space'} onClose={() => setConfirmation(null)} onConfirm={async () => { if (confirmation === 'delete') { await ctx.rest(`${base}?confirm=${encodeURIComponent(sid)}`, { method: 'DELETE' }); forgetSnapshot(scopeKey, sid); await queryClient.cancelQueries({ queryKey: ['living-spaces', scopeKey, 'spaces'] }); queryClient.setQueryData(['living-spaces', scopeKey, 'spaces'], list => list?.spaces ? { ...list, spaces: list.spaces.filter(row => row.id !== sid) } : list); queryClient.invalidateQueries({ queryKey: ['living-spaces', scopeKey, 'spaces'] }); host.navigate('/spaces') } else { await ctx.rest(`${base}/archive`, { method: 'POST' }); await syncList(fresh(await detail.refetch())) } }} />}
  </div>
}
