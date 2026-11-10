# Reference compatibility repair

## PASS within this unit

Living Spaces users need dependable multi-view apps built through normal Hermes chat. This repair aligns the build-space examples and instructions with the integrated runtime kit. Offline reference behavior passes the checks below. This is not release acceptance, independent review, Desktop qualification, or any R1 acceptance.

Exact base is `0d59944c1934ae33b08c476e5ccf34114b1ebd48`. The assigned cwd was verified and the initial tracked tree was clean. `pins.json` was read before the required bodies. All **forty-two** consecutive body shards were read in full. Combined output truncation prompted smaller rereads.

## Actual shapes and repaired behavior

`space.query()` returns `Record[]`; `useCollection()` returns `{records,loading,error,reload}` and retains records during reloads/errors. Records contain user `data`, independent `source`/`source_meta`, and authoritative `rev`.

`useSaveState()` returns `{state,message,current,run}`. `run(callback)` awaits confirmation, returns the callback result on success, and returns `undefined` while recording failure/conflict on error. Both examples now use this method. Creation fields clear only after confirmation. Research Desk notes/status/priority remain drafts until the backend confirms.

`useRoute()` takes no argument and returns `{path,params,component,pattern}`. Research Desk renders `component`, registers root/fallback routes, and passes only supported Nav props. Collection reloads keep the active view mounted so live chat edits do not discard its editor state.

`ConflictBanner` takes `{current,onKeepMine,onUseUpdated,message}`. Research Desk Keep mine rebases the preserved draft to `current.rev`; Save changes is a separate explicit retry. Use updated adopts authoritative fields. Habit check-ins retain `{id,data,baseRev}` including their intended boolean. Their Keep mine explicitly retries against `current.rev`, including across subsequent failures. No conflict auto-retry occurs.

`EmptyState` takes `{title,children,action}`, so explanatory text now renders through children. RefreshButton remains the actual kit component. Freshness keeps attempt status/time, successful completion, and source-as-of separate. Limited run history does not imply there was never a success.

No compatibility wrapper or kit change was introduced. No kit API gap prevents these examples from fitting. Frame freshness remains bounded to recent runs because the frame API has no aggregate freshness method; the documentation states this limit.

## Changed files

Under `src/living-spaces/skills/build-space/`:

- `SKILL.md` documents actual shapes, save results, routing, conflict callbacks, and freshness limits.
- `references/habit-planner.md` repairs saves, retained check-in drafts, explicit retries, and empty-state content.
- `references/research-desk/app.js` repairs routing and view retention during live reloads.
- `references/research-desk/views/editor.js` repairs confirmation and conflict handling.
- `references/research-desk/views/library.js` repairs creation and empty-state content.
- `references/research-desk/views/overview.js` and `views/queue.js` repair empty-state content.

Other owned files:

- `tests/python/test_agent_reference.py` adds the actual-kit suite to unittest.
- `tests/js/reference/compatibility.test.mjs` adds 13 offline cases.
- `tests/js/reference/bundle.mjs`, `smoke-server.mjs`, `smoke.html`, and `smoke.mjs` provide the parent-driven Chrome fixture.
- `REFERENCE_REPORT.md` records this unit.

The original reference test method, all its assertions, and its four-case PROBE are byte-identical. There are now two Python reference methods. Actual-kit tests use vendored Preact hooks and null-rendering capture components, without substituting hook implementations. Bridge/backend results are synthetic. These tests inspect VNodes and callbacks, not a browser DOM.

## Executed commands and exits

Commands ran from the assigned cwd. `node --version` returned `v22.22.3`, exit 0. `pwd`, `git rev-parse HEAD`, and initial `git status --short` exited 0.

Preflight commands both exited 0; the second returned actual `status: verified` without a trailing command:

