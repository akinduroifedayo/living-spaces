from __future__ import annotations

import base64
import binascii
import importlib
import json
import posixpath
import re
from pathlib import Path

from . import _core
from .desktop_rpc import register_desktop_rpc

TOOLSET = "living_spaces"
EMOJI = "🪴"
DEFAULT_LIBRARIES = ["preact", "preact/hooks", "spaces-kit"]
LIBRARIES = [*DEFAULT_LIBRARIES, "lightweight-charts", "htm", "lucide", "font:inter", "font:dm-sans"]
MANIFEST_PATH = "space.json"
SKILL_PATH = Path(__file__).resolve().parent / "skills" / "build-space" / "SKILL.md"
NEXT = "End your reply with the directive paragraph so the user gets an Open Space card."

SPACE_ARG = {"type": "string", "description": "Space id or exact Space name, as shown by spaces_list."}
MIME_PROP = {"type": "string", "description": "Optional. MIME follows the path extension."}
FILES_ARG = {
    "type": "object",
    "description": ("Map of relative path to full UTF-8 text, or a descriptor with exactly one source: "
                    "{\"from_path\":\"/absolute/local/file\"} copies a local file (Hermes image generation "
                    "output, downloads), {\"from_url\":\"https://...\"} downloads public HTTPS bytes (fonts, "
                    "libraries, images), {\"b64\":\"<base64>\"} for small inline bytes. null deletes a file on "
                    "writes only. Include \"space.json\" to set the manifest. Every file is written whole. Limits "
                    "count bytes: 8 MB per file, 25 MB and 600 files per Space. MIME is inferred from the path, so "
                    "use the correct file extension."),
    "additionalProperties": {"anyOf": [
        {"type": "string"}, {"type": "null"},
        {"type": "object", "properties": {"b64": {"type": "string"}, "mime": MIME_PROP},
         "required": ["b64"], "additionalProperties": False},
        {"type": "object", "properties": {"from_path": {"type": "string", "description": "Absolute local path."},
                                          "mime": MIME_PROP},
         "required": ["from_path"], "additionalProperties": False},
        {"type": "object", "properties": {"from_url": {"type": "string", "description": "Public https:// URL."},
                                          "mime": MIME_PROP},
         "required": ["from_url"], "additionalProperties": False},
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


SOURCE_KEYS = ("b64", "from_path", "from_url")


def _descriptor_source(value):
    if not isinstance(value, dict) or not set(value) <= {*SOURCE_KEYS, "mime"}:
        return None
    if "mime" in value and not isinstance(value["mime"], str):
        return None
    keys = [key for key in SOURCE_KEYS if key in value]
    if len(keys) != 1 or not isinstance(value[keys[0]], str):
        return None
    return keys[0]


def _decode_b64(core, path, encoded, *, max_bytes=None):
    maximum = core.limits.FILE_BYTES if max_bytes is None else min(max_bytes, core.limits.FILE_BYTES)
    estimated = len(encoded) // 4 * 3 - min(2, len(encoded) - len(encoded.rstrip("=")))
    core.limits.check(estimated, core.limits.FILE_BYTES, "file bytes")
    core.limits.check(estimated, maximum, "available project bytes")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raise _invalid(core, f"{path}: invalid base64 file content") from None
    core.limits.check(len(raw), core.limits.FILE_BYTES, "file bytes")
    if base64.b64encode(raw).decode("ascii") != encoded:
        raise _invalid(core, f"{path}: invalid base64 padding or pad bits")
    return raw


def _with_path(core, path, read, *, used=0):
    try:
        return read()
    except core.SpacesError as exc:
        if (exc.code == "limit" and exc.extra.get("resource") in ("available project bytes", "response body")
                and exc.extra.get("limit", core.limits.FILE_BYTES) < core.limits.FILE_BYTES):
            actual = used + exc.extra["actual"]
            maximum = core.limits.PROJECT_BYTES
            raise core.SpacesError("limit", f"{path}: project bytes exceeds {maximum} (actual {actual})",
                                   limit=maximum, actual=actual, resource="project bytes") from None
        raise core.SpacesError(exc.code, f"{path}: {exc.message}", **exc.extra) from None


def _file_refs(core):
    return importlib.import_module(core.__name__ + ".file_refs")


def _files(core, args, *, deleting=False, space=None):
    files = _json_arg(core, args, "files", dict)
    for path, value in files.items():
        if (not isinstance(value, str) and not (value is None and deleting)
                and _descriptor_source(value) is None):
            raise _invalid(core, f"{path}: expected file text or one of {{b64}}, {{from_path}} or {{from_url}} "
                           "with optional mime" + (", or null to delete" if deleting else ""))
    if not any(isinstance(value, dict) for value in files.values()):
        return files, []
    for path in files:
        core.limits.path(path)
    current = {file["path"]: file["size"] for file in core.list_files(space)} if space else {}
    retained = {path: size for path, size in current.items() if path not in files}
    libraries = _json_arg(core, args, "libraries", list, required=False)
    if libraries is None:
        libraries = [] if deleting else DEFAULT_LIBRARIES
    for library in libraries:
        if not isinstance(library, str) or library not in LIBRARIES:
            raise _invalid(core, "libraries contains an unsupported library")
        for path in core.projects._LIBRARIES[library]["files"]:
            source = core.projects.RUNTIME / path
            if path not in files and path not in current and source.is_file():
                retained[path] = source.stat().st_size
    final_paths = set(retained) | {path for path, value in files.items() if value is not None and path != MANIFEST_PATH}
    core.limits.check(len(final_paths), core.limits.PROJECT_FILES, "project files")
    used = sum(retained.values())
    core.limits.check(used, core.limits.PROJECT_BYTES, "project bytes")
    prepared, sources = {}, []
    for path, value in files.items():
        maximum = core.limits.FILE_BYTES if path == MANIFEST_PATH else min(
            core.limits.FILE_BYTES, core.limits.PROJECT_BYTES - used)
        source = _descriptor_source(value)
        if value is None:
            prepared[path] = None
            continue
        if isinstance(value, str):
            core.limits.check(len(value), core.limits.FILE_BYTES, "file bytes")
            core.limits.check(len(value), maximum, "available project bytes")
            size = len(value.encode("utf-8"))
            prepared[path] = value
        elif source == "b64":
            prepared[path] = _with_path(core, path, lambda: _decode_b64(core, path, value["b64"], max_bytes=maximum), used=used)
            size = len(prepared[path])
        elif source == "from_path":
            prepared[path] = _with_path(core, path, lambda: _file_refs(core).read_path(value["from_path"], max_bytes=maximum), used=used)
            size = len(prepared[path])
        else:
            prepared[path], note = _with_path(core, path, lambda: _file_refs(core).fetch_url(value["from_url"], max_bytes=maximum), used=used)
            size = len(prepared[path])
            sources.append(f"{path} from {note}")
        core.limits.check(size, core.limits.FILE_BYTES, "file bytes")
        if path != MANIFEST_PATH:
            used += size
            core.limits.check(used, core.limits.PROJECT_BYTES, "project bytes")
    return prepared, sources


def _summary_with_sources(summary, sources):
    return summary if not sources else f"{summary} (" + "; ".join(sources) + ")"


def _open(sid):
    return {"directive": f'::living-space{{id="{sid}"}}', "route": f"/spaces?space={sid}"}


def _split_manifest(core, files, manifest):
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
        notes.append("Optional: link kit/spaces-kit.css for the quiet Hermes look. "
                     "Most Spaces should bring their own styles.css. "
                     'The tag is <link rel="stylesheet" href="kit/spaces-kit.css"> '
                     "(adjust the relative path for a nested entry).")
    return {"space": sid, "rev": rev, "open": _open(sid), "grants_pending": pending, "warnings": warnings,
            "notes": notes, "next": NEXT}


def spaces_list(core, args, owner):
    return core.list_spaces(include_archived=True)


def spaces_get(core, args, owner):
    sid = _space(core, args)
    detail = dict(core.get_space(sid))
    detail["files"] = core.list_files(sid)
    return detail


def spaces_create(core, args, owner, maintainer=None):
    name = _text(core, args, "name")
    description = args.get("description", "")
    if not isinstance(description, str):
        raise _invalid(core, "description must be a string")
    files, sources = _files(core, args)
    files, manifest = _split_manifest(core, files, _json_arg(core, args, "manifest", dict, required=False))
    libraries = _json_arg(core, args, "libraries", list, required=False)
    if libraries is None:
        libraries = list(DEFAULT_LIBRARIES)
    if any(value not in LIBRARIES for value in libraries):
        raise _invalid(core, "libraries contains an unsupported library")
    actor = f"agent:{owner}"
    detail = core.create_space(name, description=description, owner=owner, files=files, manifest=manifest,
                               libraries=libraries, author=actor, summary=_summary_with_sources("Created", sources))
    sid = detail["id"]
    warnings = list(detail.get("warnings") or ())
    if maintainer:
        core.bind_maintainer(sid, maintainer)
    else:
        warnings.append("Canvas bot actions are unavailable because native maintaining-session context was missing. Bind it from a native maintenance turn with spaces_bind_maintainer.")
    result = _change_result(core, sid, detail.get("head_rev"), warnings)
    if maintainer:
        result["notes"].append("Canvas controls can call space.ask(text, {activationId, records: [{collection, id}]}) and listen with space.on('bot', status => ...). Keep activationId stable for an uncertain retry. Requests use native model turns and need a current user activation. Use space.refresh() for no-model feed refresh.")
    return result


def spaces_read_file(core, args, owner):
    sid = _space(core, args)
    path = _text(core, args, "path")
    return core.read_file(sid, path)


def spaces_write_files(core, args, owner):
    sid = _space(core, args)
    files, sources = _files(core, args, deleting=True, space=sid)
    files, manifest = _split_manifest(core, files, None)
    libraries = _json_arg(core, args, "libraries", list, required=False)
    summary = _summary_with_sources(_text(core, args, "summary"), sources)
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


def spaces_schedule_upkeep(core, args, owner):
    sid = _space(core, args)
    kind = _text(core, args, "kind")
    prompt = _text(core, args, "prompt", required=kind == "agent")
    return core.schedule_upkeep(sid, kind=kind, cadence=_text(core, args, "cadence"),
                                timezone=_text(core, args, "timezone"), prompt=prompt, actor=f"agent:{owner}")


def spaces_upkeep(core, args, owner):
    sid = _space(core, args)
    action = _text(core, args, "action")
    if action == "status":
        return core.get_upkeep(sid)
    return core.upkeep_action(sid, action, actor=f"agent:{owner}")


REF_NOTE = (" An ambiguous or unknown space fails with code ambiguous/not_found and lists candidates: ask the user "
            "which one they mean, never guess.")
WRITE_NOTE = (" Returns {space, rev, open, grants_pending, warnings, notes}. Fix every warning and follow notes "
              "for stylesheet links. End your reply with "
              "open.directive on its own line and say what changed, the revision, and any pending grants.")
BINARY_NOTE = (" Place binary files by reference in one line: {\"from_path\":\"/absolute/path\"} copies a local "
               "file such as Hermes image generation output or a downloaded file, and {\"from_url\":\"https://...\"} "
               "downloads fonts, libraries and images over public HTTPS (no Internet grant needed; this is you "
               "acting, not the Space). Keep {\"b64\":\"<base64>\"} for small inline bytes. from_path must be "
               "inside a supported Hermes media/download cache or the temp folder; stage other authorized "
               "files in temp with native tools first. Credential files (.env, auth.json, keys, tokens, secrets, "
               ".ssh) are refused and must not be staged to bypass the guard. Use the correct path extension for MIME. "
               "Limits: 8 MB per file, 25 MB and 600 files per Space.")

TOOLS = [
    (spaces_list, _schema(
        "spaces_list",
        "List every Space (id, name, owner, status, head_rev, freshness, upkeep, attention). Use it first whenever "
        "the user mentions a Space, so you work with real ids instead of inventing them.",
        {})),
    (spaces_get, _schema(
        "spaces_get",
        "Get one Space: manifest, file list, grants, collections with record counts, recent refresh runs, freshness, "
        "upkeep (the linked Hermes cron job, or null) and recent error count. Read this before changing a Space's code or data." + REF_NOTE,
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
        "source and optional source_meta instead of data. This preserves user data; "
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
        "Refresh now. A feed Space runs its declared feed sources in-process (needs Internet access) and returns "
        "the run; check spaces_get recent_runs for the outcome before reporting it. An agent Space triggers its "
        "linked Hermes cron job, or starts a one-time Hermes cron agent run when none is linked, and returns "
        "{kind:'cron', cron_job_id, dispatch}. dispatch is the public cron response, not proof of successful "
        "execution or delivery. That run uses model calls. Execution history is unavailable." + REF_NOTE,
        {"space": SPACE_ARG}, ["space"])),
    (spaces_schedule_upkeep, _schema(
        "spaces_schedule_upkeep",
        "Schedule this Space's upkeep as an ordinary Hermes cron job, created now. The user asking for it is the "
        "consent, as for any Hermes cron job; only call this when the user asked for scheduled upkeep. It replaces "
        "any existing upkeep job for the Space. kind agent runs the prompt as a Hermes agent turn on each fire, "
        "which uses model calls: tell the user so. kind feed runs the manifest's feed sources with no model calls. "
        "Returns public cron list metadata and a prompt preview, not the full task or execution history; "
        "report its schedule, next run and any warning." + REF_NOTE,
        {"space": SPACE_ARG,
         "kind": {"type": "string", "enum": ["agent", "feed"]},
         "cadence": {"type": "string", "description": "Hermes cron schedule, e.g. \"0 7 * * *\" or \"every 6h\"."},
         "timezone": {"type": "string", "description": "IANA timezone, e.g. \"America/Chicago\"."},
         "prompt": {"type": "string", "description": "Required for agent: the upkeep task."}},
        ["space", "kind", "cadence", "timezone"])),
    (spaces_upkeep, _schema(
        "spaces_upkeep",
        "Read or control this Space's linked Hermes cron job. status returns the link and public cron list metadata; "
        "full prompts, execution history and manual dispatch status are unavailable. pause, resume and run use "
        "the public cron tool; run returns its dispatch response without claiming an outcome. remove deletes the job and the "
        "link." + REF_NOTE,
        {"space": SPACE_ARG,
         "action": {"type": "string", "enum": ["status", "pause", "resume", "run", "remove"]}},
        ["space", "action"])),
]


def spaces_bind_maintainer(core, args, owner, maintainer=None):
    if not maintainer:
        raise core.SpacesError("blocked", "Native maintaining-session context is unavailable")
    return core.bind_maintainer(_space(core, args), maintainer)


TOOLS.append((spaces_bind_maintainer, _schema(
    "spaces_bind_maintainer",
    "Bind an existing unbound Space to this native maintaining conversation when the user asks. "
    "Uses trusted native context, never a supplied owner or route. Refuses to replace a different maintainer.",
    {"space": SPACE_ARG}, ["space"])))


def _maintainer(context):
    conversation = context.get("conversation_id")
    stored = context.get("session_id")
    if not all(isinstance(value, str) and value.strip() for value in (conversation, stored)):
        return None
    try:
        from hermes_constants import get_hermes_home
        from gateway.session_context import get_session_env
        key = get_session_env("HERMES_SESSION_KEY", "")
        if not key:
            return None
        return {"profile_id": str(Path(get_hermes_home()).resolve()), "conversation_id": conversation,
                "stored_session_id": stored, "session_key": key}
    except (ImportError, OSError, RuntimeError):
        return None


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
            if fn in (spaces_create, spaces_bind_maintainer):
                result = fn(core, args, _owner(context), _maintainer(context))
            else:
                result = fn(core, args, _owner(context))
            return json.dumps({"ok": True, "result": result}, ensure_ascii=False, default=str)
        except Exception as exc:
            return json.dumps({"ok": False, "error": _error(exc)}, ensure_ascii=False, default=str)
    handler.__name__ = fn.__name__
    return handler


def register(ctx) -> None:
    _core.load_core().configure_context(ctx)
    register_desktop_rpc(ctx, _core.load_core)
    for fn, schema in TOOLS:
        ctx.register_tool(name=schema["name"], toolset=TOOLSET, schema=schema, handler=_handler(fn),
                          description=schema["description"], emoji=EMOJI)
    ctx.register_skill("build-space", SKILL_PATH,
                       description="How to build, change, query and keep current a Living Space (multi-view app in "
                                   "the Spaces tab) with the spaces_* tools. Read before spaces_create or any code change.")
