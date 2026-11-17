## Records and concurrent edits

A record is `{collection,id,data,source,source_meta,rev,created_at,updated_at,updated_by}`.
`data` contains user-owned values such as notes, status, and priority.
Refresh fills `source` and `source_meta` with public content and provenance.
Read display values with `space.field(record, 'title')`, which returns
`record.data.title ?? record.source.title`.
Never copy all source fields into `data`. That would freeze old feed values as
user overrides. Never erase a source record because it disappeared from a feed.

```js
const records = await space.query('papers', {limit: 500}); // Record[], not {records}
// Collections larger than one page: space.queryPage('papers', {limit: 200, cursor}) returns {records, has_more, next_cursor}.
// On SpaceError code 'cursor_expired' the data changed; restart from the first page instead of showing a partial list.
const current = await space.get('papers', recordId);
const saved = await space.put('papers', current.id,
  {notes: draftNotes, status: 'reading'}, {baseRev: current.rev});
await space.put('papers', null, {title: 'Demo note', status: 'queued'}, {baseRev: 0});
await space.delete('papers', saved.id, {baseRev: saved.rev});
await space.batch([
  {op: 'put', collection: 'papers', id: a.id, data: {status: 'done'}, base_rev: a.rev},
  {op: 'put', collection: 'papers', id: b.id, data: {status: 'done'}, base_rev: b.rev}
]);
```

Single-record JavaScript calls use `baseRev`. Batch operations and agent tools
use `base_rev`. For an existing record, always send its current revision.
Missing `baseRev` or `0` creates only. A stale revision throws `conflict` with
`current`. Keep the user's draft visible. Offer to reload the current record or
explicitly retry the draft against its new revision. `ConflictBanner` calls
`onKeepMine(current)` and `onUseUpdated(current)`.
Research Desk's Keep mine rebases the retained draft to `current.rev`; a separate
Save changes click retries it. The habit planner's Keep mine is itself the
explicit retry and preserves the intended boolean rather than toggling it again.
Use updated discards the draft and adopts or reloads authoritative values.
Never auto-retry a conflict and never show `Saved` after failure.
Use `batch` for changes that must commit together. A failed batch commits nothing.

The bridge also exposes `space.refresh()`, `space.runs()`,
`space.on('change', callback)`, and `space.on('run', callback)`.
Subscriptions return unsubscribe functions. Clean up subscriptions on unmount.
`space.meta` contains `{space:{id,name,rev},grants}`. Do not pass a Space ID to
record methods. The host binds this app to one Space and session.

For chat writes, query first, then send only intended `data` fields through
`spaces_write_records`. Preserve every `base_rev`. A conflict requires another
read and a deliberate retry. These records are the same ones the running app uses.

## Draft storage for the kit editor helper

A draft is unsaved editor content. It is separate from user records, source
fields, project files, and recovery-point snapshots. The kit editor uses a
host-managed `editor_drafts` namespace in the owning profile database. It uses
no localStorage, IndexedDB, or cookies. Do not put draft contents in logs or
inspection diagnostics. Draft contents are stored as local plaintext with the
same filesystem authority as the profile database, without new encryption.

The key is profile database, Space, editor name, editor schema, collection, and
record ID. Guests cannot select the profile or Space. Every operation requires
a live Space-bound session and the data grant, including a fresh check before
reply delivery. A closed session's late reply cannot reach a new session.
Space deletion cascades to its drafts. Closing the Space retains its drafts.

Each profile retains at most 100 drafts and 1 MiB of encoded draft content.
Each draft is at most 64 KiB of UTF-8 JSON. Expiry is seven days after the last
write. Reads do not extend expiry. Each draft operation first deletes expired
entries, then evicts the oldest `updated_at` entries until both limits hold.
Ties sort by Space, editor, schema, collection, and record ID. Oversized entries
are rejected without replacing the existing draft. Expiry is lazy, so an idle
database can retain expired bytes until its next draft operation.

Use a new positive integer `schema` when the editor's value shape changes.
Recovery requires the same editor schema, kit draft format version 1, and Space
data version. A changed Space data version removes incompatible drafts on the
next draft operation. Code-only revisions retain compatible drafts. Drafts in
other editor schemas remain isolated until expiry or eviction.

Mount `useEditor(store, config)` with the current saved `record`, or `null` for
creation. Supply `initial` for a new record, or `select(record)` for a specific
set of editable fields. Save only user-owned fields, never copied feed values.
Use a stable explicit record ID for creation, and `baseRev` starts at zero.
The helper retains its original base during broadcasts and unmounts. It does
not silently rebase. See [the editor recipe](forms.md).

`store.editor(config)` exposes the same controller without hooks. Its `snapshot`
contains value, baseValue, baseRev, dirty, validation, inFlight, locked, confirmed,
failedPayload, conflictChoice, current, behind, state, message, loading, recovery,
and recoveryMessage. `ready` resolves after the initial recovery read. `flush()`
waits for queued draft persistence. A returned save record confirms success.
An unsuccessful save resolves to `undefined` and keeps recovery state visible.

Draft writes serialize before saves. The host atomically commits a record and
clears that editor's draft. Explicit discard also clears it. If the service is
missing, denied, over capacity, or unavailable, the draft remains in memory and
`recovery` becomes `memory` with an explicit message. Never claim reopen recovery
in that state. Closing before an outstanding draft write confirms can lose the
latest input. A later successful draft write restores the recovery status.

The new guest methods are `space.drafts.get(key)`, `put({...key, draft})`, and
`delete(key)`, plus `space.editor.save({...key, data, base_rev, request_id})` and
`space.editor.outcome({...key, request_id})`. They serve the kit helper, not a
second record API. `editor.save` uses the existing durable bridge receipt
transaction. `editor.outcome` calls `outcome.get` with a complete editor key.
That optional key permits proof lookup across previous sessions of the same
Space incarnation while requiring current session admission and data authority.
The original `{request_id}` outcome lookup remains bound to its original session.
A missing receipt stays unknown even if the current record happens to match.
No failed or uncertain write is retried automatically.
