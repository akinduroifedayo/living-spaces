import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "living-spaces"))
from living_spaces_core import bridge, db, feeds, grants, logs, projects, records, runs, sessions, SpacesError


class ReviewBackendCase(unittest.TestCase):
    def setUp(self):
        (ROOT / ".run").mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix="review-backend-", dir=ROOT / ".run")
        self.addCleanup(temporary.cleanup)
        environment = patch.dict(os.environ, {
            "LIVING_SPACES_DB": str(Path(temporary.name) / "spaces.db"),
            "HERMES_HOME": temporary.name,
        })
        environment.start()
        self.addCleanup(environment.stop)
        self.sid = projects.create_space(
            "Review Backend", owner="Demo Hermes", author="agent:demo",
            files={"index.html": "<h1>Synthetic review fixture</h1>"},
        )["id"]


class ReviewLogRedactionTests(ReviewBackendCase):
    CREDENTIALS = {
        "password": "synthetic-secret",
        "api_key": "demo-short-secret",
        "access_token": "demo-access-7",
        "refresh_token": "demo-refresh-8",
        "client_secret": "demo-client-9",
        "authorization": "demo-auth-6",
    }

    def stored_messages(self, message):
        self.assertEqual(logs.add_logs(self.sid, None, [{"level": "info", "msg": message}]), 1)
        with db.read() as conn:
            raw = dict(conn.execute(
                "SELECT * FROM logs WHERE space=? ORDER BY id DESC LIMIT 1", (self.sid,),
            ).fetchone())
        returned = logs.read_logs(self.sid, limit=1)
        self.assertEqual(len(returned), 1)
        self.assertEqual(returned[0]["id"], raw["id"])
        self.assertEqual(raw["level"], "info")
        return {"sqlite": raw["msg"], "read_logs": returned[0]["msg"]}

    def assert_redacted(self, message, secrets, innocent):
        for surface, stored in self.stored_messages(message).items():
            with self.subTest(surface=surface):
                for value in innocent:
                    self.assertIn(value, stored)
                for secret in secrets:
                    with self.subTest(secret=secret):
                        self.assertNotIn(secret, stored)

    def test_f3_flat_json_credential_values_are_redacted_before_storage(self):
        payload = {"diagnostic": "Public feed ready", "request_id": "request-17", **self.CREDENTIALS}
        self.assert_redacted(json.dumps(payload), self.CREDENTIALS.values(),
                             ("Public feed ready", "request-17"))

    def test_f3_nested_json_credential_values_are_redacted_before_storage(self):
        payload = {
            "diagnostic": "Public feed ready",
            "context": {"attempts": [{"request_id": "request-17", "credentials": self.CREDENTIALS}]},
            "result": {"status": "No updates"},
        }
        self.assert_redacted(json.dumps(payload), self.CREDENTIALS.values(),
                             ("Public feed ready", "request-17", "No updates"))

    def test_f3_credential_assignments_are_redacted_before_storage(self):
        for key, secret in self.CREDENTIALS.items():
            for quote in ("", "'", '"'):
                with self.subTest(key=key, quote=quote):
                    value = secret + (" synthetic words" if quote else "")
                    message = f"Public feed ready {key}={quote}{value}{quote} request_id=request-17"
                    self.assert_redacted(message, (secret, "synthetic words") if quote else (secret,),
                                         ("Public feed ready", "request_id=request-17"))

    def test_f3_plain_diagnostic_is_preserved_exactly(self):
        message = "Public feed ready; collection=papers count=2 request_id=request-17"
        for surface, stored in self.stored_messages(message).items():
            with self.subTest(surface=surface):
                self.assertEqual(stored, message)


