# Integrated customization repair review: ISSUES

Ife wants normal Hermes chat to build custom multi-view apps with durable data, internet access and upkeep while preserving authority and isolation. This review checks the integrated repairs against F01 through F09 in the complete prior review. It finds two bounded issues. The original nine reproductions pass their frozen regressions. This verdict is not release acceptance or native security qualification.

Reviewed SHA `47a75673b23feb2922df6da6429a26abf9371c5f`. Branch `forge/r1-c-review-repairs`. Workspace `/Volumes/Expansion/Development/Projects/living-spaces-wt/c-review-repairs`.

**Attribution and authority.** The commission selects fresh Sol xhigh normal. This is a fresh same-GPT-family review of Astra-authored repairs, not the required cross-family acceptance gate. No model launch, nested delegation, route substitution or fallback was attempted. This report does not independently verify provider wire metadata, effort, tier or backend weights. The parent retains that receipt audit and the program lifecycle. The explicit bounded commission supersedes generic skill stages that would launch models, run Desktop or publish changes.

## Input coverage and preservation

Read `.run/packet/pins.json` first, then all **forty-seven required shards in full**. An initial oversized display was truncated; the affected bodies were reread in bounded batches before verification. The complete packet covers fifteen source files, with the following exact shard coverage.

| Source | Shards, inclusive |
| --- | --- |
| `docs/evidence/review-customization/REVIEW.md` | 001–005 |
| `docs/evidence/review-customization/green-audit.json` | 006 |
| `tests/python/test_review_customization.py` | 007–012 |
| `tests/python/review_customization_support.py` | 013–015 |
| `tests/python/feed_transport_support.py` | 016 |
| `src/desktop/ui/permissions.jsx` | 017–019 |
| `src/desktop/ui/schedule.jsx` | 020 |
| `src/living-spaces/__init__.py` | 021–027 |
| `src/living-spaces/dashboard/plugin_api.py` | 028–030 |
| `src/living-spaces/living_spaces_core/bridge.py` | 031 |
| `src/living-spaces/living_spaces_core/feeds.py` | 032–033 |
| `src/living-spaces/living_spaces_core/grants.py` | 034–036 |
| `src/living-spaces/living_spaces_core/net.py` | 037–039 |
| `src/living-spaces/living_spaces_core/runs.py` | 040–043 |
| `src/living-spaces/living_spaces_core/schedules.py` | 044–047 |

Read the complete external model policy, requested Poteto skill, `references/hermes-tools.md` and `references/gated-program-delegation.md`. Additional reads stayed within this tree, apart from those instructions and the supplied preflight tool. They included the applicable contract/test commands, spec amendments, repair reports, frozen-method manifest, legacy test diffs against `e45e094`, storage/session/record code, relevant project/SpaceView call sites, and existing Node test scaffolding. No repository-local `AGENTS.md` was found. The supplied AGENTS instructions govern. The local memory registry had no relevant hit. No network-backed context lookup was made under the commission's no-network boundary.

Before any `.run` write, all 47 shard hashes and fifteen source hashes matched. The supported command below exited **0** and its JSON parsed as `status: verified`, matching **408/408** baseline paths and hashes. This is a workspace observation, not an OS sandbox or future-state guarantee.

```sh
python3 -B /Users/ifedayoakinduro/.hermes/skills/pstack/hermes-local/native-preflight.py --workspace /Volumes/Expansion/Development/Projects/living-spaces-wt/c-review-repairs --parent /Volumes/Expansion/Development/Projects/living-spaces --manifest /Volumes/Expansion/Development/Projects/living-spaces-wt/c-review-repairs/.run/baseline.json
```

Initial parsed receipt is `preflight-initial.json`. Final `verify-final.py` reruns the supported preflight, hashes every shard and source, verifies each shard body against its declared source slice, checks the branch, empty Git status and `git diff --check`, and binds this report and retained artifacts in `final-integrity.json`.

## Executed results

All Python product/test execution used `/Users/ifedayoakinduro/.hermes/hermes-agent/venv/bin/python`. The wrapper allowlists inherited environment keys and places `HERMES_HOME`, `TMPDIR` and `LIVING_SPACES_DB` under this private `.run`. Stock discovery was neither replaced nor patched. Test files were not changed, skipped or injected into.

