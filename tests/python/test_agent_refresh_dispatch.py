from contextlib import ExitStack, contextmanager
import copy
from datetime import datetime, timedelta, timezone
from enum import Enum
import json
import re
import sqlite3
import unittest
from unittest.mock import patch

from tests.python.review_customization_support import CustomizationFixture, PACKAGE, SyntheticContext


class RunOutcome(Enum):
    INLINE = "inline"
    SKIPPED = "synthetic_skip"
    NOT_EXECUTED = "synthetic_not_executed"
    SKIP_ONLY = "synthetic_skip_without_execution_flags"
    FAILED = "synthetic_inline_failure"
    FORWARDED = "forwarded"
    BACKGROUND = "background"
    UNSPECIFIED = "no_execution_metadata"


class PausedRefusingContext(SyntheticContext):
    def __init__(self, fx):
        super().__init__(fx.cron)
        self.fx = fx
        self.outcome = RunOutcome.INLINE
        self.deny_activation = False
        self.activation_refusals = []
        self.run_attempts = []
        self.run_replies = []
        self.effects = []
        self.run_duration = timedelta(0)
        self.tick_after_run = False
        self.fail_write_after_run = False

    def dispatch_tool(self, name, args):
        assert name == "cronjob_manage", name
        action = args["action"]
        if self.deny_activation and (action == "resume" or
                                     (action == "create" and not args.get("paused", False))):
            self.calls.append((name, copy.deepcopy(args)))
            reply = {"success": False, "error": "Synthetic activation policy refusal"}
            self.activation_refusals.append(copy.deepcopy(reply))
            return json.dumps(reply)
        if action == "create":
            return self.create_with_slot(name, args)
        if action != "run":
            return super().dispatch_tool(name, args)

        self.calls.append((name, copy.deepcopy(args)))
        jid = args["job_id"]
        job = self.cron.get_job(jid)
        self.run_attempts.append({"job_id": jid, "job": copy.deepcopy(job)})
        if job is None:
            reply = {"success": False, "error": "Job not found"}
        elif job["enabled"] is not True:
            reply = {"success": True, "job": dict(self.format_job(job), executed=False,
                     execution_success=False,
                     execution_skipped="Job is paused/disabled; resume it before running.")}
        elif self.outcome in (RunOutcome.SKIPPED, RunOutcome.NOT_EXECUTED, RunOutcome.SKIP_ONLY):
            diagnostics = {
                RunOutcome.SKIPPED: {"executed": False, "execution_success": False,
                                     "execution_skipped": "Synthetic competing claim"},
                RunOutcome.NOT_EXECUTED: {"executed": False},
                RunOutcome.SKIP_ONLY: {"execution_skipped": "Synthetic competing claim"},
            }
            reply = {"success": True, "job": dict(self.format_job(job), **diagnostics[self.outcome])}
        elif self.outcome is RunOutcome.FORWARDED:
            reply = {"success": True, "forwarded_to_gateway": True,
                     "note": "Synthetic gateway accepted handoff", "request_id": jid + "-handoff"}
        elif self.outcome is RunOutcome.BACKGROUND:
            execution = self.cron.execution(jid, status="running")
            reply = {"success": True, "job": dict(self.format_job(job), executed=True,
                     execution_mode="background", delegation_id=execution["id"])}
        elif self.outcome is RunOutcome.UNSPECIFIED:
            reply = {"success": True, "job": self.format_job(job), "note": "No execution outcome supplied"}
        elif self.outcome is RunOutcome.FAILED:
            execution = self.cron.execution(jid, status="failed")
            execution["error"] = "Synthetic model unavailable"
            reply = {"success": True, "job": dict(self.format_job(job), executed=True,
                     execution_mode="inline", execution_success=execution["status"] == "completed",
                     execution_error=execution["error"])}
        else:
            assert self.outcome is RunOutcome.INLINE, self.outcome
            execution = self.execute(jid, origin="manual")
            # Hermes treats a manual run as an extra fire (cron/extra_fire.py): mark_job_run stamps
            # the outcome but leaves repeat.completed, enabled, state and the pending next_run_at
            # slot untouched, so a one-shot stays due for the scheduler.
            self.cron.jobs[jid].update(last_run_at=datetime.now(timezone.utc).isoformat(), last_status="ok")
            ended = datetime.now(timezone.utc) + self.run_duration
            self.settle_extra_fire(jid, ended)
            reply = {"success": True, "job": dict(self.format_job(self.cron.get_job(jid)), executed=True,
                     execution_mode="inline", execution_success=execution["status"] == "completed",
                     execution_id=execution["id"])}
            if self.tick_after_run:
                # A scheduler tick lands after mark_job_run cleared the claim and before the caller
                # sees the reply, which is the window the plugin cannot close after the fact.
                self.ticks_during_run = self.scheduler_tick(ended)
        self.run_replies.append(copy.deepcopy(reply))
        return json.dumps(reply)

    def settle_extra_fire(self, jid, ended):
        # cron/extra_fire.settle: a once slot that passed while the manual run was in flight becomes
        # due at the run's end instead of being kept in the future.
        job = self.cron.jobs[jid]
        slot = job.get("next_run_at")
        if job["schedule"].get("kind") == "once" and slot and datetime.fromisoformat(slot) <= ended:
            job["next_run_at"] = ended.isoformat()

    def create_with_slot(self, name, args):
        # Hermes parses "in <N>m" as a once schedule whose slot is creation time + N minutes and
        # stores repeat as {"times", "completed"}; the shared fixture stores a fixed 2027 slot.
        created = json.loads(super().dispatch_tool(name, args))
        match = re.fullmatch(r"in (\d+)([mhd])", args.get("schedule", ""))
        if not created.get("success") or match is None:
            return json.dumps(created)
        job = self.cron.jobs[created["job_id"]]
        slot = datetime.now(timezone.utc) + timedelta(minutes=int(match.group(1)) * {"m": 1, "h": 60, "d": 1440}[match.group(2)])
        job.update(schedule={"kind": "once", "run_at": slot.isoformat(), "display": "once " + args["schedule"]},
                   schedule_display="once " + args["schedule"], next_run_at=slot.isoformat(),
                   repeat={"times": args.get("repeat"), "completed": 0})
        created["job"] = self.format_job(job)
        return json.dumps(created)

    def execute(self, jid, *, origin):
        job = self.cron.get_job(jid)
        sid = job["name"].split(":")[1]
        count = len([effect for effect in self.effects if effect["space"] == sid]) + 1
        marker = {"space": sid, "job_id": jid, "execution_count": count}
        written = self.fx.projects.write_files(
            sid, files={"refresh-effect.json": json.dumps(marker)},
            author="agent:refresh-double", summary=f"Synthetic {origin} refresh effect")
        observed = json.loads(self.fx.core.read_file(sid, "refresh-effect.json")["text"])
        self.effects.append({**observed, "rev": written["rev"], "origin": origin})
        return self.cron.execution(jid, status="completed")

    def scheduler_tick(self, now):
        """One Hermes scheduler tick for one-shots: get_due_jobs eligibility, then a scheduled fire
        whose mark_job_run -> _advance_after_run spends the repeat budget and retires the record."""
        fired = []
        for jid, job in list(self.cron.jobs.items()):
            next_run = job.get("next_run_at")
            if (job.get("enabled") is not True or job.get("state") != "scheduled" or next_run is None
                    or datetime.fromisoformat(next_run) > now):
                continue
            assert job["schedule"].get("kind") == "once", f"recurring advance is not modeled: {jid}"
            self.execute(jid, origin="scheduled")
            repeat = job["repeat"]
            repeat["completed"] += 1
            job.update(last_run_at=now.isoformat(), last_status="ok")
            if repeat["times"] is not None and repeat["completed"] >= repeat["times"]:
                job.update(enabled=False, state="completed", next_run_at=None)
            fired.append(jid)
        return fired


class AgentRefreshDispatchTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.fx = CustomizationFixture(self.stack)
        self.ctx = PausedRefusingContext(self.fx)
        self.fx.ctx = self.ctx
        self.fx.upkeep.configure_context(self.ctx)

    @contextmanager
    def observe(self, sid, precondition):
        record = {
            "case": self.id(), "space": sid, "precondition": precondition,
            "jobs_before": self.fx.cron.list_jobs(include_disabled=True),
            "link_before": self.fx.upkeep.get_upkeep(sid)["link"],
            "result": None, "error": None,
        }
        reply_start = len(self.ctx.run_replies)
        attempt_start = len(self.ctx.run_attempts)
        activation_start = len(self.ctx.activation_refusals)
        try:
            yield record
        finally:
            files = self.fx.core.list_files(sid)
            marker = (self.fx.core.read_file(sid, "refresh-effect.json")
                      if any(file["path"] == "refresh-effect.json" for file in files) else None)
            record.update(
                jobs_after=self.fx.cron.list_jobs(include_disabled=True),
                link_after=self.fx.upkeep.get_upkeep(sid)["link"],
                observed_space_marker=marker,
                observed_execution_effect=[copy.deepcopy(effect) for effect in self.ctx.effects
                                           if effect["space"] == sid],
                executions=copy.deepcopy(self.fx.cron.executions),
                raw_replies=copy.deepcopy(self.ctx.run_replies[reply_start:]),
                run_attempts=copy.deepcopy(self.ctx.run_attempts[attempt_start:]),
                activation_refusals=copy.deepcopy(self.ctx.activation_refusals[activation_start:]),
            )
            print(json.dumps(record, sort_keys=True), flush=True)

    def refresh(self, sid, observation):
        try:
            result = self.fx.runs.start_refresh(sid, trigger="manual", actor="user")
        except self.fx.core.SpacesError as exc:
            observation["error"] = exc.to_dict()
            raise
        observation["result"] = result
        return result

    def assert_executed_once(self, sid, result):
        effects = [effect for effect in self.ctx.effects if effect["space"] == sid]
        self.assertEqual(len(effects), 1)
        marker = json.loads(self.fx.core.read_file(sid, "refresh-effect.json")["text"])
        self.assertEqual(marker, {"space": sid, "job_id": result["cron_job_id"], "execution_count": 1})
        executions = [entry for entry in self.fx.cron.executions if entry["job_id"] == result["cron_job_id"]]
        self.assertEqual(len(executions), 1)
        self.assertEqual(executions[0]["status"], "completed")
        attempts = [entry for entry in self.ctx.run_attempts if entry["job_id"] == result["cron_job_id"]]
        self.assertEqual(len(attempts), 1)
        self.assertIs(attempts[0]["job"]["enabled"], True)
        self.assertEqual(result["dispatch"], self.ctx.run_replies[-1])
        self.assertIs(result["dispatch"]["job"]["execution_success"], True)

    def healthy_control(self):
        sid = self.fx.make()
        self.fx.schedule(sid)
        with self.observe(sid, "Healthy linked enabled inline-run control") as observation:
            result = self.refresh(sid, observation)
            self.assert_executed_once(sid, result)

    def test_fresh_unlinked_refresh_executes_once(self):
        self.healthy_control()
        sid = self.fx.make()
        with self.observe(sid, "Fresh agent Space with no linked or one-shot job") as observation:
            result = self.refresh(sid, observation)
            self.assert_executed_once(sid, result)
            self.assertIsNone(self.fx.upkeep.get_upkeep(sid)["link"])

    def test_scheduler_double_fires_unrun_one_shot_once(self):
        sid = self.fx.make()
        created = json.loads(self.ctx.dispatch_tool("cronjob_manage", {
            "action": "create", "prompt": "Update this Space.", "schedule": "in 1m", "repeat": 1,
            "name": f"living-spaces:{sid}:once", "no_agent": False, "deliver": "local"}))
        jid = created["job_id"]
        due = datetime.now(timezone.utc) + timedelta(minutes=2)
        self.assertEqual(self.ctx.scheduler_tick(due - timedelta(minutes=1, seconds=30)), [])
        self.assertEqual(self.ctx.scheduler_tick(due), [jid])
        self.assertEqual(self.ctx.scheduler_tick(due + timedelta(minutes=5)), [])
        job = self.fx.cron.get_job(jid)
        self.assertEqual((job["enabled"], job["state"], job["next_run_at"], job["repeat"]),
                         (False, "completed", None, {"times": 1, "completed": 1}))
        self.assertEqual([effect["origin"] for effect in self.ctx.effects if effect["space"] == sid], ["scheduled"])

    def test_fresh_refresh_is_not_executed_again_by_scheduler(self):
        sid = self.fx.make()
        with self.observe(sid, "Fresh Refresh now, then a scheduler tick past the one-shot slot") as observation:
            result = self.refresh(sid, observation)
            self.assert_executed_once(sid, result)
            observation["scheduler_fired"] = self.ctx.scheduler_tick(
                datetime.now(timezone.utc) + timedelta(minutes=2))
            effects = [effect for effect in self.ctx.effects if effect["space"] == sid]
            self.assertEqual([(effect["origin"], effect["execution_count"]) for effect in effects],
                             [("manual", 1)])
            self.assertEqual(observation["scheduler_fired"], [])
            self.assertEqual([entry for entry in self.fx.cron.executions
                              if entry["job_id"] == result["cron_job_id"]][1:], [])

    def refuse(self, *actions, job_id):
        original = self.ctx.dispatch_tool
        refused = []

        def dispatch(name, args):
            if args["action"] in actions and args.get("job_id") == job_id():
                refused.append(args["action"])
                return json.dumps({"success": False, "error": "Synthetic " + args["action"] + " refusal"})
            return original(name, args)
        return patch.object(self.ctx, "dispatch_tool", side_effect=dispatch), refused

    def unrelated_jobs(self):
        other = self.fx.make()
        self.fx.schedule(other)
        json.loads(self.ctx.dispatch_tool("cronjob_manage", {
            "action": "create", "prompt": "Unrelated daily brief.", "schedule": "in 1m", "repeat": 1,
            "name": "daily-brief", "no_agent": False, "deliver": "local"}))
        return self.fx.cron.list_jobs(include_disabled=True)

    def fresh_once_id(self):
        return next((entry["job_id"] for entry in reversed(self.ctx.run_attempts)), None)

    def test_successful_fresh_refresh_retires_only_its_one_shot(self):
        unrelated = self.unrelated_jobs()
        sid = self.fx.make()
        with self.observe(sid, "Fresh Refresh now beside a linked job and an unrelated one-shot") as observation:
            result = self.refresh(sid, observation)
            self.assert_executed_once(sid, result)
            jid = result["cron_job_id"]
            self.assertEqual(result["one_shot"], {"job_id": jid, "consumed": "removed"})
            self.assertIsNone(self.fx.cron.get_job(jid))
            self.assertEqual(self.fx.cron.list_jobs(include_disabled=True), unrelated)
            shown = self.fx.upkeep.get_upkeep(sid)
            self.assertEqual((shown["link"], shown["one_shots"]), (None, []))

    def test_linked_refresh_keeps_its_recurring_job(self):
        sid = self.fx.make()
        first = self.fx.schedule(sid)
        jid = first["link"]["cron_job_id"]
        before = self.fx.cron.get_job(jid)
        with self.observe(sid, "Linked recurring job is not invocation-owned") as observation:
            result = self.refresh(sid, observation)
            self.assert_executed_once(sid, result)
            self.assertNotIn("one_shot", result)
            after = self.fx.cron.get_job(jid)
            self.assertEqual({key: after[key] for key in ("enabled", "state", "next_run_at", "schedule")},
                             {key: before[key] for key in ("enabled", "state", "next_run_at", "schedule")})

    def test_unremovable_one_shot_is_disabled_and_reported(self):
        sid = self.fx.make()
        refusal, refused = self.refuse("remove", job_id=self.fresh_once_id)
        with self.observe(sid, "Successful fresh refresh whose one-shot removal is refused") as observation:
            with refusal:
                result = self.refresh(sid, observation)
            self.assert_executed_once(sid, result)
            jid = result["cron_job_id"]
            self.assertEqual(refused, ["remove"])
            self.assertEqual((result["one_shot"]["job_id"], result["one_shot"]["consumed"]), (jid, "paused"))
            self.assertIn("Synthetic remove refusal", json.dumps(result["one_shot"]["cleanup"]))
            self.assertIs(self.fx.cron.get_job(jid)["enabled"], False)
            shots = self.fx.upkeep.get_upkeep(sid)["one_shots"]
            self.assertEqual([(shot["id"], shot["enabled"]) for shot in shots], [(jid, False)])
            observation["scheduler_fired"] = self.ctx.scheduler_tick(
                datetime.now(timezone.utc) + timedelta(minutes=2))
            self.assertEqual(observation["scheduler_fired"], [])
            self.assertEqual([effect["origin"] for effect in self.ctx.effects if effect["space"] == sid], ["manual"])

    def test_unconsumed_one_shot_is_not_reported_as_success(self):
        sid = self.fx.make()
        refusal, refused = self.refuse("pause", "remove", job_id=self.fresh_once_id)
        with self.observe(sid, "Successful fresh refresh whose one-shot can be neither paused nor removed") as observation:
            with refusal, self.assertRaises(self.fx.core.SpacesError) as caught:
                self.refresh(sid, observation)
            error = caught.exception.to_dict()
            jid = self.ctx.run_attempts[-1]["job_id"]
            self.assertEqual(sorted(refused), ["pause", "remove"])
            self.assertEqual((error["code"], error["reason"], error["orphan_job_id"]),
                             ("blocked", "one_shot_not_consumed", jid))
            self.assertEqual(error["native"], self.ctx.run_replies[-1])
            self.assertIs(error["native"]["job"]["execution_success"], True)
            self.assertIn("Synthetic pause refusal", json.dumps(error["pause"]))
            self.assertIn("Synthetic remove refusal", json.dumps(error["cleanup"]))
            self.assertIn("may run again", error["message"])
            self.assertIs(self.fx.cron.get_job(jid)["enabled"], True)
            self.assertEqual([effect["origin"] for effect in self.ctx.effects if effect["space"] == sid], ["manual"])

    def test_failed_fresh_refresh_is_cleaned_not_consumed(self):
        self.healthy_control()
        for outcome in (RunOutcome.FAILED, RunOutcome.SKIPPED):
            with self.subTest(outcome=outcome.value):
                sid = self.fx.make()
                before = self.fx.cron.list_jobs(include_disabled=True)
                self.ctx.outcome = outcome
                with self.observe(sid, "Fresh one-shot whose inline run fails, " + outcome.value) as observation:
                    with self.assertRaises(self.fx.core.SpacesError) as caught:
                        self.refresh(sid, observation)
                    self.assertEqual((caught.exception.code, caught.exception.extra["reason"]),
                                     ("blocked", "native_refused"))
                    self.assertEqual(caught.exception.extra["native"], self.ctx.run_replies[-1])
                    self.assertEqual(self.fx.cron.list_jobs(include_disabled=True), before)
                    self.assertEqual(self.ctx.scheduler_tick(datetime.now(timezone.utc) + timedelta(minutes=2)), [])
                    self.assertEqual([effect for effect in self.ctx.effects if effect["space"] == sid], [])

    def test_cron_origin_refresh_is_refused_without_creating_a_one_shot(self):
        sid = self.fx.make()
        before = self.fx.cron.list_jobs(include_disabled=True)
        self.ctx.execution = {"job_id": "synthetic-running-cron"}
        with self.observe(sid, "Refresh now requested from inside a cron execution") as observation:
            with self.assertRaises(self.fx.core.SpacesError) as caught:
                self.refresh(sid, observation)
            self.assertEqual(caught.exception.extra["reason"], "cron_recursion")
            self.assertEqual(self.fx.cron.list_jobs(include_disabled=True), before)
            self.assertEqual(self.ctx.run_attempts, [])

    def test_enabled_linked_refresh_executes_once(self):
        sid = self.fx.make()
        first = self.fx.schedule(sid)
        jid = first["link"]["cron_job_id"]
        with self.observe(sid, "Pre-existing linked enabled agent job") as observation:
            result = self.refresh(sid, observation)
            self.assert_executed_once(sid, result)
            self.assertEqual(result["cron_job_id"], jid)
            self.assertEqual(self.fx.upkeep.get_upkeep(sid)["link"], first["link"])
            self.assertIs(self.fx.cron.get_job(jid)["enabled"], True)

    def test_explicit_non_execution_is_refused(self):
        self.healthy_control()
        for outcome in (RunOutcome.SKIPPED, RunOutcome.NOT_EXECUTED, RunOutcome.SKIP_ONLY):
            with self.subTest(outcome=outcome.value):
                sid = self.fx.make()
                self.fx.schedule(sid)
                self.ctx.outcome = outcome
                before = self.fx.cron.list_jobs(include_disabled=True)
                with self.observe(sid, "Synthetic enabled-job refusal, " + outcome.value) as observation:
                    with self.assertRaises(self.fx.core.SpacesError) as caught:
                        self.refresh(sid, observation)
                    self.assertEqual(caught.exception.code, "blocked")
                    self.assertEqual(caught.exception.extra["native"], self.ctx.run_replies[-1])
                    self.assertIs(self.ctx.run_attempts[-1]["job"]["enabled"], True)
                    jid = self.ctx.run_attempts[-1]["job_id"]
                    self.assertEqual([entry for entry in self.fx.cron.executions if entry["job_id"] == jid], [])
                    self.assertEqual([effect for effect in self.ctx.effects if effect["space"] == sid], [])
                    self.assertEqual(self.fx.cron.list_jobs(include_disabled=True), before)

    def test_public_refresh_refusal_preserves_native_diagnostics(self):
        plugin = self.fx.load("_agent_refresh_dispatch_plugin", PACKAGE / "__init__.py")
        handler = plugin._handler(plugin.spaces_refresh)
        with patch.object(plugin._core, "load_core", return_value=self.fx.core):
            control = self.fx.make()
            self.fx.schedule(control)
            with self.observe(control, "Healthy public linked enabled inline-run control") as observation:
                reply = json.loads(handler({"space": control}, profile_name="Refresh regression"))
                observation["result"] = reply
                self.assertIs(reply["ok"], True, reply)
                self.assert_executed_once(control, reply["result"])
            for outcome in (RunOutcome.SKIPPED, RunOutcome.NOT_EXECUTED, RunOutcome.FAILED):
                with self.subTest(outcome=outcome.value):
                    sid = self.fx.make()
                    self.fx.schedule(sid)
                    self.ctx.outcome = outcome
                    with self.observe(sid, "Synthetic public native refusal, " + outcome.value) as observation:
                        reply = json.loads(handler({"space": sid}, profile_name="Refresh regression"))
                        observation["result"] = reply
                        if "error" in reply:
                            observation["error"] = reply["error"]
                        self.assertIs(reply["ok"], False, reply)
                        self.assertEqual(reply["error"]["code"], "blocked")
                        self.assertEqual(reply["error"]["native"], self.ctx.run_replies[-1])
                        self.assertNotIn("result", reply)
                        self.assertEqual([effect for effect in self.ctx.effects if effect["space"] == sid], [])

    def test_paused_linked_refresh_preserves_job_and_link(self):
        self.healthy_control()
        sid = self.fx.make()
        first = self.fx.schedule(sid)
        jid = first["link"]["cron_job_id"]
        self.fx.upkeep.upkeep_action(sid, "pause", actor="user")
        before = self.fx.cron.list_jobs(include_disabled=True)
        with self.observe(sid, "Operator-paused pre-existing linked job, not invocation-owned") as observation:
            with self.assertRaises(self.fx.core.SpacesError):
                self.refresh(sid, observation)
            self.assertEqual(self.fx.cron.list_jobs(include_disabled=True), before)
            self.assertEqual(self.fx.upkeep.get_upkeep(sid)["link"], first["link"])
            self.assertIs(self.fx.cron.get_job(jid)["enabled"], False)
            self.assertEqual([effect for effect in self.ctx.effects if effect["space"] == sid], [])
            self.assertEqual([entry for entry in self.fx.cron.executions if entry["job_id"] == jid], [])

    def test_inline_execution_failure_is_refused(self):
        self.healthy_control()
        sid = self.fx.make()
        first = self.fx.schedule(sid)
        self.ctx.outcome = RunOutcome.FAILED
        with self.observe(sid, "Synthetic enabled inline execution fails before its Space write") as observation:
            with self.assertRaises(self.fx.core.SpacesError) as caught:
                self.refresh(sid, observation)
            self.assertEqual(caught.exception.code, "blocked")
            self.assertEqual(caught.exception.extra["native"], self.ctx.run_replies[-1])
            executions = [entry for entry in self.fx.cron.executions
                          if entry["job_id"] == first["link"]["cron_job_id"]]
            self.assertEqual(len(executions), 1)
            self.assertEqual(executions[0]["status"], "failed")
            self.assertEqual([effect for effect in self.ctx.effects if effect["space"] == sid], [])
            self.assertEqual(self.fx.upkeep.get_upkeep(sid)["link"], first["link"])

    def test_accepted_dispatch_metadata_does_not_invent_completion(self):
        self.healthy_control()
        for outcome in (RunOutcome.FORWARDED, RunOutcome.BACKGROUND, RunOutcome.UNSPECIFIED):
            with self.subTest(outcome=outcome.value):
                sid = self.fx.make()
                first = self.fx.schedule(sid)
                self.ctx.outcome = outcome
                with self.observe(sid, "Accepted enabled dispatch, " + outcome.value) as observation:
                    result = self.refresh(sid, observation)
                    self.assertEqual(result, {"kind": "cron", "cron_job_id": first["link"]["cron_job_id"],
                                              "dispatch": self.ctx.run_replies[-1]})
                    self.assertNotIn("execution_success", result["dispatch"].get("job", {}))
                    self.assertEqual([effect for effect in self.ctx.effects if effect["space"] == sid], [])
                    executions = [entry for entry in self.fx.cron.executions
                                  if entry["job_id"] == first["link"]["cron_job_id"]]
                    self.assertEqual([entry["status"] for entry in executions],
                                     ["running"] if outcome is RunOutcome.BACKGROUND else [])

    def test_activation_refusal_cleans_only_new_job(self):
        self.healthy_control()
        sid = self.fx.make()
        before = self.fx.cron.list_jobs(include_disabled=True)
        self.ctx.deny_activation = True
        with self.observe(sid, "Synthetic policy refuses resume or creation of enabled work") as observation:
            with self.assertRaises(self.fx.core.SpacesError) as caught:
                self.refresh(sid, observation)
            self.assertTrue(self.ctx.activation_refusals)
            self.assertEqual(caught.exception.extra["native"], self.ctx.activation_refusals[-1])
            self.assertEqual(self.fx.cron.list_jobs(include_disabled=True), before)
            self.assertIsNone(self.fx.upkeep.get_upkeep(sid)["link"])
            self.assertEqual([effect for effect in self.ctx.effects if effect["space"] == sid], [])

    def test_skipped_fresh_refresh_cleans_only_owned_one_shot(self):
        self.healthy_control()
        sid = self.fx.make(handler="feed")
        first = self.fx.schedule(sid, kind="feed")
        shim_before = self.fx.upkeep._shim(sid).read_bytes()
        before = self.fx.cron.list_jobs(include_disabled=True)
        self.fx.change_upkeep(sid, {"handler": "agent", "prompt": "Update this Space."})
        self.ctx.outcome = RunOutcome.SKIPPED
        with self.observe(sid, "Synthetic forced skip of fresh agent one-shot beside an existing feed link") as observation:
            with self.assertRaises(self.fx.core.SpacesError) as caught:
                self.refresh(sid, observation)
            self.assertEqual(caught.exception.extra["native"], self.ctx.run_replies[-1])
            self.assertIs(self.ctx.run_attempts[-1]["job"]["enabled"], True)
            self.assertEqual(self.fx.cron.list_jobs(include_disabled=True), before)
            self.assertEqual(self.fx.upkeep.get_upkeep(sid)["link"], first["link"])
            self.assertEqual(self.fx.upkeep._shim(sid).read_bytes(), shim_before)
            self.assertEqual([effect for effect in self.ctx.effects if effect["space"] == sid], [])

    def assert_no_scheduler_rerun(self, sid, jid, horizon):
        for later in horizon:
            self.assertEqual(self.ctx.scheduler_tick(datetime.now(timezone.utc) + later), [], later)
        self.assertEqual([effect["origin"] for effect in self.ctx.effects if effect["space"] == sid
                          and effect["origin"] == "scheduled"], [])
        job = self.fx.cron.get_job(jid)
        self.assertTrue(job is None or job["enabled"] is False, job)

    def test_background_fresh_refresh_is_not_run_again_by_scheduler(self):
        sid = self.fx.make()
        self.ctx.outcome = RunOutcome.BACKGROUND
        with self.observe(sid, "Fresh Refresh now dispatched to the background, then scheduler ticks") as observation:
            result = self.refresh(sid, observation)
            jid = result["cron_job_id"]
            self.assertEqual(result["dispatch"], self.ctx.run_replies[-1])
            self.assertEqual(result["one_shot"], {"job_id": jid, "consumed": "paused", "execution_mode": "background"})
            self.assertEqual([entry["status"] for entry in self.fx.cron.executions if entry["job_id"] == jid],
                             ["running"])
            self.assertEqual([shot["id"] for shot in self.fx.upkeep.get_upkeep(sid)["one_shots"]], [jid])
            self.assert_no_scheduler_rerun(sid, jid, (timedelta(minutes=2), timedelta(days=2)))

    def test_inline_run_outlasting_its_slot_is_not_claimed_by_scheduler(self):
        for duration in (timedelta(seconds=90), timedelta(hours=6)):
            with self.subTest(duration=str(duration)):
                sid = self.fx.make()
                self.ctx.run_duration = duration
                self.ctx.tick_after_run = True
                with self.observe(sid, "Fresh inline run longer than the one-shot slot, tick before consumption") as observation:
                    result = self.refresh(sid, observation)
                    observation["ticks_during_run"] = self.ctx.ticks_during_run
                    self.assertEqual(self.ctx.ticks_during_run, [])
                    self.assert_executed_once(sid, result)
                    self.assertEqual(result["one_shot"], {"job_id": result["cron_job_id"], "consumed": "removed"})
                    self.assert_no_scheduler_rerun(sid, result["cron_job_id"], (timedelta(days=2),))

    def test_inline_run_outlasting_the_seven_day_slot_can_be_claimed_once_more_then_never(self):
        sid = self.fx.make()
        self.ctx.run_duration = timedelta(days=8)
        self.ctx.tick_after_run = True
        with self.observe(sid, "Fresh inline run longer than the 7-day slot, tick before consumption") as observation:
            result = self.refresh(sid, observation)
            jid = result["cron_job_id"]
            observation["ticks_during_run"] = self.ctx.ticks_during_run
            self.assertEqual(self.ctx.ticks_during_run, [jid])
            self.assertEqual([effect["origin"] for effect in self.ctx.effects if effect["space"] == sid],
                             ["manual", "scheduled"])
            self.assertIsNone(self.fx.cron.get_job(jid))
            for later in (timedelta(days=9), timedelta(days=30)):
                self.assertEqual(self.ctx.scheduler_tick(datetime.now(timezone.utc) + later), [], later)
            self.assertEqual([effect["origin"] for effect in self.ctx.effects if effect["space"] == sid],
                             ["manual", "scheduled"])

    def test_unverifiable_run_keeps_the_native_reply(self):
        sid = self.fx.make()
        dispatch = self.ctx.dispatch_tool
        failed = []

        def list_fails_once_after_run(name, args):
            if args["action"] == "list" and self.ctx.run_replies and not failed:
                failed.append(args)
                raise OSError("cron store unavailable")
            return dispatch(name, args)
        with self.observe(sid, "Fresh inline run succeeds, then the post-run job list fails once") as observation:
            with patch.object(self.ctx, "dispatch_tool", side_effect=list_fails_once_after_run), \
                    self.assertRaises(self.fx.core.SpacesError) as caught:
                self.refresh(sid, observation)
            error = caught.exception.to_dict()
            jid = self.ctx.run_attempts[-1]["job_id"]
            self.assertEqual(len(failed), 1)
            self.assertEqual(error["native"], self.ctx.run_replies[-1])
            self.assertIs(error["native"]["job"]["execution_success"], True)
            self.assertIn("cron store unavailable", error["message"])
            self.assertIsNone(self.fx.cron.get_job(jid))
            self.assert_no_scheduler_rerun(sid, jid, (timedelta(minutes=2), timedelta(days=8)))
            self.assertEqual([effect["origin"] for effect in self.ctx.effects if effect["space"] == sid], ["manual"])

    def test_refused_post_run_list_keeps_the_failed_run_diagnostic(self):
        sid = self.fx.make()
        dispatch = self.ctx.dispatch_tool
        refused = []
        self.ctx.outcome = RunOutcome.FAILED

        def list_refused_once_after_run(name, args):
            if args["action"] == "list" and self.ctx.run_replies and not refused:
                refused.append({"success": False, "error": "cron store locked"})
                return json.dumps(refused[-1])
            return dispatch(name, args)
        with self.observe(sid, "Fresh inline run fails, then the post-run job list is refused once") as observation:
            with patch.object(self.ctx, "dispatch_tool", side_effect=list_refused_once_after_run), \
                    self.assertRaises(self.fx.core.SpacesError) as caught:
                self.refresh(sid, observation)
            error = caught.exception.to_dict()
            jid = self.ctx.run_attempts[-1]["job_id"]
            self.assertEqual(error["native"], self.ctx.run_replies[-1])
            self.assertIs(error["native"]["job"]["execution_success"], False)
            self.assertEqual(error["native"]["job"]["execution_error"], "Synthetic model unavailable")
            self.assertEqual(error["verification"]["native"], refused[0])
            self.assertIn("cron store locked", error["message"])
            self.assertIsNone(self.fx.cron.get_job(jid))

    def test_store_failure_after_run_is_reported_and_cleaned(self):
        sid = self.fx.make()
        write = self.fx.db.write

        def failing_write():
            if self.ctx.run_replies:
                raise sqlite3.OperationalError("database is locked")
            return write()
        with self.observe(sid, "Fresh inline run succeeds, then the SQLite recheck raises") as observation:
            with patch.object(self.fx.db, "write", side_effect=failing_write), \
                    self.assertRaises(self.fx.core.SpacesError) as caught:
                self.refresh(sid, observation)
            error = caught.exception.to_dict()
            jid = self.ctx.run_attempts[-1]["job_id"]
            self.assertEqual((error["code"], error["reason"]), ("blocked", "post_run_check_failed"))
            self.assertIn("database is locked", error["message"])
            self.assertEqual(error["native"], self.ctx.run_replies[-1])
            self.assertIsNone(self.fx.cron.get_job(jid))
            self.assert_no_scheduler_rerun(sid, jid, (timedelta(minutes=2), timedelta(days=2)))
            self.assertEqual([effect["origin"] for effect in self.ctx.effects if effect["space"] == sid], ["manual"])


if __name__ == "__main__":
    unittest.main()
