# w2-limits R1-08 report

Living Spaces must retain usable projects and coherent records when work fails, and must report resource limits without pretending a rejected write was saved.

**Verdict: ISSUES.** The owned core changes and all executable local gates pass. Three defects were reproduced and fixed. Real Desktop qualification remains for Forge. Source audit found unresolved sandbox and upkeep error-reporting issues outside this lane's ownership. Git staging itself is blocked by the sandbox, so nothing is committed or staged.

Branch `forge/r1-w2-limits`. Base and unchanged HEAD `0aaebc35da217e11511bf678b9f4b88fc5add4e0`.

## Changed files

| File | Change |
| --- | --- |
| `src/living-spaces/living_spaces_core/feeds.py` | Measure text feeds in UTF-8 bytes. Use the same compact UTF-8 JSON serialization as records for source size. Derive feed constants from `limits.py`. |
| `src/living-spaces/living_spaces_core/projects.py` | Validate the final normalized manifest before persisting a revision, including defaults and bundled import entries. Reuse the checked serialization for storage. |
| `tests/python/test_core_limits.py` | 21 tests covering real frozen boundaries, rejection, rollback, recovery, retention, and real registered agent handlers. |
| `tests/python/test_core_interruptions.py` | Four tests injecting exceptions after actual SQL mutations, including a refresh run that fails visibly and then recovers. |
| `harness/qualify_limits.py` | Complete isolated Desktop harness using `guest_realm.guest`, the shipped save-state kit, registered agent handlers, canonical snapshots, and fixture cleanup. Not executed. |
| `LANE_REPORT.md` | This handoff and the verification receipts. |

No contract, grants, runs, schedules, UI, sandbox, skill, or shipped bundle changes. Temporary test databases and verification artifacts stayed under the worktree's ignored `.run/` directory. No package install, push, Desktop/gateway launch, or listener was performed. The stock Python suite attempted its existing local-server fixture, which the sandbox refused and the suite skipped.

## Red then green

The first focused run executed 24 tests. It had 21 passes and these three failures. Its log is `.run/w2-limits/red.log`.

| Defect | Red evidence | Repair and green evidence |
| --- | --- | --- |
| Feed source size disagreed with canonical record serialization. | `test_feed_source_limit_uses_canonical_record_encoding_and_recovers` expected `actual=65537`, received `65548`. The old serializer also expands non-ASCII characters, rejecting otherwise valid source content. | `limits.object_json` now measures exactly what records store. The test verifies the rejected size, unchanged database, and a valid Unicode retry. |
| A text feed could exceed 3 MB in UTF-8 while passing a character-count check. | `test_feed_text_byte_limit_uses_utf8_and_recovers` failed with `SpacesError not raised`. | Measure UTF-8 bytes for string input. The test verifies the exact byte count, no write, and a valid refresh retry. |
| A normalized manifest could exceed 8 MB after defaults were added. | `test_normalized_manifest_cannot_exceed_file_limit` failed with `SpacesError not raised`. | Check the final manifest in `_save_revision`. The test verifies a typed error with the final serialized size, whole-database rollback, and a successful next revision. |

After the fixes, the same 24 tests passed in `.run/w2-limits/green.log`. One additional real agent-handler integration test brought the final focused count to **25 passed, zero failed** in `.run/w2-limits/focused-final.log`. No product changes followed that green run.

The initial red-run shell wrapper tried to assign zsh's read-only `status` variable after unittest finished. The test log above contains the completed 24-test failure report. Later wrappers use `test_exit` and preserve the test command's exit code.

## Frozen limit audit

The tests use the real published constants, not reduced mock caps. Rejection assertions compare `code`, numeric `limit`, exact numeric `actual`, a nonempty message, and the complete logical SQLite dump hash before/after. Each rejection has a valid retry. Boundary payloads are generated locally and contain only public fixture content.

