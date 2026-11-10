# Lane UI report

## ISSUES

The goal is a dependable Spaces desktop surface for chat-built applications, with visible permissions, durable-data status, revisions and approved upkeep. The UI source, built bundle and isolated tests are present. Final acceptance is not claimed. Integration still needs the sandbox lane's release-1 module. Git metadata writes are denied in this seat, so no commits were created.

Branch is `forge/r1-ui`. Starting and current HEAD is `1fe4c57`. Nothing was pushed. No Hermes app, gateway or scheduler was started, stopped or changed. No packages were installed. No independent review was run.

## Built files

- `src/desktop/plugin.src.js` registers `/spaces`, the Spaces sidebar row and the validated `living-space` transcript directive. The directive displays the name, owner, status, revision and Open Space action. Hash query changes select a Space without losing direct-link navigation.
- `src/desktop/ui/context.jsx` scopes caches by SDK connection/profile identity, remounts views on a scope change and fences requests/results from stale backend callbacks.
- `src/desktop/ui/model.mjs` owns slug validation, status models, attention counts, filtering/sorting, separate freshness facts, cursor advancement, run summaries, restore copy and bounded diagnostic formatting.
- `src/desktop/ui/components.jsx` owns shared SDK-backed actions, pills, tiles, owner chips, time formatting, copy prompts, banners, sheets and confirmation dialogs. Revocation uses SDK Dialog with alertdialog semantics and default focus on Keep access. Confirmation does not treat Enter anywhere in the dialog as consent.
- `src/desktop/ui/index.jsx` implements the cards, pinned/recent order, counts, search, filters, first-use prompts, new-chat action discovery and empty/error/loading states.
- `src/desktop/ui/space.jsx` implements the host frame, refresh controls, schedule/pause actions, permissions/history access, archive/delete, building/failed/blocked/crashed/archived states and save/conflict feedback. A failed refresh leaves content mounted with reduced saturation. Archived Spaces show retained-data copy and Restore/Delete actions; they do not run a frame until restored.
- `src/desktop/ui/session.mjs` opens/closes backend sessions, binds bridge calls, suppresses delivery after closure and cleans up sessions that finish opening after navigation. Failed/conflicted write arguments remain available for explicit retry. Pending writes do not appear saved. Repeated Retry save activation shares its pending request. An unrelated successful write does not hide an unresolved conflict.
- `src/desktop/ui/permissions.jsx` places the exact WebRTC note above the scrolling sheet body, then grants, waiting decisions and schedule requests, unavailable release-2 rows, owner and audit. Release-2 rows have no controls. No narrower-scope option is invented.
- `src/desktop/ui/history.jsx` implements run history, truthful no-change results, revision rows and code restoration confirmation. Incompatible restore errors remain visible in the confirmation.
- `src/desktop/ui/schedule.jsx` implements cadence/timezone, next run, last attempt, cost and limits, catch-up policy, pause/resume and a copyable schedule-change prompt.
- `src/desktop/ui/styles.js` uses SDK tokens, the specified eight tile accents, status words/glyphs/border patterns, visible focus, compact action handling and reduced-motion rules.
- `src/desktop/ui/sandbox-shim.js` is the explicitly permitted temporary import seam. See integration requirements below.
- `src/living-spaces/desktop/plugin.js` is the built ESM artifact. Final measured size is **92,560 bytes** (esbuild reports 90.4 KB).
- `tests/js/ui/index.js` contains the pure-logic and session-lifecycle tests. `tests/js/ui/sdk-stub.js` and `tests/js/ui/render-smoke.mjs` provide the requested SDK-stub static-render gate using Hermes's existing React and react-dom/server packages.

The implementation follows the frozen REST paths. Details poll every 2000 ms, and record changes poll every 1500 ms. Head revision/grant changes and reloaded events replace sessions. Run updates and record changes are sent through the sandbox event interface. Opening a Space posts `/opened`. These React effect paths are implemented but have not been qualified in Desktop.

Model the Domain shaped the shared status table and contract-shaped data helpers. Test Behavior, Not Implementation shaped the lifecycle assertions around observable requests, results and save state. Prove It Works shaped the rerunnable render gate and inspection of the built artifact. These are the three principle leaf skills read for this work.

## Verification actually run

The shell's default `node` is v22.22.3. `/opt/homebrew/bin/node` is **v25.9.0**, and the final gate used that executable. Earlier default-node runs also passed.

| Exact command | Observed result |
| --- | --- |
| `node --test tests/js/ui/` | Initial and intermediate runs: 25 passed, 0 failed, 0 skipped. |
| `node tests/js/ui/render-smoke.mjs` | 38 assertions passed; no skip. |
| `/opt/homebrew/bin/node --test tests/js/ui/` | Final: **28 passed, 0 failed, 0 skipped**. |
| `/opt/homebrew/bin/node tests/js/ui/render-smoke.mjs` | Final: **40 assertions passed**, 12 static HTML fixtures, no skip. |
| `/opt/homebrew/bin/esbuild src/desktop/plugin.src.js --bundle --format=esm --jsx=automatic --external:@hermes/plugin-sdk --external:react --external:react/jsx-runtime --outfile=src/living-spaces/desktop/plugin.js` | Passed. Final bundle 92,560 bytes. |
| `grep -o 'from "[^"]*"' src/living-spaces/desktop/plugin.js \| sort -u` | Exactly the three imports shown below. |
| `/opt/homebrew/bin/node --check src/living-spaces/desktop/plugin.js` | Passed. Bundle parses as JavaScript without source JSX. |
| `wc -c src/living-spaces/desktop/plugin.js` | 92560. |
| `git diff --check` | Exit 0. New files are untracked because staging is denied. |
| `git diff --no-index --check /dev/null <file>` for each of the 17 new source/bundle/test/report files, driven by a Python subprocess loop | 17 files checked, 0 whitespace failures. |

