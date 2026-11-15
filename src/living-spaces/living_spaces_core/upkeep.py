from __future__ import annotations

import json
import re
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import db
from .errors import SpacesError

PACKAGE = Path(__file__).resolve().parents[1]
KINDS = ("agent", "feed")
ACTIONS = ("pause", "resume", "run", "remove")
ONE_SHOT_LIMIT = 5
AGENT_MIN_MINUTES = 15
AGENT_PROMPT_LIMIT = 8000
# Refresh now runs its one-shot explicitly. The native slot exists only because a once job needs one, so it is
# set far beyond a normal run. The run holds the claim until it finishes and the pause lands only after that, so
# a run still in flight past the slot (7 days awake, or a host suspended across it) can be claimed once more.
# A one-shot created already due was tried instead: Hermes's dispatch-limit guard retired it mid-run and a
# successful run was reported as failed, so the bounded slot stays.
ONE_SHOT_SLOT = "in 7d"
_CONTEXTS = {}
UNAVAILABLE = {
    "prompt": "The public cron tool exposes only a prompt preview, not the full task.",
    "timezone": "The public cron list does not expose the stored timezone.",
    "executions": "Execution history is unavailable through the public cron tool.",
    "dispatch": "Manual-run and catch-up dispatch status is unavailable through the public cron tool.",
}


def configure_context(ctx):
    _CONTEXTS[db.hermes_home().resolve()] = ctx


def _context():
    ctx = _CONTEXTS.get(db.hermes_home().resolve())
    if ctx is None:
        raise SpacesError("blocked", "Public Hermes cron context is unavailable", reason="cron_context_unavailable")
    return ctx


def _scheduling_allowed():
    ctx = _context()
    try:
        execution = ctx.current_cron_execution()
    except Exception as exc:
        raise SpacesError("blocked", "Could not verify cron execution identity", reason="cron_identity_unavailable") from exc
    if execution is not None:
        raise SpacesError("blocked", "Living Spaces cannot schedule, resume or run upkeep from a cron execution. "
                          "This remains blocked even when cron.allow_agent_scheduling is true because the public "
                          "plugin context cannot read that global policy.", reason="cron_recursion")


def _clock_values(field, maximum):
    values = set()
    for part in field.split(","):
        match = re.fullmatch(r"(\*|[0-9]{1,2}(?:-[0-9]{1,2})?)(?:/([0-9]{1,6}))?", part)
        if not match:
            raise ValueError("Unsupported cron clock field")
        base, step = match.groups()
        step = int(step or 1)
        if step < 1:
            raise ValueError("Cron step must be positive")
        if base == "*":
            span = list(range(maximum + 1))
        else:
            bounds = [int(value) for value in base.split("-")]
            if any(value > maximum for value in bounds):
                raise ValueError("Cron clock field is out of range")
            start = bounds[0]
            end = bounds[1] if len(bounds) == 2 else (maximum if match.group(2) else start)
            span = (list(range(start, end + 1)) if start <= end
                    else list(range(start, maximum + 1)) + list(range(end + 1)))
        values.update(span[::step])
    return sorted(values)


def _require_conservative_nominal_agent_spacing(cadence):
    text = cadence.strip().lower()
    duration = re.fullmatch(r"(every |in )?([0-9]{0,6})\s*(m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days)", text)
    if duration:
        prefix, count, unit = duration.groups()
        minutes = int(count or 1) * {"m": 1, "h": 60, "d": 1440}[unit[0]]
        if minutes > 0 and (prefix == "in " or minutes >= AGENT_MIN_MINUTES):
            return
    else:
        day = r"(?:day|daily|everyday|weekdays?|weekends?|sun(?:day)?|mon(?:day)?|tue(?:s|sday)?|wed(?:s|nesday)?|thu(?:r|rs|rsday)?|fri(?:day)?|sat(?:urday)?)"
        clock = r"(?:noon|midday|midnight|[0-9]{1,2}(?::[0-9]{2})?(?: ?[ap]m)?)"
        if re.fullmatch(rf"(?:every )?{day}(?:(?:,? |, ?| and ){day})* (?:at )?{clock}", text):
            return
        try:
            datetime.fromisoformat(text.replace("z", "+00:00"))
            return
        except ValueError:
            pass
        fields = text.split()
        if len(fields) == 5:
            try:
                minutes = _clock_values(fields[0], 59)
                hours = _clock_values(fields[1], 23)
                instants = sorted(hour * 60 + minute for hour in hours for minute in minutes)
                gaps = [later - earlier for earlier, later in zip(instants, instants[1:] + [instants[0] + 1440])]
                if min(gaps) >= AGENT_MIN_MINUTES:
                    return
            except ValueError:
                pass
    raise SpacesError("invalid", "Agent upkeep needs at least 15 minutes between nominal scheduled fires. "
                      "Use a supported interval, daily/weekly time, or five-field cron with a verifiable clock spacing; "
                      "unsupported cadence forms are refused.", reason="agent_cadence", minimum_minutes=AGENT_MIN_MINUTES)


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


