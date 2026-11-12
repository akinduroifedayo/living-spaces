"""Recursion and cost bounds on all upkeep entry points, without executing model work."""
from contextlib import ExitStack
from dataclasses import dataclass
import json
import unittest
from unittest.mock import Mock, patch

from tests.python.review_customization_support import CustomizationFixture, PACKAGE


@dataclass(frozen=True)
class CronExecution:
    job_id: str = "outer-job"
    execution_id: str = "outer-fire"


class UpkeepGuardTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.fx = CustomizationFixture(self.stack)

    def assert_refused_without_mutation(self, call, reason):
        fx = self.fx
        before = list(fx.cron.calls)
        with self.assertRaises(fx.core.SpacesError) as caught:
            call()
        self.assertEqual(caught.exception.extra["reason"], reason)
        self.assertEqual(fx.cron.calls, before)

    def test_cron_execution_blocks_both_schedule_kinds_and_all_resume_run_paths_even_with_opt_in(self):
        fx = self.fx
        for global_flag in (False, True):
            for kind in ("agent", "feed"):
                with self.subTest(global_flag=global_flag, kind=kind):
                    fx.ctx.execution = None
                    sid = fx.make(handler=kind)
                    fx.schedule(sid, kind=kind)
                    fx.ctx.get_config = Mock(return_value=global_flag)
                    fx.ctx.execution = CronExecution()
                    self.assert_refused_without_mutation(lambda: fx.schedule(sid, kind=kind), "cron_recursion")
                    for action in ("resume", "run"):
                        self.assert_refused_without_mutation(
                            lambda: fx.upkeep.upkeep_action(sid, action, actor="user"), "cron_recursion")
                    if kind == "agent":
                        self.assert_refused_without_mutation(
                            lambda: fx.runs.start_refresh(sid, trigger="chat", actor="agent:review"), "cron_recursion")
                    fx.ctx.get_config.assert_not_called()
                    self.assertIsNotNone(fx.upkeep.get_upkeep(sid)["job"])
                    self.assertFalse(fx.upkeep.upkeep_action(sid, "pause", actor="user")["job"]["enabled"])
                    self.assertIsNone(fx.upkeep.upkeep_action(sid, "remove", actor="user")["link"])

    def test_cron_execution_blocks_unlinked_agent_refresh_through_tool_and_rest(self):
        fx = self.fx
        sid = fx.make()
        plugin = fx.load("_upkeep_guard_plugin", PACKAGE / "__init__.py")
        with patch.object(plugin._core, "load_core", return_value=fx.core):
            fx.ctx.execution = CronExecution()
            before = list(fx.cron.calls)
            reply = json.loads(plugin._handler(plugin.spaces_refresh)({"space": sid}))
            self.assertFalse(reply["ok"], reply)
            self.assertEqual(reply["error"]["reason"], "cron_recursion")
            response = fx.client().post(f"/spaces/{sid}/refresh")
            self.assertEqual(response.status_code, 423)
            self.assertEqual(response.json()["error"]["reason"], "cron_recursion")
            self.assertEqual(fx.cron.calls, before)

    def test_feed_refresh_inside_cron_remains_non_model(self):
        fx = self.fx
        sid = fx.make(handler="feed")
        fx.ctx.execution = CronExecution()
        with patch.object(fx.runs.threading.Thread, "start"):
            result = fx.runs.start_refresh(sid, trigger="chat", actor="agent:review")
        self.assertEqual(result["status"], "queued")
        self.assertEqual(fx.cron.calls, [])

    def test_missing_execution_identity_api_fails_closed(self):
        fx = self.fx
        sid = fx.make()
        with patch.object(fx.ctx, "current_cron_execution", side_effect=RuntimeError("Identity unavailable")):
            self.assert_refused_without_mutation(lambda: fx.schedule(sid), "cron_identity_unavailable")

    def test_fast_agent_intervals_cron_bursts_ranges_and_cross_hour_boundaries_are_rejected(self):
        fx = self.fx
        sid = fx.make()
        first = fx.schedule(sid)["link"]
        for cadence in ("every 1m", "every minute", "14m", "0m", "*/1 * * * *", "*/14 * * * *",
                        "0,1 * * * *", "0-10 * * * *", "0,59 * * * *", "0-59/16 * * * *",
                        "0,59 0,23 * * *", "* * * * * *"):
            with self.subTest(cadence=cadence):
                self.assert_refused_without_mutation(lambda: fx.schedule(sid, cadence=cadence), "agent_cadence")
                self.assertEqual(fx.upkeep.get_upkeep(sid)["link"], first)

    def test_safe_agent_intervals_and_common_cron_and_natural_forms_reach_public_validation(self):
        fx = self.fx
        sid = fx.make()
        for cadence in ("every 15m", "15 minutes", "every hour", "every 2h", "every day", "*/15 * * * *",
                        "0,15,30,45 * * * *", "0-59/15 * * * *", "0,59 0 * * *", "0 7 * JAN MON-FRI",
                        "every monday 9am", "weekdays at 9am", "every monday, wednesday at 9am"):
            with self.subTest(cadence=cadence):
                shown = fx.schedule(sid, cadence=cadence)
                self.assertEqual(shown["job"]["cadence"], cadence)
                creates = [args for _name, args in fx.ctx.calls if args["action"] == "create"]
                self.assertEqual(creates[-1]["schedule"], cadence)
        feed = fx.make(handler="feed")
        self.assertEqual(fx.schedule(feed, kind="feed", cadence="every 1m")["job"]["cadence"], "every 1m")

    def test_unsupported_agent_cadence_fails_closed_before_create(self):
        fx = self.fx
        sid = fx.make()
        for cadence in ("whenever", "@reboot", "0 0 * * * 0", "0 0 * * * 2027", "0 H * * *"):
            with self.subTest(cadence=cadence):
                self.assert_refused_without_mutation(lambda: fx.schedule(sid, cadence=cadence), "agent_cadence")

    def test_user_prompt_cap_counts_unicode_characters_not_wrapper_or_bytes(self):
        fx = self.fx
        sid = fx.make()
        accepted = "🦉" * 8000
        shown = fx.schedule(sid, prompt=accepted)
        jid = shown["link"]["cron_job_id"]
        self.assertTrue(fx.cron.jobs[jid]["prompt"].endswith(accepted))
        self.assertGreater(len(fx.cron.jobs[jid]["prompt"]), 8000)
        self.assert_refused_without_mutation(lambda: fx.schedule(sid, prompt=accepted + "a"), "agent_prompt_limit")
        with self.assertRaises(fx.core.SpacesError) as caught:
            fx.change_upkeep(sid, {"handler": "agent", "prompt": accepted + "a"})
        self.assertEqual(caught.exception.extra["limit"], 8000)
        self.assertEqual(caught.exception.extra["actual"], 8001)
        self.assertEqual(fx.upkeep.get_upkeep(sid)["link"]["cron_job_id"], jid)


if __name__ == "__main__":
    unittest.main()
