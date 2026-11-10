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
This release is under development. A package missing another lane's artifacts
is not ready for an end-to-end install.

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

## Permissions and network disclosure

Spaces block ordinary internet connections unless you approve a site or capability. This is not a complete block: a browser feature called WebRTC can still send data that this Space can read. It does not give the Space access to Hermes, credentials, your unapproved files or other Spaces. Only put data in a Space that you trust it to handle.

Release 1 has no approved-site embeds, device access, arbitrary tool invocation,
file access, or cross-Space access. Generated applications run inside a sandbox.
The host supplies their own records, refresh operations, and scoped logs through
`window.space`. Public feed retrieval runs on the host over HTTPS, only for
approved declared hosts. Credentials are not required and must not enter projects.

## Data and recovery

The database is `<HERMES_HOME>/plugin-data/living-spaces/spaces.db`.
It contains projects, content-addressed file blobs, revisions, records, grants,
sessions, run history, schedules, and runtime logs. SQLite uses WAL. Back up the
database with a SQLite-aware backup or with the owning runtime stopped.
`LIVING_SPACES_DB` overrides the path for isolated tests.

Record writes use revision checks. Conflicts preserve the current saved record
and return it for resolution. Multi-record batches commit together or not at all.
Code changes leave records intact. Data schema changes need a version and a
declarative migration. Restoring code across incompatible data versions fails
visibly. Archive pauses upkeep. Delete requires the exact Space ID and removes
the Space's schedule before its stored data.

Approved schedules use Hermes cron and a host-generated script under
`<HERMES_HOME>/scripts/`. The plugin registers no startup schedule or gateway hook.
Catch-up runs one current refresh when Hermes wakes. Missed intervals are not
replayed. Missing cron support reports a blocked state.

## Limits and diagnostics

- Projects allow 25 MB, 600 files, and 8 MB per file.
- A Space allows 50,000 records. Each record allows 256 KB of user data and 64 KB
  of source data. A batch allows 500 operations.
- Bridge messages allow 1 MB. A feed allows 3 MB and 200 entries per source.
- Runtime logs retain the latest 2,000 entries. Code revisions remain available.

Limit errors include the limit and actual value. Fetch failures retain last-good
records. Last attempt, last success, and source timestamps are separate facts.
Use `spaces_read_logs` after opening a Space to diagnose runtime errors.
Use `spaces_revisions` and `spaces_restore` for code recovery.

The plugin does not supply a cloud service, automatic code repair, general
background code execution, or cross-profile delegation. Real chat creation,
Desktop sandbox behavior, restart persistence, and schedule execution need
integrated verification. Adapter unit tests alone do not establish those outcomes.