```sh
/Users/ifedayoakinduro/.hermes/hermes-agent/venv/bin/python /Users/ifedayoakinduro/.hermes/skills/pstack/hermes-local/native-preflight.py --help
/Users/ifedayoakinduro/.hermes/hermes-agent/venv/bin/python /Users/ifedayoakinduro/.hermes/skills/pstack/hermes-local/native-preflight.py --workspace /Volumes/Expansion/Development/Projects/living-spaces-wt/reference --parent /Volumes/Expansion/Development/Projects/living-spaces --manifest /Volumes/Expansion/Development/Projects/living-spaces-wt/reference/.run/reference/baseline.json
```

Reference command:

```sh
node --no-warnings --experimental-vm-modules --import ./tests/js/sandbox/env.mjs --test tests/js/reference/compatibility.test.mjs
```

It first executed seven cases against the unrepaired examples, exit 1 with seven failures. After repair it passed seven, then twelve cases, exit 0. A focused invocation adding `--test-name-pattern='habit retry retains'` exited 1 at the revision assertion before the final retry correction. The final full invocation exited 0 with **13 passed, zero skipped**. An initial invocation omitting `--import ./tests/js/sandbox/env.mjs` exited 1 before collection because vendored hooks could not resolve bare `preact`; this was harness setup failure, not behavioral evidence.

Final gates:

```sh
PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.run/reference/tmp" /Users/ifedayoakinduro/.hermes/hermes-agent/venv/bin/python -m unittest discover -s tests/python -t .
node --test tests/js/sandbox/
node --test tests/js/ui/
node --check tests/js/reference/smoke.mjs
node --check tests/js/reference/smoke-server.mjs
PYTHONDONTWRITEBYTECODE=1 python3 .run/reference/audit.py
git diff --check
```

All exited 0. Unittest ran 144 tests with one existing skip; sandbox passed 48 and UI passed 28 without skips. Logs are `.run/reference/{unittest,sandbox,ui,compatibility}.log`. The Python gate was repeated after the final habit correction. The reference suite also parses both complete smoke bundles and checks every JS import resolves locally.

The audit compares baseline hashes, ownership, original test bodies/PROBE, public fixtures, ten skill links, and new-file whitespace. `.run/reference/artifact-audit.json` records **112 frozen files checked, zero drift**. Research Desk manifest, entry HTML, styles, runtime kit, loader, contracts, core, Desktop, and existing sandbox tests remain unchanged.

## Parent Chrome replay and missing coverage

Run `node tests/js/reference/smoke-server.mjs`, then open its printed loopback URL in real Chrome. Switch examples with the host links. The fixture loads actual example bytes, actual runtime kit/vendor files, and actual sandbox mounting code. Its backend is labeled synthetic and in-memory.

For Research Desk, navigate Overview/Library/Queue, select the public fixture, edit notes/status/priority, and observe the delayed Saving state. Simulate chat edit while dirty; confirm the draft survives requery, Save conflicts, Keep mine does not write, and a separate Save sends the authoritative revision. Check Use updated, search-empty guidance, failed save retention, refresh denial, queued status, and success/failure freshness.

For habits, add a habit and check it in. Simulate a chat edit during the delayed save; confirm conflict retains the intended value and Keep mine sends an explicit rebased retry. Inspect `window.reference.calls`, `.rows`, `.events`, and `.logs` in the host. Reload resets this synthetic backend.

The worker did not start this server or Chrome. Parent owns that execution and acceptance, real Desktop, real backend persistence/restart, models, public feeds, and cron. No chart was added.

## Procedural limits and denials

No subagents, independent review, network service, dependency install, gateway, credentials, or cron access was used. Companion skill reads and delegation stages were not performed outside the frozen packet under this bounded commission. GBrain network lookup was omitted under the offline restriction. No required read was denied.

The stock Python suite skipped `test_manual_refresh_from_local_server_has_provenance_and_timestamps` because its loopback bind was denied. This remains missing coverage, not a pass for that case.

`git add src/living-spaces/skills/build-space tests/python/test_agent_reference.py tests/js/reference` exited **128**. Creating `/Volumes/Expansion/Development/Projects/living-spaces/.git/worktrees/reference/index.lock` was denied with `Operation not permitted`. No alternate write mechanism or elevated retry was attempted. No commit or push occurred. Files remain for parent integration.
