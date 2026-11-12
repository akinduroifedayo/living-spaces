# Living Spaces

An open canvas for your bots that live in Hermes. Build and change dashboards, data displays, games, documents, and multi-view apps in normal Hermes chat. Open them from chat or the Desktop **Spaces** tab, use them, and return to your saved work.

The bot is the trusted author. Living Spaces hosts its canvas and supplies local records, project files, revisions, and diagnostics. Chat and the canvas share the same records. Refresh preserves user-owned notes and choices. Code restore creates a new revision without rewinding saved records. The sandbox separates generated code from Desktop and other Spaces.

## Proven in Desktop

Ordinary chat built Pocket Garden. Entries saved inside the Space survived leaving and reopening, and a chat-requested Light view preserved all four plant records. An image loaded by URL through `space.net.blob`. One in-Space bot-button click made one native request; its answer appeared in chat and the Space without losing saved plant data.

Sky Window, Research Desk and Pair Play were also rebuilt through ordinary Desktop chat, with independent functional checks passing 9/9, 10/10 and 8/8. Native Hermes cron wrote a generated brief into closed Research Desk; reopening displayed it, with all 47 existing user-data payloads byte-identical. The narrow-width overflow repair passed independent design review.

The release is on public `main` at [akinduroifedayo/living-spaces](https://github.com/akinduroifedayo/living-spaces). See [current release status](../../docs/evidence/R1-STATUS.md) for the receipt-backed summary and [catalog PR #153809](https://github.com/NousResearch/hermes-agent/pull/153809).

## Install and enable

Use Hermes 0.23.1 or later with Hermes Desktop. Qualified on macOS. This folder is the plugin package; the repository root is not.

In the Hermes profile where you want Living Spaces, install from the public plugin subdirectory and enable it:

```sh
hermes plugins install akinduroifedayo/living-spaces/src/living-spaces --no-deps --no-enable
hermes plugins enable living-spaces
```

Then enable **Living Spaces** in Desktop **Capabilities > Plugins** and open **Spaces**. The CLI and Desktop switches enable different parts of the plugin; both are required. The [root installation guide](../../README.md#install) also provides a pinned command and a manual-copy fallback.

## Build and use a Space

Start a normal chat with the `living_spaces` toolset available. Ask, for example, "Build a reading desk with an overview, searchable library, and reading queue." The bot uses the bundled `build-space` skill and returns an **Open Space** card.

Use the Space, save a note, and reopen it from **Spaces**. Ask in the same chat to change a view or add behavior to the existing Space. Record writes use revision checks; conflicts return the saved record for resolution. Multi-record batches commit together or not at all. Failed refreshes retain last-good records.

Apps can use multiple files, custom CSS, modules, binary assets, and browser-compatible output from a framework. The kit and dependency shelf are optional. An installed design skill can guide the bot's design.

File-by-reference imports accept `from_path` for an absolute local file or `from_url` for a public HTTPS resource in a file descriptor. The backend copies bytes into project storage; it does not leave a dependency on a temporary source file. Local roots are the active Hermes home's `cache/images`, `cache/documents`, `cache/screenshots`, `cache/vision`, `cache/video`, `cache/videos`, `cache/generated/images`, `downloads/connectors`, `images` and `cache/scratch`, their supported populated legacy media directories, and Python's current temp directory. The whole Hermes home, general cache and user home are not import roots. Credential/store exclusions still apply when temp overlaps them, and symlinked cache roots cannot expand admission. Stage any other authorized file with native tools into a fresh temp directory first, under normal file/tool policy; do not stage credentials to bypass a refusal. This does not restrict content, build output, frameworks or project layout beyond resource limits, and does not give canvas JavaScript arbitrary filesystem access.

## Keep a Space current

Ask in chat, for example, "Update this reading desk every morning at 7 with new papers." The bot creates an ordinary native Hermes cron job. Native cron is the sole truth for its prompt, cadence, timezone, enabled state, and executions. The plugin stores a link, with no second schedule, approval step, or synchronization layer.

The **Upkeep** panel uses public cron list metadata and offers **Pause**, **Resume**, **Run now**, and **Remove**. Changes made through native cron appear there without plugin reconciliation. The public tool exposes a truncated prompt preview, not the complete task, execution history, or manual/catch-up dispatch status. These views and the stored timezone are explicitly unavailable rather than reconstructed from private stores. The model-call label follows the public job's `no_agent` field rather than a potentially stale plugin link. Only explicit `no_agent=true` is labelled no-model; an omitted flag retains the model-call warning. A successful run request can queue, forward, execute, skip, or fail; its public response is not proof of a successful execution or delivery.

- Feed upkeep fetches public RSS or Atom data without a model call.
- Agent upkeep runs a normal Hermes agent job under native tool and approval policy. It makes model and tool calls and can consume subscription quota. The panel labels it **Uses model calls**. New agent schedules require at least 15 minutes between nominal fires to limit unattended model-call frequency. User tasks are capped at 8,000 Unicode characters to bound recurring prompt cost; the plugin wrapper does not count toward that task limit. These are bounds on new scheduling inputs, not a quota or runtime limit for jobs edited elsewhere.
- Host **Refresh now** runs a feed handler or triggers agent work. For an agent handler, it runs the linked job or creates a native one-shot job if none is linked.
- Guest `space.refresh()` is restricted to the no-model feed handler. Mounting or timer-driven feed refresh must not dispatch agent upkeep.

Scheduling either upkeep kind, resuming or running any linked upkeep, and agent Refresh now are refused while the public `ctx.current_cron_execution()` reports a bound native cron execution identity. Status, pause, remove, and non-model feed refresh remain available. This is intentionally stricter than `cron.allow_agent_scheduling=true`: the public plugin context cannot read the global flag, and public tool dispatch does not enforce it. No plugin setting substitutes for the global policy. The host deliberately returns no current execution for delegated child agents, so this guard is not transitive ancestry enforcement, and the plugin adds no private configuration or lineage reader.

Agent cadence accepts ordinary intervals, single daily/weekly time phrases, one-shot delays/timestamps, and five-field cron with numeric minute/hour lists, ranges, and steps. Cron clock spacing is checked across the full day, including midnight, conservatively ignoring calendar restrictions. Six-field or otherwise unprovable cadence forms fail closed. Native cron still validates every accepted schedule and scans every prompt through the public create action before the existing schedule is removed. Feed cadence is unchanged. The 15-minute bound is nominal local-clock spacing, not an elapsed-time guarantee across timezone transitions.

Upkeep requires the Hermes cron runtime to be running. Native catch-up policy governs missed work; the plugin supplies no always-on cloud service. Archiving pauses linked upkeep and pending one-shot jobs. Unarchiving does not resume them. Pause and Remove stop future work; already-running native work may finish. A native failure must not be interpreted as a successful pause or removal.

## Internet and native authority

The per-Space **Internet access** setting is on by default for the implemented mediated path. `space.net.fetch` checks public HTTPS destinations and redirects. It forwards the Space's own `Cookie` and `Authorization` headers and removes them when a redirect changes origin. Hermes-specific and reserved transport headers remain blocked. Responses are limited to 5 MiB. With Internet access off, supported canvas fetches and feed retrieval are blocked. The switch does not disable the bot's normal native tools.

`space.net.fetch(url, {as: 'json'})` returns an object with `status`, `url`, `headers`, and `json`. It is not a Fetch `Response`; use its `json` field instead of calling `.json()` or reading `.body`.

Load an image URL through `space.net.blob(url)`, then assign `URL.createObjectURL(blob)` to the image. Revoke that object URL when the image is no longer needed. The helper returns a Blob, rejects non-success HTTP status, and follows the same Internet setting as `space.net.fetch`. It does not permit a direct remote `<img src>` request.

Internet Off is not a promise of zero outbound data. WebRTC can still send data that the Space can read. Data already delivered to a Space cannot be recalled. Consider what data you put in an internet-enabled canvas.

Maintaining-bot controls address the Space's own bot through a native turn and Hermes's existing policy. The Pocket Garden check observed one request from one click and a completed answer in both chat and the Space. The plugin adds no per-tool, per-site, per-device, or upkeep approval system.

## Data, costs, and compatibility

Space data is local SQLite at `<HERMES_HOME>/plugin-data/living-spaces/spaces.db`. It includes projects, file blobs, revisions, records, grants, sessions, feed history, upkeep links, and runtime logs. Native cron retains agent execution history. The plugin sends no telemetry. Records can enter the configured model's context when a bot reads them, and internet requests contact their destination services.

The plugin needs no new credentials. The mediated network path never reads Hermes credential stores or attaches Hermes credentials. Space-supplied API credentials are Space data: values saved in project files or records can persist in revisions and backups or enter model context when a bot reads them. The plugin adds no secret vault.

Feed scheduling writes `<HERMES_HOME>/scripts/living-spaces-refresh-<space-id>.py` and creates a native cron job. Agent scheduling creates the native job without a feed script. Hermes executes the script or agent job under its normal runtime policy. Removing upkeep or deleting the Space removes associated future jobs and the feed script.

Upkeep uses `ctx.dispatch_tool("cronjob_manage", ...)` for all job operations, including one-shots and teardown; it imports no private cron modules. Desktop session cleanup uses public `ctx.rest` in the active scope and a pinned plugin RPC through `host.requestProfile` after a scope switch. Cross-scope cleanup requires the owning gateway to support `plugin-rpc-v1`; unsupported or ambiguous routes fail closed and report cleanup failure. These paths use public host APIs; compatibility remains tied to the documented host contract. Catalog approval is not implied.

Projects allow 25 MiB, 600 files, and 8 MiB per file. A Space allows 50,000 records, with 256 KiB of user data and 64 KiB of source data per record. Batches allow 500 operations; bridge messages allow 1 MiB. Runtime logs retain the latest 2,000 entries. These limits do not promise a total cap on retained revision storage.

## Recovery and removal

Use chat to ask the bot to inspect scoped runtime logs and repair the Space. The tools include `spaces_read_logs`, `spaces_revisions`, and `spaces_restore`. Code restore and user-data recovery are separate.

Back up the database with a SQLite-aware backup or with its owning runtime stopped. SQLite uses a write-ahead log, so copying only a live database file can omit recent writes.

Before removing the plugin, remove each Space's upkeep through **Upkeep**, or delete the Space. Disabling the extension alone does not cancel native cron jobs. Unhandled jobs can remain scheduled and fail after package removal.

After handling upkeep, disable **Living Spaces** in Desktop **Capabilities > Plugins**. In the selected profile's CLI context, run:

```sh
hermes plugins disable living-spaces
hermes plugins remove living-spaces
```

Package removal does not erase the separate `plugin-data` directory. Space deletion is logical removal, not secure disk erasure; file blobs and external backups can remain.

## Repository documentation and license

The following relative links refer to repository documentation and may be unavailable when this folder is copied alone:

- [Specification](../../docs/spec/SPEC.md) and [amendments](../../docs/spec/AMENDMENTS.md). Later owner decisions govern.
- [Current release status](../../docs/evidence/R1-STATUS.md), summarizing observed Desktop, upkeep, design and packaging results.
- [MIT License](../../LICENSE). Copyright Living Spaces contributors.

Vendored libraries and fonts retain their own licenses. The package's [third-party notices](THIRD-PARTY.md) describe the bundled shelf. The root MIT license does not replace those notices.
