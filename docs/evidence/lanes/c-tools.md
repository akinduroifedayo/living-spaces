# c-tools lane report

Ife wants agents to build distinctive Spaces with generated assets, validated
themes and selected offline libraries. This lane implements those agent-tool
paths without changing guest rendering or automatically editing app HTML.

**Verdict: ISSUES.** All requested product changes pass focused and Python
regressions. The complete JavaScript suite passes serially; its parallel run
exposes an existing fixed-delay host test failure. Package validation passes
with two warnings in unchanged files. Git staging is sandbox-blocked. No push
was attempted. This is not a real-Desktop or R1 acceptance verdict.

Base is `7febcd8`, branch `forge/r1-c-tools`. The supplied grounding report was
read in full before implementation, followed by the spec sections 2 and 4,
frozen contracts, R1 ledger and all four named harness files. No GBrain tool was
exposed in this session, so a context pack could not be pulled. No relevant Codex
memory entry was found. The supplied frozen decisions governed implementation.

## Files changed

- `src/living-spaces/__init__.py` accepts UTF-8 strings, binary `{b64, mime?}`
  descriptors, and write-only null deletions. Both tools decode at the boundary.
  Malformed descriptors and invalid base64 return `invalid` naming the path.
  Decoding rejects nonalphabet characters, whitespace, bad padding and nonzero
  pad bits. Limits count decoded bytes, including an encoded `space.json` before
  manifest extraction. Tool schemas and descriptions document generated Hermes
  images, audio, fonts, decoded limits and optional library selection on writes.
  Results include `notes` with the exact kit stylesheet link when kit CSS exists.
- `src/living-spaces/living_spaces_core/projects.py` validates optional theme
  objects inside normal manifest normalization. It rejects unknown theme keys,
  bad presets, malformed token maps/names/values and more than 64 tokens. It
  preserves valid CSS strings and optional-field presence without inventing a
  preset, tokens or accent mapping. Library groups derive from packaged
  `SHELF.json`; selection copies the exact declared files and licenses and adds
  declared aliases. Existing legacy groups retain their dependencies. Core
  `write_files(..., libraries=())` adds selected libraries within the revision
  transaction and respects `base_rev`, file/byte limits and explicit edits.
- `tests/python/test_c_tools.py` adds 23 tests using registered tool handlers and
  the real core, with fresh `HERMES_HOME` and `LIVING_SPACES_DB` under `.run/`.
  Assertions cover real PNG/WAV byte transport, descriptor/schema errors,
  decoded-byte limits, theme boundaries, exact shelf contents, preserving files
  and aliases, atomic errors and kit notes without HTML edits.
- `LANE_REPORT.md` replaces the inherited earlier lane report with this handoff.

`limits.py` did not need changing. No guest, bridge, grants, networking, upkeep,
kit CSS, build-space skill, spec or frozen contract file changed. Neither shipped
artifact changed. No credentials or private content were used.

## Decisions and limits of the implementation

- Model the Domain shaped the library implementation. Groups use the existing
  shelf's `files` and `imports` shape, including licenses, rather than a second
  inferred inventory of shelf payloads.
- Create retains its established Preact/hooks/kit defaults. Explicit `[]` copies
  nothing. Writes default to no additions. New shelf groups are never copied
  unless selected. Selecting a group again preserves existing files and aliases;
  explicit file replacements and null deletions win. Selection is additive, not
  a request to remove other already-installed groups.
- Optional `mime` must be a string. It is accepted but is not persisted as an
  override. The frozen descriptor decodes to bytes, and existing bundle MIME
  remains inferred from the path. Both tool descriptions tell agents to use the
  correct extension. No storage-schema change was introduced.
- Empty themes, empty token maps and empty CSS values are valid under decision 2.
  Presets and token names are case-sensitive. Forbidden CSS substrings are
  rejected case-insensitively. Values are not trimmed or rewritten.
- Kit guidance is informational `notes`, not a new error warning. It says to add
  `<link rel="stylesheet" href="kit/spaces-kit.css">` and adjust the relative
  path for a nested entry. It can recur on later edits while kit CSS is present.
  No HTML parsing or injection was added.

## Red-then-green evidence

The final 22-test regression file before the additional padding case was run
against the two original product files from `git show 7febcd8:<path>`. The current
product bytes were saved first and restored in a `finally` block. Tests stayed
unchanged during that replay. It exited 1 with **22 test methods, 96 failed
assertions/subtests, 3 schema lookup errors**. Three unaffected methods passed.
The schema errors were missing `anyOf` and write `libraries`, not import errors.

