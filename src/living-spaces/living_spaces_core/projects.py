"""Content-addressed projects and immutable code history, separate from records."""
import base64
import hashlib
from collections import Counter
import json
import mimetypes
import re
import unicodedata
from pathlib import Path

from . import db, diagnostics, grants, limits, migrations, records, runs, upkeep
from .errors import SpacesError

RUNTIME = Path(__file__).parent.parent / "runtime"
_LIBRARIES = {
    "preact": {"files": ["vendor/preact.mjs"], "imports": {"preact": "vendor/preact.mjs"}},
    "preact/hooks": {"files": ["vendor/hooks.mjs", "vendor/preact.mjs"],
                     "imports": {"preact": "vendor/preact.mjs", "preact/hooks": "vendor/hooks.mjs"}},
    "lightweight-charts": {"files": ["vendor/lightweight-charts.mjs"],
                           "imports": {"lightweight-charts": "vendor/lightweight-charts.mjs"}},
    "spaces-kit": {"files": ["kit/spaces-kit.mjs", "kit/spaces-kit.css", "vendor/preact.mjs", "vendor/hooks.mjs"],
                   "imports": {"spaces-kit": "kit/spaces-kit.mjs", "preact": "vendor/preact.mjs",
                               "preact/hooks": "vendor/hooks.mjs"}},
    **json.loads((RUNTIME / "vendor/SHELF.json").read_text(encoding="utf-8"))["libraries"],
}
_ACCENTS = {"blue", "green", "amber", "purple", "teal", "rose", "orange", "grey"}
_THEME_PRESETS = {"editorial", "terminal", "playful", "minimal", "data", "journal", "game"}
READ_FILES_MAX = 20
READ_FILE_BYTES = 256 * 1024
READ_TOTAL_BYTES = 1024 * 1024
EDIT_FILES_MAX = 100


def _manifest(value, name, description):
    limits.object_json(value, limits.FILE_BYTES, "manifest")
    value = json.loads(limits.dumps(value))
    value.setdefault("schema", 1)
    if type(value["schema"]) is not int or value["schema"] != 1:
        raise SpacesError("invalid", "Unsupported manifest schema")
    value.setdefault("name", name)
    value.setdefault("description", description)
    limits.text(value["name"], "name")
    limits.text(value["description"], "description", nonempty=False)
    value.setdefault("entry", "index.html")
    limits.path(value["entry"])
    value.setdefault("imports", {})
    limits.object_json(value["imports"])
    for key, path in value["imports"].items():
        limits.text(key, "import name")
        limits.path(path)
    accent = value.get("accent", "blue")
    value["accent"] = accent if isinstance(accent, str) and accent in _ACCENTS else "blue"
    icon = value.get("icon", "layers")
    value["icon"] = icon if isinstance(icon, str) and re.fullmatch(r"[a-z][a-z0-9-]*", icon) else "layers"
    if "theme" in value:
        theme = value["theme"]
        limits.object_json(theme, resource="theme")
        if set(theme) - {"preset", "tokens"}:
            raise SpacesError("invalid", "Unknown theme keys; expected preset or tokens")
        if "preset" in theme:
            if not isinstance(theme["preset"], str) or theme["preset"] not in _THEME_PRESETS:
                raise SpacesError("invalid", "Unknown theme.preset")
        if "tokens" in theme:
            tokens = theme["tokens"]
            limits.object_json(tokens, resource="theme.tokens")
            if len(tokens) > 64:
                raise SpacesError("invalid", "theme.tokens must contain at most 64 tokens")
            for token, css in tokens.items():
                if not re.fullmatch(r"[a-z][a-z0-9-]{0,39}", token):
                    raise SpacesError("invalid", f"Invalid theme token name: {token}")
                if (not isinstance(css, str) or len(css) > 200
                        or any(char in css for char in ";{}<>\\")
                        or any(part in css.lower() for part in ("url(", "@import", "expression("))):
                    raise SpacesError("invalid", f"Invalid theme token value: {token}")
    value.setdefault("data", {})
    limits.object_json(value["data"])
    value["data"].setdefault("version", 1)
    limits.integer(value["data"]["version"], "data.version", minimum=1)
    collections = value["data"].get("collections", {})
    limits.object_json(collections)
    for collection, definition in collections.items():
        limits.identifier(collection, "collection")
        limits.object_json(definition)
    migrations.validate(value["data"].get("migrations", []))
    if "upkeep" in value:
        upkeep.validate_upkeep(value["upkeep"])
        limits.object_json(value["upkeep"])
        sources = value["upkeep"].get("sources", [])
        if not isinstance(sources, list):
            raise SpacesError("invalid", "upkeep.sources must be an array")
        for source in sources:
            limits.object_json(source)
            limits.text(source.get("url"), "source URL")
    return value


