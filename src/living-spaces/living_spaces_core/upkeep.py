from __future__ import annotations

import json
import re
import sqlite3

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import db, maintenance
from .errors import SpacesError

PACKAGE = Path(__file__).resolve().parents[1]
KINDS = ("agent", "feed")
ACTIONS = ("pause", "resume", "run", "remove", "recover")
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
    return maintenance.invoke(action, args, lambda: _public_call(action, **args))


def _public_call(action, **args):
    try:
        reply = _context().dispatch_tool("cronjob_manage", {"action": action, **args})
        result = json.loads(reply) if isinstance(reply, str) else reply
    except SpacesError:
        raise
    except Exception as exc:
        raise SpacesError("blocked", f"Hermes cron {action} is unavailable: {exc}", reason="cron_unavailable") from exc
    if not isinstance(result, dict) or result.get("success") is not True:
        message = result.get("error") if isinstance(result, dict) else "Invalid public cron response"
        reason = "native_refused" if isinstance(result, dict) and result.get("success") is False else "cron_response_invalid"
        raise SpacesError("blocked", f"Hermes cron {action} refused: {message}", reason=reason, native=result)
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
    result = None
    failure = None
    try:
        result = _call(action, job_id=jid, **args)
    except SpacesError as exc:
        if action != "remove":
            raise
        failure = exc
        failure.extra.update(action=action, job_id=jid)
    try:
        job = next((job for job in _jobs()["jobs"] if job["job_id"] == jid), None)
    except SpacesError as verification:
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
    failure.extra.update(created_job_id=jid, created_job_removed=True)
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


@dataclass
class _Projection:
    """One public read's native job listing. Only summary() consults it; authority paths always list fresh."""
    relevant: bool
    listed: dict | None = None
    error: SpacesError | None = None

    def listing(self):
        if self.listed is None and self.error is None:
            try:
                self.listed = _jobs()
            except SpacesError as exc:
                self.error = exc
        if self.error is not None:
            raise self.error
        return self.listed


_PROJECTION: ContextVar[_Projection | None] = ContextVar("living_spaces_upkeep_projection", default=None)


def _relevant(sids):
    """Whether any Space has native state worth a cron list: a link, a retained claim or an unsettled operation."""
    if sids is None:
        return True
    sids = list(sids)
    if not sids:
        return False
    marks = ",".join("?" * len(sids))
    with db.read() as conn:
        return conn.execute(
            f"SELECT 1 FROM upkeep_links WHERE space IN ({marks}) UNION ALL "
            f"SELECT 1 FROM refresh_claims WHERE space IN ({marks}) UNION ALL "
            f"SELECT 1 FROM maintenance_operations WHERE space IN ({marks}) AND phase!='retired' LIMIT 1",
            (*sids, *sids, *sids)).fetchone() is not None


@contextmanager
def read_projection(sids=None):
    """Share one native listing across the summaries of one public read.

    `sids` names every Space the read will summarize; when none has relevant native state, no list runs and
    summaries are None. `None` means a single-Space read that always lists, so detail keeps orphan discovery.
    """
    token = _PROJECTION.set(_Projection(_relevant(sids)))
    try:
        yield
    finally:
        _PROJECTION.reset(token)


