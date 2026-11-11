# Add living-spaces to the plugin catalog

<!-- Draft. Not opened. Catalog submission, public visibility and the hackathon submission
need separate owner approval (docs/evidence/R1-STATUS.md). Pin the SHA before use. -->

Proposed catalog PR, not opened. The repository is still private. Forge must
validate the final candidate and set its exact pin; Ife must approve publication.

This PR will add one file, `plugin-catalog/living-spaces.yaml`. It pins
`https://github.com/akinduroifedayo/living-spaces` at `PIN_40_CHAR_SHA_AT_FINAL_COMMIT`, subdirectory
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

## Install, enable and remove access

For this private candidate, copy the complete `src/living-spaces/` package from an
authorized checkout to the active profile's `<HERMES_HOME>/plugins/living-spaces/`.
Do not copy only the renderer bundle or overwrite an existing install without a
backup. Use Hermes 0.23.1 or later. There is no catalog-name installation yet.

Run `hermes plugins enable living-spaces` so `plugins.enabled` includes
`living-spaces`. Also enable **Living Spaces** in Desktop **Capabilities > Plugins**.
Both switches are required. Start a normal chat with the `living_spaces` toolset
available, request Research Desk, then use the **Open Space** card. Review the
Space's **Permissions** before approving refresh or a requested schedule.

To revoke, open **Permissions**, choose **Revoke** on the granted capability and
confirm **Revoke**. Data already delivered cannot be recalled and completed
requests cannot be undone. Use **More Space actions > Pause upkeep** to explicitly
pause recurring work. Revocation blocking a fresh mount is observed; revocation
stopping future scheduled work remains open under R1-07.

To delete, choose **More Space actions > Archive Space…** and confirm, then
**Delete… > Delete Space** on the archived Space after reading the permanent-loss
warning. Archive keeps records/revisions and pauses upkeep. Delete removes the
Space, its records/revisions, native job and schedule script. The current host
supplies the Space ID confirmation; there is no typed-ID input. Backups and
exported copies are not recalled. Deletion is logical removal, not secure disk
erasure; content-addressed project file blobs can remain in the profile database.

Before uninstalling, delete or pause scheduled Spaces. Disable the Desktop switch
and run `hermes plugins disable living-spaces`, then
`hermes plugins remove living-spaces`. Current Hermes source removes the package and install/config
metadata, leaving the separate profile `plugin-data` directory. Uninstall is not
data erasure and still needs an isolated rehearsal before publication.

## Hermes surfaces used

