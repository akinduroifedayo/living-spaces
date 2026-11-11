# Consent and lifecycle repair handoff

Living Spaces should let normal Hermes chat build durable custom apps whose users approve the exact agent task and schedule, can stop upkeep, and can audit completed work. This lane repairs F01/F02/F05/F06/F07/F09 in the six assigned product files. Its sixteen frozen customization cases pass. Whole-suite acceptance remains RED because of the named other-lane findings and frozen old-test conflicts below. Not landed or committed.

## Workspace and evidence boundary

- Worktree `/Volumes/Expansion/Development/Projects/living-spaces-wt/c-fix-consent`; branch `forge/r1-c-fix-consent`; starting/current HEAD `e45e094b81c19e3cfc0950cb4148f7f7188cd06e`.
- Read packet pins first, then all thirty-two required shards completely. Read the complete review, red log, red audit and frozen method manifest. Initial verification matched all 382 baseline paths, all 32 shards and their pinned sources.
- Read the commissioned model policy, Poteto skill, Hermes tool adapter and gated delegation instructions. Requested identity is Astra high fast per the commission. This report does not independently establish transport identity, effort, tier or fallback; parent must audit its launch/session receipt. No model or delegate was launched here.
- `native-preflight.py --help` directly failed because the file is not executable. Invoked help through `python3`, then used exactly the documented `--workspace`, `--parent`, `--manifest` flags. Supported preflight exited 0 and returned `status: verified`; complete result retained in `preflight.json`. This is a workspace observation, not an OS sandbox guarantee.
- The bounded GBrain context request returned no project card. Local memory search had no relevant hit. Neither supplied implementation decisions.
- All execution uses public synthetic data. `run-checks.py` launches the real stock commands, captures their direct exits, and checks frozen test hashes before and after. `TMPDIR` and `HERMES_HOME` are inside this worktree's `.run`. It does not replace the stock tests with probes.
- The user's no-model/no-live-runtime boundary supersedes the skill's normal delegate, architecture arena, comment-review and real-UI stages. Final independent review and Desktop acceptance remain with the parent. Applied Model the Domain by putting the exact agent task in Refresh scope, rather than adding a guest-only guard. Applied Deslop as a local diff check; no new product comments or unrelated cleanup.

## Exact owned function changes

| File / function | Delta and reason |
| --- | --- |
| `grants.py:_scope` | Accept and validate optional `upkeep: {handler: 'agent', prompt: <exact string>}` beside hosts. Preserve exact whitespace and punctuation; enforce the existing 4,000-character prompt bound. Feed-only scope remains `{hosts: [...]}`. |
| `grants.py:_manifest` | Seed agent upkeep into requested Refresh scope and require matching upkeep identity in addition to host subset compatibility. Feed-to-agent or prompt changes request fresh approval. |
| `grants.py:_check` | Recheck the head manifest's exact agent task against granted upkeep for every Refresh authority check. A reduced `{hosts: []}` grant cannot authorize agent work. This covers manual/guest admission, schedules and source-owned write checks through their existing authority seam. |
| `runs.py:cancel_pending` | Pause a native schedule before discovery; synchronize native executions in the cancellation transaction; cancel discovered pending work. Deduplicate cancel/remove actions by job ID and retain durable canceled rows. Existing native `remove_job` owns cancellation of one-shot jobs. |
| `runs.py:_sync_agent_runs` | Accept a caller's transaction, otherwise open one write transaction. Follow `before_claimed_at` pages of 500 until exhausted, keeping display bounds independent. Preserve execution-ID idempotence. Import native `missed` records as blocked history with their reason; do not use missed occurrences to consume queued manual runs. |
| `schedules.py:decide_schedule` | Add optional trusted-core `requested_schedule`. Compare cadence/timezone/purpose/requested_at against the current row under the activation transaction before native create/activation. Recheck Refresh for both feed and agent. Import native history before deleting/replacing the old job pointer. |
| `schedules.py:pause_schedule` | Recheck Refresh under the transaction before Resume. Leave invalid/unapproved resume paths without native effects. |
| `schedules.py:remove_schedule` | Import native executions before removing the job and deleting its schedule pointer. |
| `plugin_api.py:schedule_update` | Accept requested_schedule and require the complete four-field object for REST approval. Denial still needs no snapshot. Forward it to the core decision. |
| `permissions.jsx:GrantCard` | Show agent mode, exact requested prompt, model-call cost and enabled-native-tool disclosure at Refresh approval. The display comes from the submitted requested_scope, not an unrelated manifest snapshot. |
| `permissions.jsx:PermissionsSheet` | Submit all four schedule fields from the rendered schedule row, retain requested_upkeep, and show a schedule-specific conflict with refetch. |
| `schedule.jsx:UpkeepCost` | Accept a direct upkeep snapshot while preserving existing space-based callers, so Refresh and Schedule share prompt/cost rendering. |

