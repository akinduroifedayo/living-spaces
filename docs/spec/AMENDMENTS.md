# Spec amendments

> **Definition (Ife, A-04).** "I see spaces as an open canvas for your bots that live in Hermes." The bot is the trusted author and the canvas is its surface. This supersedes the framing of SPEC v5.1, which treated a Space as an untrusted app to be permissioned.

Authority: later explicit Ife decisions govern. `SPEC.md` is now Product's delivered v6 and replaces conflicting historical amendment and v5.1 wording. V5.1 is retained in `history/SPEC-v5.1.md`. Historical decisions below retain their attribution and status; they do not override v6's current open-frame target or acceptance checks.

Each entry records the owner's decision, date and engineering status. Entries that precede v6 are historical where v6 supersedes them. Later explicit owner decisions still govern.
## A-01. Spaces reach the internet; isolation is unchanged (Nov 10, 2026)

**Decision (Ife).** "Well why is internet restricted for spaces? It should be exposed to whatever Hermes's is exposed to. Whats the restriction?. Isn't that limiting?"

This supersedes SPEC.md's "ordinary network access is blocked by default" and moves approved sites from release 2 into one per-Space switch.

**Rule.**
- Each Space has a host-owned **Internet access** permission. It is on by default. The user switches it in the host Permissions panel. Space code cannot change it. The agent can ask for it to be turned back on, and that request goes through host Approve.
- Isolation is the same in both states. A Space cannot reach the Desktop page, the Hermes backend or gateway, files, credentials, other Spaces, browser storage, loopback, or private and link-local networks.

**What release 1 ships (engineering status: in progress, not qualified).** Internet access is **mediated**. Space code calls `space.net.fetch(url, options)`. The Hermes backend makes the request after checking every resolved address of the target. It pins the connection to the checked public address and re-checks each redirect. It allows HTTPS only, attaches no cookies or credentials, and caps responses at 5 MiB. The frame itself stays network-off, using the CSP qualified 86/86 under R1-01.

**Why not an open frame CSP.** A read-only feasibility review against the installed Electron 44.9.3 / Chromium 152 and Hermes 7f3ac61 found three problems (`run/seats/network-feasibility/attempt-1/summary.md`):
- A CSP that allows `https:` also allows `https://127.0.0.1`, LAN addresses, cloud metadata and DNS-rebinding targets.
- Plugins get no per-frame request or IP hook.
- The default-session header hook would attach remote-backend headers to a Space request aimed at that backend.

Shipping an open CSP would break the isolation half of this decision.

**Consequences.**
- Live APIs, JSON, text and remote images work through `space.net.fetch` (images arrive as bytes).
- Direct CDN script imports, web fonts from the network and iframe embeds (YouTube, maps) do not work in release 1. Bundled shelf libraries, agent-vendored files and binary assets cover most of that need.
- **R1-01 is redefined:**
  - With Internet access on, `space.net.fetch` reaches public HTTPS.
  - With it off, `net.fetch` returns `not_granted`.
  - In both states, direct frame network paths stay blocked, local and private targets fail, and Space code cannot flip the switch.
- The WebRTC caveat applies to the frame in both states, because the frame CSP is unchanged. The Permissions copy shows it with the Off state.

**Open items for Ife.**
1. A direct open-frame mode (CDN imports, embeds) needs a host capability: an isolated Space session with an egress broker. That is a shared-Hermes change and needs separate approval. Post-submission.
2. Release 2: when a Space with internet on asks for files or private tools, the approval prompt must state that combination plainly.

## A-02. The plugin is the environment, not a constraint (Nov 10, 2026)

**Principle (Ife).** "The important thing with spaces is, our plugin is providing the space and environment for the agent to build what the user wants. Dashboards, mini apps, trackers etc. our plugin shouldn't be limiting the agent, its tools, skills, design etc."

And: "one thing I want to make sure we are building to ultimate agent customizability and design of these spaces and not just bland looking html. If more dependencies are needed, let's think about what those look like etc"

**Rule.** Every limit needs a safety, data-integrity or resource reason. Only these stay limited:
- isolation (the Desktop page, backend, files, credentials, other Spaces, local and private network)
- host-owned grants and the Internet access switch
- data-integrity rules (saved versus unsaved state, revisions, conflicts)
- generous, documented resource caps

