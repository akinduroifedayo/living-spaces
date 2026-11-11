# Premium pass — final polish review

Method: synthesis of the two isolated, sequential live assessments delivered by t_b3b306df/run1066 (`a-live.md`, design; `b-live.md`, detector/technical), plus Miro's offline direct image and full-resolution detail reinspection in t_e020f8d4/run1067. This resumes the immutable v1 review; it is not a new host inspection or a release certificate.

## Verdict

**Accept the demonstrated visual iteration in all three real chat-built Spaces. Preserve their distinct directions. Do not grant full responsive, functional or release acceptance.** Sky12 brings real weather before scenery; Research19 restores an uninterrupted query/results flow; Pair11 makes the board the first task. Remaining host identity and embedded-width failures are significant enough to fix before claiming the whole product is polished.

“Shipped” below means present in the isolated ordinary-chat-built revision and independently captured, not deployed to production. The final reports and screenshots are staged for Forge to commit under `docs/design/premium-pass/final-review/polish-addendum/`. Repository delivery requires a separate committed-byte readback. Original deadline: **November 11, 2026, 10 AM CT**; an on-time review handoff does not mean all remaining risks were resolved by that deadline.

## Immutable evidence and identity

- Baseline → regenerated review remains `../REVIEW-BEFORE-ITERATION.md`, with `../before/`, `../regenerated/`, `../assessment-a.md`, `../assessment-b.md`, and the exact `../HOST-CHROME-SPEC.md`. Integrated v1 commit: `2b93cf8dd12b177ba73e0150afac252afaf25d5c`; its 83-file manifest and 47 PNGs are not replaced by this addendum.
- Actual baseline → regeneration → one polish iteration: **Sky4→11→12; Research8→18→19; Pair5→10→11**. Do not substitute the two reference showcases for these real Spaces.
- Frozen provenance independently checked in the previous run and retained here as `polish-provenance-readback.json`: exactly one polish prompt per existing session; terminal finish `stop`; model `gpt-6-astra`, provider `openai-codex`, picker `GPT-6-astra · Fast`; no skill_manage call in the polish turns. Provider-applied service tier is not observed.
- Changed generated files: Sky `styles.css`; Research `views/library.js`; Pair `fit.css` and `views/history.js`. Original saved records (3 / 47 / 2 respectively), manifests and grants matched the frozen snapshots. This preservation receipt is not a new functional regression run.
- Current-revision UI proof is **only** `a-live-{sky-window,research-desk,pair-play}-revision-proof.png` for12/19/11. Earlier `*-revisions.png` accidentally remained on Run history and are not revision proof.
- Loaded old host renderer is bound independently by B: installed SHA-256 `9b703959096f80de81ac28245bdd0bb3303f51f87bf340b6434dce1605e6c536`; import-normalized loaded/installed equality, SHA-256 `d6a1b3cde7a6258b3ab94c9573898ce6aebea217e47cb4c8c5594372d352945d`. Candidate `2b93cf8` was **not loaded**. Do not assign live acceptance to candidate-only or later host fixes.
- A/B restored the original Research route/search, viewport, panels and recorded scroll, with final readback. Exclusive CDP9341 custody was released at09:31. This retry did not reacquire it or touch host/store/source.
- App390 yielded guest275px; app320 yielded guest221px; desktop1690 yielded guest1404px. These are real composed-host widths, not standalone390/320 canvas tests. Crops remove external personal chrome. Drawer-title clipping at the very top is a capture limitation, not an application defect.

## Critique: before / regenerated / polished

### Sky Window — quiet observatory, Operate

Baseline4's similarly weighted dark city cards became regeneration11's ink-and-ivory observatory: compact city selectors, selected-city scene and directly labelled seven-day intervals. That conceptual improvement is preserved, not redesigned.

**Verified iteration11→12:** compare `../audit/b-sky-window-mobile-verified.png` to `a-live-sky-loaded-390.png`. The tall brand/eyebrow region is reduced, the plus-only action becomes visible **Manage cities**, and current Chicago temperature/condition appear above the decorative scene. The three public cities and units remain. At app390 the title and weather data are substantially closer to the first view; this is the intended practical gain, not merely smaller type.

Desktop Week remains an aligned seven-day range display with explicit °C, endpoints, condition icon plus text, rain chance and millimetres. `a-live-sky-week-desktop.png` supports the composition; source calculations were not independently rerun in this offline reinspection. The image is a weather illustration, not a camera observation. Public forecast values legitimately change with retrieval time; differing temperatures between captures are not treated as regressions.

