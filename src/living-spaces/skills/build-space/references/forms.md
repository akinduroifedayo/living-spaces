# Keep an editor draft through navigation and reopen

Create one `createEditorStore(window.space)` in the app shell, outside route and
filter components. Pass that store into each view. Destroy it when the Space
closes. Do not recreate it when a query reloads. Use a stable editor name and
record ID, including for creation. The helper never allocates a new record ID.

```js
import {createEditorStore, useEditor, html, SaveIndicator, ConflictBanner} from 'spaces-kit';
const editors = createEditorStore(window.space);

export function NoteEditor({record}) {
	const edit = useEditor(editors, {
		editor: 'paper-note', schema: 1, collection: 'papers', id: record.id, record,
		select: current => ({notes: current?.data.notes || ''}),
		validate: value => value.notes.trim() ? null : 'Enter a note.'
	});
	return html`<section role="group" aria-label="Edit note">
		<label>Note<textarea value=${edit.value.notes} disabled=${edit.locked}
			onInput=${event => edit.setValue({notes: event.target.value})} /></label>
		<button type="button" disabled=${edit.locked || !edit.dirty} onClick=${edit.save}>Save changes</button>
		<${SaveIndicator} state=${edit.state === 'unknown' ? 'failed' : edit.state} message=${edit.message} />
		${edit.validation && html`<p role="alert">${edit.validation}</p>`}
		${edit.behind && html`<p role="status">This draft is behind the stored record.</p>`}
		${edit.state === 'conflict' && html`<${ConflictBanner} current=${edit.current}
			onKeepMine=${edit.keepMine} onUseUpdated=${edit.useUpdated} />`}
		${edit.state === 'failed' && html`<button type="button" onClick=${edit.retry}>Retry save</button>`}
		${edit.state === 'unknown' && html`<button type="button" onClick=${edit.check}>Check save outcome</button>`}
		<button type="button" disabled=${edit.loading || !!edit.inFlight} onClick=${() => edit.discard()}>Discard draft</button>
		<p role="status">${edit.recoveryMessage}</p>
	</section>`;
}
```

The helper locks input during saving, failure, conflict, and outcome checking.
Bind `disabled` to `locked`. Calls to `setValue` also enforce that lock before
rerender. `inFlight` and `failedPayload` hold `{data, baseRev}` snapshots.
`confirmed` holds the confirmed write result. Only confirmation produces Saved
and clears the host draft. A failed or unknown save keeps the exact payload.
Retry checks proof for an unknown save and never sends the write again.

`Keep mine` reads the authoritative current revision and explicitly retries the
retained payload. A further concurrent edit can conflict again. `Use updated`
reads the authoritative record and discards the draft without writing a record.
The host directs these saves back to the app editor and offers no competing
retry or discard buttons. A broadcast marks `behind` without changing `baseRev`
or the visible draft. The revision advances only on confirmation or a deliberate
recovery choice.

Use explicit `type="button"` actions. Native form submission remains unavailable
under the existing sandbox and CSP. Keep textarea Enter for newlines. The
existing `useSaveState`, `ConflictBanner`, `useCollection`, and `space.put` APIs
remain available with their existing shapes and behavior.

Read [draft storage and concurrent records](records.md) for retention and privacy.
The older Research Desk and habit-planner examples use their existing low-level
save handling. They do not provide durable draft recovery. Apps using this helper
can report reopen recovery only while `recovery === 'durable'`.