def _mutate(action, jid, *, on_run_reply=None, **args):
    result = None
    failure = None
    try:
        result = _call(action, job_id=jid, **args)
    except SpacesError as exc:
        if action != "remove":
            raise
        failure = exc
        failure.extra.update(action=action, job_id=jid)
    if action == "run" and on_run_reply is not None:
        try:
            on_run_reply(result)
        except Exception as exc:
            raise SpacesError("blocked", f"Hermes accepted the run, but its refresh claim could not be updated: {exc}",
                              reason="post_run_check_failed", native=result, action=action, job_id=jid) from exc
    try:
        job = next((job for job in _jobs()["jobs"] if job["job_id"] == jid), None)
    except SpacesError as verification:
        if action == "run":
            # The run reply owns native; the failed verification keeps its own reply under verification.
            raise SpacesError("blocked", verification.message, **{**verification.extra, "reason": "post_run_check_failed",
                              "action": action, "job_id": jid,
                              "native": result, "verification": verification.to_dict()}) from verification
        if action != "remove":
            raise
        message = f"{failure.message}; " if failure else ""
        raise SpacesError("blocked", f"{message}Hermes cron remove outcome for job {jid} is unknown: "
                          f"{verification.message}", reason="cron_remove_outcome_unknown",
                          action=action, job_id=jid,
                          native=failure.extra.get("native") if failure else result,
                          original=failure.to_dict() if failure else result,
                          verification=verification.to_dict()) from verification
    if failure:
        if job is not None:
            raise failure
        return {"success": True, "already_absent": True, "native": failure.extra.get("native")}
    if action == "remove":
        valid = job is None
    elif action == "pause":
        valid = job is not None and job.get("enabled") is False
    elif action == "resume":
        valid = job is not None and job.get("enabled") is True
    else:
        valid = True  # A one-shot may already have completed and disappeared.
    if not valid:
        raise SpacesError("blocked", f"Hermes cron {action} could not be verified", reason="cron_unverified",
                          action=action, job_id=jid, native=result)
    return result


def _create(**args):
    jid = None
    try:
        result = _call("create", **args)
        jid = result.get("job_id")
        if not isinstance(jid, str) or not any(job["job_id"] == jid for job in _jobs()["jobs"]):
            raise SpacesError("blocked", "Hermes cron creation could not be verified", reason="cron_unverified", native=result)
        return jid
    except SpacesError as exc:
        failure = exc
        native = exc.extra.get("native")
        if jid is None and isinstance(native, dict) and native.get("job_saved") is True:
            jid = native.get("job_id")
    if not isinstance(jid, str):
        raise failure
    try:
        _mutate("remove", jid)
    except SpacesError as cleanup:
        raise SpacesError("blocked", f"{failure.message}; cleanup of the newly created Hermes cron job {jid} also failed: "
                          f"{cleanup.message}. Job {jid} may remain paused and unlinked.",
                          reason="cron_cleanup_failed", orphan_job_id=jid,
                          original=failure.to_dict(), cleanup=cleanup.to_dict()) from failure
    raise failure


def validate_upkeep(upkeep):
    if not isinstance(upkeep, dict) or upkeep.get("handler") not in KINDS:
        raise SpacesError("invalid", "upkeep.handler must be feed or agent")
    if upkeep["handler"] == "agent":
        _prompt(upkeep.get("prompt"))


