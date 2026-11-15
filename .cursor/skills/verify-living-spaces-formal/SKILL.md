---
name: verify-living-spaces-formal
description: Use when a change touches Living Spaces core (records, bridge, sessions, grants, net, upkeep/Refresh, delete, inspection). Runs the formal checks and their negative controls against real code.
---

# Living Spaces formal verification

Check selected high-risk properties against real `living_spaces_core` code and a bounded Refresh model.
Deliberately broken copies show whether each check can still detect its named regression.

```bash
python3 verification/formal/run.py                       # this tree: checks + negative controls, about 5 min
python3 verification/formal/run.py --only records_integrity --no-controls   # one check, ~12 s
```

Exit 0 means the checks matched their expected baseline, including the unresolved findings listed below, and every
applicable negative control failed with the property it targets. It is not a release approval or a claim that the known-broken
properties hold. Add `--json FILE` for a receipt. Tested with Python 3.13.2 and Java 25.0.2 (stdlib only, no
pip installs); the first run downloads TLA+
tools 1.7.4 into `.fv-tools/` (gitignored) and refuses a jar whose sha256 is not
`936a262061c914694dfd669a543be24573c45d5aa0ff20a8b96b23d01e050e88`. Nothing touches a live profile: every check
runs in a throwaway `HERMES_HOME` under `.fv-tools/scratch/` and fakes Hermes cron and the OS network edges.
Receipts hash the verifier, covered source and skill, and fail if those inputs change during the run.
Only a checkout root receives a Git identity. Scratch copies report `unknown` and retain their source hashes.

## Sync

| Check | Synced at | Evidence level |
|---|---|---|
| refresh_model, refresh_one_shot, refresh_concurrency, records_integrity, bridge_authority, delete_residue, net_boundary | `4aea12db5375b30e90b5e0fa8f7d12ad7e0fdf98` (0.1.1) | see below |
| inspection_readonly | `8008dcc6f77c3f5cb51f966ab1241bd9f89dc37a` (inspection candidate) | prints "not applicable" on trees without `inspection.py` |

`run.py` prints `DRIFT` for every check whose covered files changed since its sync commit. Drift is a prompt to
re-read the cited lines, not a failure; `/maintain-formal-verification-skill` owns bringing a drifted check back.
Move a sync commit forward only after confirming that the check still describes those functions. `--src` changes
the Python code under test, not the TLA+ model. A model run on a candidate still needs this mapping review.

Read every TLA+ result with the pstack `/statechart` skill. It reports the shortest path to each broken invariant
in plain words. Follow that skill's current commands rather than copying commands from an old machine. The model
and flags for each run are in `verification/formal/tla.py`; use the same configuration when drawing its result.

## What each check proves

Evidence levels, strongest first:
- **Exhaustive within bound**: every combination in a stated finite domain, run on the real code.
- **Model-checked (modeled only)**: every reachable state of a TLA+ model whose steps cite code lines; says nothing
  about code the model does not mirror.
- **Generated, real code**: many generated cases on the real code; a pass is strong evidence, not proof.

| Check | Level | Properties | Bound | Runtime |
|---|---|---|---|---|
| `refresh_model` (`verification/formal/refresh/RefreshOneShot.tla`) | Model-checked | AtMostOnce, NoSuccessForSkippedRun, NoFalseRefusal; F1 checked separately | one request and one job; at most one user pause/remove/archive/delete; separate native effects, readbacks, DB recheck and execution/reply; bounded clock and reply types below; 79394 baseline states | 10 s for all configurations |
| `refresh_one_shot` | Generated, real code (exhaustive over its scenario grid) | AtMostOnce, NoSuccessForSkipped, NoFalseRefusal, NoLeftoverOneShot | 2844 scenarios: 3 starts x 3 run outcomes x 4 mid-run events x every set of up to 2 cron refusals | 22 s |
| `refresh_concurrency` | Generated, real code | OneRunAtATime | 3 trigger pairs, both requests inside their native run together | 1 s |
| `records_integrity` | Generated, real code vs reference model | Conflict, RevMonotonic, UserOwned, BatchAtomic, Isolation, Cursor | seeds 0..119 x 30 steps, 2 generated Spaces x 2 collections x 3 ids; separate three-operation numeric stale-revision fixture | 12 s |
| `bridge_authority` | Exhaustive within bound | Authority, NoEffect | 800 cases: 8 grant sets x 5 session kinds x 10 ops x `space` arg spoof | 9 s |
| `delete_residue` | Generated, real code (schema read live) | Gone, Untouched, Fresh | every table with a `space` column; 10 of them populated | <1 s |
| `net_boundary` | Generated, real code (resolver and entire transport faked) | VettedIpArgument, ResolvedIpArgument, PortAllowlist, CredentialsStay | seeds 0..19999: 9 spellings of private/public IPv4, IPv6, mixed DNS answers, up to 4 redirects | 1 s |
| `inspection_readonly` | Exhaustive within bound | ReadOnly, Refused, SameAsLive, Snapshot | 6768 calls: 8 grant sets x spoof x 405 query shapes + get/meta/runs/log/unknown/6 writes | 9 s |

