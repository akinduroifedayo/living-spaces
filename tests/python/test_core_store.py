import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "living-spaces"))
import living_spaces_core
from living_spaces_core import bridge, db, grants, limits, logs, projects, records, sessions, SpacesError


class CoreCase(unittest.TestCase):
    def setUp(self):
        (ROOT / ".run").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / ".run")
        self.addCleanup(self.temp.cleanup)
        self.environment = patch.dict(os.environ, {
            "LIVING_SPACES_DB": str(Path(self.temp.name) / "spaces.db"),
            "HERMES_HOME": self.temp.name,
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)
        for name in ("runs", "feeds", "schedules"):
            previous = living_spaces_core.__dict__.pop(name, None)
            def restore_attribute(name=name, previous=previous):
                living_spaces_core.__dict__.pop(name, None)
                if previous is not None:
                    setattr(living_spaces_core, name, previous)
            self.addCleanup(restore_attribute)
        unavailable = {f"living_spaces_core.{name}": None for name in ("runs", "feeds", "schedules")}
        modules = patch.dict(sys.modules, unavailable)
        modules.start()
        self.addCleanup(modules.stop)
        self.sid = self.create()["id"]

    def create(self, name="Research Desk", **kwargs):
        return projects.create_space(name, owner="Demo Hermes", author="agent:demo", files={"index.html": "<h1>Public demo</h1>"}, **kwargs)

    def error(self, code, function, *args, **kwargs):
        with self.assertRaises(SpacesError) as caught:
            function(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)
        return caught.exception.to_dict()

    def put(self, rid="paper", data=None, **kwargs):
        return records.put(self.sid, "papers", rid, data if data is not None else {"note": "Demo note"}, actor="user", **kwargs)

    def write(self, files, **kwargs):
        return projects.write_files(self.sid, files=files, author="agent:demo", summary="Demo edit", **kwargs)

    def manifest_v2(self, ops):
        manifest = projects.get_space(self.sid)["manifest"]
        manifest["data"] = {"version": 2, "migrations": [{"to": 2, "ops": ops}]}
        return manifest

    def counts(self):
        with db.read() as conn:
            return {table: conn.execute(f"SELECT count(*) FROM {table} WHERE space=?", (self.sid,)).fetchone()[0]
                    for table in ("records", "changes", "revisions", "recovery_points")}


class ProjectTests(CoreCase):
    def test_create_edit_restore_preserves_history_and_records(self):
        self.put()
        before = records.get(self.sid, "papers", "paper")
        self.assertEqual(projects.get_space(self.sid)["status"], "active")
        edit = projects.edit_file(self.sid, "index.html", old="Public demo", new="New view", author="agent:demo", summary="New view", base_rev=1)
        restored = projects.restore_revision(self.sid, 1, author="user")
        self.assertEqual((edit["rev"], restored["rev"], restored["kind"], restored["restored_from"]), (2, 3, "restore", 1))
        self.assertEqual([item["rev"] for item in projects.list_revisions(self.sid)], [3, 2, 1])
        self.assertIn("Public demo", projects.read_file(self.sid, "index.html")["text"])
        self.assertIn("New view", projects.read_file(self.sid, "index.html", rev=2)["text"])
        self.assertEqual(records.get(self.sid, "papers", "paper"), before)

    def test_blobs_are_content_addressed_and_deduplicated(self):
        result = self.write({"a.txt": "same", "b.txt": "same"})
        self.assertEqual(result["files"]["a.txt"], hashlib.sha256(b"same").hexdigest())
        with db.read() as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM blobs WHERE sha=?", (result["files"]["a.txt"],)).fetchone()[0], 1)
        self.write({"a.txt": None})
        self.assertNotIn("a.txt", [item["path"] for item in projects.list_files(self.sid)])
        self.assertEqual(projects.read_file(self.sid, "a.txt", rev=2)["text"], "same")

    def test_binary_files_and_bundle(self):
        self.write({"image.png": b"\x89PNG\xff"})
        file = projects.read_file(self.sid, "image.png")
        self.assertEqual(base64.b64decode(file["b64"]), b"\x89PNG\xff")
        bundle = projects.bundle(self.sid)
        self.assertEqual(bundle["rev"], 2)
        image = next(file for file in bundle["files"] if file["path"] == "image.png")
        self.assertEqual(image["mime"], "image/png")

    def test_building_becomes_active_only_with_entry(self):
        space = projects.create_space("Building", owner="Demo Hermes", author="user")
        self.assertEqual((space["status"], space["head_rev"]), ("building", 0))
        sid = space["id"]
        projects.write_files(sid, files={"other.txt": "draft"}, author="user", summary="Draft")
        self.assertEqual(projects.get_space(sid)["status"], "building")
        projects.write_files(sid, files={"index.html": "Ready"}, author="user", summary="Ready")
        self.assertEqual(projects.get_space(sid)["status"], "active")

    def test_space_json_is_manifest_not_project_file(self):
        manifest = {"name": "Renamed", "entry": "main.html", "accent": "bad", "icon": "bad icon", "data": {"version": 1}}
        self.write({"space.json": json.dumps(manifest), "main.html": "Ready"})
        space = projects.get_space(self.sid)
        self.assertEqual((space["id"], space["name"], space["accent"], space["icon"]), (self.sid, "Renamed", "blue", "layers"))
        self.assertNotIn("space.json", [item["path"] for item in projects.list_files(self.sid)])
        self.assertEqual(json.loads(projects.read_file(self.sid, "space.json")["text"]), space["manifest"])
        self.assertEqual(projects.resolve_space("RENAMED"), self.sid)

    def test_ambiguous_name_and_exact_id_precedence(self):
        second = self.create("Research Desk")
        error = self.error("ambiguous", projects.resolve_space, "RESEARCH DESK")
        self.assertEqual({item["id"] for item in error["candidates"]}, {self.sid, second["id"]})
        self.assertEqual(projects.resolve_space(self.sid), self.sid)
        self.error("not_found", projects.resolve_space, "Research")

    def test_slug_is_bounded_and_collisions_are_unique(self):
        one = self.create("A" * 90)["id"]
        two = self.create("A" * 90)["id"]
        self.assertEqual(len(one), 48)
        self.assertLessEqual(len(two), 48)
        self.assertTrue(two.endswith("-2"))
        self.assertEqual(self.create("?")["id"], "space")

    def test_stale_revision_and_non_single_edit_are_rejected(self):
        self.write({"index.html": "repeat repeat"}, base_rev=1)
        self.error("conflict", self.write, {"index.html": "lost"}, base_rev=1)
        for old in ("repeat", "missing"):
            self.error("invalid", projects.edit_file, self.sid, "index.html", old=old, new="x", author="user", summary="x")
        self.assertEqual(projects.get_space(self.sid)["head_rev"], 2)

    def test_invalid_paths_and_manifest_are_rejected_atomically(self):
        for path in ("../escape", "/absolute", "a//b", "a/./b", "bad name", "x/.."):
            self.error("invalid", self.write, {path: "bad"})
        self.error("invalid", self.write, {"space.json": "[]"})
        self.error("invalid", self.write, {"space.json": "{"})
        self.assertEqual(projects.get_space(self.sid)["head_rev"], 1)

    def test_bundled_libraries_and_missing_kit_warning_preserve_explicit_imports(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".run") as directory:
            runtime = Path(directory)
            (runtime / "vendor").mkdir()
            for name in ("preact.mjs", "hooks.mjs", "lightweight-charts.mjs"):
                (runtime / "vendor" / name).write_text("export const demo = true")
            with patch.object(projects, "RUNTIME", runtime):
                space = projects.create_space("Libraries", owner="Demo Hermes", author="user",
                    files={"index.html": "Ready", "custom.mjs": "demo"},
                    manifest={"imports": {"preact": "custom.mjs"}},
                    libraries=["preact", "preact/hooks", "lightweight-charts", "spaces-kit"])
        self.assertEqual(space["manifest"]["imports"]["preact"], "custom.mjs")
        self.assertEqual(space["manifest"]["imports"]["preact/hooks"], "vendor/hooks.mjs")
        self.assertNotIn("spaces-kit", space["manifest"]["imports"])
        self.assertTrue(any("kit/spaces-kit.mjs" in message for message in space["warnings"]))
        self.assertIn("vendor/lightweight-charts.mjs", [item["path"] for item in projects.list_files(space["id"])])

    def test_project_limits_keep_prior_revision(self):
        for attribute, value, changed in (("FILE_BYTES", 8, {"large.txt": "x" * 9}),
                                           ("PROJECT_FILES", 1, {"extra.txt": "x"}),
                                           ("PROJECT_BYTES", 25, {"extra.txt": "x" * 30})):
            with self.subTest(attribute=attribute), patch.object(limits, attribute, value):
                error = self.error("limit", self.write, changed)
                self.assertGreater(error["actual"], error["limit"])
                self.assertEqual(projects.get_space(self.sid)["head_rev"], 1)

    def test_real_bundled_vendor_files_are_copied_exactly(self):
        space = projects.create_space("Vendor demo", owner="Demo Hermes", author="user",
            files={"index.html": "Ready"}, libraries=["preact", "preact/hooks", "lightweight-charts"])
        files = {item["path"]: item for item in projects.list_files(space["id"])}
        for name, path in (("preact", "vendor/preact.mjs"), ("preact/hooks", "vendor/hooks.mjs"), ("lightweight-charts", "vendor/lightweight-charts.mjs")):
            self.assertEqual(files[path]["sha"], hashlib.sha256((projects.RUNTIME / path).read_bytes()).hexdigest())
            self.assertEqual(space["manifest"]["imports"][name], path)

    def test_warnings_for_unresolved_imports_and_network(self):
        result = self.write({"app.mjs": "import x from './missing.mjs'; const url='https://example.org'"})
        self.assertTrue(any("Unresolved relative import" in item for item in result["warnings"]))
        self.assertTrue(any("Network URLs" in item for item in result["warnings"]))

    def test_invalid_accent_values_fall_back(self):
        for value in (["bad"], {"bad": True}, None, 1):
            result = self.write({}, manifest={"accent": value})
            self.assertEqual(result["manifest"]["accent"], "blue")

    def test_pin_open_and_summary_shapes(self):
        projects.touch_opened(self.sid)
        projects.set_pinned(self.sid, True)
        space = projects.get_space(self.sid)
        self.assertTrue(space["pinned"])
        self.assertIsInstance(space["last_opened_at"], float)
        self.assertEqual(set(space["freshness"]), {"last_success_at", "last_attempt_at", "last_attempt_status", "source_as_of", "next_run_at"})
        self.assertIsNone(space["schedule"])


class RecordTests(CoreCase):
    def test_create_only_and_stale_put_return_current(self):
        first = self.put()
        for base in (None, 0, 99):
            error = self.error("conflict", self.put, data={"note": "lost"}, base_rev=base)
            self.assertEqual(error["current"], first)
        updated = self.put(data={"status": "reading"}, base_rev=first["rev"])
        self.assertEqual(updated["data"], {"note": "Demo note", "status": "reading"})
        self.assertEqual(updated["rev"], 2)
        self.error("conflict", self.put, "missing", base_rev=1)

    def test_replace_and_generated_id(self):
        first = self.put()
        replaced = self.put(data={"status": "done"}, base_rev=first["rev"], merge=False)
        self.assertEqual(replaced["data"], {"status": "done"})
        generated = self.put(None)
        self.assertRegex(generated["id"], r"^r_[0-9a-f]{12}$")

    def test_batch_bad_op_rolls_back_records_and_changes(self):
        error = self.error("conflict", records.batch, self.sid, [
            {"op": "put", "collection": "papers", "id": "one", "data": {}, "base_rev": 0},
            {"op": "put", "collection": "papers", "id": "two", "data": {}, "base_rev": 9},
        ], actor="user")
        self.assertEqual(error["op_index"], 1)
        self.assertEqual((self.counts()["records"], self.counts()["changes"]), (0, 0))
        self.error("invalid", records.batch, self.sid, [{"op": "put", "collection": "papers"}], actor="user")

    def test_successful_batch_sees_earlier_ops(self):
        result = records.batch(self.sid, [
            {"op": "put", "collection": "papers", "id": "one", "data": {"note": "Demo"}},
            {"op": "put", "collection": "papers", "id": "one", "data": {"status": "done"}, "base_rev": 1},
            {"op": "delete", "collection": "papers", "id": "one", "base_rev": 2},
        ], actor="user")
        self.assertEqual(len(result["results"]), 3)
        self.assertEqual(records.query(self.sid, "papers")["total"], 0)
        self.assertEqual(len(records.changes_since(self.sid, 0)["changes"]), 3)

    def test_upsert_source_preserves_user_data_and_unchanged_cursor(self):
        self.assertEqual(records.upsert_source(self.sid, "papers", "paper", {"title": "Public title"}, {"fetched_at": 1}, actor="upkeep:manual"), "added")
        self.put(data={"note": "Demo note", "status": "reading"}, base_rev=1)
        self.assertEqual(records.upsert_source(self.sid, "papers", "paper", {"title": "Updated title"}, {"fetched_at": 2}, actor="upkeep:manual"), "updated")
        before = records.get(self.sid, "papers", "paper")
        self.assertEqual(before["data"], {"note": "Demo note", "status": "reading"})
        self.assertEqual(before["source"]["title"], "Updated title")
        seq = records.changes_since(self.sid, 0)["seq"]
        self.assertEqual(records.upsert_source(self.sid, "papers", "paper", {"title": "Updated title"}, {"fetched_at": 3}, actor="upkeep:manual"), "unchanged")
        self.assertEqual(records.changes_since(self.sid, seq)["changes"], [])
        self.assertEqual(records.get(self.sid, "papers", "paper")["rev"], before["rev"])

    def test_query_filter_order_pagination_and_data_precedence(self):
        records.upsert_source(self.sid, "papers", "a", {"status": "reading", "title": "A"}, {}, actor="upkeep:manual")
        records.upsert_source(self.sid, "papers", "b", {"status": "reading", "title": "B"}, {}, actor="upkeep:manual")
        self.put("a", {"status": "done"}, base_rev=1)
        reading = records.query(self.sid, "papers", where={"status": "reading"})
        self.assertEqual([item["id"] for item in reading["records"]], ["b"])
        ordered = records.query(self.sid, "papers", order="-title", limit=1)
        self.assertEqual((ordered["total"], ordered["records"][0]["id"]), (2, "b"))
        self.assertEqual(records.query(self.sid, "papers", order="title", offset=1)["records"][0]["id"], "b")

    def test_changes_monotonic_paginated_and_recreate_does_not_reuse_rev(self):
        a = self.put()
        records.delete(self.sid, "papers", "paper", actor="user", base_rev=a["rev"])
        recreated = self.put()
        self.assertGreater(recreated["rev"], a["rev"])
        cursor, seqs = 0, []
        while True:
            page = records.changes_since(self.sid, cursor, limit=1)
            if not page["changes"]:
                break
            seqs += [change["seq"] for change in page["changes"]]
            cursor = page["seq"]
        self.assertEqual(len(seqs), 3)
        self.assertEqual(seqs, sorted(set(seqs)))
        self.error("conflict", self.put, base_rev=a["rev"])

    def test_concurrent_put_allows_one_winner(self):
        first = self.put()
        barrier = threading.Barrier(2)
        outcomes = []
        def writer(value):
            barrier.wait()
            try:
                self.put(data={"note": value}, base_rev=first["rev"])
                outcomes.append("saved")
            except SpacesError as exc:
                outcomes.append(exc.code)
        threads = [threading.Thread(target=writer, args=(value,)) for value in ("Demo A", "Demo B")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        self.assertEqual(sorted(outcomes), ["conflict", "saved"])
        self.assertEqual(len(records.changes_since(self.sid, 0)["changes"]), 2)

    def test_record_limits_are_visible_and_preserve_state(self):
        error = self.error("limit", self.put, data={"note": "x" * limits.DATA_BYTES})
        self.assertEqual(error["limit"], limits.DATA_BYTES)
        self.assertGreater(error["actual"], limits.DATA_BYTES)
        self.assertEqual(self.counts()["records"], 0)
        with patch.object(limits, "RECORDS", 1):
            self.put()
            self.error("limit", self.put, "other")
        self.error("limit", records.upsert_source, self.sid, "papers", "large", {"text": "x" * limits.SOURCE_BYTES}, {}, actor="upkeep:manual")
        self.error("limit", records.batch, self.sid, [{}] * 501, actor="user")

    def test_provenance_change_updates_source_even_with_same_content(self):
        source = {"title": "Public title"}
        records.upsert_source(self.sid, "papers", "paper", source, {"url": "https://example.org/one"}, actor="upkeep:manual")
        result = records.upsert_source(self.sid, "papers", "paper", source, {"url": "https://example.org/two"}, actor="upkeep:manual")
        self.assertEqual(result, "updated")
        self.assertEqual(records.get(self.sid, "papers", "paper")["source_meta"]["url"], "https://example.org/two")

    def test_invalid_identifiers_and_json(self):
        for collection in ("_host", "Bad", "../papers"):
            self.error("invalid", records.query, self.sid, collection)
        self.error("invalid", self.put, "bad/id")
        self.error("invalid", self.put, data=[])
        self.error("invalid", self.put, data={"value": float("nan")})
        self.assertEqual(records.put(self.sid, "_prefs", "ui", {}, actor="app")["collection"], "_prefs")

    def test_persistence_after_fresh_python_process(self):
        self.put()
        code = "import sys; sys.path.insert(0, sys.argv[1]); from living_spaces_core import records; print(records.get(sys.argv[2], 'papers', 'paper')['data']['note'])"
        result = subprocess.run([sys.executable, "-c", code, str(ROOT / "src" / "living-spaces"), self.sid], capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.strip(), "Demo note")


class MigrationTests(CoreCase):
    def test_version_raise_migrates_and_snapshot_is_full(self):
        self.put(data={"stat": "reading", "note": "Demo"})
        records.upsert_source(self.sid, "papers", "paper", {"title": "Public title"}, {"source_id": "demo"}, actor="upkeep:manual")
        manifest = self.manifest_v2([
            {"op": "rename_field", "collection": "papers", "from": "stat", "to": "status"},
            {"op": "set_default", "collection": "papers", "field": "priority", "value": "normal"},
        ])
        result = self.write({"index.html": "Version 2"}, manifest=manifest)
        self.assertEqual(result["rev"], 2)
        self.assertEqual(projects.get_space(self.sid)["data_version"], 2)
        current = records.get(self.sid, "papers", "paper")
        self.assertEqual(current["data"], {"status": "reading", "note": "Demo", "priority": "normal"})
        self.assertEqual(current["source"], {"title": "Public title"})
        point = records.list_recovery_points(self.sid)[0]
        self.assertEqual((point["data_version"], point["head_rev"]), (1, 1))
        with db.read() as conn:
            snapshot = json.loads(conn.execute("SELECT snapshot FROM recovery_points WHERE id=?", (point["id"],)).fetchone()[0])
        self.assertEqual(snapshot[0]["data"], {"stat": "reading", "note": "Demo"})
        self.assertEqual(snapshot[0]["source_meta"], {"source_id": "demo"})

    def test_failing_migration_rolls_back_revision_records_changes_and_keeps_recovery(self):
        before = self.put(data={"stat": "reading", "status": "done"})
        manifest = self.manifest_v2([
            {"op": "set_default", "collection": "papers", "field": "priority", "value": "normal"},
            {"op": "rename_field", "collection": "papers", "from": "stat", "to": "status"},
        ])
        original_counts = self.counts()
        error = self.error("invalid", self.write, {"index.html": "Broken version"}, manifest=manifest)
        self.assertIsInstance(error["recovery_point"], int)
        self.assertEqual(records.get(self.sid, "papers", "paper"), before)
        self.assertEqual(projects.get_space(self.sid)["data_version"], 1)
        self.assertEqual(projects.get_space(self.sid)["head_rev"], 1)
        self.assertIn("Public demo", projects.read_file(self.sid, "index.html")["text"])
        self.assertEqual(self.counts(), {**original_counts, "recovery_points": 1})

    def test_unexpected_migration_failure_also_retains_recovery_point(self):
        original = self.put()
        manifest = self.manifest_v2([])
        def fail(conn, sid, *args, **kwargs):
            records._put(conn, sid, "papers", "paper", {"note": "Transient demo"}, actor="user", base_rev=original["rev"])
            raise RuntimeError("Injected migration failure")
        with patch.object(living_spaces_core.migrations, "apply", fail):
            error = self.error("invalid", self.write, {"index.html": "Transient code"}, manifest=manifest)
        self.assertIsInstance(error["recovery_point"], int)
        self.assertEqual(records.get(self.sid, "papers", "paper"), original)
        self.assertEqual(projects.get_space(self.sid)["head_rev"], 1)
        self.assertEqual(len(records.list_recovery_points(self.sid)), 1)

    def test_restore_incompatible_version_and_version_downgrade_blocked(self):
        self.write({}, manifest=self.manifest_v2([]))
        error = self.error("incompatible", projects.restore_revision, self.sid, 1, author="user")
        self.assertEqual((error["from_version"], error["to_version"]), (2, 1))
        self.error("incompatible", self.write, {}, manifest={"data": {"version": 1}})
        self.assertEqual(projects.get_space(self.sid)["head_rev"], 2)

    def test_unknown_and_missing_migrations_rejected(self):
        self.error("invalid", self.write, {}, manifest=self.manifest_v2([{"op": "execute", "command": "demo"}]))
        self.assertEqual(projects.get_space(self.sid)["head_rev"], 1)
        self.error("invalid", self.write, {}, manifest={"data": {"version": 3, "migrations": []}})
        self.assertEqual(projects.get_space(self.sid)["data_version"], 1)
        self.assertEqual(len(records.list_recovery_points(self.sid)), 1)

    def test_collection_copy_rename_delete_and_default_preserve_sources(self):
        self.put(data={"obsolete": True, "priority": "high"})
        records.upsert_source(self.sid, "papers", "paper", {"title": "Public"}, {}, actor="upkeep:manual")
        self.write({}, manifest=self.manifest_v2([
            {"op": "delete_field", "collection": "papers", "field": "obsolete"},
            {"op": "set_default", "collection": "papers", "field": "priority", "value": "normal"},
            {"op": "copy_collection", "from": "papers", "to": "library"},
            {"op": "rename_collection", "from": "library", "to": "queue"},
        ]))
        self.assertEqual(records.get(self.sid, "queue", "paper")["data"], {"priority": "high"})
        self.assertEqual(records.get(self.sid, "queue", "paper")["source"], {"title": "Public"})
        self.assertEqual(records.query(self.sid, "library")["total"], 0)
        self.assertEqual(records.query(self.sid, "papers")["total"], 1)

    def test_recovery_restore_replaces_records_takes_fresh_point_and_preserves_code(self):
        self.put()
        point = records.create_recovery_point(self.sid, "Demo checkpoint")
        self.put(data={"note": "Later demo"}, base_rev=1)
        self.put("later")
        self.write({"index.html": "New code"})
        result = records.restore_recovery_point(self.sid, point, actor="user")
        self.assertEqual(result["records"], 1)
        self.assertNotEqual(result["recovery_point"], point)
        self.assertEqual(records.get(self.sid, "papers", "paper")["data"]["note"], "Demo note")
        self.assertGreater(records.get(self.sid, "papers", "paper")["rev"], 2)
        self.error("not_found", records.get, self.sid, "papers", "later")
        self.assertEqual(projects.read_file(self.sid, "index.html")["text"], "New code")
        self.assertEqual(len(records.list_recovery_points(self.sid)), 2)
        other = self.create("Other")["id"]
        self.error("not_found", records.restore_recovery_point, other, point, actor="user")

    def test_cross_version_recovery_is_blocked(self):
        point = records.create_recovery_point(self.sid, "Version one")
        self.write({}, manifest=self.manifest_v2([]))
        self.error("incompatible", records.restore_recovery_point, self.sid, point, actor="user")


class AuthorityTests(CoreCase):
    def upkeep(self, hosts):
        return {"upkeep": {"handler": "feed", "sources": [{"id": str(i), "url": f"https://{host}/public.xml", "collection": "papers"} for i, host in enumerate(hosts)]}}

    def test_default_grants_and_refresh_scope_widening(self):
        self.assertEqual({row["capability"]: row["status"] for row in grants.list_grants(self.sid)}, {"data": "granted", "logs": "granted", "net": "granted"})
        self.write({}, manifest=self.upkeep(["example.org"]))
        refresh = next(row for row in grants.list_grants(self.sid) if row["capability"] == "refresh")
        self.assertEqual((refresh["status"], refresh["requested_scope"]), ("requested", {"hosts": ["example.org"]}))
        grants.decide(self.sid, "refresh", "grant")
        grants.check(self.sid, "refresh", {"hosts": ["example.org"]})
        self.write({}, manifest=self.upkeep(["example.org", "example.com"]))
        self.error("not_granted", grants.check, self.sid, "refresh", {"hosts": ["example.org"]})
        refresh = next(row for row in grants.list_grants(self.sid) if row["capability"] == "refresh")
        self.assertEqual(refresh["status"], "requested")
        self.assertEqual(refresh["requested_scope"], {"hosts": ["example.com", "example.org"]})
        self.assertIn("denied", [entry["outcome"] for entry in grants.audit_log(self.sid)])

    def test_narrow_grant_scope_and_denied_request_does_not_reprompt(self):
        self.write({}, manifest=self.upkeep(["example.org", "example.com"]))
        grants.decide(self.sid, "refresh", "grant", scope={"hosts": ["example.org"]})
        self.error("not_granted", grants.check, self.sid, "refresh", {"hosts": ["example.com"]})
        self.write({}, manifest=self.upkeep(["example.org"]))
        grants.check(self.sid, "refresh", {"hosts": ["example.org"]})
        grants.decide(self.sid, "refresh", "deny")
        self.write({}, manifest=self.upkeep(["example.org", "example.com"]))
        self.assertEqual(next(row for row in grants.list_grants(self.sid) if row["capability"] == "refresh")["status"], "denied")

    def test_revocation_cancels_pending_via_lazy_seam(self):
        self.write({}, manifest=self.upkeep(["example.org"]))
        calls = []
        fake = types.SimpleNamespace(cancel_pending=lambda *args: calls.append(args))
        with patch.dict(sys.modules, {"living_spaces_core.runs": fake}):
            grants.decide(self.sid, "refresh", "revoke")
        self.assertEqual(calls, [(self.sid, "refresh revoked")])
        self.error("not_granted", grants.check, self.sid, "refresh")

    def test_sessions_are_space_bound_and_closed_dispatch_fails_first(self):
        session = sessions.open_session(self.sid)["session"]
        other = self.create("Other")["id"]
        self.error("session_invalid", sessions.require, other, session)
        sessions.close_session(session)
        reply = bridge.dispatch(self.sid, session, "data.put", [])
        self.assertEqual(reply["error"]["code"], "session_invalid")
        self.assertEqual(self.counts()["records"], 0)

    def test_cross_space_args_and_batch_ops_only_mutate_bound_space(self):
        other = self.create("Other")["id"]
        session = sessions.open_session(self.sid)["session"]
        put = bridge.dispatch(self.sid, session, "data.put", {"space": other, "collection": "papers", "id": "one", "data": {"note": "Demo"}})
        self.assertTrue(put["ok"], put)
        batch = bridge.dispatch(self.sid, session, "data.batch", {"space": other, "ops": [{"op": "put", "space": other, "collection": "papers", "id": "two", "data": {}}]})
        self.assertTrue(batch["ok"], batch)
        self.assertEqual(records.query(self.sid, "papers")["total"], 2)
        self.assertEqual(records.query(other, "papers")["total"], 0)

    def test_bridge_validates_shapes_grants_and_oversized_payload(self):
        session = sessions.open_session(self.sid)["session"]
        for args in (None, [], "text", {"unexpected": True}, {"collection": "papers", "limit": -1}):
            reply = bridge.dispatch(self.sid, session, "data.query", args)
            self.assertEqual(reply["error"]["code"], "invalid", reply)
        oversized = bridge.dispatch(self.sid, session, "data.put", {"collection": "papers", "data": {"note": "x" * limits.BRIDGE_BYTES}})
        self.assertEqual(oversized["error"]["code"], "limit")
        grants.decide(self.sid, "data", "revoke")
        reply = bridge.dispatch(self.sid, session, "data.put", [])
        self.assertEqual(reply["error"]["code"], "not_granted")
        self.assertEqual(bridge.dispatch(self.sid, session, "agent.ask", {})["error"]["code"], "not_granted")

    def test_bridge_meta_log_read_write_delete(self):
        session = sessions.open_session(self.sid)["session"]
        def call(op, args):
            reply = bridge.dispatch(self.sid, session, op, args)
            self.assertTrue(reply["ok"], reply)
            return reply["result"]
        self.assertEqual(call("meta", {})["space"]["id"], self.sid)
        item = call("data.put", {"collection": "papers", "data": {"note": "Demo"}})
        self.assertEqual(call("data.get", {"collection": "papers", "id": item["id"]}), item)
        self.assertEqual(call("data.query", {"collection": "papers"})["total"], 1)
        self.assertEqual(call("log", {"entries": [{"level": "error", "msg": "Demo failure"}]}), {"stored": 1})
        self.assertEqual(call("data.delete", {"collection": "papers", "id": item["id"], "base_rev": item["rev"]}), {"deleted": True})
        self.assertEqual(projects.get_space(self.sid)["error_count_24h"], 1)

    def test_missing_upkeep_returns_blocked_and_denied_refresh_does_not_call(self):
        session = sessions.open_session(self.sid)["session"]
        self.assertEqual(bridge.dispatch(self.sid, session, "refresh", {})["error"]["code"], "not_granted")
        self.write({}, manifest=self.upkeep(["example.org"]))
        grants.decide(self.sid, "refresh", "grant")
        with patch.dict(sys.modules, {"living_spaces_core.runs": None}):
            for op in ("refresh", "runs.list"):
                reply = bridge.dispatch(self.sid, session, op, {})
                self.assertEqual((reply["error"]["code"], reply["error"]["reason"]), ("blocked", "no_handler"))

    def test_inflight_result_not_delivered_after_revocation_or_session_close(self):
        self.write({}, manifest=self.upkeep(["example.org"]))
        grants.decide(self.sid, "refresh", "grant")
        session = sessions.open_session(self.sid)["session"]
        def refresh(*args, **kwargs):
            grants.decide(self.sid, "refresh", "revoke")
            return {"id": "demo-run"}
        with patch.dict(sys.modules, {"living_spaces_core.runs": types.SimpleNamespace(start_refresh=refresh)}):
            self.assertEqual(bridge.dispatch(self.sid, session, "refresh", {})["error"]["code"], "not_granted")

    def test_future_and_capability_disclosures(self):
        self.assertEqual(set(grants.FUTURE), {"sites", "camera", "microphone", "location", "tool:*", "files", "cross_space", "agent.ask"})
        for capability in grants.CAPABILITIES.values():
            self.assertTrue({"label", "description", "default_purpose", "data_leaves_device", "continuing_access"} <= capability.keys())

    def test_archive_delete_hooks_and_namespace_cleanup(self):
        self.put()
        records.create_recovery_point(self.sid, "Demo point")
        session = sessions.open_session(self.sid)["session"]
        logs.add_logs(self.sid, session, [{"level": "info", "msg": "Demo"}])
        calls = []
        schedule = types.SimpleNamespace(on_archive=lambda sid: calls.append(("archive", sid)),
            on_unarchive=lambda sid: calls.append(("unarchive", sid)),
            on_delete=lambda sid: calls.append(("delete", sid)), get_schedule=lambda sid: None)
        runs = types.SimpleNamespace(cancel_pending=lambda sid, reason: calls.append(("cancel", reason)))
        with patch.dict(sys.modules, {"living_spaces_core.runs": runs, "living_spaces_core.schedules": schedule}):
            projects.set_status(self.sid, "archived", actor="user")
            self.error("archived", self.put, "new")
            self.error("session_invalid", sessions.require, self.sid, session)
            self.assertEqual(projects.list_spaces(False), [])
            projects.set_status(self.sid, "active", actor="user")
            self.error("invalid", projects.delete_space, self.sid, actor="user", confirm="no")
            result = projects.delete_space(self.sid, actor="user", confirm=self.sid)
        self.assertEqual(result["removed"]["records"], 1)
        self.assertLess(calls.index(("delete", self.sid)), calls.index(("cancel", "deleted")))
        self.assertIn(("archive", self.sid), calls)
        self.assertIn(("unarchive", self.sid), calls)
        self.error("not_found", projects.get_space, self.sid)
        with db.read() as conn:
            for table in ("records", "changes", "revisions", "sessions", "logs", "grants", "audit", "runs", "recovery_points"):
                self.assertEqual(conn.execute(f"SELECT count(*) FROM {table} WHERE space=?", (self.sid,)).fetchone()[0], 0, table)

    def test_session_closed_between_preflight_and_mutation_does_not_write(self):
        session = sessions.open_session(self.sid)["session"]
        original = bridge._call
        def close_before_call(*args):
            sessions.close_session(session)
            return original(*args)
        with patch.object(bridge, "_call", close_before_call):
            reply = bridge.dispatch(self.sid, session, "data.put", {"collection": "papers", "data": {"note": "Demo"}})
        self.assertEqual(reply["error"]["code"], "session_invalid")
        self.assertEqual(self.counts()["records"], 0)

    def test_grant_revoked_between_preflight_and_mutation_does_not_write(self):
        session = sessions.open_session(self.sid)["session"]
        original = bridge._call
        def revoke_before_call(*args):
            grants.decide(self.sid, "data", "revoke")
            return original(*args)
        with patch.object(bridge, "_call", revoke_before_call):
            reply = bridge.dispatch(self.sid, session, "data.put", {"collection": "papers", "data": {"note": "Demo"}})
        self.assertEqual(reply["error"]["code"], "not_granted")
        self.assertEqual(self.counts()["records"], 0)

    def test_unknown_op_matching_capability_is_denied_and_audited(self):
        session = sessions.open_session(self.sid)["session"]
        reply = bridge.dispatch(self.sid, session, "data", {})
        self.assertEqual(reply["error"]["code"], "not_granted")
        self.assertEqual(grants.audit_log(self.sid)[0]["outcome"], "denied")

    def test_audit_redacts_values_without_breaking_json(self):
        grants.request(self.sid, "refresh", scope={"hosts": ["example.org"]}, purpose='Demo Bearer "quoted"', actor="user")
        audit = grants.audit_log(self.sid)
        self.assertEqual(audit[0]["detail"]["scope"], {"hosts": ["example.org"]})
        self.assertNotIn("quoted", audit[0]["detail"]["purpose"])

    def test_delete_reports_schedule_removed_by_hook(self):
        with db.write() as conn:
            conn.execute("INSERT INTO schedules(space,status,cadence,timezone) VALUES(?,'requested','0 * * * *','UTC')", (self.sid,))
        def remove(sid):
            with db.write() as conn:
                conn.execute("DELETE FROM schedules WHERE space=?", (sid,))
        with patch.dict(sys.modules, {"living_spaces_core.schedules": types.SimpleNamespace(on_delete=remove)}):
            result = projects.delete_space(self.sid, actor="user", confirm=self.sid)
        self.assertTrue(result["removed"]["schedule"])

    def test_all_bridge_mutations_recheck_session_inside_transaction(self):
        original_record = self.put()
        cases = [
            ("data.put", {"collection": "papers", "data": {"note": "Demo"}}),
            ("data.delete", {"collection": "papers", "id": "paper", "base_rev": original_record["rev"]}),
            ("data.batch", {"ops": [{"op": "put", "collection": "papers", "data": {}}]}),
            ("log", {"entries": [{"level": "error", "msg": "Demo"}]}),
        ]
        original_call = bridge._call
        for op, args in cases:
            with self.subTest(op=op):
                session = sessions.open_session(self.sid)["session"]
                def close_before_call(*call_args):
                    sessions.close_session(session)
                    return original_call(*call_args)
                with patch.object(bridge, "_call", close_before_call):
                    reply = bridge.dispatch(self.sid, session, op, args)
                self.assertEqual(reply["error"]["code"], "session_invalid")
                self.assertEqual(records.get(self.sid, "papers", "paper"), original_record)
                self.assertEqual(self.counts()["records"], 1)
                self.assertEqual(logs.read_logs(self.sid), [])

    def test_result_is_discarded_if_handler_closes_session(self):
        session = sessions.open_session(self.sid)["session"]
        def list_runs(*args, **kwargs):
            sessions.close_session(session)
            return [{"id": "demo"}]
        with patch.dict(sys.modules, {"living_spaces_core.runs": types.SimpleNamespace(list_runs=list_runs)}):
            reply = bridge.dispatch(self.sid, session, "runs.list", {})
        self.assertEqual(reply["error"]["code"], "session_invalid")
        self.assertNotIn("result", reply)

    def test_delete_schedule_failure_preserves_space(self):
        def fail(sid):
            raise SpacesError("blocked", "Cron unavailable", reason="no_handler")
        with patch.dict(sys.modules, {"living_spaces_core.schedules": types.SimpleNamespace(on_delete=fail)}):
            self.error("blocked", projects.delete_space, self.sid, actor="user", confirm=self.sid)
        self.assertEqual(projects.get_space(self.sid)["id"], self.sid)


class LogAndStorageTests(CoreCase):
    def test_secret_redaction_and_space_isolation(self):
        secrets = ["sk-demoSecret123", "ghp_demoSecret123", "gho_demoSecret123", "Bearer demoSecret123", "password=demoSecret123", "a" * 40,
                   "YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXo12345=="]
        logs.add_logs(self.sid, None, [{"level": "error", "msg": "Demo " + " ".join(secrets)}])
        message = logs.read_logs(self.sid)[0]["msg"]
        for secret in secrets:
            self.assertNotIn(secret, message)
        self.assertIn("Demo", message)
        other = self.create("Other")["id"]
        self.assertEqual(logs.read_logs(other), [])

    def test_quoted_passwords_and_bearer_tokens_are_redacted(self):
        logs.add_logs(self.sid, None, [{"level": "info", "msg": 'Demo password="demo words" Bearer "demo-token"'}])
        message = logs.read_logs(self.sid)[0]["msg"]
        self.assertNotIn("demo words", message)
        self.assertNotIn("demo-token", message)

    def test_log_limits_reject_whole_call_and_keep_last_2000(self):
        self.error("limit", logs.add_logs, self.sid, None, [{"level": "info", "msg": "x"}] * 51)
        self.error("limit", logs.add_logs, self.sid, None, [{"level": "info", "msg": "x" * 4001}])
        self.assertEqual(logs.read_logs(self.sid), [])
        for batch in range(41):
            logs.add_logs(self.sid, None, [{"level": "info", "msg": f"Demo {batch * 50 + index}"} for index in range(50)])
        saved = logs.read_logs(self.sid, limit=3000)
        self.assertEqual(len(saved), 2000)
        self.assertEqual((saved[0]["msg"], saved[-1]["msg"]), ("Demo 2049", "Demo 50"))

    def test_storage_pragmas_and_new_database_same_path(self):
        with db.read() as conn:
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 1)
            self.assertEqual(conn.execute("PRAGMA journal_mode").fetchone()[0], "wal")
            self.assertEqual(conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            self.assertEqual(conn.execute("PRAGMA busy_timeout").fetchone()[0], 5000)
        for suffix in ("", "-wal", "-shm"):
            Path(str(db.db_path()) + suffix).unlink(missing_ok=True)
        self.assertEqual(projects.list_spaces(), [])

    def test_import_does_not_load_upkeep(self):
        code = "import sys; sys.path.insert(0, sys.argv[1]); import living_spaces_core; assert not any('living_spaces_core.' + n in sys.modules for n in ('runs','feeds','schedules'))"
        subprocess.run([sys.executable, "-c", code, str(ROOT / "src" / "living-spaces")], check=True, capture_output=True)


if __name__ == "__main__":
    unittest.main()
