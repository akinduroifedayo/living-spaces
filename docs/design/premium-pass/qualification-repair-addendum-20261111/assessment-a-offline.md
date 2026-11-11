# Assessment A — Living Spaces R1, offline design critique

Method: isolated Assessment A subagent (Astra); pinned-source and supplied screenshot inspection only. This is not the combined Impeccable critique or live release acceptance. No detector findings or Assessment B were read. No browser, CDP, store, install, or source changes were made.

## Outcome and design specificity

**Preserve the authored guest worlds; do not accept the narrow host header yet.** Sky Window's night-weather scene, Research Desk's paper-and-ink reading room, and Pair Play's tactile orchard deck are recognizably different applications, not one dashboard recolored three times. The neutral host is appropriately conventional for an Operate surface. The problem is allocation of scarce space and competing status layers, not lack of visual ambition.

The newer native screenshots show a coherent compact header at app900, a severely abbreviated identity at app390, and a completely invisible Space name at app320. A dedicated identity row is a credible bounded repair, but it buys recognition with meaningful vertical cost. **The proposed `flex-basis:100%` identity rule has not been seen rendered and receives no acceptance here.** It also cannot repair the already-visible guest horizontal overflow by itself.

## Evidence and limits

Repository read only through `git show 5abf8224b0efcee53f4c9ac16d16fcf1a53c8b71:<path>`:

- `src/desktop/ui/space.jsx`: `useHeaderMode`, SpaceView identity/actions, status/error banners, source-level confirmation and focus-return intent.
- `src/desktop/ui/styles.js`: `.ls-framebar`, `.ls-identity`, `.ls-name-row`, `.ls-frame-meta`, header modes, content minimum heights, motion/forced-colors rules.
- `docs/design/DIRECTION.md`.
- `docs/design/premium-pass/final-review/HOST-CHROME-SPEC.md`.
- `src/living-spaces/skills/build-space/SKILL.md`.
- `src/living-spaces/runtime/kit/README.md`.

These design documents explicitly distinguish proposals from verification. The build guidance correctly requires measuring the actual canvas, compressing decorative mastheads before essential text, and checking task visibility rather than overflow alone. The screenshots expose incomplete realization of those principles, not a need to replace them.

Impeccable skill and critique playbook loaded. Parent reports context setup already run; it was not repeated against mutable source. Native-header-r5 is attributed to this installed source by the commission/Forge, not independently rebound to a running process by this review. Its `observation.json` is supplied prior measurement evidence, not a measurement made here. Earlier polished captures are historical real-chat visual evidence (commission labels Sky12, Research19, Pair11), not proof of their current installed revisions. No image was synthesized or recaptured.

## What works

1. **Useful division between host and authored content.** Persistent host controls retain one language while the frame gives each Space a distinct material and composition. The quiet index makes names, ownership and status scan well; it need not imitate each guest's art direction.
2. **Task-specific composition earns the premium feeling.** Sky gives weather a recognizable place and scale; Research's desktop search/results beside reading detail minimizes context switching; Pair's narrow capture puts the playable board ahead of its slogan and secondary statistics. Pair is the strongest narrow task-first example inspected.
3. **Truthful-state intent is present in source.** Save status is silent when idle, current errors have explicit recovery affordances, missing metadata is not padded with meaningless placeholders, and History/Upkeep move to overflow using actual frame width. Source contains reduced-motion and forced-colors handling. These are strengths of implementation intent, not certificates of working accessibility or recovery.

## Priority issues

### P1 — Host identity disappears at app320

**Observed:** `header-320.png` retains the generic tile and “Ready” but no Space name. The supplied measurement gives the name a width of zero; at app390 it has roughly 51px and reads “Rese…”. Meanwhile the back button keeps its full label. The guest's own masthead cannot substitute for host identity: it may be scrolled away, crashed, or display arbitrary generated content.