def _prompt(prompt):
    if not isinstance(prompt, str) or not prompt.strip():
        raise SpacesError("invalid", "Agent upkeep requires a nonempty prompt")
    if len(prompt) > AGENT_PROMPT_LIMIT:
        raise SpacesError("limit", "Agent upkeep task exceeds 8000 Unicode characters",
                          reason="agent_prompt_limit", limit=AGENT_PROMPT_LIMIT, actual=len(prompt))
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
    row = conn.execute("SELECT status,created_at FROM spaces WHERE id=?", (sid,)).fetchone()
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
        "id": job["job_id"], "name": job.get("name"), "uses_model": job.get("no_agent") is not True,
        "prompt": None, "prompt_preview": job.get("prompt_preview"),
        "schedule_display": job.get("schedule"), "cadence": job.get("schedule"),
        "timezone": None, "enabled": job.get("enabled"), "state": job.get("state"),
        "next_run_at": _seconds(job.get("next_run_at")), "last_run_at": _seconds(job.get("last_run_at")),
        "last_status": job.get("last_status"), "last_error": job.get("last_error"),
        "last_delivery_error": job.get("last_delivery_error"), "last_fire_error": job.get("last_fire_error"),
    }


def _owned_jobs(sid, link, jobs, *, claim=None):
    linked_id = link["cron_job_id"] if link else None
    claimed_id = claim["cron_job_id"] if claim else None
    names = (f"living-spaces:{sid}", _once_name(sid))
    return [job for job in jobs if job["job_id"] in (linked_id, claimed_id) or job.get("name") in names]


