Added only [test_review_backend.py](/Volumes/Expansion/Development/Projects/living-spaces-wt/w2-backend-tests/tests/python/test_review_backend.py). Existing tests remain unchanged. **Tests are unexecuted.** No product edits, commit, or push.

Expected baseline results, inferred from source:

| Test | Expected behavior |
|---|---|
| `test_f3_flat_json_credential_values_are_redacted_before_storage` | **Red:** all six credential values remain in SQLite and `read_logs`. |
| `test_f3_nested_json_credential_values_are_redacted_before_storage` | **Red:** nested credential values remain on both surfaces. |
| `test_f3_credential_assignments_are_redacted_before_storage` | **Red:** five non-password keys leak in bare and quoted assignments. Password cases are passing controls. |
| `test_f3_plain_diagnostic_is_preserved_exactly` | Passing control requiring unchanged diagnostic text. |
| `test_f4_session_closed_after_grant_check_cannot_admit_refresh` | **Red:** despite `session_invalid`, one fetch, run, record, and change occur after closure. |
| `test_f4_live_session_refresh_fetches_and_persists` | Passing control requiring successful fetch and persistence. |
| `test_f4_admitted_native_upkeep_survives_unrelated_session_close` | Passing control requiring admitted native upkeep to finish after an unrelated session closes. |

F3 checks innocent content preservation without prescribing redaction formatting, which the contract leaves unspecified. F4 uses thread events and real runs APIs; it imposes no cancellation requirement on previously admitted work. The native control creates no cron job.

Read-only diff inspection found no tracked changes or whitespace diagnostics.

Parent command, from this worktree:

```sh
~/.hermes/hermes-agent/venv/bin/python -m unittest discover -s tests/python -t . -p 'test_review_backend.py' -v
```