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

The host loads a multi-file project into a sandboxed frame and supplies `window.space`.
Any file types, folder layout, framework or plain JavaScript are fine. The rules
below exist only for isolation, data integrity and resource limits.

**This is the one network rule for Spaces.** The frame has no direct network.
Browser `fetch`, XMLHttpRequest, WebSocket, CDN or remote `import`, remote images,
web fonts and iframe embeds are blocked by the frame's policy and will fail.
To reach the internet, call `space.net.fetch(url, {method, headers, body, as})`.
`as` is `'text'` (default), `'json'` or `'bytes'`. The result always has
`{status, url, headers}` plus `text`, `json` or `{b64, mime}`, respectively.
For JSON use `const response = await space.net.fetch(url, {as: 'json'});`
and then `const data = response.json`. There is no `.body` or `.json()` method.
Check `response.status` before reading a successful payload. HTTP errors return
their status; permission and network failures reject with a typed error.
The Hermes host performs the
request over public HTTPS only. It never sends cookies or credentials, refuses
local and private addresses, and caps responses at 5 MiB. It works while the
Space's "Internet access" permission is on. That is the default, and the user can
turn it off in Permissions. On `not_granted`, show a clear "Internet access is off
for this Space" state rather than an error. Show remote images by fetching them
`as: 'bytes'` and using a `data:` or `blob:` URL. Persist anything the app must
keep in records, not in memory.

Also unavailable in the frame: `localStorage`, IndexedDB, cookies, Node, Hermes
internals and parent-frame access. Do not create a second backend or store user
data in project files.

Project files can be text or binary. Place binary files (PNG, WebP, audio, WOFF2,
vendored libraries) by reference, with one line per file in `files`:
- `{"from_path": "/absolute/path/art.png"}` copies a local file. Use it for
  images from Hermes's image generation tool (hero art, illustrations, sprites)
  and for files you downloaded. The path must be inside the Hermes home, the
  temp folder or your home folder. Credential files (`.env`, `auth.json`, keys,
  tokens, secrets, `.ssh`) are refused.
- `{"from_url": "https://..."}` downloads public HTTPS bytes at write time. Use
  it for fonts, libraries and images. You are fetching, not the Space, so it
  works with the Space's Internet access off. It does not let the frame load
  remote URLs; the file becomes a local project file.
- `{"b64": "<base64>"}` stays for small inline bytes.

MIME follows the path extension, so use the right one. Limits count bytes:
8 MB per file, 25 MB and 600 files per Space. If any entry fails, nothing in that
call is written. Static references in HTML and CSS are resolved at load.
For a path built at runtime (a Preact `src`, `srcset`, SVG `href`, `new Audio()`),
use `space.asset('images/hero.png')`, which returns a frame-local URL or `null`.

The default `libraries` are `preact`, `preact/hooks`, and `spaces-kit`.
The tool copies their local files and adds their bare names to `manifest.imports`.
Add other bundled offline libraries explicitly when the app needs them:
`lightweight-charts`, `htm`, `lucide` (SVG icons), `font:inter` and `font:dm-sans`
(WOFF2 files under `vendor/fonts/`). They are optional. Vendoring your own ESM
library into the project's files also works. Use relative imports for
application modules and local asset paths in HTML/CSS. Do not write an HTML
import map. The host builds it from the manifest.

The kit's behaviour module and visual CSS are independently optional. Link
`kit/spaces-kit.css` before your own `styles.css` only when choosing its base or
canvas materials; otherwise bring your own design system. `manifest.theme` sets a starting point
without CSS edits: `{"preset": "editorial", "tokens": {"bg": "#101418"}}`.
Presets are `editorial`, `terminal`, `playful`, `minimal`, `data`, `journal` and `game`.
Each token becomes a `--space-<name>` CSS variable, and your own CSS still wins.
`accent` only colors the Space's tile in the Spaces tab.

Resource limits: 8 MiB per file, 600 files and 25 MiB per revision,
256 KiB per record, 1 MiB per bridge message. They are generous. Design freely
within them.

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

## Design the canvas (you are the designer here)

A Space is an open canvas that belongs to you, the bot that made it. It has no
house style. The user asked for a thing, and you get to decide how that thing
looks. Make something they would show a friend. If the user names a style or
their own design skill is installed (impeccable or another), follow that
instead. The visual defaults below are suggestions, not templates or limits.
Accessibility, truthful data, permissions and durable-save rules still apply.

