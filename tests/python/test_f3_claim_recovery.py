"""F3 recovery contracts on the real core with synthetic public cron boundaries.

Authored without execution. Process fixtures require F3_PROCESS_TEST_TMPDIR on
Expansion. Native effects are produced by the existing completion helpers, not
by inserting claim rows or inventing successful dispatch results.
"""
from contextlib import ExitStack
import copy
import json
import os
from pathlib import Path
import signal
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

from tests.python.review_customization_support import CustomizationFixture
from tests.python.test_agent_refresh_dispatch import RunOutcome
from tests.python.test_f1_f4_regressions import CompletingCronContext
from tests.python import test_f3_process_claims as process_support


def expansion_base():
    base = Path(os.environ["F3_PROCESS_TEST_TMPDIR"]).resolve()
    if not base.is_relative_to(Path("/Volumes/Expansion")):
        raise ValueError("F3_PROCESS_TEST_TMPDIR must be an owned directory on Expansion")
    base.mkdir(parents=True, exist_ok=True)
    return base


def observe(case, **values):
    message = json.dumps({"case": case.id(), "boundary": "synthetic public cron",
                          **values}, sort_keys=True)
    print(message, flush=True)
    return message


class CallbackWindowExit(BaseException):
    """Interruption after the real acceptance callback, before verification."""


