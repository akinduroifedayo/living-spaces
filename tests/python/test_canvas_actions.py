import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/living-spaces"))
from living_spaces_core import actions, bridge, db, projects, records, sessions, SpacesError


class CanvasActions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / ".run-evidence/tmp")
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {"LIVING_SPACES_DB": str(Path(self.temp.name) / "spaces.db"), "HERMES_HOME": self.temp.name})
        self.env.start()
        self.addCleanup(self.env.stop)
        summary = patch.object(projects.upkeep, "summary", return_value=None)
        summary.start()
        self.addCleanup(summary.stop)
        self.sid = projects.create_space("Canvas", owner="Display attribution", author="agent:test", files={"index.html": "hello"})["id"]
        self.session = sessions.open_session(self.sid)["session"]
        self.binding = {"profile_id": "/native/owner", "stored_session_id": "physical-segment", "conversation_id": "conversation", "session_key": "native-key"}
        self.target = {"profile_id": "/native/owner", "session_id": "canonical-session", "route": {
            "connectionId": "registered-owner", "profile": "desktop-owner", "targetProfile": "owner", "mode": "remote"}}
        actions.bind_maintainer(self.sid, self.binding)

    def claim(self, key="click-1", text="Explain this", refs=None, session=None):
        return actions.claim_action(self.sid, session or self.session, activation_id=key, text=text, records=refs or [], target=self.target)

    def receipt(self, intent, status="terminal", outcome="completed"):
        return {"admission_id": "admission-1", "ref": {"profile_id": self.target["profile_id"], "session_id": self.target["session_id"]}, "status": status, "outcome": outcome}

    def test_unbound_old_spaces_and_guest_dispatch_fail_closed(self):
        other = projects.create_space("Old canvas", owner="Guessed profile", author="test")["id"]
        session = sessions.open_session(other)["session"]
        with self.assertRaisesRegex(SpacesError, "No maintaining session"):
            actions.action_context(other, session)
        reply = bridge.dispatch(self.sid, self.session, "bot.request", {"activation_id": "guest", "text": "act"})
        self.assertFalse(reply["ok"])
        self.assertEqual(reply["error"]["code"], "blocked")

    def test_maintainer_is_immutable_and_survives_restore(self):
        actions.bind_maintainer(self.sid, dict(self.binding))
        with self.assertRaisesRegex(SpacesError, "different maintaining"):
            actions.bind_maintainer(self.sid, {**self.binding, "stored_session_id": "other"})
        projects.write_files(self.sid, files={"index.html": "changed"}, author="test", summary="change")
        projects.restore_revision(self.sid, 1, author="test")
        self.assertEqual(actions.action_context(self.sid, self.session)["maintainer"], self.binding)

    def test_same_key_same_payload_and_unresolved_other_keys_coalesce(self):
        first = self.claim()
        self.assertTrue(first["dispatch"])
        self.assertEqual(self.claim()["action"], first["action"])
        second = self.claim("click-2", "Different request")
        self.assertFalse(second["dispatch"])
        self.assertEqual(second["action"], first["action"])
        for key in ("click-1", "click-2"):
            with self.assertRaisesRegex(SpacesError, "different request"):
                self.claim(key, "Changed payload")

    def test_concurrent_mounts_admit_one_immutable_intent(self):
        second_session = sessions.open_session(self.sid)["session"]
        barrier = threading.Barrier(2)
        results, errors = [], []
        def activate(key, session):
            try:
                barrier.wait()
                results.append(self.claim(key, session=session))
            except Exception as error:
                errors.append(error)
        threads = [threading.Thread(target=activate, args=("first", self.session)), threading.Thread(target=activate, args=("second", second_session))]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        self.assertEqual(sum(item["dispatch"] for item in results), 1)
        self.assertEqual(results[0]["action"]["input_id"], results[1]["action"]["input_id"])

    def test_reload_recovers_intent_and_close_rejects_delivery(self):
        intent = self.claim()["action"]
        sessions.close_session(self.session)
        with self.assertRaises(SpacesError):
            actions.observe_action(self.sid, self.session, activation_id="click-1", receipt=self.receipt(intent))
        reopened = sessions.open_session(self.sid)["session"]
        self.assertEqual(actions.action_context(self.sid, reopened)["action"], intent)
        self.assertFalse(self.claim("reloaded", session=reopened)["dispatch"])

    def test_only_correlated_terminal_receipt_releases_coalescing(self):
        intent = self.claim()["action"]
        wrong = {**self.receipt(intent), "ref": {"profile_id": "/other", "session_id": "canonical-session"}}
        with self.assertRaises(SpacesError):
            actions.observe_action(self.sid, self.session, activation_id="click-1", receipt=wrong)
        for status in ("queued", "started", "unknown"):
            actions.observe_action(self.sid, self.session, activation_id="click-1", receipt=self.receipt(intent, status, None))
            self.assertFalse(self.claim("again-" + status)["dispatch"])
        actions.observe_action(self.sid, self.session, activation_id="click-1", receipt=self.receipt(intent))
        self.assertFalse(self.claim()["dispatch"])
        self.assertTrue(self.claim("next")["dispatch"])
        self.assertEqual(actions.action_context(self.sid, self.session, "click-1")["action"]["input_id"], intent["input_id"])

    def test_record_context_is_bounded_scoped_and_frozen(self):
        records.put(self.sid, "notes", "one", {"note": "original"}, actor="user")
        refs = [{"collection": "notes", "id": "one"}]
        first = self.claim(refs=refs)["action"]
        records.put(self.sid, "notes", "one", {"note": "newer"}, actor="user", base_rev=1)
        self.assertEqual(self.claim(refs=refs)["action"]["text"], first["text"])
        self.assertIn('"note": "original"', first["text"])
        with self.assertRaises(SpacesError):
            self.claim("oversized", "a" * (actions.TEXT_BYTES + 1))
        with self.assertRaises(SpacesError):
            self.claim("too-many", refs=refs * 21)
        with self.assertRaises(SpacesError):
            self.claim("escape", refs=[{"collection": "notes", "id": "../secret"}])

    def test_unavailable_record_rolls_back_and_wrong_profile_cannot_claim(self):
        with self.assertRaises(SpacesError):
            self.claim(refs=[{"collection": "notes", "id": "missing"}])
        self.assertIsNone(actions.action_context(self.sid, self.session)["action"])
        self.target["profile_id"] = "/ambient/profile"
        with self.assertRaises(SpacesError):
            self.claim()
        self.assertIsNone(actions.action_context(self.sid, self.session)["action"])

    def test_native_creation_capture_uses_real_context_fields_not_args(self):
        path = ROOT / "src/living-spaces/__init__.py"
        spec = importlib.util.spec_from_file_location("canvas_plugin", path, submodule_search_locations=[str(path.parent)])
        plugin = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = plugin
        spec.loader.exec_module(plugin)
        constants = types.ModuleType("hermes_constants")
        constants.get_hermes_home = lambda: Path(self.temp.name)
        session_module = types.ModuleType("hermes_cli.plugin_session")
        session_module.session_key = lambda: "trusted-key"
        with patch.dict(sys.modules, {"hermes_constants": constants, "hermes_cli.plugin_session": session_module}):
            captured = plugin._maintainer({"session_id": "physical", "conversation_id": "logical", "profile_name": "ambient"})
            self.assertEqual(captured, {"profile_id": str(Path(self.temp.name).resolve()), "stored_session_id": "physical", "conversation_id": "logical", "session_key": "trusted-key"})
            self.assertIsNone(plugin._maintainer({"profile_name": "ambient"}))
            session_module.session_key = lambda: ""
            self.assertIsNone(plugin._maintainer({"session_id": "physical", "conversation_id": "logical"}))

    def test_parent_row_delete_cascades_action_metadata(self):
        self.claim()
        with db.write() as conn:
            conn.execute("DELETE FROM spaces WHERE id=?", (self.sid,))
        with db.read() as conn:
            for table in ("maintainers", "action_intents", "action_keys"):
                self.assertEqual(conn.execute(f"SELECT count(*) FROM {table} WHERE space=?", (self.sid,)).fetchone()[0], 0)

    def test_creation_handler_binds_and_missing_context_is_visible(self):
        path = ROOT / "src/living-spaces/__init__.py"
        spec = importlib.util.spec_from_file_location("canvas_creation_plugin", path, submodule_search_locations=[str(path.parent)])
        plugin = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = plugin
        spec.loader.exec_module(plugin)
        with patch.object(plugin, "_maintainer", return_value=self.binding):
            response = json.loads(plugin._handler(plugin.spaces_create)({"name": "Native built", "files": {"index.html": "test"}, "libraries": []}))
        self.assertTrue(response["ok"])
        sid = response["result"]["space"]
        session = sessions.open_session(sid)["session"]
        self.assertEqual(actions.action_context(sid, session)["maintainer"], self.binding)
        response = json.loads(plugin._handler(plugin.spaces_create)({"name": "Unbound", "files": {"index.html": "test"}, "libraries": []}))
        self.assertTrue(response["ok"])
        self.assertTrue(any("native maintaining-session context was missing" in warning for warning in response["result"]["warnings"]))

    def test_rest_action_endpoints_are_session_bound_and_reject_extra_fields(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        path = ROOT / "src/living-spaces/dashboard/plugin_api.py"
        spec = importlib.util.spec_from_file_location("canvas_action_api", path)
        api = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(api)
        app = FastAPI()
        app.include_router(api.router)
        with TestClient(app) as client:
            base = f"/spaces/{self.sid}/actions"
            self.assertEqual(client.post(base + "/context", json={"session": self.session}).status_code, 200)
            response = client.post(base + "/claim", json={"session": self.session, "activation_id": "endpoint", "text": "explain", "records": [], "target": self.target})
            self.assertEqual(response.status_code, 200)
            intent = response.json()["action"]
            self.assertTrue(response.json()["dispatch"])
            response = client.post(base + "/observe", json={"session": self.session, "activation_id": "endpoint", "receipt": self.receipt(intent, "queued", None)})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(client.post(base + "/context", json={"session": self.session, "route": "guest"}).status_code, 400)
            sessions.close_session(self.session)
            self.assertEqual(client.post(base + "/context", json={"session": self.session}).status_code, 403)
