# R02 candidate A

## Problem

Ife wants normal Hermes chat to build safe, durable Spaces. Refresh regrant must not revive native activity surviving revocation. Source evidence in sealed views 001–016 shows permission commits before cancellation, cancellation can escape before schedule withdrawal, and regrant performs no reconciliation. Parent receipt 022 reports 35 tests, 25 failure events across five methods, zero errors/skips. The following is a design inference, not an executed repair.

## Usage (caller's view)

```python
# Not implemented. Existing caller surface remains.
grants.decide(sid, "refresh", "revoke")  # revoked; schedule inactive
grants.decide(sid, "refresh", "grant", requested_scope=displayed)
# Raises SpacesError("blocked") while native authority is unresolved.
# Success grants Refresh but leaves schedule inactive.
schedules.pause_schedule(sid, False, actor="user")  # explicit Resume
```

## Shape

Recommend synchronous reconciliation at the existing grant boundary. Four facts remain separate. `grants.status` records consent; `schedules.status/next_run_at` record local scheduling; retained `cron_job_id` and run detail identify native work; audit detail and pending-run detail record acknowledgement or uncertainty. No new schema or background service.

The deciding fact is fresh reconciliation of every retained schedule identity and pending agent-job identity, including ledger-discovered executions. `runs` produces that evidence from native responses and ledger observations. `grants.decide` consumes it before committing `granted`. Persist its identity-bound evidence in existing audit/run detail, but never treat an old audit receipt or local `disabled` status as continuing native proof.

```python
# Not implemented. Private domain sketches; no native wire types exported.
# living_spaces_core/runs.py
JobId = str
RunId = str
class Observation:
    complete: bool
    executions: dict[RunId, Literal["terminal", "unknown"]]
class _Interruption:
    jobs: dict[JobId, Literal["paused", "absent", "unknown"]]
    executions: dict[RunId, Literal["terminal", "unknown"]]
    complete_observation: bool
    reason: str
    def permits_regrant(self) -> bool: ...
def _withdraw_pending(conn, sid, reason) -> None: ...  # new
def _reconcile_interruption(conn, sid, reason, actor) -> _Interruption: ...  # new
def cancel_pending(sid, reason) -> int: ...  # preserve public result
def _sync_agent_runs(sid, *, conn=None) -> Observation: ...
# living_spaces_core/schedules.py
def on_refresh_revoked(sid, decision, *, actor, conn=None) -> None: ...
def _record_refresh_interruption(conn, sid, evidence, actor) -> None: ...  # new
def get_schedule(sid): ...
# living_spaces_core/grants.py
def decide(sid, capability, decision, *, actor="user",
           scope=None, requested_scope=None): ...
```

All proposed R02 files are under `src/living-spaces/living_spaces_core/`. Ownership changes are limited to the signatures above. `decide` retains validation and commits withdrawal, schedule disabling, pending-run annotations and audit in one SQLite transaction. `on_refresh_revoked` becomes local-only and uses existing `_disabled`. `_withdraw_pending` preserves feed cancellation guards; agent rows retain observed status and identities with `interruption=unconfirmed`, never a speculative `cancel_reason`.

After withdrawal commits, `decide` starts another transaction, rereads consent, and reconciles only if still withdrawn. For grant from any non-granted state, it reconciles inside the decision transaction before updating consent. No retained identities means no native dependency. `_reconcile_interruption` centralizes the existing pause/discovery/cancellation sequence; `cancel_pending` uses it while retaining its count result and local cancellation behavior.

Pause recurring identities, import their ledger even without local pending rows, cancel live executions, then observe outcomes. Preserve one-shot cleanup semantics, but removal is not execution termination. `_sync_agent_runs` must report incomplete observation, permit terminal native updates despite cancellation requests, and stop converting missing jobs into presumed execution failure. `_record_refresh_interruption` owns schedule acknowledgement/audit writes. `get_schedule` must never promote an inactive local schedule merely because native readback says enabled.

| Event | Consent | Local schedule | Native knowledge |
|---|---|---|---|
| Withdrawal commit | revoked | disabled; next null | unconfirmed; identities retained |
| Adapter unavailable | revoked | disabled; unavailable reason | pending statuses unchanged |
| Pause acknowledged | revoked | paused; next null | future scheduling paused; execution separate |
| Regrant unresolved | revoked | inactive | typed blocked; no create/resume/trigger |
| Regrant reconciled | granted | inactive | pause/absence plus terminal execution evidence |
| Explicit Resume | granted | active after acknowledgement | existing Resume checks apply |

A matching pause response with disabled/paused state acknowledges schedule mutation only. Null, false, malformed responses and effect-then-error remain unknown unless authoritative readback resolves them. Ledger `unknown` is never terminal evidence. Loader `ImportError`, native-call `OSError` and native-storage `JSONDecodeError` become explicit uncertainty; regrant refuses. Restrict those catches to their native boundaries, including cancellation and ledger access. Further exception classes require characterization, not a blanket catch. Internal programming errors propagate after durable withdrawal. This does not promise HTTP success for arbitrary internal defects.

## Synthesis decision

Recommend this shape within this candidate only. Existing public decisions hide reconciliation without making callers coordinate stages. Parent ranking and acceptance remain outstanding; no sibling was consulted.

## Tradeoffs accepted

We accept native latency under SQLite's existing `BEGIN IMMEDIATE` serialization for simple consent ordering. We accept repeated reconciliation for restart safety without another durable authority store.

## Alternatives considered

Strongest rejected shape is a durable quarantine registry owned by a new consent coordinator. Its types would be `Quarantine(space, epoch, native_ids, unresolved)` and `GrantIntent(scope, epoch)`; `withdraw()`, `acknowledge()`, and `release_grant()` would govern effectiveness. Grant becomes effective when the registry releases its barrier, rather than when current retained identities reconcile. This hides retries well but requires every job creator/remover to maintain registry completeness and adds persistence and lifecycle ownership. Native creation still cannot atomically register with SQLite. Its broader producer changes do not earn their cost for R02.

## Open questions and risks

Does native pause/cancel fence already admitted claims, and which ledger observation proves those executions terminal? Parent must characterize that single lifecycle contract before claiming interruption. The supplied leaves omit cancellation internals. Synthetic acknowledgements cannot establish it.

SQLite serializes participating local writers, not native workers or external native edits. A crash after withdrawal leaves durable uncertainty; a crash after native pause before grant leaves consent revoked. Retry reconciles again. Native re-enable or claim races outside SQLite remain unproved; no cross-store atomicity is claimed.

## Next implementation step

After parent selection, implement the named withdrawal transaction and reconciliation boundary, then run all 35 unchanged tests.

Frozen compatibility requires unavailable REST revoke success, blocked regrant, restored pause-before-grant, truthful pending history, preserved completed/unrelated state, and working explicit Resume. Separately, R01 requires only `dashboard/plugin_api.py:schedule_update` to require `requested_upkeep` on approval; denial remains exempt. Three positive controls and the original 27 remain mandatory, not whole-release acceptance.

Read completely: `pins.json` and `views/required-001.txt` through `required-043.txt`, respecting complete-file/excerpt scopes and inserted display newlines. Additional dependency reads: own-tree `dashboard/plugin_api.py` AST-extracted `schedule_get` and `schedule_update`. No other skill leaves. Required-input denials/missing bodies: none. Native interruption semantics remain missing evidence. Standalone preflight returned zero and parsed `verified` for base `59aef209f46cc38bf396f5807feb4fe5d6e11edf` and 451 files. NOTHING EXECUTED against product, tests, probes, services, Desktop, native cron or network; only reads, static inspection, preflight and this report write occurred.
