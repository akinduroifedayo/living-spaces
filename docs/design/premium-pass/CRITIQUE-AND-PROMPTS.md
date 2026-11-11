# Three real Spaces — corrected pre-premium baseline

Method: dual-agent (A: deleg_d1f366c2/task-0 · B: deleg_d1f366c2/task-1), followed by Miro's direct image/crop inspection and synthesis. This is a **historical screenshot critique**, not a full live Impeccable critique/audit, interaction pass or product acceptance. No behavioral health score is assigned to unseen states.

## Decision and evidence correction

**Recommendation:** regenerate through normal chat after the revised design skill is integrated; judge whether the agent makes three purpose-specific applications, not whether it adds shadows or follows a hand-authored showcase. Preserve useful data and interaction. The weather chart needs clearer measurement semantics; Research needs a paper-first hierarchy; Pair needs a coordinated game identity and deliberate play surface.

This supersedes the baseline claims and art-directed prompts in the earlier `docs/design/premium-pass/02-critique-and-prompts.md`:
- Research Desk **does have** real, populated chat-updated evidence in the external build directory. Its reference screenshot is not the baseline.
- Pair Play's six dashed collection slots belong to **Progress**, not its twelve-card Play board. Its actual Play capture has blue star backs and a matched watermelon pair.
- Stills do **not** establish that motion, celebration or other uncaptured states are missing.
- Sky's rain bars are visible at the plot base. The capture does not establish clipping. The concrete problem is the missing visible numerical precipitation scale next to a degree-labelled temperature axis.

No application or repository files were edited. Forge owns copying this packet into `docs/design/premium-pass/` and any changes outside the separately commissioned design-skill/kit paths.

## Baseline identity and provenance

Packet root: `/Volumes/Expansion/Development/Build/premium-baseline-t_c75659a7/`.

`baseline-manifest.json` binds **12 staged PNGs: 11 actual historical Desktop captures and 1 reference-only capture** to source paths, source SHA-256, original dimensions, exact crop bounds, staged dimensions and staged SHA-256. Original actual captures are 1690×858 whole-window pixels, not measured guest CSS viewports. Actual staged captures are 1430×784 host+canvas crops, removing the Hermes sidebar/account footer without resizing or inventing pixels. The reference is retained at its original size. Source originals remain at their recorded paths. Request/run times are not exact screenshot timestamps; capture-to-revision binding is contextual where noted.

| Space | Actual source evidence | Binding / content |
|---|---|---|
| Sky Window | repo `docs/evidence/runs/sky-same-session-repair/{opened,week,cities}.png` and sibling request/receipt/views JSON | Chat repair 3→4; captured Today/Week/Cities report three live cities, retrieved 02:05 AM. `baseline/sky-*.png`. |
| Research Desk | external `living-spaces-r1/evidence/regenerate-research-desk-20261111-025333/` and `research-kit-interaction-20261111-032116/` | Chat update 7→8; first Overview has 26 papers; follow-up fixture makes 27. Actual Overview/Queue/Review/Saved/Reopened. `baseline/research-*.png`. |
| Pair Play | external `living-spaces-r1/evidence/postpackage-pair-play-open.png`; repo `docs/evidence/runs/r1-09-repair/02-progress-repaired.png` | Play board: 12 cards, 2 turns, 1/6 pairs; Progress: collected-pair summary. Repair receipt establishes good2→fault3→repaired4; Play's later revision correspondence is contextual, not hash-bound. `baseline/pair-*.png`. |

The external evidence root is `/Volumes/Expansion/Development/Build/living-spaces-r1/evidence/`. `assessment-b.md` details source/revision gaps. Historical source lacks a full per-capture manifest joining host build, code digests, capture time, viewport and DPR. This packet preserves a traceable baseline, not a claim of complete reproducibility.

## 1. Sky Window — useful weather dashboard, insufficiently authored

**Mode:** Operate, with ambient display appeal. **Strengths:** immediate city→temperature→condition scan; explicit weather words and icons; three task-based views; forecast/retrieval times and units are present.

