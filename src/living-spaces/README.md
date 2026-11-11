# Living Spaces

An open canvas for your bots that live in Hermes. Build and change dashboards, data displays, games, documents, and multi-view apps in normal Hermes chat. Open them from chat or the Desktop **Spaces** tab, use them, and return to your saved work.

The bot is the trusted author. Living Spaces hosts its canvas and supplies local records, project files, revisions, and diagnostics. Chat and the canvas share the same records. Refresh preserves user-owned notes and choices. Code restore creates a new revision without rewinding saved records. The sandbox separates generated code from Desktop and other Spaces.

## Experimental candidate

This candidate is **not release-ready**. `VALIDATOR-PASS` describes packaging evidence only. It does not establish product acceptance, catalog approval, or a new validation of this revision. The integrating maintainer owns final exact-head validation, installation checks, and publication.

The repository is public at [akinduroifedayo/living-spaces](https://github.com/akinduroifedayo/living-spaces). Public `main` still contains the seed; promotion of the reviewed candidate is pending. There is no catalog install-by-name route yet.

These capabilities have different qualification states:

- Normal-chat authoring, local records, revisions, and native cron upkeep have historical runtime evidence. That evidence belongs to the recorded revisions, not every later candidate.
- File-by-reference imports are implemented. Final real-chat import, restart, and restore qualification remains pending.
- Maintaining-bot controls are implemented in source. Native admission, activation, and retry safety remain open gates. The required interaction is one in-Space click, with no unattended model spend from mounting, timers, or retries. One-click safety is not yet proved.
- Release 1 uses mediated public HTTPS, including keyed APIs with the Space's own credentials. Image-by-URL support through `space.net.blob` is integrated and under final qualification. Direct frame internet is deferred by owner decision to the next release.
- Known width bugs affect the combined Desktop host and generated canvas, including clipped content and compressed host controls. They remain open until real captures qualify the repaired candidate.

## Install and enable

Use Hermes 0.23.1 or later with Desktop. This folder is the plugin package. Copy the whole folder, including its Python modules, Desktop extension, dashboard, guest runtime, scripts, skills, and bundled assets.

The manual copy route was exercised historically on macOS. Installation from the public URL has **not** been newly tested. Linux and Windows remain unqualified.

1. Clone the public repository into a new directory:

   ```sh
   git clone https://github.com/akinduroifedayo/living-spaces.git
   cd living-spaces
   ```

2. Choose an explicit reviewed candidate commit supplied by the maintainer. Replace `<reviewed-commit>` before running:

   ```sh
   git checkout --detach <reviewed-commit>
   ```

   Do not treat the seed `main` or an unreviewed branch tip as the candidate. If the reviewed commit is not published yet, wait for its promotion.

3. Identify the Hermes profile that you intend to use. In this document, `<HERMES_HOME>` means that selected profile's home.
4. Copy the entire `src/living-spaces` directory into `<HERMES_HOME>/plugins/living-spaces`. Do not overwrite or merge into an existing installation. Preserve the existing package and use an empty destination.
5. In the selected profile's CLI context, enable the Python tools and bundled skill:

   ```sh
   hermes plugins enable living-spaces
   ```

6. Enable **Living Spaces** in Desktop **Capabilities > Plugins**. This enables the Desktop extension. Both switches are required.

## Build and use a Space

Start a normal chat with the `living_spaces` toolset available. Ask, for example, "Build a reading desk with an overview, searchable library, and reading queue." The bot uses the bundled `build-space` skill and returns an **Open Space** card.

Use the Space, save a note, and reopen it from **Spaces**. Ask in the same chat to change a view or add behavior to the existing Space. Record writes use revision checks; conflicts return the saved record for resolution. Multi-record batches commit together or not at all. Failed refreshes retain last-good records.

Apps can use multiple files, custom CSS, modules, binary assets, and browser-compatible output from a framework. The kit and dependency shelf are optional. An installed design skill can guide the bot's design.

File-by-reference imports accept `from_path` for an absolute local file or `from_url` for a public HTTPS resource in a file descriptor. The backend copies bytes into project storage; it does not leave a dependency on a temporary source file. Local imports enforce allowed roots, file-size limits, and credential/store exclusions. These imports do not give canvas JavaScript arbitrary filesystem access. Native file and tool policy still applies.

## Keep a Space current

Ask in chat, for example, "Update this reading desk every morning at 7 with new papers." The bot creates an ordinary native Hermes cron job. Native cron is the sole truth for its prompt, cadence, timezone, enabled state, and executions. The plugin stores a link, with no second schedule, approval step, or synchronization layer.

The **Upkeep** panel reads native state and offers **Pause**, **Resume**, **Run now**, and **Remove**. Changes made through native cron appear there without plugin reconciliation.

- Feed upkeep fetches public RSS or Atom data without a model call.
- Agent upkeep runs a normal Hermes agent job under native tool and approval policy. It makes model and tool calls and can consume subscription quota. The panel labels it **Uses model calls**.
- Host **Refresh now** runs a feed handler or triggers agent work. For an agent handler, it runs the linked job or creates a native one-shot job if none is linked.
- Guest `space.refresh()` is restricted to the no-model feed handler. Mounting or timer-driven feed refresh must not dispatch agent upkeep.

Upkeep requires the Hermes cron runtime to be running. Native catch-up policy governs missed work; the plugin supplies no always-on cloud service. Archiving pauses linked upkeep and pending one-shot jobs. Unarchiving does not resume them. Pause and Remove stop future work; already-running native work may finish. A native failure must not be interpreted as a successful pause or removal.

## Internet and native authority

The per-Space **Internet access** setting is on by default for the implemented mediated path. `space.net.fetch` checks public HTTPS destinations and redirects. It forwards the Space's own `Cookie` and `Authorization` headers and removes them when a redirect changes origin. Hermes-specific and reserved transport headers remain blocked. Responses are limited to 5 MiB. With Internet access off, supported canvas fetches and feed retrieval are blocked. The switch does not disable the bot's normal native tools.

`space.net.fetch(url, {as: 'json'})` returns an object with `status`, `url`, `headers`, and `json`. It is not a Fetch `Response`; use its `json` field instead of calling `.json()` or reading `.body`.

Load an image URL through `space.net.blob(url)`, then assign `URL.createObjectURL(blob)` to the image. Revoke that object URL when the image is no longer needed. The helper returns a Blob, rejects non-success HTTP status, and follows the same Internet setting as `space.net.fetch`. It does not permit a direct remote `<img src>` request.

Live embeds, streams, WebSockets, and libraries loaded from the web at runtime are not supported in release 1. Bundled assets and libraries remain available. Direct frame internet is deferred, not silently enabled.

Internet Off is not a promise of zero outbound data. WebRTC can still send data that the Space can read. Data already delivered to a Space cannot be recalled. Consider what data you put in an internet-enabled canvas.

Maintaining-bot controls are intended to address the Space's own bot through a native turn and Hermes's existing policy. Source implementation does not prove correct admission or safe activation and retries in the running candidate. A submitted request is not a completed answer. The plugin adds no per-tool, per-site, per-device, or upkeep approval system.

## Data, costs, and compatibility

Space data is local SQLite at `<HERMES_HOME>/plugin-data/living-spaces/spaces.db`. It includes projects, file blobs, revisions, records, grants, sessions, feed history, upkeep links, and runtime logs. Native cron retains agent execution history. The plugin sends no telemetry. Records can enter the configured model's context when a bot reads them, and internet requests contact their destination services.

The plugin needs no Hermes credentials and does not read credential stores. User-provided API keys are Space data. A key held only in generated code memory is not automatically saved. If a Space saves a key in a record or project file, it lives in this SQLite store, with no additional encryption or vault protection. It may remain in revisions or backups and enter model context when a bot reads it. The mediated path attaches only credentials supplied by the Space, never Hermes's own credentials. Direct frame networking is deferred.

Feed scheduling writes `<HERMES_HOME>/scripts/living-spaces-refresh-<space-id>.py` and creates a native cron job. Agent scheduling creates the native job without a feed script. Hermes executes the script or agent job under its normal runtime policy. Removing upkeep or deleting the Space removes associated future jobs and the feed script.

Upkeep uses the private `cron.jobs` and `cron.executions` modules. Desktop session cleanup uses the raw `window.hermesDesktop` bridge to retain the original backend target. These integrations carry compatibility risk and catalog-review warnings. This is not an all-public-SDK or catalog-approved package.

Projects allow 25 MiB, 600 files, and 8 MiB per file. A Space allows 50,000 records, with 256 KiB of user data and 64 KiB of source data per record. Batches allow 500 operations; bridge messages allow 1 MiB. Runtime logs retain the latest 2,000 entries. These limits do not promise a total cap on retained revision storage.

## Recovery and removal

Use chat to ask the bot to inspect scoped runtime logs and repair the Space. The tools include `spaces_read_logs`, `spaces_revisions`, and `spaces_restore`. Code restore and user-data recovery are separate. Incompatible schema restoration and interrupted migrations still need final candidate qualification.

Back up the database with a SQLite-aware backup or with its owning runtime stopped. SQLite uses a write-ahead log, so copying only a live database file can omit recent writes.

Before removing the plugin, remove each Space's upkeep through **Upkeep**, or delete the Space. Disabling the extension alone does not cancel native cron jobs. Unhandled jobs can remain scheduled and fail after package removal.

After handling upkeep, disable **Living Spaces** in Desktop **Capabilities > Plugins**. In the selected profile's CLI context, run:

```sh
hermes plugins disable living-spaces
hermes plugins remove living-spaces
```

Package removal does not erase the separate `plugin-data` directory. Space deletion is logical removal, not secure disk erasure; file blobs and external backups can remain. Uninstall has not been newly rehearsed for this candidate.

## Repository documentation and license

The following relative links refer to repository documentation and may be unavailable when this folder is copied alone:

- [Specification](../../docs/spec/SPEC.md) and [amendments](../../docs/spec/AMENDMENTS.md). Later owner decisions govern.
- [Evidence ledger](../../docs/evidence/R1-STATUS.md). Historical receipts apply to their recorded revisions; they are not fresh passes for this candidate.
- [Interim design qualification](../../docs/design/premium-pass/qualification-addendum-20261111/QUALIFICATION-INTERIM.md). The inspected composed-width failures need repaired-candidate captures.
- [MIT License](../../LICENSE). Copyright Living Spaces contributors.

Vendored libraries and fonts retain their own licenses. The package's [third-party notices](THIRD-PARTY.md) describe the bundled shelf and remaining provenance gaps. The root MIT license does not replace those notices.
