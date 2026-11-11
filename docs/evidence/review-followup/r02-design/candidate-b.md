# R02 candidate B

## Problem

Ife needs chat-built Spaces whose withdrawn Refresh permission stays withdrawn through native failures, and whose regrant cannot restart old upkeep. **Source** [001–016](packet/pins.json) shows three separate stores of meaning. The grant commits before cancellation; the upfront cron load can abort local schedule withdrawal; grant has no reconciliation gate. **Inference** repairing exception reachability alone cannot prevent regained native authority.

## Usage (caller's view)

```python
# Not implemented. Caller pseudocode.
grants.decide(sid, "refresh", "revoke")  # revoked; inspect schedule reason
grants.decide(sid, "refresh", "grant", requested_scope=displayed)
# Either typed SpacesError("blocked"), still revoked, or granted with inactive schedule.
schedules.pause_schedule(sid, False, actor="user")  # separate explicit Resume
```

## Shape

**Recommended design inference.** Keep synchronous effective consent in `grants.decide`. Do not introduce another authority store.

| Fact | Producer and durable location |
|---|---|
| Refresh decision | `grants.decide`; grants status/scope and decision audit |
| Local scheduling intent | schedules owner; status and next_run_at |
| Native identity | schedules.cron_job_id and runs.detail.cron_job_id; retain both |
| Interruption knowledge | native acknowledgements interpreted by schedules/runs; audit.detail and pending runs.detail |
| Deciding fact | fresh typed reconciliation receipt under the grant write lock; historical audit never authorizes grant |

**Withdrawal.** In one SQLite transaction, commit revoked/denied, local disabled scheduling, null next_run_at, and an audit reason saying interruption is unconfirmed. Preserve cadence, identity, scope snapshots and history. Only afterwards attempt native reconciliation. Adapter unavailability updates the visible reason to include “unavailable”; REST returns the durable withdrawal successfully.

**Regrant.** While Refresh remains revoked, reconcile every retained recurring and pending one-shot identity, including disabled schedule rows. Pause surviving recurring jobs, validate matching identity and disabled state, discover native executions, request cancellation, and synchronize terminal observations. Require both a schedule fence and confirmed execution quiescence. Absence of a job alone does not prove execution termination. An unavailable adapter, ledger gap, no-op, malformed acknowledgement or uncertain cancellation produces typed blocked refusal before grant. No create, resume or trigger occurs. Commit refusal diagnostics before raising outside the transaction. Grant commits only after the receipt; scheduling remains inactive.

```python
# Not implemented. Recommended types/signatures; paths relative to src/living-spaces.
# living_spaces_core/schedules.py
class Reconciliation:
    schedule: Literal["paused", "absent", "unconfirmed"]
    executions: Literal["terminal", "unconfirmed"]
    reason: str
    # safe only with acknowledged schedule fence AND terminal execution evidence
def on_refresh_revoked(conn, sid, decision, *, actor): raise NotImplementedError
def reconcile_refresh(conn, sid, *, actor, expected_decision_id=None) -> Reconciliation:
    raise NotImplementedError
def _native_call(operation, *args, **kwargs): raise NotImplementedError
# living_spaces_core/grants.py
def _audit(conn, sid, actor, action, capability, outcome, detail=None) -> int:
    raise NotImplementedError  # return existing audit insertion id
def decide(sid, capability, decision, *, actor="user", scope=None, requested_scope=None):
    raise NotImplementedError
# living_spaces_core/runs.py
def cancel_pending(sid, reason, *, conn=None) -> int: raise NotImplementedError
def _sync_agent_runs(sid, *, conn=None) -> NativeObservation: raise NotImplementedError
class NativeObservation:
    complete: bool
    outstanding_execution_ids: tuple[str, ...]
# Existing schedules.get_schedule(sid) also changes; public signatures otherwise stay.
```

Exact repair ownership is those three files and eight named functions. `on_refresh_revoked` becomes transaction-local withdrawal, called inside `decide`. New `reconcile_refresh` owns the fence and calls `cancel_pending` within the supplied transaction. Cancellation retains its integer return contract, but native uncertainty becomes typed refusal. `_sync_agent_runs` returns coverage instead of silently implying success; missing jobs cannot manufacture canceled executions. Pending agent intent uses separate withdrawal metadata, not `cancel_reason`, which currently suppresses synchronization. Only terminal native evidence changes agent runs to canceled; completed rows stay unchanged. Feed cooperative cancellation remains intact.

