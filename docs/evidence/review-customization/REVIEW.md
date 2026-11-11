# Living Spaces frozen customization review — ISSUES

**Reviewed SHA:** `234134b6fd2a8553041664d8ad7cbf827a6df230`  
**Private tree:** `/Volumes/Expansion/Development/Projects/living-spaces-wt/c-review`  
**Verdict scope:** mediated HTTPS and agent/feed-upkeep security, consent, data integrity, and lifecycle. This is **not whole-release acceptance**. No fixes, installs, host changes, Desktop/gateway/model calls, real network/listeners, or cron ticker were performed.

## Attribution, inputs, and evidence limits

- Reviewer runtime declares `gpt-6.1-sol` / `openai-codex`; commission selected `sol-xhigh` for a high-risk independent review of Astra-high-authored work. Effort is commissioned, not wire-verified here; the parent must audit its session/route receipt. This is a fresh **same-GPT-family** context, **not a cross-family acceptance gate**. Per the commission, the Claude route is unavailable with HTTP 429; this seat did not retry it.
- Read `.run/packet/pins.json` first, then **all thirty-eight complete required shards**, with no body summaries. The packet covers twelve source files, including governing `AMENDMENTS.md`. Additional source reads stayed in this frozen tree. Required external model/workflow instructions were also read. No live implementation tree was inspected.
- Initial and final verification matched all **376 tracked paths and hashes** against `.run/baseline.json`, the exact SHA, all 38 shard hashes, and all pinned source hashes. Tracked/nonignored status was empty. Evidence writes are confined to `.run/`.
- **Executed counterexamples below use real frozen core/REST/tool code and real private SQLite. HTTPS transport and native cron job/execution leaves are synthetic**, as required by the no-network/no-ticker boundary. A call observed at a synthetic transport is not peer-observed traffic; a synthetic execution ledger is not a real model invocation. Findings name that distinction individually. Parent must rerun each reproducer and qualify any native consequence before accepting it.
- The prior parent full gate (305 Python / 125 stock Node / 147 standalone Node / 19 reference) is relayed context only. I did not rerun or adopt those totals.

## Reproduce and receipts

From any working directory:

```sh
/Users/ifedayoakinduro/.hermes/hermes-agent/venv/bin/python -B /Volumes/Expansion/Development/Projects/living-spaces-wt/c-review/.run/review/reproduce.py all
```

**Observed exit 0.** This means **the retained counterexamples reproduced**, not that product requirements passed. The runner checks frozen-source preservation before and after, explicitly sets `HERMES_HOME`, `TMPDIR`, and `LIVING_SPACES_DB` under this tree's `.run/review/`, runs ten counterexample cases for nine findings, then selected stock tests.

Retained authoritative execution: `.run/review/verified-execution.json` (argv, exit 0), `.run/review/verified.stdout.json` (full child commands, direct exits, output, environment, probe hashes, before/after preservation), `.run/review/verified.stderr` (empty). Original attempts and logs remain alongside them. Original `.run/review/run.py` intentionally retains the subsequently dropped `history_loss` hypothesis and therefore returns 1; use `reproduce.py` for retained findings.

Individual commands below use this exact prefix:

```sh
/Users/ifedayoakinduro/.hermes/hermes-agent/venv/bin/python -B /Volumes/Expansion/Development/Projects/living-spaces-wt/c-review/.run/review/reproduce.py CASE
```

Replace `CASE` with the literal case named for the finding. Every retained case's direct subprocess exit was **0**, in the original successful observation and final replay.

## Executed findings

### F01 — P1: A previously approved feed can silently become frame-triggered native agent work

**Exact source:** `src/living-spaces/living_spaces_core/grants.py:87-109` retains Refresh when new hosts are a subset; `schedules.py:51-66` only invalidates a schedule, not the Refresh grant; `runs.py:163-233` requires schedule approval only for `trigger='schedule'`; `runs.py:147-160` creates/triggers a native agent one-shot; `bridge.py:41-60` routes an untrusted frame's `refresh` as manual. The host Refresh card at `src/desktop/ui/permissions.jsx:12,31-36` describes public-source/host access; cost/prompt disclosure is in the scheduled-work surface instead.

**Reproduction:** `CASE=mode_escalation`; companion `CASE=prompt_change`.

**Observed:** after creating a feed and granting Refresh, a normal manifest write replacing it with an agent prompt leaves `before_refresh='granted'`, `after_refresh='granted'`, `schedule=null`. Without any new host decision, real `bridge.dispatch(...,'refresh',{})` returns `ok=true`, `status='queued'`; the captured native job has `no_agent=false` and contains the newly introduced prompt. Companion case: changing an already approved agent prompt puts its schedule in `requested`; the scheduled entrypoint is `blocked/schedule_not_approved`, **but the frame/manual path queues the new unapproved prompt**.