def _read(sid):
    with db.read() as conn:
        _space(conn, sid)
        link = _link(conn, sid)
    result = {"link": link, "job": None, "executions": [], "one_shots": [], "orphan_jobs": [], "missing": False,
              "error": None, "unavailable": dict(UNAVAILABLE)}
    try:
        listed = _jobs()
    except SpacesError as exc:
        result["error"] = exc.message
        return result
    jobs = _owned_jobs(sid, link, listed["jobs"])
    result["gateway_running"] = listed.get("gateway_running")
    result["warning"] = listed.get("warning")
    result["one_shots"] = [dict(_job(job), executions=[]) for job in jobs
                           if job.get("name") == _once_name(sid)][:ONE_SHOT_LIMIT]
    result["orphan_jobs"] = [_job(job) for job in jobs if job.get("name") == f"living-spaces:{sid}"
                             and (not link or job["job_id"] != link["cron_job_id"])]
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
        return ({"cron_job_id": None, "kind": None, "enabled": None, "state": "recovery",
                 "next_run_at": None, "missing": False, "orphan_jobs": state["orphan_jobs"]}
                if state["orphan_jobs"] else None)
    job = state["job"] or {}
    kind = ("agent" if job["uses_model"] else "feed") if state["job"] else state["link"]["kind"]
    result = {"cron_job_id": state["link"]["cron_job_id"], "kind": kind,
              "enabled": job.get("enabled"), "state": job.get("state"),
              "next_run_at": job.get("next_run_at"), "missing": state["missing"]}
    if state["orphan_jobs"]:
        result["orphan_jobs"] = state["orphan_jobs"]
    return result


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
        _require_conservative_nominal_agent_spacing(cadence)
        mode = {"prompt": agent_prompt(sid, prompt), "no_agent": False}
    elif prompt is not None:
        raise SpacesError("invalid", "Feed upkeep takes no prompt")
    else:
        mode = {"prompt": None, "script": _shim(sid).name, "no_agent": True}
    _scheduling_allowed()
    with db.write() as conn:
        space = _space(conn, sid)
        if space["status"] == "archived":
            raise SpacesError("archived", "Unarchive the Space before scheduling upkeep")
        if kind == "feed":
            revision = conn.execute("SELECT r.manifest FROM revisions r JOIN spaces s ON s.id=r.space AND s.head_rev=r.rev WHERE s.id=?", (sid,)).fetchone()
            if revision is None or (json.loads(revision["manifest"]).get("upkeep") or {}).get("handler") != "feed":
                raise SpacesError("invalid", "Feed upkeep needs upkeep.handler feed in the Space manifest")
        old = _link(conn, sid)
        jobs = _jobs()["jobs"]
        orphans = [job["job_id"] for job in _owned_jobs(sid, old, jobs)
                   if job.get("name") == f"living-spaces:{sid}"
                   and (not old or job["job_id"] != old["cron_job_id"])]
        if orphans:
            raise SpacesError("blocked", "Pause/remove this Space's unlinked recurring upkeep jobs before scheduling again: "
                              + ", ".join(orphans), reason="upkeep_recovery_required", orphan_job_ids=orphans)
        claim = _refresh_claim(conn, sid)
        claimed_id = claim["cron_job_id"] if claim and claim["space_created_at"] == space["created_at"] else None
        unclaimed_one_shots = [job["job_id"] for job in jobs
                               if job.get("name") == _once_name(sid) and job["job_id"] != claimed_id]
        if unclaimed_one_shots:
            raise SpacesError("blocked", "This Space has one-shot refresh work without a durable claim. "
                              "Its completion is unknown. Use Upkeep Remove before retrying: "
                              + ", ".join(unclaimed_one_shots), reason="refresh_outcome_unknown",
                              orphan_job_ids=unclaimed_one_shots)
        shim = _shim(sid)
        had_shim = shim.exists()
        if kind == "feed":
            template = (PACKAGE / "scripts" / "refresh_space.py").read_text()
            shim.parent.mkdir(parents=True, exist_ok=True)
            shim.write_text(template.replace("__LIVING_SPACES_PACKAGE__", repr(str(PACKAGE))).replace("__LIVING_SPACES_SID__", repr(sid)))
        try:
            jid = _create(**mode, schedule=cadence, name=f"living-spaces:{sid}", deliver="local",
                          catch_up=True, timezone=timezone, paused=True)
        except SpacesError as failure:
            if not had_shim and not failure.extra.get("orphan_job_id"):
                shim.unlink(missing_ok=True)
            raise
        try:
            _mutate("resume", jid)
            if old and any(job["job_id"] == old["cron_job_id"] for job in _jobs()["jobs"]):
                _mutate("remove", old["cron_job_id"])
        except SpacesError as failure:
            if (old and failure.extra.get("reason") == "cron_remove_outcome_unknown"
                    and failure.extra.get("job_id") == old["cron_job_id"]):
                raise SpacesError("blocked", f"{failure.message}. Replacement was not committed. "
                                  f"Candidate {jid} is retained unlinked, last confirmed enabled. "
                                  f"The SQLite link remains {old['cron_job_id']}, which may be missing natively. "
                                  "Both jobs may run. Use Pause/Remove to recover before scheduling again.",
                                  reason="cron_remove_outcome_unknown", old_job_id=old["cron_job_id"],
                                  orphan_job_id=jid, retained_job={"id": jid, "enabled": True},
                                  original=failure.to_dict()) from failure
            pause_failure = None
            try:
                _mutate("pause", jid, reason=f"Living Spaces upkeep replacement by {actor} failed")
            except SpacesError as unpaused:
                pause_failure = unpaused
            try:
                _mutate("remove", jid)
            except SpacesError as cleanup:
                if pause_failure is None:
                    state = f"Disabling it succeeded before removal was attempted, but Job {jid} remains unlinked."
                    extra = {}
                else:
                    state = (f"Disabling it also failed: {pause_failure.message}. "
                             f"Job {jid} may still be enabled and consume quota, and it remains unlinked.")
                    extra = {"pause": pause_failure.to_dict()}
                raise SpacesError("blocked", f"{failure.message}; cleanup of the newly created Hermes cron job {jid} also failed: "
                                  f"{cleanup.message}. {state}",
                                  reason="cron_cleanup_failed", orphan_job_id=jid,
                                  original=failure.to_dict(), cleanup=cleanup.to_dict(), **extra) from failure
            if not had_shim:
                shim.unlink(missing_ok=True)
            raise
        if kind == "agent":
            shim.unlink(missing_ok=True)
        if old:
            conn.execute("DELETE FROM refresh_claims WHERE space=? AND cron_job_id=?", (sid, old["cron_job_id"]))
        conn.execute("DELETE FROM upkeep_links WHERE space=?", (sid,))
        conn.execute("INSERT INTO upkeep_links(space,cron_job_id,kind,created_at,created_by) VALUES(?,?,?,?,?)",
                     (sid, jid, kind, db.now(), actor))
    return get_upkeep(sid)


def _carry_run_reply(error, native):
    # Rule: every error raised after a run was dispatched carries the run reply at top-level native. If the
    # error held a different reply of its own, the whole original error moves under post_run_error.
    if error.extra.get("native") is native:
        return error
    if error.extra.get("reason") in ("native_refused", "cron_unavailable", "cron_unverified", "cron_response_invalid"):
        return SpacesError("blocked", error.message, **{**error.extra, "reason": "post_run_check_failed",
                           "native": native, "verification": error.to_dict(), "post_run_error": error.to_dict()})
    return SpacesError(error.code, error.message, **{**error.extra, "native": native, "post_run_error": error.to_dict()})


