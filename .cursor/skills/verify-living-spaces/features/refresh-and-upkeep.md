# Refresh a Space and control upkeep

A user updates source data, sees failures without losing notes, and controls ordinary Hermes cron upkeep.

## Sub-features

- `refresh-host` runs the Space's declared handler from Refresh now.
- `refresh-guest` uses an app's no-model feed refresh control.
- `refresh-failed` retains last-good source data and all user fields after failure.
- `refresh-double-agent` compares Desktop twice against Desktop plus native chat on the same agent-upkeep Space. Both pins produced one job after Desktop twice, but two native one-shots and two model-backed cron sessions after Desktop plus chat.
- `upkeep-create` schedules a feed or agent job through ordinary chat.
- `upkeep-control` pauses, resumes, runs, and removes linked upkeep.
- `upkeep-recovery` displays missing, unlinked, and one-shot jobs truthfully.

## How to get to it (user POV)

- Open a Space and choose **Refresh** in the floating island. It appears only when the Space declares a refresh; otherwise **Details** explains *This Space has no refresh of its own…*. A failed-refresh notice also offers **Try again**.
- Use an authored feed canvas's refresh button. Guest refresh never dispatches agent upkeep.
- Choose **More Space actions > Upkeep**, or **Details > Manage upkeep**. The upkeep state is shown under Details > Freshness; the old **Upkeep: none/on/paused** island buttons no longer exist.
- Ask the bot in chat to keep that Space current. Native **Scheduled jobs** is another entry to those same cron jobs.
- In Upkeep use **Run now**, **Pause**, **Resume**, and **Remove**. Review **More Space actions > History > Run history** (or **Details > Open history**) for feed results.

## Driving it with control-living-spaces

Preconditions:

- A feed fixture needs a declared public HTTPS source and a successful source fetch. The Notebook fixture has no refresh handler.
- Agent Refresh and agent schedules use model calls. The scoped native race used only the disposable app's existing `nous/welcome` model and an agent fixture without recurring upkeep. Do not configure another provider or schedule recurring work from this grant.
- Only the disposable home's cron may be changed. No scheduler or live home mutation is authorized by this skill.

- **Host entry.** On a Space with a declared refresh, click the island's Refresh. Capture before/after and require an actual completed source-data change, not a queued job response. On Notebook require no Refresh control and the Details explanation (`mapped_journeys.py` case `upkeep-empty-and-refresh-unavailable`); never call that a successful refresh.
- **History entry.** Click `button[aria-label="More Space actions"]`, then `text=History`, then `text=Run history`. Require the exact attempted run's trigger, status, and error or result. No runs is an unmet precondition for success-history coverage.
- **Upkeep entry.** Click `text=Details`, then `text=Manage upkeep` (or More Space actions > Upkeep). Require **No upkeep yet** on Notebook. This proves only the empty state.
- **Double Desktop Refresh.** `mapped_journeys.py` prepares the separate agent fixture and clicks Refresh twice. The second gesture encountered the native disabled or busy button on both pins. One native job and one cron session resulted. This does not test Desktop plus chat.
- **Desktop plus chat.** Run `"$(dirname "$C")/race_native.py" --repo /Volumes/Expansion/Development/Build/living-spaces-app-verification-candidate --out "/Volumes/Expansion/Development/Build/living-spaces-app-verification-evidence/candidate-race-$(date +%Y%m%d-%H%M%S)"`. The runner prepares and cleans a fresh instance. It clicks native Desktop Refresh, switches back to native chat, and submits the drafted `spaces_refresh` request for the same Space. Repeat separately against the baseline worktree. Compare exact native one-shot IDs, cron session IDs, API-call counts, and overlap timestamps in `race-result.json`. Both recorded pins reproduced two native dispatches and two model runs. A command exit of zero means the experiment completed, not deduplication passed.
- **Schedule.** In authorized chat submit `Keep Verification Notebook current every morning at 7 America/Chicago.` only after an appropriate handler and permitted model are present. Require a real native job ID and a matching Upkeep row before proceeding.
- **Pause and resume.** Click `text=Pause`, verify the exact native job disabled in a second public view, then click `text=Resume` and verify it enabled. Already-running work may finish.
- **Run.** Click `text=Run now`. Preserve dispatch separately from execution. The public API does not expose full execution history or delivery proof.
- **Remove.** Click `text=Remove`, then the confirmation dialog's Remove button. Require no link, orphan, or one-shot job in the refreshed public view. Preserve records and note payloads.

## Gotchas

- No handler, feed source, source records, native upkeep link, or model auth is seeded by the Notebook fixture. Do not weaken these journeys to pass.
- `control.py` now launches with `nous.guest: false`, so a fresh home has no `nous/welcome` route and `mapped_journeys.py` reports `refresh-double-agent` as `verified-unreachable`. The race receipts below come from the earlier welcome-trial runs; reproducing them needs an explicitly approved model route.
- The optional agent fixture supplies only the declared agent-upkeep task. `baseline-desktop-chat-race-01` recorded jobs `2a5836e07588` and `e34e9cd534f2`, with native API-call counts 6 and 5. `candidate-desktop-chat-race-01` recorded jobs `c84fbfee5685` and `a368e04ab02d`, with counts 6 and 6. Chat dispatch fell inside the first cron session on each pin. The Space runs table remained empty. Each run left one paused, disabled one-shot before owned teardown.
- A native job request can queue, forward, skip, or fail. A successful request is not completed upkeep.
- Network mocks are permitted only at the product's existing external transport boundary and must be labeled. They do not prove live source compatibility.
- Public native cron omits full prompts, timezone, execution history, and manual dispatch status in some views. Keep its observations separate from explicitly labeled read-only session-database telemetry in the disposable home. Do not claim that session telemetry appeared in the public UI.
- Archive pauses future upkeep. Restore does not resume it. Do not resume a real user's jobs during verification.
