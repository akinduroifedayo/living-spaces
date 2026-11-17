# Draft storage and concurrent records

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
