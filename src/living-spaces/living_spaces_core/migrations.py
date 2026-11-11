"""Declared data migrations inside the project revision transaction."""
import json

from . import db, limits, records
from .errors import SpacesError

_FIELDS = {
    "rename_field": {"op", "collection", "from", "to"},
    "set_default": {"op", "collection", "field", "value"},
    "delete_field": {"op", "collection", "field"},
    "rename_collection": {"op", "from", "to"},
    "copy_collection": {"op", "from", "to"},
}


def validate(declarations):
    if not isinstance(declarations, list):
        raise SpacesError("invalid", "data.migrations must be an array")
    versions = set()
    for migration in declarations:
        limits.object_json(migration)
        if set(migration) != {"to", "ops"}:
            raise SpacesError("invalid", "Migrations require to and ops")
        version = limits.integer(migration["to"], "migration version", minimum=2)
        if version in versions:
            raise SpacesError("invalid", "Duplicate migration version")
        versions.add(version)
        if not isinstance(migration["ops"], list):
            raise SpacesError("invalid", "Migration ops must be an array")
        for op in migration["ops"]:
            limits.object_json(op)
            kind = op.get("op")
            if not isinstance(kind, str) or kind not in _FIELDS or set(op) != _FIELDS[kind]:
                raise SpacesError("invalid", "Unknown or malformed migration operation")
            if "collection" in op:
                limits.identifier(op["collection"], "collection")
                for field in ("from", "to", "field"):
                    if field in op:
                        limits.text(op[field], "migration field")
            else:
                limits.identifier(op["from"], "collection")
                limits.identifier(op["to"], "collection")
                if op["from"] == op["to"]:
                    raise SpacesError("invalid", "Collection migration needs different names")


def apply(conn, sid, from_version, to_version, declarations, *, actor):
    validate(declarations)
    declared = {migration["to"]: migration["ops"] for migration in declarations}
    for version in range(from_version + 1, to_version + 1):
        if version not in declared:
            raise SpacesError("invalid", f"Missing migration to data version {version}")
        for op in declared[version]:
            if op["op"] in ("rename_collection", "copy_collection"):
                _collection(conn, sid, op, actor)
            else:
                _field(conn, sid, op, actor)
    conn.execute("UPDATE spaces SET data_version=? WHERE id=?", (to_version, sid))


def _field(conn, sid, op, actor):
    rows = conn.execute("SELECT * FROM records WHERE space=? AND collection=?", (sid, op["collection"])).fetchall()
    for row in rows:
        data = json.loads(row["data"])
        before = data.copy()
        if op["op"] == "rename_field" and op["from"] in data:
            if op["to"] in data and op["to"] != op["from"]:
                raise SpacesError("invalid", "Migration would overwrite an existing field")
            data[op["to"]] = data.pop(op["from"])
        elif op["op"] == "set_default":
            data.setdefault(op["field"], op["value"])
        elif op["op"] == "delete_field":
            data.pop(op["field"], None)
        if data != before:
            records._put(conn, sid, row["collection"], row["id"], data,
                         actor=actor, base_rev=row["rev"], merge=False)


def _collection(conn, sid, op, actor):
    rows = conn.execute("SELECT * FROM records WHERE space=? AND collection=?", (sid, op["from"])).fetchall()
    for row in rows:
        if records._row(conn, sid, op["to"], row["id"]):
            raise SpacesError("invalid", "Migration target record already exists")
        if op["op"] == "copy_collection":
            records._capacity(conn, sid)
        rev, at = records._next_rev(conn, sid, op["to"], row["id"]), db.now()
        conn.execute("INSERT INTO records(space,collection,id,data,source,source_meta,rev,created_at,updated_at,updated_by) VALUES(?,?,?,?,?,?,?,?,?,?)",
                     (sid, op["to"], row["id"], row["data"], row["source"], row["source_meta"], rev, row["created_at"], at, actor))
        records._change(conn, sid, op["to"], row["id"], "put", rev, actor, at)
        if op["op"] == "rename_collection":
            records._delete(conn, sid, op["from"], row["id"], actor=actor, base_rev=row["rev"])


def grant_internet_access(conn):
    from . import grants

    purpose = grants.CAPABILITIES["net"]["default_purpose"]
    missing = conn.execute("""SELECT id FROM spaces WHERE NOT EXISTS
        (SELECT 1 FROM grants WHERE grants.space=spaces.id AND capability='net')""").fetchall()
    for row in missing:
        conn.execute("""INSERT INTO grants(space,capability,status,scope,purpose,decided_at,decided_by)
            VALUES(?,'net','granted','{}',?,?,'user')""", (row["id"], purpose, db.now()))
        grants._audit(conn, row["id"], "user", "decision", "net", "granted", {"default_on_migration": True})


def add_action_refusal_reason(conn):
    if "refusal_reason" not in {row["name"] for row in conn.execute("PRAGMA table_info(action_intents)")}:
        conn.execute("ALTER TABLE action_intents ADD COLUMN refusal_reason TEXT")


def link_native_upkeep(conn):
    """Convert legacy schedules rows to upkeep links, then drop schedules and Refresh grants."""
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='schedules'").fetchone():
        rows = conn.execute("""SELECT sc.space, sc.cron_job_id, r.manifest FROM schedules sc
            JOIN spaces s ON s.id=sc.space LEFT JOIN revisions r ON r.space=s.id AND r.rev=s.head_rev
            WHERE sc.cron_job_id IS NOT NULL AND sc.cron_job_id!=''""").fetchall()
        for row in rows:
            handler = (json.loads(row["manifest"]).get("upkeep") or {}).get("handler") if row["manifest"] else None
            conn.execute("""INSERT OR IGNORE INTO upkeep_links(space,cron_job_id,kind,created_at,created_by)
                VALUES(?,?,?,?,'migration')""", (row["space"], row["cron_job_id"],
                                                 "agent" if handler == "agent" else "feed", db.now()))
        conn.execute("DROP TABLE schedules")
    conn.execute("DELETE FROM grants WHERE capability='refresh'")
