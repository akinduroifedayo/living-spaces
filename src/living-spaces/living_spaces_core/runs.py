from __future__ import annotations

import json
import threading
import uuid

from . import db, feeds
from .errors import SpacesError

STALE_SECONDS = 120
HEARTBEAT_SECONDS = 10


def _run(row):
    result = dict(row)
    result["changed"] = json.loads(result["changed"])
    result["detail"] = json.loads(result["detail"])
    return result


def get_run(run_id):
    with db.read() as conn:
        row = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    if row is None:
        raise SpacesError("not_found", "Refresh run not found")
    return _run(row)


def list_runs(sid, limit=50):
    if not isinstance(limit, int) or not 1 <= limit <= 500:
        raise SpacesError("invalid", "Run limit must be between 1 and 500")
    with db.read() as conn:
        rows = conn.execute("SELECT * FROM runs WHERE space=? ORDER BY queued_at DESC, rowid DESC LIMIT ?", (sid, limit)).fetchall()
    return [_run(row) for row in rows]


def freshness(sid):
    from . import upkeep

    with db.read() as conn:
        success = conn.execute("SELECT ended_at,source_as_of FROM runs WHERE space=? AND status='succeeded' ORDER BY ended_at DESC LIMIT 1", (sid,)).fetchone()
        attempt = conn.execute("SELECT queued_at,status FROM runs WHERE space=? ORDER BY queued_at DESC, rowid DESC LIMIT 1", (sid,)).fetchone()
    linked = upkeep.summary(sid)
    return {
        "last_success_at": success["ended_at"] if success else None,
        "last_attempt_at": attempt["queued_at"] if attempt else None,
        "last_attempt_status": attempt["status"] if attempt else None,
        "source_as_of": success["source_as_of"] if success else None,
        "next_run_at": linked["next_run_at"] if linked else None,
    }


def cancel_pending(sid, reason):
    with db.write() as conn:
        rows = conn.execute("SELECT * FROM runs WHERE space=? AND status IN ('queued','running')", (sid,)).fetchall()
        for row in rows:
            detail = json.loads(row["detail"])
            detail.setdefault("cancel_reason", reason)
            if row["status"] == "queued":
                conn.execute("UPDATE runs SET status='canceled',ended_at=?,detail=? WHERE id=?", (db.now(), json.dumps(detail), row["id"]))
            else:
                conn.execute("UPDATE runs SET detail=? WHERE id=?", (json.dumps(detail), row["id"]))
    return len(rows)


def start_refresh(sid, *, trigger, actor, wait=False, session=None):
    """Refresh now. Feed upkeep runs in-process; agent upkeep runs through native Hermes cron."""
    from . import grants, projects, sessions, upkeep

    if trigger not in ("manual", "schedule", "chat"):
        raise SpacesError("invalid", "Unknown refresh trigger")
    space = projects.get_space(sid)
    manifest_upkeep = projects.bundle(sid)["manifest"].get("upkeep") or {}
    handler = manifest_upkeep.get("handler", "")
    if handler == "agent":
        if session is not None:
            raise SpacesError("blocked", "Agent upkeep runs from Refresh now in Hermes or from chat", reason="agent_from_guest")
        return upkeep.refresh_now(sid, manifest_upkeep, actor=actor)
    reason = "archived" if space["status"] == "archived" else None
    if not reason and handler != "feed":
        reason = "no_handler"
    dispatch = upkeep.dispatch_detail(sid) if trigger == "schedule" else None
    now = db.now()
    run_id = "run_" + uuid.uuid4().hex[:16]
    with db.write() as conn:
        if session is not None:
            sessions._require(conn, sid, session)
        current = conn.execute("SELECT status FROM spaces WHERE id=?", (sid,)).fetchone()
        if current is None:
            raise SpacesError("not_found", "Space not found")
        if current["status"] == "archived":
            reason = "archived"
        if not reason and not grants._check(conn, sid, "net"):
            reason = "not_granted"
        conn.execute("UPDATE runs SET status='failed',error='interrupted',ended_at=? WHERE space=? AND status IN ('queued','running') AND COALESCE(heartbeat_at,started_at,queued_at)<?", (now, sid, now - STALE_SECONDS))
        row = conn.execute("SELECT * FROM runs WHERE space=? AND status IN ('queued','running') ORDER BY queued_at LIMIT 1", (sid,)).fetchone()
        if row:
            return _run(row)
        detail = {"reason": reason} if reason else {}
        if dispatch:
            detail["dispatch"] = dispatch
        conn.execute("INSERT INTO runs(id,space,trigger,handler,actor,status,queued_at,ended_at,changed,detail,heartbeat_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (
            run_id, sid, trigger, handler, actor, "blocked" if reason else "queued", now, now if reason else None,
            json.dumps({"added": 0, "updated": 0, "unchanged": 0, "removed": 0}), json.dumps(detail), now,
        ))
    if not reason:
        if wait:
            _work(run_id, manifest_upkeep)
        else:
            threading.Thread(target=_work, args=(run_id, manifest_upkeep), daemon=True).start()
    return get_run(run_id)


