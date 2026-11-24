import hashlib
from unittest.mock import patch

from .test_core_store import CoreCase
from .test_c_tools import ToolCase
from living_spaces_core import bridge, db, feeds, inspection, limits, projects, records, runs, sessions, upkeep


def source(identity):
    return {"id": identity, "url": f"https://{identity}.example/feed", "collection": identity}


def payload(identity, title="First", extra=""):
    return f"<rss><channel><item><guid>{identity}</guid><title>{title}</title><pubDate>Mon, 02 Nov 2026 12:00:00 GMT</pubDate></item>{extra}</channel></rss>".encode()


class Q15FreshnessTests(CoreCase):
    def setUp(self):
        super().setUp()
        self.write({}, manifest={"upkeep": {"handler": "feed", "sources": [source("alpha"), source("beta")]}})

    def refresh(self, bodies):
        def fetch(sid, url):
            value = bodies[url.split("//")[1].split(".")[0]]
            if isinstance(value, Exception):
                raise value
            return value
        with patch.object(feeds, "fetch", side_effect=fetch):
            return runs.start_refresh(self.sid, trigger="manual", actor="user", wait=True)

    def summary(self):
        session = sessions.open_session(self.sid)["session"]
        reply = bridge.dispatch(self.sid, session, "freshness", {})
        self.assertTrue(reply["ok"], reply)
        return reply["result"]

    def test_mixed_sources_advance_independently_and_preserve_overrides(self):
        initial = self.refresh({"alpha": payload("a"), "beta": payload("b")})
        self.assertEqual(initial["status"], "succeeded")
        rid = "src_" + hashlib.sha1(b"a").hexdigest()[:16]
        record = records.get(self.sid, "alpha", rid)
        records.put(self.sid, "alpha", rid, {"title": "My title", "note": "Keep"}, actor="user", base_rev=record["rev"])
        before = records.query(self.sid, "beta")["records"]
        mixed = self.refresh({"alpha": payload("a", "New source title"), "beta": TimeoutError("Beta unavailable")})
        self.assertEqual(mixed["status"], "failed")
        updated = records.get(self.sid, "alpha", rid)
        self.assertEqual(updated["source"]["title"], "New source title")
        self.assertEqual(updated["data"], {"title": "My title", "note": "Keep"})
        self.assertEqual(records.query(self.sid, "beta")["records"], before)
        self.assertIn("sources", projects.get_space(self.sid)["freshness"])
        summaries = {item["id"]: item for item in self.summary()["sources"]}
        self.assertGreater(summaries["alpha"]["last_success_at"], initial["started_at"])
        self.assertEqual(summaries["beta"]["last_success_at"], initial["detail"]["sources"][1]["last_success_at"])
        self.assertGreater(summaries["beta"]["last_attempt_at"], summaries["beta"]["last_success_at"])
        self.assertEqual(summaries["beta"]["failure_reason"], "Beta unavailable")
        self.assertEqual(summaries["alpha"]["source_as_of"], 1793620800.0)
        self.assertEqual(mixed["detail"]["counts"], {"committed": 1, "skipped": 0, "rejected": 0})

    def test_rejected_entries_and_skipped_atomic_batch_have_honest_counts(self):
        invalid = "<item><title>No identity</title></item>"
        oversized = "<item><guid>large</guid><description>" + "x" * (limits.SOURCE_BYTES + 1) + "</description></item>"
        run = self.refresh({"alpha": payload("a", extra=invalid + oversized), "beta": payload("b")})
        self.assertEqual(run["status"], "failed")
        self.assertEqual(records.query(self.sid, "alpha")["total"], 0)
        self.assertEqual(records.query(self.sid, "beta")["total"], 1)
        self.assertIn("counts", run["detail"])
        self.assertEqual(run["detail"]["counts"], {"committed": 1, "skipped": 1, "rejected": 2})
        self.assertEqual(run["detail"]["sources"][0]["counts"], {"committed": 0, "skipped": 1, "rejected": 2})
        self.assertEqual(run["changed"]["added"], 1)

    def test_unchanged_and_duplicate_entries_are_skipped_not_committed(self):
        body = payload("a", extra="<item><guid>a</guid><title>First</title><pubDate>Mon, 02 Nov 2026 12:00:00 GMT</pubDate></item>")
        first = self.refresh({"alpha": body, "beta": payload("b")})
        self.assertEqual(records.query(self.sid, "alpha")["total"], 1)
        self.assertIn("counts", first["detail"])
        self.assertEqual(first["detail"]["counts"], {"committed": 2, "skipped": 1, "rejected": 0})
        again = self.refresh({"alpha": body, "beta": payload("b")})
        self.assertEqual(again["detail"]["counts"], {"committed": 0, "skipped": 3, "rejected": 0})

    def test_summary_retains_success_beyond_history_window_without_cron_reads(self):
        good = self.refresh({"alpha": payload("a"), "beta": payload("b")})
        for _ in range(51):
            failed = self.refresh({"alpha": TimeoutError("Offline"), "beta": TimeoutError("Offline")})
            self.assertEqual(failed["status"], "failed")
        self.assertFalse(any(row["status"] == "succeeded" for row in runs.list_runs(self.sid)))
        with patch.object(upkeep, "_jobs", side_effect=AssertionError("Guest must not read cron")) as cron:
            summary = self.summary()
        cron.assert_not_called()
        self.assertIsNotNone(summary["last_success_at"])
        self.assertEqual(summary["sources"][0]["last_success_at"], good["detail"]["sources"][0]["last_success_at"])
        self.assertEqual(summary["sources"][0]["failure_reason"], "Offline")

    def test_index_keeps_q02_one_listing_and_unlinked_zero_listing(self):
        self.refresh({"alpha": payload("a"), "beta": TimeoutError("Offline")})
        with patch.object(upkeep, "_jobs", return_value={"jobs": [], "count": 0}) as cron:
            unlinked = projects.list_spaces()
            self.assertEqual(cron.call_count, 0)
            with db.write() as conn:
                conn.execute("INSERT INTO upkeep_links VALUES(?, 'fixture-linked-job', 'feed', ?, 'user')", (self.sid, db.now()))
            linked = projects.list_spaces()
            self.assertEqual(cron.call_count, 1)
        self.assertIn("sources", unlinked[0]["freshness"])
        self.assertEqual(linked[0]["freshness"]["sources"], unlinked[0]["freshness"]["sources"])


