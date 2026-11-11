# Independent live Assessment B — detector and technical audit

Method: isolated Assessment B, sequential live custody after A; A's findings and design judgment were not read. Target: installed Hermes page `554C65AC7B54612834E5CD860EEBBCA2`, CDP **9341 only**, `/spaces`. This is B's evidence for parent synthesis, not a standalone combined A+B critique. Read-only UI lane: route/panel/focus navigation and viewport emulation; no refresh controls, reload, permission toggles, upkeep actions, revision restoration, gameplay, saves, source edits, installs or servers.

**Outcome:** verified host-header collapse at 900px app width and at 320px, plus generated Research/Sky overflow at the actual narrow sandbox width. Permissions, History and Upkeep passed the sampled modal keyboard sequence. Loaded renderer identity is independently bound to installed source. Final original route, viewport, theme, closed panels, window scroll and Research search were restored and read back.

## Runtime provenance

`Debugger.getScriptSource` found the loaded Living Spaces blob script, id `348`:
- Loaded raw: **107646 bytes**, SHA-256 `bbc79222e10e20c8ebe01fd16c133fa62f5a9f2fe69cfe30949d1dd4948f28f0`.
- Installed file: `/Volumes/Expansion/Development/Projects/living-spaces/src/living-spaces/desktop/plugin.js`; SHA-256 **`9b703959096f80de81ac28245bdd0bb3303f51f87bf340b6434dce1605e6c536`**, matching the supplied handoff's 106822-byte installed renderer.
- Normalize only static `from 'specifier'` / `from "specifier"` imports, replacing specifiers with `IMPORT`: loaded and installed strings are **exactly equal**; both normalized hashes `d6a1b3cde7a6258b3ab94c9573898ce6aebea217e47cb4c8c5594372d352945d`.
- Therefore this is evidence about the installed/loaded renderer, **not** qualification of snapshot candidate pin `2b93cf8dd12b177ba73e0150afac252afaf25d5c` or future source changes. Handoff associates installed source with canonical `b5bcfdabdf35df9781686e52282abf2ca2b93f3c`; that Git association was supplied, not independently re-audited here.
- Final UI revisions: Research **19**, Sky **12**, Pair **11**, matching handoff. This compares a supplied baseline to independent final UI readback; not a full before/after backend snapshot.

## Bundled detector receipt and scope

Executed `/Users/ifedayoakinduro/.hermes/skills/creative/impeccable/scripts/impeccable detect --cdp 9341 --target 'dist/index.html#/spaces' --json`. Actual detector exit **2**; output is `b-live-detector.json`, stderr `b-live-detector.stderr`.

Programmatically counted **3 findings**:
1. `low-contrast`: `span.shrink-0.text-\\[0\\.64rem\\]`, reported 3.0:1 vs 4.5:1.
2. `low-contrast`: `span.truncate.text-muted-foreground\\/80`, reported 3.8:1 vs 4.5:1.
3. `repeating-stripes-gradient`: advisory on `body`.

Exact-selector runtime scope checks found one match each and **none inside `.ls-root`**. The body advisory is outer desktop decoration; both contrast findings belong to outer chrome, not generated Space or Living Spaces panel. These are out-of-scope attribution exclusions, not claims that the detector's pixel readings are false. **Zero detector findings attributable to the target panel; not a clean accessibility certificate.** The top-page detector does not establish nested generated-frame coverage. No overlay/server was used. Receipts: `b-live-detector-receipt.json`.

## Measurements and prioritized findings

Widths below are **app viewport / available Living Spaces panel / generated viewport**, not standalone browser-mobile widths. Metrics remained applied on the same open CDP session through captures.

| App width | Panel width | Generated innerWidth | Host document overflow |
|---:|---:|---:|---|
| 900 | 640 | 614 | none (`scrollWidth=900`) |
| 390 | 301.34375 | 275 | none (`scrollWidth=390`) |
| 320 | 247.265625 | 221 | none (`scrollWidth=320`) |

### P1 — host identity is squeezed to zero width

At **900px app width**, `.ls-identity` measured **0px**, and the Research title **0px**, while all actions remain on the same row. The Ready pill visibly floats above/over the action cluster; title and freshness lose their usable space. At 320px, the title is again **0px**; at 390px it is only **51.140625px**. Header heights: 85.5 / 127.5 / 165.5px respectively.

