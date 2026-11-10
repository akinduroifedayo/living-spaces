# Sandbox-compatible form references

The goal is useful multi-view Spaces whose add/save actions work in the accepted
allow-scripts-only frame. This slice changes generation references and guidance.

Data and event shapes remain as follows.

- Paper creation uses `put('papers', null, {title, status:'queued', priority:'normal', notes:''}, {baseRev:0})`.
- Paper editing sends `{status, priority, notes}` against the retained record's revision.
- Habit creation uses `put('habits', null, {name}, {baseRev:0})`.
- Check-ins retain `{id, data:{habit,day,done}, baseRev}`. The intended boolean survives conflicts and explicit retries.
- Single-line keyboard events inspect `key`, `isComposing`, `keyCode`, `repeat`, and all four modifier flags. Only plain, non-composing Enter activates the shared add action. Textarea Enter remains ordinary multiline input.
- Kit confirmation remains `await save.run(callback)`, returning the confirmed record or `undefined`. Bridge requests remain `{v:1,id,op,args}`; `data.put` carries `collection,id,data,base_rev`. No API changed.

Exact base is `4828ce753b144abe3edb3dcdc3b355db2df459cf`.
Workspace is `/Volumes/Expansion/Development/Projects/living-spaces-wt/forms`.
Initial `pwd`, exact HEAD, and clean tracked state were established before edits.
The required native preflight ran directly without a trailing command and exited
0. Its JSON output was separately parsed and asserted `status == 'verified'`.
It is a pre-write observation, not a sandbox. `pins.json` was read first, followed
by every complete body in all forty-three required shards.

**PASS within this implementation slice.** Offline checks pass. The authored
Chrome replay is unexecuted and parent-owned. This is no Desktop, model-chat,
independent review, release qualification, or R1 acceptance claim.

## Changes

All paths below are relative to the workspace.

- `src/living-spaces/skills/build-space/SKILL.md` explains native-submit suppression and gives a compatible JavaScript idiom with validation, confirmation, Enter handling, and a synchronous pending lock.
- `src/living-spaces/skills/build-space/references/research-desk/views/library.js` replaces native submission with a labeled group and explicit Add button.
- `src/living-spaces/skills/build-space/references/research-desk/views/editor.js` uses an explicit Save button and section. Existing draft/conflict choices remain.
- `src/living-spaces/skills/build-space/references/habit-planner.md` migrates creation and locks creation/check-in writes against immediate duplicate activation.
- `tests/js/reference/compatibility.test.mjs` retains every original identity and assertion and adds six cases for click, Enter, validation, pending locks, modifiers, IME flags, and multiline input.
- `tests/python/test_agent_reference.py` retains both test identities and all assertions. Its fake hooks expose `useRef`; temporary directories now stay under `.run/forms`.
- `tests/js/reference/env.mjs` resolves the unchanged vendored Preact modules without the sandbox test environment's unrelated temporary home.
- `tests/js/reference/smoke.mjs` adds an opt-in confirmation hold/release for deterministic pending-state replay.
- `tests/js/reference/forms-replay.mjs` performs CDP mouse, key, and text activation against the actual sandbox/examples. It captures trusted DOM events and bridge requests and checks saves without native submit. Its backend is explicitly synthetic.
- `tests/js/reference/FORMS_REPLAY.md` documents the parent's driver bindings and execution boundary.
- `FORM_REPORT.md` records this handoff.

Exact test migration changes only the existing shared `submit(tree)` helper from
captured `form.props.onSubmit(...)` to the corresponding Add/Save button's
`props.onClick()`. The original thirteen JavaScript test bodies are byte-identical
to the base, including payload, confirmation, failure, draft, conflict, and retry
assertions. No wrapper or kit compatibility API was added.

## Executed verification

Receipts and complete logs are under `.run/forms`. `run.py` captures each child
process's actual return code and propagates it. No pipeline determines success.

