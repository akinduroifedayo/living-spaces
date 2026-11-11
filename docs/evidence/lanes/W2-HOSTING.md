# w2-hosting lane report

Living Spaces needs executable R1-01 evidence against the integrated Desktop sandbox. This lane supplies the disposable fixture, adversarial qualification harness, and evidence guide. **Verdict is ISSUES.** Offline verification is available; actual Desktop qualification remains unexecuted under the lane's hard execution boundary. R1-01 is not promoted.

## Files changed

- `harness/qualify_hosting.py` owns loopback HTTP/raw TCP/UDP canaries, pre-boot CDP Network capture, fixture lifecycle, probe orchestration, canonical SQLite comparisons, origin-diagnostic collection and receipts.
- `harness/fixtures/hosting/index.html`, `main.mjs`, `views/detail.mjs`, `theme.css`, and `images/mark.svg` form the two-view multi-file positive control. Core adds the existing packaged Preact library.
- `harness/fixtures/hosting/probes.mjs` implements hostile main-world, nested-frame, worker, navigation, privileged-read, spoofed-message and WebRTC probes.
- `tests/js/sandbox/hosting.test.mjs` executes the generated Worker, SharedWorker and nested-srcdoc programs with network-free fakes. It verifies their attempted requests and execution receipts.
- `docs/evidence/R1-01-HOSTING.md` documents containment, expected observations, the exact spec exception, source-grounded Chromium diagnosis, limits and Forge's run command.
- `LANE_REPORT.md` is this handoff.

No production source changed. No policy, sandbox token, contract, Python core, upkeep, UI, skill, reference example, other harness, or shipped bundle was edited. The local esbuild output used for tests is under ignored `.run/package/` only.

## Verification and exact commands

Commands ran from the assigned worktree. The Python and JavaScript tests use their existing temporary `HERMES_HOME` / `LIVING_SPACES_DB` setup under `.run/`. No package was installed. No Desktop, gateway, Chrome, listener or scheduler was started or stopped.

| Command | Observed result |
|---|---|
| `~/.hermes/hermes-agent/venv/bin/python -m unittest discover -s tests/python -t .` | 151 tests run, 150 passed, 1 skipped, 0 failures. Output retained in `.run/hosting-python-tests.log`. |
| `node --test tests/js/sandbox/*.test.mjs tests/js/ui/*.test.mjs tests/js/reference/*.test.mjs` | Did not start. `zsh:1: no matches found: tests/js/ui/*.test.mjs`. UI tests are `tests/js/ui/index.js`. |
| `node --test tests/js/sandbox/*.test.mjs tests/js/reference/*.test.mjs` | 67 reported tests, 63 passed, 4 failed. Three test files could not resolve `preact`; one assertion lacked `.run/package/desktop-metafile.json`. Log `.run/hosting-js-tests.log`. |
| `esbuild src/desktop/plugin.src.js --bundle --format=esm --jsx=automatic --external:@hermes/plugin-sdk --external:react --external:react/jsx-runtime --outfile=.run/package/plugin.js --metafile=.run/package/desktop-metafile.json` | Exit 0. Generated the real renderer dependency graph required by the stock test. Shipped bundle untouched. |
| `node --import ./tests/js/sandbox/env.mjs --test tests/js/sandbox/*.test.mjs tests/js/ui/index.js tests/js/reference/*.test.mjs` | 113 reported tests, 112 passed, 1 file failed to start. `SyntaxError: The requested module 'node:vm' does not provide an export named 'SourceTextModule'`. Log `.run/hosting-js-prepared-tests.log`. |
| `node --experimental-vm-modules --import ./tests/js/sandbox/env.mjs --test tests/js/sandbox/*.test.mjs tests/js/ui/index.js tests/js/reference/*.test.mjs` | Before new harness tests, 131/131 passed. Final count below. Uses the existing resolver hook and VM flag; no dependency installation. |
| `node --import ./tests/js/sandbox/env.mjs --test tests/js/sandbox/hosting.test.mjs` | Initial 2 passed / 1 failed from comparing an array from another VM realm with `deepStrictEqual`. Fixed the assertion to create a host-realm array. Rerun 3/3 passed. This was a harness-test assertion error, not a product defect. |
| `python3 -m py_compile harness/qualify_hosting.py` | Passed. Does not import or execute the Desktop harness. |
| `node --check harness/fixtures/hosting/probes.mjs` | Passed. |
| `node --check harness/fixtures/hosting/main.mjs` | Passed. |
| `node --check harness/fixtures/hosting/views/detail.mjs` | Passed. |

