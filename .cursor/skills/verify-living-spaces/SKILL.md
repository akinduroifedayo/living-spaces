---
name: verify-living-spaces
description: "Drive Living Spaces in an isolated Hermes Desktop; use to prove user journeys, capture evidence, and diagnose startup."
disable-model-invocation: true
---

# Verify Living Spaces

**Status: exercised draft, NOT an accepted Desktop verification skill.** The current clean-home runs reach a healthy isolated backend and finish native onboarding, but Living Spaces is absent from the Desktop plugin inventory. `proof` deliberately exits nonzero. No mapped Desktop product journey has passed. Do not equate the candidate's successful headless inspection with Desktop coverage.

This skill is for an agent reading the checkout cold. Read [the feature index](features/README.md), then the matching feature recipe. Use `/maintain-verification-skill` when the application or its host changes.

## Product and pin

Primary surface: the **Spaces** tab in Hermes Desktop, including a sandboxed app canvas. Secondary surfaces: normal chat's `living_spaces` tools and Open Space transcript card; guest `space.*` APIs; ordinary Hermes cron upkeep; scoped diagnostics and revision history. HTTP transport is implementation plumbing, not a replacement for a Desktop click.

- Released product baseline: `4aea12db5375b30e90b5e0fa8f7d12ad7e0fdf98` (0.1.1).
- Separate unpublished inspection candidate: exact Git commit `8008dcc`, resolved and recorded in each `product-pin.json`. **Runtime inspection is not shipped in the released baseline.**
- Verification checkout: `/Volumes/Expansion/Development/Build/living-spaces-app-verification`, branch `verify/living-spaces-app`.
- Candidate copy: `/Volumes/Expansion/Development/Build/living-spaces-app-verification-candidate` (detached; never edit product code there).
- Installed host exercised: `/Applications/Hermes.app`, Desktop `v0.23.1+6306`; existing source/runtime `/Users/ifedayoakinduro/.hermes/hermes-agent` and its existing venv. This is a host dependency, not a bundled product build.

The repo documents `harness/app.py prepare`, `start`, `status`, `enable-desktop`, and `stop`; `harness/cdp.py` provides CDP primitives. Do **not** execute that launcher verbatim here: prepare also enables a model plugin, enable-desktop mutates localStorage, and stop uses gateway stop. This helper instead copies only the product into a fresh home, enables only `living-spaces` in that home's config, uses native onboarding/plugin controls, and kills identity-checked owned PIDs.

## Launch

No builds or dependency installs are authorized or needed. Use existing executables only. No auth is copied; the host may create its own anonymous Welcome state. No chat/model submission is authorized by these instructions. Do not enable the model plugin, sign in, access credentials, modify another profile, or use the everyday Desktop session.

```sh
cd /Volumes/Expansion/Development/Build/living-spaces-app-verification
export C="$PWD/.cursor/skills/verify-living-spaces/scripts/control.py"
export RUN=/Volumes/Expansion/Development/Build/living-spaces-app-verification-evidence/baseline-rerun
"$C" proof --out "$RUN"
```

`proof` is the exact end-to-end rerun command: prepare an empty home; recheck `127.0.0.1:19432` is free; launch the actual Desktop executable in a new process group; native **Skip setup > No thanks > Capabilities > Plugins**; native **Cmd-K > Reload desktop plugins** if necessary; enable Spaces through its native switch if inventoried; require a usable empty Spaces index; Doctor; fixture preparation; native card entry, form submission, persisted note and reopen; evidence; owned-PID teardown in `finally`. Today it fails before the usable index and records that gap. An existing evidence path is refused. Rename neither baseline-04 nor candidate-01 and never reuse their state.

For manual diagnosis of one new instance:

```sh
export RUN=/Volumes/Expansion/Development/Build/living-spaces-app-verification-evidence/manual-rerun
"$C" launch --out "$RUN"
trap '"$C" cleanup --out "$RUN"' EXIT INT TERM
"$C" setup --out "$RUN"
"$C" doctor --out "$RUN"
```

A CDP page or a healthy backend is **not readiness**. Readiness requires native `[data-testid="spaces-index"]` and its usable empty-state/card controls. If setup fails, preserve the failure, run `diagnostic`, and clean up. Do not inject a plugin registration, route, grant, mount, or test-only endpoint to make it pass. The loopback port is dedicated to this run; do not touch the unrelated Google listener at 9222. Reconfirm coordination before concurrent host tests.

Candidate comparison, after the baseline attempt:

```sh
"$C" proof --out /Volumes/Expansion/Development/Build/living-spaces-app-verification-evidence/candidate-rerun --repo /Volumes/Expansion/Development/Build/living-spaces-app-verification-candidate
```

