# Spaces sandbox spike: findings (t_4833de47)

**Verdict: SAFE FOR EVERYTHING EXCEPT ONE NETWORK CHANNEL. The plugin alone cannot close that channel.**
I ran agent-style Space code in a real Hermes desktop app (installed build 7f3ac61295, Electron 44.9.3) as a second isolated instance. The code could not reach the host page, Hermes APIs, cookies, storage, Node, the backend, or another Space's data. All HTTP, WebSocket, image, beacon, worker, form, popup and navigation exfiltration was blocked, and an attacker listener logged zero HTTP requests. **WebRTC is the exception.** A Space can open STUN/TURN connections to any host, and data placed in the TURN username reached my listener. The CSP `webrtc 'block'` directive is not enforced by this Chromium, whether it arrives in a meta tag or a response header. Fixing this needs a host-app change. Per the card I stopped there and did not work around it.

## Mechanism

```
Spaces page (plugin, renderer origin file://)
 └─ iframe A "shell": srcdoc, sandbox="allow-scripts" (opaque origin), CSP below
     └─ iframe B "space": srcdoc, sandbox="allow-scripts" (opaque origin), same CSP
         ├─ loader: project files -> frame-local blob: URLs, import map, entry HTML rendered
         └─ window.space  <-- one MessagePort -->  host bridge (bound to ONE space id)
```
- **Opaque origin** (no `allow-same-origin`) is the containment. This is the same posture as the app's own inline chat widgets (`inline-preview-directive.tsx`, `SandboxedFrame`).
- **CSP** (meta in srcdoc): `default-src 'none'; script-src 'unsafe-inline' 'unsafe-eval' blob:; style-src 'unsafe-inline' blob:; img/font/media-src blob: data:; worker-src blob:; connect-src 'none'; frame-src 'none'; form-action 'none'; base-uri 'none'; object-src 'none'`. The desktop renderer has no page CSP of its own, so the frame gets only this policy. The app's CSP and Electron settings did not get in the way.
- **Why two frames:** the shell's `frame-src 'none'` is the embedder policy for B, so B cannot navigate itself to an external URL, a `data:` or `blob:` document, or a meta refresh. B can't change that policy. Electron logged `ERR_BLOCKED_BY_CSP` for each attempt.
- **Bridge:** the host makes one `MessageChannel` per mount and transfers one port to the Space. The host fills in the Space id; frame messages never carry it. Versioned (`v: 1`). Every op maps to a grant, and an op without a grant is refused and counted in the toolbar ("2 denied").

## What the sandbox allows (measured in the isolated app)

| Capability | Result | Evidence |
|---|---|---|
| Multi-file project (HTML + CSS + 3 JS modules + SVG + 3 vendored libs, 9 files, ~215 KB) | works | 04-release-tracker.png |
| ES module relative imports, bare imports of vendored libs via import map | works (Preact 10.24.2, lightweight-charts 5.2.1 from local files, no CDN) | 06-trend-chart.png |
| CSS `url()` assets, `<link>` stylesheets | works (SVG logo rendered) | 04 |
| Client-side routing (hash) across 3 views | works | 05, 06 |
| Canvas charting library | works (7 canvases drawn) | 06 |
| In-app saves (checkbox, note) persist; reopen after renderer reload shows them | works | 08-reopened-trend.png |
| Agent tool write (`spaces_write_data`) appears in the running app | works, about 2 s (poll) | note field updated live |
| Refresh now (manual, Hermes-side handler) redraws chart | works | refresh_log `manual` entries |
| No-agent cron refresh (`every 1m`) redraws open app without interaction | works (9 -> 10 refreshes live) | 09-cron-live-update.png, `hermes cron runs` |
| Runtime console/errors/CSP violations reach the backend for the agent (`spaces_read_logs`) | works | logs table: "blocked by sandbox policy: connect-src ..." |
| Stale-write protection (base_rev) | implemented, not stress-tested | store.py |

## What it blocks (hostile Space, attacker listener on 127.0.0.1:47801 TCP/HTTP + 47802 UDP)