A separate inline Python check used the existing Hermes interpreter, a fresh `.run/` temporary directory and real core, without importing `qualify_schedule` or contacting CDP. Six assertions passed for exact fixture id, seven admitted files, bare Preact import mapping, byte-identical packaged vendor file, stable canonical snapshot and detection of a record mutation. The temporary database was removed. This is offline fixture admission, not Desktop evidence.

## Product fixes and red/green evidence

None. Reading the integrated producers and bridge did not establish a new containment defect. No product fix or security red/green claim is made. The new fixture tests validate executable probe generation only; they do not simulate Chromium security enforcement.

## Harness written but not executed

Forge must run this serially from the integrated candidate worktree, with the isolated Desktop already running on its Spaces index and no protected Space session open:

```sh
LS_CDP_PORT=9341 ~/.hermes/hermes-agent/venv/bin/python harness/qualify_hosting.py
```

The helper modules currently bind `Build/living-spaces-r1`. A pre-existing `hosting-probe` is refused. The harness creates only that fixture through core, snapshots Research Desk and Pair Play without mounting or changing either, and deletes the fixture in `finally`. It verifies the mounted guest HTML equals the reviewed package. Any failed assertion or incomplete run produces nonzero status. Snapshot evidence contains hashes, not active session identifiers.

Outputs are `evidence/hosting/<timestamp>/hosting.json`, `listeners.json`, `network.json`, and before/after snapshot digests beneath the isolated build directory. WebRTC has a recorded `packet_arrived` observation and `asserted_blocked: false`. No result from this lane says those runtime assertions passed.

## Proven issues, limitations and remaining work

1. Git index writes are denied by this sandbox, so staging and committing could not complete. Authored files are intact and unstaged.
2. R1-01 remains pending because real Desktop execution is forbidden in this lane. Forge must execute the harness and audit its receipts before acceptance.
3. The stock JS command needs the actual UI filename, the existing Preact resolver preload, `--experimental-vm-modules`, and a generated renderer metafile in a fresh worktree. The failed attempts and successful prepared run are reported above.
4. The spike retained six `site_info.cc:925` origin checks without stack traces or per-probe timestamps. Current Chromium source identifies the matching precursor-origin assertion in sandboxed data-URL site selection. Exact historical binary revision/flags and trigger remain unproved. The evidence document separates source facts from inference.
5. The new WebRTC probe observes STUN only. It does not rerun historical TURN payload exfiltration or prove closure when UDP is absent during the observation interval.
6. The whole-database spoof comparison fails if another lane or approved schedule writes concurrently. This is intentional; the harness never changes schedules to make its result pass.
7. Real CDP target timing, browser behavior, listener delivery, frame reload behavior and cleanup still need Forge's execution. Offline syntax and mocks cannot establish them.
8. The full plugin/catalog validator was not rerun. No package/source changes require dependency installation; the lane's permitted gates were the stock unit suites and offline checks. The integrated candidate still needs Forge's release validation.

## Contract issues and spec gaps

No contract change requested. A3's session-free guest boot is respected. The spec explicitly permits the known WebRTC exception and does not justify widening any sandbox or CSP permission.

Proposed resolution for nested blob coverage is to record explicit CSP frame rejection when the blob document cannot execute. Require actual execution and all eleven probe receipts from the fresh srcdoc child. A timeout alone fails. The spec does not prescribe observation windows; this harness records its bounded windows and never generalizes a zero-hit window into zero possible network egress.

## Final verification

Final prepared JS suite passed **134/134**, with zero failures, cancellations or skips. Log is `.run/hosting-js-final-tests.log`. Python passed **150**, skipped **1**, failed **0** out of 151. `node tests/js/sandbox/check.mjs` passed syntax for 19 JavaScript files and whitespace for 25 lane files. Fixture-module syntax checks and Python compilation passed. `git diff --check` passed. An explicit `git diff --no-index --check /dev/null <file>` loop also passed for all ten untracked authored files, so the empty tracked diff is not the only whitespace check.

`node scripts/check-renderer-graph.mjs .run/package/desktop-metafile.json` passed. The final focused fixture test rerun passed 3/3 after cleanup changes.

Git staging and commit are **blocked by the filesystem sandbox**. `git add harness/qualify_hosting.py harness/fixtures/hosting tests/js/sandbox/hosting.test.mjs` and `git commit -m "test: add integrated hosting qualification harness"` both failed with:

```text
fatal: Unable to create '/Volumes/Expansion/Development/Projects/living-spaces/.git/worktrees/w2-hosting/index.lock': Operation not permitted
```

The lane cannot leave files staged because the index lock itself is denied. All ten authored files remain untracked in `forge/r1-w2-hosting`. No commit exists and no push was attempted. Forge should stage and commit them from a context allowed to write this worktree's Git index. No permission escalation was attempted.
