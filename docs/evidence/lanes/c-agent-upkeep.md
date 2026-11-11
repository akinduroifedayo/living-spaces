# c-agent-upkeep lane report

Ife needs Living Spaces upkeep to run a normal Hermes agent, so living apps can
maintain more than RSS/Atom feeds. This lane adds native agent jobs, preserves
feed jobs, and supplies integration patches for files owned by other lanes.

**Verdict: ISSUES.** Offline implementation and tests pass. Forge must integrate
four patches, rebuild/install, and execute the real Desktop harness. Git staging
is sandbox-blocked; no commit or push was created. No real model run, Desktop,
gateway, Chrome, scheduler service, network listener or package install was run.

## Files changed

- `src/living-spaces/living_spaces_core/schedules.py` validates `feed|agent` and a
  nonblank agent prompt of at most 4000 characters. Agent approval creates a native
  prompt job with `no_agent=False`, `deliver="local"`, `catch_up=True` and the
  requested timezone. No model/provider, skills or toolset override is imposed.
  Feed approval retains the existing no-agent script. The native prompt names
  the Space id, requires `spaces_*` for Space access, preserves user fields,
  checks archive/Refresh status, and requests source-owned writes.
- The same module provides a revision hook that pauses the old native job and
  returns the schedule to `requested` on handler or prompt changes, including
  restore. An optional `requested_upkeep` approval snapshot rejects a prompt
  different from what the host displayed. Refresh grants and the current
  manifest are checked again under the SQLite write lock before agent approval.
- `src/living-spaces/living_spaces_core/runs.py` creates an independently paused
  native one-shot job (`schedule="in 1m"`, `repeat=1`) and calls native
  `trigger_job` once for Refresh now. This keeps manual work independent of
  recurring schedule pause/resume. Concurrent requests dedupe against one Space
  run, including an already observed running scheduled job. Native execution
  records supply queued/running/succeeded/failed/canceled states and job/run ids
  in `detail.cron_job_id` and `detail.cron_run_id`. Agent jobs do not expire under
  the feed worker's 120-second heartbeat timeout. Missing jobs and enqueue errors
  become failed runs. Terminal one-shots are removed after reconciliation.
- Agent cancellation removes one-shots or pauses and requests native interruption
  of recurring agent work. Existing archive/delete/revoke hooks apply. Scheduled
  entry through a legacy feed shim cannot invoke an unapproved new agent prompt.
- `src/desktop/ui/schedule.jsx` shares `UpkeepCost`, rendering “Uses model calls”
  and escaped, wrapping prompt text for agent mode; feed cost copy is unchanged.
- `tests/python/test_agent_upkeep.py` adds **32 tests**, including fake native cron
  injection, simultaneous refreshes, lifecycle, validation, approval changes,
  stale snapshots, native failure states, and an installed-cron API shape test.
  Four tests apply integration patches only to a temporary source copy and prove
  the manifest hooks, source adapter, host approval REST boundary and rendered UI.
- `harness/qualify_agent_upkeep.py` is the Forge-only real-Desktop harness. It
  reuses `qualify_schedule`, `guest_realm` and `cdp`, makes a disposable public
  fixture, approves through native host input, requests two real model runs,
  checks source provenance and retained notes, observes guest updates, executes
  with the Space closed, checks pause/reapproval/archive/delete, and compares
  other Spaces. Failed qualification archives its fixture for inspection.
- `.run/projects.patch`, `.run/init.patch`, `.run/permissions.patch` and
  `.run/schedule-api.patch` are the cross-lane seams below. They must be force-added
  because `.run/` is ignored.
- `LANE_REPORT.md` replaces the inherited unrelated lane report as requested.

`projects.py`, package `__init__.py`, the REST adapter and `permissions.jsx` were
not edited directly. No grants/bridge/net, guest, kit, build-space skill, contract,
specification or generated shipped bundle files changed. The feed-only
`scripts/refresh_space.py` was read and needs no change; agent jobs use no shim.

The Model the Domain principle shaped the use of existing run states and a
native-status mapping in `runs.detail`, rather than a second queue or schema.

## Installed Hermes findings

Read `cron/jobs.py`, `cron/scheduler.py`, `cron/executions.py` and the native
cancellation path in the installed Hermes source. No installed files changed.

- `create_job` accepts `prompt`, optional `skills`, `no_agent`, `deliver`,
  `catch_up`, `paused`, `repeat`, `timezone` and `enabled_toolsets`.
