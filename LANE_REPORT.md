# w2-submission lane report

Ife needs the submission drafts to describe the current Living Spaces candidate
without turning partial R1 evidence into release acceptance. This lane updates
only submission documentation, the package README and a catalog consistency
checker. No product code, manifest, contract or R1 status file changed.

**Verdict: ISSUES.** Requested artifacts and offline verification are complete.
Staging and committing are blocked by the sandbox. Catalog/publication gates and
R1 acceptance remain open as detailed below. No push was attempted.

## Files changed

- `docs/submission/catalog-entry.draft.yaml` matches manifest name, description,
  version, Hermes floor and the 13 registered tools. Hooks, middleware and env
  declarations remain empty. Documents the distinct empty host-capability list
  and Desktop surface. Uses macOS-only qualification metadata. Keeps the private
  URL and literal `PIN_40_CHAR_SHA_AT_FINAL_COMMIT`.
- `scripts/check-catalog-draft.py` reads two YAML mappings using stdlib and PyYAML.
  It rejects name/version/floor or registration drift, a changed host-capability
  declaration, an invalid pin, missing required descriptive fields, incorrect
  package/category or a missing Desktop entrypoint. Optional file arguments let
  reviewers test malformed drafts without changing the real one.
- `src/living-spaces/README.md` documents package placement, both enable switches,
  grant revocation, archive/delete, local profile SQLite, no telemetry, chat/model
  context, the exact WebRTC disclosure and the private scheduling import/reason.
  Corrects the typed-ID deletion instruction. Separates historical validation,
  observed paths and open R1 checks. Explains logical deletion and uninstall
  retention without claiming secure erasure or an uninstall rehearsal.
- `docs/submission/PR-DESCRIPTION.draft.md` carries the same disclosures, install
  and lifecycle instructions, validation receipt and remaining acceptance work.
  Removes stale validator TODO and false Claude Code attribution.
- `docs/submission/DEMO-SCRIPT.md` retains 11 shots totaling 83 seconds, uses public
  arXiv/Research Desk and Pair Play content, accepts truthful no-change refresh,
  and defers final footage/screenshots until Miro's design kit merges.
- `docs/submission/CHECKLIST.md` covers preflight, entry schema, all 18 admission
  rules, PR/CI/reviewer stages and the separate publication/demo/Typeform gates.
- `LANE_REPORT.md` is this requested handoff, explicitly authorized outside the
  lane's normal owned paths.

## Verification and exact commands

Commands ran from this worktree. Test homes and generated artifacts are under
`.run/`. Nothing was installed. No Desktop, gateway, Chrome, scheduler service,
HTTP server or other listener was started. The unit tests exercise cron functions
only against temporary test homes; this is not a running cron scheduler.

### Catalog checker

```sh
~/.hermes/hermes-agent/venv/bin/python scripts/check-catalog-draft.py
```

- Red, before draft edits: exit **1**, `FAIL: sha must be
  PIN_40_CHAR_SHA_AT_FINAL_COMMIT or a 40-hex SHA` against the old
  `PIN_AT_SUBMISSION` value.
- Green, after draft edits and again after final review: exit **0**, `PASS:
  catalog draft matches plugin.yaml (13 tools); pin syntax accepted`.
- This is a draft consistency check, not the Hermes validator and not permission
  to submit a placeholder as a real catalog pin.

```sh
~/.hermes/hermes-agent/venv/bin/python .run/w2-submission/check-draft-cases.py
PYTHONPYCACHEPREFIX="$PWD/.run/w2-submission/pycache" ~/.hermes/hermes-agent/venv/bin/python -m py_compile scripts/check-catalog-draft.py
```

The local temporary verification driver passed **24/24**, exit **0**. It invokes
the checker in subprocesses against YAML copies in a temporary directory. Cases
cover the placeholder, two valid full SHAs, eight invalid pins, name/version/floor
drift, each of four registration lists, three invalid capability mappings,
category/subdir drift and a newly declared manifest host capability. The real
manifest was never edited. Receipt is `.run/w2-submission/catalog-cases.log`.
Compilation exited **0**. No product fix was made, so a product red/green run is
not applicable; the existing bridge fix is reported only from R1 evidence.

### Python

