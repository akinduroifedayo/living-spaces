Repaired F3/F4 within the three owned modules:

- Credential values are redacted from JSON and assignment diagnostics before storage.
- Bridge session and grant checks now run atomically during refresh admission.
- Failed upkeep sources preserve structured errors and visible `limit`/`actual` values.

Verification: frozen tests went from 79 failures to **7 passing tests**. Full discovery passed **193 tests**. Existing tests remain byte-identical; `git diff --check` passed. No fixture-bind blocker occurred.

[Full report](.run/backend-fix-report.md)

Sandbox permissions blocked Git’s `index.lock`, so changes remain uncommitted for the parent. Independent review and the host gate remain parent-owned; no R1 acceptance claimed.