| Execution | Direct exit | Actual result | Retained receipt/log prefix |
| --- | --- | --- | --- |
| Frozen customization regression | 0 | 27 run, 27 passed, zero failures/errors/skips | `regression` |
| Full Python discovery | 0 | 332 run, 332 passed, zero failures/errors/skips | `discovery` |
| Disposable renderer build prerequisite | 0 | Generated only `.run/package/` outputs | `build-prerequisite` |
| Stock Node entrypoints | 0 | 125 tests, 125 passed, zero failures/skips | `stock-node` |
| Standalone Node files | 0 | 148 tests, 148 passed, zero failures/skips | `standalone-node` |
| Reference Node cases | 0 | 19 tests, 19 passed, zero failures/skips | `reference-node` |
| Additional real-core probes | 0 | Eleven groups completed, including two reproduced issues and one disclosed limitation | `probes` |
| Rendered host consent probe | 0 | React/JSDOM render, clicks, exact snapshots and conflict/refetch checks | `ui` |
| Rendered payload replay through real REST | 0 | HTTP 200, exact displayed schedule and upkeep used for synthetic native job | `ui-replay` |
| Legacy/frozen test audit | 0 | Ten permitted method migrations; 27 frozen methods match | `test-audit` |

Receipts use `<prefix>.receipt.json`; raw output uses `<prefix>.stdout` and `<prefix>.stderr`. The first stock receipts also remain at `<prefix>.json`. These are direct subprocess exits, not deductions from wrapper completion. Node commands overlap and are not a unique combined sum. Python discovery includes the 27 regression cases.

Exact stock commands, from this workspace and under the private environment above:

```sh
/Users/ifedayoakinduro/.hermes/hermes-agent/venv/bin/python -B -m unittest tests.python.test_review_customization -v
/Users/ifedayoakinduro/.hermes/hermes-agent/venv/bin/python -B -m unittest discover -s tests/python -t . -v
esbuild src/desktop/plugin.src.js --bundle --format=esm --jsx=automatic --external:@hermes/plugin-sdk --external:react --external:react/jsx-runtime --outfile=.run/package/plugin.js --metafile=.run/package/desktop-metafile.json
node --test tests/js/sandbox/index.js tests/js/ui/index.js
node --experimental-vm-modules --import ./tests/js/sandbox/env.mjs --test tests/js/sandbox/*.test.mjs tests/js/ui/*.test.mjs
node --experimental-vm-modules --import ./tests/js/sandbox/env.mjs --test tests/js/reference/*.test.mjs
```

**Failed attempts retained.** Before generating the documented renderer metafile, stock Node exited 1 with 124/125 passed. An initially broader standalone selection also included `tests/js/ui/index.js` and exited 1 with 177/178 passed. Both failed only the missing `.run/package/desktop-metafile.json` prerequisite. Their logs/receipts remain as `*-before-prerequisite.*`. The final 148-case command above matches the intended standalone selection.

A supplemental runner initially overwrote its own UI input and audit output with similarly named receipts. This caused UI and payload-replay exits 1. Those logs remain as `ui-receipt-collision.*` and `ui-replay-receipt-collision.*`. Receipt filenames were separated, fixtures regenerated, and the complete eleven-group probe plus UI/input/replay/audit sequence reran with direct exits 0. No product/test bytes changed. An incidental Git invocation emitted Xcode command-line-tool diagnostics in an earlier probe attempt; no Xcode build was requested or used as evidence.

## Reproduced issues

Both commands below run from this workspace. Exit 0 means the counterexample reproduced, not that the requirement passed. They call actual product functions and real private SQLite. Native cron objects are synthetic. REST uses in-process TestClient without a listener.

### R01. P2. REST schedule approval can omit the displayed upkeep snapshot

**Symbols.** `dashboard/plugin_api.py:schedule_update`, lines 188–197, requires the four schedule fields but forwards upkeep only if present. `living_spaces_core/schedules.py:decide_schedule`, lines 185–194, defaults it to `None` and skips the comparison.

```sh
/Users/ifedayoakinduro/.hermes/hermes-agent/venv/bin/python -B .run/probes.py missing_upkeep
```

**Actual.** Create an agent Space, approve its exact Refresh scope, request a schedule, and POST only `decision: approve` plus the exact four-field `requested_schedule`. The real REST route returns **HTTP 200**, `status: active`, and creates one enabled synthetic agent job. No `requested_upkeep` was submitted or compared. Evidence is `missing_upkeep.json`, the matching line in `probes.stdout`, and `evidence/missing-upkeep.db`.

