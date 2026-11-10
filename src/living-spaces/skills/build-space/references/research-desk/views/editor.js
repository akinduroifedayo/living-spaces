import { useEffect, useState } from 'preact/hooks';
import { html, useSaveState, SaveIndicator, ConflictBanner } from 'spaces-kit';

function fields(record) {
  return { status: record.data.status || 'queued', priority: record.data.priority || 'normal',
    notes: record.data.notes || '' };
}

export function Editor({ record, reload }) {
  const [base, setBase] = useState(record);
  const [draft, setDraft] = useState(() => fields(record));
  const [conflict, setConflict] = useState(null);
  const save = useSaveState();
  const dirty = JSON.stringify(draft) !== JSON.stringify(fields(base));
  useEffect(() => {
    if (!dirty && save.state !== 'saving') {
      setBase(record);
      setDraft(fields(record));
    }
  }, [record.rev]);
  const change = (name, value) => setDraft(previous => ({ ...previous, [name]: value }));
  const submit = async event => {
    event.preventDefault();
    try {
      await save.save(async () => {
        try {
          const saved = await window.space.put('papers', base.id, draft, { baseRev: base.rev });
          setBase(saved);
          setConflict(null);
          reload();
          return saved;
        } catch (error) {
          if (error.code === 'conflict') setConflict(error);
          throw error;
        }
      });
    } catch (_) {}
  };
  const reloadCurrent = async () => {
    try {
      const current = await window.space.get('papers', base.id);
      setBase(current);
      setDraft(fields(current));
      setConflict(null);
    } catch (error) { setConflict(error); }
  };
  return html`
    <form class="editor" onSubmit=${submit}>
      <h3>${window.space.field(record, 'title') || 'Untitled'}</h3>
      <p class="summary">${window.space.field(record, 'summary') || 'No summary supplied.'}</p>
      ${record.source_meta && html`<p class="provenance">Source ${record.source_meta.source_id}.
        Retrieved ${new Date(record.source_meta.fetched_at * 1000).toLocaleString()}.</p>`}
      <fieldset disabled=${save.state === 'saving'}>
        <label>Status<select value=${draft.status} onChange=${e => change('status', e.target.value)}>
          <option value="queued">Queued</option><option value="reading">Reading</option><option value="done">Completed</option>
        </select></label>
        <label>Priority<select value=${draft.priority} onChange=${e => change('priority', e.target.value)}>
          <option value="high">High</option><option value="normal">Normal</option><option value="low">Low</option>
        </select></label>
        <label>Notes<textarea rows="5" value=${draft.notes} onInput=${e => change('notes', e.target.value)} /></label>
        <button type="submit" disabled=${!dirty || !!conflict}>Save changes</button>
      </fieldset>
      <${SaveIndicator} state=${dirty && save.state === 'saved' ? 'idle' : save.state}
        message=${dirty && save.state === 'saved' ? 'Unsaved draft' : save.message} />
      ${dirty && html`<p role="status">You have an unsaved draft.</p>`}
      ${conflict && html`
        <${ConflictBanner} error=${conflict} onReload=${reloadCurrent} />
        <section role="alert">
          <p>${conflict.message} Your draft is still above.</p>
          ${conflict.current && html`<p>Current saved notes: ${conflict.current.data?.notes || '(empty)'}</p>`}
          <button type="button" onClick=${reloadCurrent}>Discard draft and load current record</button>
          ${conflict.current && html`<button type="button" onClick=${() => {
            setBase(conflict.current); setConflict(null);
          }}>Keep draft for an explicit retry</button>`}
        </section>`}
    </form>`;
}
