# w2-partials lane report

Living Spaces needs evidence that ambiguous chat targets cannot mutate the wrong app, refresh preserves concurrent user edits, incompatible restore preserves current data, and frame reload invalidates the old session. This lane adds three core tests and one four-step Desktop harness. It does not claim Desktop acceptance.

**Verdict: ISSUES.** The permitted unit gates pass with one sandbox-related Python skip. All four Desktop steps await Forge. The host error formatter demonstrably omits restore version numbers. Git refuses staging, so no commit was possible.

## Scope and files

Base and current HEAD are `0aaebc35da217e11511bf678b9f4b88fc5add4e0` on `forge/r1-w2-partials`.

- `tests/python/test_core_partials.py` adds three tests against the real core and SQLite. Temporary homes and databases live under this worktree's `.run/`. Feed fetching is injected; these new tests use no network.
- `harness/qualify_partials.py` adds selectable `ambiguous`, `stale-refresh`, `incompatible-restore`, and `frame-reload` steps, plus a read-only semantic review mode.
- `LANE_REPORT.md` records the handoff.

No product source, frozen contract, Desktop bundle, guest producer, or other lane's files changed. Test logs and a renderer build/metafile are untracked local artifacts under `.run/`.

The requested poteto style policy informed the implementation. Model the Domain led to an explicit step registry and evidence records containing checks, status, fixtures, and trace provenance. The throughput checkpoint was core behavior first, then harness construction, then stock gates and handoff. Each unit ends with a runnable check.

## What is proven locally

### R1-03 resolution inspection

Every existing-Space agent tool routes through `_space` in `src/living-spaces/__init__.py`, which delegates to `core.resolve_space`. The tool handler preserves structured errors. `projects.resolve_space` accepts exact IDs or unique case-insensitive exact names. Duplicate exact names yield `ambiguous` with candidates. Partial names yield `not_found`; there is no fuzzy single-Space selection. The existing `test_ambiguous_reference_never_guesses_or_writes` also passed in the stock suite.

No agent resolution defect was found, so no agent source or agent test file was changed. Model behavior for the phrase “my research space” is still a real-Desktop acceptance question.

### R1-06 core races

An event barrier holds the real refresh worker inside an injected RSS fetch. The tests exercise both commit orders.

1. The guest bridge write commits while refresh is running. The source update then commits. Both user fields and source survive, rev advances twice, and the changes stream has exactly the corresponding put/source revisions. Reusing the guest's now-stale revision returns `conflict` with the complete current record and adds no changes.
2. Refresh commits before the guest writes with its previously current revision. The guest receives `conflict` with current data/source. Retrying with the supplied current revision preserves source and merges the intended user change.

Both tests pass against the unchanged core. No core defect or expected failure was found.

### R1-10 core restore and host display gap

The third test creates data version 1, renames a user field through a version 2 migration, then attempts restoration of revision 1. The core returns `incompatible`, `from_version=2`, `to_version=1`. Records, history and the data version remain unchanged.

A direct invocation of the existing host `errorText` function with that error returns exactly:

> Incompatible revision: Code restore requires the current data version. Your current code and records are unchanged.

Neither version is present. This is executable formatter evidence, not an observation of the running Desktop. The harness checks the actual host error banner for both versions and is expected to fail that check until the Desktop owner addresses it. No Desktop code was edited.

## Verification commands and receipts

Commands were run from the lane worktree. Output counts below are actual observations.

