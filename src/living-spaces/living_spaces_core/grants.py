"""Host-owned capability requests, decisions, scopes and audit history."""
import json
from urllib.parse import urlsplit

from . import db, limits
from .errors import SpacesError

CAPABILITIES = {
    "data": {"label": "Own data", "description": "Read and change this Space's own records.",
             "default_purpose": "Save and use this Space's data", "data_leaves_device": False, "continuing_access": True},
    "logs": {"label": "Diagnostics", "description": "Submit bounded runtime logs for this Space.",
             "default_purpose": "Diagnose and repair this Space", "data_leaves_device": False, "continuing_access": True},
    "refresh": {"label": "Refresh", "description": "Run declared upkeep against approved public-source hosts.",
                "default_purpose": "Keep this Space's sources current", "data_leaves_device": True, "continuing_access": True},
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

    conn.execute("INSERT INTO audit(space,at,actor,action,capability,outcome,detail) VALUES(?,?,?,?,?,?,?)",
                 (sid, db.now(), actor, action, capability, outcome, limits.dumps(redact_values(detail or {}))))


def _subset(needed, granted):
    if isinstance(needed, dict):
        return isinstance(granted, dict) and all(key in granted and _subset(value, granted[key]) for key, value in needed.items())
    if isinstance(needed, list):
        return isinstance(granted, list) and all(value in granted for value in needed)
    return needed == granted


def _scope(capability, scope):
    limits.object_json(scope)
    if capability == "refresh":
        if set(scope) - {"hosts"} or not isinstance(scope.get("hosts", []), list):
            raise SpacesError("invalid", "Refresh scope must contain a hosts array")
        if any(not isinstance(host, str) or not host or host != host.lower()
               or any(char in host for char in "/:@* ") for host in scope.get("hosts", [])):
            raise SpacesError("invalid", "Refresh hosts must be exact lowercase hostnames")
        return {"hosts": sorted(set(scope.get("hosts", [])))}
    if scope:
        raise SpacesError("invalid", "Own-data and log capabilities have no external scope")
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
    for capability in ("data", "logs"):
        purpose = CAPABILITIES[capability]["default_purpose"]
        _request(conn, sid, capability, scope={}, purpose=purpose, actor=actor)
        conn.execute("UPDATE grants SET status='granted',scope='{}',decided_at=?,decided_by='user' WHERE space=? AND capability=?",
                     (db.now(), sid, capability))
        _audit(conn, sid, "user", "decision", capability, "granted", {"default_on_create": True})
    _manifest(conn, sid, manifest, actor)


def _manifest(conn, sid, manifest, actor):
    upkeep = manifest.get("upkeep")
    if upkeep is None:
        return
    hosts = []
    for source in upkeep.get("sources", []):
        try:
            host = urlsplit(source["url"]).hostname
        except (KeyError, ValueError, TypeError) as exc:
            raise SpacesError("invalid", "Invalid upkeep source URL") from exc
        if not host:
            raise SpacesError("invalid", "Upkeep source URL requires a host")
        hosts.append(host.lower())
    scope = _scope("refresh", {"hosts": hosts})
    row = conn.execute("SELECT * FROM grants WHERE space=? AND capability='refresh'", (sid,)).fetchone()
    if row:
        current = _grant(row)
        if current["status"] == "granted" and _subset(scope, current["scope"]):
            return
        if current["status"] != "granted" and current["requested_scope"] == scope:
            return
    _request(conn, sid, "refresh", scope=scope,
             purpose=CAPABILITIES["refresh"]["default_purpose"], actor=actor)


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


def decide(sid, capability, decision, *, actor="user", scope=None):
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
        selected = _scope(capability, scope if scope is not None else current["requested_scope"] or current["scope"])
        if decision == "grant" and not _subset(selected, current["requested_scope"] or current["scope"]):
            raise SpacesError("invalid", "Grant scope exceeds the requested scope")
        status = {"grant": "granted", "deny": "denied", "revoke": "revoked"}[decision]
        conn.execute("UPDATE grants SET status=?,scope=?,decided_at=?,decided_by=? WHERE space=? AND capability=?",
                     (status, limits.dumps(selected), db.now(), actor, sid, capability))
        _audit(conn, sid, actor, "decision", capability, status, {"scope": selected})
        result = _grant(conn.execute("SELECT * FROM grants WHERE space=? AND capability=?", (sid, capability)).fetchone())
    if capability == "refresh" and decision in ("deny", "revoke"):
        try:
            from . import runs
            cancel = runs.cancel_pending
        except (ImportError, AttributeError):
            pass
        else:
            cancel(sid, "refresh revoked")
        try:
            from . import schedules
            pause = schedules.on_refresh_revoked
        except (ImportError, AttributeError):
            pass
        else:
            pause(sid, decision, actor=actor)
    return result


def audit_log(sid, limit=100):
    limits.integer(limit, "limit")
    with db.read() as conn:
        db.space(conn, sid)
        entries = [dict(row) for row in conn.execute("SELECT * FROM audit WHERE space=? ORDER BY id DESC LIMIT ?", (sid, limit))]
        for entry in entries:
            entry["detail"] = json.loads(entry["detail"])
        return entries
