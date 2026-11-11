"""Upkeep links. The native Hermes cron job is the only truth for a schedule; the plugin keeps a link."""
from __future__ import annotations

import importlib
import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import db
from .errors import SpacesError

PACKAGE = Path(__file__).resolve().parents[1]
KINDS = ("agent", "feed")
ACTIONS = ("pause", "resume", "run", "remove")
EXECUTION_LIMIT = 20
ONE_SHOT_LIMIT = 5


def _cron():
    return importlib.import_module("cron.jobs")


def _ledger():
    return importlib.import_module("cron.executions")


def _jobs():
    try:
        return _cron()
    except Exception as exc:
        raise SpacesError("blocked", "Native Hermes cron is unavailable", reason=f"{type(exc).__name__}: {exc}") from exc


def validate_upkeep(upkeep):
    if not isinstance(upkeep, dict) or upkeep.get("handler") not in KINDS:
        raise SpacesError("invalid", "upkeep.handler must be feed or agent")
    if upkeep["handler"] == "agent":
        _prompt(upkeep.get("prompt"))


def _prompt(prompt):
    if not isinstance(prompt, str) or not prompt.strip():
        raise SpacesError("invalid", "Agent upkeep requires a nonempty prompt")
    return prompt


def agent_prompt(sid, prompt):
    return (
        f"Maintain only the Living Space with id {sid}. Use spaces_* tools for all Space reads and writes. "
        "Do not change any other Space or write the Space database/files directly. "
        "First use spaces_get to check that this Space is not archived; stop without writes if it is. "
        "Use the tools available in your Hermes configuration to complete the task, respecting their "
        "permissions. Do not call spaces_refresh, spaces_schedule_upkeep or spaces_upkeep. "
        "Preserve user notes, statuses and other user-owned fields. For retrieved/generated records, use "
        "spaces_write_records with source_owned=true and source metadata; never put upkeep results in user data. "
        "If source-owned writes are unavailable, report that limitation without overwriting user fields.\n\n"
        "Upkeep task:\n" + _prompt(prompt)
    )


def _space(conn, sid):
    if not isinstance(sid, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,47}", sid):
        raise SpacesError("invalid", "Invalid Space id")
    row = conn.execute("SELECT status FROM spaces WHERE id=?", (sid,)).fetchone()
    if row is None:
        raise SpacesError("not_found", "Space not found")
    return row


def _link(conn, sid):
    row = conn.execute("SELECT cron_job_id,kind,created_at,created_by FROM upkeep_links WHERE space=?", (sid,)).fetchone()
    return dict(row) if row else None


def _shim(sid):
    return db.hermes_home() / "scripts" / f"living-spaces-refresh-{sid}.py"


