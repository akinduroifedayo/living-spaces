from __future__ import annotations

import copy
import hashlib
import http.server
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
from urllib.request import urlopen

import httpx

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "src" / "living-spaces"
FIXTURES = Path(__file__).parent / "fixtures" / "feeds"
sys.path.insert(0, str(PACKAGE))

import living_spaces_core as core
from living_spaces_core import db, feeds, runs, schedules
from living_spaces_core.errors import SpacesError

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
        self.grants = types.SimpleNamespace(check=self.check)
        for name, module in (("projects", self.projects), ("records", self.records), ("grants", self.grants)):
            item = patch.object(core, name, module, create=True)
            item.start()
            self.addCleanup(item.stop)
        self.fetch = Mock(return_value=(FIXTURES / "research.rss").read_bytes())
        item = patch.object(feeds, "fetch", self.fetch)
        item.start()
        self.addCleanup(item.stop)

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
        client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=payload)))
        with patch.object(feeds, "fetch", HTTP_FETCH), patch.object(feeds.httpx, "Client", return_value=client):
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

    def test_manual_refresh_from_local_server_has_provenance_and_timestamps(self):
        body = (FIXTURES / "research.rss").read_bytes()

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        try:
            server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        except PermissionError as exc:
            self.skipTest(f"Sandbox forbids binding the local HTTP fixture: {exc}")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            def local_fetch(sid, url):
                with urlopen(f"http://127.0.0.1:{server.server_port}/feed", timeout=3) as response:
                    return response.read()

            self.fetch.side_effect = local_fetch
            run = self.refresh()
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
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

    def test_denied_absent_revoked_or_narrow_grant_is_blocked_without_fetch(self):
        for status in ("denied", None, "revoked", "requested"):
            with self.subTest(status=status):
                self.grant_status = status
                run = self.refresh()
                self.assertEqual(run["status"], "blocked")
                self.assertEqual(run["detail"]["reason"], "not_granted")
        self.grant_status = "granted"
        self.manifest["upkeep"]["sources"].append(self.source("other", "other.example"))
        self.assertEqual(self.refresh()["status"], "blocked")
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
        with db.write() as conn:
            conn.execute("INSERT INTO schedules(space,status,cadence,timezone,next_run_at) VALUES('research-desk','requested','0 * * * *','UTC',?)", (db.now() + 3600,))
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

    def test_bad_source_does_not_hide_another_sources_missing_host_grant(self):
        self.manifest["upkeep"]["sources"] = [self.source("bad"), self.source("denied", "other.example")]
        self.manifest["upkeep"]["sources"][0]["url"] = "http://research.example/feed"
        self.assertEqual(self.refresh()["status"], "blocked")
        self.fetch.assert_not_called()

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
        too_many = b"<rss><channel>" + b"<item><guid>demo</guid></item>" * 201 + b"</channel></rss>"
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

    def test_production_fetch_uses_streaming_timeout_and_per_request_grants(self):
        requests = []

        def serve(request):
            requests.append(request)
            if request.url.path == "/feed":
                return httpx.Response(302, headers={"location": "/current"})
            return httpx.Response(200, content=(FIXTURES / "research.rss").read_bytes())

        client = httpx.Client(transport=httpx.MockTransport(serve))
        check = Mock(side_effect=self.check)
        with patch.object(feeds.httpx, "Client", return_value=client) as factory, patch.object(self.grants, "check", check):
            payload = HTTP_FETCH("research-desk", "https://research.example/feed")
        factory.assert_called_once_with(timeout=20.0, follow_redirects=False)
        self.assertEqual(len(requests), 2)
        self.assertEqual(len(feeds.parse(payload)), 2)
        self.assertEqual(check.call_count, 2)

    def test_off_host_redirect_is_refused_even_if_other_host_is_also_granted(self):
        self.allowed.add("other.example")
        requests = []

        def serve(request):
            requests.append(request)
            return httpx.Response(302, headers={"location": "https://other.example/feed"})

        client = httpx.Client(transport=httpx.MockTransport(serve))
        with patch.object(feeds.httpx, "Client", return_value=client):
            with self.assertRaisesRegex(SpacesError, "changed host"):
                HTTP_FETCH("research-desk", "https://research.example/feed")
        self.assertEqual(len(requests), 1)

    def test_http_and_credentialed_sources_are_refused_before_request(self):
        for url in ("http://research.example/feed", "https://demo:example@research.example/feed"):
            with self.subTest(url=url), patch.object(feeds.httpx, "Client") as factory:
                with self.assertRaises(SpacesError):
                    HTTP_FETCH("research-desk", url)
                factory.assert_not_called()

    def test_streaming_body_limit(self):
        client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"x" * (feeds.MAX_BYTES + 1))))
        with patch.object(feeds.httpx, "Client", return_value=client):
            with self.assertRaises(SpacesError) as caught:
                HTTP_FETCH("research-desk", "https://research.example/feed")
        self.assertEqual(caught.exception.code, "limit")