**Impact:** Users lose the context needed to trust Refresh, Permissions and the overflow actions. This is a recognition and control-targeting problem even though the host document itself does not overflow.

**Bounded direction:** Reserve useful identity width at the narrow frame size and validate status/name coexistence. The proposed dedicated row may do that; do not treat a CSS edit or a nonzero name width as sufficient. Check real long names and non-Ready states, plus meaningful identification at the actual app320 frame width. Suggested follow-up: `/impeccable adapt`.

### P1 — App320 still clips the guest working surface

**Observed:** Native Research app320 has a horizontal scrollbar and a cut-off guest Refresh control. Supplied guest width is 221px while document/body width is 254px: 33px horizontal excess. Historical Sky app320 also shows horizontal scrolling, a clipped Cities tab, “Chicago” breaking midword, and squeezed city values. This is not evidence that the newest Research guest has the same source as the historical Sky guest; they are separate observations with the same containment risk.

**Impact:** Essential controls and comparison text no longer read as a stable working interface. Outer-document `docW == app width` is not an acceptance test for the nested canvas.

**Bounded direction:** Verify each guest at its real sub-app viewport; wrap navigation and compress the guest masthead/secondary copy before essential values. Do not solve this by hiding the scrollbar or clipping the canvas. The extra host identity row changes height, not this width defect. Suggested follow-up: `/impeccable adapt`.

### P2 — Diagnostic language and layered states make recovery harder to interpret

**Observed:** All newer captures show “Ready”, “Internet on”, and “Bot request: offline” together. These can be technically compatible, but the distinctions are not self-explanatory. The error body exposes `404: {"detail":"Not Found"}. No automatic resend.` A visible “Check bot status” action is better than a dead end, but the body does not explain what part of the task failed or what remains usable.

**Impact:** A first-time user must translate server output and decide which of several status systems to believe. The current banner also occupies substantial space above already-constrained guest content.

**Bounded direction:** Keep the failure visible and scoped to the bot request; explain the failed action, retained content and next step in user language, with raw diagnostics secondary. Do not remove the warning merely to reclaim height, or relabel the whole Space as offline without authoritative evidence. Whether checking status actually recovers is untested. Suggested follow-up: `/impeccable clarify`.

### P2 — Research's narrow opening delays the actual research work

**Observed:** At native app390 the initial guest viewport is largely masthead, four navigation labels and “A little clarity. Ahead of the curve.” The useful list is not visible. The earlier Research390 capture similarly spends most of its first view on identity/navigation/slogan before the shortlist. This predates the proposed identity-row change. Historical Sky320 also spends scarce height on a heavily wrapped slogan before the principal detailed reading.

**Impact:** On returning visits the product makes users pass its introduction before doing the job. Additional host height compounds this rather than creating it.

**Bounded direction:** Preserve the typography and materials but compress ornamental introduction at narrow canvas widths, following Pair390's board-first example. Do not remove meaningful error/status text to preserve a slogan. Suggested follow-up: `/impeccable distill`.

## Proposed extra identity row at app320: cost, benefit, acceptance bar

The pinned source currently lets Back and identity share the first flex line; non-wide actions occupy their own wrapped area. The header mode is measured from `.ls-frame`, not the app window. Therefore app900 is a **640px compact frame**, app390 about **301px**, and app320 about **247px**. These screenshots are cropped to the Space frame; their filenames are app widths, not PNG/canvas widths.

Measured baseline from the supplied observation:

| App width | Frame width | Header height | Guest viewport |
|---|---:|---:|---:|
| 900 | 640px | 109.5px | 614 × 543px |
| 390 | 301.34375px | 165.5px | 275 × 467px |
| 320 | 247.265625px | 165.5px | 221 × 467px |