def _seconds(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _cadence(job):
    schedule = job.get("schedule")
    if isinstance(schedule, dict):
        return schedule.get("expr") or schedule.get("display") or job.get("schedule_display")
    return schedule


def _once_name(sid):
    return f"living-spaces:{sid}:once"


def _job(job):
    return {
        "id": job.get("id"), "name": job.get("name"), "uses_model": not job.get("no_agent"),
        "prompt": None if job.get("no_agent") else job.get("prompt"),
        "schedule_display": job.get("schedule_display"), "cadence": _cadence(job),
        "timezone": job.get("timezone"), "enabled": job.get("enabled"), "state": job.get("state"),
        "next_run_at": _seconds(job.get("next_run_at")), "last_run_at": _seconds(job.get("last_run_at")),
        "last_status": job.get("last_status"), "last_error": job.get("last_error"),
    }


def _execution(entry):
    return {
        "id": entry.get("id"), "status": entry.get("status"),
        "claimed_at": _seconds(entry.get("claimed_at")), "started_at": _seconds(entry.get("started_at")),
        "finished_at": _seconds(entry.get("finished_at")), "error": entry.get("error"),
        "scheduled_instant": entry.get("scheduled_instant"),
    }


def _one_shots(sid, jobs, ledger):
    found = [job for job in jobs.list_jobs(include_disabled=True) if job.get("name") == _once_name(sid)]
    found.sort(key=lambda job: str(job.get("created_at") or ""), reverse=True)
    return [dict(_job(job), executions=[_execution(entry) for entry in ledger.list_executions(job_id=job["id"], limit=5)])
            for job in found[:ONE_SHOT_LIMIT]]


def _read(sid, *, executions=True):
    with db.read() as conn:
        _space(conn, sid)
        link = _link(conn, sid)
    result = {"link": link, "job": None, "executions": [], "one_shots": [], "missing": False, "error": None}
    try:
        jobs = _cron()
        ledger = _ledger() if executions else None
        if executions:
            result["one_shots"] = _one_shots(sid, jobs, ledger)
        if link is None:
            return result
        job = jobs.get_job(link["cron_job_id"])
        entries = ledger.list_executions(job_id=link["cron_job_id"], limit=EXECUTION_LIMIT) if executions else []
    except Exception as exc:
        result["error"] = f"Native Hermes cron is unavailable ({type(exc).__name__}): {exc}"
        return result
    result["missing"] = job is None
    result["job"] = _job(job) if job else None
    result["executions"] = [_execution(entry) for entry in entries[:EXECUTION_LIMIT]]
    return result


def get_upkeep(sid):
    return _read(sid)


def summary(sid):
    state = _read(sid, executions=False)
    if state["link"] is None:
        return None
    job = state["job"] or {}
    kind = state["link"]["kind"] if state["job"] is None else ("agent" if job["uses_model"] else "feed")
    return {"cron_job_id": state["link"]["cron_job_id"], "kind": kind,
            "enabled": job.get("enabled"), "state": job.get("state"),
            "next_run_at": job.get("next_run_at"), "missing": state["missing"]}


def schedule_upkeep(sid, *, kind, cadence, timezone, prompt=None, actor):
    if kind not in KINDS:
        raise SpacesError("invalid", "kind must be agent or feed")
    if not isinstance(cadence, str) or not cadence.strip():
        raise SpacesError("invalid", "cadence is required")
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError, TypeError) as exc:
        raise SpacesError("invalid", "timezone must be an IANA timezone") from exc
    if kind == "agent":
        mode = {"prompt": agent_prompt(sid, prompt), "no_agent": False}
    elif prompt is not None:
        raise SpacesError("invalid", "Feed upkeep takes no prompt")
    else:
        mode = {"prompt": None, "script": _shim(sid).name, "no_agent": True}
    jobs = _jobs()
    with db.write() as conn:
        if _space(conn, sid)["status"] == "archived":
            raise SpacesError("archived", "Unarchive the Space before scheduling upkeep")
        if kind == "feed":
            revision = conn.execute("SELECT r.manifest FROM revisions r JOIN spaces s ON s.id=r.space AND s.head_rev=r.rev WHERE s.id=?", (sid,)).fetchone()
            if revision is None or (json.loads(revision["manifest"]).get("upkeep") or {}).get("handler") != "feed":
                raise SpacesError("invalid", "Feed upkeep needs upkeep.handler feed in the Space manifest")
        old = _link(conn, sid)
        if old:
            jobs.remove_job(old["cron_job_id"])
            conn.execute("DELETE FROM upkeep_links WHERE space=?", (sid,))
        shim = _shim(sid)
        if kind == "feed":
            template = (PACKAGE / "scripts" / "refresh_space.py").read_text()
            shim.parent.mkdir(parents=True, exist_ok=True)
            shim.write_text(template.replace("__LIVING_SPACES_PACKAGE__", repr(str(PACKAGE))).replace("__LIVING_SPACES_SID__", repr(sid)))
        else:
            shim.unlink(missing_ok=True)
        try:
            job = jobs.create_job(**mode, schedule=cadence, name=f"living-spaces:{sid}", deliver="local",
                                  catch_up=True, timezone=timezone)
        except ValueError as exc:
            shim.unlink(missing_ok=True)
            raise SpacesError("invalid", f"Hermes cron rejected the schedule: {exc}") from exc
        conn.execute("INSERT INTO upkeep_links(space,cron_job_id,kind,created_at,created_by) VALUES(?,?,?,?,?)",
                     (sid, job["id"], kind, db.now(), actor))
    return get_upkeep(sid)


