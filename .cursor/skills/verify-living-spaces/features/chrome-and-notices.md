# Gallery chrome and notices

## Sub-features

- **Gallery landing** (`src/desktop/ui/index.jsx`). Each Space shows as a card, `a[href="#/spaces?space=<id>"]`. Its accessible name reads like **Verification Notebook, Ready, owner Hermes. Not refreshed yet.** The preview is `[data-preview="snapshot"]` once a local snapshot exists. Before that it is `[data-preview="fallback"]`, the Space's accent and icon. Snapshots are taken from the open Space's viewport and stored only in this renderer's localStorage (`src/desktop/ui/snapshots.mjs`). Deleting a Space forgets its snapshot. A pinned card carries `.ls-pin` (text **Pinned**) and sorts first. The filter row is **Recent**, **Pinned** (shown only when something is pinned), **Needs attention · N** and **Archived**, captioned **Pinned first, then recently opened**. The create card, `.ls-newcard`, says **Build a Space in chat** and offers **Start a new chat**.
- **Floating island** (`src/desktop/ui/space.jsx:429-445`). This replaces the old header bar. The identity island holds **Back to Spaces**, `header.ls-framebar button[aria-label="Back to Spaces"]`, the Space name, and a freshness phrase in `.ls-frame-meta-text` from `freshnessFacts` (`model.mjs:150-160`). For the fixture, that phrase is **Changed in chat by Hermes · …** after creation and **Edited in this Space · …** after a guest write. The actions island, `.ls-frame-actions`, holds **Internet on** while the net grant is on, **Details**, and **More Space actions** (History, Upkeep, Permissions, Pin/Unpin Space, Archive Space…). **Refresh** appears only when the Space declares a refresh. A Space without one shows no Refresh button at all.
- **Details sheet** (`space.jsx:82-103`). A drawer titled **Space details**, described as **Freshness, storage, access, history and runtime for <name>**. Focus starts on **Close**, and Escape closes the drawer. The sections are:
  - **Freshness**: Latest change, plus *This Space has no refresh of its own…* when there is no refresh, and Upkeep. Action: **Manage upkeep**.
  - **Storage**: the storage notice title and line with a meter, or *Within this Space's storage limits.* Action: **Review storage** (opens History).
  - **Access**: Internet, plus each other grant by its user word (Records, Diagnostic log). Action: **Manage access**.
  - **History**: Revision, and Last refresh when a run exists. Action: **Open history**.
  - **Runtime**: Host **Available** and Space app **Loaded**. The **Backend · needs setup** text sits in the host status bar, outside the drawer.

  Each action opens the matching drawer: **No upkeep yet**, **Internet access**, or **No refresh runs yet.**
