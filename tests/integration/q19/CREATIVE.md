# Q19 creative-quality criteria (pre-registered)

Status: frozen with the plan, before the first generation session. Revised once before freeze after design-owner
critique (Miro, 2026-11-17: honesty clause, host fit, absolute floor, generic aggregation, entry_rewrites rename). Scoring rules and gate thresholds may not be changed
after any artifact has been seen. The ACCEPTANCE "Judge visuals" rubric (five dimensions) is still scored and gated
exactly as before. This document adds a second rubric; it does not replace or soften the first.

## Why a second rubric

The original rubric checks that an artifact is usable and coherent. An app can score 3 on everything ("consistent but
generic") and still be the bland, interchangeable result the owner does not want. The owner's goal is non-bland,
coherent, sophisticated, genuinely varied apps and documents, built by an agent that explores usefully. Each part of
that sentence is scored separately below, so a generic visual pass cannot stand in for it.

## Per-artifact dimensions (1-5, blinded, every build and every edit)

| Dimension | 1 | 3 | 5 |
|---|---|---|---|
| Distinctiveness | Default template: stock card grid, stock palette, could be any subject | Some subject-specific choices on a generic frame | Specific visual and interaction decisions that clearly come from this subject and its data, and would still read as clear and conventional to a first-time user |
| Coherence | Choices fight each other: mixed type voices, arbitrary colour, decoration unrelated to content | One system, applied unevenly | Type, colour, spacing, motion and states read as one considered system; every flourish serves content; it sits calmly inside the host frame without imitating or contradicting its status language |
| Craft | Rough: misaligned, cramped or empty, default form controls, unstyled states | Tidy but plain; rhythm and hierarchy unremarkable | Considered rhythm, hierarchy and detail, including narrow widths; restraint where it helps (edge states are scored by the ACCEPTANCE rubric, not here) |
| Subject insight | Shows data without helping understand it | Sensible standard presentation | The presentation reveals something (a chart choice, an ordering, a summary) a plain list would hide, and states its measure and denominator; nothing is distorted or decorative |

Each judgment also records `generic: true|false` (would a reviewer mistake this for a stock template with the subject
swapped in?) and one sentence naming the most distinctive decision, or "none".

The edited artifact is judged on its own and also records `edit_integrated: 1-5` (1 = bolted on in a different style,
5 = the addition looks as if it was always part of the design).

## Per-group variety (1-5, blinded)

For each brief and condition, the reviewer sees the three builds side by side (blind ids, shuffled order, never mixed
across conditions in one view) and scores `variety`:

- 1: the same template recoloured or reworded
- 3: different surfaces over a shared structure
- 5: three genuinely different, each defensible, solutions to the same brief; divergence that weakens any single build's clarity does not count

Variety never rewards incoherence: the score is about real alternatives, and per-artifact coherence is scored
separately.

## Agent exploration (deterministic, from the session transcript)

Exploration is measured from tool calls, not judged from prose, because transcripts reveal the condition and could not be blinded.

- `inspected`: the agent looked at its own rendered result (spaces_inspect or an equivalent capture) at least once
  before declaring done. A single capture satisfies it; the report says so.
- `revised_after_inspect`: at least one file write after an inspection in the same session.
- `references_read`: number of distinct kit/skill reference files read.
- `entry_rewrites`: number of writes to the entry file (index.html). This records rewriting, not proven exploration
  of alternatives, and is never gated.

## Pre-registered creative gate

Failed or limit-reached builds stay in the denominator, scored 1 on every creative dimension and variety, and counted
as `generic: true`, and are reported separately, so creative medians can be read with and without failures.

An artifact is generic if a majority of its reviewers mark it generic; ties count as generic. Medians may be
half-integers; a decline is any negative difference.

The gate passes only if all hold:

1. Complete: every planned artifact has two or more independent reviewers, and every brief/condition group has two or
   more variety judgments.
2. No brief-level median decline from baseline to candidate on any of the four creative dimensions.
3. Overall candidate median above baseline on at least two of the four creative dimensions.
4. Candidate variety median at least the baseline median, with no brief where it is lower by 1 or more.
5. Candidate generic rate strictly below baseline, or both are zero.
6. Candidate `inspected` rate at least the baseline rate. The other exploration measures are reported, not gated.
7. Absolute floor: candidate median at least 3 on Coherence and Craft, overall and in every brief.

The report shows every score, the disagreement count (any two reviewers 2 or more apart), sample sizes, the
distinctive-decision sentences, and side-by-side images for every brief. Failed generations are shown, not hidden. This
is a small comparison. It supports a decision about this candidate, not a claim of general aesthetic superiority.

## Cost

Creative dimensions are scored in the same review session as the original rubric, inside its frozen budget.
Variety adds 12 group judgments per reviewer at a frozen budget of 50k input and 3k output tokens. Worst case
rises from $853.20 to $859.26, still under the unchanged $860 cap. The 80% pause stays at $688.