def _input_files(files, manifest):
    if files is None:
        files = {}
    if not isinstance(files, dict):
        raise SpacesError("invalid", "files must be an object")
    prepared, extracted = {}, None
    for path, content in files.items():
        limits.path(path)
        if content is not None and not isinstance(content, (str, bytes)):
            raise SpacesError("invalid", "File content must be text, bytes or null")
        raw = content.encode("utf-8") if isinstance(content, str) else content
        if raw is not None:
            limits.check(len(raw), limits.FILE_BYTES, "file bytes")
        if path == "space.json":
            if raw is None:
                raise SpacesError("invalid", "The Space manifest cannot be deleted")
            try:
                extracted = json.loads(raw)
            except (ValueError, UnicodeError) as exc:
                raise SpacesError("invalid", "space.json must contain a JSON object") from exc
            limits.object_json(extracted)
        else:
            prepared[path] = raw
    if manifest is not None and extracted is not None and manifest != extracted:
        raise SpacesError("invalid", "Conflicting explicit manifest and space.json")
    return prepared, manifest if manifest is not None else extracted


def _libraries(files, manifest, libraries, found, existing=()):
    if not isinstance(libraries, (tuple, list)):
        raise SpacesError("invalid", "libraries must be an array")
    for library in libraries:
        if not isinstance(library, str) or library not in _LIBRARIES:
            raise SpacesError("invalid", "Unknown bundled library")
        group = _LIBRARIES[library]
        for path in group["files"]:
            source = RUNTIME / path
            if not source.is_file():
                if path.startswith("kit/"):
                    found.append(diagnostics.diagnostic("library.file_unavailable", ref=path))
                    continue
                raise SpacesError("blocked", f"Bundled library file is unavailable: {path}", reason="no_handler")
            if path not in files and path not in existing:
                files[path] = source.read_bytes()
            for name, target in group.get("imports", {}).items():
                if path == target:
                    manifest["imports"].setdefault(name, target)


def _revision(conn, sid, rev=None):
    space = db.space(conn, sid)
    rev = space["head_rev"] if rev is None else limits.integer(rev, "rev", minimum=1)
    if rev == 0:
        return {"space": sid, "rev": 0, "manifest": _manifest({}, space["name"], space["description"]), "files": {}}
    row = conn.execute("SELECT * FROM revisions WHERE space=? AND rev=?", (sid, rev)).fetchone()
    if row is None:
        raise SpacesError("not_found", "Revision not found")
    result = dict(row)
    result["files"], result["manifest"] = json.loads(result["files"]), json.loads(result["manifest"])
    return result


def _store_files(conn, existing, changed):
    files = existing.copy()
    for path, content in changed.items():
        if content is None:
            files.pop(path, None)
        else:
            limits.check(len(content), limits.FILE_BYTES, "file bytes")
            sha = hashlib.sha256(content).hexdigest()
            conn.execute("INSERT OR IGNORE INTO blobs(sha,size,content) VALUES(?,?,?)", (sha, len(content), content))
            files[path] = sha
    limits.check(len(files), limits.PROJECT_FILES, "project files")
    size = sum(conn.execute("SELECT size FROM blobs WHERE sha=?", (sha,)).fetchone()[0] for sha in files.values())
    limits.check(size, limits.PROJECT_BYTES, "project bytes")
    return files


def _diagnose(conn, manifest, files, found=()):
    load = lambda sha: conn.execute("SELECT content FROM blobs WHERE sha=?", (sha,)).fetchone()[0]
    found = [*found, *diagnostics.diagnose(manifest, files, load)]
    return {"diagnostics": found, "warnings": [d["message"] for d in found]}


