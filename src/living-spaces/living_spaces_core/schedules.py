from __future__ import annotations

import importlib
import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import db
from .errors import SpacesError

CATCH_UP_POLICY = "Runs one current refresh when Hermes wakes. Missed intervals aren't replayed."
PACKAGE = Path(__file__).resolve().parents[1]


def _cron():
    return importlib.import_module("cron.jobs")


def validate_upkeep(upkeep):
    if not isinstance(upkeep, dict) or upkeep.get("handler") not in ("feed", "agent"):
        raise SpacesError("invalid", "upkeep.handler must be feed or agent")
    if upkeep["handler"] == "agent":
        prompt = upkeep.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 4000:
            raise SpacesError("invalid", "Agent upkeep requires a nonempty prompt of at most 4000 characters")


def _require_current_upkeep(conn, sid, upkeep):
    row = conn.execute("SELECT r.manifest FROM revisions r JOIN spaces s ON s.id=r.space AND s.head_rev=r.rev WHERE s.id=?", (sid,)).fetchone()
    if row and json.loads(row["manifest"]).get("upkeep") != upkeep:
        raise SpacesError("conflict", "Upkeep changed; review the current prompt before continuing")


def agent_prompt(sid, upkeep):
    validate_upkeep(upkeep)
    return (
        f"Maintain only the Living Space with id {sid}. Use spaces_* tools for all Space reads and writes. "
        "Do not change any other Space or write the Space database/files directly. "
        "First use spaces_get to check that this Space is not archived and its refresh grant is granted; "
        "stop without writes if either check fails. Use the tools available in your Hermes configuration "
        "to complete the task, respecting their permissions. Do not call spaces_refresh or change schedules. "
        "Preserve user notes, statuses and other user-owned fields. For retrieved/generated records, use "
        "spaces_write_records with source_owned=true and source metadata; never put upkeep results in user data. "
        "If source-owned writes are unavailable, report that limitation without overwriting user fields.\n\n"
        "Upkeep task:\n" + upkeep["prompt"]
    )


def on_manifest_change(conn, sid, old, new, *, actor):
    before, after = old.get("upkeep") or {}, new.get("upkeep") or {}
    if (before.get("handler"), before.get("prompt")) == (after.get("handler"), after.get("prompt")):
        return
    row = conn.execute("SELECT * FROM schedules WHERE space=?", (sid,)).fetchone()
    if row is None:
        return
    if row["cron_job_id"]:
        try:
            _cron().pause_job(row["cron_job_id"], reason="Upkeep handler or prompt changed; approval required")
        except ImportError as exc:
            raise SpacesError("blocked", "Cannot pause the existing native cron job", reason=str(exc)) from exc
    conn.execute("UPDATE schedules SET status='requested',requested_at=?,decided_at=NULL,next_run_at=NULL WHERE space=?", (db.now(), sid))
    conn.execute("INSERT INTO audit(space,at,actor,action,outcome,detail) VALUES(?,?,?,?,?,?)", (
        sid, db.now(), actor, "schedule.requested", "requested", json.dumps({"reason": "Upkeep handler or prompt changed"}),
    ))


def _space(conn, sid):
    if not isinstance(sid, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,47}", sid):
        raise SpacesError("invalid", "Invalid Space id")
    row = conn.execute("SELECT status FROM spaces WHERE id=?", (sid,)).fetchone()
    if row is None:
        raise SpacesError("not_found", "Space not found")
    return row


def _shim(sid):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,47}", sid):
        raise SpacesError("invalid", "Invalid Space id")
    return db.hermes_home() / "scripts" / f"living-spaces-refresh-{sid}.py"


def _next(job):
    value = job.get("next_run_at")
    if value is None:
        return None
    if isinstance(value, (float, int)):
        return float(value)
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def _disabled(conn, sid, reason, actor):
    conn.execute("UPDATE schedules SET status='disabled',next_run_at=NULL,decided_at=? WHERE space=?", (db.now(), sid))
    conn.execute("INSERT INTO audit(space,at,actor,action,outcome,detail) VALUES(?,?,?,?,?,?)", (
        sid, db.now(), actor, "schedule.disabled", "disabled", json.dumps({"reason": reason}),
    ))


