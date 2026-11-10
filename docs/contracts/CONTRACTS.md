# Living Spaces: frozen release-1 contracts

Owner: Forge. Status: frozen for the release-1 swarm. Product behaviour comes from `docs/spec/SPEC.md` (v5.1). Experience direction comes from `docs/design/DIRECTION.md` (Miro, branch `miro/design-direction-v1`). Change this file only through Forge. Lanes that need a change post it to Forge instead of editing.

## 0. Package layout (one installable plugin folder)

```
src/living-spaces/                    # the plugin package (plugin id: living-spaces)
├── plugin.yaml                       # kind: standalone, provides_tools: [...]
├── __init__.py                       # register(ctx): tools + skill. Thin. Loads core via _core.py
├── _core.py                          # load_core(): imports living_spaces_core by path, cached in sys.modules
├── living_spaces_core/               # pure Python. stdlib + httpx only. No hermes imports except optional get_hermes_home
│   ├── __init__.py                   # re-exports the public API in section 3
│   ├── db.py  projects.py  records.py  grants.py  sessions.py  logs.py  limits.py  errors.py  migrations.py
│   ├── runs.py  feeds.py  schedules.py
│   └── bridge.py                     # dispatch(space, session, op, args) -> reply  (the only frame entry point)
├── dashboard/manifest.json           # {"name":"living-spaces","label":"Spaces","api":"plugin_api.py","tab":{"path":"/spaces","hidden":true}}
├── dashboard/plugin_api.py           # FastAPI router. Loose module: loads core through ../_core.py by path
├── desktop/plugin.js                 # BUILT artifact (esbuild) from src/desktop/**. Committed so the package loads from git
├── runtime/vendor/                   # preact.mjs, hooks.mjs, lightweight-charts.mjs (htm pending dependency approval) (copied into Spaces on request)
├── runtime/kit/                      # spaces-kit.mjs + spaces-kit.css (copied into Spaces on request)
├── scripts/refresh_space.py          # cron shim template (section 6)
└── skills/build-space/SKILL.md       # teaches the agent to build Spaces
src/desktop/                          # desktop half source, bundled to src/living-spaces/desktop/plugin.js
├── plugin.src.js  ui/**  sandbox/**
harness/                              # isolated-app launcher, CDP driver, probes, R1 suites (never shipped)
tests/python  tests/js                # unit tests
```

Storage: `<HERMES_HOME>/plugin-data/living-spaces/spaces.db` (SQLite, WAL, busy_timeout 5000, foreign_keys on). The core resolves HERMES_HOME by calling `hermes_constants.get_hermes_home()` when it imports, else the `HERMES_HOME` env var, else `~/.hermes`. `LIVING_SPACES_DB` overrides the full path, for tests only. Every public function opens and closes its own connection. Multi-step writes run inside one `BEGIN IMMEDIATE` transaction.

## 1. Identifiers and primitives

- `space_id`: `^[a-z0-9][a-z0-9-]{1,47}$`. It comes from the name slug plus a `-2`, `-3`… suffix on collision and never changes on rename.
- `collection`: `^[a-z][a-z0-9_]{0,39}$`. Names starting `_` are reserved for the host (`_prefs` is allowed for app preferences).
- `record_id`: `^[A-Za-z0-9_.:-]{1,128}$`. When an app creates a record without an id, the host generates `r_<12 hex>`.
- `path` (project file): POSIX, relative, no `..`, `.` or empty segments, no leading `/`, ≤ 200 chars, `[A-Za-z0-9._/-]` only.
- Times are float unix seconds in storage and the API. The UI formats them.
- `actor`: `user` (host UI action), `app` (from the frame through the bridge), `agent:<profile-or-bot>` (tools), `upkeep:<trigger>`.

## 2. Storage schema (db.py owns DDL; `PRAGMA user_version = 1`)

