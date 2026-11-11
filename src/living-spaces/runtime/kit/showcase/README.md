# Live premium references

Two code-led extensions of the existing Sky Window and Pair Play reference directions, plus Chromatic Current, a procedural visual piece. These use the updated optional-kit design guidance, with app-owned CSS to demonstrate that the kit is not a mandatory house style. No framework, install, CDN, new generation provider or credentials.

- **Sky Window — dashboard:** a dark viewing room, generated skyline masks, a forecast-derived sky, selectable cities and a shared °C domain for seven daily low–high intervals. Rain bars use a fixed 0–100% denominator. The exact table is keyboard accessible. Public live Open-Meteo forecasts are model output, not observed station weather. Retrieval time is UTC; city time comes from the source. Failure keeps last-good data; initial failure invents none. Synthetic exploration is explicit, not automatic.
- **Pair Play — game:** green tabletop, cream/oxblood printed cards, authored SVG fruit and a complete twelve-card memory loop. Turns, mismatch, matching, win, redeal and recent-round scorecard all work. Finished rounds use create-only writes and a stable retry ID, then exact record readback before Saved. Failed results remain mounted. The local verifier uses an isolated file-backed store through the actual Space bridge, not production records.

## Chromatic Current — visual piece

A full-bleed procedural colour weave, not a dashboard or a game. Original Canvas mathematics draw the artwork; no image, remote font, service, API key or Internet grant is needed. Three colourways, keyboard-operable variation and one-step Undo, explicit motion pause and reduced-motion handling. Keep freezes the exact seed/colourway/phase in one record; Replace kept composition explicitly replaces that slot. Every successful write is read back, and uncertain writes/conflicts require reload before another explicit save. Restore is unavailable until the saved record is authoritative again. The drawing adapts to the viewport; stored parameters, not identical cross-device pixels, are preserved.

Open `?name=chromatic-current` on the runner. Use a **fresh empty output store** for each full verifier run:

```sh
node src/living-spaces/runtime/kit/showcase/harness/verify-chromatic.mjs --port 8783 --out /Volumes/Expansion/Development/Projects/living-spaces-wt/.tmp/chromatic-evidence
```

Extra verifier-only faults: `get` (failed composition read), `missing` (injected not-found), and `save`; `delay=900` exposes in-flight work. These are explicit injected states. A sequential conflict and simultaneous compare-and-swap test use only the separate verifier store. The harness serializes operations per reference; that is not evidence of production-store concurrency. No raster artwork ships in this reference. Source art provenance: original authored `chromatic-current/art.js`, mathematical sine-based warp/weft drawing, no claimed physical simulation or measured data.

## Run and inspect

From the repo root, using already installed Node and Chrome:

```sh
node src/living-spaces/runtime/kit/showcase/harness/server.mjs --out /Volumes/Expansion/Development/Projects/living-spaces-wt/.tmp/showcase-demo-store --port 8783
# In another terminal:
node src/living-spaces/runtime/kit/showcase/harness/verify.mjs --port 8783 --out /Volumes/Expansion/Development/Projects/living-spaces-wt/.tmp/showcase-evidence
```

Open `http://127.0.0.1:8783/?name=sky-window` or `?name=pair-play`. Stop the temporary verifier server when finished. This is a local reference runner, not a new product service. Do not expose it to a network. Its network proxy permits only the public Open-Meteo forecast endpoint; there is no credential/cookie forwarding. The store contains only demo play.

Verifier-only faults: `fault=net`, `off`, `empty`, `invalid` for forecasts; `query` or `save` for the scorecard, and `delay=900` for in-flight loading. These are disclosed injected responses, not alleged live outages. Normal dashboard requests reach the real public API. Normal game writes and subsequent reads reach the isolated file-backed store. The verifier does not synthesize passing responses.

## Provenance and limits

The four WebP assets are unchanged copies from `572e4f2` / the earlier showcase reference tree. The prior provenance record identifies them as Hermes-generated decorative illustrations, not photographs or measured conditions. This phase made no generation calls. Exact original generation prompts/provider metadata are not in the source tree and are not invented here. Asset SHA-256 values accompany the staged evidence manifest. All coordinates are generic public city centres. Sample weather is fixed January 2026 content, explicitly labelled; unused historical fixtures remain synthetic and are not loaded.

System font preferences deliberately fall back offline; no named face is represented as bundled. Two-dimensional card turns replace the earlier 3D/rotated-layer treatment: rotation-associated headless compositor failures produced invalid captures. Only valid final recaptures are evidence. Sunlight glow and rain stripes are semantic weather illustration, not dashboard chrome. The detector flags these plus the inherited room lighting; no detector-clean claim.

Coverage receipts are staged for `docs/design/premium-pass/`. These qualify live references in the real packaged nested sandbox and Space bridge, **not** ordinary-chat generation, actual Desktop host integration, production persistence, browser-native zoom, real touch, assistive-technology speech, or arbitrary weather-image contrast. The two fixed art directions intentionally choose their own light/dark materials, not host theme mirroring. The existing older sources in `skills/build-space/references/showcase/` are historical, unqualified prototypes; this folder is the maintained live reference.
