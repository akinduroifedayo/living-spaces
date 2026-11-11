# w2-repair report

Living Spaces needs dependable saves, approval tied to what the user saw, and session and data access boundaries that survive retries and profile switches. This lane repairs F1, the F2 host half, F5, F6, and amendment A2.

**Verdict: ISSUES.** All new regression tests pass. The complete Node gate passes 146/146. Python discovery runs 156 tests with two failure records in one legacy adapter test and one sandbox-related skip. That adapter still expects approval without `requested_scope`. Staging and committing are blocked by the sandbox. Desktop acceptance is not claimed.

Branch is `forge/r1-w2-repair`, starting at `0aaebc35da217e11511bf678b9f4b88fc5add4e0`. No push was attempted.

## Changes and success criteria

The sequence was failing regression, targeted repair, passing regression, then the available repository gates. Raw receipts remain in `.run/repair/` in this worktree. Tests use temporary homes/databases under `.run/` and public fixture data.

- `src/living-spaces/living_spaces_core/grants.py`. Only `decide`, including its signature, changes. It accepts the displayed `requested_scope`, normalizes it and compares it to the current request inside the write transaction. A mismatch raises `conflict` with the current Grant and does not append an audit decision. The existing subset check still forbids wider grants. The revoke/cancel hook and everything after it are byte-identical to the base.
- `src/living-spaces/dashboard/plugin_api.py`. Only the grant route changes. REST approval requires a `requested_scope` object and forwards it to core. Deny/revoke remain available without it.
- `src/desktop/ui/permissions.jsx`. Approve sends the displayed scope. Failed decisions refetch the current request and schedule, including when native IPC strips structured HTTP error properties. The user sees the replacement scope and must approve again.
- `src/desktop/ui/session.mjs`. Each ID-less put gets a cryptographically generated `r_<12 hex>` ID and `base_rev: 0` before transport. This includes individual puts inside batches. The first draft is cloned and Retry save reuses it. Explicit IDs and revision preconditions remain intact. Transport failure produces an unknown outcome, which remains unknown if a later rejected retry cannot establish whether the original committed. A confirmed first-attempt rejection remains failed.
- `src/desktop/ui/session.mjs`. Session opening, bundle loading and cleanup use a captured native API connection/profile when supplied by Desktop. Closing makes at most three attempts per close invocation, with 250 ms and 500 ms retry waits and a 5-second transport timeout per DELETE. Concurrent close calls share the same attempt sequence. Exhaustion reports errors and rejects; a later destroy can retry. Successful cleanup stays deduplicated. Opening after navigation still closes the issued token.
- `src/desktop/ui/space.jsx`. Captures the connection/profile from the rendered context, rather than mutable host state at effect execution. Supplies the fixed lifecycle transport, shows unknown-save copy, and displays a host error notification after cleanup exhaustion. Polling and forwarding `data.changed` both require a granted data capability. Cached/late change pages are withheld once revocation is observed.
- `src/living-spaces/living_spaces_core/db.py`. Adds nullable `schedules.reason TEXT` to new schemas and an idempotent missing-column migration for existing schemas. The check and ALTER run under `BEGIN IMMEDIATE`, preserving existing rows and reason values. The schema version remains 1 as required by the frozen contract.
- `src/living-spaces/desktop/plugin.js`. Rebuilt from the owned UI source with the exact required command.
- `tests/python/test_core_repair.py`. Five real-core/route/schema regression tests.
- `tests/js/ui/repair-session.test.mjs`. Seven transport/session behavior tests, using an in-memory backend model for uncertain writes. These are not a claim of real-Desktop or real-core replay acceptance.
- `tests/js/ui/repair-components.test.mjs`. Eight React/jsdom component tests, with the query and sandbox seams stubbed. They exercise real UI callbacks/effects and visible copy, not screenshots or source matching.
- `tests/js/ui/index.js`. Updates the existing wire expectation for generated IDs and the existing transport-error expectation from failed to unknown.
- `tests/js/ui/qualify_repair.py`. Forge-only real-Desktop F6 harness. Compiled, not executed.
- `LANE_REPORT.md`. This report.