- `trigger_job(job_id, extra_prompt=None)` queues the next tick, stamps manual
  intent, and enables/resumes the job. This is why manual refresh creates a
  separate one-shot instead of triggering a paused recurring schedule.
- Bare `1m` is an interval. `in 1m` is native one-shot syntax. A paused one-shot
  is created first and then triggered, preventing execution before registration.
- `_resolve_cron_enabled_toolsets` uses a per-job override when supplied;
  otherwise it inherits the configured cron platform tools. Native configuration
  and deny rules remain authoritative. `skills` is optional, so no build skill
  or fixed tool list is injected.
- `cron.executions.list_executions(job_id=..., limit=...)` exposes execution ids,
  claimed/start/finish times and native statuses. `completed` maps to succeeded;
  `unknown` maps to failed; `cancelled` maps to canceled. Missed slots are not
  fabricated as executed Space refreshes.
- The installed native API test creates/triggers/removes only a job in its fresh
  `.run/` test home. It does not start a ticker or call a model.

## Forge integration patches

Apply these after reviewing overlap with c-tools. These are patch artifacts,
not claims that unowned working-tree files already contain the changes.

```sh
git apply .run/projects.patch
git apply .run/init.patch
git apply .run/permissions.patch
git apply .run/schedule-api.patch
```

1. **projects.patch.** The small validation call sits at existing upkeep
   validation. A second two-line hook in `_save_revision` is necessary for
   transactional edit/restore reapproval. There is no new project-state file.
2. **init.patch.** Adds optional boolean `source_owned` to `spaces_write_records`.
   Default behavior stays the existing user-data batch. With `true`, put ops use
   `source` and optional `source_meta`, require Refresh under the write lock,
   force metadata handler `agent` and fetched time, and call the existing source
   writer in one transaction. User `data` is untouched, source deletes/mixed
   data writes are rejected, and failure rolls the entire batch back. The result
   is `{added, updated, unchanged}`. The tool schema describes this extension.
3. **permissions.patch.** The actual Approve button is in `PermissionsContent`,
   not ScheduleSheet. Reuses `UpkeepCost` there so model cost and prompt appear
   before approval. Submits the displayed upkeep snapshot and refreshes the
   parent detail after a conflict.
4. **schedule-api.patch.** Carries optional object `requested_upkeep` from the
   approval REST request to `decide_schedule`. Existing approve/deny/pause payloads
   stay supported. Stale prompt approval returns `conflict`; malformed snapshots
   return `invalid`. This prevents an old host click from approving a changed
   prompt the user has not reviewed.

The four integration tests copy `src/` into fresh `.run/` directories and apply
these patches there. They also accept already-applied patches after integration.
They do not patch the original worktree. Their renderer uses the installed React
and esbuild dependencies without installing anything. All four ran, none skipped.

## Verification and red/green evidence

Commands ran from this worktree unless a different directory is stated. Logs
are local, ignored files under `.run/c-agent-upkeep/`. Home-relative interpreter
spelling below resolves to the installed interpreter used in the runs. Every
Python test home/database is under the worktree's `.run/`.

### Agent feature regressions

```sh
PYTHONDONTWRITEBYTECODE=1 ~/.hermes/hermes-agent/venv/bin/python -m unittest tests.python.test_agent_upkeep
```

Final green: **32 tests passed**, zero failures, errors or skips. Receipt:
`agent-green.log`. The final stock suite below also includes these same 32 tests.

For the red run, exported the unchanged base into a throwaway directory, copied
only the new tests and integration patches, then ran the same test module there:

```sh
mkdir -p .run/c-agent-upkeep/baseline
git archive 7febcd8 src tests | tar -x -C .run/c-agent-upkeep/baseline
cp tests/python/test_agent_upkeep.py .run/c-agent-upkeep/baseline/tests/python/test_agent_upkeep.py
mkdir -p .run/c-agent-upkeep/baseline/.run
cp .run/projects.patch .run/init.patch .run/permissions.patch .run/schedule-api.patch .run/c-agent-upkeep/baseline/.run/
cd .run/c-agent-upkeep/baseline
PYTHONDONTWRITEBYTECODE=1 ~/.hermes/hermes-agent/venv/bin/python -m unittest tests.python.test_agent_upkeep > ../red-final.log 2>&1
```

Final base run: exit **1**, **32 tests**, **16 failure outcomes and 16 error
outcomes**. Unittest counts subtest outcomes separately. Feed/lifecycle controls
already present are not claimed as new failures. Missing agent handler support,
validation/hooks, native status reconciliation and UI disclosure are red.

