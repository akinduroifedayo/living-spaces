# Release 1 evidence status

The goal is a real application built and evolved from normal Hermes chat, used in Desktop, with durable shared data and controlled upkeep. This report does not assert release acceptance.

## Current checkpoint

All five primary lanes are integrated on the build branch, not main. Parent reran the current integrated baseline at `d65126d4f8beb98827636363ab915794d445a405`. The actual Hermes runtime bootstrap ran all 146 Python cases with no failures or skips. A separate bare-venv attempt reached the same ordered cases but had four native-cron setup errors because that interpreter lacked `hermes_yaml`. Both receipts are retained under `evidence/current-baseline/` and `evidence/current-baseline-runtime/` in the external build directory. No product or test bytes changed between those attempts. The earlier real-adapter test caught the missing flat operation exports that fake-core tests missed. Public upkeep exports are now lazy, preserving import isolation.

The current combined sandbox and UI Node run passed all 76 cases with no failures or skips. Its raw TAP output and receipt are in `evidence/current-baseline/host/`. Earlier parent Chrome smoke passed 17 checks after correcting execution-context attribution, selector quoting, fixture readiness, and fragment navigation. Those failed attempts remain retained. Static-render and fixture-browser results do not establish Desktop or release acceptance.

The packaging candidate passes unchanged full validation, including Desktop admission, under the actual Hermes runtime in a separate test home. The native `cron.jobs` private-import warning remains. The parent ran all 151 Python cases successfully on the repaired candidate. Its 108-case sandbox and UI run and 19-case reference run pass. The parent verified the red run's 17 behavioral failures and preserved case identities, the byte-identical loader relocation, and all 133 frozen Python methods. Validation is not sandbox or release acceptance. The repository remains private and no verified-unit merge to main has occurred.

The initial model-access smoke returned `ISOLATED-TURN-OK`. Subsequent normal Desktop turns created Research Desk revision 1 and repaired its native-submit bug as revision 2 through `claude-sonnet-5-5` and `claude-subscription-directsdk-experimental`. The existing machine-wide login is used without copying credentials. The first real interaction exposed a generation-reference defect that fake hook tests had not caught. Frame permissions remain unchanged.

The current isolated Desktop and gateway remain in use for qualification. Their home and evidence are under the external `living-spaces-r1` build directory, outside Git. Actual mouse activation added a fifth public paper and saved notes, status and priority. Canonical storage and reopened controls agree. The first replay hit a harness frame-readiness race during reopen; its failed log is retained beside the successful reopen-only retry. A further model turn read those values and changed that same record while the Space stayed mounted. The real app reflected the new note and completed status without a manual reload. This is not full restart evidence.

The real-model trace is `evidence/normal-chat-03.trace.json` in that build directory. `journey-interaction.log.attempt-1`, `journey-interaction-attempt-2.log`, `journey-chat-live-update.json` and its screenshot retain the interaction evidence and the harness failure. The exact packaged renderer SHA-256 is `4ec39eca0987f25709dd8de52de39208bb4c688ea0407fee975b637e5d6fdd00`. These observations precede the packaging repair and must be requalified afterward.

## Acceptance ledger

| Check | Status | Missing evidence |
|---|---|---|
| R1-01 safe hosting | Pending | Requalify integrated sandbox in isolated Desktop, adversarial ordinary-network probes and origin-check diagnosis. Prior spike is historical evidence only. |
| R1-02 real creation | Observed before packaging repair | Real normal Desktop chat created Research Desk; working Open Space, owner index and three shared-data views observed. Native-submit defect repaired through the same chat without permissions changes. Requalify after packaging changes. |
| R1-03 durable interaction | Partial | Actual add/save/reopen and model read/change reflected in the mounted app. Ambiguous-target non-mutation remains unproven. |
| R1-04 evolution and breadth | Partial before packaging repair | Normal chat added Research Desk's Review view as revision 3. Records, grants, and schedule were compared before interaction; the new action updated a paper in the real app. A separate normal Desktop chat created Pair Play revision 1 and returned its Open Space card. Game interaction, evolution, recovery and post-package checks remain open. |
| R1-05 authority | Pending | Actual grant panel, denial and revocation checks, WebRTC disclosure and secret checks. |
| R1-06 refresh | Pending | Real public retrieval, notes retained, failure and concurrent-write behavior. |
| R1-07 schedule | Pending | Approved isolated native cron updates closed and open Spaces; pause and cleanup verified. |
| R1-08 restart and failure | Pending | Full isolated Desktop/backend restart with records, revisions and owner intact; resource/interruption cases. |
| R1-09 repair | Pending | Bounded scoped error and real chat repair without data loss. |
| R1-10 restore | Pending | Code restored as a new revision without data rewind; incompatible schema blocked or safely migrated. |
| R1-11 lifecycle | Pending | Closed/reloaded sessions, malformed/oversized messages, dedupe, second Space, archive/delete stop future upkeep. |
| R1-12 usability | Pending | Miro's qualification of running candidate and observed return-use journey. Static design frames do not pass. |

## Promotion and publication

The repository remains private. Periodic `forge/*` pushes and verified-unit PR merges are authorized. Public visibility, catalog submission, upstream PRs and hackathon submission need separate owner approval. No catalog PR has been opened.

## Procedural gaps

The initial contracts were authored before completing the prescribed HOW exploration and Architect arena. The lane launches also preceded a full frozen-input and native-preflight audit. Those stages cannot be claimed retroactively. The artifacts require fresh independent qualification against the integrated state before unit acceptance or merge. File-separated worktrees do not prove an OS sandbox or worker qualification.

## Next work

The form-reference correction is integrated. Its parent Chrome replay passed 13 Research Desk checks and 11 habit-planner checks without widening frame permissions. Package design synthesis is committed at `d65126d`. Candidate A is the refinement base with B's deterministic static document and source-module graft. The Opus cross-judge read all 98 bound bodies; overlap with B is disclosed and its recommendation is non-binding. `docs/architecture/SANDBOX-ADMISSION.md` records the choice and remaining runtime gates.

Package implementation is committed and privately backed up on `forge/r1-package` at `157043223b6f98f2d375808f2f851c0283bd0c06`. The parent audited the actual Codex `gpt-6.1-sol` high session and all 86 required bodies. A no-match lookup in an unbound Codex memory file is a procedural deviation. The parent also removed one extra EOF blank line that the worker's unstaged-only whitespace check missed. Rebuilding proved identical shipped guest bytes. Raw route, scope, red/green and full-validator receipts are retained in `run/seats/package/attempt-1/` and `evidence/package-parent/` under the external build directory.

A fresh Sonnet medium Comment Sicko seat is auditing only newly introduced comments in its separate `forge/r1-package-comments` worktree. Independent source review, actual Chrome and Desktop requalification, and remaining R1 checks stay open. Pair Play's normal chat created the game and evolved it to revision 2. Actual interaction saved moves and preferences; eight reopen and namespace checks passed. Its initial immediate session lookup raced creation, and transient DOM targeting, index readiness, and selector-quoting errors stopped early harness attempts. Those failures remain beside the corrected canonical session lookup and successful reopen evidence. The new Progress view still needs actual use and preservation checks. Miro's running-candidate review and Ife's final acceptance remain separate gates.