The file and function map for each check is `verification/formal/COVERAGE.json`. The negative controls are in
`verification/formal/mutants.py` (29 on 0.1.1, 34 with inspection) plus the model configurations in `tla.py`.
Each control names the property it must trip. Ambiguous controls also require mechanism signatures. Every TLA+
negative configuration checks its final trace values. The paused-run control starts fresh with no user action,
requires `manualRan=FALSE` and a `skipped` reply. The Python counterpart requires an inline-success scenario with
zero executions. The stale-revision control must accept numeric base revision 1 against current revision 2.
Historical Refresh mechanisms (a)-(c) have model and real-code
controls. The (d) control is a related due-slot failure, not a replay of native dispatch-limit retirement mid-run.
In the Python double, one virtual minute elapses before resume, so an `in 1m` job is eligible then. An `in 2m`
job is outside that timing bound. This is not a proof that all shorter schedules or native retirement modes are safe.

The real-code refresh fault grid injects failures in resume, pause, remove and list calls numbered 1 through 3,
with at most two failures. It does not inject create/run refusal or any consume-phase list failures. It exercises
inline success, inline failure and background dispatch, not forwarded or metadata-free run replies. The product
accepts those other reply types, so this check does not prove they executed or consumed the one-shot.

The TLA+ baseline clocks a fresh job due only after the request returns. The long-run control clocks it due
between execution and reply. Other mid-request elapsed-time delays are omitted. Recurring linked-job scheduler
fires, create/commit failures, lost acknowledgements, process crashes and timeouts are outside the model. A user
lifecycle operation has separate list, mutate, verify, final-list and DB commit steps, but only one job and no
filesystem or DB-commit failures. `AtMostOnce` excludes recurring linked jobs and paths that report cleanup
failure. `ok` for background dispatch means accepted, not completed. These are safety checks, not liveness proofs.
An explicit run refusal while an existing job remains present is also outside the model. TLC action coverage
must reach the user lifecycle, DB recheck and native pause/remove actions. This is a non-vacuity check, not an
independent proof of the lifecycle transaction. After a violation, `/statechart` can hit its 100,000-state rerun
bound. The (d) and long-run reports leave additional rules unchecked. The baseline completes all 79,394 states.

The two `NoFalseRefusal` checks are not identical. TLA+ forbids an explicit run-refused result after a confirmed
successful execution. Python requires a post-execution error to carry the native execution reply and detects
misleading `native_refused` reasons outside F1. The Python scheduler deletes a spent once job, while the model
keeps it disabled. The (d) controls therefore demonstrate related failure classes, not matching native traces.

## Findings at the sync commits

Python checks report these as `known_findings`. Their documented presence is not a new regression. F1's exact
120-scenario set is pinned by a SHA-256 over scenario inputs; any change, including a fix, fails with
`KnownFindingDrift` until the synced baseline is reviewed. Other product fixes can remove their Python findings,
but the source-linked model and its frozen finding expectation still need maintenance before acceptance.

- **F1 Refresh reported refused after it ran.** If Hermes cron refuses the job-list call that verifies a run
  (`upkeep.py:149-155`), `_call` raises `reason="native_refused"` (`upkeep.py:123-125`) and the caller sees
  `blocked (native_refused): Hermes cron list refused` though the run executed. The run reply is attached as
  `native`. Reproduced with an injected public-cron refusal: fresh start, inline run succeeds, list call #3 refuses.
  This demonstrates error reporting under that synthetic fault, not its frequency in a live Hermes session.
  The Python exemption also covers injected native refusals during `_run_now`'s archived/deleted Space recheck
  at `upkeep.py:449-450`. It requires a recorded fault inside `_run_now` and its exact action/call-number message.
  Re-entered user archive/delete faults have their own phases. Consume-phase errors are never exempt. The
  maintained consume-phase refusal control requires all 11 unknown violations, including a delete refusal
  followed by a distinct consume refusal of the same action. A frozen three-case probe also checks that case
  alongside ordinary success and a genuine F1 positive control.
  The TLA+ F1 configuration checks only the run-list verification case, not all Python F1 cases.
- **F2 Deleted file contents stay in the database.** `blobs` is content-addressed and has no `space` column
  (`projects.py:162`); `delete_space` removes revisions but never collects blobs, so the HTML of a deleted Space
  stays in `spaces.db`. The desktop says Delete removes "all its records and revisions permanently"
  (`src/desktop/ui/space.jsx:191`). Severity: privacy and storage.
