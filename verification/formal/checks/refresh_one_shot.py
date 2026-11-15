"""Refresh now on real upkeep.refresh_now, every scenario in a bounded fault space, against a fake public cron.

The fake follows the reply shapes of Hermes tools/cronjob_tools.py _action_run (Hermes a317c07, lines 791-845):
a missing job is refused, a paused job replies executed=False with execution_skipped, an enabled job runs inline
(execution_success true or false) or starts in the background (executed=True, execution_mode=background, no
execution_success). A manual run is an extra fire: the once slot stays pending until the scheduler spends it.

Properties, for one Refresh now request:
  AtMostOnce            the request causes at most one execution, unless its error says the job may run again
  NoSuccessForSkipped   a returned result means the manual run executed (inline success or background start)
  NoFalseRefusal        an error after an execution that succeeded carries that run's reply, unless it warns the
                        job may run again (finding F1: such errors still say reason native_refused)
  NoLeftoverOneShot     after a returned result, no enabled one-shot of this request is still pending
"""
from __future__ import annotations

import hashlib
import itertools
import json
import re
import sqlite3
import sys

from harness import Violation, main, space

OUTCOMES = ("inline_ok", "inline_fail", "background")
FAULT_ACTIONS = ("resume", "pause", "remove", "list")
DURING_RUN = (None, "archive", "delete")
POST_RUN_DB = (False, True)
STARTS = ("fresh", "linked_enabled", "linked_paused")
MINUTES_BEFORE_RESUME = 1
KNOWN_F1_CASES_SHA256 = "65d451636e7abb4bfc5f29f390167b778254a31f997c94bafaa987e3f4f6e499"


class FakeCron:
    def __init__(self, scenario, core):
        self.s = scenario
        self.core = core
        self.jobs = {}
        self.count = {}
        self.executions = []
        self.next_id = 1
        self.armed_db_failure = False
        self.in_run = False
        self.refusals = []

    def current_cron_execution(self):
        return None

    def add(self, name, enabled, schedule="every 1h", repeat=None):
        jid = f"s{self.s['n']}-job{self.next_id}"
        self.next_id += 1
        self.jobs[jid] = {"job_id": jid, "name": name, "enabled": enabled, "schedule": schedule,
                          "repeat": repeat, "pending": True, "state": "scheduled" if enabled else "paused"}
        return jid

    def view(self, job):
        return {k: v for k, v in job.items() if k != "pending"}

    def due_by_resume(self, schedule):
        match = re.fullmatch(r"in (\d+)([mhd])", schedule or "")
        if not match:
            return True
        minutes = int(match.group(1)) * {"m": 1, "h": 60, "d": 1440}[match.group(2)]
        return minutes <= MINUTES_BEFORE_RESUME

    def fire(self, jid, origin):
        job = self.jobs[jid]
        self.executions.append((origin, jid, True))
        if job["repeat"] == 1:
            del self.jobs[jid]

    def tick(self):
        for jid, job in list(self.jobs.items()):
            if job["enabled"] and job["pending"] and job.get("due"):
                self.fire(jid, "scheduled")

    def fault(self, action):
        n = self.count[action] = self.count.get(action, 0) + 1
        refused = (action, n) in self.s["faults"]
        if refused:
            phase = "other"
            frame = sys._getframe(1)
            while frame is not None:
                if frame.f_code.co_name in ("_consume_one_shot", "on_delete", "pause_for_archive", "_run_now"):
                    phase = frame.f_code.co_name
                    break
                frame = frame.f_back
            self.refusals.append((action, n, phase))
        return refused

    def dispatch_tool(self, name, args):
        assert name == "cronjob_manage"
        action = args["action"]
        if action in FAULT_ACTIONS and self.fault(action):
            return json.dumps({"success": False, "error": f"injected {action} refusal #{self.count[action]}"})
        if action == "list":
            jobs = [self.view(j) for j in self.jobs.values()]
            return json.dumps({"success": True, "count": len(jobs), "jobs": jobs})
        if action == "create":
            jid = self.add(args["name"], not args.get("paused", False), args["schedule"], args.get("repeat"))
            self.jobs[jid]["due"] = self.due_by_resume(args["schedule"])
            return json.dumps({"success": True, "job_id": jid})
        jid = args["job_id"]
        job = self.jobs.get(jid)
        if job is None:
            return json.dumps({"success": False, "error": f"Job '{jid}' not found"})
        if action in ("pause", "resume"):
            job["enabled"] = action == "resume"
            job["state"] = "scheduled" if job["enabled"] else "paused"
            if action == "resume":
                self.tick()
            return json.dumps({"success": True, "job": self.view(job)})
        if action == "remove":
            del self.jobs[jid]
            return json.dumps({"success": True})
        if action == "run":
            if not job["enabled"]:
                return json.dumps({"success": True, "job": {**self.view(job), "executed": False,
                                                            "execution_skipped": "Job is paused"}})
            outcome = self.s["outcome"]
            self.executions.append(("manual", jid, outcome != "inline_fail"))
            try:
                if self.s["during_run"] == "archive":
                    self.core.set_status(self.s["sid"], "archived", actor="user")
                elif self.s["during_run"] == "delete":
                    self.core.delete_space(self.s["sid"], actor="user", confirm=self.s["sid"])
            except self.core.SpacesError:
                pass
            self.armed_db_failure = self.s["post_run_db"]
            job_view = self.view(self.jobs[jid]) if jid in self.jobs else {"job_id": jid}
            if outcome == "background":
                return json.dumps({"success": True, "job": {**job_view, "executed": True,
                                                            "execution_mode": "background", "delegation_id": "d1"}})
            return json.dumps({"success": True, "job": {**job_view, "executed": True,
                                                        "execution_success": outcome == "inline_ok",
                                                        **({} if outcome == "inline_ok" else {"execution_error": "upkeep failed"})}})
        raise AssertionError(action)


