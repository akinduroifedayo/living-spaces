# R02 synthesis for refinement

Ife needs normal Hermes chat to build durable Spaces whose revoked Refresh permission cannot silently restart old upkeep. The repair keeps consent, local scheduling intent and native interruption knowledge separate. This is a design contract, not product or release acceptance.

## Selection and gates

Both audited candidates read all forty-three bound bodies and changed no product files. Both recommend synchronous reconciliation in the existing grant decision and reject a new durable barrier registry. The parent uses candidate B as the refinement base because it explicitly preserves refusal diagnostics and binds post-withdrawal effects to the decision identity. Candidate A supplies explicit native exception classification and the warning that missing jobs cannot prove execution termination. No broad architecture change or new schema is justified.

The frozen rubric criteria are durable withdrawal, fail-closed regrant, preserved history, concurrency and crash boundaries, and repair size. Parent provisional scores are A [3,3,4,3,3] and B [4,4,4,4,3]. The separate score receipt binds report hashes and the rubric. The required different-family cross-judge is skipped under Arena's unavailable-judge path because Claude's subscription window is exhausted until 02:00 CT. Neither a same-family judge nor these scores substitute for independent source review after repair.

## Observed native contract

The parent executed real cron.jobs and cron.executions adapters in a disposable home without a cron worker or a model call. pause_job preserved a synthetic existing fire_claim. cancel_job_run returned success=true and cancelled=true while get_execution still reported running and a cancellation marker existed. The request is not termination evidence. Full logs and source hashes are bound separately. This characterizes native storage and acknowledgement, not actual worker interruption or a concurrent fire race.

A reconciliation must therefore refuse while any retained native job has fire_claim or run_claim, while an observed native execution remains claimed, running or unknown, or while ledger coverage is incomplete. This additional claim gate comes from observed pause behavior, not a new guessed protocol field. A paused job with a claim is not quiescent. A missing job alone is not proof. Native claim-versus-pause race qualification and actual model cancellation remain open runtime gates.

## Ownership and allowed repair

Only living_spaces_core/grants.py, schedules.py and runs.py may change. Tests and all other product files are frozen for this writer. This is a multi-function repair, not a one-method patch.

- grants.decide owns the effective decision. Withdrawal first commits revoked or denied, local inactive schedule and pending-run uncertainty in one SQLite transaction. Only then attempt native cleanup. Native adapter failures must not undo durable withdrawal or cause REST revoke to fail. Return the durable decision with visible interruption uncertainty.
- schedules.on_refresh_revoked gains an optional transaction argument to support local withdrawal inside decide. Preserve its existing standalone caller contract. schedules.get_schedule must not promote paused or disabled local intent just because native readback is enabled.
- schedules.reconcile_refresh is the one new reconciliation entry point. It accepts the current write connection, Space id, actor, and optional expected withdrawal audit id. It checks decision identity before post-withdrawal effects. On regrant it runs before the grant update, while the prior decision is still visible. Native pause or authoritative absence must be established for each retained recurring identity. Native claims and execution uncertainty prevent a safe receipt. Success leaves the schedule paused or disabled, with no next run. A separate explicit Resume is still required.
- schedules.Reconciliation is a small private result type for schedule fencing, execution quiescence and a reason. It is not a second persistence system. schedules._native_call may translate only native invocation failures into explicit uncertainty. SQL, parsing of internal rows and programming failures remain outside the catch. Native malformed or no-op acknowledgements must not become success.
- runs.cancel_pending preserves its integer result and gains optional conn support if needed. runs._withdraw_pending records local feed cancellation as before, but agent interruption intent cannot fabricate canceled status or suppress later native terminal synchronization.
- runs._sync_agent_runs returns a private NativeObservation with observation completeness and outstanding native identities. It still performs existing history synchronization. Cancellation requests cannot suppress later terminal observations. Missing jobs and unknown native statuses cannot manufacture termination. Native failures report incomplete observation.
- grants._audit may return the inserted audit id. Existing audit and run detail retain diagnostics and identities. Refusal diagnostics must commit before decide raises typed SpacesError outside the transaction.

Imports required for these types are allowed. Helper functions are limited to the named new functions above. If another helper or function body is necessary, report the exact seam rather than silently expanding scope. Preserve public signatures except the optional transaction arguments. Existing tests with old instrumentation may need parent-owned migration, but the writer must not add product fallbacks merely to satisfy stale fake modules.

## Required behavior and proof

No retained native identity means initial Refresh approval has no new cron dependency. Revoke during adapter failure commits inactive local intent, preserves truthful agent history, and exposes unavailable interruption. Regrant during uncertainty refuses before consent changes. Restored native reconciliation runs before grant and never creates, resumes or triggers work. Completed history, other Spaces and user records stay unchanged. Explicit Resume remains valid after confirmed reconciliation.

All thirty-five frozen review methods must remain byte-identical and eventually pass. Their existing red receipt is the baseline. The one missing-upkeep R01 method remains red in this unmodified repair tree until its separate one-file REST repair is integrated. The other two R01 methods are passing controls. The R02 writer must not touch that API file. Parent owns stock execution, integration, live Desktop probes, generated files and review. SQLite serializes participating local writers only. No claim of atomicity with cron or protection against independent native administrative edits is made.
