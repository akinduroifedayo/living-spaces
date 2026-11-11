# R02 positive-path refusals

The goal is safe Refresh withdrawal followed by a usable, explicit later approval. The unaccepted R02 proposal passes the existing R02 regressions but permanently refuses two legitimate later approvals. These are release defects, not accepted conservative limits.

## Observations

`unstarted-native/` records actual R02 core, SQLite and native job/ledger adapters in a disposable home. A manual one-shot is queued, with no native claim or execution. Revocation removes its native job. The ledger remains empty, but the local run remains queued and regrant returns `blocked`. There is no gateway ticker, native worker or model run. The fixture Space is deleted and native jobs are reread as empty. `characterize-unstarted.py` is the executed recipe. Its absolute worktree path identifies the unaccepted proposal, not the product branch.

`terminal-history-501/observation.json` records actual R02 core and SQLite with synthetic native cron leaves. All 501 executions are completed. Regrant nevertheless returns `blocked` because the implementation refuses any full 500-entry ledger page instead of proving complete history coverage. This is a source-function characterization, not native execution or concurrency qualification.

`source-binding.json` pins the exact three proposed product files against base `59aef209f46cc38bf396f5807feb4fe5d6e11edf`. `proposed-r02.patch` retains that unaccepted delta for reconstruction. None of it is composed into the product branch by this evidence commit.

## Existing and full-suite results

The first parent review replay executes all 35 frozen methods. R02 cases pass. Six failure events remain in the R01 method because this separate repair tree does not include the composed REST repair. `review-raw.log` and `review-observations.json` retain the result. The author receipt records the unchanged method hashes and complete 51-body read audit.

The supported-runtime full-suite replay executes 340 tests and remains red with eight failure events, eight errors and one skip. The six R01 failure events remain. Two older one-shot status expectations fail. The errors include intentionally disabled optional-module fixtures and an unconfigured synchronization mock. They require separate disposition, not assertion weakening. This is not a legitimate zero-error regression red or a passing full gate. `full-runtime/` retains the direct exit, invocation and raw log.

## Current boundary

A separate Sol medium normal test author owns a draft of three additional methods in a private worktree. Parent owns insertion, frozen-prefix comparison, execution and the subsequent bounded product repair. The original 35 methods remain frozen. Running or unknown native executions must still refuse regrant. Cancellation acknowledgement alone must never count as terminal execution evidence.

Actual worker interruption, a concurrent claim/removal race, independent source acceptance, affected Desktop requalification and the integrated gate remain open. There is no candidate pin or release acceptance.
