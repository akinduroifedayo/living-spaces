# AGENT lane report

## ISSUES

The goal is a Hermes plugin package and build skill that let normal chat create
and maintain dependable multi-view Spaces. The owned implementation is written.
The focused suite passes 38 tests. Hermes admission validation passes 15 checks.
Real sandbox integration and kit compatibility remain unproven. Git staging and
commits are blocked by this session's filesystem permissions.

Branch is `forge/r1-agent`. No push was attempted. The frozen contracts, shared
loader, core, upkeep, sandbox, Desktop implementation, and live Hermes profile
were not edited. The previous attempt's untracked `__init__.py` was preserved and
completed rather than discarded.

## What was built

All package paths below are relative to `src/living-spaces/`.

- `plugin.yaml` declares version 0.1.0, standalone kind, all 13 tools, no hooks or
  privileged plugin capabilities, and `requires_hermes: ">=0.23.1"`. The installed
  `hermes_cli.__version__` returned 0.23.1. The checkout's pyproject has the
  placeholder version 0.0.0, so the installed version was used.
- `__init__.py` registers the `living_spaces` toolset and `build-space` skill.
  Handlers return JSON envelopes, delegate exact-name/ID resolution, preserve
  core errors, attribute writes to the call-context bot or active profile,
  extract `space.json`, supply default libraries, and return Open Space details.
  Static warnings inspect the complete resulting revision, including unchanged
  importers after a module deletion. No cron hooks or startup jobs are registered.
- `dashboard/manifest.json` labels the tab Spaces and declares its hidden
  `/spaces` route and loose `plugin_api.py` module.
- `dashboard/plugin_api.py` implements every section 8 route. All core work,
  including aggregate reads, runs in the threadpool. Space IDs are validated
  before loading core. Error statuses use the seeded `SpacesError.http_status`.
  Bridge requests preserve session, op, and args and bind identity to the URL.
  Bridge validation and dispatch errors return HTTP 200 with `ok: false`.
  Closing a session checks its Space binding. Host actions return SpaceSummary.
- `skills/build-space/SKILL.md` has 198 lines. It teaches shared records,
  concurrency, migrations, public-feed upkeep, approvals, diagnostics, recovery,
  and directive replies. It tells the model to verify copied kit signatures
  before handing the app to the user.
- `skills/build-space/references/research-desk/` contains `space.json`,
  `index.html`, `app.js`, `styles.css`, and `views/{overview,library,queue,editor}.js`.
  It supplies three views, search/detail, creation, notes/status/priority,
  source provenance, separate freshness facts, save/conflict states, and a public
  Atom feed. Selected editors remain visible when live data changes remove an
  item from the queue filter. Limited history never claims there was no success.
- `skills/build-space/references/habit-planner.md` supplies a complete second
  app with habits and daily check-ins, without public retrieval or upkeep.
- `README.md` explains installation, both enable switches, storage, limits,
  approvals, and the exact spec section 2 WebRTC disclosure.
- `tests/python/test_agent_adapters.py` tests the tool and REST adapters against
  a fake core using the real seeded error class.
- `tests/python/test_agent_reference.py` runs four Node VM cases for retained
  editor identity after completion, filtering, or removal from loaded records.
  These use synthetic hooks and tagged-template output, not a real DOM or kit.

The Model the Domain principle kept handlers and JSON schemas in one tool
registration table. The report and examples follow the requested plain-writing
policy. Independent read-only review identified dependency-deletion warnings,
filtered-editor draft loss, and incomplete-history freshness claims. Those
findings were addressed. There were no phase-narrating comments to remove.

## Verification

Commands ran from the worktree root. Each test creates fresh `HERMES_HOME` and
`LIVING_SPACES_DB` locations under `.run/`. Unit tests use no network. The final
Node run used Homebrew Node 25.9.0. Earlier runs used the shell's Node 22.22.3.
No package installation command was issued.

### Focused tests

The exact requested discovery form was attempted:

```sh
~/.hermes/hermes-agent/venv/bin/python -m unittest discover -s tests/python -t . -p 'test_agent_*.py' -v
```

It aborted before collecting tests, with zero tests run:

```text
ImportError: Start directory is not importable: '<worktree>/tests/python'
```

The seed has no `tests/__init__.py` or `tests/python/__init__.py`. Those paths
are outside the lane's explicit ownership, so no package markers were added.

The final working invocation was:

