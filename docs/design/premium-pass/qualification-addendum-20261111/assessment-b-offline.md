# Assessment B — independent offline detector and technical audit

Method: isolated Assessment B subagent; source-only. Assessment A was not read. Browser evidence deliberately withheld by owner, not unavailable tooling. This is the B contribution, not a completed combined critique or live release qualification.

## Outcome and provenance

**Implementation coherence: pass at source level; implementation integrity is not clean.** The host uses native SDK controls and factual state models, while the canvases have distinct, intentional materials. The detector does not establish a generic-design failure. Manual review nevertheless found concrete recovery-copy and data-validation defects, a bounded-history correctness issue, and a paint-cost risk.

- Target: `/Volumes/Expansion/Development/Build/r1-qualification-t_b3b306df/snapshot/src/living-spaces/`.
- Supplied frozen integration identity: **`2b93cf8dd12b177ba73e0150afac252afaf25d5c`**. This is **not** the final submission pin. The snapshot and assigned workspace are not Git repositories (`git rev-parse HEAD` returned 128); this assessment preserves the supplied pin rather than claiming to have independently resolved it from Git. `b-source-manifest.json` fingerprints detector-scope files, and the scan runner verified those bytes unchanged across its run.
- Relevant product direction: `snapshot/docs/design/DIRECTION.md` and `snapshot/docs/design/premium-pass/final-review/HOST-CHROME-SPEC.md`. Their own historical verification/status qualifications remain intact. Their accepted semantics were used as instructed, not treated as present-day runtime evidence.
- No live app, CDP, browser, store, native turn, provider, service, install, restart, or source modification. No screenshot or prior Assessment B receipt was used to prove current behavior. No overlay was injected or claimed.
- Old host and Sky 11 / Research 18 / Pair 10 captures do not qualify this integration. The supplied newer store revisions 12 / 19 / 11 lack matching terminal-turn/capture evidence; **this audit neither inspected nor qualified them**. Source-reference issues below must not be relabeled as observed defects of those store revisions.
- Parent already completed Impeccable context loading. No context rerun, PRODUCT.md, DESIGN.md, critique-storage write, or design-system replacement was performed. No `ignore.md` was found in the snapshot filename search.

All code paths below are relative to the frozen package root unless explicitly prefixed `snapshot/docs/`. Line numbers refer to the exact frozen files, including the built `desktop/plugin.js`, not its original JSX comments.

## Actual bundled detector execution

Installed engine: `/Users/ifedayoakinduro/.impeccable/bin/0.1.16/impeccable`, reached through the requested launcher. `IMPECCABLE_BIN` pins that existing executable; `IMPECCABLE_LAUNCHER_PROBE=1` prevents launcher download fallback. The engine SHA-256 is retained in `b-scan-summary.json`.

Command shape (each exact absolute command and cwd is retained separately):

```sh
IMPECCABLE_BIN=/Users/ifedayoakinduro/.impeccable/bin/0.1.16/impeccable IMPECCABLE_LAUNCHER_PROBE=1 /Users/ifedayoakinduro/.hermes/skills/creative/impeccable/scripts/impeccable detect --json <existing-source-target>
```

Cwd: `/Users/ifedayoakinduro/.hermes/kanban/workspaces/t_b3b306df`.

| Receipt stem | Target | Exit | JSON findings | Limitation |
|---|---|---:|---:|---|
| `b-scan-host` | `desktop/plugin.js` | 0 | 0 | Built JSX-runtime calls and embedded CSS; empty scan is not host DOM coverage. |
| `b-scan-guest` | `guest/space-host.html` | 0 | 0 | Relay/escaped srcdoc, not the assembled canvas DOM. |
| `b-scan-sky` | `runtime/kit/showcase/sky-window` | 2 | 3 | Existing markup with linked stylesheet, not computed or pixel evidence. |
| `b-scan-pair` | `runtime/kit/showcase/pair-play` | 0 | 0 | Dynamic buttons and score state still require manual source review and later live testing. |
| `b-scan-research` | `skills/build-space/references/research-desk` | 0 | 0 | **Incomplete linked CSS coverage**, warning below; empty HTML app root. |
| `b-scan-kit` | `runtime/kit/spaces-kit.mjs` | 0 | 0 | Template/source scan, not instantiated components. |
| `b-scan-kit-markup` | `runtime/kit/canvas-gallery.html` | 0 | 1 advisory | Supplemental existing markup to exercise the linked kit stylesheet; specimen, not a submitted canvas. |

