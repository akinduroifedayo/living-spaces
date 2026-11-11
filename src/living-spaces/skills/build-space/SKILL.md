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
The examples use the integrated kit's public API below. For an existing Space,
read `kit/spaces-kit.mjs` with `spaces_read_file` before editing its callers.
After creation, check the copied kit too. Adapt callers to that source.

| Export | Actual shape or props |
| --- | --- |
| `useCollection(collection, options)` | `{records: Record[], loading, error, reload}`. `reload()` resolves to records or `undefined` on error. Existing records remain available during a reload or failure. |
| `useSaveState()` | `{state, message, current, run}`. `await run(callback)` returns the callback result after confirmation, or `undefined` on failure. It records `failed` or `conflict` and does not rethrow. |
| `hashRouter(routes)` | Register `{pattern: Component}`, including `/` and optional `*`. Returns `{route, navigate(path), destroy()}`. Register once outside render. |
| `useRoute()` | `{path, params, component, pattern}`. Takes no router argument. Render `route.component`. |
| `Nav` | `{items: [{path, label}], label?}`. Uses the registered router through `useRoute()` internally. |
| `SaveIndicator` | `{state, message?}`. States are `idle`, `saving`, `saved`, `failed`, `conflict`. |
| `ConflictBanner` | `{current, onKeepMine, onUseUpdated, message?}`. Each button passes `current` to its callback. The caller owns rebase, retry, or discard. |
| `EmptyState` | `{title?, children, action?}`. Put explanatory markup in children, and optional button markup in `action`. |
| `RefreshButton` | No props. Requests refresh, follows run events, and reports denial or failure. A queued reply is not completion. |

Keep the active view mounted while `collection.loading` changes. Show a loading
message alongside it. Replacing the view on every requery discards its drafts.
Do not put success side effects after `await save.run(...)` without checking
its result. Run them inside the callback after `space.put` confirms, or check
that the returned record exists. Disable editable creation fields while saving
so a confirmation cannot clear newer input.

## Design the inside, kit first

Compose plain HTML with `kit/spaces-kit.css`; use app CSS only for domain layout.
The kit follows Desktop's light/dark preference. Never hard-code a white canvas,
load web fonts/CDNs, or imitate the host's permission, schedule or chat controls.
Use the system font, semantic tokens (`--space-*`), and real saved records.

- **Shell:** `space-app` → `space-header` (one h1, optional `space-tile` +
  `space-icon`, short description, one primary action) → `Nav` → view. Keep
  view navigation visible and label it; do not put every section in a card.
- **Dashboard:** `space-stat-grid` + `space-card space-stat` for a few useful
  measures, then a wide `space-chart` or table and a supporting list. Name the
  measure, unit, period and denominator. No arbitrary big-number hero.
- **Tracker/planner:** date or period control, `space-list` of labeled
  `space-check` checkboxes, then `space-form-row` for creation. Completion must
  be text/checkmark as well as color; a selected date is not a saved check-in.
- **Document:** `space-document`, readable headings and ≤72ch measure; use
  navigation only for real chapters. **Tool:** input group beside output with
  `space-split`; on narrow screens inputs precede results. Label every field.
- **Game:** `space-game`, visible rules/turn/result, `space-board` with native
  `space-cell` buttons and names (row/column, contents). Keep reset deliberate;
  offer keyboard equivalents to drag, and persist only what the user expects.
- **Multi-view app:** shell + `Nav`, list/detail `space-split`, focused editor.
  Preserve mounted editors/drafts on reload; current location uses aria-current.

Use 14px body, 20px page title, 16px sections (kit defaults). Keep secondary
text readable, numeric table columns `space-numeric`, 12–16px within groups,
24–32px between jobs. `space-card` groups related work, never another card.
Tile accents (`data-accent="blue|green|amber|purple|teal|rose|orange|grey"`)
identify subjects, not status. `space-tile` is for a meaningful app/subject icon,
not decoration on every block. Decorative `space-icon` spans need aria-hidden;
icon-only controls need an accessible name. Available icons are in the CSS.

