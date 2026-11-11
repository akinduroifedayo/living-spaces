# F03 and F08 repair report

Living Spaces should let normal Hermes chat build custom apps with durable data, internet access, and upkeep. This lane repairs session-bound egress and feed public-network isolation within that existing scope.

The assigned slice is green on synthetic transport evidence. Integration acceptance remains with Forge. Full discovery remains red for the named other-lane defects and frozen HTTPX instrumentation below. Nothing is landed.

## Inputs and authority

- Workspace `/Volumes/Expansion/Development/Projects/living-spaces-wt/c-fix-net`, branch `forge/r1-c-fix-net`, clean starting HEAD `e45e094b81c19e3cfc0950cb4148f7f7188cd06e`.
- Read `.run/packet/pins.json` first, then all twenty required shards in full. Read F03 and F08, the complete parent red log, red audit, and method pins. Initial native preflight verified all 382 baseline paths. All 20 shard hashes and their source hashes matched before product edits.
- Read the requested pstack model policy, poteto-mode skill, Hermes adapter, and gated-program delegation reference. The commission specifies Astra high fast. No model route was launched, substituted, or changed here. Runtime model/provider/effort/tier attribution remains for the parent's session-receipt audit; this report does not claim wire verification.
- The explicit no-model-execution, frozen-tests, three-file ownership, and no-PR boundaries override the generic skill's delegation, test-authoring, and PR stages. This is the commissioned repair worker, not a new architecture competition or acceptance reviewer.
- Bounded memory lookup found no relevant retained registry entry. GBrain context pack supplied no relevant project card; no external history was used for implementation decisions.

## Preflight and success criteria

Ran `/Users/ifedayoakinduro/.hermes/skills/pstack/hermes-local/native-preflight.py --help` first. Then used the supported invocation with `--workspace`, `--parent`, and `--manifest .run/baseline.json`. Exit 0, parsed `status: verified`. Retained `.run/preflight.json` and `.run/preflight-receipt.json`. This establishes checked workspace state, not an OS sandbox or atomic protection against later changes.

1. Reproduce the frozen behavior with the real review suite. Completed before edits, matching the parent's 14 failing methods and 27 failure events exactly.
2. Change only the three owned product files. Completed. One shared transport handles DNS vetting, socket pinning, redirects, deadline, and bounded raw response bytes.
3. Verify the eight F03/F08 methods, stock Net suite, and full stock Python discovery. Completed with the exact results below. Preserve every test byte and identify any instrumentation conflicts. Completed.

## Owned function deltas

- `bridge.py::_call`, line 41. Passes `session=session` into `net.fetch`. `_OPS` stays unchanged. Frames cannot supply `session`, `authorize`, `capability`, or a response cap.
- `net.py::fetch`, line 253. Adds optional `session=None`. Its private authorization closure checks the bound session when present and the existing Net grant. Request validation, text/JSON/base64 response shape, and bounded Net audit remain in this wrapper. It rechecks authority after response conversion before returning.
- `net.py::_fetch_public`, line 192. Extracts the existing transport loop into an internal helper taking a trusted authorization callback and per-call byte cap. It returns `(response_metadata, body_bytes)`. It checks authority before URL/DNS processing for each hop, after DNS before creating a connection, immediately before `request`, and after reading before returning. It uses the existing `_target`, `_addresses`, and `_PinnedHTTPS`, without a second transport, second DNS resolution at connect, or HTTPX path. Every DNS answer must be public; the selected numeric IP stays pinned with the original hostname used for TLS and Host. Redirect joining retains the pre-normalized URL so a source host ending in a dot can follow a relative redirect without silently changing its exact approved host identity.
- `feeds.py::fetch`, line 26. Removes HTTPX and calls `_fetch_public` with `MAX_BYTES` (3 MiB). The callback enforces the existing exact source host and HTTPS-only policy and checks Refresh host scope. It never checks Net. Non-2xx final responses are rejected, and a final Refresh check precedes returning unchanged bytes. `source_host`, parsing, and `refresh_source` provenance construction are unchanged.
- Imports change only to support these functions and remove the unused HTTPX and feed `urljoin` dependencies.

The Model the Domain principle informed the internal `(metadata, bytes)` response shape and a single authority-neutral transport boundary. A capability selector in the public API and duplicated feed pinning logic were rejected because neither is needed. No product comments or unrelated abstractions were added.

## Commands and observed results

All Python commands used `/Users/ifedayoakinduro/.hermes/hermes-agent/venv/bin/python`, with `TMPDIR=$PWD/.run/tmp`, `HERMES_HOME=$PWD/.run/home`, and `PYTHONDONTWRITEBYTECODE=1`. Tests also create their own disposable databases. These are real unittest invocations using frozen files, without replacement discovery runners or test injection.

