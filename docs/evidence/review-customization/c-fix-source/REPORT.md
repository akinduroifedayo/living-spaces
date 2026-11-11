# F04 source-owned revision repair

Ife wants normal Hermes chat to build custom multi-view apps with durable data, internet and upkeep. This repair protects durable source fields from stale agent writes while preserving revision-omitting feed-like upserts. F04 is locally green. This lane is not integrated, landed or accepted for release.

## Scope and provenance

- Workspace `/Volumes/Expansion/Development/Projects/living-spaces-wt/c-fix-source`, branch `forge/r1-c-fix-source`, clean starting HEAD `e45e094b81c19e3cfc0950cb4148f7f7188cd06e`.
- Read `.run/packet/pins.json` first and all twenty-four required shards in full. These cover the complete review, new suite, fixture support, plugin and records module. Read `.run/red.log`, `.run/red-audit.json`, `.run/frozen-methods.json` and `.run/baseline.json` completely. Truncated displays were followed by bounded reads.
- Read the required model policy, Hermes Poteto skill and both named references. The commission requests Astra high fast with its explicit normal-tier override. No model launch or substitution was performed by this lane. Actual provider/model/effort/tier and fallback attribution remain the parent's session-receipt audit; this report does not claim wire verification.
- Ran `native-preflight.py --help`, then its supported `--workspace`, `--parent`, `--manifest .run/baseline.json` invocation. Direct exit 0; parsed `status=verified`, all 382 manifest paths and hashes matched. Receipt `preflight.json`. This is a pre-write workspace observation, not an OS sandbox.
- All 24 shard hashes and five original source hashes matched before the product edit. No repository-local AGENTS.md was found. Followed the supplied AGENTS instructions and the stock Python gate in `docs/contracts/CONTRACTS.md` section 12.
- Parent owns the independent review and integration stages. No nested delegation or additional model execution. No sibling issue was adopted.

## Exact owned deltas

Only `src/living-spaces/__init__.py` changed. `spaces_write_records` gained five lines immediately before source metadata preparation, inside the existing `core.db.write()` transaction.

1. Branch on key presence, `"base_rev" in op`, so omission is distinct from a supplied null.
2. Call existing `core.limits.integer` to require a nonnegative integer. Null, booleans, floats, strings, objects and arrays are rejected with `invalid`.
3. Call existing `core.records._ids` before the new SQL lookup, retaining identifier validation before binding inputs.
4. Read the row with existing `core.records._row` on the same transaction connection.
5. Call existing `core.records._concurrency`, preserving the existing `conflict` error and decoded `current` record (or null for a missing record).

No helpers, imports, new connection or transaction split were added. `records.py` is byte-identical. `BEGIN IMMEDIATE` already spans the batch; the existing exception rollback protects prior operations, source metadata, revisions, timestamps and the change cursor. The check precedes the upsert's unchanged-payload shortcut, so a stale revision cannot escape validation by sending identical source fields.

The sole other edit is the permitted `spaces_write_records` tool description. It scopes the existing omission/create guidance to user data and explicitly documents source-owned omission as an idempotent upsert without a revision check. Supplied revisions must match; zero is create-only. Schema properties, required fields, other tool descriptions and all 28 other plugin function bodies are unchanged.

The Model the Domain principle shaped the choice to retain the existing operation dict and distinguish the optional key at this boundary. No new abstraction was needed. Contract conflicts and test instrumentation migrations required by this lane: none.

## Verification

All test execution used `/Users/ifedayoakinduro/.hermes/hermes-agent/venv/bin/python`. `run-check.py` calls the actual interpreter/stock unittest commands in a subprocess and records its direct exit, full combined output, command, cwd, environment and log hash. `TMPDIR=.run/tmp`, `HERMES_HOME=.run/home` and the fallback database path are absolute paths inside this worktree. Environment inheritance is allowlisted; installed Hermes code and Node dependencies remain readable for stock tests. No test bytes or assertions were changed.

| Execution | Direct exit | Executed | Result |
| --- | --- | --- | --- |
| `-m unittest tests.python.test_review_customization -k f04 -v` before edit | 1 | 3 | 2 controls passed; 1 method failed at 3 subtest assertions |
| Same F04 command after edit | 0 | 3 | 3 passed |
| `-m unittest tests.python.test_review_customization -v` | 1 | 27 | 14 passed; 13 other-lane methods failed at 24 assertions |
| `-m unittest discover -s tests/python -t . -v` | 1 | 332 | 319 passed; same 13 other-lane methods failed at 24 assertions; all 305 old tests passed |
| `.run/probe-source-revisions.py` supplemental probe | 0 | 17 observations | Real adapter/SQLite behavior passed; not a replacement suite |
| `.run/audit.py` preservation/count reconciliation | 0 | 382 paths, 62 test files, 27 methods, 24 shards | Verified |
| `git diff --check` | 0 | Diff | No whitespace errors |

