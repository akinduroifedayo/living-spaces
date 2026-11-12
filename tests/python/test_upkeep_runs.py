from __future__ import annotations

import copy
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "src" / "living-spaces"
FIXTURES = Path(__file__).parent / "fixtures" / "feeds"
sys.path.insert(0, str(PACKAGE))

import living_spaces_core as core
from living_spaces_core import db, feeds, runs, upkeep
from living_spaces_core.errors import SpacesError
from .feed_transport_support import PUBLIC, PinnedTransport, Response

HTTP_FETCH = feeds.fetch


class UpkeepCase(unittest.TestCase):
    def setUp(self):
        (ROOT / ".run").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="upkeep-", dir=ROOT / ".run")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.env = patch.dict(os.environ, {"LIVING_SPACES_DB": str(self.home / "spaces.db"), "HERMES_HOME": str(self.home)})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.manifest = {"upkeep": {"handler": "feed", "sources": [self.source("demo")]}}
        self.allowed = {"research.example"}
        self.grant_status = "granted"
        with db.write() as conn:
            conn.execute("INSERT INTO spaces(id,name,owner,status,created_at,updated_at) VALUES('research-desk','Research Desk','Demo','active',?,?)", (db.now(), db.now()))
        self.projects = types.SimpleNamespace(get_space=self.get_space, bundle=lambda sid: {"manifest": copy.deepcopy(self.manifest)})
        self.records = types.SimpleNamespace(upsert_source=self.upsert_source, upsert_sources=self.upsert_sources)
        self.grants = types.SimpleNamespace(
            check=self.check,
            _check=lambda conn, sid, capability, scope_need=None: (
                self.grant_status == "granted"
                and set((scope_need or {}).get("hosts", [])).issubset(self.allowed)
            ),
        )
        for name, module in (("projects", self.projects), ("records", self.records), ("grants", self.grants)):
            item = patch.object(core, name, module, create=True)
            item.start()
            self.addCleanup(item.stop)
        self.fetch = Mock(return_value=(FIXTURES / "research.rss").read_bytes())
        item = patch.object(feeds, "fetch", self.fetch)
        item.start()
        self.addCleanup(item.stop)
        self.fetch_patch = item

    @staticmethod
    def source(source_id, host="research.example"):
        return {"id": source_id, "url": f"https://{host}/feed", "collection": "papers"}

    def get_space(self, sid):
        with db.read() as conn:
            row = conn.execute("SELECT * FROM spaces WHERE id=?", (sid,)).fetchone()
        if row is None:
            raise SpacesError("not_found", "Space not found")
        return dict(row)

    def check(self, sid, capability, scope_need=None):
        self.get_space(sid)
        if self.grant_status != "granted" or not set((scope_need or {}).get("hosts", [])).issubset(self.allowed):
            raise SpacesError("not_granted", "Refresh is not granted", capability=capability)

    def upsert_sources(self, sid, collection, entries, *, actor):
        counts = {"added": 0, "updated": 0, "unchanged": 0}
        with db.write() as conn:
            db.space(conn, sid, writable=True)
            for rid, source, source_meta in entries:
                result = self.records.upsert_source(conn, sid, collection, rid, source, source_meta, actor=actor)
                counts[result] += 1
        return counts

    def upsert_source(self, conn, sid, collection, rid, source, source_meta, *, actor):
        row = conn.execute("SELECT * FROM records WHERE space=? AND collection=? AND id=?", (sid, collection, rid)).fetchone()
        if row and json.loads(row["source"]) == source:
            return "unchanged"
        now = db.now()
        rev = row["rev"] + 1 if row else 1
        conn.execute("INSERT INTO records(space,collection,id,source,source_meta,rev,created_at,updated_at,updated_by) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(space,collection,id) DO UPDATE SET source=excluded.source,source_meta=excluded.source_meta,rev=excluded.rev,updated_at=excluded.updated_at,updated_by=excluded.updated_by", (
            sid, collection, rid, json.dumps(source), json.dumps(source_meta), rev, now, now, actor,
        ))
        conn.execute("INSERT INTO changes(space,collection,record_id,op,rev,actor,at) VALUES(?,?,?,'source',?,?,?)", (sid, collection, rid, rev, actor, now))
        return "updated" if row else "added"

    def refresh(self):
        return runs.start_refresh("research-desk", trigger="manual", actor="user", wait=True)

    def stored(self):
        with db.read() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM records ORDER BY id")]

    def wait_run(self, run_id):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            run = runs.get_run(run_id)
            if run["status"] not in ("queued", "running"):
                return run
            time.sleep(0.01)
        self.fail("Refresh worker did not finish")


