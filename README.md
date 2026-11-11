# Living Spaces

Ask your Hermes agent for a dashboard, tracker, planner, game, or multi-view app in normal Desktop chat. The agent builds its files and saves it in the **Spaces** tab. Living Spaces provides hosting, persistent records, revisions, permissions, diagnostics, and upkeep.

## Development status

Release 1 is a private local build. It has not merged to `main`, entered the public catalog, or received final product and design acceptance. [The acceptance ledger](docs/evidence/R1-STATUS.md) records evidence, failures, and remaining checks.

The engineering build has exercised normal-chat creation, saved edits, restart persistence, refresh, native schedules, revision restore, and repair in an isolated Hermes Desktop instance. These observations do not imply that every R1 criterion passes.

## What the current build provides

- Apps can contain multiple views, custom CSS, modules, and binary assets. The design kit and its seven presets are optional. An installed design skill takes precedence over the supplied defaults.
- Records distinguish source fields from user fields. Refresh preserves user notes and statuses. Supplied record revisions protect against stale edits. File changes create revisions without resetting records.
- Each Space runs in opaque-origin frames. The host binds the capability bridge to that Space and its current session.
- Internet access is on by default through `space.net.fetch`. The host checks public HTTPS destinations and redirects. Direct frame networking, CDN imports, and remote embeds remain blocked.
- Host-owned permissions show the exact agent task and schedule before approval. A changed task requires new Refresh approval. Upkeep can use a cheap feed handler or a normal Hermes cron agent job with model calls and enabled tools.
- Libraries copy into a Space only when requested. The current shelf adds htm, Lucide, Inter, and DM Sans alongside Preact, hooks, the optional kit, and lightweight-charts. [The third-party notice](src/living-spaces/THIRD-PARTY.md) records licenses and known provenance gaps. Miro's larger [curated shelf](docs/design/DEPENDENCY-SHELF.md) is a proposal, not a list of shipped modules.

## Important boundaries

Internet access is mediated, not an open browser network policy. `space.net.fetch(url, {as: 'json'})` returns an object containing `status`, `url`, `headers`, and `json`. It does not return a Fetch `Response` with `.json()` or a `.body` property.

Turning Internet access off is not a complete outbound block. WebRTC can still send data readable by the Space. The Permissions panel discloses this browser limitation. Data already delivered to a Space cannot be recalled.

Agent upkeep uses the user's model subscription and the tools enabled for native Hermes cron jobs. It is not a new restricted agent sandbox. Approval shows that cost and access distinction.

## Repository references

- [Approved spec v5.1](docs/spec/SPEC.md) and [owner amendments](docs/spec/AMENDMENTS.md) define product scope. Amendments govern conflicts.
- [Engineering contracts](docs/contracts/CONTRACTS.md) define storage, bridge, tools, and integration changes.
- [R1 evidence](docs/evidence/R1-STATUS.md) separates stock tests, real Desktop observations, review, and acceptance.
- [Design direction](docs/design/) contains Miro's kit, references, and design receipts.
- [Future package-tool proposal](docs/architecture/PACKAGES.md) is design-only and does not authorize installation.

Source lives in `src/`. Test and qualification code lives in `tests/` and `harness/`. Public demo content is the only fixture content admitted to this repository.