| Fix | Red evidence | Green evidence |
|---|---|---|
| Binary input and schema | 35 failing assertions/subtests and 2 missing-schema errors. PNG/WAV create rejected descriptors, limits returned invalid, and errors omitted paths. | All 8 original binary methods passed. PNG and PCM WAV create, read through `spaces_read_file`, write into the same Space, and bundle return identical bytes and SHA-256. |
| Theme validation | 44 failing subtests/assertions. Invalid shapes, presets, names, unsafe values and 65 tokens were accepted. | All 6 theme methods pass, including seven presets, tokens-only, both, optional absence, 40/41-character names, 200/201-character values and 64/65 tokens. |
| Shelf selection | Create rejected all four groups; writes ignored selection; schema omitted choices. These plus kit produced 17 failures and 1 schema error. | All 8 shelf/kit methods pass. Each group has an exact file-set and byte-content comparison with the packaged group, including licenses and WOFF2 paths. |
| Kit link | Both create and write lacked the exact link in warnings or notes. | The exact link is present after both selections; HTML remains byte-identical. |

One additional review regression tested `YWJj=`, `YWJj====` and `Zh==` against
create and write. With only `b64decode(validate=True)`, it exited 1 with **1
method, 6 failed subtests**, because Python accepted all three. The canonical
re-encoding check fixes it. The final focused run passes **23/23**, with no skips.

Exact focused commands, all from the worktree root:

```sh
PYTHONDONTWRITEBYTECODE=1 ~/.hermes/hermes-agent/venv/bin/python -m unittest tests.python.test_c_tools -v
~/.hermes/hermes-agent/venv/bin/python -B -m unittest tests.python.test_c_tools -v
PYTHONDONTWRITEBYTECODE=1 ~/.hermes/hermes-agent/venv/bin/python -m unittest tests.python.test_c_tools.BinaryTests.test_noncanonical_base64_is_rejected -v
```

The first command initially ran 21 methods before the encoded-manifest case was
added. That red run had 95 failures and 3 errors; its first green run passed
21/21. The baseline replay used the second command with 22 methods. The third
command is the separate padding red run. The first command's final run passed
23/23. Raw receipts remain in ignored `.run/c-tools-red.log`,
`.run/c-tools-red-final.log`, `.run/c-tools-padding-red.log` and
`.run/c-tools-green-final.log`.

Decoded limit tests temporarily lower the existing file/project constants to
1,024/2,050 bytes. Two identical 1,024-byte files fit despite their larger base64
representations; an extra 3-byte file fails the total limit at 2,051. A 1,025-byte
file fails the file limit. Errors preserve the previous revision. The stock core
limit tests also ran unchanged.

## Full verification

```sh
PYTHONDONTWRITEBYTECODE=1 ~/.hermes/hermes-agent/venv/bin/python -m unittest discover -s tests/python -t .
```

Final exit **0**, **241 passed, 0 failures, 0 errors, 0 skipped**. Earlier full
runs before the padding test passed 240/240. Raw final receipt is
`.run/c-tools-python-final.log`. The current suite uses injected transports;
there was no listener test to skip. No gateway, Desktop, Chrome, network listener
or cron scheduler was started, stopped or restarted. No package was installed.

JavaScript uses the existing Preact resolver and Node VM-module flag. The command
also includes `tests/js/ui/index.js`, which the `*.test.mjs` glob omits.

```sh
node --experimental-vm-modules --import ./tests/js/sandbox/env.mjs --test tests/js/sandbox/*.test.mjs tests/js/ui/*.test.mjs tests/js/ui/index.js tests/js/reference/*.test.mjs
```

- First run exited **1**, **178 passed / 179 total**, with one missing prerequisite.
  The renderer graph test reported `ENOENT: no such file or directory, open
  '.run/package/desktop-metafile.json'`.
- Generated only ignored build output with the command below. Exit **0**.
- Next two unchanged parallel runs each exited **1**, **178 passed / 179 total**.
  `host.test.mjs:103` in `mount binds boot to host session, forwards replies and
  emits versioned events` reported `0 !== 1` after its existing `await delay(20)`.
- Serial execution exited **0**, **179 passed, 0 failed, 0 skipped**. This supports
  timing sensitivity; it does not prove the cause or fix the parallel gate.

```sh
esbuild src/desktop/plugin.src.js --bundle --format=esm --jsx=automatic --external:@hermes/plugin-sdk --external:react --external:react/jsx-runtime --outfile=.run/package/plugin.js --metafile=.run/package/desktop-metafile.json
node --experimental-vm-modules --import ./tests/js/sandbox/env.mjs --test --test-concurrency=1 tests/js/sandbox/*.test.mjs tests/js/ui/*.test.mjs tests/js/ui/index.js tests/js/reference/*.test.mjs
node scripts/check-renderer-graph.mjs .run/package/desktop-metafile.json
~/.hermes/hermes-agent/venv/bin/python scripts/check-shelf.py
~/.hermes/hermes-agent/venv/bin/python scripts/check-catalog-draft.py
PYTHONPYCACHEPREFIX="$PWD/.run/c-tools-pycache" ~/.hermes/hermes-agent/venv/bin/python -m py_compile src/living-spaces/__init__.py src/living-spaces/living_spaces_core/projects.py tests/python/test_c_tools.py
node tests/js/sandbox/check.mjs
```

