---
name: verify-living-spaces
description: "Drive Living Spaces in an isolated Hermes Desktop; use to prove user journeys, capture evidence, and reproduce native Refresh races."
disable-model-invocation: true
---

# Verify Living Spaces

**Status: usable scoped Desktop driver, re-exercised on main `92486e1` (post-Gallery). Product acceptance is not complete.** The isolated Desktop decision enables the native Spaces page. Native note save and reopen pass with visible and SQLite evidence. On main, the Gallery landing, floating island, Details sheet, notice dock, unbound bot notice, Copy details and storage notice also pass natively. Copy details redaction is checked from source only. The Desktop plus chat Refresh race created two native one-shots and two model-backed cron sessions on both older pins; it needs a model route, which the current launch no longer has. Do not treat this skill as a release approval.

Read [the feature index](features/README.md) before driving. Use `/maintain-verification-skill` when the host or product changes.

## Product and pin

- Current target: any clean checkout. `product-pin.json` records `checkout_head`, the `src/living-spaces` tree, and file digests. Last maintained against `origin/main` `92486e1` (product tree `7eb1844`), driven from a worktree whose `src/` equals that commit.
- Historical labels: released baseline `4aea12db5375b30e90b5e0fa8f7d12ad7e0fdf98` (0.1.1) and unpublished candidate `8008dcc6f77c3f5cb51f966ab1241bd9f89dc37a` keep their names when their exact tree is checked out. Runtime inspection exists only on that candidate.
- Baseline verification worktree `/Volumes/Expansion/Development/Build/living-spaces-app-verification`, branch `verify/living-spaces-app`.
- Candidate worktree `/Volumes/Expansion/Development/Build/living-spaces-app-verification-candidate`. Never edit product code there.
- Existing host `/Applications/Hermes.app`, observed Desktop `v0.23.3+1019` (earlier runs: `v0.23.1+6306`). The runtime and interpreter are existing dependencies, not a build produced by this skill.

Do not run the released `harness/app.py` whole. Its prepare step configures a model plugin and its stop step invokes gateway stop. Reuse only protocol details. The helper owns its PID group, detached gateway, OS home, Hermes home, userData, cwd, and temporary directory.

## Launch

No installs, auth copying, sign-in, live profile changes, gateway restart, publication, or product repairs are permitted. Use only the existing host and interpreter. Do not select a paid provider to make a journey work.

The disposable config is `plugins.enabled: [living-spaces]`, `nous.guest: false` and `security.allow_lazy_installs: false`, with `HERMES_SHARED_AUTH_DIR` inside the disposable home. `nous.guest: false` is the host's own switch that stops a fresh home claiming the Desktop welcome trial or minting a free-tier account (the same config as `tools/verify-desktop/drive.py`). Onboarding is completed with **I'll choose a provider later** (older hosts: **Skip setup** / **No thanks**). The consequence is that no model route exists: chat, agent Refresh and native inspection are `verified-unreachable` in a fresh run. Earlier native inspection and race receipts used the welcome-trial `nous/welcome` route before this change.

```sh
cd /Volumes/Expansion/Development/Build/living-spaces-app-verification
export C="$PWD/.cursor/skills/verify-living-spaces/scripts/control.py"
export RUN="/Volumes/Expansion/Development/Build/living-spaces-app-verification-evidence/baseline-$(date +%Y%m%d-%H%M%S)"
"$C" proof --enable-isolated-desktop --out "$RUN"
```

The proof prepares fresh directories, disables lazy installs, rechecks loopback CDP 19432 immediately before launch, then proves actual storage isolation before its one Desktop decision write. It completes native onboarding, selects Reload desktop plugins, clicks native Spaces navigation, requires a usable index, prepares a fixture, saves a note through its visible controls, verifies SQLite, leaves and reopens, and cleans up in `finally`.

`--enable-isolated-desktop` is opt-in and valid only for `proof`. Without it, the clean-home loader can lack Spaces. Existing output directories are refused and never erased for a rerun. Do not touch the unrelated listener on 9222.

Candidate comparison uses a separate fresh output path:

```sh
"$C" proof --enable-isolated-desktop --repo /Volumes/Expansion/Development/Build/living-spaces-app-verification-candidate --out "/Volumes/Expansion/Development/Build/living-spaces-app-verification-evidence/candidate-$(date +%Y%m%d-%H%M%S)"
```

A candidate proof also runs the separately labeled headless handler check after the native feature passes. That secondary result never replaces Desktop proof.

For an owned live instance used by the broader recipes:

```sh
"$C" launch --out "$RUN"
trap '"$C" cleanup --out "$RUN"' EXIT INT TERM
"$(dirname "$C")/flag_enable.py" --out "$RUN"
"$C" setup --out "$RUN"
"$C" doctor --out "$RUN"
"$C" fixture --out "$RUN"
```

Choose `--repo` on `launch` for the candidate. Do not use an already completed proof's output directory for this sequence.

## Isolated Desktop decision

The release's `harness/app.py:123-128` evaluates a write through CDP in the page selected by `/dist/index.html`. It preserves the JSON object under `hermes.desktop.pluginDecisions.v2` and sets only `living-spaces` to `true`, then reloads the page. It does not hard-code an origin.

