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



    def test_r01_missing_upkeep_snapshot_refuses_agent_and_feed_rest_approval(self):
        fx = self.fx
        client = fx.client()
        for handler in ("agent", "feed"):
            with self.subTest(handler=handler):
                sid = fx.make(handler=handler)
                grant = fx.refresh_grant(sid)
                self.assertEqual(grant["status"], "granted")
                self.assertEqual(grant["scope"], grant["requested_scope"])
                if handler == "agent":
                    self.assertEqual(grant["scope"]["upkeep"],
                                     {"handler": "agent", "prompt": AGENT_PROMPT})
                displayed = fx.schedules.request_schedule(
                    sid, cadence="0 7 1 * *", timezone="UTC",
                    purpose="Monthly approved task", actor="agent:review")
                snapshot = {key: displayed[key] for key in SCHEDULE_FIELDS}
                jobs_before = copy.deepcopy(fx.cron.jobs)
                calls_before = list(fx.cron.calls)
                response = client.post(f"/spaces/{sid}/schedule", json={
                    "decision": "approve", "requested_schedule": snapshot,
                })
                with self.subTest(boundary="missing upkeep rejected at REST"):
                    self.assertEqual(response.status_code, 400, response.text)
                    self.assertEqual(response.json()["error"]["code"], "invalid")
                with self.subTest(boundary="no native creation"):
                    self.assertEqual(fx.cron.calls, calls_before)
                    self.assertEqual(fx.cron.jobs, jobs_before)
                with self.subTest(boundary="request remains unapproved"):
                    with fx.db.read() as conn:
                        stored = dict(conn.execute(
                            "SELECT * FROM schedules WHERE space=?", (sid,)).fetchone())
                    self.assertEqual(stored["status"], "requested")
                    self.assertIsNone(stored["cron_job_id"])
                    self.assertEqual({key: stored[key] for key in SCHEDULE_FIELDS}, snapshot)

    def test_r01_matching_upkeep_and_schedule_approve_one_native_job_control(self):
        fx = self.fx
        client = fx.client()
        for handler in ("agent", "feed"):
            with self.subTest(handler=handler):
                sid = fx.make(handler=handler)
                upkeep = copy.deepcopy(fx.projects.bundle(sid)["manifest"]["upkeep"])
                grant = copy.deepcopy(fx.refresh_grant(sid))
                displayed = fx.schedules.request_schedule(
                    sid, cadence="0 7 1 * *", timezone="Pacific/Auckland",
                    purpose="Monthly displayed task", actor="agent:review")
                snapshot = {key: displayed[key] for key in SCHEDULE_FIELDS}
                jobs_before = set(fx.cron.jobs)
                call_start = len(fx.cron.calls)
                response = client.post(f"/spaces/{sid}/schedule", json={
                    "decision": "approve", "requested_upkeep": upkeep,
                    "requested_schedule": snapshot,
                })
                self.assertEqual(response.status_code, 200, response.text)
                approved = response.json()
                self.assertEqual(approved["status"], "active")
                self.assertEqual({key: approved[key] for key in SCHEDULE_FIELDS}, snapshot)
                jid = approved["cron_job_id"]
                self.assertEqual(set(fx.cron.jobs) - jobs_before, {jid})
                self.assertEqual([call for call in fx.cron.calls[call_start:]
                                  if call[0] == "create"], [("create", jid)])
                job = fx.cron.jobs[jid]
                self.assertTrue(job["enabled"])
                self.assertEqual((job["schedule"], job["timezone"]),
                                 (snapshot["cadence"], snapshot["timezone"]))
                self.assertEqual(job["no_agent"], handler == "feed")
                if handler == "agent":
                    self.assertTrue(job["prompt"].endswith("Upkeep task:\n" + upkeep["prompt"]))
                else:
                    self.assertEqual(job["script"], f"living-spaces-refresh-{sid}.py")
                self.assertEqual(fx.projects.bundle(sid)["manifest"]["upkeep"], upkeep)
                self.assertEqual(fx.refresh_grant(sid), grant)
                self.assertEqual({key: fx.schedules.get_schedule(sid)[key]
                                  for key in SCHEDULE_FIELDS}, snapshot)

    def test_r01_denial_needs_neither_snapshot_and_creates_no_job_control(self):
        fx = self.fx
        client = fx.client()
        for handler in ("agent", "feed"):
            with self.subTest(handler=handler):
                sid = fx.make(handler=handler)
                displayed = fx.schedules.request_schedule(
                    sid, cadence="0 7 1 * *", timezone="UTC",
                    purpose="Optional monthly upkeep", actor="agent:review")
                jobs_before = copy.deepcopy(fx.cron.jobs)
                calls_before = list(fx.cron.calls)
                response = client.post(f"/spaces/{sid}/schedule", json={"decision": "deny"})
                self.assertEqual(response.status_code, 200, response.text)
                denied = response.json()
                self.assertEqual(denied["status"], "disabled")
                self.assertIsNone(denied["cron_job_id"])
                self.assertIsNone(denied["next_run_at"])
                self.assertEqual({key: denied[key] for key in SCHEDULE_FIELDS},
                                 {key: displayed[key] for key in SCHEDULE_FIELDS})
                self.assertEqual(fx.schedules.get_schedule(sid)["status"], "disabled")
                self.assertEqual(fx.cron.jobs, jobs_before)
                self.assertEqual(fx.cron.calls, calls_before)

    def test_r02_unavailable_adapter_revoke_without_pending_runs_succeeds_at_rest(self):
        from fastapi.testclient import TestClient

        fx = self.fx
        sid = fx.make()
        jid = fx.approve_schedule(sid)["cron_job_id"]
        client = self.stack.enter_context(TestClient(fx.client().app, raise_server_exceptions=False))
        with fx.db.read() as conn:
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM runs WHERE space=? AND status IN ('queued','running')",
                (sid,)).fetchone()[0], 0)
        self.assertTrue(fx.cron.jobs[jid]["enabled"])
        jobs_before = copy.deepcopy(fx.cron.jobs)
        calls_before = list(fx.cron.calls)
        with patch.object(fx.schedules, "_cron", side_effect=ImportError("native adapter unavailable")):
            response = client.post(f"/spaces/{sid}/grants/refresh", json={"decision": "revoke"})
            with fx.db.read() as conn:
                stored = dict(conn.execute(
                    "SELECT * FROM schedules WHERE space=?", (sid,)).fetchone())
            visible = fx.schedules._schedule_row(sid)
            with self.subTest(boundary="REST revoke succeeds"):
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["status"], "revoked")
            with self.subTest(boundary="Refresh durably revoked"):
                self.assertEqual(fx.refresh_grant(sid)["status"], "revoked")
            with self.subTest(boundary="inactive before any reconciling read"):
                self.assertIn(stored["status"], ("disabled", "paused", "requested"))
                self.assertIsNone(stored["next_run_at"])
            with self.subTest(boundary="unconfirmed native interruption is visible"):
                self.assertIn("unavailable", (visible.get("reason") or "").lower())
            with self.subTest(boundary="no fabricated native acknowledgement"):
                self.assertEqual(fx.cron.calls, calls_before)
                self.assertEqual(fx.cron.jobs, jobs_before)
                for event in fx.grants.audit_log(sid):
                    if event["action"] == "schedule.paused" and event["outcome"] == "paused":
                        self.assertIn("unavailable", json.dumps(event["detail"]).lower())

    def test_r02_restored_adapter_interrupts_native_job_before_refresh_regrant(self):
        from fastapi.testclient import TestClient

        fx = self.fx
        sid = fx.make()
        jid = fx.approve_schedule(sid)["cron_job_id"]
        client = self.stack.enter_context(TestClient(fx.client().app, raise_server_exceptions=False))
        calls_before = list(fx.cron.calls)
        with patch.object(fx.schedules, "_cron", side_effect=ImportError("native adapter unavailable")):
            response = client.post(f"/spaces/{sid}/grants/refresh", json={"decision": "revoke"})
        self.assertEqual(fx.refresh_grant(sid)["status"], "revoked")
        self.assertTrue(fx.cron.jobs[jid]["enabled"])
        self.assertEqual(fx.cron.calls, calls_before)
        interruptions = []
        pause, remove = fx.cron.pause_job, fx.cron.remove_job

        def observe_interruption(native_call, job_id, *args, **kwargs):
            result = native_call(job_id, *args, **kwargs)
            if job_id == jid:
                interruptions.append((fx.refresh_grant(sid)["status"],
                                      copy.deepcopy(fx.cron.jobs.get(jid))))
            return result

        with patch.object(fx.cron, "pause_job",
                          side_effect=lambda *args, **kwargs: observe_interruption(pause, *args, **kwargs)), \
                patch.object(fx.cron, "remove_job",
                             side_effect=lambda *args, **kwargs: observe_interruption(remove, *args, **kwargs)):
            granted = fx.approve_refresh(sid)
        with self.subTest(boundary="revoke returns success"):
            self.assertEqual(response.status_code, 200, response.text)
        with self.subTest(boundary="restored adapter permits safe regrant"):
            self.assertEqual(granted["status"], "granted")
            self.assertEqual(fx.refresh_grant(sid)["status"], "granted")
        with self.subTest(boundary="native interruption precedes durable grant"):
            self.assertTrue(interruptions, "Regrant must resolve the enabled native job")
            status, job = interruptions[0]
            self.assertEqual(status, "revoked")
            if job is not None:
                self.assertFalse(job["enabled"])
                self.assertEqual(job["state"], "paused")
        with self.subTest(boundary="native job cannot remain enabled"):
            job = fx.cron.jobs.get(jid)
            if job is not None:
                self.assertFalse(job["enabled"])
                self.assertEqual(job["state"], "paused")
            self.assertTrue(any(call[0] in ("pause", "remove") and call[1] == jid
                                for call in fx.cron.calls[len(calls_before):]))
        with self.subTest(boundary="regrant does not resume or create"):
            self.assertEqual([call for call in fx.cron.calls[len(calls_before):]
                              if call[0] in ("create", "resume", "trigger")], [])
        with self.subTest(boundary="schedule awaits explicit approval or Resume"):
            with fx.db.read() as conn:
                stored = dict(conn.execute(
                    "SELECT * FROM schedules WHERE space=?", (sid,)).fetchone())
            self.assertIn(stored["status"], ("disabled", "paused", "requested"))
            self.assertIsNone(stored["next_run_at"])
            self.assertIn(fx.schedules.get_schedule(sid)["status"],
                          ("disabled", "paused", "requested"))

    def test_r02_unavailable_adapter_keeps_refresh_regrant_fail_closed(self):
        from fastapi.testclient import TestClient

        fx = self.fx
        sid = fx.make()
        fx.approve_schedule(sid)
        client = self.stack.enter_context(TestClient(fx.client().app, raise_server_exceptions=False))
        jobs_before = copy.deepcopy(fx.cron.jobs)
        calls_before = list(fx.cron.calls)
        with patch.object(fx.schedules, "_cron", side_effect=ImportError("native adapter unavailable")):
            response = client.post(f"/spaces/{sid}/grants/refresh", json={"decision": "revoke"})
            self.assertEqual(fx.refresh_grant(sid)["status"], "revoked")
            with self.subTest(boundary="typed refusal while interruption is unavailable"):
                with self.assertRaises(fx.core.SpacesError):
                    fx.approve_refresh(sid)
            with self.subTest(boundary="Refresh stays revoked"):
                self.assertEqual(fx.refresh_grant(sid)["status"], "revoked")
            with self.subTest(boundary="revoke succeeds despite unavailable adapter"):
                self.assertEqual(response.status_code, 200, response.text)
            with self.subTest(boundary="inactive schedule retains visible unavailable reason"):
                with fx.db.read() as conn:
                    stored = dict(conn.execute(
                        "SELECT * FROM schedules WHERE space=?", (sid,)).fetchone())
                self.assertIn(stored["status"], ("disabled", "paused", "requested"))
                self.assertIsNone(stored["next_run_at"])
                self.assertIn("unavailable",
                              (fx.schedules._schedule_row(sid).get("reason") or "").lower())
            with self.subTest(boundary="no fabricated native interruption or restart"):
                self.assertEqual(fx.cron.jobs, jobs_before)
                self.assertEqual(fx.cron.calls, calls_before)

    def test_r02_unavailable_adapter_preserves_pending_run_uncertainty_and_gates_regrant(self):
        from fastapi.testclient import TestClient

        fx = self.fx
        client = self.stack.enter_context(TestClient(fx.client().app, raise_server_exceptions=False))
        for native_status, local_status in (("claimed", "queued"), ("running", "running")):
            with self.subTest(native_status=native_status):
                sid = fx.make()
                jid = fx.approve_schedule(sid)["cron_job_id"]
                execution = fx.cron.execution(jid, native_status)
                pending = fx.runs.list_runs(sid)
                self.assertEqual(len(pending), 1)
                self.assertEqual(pending[0]["status"], local_status)
                self.assertEqual(pending[0]["detail"]["cron_run_id"], execution["id"])
                rid = pending[0]["id"]
                jobs_before = copy.deepcopy(fx.cron.jobs)
                executions_before = copy.deepcopy(fx.cron.executions)
                calls_before = list(fx.cron.calls)
                with patch.object(fx.schedules, "_cron", side_effect=ImportError("native adapter unavailable")):
                    response = client.post(f"/spaces/{sid}/grants/refresh", json={"decision": "revoke"})
                    with fx.db.read() as conn:
                        stored = dict(conn.execute(
                            "SELECT * FROM schedules WHERE space=?", (sid,)).fetchone())
                        run = dict(conn.execute("SELECT * FROM runs WHERE id=?", (rid,)).fetchone())
                    visible = fx.schedules._schedule_row(sid)
                    with self.subTest(boundary="revoke persists and returns successfully"):
                        self.assertEqual(fx.refresh_grant(sid)["status"], "revoked")
                        self.assertEqual(response.status_code, 200, response.text)
                        self.assertEqual(response.json()["status"], "revoked")
                    with self.subTest(boundary="inactive schedule without a getter repair"):
                        self.assertIn(stored["status"], ("disabled", "paused", "requested"))
                        self.assertIsNone(stored["next_run_at"])
                    with self.subTest(boundary="pending work is not falsely canceled"):
                        self.assertIn(run["status"], ("queued", "running", "failed", "blocked"))
                        self.assertEqual(json.loads(run["detail"])["cron_run_id"], execution["id"])
                    with self.subTest(boundary="interruption failure or uncertainty is visible"):
                        detail = json.dumps({"error": run["error"], "detail": json.loads(run["detail"]),
                                             "reason": visible.get("reason")}).lower()
                        self.assertRegex(detail, r"unavailable|unconfirmed|uncertain|cannot|could not|failed")
                    with self.subTest(boundary="regrant is a typed refusal"):
                        with self.assertRaises(fx.core.SpacesError):
                            fx.approve_refresh(sid)
                    with self.subTest(boundary="Refresh remains revoked"):
                        self.assertEqual(fx.refresh_grant(sid)["status"], "revoked")
                    with self.subTest(boundary="native leaves report no successful interruption"):
                        self.assertEqual(fx.cron.jobs, jobs_before)
                        self.assertEqual(fx.cron.executions, executions_before)
                        self.assertEqual(fx.cron.calls, calls_before)

    def test_r02_working_adapter_revoke_and_regrant_preserve_unrelated_state_control(self):
        fx = self.fx
        sid = fx.make()
        jid = fx.approve_schedule(sid)["cron_job_id"]
        completed = fx.cron.execution(jid, "completed")
        running = fx.cron.execution(jid)
        history_before = {run["detail"]["cron_run_id"]: run for run in fx.runs.list_runs(sid)}
        other_sid = fx.make()
        other_jid = fx.approve_schedule(other_sid)["cron_job_id"]
        other_execution = fx.cron.execution(other_jid)
        other_history = fx.runs.list_runs(other_sid)
        other_schedule = fx.schedules.get_schedule(other_sid)
        other_grant = fx.refresh_grant(other_sid)
        other_job = copy.deepcopy(fx.cron.jobs[other_jid])
        other_native_run = copy.deepcopy(other_execution)
        user_record = fx.records.put(
            sid, "items", "keep", {"notes": "Existing user data"}, actor="user")
        call_start = len(fx.cron.calls)
        response = fx.client().post(f"/spaces/{sid}/grants/refresh", json={"decision": "revoke"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "revoked")
        self.assertEqual(fx.refresh_grant(sid)["status"], "revoked")
        self.assertEqual(fx.schedules.get_schedule(sid)["status"], "paused")
        self.assertFalse(fx.cron.jobs[jid]["enabled"])
        self.assertEqual(fx.cron.jobs[jid]["state"], "paused")
        self.assertEqual(running["status"], "cancelled")
        self.assertIn(("pause", jid), fx.cron.calls[call_start:])
        self.assertIn(("cancel", jid), fx.cron.calls[call_start:])
        history = {run["detail"]["cron_run_id"]: run for run in fx.runs.list_runs(sid)}
        self.assertEqual(history[running["id"]]["status"], "canceled")
        self.assertEqual(history[completed["id"]], history_before[completed["id"]])
        call_regrant = len(fx.cron.calls)
        self.assertEqual(fx.approve_refresh(sid)["status"], "granted")
        self.assertEqual(fx.schedules.get_schedule(sid)["status"], "paused")
        self.assertFalse(fx.cron.jobs[jid]["enabled"])
        self.assertEqual(running["status"], "cancelled")
        self.assertEqual([call for call in fx.cron.calls[call_regrant:]
                          if call[0] in ("create", "resume", "trigger")], [])
        self.assertEqual([call for call in fx.cron.calls[call_start:] if call[0] == "remove"], [])
        self.assertEqual(fx.cron.jobs[other_jid], other_job)
        self.assertEqual(other_execution, other_native_run)
        self.assertEqual(fx.runs.list_runs(other_sid), other_history)
        self.assertEqual(fx.schedules.get_schedule(other_sid), other_schedule)
        self.assertEqual(fx.refresh_grant(other_sid), other_grant)
        self.assertEqual(fx.records.get(sid, "items", "keep"), user_record)
        self.assertIn(completed, fx.cron.executions)
        self.assertIn(running, fx.cron.executions)
        self.assertEqual([call for call in fx.cron.calls[call_start:] if call[1] == other_jid], [])
        fx.schedules.pause_schedule(sid, False, actor="user")
        self.assertTrue(fx.cron.jobs[jid]["enabled"])
        self.assertEqual(fx.schedules.get_schedule(sid)["status"], "active")

    def test_r02_removed_unstarted_one_shot_allows_regrant_but_running_ack_does_not(self):
        for native_state in ("unstarted", "running"):
            with self.subTest(native_state=native_state), ExitStack() as stack:
                fx = CustomizationFixture(stack)
                try:
                    sid = fx.make()
                    other_sid = fx.make()
                    other_jid = fx.approve_schedule(other_sid)["cron_job_id"]
                except fx.core.SpacesError as error:
                    self.fail(f"Initial exact approval must succeed: {error.to_dict()}")
                other_execution = fx.cron.execution(other_jid)
                other_job = copy.deepcopy(fx.cron.jobs[other_jid])
                other_native = copy.deepcopy(other_execution)
                run = fx.runs.start_refresh(sid, trigger="manual", actor="user")
                self.assertEqual(run["status"], "queued")
                self.assertTrue(run["detail"]["one_shot"])
                jid = run["detail"]["cron_job_id"]
                self.assertIsNone(fx.cron.jobs[jid].get("fire_claim"))
                self.assertIsNone(fx.cron.jobs[jid].get("run_claim"))
                self.assertEqual(fx.cron.list_executions(job_id=jid), [])
                if native_state == "running":
                    execution = fx.cron.execution(jid)
                    claimed_at = datetime.fromtimestamp(run["queued_at"] + 1).astimezone().isoformat()
                    execution.update(claimed_at=claimed_at, started_at=claimed_at)
                    self.assertEqual(fx.runs.get_run(run["id"])["status"], "running")
                    execution_before = copy.deepcopy(execution)
                call_start = len(fx.cron.calls)
                with patch.object(fx.cron, "cancel_job_run", return_value=True) as cancel:
                    revoked = fx.grants.decide(sid, "refresh", "revoke")
                    self.assertEqual(revoked["status"], "revoked")
                    self.assertNotIn(jid, fx.cron.jobs)
                    self.assertIn(("remove", jid), fx.cron.calls[call_start:])
                    cancel.assert_any_call(jid, reason=unittest.mock.ANY)
                    if native_state == "running":
                        self.assertEqual(execution, execution_before)
                        with self.assertRaises(fx.core.SpacesError) as refused:
                            fx.approve_refresh(sid)
                        self.assertEqual(refused.exception.code, "blocked")
                        self.assertEqual(refused.exception.message,
                                         "Cannot grant Refresh until native interruption is confirmed")
                        self.assertEqual(fx.refresh_grant(sid)["status"], "revoked")
                        self.assertEqual(execution, execution_before)
                        self.assertEqual([call for call in fx.cron.calls[call_start:]
                                          if call[0] in ("create", "resume", "trigger")], [])
                        execution.update(status="completed", started_at=execution["claimed_at"],
                                         finished_at=execution["claimed_at"], error=None)
                    with self.subTest(boundary="exact reapproval succeeds"):
                        try:
                            approved = fx.approve_refresh(sid)
                        except fx.core.SpacesError as error:
                            self.fail(f"Exact Refresh reapproval must succeed: {error.to_dict()}")
                        self.assertEqual(approved["status"], "granted")
                        self.assertEqual(fx.refresh_grant(sid)["status"], "granted")
                    with self.subTest(boundary="withdrawn descriptor no longer blocks"):
                        withdrawn = fx.runs.get_run(run["id"])
                        self.assertNotIn(withdrawn["status"], ("queued", "running"))
                        self.assertIsNotNone(withdrawn["ended_at"])
                        self.assertTrue(withdrawn["detail"].get("cancel_reason"))
                    with self.subTest(boundary="approval admits no work"):
                        self.assertNotIn(jid, fx.cron.jobs)
                        self.assertIsNone(fx.schedules.get_schedule(sid))
                        self.assertEqual([call for call in fx.cron.calls[call_start:]
                                          if call[0] in ("create", "resume", "trigger")], [])
                        with fx.db.read() as conn:
                            self.assertEqual(conn.execute(
                                "SELECT COUNT(*) FROM runs WHERE space=?", (sid,)).fetchone()[0], 1)
                        if native_state == "unstarted":
                            self.assertEqual(fx.cron.list_executions(job_id=jid), [])
                    with self.subTest(boundary="unrelated authority survives"):
                        self.assertEqual(fx.cron.jobs[other_jid], other_job)
                        self.assertEqual(other_execution, other_native)
                        self.assertEqual(fx.refresh_grant(other_sid)["status"], "granted")
                        self.assertEqual([call for call in fx.cron.calls[call_start:]
                                          if call[1] == other_jid], [])

    def test_r02_terminal_history_regrant_covers_pages_and_rejects_uncertain_ledger(self):
        cases = (("short", 2), ("full", 501), ("unknown", 2),
                 ("malformed", 2), ("inaccessible", 2))
        for evidence, count in cases:
            with self.subTest(evidence=evidence), ExitStack() as stack:
                fx = CustomizationFixture(stack)
                try:
                    sid = fx.make()
                    jid = fx.approve_schedule(sid)["cron_job_id"]
                except fx.core.SpacesError as error:
                    self.fail(f"Initial exact approval must succeed: {error.to_dict()}")
                entries = [fx.cron.execution(jid, "completed") for _ in range(count)]
                stamps = [entry["claimed_at"] for entry in entries]
                self.assertEqual(stamps, sorted(set(stamps)))
                self.assertTrue(all(entry["finished_at"] is not None for entry in entries))
                native_before = copy.deepcopy(entries)
                call_start = len(fx.cron.calls)
                with patch.object(fx.cron, "cancel_job_run", return_value=True):
                    with ExitStack() as ledger_fault:
                        if evidence == "unknown":
                            ledger_fault.enter_context(patch.dict(entries[0], status="unknown"))
                        elif evidence == "malformed":
                            ledger_fault.enter_context(patch.dict(entries[0], finished_at="not-a-timestamp"))
                        elif evidence == "inaccessible":
                            ledger_fault.enter_context(patch(
                                "cron.executions.list_executions",
                                side_effect=OSError("native ledger unavailable")))
                        revoked = fx.grants.decide(sid, "refresh", "revoke")
                        self.assertEqual(revoked["status"], "revoked")
                        if evidence in ("malformed", "inaccessible"):
                            with self.assertRaises(fx.core.SpacesError) as refused:
                                fx.approve_refresh(sid)
                            self.assertEqual(refused.exception.code, "blocked")
                            self.assertEqual(refused.exception.message,
                                             "Cannot grant Refresh until native interruption is confirmed")
                            self.assertEqual(fx.refresh_grant(sid)["status"], "revoked")
                            self.assertIn(fx.schedules.get_schedule(sid)["status"], ("paused", "disabled"))
                            self.assertIsNone(fx.schedules.get_schedule(sid)["next_run_at"])
                            self.assertFalse(fx.cron.jobs[jid]["enabled"])
                            self.assertEqual(fx.cron.jobs[jid]["state"], "paused")
                            self.assertEqual([call for call in fx.cron.calls[call_start:]
                                              if call[0] in ("create", "resume", "trigger")], [])
                    self.assertEqual(entries, native_before)
                    regrant_start = len(fx.cron.calls)
                    with self.subTest(boundary="complete terminal history permits approval"):
                        try:
                            approved = fx.approve_refresh(sid)
                        except fx.core.SpacesError as error:
                            self.fail(f"Complete terminal history must permit reapproval: {error.to_dict()}")
                        self.assertEqual(approved["status"], "granted")
                        self.assertEqual(fx.refresh_grant(sid)["status"], "granted")
                    with self.subTest(boundary="every completed execution is reconciled"):
                        with fx.db.read() as conn:
                            history = conn.execute(
                                "SELECT status,detail,ended_at FROM runs WHERE space=?", (sid,)).fetchall()
                        self.assertEqual(len(history), count)
                        self.assertEqual({json.loads(row["detail"])["cron_run_id"] for row in history},
                                         {entry["id"] for entry in entries})
                        self.assertTrue(all(row["status"] == "succeeded" and row["ended_at"] is not None
                                            for row in history))
                    with self.subTest(boundary="consent does not restart schedule"):
                        schedule = fx.schedules.get_schedule(sid)
                        self.assertIn(schedule["status"], ("paused", "disabled"))
                        self.assertIsNone(schedule["next_run_at"])
                        self.assertFalse(fx.cron.jobs[jid]["enabled"])
                        self.assertEqual(fx.cron.jobs[jid]["state"], "paused")
                        self.assertIsNone(fx.cron.jobs[jid].get("fire_claim"))
                        self.assertIsNone(fx.cron.jobs[jid].get("run_claim"))
                        self.assertEqual([call for call in fx.cron.calls[regrant_start:]
                                          if call[0] in ("create", "resume", "trigger")], [])
                        self.assertEqual(entries, native_before)

    def test_r02_older_running_execution_beyond_full_page_blocks_until_terminal(self):
        fx = self.fx
        try:
            sid = fx.make()
            jid = fx.approve_schedule(sid)["cron_job_id"]
            other_sid = fx.make()
            other_jid = fx.approve_schedule(other_sid)["cron_job_id"]
        except fx.core.SpacesError as error:
            self.fail(f"Initial exact approval must succeed: {error.to_dict()}")
        other_execution = fx.cron.execution(other_jid)
        other_bytes = json.dumps({"job": fx.cron.jobs[other_jid], "execution": other_execution},
                                sort_keys=True).encode()
        older = fx.cron.execution(jid)
        newer = [fx.cron.execution(jid, "completed") for _ in range(501)]
        older_before = copy.deepcopy(older)
        newer_before = copy.deepcopy(newer)
        self.assertTrue(all(entry["claimed_at"] > older["claimed_at"] for entry in newer))
        self.assertEqual(len({entry["claimed_at"] for entry in newer}), 501)
        self.assertNotIn(older, fx.cron.list_executions(job_id=jid, limit=500))
        call_start = len(fx.cron.calls)
        with patch.object(fx.cron, "cancel_job_run", return_value=True) as cancel:
            revoked = fx.grants.decide(sid, "refresh", "revoke")
            self.assertEqual(revoked["status"], "revoked")
            cancel.assert_any_call(jid, reason=unittest.mock.ANY)
            self.assertEqual(older, older_before)
            with self.assertRaises(fx.core.SpacesError) as refused:
                fx.approve_refresh(sid)
            self.assertEqual(refused.exception.code, "blocked")
            self.assertEqual(refused.exception.message,
                             "Cannot grant Refresh until native interruption is confirmed")
            self.assertEqual(fx.refresh_grant(sid)["status"], "revoked")
            self.assertEqual(older, older_before)
            with self.subTest(boundary="pagination discovers older live execution"):
                with fx.db.read() as conn:
                    history = conn.execute("SELECT status,detail FROM runs WHERE space=?", (sid,)).fetchall()
                self.assertEqual(len(history), 502)
                statuses = {json.loads(row["detail"])["cron_run_id"]: row["status"] for row in history}
                self.assertEqual(statuses[older["id"]], "running")
                self.assertTrue(all(statuses[entry["id"]] == "succeeded" for entry in newer))
            with self.subTest(boundary="refusal keeps schedule fenced"):
                schedule = fx.schedules.get_schedule(sid)
                self.assertIn(schedule["status"], ("paused", "disabled"))
                self.assertIsNone(schedule["next_run_at"])
                self.assertFalse(fx.cron.jobs[jid]["enabled"])
                self.assertEqual(fx.cron.jobs[jid]["state"], "paused")
                self.assertEqual([call for call in fx.cron.calls[call_start:]
                                  if call[0] in ("create", "resume", "trigger")], [])
            older.update(status="completed", started_at=older["claimed_at"],
                         finished_at=newer[-1]["finished_at"], error=None)
            regrant_start = len(fx.cron.calls)
            with self.subTest(boundary="terminal completion permits exact approval"):
                try:
                    approved = fx.approve_refresh(sid)
                except fx.core.SpacesError as error:
                    self.fail(f"Terminal completion must permit reapproval: {error.to_dict()}")
                self.assertEqual(approved["status"], "granted")
                self.assertEqual(fx.refresh_grant(sid)["status"], "granted")
            with self.subTest(boundary="terminal history reconciled without restart"):
                with fx.db.read() as conn:
                    history = conn.execute(
                        "SELECT status,detail,ended_at FROM runs WHERE space=?", (sid,)).fetchall()
                self.assertEqual(len(history), 502)
                self.assertEqual({json.loads(row["detail"])["cron_run_id"] for row in history},
                                 {older["id"]} | {entry["id"] for entry in newer})
                self.assertTrue(all(row["status"] == "succeeded" and row["ended_at"] is not None
                                    for row in history))
                schedule = fx.schedules.get_schedule(sid)
                self.assertIn(schedule["status"], ("paused", "disabled"))
                self.assertIsNone(schedule["next_run_at"])
                self.assertFalse(fx.cron.jobs[jid]["enabled"])
                self.assertEqual(fx.cron.jobs[jid]["state"], "paused")
                self.assertEqual([call for call in fx.cron.calls[regrant_start:]
                                  if call[0] in ("create", "resume", "trigger")], [])
            with self.subTest(boundary="unrelated native bytes survive"):
                self.assertEqual(json.dumps({"job": fx.cron.jobs[other_jid], "execution": other_execution},
                                            sort_keys=True).encode(), other_bytes)
                self.assertEqual(newer, newer_before)
                self.assertEqual([call for call in fx.cron.calls[call_start:] if call[1] == other_jid], [])

    def test_r03_superseded_schedules_require_fresh_schedule_approval(self):
        fx = self.fx
        control = fx.make()
        control_jid = fx.approve_schedule(control)["cron_job_id"]
        self.assertEqual(fx.schedules.get_schedule(control)["status"], "active")
        fx.grants.decide(control, "refresh", "revoke")
        fx.approve_refresh(control)
        self.assertEqual(fx.schedules.get_schedule(control)["status"], "paused")
        self.assertFalse(fx.cron.jobs[control_jid]["enabled"])
        fx.schedules.pause_schedule(control, False, actor="user")
        self.assertEqual(fx.schedules.get_schedule(control)["status"], "active")
        self.assertTrue(fx.cron.jobs[control_jid]["enabled"])
        self.assertTrue(fx.cron.jobs[control_jid]["prompt"].endswith(AGENT_PROMPT))

        for transition in ("prompt_refresh_approval", "cadence_revoke_regrant", "prompt_archive_unarchive"):
            with self.subTest(transition=transition):
                sid = fx.make()
                old_jid = fx.approve_schedule(sid)["cron_job_id"]
                upkeep = {"handler": "agent", "prompt": AGENT_PROMPT}
                if transition == "cadence_revoke_regrant":
                    displayed = fx.schedules.request_schedule(
                        sid, cadence="*/5 * * * *", timezone="Asia/Tokyo",
                        purpose="New five-minute task", actor="agent:review")
                else:
                    upkeep = {"handler": "agent", "prompt": "Maintain only the newly approved public records."}
                    fx.change_upkeep(sid, upkeep)
                    displayed = fx.schedules.get_schedule(sid)
                snapshot = {key: displayed[key] for key in SCHEDULE_FIELDS}
                self.assertEqual(displayed["status"], "requested")
                self.assertFalse(fx.cron.jobs[old_jid]["enabled"])
                if transition == "cadence_revoke_regrant":
                    fx.grants.decide(sid, "refresh", "revoke")
                    with self.subTest(boundary="withdrawal preserves missing schedule approval"):
                        self.assertEqual(fx.schedules.get_schedule(sid)["status"], "requested")
                elif transition == "prompt_archive_unarchive":
                    self.assertEqual(fx.projects.set_status(sid, "archived", actor="user")["status"], "archived")
                    with self.subTest(boundary="archive preserves missing schedule approval"):
                        self.assertEqual(fx.schedules.get_schedule(sid)["status"], "requested")
                    self.assertEqual(fx.projects.set_status(sid, "active", actor="user")["status"], "active")
                    with self.subTest(boundary="unarchive preserves missing schedule approval"):
                        self.assertEqual(fx.schedules.get_schedule(sid)["status"], "requested")
                fx.approve_refresh(sid)
                with self.subTest(boundary="Refresh approval is not schedule approval"):
                    self.assertEqual(fx.schedules.get_schedule(sid)["status"], "requested")
                with self.subTest(boundary="Resume requires fresh schedule approval"):
                    with self.assertRaises(fx.core.SpacesError) as refused:
                        fx.schedules.pause_schedule(sid, False, actor="user")
                    self.assertEqual(refused.exception.code, "blocked")
                with self.subTest(boundary="refused Resume cannot enable native work"):
                    self.assertFalse(any(job["enabled"] for job in fx.cron.jobs.values()
                                         if job.get("name") == f"living-spaces:{sid}"))
                    self.assertEqual(fx.schedules.get_schedule(sid)["status"], "requested")
                approved = fx.schedules.decide_schedule(
                    sid, "approve", requested_upkeep=copy.deepcopy(upkeep),
                    requested_schedule=copy.deepcopy(snapshot))
                with self.subTest(boundary="fresh approval replaces the superseded job"):
                    self.assertNotEqual(approved["cron_job_id"], old_jid)
                    if old_jid in fx.cron.jobs:
                        self.assertFalse(fx.cron.jobs[old_jid]["enabled"])
                with self.subTest(boundary="fresh approval creates the displayed native task"):
                    self.assertEqual(approved["status"], "active")
                    self.assertEqual({key: approved[key] for key in SCHEDULE_FIELDS}, snapshot)
                    job = fx.cron.jobs[approved["cron_job_id"]]
                    self.assertTrue(job["enabled"])
                    self.assertFalse(job["no_agent"])
                    self.assertTrue(job["prompt"].endswith("Upkeep task:\n" + upkeep["prompt"]))
                    self.assertEqual((job["schedule"], job["timezone"]),
                                     (snapshot["cadence"], snapshot["timezone"]))
                    self.assertEqual([jid for jid, native in fx.cron.jobs.items()
                                      if native.get("name") == f"living-spaces:{sid}" and native["enabled"]],
                                     [approved["cron_job_id"]])

    def test_r03_failed_native_pause_is_retried_by_ordinary_reads(self):
        fx = self.fx
        control = fx.make()
        control_jid = fx.approve_schedule(control)["cron_job_id"]
        fx.grants.decide(control, "refresh", "revoke")
        self.assertEqual(fx.refresh_grant(control)["status"], "revoked")
        self.assertFalse(fx.cron.jobs[control_jid]["enabled"])

        sid = fx.make()
        jid = fx.approve_schedule(sid)["cron_job_id"]
        self.assertTrue(fx.cron.jobs[jid]["enabled"])
        pause = fx.cron.pause_job
        failed = False

        def fail_once(job_id, *args, **kwargs):
            nonlocal failed
            if not failed:
                failed = True
                raise OSError("Transient native pause failure")
            return pause(job_id, *args, **kwargs)

        with patch.object(fx.cron, "pause_job", side_effect=fail_once):
            revoked = fx.grants.decide(sid, "refresh", "revoke")
        self.assertTrue(failed, "The transient failure must reach the native pause boundary")
        self.assertEqual(revoked["status"], "revoked")
        jobs_before_reads = set(fx.cron.jobs)
        executions_before_reads = copy.deepcopy(fx.cron.executions)
        fx.schedules.get_schedule(sid)
        self.assertEqual(fx.runs.list_runs(sid), [])
        self.assertEqual(fx.refresh_grant(sid)["status"], "revoked")
        schedule = fx.schedules.get_schedule(sid)
        self.assertIn(schedule["status"], ("disabled", "paused", "requested"))
        self.assertIsNone(schedule["next_run_at"])
        self.assertTrue(set(fx.cron.jobs).issubset(jobs_before_reads))
        self.assertEqual(fx.cron.executions, executions_before_reads)
        self.assertFalse(any(job["enabled"] for job in fx.cron.jobs.values()))
        for job in fx.cron.jobs.values():
            self.assertIsNone(job.get("manual_run_at"))

    def test_r03_native_unknown_manual_run_is_failed_and_does_not_block_refresh(self):
        fx = self.fx
        sid = fx.make()
        completed = fx.runs.start_refresh(sid, trigger="manual", actor="user")
        control = fx.cron.execution(completed["detail"]["cron_job_id"], "completed")
        stamp = datetime.fromtimestamp(completed["queued_at"] + 1).astimezone().isoformat()
        control.update(claimed_at=stamp, started_at=stamp, finished_at=stamp)
        self.assertEqual(fx.runs.get_run(completed["id"])["status"], "succeeded")

        run = fx.runs.start_refresh(sid, trigger="manual", actor="user")
        self.assertNotEqual(run["id"], completed["id"])
        self.assertEqual(run["status"], "queued")
        jid = run["detail"]["cron_job_id"]
        execution = fx.cron.execution(jid)
        stamp = datetime.fromtimestamp(run["queued_at"] + 1).astimezone().isoformat()
        execution.update(claimed_at=stamp, started_at=stamp)
        self.assertEqual(fx.runs.get_run(run["id"])["status"], "running")
        execution.update(status="unknown", finished_at=stamp, error=None)
        visible = fx.runs.get_run(run["id"])
        with self.subTest(boundary="unknown is terminal locally"):
            self.assertEqual(visible["status"], "failed")
            self.assertIsNotNone(visible["ended_at"])
        with self.subTest(boundary="unknown outcome and possible side effects are visible"):
            diagnostic = json.dumps({"error": visible["error"], "detail": visible["detail"]}).lower()
            self.assertIn("unknown", diagnostic)
            self.assertRegex(diagnostic, r"side[ _-]?effects?")
            self.assertRegex(diagnostic, r"may|might|possible|possibly|could")
        subsequent = fx.runs.start_refresh(sid, trigger="manual", actor="user")
        with self.subTest(boundary="another refresh is admitted"):
            self.assertNotEqual(subsequent["id"], run["id"])
            self.assertEqual(subsequent["status"], "queued")
            self.assertNotEqual(subsequent["detail"]["cron_job_id"], jid)
            native = fx.cron.jobs[subsequent["detail"]["cron_job_id"]]
            self.assertTrue(native["enabled"])
            self.assertTrue(native["prompt"].endswith("Upkeep task:\n" + AGENT_PROMPT))
        self.assertEqual(execution["status"], "unknown")
        self.assertEqual(execution["finished_at"], stamp)

    def test_r03_terminal_unknown_allows_regrant_only_after_native_claims_clear(self):
        fx = self.fx
        for native_state in ("paused", "absent", "run_claim"):
            with self.subTest(native_state=native_state):
                sid = fx.make()
                jid = fx.approve_schedule(sid)["cron_job_id"]
                run = fx.runs.start_refresh(sid, trigger="manual", actor="user")
                self.assertEqual(run["status"], "queued")
                one_shot_jid = run["detail"]["cron_job_id"]
                execution = fx.cron.execution(one_shot_jid, "unknown")
                stamp = datetime.fromtimestamp(run["queued_at"] + 1).astimezone().isoformat()
                execution.update(claimed_at=stamp, started_at=stamp, finished_at=stamp)
                if native_state == "run_claim":
                    fx.cron.jobs[jid]["run_claim"] = "retained-native-worker"
                fx.grants.decide(sid, "refresh", "revoke")
                self.assertEqual(fx.refresh_grant(sid)["status"], "revoked")
                self.assertFalse(fx.cron.jobs[jid]["enabled"])
                if native_state == "absent":
                    fx.schedules.decide_schedule(sid, "deny")
                    self.assertNotIn(jid, fx.cron.jobs)
                else:
                    self.assertEqual(fx.cron.jobs[jid]["state"], "paused")
                if native_state == "run_claim":
                    with self.assertRaises(fx.core.SpacesError) as refused:
                        fx.approve_refresh(sid)
                    self.assertEqual(refused.exception.code, "blocked")
                    self.assertEqual(fx.refresh_grant(sid)["status"], "revoked")
                    self.assertFalse(fx.cron.jobs[jid]["enabled"])
                    self.assertEqual(fx.cron.jobs[jid]["run_claim"], "retained-native-worker")
                    fx.cron.jobs[jid].pop("run_claim")
                for job in fx.cron.jobs.values():
                    self.assertFalse(job["enabled"])
                    self.assertIsNone(job.get("fire_claim"))
                    self.assertIsNone(job.get("run_claim"))
                jobs_before = copy.deepcopy(fx.cron.jobs)
                native_before = copy.deepcopy(fx.cron.executions)
                with self.subTest(boundary="quiescent unknown permits exact Refresh reapproval"):
                    try:
                        granted = fx.approve_refresh(sid)
                    except fx.core.SpacesError as error:
                        self.fail(f"Terminal unknown with no native claims must permit regrant: {error.to_dict()}")
                    self.assertEqual(granted["status"], "granted")
                    self.assertEqual(fx.refresh_grant(sid)["status"], "granted")
                with self.subTest(boundary="reapproval does not admit native work"):
                    self.assertTrue(set(fx.cron.jobs).issubset(jobs_before))
                    self.assertFalse(any(job["enabled"] for job in fx.cron.jobs.values()))
                    self.assertEqual(fx.cron.executions, native_before)
                    for job_id, job in fx.cron.jobs.items():
                        self.assertEqual(job.get("manual_run_at"), jobs_before[job_id].get("manual_run_at"))
                    self.assertIsNone(fx.schedules.get_schedule(sid)["next_run_at"])

    def test_r03_vanished_one_shot_without_ledger_fails_and_allows_new_refresh(self):
        fx = self.fx
        sid = fx.make()
        run = fx.runs.start_refresh(sid, trigger="manual", actor="user")
        self.assertEqual(run["status"], "queued")
        jid = run["detail"]["cron_job_id"]
        self.assertTrue(run["detail"]["one_shot"])
        self.assertTrue(fx.cron.jobs[jid]["enabled"])
        self.assertEqual(fx.cron.list_executions(job_id=jid), [])
        self.assertEqual(fx.runs.start_refresh(sid, trigger="manual", actor="user")["id"], run["id"])
        fx.cron.jobs.pop(jid)
        self.assertEqual(fx.cron.list_executions(job_id=jid), [])
        fx.runs.list_runs(sid)
        visible = fx.runs.get_run(run["id"])
        self.assertNotIn("cancel_reason", visible["detail"])
        self.assertEqual(fx.refresh_grant(sid)["status"], "granted")
        with self.subTest(boundary="missing native work is a failed terminal attempt"):
            self.assertEqual(visible["status"], "failed")
            self.assertIsNotNone(visible["ended_at"])
        subsequent = fx.runs.start_refresh(sid, trigger="manual", actor="user")
        with self.subTest(boundary="native disappearance does not block future refresh"):
            self.assertNotEqual(subsequent["id"], run["id"])
            self.assertEqual(subsequent["status"], "queued")
            new_jid = subsequent["detail"]["cron_job_id"]
            self.assertNotEqual(new_jid, jid)
            self.assertTrue(fx.cron.jobs[new_jid]["enabled"])
            self.assertTrue(fx.cron.jobs[new_jid]["prompt"].endswith("Upkeep task:\n" + AGENT_PROMPT))

if __name__ == "__main__":
    unittest.main()
