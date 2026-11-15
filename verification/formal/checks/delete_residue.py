"""Delete removes a Space's data, and a new Space that reuses its id starts empty. Real projects.delete_space.

Space ids are slugs of the name (projects.py:220-228), so deleting "Garden" and creating "Garden" again yields
the same id. Rows left behind by the delete would then belong to the new Space. The desktop promises "Delete
removes this Space, all its records and revisions permanently" (src/desktop/ui/space.jsx:191).

The table list is read from the live SQLite schema, so a table added later is checked without editing this file:
  Gone       after delete_space, no table with a space column has a row for the deleted id
  Untouched  the other Space's rows are identical before and after
  Fresh      the re-created Space holds only what create_space writes (three grants and their six audit rows)
  Blobs      file contents stored only for the deleted Space are gone (blobs has no space column; finding F2)
"""
from __future__ import annotations

import json

from harness import Violation, main

UNIQUE = "<!doctype html><title>only-in-garden 7f3a</title>"


class NoCron:
    def current_cron_execution(self):
        return None

    def dispatch_tool(self, name, args):
        if args["action"] == "list":
            return json.dumps({"success": True, "count": 0, "jobs": []})
        return json.dumps({"success": False, "error": "no cron in this check"})


def space_tables(conn):
    names = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    return sorted(n for n in names if any(c[1] == "space" for c in conn.execute(f"PRAGMA table_info({n})")))


def rows(conn, table, sid):
    return sorted(tuple(r) for r in conn.execute(f"SELECT * FROM {table} WHERE space=?", (sid,)))


def populate(core, sid, content):
    from living_spaces_core import records, runs, logs, sessions, db
    records.put(sid, "plants", "fern", {"water": "weekly"}, actor="user")
    records.upsert_source(sid, "plants", "rose", {"title": "Rose"}, {"handler": "agent"}, actor="upkeep")
    records.create_recovery_point(sid, "checkpoint")
    core.write_files(sid, files={"index.html": content}, author="agent", summary="edit")
    token = sessions.open_session(sid)["session"]
    core.dispatch(sid, token, "log", {"entries": [{"level": "error", "msg": "boom"}]})
    runs.start_refresh(sid, trigger="manual", actor="user")
    core.decide(sid, "net", "revoke", actor="user")
    with db.write() as conn:
        conn.execute("INSERT INTO upkeep_links(space,cron_job_id,kind,created_at,created_by) VALUES(?,?,?,?,?)",
                     (sid, f"gone-{sid}", "feed", db.now(), "agent"))
    return token


def check(core, home):
    from living_spaces_core import db, upkeep
    upkeep.configure_context(NoCron())
    findings = {}
    garden = core.create_space("Garden", owner="Bjorn", files={"index.html": "<p>start</p>"}, author="agent")["id"]
    other = core.create_space("Kitchen", owner="Bjorn", files={"index.html": "<p>k</p>"}, author="agent")["id"]
    populate(core, garden, UNIQUE)
    populate(core, other, "<!doctype html><title>only-in-kitchen</title>")
    with db.read() as conn:
        tables = space_tables(conn)
        other_before = {t: rows(conn, t, other) for t in tables}
        populated = [t for t in tables if rows(conn, t, garden)]
        unique_sha = conn.execute("SELECT sha FROM blobs WHERE content=?", (UNIQUE.encode(),)).fetchone()[0]
        owners = {r["space"] for r in conn.execute("SELECT space,files FROM revisions")
                  if unique_sha in json.loads(r["files"]).values()}
        if owners != {garden}:
            raise Violation(f"Blobs fixture is not unique to {garden!r}: referenced by {owners}")
    core.delete_space(garden, actor="user", confirm=garden)
    with db.read() as conn:
        left = {t: rows(conn, t, garden) for t in tables if rows(conn, t, garden)}
        other_after = {t: rows(conn, t, other) for t in tables}
        blob_left = conn.execute("SELECT 1 FROM blobs WHERE sha=?", (unique_sha,)).fetchone() is not None
    if left:
        raise Violation(f"Gone: after delete_space({garden!r}) rows remain in {sorted(left)}: {left}")
    changed = [t for t in tables if other_before[t] != other_after[t]]
    if changed:
        raise Violation(f"Untouched: deleting {garden!r} changed {other!r} in {changed}")
    if blob_left:
        findings["F2"] = {"what": "file contents only the deleted Space used stay in the blobs table",
                          "example": f"after delete_space({garden!r}) blobs still holds sha {unique_sha[:12]} = {UNIQUE!r}"}
    again = core.create_space("Garden", owner="Bjorn", author="agent")["id"]
    if again != garden:
        raise Violation(f"precondition: re-created Garden got id {again!r}, expected the reused id {garden!r}")
    with db.read() as conn:
        fresh = {t: rows(conn, t, again) for t in tables}
    stale = {t: r for t, r in fresh.items() if r and t not in ("grants", "audit")}
    if stale or len(fresh["grants"]) != 3 or len(fresh["audit"]) != 6:
        raise Violation(f"Fresh: the re-created Space {again!r} inherited rows: {stale or fresh}")
    return {"space_tables": tables, "populated_before_delete": populated, "known_findings": findings}


if __name__ == "__main__":
    main(check)