```sql
spaces(id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
  owner TEXT NOT NULL,                       -- owner bot display name/profile, e.g. "Hermes" or profile name
  status TEXT NOT NULL CHECK(status IN ('building','active','archived')),
  head_rev INTEGER NOT NULL DEFAULT 0,       -- 0 = no code yet (building)
  data_version INTEGER NOT NULL DEFAULT 1,   -- schema version the current records conform to
  accent TEXT NOT NULL DEFAULT 'blue', icon TEXT NOT NULL DEFAULT 'layers',
  pinned INTEGER NOT NULL DEFAULT 0, last_opened_at REAL, created_at REAL NOT NULL,
  updated_at REAL NOT NULL, archived_at REAL)
blobs(sha TEXT PRIMARY KEY, size INTEGER NOT NULL, content BLOB NOT NULL)            -- sha256 hex
revisions(space TEXT NOT NULL REFERENCES spaces(id) ON DELETE CASCADE, rev INTEGER NOT NULL,
  parent_rev INTEGER, kind TEXT NOT NULL CHECK(kind IN ('create','edit','restore')),
  restored_from INTEGER, manifest TEXT NOT NULL, files TEXT NOT NULL,   -- files: JSON {path: sha}
  author TEXT NOT NULL, summary TEXT NOT NULL, created_at REAL NOT NULL, PRIMARY KEY(space, rev))
records(space TEXT NOT NULL REFERENCES spaces(id) ON DELETE CASCADE, collection TEXT NOT NULL, id TEXT NOT NULL,
  data TEXT NOT NULL DEFAULT '{}',           -- user-owned fields (app, chat). JSON object
  source TEXT,                               -- source-owned fields (upkeep only). JSON object or NULL
  source_meta TEXT,                          -- {"handler","source_id","url","fetched_at","source_updated"} or NULL
  rev INTEGER NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL, updated_by TEXT NOT NULL,
  PRIMARY KEY(space, collection, id))
changes(seq INTEGER PRIMARY KEY AUTOINCREMENT, space TEXT NOT NULL, collection TEXT NOT NULL,
  record_id TEXT NOT NULL, op TEXT NOT NULL CHECK(op IN ('put','delete','source')), rev INTEGER NOT NULL,
  actor TEXT NOT NULL, at REAL NOT NULL)
recovery_points(id INTEGER PRIMARY KEY AUTOINCREMENT, space TEXT NOT NULL, reason TEXT NOT NULL,
  data_version INTEGER NOT NULL, head_rev INTEGER NOT NULL, snapshot TEXT NOT NULL, created_at REAL NOT NULL)
grants(space TEXT NOT NULL REFERENCES spaces(id) ON DELETE CASCADE, capability TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('requested','granted','denied','revoked')),
  scope TEXT NOT NULL DEFAULT '{}', purpose TEXT NOT NULL DEFAULT '', requested_scope TEXT,
  requested_at REAL, decided_at REAL, decided_by TEXT, PRIMARY KEY(space, capability))
audit(id INTEGER PRIMARY KEY AUTOINCREMENT, space TEXT NOT NULL, at REAL NOT NULL, actor TEXT NOT NULL,
  action TEXT NOT NULL, capability TEXT, outcome TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '{}')
sessions(id TEXT PRIMARY KEY, space TEXT NOT NULL, created_at REAL NOT NULL, closed_at REAL, head_rev INTEGER NOT NULL)
runs(id TEXT PRIMARY KEY, space TEXT NOT NULL, trigger TEXT NOT NULL CHECK(trigger IN ('manual','schedule','chat')),
  handler TEXT NOT NULL, actor TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('queued','running','succeeded','failed','canceled','blocked')),
  queued_at REAL NOT NULL, started_at REAL, ended_at REAL, source_as_of REAL,
  changed TEXT NOT NULL DEFAULT '{}',        -- {"added":n,"updated":n,"unchanged":n,"removed":0}
  error TEXT, detail TEXT NOT NULL DEFAULT '{}', heartbeat_at REAL)
schedules(space TEXT PRIMARY KEY REFERENCES spaces(id) ON DELETE CASCADE,
  status TEXT NOT NULL CHECK(status IN ('requested','active','paused','disabled')),
  cadence TEXT NOT NULL, timezone TEXT NOT NULL, purpose TEXT NOT NULL DEFAULT '',
  cron_job_id TEXT, catch_up TEXT NOT NULL DEFAULT 'one', requested_at REAL, decided_at REAL, next_run_at REAL)
logs(id INTEGER PRIMARY KEY AUTOINCREMENT, space TEXT NOT NULL, session TEXT, rev INTEGER, at REAL NOT NULL,
  level TEXT NOT NULL, msg TEXT NOT NULL)
```
Indexes: `changes(space, seq)`, `records(space, collection, updated_at)`, `runs(space, queued_at)`, `logs(space, id)`, `audit(space, id)`.