@contextmanager
def _after_run(native):
    try:
        yield
    except SpacesError as exc:
        carried = _carry_run_reply(exc, native)
        if carried is exc:
            raise
        raise carried from exc


def _run_now(sid, jid, *, on_reply=None):
    # Public run may execute inline and call Space tools, so never hold SQLite's write lock here.
    native = _mutate("run", jid, on_run_reply=on_reply)
    with _after_run(native):
        try:
            with db.write() as conn:
                row = conn.execute("SELECT status FROM spaces WHERE id=?", (sid,)).fetchone()
                if row is None or row["status"] == "archived":
                    if any(job["job_id"] == jid for job in _jobs()["jobs"]):
                        _mutate("remove" if row is None else "pause", jid)
                    code = "not_found" if row is None else "archived"
                    raise SpacesError(code, "Space was deleted or archived during the run request", native=native)
        except SpacesError:
            raise
        except Exception as exc:
            raise SpacesError("blocked", f"Hermes accepted the run, but Living Spaces could not recheck the Space afterwards: {exc}",
                              reason="post_run_check_failed", native=native) from exc
    return native


def upkeep_action(sid, action, *, actor):
    if action not in ACTIONS:
        raise SpacesError("invalid", "action must be pause, resume, run or remove")
    if action in ("resume", "run"):
        _scheduling_allowed()
    with db.write() as conn:
        space = _space(conn, sid)
        status = space["status"]
        link = _link(conn, sid)
        if action in ("resume", "run"):
            if link is None:
                raise SpacesError("not_found", "No upkeep scheduled")
            if status == "archived":
                raise SpacesError("archived", "Unarchive the Space before running upkeep")
            if action == "run":
                claim = _refresh_claim(conn, sid)
                claimed_id = claim["cron_job_id"] if claim and claim["space_created_at"] == space["created_at"] else None
                unclaimed_one_shots = [job["job_id"] for job in _jobs()["jobs"]
                                       if job.get("name") == _once_name(sid) and job["job_id"] != claimed_id]
                if unclaimed_one_shots:
                    raise SpacesError("blocked", "This Space has one-shot refresh work without a durable claim. "
                                      "Its completion is unknown. Use Upkeep Remove before retrying: "
                                      + ", ".join(unclaimed_one_shots), reason="refresh_outcome_unknown",
                                      orphan_job_ids=unclaimed_one_shots)
            if action == "resume":
                _mutate(action, link["cron_job_id"])
        else:
            claim = _refresh_claim(conn, sid)
            targets = _owned_jobs(sid, link, _jobs()["jobs"], claim=claim)
            target_ids = {job["job_id"] for job in targets}
            if action == "remove" and claim:
                target_ids.add(claim["cron_job_id"])
            if link is None and not target_ids:
                raise SpacesError("not_found", "No upkeep scheduled")
            args = {"reason": f"Paused from Living Spaces by {actor}"} if action == "pause" else {}
            for jid in sorted(target_ids):
                _mutate(action, jid, **args)
            remaining = _owned_jobs(sid, link, _jobs()["jobs"], claim=claim)
            if ((action == "remove" and remaining)
                    or (action == "pause" and any(job.get("enabled") is not False for job in remaining))):
                raise SpacesError("blocked", f"This Space's upkeep {action} could not be verified", reason="cron_unverified")
        if action == "remove":
            _shim(sid).unlink(missing_ok=True)
            conn.execute("DELETE FROM upkeep_links WHERE space=?", (sid,))
            conn.execute("DELETE FROM refresh_claims WHERE space=?", (sid,))
    if action == "run" and link is not None:
        native = _run_now(sid, link["cron_job_id"])
        with _after_run(native):
            result = get_upkeep(sid)
    else:
        native = None
        result = get_upkeep(sid)
    if action == "run":
        result["dispatch"] = native
    return result


def _refresh_outcome(native):
    if not isinstance(native, dict):
        return "unresolved"
    if native.get("success") is False:
        return "refused"
    job = native.get("job")
    if not isinstance(job, dict):
        return "unresolved"
    if (job.get("executed") is False or job.get("execution_skipped")
            or job.get("execution_success") is False):
        return "refused"
    if job.get("executed") is True:
        if job.get("execution_success") is True:
            return "completed"
        if job.get("execution_mode") == "background":
            return "background"
    return "unresolved"