Blocked: `parent`/`top` document, `hermesDesktop` on parent/top/self, `top.location` read, `top.location` write, `document.cookie`, `localStorage`, `indexedDB`, `require`/`process`, fetch to attacker and to the backend (`/api/status`, another Space's data route), XHR, WebSocket, `<img>`, `sendBeacon`, EventSource, fetch from a Worker, fetch from a nested srcdoc frame, external child iframe, `window.open`, form POST, self-navigation to http/data/blob, meta refresh, `document.write` + fetch, `<a target=_blank|_top>`.
Bridge: `data.get`/`data.set` with `space:"other"` returned or wrote only the Space's own data. The other Space's secret was untouched. `../../other/secret` was stored as a literal key in the Space's own data. Ungranted ops `tool:terminal` and `agent.ask` were refused. Forged host messages (`hermes-inline-preview-intent`, `hermes-skill-pick`, `hermes-guest-loaded`, `hermes-preview-document`, `space-boot`) reached the host window and were ignored. The host URL did not change and no chat turn was created (sessions = 0).
Canary: **0 HTTP requests** across every run. Three probe lines read "ESCAPED" (beacon, child iframe, form) only because the probe could not observe the outcome. The CSP violation log and the canary show all three were blocked. Raw output: `evidence/hostile-results.txt`, `evidence/nav-results.txt`.

## The gap: WebRTC egress

- **STUN (UDP):** a `RTCPeerConnection` with `stun:127.0.0.1:47802` sent binding requests to the listener (`evidence/canary.log`).
- **TURN (UDP and TCP):** a Space put its own saved note into the TURN username. `evidence/turn.log`: `username=SPACEDATA-topsecret42`. TURN over TCP produced a TCP accept on 47801.
- **`webrtc 'block'`** is in the Space CSP, and the frame reports it, but it is not enforced. The same thing happened when the directive came as an HTTP header (`HEADERCSP-probe` reached the listener). Removing `RTCPeerConnection` inside the frame is not a fix either, because a nested srcdoc frame gets a fresh copy (tested: "webrtc in child srcdoc frame: created").
- **Blast radius:** a Space can leak only what it can read. That means its own saved data and what the user types into it. It can't use this channel to read the host, other Spaces, files or credentials. The realistic threat is prompt-injected source text making agent-written code exfiltrate that Space's contents.
- **Existing app widgets:** by code reading, the inline chat HTML widgets share the opaque-origin posture and set no CSP, so they likely have the same WebRTC channel plus open fetch. I did not test this.
- **Fix options (host side, all unverified, all need approval because they change Hermes):** (1) render Spaces in a dedicated Electron partition whose session routes through a dead proxy with `setWebRTCIPHandlingPolicy('disable_non_proxied_udp')`, so WebRTC has no path out; (2) a main-process `frame-created` hook that removes `RTCPeerConnection` in every frame of the Spaces partition; (3) wait for Chromium to enforce CSP `webrtc`. A plugin cannot do any of these.

## Network policy (decided)

Space code has **no direct network access**. Data enters only through the bridge, from Hermes-side handlers (refresh, cron, agent tools). Later, a grant like `fetch:<host>` would be served by a host-side proxy op, never by `connect-src`. This holds today for every channel except WebRTC (above).

## Architecture notes for the full-scope spec (from the scope correction)

- **Space = project:** manifest (`entry`, `imports`, `refresh`, `grants`) plus many files and binary assets. The spike stores the current revision only and bumps `code_rev`. The real store should keep content-addressed blobs and immutable revisions so restore never loses work.
- **Structured data:** per-Space key/value with per-key `rev` and `base_rev` conflict detection. Collections and queries come later. Writes are tagged by source (`space`, `tool`, `manual`, `cron`).
- **Bridge:** a versioned op set with a grant table. v1 grants are `data`, `refresh`, `logs`. Room is reserved for `agent.ask`, `tool:<name>` (GBrain, web, MCP), and `files.read` (user-granted). Each grant would be shown in the Space toolbar and toggled per Space, and stays denied until enabled (proven: ungranted ops refused).
- **Upkeep:** Space-defined handlers run on the Hermes side (the spike has `demo_tick`), triggered manually or by cron. On-open and event triggers fit the same `run_refresh(sid, trigger)` entry point.
- **Agent tools:** the spike has `spaces_list`, `spaces_read_data`, `spaces_write_data`, `spaces_read_logs`. The full set: create, read, write and delete files, manifest edit, revisions and restore, data, logs.
- **Size:** about 215 KB of vendored code loaded instantly. The whole project crosses `postMessage` once per code revision. Multi-MB assets should move to a host-served blob op. Not measured beyond this.

## Not proven

- A real model-driven chat turn (the isolated home has no credentials, and the card now stops before Step 2).
- Full Desktop restart reopen. Proven: renderer reload plus navigation away and back. The data lives in plugin_db on disk, so it is profile-scoped.
- Chromium logged non-fatal `Check failed: origin...IsValid()` lines in the browser process during the opaque-origin navigation probes, and the app kept running. That's worth upstream attention, but I didn't triage it.
- Stress: concurrent refresh with user edits, very large projects, many simultaneous Spaces.

## Isolation and cleanup

`HERMES_HOME=/Volumes/Expansion/Development/Build/spaces-t_4833de47/home`, separate `HERMES_DESKTOP_USER_DATA_DIR`, `HERMES_DESKTOP_ISOLATED_BACKEND=1`, runtime code read from the existing checkout via `HERMES_DESKTOP_HERMES_ROOT` (nothing written there). CDP on loopback 9339 for this instance only. Ife's app (pid 64328) and gateway (pid 62318) were checked before and after and never touched.
