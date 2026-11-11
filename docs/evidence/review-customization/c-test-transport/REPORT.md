# Feed test transport migration

Ife wants safe maintained Spaces. This lane migrates the seven obsolete feed HTTPX test instruments to the shared pinned public HTTPS path without changing product behavior. The scoped migration passes. Full Python discovery remains red only for the expected consent-lane failures. Nothing is landed.

## Authority, baseline, and required reads

- Private cwd `/Volumes/Expansion/Development/Projects/living-spaces-wt/c-test-transport`.
- Branch `forge/r1-c-test-transport`. Clean starting HEAD `d4b14c06d7442a156729c68db447feb6cb55692f`.
- Read `.run/net-report.md` in full, including its seven-method inventory at lines 93–105. Read both scoped test files, `test_net.py`, `review_customization_support.py`, `net.py`, and `feeds.py` in full.
- Read `/Users/ifedayoakinduro/.agents/pstack-models.md`, `/Users/ifedayoakinduro/.hermes/skills/pstack/poteto-mode/SKILL.md`, and its `references/hermes-tools.md` and `references/gated-program-delegation.md` in full. Read Model the Domain, deslop, and no-comments guidance. No applicable repository AGENTS.md was found. The supplied AGENTS instructions and repository Python gate were followed.
- Requested route was Astra high fast, owner authorized. This session has no mechanism to change or verify its own model/effort/service tier. No model route was launched, substituted, or reconfigured. Runtime attribution remains unverified for the parent's receipt audit. No claim of wire verification.
- The explicit no-model execution and narrow test migration mandate supersede generic model delegation, arena, independent-review, and PR skill stages. The explicit stock-suite instruction authorizes worker execution despite the generic test-authoring reference's parent-only default. Parent owns final integrated acceptance.
- Bounded local memory search had no relevant entry. GBrain context pack returned no project card; unrelated hot facts were not used. No writeback.
- Captured SHA-256 for all 391 baseline files in `baseline.json`. Ran the documented native preflight after reading its help. Exit 0 and parsed `status: verified`, retained in `preflight.json`. This is a pre-edit observation, not an OS isolation guarantee.

## Execution checkpoint

1. Reproduce the named instrumentation failures. Complete. Seven methods errored in eight events, all on missing `feeds.httpx`.
2. Replace only the transport leaves. Complete. Seven methods now pass through real feed validation and the real shared transport loop.
3. Run the stock Python gate and audit the frozen bytes/assertions. Complete. Full discovery has only the named consent failures. No work remains in flight in this lane. Parent next reviews this delta and combines the consent sibling before integrated acceptance.

## Changed paths and methods

`tests/python/feed_transport_support.py` is the sole new support file. `Response` exposes status, headers, `getheader`, `getheaders`, bounded `read1`, and close. `PinnedTransport` queues responses and records connections, sends, and response order. Its connections expose request/getresponse/close/abort. Resolution returns the public numeric address `93.184.216.34`. Requests record the original hostname, method, path/query target, body, and headers. The installer patches only `net._resolve` and `net._connection` in product code and guards real socket/DNS calls against escape. It never patches `net._fetch_public` or replaces feed behavior.

Model the Domain informed the ordered response queue and event list. They keep connection metadata and authorization/send ordering observable without a product compatibility alias.

`tests/python/test_core_limits.py` changes one test method and its imports.

- `FeedLimitTests.test_feed_stream_byte_limit_stops_without_writes_and_recovers`. The stream yields bounded slices of the unchanged oversize body and a separate valid retry response. The real stream cap observes exactly `FEED_BYTES + 1`, and the original database-snapshot and retry-byte equality checks remain.

`tests/python/test_upkeep_runs.py` changes six test methods, imports, and one setup instrumentation line.

- `RunTests.test_manual_refresh_through_injected_https_transport_has_provenance`.
- `RunTests.test_manual_refresh_has_provenance_and_timestamps`.
- `FeedTests.test_production_fetch_uses_streaming_timeout_and_per_request_grants`.
- `FeedTests.test_off_host_redirect_is_refused_even_if_other_host_is_also_granted`.
- `FeedTests.test_http_and_credentialed_sources_are_refused_before_request`.
- `FeedTests.test_streaming_body_limit`.