Every record write bumps `records.rev` and appends one `changes` row in the same transaction. `seq` is the live-update cursor.

## 3. Space manifest (stored per revision; the agent writes it as `space.json`, or the tools pass it as an object)

```json
{
  "schema": 1,
  "name": "Research Desk", "description": "Public AI research reading system",
  "entry": "index.html",
  "imports": {"preact": "vendor/preact.mjs", "preact/hooks": "vendor/hooks.mjs",
              "lightweight-charts": "vendor/lightweight-charts.mjs", "spaces-kit": "kit/spaces-kit.mjs"},
  "accent": "blue", "icon": "book",
  "data": {"version": 1,
    "collections": {"papers": {"description": "Library items", "source_owned": ["title","summary","url","authors","published"]}},
    "migrations": [ {"to": 2, "ops": [{"op":"rename_field","collection":"papers","from":"stat","to":"status"},
                                      {"op":"set_default","collection":"papers","field":"priority","value":"normal"}]} ]},
  "upkeep": {"handler": "feed",
    "sources": [{"id": "arxiv-ai", "url": "https://export.arxiv.org/api/query?search_query=cat:cs.AI&sortBy=submittedDate&max_results=20",
                 "collection": "papers", "purpose": "New public cs.AI papers"}]}
}
```
- `accent` is one of `blue green amber purple teal rose orange grey`. Any other value falls back to `blue`. `icon` is a codicon name (fallback `layers`).
- `space.json` is never stored as a project file. The tools pull it out into the revision manifest. `spaces_read_file(path="space.json")` returns the manifest.
- Allowed migration ops: `rename_field`, `set_default`, `delete_field`, `rename_collection`, `copy_collection`. Unknown op means the write is rejected (`invalid`).

## 4. Public core API (`living_spaces_core`, all return JSON-safe dicts/lists; raise `SpacesError(code, message, **extra)`)

Error codes: `not_found`, `invalid`, `conflict` (extra: `current` record), `not_granted` (extra: `capability`), `limit` (extra: `limit`, `actual`), `session_invalid`, `archived`, `blocked` (extra: `reason`), `ambiguous` (extra: `candidates`), `incompatible` (extra: `from_version`, `to_version`).

