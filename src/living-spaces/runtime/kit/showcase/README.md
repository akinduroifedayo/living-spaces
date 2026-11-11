# Live premium references

Two code-led extensions of the existing Sky Window and Pair Play reference directions. These use the updated optional-kit design guidance and its material vocabulary, with app-owned CSS to demonstrate that the kit is not a mandatory house style. No framework, install, CDN, new generation provider or credentials.

- **Sky Window — dashboard:** a dark viewing room, generated skyline masks, a forecast-derived sky, selectable cities and a shared °C domain for seven daily low–high intervals. Rain bars use a fixed 0–100% denominator. The exact table is keyboard accessible. Public live Open-Meteo forecasts are model output, not observed station weather. Retrieval time is UTC; city time comes from the source. Failure keeps last-good data; initial failure invents none. Synthetic exploration is explicit, not automatic.
- **Pair Play — game:** green tabletop, cream/oxblood printed cards, authored SVG fruit and a complete twelve-card memory loop. Turns, mismatch, matching, win, redeal and recent-round scorecard all work. Finished rounds use create-only writes and a stable retry ID, then exact record readback before Saved. Failed results remain mounted. The local verifier uses an isolated file-backed store through the actual Space bridge, not production records.

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
