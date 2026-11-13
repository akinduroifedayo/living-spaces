from contextlib import ExitStack, contextmanager
import copy
from enum import Enum
import json
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

    def dispatch_tool(self, name, args):
        assert name == "cronjob_manage", name
        action = args["action"]
        if self.deny_activation and (action == "resume" or
                                     (action == "create" and not args.get("paused", False))):
            self.calls.append((name, copy.deepcopy(args)))
            reply = {"success": False, "error": "Synthetic activation policy refusal"}
            self.activation_refusals.append(copy.deepcopy(reply))
            return json.dumps(reply)
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
            sid = job["name"].split(":")[1]
            count = len([effect for effect in self.effects if effect["space"] == sid]) + 1
            marker = {"space": sid, "job_id": jid, "execution_count": count}
            written = self.fx.projects.write_files(
                sid, files={"refresh-effect.json": json.dumps(marker)},
                author="agent:refresh-double", summary="Synthetic inline refresh effect")
            observed = json.loads(self.fx.core.read_file(sid, "refresh-effect.json")["text"])
            self.effects.append({**observed, "rev": written["rev"]})
            execution = self.cron.execution(jid, status="completed")
            reply = {"success": True, "job": dict(self.format_job(job), executed=True,
                     execution_mode="inline", execution_success=execution["status"] == "completed",
                     execution_id=execution["id"])}
            if job.get("repeat") == 1:
                self.cron.remove_job(jid)
        self.run_replies.append(copy.deepcopy(reply))
        return json.dumps(reply)


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


if __name__ == "__main__":
    unittest.main()
