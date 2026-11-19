# Bring local assets and libraries

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
- `{"from_path": "/absolute/path/art.png"}` copies a local file from a supported
  location under the active Hermes home: `cache/images`, `cache/documents`,
  `cache/screenshots`, `cache/vision`, `cache/video`, `cache/videos`,
  `cache/generated/images`, `downloads/connectors`, `images`, or `cache/scratch`.
  Populated legacy `image_cache`, `document_cache`, `browser_screenshots`,
  `temp_vision_images`, `temp_video_files`, and `video_cache` also work.
  The current Python temp directory (`tempfile.gettempdir()`) is allowed too.
  The whole Hermes home, general `cache` and your home folder are not import
  roots. Credential stores stay blocked even when a temp directory overlaps
  them. Cache-root symlinks and parent traversal cannot widen these roots.
  For any other authorized file, use native file or terminal tools under their
  normal policy to copy or build it into a fresh temp staging directory first,
  then pass that staged absolute path. Do not stage credentials to bypass a
  refusal. Any authorized text or binary content, build output, framework or
  project layout is valid; this path boundary is not a generated-images-only
  or application-design restriction.
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
`lightweight-charts`, `plot` (Observable Plot with D3, general charts), `markdown` (marked + DOMPurify safe rich text), `htm`, `lucide` (SVG icons), `font:inter` and `font:dm-sans`
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

Use the `html` tagged template for Preact markup. The browser has no JSX build step. Bring precompiled JSX or use tagged templates. Interpolated strings render as text. Do not insert feed
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
| `readFreshness()` | Resolves to the SQLite-backed freshness summary from `space.freshness()`, including per-source facts across retained run history. It does not read native cron. |
| `useFreshness()` | `{freshness, loading, error, reload}`. Loads the summary and reloads on run events. Keeps the last-good summary on read failure and ignores stale replies. |
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