| Command | Result |
|---|---|
| `~/.hermes/hermes-agent/venv/bin/python -m unittest tests.python.test_core_partials -v` | First authoring run: 3 tests, 1 passed, 2 failed because the tests over-specified the conflict message text. No product failure. |
| Same focused command after asserting the contract's code/current fields instead | 3 tests, 3 passed, 0 failures/skips. |
| `~/.hermes/hermes-agent/venv/bin/python -m py_compile harness/qualify_partials.py tests/python/test_core_partials.py` | Passed. This checks syntax, not Desktop behavior. |
| `~/.hermes/hermes-agent/venv/bin/python harness/qualify_partials.py --help` | Passed; lists all four steps and the chat/review arguments. Does not import app-driving helpers. |
| `~/.hermes/hermes-agent/venv/bin/python -m unittest discover -s tests/python -t .` | 154 tests, 153 passed, 1 skipped, 0 failures/errors. Log `.run/partials-python.log`. |
| `~/.hermes/hermes-agent/venv/bin/python -m unittest tests.python.test_upkeep_runs.RunTests.test_manual_refresh_from_local_server_has_provenance_and_timestamps -v` | 1 test, 1 skipped. Exact reason below. |
| `node --test tests/js/sandbox/*.test.mjs tests/js/ui/index.js tests/js/reference/*.test.mjs` | First attempt: 97 reported tests, 93 passed, 4 failed. Missing Preact import setup and renderer metafile. Log `.run/partials-node.log`. |
| `mkdir -p .run/package && esbuild src/desktop/plugin.src.js --bundle --format=esm --jsx=automatic --external:@hermes/plugin-sdk --external:react --external:react/jsx-runtime --outfile=.run/package/plugin.js --metafile=.run/package/desktop-metafile.json` | Passed. Produces only local test prerequisites; shipped bundle untouched. |
| `node --import ./tests/js/sandbox/env.mjs --test tests/js/sandbox/*.test.mjs tests/js/ui/index.js tests/js/reference/*.test.mjs` | Second attempt: 113 reported tests, 111 passed, 2 failed. Missing `--experimental-vm-modules` for reference tests; one existing host timing test also failed. Log `.run/partials-node-ready.log`. |
| `node --experimental-vm-modules --import ./tests/js/sandbox/env.mjs --test tests/js/sandbox/*.test.mjs tests/js/ui/index.js tests/js/reference/*.test.mjs` | Final: 131 tests, 131 passed, 0 failures/skips. Log `.run/partials-node-final.log`. |
| `git diff --check` | Passed for tracked changes. New-file whitespace checks are listed below. |
| `for partials_file in harness/qualify_partials.py tests/python/test_core_partials.py LANE_REPORT.md; do git diff --no-index --check /dev/null "$partials_file"; done` | No whitespace diagnostics for any new file. No-index comparison reports added-file differences with exit 1. |

The existing HTTP test skipped with `Sandbox forbids binding the local HTTP fixture: [Errno 1] Operation not permitted`. No listener was started. Forge can rerun it outside this sandbox.

The second Node attempt failed `mount binds boot to host session, forwards replies and emits versioned events` at `host.test.mjs:102` with `0 !== 1` after its existing 20 ms delay. It passed in the first and final runs. This is a transient existing test failure; the timing explanation is inferred, and no test was changed to conceal it.

Formatter reproducer, run successfully:

```sh
node --input-type=module -e 'import { errorText } from "./src/desktop/ui/model.mjs"; const error = {code:"incompatible", message:"Code restore requires the current data version", from_version:2, to_version:1}; const text = errorText(error); console.log(JSON.stringify({error, text, exposesBothVersions: /2/.test(text) && /1/.test(text)}));'
```

Observed `exposesBothVersions` is `false`.

## Harness handoff, not executed

Forge must run these serially against the shared isolated Desktop, with this lane's files available and the integrated candidate installed. No gateway, app, Chrome, scheduler or network listener was started or controlled by this lane.

```sh
~/.hermes/hermes-agent/venv/bin/python harness/qualify_partials.py ambiguous --chat-session "$FRESH_ISOLATED_CHAT_SESSION"
~/.hermes/hermes-agent/venv/bin/python harness/qualify_partials.py stale-refresh
~/.hermes/hermes-agent/venv/bin/python harness/qualify_partials.py incompatible-restore
~/.hermes/hermes-agent/venv/bin/python harness/qualify_partials.py frame-reload
```

Create a fresh neutral conversation in the isolated Desktop for `FRESH_ISOLATED_CHAT_SESSION`. The harness rejects a session containing earlier user turns so prior selection of Research Desk cannot disambiguate the prompt. The prompt itself supplies no Space ID or exact name.

Each invocation writes timestamped evidence beneath the existing isolated run's `evidence/partials/` directory. It records checks and errors and returns 0 for PASS, 1 for FAIL, or 2 for NEEDS_REVIEW. It snapshots raw SQLite values in stable JSON bytes for both protected Spaces, including all collections, revisions, projects, changes, grants, schedules, runs, recovery points, audit and logs. Sessions are excluded because navigation legitimately closes them. Before/after files must be byte-identical. Every created fixture is tracked immediately and deleted in `finally`, with deletion asserted. Cleanup failure makes the invocation fail. Existing fixtures are never silently reused or deleted.