```python
# projects.py
create_space(name, *, description="", owner, files: dict[str,str|bytes] | None, manifest: dict | None,
             libraries: list[str] = (), author, summary="Created") -> SpaceDetail
resolve_space(ref: str) -> str              # exact id, else unique case-insensitive exact name; else not_found/ambiguous
list_spaces(include_archived=True) -> list[SpaceSummary]
get_space(sid) -> SpaceDetail
read_file(sid, path, rev=None) -> {"path","text"|"b64","size","sha","rev"}
list_files(sid, rev=None) -> [{"path","size","sha"}]
write_files(sid, *, files: dict[str, str|bytes|None], manifest: dict|None, author, summary,
            base_rev: int|None) -> RevisionInfo   # None value deletes a path; stale base_rev -> conflict
edit_file(sid, path, *, old: str, new: str, author, summary, base_rev=None) -> RevisionInfo   # exact single match
list_revisions(sid) -> [RevisionInfo]
restore_revision(sid, rev, *, author) -> RevisionInfo   # new 'restore' revision; data untouched; incompatible if data.version differs
bundle(sid, rev=None) -> {"space": SpaceSummary, "rev", "manifest", "files":[{"path","mime","text"|"b64"}]}
set_status(sid, status, *, actor)  # archive/unarchive; archive pauses schedule + cancels queued runs
delete_space(sid, *, actor, confirm: str)  # confirm must equal sid; removes schedule cron job first
touch_opened(sid); set_pinned(sid, bool)
# records.py
query(sid, collection, *, where: dict|None=None, order: str|None=None, limit=500, offset=0) -> {"records":[Record],"total","seq"}
get(sid, collection, rid) -> Record
put(sid, collection, rid|None, data: dict, *, actor, base_rev: int|None, merge=True) -> Record
       # base_rev None = create-only when rid is new, else conflict; 0 = must not exist; merge=True shallow-merges data
delete(sid, collection, rid, *, actor, base_rev: int|None) -> {"deleted": True}
batch(sid, ops: list[dict], *, actor) -> {"results":[...], "seq"}   # all-or-nothing; op = {"op":"put"|"delete", ...same args}
upsert_source(sid, collection, rid, source: dict, source_meta: dict, *, actor) -> ("added"|"updated"|"unchanged")
       # touches only source/source_meta; never data
changes_since(sid, seq: int, limit=500) -> {"seq": latest, "changes":[{"seq","collection","id","op","rev","actor","at"}]}
create_recovery_point(sid, reason) -> id;  list_recovery_points(sid);  restore_recovery_point(sid, id, *, actor)
# Record = {"collection","id","data":{},"source":{}|None,"source_meta":{}|None,"rev","created_at","updated_at","updated_by"}
# grants.py
CAPABILITIES = {"data": ..., "logs": ..., "refresh": ...}   # labels, descriptions, default purposes (section 5)
list_grants(sid) -> [Grant];  check(sid, capability, scope_need: dict|None=None) -> None | raises not_granted
request(sid, capability, *, scope, purpose, actor) -> Grant      # code/manifest changes call this; never grants
decide(sid, capability, decision: 'grant'|'deny'|'revoke', *, actor='user', scope=None) -> Grant
audit_log(sid, limit=100) -> [AuditEntry]
# sessions.py
open_session(sid) -> {"session","grants","head_rev"};  close_session(session);  require(sid, session) -> None|session_invalid
# logs.py
add_logs(sid, session, entries) -> int;  read_logs(sid, limit=100, level=None) -> [Log]   # secrets redacted on write
# runs.py
start_refresh(sid, *, trigger, actor) -> Run       # dedupes: returns the in-flight run if one exists; blocked if not granted/archived
get_run(run_id);  list_runs(sid, limit=50) -> [Run];  freshness(sid) -> Freshness
# schedules.py
request_schedule(sid, *, cadence, timezone, purpose, actor) -> Schedule   # status requested; no cron job yet
decide_schedule(sid, decision: 'approve'|'deny', *, actor='user') -> Schedule   # approve creates the cron job
pause_schedule(sid, paused: bool, *, actor) -> Schedule;  get_schedule(sid) -> Schedule|None;  remove_schedule(sid)
# bridge.py
dispatch(sid, session, op, args) -> {"ok": True, "result": ...} | {"ok": False, "error": {"code","message",...}}
```
SpaceSummary is `{id,name,description,owner,status,head_rev,accent,icon,pinned,updated_at,last_opened_at,freshness,schedule,attention}`. SpaceDetail adds `manifest, grants, recent_runs, data_version, collections:{name: count}, error_count_24h`.
`freshness` is `{"last_success_at","last_attempt_at","last_attempt_status","source_as_of","next_run_at"}`. These are separate facts and must never be merged. `attention` is `null` or `{"kind":"failed"|"blocked"|"crashed","message"}`.

## 5. Grants (release 1)

| capability | default on create | scope | meaning |
|---|---|---|---|
| `data` | granted (visible) | `{}` | read/write this Space's own records. Never another Space's. |
| `logs` | granted (visible) | `{}` | submit runtime console/errors; agent reads them |
| `refresh` | `requested` when the manifest has `upkeep`, otherwise absent | `{"hosts":["export.arxiv.org"]}` | run the declared host-owned upkeep handler against those hosts only |

