"""Authoritative records with optimistic concurrency and an ordered change cursor."""
import json
import secrets

from . import db, limits
from .errors import SpacesError


def _record(row):
    return {key: json.loads(row[key]) if key in ("data", "source", "source_meta") and row[key] is not None
            else row[key] for key in row.keys() if key != "space"}


def _row(conn, sid, collection, rid):
    return conn.execute("SELECT * FROM records WHERE space=? AND collection=? AND id=?",
                        (sid, collection, rid)).fetchone()


def _ids(collection, rid):
    limits.identifier(collection, "collection")
    limits.identifier(rid, "record")


def _seq(conn, sid):
    return conn.execute("SELECT coalesce(max(seq),0) FROM changes WHERE space=?", (sid,)).fetchone()[0]


def _next_rev(conn, sid, collection, rid):
    return conn.execute("SELECT coalesce(max(rev),0)+1 FROM changes WHERE space=? AND collection=? AND record_id=?",
                        (sid, collection, rid)).fetchone()[0]


def _change(conn, sid, collection, rid, op, rev, actor, at):
    conn.execute("INSERT INTO changes(space,collection,record_id,op,rev,actor,at) VALUES(?,?,?,?,?,?,?)",
                 (sid, collection, rid, op, rev, actor, at))


def _capacity(conn, sid):
    count = conn.execute("SELECT count(*) FROM records WHERE space=?", (sid,)).fetchone()[0]
    limits.check(count + 1, limits.RECORDS, "records")


def _concurrency(row, base_rev):
    if base_rev is not None:
        limits.integer(base_rev, "base_rev")
    if (row is None and base_rev not in (None, 0)) or (row is not None and base_rev != row["rev"]):
        raise SpacesError("conflict", "Record changed; read current before retrying",
                          current=_record(row) if row else None)


def _put(conn, sid, collection, rid, data, *, actor, base_rev=None, merge=True):
    rid = rid if rid is not None else "r_" + secrets.token_hex(6)
    _ids(collection, rid)
    limits.object_json(data, limits.DATA_BYTES, "record data")
    limits.text(actor, "actor")
    if type(merge) is not bool:
        raise SpacesError("invalid", "merge must be a boolean")
    row = _row(conn, sid, collection, rid)
    _concurrency(row, base_rev)
    merged = {**json.loads(row["data"]), **data} if row and merge else data
    encoded = limits.object_json(merged, limits.DATA_BYTES, "record data")
    at, rev = db.now(), _next_rev(conn, sid, collection, rid)
    if row:
        conn.execute("UPDATE records SET data=?,rev=?,updated_at=?,updated_by=? WHERE space=? AND collection=? AND id=?",
                     (encoded, rev, at, actor, sid, collection, rid))
    else:
        _capacity(conn, sid)
        conn.execute("INSERT INTO records(space,collection,id,data,rev,created_at,updated_at,updated_by) VALUES(?,?,?,?,?,?,?,?)",
                     (sid, collection, rid, encoded, rev, at, at, actor))
    _change(conn, sid, collection, rid, "put", rev, actor, at)
    return _record(_row(conn, sid, collection, rid))


def put(sid, collection, rid, data, *, actor, base_rev=None, merge=True):
    with db.write() as conn:
        db.space(conn, sid, writable=True)
        return _put(conn, sid, collection, rid, data, actor=actor, base_rev=base_rev, merge=merge)


def _delete(conn, sid, collection, rid, *, actor, base_rev=None):
    _ids(collection, rid)
    limits.text(actor, "actor")
    row = _row(conn, sid, collection, rid)
    if row is None:
        raise SpacesError("not_found", "Record not found")
    _concurrency(row, base_rev)
    rev = _next_rev(conn, sid, collection, rid)
    conn.execute("DELETE FROM records WHERE space=? AND collection=? AND id=?", (sid, collection, rid))
    _change(conn, sid, collection, rid, "delete", rev, actor, db.now())
    return {"deleted": True}


def delete(sid, collection, rid, *, actor, base_rev=None):
    with db.write() as conn:
        db.space(conn, sid, writable=True)
        return _delete(conn, sid, collection, rid, actor=actor, base_rev=base_rev)


def get(sid, collection, rid):
    _ids(collection, rid)
    with db.read() as conn:
        db.space(conn, sid)
        row = _row(conn, sid, collection, rid)
        if row is None:
            raise SpacesError("not_found", "Record not found")
        return _record(row)


