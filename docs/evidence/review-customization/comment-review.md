# Comment Sicko report

Ife wants normal Hermes chat to build safe durable Living Spaces apps. This is the bounded comment audit of the frozen repair source before fresh review. It is not implementation review or final acceptance.

**Result.** 11 entries inventoried, comprising eight Python docstrings and three Python line comments. Recommend deleting seven entries, keeping four, and carrying two `MUST KILL` naming targets to the parent. All entries occupy one physical line each. Actual deletions are zero. The only file written by this seat is `.run/REPORT.md`.

**Binding.** Workspace `/Volumes/Expansion/Development/Projects/living-spaces-wt/c-comment-repairs`. Branch `forge/r1-c-comment-repairs`. HEAD and baseline commit `fd489dd67e81f1fe373f07c869421ed04cfb8fbf`. Git status was clean before review. The requested seat is Astra high fast; this report does not independently attest backend model, effort, service tier, or fallback metadata. No model was launched or switched, and no nested agent was used.

**Checks and coverage.** Read `pins.json` before consuming the shards. Read all 32 complete shard bodies, including `required-001.txt`, the exact agent definition. Initially truncated aggregate reads were reread in bounded batches. Verified every shard SHA-256, every original source SHA-256, every character slice, and contiguous coverage from character zero to EOF. All ten scoped source hashes also match `.run/baseline.json`. All 392 manifest files match their frozen hashes, and the manifest path set exactly matches tracked plus nonignored untracked files. No required source or shard is missing. Non-scoped files were hashed for integrity only, not comment-reviewed.

The requested model policy, Hermes poteto-mode skill, its `references/hermes-tools.md`, and `/Users/ifedayoakinduro/.codex/skills/no-comments/SKILL.md` were read. The how skill and its explainer reference were read for the narrow traces below; its nested explainer step was superseded by the explicit no-nested-models instruction. The supplied bounded Comment Sicko definition governs this seat; the parent owns acceptance and edits. No additional repository `AGENTS.md` was found in the inspected ancestor paths or under `src`.

The local memory registry had no relevant hits. A bounded GBrain context pack returned no Living Spaces entity card or relevant project evidence; unrelated returned facts were not used. It also reported nine unembedded chunks, so that result is not evidence that historical context is absent. No brain writes or indexing were performed. The frozen source remains the authority here.

**Coverage by file.** Each row covers the complete file, including unchanged lines within that file. Counts include docstrings. Runtime strings are excluded.

| File | Shards | Lines | Inventory | Delete | Keep |
| --- | --- | ---: | ---: | ---: | ---: |
| `src/desktop/ui/permissions.jsx` | required-002.txt through required-004.txt | 84 | 0 | 0 | 0 |
| `src/desktop/ui/schedule.jsx` | required-005.txt | 36 | 0 | 0 | 0 |
| `src/living-spaces/__init__.py` | required-006.txt through required-012.txt | 513 | 4 | 4 | 0 |
| `src/living-spaces/dashboard/plugin_api.py` | required-013.txt through required-015.txt | 263 | 1 | 1 | 0 |
| `src/living-spaces/living_spaces_core/bridge.py` | required-016.txt | 95 | 1 | 0 | 1 |
| `src/living-spaces/living_spaces_core/feeds.py` | required-017.txt through required-018.txt | 136 | 1 | 0 | 1 |
| `src/living-spaces/living_spaces_core/grants.py` | required-019.txt through required-021.txt | 209 | 1 | 1 | 0 |
| `src/living-spaces/living_spaces_core/net.py` | required-022.txt through required-024.txt | 285 | 2 | 0 | 2 |
| `src/living-spaces/living_spaces_core/runs.py` | required-025.txt through required-028.txt | 330 | 0 | 0 | 0 |
| `src/living-spaces/living_spaces_core/schedules.py` | required-029.txt through required-032.txt | 322 | 1 | 1 | 0 |

**Exact inventory and decisions.** Source line numbers refer to the frozen files, not packet wrapper lines. Each quoted entry below is complete.

