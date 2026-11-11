# Direct frame internet is deferred

## Owner decision

On 2026-11-11 at 10:52 CT, Ife deferred direct frame internet to the next release, relayed by Bjorn on task `t_d40eb81d`. R1-13 is **deferred by owner decision, disclosed**, not passed. Partition qualification stopped. No partition host is integrated into release 1.

Release 1 uses mediated public HTTPS retrieval. A Space supplies its own API credentials. Hermes credentials are not supplied. Images use mediated byte retrieval and caller-owned Blob URLs. Live embeds, streams, WebSockets, and libraries loaded from the web at runtime are not supported by this release.

## Observed mechanism

The installed Desktop attaches remote-request headers through its default-session `onBeforeSendHeaders` hook and `applyRemoteRequestHeaders`, using the connection registry. An opaque iframe does not by itself separate that network session.

A bounded real-Desktop probe added a public synthetic registry marker and removed it after observation. Matching requests from an iframe-shaped substitute received the marker, including the tested redirect paths. A raw webview with a separate nonpersistent partition did not receive it in the same HTTP-loopback matrix. Creating that partition required no Desktop source or installed-artifact change.

The result identifies a possible credential-isolation mechanism. It does not qualify a replacement Space host. The existing plugin bridge and mount lifecycle cannot simply be assumed to work in that partition.

## Evidence and limits

The parent executed the author-only probe. Its result contains 48 observed cases, all matching their expectations, and 9 successful cleanup checks. A separate cleanup readback has 7 successful checks. These counts describe different checks and are not added together as an acceptance total.

Retained evidence is under the release build directory:

- `run/seats/partition-positive-r4/result-83803275634049179473d3cc1b7df8b9.json` records the requests and bounded result.
- `run/seats/partition-positive-r4/parent-cleanup-verification.json` records the independent cleanup readback.
- Probe SHA-256 is `06b19e47c2fc12f23af5c070ae29dc0a248209fd4ebfc5d517ffc6a34a00bd72`.

The original result is `PARTIAL` and explicitly records `r1_13_acceptance: false`. The native preview widget was not mounted. The fixture was authored, not created through a model transcript. No general isolation or zero-egress claim follows from this matrix.

## First qualification item for the next release

Before integrating a partition host, qualify these behaviors against the installed Desktop:

1. Public HTTPS requests and redirects, including real web images and fonts.
2. WSS and other live connections without ambient Desktop credentials.
3. Descendant frames, navigation, workers, and replacement documents.
4. Internet revocation, including in-flight responses and late delivery.
5. A replacement bridge with authenticated ownership, session invalidation, profile switching, and cleanup.
6. The native widget comparison and real chat-built Space path.

The current findings justify investigating the partition approach without a Desktop change. They do not establish that the complete feature needs no Desktop change. Release 1 retains its mediated path and disclosed WebRTC exception.
