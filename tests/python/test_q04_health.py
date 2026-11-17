import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "living-spaces"))
from living_spaces_core import bridge, db, logs, projects, records, sessions, SpacesError


class Q04HealthTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".run").mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix="q04-health-", dir=ROOT / ".run")
        self.addCleanup(temporary.cleanup)
        environment = patch.dict(os.environ, {
            "LIVING_SPACES_DB": str(Path(temporary.name) / "spaces.db"),
            "HERMES_HOME": temporary.name,
        })
        environment.start()
        self.addCleanup(environment.stop)
        self.sid = projects.create_space(
            "Q04 health", owner="Demo", author="test:q04",
            files={"index.html": "<main>Version one</main>"},
        )["id"]

    def report(self, session, entries=None, **metadata):
        reply = bridge.dispatch(self.sid, session, "log", {
            "entries": entries if entries is not None else [], **metadata,
        })
        self.assertTrue(reply["ok"], reply)
        return reply["result"]

    def diagnostics(self):
        return logs.read_logs(self.sid, include_summary=True)

    def snapshot(self):
        with db.read() as conn:
            tables = {
                table: [dict(row) for row in conn.execute(
                    f"SELECT * FROM {table} WHERE space=? ORDER BY {order}", (self.sid,)
                )]
                for table, order in (
                    ("records", "collection,id"), ("changes", "seq"),
                    ("revisions", "rev"), ("recovery_points", "id"),
                )
            }
        return {
            "space": projects.get_space(self.sid),
            "code": projects.read_file(self.sid, "index.html"),
            "tables": tables,
        }

    def migrate(self):
        manifest = projects.get_space(self.sid)["manifest"]
        manifest["data"] = {"version": 2, "migrations": [{"to": 2, "ops": [
            {"op": "rename_field", "collection": "notes", "from": "note", "to": "annotation"},
        ]}]}
        return projects.write_files(
            self.sid, files={"index.html": "<main>Version two</main>"}, manifest=manifest,
            base_rev=1, author="test:q04", summary="Migrate notes",
        )

    def test_failed_lifecycle_supersedes_loaded_without_losing_counts_or_redaction(self):
        session = sessions.open_session(self.sid)["session"]
        self.report(session, lifecycle="loaded", dropped=7, unconfirmed=4)
        self.assertEqual(self.diagnostics()["summary"], {
            "rev": 1, "opened": True, "sessions": 1, "loaded": 1, "failed": 0,
            "unreported": 0, "errors": 0, "warnings": 0, "dropped": 7, "unconfirmed": 4,
        })
        self.report(session, [
            {"level": "error", "msg": "Evaluation failed password=q04-private-token"},
            {"level": "warn", "msg": "Handled warning"},
        ], lifecycle="failed", dropped=3, unconfirmed=2)
        result = self.diagnostics()
        self.assertEqual(len(result["entries"]), 2, "the failed report reached persistent storage")
        with db.read() as conn:
            stored = [row["msg"] for row in conn.execute(
                "SELECT msg FROM logs WHERE space=? ORDER BY id", (self.sid,)
            )]
        self.assertNotIn("q04-private-token", "\n".join(stored))
        self.assertIn("[REDACTED]", stored[0])
        self.assertEqual(result["summary"], {
            "rev": 1, "opened": True, "sessions": 1, "loaded": 0, "failed": 1,
            "unreported": 0, "errors": 1, "warnings": 1, "dropped": 7, "unconfirmed": 4,
        })

    def test_loaded_after_failed_cannot_clear_failure_but_a_new_session_can_load(self):
        failed = sessions.open_session(self.sid)["session"]
        self.report(failed, lifecycle="failed", dropped=5, unconfirmed=2)
        self.report(failed, [{"level": "warn", "msg": "Late shell report"}], lifecycle="loaded", dropped=1)
        self.assertEqual(self.diagnostics()["summary"], {
            "rev": 1, "opened": True, "sessions": 1, "loaded": 0, "failed": 1,
            "unreported": 0, "errors": 0, "warnings": 1, "dropped": 5, "unconfirmed": 2,
        })
        loaded = sessions.open_session(self.sid)["session"]
        self.report(loaded, lifecycle="loaded")
        self.assertEqual(self.diagnostics()["summary"], {
            "rev": 1, "opened": True, "sessions": 2, "loaded": 1, "failed": 1,
            "unreported": 0, "errors": 0, "warnings": 1, "dropped": 5, "unconfirmed": 2,
        })

    def test_handled_console_errors_do_not_change_loaded_or_unreported_lifecycle(self):
        loaded = sessions.open_session(self.sid)["session"]
        unreported = sessions.open_session(self.sid)["session"]
        self.report(loaded, lifecycle="loaded")
        entries = [{"level": "error", "msg": "Handled boot entry load failure"}] * 4
        self.report(loaded, entries)
        self.report(unreported, entries)
        result = self.diagnostics()
        self.assertEqual(len(result["entries"]), 8)
        self.assertEqual(result["summary"], {
            "rev": 1, "opened": True, "sessions": 2, "loaded": 1, "failed": 0,
            "unreported": 1, "errors": 8, "warnings": 0, "dropped": 0, "unconfirmed": 0,
        })

    def test_incompatible_code_restore_preserves_migrated_records_code_and_history(self):
        records.put(self.sid, "notes", "one", {"note": "Keep me", "status": "reading"}, actor="user")
        self.migrate()
        current = records.get(self.sid, "notes", "one")
        self.assertEqual(current["data"], {"annotation": "Keep me", "status": "reading"})
        before = self.snapshot()
        with self.assertRaises(SpacesError) as caught:
            projects.restore_revision(self.sid, 1, author="user")
        error = caught.exception.to_dict()
        self.assertEqual((error["code"], error["from_version"], error["to_version"]), ("incompatible", 2, 1))
        self.assertEqual(self.snapshot(), before)
        compatible = projects.write_files(
            self.sid, files={"index.html": "<main>Later version two</main>"},
            base_rev=2, author="test:q04", summary="Same data version edit",
        )
        restored = projects.restore_revision(self.sid, 2, author="user")
        self.assertEqual((compatible["rev"], restored["rev"], restored["restored_from"]), (3, 4, 2))
        self.assertEqual(records.get(self.sid, "notes", "one"), current)
        self.assertEqual(projects.get_space(self.sid)["data_version"], 2)

    def test_code_only_restore_retains_current_notes_statuses_and_change_cursor(self):
        original = records.put(self.sid, "notes", "one", {"note": "Earlier note", "status": "reading"}, actor="user")
        projects.write_files(
            self.sid, files={"index.html": "<main>Later code</main>"},
            base_rev=1, author="test:q04", summary="Code edit",
        )
        latest = records.put(
            self.sid, "notes", "one", {"note": "Latest note", "status": "done"},
            actor="user", base_rev=original["rev"],
        )
        before = self.snapshot()
        restored = projects.restore_revision(self.sid, 1, author="user")
        after = self.snapshot()
        self.assertEqual((restored["rev"], restored["kind"], restored["restored_from"]), (3, "restore", 1))
        self.assertEqual(after["code"]["text"], "<main>Version one</main>")
        self.assertNotEqual(after["code"]["text"], before["code"]["text"])
        self.assertEqual(records.get(self.sid, "notes", "one"), latest)
        for table in ("records", "changes", "recovery_points"):
            self.assertEqual(after["tables"][table], before["tables"][table], table)
        self.assertEqual(after["tables"]["revisions"][:2], before["tables"]["revisions"])
        self.assertEqual(len(after["tables"]["revisions"]), 3)
        self.assertEqual(after["space"]["data_version"], 1)

    def test_cross_version_recovery_refusal_preserves_all_state_without_data_undo(self):
        records.put(self.sid, "notes", "one", {"note": "Version one note"}, actor="user")
        point = records.create_recovery_point(self.sid, "Before migration")
        self.migrate()
        current = records.get(self.sid, "notes", "one")
        self.assertEqual(current["data"], {"annotation": "Version one note"})
        before = self.snapshot()
        with self.assertRaises(SpacesError) as caught:
            records.restore_recovery_point(self.sid, point, actor="user")
        self.assertEqual(caught.exception.code, "incompatible")
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
