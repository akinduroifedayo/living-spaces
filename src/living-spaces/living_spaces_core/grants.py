import json

from . import db, limits
from .errors import SpacesError

CAPABILITIES = {
    "net": {"label": "Internet access", "description": "This Space can load content from and send data to the internet. It can't reach your Hermes app, your files or other Spaces.",
            "default_purpose": "Load and send internet content", "data_leaves_device": True, "continuing_access": True},
    "data": {"label": "Own data", "description": "Read and change this Space's own records.",
             "default_purpose": "Save and use this Space's data", "data_leaves_device": False, "continuing_access": True},
    "logs": {"label": "Diagnostics", "description": "Submit bounded runtime logs for this Space.",
             "default_purpose": "Diagnose and repair this Space", "data_leaves_device": False, "continuing_access": True},
}
FUTURE = {
    "sites": {"label": "Approved sites"}, "camera": {"label": "Camera"},
    "microphone": {"label": "Microphone"}, "location": {"label": "Location"},
    "tool:*": {"label": "Hermes tools"}, "files": {"label": "Selected files"},
    "cross_space": {"label": "Other Spaces"}, "agent.ask": {"label": "Ask the agent"},
}


def _grant(row):
    result = dict(row)
    for key in ("scope", "requested_scope"):
        result[key] = json.loads(result[key]) if result[key] is not None else None
    return result


def _audit(conn, sid, actor, action, capability, outcome, detail=None):
    from .logs import redact_values

    return conn.execute("INSERT INTO audit(space,at,actor,action,capability,outcome,detail) VALUES(?,?,?,?,?,?,?)",
                        (sid, db.now(), actor, action, capability, outcome, limits.dumps(redact_values(detail or {})))).lastrowid


def _subset(needed, granted):
    if isinstance(needed, dict):
        return isinstance(granted, dict) and all(key in granted and _subset(value, granted[key]) for key, value in needed.items())
    if isinstance(needed, list):
        return isinstance(granted, list) and all(value in granted for value in needed)
    return needed == granted


def _scope(capability, scope):
    limits.object_json(scope)
    if scope:
        raise SpacesError("invalid", "This capability has no external scope")
    return {}


def _request(conn, sid, capability, *, scope, purpose, actor):
    if not isinstance(capability, str) or capability not in CAPABILITIES:
        raise SpacesError("invalid", "Capability is not available in release 1")
    scope = _scope(capability, scope)
    limits.text(purpose, "purpose", nonempty=False)
    limits.text(actor, "actor")
    at = db.now()
    conn.execute("""INSERT INTO grants(space,capability,status,scope,purpose,requested_scope,requested_at)
        VALUES(?,?,'requested','{}',?,?,?) ON CONFLICT(space,capability) DO UPDATE SET
        status='requested',purpose=excluded.purpose,requested_scope=excluded.requested_scope,requested_at=excluded.requested_at""",
                 (sid, capability, purpose, limits.dumps(scope), at))
    _audit(conn, sid, actor, "request", capability, "requested", {"scope": scope, "purpose": purpose})
    return _grant(conn.execute("SELECT * FROM grants WHERE space=? AND capability=?", (sid, capability)).fetchone())


def _seed(conn, sid, manifest, actor):
    for capability in ("data", "logs", "net"):
        purpose = CAPABILITIES[capability]["default_purpose"]
        _request(conn, sid, capability, scope={}, purpose=purpose, actor=actor)
        conn.execute("UPDATE grants SET status='granted',scope='{}',decided_at=?,decided_by='default' WHERE space=? AND capability=?",
                     (db.now(), sid, capability))
        _audit(conn, sid, "default", "decision", capability, "granted", {"default_on_create": True})


def list_grants(sid):
    with db.read() as conn:
        db.space(conn, sid)
        return [_grant(row) for row in conn.execute("SELECT * FROM grants WHERE space=? ORDER BY capability", (sid,))]


def _check(conn, sid, capability, scope_need=None):
    need = scope_need if scope_need is not None else {}
    limits.object_json(need)
    limits.text(capability, "capability")
    row = conn.execute("SELECT * FROM grants WHERE space=? AND capability=?", (sid, capability)).fetchone()
    allowed = row is not None and row["status"] == "granted" and _subset(need, json.loads(row["scope"]))
    if not allowed:
        _audit(conn, sid, "app", "check", capability, "denied", {"scope_need": need})
    return allowed


def check(sid, capability, scope_need=None):
    with db.write() as conn:
        db.space(conn, sid)
        allowed = _check(conn, sid, capability, scope_need)
    if not allowed:
        raise SpacesError("not_granted", "Capability or requested scope is not granted", capability=capability)


def request(sid, capability, *, scope, purpose, actor):
    with db.write() as conn:
        db.space(conn, sid, writable=True)
        return _request(conn, sid, capability, scope=scope, purpose=purpose, actor=actor)


def decide(sid, capability, decision, *, actor="user", scope=None, requested_scope=None):
    limits.text(capability, "capability")
    if decision not in ("grant", "deny", "revoke"):
        raise SpacesError("invalid", "Decision must be grant, deny or revoke")
    limits.text(actor, "actor")
    with db.write() as conn:
        db.space(conn, sid)
        row = conn.execute("SELECT * FROM grants WHERE space=? AND capability=?", (sid, capability)).fetchone()
        if row is None:
            raise SpacesError("not_found", "Capability request not found")
        current = _grant(row)
        if decision == "grant" and requested_scope is not None:
            displayed = _scope(capability, requested_scope)
            if displayed != (current["requested_scope"] if current["requested_scope"] is not None else current["scope"]):
                raise SpacesError("conflict", "Permission request changed. Review the current request before approving.",
                                  current=current)
        selected = _scope(capability, scope if scope is not None else current["requested_scope"] or current["scope"])
        if decision == "grant" and not _subset(selected, current["requested_scope"] or current["scope"]):
            raise SpacesError("invalid", "Grant scope exceeds the requested scope")
        status = {"grant": "granted", "deny": "denied", "revoke": "revoked"}[decision]
        conn.execute("UPDATE grants SET status=?,scope=?,decided_at=?,decided_by=? WHERE space=? AND capability=?",
                     (status, limits.dumps(selected), db.now(), actor, sid, capability))
        _audit(conn, sid, actor, "decision", capability, status, {"scope": selected})
        return _grant(conn.execute("SELECT * FROM grants WHERE space=? AND capability=?", (sid, capability)).fetchone())


def audit_log(sid, limit=100):
    limits.integer(limit, "limit")
    with db.read() as conn:
        db.space(conn, sid)
        entries = [dict(row) for row in conn.execute("SELECT * FROM audit WHERE space=? ORDER BY id DESC LIMIT ?", (sid, limit))]
        for entry in entries:
            entry["detail"] = json.loads(entry["detail"])
        return entries
