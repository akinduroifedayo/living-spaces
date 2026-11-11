Living Spaces needs dependable saves and host-enforced permissions. **Do not promote `0aaebc3` yet.** This review found two blockers and four should-fix defects in `6742ea0..0aaebc3`.

The worktree remained unchanged. Findings below were reproduced with isolated, in-memory component probes. No real-Desktop acceptance run was performed.

**Executed findings**

1. **Blocker. Approval can grant a hostname the user never saw.**

   [permissions.jsx:49](/Volumes/Expansion/Development/Projects/living-spaces-wt/w2-review/src/desktop/ui/permissions.jsx:49) sends only `{decision:"grant"}`. [grants.py:152](/Volumes/Expansion/Development/Projects/living-spaces-wt/w2-review/src/living-spaces/living_spaces_core/grants.py:152) selects the latest requested scope.

   If the displayed request names `example.com`, then a revision changes it before the click reaches the backend, approval grants the replacement host. Polling does not bind consent to the displayed request.

   **Executed result.** Displayed status was `requested`, displayed scope was `example.com`, and the resulting granted scope was `unreviewed.example`.

   **Test sketch.** Create a pending refresh request for host A; retain that displayed grant; write a manifest requesting host B; submit the UI’s `{decision:"grant"}`. Assert B is not granted without renewed consent. Bind approval to the displayed scope/request version.

   Violates R1-05 and the explicit-consent boundary in spec §2.

2. **Blocker. Retrying an uncertain create duplicates persisted records.**

   [session.mjs:35](/Volumes/Expansion/Development/Projects/living-spaces-wt/w2-review/src/desktop/ui/session.mjs:35) resubmits the original arguments. [records.py:52](/Volumes/Expansion/Development/Projects/living-spaces-wt/w2-review/src/living-spaces/living_spaces_core/records.py:52) generates another ID when none was supplied. The local retry token never reaches the backend.

   When a create commits but its response is lost, the host says “this change was not stored.” Clicking **Retry save** creates a second record.

   **Executed result.** A transport stub that committed before throwing produced `stored=1, status=failed`; retry produced `stored=2, status=saved`. Separately, the real core accepted identical ID-less creates and persisted two different IDs.

   **Test sketch.** Commit the first `data.put`, drop its response, then invoke the exposed retry callback. Assert exactly one record exists. Cover ID-less creates inside `data.batch` too. Preserve an operation identity across retries and distinguish an unknown outcome from a confirmed failure.

   Violates R1-11’s requirement that retries not multiply effects.

3. **Should-fix. Structured console output bypasses password redaction.**

   [logs.py:10](/Volumes/Expansion/Development/Projects/living-spaces-wt/w2-review/src/living-spaces/living_spaces_core/logs.py:10) recognizes `password=...`, but not JSON’s `"password":...`. The loader serializes logged objects using `JSON.stringify`.

   A normal `console.log({password: "synthetic-secret"})` therefore persists the password and exposes it through diagnostics and `spaces_read_logs`.

   **Executed result.** `logs.add_logs` followed by `read_logs` returned both `"password": "synthetic-secret"` and `"api_key": "demo-short-secret"` unchanged.

   **Test sketch.** Submit JSON-serialized credential objects through the log bridge, then inspect stored logs. Assert credential values are absent. Include short values that do not match the generic 32-character token pattern.

   Violates the redaction contract and R1-05/R1-09.

4. **Should-fix. Refresh can fetch and write after its session closes.**

   [bridge.py:54](/Volumes/Expansion/Development/Projects/living-spaces-wt/w2-review/src/living-spaces/living_spaces_core/bridge.py:54) starts refresh without passing or rechecking the session during run admission. Unlike record mutations, this path lacks an authorization check inside its write transaction.

   Closing the session between preflight and handler execution does not prevent the refresh. The final check only suppresses its reply.

   **Executed result.** The bridge returned `session_invalid`, while a fixture fetch occurred, the run succeeded, and one record was stored.

   **Test sketch.** Extend the existing preflight-close tests to `refresh`. Close the session after the first grant check, use a fixture fetcher, and allow the worker to finish. Assert no fetch, admitted run, or record write occurs.

   Violates R1-11 lifecycle isolation.

