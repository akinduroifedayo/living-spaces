# R1-01 hosting qualification

Status is **executable qualification prepared; real Desktop run pending**. This lane did not launch Desktop, a gateway, Chrome, or any network listener. Unit tests and source inspection do not pass R1-01. Forge must run the harness serially and attach its receipts before changing the acceptance ledger.

## Integrated containment mechanism

The reviewed implementation is `src/guest/document.mjs`, `src/guest/loader.mjs`, and `src/desktop/sandbox/index.js`, including amendment A3 of the frozen contracts.

```text
Desktop renderer
  iframe shell, srcdoc, sandbox="allow-scripts", opaque origin
    iframe Space, srcdoc, sandbox="allow-scripts", opaque origin
      local project blobs + import map + window.space
```

Neither frame has `allow-same-origin`, popup, form, or top-navigation permission. The shell and inner document carry the same fixed CSP. The shell owns the inner frame's navigation policy, so generated code cannot remove that outer policy. Both frames are necessary to cover inner self-navigation.

```text
default-src 'none'; script-src 'unsafe-inline' 'unsafe-eval' blob:; style-src 'unsafe-inline' blob:; img-src blob: data:; font-src blob: data:; media-src blob: data:; worker-src blob:; connect-src 'none'; frame-src 'none'; form-action 'none'; base-uri 'none'; object-src 'none'; manifest-src 'none'; webrtc 'block'
```

The backend supplies the installed, deterministic `space-host.html` in `sandbox: {format: 1, shell_srcdoc}`. The renderer parses that envelope before mounting. It sends only project fields and grants to the shell. Each mount creates a MessageChannel, whose guest port passes through the shell into the inner frame. Both boot listeners require their immediate parent's window as the source and remove themselves after accepting one boot. Subsequent API requests use the port, not global `message` events. The host checks bridge version, shape, size, operation and grants. Its REST closure supplies the bound Space and session; neither is selected by an app request. A3 keeps the session identifier out of the guest. Closure and reload invalidate the channel.

The loader creates frame-local blobs, rewrites local references, and builds import mappings. `runtime/vendor/preact.mjs` is copied by core into the fixture's `vendor/preact.mjs`. The test verifies those bytes match. No production sandbox policy or producer was changed in this lane. Source review did not establish a new containment defect; that is not proof of containment.

## Probe matrix and expected results

`harness/qualify_hosting.py` imports `guest_realm.guest`, `cdp.Session` and target helpers, plus `qualify_schedule`'s core, visibility, polling and page helpers. App probes execute in the main world of the actual Space, through its real `window.space` API where applicable. No mock browser qualifies containment.

