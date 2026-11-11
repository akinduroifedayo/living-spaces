# Living Spaces premium pass — review and polish request

Method: dual isolated assessments (A: deleg_e97b721a/task-0, captured-host design review; B: deleg_db597ba6/task-0, live Desktop/CDP detector and technical audit), synthesized by Miro with direct before/after image and full-resolution crop inspection. **This is the pre-iteration receipt, not final design acceptance.**

## Identity and authority

Review date: 2026-11-11. Original target: 10 AM CT. Task t_e020f8d4; engineering integration and rerun owner t_d40eb81d. Mode: Operate for all three working canvases, with Read emphasis for Research. Refinement preserves quiet observatory / warm editorial / orchard; no replacement design or new assets commissioned.

Real regenerated Space revisions: Sky Window 11 (baseline 4), Research Desk 18 (baseline 8), Pair Play 10 (baseline 5). Real ordinary-chat provenance and functional captures are at `../regeneration/astra-run/`, evidence commit b5bcfdabdf35df9781686e52282abf2ca2b93f3c; source is unchanged from 72b626aba71067166e737feb95e9585df5262816. Assessment B independently read current revisions and matched loaded renderer code to installed bundle after host import rewriting. See `audit/b-runtime-normalized.json` and identity receipt. This is not the newer cut-integration candidate's qualification.

The task's package-level impeccable context ran successfully in Miro's private worktree. PRODUCT.md/DESIGN.md are absent; incumbent source and named accepted directions govern this narrow refinement. No root context files were invented or written. Direct source edits are restricted to the build-space design section and runtime/kit; all host/generated-Space changes and docs integration go through Forge.

Route transparency: A unexpectedly resolved through the tool default to gpt-6.1-terra/openai-codex/high/normal. B was explicitly gpt-6-astra/openai-codex/high/normal. The parent remains gpt-6-astra. These are tool-reported routes, not provider backend claims. The mismatch with the requested Astra/priority policy was disclosed to Forge; A is not relabelled Astra and neither child is called priority. No Sol or Claude seat was used.

## Verdict

**Distinctive and materially better than the baseline, but not yet fully polished or qualified.** The concepts are good enough to preserve. The important improvements are task visibility on narrow screens, Research's search flow and truthful Pair duration—not more decoration.

### Sky Window

- Before: dark, similar-sized city cards, prominent numerical weather, a conventional line/rain chart. After: compact city selectors, an ink-and-ivory selected-city scene and a seven-day interval ribbon with numeric ranges, conditions and precipitation. The weather is real public Open-Meteo data through the bridge; this is not the separate reference showcase.
- Strength: directly labelled seven-day values reduce reliance on hovering a chart. City confirmation/favourite states are represented in the real captures.
- Trade-off: the selected scene and stacked headings push useful detail down the narrow viewport. The mobile manage action becomes only a plus. The large sun/cloud artwork is decorative; it should not be mistaken for an observed camera view or precise weather depiction. No claim is made that overcast data itself is wrong.
- Proposed iteration P2: compress narrow masthead/intro; put selected city temperature and condition before atmospheric art, retain all city summaries and units, show `Manage cities` visibly rather than plus-only. No data schema or behaviour removal.

### Research Desk

- Before: dense dark overview with count cards, status bars and review CTA. After: cream paper, serif titles, rust accents, source-led reading list and a forest shortlist. It feels like reading material rather than a generic admin dashboard. The source record count grew from 27 to47 through actual public refresh, not a layout effect.
- Strength: source/demo provenance and visible unsaved/saved feedback at the editor. Reported notes/status/priority saves were read back by Forge.
- Defect P2: at the captured phone Library state, the add-paper form sits between search and results. This is an ordering/discoverability defect, not evidence that search is broken.
- Proposed iteration: search → result count → result list remain adjacent. Secondary `Add a paper` disclosure keeps creation accessible, preserves draft and focus. Verify matches, no matches, long titles and creation/editor regression. Retain the warm editorial direction and all records.

### Pair Play

