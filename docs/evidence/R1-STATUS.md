# Release 1 — current status

Updated November 11, 2026, against public release `4f0b41918c3370c359b808674e33a90a1068031d`. Its plugin files are identical to the installed `8134be424b5a5756a89278e729ab537475f45155` build used for the Pocket Garden demonstration.

**The core loop is proven in the installed Desktop release:** ordinary chat built Pocket Garden; entries saved inside the Space survived leaving and reopening; a chat-requested Light view preserved all four plant records. An image loaded by URL through the mediated Blob helper. One in-Space bot-button click made exactly one native request, and its answer appeared in chat and the Space without losing saved plant data.

| Area | Observed result |
|---|---|
| Ordinary-chat demo apps | Sky Window, Research Desk and Pair Play were rebuilt through ordinary Desktop chat. Independent functional checks passed 9/9, 10/10 and 8/8 respectively. |
| Scheduled upkeep | A native Hermes cron run completed in 57 seconds and wrote a generated brief into Research Desk while it was closed. Reopening displayed the brief. All 47 existing user-data payloads were byte-identical; the other 46 complete records were unchanged. |
| Design | The narrow-width overflow repair passed independent design review on November 11 at 12:59 PM CT. |
| Packaging | At `4f0b419`, `hermes plugins validate src/living-spaces --install-deps` passed all 16 checks, with catalog warnings for rules 8 and 9. Public subdirectory installation and enablement succeeded. |
| Catalog | [Catalog PR #153809](https://github.com/NousResearch/hermes-agent/pull/153809) is open. |

Mediated networking supports public HTTPS with DNS validation and redirect re-checks, blocks private and local destinations, and enforces 5 MiB response and 20-second request caps. Hermes credentials are never attached.

The demo-app checks are recorded in the [ordinary-chat regeneration report](../design/premium-pass/regeneration/astra-run/README.md). Pocket Garden, native-cron and packaging results were checked against the release's retained recording, execution, preservation and validator receipts. This page summarizes those observed results; earlier build logs remain in Git history.
