import { EmptyState, ErrorState, SearchField, SegmentedControl, Skeleton, host, useQuery } from '@hermes/plugin-sdk'
import { useState } from 'react'
import { Action, CopyPrompt, Icon, SpaceTile, StatusPill, Time, absolute, relative } from './components.jsx'
import { PROMPTS, accentColor, cardLines, freshnessFacts, freshnessPhrase, iconName, spaceRoute, spaceStatus, summaryCounts, visibleSpaces } from './model.mjs'
import { readSnapshot } from './snapshots.mjs'

// The card's picture: the Space's own last snapshot when one was captured for its current code, otherwise
// a composed accent-and-icon card. Never an empty or broken image: an image that fails to decode falls back.
export function CardPreview({ space, scopeKey = null }) {
  const snapshot = readSnapshot(scopeKey, space.id, space.head_rev || null)
  const [failed, setFailed] = useState(null)
  const usable = !!snapshot && failed !== snapshot.image
  return <div className={`ls-thumb${usable ? '' : ' ls-thumb-fallback'}`} style={{ '--ls-accent': accentColor(space.accent) }} data-preview={usable ? 'snapshot' : 'fallback'}>
    {usable
      ? <img src={snapshot.image} width={snapshot.width} height={snapshot.height} alt="" decoding="async" draggable={false} onError={() => setFailed(snapshot.image)} />
      : <span className="ls-thumb-mark" aria-hidden="true"><Icon name={iconName(space.icon)} /></span>}
  </div>
}

export function SpaceCard({ space, scopeKey = null }) {
  const status = spaceStatus(space)
  const lines = cardLines(space, relative)
  const facts = freshnessFacts(space, absolute)
  const phrase = freshnessPhrase(space)
  return <a className={`ls-card ls-${status}`} style={{ '--ls-accent': accentColor(space.accent) }} href={`#${spaceRoute(space.id)}`} onClick={e => { if (!e.metaKey && !e.ctrlKey && !e.shiftKey && e.button === 0) { e.preventDefault(); host.navigate(spaceRoute(space.id)) } }}
    aria-label={`${space.name}, ${status[0].toUpperCase() + status.slice(1)}, owner ${space.owner}. ${lines.filter(Boolean).join('. ')}. ${facts.map(f => `${f.label} ${f.value}`).join('. ')}${space.pinned ? '. Pinned' : ''}`}>
    <div className="ls-card-media">
      <CardPreview space={space} scopeKey={scopeKey} />
      {status !== 'ready' && <span className="ls-card-state"><StatusPill status={status} /></span>}
      {space.pinned ? <span className="ls-pin" title="Pinned"><Icon name="pinned" /><span className="ls-sr">Pinned</span></span> : null}
    </div>
    <div className="ls-card-caption"><SpaceTile space={space} small /><div className="ls-card-text">
      <div className="ls-card-name">{space.name}</div>
      {space.description && <p className="ls-card-description">{space.description}</p>}
      <div className="ls-card-freshness">{phrase.at != null ? <>{phrase.label} · <Time at={phrase.at} relative /></> : phrase.label}</div>
    </div></div>
  </a>
}

function newChatAction(ctx) {
  const actions = ctx.listActions?.() || []
  return actions.find(a => a.id === 'session.new') || actions.find(a => /new.*chat|new.*session/i.test(`${a.id} ${a.label}`))
}
function useNewChat(ctx) {
  const [notice, setNotice] = useState('')
  const action = newChatAction(ctx)
  const start = () => {
    const result = action && ctx.runAction?.(action.id)
    if (!result?.ok) setNotice('A new chat is unavailable. Copy an example prompt and paste it into a normal Hermes chat.')
  }
  return { action, start, notice }
}

// The create entry point inside the gallery: Spaces are built in chat, so this starts one.
function NewSpaceCard({ ctx }) {
  const { action, start, notice } = useNewChat(ctx)
  return <div role="listitem" className="ls-newcard"><div>
    <Icon name="comment-discussion" /><strong>Build a Space in chat</strong>
    <span className="ls-secondary">Describe it to Hermes. It appears here as Building.</span>
    <div className="ls-actions">{action ? <Action icon="add" onClick={start}>Start a new chat</Action> : <CopyPrompt text={PROMPTS[0]} label="Copy prompt" />}</div>
    {notice && <p role="status">{notice}</p>}
  </div></div>
}