def _save_revision(conn, space, manifest, files, *, kind, author, summary, restored_from=None):
    encoded_manifest = limits.object_json(manifest, limits.FILE_BYTES, "manifest")
    rev, at = space["head_rev"] + 1, db.now()
    conn.execute("INSERT INTO revisions(space,rev,parent_rev,kind,restored_from,manifest,files,author,summary,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                 (space["id"], rev, space["head_rev"] or None, kind, restored_from,
                  encoded_manifest, limits.dumps(files), author, summary, at))
    status = "active" if manifest["entry"] in files else space["status"]
    conn.execute("UPDATE spaces SET head_rev=?,name=?,description=?,accent=?,icon=?,status=?,updated_at=? WHERE id=?",
                 (rev, manifest["name"], manifest["description"], manifest["accent"], manifest["icon"], status, at, space["id"]))
    return _revision(conn, space["id"], rev)


def create_space(name, *, description="", owner, files=None, manifest=None, libraries=(), author, summary="Created"):
    limits.text(name, "name")
    limits.text(description, "description", nonempty=False)
    limits.text(owner, "owner")
    limits.text(author, "author")
    limits.text(summary, "summary", nonempty=False)
    changed, supplied = _input_files(files, manifest)
    if any(value is None for value in changed.values()):
        raise SpacesError("invalid", "New project files cannot be null")
    normalized = _manifest(supplied if supplied is not None else {}, name, description)
    found = []
    _libraries(changed, normalized, libraries, found)
    slug = re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()).strip("-")[:48].rstrip("-")
    if len(slug) < 2:
        slug = (slug + "-space") if slug else "space"
    with db.write() as conn:
        sid, suffix = slug, 1
        while conn.execute("SELECT 1 FROM spaces WHERE id=?", (sid,)).fetchone():
            suffix += 1
            tail = f"-{suffix}"
            sid = slug[:48 - len(tail)].rstrip("-") + tail
        at = db.now()
        conn.execute("INSERT INTO spaces(id,name,description,owner,status,data_version,accent,icon,created_at,updated_at) VALUES(?,?,?,?,'building',?,?,?,?,?)",
                     (sid, normalized["name"], normalized["description"], owner, normalized["data"]["version"], normalized["accent"], normalized["icon"], at, at))
        from . import maintenance
        maintenance.create_identity(conn, sid)
        grants._seed(conn, sid, normalized, author)
        stored = {}
        if changed or supplied is not None or libraries:
            stored = _store_files(conn, {}, changed)
            _save_revision(conn, db.space(conn, sid), normalized, stored, kind="create", author=author, summary=summary)
        report = _diagnose(conn, normalized, stored, found)
    return {**get_space(sid), **report}


def _resolve(conn, ref):
    limits.text(ref, "space reference")
    rows = conn.execute("SELECT id,name FROM spaces ORDER BY id").fetchall()
    if any(row["id"] == ref for row in rows):
        return ref
    matches = [dict(row) for row in rows if row["name"].casefold() == ref.casefold()]
    if len(matches) == 1:
        return matches[0]["id"]
    if matches:
        raise SpacesError("ambiguous", "Several Spaces have that exact name", candidates=matches)
    raise SpacesError("not_found", "Space not found")


def resolve_space(ref):
    limits.text(ref, "space reference")
    with db.read() as conn:
        return _resolve(conn, ref)


def _summary(row):
    sid = row["id"]
    summary = {key: row[key] for key in ("id", "name", "description", "owner", "status", "head_rev", "accent", "icon", "pinned", "updated_at", "last_opened_at")}
    summary["pinned"] = bool(summary["pinned"])
    summary["freshness"] = runs.freshness(sid)
    summary["upkeep"] = upkeep.summary(sid)
    summary["attention"] = None
    recent = runs.list_runs(sid, limit=1)
    if recent and recent[0]["status"] in ("failed", "blocked"):
        run = recent[0]
        summary["attention"] = {"kind": run["status"], "message": run.get("error") or (run.get("detail") or {}).get("reason") or "Refresh unavailable"}
    return summary


