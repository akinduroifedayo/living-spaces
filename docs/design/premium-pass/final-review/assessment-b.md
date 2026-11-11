# Assessment B — independent detector and technical evidence

Method: isolated Assessment B, read-only Desktop CDP 9341; Assessment A was not read. Captured 2026-11-11 approximately 08:39–08:47 CT. Context loading was already completed by parent. No implementation, chat, grant toggle, cron action, reload, restart, symlink change, or provider/model change was performed. Route navigation and viewport emulation only; generic Space crops exclude the session sidebar/account footer.

## Outcome

**Generated canvases are coherent and responsive in the sampled states, but host chrome does not fully meet the exact spec.** Most consequential: at a 900px app viewport, the Space name and freshness collapse to **0px width**; Internet access is granted but the required **Internet on** chip is absent. No full accessibility/performance/release pass is claimed.

### Exact identity receipts

- Target: `file:///Applications/Hermes.app/Contents/Resources/app.asar.unpacked/dist/index.html#/spaces?space=pair-play`, target ID `554C65AC7B54612834E5CD860EEBBCA2`; visible, 1690×858, DPR 1 initially and finally.
- Read-only SQLite query of isolated `home/plugin-data/living-spaces/spaces.db` confirms **Sky Window 11 / Research Desk 18 / Pair Play 10**, unchanged on final readback. `b-identity.json` records revision file→SHA maps; `b-readback.json` verifies revisions, grants, route and viewport.
- Current source HEAD is `b5bcfdabdf35df9781686e52282abf2ca2b93f3c`, **not** the earlier evidence HEAD `72b626aba71067166e737feb95e9585df5262816`. `git diff 72b626a HEAD -- src` and `git status --short -- src` returned no changes. Recent commits were evidence documentation.
- Installed desktop plugin and source bundle SHA256 both `9b703959096f80de81ac28245bdd0bb3303f51f87bf340b6434dce1605e6c536`.
- Actual loaded plugin was retrieved with Debugger.getScriptSource: blob script, 107646 bytes, SHA256 `bbc79222e10e20c8ebe01fd16c133fa62f5a9f2fe69cfe30949d1dd4948f28f0`. **Loaded code equals installed disk code after normalizing import specifiers** (host rewrites imports to blob URLs). `b-runtime-normalized.json` records `importsNormalizedEqual: true`; `b-runtime-diff.json` records differences. This is stronger evidence than assuming current checkout equals loaded renderer.
- Source plugin installation is a separate desktop plugin file; backend `home/plugins/living-spaces` resolves to the project’s `src/living-spaces`. Nothing was relinked.

## Bundled detector — actually executed

Command: `/Users/ifedayoakinduro/.hermes/skills/creative/impeccable/scripts/impeccable detect --cdp 9341 --target 'file:///Applications/Hermes.app/Contents/Resources/app.asar.unpacked/dist/index.html#/spaces?space=pair-play' --json`

**Exit 2, three findings:** two `low-contrast` warnings (3.0:1 and 3.8:1, required 4.5:1), one `repeating-stripes-gradient` advisory. Exact JSON and command are in `b-detector-receipt.json`. No installation or overlay server.

Scope verification (`b-detector-scope.json`): both contrast selectors lie **outside `.ls-root`**, in the left/footer app chrome (x18 and x105); stripe selector is the outer `body`. These are **not evidence of contrast or decorative-pattern failures inside the regenerated canvases**. Keep them as outer-host observations, not Space bugs. Detector traversal into sandbox canvases is not established, so three results are not an exhaustive Space scan.

Manual computed-color probe independently sampled visible text within each generated frame: Sky and Research produced no sub-4.5 candidates; Pair produced one decorative star at 2.90:1 (not meaningful text, do not count as a WCAG text failure). This was a limited opaque-background calculation, not pixel-composited or exhaustive contrast certification. Gradient/alpha cases, all interactive states and offscreen text remain unverified. Receipts: `b-*-contrast.json`.

## Five audit dimensions (qualified)

