# UPKEEP lane report

**BLOCKED.** Living Spaces needs dependable refreshes and approved background upkeep that preserve user data. The implementation is present in this worktree. Source-wide storage rollback remains blocked by the frozen core API, the exact test gate cannot discover the unmarked test package, and sandbox permissions prevent staging or committing. This is not an R1 acceptance pass.

Branch `forge/r1-upkeep`. No commits or pushes were created.

## Built

- `src/living-spaces/living_spaces_core/runs.py` implements recorded blocked attempts, SQLite-serialized run claiming and deduplication, daemon and inline execution, ten-second heartbeats, recovery after 120 seconds without a heartbeat, queued cancellation, running cancellation at source boundaries, source progress, history and separate freshness facts.
- `src/living-spaces/living_spaces_core/feeds.py` implements HTTPS-only fetching with httpx, a 20-second timeout, streamed 3 MiB limit, per-request grant checks and rejection of off-host redirects. RSS and Atom parsing includes the arXiv API shape, stable source IDs, provenance, float timestamps, declaration guards including UTF-16/32, entry limits and complete parse validation before writes. It calls the declared `records.upsert_source` API and never deletes records.
- `src/living-spaces/living_spaces_core/schedules.py` implements requested schedules without job creation, explicit approval, native no-agent cron jobs, pause/resume, archive/unarchive/delete hooks and native next-run synchronization. Missing cron disables visibly. Disabled reasons persist in the existing audit table. Cadence changes pause the old job until approval. Missing cron prevents falsely reporting successful job deletion.
- `src/living-spaces/scripts/refresh_space.py` is the shim template. Approval substitutes the absolute package path and Space ID. The shim loads `_core.py`, calls `load_core()`, invokes `start_refresh(..., wait=True)` and prints nothing on success. Other outcomes print one error line and exit nonzero.
- `tests/python/test_upkeep_runs.py` contains 42 unittest cases and test-only core fakes. The records fake stores source and user data separately in the seeded SQLite schema and emits change rows. HTTP tests use injected fetchers or httpx transports. Native cron tests use temporary homes under `.run/` and import the installed cron implementation read-only.
- `tests/python/fixtures/feeds/research.rss` and `research.atom` contain synthetic public-looking research content.

The native cron record stores `id` and ISO-formatted `next_run_at`. The adapter converts the next-run instant to float Unix seconds. Paused schedules expose `next_run_at=None` while native cron retains its occurrence for catch-up. Jobs explicitly set `catch_up=True`. The catch-up copy constant matches the requested wording exactly.

## Verification

Commands ran from the worktree root using the prescribed interpreter.

```sh
~/.hermes/hermes-agent/venv/bin/python -m unittest discover -s tests/python -t . -p 'test_upkeep_*.py' -v
```

**FAIL before discovery, exit 1, zero tests run.** Both attempts raised `ImportError: Start directory is not importable`. Python is 3.11.15. The seed contains neither `tests/__init__.py` nor `tests/python/__init__.py`. Those paths are outside this lane's ownership. An optional scope question was sent; no answer was received before handoff, so neither marker was added.

```sh
~/.hermes/hermes-agent/venv/bin/python -m unittest discover -s tests/python -p 'test_upkeep_*.py' -v
```

Final result **42 run, 40 passed, 1 skipped, 1 expected failure, 0 unexpected failures/errors, exit 0**.

- The skipped case is `test_manual_refresh_from_local_server_has_provenance_and_timestamps`. Binding the local `http.server` fixture raises `PermissionError: [Errno 1] Operation not permitted` in this sandbox. The fixture remains available for a less restrictive runner. A separate passing manual-refresh case runs the production HTTPS fetch path through an injected httpx transport and verifies persisted provenance and timestamps.
- The expected failure is `test_source_write_failure_rolls_back_all_source_changes`. It updates the first existing record, injects a storage failure on the second upsert and observes that the first update remains committed. This is an unmet requirement, not a passing atomicity check.
- Passing cases cover unchanged refreshes, note/status preservation, last-good data after fetch and XML failures, partial multi-source failure, denied/absent/revoked/narrow grants with zero fetches, concurrent deduplication, daemon execution, cancellation, heartbeat advancement, stale recovery, freshness separation, feed security/limits, native cron lifecycle, missing cron, cadence reapproval and shim output behavior.
- Native tests asserted a job was persisted in the temporary home's `cron/jobs.json`, exercised native pause/resume/remove, checked the generated shim and removed the jobs. No scheduler or gateway was started.