def _field(record, name):
    value = record["data"].get(name)
    return value if value is not None else (record["source"] or {}).get(name)


def query(sid, collection, *, where=None, order=None, limit=500, offset=0):
    limits.identifier(collection, "collection")
    limits.integer(limit, "limit")
    limits.integer(offset, "offset")
    if where is not None:
        limits.object_json(where)
    if order is not None:
        limits.text(order, "order")
    with db.read() as conn:
        db.space(conn, sid)
        rows = [_record(row) for row in conn.execute("SELECT * FROM records WHERE space=? AND collection=? ORDER BY id",
                                                    (sid, collection))]
        rows = [row for row in rows if all(_field(row, field) == value for field, value in (where or {}).items())]
        def sort_key(record):
            value = _field(record, order.lstrip("-")) if order else None
            if value is None:
                value = record["updated_at"]
            if isinstance(value, (int, float)):
                return (0, value, record["id"])
            return (1, value if isinstance(value, str) else limits.dumps(value), record["id"])
        rows.sort(key=sort_key, reverse=bool(order and order.startswith("-")))
        return {"records": rows[offset:offset + limit], "total": len(rows), "seq": _seq(conn, sid)}


def _batch(conn, sid, ops, *, actor):
    if not isinstance(ops, list):
        raise SpacesError("invalid", "ops must be an array")
    limits.check(len(ops), limits.BATCH_OPS, "batch ops")
    results = []
    for index, op in enumerate(ops):
        try:
            limits.object_json(op)
            kind = op.get("op")
            allowed = {"op", "collection", "id", "base_rev", "space"}
            if kind == "put":
                allowed |= {"data", "merge"}
            if kind not in ("put", "delete") or set(op) - allowed:
                raise SpacesError("invalid", "Invalid batch operation")
            if "collection" not in op or (kind == "put" and "data" not in op) or (kind == "delete" and "id" not in op):
                raise SpacesError("invalid", "Missing batch operation fields")
            args = {key: value for key, value in op.items() if key not in ("op", "space")}
            args["rid"] = args.pop("id", None)
            results.append((_put if kind == "put" else _delete)(conn, sid, actor=actor, **args))
        except SpacesError as exc:
            raise SpacesError(exc.code, exc.message, **{**exc.extra, "op_index": index}) from exc
    return {"results": results, "seq": _seq(conn, sid)}


def batch(sid, ops, *, actor):
    with db.write() as conn:
        db.space(conn, sid, writable=True)
        return _batch(conn, sid, ops, actor=actor)


def _upsert_source(conn, sid, collection, rid, source, source_meta, *, actor):
    _ids(collection, rid)
    encoded = limits.object_json(source, limits.SOURCE_BYTES, "record source")
    meta = limits.object_json(source_meta, limits.SOURCE_BYTES, "source metadata")
    limits.text(actor, "actor")
    row = _row(conn, sid, collection, rid)
    if row and json.loads(row["source"] or "null") == source:
        previous_meta = json.loads(row["source_meta"] or "{}")
        stable_meta = {key: value for key, value in source_meta.items() if key != "fetched_at"}
        previous_stable = {key: value for key, value in previous_meta.items() if key != "fetched_at"}
        # Fetch timestamps alone do not turn an unchanged source into a record edit.
        if stable_meta == previous_stable:
            return "unchanged"
    at, rev = db.now(), _next_rev(conn, sid, collection, rid)
    if row:
        conn.execute("UPDATE records SET source=?,source_meta=?,rev=?,updated_at=?,updated_by=? WHERE space=? AND collection=? AND id=?",
                     (encoded, meta, rev, at, actor, sid, collection, rid))
    else:
        _capacity(conn, sid)
        conn.execute("INSERT INTO records(space,collection,id,source,source_meta,rev,created_at,updated_at,updated_by) VALUES(?,?,?,?,?,?,?,?,?)",
                     (sid, collection, rid, encoded, meta, rev, at, at, actor))
    _change(conn, sid, collection, rid, "source", rev, actor, at)
    return "updated" if row else "added"


def upsert_source(sid, collection, rid, source, source_meta, *, actor):
    with db.write() as conn:
        db.space(conn, sid, writable=True)
        return _upsert_source(conn, sid, collection, rid, source, source_meta, actor=actor)