**Required:** the feed grant must not silently authorize a new model/tool-executing mode or changed prompt. A frame calling Refresh is not a host user approving the new agent task/cost. Before that transition is approved, the frame/manual path must not create/trigger the agent job. This is R1-05's no-silent-new-authority requirement and A-02's disclosed agent approval, not an objection to allowing native agent tools once approved. Ordinary manually requested refresh and schedules being separate is intentional; reusing a legacy feed approval is the defect.

**Evidence class:** executed real bridge/grant/store/admission defect; captured cron creation/trigger only. No actual model/tool spend was incurred or measured.

### F02 — P1: Schedule approval is bound to the upkeep prompt, not the cadence/timezone/purpose displayed

**Exact source:** `src/living-spaces/dashboard/plugin_api.py:184-197`; `living_spaces_core/schedules.py:186-245`; host payload at `src/desktop/ui/permissions.jsx:80`. The API accepts `requested_upkeep`, but no displayed schedule identity/version/fields. Approval uses the current row's cadence/timezone/purpose.

**Reproduction:** `CASE=stale_schedule` (real FastAPI TestClient, no listener).

**Observed:** request displayed as `0 7 1 * *`, `UTC`, `Once a month`; a subsequent request changes it to `* * * * *`, `Pacific/Auckland`, `Every minute`. Approving with the exact unchanged `requested_upkeep` that the host sends returns **HTTP 200**, `status='active'`, and a native job for **every minute** in the changed timezone.

**Required:** stale approval must return `conflict` without enabling a job, or approve exactly the displayed cadence/timezone/purpose. A valid prompt snapshot cannot stand in for the schedule the user approved (SPEC §3).

**Evidence class:** executed REST/core consent failure with captured synthetic cron write. Actual recurring dispatch not run.

### F03 — P2: Closing the bridge session suppresses the result but does not stop a subsequent redirect POST

**Exact source:** `src/living-spaces/living_spaces_core/bridge.py:41-45,70-95`; `net.py:192-268`, especially the redirect loop's grant-only checks. The session is checked outside `net.fetch` and is not available to its per-hop egress checks.

**Reproduction:** `CASE=closed_session_egress`.

**Observed:** first request is a POST to `first.example` while session open. Its synthetic 307 response closes the real SQLite session. `net.fetch` then calls the transport for a **second POST to `second.example` with `closed=true`**. Only after this does the bridge return `session_invalid`. Paired control revokes Net at the same seam: only the first request is issued and the result is `not_granted`.

**Required:** session closure/reload invalidation must prevent new redirect egress/side effects under that closed frame authority; returning an error after the new POST is too late. The already-issued first request cannot be recalled and is not the finding. R1-11 requires lifecycle invalidation, not merely hiding the eventual response.

**Evidence class:** executed bridge/transport-call ordering counterexample with deterministic session closure. No real POST or external side effect was delivered. Not a claim of an atomic network revocation fence.

### F04 — P2: `source_owned=true` silently ignores a caller's stale `base_rev`

**Exact source:** `src/living-spaces/__init__.py:280-305` passes source/source_meta to `_upsert_source` without using `base_rev`; `living_spaces_core/records.py:168-190` replaces source fields without a revision check. The same tool's schema/description at `__init__.py:404-424` instructs callers that stale base revisions conflict and exposes `base_rev` for operations.

**Reproduction:** `CASE=source_conflict`.

**Observed:** read source rev **2**, write newer source at rev **3**, then submit a second source-owned put with `base_rev=2`. It returns `updated=1` and durably replaces the newer title with `stale overwrites newer`. Paired ordinary-data write using the same stale revision returns `conflict`. User note remains intact (the separate source/data columns do work).

**Required:** a supplied stale `base_rev` must fail the whole source-owned batch with `conflict`, preserving the newer source, or the surface must explicitly reject unsupported concurrency parameters rather than silently accept them. This is source-data loss, **not** a claim that the tested path overwrites user notes. SPEC §3 requires stale concurrent changes to conflict/reconcile.

**Evidence class:** executed public tool-adapter and durable SQLite defect; no cron simulation is necessary to the overwrite.

### F05 — P2: Revocation requests native interruption only if someone already read/imported the running schedule

**Exact source:** `src/living-spaces/living_spaces_core/runs.py:61-80` enumerates only locally mirrored pending runs; `runs.py:87-144` mirrors native executions lazily on reads; `grants.py:143-182` cancels before pausing; `schedules.py:280-284` pauses the schedule without discovering/canceling a running execution.

**Reproduction:** `CASE=unmirrored_revoke`.