The observed renderer is `file:///Applications/Hermes.app/Contents/Resources/app.asar.unpacked/dist/index.html`, origin `file://`. `flag_enable.py` writes the same one-field decision through `Runtime.evaluate`, reads it back, reloads through CDP, and reads it again.

**Fail closed before the write.** The guard binds the CDP listener to the manifest PID and start identity, verifies renderer command lines use exactly `RUN/state/ud`, and requires that PID's open `Local Storage/leveldb/LOCK` under that directory. It rejects foreign Local Storage and paths under the real Application Support or Hermes home. Environment variables alone are not proof. Receipts are `flag-isolation.json`, `flag-write.json`, and `flag-after-reload.json`.

A native inventory switch is not required when Spaces navigation is already present. Click that navigation and assert the actual index. The old switch-only test produced a false negative after the flag had worked.

## Doctor

```sh
"$C" doctor --out "$RUN"
"$C" diagnostic --out "$RUN"
"$C" capture --out "$RUN" --value diagnosis
```

Doctor is read-only. It verifies PID and port ownership, disposable backend enablement, and the current native Spaces index. It does not navigate, mount a Space, set a permission, authenticate, or establish model access. Run it on the index, not while a detail page is open.

Diagnostic reads scoped host status, package inventory, known directory entries, and visible switches. `desktopPluginsRoot()` is not a read-only diagnostic because the host can reconcile files when called.

## Drive

The feature map calls `scripts/control.py` **control-living-spaces**. CDP gestures drive the actual owned renderer. Read DOM and SQLite for observations, never use internal setters or HTTP calls as substitutes for native actions.

```sh
"$C" read --out "$RUN"
"$C" click --out "$RUN" --value 'a[href="#/spaces?space=verification-notebook"]'
"$C" guest-fill --out "$RUN" --selector 'input[aria-label="Note"]' --value 'W32 persisted note'
"$C" guest-click --out "$RUN" --value 'button#save'
"$C" guest-read --out "$RUN"
"$C" records --out "$RUN"
```

Wait for the fixture's polled native card before clicking. Require **Note saved**, the rendered note, and a matching SQLite record. Return through **Back to Spaces**, `header.ls-framebar button[aria-label="Back to Spaces"]` (`control.BACK`), reopen the native card, and require the same note. A persisted row without visible success fails.

The fixture uses a labeled input and an explicit `type="button"` click handler. Native form submission is forbidden by the shipped sandbox, including `onSubmit`. Do not loosen the sandbox or use `requestSubmit()` to repair a fixture.

`fixture` prepares one code revision through the shipped handler. It is not chat creation or maintaining-session binding. Its warning about the absent maintaining session is real. The visible **Hermes didn't receive the request** notice (unbound) does not invalidate a separately proven note save. The fixture page also has two notice probes, **Ask Hermes** (`space.ask`) and **Fill storage** (one ~234 KB `bulk` record); see [chrome-and-notices](features/chrome-and-notices.md).

Run the broader native recipes in a live prepared instance:

```sh
"$(dirname "$C")/mapped_journeys.py" --out "$RUN"
```

This drives note save and reopen, History, empty Upkeep with no Refresh control, Internet Off and its audit, search and Archived filter, pin and unpin, Desktop double Refresh, and archive, restore, and logical deletion of the disposable Notebook. Results are in `mapped-journeys.json`; inspect every case, not just the command exit. `refresh-double-agent` reports `verified-unreachable` with its prerequisite when no model route exists; with one, it creates a separate agent-upkeep fixture and its row is telemetry, not a passed concurrency test. The fixture deletion is intentional and is not suitable for live data, so run it after `chrome_journeys.py`.

Gallery chrome and notices are driven by:

```sh
"$(dirname "$C")/chrome_journeys.py" --out "$RUN" --clipboard
```

It needs a fresh instance with the fixture and writes `chrome-journeys.json`. `--clipboard` reads Copy details through the macOS pasteboard. It refuses a pasteboard holding anything but plain text, and restores that text afterwards. Supporting manual commands: `hover --value <selector|corner>`, `box --value <selector>` and `focused`.

## Native inspection and interruption

Use the candidate only, and only with an explicitly approved model route (a fresh run has none; see Launch). From the native **Getting started** chat, verify the route is the approved one. Submit a read-only request to inspect Verification Notebook revision 1 with the runtime tool. Require the actual stored `spaces_inspect` tool result, not the model's summary. The completed native candidate trial returned `loaded`, no errors, and renderer and temporary-directory cleanup. It also returned a host notice about the unrecognized CSP `webrtc` directive. Inspection has no screenshot and does not prove visual quality.

```sh
"$C" click --out "$RUN" --value 'text=Getting started'
"$(dirname "$C")/native_inspection.py" inspect-results --out "$RUN"
"$(dirname "$C")/native_inspection.py" stop-trial --out "$RUN"
```