- `baseline-reference` ran Node compatibility tests before edits. Exit 0, 13 passed.
- `regression-red` ran the original tests plus six added cases before changing examples. Exit 1, 13 passed and six assertion failures at native-submit markup. No setup errors or skips. This is offline source evidence, separate from the supplied Desktop reproduction.
- `reference-green` was an unsuccessful intermediate run despite its filename. Exit 1, 16 passed and three failed. Two tests mistakenly accessed Preact refs through `props` instead of vnode `ref`. The third expected Saved while a retained new-habit draft correctly displayed Draft not saved. These new-test instrumentation errors were corrected; original tests stayed unchanged.
- `reference-final` ran `node --no-warnings --experimental-vm-modules --import ./tests/js/reference/env.mjs --test tests/js/reference/compatibility.test.mjs`. Exit 0, 19 passed, zero failures/skips.
- `python-reference` ran `/Users/ifedayoakinduro/.hermes/hermes-agent/venv/bin/python -m unittest tests.python.test_agent_reference -v`. Exit 0, both tests passed, including the 19-case suite and all four fake-hook draft-retention cases.
- `syntax-check` exited 1 because the checker incorrectly wrapped the habit module's imports inside a function. `syntax-final` corrected that instrumentation and exited 0 with 15 JavaScript syntax checks and ten valid skill links.
- A separate initial manifest parser incorrectly expected the preflight output's `status` field in `baseline.json`. Its KeyError was masked by later read commands in that batch. The direct preflight exits and separately parsed `preflight.json` establish the required result; the masked batch is not verification evidence.
- `scope-audit` exited 0. All 114 frozen baseline files match SHA-256, changed/new source paths stay in scope, and original thirteen test bodies are byte-identical. Details are in `frozen-audit.json`.

## Boundary and handoff

Sandbox permissions, CSP, kit, shared contracts, core, upkeep, UI, adapters,
manifest, and every other test remain unchanged. No excluded worktree, process,
app/home/log, credential, source profile, or live service was read or modified.
No runtime, server, browser, cron, installation, network, or push action ran.

The parent retains real Chrome replay, real isolated Desktop/model-chat checks,
and the repository's broad final gates. Fake-hook and synthetic-backend results
do not establish those outcomes. Local commit disposition and final whitespace
check are recorded below.

`git diff --check` exited 0 (`whitespace.json`). Staging with
`git add src/living-spaces/skills/build-space tests/js/reference tests/python/test_agent_reference.py FORM_REPORT.md`
exited 128 because creating `.git/worktrees/forms/index.lock` was denied with
Operation not permitted. No elevated or alternate-index retry was attempted.
No commit was created. Files remain for the parent to stage and integrate.

The first `final-audit` attempt exited 1 because it treated Git's new-file
`--no-index` difference exit as a whitespace error, despite empty diagnostics.
The corrected final audit checks new-file whitespace directly and retains that
instrumentation failure separately. It also rechecks every frozen hash and
allowed path after writing this report.

## Parent execution after handoff

The parent verified route/cwd/high effort from the exact Codex session and found all 43 complete required bodies in the transcript. It independently checked frozen baseline bytes and the entire original JavaScript test prefix, allowing only the declared submit-helper swap. Parent execution of both Python reference tests passes after explicitly selecting TAP output in the nested Node command. Assertions remain unchanged.

The parent authored `tests/js/reference/forms-cdp.mjs` by adapting the already exercised sandbox CDP driver. The first Chrome runs reached the controls but stalled after modifier-key scenarios. Geometry diagnostics rejected the initial coordinate hypothesis. Resetting key-up modifiers alone did not fix it. Removing the Windows-shaped native virtual key code from the macOS CDP events did. This changes the driver, not the app. Failed receipts and a screenshot remain under `.run/forms/chrome-*`.

The final parent Chrome run, `chrome-1794350357722`, passed 13 Research Desk checks and 11 habit-planner checks on Chrome 157.0.8103.51. It exercised native mouse and keyboard events, pending confirmation, duplicate suppression and multiline notes in the actual sandbox with the explicitly synthetic backend. It is not Desktop or model-chat acceptance. The parent added hit-test and event diagnostics to the replay without removing assertions.
