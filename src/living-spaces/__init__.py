"""Living Spaces: agent tools that build and maintain Spaces, plus the build-space skill (CONTRACTS.md §9)."""
from __future__ import annotations

import base64
import binascii
import json
import posixpath
import re
from pathlib import Path

from . import _core

TOOLSET = "living_spaces"
EMOJI = "🪴"
DEFAULT_LIBRARIES = ["preact", "preact/hooks", "spaces-kit"]
LIBRARIES = [*DEFAULT_LIBRARIES, "lightweight-charts", "htm", "lucide", "font:inter", "font:dm-sans"]
MANIFEST_PATH = "space.json"
SKILL_PATH = Path(__file__).resolve().parent / "skills" / "build-space" / "SKILL.md"
NEXT = "End your reply with the directive paragraph so the user gets an Open Space card."

SPACE_ARG = {"type": "string", "description": "Space id or exact Space name, as shown by spaces_list."}
FILES_ARG = {
    "type": "object",
    "description": ("Map of relative path to full UTF-8 text or {\"b64\":\"<base64>\",\"mime\":\"<optional>\"} "
                    "for binary assets. null deletes a file on writes only. Include \"space.json\" to set the "
                    "manifest. Every file is written whole; size limits count decoded bytes. MIME is inferred "
                    "from the path, so use the correct file extension."),
    "additionalProperties": {"anyOf": [
        {"type": "string"}, {"type": "null"},
        {"type": "object", "properties": {"b64": {"type": "string"}, "mime": {"type": "string"}},
         "required": ["b64"], "additionalProperties": False},
    ]},
}
LIBRARIES_ARG = {"type": "array", "items": {"type": "string", "enum": LIBRARIES},
                 "description": "Copy selected bundled groups, including licenses, and add import aliases. "
                                "Existing files and aliases are preserved unless explicitly replaced. "
                                "Fonts copy to vendor/fonts/. [] copies nothing. Create defaults to preact, "
                                "preact/hooks and spaces-kit; writes default to no additions."}


def _schema(name, description, properties, required=()):
    return {"name": name, "description": description,
            "parameters": {"type": "object", "properties": properties, "required": list(required)}}


def _invalid(core, message):
    error = getattr(core, "SpacesError", None) or core.errors.SpacesError
    return error("invalid", message)


def _text(core, args, name, *, required=True):
    value = args.get(name)
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip():
        raise _invalid(core, f"{name} must be a non-empty string")
    return value


def _int(core, args, name, *, required=True):
    value = args.get(name)
    if value is None and not required:
        return None
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        value = int(value)
    if isinstance(value, bool) or not isinstance(value, int):
        raise _invalid(core, f"{name} must be an integer")
    return value


def _json_arg(core, args, name, kind, *, required=True):
    """Models sometimes send an object argument as a JSON string; accept both."""
    value = args.get(name)
    if value is None and not required:
        return None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            raise _invalid(core, f"{name} must be a JSON {kind.__name__ == 'dict' and 'object' or 'array'}") from None
    if not isinstance(value, kind):
        raise _invalid(core, f"{name} must be a JSON {kind.__name__ == 'dict' and 'object' or 'array'}")
    return value


def _space(core, args):
    return core.resolve_space(_text(core, args, "space"))


def _files(core, args, *, deleting=False):
    prepared = {}
    for path, value in _json_arg(core, args, "files", dict).items():
        if isinstance(value, str) or (value is None and deleting):
            prepared[path] = value
        elif (isinstance(value, dict) and isinstance(value.get("b64"), str)
              and set(value) <= {"b64", "mime"}
              and ("mime" not in value or isinstance(value["mime"], str))):
            try:
                prepared[path] = base64.b64decode(value["b64"], validate=True)
            except (ValueError, binascii.Error):
                raise _invalid(core, f"{path}: invalid base64 file content") from None
            core.limits.check(len(prepared[path]), core.limits.FILE_BYTES, "file bytes")
            if base64.b64encode(prepared[path]).decode("ascii") != value["b64"]:
                raise _invalid(core, f"{path}: invalid base64 padding or pad bits")
        else:
            raise _invalid(core, f"{path}: expected file text or a {{b64, mime?}} descriptor"
                           + (" or null to delete" if deleting else ""))
    return prepared