All auxiliary commands exited **0**. Graph gate excludes guest code and HTML.
Shelf integrity passes **12 files, 1,224,136 bytes**. Catalog metadata matches
**13 tools**. Compilation passes. The syntax/whitespace gate passes **19 JS
files and 25 lane files**. No harness was written or modified, so no harness
compilation or runtime pass is claimed. Node receipts are `.run/c-tools-node.log`,
`.run/c-tools-node-final.log`, `.run/c-tools-node-retry.log` and
`.run/c-tools-node-serial.log`.

Package validation called the installed validator directly, avoiding the CLI's
dependency-bootstrap path. It used the existing interpreter with no installation.

```sh
mkdir -p .run/c-tools-validation
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$HOME/.hermes/hermes-agent" HERMES_HOME="$PWD/.run/c-tools-validation/home" LIVING_SPACES_DB="$PWD/.run/c-tools-validation/spaces.db" TMPDIR="$PWD/.run/c-tools-validation" ~/.hermes/hermes-agent/venv/bin/python - <<'PY'
from pathlib import Path
from hermes_cli.plugin_validate import validate_plugin_dir
report = validate_plugin_dir(Path('src/living-spaces').resolve())
for name, ok, detail in report.checks:
    print(('PASS' if ok else 'FAIL') + ' ' + name + ': ' + detail)
for warning in report.warnings:
    print('WARN ' + warning)
print(f'{len(report.checks)} checks, {len(report.failures)} failures, {len(report.warnings)} warnings')
raise SystemExit(report.exit_code)
PY
```

Exit **0**, **16 checks passed, 0 failures, 2 warnings**. The warnings name the
private `cron.jobs` import at `living_spaces_core/schedules.py:18` and raw bridge
`window.hermesDesktop` at `desktop/plugin.js:1105`. Both files are unchanged and
outside this lane. Receipt is `.run/c-tools-validator.log`. Validation preceded
the final two-line strict-padding fix; that fix passed the full Python rerun.

## Git and handoff

```sh
git diff --check
git add src/living-spaces/__init__.py src/living-spaces/living_spaces_core/projects.py tests/python/test_c_tools.py
git diff --cached --check
git add src/living-spaces/__init__.py src/living-spaces/living_spaces_core/projects.py tests/python/test_c_tools.py LANE_REPORT.md
git commit -m 'Support binary assets, validated themes and selected shelf libraries'
```

Whitespace checks exited **0**. Both staging attempts and the commit attempt
failed with exit **128**:

```text
fatal: Unable to create '<shared-repo>/.git/worktrees/c-tools/index.lock': Operation not permitted
```

Changes remain unstaged. The cached whitespace check was empty. No alternate
index or Git-object workaround was used. Approval escalation is unavailable.
Forge must stage and commit the four files above from an authorized shell.

## What is not done and proven issues

1. No real-Desktop asset rendering, playback, font rendering, theme application,
   module execution or normal-chat model turn was run. Guest behavior belongs to
   c-guest; Forge must qualify the integrated result serially in the shared app.
   No app-driving harness was written, so there is no new harness command to run.
2. Parallel JS verification still fails the fixed-delay host test described above.
   Forge should rerun the exact parallel command and assign a deterministic
   completion signal to its owning lane if it remains intermittent. Serial green
   is reported separately and does not erase either failed receipt.
3. The two package-validator warnings remain open for Forge. No unrelated fix was
   attempted in schedules or the shipped renderer.
4. No MIME override persistence was added. Correct extensions are required for
   existing path-based bundle MIME inference.
5. No commits or pushes were created because Git staging is denied. No generated
   artifact is included in the changed-file set.

## Contract issues and spec gaps

- No disagreement with the frozen lane decisions. `CONTRACTS.md` still lists htm
  as pending, omits the four approved shelf groups and theme rules, and lacks the
  new optional `libraries` keyword on core and tool writes. It also omits result
  `notes`. Forge should amend sections 0, 3, 4 and 9 at integration. It was not
  edited here.
- Decision 1 gives `mime?` no storage or override semantics. This implementation
  follows its bytes-at-boundary rule and retains existing MIME inference. If
  MIME overrides are intended, Forge should define their revision storage and
  read/bundle contract before commissioning that extension.
- Spec R1-01/R1-04 include assets and bundled libraries, but no dedicated theme
  acceptance case. Forge should add an integrated guest check for preset-only,
  tokens-only, combined themes, CSS override order, and binary assets/fonts
  created through these tools. Unit results alone do not establish that outcome.
