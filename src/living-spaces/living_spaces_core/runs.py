from __future__ import annotations

import importlib
import json
import threading
import uuid
from datetime import datetime

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
    if row["handler"] == "agent" and row["status"] in ("queued", "running"):
        _sync_agent_runs(row["space"])
        with db.read() as conn:
            row = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    return _run(row)


def list_runs(sid, limit=50):
    if not isinstance(limit, int) or not 1 <= limit <= 500:
        raise SpacesError("invalid", "Run limit must be between 1 and 500")
    _sync_agent_runs(sid)
    with db.read() as conn:
        rows = conn.execute("SELECT * FROM runs WHERE space=? ORDER BY queued_at DESC, rowid DESC LIMIT ?", (sid, limit)).fetchall()
    return [_run(row) for row in rows]


def freshness(sid):
    from . import schedules

    _sync_agent_runs(sid)
    with db.read() as conn:
        success = conn.execute("SELECT ended_at,source_as_of FROM runs WHERE space=? AND status='succeeded' ORDER BY ended_at DESC LIMIT 1", (sid,)).fetchone()
        attempt = conn.execute("SELECT queued_at,status FROM runs WHERE space=? ORDER BY queued_at DESC, rowid DESC LIMIT 1", (sid,)).fetchone()
    schedule = schedules.get_schedule(sid)
    return {
        "last_success_at": success["ended_at"] if success else None,
        "last_attempt_at": attempt["queued_at"] if attempt else None,
        "last_attempt_status": attempt["status"] if attempt else None,
        "source_as_of": success["source_as_of"] if success else None,
        "next_run_at": schedule["next_run_at"] if schedule else None,
    }


def cancel_pending(sid, reason):
    from . import schedules

    with db.write() as conn:
        schedule = conn.execute("SELECT cron_job_id FROM schedules WHERE space=?", (sid,)).fetchone()
        if schedule and schedule["cron_job_id"]:
            schedules._cron().pause_job(schedule["cron_job_id"], reason=reason)
        _sync_agent_runs(sid, conn=conn)
        rows = conn.execute("SELECT * FROM runs WHERE space=? AND status IN ('queued','running')", (sid,)).fetchall()
        canceled_jobs = set()
        for row in rows:
            detail = json.loads(row["detail"])
            detail["cancel_reason"] = reason
            if row["handler"] == "agent" and detail.get("cron_job_id") not in canceled_jobs and detail.get("cron_job_id"):
                canceled_jobs.add(detail["cron_job_id"])
                jobs = schedules._cron()
                if detail.get("one_shot"):
                    jobs.remove_job(detail["cron_job_id"])
                else:
                    jobs.pause_job(detail["cron_job_id"], reason=reason)
                    jobs.cancel_job_run(detail["cron_job_id"], reason=reason)
            if row["status"] == "queued" or row["handler"] == "agent":
                conn.execute("UPDATE runs SET status='canceled',ended_at=?,detail=? WHERE id=?", (db.now(), json.dumps(detail), row["id"]))
            else:
                conn.execute("UPDATE runs SET detail=? WHERE id=?", (json.dumps(detail), row["id"]))
    return len(rows)


def _timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() if value else None


def _sync_agent_runs(sid, *, conn=None):
    from . import schedules

    if conn is None:
        with db.write() as conn:
            return _sync_agent_runs(sid, conn=conn)
    schedule = conn.execute("SELECT cron_job_id FROM schedules WHERE space=?", (sid,)).fetchone()
    pending = conn.execute("SELECT * FROM runs WHERE space=? AND handler='agent' AND status IN ('queued','running')", (sid,)).fetchall()
    job_ids = {json.loads(row["detail"]).get("cron_job_id") for row in pending}
    if schedule:
        job_ids.add(schedule["cron_job_id"])
    job_ids.discard(None)
    if not job_ids:
        return
    try:
        jobs = schedules._cron()
        agent_jobs = {jid: jobs.get_job(jid) for jid in job_ids}
        agent_jobs = {jid: job for jid, job in agent_jobs.items() if not job or job.get("no_agent") is False}
        if not agent_jobs:
            return
        ledger = importlib.import_module("cron.executions")
    except ImportError:
        return
    statuses = {"claimed": "queued", "running": "running", "completed": "succeeded", "failed": "failed", "unknown": "failed", "cancelled": "canceled", "missed": "blocked"}
    for jid, job in agent_jobs.items():
        executions = ledger.list_executions(job_id=jid, limit=500)
        page = executions
        while len(page) == 500:
            page = ledger.list_executions(job_id=jid, limit=500, before_claimed_at=page[-1]["claimed_at"])
            executions.extend(page)
        cleanup = False
        if conn.execute("SELECT 1 FROM spaces WHERE id=?", (sid,)).fetchone() is None:
            continue
        for execution in reversed(executions):
            status = statuses.get(execution["status"])
            if status is None:
                continue
            claimed = _timestamp(execution["claimed_at"])
            row = conn.execute("SELECT * FROM runs WHERE space=? AND json_extract(detail,'$.cron_run_id')=?", (sid, execution["id"])).fetchone()
            if row is None and execution["status"] != "missed":
                row = conn.execute("SELECT * FROM runs WHERE space=? AND handler='agent' AND status='queued' AND json_extract(detail,'$.cron_job_id')=? AND json_extract(detail,'$.cron_run_id') IS NULL AND queued_at<=? ORDER BY queued_at LIMIT 1", (sid, jid, claimed)).fetchone()
            if row is None:
                rid = "run_cron_" + execution["id"]
                conn.execute("INSERT OR IGNORE INTO runs(id,space,trigger,handler,actor,status,queued_at) VALUES(?,?,'schedule','agent','upkeep:schedule','queued',?)", (rid, sid, claimed))
                row = conn.execute("SELECT * FROM runs WHERE id=?", (rid,)).fetchone()
            detail = json.loads(row["detail"])
            if detail.get("cancel_reason"):
                continue
            if row["status"] in ("succeeded", "failed", "canceled", "blocked") and status in ("queued", "running"):
                continue
            if detail.get("cron_status") == execution["status"]:
                continue
            detail.update(cron_job_id=jid, cron_run_id=execution["id"], cron_status=execution["status"], changed_unavailable=True)
            if execution["status"] == "missed":
                detail["reason"] = execution.get("error") or "Scheduled occurrence missed"
            if execution.get("scheduled_instant"):
                detail["scheduled_instant"] = execution["scheduled_instant"]
            conn.execute("UPDATE runs SET status=?,started_at=?,ended_at=?,error=?,detail=?,heartbeat_at=? WHERE id=?", (
                status, _timestamp(execution.get("started_at")), _timestamp(execution.get("finished_at")), execution.get("error"), json.dumps(detail), db.now(), row["id"],
            ))
            cleanup = cleanup or (detail.get("one_shot", False) and status in ("succeeded", "failed", "canceled"))
        if job is None:
            conn.execute("UPDATE runs SET status='failed',error='Native cron job is missing',ended_at=? WHERE space=? AND handler='agent' AND status IN ('queued','running') AND json_extract(detail,'$.cron_job_id')=?", (db.now(), sid, jid))
        if cleanup and job:
            jobs.remove_job(jid)


