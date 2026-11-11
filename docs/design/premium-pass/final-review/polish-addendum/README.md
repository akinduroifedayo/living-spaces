# Final polish addendum — delivery index

Start with [FINAL-POLISH-REVIEW.md](FINAL-POLISH-REVIEW.md). **Three visual iterations verified; full product acceptance withheld.** The source/current-revision proof, exact scope, before/after links, host-spec matrix, state gaps and reproduction steps are there.

## Integration contract

Forge only: copy this directory without modification to `docs/design/premium-pass/final-review/polish-addendum/`. Preserve v1 and all prior evidence. Commit and push through the existing approved lane; return commit ID and manifest verification. Miro must independently compare each committed blob to MANIFEST.json before calling docs delivery complete. This is documentation-only integration; do not load a host candidate or alter the store as a side effect.

`MANIFEST.json` enumerates payload files with exact SHA-256, bytes, original evidence location and PNG dimensions; it excludes itself. It checks copied evidence, not fresh runtime behavior. Public generic demo captures only. No screenshots of the user's outside sidebar/account area are included.

## Key before / after comparisons

| Space | Regenerated before | Final actual-host capture |
|---|---|---|
| Sky11→12 | `../audit/b-sky-window-mobile-verified.png` | [Sky12 app390](a-live-sky-loaded-390.png) |
| Research18→19 | `../regenerated/research-phone-390.png` (different capture scale) | [Library19 app390](a-live-research-detail-390.png) |
| Pair10→11 | `../audit/b-pair-play-mobile-verified.png` | [Pair11 app390](a-live-pair-play-390.png) |

Original baseline4/8/5 comparisons remain one level up in the immutable v1 report, `before/` and `regenerated/`. No original screenshot is rescaled/relabelled here. App390 means guest275; app320 means guest221, not equivalent standalone width.

## Evidence authority and exclusions

`a-live.md` and `b-live.md` are the isolated live assessors' reports; they retain their original absolute paths and auxiliary-image inventory. The selected evidence files in this packet retain original names and exact bytes. JSON receipts intentionally retain references to the complete originating capture set. Not every original auxiliary image is copied here; absence from this curated packet does not imply the source report is fabricating an image.

**Exclude from acceptance:** original A `a-live-sky-window-desktop.png` / `a-live-sky-window-390.png` and B `b-live-sky-window-native.png` / `b-live-pair-play-native.png` were unready startup shells. Use populated `a-live-sky-loaded-*` or B `*-ready-*`. A `a-live-*-revisions.png` remained Run history; use `a-live-*-revision-proof.png`. Superseded images, raw helper scripts and Python bytecode are deliberately not copied. All cited original drivers remain in the inspector's authorized Expansion evidence directory; no runtime replay was performed in packaging.

The paused Upkeep/Permissions captures clip the very top of the drawer title because of the public-pane crop. That is not an app title-clipping defect. The actual zero-width **header identity** at900/320 is a different, measured problem.

## Review receipts

- [Design assessment](a-live.md): authored worlds, priority issues, heuristic/cognitive-load findings, visible states and honest limits.
- [Technical assessment](b-live.md): detector scope, DOM geometry, modal keyboard, AX/focus/CSSOM and runtime identity.
- [Detector receipt](b-live-detector-receipt.json): real command/exit, scoped findings, width deltas and final restoration.
- [Iteration provenance](polish-provenance-readback.json): one ordinary-chat prompt each, revisions, changed generated files and saved-data/grant/manifest preservation.
- [Sky12 revision](a-live-sky-window-revision-proof.png), [Research19 revision](a-live-research-desk-revision-proof.png), [Pair11 revision](a-live-pair-play-revision-proof.png).

Do not infer elapsed-formatting success from Pair's empty History or post-polish functional recertification from pre-polish checks. Do not equate source candidate2b93cf8 with the loaded9b703959… renderer. No provider-applied priority-tier claim is made.