class _Canceled(Exception):
    pass


def _require_running(run_id):
    run = get_run(run_id)
    if run["status"] != "running" or run["detail"].get("cancel_reason"):
        raise _Canceled()
    with db.read() as conn:
        space = conn.execute("SELECT status FROM spaces WHERE id=?", (run["space"],)).fetchone()
    if space is None or space["status"] == "archived":
        raise _Canceled()


def _heartbeat(run_id, stop):
    while not stop.wait(HEARTBEAT_SECONDS):
        with db.write() as conn:
            updated = conn.execute("UPDATE runs SET heartbeat_at=? WHERE id=? AND status='running'", (db.now(), run_id)).rowcount
        if not updated:
            return


def _work(run_id, upkeep):
    with db.write() as conn:
        if not conn.execute("UPDATE runs SET status='running',started_at=?,heartbeat_at=? WHERE id=? AND status='queued'", (db.now(), db.now(), run_id)).rowcount:
            return
    run = get_run(run_id)
    stop = threading.Event()
    pulse = threading.Thread(target=_heartbeat, args=(run_id, stop), daemon=True)
    pulse.start()
    changed = {"added": 0, "updated": 0, "unchanged": 0, "removed": 0}
    sources = []
    source_as_of = None
    status, error = "succeeded", None
    try:
        for source in upkeep.get("sources", []):
            _require_running(run_id)
            result = {"id": source.get("id"), "ok": False, "added": 0, "updated": 0, "unchanged": 0}
            try:
                _, as_of = feeds.refresh_source(run["space"], source, actor=run["actor"], before_write=lambda: _require_running(run_id), counts=result)
                result["ok"] = True
                source_as_of = max(source_as_of or as_of, as_of)
            except _Canceled:
                raise
            except Exception as exc:
                result["error"] = str(exc)
                if isinstance(exc, SpacesError):
                    result["error_detail"] = exc.to_dict()
                    if "limit" in exc.extra and "actual" in exc.extra:
                        result["error"] += f" (limit {exc.extra['limit']}, actual {exc.extra['actual']})"
                status = "failed"
                message = f"{result['id']}: {result['error']}"
                error = message if error is None else error + f"; {message}"
            for key in ("added", "updated", "unchanged"):
                changed[key] += result[key]
            sources.append(result)
            with db.write() as conn:
                row = conn.execute("SELECT detail FROM runs WHERE id=? AND status='running'", (run_id,)).fetchone()
                if row:
                    detail = json.loads(row["detail"])
                    detail["sources"] = sources
                    conn.execute("UPDATE runs SET changed=?,source_as_of=?,detail=?,heartbeat_at=? WHERE id=?", (
                        json.dumps(changed), source_as_of, json.dumps(detail), db.now(), run_id,
                    ))
        _require_running(run_id)
    except _Canceled:
        status, error = "canceled", None
    except Exception as exc:
        status, error = "failed", str(exc)
    finally:
        stop.set()
        pulse.join()
        with db.write() as conn:
            row = conn.execute("SELECT detail FROM runs WHERE id=? AND status='running'", (run_id,)).fetchone()
            if row:
                detail = json.loads(row["detail"])
                detail["sources"] = sources
                if detail.get("cancel_reason"):
                    status, error = "canceled", None
                conn.execute("UPDATE runs SET status=?,ended_at=?,heartbeat_at=?,source_as_of=?,changed=?,error=?,detail=? WHERE id=?", (
                    status, db.now(), db.now(), source_as_of, json.dumps(changed), error, json.dumps(detail), run_id,
                ))