| CONTRACTS limit | Proof in `test_core_limits.py` |
| --- | --- |
| Project 25 MB | `test_project_bytes_count_duplicate_blobs_per_file_and_retry_at_boundary`. Counts shared blobs once per logical file, rejects total + 1, rolls back inserted blobs, accepts the exact boundary. |
| Project 600 files | `test_file_count_is_resulting_project_and_retry_at_boundary`. Includes pre-existing files, rejects 601, accepts 600. `test_failed_create_leaves_no_space_grants_revision_or_blobs` also covers failed creation. |
| File 8 MB | `test_file_limit_counts_utf8_bytes_and_retry_at_boundary`. Uses multibyte text, rejects + 1 byte, accepts exactly 8 MB. Final manifest size has its own regression above. |
| Record data 256 KB | `test_data_limit_rejects_whole_batch_and_retry_at_boundary` rejects the second operation and rolls back the first. Exact-boundary retry succeeds. `test_data_limit_checks_merged_record_and_utf8` covers merged size and multibyte data. |
| Source 64 KB | `test_source_and_metadata_limits_leave_prior_record_and_retry_at_boundary` covers both source and separately bounded source metadata. Notes survive. `test_source_batch_rolls_back_earlier_source_on_limit_and_recovers` covers A1 batching. Feed serialization is covered separately. |
| 50,000 records | `test_record_capacity_across_collections_is_atomic_and_recoverable`. Direct SQL seeds 49,999 fixture rows for speed, without lowering the cap. A two-record public batch crossing the cap rolls back. Record 50,000 succeeds. New user and source records at capacity fail with 50,001; existing records remain editable; deletion creates room for a successful source retry. |
| Batch 500 | `test_batch_limit_and_retry_at_boundary` and `test_source_batch_limit_and_retry_at_boundary`. Reject 501, store none, accept all 500 without truncation. |
| Logs 2,000 retained | `test_log_history_keeps_exactly_last_2000_per_space`. The 2,001st is accepted and evicts only the oldest entry. Another Space is unchanged. Further writes succeed. This is the designed retention exception, not a rejecting limit. |
| Log call 50 / message 4,000 characters | `test_log_batch_and_message_limits_are_atomic_and_recoverable`. Rejects 51 and 4,001, rolls back the entire call, accepts exact bounds with no core truncation. These additional bounds are frozen in §7. |
| Bridge 1 MB | `test_bridge_limit_returns_numbers_stores_nothing_and_recovers`. Each constituent record is below its own cap, so the aggregate envelope is the limiting resource. Tests actual `bridge.dispatch`, structured error numbers, no write, and a successful same-session retry. Renderer behavior remains an issue below. |
| Feed 3 MB | `test_feed_bytes_and_entries_reject_whole_source_and_recover`, `test_feed_text_byte_limit_uses_utf8_and_recovers`, and `test_feed_stream_byte_limit_stops_without_writes_and_recovers`. The stream test uses an in-process fake HTTP client, never a listener. Byte parsing accepts the exact boundary. |
| Feed 200 entries | `test_feed_bytes_and_entries_reject_whole_source_and_recover`. Rejects 201 without changing existing data, then successfully refreshes; parses all 200 at the boundary. |

`test_frozen_limit_values` asserts the complete advertised limit dictionary. `test_registered_handlers_keep_limit_numbers_atomicity_and_recovery` invokes actual handlers registered by the plugin, without a mocked core, for oversized batch, data, file, and file-count writes.

## Interrupted work

The injected failure occurs **after** `Connection.execute` has run the selected mutation. Tests also assert that the selected failure point was reached.

- Project writes are interrupted after the second blob insert, after revision insertion, and after the head update. Both `OSError` and `KeyboardInterrupt` roll back all state. The original bundle stays equal and loadable. A valid retry creates revision 2 exactly once.
- A batch updates one record, deletes another, and inserts a third. An exception after the third change-cursor insert rolls back all three operations and their cursor entries. Both ordinary exceptions and interruption exceptions are covered. The next identical batch succeeds.
- A feed source refresh fails after its second record change. Source values, metadata, revisions, user notes/status, and the cursor remain unchanged. Counts do not claim rolled-back work. The next refresh updates two records and adds one while retaining user fields.
- A full `runs.start_refresh(..., wait=True)` using a fake fetcher records the injected source failure as `failed`, names the interrupted write, reports zero changes, and retains records. The next run succeeds. A1's `upsert_sources` transaction is exercised through the real feed path.