def _schedule_row(sid):
    with db.read() as conn:
        row = conn.execute("SELECT * FROM schedules WHERE space=?", (sid,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        if result.get("reason") is None:
            result.pop("reason", None)
        if result["status"] in ("disabled", "paused"):
            audit = conn.execute("SELECT detail FROM audit WHERE space=? AND action=? ORDER BY id DESC LIMIT 1", (sid, "schedule." + result["status"])).fetchone()
            if audit:
                result["reason"] = json.loads(audit["detail"])["reason"]
        return result


def get_schedule(sid):
    schedule = _schedule_row(sid)
    if schedule is None or not schedule["cron_job_id"] or schedule["status"] not in ("active", "paused"):
        return schedule
    job = None
    with db.write() as conn:
        current = conn.execute("SELECT * FROM schedules WHERE space=?", (sid,)).fetchone()
        if current is None:
            return None
        if current["cron_job_id"] != schedule["cron_job_id"] or current["status"] not in ("active", "paused"):
            return dict(current)
        try:
            job = _cron().get_job(current["cron_job_id"])
        except ImportError as exc:
            _disabled(conn, sid, f"Native cron is unavailable: {exc}", "upkeep:schedule")
        else:
            if job is None:
                _disabled(conn, sid, "Native cron job is missing; approve the schedule again", "upkeep:schedule")
            else:
                paused = job.get("state") == "paused" or not job.get("enabled", True)
                conn.execute("UPDATE schedules SET status=?,next_run_at=? WHERE space=?", (
                    "paused" if paused else "active", None if paused else _next(job), sid,
                ))
    result = _schedule_row(sid)
    if result and job:
        if job.get("last_dispatch"):
            result["last_dispatch"] = job["last_dispatch"]
        if result["status"] == "paused" and job.get("paused_reason"):
            result["reason"] = job["paused_reason"]
    return result


def dispatch_detail(sid):
    schedule = _schedule_row(sid)
    if not schedule or not schedule["cron_job_id"]:
        return None
    try:
        job = _cron().get_job(schedule["cron_job_id"])
    except ImportError:
        return None
    if not job or job.get("manual_run_at"):
        return None
    dispatch = job.get("last_dispatch")
    # A completed dispatch is history, not evidence for a new invocation of the shim.
    if dispatch and (not job.get("last_run_at") or
                     datetime.fromisoformat(dispatch["dispatched_at"]) > datetime.fromisoformat(job["last_run_at"])):
        return dispatch
    return None


def request_schedule(sid, *, cadence, timezone, purpose, actor):
    if not isinstance(cadence, str) or not cadence.strip():
        raise SpacesError("invalid", "Schedule cadence is required")
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError, TypeError) as exc:
        raise SpacesError("invalid", "Schedule timezone must be an IANA timezone") from exc
    with db.write() as conn:
        _space(conn, sid)
        existing = conn.execute("SELECT cron_job_id FROM schedules WHERE space=?", (sid,)).fetchone()
        if existing and existing["cron_job_id"]:
            try:
                _cron().pause_job(existing["cron_job_id"], reason="Schedule change awaiting approval")
            except ImportError as exc:
                raise SpacesError("blocked", "Cannot pause the existing native cron job", reason=str(exc)) from exc
        conn.execute("INSERT INTO schedules(space,status,cadence,timezone,purpose,requested_at) VALUES(?,'requested',?,?,?,?) ON CONFLICT(space) DO UPDATE SET status='requested',cadence=excluded.cadence,timezone=excluded.timezone,purpose=excluded.purpose,requested_at=excluded.requested_at,decided_at=NULL,next_run_at=NULL", (
            sid, cadence, timezone, purpose, db.now(),
        ))
    return _schedule_row(sid)


def decide_schedule(sid, decision, *, actor="user", requested_upkeep=None):
    if decision not in ("approve", "deny"):
        raise SpacesError("invalid", "Schedule decision must be approve or deny")
    if decision == "approve":
        from . import grants, projects
        grants.check(sid, "refresh")
        upkeep = projects.bundle(sid)["manifest"].get("upkeep")
        validate_upkeep(upkeep)
        if requested_upkeep is not None and requested_upkeep != upkeep:
            raise SpacesError("conflict", "Upkeep request changed. Review the current prompt before approving.")
    with db.write() as conn:
        space = _space(conn, sid)
        if decision == "approve":
            _require_current_upkeep(conn, sid, upkeep)
            if upkeep["handler"] == "agent" and not grants._check(conn, sid, "refresh"):
                raise SpacesError("not_granted", "Refresh is not granted", capability="refresh")
        row = conn.execute("SELECT * FROM schedules WHERE space=?", (sid,)).fetchone()
        if row is None:
            raise SpacesError("not_found", "Schedule not found")
        if decision == "approve" and space["status"] == "archived":
            raise SpacesError("archived", "Unarchive the Space before approving upkeep")
        try:
            jobs = _cron()
        except ImportError as exc:
            _disabled(conn, sid, f"Native cron is unavailable: {exc}", actor)
        else:
            if decision == "approve" and row["status"] == "active" and row["cron_job_id"] and jobs.get_job(row["cron_job_id"]):
                return dict(row)
            if row["cron_job_id"]:
                jobs.remove_job(row["cron_job_id"])
                conn.execute("UPDATE schedules SET cron_job_id=NULL WHERE space=?", (sid,))
            shim = _shim(sid)
            if decision == "deny":
                shim.unlink(missing_ok=True)
                _disabled(conn, sid, "Schedule denied by user", actor)
            else:
                job = None
                try:
                    if upkeep["handler"] == "agent":
                        shim.unlink(missing_ok=True)
                        mode = {"prompt": agent_prompt(sid, upkeep), "no_agent": False}
                    else:
                        template = (PACKAGE / "scripts" / "refresh_space.py").read_text()
                        script = template.replace("__LIVING_SPACES_PACKAGE__", repr(str(PACKAGE))).replace("__LIVING_SPACES_SID__", repr(sid))
                        shim.parent.mkdir(parents=True, exist_ok=True)
                        shim.write_text(script)
                        mode = {"prompt": None, "script": shim.name, "no_agent": True}
                    job = jobs.create_job(
                        **mode, schedule=row["cadence"], name=f"living-spaces:{sid}",
                        deliver="local", catch_up=True, timezone=row["timezone"],
                    )
                    conn.execute("UPDATE schedules SET status='active',cron_job_id=?,decided_at=?,next_run_at=? WHERE space=?", (
                        job["id"], db.now(), _next(job), sid,
                    ))
                except Exception as exc:
                    if job:
                        jobs.remove_job(job["id"])
                    shim.unlink(missing_ok=True)
                    _disabled(conn, sid, f"Could not enable native cron: {exc}", actor)
    return _schedule_row(sid)


def pause_schedule(sid, paused, *, actor, reason="Space upkeep paused"):
    if not isinstance(paused, bool):
        raise SpacesError("invalid", "paused must be a boolean")
    if not paused:
        from . import grants
        grants.check(sid, "refresh")
    with db.write() as conn:
        space = _space(conn, sid)
        if not paused and space["status"] == "archived":
            raise SpacesError("archived", "Unarchive the Space before resuming upkeep")
        row = conn.execute("SELECT * FROM schedules WHERE space=?", (sid,)).fetchone()
        if row is None:
            raise SpacesError("not_found", "Schedule not found")
        if not row["cron_job_id"] or row["status"] not in ("active", "paused"):
            raise SpacesError("blocked", "Approve the schedule before changing pause", reason="schedule_not_approved")
        try:
            jobs = _cron()
        except ImportError as exc:
            _disabled(conn, sid, f"Native cron is unavailable: {exc}", actor)
        else:
            job = jobs.pause_job(row["cron_job_id"], reason=reason) if paused else jobs.resume_job(row["cron_job_id"])
            if job is None:
                _disabled(conn, sid, "Native cron job is missing; approve the schedule again", actor)
            else:
                conn.execute("UPDATE schedules SET status=?,next_run_at=? WHERE space=?", ("paused" if paused else "active", None if paused else _next(job), sid))
                if paused:
                    conn.execute("INSERT INTO audit(space,at,actor,action,outcome,detail) VALUES(?,?,?,?,?,?)", (
                        sid, db.now(), actor, "schedule.paused", "paused", json.dumps({"reason": reason}),
                    ))
    return _schedule_row(sid)


def on_refresh_revoked(sid, decision, *, actor):
    schedule = _schedule_row(sid)
    if schedule and schedule["status"] in ("active", "paused"):
        reason = "Refresh permission " + ("denied" if decision == "deny" else "revoked") + "; approve Refresh and resume upkeep to restart."
        pause_schedule(sid, True, actor=actor, reason=reason)


def on_archive(sid):
    schedule = _schedule_row(sid)
    if schedule and schedule["status"] in ("active", "paused"):
        pause_schedule(sid, True, actor="upkeep:archive")


def on_unarchive(sid):
    return get_schedule(sid)


def remove_schedule(sid):
    with db.write() as conn:
        _space(conn, sid)
        row = conn.execute("SELECT * FROM schedules WHERE space=?", (sid,)).fetchone()
        if row and row["cron_job_id"]:
            try:
                jobs = _cron()
            except ImportError as exc:
                raise SpacesError("blocked", "Cannot remove the native cron job", reason=str(exc)) from exc
            jobs.remove_job(row["cron_job_id"])
        _shim(sid).unlink(missing_ok=True)
        conn.execute("DELETE FROM schedules WHERE space=?", (sid,))


def on_delete(sid):
    remove_schedule(sid)