- A grant counts only when `status == 'granted'` and the needed scope is a subset of the granted scope.
- A new revision whose upkeep hosts are not a subset of the granted scope sets `refresh` back to `requested` with `requested_scope`. The previous grant stops working until approved. Silent widening is impossible.
- `deny` and `revoke` cancel queued runs and make scheduled runs end `blocked`. An app calling `refresh` without the grant gets `not_granted`, with no fetch and no write.
- Release-2 capabilities (`sites`, `camera`, `microphone`, `location`, `tool:*`, `files`, `cross_space`, `agent.ask`) are named in `grants.FUTURE` for the UI's "Not available yet" rows. Bridge ops for them do not exist and return `not_granted`.

## 6. Upkeep

- `start_refresh` inserts a run (`queued`), then runs the handler in a worker thread (REST/tool) or inline (cron shim). One non-terminal run per Space is allowed: a second request returns the same run. A run with no heartbeat for over 120 s is marked `failed` ("interrupted") on the next start.
- `feed` handler: for each source, check `refresh` covers its host, then fetch over https only (httpx, 20 s timeout, 3 MB cap, no redirects off-host). Parse RSS 2.0 or Atom with `xml.etree` (defusedxml-like guards: reject DOCTYPE/ENTITY). Map each entry to `{title, summary, url, authors, published, updated}` with record id `src_<sha1(entry id or link)[:16]>`. Call `upsert_source` per entry in one transaction per source. A partial failure records which source failed and leaves the others' records intact. On failure every existing record keeps its source fields and the run is `failed` with a useful error. Upkeep never deletes records in release 1.
- Run statuses: `succeeded` (with `changed` counts, "no change" is a valid success), `failed` (`error`), `blocked` (`detail.reason`: `not_granted` | `archived` | `no_handler`), `canceled`.
- Schedule: `approve` writes `<HERMES_HOME>/scripts/living-spaces-refresh-<sid>.py` from `scripts/refresh_space.py` (the shim loads core by path and calls `start_refresh(sid, trigger="schedule", actor="upkeep:schedule")` inline). It then creates a no-agent cron job through `cron.jobs.create_job(prompt=None, schedule=cadence, name=f"living-spaces:{sid}", script=..., no_agent=True, deliver="local", catch_up=True, timezone=tz)`. Pause and resume call `cron.jobs.pause_job`/`resume_job`. Archive pauses. Delete removes the job and the shim. `next_run_at` is read from the cron job. If the cron import is unavailable, report `blocked` and say so. Never fake it.
- Catch-up policy, shown in the UI: "Runs one current refresh when Hermes wakes. Missed intervals aren't replayed."

## 7. Bridge protocol v1 (frame ⇄ host ⇄ backend)

Transport: one `MessageChannel` per mount. The host transfers `port2` inside `{type:"space-boot", v:1, session, bundle, grants}` to the inner frame through the shell relay (see `src/desktop/sandbox`). The host binds the port to one `space_id` and one `session`. Frames never send a space id, and any id in args is ignored.

Frame → host request: `{v:1, id:<int>, op:<string>, args:<object>}`. Max serialized size 1 MB. Anything else is dropped and counted as `denied`.
Host → frame reply: `{v:1, id, ok:true, result}` or `{v:1, id, ok:false, error:{code, message, current?}}`.
Host → frame event: `{v:1, type:"event", event:"data.changed", payload:{seq, changes:[...]}}`, `"run.updated"` (payload Run), `"session.closed"` (payload `{reason}`).

