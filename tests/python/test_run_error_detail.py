import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "living-spaces"))
from living_spaces_core import feeds, grants, projects, records, runs, SpacesError


class RunErrorDetailTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".run").mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix="run-error-", dir=ROOT / ".run")
        self.addCleanup(temporary.cleanup)
        environment = patch.dict(os.environ, {
            "LIVING_SPACES_DB": str(Path(temporary.name) / "spaces.db"),
            "HERMES_HOME": temporary.name,
        })
        environment.start()
        self.addCleanup(environment.stop)
        self.sid = projects.create_space(
            "Run Error", owner="Demo", author="user",
            files={"index.html": "<h1>Public demo</h1>"},
            manifest={"upkeep": {"handler": "feed", "sources": [{
                "id": "public-feed", "url": "https://research.example/feed", "collection": "papers",
            }]}},
        )["id"]
        grants.decide(self.sid, "refresh", "grant")

    def refresh(self):
        return runs.start_refresh(self.sid, trigger="manual", actor="user", wait=True)

    def test_feed_entry_limit_preserves_numbers_and_recovers(self):
        entry = b"<item><guid>public-paper</guid><title>Public paper</title></item>"
        payload = b"<rss><channel>" + entry * 201 + b"</channel></rss>"
        with patch.object(feeds, "fetch", return_value=payload):
            run = self.refresh()
        self.assertEqual(run["status"], "failed")
        source = run["detail"]["sources"][0]
        self.assertFalse(source["ok"])
        self.assertEqual(source["error_detail"], {
            "code": "limit", "message": "Feed exceeds 200 entries", "limit": 200, "actual": 201,
        })
        for message in (source["error"], run["error"]):
            self.assertIn("limit 200", message)
            self.assertIn("actual 201", message)
        self.assertEqual(runs.get_run(run["id"]), run)
        self.assertEqual(runs.list_runs(self.sid), [run])
        self.assertEqual(records.query(self.sid, "papers")["total"], 0)
        self.assertEqual(run["changed"], {"added": 0, "updated": 0, "unchanged": 0, "removed": 0})
        with patch.object(feeds, "fetch", return_value=b"<rss><channel>" + entry + b"</channel></rss>"):
            recovered = self.refresh()
        self.assertEqual(recovered["status"], "succeeded")
        self.assertIsNone(recovered["error"])
        self.assertEqual(recovered["changed"]["added"], 1)

    def test_other_spaces_error_keeps_structured_extras(self):
        failure = SpacesError("not_granted", "Synthetic source denial", capability="refresh")
        with patch.object(feeds, "fetch", side_effect=failure):
            run = self.refresh()
        self.assertEqual(run["status"], "failed")
        source = run["detail"]["sources"][0]
        self.assertFalse(source["ok"])
        self.assertEqual(source["error_detail"], failure.to_dict())
        self.assertEqual(source["error"], "Synthetic source denial")
        self.assertEqual(run["error"], "public-feed: Synthetic source denial")

    def test_unstructured_error_retains_existing_message(self):
        with patch.object(feeds, "fetch", side_effect=OSError("Synthetic transport failure")):
            run = self.refresh()
        self.assertEqual(run["status"], "failed")
        source = run["detail"]["sources"][0]
        self.assertFalse(source["ok"])
        self.assertNotIn("error_detail", source)
        self.assertEqual(source["error"], "Synthetic transport failure")
        self.assertEqual(run["error"], "public-feed: Synthetic transport failure")


if __name__ == "__main__":
    unittest.main()