Every unittest run had zero errors and zero skips. Logs and receipts share these prefixes: `f04-before`, `f04-after`, `customization-after`, `discovery-after`, `source-probe`. `final-audit.json` contains reconciled identities/counts and full frozen-test hashes.

The red-to-green method is `tests.python.test_review_customization.ReviewCustomizationTests.test_f04_stale_source_revision_conflicts_and_rolls_back_whole_batch`. Before repair its three boundaries failed: stale source conflict, current source/metadata preservation, whole batch rollback. After repair all pass. Exact runner summaries:

```text
Ran 3 tests in 0.119s

FAILED (failures=3)
```

```text
Ran 3 tests in 0.145s

OK
```

Controls `test_f04_current_source_revision_preserves_user_fields_control` and `test_f04_stale_user_revision_still_conflicts_control` pass before and after. Full discovery also passes the unchanged `tests.python.test_agent_upkeep.AgentIntegrationSeamTests.test_source_owned_adapter_in_integrated_tree`, ordinary tool adapter tests, source transaction tests and core source-upsert controls.

The supplemental probe covers eight invalid revision values with rollback of an earlier insertion; stale/zero/future revisions on existing records including identical source payloads; missing-record conflict payload; matching and omitted-revision idempotence including unchanged timestamps/cursor; omitted-revision update preserving user data; zero-revision creation; and sequential same-record operations whose second stale revision rolls back the first. It uses the public synthetic fixture and real product functions/SQLite, with network blocked by the stock fixture.

## Remaining failures owned elsewhere

All names below are methods of `tests.python.test_review_customization.ReviewCustomizationTests`, present in the parent's frozen red audit. The after-run failure set equals that audit minus F04.

Consent lane (`c-fix-consent`):

- `test_f01_agent_prompt_change_blocks_manual_and_scheduled_admission`
- `test_f01_feed_to_agent_requires_fresh_refresh_approval`
- `test_f01_stale_agent_scope_cannot_approve_changed_prompt`
- `test_f02_matching_displayed_schedule_approves_exact_fields`
- `test_f02_stale_displayed_schedule_conflicts_at_rest_boundary`
- `test_f05_revoke_discovers_unmirrored_running_execution`
- `test_f06_denial_preserves_unmirrored_completed_history`
- `test_f07_history_backfill_includes_501st_execution`
- `test_f09_feed_approval_rechecks_separately_committed_revocation`

Network lane (`c-fix-net`):

- `test_f03_bridge_passes_bound_session_to_real_net_fetch`
- `test_f03_closed_session_prevents_redirect_post`
- `test_f08_feed_rejects_approved_loopback_before_transport`
- `test_f08_public_feed_uses_vetted_pinned_destination`

## Preservation, hazards and NOT done

Final audit verifies 381 of 382 baseline paths byte-identical; the sole changed path is the owned plugin. All 62 test files and 27 AST method pins match. All 24 original packet shards remain frozen. `LANE_REPORT.md`, generated bundles, other functions, consent/network modules and `records.py` are unchanged. Modified plugin SHA-256 is `12b7a25ef9f330100da6ddc4ff4771ac6a5d89246537caeeb6e215aafd93b24b`.

The adapter now reuses private records helpers in addition to its existing private source upsert. These are unchanged internal implementation dependencies. Omission deliberately remains unconditional source upsert behavior; callers needing concurrency protection must supply the revision. This is explicit in the tool description. No blind-override option or silent ignoring of a supplied revision was added.

No actual Desktop, gateway, model, ticker, network or listener execution. No credentials/live profile access, installs, host modifications, pushes, merges or PRs. Stock tests exercise synthetic transports and isolated temporary native cron storage, not live scheduling/model dispatch. Supplemental probes do not stand in for the real unittest suite. No generated product bundle build or commit. No JS-only gate claimed. The final package validator with installs and real Desktop acceptance remain parent-owned and were not run under this lane's prohibition on installs/runtime activity.

The repaired source needs parent integration and fresh review. Prior review gates do not automatically accept the new bytes. Full suite remains red only for the named other-lane defects. Nothing is left running in this lane.

## Local commit disposition

The permitted local commit could not be created. `git add -- src/living-spaces/__init__.py` exited 128 because Git could not create `/Volumes/Expansion/Development/Projects/living-spaces/.git/worktrees/c-fix-source/index.lock` (`Operation not permitted`). No escalation or alternate Git path was attempted. The product diff is left unstaged in the assigned worktree, with HEAD still at the frozen base. Parent can collect the diff and `.run` evidence directly.