The guest kit, guest CSS, sandbox, records, sessions, schedules, logs, bridge and runs implementations were not edited. No shared services, Desktop, Chrome or network listeners were started by this lane. The stock Python suite attempted its local HTTP fixture and skipped when the sandbox refused the bind.

## Red then green evidence

All commands below ran from the worktree root. Red and green used the same substantive assertions, except the explicitly disclosed test-helper correction.

| Finding | Red receipt | Green receipt |
|---|---|---|
| F1 core and REST | `f1-red.log`: 3 tests, 2 errors for the missing keyword and 1 failure because the route returned 400 instead of conflict | `f1-green-final.log`: 3/3 pass |
| F1 UI | `f1-ui-red.log`: 0/1 pass; approval omitted displayed scope | `f1-ui-green.log`: 1/1 pass |
| F1 native IPC | `f1-native-red.log`: 0/1 pass; plain Error conflict did not refetch | `f1-native-green.log`: 2/2 pass, structured and native error cases |
| F2 | `f2-red.log`: 0/4 pass; missing IDs, wrong outcome status and mutable retry draft | `f2-green.log`: 34/34 pass, four repair tests plus 30 existing UI tests |
| F2 uncertainty across retries | `f2-uncertainty-red.log`: 0/1 pass; rejected retry incorrectly converted an uncertain original outcome to failed | `f2-uncertainty-green.log`: 7/7 pass, all session repair tests at that point |
| F5 | `f5-red.log`: 0/3 pass; no retry, no rejection after exhaustion, no opening-backend binding | `f5-green.log`: 37/37 pass, seven repair tests plus 30 existing UI tests |
| F5 render/effect switch race | `f5-scope-red.log`: 0/1 pass; current host state overrode the rendered context | `f5-scope-green.log`: 1/1 pass |
| F6 | `f6-red.log`: 0/4 pass; missing/requested/revoked data grants still polled and forwarded metadata | `f6-green.log`: 5/5 pass, four F6 cases plus F1 UI |
| A2 | `a2-red.log`: 2 tests, 1 failure and 1 error; missing column in both new and existing databases | `a2-green.log`: 5/5 pass, two schema cases plus three consent cases |

The first F1 green attempt (`f1-green.log`) had 2 passes and 1 test-helper error. The inherited `CoreCase.error` returns a dict, not an exception. Changing `error.extra['current']` to `error['current']` fixed that harness error. It did not weaken the assertion or change product code.

Exact focused commands, with the different receipts listed above produced by redirecting stdout/stderr to their matching log:

```sh
~/.hermes/hermes-agent/venv/bin/python -m unittest tests.python.test_core_repair.ConsentBindingTests
~/.hermes/hermes-agent/venv/bin/python -m unittest tests.python.test_core_repair.ScheduleReasonTests
~/.hermes/hermes-agent/venv/bin/python -m unittest tests.python.test_core_repair
node --test tests/js/ui/repair-components.test.mjs
node --test --test-name-pattern='native IPC' tests/js/ui/repair-components.test.mjs
node --test --test-name-pattern=F1 tests/js/ui/repair-components.test.mjs
node --test --test-name-pattern=F6 tests/js/ui/repair-components.test.mjs
node --test --test-name-pattern='view pins' tests/js/ui/repair-components.test.mjs
node --test tests/js/ui/repair-session.test.mjs
node --test --test-name-pattern=F5 tests/js/ui/repair-session.test.mjs
node --test --test-name-pattern='uncertain transport' tests/js/ui/repair-session.test.mjs
node --test tests/js/ui/repair-session.test.mjs tests/js/ui/index.js
node --test tests/js/ui/repair-components.test.mjs tests/js/ui/repair-session.test.mjs
```

