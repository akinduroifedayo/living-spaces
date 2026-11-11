# Assessment A — LIVE follow-up

Method: isolated design review (Assessment A only). No detector output or prior A/B findings consumed. Live CDP 9341; actual installed Hermes window; normal astra-high routing, not priority. Context was already run by parent. Read frozen DIRECTION.md and final-review/HOST-CHROME-SPEC.md; applied the later disclosure/header direction rather than treating the original notice ordering as binding.

## Outcome / custody

**Control released at 09:19:15 CT, November 11, 2026.** Final route, viewport, panels and original Research search state restored in `finally`, then read back. `a-live-verify.py` independently compared original and release receipts: exact equality. Original/restored: `#/spaces?space=research-desk`, app 1690×858, main scroll 0,0, no dialogs; guest `#/library`, search `attention`, guest scroll 0,0. No further CDP interaction after release.

No refresh/run, game flip, Continue, new round, save, restore, permission toggle, source/store mutation, install, server, reload or model turn was invoked. Only navigation, paper selection, history/disclosures and transient viewport changes. Sky's own normal on-open public weather loading occurred; the Refresh controls were not used. Writes confined to `addendum/a-live*` on Expansion.

**Current revisions independently verified through native-click Revisions tabs and visually inspected:** Sky Window **12**, Research Desk **19**, Pair Play **11**. Native input was required for the host tab: DOM `.click()` left Run history selected, so those first attempts are not revision proof. The final `*-revision-proof.png` images are genuine Current-revision evidence.

Host provenance is inherited from the authorized handoff: canonical b5bcfda, source72b626a, installed renderer SHA-256 `9b703959096f80de81ac28245bdd0bb3303f51f87bf340b6434dce1605e6c536`; candidate2b93cf8 not loaded. This follow-up did not independently hash the in-memory renderer, and does not imply candidate-host qualification.

## Viewports and evidence interpretation

| Actual app viewport | Nested public demo viewport width | Meaning |
|---|---:|---|
| 1690×858, DPR1 | 1404 CSS px | Desktop app with its existing sidebar |
| 390×844, DPR1 | 275 CSS px | Real app narrow emulation, not an iframe artificially set to 390 |
| 320×844, DPR1 | 221 CSS px | Real app narrow emulation, not an iframe artificially set to 320 |

The reduced guest space is an integration fact, not a reason to relabel the captures. Public-pane crops exclude personal sidebar/account/footer content; image width is consequently smaller than app width. Dialog-only revision proof is cropped to the dialog. The broader Permissions/Upkeep crops start at the public-pane top and cut the very top of the drawer title: **capture limitation, not an app clipping finding**.

The initial `a-live-sky-window-desktop.png` and `a-live-sky-window-390.png` caught startup before the guest was ready. They are not evidence of a permanent blank state. Superseding `a-live-sky-loaded-*` show fully populated weather after waiting. Do not use initial loading captures to score steady-state Sky.

## Design-specificity verdict

These are three authored product worlds, not one generic dashboard skin. Sky's dark observatory, amber weather symbols and shared-scale week forecast fit its subject; Research's cream paper, editorial serif and rust accents fit reading; Pair's orchard-green patterned cards and restrained score rail feel coherent and calm. The stronger desktop composition survives at app390, but **app320 exposes a real host/guest contract failure**. Do not redesign these worlds; fix their available-width behavior.

### Strengths visible in the revised flows

- **Pair11:** at app390 the board comes before the editorial headline; turn/pair count stays immediately above the cards. The current saved round is visibly loaded. History honestly says no finished rounds and explains that unfinished/new rounds do not create an entry. No persisted gameplay was exercised.
- **Research19:** Add a paper is a secondary disclosure; search, result count and results form one contiguous Library flow. Desktop paper selection creates a readable two-column reading room with demo provenance. Search state could be restored exactly.
- **Sky12:** app390 displays current city, temperature and weather metrics before decorative scenery. Today/Week/Cities and Manage cities are visible. The desktop week uses aligned temperature ranges and text/icon weather labels, with an explicit shared-scale explanation.

## Observed priority issues

### P1 — app320 breaks host identity and Sky/Research content containment

At app320, the host Space name disappears rather than remaining identifiable; metadata is heavily clipped. The persistent chrome leaves only **221px** for the guest. Loaded Sky then clips the Cities navigation, truncates weather labels/temperatures and splits Chicago into `Chicag` / `o`; a horizontal scrollbar appears. Research's internal Refresh button is cut at the right edge and its guest horizontally scrolls. Pair keeps a usable four-column board, but also shows a horizontal scrollbar. At app390 the names are already severely abbreviated (`Sky …`, `Rese…`, `Pair …`), although the guest content is substantially healthier.