| op | grant | args | result |
|---|---|---|---|
| `meta` | none | `{}` | `{space:{id,name,rev}, grants:[capability…], limits}` |
| `data.query` | data | `{collection, where?, order?, limit?, offset?}` | `{records, total, seq}` |
| `data.get` | data | `{collection, id}` | Record |
| `data.put` | data | `{collection, id?, data, base_rev?, merge?}` | Record (`conflict` carries `current`) |
| `data.delete` | data | `{collection, id, base_rev?}` | `{deleted:true}` |
| `data.batch` | data | `{ops:[...]}` | `{results, seq}` |
| `refresh` | refresh | `{}` | Run |
| `runs.list` | none | `{limit?}` | `[Run]` |
| `log` | logs | `{entries:[{level,msg}]}` (≤ 50 per call, msg ≤ 4000 chars) | `{stored:n}` |

The host forwards every op to `POST /spaces/{sid}/bridge {session, op, args}`. The backend checks the session (open, matching space) and the grant, then runs `bridge.dispatch`. **The backend is the authority. The host JS check only gives fast feedback.** A frame reload is detected by the host (shell `load` after boot): the host closes the session (`DELETE /sessions/{s}`), destroys the port and remounts with a new session. Any message on an old port gets `session_invalid` (the backend rejects closed sessions too).

Live updates: while a Space is open the host polls `GET /spaces/{sid}/changes?since=<seq>` every 1500 ms and posts `data.changed` events. It polls `GET /spaces/{sid}` for a `head_rev` change (code revision means a remount at the same route) and for run status changes (`run.updated`).

`window.space` (frame API, provided by the loader, documented for the agent in the skill):
```js
space.meta  // {space:{id,name,rev}, grants}
await space.query(collection, {where, order, limit})   // -> Record[]
await space.get(collection, id)        await space.put(collection, id|null, data, {baseRev})  // throws SpaceError(code)
await space.delete(collection, id, {baseRev})          await space.batch(ops)
await space.refresh()                  await space.runs()
space.on('change', ({seq, changes}) => ...)   space.on('run', run => ...)   // returns unsubscribe
space.field(record, name)  // data[name] ?? source[name]
```
`spaces-kit.mjs` (optional helper library copied into Spaces) adds: `useCollection(collection, opts)` (Preact hook that re-queries on change events), `useSaveState()` (`idle|saving|saved|failed|conflict` plus message), `hashRouter(routes)`, `SaveIndicator`, `ConflictBanner`, `EmptyState`, and a base CSS (`spaces-kit.css`) with accessible defaults (focus rings, ≥ 4.5:1 text, reduced motion).

## 8. REST API (`/api/plugins/living-spaces`, JSON)

| method + path | body | returns |
|---|---|---|
| GET `/spaces` | | `{spaces:[SpaceSummary], seq_global}` |
| GET `/spaces/{sid}` | | SpaceDetail plus `schedule`, `freshness` |
| GET `/spaces/{sid}/bundle` | | bundle(sid) |
| POST `/spaces/{sid}/sessions` | | `{session, grants, head_rev}` |
| DELETE `/spaces/{sid}/sessions/{session}` | | `{closed:true}` |
| POST `/spaces/{sid}/bridge` | `{session, op, args}` | bridge reply (always HTTP 200 with `ok`) |
| GET `/spaces/{sid}/changes?since=` | | changes_since |
| GET `/spaces/{sid}/runs` · POST `/spaces/{sid}/refresh` | | `[Run]` · Run (actor `user`, trigger `manual`) |
| GET `/spaces/{sid}/grants` · POST `/spaces/{sid}/grants/{cap}` | `{decision, scope?}` | `{grants, future, audit}` · Grant |
| GET `/spaces/{sid}/schedule` · POST `/spaces/{sid}/schedule` | `{decision:'approve'|'deny'}` or `{paused:bool}` | Schedule |
| GET `/spaces/{sid}/revisions` · POST `/spaces/{sid}/revisions/{rev}/restore` | | `[RevisionInfo]` · RevisionInfo |
| GET `/spaces/{sid}/logs` | | `[Log]` |
| POST `/spaces/{sid}/archive` · `/unarchive` · `/pin` `{pinned}` · `/opened` | | SpaceSummary |
| DELETE `/spaces/{sid}?confirm=<sid>` | | `{deleted:true, removed:{records,revisions,schedule}}` |
| GET `/status` | | `{seq_global, spaces:n, attention:n}` |