| Surface | Use |
|---|---|
| Python tools | `register()` calls `ctx.register_tool` for 13 tools in the `living_spaces` toolset: `spaces_list`, `spaces_get`, `spaces_create`, `spaces_read_file`, `spaces_write_files`, `spaces_edit_file`, `spaces_query`, `spaces_write_records`, `spaces_read_logs`, `spaces_revisions`, `spaces_restore`, `spaces_refresh`, `spaces_request_schedule`. |
| Bundled skill | `ctx.register_skill("build-space", ...)` registers `skills/build-space/SKILL.md` and its reference apps. |
| Dashboard plugin API | `dashboard/manifest.json` declares a hidden `/spaces` tab and `plugin_api.py`. The FastAPI router serves Space listing, bundles, bridge sessions, records changes, runs, refresh, grants, schedule, revisions, logs, archive, pin and delete. |
| Desktop plugin SDK | `desktop/plugin.js` imports only `@hermes/plugin-sdk` and `react`. It registers a `/spaces` page in `ROUTES_AREA`, a **Spaces** entry in `SIDEBAR_NAV_AREA`, and the `living-space` directive in `TRANSCRIPT_DIRECTIVE_AREA` for the Open Space card. |
| Native cron | Approving a schedule creates a no-agent job through `cron.jobs`. See [Validator warning](#validator-warning). |

The plugin registers no hooks, no middleware, no startup schedule and no gateway hook. It
declares no `requires_env` and no host capabilities (`capabilities: []`). The
catalog `capabilities` mapping summarizes registered tools/hooks/middleware/env;
it is a different schema from the manifest's host-capability list. The trusted
Desktop extension has renderer authority; the generated Space runs in the sandbox.

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
  created to show pause state and the next run. It resolves the active profile home
  and derives the owner label from its name. Generated apps receive no general
  file access.
- **Shell commands.** The plugin runs no shell commands and starts no subprocesses. Hermes's
  cron scheduler runs the generated Python script without an agent turn.
- **Background work.** A refresh runs on a worker thread in the Hermes process and ends when
  the fetch and write complete. An approved schedule runs only while Hermes's cron ticker is
  running. The plugin starts no long-running process of its own.
- **Credentials.** The plugin stores no credentials and needs none. Feed URLs with embedded
  credentials are rejected.
- **Privacy and telemetry.** The plugin sends no telemetry or usage reporting.
  Data stays in local SQLite under the active profile at
  `<HERMES_HOME>/plugin-data/living-spaces/spaces.db` (WAL). Approved feeds contact
  their declared hosts. Chat can read Space records into the configured model's
  context; the WebRTC note below applies to data the generated app can read.
- **Network limit of generated apps.** See [Known limits](#known-limits).

## Validator warning

`hermes plugins validate <export>/src/living-spaces --install-deps` passed at
`872480426c70fb7cfac1eda3d0837809a66e6955`, exit 0, with 16 passed checks and one
warning. The [raw receipt](../evidence/runs/validate-8724804/raw.log) includes
Desktop admission, a safe security scan and no runtime core rebinds.

The warning identifies the `cron.jobs` import in `living_spaces_core/schedules.py`, which is not on the public plugin API list. The plugin calls
`create_job`, `get_job`, `pause_job`, `resume_job` and `remove_job`. It does not patch,
wrap or rebind anything in that module.

The reason is that Hermes has no public plugin API for this kind of job. The public
`ctx.register_automation_blueprint` adds a prompt template that a user schedules as an
agent job. It has no no-agent script option, and it returns no handle to pause or remove the
job. Living Spaces needs a no-agent job created when the user approves a Space's schedule,
and paused or removed when that Space is paused, archived or deleted. This private API
can break on any Hermes release. Public-surfaces compliance remains unresolved for
catalog review. Forge must resolve the scheduling seam with maintainers; opening
an upstream issue also needs Ife approval.

The exact warning is:

```text
⚠ private core imports (catalog rule 9: public surfaces only; these can break on
any release): living_spaces_core/schedules.py:18 cron.jobs. Use ctx.* /
documented plugin APIs, or open an issue for the seam you need.
```

The final candidate has not been validated at its final pin. Forge owns that run
and the subsequent placeholder replacement. A passing validator does not resolve
maintainer acceptance of a private API or prove Release 1 acceptance.

## Known limits

The host-owned Permissions panel displays this note under the heading "Before you approve
anything":

> Spaces block ordinary internet connections unless you approve a site or capability. This is not a complete block: a browser feature called WebRTC can still send data that this Space can read. It does not give the Space access to Hermes, credentials, your unapproved files or other Spaces. Only put data in a Space that you trust it to handle.

- Schedules need Hermes running. The catch-up policy is:
  "Runs one current refresh when Hermes wakes. Missed intervals aren't replayed."
- Release 1 has no approved-site embeds, device access, arbitrary tool invocation, file
  access or cross-Space access.
- Bridge requests over 1 MB with a usable ID receive `limit`; malformed requests
  with a usable ID receive `invalid`. Unidentifiable messages cannot receive a
  correlated reply. R1-11 observed typed errors and no stored writes.
- Qualification evidence covers macOS only. Linux and Windows remain unqualified.
- Release 1 acceptance is incomplete. [R1-STATUS](../evidence/R1-STATUS.md) records
  R1-01 and R1-12 as pending, R1-02 as observed before packaging repair, and the
  remaining checks as partial. R1-05 authority passed 22/22, R1-09 repair 15/15,
  failure/restore 18/18 and R1-11 lifecycle 23/23 in prior isolated runs.
- Open checks include integrated ordinary-network qualification, creation after
  packaging repair, ambiguous targets, broader evolution, concurrent edits during
  refresh, missed-run catch-up, revoke-stops-schedule, final schedule cleanup,
  resource/interruption recovery, incompatible data-version restore and in-place
  frame reload replay. Narrower-than-requested grants are absent from the frozen
  contract. Miro's usability qualification and Ife's final acceptance remain open.
- Schedule update evidence used a deliberately altered source record, focus
  emulation and a harness navigation fallback. Repair and lifecycle used disclosed
  fixtures. Those receipts must not be presented as an unedited product journey.

## Screenshots and submission gates

Final screenshots are pending Forge after Miro's design kit merges. Use public
Research Desk/arXiv and Pair Play content only. Capture six gallery images from
the final candidate: Open Space card, Research Desk Library with a demo note,
Permissions with the full WebRTC note, refresh result, approved schedule with
pause control, and Pair Play Progress. Pin GitHub-hosted image URLs to the final
candidate SHA; attach UI screenshots to this PR before opening it.

[CHECKLIST.md](CHECKLIST.md) tracks the admission requirements. Public repository,
catalog PR, demo-video publication and Typeform submission each need Ife approval.
No catalog PR or hackathon submission is claimed here.
