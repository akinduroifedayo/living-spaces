# c-guest lane report

Ife needs agent-built Spaces to retain their authored root styling, apply manifest themes, resolve assets created in the DOM after boot, and call the mediated fetch bridge. This lane implements those four guest-loader behaviors.

**Verdict: ISSUES.** All requested guest changes and regression tests are complete. Python passes 218/218 and the complete serial Node suite passes 189/189. The concurrent Node suite twice fails one unchanged timing-sensitive host assertion. Git staging is sandbox-blocked, so no commit could be created. Real Desktop qualification and cross-lane integration remain with Forge. No release acceptance is claimed.

Branch `forge/r1-c-guest`, base `7febcd8`. No push was attempted.

## Files changed

- `src/guest/loader.mjs` adds 41 lines. Copies only `lang`, `dir`, `class`, `data-*`, and `style` from the parsed root. Root event handlers and other attributes are omitted. Body copying stays intact.
- The loader applies any of the seven frozen manifest presets after root copying. Valid tokens become one `style[data-space-theme]` before entry stylesheets. Token names, value types, forbidden characters/substrings, 200-character values, and the 64-token limit are checked again. Invalid settings are skipped with one warning per boot.
- The loader exposes `space.asset(path)` through the existing project resolver and blob map. Paths resolve from the project root, including `./` normalization. Missing, external, non-string and malformed paths return `null`.
- The loader exposes `space.net.fetch(url, {method, headers, body, as})`. It sends `net.fetch` with the frozen fields, omits only undefined values among those fields, and returns the existing bridge promise. Host errors and session closure retain their existing behavior.
- `tests/js/sandbox/c-guest.test.mjs` adds ten behavior tests. It reuses `env.mjs`, the installed JSDOM dependency resolution pattern from UI tests, the serialized guest producer, and Node blob storage. No existing fixture or test changed.
- `LANE_REPORT.md` replaces the inherited lane report with this handoff, as requested.

`src/guest/document.mjs` needed no change. The generated guest HTML was rebuilt for tests and restored before staging. The renderer prerequisite was built only into `.run/package/`. No generated artifact belongs in this commit.

## Decisions and boundaries

The Model the Domain principle kept the implementation on the existing path-to-blob map and the frozen theme/fetch objects. No new asset registry, bridge transport or configuration layer was introduced.

For an over-limit token map, the loader considers the first 64 entries in object order and skips the excess with the same single warning. Invalid entries within that prefix are skipped. Values count Unicode characters, matching Python string-length semantics. Empty or wholly invalid token maps emit no empty style element. An invalid preset leaves the entry's root preset intact.

The entry root's inline style retains normal CSS priority. Manifest tokens are inserted before all app CSS as frozen, so later app or kit CSS may override them. No kit CSS was edited.

The requested grounding report, spec sections 2 and 4, contracts, evidence status, and the four named Desktop harness sources were read. No callable GBrain tool was available in this session. Current repository code and the supplied frozen decisions were used as authority.

## Red then green evidence

The initial test run on the unmodified loader produced **0 passed, 10 failed**. The first implementation produced **10 passed, 0 failed**. Additional token-name line-ending cases passed without requiring a special-case guard.

The final test file was then rerun unchanged against the loader from `7febcd8`, followed by the final loader. Both runs rebuilt the guest document. Final results were **0/10 passing on base** and **10/10 passing on the repair**, with no skips. The saved final source and restored working source were compared byte-for-byte with `cmp`.

| Fix | Base failure | Repair evidence |
|---|---|---|
| Root attributes | Expected vetted root attributes, observed an empty root attribute map. | Exact allowed attributes present; `onclick`, `onload`, `id`, and `title` absent; body attributes and content retained. |
| Theme preset and ordering | Manifest preset absent. | Manifest wins; all seven presets work; tokens-only preserves the HTML preset; exactly one token style precedes linked, head-inline and body-inline app styles. |
| Theme validation | Expected token style absent; count-limit style absent. | Good tokens survive; malformed names/types/values and forbidden substrings are skipped; 64 properties maximum; exactly one warning for invalid settings. |
| Late asset helper | `api.asset is not a function`. | An image appended after boot receives a blob URL. Resolving that URL returns `image/png` and bytes identical to the bundled PNG. Nested entry location does not change root-relative lookup. |
| Mediated fetch | `Cannot read properties of undefined (reading 'fetch')`. | Exact v1 operation/args, omitted undefined fields, preserved falsy values, reply passthrough, four frozen host error codes, and session closure all pass. |

