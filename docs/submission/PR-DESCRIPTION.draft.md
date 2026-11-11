# Add living-spaces to the plugin catalog

<!-- Draft. Not opened. Catalog submission, public visibility and the hackathon submission
need separate owner approval (docs/evidence/R1-STATUS.md). Pin the SHA before use. -->

This PR adds one file, `plugin-catalog/living-spaces.yaml`. It pins
`https://github.com/akinduroifedayo/living-spaces` at `PIN_AT_SUBMISSION`, subdirectory
`src/living-spaces`, version `0.1.0`, `requires_hermes: ">=0.23.1"`.

## What it does

Living Spaces lets a user ask for an application in normal Hermes chat and use it in a
Desktop **Spaces** tab. The agent reads the bundled `build-space` skill, writes a
multi-file project with the `spaces_*` tools, and ends its reply with an **Open Space**
card. A Space can have multiple views, local modules, bundled libraries and structured
records.

Chat and the running app read and change the same records. Record writes use revision
checks, so a stale write conflicts instead of overwriting newer data. Code changes create
revisions. Restoring a revision does not rewind saved records.

A Space can declare public RSS or Atom feeds as its refresh source. The user approves
refresh per Space in a host-owned **Permissions** panel. Refresh updates source-owned
fields and keeps user notes and status. The user can also approve a schedule. An approved
schedule is a native no-agent Hermes cron job, with pause controls and run history.

Generated application code runs in nested opaque-origin sandboxed frames. The host supplies
the Space's own records, refresh operations and scoped logs through `window.space`.

## Hermes surfaces used

| Surface | Use |
|---|---|
| Python tools | `register()` calls `ctx.register_tool` for 13 tools in the `living_spaces` toolset: `spaces_list`, `spaces_get`, `spaces_create`, `spaces_read_file`, `spaces_write_files`, `spaces_edit_file`, `spaces_query`, `spaces_write_records`, `spaces_read_logs`, `spaces_revisions`, `spaces_restore`, `spaces_refresh`, `spaces_request_schedule`. |
| Bundled skill | `ctx.register_skill("build-space", ...)` registers `skills/build-space/SKILL.md` and its reference apps. |
| Dashboard plugin API | `dashboard/manifest.json` declares a hidden `/spaces` tab and `plugin_api.py`. The FastAPI router serves Space listing, bundles, bridge sessions, records changes, runs, refresh, grants, schedule, revisions, logs, archive, pin and delete. |
| Desktop plugin SDK | `desktop/plugin.js` imports only `@hermes/plugin-sdk` and `react`. It registers a `/spaces` page in `ROUTES_AREA`, a **Spaces** entry in `SIDEBAR_NAV_AREA`, and the `living-space` directive in `TRANSCRIPT_DIRECTIVE_AREA` for the Open Space card. |
| Native cron | Approving a schedule creates a no-agent job through `cron.jobs`. See [Validator warning](#validator-warning). |

The plugin registers no hooks, no middleware, no startup schedule and no gateway hook. It
declares no `requires_env`.

## Disclosures (rule 13)

- **Network calls.** The Hermes host fetches feeds with `httpx` over HTTPS GET. It fetches
  only from hosts the user has approved in that Space's Refresh grant, and it checks the
  grant on every request. URLs must use `https` and must not contain credentials. Redirects
  are followed only on the same host, for at most five redirects. A redirect to another host
  fails. The timeout is 20 seconds. A response above 3 MB or 200 entries fails. Feeds that
  contain `DOCTYPE` or `ENTITY` declarations are rejected. The third-party host is whichever
  feed the user approves. The Research Desk reference uses `export.arxiv.org`.
- **Files written outside the plugin's own data.** Approving a schedule writes
  `<HERMES_HOME>/scripts/living-spaces-refresh-<space-id>.py` and creates a Hermes cron
  job named `living-spaces:<space-id>`. Denying the schedule or deleting the Space removes
  both.
- **Reads outside the plugin's own data.** The schedule code reads back the cron job it
  created to show pause state and the next run. The plugin reads no other Hermes or user
  files. It derives the owner label from the active profile name.
- **Shell commands.** The plugin runs no shell commands and starts no subprocesses. Hermes's
  cron scheduler runs the generated Python script without an agent turn.
- **Background work.** A refresh runs on a worker thread in the Hermes process and ends when
  the fetch and write complete. An approved schedule runs only while Hermes's cron ticker is
  running. The plugin starts no long-running process of its own.
- **Credentials.** The plugin stores no credentials and needs none. Feed URLs with embedded
  credentials are rejected.
- **Telemetry.** None. The feed fetcher is the plugin's only outbound HTTP client.
- **Data location.** `<HERMES_HOME>/plugin-data/living-spaces/spaces.db` (SQLite, WAL).
- **Network limit of generated apps.** See [Known limits](#known-limits).

## Validator warning

`hermes plugins validate` passes and reports a warning: `living_spaces_core/schedules.py`
imports `cron.jobs`, which is not on the public plugin API list. The plugin calls
`create_job`, `get_job`, `pause_job`, `resume_job` and `remove_job`. It does not patch,
wrap or rebind anything in that module.

The reason is that Hermes has no public plugin API for this kind of job. The public
`ctx.register_automation_blueprint` adds a prompt template that a user schedules as an
agent job. It has no no-agent script option, and it returns no handle to pause or remove the
job. Living Spaces needs a no-agent job created when the user approves a Space's schedule,
and paused or removed when that Space is paused, archived or deleted. If maintainers prefer
a public seam for this, we will open an issue describing it.

<!-- TODO(verify): rerun the validator at the pinned SHA, paste the exact warning line, and
confirm no other warnings. R1-STATUS records this warning on the packaging candidate only. -->

## Known limits

The host-owned Permissions panel displays this note under the heading "Before you approve
anything":

> Spaces block ordinary internet connections unless you approve a site or capability. This is not a complete block: a browser feature called WebRTC can still send data that this Space can read. It does not give the Space access to Hermes, credentials, your unapproved files or other Spaces. Only put data in a Space that you trust it to handle.

- Schedules need Hermes running. The catch-up policy is:
  "Runs one current refresh when Hermes wakes. Missed intervals aren't replayed."
- Release 1 has no approved-site embeds, device access, arbitrary tool invocation, file
  access or cross-Space access.
- Release 1 acceptance is not complete. `docs/evidence/R1-STATUS.md` in the plugin
  repository lists which checks are observed, partial and pending.

## Screenshots

SCREENSHOT: chat-request-open-space-card

SCREENSHOT: research-desk-library

SCREENSHOT: research-desk-queue-with-note

SCREENSHOT: permissions-panel-webrtc-note

SCREENSHOT: refresh-run-result

SCREENSHOT: schedule-approved-pause-control

SCREENSHOT: history-runs

SCREENSHOT: pair-play-memory-game

🤖 Generated with [Claude Code](https://claude.com/claude-code)
