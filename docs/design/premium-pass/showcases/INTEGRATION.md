# Forge integration — exact bounded handoff

Source worktree: `/Volumes/Expansion/Development/Projects/living-spaces-wt/premium-pass`, branch `miro/premium-pass`, pushed final revision `e26f9553d2f6ba88e90c3e15f39c6eb10677f43b`.

## Source integration

Do not merge the whole branch: earlier historical revisions include work beyond this commission. Relative to the upstream kit phase (`6000b735`), this phase changes only:

1. Add the entire `src/living-spaces/runtime/kit/showcase/` subtree from the final revision (19 files; two references plus their isolated runner/verifier).
2. In the design section of `src/living-spaces/skills/build-space/SKILL.md`, change only the showcase link from `references/showcase/README.md` to `../../runtime/kit/showcase/README.md`. Preserve current runtime, data and upkeep prose.

Example exact scoped extraction from the final source revision after fetching, subject to your integration-worktree status:

```sh
git restore --source=e26f9553d2f6ba88e90c3e15f39c6eb10677f43b -- src/living-spaces/runtime/kit/showcase
```

The kit/guidance parent receipt remains separate. This is a working local reference subtree, not a new default house style and not evidence of successful ordinary-chat generation.

## Documentation integration (Forge only)

Copy the contents of this staged directory to `docs/design/premium-pass/showcases/` and commit there. Miro has not written that repo path. It includes 22 PNGs, README, bounded PRODUCT/DESIGN receipts, verification output, finish review, SHA-256 manifest and public live response/demo record receipts. No browser profile or invalid diagnostic captures are included.

Final source and documentation hashes are in SHA256.json. Keys beginning `src/` are rooted at the repo; other keys are relative to this directory. Original generated WebP imagery is inherited unchanged from the earlier public/generic reference assets; generation metadata gaps are stated rather than reconstructed.

## Exercise

Use the two commands in README.md. Start the runner on loopback only, then open the two URLs. Verification should be performed with a new empty output store for the first-round/empty-scorecard captures. The runner is temporary: stop it when finished.

Final actual run: 29 checks passed from a fresh empty store, initialHistoryCount 0. Live forecast receipts were obtained at 2026-11-11 12:37 UTC. Final independent visual recheck passed after mobile scroll-cue and win hierarchy fixes. Actual Desktop, production backend, ordinary-chat regeneration, screen-reader speech, real touch, native browser zoom and exhaustive condition-dependent contrast remain unqualified. These belong to the existing downstream review, not this reference-completion claim.
