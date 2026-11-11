# Living Spaces

Build persistent applications in normal Hermes chat and use them in the Desktop
**Spaces** tab. An app can have multiple views, local modules, bundled libraries,
and structured records. Chat and the app read and change the same records.
Code revisions support repair and restore without rewinding saved data.

Release 1 supports manual refresh and user-approved schedules for public RSS and
Atom feeds. Refresh updates source fields while retaining user notes and status.
Schedules run a host-owned script without an agent turn. They need Hermes running.

## Install and enable

This folder is the plugin package. Use Hermes 0.23.1 or later. A complete package
includes `desktop/plugin.js`, `dashboard/`, `runtime/`, and `living_spaces_core/`.

1. Install this package through Hermes's local-directory plugin installer, or
   place the complete folder at `<HERMES_HOME>/plugins/living-spaces/`.
2. Run `hermes plugins enable living-spaces`. This adds `living-spaces` to
   `plugins.enabled` for Python tools and the build skill. The equivalent config is:

   ```yaml
   plugins:
     enabled:
       - living-spaces
   ```

3. Enable **Living Spaces** in Desktop **Capabilities > Plugins**. This second
   switch enables the Desktop extension. Both switches are required.
4. Start a normal chat with the `living_spaces` toolset available. Ask
   "Build Research Desk with an overview, searchable library, and reading queue."
   The agent reads the bundled `build-space` skill and returns an **Open Space** card.
5. Open the Space. Approve its requested **Refresh** scope in **Permissions**
   before fetching public data. A requested schedule also needs approval there.

Enabling the plugin does not approve a Space's external capabilities. Data and
runtime log grants are visible per Space. Feed host changes request approval
again. Denied or revoked refresh cannot fetch or update source records.

## Permissions

Release 1 has no approved-site embeds, device access, arbitrary tool invocation,
file access, or cross-Space access. Generated applications run inside a sandbox.
The host supplies their own records, refresh operations, and scoped logs through
`window.space`. Public feed retrieval runs on the host over HTTPS, only for
approved declared hosts. Credentials are not required and must not enter projects.
The Permissions panel shows the WebRTC network note in [Limits](#limits) before
you approve anything.

## Disclosures

- **Network calls.** The Hermes host fetches feeds over HTTPS GET. It fetches only
  from hosts you approved in that Space's Refresh grant, and checks the grant on
  every request. URLs must use `https` and must not contain credentials. Redirects
  are followed only on the same host, for at most five redirects. A redirect to
  another host fails. The timeout is 20 seconds. A response above 3 MB or 200
  entries fails. Feeds with `DOCTYPE` or `ENTITY` declarations are rejected. The
  Research Desk reference uses `export.arxiv.org`.
- **Files written outside the plugin's own data.** Approving a schedule writes
  `<HERMES_HOME>/scripts/living-spaces-refresh-<space-id>.py` and creates a Hermes
  cron job named `living-spaces:<space-id>`. Denying the schedule or deleting the
  Space removes both.
- **Reads outside the plugin's own data.** Schedule code reads back the cron job it
  created to show pause state and the next run. The plugin reads no other Hermes or
  user files.
- **Shell commands.** The plugin runs no shell commands and starts no subprocesses.
  Hermes's cron scheduler runs the generated Python script without an agent turn.
- **Background work.** A refresh runs on a worker thread in the Hermes process and
  ends when the fetch and write complete. An approved schedule runs only while
  Hermes's cron ticker is running. The plugin registers no startup schedule or
  gateway hook.
- **Credentials.** The plugin stores no credentials and needs none.
- **Telemetry.** None. The feed fetcher is the plugin's only outbound HTTP client.
- **Undocumented Hermes module.** Schedules import `cron.jobs`, which is not on
  Hermes's public plugin API list, so `hermes plugins validate` warns about it.
  The plugin calls `create_job`, `get_job`, `pause_job`, `resume_job` and
  `remove_job`, and patches nothing. The public automation blueprint API creates
  user-scheduled agent jobs from a prompt. It cannot create a no-agent script job
  or return a handle to pause or remove one.

## Limits

Spaces block ordinary internet connections unless you approve a site or capability. This is not a complete block: a browser feature called WebRTC can still send data that this Space can read. It does not give the Space access to Hermes, credentials, your unapproved files or other Spaces. Only put data in a Space that you trust it to handle.

- Schedules need Hermes running. The plugin supplies no cloud service.
- Catch-up policy: "Runs one current refresh when Hermes wakes. Missed intervals aren't replayed."
  If native cron is unavailable, the schedule is disabled and shows the reason.
- Projects allow 25 MB, 600 files, and 8 MB per file.
- A Space allows 50,000 records. Each record allows 256 KB of user data and 64 KB
  of source data. A batch allows 500 operations.
- Bridge messages allow 1 MB. A feed allows 3 MB and 200 entries per source.
- Runtime logs retain the latest 2,000 entries. Code revisions remain available.

Limit errors include the limit and actual value. Fetch failures retain last-good
records. Last attempt, last success, and source timestamps are separate facts.
Use `spaces_read_logs` after opening a Space to diagnose runtime errors.
Use `spaces_revisions` and `spaces_restore` for code recovery.

The plugin does not supply automatic code repair, general background code
execution, or cross-profile delegation. Release 1 acceptance is not complete.
The repository's `docs/evidence/R1-STATUS.md` lists which checks are observed,
partial and pending.

## Data and recovery

Record writes use revision checks. Conflicts preserve the current saved record
and return it for resolution. Multi-record batches commit together or not at all.
Code changes leave records intact. Data schema changes need a version and a
declarative migration. Restoring code across incompatible data versions fails
visibly. Archive pauses upkeep. Delete requires the exact Space ID and removes
the Space's schedule before its stored data.

## Uninstall and data

The database is `<HERMES_HOME>/plugin-data/living-spaces/spaces.db`.
It contains projects, content-addressed file blobs, revisions, records, grants,
sessions, run history, schedules, and runtime logs. SQLite uses WAL. Back up the
database with a SQLite-aware backup or with the owning runtime stopped.
`LIVING_SPACES_DB` overrides the path for isolated tests.

Deleting a Space removes its cron job and its script under `<HERMES_HOME>/scripts/`.
The plugin has no uninstall step of its own. Before you remove the plugin, delete
or pause each scheduled Space. A cron job left active after removal fails on each
run because its script cannot load the plugin package.

<!-- TODO(verify): whether `hermes plugins remove` deletes
<HERMES_HOME>/plugin-data/living-spaces/. State the answer here before submission. -->