**Observed:** seed a running execution for an approved recurring agent job, without reading Space history first. Revoke Refresh. Captured `cancel_job_run` calls are **[]**; subsequent real `runs.list_runs` imports it as **running**, even though schedule is paused. Paired control calls `runs.list_runs` once before revocation: one native cancel request is made and the Space run is **canceled**.

**Required:** the cancellation decision and run state must not depend on whether a UI/history read happened before revocation. Discover/cancel currently running native upkeep consistently when handling the revoke, and represent it consistently. Source-owned writes independently recheck Refresh; their denial is not evidence that the native model session was interrupted.

**Evidence class:** executed cancellation-adapter omission and durable-state inconsistency with synthetic native ledger. The actual native `pause_job`/interrupt semantics and real agent survival require parent qualification; this report does **not** claim to have observed a live agent continue.

### F06 — P2: Denying a changed schedule can lose completed run history and last-success state

**Exact source:** `src/living-spaces/living_spaces_core/schedules.py:186-245` removes the old job and clears `cron_job_id` on deny without first preserving its executions; `runs.py:87-144` discovers history only through current schedule/pending job IDs.

**Reproduction:** `CASE=history_denial` (uses `history-requested.py`, including a real `request_schedule` before the host denial).

**Observed:** an approved agent job has a completed execution. Request a cadence change, yielding `status='requested'`, then deny it before any Space run read. Native ledger retains the execution, but Space `history_count=0` and `last_success_at=null`. Paired control imports history once before the same change/deny: `history_count=1`, last success preserved.

**Required:** disabling/denying future upkeep must not erase discovery of already completed work or make a known success appear never to have happened. Every run remains auditable; removing a schedule is not deleting the Space's history.

**Evidence class:** executed real schedule/store/importer behavior with retained synthetic native execution. No real scheduled run executed.

### F07 — P2: Native execution synchronization permanently omits history beyond its newest 500 entries

**Exact source:** `src/living-spaces/living_spaces_core/runs.py:87-144`, especially `ledger.list_executions(job_id=jid, limit=500)` with no pagination/checkpoint/backfill.

**Reproduction:** `CASE=history_backlog`.

