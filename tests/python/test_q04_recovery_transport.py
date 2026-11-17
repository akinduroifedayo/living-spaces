"""Q04 offline adapter contracts. Fixtures are synthetic, not captured native evidence."""
import importlib.util
import os
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from .test_core_store import CoreCase, ROOT, db, projects, records


class Q04RecoveryTransportTests(CoreCase):
    def http_client(self):
        path = ROOT / "src/living-spaces/dashboard/plugin_api.py"
        spec = importlib.util.spec_from_file_location("q04_recovery_transport_api", path)
        assert spec is not None and spec.loader is not None
        api = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(api)
        app = FastAPI()
        app.include_router(api.router)
        client = TestClient(app)
        self.addCleanup(client.close)
        return client

    def database_state(self):
        with db.read() as conn:
            return tuple(conn.iterdump())

    def recovery_list(self, client, sid=None):
        response = client.get(f"/spaces/{sid or self.sid}/recovery-points")
        self.assertEqual(response.status_code, 200,
                         "Q04 requires GET recovery-points, not a missing-route 404: " + response.text)
        result = response.json()
        self.assertIsInstance(result, list)
        return result

    def test_core_recovery_metadata_control(self):
        self.assertEqual(records.list_recovery_points(self.sid), [])
        self.put(data={"note": "Q04 synthetic record, not recovery metadata"})
        point = records.create_recovery_point(self.sid, "Q04 synthetic checkpoint")
        rows = records.list_recovery_points(self.sid)
        self.assertEqual(len(rows), 1)
        self.assertEqual(set(rows[0]), {"id", "space", "reason", "data_version", "head_rev", "created_at"})
        self.assertEqual(rows[0]["id"], point)
        self.assertEqual(rows[0]["space"], self.sid)
        self.assertEqual(rows[0]["reason"], "Q04 synthetic checkpoint")
        self.assertEqual((rows[0]["data_version"], rows[0]["head_rev"]), (1, 1))
        self.assertIsInstance(rows[0]["created_at"], (int, float))
        self.assertNotIn("snapshot", rows[0])

    def test_existing_detail_and_revision_paths_control(self):
        self.write({"index.html": "<h1>Q04 synthetic revised code</h1>"})
        client = self.http_client()
        before = self.database_state()
        detail = client.get(f"/spaces/{self.sid}")
        history = client.get(f"/spaces/{self.sid}/revisions")
        self.assertEqual(self.database_state(), before)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual((detail.json()["id"], detail.json()["data_version"], detail.json()["head_rev"]),
                         (self.sid, 1, 2))
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.json(), projects.list_revisions(self.sid, files=False))
        self.assertEqual([row["rev"] for row in history.json()], [2, 1])
        self.assertEqual(records.list_recovery_points(self.sid), [])

    def test_existing_code_only_restore_keeps_current_records_control(self):
        original = self.put(data={"note": "Q04 synthetic original"})
        self.write({"index.html": "<h1>Q04 synthetic new code</h1>"})
        current = self.put(data={"note": "Q04 synthetic newer user edit"}, base_rev=original["rev"])
        client = self.http_client()
        restored = client.post(f"/spaces/{self.sid}/revisions/1/restore")
        self.assertEqual(restored.status_code, 200)
        self.assertEqual((restored.json()["kind"], restored.json()["restored_from"]), ("restore", 1))
        self.assertIn("Public demo", projects.read_file(self.sid, "index.html")["text"])
        self.assertEqual(records.get(self.sid, "papers", "paper"), current)
        self.assertEqual(records.list_recovery_points(self.sid), [])

    def test_existing_cross_version_refusals_control(self):
        self.put(data={"note": "Q04 synthetic pre-migration record"})
        point = records.create_recovery_point(self.sid, "Q04 synthetic version one")
        self.write({}, manifest=self.manifest_v2([]))
        client = self.http_client()
        before = self.database_state()
        refused = client.post(f"/spaces/{self.sid}/revisions/1/restore")
        self.assertEqual(refused.status_code, 409)
        self.assertEqual(refused.json()["error"]["code"], "incompatible")
        self.assertEqual((refused.json()["error"]["from_version"], refused.json()["error"]["to_version"]),
                         (2, 1))
        error = self.error("incompatible", records.restore_recovery_point, self.sid, point, actor="user")
        self.assertEqual((error["from_version"], error["to_version"]), (2, 1))
        self.assertEqual(self.database_state(), before)

    def test_empty_recovery_list_is_not_code_history(self):
        client = self.http_client()
        history = client.get(f"/spaces/{self.sid}/revisions")
        self.assertEqual(history.status_code, 200)
        self.assertEqual([row["rev"] for row in history.json()], [1])
        self.assertEqual(records.list_recovery_points(self.sid), [])
        self.assertEqual(self.recovery_list(client), [])

    def test_populated_list_preserves_core_metadata_and_newest_first_order(self):
        self.put(data={"note": "Q04 synthetic snapshot content must stay private to the store"})
        first = records.create_recovery_point(self.sid, "Q04 synthetic first point")
        self.write({"index.html": "<h1>Q04 synthetic later code</h1>"})
        second = records.create_recovery_point(self.sid, "Q04 synthetic second point")
        expected = records.list_recovery_points(self.sid)
        self.assertEqual([row["id"] for row in expected], [second, first])
        client = self.http_client()
        rows = self.recovery_list(client)
        self.assertEqual(rows, expected)
        self.assertEqual([row["reason"] for row in rows],
                         ["Q04 synthetic second point", "Q04 synthetic first point"])
        self.assertEqual([row["head_rev"] for row in rows], [2, 1])
        for row in rows:
            self.assertEqual(set(row), {"id", "space", "reason", "data_version", "head_rev", "created_at"})
            self.assertNotIn("snapshot", row)
            self.assertNotIn("files", row)
            self.assertNotIn("manifest", row)

    def test_migrated_points_keep_source_versions_distinct_from_current_space(self):
        self.put(data={"stat": "Q04 synthetic reading"})
        self.write({"index.html": "<h1>Q04 synthetic version two</h1>"}, manifest=self.manifest_v2([
            {"op": "rename_field", "collection": "papers", "from": "stat", "to": "status"},
        ]))
        current_point = records.create_recovery_point(self.sid, "Q04 synthetic version two checkpoint")
        expected = records.list_recovery_points(self.sid)
        self.assertEqual([row["data_version"] for row in expected], [2, 1])
        self.assertEqual([row["head_rev"] for row in expected], [2, 1])
        self.assertEqual(expected[0]["id"], current_point)
        self.assertEqual(expected[1]["reason"], "Before migration to data version 2")
        self.assertEqual(records.get(self.sid, "papers", "paper")["data"], {"status": "Q04 synthetic reading"})
        client = self.http_client()
        before = self.database_state()
        detail = client.get(f"/spaces/{self.sid}")
        response = client.get(f"/spaces/{self.sid}/recovery-points")
        self.assertEqual(self.database_state(), before)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["data_version"], 2)
        self.assertEqual(response.status_code, 200, "Migrated recovery points need a real GET route")
        self.assertEqual(response.json(), expected)
        self.assertEqual([row["data_version"] == detail.json()["data_version"] for row in response.json()],
                         [True, False])

    def test_missing_space_has_typed_not_found_without_creating_state(self):
        records.create_recovery_point(self.sid, "Q04 synthetic existing Space control")
        self.error("not_found", records.list_recovery_points, "q04-missing-space")
        client = self.http_client()
        control = client.get(f"/spaces/{self.sid}")
        self.assertEqual(control.status_code, 200)
        before = self.database_state()
        response = client.get("/spaces/q04-missing-space/recovery-points")
        self.assertEqual(self.database_state(), before)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json().get("error", {}).get("code"), "not_found",
                         "A router-level 404 is not a typed missing-Space response")

    def test_invalid_space_id_is_rejected_at_transport_boundary(self):
        client = self.http_client()
        control = client.get("/spaces/Invalid_ID")
        self.assertEqual(control.status_code, 400)
        self.assertEqual(control.json()["error"]["code"], "invalid")
        before = self.database_state()
        response = client.get("/spaces/Invalid_ID/recovery-points")
        self.assertEqual(self.database_state(), before)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json().get("error", {}).get("code"), "invalid")

    def test_recovery_lists_are_space_scoped(self):
        own = records.create_recovery_point(self.sid, "Q04 synthetic own Space point")
        other_sid = self.create("Q04 synthetic other Space")["id"]
        other = records.create_recovery_point(other_sid, "Q04 synthetic other Space point")
        self.assertNotEqual(own, other)
        self.assertEqual([row["id"] for row in records.list_recovery_points(self.sid)], [own])
        self.assertEqual([row["id"] for row in records.list_recovery_points(other_sid)], [other])
        client = self.http_client()
        own_rows = self.recovery_list(client)
        other_rows = self.recovery_list(client, other_sid)
        self.assertEqual(own_rows, records.list_recovery_points(self.sid))
        self.assertEqual(other_rows, records.list_recovery_points(other_sid))
        self.assertEqual({row["space"] for row in own_rows}, {self.sid})
        self.assertEqual({row["space"] for row in other_rows}, {other_sid})

    def test_same_space_and_point_ids_are_scoped_to_backend_profile_store(self):
        client = self.http_client()
        profiles = [Path(self.temp.name) / name for name in ("synthetic-profile-a", "synthetic-profile-b")]
        expected = []
        with patch.dict(os.environ, {"LIVING_SPACES_DB": ""}):
            for index, home in enumerate(profiles):
                with patch.object(db, "hermes_home", return_value=home):
                    self.assertEqual(db.db_path(), home / "plugin-data/living-spaces/spaces.db")
                    sid = self.create("Q04 synthetic shared name")["id"]
                    point = records.create_recovery_point(sid, f"Q04 synthetic profile {index}")
                    rows = records.list_recovery_points(sid)
                    self.assertEqual([row["id"] for row in rows], [point])
                    expected.append((sid, point, rows))
            self.assertEqual(expected[0][:2], expected[1][:2], "Exercise colliding IDs in independent stores")
            self.assertNotEqual(expected[0][2], expected[1][2])
            for home, (sid, point, rows) in zip(profiles, expected):
                with self.subTest(profile=home.name), patch.object(db, "hermes_home", return_value=home):
                    before = self.database_state()
                    response = client.get(f"/spaces/{sid}/recovery-points")
                    self.assertEqual(self.database_state(), before)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json(), rows)
                    self.assertEqual([row["id"] for row in response.json()], [point])

    def test_repeated_get_does_not_restore_touch_or_append_any_persisted_state(self):
        original = self.put(data={"note": "Q04 synthetic checkpoint data"})
        records.create_recovery_point(self.sid, "Q04 synthetic preserved snapshot")
        current = self.put(data={"note": "Q04 synthetic newer data must survive reads"}, base_rev=original["rev"])
        self.write({"index.html": "<h1>Q04 synthetic newer code must survive reads</h1>"})
        expected = records.list_recovery_points(self.sid)
        client = self.http_client()
        before = self.database_state()
        responses = [client.get(f"/spaces/{self.sid}/recovery-points") for _ in range(3)]
        self.assertEqual(self.database_state(), before)
        self.assertEqual(records.get(self.sid, "papers", "paper"), current)
        self.assertIn("newer code must survive reads", projects.read_file(self.sid, "index.html")["text"])
        for response in responses:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), expected)

    def test_get_remains_read_only_while_another_sqlite_writer_holds_lock(self):
        records.create_recovery_point(self.sid, "Q04 synthetic writer contention checkpoint")
        expected = records.list_recovery_points(self.sid)
        client = self.http_client()
        before = self.database_state()
        original_connect = db.connect

        def short_connect():
            conn = original_connect()
            conn.execute("PRAGMA busy_timeout=25")
            return conn

        holder = original_connect()
        holder.execute("BEGIN IMMEDIATE")
        try:
            with patch.object(db, "connect", side_effect=short_connect):
                self.assertEqual(records.list_recovery_points(self.sid), expected)
                response = client.get(f"/spaces/{self.sid}/recovery-points")
        finally:
            holder.execute("ROLLBACK")
            holder.close()
        self.assertEqual(self.database_state(), before)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected)

    def test_recovery_collection_has_no_mutating_http_methods(self):
        self.put(data={"note": "Q04 synthetic protected record"})
        records.create_recovery_point(self.sid, "Q04 synthetic protected checkpoint")
        client = self.http_client()
        before = self.database_state()
        responses = [(method, client.request(method, f"/spaces/{self.sid}/recovery-points"))
                     for method in ("POST", "PUT", "PATCH", "DELETE")]
        self.assertEqual(self.database_state(), before)
        for method, response in responses:
            with self.subTest(method=method):
                self.assertEqual(response.status_code, 405, "Only GET is commissioned for recovery-points")