- Before: narrow blue-backed utility board. After: broad cream-and-forest orchard deck with patterned backs, numbered cards and a round rail. The actual fruit faces remain platform emoji; they are not newly generated illustrations. That is an intentional voice to preserve in this bounded pass, not a new asset request.
- Strength: explicit mismatch text and Continue avoid a time-limited memory reveal; completed pairs and history have clear feedback. A six-pair round was independently exercised by Forge.
- Defect P2: four-line headline consumes too much phone space before the board. History shows `643m 59s` from original start to finish: valid elapsed time, but potentially misleading if read as active play.
- Proposed iteration: compact headline to at most two lines at narrow width, board/status first. Format `Elapsed 10h 43m · includes time away` for that long duration; derive from existing timestamps, never rewrite historical records or pretend to track active play. Keep deliberate Continue and persistence.

## Heuristic critique and cognitive load

The complete ten-heuristic table is in `assessment-a.md`. It is provisional, not a runtime pass. Visibility, real-world match, consistency, recognition and aesthetics are generally strong (mostly 3/4); recovery and full keyboard/control coverage remain unverified. A scored uncertain recovery as a midpoint rather than proof of failure. Consequently **no aggregate design-health number or ship rating is asserted**. Incomplete coverage must not become a falsely precise acceptance score.

Sky's seven days and Pair's twelve cards are meaningful domain structures, not an automatic violation of a four-option guideline. The avoidable load is repeated introductory hierarchy before the work. Research's mobile query/add/results split adds an unnecessary context switch. Relevant persona risks: first-time city management discoverability; interrupted phone use with a tall introduction; low-vision users reading secondary small metadata. Measurement found no opaque-background text contrast candidates below4.5 in sampled Sky/Research views; that is not an exhaustive pixel-composited WCAG pass.

## Host header, Upkeep and Internet row

The exact original spec is included as `HOST-CHROME-SPEC.md`. The full requirement-by-requirement status is in `assessment-b.md`.

- **P1 observed:** at a900px app width, the sidebar leaves640px of panel; title and freshness have0px width and Ready overlaps actions. Screenshot and DOM geometry agree. Base breakpoints on available panel width, reserve useful identity width, and move secondary actions before collapse.
- **P1 spec gap:** Internet is granted but there is no `Internet on` affordance in the header; source and loaded renderer agree. Spec section1 calls the chip optional, but section2 identifies it as the persistent changing-risk signal. This review requests implementing that agreed signal, not inventing a new permission or claiming this omission alone is a security vulnerability. It must open Permissions and must not reintroduce title collapse.
- Missing freshness placeholders and persistent sandbox caption are removed in sampled views. Idle `No unsaved changes` is gone. Upkeep none/paused labels work. Sky/Pair `Not refreshed yet` is accurate for host upkeep metadata even when Sky performs an in-canvas fetch; do not stamp a host success from that guest fetch.
- Upkeep absent and paused feed states were inspected. The paused description adds truthful already-running-work context; retain that clarification rather than revert it merely for verbatim conformity. Raw cadence fallback is allowed when friendly schedule_display is unavailable.
- Permissions On switch is visually real and semantically labelled. Native Tab reaches it; Escape restores opener focus. Hit target measured44×40: this meets the pinned host spec's44×40 but is **not** a44×44 general mobile-floor pass. A later44px height improvement is reasonable, not a claimed shipped change.
- Not verified: full freshness branches, first-open optional notice decision, active/running/failed/missing/archived/loading/refetch/cron-unavailable Upkeep, prompt expansion, run/pause/resume/remove feedback, Internet Off/requested/busy/failure, actual toggle focus retention, forced colors and motion rendering. No cron/grant actions were taken in this review.
- Permissions source uses `This Space` instead of its name; busy wording placement differs from spec. These are minor discrepancies, not a substitute for testing the failure path. Overflow40×32 vs pinned32×32 is harmless extra width unless it contributes to collapse.

## Technical audit receipt

Bundled impeccable detector ran against the actual Electron CDP target, exit2: two contrast warnings and a stripe advisory. Their selectors are outside the Space root; they are outer application chrome findings, not proven canvas defects. No overlay/server or install occurred. Sandbox traversal is not established; the detector is not exhaustive.

Audit: accessibility3/4 provisional; performance unscored; theming3/4 provisional; responsiveness2/4 due host collapse; implementation integrity2/4 due host gaps. **No /20 aggregate** because performance was not tested. Generated CSS includes reduced-motion rules; this is source evidence only. B's corrected mobile receipts show390px app →275px canvas viewport (260px client area); no horizontal document overflow. Initial incorrectly emulated `*-390` captures and misnamed `permissions-off` files are excluded from the delivery packet.

## State and verification coverage

