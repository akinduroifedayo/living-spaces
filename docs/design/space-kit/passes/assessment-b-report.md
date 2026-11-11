# Space kit critique — Assessment B

Method: isolated Assessment B subagent (detector + browser evidence). Assessment A was not read. This is evidence for parent synthesis, not the combined design critique.

## Execution

- Bundled detector executed **once** from the repository root:
  ```text
  /Users/ifedayoakinduro/.hermes/skills/creative/impeccable/scripts/impeccable detect --json src/living-spaces/skills/build-space/references src/living-spaces/runtime/kit/spaces-kit.css
  ```
- Exit **2**: completed with findings, not an operational crash. Raw stdout is preserved without rewriting in `assessment-b-detector.raw.json`; stderr in `assessment-b-detector.stderr.txt`.
- Configuration and ignores were left unchanged. Context was already loaded by the parent; it was not rerun. No UI, runtime, test, or source changes were made by B.
- Source hashes recorded before scanning match after evidence collection. See `assessment-b-execution.json` and `assessment-b-verification.json`.

## Deterministic findings

Parsed programmatically from raw JSON: **8 findings**, all `cramped-padding`, all severity `warning`, all in `src/living-spaces/skills/build-space/references/kit-gallery.html`. The detector emits `line: 0` for every entry; the source locations below are manual mappings, not invented detector line numbers.

| Raw entries | Detector snippet / mapped location | Browser/source validation |
|---:|---|---|
| 3 | `<div> "space-card": children flush against border+bg on all sides (no inset)` — gallery lines 31–33, metric cards | False positives at sampled default desktop/mobile rendering: computed card padding is **16px**, not zero. CSS line 122 uses `calc(var(--space-4) * var(--space-density))`. |
| 1 | `<section> "space-card": children flush against border+bg on top/right/left (no inset)` — gallery line 38, Reading list | False positive in sampled rendering: computed padding **16px**. The reading-list header and controls are inset. |
| 3 | `<li>: children flush against border-bottom on bottom (no inset)` — gallery line 38, three reading-list items | False positives in sampled rendering: item padding is `0px 0px 12px`, `12px 0px`, `12px 0px 0px`. The last item has no bottom border. CSS lines 169–171 provide the intended inset/separator behavior. |
| 1 | `<div> "space-table-wrap": children flush against border on all sides (no inset)` — gallery line 48 | Structural false positive: the scroll/border wrapper deliberately has zero padding, but the caption has **12px** padding and cells **10px 12px** (CSS lines 174–177). The text is not flush against the external boundary. |

Evidence: `assessment-b-gallery-browser.json`, `assessment-b-gallery-overflow-no-overlay.json`, `assessment-b-gallery-desktop.png`, `assessment-b-gallery-data-mobile.png`, and `assessment-b-gallery-mobile-no-overlay.png`. False-positive disposition applies to these inspected states, not every theme/density combination.

## Scope and coverage limits

The submitted directory includes the gallery, research-desk HTML/CSS, Preact/HTM source (`app.js` and `views/{overview,library,queue,editor}.js`), weather HTML/CSS/JS, and the inline habit-planner markdown. The complete source inventory and hashes are in the execution/verification JSON.

- **Kit CSS:** explicitly passed as requested. The CLI produced no unsupported-target or ignored-CSS error, and no standalone CSS finding. Its help advertises non-HTML regex analysis. A no-finding CSS result does not establish full computed-style coverage.
- **Linked styles:** the detector warned that research-desk's `./kit/spaces-kit.css` could not be read at its authored source-relative path. Its exact warning is preserved in stderr. The preview mounts/inlines the kit, so browser rendering has styles that the source HTML scan could not resolve there. Color/custom-property source coverage for that target is incomplete.
- **Preact/HTM templates:** their JS files were in the submitted tree and read independently, including conditional editor/conflict/empty-state markup. The CLI emits findings only, not a scanned-file manifest. No findings in these files is not proof that template-generated DOM was fully parsed. Browser evidence renders the research overview and the seeded habit planner, but not every research route/conditional state.
- **Habit markdown:** read the inline HTML and JS directly (HTML lines 31–49, JS lines 53–149). The CLI does not establish that markdown fences were scanned; no extracted temporary HTML/JS was submitted and no second detector run was made. Treat static markdown coverage as **unconfirmed**, not clean. Its rendered inline implementation is represented by the habit-planner preview/screenshots, subject to the sandbox overlay restriction below.
- The weather target is the explicitly labelled Internet-Off fixture using actual reference code, not an assertion of production host network behavior. No live public feed or weather network request was required for this evidence.

## Browser evidence

