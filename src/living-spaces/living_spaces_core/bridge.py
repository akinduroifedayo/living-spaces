"""The frame's sole backend entry point. Identity comes from the bound session."""
import hashlib
import json
import re

from . import db, drafts, grants, limits, logs, net, records, runs, sessions
from .errors import SpacesError

_OPS = {
    "meta": (None, set(), set()),
    "net.fetch": ("net", {"url"}, {"method", "headers", "body", "as"}),
    "data.query": ("data", {"collection"}, {"where", "order", "limit", "offset", "page", "cursor"}),
    "data.get": ("data", {"collection", "id"}, set()),
    "data.put": ("data", {"collection", "data"}, {"id", "base_rev", "merge"}),
    "data.delete": ("data", {"collection", "id"}, {"base_rev"}),
    "data.batch": ("data", {"ops"}, set()),
    "draft.get": ("data", {"editor", "schema", "collection", "id"}, set()),
    "draft.put": ("data", {"editor", "schema", "collection", "id", "draft"}, set()),
    "draft.delete": ("data", {"editor", "schema", "collection", "id"}, set()),
    "editor.save": ("data", {"editor", "schema", "collection", "id", "data", "base_rev"}, set()),
    "outcome.get": (None, {"request_id"}, {"editor", "schema", "collection", "id"}),
    "bot.request": (None, {"activation_id", "text"}, {"records"}),
    "refresh": (None, set(), set()),
    "runs.list": (None, set(), {"limit"}),
    "freshness": (None, set(), set()),
    "log": ("logs", {"entries"}, {"lifecycle", "dropped", "unconfirmed"}),
}
_LOCAL_WRITES = {"data.put", "data.delete", "data.batch", "log", "editor.save"}


def _request_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", value):
        raise SpacesError("invalid", "Invalid request_id")
    return value


def _authorize(invocation):
    with db.read() as conn:
        if invocation.session is not None:
            sessions._require(conn, invocation.sid, invocation.session)
        row = db.space(conn, invocation.sid)
        if invocation.space_created_at is None:
            invocation.space_created_at = row["created_at"]
        elif invocation.space_created_at != row["created_at"]:
            raise SpacesError("session_invalid", "The original Space is no longer available")
    if invocation.capability:
        grants.check(invocation.sid, invocation.capability)


def _receipt(conn, invocation, request_id):
    return conn.execute("SELECT operation,fingerprint,confirmation FROM bridge_receipts "
                        "WHERE space=? AND space_created_at=? AND session=? AND request_id=?",
                        (invocation.sid, invocation.space_created_at, invocation.session, request_id)).fetchone()


def _lookup(sid, session, request_id):
    invocation = db.current_invocation()
    assert invocation is not None
    _request_id(request_id)
    with db.read() as conn:
        sessions._require(conn, sid, session)
        row = db.space(conn, sid)
        if row["created_at"] != invocation.space_created_at:
            raise SpacesError("session_invalid", "The original Space is no longer available")
        receipt = _receipt(conn, invocation, request_id)
    invocation.capability = _OPS[receipt["operation"]][0] if receipt else "data"
    grants.check(sid, invocation.capability)
    if receipt is None:
        return None
    invocation.effect.state = "confirmed"
    return {"found": True, "operation": receipt["operation"], "confirmation": json.loads(receipt["confirmation"])}