| Dimension | Score | Evidence and qualification |
|---|---:|---|
| Accessibility | 3/4 provisional | Permissions Close→Tab reaches switch; native Escape returns to opener. Switch has role, checked state, labelledby/describedby, 44×40 hit area, visible unclipped 2px ring. No VoiceOver, full keyboard workflow, toggle/busy/error announcements or zoom pass. |
| Performance | Unscored | Three views rendered and navigation worked; no tracing, throttled loading, memory, interaction timing or animation-frame benchmark. Do not convert this to a performance pass. |
| Theming | 3/4 provisional | Host uses UI tokens; all three generated CSS sets use custom properties and include reduced-motion rules. Sky/Research kit CSS includes forced-colors; Pair CSS set has no forced-colors rule. Actual alternate theme/forced-colors behavior not exercised. |
| Responsive design | 2/4 | Canvas layouts fit desktop and 390px app emulation without horizontal document overflow; host header fails at 900px. Native touch/gesture and 200% text zoom not tested. |
| Implementation integrity | 2/4 | Distinct product-specific canvases and truthful revision identities; host’s missing risk signal and collapsed identity are verified failures against exact spec. Detector findings were scoped rather than blindly attributed. |

**No aggregate health score:** performance was not measured; a /20 total would imply coverage not obtained.

## Prioritized verified findings

### [P1] Header loses Space identity at 900px
- Location: host `.ls-framebar` / `.ls-identity`; `src/desktop/ui/styles.js:11–13`.
- A 900×844 app viewport leaves a 640px Space panel because the sidebar remains 260px. The action cluster occupies 492.203px; identity shrinks to 12.422px; **h1 and metadata each measure width 0**. Ready pill intrudes over the Upkeep action. Users cannot identify the Space or read freshness while risk-bearing actions remain available.
- Receipts: `b-header900-geometry.json`, `b-host-900.png`. Spec §1 requires a useful single row at >=900, not invisible identity.
- Recommendation: make responsive decisions from available panel width / reserve identity minimum and move secondary actions before collapse. `/impeccable adapt`.

### [P1] Required Internet-on risk chip missing
- Pair Play Permissions shows On; `aria-checked=true`, database net grant `granted`. All three audited Spaces have net granted. Yet header has no `Internet on` chip in any sampled desktop view.
- The loaded plugin itself contains no `Internet on` text; source action cluster `space.jsx:137–143` has no chip. This is unimplemented, not merely a hidden capture state.
- Impact: exact spec’s sole persistent signal of changed network risk is absent. Permissions remains accessible, but risk is hidden until opened.
- Receipts: `b-permissions-detail.json`, `b-identity.json`, `b-loaded-plugin.json`, desktop captures. Recommendation: implement granted-only chip opening Permissions. `/impeccable harden`.

### [P2] Smaller exact-spec discrepancies in host chrome
- Overflow button is **40×32** at 900/600 and desktop, rather than specified 32×32; at 360 it becomes 32×32. All sampled header buttons meet the host’s 32px height minimum (not a claim of 44px mobile targets).
- Paused Next run says `Paused. Future runs stop until resumed. Already-running work may finish.` instead of pinned `Paused. It won't run until resumed.` This is arguably useful clarification, but not exact implementation.
- Permissions On description says `This Space...` instead of `{Space}...`; busy text is a separate status paragraph in source rather than replacing On/Off beside the switch. Busy behavior was not exercised.
- Recommendation: reconcile copy/geometry with owner; preserve truthful in-flight warning if intentionally approved. `/impeccable clarify`, then `/impeccable polish`.

## Exact host-spec implementation matrix