def _queue_agent(conn, sid, run_id, upkeep):
    from . import schedules

    jobs = schedules._cron()
    prompt = schedules.agent_prompt(sid, upkeep)
    job = jobs.create_job(prompt=prompt, schedule="in 1m", repeat=1, name=f"living-spaces:{sid}:{run_id}", no_agent=False, deliver="local", catch_up=True, paused=True)
    detail = {"cron_job_id": job["id"], "one_shot": True, "changed_unavailable": True}
    conn.execute("UPDATE runs SET detail=? WHERE id=?", (json.dumps(detail), run_id))
    try:
        if jobs.trigger_job(job["id"]) is None:
            raise RuntimeError("Native cron job could not be triggered")
    except Exception:
        jobs.remove_job(job["id"])
        raise


def start_refresh(sid, *, trigger, actor, wait=False, session=None):
    from . import grants, projects, schedules, sessions

    if trigger not in ("manual", "schedule", "chat"):
        raise SpacesError("invalid", "Unknown refresh trigger")
    space = projects.get_space(sid)
    upkeep = projects.bundle(sid)["manifest"].get("upkeep") or {}
    handler = upkeep.get("handler", "")
    reason = "archived" if space["status"] == "archived" else None
    if not reason and handler not in ("feed", "agent"):
        reason = "no_handler"
    if handler == "agent":
        schedules.validate_upkeep(upkeep)
        _sync_agent_runs(sid)
    hosts = set()
    if not reason:
        for source in upkeep.get("sources", []) if handler == "feed" else []:
            try:
                hosts.add(feeds.source_host(source["url"]))
            except (SpacesError, KeyError, TypeError, ValueError):
                continue
        try:
            grants.check(sid, "refresh", {"hosts": sorted(hosts)})
        except SpacesError as exc:
            if exc.code != "not_granted":
                raise
            reason = "not_granted"
    dispatch = schedules.dispatch_detail(sid) if trigger == "schedule" else None
    now = db.now()
    run_id = "run_" + uuid.uuid4().hex[:16]
    with db.write() as conn:
        if handler == "agent":
            schedules._require_current_upkeep(conn, sid, upkeep)
            if not grants._check(conn, sid, "refresh"):
                reason = "not_granted"
            if not reason and trigger == "schedule":
                schedule = conn.execute("SELECT * FROM schedules WHERE space=?", (sid,)).fetchone()
                job = schedules._cron().get_job(schedule["cron_job_id"]) if schedule and schedule["status"] == "active" and schedule["cron_job_id"] else None
                if not job or job.get("no_agent") is not False or not job.get("enabled", True) or job.get("prompt") != schedules.agent_prompt(sid, upkeep):
                    reason = "schedule_not_approved"
        if session is not None:
            sessions._require(conn, sid, session)
            if not grants._check(conn, sid, "refresh", {"hosts": sorted(hosts)}):
                raise SpacesError("not_granted", "Capability or requested scope is not granted", capability="refresh")
        current = conn.execute("SELECT status FROM spaces WHERE id=?", (sid,)).fetchone()
        if current is None:
            raise SpacesError("not_found", "Space not found")
        if current["status"] == "archived":
            reason = "archived"
        conn.execute("UPDATE runs SET status='failed',error='interrupted',ended_at=? WHERE space=? AND handler!='agent' AND status IN ('queued','running') AND COALESCE(heartbeat_at,started_at,queued_at)<?", (now, sid, now - STALE_SECONDS))
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
        if not reason and handler == "agent":
            try:
                _queue_agent(conn, sid, run_id, upkeep)
            except Exception as exc:
                conn.execute("UPDATE runs SET status='failed',error=?,ended_at=? WHERE id=?", (str(exc), db.now(), run_id))
    if not reason and handler != "agent":
        if wait:
            _work(run_id, upkeep)
        else:
            threading.Thread(target=_work, args=(run_id, upkeep), daemon=True).start()
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