| Probe | Required observation |
|---|---|
| Listener controls | Harness-origin HTTP request, raw TCP/WebSocket-shaped handshake, and UDP datagram are recorded. HTTP accepts and raw TCP accepts count even without valid HTTP. Threads remain alive through the observation window. |
| Positive multi-file app | Overview → Details → Overview; local ES module returns its label; packaged Preact renders both views; CSS custom property is applied; SVG decodes at its declared width. |
| Positive network capture | CDP `Network` enabled on automatically attached frame targets before resuming them; at least one blob request observed; no resource request with a non-blob/data URL; no listener hits. CDP errors fail qualification. |
| `fetch`, XHR, `sendBeacon`, EventSource, WebSocket | Each operation attempted and recorded; zero ordinary listener hits, regardless of whether the API throws or returns. |
| Image, stylesheet link, script `src`, CSS `url()`, `@import`, font face | Each inserted and given time to load; font has actual text using it; zero listener hits. |
| Fresh nested `srcdoc` | Child execution handshake and all eleven HTTP/WebSocket/asset probes must complete; zero listener hits. |
| Fresh nested blob document | Same probes embedded in a fresh blob document. Either execution reports all probes or an observed `frame-src` violation establishes that loading the document was blocked. A bare timeout does not pass. Zero listener hits. |
| Worker and SharedWorker fetch | Fresh blob worker program attempts fetch. A blocked-fetch reply or constructor rejection passes; unexplained worker error or timeout fails. Zero listener hits. |
| `location`, `top.location`, `window.open`, `<a target=_top>`, meta refresh, POST form | Each runs from a fresh mount; host URL and page-target set unchanged, bridge remains usable, zero listener hits. |
| Additional data/blob self-navigation | Attempts contain a listener fetch in their destination document; same zero-hit and host-integrity checks. These also help reproduce the historical origin-check diagnostic. |
| `parent.document`, `top.document`, cookies, localStorage, IndexedDB database enumeration, CacheStorage keys | Throws or returns no value/data. A nonempty privileged read fails. |
| Self/parent/top `hermesDesktop`, backend URL through `top.hermesDesktop.getBackendUrl`, `top.location`, Node `require`/`process` | Throws or returns nothing. Returned values are classified without recording privileged contents. |
| Forged `space` in `window.space.query` | Try every existing collection in Research Desk and Pair Play. Each protected Space must have actual records as a positive control. Empty fixture results or typed rejection only; protected snapshots unchanged. |
| Raw envelopes to `parent` | Spoofed tool/agent/prototype operation names, forged session/Space, wrong version, over-1-MB payload, fake boot and host-intent messages. Entire canonical SQLite snapshot unchanged across this quiet interval; legitimate bridge still works. |
| Preservation and cleanup | All SQL values associated with Research Desk and Pair Play, including referenced blob bytes, compare byte-for-byte before/after. Disposable `hosting-probe` is deleted, including on failure. |
| WebRTC STUN | Record RTCPeerConnection construction/offer outcome and whether UDP arrived at the local STUN port. **No assertion that WebRTC is blocked.** |

Each listener record includes phase, time and transport. The full-run zero-ordinary-hit assertion also catches delayed requests crossing probe phases. UDP is reported separately. API return values alone never establish egress or containment. A forbidden read, unexpected traffic, incomplete probe, CDP instrumentation error, cleanup failure, or preservation mismatch makes the process exit nonzero.

Canonical snapshots compare deterministic bytes of SQL values, including original stored JSON strings and BLOB bytes. They do not compare physical SQLite/WAL page layouts, which can change without changing data. Snapshot bytes remain in memory; receipts store SHA-256 digests so active session identifiers are not written into evidence. No protected Space is mounted, mutated or used as fixture source. The whole-database spoof interval deliberately fails on any concurrent writer; Forge must run serially in a quiet isolated instance.

## WebRTC exception, verbatim from spec §2

> **Known limit — not a release-blocking closure requirement:** Forge demonstrated WebRTC STUN/TURN egress carrying a Space's own saved note to a listener. Chromium ignored the proposed WebRTC CSP restriction; frame-level removal was bypassable through a nested frame. This does not show access to host credentials or another Space, but it does allow disclosure of data that the malicious Space can read. Zero HTTP requests is not zero network egress. [S3, S5]

The qualification makes a fresh STUN observation. It does not requalify historical TURN username exfiltration, claim closure if no packet arrives, or require a plugin workaround or host change. A five-second ICE observation plus a two-second settling interval is recorded; absence during that window is only an observation for that build and environment.

## Chromium origin-check diagnosis

Historical inputs read were the spike's `FINDINGS.md`, `tools/canary.py`, `tools/turn_canary.py`, `tools/cdp.py`, and `evidence/{app.log,hostile-results.txt,nav-results.txt}` under `Build/spaces-t_4833de47`. The repository copy at `docs/evidence/spikes/sandbox-spike-FINDINGS.md` is historical too.

**Known from retained evidence.** `app.log` has six browser-process messages at `12:20:04.123441` through `12:20:04.125069`, naming `content/browser/site_info.cc:925` and the failed expression `origin.GetTupleOrPrecursorTupleIfOpaque().IsValid()`. They follow self-HTTP-navigation CSP failures and immediately precede data-URL, blob-URL and meta-refresh `ERR_BLOCKED_BY_CSP` messages. The same browser process continues logging. `nav-results.txt` reports unchanged host URL for all eight navigation cases. It has no timestamp-to-probe mapping or stack trace, so it does not identify which exact navigation emitted each line. The app's later shutdown error and listener-count warning are separate messages, not evidence that this origin check crashed it.

