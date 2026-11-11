# Living Spaces R1-12 — qualification addendum

Method: dual isolated live assessments (A: `deleg_8b0b398e/task-0`; B: `deleg_413bb31b/task-0`), sequential custody of the same Desktop, then Miro's direct image inspection and source comparison. Both tools reported gpt-6-astra / openai-codex / high / normal; neither is labelled priority. Supporting offline source scan: `deleg_75df3d88/task-1`.

## Verdict for Bjorn

**FAIL for the inspected configuration. Final submission-candidate qualification is pending.** Do not submit on the strength of this report. Preserve the three visual directions; correct the composed host/Space width failures and missing persistent Internet signal, then verify the exact final candidate. The three polish revisions exist and their principal visual changes are observable, but read-only inspection cannot establish their complete functional regression or final-package behavior.

This is an additive interim receipt, not an edit to `final-review/` v1 and not an early invocation of the task's 11:00 CT fallback. Forge explicitly identified the current head as **not the final submission pin**. The final verdict must be rebound when that pin arrives, or under the stated 11:00 fallback.

### Exactly what was judged

- **Source audited:** `2b93cf8dd12b177ba73e0150afac252afaf25d5c`, frozen by `git archive` from `forge/r1-cut-integration`. Forge reports a fresh exact-archive 16/16 validator pass; Miro did not rerun that validator. This source was **not installed for this inspection**.
- **Actual running host:** canonical checkout `b5bcfdabdf35df9781686e52282abf2ca2b93f3c` (parent independently read HEAD); source lineage `72b626aba71067166e737feb95e9585df5262816`. Installed renderer SHA-256 `9b703959096f80de81ac28245bdd0bb3303f51f87bf340b6434dce1605e6c536`.
- **In-memory binding:** Debugger script 348 raw SHA-256 `bbc79222e10e20c8ebe01fd16c133fa62f5a9f2fe69cfe30949d1dd4948f28f0`. After normalizing only static import specifiers, loaded and installed source are exactly equal, hash `d6a1b3cde7a6258b3ab94c9573898ce6aebea217e47cb4c8c5594372d352945d`. Raw hashes differ because the host rewrites imports; the normalized match is not a claim that raw bytes match.
- **Actual generated Spaces:** Sky Window **12**, Research Desk **19**, Pair Play **11**, independently read and photographed through Current-revision UI. Prior ordinary-chat revisions 11/18/10 remain historical comparison evidence at `b5bcfda`; they are not silently relabelled.
- **Chat provenance:** Forge's explicit handoff reports all three polish turns terminal `finish=stop`, original record counts 3/47/2 and all grants unchanged. This is attributed upstream evidence, not Miro's independent native-persistence test.
- **Safety:** CDP9341 only, granted to this card/run1066 from09:10–09:40 CT. A and B ran sequentially. Custody released early at09:31. No explicit refresh, save, game flip/Continue/new round, permission change, model turn, source/symlink edit, install or reload. Opening Sky initiated its normal public forecast fetch. Sampled route/search/viewport/scroll/panels restored exactly; complete backend record hashes were not independently taken.

## Design specificity and observed improvements

The quiet observatory, cream editorial reading desk, and orchard-green game are meaningfully different compositions. No new aesthetic direction is needed.

| Space | Observed in new revision | Qualification limits |
|---|---|---|
| Sky12 | Visible Manage cities; current temperature/condition and city summaries precede decorative scene at app390. Today/Week/Cities present, real live/retrieved labels visible. | Add/favourite/remove and failed-fetch recovery not executed; app320 containment fails. |
| Research19 | Add a paper is a secondary disclosure; search → count → results are contiguous. `attention` shows 2 of47; selected paper opens the reading room. | Disclosure draft retention/zero-result/save regressions not executed in this pass; prior worker save check was in-memory, not native persistence. |
| Pair11 | Board and current-round state precede the editorial heading at app390; named twelve-card board, saved-round message, Play/Progress/History. | History was empty; elapsed/includes-time-away formatting therefore unverified. No mismatch/Continue/completion/persistence regression. Reported automatic Continue-focus inconsistency remains an upstream hypothesis requiring reproduction. |

Host index shows distinct identity tiles and text+icon status, search/filter hierarchy and separate freshness facts. Runs disclose trigger, timestamp/timezone, duration and no-change outcomes. Permissions, History and Upkeep passed sampled native-click opening, initial Close focus,14 forward Tabs plus Shift+Tab containment, Escape dismissal and opener-focus return. These checks do not certify every dialog or full accessibility.

