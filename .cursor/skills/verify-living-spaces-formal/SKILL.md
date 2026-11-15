---
name: verify-living-spaces-formal
description: Use when a change touches Living Spaces core (records, bridge, sessions, grants, net, upkeep/Refresh, delete, inspection). Runs the formal checks and their negative controls against real code.
---

# Living Spaces formal verification

One command checks the properties that keep Spaces safe and correct, against the real `living_spaces_core` code, and
proves each check can still fail by running it on deliberately broken copies.

```bash
python3 verification/formal/run.py                       # this tree: checks + negative controls, ~3 min
python3 verification/formal/run.py --src /path/to/tree   # any checkout with the same layout (read only)
python3 verification/formal/run.py --only records_integrity --no-controls   # one check, ~12 s
```

Exit 0 means every check passed (known findings are listed, not hidden) and every negative control failed with the
property it targets. Add `--json FILE` for a receipt. Tested with Python 3.13.2 and Java 25.0.2 (stdlib only, no
pip installs); the first run downloads TLA+
tools 1.7.4 into `.fv-tools/` (gitignored) and refuses a jar whose sha256 is not
`936a262061c914694dfd669a543be24573c45d5aa0ff20a8b96b23d01e050e88`. Nothing touches a live profile: every check
runs in a throwaway `HERMES_HOME` under `.fv-tools/scratch/` and fakes Hermes cron and the OS network edges.

## Sync

| Check | Synced at | Evidence level |
|---|---|---|
| refresh_model, refresh_one_shot, refresh_concurrency, records_integrity, bridge_authority, delete_residue, net_boundary | `4aea12db5375b30e90b5e0fa8f7d12ad7e0fdf98` (0.1.1) | see below |
| inspection_readonly | `8008dcc6f77c3f5cb51f966ab1241bd9f89dc37a` (inspection candidate) | prints "not applicable" on trees without `inspection.py` |

`run.py` prints `DRIFT` for every check whose covered files changed since its sync commit. Drift is a prompt to
re-read the cited lines, not a failure; `/maintain-formal-verification-skill` owns bringing a drifted check back.

## What each check proves

Evidence levels, strongest first:
- **Exhaustive within bound**: every combination in a stated finite domain, run on the real code.
- **Model-checked (modeled only)**: every reachable state of a TLA+ model whose steps cite code lines; says nothing
  about code the model does not mirror.
- **Generated, real code**: many generated cases on the real code; a pass is strong evidence, not proof.

| Check | Level | Properties | Bound | Runtime |
|---|---|---|---|---|
| `refresh_model` (`verification/formal/refresh/RefreshOneShot.tla`) | Model-checked | AtMostOnce, NoSuccessForSkippedRun, NoFalseRefusal | one Refresh now; one user pause/remove/archive/delete at any point; any cron refusal; one post-run DB failure; every interleaving with the scheduler; 4286 states | 2 s |
| `refresh_one_shot` | Generated, real code (exhaustive over its scenario grid) | AtMostOnce, NoSuccessForSkipped, NoFalseRefusal, NoLeftoverOneShot | 2844 scenarios: 3 starts x 3 run outcomes x 4 mid-run events x every set of up to 2 cron refusals | 22 s |
| `refresh_concurrency` | Generated, real code | OneRunAtATime | 3 trigger pairs, both requests inside their native run together | 1 s |
| `records_integrity` | Generated, real code vs reference model | Conflict, RevMonotonic, UserOwned, BatchAtomic, Isolation, Cursor | seeds 0..119 x 30 steps, 2 Spaces x 2 collections x 3 ids | 12 s |
| `bridge_authority` | Exhaustive within bound | Authority, NoEffect | 800 cases: 8 grant sets x 5 session kinds x 10 ops x `space` arg spoof | 9 s |
| `delete_residue` | Generated, real code (schema read live) | Gone, Untouched, Fresh | every table with a `space` column; 10 of them populated | <1 s |
| `net_boundary` | Generated, real code (resolver + socket faked) | NoPrivateConnect, Pinned, HttpsOnly, CredentialsStay | seeds 0..19999: 9 spellings of private/public IPv4, IPv6, mixed DNS answers, up to 4 redirects | 1 s |
| `inspection_readonly` | Exhaustive within bound | ReadOnly, Refused, SameAsLive, Snapshot | 6768 calls: 8 grant sets x spoof x 405 query shapes + get/meta/runs/log/unknown/6 writes | 9 s |

