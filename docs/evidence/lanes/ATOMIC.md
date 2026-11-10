# Atomic source integration repair

Living Spaces users need saved source data they can trust across app, chat, and upkeep. A failed source now rolls back its complete write, including its change cursor, and reports zero committed changes.

The owned worktree is `/Volumes/Expansion/Development/Projects/living-spaces-wt/atomic`, on branch `forge/r1-atomic`. Before editing, `pwd`, `git rev-parse HEAD`, and `git status --short` verified that directory, exact base `2b94d99bac23681a7f4cb6b8e46e91bdc4f45d91`, and a clean tree.

The requested model policy, poteto skill, both reference files, contracts including A1, and all seven named code/test inputs were read. This implementation commission's fixed API, file scope, offline execution, and frozen acceptance take precedence over broader coordinator workflows. No subagents, network lookups, installs, gateways, live profiles, or cron services were used.

Changed files are limited to:

- `src/living-spaces/living_spaces_core/records.py` adds `upsert_sources`. It validates the entry list, the existing 500-operation batch bound, collection, actor, entry shape, and writable Space. Every valid entry uses the unchanged `_upsert_source` in one `db.write` IMMEDIATE transaction. Existing source, metadata, record-capacity, provenance, user-data, and no-change rules remain in that helper. Counts return after commit. Feed metadata supplies the hosts for an effective refresh-grant check on the same connection before commit, while the write lock excludes concurrent revocation.
- `src/living-spaces/living_spaces_core/feeds.py` constructs the complete entry list and calls `upsert_sources` once. It adds counts only after the API returns. Production has no per-record fallback. The existing feed limit remains 200 entries. This follows the repair instruction that supersedes A1's historical fallback allowance.
- `tests/python/test_upkeep_runs.py` migrates the records fake to a shared transaction. Both second-write faults remain. The old partial-prefix case now requires zero counts, records, and change rows. The existing rollback case now runs without `expectedFailure` and still requires prior records to remain identical. All 42 cases remain. The other 40 test method bodies are byte-identical to the base.
- `ATOMIC_REPORT.md` records this repair and its evidence.

All test commands ran from the owned worktree using the existing interpreter. The environment prefix was `TMPDIR="$PWD/.run/atomic-repair/tmp" PYTHONDONTWRITEBYTECODE=1`. Fixture homes, databases, temporary directories, and logs stayed under `.run/`.

| Command | Outcome |
| --- | --- |
| `/Users/ifedayoakinduro/.hermes/hermes-agent/venv/bin/python -m unittest tests.python.test_integration_source -v` before repair | Exit 1. Ran 4 tests. 3 passed, 1 behavioral failure, 0 errors, 0 skips. The first row remained after the injected second-write OSError. |
| Same integration command after repair | Exit 0. Ran 4 tests. 4 passed, 0 failures, errors, skips, or expected failures. |
| `/Users/ifedayoakinduro/.hermes/hermes-agent/venv/bin/python -m unittest discover -s tests/python -t . -v` | Exit 0. Ran 105 tests. 104 passed, 1 skipped, 0 failures, errors, or expected failures. The formerly expected rollback failure is an ordinary pass. |
| `git diff --check` | Exit 0. No whitespace errors. |

Logs are retained locally in `.run/atomic-repair/integration-before.log`, `integration-after.log`, and `python-suite.log`. The AST/source comparison in `scope-audit.log` verified the permitted test migration and unchanged frozen integration file. Its SHA-256 before and after is `7ec09d11e8663e59051c9e3a22aaec5526fa1f49b47055292199806c2942a7b9`.

Additional inline real-core probes ran with the same interpreter and `-B`, exiting 0. `source-probes.log` records five passing groups. They cover exactly one BEGIN IMMEDIATE/COMMIT, unchanged counts and cursor, user-data preservation, six invalid batch controls, record-capacity rollback, revocation between the final feed precheck and batch entry, transaction-exit failure without published counts, and writable-Space enforcement even for an empty batch. These are supporting probes, separate from the stock suite counts.

The Model the Domain principle kept A1's list of triples and count dictionary without another abstraction. Prove It Works required the unchanged real integration gate and direct transaction probes. The diff review followed the deslop guidance and found no unrelated edits.

The sandbox denied binding the local HTTP fixture with `[Errno 1] Operation not permitted`. That test was skipped, not passed. Mock HTTPS transport coverage passed. No live transport, service behavior, independent acceptance review, push, merge, or deployment is claimed. This is an implementation handoff for parent review, not a landed change.

After `git diff --check` passed, the attempted command was `git add src/living-spaces/living_spaces_core/records.py src/living-spaces/living_spaces_core/feeds.py tests/python/test_upkeep_runs.py ATOMIC_REPORT.md && git commit -m "Commit feed source records atomically"`. It exited 128 during `git add` because Git could not create `/Volumes/Expansion/Development/Projects/living-spaces/.git/worktrees/atomic/index.lock`, reporting `Operation not permitted`. The commit command did not run. No commit or push was made. All four files remain available in the owned worktree for the parent to review and commit.