**Remaining:** app320 clips Cities navigation and weather content; Chicago breaks into `Chicag`/`o`. Host `Not refreshed yet` beside guest `3 of 3 live · retrieved…` is technically about different refresh mechanisms but reads ambiguously. Coordinate-based city entry is honest but burdensome; city search is a future product improvement, not a secretly added requirement or shipped feature.

### Research Desk — warm editorial, Operate / Read

Baseline8's dense dark overview became regeneration18's cream paper, serif reading hierarchy, rust accents and forest shortlist. Real public refresh increased the collection from27 to47; that is data provenance, not a design effect. The selected reading room retains demo-paper labelling.

**Verified iteration18→19:** compare `../regenerated/research-phone-390.png` (the open creation form interrupted query/results) to `a-live-research-detail-390.png` and `a-live-research-detail-desktop.png`. **Add a paper** is now a secondary disclosure above the search flow; the query `attention`, **2 of47** result count and matching list remain contiguous. The desktop reading-room split is intact. The earlier phone image uses different capture geometry; this is an ordering comparison, not a pixel-position or performance benchmark.

**Remaining:** app320 cuts off the guest Refresh button. Narrow Overview still devotes most of its first view to branding, headline and shortlist; narrow Library places the selected reading room below the list. These are density/wayfinding opportunities, not evidence of lost notes or failed selection. New-paper draft retention, disclosure keyboard behavior through save/error, zero-match search, and post-polish editor save regression were not exercised in the read-only rerun.

### Pair Play — orchard, Operate

Baseline5's blue utility board became regeneration10's broad cream-and-forest orchard deck, patterned backs and round rail. Fruit faces in the actual generated game remain platform emoji; the reference's authored SVG fruit is a separate implementation.

**Verified iteration10→11:** compare `../audit/b-pair-play-mobile-verified.png` to `a-live-pair-play-390.png`. All twelve cards and turn/pair status now precede the editorial headline. The headline remains as a compact two-line supporting section below the board rather than blocking the game. Desktop composition stays intact in `a-live-pair-play-desktop.png`; the current saved round is visibly loaded.

**Only source/provenance verified, not live outcome:** `views/history.js` changed to qualify elapsed time and format long durations. `a-live-pair-history-390.png` shows **No finished rounds yet**, honestly explaining when an entry is created. There was no completed round in the read-only window, so no rendered long-duration result exists. Do not claim “Elapsed10h43m · includes time away” passed in the real game. The prior completed-game screenshot is revision10, not11. No game flips, Continue, completion, new round or persistence mutations occurred in this rerun.

**Remaining:** a thin horizontal scrollbar is visible at app320. B measured document207px within innerWidth221px, so a broad content-overflow failure is not established for Pair; subpixel/container overflow still needs diagnosis. Do not overstate this as the same measured defect as Sky/Research.

## Audit and host-spec disposition

The exact host handoff remains `../HOST-CHROME-SPEC.md`; later explicit disclosure direction takes precedence over older warning ordering. No new security or consent wording is authorized by this review.

| Requirement / state | Observed result | Still open |
|---|---|---|
| Header truthful metadata, owner, no missing-value placeholders | Sampled owner/freshness visible at desktop; `Not reported`, idle `No unsaved changes`, persistent sandbox caption absent | Full timestamp/build/failed/archive branches; do not infer host success from guest fetch |
| Header responsive identity/action layout | **P1 FAIL:** title0px at app900 and320; only51.14px at390. Ready overlaps actions at900 | Reserve readable identity and collapse secondary actions based on panel/container width, not app viewport alone |
| Granted Internet header signal | Absent in loaded runtime | Prior exact request to Forge remains unimplemented in this runtime. Spec §1 calls it optional; §2 requires it as persistent changing-risk signal. Candidate-only work is not live completion |
| Upkeep none / paused feed | None inspected in v1; paused feed inspected again: status, No model calls, last success, timezone, wake policy, Resume/Run now/Remove and executions | No action executed; friendly cadence absent (`0 7 * * *`). Raw fallback is permitted by spec, so readability P2, not strict failure |
| Upkeep active/running/failed/missing/archived/loading/refetch/cron unavailable; prompt expansion | Not exercised in rerun | Exact action feedback, server-state recovery, focus retention through busy and destructive confirmation unverified |
| Permissions Internet On | Real switch, On text, labelled accessible control; row and explanation visible | Uses `This Space` rather than actual name. Off/requested/revoked/busy/failure branches and announcements unverified |
| Switch geometry / consent | B measures44×40 target; meets pinned44×40 spec, not general44×44 mobile floor | No actual toggle; focus retention through request/result not proven. Preserve existing WebRTC disclosure and consent meaning |
| Sampled modal keyboard | Permissions, History, Upkeep: Close receives focus;14 forward Tabs and Shift+Tab stay inside; Escape closes and returns exact opener with2px outline | Not an all-dialog or all-route keyboard pass; no VoiceOver speech |
| Generated semantics/focus | Named links/searchbox/disclosure/card buttons; sampled first link has3px accent outline | Not a complete task journey or contrast certificate |
| Reduced motion | Live CSSOM contains overrides; Sky entrances positively gated | No media-emulated transition/gameplay behavior run, no forced-colors/light-theme/native200%zoom/physical touch qualification |
| First-open notice | Optional/cuttable by original spec | No new decision or first-open test claimed |