The commissioned `grants.sync_manifest` name does not exist at this frozen base. The actual seam is `grants._manifest`, called at `projects.py:221` after revision insertion/head update, with initial creation through `_seed`. It already receives the current manifest within the write transaction. No `projects.py` integration patch is needed and that file is unchanged.

No net/bridge/feeds, root `__init__.py`, loader/kit/projects, test or LANE_REPORT bytes changed. There is no database schema change.

## Real verification results

All receipts and logs are relative to this `.run` directory. `result-audit.json` reconciles test counts and method identities from the actual logs.

| Execution | Direct exit and counts | Evidence |
| --- | --- | --- |
| Owned frozen methods through real unittest | Exit 0; 16 run / 16 pass; no failures/errors/skips | `owned-final.json`, `owned-final.log` |
| Required `python -m unittest tests.python.test_review_customization -v` | Exit 1; 27 run / 22 pass; five failing methods with eight failed assertions; no errors/skips | `customization-final.json`, `customization-final.log` |
| Stock `python -m unittest discover -s tests/python -t . -v` | Exit 1; 332 run / 315 pass; seven failing methods with eleven failed assertions, ten errors; no skips | `full-python-final.json`, `full-python-final.log` |
| Stock selected Node UI tests | Exit 0; 39 run / 39 pass; no failures/skips | `node-ui.json`, `node-ui.log` |
| Supplemental authority/lifecycle probes | Exit 0; twelve reported observations using real core/SQLite/REST and synthetic cron leaves | `authority-lifecycle-probe-final.json`, `authority-lifecycle-probe-final.log`, `authority-lifecycle-probe.py` |
| Supplemental React consent probe | Exit 0; exact prompt/cost render, scope and four-field schedule submission, conflict/refetch checked in JSDOM | `ui-consent-probe.json`, `ui-consent-probe.log`, `ui-consent-probe.mjs` |
| Scope/hash/diff gate | Exit 0; six owned paths changed, 376 other baseline paths unchanged, 62 frozen test files / 27 frozen test methods / 32 frozen packet shards match | `final-integrity.json`, `verify-scope.py` |

The first discovery invocation omitted `-t .` and ran 301 entries, including a `test_net` relative-import collection error. That command is not claimed as full coverage. Its exit 1 and log remain in `full-python.json/log`; the correct documented command above subsequently executed all 332 cases. Intermediate runs are retained separately.

Node command was `node --test tests/js/ui/net-permissions.test.mjs tests/js/ui/repair-components.test.mjs tests/js/ui/status.test.mjs tests/js/ui/repair-session.test.mjs`. JSX was transpiled in memory by the existing tests. No distributed bundle was generated or committed.

Supplementary probes verify each schedule field independently returns 409 without native calls; missing/null/incomplete snapshots return 400; an agent scope stripped to hosts cannot start work; replacement and removal preserve completed history and last success; 1,502 retained rows import uniquely across four pages with display limit 1; missed occurrences remain visible; two unmirrored running executions cancel with one native call even across repeated revoke; source writes after revoke fail and preserve prior records. These are supporting evidence, not a substitute for stock suites or real Desktop/native execution.

