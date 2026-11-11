# Lane w2-schedule report

Living Spaces must show when upkeep catches up after downtime, stop scheduled work when Refresh is denied or revoked, and leave no harness-created cron jobs behind. The core fixes and offline harness are ready for Forge's integration and real-Desktop run.

**Verdict: ISSUES.** Local checks pass. Host copy changes and real gateway qualification remain open. The sandbox also prevents staging and committing.

## Changes

- `src/living-spaces/living_spaces_core/schedules.py` exposes native `last_dispatch`, reads current dispatch metadata for run creation, pauses on refresh denial/revocation, persists a visible pause reason in the existing audit table, and requires a Refresh grant before approval or explicit resume.
- `src/living-spaces/living_spaces_core/runs.py` snapshots dispatch metadata into `Run.detail.dispatch` for scheduled runs. Completion preserves it on success or failure. Manual refreshes and already-completed native dispatches do not inherit an old catch-up label.
- `src/living-spaces/living_spaces_core/grants.py` changes only the refresh revoke/deny hook. Cancellation and schedule pause have independent lazy imports, preserving the existing core-only seam.
- `tests/python/test_upkeep_runs.py` adds four behavior tests. The existing local HTTP listener fixture now uses `httpx.MockTransport`, preserving provenance/timestamp assertions without network access.
- `harness/qualify_schedule_offline.py` implements `prepare-offline`, `verify-catchup`, `revoke`, and `cleanup`.
- `LANE_REPORT.md` records the handoff.

No schema migration, run-status enum, cron policy, or cron shim change was needed. No host UI, frozen contracts, guest producer, or Miro-owned file was edited.

The Model the Domain principle shaped the implementation. Native dispatch timing remains a single metadata object in the existing run detail, and revocation uses the existing paused state rather than adding parallel status flags.

## Native cron findings

Read-only source inspection used the installed Hermes checkout under `~/.hermes/hermes-agent`.

- `cron/jobs.py::_compute_grace_seconds` uses half the cadence, clamped to 120–7200 seconds. Explicit `grace_minutes` overrides it but still has a 120-second ticker tolerance floor.
- `_classify_dispatch_lateness` returns `catch_up` beyond grace, otherwise `late` beyond 300 seconds, otherwise `on_time`. The beyond-grace condition takes precedence.
- `_evaluate_due_job` calls `cron/missed_runs.py::fast_forward_missed_recurring`. An explicit `catch_up=True` takes precedence over the global/default and grace-based skip policy. It advances the next eligible slot into the future and dispatches once. It does not replay every missed interval.
- Collapsed missed slots are booked in the native execution ledger. The native job persists `last_dispatch = {scheduled_at, dispatched_at, lateness_seconds, kind}` before the shim executes.
- Native completion records `last_status` as `ok` or `error` for these local no-agent jobs. Successful catch-up is still `ok`; its lateness is in `last_dispatch`, not a separate completion status. Empty shim output is silent success.
- `pause_job` sets `enabled=False`, `state='paused'`, and `paused_reason`. Native resume can retain an overdue occurrence for catch-up. Regranting Refresh must therefore leave the job paused until an explicit user resume.

Before this change, Living Spaces discarded dispatch metadata and showed an ordinary scheduled success after catch-up. The native policy was correct, but the host could not distinguish a catch-up run. Deny/revoke canceled pending refresh work but left native cron enabled. Its subsequent dispatches could continue creating blocked runs.

## Red and green evidence

Logs are retained locally in `.run/` and are not committed.

### Catch-up metadata and revoke pause

Run before the product fixes:

```sh
~/.hermes/hermes-agent/venv/bin/python -m unittest \
  tests.python.test_upkeep_runs.ScheduleTests.test_catchup_dispatch_survives_in_run_history \
  tests.python.test_upkeep_runs.ScheduleTests.test_failed_catchup_keeps_dispatch_and_last_good_data \
  tests.python.test_upkeep_runs.ScheduleTests.test_refresh_decisions_pause_native_job_until_explicit_resume
```

Red, `.run/w2-red.log`: **3 tests, 4 failures**. Both run tests observed missing dispatch metadata. The deny and revoke subcases both observed native `('scheduled', True)` instead of `('paused', False)`.

Green, `.run/w2-green.log`: **3 tests passed**. The native cron store and due scan operate only inside a temporary worktree `.run/` home. The catch-up test observes one due job after three missed days, completes it, and observes no second due job. It verifies durable run metadata after native completion. The revoke test verifies cancellation, native pause, no due dispatch, persistent reason, no automatic resume on regrant, and explicit resume.

### Approval and resume guard

```sh
~/.hermes/hermes-agent/venv/bin/python -m unittest \
  tests.python.test_upkeep_runs.ScheduleTests.test_approval_and_resume_require_refresh_permission
```

The two newly added grant checks were temporarily removed for red, then restored before green. No other behavior was changed during that experiment.

