# Dependency shelf for agent-built Spaces

Miro → Forge · release-1 recommendation · 10 November 2026

## Floor, not ceiling

Spaces are an environment for whatever the user wants. The kit, presets and shelf are optional. A building agent can use its installed design skills, generate assets and vendor other libraries. The shelf earns its place by making common work fast, pinned and usable offline. Never copy the entire shelf into every Space.

**Integration update:** Forge's newer runtime keeps direct frame network blocked and exposes mediated `space.net.fetch`; this is not CDN/import/embed access. The web/on-demand rows below are sourcing recommendations for agent-vendored assets or a future qualified runtime, not claims that remote modules, web fonts or iframes load directly in R1. Follow the current build skill's single authoritative network rule.

**Decision:** keep the existing Preact/hooks and financial lightweight-charts. Add typography, icons, a general SVG chart library and safe markdown. Small motion is worthwhile if its isolated build qualifies. Do not rush multiple chart or game engines into the candidate. Network-open is a product decision with a separate isolation feasibility gate; this proposal does not claim the runtime gate has passed.

## Bundle for the submission

Sizes are approximate **uncompressed payloads** unless marked measured. Raw bytes count against project limits; gzip is a transport comparison, not storage. Package/version/license facts were read from official npm metadata and downloaded package manifests; Forge owns final pinning, integrity and license notices.

| Item / proposed key | Version; license | Approximate size | Design reason / qualification |
|---|---|---|---|
| `htm` | 3.1.1; Apache-2.0 | 1–4 KB | Approved authoring convenience. The kit's `html` export already provides a tagged-template authoring path; document both without implying JSX compilation. |
| `lucide` | Use Forge's already selected lucide-static **1.71.0**; ISC | Hundreds of KB for the complete node catalog; measure generated wrapper | Subject-specific SVG icons without emoji or network. Prefer a tiny safe `icon()` renderer; decorative by default, optional accessible label. The CSS kit also includes a small authored icon set. Do not ship all SVG files plus the same JSON catalog. |
| `spaces-fonts` | Fontsource 5.3.0; OFL-1.1 | Roughly 150–250 KB total latin woff2, depending on selected weights | Keep Forge's initial Inter + DM Sans. **Add Newsreader (roman variable), Bricolage Grotesque, JetBrains Mono**: reading, expressive sans and code/measurement are genuinely different jobs. System UI stays the default to match Desktop. Ship font CSS, licenses and fallbacks. Fonts are opt-in; presets work without them. |
| `plot` | @observablehq/plot 0.6.19; ISC (included D3 dependencies retain their notices) | **387,154 bytes raw / 131,088 gzip, measured** from scratch bundled ESM | General bars, lines, dots, distributions, heatmaps and facets. SVG inherits theme color and supports accessible captions and labels. Include D3 dependencies in one offline ESM artifact, not unresolved bare imports. Lightweight-charts remains the finance specialist. |
| `markdown` | marked 18.2.0, MIT; DOMPurify 3.4.17, MPL-2.0 OR Apache-2.0 | About 49 KB + 83 KB raw | Documents and live content need readable rich text. Parse **and sanitize** external or user HTML; never treat markdown parsing as sanitization. Keep both exports available and show the safe usage in the shelf docs. |
| `motion` (conditional) | motion 14.12.0 **motion/mini**; MIT | **8,568 bytes raw / 3,312 gzip, measured** from scratch bundled ESM | Small WAAPI-based `animate` for interruptible feedback, game moves and transitions. Mini is not the full springs/layout API: do not advertise those exports. Bundle only this isolated build if runtime import checks pass; otherwise web-on-demand after submission. Respect reduced motion in JS as well as CSS. |

The measured artifacts live in Miro's scratch shelf probe, not production dependencies. Forge should reproduce builds, hash outputs, preserve upstream licenses and run offline imports in the opaque-origin sandbox. Do not reuse unaudited scratch node_modules as the shipping shelf.

## Web / agent-vendored when needed, not default shelf

| Item | Version checked; license | Approximate size / reason |
|---|---|---|
| D3 standalone | 7.9.2; ISC | About 274 KB raw. Excellent for bespoke scales, graphs and layouts, but Plot already carries its own subset. Add only when the Space needs direct D3. |
| Rough.js | 4.6.6; MIT | About 27 KB raw. Useful when hand-drawn marks are the actual visual direction, not texture applied to every planner. |
| Three.js | 0.187.0; MIT | About 2.1 MB across module + core. Use for actual 3D; no reason for every Space to carry it. |
| ECharts / Chart.js | 6.1.0 Apache-2.0 / 4.6.1 MIT | Roughly 1.1 MB / 200 KB minified. Legitimate alternatives for specific chart interactions. Canvas needs explicit theme updates and equivalent textual data. |
| Phaser / PixiJS / other game engines | Pin and verify when selected; generally MIT | Purpose-specific. Small turn-based games need DOM/Canvas, not an engine. Large games may legitimately need one. |
| Maps, public APIs, media embeds, images, extra fonts | Provider-specific terms | Inherently online; do not add these to the offline shelf. Design loading, denied/offline, failed-load and retry states. Verify CORS/embedding permission from an opaque origin. No credentials in Space files. |

Remote dependencies should be version-pinned HTTPS, not floating `latest`. Runtime network access, redirects and private-network isolation remain Forge's boundary. A graceful failed-load message is not evidence that an embed or endpoint works.

## Runtime integration seams for Forge

1. Copy shelf files only when requested, with exact supported library keys/import paths in the build skill. Fonts need binary MIME/base64 support, CSS `url()` rewriting and `font-src` validation in the real sandbox.
2. Link `kit/fonts.css` only when the font shelf is present. Preset font stacks fall back to Georgia/system/monospace and must not fail while fonts load.
3. Interior customization is ordinary app CSS: `data-theme` + `--space-*` overrides, including arbitrary colors, type, geometry, density, background and motion. The host manifest accent is **not** a limit on the interior palette. If manifest theme metadata is added, keep it optional and document its real loader behavior before agents rely on it.
4. Expose an authoritative network mode to the guest (for example `space.meta.network`) only if implemented. Until then a failed request cannot distinguish Internet Off from CORS, source outage or embedding refusal. Keep fallback copy truthful.
5. Internet On/Off remains host-owned. Restoring access follows the host approval contract. Changing CSS must never impersonate a permission control.

## Later

Extended font subsets, audio/game helpers and a package-install pipeline can be added without changing the kit. Non-Latin text uses the system fallback today; do not claim the bundled Latin shelf covers every script.