Local raw receipts are in `.run/c-guest/`, excluded from Git. `red.log` and `green.log` are the initial pair; `token-edge-check.log` is the passing edge-case check; `final-red.log` and `final-green.log` are the final unchanged-test pair.

Commands for the final pair were:

```sh
cp src/guest/loader.mjs .run/c-guest/loader-final.mjs
trap 'cp .run/c-guest/loader-final.mjs src/guest/loader.mjs' EXIT
git show 7febcd8:src/guest/loader.mjs > src/guest/loader.mjs
node scripts/build-sandbox.mjs
node --test tests/js/sandbox/c-guest.test.mjs > .run/c-guest/final-red.log 2>&1
cp .run/c-guest/loader-final.mjs src/guest/loader.mjs
node scripts/build-sandbox.mjs
node --test tests/js/sandbox/c-guest.test.mjs > .run/c-guest/final-green.log 2>&1
cmp src/guest/loader.mjs .run/c-guest/loader-final.mjs
```

The baseline test exit was 1 and repair exit was 0. The execution also saved both statuses and checked those expected values after restoring the source.

## Required suites and checks

Full-suite commands ran with this environment prefix. Individual fixtures further allocate their own temporary homes under `.run/`.

```sh
HERMES_HOME="$PWD/.run/c-guest/test-home" LIVING_SPACES_DB="$PWD/.run/c-guest/test-home/spaces.db" PYTHONDONTWRITEBYTECODE=1
```

The following are the exact test invocations after that prefix:

```sh
~/.hermes/hermes-agent/venv/bin/python -m unittest discover -s tests/python -t .
node --test tests/js/sandbox/*.test.mjs tests/js/ui/*.test.mjs tests/js/reference/*.test.mjs
node --experimental-vm-modules --import ./tests/js/sandbox/env.mjs --test tests/js/sandbox/*.test.mjs tests/js/ui/*.test.mjs tests/js/reference/*.test.mjs tests/js/ui/index.js
node --import ./tests/js/sandbox/env.mjs --test tests/js/sandbox/host.test.mjs
node --experimental-vm-modules --import ./tests/js/sandbox/env.mjs --test --test-concurrency=1 tests/js/sandbox/*.test.mjs tests/js/ui/*.test.mjs tests/js/reference/*.test.mjs tests/js/ui/index.js
```

| Run | Actual result | Receipt |
|---|---|---|
| Python stock | 218 passed, 0 failures/errors/skips; exit 0. | `python.log` |
| Node stock globs | 122 passed, 3 failed test-file startups; 125 reported tests; exit 1. | `node-stock.log` |
| Node with prerequisite import hook and VM flag, plus UI index | 188 passed, 1 failed, 0 skipped; exit 1. | `node-full.log` |
| Same concurrent invocation rerun, unchanged | 188 passed, 1 failed, 0 skipped; exit 1. | `node-full-rerun.log` |
| Host test file alone | 35 passed, 0 failed/skipped; exit 0. | `host-rerun.log` |
| Full suite serially | 189 passed, 0 failed/skipped; exit 0. | `node-serial.log` |

The stock Node failures were startup errors in `compatibility.test.mjs`, `hooks.test.mjs`, and `html.test.mjs`. Exact error excerpt was `Error [ERR_MODULE_NOT_FOUND]: Cannot find package 'preact'`. Preloading the existing sandbox import hook resolves Preact before static test imports; `--experimental-vm-modules` enables the reference suite's `SourceTextModule`/`SyntheticModule`. No package installation or test-source change was needed. The UI `index.js` was included explicitly so the glob did not omit its cases.

Both concurrent failures were `mount binds boot to host session, forwards replies and emits versioned events`, at `tests/js/sandbox/host.test.mjs:103`. Actual was `0`, expected `1`, after the existing `await delay(20)`. The isolated file and the serial suite pass. This lane did not modify or relax that assertion. Serial success does not erase the concurrent failures.

Build and static verification commands were:

```sh
node scripts/build-sandbox.mjs
esbuild src/desktop/plugin.src.js --bundle --format=esm --jsx=automatic --external:@hermes/plugin-sdk --external:react --external:react/jsx-runtime --outfile=.run/package/plugin.js --metafile=.run/package/desktop-metafile.json
node scripts/check-renderer-graph.mjs .run/package/desktop-metafile.json
node --check src/guest/loader.mjs
node --check tests/js/sandbox/c-guest.test.mjs
node tests/js/sandbox/check.mjs
git diff --check
```

Guest build, temporary renderer build, renderer graph exclusion, and the two focused syntax checks passed. The sandbox syntax/whitespace check and final diff check are recorded at handoff below. The serial suite includes the deterministic installed-document equality checks against the rebuilt guest artifact. No release-wide Hermes validator or app-driving command ran.

## Harnesses and what is not done

No harness was authored or executed. Harness paths are outside this lane's ownership. Therefore there is no new Python harness to compile or execute. Forge owns serialized real-Desktop qualification after integration, using the existing `guest_realm.py`/`cdp.py` pattern that this lane read.

JSDOM proves root attributes, stylesheet DOM order and generated loader behavior. Node blob resolution proves URL backing, MIME and byte identity. These are not Chromium image decoding, computed-theme rendering or CSP acceptance. No real Desktop, gateway, Chrome, network listener or scheduler was started or changed. No unit test made a network request.

The guest fetch tests use a fake message port. Host/backend policy, default `net` grants, revocation, and real fetch results depend on c-netfetch and remain unqualified here. Manifest admission remains c-tools' work. Dynamic references require explicit `space.asset`; no automatic DOM observer or late-reference rewriting was added.

## Contract issues and spec gaps

1. The frozen prompt introduces `theme`, `space.asset`, and `net.fetch`, but `CONTRACTS.md` sections 3, 5 and 7 do not yet describe them. No frozen decision was changed. Forge should merge the agreed theme validation, preset precedence, asset helper and fetch/grant shapes into the contract during integration.
2. Spec section 2 says creation grants no outside capabilities, while frozen decision 3 grants `net` by default. R1-01 also speaks broadly about ordinary HTTP exfiltration blocking. Forge/Product should record the approved mediated-network exception, distinguish it from direct guest network access, and align R1-01/R1-05 probes and disclosure with the chosen default. This lane preserves CSP and implements only the mandated guest wrapper.
3. The concurrent host assertion above remains a reproducible test issue in this worktree. Proposed follow-up is a bounded condition-based wait in its owning lane, with a baseline run and preserved failure receipts. No out-of-scope fix was attempted.
4. Serial Node discovery must include standalone tests and `tests/js/ui/index.js`. The raw command also needs the existing import-hook/VM prerequisites. Forge should preserve these in the canonical test runner.
5. Real-Desktop visual/image and integrated fetch verification remain required before claiming acceptance. The proposed check is to mount a public fixture with conflicting HTML/manifest presets, inline and linked CSS, and a PNG assigned through `space.asset` after boot; inspect root attributes, computed tokens and image dimensions in the actual guest realm, then exercise fetch grant and revocation through the integrated host.

## Handoff state

`node tests/js/sandbox/check.mjs` passed syntax for 20 JavaScript files and whitespace for 26 lane files, including untracked additions. `git diff --check` passed. Both generated artifacts match HEAD, confirmed by `git diff --exit-code -- src/living-spaces/guest/space-host.html src/living-spaces/desktop/plugin.js`. The renderer artifact was never changed.

`git restore --source=HEAD -- src/living-spaces/guest/space-host.html` failed because the sandbox denied creation of `.git/worktrees/c-guest/index.lock` with `Operation not permitted`. The generated HTML was instead restored using the read-only Git command and an authorized worktree write:

```sh
git show HEAD:src/living-spaces/guest/space-host.html > src/living-spaces/guest/space-host.html
```

Forge must run `node scripts/build-sandbox.mjs` before rerunning the deterministic-document tests on this source-only handoff. The committed generated HTML intentionally remains at the base until the integration rebuild.

`git add src/guest/loader.mjs tests/js/sandbox/c-guest.test.mjs LANE_REPORT.md` failed with the same `index.lock` error, exit 128. The chained `git commit -m "Apply guest themes and expose asset and mediated fetch helpers"` therefore could not run. Changes cannot be left staged under this sandbox. No commit or push was created. Only the loader, new regression test and this report remain changed. Forge must stage and commit them outside this sandbox.