def list_spaces(include_archived=True):
    if type(include_archived) is not bool:
        raise SpacesError("invalid", "include_archived must be a boolean")
    with db.read() as conn:
        rows = [dict(row) for row in conn.execute("SELECT * FROM spaces WHERE (? OR status!='archived') ORDER BY pinned DESC,updated_at DESC,id", (include_archived,))]
    with upkeep.read_projection([row["id"] for row in rows]):
        return [_summary(row) for row in rows]


def _head_manifest(conn, sid):
    """The head revision's manifest, without decoding its file map."""
    space = db.space(conn, sid)
    if space["head_rev"] == 0:
        return _manifest({}, space["name"], space["description"])
    row = conn.execute("SELECT manifest FROM revisions WHERE space=? AND rev=?", (sid, space["head_rev"])).fetchone()
    if row is None:
        raise SpacesError("not_found", "Revision not found")
    return json.loads(row["manifest"])


def get_space(sid):
    with db.read() as conn:
        space = dict(db.space(conn, sid))
        manifest = _head_manifest(conn, sid)
        collections = {row["collection"]: row["n"] for row in conn.execute("SELECT collection,count(*) AS n FROM records WHERE space=? GROUP BY collection", (sid,))}
        for collection in manifest.get("data", {}).get("collections", {}):
            collections.setdefault(collection, 0)
        grant_rows = [grants._grant(row) for row in conn.execute("SELECT * FROM grants WHERE space=? ORDER BY capability", (sid,))]
        from .storage import _summary as storage_summary
        storage = storage_summary(conn, sid)
        errors = conn.execute("SELECT count(*) FROM logs WHERE space=? AND level='error' AND at>=?", (sid, db.now() - 86400)).fetchone()[0]
    with upkeep.read_projection():
        result = _summary(space)
    result.update(manifest=manifest, grants=grant_rows, recent_runs=runs.list_runs(sid, limit=10),
                  data_version=space["data_version"], collections=collections, error_count_24h=errors, storage=storage)
    return result


def _content(raw):
    try:
        return {"text": raw.decode("utf-8")}
    except UnicodeError:
        return {"b64": base64.b64encode(raw).decode("ascii")}


def read_file(sid, path, rev=None):
    limits.path(path)
    with db.read() as conn:
        revision = _revision(conn, sid, rev)
        if path == "space.json":
            raw = limits.dumps(revision["manifest"]).encode("utf-8")
            sha = hashlib.sha256(raw).hexdigest()
        else:
            sha = revision["files"].get(path)
            if sha is None:
                raise SpacesError("not_found", "File not found")
            raw = conn.execute("SELECT content FROM blobs WHERE sha=?", (sha,)).fetchone()[0]
        return {"path": path, **_content(raw), "size": len(raw), "sha": sha, "rev": revision["rev"]}


def list_files(sid, rev=None):
    with db.read() as conn:
        revision = _revision(conn, sid, rev)
        return [{"path": path, "size": conn.execute("SELECT size FROM blobs WHERE sha=?", (sha,)).fetchone()[0], "sha": sha}
                for path, sha in sorted(revision["files"].items())]


def read_files(sid, paths):
    """Read one head snapshot, with bounded content and an outcome for every path."""
    if not isinstance(paths, list) or not paths:
        raise SpacesError("invalid", "paths must be a nonempty array")
    limits.check(len(paths), READ_FILES_MAX, "read paths")
    results, used = [], 0
    with db.read() as conn:
        revision = _revision(conn, sid)
        for path in paths:
            try:
                limits.path(path)
                if path == "space.json":
                    raw = limits.dumps(revision["manifest"]).encode("utf-8")
                    sha = hashlib.sha256(raw).hexdigest()
                else:
                    sha = revision["files"].get(path)
                    if sha is None:
                        raise SpacesError("not_found", "File not found")
                    size = conn.execute("SELECT size FROM blobs WHERE sha=?", (sha,)).fetchone()[0]
                    limits.check(size, READ_FILE_BYTES, "read file bytes")
                    raw = conn.execute("SELECT content FROM blobs WHERE sha=?", (sha,)).fetchone()[0]
                limits.check(len(raw), READ_FILE_BYTES, "read file bytes")
                content = _content(raw)
                size = len(next(iter(content.values())).encode("utf-8"))
                limits.check(used + size, READ_TOTAL_BYTES, "read content bytes")
                used += size
                result = {"path": path, **content, "size": len(raw), "sha": sha, "rev": revision["rev"]}
                results.append({"path": path, "ok": True, "result": result})
            except SpacesError as exc:
                results.append({"path": path, "ok": False, "error": exc.to_dict()})
    return {"space": sid, "rev": revision["rev"], "results": results}


