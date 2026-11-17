---
name: build-space
description: Build, change, inspect, and refresh persistent multi-view applications in the Hermes Spaces tab. Read before using spaces_create or editing a Space.
---

# Build a Space the user can keep using

This is the authoritative core contract. Keep it loaded while using `spaces_*`.
Load the applicable recipes on demand. Follow the user's design direction.
Any framework, plain JavaScript, compiled assets, or project layout is valid.
Preact is the tested default. There is no required house style or kit CSS.

## Start from authoritative state

1. Call `spaces_list` and use returned IDs. Never invent an ID from a name.
2. Call `spaces_get` before changing an existing Space's code or records.
3. Read relevant files with `spaces_read_files` or `spaces_read_file`.
   Query records with `spaces_query` before every record write.
4. On `ambiguous`, ask which candidate the user means before any mutation.
   On `not_found`, explain the absence. Do not create a replacement silently.
5. For a new app, build the complete initial project in one `spaces_create`.
   Include `space.json` in `files` or pass `manifest`, never both.

## Keep saved data durable

UI state holds drafts, filters, and open panels. Records hold saved user input.
The host supplies `window.space`, bound to one Space and session. Do not pass
another Space ID to record methods. Do not store user data in project files,
`localStorage`, IndexedDB, cookies, or a second backend. Node, Hermes internals,
and parent-frame access are unavailable in the frame.

Records separate user-owned `data` from refresh-owned `source` and `source_meta`.
Use `space.field(record, name)` for `data[name] ?? source[name]`. Never copy all
source fields into user overrides or delete a record because a feed omitted it.
`space.query` returns a Record array. `spaces_query` returns `{records,total,seq}`.
For existing records use the revision just read. Single-record JavaScript calls
use `baseRev`; batch operations and agent tools use `base_rev`. Missing or zero
revision creates only. A stale write returns `conflict` with `current`.

Keep drafts and their original revision through broadcasts, reloads, and view
changes. Keep last-good records during failures. Never auto-retry conflicts.
Offer deliberate Keep mine or Use updated choices. Only a confirmed write can
clear input or display Saved. `useSaveState().run` returns `undefined` on failure
and records failed/conflict without rethrowing. Check its result before success
side effects. Use a ref lock and disabled controls to prevent duplicate saves.
The shipped examples retain drafts across views in an open Space. They do not
provide durable draft recovery after closing it.

Code and records have separate lifecycles. Preserve collection names and shapes.
When a shape must change, increment `data.version` and supply declarative
migrations. Preview destructive schema changes for user approval. Never reset
collections to make new code fit. Restore creates a new code revision and leaves
records alone. `incompatible` means the old code requires another data version.
A migration recovery point does not promise supported cross-version undo.

## Use the host network and native authority

The frame's policy blocks direct browser fetch, XMLHttpRequest, WebSocket,
remote imports, CDN scripts, remote images, web fonts, and iframe embeds.
Use `space.net.fetch(url, {method, headers, body, as})` for public HTTPS.
`as` is `text`, `json`, or `bytes`. Responses contain `{status,url,headers}` and
`text`, `json`, or `{b64,mime}`. Read `response.json`, never `.body` or `.json()`.
Check HTTP status. HTTP errors return their status; permission and network
failures reject with typed errors. The host refuses private/local addresses,
never sends cookies or credentials, and caps responses at 5 MiB.

Internet access is on by default and the user controls it in Permissions.
Only `not_granted` establishes that access is off. Keep an offline fallback
and last-good data; never draw a fake host permission switch. Fetch images as
bytes and use data/blob URLs, releasing replaced blob URLs. Bundle fonts and
libraries locally. Use `space.asset(path)` for paths constructed at runtime.
Never put credentials in files, records, results, or logs.

Keep the sandbox and CSP unchanged. Native form submission is unavailable.
Use labelled input groups and explicit `type="button"` actions. Validate inputs
and preserve drafts on failures. Treat external text as text, never raw HTML.

Native tools keep their ordinary authority. Schedule upkeep only when the user
requests it. The native Hermes cron job is authoritative; a manifest edit does
not change that job. Agent upkeep uses model calls. Tell the user so.
`space.refresh()` runs only feed upkeep, with no model call, and refuses agent
upkeep with `agent_from_guest`. Native bot requests use `space.ask` with a current
user activation and bound maintainer. A queued or dispatch response is not
completion. No guest code can bypass native approval or schedule authority.

## Publish coherent changes