class Q15ToolTests(ToolCase):
    def test_public_tool_detail_reports_partial_source_success(self):
        sid = self.create(manifest={"upkeep": {"handler": "feed", "sources": [source("alpha"), source("beta")]}})["space"]
        with patch.object(feeds, "fetch", side_effect=[payload("a"), TimeoutError("Offline")]):
            run = runs.start_refresh(sid, trigger="chat", actor="agent:demo", wait=True)
        self.assertEqual(run["status"], "failed")
        detail = self.ok("spaces_get", space=sid)
        self.assertIsNotNone(detail["freshness"]["last_success_at"])
        self.assertEqual(detail["collections"]["alpha"], 1)
        self.assertEqual(detail["freshness"]["sources"][1]["failure_reason"], "Offline")


class Q15InspectionFreshnessTests(CoreCase):
    def test_passive_inspection_serves_the_same_freshness_summary_read_only(self):
        sid = projects.create_space("Feed", owner="Demo", author="agent:demo", files={"index.html": "<main>x</main>"})["id"]
        live = runs.freshness(sid, include_upkeep=False)
        conn = inspection._open_snapshot()
        self.addCleanup(conn.close)
        adapter = inspection.PassiveAdapter(inspection.Snapshot(conn, sid, 1))
        reply = adapter.call("freshness", {})
        self.assertEqual(reply, {"ok": True, "result": live, "outcome": {"status": "success"}})
        self.assertEqual(adapter.call("freshness", {"extra": 1})["ok"], False)
