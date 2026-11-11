# Assessment A — independent LIVE delta

Method: isolated Assessment A; actual Desktop CDP9341, parent t_b3b306df/run1073. No detector or Assessment B read. This is A's design judgment, not combined critique or release acceptance. Impeccable context was already run by parent; critique playbook loaded. Source design direction, HOST-CHROME-SPEC and kit README read with git show at d7f20699fe441b606a0e0684cfde34a37dada1d9.

## Outcome

**Accept the dedicated narrow identity row as a bounded design improvement for these three observed Ready states. Do not accept the composed app320 experience: Research and Sky still have P1 guest-width failures.** The extra row is not the same defect as the overflow and should not be reverted to recover height.

The installed plugin file hash was independently read as `3a5ef2d4f276e26075cc3f194929392286bbc3f3b0d4b193b1d5ef915560c01f`. Runtime source byte equality was not independently established by Debugger in this review. Actual History → Revisions panels confirm **Research19 / Sky12 / Pair11** as Current; see `*-revisions-native.png` and the geometry JSON. Earlier files ending `-revisions.png` and `-revision-proof.png` show Run history, not revision proof: DOM click did not activate the Radix tab. Native pointer events produced the authoritative proof.

## Header judgment: the 42px is worth spending

The former invisible/near-invisible name problem is materially repaired. At app390 Research Desk is readable in full; at app320 it is recognizable as “Research …”, with Ready preserved. Sky Window and Pair Play remain named at app320. Permissions, Refresh now and overflow remain visibly separate targets. Back gets its own line; this is less efficient than ideal, but losing which Space an action targets is worse.

Research's measured header is now **207.5px at app320**, with a **60.5px identity**; the supplied earlier A baseline was 165.5px. The narrow rule's projected 42px cost is therefore realized for this observed state. Sky and Pair have 189.5px headers and 42.5px identity blocks. At app900 all three remain compact with 109.5px headers and 614px guest viewport width: the narrow repair does not bloat that compact state.

**Scope of acceptance:** these actual names, Ready, observed freshness, idle save state, and existing bot-error banner. Long names, longer non-Ready labels, busy saves and banner-free composition were not fabricated or exercised. This is not all-state header qualification.

## Design specificity and strengths

The authored worlds are genuinely distinct: Research is an editorial reading room; Sky is a night-weather instrument with place and atmospheric depth; Pair is a tactile tabletop. Preserve them. The native index correctly acts as a conventional neutral directory rather than trying to preview three competing visual worlds.

- **Pair is the best narrow task-first example.** Its board is immediately visible at guest221, with readable Play/Progress/History and current-round status. No game flips were made; the existing one-turn round was left intact.
- **Host identity and permissions remain clearly outside the guest.** The new identity line improves recognition without changing the authored canvas. Correctly cropped Permissions panels show a real switch, explicit On text, scoped grants and a visible Close focus ring.
- **Progressive disclosure is useful.** Research Library keeps Add a paper closed; Progress and Week are understandable safe navigation surfaces. Upkeep clearly distinguishes Paused, public-source refresh and no model calls.

## Priority issues

### P1 — Research and Sky still break at the actual 221px guest width

App320 does not mean guest320. Measured guest widths: app1690 → 1404, app900 → 614, app390 → 275, app320 → **221**.

Research's document scroll width is **254px**, and its Refresh button reaches x=254.203125: the screenshot visibly cuts the control on the right. Sky's document scroll width is **246px**; Cities is clipped beyond the tab capsule, and the Chicago temperature/city-card contents collide with the very narrow card allocation. A horizontal scrollbar is visibly present. Research and Sky app390 are substantially more legible; standalone320 is not a sufficient test.

**Fix:** use the nested content width as the breakpoint. At <=260px, put Research Refresh on its own line or compress the masthead into a title/action stack; let Sky navigation wrap or use a deliberate accessible scrolling rail, and replace the forced three-up city cards with a one-column list or properly sized horizontal rail. Keep temperatures intact. Do not hide overflow to make the metric pass. Re-test at 221px, including scrollbar space. `/impeccable adapt`.

Pair's document scroll width is 207px against innerWidth221; its board and navigation visually fit. Do not generalize the other guests' defect to Pair.

### P2 — Bot failure copy adds a competing task and exposes transport internals

All three show Ready, Internet on and “Bot request: offline”, followed by `404: {"detail":"Not Found"}. No automatic resend.` These can be compatible facts, but the UI makes the user reconcile them. This is a pre-existing backend/host condition, **not caused by the identity-row repair**. No Check bot status request was made.

**Fix:** retain a visible, accurately scoped failure. Explain what request failed, which content remains usable, and what the check action does. Put the 404 payload behind details; do not label the whole Space offline or silently dismiss the warning to reclaim space. `/impeccable clarify`.

### P2 — Research spends its narrow first view introducing itself rather than exposing papers

At app390 the Overview's masthead, four navigation labels and large slogan consume the remaining viewport. In Library the search label only reaches the bottom of the initial capture; results require further scrolling. The repaired host identity and error banner make the cost more obvious, but the guest's redundant introduction predates them.