### 1. Commit to an art direction before you write code

Choose the surface's mode first: **Operate** for tools and games, **Read** for
documents, **Experience** for a visual piece. A working tool is not a marketing
page: let the work lead, not a decorative welcome screen. Then write a
three-line brief for yourself (a comment in `styles.css` is enough):
- **Concept:** one image from the subject's own world, not "a dashboard".
  Weather could be an observatory, an airport departures board or a
  watercolour almanac. A reading list could be a library card catalogue or
  a broadsheet. A memory game could be a deck of letterpress cards on felt.
- **Material and light:** what the surface is made of (paper, glass, enamel,
  night sky, felt, CRT phosphor) and whether it is light or dark. Choose from
  the scene of use, not the category.
- **Signature:** the one move people will remember, for example a hero
  illustration, a giant typographic numeral, a custom chart shape, a
  texture, or a motion moment.

Then commit to it. Every colour, typeface, radius, icon and empty state should
belong to that concept. When torn between safe and committed, commit. Two
Spaces from the same bot should not look like siblings unless the user asked
for that.

### 2. Build the world with real materials

- **Type:** pick a display face with character and a readable text face.
  Bundle an appropriately licensed WOFF2 and declare `@font-face`; the optional
  `font:inter` / `font:dm-sans` libraries supply local text faces. A font name in
  CSS does not download it. Deliberate system stacks are valid offline fallbacks.
  Use expressive scale when the content earns it, not uniformly tiny type or
  a giant numeral on every screen. Use `clamp()` and tabular numerals for data.
- **Colour:** a ground, an ink and one or two accents with a job. Tint
  neutrals toward the concept's hue. Gradients, grain, glow, glass and deep
  shadows are all fine when they are the material you chose, not a garnish.
- **Depth and texture:** layer the canvas. Background art, a hero band, a
  surface that sits on it. Soft offset shadows, inner light, noise or paper
  texture (an SVG `feTurbulence` filter or a generated tile), and
  `backdrop-filter` all count.
- **Imagery:** give the concept a visual signature where it helps. A reading
  tool can be typographic; imagery is not a mandatory extra request or cost.
  - Generate it. When an approved image tool and cost envelope are available,
    use them for hero art, scene
    illustrations, spot illustrations for empty states, sprites, card backs,
    textures and icon sets. Prompt in the concept's style, and ask for
    transparent PNGs for cut-outs. Do not switch providers or use a paid/API
    fallback to bypass an unavailable tool. Draw SVG instead. Put the result in
    the project: this revision supports `files` with `{"b64", "mime"}`.
    Use a future file-reference route only if the actual tool schema exposes it.
    Reference the asset from CSS or HTML, or through
    `space.asset(path)` at runtime.
  - Draw it. Inline SVG illustrations, patterns and pictograms are cheap and
    crisp: a sun arc, a city skyline silhouette, a card-suit motif.
  - Use the web. When Internet access is on, fetch licensed public imagery
    through the runtime's supported path. **The Runtime section is authoritative:**
    at this revision direct remote images, web fonts, CDN imports and embeds are
    blocked. Use `space.net.fetch(url, {as:'bytes'})` for images, check HTTP
    status, and use the returned `b64` and `mime` as a data URL (or a decoded
    Blob). Release replaced blob URLs. Bundle fonts and libraries locally.
    If a later runtime explicitly enables direct remote assets, use that route
    with load/error fallbacks; never infer capability from an amendment or plan.
  - **Always ship an offline fallback:** a bundled or generated asset, an SVG,
    or a styled placeholder, so the Space still looks finished when Internet
    access is off.
  - Keep source, licence/attribution and generated-art provenance with the
    asset. Size it to its display role; compress large images before bundling.
    Generated art is not a documentary photo or a data visualization. Never
    present an invented skyline, person or condition as observed evidence.
- **Icons:** one consistent family (bundled `lucide`, a web library, or
  your own SVG set). Emoji is fine as a deliberate voice (a game), not as a
  stand-in for an icon system.

### 3. Lay out the job, not a grid of cards