- **Identity — P2:** rounded navy panels, purple header glow and a gradient weather tile make it recognizably weather software, but the two visible city cards share almost the same visual world despite overcast versus rain. Let the new agent choose a coherent concept grounded in conditions/place/time; do not prescribe skyline art or a particular palette.
- **Hierarchy — P2:** Chicago and Lisbon dominate the first viewport; Tokyo begins below it. Coordinates compete with city names. The six measurements occupy an eight-cell grid, leaving a large unlabelled filled remainder in each card. Demote coordinates, compact the secondary measurements and make the city comparison intentional. Preserve temperature and condition prominence rather than flattening everything.
- **Imagery — P2:** small line-condition glyphs and the tile are the only visible imagery. There is no larger environmental depiction. More authored condition imagery could earn its place here, provided weather values remain readable and imagery is not presented as a literal live camera view.
- **Visualization/interaction — P1:** Week directly labels high/low °C and the selected day's rain in mm, but cyan rain bars share the plot with a degree-labelled axis and no visible numerical mm scale. Separate or explicitly scale the precipitation measure; keep a text-value alternative and selected-day values distinguishable from final-day endpoint labels. A line chart is valid: replacing it merely to avoid a default chart is not the goal. Cities offers clear favourite/remove actions, but adding a place requires latitude/longitude; city lookup or optional advanced coordinates would reduce ordinary-user burden if commissioned. Do not invent a geocoder dependency for this pass.
- **Host integration — P1:** the canvas says `3 of 3 live · retrieved 02:05 AM`, while the host says `Last successful update Not reported · source data from Not reported`. This is conflicting status presentation, not proof that retrieval failed. Host Refresh now and guest Refresh need distinguishable purpose and honest feedback. Apply Forge's host-chrome implementation, subject to Product's truthfulness corrections, rather than restyling the guest to camouflage it.
- **States:** captured: Today, Week, Cities, current retrieval status, disabled add action and no favourite. Unverified: first load, zero cities, partial-city failure, stale last-good data, retry, invalid coordinates, long names, favourite persistence and refresh concurrency. Regenerated output must keep last-good weather and distinguish forecast time from fetch time.
- **Accessibility:** text+icon conditions, units and direct labels help. Dense small metadata and colour-coded chart series need measured contrast and keyboard/screen-reader checks; the visible instruction says `Hover or touch the chart for a day`, not proof of keyboard access or its absence. Verify a focusable day selector/table, non-colour identification and 44px touch actions.
- **Mobile:** no actual narrow baseline exists. The two-column cards, multi-cell metrics and Week plot are reflow risks, not observed phone defects. Verify 390px and 320px, all city names/actions, readable chart labels and touch selection without hover dependence.

## 2. Research Desk — real reading workflow, overview still admin-first

**Mode:** Operate + Read. **Strengths:** restrained olive-black/green editorial tone and serif heading; labelled status/priority badges; next-review action; actual saved-note and reopened-library evidence. This is not an empty reference render.

