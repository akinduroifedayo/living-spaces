# Attempt 3: Astra route blocked by missing Codex credential

At 07:18 CT on 2026-11-11 the owner-approved route (t_d40eb81d comments 2222 and 2224) was in place. The isolated home config was set to `gpt-6-astra` on `openai-codex` with priority service tier. A new ordinary Desktop chat session showed the picker label "GPT-6-astra · Fast". The exact Sky Window prompt was sent once through native composer input.

The gateway could not resolve the route. `gateway-log-excerpt.txt` records `codex_auth_missing`: "No Codex credentials stored." The Desktop displayed "The AI service rejected your API key" (`sky-window-codex-auth-missing.png`, with the bottom 32 footer pixels excluded). The isolated `HERMES_HOME` has no `auth.json`. The handoff assumed Codex auth would resolve through `HOME`, but the gateway's Codex resolver reads the Hermes auth store under `HERMES_HOME`, not `~/.codex`.

Nothing was generated. The session row shows model `gpt-6-astra` but has zero persisted messages and zero tool calls. Sky Window's spaces, records, revisions and grants rows match before and after (Sky Window still has 4 revisions). Research Desk and Pair Play were not sent.

`blocker-receipt.json` lists six checks, all passing, and the SHA-256 of every artifact. `regen.py`, `ui.py` and `clipshot.py` are the exact drivers used.

Resume requires an owner decision. Either authorize a Codex OAuth login or credential provisioning for the isolated home only, or choose another route that already has credentials. Copying credentials or adding auth was explicitly unauthorized, so it was not attempted. No retry was made on Sonnet, and no gateway restart was performed.
