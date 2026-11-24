---
name: verify-living-spaces-formal
description: Use when a change touches Living Spaces core (records, bridge, sessions, grants, net, upkeep/Refresh, delete, inspection). Runs the formal checks and their negative controls against real code.
---

# Living Spaces formal verification

Check selected high-risk properties against real `living_spaces_core` code and a bounded Refresh model.
Deliberately broken copies show whether each check can still detect its named regression.

```bash
python3 verification/formal/run.py                       # this tree: checks + negative controls, about 20 min
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
| all eight checks | `92486e1a36594bb37d152a031f07cccd24950f0f` (main after PRs #6-#9) | see below |

`inspection_readonly` still prints "not applicable" on a tree without `inspection.py`. The previous syncs were
`4aea12d` (0.1.1) and `8008dcc` (inspection candidate).

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
| `refresh_model` (`verification/formal/refresh/RefreshOneShot.tla`) | Model-checked | AtMostOnce, NoSuccessForSkippedRun, NoFalseRefusal, NoRefusalAfterSuccessfulRun | one request and one job; at most one user pause/remove/archive/delete; refresh and user SQLite writers serialized; separate native effects, readbacks, receipt write, read-only fence, verification list and execution/reply; remove/delete retire the claim; bounded clock and reply types below; 49674 baseline states | about 20 s for all configurations |
| `refresh_one_shot` | Generated, real code (exhaustive over its scenario grid) | AtMostOnce, NoSuccessForSkipped, NoFalseRefusal, NoLeftoverOneShot | 4266 scenarios: 3 starts x 3 run outcomes x 5 mid-run events (nothing, archive, delete, Upkeep remove, Upkeep pause) and post-run DB failure x every set of up to 2 cron refusals | about 110 s |
| `refresh_concurrency` | Generated, real code | OneRunAtATime | 3 trigger pairs, both requests inside their native run together | 10 s |
| `records_integrity` | Generated, real code vs reference model | Conflict, RevMonotonic, UserOwned, BatchAtomic, Isolation, Cursor | seeds 0..119 x 30 steps, 2 generated Spaces x 2 collections x 3 ids; separate three-operation numeric stale-revision fixture | 12 s |
| `bridge_authority` | Exhaustive within bound | Authority, NoEffect | 800 cases: 8 grant sets x 5 session kinds x 10 ops x `space` arg spoof | 9 s |
| `delete_residue` | Generated, real code (schema read live) | Gone, Untouched, Fresh, Blobs | every table with a `space` column; 12 of them populated; retained `maintenance_operations` history must be retired and belong to the deleted incarnation | <1 s |
| `net_boundary` | Generated, real code (resolver and entire transport faked) | VettedIpArgument, ResolvedIpArgument, PortAllowlist, CredentialsStay | seeds 0..19999: 9 spellings of private/public IPv4, IPv6, mixed DNS answers, up to 4 redirects | 1 s |
| `inspection_readonly` | Exhaustive within bound | ReadOnly, Refused, SameAsLive, Snapshot | 6768 calls: 8 grant sets x spoof x 405 query shapes + get/meta/runs/log/unknown/6 writes | 25 s |

The file and function map for each check is `verification/formal/COVERAGE.json`. The negative controls are in
`verification/formal/mutants.py` (41 with the F4/F5 controls) plus the model configurations in `tla.py`.
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
lifecycle operation has separate list, mutate, verify, final-list and DB commit steps inside one writer
(`maintenance.control` + `transaction`), but only one job and no filesystem or DB-commit failures. Upkeep remove
and Space delete retire the refresh claim in that commit; the refresh then fails its next fence with
`refresh_claim_lost`/`not_found` and does no cleanup. Joined followers, orphan discovery and `unresolved` replies
are outside the model. `AtMostOnce` excludes recurring linked jobs and paths that report cleanup
failure. `ok` for background dispatch means accepted, not completed. These are safety checks, not liveness proofs.
An explicit run refusal while an existing job remains present is also outside the model. TLC action coverage
must reach the user lifecycle, receipt, fence, archive recheck, consume and native pause/remove actions. This is a non-vacuity check, not an
independent proof of the lifecycle transaction. After a violation, `/statechart` can hit its 100,000-state rerun
bound. The (d) and long-run reports leave additional rules unchecked. The baseline completes all 49,674 states.

The two `NoFalseRefusal` checks are not identical. TLA+ forbids an explicit run-refused result after a confirmed
successful execution, and `NoRefusalAfterSuccessfulRun` forbids a refused verification list being reported as a
refusal. Python requires a post-execution error to carry the native execution reply and never say
`native_refused`. The Python scheduler deletes a spent once job, while the model
keeps it disabled. The (d) controls therefore demonstrate related failure classes, not matching native traces.

## Findings at the sync commit

No findings are open. Python checks can still report open findings as `known_findings`; a documented one is not a
new regression, and its exact case set must be pinned so that any change, including a fix, is noticed.

Fixed, now hard properties with regression controls:
- **F4** (inspection replies lacked the live `outcome` envelope, from `10517b9`): `PassiveAdapter.call` returns
  `outcome: {status: success|rejected}` like `bridge.dispatch`; control `inspect-F4-envelope-dropped`.
- **F5** (live `not_granted` redacted to "Operation could not be completed" without `capability`, from
  `10517b9`): `bridge._delivery_failure` substitutes the authority error itself, so it keeps the detail
  `docs/contracts/CONTRACTS.md` promises; control `inspect-F5-redaction-change-noticed`, and
  `inspect-F5-wrong-adapter-error-not-excused` keeps the adapter's side to the contract. Tests in
  `tests/python/test_bridge_reply_contract.py`.
- **F1** (Refresh reported refused after it ran): `b57f3cc`/`f56321d` raise `post_run_check_failed` with the run
  reply (`upkeep.py:607-609`); controls `refresh-verify-refusal-reported-as-refused` and
  `f1-verify-refusal-reported-as-refused`.
- **F2** (deleted file contents kept): `bfc0e09` deletes blobs only the deleted Space referenced
  (`projects.py:610-616`); control `delete-keeps-unique-blobs`.
- **F3** (overlapping agent Refresh requests each run): `maintenance.acquire` admits one claim per Space and
  `join` returns the saved reply (`maintenance.py:313-338`); control `refresh-each-request-runs-twice`.

The supplemental feed-size probe (`verification/formal/probes/feed_limit.py`, formerly listed as F4) is not part
of the suite and was not re-run at this sync.

Residual by design: a native run longer than the 7-day one-shot slot can be claimed again
(`docs/architecture/F3-MAINTENANCE-COORDINATION.md`, "Limits"); the model shows it under `residual-run-outlasts-slot`.

Retained by design: `maintenance_operations` rows survive `delete_space` so an old reply can still belong to its
operation (same document). `delete_residue` requires them to be retired history of the deleted incarnation.

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
- Desktop-only state: Space snapshots (`src/desktop/ui/snapshots.mjs`: capture on leave, cap 24,
  replace-on-capture, stale-leave guard), notice dismissal per activation and passive-poll non-reopen, and the
  storage warning rules from #7. None of them write a guarded core table; they are covered by JS unit tests only.
- `bridge_receipts`/`editor_drafts` and `editor.save`/`outcome.get` reconciliation (10517b9): scanned by
  `delete_residue`, but no property covers replay or reconciliation.
- Data migrations, file-reference import containment, concurrent grant/session revocation, and delete/recreate
  ABA races. Recovery-point restore is exercised, but that does not establish migration correctness.
- `harness/app.py` (the release test harness): `prepare` enables a model plugin, `enable-desktop` writes Desktop
  localStorage and `stop` stops the gateway. Never run it as part of this skill.

## Following this skill on a change

1. Run `python3 verification/formal/run.py`. Note any `DRIFT` lines.
2. A `BAD` check line normally means a property your change broke: the line quotes the steps and stored state.
   Fix the code, not the check, unless the documented behavior changed on purpose. `KnownFindingDrift` instead
   means a pinned finding set changed (none is pinned today). Investigate it, including a genuine fix, before updating that
   pin and the source-linked model through `/maintain-formal-verification-skill`.
3. A `BAD control` line means a check can no longer see the break it guards, or the mutant text no longer matches
   (the code moved). Update the mutant's text in `mutants.py` to the new code; never delete a control to go green.
   Fix any baseline `BAD` check first. A real bug can make other controls fail for the wrong reason, even when
   those controls themselves remain sound.
4. For a new property, add a check under `verification/formal/checks/` using `harness.main`, a mutant that breaks
   it, and its row in `COVERAGE.json` with the commit you synced to.
