Method: isolated Assessment A — independent design review; no detector run or detector findings consumed. Parent owns Assessment B, synthesis, and fixes.

# Space kit / reference critique — Assessment A

## Scope and evidence

Mode: **Operate** throughout, including the gallery. Reviewed incumbent source and visually inspected the existing server in isolated browser session `space-critique-a`; no Forge app, Desktop, or live home inspected. Used the commissioned brief rather than interviewing the user.

Browser coverage:
- `/?example=research-desk`: settled Overview, light/dark desktop at 1440 × 1000; narrow dark at 390 × 844.
- `/?example=habit-planner`: light desktop and narrow dark.
- `src/living-spaces/skills/build-space/references/kit-gallery.html`: all seven starting identities visually compared (Editorial, Terminal, Playful, Minimal, Data-dense, Warm journal, Game); Editorial light desktop, Terminal dark desktop including states, and Warm journal narrow light. Not a complete seven-by-two-theme responsive matrix.
- `/weather-off.html`: simulated host Internet Off, light desktop empty state, **Explore sample** activated, labelled synthetic chart, narrow dark chart and expanded exact-values table.
- `/?example=weather-window`: actual sandbox's unavailable-live state, dark desktop.

Read kit CSS/module and reference implementation files. The preview uses synthetic in-memory records; weather sample values are illustrative, **not actual weather**. Network enforcement belongs to Forge; this review makes no production networking claim. The standalone off fixture and actual sandbox report different states correctly; they are not interchangeable evidence.

Limitations: sandbox pointer attempts did not produce a reliable Library navigation or check-in transition in this browser session. Do not interpret that alone as a product defect. Editor draft-loss finding below is source-supported, not an observed browser reproduction. No assistive-technology session, exhaustive keyboard run, or measured contrast audit was performed. Initial iframe boot and resize captures were sometimes unsettled; judgments use settled views, not transient blank/clipped frames. Context loading found no PRODUCT.md, DESIGN.md, or surface brief; the commissioned brief and incumbent implementation supply scope.

## Design specificity verdict

**A credible plural kit, with stronger identity variation than task composition in Research Desk.** Editorial's sharp sage surfaces and serif hierarchy, Terminal's compact monospaced blue-black treatment, and Journal's warm, generous serif treatment are distinguishable visual worlds. Playful and Game separate themselves through rounding, scale, and Game's dotted field; Minimal and Data-dense are quieter, closer relatives. The seven are useful optional starts, not seven rules agents must obey.

The repeated gallery arrangement is appropriate for comparing components, not evidence that every Space must use that arrangement. Weather Window is the strongest proof of freedom: its atmospheric field, asymmetric plot enclosure, temperature-led composition, and no-kit implementation actually organize a different task. Daily Practice also earns its simple date/add/check structure. Research Desk is less specific: its first view presents four generic counters and freshness administration rather than the user's reading. Preserve composability; improve that reference's task emphasis rather than standardizing all Spaces into one dashboard.

## Nielsen design-health scores

Scale: 0 absent/broken, 1 weak, 2 partial, 3 good, 4 excellent. All ten apply to Operate. These are scoped design judgments, not certification.

| # | Heuristic | Score / 4 | Evidence / constraint |
|---|---|---:|---|
| 1 | Visibility of system status | 3 | Named save states, refresh history, explicit synthetic/unavailable status; root Overview lacks an active nav treatment. |
| 2 | Match with real world | 3 | Library, Queue, Day, and degrees Celsius are natural; freshness administration occupies disproportionate reading-workspace attention. |
| 3 | User control and freedom | 2 | Reversible habit checks and conflict choices; editor drafts are local to an unmountable view. |
| 4 | Consistency and standards | 3 | Native controls and consistent semantic status language across intentionally different identities. |
| 5 | Error prevention | 2 | Empty-add guards, disabled pending actions, and revision checks; no dirty-editor departure guard. |
| 6 | Recognition rather than recall | 3 | Visible text labels and exact-value table; default Overview is not visually marked current. |
| 7 | Flexibility and efficiency | 2 | Enter-to-add implementation, search, optional tokens/presets; reading starts with an administrative overview rather than an immediately actionable item. |
| 8 | Aesthetic and minimalist design | 3 | Clear hierarchy and restrained grouping overall; Research Desk prioritizes telemetry over work. |
| 9 | Error diagnosis and recovery | 3 | Retained-draft conflict language and local sample fallback; live-load CTA still invites an unavailable operation. |
| 10 | Help and documentation | 2 | Inline specimen and state explanations are useful; host Permissions instructions do not provide a direct contextual route here. |
| **Total** | **Acceptable — targeted improvements needed** | **26 / 40** | Sum checked programmatically. |

## Cognitive-load checklist

| Check | Result | Evidence |
|---|---|---|
| Single focus | Pass | Habit entry/check-in and weather location/sample tasks remain identifiable. |
| Chunking, ≤4 related items | Pass | Four reading counters, three cities, three reading-list items. |
| Related visual grouping | Pass | Forms, lists, provenance, and chart/table are consistently grouped. |
| Visual hierarchy | **Fail: Research Desk** | The only header action is Refresh; counters and a large freshness panel precede any paper or reading action. |
| One decision at a time | Pass | Sample exploration precedes details; native selectors isolate a choice. |
| Minimal visible choices | Pass, with bounded exception | Three cities and two weather actions are separate groups. Expanded identity selector has eight choices (default plus seven); acceptable as an occasional expert preview selector, not a proposed end-user first-run chooser. |
| Working-memory demand | Pass | Units, provenance, selected city/date, and exact values stay attached to the work. |
| Progressive disclosure | Pass | Weather table and gallery details are on demand; error specimens are deliberately visible in the gallery. |