def _open(sid):
    return {"directive": f'::living-space{{id="{sid}"}}', "route": f"/spaces?space={sid}"}


def _split_manifest(core, files, manifest):
    """space.json is never a project file (CONTRACTS.md §3): pull it out into the revision manifest."""
    files = dict(files)
    if MANIFEST_PATH not in files:
        return files, manifest
    if manifest is not None:
        raise _invalid(core, "Pass the manifest once: either files['space.json'] or manifest, not both")
    raw = files.pop(MANIFEST_PATH)
    if not isinstance(raw, (str, bytes)):
        raise _invalid(core, "space.json cannot be deleted; write a new manifest instead")
    try:
        manifest = json.loads(raw)
    except ValueError as exc:
        raise _invalid(core, f"space.json is not valid JSON: {exc}") from None
    if not isinstance(manifest, dict):
        raise _invalid(core, "space.json must be a JSON object")
    return files, manifest


IMPORT_RE = re.compile(r"""(?:\bfrom\s*|\bimport\s*\(?\s*)['"]([^'"\n]+)['"]""")
HTML_REF_RE = re.compile(r"""<(?:script|link|img|source)\b[^>]*?\b(?:src|href)\s*=\s*['"]([^'"]+)['"]""", re.I)
CSS_URL_RE = re.compile(r"""url\(\s*['"]?([^'")]+)['"]?\s*\)""")
NETWORK_RE = re.compile(r"""\bfetch\s*\(|\bXMLHttpRequest\b|\bnew\s+WebSocket\b|\bEventSource\s*\(|\bsendBeacon\s*\("""
                        r"""|\b(?:src|href)\s*=\s*['"]https?://|\bfrom\s*['"]https?://|\bimport\s*\(\s*['"]https?://"""
                        r"""|url\(\s*['"]?https?://|@import\s+['"]?(?:url\()?\s*['"]?https?://""")


def _refs(path, text):
    ext = posixpath.splitext(path)[1].lower()
    if ext in (".js", ".mjs"):
        return [(ref, True) for ref in IMPORT_RE.findall(text)]
    if ext in (".html", ".htm"):
        scripts = re.findall(r"<script\b[^>]*type\s*=\s*['\"]module['\"][^>]*>(.*?)</script>", text, re.I | re.S)
        return ([(ref, False) for ref in HTML_REF_RE.findall(text)]
                + [(ref, True) for body in scripts for ref in IMPORT_RE.findall(body)])
    if ext == ".css":
        return [(ref, False) for ref in CSS_URL_RE.findall(text)]
    return []


def _warnings(written, paths, manifest):
    """Static checks the agent can act on before the user opens the Space. The sandbox enforces; this explains."""
    manifest = manifest or {}
    entry = manifest.get("entry") or "index.html"
    imports = set((manifest.get("imports") or {}).keys())
    warnings = []
    if entry not in paths:
        warnings.append(f"Entry file {entry!r} is missing, so the Space cannot boot.")
    for path, text in sorted(written.items()):
        if not isinstance(text, str):
            continue
        if NETWORK_RE.search(text):
            warnings.append(f"{path}: direct network access (fetch, WebSocket or a remote URL) is blocked in the frame. "
                            "Use space.net.fetch for public HTTPS, window.space for saved data, and project files or "
                            "libraries for code and assets.")
        for ref, is_module in _refs(path, text):
            if re.match(r"^(?:[a-z][a-z0-9+.-]*:|#|//)", ref, re.I):
                continue
            if is_module and not ref.startswith((".", "/")):
                if ref not in imports:
                    warnings.append(f"{path}: bare import {ref!r} is not in the manifest imports; add it to "
                                    "libraries or vendor the file.")
                continue
            target = posixpath.normpath(posixpath.join(posixpath.dirname(path), ref.split("?")[0].split("#")[0]))
            if ref.startswith("/"):
                target = target.lstrip("/")
            if target not in paths:
                warnings.append(f"{path}: {ref!r} does not resolve to a project file.")
    return warnings