def _introduced(found, baseline):
    identity = lambda d: (d["code"], d["path"], d.get("ref"), d.get("target"))
    remaining = Counter(identity(d) for d in baseline)
    introduced = []
    for d in found:
        if remaining[identity(d)]:
            remaining[identity(d)] -= 1
        else:
            introduced.append(d)
    return introduced


def _write(conn, sid, changed, supplied, author, summary, base_rev, libraries=(), *, validate=False):
    space = db.space(conn, sid, writable=True)
    if base_rev is not None:
        limits.integer(base_rev, "base_rev")
        if base_rev != space["head_rev"]:
            raise SpacesError("conflict", "Project revision changed", current={"head_rev": space["head_rev"]})
    old = _revision(conn, sid)
    manifest = _manifest(supplied if supplied is not None else old["manifest"], space["name"], space["description"])
    found = []
    _libraries(changed, manifest, libraries, found, existing=old["files"])
    version = manifest["data"]["version"]
    if version < space["data_version"]:
        raise SpacesError("incompatible", "Project requires an older data version", from_version=space["data_version"], to_version=version)
    recovery = None
    if version > space["data_version"]:
        recovery = records._recovery_point(conn, sid, f"Before migration to data version {version}")
    conn.execute("SAVEPOINT revision_write")
    try:
        stored = _store_files(conn, old["files"], changed)
        report = _diagnose(conn, manifest, stored, found) if validate else None
        if report:
            # A batch is rejected only for diagnostics it introduces. Warnings already present at the base head
            # are reported, not blocking; identity ignores line/column because edits shift positions.
            introduced = _introduced(report["diagnostics"], _diagnose(conn, old["manifest"], old["files"])["diagnostics"])
            if introduced:
                raise SpacesError("invalid", "Batch candidate failed project validation",
                                  diagnostics=introduced, warnings=[d["message"] for d in introduced])
        if version > space["data_version"]:
            migrations.apply(conn, sid, space["data_version"], version, manifest["data"].get("migrations", []), actor=author)
        info = _save_revision(conn, space, manifest, stored, kind="edit" if space["head_rev"] else "create", author=author, summary=summary)
        info.update(report if report is not None else _diagnose(conn, manifest, stored, found))
    except Exception as exc:
        conn.execute("ROLLBACK TO revision_write")
        conn.execute("RELEASE revision_write")
        if recovery is not None:
            if isinstance(exc, SpacesError):
                return None, SpacesError(exc.code, exc.message, **{**exc.extra, "recovery_point": recovery})
            return None, SpacesError("invalid", "Migration failed; the prior project and records were retained", recovery_point=recovery)
        raise
    conn.execute("RELEASE revision_write")
    return info, None


def write_files(sid, *, files, manifest=None, author, summary, base_rev=None, libraries=()):
    changed, supplied = _input_files(files, manifest)
    limits.text(author, "author")
    limits.text(summary, "summary", nonempty=False)
    with db.write() as conn:
        info, error = _write(conn, sid, changed, supplied, author, summary, base_rev, libraries)
    if error:
        raise error
    return info


def edit_file(sid, path, *, old, new, author, summary, base_rev=None):
    limits.path(path)
    limits.text(old, "old")
    limits.text(new, "new", nonempty=False)
    limits.text(author, "author")
    limits.text(summary, "summary", nonempty=False)
    with db.write() as conn:
        revision = _revision(conn, sid)
        if path == "space.json":
            raw = limits.dumps(revision["manifest"]).encode("utf-8")
        else:
            sha = revision["files"].get(path)
            if sha is None:
                raise SpacesError("not_found", "File not found")
            raw = conn.execute("SELECT content FROM blobs WHERE sha=?", (sha,)).fetchone()[0]
        try:
            text = raw.decode("utf-8")
        except UnicodeError as exc:
            raise SpacesError("invalid", "Cannot edit a binary file") from exc
        if text.count(old) != 1:
            raise SpacesError("invalid", "old must occur exactly once")
        changed, supplied = _input_files({path: text.replace(old, new, 1)}, None)
        info, error = _write(conn, sid, changed, supplied, author, summary, base_rev)
    if error:
        raise error
    return info