The import scan returned:

```text
from "@hermes/plugin-sdk"
from "react"
from "react/jsx-runtime"
```

The render gate exercises index, first use, Space frame, Permissions, building, failed, blocked, crashed, archived, run history, revisions and schedule. It checks exact disclosure text/order, the disclosure outside the scrolling body, unavailable rows without buttons/inputs, separate freshness facts, no false initial Saved claim, blocked/archived refresh reasons, no-change success, directive validation/metadata, registration and cache separation for colliding Space IDs on different backends. The fake `ctx.rest` serves public demo fixtures; there is no test network access.

Each unit/render invocation sets `HERMES_HOME` and `LIVING_SPACES_DB` to a fresh directory under this worktree's ignored `.run/`. The final static fixtures are in `.run/ui-render-DnXvlD/`. They are test artifacts, not visual-acceptance evidence.

No repo-wide package script, Makefile or local validator is configured in this checkout. Other lanes' Python/core/REST/sandbox gates were not run here.

## Not done or unproven

1. **Sandbox integration is required.** `src/desktop/sandbox/index.js` is absent from this worktree. The shim re-exports the old spike mount and supplies the exact disclosure. The old spike does not implement the frozen session-aware bridge operations, bundle shape or `postEvent` interface. This is a build seam, not a working release-1 application runtime. Forge must replace imports from `./sandbox-shim.js` in `space.jsx` and `permissions.jsx` with `../sandbox/index.js`, remove the shim and rebuild. Do not ship the current shim bundle as R1.
2. No real-app acceptance, actual frame load, live record updates, restart persistence, HTTP permission enforcement, cron approval/run, model-driven chat or destructive-action execution was run. Those belong to the integrated isolated-app qualification. The tests use injected adapters and SDK stubs.
3. Keyboard traversal, real SDK focus trapping/return, screen readers, actual dark/light contrast, narrow layouts, large text and forced-colors remain unproven. Static rendering does not establish R1-12. Focus return from menu-opened sheets is explicitly wired to the overflow trigger, but requires a real keyboard walk.
4. Generic host conflict controls preserve the submitted bridge arguments. Keep my note is offered for `data.put` with a current revision and requires an explicit rebase. Batch/delete conflicts can be compared or discarded. Use updated record starts a new frame/session to load authoritative state. Arbitrary application-specific draft handling and conflict UX still need integrated testing. Draft retention is in the current host view, not durable across closing the Space.
5. A failed backend session-close request cannot prove server invalidation. The local port/frame closes and further local bridge calls are denied. Backend session expiry/replay enforcement requires the sandbox/core acceptance tests.
6. Backend callback/request fences and cache separation with colliding Space IDs pass isolated tests. Actual profile/backend switching still needs Desktop qualification. Because `ctx.rest` follows the active backend, an old session's close request is rejected locally after a switch rather than sent to the wrong backend; backend expiry/retirement must invalidate the old server-side session.
7. The old spike desktop source is retained as a read-only reference while the replacement sandbox is pending. No other lane's source was edited.

## Contract issues

- **Temporary sandbox mismatch.** The absent section-12 module requires the sanctioned shim above. Its runtime incompatibility is explicit; the frozen contract was not edited.
- **Sidebar attention badge unavailable in this SDK.** `SidebarNavContribution` exposes only `codicon`, `label`, `path` and optional `tier`. No badge or custom badge-render hook is present. The sidebar remains Spaces with the layers icon. The index displays attention counts. No badge field was invented, and `/status` is not polled solely for an unsupported badge.
- **Narrower scopes are not defined.** Section 8's grants response has grants/future/audit but no host-defined narrower choices. Approve narrower is omitted as instructed. Adding arbitrary host checkboxes would invent a seam.
- **Cursor pagination is underspecified.** `changes_since` reports `seq: latest` alongside a limited changes page, without has_more. The UI advances to the greatest delivered row sequence, never the advertised latest value ahead of a page, so it cannot skip undelivered changes. Empty pages retain their cursor.
- **Error events do not define a detailed diagnostic shape.** The UI handles message/error, optional location/filename/phase/fatal and repeated errors. It bounds/redacts common credential values and displays a missing-location fact when unavailable. Real sandbox event compatibility still needs qualification.

## Git receipt

Attempted:

```text
git add src/desktop/plugin.src.js src/desktop/ui src/living-spaces/desktop/plugin.js tests/js/ui
git diff --cached --check
git diff --cached --stat
git commit -m "feat(ui): add Spaces host views and session lifecycle"
```

Staging and commit failed with:

```text
fatal: Unable to create '.../living-spaces/.git/worktrees/ui/index.lock': Operation not permitted
```

The Git directory resolves to the expected shared worktree metadata. This is a sandbox permission failure, not an existing lock-file collision. The session disallows permission escalation. No metadata workaround was attempted. All lane files, including this report, remain in the worktree for Forge. A final `git add` including `LANE_REPORT.md` was also attempted and received the same denial. A commit containing this report is still required once Git writes are available.