def _change_result(core, sid, rev, extra_warnings=()):
    project = core.bundle(sid, rev=rev)
    paths = {file["path"] for file in project["files"]}
    texts = {file["path"]: file["text"] for file in project["files"] if "text" in file}
    pending = [{"capability": g.get("capability"), "purpose": g.get("purpose"),
                "scope": g.get("requested_scope") or g.get("scope")}
               for g in core.list_grants(sid) if g.get("status") == "requested"]
    warnings = list(dict.fromkeys([*extra_warnings, *_warnings(texts, paths, project["manifest"])]))
    notes = []
    if "kit/spaces-kit.css" in paths:
        notes.append('To use the kit styles, add <link rel="stylesheet" href="kit/spaces-kit.css"> '
                     'to your HTML (adjust the relative path for a nested entry).')
    return {"space": sid, "rev": rev, "open": _open(sid), "grants_pending": pending, "warnings": warnings,
            "notes": notes, "next": NEXT}


def spaces_list(core, args, owner):
    return core.list_spaces(include_archived=True)


def spaces_get(core, args, owner):
    sid = _space(core, args)
    detail = dict(core.get_space(sid))
    detail["files"] = core.list_files(sid)
    return detail


def spaces_create(core, args, owner):
    name = _text(core, args, "name")
    description = args.get("description", "")
    if not isinstance(description, str):
        raise _invalid(core, "description must be a string")
    files, manifest = _split_manifest(core, _files(core, args),
                                      _json_arg(core, args, "manifest", dict, required=False))
    libraries = _json_arg(core, args, "libraries", list, required=False)
    if libraries is None:
        libraries = list(DEFAULT_LIBRARIES)
    if any(value not in LIBRARIES for value in libraries):
        raise _invalid(core, "libraries contains an unsupported library")
    actor = f"agent:{owner}"
    detail = core.create_space(name, description=description, owner=owner, files=files, manifest=manifest,
                               libraries=libraries, author=actor, summary="Created")
    sid = detail["id"]
    return _change_result(core, sid, detail.get("head_rev"), detail.get("warnings") or ())


def spaces_read_file(core, args, owner):
    sid = _space(core, args)
    path = _text(core, args, "path")
    return core.read_file(sid, path)


def spaces_write_files(core, args, owner):
    sid = _space(core, args)
    files, manifest = _split_manifest(core, _files(core, args, deleting=True), None)
    libraries = _json_arg(core, args, "libraries", list, required=False)
    summary = _text(core, args, "summary")
    info = core.write_files(sid, files=files, manifest=manifest, author=f"agent:{owner}", summary=summary,
                            base_rev=_int(core, args, "base_rev", required=False),
                            **({"libraries": libraries} if libraries is not None else {}))
    return _change_result(core, sid, info.get("rev"), info.get("warnings") or ())


def spaces_edit_file(core, args, owner):
    sid = _space(core, args)
    path = _text(core, args, "path")
    old = args.get("old")
    new = args.get("new")
    if not isinstance(old, str) or not old or not isinstance(new, str):
        raise _invalid(core, "old must be a non-empty string and new must be a string")
    summary = _text(core, args, "summary")
    actor = f"agent:{owner}"
    if path == MANIFEST_PATH:
        current = core.read_file(sid, MANIFEST_PATH)
        text = current["text"]
        count = text.count(old)
        if count != 1:
            raise _invalid(core, f"old must match space.json exactly once (matched {count} times); "
                                 "read it with spaces_read_file first")
        _, manifest = _split_manifest(core, {MANIFEST_PATH: text.replace(old, new)}, None)
        info = core.write_files(sid, files={}, manifest=manifest, author=actor, summary=summary,
                                base_rev=current["rev"])
        return _change_result(core, sid, info.get("rev"), info.get("warnings") or ())
    info = core.edit_file(sid, path, old=old, new=new, author=actor, summary=summary)
    return _change_result(core, sid, info.get("rev"), info.get("warnings") or ())


def spaces_query(core, args, owner):
    sid = _space(core, args)
    where = _json_arg(core, args, "where", dict, required=False)
    limit = _int(core, args, "limit", required=False)
    return core.query(sid, _text(core, args, "collection"), where=where, limit=100 if limit is None else limit)