class ScheduleTests(UpkeepCase):
    def cron(self):
        hermes = Path.home() / ".hermes" / "hermes-agent"
        self.assertTrue(Path(os.environ["HERMES_HOME"]).is_relative_to(ROOT / ".run"))
        sys.path.insert(0, str(hermes))
        self.addCleanup(sys.path.remove, str(hermes))
        return schedules._cron()

    def request(self):
        return schedules.request_schedule("research-desk", cadence="0 * * * *", timezone="America/Chicago", purpose="Public demo research", actor="agent:demo")

    def test_request_does_not_import_cron_create_job_or_write_shim(self):
        with patch.object(schedules, "_cron") as cron:
            result = self.request()
        cron.assert_not_called()
        self.assertEqual(result["status"], "requested")
        self.assertIsNone(result["cron_job_id"])
        self.assertFalse((self.home / "cron" / "jobs.json").exists())
        self.assertFalse((self.home / "scripts").exists())

    def test_native_schedule_approve_pause_resume_archive_and_delete_in_temp_home(self):
        jobs = self.cron()
        self.request()
        with jobs.use_cron_store(self.home):
            result = schedules.decide_schedule("research-desk", "approve")
            self.assertEqual(result["status"], "active", result)
            job_id = result["cron_job_id"]
            cron_file = self.home / "cron" / "jobs.json"
            self.assertTrue(cron_file.exists())
            persisted = json.loads(cron_file.read_text())
            job = jobs.get_job(job_id)
            self.assertIn(job_id, json.dumps(persisted))
            self.assertEqual(job["name"], "living-spaces:research-desk")
            self.assertEqual(job["script"], "living-spaces-refresh-research-desk.py")
            self.assertEqual(job["prompt"], "")
            self.assertTrue(job["no_agent"])
            self.assertTrue(job["catch_up"])
            self.assertEqual(job["deliver"], "local")
            self.assertEqual(job["timezone"], "America/Chicago")
            self.assertEqual(result["next_run_at"], schedules._next(job))
            shim = self.home / "scripts" / job["script"]
            self.assertTrue(shim.exists())
            script = shim.read_text()
            self.assertIn(repr(str(PACKAGE)), script)
            self.assertNotIn("__LIVING_SPACES_", script)
            self.assertEqual(schedules.decide_schedule("research-desk", "approve")["cron_job_id"], job_id)
            self.assertEqual(len(jobs.load_jobs()), 1)
            self.assertEqual(schedules.pause_schedule("research-desk", True, actor="user")["status"], "paused")
            self.assertFalse(jobs.get_job(job_id)["enabled"])
            self.assertIsNone(schedules.get_schedule("research-desk")["next_run_at"])
            self.assertEqual(schedules.pause_schedule("research-desk", False, actor="user")["status"], "active")
            self.assertTrue(jobs.get_job(job_id)["enabled"])
            with db.write() as conn:
                conn.execute("UPDATE spaces SET status='archived'")
            schedules.on_archive("research-desk")
            self.assertFalse(jobs.get_job(job_id)["enabled"])
            with self.assertRaises(SpacesError) as caught:
                schedules.pause_schedule("research-desk", False, actor="user")
            self.assertEqual(caught.exception.code, "archived")
            with db.write() as conn:
                conn.execute("UPDATE spaces SET status='active'")
            schedules.on_unarchive("research-desk")
            self.assertFalse(jobs.get_job(job_id)["enabled"])
            schedules.on_delete("research-desk")
            self.assertIsNone(jobs.get_job(job_id))
            self.assertFalse(shim.exists())
            self.assertIsNone(schedules.get_schedule("research-desk"))
            self.assertEqual(jobs.load_jobs(), [])

    def test_missing_cron_disables_with_persisted_visible_reason(self):
        self.request()
        with patch.object(schedules, "_cron", side_effect=ImportError("demo cron unavailable")):
            result = schedules.decide_schedule("research-desk", "approve")
        self.assertEqual(result["status"], "disabled")
        self.assertIn("demo cron unavailable", result["reason"])
        self.assertEqual(schedules.get_schedule("research-desk")["reason"], result["reason"])
        self.assertIsNone(result["cron_job_id"])
        self.assertFalse((self.home / "scripts").exists())

    def test_deny_never_creates_a_job(self):
        self.request()
        with patch.object(schedules, "_cron") as factory:
            result = schedules.decide_schedule("research-desk", "deny")
        factory.return_value.create_job.assert_not_called()
        self.assertEqual(result["status"], "disabled")
        self.assertIn("denied", result["reason"])

    def test_native_get_refreshes_next_run_and_missing_job_is_visible(self):
        jobs = self.cron()
        self.request()
        with jobs.use_cron_store(self.home):
            result = schedules.decide_schedule("research-desk", "approve")
            job_id = result["cron_job_id"]
            try:
                updated = jobs.update_job(job_id, {"next_run_at": "2027-01-01T12:00:00+00:00"})
                self.assertEqual(schedules.get_schedule("research-desk")["next_run_at"], schedules._next(updated))
                jobs.remove_job(job_id)
                disabled = schedules.get_schedule("research-desk")
                self.assertEqual(disabled["status"], "disabled")
                self.assertIn("missing", disabled["reason"])
            finally:
                schedules.remove_schedule("research-desk")

    def test_re_request_pauses_old_job_and_requires_new_approval(self):
        jobs = self.cron()
        self.request()
        with jobs.use_cron_store(self.home):
            first = schedules.decide_schedule("research-desk", "approve")
            try:
                changed = schedules.request_schedule("research-desk", cadence="0 8 * * *", timezone="UTC", purpose="Daily public feed", actor="agent:demo")
                self.assertEqual(changed["status"], "requested")
                self.assertFalse(jobs.get_job(first["cron_job_id"])["enabled"])
                with self.assertRaises(SpacesError):
                    schedules.pause_schedule("research-desk", False, actor="user")
                second = schedules.decide_schedule("research-desk", "approve")
                self.assertNotEqual(first["cron_job_id"], second["cron_job_id"])
                self.assertIsNone(jobs.get_job(first["cron_job_id"]))
                self.assertEqual(len(jobs.load_jobs()), 1)
            finally:
                schedules.remove_schedule("research-desk")

    def test_create_job_failure_removes_shim_and_reports_disabled(self):
        self.request()
        with patch.object(schedules, "_cron") as factory:
            factory.return_value.create_job.side_effect = ValueError("Invalid cadence")
            result = schedules.decide_schedule("research-desk", "approve")
        self.assertEqual(result["status"], "disabled")
        self.assertIn("Invalid cadence", result["reason"])
        self.assertFalse((self.home / "scripts" / "living-spaces-refresh-research-desk.py").exists())

    def test_delete_fails_visibly_when_native_cron_cannot_be_loaded(self):
        jobs = self.cron()
        self.request()
        with jobs.use_cron_store(self.home):
            active = schedules.decide_schedule("research-desk", "approve")
            try:
                with patch.object(schedules, "_cron", side_effect=ImportError("demo cron unavailable")):
                    with self.assertRaises(SpacesError) as caught:
                        schedules.remove_schedule("research-desk")
                self.assertEqual(caught.exception.code, "blocked")
                self.assertIsNotNone(jobs.get_job(active["cron_job_id"]))
                self.assertTrue((self.home / "scripts" / "living-spaces-refresh-research-desk.py").exists())
            finally:
                schedules.remove_schedule("research-desk")

    def test_bad_timezone_or_missing_cadence_or_unapproved_resume_is_rejected(self):
        with self.assertRaises(SpacesError):
            schedules.request_schedule("research-desk", cadence="", timezone="UTC", purpose="Demo", actor="user")
        with self.assertRaises(SpacesError):
            schedules.request_schedule("research-desk", cadence="0 * * * *", timezone="Not/AZone", purpose="Demo", actor="user")
        self.request()
        with self.assertRaises(SpacesError):
            schedules.pause_schedule("research-desk", False, actor="user")

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
        self.assertEqual(schedules.CATCH_UP_POLICY, "Runs one current refresh when Hermes wakes. Missed intervals aren't replayed.")


if __name__ == "__main__":
    unittest.main()