No transaction repair was needed for these cases. They passed before the three limit fixes. Exception injection is not an OS kill or a power-loss test; restart persistence was outside this lane because it was already proven.

## Commands and outcomes

All commands ran from this worktree. Raw logs are in `.run/w2-limits/` and are intentionally not committed.

| Exact verification command | Actual outcome |
| --- | --- |
| `~/.hermes/hermes-agent/venv/bin/python -m unittest discover -s tests/python -t .` | Baseline 151 run, 150 passed, one skipped, zero failures (`python-baseline.log`). After initial fixes, 175 run, 174 passed, one skipped (`python-after-fixes.log`). |
| `~/.hermes/hermes-agent/venv/bin/python -m unittest tests.python.test_core_limits tests.python.test_core_interruptions` | Red 24 run / three failed (`red.log`); green 24 passed (`green.log`); final 25 passed (`focused-final.log`). |
| `~/.hermes/hermes-agent/venv/bin/python -m unittest discover -s tests/python -t . -v` | **176 run, 175 passed, one skipped, zero failures** (`python-final.log`). |
| `node --test tests/js/sandbox/*.test.mjs tests/js/reference/*.test.mjs` | Baseline 67 reported, 63 passed, four failed (`js-baseline.log`). Three files could not resolve `preact`; the renderer graph check lacked `.run/package/desktop-metafile.json`. |
| `esbuild src/desktop/plugin.src.js --bundle --format=esm --jsx=automatic --external:@hermes/plugin-sdk --external:react --external:react/jsx-runtime --outfile=.run/package/desktop-renderer.js --metafile=.run/package/desktop-metafile.json` | Passed. Built only ignored test artifacts (`renderer-build.log`). No shipped bundle changed. |
| `node --import ./tests/js/sandbox/env.mjs --test tests/js/sandbox/*.test.mjs tests/js/ui/index.js tests/js/reference/*.test.mjs` | 113 reported, 112 passed, one failed (`js-final.log`). Reference tests require VM modules. |
| `node --experimental-vm-modules --import ./tests/js/sandbox/env.mjs --test tests/js/sandbox/*.test.mjs tests/js/ui/index.js tests/js/reference/*.test.mjs` | **131 passed, zero failures/skips** (`js-qualified.log`). Uses the existing vendor resolver and actual UI suite filename. |
| `node tests/js/ui/render-smoke.mjs` | **40 assertions passed**, 12 static HTML fixtures (`ui-render.log`). No browser launched. |
| `~/.hermes/hermes-agent/venv/bin/python -m py_compile harness/qualify_limits.py tests/python/test_core_limits.py tests/python/test_core_interruptions.py` | Passed. |
| `node --check .run/w2-limits/probe.mjs` | Passed. The fixture's `SCRIPT` constant was extracted with Python `ast.literal_eval`, without importing or executing the Desktop harness. |
| `node --check .run/w2-limits/host-probe.js` | Passed. The host observer expression was likewise extracted without executing the harness. |
| `git diff --check` | Passed. |
| `git diff --no-index --check /dev/null tests/python/test_core_limits.py` | Passed. Checks the untracked test file despite blocked staging. |
| `git diff --no-index --check /dev/null tests/python/test_core_interruptions.py` | Passed. |
| `git diff --no-index --check /dev/null harness/qualify_limits.py` | Passed. |
| `git diff --no-index --check /dev/null LANE_REPORT.md` | Passed. |

The four `--no-index --check` commands emitted no whitespace diagnostics. Their exit code is 1 because each file differs from `/dev/null`; that is not a whitespace failure. The normal `git diff --check` exited 0.

The one Python skip is the existing network fixture:

```text
test_manual_refresh_from_local_server_has_provenance_and_timestamps
Sandbox forbids binding the local HTTP fixture: [Errno 1] Operation not permitted
```

The intermediate JavaScript errors were:

```text
ERR_MODULE_NOT_FOUND: Cannot find package 'preact'
ENOENT: no such file or directory, open '.run/package/desktop-metafile.json'
SyntaxError: The requested module 'node:vm' does not provide an export named 'SourceTextModule'
```

## Desktop harness for Forge

**Written and syntax-checked only. No Desktop pass is claimed.** Run serially after integrating/reloading the relevant plugin code in the existing isolated app. The harness inherits the isolated paths and CDP setup from `qualify_schedule.py` and `guest_realm.py`. It verifies that both helpers and core resolve the same isolated database before creating a Space. It does not start or stop the app or gateway.

```sh
~/.hermes/hermes-agent/venv/bin/python harness/qualify_limits.py
```

The harness does the following:

1. Moves to the index, waits for protected frames/sessions to close, and captures complete canonical snapshots of `research-desk` and `pair-play`. Includes every scoped table and the bytes of blobs referenced by every revision, not a hardcoded collection list.
2. Refuses to overwrite a pre-existing `limits-probe`. Creates that disposable Space through core with public fixture content and the shipped kit.
3. Exceeds batch and record-data limits through the guest realm. Also exceeds the bridge envelope cap. A prior successful guest write establishes Saved before each rejected attempt, so a stale Saved indicator cannot pass accidentally.
4. Exceeds batch, record-data, project-file size, and project-file count through the plugin's real registered tool handlers. Handler calls use the registration pattern from `test_agent_adapters.py` with real storage.
5. Checks typed error numbers, canonical non-mutation, visible frame save state, host status/alert/toast text through a mutation observer, and screenshots. Reopens the old revision and verifies a valid retry persists. Host text saying `Not saved` is not misclassified as success.
6. Deletes only the fixture it created in `finally`, even if a scenario fails. Writes protected after-snapshots and requires byte equality. It neither rewinds nor repairs protected Spaces.

Receipts go to `evidence/limits/<timestamp>/` under the existing isolated run directory. `limits.json` reports every assertion, captured errors, frame/host observations, cleanup outcome, and before/after SHA-256 values. The process exits nonzero if any check fails. Missing numeric errors are recorded without stopping later scenarios. This is a fixture/adapter qualification, not a model-chat test or a claim about every generated app's save UI.

## Open issues outside owned paths

These findings are from current source inspection, not a Desktop run. They are not covered up by the passing core tests.

1. **Renderer bridge limits lose numbers.** `src/desktop/sandbox/index.js:93` returns only `code` and `message` for an oversized envelope. It omits both `limit` and `actual`. The harness deliberately tests this and is expected to fail until the sandbox owner fixes it. Measure UTF-8 bytes too; `validateRequest` currently uses JavaScript string length at line 23, while core measures UTF-8 bytes. Backend enforcement remains present.
2. **Locally rejected writes bypass the host save-state path.** The same early return at `src/desktop/sandbox/index.js:95` does not invoke `call`. `src/desktop/ui/session.mjs` updates save state only inside that call. After a successful write followed by an oversized envelope, source control flow leaves the host's previous Saved state intact while the guest gets an error. This is a source-derived failure scenario, pending Desktop confirmation. Route local write failures into the host write-status path without authorizing the operation. The harness primes Saved to test it.
3. **Guest diagnostics silently truncate individual messages.** `src/guest/loader.mjs:148` uses `.slice(0, 4000)` without a truncation marker or original length. Queue overflow has a warning, but individual message truncation does not. Core rejects an oversized message correctly. The sandbox owner should preserve bounded diagnostics with an explicit truncation notice and actual count, or return a typed limit for a caller-driven log operation.
4. **Host log-limit errors use the wrong shape.** `src/desktop/sandbox/index.js:108` combines malformed log entries and numeric excess; line 111 returns `invalid` without numbers for 51 entries or a 4,001-character message. Core returns `limit` with both numbers. Separate malformed input from exceeded limits.
5. **Refresh run reporting discards structured limit errors.** `src/living-spaces/living_spaces_core/runs.py:159` stores `str(exc)` rather than `SpacesError.to_dict()`. For the feed-entry limit and streamed byte limit, the messages in `feeds.py:94` and `feeds.py:49` contain the maximum but omit `actual`; the numeric extras are lost to the run reader. Preserve structured error information in the failed source detail and make the user-visible message include both values. This lane did not edit `runs.py`.