def edit_files(sid, *, edits, base_rev, author, summary):
    """Apply ordered exact replacements to one candidate and publish all or none."""
    if not isinstance(edits, list) or not edits:
        raise SpacesError("invalid", "edits must be a nonempty array")
    limits.check(len(edits), EDIT_FILES_MAX, "project edits")
    limits.text(author, "author")
    limits.text(summary, "summary", nonempty=False)
    index, path, indexes, news = 0, None, {}, {}
    with db.write() as conn:
        try:
            path = edits[0].get("path") if isinstance(edits[0], dict) else None
            limits.integer(base_rev, "base_rev")
            space = db.space(conn, sid, writable=True)
            if base_rev != space["head_rev"]:
                raise SpacesError("conflict", "Project revision changed", current={"head_rev": space["head_rev"]})
            revision, candidate = _revision(conn, sid), {}
            for index, edit in enumerate(edits):
                path = edit.get("path") if isinstance(edit, dict) else None
                if not isinstance(edit, dict) or set(edit) != {"path", "old", "new"}:
                    raise SpacesError("invalid", "Each edit requires exactly path, old and new")
                limits.path(path)
                old, new = edit["old"], edit["new"]
                if not isinstance(old, str) or not old or not isinstance(new, str):
                    raise SpacesError("invalid", "old must be nonempty text and new must be text")
                if path in candidate:
                    raw = candidate[path]
                elif path == "space.json":
                    raw = limits.dumps(revision["manifest"]).encode("utf-8")
                else:
                    sha = revision["files"].get(path)
                    if sha is None:
                        raise SpacesError("not_found", "File not found")
                    raw = conn.execute("SELECT content FROM blobs WHERE sha=?", (sha,)).fetchone()[0]
                try:
                    text = raw.decode("utf-8")
                except UnicodeError as exc:
                    raise SpacesError("invalid", "Cannot edit a binary file") from exc
                if text.count(old) != 1:
                    raise SpacesError("invalid", "old must occur exactly once")
                try:
                    raw = text.replace(old, new, 1).encode("utf-8")
                except UnicodeError as exc:
                    raise SpacesError("invalid", "Replacement must be valid UTF-8") from exc
                limits.check(len(raw), limits.FILE_BYTES, "file bytes")
                candidate[path], indexes[path] = raw, index
                news.setdefault(path, []).append((index, new))
            # Attribute manifest parsing, normalization and migration failures to its last edit.
            if "space.json" in indexes:
                index, path = indexes["space.json"], "space.json"
            changed, supplied = _input_files(candidate, None)
            info, error = _write(conn, sid, changed, supplied, author, summary, base_rev, validate=True)
            if error:
                raise error
            return info
        except SpacesError as exc:
            for diagnostic in exc.extra.get("diagnostics", []):
                affected = diagnostic["path"]
                if affected in indexes or diagnostic.get("target") in indexes:
                    path = affected if affected in indexes else diagnostic["target"]
                    # Name the last edit to that file whose replacement introduced the reference, else its last edit.
                    ref = diagnostic.get("ref")
                    index = next((i for i, text in reversed(news.get(path, [])) if ref and ref in text), indexes[path])
                    break
            raise SpacesError(exc.code, exc.message, **{**exc.extra, "edit_index": index, "path": path}) from exc


def list_revisions(sid, *, files=True):
    if type(files) is not bool:
        raise SpacesError("invalid", "files must be a boolean")
    with db.read() as conn:
        db.space(conn, sid)
        if files:
            return [_revision(conn, sid, row[0]) for row in conn.execute("SELECT rev FROM revisions WHERE space=? ORDER BY rev DESC", (sid,))]
        rows = conn.execute("SELECT space,rev,parent_rev,kind,restored_from,manifest,author,summary,created_at "
                            "FROM revisions WHERE space=? ORDER BY rev DESC", (sid,))
        return [dict(row, manifest=json.loads(row["manifest"])) for row in rows]