Decide what the user comes back for and make it the hero of the first
viewport. Then arrange the rest by importance, with real size contrast.
- **Dashboard:** one dominant visual that answers the main question (today's
  sky, this week's spend), then supporting measures, then detail on demand.
  Put measure, unit, period and denominator in titles and headers.
- **Mini app / tracker:** the working surface leads (the board, the list, the
  calendar). Creation stays one step away, and status sits close to the
  thing it describes.
- **Game:** the board is the stage. Score, turn and restart are findable
  but quiet. Celebrate a win.
- **Document:** a reading measure of about 65–75ch, generous margins, useful
  headings and imagery set into the text like a magazine.
- **Visual piece / live board:** let the artwork or board fill the stage; do
  not constrain it to a document column. Keep spatial meaning on narrow screens.

Avoid the default look: a row of identical stat cards, then a grid of
same-size cards, all with the same border and radius. Vary the shapes: full
bleed bands, an asymmetric split, a list without boxes, one feature panel.
Never put a card inside a card.

### 4. Make data visual, and make it yours

Charts are part of the art direction. Draw them for this subject:
- a temperature ribbon or a sun-and-moon arc for weather, a radial clock
  for a schedule, a heat calendar for habits, a small-multiples strip for
  cities, a bar of real tiles for game progress, a timeline for research.
- Use local SVG or Canvas, a bundled chart library appropriate to the data
  (`lightweight-charts` is for time series), or a locally vendored dependency.
  Style axes, gridlines and labels in the
  concept's type and colour, or remove them when direct labels read better.
- Keep the numbers honest. Use real calculations, units on every axis or
  label, and a text summary or table on demand. Don't invent trends, and
  never identify a series by colour alone. Compute the domain from all eligible
  values; preserve negative values and meaningful baselines. A sun arc represents
  time, not temperature. A pretty shape is not permission to change the measure.
  Show zero, empty and no-eligible states, not invented fallback values.

### 5. Add motion that means something

Plan one authored moment per view: numbers counting up to a fresh value, the
sun arc drawing in, cards flipping, a new record sliding into place, or a
loading shimmer in the concept's material. Use a short exponential ease-out
(150–400ms for routine feedback). Prefer `transform` and `opacity`; profile
`clip-path`, filters and large blur layers before using them. Keep essential
content visible if animation fails. Under `prefers-reduced-motion: reduce`, show
the end state instead, including drawn strokes and loading indicators. Motion
should not hide a result or delay a control. Offer pause for ongoing ambient art.

### 6. Design every state in the same world

- **First run / empty:** an illustration or scene from the concept, one
  sentence on what belongs here, and the next action. Don't fabricate
  records or metrics.
- **Loading:** a skeleton or shimmer shaped like the real content. Keep
  last-good data and drafts on screen while reloading.
- **Error / offline / Internet off:** stay in character. Name what failed,
  what survived and the recovery action. Say "Internet access is off for this
  Space" only from authoritative host state (`not_granted`). Never draw
  something that looks like the host's permission switch.
- **Saved / conflict:** persistent text (`SaveIndicator`, `ConflictBanner`,
  or your own styled equivalents). No toast-only feedback.
- **Success:** a little delight when a goal is reached.

### 7. Fit any width

The canvas runs from about 320px (narrow window or phone) to 1600px. Use fluid
type (`clamp()`), wrapping grids and container queries. At narrow widths, keep
the hero and the main action in the first screen, stack secondary panels, and
make touch targets at least 44px. Long names wrap and never overflow.

### 8. The floor (keep these whatever the style)

Visible focus rings; labelled inputs and icon buttons; body text at least
4.5:1 contrast (large text 3:1), checked on top of any image or gradient
(add a scrim when needed); status always carries a word or icon, not colour
alone; keyboard paths for every pointer action; reduced-motion alternatives;
light and dark if you rely on the host theme. Check these again after custom
CSS. Before you finish, inspect the running Space at wide, 390px and 320px widths,
200% zoom, long text, keyboard focus and reduced motion; exercise its empty,
loading, error, success and confirmed-save states. Say which checks you actually
ran. A static frame is not evidence of a working save, refresh or game loop.

### The optional kit

`spaces-kit` (JS) gives you behaviour: `useCollection`, `useSaveState`,
`hashRouter`, `Nav`, `SaveIndicator`, `ConflictBanner`, `EmptyState` and
`RefreshButton`. Use it freely. Its markup is plain and easy to restyle.

`kit/spaces-kit.css` is **opt-in**, linked before the app's own `styles.css`.
Use no kit CSS, its quiet base, or one of six optional canvas materials:
`observatory` (night and glass), `letterpress` (paper and ink), `blueprint`
(drafting grid), `felt` (tabletop), `daybreak` (warm light) and `enamel` (bold
colour blocks). Set `data-theme="letterpress"` on **body**. These six are CSS
attributes, **not accepted manifest preset names**. They choose their own light
or dark scheme. They contain no downloaded fonts, generated images or app logic.
Override tokens and composition freely; a material alone is not an art direction.

Useful primitives: `space-hero`, `space-display`, `space-asymmetric`,
`space-ledger`, `space-rail`, `space-panel` and `space-state`. Motion is opt-in:
`space-reveal`, `space-draw`, `space-skeleton--shimmer`; `data-motion="none"`
disables these helpers, and OS reduced motion wins. Keep loading text alongside
decorative skeletons. Read the companion source
[canvas guide](../../runtime/kit/README.md) and
[specimen](../../runtime/kit/canvas-gallery.html) for composition, asset and state
recipes. They demonstrate three different layouts with public synthetic content,
not a mandated starting screen. These docs are source references, not files
automatically copied into each created Space.

`manifest.theme` presets (`editorial`, `terminal`, `playful`, `minimal`,
`data`, `journal`, `game`) only set kit tokens. Treat them as palettes to
start from, not as an art direction. `accent` colours the Space's tile in the
Spaces tab; pick the hue closest to your concept.

References: [Weather Window](references/weather-window/index.html) uses its
own visual language without kit CSS. [Showcase sources](../../runtime/kit/showcase/README.md)
are further technique references, not proof of chat generation or qualification;
consult their verification receipts before claiming live behaviour. Read them
for ambition and technique, not to copy their look.

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
Do not label fixtures as fetched research.

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

## Keep the Space current

Declare upkeep in the manifest. Two handlers exist:

- `upkeep: {handler:'feed', sources:[{id,url,collection,purpose}]}` reads public
  HTTPS RSS or Atom feeds in-process with no model calls. It needs Internet access,
  which is on by default; the user can turn it off in Permissions.
- `upkeep: {handler:'agent', prompt:'...'}` runs a Hermes agent turn that uses
  `spaces_*` tools, writes results with `source_owned=true`, and preserves user
  fields. Each run uses model calls; tell the user so.

Put credentials nowhere in files, records, tool results, or logs.

`spaces_refresh` is Refresh now. A feed Space returns a run: `queued` and
`running` mean in progress; check `spaces_get` recent runs and report success
only for `succeeded`. A successful no-change run is valid. On `blocked`, explain
the reason and the action needed. On `failed`, keep last-good records visible and
describe the error. Show last attempt, last success, and source-as-of separately.
None implies either of the others. An agent Space returns
`{kind:'cron', cron_job_id, triggered:true}`: it triggers the linked Hermes cron
job, or starts a one-time Hermes cron agent run when none is linked. Read the
outcome with `spaces_upkeep` action `status` (`one_shots` for unlinked runs).
The app's `space.refresh()` runs only the feed handler. For an agent Space it
returns `blocked` with reason `agent_from_guest`; agent upkeep runs from Refresh
now in Hermes, from chat, or from the linked cron job.
The frame has `space.runs()`, not a freshness-summary method. Research Desk uses
recent runs and labels that limited window. If no success appears there, say
"No success in recent history", not "Never refreshed". Keep last-good collection
records and mounted editors visible through refresh or query errors.

When the user asks for scheduled upkeep, call `spaces_schedule_upkeep` with
`kind`, `cadence`, an IANA `timezone`, and for `agent` the `prompt`. It creates an
ordinary Hermes cron job now; the user's request is the consent, as for any cron
job. It replaces any existing upkeep job for the Space. The result is the native
job: report its prompt, schedule, and next run exactly as returned. Changing the
manifest prompt later does not change the job; schedule again when the user asks.
Use `spaces_upkeep` with `status`, `pause`, `resume`, `run`, or `remove` to read
or control the job. `missing: true` means the linked job no longer exists.
Archiving pauses the job and unarchiving does not resume it. Scheduled upkeep
needs Hermes available. Catch-up runs one current refresh when Hermes wakes,
without replaying missed intervals.

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

State exactly what changed, the returned revision, any grants that are off, and
any upkeep job you scheduled with its prompt, schedule, and next run. Mention any unresolved warnings or unverified behavior.
Use the actual returned `open.directive`. End create and update replies with
this directive paragraph on its own line, replacing the example ID:

::living-space{id="research-desk"}
