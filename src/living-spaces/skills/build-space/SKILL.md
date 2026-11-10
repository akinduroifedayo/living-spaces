---
name: build-space
description: Build, change, inspect, and refresh persistent multi-view applications in the Hermes Spaces tab. Read before using spaces_create or editing a Space.
---

# Build a Space the user can keep using

Use the `spaces_*` tools when the user asks to build an app, change a Space,
ask what is in it, or keep its data current. Work in normal Hermes chat.
Build the requested application, including navigation, forms, and durable data.
Research Desk is an example. Planners, games, documents, and other apps are valid.

## Start with the existing state

1. Call `spaces_list`. Use returned IDs. Never invent an ID from a display name.
2. For an existing Space, call `spaces_get` before changing code or records.
   Read the relevant files with `spaces_read_file` and records with `spaces_query`.
3. `space` accepts an ID or an exact name. On `ambiguous`, show the candidates
   and ask which Space the user means. Do not mutate anything until resolved.
   On `not_found`, explain what is missing. Do not silently create a replacement.
4. For a new app, choose views and collections that fit the request. Build the
   complete initial project in one `spaces_create` call. Include `space.json` in
   `files`, or pass the same object as `manifest`, never both.

Before writing, decide what must persist. A UI state variable holds a draft,
search text, or an open panel. A record holds saved user input.
Never describe unsaved UI state as saved.

## Runtime and project files

The host loads a multi-file project into a sandbox and supplies `window.space`.
The app cannot use the network. Obtain all persistent data through `space`.
Do not use `fetch`, XMLHttpRequest, WebSocket, CDN imports, remote images,
`localStorage`, IndexedDB, Node, Hermes internals, or parent-frame access.
Do not create a second backend or store user data in project files.

The default `libraries` are `preact`, `preact/hooks`, and `spaces-kit`.
The tool copies their local files and adds their bare names to `manifest.imports`.
Add `lightweight-charts` explicitly when the app needs it.
Use relative imports for application modules and local asset paths in HTML/CSS.
Link `kit/spaces-kit.css` before your own `styles.css`.
Do not write an HTML import map. The host builds it from the manifest.

```js
import { render } from 'preact';
import { useState } from 'preact/hooks';
import { html, useCollection, useSaveState, hashRouter, useRoute,
  SaveIndicator, ConflictBanner, EmptyState, Nav, RefreshButton } from 'spaces-kit';
const space = window.space;
```

Use the `html` tagged template for Preact markup. Do not write JSX because there
is no JSX build step. Interpolated strings render as text. Do not insert feed
summaries as raw HTML. Keep an app shell, navigation, and view modules.
Use hash routes so reopening or switching views does not navigate outside the app.

Use `useCollection` to subscribe to saved records, including chat edits.
Use `useSaveState`, `SaveIndicator`, and `ConflictBanner` for durable save feedback.
Use `EmptyState` for an empty collection or an empty search result.
`RefreshButton` invokes the declared refresh through the bridge.
The complete example below shows the helper calls. After creating a Space,
call `spaces_get`, then read `kit/spaces-kit.mjs` with `spaces_read_file` to
confirm hook result fields and component props. The copied kit is authoritative.
If its signatures differ, adapt the calls before handing the app to the user.

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
explicitly retry the draft against its new revision. Never auto-retry a conflict
and never show `Saved` after failure. Use `batch` for changes that must commit
together. A failed batch commits nothing.

The bridge also exposes `space.refresh()`, `space.runs()`,
`space.on('change', callback)`, and `space.on('run', callback)`.
Subscriptions return unsubscribe functions. Clean up subscriptions on unmount.
`space.meta` contains `{space:{id,name,rev},grants}`. Do not pass a Space ID to
record methods. The host binds this app to one Space and session.

For chat writes, query first, then send only intended `data` fields through
`spaces_write_records`. Preserve every `base_rev`. A conflict requires another
read and a deliberate retry. These records are the same ones the running app uses.

## Build from a complete example

Read all files in [Research Desk](references/research-desk/index.html) before
using this example. Copy their contents into the create tool's `files` object
under these paths. Do not send filesystem paths as file contents.