Anything else is allowed. That includes any file types and layout, any framework or plain JS, bundled or self-vendored libraries, binary assets including generated images, and a theme object with free token overrides. The kit is optional, and an installed design skill takes precedence over the plugin's design defaults.

**Release 1 work under this principle (status: in progress):**
- Binary file descriptors in the agent tools.
- Manifest `theme` with presets and tokens.
- Optional offline dependency shelf.
- `space.asset()`.
- Build-skill rules rewritten as guidance rather than prohibitions.
- **Agent upkeep mode:** a native Hermes cron agent job with a prompt can run alongside the cheap no-agent feed handler. Chat creates it and the Space's Upkeep panel shows that it uses model calls. See A-03, which replaced the approval flow this bullet first described.

**Open item for Ife.** A host-side package install tool lets the agent request `name@version`. The host fetches it, verifies integrity, bundles it and stores it in the Space. It is a release 2 design item.

## A-03. Upkeep is an ordinary Hermes cron job (Nov 11, 2026)

**Question (Ife).** "Why is this a blocker? Won't scheduled refresh be a potential cron or routine with the full Hermes agent capability and tools updating the space?"

**Decision (Ife).** At about 04:00 CT on Nov 11, 2026 Ife answered "Yes" to making the native-cron-only design the shipping path and to stopping the R03 repair of the approval layer.

This supersedes SPEC.md v5.1's host-owned schedule approval and the Refresh capability, and the approval text in A-02 and in CONTRACTS.md section 14.

**Rule.**
- The native Hermes cron job is the only truth for a schedule. The plugin stores a link to it and nothing else: no copy of the prompt, cadence, timezone, enabled state or approval state.
- Chat creation is consent, as for any Hermes cron job. The agent creates the job with `spaces_schedule_upkeep` when the user asks. There is no pending state and no host Approve step.
- Each Space has a live **Upkeep** panel. It reads the native job and shows what runs: the full prompt for an agent job, cadence, timezone, state, next and last run, and recent executions. It offers Pause, Resume, Run now and Remove. Agent upkeep is labeled "Uses model calls".
- **Refresh now** runs the feed handler directly. For an agent handler it triggers the linked cron job, or a one-shot agent job when none is linked.
- Removed: the schedule states (requested, active, paused, disabled), `spaces_request_schedule`, host schedule approval and Resume rechecks, the Refresh permission and its host-scope reapproval, exact-prompt approval binding, and the copy of agent run history into Space history.
- Kept: the Internet access (`net`) permission, Data and Diagnostics grants, the public-address check and last-good feed behavior, source-owned writes, the WebRTC disclosure, the private `cron.jobs` and `cron.executions` imports and the backend-pinned frontend cleanup. Existing `audit` rows are untouched.

**Four defaults.**
1. Guest code can trigger only the no-model feed handler. A guest `refresh` against an agent handler returns `blocked` (`agent_from_guest`). Agent upkeep runs from Refresh now in Hermes or from chat.
2. Archiving a Space pauses its job. Unarchiving does not resume it. The user resumes it in the Upkeep panel or in chat.
3. A job that is running when the user pauses or removes it finishes. Pause and remove stop future runs, not the current one.
4. Migration is idempotent. Each existing schedule row with a native job becomes a link, then the `schedules` table is dropped and `refresh` grants are deleted.

**Why.** Three review rounds each found defects in the plugin-side sync layer that mirrored schedule state and approval (reviewer report: `/Volumes/Expansion/Development/Build/living-spaces-r1/run/seats/r02-xreview/REPORT.md`; frozen R03 tests at commit `8b5f758` on `forge/r1-r03-tests`). That evidence is why the layer was removed rather than repaired. The native job already has one owner and one schedule, so the plugin no longer keeps a second copy that can disagree.

**Evidence to rerun.** R1-05 (shortened: Internet access, Data and Diagnostics grants and revocation, with no Refresh grant), R1-06, R1-07 and R1-11. Earlier receipts for the removed approval flow do not count toward these.

**Engineering status: in progress, not qualified.** The contract is `docs/contracts/CONTRACTS.md` section 14.

## A-04. A Space is an open canvas for the user's bots (Nov 11, 2026)

**Definition (Ife).** "I see spaces as an open canvas for your bots that live in Hermes. Is this what we are building? Because if you look at it that way, the choices we are making are much clearer in terms of product."

This is the definition of the product. It supersedes the framing of SPEC v5.1.

