# A toolbox, not a house style

A Space is the bot's open canvas. Use the behaviour module with your own CSS,
choose one of these materials, override everything, or use none of the kit.
The user's brief and their design skills take precedence. Accessibility,
truthful data and confirmed saves are not optional.

## Choose the structure before the skin

| Task | Composition to try | Signature that earns its place |
| --- | --- | --- |
| Understand conditions | A scene beside the primary measure, then a shared-scale range plot and a narrow ledger | Authored or generated place illustration; daylight from real time, not a random gradient |
| Read and annotate | A typographic opening, unboxed list, adjacent reading detail | Distinct display lettering, fine rules, a sourced illustration |
| Play or manipulate | The board/workbench as the stage; rules and controls nearby | Tactile pieces, a legible selection or turn, one satisfying state change |
| Inspect dense data | One dominant table or plot with comparison controls | Direct labels, meaningful domain, unit and denominator in the title |

These are composition ideas, not app templates. Don't give every job a hero
numeral and a grid of equally weighted cards. Likewise, don't add a decorative
hero that pushes a working tool below the fold. The board is allowed to be a grid
because position is its content; the rest of the page need not be.

Open `canvas-gallery.html` beside this file to see **three different layouts**
across six materials. The weather ranges use one calculated domain including a
negative low; the reading desk expands abstracts; the tile workbench toggles and
clears a pattern. Its data is synthetic, SVG is authored, states are simulations,
and selection is local only. It is not evidence of a live API, saved records,
chat generation or the complete showcase apps.

## Load only the layers you want

```html
<!-- Omit this link entirely when bringing your own visual system. -->
<link rel="stylesheet" href="kit/spaces-kit.css">
<link rel="stylesheet" href="styles.css">
<body data-theme="letterpress">
  <main class="space-app"><!-- your composition, not a mandatory shell --></main>
</body>
```

`spaces-kit.mjs` can be used without the CSS. Its `useCollection`, `useSaveState`,
`SaveIndicator`, `ConflictBanner`, routing and refresh helpers keep their existing
API. The app still owns data, rules, recovery, conflict choices and accessible
markup. None of the new visual helpers performs network calls or saves.

The six **body attributes** below are not manifest presets. No schema expansion
is required. The seven existing manifest presets remain compatible, follow host
light/dark and are starting palettes, not seven different application designs.

| `data-theme` | Material | Type intent / offline fallback | Scheme |
| --- | --- | --- | --- |
| `observatory` | Deep sky, a restrained star field, translucent depth | Character serif / Georgia | Dark |
| `letterpress` | Warm grained paper, oxblood ink, soft paper lift | Editorial serif / Didot, Times, Georgia | Light |
| `blueprint` | Drafting grid, fine lines, square geometry | Measurement mono / system mono | Dark |
| `felt` | Tabletop green, cream pieces, red actions | Slab display / Rockwell, Georgia | Dark |
| `daybreak` | Warm light, soft surfaces, broad corners | Expressive sans / system sans | Light |
| `enamel` | Colour blocks, black outlines, deliberate hard shadow | Heavy display / installed heavy sans | Light |

Named display faces in the CSS are **font preferences, not shipped assets or
network requests**. Bundle an appropriately licensed display face when its shape
matters. The specimens intentionally exercise system fallbacks. For local text
fonts, request `font:dm-sans` or `font:inter`, then declare the bundled faces:

```css
@font-face {
  font-family: 'DM Sans'; font-style: normal; font-weight: 400; font-display: swap;
  src: url('vendor/fonts/dm-sans-latin-400-normal.woff2') format('woff2');
}
@font-face {
  font-family: 'DM Sans'; font-style: normal; font-weight: 700; font-display: swap;
  src: url('vendor/fonts/dm-sans-latin-700-normal.woff2') format('woff2');
}
body { --space-font: 'DM Sans', system-ui, sans-serif; }
```

Paths above assume an app-level `styles.css` and the optional font library.
Do not point at a file that was never included. For other alphabets, bundle the
needed glyph coverage and test long labels. This kit includes no downloaded
custom display fonts or generated hero art.

## Compose and override

- `space-hero`: optional image/scene band; it bleeds by `--space-pad`. Put it
  directly in the page, not inside a padded panel. Set `margin:0` when contained.
- `space-display`, `--sm`, `--xl`: fluid display type. Use the large variants
  only for short content; they aren't a body-text scale.
- `space-asymmetric`: a 1.7:1 split, stacked below 680px. Keep the primary task
  first in DOM order. Adapt the breakpoint to the content, not the device name.
- `space-ledger`: ruled label/value rows; use units and tabular values.
- `space-rail`: horizontal secondary content with scroll snap; retain keyboard
  access and a visible cue that more content exists.
- `space-panel`: optional material/depth, **not** the default wrapper for every
  region. `space-state`: illustration, heading, explanation and recovery action.
- `space-sparkline`: stroke styling only, not data or a charting engine. Supply
  real paths, a useful accessible summary and domain; never use it as fake data.