Evidence: `b-live-research-900.png`, `b-live-research-320.png`, corresponding geometry in `b-live-evidence.json`; directly inspected through vision. This is not just a permissible ellipsis: identity has no allocated width. Persistent desktop chrome reduces the content width before viewport media breakpoints respond. Fix layout based on available container width, reserve identity width, and collapse secondary actions before identity reaches zero. `/impeccable adapt` then `/impeccable polish`. Later HOST-CHROME-SPEC.md governs header/caption expectations; old warning ordering and caption requirements were not used to manufacture failures.

### P1 — Research and Sky overflow their actual 320px-app sandbox

At app width 320, generated `innerWidth=221`:
- Research: document/body scroll width **254**, exceeding innerWidth by **33px**. The right-side Refresh control is visibly clipped and a horizontal scrollbar appears.
- Sky: document/body scroll width **246**, exceeding innerWidth by **25px**.
- Pair: document width **207**, below innerWidth; no comparable broad content overflow established. Its screenshot has a thin horizontal scrollbar, so do not infer zero subpixel/client-width overflow from this coarse measure.

At app widths 900 and 390, all sampled generated documents had scroll widths below innerWidth (vertical scrollbar accounts for the difference). This is a composed-host failure at the actual delivered width, **not** a claim that the Spaces fail at standalone 320px content width. Fix intrinsic minimums, header/action wrapping and card widths against the actual embedded width, or define/enforce a host minimum width. `/impeccable adapt`. Evidence: `b-live-followup.json`, `b-live-detector-receipt.json`, `b-live-*-ready-320.png`; Research 320 and Sky 390 inspected visually.

### P2 — Upkeep's schedule remains technical rather than readable

Research Upkeep shows `Runs 0 7 * * *` followed by `America/Chicago`. The timezone is clear, but the cadence requires cron knowledge. The later spec permits raw cadence as a fallback when schedule_display is missing, so this is **a minor usability gap, not a contract failure**. Prefer a trustworthy human-readable schedule while preserving timezone. `/impeccable clarify`.

Scope counts for these consolidated findings: **P0 0 / P1 2 / P2 1 / P3 0**. Research and Sky overflow are grouped as one shared narrow-layout issue.

## Modal keyboard and visual checks

Native CDP mouse presses opened each Research panel (not DOM `.click()`, so opener-focus return was meaningfully exercised). For **Permissions, History and Upkeep**, independently:
- Initial focus: **Close** inside the dialog.
- **14 forward Tabs**, then Shift+Tab: every sampled focus remained inside the dialog.
- Escape: dialog count became **0**, focus returned to the exact opener (`Permissions`, `History`, `Upkeep: paused`). Returned opener computed outline: **2px solid accent**.
- Dialog labels/modal attributes and focus samples preserved in `b-live-evidence.json`.

Permissions visually presents Internet access **On**, with a real switch; Own data and Diagnostics **Allowed**. Sampled 390px dialog fills **390×844**, and its content wraps rather than clipping. Research Permissions text is **exactly unchanged** between first and final readings (`researchGrantsTextUnchanged=true`). No switch was activated. Internet-off/requested/busy/error states were not manufactured.

History clearly distinguishes outcome, manual trigger, timestamp/timezone, duration and “no change · 20 unchanged.” Revisions tab displays “Restoring code does not rewind records” and Research revision 19 Current. No restore action was touched.