Specific fix receipts:

| Fix | Before | After |
|---|---|---|
| Agent approval, validation/reapproval, native queue/status, concurrency and grant behavior | Base regression run above | All 32 pass on lane implementation and integration copies |
| Native one-shot syntax, active-run interruption, stale terminal-state protection | `race-red.log`: 3 tests, 3 failures | `race-green.log`: 3 tests pass; final suite retains the behaviors |
| Scheduled entry cannot bypass approval, including old feed shims | `approval-red.log`: 2 tests, 2 failures | `approval-green.log`: 2 tests pass |
| Host snapshot differs from current prompt | `display-red.log`: 1 test, 1 error (missing API argument) | `display-green.log`: 1 test passes |
| Cross-lane validation, source adapter, approval REST snapshot and pre-approval UI | `boundaries-red.log`: 4 tests, 3 failures, 1 error with patch application withheld | All 4 pass with patches in temporary copies |

The targeted race command named these methods on `AgentUpkeepTests`:
`test_cancel_running_agent_requests_native_interrupt`,
`test_stale_native_snapshot_cannot_reopen_finished_run`, and
`test_manual_refresh_does_not_resume_paused_schedule`.
The approval command named
`test_scheduled_entrypoint_cannot_bypass_agent_approval` and
`test_old_feed_shim_cannot_run_a_new_unapproved_agent_prompt`.
The display command named
`test_approval_rejects_a_prompt_different_from_the_host_display`.
All used `PYTHONDONTWRITEBYTECODE=1` and the same interpreter/unittest invocation.