The stock discovery includes
`tests.python.test_upkeep_runs.RunTests.test_manual_refresh_from_local_server_has_provenance_and_timestamps`,
which constructs `ThreadingHTTPServer(("127.0.0.1", 0), ...)`. The hard lane
boundary forbids listeners, so the runner marked exactly that method skipped
before running the discovered suite. It did not try to bind and did not fabricate
a sandbox error. Test files remain unchanged.

```sh
HERMES_HOME="$PWD/.run/w2-submission/home" LIVING_SPACES_DB="$PWD/.run/w2-submission/home/spaces.db" PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" ~/.hermes/hermes-agent/venv/bin/python .run/w2-submission/run-python.py > .run/w2-submission/python.log 2>&1
```

Exit **0**. **151 discovered/run, 150 passed, 0 failures, 0 errors, 1 skipped**.
The runner used `unittest.defaultTestLoader.discover('tests/python',
top_level_dir='.')`, set the named method's `__unittest_skip__` and
`__unittest_skip_why__`, then ran `unittest.TextTestRunner(verbosity=2)`.
The runner and raw log are local ignored artifacts, not committed product files.

Forge's full stock command outside the no-listener lane is:

```sh
~/.hermes/hermes-agent/venv/bin/python -m unittest discover -s tests/python -t .
```

### JavaScript and rendering

Generated the dependency-graph prerequisite into `.run/`, leaving the shipped
bundle untouched:

```sh
esbuild src/desktop/plugin.src.js --bundle --format=esm --jsx=automatic --external:@hermes/plugin-sdk --external:react --external:react/jsx-runtime --outfile=.run/package/plugin.js --metafile=.run/package/desktop-metafile.json
```

Exit **0**. The UI unit entry is `tests/js/ui/index.js`; no `ui/*.test.mjs` files
exist, so the stock glob was adjusted.

```sh
node --test tests/js/sandbox/*.test.mjs tests/js/ui/index.js tests/js/reference/*.test.mjs > .run/w2-submission/node.log 2>&1
```

Initial attempt reported **97 tests, 94 passed, 3 failed file starts**.
`hooks.test.mjs`, `html.test.mjs` and `compatibility.test.mjs` could not resolve
`preact`. Exact error was `Error [ERR_MODULE_NOT_FOUND]: Cannot find package
'preact' imported from .../src/living-spaces/runtime/vendor/hooks.mjs`. The tool
wrapper ended with `tail`, so its shell exit 0 was not a passing Node test run.

```sh
node --import ./tests/js/sandbox/env.mjs --test tests/js/sandbox/*.test.mjs tests/js/ui/index.js tests/js/reference/*.test.mjs > .run/w2-submission/node-with-env.log 2>&1
```

With the existing resolver preloaded, exit **1**, **113 tests, 112 passed,
1 failed file start**. Exact error was `SyntaxError: The requested module
'node:vm' does not provide an export named 'SourceTextModule'` in the reference
suite. That suite needs Node's VM modules flag. No source or test edits were made.

```sh
node --experimental-vm-modules --import ./tests/js/sandbox/env.mjs --test tests/js/sandbox/*.test.mjs tests/js/ui/index.js tests/js/reference/*.test.mjs > .run/w2-submission/node-final.log 2>&1
node tests/js/ui/render-smoke.mjs > .run/w2-submission/render.log 2>&1
node scripts/check-renderer-graph.mjs .run/package/desktop-metafile.json
```

Final Node exit **0**, **131 tests passed, 0 failed, 0 skipped**. Static rendering
exited **0** with **40 assertions** and 12 HTML fixtures. Graph gate exited **0**,
`Renderer graph excludes guest code and guest HTML`. Rendering is not real
Desktop acceptance. No app-driving harness was written or executed in this lane.

### Documentation and whitespace

A read-only `python3 -` assertion pass checked the following against actual files:

- The spec section 2 disclosure is verbatim in README, PR draft and catalog draft.
- All **21** relative Markdown file links resolve.
- All **11** shot budgets sum to **83 seconds**, below 90.
- Checklist includes all **18** numbered admission rules and all four separate
  Ife approval gates.
- The obsolete `PIN_AT_SUBMISSION` placeholder is absent.

All five groups passed, exit **0**. The sources of current behavior were the
manifest, spec, frozen contracts, R1 ledger, committed validator receipt, current
host controls and read-only Hermes install/removal implementation. The GBrain
context pack supplied no current implementation authority.

```sh
git diff --check
git diff --cached --check
```

Both exited **0** before the attempted commit. The cached check was empty because
staging failed. The final working-tree check also exited **0**.