Use `space-button--primary` once per task group; secondary buttons are default.
Use labels, native inputs, visible required hints and nearby `space-field-error`
text with aria-describedby/aria-invalid. Default controls are 36px, 44px on
narrow screens. Never hide focus. Do not reduce disabled controls to opacity.

First run: `EmptyState` says what belongs here and the next action; no fake
records or congratulatory metrics. Distinguish empty search from no records.
Keep last-good data during load/failure; `space-loading` + role=status names
what is loading. Skeletons are optional, aria-hidden, with real loading text.
Use `space-notice space-notice--error` + role=alert for new failures, state what
was retained and provide a real retry. SaveIndicator and ConflictBanner retain
truthful text; never rely on tint, a spinner, or a disappearing toast alone.

Charts: use bundled lightweight-charts only when needed, or accessible local
SVG/CSS for simple plots. `space-chart`/`space-chart-plot` provide a frame, not
a calculation. Use real domain calculations; label axes, units and series, give
an equivalent table/summary, and handle empty/no-eligible data without a fake
trend. Series need labels or patterns, not color alone. Respect reduced motion.

Avoid gradients/glass, emoji-as-icons, eyebrow kickers, decorative sparklines,
card-inside-card layouts, giant stacked forms, invented freshness, and fixed
widths that overflow. Check light/dark, narrow width, long text, keyboard focus,
loading/empty/error and a real confirmed-save path before calling it finished.
See the [kit gallery](references/kit-gallery.html) for composable markup and
[Three in a row](references/three-in-a-row.md) for a small game.

## JavaScript-controlled forms

The accepted frame has `sandbox="allow-scripts"` and CSP `form-action 'none'`.
Native form submission is unavailable, including a form's `onSubmit` callback.
Use labeled inputs in a `div role="group"` or a section, and explicit
`type="button"` actions with `onClick`. Keep the sandbox and CSP unchanged.
Do not use `requestSubmit()`, submit buttons, or a global form handler as a fix.

Validate required controls with `reportValidity()` inside the action and reject
blank trimmed values. Use a ref lock as well as disabled controls so repeated
activation before rerender cannot write twice. Import `useRef` from
`preact/hooks`. For example, inside a component with `title`, `setTitle`,
`reload`, and `save = useSaveState()`:

```js
const titleInput = useRef(null);
const saving = useRef(false);
const add = async () => {
  if (saving.current || titleInput.current?.reportValidity() === false || !title.trim()) return;
  saving.current = true;
  try {
    await save.run(async () => {
      const created = await space.put('papers', null, {title: title.trim()}, {baseRev: 0});
      setTitle('');
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
return html`<div role="group" aria-label="Add a paper">
  <label>Title<input ref=${titleInput} required value=${title} disabled=${save.state === 'saving'}
    onInput=${e => setTitle(e.target.value)} onKeyDown=${addOnEnter} /></label>
  <button type="button" onClick=${add} disabled=${save.state === 'saving' || !title.trim()}>Add paper</button>
  <${SaveIndicator} state=${title.trim() && save.state === 'saved' ? 'idle' : save.state}
    message=${title.trim() && save.state === 'saved' ? 'Draft not saved' : save.message} />
</div>`;
```

Attach Enter activation only to single-line creation fields. Ignore composition,
key repeats, and modifier keys. Leave textarea Enter available for newlines;
do not put this handler on the group or editor. Save editor changes with its
explicit button. Preserve drafts on failure and existing explicit conflict
choices. Only confirmed writes may clear input or show Saved.

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
The frame has `space.runs()`, not a freshness-summary method. Research Desk uses
recent runs and labels that limited window. If no success appears there, say
"No success in recent history", not "Never refreshed". Keep last-good collection
records and mounted editors visible through refresh or query errors.

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