`inspect-results` reads the owned native session database. `stop-trial` submits a second native read-only inspection, waits for **Running spaces inspect**, then types `/stop` and submits it. It records whether the tool was still visibly running immediately before submission, the exact native cancellation result, canonical SQL digests, and owned browser-process observations. A completed inspection before the stop attempt is not interruption proof. The candidate trial demonstrated explicit-stop cancellation and unchanged canonical SQL; its owned renderer disappeared on the following process sample. The PNG taken immediately after stop is intermediate; the later DOM and stored tool result establish completion.

## Desktop plus chat Refresh race

The native Desktop busy button suppresses a second Desktop click. It does not establish protection against a native chat Refresh. Run the exact race in a new disposable home:

```sh
"$(dirname "$C")/race_native.py" --repo /Volumes/Expansion/Development/Build/living-spaces-app-verification-candidate --out "/Volumes/Expansion/Development/Build/living-spaces-app-verification-evidence/candidate-race-$(date +%Y%m%d-%H%M%S)"
```

For the baseline, change `--repo` to this verification worktree and use another output path. The runner launches and cleans up itself. It prepares one agent fixture, primes native chat with the tool schema without firing Refresh, drafts the chat request, presses Desktop Refresh, switches back to native chat, and submits immediately.

`race-result.json` reports exact native one-shot IDs, cron session IDs, actual model API-call counts, timestamps proving overlap, native tool-call arguments, and Space run rows. **Both product pins failed this race:** two one-shots and two model-backed native cron sessions for the same Space. The chat call arrived before the first cron session ended. No product repair is included. The empty Space `runs` table is not evidence that no model work happened.

A runner exit of zero means the experiment completed, not that deduplication passed. The observed bug is `observed_two_with_overlap=true`. Both recorded races left one disabled, paused one-shot before teardown. The owned home and detached gateway were then removed; do not report zero jobs before teardown for these two races.

## Evidence and cleanup

Evidence root `/Volumes/Expansion/Development/Build/living-spaces-app-verification-evidence` is outside disposable `state/` and every Forge or W31 tree.

- `baseline-flag-04` and `candidate-flag-02` contain the successful native proof, note rows, screenshots, and cleanup.
- `baseline-journeys-01` and `candidate-journeys-01` contain the broader mapped native trials.
- `candidate-journeys-01/native-inspect-tool-results.json`, `stop-attempt.json`, and `stop-outcome.json` bind native dispatch, cancellation, unchanged SQL, and browser cleanup.
- `baseline-desktop-chat-race-01` and `candidate-desktop-chat-race-01` contain the actual duplicated native dispatches.
- `main-92486e1-reproof2-20261123-184505` is the final re-proof after review fixes (same results; checkout `4428901` plus those fixes, `src/` identical to `92486e1`). `main-92486e1-reproof-20261123-183445` is the first post-Gallery re-proof on main: `chrome-journeys.json` (7/7 passed), `mapped-journeys.json` (7 passed, `refresh-double-agent` verified-unreachable), `copy-details.txt` and 36 PNGs. Its `product-pin.json` records checkout `79a095c`, whose `src/` is identical to `92486e1` (product tree `7eb1844`). `main-92486e1-20261123-182324` holds the exploratory drives that found the harness gaps, including its failed first attempts.
- Earlier flag trials remain as failed harness attempts. `flag-01` failed the old switch-only check. `baseline-flag-02` did not wait for the polled card. `baseline-flag-03` used a forbidden submit fixture. Do not relabel these green.
- Driver-only unit receipts are `followup-unit-tests-green.json`. Mocked guard and classifier tests are not product proof. The earlier red receipt records a missing `wait_text` mock, not a product failure.

```sh
"$C" cleanup --out "$RUN"
```

Cleanup verifies PID start identity and the owned process group, discovers detached gateways by the exact disposable `HERMES_HOME`, preserves logs and canonical SQL, removes only `RUN/state`, and records remaining processes and the CDP port. Existing-output refusal gives no cleanup authority. Orphan signals require identity and the exact disposable path. A failed cleanup leaves evidence and a failure receipt. After native inspection or cron, independently scan owned path-bearing processes as well. Never claim final containment from Electron's exit alone.

## Helpers and remaining coverage

All scripts use the existing interpreter and are executable. `test_driver_safety.py` covers reused-output refusal, real owned orphan cleanup, and visible-save classification. `test_flag_enable.py` covers the matching-storage control, missing lock, foreign renderer directory, foreign Local Storage, one-field preservation, and the fixture's supported click path. The flag boundary cases use mocks and are driver checks only.

`.agents/skills/verify-living-spaces` is the repo-local alias. No live project-trust setting was changed.

Coverage remains partial. The bot reply banner (Hermes replied, Read reply, Dismiss reply, answer summary), Retry same request, offline/unknown copy, natural-language creation and editing, older-code restore, shared chat data editing, record conflicts and batches, assets and multiple views, feed success and failure, recurring upkeep controls, pending-grant decisions, cross-profile isolation, and maintained-bot binding are not qualified by these trials. Keep those entries explicit in the feature map. A working driver and the reproduced F-refresh bug do not qualify the whole product. Forge owns integration and any repair. No merge, push, live install, restart, auth change, or publication follows from this skill.
