# Premium regeneration blocked on the ordinary chat route

The goal is to regenerate Sky Window, Research Desk, and Pair Play from the three supplied prompts, using the updated design guidance inside the real host. This attempt produced a provider failure, not a regenerated Space.

## Observed result

At about 06:52 CT on November 11, 2026, the exact Sky Window prompt was submitted once through the existing Desktop chat composer. The configured Sonnet 5.5 route exhausted its built-in retries. The host displayed these messages.

- "Claude Subscription DirectSDK (Experimental) is busy right now"
- "You've hit Claude Subscription DirectSDK (Experimental)'s rate limit. Wait a moment, then retry."
- "Your request was not processed. Send it again if you still want me to carry it out."

No tool call or skill load occurred after submission. The installed skill's disk hash matches the handoff, but this attempt cannot prove loaded guidance. No regenerated HTML, imagery, weather, research feed, game, or functional result was produced. Research Desk and Pair Play were not submitted after the shared provider route failed.

Sky Window remains revision 4. Its records, revisions, grants, and Space row are identical before and after this attempt. Research Desk remains revision 8 and Pair Play remains revision 5. These are existing artifacts, not premium regeneration results.

## Environment and evidence

The repository is `/Volumes/Expansion/Development/Projects/living-spaces`, branch `forge/r1-contracts`, starting at `72b626aba71067166e737feb95e9585df5262816`. The existing isolated host uses CDP `http://127.0.0.1:9341` and `HERMES_HOME=/Volumes/Expansion/Development/Build/living-spaces-r1/home`. The installed `build-space` skill has SHA-256 `50851b36d8918428e882b9a0e1a132d7e4a7b9239d9a4447f2ab28879f1dde96`.

The files in this directory record the exact prompt, chat session, timestamps, post-submission transcript, host error, screenshot, before and after store rows, and a hash-bound receipt. `blocker-receipt.json` contains five executed checks. All five passed. Those checks prove rejection and preservation, not application functionality.

`sky-window-provider-blocked.png` is a real host CDP screenshot at a 1690 by 858 viewport. The bottom 32 pixels are excluded at capture to omit the account footer. The visible prompt and provider failure are unchanged. `sky-window-host-message.txt` omits the footer too. The before and after records contain only the public city centres Chicago, Lisbon, and Tokyo. No external live data was fetched during this attempt.

The read-only capture script is retained as `capture-blocker.py`. It uses the existing `harness/cdp.py` and the already available Hermes runtime `websockets` module. The normal prompt was sent through the existing `harness/chat_turn.py` using native CDP input events, not a tool API or source injection. Its observer expected a terminal `finish_reason`, but the rejected assistant row has none. After independently recording the terminal rejection, only the local observer process was terminated. No model turn was forcibly canceled.

## Resume boundary

This card remains incomplete. The normal configured provider must become available, or the owner must explicitly authorize a route change. Do not silently force a provider or restart the gateway. The task releases its exclusive chat and store window early after this failed attempt. Reacquire ownership before another submission. The prior grant ends at 08:00 CT.

On authorized resume, inspect the existing Sky Window submission before retrying. It was rejected without processing. Then submit each outstanding prompt through normal chat, capture loaded skill bodies from actual tool traces, inspect generated revisions, and exercise live functional and mobile states. Miro's downstream before-and-after review and one verified iteration remain pending. Reference showcase screenshots are not substitutes for these results.

No product code, host implementation, permissions, or provider configuration changed. No deployment or production verification occurred. The existing backend's in-memory code remains unattested because no restart was performed.
