"""Delete removes a Space's data, and a new Space that reuses its id starts empty. Real projects.delete_space.

Space ids are slugs of the name (projects.py:220-228), so deleting "Garden" and creating "Garden" again yields
the same id. Rows left behind by the delete would then belong to the new Space. The desktop promises "Delete
removes this Space, all its records and revisions permanently" (src/desktop/ui/space.jsx:191).

The table list is read from the live SQLite schema, so a table added later is checked without editing this file:
  Gone       after delete_space, no table with a space column has a row for the deleted id, except the
             maintenance_operations history, which is kept on purpose: "These records survive Space deletion so an
             old reply can belong to its original operation" (docs/architecture/F3-MAINTENANCE-COORDINATION.md,
             f56321d). Every kept row must belong to the deleted incarnation and be retired, so it can never fence,
             block or be joined by a Space that reuses the id.
  Untouched  the other Space's rows are identical before and after
  Fresh      the re-created Space holds only what create_space writes (three grants, their six audit rows and a new
             maintenance identity), and no kept maintenance history matches its incarnation
  Blobs      file contents stored only for the deleted Space are gone (F2, fixed in bfc0e09)
"""
from __future__ import annotations

RETAINED = "maintenance_operations"

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
    with db.read() as conn:
        incarnation = conn.execute("SELECT incarnation FROM maintenance_spaces WHERE space=?", (garden,)).fetchone()[0]
    core.delete_space(garden, actor="user", confirm=garden)
    with db.read() as conn:
        left = {t: rows(conn, t, garden) for t in tables if t != RETAINED and rows(conn, t, garden)}
        kept = [dict(r) for r in conn.execute(f"SELECT * FROM {RETAINED} WHERE space=?", (garden,))]
        other_after = {t: rows(conn, t, other) for t in tables}
        blob_left = conn.execute("SELECT 1 FROM blobs WHERE sha=?", (unique_sha,)).fetchone() is not None
    if left:
        raise Violation(f"Gone: after delete_space({garden!r}) rows remain in {sorted(left)}: {left}")
    live = [r for r in kept if r["incarnation"] != incarnation or r["phase"] != "retired"]
    if live:
        raise Violation(f"Gone: after delete_space({garden!r}) kept {RETAINED} rows are not retired history of the "
                        f"deleted incarnation {incarnation}: {live}")
    changed = [t for t in tables if other_before[t] != other_after[t]]
    if changed:
        raise Violation(f"Untouched: deleting {garden!r} changed {other!r} in {changed}")
    if blob_left:
        raise Violation(f"Blobs: after delete_space({garden!r}) blobs still holds sha {unique_sha[:12]} = {UNIQUE!r}, "
                        "content no other Space references")
    again = core.create_space("Garden", owner="Bjorn", author="agent")["id"]
    if again != garden:
        raise Violation(f"precondition: re-created Garden got id {again!r}, expected the reused id {garden!r}")
    with db.read() as conn:
        fresh = {t: rows(conn, t, again) for t in tables}
        reborn = conn.execute("SELECT incarnation FROM maintenance_spaces WHERE space=?", (again,)).fetchone()
    history = [r for r in fresh[RETAINED] if r[2] != incarnation]
    stale = {t: r for t, r in fresh.items() if r and t not in ("grants", "audit", "maintenance_spaces", RETAINED)}
    if (stale or history or len(fresh["grants"]) != 3 or len(fresh["audit"]) != 6
            or reborn is None or reborn[0] == incarnation):
        raise Violation(f"Fresh: the re-created Space {again!r} inherited rows or the deleted incarnation: "
                        f"{stale or history or fresh}")
    return {"space_tables": tables, "populated_before_delete": populated, "retained_history_rows": len(kept),
            "known_findings": {}}


if __name__ == "__main__":
    main(check)