Each stem has `.command.txt`, `.stdout`, `.stderr`, and `.exit` files containing the exact command, raw output streams, and process exit. There are **4 raw findings: 2 warnings and 2 advisories**. Three belong to Sky; the fourth belongs only to the supplemental kit specimen. The advisory-only scan returned **0 despite nonempty JSON**; do not infer finding count from exit alone. No entrypoint failure was encountered.

Research stderr, verbatim:

```text
impeccable detect: could not read linked stylesheet ./kit/spaces-kit.css (resolved to /Volumes/Expansion/Development/Build/r1-qualification-t_b3b306df/snapshot/src/living-spaces/skills/build-space/references/research-desk/kit/spaces-kit.css); color and custom-property rules will be incomplete
```

This is a **scan limitation, not proof of a broken deployed stylesheet**. Research `index.html:7` requests that project-relative library; `living_spaces_core/projects.py:20–22,120–138` supplies kit files when the library is selected. The actual packaged stylesheet was read manually, and the existing `canvas-gallery.html:6` was scanned as a supplement. Nothing was copied into the frozen reference to manufacture a successful scan.

### Verify every raw finding in source

All detector locations are reported as markup **line 0**, not actionable CSS lines. These are the verified origins and dispositions:

| Rule / severity | Verified source | Disposition |
|---|---|---|
| `dark-glow` / warning | Sky `styles.css:58–65`: warm zero-offset shadows on `.orb`; `app.js:144–161` derives its sky phase and position from weather/local hour. | Pattern exists. **Contextual false positive as a generic shortcut verdict**: this is a sun/moon illustration, not a glowing action control. Preserve the authored metaphor; no automatic redesign. Pixel contrast and paint cost remain untested. |
| `radial-halo` / warning | Sky `styles.css:22–27`: dark room background with `#18214a` / `#2a1838` radial washes. | Pattern exists and is decorative. **Visual judgment deferred**, not a technical defect or proven false positive. The night-room direction is explicit at `styles.css:1–6`; source alone cannot establish whether it overwhelms data. |
| `repeating-stripes-gradient` / advisory | Sky `styles.css:87–94`: rain/storm weather layer, conditional on `data-kind`; `app.js:146,157` supplies the condition. | Pattern exists. **Contextual false positive as unrelated decoration**: stripes encode precipitation. The separately identified animation-property risk below does not invalidate the weather metaphor. |
| `codex-grid-background` / advisory | Kit `spaces-kit.css:372–385`: optional `[data-theme="blueprint"]` drafting grid. Gallery links this stylesheet at `canvas-gallery.html:6`. | Verified optional specimen/preset, **not evidence that host, Research editorial, Sky, or Pair uses a decorative grid**. Do not transfer this finding to submitted surfaces. It is explicitly a blueprint material. |

The deterministic findings are not the manual technical findings below. None proves an observed runtime defect.

## Audit dimensions — evidence-limited scoring

| Dimension | Score | Evidence-supported conclusion |
|---|---|---|
| Accessibility | **Unscored** | Native buttons, labels, live regions, focus hooks and reduced-motion rules exist. WCAG AA, actual focus order/retention, announcements and contrast were not exercised. |
| Performance | **Unscored** | Visibility-aware polling and resize debounce exist; Sky animates a paint property. No timings, traces, bundle audit, memory or frame-budget measurements. |
| Theming | **Unscored** | Host semantic tokens, kit light/dark definitions, and intentionally fixed-material showcase palettes are source-visible. Theme propagation, computed values and rendered contrast are unknown. |
| Responsive layout | **Unscored** | Explicit host/canvas breakpoints and scroll alternatives are present. No viewport, zoom, large-text, hit-box or gesture execution. |
| Implementation integrity | **2/4 — source-only** | Several verified issues in recovery language, input validation and history scope; coherent product-specific structure otherwise. Detector warnings do not themselves lower this score. |