**Required.** The commission's REST contract binds both the four-field schedule snapshot and the displayed upkeep snapshot. Missing upkeep should be rejected without creating a job. The trusted core's optional parameter need not be changed to enforce this at REST.

**Bound.** This is an incomplete approval contract, not an F01 prompt-authority bypass. Refresh still requires the current exact agent task. The rendered host path passes both snapshots correctly. `ui-probe.json` and `ui_replay.json` retain its real rendered payload and successful REST replay; `schedule_fields.json` retains 409s for each stale schedule field and stale supplied upkeep. The migrated REST mock test still sends no upkeep and does not test this missing-field refusal. The 27 new tests do not exercise omission either.

### R02. P2. The new upfront cron pause aborts revocation cleanup on adapter import failure

**Symbols.** `living_spaces_core/runs.py:cancel_pending`, lines 65–68, calls `_cron().pause_job` before discovery with no import-failure handling. `grants.py:decide`, lines 178–197, has already committed revocation and calls cancellation before `on_refresh_revoked`. The exception prevents that later callback from reaching `schedules.py:pause_schedule`'s existing disabled-state fallback.

```sh
/Users/ifedayoakinduro/.hermes/hermes-agent/venv/bin/python -B .run/probes.py revoke_module_unavailable
```

**Actual.** Approve an agent schedule with no local pending runs, then make only the cron adapter loader raise `ImportError`. Real `grants.decide(..., 'refresh', 'revoke')` durably stores `revoked`, raises the uncaught exception, and leaves the schedule row **active**. The same real REST route returns **HTTP 500**. Restore the synthetic adapter and approve Refresh through the normal function. The schedule is still **active**, the synthetic native job is enabled, and no Resume action occurred. The call log contains only the original job creation.

**Required.** Revocation should retain truthful inactive scheduling state and run the supported unavailable-adapter cleanup path even when cancellation cannot obtain the native adapter. Regrant must not silently recover an active schedule from this failed cleanup. Failure to interrupt native work must remain visible; this does not require pretending an unavailable adapter was successfully called.

**Old-byte control.** The probe extracts the exact `cancel_pending` body from `e45e094` and substitutes that function only, in a separate disposable fixture. Under the identical no-pending-run/import-failure setup, real revocation returns `revoked` and the existing schedule callback persists **disabled** with the native-unavailable reason. This isolates the new unconditional pause's exception regression. It is not a full old-tree qualification and does not prove old native interruption worked.

**Evidence.** `revoke_module_unavailable.json`, its `probes.stdout` record, and `evidence/revoke-module-unavailable.db` retain states, call log, HTTP 500 and old-function control. The stored database snapshot is taken after the first regrant; the JSON separately retains the revoked state. This is handled exception-path behavior in one live process, not a process-crash injection or a claim to have fixed atomicity between native jobs and SQLite. No real native job continued or restarted in this review.

## Disposition against the nine exact old findings

| Finding | Executed disposition on integrated bytes |
| --- | --- |
| F01 | Original feed-to-agent and changed-prompt admissions are blocked. Supplemental `authority_identity` checks manual/chat, schedule and source-write admission, including a stripped hosts-only grant and a matching reapproval control. Source data/cursor remain unchanged on denial. No per-run native tool sandbox is claimed. |
| F02 | Stale cadence/timezone/purpose/requested_at and supplied stale upkeep return conflicts without native creation. Rendered UI submits the exact displayed values, shows prompt/model cost before approval, and refetches after conflict. REST omission remains R01. |
| F03 | Bound session reaches real Net fetch. Closing at the first 307 stops the second connection/send; Net-revoke and open-session controls pass. Additional DNS, connection-factory and body-read closures suppress new sends or delivery at their tested seams. The already-sent first request is not recalled. |
| F04 | Supplied stale revisions roll back the entire source batch, metadata and change cursor. Seven invalid supplied types/values also roll back prior operations. Identical stale payloads still conflict. Omitted revisions preserve idempotent unchanged upserts and allow changed-source upserts while retaining user fields. |
| F05 | An unmirrored running native-ledger execution is discovered before revocation cancellation. Supplemental backlog test discovers two running records, requests one cancel per job, and persists canceled states. The adapter-unavailable exception regression is R02. |
| F06 | Exact request-change/deny workflow preserves previously unmirrored completed history and last success. Supplemental pointer removal retains all 1,505 imported history records. No late native completion after removal was qualified. |
| F07 | Unique-timestamp pagination imports 1,502 completed, one missed and two running executions, with 1,505 distinct durable IDs despite display limit 1 and repeated sync. Missed work is blocked with its reason and does not consume a queued manual run. Same-timestamp cursor limit remains below. |
| F08 | Approved literal loopback and mixed public/private DNS are rejected before transport. Public feed fetch works with Net revoked. Supplemental real feed/shared-helper/`_PinnedHTTPS` path uses a mocked numeric socket destination and exact hostname TLS/Host. Actual DNS, TLS peers and sockets were not used. Refresh remains separate from Net. |
| F09 | Separate subprocesses commit revocation after the initial public check and before approval or Resume obtains its write transaction. Both real REST calls return 403/not_granted with no create/resume calls; regrant leaves requested/paused state. This closes the old activation race. R02 covers the distinct cancellation exception path. |

