# F3 maintenance coordination

This note describes the replacement implementation. It is not a proof or a test receipt. Native cron remains the schedule and execution authority.

## Private state

`maintenance.py` owns admission, evidence reduction, retirement, and identity checks. Its SQLite records have separate responsibilities.

- `maintenance_spaces` binds each Space to an incarnation UUID and a link generation. Creation writes the UUID in the Space transaction. Startup backfills existing Spaces transactionally.
- `refresh_claims` remains the single active native-work binding per Space. Its compatibility phases remain `pending`, `background`, and `unresolved`. The added fields bind incarnation, link generation, command, and actor.
- `maintenance_operations` retains command tokens, exact known native IDs, raw replies, errors, and retirement dispositions. These records survive Space deletion so an old reply can belong to its original operation.
- `maintenance_effects` records possibly-sent effects, observed replies, and outstanding one-shot disable obligations. A command envelope commits before the lifecycle writer starts. Effects inside that writer commit with its local changes. A live failure copies rolled-back receipts into the retained operation.
- `maintenance_feeds` binds local feed runs to an incarnation and, when authorized, a native Run operation.

These tables do not copy native execution history or supply authoritative enabled state. Native inventory comes from validated public `cronjob_manage` lists with `include_disabled=True`.

## Admission and retirement

Refresh and linked Upkeep Run share `maintenance.acquire` and the same active claim. A matching follower returns the saved native reply without another dispatch. A different target blocks with the known native IDs.

Schedule and Resume use `maintenance.admit`. Schedule blocks unlinked claimed one-shots. Replacing the exact linked claimed job remains explicit recovery. Resume checks disabled legacy one-shots and cannot treat a paused native job as completed work. Queued or running feed work blocks incompatible commands with its run IDs.

Pause suppresses scheduling without releasing execution ownership. Remove retires coordination as `abandoned` only after exact removal or absence is verified. Abandonment does not assert that all native execution has stopped. Archive preserves unresolved native ownership.

A returned reply or finalizer checks the incarnation, operation token, exact claimed job, and link generation before changing live state or cleaning up its owned native resource. Receipts can still update the original historical operation. An old-incarnation caller returns `not_found`, with the original native reply, instead of treating a recreated Space as its target.

## Native outcome evidence

The reducer distinguishes a matching explicit terminal reply, matching background acceptance, and unresolved work. Forwarded and metadata-free replies remain unchanged and unresolved. A terminal-looking reply for another job ID is not terminal evidence for the owned job.

Background acceptance captures a usable matching reply's `last_run_at`, including an explicit null baseline. Missing, malformed, or mismatched baselines remain unknown. A later usable changed stamp and terminal native status can retire background work as `conditional_terminal_stamp`. This preserves the existing conditional native contract. It does not prove execution-history correlation or execution success.

Elapsed time, caller death, missing inventory, and pause never authorize another native dispatch. A later caller can retry a still-outstanding disable obligation without replaying create or run.

## Local transactions and feed work

Native `run` is outside every SQLite writer because inline native execution can call Space tools. The possibly-sent reservation commits before dispatch.

Archive performs Space changes, session closure, and feed cancellation in one local transaction after native schedule suppression. Delete stages cancellation in that same transaction before native removal. A refusal rolls the cancellation back. The F2 reference-aware blob deletion statement remains unchanged.

`runs.cancel_pending` and transactional `get_run` use the caller's maintenance connection. The latter supplies read-your-writes behavior without exposing uncommitted cancellation to other connections.

Feed source writes carry a run-incarnation context. `db.write` checks that context after acquiring its writer, before feed record changes. This closes the gap between a source's pre-write callback and its actual local commit without changing the F4 record limits or feed parser.

A feed can attach to an existing native Run operation only through a matching public `current_cron_execution` job identity and the matching feed link. Missing identity cannot create that attachment. Standalone feed shims without a PluginContext retain local feed admission when no native operation or claim is known. They cannot audit unknown native orphans. Configured public-context callers do audit those orphans.

## Replacement ordering

The candidate is created paused, then activated and verified before the old job is removed. This retains the frozen candidate-activation-refusal contract. Removing the old valid schedule first could destroy it when candidate activation is refused.

Native effects and SQLite are not atomic. A candidate can be enabled while the old job still exists. If old removal or its verification is uncertain, the old link and claim remain and the candidate is reported unlinked. Cleanup reports preserve the original refusal, pause failure, and removal failure. The implementation does not claim to roll back external effects.

## Limits and qualification

The public API does not provide atomic run-and-disable behavior. Death after resume or acceptance but before verified pause can leave a one-shot enabled. Host suspension or an inline run that crosses the seven-day slot can permit another native fire. The offset is not a lease. This is not crash-safe exactly-once execution.

A command envelope is durable before native effects. Individual effect receipts inside a lifecycle writer are not independently durable until that writer commits. Death can therefore lose a newly returned candidate ID. Recovery discovers exact Space-owned names, includes disabled jobs, and never automatically replays the uncertain create.

If SQLite cannot accept a post-run receipt, the implementation can attempt exact-ID suppression or terminal cleanup after a read-only ownership check. It retains the committed reservation and reports the storage failure. That compensation is best effort, not an atomic storage-and-native transaction.

The unchanged stock method `tests.python.test_native_upkeep.NativeUpkeepTests.test_agent_refresh_now_without_a_link_creates_an_unlinked_one_shot` expects its last recorded native call to be `trigger` at line 177. Safe metadata-free handling requires a later pause. The implementation keeps the pause and leaves that contradictory stock assertion as an explicit RED gate. It does not parse free-text notes, inspect fake-specific attributes, replay run, or edit the frozen assertion.

**TESTS NOT RUN.** The parent owns execution, frozen-file verification, integration, review, and qualification.