def _refresh_claim(conn, sid):
    row = conn.execute("SELECT * FROM refresh_claims WHERE space=?", (sid,)).fetchone()
    return dict(row) if row else None


def _update_refresh_claim(claim, native, *, phase="unresolved", settled=False):
    baseline = "null" if claim["created_one_shot"] else None
    job = native.get("job") if isinstance(native, dict) else None
    if (not claim["created_one_shot"] and isinstance(job, dict) and _refresh_outcome(native) == "background"
            and job.get("job_id") == claim["cron_job_id"] and "last_run_at" in job
            and (job["last_run_at"] is None or _seconds(job["last_run_at"]) is not None)):
        # Native acquires the per-job fire claim before producing this reply. An earlier list
        # stamp could belong to a run that finished before our native claim was acquired.
        baseline = json.dumps(job["last_run_at"])
    if phase != "pending":
        phase = "background" if _refresh_outcome(native) == "background" and baseline is not None else "unresolved"
    try:
        with db.write() as conn:
            identity = (claim["space"], claim["space_created_at"], claim["token"])
            if settled:
                conn.execute("DELETE FROM refresh_claims WHERE space=? AND space_created_at=? AND token=?", identity)
            else:
                conn.execute("UPDATE refresh_claims SET native=?,baseline_completion=?,phase=? "
                             "WHERE space=? AND space_created_at=? AND token=?",
                             (json.dumps(native), baseline, phase, *identity))
    except Exception as exc:
        raise SpacesError("blocked", f"Could not preserve the refresh claim for job {claim['cron_job_id']}: {exc}",
                          reason="post_run_check_failed", native=native, cron_job_id=claim["cron_job_id"]) from exc


def _join_refresh(conn, claim, *, actor):
    native = json.loads(claim["native"]) if claim["native"] is not None else None
    result = {"kind": "cron", "cron_job_id": claim["cron_job_id"], "dispatch": native,
              "joined": True, "refresh_state": claim["phase"]}
    if claim["phase"] == "background":
        try:
            job = next((job for job in _jobs()["jobs"] if job["job_id"] == claim["cron_job_id"]), None)
        except SpacesError as exc:
            result["recovery"] = {"reason": "refresh_outcome_unknown", "verification": exc.to_dict()}
            return result
        stamp = job.get("last_run_at") if job else None
        if (_seconds(stamp) is not None and claim["baseline_completion"] is not None
                and stamp != json.loads(claim["baseline_completion"])):
            if claim["created_one_shot"]:
                with _after_run(native):
                    _consume_one_shot(claim["cron_job_id"], native, actor=actor)
            conn.execute("DELETE FROM refresh_claims WHERE space=? AND token=?", (claim["space"], claim["token"]))
            return None
        if job is None:
            result["refresh_state"] = "unresolved"
            result["recovery"] = {"reason": "refresh_outcome_unknown",
                                  "message": "The native job is missing, not confirmed finished. Use Upkeep Remove to recover."}
    elif claim["phase"] == "unresolved":
        result["recovery"] = {"reason": "refresh_outcome_unknown",
                              "message": "Native completion is unconfirmed. Use Upkeep Remove before retrying."}
    elif claim["phase"] == "pending" and db.now() - claim["created_at"] >= 120:
        result["recovery"] = {"reason": "refresh_outcome_unknown",
                              "message": "Native completion is unconfirmed. This pending refresh is not released by age. "
                                         "Use Upkeep Remove before retrying."}
    return result


def _cleanup_failed_refresh(jid, failure, *, actor, native, may_be_running):
    pause_failure = None
    try:
        _mutate("pause", jid, reason=f"Living Spaces refresh by {actor} failed")
    except SpacesError as unpaused:
        pause_failure = unpaused
    try:
        if may_be_running:
            if pause_failure is not None:
                raise pause_failure
        elif any(job["job_id"] == jid for job in _jobs()["jobs"]):
            _mutate("remove", jid)
    except SpacesError as cleanup:
        if pause_failure is None:
            state = f"Disabling it succeeded before cleanup was attempted. Job {jid} may remain paused and unlinked."
            extra = {}
        else:
            state = (f"Disabling it also failed: {pause_failure.message}. "
                     f"Job {jid} may still be enabled and consume quota, and may remain unlinked.")
            extra = {"pause": pause_failure.to_dict()}
        if native is not None:
            extra["native"] = native
        if may_be_running:
            state += " Its execution may still be running, so it was not removed and its refresh claim is retained."
        raise SpacesError("blocked", f"{failure.message}; cleanup of the newly created Hermes cron job {jid} also failed: "
                          f"{cleanup.message}. {state}", reason="cron_cleanup_failed", orphan_job_id=jid,
                          original=failure.to_dict(), cleanup=cleanup.to_dict(), **extra) from failure


