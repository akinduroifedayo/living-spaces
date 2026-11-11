# Impeccable audit · kit and references

## Implementation integrity verdict

**Coherent scoped implementation, with explicitly bounded evidence.** The shared CSS retains existing runtime class names, supplies semantic components and optional tokens, and does not import dependencies. The reference apps use real kit/bridge callers with synthetic records in the preview. Weather Window uses no kit and does not bypass hosted network policy. Production network, font/manifest injection and real-chat qualification remain Forge's responsibility.

## Audit health

| Dimension | Score /4 | Evidence / remaining limit |
|---|---:|---|
| Accessibility | 3 | 272 computed palette pairs pass; native Tab focus/reduced-motion and labelled inputs checked; no VoiceOver certification |
| Performance | 4 | Dependency-free CSS, small local SVG, no network requirement for core kit; no broad will-change/layout animation |
| Theming | 4 | Default and seven presets computed in light/dark; actual editorial/journal sandbox palettes observed; arbitrary overrides require revalidation |
| Responsive | 3 | 320/390/720px geometry passes; mobile specificity defect fixed; narrow habit capture remains unreliable |
| Integrity | 3 | Real reference code, preserved save/revision semantics and synthetic stamps; detector/template/CSP limits documented |
| **Total** | **17/20** | **Good, not an exhaustive release/accessibility certificate** |

## Issues found and disposition

- **P1 Accessibility/Responsive — input target rule specificity.** Base input exclusions outranked the narrow rule, leaving text/date inputs at 37/39px. Match the full selector in the narrow rule. Final measured narrow controls pass the 44px height check. WCAG 2.5.8's minimum is not itself 44px; this is the commissioned usability floor.
- **P2 Responsive — freshness disclosure 32px.** Reference summary now has 44px minimum height and vertical alignment.
- **P2 Integrity — contradictory network guidance.** Optional design defaults now explicitly defer to Runtime/project files, owned by Forge. No direct-fetch/CDN/embed capability claim remains in the design section. Hosted Weather Window shows unavailable/sample rather than attempting direct fetch.
- **P2 Theming — root attributes discarded by existing loader.** References select themes on body as well as html; loader copies body attributes. Runtime seam was reported to Forge, not repaired here.
- **P2 Responsive — SVG label shrink.** Width-aware viewBox and sparse narrow ticks retain readable temperature/time labels. Sample uses real local linear-scale calculations; no decorative curve.
- **P2 specimen consistency — planner max-width specificity.** main.space-app now retains the intended 720px maximum rather than inheriting the generic 1120px shell.

## Execution

- `node --test tests/js/sandbox/index.js tests/js/ui/index.js`: 112 passed, zero failed on this branch's Forge base 44211c8.
- `node --no-warnings --experimental-vm-modules --import ./tests/js/reference/env.mjs --test tests/js/reference/compatibility.test.mjs`: 19 passed, zero failed.
- Initial reference test invocation without the env import failed to resolve Preact; corrected command used the existing repo resolver. No package installed and no test changed.
- `check-browser.mjs`: current-page-bound CDP contexts; 27 measured page states, existing trusted-input replays for both refs, draft remount, native Tab focus and static reduced-motion cue pass. Exact JSON and replay check names in browser-checks.json. This is not 27 unique workflows.
- `contrast.json`: 272 checks over default + seven presets, light/dark; text/link/muted on base/card/surface, semantic statuses, primary-action text, focus and control-line contrast. Palette values were resolved by Chromium before WCAG luminance calculation. Not an arbitrary-user-theme guarantee.
- Detector executed once by Assessment B, eight context-verified source warnings. Raw output and source coverage limits retained. Not rerun to erase warnings.

## Visual evidence limitations

Final light/dark desktop references, gallery, weather Off/sample pair, library/editor and representative narrow frames/crops were inspected. A narrow habit PNG repeatedly captures a white nested-frame surface despite valid inner DOM geometry and working source/state tests. It is retained as a diagnostic, **not visual acceptance**. This may be a capture/compositor defect; its cause is not proven. Do not infer absence of an implementation defect from the passing DOM measurements. Desktop habit light/dark renders are valid.

No physical touch gestures, screen reader, Safari/Firefox, browser-level 200% zoom, exhaustive long-content/localization matrix, or production Electron theme switching was qualified here. Canvas/WebGL/game interaction is not tested; gallery board is explicitly a disabled static anatomy specimen. Optional downloaded font wiring and the network broker are not present on this branch.

## Positive findings / next actions

Keep native semantic controls, explicit words in status badges, bounded motion and durable save/conflict feedback. Preserve the independent report/raw detector receipts. Forge should qualify its merged runtime, fonts, manifest theme injection, network semantics and real-chat regenerated Spaces. Do not relax sandbox CSP to obtain detector overlays or a prettier weather screenshot.