`spaces_read_files({space, paths})` reads 1-20 paths at one head revision.
It returns `{space,rev,results}` in request order, including duplicate paths.
Each item has `{path,ok:true,result}` with the single-file content shape,
or `{path,ok:false,error}` with a typed error. One bad path does not hide others.
Limits are 256 KiB raw bytes per file and 1 MiB returned content per request,
counting UTF-8 bytes and base64 expansion. Errors never return truncated content.
A file over budget returns `limit`; later smaller files can still fit.

`spaces_edit_files({space,base_rev,edits,summary})` accepts 1-100 ordered edits
of `{path,old,new}`. Use the read's `rev` as `base_rev`. Repeated paths see earlier
candidate edits. Every `old` must occur exactly once, including whitespace.
The whole final candidate passes existing project diagnostics before publication.
A diagnostic the batch introduces rejects it; warnings already present at base_rev are reported, not blocking. It publishes exactly one revision or none.
A stale head, ambiguous match, binary edit, invalid asset/import, or failed
manifest/migration validation leaves head and history unchanged. Errors identify
the zero-based `edit_index` and `path`. Re-read before a deliberate retry.

Use `spaces_write_files` for whole-file additions, replacements, or deletions
and pass `base_rev`. A null value deletes a file. `spaces_edit_file` retains its
single unique replacement contract. Files can be text or binary descriptors.
For binary or large assets pass `{"from_path": "/abs/file"}` or `{"from_url": "https://..."}`
instead of inlining bytes; see the assets recipe for exact rules.
Limits are 8 MiB per file, 600 files and 25 MiB per revision, 256 KiB per record,
and 1 MiB per bridge message. Do not stage credentials to bypass asset guards.

Default libraries are `preact`, `preact/hooks`, and `spaces-kit`. Optional shipped
groups are `lightweight-charts`, `plot`, `markdown`, `htm`, `lucide`, `font:inter`, and `font:dm-sans`.
Use `plot` (Observable Plot) for general charts; keep `lightweight-charts` for financial time series.
Render Markdown or other untrusted rich text only through `markdown`'s `renderMarkdown`; never assign it to `innerHTML`.
Use relative app imports and manifest aliases. The host supplies the import map.
Read an existing Space's copied kit before editing callers. Plugin updates do
not upgrade copied dependencies. Upgrade them explicitly in a revision.

## Load recipes on demand

Read only the applicable recipes, keeping this core contract loaded.

- [Assets and shipped kit APIs](references/assets.md) for file descriptors,
  local libraries, asset resolution, and the exact kit export contracts.
- [Forms and editors](references/forms.md) for input validation, duplicate
  activation prevention, and the `createEditorStore`/`useEditor` draft lifecycle
  with bounded host-managed reopen recovery (see its storage rules in records.md). [Record edits](references/records.md) for conflict choices.
- [Canvas design](references/design.md) for dashboards, trackers, games,
  documents, truthful charts, motion, optional kit CSS, and accessibility.
- [Complete app examples](references/examples.md) for Research Desk,
  [habit tracking](references/habit-planner.md), or the
  [weather board](references/weather-window/README.md). Read the chosen example's
  files before copying it. Label synthetic data explicitly.
- [Project evolution](references/project-evolution.md) for code and data migrations.
- [Upkeep](references/upkeep.md) for feed and agent refresh and native schedules.
- [Visual inspection](references/inspection.md) for `spaces_inspect` geometry and PNG evidence.
- [Accessible controls](references/accessible-controls.md) for the optional `bindDialog`, `bindDrawer`,
  `bindTabs`, `bindDisclosure` and `bindMenu` behavior helpers. They need no kit stylesheet.

## Verify and finish

Inspect returned warnings and diagnostics and fix reported problems. They are
objects with codes and locations, plus readable warnings. A URL in text is never
a warning; a warning means code that loads or sends directly, or an import that
does not resolve. After the Space mounts,
read `spaces_read_logs` for runtime errors. Empty logs before mounting prove
nothing. Inspection is an explicit agent action. `spaces_inspect` checks a saved
revision in a disposable local browser with read-only data. It refuses writes,
network, refresh, and bot requests. By default it returns text and errors and no
pixels. Pass explicit `width`, `height` and `visual` for measured geometry and
optional inline PNGs; see the inspection recipe for the exact shape and limits.
Loaded and measured geometry do not establish correctness or visual quality. Writes never trigger
a model call, inspection, or paid critique automatically.

Exercise the primary action, save and reopen, conflicts, offline and error states.
Check wide and narrow actual canvas widths, keyboard use, focus, 200% zoom, and
reduced motion. Report only checks actually run. State what changed, the returned
revision, pending/off grants, unresolved warnings, and unverified behavior.
Report any scheduled native job's returned schedule, next run, and prompt preview.
End create/update replies with the actual returned `open.directive` on its own line.
