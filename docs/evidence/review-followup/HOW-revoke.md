## Overview

Ife wants normal Hermes chat to build safe, durable custom Spaces. Refresh revocation must stop upkeep, and granting Refresh again must not silently restart it. The frozen source guarantees committed permission withdrawal and conditional native pause handling. It does not guarantee native suspension through adapter failure, or safe regrant after that unresolved failure.

This is one simple-path HOW explanation against `302320b78dfe2b40b44eae2657bd5165fd03d8ae`, on `forge/r1-c-how-revoke`. No implementation is selected.

## Key concepts

The Refresh grant, local schedule status, and native job state are separate facts. `grants._check` requires `granted` and matching scope. Agent upkeep additionally requires the current exact handler/prompt. A schedule's `cron_job_id` identifies native work; a local `disabled` row does not disable that work by itself.

## How it works

**Permission withdrawal commits first.** REST `grant_decide` calls `grants.decide`. Its grant transaction writes the decision and audit before cancellation begins. `db.write` commits on normal exit and rolls back only its own transaction on an exception. Therefore later cancellation failure cannot roll back the already committed `revoked` grant. REST `_run` catches `SpacesError`, not the raw `ImportError` in R02.

**Normal cancellation has two stages.** `runs.cancel_pending` first pauses the retained schedule job, then `_sync_agent_runs` imports native executions before selecting pending runs. It removes one-shot jobs, pauses recurring jobs and requests `cancel_job_run`, then records cancellation locally. This discovers running native work even when no local pending row existed. Subsequently, `schedules.on_refresh_revoked` calls `pause_schedule(True)` for an active or paused schedule. A non-null `pause_job` result leads to committed `paused`, cleared `next_run_at`, and an audit reason requiring Refresh approval and Resume.

These are conditional adapter calls and local commits. The upfront pause ignores its return value. Local canceled rows and a non-null adapter response do not independently prove interruption of actual model/tool execution.

**Adapter unavailability already has a fallback.** In `pause_schedule`, an `ImportError` loading `_cron()` calls `_disabled`. A missing job also disables the schedule. `_disabled` commits `disabled`, clears `next_run_at`, timestamps the decision, and audits the reason. It retains `cron_job_id`. Exceptions from `pause_job` itself are outside that loader catch. `_sync_agent_runs` separately tolerates import failure, but cannot protect a failure before it is called.

**R02 prevents reaching that fallback.** Commit `1a5a2e40ee1d5baf81f21af334ab365e904cab15` added the upfront pause and native-ledger discovery. Its `_cron()` call raises before discovery or pending-row selection. In `grants.decide`, the import/attribute catches protect callback lookup only. Calling `cancel` occurs in the `else`, so its exception escapes and skips `on_refresh_revoked`. The cancellation transaction rolls back; the grant remains revoked and the untouched schedule remains active.

The parent's reported synthetic `revoke_module_unavailable` result, including HTTP 500, matches this trace. At `e45e094`, the complete old `cancel_pending` body loads cron only inside the pending-agent loop. With no pending rows, cancellation returns and the schedule callback reaches `_disabled`. This explains the reported old-function control. It establishes fallback reachability, not successful native interruption or general old-tree safety.

**Regrant does not reconcile native authority.** REST requires the displayed `requested_scope`; `grants.decide` checks that snapshot and limits the selected scope, then commits `granted`. It neither checks schedule cleanup nor pauses or resumes a native job. Thus an enabled job surviving R02 stays enabled without Resume. In the disabled fallback case, the pointer also survives. `get_schedule` returns disabled rows without consulting cron, and `pause_schedule(False)` rejects them until schedule approval. Those local rules do not themselves stop the retained native job.

Explicit schedule approval and Resume recheck Refresh inside their write transaction. The same commit added the missing transactional checks for feed approval and Resume, closing the reported F09 ordering race. Those checks govern those actions, not a grant-only transition. Native agent jobs receive `agent_prompt`, which asks them to check Refresh; that prompt is not an enforced native pause acknowledgement.

## Where things live

Under `src/living-spaces/`:

- `living_spaces_core/grants.py:159` owns decision ordering; `:129` owns permission checks.
- `living_spaces_core/runs.py:61` owns cancellation; `:93` imports native history.
- `living_spaces_core/schedules.py:93`, `:115`, `:185`, `:253`, and `:287` own disabling, readback, approval, pause/resume, and revoke handling.
- `dashboard/plugin_api.py:48` and `:163` own REST errors and grant forwarding. `living_spaces_core/db.py:120` defines transaction boundaries.

## Gotchas

The missing invariant is that granting Refresh alone must not restore effective upkeep authority to any job surviving revocation. Before regrant can safely become effective, the system must establish that such work remains unable to act without fresh explicit schedule authority. A disabled local row cannot establish this while native suspension remains unacknowledged.

The smallest discriminating next observation is the retained native job's enabled/paused state and lifecycle-call log immediately after grant-only reapproval in the existing disabled-fallback control, without Resume. That separates successful local cleanup from native suspension. This observation was not performed here. R02 is synthetic adapter fault injection in one live process, not a production outage, native model run, socket action, or crash-atomicity proof.

Integrity checks matched 423 baseline files, all 25 packet hashes and eight source hashes. This is integrity evidence, not a sandbox.

Exact input bodies read were `.run/packet/pins.json` and every `required-001.txt` through `required-025.txt` in that directory, completely. These contain the whole review, grants, runs, schedules, REST module, HOW skill, explainer template and Unslop. Also read completely were `/Users/ifedayoakinduro/.agents/pstack-models.md`, `/Users/ifedayoakinduro/.hermes/skills/pstack/poteto-mode/SKILL.md` and its `references/hermes-tools.md`. Additional reads were `db.py:107-149`, the four-file `1a5a2e4` diff, and the complete `e45e094` cancellation body. Baseline manifest processing and static hash/AST reads supplied integrity and line references. Denied or missing required inputs were none; no repository-local AGENTS.md was found. No product execution occurred.