def scenarios():
    single = [frozenset()] + [frozenset({(a, n)}) for a in FAULT_ACTIONS for n in (1, 2, 3)]
    pairs = [frozenset({(a, n), (b, m)}) for (a, n), (b, m) in itertools.combinations(
        [(a, n) for a in FAULT_ACTIONS for n in (1, 2, 3)], 2)]
    for start, outcome, during, db_fail, faults in itertools.product(STARTS, OUTCOMES, DURING_RUN, POST_RUN_DB, single + pairs):
        if during and db_fail:
            continue
        yield {"start": start, "outcome": outcome, "during_run": during, "post_run_db": db_fail, "faults": faults}


def describe(s, cron, outcome, error):
    faults = ", ".join(f"{a} call #{n} refused" for a, n in sorted(s["faults"])) or "no cron refusals"
    told = "returned " + json.dumps({k: v for k, v in outcome.items() if k != "dispatch"}) if error is None \
        else f"raised {error.code} ({error.extra.get('reason')}): {error.message}"
    return (f"start={s['start']}, run outcome={s['outcome']}, during run={s['during_run'] or 'nothing'}, "
            f"post-run DB failure={s['post_run_db']}, {faults}. refresh_now {told}. Executions: {cron.executions}")


def check_one(core, s):
    from living_spaces_core import db, upkeep
    sid = space(core, f"Refresh {s['n']}")
    s["sid"] = sid
    cron = FakeCron(s, core)
    upkeep.configure_context(cron)
    if s["start"] != "fresh":
        jid = cron.add(f"living-spaces:{sid}", s["start"] == "linked_enabled")
        with db.write() as conn:
            conn.execute("INSERT INTO upkeep_links(space,cron_job_id,kind,created_at,created_by) VALUES(?,?,?,?,?)",
                         (sid, jid, "agent", db.now(), "agent"))
    real_write = db.write

    def write():
        if cron.armed_db_failure:
            cron.armed_db_failure = False
            raise sqlite3.OperationalError("injected database failure after the run")
        return real_write()

    db.write = write
    outcome = error = None
    try:
        outcome = upkeep.refresh_now(sid, {"handler": "agent", "prompt": "Update the list"}, actor="user")
    except core.SpacesError as exc:
        error = exc
    finally:
        db.write = real_write
    once = [j for j in cron.jobs.values() if j["name"] == f"living-spaces:{sid}:once"]
    for job in once:
        job["due"] = True
    cron.tick()
    created = s["start"] == "fresh"
    mine = [e for e in cron.executions if created or e[0] == "manual"]
    text = json.dumps(error.to_dict()) if error else ""
    warned = "may still be enabled" in text or "may run again" in text
    story = describe(s, cron, outcome or {}, error)
    violations = []
    if created and not warned and len(mine) > 1:
        violations.append(("AtMostOnce", story))
    if error is None:
        if not any(e[0] == "manual" for e in mine) or s["outcome"] == "inline_fail":
            violations.append(("NoSuccessForSkipped", story))
        if any(j["enabled"] and j["pending"] for j in once):
            violations.append(("NoLeftoverOneShot", story))
    elif not warned and any(ok for _, _, ok in mine):
        native = error.extra.get("native")
        ran = isinstance(native, dict) and isinstance(native.get("job"), dict) and native["job"].get("executed") is True
        if not ran:
            violations.append(("NoFalseRefusal", story))
        elif error.extra.get("reason") == "native_refused":
            injected_post_run_refusal = any(
                phase == "_run_now"
                and error.message == f"Hermes cron {action} refused: injected {action} refusal #{n}"
                for action, n, phase in cron.refusals)
            if injected_post_run_refusal:
                violations.append(("NoFalseRefusal", story, "F1"))
            else:
                violations.append(("NoFalseRefusal", story))
    tag = "ok" if error is None else error.extra.get("reason") or error.code
    return tag, violations


KNOWN = {"F1": "a successful run is reported as refused when a cron call after the run is refused"}


def check(core, home):
    results, findings, unknown, finding_cases = {}, {}, [], []
    for n, s in enumerate(scenarios()):
        s["n"] = n
        tag, violations = check_one(core, s)
        results[tag] = results.get(tag, 0) + 1
        for v in violations:
            if len(v) == 3:
                findings.setdefault(v[2], {"count": 0, "example": v[1]})["count"] += 1
                finding_cases.append([s["start"], s["outcome"], s["during_run"], s["post_run_db"], sorted(s["faults"])])
            else:
                unknown.append(v)
    if unknown:
        first = {}
        for prop, story in unknown:
            first.setdefault(prop, story)
        raise Violation(f"{len(unknown)} scenario(s) broke a property. " +
                        " | ".join(f"{prop}: {story}" for prop, story in first.items()))
    finding_hash = hashlib.sha256(json.dumps(finding_cases, separators=(",", ":")).encode()).hexdigest()
    if finding_hash != KNOWN_F1_CASES_SHA256:
        raise Violation(f"KnownFindingDrift: F1 scenario set changed: {len(finding_cases)} cases, sha256={finding_hash}. "
                        "Review the source and F1 attribution before updating its synced baseline.")
    return {"scenarios": sum(results.values()), "outcomes": results, "f1_scenarios_sha256": finding_hash,
            "known_findings": {k: {"what": KNOWN[k], **v} for k, v in findings.items()},
            "known_findings_gone": sorted(set(KNOWN) - set(findings))}


if __name__ == "__main__":
    main(check)