This uses the same Desktop path and, separately, exercises the candidate's registered `spaces_inspect` handler against the disposable fixture. The comparison does not install or publish the candidate.

## Doctor

```sh
"$C" doctor --out "$RUN"
```

Doctor is read-only: it reads the launch manifest, checks PID start identity/process group, requires the CDP listener to belong to that PID on loopback, checks isolated plugin enablement, and reads the renderer DOM for the usable Spaces index. It neither opens a Space (which writes last-opened metadata), calls root reconciliation, starts a backend, authenticates, nor changes config. It exits nonzero when the app is not worth driving. Auth is deliberately absent for model journeys; those cannot pass Doctor's UI readiness as an authorization substitute.

For a retained diagnostic rather than Doctor:

```sh
"$C" diagnostic --out "$RUN"
"$C" capture --out "$RUN" --value diagnosis
```

Diagnostic reads native `host.status()`, `plugins.manage` list, exact directory listings, and the visible Desktop switches. It asserts `hermes_home` equals this run's home. `desktopPluginsRoot()` is intentionally not a read-only check: the host implementation reconciles/migrates files when called.

## Drive

`control-living-spaces` is the feature map's name for `scripts/control.py`. It uses CDP solely against its manifest-owned real Electron renderer. Native gestures are kept together on one debugger connection; splitting press/release across connections can cancel them. DOM evaluation is for observations and element bounds, not internal setters.

```sh
"$C" read --out "$RUN"
"$C" click --out "$RUN" --value 'button[data-tour="tab-plugins"]'
"$C" fill --out "$RUN" --selector 'input[aria-label="Search plugins"]' --value living
"$C" key --out "$RUN" --value Escape
"$C" capture --out "$RUN" --value before-action
```

`click` accepts a unique visible CSS target or `text=` followed by exact button/link/menu text. Ambiguity is a failure. Do not guess by coordinates; the helper derives coordinates from the selected element. `fill` sends native select-all and insert-text editing events. `key` supports Enter, Escape, Tab. A successful input dispatch alone is not an asserted outcome.

Once Doctor passes, the mapped persistence recipe is:

```sh
"$C" fixture --out "$RUN"
"$C" click --out "$RUN" --value 'a[href="#/spaces?space=verification-notebook"]'
"$C" capture --out "$RUN" --value before-save
"$C" guest-fill --out "$RUN" --selector 'input[aria-label="Note"]' --value 'W32 persisted note'
"$C" guest-click --out "$RUN" --value 'button[type="submit"]'
"$C" guest-read --out "$RUN"
"$C" capture --out "$RUN" --value after-save
"$C" records --out "$RUN"
```

Require **Note saved**, rendered **W32 persisted note**, the inserted SQLite record, then leave and reopen through the native card and verify the same note. **This segment remains unexercised because Doctor cannot pass in the current host.** Guest helpers are draft code, not verified controls. No success claim is permitted from fixture creation or a raw database read.

`fixture` invokes the real released `spaces_create` handler with the included public HTML fixture. That is explicit preparation, **not** natural-language creation, native chat dispatch, maintaining-session binding, or a Desktop UI action. It creates one revision, no notes, no refresh handler, no upkeep, no pending grant, and no second profile. Missing preconditions stay failures in the map. Do not replace them with tests that prove less.

## Evidence

Each attempt lives under `/Volumes/Expansion/Development/Build/living-spaces-app-verification-evidence/`, outside disposable `state/` and outside every Forge/W31 tree. Relevant retained runs:

- `baseline-01`: failed first setup; the config CLI unexpectedly prepared dependencies. This is a recorded boundary deviation, not a clean no-install pass.
- `baseline-02` and `baseline-03`: native startup/loader investigations; fixture preparation in baseline-03 is not UI proof.
- `baseline-04`, `baseline-05`, and `baseline-rerun`: scripted baseline attempts and diagnostics. Screenshot review showed the early Enter-based reload did not close the palette, so these do not prove completed reload selection.
- `baseline-reload-click`: native reload option clicked, palette closure asserted and visually checked; package still absent from native inventory. Doctor failed.
- `candidate-01`, `candidate-02`, and `candidate-rerun`: Desktop attempts and separately successful headless inspection handler with canonical SQL invariance. Their early reload selection was not confirmed.
- `candidate-reload-click`: an intermediate onboarding click failed; preserved rather than counted as plugin coverage.
- `candidate-final`: focus-before-coordinate capture, native reload option clicked with palette closure asserted, same missing native inventory/Doctor failure; headless inspection passed again.

