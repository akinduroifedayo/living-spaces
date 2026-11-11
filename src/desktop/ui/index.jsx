import { EmptyState, ErrorState, SearchField, SegmentedControl, Skeleton, host, useQuery } from '@hermes/plugin-sdk'
import { useState } from 'react'
import { Action, CopyPrompt, Icon, OwnerChip, SpaceTile, StatusPill, Time, absolute, relative } from './components.jsx'
import { PROMPTS, accentColor, cardLines, freshnessFacts, spaceRoute, spaceStatus, summaryCounts, visibleSpaces } from './model.mjs'

export function SpaceCard({ space }) {
  const status = spaceStatus(space)
  const lines = cardLines(space, relative)
  const facts = freshnessFacts(space, absolute)
  return <a className={`ls-card ls-${status}`} style={{ '--ls-accent': accentColor(space.accent) }} href={`#${spaceRoute(space.id)}`} onClick={e => { if (!e.metaKey && !e.ctrlKey && !e.shiftKey && e.button === 0) { e.preventDefault(); host.navigate(spaceRoute(space.id)) } }}
    aria-label={`${space.name}, ${status === 'failed' ? 'Failed' : status[0].toUpperCase() + status.slice(1)}, owner ${space.owner}. ${lines.join('. ')}. ${facts.map(f => `${f.label} ${f.value}`).join('. ')}`}>
    <div className="ls-card-top"><SpaceTile space={space} /><div><div className="ls-card-name">{space.name}</div><OwnerChip owner={space.owner} /></div>{space.pinned ? <span className="ls-pin"><Icon name="pinned" /><span className="ls-sr">Pinned</span></span> : null}</div>
    <p className="ls-card-description">{space.description}</p><div><StatusPill status={status} /></div>
    <div className="ls-card-freshness"><span>{lines[0]}</span>{lines[1] && <span className="ls-secondary">{lines[1]}</span>}{space.status !== 'archived' && status !== 'building' && <>{space.freshness?.last_attempt_at != null && <div className="ls-secondary">Last attempt <Time at={space.freshness.last_attempt_at} relative />{space.freshness.last_attempt_status && ` · ${space.freshness.last_attempt_status}`}</div>}{space.freshness?.source_as_of != null && <div className="ls-secondary">Source data from <Time at={space.freshness.source_as_of} relative /></div>}</>}</div>
  </a>
}
export function FirstSpace({ ctx }) {
  const [notice, setNotice] = useState('')
  const actions = ctx.listActions?.() || []
  const action = actions.find(a => a.id === 'session.new') || actions.find(a => /new.*chat|new.*session/i.test(`${a.id} ${a.label}`))
  function start() {
    const result = ctx.runAction?.(action.id)
    if (!result?.ok) setNotice('A new chat is unavailable. Copy an example prompt and paste it into a normal Hermes chat.')
  }
  return <div className="ls-empty"><div className="ls-empty-tiles" aria-hidden="true"><SpaceTile space={{ accent: 'blue', icon: 'book' }} /><SpaceTile space={{ accent: 'green', icon: 'calendar' }} /><SpaceTile space={{ accent: 'purple', icon: 'graph' }} /></div>
    <EmptyState title="Build your first Space in chat" description="An open canvas for your bots that live in Hermes. Describe what you want in a normal Hermes chat, then open it here." />
    {PROMPTS.map(text => <CopyPrompt key={text} text={text} />)}
    <div className="ls-actions">{action ? <Action primary icon="add" onClick={start}>Start a new chat</Action> : <CopyPrompt text={PROMPTS[0]} label="Start a new chat" />}<span className="ls-secondary">New Spaces appear here, labelled Building until ready.</span></div>
    {!action && <p role="status">This host cannot start a new chat here. The action copies the example prompt to paste into a normal Hermes chat.</p>}{notice && <p role="status">{notice}</p>}
  </div>
}
export function SpacesIndex({ ctx }) {
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('all')
  const list = useQuery({ queryKey: ['living-spaces', ctx.queryScope || null, 'spaces'], queryFn: () => ctx.rest('/spaces'), refetchInterval: 2000, notifyOnChangeProps: ['data', 'error', 'isLoading', 'dataUpdatedAt'] })
  const spaces = list.data?.spaces || []
  const counts = summaryCounts(spaces)
  const visible = visibleSpaces(spaces, search, filter)
  return <div className="ls-page" data-testid="spaces-index"><div className="ls-page-heading"><h1>Spaces</h1>{list.data && <span className="ls-secondary ls-num">{counts.active} active · {counts.attention} need attention</span>}</div>
    {list.error && <ErrorState title="Spaces could not be loaded" description={list.error.message}><Action onClick={() => list.refetch()}>Try again</Action></ErrorState>}
    {list.isLoading ? <div className="ls-grid" aria-label="Loading Spaces">{[1, 2, 3].map(n => <Skeleton key={n} style={{ height: 240 }} />)}</div> : list.data && !spaces.length ? <FirstSpace ctx={ctx} /> : list.data ? <>
      <div className="ls-toolbar"><SearchField value={search} onChange={setSearch} placeholder="Search Spaces or owner" aria-label="Search Spaces or owner" variant="box" containerClassName="ls-search" />
        <SegmentedControl value={filter} onChange={setFilter} sizing="content" options={[{ id: 'all', label: 'All' }, { id: 'attention', label: `Needs attention · ${counts.attention}` }, { id: 'archived', label: 'Archived' }]} /><span className="ls-sort">Sorted by recently used</span></div>
      {visible.length ? <div className="ls-grid" role="list" aria-label="Spaces">{visible.map(s => <div role="listitem" key={s.id}><SpaceCard space={s} /></div>)}</div> : <div role="status"><EmptyState title={search ? `No Spaces match “${search}”. Try another name or owner.` : filter === 'attention' ? 'Nothing needs attention.' : 'No archived Spaces.'} /></div>}
    </> : null}
    <p className="ls-footer">Spaces are built and changed in a normal chat. Ask your agent to “build…”, “change…” or “keep … current”.</p>
  </div>
}