| Surface | Evidence obtained | Still unverified |
|---|---|---|
| Real Sky11 | Live3/4-city states, Week, favourite/add/remove confirmation, selected city, refresh; Forge9 checks | Independent empty/partial/offline/error retry, full keyboard, reduced motion,320/zoom |
| Real Research18 | Overview/library/search/editor unsaved+saved/queue/review/refresh; Forge10 checks | Empty search/queue, failed save/refresh, incoming-data draft protection, native select UI, screen reader |
| Real Pair10 | Resume/mismatch/Continue/5of6/complete/history/progress; Forge8 checks | Settings editor, failure recovery/empty history, motion, touch,320/zoom |
| Host | Header desktop/900/600/360, Upkeep none+paused, Permissions On, limited focus | Remaining exact host-state matrix above |
| Reference showcases | Separate live public forecast and complete persisted local game;29 prior executed assertions,22 captures | Desktop/chat/production acceptance, native zoom, physical touch, speech, exhaustive condition contrast |

Forge's functional checks are attributed upstream receipts, not re-executed by Miro. Pair mismatch/mismatch-continue images share a hash; two filenames are not two independent state transitions. Baseline and regenerated captures have matching desktop crop geometry but different content/time/scroll positions; weather differences are not regression measurements.

## Two live showcases — reviewed separately

`../showcases/VERIFICATION.md`, `verification.json`, `INTEGRATION-RECEIPT.json` and image hashes bind source e26f9553d2f6ba88e90c3e15f39c6eb10677f43b. Sky uses public Open-Meteo responses and a labelled low-to-high °C plot with rain %. Pair uses a real input-driven game loop and an isolated file-backed demo store; failures are deliberately injected by its verifier. Both have visible live-state evidence and prior passing checks. Miro reinspected the live dashboard, dense plot/provenance, and game completion during this review. Generated skyline/card-back art is inherited and decorative; original provider/prompt metadata remain missing and disclosed. No new imagery calls occurred.

## Polish performed versus proposed

**Performed:** scoped build-space design-guidance improvement at6e0f7b78158fb1a45fb83242b88b1e18f05791a7 on miro/premium-pass, pushed and exact origin-readback verified. Only three design hunks: query/results adjacency, elapsed-vs-active semantics, actual canvas dimensions/task-first narrow layouts. Outside design section byte-identical; four design links resolve; git diff --check passed. No shared-kit abstraction added for local app defects. No UI build or detector rerun is claimed for a markdown-only change.

**Requested, not yet verified:** one polish iteration per actual regenerated Space plus the host fixes above. Exact deltas delivered on t_d40eb81d comment2262, priority clarification2263, guidance handoff2265. Proposed changes are not completed work. The final addendum must bind each new revision and verify it visually and functionally before acceptance.

## Reproduction and next capture

1. Coordinate exclusive ownership of isolated Desktop CDP9341; never attach to the user's normal app. Bind app/backend/home, loaded renderer identity and Space revisions first. Do not change credentials/provider or restart.
2. Reopen each actual Space through Spaces. Capture the same1430×784 crop from1690×858 for desktop comparisons; use the real app widths390 and320 and record the nested canvas dimensions. Persist emulation in the same live CDP session as measurement/capture; reconnecting can reset it.
3. Sky: Today→Week→Cities; confirm labelled management and current temp/condition above art; preserve city records. Research: Library search attention and a zero-match query; disclosure open/close with draft and keyboard; editor save; preserve records. Pair: existing round→mismatch→Continue→completion→History; verify elapsed qualification and compact board, preserve/restore public demo test mutations under Forge's lane.
4. Host:900px especially, then600/360 and desktop; title/freshness remain nonzero and readable; granted Internet indicator opens Permissions. Test absence when off only in an authorized reversible test window.
5. Exercise empty/loading/error/recovery/reduced-motion/keyboard on isolated copies where practical; label injected faults as injected and all unexecuted states as unverified. Capture final state, exact identity, raw check receipts and cleanup.
6. Forge copies this immutable packet under `docs/design/premium-pass/final-review/`, commits it, and provides commit/hash readback. Miro inspects returned iteration captures and records pass/remaining issues in a separate addendum. No direct docs writes by Miro.

Questions skipped: assigned headless refinement with explicit scope and deadline, overriding the playbook's interactive prioritization step. Missing product context is disclosed, not filled with invented strategy. Current gaps remain open; this receipt does not authorize release.