**No total, rating band, `/20`, or release-quality percentage is asserted.** Unscored means unknown, not zero and not passed.

## Prioritized source findings and practical fixes

Four priorities: **2 P1, 2 P2; no P0 or P3 assigned**. These are source findings/risk priorities, not four reproduced runtime failures. Fixes are recommendations only.

### B-01 · P1 · Research directs people to a nonexistent Refresh permission

**Category:** Implementation integrity / recovery copy.

**Evidence:** `skills/build-space/references/research-desk/views/overview.js:33,40–41` instructs users to “Approve Refresh” in Permissions. The shared error branch repeats it at `runtime/kit/spaces-kit.mjs:230–231`, reached by Research's `app.js:39`. In contrast, the frozen bridge declares `refresh` with no capability gate at `living_spaces_core/bridge.py:5–16,55–56`; host permissions render Internet access, Own data and Diagnostics (`desktop/plugin.js:504–509,580–598`). `snapshot/docs/design/DIRECTION.md:47` expressly says there is no Refresh grant.

**Impact:** The empty-library/freshness guidance sends a first-time user to a control that does not exist. The shared catch path also offers an impossible recovery if `not_granted` reaches it. This is a source-proven instruction mismatch, not proof that a particular refresh failed live.

**Fix:** Replace both unconditional Overview instructions with “Turn on Internet access in the Space's Permissions, then refresh the public feed.” In the shared handler, map the actual capability/reason instead of inventing a Refresh grant; if the cause is unknown, preserve the server message and direct the user to host run details. Keep owner/upkeep failures distinct from Internet access. Verify the no-grant, blocked-owner and healthy-feed branches after custody is released.

**Standard:** Product permission contract and actionable recovery; no WCAG conformance claim. **Suggested command:** `/impeccable clarify`.

### B-02 · P1 · Sky accepts an empty sunset array, then dereferences it

**Category:** Implementation integrity / error resilience.

**Evidence:** `runtime/kit/showcase/sky-window/app.js:93–100` validates the lengths and values of several daily arrays, but tests sunset only with `d.daily.sunset?.every(v => typeof v === 'string')`. An empty sunset array satisfies that test. The renderer unconditionally calls `d.daily.sunset[0].slice(11, 16)` at `app.js:172`. Validated responses replace `state` at `app.js:110–118`; `draw()` is called in `finally` at `app.js:123–125`, outside the request's catch handling.

**Impact:** For an otherwise valid response with `sunset: []`, the source path accepts the data, overwrites the previous forecast, then attempts a method on `undefined`. This is a **source-proven unhandled-input path**, not a claim that Open-Meteo returned it or that an observed window crashed.

**Fix:** Before committing state, require a sunset array aligned with the seven dates and validate every used timestamp. Alternatively treat missing sunset explicitly as unavailable and omit that fact without fabricating a value. Keep previous good data if required forecast validation fails. Add focused future tests for empty, short and malformed sunset arrays and the last-good-data path; do not merely swallow render exceptions.

**Standard:** Input validation and last-good-data integrity, not a WCAG ruling. **Suggested command:** `/impeccable harden`.

### B-03 · P2 · Pair's “Best round” and recent history are computed from an undisclosed first page

**Category:** Implementation integrity / bounded-history correctness.

**Evidence:** `runtime/kit/showcase/pair-play/rounds.js:7–9` requests `limit: 500` with neither ordering nor pagination. `living_spaces_core/records.py:114–135` sorts default queries by `updated_at` ascending, then slices the page. Pair computes best from the returned subset (`app.js:51–54`) and sorts only that subset for the latest eight rounds (`app.js:58–65`). The labels promise “Best round” and “Past rounds” without a cap (`index.html:33,36–38`). A new in-session save is prepended at `app.js:82`, but reopening reloads the limited page.

**Impact:** Once history exceeds the limit, newer rounds can be absent after reopening; the displayed best can differ from the true best. No large store was inspected or generated here. This is the deterministic consequence of the query/aggregation scope, conditional on crossing the bound.