## Frozen red to green identities

Each name below belongs to `tests.python.test_review_customization.ReviewCustomizationTests`. These nine methods failed in the supplied parent red and now pass unchanged. Their nineteen failed assertions are gone.

- `test_f01_feed_to_agent_requires_fresh_refresh_approval`
- `test_f01_agent_prompt_change_blocks_manual_and_scheduled_admission`
- `test_f01_stale_agent_scope_cannot_approve_changed_prompt`
- `test_f02_stale_displayed_schedule_conflicts_at_rest_boundary`
- `test_f02_matching_displayed_schedule_approves_exact_fields`
- `test_f05_revoke_discovers_unmirrored_running_execution`
- `test_f06_denial_preserves_unmirrored_completed_history`
- `test_f07_history_backfill_includes_501st_execution`
- `test_f09_feed_approval_rechecks_separately_committed_revocation`

The seven previously passing owned controls remain green.

- `test_f01_matching_agent_approval_allows_manual_refresh_control`
- `test_f01_unchanged_feed_manifest_preserves_host_scope_control`
- `test_f02_rest_denial_disables_schedule_without_native_job_control`
- `test_f05_revoke_cancels_already_mirrored_execution_control`
- `test_f06_denial_preserves_already_mirrored_history_control`
- `test_f07_history_import_at_500_is_idempotent_control`
- `test_f09_active_feed_stays_paused_after_regrant_until_resume_control`

## Other-lane failures retained

The same five methods fail in both final customization and full discovery. No sibling work was adopted.

- c-fix-net F03 `test_f03_bridge_passes_bound_session_to_real_net_fetch` and `test_f03_closed_session_prevents_redirect_post`.
- c-fix-source F04 `test_f04_stale_source_revision_conflicts_and_rolls_back_whole_batch`, three failed subtests.
- c-fix-net F08 `test_f08_feed_rejects_approved_loopback_before_transport`, two failed subtests, and `test_f08_public_feed_uses_vetted_pinned_destination`.

## Frozen old tests: precise conflicts for the parent

All 305 old cases were executed unchanged. 293 pass and twelve methods need parent disposition. They are not described as a green regression gate. No test was patched, monkeypatched for a full-suite claim, skipped or weakened.

1. `tests/python/test_upkeep_runs.py:UpkeepCase.setUp` supplies `types.SimpleNamespace(check=self.check)` as grants. It has no `_check`. Both activation and Resume now need the transactional authority check, so nine `ScheduleTests` cases error with that exact AttributeError. The instrumentation migration is to provide `_check(conn, sid, capability, scope_need=None)` on that existing fake, returning the same granted-status and host-subset predicate used by `UpkeepCase.check`. All test assertions can remain byte-identical. Do not add a missing-method bypass to production. A precise fixture addition would be:

   ```python
   self.grants._check = lambda conn, sid, capability, scope_need=None: (
       self.grant_status == "granted"
       and set((scope_need or {}).get("hosts", [])).issubset(self.allowed)
   )
   ```

   Affected methods are `test_approval_and_resume_require_refresh_permission`, `test_catchup_dispatch_survives_in_run_history`, `test_create_job_failure_removes_shim_and_reports_disabled`, `test_delete_fails_visibly_when_native_cron_cannot_be_loaded`, `test_failed_catchup_keeps_dispatch_and_last_good_data`, `test_missing_cron_disables_with_persisted_visible_reason`, `test_native_get_refreshes_next_run_and_missing_job_is_visible`, `test_native_schedule_approve_pause_resume_archive_and_delete_in_temp_home`, and `test_re_request_pauses_old_job_and_requires_new_approval`.

2. `tests/python/test_agent_upkeep.py:AgentIntegrationSeamTests.test_manifest_hooks_in_integrated_tree` errors at line 374. It changes the agent prompt, then approves the schedule without renewing Refresh. F01 expressly prohibits that. Parent can preserve its schedule assertions by approving the new displayed Refresh requested_scope immediately before that second schedule approval. Its prior `cron.pause_job.assert_called_once()` remains meaningful. This is an old fixture's assumption about authority, not a product path to restore.

