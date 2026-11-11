import json
from urllib.parse import urlsplit

from . import db, limits
from .errors import SpacesError

CAPABILITIES = {
    "net": {"label": "Internet access", "description": "This Space can load content from and send data to the internet. It can't reach your Hermes app, your files or other Spaces.",
            "default_purpose": "Load and send internet content", "data_leaves_device": True, "continuing_access": True},
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
    if capability == "refresh":
        if set(scope) - {"hosts", "upkeep"} or not isinstance(scope.get("hosts", []), list):
            raise SpacesError("invalid", "Refresh scope must contain a hosts array")
        if any(not isinstance(host, str) or not host or host != host.lower()
               or any(char in host for char in "/:@* ") for host in scope.get("hosts", [])):
            raise SpacesError("invalid", "Refresh hosts must be exact lowercase hostnames")
        result = {"hosts": sorted(set(scope.get("hosts", [])))}
        if "upkeep" in scope:
            upkeep = scope["upkeep"]
            if (not isinstance(upkeep, dict) or set(upkeep) != {"handler", "prompt"}
                    or upkeep["handler"] != "agent" or not isinstance(upkeep["prompt"], str)
                    or not upkeep["prompt"].strip() or len(upkeep["prompt"]) > 4000):
                raise SpacesError("invalid", "Refresh upkeep scope requires handler agent and an exact prompt of at most 4000 characters")
            result["upkeep"] = dict(upkeep)
        return result
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
    scope = {"hosts": hosts}
    if upkeep.get("handler") == "agent":
        scope["upkeep"] = {"handler": "agent", "prompt": upkeep["prompt"]}
    scope = _scope("refresh", scope)
    row = conn.execute("SELECT * FROM grants WHERE space=? AND capability='refresh'", (sid,)).fetchone()
    if row:
        current = _grant(row)
        if (current["status"] == "granted" and _subset(scope, current["scope"])
                and scope.get("upkeep") == current["scope"].get("upkeep")):
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
    if allowed and capability == "refresh":
        revision = conn.execute("SELECT r.manifest FROM revisions r JOIN spaces s ON s.id=r.space AND s.head_rev=r.rev WHERE s.id=?", (sid,)).fetchone()
        upkeep = (json.loads(revision["manifest"]).get("upkeep") or {}) if revision else {}
        if upkeep.get("handler") == "agent":
            allowed = json.loads(row["scope"]).get("upkeep") == {"handler": "agent", "prompt": upkeep["prompt"]}
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
    refusal = None
    withdrawal_id = None
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
        if capability == "refresh" and decision == "grant" and current["status"] != "granted":
            from . import schedules
            reconciliation = schedules.reconcile_refresh(conn, sid, actor=actor)
            if (not reconciliation.schedule_fenced or not reconciliation.executions_quiescent
                    or reconciliation.reason is not None):
                refusal = reconciliation.reason or "Native interruption is unconfirmed"
                _audit(conn, sid, actor, "grant.blocked", capability, "blocked", {"reason": refusal})
        status = {"grant": "granted", "deny": "denied", "revoke": "revoked"}[decision]
        if refusal is None:
            conn.execute("UPDATE grants SET status=?,scope=?,decided_at=?,decided_by=? WHERE space=? AND capability=?",
                         (status, limits.dumps(selected), db.now(), actor, sid, capability))
            decision_id = _audit(conn, sid, actor, "decision", capability, status, {"scope": selected})
            if capability == "refresh" and decision in ("deny", "revoke"):
                from . import runs, schedules
                withdrawal_id = decision_id
                schedules.on_refresh_revoked(sid, decision, actor=actor, conn=conn)
                runs.cancel_pending(sid, "refresh revoked", conn=conn)
        result = _grant(conn.execute("SELECT * FROM grants WHERE space=? AND capability=?", (sid, capability)).fetchone())
    if refusal is not None:
        raise SpacesError("blocked", "Cannot grant Refresh until native interruption is confirmed", reason=refusal)
    if withdrawal_id is not None:
        with db.write() as conn:
            schedules.reconcile_refresh(conn, sid, actor=actor, expected_withdrawal_audit_id=withdrawal_id)
    return result


def audit_log(sid, limit=100):
    limits.integer(limit, "limit")
    with db.read() as conn:
        db.space(conn, sid)
        entries = [dict(row) for row in conn.execute("SELECT * FROM audit WHERE space=? ORDER BY id DESC LIMIT ?", (sid, limit))]
        for entry in entries:
            entry["detail"] = json.loads(entry["detail"])
        return entries
