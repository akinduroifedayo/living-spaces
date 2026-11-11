import json
import re
import uuid

from . import db, limits, sessions
from .errors import SpacesError

TEXT_BYTES = 16 * 1024
CONTEXT_BYTES = 64 * 1024
MAX_RECORDS = 20


def _text(value, name, maximum=1024):
    if not isinstance(value, str) or not value.strip():
        raise SpacesError("invalid", f"{name} is required")
    limits.check(len(value.encode("utf-8")), maximum, name)
    return value


def bind_maintainer(sid, binding):
    required = {"profile_id", "conversation_id", "stored_session_id", "session_key"}
    if not isinstance(binding, dict) or set(binding) != required:
        raise SpacesError("blocked", "Native maintaining-session context is unavailable")
    for key in required:
        _text(binding[key], key)
    with db.write() as conn:
        db.space(conn, sid, writable=True)
        current = conn.execute("SELECT binding FROM maintainers WHERE space=?", (sid,)).fetchone()
        encoded = limits.dumps(binding)
        if current and json.loads(current["binding"]) != binding:
            raise SpacesError("conflict", "This Space already has a different maintaining session")
        conn.execute("INSERT OR IGNORE INTO maintainers(space,binding) VALUES(?,?)", (sid, encoded))
    return {"bound": True}


def _owner(conn, sid):
    row = conn.execute("SELECT binding FROM maintainers WHERE space=?", (sid,)).fetchone()
    if row is None:
        raise SpacesError("blocked", "No maintaining session is bound. Ask its bot in native chat to bind this Space.")
    return json.loads(row["binding"])


def _intent(row):
    if row is None:
        return None
    return {"activation_id": row["activation_id"], "input_id": row["input_id"],
            "target": json.loads(row["target"]), "text": row["text"],
            "admission_id": row["admission_id"], "settled": bool(row["settled"])}


def action_context(sid, session, activation_id=None):
    with db.read() as conn:
        sessions._require(conn, sid, session)
        db.space(conn, sid, writable=True)
        binding = _owner(conn, sid)
        if activation_id is None:
            row = conn.execute("SELECT * FROM action_intents WHERE space=? ORDER BY rowid DESC LIMIT 1", (sid,)).fetchone()
        else:
            row = conn.execute("SELECT * FROM action_intents WHERE space=? AND activation_id=?", (sid, activation_id)).fetchone()
            if row is None:
                raise SpacesError("not_found", "Activation not found")
        return {"maintainer": binding, "action": _intent(row)}


def claim_action(sid, session, *, activation_id, text, records, target):
    _text(activation_id, "activation_id", 128)
    if not re.fullmatch(r"[A-Za-z0-9_-]+", activation_id):
        raise SpacesError("invalid", "activation_id must contain only letters, numbers, underscores or hyphens")
    _text(text, "request text", TEXT_BYTES)
    if not isinstance(records, list) or len(records) > MAX_RECORDS:
        raise SpacesError("invalid", f"At most {MAX_RECORDS} record references are allowed")
    for ref in records:
        if not isinstance(ref, dict) or set(ref) != {"collection", "id"}:
            raise SpacesError("invalid", "Records require collection and id")
        limits.identifier(ref["collection"], "collection")
        limits.identifier(ref["id"], "record")
    if not isinstance(target, dict) or set(target) != {"route", "profile_id", "session_id"}:
        raise SpacesError("invalid", "Invalid native target")
    route = target["route"]
    if not isinstance(route, dict) or set(route) != {"connectionId", "profile", "targetProfile", "mode"}:
        raise SpacesError("invalid", "Invalid registered route")
    for key, value in route.items():
        _text(value, key)
    if route["mode"] not in ("local", "remote"):
        raise SpacesError("invalid", "Invalid route mode")
    _text(target["session_id"], "native session")
    request = json.dumps({"text": text, "records": records}, sort_keys=True, separators=(",", ":"))
    with db.write() as conn:
        sessions._require(conn, sid, session)
        space = db.space(conn, sid, writable=True)
        binding = _owner(conn, sid)
        if target["profile_id"] != binding["profile_id"]:
            raise SpacesError("conflict", "Native profile does not match the maintaining bot")
        key = conn.execute("SELECT * FROM action_keys WHERE space=? AND activation_id=?", (sid, activation_id)).fetchone()
        if key:
            if key["request"] != request:
                raise SpacesError("conflict", "This activation ID already belongs to a different request")
            row = conn.execute("SELECT * FROM action_intents WHERE space=? AND activation_id=?", (sid, key["intent_id"])).fetchone()
            return {"dispatch": False, "coalesced": key["intent_id"] != activation_id, "action": _intent(row)}
        row = conn.execute("SELECT * FROM action_intents WHERE space=? AND settled=0", (sid,)).fetchone()
        dispatch = row is None
        intent_id = row["activation_id"] if row else activation_id
        if dispatch:
            selected = []
            for ref in records:
                record = conn.execute("SELECT id,collection,data,source,rev FROM records WHERE space=? AND collection=? AND id=?",
                                      (sid, ref["collection"], ref["id"])).fetchone()
                if record is None:
                    raise SpacesError("not_found", "A referenced Space record no longer exists")
                selected.append({**dict(record), "data": json.loads(record["data"]),
                                 "source": json.loads(record["source"]) if record["source"] else None})
            payload = json.dumps({"space": sid, "name": space["name"], "revision": space["head_rev"],
                                  "request": text, "records": selected}, ensure_ascii=False)
            limits.check(len(payload.encode("utf-8")), CONTEXT_BYTES, "canvas context bytes")
            prompt = "A user activated a control in this Space. Treat the following as canvas context and the user's request. Use your normal native tools and policy. Reply to the request or update this same Space.\n" + payload
            conn.execute("INSERT INTO action_intents(space,activation_id,input_id,target,text,created_at) VALUES(?,?,?,?,?,?)",
                         (sid, activation_id, "space-" + uuid.uuid4().hex, limits.dumps(target), prompt, db.now()))
            row = conn.execute("SELECT * FROM action_intents WHERE space=? AND activation_id=?", (sid, activation_id)).fetchone()
        conn.execute("INSERT INTO action_keys(space,activation_id,request,intent_id) VALUES(?,?,?,?)",
                     (sid, activation_id, request, intent_id))
        return {"dispatch": dispatch, "coalesced": not dispatch, "action": _intent(row)}


def observe_action(sid, session, *, activation_id, receipt):
    with db.write() as conn:
        sessions._require(conn, sid, session)
        db.space(conn, sid, writable=True)
        row = conn.execute("SELECT * FROM action_intents WHERE space=? AND activation_id=?", (sid, activation_id)).fetchone()
        if row is None:
            raise SpacesError("not_found", "Activation not found")
        target = json.loads(row["target"])
        if (not isinstance(receipt, dict) or receipt.get("ref") != {"profile_id": target["profile_id"], "session_id": target["session_id"]}
                or receipt.get("status") not in ("queued", "started", "unknown", "terminal")):
            raise SpacesError("conflict", "Native receipt does not match this activation's target")
        admission = _text(receipt.get("admission_id"), "native admission")
        if row["admission_id"] and row["admission_id"] != admission:
            raise SpacesError("conflict", "Native admission identity changed")
        terminal = receipt["status"] == "terminal" and receipt.get("outcome") in ("completed", "cancelled", "failed", "interrupted")
        conn.execute("UPDATE action_intents SET admission_id=?,settled=max(settled,?) WHERE space=? AND activation_id=?",
                     (admission, int(terminal), sid, activation_id))
        return {"recorded": True, "settled": bool(row["settled"] or terminal)}