Red, `.run/w2-permission-red.log`: **1 test, 2 failing subcases**, both `SpacesError not raised`. Green, `.run/w2-permission-green.log`: **1 test passed**. An initial version of this test also had a test-context error after its expected failure; that assertion placement was corrected before the recorded final red/green pair.

Final combined focused command was the three-test command above plus `tests.python.test_upkeep_runs.ScheduleTests.test_approval_and_resume_require_refresh_permission`. Result, `.run/w2-targeted-final.log`: **4 tests passed**.

## Repository verification

```sh
~/.hermes/hermes-agent/venv/bin/python -m unittest discover -s tests/python -t .
```

Final result, `.run/w2-python-final.log`: **155 tests passed, 0 failed, 0 skipped**. All test homes and databases are temporary directories under this worktree's `.run/`.

An intermediate full run had **154 tests, 1 failure, 1 skip**. The failure exposed a coupled lazy import that prevented the old cancellation seam from firing when schedules were unavailable. Independent imports fixed it. The skip was the pre-existing local HTTP fixture's refused listener bind; replacing that fixture with an in-memory HTTP transport removed the listener attempt from the final suite. A subsequent intermediate run passed all 154 tests before the final guard test was added.

The literal requested JS globs could not start because `tests/js/ui/*.test.mjs` does not exist. The UI suite is `render-smoke.mjs`. The first adjusted run had **63 passes / 67 tests**, with missing vendor resolution, renderer metafile, and VM-module support. Adding the import hook and metafile produced **82 passes / 83 tests**; the remaining failure was `node:vm` not exporting `SourceTextModule` without its flag. The final commands were:

```sh
mkdir -p .run/package
esbuild src/desktop/plugin.src.js --bundle --format=esm --jsx=automatic \
  --external:@hermes/plugin-sdk --external:react --external:react/jsx-runtime \
  --outfile=.run/package/plugin.js --metafile=.run/package/desktop-metafile.json
node --experimental-vm-modules --import ./tests/js/sandbox/env.mjs --test \
  tests/js/sandbox/*.test.mjs tests/js/reference/*.test.mjs
node tests/js/ui/render-smoke.mjs
~/.hermes/hermes-agent/venv/bin/python -m py_compile harness/qualify_schedule_offline.py
git diff --check
```

Results:

- JS unit suites, `.run/w2-js-final.log`: **101 tests passed, 0 failed, 0 skipped**.
- UI render suite, `.run/w2-ui.log`: **40 assertions passed**, 12 static HTML fixtures. No browser was started.
- Harness compile: **1 file passed**. This is syntax validation, not harness acceptance.
- Whitespace check: passed.

The plugin admission validator was also run without installing dependencies. Exact Python invocation:

```sh
~/.hermes/hermes-agent/venv/bin/python - <<'PY'
import json
import os
from pathlib import Path
import sys
import tempfile
root = Path.cwd()
with tempfile.TemporaryDirectory(prefix='w2-validator-', dir=root / '.run') as scratch:
    os.environ['HERMES_HOME'] = scratch
    os.environ['LIVING_SPACES_DB'] = str(Path(scratch) / 'spaces.db')
    tempfile.tempdir = scratch
    sys.path.insert(0, str(Path.home() / '.hermes/hermes-agent'))
    from hermes_cli.plugin_validate import validate_plugin_dir
    result = validate_plugin_dir(root / 'src/living-spaces')
    Path('.run/w2-validator.json').write_text(json.dumps(result.to_dict(), indent=2))
    print(json.dumps(result.to_dict(), indent=2))
    raise SystemExit(result.exit_code)
PY
```

Result, `.run/w2-validator.json`: **16 checks passed, exit 0, 1 warning**. The warning is the existing private `cron.jobs` import under catalog rule 9. No package installation or live-profile write was performed.

## Forge-only harness handoff

**Written and compiled, never executed.** No Desktop, Chrome, gateway, ticker process, or network listener was started, stopped, or restarted by this lane. Unit tests use native cron APIs against temporary stores, not a running scheduler.

Prerequisites:

1. Integrate this lane and the host copy changes below into the plugin checkout used by the isolated app.
2. The existing isolated `research-desk` must contain the proven public-feed upkeep configuration and at least one source-owned record with a title per collection. The harness copies that configuration and public source metadata into a separate `Offline Catchup Probe` Space. It creates fresh synthetic user notes and never copies user data from Research Desk.
3. Use the same isolated root for `harness/app.py` and this harness. Their default root matches the existing schedule qualification. `LS_RUN_ROOT` and `LS_CDP_PORT` can select Forge's isolated instance.

Run these commands separately from the integrated repository. Forge owns the stop/start operations:

```sh
~/.hermes/hermes-agent/venv/bin/python harness/app.py stop
~/.hermes/hermes-agent/venv/bin/python harness/qualify_schedule_offline.py prepare-offline
~/.hermes/hermes-agent/venv/bin/python harness/app.py start
~/.hermes/hermes-agent/venv/bin/python harness/qualify_schedule_offline.py verify-catchup
~/.hermes/hermes-agent/venv/bin/python harness/qualify_schedule_offline.py revoke
~/.hermes/hermes-agent/venv/bin/python harness/qualify_schedule_offline.py cleanup
```