**Fix:** keep the paper/ink language and useful section hierarchy, but reduce the narrow masthead and omit or greatly reduce the introductory slogan on returning/task views. Let search and the first result appear sooner. Use Pair's board-first ordering as the structural example, not its visual skin. `/impeccable distill`.

### P2 — Upkeep exposes cron syntax and an undifferentiated execution wall

The live panel presents `0 7 * * *` with America/Chicago, followed by a long list of completed executions. It is technically informative but not task language. The same issue persists in the correctly cropped app320 panel; action controls themselves fit.

**Fix:** show a derived human-readable schedule with timezone, keep the raw expression secondary, and show the latest few executions with an explicit “View all” disclosure. Preserve all historical data. `/impeccable clarify`.

## Bounded heuristic update

These are visible-design scores, not functional certification; no aggregate is appropriate for unexercised safeguards and recovery.

| Heuristic | Assessment | Basis |
|---|---|---|
| Status visibility | 2/4 | Freshness and explicit states; conflicting apparent scopes remain. |
| Real-world language | 3/4 | Clear task names; raw 404 and cron expressions intrude. |
| Control/freedom | 3/4, inspected paths only | Safe routes and Escape close worked; destructive/undo paths untested. |
| Consistency | 3/4 | Stable host grammar with intentionally distinct guests. |
| Error prevention | Unscored | No saves, grants, refreshes, flips or destructive operations tested. |
| Recognition | 3/4 | Narrow host name repaired; remaining guest clipping hurts affordances. |
| Efficiency | Unscored | No timed task or accelerator qualification. |
| Aesthetic/minimalism | 2/4 across sizes | Strong native composition; narrow Research overhead and Sky clipping. |
| Recovery | 1/4 for copy only | Transport error exposed; actual recovery deliberately not attempted. |
| Help/documentation | Unscored | Contextual permissions/upkeep explanations seen; full discoverability not tested. |

Cognitive load: grouping and <=4 guest navigation choices work. Single focus and hierarchy fail in narrow Research; the app900 host still presents five action choices plus Back, with Refresh clearly primary. Internet on and Permissions duplicate a destination. This is a density concern, not an automatic rule that five options are unusable. The game grid is the task, not twelve unrelated menu choices.

Persona flags: Jordan must interpret Ready versus bot offline; Alex must scroll past Research's introduction before working; Sam benefits from restored host identification but still faces clipped guest controls at narrow widths. No contrast, screen-reader, zoom or full keyboard certification is claimed. Emotional high point is entering an authored guest world; the technical failure banner and narrow clipping interrupt confidence before the task. No completed save/refresh/win was exercised, so end-state quality is unscored.

Questions for parent synthesis: prioritize **guest221 containment / Research first-task visibility / recovery copy**? For narrow host density, **keep the accepted row / later shorten Back while preserving identity**? These are recommendations for synthesis, not permission to modify this read-only target.

## Evidence, execution notes and release

Artifacts are all under `/Volumes/Expansion/Development/Build/r1-qualification-t_b3b306df/qualification-repair-addendum-20261111/`:

- Drivers: `a-live-delta.py`, `a-live-delta-followup.py`, `a-live-delta-panels.py`; contact-sheet helper `a-live-delta-sheets.py`.
- Structured evidence: `a-live-delta-original.json`, `a-live-delta-geometry.json`, `a-live-delta-restoration.json`.
- Main panel images: `a-live-delta-{research-desk,sky-window,pair-play}-{1690,900,390,320}.png`; index at all four widths.
- Correct full portalled-panel crops: `a-live-delta-dialog-{permissions,upkeep}-{1690,390,320}.png`.
- Revision identity: `a-live-delta-{research-desk,sky-window,pair-play}-revisions-native.png`.
- Safe guest routes: `a-live-delta-research-desk-library-390.png`, `a-live-delta-sky-window-week-390.png`, `a-live-delta-pair-play-progress-390.png`.

Actually viewed all three app320 PNGs, all three app900/390/native compositions via contact sheets (Research900 also full-size), index contact sheet, corrected Permissions native/320 and Upkeep320 full-size crops, and all three safe guest-route PNGs. Contact sheets are derived inspection aids; original PNGs and geometry remain authoritative. Early root-cropped drawer images cut the portal at the root boundary; use the later `dialog-` crops for panel judgment.

The first driver raised KeyError on the index's absent header after saving its capture; finally restored successfully. The optional-key error was repaired and remaining index widths completed. DOM click did not select Radix Revisions; native pointer events fixed the evidence collection, not application code. Metrics connection stayed open through capture; nested guests settled before each capture. No waiting loops, detector, installs, source/backend/store writes, board actions or model requests were performed. Navigating Sky allows its normal existing data loading; no Refresh action was invoked.

**CDP9341 custody RELEASED at 2026-11-11 10:50:01 CST.** Final readback verifies `#/spaces?space=research-desk`, 1690×858, html class dark / color-scheme dark, host scroll [0,0], zero dialogs, guest hash empty and guest scroll [0,0]. `a-live-delta-restoration.json` records `verified: true`. No further CDP use after this release.