class RunTests(UpkeepCase):
    def test_manual_refresh_through_injected_https_transport_has_provenance(self):
        payload = (FIXTURES / "research.rss").read_bytes()
        self.fetch_patch.stop()
        with PinnedTransport([Response(payload)]).installed():
            run = self.refresh()
        self.assertEqual(run["status"], "succeeded")
        self.assertEqual(run["changed"]["added"], 2)
        for row in self.stored():
            meta = json.loads(row["source_meta"])
            self.assertEqual(meta["handler"], "feed")
            self.assertEqual(meta["source_id"], "demo")
            self.assertEqual(meta["url"], "https://research.example/feed")
            self.assertIsInstance(meta["source_updated"], float)
            self.assertGreaterEqual(meta["fetched_at"], run["started_at"])
            self.assertLessEqual(meta["fetched_at"], run["ended_at"])
            self.assertIsInstance(json.loads(row["source"])["published"], float)
            self.assertGreater(row["created_at"], 0)

    def test_manual_refresh_has_provenance_and_timestamps(self):
        body = (FIXTURES / "research.rss").read_bytes()
        self.fetch_patch.stop()
        with PinnedTransport([Response(body)]).installed():
            run = self.refresh()
        self.assertEqual(run["status"], "succeeded")
        self.assertEqual(run["changed"], {"added": 2, "updated": 0, "unchanged": 0, "removed": 0})
        row = self.stored()[0]
        meta = json.loads(row["source_meta"])
        self.assertEqual(meta["handler"], "feed")
        self.assertEqual(meta["source_id"], "demo")
        self.assertEqual(meta["url"], "https://research.example/feed")
        self.assertIsInstance(meta["fetched_at"], float)
        self.assertIsInstance(meta["source_updated"], float)
        self.assertGreater(row["created_at"], 0)
        self.assertEqual(row["updated_by"], "user")
        self.assertLess(run["source_as_of"], run["ended_at"])

    def test_same_feed_is_unchanged_and_user_note_survives_update(self):
        self.refresh()
        with db.write() as conn:
            conn.execute("UPDATE records SET data=?", (json.dumps({"note": "Synthetic demo note", "status": "reading"}),))
        self.assertEqual(self.refresh()["changed"]["unchanged"], 2)
        self.fetch.return_value = self.fetch.return_value.replace(b"Small Models", b"Updated Models")
        run = self.refresh()
        self.assertEqual(run["changed"]["updated"], 1)
        for row in self.stored():
            self.assertEqual(json.loads(row["data"]), {"note": "Synthetic demo note", "status": "reading"})

    def test_fetch_failure_retains_every_existing_field(self):
        self.refresh()
        before = self.stored()
        self.fetch.side_effect = TimeoutError("Public feed timed out")
        run = self.refresh()
        self.assertEqual(run["status"], "failed")
        self.assertIn("timed out", run["error"])
        self.assertEqual(self.stored(), before)
        self.assertFalse(run["detail"]["sources"][0]["ok"])

    def test_partial_source_failure_counts_success_and_retains_prior_records(self):
        self.refresh()
        before = self.stored()
        self.manifest["upkeep"]["sources"].append(self.source("second"))
        self.fetch.side_effect = [OSError("Source unavailable"), (FIXTURES / "research.atom").read_bytes()]
        run = self.refresh()
        self.assertEqual(run["status"], "failed")
        self.assertEqual(run["changed"]["added"], 1)
        self.assertEqual([s["ok"] for s in run["detail"]["sources"]], [False, True])
        stored = {row["id"]: row for row in self.stored()}
        for row in before:
            self.assertEqual(stored[row["id"]], row)

    def test_internet_access_off_is_blocked_without_fetch(self):
        for status in ("denied", None, "revoked", "requested"):
            with self.subTest(status=status):
                self.grant_status = status
                run = self.refresh()
                self.assertEqual(run["status"], "blocked")
                self.assertEqual(run["detail"]["reason"], "not_granted")
        self.fetch.assert_not_called()
        self.assertEqual(self.stored(), [])

    def test_archived_or_missing_or_unknown_handler_is_blocked(self):
        self.manifest = {}
        self.assertEqual(self.refresh()["detail"]["reason"], "no_handler")
        self.manifest = {"upkeep": {"handler": "shell"}}
        self.assertEqual(self.refresh()["detail"]["reason"], "no_handler")
        with db.write() as conn:
            conn.execute("UPDATE spaces SET status='archived'")
        self.assertEqual(self.refresh()["detail"]["reason"], "archived")
        self.fetch.assert_not_called()

    def test_concurrent_starts_dedupe_and_daemon_worker_does_one_fetch(self):
        entered, release = threading.Event(), threading.Event()

        def fetch(*args):
            self.assertTrue(threading.current_thread().daemon)
            entered.set()
            if not release.wait(5):
                raise TimeoutError("Test release timed out")
            return (FIXTURES / "research.rss").read_bytes()

        self.fetch.side_effect = fetch
        first = runs.start_refresh("research-desk", trigger="manual", actor="user")
        try:
            self.assertTrue(entered.wait(3))
            result = []
            threads = [threading.Thread(target=lambda: result.append(runs.start_refresh("research-desk", trigger="chat", actor="agent:demo"))) for _ in range(8)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(3)
            self.assertEqual(len(result), 8)
            self.assertEqual({run["id"] for run in result}, {first["id"]})
            self.assertEqual(self.fetch.call_count, 1)
        finally:
            release.set()
            final = self.wait_run(first["id"])
        self.assertEqual(final["status"], "succeeded")
        self.assertEqual(len(runs.list_runs("research-desk")), 1)

    def test_cancel_running_during_fetch_prevents_delivery_and_second_source(self):
        self.manifest["upkeep"]["sources"].append(self.source("second"))

        def fetch(*args):
            self.assertEqual(runs.cancel_pending("research-desk", "refresh revoked"), 1)
            return (FIXTURES / "research.rss").read_bytes()

        self.fetch.side_effect = fetch
        run = self.refresh()
        self.assertEqual(run["status"], "canceled")
        self.assertEqual(run["detail"]["cancel_reason"], "refresh revoked")
        self.assertEqual(self.fetch.call_count, 1)
        self.assertEqual(self.stored(), [])

    def test_cancel_queued_prevents_worker_fetch(self):
        with patch.object(runs.threading.Thread, "start"):
            run = runs.start_refresh("research-desk", trigger="manual", actor="user")
        self.assertEqual(run["status"], "queued")
        self.assertEqual(runs.cancel_pending("research-desk", "archived"), 1)
        runs._work(run["id"], self.manifest["upkeep"])
        self.assertEqual(runs.get_run(run["id"])["status"], "canceled")
        self.fetch.assert_not_called()

    def test_stale_run_recovery_and_old_worker_cannot_restart(self):
        with patch.object(runs.threading.Thread, "start"):
            old = runs.start_refresh("research-desk", trigger="manual", actor="user")
        with db.write() as conn:
            conn.execute("UPDATE runs SET status='running',heartbeat_at=? WHERE id=?", (db.now() - 121, old["id"]))
        new = self.refresh()
        self.assertNotEqual(old["id"], new["id"])
        self.assertEqual(new["status"], "succeeded")
        interrupted = runs.get_run(old["id"])
        self.assertEqual(interrupted["status"], "failed")
        self.assertEqual(interrupted["error"], "interrupted")
        runs._work(old["id"], self.manifest["upkeep"])
        self.assertEqual(self.fetch.call_count, 1)

    def test_recent_heartbeat_preserves_long_running_run(self):
        with patch.object(runs.threading.Thread, "start"):
            run = runs.start_refresh("research-desk", trigger="manual", actor="user")
        with db.write() as conn:
            conn.execute("UPDATE runs SET queued_at=?,heartbeat_at=?,status='running' WHERE id=?", (db.now() - 1000, db.now(), run["id"]))
        self.assertEqual(self.refresh()["id"], run["id"])
        self.fetch.assert_not_called()

    def test_freshness_keeps_last_success_and_latest_attempt_separate(self):
        empty = runs.freshness("research-desk")
        self.assertTrue(all(value is None for value in empty.values()))
        success = self.refresh()
        self.fetch.side_effect = OSError("Unavailable")
        failed = self.refresh()
        with patch.object(upkeep, "summary", return_value={"next_run_at": db.now() + 3600}):
            fresh = runs.freshness("research-desk")
        self.assertEqual(fresh["last_success_at"], success["ended_at"])
        self.assertEqual(fresh["last_attempt_at"], failed["queued_at"])
        self.assertEqual(fresh["last_attempt_status"], "failed")
        self.assertEqual(fresh["source_as_of"], success["source_as_of"])
        self.assertGreater(fresh["next_run_at"], failed["ended_at"])

    def test_revoke_during_fetch_without_cancel_hook_still_blocks_writes(self):
        def fetch(*args):
            self.grant_status = "revoked"
            return (FIXTURES / "research.rss").read_bytes()

        self.fetch.side_effect = fetch
        self.assertEqual(self.refresh()["status"], "failed")
        self.assertEqual(self.stored(), [])

    def test_bad_xml_keeps_last_good_records(self):
        self.refresh()
        before = self.stored()
        self.fetch.return_value = b'<!DOCTYPE rss [<!ENTITY secret "oops">]><rss><channel/></rss>'
        self.assertEqual(self.refresh()["status"], "failed")
        self.assertEqual(self.stored(), before)

    def test_unknown_run_and_invalid_arguments_use_core_errors(self):
        with self.assertRaises(SpacesError) as caught:
            runs.get_run("unknown")
        self.assertEqual(caught.exception.code, "not_found")
        with self.assertRaises(SpacesError):
            runs.start_refresh("research-desk", trigger="unknown", actor="user")
        with self.assertRaises(SpacesError):
            runs.list_runs("research-desk", limit=0)

    def test_heartbeat_advances_while_fetch_is_waiting(self):
        entered, release = threading.Event(), threading.Event()

        def fetch(*args):
            entered.set()
            if not release.wait(5):
                raise TimeoutError("Test release timed out")
            return (FIXTURES / "research.rss").read_bytes()

        self.fetch.side_effect = fetch
        with patch.object(runs, "HEARTBEAT_SECONDS", 0.01):
            run = runs.start_refresh("research-desk", trigger="manual", actor="user")
            try:
                self.assertTrue(entered.wait(3))
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    current = runs.get_run(run["id"])
                    if current["heartbeat_at"] > current["started_at"]:
                        break
                    time.sleep(0.01)
                self.assertGreater(current["heartbeat_at"], current["started_at"])
            finally:
                release.set()
                final = self.wait_run(run["id"])
        self.assertEqual(final["status"], "succeeded")

    def test_archiving_during_fetch_prevents_source_writes(self):
        def fetch(*args):
            with db.write() as conn:
                conn.execute("UPDATE spaces SET status='archived'")
            return (FIXTURES / "research.rss").read_bytes()

        self.fetch.side_effect = fetch
        self.assertEqual(self.refresh()["status"], "canceled")
        self.assertEqual(self.stored(), [])

    def test_bad_source_fails_visibly_without_hiding_the_next_source(self):
        self.manifest["upkeep"]["sources"] = [self.source("bad"), self.source("other", "other.example")]
        self.manifest["upkeep"]["sources"][0]["url"] = "http://research.example/feed"
        run = self.refresh()
        self.assertEqual(run["status"], "failed")
        self.assertEqual([source["ok"] for source in run["detail"]["sources"]], [False, True])
        self.fetch.assert_called_once_with("research-desk", "https://other.example/feed")

    def test_source_write_failure_reports_zero_committed_changes(self):
        original = self.records.upsert_source
        calls = 0

        def fail_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("Synthetic storage failure")
            return original(*args, **kwargs)

        self.records.upsert_source = fail_second
        run = self.refresh()
        self.assertEqual(run["status"], "failed")
        self.assertEqual(calls, 2)
        self.assertEqual(run["changed"], {"added": 0, "updated": 0, "unchanged": 0, "removed": 0})
        source = run["detail"]["sources"][0]
        self.assertEqual({key: source[key] for key in ("added", "updated", "unchanged")},
                         {"added": 0, "updated": 0, "unchanged": 0})
        self.assertEqual(self.stored(), [])
        with db.read() as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM changes").fetchone()[0], 0)

    def test_source_write_failure_rolls_back_all_source_changes(self):
        self.refresh()
        before = self.stored()
        self.fetch.return_value = self.fetch.return_value.replace(b"synthetic", b"revised synthetic")
        original = self.records.upsert_source
        calls = 0

        def fail_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("Synthetic storage failure")
            return original(*args, **kwargs)

        self.records.upsert_source = fail_second
        self.assertEqual(self.refresh()["status"], "failed")
        self.assertEqual(calls, 2)
        self.assertEqual(self.stored(), before, "A failed source must roll back all source changes")


class FeedTests(UpkeepCase):
    def test_atom_arxiv_shape_maps_fields_dates_and_stable_ids(self):
        rows = feeds.parse((FIXTURES / "research.atom").read_bytes())
        rid, item = rows[0]
        self.assertEqual(rid, "src_" + hashlib.sha1(b"https://research.example/abs/demo.0001v1").hexdigest()[:16])
        self.assertEqual(item["authors"], ["Ada Example", "Lin Sample"])
        self.assertEqual(item["url"], "https://research.example/abs/demo.0001")
        self.assertIsInstance(item["published"], float)
        self.assertGreater(item["updated"], item["published"])
        self.assertEqual(set(item), {"title", "summary", "url", "authors", "published", "updated"})

    def test_rss_maps_authors_and_link_fallback_for_id(self):
        payload = b'<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/"><channel><item><title>Demo</title><link>https://research.example/1</link><dc:creator>Ada Example</dc:creator></item></channel></rss>'
        rid, item = feeds.parse(payload)[0]
        self.assertEqual(rid, "src_" + hashlib.sha1(b"https://research.example/1").hexdigest()[:16])
        self.assertEqual(item["authors"], ["Ada Example"])
        self.assertIsNone(item["updated"])

    def test_doctype_and_entity_are_rejected_in_utf8_utf16_and_utf32(self):
        for text in ('<!DOCTYPE rss><rss><channel/></rss>', '<!ENTITY example "demo"><rss><channel/></rss>'):
            for encoding in ("utf-8", "utf-16", "utf-32"):
                with self.subTest(text=text, encoding=encoding):
                    with self.assertRaisesRegex(SpacesError, "forbidden"):
                        feeds.parse(text.encode(encoding))

    def test_bad_xml_format_or_missing_entry_identity_is_rejected(self):
        for payload in (b"<rss>", b"<html/>", b"<rss><channel><item><title>Demo</title></item></channel></rss>"):
            with self.subTest(payload=payload):
                with self.assertRaises(SpacesError):
                    feeds.parse(payload)

    def test_entry_and_body_limits_are_visible(self):
        too_many = b"<rss><channel>" + b"<item><guid>demo</guid></item>" * (feeds.MAX_ENTRIES + 1) + b"</channel></rss>"
        for payload in (too_many, b"x" * (feeds.MAX_BYTES + 1)):
            with self.subTest(size=len(payload)):
                with self.assertRaises(SpacesError) as caught:
                    feeds.parse(payload)
                self.assertEqual(caught.exception.code, "limit")
                self.assertGreater(caught.exception.extra["actual"], caught.exception.extra["limit"])

    def test_parse_all_entries_before_writing_any(self):
        payload = (FIXTURES / "research.rss").read_bytes()
        self.fetch.return_value = payload.replace(b"</channel>", b"<item><title>No identity</title></item></channel>")
        run = self.refresh()
        self.assertEqual(run["status"], "failed")
        self.assertEqual(self.stored(), [])

    def test_no_entries_is_success_with_no_change_and_fetched_time(self):
        self.fetch.return_value = b"<rss><channel/></rss>"
        run = self.refresh()
        self.assertEqual(run["status"], "succeeded")
        self.assertEqual(run["changed"], {"added": 0, "updated": 0, "unchanged": 0, "removed": 0})
        self.assertIsInstance(run["source_as_of"], float)

    def test_production_fetch_uses_streaming_timeout_and_per_request_net_checks(self):
        transport = PinnedTransport([
            Response(status=302, headers={"location": "/current"}),
            Response((FIXTURES / "research.rss").read_bytes()),
        ])
        requests = transport.requests

        def check(sid, capability, scope_need=None):
            self.check(sid, capability, scope_need)
            transport.events.append(("grant", sid, capability, scope_need))

        with transport.installed(), patch.object(self.grants, "check", check):
            payload = HTTP_FETCH("research-desk", "https://research.example/feed")
        self.assertEqual(len(transport.connections), 2)
        for host, port, ip, timeout in transport.connections:
            self.assertEqual((host, port, ip), ("research.example", 443, PUBLIC))
            self.assertGreater(timeout, 0)
            self.assertLessEqual(timeout, 20)
        self.assertEqual(len(requests), 2)
        self.assertEqual(len(feeds.parse(payload)), 2)
        self.assertEqual([request["target"] for request in requests], ["/feed", "/current"])
        grant = ("grant", "research-desk", "net", None)
        for index, event in enumerate(transport.events):
            if event[0] == "request":
                self.assertGreater(index, 0)
                self.assertEqual(transport.events[index - 1], grant)
                self.assertEqual(event[1]["headers"]["Host"], "research.example")
        redirect = transport.events.index(("response", requests[0], 302))
        next_connection = transport.events.index(("connect", transport.connections[1]), redirect + 1)
        self.assertLess(redirect, next_connection)
        self.assertIn(grant, transport.events[redirect + 1:next_connection])

    def test_off_host_redirect_is_refused(self):
        transport = PinnedTransport([Response(status=302, headers={"location": "https://other.example/feed"})])
        requests = transport.requests
        with transport.installed():
            with self.assertRaisesRegex(SpacesError, "changed host"):
                HTTP_FETCH("research-desk", "https://research.example/feed")
        self.assertEqual(len(requests), 1)

    def test_http_and_credentialed_sources_are_refused_before_request(self):
        for url in ("http://research.example/feed", "https://demo:example@research.example/feed"):
            transport = PinnedTransport([])
            factory = transport.factory
            with self.subTest(url=url), transport.installed():
                with self.assertRaises(SpacesError):
                    HTTP_FETCH("research-desk", url)
                factory.assert_not_called()

    def test_streaming_body_limit(self):
        with PinnedTransport([Response(b"x" * (feeds.MAX_BYTES + 1))]).installed():
            with self.assertRaises(SpacesError) as caught:
                HTTP_FETCH("research-desk", "https://research.example/feed")
        self.assertEqual(caught.exception.code, "limit")


class NativeCronTests(UpkeepCase):
    """Public-dispatch fixtures. Real host cron lifecycle is qualified separately in isolation."""

    def cron(self):
        from tests.python.review_customization_support import SyntheticContext

        self.ctx = SyntheticContext()
        jobs = self.ctx.cron
        upkeep.configure_context(self.ctx)
        with db.write() as conn:
            conn.execute("INSERT INTO revisions(space,rev,kind,manifest,files,author,summary,created_at) VALUES('research-desk',1,'create',?,'{}','user','',?)",
                         (json.dumps(self.manifest), db.now()))
            conn.execute("UPDATE spaces SET head_rev=1")
        return jobs

    def schedule(self, kind="feed", prompt=None):
        return upkeep.schedule_upkeep("research-desk", kind=kind, cadence="0 * * * *", timezone="America/Chicago",
                                      prompt=prompt, actor="agent:demo")

    def test_public_cron_feed_job_matches_get_upkeep(self):
        jobs = self.cron()
        shown = self.schedule()
        native = jobs.get_job(shown["link"]["cron_job_id"])
        self.assertTrue(native["no_agent"])
        self.assertEqual((native["deliver"], native["catch_up"], native["timezone"]), ("local", True, "America/Chicago"))
        self.assertEqual(shown["job"]["cadence"], native["schedule"]["expr"])
        self.assertEqual(shown["job"]["schedule_display"], native["schedule_display"])
        self.assertIsNone(shown["job"]["prompt"])
        self.assertEqual(shown["job"]["next_run_at"], datetime.fromisoformat(native["next_run_at"]).timestamp())
        self.assertEqual(shown["executions"], [])
        upkeep.upkeep_action("research-desk", "remove", actor="user")
        self.assertIsNone(jobs.get_job(native["id"]))

    def test_public_cron_agent_job_uses_ordinary_chat_cron_settings(self):
        jobs = self.cron()
        self.manifest = {"upkeep": {"handler": "agent", "prompt": "Update the public demo."}}
        shown = self.schedule(kind="agent", prompt="Update the public demo.")
        native = jobs.get_job(shown["link"]["cron_job_id"])
        self.assertFalse(native["no_agent"])
        self.assertIsNone(shown["job"]["prompt"])
        self.assertEqual(shown["job"]["prompt_preview"], native["prompt"][:100] + "...")
        for key in ("enabled_toolsets", "skills", "model", "provider", "script"):
            self.assertFalse(native.get(key), key)
        upkeep.upkeep_action("research-desk", "pause", actor="user")
        self.assertEqual(jobs.get_job(native["id"])["state"], "paused")
        upkeep.upkeep_action("research-desk", "remove", actor="user")

    def test_public_cron_one_shot_refresh_now(self):
        jobs = self.cron()
        self.manifest = {"upkeep": {"handler": "agent", "prompt": "Update the public demo."}}
        result = self.refresh()
        job = jobs.get_job(result["cron_job_id"])
        try:
            self.assertEqual(job["schedule"]["expr"], "in 1m")
            self.assertEqual(job["name"], "living-spaces:research-desk:once")
            self.assertFalse(job["no_agent"])
            self.assertEqual(job["deliver"], "local")
            self.assertIsNotNone(job["manual_run_at"])
            self.assertIsNone(job.get("enabled_toolsets"))
            self.assertIsNone(upkeep.get_upkeep("research-desk")["link"])
        finally:
            jobs.remove_job(job["id"])

    def test_catchup_dispatch_is_honestly_unavailable(self):
        jobs = self.cron()
        jid = self.schedule()["link"]["cron_job_id"]
        jobs.jobs[jid]["last_dispatch"] = {"kind": "catch_up"}
        run = runs.start_refresh("research-desk", trigger="schedule", actor="upkeep:schedule", wait=True)
        self.assertEqual(run["status"], "succeeded")
        self.assertNotIn("dispatch", run["detail"])
        self.assertIn("dispatch", upkeep.get_upkeep("research-desk")["unavailable"])
        upkeep.upkeep_action("research-desk", "remove", actor="user")

    def test_failed_feed_keeps_last_good_data_without_private_dispatch_metadata(self):
        self.cron()
        self.refresh()
        before = self.stored()
        self.schedule()
        self.fetch.side_effect = TimeoutError("Feed unavailable")
        run = runs.start_refresh("research-desk", trigger="schedule", actor="upkeep:schedule", wait=True)
        self.assertEqual(run["status"], "failed")
        self.assertNotIn("dispatch", run["detail"])
        self.assertEqual(self.stored(), before)
        upkeep.upkeep_action("research-desk", "remove", actor="user")

    def test_bad_timezone_cadence_or_kind_is_rejected_before_native_cron(self):
        for kwargs in ({"timezone": "Mars/Base"}, {"cadence": " "}, {"kind": "shell"}, {"kind": "agent", "prompt": " "},
                       {"kind": "feed", "prompt": "Feeds take no prompt"}):
            args = {"kind": "feed", "cadence": "0 * * * *", "timezone": "UTC", "prompt": None, "actor": "agent:demo", **kwargs}
            with self.subTest(kwargs=kwargs), patch.object(upkeep, "_call") as cron:
                with self.assertRaises(SpacesError) as error:
                    upkeep.schedule_upkeep("research-desk", **args)
                self.assertEqual(error.exception.code, "invalid")
                cron.assert_not_called()

    def test_shim_loads_by_path_waits_inline_and_is_silent_only_on_success(self):
        import contextlib
        import io

        script = (PACKAGE / "scripts" / "refresh_space.py").read_text().replace("__LIVING_SPACES_PACKAGE__", repr(str(PACKAGE))).replace("__LIVING_SPACES_SID__", repr("research-desk"))
        namespace = {"__name__": "test_refresh_shim"}
        exec(compile(script, "refresh-demo.py", "exec"), namespace)
        for result, expected in (({"status": "succeeded"}, 0), ({"status": "failed", "error": "Demo feed\nunavailable"}, 1), ({"status": "blocked", "detail": {"reason": "not_granted"}}, 1)):
            with self.subTest(result=result), patch.object(runs, "start_refresh", return_value=result) as start:
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(namespace["main"](), expected)
                start.assert_called_once_with("research-desk", trigger="schedule", actor="upkeep:schedule", wait=True)
                self.assertEqual(len(output.getvalue().splitlines()), expected)

    def test_upkeep_validation(self):
        for value in (None, [], {}, {"handler": "shell"}, {"handler": "agent"}, {"handler": "agent", "prompt": " "},
                      {"handler": "agent", "prompt": 3}):
            with self.subTest(upkeep=value), self.assertRaises(SpacesError) as error:
                upkeep.validate_upkeep(value)
            self.assertEqual(error.exception.code, "invalid")
        upkeep.validate_upkeep({"handler": "agent", "prompt": "a" * 8000})
        with self.assertRaises(SpacesError) as caught:
            upkeep.validate_upkeep({"handler": "agent", "prompt": "a" * 8001})
        self.assertEqual(caught.exception.code, "limit")
        upkeep.validate_upkeep({"handler": "feed", "sources": []})


if __name__ == "__main__":
    unittest.main()
