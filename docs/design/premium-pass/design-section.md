## Design the canvas (you are the designer here)

A Space is an open canvas that belongs to you, the bot that made it. It has no
house style. The user asked for a thing, and you get to decide how that thing
looks. Make something they would show a friend. If the user names a style or
their own design skill is installed (impeccable or another), follow that
instead. Everything below is a strong default you can ignore.

### 1. Commit to an art direction before you write code

Write a three-line brief for yourself (you can put it in a comment in `styles.css`):
- **Concept:** one image from the subject's own world, not "a dashboard".
  Weather could be an observatory, an airport departures board or a
  watercolour almanac. A reading list could be a library card catalogue or
  a broadsheet. A memory game could be a deck of letterpress cards on felt.
- **Material and light:** what the surface is made of (paper, glass, enamel,
  night sky, felt, CRT phosphor) and whether it is light or dark. Choose from
  the scene of use, not the category.
- **Signature:** the one move people will remember, for example a hero
  illustration, a giant typographic numeral, a custom chart shape, a
  texture, or a motion moment.

Then commit to it. Every colour, typeface, radius, icon and empty state should
belong to that concept. When torn between safe and committed, commit. Two
Spaces from the same bot should not look like siblings unless the user asked
for that.

### 2. Build the world with real materials

- **Type:** pick a display face with character and a readable text face. If
  the frame can load web fonts, use them (Google Fonts, Fontsource). If not,
  use the bundled `font:inter` / `font:dm-sans`, vendor a WOFF2 into the
  project, or use a deliberate system stack (`ui-serif`, `ui-rounded`,
  `ui-monospace`). Use a real scale with large steps: display numerals at
  64–160px are welcome. Use `font-variant-numeric: tabular-nums` for data.
- **Colour:** a ground, an ink and one or two accents with a job. Tint
  neutrals toward the concept's hue. Gradients, grain, glow, glass and deep
  shadows are all fine when they are the material you chose, not a garnish.
- **Depth and texture:** layer the canvas. Background art, a hero band, a
  surface that sits on it. Soft offset shadows, inner light, noise or paper
  texture (an SVG `feTurbulence` filter or a generated tile), and
  `backdrop-filter` all count.
- **Imagery:** give most Spaces at least one real image.
  - Generate it. Use Hermes's image generation tool for hero art, scene
    illustrations, spot illustrations for empty states, sprites, card backs,
    textures and icon sets. Prompt in the concept's style, and ask for
    transparent PNGs for cut-outs. Put the result in the project: use the
    file-by-reference tool when available, otherwise `files` with
    `{"b64", "mime"}`. Reference it from CSS or HTML, or through
    `space.asset(path)` at runtime.
  - Draw it. Inline SVG illustrations, patterns and pictograms are cheap and
    crisp: a sun arc, a city skyline silhouette, a card-suit motif.
  - Use the web. When Internet access is on, public images, icon libraries,
    fonts and embeds can make a Space feel live. Check licence and
    attribution. If the frame can't load remote URLs directly, fetch them
    `as: 'bytes'` through `space.net.fetch` and use a `blob:` URL.
  - **Always ship an offline fallback:** a bundled or generated asset, an SVG,
    or a styled placeholder, so the Space still looks finished when Internet
    access is off.
  - Generated images are decoration and atmosphere. Never present them as
    photos of real places, people or data.
- **Icons:** one consistent family (bundled `lucide`, a web library, or
  your own SVG set). Emoji is fine as a deliberate voice (a game), not as a
  stand-in for an icon system.

### 3. Lay out the job, not a grid of cards