### Prioritized unresolved issues

1. **P1 — host identity collapses.** At app900, available panel640/guest614; `.ls-identity` and title0px. At app320 title0px again. `b-live-research-900.png` and JSON geometry agree. Fix the host container allocation first, retaining readable name/status and accessible secondary-action disclosure. `/impeccable adapt` then polish.
2. **P1 — actual narrow guest content overflows.** At app320/guest221, Research scrollWidth254 (33px excess), Sky246 (25px excess). Visible Refresh/nav/weather clipping confirms meaningful loss, not just a scrollbar. Fix intrinsic minimums, wrapping and city comparisons against the delivered width; retest together with the host fix. Do not claim standalone320 failure. `/impeccable adapt`.
3. **P2 — refresh semantics require translation.** Keep guest retrieval truth and host-run truth distinct. Clarify or suppress irrelevant host freshness without fabricating a host success. This follows the specified `Not refreshed yet` branch but reveals a usability trade-off. `/impeccable clarify`.
4. **P2 — narrow Research hides reading work beneath preamble/list.** Compact repeated branding/prose and offer an explicit selected-paper reading path while preserving query context. Scope this after the P1s. `/impeccable distill`.
5. **P2 — raw Upkeep cadence is harder to read.** Prefer a trustworthy friendly schedule with exact timezone; raw cron remains a valid fallback. `/impeccable clarify`.

The outstanding Internet indicator request and Pair elapsed verification are tracked above rather than hidden by a score. City-search redesign is a separate future product choice, not part of this completed iteration.

### Detector and scoring discipline

B actually ran bundled `impeccable detect --cdp 9341 --target 'dist/index.html#/spaces' --json`, exit2. The receipt records **two contrast findings and one stripe advisory**, all outside `.ls-root`. Zero attributable panel findings is **not** a clean accessibility result; nested generated-frame contrast is not exhaustively covered. No overlay/server was created.

A's provisional heuristic values (0–4): status2, real-world match3, control3, consistency3, prevention2, recognition3, efficiency2, aesthetics3, recovery2, help3; computed total26/40 in the assessment. This is an incomplete read-only sample, **not a release rating or a comparable before/after quality score**. B's partial scores: accessibility3, responsiveness1, integrity3; performance/theming unscored, no aggregate. Sampled focus behavior is stronger evidence than a flattering total.

Persona risks remain concrete: Casey cannot see full identity/navigation at the narrowest composed width; Jordan must interpret two freshness mechanisms and cron syntax; Sam has promising focus/labels but no completed screen-reader/zoom journey. Preserve the coherent visual worlds rather than spending the next pass on more decoration.

## State coverage and truthful limits

| Evidence layer | Actually exercised / observed | Not proven by it |
|---|---|---|
| Pre-polish generated11/18/10 | Forge's27 functional checks and28 real-host captures; original baseline comparisons | Post-polish functional recertification |
| Post-polish12/19/11 | Actual loaded views/navigation, current revisions, Sky steady live loading, Research query/results + selected detail, Pair saved-round display and empty History; desktop/app390/app320; B app900 measurements | Mutations, save/refresh error recovery, game completion/duration/persistence, newly created record, city add/remove regression |
| Host rerun | Paused/On visual states, sampled modal keyboard, loaded identity and restoration | Candidate2b93 or later host changes; complete Upkeep/permission state matrix |
| Empty/loading/error | Pair empty History observed; initial Sky shell superseded by populated data | Permanent blank Sky defect; complete loading/partial/empty/offline/error recovery; any fabricated fault test |
| Motion/accessibility | CSSOM, named AX controls, focus samples | Full motion behavior, contrast sweep, speech, native zoom, real touch |

