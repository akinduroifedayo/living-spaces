import { render } from 'preact'
import { useEffect, useState } from 'preact/hooks'
import { html, useRecord, useSaveState, hashRouter, useRoute, Nav, SaveIndicator, ConflictBanner, RefreshButton } from 'spaces-kit'

function Overview() {
  const { record, loading, error, reload } = useRecord('papers', 'demo')
  const save = useSaveState()
  const [note, setNote] = useState('Public demo note')
  const [base, setBase] = useState(null)
  useEffect(() => { if (record && base === null) setBase(record.rev) }, [record])
  const persist = rev => save.run(async () => {
    const updated = await space.put('papers', 'demo', { note }, { baseRev: rev })
    setBase(updated.rev)
    await reload()
    return updated
  })
  return html`<section><h2>Overview</h2><div class="demo-logo"></div><p id="record-title">${loading ? 'Loading' : error ? error.message : space.field(record, 'title')}</p><label for="note">Note</label><textarea id="note" value=${note} onInput=${e => setNote(e.currentTarget.value)} /><button id="save" data-base-rev=${base} disabled=${loading || base === null || save.state === 'saving'} onClick=${() => persist(base)}>Save note</button> <${SaveIndicator} ...${save} />${save.state === 'conflict' && html`<${ConflictBanner} current=${save.current} onKeepMine=${current => persist(current.rev)} onUseUpdated=${current => { setNote(space.field(current, 'note')); setBase(current.rev) }} />`}<p id="current-note">${record && space.field(record, 'note')}</p><${RefreshButton} /></section>`
}
function LibraryView() {
  const [Component, setComponent] = useState(null)
  useEffect(() => {
    const name = 'library'
    import('./views/' + name + '.mjs?cache=1#view').then(module => setComponent(() => module.default))
  }, [])
  return Component ? html`<${Component} />` : html`<p>Opening library</p>`
}
hashRouter({ '/': Overview, '/library': LibraryView, '*': Overview })
function App() {
  const route = useRoute()
  return html`<main><h1>Demo Research Desk</h1><${Nav} items=${[{ path: '/', label: 'Overview' }, { path: '/library', label: 'Library' }]} /><${route.component} /></main>`
}
render(html`<${App} />`, document.getElementById('app'))
window.demo = {
  async probe() {
    let parentBlocked = false
    let fetchBlocked = false
    try { window.parent.document.body } catch { parentBlocked = true }
    try { await fetch('http://127.0.0.1:9/x') } catch { fetchBlocked = true }
    console.log('demo containment', { parentBlocked, fetchBlocked })
    return { parentBlocked, fetchBlocked }
  }
}