| Invocation after the interpreter | Log | Direct exit | Observed result |
| --- | --- | --- | --- |
| `-m unittest tests.python.test_review_customization -v`, before edits | `before-review.log` | 1 | 27 methods, 13 passed, 14 failed, 27 failure events, zero errors/skips |
| `-m unittest tests.python.test_review_customization -v`, after repair | `after-review.log` | 1 | 27 methods, 17 passed, 10 failed, 22 failure events, zero errors/skips |
| `-m unittest tests.python.test_net -v` | `net.log` | 0 | 32 passed, zero failures/errors/skips |
| `-m unittest discover -s tests/python -t . -v` | `full.log` | 1 | 332 methods, 315 passed, 10 failed methods with 22 failure events, seven errored methods with eight error events, zero skips |
| `-m unittest tests.python.test_review_customization -k test_f03 -k test_f08 -v` | `focused.log` | 0 | All eight assigned methods passed, zero failures/errors/skips |
| `.run/probes.py` | `probes.log`, `probes.json` | 0 | Nine supplemental synthetic probe groups passed |
| `.run/verify.py` | `verification.json` | 0 | Frozen hashes and scope verified; `git diff --check` exit 0 |

The final full discovery and focused run include the raw-URL redirect joining adjustment. Full discovery reran all 32 Net methods successfully on those final bytes. Logs and `.run/verification.json` retain method identities and counts. Direct exits in that JSON are transcribed from the execution tool receipts; they are not inferred from a wrapper success.

The four red-to-green methods are all in `tests.python.test_review_customization.ReviewCustomizationTests`.

- `test_f03_bridge_passes_bound_session_to_real_net_fetch`.
- `test_f03_closed_session_prevents_redirect_post`.
- `test_f08_feed_rejects_approved_loopback_before_transport`.
- `test_f08_public_feed_uses_vetted_pinned_destination`.

The four already-green controls remain green.

- `test_f03_net_revocation_prevents_redirect_post_control`.
- `test_f03_open_session_preserves_redirect_post_control`.
- `test_f08_refresh_authority_works_with_net_revoked_control`.
- `test_f08_mediated_net_rejects_loopback_control`.

The pre-edit failure included the unwanted second send, verbatim from `before-review.log`.

```text
-  ('second.example', 'POST', b'demo', True)]
```

The final focused result is verbatim from `focused.log`.

```text
Ran 8 tests in 0.291s

OK
```

The supplemental probes call the real core and SQLite with the frozen fixture's denied live sockets/DNS and synthetic `_connection` and `_resolve` seams. They verify mixed public/private DNS refusal, private rebinding on redirect, public redirect pinning, non-UTF-8 bytes unchanged with Net revoked, exact source-host/downgrade rejection, trailing-dot relative redirects, the exact 3 MiB boundary and cap+1 error numbers, Refresh revoke during a 307 and before delivery, session closure at DNS/connection/delivery seams, rejected bridge authority arguments, and retained feed provenance. These are supporting probes, not a replacement full-suite claim or observed external egress.

## Remaining other-lane failures

Ten methods remain red, exactly as before this repair, in `ReviewCustomizationTests`.

- Consent lane F01. `test_f01_agent_prompt_change_blocks_manual_and_scheduled_admission`, `test_f01_feed_to_agent_requires_fresh_refresh_approval`, `test_f01_stale_agent_scope_cannot_approve_changed_prompt`.
- Consent lane F02. `test_f02_matching_displayed_schedule_approves_exact_fields`, `test_f02_stale_displayed_schedule_conflicts_at_rest_boundary`.
- Source lane F04. `test_f04_stale_source_revision_conflicts_and_rolls_back_whole_batch`.
- Consent lane F05. `test_f05_revoke_discovers_unmirrored_running_execution`.
- Consent lane F06. `test_f06_denial_preserves_unmirrored_completed_history`.
- Consent lane F07. `test_f07_history_backfill_includes_501st_execution`.
- Consent lane F09. `test_f09_feed_approval_rechecks_separately_committed_revocation`.

No sibling issue was adopted and no sibling path was edited.

## Frozen old-test instrumentation for parent migration

All eight error events are `AttributeError: module 'living_spaces_core.feeds' has no attribute 'httpx'` at the obsolete mock target. Seven old methods are affected. The remaining 298 old methods pass. No test was edited, disabled, or conditionally skipped.