Isolated browser session: `space-critique-b`; fresh tabs, not Assessment A's tabs. Captures at **1280×900** and **390×844** browser viewports. Waited approximately three seconds for preview boot. Used browser/CDP screenshots rather than a separate automation harness. Browser inspection and script instrumentation were ephemeral; no source injection tags were written.

| Target | Preflight | Live detector script / console | Evidence |
|---|---|---|---|
| `/?example=research-desk` | Outer title mutation + appended inline script succeeded. Followed the opaque-origin wrapper to the actual nested application frame; title mutation + appended inline execution also succeeded there. | Outer preview script loaded and logged `[impeccable] No anti-patterns found.` **Not an application verdict.** The actual application's external `detect.js` was blocked by CSP. | `assessment-b-preflight.json`, `assessment-b-research-browser.json`, **`assessment-b-research-application.json`**, research desktop/mobile PNGs. The application JSON is the authoritative inner-app record; the earlier browser JSON also records an intermediate wrapper with an empty text body. |
| `/?example=habit-planner` | Outer and actual nested application title/script preflights succeeded. | Outer preview logged no anti-patterns. Actual application `detect.js` blocked by CSP. **No reliable application overlay.** | `assessment-b-habit-browser.json`, habit desktop/mobile PNGs. |
| `/src/living-spaces/skills/build-space/references/kit-gallery.html` | Mutable title and appended inline script executed. | External script loaded and ran. Captured console: `icon-tile-stack 40x40px icon tile above h3 "Your library is empty"`. Source location: gallery line 40. This is a browser-only structural/advisory signal, not a CLI finding and not automatically a usability defect. It is an empty-state identity tile in a component specimen. | `assessment-b-gallery-browser.json`, gallery desktop/overlay/mobile/data PNGs. |
| `/weather-off.html` | Mutable title and appended inline script executed. | External script loaded and logged `[impeccable] No anti-patterns found.` This applies to the current Internet-Off, no-forecast state only. | `assessment-b-weather-browser.json`, weather desktop/mobile PNGs. |

### Exact sandbox failure

In the actual research and habit application frames, the appended script URL was `http://localhost:8401/detect.js`; its error handler fired. `securitypolicyviolation` records identify:

```text
blockedURI: http://localhost:8401/detect.js
violatedDirective: script-src-elem
originalPolicy: default-src 'none'; script-src 'unsafe-inline' 'unsafe-eval' blob:; style-src 'unsafe-inline' blob:; img-src blob: data:; font-src blob: data:; media-src blob: data:; worker-src blob:; connect-src 'none'; frame-src 'none'; form-action 'none'; base-uri 'none'; object-src 'none'; manifest-src 'none'; webrtc 'block'
```

Two matching violation events can occur for the same appended script because of nested sandbox policies; they are not separate findings. **CSP was not relaxed or bypassed.** Browser visual rendering and computed-style reads remain usable evidence, but there is no application detector-console result for these sandboxed apps. Successful detection on the outer fixture does not cross the opaque-origin boundary. Do not tell the user all app overlays are visible.

### Instrumentation artifact checked

The injected gallery page briefly reported mobile document `scrollWidth: 502` against `clientWidth: 379`. A fresh tab at the same 390×844 size, **without detector injection**, reported `scrollWidth: 379`, `clientWidth: 379`, and no right/left-overflowing elements. See `assessment-b-gallery-overflow-no-overlay.json` and its PNG. Do **not** promote the injected-page width reading into a product overflow bug. The uninjected mobile gallery, habit form, research metrics, and weather offline view rendered without obvious screenshot clipping; this is not an exhaustive responsive/accessibility audit.

## Cleanup and verification

- B's live detector server was started from `docs/design/space-kit/passes/` (PID 22202, port 8401), so server bookkeeping stayed within the permitted output subtree.
- Stopped using **`live-server stop --keep-inject`**, not bare `stop` (which could edit an entry HTML file). Exit **0**, stdout: `Stopped live server on port 8401.`
- Read-back health request to `http://localhost:8401/health` failed with **connection refused**, confirming B's server is stopped. The existing preview server at port 8769 was left alone.
- Source-hash verification returned no changed target sources. Existing parent worktree modifications were present before B and were not reverted.
- An initial `python3 -c` wrapper was refused by the execution approval gate **before it ran**. A saved runner under the permitted passes directory executed the detector successfully once; there was no detector retry.
- No Desktop window, Forge home, runtime test, public-network validation, or production persistence claim was made.

**Execution status:** detector and browser evidence collection completed; sandbox application overlay injection **failed as documented**. No fixes performed.

Questions are deferred to the parent combined critique; B was explicitly limited to evidence output.