Errors use HTTP 4xx with `{"error":{"code","message",...}}` (404 not_found, 400 invalid, 409 conflict, 403 not_granted/session_invalid, 413 limit, 423 archived).

## 9. Agent tools (toolset `living_spaces`, emoji 🪴). Every handler returns a JSON string `{"ok":true,"result":...}` or `{"ok":false,"error":{...}}`

`spaces_list` · `spaces_get(space)` · `spaces_create(name, description, files, manifest?, libraries?)` · `spaces_read_file(space, path)` · `spaces_write_files(space, files, summary, base_rev?)` · `spaces_edit_file(space, path, old, new, summary)` · `spaces_query(space, collection, where?, limit?)` · `spaces_write_records(space, ops)` (batch of put/delete with base_rev) · `spaces_read_logs(space, level?)` · `spaces_revisions(space)` · `spaces_restore(space, rev)` · `spaces_refresh(space)` · `spaces_request_schedule(space, cadence, timezone, purpose)`.
- `space` accepts an id or an exact name. Ambiguous or unknown refs fail with `ambiguous`/`not_found` and the candidates, never a guess (R1-03).
- `spaces_create` and `spaces_write_files` return `{space, rev, open: {directive: "::living-space{id=\"<sid>\"}", route: "/spaces?space=<sid>"}, grants_pending:[...], warnings:[...]}`. Warnings cover missing entry, unresolved relative imports, and network URLs in code (blocked at runtime).
- The skill tells the agent to end creation and update replies with the directive paragraph `::living-space{id="<sid>"}`. The desktop half registers `TRANSCRIPT_DIRECTIVE_AREA` name `living-space`, which renders an **Open Space** card that navigates to `/spaces?space=<sid>`.
- Owner: the tool context's profile/bot name when available, else `"Hermes"`.

## 10. Limits (limits.py; errors are visible `limit` with numbers, never silent truncation)

Project ≤ 25 MB total, ≤ 600 files, file ≤ 8 MB. Record `data` ≤ 256 KB serialized, `source` ≤ 64 KB. ≤ 50,000 records per Space. Batch ≤ 500 ops. Logs keep the last 2,000 per Space. Bridge message ≤ 1 MB. Feed ≤ 3 MB, ≤ 200 entries per source. Revisions are kept forever in release 1, and blobs are deduplicated.

## 11. Sandbox (carried from the spike, `src/desktop/sandbox`)

Nested srcdoc frames, `sandbox="allow-scripts"` only (opaque origin), the CSP below on both frames, and the shell frame's `frame-src 'none'` governing the inner frame's navigation. Project files become frame-local `blob:` URLs. Import maps resolve relative ESM and bare names from `manifest.imports`. CSP: `default-src 'none'; script-src 'unsafe-inline' 'unsafe-eval' blob:; style-src 'unsafe-inline' blob:; img-src blob: data:; font-src blob: data:; media-src blob: data:; worker-src blob:; connect-src 'none'; frame-src 'none'; form-action 'none'; base-uri 'none'; object-src 'none'; manifest-src 'none'; webrtc 'block'` (`webrtc` is declared but not enforced by this Chromium, a disclosed limit). Runtime errors, `console.*` and CSP violations go to `log` (batched). External links are offered by the host only, never by app navigation.

## 12. Cross-lane seams (who calls whom; lazy imports so each lane tests alone)

- Core (`projects`, `grants`, `bridge`) calls upkeep only through these functions, imported lazily inside the function with `from . import runs, schedules`. Upkeep implements them:
  `runs.cancel_pending(sid, reason) -> int` · `runs.freshness(sid) -> Freshness` · `runs.list_runs(sid, limit)` · `runs.start_refresh(sid, *, trigger, actor) -> Run` · `schedules.get_schedule(sid) -> Schedule|None` · `schedules.on_archive(sid)` · `schedules.on_unarchive(sid)` · `schedules.on_delete(sid)`.
  Until upkeep lands, core treats an `ImportError` or `AttributeError` there as "no upkeep": empty freshness `{all None}`, schedule `None`, no-op hooks. Core tests must not depend on upkeep.