| Requirement | Status | Observed fact / limit |
|---|---|---|
| Omit missing source/freshness placeholders | Implemented in sampled states | Pair/Sky: `Not refreshed yet`, no invented source date. Research: Updated + Source data from. No `Not reported` in sampled header. |
| Relative freshness with semantic time/title | Partially verified | Relative text visible; full datetime/title and all state branches not checked. |
| Empty idle save live region; no `No unsaved changes` | Implemented sampled | Initially previous `Saved ...` message; after navigation idle text empty. No unsaved placeholder absent. |
| Upkeep labels / action cluster / no standalone Pause | Implemented sampled | none and paused labels; History, Permissions, Refresh now, overflow; no standalone Pause. |
| Internet on chip when granted | **Unimplemented** | Grant true, chip absent; loaded code/source agree. |
| Header responsive behavior | **Partial / failure at 900** | 600 hides History, 360 hides History+Upkeep and retains Permissions/Refresh. 900 identity becomes 0px. |
| Name ellipsis / metadata two-line clamp | Partial | Works visibly on narrow view, but cannot recover zero-width at 900. |
| Remove persistent caption / inset bordered rounded frame | Implemented | Caption absent; source 1px border, 12px radius and content padding; visually present. |
| First-open sandbox banner | Not implemented in read source; decision unresolved | No banner implementation in space.jsx; not observed on previously opened Spaces. Spec permits explicit product removal, but no approval was established here. |
| Upkeep drawer width/title | Implemented | 460px right drawer, `Upkeep · Pair Play` / `Upkeep · Research Desk`. |
| Upkeep absent state | Implemented | Exact No upkeep yet explanation and Copy prompt; no Run/Pause/Remove action row. |
| Upkeep paused feed state | Mostly implemented | Paused pill; no-model-calls copy; Runs `0 7 * * *` and America/Chicago; Next run paused explanation; Succeeded last result; missed-run explanation; Run now, primary Resume, Remove, executions. Raw cadence permitted when display absent; upstream schedule_display not checked. |
| Upkeep feedback / polling / remaining state matrix | Unverified | No active/running/failed/missing/archived/load-error/refetch-error/cron-unavailable states induced; no cron actions. Prompt expansion is not applicable to sampled feed job. |
| Permissions real switch geometry and semantics | Implemented in On state | Native button role switch, visible On, labelledby/describedby; 44×40 hit area; 2px focus ring. |
| Close→switch keyboard / Escape→opener | Verified limited pass | Actual CDP mouse opened panel, Tab focused switch, Escape returned to Permissions. Upkeep Escape returned to Upkeep opener. Synthetic `.click()` preliminary focus behavior was not used as final result. |
| Permissions Off/WebRTC, requested, denied/revoked, busy/failure/success | Unverified runtime | Source branches exist; grants never changed. Files named `b-permissions-off*` were preliminary **misnamed On-state captures**, not evidence of Off. Prefer `b-permissions-detail*`. |
| Reduced motion / forced colors | Source presence only | Host rules exist, including broad animation/transition disabling. Intentional alternatives and real rendering not verified. |

## Responsive / generated-canvas receipts

- Desktop canvas viewport: 1404×711; clientWidth=scrollWidth=1389 (scrollbar accounts for difference).
- At 390×844 emulated app viewport, host rail leaves **275×637 canvas viewport**, clientWidth=scrollWidth=260 for all three. This is app-with-sidebar emulation, **not** standalone 390px canvas or a physical phone.
- All sampled visible-size buttons in Sky/Research meet 44×44 based on DOM control geometry; Pair includes a 20×20 input, but associated-label hit area was not checked, so no target-size violation asserted.
- `b-*-mobile-verified.{json,png}` are the valid narrow receipts. Earlier `b-*-390.*` incorrectly remained desktop-sized because emulation cleared when its CDP connection closed; **discard those as mobile evidence**.
- No gameplay cards, status/priority controls, refresh controls, grant controls or cron actions activated. Sky’s ordinary open performed its existing automatic public-data retrieval; no Refresh was clicked. Navigation naturally opens/closes host sessions and may update last-opened metadata; this is not a byte-for-byte no-side-effects claim.

## Limitations, restoration and artifacts

- Original Pair Play route and 1690×858 DPR1 viewport restored and read back; final net grants equal initial sampled grants, revisions remain 11/18/10. `b-readback.json`.
- Screen reader, actual touch, keyboard-only end-to-end tasks, empty/error/recovery states, offline, zoom, alternate theme and performance were not tested. Prior regeneration functional claims were read as context, not counted as independently repeated passes.
- Initial screenshot helper failed from nested asyncio; fixed only the audit script. One source-diff probe timed out from expensive matching; retry completed and produced normalized runtime identity. No source edits resulted.
- Report and all `b_*.py`, `b-*.json`, `b-*.png`, `b-final-run.log` artifacts are alongside this report on Expansion. No repository sources were modified. No detector overlay/server was started.

This is the delegated Assessment B evidence package, not the parent’s combined design critique; user prioritization questions remain with the parent synthesis.
