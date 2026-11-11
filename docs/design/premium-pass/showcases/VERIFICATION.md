# Live showcase verification

## Scope and result

Two functioning local references, not off-state mockups: Sky Window has actual public Open-Meteo responses through the actual packaged nested sandbox and Space bridge; Pair Play has a complete input-driven round, a real create-only write, exact readback, and persistence across a complete frame reload in the isolated verifier store. Normal live requests are not fixture responses. Failure and empty branches are explicitly injected by the verifier. The reference app code does not contain verifier controls.

## Direction contract (existing-world extension)

**THESIS:** forecasts are places to compare, not a grid of unrelated KPI tiles; the game is the board itself, not a dashboard wearing game colours. **OWN-WORLD:** Sky Window inherits midnight-blue room, luminous illustrated skylines, pale serif readings and blue rain marks; Pair Play inherits saturated green, cream stock, oxblood print and slab lettering. **STORY:** select a city to inspect its measured seven-day ranges; turn cards, remember a miss, find six pairs, confirm a saved result, deal again. **FIRST VIEWPORT:** dashboard uses a dominant city and two secondary panes above a single shared-scale plot; game has a twelve-card stage beside a scorecard. Mobile stacks supporting content without changing the board’s spatial identity. **FORM:** extension of existing source directions, not a new visual-world roll; no seed or comp approval is claimed. **FINISH:** unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance.

## Product context / documentation boundary

Audience: public-content Space builders and reviewers. Job: learn techniques from functioning references rather than copy a house style. Success: inspect live forecast semantics and finish/recover/reload a round. No personal data, production writes, external publishing, host changes, or paid assets. The repository lacks PRODUCT.md/DESIGN.md. This bounded commission prohibits root-file edits; this source-context/design receipt is staged for Forge under the existing docs acceptance home, not a parallel product mandate. Existing visual worlds and fallback type families are preserved; no full design-system claim.

## Changes that matter

- Strict forecast validation, honest empty/initial error, explicit synthetic sample, last-good retention across repeated failures, focus-preserving busy controls, motion pause.
- Shared-scale daily interval plot, true numeric labels, daily exact-value table, keyboard city switching, contained plot/table scrolling at phone widths.
- Mismatch lock, cancelled redeal timers, matching and win, create-only stable save ID, exact field readback, retained unsaved win, retry and persistent history.
- Replaced the earlier expensive procedural/3D/rotated treatment with a short 2D card turn and static tabletop lighting. Rotation removal correlates with the previously stalled compositor becoming capturable; this is not a general browser performance claim.

## Executed checks

See verification.json for every assertion and observed value. Desktop 1440px, phone 390px, narrow 320px; no document horizontal overflow and at least 44px measured controls. OS reduced motion leaves zero running animations; sky motion also has a pause control. Enter changes the selected city and opens the exact table; Space/Enter play a mismatch and all six pairs. A failed save retains its result, retry uses the same ID/baseRev 0, data.get matches the stored fields, and reload renders the recorded score. CSS 200% geometry is not browser-native zoom.

## Honest limits

No actual Desktop/chat-generation or production-backend qualification, screen-reader speech, real touch, browser-native zoom or exhaustive weather-condition contrast sweep. Existing generated-art provenance is inherited with source commit and byte hashes; original prompts/provider metadata are missing and not reconstructed. Three detector advisories remain: semantic sun glow, rain stripes, inherited room lighting. Invalid black/clipped diagnostics are excluded from this packet. The downstream task owns real regenerated-Space and host review.

Executed assertion count: 29
Valid PNG capture count: 22


## Final execution receipt

Source revision: e26f9553d2f6ba88e90c3e15f39c6eb10677f43b. Re-executed from a new empty isolated store; initialHistoryCount was 0. All 29 checks passed. The 22 PNG files in this packet were replaced with this final run, not prior-revision captures. Public network response receipts and the one demo round are in public-live-receipts/. Temporary verifier server was stopped after the run. Final visual recheck passed; the two requested polish changes were confirmed in these captures.
