# SANDBOX lane report

Status: ISSUES

Living Spaces needs a dependable multi-view app runtime with a trusted bridge, shared records, and truthful save and refresh states. This lane implements the frozen sandbox seam and the small runtime kit. Browser qualification and commits remain blocked by this session's managed permissions.

## Built

- `src/desktop/sandbox/index.js`: `BRIDGE_VERSION`, exact `WEBRTC_NOTE`, equal frozen CSPs, nested opaque srcdoc frames and shell relay, host request validation, op-to-grant checks, versioned backend replies and events, reload shutdown, suppression of late replies, and bounded log forwarding. Successful replies are checked against the current host grant again before delivery. Unknown ops, including future capabilities, are denied.
- `src/desktop/sandbox/loader.js`: frame-side `window.space` collection API, `SpaceError` with `code` and `current`, subscriptions, session closure, logging and visible boot errors. Project files use local blobs and an import map over `https://space.invalid/`. Relative static imports and literal or computed dynamic imports resolve from their original project file. Entry HTML adopts markup and executes classic and module scripts, including scripts nested in markup. Asset query strings resolve to the bundled file; image and CSS fragments survive.
- Deleted `src/desktop/sandbox/spike-sandbox-core.js`.
- `src/living-spaces/runtime/kit/spaces-kit.mjs`: original tagged-template parser, collection and record hooks, confirmed save state, hash routing, `SaveIndicator`, `ConflictBanner`, `EmptyState`, `Nav`, and `RefreshButton`. It imports only the existing bare `preact` and `preact/hooks` names. No JSX, htm, build step, or package installation.
- `src/living-spaces/runtime/kit/spaces-kit.css`: system-font base, light and dark palettes, keyboard focus rings, reduced motion, forms, tables, cards and badges. Tested text color pairs meet 4.5:1 in both palettes.
- `tests/js/sandbox/{env.mjs,index.js,html.test.mjs,host.test.mjs,loader.test.mjs,hooks.test.mjs,theme.test.mjs,check.mjs}`: parser, protocol, real MessageChannel transfer and lifecycle tests, frame API tests in a VM, actual vendored Preact hook tests with null-rendering capture components, and CSS contrast calculations. The hooks are not replaced with mocks. Browser DOM rendering is not established by these tests.
- `tests/js/sandbox/{smoke.html,smoke.mjs,smoke-server.mjs,smoke-cdp.mjs,demo/**}`: standalone two-view public-content fixture, in-memory bridge, Node HTTP server, and CDP driver using Node's built-in WebSocket. The driver starts the specified Chrome executable with a temporary profile and debugging port and closes that Chrome in `finally`. It contains checks for navigation, local assets, Saving then Saved, live changes, conflicts, refresh states, parent access, blocked fetch and CSP logging, log flooding, the frame API and reload shutdown. These browser checks have NOT run successfully here.

Only lane-owned paths and this requested report changed. No packages were installed, no network is used by unit tests, no live Hermes files or services were changed, and nothing was pushed. Tests set `HERMES_HOME` and `LIVING_SPACES_DB` to fresh directories under `.run/`.

## Verification

Node used: `/opt/homebrew/bin/node`, v25.9.0. The default shell Node is v22, so commands explicitly select the installed Node 25.

| Exact command | Real result |
| --- | --- |
| `PATH=/opt/homebrew/bin:$PATH node --test tests/js/sandbox/` | Final run: 48 tests, 48 passed, 0 failed, 0 skipped. |
| `PATH=/opt/homebrew/bin:$PATH node --import ./tests/js/sandbox/env.mjs --test tests/js/sandbox/host.test.mjs tests/js/sandbox/loader.test.mjs` | At the attempted first commit: 26 tests, 26 passed, 0 failed. The final suite includes these checks plus the later shell-reload check. |
| `PATH=/opt/homebrew/bin:$PATH node tests/js/sandbox/smoke-cdp.mjs` | Attempted twice. Both exited 1 at server startup with `listen EPERM: operation not permitted 127.0.0.1`. Zero browser assertions executed. Chrome was never launched, so there is no test Chrome to kill. |
| `git diff --check` | Passed. |
| `PATH=/opt/homebrew/bin:$PATH node tests/js/sandbox/check.mjs` | Final run passed syntax checks for 17 JavaScript files and whitespace checks for 23 lane files, including untracked additions, plus `git diff --check`. |

Final unit output:

```text
ℹ tests 48
ℹ suites 0
ℹ pass 48
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
```

Final source-check output:

```text
PASS syntax: 17 JavaScript files
PASS whitespace: 23 lane files, including untracked additions, and git diff --check
```

Earlier full-suite runs reported 0 passed / 1 failed during initial test import setup, then 28/0, 34/0, 34/0, 36/0, 44/0 and 47/0. A later stricter session-close assertion reported 47/1 because the host fixture had not actually transferred its port. Changing the fixture to perform a real structured-clone port transfer fixed it. The final result is 48/0. The source-check helper initially exited 1 because it treated the expected `git diff --no-index` difference status as a check failure even with no whitespace diagnostics. Its final version accepts that status only when there are no diagnostics, and passed. No failed check is being presented as a pass.

## Commit blocker

After the focused 26-test gate and `git diff --check`, this command was attempted:

```sh
git add src/desktop/sandbox tests/js/sandbox/env.mjs tests/js/sandbox/host.test.mjs tests/js/sandbox/loader.test.mjs
```

Git returned:

```text
fatal: Unable to create '/Volumes/Expansion/Development/Projects/living-spaces/.git/worktrees/sandbox/index.lock': Operation not permitted
```

The following `git commit -m "Implement versioned sandbox bridge and collection loader"` in the command chain did not execute because `git add` failed. This session cannot request an override. No commits were created. The branch remains `forge/r1-sandbox`, based on `1fe4c57`. Forge must stage and commit the working-tree files, including this report, in an environment that permits Git metadata writes.

## Integration notes

The UI supplies the frozen bundle, session, grant list and `call(op,args)` returning `{ok,result}` or `{ok:false,error}`. `mountSpace` returns only `postEvent` and `destroy`. It emits `booted` when the channel is handed to the shell, not when every application module has completed. On `reloaded`, the UI closes the backend session and remounts. Grant changes should remount or update the passed grant list; the backend remains authoritative.

A basic kit app can call `hashRouter({'/': Overview, '/library': Library, '/item/:id': Detail})`, read `{component,params,path}` through `useRoute()`, and render the selected component with `html`. `useRecord` returns `{record,loading,error,reload}`. `useSaveState` adds `current` to its result on conflict; `run` records failure and resolves `undefined`, so callers read its state rather than relying on a thrown error. `ConflictBanner` passes `current` into `onKeepMine` and `onUseUpdated`. `Nav` accepts `items:[{path,label}]`.

Log overflow uses a standard warning log entry, `Space log overflow: dropped N entries`, within the existing `{entries}` shape. The host emits one `log-overflow` event per mount when it sees the warning or drops a too-frequent batch. Every forwarded log batch has at most 50 entries and each message has at most 4000 characters.

## Not done or unproven

- The required headless Chrome smoke is blocked at the loopback listener. Its driver and fixtures are implemented, but browser DOM rendering, CSP enforcement, actual opaque-frame access denial, dynamic import execution, and actual reload detection need a successful run outside this restriction. The browser driver itself may need fixes after its first permitted run.
- Real isolated Hermes Desktop, real chat creation, persistence, refresh backend authority, scheduled runs, cross-Space isolation, restart and revocation integration are Forge's acceptance work. The smoke bridge is explicitly in-memory and is not persistence evidence.
- The known WebRTC exception is disclosed verbatim. This lane does not close it or claim zero outbound data.
- Runtime insertion of stylesheet links inside nested HTML views remains out of scope as commissioned. CSS `@import`, `srcset`, and `new URL(asset, import.meta.url)` are not added by this lane.
- Query strings on bundled references are treated as cache-busting and collapse to one immutable bundled file. Separate module instances distinguished only by query string or fragment are not provided.
- The import rewriter is a small lexical transform, not a complete ECMAScript parser. Tests cover static imports and exports, computed dynamic imports, template expressions, comments, strings, common regex literals and division. Unusual valid JavaScript syntax still needs browser qualification.
- No independent review was performed or claimed.
- Code and report could not be committed because Git metadata writes were denied.

## Contract issues

No change to the frozen contracts is requested. The source spec still labels itself proposed, but the current lane commission explicitly authorizes implementation; the spec was left untouched. The pre-existing `src/desktop/spike-plugin.src.js` still uses the old spike API and an old `../core/sandbox-core.js` import. It is outside this lane's ownership. The UI lane must use the frozen `src/desktop/sandbox/index.js` seam, as already specified in CONTRACTS.md section 12.

The Model the Domain principle shaped the op/grant table and explicit mount lifecycle. Boundary Discipline put request and log validation at the host port. Prove It Works produced rerunnable Node gates and the CDP driver; the failed browser preflight remains a named verification gap.
