## Design the canvas

A Space is an open canvas that belongs to you, the bot that made it. It has no
house style. The user asked for a thing, and you get to decide how that thing
looks. If the user names a style or
their own design skill is installed (impeccable or another), follow that
instead. The visual defaults below are suggestions, not templates or limits.
Accessibility, truthful data, permissions and durable-save rules still apply.

Choose the surface's mode first: **Operate** for tools and games, **Read** for
documents, **Experience** for a visual piece. A working tool is not a marketing
page: let the work lead, not a decorative welcome screen.

### Build the world with real materials

- **Type:** pick a readable text face.
  Bundle an appropriately licensed WOFF2 and declare `@font-face`; the optional
  `font:inter` / `font:dm-sans` libraries supply local text faces. A font name in
  CSS does not download it. Deliberate system stacks are valid offline fallbacks.
  Use expressive scale when the content earns it, not uniformly tiny type or
  a giant numeral on every screen. Use `clamp()` and tabular numerals for data.
- **Imagery:** A reading
  tool can be typographic; imagery is not a mandatory extra request or cost.
  - Generate it. When an approved image tool and cost envelope are available,
    use them for hero art, scene
    illustrations, spot illustrations for empty states, sprites, card backs,
    textures and icon sets. Do not switch providers or use a paid/API
    fallback to bypass an unavailable tool. Draw SVG instead. Put the result in
    the project: this revision supports `files` with `{"b64", "mime"}`.
    Use `{"from_path":"..."}` or `{"from_url":"..."}` when the actual tool
    schema exposes these file-reference forms.
    Reference the asset from CSS or HTML, or through
    `space.asset(path)` at runtime.
  - Draw it. Inline SVG illustrations, patterns and pictograms are cheap and
    crisp: a sun arc, a city skyline silhouette, a card-suit motif.
  - Use the web. When Internet access is on, fetch licensed public imagery
    through the runtime's supported path. **The Runtime section is authoritative:**
    at this revision direct remote images, web fonts, CDN imports and embeds are
    blocked. Use `space.net.fetch(url, {as:'bytes'})` for images, check HTTP
    status, and use the returned `b64` and `mime` as a data URL (or a decoded
    Blob). Release replaced blob URLs. Bundle fonts and libraries locally.
    Use load/error fallbacks. Never infer runtime capability from an amendment or plan.
  - **Always ship an offline fallback:** a bundled or generated asset, an SVG,
    or a styled placeholder, so the Space still looks finished when Internet
    access is off.
  - Keep source, licence/attribution and generated-art provenance with the
    asset. Size it to its display role; compress large images before bundling.
    Generated art is not a documentary photo or a data visualization. Never
    present an invented skyline, person or condition as observed evidence.

### Lay out the job

