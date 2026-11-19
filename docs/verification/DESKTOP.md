# Verify Living Spaces in Hermes Desktop

This is the canonical way to prove a Living Spaces change in the real Hermes Desktop. Unit, sandbox and render-smoke tests (see [AGENTS.md](../../AGENTS.md)) do not prove native behavior; this does, for the journeys it covers. The tooling lives in [`tools/verify-desktop/`](../../tools/verify-desktop/) and is development-only: it is outside `src/living-spaces/`, so it is never part of the installed plugin.

## What one run proves

`drive.py` runs the **note save, leave and reopen** journey end to end:

1. Copies this checkout's `src/living-spaces` into a brand-new disposable Hermes home, with its own Desktop user data, OS home and working directory. Nothing is copied from any real profile, and no credentials exist in the run.
2. Launches the installed Hermes Desktop against that state with a loopback-only debugging port.
3. Proves the renderer is using that state (its user-data directory, open Local Storage, and the Hermes home the host reports) **before** writing anything, then records the one Desktop decision that enables Living Spaces and confirms it survives a reload.
4. Completes onboarding without choosing a provider and opens **Spaces**, which must show the empty index.
5. Creates the synthetic *Verification Notebook* (`tools/verify-desktop/fixtures/notebook.html`) through the plugin's own `spaces_create` handler. This is fixture setup, not chat creation.
6. Through real mouse and keyboard input: opens the card, types a note, presses **Save note**, waits for the visible *Note saved* status, goes back to Spaces, reopens the card, and requires the note on screen.
7. Reads the plugin SQLite store read-only after save and after reopen; the note must be persisted both times.
8. Quits the app normally, then sends at most one TERM to the backend gateway this run started, after re-proving its start time, Hermes home and listener. It never signals by name or group and never force-kills. It then checks that nothing still references the state directory, the debugging port is free, and other Hermes gateways are unchanged.

No model is used, so the Space header shows *Bot request: offline* (no maintaining chat is bound). That banner is expected in this journey and is not a failure. The disposable config sets `nous.guest: false`, the host's own switch that stops a fresh home from claiming the Desktop welcome trial or creating a free-tier account. The run also pins the shared Nous credential store inside its own state. It fails if an `auth.json` or `nous_auth.json` appears anywhere in that state (`result.json`: `identity`, `no_identity_minted`). Whether the real shared store changed during the run is recorded too, but other running Hermes gateways rewrite it on token refresh, so that alone is not a failure.

## Prerequisites

The driver installs nothing. Missing prerequisites are setup failures.

- macOS with Hermes Desktop at `/Applications/Hermes.app` (`--app` to change it).
- A Hermes source checkout with a working venv. The default is `~/.hermes/hermes-agent` (`--hermes-root`, or `HERMES_DESKTOP_HERMES_ROOT`). The Desktop starts its backend from that root.
- Run the driver with that venv's Python. It needs `websockets`, which Hermes already provides.
- Loopback port 19432 free (`--cdp-port` to change it).
- The product tree committed. `--allow-dirty` loads uncommitted changes and records that in `prepare.json`.
- No Hermes Desktop window you care about being disturbed: the run opens a second, separately named Desktop instance.

## Run it

```sh
PY=~/.hermes/hermes-agent/venv/bin/python
"$PY" -I tools/verify-desktop/drive.py --out .run/verify-desktop/$(date +%Y%m%d-%H%M%S)
```

`--out` must be new and is never overwritten. The state directory defaults to a fresh temporary directory, and `--state` picks a new one; neither may sit inside `~/.hermes` or `~/Library/Application Support`. The command exits 0 only when the journey passed, cleanup was clean and no identity was minted (`result.json`: `passed`). Keep evidence under the ignored `.run/`; do not commit it.

## Read the result

`result.json` has one `outcome`:

| Outcome | Meaning |
|---|---|
| `journey_passed` | The product journey passed on the loaded commit (`prepare.json` → `repo_head`, `product_dirty`). Check `residue.clean` too. |
| `setup_failure` | The harness, host or environment stopped before the journey: launch, backend, isolation, onboarding, Spaces navigation or fixture. Not a product verdict. |
| `harness_failure` | Setup completed but the driver itself failed during the journey (debugging connection, screenshot or disk error, an ambiguous selector). Not a product verdict. |
| `product_failure` | A product expectation failed: save status, visible note, persistence, navigation back to the index, or the note after reopen. |

Screenshots and page text are saved at each step (`onboarding`, `empty-spaces`, `before-save`, `after-save`, `after-leave`, `after-reopen`, and `failure` when one occurs), along with `actions.jsonl`, `records-*.json`, `isolation.json` and `backend-identity.json`. A survivor process is reported in `shutdown` and `residue` and left running for you to inspect.

Keep three kinds of claims apart. A **setup or harness failure** says nothing about the product. A pass on an **older commit** is history, not proof for the current one. A **current-head** claim needs a run whose `repo_head` is the commit you are claiming, with `product_dirty: false`.

## Coverage and when to re-drive

[`tools/verify-desktop/coverage.json`](../../tools/verify-desktop/coverage.json) maps source paths to journeys. Before claiming native behavior for a change, run:

```sh
python3 tools/verify-desktop/affected.py origin/main
```

Exit 3 means a driven journey is affected: run `drive.py` on the final commit. A change to the driver, the fixture, plugin registration or Desktop loading re-drives everything. Moved files count at both paths. Source changes with no mapped journey are listed; extend `coverage.json` in the same change, or record why no journey applies. When you add a journey, add its entry to `coverage.json` and its steps to this page.

Only one journey is driven today. Building a Space in chat and Refresh/upkeep need a model route, which this tool deliberately does not create; they remain **not driven** and must not be claimed from this run.

## Limits

- Cleanup is a snapshot: a detached process that neither references the state directory nor holds a file open there is not detected.
- The run uses the installed Desktop and Hermes source as they are. Record their versions from `prepare.json` with any claim; a host update can change onboarding text or the backend lifecycle.
- If the Desktop is still running 45 seconds after its normal quit, it is reported and left running.