## P1 — block submission

### P1-01 · Host title/freshness collapse at ordinary compact desktop width

At **900px app width**, the persistent sidebar leaves **640px panel** and **614px generated viewport**. `.ls-identity` and its title measure **0px**; Ready overlaps the action cluster. At app320 the title is again0px. This is measured and visibly reproduced, not a permissible ellipsis.

**Fix:** base the header on available panel/container width, reserve a useful identity row, and move secondary actions into overflow before they compete with identity. Keep Permissions and Refresh now reachable. Verify900,600,390,320 app widths with sidebar state and actual nested width recorded, plus keyboard focus after overflow movement. `/impeccable adapt`, then `/impeccable polish`.

**Evidence:** `b-live-research-900.png`, `b-live-research-320.png`, `b-live-evidence.json`. The parent compared source72b626a→2b93cf8: `src/desktop/ui/styles.js` has the identical Git blob `f12333702bd9554a1423e71bad5b9d076a7996a2`; the built-renderer diff adds bot actions but no header-layout repair. This supports an unresolved source finding at2b93, not a claim that the entire2b93 app was run.

### P1-02 · Generated content clips in the composed320px app

At app390, the guest receives275px. At app320, it receives **221px**, not320px. Research scrollWidth254 exceeds that by33px; Sky246 exceeds it by25px. Research's Refresh is visibly cut; Sky loses navigation/condition content and breaks Chicago across lines. Pair's coarse document measure does not establish the same broad overflow; a thin scrollbar alone is not scored as a third equivalent failure.

**Fix:** remove intrinsic minimum widths, wrap nav/action rows and adapt city comparisons at the *actual* sandbox width. Alternatively product/engineering must explicitly define and enforce a supported host minimum width; this review cannot silently waive the commissioned320px check. Do not change test labels to pretend a320px guest is a320px app. `/impeccable adapt`.

**Evidence:** `a-live-sky-loaded-320.png`, `b-live-research-desk-ready-320.png`, `b-live-followup.json`, `b-live-detector-receipt.json`.

### P1-03 · Required granted-risk signal remains absent

Research Permissions visibly shows Internet access **On**, while its desktop frame has no `Internet on` affordance. Sky likewise has no such chip in the inspected header. The later HOST-CHROME-SPEC §1 calls it optional, while §2 explicitly requires it as the persistent changing-risk signal after caption removal; the prior accepted review already reconciled this as a requested P1 implementation gap. This is **not** proof of a new security vulnerability.

**Fix:** implement the granted-only, labelled Internet on affordance opening Permissions, without recreating the title collapse. Confirm absence when Off and correct focus/semantics in an authorized reversible permission-test lane. No permission toggle was authorized here.

**Evidence:** `a-live-research-detail-desktop.png`, `b-live-permissions.png`; host spec §2 item4; source/loaded header and source comparison. First-open notice decision remains unqualified, not treated as a separate blocking defect.

## P2 — refinements, not reasons to redesign

1. **Freshness semantics:** Sky host says Not refreshed yet while the guest reports live retrieval. Both can be true. Prefer distinguishing host upkeep history from source retrieval; never fabricate a host success from an in-canvas fetch. This wording currently follows the pinned spec, so changing it needs accepted copy reconciliation, not an unilateral 'fix'.
2. **Narrow Research hierarchy:** introductory overview content and the long Library list delay the reading area. Compact repeat branding and offer a clear selected-paper reading destination while retaining context; do not remove real records or functionality.
3. **Readable cadence:** Upkeep's `0 7 * * *` is a permitted fallback. Provide a truthful human cadence with timezone when available; raw cron is not a P1 contract failure.

City-name lookup would improve Sky's coordinate-based creation flow, but it is a feature/scope suggestion, **not** an R1-12 repair requirement. No new service or provider is commissioned.

## Impeccable critique receipt