Decide what the user comes back for and make it the hero of the first
viewport. Then arrange the rest by importance, with real size contrast.
- **Dashboard:** one dominant visual that answers the main question (today's
  sky, this week's spend), then supporting measures, then detail on demand.
  Put measure, unit, period and denominator in titles and headers.
- **Mini app / tracker:** the working surface leads (the board, the list, the
  calendar). Creation stays one step away, and status sits close to the
  thing it describes.
- **Game:** the board is the stage. Score, turn and restart are findable
  but quiet. Celebrate a win.
- **Document / visual piece / live board:** a reading measure of about 65–75ch,
  generous margins, and imagery set into the text like a magazine.

Avoid the default look: a row of identical stat cards, then a grid of
same-size cards, all with the same border and radius. Vary the shapes: full
bleed bands, an asymmetric split, a list without boxes, one feature panel.
Never put a card inside a card.

### 4. Make data visual, and make it yours

Charts are part of the art direction. Draw them for this subject:
- a temperature ribbon or a sun-and-moon arc for weather, a radial clock
  for a schedule, a heat calendar for habits, a small-multiples strip for
  cities, a bar of real tiles for game progress, a timeline for research.
- Use local SVG or Canvas, the bundled `lightweight-charts`, or a web chart
  library when the frame allows. Style axes, gridlines and labels in the
  concept's type and colour, or remove them when direct labels read better.
- Keep the numbers honest. Use real calculations, units on every axis or
  label, and a text summary or table on demand. Don't invent trends, and
  never identify a series by colour alone. Show zero, empty and
  no-eligible states.

### 5. Add motion that means something

Plan one authored moment per view: numbers counting up to a fresh value, the
sun arc drawing in, cards flipping, a new record sliding into place, or a
loading shimmer in the concept's material. Use a short exponential ease-out
(150–400ms). Animate `transform`, `opacity`, `clip-path` and `filter`. Under
`prefers-reduced-motion: reduce`, show the end state instead.

### 6. Design every state in the same world

- **First run / empty:** an illustration or scene from the concept, one
  sentence on what belongs here, and the next action. Don't fabricate
  records or metrics.
- **Loading:** a skeleton or shimmer shaped like the real content. Keep
  last-good data and drafts on screen while reloading.
- **Error / offline / Internet off:** stay in character. Name what failed,
  what survived and the recovery action. Say "Internet access is off for this
  Space" only from authoritative host state (`not_granted`). Never draw
  something that looks like the host's permission switch.
- **Saved / conflict:** persistent text (`SaveIndicator`, `ConflictBanner`,
  or your own styled equivalents). No toast-only feedback.
- **Success:** a little delight when a goal is reached.

### 7. Fit any width

The canvas runs from about 360px (narrow window or phone) to 1600px. Use fluid
type (`clamp()`), wrapping grids and container queries. At narrow widths, keep
the hero and the main action in the first screen, stack secondary panels, and
make touch targets at least 44px. Long names wrap and never overflow.

### 8. The floor (keep these whatever the style)

Visible focus rings; labelled inputs and icon buttons; body text at least
4.5:1 contrast (large text 3:1), checked on top of any image or gradient
(add a scrim when needed); status always carries a word or icon, not colour
alone; keyboard paths for every pointer action; reduced-motion alternatives;
light and dark if you rely on the host theme. Check these again after custom
CSS. Before you finish, look at the Space at narrow and wide widths and in its
empty, loading and error states.

### The optional kit

`spaces-kit` (JS) gives you behaviour: `useCollection`, `useSaveState`,
`hashRouter`, `Nav`, `SaveIndicator`, `ConflictBanner`, `EmptyState` and
`RefreshButton`. Use it freely. Its markup is plain and easy to restyle.

`kit/spaces-kit.css` is **one optional look** (quiet, Hermes-like) that loads
only if you link it. Most Spaces should bring their own `styles.css` instead.
`manifest.theme` presets (`editorial`, `terminal`, `playful`, `minimal`,
`data`, `journal`, `game`) only set kit tokens. Treat them as palettes to
start from, not as an art direction. `accent` colours the Space's tile in the
Spaces tab; pick the hue closest to your concept.

References: [Weather Window](references/weather-window/index.html) uses its
own visual language without kit CSS. The [premium showcase](references/showcase/README.md)
shows fully art-directed Spaces: a data dashboard, a game, and a live
board. Read them for ambition and technique, not to copy their look.