- **Identity — P2:** serif headings give a credible reading tone, but the repeated boxed totals, library icon tiles and status chart still lead like an administration dashboard. Make research recognition and reading the authored centre, not a more elaborate statistics wall.
- **Hierarchy — P1:** four totals and a chart retell the inventory before the person reaches an actual paper. The useful `Ready for review` panel says only that one high-priority paper is unfinished. Promote the next paper's title and context; subordinate compact totals. In Review, the fixture paper title is small inside a broad panel; strengthen title→metadata→summary→notes order.
- **Imagery — P2/opportunity:** no covers, figures or paper previews appear in the inspected views. Generic hero art is not required for a research tool. If appropriate, use truthful paper figures/document imagery or authored research-specific visual structure without inventing paper covers, findings or sources. A strong typographic reading app can also succeed.
- **Visualization/interaction — P2:** the status chart explicitly names its denominator (`27 papers in library`), zero baseline and values—retain that analytical honesty. The chart is largely redundant with the 27/22/1/4 tiles. Review shows `Paper 1 of 1 · Reading · High priority` with Previous, Next and Mark reading alongside Mark done. Make boundaries/current state unambiguous; the still does not prove whether those controls are disabled. Queue's split list/editor uses badges effectively, but the selection prompt and substantial chrome defer meaningful reading. Saved and reopened receipts support preserving the durable workflow, not replacing it with a decorative library.
- **Host integration — P2:** host freshness is populated here, unlike Sky. Its long absolute dates, save status and raw cron expression occupy a tall blue toolbar; the persistent sandbox caption adds another line. The guest repeats Refresh. Move operational detail to the host's intended panels and keep source facts discoverable. Do not repeat outdated absolute network/permission promises; current Product wording governs.
- **States:** captured: populated Overview and Queue, one-item Review, missing summary, Saved editor and reopened selected record. The no-summary fixture is explicitly a public probe, not evidence that public papers generally lack abstracts. Historical interaction receipt enumerates 14/14 checks, including note/status/priority preservation and reopen. Not rerun by Miro. Missing: no-match/empty library, long abstract/editor, in-flight save, failure, conflict, source refresh failure and durable recovery after interruption.
- **Accessibility:** labelled notes/status/priority and worded badges are strengths. Small navigation and Previous/Next/status buttons need target/contrast checks. Verify semantic document headings, focus restoration from list to editor, shortcut discoverability, note draft retention and meaningful save/conflict announcements; none is passed by a Saved label.
- **Mobile:** no actual phone evidence. Verify single-column list→paper transition, selected-paper context/back path, readable long titles, keyboard-visible notes and a reachable Save action at 390/320px and 200% zoom. Do not infer this from the separate kit mobile reference.

## 3. Pair Play — real playable game, generic visual vocabulary

**Mode:** Operate (play), with experiential expression. **Strengths:** a legible twelve-card grid; turns and pairs are near the task; matched cards show a checkmark, fruit name and green styling. Progress clearly states `1 of 6 pairs found · 2 turns so far`, and honestly explains the empty completed-round totals.

- **Identity — P2:** the memory grid is inherently game-specific. Blue star backs and fruit emoji are recognisable but visually disconnected. Give backs, faces, matched state and scorekeeping a coordinated identity; the agent should choose it, not be handed a felt-table mandate.
- **Hierarchy — P2:** the game occupies a roughly 440px column in a very wide canvas. Compactness can support play, but the oversized unused margins and small heading make this feel like a utility rather than a deliberate play surface. Improve proportions without filling the margins with more statistics or stretching cards beyond easy scanning.
- **Imagery — P2:** real star backs and watermelon faces exist. Improve their common art language and legibility; keep visible card names and non-colour match confirmation. Photography or generated assets are not a requirement when coherent drawn/SVG card art is more suitable.
- **Game interaction — P2:** Play exposes New round and a turn instruction; Progress exposes a six-pair collection, not a second game board. Progress has a clear selected-tab underline; the inspected Play view lacks an equally explicit selected treatment. Provide consistent navigation and an obvious resume path from Progress/History. `Ready` below the board says less than task-specific turn feedback. Test restart handling, two-card lockout, mismatch timing, match announcements, win state and best-score calculation. Stills cannot establish flip animation, absent celebration or correctness of those behaviors.
- **Host integration — P2:** host refresh/scheduling/freshness language is conspicuous for a local game and reports `Not reported`. Apply conditional factual metadata and quieter chrome through Forge. Do not invent scheduled game updates; preserve a clear distinction between game history and host upkeep history.
- **States:** captured: retained round with one match, unflipped backs, Progress in-flight and no completed rounds. Historical postpackage/reopen/repair receipts exist, but are separate checks, not one sum. Two initial interaction receipts retain a failed index-discovery check; do not relabel them green. Missing visual evidence: first round, active mismatch, full match sequence, completed round/history, reset decision, failed save and conflict.
- **Accessibility:** match checkmarks and text avoid colour-only state. Hidden-card accessible names must convey position/state without exposing concealed identities. Verify keyboard operation/focus visibility, live turn/match announcements, no pointer-only play, sufficient target size and a non-animated reduced-motion transition. None is established by this still.
- **Mobile:** the narrow desktop column is not a phone pass. Verify complete board fit at 390/320px, targets, no unintended zoom/horizontal overflow, interruption/resume and no card size collapse. Reduced motion must preserve the same turn logic.

