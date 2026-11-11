import { useRef, useState } from 'preact/hooks';
import { html, useSaveState, SaveIndicator, EmptyState } from 'spaces-kit';
import { Editor } from './editor.js';

export function Library({ records, reload }) {
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState(null);
  const [title, setTitle] = useState('');
  const titleInput = useRef(null);
  const saving = useRef(false);
  const save = useSaveState();
  const filtered = records.filter(record => ['title', 'summary', 'authors'].map(name =>
    String(window.space.field(record, name) || '')).join(' ').toLowerCase().includes(search.toLowerCase()));
  const detail = records.find(record => record.id === selected?.id) || selected;
  const add = async () => {
    if (saving.current || titleInput.current?.reportValidity() === false || !title.trim()) return;
    saving.current = true;
    try {
      await save.run(async () => {
        const created = await window.space.put('papers', null,
          { title: title.trim(), status: 'queued', priority: 'normal', notes: '' }, { baseRev: 0 });
        setTitle('');
        setSelected(created);
        reload();
        return created;
      });
    } finally { saving.current = false; }
  };
  const addOnEnter = event => {
    if (event.key !== 'Enter' || event.isComposing || event.keyCode === 229 || event.repeat ||
        event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
    event.preventDefault();
    return add();
  };
  return html`
    <section aria-labelledby="library-heading">
      <h2 id="library-heading">Library</h2>
      <label>Search papers<input type="search" value=${search} onInput=${e => setSearch(e.target.value)} /></label>
      <div class="add-item space-form-row" role="group" aria-label="Add a paper">
        <label>New paper title<input ref=${titleInput} required disabled=${save.state === 'saving'} value=${title}
          onInput=${e => setTitle(e.target.value)} onKeyDown=${addOnEnter} /></label>
        <button class="space-button--primary" type="button" onClick=${add} disabled=${save.state === 'saving' || !title.trim()}>Add to library</button>
        <${SaveIndicator} state=${title.trim() && save.state === 'saved' ? 'idle' : save.state}
          message=${title.trim() && save.state === 'saved' ? 'Draft not saved' : save.message} />
      </div>
      <div class="split space-split">
        <div><p>${filtered.length} matching papers</p>
          ${filtered.length ? html`<ul class="paper-list space-list">${filtered.map(record => html`
            <li key=${record.id}><button class="space-list-button" type="button" aria-pressed=${record.id === selected?.id}
              onClick=${() => setSelected(record)}>${window.space.field(record, 'title') || 'Untitled'}</button>
              <small>${record.data.status || 'queued'} · ${record.data.priority || 'normal'}</small></li>`)}</ul>` :
            html`<${EmptyState} title=${search ? 'No matching papers' : 'Your library is empty'}>
              <p>${search ? 'Try another search.' : 'Add a paper above or approve the public feed refresh.'}</p><//>`}
        </div>
        ${detail ? html`<${Editor} key=${detail.id} record=${detail} reload=${reload} />` :
          html`<p class="space-empty">Select a paper to read its summary and edit your notes.</p>`}
      </div>
    </section>`;
}