```sh
PATH="/opt/homebrew/opt/node@25/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 ~/.hermes/hermes-agent/venv/bin/python -m unittest discover -s tests/python -p 'test_agent_*.py' -v
```

Result was **38 tests passed, 0 failed, 0 errors**. Earlier versions of the same
suite passed 35, 37, then 38 tests before the final Node 25 run.

Coverage includes all 13 tools' success envelopes, all ten core error codes for
every tool, ambiguous-reference rejection before mutation, owner attribution,
default and explicitly empty libraries, manifest extraction/edit revisions,
record batch forwarding, complete-revision warnings, every REST route, all ten
REST error statuses, bridge replies and identity forwarding, malformed bridge
requests, session binding, invalid inputs, and event-loop responsiveness.

### Real package import and registrations

This import check used the real seeded core, not the fake core:

```sh
PYTHONDONTWRITEBYTECODE=1 HERMES_HOME="$PWD/.run/agent-checks/hermes-home" LIVING_SPACES_DB="$PWD/.run/agent-checks/spaces.db" ~/.hermes/hermes-agent/venv/bin/python - <<'PY'
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
pkg = Path('src/living-spaces').resolve()
spec = importlib.util.spec_from_file_location('agent_import_check', pkg / '__init__.py', submodule_search_locations=[str(pkg)])
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)
core = mod._core.load_core()
names = []
skills = []
mod.register(SimpleNamespace(register_tool=lambda **kw: names.append(kw['name']), register_skill=lambda *args, **kw: skills.append(args[0])))
print('Real core imported:', core.__name__)
print('Registered tools:', ', '.join(names))
print('Registered skills:', ', '.join(skills))
PY
```

It exited 0 and registered these names:

```text
spaces_list, spaces_get, spaces_create, spaces_read_file, spaces_write_files,
spaces_edit_file, spaces_query, spaces_write_records, spaces_read_logs,
spaces_revisions, spaces_restore, spaces_refresh, spaces_request_schedule
```

The registered skill was `build-space`. This proves import and registration,
not real core operations. The current worktree has only the seeded core.

### Hermes validator

The permitted CLI command was run without `--install-deps`:

```sh
PYTHONDONTWRITEBYTECODE=1 HERMES_HOME="$PWD/.run/agent-checks/hermes-home" LIVING_SPACES_DB="$PWD/.run/agent-checks/spaces.db" ~/.hermes/hermes-agent/venv/bin/python -m hermes_cli.main plugins validate "$PWD/src/living-spaces"
```

It exited 0 and ended with `Validation passed.` Before validating, Hermes's
bootstrap unexpectedly attempted dependency preparation for the temporary data
root. That attempt failed downloading `packaging==26.3` because DNS was unavailable.
The CLI then used existing dependencies. No successful installation was reported.
The validator itself passed all 15 checks. No further bootstrap runs were made.

A direct validator import initially failed with `ModuleNotFoundError: hermes_yaml`.
Adding the read-only Hermes checkout to `PYTHONPATH` resolved that import without
installing anything. The successful direct check was:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=~/.hermes/hermes-agent HERMES_HOME="$PWD/.run/agent-checks/hermes-home" LIVING_SPACES_DB="$PWD/.run/agent-checks/spaces.db" TMPDIR="$PWD/.run/agent-checks" ~/.hermes/hermes-agent/venv/bin/python - <<'PY'
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

Output was:

```text
PASS manifest: plugin.yaml parses
PASS manifest fields: name, version, description present
PASS requires_hermes: spec '>=0.23.1' parses
PASS config schema: not declared
PASS requires_env: all entries UPPER_SNAKE
PASS oauth: not declared
PASS loadable: entry: __init__.py
PASS python dependencies: none declared
PASS capability probe: register() ran in isolation
PASS declared tools: matches registrations
PASS declared hooks: matches registrations
PASS declared middleware: matches registrations
PASS built-in tool collisions: no collisions
PASS security scan: safe
PASS no core override: no runtime rebinds of Hermes core
15 checks, 0 failures, 0 warnings
```

The Desktop artifact is absent in this lane, so this result does not validate
the eventual `desktop/plugin.js` or the integrated package's scan result.

### Skill and example checks

```sh
PYTHONDONTWRITEBYTECODE=1 ~/.hermes/hermes-agent/venv/bin/python ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py src/living-spaces/skills/build-space
```

It exited 0 with `Skill is valid!`.