class F3ClaimRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        base = expansion_base()
        self.stack.enter_context(patch.object(tempfile, "tempdir", str(base)))
        self.fx = CustomizationFixture(self.stack)
        self.ctx = CompletingCronContext(self.fx)
        self.fx.ctx = self.ctx
        self.fx.upkeep.configure_context(self.ctx)

    def refresh(self, sid):
        try:
            return {"result": self.fx.runs.start_refresh(sid, trigger="manual", actor="user")}
        except self.fx.core.SpacesError as exc:
            return {"error": exc.to_dict()}

    def claim(self, sid):
        with self.fx.db.read() as conn:
            row = conn.execute("SELECT * FROM refresh_claims WHERE space=?", (sid,)).fetchone()
            return dict(row) if row else None

    def foreign(self, *, active=False):
        sid = self.fx.make()
        jid = self.fx.schedule(sid)["link"]["cron_job_id"]
        if active:
            self.ctx.outcome = RunOutcome.BACKGROUND
            owner = self.refresh(sid)
            self.assertNotIn("error", owner, owner)
        return {"sid": sid, "jid": jid, "job": self.fx.cron.get_job(jid),
                "bundle": self.fx.projects.bundle(sid), "claim": self.claim(sid)}

    def assert_foreign(self, before, message):
        self.assertEqual(self.fx.cron.get_job(before["jid"]), before["job"], message)
        self.assertEqual(self.fx.projects.bundle(before["sid"]), before["bundle"], message)
        self.assertEqual(self.claim(before["sid"]), before["claim"], message)

    def assert_recovery(self, result, message):
        self.assertEqual(result.get("recovery", {}).get("reason"),
                         "refresh_outcome_unknown", message)
        self.assertIn("Upkeep Remove", json.dumps(result.get("recovery", {})), message)

    def replacement(self, *, old_already_absent):
        fx = self.fx
        sid = fx.make()
        old = fx.schedule(sid)["link"]["cron_job_id"]
        self.ctx.outcome = RunOutcome.BACKGROUND
        owner = self.refresh(sid)
        foreign = self.foreign(active=True)
        old_claim = self.claim(sid)
        removal = None
        if old_already_absent:
            removal = json.loads(self.ctx.dispatch_tool(
                "cronjob_manage", {"action": "remove", "job_id": old}))
        replacement = fx.schedule(sid, cadence="0 */2 * * *")
        new = replacement["link"]["cron_job_id"]
        retired = self.claim(sid)
        self.ctx.outcome = RunOutcome.INLINE
        later = self.refresh(sid)
        foreign_follower = self.refresh(foreign["sid"])
        state = fx.upkeep.get_upkeep(sid)
        marker = (json.loads(fx.core.read_file(sid, "refresh-effect.json")["text"])
                  if any(f["path"] == "refresh-effect.json" for f in fx.core.list_files(sid)) else None)
        message = observe(self, old_already_absent=old_already_absent, removal=removal,
                          owner=owner, old_claim=old_claim, replacement=replacement,
                          claim_after_replacement=retired, later=later, state=state,
                          marker=marker, foreign_before=foreign, foreign_follower=foreign_follower,
                          executions=fx.cron.executions, effects=self.ctx.effects)
        self.assertNotIn("error", owner, message)
        self.assertEqual(owner["result"]["dispatch"], self.ctx.run_replies[0], message)
        self.assertEqual(old_claim["cron_job_id"], old, message)
        self.assertNotEqual(new, old, message)
        self.assertIsNone(fx.cron.get_job(old), message)
        self.assertIsNone(retired, message)
        self.assertNotIn("error", later, message)
        self.assertFalse(later.get("result", {}).get("joined", False), message)
        self.assertEqual(later.get("result", {}).get("cron_job_id"), new, message)
        self.assertEqual(state["link"]["cron_job_id"], new, message)
        self.assertIsNotNone(fx.cron.get_job(new), message)
        self.assertEqual(marker, {"space": sid, "job_id": new, "execution_count": 1}, message)
        self.assertEqual([e["job_id"] for e in fx.cron.executions],
                         [old, foreign["jid"], new], message)
        self.assertTrue(foreign_follower.get("result", {}).get("joined"), message)
        self.assertEqual(foreign_follower["result"]["cron_job_id"], foreign["jid"], message)
        self.assert_foreign(foreign, message)

    def test_reschedule_retires_only_the_verified_removed_background_claim(self):
        self.replacement(old_already_absent=False)

    def test_reschedule_retires_the_confirmed_absent_old_claim(self):
        self.replacement(old_already_absent=True)

    def test_refused_old_removal_retains_link_and_claim_control(self):
        fx = self.fx
        sid = fx.make()
        link = fx.schedule(sid)["link"]
        old = link["cron_job_id"]
        self.ctx.outcome = RunOutcome.BACKGROUND
        owner = self.refresh(sid)
        before = self.claim(sid)
        foreign = self.foreign(active=True)
        dispatch = self.ctx.dispatch_tool
        refusals = []

        def refuse_old(name, args):
            if args["action"] == "remove" and args.get("job_id") == old:
                reply = {"success": False, "error": "Injected old-job removal refusal"}
                refusals.append(reply)
                return json.dumps(reply)
            return dispatch(name, args)

        with patch.object(self.ctx, "dispatch_tool", side_effect=refuse_old):
            try:
                replacement = {"result": fx.schedule(sid, cadence="0 */2 * * *")}
            except fx.core.SpacesError as exc:
                replacement = {"error": exc.to_dict()}
        follower = self.refresh(sid)
        state = fx.upkeep.get_upkeep(sid)
        after = self.claim(sid)
        message = observe(self, owner=owner, before=before, after=after, replacement=replacement,
                          refusals=refusals, follower=follower, state=state,
                          jobs=fx.cron.list_jobs(include_disabled=True), executions=fx.cron.executions)
        self.assertNotIn("error", owner, message)
        self.assertEqual(len(refusals), 1, message)
        self.assertEqual(replacement.get("error", {}).get("reason"), "native_refused", message)
        self.assertEqual(state["link"], link, message)
        self.assertEqual(after, before, message)
        self.assertTrue(follower.get("result", {}).get("joined"), message)
        self.assertEqual(follower["result"]["cron_job_id"], old, message)
        self.assertEqual({j["id"] for j in fx.cron.list_jobs(include_disabled=True)},
                         {old, foreign["jid"]}, message)
        self.assertEqual(len(fx.cron.executions), 2, message)
        self.assertEqual(self.ctx.effects, [], message)
        self.assert_foreign(foreign, message)

    def test_unknown_old_removal_never_releases_claim_control(self):
        fx = self.fx
        sid = fx.make()
        link = fx.schedule(sid)["link"]
        old = link["cron_job_id"]
        self.ctx.outcome = RunOutcome.BACKGROUND
        owner = self.refresh(sid)
        before = self.claim(sid)
        foreign = self.foreign(active=True)
        dispatch = self.ctx.dispatch_tool
        fault = {"removed": False, "refusals": []}

        def unknown_removal(name, args):
            if args["action"] == "list" and fault["removed"] and not fault["refusals"]:
                reply = {"success": False, "error": "Injected removal verification outage"}
                fault["refusals"].append(reply)
                return json.dumps(reply)
            reply = dispatch(name, args)
            if args["action"] == "remove" and args.get("job_id") == old:
                fault["removed"] = True
            return reply

        with patch.object(self.ctx, "dispatch_tool", side_effect=unknown_removal):
            try:
                replacement = {"result": fx.schedule(sid, cadence="0 */2 * * *")}
            except fx.core.SpacesError as exc:
                replacement = {"error": exc.to_dict()}
        after = self.claim(sid)
        follower = self.refresh(sid)
        state = fx.upkeep.get_upkeep(sid)
        message = observe(self, owner=owner, before=before, after=after, replacement=replacement,
                          fault=fault, follower=follower, state=state,
                          jobs=fx.cron.list_jobs(include_disabled=True), executions=fx.cron.executions)
        self.assertNotIn("error", owner, message)
        self.assertTrue(fault["removed"], message)
        self.assertEqual(len(fault["refusals"]), 1, message)
        self.assertEqual(replacement.get("error", {}).get("reason"),
                         "cron_remove_outcome_unknown", message)
        self.assertEqual(state["link"], link, message)
        self.assertEqual(after, before, message)
        self.assertTrue(follower.get("result", {}).get("joined"), message)
        self.assertEqual(follower["result"]["cron_job_id"], old, message)
        self.assert_recovery(follower["result"], message)
        self.assertEqual(len(fx.cron.executions), 2, message)
        self.assertEqual(self.ctx.effects, [], message)
        self.assert_foreign(foreign, message)

    def test_callback_window_exit_preserves_background_settlement(self):
        fx = self.fx
        sid = fx.make()
        jid = fx.schedule(sid)["link"]["cron_job_id"]
        previous = self.refresh(sid)
        self.assertNotIn("error", previous, previous)
        baseline = fx.cron.get_job(jid)["last_run_at"]
        self.ctx.outcome = RunOutcome.BACKGROUND
        reply_start = len(self.ctx.run_replies)
        dispatch = self.ctx.dispatch_tool
        interrupted = []

        def exit_at_post_reply_list(name, args):
            if args["action"] == "list" and len(self.ctx.run_replies) > reply_start and not interrupted:
                interrupted.append(copy.deepcopy(args))
                raise CallbackWindowExit("Controlled exit after acceptance callback")
            return dispatch(name, args)

        with patch.object(self.ctx, "dispatch_tool", side_effect=exit_at_post_reply_list):
            with self.assertRaises(CallbackWindowExit):
                fx.runs.start_refresh(sid, trigger="manual", actor="user")
        accepted = copy.deepcopy(self.ctx.run_replies[-1])
        durable = self.claim(sid)
        first_follower = self.refresh(sid)
        fx.upkeep.upkeep_action(sid, "pause", actor="user")
        real_clock = time.time
        with patch("time.time", side_effect=lambda: real_clock() + 3600):
            paused_follower = self.refresh(sid)
        held = copy.deepcopy(fx.cron.executions)
        held_effects = copy.deepcopy(self.ctx.effects)
        held_claim = self.claim(sid)
        self.ctx.finish_background(jid)
        completed_stamp = fx.cron.get_job(jid)["last_run_at"]
        marker = json.loads(fx.core.read_file(sid, "refresh-effect.json")["text"])
        fx.upkeep.upkeep_action(sid, "resume", actor="user")
        self.ctx.outcome = RunOutcome.INLINE
        later = self.refresh(sid)
        message = observe(self, precondition="Controlled BaseException at first post-callback native list",
                          previous=previous, baseline=baseline, accepted=accepted, interrupted=interrupted,
                          durable=durable, held_claim=held_claim, first_follower=first_follower,
                          paused_follower=paused_follower, held=held, held_effects=held_effects,
                          completed_stamp=completed_stamp, completion_marker=marker, later=later,
                          executions=fx.cron.executions, effects=self.ctx.effects)
        self.assertEqual(len(interrupted), 1, message)
        self.assertEqual(accepted["job"]["execution_mode"], "background", message)
        self.assertEqual((accepted["job"]["job_id"], accepted["job"]["last_run_at"]),
                         (jid, baseline), message)
        self.assertNotIn("execution_success", accepted["job"], message)
        self.assertIsNotNone(durable, message)
        self.assertEqual(json.loads(durable["native"]), accepted, message)
        self.assertEqual(json.loads(durable["baseline_completion"]), baseline, message)
        for follower in (first_follower, paused_follower):
            self.assertTrue(follower.get("result", {}).get("joined"), message)
            self.assertEqual(follower["result"]["cron_job_id"], jid, message)
            self.assertEqual(follower["result"]["dispatch"], accepted, message)
        self.assertEqual([e["status"] for e in held], ["completed", "running"], message)
        self.assertEqual(len(held_effects), 1, message)
        self.assertEqual(held_claim, durable, message)
        self.assertNotEqual(completed_stamp, baseline, message)
        self.assertEqual(marker, {"space": sid, "job_id": jid, "execution_count": 2}, message)
        self.assertNotIn("error", later, message)
        self.assertFalse(later.get("result", {}).get("joined", False), message)
        self.assertEqual(len(fx.cron.executions), 3, message)
        self.assertEqual([e["execution_count"] for e in self.ctx.effects], [1, 2, 3], message)
        self.assertEqual(durable["phase"], "background", message)

    def unresolved_owner(self, outcome):
        fx = self.fx
        sid = fx.make()
        foreign = self.foreign()
        self.ctx.outcome = outcome
        owner = self.refresh(sid)
        owner_result = owner.get("result", {})
        jid = owner_result.get("cron_job_id")
        owner_job = fx.cron.get_job(jid)
        follower = self.refresh(sid)
        job = fx.cron.get_job(jid)
        claim = self.claim(sid)
        raw = copy.deepcopy(self.ctx.run_replies[-1])
        calls = copy.deepcopy(self.ctx.calls)
        message = observe(self, outcome=outcome.value, owner=owner, follower=follower,
                          raw=raw, owner_job=owner_job, job=job, claim=claim, calls=calls,
                          jobs=fx.cron.list_jobs(include_disabled=True),
                          executions=fx.cron.executions, effects=self.ctx.effects)
        self.assertNotIn("error", owner, message)
        self.assertNotIn("error", follower, message)
        self.assertEqual(owner_result.get("dispatch"), raw, message)
        self.assertNotIn("execution_success", raw.get("job", {}), message)
        self.assertEqual(follower.get("result", {}).get("dispatch"), raw, message)
        self.assertTrue(follower.get("result", {}).get("joined"), message)
        self.assertEqual(follower["result"]["cron_job_id"], jid, message)
        self.assertEqual(claim["phase"], "unresolved", message)
        self.assertEqual(len(self.ctx.run_attempts), 1, message)
        self.assertEqual(len([c for c in fx.cron.calls if c[0] == "create"]), 2, message)
        self.assertEqual((fx.cron.executions, self.ctx.effects), ([], []), message)
        self.assertFalse(any(args["action"] in ("remove", "cancel") and args.get("job_id") == jid
                             for _, args in calls), message)
        self.assert_foreign(foreign, message)
        self.assertEqual(owner_result.get("refresh_state"), "unresolved", message)
        self.assert_recovery(owner_result, message)
        self.assert_recovery(follower["result"], message)
        self.assertIs(owner_job["enabled"], False, message)
        self.assertIs(job["enabled"], False, message)

    def test_forwarded_owner_exposes_recovery_and_disables_only_its_one_shot(self):
        self.unresolved_owner(RunOutcome.FORWARDED)

    def test_metadata_free_owner_exposes_recovery_without_claiming_completion(self):
        self.unresolved_owner(RunOutcome.UNSPECIFIED)

    def test_linked_unresolved_remove_preserves_foreign_work_control(self):
        fx = self.fx
        sid = fx.make()
        jid = fx.schedule(sid)["link"]["cron_job_id"]
        foreign = self.foreign(active=True)
        self.ctx.outcome = RunOutcome.FORWARDED
        owner = self.refresh(sid)
        follower = self.refresh(sid)
        raw = copy.deepcopy(self.ctx.run_replies[-1])
        removed = fx.upkeep.upkeep_action(sid, "remove", actor="user")
        cleared = self.claim(sid)
        self.ctx.outcome = RunOutcome.INLINE
        later = self.refresh(sid)
        marker = json.loads(fx.core.read_file(sid, "refresh-effect.json")["text"])
        message = observe(self, owner=owner, follower=follower, raw=raw, removed=removed,
                          cleared=cleared, later=later, marker=marker,
                          jobs=fx.cron.list_jobs(include_disabled=True), executions=fx.cron.executions)
        self.assertNotIn("error", owner, message)
        self.assertEqual(owner["result"]["dispatch"], raw, message)
        self.assertTrue(follower.get("result", {}).get("joined"), message)
        self.assertEqual(follower["result"]["cron_job_id"], jid, message)
        self.assert_recovery(follower["result"], message)
        self.assertIsNone(cleared, message)
        self.assertIsNone(removed["link"], message)
        self.assertIsNone(fx.cron.get_job(jid), message)
        self.assertNotIn("error", later, message)
        self.assertFalse(later.get("result", {}).get("joined", False), message)
        self.assertNotEqual(later["result"]["cron_job_id"], jid, message)
        self.assertEqual(marker["job_id"], later["result"]["cron_job_id"], message)
        self.assertEqual(marker["execution_count"], 1, message)
        self.assert_foreign(foreign, message)

    def test_linked_background_stamp_settles_but_pause_and_time_do_not_control(self):
        fx = self.fx
        sid = fx.make()
        link = fx.schedule(sid)["link"]
        jid = link["cron_job_id"]
        self.ctx.outcome = RunOutcome.BACKGROUND
        owner = self.refresh(sid)
        raw = copy.deepcopy(self.ctx.run_replies[-1])
        initial = self.claim(sid)
        fx.upkeep.upkeep_action(sid, "pause", actor="user")
        real_clock = time.time
        with patch("time.time", side_effect=lambda: real_clock() + 3600):
            follower = self.refresh(sid)
        paused = fx.cron.get_job(jid)
        held = self.claim(sid)
        active = copy.deepcopy(fx.cron.executions)
        self.ctx.finish_background(jid)
        completed = fx.cron.get_job(jid)
        marker = json.loads(fx.core.read_file(sid, "refresh-effect.json")["text"])
        self.ctx.outcome = RunOutcome.INLINE
        refused_while_paused = self.refresh(sid)
        still_paused = fx.cron.get_job(jid)
        effects_before_resume = copy.deepcopy(self.ctx.effects)
        fx.upkeep.upkeep_action(sid, "resume", actor="user")
        later = self.refresh(sid)
        message = observe(self, owner=owner, raw=raw, initial=initial, paused=paused,
                          follower=follower, held=held, active=active, completed=completed,
                          marker=marker, refused_while_paused=refused_while_paused,
                          still_paused=still_paused, effects_before_resume=effects_before_resume,
                          later=later, executions=fx.cron.executions,
                          effects=self.ctx.effects, state=fx.upkeep.get_upkeep(sid))
        self.assertNotIn("error", owner, message)
        self.assertIsNone(raw["job"]["last_run_at"], message)
        self.assertEqual(initial["phase"], "background", message)
        self.assertEqual(json.loads(initial["baseline_completion"]), raw["job"]["last_run_at"], message)
        self.assertTrue(follower.get("result", {}).get("joined"), message)
        self.assertEqual(follower["result"]["dispatch"], raw, message)
        self.assertEqual(held, initial, message)
        self.assertIs(paused["enabled"], False, message)
        self.assertEqual([e["status"] for e in active], ["running"], message)
        self.assertNotEqual(completed["last_run_at"], raw["job"]["last_run_at"], message)
        self.assertEqual(marker, {"space": sid, "job_id": jid, "execution_count": 1}, message)
        self.assertEqual(refused_while_paused.get("error", {}).get("reason"), "native_refused", message)
        self.assertIs(still_paused["enabled"], False, message)
        self.assertEqual(len(effects_before_resume), 1, message)
        self.assertNotIn("error", later, message)
        self.assertFalse(later.get("result", {}).get("joined", False), message)
        self.assertEqual(later["result"]["cron_job_id"], jid, message)
        self.assertEqual([e["status"] for e in fx.cron.executions], ["completed", "completed"], message)
        self.assertEqual([e["execution_count"] for e in self.ctx.effects], [1, 2], message)
        self.assertEqual(fx.upkeep.get_upkeep(sid)["link"], link, message)
        self.assertIsNone(self.claim(sid), message)

    def test_archive_keeps_live_claim_and_never_implicitly_resumes_control(self):
        fx = self.fx
        sid = fx.make()
        link = fx.schedule(sid)["link"]
        jid = link["cron_job_id"]
        foreign = self.foreign(active=True)
        self.ctx.outcome = RunOutcome.BACKGROUND
        owner = self.refresh(sid)
        before = self.claim(sid)
        archived = fx.projects.set_status(sid, "archived", actor="user")
        archived_claim = self.claim(sid)
        blocked = self.refresh(sid)
        fx.projects.set_status(sid, "active", actor="user")
        follower = self.refresh(sid)
        paused = fx.cron.get_job(jid)
        calls = copy.deepcopy(self.ctx.calls)
        message = observe(self, owner=owner, before=before, archived=archived,
                          archived_claim=archived_claim, blocked=blocked, follower=follower,
                          paused=paused, calls=calls, executions=fx.cron.executions,
                          effects=self.ctx.effects)
        self.assertNotIn("error", owner, message)
        self.assertEqual(archived["status"], "archived", message)
        self.assertEqual(archived_claim, before, message)
        self.assertEqual(blocked.get("error", {}).get("code"), "archived", message)
        self.assertTrue(follower.get("result", {}).get("joined"), message)
        self.assertEqual(follower["result"]["cron_job_id"], jid, message)
        self.assertEqual(self.claim(sid), before, message)
        self.assertIs(paused["enabled"], False, message)
        self.assertEqual(fx.upkeep.get_upkeep(sid)["link"], link, message)
        self.assertEqual([e["status"] for e in fx.cron.executions], ["running", "running"], message)
        self.assertEqual(self.ctx.effects, [], message)
        self.assert_foreign(foreign, message)


