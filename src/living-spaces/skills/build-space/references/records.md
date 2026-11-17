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