## Two live showcase references — separate acceptance layer

The prior reference source `e26f9553d2f6ba88e90c3e15f39c6eb10677f43b` and `../../showcases/` verification remain the live-reference deliverable:29 executed assertions and22 final captures. V1's integration receipt matched47 file hashes; these are inherited verified receipts, not29 checks rerun here.

Miro reinspected `../showcases/sky-live-1440.png` (public Open-Meteo, city skyline illustration, daily low/high°C plot and rain%, exact-value disclosure and provenance) and `../showcases/pair-win.png` (6of6,7turns, saved result and scorecard) plus dense original-image crops. Both prove distinct live-state references. The reference game uses an isolated file-backed verifier store; injected failures are labelled in its verification. They do not qualify actual Pair11's persistence or Sky12's failure paths.

Inherited generated skyline/card-back art has byte provenance but missing original provider/prompt metadata; no new generation call or paid fallback occurred. New captures contain public generic demo content only. Public weather is real data, not synthetic fixture response; decorative imagery is not an observation. No prototype screenshot is passed off as interaction evidence.

## Reproduction / next authorized verification

This is a recipe for Forge's next authorized window, not permission to reacquire a running host:

1. Freeze candidate, renderer hash and revisions; obtain exclusive isolated host/store custody. Bind loaded script after import normalization. Do not equate repository HEAD with the running renderer.
2. Open each real Space in native Spaces. Measure app/panel/guest through the same CDP connection that captures. Use1690×858,900-wide,390×844 and320×844; keep user-side chrome outside the public crop. Wait for nested frame mount and steady data before judging blank/loading output.
3. Sky Today→Week→Cities: verify management label, current condition before art, full navigation/units and chart ranges at actual guest width. Retest public fetch success and authorized isolated empty/partial/error recovery.
4. Research Library: query `attention`, then zero-match; open/close Add a paper with keyboard and draft preservation, select detail, exercise a reversible public demo editor/save/error path. Preserve original records.
5. Pair: resume→mismatch→Continue→completion→History under explicitly authorized reversible fixture use. Capture a genuine long-duration record with **Elapsed** and **includes time away**, and verify timestamps remain untouched. Do not change historical records just to get a flattering screenshot. Test reload/persistence and restore isolated fixture state.
6. Host: require nonzero readable title at app900/390/320 and preserved focus after action disclosure. Verify Internet-on signal and all approved Upkeep/Internet branches, including busy/error and cancellation, under appropriate mutation authority. Verify reduced-motion transitions and keyboard path, not merely CSS presence.
7. Return exact captures/checks and cleanup; retain unresolved risks. No additional rerun was commissioned or executed by this offline close.

## Delivery and polish receipt

Performed previously: prevention guidance `6e0f7b78158fb1a45fb83242b88b1e18f05791a7` pushed, exact three design hunks integrated in2b93cf8; all outside-design skill bytes preserved. Guidance addresses query/results adjacency, elapsed-vs-active semantics and actual-canvas/task-first narrow design. It was source-only during the polish turns and is not credited as loaded by those sessions. No new kit abstraction is warranted for these local fixes.

Performed now: independent direct reinspection of final captures; revision proof; before/after linkage; consolidated critique/audit/polish disposition; explicit host matrix and functional limits; immutable docs-only handoff to Forge with a SHA-256 file manifest. No host, generated-Space, repository or credential edits in this retry. No new routine, server or publication.

**Completion boundary:** the commissioned review and one captured visual iteration per Space are complete. The full product is **not** accepted as universally polished; P1s and named behavioral gaps remain with engineering/product acceptance. Repository delivery is complete only after Forge's committed bytes are independently matched to `MANIFEST.json`.

Questions skipped: this assigned headless refinement has explicit scope and an offline-only owner direction; no live interactive prioritization or expanded implementation is authorized. Recommendation is to fix composed-width P1s first and verify the remaining behavior, preserving all three art directions.
