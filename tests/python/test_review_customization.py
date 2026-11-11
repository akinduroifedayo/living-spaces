"""Fixed-behavior regressions for F01-F09, using real core/SQLite/adapters.

Cron executions and HTTPS responses are synthetic; no model, ticker or network runs.
"""
from contextlib import ExitStack
import copy
from datetime import datetime
import json
import sqlite3
import unittest
from unittest.mock import patch

from tests.python.review_customization_support import (
    AGENT_PROMPT, PUBLIC, SCHEDULE_FIELDS, CustomizationFixture, Response,
)


class ReviewCustomizationTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.fx = CustomizationFixture(self.stack)

    def assert_agent_change_blocked(self, sid, prompt):
        fx = self.fx
        before = list(fx.cron.calls)
        session = fx.sessions.open_session(sid)["session"]
        reply = fx.bridge.dispatch(sid, session, "refresh", {})
        grant = fx.refresh_grant(sid)
        calls = fx.cron.calls[len(before):]
        with self.subTest(boundary="native admission"):
            self.assertEqual([call for call in calls if call[0] in ("create", "trigger")], [])
        with self.subTest(boundary="frame result"):
            self.assertFalse(reply["ok"], reply)
            self.assertEqual(reply["error"]["code"], "not_granted")
        with self.subTest(boundary="host decision required"):
            self.assertEqual(grant["status"], "requested")
        with self.subTest(boundary="displayed agent authority"):
            self.assertEqual(grant["requested_scope"], {
                "hosts": [], "upkeep": {"handler": "agent", "prompt": prompt},
            })

    def test_f01_feed_to_agent_requires_fresh_refresh_approval(self):
        fx = self.fx
        sid = fx.make(handler="feed")
        self.assertEqual(fx.refresh_grant(sid)["scope"], {"hosts": ["example.org"]})
        prompt = "Run the newly introduced agent task."
        fx.change_upkeep(sid, {"handler": "agent", "prompt": prompt})
        self.assertIsNone(fx.schedules.get_schedule(sid))
        self.assert_agent_change_blocked(sid, prompt)

    def test_f01_agent_prompt_change_blocks_manual_and_scheduled_admission(self):
        fx = self.fx
        sid = fx.make()
        jid = fx.approve_schedule(sid)["cron_job_id"]
        prompt = "A different agent task not yet approved"
        fx.change_upkeep(sid, {"handler": "agent", "prompt": prompt})
        scheduled = fx.runs.start_refresh(sid, trigger="schedule", actor="upkeep:schedule")
        self.assertEqual(fx.schedules.get_schedule(sid)["status"], "requested")
        self.assertFalse(fx.cron.jobs[jid]["enabled"])
        self.assertEqual(scheduled["status"], "blocked")
        self.assertIn(scheduled["detail"]["reason"], ("not_granted", "schedule_not_approved"))
        self.assert_agent_change_blocked(sid, prompt)

    def test_f01_stale_agent_scope_cannot_approve_changed_prompt(self):
        fx = self.fx
        sid = fx.make()
        displayed = copy.deepcopy(fx.refresh_grant(sid)["requested_scope"])
        fx.change_upkeep(sid, {"handler": "agent", "prompt": "A different agent task not yet approved"})
        client = fx.client()
        response = client.post(f"/spaces/{sid}/grants/refresh", json={
            "decision": "grant", "requested_scope": displayed,
        })
        self.assertEqual(response.status_code, 409, response.json())
        self.assertEqual(response.json()["error"]["code"], "conflict")
        self.assertEqual(fx.refresh_grant(sid)["status"], "requested")
        self.assertEqual(fx.cron.calls, [])

    def test_f01_matching_agent_approval_allows_manual_refresh_control(self):
        fx = self.fx
        sid = fx.make()
        client = fx.client()
        displayed = fx.refresh_grant(sid)["requested_scope"]
        response = client.post(f"/spaces/{sid}/grants/refresh", json={
            "decision": "grant", "requested_scope": displayed,
        })
        self.assertEqual(response.status_code, 200, response.json())
        session = fx.sessions.open_session(sid)["session"]
        reply = fx.bridge.dispatch(sid, session, "refresh", {})
        self.assertTrue(reply["ok"], reply)
        self.assertEqual(reply["result"]["status"], "queued")
        jid = reply["result"]["detail"]["cron_job_id"]
        self.assertFalse(fx.cron.jobs[jid]["no_agent"])
        self.assertIn(AGENT_PROMPT, fx.cron.jobs[jid]["prompt"])
        self.assertEqual([call for call in fx.cron.calls if call[0] == "trigger"], [("trigger", jid)])

    def test_f01_unchanged_feed_manifest_preserves_host_scope_control(self):
        fx = self.fx
        sid = fx.make(handler="feed")
        before = fx.refresh_grant(sid)
        fx.change_upkeep(sid, fx.projects.bundle(sid)["manifest"]["upkeep"])
        after = fx.refresh_grant(sid)
        self.assertEqual(after["status"], "granted")
        self.assertEqual(after["scope"], {"hosts": ["example.org"]})
        self.assertEqual(after["requested_scope"], before["requested_scope"])
        self.assertEqual(fx.cron.calls, [])

    def test_f02_stale_displayed_schedule_conflicts_at_rest_boundary(self):
        fx = self.fx
        sid = fx.make()
        upkeep = fx.projects.bundle(sid)["manifest"]["upkeep"]
        displayed = fx.schedules.request_schedule(sid, cadence="0 7 1 * *", timezone="UTC",
                                                  purpose="Once a month", actor="agent:review")
        current = fx.schedules.request_schedule(sid, cadence="* * * * *", timezone="Pacific/Auckland",
                                                purpose="Every minute", actor="agent:review")
        response = fx.client().post(f"/spaces/{sid}/schedule", json={
            "decision": "approve", "requested_upkeep": upkeep,
            "requested_schedule": {key: displayed[key] for key in SCHEDULE_FIELDS},
        })
        with self.subTest(boundary="REST conflict"):
            self.assertEqual(response.status_code, 409, response.json())
            self.assertEqual(response.json()["error"]["code"], "conflict")
        self.assertEqual(fx.schedules.get_schedule(sid), current)
        self.assertEqual(fx.cron.calls, [])

    def test_f02_matching_displayed_schedule_approves_exact_fields(self):
        fx = self.fx
        sid = fx.make()
        upkeep = fx.projects.bundle(sid)["manifest"]["upkeep"]
        displayed = fx.schedules.request_schedule(sid, cadence="0 7 1 * *", timezone="UTC",
                                                  purpose="Once a month", actor="agent:review")
        snapshot = {key: displayed[key] for key in SCHEDULE_FIELDS}
        response = fx.client().post(f"/spaces/{sid}/schedule", json={
            "decision": "approve", "requested_upkeep": upkeep, "requested_schedule": snapshot,
        })
        self.assertEqual(response.status_code, 200, response.json())
        approved = response.json()
        self.assertEqual(approved["status"], "active")
        self.assertEqual({key: approved[key] for key in SCHEDULE_FIELDS}, snapshot)
        job = fx.cron.jobs[approved["cron_job_id"]]
        self.assertEqual((job["schedule"], job["timezone"]), ("0 7 1 * *", "UTC"))
        self.assertEqual(len(fx.cron.jobs), 1)

    def test_f02_rest_denial_disables_schedule_without_native_job_control(self):
        fx = self.fx
        sid = fx.make()
        fx.schedules.request_schedule(sid, cadence="0 7 1 * *", timezone="UTC",
                                      purpose="Once a month", actor="agent:review")
        response = fx.client().post(f"/spaces/{sid}/schedule", json={"decision": "deny"})
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["status"], "disabled")
        self.assertIsNone(response.json()["cron_job_id"])
        self.assertEqual(fx.cron.calls, [])

    def redirect_post(self, transition):
        fx = self.fx
        sid = fx.make()
        session = fx.sessions.open_session(sid)["session"]

        def on_response(response):
            if response.status == 307:
                if transition == "close":
                    fx.sessions.close_session(session)
                elif transition == "revoke":
                    fx.grants.decide(sid, "net", "revoke")

        def observe():
            with fx.db.read() as conn:
                row = conn.execute("SELECT closed_at FROM sessions WHERE id=?", (session,)).fetchone()
                return {"closed": row["closed_at"] is not None}

        transport = fx.transport([Response(307, {"Location": "https://second.example/side-effect"}), Response()],
                                 on_response, observe)
        with patch.object(fx.net, "fetch", wraps=fx.net.fetch) as fetch:
            reply = fx.bridge.dispatch(sid, session, "net.fetch", {
                "url": "https://first.example/start", "method": "POST", "body": "demo",
            })
        return reply, transport, session, fetch.call_args

    def test_f03_bridge_passes_bound_session_to_real_net_fetch(self):
        reply, transport, session, call = self.redirect_post("none")
        self.assertTrue(reply["ok"], reply)
        self.assertEqual(len(transport.requests), 2)
        self.assertEqual(call.kwargs.get("session"), session)

    def test_f03_closed_session_prevents_redirect_post(self):
        reply, transport, _session, _call = self.redirect_post("close")
        self.assertEqual(reply["error"]["code"], "session_invalid")
        self.assertEqual([(call["host"], call["method"], call["body"], call["closed"])
                          for call in transport.requests], [("first.example", "POST", b"demo", False)])
        self.assertEqual(len(transport.connections), 1)

    def test_f03_net_revocation_prevents_redirect_post_control(self):
        reply, transport, _session, _call = self.redirect_post("revoke")
        self.assertEqual(reply["error"]["code"], "not_granted")
        self.assertEqual([(call["host"], call["method"]) for call in transport.requests],
                         [("first.example", "POST")])

    def test_f03_open_session_preserves_redirect_post_control(self):
        reply, transport, _session, _call = self.redirect_post("none")
        self.assertTrue(reply["ok"], reply)
        self.assertEqual(reply["result"]["text"], "ok")
        self.assertEqual([(call["host"], call["method"], call["body"], call["closed"])
                          for call in transport.requests], [
                              ("first.example", "POST", b"demo", False),
                              ("second.example", "POST", b"demo", False),
                          ])

    def source_revisions(self):
        fx = self.fx
        sid = fx.make()
        user = fx.records.put(sid, "items", "one", {"notes": "Keep my note"}, actor="user")
        fx.source(sid, "initial")
        old = fx.records.get(sid, "items", "one")["rev"]
        self.assertEqual(old, 2)
        fx.source(sid, "newer", old)
        current = fx.records.get(sid, "items", "one")
        self.assertEqual(current["rev"], 3)
        return sid, user, old, current

    def test_f04_stale_source_revision_conflicts_and_rolls_back_whole_batch(self):
        fx = self.fx
        sid, user, old, current = self.source_revisions()
        fx.source_ops(sid, [{"op": "put", "collection": "items", "id": "other",
                            "source": {"title": "Keep other source"}}])
        other = fx.records.get(sid, "items", "other")
        before_seq = fx.records.changes_since(sid, 0)["seq"]
        error = None
        try:
            fx.source_ops(sid, [
                {"op": "put", "collection": "items", "id": "other", "base_rev": other["rev"],
                 "source": {"title": "Must roll back"}},
                {"op": "put", "collection": "items", "id": "one", "base_rev": old,
                 "source": {"title": "stale overwrites newer"}},
            ])
        except fx.core.SpacesError as exc:
            error = exc
        final = fx.records.get(sid, "items", "one")
        with self.subTest(boundary="stale source conflict"):
            self.assertIsNotNone(error, "source-owned base_rev=2 must conflict with current rev=3")
            self.assertEqual(error.code, "conflict")
        with self.subTest(boundary="current source and metadata preserved"):
            self.assertEqual(final, current)
        with self.subTest(boundary="whole batch rollback"):
            self.assertEqual(fx.records.get(sid, "items", "other"), other)
            self.assertEqual(fx.records.changes_since(sid, 0)["seq"], before_seq)
        self.assertEqual(final["data"], user["data"])

    def test_f04_current_source_revision_preserves_user_fields_control(self):
        fx = self.fx
        sid, user, old, current = self.source_revisions()
        result = fx.source(sid, "current approved update", current["rev"])
        final = fx.records.get(sid, "items", "one")
        self.assertEqual(result, {"added": 0, "updated": 1, "unchanged": 0})
        self.assertEqual(final["source"], {"title": "current approved update"})
        self.assertEqual(final["source_meta"]["handler"], "agent")
        self.assertEqual(final["data"], user["data"])
        self.assertEqual(final["rev"], 4)

    def test_f04_stale_user_revision_still_conflicts_control(self):
        fx = self.fx
        sid, user, old, current = self.source_revisions()
        with self.assertRaises(fx.core.SpacesError) as error:
            fx.records.put(sid, "items", "one", {"notes": "stale"}, actor="agent:review", base_rev=old)
        self.assertEqual(error.exception.code, "conflict")
        self.assertEqual(fx.records.get(sid, "items", "one"), current)

    def revoke_running_schedule(self, mirror):
        fx = self.fx
        sid = fx.make()
        jid = fx.approve_schedule(sid)["cron_job_id"]
        execution = fx.cron.execution(jid)
        if mirror:
            self.assertEqual(fx.runs.list_runs(sid)[0]["status"], "running")
        fx.grants.decide(sid, "refresh", "revoke")
        history = fx.runs.list_runs(sid)
        self.assertEqual(fx.schedules.get_schedule(sid)["status"], "paused")
        self.assertFalse(fx.cron.jobs[jid]["enabled"])
        with self.subTest(boundary="native interruption"):
            self.assertEqual([call for call in fx.cron.calls if call[0] == "cancel"], [("cancel", jid)])
            self.assertEqual(execution["status"], "cancelled")
        with self.subTest(boundary="durable cancellation"):
            self.assertEqual([run["status"] for run in history], ["canceled"])

    def test_f05_revoke_discovers_unmirrored_running_execution(self):
        self.revoke_running_schedule(mirror=False)

    def test_f05_revoke_cancels_already_mirrored_execution_control(self):
        self.revoke_running_schedule(mirror=True)

    def deny_changed_schedule(self, mirror):
        fx = self.fx
        sid = fx.make()
        jid = fx.approve_schedule(sid)["cron_job_id"]
        execution = fx.cron.execution(jid, "completed")
        if mirror:
            self.assertEqual(len(fx.runs.list_runs(sid)), 1)
        requested = fx.schedules.request_schedule(sid, cadence="0 9 * * *", timezone="UTC",
                                                  purpose="Requested cadence change", actor="agent:review")
        self.assertEqual(requested["status"], "requested")
        fx.schedules.decide_schedule(sid, "deny")
        history = fx.runs.list_runs(sid)
        freshness = fx.runs.freshness(sid)
        self.assertIn(execution, fx.cron.executions)
        self.assertEqual(fx.schedules.get_schedule(sid)["status"], "disabled")
        self.assertNotIn(jid, fx.cron.jobs)
        with self.subTest(boundary="completed run history"):
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0]["detail"]["cron_run_id"], execution["id"])
            self.assertEqual(history[0]["status"], "succeeded")
        with self.subTest(boundary="last success"):
            self.assertEqual(freshness["last_success_at"], datetime.fromisoformat(execution["finished_at"]).timestamp())

    def test_f06_denial_preserves_unmirrored_completed_history(self):
        self.deny_changed_schedule(mirror=False)

    def test_f06_denial_preserves_already_mirrored_history_control(self):
        self.deny_changed_schedule(mirror=True)

    def import_history(self, count):
        fx = self.fx
        sid = fx.make()
        jid = fx.approve_schedule(sid)["cron_job_id"]
        for _ in range(count):
            fx.cron.execution(jid, "completed")
        fx.runs.list_runs(sid, limit=500)
        fx.runs.list_runs(sid, limit=500)
        with fx.db.read() as conn:
            rows = conn.execute("SELECT detail,status FROM runs WHERE space=?", (sid,)).fetchall()
        ids = [json.loads(row["detail"])["cron_run_id"] for row in rows]
        with self.subTest(boundary="durable count"):
            self.assertEqual(len(rows), count)
        with self.subTest(boundary="all execution identities"):
            self.assertEqual(set(ids), {entry["id"] for entry in fx.cron.executions})
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(row["status"] == "succeeded" for row in rows))

    def test_f07_history_backfill_includes_501st_execution(self):
        self.import_history(501)

    def test_f07_history_import_at_500_is_idempotent_control(self):
        self.import_history(500)

    def test_f08_feed_rejects_approved_loopback_before_transport(self):
        fx = self.fx
        url = "https://127.0.0.1:8443/feed"
        sid = fx.make(handler="feed", url=url)
        pinned, legacy = fx.feed_transports(b"private fixture content")
        error = None
        try:
            fx.feeds.fetch(sid, url)
        except fx.core.SpacesError as exc:
            error = exc
        with self.subTest(boundary="public address refusal"):
            self.assertIsNotNone(error, "Refresh host approval cannot allow a loopback destination")
            self.assertEqual((error.code, error.extra.get("reason")), ("blocked", "private_address"))
        with self.subTest(boundary="no private egress"):
            self.assertEqual(legacy, [])
            self.assertEqual(pinned.connections, [])

    def test_f08_public_feed_uses_vetted_pinned_destination(self):
        fx = self.fx
        sid = fx.make(handler="feed")
        fx.grants.decide(sid, "net", "revoke")
        pinned, legacy = fx.feed_transports(b"public fixture content")
        self.assertEqual(fx.feeds.fetch(sid, "https://example.org/feed"), b"public fixture content")
        self.assertEqual(pinned.connections, [("example.org", 443, PUBLIC)])
        self.assertEqual(legacy, [])
        self.assertEqual(pinned.requests[0]["headers"]["Host"], "example.org")

    def test_f08_refresh_authority_works_with_net_revoked_control(self):
        fx = self.fx
        sid = fx.make(handler="feed")
        fx.grants.decide(sid, "net", "revoke")
        pinned, legacy = fx.feed_transports(b"public fixture content")
        self.assertEqual(fx.feeds.fetch(sid, "https://example.org/feed"), b"public fixture content")
        self.assertEqual(len(pinned.requests) + len(legacy), 1)
        fx.grants.decide(sid, "refresh", "revoke")
        with self.assertRaises(fx.core.SpacesError) as error:
            fx.feeds.fetch(sid, "https://example.org/feed")
        self.assertEqual(error.exception.code, "not_granted")
        self.assertEqual(len(pinned.requests) + len(legacy), 1)

    def test_f08_mediated_net_rejects_loopback_control(self):
        fx = self.fx
        sid = fx.make(handler="feed", url="https://127.0.0.1:8443/feed")
        transport = fx.transport([Response(body=b"private fixture content")])
        with self.assertRaises(fx.core.SpacesError) as error:
            fx.net.fetch(sid, "https://127.0.0.1:8443/feed")
        self.assertEqual((error.exception.code, error.exception.extra["reason"]),
                         ("blocked", "private_address"))
        self.assertEqual(transport.connections, [])

    def test_f09_feed_approval_rechecks_separately_committed_revocation(self):
        fx = self.fx
        sid = fx.make(handler="feed")
        upkeep = fx.projects.bundle(sid)["manifest"]["upkeep"]
        fx.schedules.request_schedule(sid, cadence="0 * * * *", timezone="UTC",
                                      purpose="Demo", actor="agent:review")
        original = fx.grants.check
        transitions = []

        def revoke_after_check(*args, **kwargs):
            result = original(*args, **kwargs)
            if not transitions and args[:2] == (sid, "refresh"):
                conn = sqlite3.connect(fx.db.db_path(), isolation_level=None)
                try:
                    conn.execute("BEGIN IMMEDIATE")
                    changed = conn.execute(
                        "UPDATE grants SET status='revoked',decided_at=?,decided_by='user' "
                        "WHERE space=? AND capability='refresh'", (fx.db.now(), sid)).rowcount
                    self.assertEqual(changed, 1)
                    conn.execute("COMMIT")
                finally:
                    conn.close()
                transitions.append("revoked in separate SQLite connection")
            return result

        error = None
        with patch.object(fx.grants, "check", side_effect=revoke_after_check):
            try:
                fx.schedules.decide_schedule(sid, "approve", requested_upkeep=upkeep)
            except fx.core.SpacesError as exc:
                error = exc
        self.assertEqual(transitions, ["revoked in separate SQLite connection"])
        self.assertEqual(fx.refresh_grant(sid)["status"], "revoked")
        if error is not None:
            self.assertEqual(error.code, "not_granted")
        after_revoke = fx.schedules.get_schedule(sid)
        enabled_after_revoke = [jid for jid, job in fx.cron.jobs.items() if job["enabled"]]
        fx.approve_refresh(sid)
        after_regrant = fx.schedules.get_schedule(sid)
        with self.subTest(boundary="no activation after revoke"):
            self.assertIn(after_revoke["status"], ("requested", "paused"))
            self.assertEqual(enabled_after_revoke, [])
        with self.subTest(boundary="no automatic restart after regrant"):
            self.assertIn(after_regrant["status"], ("requested", "paused"))
            self.assertEqual([jid for jid, job in fx.cron.jobs.items() if job["enabled"]], [])

    def test_f09_active_feed_stays_paused_after_regrant_until_resume_control(self):
        fx = self.fx
        sid = fx.make(handler="feed")
        jid = fx.approve_schedule(sid)["cron_job_id"]
        fx.grants.decide(sid, "refresh", "revoke")
        self.assertEqual(fx.schedules.get_schedule(sid)["status"], "paused")
        self.assertFalse(fx.cron.jobs[jid]["enabled"])
        fx.approve_refresh(sid)
        self.assertEqual(fx.schedules.get_schedule(sid)["status"], "paused")
        self.assertFalse(fx.cron.jobs[jid]["enabled"])
        fx.schedules.pause_schedule(sid, False, actor="user")
        self.assertEqual(fx.schedules.get_schedule(sid)["status"], "active")
        self.assertTrue(fx.cron.jobs[jid]["enabled"])


if __name__ == "__main__":
    unittest.main()
