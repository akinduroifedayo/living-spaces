import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "living-spaces"))
from living_spaces_core import SpacesError, bridge, db, feeds, grants, limits, logs, projects, records, sessions


def json_bytes(value):
    return len(limits.dumps(value).encode("utf-8"))


def sized_object(size):
    return {"text": "x" * (size - json_bytes({"text": ""}))}


def feed_xml(count=1, title="Public paper"):
    items = "".join(f"<item><guid>paper-{i}</guid><title>{title}</title></item>" for i in range(count))
    return f"<rss><channel>{items}</channel></rss>".encode("utf-8")


class LimitCase(unittest.TestCase):
    def setUp(self):
        (ROOT / ".run").mkdir(exist_ok=True)
        temp = tempfile.TemporaryDirectory(prefix="limits-", dir=ROOT / ".run")
        self.addCleanup(temp.cleanup)
        environment = patch.dict(os.environ, {
            "LIVING_SPACES_DB": str(Path(temp.name) / "spaces.db"), "HERMES_HOME": temp.name,
        })
        environment.start()
        self.addCleanup(environment.stop)
        self.sid = projects.create_space("Limits Probe", owner="Demo", author="agent:demo",
                                         files={"index.html": "<h1>Last good project</h1>"})["id"]

    def snapshot(self):
        digest = hashlib.sha256()
        with db.read() as conn:
            for line in conn.iterdump():
                digest.update(line.encode("utf-8"))
        return digest.hexdigest()

    def rejected(self, maximum, actual, operation):
        before = self.snapshot()
        with self.assertRaises(SpacesError) as caught:
            operation()
        error = caught.exception.to_dict()
        self.assertEqual((error["code"], error["limit"], error["actual"]), ("limit", maximum, actual))
        self.assertTrue(error["message"])
        self.assertEqual(self.snapshot(), before)
        return error

    def write(self, files, **kwargs):
        return projects.write_files(self.sid, files=files, author="agent:demo", summary="Limit probe", **kwargs)

    def put(self, data, rid="probe", **kwargs):
        return records.put(self.sid, "probe", rid, data, actor="app", **kwargs)

    def source(self, source, meta=None):
        return records.upsert_source(self.sid, "probe", "source", source, meta or {}, actor="upkeep:manual")

    def refresh_setup(self):
        source = {"id": "public", "url": "https://example.org/feed", "collection": "papers"}
        grants.request(self.sid, "refresh", scope={"hosts": ["example.org"]}, purpose="Public feed", actor="agent:demo")
        grants.decide(self.sid, "refresh", "grant", actor="user")
        return source

    def refresh(self, source, payload):
        return feeds.refresh_source(self.sid, source, actor="upkeep:manual", before_write=lambda: None,
                                    fetcher=lambda sid, url: payload)