**Source-only scenario, not measured output:** If `flex-basis:100%` moves `.ls-identity` onto its own line while all other rules remain, Back becomes a separate 32px line plus the existing 10px row gap. If the identity's current 60.5px height and other content remain unchanged, this adds **42px**: header **207.5px**, guest approximately **425px** high rather than 467px, a loss of about **9%** of the current guest height. The header alone rises from about **21% to 26%** of the supplied 790px frame height. These arithmetic projections were calculated with `bc`; browser flex sizing, metadata wrapping, minimum heights and content state can change the result. They are not a screenshot substitute or a guaranteed height budget.

Potential width benefit: after 12px side padding, the identity row would have about 223.27px instead of 121.89px. After its 32px tile and 10px gap, about 181.27px remains for the name/status region. The status pill and its gap still consume that region: **a full untruncated name is not guaranteed**, particularly for longer status labels. A useful ellipsis is acceptable; a zero-width identity is not.

**Judgment:** Trading a modest additional row for restored identity is reasonable in principle. It is not free: the current offline banner plus generous Research masthead already delay the task. The row must be assessed on the full composed screen, not an isolated header crop. I would not reject it solely for being taller, and I would not accept it merely because the title becomes nonzero.

**Required newer evidence before acceptance:** actual app320/390/900 captures of the implemented proposal; exact app, frame and guest dimensions; readable name/status and reachable Refresh/Permissions/overflow; title variation and expanded save/status text; with and without the bot-error banner; initial task visibility and guest overflow for all three Spaces; keyboard focus/overflow-menu return checked by the authorized live reviewer. No live interaction is requested or attempted by this offline assessment.

## Nielsen heuristics — bounded visual scores, not release grades

Scale: 0–4, higher is better. Numeric entries assess only the visible presentation. “Untested — unscored” means applicable but not exercised, not `n/a` or a passing score. No composite health score is assigned to incomplete, mixed-age evidence.

| # | Heuristic | Assessment | Evidence / limitation |
|---|---|---|---|
| 1 | Visibility of system status | 2/4, visual only | Explicit status and freshness; clamped context and Ready/offline layering require interpretation. Refresh/save transitions untested. |
| 2 | Match to real-world language | 3/4, visual only | Names, Library, Reading queue and game language are natural; raw 404 body breaks the pattern. |
| 3 | User control and freedom | Untested — unscored | Back, overflow and source-level confirmations exist; navigation, cancel, focus return and restoration were not exercised here. |
| 4 | Consistency and standards | 3/4, visual only | Common host grammar and intentional guest differences; duplicate host/guest Refresh controls leave scope learning to the user. Behavioral consistency untested. |
| 5 | Error prevention | Untested — unscored | Source has locks, confirmation and conflict handling; no destructive, invalid-input or concurrent-write path was tested. |
| 6 | Recognition rather than recall | 2/4, visual only | Named controls and distinct canvases help; vanished host title and hidden narrow upkeep status undermine orientation. |
| 7 | Flexibility and efficiency | Untested — unscored | No timed task, keyboard accelerator or repeated-use flow was exercised. |
| 8 | Aesthetic and minimalist design | 2/4, visual only across supplied sizes | Strong authored desktop work and Pair390 board hierarchy; app320 clipping and narrow introductory overhead prevent a higher cross-size score. |
| 9 | Error recognition, diagnosis, recovery | 1/4 for observed error copy only | Names bot-request failure and offers a check, but raw diagnostic body does not explain a remedy. Actual recovery remains untested/unscored. |
| 10 | Help and documentation | Untested — unscored | Source docs and a historical index chat hint were seen; discoverability and adequacy of in-product help were not exercised. |

## Cognitive load and personas

The main intrinsic work is reading/research triage, weather comparison, or remembering card positions. The host should not add a second task of deciphering scope/status.