3. `tests/python/test_agent_upkeep.py:AgentIntegrationSeamTests.test_host_approval_snapshot_reaches_core_in_integrated_tree` fails at line 423, receiving 400 instead of its expected stale-upkeep 409. All three approval requests at lines 422, 426 and 429 lack requested_schedule. Parent can capture `{cadence, timezone, purpose, requested_at}` from the schedule request and add it to those payloads, preserving all response/status/native-call assertions. The stale upkeep then reaches its intended comparison; the null upkeep still fails validation.

4. `tests/python/test_agent_adapters.py:RestTests.test_all_routes_success` fails its schedule subtest at line 329 and exact mock call assertion at line 332. Line 318 sends only `{"decision":"approve"}` and the mock assertion expects no snapshot keyword. F02 requires a supplied snapshot forwarded to the core. A payload addition alone cannot preserve the exact `assert_called_once_with(SID, "approve", actor="user")` argument expectation. This is a contract conflict requiring parent authorization/disposition, not merely an instrumentation swap. The production REST boundary must not accept the old payload to make it green. Expected call under the new contract includes `requested_schedule=<the displayed four-field object>`.

These are the complete old-suite failures. No HTTPX transport instrumentation was changed in this lane.

## Native API inspection and hazards

Read the installed `/Users/ifedayoakinduro/.hermes/hermes-agent/cron/executions.py:list_executions` at lines 640 onward, read-only. It clamps limit to 1..500 and pages by `before_claimed_at`, ordered by instant, timestamp text and ID descending. The importer passes the last returned raw claimed_at to the next page. The installed ledger also retains `missed` rows; those now remain auditable instead of being silently skipped. Inspected `jobs.pause_job`, `remove_job`, and `cancel_job_run` read-only; remove_job already calls native cancellation, so one-shot cancellation does not add another explicit hook.

- Exact same claimed_at strings spanning a page boundary are an upstream API limitation: the cursor does not include ID although ordering does. The available list API cannot enumerate arbitrarily many executions with an identical timestamp. This is a source-inferred limitation, not a tested production occurrence or a claim of complete native qualification. No Hermes change was made; parent should decide whether an upstream cursor extension is needed.
- Sync now holds the Space write transaction through retained-history import and native lifecycle calls. This serializes pointer changes with mirroring but can hold the database lock longer for a backlog. No latency benchmark is claimed.
- Native ledger access remains subject to availability and native retention. The existing importer returns when cron modules cannot be imported; it cannot recover executions already pruned by Hermes. No outage/crash injection or distributed atomicity claim is made.
- Native job changes and SQLite are separate stores. The inherited cross-store crash window is not solved by these bounded repairs. Live cancellation/dispatch races, tool interruption and real Desktop rendering remain parent-owned qualification.
- F01 exact authority covers admission and current Refresh checks; it is not a native agent sandbox or a new per-run tool capability system. The existing agent prompt continues to instruct native work to use Space tools.

## NOT done and commit disposition

No Desktop, gateway, model, ticker, live network/listener, credential/profile access, install or host modification was performed. No pushes, merges, PRs, generated-bundle commits, schema changes, external messages or sibling edits. LANE_REPORT.md is unchanged. No claim of release, real native interruption, or fresh independent acceptance.

Attempted `git add` on the six owned product files only. It exited 128 with `fatal: Unable to create '/Volumes/Expansion/Development/Projects/living-spaces/.git/worktrees/c-fix-consent/index.lock': Operation not permitted`. No escalation or alternate Git write route was attempted. Changes remain unstaged in the assigned worktree, ready for parent inspection/integration. Evidence is under `.run` and is not staged.

Nothing remains running. Parent owns the frozen-test contract dispositions, integration with the other lanes, final bundle build, independent review, serialized real Desktop checks and acceptance. `final-integrity.json` binds this report's source state; `git diff --check` passed.