| ID | Source and symbol | Exact entry | Decision and reasoning |
| --- | --- | --- | --- |
| C01 | `src/living-spaces/__init__.py:1`, module | `"""Living Spaces: agent tools that build and maintain Spaces, plus the build-space skill (CONTRACTS.md §9)."""` | DELETE. Module overview and local-document pointer. It defines no caller obligation, input/output rule, or external constraint. A local contract reference is not an issue/RFC exception. |
| C02 | `src/living-spaces/__init__.py:72`, `_json_arg` | `"""Models sometimes send an object argument as a JSON string; accept both."""` | DELETE. Private normalization rationale. The code confirms two accepted representations, but the alleged model behavior is not established as a foreign constraint in this packet. It is not a public API doc comment. `MUST KILL` the implicit normalization in the symbol name; preserve supported behavior pending parent judgment. |
| C03 | `src/living-spaces/__init__.py:116`, `_split_manifest` | `"""space.json is never a project file (CONTRACTS.md §3): pull it out into the revision manifest."""` | DELETE. Private helper narration. `files.pop(MANIFEST_PATH)` and the returned `(files, manifest)` already express the split. This is our storage representation, not an external protocol requirement or public API doc comment. No reshape flag needed for this already explicit symbol. |
| C04 | `src/living-spaces/__init__.py:156`, `_warnings` | `"""Static checks the agent can act on before the user opens the Space. The sandbox enforces; this explains."""` | DELETE. Private helper overview and architecture narration. The implementation returns a list of warning strings. Its sandbox claim is not a keep-list exception, and this audit does not certify sandbox enforcement. |
| C05 | `src/living-spaces/dashboard/plugin_api.py:1`, module | `"""Desktop REST adapter for the public Living Spaces core API."""` | DELETE. Module label, not a defined public API contract. Merely saying public API does not establish contract content. |
| C06 | `src/living-spaces/living_spaces_core/bridge.py:1`, module / `dispatch` | `"""The frame's sole backend entry point. Identity comes from the bound session."""` | KEEP. Public bridge API contract about the authority of caller identity. `dispatch` requires `(sid, session)` and removes the guest `space` argument before routing. This is a security-relevant caller contract, not an internal implementation excuse. The scoped REST bridge delegates to `core.dispatch`. This retention does not certify every out-of-scope frame path. |
| C07 | `src/living-spaces/living_spaces_core/feeds.py:66`, `parse` | `# Removing NULs also catches declarations in UTF-16 and UTF-32 XML.` | KEEP. External encoding constraint. UTF-16/32 encode ASCII declaration characters with interleaved NUL bytes; scanning raw bytes for the ASCII marker would miss them. The current parser guard removes NULs before its declaration regex. Exact source guard expressions detected both DOCTYPE and ENTITY markers under all five encodings checked below. This does not assert that ElementTree accepts all those encodings. |
| C08 | `src/living-spaces/living_spaces_core/grants.py:1`, module | `"""Host-owned capability requests, decisions, scopes and audit history."""` | DELETE. Topic list/module overview. It specifies no public argument, result, failure, or authority rule beyond a label. |
| C09 | `src/living-spaces/living_spaces_core/net.py:1`, module / `fetch` | `"""Public HTTPS requests with hostname TLS and a pinned, vetted destination."""` | KEEP. Public networking API contract defining allowed destinations and TLS identity. The current `fetch` path validates HTTPS, vets the resolved address, connects to that address, and passes the original hostname for TLS. These are observable guarantees to callers, not merely a module topic list. This audit does not certify the whole security implementation. |
| C10 | `src/living-spaces/living_spaces_core/net.py:35`, `_resolve_host` | `# libc DNS has no deadline. A late answer is discarded and never opens a socket.` | KEEP. External resolver API constraint explains the otherwise non-obvious worker/queue boundary. Python's current documented `getaddrinfo` wrapper exposes no caller timeout/deadline. The source applies its budget to `Queue.get`, and a late resolver result cannot proceed to connection creation. Read “no deadline” as no caller-supplied request deadline, not a claim that every OS resolver waits forever. See evidence below. |
| C11 | `src/living-spaces/living_spaces_core/schedules.py:158`, `dispatch_detail` | `# A completed dispatch is history, not evidence for a new invocation of the shim.` | DELETE. This explains our association of retained dispatch metadata with a new refresh run. The scope does not prove an unavoidable external cron quirk. The timestamp filter is intentional behavior, but its freshness meaning belongs in the symbol rather than prose. `MUST KILL` target below. |

**MUST KILL targets.** These are comment-driven rename targets, not reproduced correctness bugs or instructions to delete working behavior.

- `src/living-spaces/__init__.py:71`, `_json_arg`. Rename to make acceptance and decoding of a JSON string or already-decoded value explicit, such as `_decode_json_arg`; the prose must not carry that normalization contract.
- `src/living-spaces/living_spaces_core/schedules.py:147`, `dispatch_detail`. Rename to express that only unfinished dispatch metadata is eligible, such as `pending_dispatch_detail`; preserve the timestamp/manual-invocation filters when the parent evaluates this target.

**Narrow how traces and keep evidence.** These are current-source traces, not application execution or historical explanations.