def restore_revision(sid, rev, *, author):
    limits.text(author, "author")
    with db.write() as conn:
        space = db.space(conn, sid, writable=True)
        target = _revision(conn, sid, rev)
        version = target["manifest"]["data"]["version"]
        if version != space["data_version"]:
            raise SpacesError("incompatible", "Code restore requires the current data version",
                              from_version=space["data_version"], to_version=version)
        result = _save_revision(conn, space, target["manifest"], target["files"], kind="restore", author=author,
                                summary=f"Restored revision {rev}", restored_from=rev)
        result.update(_diagnose(conn, target["manifest"], target["files"]))
        return result


def bundle(sid, rev=None):
    with db.read() as conn:
        space = dict(db.space(conn, sid))
        revision = _revision(conn, sid, rev)
        files = [{"path": path, "mime": mimetypes.guess_type(path)[0] or "application/octet-stream",
                  **_content(conn.execute("SELECT content FROM blobs WHERE sha=?", (sha,)).fetchone()[0])}
                 for path, sha in sorted(revision["files"].items())]
    with upkeep.read_projection():
        summary = _summary(space)
    return {"space": summary, "rev": revision["rev"], "manifest": revision["manifest"], "files": files}


def set_status(sid, status, *, actor):
    if status not in ("archived", "active", "building"):
        raise SpacesError("invalid", "Invalid Space status")
    limits.text(actor, "actor")
    from . import maintenance
    with maintenance.control(sid, "archive" if status == "archived" else "status", actor=actor) as op, maintenance.transaction(op) as conn:
        space = db.space(conn, sid)
        if status == "archived" and space["status"] != "archived":
            upkeep.pause_for_archive(conn, sid)
        if status != "archived":
            revision = _revision(conn, sid)
            status = "active" if revision["manifest"]["entry"] in revision["files"] else "building"
        conn.execute("UPDATE spaces SET status=?,archived_at=?,updated_at=? WHERE id=?",
                     (status, db.now() if status == "archived" else None, db.now(), sid))
        if status == "archived":
            conn.execute("UPDATE sessions SET closed_at=coalesce(closed_at,?) WHERE space=?", (db.now(), sid))
            runs.cancel_pending(sid, "archived")
    return get_space(sid)


def delete_space(sid, *, actor, confirm):
    limits.text(actor, "actor")
    if confirm != sid:
        raise SpacesError("invalid", "Deletion confirmation must equal the Space id")
    from . import maintenance
    with maintenance.control(sid, "delete", actor=actor) as op, maintenance.transaction(op) as conn:
        db.space(conn, sid)
        runs.cancel_pending(sid, "deleted")
        had_upkeep = upkeep.on_delete(conn, sid)
        removed = {table: conn.execute(f"SELECT count(*) FROM {table} WHERE space=?", (sid,)).fetchone()[0]
                   for table in ("records", "revisions")}
        removed["upkeep"] = had_upkeep
        for table in ("changes", "recovery_points", "audit", "sessions", "runs", "logs"):
            conn.execute(f"DELETE FROM {table} WHERE space=?", (sid,))
        conn.execute("""DELETE FROM blobs WHERE sha IN (
            SELECT file.value FROM revisions, json_each(revisions.files) AS file
            WHERE revisions.space=?
            EXCEPT
            SELECT file.value FROM revisions, json_each(revisions.files) AS file
            WHERE revisions.space!=?
        )""", (sid, sid))
        conn.execute("DELETE FROM spaces WHERE id=?", (sid,))
    return {"deleted": True, "removed": removed}


def touch_opened(sid):
    with db.write() as conn:
        db.space(conn, sid)
        conn.execute("UPDATE spaces SET last_opened_at=? WHERE id=?", (db.now(), sid))
    return get_space(sid)


def set_pinned(sid, pinned):
    if type(pinned) is not bool:
        raise SpacesError("invalid", "pinned must be a boolean")
    with db.write() as conn:
        db.space(conn, sid)
        conn.execute("UPDATE spaces SET pinned=?,updated_at=? WHERE id=?", (pinned, db.now(), sid))
    return get_space(sid)