| Heuristic | Evidence-limited score /4 | Finding |
|---|---:|---|
| Visibility of system status |2|Good local state; disappearing host identity and differing refresh meanings|
| Match to real world |3|Strong domain language; cron/manual coordinates require interpretation|
| User control and freedom |3|Navigation and sampled modal escape work; mutations/undo untested|
| Consistency and standards |3|Common host controls with distinct authored interiors|
| Error prevention |Unscored|Destructive/save/conflict paths not exercised|
| Recognition rather than recall |3|Named navigation and counts; compact header loses context|
| Flexibility and efficiency |2|Search works in observed state; narrow reading order adds effort|
| Aesthetic and minimalist design |3|Distinctive worlds; some mobile preamble remains excessive|
| Error diagnosis/recovery |Unscored|Historical outcomes inspected, live failures not induced|
| Help and documentation |3|Contextual instructions, record/revision warnings, provenance|

No aggregate health or ship rating: untested error paths are not midpoint passes. Assessment A's own26/40 is retained in its raw report as provisional but is **not adopted as acceptance**. Cognitive load is concentrated in the compressed host and repeated Research introduction, not inherently in seven forecast days or twelve game cards. Relevant risks: Casey cannot read clipped narrow content; Jordan must reconcile refresh meanings; Sam has promising named controls/focus but no complete screen-reader/zoom proof.

## Impeccable audit receipt

- Actual CDP detector ran against `dist/index.html#/spaces`, exit2: two contrast warnings and one stripe advisory. All three exact selectors are outside `.ls-root`; none may be attributed to a generated Space. This is not a detector-clean/WCAG pass, because nested-frame coverage is not established. No overlay/server was used.
- Generated-frame AX reads confirm named navigation, Research search, Sky controls and Pair card names. Safe-link focus styling is visible3px. Live CSSOM contains reduced-motion handling, but motion behavior was not exercised.
- Partial audit scores: accessibility3/4, responsive1/4, integrity3/4; performance and theming unscored. No /20 total.
- Separate source scans ran on2b93 package references/kit. They concern **reference/showcase code**, not the three real generated apps. `assessment-b-offline.md` records nonexistent Approve Refresh guidance, an empty-sunset validation path, bounded history and animation paint-risk findings with exact lines. These need engineering triage and are not relabelled as live Space defects. Raw detector findings include intentional weather art and optional blueprint styling.

## Exact primary evidence

All names are relative to this addendum:

- `a-live.md`, `b-live.md`: isolated assessments and image inventories.
- `a-live-sky-loaded-desktop.png`, `a-live-sky-loaded-390.png`, `a-live-sky-loaded-320.png`.
- `a-live-research-detail-desktop.png`, `a-live-research-desk-390.png`, `b-live-research-desk-ready-320.png`.
- `a-live-pair-play-desktop.png`, `a-live-pair-play-390.png`, `a-live-pair-history-390.png`.
- `a-live-{sky-window,research-desk,pair-play}-revision-proof.png`: exact Current revisions.
- `a-live-index-desktop.png`, `b-live-research-900.png`, `b-live-permissions.png`, `b-live-history.png`, `b-live-upkeep.png`.
- `b-live-evidence.json`: loaded identity, geometry, focus sequences. `b-live-followup.json`: settled nested-frame measurements.
- `b-live-final-receipt.json`: generated AX/CSSOM, revisions, restored state; `restorationEqual=true`, Research permission text unchanged.
- `b-live-detector.json`, `.stderr`, `b-live-detector-receipt.json`: actual scan and scope attribution.
- `a-live-original.json`, `a-live-release.json`: A restoration. Per-capture JSON preserves viewport/crop geometry.
- `SOURCE-BINDING.json`, `MANIFEST.json`: parent frozen-source verification and delivery hashes.

Initial unready Sky/Pair shells and incorrectly named *-revisions captures are retained as raw diagnostics outside the curated delivery, not evidence of defects/revision proof. Permission drawer screenshots intentionally crop the top edge; do not attribute this crop to application layout. Python bytecode in the working directory is excluded from the delivery; its attempted deletion was approval-blocked and was not bypassed.

## Remaining gate and next qualification

Need Forge's exact final submission SHA, installation/loaded-identity receipt and explicit new read-only window after host repairs. Re-check the P1 geometry and risk affordance at that pin. Native save/refresh/error paths, Pair Continue focus/completion/history elapsed copy, new-revision persistence, light theme, forced colors, screen reader,200% text zoom, real touch and reduced-motion behavior remain unqualified. Source-only bot-action repairs are unqualified live. Activation-intent and ambient-header exposure remain independent engineering/owner release gates; this design review does not waive them.

Questions skipped: this headless assigned review has an explicit scope and authority boundary; interactive priority questions are replaced by concrete P1/P2 findings and the exact final-pin dependency. No redesign or implementation was performed.