**One failed item: low cognitive load overall**, with misplaced emphasis rather than a general wall-of-options problem. Eight static accent swatches are specimens, not eight competing actions.

## What works

1. **Freedom is demonstrated, not merely promised.** Weather Window departs structurally and visually from the kit, while the seven identities vary type, geometry, density, and palette without rewriting familiar controls.
2. **Honest state and data language.** Synthetic labels survive sample exploration; charts have units, labelled extents, and exact tables. Gallery copy explicitly distinguishes a failed fetch from confirmed Internet Off.
3. **Calm task surfaces adapt usefully.** Daily Practice remains a short date/input/check sequence; narrow controls grow and forms stack. Text labels and border styles supplement semantic colors.

## Priority issues

### 1. [P1] Protect unsaved paper notes when leaving the editor

**Evidence:** `research-desk/views/editor.js:9–20,64–69` keeps the draft only in component state. `views/library.js:49–56` immediately changes selection and keys Editor by paper ID; `app.js:45` replaces the route component. Neither path gates departure or retains the draft. The visible “You have an unsaved draft” implementation warns but cannot prevent that unmount. Source-supported; not browser-reproduced in this pass.

**Impact:** Alex switching papers or Jordan following Queue can lose authored notes. Good conflict handling does not cover ordinary navigation loss.

**Fix:** Keep per-paper drafts above the route/selection lifetime, or intercept dirty departure with Save / Discard / Stay. Preserve draft and focus if saving fails. Do not add confirmations to already-saved navigation.

**Suggested command:** `/impeccable harden`.

### 2. [P2] Make the available weather action primary when live loading is unavailable

**Evidence:** In both observed unavailable states, **Load forecast** retains the strongest filled treatment while **Explore sample** is secondary. The actual sandbox says live forecasts are unavailable. After sample exploration, `weather-window/app.js:59` nevertheless says “Load forecast to return to live data”; lines 41–44 reject that operation for the reviewed host states.

**Impact:** Jordan follows the strongest affordance into the same dead end. The sample's reassuring end state reintroduces a promise this runtime cannot fulfill.

**Fix:** Promote Explore sample when live loading cannot run. Distinguish confirmed Internet Off (explain the host Permissions route) from unsupported runtime (explain the limitation). Condition the post-sample instruction; never imply that this Space can bypass host policy.

**Suggested command:** `/impeccable clarify`.

### 3. [P2] Stop shrinking chart text with the whole SVG on narrow screens

**Evidence:** At 390 px, the synthetic weather chart's time/axis labels are visibly miniature while adjacent body text stays readable. `weather-window/app.js:24–27` uses a fixed 550-unit viewBox, and the narrow CSS still sets SVG axis text at 13 units. The expanded table offers a readable workaround, but requires disclosure and horizontal scrolling to reach the rain column.

**Impact:** Sam cannot comfortably read the plotted time/temperature scale at normal phone size. The chart becomes a decorative trend unless the table is opened.

**Fix:** Render a narrower responsive viewBox with fewer time ticks and screen-sized labels; maintain the explicit unit and linear scale. Keep the exact-value disclosure, and make its horizontal overflow keyboard-reachable and apparent. Verify the result at narrow width and zoom rather than merely increasing SVG font units globally.

**Suggested command:** `/impeccable adapt`.

### 4. [P2] Give Research Desk a reading-led entry and an unambiguous current view

**Evidence:** Settled desktop Overview shows four counts, then a full-width freshness panel; no paper title or Continue reading/Open queue action. At narrow width these expand into a long preamble. Overview, Library, and Queue all appear unselected on initial load. `app.js:8–12` maps both `/` and `/overview` to Overview, while `spaces-kit.mjs:209–211` marks current only by exact path equality.

**Impact:** Alex must leave the first view to start work; Jordan sees no clear primary reading action or selected location. This is a hierarchy problem, not a request for more decoration.

**Fix:** Lead with a next queued/active paper and Open queue or Continue reading, with Add a paper for a truly empty library. Collapse freshness into a compact secondary summary with expandable timestamps. Normalize the default route or give Nav an explicit current-view alias so Overview is marked current immediately.

**Suggested command:** `/impeccable layout`.

## Persona red flags and emotional journey

- **Alex:** Direct add/search patterns are promising, but the first Research Desk screen offers monitoring rather than reading. Rapid selection changes also cross the source-identified draft-loss boundary. Do not solve this with forced onboarding.
- **Sam:** Native controls, labels, text statuses, reduced-motion rules, and chart descriptions are sound foundations. Narrow chart labels remain the specific visual failure; full screen-reader and keyboard behavior still need separate verification.
- **Jordan:** Weather's honest unavailability message is reassuring, but the primary live-load button and post-sample instruction contradict its practical next step. Unmarked Overview makes the research starting location harder to learn.

Emotional arc: the distinct, quiet interiors make entry approachable; explicitly retained records/drafts and labelled samples reassure at failure points. The valley is task momentum: Research Desk delays the reading payoff, and Weather sends the user back toward unavailable live loading after a successful sample. Make the end state useful and truthful, not merely visually finished.

## Minor observations / synthesis prompts

- Gallery `Reset fields` only clears the textarea (`kit-gallery.html:58`); rename it `Clear example notes` or actually restore every field. This is specimen behavior, not evidence of a production save defect.
- Keep optional presets optional. The stronger next reference would demonstrate another task-specific composition, not require a palette selector in every Space.
- Parent synthesis question: should Research Desk default to the queue, or retain an overview with one actionable paper? Either can preserve the current editorial identity.

Questions skipped: delegated Assessment A only; the commissioning instruction explicitly reserves decisions and synthesis for the parent and forbids asking the user. No UI/source edits made; this report is the only repository file created by this assessment.