- Grant revoke/deny for `refresh` calls `runs.cancel_pending(sid, "refresh revoked")`. Archive calls `runs.cancel_pending(sid, "archived")` and `schedules.on_archive(sid)`.
- Upkeep calls core: `records.upsert_source`, `grants.check(sid, "refresh", {"hosts":[host]})`, `projects.get_space`, `projects.bundle(sid)["manifest"]`, `db.write/read`, `errors.SpacesError`.
- The desktop host (UI lane) mounts Spaces only through `src/desktop/sandbox/index.js` (sandbox lane):
  ```js
  export const BRIDGE_VERSION = 1
  export function mountSpace(container, { bundle, session, grants, call, onEvent }) -> { postEvent(event, payload), destroy() }
  // bundle = GET /spaces/{sid}/bundle response; call(op, args) -> Promise<reply> (UI lane implements it as POST /bridge);
  // onEvent({kind:'booted'|'reloaded'|'denied'|'error'|'log-overflow', ...}). On 'reloaded' the UI closes the session and remounts.
  export const WEBRTC_NOTE  // the exact spec §2 disclosure string (UI renders it; single source)
  ```
  The sandbox lane also owns `src/living-spaces/runtime/kit/*`. The UI lane owns `src/desktop/plugin.src.js` and `src/desktop/ui/**`, and builds `src/living-spaces/desktop/plugin.js` with `esbuild src/desktop/plugin.src.js --bundle --format=esm --external:@hermes/plugin-sdk --external:react --external:react/jsx-runtime --outfile=src/living-spaces/desktop/plugin.js`.
- Test file ownership: `tests/python/test_core_*.py` (core), `tests/python/test_upkeep_*.py` (upkeep), `tests/python/test_agent_*.py` (agent), `tests/js/sandbox/**` (sandbox), `tests/js/ui/**` (ui). Python tests use stdlib `unittest` and run with `~/.hermes/hermes-agent/venv/bin/python -m unittest discover -s tests/python -t .`. Each test sets `LIVING_SPACES_DB` (and `HERMES_HOME` if it touches cron) to a fresh temp dir **inside the worktree's `.run/`**, never under `~/.hermes`.

## 13. Amendments found during the swarm (Forge applies at integration)

- **A1 (upkeep → core):** "one transaction per source" can't be built from a single-record `upsert_source`. Core adds `records.upsert_sources(sid, collection, entries: list[(rid, source, source_meta)], *, actor) -> {"added","updated","unchanged"}`, which runs in one IMMEDIATE transaction. Upkeep calls it when present and falls back to per-record calls.
- **A2 (upkeep → schema):** `schedules` gains `reason TEXT` so `disabled` can carry a visible reason (e.g. "Hermes cron is unavailable in this process"). Migration: `ALTER TABLE schedules ADD COLUMN reason TEXT` when missing.
- **A3 (admission, Forge):** The REST bundle response in section 8 gains `sandbox: {format: 1, shell_srcdoc: string}`. Only the fixed installed backend producer supplies it from the deterministic packaged guest document. Core `bundle()` and persisted project/revision data stay unchanged. Renderer-private parsing rejects malformed or unsupported sandbox wire data. Section 12 mounting becomes `mountSpace(container, {bundle, grants, call, onEvent})`; the session remains only in the host REST closure. The section 7 boot envelope drops `session` and receives only the existing project-bundle fields, grants, and port. Neither session nor sandbox wire metadata reaches the guest. Both opaque frames and section 11's exact CSP remain unchanged. Guest producers move out of renderer dependencies into build-time modules and one reviewed static package asset. Format changes when the boot/bridge schema or immutable policy floor becomes incompatible. Unsupported formats fail closed with session cleanup and an actionable reinstall message. See `docs/architecture/SANDBOX-ADMISSION.md` for the selected refinement shape, required repairs, test migrations, and unexecuted runtime gates. This amendment authorizes implementation, not release acceptance.