This command checked all linked skill references, manifest JSON, local imports,
and syntax for five Research Desk modules and the habit planner's JavaScript:

```sh
PATH="/opt/homebrew/opt/node@25/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 ~/.hermes/hermes-agent/venv/bin/python - <<'PY'
from pathlib import Path
import json
import re
import subprocess
base = Path('src/living-spaces/skills/build-space')
links = re.findall(r'\]\((references/[^)]+)\)', (base / 'SKILL.md').read_text())
assert all((base / link).is_file() for link in links)
project = base / 'references/research-desk'
manifest = json.loads((project / 'space.json').read_text())
for path in sorted(project.rglob('*.js')):
    subprocess.run(['node', '--input-type=module', '--check'], input=path.read_text(), text=True, check=True, capture_output=True)
    for target in re.findall(r"from ['\"]([^'\"]+)['\"]", path.read_text()):
        assert (path.parent / target).is_file() if target.startswith('.') else target in manifest['imports'], (path, target)
habit = (base / 'references/habit-planner.md').read_text()
code = re.search(r'```js\n(.*?)\n```', habit, re.S).group(1)
subprocess.run(['node', '--input-type=module', '--check'], input=code, text=True, check=True, capture_output=True)
print(f'PASS: {len(links)} skill links, 6 JavaScript syntax checks, Research Desk imports and manifest JSON')
PY
```

It reported **10 valid links, 6 syntax checks passed, 0 failures**. This check
used no network and did not execute the real sandbox.

`git diff --check` exited 0. Because the files remain untracked, a separate
per-file `git diff --no-index --check /dev/null <file>` check also verified all
17 owned implementation files, with no whitespace errors.

## Contract issues

1. Section 8 requires `seq_global`, but sections 4 and 6 expose no global
   change-cursor function. The adapter derives the maximum cursor by calling
   `changes_since(sid, 0, limit=1)` for each listed Space. This follows only
   public signatures, but is O(number of Spaces), can race deletion, and may
   reset after the last Space holding the highest cursor is deleted. A true
   monotonic global cursor needs a coordinator-owned contract/core decision.
2. Section 7 specifies kit helper names but omits their return shapes and
   component props. The kit source is absent in this worktree. The examples
   currently expect `useCollection` to return `{records,loading,error,reload}`,
   `useSaveState` to return `{state,message,save(callback)}`, `useRoute(router)`
   to return `{path}`, and `hashRouter(routes)` to return the router passed to
   `useRoute` and `Nav`. `Nav` receives `{items:[{path,label}],router}`.
   `SaveIndicator` receives `{state,message}`. `ConflictBanner` receives
   `{error,onReload}`. `EmptyState` receives `{title,message}`. `RefreshButton`
   needs no props. Forge must align these with the sandbox lane before claiming
   the reference runs. No runtime compatibility layer was invented.
3. The requested `-t .` test invocation needs test-package markers that are
   absent and outside this lane's ownership. Focused discovery without `-t .`
   passes. Forge should supply the shared markers if retaining that invocation.

No frozen contract was changed.

## Not done or unproven

- No real model-driven chat turn, real Desktop mount, iframe runtime, import-map
  execution, actual kit behavior, reload/restart persistence, or integrated
  core/upkeep operation was tested. This report passes no R1 acceptance check.
- No real public feed fetch or schedule was run or approved. No cron scheduler,
  gateway, or Desktop app was started, stopped, or restarted.
- The reference's charts are not implemented. `lightweight-charts` is documented
  as an optional library. Full demonstration requirements remain Forge's gate.
- No independent behavioral skill evaluation built a complete app with a model.
  The read-only review and Node component probes are narrower evidence.
- No commits were created. Git staging failed before anything entered the index.

## Commit blocker

This exact staging command was attempted:

```sh
git add src/living-spaces/plugin.yaml src/living-spaces/__init__.py src/living-spaces/dashboard/manifest.json src/living-spaces/dashboard/plugin_api.py src/living-spaces/skills/build-space src/living-spaces/README.md tests/python/test_agent_adapters.py tests/python/test_agent_reference.py
```

It exited 128:

```text
fatal: Unable to create '<shared-repository>/.git/worktrees/agent/index.lock': Operation not permitted
```

The denied path is the real worktree index, not a stale lock. The session's
approval policy is `never`, so no elevated retry is available. Implementation
files and this report remain in the worktree for Forge to stage, commit, and
integrate. No paths outside lane ownership were changed to work around this.
