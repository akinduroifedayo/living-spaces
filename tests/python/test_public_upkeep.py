"""Public cron contracts at the plugin boundary, with synthetic dispatch only."""
from contextlib import ExitStack
import json
import unittest
from unittest.mock import Mock, patch

from tests.python.review_customization_support import CustomizationFixture, PACKAGE, SyntheticContext


class PublicUpkeepTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.fx = CustomizationFixture(self.stack)

    def test_register_binds_context_for_tools_rest_archive_and_delete(self):
        fx = self.fx
        plugin = fx.load("_public_upkeep_plugin", PACKAGE / "__init__.py")
        ctx = SyntheticContext()
        ctx.register_tool = Mock()
        ctx.register_skill = Mock()
        ctx.register_rpc = Mock()
        with patch.object(plugin._core, "load_core", return_value=fx.core):
            plugin.register(ctx)
            tools = {call.kwargs["name"]: call.kwargs["handler"] for call in ctx.register_tool.call_args_list}
            sid = fx.make()
            reply = json.loads(tools["spaces_schedule_upkeep"]({"space": sid, "kind": "agent",
                               "cadence": "every 6h", "timezone": "UTC", "prompt": "Public task"}))
            self.assertTrue(reply["ok"], reply)
        jid = reply["result"]["link"]["cron_job_id"]
        self.assertIn(jid, ctx.cron.jobs)
        self.assertEqual(fx.cron.jobs, {})
        client = fx.client()
        self.assertEqual(client.post(f"/spaces/{sid}/upkeep", json={"action": "pause"}).status_code, 200)
        self.assertFalse(ctx.cron.jobs[jid]["enabled"])
        fx.projects.set_status(sid, "archived", actor="user")
        fx.projects.delete_space(sid, actor="user", confirm=sid)
        self.assertEqual(ctx.cron.jobs, {})
        self.assertEqual({name for name, _args in ctx.calls}, {"cronjob_manage"})
        self.assertTrue({"create", "list", "pause", "resume", "remove"}.issubset({args["action"] for _name, args in ctx.calls}))

    def test_native_model_mode_wins_over_stale_link_kind(self):
        fx = self.fx
        sid = fx.make(handler="feed")
        jid = fx.schedule(sid, kind="feed")["link"]["cron_job_id"]
        fx.cron.jobs[jid]["no_agent"] = False
        self.assertTrue(fx.upkeep.get_upkeep(sid)["job"]["uses_model"])
        fx.cron.jobs[jid]["no_agent"] = True
        self.assertFalse(fx.upkeep.get_upkeep(sid)["job"]["uses_model"])

    def test_failed_replacement_keeps_existing_link_job_and_feed_shim(self):
        fx = self.fx
        sid = fx.make(handler="feed")
        first = fx.schedule(sid, kind="feed")
        jid = first["link"]["cron_job_id"]
        shim = fx.upkeep._shim(sid)
        original = fx.ctx.dispatch_tool

        def dispatch(name, args):
            if args["action"] == "create":
                return json.dumps({"success": False, "error": "Prompt scan rejected replacement"})
            return original(name, args)

        calls = list(fx.cron.calls)
        with patch.object(fx.ctx, "dispatch_tool", side_effect=dispatch):
            with self.assertRaises(fx.core.SpacesError) as caught:
                fx.schedule(sid)
        self.assertIn("Prompt scan", caught.exception.message)
        self.assertEqual(fx.upkeep.get_upkeep(sid)["link"], first["link"])
        self.assertTrue(fx.cron.jobs[jid]["enabled"])
        self.assertEqual(fx.cron.calls, calls)
        self.assertTrue(shim.is_file())

    def test_context_is_keyed_by_profile_home_not_a_process_global_fallback(self):
        fx = self.fx
        with patch.object(fx.db, "hermes_home", return_value=fx.home / "profiles" / "other"):
            with self.assertRaises(fx.core.SpacesError) as caught:
                fx.upkeep._call("list", include_disabled=True)
            self.assertEqual(caught.exception.extra["reason"], "cron_context_unavailable")
            other = SyntheticContext()
            fx.upkeep.configure_context(other)
            fx.upkeep._call("list", include_disabled=True)
            self.assertEqual(len(other.calls), 1)
        fx.upkeep._call("list", include_disabled=True)
        self.assertEqual(len(fx.ctx.calls), 1)
        self.assertEqual(len(other.calls), 1)

    def test_run_preserves_queue_forward_inline_failure_and_skipped_responses(self):
        fx = self.fx
        sid = fx.make()
        fx.schedule(sid)
        replies = [
            {"success": True, "forwarded_to_gateway": True, "note": "Forwarded"},
            {"success": True, "job": {"job_id": "synthetic", "executed": True,
                                      "execution_mode": "background", "delegation_id": "synthetic"}},
            {"success": True, "job": {"job_id": "synthetic", "executed": True,
                                      "execution_success": False, "execution_error": "Model unavailable"}},
            {"success": True, "job": {"job_id": "synthetic", "executed": False,
                                      "execution_success": False, "execution_skipped": "Already claimed"}},
        ]
        for reply in replies:
            with self.subTest(reply=reply):
                fx.ctx.run_reply = reply
                result = fx.runs.start_refresh(sid, trigger="manual", actor="user")
                self.assertEqual(result["dispatch"], reply)
                self.assertNotIn("triggered", result)
                self.assertEqual(fx.upkeep.upkeep_action(sid, "run", actor="user")["dispatch"], reply)
        fx.ctx.run_reply = {"success": False, "error": "Provider refused"}
        with self.assertRaises(fx.core.SpacesError) as caught:
            fx.runs.start_refresh(sid, trigger="manual", actor="user")
        self.assertIn("Provider refused", caught.exception.message)

    def test_failed_delete_and_pause_responses_fail_closed(self):
        fx = self.fx
        sid = fx.make()
        jid = fx.schedule(sid)["link"]["cron_job_id"]
        original = fx.ctx.dispatch_tool

        def dispatch(name, args):
            if args["action"] in ("pause", "remove"):
                return {"success": False, "error": "Denied by native tool"}
            return original(name, args)

        with patch.object(fx.ctx, "dispatch_tool", side_effect=dispatch):
            with self.assertRaises(fx.core.SpacesError):
                fx.projects.set_status(sid, "archived", actor="user")
            with self.assertRaises(fx.core.SpacesError):
                fx.projects.delete_space(sid, actor="user", confirm=sid)
        self.assertEqual(fx.projects.get_space(sid)["status"], "active")
        self.assertEqual(fx.upkeep.get_upkeep(sid)["link"]["cron_job_id"], jid)
        self.assertTrue(fx.cron.jobs[jid]["enabled"])

    def test_inline_public_run_can_write_without_a_held_plugin_transaction(self):
        fx = self.fx
        sid = fx.make()
        fx.schedule(sid)
        original = fx.ctx.dispatch_tool

        def dispatch(name, args):
            if args["action"] == "run":
                import sqlite3

                with sqlite3.connect(fx.db.db_path(), timeout=0.05) as conn:
                    conn.execute("UPDATE spaces SET description='Inline public run' WHERE id=?", (sid,))
            return original(name, args)

        with patch.object(fx.ctx, "dispatch_tool", side_effect=dispatch):
            self.assertTrue(fx.runs.start_refresh(sid, trigger="manual", actor="user")["dispatch"]["success"])
            self.assertTrue(fx.upkeep.upkeep_action(sid, "run", actor="user")["dispatch"]["success"])
        self.assertEqual(fx.projects.get_space(sid)["description"], "Inline public run")

    def test_archive_during_public_run_is_rechecked_and_future_work_is_paused(self):
        fx = self.fx
        sid = fx.make()
        jid = fx.schedule(sid)["link"]["cron_job_id"]
        original = fx.ctx.dispatch_tool

        def dispatch(name, args):
            if args["action"] == "run":
                fx.projects.set_status(sid, "archived", actor="user")
            return original(name, args)

        with patch.object(fx.ctx, "dispatch_tool", side_effect=dispatch):
            with self.assertRaises(fx.core.SpacesError) as caught:
                fx.runs.start_refresh(sid, trigger="manual", actor="user")
        self.assertEqual(caught.exception.code, "archived")
        self.assertFalse(fx.cron.jobs[jid]["enabled"])
        self.assertEqual(fx.projects.get_space(sid)["status"], "archived")

    def test_gateway_warning_and_unavailable_views_survive_status_reads(self):
        fx = self.fx
        sid = fx.make()
        original = fx.ctx.dispatch_tool

        def dispatch(name, args):
            result = json.loads(original(name, args))
            if args["action"] == "list":
                result.update(gateway_running=False, warning="Gateway is not running; stored jobs do not fire")
            return json.dumps(result)

        with patch.object(fx.ctx, "dispatch_tool", side_effect=dispatch):
            shown = fx.schedule(sid)
            self.assertFalse(shown["gateway_running"])
            self.assertIn("do not fire", shown["warning"])
            self.assertTrue(shown["job"]["enabled"])
            self.assertIsNone(shown["job"]["prompt"])
            self.assertIsNone(shown["job"]["timezone"])
            self.assertTrue({"prompt", "timezone", "executions", "dispatch"}.issubset(shown["unavailable"]))
            self.assertEqual(fx.upkeep.get_upkeep(sid), shown)

    def test_incomplete_list_is_not_reported_as_missing_or_used_for_teardown(self):
        fx = self.fx
        sid = fx.make()
        fx.schedule(sid)
        with patch.object(fx.ctx, "dispatch_tool", return_value={"success": True, "count": 1, "jobs": []}):
            shown = fx.upkeep.get_upkeep(sid)
            self.assertIn("Invalid public cron", shown["error"])
            self.assertFalse(shown["missing"])
            with self.assertRaises(fx.core.SpacesError):
                fx.projects.delete_space(sid, actor="user", confirm=sid)


if __name__ == "__main__":
    unittest.main()