def _read(sid, projection=None):
    with db.read() as conn:
        _space(conn, sid)
        link = _link(conn, sid)
        saved = conn.execute("SELECT recovery_settings FROM maintenance_spaces WHERE space=?", (sid,)).fetchone()
        operations = [dict(row) for row in conn.execute(
            "SELECT o.command AS action,o.cron_job_id,o.phase FROM maintenance_operations o "
            "JOIN maintenance_spaces m ON m.space=o.space AND m.incarnation=o.incarnation "
            "WHERE o.space=? AND o.phase!='retired' "
            "AND o.command IN ('schedule','pause','resume','run','remove','refresh') "
            "ORDER BY o.created_at,o.token", (sid,))]
    result = {"link": link, "job": None, "executions": [], "one_shots": [], "orphan_jobs": [], "missing": False,
              "error": None, "unavailable": dict(UNAVAILABLE), "recovery": None, "recovery_aid": None}
    if saved and saved["recovery_settings"]:
        result["recovery_aid"] = {"label": "Recovery settings aid", "authoritative": False,
                                  "settings": json.loads(saved["recovery_settings"])}
    # A run whose native reply was recorded as background is the normal in-flight case: its reply is durable and
    # a later Run joins and settles it from the native last-run stamp. Only operations without a durable native
    # confirmation are uncertain, and only those raise the recovery barrier.
    in_flight = [op for op in operations if op["phase"] == "background" and op["action"] in ("run", "refresh")]
    operations = [op for op in operations if op not in in_flight]
    if in_flight:
        result["in_flight"] = in_flight
    if operations:
        result["recovery"] = {
            "state": "unknown", "operations": operations,
            "cause": "A native upkeep request has no durable SQLite confirmation. The process may have stopped "
                     "between the native effect and the local update; the request may still be in flight.",
            "options": "Check the native jobs below. You can pause future work or confirm recovery to remove "
                       "Space-owned jobs and clear the barrier after verified absence. Already-running work may finish. "
                       "No run will be replayed. Recreating upkeep is a separate request using the saved settings aid.",
            "evidence": "Native inventory can confirm current presence and enabled state, not an uncertain model run's outcome.",
        }
    try:
        listed = projection.listing() if projection is not None else _jobs()
    except SpacesError as exc:
        result["error"] = exc.message
        result["native_error"] = {**exc.to_dict(), "retryable": True}
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
    projection = _PROJECTION.get()
    if projection is None:
        state = _read(sid)
    elif not projection.relevant:
        return None
    else:
        state = _read(sid, projection)
    if state["recovery"]:
        return {"cron_job_id": state["link"]["cron_job_id"] if state["link"] else None,
                "kind": state["link"]["kind"] if state["link"] else None,
                "enabled": None, "state": "unknown", "next_run_at": None, "missing": state["missing"],
                "recovery": state["recovery"]}
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
    settings = dict(kind=kind, cadence=cadence, timezone=timezone, prompt=prompt)
    with maintenance.control(sid, "schedule", actor=actor, kind=kind, settings=settings) as op, maintenance.transaction(op) as conn:
        space = _space(conn, sid)
        if space["status"] == "archived":
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
        maintenance.retire_resources(conn, sid, jid=old["cron_job_id"] if old else None)
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


def _run_now(sid, jid, *, claim, on_reply=None):
    # Inline native execution may call Space tools. No SQLite writer spans this call.
    try:
        native = _call("run", job_id=jid)
    except SpacesError as failure:
        try:
            with db.read() as conn:
                maintenance.fence(conn, claim, work=True, archived=True)
        except SpacesError as lifecycle:
            raise SpacesError(lifecycle.code, lifecycle.message,
                              **{**lifecycle.extra, "native": failure.extra.get("native"),
                                 "post_run_error": failure.to_dict()}) from failure
        except Exception as check:
            failure.extra["lifecycle_check_error"] = str(check)
        raise
    with _after_run(native):
        lifecycle = None
        receipt_error = None
        if on_reply is not None:
            try:
                on_reply(native)
            except SpacesError as exc:
                if exc.code not in ("not_found", "archived") and exc.extra.get("reason") != "refresh_claim_lost":
                    receipt_error = exc
                else:
                    lifecycle = exc
            except Exception as exc:
                receipt_error = SpacesError("blocked", f"Could not preserve the native run reply: {exc}",
                                            reason="post_run_check_failed", native=native)
        try:
            with db.read() as conn:
                maintenance.fence(conn, claim, work=True, archived=True)
        except SpacesError as exc:
            lifecycle = exc
        except Exception as exc:
            raise SpacesError("blocked", f"Could not recheck the Space after native dispatch: {exc}",
                              reason="post_run_check_failed", native=native) from exc
        verification = None
        try:
            _jobs()
        except SpacesError as exc:
            verification = exc
        if lifecycle is not None:
            cleanup = None
            # Observe old-target inventory separately from dispatch verification. Observation
            # is safe even after reincarnation; a mutation always needs the original fence.
            if lifecycle.code in ("not_found", "archived"):
                try:
                    remaining = any(job["job_id"] == jid for job in _jobs()["jobs"])
                    if remaining and lifecycle.code == "archived":
                        with maintenance.transaction(claim):
                            _mutate("pause", jid)
                except SpacesError as exc:
                    cleanup = exc
            diagnostic = cleanup or verification
            message = lifecycle.message + (f"; native cleanup/check failed: {diagnostic.message}" if diagnostic else "")
            extra = {"native": native, **lifecycle.extra}
            extra["native"] = native
            if verification:
                extra["verification"] = verification.to_dict()
            if cleanup:
                extra.update(cleanup=cleanup.to_dict(), post_run_error=cleanup.to_dict())
            if receipt_error:
                extra["receipt_error"] = receipt_error.to_dict()
            raise SpacesError(lifecycle.code, message, **extra) from lifecycle
        if receipt_error is not None:
            if verification:
                receipt_error.extra["verification"] = verification.to_dict()
            raise receipt_error
        if verification is not None:
            raise SpacesError("blocked", verification.message, reason="post_run_check_failed", native=native,
                              action="run", job_id=jid, verification=verification.to_dict()) from verification
    return native