def upsert_sources(sid, collection, entries, *, actor):
    from . import feeds, grants

    if not isinstance(entries, list):
        raise SpacesError("invalid", "entries must be an array")
    limits.check(len(entries), limits.BATCH_OPS, "source entries")
    limits.identifier(collection, "collection")
    limits.text(actor, "actor")
    counts = {"added": 0, "updated": 0, "unchanged": 0}
    with db.write() as conn:
        db.space(conn, sid, writable=True)
        hosts = set()
        for entry in entries:
            if not isinstance(entry, (tuple, list)) or len(entry) != 3:
                raise SpacesError("invalid", "Source entries must contain id, source and metadata")
            rid, source, source_meta = entry
            result = _upsert_source(conn, sid, collection, rid, source, source_meta, actor=actor)
            counts[result] += 1
            if source_meta.get("handler") == "feed":
                hosts.add(feeds.source_host(source_meta["url"]))
        # The write lock keeps revocation from racing this check and the commit.
        if hosts and not grants._check(conn, sid, "refresh", {"hosts": sorted(hosts)}):
            raise SpacesError("not_granted", "Capability or requested scope is not granted", capability="refresh")
    return counts


def changes_since(sid, seq, limit=500):
    limits.integer(seq, "seq")
    limits.integer(limit, "limit", minimum=1)
    with db.read() as conn:
        db.space(conn, sid)
        rows = [dict(row) for row in conn.execute(
            "SELECT seq,collection,record_id AS id,op,rev,actor,at FROM changes WHERE space=? AND seq>? ORDER BY seq LIMIT ?",
            (sid, seq, limit))]
        return {"seq": rows[-1]["seq"] if rows else max(seq, _seq(conn, sid)), "changes": rows}


def _recovery_point(conn, sid, reason):
    space = db.space(conn, sid)
    limits.text(reason, "reason")
    snapshot = [_record(row) for row in conn.execute("SELECT * FROM records WHERE space=? ORDER BY collection,id", (sid,))]
    return conn.execute("INSERT INTO recovery_points(space,reason,data_version,head_rev,snapshot,created_at) VALUES(?,?,?,?,?,?)",
                        (sid, reason, space["data_version"], space["head_rev"], limits.dumps(snapshot), db.now())).lastrowid


def create_recovery_point(sid, reason):
    with db.write() as conn:
        return _recovery_point(conn, sid, reason)


def list_recovery_points(sid):
    with db.read() as conn:
        db.space(conn, sid)
        return [dict(row) for row in conn.execute(
            "SELECT id,space,reason,data_version,head_rev,created_at FROM recovery_points WHERE space=? ORDER BY id DESC", (sid,))]


def restore_recovery_point(sid, id, *, actor):
    limits.integer(id, "recovery point id", minimum=1)
    limits.text(actor, "actor")
    with db.write() as conn:
        space = db.space(conn, sid, writable=True)
        point = conn.execute("SELECT * FROM recovery_points WHERE space=? AND id=?", (sid, id)).fetchone()
        if point is None:
            raise SpacesError("not_found", "Recovery point not found")
        if point["data_version"] != space["data_version"]:
            raise SpacesError("incompatible", "Recovery point has a different data version",
                              from_version=space["data_version"], to_version=point["data_version"])
        fresh = _recovery_point(conn, sid, "Before recovery point restore")
        snapshot = json.loads(point["snapshot"])
        old = {(row["collection"], row["id"]): row for row in conn.execute("SELECT * FROM records WHERE space=?", (sid,))}
        target = {(item["collection"], item["id"]) for item in snapshot}
        for (collection, rid), row in old.items():
            if (collection, rid) not in target:
                _delete(conn, sid, collection, rid, actor=actor, base_rev=row["rev"])
        for item in snapshot:
            collection, rid = item["collection"], item["id"]
            rev, at = _next_rev(conn, sid, collection, rid), db.now()
            conn.execute("INSERT OR REPLACE INTO records(space,collection,id,data,source,source_meta,rev,created_at,updated_at,updated_by) VALUES(?,?,?,?,?,?,?,?,?,?)",
                         (sid, collection, rid, limits.dumps(item["data"]),
                          limits.dumps(item["source"]) if item["source"] is not None else None,
                          limits.dumps(item["source_meta"]) if item["source_meta"] is not None else None,
                          rev, item["created_at"], at, actor))
            _change(conn, sid, collection, rid, "put", rev, actor, at)
        return {"restored": id, "recovery_point": fresh, "records": len(snapshot), "seq": _seq(conn, sid)}