```sh
node tests/js/sandbox/check.mjs
```

Exit **0**. Syntax passed for **18 JavaScript files**; whitespace passed for
**24 lane files** including this report and the working-tree diff.

## Git handoff failure

Attempted the small verified catalog/checker commit with:

```sh
git add scripts/check-catalog-draft.py docs/submission/catalog-entry.draft.yaml
git diff --cached --check
git commit -m 'Align catalog draft with manifest and check metadata drift'
```

Both staging and commit failed with:

```text
fatal: Unable to create '<shared-repo>/.git/worktrees/w2-submission/index.lock': Operation not permitted
```

The shared Git metadata path is sandbox-denied despite being listed as a writable
root. Approval escalation is disabled. Changes remain **unstaged**, not committed.
No alternate index, direct Git-object write or permission bypass was attempted.
Forge can stage and commit these seven owned/requested files from an authorized
shell after reviewing them. Do not push as part of this lane.

## Not done and proven issues

1. No final package validator run or final SHA pin. Historical receipt remains
   `docs/evidence/runs/validate-8724804/raw.log`, exit 0, 16 passed checks, one
   private `cron.jobs` warning. The checker does not replace that run.
2. Private API admission remains unresolved. The guide requires public surfaces;
   it warns on this import even when `no core override` passes. README/PR explain
   the missing public no-agent job creation/control seam. Forge must settle it
   with maintainers before claiming catalog compliance.
3. R1-01 and R1-12 are pending. R1-02 is pre-packaging evidence; R1-03 through
   R1-11 remain partial. All specific missing observations from the current
   ledger are listed in README/PR/checklist. No acceptance status was changed.
4. Existing schedule/lifecycle/repair evidence includes disclosed fixtures and
   harness accommodations. The demo does not use injected source divergence as
   live retrieval, and does not claim a fixture is an unedited user journey.
5. Final screenshots/video are not captured. They follow Miro's design kit merge
   and Forge's qualification. No test schedule was created by this lane; cleanup
   of existing qualification jobs remains Forge's release-end work.
6. Linux/Windows are unqualified. Catalog `platforms: []` previously implied all
   platforms; the draft now limits its claim to macOS.
7. The prior README described an unverified local-directory installer and typed
   deletion ID. Current docs use whole-package placement and the actual host
   confirmation. The current Hermes removal implementation leaves profile plugin
   data; no uninstall runtime rehearsal was performed.
8. `projects.delete_space` removes records/revisions and dependent Space rows but
   does not garbage-collect `blobs`. Docs now disclose that project file blobs can
   remain; deletion is not secure erasure. A general data-erasure guarantee would
   require a separately scoped design and tests.
9. Raw Node commands lacked two existing test prerequisites. Corrected invocation
   passed without code edits or package installation. One Python listener case
   remains for Forge, as stated above.
10. Staging and commit are sandbox-blocked. No commits or pushes were created.
11. Public repo, catalog PR, demo-video publication and Typeform submission still
    need separate Ife approval. No external publication, issue, PR, message or
    submission was performed. Final name/lineage audit and catalog CI are pending.

## Contract issues and spec gaps

- Spec section 2 permits granting a narrower scope. The frozen R1 contract and
  UI expose approve/deny/revoke for the requested scope, with no narrower choice.
  R1-STATUS already discloses the gap. Proposed resolution is for Forge/Product
  to decide whether to amend R1's accepted scope explicitly or commission narrow
  grants with tests. Docs cannot silently mark this requirement complete.
- Catalog and manifest both use the name `capabilities` for different shapes.
  The catalog has a registration mapping; the manifest has a host-permission
  list. The checker compares registration fields and separately rejects changes
  from the disclosed empty host-permission list. No invented catalog field or
  manifest edit was used. Desktop is an entrypoint/category, not a manifest key.
- No new bridge-contract disagreement was found. Typed `limit`/`invalid`
  responses require a usable request ID; docs preserve that qualification.
- The spec requires explicit deletion and loss disclosure, not typed-ID input or
  secure media erasure. The README's typed-ID claim was corrected to the actual
  host control. Product should specify any future stronger erasure guarantee
  separately, including retained blobs and backups.
- No contract/spec files were edited. No new app harness needs a Forge command.
  Forge owns the remaining existing R1 harness runs serially under the shared
  isolated app protocol; this lane does not instruct parallel app execution.
