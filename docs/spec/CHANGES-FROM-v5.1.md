# Living Spaces v6 — what changed

**For Ife · 11 November 2026**

**The product is an open canvas for your bots—not another permission system around them.** v6 records your decisions so the building agents stop following the restrictions in v5.1. It does not ask you to approve those decisions again or pause the build.[1][2]

## The changes that matter

- **The bot is the author.** Living Spaces hosts, persists and isolates its work. The sandbox protects Desktop and neighbouring canvases; it does not limit the bot's tools, skills, frameworks or design.
- **Internet starts On.** The target includes ordinary web images, fonts, libraries, embeds and live connections inside the canvas, with an Off switch—not site-by-site approval. **That is not yet a verified shipping claim:** the inspected build still uses mediated public HTTPS. Forge is checking whether direct frame requests inherit backend credentials, and whether Hermes's own widgets do the same. Your answer is needed if exposure is confirmed.[2][4]
- **Upkeep is ordinary Hermes cron.** The plugin links to the native job and displays its actual prompt, schedule and results. Its extra approval and synchronisation layer is gone. The agent uses Hermes's own tools and rules. Canvas code may trigger cheap feed refresh, not agent refresh in a loop; your accepted limit stays.[1][2]
- **The canvas can ask its bot.** User-facing controls can send context through a native bot turn. No second per-tool or per-device consent system. Correct bot routing matters; an acknowledgement must not masquerade as finished work.
- **Assets come in by reference.** A bot should add its generated images, fonts and libraries without copying base64 through the conversation. Imported assets must remain usable after the original temporary file is gone.
- **No house style.** The kit is optional. The design bar is judged on real chat-built Spaces, not just polished reference screenshots. Your own design skills win over plugin defaults.[3]
- **Web dashboard access is removed from the product**, not parked as release 4.[1][2]

## What does not change

The names remain **Living Spaces** and **Spaces**. Build and edit in normal Hermes chat. User input survives; refresh never wipes it; “Saved” means durable. Revisions, restore, conflict handling and isolation remain. GBrain is not required. Demo content stays public and generic, with no novelty claim over Grok Pages or Muse Spaces.[1][5]

## What the builders now prove

All twelve old acceptance IDs are accounted for. Five are rewritten: hosting, authority, refresh, scheduling and lifecycle. Seven retain their obligations. Four new checks cover open internet, file-by-reference, canvas-to-bot and premium real chat-built output. Old schedule-approval receipts cannot pass the new scheduling check. A green test gate is not product acceptance.[1][2][5]

The **4 PM CT turn-in target remains the polished, capable app**, including those four capabilities. Native-cron core qualification comes first; the other lanes continue in parallel. Missing a target must be disclosed, not turned into a smaller definition of the product. Later collection/portability and recovery improvements remain; web access does not.[1][2]

## Still yours to decide

1. Open-frame internet if the credential probe confirms exposure; no extra home-network block is the intended Hermes-parity stance, not a verified shipping fact.
2. Whether the tab should show every bot's canvases rather than only the active backend/profile's.
3. How to explain private tool/file data on a canvas with Internet On, without rebuilding permission screens.
4. Whether canvas-to-bot requests need a cost guard beyond native behaviour; feed-only automatic refresh stays regardless.

**Delivery:** acceptance checks posted on Forge's `t_d40eb81d`, comment **2177**. `SPEC-v6.md` is the consolidation for Forge to copy into the repository and align with contracts, amendments, skill and UI. Product made no repository or branch changes and claims no new runtime acceptance.

## Sources

[1] kanban:t_8cabee1b
[2] kanban:t_d40eb81d
[3] kanban:t_978e1eb6
[4] file:///Volumes/Expansion/Development/Build/ls-audit-20261111-040430/LIMITS-AUDIT.md
[5] file:///Volumes/Expansion/Development/Projects/living-spaces/docs/spec/SPEC.md