**Known from upstream source.** Chromium's `SiteInfo::GetAgentClusterKeyForURL` handles opaque sandboxed data-URL frames by deriving process/site isolation information from a precursor origin. Its `DUMP_WILL_BE_CHECK` tests whether that tuple is valid before using it. This is browser-side site selection, not the Space loader or a JavaScript exception. See [Chromium site_info.cc](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/content/browser/site_info.cc). Chromium documents this macro as nonfatal in official builds, while developer/DCHECK builds can crash. That explains how a “Check failed” message can coexist with continued execution. See [Chromium check.h](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/base/check.h).

**Inference, not reproduced fact.** The data-navigation probe likely reached a site-selection path with an opaque origin lacking a valid precursor tuple. Its location beside the data-URL rejection and the matching upstream assertion support that explanation. The exact Electron 44.9.3 Chromium revision, build flags and call stack were not bound to the spike binary in this lane. Current upstream source is not proof of the exact historical implementation. No specific Chromium fix, regression version, exploitable bypass, or harmlessness across builds is established.

**Remaining runtime work.** The new harness records browser version, probe timings, CDP network events and matching origin-check lines appended to the isolated app logs during navigation. It retains only the specific diagnostic, not complete application logs. Forge should correlate any recurrence with the data/blob probe, listener receipts and bridge survival. If the current build crashes or emits the check on another path, retain the build revision and stack before considering a separate host investigation. Do not add `allow-same-origin` or relax CSP to silence the diagnostic.

## Forge execution and receipts

Install the reviewed candidate through the existing isolated-app process, then leave its Spaces index open with no Space frame or open protected sessions. Keep scheduled writers and other qualification lanes out of the interval without modifying their schedules in this harness. A pre-existing `hosting-probe` causes refusal, never overwrite or deletion. The helpers currently bind the isolated build directory `Build/living-spaces-r1`; they do not honor an alternate run root here. The harness refuses a mismatched database override and verifies the mounted guest document matches the worktree artifact.

From the integrated worktree, using the existing Hermes Python environment:

```sh
LS_CDP_PORT=9341 ~/.hermes/hermes-agent/venv/bin/python harness/qualify_hosting.py
```

The script starts and closes only its own ephemeral IPv4 loopback listeners. It does not start, stop or restart Desktop, gateways or cron. Receipts go under the isolated build's `evidence/hosting/<timestamp>/`:

- `hosting.json` records verdict, every assertion, probe observations, browser version, WebRTC observation, errors and cleanup.
- `listeners.json` records inbound HTTP/TCP/UDP activity, including the labeled harness-origin controls.
- `network.json` records frame/worker target Network events and attachment errors; renderer API request headers are excluded.
- Protected-Space and spoof-interval `*-before.sha256` / `*-after.sha256` pairs bind the in-memory byte comparisons.

Offline checks exercise generated nested-frame and worker probe programs with fakes, plus syntax and fixture admission. These prove harness construction only. No runtime pass count exists yet.

## Contract issues and spec gaps

No change to the frozen contract is requested. A3 is the authority for the session-free guest envelope. The advertised `webrtc 'block'` directive remains an unenforced declaration, explicitly qualified by the spec.

The spec does not define an observation duration or require a nested blob document to execute when policy blocks its load. Proposed qualification interpretation is to require execution of the fresh srcdoc probes, and accept explicit CSP rejection of the blob document while recording that its contained probes did not run. Timeouts alone fail. This is narrower than claiming all nested realms were executed and is visible in the receipt.

R1-01 remains pending until Forge runs this harness successfully on the integrated candidate and reviews the origin-check and WebRTC observations. No result from the spike or these unit tests promotes it.