## Reference contrast — not evidence substitution

`baseline/reference-weather-off.png` is the existing `assessment-b-weather-desktop.png`: explicitly labelled **simulated host / Internet Off / no network attempted**. It has a clearer asymmetric lead-city layout, large temperature slot and useful Load forecast/Explore sample actions. But its empty chart panel and flat blue composition do not demonstrate live data, generated output or premium interaction. Sky's real multi-city content is more useful evidence. Do not compare a reference's offline emptiness against a real live dashboard as if they were the same state.

## Regeneration handoff: exactly three ordinary chat prompts

**Gate:** WAIT for t_71cf754c's final updated skill/kit revision to be integrated and recorded by Forge. Use the prompts below through the normal Hermes chat path, one per existing Space; the skill chooses and executes art direction. No direct source injection, pasted implementation, forced showcase concept or hand-built HTML may substitute for proof of normal chat. The new prompts replace the earlier more prescriptive ones. If capability/auth/cost gates prevent an asset or a live source, report the gate rather than silently switching provider or fabricating a successful live state.

### Sky Window
> Give my Sky Window Space a fresh, polished design that you'd enjoy leaving open. Keep live Open-Meteo weather for Chicago, Lisbon and Tokyo, current conditions, today's range and a seven-day forecast, plus adding, removing and favouriting cities. Keep my saved cities and preferences. Make it work well on my phone too. You choose the visual direction.

### Research Desk
> Give my Research Desk Space a fresh, polished design for keeping up with public AI research from arXiv cs.AI. Keep the overview, searchable library, reading queue and high-priority review, with notes, status and priority for each paper. Keep my saved papers and notes, including when new papers arrive. Make it comfortable to read and use on my phone. You choose the visual direction.

### Pair Play
> Give my Pair Play Space a fresh, polished design for a memory game with six pairs of cards. Keep turns, current-round progress, completed-round history and personal best, and let me resume an unfinished round. Keep my saved rounds and settings. Make it satisfying to play on desktop and my phone. You choose the visual direction.

Machine-readable identical prompt text is in `regeneration-prompts.json`.

## Comparison receipt required from Forge (not extra user prompt instructions)

Record the exact chat input/trace, loaded skill commit, host commit, generated code revision/digests, public data provenance/freshness, guest CSS viewport/DPR, capture timestamp and PNG digests. Preserve failed turns and retries. Use the same public fixtures and viewport for like-for-like comparisons; label unavoidable data/time/host changes.

Per Space return: actual useful desktop first view and a secondary view, 390px and 320px layouts, and failure/offline states appropriate to its purpose. Sky: weather/current plus Week/Cities, partial/offline last-good recovery. Research: real paper, save/reopen, queue/review, no matches and source failure preserving notes. Pair: Play/mismatch/match/win, Progress/History, reopen and failed-save recovery. Cover keyboard, focus, measured contrast, 200% zoom, reduced motion and accessible status/visual equivalents. These are qualification asks, not existing passes.

`assessment-b.md` records limited detector evidence: exact generated Research generation material and an **older** Pair rev1 shell each returned `[]`. Those empty shell scans are **not clean DOM/a11y findings**, and the Pair scan does not qualify the captured later game. Exact Sky rev4 and Pair rev4 source and live populated-DOM scans are missing. No new browser run, service, network fetch, model regeneration, audit or polish was performed in this task. Downstream regeneration/review cards own those steps.

Questions skipped: this headless commission already fixes the next action (three function-preserving normal-chat regenerations after skill integration); no new human decision or implementation authority is requested. This is a scoped historical evidence review, not a completed interactive `/impeccable critique` command.