## Contract issues and spec gaps

- **Bridge error shape and rejection text.** §4/§10 require numeric limit errors, while §7 sketches only `code/message/current?` and still says oversized messages are dropped. Current renderer replies already differ from that drop wording. Forge should clarify that usable request IDs receive typed limit replies with `limit` and `actual`, and that local rejection also updates host save state. No contract edits were made here.
- **Log retention disclosure.** Spec §2 explicitly calls diagnostics bounded, and §4/R1-09 also requires bounded diagnostics. CONTRACTS §10 explicitly retains only the last 2,000. Neither spec section explicitly requires an eviction event or changes the frozen list-shaped `read_logs` return. The existing retention is therefore intentional and was not replaced with rejection or fabricated log rows. The reader currently gets no retention metadata from `read_logs`, and the Diagnostics permission copy does not say 2,000. Given §4's truthful-limits language, proposed resolution is visible host/tool copy saying “Only the latest 2,000 diagnostic entries per Space are retained,” with a deliberate contract amendment if eviction counts are wanted.
- **Project total and virtual manifest.** §3 explicitly excludes `space.json` from the project file map. Current 25 MB/600-file accounting uses that map; the manifest has its own 8 MB check. Tests preserve that behavior. §10's “total” does not explicitly say whether the virtual manifest counts. Forge should state the convention or commission inclusive accounting. This lane did not silently redefine it.
- **Refresh atomicity scope.** §6/A1 specify one transaction per source, while §6 also says every existing record keeps its source on failure. Spec §3 describes partial source failure without resetting unrelated records. The verified guarantee here is no partial write within the interrupted source. Already completed sources in a multi-source run are not rolled back. Forge should qualify “every existing record” as belonging to the failed source, or explicitly require a run-wide transaction.
- **Migration recovery points.** Existing project writes intentionally retain a recovery point when a data-version migration fails. The new ordinary-write rollback tests assert zero database changes; they do not redefine that documented recovery exception as a defect.

## Not done and Git handoff

No Desktop run, restart run, process-kill test, real network fetch, live schedule action, model turn, protected-Space runtime equality check, or fix in another lane's paths was performed. Protected-Space equality is an assertion in the unexecuted harness, not an observed result. Forge must rerun the existing network fixture outside the sandbox and run the Desktop harness serially.

Attempted staging and commit sequence:

```sh
git diff --check && git add src/living-spaces/living_spaces_core/feeds.py src/living-spaces/living_spaces_core/projects.py tests/python/test_core_limits.py tests/python/test_core_interruptions.py && git diff --cached --check && git commit -m 'fix(core): enforce serialized limits and prove write atomicity'
```

It failed at `git add`, before any staging or commit:

```text
fatal: Unable to create '/Volumes/Expansion/Development/Projects/living-spaces/.git/worktrees/w2-limits/index.lock': Operation not permitted
```

Forge can commit the verified core unit first, then the harness/report:

```sh
git add src/living-spaces/living_spaces_core/feeds.py src/living-spaces/living_spaces_core/projects.py tests/python/test_core_limits.py tests/python/test_core_interruptions.py
git diff --cached --check
git commit -m 'fix(core): enforce serialized limits and prove write atomicity'
git add harness/qualify_limits.py LANE_REPORT.md
git diff --cached --check
git commit -m 'test(harness): qualify resource limit failures in Desktop'
```

Do not treat this lane as R1-08 acceptance until the open surface defects are addressed and Forge's actual Desktop receipts pass.