- **Notice dock** (`space.jsx:125-200`). The banners stack bottom-right in `.ls-notices`. A notice the dock hasn't shown before collapses it to `.ls-notice-pill` after `NOTICE_COLLAPSE_MS = 8000`. The pill is 89×32 at the fixture's width. Its text is **1 failed** and its accessible name is **1 failed: <title> · <time>. Show notice**. Pointer hover or keyboard focus inside the dock pauses the timer. Leaving restarts it. Escape minimises the dock and focuses the pill. Clicking the pill expands the dock and focuses **Minimise**. Starting to use the canvas also minimises it. Failed notices carry `role="alert"`.
- **Bot request notice** (#6, `model.mjs:60-97`, `space.jsx:30-62`):
  - **Failed**: titled by what's known about delivery. Unbound gives **Hermes didn't receive the request** / *No chat is keeping this Space. Ask Hermes in chat to bind it.* Offline gives **Couldn't reach Hermes**. Unknown gives **Not sure Hermes received the request**. Actions: **Check status**, **Retry same request** (only when there is an activation), **Dismiss** once settled, and **Copy details**.
  - **Reply**: **Hermes replied**, a one-line `.ls-answer-summary` taken from the answer's first prose block, **Read reply** / **Collapse**, and **Dismiss reply**.
  - **Dismissals**: stored per activation in localStorage (`dismissal.mjs`). Passive offline or unknown republishes stay hidden. A user-initiated request shows again.
- **Copy details** (#9, `model.mjs:289-325`). This copies the failure detail plus an absolute time. Live coverage proves the copy itself. Redaction is checked from source only, because the unbound detail carries no credential, so a run without redaction would pass the same check. `diagnosticText` rebuilds a wrapped JSON error from its allowed fields. It redacts everything after the first credential key or Bearer, decoding `\u` escapes first.
- **Storage notice** (#7, `model.mjs:105-121`, `history.jsx:40-55`). It appears from 80% of a storage limit, titled **Storage N% full** with *X of Y used by records. Writes stop at the limit.* The diagnostic log is a rolling history and is not counted. **Hide until it changes** stores the dismissed percentage per Space in localStorage, so the notice returns only when usage changes.

## How to get to it (user POV)

- Open **Spaces** in the Desktop sidebar to see the gallery. Click a card to open the Space. Use **Back to Spaces** to return.
- In a Space, use **Details** for freshness, storage, access, history and runtime, and **More Space actions** for the drawers and lifecycle.
- Bot notices come from a Space asking its maintaining chat. Storage notices come from the Space's own records growing.

## Driving it with control-living-spaces

On a fresh prepared instance with the fixture (see SKILL.md Launch), run:

```sh
"$(dirname "$C")/chrome_journeys.py" --out "$RUN" --clipboard
```

Results are in `chrome-journeys.json`, and every case must be `passed`. The cases are:

- `gallery-card`: fallback preview, card name, create card, filter row.
- `space-island`: Back, More Space actions, Details, Internet on, no Refresh, freshness phrase.
- `notice-unbound-bot`: the fixture's maintaining chat is unbound. Copy details goes through the macOS pasteboard. The case refuses to run when the pasteboard holds anything but plain text, and restores that text afterwards. It must contain `"reason":"unbound"` and no credential words. The copy is saved as `copy-details.txt`.
- `notice-dock-timing`: idle collapse in 7–10 s, a 32 px pill, focus pause, Escape to the focused pill, hover pause, collapse 7–10 s after the pointer leaves, and canvas use minimising the dock.
- `notice-bot-and-storage`: Dismiss, then the fixture's **Ask Hermes** shows the user-initiated failure again. **Fill storage** writes one ~234 KB record and must show **Storage 92% full**. The freshness phrase must change to **Edited in this Space**. **Hide until it changes** must survive leaving and reopening.
- `details-sheet`: all five sections, initial focus, and the three Manage/Open routes.
- `gallery-pin-snapshot`: pin, the snapshot preview with `.ls-pin`, unpin.

Manual checks:

- `"$C" hover --out "$RUN" --value '<css|text=…|corner>'` moves the native pointer.
- `"$C" box --out "$RUN" --value '<selector>'` measures one visible target.
- `"$C" focused --out "$RUN"` reads the focused element.

## Gotchas

- The **Ask Hermes** and **Fill storage** buttons are fixture controls that call the real guest bridge, `space.ask` and `space.put`. They aren't a product surface. **Fill storage** leaves a near-limit record, so run any record-count checks first or on another run.
- A storage hide is keyed by connection, profile and Space id, not by creation, so it survives deleting and recreating a Space with the same id. `chrome_journeys.py` refuses to run when a hide is already stored. Use a fresh instance.
- The unbound failure has no activation id, so **Dismiss** is in-memory only and the notice returns when the Space is reopened. This matches `botDismissed`, which needs an activation.
- **Unreachable here: the reply banner** (Hermes replied, Read reply/Collapse, Dismiss reply, answer summary), Retry same request, and the offline/unknown copy. They need a bound maintaining chat and a model route. The disposable run has neither, because `control.py` launches with `nous.guest: false`, and this skill may not add a provider. These were checked from source only.
- Snapshot previews live in the disposable renderer's localStorage. They are not shared with another Desktop or profile, and a fresh run always starts from fallback cards.
- Phrases that include times (**· 6 sec. ago**) change between reads. Match their prefixes.