export function FirstSpace({ ctx }) {
  const { action, start, notice } = useNewChat(ctx)
  return <div className="ls-empty"><div className="ls-empty-tiles" aria-hidden="true"><SpaceTile space={{ accent: 'blue', icon: 'book' }} /><SpaceTile space={{ accent: 'green', icon: 'calendar' }} /><SpaceTile space={{ accent: 'purple', icon: 'graph' }} /></div>
    <EmptyState title="Build your first Space in chat" description="A Space is a canvas your bots keep alive. Describe one in a normal Hermes chat and it appears here." />
    {PROMPTS.map(text => <CopyPrompt key={text} text={text} />)}
    <div className="ls-actions">{action ? <Action primary icon="add" onClick={start}>Start a new chat</Action> : <CopyPrompt text={PROMPTS[0]} label="Start a new chat" />}<span className="ls-secondary">New Spaces appear here, labelled Building until ready.</span></div>
    {!action && <p role="status">This host cannot start a new chat here. The action copies the example prompt to paste into a normal Hermes chat.</p>}{notice && <p role="status">{notice}</p>}
  </div>
}

export function SpacesIndex({ ctx, scopeKey = null }) {
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('all')
  const list = useQuery({ queryKey: ['living-spaces', scopeKey, 'spaces'], queryFn: () => ctx.rest('/spaces'), refetchInterval: 2000, notifyOnChangeProps: ['data', 'error', 'isLoading', 'dataUpdatedAt'] })
  const spaces = list.data?.spaces || []
  const counts = summaryCounts(spaces)
  const visible = visibleSpaces(spaces, search, filter)
  const pinned = spaces.some(s => s.pinned && s.status !== 'archived')
  const browsing = !search && filter === 'all'
  return <div className="ls-page ls-gallery" data-testid="spaces-index"><div className="ls-page-heading"><div className="ls-page-title"><h1>Spaces</h1>{list.data && <span className="ls-secondary ls-num">{counts.active} active · {counts.attention} need attention</span>}</div>
      {list.data && spaces.length > 0 && <SearchField value={search} onChange={setSearch} placeholder="Search Spaces or owner" aria-label="Search Spaces or owner" variant="box" containerClassName="ls-search" />}</div>
    {list.error && <ErrorState title="Spaces could not be loaded" description={list.error.message}><Action onClick={() => list.refetch()}>Try again</Action></ErrorState>}
    {list.isLoading ? <div className="ls-grid" aria-label="Loading Spaces">{[1, 2, 3].map(n => <Skeleton key={n} className="ls-thumb" />)}</div> : list.data && !spaces.length ? <FirstSpace ctx={ctx} /> : list.data ? <>
      <div className="ls-toolbar">
        <SegmentedControl value={filter} onChange={setFilter} sizing="content" options={[{ id: 'all', label: 'Recent' }, ...(pinned ? [{ id: 'pinned', label: 'Pinned' }] : []), { id: 'attention', label: `Needs attention · ${counts.attention}` }, { id: 'archived', label: 'Archived' }]} /><span className="ls-sort">Pinned first, then recently opened</span></div>
      {visible.length || browsing ? <div className="ls-grid" role="list" aria-label="Spaces">{visible.map(s => <div role="listitem" key={s.id}><SpaceCard space={s} scopeKey={scopeKey} /></div>)}{browsing && <NewSpaceCard ctx={ctx} />}</div>
        : <div role="status"><EmptyState title={search ? `No Spaces match “${search}”. Try another name or owner.` : filter === 'attention' ? 'Nothing needs attention.' : filter === 'pinned' ? 'No pinned Spaces.' : 'No archived Spaces.'} /></div>}
    </> : null}
    <p className="ls-footer">Spaces are built and changed in a normal chat. Ask your agent to “build…”, “change…” or “keep … current”.</p>
  </div>
}
