# Living Spaces

An open canvas for your bots that live in Hermes. Ask for a dashboard, reading desk, tracker, game, or multi-view app in normal chat. Your bot builds the Space, and you open it from chat or the Desktop **Spaces** tab. Return later, use your saved work, and ask the bot to change it.

Living Spaces provides local records, project files, revisions, diagnostics, and ordinary native Hermes cron upkeep. Chat, the canvas, and upkeep use the same records. Refresh preserves user-owned notes and choices. Restoring code creates a revision without rolling back saved records.

## Candidate status

This is an **experimental candidate, not release-ready**. `VALIDATOR-PASS` describes packaging evidence, not product acceptance or a fresh validation of this revision. Final exact-head validation, installation checks, and publication belong to the integrating maintainer.

The [public repository](https://github.com/akinduroifedayo/living-spaces) is available. Public `main` still contains the seed; promotion of the reviewed candidate is pending. There is no catalog install-by-name route yet.

The candidate includes these capabilities and qualifications:

- Multi-file apps, custom CSS, binary assets, and optional bundled libraries. The design kit is optional.
- File-by-reference imports are implemented. The bot can copy local files or public HTTPS resources into durable project assets without echoing base64. Final real-chat import, restart, and restore qualification remains pending.
- Upkeep uses ordinary native cron as its sole schedule and execution truth. The plugin keeps a link, with no approval or synchronization layer. The Upkeep panel reads native state and offers Pause, Resume, Run now, and Remove. Agent work uses model calls and subscription quota; feed refresh does not.
- Maintaining-bot controls are implemented in source. One genuine click inside a Space can start at most one ordinary Hermes chat turn. There is no second Send control. The click is attributed to **a click inside this Space**, not a specific callback. A Space's own code could start that one turn from another click inside the same Space. Hermes's normal approvals still govern what the bot does. Source tests and standalone browser checks do not replace final real-Desktop qualification. See [the intent boundary and next-release proposal](docs/evidence/BOT-INTENT-BOUNDARY.md).
- Release 1 uses mediated public HTTPS retrieval, including keyed APIs with the Space's own credentials. The `space.net.blob` image-by-URL helper is integrated and under final qualification. Direct frame internet is deferred by owner decision to the next release. Live embeds, streams, WebSockets, and libraries loaded from the web at runtime are not supported. See the [mechanism findings and remaining checks](docs/evidence/DIRECT-INTERNET-NEXT-RELEASE.md).
- Known narrow-layout bugs affect the composed Desktop and generated canvas. Repairs require real captures of the repaired candidate before the bugs can be marked closed.

Internet Off blocks supported canvas fetches, but is not a complete outbound-data guarantee because WebRTC remains an exception. Native bot tools follow Hermes's own authority. Private cron APIs and raw Desktop bridge use also remain compatibility and catalog-review concerns.

## Network, credentials, and background work

Spaces can request any public HTTPS host through mediated fetch, subject to destination checks, redirects, and response limits. This includes keyed APIs and image URLs. Requests can send data readable by that Space to the selected third party. Feed upkeep contacts its configured public sources. The plugin sends no telemetry.

A user-provided API key is Space data, not a Hermes credential. If generated code keeps it only in memory, Living Spaces does not automatically save it. If the Space saves it in records or project files, it is stored in the profile's `plugin-data/living-spaces/spaces.db`, together with revisions and file blobs. The plugin adds no encryption or secret-vault protection. Saved values can remain in revisions or backups, and a bot reading those records or files can include them in model context. Choose what you save accordingly.

The mediated path forwards only credentials supplied by the Space in its own request, including `Authorization` and `Cookie`. It does not read Hermes credential stores or attach Hermes's credentials. Cross-origin redirects remove the Space's authorization and cookie headers. This is not a shared browser login or cookie jar.

Native Hermes cron provides background upkeep while Hermes runs. Agent jobs use model calls and enabled tools under native Hermes policy; feed jobs do not use a model. The Upkeep panel exposes the linked job and its controls. Remove upkeep before uninstalling the plugin, because native jobs can outlive plugin removal. There is no separate plugin daemon.

## Install a reviewed revision

Use Hermes 0.23.1 or later with Desktop. Historical installation evidence covers the manual copy route on macOS. Installation from the public URL has **not** been newly tested.

1. Clone `https://github.com/akinduroifedayo/living-spaces.git`.
2. Check out an explicit reviewed candidate commit. Do not install the seed `main` as the candidate.
3. Copy the entire `src/living-spaces` directory to the selected Hermes profile's `plugins/living-spaces` directory. Do not overwrite an existing installation. Preserve it and use an empty destination.
4. In that profile's CLI context, run `hermes plugins enable living-spaces`.
5. Enable **Living Spaces** in Desktop **Capabilities > Plugins**. Both enable steps are required.

The [package README](src/living-spaces/README.md) includes usage, data, upkeep, and removal disclosures.

## Repository documentation

The [specification](docs/spec/SPEC.md) and [amendments](docs/spec/AMENDMENTS.md) record scope; later owner decisions govern. The [evidence ledger](docs/evidence/R1-STATUS.md) contains historical receipts, not blanket current passes. The [interim design qualification](docs/design/premium-pass/qualification-addendum-20261111/QUALIFICATION-INTERIM.md) records the inspected layout failures.

## License

Living Spaces is licensed under the [MIT License](LICENSE), copyright Living Spaces contributors. Vendored libraries and fonts retain their own licenses. [Third-party notices](src/living-spaces/THIRD-PARTY.md) include the remaining provenance gaps.