The file and function map for each check is `verification/formal/COVERAGE.json`. The negative controls are in
`verification/formal/mutants.py` (18 on 0.1.1, 22 with inspection) plus the 8 broken TLA+ variants in `tla.py`.
Each control names the property it must trip; historical Refresh defects (a)-(d) are controls in both the model and
the real-code check.

## Findings at the sync commits

Reported by the checks as `known_findings`; they do not fail the run. A fix makes them disappear from the output.

- **F1 Refresh reported refused after it ran.** If Hermes cron refuses the job-list call that verifies a run
  (`upkeep.py:149-155`), `_call` raises `reason="native_refused"` (`upkeep.py:123-125`) and the caller sees
  `blocked (native_refused): Hermes cron list refused` though the run executed. The run reply is attached as
  `native`. Example: fresh start, inline run succeeds, list call #3 refused. Severity: wrong message, no extra run.
- **F2 Deleted file contents stay in the database.** `blobs` is content-addressed and has no `space` column
  (`projects.py:162`); `delete_space` removes revisions but never collects blobs, so the HTML of a deleted Space
  stays in `spaces.db`. The desktop says Delete removes "all its records and revisions permanently"
  (`src/desktop/ui/space.jsx:191`). Severity: privacy and storage.
- **F3 Overlapping agent Refresh requests each run.** `start_refresh` returns `upkeep.refresh_now(...)` for agent
  upkeep at `runs.py:80`, before the one-run-per-Space guard at `runs.py:98-100`. The contract says "a second request
  returns the same run" (`docs/contracts/CONTRACTS.md:190`) and R1-11 says repeated refresh "does not multiply
  effects" (`docs/spec/SPEC.md:76`). Desktop + chat at once gives two one-shots and two model runs; both are
  consumed afterwards. The Desktop button's lock (`space.jsx:127`) only covers one view.

Residual by design: a native run longer than the 7-day one-shot slot can be claimed again (`upkeep.py:19-23`); the
model shows it under `residual-run-outlasts-slot`.

## Not covered

- Browser and sandbox: the iframe sandbox, CSP, `space-host.html`, postMessage routing, and the inspection Chromium
  runner, DevTools pipe, redaction and network blocking. The companion skill `verify-living-spaces` drives the real app.
- `net.fetch` and `bot.request` through the bridge (they need a network or native adapter); `net_boundary` covers
  `net._fetch_public` directly. Real DNS, TLS and Hermes cron are faked.
- Canvas actions (`actions.py`), maintainers, `action_intents`/`action_keys` beyond the delete scan.
- Multi-process concurrency except Refresh overlap; SQLite locking is trusted.
- `harness/app.py` (the release test harness): `prepare` enables a model plugin, `enable-desktop` writes Desktop
  localStorage and `stop` stops the gateway. Never run it as part of this skill.

## Following this skill on a change

1. Run `python3 verification/formal/run.py`. Note any `DRIFT` lines.
2. A `BAD` check line is a property your change broke: the line quotes the steps and stored state. Fix the code,
   not the check, unless the documented behavior changed on purpose.
3. A `BAD control` line means a check can no longer see the break it guards, or the mutant text no longer matches
   (the code moved). Update the mutant's text in `mutants.py` to the new code; never delete a control to go green.
4. For a new property, add a check under `verification/formal/checks/` using `harness.main`, a mutant that breaks
   it, and its row in `COVERAGE.json` with the commit you synced to.
