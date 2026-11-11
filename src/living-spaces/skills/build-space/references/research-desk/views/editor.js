import { useEffect, useRef, useState } from 'preact/hooks';
import { html, useSaveState, SaveIndicator, ConflictBanner } from 'spaces-kit';

function fields(record) {
  return { status: record.data.status || 'queued', priority: record.data.priority || 'normal',
    notes: record.data.notes || '' };
}

const draftStores = new WeakMap();
// Volatile drafts belong to this open Space API, never another Space or test.
function store() {
  const api = window.space;
  if (!draftStores.has(api)) draftStores.set(api, new Map());
  return draftStores.get(api);
}

export function Editor({ record, reload }) {
  const drafts = store();
  const remembered = drafts.get(record.id);
  const [base, setBase] = useState(() => remembered?.base || record);
  const [draft, setDraft] = useState(() => remembered?.draft || fields(record));
  const [conflict, setConflict] = useState(() => remembered?.conflict || null);
  const saving = useRef(false);
  const save = useSaveState();
  const dirty = JSON.stringify(draft) !== JSON.stringify(fields(base));
  useEffect(() => {
    if (!dirty && !conflict && save.state !== 'saving') {
      setBase(record);
      setDraft(fields(record));
    }
  }, [record.rev]);
  const change = (name, value) => setDraft(previous => {
    const next = { ...previous, [name]: value };
    drafts.set(record.id, {base, draft: next, conflict});
    return next;
  });
  const submit = async () => {
    if (saving.current || !dirty || conflict) return;
    saving.current = true;
    try {
      await save.run(async () => {
        try {
          const saved = await window.space.put('papers', base.id, draft, { baseRev: base.rev });
          drafts.delete(record.id);
          setBase(saved);
          setConflict(null);
          reload();
          return saved;
        } catch (error) {
          if (error.code === 'conflict') {
            drafts.set(record.id, {base, draft, conflict: error});
            setConflict(error);
          }
          throw error;
        }
      });
    } finally { saving.current = false; }
  };
  const keepDraft = current => {
    drafts.set(record.id, {base: current, draft, conflict: null});
    setBase(current);
    setConflict(null);
  };
  const useUpdated = current => {
    drafts.delete(record.id);
    setBase(current);
    setDraft(fields(current));
    setConflict(null);
  };
  const resolvedConflict = save.state === 'conflict' && !conflict;
  return html`
    <section class="editor space-card" aria-label="Edit paper">
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
        <button class="space-button--primary" type="button" onClick=${submit} disabled=${save.state === 'saving' || !dirty || !!conflict}>Save changes</button>
      </fieldset>
      <${SaveIndicator} state=${resolvedConflict || dirty && save.state === 'saved' ? 'idle' : save.state}
        message=${resolvedConflict ? (dirty ? 'Draft kept. Save changes to retry.' : 'Updated record loaded') : dirty && save.state === 'saved' ? 'Unsaved draft' : save.message} />
      ${dirty && html`<p role="status">You have an unsaved draft. It stays available across views in this open Space, but is not saved until you choose Save changes.</p>`}
      ${conflict && html`
        <${ConflictBanner} current=${conflict.current} onKeepMine=${keepDraft} onUseUpdated=${useUpdated}
          message="This record changed elsewhere. Keep mine preserves your draft for a separate Save changes retry. Use updated discards it." />
        <p role="alert">${conflict.message} Your draft is still above.</p>
        <p>Current saved notes: ${conflict.current.data.notes || '(empty)'}</p>`}
    </section>`;
}
