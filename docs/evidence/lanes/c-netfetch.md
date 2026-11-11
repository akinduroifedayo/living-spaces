# c-netfetch lane report

Spaces need internet access through Hermes while their frame and private-network isolation stay intact. This lane adds the mediated `net.fetch` backend, default `net` grant, and host permission switch. The frame CSP stays unchanged.

**Verdict: ISSUES.** The lane's 32 Python and 7 JS tests pass. The final full suites pass 249/250 Python and 185/186 JS tests. Both remaining failures are frozen expectations in files outside this lane. Real Desktop qualification is written and compiled, not executed. Git refused both staging and committing with `Operation not permitted`; all changes remain unstaged in this worktree. Nothing was pushed.

## Scope and implementation

Base `7febcd8`, branch `forge/r1-c-netfetch`.

| File | Change |
|---|---|
| `src/living-spaces/living_spaces_core/net.py` | Stdlib HTTPS broker. Validates scheme, ports, all resolved A/AAAA destinations, legacy IPv4 literals and IPv6 transition forms. Connects a numeric socket to one vetted IP, sends the original hostname as SNI/Host, and uses the default certificate-verifying TLS context. Revalidates up to five redirects. Strips credential, proxy, Hermes and connection/framing request headers. Caps request bodies at `BRIDGE_BYTES` and response bodies at 5 MiB. Shares one 20-second network deadline across DNS, connect, TLS, headers, bodies and redirects. Returns text, JSON or base64 bytes. Audits only bounded host/status/byte fields. |
| `src/living-spaces/living_spaces_core/bridge.py` | Registers `net.fetch` and translates the bridge `as` argument to Python `as_`. Existing session/grant checks apply before and after dispatch. Network work runs outside SQLite transactions. |
| `src/living-spaces/living_spaces_core/grants.py` | Exact requested capability label/description, data-leaves-device flag and default grant. Existing revoke/request/host-decision flows apply. |
| `src/living-spaces/living_spaces_core/migrations.py` | Idempotent backfill for Spaces missing `net`. Existing granted/requested/denied/revoked rows remain untouched. Records the default grant in audit. |
| `src/living-spaces/living_spaces_core/db.py` | Runs that backfill inside the existing initialization transaction. Preserves schema version 1 and the existing DDL. |
| `src/desktop/sandbox/index.js` | Adds only `OP_GRANT['net.fetch'] = 'net'`. |
| `src/desktop/ui/permissions.jsx` | Internet access is first. Accessible On/Off switch uses the existing host grant route, disables during writes, and displays muted state copy. Requested access also offers host Approve/Deny. Exact requested WebRTC note appears only while Off. Other grant controls remain. |
| `tests/python/test_net.py` | 32 tests, fake resolver and connection seams, no real network. Includes the real stdlib HTTPResponse parser over BytesIO for truncated-response handling. |
| `tests/js/ui/net-permissions.test.mjs` | Seven React/JSDOM and operation-map cases. |
| `harness/qualify_net.py` | Forge-only real-frame qualification with native host mouse input and disposable fixture cleanup. |
| `LANE_REPORT.md` | This handoff. |

The Model the Domain principle informed the choice to keep destination policy and the pinned transport in one `net` module, using the existing capability registry and result shapes. No additional network library or grant system was introduced.

## Behavior and limits

- Only HTTPS on 443 or 8443 is admitted. Every resolved address must pass. Literal forms including `2130706433`, `0x7f.1`, shortened IPv4 and octal IPv4 are classified before any DNS query.
- Loopback, private, link-local, CGNAT, multicast, unspecified, reserved and documentation addresses are denied. IPv4-mapped, 6to4, standard NAT64 and local-use NAT64 forms cannot hide private targets. Teredo and reserved transition space are conservatively refused, including some public embedded destinations.
- No proxy environment, cookie jar, URL credentials or Hermes credentials are used. Caller-supplied `authorization`, `cookie`, `proxy-*`, `host`, and `x-hermes*` headers are removed. Framing and hop-by-hop headers are also removed so the caller cannot control HTTP framing.
- The socket never resolves the hostname a second time. TLS retains hostname verification, SNI and Host. The first vetted answer is used; there is no connection retry or automatic fallback that could replay a write.
- GET/HEAD/POST/PUT/PATCH/DELETE work. GET/HEAD bodies are invalid. Direct Python bodies may be text or bytes; the JSON bridge uses text. Text responses decode as UTF-8 with replacement; JSON must be JSON-safe, including finite numbers. No decompression is performed; the request asks for identity encoding.
- Redirects use standard method behavior: POST becomes GET on 301/302; 303 becomes GET except for HEAD; 307/308 preserve method/body. Redirect bodies are not consumed. Each target gets fresh validation and grant checks.
- DNS uses a daemon resolver thread because libc resolution has no timeout interface. The caller stops waiting at the shared deadline; a late DNS answer cannot initiate a connection. A stuck libc lookup may outlive the call. A deadline timer shuts down/closes the pinned transport to interrupt slow headers or body reads.
- Revocation prevents subsequent hops and result delivery. Already-sent external effects cannot be undone; an in-flight request may finish before its result is suppressed. Closed sessions suppress bridge results.
- Audit entries contain host, status and downloaded body byte count, with no URL query, path, headers or body. They use the existing audit store and redaction. No new audit-history retention policy was added.

