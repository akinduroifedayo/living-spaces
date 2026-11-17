import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "living-spaces"))
from living_spaces_core import bridge, db, logs, migrations, projects, sessions


class RuntimeDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".run").mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=ROOT / ".run")
        self.addCleanup(temporary.cleanup)
        environment = patch.dict(os.environ, {
            "LIVING_SPACES_DB": str(Path(temporary.name) / "spaces.db"),
            "HERMES_HOME": temporary.name,
        })
        environment.start()
        self.addCleanup(environment.stop)
        self.sid = projects.create_space(
            "Diagnostics", owner="Demo", author="agent:demo",
            files={"index.html": "<main>Demo</main>"},
        )["id"]

    def report(self, session, entries=None, **metadata):
        result = bridge.dispatch(self.sid, session, "log", {"entries": entries or [], **metadata})
        self.assertTrue(result["ok"], result)
        return result["result"]

    def diagnostics(self, **kwargs):
        return logs.read_logs(self.sid, include_summary=True, **kwargs)

    def test_session_opened_revision_wins_when_head_moves(self):
        opened = sessions.open_session(self.sid)
        projects.write_files(self.sid, files={"index.html": "Changed"}, author="agent:demo", summary="Edit")
        self.report(opened["session"], [{"level": "error", "msg": "Delayed old error"}])
        row = logs.read_logs(self.sid)[0]
        self.assertEqual(row["rev"], opened["head_rev"])
        self.assertEqual(row["attribution"], "session_opened")
        summary = self.diagnostics()["summary"]
        self.assertEqual(summary["rev"], opened["head_rev"] + 1)
        self.assertFalse(summary["opened"])
        self.assertEqual((summary["errors"], summary["failed"]), (0, 0))
        forged = bridge.dispatch(self.sid, opened["session"], "log", {"entries": [], "rev": 999})
        self.assertFalse(forged["ok"])

    def test_unopened_and_opened_without_a_report_are_explicit(self):
        summary = self.diagnostics()["summary"]
        self.assertFalse(summary["opened"])
        self.assertEqual((summary["sessions"], summary["loaded"], summary["failed"], summary["unreported"]), (0, 0, 0, 0))
        sessions.open_session(self.sid)
        summary = self.diagnostics()["summary"]
        self.assertTrue(summary["opened"])
        self.assertEqual((summary["loaded"], summary["failed"], summary["unreported"]), (0, 0, 1))

    def test_lifecycle_counts_and_drops_survive_retention_and_filtering(self):
        loaded = sessions.open_session(self.sid)["session"]
        failed = sessions.open_session(self.sid)["session"]
        self.report(loaded, lifecycle="loaded", dropped=7, unconfirmed=4)
        self.report(loaded, lifecycle="loaded", dropped=7)
        self.report(loaded, lifecycle="failed", dropped=3)
        self.report(failed, [{"level": "error", "msg": "Space failed to load: broken import"},
                             {"level": "warn", "msg": "A warning"}], lifecycle="failed", dropped=2)
        with patch.object(logs.limits, "LOG_HISTORY", 1):
            self.report(loaded, [{"level": "log", "msg": "Newer output"}], dropped=9)
        sessions.close_session(loaded)
        result = self.diagnostics(level="error", limit=1)
        self.assertEqual(result["entries"], [])
        self.assertEqual(result["summary"], {
            "rev": 1, "opened": True, "sessions": 2, "loaded": 0, "failed": 2,
            "unreported": 0, "errors": 1, "warnings": 1, "dropped": 11, "unconfirmed": 4,
        })

    def test_unattributed_rows_do_not_claim_session_execution(self):
        logs.add_logs(self.sid, None, [{"level": "error", "msg": "Backend diagnostic"}])
        result = self.diagnostics()
        self.assertEqual(result["entries"][0]["rev"], 1)
        self.assertEqual(result["entries"][0]["attribution"], "unattributed")
        self.assertFalse(result["summary"]["opened"])
        self.assertEqual(result["summary"]["errors"], 0)

    def test_redaction_applies_to_failed_lifecycle_messages_before_storage(self):
        session = sessions.open_session(self.sid)["session"]
        self.report(session, [{"level": "error", "msg": "Space failed to load: password=demo-secret"}], lifecycle="failed")
        with db.read() as conn:
            stored = conn.execute("SELECT msg FROM logs WHERE space=?", (self.sid,)).fetchone()[0]
        self.assertNotIn("demo-secret", stored)
        self.assertIn("[REDACTED]", stored)
        self.assertEqual(self.diagnostics()["entries"][0]["msg"], stored)

    def test_metadata_is_validated_and_keeps_existing_session_and_grant_checks(self):
        session = sessions.open_session(self.sid)["session"]
        for metadata in ({"lifecycle": "ready"}, {"lifecycle": {}}, {"dropped": -1},
                         {"dropped": True}, {"dropped": 2**53}, {"unconfirmed": -1}, {"unconfirmed": True}):
            with self.subTest(metadata=metadata):
                result = bridge.dispatch(self.sid, session, "log", {"entries": [{"level": "error", "msg": "No write"}], **metadata})
                self.assertFalse(result["ok"])
        self.assertEqual(logs.read_logs(self.sid), [])
        from living_spaces_core import grants
        grants.decide(self.sid, "logs", "revoke", actor="user")
        self.assertFalse(bridge.dispatch(self.sid, session, "log", {"entries": [], "lifecycle": "loaded"})["ok"])
        self.assertEqual(self.diagnostics()["summary"]["unreported"], 1)
        sessions.close_session(session)
        self.assertFalse(bridge.dispatch(self.sid, session, "log", {"entries": []})["ok"])

    def test_additive_migration_preserves_historical_ingestion_labels(self):
        conn = sqlite3.connect(":memory:")
        self.addCleanup(conn.close)
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            CREATE TABLE logs(id INTEGER PRIMARY KEY, space TEXT, session TEXT, rev INTEGER,
                              at REAL, level TEXT, msg TEXT);
            CREATE TABLE sessions(id TEXT PRIMARY KEY, space TEXT, created_at REAL,
                                  closed_at REAL, head_rev INTEGER);
            INSERT INTO logs VALUES(1,'demo','old-session',5,0,'info','Historical message');
            INSERT INTO sessions VALUES('old-session','demo',0,NULL,2);
        """)
        migrations.add_runtime_diagnostics(conn)
        migrations.add_runtime_diagnostics(conn)
        row = conn.execute("SELECT * FROM logs").fetchone()
        self.assertEqual((row["rev"], row["attribution"], row["msg"]), (5, "ingestion_head", "Historical message"))
        session = conn.execute("SELECT * FROM sessions").fetchone()
        self.assertIsNone(session["lifecycle"])
        self.assertEqual((session["log_errors"], session["log_warnings"], session["log_dropped"], session["log_unconfirmed"]), (0, 0, 0, 0))


if __name__ == "__main__":
    unittest.main()
