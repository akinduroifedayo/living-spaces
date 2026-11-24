# Refresh a Space and control upkeep

A user updates source data, sees failures without losing notes, and controls ordinary Hermes cron upkeep.

## Sub-features

- `refresh-host` runs the Space's declared handler from Refresh now.
- `refresh-guest` uses an app's no-model feed refresh control.
- `refresh-failed` retains last-good source data and all user fields after failure.
- `refresh-double-agent` presses agent Refresh twice quickly and compares native one-shot job/run counts on both released 4aea12d and unpublished 8008dcc. W31 reported duplicates; this workstream has not reproduced them.
- `upkeep-create` schedules a feed or agent job through ordinary chat.
- `upkeep-control` pauses, resumes, runs, and removes linked upkeep.
- `upkeep-recovery` displays missing, unlinked, and one-shot jobs truthfully.

## How to get to it (user POV)

- Open a Space and choose **Refresh now**. A failed-refresh banner also offers **Try again**.
- Use an authored feed canvas's refresh button. Guest refresh never dispatches agent upkeep.
- Choose **Upkeep: none**, **Upkeep: on**, **Upkeep: paused**, or **More Space actions > Upkeep** in a narrow view.
- Ask the bot in chat to keep that Space current. Native **Scheduled jobs** is another entry to those same cron jobs.
- In Upkeep use **Run now**, **Pause**, **Resume**, and **Remove**. Review **History > Run history** for feed results.

## Driving it with control-living-spaces

Preconditions:

- A feed fixture needs a declared public HTTPS source and a successful source fetch. The Notebook fixture has no refresh handler.
- Agent Refresh and agent schedules use model calls. They require a separate permitted model/session and explicit upkeep intent.
- Only the disposable home's cron may be changed. No scheduler or live home mutation is authorized by this skill.

- **Host entry.** Run `"$C" click --out "$RUN" --value 'text=Refresh now'`. Capture before/after and require an actual completed source-data change, not a queued job response. On Notebook require the explanatory unavailable state, never call that a successful refresh.
- **History entry.** Click `text=History`, then `text=Run history`. Require the exact attempted run's trigger, status, and error or result. No runs is an unmet precondition for success-history coverage.
- **Upkeep entry.** Click `text=Upkeep: none`. Require **No upkeep yet** on Notebook. This proves only the empty state.
- **Double agent Refresh.** On an actually authored agent-handler Space with authorized isolated upkeep, capture the current native **Scheduled jobs** list and `"$C" jobs --out "$RUN"`. Return to that Space; run `"$C" click --out "$RUN" --value 'text=Refresh now'` twice back-to-back, preserving both action timestamps and screenshots. Reopen Scheduled jobs, run `jobs` again, and compare exact native one-shot IDs and the Space's **Upkeep > Refresh now jobs** rows. Contract expectation: a second request returns the same non-terminal run, not an additional one-shot. Record actual deltas even if the result fails. Run the same journey on both pins, with a fresh home for each; optionally repeat with simultaneous normal-chat Refresh when a permitted model exists. Never substitute direct Python handler calls for either click. No agent-handler fixture, authorized model, or loaded Desktop exists in this draft run, so this is an explicit blocked journey, not a passing regression test.
- **Schedule.** In authorized chat submit `Keep Verification Notebook current every morning at 7 America/Chicago.` only after an appropriate handler and permitted model are present. Require a real native job ID and a matching Upkeep row before proceeding.
- **Pause and resume.** Click `text=Pause`, verify the exact native job disabled in a second public view, then click `text=Resume` and verify it enabled. Already-running work may finish.
- **Run.** Click `text=Run now`. Preserve dispatch separately from execution. The public API does not expose full execution history or delivery proof.
- **Remove.** Click `text=Remove`, then the confirmation dialog's Remove button. Require no link, orphan, or one-shot job in the refreshed public view. Preserve records and note payloads.

## Gotchas

- No handler, feed source, source records, native upkeep link, or model auth is seeded by the Notebook fixture. Do not weaken these journeys to pass.
- A native job request can queue, forward, skip, or fail. A successful request is not completed upkeep.
- Network mocks are permitted only at the product's existing external transport boundary and must be labeled. They do not prove live source compatibility.
- Public native cron omits full prompts, timezone, execution history, and manual dispatch status in some views. Do not reconstruct them from private stores.
- Archive pauses future upkeep. Restore does not resume it. Do not resume a real user's jobs during verification.