- [space.json](references/research-desk/space.json) declares collections and a public feed.
- [index.html](references/research-desk/index.html) loads CSS and the application module.
- [app.js](references/research-desk/app.js) provides the shared store and navigation.
- [views/overview.js](references/research-desk/views/overview.js) shows counts and source/run timestamps.
- [views/library.js](references/research-desk/views/library.js) implements search, creation, and detail.
- [views/queue.js](references/research-desk/views/queue.js) edits status, priority, and notes.
- [views/editor.js](references/research-desk/views/editor.js) preserves drafts and resolves conflicts.
- [styles.css](references/research-desk/styles.css) defines the layout.

The app starts with an honest empty state. Create a clearly labeled demo record
through its form or `spaces_write_records` if the user wants sample content.
Do not label fixtures as fetched research. Public refresh needs approval.

For a different application, read the [habit planner](references/habit-planner.md).
It stores daily check-ins without a feed or schedule.
Use the same record, revision, and save rules for games and other applications.

## Evolve without losing data

Read current files and the manifest. Use `spaces_edit_file` for a unique exact
replacement. If it reports zero or multiple matches, read again and choose a
longer unique snippet. Use `spaces_write_files` for multiple whole-file changes.
Pass `base_rev` equal to the `head_rev` just read. A stale head is `conflict`.
Re-read before retrying. A file value of `null` deletes that file.

Keep the collection names and stored shape unless the feature needs a migration.
When changing shape, increment `data.version` and include declarative migrations
in `space.json`. Example for version 1 to 2:

```json
{"data":{"version":2,"collections":{"papers":{"description":"Library items"}},
"migrations":[{"to":2,"ops":[
  {"op":"rename_field","collection":"papers","from":"stat","to":"status"},
  {"op":"set_default","collection":"papers","field":"priority","value":"normal"}
]}]}}
```

Supported operations are `rename_field`, `set_default`, `delete_field`,
`rename_collection`, and `copy_collection`. The host creates a recovery point.
Preview destructive schema changes for user approval. Never reset collections
to make new code fit old data. Code and records have separate lifecycles.

## Keep public data current

Declare `upkeep: {handler:'feed', sources:[{id,url,collection,purpose}]}` in the
manifest. Use public HTTPS RSS or Atom feeds. Put credentials nowhere in files,
records, tool results, or logs. Release 1 supports the host-owned `feed` handler,
not arbitrary background Python or tool calls from the app.

The manifest requests a scoped Refresh grant. The user approves it in the
Space's Permissions. Until then, say Refresh is pending. Changing source hosts
requests approval again. A tool cannot grant its own request.

`spaces_refresh` invokes the same handler as the app's Refresh button.
Read its result and check `spaces_get` recent runs. `queued` and `running` mean
in progress. Report success only for `succeeded`. A successful no-change run is
valid. On `blocked`, explain the reason and the action needed. On `failed`, keep
last-good records visible and describe the error. Show last attempt, last success,
and source-as-of separately. None implies either of the others.

For a requested cadence, call `spaces_request_schedule` with cadence, IANA
timezone, and purpose. It requests approval in the tab. It does not activate a
schedule. Never create cron jobs yourself. Never claim a schedule is active
until a tool result reports `active`. Scheduled refresh needs Hermes available.
Catch-up runs one current refresh when Hermes wakes, without replaying missed intervals.

## Check and repair

After a create or code change, inspect `warnings` and fix them. Tell the user
to open the Space. After it has mounted, call `spaces_read_logs` for runtime
errors, import failures, and policy violations. Empty logs before mounting do
not prove it works. Fix errors with `spaces_edit_file` and check again.

Use `spaces_revisions` to inspect history and `spaces_restore` to recover a
working code revision. Restore creates a new revision and leaves records alone.
`incompatible` means the old code expects another data version. Explain that
instead of forcing a restore. Do not claim a sandbox or restart test you did not run.

## Finish the chat reply

State exactly what changed, the returned revision, and which grants or schedule
approvals remain pending. Mention any unresolved warnings or unverified behavior.
Use the actual returned `open.directive`. End create and update replies with
this directive paragraph on its own line, replacing the example ID:

::living-space{id="research-desk"}
