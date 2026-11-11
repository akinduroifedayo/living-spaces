# Spec amendments

Amendments to `SPEC.md` (v5.1). Each entry records the owner's decision, its date and the engineering status. Where an entry conflicts with SPEC.md, the entry governs.

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