- **Ambiguous.** Creates `research-notes` through core and seeds a public note. Sends one real Desktop chat turn through `chat_turn.submit` with native input. Requires both candidate Spaces and the protected snapshots to remain byte-identical. Stores complete ordered user, assistant and tool trace rows. A structured `ambiguous` result must correlate to an earlier `spaces_*` call ID. Otherwise the result remains NEEDS_REVIEW until Forge reads the full trace and determines whether the final reply asks which Space. No keyword heuristic awards a pass.
- **Stale refresh.** Creates a disposable feed Space, seeds it through real core refresh, mounts it, reads the current record through the guest bridge, holds a real core worker at an injected RSS fetch barrier, and saves through guest `space.put`. It then releases refresh and attempts a stale guest write. Checks data/source survival, revs, changes, and the full `conflict.current` payload. This is a deterministic feed fixture with actual Desktop guest writes. It does not click host Refresh now or fetch an external feed; those existing acceptance observations are separate.
- **Incompatible restore.** Creates revision A with data version 1, then B with a real version 2 field migration. Uses native mouse input for History, Revisions, Restore and confirmation. Requires the incompatible banner, unchanged revisions/data, and displayed current/target versions. The last assertion is expected to expose the formatter gap above. Cleanup cancels the remaining confirmation and deletes the fixture.
- **Frame reload.** Schedules `location.reload()` only in the mounted guest realm. Observes the shell's actual `space-reloaded` message, preserved host-page marker, replaced frame, closed old session, fresh session, and remounted guest metadata. Replays a write using the old session through `core.dispatch`. Requires `session_invalid`, byte-identical records and no changes entry.

The harness reuses `qualify_schedule` navigation, native input, waiting, screenshots and visibility helpers. It reuses `guest_realm` and the lifecycle harness's core-dispatch replay pattern. It does not import `qualify_lifecycle`, because that module executes its whole suite on import. Snapshot coverage is stronger than its fixed-collection helper.

If ambiguous returns NEEDS_REVIEW, inspect `partials.json`, then write a separate review artifact containing:

```json
{
  "evidence": "/path/to/the/partials.json",
  "trace_sha256": "the trace_sha256 from that evidence",
  "asks_which_space": true,
  "rationale": "Explain which final assistant message asks the user to select a Space, using the full trace."
}
```

Do not set the boolean to true unless the trace supports it. Then run:

```sh
~/.hermes/hermes-agent/venv/bin/python harness/qualify_partials.py ambiguous --review /path/to/review.json
```

This mode only reads the existing evidence and review. It validates the trace hash, requires all preservation checks to have passed, and writes `partials-reviewed.json`. It does not send another turn or recreate fixtures. A false review is rejected. The original NEEDS_REVIEW evidence is retained.

## Red-then-green evidence

There is no product fix in this lane, so there is no product red/green claim. The initial two core-test failures were an incorrect message-text expectation in newly authored tests. Both core behaviors already passed once the tests asserted the frozen error contract. The host version-display gap remains unfixed and is not reported green.

## Contract issues and spec gaps

1. The task requires version numbers in the host incompatible message. The frozen error contract provides `from_version` and `to_version`, but the current host formatter discards them. Proposed resolution: the Desktop owner renders both fields and adds a focused UI test. The harness then verifies the real dialog. The frozen contract was not edited.
2. The agent schema's shared `REF_NOTE` says ambiguous/unknown errors list candidates, while the resolver's `not_found` error has no candidates. Exact duplicate names do supply candidates. This documentation mismatch does not imply fuzzy resolution. Proposed resolution: describe `ambiguous` candidates separately from `not_found`, through the owning lane if desired.
3. Spec R1-03 defines non-mutation for ambiguous references but does not prescribe machine scoring of open-ended clarification prose. Proposed qualification rule: accept a correlated typed ambiguous error, or an explicit semantic review of the full turn trace bound by hash. No claim based only on matching words.
4. Spec R1-06 does not require an external-network timing race. This lane provides deterministic core and Desktop bridge race coverage using injected RSS bytes. If Forge requires the race to originate from host Refresh now, additional gateway-controlled fetch coordination is still needed; this harness does not claim that path.

## Remaining work and Git boundary

Forge still needs to execute every Desktop step, adjudicate any clarification-only trace, fix or disposition the version-display gap, and collect integrated evidence. The local HTTP fixture needs an unrestricted rerun. No R1 ledger row is promoted by this lane.

The attempted command `git add tests/python/test_core_partials.py && git commit -m 'test: cover refresh races and incompatible restore'` failed at staging with `fatal: Unable to create '.../.git/worktrees/w2-partials/index.lock': Operation not permitted`. HEAD remained unchanged. Staging is blocked as well as committing; the files cannot honestly be described as staged. No push was attempted.

The final `git add harness/qualify_partials.py tests/python/test_core_partials.py LANE_REPORT.md` also exited 128 with the same lock-creation error. All three files remain untracked for Forge to stage and commit outside this restriction.
