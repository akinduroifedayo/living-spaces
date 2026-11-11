"""Content-addressed projects and immutable code history, separate from records."""
import base64
import hashlib
import json
import mimetypes
import re
import unicodedata
from pathlib import Path

from . import db, grants, limits, migrations, records, runs, upkeep
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


def _libraries(files, manifest, libraries, warnings, existing=()):
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
                    warnings.append(f"Bundled file is not available yet: {path}")
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


def _warnings(conn, manifest, files):
    warnings = []
    if manifest["entry"] not in files:
        warnings.append(f"Entry file is missing: {manifest['entry']}")
    for name, path in manifest["imports"].items():
        if path not in files:
            warnings.append(f"Unresolved import {name}: {path}")
    for path, sha in files.items():
        if not path.endswith((".js", ".mjs", ".html", ".css")):
            continue
        content = conn.execute("SELECT content FROM blobs WHERE sha=?", (sha,)).fetchone()[0].decode("utf-8", errors="replace")
        if re.search(r"https?://(?!www\.w3\.org/)", content):
            warnings.append(f"Network URLs in {path} are blocked at runtime; use space.net.fetch for public HTTPS")
        for target in re.findall(r'''(?:from\s*|import\s*|import\s*\(\s*)["'](\.[^"']+)["']''', content):
            parts = list(Path(path).parent.parts)
            for segment in target.split("/"):
                if segment == "..":
                    if parts:
                        parts.pop()
                elif segment not in ("", "."):
                    parts.append(segment)
            if "/".join(parts) not in files:
                warnings.append(f"Unresolved relative import in {path}: {target}")
    return warnings


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
    warnings = []
    _libraries(changed, normalized, libraries, warnings)
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
        grants._seed(conn, sid, normalized, author)
        if changed or supplied is not None or libraries:
            stored = _store_files(conn, {}, changed)
            _save_revision(conn, db.space(conn, sid), normalized, stored, kind="create", author=author, summary=summary)
            warnings += _warnings(conn, normalized, stored)
        else:
            warnings.append(f"Entry file is missing: {normalized['entry']}")
    result = get_space(sid)
    result["warnings"] = warnings
    return result


def resolve_space(ref):
    limits.text(ref, "space reference")
    with db.read() as conn:
        rows = conn.execute("SELECT id,name FROM spaces ORDER BY id").fetchall()
        if any(row["id"] == ref for row in rows):
            return ref
        matches = [dict(row) for row in rows if row["name"].casefold() == ref.casefold()]
        if len(matches) == 1:
            return matches[0]["id"]
        if matches:
            raise SpacesError("ambiguous", "Several Spaces have that exact name", candidates=matches)
        raise SpacesError("not_found", "Space not found")


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
    return [_summary(row) for row in rows]


def get_space(sid):
    with db.read() as conn:
        space = dict(db.space(conn, sid))
        manifest = _revision(conn, sid)["manifest"]
        collections = {row["collection"]: row["n"] for row in conn.execute("SELECT collection,count(*) AS n FROM records WHERE space=? GROUP BY collection", (sid,))}
        for collection in manifest.get("data", {}).get("collections", {}):
            collections.setdefault(collection, 0)
        grant_rows = [grants._grant(row) for row in conn.execute("SELECT * FROM grants WHERE space=? ORDER BY capability", (sid,))]
        errors = conn.execute("SELECT count(*) FROM logs WHERE space=? AND level='error' AND at>=?", (sid, db.now() - 86400)).fetchone()[0]
    result = _summary(space)
    result.update(manifest=manifest, grants=grant_rows, recent_runs=runs.list_runs(sid, limit=10),
                  data_version=space["data_version"], collections=collections, error_count_24h=errors)
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


def _write(conn, sid, changed, supplied, author, summary, base_rev, libraries=()):
    space = db.space(conn, sid, writable=True)
    if base_rev is not None:
        limits.integer(base_rev, "base_rev")
        if base_rev != space["head_rev"]:
            raise SpacesError("conflict", "Project revision changed", current={"head_rev": space["head_rev"]})
    old = _revision(conn, sid)
    manifest = _manifest(supplied if supplied is not None else old["manifest"], space["name"], space["description"])
    warnings = []
    _libraries(changed, manifest, libraries, warnings, existing=old["files"])
    version = manifest["data"]["version"]
    if version < space["data_version"]:
        raise SpacesError("incompatible", "Project requires an older data version", from_version=space["data_version"], to_version=version)
    recovery = None
    if version > space["data_version"]:
        recovery = records._recovery_point(conn, sid, f"Before migration to data version {version}")
    conn.execute("SAVEPOINT revision_write")
    try:
        stored = _store_files(conn, old["files"], changed)
        if version > space["data_version"]:
            migrations.apply(conn, sid, space["data_version"], version, manifest["data"].get("migrations", []), actor=author)
        info = _save_revision(conn, space, manifest, stored, kind="edit" if space["head_rev"] else "create", author=author, summary=summary)
        info["warnings"] = warnings + _warnings(conn, manifest, stored)
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


def list_revisions(sid):
    with db.read() as conn:
        db.space(conn, sid)
        return [_revision(conn, sid, row[0]) for row in conn.execute("SELECT rev FROM revisions WHERE space=? ORDER BY rev DESC", (sid,))]


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
        result["warnings"] = _warnings(conn, target["manifest"], target["files"])
        return result


def bundle(sid, rev=None):
    with db.read() as conn:
        space = dict(db.space(conn, sid))
        revision = _revision(conn, sid, rev)
        files = [{"path": path, "mime": mimetypes.guess_type(path)[0] or "application/octet-stream",
                  **_content(conn.execute("SELECT content FROM blobs WHERE sha=?", (sha,)).fetchone()[0])}
                 for path, sha in sorted(revision["files"].items())]
    return {"space": _summary(space), "rev": revision["rev"], "manifest": revision["manifest"], "files": files}


def set_status(sid, status, *, actor):
    if status not in ("archived", "active", "building"):
        raise SpacesError("invalid", "Invalid Space status")
    limits.text(actor, "actor")
    with db.write() as conn:
        space = db.space(conn, sid)
        if status != "archived":
            revision = _revision(conn, sid)
            status = "active" if revision["manifest"]["entry"] in revision["files"] else "building"
        conn.execute("UPDATE spaces SET status=?,archived_at=?,updated_at=? WHERE id=?",
                     (status, db.now() if status == "archived" else None, db.now(), sid))
        if status == "archived":
            conn.execute("UPDATE sessions SET closed_at=coalesce(closed_at,?) WHERE space=?", (db.now(), sid))
    if status == "archived":
        runs.cancel_pending(sid, "archived")
        upkeep.on_archive(sid)
    return get_space(sid)


def delete_space(sid, *, actor, confirm):
    limits.text(actor, "actor")
    if confirm != sid:
        raise SpacesError("invalid", "Deletion confirmation must equal the Space id")
    with db.read() as conn:
        db.space(conn, sid)
    had_upkeep = upkeep.on_delete(sid)
    runs.cancel_pending(sid, "deleted")
    with db.write() as conn:
        db.space(conn, sid)
        removed = {table: conn.execute(f"SELECT count(*) FROM {table} WHERE space=?", (sid,)).fetchone()[0]
                   for table in ("records", "revisions")}
        removed["upkeep"] = had_upkeep
        for table in ("changes", "recovery_points", "audit", "sessions", "runs", "logs"):
            conn.execute(f"DELETE FROM {table} WHERE space=?", (sid,))
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