## Frozen test and legacy assertion audit

`audit-tests.py` compares complete method source bodies against `e45e094b81c19e3cfc0950cb4148f7f7188cd06e` before examining assertions. It found **309 unchanged test-method bodies and exactly ten changed bodies**. The unchanged count includes all 27 frozen regression methods. Method definitions and executed counts differ because stock discovery also executes inherited methods. No method was added or removed in these files.

The ten changed names exactly match the supplied green audit. They comprise one REST adapter method, two agent integration methods, one feed-limit method and six upkeep transport methods. Fixture changes supply the transactional grant predicate, renew exact Refresh authority after a prompt change, add the displayed schedule fields, and observe the shared pinned transport.

Across those ten bodies, the only removed assertions are the authorized exact schedule forwarding assertion, HTTPX constructor assertion and old grant-check call count. Their replacements verify forwarding the four-field snapshot, pinned destinations/deadlines, request ordering and Refresh checks. Other behavioral assertions are preserved verbatim. All 27 AST method hashes match `frozen-methods.json`. Complete per-method old/new hashes and assertion inventories are retained in `test-audit.json`. The source diff was also read against the old bytes; the audit does not substitute a normalized/masked body comparison for scope review.

## Constraints, dropped suspicions and handoff

**Timestamp-only cursor limitation.** The available native `list_executions` interface pages by `before_claimed_at` without an ID tie-breaker. The bounded synthetic `timestamp_cursor_limit` probe confirms that 501 entries sharing the exact same timestamp yield only 500 imported rows after repeated sync. This is the disclosed upstream limitation, not a new repair finding. Unique-timestamp backlog success does not establish that arbitrary same-timestamp history is fully importable. Native retention and ledger availability also bound recovery.

**Dropped unproven suspicions: two.** An old native agent retaining an earlier prompt after a later reapproval was not qualified as an authority defect; the accepted design does not add per-run native tool capabilities. A native completion arriving after schedule-pointer removal was not established under real native removal/interruption semantics. Neither is promoted from source reading into a reproduced finding. The prior review's C01 manual/recurring native-overlap candidate remains parent-owned and unqualified here. Its previously dropped schedule-replacement history hypothesis is not reopened.

**Residual risks.** Native-job changes and Space SQLite remain separate stores with known crash windows. These probes do not establish distributed atomicity or interruption of actual model/tool execution. Network authority checks are synchronous observations, not an atomic fence; already-sent bytes cannot be recalled and changes can race the last check. History synchronization now holds a Space write transaction through backlog import/native lifecycle calls; no contention or latency benchmark was performed. JSDOM proves rendered markup and event payloads, not Electron focus, IPC, native cancellation or installed-package behavior.

The Build the Lever and Prove It Works principles shaped the retained executable probes, real REST replay and final byte verification. Model the Domain shaped the explicit case/observation maps rather than a second product implementation. No product repair was made.

**NOT done.** No tracked edits; no test edits; no credentials or live profile reads; no Desktop, gateway, ticker, model or nested-agent execution; no real sockets, DNS, network or listeners; no installs, persistent host/profile changes, pushes, merges or PRs. Installed source/dependency packages were read only as needed by stock synthetic tests. Disposable bundle, SQLite and render artifacts remain under `.run`. No release acceptance, cross-family gate, real native security result or live requalification is claimed.

All launched review processes have completed. The parent owns reproducer replay, issue disposition, any repairs, native/Desktop/network requalification and promotion. The review's final state is **ISSUES**, with two reproduced P2 findings and green requested stock suites.
