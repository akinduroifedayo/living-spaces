"""Upkeep links to ordinary Hermes jobs, accessed only through public tool dispatch."""
from __future__ import annotations

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
ONE_SHOT_LIMIT = 5
_CONTEXTS = {}
UNAVAILABLE = {
    "prompt": "The public cron tool exposes only a prompt preview, not the full task.",
    "executions": "Execution history is unavailable through the public cron tool.",
    "dispatch": "Manual-run and catch-up dispatch status is unavailable through the public cron tool.",
}


def configure_context(ctx):
    """Bind register()'s public context to this profile, including calls from REST and lifecycle helpers."""
    _CONTEXTS[db.hermes_home().resolve()] = ctx


def _context():
    ctx = _CONTEXTS.get(db.hermes_home().resolve())
    if ctx is None:
        raise SpacesError("blocked", "Public Hermes cron context is unavailable", reason="cron_context_unavailable")
    return ctx


def _call(action, **args):
    try:
        reply = _context().dispatch_tool("cronjob_manage", {"action": action, **args})
        result = json.loads(reply) if isinstance(reply, str) else reply
    except SpacesError:
        raise
    except Exception as exc:
        raise SpacesError("blocked", f"Hermes cron {action} is unavailable: {exc}", reason="cron_unavailable") from exc
    if not isinstance(result, dict) or result.get("success") is not True:
        message = result.get("error") if isinstance(result, dict) else "Invalid public cron response"
        raise SpacesError("blocked", f"Hermes cron {action} refused: {message}", reason="native_refused", native=result)
    return result


def _jobs():
    result = _call("list", include_disabled=True)
    jobs = result.get("jobs")
    if (not isinstance(jobs, list) or result.get("count") != len(jobs)
            or any(not isinstance(job, dict) or not isinstance(job.get("job_id"), str) for job in jobs)
            or len({job["job_id"] for job in jobs}) != len(jobs)):
        raise SpacesError("blocked", "Invalid public cron job list", reason="cron_response_invalid")
    return result


def _mutate(action, jid, **args):
    result = _call(action, job_id=jid, **args)
    job = next((job for job in _jobs()["jobs"] if job["job_id"] == jid), None)
    if action == "remove":
        valid = job is None
    elif action == "pause":
        valid = job is not None and job.get("enabled") is False
    elif action == "resume":
        valid = job is not None and job.get("enabled") is True
    else:
        valid = True  # A one-shot may already have completed and disappeared.
    if not valid:
        raise SpacesError("blocked", f"Hermes cron {action} could not be verified", reason="cron_unverified", native=result)
    return result


def _create(**args):
    result = _call("create", **args)
    jid = result.get("job_id")
    if not isinstance(jid, str) or not any(job["job_id"] == jid for job in _jobs()["jobs"]):
        raise SpacesError("blocked", "Hermes cron creation could not be verified", reason="cron_unverified", native=result)
    return jid


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


def _once_name(sid):
    return f"living-spaces:{sid}:once"


def _job(job):
    return {
        "id": job["job_id"], "name": job.get("name"), "uses_model": not job.get("no_agent", False),
        "prompt": None, "prompt_preview": job.get("prompt_preview"),
        "schedule_display": job.get("schedule"), "cadence": job.get("schedule"),
        "timezone": job.get("timezone"), "enabled": job.get("enabled"), "state": job.get("state"),
        "next_run_at": _seconds(job.get("next_run_at")), "last_run_at": _seconds(job.get("last_run_at")),
        "last_status": job.get("last_status"), "last_error": job.get("last_error"),
        "last_delivery_error": job.get("last_delivery_error"), "last_fire_error": job.get("last_fire_error"),
    }


def _read(sid):
    with db.read() as conn:
        _space(conn, sid)
        link = _link(conn, sid)
    result = {"link": link, "job": None, "executions": [], "one_shots": [], "missing": False,
              "error": None, "unavailable": dict(UNAVAILABLE)}
    try:
        listed = _jobs()
    except SpacesError as exc:
        result["error"] = exc.message
        return result
    jobs = listed["jobs"]
    result["gateway_running"] = listed.get("gateway_running")
    result["warning"] = listed.get("warning")
    result["one_shots"] = [dict(_job(job), executions=[]) for job in jobs
                           if job.get("name") == _once_name(sid)][:ONE_SHOT_LIMIT]
    if link:
        job = next((job for job in jobs if job["job_id"] == link["cron_job_id"]), None)
        result["missing"] = job is None
        result["job"] = _job(job) if job else None
    return result


def get_upkeep(sid):
    return _read(sid)