def _recover_upkeep(sid, *, actor, confirm):
    if confirm != sid:
        raise SpacesError("invalid", "Confirm recovery for this Space before removing its native upkeep jobs.",
                          reason="recovery_confirmation_required")
    try:
        # Observe actual authority before any recovery mutation, including a retry.
        _jobs()
        try:
            result = upkeep_action(sid, "remove", actor=actor)
        except SpacesError as exc:
            if exc.code != "not_found":
                raise
            result = get_upkeep(sid)
        if result["error"]:
            raise SpacesError("blocked", result["error"], reason="cron_unavailable")
        return result
    except SpacesError as exc:
        if exc.code != "blocked":
            raise
        raise SpacesError("blocked", "Recovery could not verify native upkeep. Retry when Hermes cron is available. "
                          "Nothing was recreated or replayed.", reason="upkeep_recovery_unavailable", retryable=True,
                          original=exc.to_dict()) from exc


def upkeep_action(sid, action, *, actor, confirm=None):
    if action not in ACTIONS:
        raise SpacesError("invalid", "action must be pause, resume, run, remove or recover")
    if action == "recover":
        return _recover_upkeep(sid, actor=actor, confirm=confirm)
    if action in ("resume", "run"):
        _scheduling_allowed()
    if action == "run":
        with db.read() as conn:
            space = _space(conn, sid)
            link = _link(conn, sid)
            if link is None:
                raise SpacesError("not_found", "No upkeep scheduled")
            if space["status"] == "archived":
                raise SpacesError("archived", "Unarchive the Space before running upkeep")
        if link["kind"] == "feed":
            with db.write() as conn:
                _space(conn, sid)
                feed = maintenance._feed_control(conn, sid, "run")
            if feed is not None:
                with maintenance.scope(None):
                    with maintenance.transaction(feed, feed_admission=True):
                        pass
                    native = _call("run", job_id=feed["cron_job_id"])
                    with _after_run(native):
                        try:
                            with maintenance.transaction(feed):
                                pass
                        except SpacesError:
                            raise
                        except Exception as exc:
                            raise SpacesError("blocked", f"Could not recheck the Space after native dispatch: {exc}",
                                              reason="post_run_check_failed", native=native) from exc
                        _jobs()
                        result = get_upkeep(sid)
                    result["dispatch"] = native
                    return result
        dispatched = refresh_now(sid, {}, actor=actor, command="run", target=link["cron_job_id"])
        native = dispatched["dispatch"]
        with _after_run(native):
            result = get_upkeep(sid)
        result["dispatch"] = native
        for key in ("joined", "refresh_state", "recovery", "disable_obligation"):
            if key in dispatched:
                result[key] = dispatched[key]
        return result
    with maintenance.control(sid, action, actor=actor, kind="feed") as op, maintenance.transaction(op) as conn:
        link = _link(conn, sid)
        held = _refresh_claim(conn, sid)
        if action == "resume":
            _mutate(action, link["cron_job_id"])
        else:
            targets = _owned_jobs(sid, link, _jobs()["jobs"], claim=held)
            target_ids = {job["job_id"] for job in targets}
            if action == "remove" and held and held["cron_job_id"]:
                target_ids.add(held["cron_job_id"])
            if link is None and not target_ids:
                # A durable uncertain create can have no returned ID. Explicit discovery plus
                # verified absence is its operator-authorized abandonment boundary.
                prior = conn.execute("SELECT 1 FROM maintenance_operations WHERE space=? AND incarnation=? "
                                     "AND token!=? AND phase!='retired'", (sid, op["incarnation"], op.get("token", ""))).fetchone()
                if action != "remove" or (held is None and prior is None):
                    raise SpacesError("not_found", "No upkeep scheduled")
            args = {"reason": f"Paused from Living Spaces by {actor}"} if action == "pause" else {}
            for jid in sorted(target_ids):
                _mutate(action, jid, **args)
            remaining = _owned_jobs(sid, link, _jobs()["jobs"], claim=held)
            if ((action == "remove" and remaining)
                    or (action == "pause" and any(job.get("enabled") is not False for job in remaining))):
                raise SpacesError("blocked", f"This Space's upkeep {action} could not be verified", reason="cron_unverified")
        if action == "remove":
            _shim(sid).unlink(missing_ok=True)
            conn.execute("DELETE FROM upkeep_links WHERE space=?", (sid,))
            maintenance.retire_resources(conn, sid, all_resources=True)
    return get_upkeep(sid)