**Fix:** Query recent rounds in descending `finished_at` order for the history view and obtain the actual best separately, or paginate validated rounds with `offset` before aggregating. If a deliberate retention/view cap is chosen, label its scope and keep the recent view newest-first. Exercise the boundary with an isolated fixture only when authorized; retain the existing exact-record save readback (`rounds.js:11–17`).

**Standard:** Honest data scope; not a live persistence-failure claim. **Suggested command:** `/impeccable harden`.

### B-04 · P2 · Sky precipitation uses an indefinitely animated paint property

**Category:** Performance — **source risk, not measured slowdown**.

**Evidence:** Sky `styles.css:88–94` runs rain/storm at `.6s` and snow at `6s`, infinitely. `styles.css:213` advances `background-position`, rather than a transform. Clouds also combine blur and motion (`styles.css:76–85`), but no measured cost is attributed to them. The explicit pause handler exists at `app.js:236`; reduced-motion/paused rules exist at `styles.css:215–217,241`.

**Impact:** Continuous background-position animation creates a paint-cost risk for a full-pane effect even when data is idle. There is no frame-drop or battery measurement in this assessment, so it is not a reproduced performance defect.

**Fix:** Move precipitation to a clipped, bounded pseudo-element/layer translated with `transform`; retain condition-dependent visibility, the pause button and static reduced-motion state. Do not add broad permanent `will-change`. Profile the normal and reduced-motion paths before asserting an improvement.

**Standard:** Compositor-friendly motion practice, not a claimed WCAG failure. **Suggested command:** `/impeccable optimize`.

## Technical review coverage and positives

### Accessibility

- Host statuses have text plus icon and border-style state (`desktop/plugin.js:26–42,191–199`); cards are anchors with assembled names (`:324–340`). The Internet control is a native button with `role="switch"`, checked/busy/disabled states, labelled-by and described-by references (`:518–539`). This supports intent, not a screen-reader result.
- Drawers use SDK Dialog and explicitly move focus to Close/return it (`:238–254`); confirmation dialogs choose the cancel target first (`:270–315`). Actual trapping, Escape and nested menu return depend on the host SDK and remain unverified.
- Empty-mounted host save live region and failure banners exist (`:228–235,1443–1451`). The revised Off/WebRTC disclosure and immediate reversible Internet toggle are intentional (`:504–506,529–531,636–641`), consistent with the later host spec (`HOST-CHROME-SPEC.md:99–119`). Do not flag missing old revoke confirmation or always-on disclosure as regressions.
- Research wraps inputs in labels (`views/library.js:38–42`, `views/editor.js:77–85`, `views/queue.js:16–19`); it marks selected records and supplies status/error text. Its saving fieldset and buttons use native `disabled`, unlike the host's focus-preserving switch. **Targeted live question, not an observed defect:** does keyboard focus remain recoverable after add/save failure or success? Test this before claiming parity.
- Sky offers a separately labelled data table, focusable horizontal scroll regions and text weather descriptions (`index.html:29–35`, `app.js:155–172,204–206`). Pair uses native card buttons with dynamic accessible names, matched state and a live instruction string (`app.js:24–48,57,94`). Neither proves VoiceOver behavior.

### Responsive layout

- Host grid shrinks via `min(300px,100%)`; frame metadata clamps, identity can shrink, drawer is bounded by `min(460px,100vw)` (`desktop/plugin.js:1752,1755–1756`). At 899/599px History/Upkeep move into overflow while Permissions/Refresh remain (`:1647–1658,1757`), matching `HOST-CHROME-SPEC.md:39` rather than the superseded older bar arrangement.
- The host's 32px action minimum (`:1754`) is intentional desktop direction (`DIRECTION.md:8,67`; later spec `:39`). It is **not automatically a WCAG AA failure because it is below the audit's generic 44px preference**. Rendered target size and spacing are untested.
- Research split/editor columns collapse at 680px; kit controls grow to 44px (`styles.css:28–32`; `spaces-kit.css:241–248`). Sky stacks city panes and keeps a scrollable minimum-width plot/table (`styles.css:193–208,230–242`). Pair changes its board to three columns and then two at very narrow widths (`styles.css:123–132,153–160`). These are source provisions, not proof against clipping or zoom loss.

