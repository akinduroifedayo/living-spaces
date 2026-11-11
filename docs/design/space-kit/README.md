# Spaces interior kit · handoff

Commission t_7d0302a8. Branch `miro/space-design-kit`, based on Forge `44211c8`. This is a composable **default**, not a restriction on what agents build. The no-kit weather dashboard deliberately departs from it.

## What ships

- Dependency-free `src/living-spaces/runtime/kit/spaces-kit.css`: Nous-compatible light/dark tokens; app shell/navigation; accent tiles; cards/stats; lists/tables; forms/buttons; semantic badges; loading/empty/error/conflict/offline surfaces; chart frame and game-board geometry; focus, forced colors and reduced motion.
- Seven optional identities: `editorial`, `terminal`, `playful`, `minimal`, `data`, `journal`, `game`. Presets change palette, type, geometry/density and, for Game, a background pattern. They are starting points, not seven copies of a compulsory screen.
- Optional design guidance in build-space/SKILL.md: installed design skill precedence, other authorized tools/assets, purpose-led composition, accessible honest states and charts. Runtime/project files remains Forge's authoritative capability rule.
- Research Desk (editorial) and Daily Practice (journal) use the kit; Weather Window uses its own CSS and actual local SVG scale calculations. No new dependencies are required by these examples.
- Dependency proposal: `../DEPENDENCY-SHELF.md`, including bundle/on-demand choices, licenses, approximate/measured sizes and integration seams.

## Compose / customize

Load kit CSS before app CSS when desired. Use semantic HTML. On the current loader, put `data-theme="journal"` on **body**; html works only where root attributes are preserved. No preset is required. Set any custom palette rather than limiting it to the host tile accent names.

```css
/* App-owned CSS after the kit: examples, not a whitelist. */
body {
  --space-accent: #b34568;
  --space-heading-font: Georgia, serif;
  --space-radius: 4px;
  --space-radius-lg: 8px;
  --space-density: .9;
  --space-shadow: 0 6px 24px #00000012;
  --space-background-image: none;
  --space-motion: 1;
}
```

Color roles: bg/card/surface, text/muted/link, action/on-action, focus, line/control-line, selected, alert/success/warning plus their backgrounds. Geometry: --space-1…6, radius-sm/radius/radius-lg, density, text-xs/sm/base/lg/title/stat, font/heading-font/mono, shadow, background-image/size and motion. Controls retain a minimum height; compact density does not shrink touch targets. Status must include words; an icon or color is supplemental.

The fonts named in preset fallback stacks are optional. Current captures use available local fallbacks. This branch does not claim shelf font copying, binary import or manifest-theme wiring. Custom CSS can defeat contrast/focus/motion floors: recheck overrides rather than promising CSS makes them unbreakable.

## Run the synthetic preview

```sh
PORT=8769 node docs/design/space-kit/render-server.mjs
# /?example=research-desk | habit-planner | weather-window
# /src/living-spaces/skills/build-space/references/kit-gallery.html
# /weather-off.html — visibly simulated host Off metadata, not real permissions
SPACE_KIT_BROWSER_TMP=/Volumes/Expansion/Development/Build/miro-space-kit-check \
  node docs/design/space-kit/check-browser.mjs
```

The server is local-only and must be stopped after use. No Forge Desktop/home is used. It mounts actual sandbox/reference code with the repo's in-memory synthetic backend. Static screen files are **not** production/chat/persistence evidence.

## Read the evidence

- `passes/critique.md`: synthesis of two independent assessments; baseline **26/40**, not a post-fix rescore.
- `passes/audit.md`: measured audit **17/20**, resolved defects and explicit coverage limits.
- `passes/polish.md`: changes and rechecks.
- `passes/assessment-{a,b…}`: retained original independent output and raw detector/browser evidence. These precede final polish; do not confuse them with final frames.
- `passes/contrast.json`: **272** computed-color checks, default plus seven presets in both modes; no failures.
- `passes/browser-checks.json`: **27** measured page states, trusted-input replays and focused regressions; no measured failures. Pixel review remains separate.

### Curated final visual receipts

All data below is synthetic. `screens/` holds the original PNGs.

| Receipt | Purpose |
|---|---|
| research-desk-light.png / research-desk-dark.png | Reading-led entry, compact counts, freshness disclosure |
| research-library-dark.png | Real list/detail/editor layout; light library capture is diagnostic only |
| habit-planner-light.png / habit-planner-dark.png | Warm, focused check-in app, bounded 720px measure |
| gallery-light.png / gallery-dark.png | Entire component vocabulary and static states |
| weather-off-light.png / weather-off-dark.png | Explicit **simulated** Internet Off state |
| weather-sample-light.png / weather-sample-dark.png | User-chosen, labelled synthetic chart; no silent fake-live fallback |
| weather-sandbox-sample.png | Diagnostic capture only; actual sandbox sample checked through DOM/state, not accepted pixels |
| weather-mobile-dark.png / research-desk-mobile-dark.png | Representative narrow chart/reading hierarchy |
| preset-*.png | Seven optional palette/type/geometry starts; not seven different app flows |

**Diagnostic only:** habit-planner-mobile-dark.png (and its duplicate `-final`), research-library-light.png and weather-sandbox-sample.png capture blank nested surfaces in the final run despite valid inner DOM measurements. Cause unproven; not visual acceptance. Earlier runs produced visible Library and sandbox weather frames, but the final files do not establish that. Original B's narrow habit render is visible but predates final target sizing. Do not ship blank images as success receipts. No browser-level zoom, VoiceOver, physical-touch or cross-engine acceptance is claimed.

## Forge merge seam / remaining integration gates

Keep the design section headed `Make the inside worth using (optional design defaults)` when reconciling your SKILL.md runtime rewrite. Existing runtime CSS names remain intact. No runtime JS, bridge, Python or test changes were authored. The source branch does not contain your newer 7febcd8 shelf or subsequent network lanes; re-run the current integrated gate after merging.

Default-open direct network is **not qualified**. Hosted Weather Window currently disables live loading and offers its local sample. A standalone browser demonstration can call Open-Meteo, but that does not prove the Space network boundary. Integrate the exact qualified host API rather than guessing a bridge signature or relaxing CSP. Host On/Off copy follows the actual landed semantics.

Forge still owns actual Desktop theme switching, optional-font/theme-loader qualification and demo regeneration through real chat. Ife retains design acceptance. No PR, merge, deployment or external publication was performed by Miro.
