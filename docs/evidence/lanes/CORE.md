# CORE lane report

ISSUES. Living Spaces needs one durable store shared by its application, chat tools and upkeep. CORE implements that store and its project, revision, grant, session and bridge APIs. The final executable suite passes 59 tests. Required discovery and Git commits are blocked by the checkout and sandbox conditions below. This is unit-level evidence, not release-1 acceptance.

## Built

All implementation changes are inside `src/living-spaces/living_spaces_core/`.

- `db.py` preserves schema version 1, WAL, foreign keys and IMMEDIATE writes. Reads use consistent transactions. Schema initialization handles a deleted database at a previously used path. An additional record-history index supports revision lookup.
- `projects.py` implements stable slug identities, exact name resolution, content-addressed blobs, immutable revisions, manifest extraction, project reads and bundles, exact single-match edits, stale-head conflicts, compatible code restore, lifecycle controls and lazy upkeep hooks. Requested vendor files copy from the package runtime. Missing kit files produce warnings. Explicit import mappings survive library injection.
- `records.py` implements optimistic concurrency, atomic batches, source/user field separation, equality queries, ordering, pagination, change cursors and full recovery snapshots. Record revisions increase across delete/recreate and recovery restore. Source provenance changes create a change; a fetch timestamp alone does not.
- `migrations.py` validates declared operations and applies version increases inside the revision transaction. A savepoint lets failed migrations roll back code, records, changes and blobs while retaining the preceding recovery point. Unexpected migration exceptions also retain that point.
- `grants.py` implements default data/log grants, scoped refresh requests, host-widening invalidation, decisions, subset checks and redacted audit history. Capability disclosures and future capability labels are exposed.
- `sessions.py` binds sessions to one Space and rejects closed, unknown or mismatched sessions.
- `logs.py` enforces call/message bounds, redacts secret patterns before persistence and retains the last 2,000 entries per Space.
- `limits.py` exposes the release-1 numbers and validates identifiers, paths and JSON values. Limit failures carry numeric `limit` and `actual` values.
- `bridge.py` checks sessions first, then capabilities and argument shapes. Space arguments cannot change the bound identity. Record and log mutations recheck authorization within their write transaction. Results are checked again before delivery. Missing upkeep handlers return `blocked` with `reason=no_handler`.
- `__init__.py` re-exports the required modules and `SpacesError` without eager upkeep imports. The seeded `errors.py` needed no changes.
- `tests/python/test_core_store.py` contains the 59 tests in project, record, migration, authority and storage/log suites. Every test uses a fresh directory beneath `.run/` for both database and Hermes home. Upkeep is isolated or replaced with local fakes. Tests perform no network calls.

Model the Domain shaped the immutable revision and separate record structures. Prove It Works shaped the executable concurrency, rollback and failure-injection checks.

## Verification

Commands ran from this worktree using Python 3.11.15.

```sh
~/.hermes/hermes-agent/venv/bin/python -m unittest discover -s tests/python -t . -p 'test_core_*.py' -v
```

FAIL before test discovery, twice. Zero tests ran. Python reports `ImportError: Start directory is not importable` for `tests/python`. This seed has neither `tests/__init__.py` nor `tests/python/__init__.py`. Both marker paths are outside CORE's explicit ownership, so CORE did not add them.

```sh
~/.hermes/hermes-agent/venv/bin/python -m unittest discover -s tests/python -p 'test_core_*.py' -v
```

Actual run sequence for this same command:

1. Initial suite passed 47 of 47 tests.
2. Added regression cases ran 55 tests with 47 passing, 6 failing and 2 errors. These reproduced authorization races, quoted-secret redaction, audit JSON corruption, invalid accent handling, source provenance updates and schedule removal reporting.
3. After fixes, all 55 tests passed.
4. Expanded suite passed all 59 tests.
5. Final suite after the history index change passed all 59 tests, with zero failures or errors.

```sh
~/.hermes/hermes-agent/venv/bin/python -m compileall -q src/living-spaces/living_spaces_core tests/python

git diff --check
```

Both commands passed with exit code 0. No separate repository test or lint gate is configured in this seed.

## Not done or unproven

- No real Desktop, chat-model, REST, sandbox or cron integration ran. A fresh Python subprocess verifies record persistence; it does not verify full Desktop/backend restart acceptance.
- Real upkeep cancellation, schedule pause/removal and refresh execution remain integration work. CORE tested the frozen lazy hooks with local fakes and the absence of handlers. It did not edit `runs.py`, `feeds.py` or `schedules.py`.
- Missing kit behavior was tested with a temporary runtime fixture. The three shipped vendor files were also copied and checked against their actual SHA-256 hashes. A real kit render remains unproven.
- Limit failures were tested for oversized records, source fields, batches, bridge payloads and logs. Project count/size and record-count boundaries use lowered constants to exercise rollback without allocating maximum-sized fixtures. Maximum-capacity stress and power-loss behavior remain unproven.
- No packages were installed. No Hermes service, app or scheduler was started, stopped or restarted. No live profile was written.
- No commits were created and nothing was pushed. The attempted `git add` failed before `git commit` could run because the sandbox refused creation of the worktree's `.git/worktrees/core/index.lock` with `Operation not permitted`. All changed files remain in this worktree for Forge to review and commit. No sandbox workaround was attempted.

## Contract issues

The frozen contract file is unchanged.

- Section 4 calls the `changes_since` result cursor “latest” while allowing a limited page. Returning the database maximum for a partial page would permanently skip changes. CORE returns the last delivered sequence for a nonempty page. A test verifies traversal through multiple one-change pages without loss. Forge should clarify this cursor wording before consumers assume it is a separate high-water mark.
- Collection migration operation fields are unspecified. CORE uses `{op, from, to}` for `rename_collection` and `copy_collection`. Field migration operations affect user-owned `data`; source fields and provenance survive collection moves/copies.
- Cross-version recovery-point restore behavior is unspecified. CORE blocks it with `incompatible` so the current code cannot silently read an older data schema. Compatible restores take a fresh recovery point first, replace records and leave code history untouched.
- Section 6 requires one transaction per fetched source, but section 4 requires each public `upsert_source` call to open its own transaction. Calling that public function repeatedly cannot supply source-wide atomicity. CORE provides the private connection-taking `_upsert_source` helper used by its own implementation; Forge and upkeep must settle how their source transaction uses this helper without changing the frozen public API silently.
- Python 3.11 discovery needs the two package markers described above. Forge must supply them or change the prescribed discovery command.