def refresh_now(sid, upkeep, *, actor):
    _scheduling_allowed()
    with db.write() as conn:
        space = _space(conn, sid)
        if space["status"] == "archived":
            raise SpacesError("archived", "Unarchive the Space before refreshing")
        claim = _refresh_claim(conn, sid)
        if claim and claim["space_created_at"] != space["created_at"]:
            conn.execute("DELETE FROM refresh_claims WHERE space=? AND token=?", (sid, claim["token"]))
            claim = None
        if claim:
            joined = _join_refresh(conn, claim, actor=actor)
            if joined is not None:
                return joined
        unclaimed_one_shots = [job["job_id"] for job in _jobs()["jobs"]
                               if job.get("name") == _once_name(sid)]
        if unclaimed_one_shots:
            raise SpacesError("blocked", "This Space has one-shot refresh work without a durable claim. "
                              "Its completion is unknown. Use Upkeep Remove before retrying: "
                              + ", ".join(unclaimed_one_shots), reason="refresh_outcome_unknown",
                              orphan_job_ids=unclaimed_one_shots)
        link = _link(conn, sid)
        created = not (link and link["kind"] == "agent")
        if created:
            jid = _create(prompt=agent_prompt(sid, upkeep.get("prompt")), schedule=ONE_SHOT_SLOT, repeat=1,
                          name=_once_name(sid), no_agent=False, deliver="local", catch_up=True, paused=True)
        else:
            jid = link["cron_job_id"]
        conn.execute("INSERT INTO refresh_claims(space,space_created_at,token,cron_job_id,created_one_shot,"
                     "baseline_completion,phase,created_at) VALUES(?,?,?,?,?,?,'pending',?)",
                     (sid, space["created_at"], uuid.uuid4().hex, jid, int(created), "null" if created else None, db.now()))
        claim = _refresh_claim(conn, sid)
        assert claim is not None
    dispatched = False
    native = None
    try:
        with db.write() as conn:
            current = _space(conn, sid)
            owned = _refresh_claim(conn, sid)
            if (current["created_at"] != claim["space_created_at"] or owned is None
                    or owned["token"] != claim["token"]):
                raise SpacesError("blocked", "This refresh was removed before dispatch", reason="refresh_claim_lost")
            if current["status"] == "archived":
                raise SpacesError("archived", "Unarchive the Space before refreshing")
            if created:
                _mutate("resume", jid)
        dispatched = True
        native = _run_now(sid, jid, on_reply=lambda reply: _update_refresh_claim(claim, reply))
        if _refresh_outcome(native) == "refused":
            raise SpacesError("blocked", "Hermes cron did not complete the refresh execution",
                              reason="native_refused", native=native)
    except SpacesError as failure:
        if dispatched:
            native = failure.extra.get("native", native)
        terminal = not dispatched or _refresh_outcome(native) in ("completed", "refused")
        try:
            if created and failure.code != "not_found":
                _cleanup_failed_refresh(jid, failure, actor=actor, native=native, may_be_running=not terminal)
        except SpacesError as cleanup:
            failure = cleanup
            terminal = False
        try:
            _update_refresh_claim(claim, native, phase="unresolved", settled=terminal)
        except SpacesError as claim_failure:
            failure.extra["claim_error"] = claim_failure.to_dict()
        raise failure
    # dispatch stays the verbatim native reply; one_shot records what happened to the owned job afterwards.
    result = {"kind": "cron", "cron_job_id": jid, "dispatch": native}
    outcome = _refresh_outcome(native)
    try:
        with _after_run(native):
            if created and outcome in ("completed", "background"):
                result["one_shot"] = _consume_one_shot(jid, native, actor=actor, background=outcome == "background")
            elif created and outcome == "unresolved":
                result["refresh_state"] = "unresolved"
                result["recovery"] = {"reason": "refresh_outcome_unknown",
                                      "message": "Native completion is unconfirmed. Use Upkeep Remove before retrying."}
                try:
                    _mutate("pause", jid, reason=f"Living Spaces refresh by {actor} has an unconfirmed native outcome")
                except SpacesError as pause_failure:
                    raise SpacesError("blocked", f"Native refresh completion is unconfirmed, and its Hermes cron one-shot {jid} "
                                      f"could not be disabled ({pause_failure.message}). It may still be enabled and may run "
                                      "again at its scheduled slot. Unknown work was not removed; its refresh claim is retained. "
                                      "Use Upkeep Remove before retrying.",
                                      reason="one_shot_not_consumed", orphan_job_id=jid, native=native,
                                      refresh_state="unresolved", recovery=result["recovery"],
                                      pause=pause_failure.to_dict()) from pause_failure
            _update_refresh_claim(claim, native, phase="unresolved", settled=outcome == "completed")
    except SpacesError as failure:
        try:
            _update_refresh_claim(claim, native, phase="unresolved")
        except SpacesError as claim_failure:
            failure.extra["claim_error"] = claim_failure.to_dict()
        raise
    return result