### Theming

- Host derives its surfaces and semantic states from `--ui-*`; its fixed eight-color tile palette is sanctioned identity, not status (`desktop/plugin.js:23–24,1746,1753–1757`; `DIRECTION.md:9–10`). The white switch-thumb fallback is not evidence of broken light mode.
- Kit contains light/dark token definitions and editorial `light-dark()` choices (`spaces-kit.css:5–87,260–268`). Research selects editorial at `index.html:2,10`. Sky's night room and Pair's felt/card stock intentionally fix their material palettes (`Sky styles.css:1–19`; `Pair styles.css:1–21`); they should not be forced into host chrome merely to eliminate hard-coded illustration colors.
- Host/kit reduced-motion and forced-color provisions exist (`desktop/plugin.js:1757`; `spaces-kit.css:474–493`); the showcases disable motion without hiding card faces or weather text. No computed contrast, forced-color screenshot or theme-switch result is claimed.

### Performance and implementation

- Upkeep explicitly pauses polling when hidden, uses a slower idle cadence, and clears timers/listeners (`desktop/plugin.js:728–767`). Other query polling relies on SDK defaults; background behavior is not assumed. Sky resize work is debounced (`app.js:238–239`); Pair's forced layout at `app.js:31` is once per deal, not a read/write loop or demonstrated thrashing.
- Research collection requests reject stale responses and unsubscribe (`spaces-kit.mjs:98–121`); drafts survive view changes in a per-Space weak-map scope with explicit unsaved messaging (`views/editor.js:9–35,87–94`). These are useful source safeguards, not exercised persistence claims.
- Pair verifies exact stored round data before “saved” (`rounds.js:11–17`). Sky labels its opt-in synthetic sample and retains explicit stale/error language (`app.js:75–91,120–122,226–231`); it does not silently present demo weather as live. Host permission/upkeep changes refetch and compare server state (`desktop/plugin.js:650–662,780–789`).
- Cross-cutting issue: canvas recovery copy and data-boundary assumptions lag behind the stronger host state model. Fix those specific seams; do not replace the authored canvas identities based on generic detector warnings.

## Live tests withheld — no substitute evidence

Owner withheld runtime custody while chat completes. The following were **not attempted**, and old captures cannot stand in for them:

1. Attach to the exact Desktop build, prove its integration identity and renderer/store mapping, then capture host and each actual canvas revision with matching terminal-turn evidence. New store revisions remain unqualified.
2. Host at 1690, 900, 600 and 360px; full/missing/no-success freshness, loading/failure states, Upkeep states, overflow/menu focus, Internet on/off/requested/busy/failed and readback. Add zoom/large text and long-name coverage. No viewport was synthesized here.
3. Keyboard-only traversal, real focus ring visibility, sheet trap/Escape/return, Research add/save/conflict focus, Pair completion/retry focus, Sky focus across redraw and scrollable chart operation; VoiceOver announcements and names.
4. Pixel/computed contrast in host light/dark and every relevant canvas state; forced colors, reduced motion and user pause behavior. No screen-reader, contrast ratio or interaction pass is inferred from source.
5. Performance traces for precipitation, resize and large libraries; hidden-document polling behavior; memory/CPU and paint costs. No timing result was invented.
6. Authorized isolated functional fixtures for malformed Sky data/last-good recovery, Pair history beyond one page/reopen, Research permissions/recovery/save-conflict, and actual terminal native bot outcomes. No store was read, seeded, mutated or replayed.

**Next action order, if separately authorized:** `/impeccable clarify` for B-01; `/impeccable harden` for B-02/B-03; `/impeccable optimize` for B-04; re-run the scoped detector and authorized live audit; `/impeccable polish` only after correctness and verification. No fixes were executed.

Assessment-B-only handoff: the parent owns synthesis and any user questions. This report does not claim completion of Assessment A or the combined critique's live-evidence requirements.