def upkeep_action(sid, action, *, actor):
    if action not in ACTIONS:
        raise SpacesError("invalid", "action must be pause, resume, run or remove")
    jobs = _jobs()
    with db.write() as conn:
        status = _space(conn, sid)["status"]
        link = _link(conn, sid)
        if link is None:
            raise SpacesError("not_found", "No upkeep scheduled")
        if action in ("resume", "run") and status == "archived":
            raise SpacesError("archived", "Unarchive the Space before running upkeep")
        jid = link["cron_job_id"]
        try:
            if action == "pause":
                jobs.pause_job(jid, reason=f"Paused from Living Spaces by {actor}")
            elif action == "resume":
                jobs.resume_job(jid)
            elif action == "run":
                jobs.trigger_job(jid)
            else:
                jobs.remove_job(jid)
                _shim(sid).unlink(missing_ok=True)
                conn.execute("DELETE FROM upkeep_links WHERE space=?", (sid,))
        except ValueError as exc:
            raise SpacesError("blocked", str(exc), reason="native_refused") from exc
    return get_upkeep(sid)


def refresh_now(sid, upkeep, *, actor):
    jobs = _jobs()
    # Held under the write lock so archive and delete, which take the same lock, cannot interleave
    # between the status check and the native job this creates.
    with db.write() as conn:
        if _space(conn, sid)["status"] == "archived":
            raise SpacesError("archived", "Unarchive the Space before refreshing")
        link = _link(conn, sid)
        if link and link["kind"] == "agent":
            if jobs.trigger_job(link["cron_job_id"]) is None:
                raise SpacesError("blocked", "The linked Hermes job no longer exists", reason="missing")
            return {"kind": "cron", "cron_job_id": link["cron_job_id"], "triggered": True}
        # Created paused, then triggered: a paused job has no pending slot, so run-now fires exactly once.
        job = jobs.create_job(prompt=agent_prompt(sid, upkeep.get("prompt")), schedule="in 1m", repeat=1,
                              name=_once_name(sid), no_agent=False, deliver="local",
                              catch_up=True, paused=True)
        try:
            if jobs.trigger_job(job["id"]) is None:
                raise SpacesError("blocked", "Hermes cron could not start the refresh", reason="native_refused")
        except Exception:
            jobs.remove_job(job["id"])
            raise
    return {"kind": "cron", "cron_job_id": job["id"], "triggered": True}


def dispatch_detail(sid):
    with db.read() as conn:
        link = _link(conn, sid)
    if not link:
        return None
    try:
        job = _cron().get_job(link["cron_job_id"])
    except Exception:
        return None
    if not job or job.get("manual_run_at"):
        return None
    dispatch = job.get("last_dispatch")
    if dispatch and (not job.get("last_run_at") or
                     datetime.fromisoformat(dispatch["dispatched_at"]) > datetime.fromisoformat(job["last_run_at"])):
        return dispatch
    return None


def pause_for_archive(conn, sid):
    """Pause the linked job and pending one-shots inside the archiving transaction; any failure aborts it."""
    link = _link(conn, sid)
    try:
        jobs = _cron()
    except ImportError:
        if link is None:
            return  # No native scheduler is importable, so nothing of this Space's can run.
        raise SpacesError("blocked", "Could not pause this Space's upkeep, so it was not archived",
                          reason="Native Hermes cron is unavailable")
    pending = [job["id"] for job in jobs.list_jobs(include_disabled=True)
               if job.get("name") == _once_name(sid) and job.get("enabled")]
    targets = ([link["cron_job_id"]] if link else []) + pending
    try:
        for jid in targets:
            paused = jobs.pause_job(jid, reason="Living Space archived")
            if link and jid == link["cron_job_id"] and paused is None:
                continue  # Missing linked job: nothing can run, and the panel shows it as missing.
            if paused is not None and paused.get("enabled"):
                raise RuntimeError(f"job {jid} is still enabled")
    except Exception as exc:
        raise SpacesError("blocked", "Could not pause this Space's upkeep, so it was not archived",
                          reason=f"{type(exc).__name__}: {exc}") from exc


def on_delete(sid):
    jobs = _jobs()
    with db.write() as conn:
        _space(conn, sid)
        link = _link(conn, sid)
        if link:
            jobs.remove_job(link["cron_job_id"])
        for job in jobs.list_jobs(include_disabled=True):
            if job.get("name") == _once_name(sid):
                jobs.remove_job(job["id"])
        _shim(sid).unlink(missing_ok=True)
        conn.execute("DELETE FROM upkeep_links WHERE space=?", (sid,))
    return link is not None