`UpkeepCase.setUp` adds only `self.fetch_patch = item`. The two RunTests stop this already-existing fixture patch before refresh, restoring the real `feeds.fetch` rather than installing another patch over it. Other fixture-based upkeep tests retain their prior instrumentation. Direct FeedTests continue calling the existing captured real `HTTP_FETCH` function. No new replacement of `feeds.fetch` was introduced.

## Assertion preservation and replacement

`verify.py` compares complete method source segments and individual assertion source text against the clean base. All 67 existing test methods in the two owned files remain. Sixty test-method bodies remain byte-identical; seven changed only as listed. Across all methods and helpers in these files, 78 bodies remain byte-identical. Outside the two owned files, all 389 baseline files remain byte-identical, including every product file, fixture, review-customization test/support file, `test_net.py`, and `LANE_REPORT.md`.

All 30 retained assertion calls in the seven migrated methods are verbatim. Every other existing assertion in the two owned files is also preserved. Only these two expressly obsolete mechanism assertions were replaced.

```python
factory.assert_called_once_with(timeout=20.0, follow_redirects=False)
self.assertEqual(check.call_count, 2)
```

Their replacements require two separate connections to the vetted numeric destination, each timeout greater than zero and at most 20 seconds, and sends targeting `/feed` then `/current`. Each recorded send must have an immediately preceding successful Refresh check for the current space and exact host scope. The redirect response must precede a new scoped check before the next connection. Headers must retain the original Host. No arbitrary grant-call-count guard is used. The fake connection cannot follow a redirect itself.

The off-host redirect still raises `changed host` after exactly one send. HTTP and credential-bearing URLs still fail before any connection. The streaming limit still returns `limit`. Feed fixture bytes, source URLs, and expected result fields are unchanged. No tests were removed, skipped, or converted to expected failures. No HTTPX references remain in either owned test file or the new helper; frozen review-customization support was not edited.

The following is the complete unchanged assertion inventory for the seven methods. `assertion-inventory.json` also records the two removed calls and all new invariant assertions.

### FeedLimitTests.test_feed_stream_byte_limit_stops_without_writes_and_recovers

```python
self.rejected(limits.FEED_BYTES, limits.FEED_BYTES + 1,
                          lambda: feeds.fetch(self.sid, "https://example.org/feed"))
self.assertEqual(feeds.fetch(self.sid, "https://example.org/feed"), feed_xml())
```

### RunTests.test_manual_refresh_through_injected_https_transport_has_provenance

```python
self.assertEqual(run["status"], "succeeded")
self.assertEqual(run["changed"]["added"], 2)
self.assertEqual(meta["handler"], "feed")
self.assertEqual(meta["source_id"], "demo")
self.assertEqual(meta["url"], "https://research.example/feed")
self.assertIsInstance(meta["source_updated"], float)
self.assertGreaterEqual(meta["fetched_at"], run["started_at"])
self.assertLessEqual(meta["fetched_at"], run["ended_at"])
self.assertIsInstance(json.loads(row["source"])["published"], float)
self.assertGreater(row["created_at"], 0)
```

### RunTests.test_manual_refresh_has_provenance_and_timestamps

```python
self.assertEqual(run["status"], "succeeded")
self.assertEqual(run["changed"], {"added": 2, "updated": 0, "unchanged": 0, "removed": 0})
self.assertEqual(meta["handler"], "feed")
self.assertEqual(meta["source_id"], "demo")
self.assertEqual(meta["url"], "https://research.example/feed")
self.assertIsInstance(meta["fetched_at"], float)
self.assertIsInstance(meta["source_updated"], float)
self.assertGreater(row["created_at"], 0)
self.assertEqual(row["updated_by"], "user")
self.assertLess(run["source_as_of"], run["ended_at"])
```

### FeedTests.test_production_fetch_uses_streaming_timeout_and_per_request_grants

```python
self.assertEqual(len(requests), 2)
self.assertEqual(len(feeds.parse(payload)), 2)
```

### FeedTests.test_off_host_redirect_is_refused_even_if_other_host_is_also_granted

```python
self.assertEqual(len(requests), 1)
self.assertRaisesRegex(SpacesError, "changed host")
```

### FeedTests.test_http_and_credentialed_sources_are_refused_before_request

```python
factory.assert_not_called()
self.assertRaises(SpacesError)
```