Run `cleanup` even if verification fails. A host-copy failure in `verify-catchup` still saves the canonical catch-up observation so Forge can exercise `revoke` independently. Reports and screenshots go under the isolated root's `evidence/schedule-offline/`; reports use unique attempt timestamps.

`prepare-offline` refuses a live-profile root and refuses a running isolated gateway/held runtime lock. It creates a no-agent schedule and moves its `next_run_at` three daily slots into the past through `cron.jobs.update_job`, with `grace_minutes=2` and `catch_up=True`. The normal next slot is about 30 minutes ahead, leaving time to observe catch-up without confusing it with an ordinary scheduled run. Complete verification promptly after preparation.

`verify-catchup` waits for the gateway's real ticker, then observes at least 130 seconds and two successful executions of a separate minute-cadence ticker witness. It requires exactly one Space catch-up run, successful source updates, native/run dispatch agreement, preserved user notes, future next slot, and truthful host History text.

`revoke` presses the host Permissions Refresh Revoke control and confirmation using native CDP mouse events. It requires native paused/disabled state, a reason, null eligible next run, and no additional scheduled runs across another two witnessed ticker intervals. It moves the paused job's next slot into the past to ensure the non-execution assertion is meaningful. It also requires the host Schedule sheet to explain revocation and deliberate recovery. Focus emulation keeps polling active in the occluded isolated window, matching the earlier harness pattern.

`cleanup` deletes the fixture schedule, both harness-created native jobs, and both shims. It verifies no matching created job remains in the native store, no shim remains, and user records are preserved. The fixture Space and run history remain inspectable. Other Living Spaces jobs are listed in the cleanup report and are not deleted.

## Contract issues and host work

**Proposed amendment A4, for Forge to review and apply.** Do not change the frozen file in this lane.

- Extend the lazy upkeep seam with `schedules.on_refresh_revoked(sid, decision, *, actor)`. Refresh deny/revoke calls it independently of `runs.cancel_pending(sid, "refresh revoked")`.
- Pausing carries a reason, surfaced as optional `Schedule.reason`, backed by native `paused_reason` and the existing `schedule.paused` audit record. No new database column is required for this implementation.
- Add optional `Schedule.last_dispatch` and `Run.detail.dispatch`, each carrying native `{scheduled_at, dispatched_at, lateness_seconds, kind}`. Native timestamps are ISO strings. `kind` is `on_time`, `late`, or `catch_up`. Run completion statuses and the `schedule` trigger remain unchanged.
- Approving or resuming a schedule requires the Refresh grant and can return the existing `not_granted` error. Regranting alone does not resume anything.

Proven host gaps, outside this lane's ownership:

1. `src/desktop/ui/history.jsx::RunRow` and `model.mjs::runResult` ignore dispatch metadata. Show “Catch-up refresh” for `catch_up`, the missed scheduled time and actual dispatch time, and “Missed intervals were not replayed.” Show delayed timing for `late`. A failed catch-up must still say failed and retain last-good freshness.
2. `src/desktop/ui/schedule.jsx` ignores `schedule.reason` and `last_dispatch`. Render the pause reason, latest catch-up/delayed timing, and a recovery instruction such as “Refresh permission revoked. Approve Refresh in Permissions, then resume upkeep.” When an active `next_run_at` is overdue, call it delayed/awaiting Hermes rather than implying continuous service. Do not call every small ticker delay a catch-up; use native classification once dispatched.
3. The Refresh revoke dialog currently promises “Scheduled and manual refreshes stop and show Blocked.” Update it to explain that scheduled upkeep pauses and Refresh must be approved before an explicit resume. No fabricated blocked run is inserted when there was no attempted run.

Both UI-text harness assertions intentionally remain release gates. They will fail on the current unmodified host. Existing native integration and private import availability must be verified by Forge's real app run; local tests are not that evidence.

The earlier R1-07 Research Desk job and any other pre-existing test jobs remain Forge's release-end cleanup responsibility. This harness reports them but only deletes resources it created.

## Git handoff and remaining work

Attempted after passing tests:

```sh
git diff --check
git add src/living-spaces/living_spaces_core/schedules.py \
  src/living-spaces/living_spaces_core/runs.py \
  src/living-spaces/living_spaces_core/grants.py tests/python/test_upkeep_runs.py
git commit -m 'Preserve catch-up timing and pause upkeep when refresh is revoked'
```

`git add` failed before commit could run:

```text
fatal: Unable to create '<main-repo>/.git/worktrees/w2-schedule/index.lock': Operation not permitted
```

Thus changes could not even be staged. They remain in the worktree, including this report. No push was attempted. Forge must stage and commit the product/test change, then the harness/report, outside this sandbox.

Not done: real offline/restart/catch-up qualification; real native-input revocation qualification; host copy changes; deletion of live isolated test jobs; acceptance ledger updates; commits. R1-07 must remain partial until Forge records the actual harness outcomes and final cleanup.