The final session-only run after adding the shared temp-home setup passed 7/7 (`session-final.log`). The final combined gate below includes all eight component tests.

## Repository gates and blocked operations

```sh
~/.hermes/hermes-agent/venv/bin/python .run/review/repro-review.py .
```

Did not start the probes. It hardcodes a temp directory outside this worktree. The failure was `PermissionError: [Errno 1] Operation not permitted` creating a child under `/Volumes/Expansion/Development/Build/living-spaces-r1/run`. The supplied script was not modified.

```sh
~/.hermes/hermes-agent/venv/bin/python -m unittest discover -s tests/python -t .
```

`python-full.log`: 156 tests run. Two failure records arise in `RestTests.test_all_routes_success`, one for its approval subtest and one for its mock-call assertion. Both require the old `{decision, scope}` body and omit the newly required displayed `requested_scope`. There is one skip in `test_manual_refresh_from_local_server_has_provenance_and_timestamps` because the sandbox forbids binding its local HTTP server. The remaining 154 test methods pass. Forge must update the legacy adapter expectation in its owned lane and rerun the stock suite. This lane did not edit or suppress that test.

The first broad Node invocation was:

```sh
node --test tests/js/sandbox/*.test.mjs tests/js/sandbox/index.js tests/js/ui/*.test.mjs tests/js/ui/index.js tests/js/reference/*.test.mjs
```

`node-full.log`: 191 reported tests, 186 pass and 5 fail. This invocation duplicated sandbox tests through `index.js`, lacked the Preact preload/VM setup, and lacked `.run/package/desktop-metafile.json`. Those failures are invocation/setup failures, not five demonstrated product defects. The corrected invocation removes the duplicate entrypoint and supplies the existing test environment.

```sh
mkdir -p .run/package
esbuild src/desktop/plugin.src.js --bundle --format=esm --jsx=automatic --external:@hermes/plugin-sdk --external:react --external:react/jsx-runtime --outfile=src/living-spaces/desktop/plugin.js
esbuild src/desktop/plugin.src.js --bundle --format=esm --jsx=automatic --external:@hermes/plugin-sdk --external:react --external:react/jsx-runtime --outfile=.run/package/desktop.js --metafile=.run/package/desktop-metafile.json
node scripts/check-renderer-graph.mjs .run/package/desktop-metafile.json
node --import ./tests/js/sandbox/env.mjs --experimental-vm-modules --test tests/js/sandbox/*.test.mjs tests/js/ui/*.test.mjs tests/js/ui/index.js tests/js/reference/*.test.mjs
node tests/js/ui/render-smoke.mjs
~/.hermes/hermes-agent/venv/bin/python -m py_compile src/living-spaces/living_spaces_core/grants.py src/living-spaces/living_spaces_core/db.py src/living-spaces/dashboard/plugin_api.py tests/python/test_core_repair.py tests/js/ui/qualify_repair.py
git diff --check
```

Both builds pass. The graph gate passes. The production bundle equals the graph build byte for byte. The corrected intermediate Node run passed 143/143 (`node-full-corrected.log`); the final run passed **146/146**, no failures/skips (`node-final.log`). Static rendering passed **40 assertions**, producing 12 local HTML fixtures (`render-final.log`). Python compilation and `git diff --check` pass. An additional local path/byte check confirms only owned paths changed, the grant revoke/cancel hook is unchanged, and tracked plus new files have no trailing whitespace. No package validator requiring installs or app startup was run.

```sh
git add src/living-spaces/living_spaces_core/grants.py src/living-spaces/dashboard/plugin_api.py src/desktop/ui/permissions.jsx src/living-spaces/desktop/plugin.js tests/python/test_core_repair.py tests/js/ui/repair-components.test.mjs
git commit -m 'fix: bind permission approval to the displayed scope'
```