def spaces_write_records(core, args, owner):
    sid = _space(core, args)
    ops = _json_arg(core, args, "ops", list)
    if not ops:
        raise _invalid(core, "ops must contain at least one operation")
    source_owned = args.get("source_owned", False)
    if not isinstance(source_owned, bool):
        raise _invalid(core, "source_owned must be a boolean")
    if source_owned:
        core.limits.check(len(ops), core.limits.BATCH_OPS, "source operations")
        counts = {"added": 0, "updated": 0, "unchanged": 0}
        with core.db.write() as conn:
            core.db.space(conn, sid, writable=True)
            if not core.grants._check(conn, sid, "refresh"):
                raise core.SpacesError("not_granted", "Refresh is not granted", capability="refresh")
            for op in ops:
                if not isinstance(op, dict) or op.get("op") != "put" or "data" in op:
                    raise _invalid(core, "Source-owned operations must put source fields, without data")
                if "base_rev" in op:
                    core.limits.integer(op["base_rev"], "base_rev")
                    core.records._ids(op.get("collection"), op.get("id"))
                    row = core.records._row(conn, sid, op.get("collection"), op.get("id"))
                    core.records._concurrency(row, op["base_rev"])
                metadata = op.get("source_meta", {})
                core.limits.object_json(metadata, core.limits.SOURCE_BYTES, "source metadata")
                metadata = {**metadata, "handler": "agent", "fetched_at": core.db.now()}
                result = core.records._upsert_source(conn, sid, op.get("collection"), op.get("id"),
                                                     op.get("source"), metadata, actor=f"upkeep:{owner}")
                counts[result] += 1
        return counts
    return core.batch(sid, ops, actor=f"agent:{owner}")


def spaces_read_logs(core, args, owner):
    sid = _space(core, args)
    return core.read_logs(sid, limit=100, level=_text(core, args, "level", required=False))


def spaces_revisions(core, args, owner):
    return core.list_revisions(_space(core, args))


def spaces_restore(core, args, owner):
    sid = _space(core, args)
    info = core.restore_revision(sid, _int(core, args, "rev"), author=f"agent:{owner}")
    return {"space": sid, "rev": info.get("rev"), "revision": info, "open": _open(sid), "next": NEXT}


def spaces_refresh(core, args, owner):
    return core.start_refresh(_space(core, args), trigger="chat", actor=f"agent:{owner}")


def spaces_request_schedule(core, args, owner):
    sid = _space(core, args)
    return core.request_schedule(sid, cadence=_text(core, args, "cadence"), timezone=_text(core, args, "timezone"),
                                 purpose=_text(core, args, "purpose"), actor=f"agent:{owner}")


REF_NOTE = (" An ambiguous or unknown space fails with code ambiguous/not_found and lists candidates: ask the user "
            "which one they mean, never guess.")
WRITE_NOTE = (" Returns {space, rev, open, grants_pending, warnings, notes}. Fix every warning and follow notes "
              "for stylesheet links. End your reply with "
              "open.directive on its own line and say what changed, the revision, and any pending grants.")
BINARY_NOTE = (" Pass binary images, audio and fonts as {\"b64\":\"<base64>\",\"mime\":\"<optional>\"} "
               "file values. Hermes's image generation output can be placed this way by base64-encoding the "
               "generated file bytes. Use the correct path extension for MIME; limits count decoded bytes.")