Checklist, restricted to visible composition:
- **Single focus: fails on narrow Research opening.** Host recovery, guest introduction and navigation precede the research task.
- **Chunking: generally supported.** Guest top-level navigation is three or four items. The app900 host offers five action choices (Upkeep, Internet on, Permissions, Refresh now, overflow), plus separate Back. This is a review signal, not proof that five choices alone overload users; the primary is clearly distinguished.
- **Grouping: supported.** Frame boundary, research rules and game board separate responsibilities.
- **Visual hierarchy: fails at app320.** Status survives while identity vanishes; critical guest controls clip.
- **One thing at a time: mixed.** Research desktop detail is co-located; the native bot failure demands a competing decision. Interaction sequencing is untested.
- **Minimal choices: concern, not a blanket failure.** Internet on and Permissions lead to the same source-level sheet. Do not count the game's twelve cards as twelve unrelated menu choices; their spatial array is the task.
- **Working memory: visual failure in host orientation.** The name cannot be recalled from a host title that is not visible. Persistence and return-to-task behavior are untested.
- **Progressive disclosure: present in source and appearance.** Overflow and Research's closed Add a paper are sensible. Their behavior was not revalidated.

Persona red flags (scenario walkthroughs, not user tests):
- **Jordan, first-time user:** opens Research and sees Ready/Internet on/offline together, then a raw 404. It is unclear whether Refresh now, guest Refresh or Check bot status addresses the problem. Narrow host identity provides little reassurance about which Space is affected.
- **Alex, returning power user:** desktop research adjacency and narrow Pair board placement are efficient. Repeated narrow Research visits spend screen space on a slogan rather than papers. No claim is made about missing shortcuts or click counts; those were not tested.
- **Sam, low-vision/keyboard-dependent user:** title compression and small secondary metadata are clear risk signals. CSS contains visible-focus and reduced-motion intent; actual contrast, zoom, tab order, announcements and menu/dialog behavior are untested. Native 32px host buttons meet the supplied desktop spec; they should not be casually certified as the kit's 44px touch targets or as a phone usability pass.

Emotional journey: the index promises manageable owned tools; entering the distinct guest world is the visual high point. Narrow clipping and a technical bot error interrupt that confidence before the task begins. Pair390 recovers attention by putting the board immediately at hand. No completed save, refresh, win, recovery or return visit was exercised, so peak/end behavior is not scored.

## Images inspected (all supplied files, loaded directly)

Newer native-header-r5 directory:
`/Volumes/Expansion/Development/Build/living-spaces-r1/run/recovery-r3-evidence/native-header-r5/`

- `header-900.png`
- `header-390.png`
- `header-320.png`
- Companion measurements read: `observation.json` (not an image).

Historical polished directory:
`/Volumes/Expansion/Development/Build/r1-qualification-t_b3b306df/addendum/`

- `a-live-sky-loaded-desktop.png`
- `a-live-sky-loaded-390.png`
- `a-live-sky-loaded-320.png`
- `a-live-research-detail-desktop.png`
- `a-live-research-desk-390.png`
- `a-live-pair-play-desktop.png`
- `a-live-pair-play-390.png`
- `a-live-index-desktop.png`

All eleven images above were inspected; no Assessment B images or findings were opened. Desktop images were readable at their supplied resolution; separate crops were not needed. Historical Pair320 and Research320 polished captures were not part of this inspected set; current native Research320 is covered, but that does not supply Pair320 evidence.

## Gaps and execution notes

No new live qualification, screen-reader, contrast, 200% zoom, light-theme, forced-colors, reduced-motion, focus traversal, save/conflict, game completion, permission-change or refresh execution checks were performed. The proposal remains unseen. The older guest images cannot establish current release parity. Source-level safeguards and a prior focus observation do not close these gaps.

An attempted read-only Python batching command and an arithmetic `execute_code` call were blocked by unattended execution policy. Neither ran. Direct pinned `git show` reads and `bc` arithmetic succeeded; no approval/config workaround was attempted. Only this requested report was written. No source, runtime, store, install, browser state or skill was modified.

Questions skipped: this is the explicitly headless, bounded Assessment A commission; no interactive questions permitted. The acceptance checks above are handoff requirements, not approval of the proposal.