- `tests/python/test_core_limits.py::FeedLimitTests.test_feed_stream_byte_limit_stops_without_writes_and_recovers`, mock at line 305. Preserve `self.rejected(limits.FEED_BYTES, limits.FEED_BYTES + 1, ...)` and exact recovered feed-byte equality at line 309. Instrument the shared pinned response stream instead of `response.iter_bytes` and `feeds.httpx.Client`.
- `tests/python/test_upkeep_runs.py::RunTests.test_manual_refresh_through_injected_https_transport_has_provenance`, mock at line 114. Preserve succeeded status, two added rows, handler/source_id/original URL metadata, float source timestamps, fetched-at bounds, published timestamp, and positive created-at assertions at lines 116-126.
- `RunTests.test_manual_refresh_has_provenance_and_timestamps`, mock at line 132. Preserve succeeded status, complete changed counts, feed metadata, float timestamps, positive created-at, `updated_by == 'user'`, and source freshness assertions at lines 134-144.
- `FeedTests.test_production_fetch_uses_streaming_timeout_and_per_request_grants`, mock at line 468. Preserve two requests and two parsed entries. Its literal `factory.assert_called_once_with(timeout=20.0, follow_redirects=False)` names the removed HTTPX constructor. Its literal `self.assertEqual(check.call_count, 2)` counts the old once-per-hop grant calls; the shared transport now checks before DNS, after DNS, before send, and before delivery. These are explicit instrumentation/contract conflicts for the parent, not authorization to weaken product guards or silently edit assertions. A truthful migrated observer must measure the intended per-request checks and shared deadline without pretending HTTPX is still used.
- `FeedTests.test_off_host_redirect_is_refused_even_if_other_host_is_also_granted`, mock at line 484. Preserve `assertRaisesRegex(SpacesError, 'changed host')` and `len(requests) == 1` at line 487.
- `FeedTests.test_http_and_credentialed_sources_are_refused_before_request`, mock at line 491. Its two subtests account for two error events. Preserve `assertRaises(SpacesError)` and zero transport calls.
- `FeedTests.test_streaming_body_limit`, mock at line 498. Preserve the raised `SpacesError` and `caught.exception.code == 'limit'`.

Transport migration must observe `net._resolve` and `net._connection` without bypassing the actual shared helper. The frozen new suite already does this. The `.run` probes add supporting cap/provenance coverage while the parent owns the old-test migration.

## Contract differences and hazards

- Feed retrieval now inherits the same public HTTPS destination policy as Net, including ports 443/8443, all-answer refusal, numeric pinning, total deadline, and identity encoding. Feed scope still uses the exact original `source_host` comparison, not a suffix or normalized-host permission expansion.
- Missing-location/over-limit redirect errors now use the shared `blocked/redirect` error instead of feed-specific `invalid` messages. Feed final non-2xx errors become a core `SpacesError('invalid', ..., status=...)` instead of an HTTPX exception. These keep failure behavior without retaining HTTPX. No frozen behavioral assertion failed on those changes.
- Checks are synchronous observations before new sends and delivery. They are not an atomic cancellation fence. Closing a session cannot recall an already-sent request, and an authority change can race the final check. F03's deterministic first-307 closure is stopped before the second connection/send.
- The helper is trusted internal code, not a new exposed capability. Future callers must supply their own authorization callback and byte cap. Existing bridge arguments remain closed.
- Generic skill arena, extra model review, and PR stages were not executed under this commission's explicit boundaries. Parent must commission fresh independent review and retain runtime/acceptance ownership.

## Preservation and not done

`.run/verification.json` verifies all 62 frozen test files, all 27 pinned test-method bodies, all 20 packet shards, and all 379 unowned baseline files. Only `net.py`, `bridge.py`, and `feeds.py` differ from the base. `LANE_REPORT.md` remains byte-identical. `.run` contains only local evidence and disposable test outputs.

No Desktop, gateway, model, ticker, live network, or listener execution. No credential or live-profile access, installs, host changes, pushes, merges, or PRs. No release bundle was built or committed; full discovery's own disposable renderer artifacts stay under `.run`. No test assertion or fixture changed. No claim of whole-release acceptance, actual peer-observed POST suppression, or independent final review.

The parent next integrates the three-file delta, migrates the named old instrumentation under its own authorization, combines sibling repairs, and reruns acceptance. Local commit disposition is recorded below.

Local commit was not possible. `git add src/living-spaces/living_spaces_core/net.py src/living-spaces/living_spaces_core/bridge.py src/living-spaces/living_spaces_core/feeds.py` exited 128 with `Unable to create '/Volumes/Expansion/Development/Projects/living-spaces/.git/worktrees/c-fix-net/index.lock': Operation not permitted`. No bypass or retry through another tool was attempted. The product edits remain uncommitted in the assigned worktree; no staged delta or commit was created.
