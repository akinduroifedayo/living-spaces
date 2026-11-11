from contextlib import contextmanager
from unittest.mock import patch
import unittest

from tests.python.test_core_limits import LimitCase, feed_xml
from living_spaces_core import db, feeds, projects, records, runs


@contextmanager
def interrupt_after(statement, occurrence, exception=OSError):
    connect = db.connect
    executed = []

    class Connection:
        def __init__(self):
            self.conn = connect()

        def __getattr__(self, name):
            return getattr(self.conn, name)

        def execute(self, sql, *args):
            result = self.conn.execute(sql, *args)
            if sql.startswith(statement):
                executed.append(sql)
                if len(executed) == occurrence:
                    raise exception("Interrupted test write")
            return result

    with patch.object(db, "connect", side_effect=Connection):
        yield executed


class InterruptedWriteTests(LimitCase):
    def test_project_interruption_retains_loadable_head_and_no_partial_blobs(self):
        original = projects.bundle(self.sid)
        for statement, occurrence in (("INSERT OR IGNORE INTO blobs", 2),
                                      ("INSERT INTO revisions", 1),
                                      ("UPDATE spaces SET head_rev", 1)):
            for exception in (OSError, KeyboardInterrupt):
                with self.subTest(statement=statement, exception=exception.__name__):
                    before = self.snapshot()
                    with interrupt_after(statement, occurrence, exception) as executed:
                        with self.assertRaisesRegex(exception, "Interrupted test write"):
                            self.write({"index.html": "<h1>Unfinished</h1>", "new.txt": "Partial blob"}, base_rev=1)
                    self.assertEqual(len(executed), occurrence)
                    self.assertEqual(self.snapshot(), before)
                    self.assertEqual(projects.bundle(self.sid), original)
        self.assertEqual(self.write({"index.html": "<h1>Recovered</h1>", "new.txt": "Complete"}, base_rev=1)["rev"], 2)
        self.assertIn("Recovered", projects.read_file(self.sid, "index.html")["text"])

    def test_interrupted_batch_rolls_back_updates_deletes_inserts_and_cursor(self):
        first = self.put({"note": "Original"}, rid="first")
        second = self.put({"note": "Keep me"}, rid="second")
        ops = [{"op": "put", "collection": "probe", "id": "first", "base_rev": first["rev"], "data": {"note": "Changed"}},
               {"op": "delete", "collection": "probe", "id": "second", "base_rev": second["rev"]},
               {"op": "put", "collection": "probe", "id": "third", "data": {"note": "New"}}]
        for exception in (OSError, KeyboardInterrupt):
            with self.subTest(exception=exception.__name__):
                before = self.snapshot()
                with interrupt_after("INSERT INTO changes", 3, exception) as executed:
                    with self.assertRaisesRegex(exception, "Interrupted test write"):
                        records.batch(self.sid, ops, actor="app")
                self.assertEqual(len(executed), 3)
                self.assertEqual(self.snapshot(), before)
        result = records.batch(self.sid, ops, actor="app")
        self.assertEqual(len(result["results"]), 3)
        self.assertEqual({r["id"]: r["data"] for r in records.query(self.sid, "probe")["records"]},
                         {"first": {"note": "Changed"}, "third": {"note": "New"}})

    def test_interrupted_feed_source_rolls_back_sources_notes_metadata_and_cursor(self):
        source = self.refresh_setup()
        self.refresh(source, feed_xml(2, "Original"))
        row = records.query(self.sid, "papers")["records"][0]
        records.put(self.sid, "papers", row["id"], {"note": "Keep note", "status": "reading"}, actor="app", base_rev=row["rev"])
        before = self.snapshot()
        counts = {"added": 0, "updated": 0, "unchanged": 0}
        with interrupt_after("INSERT INTO changes", 2) as executed:
            with self.assertRaisesRegex(OSError, "Interrupted test write"):
                feeds.refresh_source(self.sid, source, actor="upkeep:manual", before_write=lambda: None,
                                     fetcher=lambda sid, url: feed_xml(3, "Updated"), counts=counts)
        self.assertEqual(len(executed), 2)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(counts, {"added": 0, "updated": 0, "unchanged": 0})
        self.assertEqual(self.refresh(source, feed_xml(3, "Updated"))[0], {"added": 1, "updated": 2, "unchanged": 0})
        self.assertEqual(records.get(self.sid, "papers", row["id"])["data"], {"note": "Keep note", "status": "reading"})

    def test_refresh_run_reports_interruption_and_retry_succeeds(self):
        source = self.refresh_setup()
        manifest = projects.get_space(self.sid)["manifest"]
        manifest["upkeep"] = {"handler": "feed", "sources": [source]}
        self.write({}, manifest=manifest)
        self.refresh(source, feed_xml(2, "Original"))
        before = records.query(self.sid, "papers")
        with patch.object(feeds, "fetch", return_value=feed_xml(3, "Updated")):
            with interrupt_after("INSERT INTO changes", 2) as executed:
                failed = runs.start_refresh(self.sid, trigger="manual", actor="user", wait=True)
            self.assertEqual(len(executed), 2)
            self.assertEqual(failed["status"], "failed")
            self.assertIn("Interrupted test write", failed["error"])
            self.assertFalse(failed["detail"]["sources"][0]["ok"])
            self.assertEqual(failed["changed"], {"added": 0, "updated": 0, "unchanged": 0, "removed": 0})
            self.assertEqual(records.query(self.sid, "papers"), before)
            recovered = runs.start_refresh(self.sid, trigger="manual", actor="user", wait=True)
        self.assertEqual(recovered["status"], "succeeded")
        self.assertEqual(recovered["changed"], {"added": 1, "updated": 2, "unchanged": 0, "removed": 0})


if __name__ == "__main__":
    unittest.main()