TOOLS = [
    (spaces_list, _schema(
        "spaces_list",
        "List every Space (id, name, owner, status, head_rev, freshness, schedule, attention). Use it first whenever "
        "the user mentions a Space, so you work with real ids instead of inventing them.",
        {})),
    (spaces_get, _schema(
        "spaces_get",
        "Get one Space: manifest, file list, grants, collections with record counts, recent refresh runs, freshness, "
        "schedule and recent error count. Read this before changing a Space's code or data." + REF_NOTE,
        {"space": SPACE_ARG}, ["space"])),
    (spaces_create, _schema(
        "spaces_create",
        "Create a new Space (a multi-file sandboxed app in the Spaces tab) from a complete set of files. Read the "
        "build-space skill first. Include space.json (or pass manifest) declaring data collections and optional "
        "upkeep feeds. libraries defaults to preact, preact/hooks and spaces-kit, copied into the project and wired "
        "into the import map. Select lightweight-charts, htm, lucide, font:inter or font:dm-sans as needed. "
        "Kit selection returns the stylesheet link to add to your HTML." + BINARY_NOTE + WRITE_NOTE,
        {"name": {"type": "string", "description": "Display name, e.g. \"Research Desk\". The id is derived from it."},
         "description": {"type": "string", "description": "One plain sentence saying what the Space is for."},
         "files": FILES_ARG,
         "manifest": {"type": "object", "description": "The space.json manifest, if not given as a file."},
         "libraries": LIBRARIES_ARG},
        ["name", "description", "files"])),
    (spaces_read_file, _schema(
        "spaces_read_file",
        "Read one project file at the current revision. path \"space.json\" returns the manifest as JSON text. Read "
        "a file before editing it." + REF_NOTE,
        {"space": SPACE_ARG, "path": {"type": "string", "description": "Relative path, e.g. \"views/queue.js\"."}},
        ["space", "path"])),
    (spaces_write_files, _schema(
        "spaces_write_files",
        "Write whole files as one new revision: add or replace files, delete a file by mapping its path to null, "
        "replace the manifest with a \"space.json\" entry. Pass base_rev (the head_rev you read) so a concurrent "
        "change fails with code conflict instead of being overwritten; on conflict re-read and retry. Prefer "
        "spaces_edit_file for small changes. Select libraries to add bundled groups with the same semantics as "
        "create; omitted libraries adds nothing. Saved records are never touched by code changes."
        + BINARY_NOTE + REF_NOTE + WRITE_NOTE,
        {"space": SPACE_ARG, "files": FILES_ARG, "libraries": LIBRARIES_ARG,
         "summary": {"type": "string", "description": "What changed, in a few words. Shown in revision history."},
         "base_rev": {"type": "integer", "description": "The head_rev this change is based on."}},
        ["space", "files", "summary"])),
    (spaces_edit_file, _schema(
        "spaces_edit_file",
        "Replace one exact snippet in one file as a new revision. old must occur exactly once in the current file, "
        "including whitespace; otherwise it fails with code invalid and you should re-read the file and retry with "
        "a longer unique snippet. Works on \"space.json\" too." + REF_NOTE + WRITE_NOTE,
        {"space": SPACE_ARG, "path": {"type": "string"},
         "old": {"type": "string", "description": "Exact current text to replace, unique in the file."},
         "new": {"type": "string", "description": "Replacement text."},
         "summary": {"type": "string", "description": "What changed, in a few words."}},
        ["space", "path", "old", "new", "summary"])),
    (spaces_query, _schema(
        "spaces_query",
        "Read records from one collection of a Space, the same data the app shows. Each record has id, rev, data "
        "(user-owned fields) and source (fields filled by refresh); a field's value is data[name] if set, else "
        "source[name]. Returns {records, total, seq}. Use it to answer questions about the Space and before every "
        "write, to get each record's current rev." + REF_NOTE,
        {"space": SPACE_ARG, "collection": {"type": "string", "description": "Collection name, e.g. \"papers\"."},
         "where": {"type": "object", "description": "Equality filter on fields, e.g. {\"status\": \"reading\"}."},
         "limit": {"type": "integer", "description": "Max records to return (default 100, max 500)."}},
        ["space", "collection"])),
    (spaces_write_records, _schema(
        "spaces_write_records",
        "Change records in one all-or-nothing batch, so the running app updates live. Ops: {\"op\":\"put\", "
        "\"collection\", \"id\", \"data\", \"base_rev\"} shallow-merges data into the record; {\"op\":\"delete\", "
        "\"collection\", \"id\", \"base_rev\"}. To update an existing record's data pass base_rev = its current rev from "
        "spaces_query; omit base_rev (or 0) only to create a new record. A stale base_rev fails the whole batch with "
        "code conflict and the record's current value: re-read and retry, never overwrite blindly. Only write the "
        "user's own fields (data) by default. For upkeep, set source_owned=true and use put operations with "
        "source and optional source_meta instead of data. This requires Refresh and preserves user data; "
        "source-owned deletes are not supported. For source-owned puts, a supplied base_rev must be a nonnegative "
        "integer matching the current rev (0 to create); omitting base_rev performs an idempotent upsert "
        "without a revision check." + REF_NOTE,
        {"space": SPACE_ARG,
         "source_owned": {"type": "boolean", "description": "Upkeep writes source fields only; preserves user notes. Default false."},
         "ops": {"type": "array", "description": "Up to 500 operations applied together.",
                 "items": {"type": "object", "properties": {
                     "op": {"type": "string", "enum": ["put", "delete"]},
                     "collection": {"type": "string"}, "id": {"type": "string"},
                     "data": {"type": "object"}, "source": {"type": "object"}, "source_meta": {"type": "object"},
                     "base_rev": {"type": "integer"},
                     "merge": {"type": "boolean", "description": "false replaces data instead of merging."}},
                     "required": ["op", "collection"]}}},
        ["space", "ops"])),
    (spaces_read_logs, _schema(
        "spaces_read_logs",
        "Read the Space's recent runtime console output, uncaught errors and sandbox policy violations (newest "
        "first). Check it after the user opens a new or changed Space, and whenever they report it is blank or "
        "broken. Fix what you find with spaces_edit_file." + REF_NOTE,
        {"space": SPACE_ARG, "level": {"type": "string", "enum": ["error", "warn", "info", "log"],
                                       "description": "Only this level."}},
        ["space"])),
    (spaces_revisions, _schema(
        "spaces_revisions",
        "List the Space's code revisions (rev, kind, author, summary, time), newest first." + REF_NOTE,
        {"space": SPACE_ARG}, ["space"])),
    (spaces_restore, _schema(
        "spaces_restore",
        "Restore an earlier code revision as a new revision. Records are not rewound. Fails with code incompatible "
        "if that revision expects a different data.version; tell the user instead of forcing it." + REF_NOTE,
        {"space": SPACE_ARG, "rev": {"type": "integer", "description": "Revision number to restore."}},
        ["space", "rev"])),
    (spaces_refresh, _schema(
        "spaces_refresh",
        "Run the Space's declared upkeep refresh now (the feed sources in its manifest). Returns the run, usually "
        "queued or running; check spaces_get recent_runs for the outcome before reporting it. Fails with code "
        "blocked when the user has not approved Refresh in the Space's Permissions; say so and ask them to "
        "approve it there." + REF_NOTE,
        {"space": SPACE_ARG}, ["space"])),
    (spaces_request_schedule, _schema(
        "spaces_request_schedule",
        "Ask the user to approve a refresh schedule. This only files a request: the schedule starts after the user "
        "approves it in the Space's Permissions, so never say it is active until spaces_get shows status active." + REF_NOTE,
        {"space": SPACE_ARG,
         "cadence": {"type": "string", "description": "Cron expression or interval, e.g. \"0 7 * * *\" or \"every 6h\"."},
         "timezone": {"type": "string", "description": "IANA timezone, e.g. \"America/Chicago\"."},
         "purpose": {"type": "string", "description": "Why, in words the user will see when approving."}},
        ["space", "cadence", "timezone", "purpose"])),
]