def _mutate(sid, session, op, args):
    invocation = db.current_invocation()
    assert invocation is not None
    proof = invocation.effect
    if proof.owner != (sid, session, op):
        raise SpacesError("invalid", "Operation ownership changed")
    capability = _OPS[op][0]
    request_id = invocation.request_id
    fingerprint = None
    if request_id is not None:
        fingerprint = hashlib.sha256(json.dumps({"op": op, "args": args}, sort_keys=True,
                                                ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")).hexdigest()
    with db.write(proof=proof) as conn:
        sessions._require(conn, sid, session)
        row = db.space(conn, sid)
        if row["created_at"] != invocation.space_created_at:
            raise SpacesError("session_invalid", "The original Space is no longer available")
        allowed = grants._check(conn, sid, capability)
        if allowed:
            receipt = _receipt(conn, invocation, request_id) if request_id is not None else None
            if receipt is not None:
                if receipt["operation"] != op or receipt["fingerprint"] != fingerprint:
                    raise SpacesError("conflict", "request_id belongs to a different operation")
                proof.state = "confirmed"
                result = json.loads(receipt["confirmation"])
            else:
                if op != "log":
                    db.space(conn, sid, writable=True)
                before = records._seq(conn, sid) if request_id is not None and op != "log" else None
                proof.state = "active"
                if op == "log":
                    result = {"stored": logs._add_logs(conn, sid, session, **args)}
                else:
                    if op == "data.batch":
                        result = records._batch(conn, sid, args["ops"], actor="app")
                    else:
                        clean = args.copy()
                        if op == "editor.save":
                            drafts.key(clean.pop("editor"), clean.pop("schema"), clean["collection"], clean["id"])
                        clean["rid"] = clean.pop("id", None)
                        handler = records._put if op in ("data.put", "editor.save") else records._delete
                        result = handler(conn, sid, actor="app", **clean)
                        if op == "editor.save":
                            drafts._delete(conn, sid, args["editor"], args["schema"], args["collection"], args["id"])
                if request_id is not None:
                    confirmation = result if op == "log" else {"changes": [dict(change) for change in conn.execute(
                        "SELECT seq,collection,record_id AS id,op,rev FROM changes WHERE space=? AND seq>? ORDER BY seq",
                        (sid, before))], "seq": records._seq(conn, sid)}
                    if op == "editor.save":
                        confirmation["editor"] = {name: args[name] for name in ("editor", "schema", "collection", "id")}
                    conn.execute("INSERT INTO bridge_receipts(space,space_created_at,session,request_id,operation,"
                                 "fingerprint,confirmation,created_at) VALUES(?,?,?,?,?,?,?,?)",
                                 (sid, row["created_at"], session, request_id, op, fingerprint,
                                  limits.dumps(confirmation), db.now()))
    if not allowed:
        raise SpacesError("not_granted", "Capability is no longer granted", capability=capability)
    return result


def _start_refresh(invocation, start):
    from . import upkeep

    with db.read() as conn:
        db.space(conn, invocation.sid, writable=True)
        row = conn.execute("SELECT manifest FROM revisions WHERE space=? AND rev=(SELECT head_rev FROM spaces WHERE id=?)",
                           (invocation.sid, invocation.sid)).fetchone()
        handler = (json.loads(row["manifest"]).get("upkeep") or {}).get("handler") if row else None
    if handler == "agent":
        if invocation.session is not None:
            raise SpacesError("blocked", "Agent upkeep runs from Refresh now in Hermes or from chat", reason="agent_from_guest")
        upkeep._scheduling_allowed()
    invocation.effect.state = "possibly_sent"
    return start()


def _refresh_outcome(result):
    from . import maintenance

    if result.get("kind") == "cron":
        if result.get("recovery") or maintenance.outcome(result.get("dispatch"), result.get("cron_job_id")) not in ("completed", "background"):
            return {"status": "unknown"}
        return {"status": "success", "confirmation": "attached"}
    if not isinstance(result.get("id"), str) or not result["id"]:
        return {"status": "unknown"}
    return {"status": "success", "confirmation": "attached", "run_id": result["id"]}


def _call(sid, session, op, args):
    if op.startswith("draft."):
        return drafts.call(sid, session, op.split(".")[1], **args)
    if op == "outcome.get" and len(args) > 1:
        if set(args) != {"editor", "schema", "collection", "id", "request_id"}:
            raise SpacesError("invalid", "Editor outcome lookup requires a complete editor key")
        db.current_invocation().capability = "data"
        grants.check(sid, "data")
        identity = {name: args[name] for name in ("editor", "schema", "collection", "id")}
        drafts.key(**identity)
        _request_id(args["request_id"])
        invocation = db.current_invocation()
        with db.read() as conn:
            sessions._require(conn, sid, session)
            rows = conn.execute("SELECT confirmation FROM bridge_receipts WHERE space=? AND space_created_at=? "
                                "AND request_id=? AND operation='editor.save'",
                                (sid, invocation.space_created_at, args["request_id"])).fetchall()
            for row in rows:
                confirmation = json.loads(row["confirmation"])
                if confirmation.get("editor") == identity:
                    invocation.effect.state = "confirmed"
                    return {"found": True, "confirmation": confirmation}
        return None
    if op == "net.fetch":
        clean = args.copy()
        clean["as_"] = clean.pop("as", "text")
        return net.fetch(sid, session=session, **clean)
    if op == "meta":
        with db.read() as conn:
            row = db.space(conn, sid)
            space = {"id": sid, "name": row["name"], "rev": row["head_rev"]}
        return {"space": space, "grants": [row["capability"] for row in grants.list_grants(sid) if row["status"] == "granted"],
                "limits": limits.LIMITS.copy()}
    if op == "bot.request":
        raise SpacesError("blocked", "Bot requests require the native Desktop action adapter")
    if op == "refresh":
        return _start_refresh(db.current_invocation(), lambda: runs.start_refresh(sid, trigger="manual", actor="app", session=session))
    if op == "runs.list":
        return runs.list_runs(sid, **args)
    if op == "outcome.get":
        return _lookup(sid, session, args["request_id"])
    if op == "freshness":
        return runs.freshness(sid, include_upkeep=False)
    if op in _LOCAL_WRITES:
        return _mutate(sid, session, op, args)
    if op == "data.query":
        return records.query(sid, **args)
    args = args.copy()
    args["rid"] = args.pop("id", None)
    return records.get(sid, **args)


def _failure(error, proof):
    status = "unknown" if proof.possible else "busy" if db.is_busy(error) else "rejected"
    if status == "unknown":
        detail = {"code": error.code if isinstance(error, SpacesError) else "ambiguous", "message": "Operation outcome is unknown"}
    elif status == "busy":
        detail = {"code": "blocked", "message": "Store is busy"}
    elif isinstance(error, SpacesError):
        detail = error.to_dict()
    else:
        detail = {"code": "invalid", "message": "Operation could not be completed"}
    return {"ok": False, "error": detail, "outcome": {"status": status}}


def _delivery_failure(invocation, error):
    # A caller that lost authority gets the authority error in place of the operation's, so detail such as a
    # conflict's current record never reaches it. The authority error itself (not_granted with its capability,
    # session_invalid) is the truthful reply and is safe to send.
    try:
        _authorize(invocation)
    except Exception as authority:
        error = authority
    return _failure(error, invocation.effect)


def dispatch(sid, session, op, args, request_id=None):
    with db.invocation(sid, session, op, request_id) as invocation:
        try:
            sessions.require(sid, session)
            _authorize(invocation)
            if not isinstance(op, str) or op not in _OPS:
                capability = op if isinstance(op, str) else "unknown"
                try:
                    with db.contention_limit(.1), db.write() as conn:
                        grants._audit(conn, sid, "app", "check", capability, "denied", {"op": capability})
                except Exception:
                    pass
                raise SpacesError("not_granted", "Operation is unavailable", capability=capability)
            capability, required, optional = _OPS[op]
            invocation.capability = capability
            if capability:
                grants.check(sid, capability)
            if request_id is not None:
                _request_id(request_id)
                if op not in _LOCAL_WRITES:
                    raise SpacesError("invalid", "request_id is only supported for local writes")
            limits.object_json(args)
            envelope = {"v": 1, "id": 0, "op": op, "args": args}
            if request_id is not None:
                envelope["request_id"] = request_id
            limits.check(len(limits.dumps(envelope).encode("utf-8")), limits.BRIDGE_BYTES, "bridge payload")
            clean = {key: value for key, value in args.items() if key != "space"}
            if required - clean.keys() or clean.keys() - required - optional:
                raise SpacesError("invalid", "Missing or unknown operation arguments")
            if op == "editor.save" and request_id is None:
                raise SpacesError("invalid", "Editor saves require a request_id")
            result = _call(sid, session, op, clean)
            _authorize(invocation)
            if op == "outcome.get" and result is None:
                return {"ok": False, "error": {"code": "ambiguous", "message": "Operation outcome is unknown"},
                        "outcome": {"status": "unknown"}}
            outcome = _refresh_outcome(result) if op == "refresh" else {"status": "success"}
            return {"ok": True, "result": result, "outcome": outcome}
        except Exception as error:
            return _delivery_failure(invocation, error)


def native_refresh(sid, start):
    with db.invocation(sid, None, "refresh") as invocation:
        try:
            _authorize(invocation)
            result = _start_refresh(invocation, start)
            _authorize(invocation)
            return {**result, "outcome": _refresh_outcome(result)}
        except Exception as error:
            return _delivery_failure(invocation, error)