- **F3 Overlapping agent Refresh requests each run.** `start_refresh` returns `upkeep.refresh_now(...)` for agent
  upkeep at `runs.py:80`, before the one-run-per-Space guard at `runs.py:98-100`. The contract says "a second request
  returns the same run" (`docs/contracts/CONTRACTS.md:190`) and R1-11 says repeated refresh "does not multiply
  effects" (`docs/spec/SPEC.md:76`). Desktop + chat at once gives two one-shots and two model runs; both are
  consumed afterwards in the isolated code probe. The Desktop button's lock (`space.jsx:127`) only covers one view.
  W32 also reproduced Desktop plus native chat in the real app on both exact pins, released
  `4aea12db5375b30e90b5e0fa8f7d12ad7e0fdf98` and candidate `8008dcc6f77c3f5cb51f966ab1241bd9f89dc37a`.
  The evidence root is `/Volumes/Expansion/Development/Build/living-spaces-app-verification-evidence/`.
  `baseline-desktop-chat-race-01/race-result.json` records one-shots `2a5836e07588` and `e34e9cd534f2`.
  `candidate-desktop-chat-race-01/race-result.json` records one-shots `c84fbfee5685` and `a368e04ab02d`.
  Each run has two overlapping `source=cron` sessions with API calls and `cron_complete`, and a chat
  `spaces_refresh` call inside the first session's runtime window. The corresponding `race-actions.json`
  files record Desktop before chat. This is a pre-existing shipped-release bug, not a candidate regression.
  W32 executed the real-app runs; W31 read back the receipts. Both Space runs tables stayed empty, so the
  evidence proves duplicate dispatch and model work, not duplicate Space run rows or a W31 live execution.

Supplemental finding **F4 Feed-size limits disagree** is not part of the formal suite. The parser accepts 501,
999 and 1000 entries, but `feeds.refresh_source` then rejects the batch with `source entries exceeds 500`, storing
zero records. 499 and 500 succeed; 1001 fails at the parser. Reproduce on an isolated database with
`python3 verification/formal/probes/feed_limit.py --src .`. The parser/ingest mismatch is at `feeds.py:82-83,131`
and `records.py:199-205` at 4aea12d. This is not a partial-write finding or a parser proof.

Residual by design: a native run longer than the 7-day one-shot slot can be claimed again (`upkeep.py:19-23`); the
model shows it under `residual-run-outlasts-slot`.

## Not covered

- Browser and sandbox: the iframe sandbox, CSP, `space-host.html`, postMessage routing, and the inspection Chromium
  runner, DevTools pipe, redaction and network blocking. The companion skill `verify-living-spaces` drives the real app.
- `net.fetch` and `bot.request` through the bridge (they need a network or native adapter); `net_boundary` covers
  `net._fetch_public` directly. Real DNS, the entire `_PinnedHTTPS` transport, TLS, SNI and Hermes cron are faked.
  The network check verifies arguments passed to the transport and redirect headers, not actual socket pinning
  or certificate validation.
- Canvas actions (`actions.py`), maintainers, `action_intents`/`action_keys` beyond the delete scan.
- Multi-process concurrency. Refresh overlap uses two threads, not two processes. SQLite locking is trusted.
- Profile isolation, Desktop backend switching, and REST/RPC management authorization. The authority checks use
  two Spaces in one isolated database. They do not prove separation between Hermes profiles. `LIVING_SPACES_DB`
  can explicitly make profiles share a database, and `owner` is a display label rather than bot authorization.
- Data migrations, file-reference import containment, concurrent grant/session revocation, and delete/recreate
  ABA races. Recovery-point restore is exercised, but that does not establish migration correctness.
- `harness/app.py` (the release test harness): `prepare` enables a model plugin, `enable-desktop` writes Desktop
  localStorage and `stop` stops the gateway. Never run it as part of this skill.

## Following this skill on a change

1. Run `python3 verification/formal/run.py`. Note any `DRIFT` lines.
2. A `BAD` check line normally means a property your change broke: the line quotes the steps and stored state.
   Fix the code, not the check, unless the documented behavior changed on purpose. `KnownFindingDrift` instead
   means F1's pinned scenario set changed. Investigate it, including a genuine F1 fix, before updating that pin
   and the source-linked model through `/maintain-formal-verification-skill`.
3. A `BAD control` line means a check can no longer see the break it guards, or the mutant text no longer matches
   (the code moved). Update the mutant's text in `mutants.py` to the new code; never delete a control to go green.
   Fix any baseline `BAD` check first. A real bug can make other controls fail for the wrong reason, even when
   those controls themselves remain sound.
4. For a new property, add a check under `verification/formal/checks/` using `harness.main`, a mutant that breaks
   it, and its row in `COVERAGE.json` with the commit you synced to.