def summary(sid):
    state = _read(sid)
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
    with db.write() as conn:
        if _space(conn, sid)["status"] == "archived":
            raise SpacesError("archived", "Unarchive the Space before scheduling upkeep")
        if kind == "feed":
            revision = conn.execute("SELECT r.manifest FROM revisions r JOIN spaces s ON s.id=r.space AND s.head_rev=r.rev WHERE s.id=?", (sid,)).fetchone()
            if revision is None or (json.loads(revision["manifest"]).get("upkeep") or {}).get("handler") != "feed":
                raise SpacesError("invalid", "Feed upkeep needs upkeep.handler feed in the Space manifest")
        old = _link(conn, sid)
        shim = _shim(sid)
        had_shim = shim.exists()
        if kind == "feed":
            template = (PACKAGE / "scripts" / "refresh_space.py").read_text()
            shim.parent.mkdir(parents=True, exist_ok=True)
            shim.write_text(template.replace("__LIVING_SPACES_PACKAGE__", repr(str(PACKAGE))).replace("__LIVING_SPACES_SID__", repr(sid)))
        try:
            jid = _create(**mode, schedule=cadence, name=f"living-spaces:{sid}", deliver="local",
                          catch_up=True, timezone=timezone, paused=True)
        except SpacesError:
            if not had_shim:
                shim.unlink(missing_ok=True)
            raise
        try:
            if old and any(job["job_id"] == old["cron_job_id"] for job in _jobs()["jobs"]):
                _mutate("remove", old["cron_job_id"])
            _mutate("resume", jid)
        except SpacesError:
            _mutate("remove", jid)
            raise
        if kind == "agent":
            shim.unlink(missing_ok=True)
        conn.execute("DELETE FROM upkeep_links WHERE space=?", (sid,))
        conn.execute("INSERT INTO upkeep_links(space,cron_job_id,kind,created_at,created_by) VALUES(?,?,?,?,?)",
                     (sid, jid, kind, db.now(), actor))
    return get_upkeep(sid)


def upkeep_action(sid, action, *, actor):
    if action not in ACTIONS:
        raise SpacesError("invalid", "action must be pause, resume, run or remove")
    with db.write() as conn:
        status = _space(conn, sid)["status"]
        link = _link(conn, sid)
        if link is None:
            raise SpacesError("not_found", "No upkeep scheduled")
        if action in ("resume", "run") and status == "archived":
            raise SpacesError("archived", "Unarchive the Space before running upkeep")
        args = {"reason": f"Paused from Living Spaces by {actor}"} if action == "pause" else {}
        native = _mutate(action, link["cron_job_id"], **args)
        if action == "remove":
            _shim(sid).unlink(missing_ok=True)
            conn.execute("DELETE FROM upkeep_links WHERE space=?", (sid,))
    result = get_upkeep(sid)
    if action == "run":
        result["dispatch"] = native
    return result


def refresh_now(sid, upkeep, *, actor):
    # Share archive/delete's write lock until the native job is created and dispatched.
    with db.write() as conn:
        if _space(conn, sid)["status"] == "archived":
            raise SpacesError("archived", "Unarchive the Space before refreshing")
        link = _link(conn, sid)
        if link and link["kind"] == "agent":
            jid = link["cron_job_id"]
            native = _mutate("run", jid)
        else:
            jid = _create(prompt=agent_prompt(sid, upkeep.get("prompt")), schedule="in 1m", repeat=1,
                          name=_once_name(sid), no_agent=False, deliver="local", catch_up=True, paused=True)
            try:
                native = _mutate("run", jid)
            except SpacesError:
                _mutate("remove", jid)
                raise
    return {"kind": "cron", "cron_job_id": jid, "dispatch": native}


def pause_for_archive(conn, sid):
    """Pause future work inside the archiving transaction; any failure aborts it."""
    link = _link(conn, sid)
    try:
        jobs = _jobs()["jobs"]
        targets = {job["job_id"] for job in jobs if job.get("name") == _once_name(sid)}
        if link and any(job["job_id"] == link["cron_job_id"] for job in jobs):
            targets.add(link["cron_job_id"])
        for jid in sorted(targets):
            _mutate("pause", jid, reason="Living Space archived")
    except SpacesError as exc:
        raise SpacesError("blocked", "Could not pause this Space's upkeep, so it was not archived", reason=exc.message) from exc


def on_delete(conn, sid):
    """Remove future native work within the caller's Space deletion transaction."""
    _space(conn, sid)
    link = _link(conn, sid)
    jobs = _jobs()["jobs"]
    targets = {job["job_id"] for job in jobs if job.get("name") == _once_name(sid)}
    if link and any(job["job_id"] == link["cron_job_id"] for job in jobs):
        targets.add(link["cron_job_id"])
    for jid in sorted(targets):
        _mutate("remove", jid)
    _shim(sid).unlink(missing_ok=True)
    conn.execute("DELETE FROM upkeep_links WHERE space=?", (sid,))
    return link is not None