Impact: users cannot reliably identify the current Space or read/operate all content without horizontal panning. Fix the **host** allocation/identity row and the guest minimum-width assumptions together; test actual app widths, not isolated guest390. Preserve a readable name and stack essential host controls; let Sky's city comparisons/nav and Research's brand/Refresh wrap or compact at the actual available width. Evidence: `a-live-sky-loaded-320.png`, `a-live-research-desk-320.png`, `a-live-pair-play-320.png`. Suggested command: `/impeccable adapt`.

### P2 — host freshness language conflicts with live Sky content

The header says `Not refreshed yet` while the guest says `3 of 3 live · retrieved 09:16 AM` (later 09:19 AM) and displays live weather. The facts may represent different refresh mechanisms, but the visible copy does not explain the distinction. A first-time reader can reasonably believe the weather is stale or uninitialized. Distinguish host-run history from guest-source retrieval, or suppress host-run freshness where it is not the relevant freshness signal. Do not falsely infer a source timestamp. Evidence: `a-live-sky-loaded-desktop.png`, `a-live-sky-loaded-390.png`, `a-live-sky-week-390.png`. Suggested command: `/impeccable clarify`.

### P2 — Research's narrow reading work starts too far below its introduction

At app390, overview branding/navigation plus the editorial headline and shortlist consume essentially the entire first guest viewport; frontier papers are below. In Library with a paper selected, the first viewport still ends inside the result list, before the selected reading room. The revised search/results adjacency is good, but desktop-style preamble remains expensive in an Operate/Read surface. Compact repeat branding and overview prose on narrow containers; provide an explicit selected-paper reading path or contextual jump without removing the search context. This is a visibility/efficiency observation, **not** a claim that paper selection fails or loses notes. Evidence: `a-live-research-desk-390.png`, `a-live-research-detail-390.png`. Suggested command: `/impeccable distill`.

### P2 — Sky city entry asks users to supply geographic coordinates

Cities exposes City name, Latitude and Longitude directly, with decimal-degree and signed-coordinate guidance. The copy is honest and the grouped form is legible at app390, but ordinary weather users must look up coordinates outside the task. Offer a city search with disambiguated places as the main route; retain coordinates as an advanced/manual option. No city was entered or saved, so validation and persistence remain untested. Evidence: `a-live-sky-cities-390.png`. Suggested command: `/impeccable shape`.

### P2 — paused Upkeep exposes cron syntax instead of a natural schedule

The Runs value is `0 7 * * *`, followed by America/Chicago. Pause status and Resume action are clear, but users must decode the schedule to know what resuming means. Render a human cadence alongside the exact timezone, retaining raw cron in details. This is a usability issue, not a strict violation of the later spec's permitted raw-cadence fallback when schedule_display is absent. Evidence: `a-live-upkeep-desktop.png`. Suggested command: `/impeccable clarify`.

## Ten provisional heuristic scores

Scale 0–4. Combined host + three demo surfaces, **not** separate product grades. Limited read-only sample: unexercised saving/error recovery/accessibility must not be mistaken for proven quality or proven defects.

| # | Heuristic | Score | Basis / qualification |
|---|---|---:|---|
| 1 | Visibility of system status | 2 | Clear saved-round/count and research freshness; contradictory Sky host/guest freshness and missing narrow identity |
| 2 | Match with real world | 3 | Strong domain language; raw cron and coordinates remain technical burdens |
| 3 | User control and freedom | 3 | Back navigation, local views and Escape dismissal worked; destructive undo/restore not tested |
| 4 | Consistency and standards | 3 | Coherent guest worlds and common host controls; separate refresh meanings need clarification |
| 5 | Error prevention | 2 | Explicit current-revision/records warning and demo provenance; mutation guardrails not exercised |
| 6 | Recognition rather than recall | 3 | Named navigation, visible counts and history; app320 hides identity/navigation content |
| 7 | Flexibility and efficiency | 2 | Useful search and multiple views; narrow reading preamble and manual coordinates add effort; shortcuts not qualified |
| 8 | Aesthetic and minimalist design | 3 | Distinct, controlled visual systems; research mobile hierarchy remains over-introductory |
| 9 | Error recognition and recovery | 2 | Historical failures are inspectable; live failure/save/conflict paths deliberately not triggered |
| 10 | Help and documentation | 3 | Contextual game instructions/history explanation, weather units and revision warning; no comprehensive help audit |
| | **Total** | **26/40** | **Provisional “Acceptable”; not a release acceptance score** |

Total computed by `a-live-verify.py`, not estimated.

## Cognitive load / personas / emotional journey