def _owner(context):
    for source in (context, context.get("context"), context.get("tool_context"), context.get("parent_agent")):
        if source is None:
            continue
        for key in ("profile_name", "bot_name"):
            name = source.get(key) if isinstance(source, dict) else getattr(source, key, None)
            if isinstance(name, str) and name.strip() and name != "default":
                return name.strip()
    try:
        from hermes_constants import get_hermes_home
        home = Path(get_hermes_home())
        if home.parent.name == "profiles" and not home.name.startswith("."):
            return home.name
    except (ImportError, OSError, RuntimeError):
        pass
    return "Hermes"


def _error(exc):
    if isinstance(getattr(exc, "code", None), str) and callable(getattr(exc, "to_dict", None)):
        return exc.to_dict()
    return {"code": "internal", "message": "Living Spaces could not complete this operation."}


def _handler(fn):
    def handler(args, **context):
        try:
            core = _core.load_core()
            if not isinstance(args, dict):
                raise _invalid(core, "arguments must be a JSON object")
            result = fn(core, args, _owner(context))
            return json.dumps({"ok": True, "result": result}, ensure_ascii=False, default=str)
        except Exception as exc:
            return json.dumps({"ok": False, "error": _error(exc)}, ensure_ascii=False, default=str)
    handler.__name__ = fn.__name__
    return handler


def register(ctx) -> None:
    for fn, schema in TOOLS:
        ctx.register_tool(name=schema["name"], toolset=TOOLSET, schema=schema, handler=_handler(fn),
                          description=schema["description"], emoji=EMOJI)
    ctx.register_skill("build-space", SKILL_PATH,
                       description="How to build, change, query and keep current a Living Space (multi-view app in "
                                   "the Spaces tab) with the spaces_* tools. Read before spaces_create or any code change.")
