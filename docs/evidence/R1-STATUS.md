# Release 1 evidence status

The goal is a real application built and evolved from normal Hermes chat, used in Desktop, with durable shared data and controlled upkeep. This report does not assert release acceptance.

## Current checkpoint

Forge froze the shared contracts on `forge/r1-contracts` and launched five implementation lanes in private worktrees. The first Claude UI, sandbox and agent attempts hit the subscription limit. Fresh Codex seats replace those failed attempts. Their receipts remain under the external build directory. No implementation lane has an accepted verdict yet.

The isolated-home model access smoke returned `ISOLATED-TURN-OK` through `claude-sonnet-5-5`, using the existing machine-wide Claude login. This is model access evidence, not Space creation acceptance. The Claude subscription limit subsequently blocked worker seats until its reported 16:00 CT reset.

The harness launcher started the installed Hermes Desktop in a separate instance. Its gateway process environment named the isolated build home. The normal chat composer rendered. The harness then stopped that instance and its gateway. This does not establish plugin restart persistence.

## Acceptance ledger

| Check | Status | Missing evidence |
|---|---|---|
| R1-01 safe hosting | Pending | Requalify integrated sandbox in isolated Desktop, adversarial ordinary-network probes and origin-check diagnosis. Prior spike is historical evidence only. |
| R1-02 real creation | Pending | Normal-chat model invokes plugin tools and creates Research Desk with working Open Space and three views. |
| R1-03 durable interaction | Pending | App edits persist and chat reads/changes the same records, reflected without manual reload. |
| R1-04 evolution and breadth | Pending | Chat evolves Research Desk and a different app without data loss. |
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

Five implementation lanes are in flight. Forge owns the isolated-app harness, integration and evidence collection. After integration the first user-value gate is R1-02, then the remaining R1 boundary checks. Miro's design qualification remains separate from engineering verification and Ife's final acceptance.