**Observed:** seed **501** completed executions for one approved native job, then call real `runs.list_runs` twice. Full SQLite count (not the UI's page length) is **500**, and `review-exec-1` is absent even though the native ledger retains all 501.

**Required:** synchronizing retained executions must preserve every run, or explicitly implement/disclose an intentional history-retention contract. A display page limit must not silently become a durable import-loss boundary. No such 500-run retention rule is in the reviewed contract.

**Evidence class:** executed importer/store boundary against a synthetic ledger honoring the requested limit; real native ledger retention/population not exercised. This is independent of F06's loss of the old job-discovery pointer.

### F08 — P1: The feed-upkeep HTTPS path bypasses public-address isolation entirely

**Exact source:** `src/living-spaces/living_spaces_core/feeds.py:21-51` checks HTTPS/hostname scope but hands the URL directly to `httpx.Client.stream` without the public-IP validation/pinning in `net.py:130-159`. Feed sources are accepted by `projects.py:95-103`; the Refresh UI calls them public sources.

**Reproduction:** `CASE=feed_private`.

**Observed:** create a feed whose host is `127.0.0.1`, approve its Refresh host scope, and call the real feed fetcher through an HTTPX MockTransport. It issues `https://127.0.0.1:8443/feed` and returns `private fixture content`. Paired mediated-Net address check on that same address returns `blocked/private_address`.

**Required:** a public-source Refresh host approval must not permit loopback/private backend access. That isolation is not a permission users may opt out of in A-01. The feed path must enforce the same public destination boundary, not merely a hostname allowlist. A rebinding hostname is an additional **source-inferred** consequence of the missing check, not an executed DNS exploit here.

**Evidence class:** executed private-target guard omission/request acceptance, not an actual SSRF socket or private-data read. No real loopback service was contacted. This finding concerns the parallel upkeep path; the mediated `net.fetch` literal/DNS checks themselves passed their stock controls.

### F09 — P2: A feed schedule can become active after Refresh was revoked in another process

**Exact source:** `src/living-spaces/living_spaces_core/schedules.py:186-245`: the initial Refresh check is outside the write transaction; the under-lock recheck is conditional on `handler == 'agent'`. `on_refresh_revoked` does not pause a still-requested schedule.

**Reproduction:** `CASE=feed_revoke_race`.

**Observed:** a real subprocess revokes Refresh after the initial feed-approval grant check but before schedule activation. Child exits **0**, prints `refresh revoked in separate process`. Approval nevertheless returns **active**, Refresh is **revoked**, and captured native job is **enabled**. Regrant Refresh without any Resume action: schedule remains **active**.

**Required:** revoke-before-activation must prevent activation or leave the schedule paused. Later regrant must preserve the promised explicit Resume step. The feed's fetch/write grant checks still block its data operations while revoked; the defect is scheduling authority/state and automatic restart after regrant, not a demonstrated data read during revocation.

**Evidence class:** executed separate-process grant transition on real SQLite, with a deterministic synchronization hook at the check boundary and synthetic cron creation. No ticker or actual concurrent native dispatch.

## Source-inferred candidate, not promoted to a runtime finding

**C01 — per-Space overlap across manual and recurring native jobs.** Exact source: `schedules.py:224-236` creates a prompt-based recurring native job that does not pass through `start_refresh`; `runs.py:147-160,163-233` deduplicates manual starts locally, but makes a separate one-shot job. `_sync_agent_runs` imports distinct executions without enforcing one pending run per Space.

Executed supporting probe (original `execution.json`, exit 0):

```sh
env HERMES_HOME=/Volumes/Expansion/Development/Projects/living-spaces-wt/c-review/.run/review/home TMPDIR=/Volumes/Expansion/Development/Projects/living-spaces-wt/c-review/.run/review/tmp PYTHONDONTWRITEBYTECODE=1 /Users/ifedayoakinduro/.hermes/hermes-agent/venv/bin/python -B /Volumes/Expansion/Development/Projects/living-spaces-wt/c-review/.run/review/probe.py overlapping_paths
```

**Observed:** real manual admission plus approved schedule leaves two distinct native jobs enabled. Supplying one synthetic running ledger execution for each makes the real importer persist two running Space runs, triggers `manual` and `schedule`, no cancellation request. **Required:** actual overlapping triggers serialize or safely reconcile, with at most one in-flight Space handler under the declared dedupe contract. **Limit:** supplying native ledger executions is not proving that the real scheduler admits/overlaps them. Actual native scheduling/parallelism policy is outside this seat's allowed execution, so this remains a parent investigation, not a claimed executed native-concurrency defect.

## Dropped hypothesis / failed attempt preserved

**D01 — history loss when replacing a schedule on approval:** original `probe.py history_loss` exited **1** because the predicted defect did not reproduce. Both arms retained one run. Reading `projects.bundle` reaches `_summary` (`projects.py:275-285,436-443`) and synchronizes history before approval replaces the old job. This is an existing guard I initially missed. It is **not a finding**. The distinct deny path in F06 does not read that bundle and reproduced separately, including the requested/deny host workflow. Original stderr and nonzero runner receipt were not overwritten.

Dropped findings count: **one** unproven hypothesis. Source-only open candidates: **one** (C01). No issue cap was applied.

## Positive controls and stock execution

Executed the unmodified stock command, under the runner's private environment:

```sh
/Users/ifedayoakinduro/.hermes/hermes-agent/venv/bin/python -B -m unittest tests.python.test_net tests.python.test_agent_upkeep.AgentUpkeepTests tests.python.test_agent_upkeep.AgentIntegrationSeamTests.test_manifest_hooks_in_integrated_tree tests.python.test_agent_upkeep.AgentIntegrationSeamTests.test_source_owned_adapter_in_integrated_tree tests.python.test_agent_upkeep.AgentIntegrationSeamTests.test_host_approval_snapshot_reaches_core_in_integrated_tree -v
```

**Exit 0, 62 executed / 62 `ok`, zero failures/errors/skips**, reconciled programmatically in final runner. This covers mediated destination classes and legacy literals, mixed DNS, first-answer pinning and hostname TLS, private/downgrade redirects, stripped credentials/framing headers, body/response caps, total/DNS deadlines, truncated HTTP, late result suppression after Net revoke/session close, native agent adapter controls, manifest-change schedule invalidation, prompt snapshot mismatch rejection, and source-owned user-note preservation/atomic batch rollback. These tests use their stock synthetic leaves; they are not native Desktop/network acceptance. Default-on Net and direct-frame-network-off are intentional A-01 decisions and are **not findings**.

## Exit state and handoff

- Final retained-finding replay plus stock tests: exit **0**. Earlier discovery runner: exit **1**, solely the preserved dropped history-replacement hypothesis. All nine reported defects have exact code, executable cases, and observed-versus-required behavior above.
- Final preservation receipt: SHA unchanged; **376/376 tracked bytes and path population match**; all **38/38 shards** and pinned source hashes match; Git status empty. Product/test edits: **none**. All newly created scripts, JSON receipts, stdout/stderr, and this report are under this private tree's `.run/` only.
- Model/cross-family qualification remains as disclosed. No live runtime or release gate is accepted. Parent owns rerunning each reproduction, dispositioning findings, real native/network/Desktop qualification, any repair, and promotion.