The boundary red command was:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" ~/.hermes/hermes-agent/venv/bin/python .run/c-agent-upkeep/run-unpatched-boundaries.py
```

That local runner loads `AgentIntegrationPatchTests` and withholds only its
`patch` subprocess calls while allowing all Python, REST and renderer assertions
to execute against the unpatched copy. This separately proves that the patches,
not just their owned helper functions, are required.

### Stock Python suite

```sh
HERMES_HOME="$PWD/.run/c-agent-upkeep/home" LIVING_SPACES_DB="$PWD/.run/c-agent-upkeep/home/spaces.db" PYTHONDONTWRITEBYTECODE=1 ~/.hermes/hermes-agent/venv/bin/python -m unittest discover -s tests/python -t . > .run/c-agent-upkeep/python-final.log 2>&1
```

Exit **0**, **250 tests passed**, zero failures, errors or skips.

An initial local runner copied the inherited report's obsolete skip name and
could not start: `AttributeError: type object 'RunTests' has no attribute
 'test_manual_refresh_from_local_server_has_provenance_and_timestamps'`.
Current source uses `httpx.MockTransport` and has no listener test. After reading
that source, the unmodified stock discovery above ran in full. No test was skipped
and no listener was attempted. Earlier intermediate stock runs passed 237 and
245 tests before the remaining regressions were added.

### JavaScript, renderer and graph

```sh
esbuild src/desktop/plugin.src.js --bundle --format=esm --jsx=automatic --external:@hermes/plugin-sdk --external:react --external:react/jsx-runtime --outfile=.run/package/plugin.js --metafile=.run/package/desktop-metafile.json
node --experimental-vm-modules --import ./tests/js/sandbox/env.mjs --test tests/js/sandbox/*.test.mjs tests/js/ui/index.js tests/js/reference/*.test.mjs > .run/c-agent-upkeep/node-final.log 2>&1
node tests/js/ui/render-smoke.mjs > .run/c-agent-upkeep/render.log 2>&1
node scripts/check-renderer-graph.mjs .run/package/desktop-metafile.json
node tests/js/sandbox/check.mjs
```

All exit **0**. **147 JavaScript tests pass**, zero failures/skips. Static renderer
passes **40 assertions**, producing 12 local fixtures. Renderer graph excludes
guest code/HTML. Syntax gate passes **19 JavaScript files** and whitespace passes
**25 lane files** both before and after this report update. The UI entry is `index.js`; no
`tests/js/ui/*.test.mjs` files exist. Existing test prerequisites require the VM
modules flag and the resolver preload.

The first Node attempt before creating the graph prerequisite had **147 tests,
146 passed, 1 failed**: `ENOENT: no such file or directory, open
'.run/package/desktop-metafile.json'`. Building only into `.run/package` resolved
it. Neither generated shipped artifact was changed.

### Harness and whitespace

```sh
PYTHONPYCACHEPREFIX="$PWD/.run/c-agent-upkeep/pycache" ~/.hermes/hermes-agent/venv/bin/python -m py_compile harness/qualify_agent_upkeep.py
git diff --check
```

Both exit **0**. `git apply --check` also accepts all four integration patches against the unowned base files. `git diff --cached --check` is clean but empty because staging failed. Compilation is the only execution of the new harness in this
lane. No Desktop or model success is claimed.

## Harness command for Forge

After integrating the patches and rebuilding/installing in the existing isolated
Desktop, run serially with other app harnesses:

```sh
~/.hermes/hermes-agent/venv/bin/python harness/qualify_agent_upkeep.py
```

The harness follows the existing isolated profile/CDP settings from
`qualify_schedule.py` and `cdp.py`. It requires the already-running isolated
Desktop and gateway, configured model access, and `living_spaces` tools enabled
for native cron. It will spend model calls. Its fixture is explicitly
harness-authored; source divergence before the scheduled run is disclosed, not
presented as live retrieval. Output is `evidence/agent-upkeep/agent-upkeep.json`
and screenshots under the existing isolated build root. A normal pass deletes
only its disposable fixture; failure archives it for inspection.

## Git handoff

The attempted verified implementation commit command was:

```sh
git add src/living-spaces/living_spaces_core/schedules.py src/living-spaces/living_spaces_core/runs.py src/desktop/ui/schedule.jsx tests/python/test_agent_upkeep.py && git add -f .run/projects.patch .run/init.patch .run/permissions.patch .run/schedule-api.patch && git diff --cached --check && git commit -m 'Add native agent upkeep jobs and approval integration seams'
```

The first `git add` failed with exit **128**:

```text
fatal: Unable to create '<shared-repo>/.git/worktrees/c-agent-upkeep/index.lock': Operation not permitted
```

Staging failed, so the later commands did not execute. All changes remain
**unstaged**. No alternate index, permission bypass or push was attempted. Forge
must stage the five changed/new source/test/harness files, this report, and
force-add the four named patch files from an authorized shell. The shared Git
metadata permission failure prevents the requested small commits in this lane.

## Not done, contract issues and spec gaps

1. The four seam patches are not applied to the unowned worktree files. Without
   them, project writes do not validate/invalidate agent upkeep, the actual host
   approval card still says “No model calls,” and the tool lacks source writes.
   The red boundary tests prove these gaps. Integrate all four before qualification.
2. Frozen contract sections 3/6 describe only feed upkeep and a no-agent shim.
   Decision 4 authorizes the agent extension. Forge should document agent prompt
   validation, native job behavior and native execution identifiers without
   changing the frozen decision or adding host scopes.
3. Sections 4/8 need the optional `requested_upkeep` approval snapshot documented.
   Section 9 needs `spaces_write_records.source_owned`, source/source_meta ops,
   its counts result and Refresh requirement documented. Default tool behavior
   remains unchanged. These files were not edited in this lane.
4. Spec section 2's per-tool, per-Space authority intersection is stronger than
   a normal native Hermes agent with a prompt restriction. Per decision 4 this
   lane inherits native cron tool authority and adds no host scopes. “Only this
   Space” is an instruction to the model, not a new tool sandbox. Source-owned
   writes enforce Refresh/archive checks and preserve data, but do not prevent
   an agent from choosing other ordinary tools. Forge/Product must reconcile
   this accepted R1 behavior with the broader spec before claiming scoped-tool
   isolation. No change to the frozen decision is proposed here.
5. Native run status proves job completion, not correctness of the model's task.
   The real harness separately asserts an actual source write and retained notes.
   Arbitrary agent changes are not measured as feed-style added/updated counts;
   `detail.changed_unavailable` says so, and agent source-as-of remains unknown.
6. Agent execution history is reconciled when runs/freshness are read, using up
   to 500 retained native executions per job. There is no added daemon or model
   watcher. This is not a promise of unlimited backfill beyond native retention.
7. Private native dependency now includes `cron.executions` as well as the
   existing `cron.jobs` seam. Installed APIs were verified, but the declared
   minimum Hermes version and catalog admission for private APIs need Forge's
   integrated package validation. No package validator or install ran here.
8. Real Desktop/model execution, offline catch-up, the configured cron toolset's
   availability and final R1 acceptance remain unqualified. `catch_up=True` and
   the existing one-current-refresh UI policy are preserved; compilation and
   unit tests do not prove ticker execution.
9. Git staging/commit is sandbox-blocked as documented above. No product artifact
   was published or pushed. No credentials, private demo data or live profile
   data were added.
