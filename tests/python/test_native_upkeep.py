"""Native-cron-only upkeep (A-03): the Hermes cron job is the only truth, the plugin keeps a link."""
from contextlib import ExitStack
import json
import sqlite3
import unittest
from unittest.mock import patch

from tests.python.review_customization_support import AGENT_PROMPT, PACKAGE, CustomizationFixture


class NativeUpkeepTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.fx = CustomizationFixture(self.stack)

    def jobs_named(self, name):
        return [job for job in self.fx.cron.jobs.values() if job["name"] == name]

    def test_schedule_creates_one_native_job_matching_what_get_upkeep_shows(self):
        fx = self.fx
        sid = fx.make()
        shown = fx.schedule(sid, cadence="0 7 * * *")
        self.assertEqual(len(fx.cron.jobs), 1)
        native = next(iter(fx.cron.jobs.values()))
        self.assertEqual(native["name"], f"living-spaces:{sid}")
        self.assertEqual((native["deliver"], native["catch_up"], native["no_agent"], native["timezone"]),
                         ("local", True, False, "UTC"))
        self.assertTrue(native["prompt"].endswith("Upkeep task:\n" + AGENT_PROMPT))
        self.assertIsNone(shown["job"]["prompt"])
        self.assertEqual(shown["job"]["prompt_preview"], native["prompt"][:100] + "...")
        self.assertEqual(shown["job"]["cadence"], native["schedule"]["expr"])
        self.assertEqual(shown["job"]["cadence"], "0 7 * * *")
        self.assertEqual(shown["link"]["kind"], "agent")
        self.assertEqual(shown["link"]["created_by"], "agent:review")
        self.assertEqual((shown["missing"], shown["error"]), (False, None))
        self.assertEqual(fx.upkeep.get_upkeep(sid), shown)

    def test_feed_schedule_runs_the_shim_with_no_model_calls(self):
        fx = self.fx
        sid = fx.make(handler="feed")
        shown = fx.schedule(sid, kind="feed")
        native = fx.cron.jobs[shown["link"]["cron_job_id"]]
        self.assertTrue(native["no_agent"])
        self.assertEqual(native["script"], f"living-spaces-refresh-{sid}.py")
        self.assertTrue((fx.home / "scripts" / native["script"]).is_file())
        self.assertIsNone(shown["job"]["prompt"])

    def test_replace_removes_the_old_job(self):
        fx = self.fx
        sid = fx.make()
        first = fx.schedule(sid)["link"]["cron_job_id"]
        second = fx.schedule(sid, prompt="A new task", cadence="every 6h")
        self.assertNotIn(first, fx.cron.jobs)
        self.assertEqual(list(fx.cron.jobs), [second["link"]["cron_job_id"]])
        self.assertTrue(fx.cron.jobs[second["link"]["cron_job_id"]]["prompt"].endswith("A new task"))
        with fx.db.read() as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM upkeep_links WHERE space=?", (sid,)).fetchone()[0], 1)

    def test_actions_pass_through_and_status_reads_native_state_without_a_local_copy(self):
        fx = self.fx
        sid = fx.make()
        jid = fx.schedule(sid)["link"]["cron_job_id"]
        paused = fx.upkeep.upkeep_action(sid, "pause", actor="user")
        self.assertEqual((paused["job"]["enabled"], paused["job"]["state"]), (False, "paused"))
        resumed = fx.upkeep.upkeep_action(sid, "resume", actor="user")
        self.assertEqual((resumed["job"]["enabled"], resumed["job"]["state"]), (True, "scheduled"))
        fx.upkeep.upkeep_action(sid, "run", actor="user")
        self.assertEqual([call[0] for call in fx.cron.calls[2:]], ["pause", "resume", "trigger"])
        fx.cron.jobs[jid].update(enabled=False, state="paused", last_status="error", last_error="Model unavailable")
        shown = fx.upkeep.get_upkeep(sid)
        self.assertEqual((shown["job"]["enabled"], shown["job"]["last_status"], shown["job"]["last_error"]),
                         (False, "error", "Model unavailable"))
        with fx.db.read() as conn:
            self.assertEqual([column[1] for column in conn.execute("PRAGMA table_info(upkeep_links)")],
                             ["space", "cron_job_id", "kind", "created_at", "created_by"])
        removed = fx.upkeep.upkeep_action(sid, "remove", actor="user")
        self.assertEqual(fx.cron.calls[-1], ("remove", jid))
        self.assertEqual(fx.cron.jobs, {})
        self.assertIsNone(removed["link"])

    def test_missing_native_job_is_reported(self):
        fx = self.fx
        sid = fx.make()
        jid = fx.schedule(sid)["link"]["cron_job_id"]
        del fx.cron.jobs[jid]
        shown = fx.upkeep.get_upkeep(sid)
        self.assertEqual((shown["missing"], shown["job"], shown["link"]["cron_job_id"]), (True, None, jid))
        self.assertTrue(fx.projects.get_space(sid)["upkeep"]["missing"])

    def test_unavailable_native_cron_sets_error_without_raising(self):
        fx = self.fx
        sid = fx.make()
        fx.schedule(sid)
        with patch.object(fx.ctx, "dispatch_tool", side_effect=ImportError("cron missing")):
            shown = fx.upkeep.get_upkeep(sid)
            space = fx.projects.get_space(sid)
        self.assertIn("cron missing", shown["error"])
        self.assertFalse(shown["missing"])
        self.assertEqual(space["id"], sid)

    def test_migration_links_schedules_drops_refresh_grants_and_is_idempotent(self):
        fx = self.fx
        agent, feed = fx.make(), fx.make(handler="feed")
        with fx.db.write() as conn:
            conn.execute("CREATE TABLE schedules(space TEXT PRIMARY KEY, status TEXT, cadence TEXT, timezone TEXT, cron_job_id TEXT)")
            conn.executemany("INSERT INTO schedules VALUES(?,?,?,?,?)", [
                (agent, "active", "0 * * * *", "UTC", "legacy-agent"),
                (feed, "paused", "0 * * * *", "UTC", "legacy-feed"),
            ])
            conn.execute("INSERT INTO grants(space,capability,status) VALUES(?,'refresh','granted')", (agent,))
            conn.execute("INSERT INTO audit(space,at,actor,action,capability,outcome) VALUES(?,0,'user','decision','refresh','granted')", (agent,))
            audit = conn.execute("SELECT count(*) FROM audit").fetchone()[0]
            fx.core.migrations.link_native_upkeep(conn)
            fx.core.migrations.link_native_upkeep(conn)
            links = conn.execute("SELECT space,cron_job_id,kind,created_by FROM upkeep_links ORDER BY space").fetchall()
            self.assertEqual([tuple(row) for row in links], [
                (agent, "legacy-agent", "agent", "migration"), (feed, "legacy-feed", "feed", "migration"),
            ])
            self.assertIsNone(conn.execute("SELECT 1 FROM sqlite_master WHERE name='schedules'").fetchone())
            self.assertEqual(conn.execute("SELECT count(*) FROM grants WHERE capability='refresh'").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT count(*) FROM audit").fetchone()[0], audit)

    def test_archive_pauses_and_unarchive_does_not_resume(self):
        fx = self.fx
        sid = fx.make()
        jid = fx.schedule(sid)["link"]["cron_job_id"]
        fx.projects.set_status(sid, "archived", actor="user")
        self.assertFalse(fx.cron.jobs[jid]["enabled"])
        with self.assertRaises(fx.core.SpacesError) as error:
            fx.upkeep.upkeep_action(sid, "resume", actor="user")
        self.assertEqual(error.exception.code, "archived")
        with self.assertRaises(fx.core.SpacesError) as error:
            fx.schedule(sid)
        self.assertEqual(error.exception.code, "archived")
        fx.projects.set_status(sid, "active", actor="user")
        self.assertFalse(fx.cron.jobs[jid]["enabled"])
        self.assertEqual(fx.cron.calls.count(("resume", jid)), 1)

    def test_delete_removes_jobs_shims_links_and_one_shots(self):
        fx = self.fx
        sid = fx.make(handler="feed")
        jid = fx.schedule(sid, kind="feed")["link"]["cron_job_id"]
        once = fx.cron.create_job(prompt="x", schedule="in 1m", name=f"living-spaces:{sid}:once", paused=True)["id"]
        other = fx.cron.create_job(prompt="x", schedule="in 1m", name="living-spaces:other-space:once")["id"]
        shim = fx.home / "scripts" / f"living-spaces-refresh-{sid}.py"
        self.assertTrue(shim.is_file())
        result = fx.projects.delete_space(sid, actor="user", confirm=sid)
        self.assertTrue(result["removed"]["upkeep"])
        self.assertEqual(set(fx.cron.jobs), {other})
        self.assertIn(("remove", jid), fx.cron.calls)
        self.assertIn(("remove", once), fx.cron.calls)
        self.assertFalse(shim.exists())
        with fx.db.read() as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM upkeep_links").fetchone()[0], 0)

    def test_agent_refresh_now_triggers_the_linked_job(self):
        fx = self.fx
        sid = fx.make()
        jid = fx.schedule(sid)["link"]["cron_job_id"]
        result = fx.runs.start_refresh(sid, trigger="manual", actor="user")
        self.assertEqual((result["kind"], result["cron_job_id"]), ("cron", jid))
        self.assertTrue(result["dispatch"]["success"])
        self.assertEqual(fx.cron.calls[-1], ("trigger", jid))
        self.assertEqual(len(fx.cron.jobs), 1)
        self.assertEqual(fx.runs.list_runs(sid), [])

    def test_agent_refresh_now_without_a_link_creates_an_unlinked_one_shot(self):
        fx = self.fx
        sid = fx.make()
        result = fx.runs.start_refresh(sid, trigger="chat", actor="agent:review")
        native = fx.cron.jobs[result["cron_job_id"]]
        self.assertEqual((result["kind"], result["cron_job_id"]), ("cron", native["id"]))
        self.assertTrue(result["dispatch"]["success"])
        self.assertEqual((native["name"], native["repeat"], native["no_agent"]), (f"living-spaces:{sid}:once", 1, False))
        self.assertEqual(native["prompt"], fx.upkeep.agent_prompt(sid, AGENT_PROMPT))
        self.assertEqual(fx.cron.calls[-1], ("trigger", native["id"]))
        self.assertIsNone(fx.upkeep.get_upkeep(sid)["link"])

    def test_guest_bridge_refresh_with_agent_handler_is_blocked(self):
        fx = self.fx
        sid = fx.make()
        fx.schedule(sid)
        before = list(fx.cron.calls)
        session = fx.sessions.open_session(sid)["session"]
        reply = fx.bridge.dispatch(sid, session, "refresh", {})
        self.assertFalse(reply["ok"])
        self.assertEqual(reply["error"], {"code": "blocked", "reason": "agent_from_guest",
                                          "message": "Agent upkeep runs from Refresh now in Hermes or from chat"})
        self.assertEqual(fx.cron.calls, before)

    def test_guest_bridge_feed_refresh_needs_no_refresh_grant(self):
        fx = self.fx
        sid = fx.make(handler="feed")
        session = fx.sessions.open_session(sid)["session"]
        with patch.object(fx.runs.threading.Thread, "start"):
            reply = fx.bridge.dispatch(sid, session, "refresh", {})
        self.assertTrue(reply["ok"], reply)
        self.assertEqual(reply["result"]["status"], "queued")
        self.assertNotIn("refresh", [row["capability"] for row in fx.grants.list_grants(sid)])

    def test_manifest_prompt_change_leaves_the_native_job_untouched(self):
        fx = self.fx
        sid = fx.make()
        jid = fx.schedule(sid)["link"]["cron_job_id"]
        before = json.dumps(fx.cron.jobs[jid], sort_keys=True)
        calls = list(fx.cron.calls)
        fx.change_upkeep(sid, {"handler": "agent", "prompt": "A different task in the manifest"})
        self.assertEqual(json.dumps(fx.cron.jobs[jid], sort_keys=True), before)
        self.assertEqual(fx.cron.calls, calls)
        self.assertTrue(fx.cron.jobs[jid]["prompt"].endswith(AGENT_PROMPT))
        self.assertIsNone(fx.upkeep.get_upkeep(sid)["job"]["prompt"])

    def test_execution_history_is_unavailable_not_fabricated(self):
        fx = self.fx
        sid = fx.make()
        jid = fx.schedule(sid)["link"]["cron_job_id"]
        for status in ("completed", "failed", "unknown", "running"):
            fx.cron.execution(jid, status)
        fx.cron.execution("someone-else", "completed")
        shown = fx.upkeep.get_upkeep(sid)["executions"]
        self.assertEqual(shown, [])
        self.assertIn("executions", fx.upkeep.get_upkeep(sid)["unavailable"])
        for _ in range(25):
            fx.cron.execution(jid, "completed")
        self.assertEqual(fx.upkeep.get_upkeep(sid)["executions"], [])

    def test_space_summary_exposes_upkeep_from_the_native_job(self):
        fx = self.fx
        sid = fx.make()
        self.assertIsNone(fx.projects.get_space(sid)["upkeep"])
        jid = fx.schedule(sid)["link"]["cron_job_id"]
        space = next(item for item in fx.projects.list_spaces() if item["id"] == sid)
        self.assertNotIn("schedule", space)
        self.assertEqual(space["upkeep"], {"cron_job_id": jid, "kind": "agent", "enabled": True, "state": "scheduled",
                                           "next_run_at": 1804809600.0, "missing": False})
        self.assertEqual(space["freshness"]["next_run_at"], 1804809600.0)

    def test_rest_upkeep_routes_and_removed_schedule_routes(self):
        fx = self.fx
        sid = fx.make()
        client = fx.client()
        self.assertIsNone(client.get(f"/spaces/{sid}/upkeep").json()["link"])
        fx.schedule(sid)
        shown = client.get(f"/spaces/{sid}/upkeep").json()
        self.assertEqual(shown, fx.upkeep.get_upkeep(sid))
        paused = client.post(f"/spaces/{sid}/upkeep", json={"action": "pause"})
        self.assertEqual((paused.status_code, paused.json()["job"]["enabled"]), (200, False))
        self.assertEqual(client.post(f"/spaces/{sid}/upkeep", json={"action": "delete"}).status_code, 400)
        self.assertEqual(client.post(f"/spaces/{sid}/upkeep", json={}).status_code, 400)
        self.assertEqual(client.get(f"/spaces/{sid}/schedule").status_code, 404)
        self.assertEqual(client.post(f"/spaces/{sid}/schedule", json={"paused": True}).status_code, 404)
        refresh = client.post(f"/spaces/{sid}/refresh").json()
        self.assertEqual((refresh["kind"], refresh["dispatch"]["success"]), ("cron", True))
        grant = client.post(f"/spaces/{sid}/grants/refresh", json={"decision": "revoke"})
        self.assertEqual((grant.status_code, grant.json()["error"]["code"]), (404, "not_found"))
        self.assertIn("upkeep", client.post(f"/spaces/{sid}/pin", json={"pinned": True}).json())

    def test_agent_tools_schedule_and_control_upkeep(self):
        fx = self.fx
        plugin = fx.load("_native_upkeep_plugin", PACKAGE / "__init__.py")
        names = [schema["name"] for _fn, schema in plugin.TOOLS]
        self.assertNotIn("spaces_request_schedule", names)
        tools = {schema["name"]: fn for fn, schema in plugin.TOOLS}
        sid = fx.make()
        with self.assertRaises(fx.core.SpacesError):
            tools["spaces_schedule_upkeep"](fx.core, {"space": sid, "kind": "agent", "cadence": "0 * * * *",
                                                       "timezone": "UTC"}, "Review")
        created = tools["spaces_schedule_upkeep"](fx.core, {"space": sid, "kind": "agent", "cadence": "0 * * * *",
                                                            "timezone": "UTC", "prompt": "Chat task"}, "Review")
        self.assertEqual(created["link"]["created_by"], "agent:Review")
        self.assertEqual(tools["spaces_upkeep"](fx.core, {"space": sid, "action": "status"}, "Review"), created)
        self.assertFalse(tools["spaces_upkeep"](fx.core, {"space": sid, "action": "pause"}, "Review")["job"]["enabled"])
        self.assertEqual(tools["spaces_get"](fx.core, {"space": sid}, "Review")["upkeep"]["enabled"], False)
        description = dict((schema["name"], schema["description"]) for _fn, schema in plugin.TOOLS)["spaces_schedule_upkeep"]
        for phrase in ("ordinary Hermes cron job", "consent", "model calls", "replaces"):
            self.assertIn(phrase, description)

    def test_feed_shim_never_starts_model_work_after_the_handler_becomes_agent(self):
        fx = self.fx
        sid = fx.make(handler="feed")
        fx.schedule(sid, kind="feed")
        fx.change_upkeep(sid, {"handler": "agent", "prompt": AGENT_PROMPT})
        before = dict(fx.cron.jobs)
        run = fx.runs.start_refresh(sid, trigger="schedule", actor="upkeep:schedule", wait=True)
        self.assertEqual((run["status"], run["detail"]["reason"]), ("blocked", "no_handler"))
        self.assertEqual(fx.cron.jobs.keys(), before.keys())
        self.assertNotIn("trigger", [call[0] for call in fx.cron.calls])

    def test_archive_pauses_pending_one_shots(self):
        fx = self.fx
        sid = fx.make()
        once = fx.runs.start_refresh(sid, trigger="manual", actor="user")["cron_job_id"]
        fx.projects.set_status(sid, "archived", actor="user")
        self.assertFalse(fx.cron.jobs[once]["enabled"])

    def test_archive_fails_closed_when_native_pause_fails(self):
        fx = self.fx
        sid = fx.make()
        jid = fx.schedule(sid)["link"]["cron_job_id"]
        with patch.object(fx.cron, "pause_job", side_effect=OSError("cron store unavailable")):
            with self.assertRaises(fx.core.SpacesError) as error:
                fx.projects.set_status(sid, "archived", actor="user")
        self.assertEqual(error.exception.code, "blocked")
        self.assertEqual(fx.projects.get_space(sid)["status"], "active")
        self.assertTrue(fx.cron.jobs[jid]["enabled"])
        fx.projects.set_status(sid, "archived", actor="user")
        self.assertFalse(fx.cron.jobs[jid]["enabled"])

    def test_archive_with_a_missing_linked_job_still_archives(self):
        fx = self.fx
        sid = fx.make()
        jid = fx.schedule(sid)["link"]["cron_job_id"]
        del fx.cron.jobs[jid]
        self.assertEqual(fx.projects.set_status(sid, "archived", actor="user")["status"], "archived")

    def test_refresh_now_one_shot_creation_holds_the_write_lock(self):
        fx = self.fx
        sid = fx.make()
        original = fx.cron.create_job
        observed = []

        def contend(**kwargs):
            contender = sqlite3.connect(fx.db.db_path(), timeout=0.05)
            try:
                contender.execute("BEGIN IMMEDIATE")
                observed.append("acquired")
                contender.execute("ROLLBACK")
            except sqlite3.OperationalError as exc:
                observed.append(str(exc))
            finally:
                contender.close()
            return original(**kwargs)

        with patch.object(fx.cron, "create_job", side_effect=contend):
            fx.runs.start_refresh(sid, trigger="manual", actor="user")
        self.assertEqual(observed, ["database is locked"])

    def test_pending_one_shots_are_visible_but_history_is_unavailable(self):
        fx = self.fx
        sid = fx.make()
        once = fx.runs.start_refresh(sid, trigger="manual", actor="user")["cron_job_id"]
        fx.cron.execution(once, "unknown")
        shown = fx.upkeep.get_upkeep(sid)
        self.assertIsNone(shown["link"])
        self.assertEqual([(shot["id"], shot["uses_model"], [e["status"] for e in shot["executions"]])
                          for shot in shown["one_shots"]], [(once, True, [])])
        self.assertIn("executions", shown["unavailable"])

    def test_shown_kind_uses_the_known_link_not_an_omitted_public_mode(self):
        fx = self.fx
        sid = fx.make(handler="feed")
        jid = fx.schedule(sid, kind="feed")["link"]["cron_job_id"]
        fx.cron.jobs[jid].update(no_agent=False, prompt="Edited in cron")
        shown = fx.upkeep.get_upkeep(sid)
        self.assertEqual((shown["job"]["uses_model"], shown["job"]["prompt"]), (False, None))
        self.assertIsNone(shown["job"]["timezone"])
        self.assertEqual(shown["job"]["prompt_preview"], "Edited in cron")
        self.assertEqual(fx.projects.get_space(sid)["upkeep"]["kind"], "feed")

    def test_agent_task_at_the_prompt_cap_is_accepted(self):
        fx = self.fx
        sid = fx.make()
        long_prompt = "a" * 8000
        shown = fx.schedule(sid, prompt=long_prompt)
        self.assertTrue(fx.cron.jobs[shown["link"]["cron_job_id"]]["prompt"].endswith(long_prompt))

    def test_link_table_enforces_kind_and_unique_job(self):
        fx = self.fx
        sid = fx.make()
        with fx.db.write() as conn:
            conn.execute("INSERT INTO upkeep_links VALUES(?, 'a', 'feed', 0, 'user')", (sid,))
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("INSERT INTO upkeep_links VALUES(?, 'a', 'agent', 0, 'user')", (sid,))
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("INSERT INTO upkeep_links VALUES(?, 'b', 'shell', 0, 'user')", (sid,))


if __name__ == "__main__":
    unittest.main()
