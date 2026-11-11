# Add living-spaces to the plugin catalog

Draft only. No PR is open. The repository remains private. The candidate pin, final validation, screenshots and publication approval are pending.

## Why

Ife's definition: "I see spaces as an open canvas for your bots that live in Hermes." The bot is the trusted author and the canvas is its surface. Concretely, Ife wants normal Hermes Desktop chat to build persistent applications with multiple views and upkeep that runs as an ordinary Hermes cron job. Living Spaces gives those applications a Spaces tab, shared records, revisions, permissions and diagnostics. The agent uses the bundled build-space skill and fourteen spaces_* tools, then returns an Open Space card.

## Proposed catalog change

Add only `plugin-catalog/living-spaces.yaml`, from [the catalog draft](catalog-entry.draft.yaml). The package is `src/living-spaces`, version `0.1.0`, requiring Hermes `>=0.23.1`. Replace `PIN_40_CHAR_SHA_AT_FINAL_COMMIT` only after validating that exact commit. Qualification currently covers macOS only.

## Access and data boundaries

- Both the profile plugin switch and Desktop Capabilities switch must enable Living Spaces. The package registers tools, a skill, a dashboard API and Desktop contributions. It registers no hooks, middleware or startup schedule and declares no environment requirements or host capabilities.
- The trusted Desktop extension has renderer authority. Generated apps run in opaque-origin sandboxed frames. Their bridge binds records, logs and allowed operations to one Space and session.
- Internet access is on by default per Space. `space.net.fetch` mediates public HTTPS requests and redirects, blocks local/private destinations and Hermes backends, and can send data readable by the Space. At this commit direct frame networking, CDN imports and remote embeds stay blocked; open internet in the frame, file-by-reference and a canvas-to-bot control are in progress, not qualified, and not claimed here. Internet access is independently revocable.
- Revocation is not a complete outbound block. WebRTC can still send data the Space can read. It does not grant access to Hermes, credentials, unapproved files or other Spaces. Already delivered data cannot be recalled.
- Records and project files persist in the active profile's `plugin-data/living-spaces/spaces.db`. Refresh preserves user fields. Stale writes conflict. Restore does not rewind saved records. Chat can place Space data in the configured model's context. The plugin sends no telemetry and stores no credentials.
- Upkeep is an ordinary Hermes cron job. The user asks in chat and the agent creates it; that request is the consent, and the native job is the only schedule record (the plugin stores a link). Each Space's Upkeep panel reads the job live, shows exactly what runs, and offers Pause, Resume, Run now and Remove. Amendment A-03 records the decision.
- Feed upkeep fetches public sources without a model call. Agent upkeep uses the active Hermes profile's model subscription and enabled tools, with their existing permissions. It is not a newly restricted agent sandbox and can consume quota; the panel says "Uses model calls". Space code can trigger only the no-model feed refresh, not agent upkeep.
- Native cron jobs run only while Hermes runs. Catch-up performs one current refresh, not every missed interval. Feed upkeep writes a generated script under `<HERMES_HOME>/scripts`; native cron owns execution. Archive pauses the job and unarchive does not resume it. The plugin starts no independent service.
- Optional libraries and fonts are copied from the pinned offline shelf, not installed from arbitrary packages. [README](../../README.md) and [THIRD-PARTY.md](../../src/living-spaces/THIRD-PARTY.md) list shipped items and provenance limits.

## Qualification and compatibility holds

[The acceptance ledger](../evidence/R1-STATUS.md) distinguishes source tests, actual Desktop observations, failures and missing evidence. Release acceptance is not passed. Upkeep was reworked under A-03, so R1-05 (shortened), R1-06, R1-07 and R1-11 are being rerun. Engineering status is in progress, not qualified. Running-candidate design review and Ife's acceptance remain open.

Preliminary validation of `59aef209f46cc38bf396f5807feb4fe5d6e11edf` exits 0. [The actual log](../evidence/runs/validator-59aef20/raw.log) reports two catalog warning classes. Rule 9 flags private `cron.jobs` and `cron.executions` imports. Rule 8 flags raw `window.hermesDesktop` access used to keep session cleanup bound to its original backend. No supported pinned REST target was found in the inspected SDK. This is not an all-public-SDK or catalog-approved package. Maintainer review remains required. Opening an upstream issue also needs Ife's approval.

## Removal and publication

Remove upkeep or delete Spaces with upkeep before disabling and removing the plugin. Archive retains data and pauses the upkeep job. Delete removes the Space and its native scheduling artifacts, but is not secure erasure and does not recall backups. Hermes removal leaves separate plugin data. An isolated uninstall rehearsal remains required.

Final screenshots must come from the validated running candidate, not static design frames. [The checklist](CHECKLIST.md) tracks remaining submission requirements. Public visibility, a catalog PR, video publication and hackathon submission each require separate owner approval. Nothing is submitted by this draft.