**What it settles (comment 2155).**
1. **The bot is the trusted author; the canvas is its surface.** v5.1 treated a Space as an untrusted app to be permissioned. That framing produced the internet block, the build-skill bans and the approval layer for upkeep. The sandbox stays to protect the Desktop app and to keep one canvas from breaking another, not to police the bot.
2. **When in doubt, do what Hermes does for the bot's own chat widgets.** If a choice needs a permission screen Hermes doesn't have, it is the wrong choice.
3. **Anything the bot can do in chat, it can put on or do for a canvas:** any tool, any skill, any time, from chat, cron or another task.
4. **The canvas talks back to its bot.** A control on a canvas can ask its bot to act. Under this definition that is core, not an extra.
5. **Keep:** the user's own input on a canvas is never overwritten by the bot's refresh, saved means saved, revisions and restore.

**Engineering status.** Points 2 to 4 are a lens for defaults, not shipped features. Point 3 is partly shipped (chat and cron already write Spaces through the `spaces_*` tools). Point 4 is in progress, not qualified (see A-06). Point 5 ships and is covered by the existing record, revision and restore evidence.

## A-05. Release 4 is removed; the permission model becomes "the canvas asks its bot" (Nov 11, 2026)

**Decision (Ife).** "I don't even consider the release 4 items in scope of what this product should be."

**Rule.**
- Release 4 (authenticated web dashboard access) is **removed from the roadmap, not deferred**. No web dashboard, remote access or hosted surface is planned. It does not appear in the README, catalog entry or demo.
- Release 2's per-tool, per-site and per-device permission model (approved sites, camera, microphone, location, per-tool Hermes grants) is **replaced by "the canvas asks its bot"**. A canvas needing something asks the bot that owns it, and the bot acts with Hermes's own tools under Hermes's own approval rules. The plugin adds no permission screen Hermes doesn't have (A-04, point 2).
- The Internet access switch (A-01), the Data and Diagnostics grants and the WebRTC disclosure are unchanged by this entry.

**Engineering status: the canvas-to-bot path is in progress, not qualified (A-06).**

## A-06. Scope for the 4 PM turn-in (Nov 11, 2026)

**North Star (Ife, comment 2151, verbatim).** "the North Star for this plugin is for the agent and user to have this space as persistent display for any dashboard, data, mini app etc. is that still what we are building? And also I want to be turning in the full polished app including the full capabilities and premium design."

**Reading.** A Space is a persistent display the agent and the user share. The agent, with all of Hermes's tools and skills, builds it and keeps it current. The plugin hosts, persists and isolates, and adds no consent or sync layer that Hermes doesn't have.

**Turn-in lanes, in priority order.** Each is its own lane, merged only when green and reviewed. None may hold the core candidate hostage. Not making a lane is acceptable; silently dropping it is not, and the README and catalog list whatever is left out.

| Lane | Intent | Engineering status |
|---|---|---|
| Open internet in the frame | With Internet access on, the frame reaches web images, fonts, CDN libraries, embeds and WebSocket, matching what Hermes's own widget frame allows. `space.net.fetch` stays for CORS-less APIs. Off stays as it is. Default-on shipping waits on the credential-exposure question (backend headers attached by URL in Desktop's default session) and Ife's decision on the answer. | in progress, not qualified |
| File-by-reference | Write tools accept a file value of `{"from_path": "<local file>"}` or `{"from_url": "https://..."}`, and the backend copies the bytes into the Space, so generated images, fonts and libraries go in with a one-line call. Space caps stay and are stated to the agent. No request, approve, resolve, verify or bundle lifecycle. | in progress, not qualified |
| Canvas-to-bot | A control in a Space sends a request to the owning chat or a fresh agent turn, as native widgets do with `window.hermes.send`. The agent updates the Space with all its tools under Hermes's own approval rules. No per-tool plugin grants. | in progress, not qualified |
| Premium design | Host-chrome fixes (no placeholder text such as "Not reported", edge-to-edge canvas, one Upkeep control, a real Internet switch) and an art-directed build skill, followed by regenerated demo Spaces through real chat. | in progress, not qualified |

**Also in scope if small:** rename, pin and search on the Spaces index.

**Constraint.** Native cron has its own toolset and approval policy. Removing the plugin's consent must not bypass or widen that. A linked job runs with what an ordinary chat-created cron job gets (A-03).

**What the docs may claim.** Only what is shipped at the documented commit. The four lanes above are listed as in progress wherever they appear.
