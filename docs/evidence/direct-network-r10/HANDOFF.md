# Direct HTTPS candidate handoff

## Goal and verdict

Allow ordinary HTTPS web code in Spaces without attaching Hermes credentials. Keep Internet Off meaningful and preserve the existing bridge and saved Spaces.

BLOCKED. The real preliminary catalog validator rejects the raw webview required by this candidate. No promotion SHA is available. Do not disguise the call or weaken the scan.

## Source

- Worktree `/Volumes/Expansion/Development/Build/living-spaces-direct-network-r10`.
- Branch `forge/direct-network-r10`.
- Base `8134be424b5a5756a89278e729ab537475f45155`.
- This candidate is archived on `forge/direct-network-r10` for the next release only. It is validator-red by host policy. The preservation commit does not qualify or promote it. No main change, package installation or cutover was performed for this candidate.
- Existing isolated installed package remains the previous cutover's 3ace854 candidate. This run does not qualify that package or change the entry pin of 8134be4.

## Verified evidence

`gate-r10b/receipt.json` records successful sandbox and renderer builds, renderer graph check, 395 Python tests, 125 grouped Node tests, 243 standalone Node tests and 19 reference tests. These qualify the dirty source tree, not an exact commit. The earlier failed test-home run is preserved in `gate-r10/`. Two format1 document expectations were updated to assert all three trusted format2 assets. The test home uses a symlink to existing Hermes code/dependencies, not another profile's credentials.

`mount-product-corrected.json` records actual candidate mounts with real isolated backend sessions and saved data. Pocket Garden revision11 rendered four plants. Research Desk revision20 rendered47 records. Sky Window revision13 rendered three saved cities and completed three mediated fetches. Pair Play revision11 rendered its saved round. The per-Space screenshots are partial cropped views, not complete design qualification.

The first inspector incorrectly required an inline child frame. The correction records the owned webview target and separate OOPIF target with the matching parentId. Four mounts passed after that correction. It did not perform a model turn or a write test.

`cleanup-readback.json` independently confirms zero disposable mount elements, zero probe globals, zero webviews and only the main page target. The application is on `#/spaces` with zero dialogs. Session DELETE requests completed during each probe cleanup. No cron jobs were created.

## Validator blocker

`validator-preliminary.json` records exit1 and15/16 checks. Security scan passes. The desktop surface check fails with `preview guest reach (desktop/plugin.js:1291)`.

That line is `document.createElement("webview")`. The installed `hermes_cli/plugin_validate_desktop.py` explicitly rejects raw webview creation. The SDK documentation at `website/docs/developer-guide/desktop-plugin-sdk.md:1038–1093` prohibits raw webviews and exposes SandboxedFrame without a partition selector. The documented preview scripting door acts on the focused preview Browser and is not a documented disposable credential-separated partition API.

A supported host partition API or an upstream API/policy decision is required. No host modification is commissioned here. A human release override would not turn the failed validator into a pass.

The `hermes plugins validate` launcher unexpectedly bootstrapped runtime dependencies in the fresh isolated `validator-home` before running, despite omission of `--install-deps`. Preserve this disclosure. No repeat, live-profile change or deletion was attempted.

## Unproven gates

- HTTPS credential separation matrix with positive controls on the candidate.
- Internet Off teardown and direct-request blocking through the actual UI lifecycle.
- Candidate save and in-Space bot completion.
- HTTPS script/style/font/media loading through the candidate.
- Exact-SHA validator and stock gate.
- Independent review and installed-package smoke.

The old48-case matrix is HTTP-loopback differential evidence, not HTTPS acceptance. A bounded HTTPS loopback certificate-exception proposal was posted in comment2393, but the subsequent validator blocker supersedes proceeding with that test. No certificate exception or dummy registry entry was created in this run.

WebSockets and descendant frames remain denied by the candidate CSP. The accepted WebRTC limitation remains disclosed; the `webrtc 'block'` directive alone is not treated as a browser-enforced guarantee.

## Resume condition

Resolve the supported host API and catalog compliance route first. Preserve the candidate and existing receipts. Do not rebuild Release1, create replacement implementation swarms, change main, or open another catalog PR. Comments2392 and2394 contain the latest native pass and release blocker respectively.

## Owner disposition

The 2026-11-11 submission remains pinned to `8134be424b5a5756a89278e729ab537475f45155`. The direct-network lane is stopped for today. No TLS exception, additional probe, workaround, or scope change is authorized. This branch preserves incomplete work, not a release candidate. Raw preliminary validator output is retained beside this handoff. Other receipts remain in the original local evidence directory named above.