For every proof retain the feature/entry ID, command and exit status, action log, before/action/result screenshots, AX snapshots, DOM text, relevant backend logs, persisted side-effect second view, and teardown receipt. `capture` saves PNG/AX/text; `records` reads SQLite with `mode=ro` and `query_only`; cleanup saves the plugin's canonical SQL and logs before removing the home. Evidence must still exist after cleanup.

The candidate `inspection-proof.json` reports **loaded**, actual viewport 1024×768, notebook text and one data query, no errors, browser process/temp cleanup, and equal canonical SQL digests before/after. It has **no screenshot** and proves neither Desktop pixels, a form save, chat tool dispatch, nor `/stop`. Inspection uses a passive disposable real Chromium renderer and the production bridge; no external mocks are used.

Do not treat all mapped entries as covered by one entry. Do not claim API/headless proof as native Desktop proof. Side effects require a read-only second view alongside the visible result. Mock only where production already isolates an external boundary, disclose the boundary, and never pass mock/source transport as real network compatibility. Refresh requests that merely queue jobs are not completed upkeep.

## Cleanup

```sh
"$C" cleanup --out "$RUN"
```

Teardown verifies the owned Desktop PID's start identity, terminates its owned process group, and discovers detached native gateways only by the exact fresh `HERMES_HOME` environment plus command/PID/start identity. No process-name kill, global gateway stop, app restart, or other person's session is allowed. Detached gateway ownership matters: the first implementation checked only Electron's process group and initially missed those processes; the corrected cleanup was run against every earlier attempt.

Cleanup preserves evidence, copies scoped logs and SQL, removes only `RUN/state`, then records zero owned processes and whether port 19432 is free. A refused existing output path grants no cleanup authority: launch/proof only clean directories acquired by that invocation. If the Desktop leader has exited, orphan signals require both the original group and the exact disposable user-data path plus PID/start identity. A refusal/failure preserves logs/SQL and writes `cleanup-failed.json`, leaving state for diagnosis. Never claim complete teardown if either check fails. It may report the port occupied by a different owned attempt rather than kill that listener. After the final attempt, require a free port and all evidence present. No live profile, cron, Spaces data, auth, or user-installed app is removed. Local worktrees and evidence remain for review.

## Helpers

All shipped Python scripts are executable and use the already-installed venv; no package admission occurs.

- `scripts/control.py`: all public commands above, plus `inspect --out "$RUN"` for candidate-only secondary proof and `proof` for the owned complete attempt.
- `scripts/fixture.py`: called by `control.py fixture`; direct invocation requires the exact disposable HERMES_HOME. It is not a user action.
- `scripts/inspection_tool.py`: called by `control.py inspect`; compares canonical SQL around the registered candidate handler. It is not native chat/tool-dispatch proof.
- `scripts/test_driver_safety.py`: run `"$C"`'s sibling directly: `.cursor/skills/verify-living-spaces/scripts/test_driver_safety.py`. Three driver-only regression cases cover reused-path refusal, real owned orphan cleanup/log survival, and rejection of a persisted note without visible save success. The classifier case uses mocks and is explicitly **not product/UI evidence**. Red and green receipts live at `review-safety-red.json` and `review-safety-green.json` in the evidence root. Safety fixtures now use the dedicated Hermes scratch path; the first red run inherited the host's system TMPDIR and was automatically removed.
- `fixtures/notebook.html`: tiny in-canvas form using production `space.query` and `space.put`. No hidden writes from the driver.

The canonical skill stays in `.cursor/skills/verify-living-spaces/` as commissioned. `.agents/skills/verify-living-spaces` is a repo-local alias for Hermes discovery; project trust remains a separate host prerequisite and no live trust registry is changed.

## Current acceptance and next owner

**UNMET:** a usable fresh-home Spaces index; read-only Doctor success; at least one mapped native Desktop product feature with visible and persisted side effects. Consequently this is a draft local diff, not a completed verification skill or a release recommendation.

**Observed on both product pins:** backend enabled and inventories Living Spaces with `has_desktop_half=true`; correct root/child directory entries; native onboarding and reload action; no Spaces inventory switch/navigation. The root cause is not established. Do not blame package enablement or the empty explicit-decisions map based on this evidence.

**Mapped only:** authoring/editing/chat-card entry; native record save/reopen; permissions; lifecycle; refresh/upkeep; ownership; all alternative entry paths. The W31-reported double agent Refresh must be driven and native one-shot jobs counted on both pins once the Desktop gap is resolved; it is not reproduced by this workstream. `/stop` remains unverified.

Forge remains the sole integration owner. Changes stay local on this branch; do not merge, push, publish, live-install, restart a gateway/Desktop, repair product/host code, copy credentials, or enable a model to unblock this draft. Return the precise startup evidence to Forge/Bjorn. A working safe host path must be established before changing this status.
