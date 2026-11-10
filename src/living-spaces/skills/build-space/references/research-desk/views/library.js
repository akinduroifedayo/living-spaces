import { useState } from 'preact/hooks';
import { html, useSaveState, SaveIndicator, EmptyState } from 'spaces-kit';
import { Editor } from './editor.js';

export function Library({ records, reload }) {
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState(null);
  const [title, setTitle] = useState('');
  const save = useSaveState();
  const filtered = records.filter(record => ['title', 'summary', 'authors'].map(name =>
    String(window.space.field(record, name) || '')).join(' ').toLowerCase().includes(search.toLowerCase()));
  const detail = records.find(record => record.id === selected?.id) || selected;
  const add = async event => {
    event.preventDefault();
    if (!title.trim()) return;
    try {
      await save.save(async () => {
        const created = await window.space.put('papers', null,
          { title: title.trim(), status: 'queued', priority: 'normal', notes: '' }, { baseRev: 0 });
        setTitle('');
        setSelected(created);
        reload();
        return created;
      });
    } catch (_) {}
  };
  return html`
    <section aria-labelledby="library-heading">
      <h2 id="library-heading">Library</h2>
      <label>Search papers<input type="search" value=${search} onInput=${e => setSearch(e.target.value)} /></label>
      <form class="add-item" onSubmit=${add}>
        <label>New paper title<input required value=${title} onInput=${e => setTitle(e.target.value)} /></label>
        <button disabled=${save.state === 'saving' || !title.trim()}>Add to library</button>
        <${SaveIndicator} state=${title.trim() && save.state === 'saved' ? 'idle' : save.state}
          message=${title.trim() && save.state === 'saved' ? 'Draft not saved' : save.message} />
      </form>
      <div class="split">
        <div><p>${filtered.length} matching papers</p>
          ${filtered.length ? html`<ul class="paper-list">${filtered.map(record => html`
            <li key=${record.id}><button type="button" aria-pressed=${record.id === selected?.id}
              onClick=${() => setSelected(record)}>${window.space.field(record, 'title') || 'Untitled'}</button>
              <small>${record.data.status || 'queued'} · ${record.data.priority || 'normal'}</small></li>`)}</ul>` :
            html`<${EmptyState} title=${search ? 'No matching papers' : 'Your library is empty'}
              message=${search ? 'Try another search.' : 'Add a paper above or approve the public feed refresh.'} />`}
        </div>
        ${detail ? html`<${Editor} key=${detail.id} record=${detail} reload=${reload} />` :
          html`<p class="panel">Select a paper to read its summary and edit your notes.</p>`}
      </div>
    </section>`;
}