class ReviewRefreshAdmissionTests(ReviewBackendCase):
    FEED_URL = "https://research.example/feed"
    FEED = (
        b'<rss version="2.0"><channel><title>Public demo</title><item>'
        b'<guid>synthetic-review-paper</guid><title>Public review paper</title>'
        b'<link>https://research.example/paper</link>'
        b'<description>Synthetic public summary</description></item></channel></rss>'
    )

    def setUp(self):
        super().setUp()
        projects.write_files(self.sid, files={}, manifest={"upkeep": {
            "handler": "feed", "sources": [{
                "id": "review-feed", "url": self.FEED_URL, "collection": "papers",
            }],
        }}, author="agent:demo", summary="Declare public feed")
        self.session = sessions.open_session(self.sid)["session"]
        self.fetch = Mock(return_value=self.FEED)
        fetch_patch = patch.object(feeds, "fetch", self.fetch)
        fetch_patch.start()
        self.addCleanup(fetch_patch.stop)
        self.start_refresh = runs.start_refresh

    def refresh_and_wait(self, *args, **kwargs):
        # Drain real upkeep before inspecting side effects, including the expected red path.
        kwargs["wait"] = True
        return self.start_refresh(*args, **kwargs)

    def start_call(self, call):
        outcome = {}

        def invoke():
            try:
                outcome["result"] = call()
            except Exception as exc:
                outcome["error"] = exc

        thread = threading.Thread(target=invoke)
        thread.start()
        self.addCleanup(thread.join, 10)
        return thread, outcome

    def finish_call(self, thread, outcome):
        thread.join(10)
        self.assertFalse(thread.is_alive(), "Review operation did not finish")
        if "error" in outcome:
            raise outcome["error"]
        return outcome["result"]

    def assert_session_closed(self):
        with self.assertRaises(SpacesError) as caught:
            sessions.require(self.sid, self.session)
        self.assertEqual(caught.exception.code, "session_invalid")

    def assert_no_admission_or_write(self):
        with self.subTest(effect="runs API"):
            self.assertEqual(runs.list_runs(self.sid), [])
        with db.read() as conn:
            for table in ("runs", "records", "changes"):
                with self.subTest(effect=table):
                    self.assertEqual(conn.execute(
                        f"SELECT count(*) FROM {table} WHERE space=?", (self.sid,),
                    ).fetchone()[0], 0)

    def assert_successful_refresh(self, run, actor, trigger):
        self.assertEqual(run["status"], "succeeded", run)
        self.assertEqual((run["actor"], run["trigger"]), (actor, trigger))
        self.assertEqual(run["changed"], {"added": 1, "updated": 0, "unchanged": 0, "removed": 0})
        self.assertEqual(runs.get_run(run["id"]), run)
        self.assertEqual(runs.list_runs(self.sid), [run])
        self.fetch.assert_called_once_with(self.sid, self.FEED_URL)
        result = records.query(self.sid, "papers")
        self.assertEqual(result["total"], 1)
        record = result["records"][0]
        self.assertEqual(record["source"]["title"], "Public review paper")
        self.assertEqual(record["source_meta"]["url"], self.FEED_URL)
        self.assertEqual(record["updated_by"], actor)
        changes = records.changes_since(self.sid, 0)["changes"]
        self.assertEqual(len(changes), 1)
        self.assertEqual((changes[0]["id"], changes[0]["op"]), (record["id"], "source"))

    def test_f4_session_closed_after_entry_check_cannot_admit_refresh(self):
        closed, resume = threading.Event(), threading.Event()
        real_check = sessions.require

        def close_after_first_check(*args, **kwargs):
            result = real_check(*args, **kwargs)
            if not closed.is_set():
                sessions.close_session(self.session)
                closed.set()
                if not resume.wait(10):
                    raise TimeoutError("Review dispatch was not released")
            return result

        with patch.object(sessions, "require", close_after_first_check), \
                patch.object(runs, "start_refresh", self.refresh_and_wait):
            thread, outcome = self.start_call(
                lambda: bridge.dispatch(self.sid, self.session, "refresh", {}),
            )
            try:
                self.assertTrue(closed.wait(10), "First successful session check did not close the session")
                self.assert_session_closed()
                self.assert_no_admission_or_write()
                self.fetch.assert_not_called()
            finally:
                resume.set()
                thread.join(10)
            reply = self.finish_call(thread, outcome)

        self.assertFalse(reply["ok"], reply)
        self.assertEqual(reply["error"]["code"], "session_invalid")
        with self.subTest(effect="fetch"):
            self.fetch.assert_not_called()
        self.assert_no_admission_or_write()

    def test_f4_live_session_refresh_fetches_and_persists(self):
        with patch.object(runs, "start_refresh", self.refresh_and_wait):
            reply = bridge.dispatch(self.sid, self.session, "refresh", {})
        self.assertTrue(reply["ok"], reply)
        sessions.require(self.sid, self.session)
        self.assert_successful_refresh(reply["result"], "app", "manual")

    def test_f4_admitted_native_upkeep_survives_unrelated_session_close(self):
        fetching, release = threading.Event(), threading.Event()

        def blocked_fetch(sid, url):
            fetching.set()
            if not release.wait(10):
                raise TimeoutError("Review fetch was not released")
            return self.FEED

        self.fetch.side_effect = blocked_fetch
        thread, outcome = self.start_call(lambda: runs.start_refresh(
            self.sid, trigger="schedule", actor="upkeep:schedule", wait=True,
        ))
        try:
            self.assertTrue(fetching.wait(10), "Native upkeep did not reach the fake fetcher")
            admitted = runs.list_runs(self.sid)
            self.assertEqual(len(admitted), 1)
            self.assertEqual(admitted[0]["status"], "running")
            self.assertEqual(records.query(self.sid, "papers")["total"], 0)
            sessions.close_session(self.session)
            self.assert_session_closed()
            self.assertEqual(runs.get_run(admitted[0]["id"])["status"], "running")
        finally:
            release.set()
            thread.join(10)
        run = self.finish_call(thread, outcome)
        self.assertEqual(run["id"], admitted[0]["id"])
        self.assert_successful_refresh(run, "upkeep:schedule", "schedule")


if __name__ == "__main__":
    unittest.main()