def _consume_one_shot(jid, native, *, actor, background=False):
    # Hermes counts a manual run as an extra fire, so the once slot stays pending after the run. A background
    # run is still in flight, and removing its job would cancel it, so that job is only disabled.
    pause_failure = None
    try:
        _mutate("pause", jid, reason=f"Living Spaces refresh by {actor} already ran this one-shot")
    except SpacesError as exc:
        pause_failure = exc
    if background:
        if pause_failure is None:
            return {"job_id": jid, "consumed": "paused", "execution_mode": "background"}
        raise SpacesError("blocked", f"The refresh started in the background, but its Hermes cron one-shot {jid} "
                          f"could not be disabled ({pause_failure.message}). It stays scheduled for about 7 days after this "
                          "refresh and may run again then; pause or remove it from Upkeep after this run finishes.",
                          reason="one_shot_not_consumed", orphan_job_id=jid, native=native,
                          pause=pause_failure.to_dict()) from pause_failure
    try:
        _mutate("remove", jid)
        return {"job_id": jid, "consumed": "removed"}
    except SpacesError as cleanup:
        if pause_failure is None:
            return {"job_id": jid, "consumed": "paused", "cleanup": cleanup.to_dict()}
        raise SpacesError("blocked", f"The refresh ran, but its Hermes cron one-shot {jid} could not be disabled "
                          f"({pause_failure.message}) or removed ({cleanup.message}). It stays scheduled for about 7 days "
                          "after this refresh and may run again then; pause or remove it from Upkeep.",
                          reason="one_shot_not_consumed", orphan_job_id=jid, native=native,
                          pause=pause_failure.to_dict(), cleanup=cleanup.to_dict()) from cleanup


def pause_for_archive(conn, sid):
    link = _link(conn, sid)
    claim = _refresh_claim(conn, sid)
    try:
        targets = {job["job_id"] for job in _owned_jobs(sid, link, _jobs()["jobs"], claim=claim)}
        for jid in sorted(targets):
            _mutate("pause", jid, reason="Living Space archived")
        if any(job.get("enabled") is not False for job in _owned_jobs(sid, link, _jobs()["jobs"], claim=claim)):
            raise SpacesError("blocked", "This Space's upkeep pause could not be verified", reason="cron_unverified")
    except SpacesError as exc:
        raise SpacesError("blocked", "Could not pause this Space's upkeep, so it was not archived", reason=exc.message) from exc


def on_delete(conn, sid):
    """Remove future native work within the caller's Space deletion transaction."""
    _space(conn, sid)
    link = _link(conn, sid)
    claim = _refresh_claim(conn, sid)
    targets = {job["job_id"] for job in _owned_jobs(sid, link, _jobs()["jobs"], claim=claim)}
    if claim:
        targets.add(claim["cron_job_id"])
    for jid in sorted(targets):
        _mutate("remove", jid)
    if _owned_jobs(sid, link, _jobs()["jobs"], claim=claim):
        raise SpacesError("blocked", "This Space's upkeep removal could not be verified", reason="cron_unverified")
    _shim(sid).unlink(missing_ok=True)
    conn.execute("DELETE FROM upkeep_links WHERE space=?", (sid,))
    conn.execute("DELETE FROM refresh_claims WHERE space=?", (sid,))
    return link is not None
