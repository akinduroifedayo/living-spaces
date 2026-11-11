"""The frame's sole backend entry point. Identity comes from the bound session."""
from . import db, grants, limits, logs, net, records, sessions
from .errors import SpacesError

_OPS = {
    "meta": (None, set(), set()),
    "net.fetch": ("net", {"url"}, {"method", "headers", "body", "as"}),
    "data.query": ("data", {"collection"}, {"where", "order", "limit", "offset"}),
    "data.get": ("data", {"collection", "id"}, set()),
    "data.put": ("data", {"collection", "data"}, {"id", "base_rev", "merge"}),
    "data.delete": ("data", {"collection", "id"}, {"base_rev"}),
    "data.batch": ("data", {"ops"}, set()),
    "refresh": ("refresh", set(), set()),
    "runs.list": (None, set(), {"limit"}),
    "log": ("logs", {"entries"}, set()),
}


def _mutate(sid, session, op, args):
    capability = _OPS[op][0]
    with db.write() as conn:
        sessions._require(conn, sid, session)
        allowed = grants._check(conn, sid, capability)
        if allowed:
            if op == "log":
                result = {"stored": logs._add_logs(conn, sid, session, args["entries"])}
            else:
                db.space(conn, sid, writable=True)
                if op == "data.batch":
                    result = records._batch(conn, sid, args["ops"], actor="app")
                else:
                    clean = args.copy()
                    clean["rid"] = clean.pop("id", None)
                    handler = records._put if op == "data.put" else records._delete
                    result = handler(conn, sid, actor="app", **clean)
    if not allowed:
        raise SpacesError("not_granted", "Capability is no longer granted", capability=capability)
    return result


def _call(sid, session, op, args):
    if op == "net.fetch":
        clean = args.copy()
        clean["as_"] = clean.pop("as", "text")
        return net.fetch(sid, **clean)
    if op == "meta":
        with db.read() as conn:
            row = db.space(conn, sid)
            space = {"id": sid, "name": row["name"], "rev": row["head_rev"]}
        return {"space": space, "grants": [row["capability"] for row in grants.list_grants(sid) if row["status"] == "granted"],
                "limits": limits.LIMITS.copy()}
    if op in ("refresh", "runs.list"):
        try:
            from . import runs
            handler = runs.start_refresh if op == "refresh" else runs.list_runs
        except (ImportError, AttributeError) as exc:
            raise SpacesError("blocked", "Upkeep handler is unavailable", reason="no_handler") from exc
        if op == "refresh":
            return handler(sid, trigger="manual", actor="app", session=session)
        return handler(sid, **args)
    if op in ("data.put", "data.delete", "data.batch", "log"):
        return _mutate(sid, session, op, args)
    if op == "data.query":
        return records.query(sid, **args)
    args = args.copy()
    args["rid"] = args.pop("id", None)
    return records.get(sid, **args)


def dispatch(sid, session, op, args):
    try:
        sessions.require(sid, session)
        if not isinstance(op, str) or op not in _OPS:
            capability = op if isinstance(op, str) else "unknown"
            with db.write() as conn:
                grants._audit(conn, sid, "app", "check", capability, "denied", {"op": capability})
            raise SpacesError("not_granted", "Operation is unavailable", capability=capability)
        capability, required, optional = _OPS[op]
        if capability:
            grants.check(sid, capability)
        limits.object_json(args)
        limits.check(len(limits.dumps({"v": 1, "id": 0, "op": op, "args": args}).encode("utf-8")),
                     limits.BRIDGE_BYTES, "bridge payload")
        clean = {key: value for key, value in args.items() if key != "space"}
        if required - clean.keys() or clean.keys() - required - optional:
            raise SpacesError("invalid", "Missing or unknown operation arguments")
        result = _call(sid, session, op, clean)
        sessions.require(sid, session)
        if capability:
            grants.check(sid, capability)
        return {"ok": True, "result": result}
    except SpacesError as exc:
        return {"ok": False, "error": exc.to_dict()}
    except Exception:
        return {"ok": False, "error": {"code": "invalid", "message": "Operation could not be completed"}}