class F3InterruptedPendingTests(unittest.TestCase):
    def setUp(self):
        expansion_base()
        self.processes = process_support.F3ProcessClaimsTests("runTest")
        self.addCleanup(self.processes.doCleanups)
        self.processes.setUp()

    def claim(self):
        root = self.processes.root
        sid = (root / "space").read_text()
        with sqlite3.connect((root / "spaces.db").as_uri() + "?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM refresh_claims WHERE space=?", (sid,)).fetchone()
            return dict(row) if row else None

    def blocked_owner(self):
        h = self.processes
        owner = h.spawn("inline-owner")
        active = process_support.wait_for(lambda: process_support.snapshot(h.root)["executions"])
        claim = self.claim()
        return owner, active, claim

    def kill_owned_owner(self):
        owner, active, claim = self.blocked_owner()
        os.kill(owner.pid, signal.SIGKILL)
        owner.wait(timeout=5)
        return owner, active, claim

    def test_killed_pending_owner_gets_informational_recovery_after_one_hour(self):
        h = self.processes
        owner, active, before = self.kill_owned_owner()
        later = h.call("stale-follower", mode="background", offset=3600)
        state = process_support.snapshot(h.root)
        after = self.claim()
        result = later.get("result", {})
        message = observe(self, precondition="Owned inline process killed at file-backed native execution barrier",
                          owner_pid=owner.pid, owner_exit=owner.returncode, active=active,
                          before=before, later=later, after=after, native=state)
        self.assertEqual(owner.returncode, -signal.SIGKILL, message)
        self.assertNotIn("error", later, message)
        self.assertNotEqual(later["pid"], owner.pid, message)
        self.assertGreaterEqual(later["observed_wall_time"] - before["created_at"], 3600, message)
        self.assertTrue(result.get("joined"), message)
        self.assertEqual(result.get("cron_job_id"), before["cron_job_id"], message)
        self.assertEqual(result.get("refresh_state"), "pending", message)
        self.assertIsNone(result.get("dispatch"), message)
        self.assertEqual(after, before, message)
        self.assertEqual([e["status"] for e in state["executions"]], ["running"], message)
        self.assertEqual(len([c for c in state["calls"] if c[0] == "run"]), 1, message)
        self.assertEqual(state["effects"], [], message)
        self.assertFalse(any(c[0] in ("cancel", "remove") for c in state["calls"]), message)
        self.assertEqual(result.get("recovery", {}).get("reason"), "refresh_outcome_unknown", message)
        self.assertIn("Upkeep Remove", json.dumps(result.get("recovery", {})), message)

    def test_fresh_pending_follower_joins_without_stale_recovery_control(self):
        h = self.processes
        owner, active, before = self.blocked_owner()
        try:
            follower = h.call("fresh-follower", mode="background")
            held = self.claim()
            state = process_support.snapshot(h.root)
            owner_alive = owner.poll() is None
        finally:
            (h.root / "inline-release").touch()
        completed = h.joined(owner, "inline-owner")
        marker = h.call("inspect", "inspect")
        message = observe(self, active=active, before=before, follower=follower, held=held,
                          native_while_pending=state, owner_alive=owner_alive,
                          completed=completed, markers=marker)
        self.assertTrue(owner_alive, message)
        self.assertNotIn("error", follower, message)
        result = follower["result"]
        self.assertTrue(result.get("joined"), message)
        self.assertEqual(result.get("cron_job_id"), before["cron_job_id"], message)
        self.assertEqual(result.get("refresh_state"), "pending", message)
        self.assertNotIn("recovery", result, message)
        self.assertLess(follower["observed_wall_time"] - before["created_at"], 120, message)
        self.assertEqual(held, before, message)
        self.assertEqual([e["status"] for e in state["executions"]], ["running"], message)
        self.assertEqual(state["effects"], [], message)
        self.assertEqual(len([c for c in state["calls"] if c[0] == "run"]), 1, message)
        self.assertNotIn("error", completed, message)
        self.assertEqual(len(marker["result"]["markers"]), 1, message)
        self.assertEqual(marker["result"]["markers"][0]["job_id"], before["cron_job_id"], message)

    def test_remove_recovers_killed_pending_only_and_preserves_foreign_execution_control(self):
        h = self.processes
        owner, active, before = self.kill_owned_owner()
        foreign_ctx = process_support.SharedCronContext(h.root, None, "foreign", "background")
        foreign_created = json.loads(foreign_ctx.dispatch_tool("cronjob_manage", {
            "action": "create", "name": "foreign-daily-brief", "prompt": "Foreign work",
            "schedule": "0 * * * *", "deliver": "local", "no_agent": False, "paused": False}))
        foreign_id = foreign_created["job_id"]
        foreign_reply = json.loads(foreign_ctx.dispatch_tool(
            "cronjob_manage", {"action": "run", "job_id": foreign_id}))
        native_before = process_support.snapshot(h.root)
        removed = h.call("remove", "remove")
        cleared = self.claim()
        absent = process_support.snapshot(h.root)
        (h.root / "inline-release").touch()
        later = h.call("later")
        after = process_support.snapshot(h.root)
        markers = h.call("inspect", "inspect")
        message = observe(self, owner_pid=owner.pid, owner_exit=owner.returncode,
                          active=active, before=before, foreign_reply=foreign_reply,
                          native_before=native_before, removed=removed, cleared=cleared,
                          absent=absent, later=later, after=after, markers=markers)
        self.assertEqual(owner.returncode, -signal.SIGKILL, message)
        self.assertNotIn("error", removed, message)
        self.assertIsNone(cleared, message)
        self.assertNotIn(before["cron_job_id"], absent["jobs"], message)
        self.assertEqual(absent["jobs"], {foreign_id: native_before["jobs"][foreign_id]}, message)
        self.assertEqual([e["status"] for e in absent["executions"]
                          if e["job_id"] == before["cron_job_id"]], ["cancelled"], message)
        self.assertEqual([e for e in absent["executions"] if e["job_id"] == foreign_id],
                         [e for e in native_before["executions"] if e["job_id"] == foreign_id], message)
        self.assertEqual(absent["effects"], [], message)
        self.assertNotIn("error", later, message)
        new_id = later["result"]["cron_job_id"]
        self.assertNotEqual(new_id, before["cron_job_id"], message)
        self.assertFalse(later["result"].get("joined", False), message)
        self.assertEqual([e["job_id"] for e in after["effects"]], [new_id], message)
        self.assertEqual([m["job_id"] for m in markers["result"]["markers"]], [new_id], message)
        self.assertEqual(after["jobs"][foreign_id], native_before["jobs"][foreign_id], message)
        self.assertEqual([e["status"] for e in after["executions"] if e["job_id"] == foreign_id],
                         ["running"], message)


if __name__ == "__main__":
    unittest.main()