Earlier runs of the same fallback command recorded development progress. The initial run had 15 tests, 14 passed and 1 error from the prohibited localhost bind. After adding the explicit skip and more cases, 38 ran with 37 passed and 1 skipped. Two subsequent runs each had 40 tests, 38 passed, 1 skipped and 1 expected failure. The final run above adds the injected HTTPS provenance case and the missing-cron deletion case.

`git diff --check` passed. Because all changes are untracked, an additional `git diff --no-index --check /dev/null <file>` check covers each of the eight deliverable files. No additional test/check runner or validator is declared in the seeded repository.

## Not done or unproven

- **Source-wide storage atomicity is not implemented.** Fetch, parse, declaration and entry-limit failures occur before writes and retain existing data. An error or process death between successful per-record upserts can leave a partially updated source. The run reports committed counts truthfully. See the contract issue below.
- The exact prescribed discovery command remains blocked by missing package markers outside lane ownership.
- Real localhost HTTP serving remains unverified because socket binding is prohibited. Production HTTPS behavior is tested through transport injection, not a remote network.
- Core `projects`, `records` and `grants` are still absent in this checkout. Integration with their real implementations needs verification after Forge integrates the lanes.
- Native cron storage and controls are verified. Actual scheduler execution, sleep/wake catch-up, closed-Space refresh, real Desktop behavior and real chat are not verified. No live services were started, stopped or restarted.
- Atomic recovery across SQLite, the shim file and the external cron store after process death is unproven. Ordinary create-job failure cleanup is tested.
- Staging and committing were attempted and rejected. `git add` and `git commit` could not create the worktree's `index.lock` and exited 128 with `Operation not permitted`. The worktree files remain untracked for Forge to stage and commit in a session with working Git metadata permissions. No alternate Git metadata or permission bypass was attempted.

## Contract issues

1. **Source transactions have no usable core seam.** CONTRACTS sections 4 and 12 expose only `records.upsert_source(sid, collection, rid, source, source_meta, *, actor)`. Section 0 says each public function opens its own connection. Section 6 requires all entries of a source in one transaction. The seeded `db.write()` also always opens a new connection. Wrapping upsert calls inside another `db.write()` cannot share the connection and would block the independent writers. Forge must coordinate a transaction-aware core seam or an atomic source-batch API before R1-06 can pass. This lane did not modify core-owned files, monkeypatch production database functions or duplicate record ownership logic.
2. **Disabled schedules have no reason column.** The lane commission explicitly requests status `disabled` with a visible reason, whereas section 6 also says to report `blocked` when cron is unavailable. The table permits `disabled` and does not permit `blocked`. This implementation stores `disabled`, persists its reason in `audit` under `schedule.disabled`, and includes `reason` in the returned disabled Schedule. Forge should confirm this serialization for the UI.
3. **The inline argument is absent from the frozen signature.** The commission and cron behavior require `wait=True`; sections 4 and 12 list only `trigger` and `actor`. This implementation adds backward-compatible keyword-only `wait=False` and uses `wait=True` in the shim.
4. **The required discovery gate needs shared test-package ownership.** Forge should add the two empty package markers or adopt discovery without `-t .`. This lane preserved its explicit file boundary.

## Decisions and handoff

The Model the Domain principle kept run and schedule status authoritative in SQLite, with cancellation reasons persisted in run detail. Prove It Works led to assertions against the real temporary cron store and an explicit expected-failure case for the missing atomicity guarantee. Both principle leaf skills were read in this session.

Forge should first resolve the source transaction seam, integrate the real core modules and add shared test package markers. Then rerun the exact unittest gate in an environment that permits the local fixture, remove the atomicity expected-failure annotation after implementing the guarantee, and verify actual isolated-app scheduling. Git permissions must also be corrected before the requested commits can be made.