Upkeep shows **Paused**, public-source feed/**No model calls**, paused-next-run explanation, previous success, wake/missed-run policy, execution history, and distinct Run now / Resume / Remove actions. Nothing was executed. These are credible state explanations, not tested action success paths.

Drawer screenshots crop away external personal chrome and intentionally remove the top 34px/footer strip; consequently their title is partially cropped in the artifact. **Do not report that screenshot crop as an app title-clipping bug.**

## Generated semantics, focus and motion

Nested-frame AX trees were queried with the generated **frameId**, not only the outer sandbox target:
- Research: named navigation links; named `Search papers (title, summary, authors, notes)` searchbox; `Add a paper` disclosure; meaningful paper-result button names. A raw DOM pass initially showed unnamed hidden controls, but AX/visible-control verification does **not** support an unlabeled-control finding.
- Sky: Today/Week/Cities and Manage cities links; named Refresh; city buttons include city, condition and temperature.
- Pair: `Pair Play home`; Play/Progress/History links; twelve buttons named **Card 1…12, face down**; New round and Make it yours disclosure. Existing saved-round UI was inspected, never played or reset.
- A safe first link in each generated Space accepted focus and computed a **3px solid** visible outline in its own accent. This is a focus-style spot-check, not a complete keyboard journey.

Read **live CSSOM rules**: all three include reduced-motion overrides disabling animation/transition and smooth scrolling; Pair also neutralizes hover transform. Sky entrance animations are positively gated on `prefers-reduced-motion: no-preference`. No 0.01ms workaround found in these returned rules. Motion media emulation/state transitions were **not exercised**, so source/CSSOM support is not claimed as full reduced-motion behavior validation. Receipts: `b-live-final-receipt.json`.

## Partial audit scores — no aggregate

| Dimension | Partial score /4 | Scope/limit |
|---|---:|---|
| Accessibility | 3 | Sampled dialog focus/trap/Escape and generated names/focus are good; full contrast, VoiceOver, all paths and zoom not qualified. |
| Responsive design | 1 | Verified zero-width host identity and two generated narrow-overflow failures. |
| Implementation integrity | 3 | Coherent host control pattern; independent loaded identity; detector warnings correctly excluded by scope. |
| Performance | Unscored | No profiling or load benchmark. |
| Theming | Unscored | Existing dark host only; no theme switch/forced-colors validation. |

**No total, normalized percentage, full health rating or release acceptance is asserted.** Operate-mode strengths: clear distinction between host controls and authored Spaces, truthful run outcomes, named generated controls, and dependable sampled modal escape behavior. The index adapted to narrower columns without outer document overflow; card widths were 576 / 261.34375 / 207.265625px at the three app widths.

## Restoration, evidence quality and gaps

Final readback (`b-live-final-receipt.json`, repeated in `b-live-detector-receipt.json`):
- Host `#/spaces?space=research-desk`, **1690×858**, dark, window scroll `[0,0]`, **0 dialogs**.
- Guest `#/library`, scroll `[0,0]`, search **`attention`**.
- Exact comparison with initial recorded state: **true**. Device metrics cleared, theme never changed. Final probe timestamp **2026-11-11T09:27:14.937053-06:00**; subsequent read-only detector scope receipt confirms the same state.

Initial route captures waited too briefly for nested frame mount: `b-live-sky-window-native.png` and `b-live-pair-play-native.png` show unready shells, and first restoration logged guest=null. These are **superseded**, not product-failure evidence. Follow-up explicitly waited for the guest, re-captured all three widths, restored the original search, and verified equality. A follow-up script initially failed before any browser action due to a missing import; it was corrected and executed successfully. Initial outer-target AX reads were empty; proper generated-frameId reads produced the actual semantic evidence.

**23 panel-only screenshots** saved under `b-live*.png`; manifest in `b-live-detector-receipt.json`. Key images were loaded and visually inspected (900/320 Research, 390 index, Permissions native/390, History, Upkeep, Pair 320, Sky 390). All intentionally written artifacts are `addendum/b-live*`; no A judgment or assessments consumed. **Artifact-hygiene exception:** Python's import loader automatically created `addendum/__pycache__/b-live-audit.cpython-313.pyc`. An exact-file cleanup command was blocked by the tool's deletion approval guard, so that bytecode remains for parent cleanup; no bypass was attempted.

Remaining gaps: no complete backend grants/record checksum snapshot; only Research grant text before/after plus supplied-baseline/current revision comparison for all three. No model/permission/gameplay/save mutations used to test busy/error/success paths. Internal arbitrary scroll containers were not exhaustively inventoried; recorded window scroll, guest route/search and panels are restored. No physical touch, 200% text zoom, screen-reader session, light theme, forced colors or reduced-motion behavioral run. Do not extrapolate sampled modal passes to every dialog or generated route.

Reusable audit lesson for parent: wait for nested guest mount and request AX with the generated frameId; early empty trees/shell screenshots are insufficient evidence. No skill file was written because this custody lane allowed writes only to `b-live*`.

Questions deferred to parent synthesis; B does not ask a second independent direction question.