- Most guest top-level decisions are grouped into three or four views. Desktop host actions exceed four visible choices, but separate upkeep/history/permissions/refresh/overflow into a stable host cluster; narrow disclosure reduces that cluster.
- Research's primary-task focus and hierarchy are the weak cognitive-load checks on narrow screens; search/result grouping itself is a strength. Sky's coordinate form creates an outside-information dependency. Pair presents the clearest single task.
- **Casey, narrow-device user:** app320 clipping and disappearing identity are the major red flags; app390 Pair is notably more usable.
- **Jordan, first-timer:** live-versus-not-refreshed Sky and raw cron need interpretation the UI should provide.
- **Sam, low-vision/keyboard user:** reduced effective widths expose containment risk. No screen-reader, zoom200, focus-trap or contrast-ratio certification is claimed.
- Emotional peak: distinctive calm composition and ready-to-use content. Valley: narrow compression and technical city-entry burden. End-state evidence: Pair's empty History is reassuring and honest, but completed-round end states were not present and were not manufactured by playing.

## Visually inspected primary image paths

All paths below are exact; each was opened with the vision tool and inspected as an image, not inferred only from DOM text.

- /Volumes/Expansion/Development/Build/r1-qualification-t_b3b306df/addendum/a-live-index-desktop.png
- /Volumes/Expansion/Development/Build/r1-qualification-t_b3b306df/addendum/a-live-index-390.png
- /Volumes/Expansion/Development/Build/r1-qualification-t_b3b306df/addendum/a-live-sky-loaded-desktop.png
- /Volumes/Expansion/Development/Build/r1-qualification-t_b3b306df/addendum/a-live-sky-loaded-390.png
- /Volumes/Expansion/Development/Build/r1-qualification-t_b3b306df/addendum/a-live-sky-loaded-320.png
- /Volumes/Expansion/Development/Build/r1-qualification-t_b3b306df/addendum/a-live-sky-week-desktop.png
- /Volumes/Expansion/Development/Build/r1-qualification-t_b3b306df/addendum/a-live-sky-week-390.png
- /Volumes/Expansion/Development/Build/r1-qualification-t_b3b306df/addendum/a-live-sky-cities-390.png
- /Volumes/Expansion/Development/Build/r1-qualification-t_b3b306df/addendum/a-live-research-desk-desktop.png
- /Volumes/Expansion/Development/Build/r1-qualification-t_b3b306df/addendum/a-live-research-desk-390.png
- /Volumes/Expansion/Development/Build/r1-qualification-t_b3b306df/addendum/a-live-research-desk-320.png
- /Volumes/Expansion/Development/Build/r1-qualification-t_b3b306df/addendum/a-live-research-detail-desktop.png
- /Volumes/Expansion/Development/Build/r1-qualification-t_b3b306df/addendum/a-live-research-detail-390.png
- /Volumes/Expansion/Development/Build/r1-qualification-t_b3b306df/addendum/a-live-pair-play-desktop.png
- /Volumes/Expansion/Development/Build/r1-qualification-t_b3b306df/addendum/a-live-pair-play-390.png
- /Volumes/Expansion/Development/Build/r1-qualification-t_b3b306df/addendum/a-live-pair-play-320.png
- /Volumes/Expansion/Development/Build/r1-qualification-t_b3b306df/addendum/a-live-pair-history-390.png
- /Volumes/Expansion/Development/Build/r1-qualification-t_b3b306df/addendum/a-live-permissions-desktop.png
- /Volumes/Expansion/Development/Build/r1-qualification-t_b3b306df/addendum/a-live-upkeep-desktop.png
- /Volumes/Expansion/Development/Build/r1-qualification-t_b3b306df/addendum/a-live-sky-window-revision-proof.png
- /Volumes/Expansion/Development/Build/r1-qualification-t_b3b306df/addendum/a-live-research-desk-revision-proof.png
- /Volumes/Expansion/Development/Build/r1-qualification-t_b3b306df/addendum/a-live-pair-play-revision-proof.png

`a-live-captures.json`, `a-live-flow-captures.json`, `a-live-final-captures.json` record actual per-capture app/guest viewport, crop and public DOM context. `a-live-revision-receipts.json` records actual Current revision text. There are 30 unique retained images in these receipts, including auxiliary and superseded captures; not all auxiliary captures are claimed as visually reviewed. `a-live-original.json` and `a-live-release.json` are the exact restoration pair. Supporting drivers: `a-live-capture.py`, `a-live-flows.py`, `a-live-final-probe.py`, `a-live-verify.py`.

## Limits / parent synthesis prompts

No detector, mutation, persistence correctness, completed-game elapsed-time formatting, failure simulation, screen-reader, reduced-motion, forced-colors or full keyboard qualification in this window. Original host history attempts named `*-revisions.png` actually show Run history; only `*-revision-proof.png` should be used for revision verification. Revisions were verified visually after correcting the input method; this is not a product-tab failure.

Questions for parent synthesis, not a request to extend custody: prioritize (a) host/guest app320 containment, (b) app390 research reading density, or (c) freshness terminology? Preserve all three visual worlds and fix the top issue first, or include the four P2 improvements in the next scoped pass?
