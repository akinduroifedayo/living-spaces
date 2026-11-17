# Working on Living Spaces

Living Spaces is a Hermes plugin for persistent apps in Hermes Desktop. The installable package is `src/living-spaces`, not the repository root.

## Read the relevant contracts

- Product scope lives in [the spec](docs/spec/SPEC.md) and [its amendments](docs/spec/AMENDMENTS.md).
- Read [the public contracts](docs/contracts/CONTRACTS.md) before changing tool, REST, bridge, revision, or upkeep behavior.
- Read [sandbox admission](docs/architecture/SANDBOX-ADMISSION.md) for packaging changes and [maintenance coordination](docs/architecture/F3-MAINTENANCE-COORDINATION.md) for refresh and scheduling changes.
- Use [the design direction](docs/design/DIRECTION.md) for host UI work. Historical reports describe their tested revision, not the current checkout. A proposal does not authorize implementation.

## Edit source, regenerate the package

- `src/desktop/` contains the desktop plugin source and host UI.
- `src/guest/` contains the guest loader and document generator.
- `src/inspection/runner.mjs` contains the browser inspection runner source.
- `src/living-spaces/living_spaces_core/` contains the Python core. `src/living-spaces/__init__.py`, `src/living-spaces/desktop_rpc.py`, and `src/living-spaces/dashboard/plugin_api.py` adapt it to Hermes.
- `src/living-spaces/runtime/` and `src/living-spaces/skills/build-space/` contain the shipped app kit, vendor shelf, and agent guidance.

Do not hand-edit the generated `src/living-spaces/desktop/plugin.js`, `src/living-spaces/guest/space-host.html`, or `src/living-spaces/inspection/runner.js`. Rebuild them from source. Do not edit vendored libraries to fix host behavior.

Run commands below from the repository root. Use an existing prepared development environment with Node supporting `node:module`'s `registerHooks`, esbuild on `PATH`, and a Python interpreter with Hermes and its test dependencies importable, including FastAPI and HTTPX. This repository has no root `package.json` or dependency bootstrap. Missing dependencies are setup failures, not product failures. Do not install into an everyday Hermes profile to satisfy a test.

```sh
mkdir -p .run/package
esbuild src/desktop/plugin.src.js --bundle --format=esm --jsx=automatic \
	--external:@hermes/plugin-sdk --external:react --external:react/jsx-runtime \
	--outfile=src/living-spaces/desktop/plugin.js \
	--metafile=.run/package/desktop-metafile.json
node scripts/build-sandbox.mjs
esbuild src/inspection/runner.mjs --bundle --format=iife \
	--outfile=src/living-spaces/inspection/runner.js
node scripts/check-renderer-graph.mjs .run/package/desktop-metafile.json
```

The metafile location matters. Stock tests read `.run/package/desktop-metafile.json`. The renderer graph must exclude guest code and guest HTML. An unchanged source tree must rebuild without a tracked diff. For an intentional change, include regenerated output, then repeat the build and confirm that the output is identical.

## Preserve the boundaries

- Model lifecycle states and ownership explicitly. Keep validation at external boundaries and business logic in the core rather than duplicating it across adapters.
- Preserve revision conflict detection, atomic record writes, migration safety, and retry idempotence. A source revision restore must not silently rewind user records.
- Keep guest execution separate from the host. Route network access through the permissioned host path; do not open the guest network policy to bypass a refusal.
- Keep native cron execution distinct from feed refresh. A dispatch acknowledgement is not a completed run.
- Prefer a focused fix over another compatibility layer. When replacing an internal API, migrate its callers and remove the old path.

## Verify the changed behavior

Reproduce a bug before repairing it. Test observable behavior rather than private implementation details. Do not weaken an assertion to make a change pass; explain and review an intentional contract change.

Build first, then run the stock checks and affected focused tests. The JavaScript index tests do not include every supplemental test.

Before Python discovery, export `F3_PROCESS_TEST_TMPDIR` as an owned scratch directory that resolves under `/Volumes/Expansion`. Export `F3_LEGACY_SOURCE` as the path to a clean checkout of `4aea12db5375b30e90b5e0fa8f7d12ad7e0fdf98`, the 0.1.1 baseline, also under `/Volumes/Expansion`, with no untracked files. See `tests/python/test_f3_legacy_upgrade.py` and `tests/python/test_f3_legacy_routes.py`. These are current test constraints, not general runtime requirements. Do not substitute the current tree for the legacy fixture.

```sh
: "${F3_PROCESS_TEST_TMPDIR:?Set an owned scratch directory under /Volumes/Expansion}"
: "${F3_LEGACY_SOURCE:?Set a clean checkout of the required 0.1.1 baseline}"
python3 -m unittest discover -s tests/python -t . -v
node --test tests/js/sandbox/index.js tests/js/ui/index.js
node --experimental-vm-modules --import ./tests/js/sandbox/env.mjs --test \
	tests/js/reference/compatibility.test.mjs \
	tests/js/sandbox/*.test.mjs tests/js/ui/*.test.mjs
python3 scripts/check-shelf.py
```

For host UI work, also run `node tests/js/ui/render-smoke.mjs`. It expects the Hermes Desktop React dependencies under the current home directory's `.hermes/hermes-agent/apps/desktop/node_modules`. Its `SKIP` result is not a pass. It renders with a stub SDK and does not prove real Desktop behavior.

Unit tests, headless browser tests, packaged-plugin checks, and native Desktop journeys prove different things. Exercise the affected real journey when claiming native behavior. Keep synthetic data labeled. Never infer visual correctness from logs alone.

## Work safely and finish clearly

- Confirm the checkout and base before editing. Preserve pre-existing dirty files. Give concurrent writers separate worktrees and serialize integration and generated-file rebuilds.
- Use disposable test homes and databases. Do not run live harnesses against an everyday profile. Installation, restarts, credentials, live data changes, and publication require the authority granted for the task; this file grants none.
- Keep secrets, profile state, and temporary evidence out of commits. Use ignored `.run/` for local build and test output.
- Obtain independent review for consequential changes. Judge findings on their merits. When repeated repairs fail the same condition, test the shared premise before another repair.
- Report the exact tested commit or working-tree state, commands, results, and remaining gaps. Reuse evidence only when it matches the accepted inputs. A local commit, a pushed branch, a merged change, and an installed release are separate states.