class ProjectLimitTests(LimitCase):
    def test_frozen_limit_values(self):
        self.assertEqual(limits.LIMITS, {
            "project_bytes": 25 * 1024 * 1024, "project_files": 600, "file_bytes": 8 * 1024 * 1024,
            "data_bytes": 256 * 1024, "source_bytes": 64 * 1024, "records": 50_000,
            "batch_ops": 500, "log_entries": 50, "log_message": 4000, "log_history": 2000,
            "bridge_bytes": 1024 * 1024, "feed_bytes": 3 * 1024 * 1024, "feed_entries": 200,
        })

    def test_file_limit_counts_utf8_bytes_and_retry_at_boundary(self):
        content = "é" * (limits.FILE_BYTES // 2)
        self.rejected(limits.FILE_BYTES, limits.FILE_BYTES + 1,
                      lambda: self.write({"earlier.txt": "first", "large.txt": content + "x"}))
        self.assertEqual(self.write({"large.txt": content})["rev"], 2)
        self.assertEqual(projects.read_file(self.sid, "large.txt")["size"], limits.FILE_BYTES)

    def test_file_count_is_resulting_project_and_retry_at_boundary(self):
        files = {f"part-{i}.txt": "public" for i in range(limits.PROJECT_FILES)}
        self.rejected(limits.PROJECT_FILES, limits.PROJECT_FILES + 1, lambda: self.write(files))
        files.pop("part-0.txt")
        self.assertEqual(len(self.write(files)["files"]), limits.PROJECT_FILES)

    def test_project_bytes_count_duplicate_blobs_per_file_and_retry_at_boundary(self):
        entry_size = projects.read_file(self.sid, "index.html")["size"]
        files = {f"part-{i}.bin": b"x" * limits.FILE_BYTES for i in range(3)}
        files["tail.bin"] = b"y" * (limits.PROJECT_BYTES - 3 * limits.FILE_BYTES - entry_size + 1)
        self.rejected(limits.PROJECT_BYTES, limits.PROJECT_BYTES + 1, lambda: self.write(files))
        files["tail.bin"] = files["tail.bin"][:-1]
        self.assertEqual(self.write(files)["rev"], 2)
        self.assertEqual(sum(f["size"] for f in projects.list_files(self.sid)), limits.PROJECT_BYTES)

    def test_failed_create_leaves_no_space_grants_revision_or_blobs(self):
        files = {f"part-{i}.txt": "public" for i in range(limits.PROJECT_FILES + 1)}
        self.rejected(limits.PROJECT_FILES, limits.PROJECT_FILES + 1,
                      lambda: projects.create_space("New Probe", owner="Demo", author="agent:demo", files=files))
        created = projects.create_space("New Probe", owner="Demo", author="agent:demo", files={"index.html": "Ready"})
        self.assertEqual((created["id"], created["head_rev"]), ("new-probe", 1))

    def test_normalized_manifest_cannot_exceed_file_limit(self):
        supplied = {"description": "x" * (limits.FILE_BYTES - json_bytes({"description": ""}))}
        normalized = {**projects.get_space(self.sid)["manifest"], **supplied}
        self.rejected(limits.FILE_BYTES, json_bytes(normalized), lambda: self.write({}, manifest=supplied))
        self.assertEqual(self.write({}, manifest={"description": "Public demo"})["rev"], 2)


class RecordLimitTests(LimitCase):
    def test_data_limit_rejects_whole_batch_and_retry_at_boundary(self):
        data = sized_object(limits.DATA_BYTES + 1)
        ops = [{"op": "put", "collection": "probe", "id": "first", "data": {}},
               {"op": "put", "collection": "probe", "id": "large", "data": data}]
        error = self.rejected(limits.DATA_BYTES, limits.DATA_BYTES + 1,
                              lambda: records.batch(self.sid, ops, actor="app"))
        self.assertEqual(error["op_index"], 1)
        ops[1]["data"] = sized_object(limits.DATA_BYTES)
        self.assertEqual(len(records.batch(self.sid, ops, actor="app")["results"]), 2)
        self.assertEqual(json_bytes(records.get(self.sid, "probe", "large")["data"]), limits.DATA_BYTES)

    def test_data_limit_checks_merged_record_and_utf8(self):
        data = {"text": "é" * ((limits.DATA_BYTES - json_bytes({"text": ""})) // 2)}
        first = self.put(data)
        change = {"extra": "x"}
        self.rejected(limits.DATA_BYTES, json_bytes({**data, **change}),
                      lambda: self.put(change, base_rev=first["rev"]))
        self.assertEqual(self.put({"text": "Public demo"}, base_rev=first["rev"])["rev"], first["rev"] + 1)

    def test_source_and_metadata_limits_leave_prior_record_and_retry_at_boundary(self):
        self.source({"title": "Original"})
        self.put({"note": "Keep this note"}, rid="source", base_rev=1)
        for field in ("source", "metadata"):
            with self.subTest(field=field):
                value = sized_object(limits.SOURCE_BYTES + 1)
                self.rejected(limits.SOURCE_BYTES, limits.SOURCE_BYTES + 1,
                              lambda: self.source(value) if field == "source" else self.source({}, value))
                accepted = sized_object(limits.SOURCE_BYTES)
                self.assertEqual(self.source(accepted) if field == "source" else self.source({}, accepted), "updated")
                record = records.get(self.sid, "probe", "source")
                self.assertEqual(record["data"], {"note": "Keep this note"})
                self.assertEqual(record["source" if field == "source" else "source_meta"], accepted)

    def test_source_batch_rolls_back_earlier_source_on_limit_and_recovers(self):
        entries = [("first", {"title": "Public"}, {}), ("large", sized_object(limits.SOURCE_BYTES + 1), {})]
        self.rejected(limits.SOURCE_BYTES, limits.SOURCE_BYTES + 1,
                      lambda: records.upsert_sources(self.sid, "papers", entries, actor="upkeep:manual"))
        entries[1] = ("large", sized_object(limits.SOURCE_BYTES), {})
        self.assertEqual(records.upsert_sources(self.sid, "papers", entries, actor="upkeep:manual")["added"], 2)

    def test_batch_limit_and_retry_at_boundary(self):
        ops = [{"op": "put", "collection": "probe", "id": f"record-{i}", "data": {}} for i in range(501)]
        self.rejected(500, 501, lambda: records.batch(self.sid, ops, actor="app"))
        result = records.batch(self.sid, ops[:500], actor="app")
        self.assertEqual(len(result["results"]), 500)
        self.assertEqual(records.query(self.sid, "probe")["total"], 500)

    def test_source_batch_limit_and_retry_at_boundary(self):
        entries = [(f"source-{i}", {"title": "Public"}, {}) for i in range(501)]
        self.rejected(500, 501, lambda: records.upsert_sources(self.sid, "papers", entries, actor="upkeep:manual"))
        self.assertEqual(records.upsert_sources(self.sid, "papers", entries[:500], actor="upkeep:manual")["added"], 500)

    def test_record_capacity_across_collections_is_atomic_and_recoverable(self):
        with db.write() as conn:
            conn.executemany("INSERT INTO records(space,collection,id,data,rev,created_at,updated_at,updated_by) VALUES(?,?,?,'{}',1,1,1,'app')",
                             ((self.sid, "seed", f"record-{i}") for i in range(limits.RECORDS - 1)))
        ops = [{"op": "put", "collection": "probe", "id": rid, "data": {}} for rid in ("last", "overflow")]
        self.rejected(50_000, 50_001, lambda: records.batch(self.sid, ops, actor="app"))
        self.assertEqual(records.batch(self.sid, ops[:1], actor="app")["results"][0]["id"], "last")
        self.rejected(50_000, 50_001, lambda: self.put({}, rid="overflow"))
        self.assertEqual(self.put({"note": "Still editable"}, rid="last", base_rev=1)["rev"], 2)
        self.rejected(50_000, 50_001, lambda: self.source({"title": "Overflow"}))
        records.delete(self.sid, "probe", "last", base_rev=2, actor="app")
        self.assertEqual(self.source({"title": "Room again"}), "added")


class LogAndBridgeLimitTests(LimitCase):
    def test_log_batch_and_message_limits_are_atomic_and_recoverable(self):
        entries = [{"level": "info", "msg": "Public diagnostic"}] * 51
        self.rejected(50, 51, lambda: logs.add_logs(self.sid, None, entries))
        self.assertEqual(logs.add_logs(self.sid, None, entries[:50]), 50)
        entries = [{"level": "info", "msg": "Earlier valid message"}, {"level": "info", "msg": "!" * 4001}]
        self.rejected(4000, 4001, lambda: logs.add_logs(self.sid, None, entries))
        entries[1]["msg"] = "!" * 4000
        self.assertEqual(logs.add_logs(self.sid, None, entries), 2)
        self.assertEqual(logs.read_logs(self.sid)[0]["msg"], "!" * 4000)

    def test_log_history_keeps_exactly_last_2000_per_space(self):
        other = projects.create_space("Other Probe", owner="Demo", author="agent:demo")["id"]
        logs.add_logs(other, None, [{"level": "info", "msg": "Other diagnostic"}])
        other_before = logs.read_logs(other)
        for start in range(0, limits.LOG_HISTORY, 50):
            logs.add_logs(self.sid, None, [{"level": "info", "msg": f"Diagnostic {i}"} for i in range(start, start + 50)])
        self.assertEqual(logs.add_logs(self.sid, None, [{"level": "info", "msg": "Newest diagnostic"}]), 1)
        kept = logs.read_logs(self.sid, limit=3000)
        self.assertEqual(len(kept), limits.LOG_HISTORY)
        self.assertEqual((kept[0]["msg"], kept[-1]["msg"]), ("Newest diagnostic", "Diagnostic 1"))
        self.assertEqual(logs.read_logs(other), other_before)
        self.assertEqual(logs.add_logs(self.sid, None, [{"level": "warn", "msg": "Next diagnostic"}]), 1)

    def test_bridge_limit_returns_numbers_stores_nothing_and_recovers(self):
        session = sessions.open_session(self.sid)["session"]
        args = {"ops": [{"op": "put", "collection": "probe", "id": f"r-{i}", "data": sized_object(210_000)} for i in range(5)]}
        actual = json_bytes({"v": 1, "id": 0, "op": "data.batch", "args": args})
        before = self.snapshot()
        result = bridge.dispatch(self.sid, session, "data.batch", args)
        self.assertFalse(result["ok"])
        self.assertEqual((result["error"]["code"], result["error"]["limit"], result["error"]["actual"]),
                         ("limit", limits.BRIDGE_BYTES, actual))
        self.assertEqual(self.snapshot(), before)
        result = bridge.dispatch(self.sid, session, "data.batch", {"ops": args["ops"][:1]})
        self.assertTrue(result["ok"], result)
        self.assertEqual(records.query(self.sid, "probe")["total"], 1)


class AgentLimitTests(LimitCase):
    def test_registered_handlers_keep_limit_numbers_atomicity_and_recovery(self):
        package = ROOT / "src/living-spaces"
        spec = importlib.util.spec_from_file_location("core_limit_plugin", package / "__init__.py",
                                                     submodule_search_locations=[str(package)])
        plugin = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {spec.name: plugin}):
            spec.loader.exec_module(plugin)
            tools = {}
            plugin.register(SimpleNamespace(register_tool=lambda **tool: tools.update({tool["name"]: tool}),
                                            register_skill=lambda *args, **kwargs: None))
            for kind in ("batch", "data", "file", "files"):
                with self.subTest(kind=kind):
                    if kind in ("batch", "data"):
                        name = "spaces_write_records"
                        ops = ([{"op": "put", "collection": "probe", "data": {}}] * 501 if kind == "batch" else
                               [{"op": "put", "collection": "probe", "data": sized_object(limits.DATA_BYTES + 1)}])
                        args = {"space": self.sid, "ops": ops}
                        maximum, actual = (500, 501) if kind == "batch" else (limits.DATA_BYTES, limits.DATA_BYTES + 1)
                        retry = {"space": self.sid, "ops": [{"op": "put", "collection": "probe", "data": {"note": "Recovered"}}]}
                    else:
                        name = "spaces_write_files"
                        files = ({"large.txt": "x" * (limits.FILE_BYTES + 1)} if kind == "file" else
                                 {f"extra-{i}.txt": "Public" for i in range(601 - len(projects.list_files(self.sid)))})
                        args = {"space": self.sid, "files": files, "summary": "Rejected probe"}
                        maximum, actual = (limits.FILE_BYTES, limits.FILE_BYTES + 1) if kind == "file" else (600, 601)
                        retry = {"space": self.sid, "files": {"retry.txt": "Recovered"}, "summary": "Recovered"}
                    before = self.snapshot()
                    reply = json.loads(tools[name]["handler"](args, profile_name="Demo"))
                    self.assertEqual((reply["ok"], reply["error"]["code"], reply["error"]["limit"], reply["error"]["actual"]),
                                     (False, "limit", maximum, actual))
                    self.assertEqual(self.snapshot(), before)
                    self.assertTrue(json.loads(tools[name]["handler"](retry, profile_name="Demo"))["ok"])


class FeedLimitTests(LimitCase):
    def test_feed_bytes_and_entries_reject_whole_source_and_recover(self):
        source = self.refresh_setup()
        self.refresh(source, feed_xml(title="Original"))
        for maximum, actual, payload in ((limits.FEED_BYTES, limits.FEED_BYTES + 1, b" " * (limits.FEED_BYTES + 1)),
                                         (limits.FEED_ENTRIES, limits.FEED_ENTRIES + 1, feed_xml(201))):
            with self.subTest(maximum=maximum):
                self.rejected(maximum, actual, lambda: self.refresh(source, payload))
                self.assertEqual(self.refresh(source, feed_xml(title=f"Recovered {maximum}"))[0]["updated"], 1)
        self.assertEqual(len(feeds.parse(feed_xml(200))), 200)
        payload = feed_xml()
        self.assertEqual(len(feeds.parse(payload + b" " * (limits.FEED_BYTES - len(payload)))), 1)

    def test_feed_text_byte_limit_uses_utf8_and_recovers(self):
        source = self.refresh_setup()
        payload = "<rss><channel>" + "é" * (limits.FEED_BYTES // 2) + "</channel></rss>"
        self.rejected(limits.FEED_BYTES, len(payload.encode("utf-8")), lambda: self.refresh(source, payload))
        self.assertEqual(self.refresh(source, feed_xml())[0]["added"], 1)

    def test_feed_source_limit_uses_canonical_record_encoding_and_recovers(self):
        source = self.refresh_setup()
        fields = feeds.parse(feed_xml(title=""))[0][1]
        title = "x" * (limits.SOURCE_BYTES - json_bytes(fields) + 1)
        self.rejected(limits.SOURCE_BYTES, limits.SOURCE_BYTES + 1, lambda: self.refresh(source, feed_xml(2, title)))
        title = "é" * ((limits.SOURCE_BYTES - json_bytes(fields)) // 2)
        accepted = feed_xml(2, title)
        self.assertEqual(self.refresh(source, accepted)[0]["added"], 2)
        self.assertEqual(records.query(self.sid, "papers")["records"][0]["source"]["title"], title)

    def test_feed_stream_byte_limit_stops_without_writes_and_recovers(self):
        self.refresh_setup()
        response = Mock(is_redirect=False)
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.iter_bytes.return_value = iter([b"x" * limits.FEED_BYTES, b"x"])
        client = Mock()
        client.__enter__ = Mock(return_value=client)
        client.__exit__ = Mock(return_value=False)
        client.stream.return_value = response
        with patch.object(feeds.httpx, "Client", return_value=client):
            self.rejected(limits.FEED_BYTES, limits.FEED_BYTES + 1,
                          lambda: feeds.fetch(self.sid, "https://example.org/feed"))
            response.iter_bytes.return_value = iter([feed_xml()])
            self.assertEqual(feeds.fetch(self.sid, "https://example.org/feed"), feed_xml())


if __name__ == "__main__":
    unittest.main()