Override `--space-bg`, `--space-text`, `--space-muted`, `--space-font`,
`--space-heading-font`, `--space-display-font`, `--space-ink-2`, radius/density,
`--space-panel-bg`, `--space-panel-border`, `--space-panel-shadow`,
`--space-panel-blur`, `--space-hero-bg`, `--space-hero-image`,
`--space-background-image` and `--space-background-size` in app CSS after the
kit. Tile `accent` remains an identity cue, not a limit on the interior palette.
Check focus, muted text, semantic status colours, and any text over images after
your overrides. A scrim is a starting technique, not a contrast certificate.

```css
/* A Space's own concept, not a stock theme in a different accent colour. */
body {
  --space-heading-font: 'My licensed display face', Georgia, serif;
  --space-panel-shadow: 0 12px 30px #241c1220;
  --space-hero-image: url('images/hero.webp');
}
```

## Assets and available capabilities

The runtime contract in `build-space/SKILL.md` is authoritative. At this source
revision:

- Local binary images/fonts and authored SVG work. Static HTML/CSS paths are
  resolved by the host; runtime-built paths use `space.asset('images/hero.webp')`.
- Generated heroes, illustrations, texture tiles, sprites and icons can be
  bundled when the agent has an **already-approved** generation tool/cost
  envelope. Nothing here enables a provider or spends quota. If unavailable,
  use authored SVG; don't open an account or switch to a paid API.
- With **Internet access on**, `space.net.fetch` can obtain public HTTPS images
  as bytes. Direct remote image URLs, web fonts, CDN imports and embeds remain
  blocked in this revision. Planned open-network and file-by-reference support
  are not qualified capabilities here. Inspect the actual tool schema before
  using a file-reference descriptor; the existing binary fallback is `{b64,mime}`.
- No storage API, parent-frame access or arbitrary bot tool call is added by this
  kit. Saved content belongs in records; a selected tile can be ordinary UI state.

An image byte reply has top-level `b64` and `mime` (not `response.bytes`). Keep a
bundled fallback visible until a valid image loads. An example **for existing
Space code**, not for fetching private data:

```js
async function loadPublicImage(image, publicHttpsUrl) {
  // image.src should already point to a bundled image via space.asset(...).
  const fallback = image.src;
  try {
    const r = await space.net.fetch(publicHttpsUrl, {as: 'bytes'});
    if (r.status < 200 || r.status >= 300) throw new Error(`Image HTTP ${r.status}`);
    const mime = r.mime?.split(';')[0];
    if (!['image/png', 'image/jpeg', 'image/webp', 'image/gif'].includes(mime) || !r.b64)
      throw new Error('Unsupported image reply');
    const candidate = new Image();
    candidate.src = `data:${mime};base64,${r.b64}`;
    await candidate.decode(); // Keep the fallback visible until decoding succeeds.
    image.src = candidate.src;
    return {state: 'loaded'};
  } catch (error) {
    image.src = fallback;
    return {state: error.code === 'not_granted' ? 'internet-off' : 'failed'};
  }
}
```

Use a decorative image's empty alt or a content image's meaningful alt. Retain
source URL, licence/credit and generated-art provenance. An invented scene must
not imply an observed place, weather condition or measured result. Give images
intrinsic dimensions; compress them to the required display size.

## Motion, states and narrow layouts

Motion is optional. `space-reveal` is a short entrance, `space-draw` is a stroke
reveal (`pathLength="1" style="--len:1"`), and `space-skeleton--shimmer` opts a
plain skeleton into shimmer. `data-motion="none"` on the body disables the kit
helpers. OS reduced motion removes reveals/shimmer and shows complete strokes;
reduced transparency replaces glass with a solid surface. App-authored motion
must respect the same preferences. Ongoing ambient motion needs a pause route.

Place loading/error feedback **next to the affected work**, not below a long
page. Keep last-good content, editors and drafts mounted. A first-run empty state
has no fake numbers; a search miss offers clear/reset instead of creating data.
Name failure, what survived and recovery. Use persistent saved/conflict feedback
from confirmed writes. No host permission switch imitation or guessed Internet
state. Skeletons are decorative and need visible loading text.

Test desktop, 390px, 320px, 200% zoom, long text, keyboard, reduced motion and
empty/loading/error/success states. Respect at least 44px touch targets. A spatial
board may remain a grid on mobile; supporting regions should stack and wrap.

`verify-canvas.mjs` runs the local specimen checks with Chrome and Node, without
installing anything or contacting external services. Supply a writable output
directory; all profiles, screenshots and JSON go there:

```sh
node src/living-spaces/runtime/kit/verify-canvas.mjs --out /Volumes/Expansion/Development/Projects/living-spaces-wt/.tmp/premium-kit
```

The verification report distinguishes geometry, keyboard and state exercises
from rendered screenshots. It is not Desktop acceptance or a screen-reader audit.