- **Dashboard:** one dominant visual that answers the main question (today's
  sky, this week's spend), then supporting measures, then detail on demand.
  Put measure, unit, period and denominator in titles and headers.
- **Mini app / tracker:** the working surface leads (the board, the list, the
  calendar). Creation stays one step away, and status sits close to the
  thing it describes. Keep search, result count and results adjacent; a secondary
  creation form belongs behind a labelled disclosure, not between query and results.
  Preserve its draft and keyboard focus when opening or closing it.
- **Game:** Score, turn and restart are findable.
- **Document:** a reading measure of about 65–75ch, generous margins, useful
  headings.
- **Visual piece / live board:** Keep spatial meaning on narrow screens.

### Make data visual

- Use local SVG or Canvas, or a bundled chart library appropriate to the data:
  `plot` (Observable Plot) for bar, distribution, heatmap and general time-series
  charts, `lightweight-charts` only for financial price series. Don't select both
  for the same job. Copy a recipe from [charts/recipes.mjs](charts/recipes.mjs):
  each derives its domain from the data, names the unit on the axis or legend,
  keeps negative values and gaps visible, returns a text summary, and shows an
  empty state when nothing is eligible.
- Keep the numbers honest. Use real calculations, units on every axis or
  label, and a text summary or table on demand. Don't invent trends, and
  never identify a series by colour alone. Compute the domain from all eligible
  values; preserve negative values and meaningful baselines. A sun arc represents
  time, not temperature. A pretty shape is not permission to change the measure.
  Show zero, empty and no-eligible states, not invented fallback values.
  Label elapsed wall-clock duration separately from active time: a resumed game
  measured from start to finish includes time away. Format long durations in
  hours/minutes; never relabel existing timestamps as active play.

### Add motion that means something

Prefer `transform` and `opacity`; profile
`clip-path`, filters and large blur layers before using them. Keep essential
content visible if animation fails. Under `prefers-reduced-motion: reduce`, show
the end state instead, including drawn strokes and loading indicators. Motion
should not hide a result or delay a control. Offer pause for ongoing ambient art.

### Design every state

- **First run / empty:** one
  sentence on what belongs here, and the next action. Don't fabricate
  records or metrics.
- **Loading:** Keep
  last-good data and drafts on screen while reloading.
- **Error / offline / Internet off:** Name what failed,
  what survived and the recovery action. Say "Internet access is off for this
  Space" only from authoritative host state (`not_granted`). Never draw
  something that looks like the host's permission switch.
- **Saved / conflict:** persistent text (`SaveIndicator`, `ConflictBanner`,
  or your own styled equivalents). No toast-only feedback.

### Fit any width

The canvas can be narrower than the app window because the host's navigation
and frame take space. Use fluid type (`clamp()`), wrapping grids and container
queries; measure the actual canvas viewport, not just the outer window. At
narrow widths, lead with the current reading, result list or playable board;
compress decorative mastheads and slogans before shrinking essential text.
Keep primary controls visible and secondary creation one step away. Make touch
targets at least 44px. Long names wrap and never overflow. Record both app and
canvas dimensions when checking wide, 390px and 320px app windows; a no-overflow
measurement alone does not prove the main task is visible or reachable.

### The floor (keep these whatever the style)

Visible focus rings; labelled inputs and icon buttons; body text at least
4.5:1 contrast (large text 3:1), checked on top of any image or gradient
(add a scrim when needed); status always carries a word or icon, not colour
alone; keyboard paths for every pointer action; reduced-motion alternatives;
light and dark if you rely on the host theme. Check these again after custom
CSS. Before you finish, inspect the running Space at wide, 390px and 320px widths,
200% zoom, long text, keyboard focus and reduced motion; exercise its empty,
loading, error, success and confirmed-save states. Say which checks you actually
ran. A static frame is not evidence of a working save, refresh or game loop.

### The optional kit

`spaces-kit` (JS) gives you behaviour: `useCollection`, `useSaveState`,
`hashRouter`, `Nav`, `SaveIndicator`, `ConflictBanner`, `EmptyState` and
`RefreshButton`. Use it freely. Its markup is plain and easy to restyle.

`kit/spaces-kit.css` is **opt-in**, linked before the app's own `styles.css`.
Use no kit CSS, its quiet base, or one of six optional canvas materials:
`observatory` (night and glass), `letterpress` (paper and ink), `blueprint`
(drafting grid), `felt` (tabletop), `daybreak` (warm light) and `enamel` (bold
colour blocks). Set `data-theme="letterpress"` on **body**. These six are CSS
attributes, **not accepted manifest preset names**. They choose their own light
or dark scheme. They contain no downloaded fonts, generated images or app logic.
Override tokens and composition freely.

Useful primitives: `space-hero`, `space-display`, `space-asymmetric`,
`space-ledger`, `space-rail`, `space-panel` and `space-state`. Motion is opt-in:
`space-reveal`, `space-draw`, `space-skeleton--shimmer`; `data-motion="none"`
disables these helpers, and OS reduced motion wins. Keep loading text alongside
decorative skeletons. Read the companion source
[canvas guide](../../../runtime/kit/README.md) and
[specimen](../../../runtime/kit/canvas-gallery.html) for composition, asset and state
recipes. They demonstrate three different layouts with public synthetic content,
not a mandated starting screen. These docs are source references, not files
automatically copied into each created Space.

`manifest.theme` presets (`editorial`, `terminal`, `playful`, `minimal`,
`data`, `journal`, `game`) only set kit tokens. `accent` colours the Space's tile in the
Spaces tab.

References: [Weather Window](weather-window/index.html) uses its
own visual language without kit CSS. [Showcase sources](../../../runtime/kit/showcase/README.md)
are further technique references, not proof of chat generation or qualification;
consult their verification receipts before claiming live behaviour.