- `_handler` checks that the outer tool arguments are a dictionary. `_json_arg` then optionally parses each named string using `json.loads`, checks the requested container type, and returns that value. `_files`, creation, record queries, and record writes use this normalization. No scoped source proves that a model/provider forces this dual representation. The observed behavior supports the naming flag; the model attribution does not earn a keep.
- `runs.start_refresh` asks `schedules.dispatch_detail` for metadata only for the schedule trigger. `dispatch_detail` loads the linked job, rejects missing jobs and manual invocations, then returns `last_dispatch` only if there is no `last_run_at` or the dispatch timestamp is newer. This is the code's unfinished-dispatch rule. No cron runtime was called, and no claim is made about unseen cron implementation behavior.
- `bridge.dispatch` at lines 70-95 calls `sessions.require` before dispatch and again before returning, removes the `space` key from guest arguments, and passes its bound `sid` through `_call`. The module docstring records the public caller-identity rule reflected by that path.
- `net.fetch` at lines 253-285 calls `_fetch_public`. That function calls `_target`, then `_addresses`, before creating `_connection`; `_connection` is `_PinnedHTTPS`. Its `connect` uses `self.ip` for the transport address and `self.host` for `server_hostname`. This is source evidence for C09's public contract, not a socket test.
- `_fetch_public` calls `_addresses` before creating a connection. Nonliteral hosts reach `_resolve_host` through `_resolve`. The resolver worker only calls `getaddrinfo` and puts its result/exception into a local queue. When the caller's queue wait expires it raises, and no connection is created on that path. The late worker has no connection-creation call. Python documents `getaddrinfo(host, port, family, type, proto, flags)` as a wrapper of the system C function, with no timeout argument. [Python socket documentation](https://docs.python.org/3/library/socket.html#socket.getaddrinfo). This establishes the API limitation on the current referenced code path by documentation and source inspection. No DNS, socket, or timing probe was run. The supplemental POSIX documentation fetch returned HTTP 403 and was not used as evidence.
- For C07, an in-memory probe parsed `feeds.py` with `ast`, extracted only the existing `guard` and `pattern` assignment nodes in `parse`, compiled those exact nodes, and applied the existing regex to `<!DOCTYPE rss>` and `<!ENTITY x "y">` encoded as UTF-8, UTF-16LE, UTF-16BE, UTF-32LE and UTF-32BE. All ten combinations matched. It imported no application module, changed no source, and did not execute a feed request or the application parser. `refresh_source` calls `parse` in the current scoped source, so the guard is on the declared feed path. This is narrow expression evidence, not an end-to-end feed test.

**Non-comments and skips.** Both JSX files contain zero comments. Python tokenization found exactly the three line comments above, and AST inspection found exactly the eight docstrings above. No lint/TypeScript suppression, prettier-ignore, legal/license header, issue/RFC comment, commented-out code, or additional standalone documentation string was found in scope. Runtime UI disclosures, tool schema descriptions, SQL, regex strings, and `agent_prompt` text are application data and are not deletion candidates.

The proposed comment-deletion files are `src/living-spaces/__init__.py`, `src/living-spaces/dashboard/plugin_api.py`, `src/living-spaces/living_spaces_core/grants.py`, and `src/living-spaces/living_spaces_core/schedules.py`. No source files were touched. The other six scoped files have no proposed deletions. Previous customization files and tests were excluded from comment review. No application, Desktop, gateway, model, socket, cron, install, credential, host/profile, push, merge, or PR operation was performed. Repo product/test gates were not run because this seat permits only a report write and forbids application/host execution. `git diff --check` passed. There is no product acceptance verdict.

**Frozen hashes.** Every scoped source hash below agrees with both packet pins and baseline. The source byte counts include UTF-8 multibyte characters; packet offsets count characters.

| Source | SHA-256 |
| --- | --- |
| `.run/agent.md` | `3e239e40b7b4b9beb2cf7f3ccc57f2388eb8b69bd1ba8ae888ef87ef6e0e2116` |
| `src/desktop/ui/permissions.jsx` | `1b5129495eeec4fc1771e6859dc46373046aad16738a56c1e90b53c9cb24901f` |
| `src/desktop/ui/schedule.jsx` | `84e40985585f8ec709c5058336f4feac85faf33775aad12e7fa1905f783f1f30` |
| `src/living-spaces/__init__.py` | `12b7a25ef9f330100da6ddc4ff4771ac6a5d89246537caeeb6e215aafd93b24b` |
| `src/living-spaces/dashboard/plugin_api.py` | `e0060b06e16da39dbf91588cd0f2cdf6b6873c3dbc91a5d39ed8e9a30462262a` |
| `src/living-spaces/living_spaces_core/bridge.py` | `eaf69ac942a294616561cf39fd8c330e68f1f798e315b84f3bd7676c2c1b1e76` |
| `src/living-spaces/living_spaces_core/feeds.py` | `9b52d0888644abe40f46dd0bb70d4536ee8b8c6e202e8dde12d69e88c796a4b2` |
| `src/living-spaces/living_spaces_core/grants.py` | `f41aceced3d2af1f7648763e8580a021adb171ed9282e408e8dc006c46904c29` |
| `src/living-spaces/living_spaces_core/net.py` | `eae55020012ec54ba68a3bd71f1bd19cc0ba55f22a8ed434edf24b10a9fcea20` |
| `src/living-spaces/living_spaces_core/runs.py` | `f2934073bb16209420a97b1a04270a05f449d8b3e7cbb03f09f151c9abaf2bfc` |
| `src/living-spaces/living_spaces_core/schedules.py` | `9a902d814daa44343faf1689e84378c172acbc407bd52d3c9e3ad9dde6c04229` |

Control-file SHA-256 values.

- `.run/baseline.json`. `7436a1665c98f4256194f6b6913e662486d3bd720532ccdda8a8500457636e91`.
- `.run/packet/pins.json`. `769c33b27a44f18cf67f70017ca6664d3c5fe014b94e869264f6921475d6f448`.

No required-input omissions remain. Four keeps are exception-protected recommendations, not skipped inventory. The parent applies accepted deletions, judges both naming flags, and commissions fresh repair review.
