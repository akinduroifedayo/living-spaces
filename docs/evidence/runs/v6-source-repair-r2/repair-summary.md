Implemented the bounded repair for native canvas requests, queued-burst exclusion, and durable pre-admission refusal recovery.

Confirmed the assigned cwd and HEAD `a96bd3b1c797f03f47c50cd1f7385807389dffba`. Before editing, I read all 51 complete bodies, verified their hashes and source hashes, matched all 621 source-baseline files, and verified the parent preflight’s `status: verified`.

The exact delta is six files, with 87 insertions and 11 deletions.

- `src/desktop/ui/actions.mjs` synchronously admits one in-flight request. Extra burst requests receive immediate feedback without queued dispatch work. Same-key payload conflicts remain visible. Definitive `prompt.submit` refusals persist through `reject`; restored refusals report their original reason without native lookup or resend.
- `living_spaces_core/actions.py` exposes `refusal_reason` and adds `reject_action`. It validates the live Space session, exact activation/input identity, absent admission, and finite refusal reason. Conflicting refusals fail closed; repeated identical refusals preserve the record. Receipt observation cannot overwrite a refusal.
- `living_spaces_core/db.py` and `migrations.py` add nullable `refusal_reason` and its idempotent existing-database migration.
- `living_spaces_core/__init__.py` exports the operation.
- `dashboard/plugin_api.py` adds the trusted-host `actions/reject` endpoint with exactly `session`, `activation_id`, `input_id`, and `reason`.

The finite reasons are `permission_denied`, `queue_full`, `invalid_params`, `not_found`, `profile_mismatch`, and `runtime_draining`. Classification is confined to `prompt.submit`. `admission_conflict` remains unresolved because an admission may exist. Ambiguous transport failure retains exact-ID explicit retry and no automatic resend.

Reject updates only refusal and settlement fields. Original input ID, payload, target, and null admission remain intact. The existing `BEGIN IMMEDIATE` transaction serializes reject, claim, and observation writes. The column check and `ALTER TABLE` run inside serialized initialization, making repeated initialization safe. No synthetic receipt or admission is created.

Persistence failure remains visibly failed and includes both the native reason and an explicit statement that refusal persistence could not be confirmed. This also covers the frozen legacy fixture.

All 72 test files remain hash-identical. The frozen Node suite remains:

`487758dc6b198347bb83d92db6016d5accccb7373a93923c078ee936c413b46b`

The Python canvas suite remains:

`45201305598024a86fbe04b934bbb20065804f6aafe080258df51a6c13d392d5`

Only the six permitted files differ from the source baseline. The other 615 files and all packet bodies remain unchanged. `git diff --check` exited zero.

**Tests have NOT RUN.** No probes, builds, servers, browsers, network calls, model submissions, commits, or live-app changes were performed.

The accepted window-wide activation limitation remains. This adds neither a cumulative spending cap nor a per-tool permission layer. Database-reopen behavior, frozen-suite passage, and real native admission/spending still require parent execution and fresh independent review.

Model the Domain kept refusal separate from native admission. Make Operations Idempotent shaped repeat rejection and migration. Laziness Protocol kept the repair within architecture A and the six allowed paths.