## Red and green evidence

Logs are local ignored files under `.run/`. The commands below ran from this worktree; none drove Desktop or opened a listener.

| Change or check | Exact command | Observed result |
|---|---|---|
| Backend initial red | `~/.hermes/hermes-agent/venv/bin/python -m unittest tests.python.test_net` | 28 tests: 1 failure, 27 errors. Missing default grant, missing grant rows and absent net module. `.run/net-red.log`. |
| Backend first implementation | Same command | 27 pass, 1 failure in the test helper: it incorrectly expected an empty connection history after an earlier successful fetch. `.run/net-green.log` was subsequently replaced by the successful run. |
| Backend initial green | Same command | 28/28 pass after correcting the helper to compare the connection count before/after the blocked request. `.run/net-green.log`. |
| UI/host-map red | `node --test tests/js/ui/net-*.test.mjs` | 7 tests: 1 pass, 6 failures. Existing other-grant control case passed; new switch/disclosure/route/map cases failed. `.run/net-ui-red.log`. |
| UI/host-map green | Same command | 7/7 pass. `.run/net-ui-green.log`. |
| Truncated-response regression red | `~/.hermes/hermes-agent/venv/bin/python -m unittest tests.python.test_net` | 32 tests: 31 pass, 1 failure. Advertised 10 bytes with only 5 delivered incorrectly succeeded. `.run/net-review-red.log`. |
| Final backend focused green | Same command | 32/32 pass after rejecting an incomplete response. `.run/net-review-green.log`. |
| Final UI focused green | `node --import ./tests/js/sandbox/env.mjs --test tests/js/ui/net-*.test.mjs` | 7/7 pass. `.run/net-ui-final.log`. |
| Initial stock Python | `~/.hermes/hermes-agent/venv/bin/python -m unittest discover -s tests/python -t .` | 246 tests: 244 pass, 2 failures. Stale default-grant assertion and an unnecessary schema-version bump. `.run/net-python-suite.log`. |
| Schema version preserved | Same command | 246 tests: 245 pass, 1 failure. Only stale default-grant assertion remained. `.run/net-python-suite-final.log`. |
| Final stock Python | Same command | 250 tests: 249 pass, 1 failure. `.run/net-python-final.log`. |
| Literal stock JS invocation | `node --test tests/js/sandbox/*.test.mjs tests/js/ui/*.test.mjs tests/js/reference/*.test.mjs` | 122 reported tests: 116 pass, 6 failures. Three modules could not resolve `preact`; renderer metafile was absent; old grant map assertion and one host timing assertion failed. `.run/net-js-suite.log`. |
| Prepared stock JS | `node --import ./tests/js/sandbox/env.mjs --experimental-vm-modules --test tests/js/sandbox/*.test.mjs tests/js/ui/*.test.mjs tests/js/reference/*.test.mjs` | 156 tests: 154 pass, 2 failures. Old grant map assertion and host timing assertion. `.run/net-js-suite-ready.log`. |
| Final serialized JS, including existing UI index | `node --import ./tests/js/sandbox/env.mjs --experimental-vm-modules --test --test-concurrency=1 tests/js/sandbox/*.test.mjs tests/js/ui/*.test.mjs tests/js/ui/index.js tests/js/reference/*.test.mjs` | 186 tests: 185 pass, 1 failure. Only old grant map assertion. `.run/net-js-final.log`. |

No skips or cancellations were reported in the final suites. The parallel host timing failure was `mount binds boot to host session, forwards replies and emits versioned events`, expecting one call after a fixed 20 ms wait but observing zero. That unchanged test passed in the final serialized run. It was not edited or claimed fixed.

Build/check commands, all successful:

```sh
esbuild src/desktop/plugin.src.js --bundle --format=esm --jsx=automatic --external:@hermes/plugin-sdk --external:react --external:react/jsx-runtime --outfile=.run/package/plugin.js --metafile=.run/package/desktop-metafile.json
node scripts/check-renderer-graph.mjs .run/package/desktop-metafile.json
~/.hermes/hermes-agent/venv/bin/python -m py_compile harness/qualify_net.py
~/.hermes/hermes-agent/venv/bin/python -m py_compile src/living-spaces/living_spaces_core/net.py src/living-spaces/living_spaces_core/bridge.py src/living-spaces/living_spaces_core/grants.py src/living-spaces/living_spaces_core/migrations.py src/living-spaces/living_spaces_core/db.py harness/qualify_net.py
git diff --check
```