Both were rejected with `fatal: Unable to create '/Volumes/Expansion/Development/Projects/living-spaces/.git/worktrees/w2-repair/index.lock': Operation not permitted`. No commit exists for this lane, and changes cannot be left staged because staging is also denied. All edits and this report are in the working tree for Forge to stage and commit. No push was attempted.

## Desktop harness handoff

Syntax check passed:

```sh
~/.hermes/hermes-agent/venv/bin/python -m py_compile tests/js/ui/qualify_repair.py
```

Forge should run this serially against the existing isolated Desktop after installing the integrated rebuilt bundle:

```sh
~/.hermes/hermes-agent/venv/bin/python tests/js/ui/qualify_repair.py
```

It reuses `harness/qualify_schedule.py`, `guest_realm.py` and `cdp.py`. It creates a disposable public fixture, proves granted change delivery, revokes own-data through native host controls, waits for the remounted guest to lose authority, installs a fresh listener, writes through core, and checks no metadata arrives across four polling intervals. It also checks guest queries are denied, then closes and deletes the fixture. Evidence goes under `.run/repair/desktop/`. It does not start a service or touch model-built Spaces. **It has not been executed.** Syntax checks cannot prove native button targeting, frame readiness or revocation behavior.

F1 approval races, F2 lost native responses, and F5 actual profile-switch cleanup still need Forge's Desktop qualification. Unit tests and the source inspection of Desktop's routing/IPC are not substitutes for those observations. Reuse the existing authority/lifecycle harness patterns for those cases.

## Contract issues and proposals

1. F1 extends `decide` with optional `requested_scope` for trusted core callers and makes that object mandatory on REST grant decisions. Core callers that omit it retain the existing programmatic behavior. `conflict.current` can now be a Grant, whereas the frozen errors section describes a Record. Forge should amend the REST/API contract and update the old adapter test. The frozen contract file was not edited.
2. F2 adds a host-only `unknown` save status. The guest kit status enum and bridge error codes are unchanged. The current core rejects replay of the stable create with conflict; the tests prove one durable identity and no silent overwrite, not success-on-replay. Core idempotency/replay behavior, including delete/recreate cases, remains owned by the later records lane. Do not strip `base_rev: 0` or replace it with the current revision automatically.
3. F5 needs a fixed backend transport. Installed Desktop source shows `ctx.rest` resolves the active profile each call and offers no fixed-backend option. The native API accepts explicit connection/profile pins, which this lane captures for lifecycle calls only. Guest operations still use the existing scoped REST guard. Native API availability/routing must be verified in the real Desktop. The fallback for contexts without the native API relies on their supplied REST transport and does not establish cross-profile cleanup.
4. F5 cannot guarantee backend invalidation after renderer termination, a lost session-open response, or an outage longer than all close retries. `sessions.py` has no expiry. Proposed follow-up: bounded server session leases with renewal only by the owning mounted host, and replacement-session invalidation keyed by host mount identity. Avoid globally invalidating every session for a Space because independent windows may legitimately coexist. This requires a coordinated backend/host contract change. It is not implemented here.
5. F6 should also have a sandbox-side `data.changed` guard against its current granted-capability set, especially before emitting queued events. That file belongs to the other lane and is unchanged. Host revocation is observed through the existing detail poll; this fix does not prove zero latency between backend revocation and its arrival in the host. A session-bound changes endpoint with a backend data-grant check would address that remaining authorization timing seam. This is a proposal, not an implemented or tested backend guarantee.
6. A2's schema discrepancy is repaired. Populating/reading the reason in `schedules.py` remains the other lane's responsibility; existing schedule-read behavior was not changed.

## Not done

F3 log redaction, F4 refresh/session admission, and F2 core repairs are untouched. No real Desktop, gateway, Chrome, network acceptance, restart, package installation or release qualification was run. No credentials or private demo content were introduced. No GBrain or local memory writeback was performed. Staging, commits, the legacy adapter-test update, the isolated Desktop harness run, and integrated acceptance remain for Forge.