def _refresh_outcome(native):
    return maintenance.outcome(native)


def _refresh_claim(conn, sid):
    return maintenance.claim(conn, sid)


def _update_refresh_claim(claim, native, *, phase="unresolved", settled=False):
    try:
        maintenance.update_work(claim, native, phase=phase, settled=settled)
    except SpacesError:
        raise
    except Exception as exc:
        raise SpacesError("blocked", f"Could not preserve the refresh claim for job {claim['cron_job_id']}: {exc}",
                          reason="post_run_check_failed", native=native, cron_job_id=claim["cron_job_id"]) from exc


def _join_refresh(conn, claim, *, actor):
    return maintenance.join(conn, claim, actor=actor)


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


def refresh_now(sid, upkeep, *, actor, command="refresh", target=None):
    _scheduling_allowed()
    claim, joined = maintenance.acquire(sid, command, actor=actor, target=target)
    if joined is not None:
        return joined
    assert claim is not None
    created = bool(claim["created_one_shot"])
    jid = claim["cron_job_id"]
    dispatched = False
    native = None
    with maintenance.scope(claim):
        try:
            with maintenance.transaction(claim) as conn:
                maintenance.fence(conn, claim, work=True, archived=True)
                if created:
                    jid = _create(prompt=agent_prompt(sid, upkeep.get("prompt")), schedule=ONE_SHOT_SLOT, repeat=1,
                                  name=_once_name(sid), no_agent=False, deliver="local", catch_up=True, paused=True)
                    maintenance.bind_job(conn, claim, jid)
            with maintenance.transaction(claim) as conn:
                maintenance.fence(conn, claim, work=True, archived=True)
                if created:
                    _mutate("resume", jid)
            dispatched = True
            native = _run_now(sid, jid, claim=claim, on_reply=lambda reply: _update_refresh_claim(claim, reply))
            if command == "refresh" and _refresh_outcome(native) == "refused":
                raise SpacesError("blocked", "Hermes cron did not complete the refresh execution",
                                  reason="native_refused", native=native)
        except SpacesError as failure:
            native = failure.extra.get("native", native) if dispatched else native
            terminal = (not dispatched or failure.extra.get("unsent") is True
                        or maintenance.outcome(native, jid) in ("completed", "refused"))
            creation_cleanup_failed = created and not jid and isinstance(failure.extra.get("orphan_job_id"), str)
            if creation_cleanup_failed:
                with maintenance.transaction(claim) as conn:
                    jid = failure.extra["orphan_job_id"]
                    maintenance.bind_job(conn, claim, jid)
                terminal = False
            stale = failure.code == "not_found" or failure.extra.get("reason") == "refresh_claim_lost"
            try:
                if created and jid and not stale and not creation_cleanup_failed:
                    with maintenance.transaction(claim) as conn:
                        _cleanup_failed_refresh(jid, failure, actor=actor, native=native, may_be_running=not terminal)
                        if not terminal:
                            maintenance.disable_done(conn, claim)
            except sqlite3.Error as storage:
                # The durable reservation remains occupied. Suppression is still useful
                # when the store cannot accept a receipt; no native run/create is replayed.
                try:
                    maintenance.compensate_without_receipt(claim, lambda: _cleanup_failed_refresh(
                        jid, failure, actor=actor, native=native, may_be_running=not terminal))
                except Exception as cleanup:
                    failure.extra["cleanup"] = cleanup.to_dict() if isinstance(cleanup, SpacesError) else {"message": str(cleanup)}
                failure.extra["receipt_error"] = str(storage)
                terminal = False
            except SpacesError as cleanup:
                if failure.code in ("not_found", "archived"):
                    failure.extra["cleanup"] = cleanup.to_dict()
                else:
                    failure = _carry_run_reply(cleanup, native) if dispatched else cleanup
                terminal = False
            # Unknown creation without a returned ID cannot be retried. A structured refusal
            # without a saved job is the only creation failure that proves no work was admitted.
            if (created and not jid and failure.extra.get("reason") != "native_refused"
                    and failure.extra.get("unsent") is not True and failure.extra.get("created_job_removed") is not True):
                terminal = False
            if (created and not jid and isinstance(failure.extra.get("native"), dict)
                    and failure.extra["native"].get("job_saved") is True
                    and failure.extra.get("created_job_removed") is not True):
                terminal = False
            claim["failure"] = failure.to_dict()
            try:
                _update_refresh_claim(claim, native, phase="unresolved", settled=terminal)
            except SpacesError as claim_failure:
                failure.extra["claim_error"] = claim_failure.to_dict()
            raise failure
        result = {"kind": "cron", "cron_job_id": jid, "dispatch": native}
        outcome = maintenance.outcome(native, jid)
        try:
            with _after_run(native):
                with maintenance.transaction(claim) as conn:
                    maintenance.fence(conn, claim, work=True, archived=True)
                    if created and outcome in ("completed", "background"):
                        result["one_shot"] = _consume_one_shot(jid, native, actor=actor, background=outcome == "background")
                        maintenance.disable_done(conn, claim)
                    elif created and outcome == "unresolved":
                        try:
                            _mutate("pause", jid, reason=f"Living Spaces refresh by {actor} has an unconfirmed native outcome")
                            maintenance.disable_done(conn, claim)
                        except SpacesError as pause_failure:
                            raise SpacesError("blocked", f"Native refresh completion is unconfirmed, and its Hermes cron one-shot {jid} "
                                              f"could not be disabled ({pause_failure.message}). It may still be enabled and may run again at its scheduled slot. "
                                              "Unknown work was not removed. Use Upkeep Remove before retrying.",
                                              reason="one_shot_not_consumed", orphan_job_id=jid, native=native,
                                              refresh_state="unresolved", pause=pause_failure.to_dict()) from pause_failure
                if created and outcome in ("unresolved", "background"):
                    result["refresh_state"] = outcome
                    result["recovery"] = {"reason": "refresh_outcome_unknown",
                                          "message": "Native completion is unconfirmed. Use Upkeep Remove before retrying."}
                _update_refresh_claim(claim, native, phase="unresolved", settled=outcome in ("completed", "refused"))
        except SpacesError as failure:
            claim["failure"] = failure.to_dict()
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
        return {"job_id": jid, "consumed": "removed", **({"pause": pause_failure.to_dict()} if pause_failure else {})}
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
        raise SpacesError("blocked", "Could not pause this Space's upkeep, so it was not archived", reason=exc.message,
                          original=exc.to_dict()) from exc


def on_delete(conn, sid):
    """Remove future native work within the caller's Space deletion transaction."""
    _space(conn, sid)
    link = _link(conn, sid)
    claim = _refresh_claim(conn, sid)
    targets = {job["job_id"] for job in _owned_jobs(sid, link, _jobs()["jobs"], claim=claim)}
    if claim and claim["cron_job_id"]:
        targets.add(claim["cron_job_id"])
    for jid in sorted(targets):
        _mutate("remove", jid)
    if _owned_jobs(sid, link, _jobs()["jobs"], claim=claim):
        raise SpacesError("blocked", "This Space's upkeep removal could not be verified", reason="cron_unverified")
    _shim(sid).unlink(missing_ok=True)
    conn.execute("DELETE FROM upkeep_links WHERE space=?", (sid,))
    maintenance.retire_resources(conn, sid, all_resources=True)
    return link is not None
