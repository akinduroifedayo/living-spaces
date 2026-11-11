# Living Spaces

Build persistent applications in normal Hermes chat and use them in the Desktop
**Spaces** tab. An app can have multiple views, local modules, bundled libraries,
and structured records. Chat and the app read and change the same records.
Code revisions support repair and restore without rewinding saved data.

Release 1 supports **Refresh now** for public RSS and Atom feeds, and upkeep that
runs as an ordinary Hermes cron job. Ask in chat and Hermes creates the job. Your
request is the consent, as for any Hermes cron job. The Space's **Upkeep** panel
shows exactly what runs and lets you pause, resume, run or remove it. Refresh
updates source fields while retaining user notes and status. Upkeep needs Hermes
running.

- **Feed upkeep** fetches a public feed with no model call.
- **Agent upkeep** runs the full Hermes agent on a prompt, with the profile's
  enabled tools. It uses model calls and can consume subscription quota. The
  Upkeep panel shows the full prompt and says "Uses model calls".
- Space code can trigger only the no-model feed refresh, never agent upkeep.

This is an unreleased candidate in a private repository. Package validation passed
at `872480426c70fb7cfac1eda3d0837809a66e6955` with 16 checks and one private-import
warning. That is not Release 1 acceptance. See [Evidence and open checks](#evidence-and-open-checks).

## Install and enable

This folder is the plugin package. Use Hermes 0.23.1 or later. A complete package
includes `plugin.yaml`, `__init__.py`, `_core.py`, `desktop/plugin.js`,
`dashboard/`, `guest/`, `runtime/`, `scripts/`, `skills/`, and `living_spaces_core/`.
Use the active Hermes profile's home wherever `<HERMES_HOME>` appears below.
Only macOS has qualification evidence; Linux and Windows remain unqualified.

1. From an authorized checkout, copy the entire `src/living-spaces/` directory
   into `<HERMES_HOME>/plugins/living-spaces/`. Copy the package, not the repository
   root. Do not overwrite an existing installation without backing it up.
   There is no published catalog entry to install by name yet.
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
5. Open the Space. To keep it current, ask in chat, for example "Update Research
   Desk every morning at 7 with new papers." Hermes creates a cron job named
   `living-spaces:<space-id>`. Open **Upkeep** in the Space to see what runs.

Enabling the plugin does not grant a Space anything beyond what is shown in
**Permissions**: its own data, runtime logs and Internet access. Turning Internet
access off makes feed refresh return `not_granted`.

## Permissions

Open a Space, select **Permissions**, then **Revoke** beside a granted capability.
Read the confirmation and select **Revoke** again. Data already delivered to the
Space cannot be recalled, and completed requests cannot be undone. To stop
recurring upkeep, open **Upkeep** and select **Pause**, or **Remove** to delete the
job. A job that is running when you pause or remove it finishes. Permissions
control Internet access and data, not the cron job.

Release 1 has no approved-site embeds, device access, arbitrary tool invocation,
file access, or cross-Space access. Generated applications run inside a sandbox.
The host supplies their own records, the no-model feed refresh, and scoped logs
through `window.space`. Public feed retrieval runs on the host over HTTPS and
needs Internet access on. Credentials are not required and must not enter projects.
The Permissions panel shows the WebRTC network note in [Limits](#limits).

## Disclosures

- **Network calls.** The Hermes host fetches feeds over HTTPS GET to public
  addresses only, and checks the Space's Internet access setting on every request.
  URLs must use `https` and must not contain credentials. Redirects
  are followed only on the same host, for at most five redirects. A redirect to
  another host fails. The timeout is 20 seconds. A response above 3 MB or 200
  entries fails. Feeds with `DOCTYPE` or `ENTITY` declarations are rejected. The
  Research Desk reference uses `export.arxiv.org`.
- **Files written outside the plugin's own data.** Creating feed upkeep writes
  `<HERMES_HOME>/scripts/living-spaces-refresh-<space-id>.py` and creates a Hermes
  cron job named `living-spaces:<space-id>`. Agent upkeep creates the job only.
  Removing upkeep or deleting the Space removes the job and any script. Refresh now
  on an agent Space with no job creates a one-shot job named `living-spaces:<space-id>:once`.
- **Reads outside the plugin's own data.** The Upkeep panel reads the native cron
  job and its recent executions live. The plugin stores only a link to the job, not
  a copy of its prompt or schedule. The owner label is derived from
  the active profile name; the plugin also resolves that profile's home. Generated apps receive no general file access.
- **Shell commands.** The plugin runs no shell commands and starts no subprocesses.
  Hermes's cron scheduler runs feed upkeep's generated Python script without an
  agent turn, and runs agent upkeep as a normal agent job.
- **Model calls and cost.** Agent upkeep makes model and tool calls on the active
  profile and can consume its quota. It is not a restricted sandbox. Feed upkeep
  and the in-app Refresh now make no model call.
- **Background work.** A refresh runs on a worker thread in the Hermes process and
  ends when the fetch and write complete. Upkeep runs only while
  Hermes's cron ticker is running. The plugin registers no startup schedule or
  gateway hook.
- **Credentials.** The plugin stores no credentials and needs none.
- **Privacy.** Space data is local SQLite under the active profile at
  `<HERMES_HOME>/plugin-data/living-spaces/spaces.db`. The plugin sends no telemetry
  or usage reporting. Approved feed requests contact the declared host. When you
  ask chat to read a Space, its records can enter the configured model's context.
  The WebRTC disclosure below applies to data a generated app can read.
- **Undocumented Hermes module.** Upkeep imports `cron.jobs` and `cron.executions`,
  which are not on Hermes's public plugin API list, so `hermes plugins validate`
  warns about them. The plugin calls `create_job`, `get_job`, `pause_job`,
  `resume_job`, `trigger_job`, `remove_job` and `list_executions`, and patches nothing. The public automation blueprint API creates
  user-scheduled agent jobs from a prompt. It cannot create a no-agent script job
  or return a handle to pause or remove one. The Upkeep panel needs that handle so
  pause, archive and delete control the same job. This private
  API can break on a Hermes release. Catalog acceptance of the warning remains
  open; Forge must resolve the public scheduling seam with maintainers before
  claiming compliance with the public-surfaces requirement.

## Limits

Spaces block ordinary internet connections unless you approve a site or capability. This is not a complete block: a browser feature called WebRTC can still send data that this Space can read. It does not give the Space access to Hermes, credentials, your unapproved files or other Spaces. Only put data in a Space that you trust it to handle.

- Upkeep needs Hermes running. The plugin supplies no cloud service.
- Catch-up policy: "Runs one current refresh when Hermes wakes. Missed intervals aren't replayed."
  If native cron is unavailable, the Upkeep panel shows the error.
- Archiving pauses upkeep. Unarchiving does not resume it; resume it in the Upkeep panel.
- Projects allow 25 MB, 600 files, and 8 MB per file.
- A Space allows 50,000 records. Each record allows 256 KB of user data and 64 KB
  of source data. A batch allows 500 operations.
- Bridge messages allow 1 MB. A feed allows 3 MB and 200 entries per source.
- Runtime logs retain the latest 2,000 entries. Code revisions remain available.

An oversized bridge request with a usable request ID receives `limit`; a malformed
request with a usable ID receives `invalid`. The host no longer silently drops
those rejected requests. Unidentifiable envelopes cannot receive a correlated reply.
Storage limit errors include the limit and actual value. Fetch failures retain last-good
records. Last attempt, last success, and source timestamps are separate facts.
Use `spaces_read_logs` after opening a Space to diagnose runtime errors.
Use `spaces_revisions` and `spaces_restore` for code recovery.

The plugin does not supply automatic code repair, general background code
execution, or cross-profile delegation. Release 1 acceptance is not complete.
The repository's [R1-STATUS](../../docs/evidence/R1-STATUS.md) is the acceptance ledger.

## Data and recovery

Record writes use revision checks. Conflicts preserve the current saved record
and return it for resolution. Multi-record batches commit together or not at all.
The observed repair and compatible code restore preserved records. Incompatible
data-version restore and interrupted migration still need Desktop qualification.

To archive, open **More Space actions > Archive Space…** and confirm. This keeps
records and revisions and pauses the upkeep job. From the archived Space, select
**Delete…**, read the permanent-loss warning and confirm **Delete Space**. The
host sends the Space ID confirmation; the current dialog does not ask you to
type it. R1-11 observed deletion of a disposable Space, its native cron job and
its feed script. Exported copies and backups are not recalled. Deletion is
logical removal, not secure disk erasure; content-addressed project file blobs
can remain in the profile database.

## Uninstall and data

The database is `<HERMES_HOME>/plugin-data/living-spaces/spaces.db`.
It contains projects, content-addressed file blobs, revisions, records, grants,
sessions, feed run history, links to upkeep cron jobs, and runtime logs. SQLite uses WAL. Back up the
database with a SQLite-aware backup or with the owning runtime stopped.
`LIVING_SPACES_DB` overrides the path for isolated tests.

Deleting a Space removes its cron job and its script under `<HERMES_HOME>/scripts/`.
The plugin has no uninstall step of its own. Before you remove the plugin, remove
each Space's upkeep in its Upkeep panel or delete the Space. A cron job left active after removal fails on each
run because its script cannot load the plugin package.

After handling upkeep, disable the Desktop extension in **Capabilities > Plugins** and run `hermes plugins disable living-spaces`. To remove the package,
run `hermes plugins remove living-spaces`. The current Hermes removal code removes
the plugin tree and install/config metadata, not its separate `plugin-data`
directory. Removal is not a data-erasure operation. Uninstall has not been
rehearsed in Desktop; Forge must verify it before publication.

## Evidence and open checks

The [validation receipt](../../docs/evidence/runs/validate-8724804/raw.log)
is for `8724804`, not the final submission commit. Forge must validate the final
candidate again and set the catalog pin afterward. The
[R1 ledger](../../docs/evidence/R1-STATUS.md) records these boundaries.

| Check | Evidence and remaining work |
|---|---|
| R1-01 | Pending integrated Desktop network/adversarial qualification and origin-check diagnosis. No complete network-isolation claim. |
| R1-02 | Normal chat created Research Desk before packaging repair; requalification remains open. |
| R1-03 | Save/reopen and chat-to-open-app updates observed; ambiguous-target non-mutation remains open. |
| R1-04 | Research Desk evolution and Pair Play creation/evolution observed; broader acceptance review remains open. |
| R1-05 | Rerun required under A-03 (shortened: Internet access, Data and Diagnostics grants, revocation and redaction; no Refresh grant). Earlier receipts covered the removed approval flow and do not count. |
| R1-06 | Real arXiv retrieval retained notes; failure/recovery retained records. Rerun required under A-03. Stale concurrent edits during refresh remain open. |
| R1-07 | Rerun required under A-03: a chat-created native job, the Upkeep panel, pause, resume, run now and remove. Earlier receipts covered the removed approval flow. Catch-up and final test-job cleanup remain open. |
| R1-08 | Full isolated restart preserved projects, records, revisions and grants. Resource limits and interrupted-work recovery remain open. |
| R1-09 | Repair passed 15/15 after a disclosed harness fault and a real chat repair; the model retried a call with wrong argument names. |
| R1-10 | Compatible restore preserved records in the 18/18 failure/restore run. Incompatible data-version restore remains open. |
| R1-11 | Lifecycle passed 23/23 before A-03, including typed rejections, session close/reopen, cross-Space confinement, deduplication and fixture archive/delete. Rerun required for upkeep link cleanup. In-place frame reload replay remains open. |
| R1-12 | Miro's running-candidate usability qualification and return-use journey remain pending. |

Upkeep follows [A-03](../../docs/spec/AMENDMENTS.md): the native cron job is the
only truth, with no plugin-side approval step. Engineering status is in progress
and not qualified.

These counts are prior receipts summarized by R1-STATUS, not new runs performed
while updating this README. Final screenshots follow Miro's design kit merge.