The renderer graph check reported `Renderer graph excludes guest code and guest HTML`. Only a local `.run/package/plugin.js` was built. The committed generated plugin and guest HTML were not changed. No package was installed.

## Integration issues

1. `tests/python/test_core_store.py:434` expects exactly `{"data":"granted","logs":"granted"}`. The observed extra `net: granted` is required by frozen decision 3. Forge should update that owned expectation to include `net`.
2. `tests/js/sandbox/host.test.mjs:28` asserts the old exact operation map. Forge should add `'net.fetch': 'net'` to that expectation.
3. `src/guest/loader.mjs` and the generated guest document on this branch do not expose `space.net.fetch`. This is c-guest's explicit ownership. Integrate that lane and rebuild once before running the harness.
4. The current registered tools in `src/living-spaces/__init__.py` do not include a general capability-request tool. Core `grants.request(..., 'net', ...)` and subsequent host Approve are implemented and tested. If agent re-request must be available through a normal plugin tool, Forge/c-tools must expose that route. This lane did not edit tool registration or manifests.
5. `src/living-spaces/__init__.py` still emits its general network-blocked warning. Forge/c-tools should distinguish direct guest networking from mediated `space.net.fetch` in that copy.
6. No real TLS, DNS, public retrieval, guest integration, native switch, visual/keyboard, or isolation acceptance is claimed. Unit transport seams verify numeric connection and hostname TLS setup, not a live handshake.
7. Staging and committing are unavailable in this sandbox. `git add ...` and `git commit -m 'Add permissioned HTTPS fetch with pinned public destinations'` both failed with `fatal: Unable to create '/Volumes/Expansion/Development/Projects/living-spaces/.git/worktrees/c-netfetch/index.lock': Operation not permitted`. No commit was created, and the changes could not be left staged. Forge must stage and commit them outside this sandbox.

## Contract issues and spec gaps

- The task's frozen decision 3 adds a default-granted external capability to both new and existing Spaces. SPEC §2 still says creation grants no outside capabilities and external capabilities need consent. Apply an explicit decision-3 amendment; do not infer that the old default-off acceptance wording still governs mediated fetching.
- CONTRACTS §§4, 5 and 7 omit `net` and `net.fetch`, and §10 lists a 1 MiB bridge message limit without distinguishing requests from larger responses. Add the frozen input/result shapes, 1 MiB request-envelope/body limit, 5 MiB downloaded-response-body limit, 20-second network deadline and the existing error-code mappings. Base64 responses can exceed 5 MiB on the wire.
- CONTRACTS §12 says the permissions UI renders the exact old `WEBRTC_NOTE` export. The task now requires the exact new Off-only note. This lane renders the requested new text locally in Permissions and leaves the old exported string intact for other consumers/tests. Forge should reconcile that documented single-source contract.
- Broad direct networking and arbitrary remote embeds remain unavailable. Mediated retrieval satisfies the commissioned option (b), not those broader interpretations of internet access. Keep acceptance scoped accordingly while retaining the existing isolation checks.
- Permission revocation is not retrospective cancellation of a completed external POST/PUT/PATCH/DELETE. The existing spec's limitation still applies. Re-request requires a host decision; code changes do not silently restore a revoked `net` row.

## Forge harness command

Compile passed. Execution was deliberately not attempted under this lane's hard boundary. After integrating c-guest, rebuilding the package, and attaching the shared isolated app to that integrated code, Forge should run this serially. Set the variable to the actual isolated gateway port, not the CDP port:

```sh
~/.hermes/hermes-agent/venv/bin/python harness/qualify_net.py --gateway-port "${LS_GATEWAY_PORT:?Set the isolated gateway port}" --public-url https://example.com/ --lan-url https://192.168.1.1/
```

`--run-root` and `LS_CDP_PORT` allow the existing isolated harness setup to be selected. The run root defaults to the existing external `living-spaces-r1` directory. The harness refuses a live Hermes home, requires an existing isolated database, creates only its own public fixture, records `evidence/net/net.json` and two screenshots, and deletes its fixture afterward. It does not start or stop any app, gateway or listener. It checks public HTTPS, blocked gateway/loopback/LAN targets, unchanged ordinary-fetch blocking, the On/Off disclosure, revocation and host reapproval.

No full Hermes plugin validator was invoked because Desktop admission can require prohibited app-driving work. Forge owns final package validation and real-app acceptance.

GBrain tool discovery exposed no callable GBrain context-pack tool. No GBrain history informed the implementation and no knowledge writeback was made.