5. **Should-fix. Failed session cleanup is swallowed permanently, including on profile switch.**

   [session.mjs:16](/Volumes/Expansion/Development/Projects/living-spaces-wt/w2-review/src/desktop/ui/session.mjs:16) catches the close failure and caches the settled promise. Further destruction attempts never retry. The caller supplies no error handler.

   Switching profiles makes the old `scopedRest` reject cleanup before sending DELETE. The backend session remains open; [sessions.py:31](/Volumes/Expansion/Development/Projects/living-spaces-wt/w2-review/src/living-spaces/living_spaces_core/sessions.py:31) has no expiry or replacement-session invalidation.

   **Executed result.** Changing the mocked profile before `destroy()` produced zero backend close requests, yet destruction resolved. A separate failed-DELETE probe made only one attempt across two calls to `destroy()`.

   **Test sketch.** Open under profile A, switch to B, destroy, then inspect A’s session row and replay its token. Require eventual invalidation and observable cleanup failure. Use a transport bound to the original backend for cleanup.

   Backend replay consequences are derived from the session validator; the frontend failure paths were executed. Violates R1-11.

6. **Should-fix. Revoking data access does not stop delivery of new record metadata.**

   [space.jsx:88](/Volumes/Expansion/Development/Projects/living-spaces-wt/w2-review/src/desktop/ui/space.jsx:88) polls changes without checking the data grant. [sandbox/index.js:154](/Volumes/Expansion/Development/Projects/living-spaces-wt/w2-review/src/desktop/sandbox/index.js:154) forwards events without a grant check.

   After revocation and remount, the guest can still learn new collection names, record IDs, actors, operations, revisions, and timestamps. This is newly delivered information, not previously cached data.

   **Executed result.** A host mounted with `grants: []` denied `data.query` but delivered a `data.changed` payload containing `private_notes/client-alice`.

   **Test sketch.** Revoke data access, register a guest change listener, then create a record through chat/core. Assert the guest receives no record metadata. For Desktop qualification, reuse `harness/guest_realm.py` and the existing lifecycle harness.

   The port-level behavior was executed; the complete revocation/remount scenario is derived from the UI flow. Violates spec §2 and R1-05/R1-11.

**Contract issues**

- **Nit. Amendment A2 is not implemented in the database schema.** [db.py:47](/Volumes/Expansion/Development/Projects/living-spaces-wt/w2-review/src/living-spaces/living_spaces_core/db.py:47) omits `schedules.reason`, with no corresponding migration. The implementation reconstructs disabled reasons from audit entries instead. Executing the DDL in memory confirmed the column is absent. Reproducer: initialize `db.DDL`, then execute `SELECT reason FROM schedules`; it fails. Forge should reconcile the implementation and frozen amendment.

**Verification and limits**

- Stock Python discovery attempted all 151 tests. It ended with 150 setup errors because creating `.run/` was forbidden. This is an environment failure, not 150 demonstrated product defects.
- The combined sandbox/UI Node suite was similarly blocked by `.run/` creation.
- All **19 reference compatibility tests passed** unchanged:
  `node --import ./tests/js/reference/env.mjs --experimental-vm-modules --test tests/js/reference/compatibility.test.mjs`
- Both selected shipped-document tests passed:
  `node --test --test-name-pattern='shipped' tests/js/sandbox/document.test.mjs`
- Targeted core probes confirmed stale-write rejection, atomic batch rollback, cross-Space session rejection, and rejection after a successfully recorded close.
- Scoped integrated `git diff --check`, working-tree `git diff --check`, and clean-status checks passed.

The packaged sandbox document matches its deterministic producer, and the tested shell boot checks passed. Ordinary-network isolation and actual Desktop reload behavior remain unverified by this seat.