### FeedTests.test_streaming_body_limit

```python
self.assertEqual(caught.exception.code, "limit")
self.assertRaises(SpacesError)
```

## Commands, counts, and direct exits

All suite runs used `/Users/ifedayoakinduro/.hermes/hermes-agent/venv/bin/python` with `HERMES_HOME="$PWD/.run/home"`, `TMPDIR="$PWD/.run/tmp"`, and `PYTHONDONTWRITEBYTECODE=1`. Each test's disposable database and any cron store stayed in this private worktree. These are stock unittest invocations, with no replacement runner or injected test cases.

Focused command, before and after migration.

```sh
HERMES_HOME="$PWD/.run/home" TMPDIR="$PWD/.run/tmp" PYTHONDONTWRITEBYTECODE=1 /Users/ifedayoakinduro/.hermes/hermes-agent/venv/bin/python -m unittest tests.python.test_core_limits tests.python.test_upkeep_runs -k test_feed_stream_byte_limit -k test_manual_refresh_through_injected -k test_manual_refresh_has_provenance -k test_production_fetch -k test_off_host_redirect -k test_http_and_credentialed -k test_streaming_body_limit -v
```

Full stock gate on final test bytes.

```sh
HERMES_HOME="$PWD/.run/home" TMPDIR="$PWD/.run/tmp" PYTHONDONTWRITEBYTECODE=1 /Users/ifedayoakinduro/.hermes/hermes-agent/venv/bin/python -m unittest discover -s tests/python -t . -v
```

| Run | Methods | Passed | Failed methods/events | Errored methods/events | Skips | Direct exit |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Before focused | 7 | 0 | 0/0 | 7/8 | 0 | 1 |
| After focused | 7 | 7 | 0/0 | 0/0 | 0 | 0 |
| Full discovery | 332 | 323 | 9/19 | 0/0 | 0 | 1 |

Logs and direct process exits are retained as `before-focused.log/.exit`, `after-focused.log/.exit`, and `full.log/.exit`. The focused pass preceded one test-only robustness adjustment to search for the second connection after the redirect event; full discovery executed that final form. Full discovery includes all seven migrated methods, all 32 Net tests, and all eight F03/F08 methods passing. All 305 pre-review-customization tests pass. F04 also passes on this supplied baseline.

`python -B .run/verify.py` exited 0. It checks frozen file hashes, exact changed method scope, assertion source preservation, no new/removed methods, no HTTPX references in the owned files, and parses the stock logs. `git diff --check` exited 0. Results are in `verification.json`. No additional repo state validator is adopted here.

## Expected consent-lane failures

All failures are in `tests.python.test_review_customization.ReviewCustomizationTests`. They remain for sibling integration and were not repaired here.

- `test_f01_agent_prompt_change_blocks_manual_and_scheduled_admission`.
- `test_f01_feed_to_agent_requires_fresh_refresh_approval`.
- `test_f01_stale_agent_scope_cannot_approve_changed_prompt`.
- `test_f02_matching_displayed_schedule_approves_exact_fields`.
- `test_f02_stale_displayed_schedule_conflicts_at_rest_boundary`.
- `test_f05_revoke_discovers_unmirrored_running_execution`.
- `test_f06_denial_preserves_unmirrored_completed_history`.
- `test_f07_history_backfill_includes_501st_execution`.
- `test_f09_feed_approval_rechecks_separately_committed_revocation`.

## Local commit disposition

`git add tests/python/test_core_limits.py tests/python/test_upkeep_runs.py tests/python/feed_transport_support.py` exited 128.

```text
fatal: Unable to create '/Volumes/Expansion/Development/Projects/living-spaces/.git/worktrees/c-test-transport/index.lock': Operation not permitted
```

No bypass or retry through another mechanism. The two modified files and new support file remain an uncommitted delta. `.run` is ignored evidence and was not staged. No commit was created.

## NOT done

No product edits, HTTPX compatibility alias, edits to frozen review-customization bytes, or sibling fixes. No runtime, Desktop, gateway, model, ticker, listener, live DNS/socket execution, installs, credentials, host/profile changes, pushes, merges, or PRs. No external messaging. No independent model review or final release acceptance is claimed. The synthetic evidence does not establish real-network transport behavior. Parent owns comparison of assertions, integration of the consent sibling, and the full integrated gate.