New `_native_call` catches exceptions only around adapter invocation, records operation/type diagnostics, and converts them to unconfirmed receipts. Loader ImportError receives explicit handling. Response parsing, SQL and internal logic remain outside that catch. No catch-and-pass. `get_schedule` may downgrade an active row but never promote inactive intent from native enabled state. Existing approval and explicit Resume remain activation writers. This concentrates policy behind existing caller operations.

| Transition | Durable grant | Local schedule | Native knowledge |
|---|---|---|---|
| Withdraw committed | revoked | disabled | unconfirmed |
| Withdrawal acknowledged | revoked | paused | paused; execution evidence separate |
| Regrant unavailable | revoked | inactive | unconfirmed |
| Regrant reconciled | granted | paused/disabled | fenced and terminal |
| Explicit Resume | granted | active | resume acknowledged |

## Synthesis decision

Rank 1 is synchronous reconciliation using existing persistence. Rank 2 is the barrier alternative below. This is this candidate's ranking only; parent selection remains pending. No sibling material was read.

## Tradeoffs accepted

We accept SQLite writer blocking during the grant fence in exchange for serialization with existing approval/Resume checks. Native effects still have separate commits.

## Alternatives considered

**Durable barrier/resolver.** New `living_spaces_core/refresh_authority.py` owns unresolved authority in a `RefreshBarrier(withdrawal_id, native_ids, grant_intent, receipt)` table. Its `withdraw` commits barrier plus revoked/inactive state; `request_grant` stores displayed positive intent; `resolve` reconciles per-job obligations and conditionally commits granted, leaving scheduling inactive. `grants._check` consults the barrier. Grant becomes effective in resolver commit, rather than `decide`. This hides restart recovery but adds schema, another permission reader and activation writer. Asynchronous resolution cannot satisfy restored-adapter synchronous grant expectations; inline resolution still needs the recommended native fence. Rejected for unnecessary ownership and persistence expansion, not claimed impossible.

```python
# Not implemented. Rejected living_spaces_core/refresh_authority.py.
class RefreshBarrier:
    withdrawal_id: int
    native_ids: tuple[str, ...]
    grant_intent: dict | None
    receipt: Reconciliation
def withdraw(conn, sid, decision) -> RefreshBarrier: raise NotImplementedError
def request_grant(conn, sid, requested_scope) -> RefreshBarrier: raise NotImplementedError
def resolve(sid, withdrawal_id): raise NotImplementedError
```

## Open questions and risks

Can the parent characterize whether pause plus cancellation and terminal ledger observation fences claim-versus-pause races and actual queued/running execution, including cross-process activity? The supplied native excerpt does not define cancellation acknowledgement. Until established, ambiguous receipts block regrant; synthetic leaves prove no interruption guarantee.

SQLite serializes local writers, not cron. Post-withdrawal cleanup checks its audit decision id before effects, preventing stale cleanup after newer consent. Crash after local commit leaves revoked/inactive; crash after native pause leaves revoked; retry reconciles again. External native edits and orphan jobs without retained identities remain outside proven coverage.

## Next implementation step

Parent first binds the native acknowledgement characterization, then assigns the named repair and runs all 35 frozen tests unchanged.

**Compatibility inference.** The five R02 tests require successful durable withdrawal, visible uncertainty, blocked unavailable regrant, restored fencing before grant, and working revoke/regrant/Resume with unrelated state preserved. R01 separately requires the missing-upkeep REST guard; this sketch does not redesign it. Receipt 022 reports 35 tests, 25 failure events in five methods, zero errors/skips; the original 27 and three controls pass. This is minimum acceptance, not release proof.

**Read/verification closure.** Read pins.json first and all `views/required-001.txt` through `required-043.txt` completely. All 43 view hashes matched. Respect complete-file/excerpt labels and inserted display newlines. Additional dependency/skill reads, denials and missing required inputs were none. Preflight direct exit 0, parsed verified, exact base 59aef209f46cc38bf396f5807feb4fe5d6e11edf, 451 files. First output was truncated; unchanged command repeated for parsing. Post-write baseline hashes stayed unchanged; git diff --check exited 0. Requested Codex/openai-codex/gpt-6.1-sol/xhigh/normal; route metadata not independently inspected.

**NOTHING EXECUTED.** No product, tests, probes, services, native jobs, network or agents executed. Only authorized preflight, read/hash operations and report checks ran. Only .run/REPORT.md was written.

