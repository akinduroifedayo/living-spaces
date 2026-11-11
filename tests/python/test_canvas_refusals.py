import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/living-spaces"))
from living_spaces_core import actions, db, projects, sessions, SpacesError


class CanvasRefusals(unittest.TestCase):
    def setUp(self):
        work = ROOT / ".run"
        work.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=work)
        self.addCleanup(self.temp.cleanup)
        env = patch.dict(os.environ, {"LIVING_SPACES_DB": str(Path(self.temp.name) / "spaces.db"), "HERMES_HOME": self.temp.name})
        env.start()
        self.addCleanup(env.stop)
        summary = patch.object(projects.upkeep, "summary", return_value=None)
        summary.start()
        self.addCleanup(summary.stop)
        self.sid = projects.create_space("Refusal fixture", owner="Demo", author="test", files={"index.html": "fixture"})["id"]
        self.session = sessions.open_session(self.sid)["session"]
        self.binding = {"profile_id": "/native/owner", "stored_session_id": "physical", "conversation_id": "logical", "session_key": "key"}
        self.target = {"profile_id": "/native/owner", "session_id": "logical", "route": {
            "connectionId": "registered", "profile": "desktop-owner", "targetProfile": "owner", "mode": "remote"}}
        actions.bind_maintainer(self.sid, self.binding)

    def claim(self, key="first"):
        return actions.claim_action(self.sid, self.session, activation_id=key, text="Explain the record", records=[], target=self.target)

    def reject(self, intent, reason="permission_denied", **overrides):
        args = {"session": self.session, "activation_id": intent["activation_id"], "input_id": intent["input_id"], "reason": reason}
        args.update(overrides)
        return actions.reject_action(self.sid, **args)

    def observe(self, intent):
        receipt = {"ref": {"profile_id": "/native/owner", "session_id": "logical"}, "admission_id": "native-1", "status": "queued"}
        return actions.observe_action(self.sid, self.session, activation_id=intent["activation_id"], receipt=receipt)

    def context(self, key="first"):
        return actions.action_context(self.sid, self.session, activation_id=key)["action"]

    def test_each_definitive_reason_preserves_identity_and_releases_slot(self):
        reasons = ("permission_denied", "queue_full", "invalid_params", "not_found", "profile_mismatch", "runtime_draining")
        for index, reason in enumerate(reasons):
            with self.subTest(reason=reason):
                key = f"intent-{index}"
                claim = self.claim(key)
                self.assertTrue(claim["dispatch"])
                original = claim["action"]
                result = self.reject(original, reason)
                self.assertTrue(result["recorded"])
                self.assertTrue(result["settled"])
                expected = {**original, "settled": True, "refusal_reason": reason}
                self.assertEqual(result["action"], expected)
                self.assertEqual(self.context(key), expected)
                replay = self.claim(key)
                self.assertFalse(replay["dispatch"])
                self.assertEqual(replay["action"], expected)

    def test_repeated_refusal_is_idempotent_and_conflicting_reason_is_atomic(self):
        intent = self.claim()["action"]
        first = self.reject(intent)
        self.assertEqual(self.reject(intent), first)
        with self.assertRaises(SpacesError):
            self.reject(intent, "queue_full")
        self.assertEqual(self.context(), first["action"])

    def test_mismatched_identity_and_ambiguous_reason_leave_intent_unresolved(self):
        intent = self.claim()["action"]
        for overrides in ({"input_id": "wrong"}, {"activation_id": "missing"}, {"reason": "admission_conflict"}, {"reason": "transport_error"}):
            with self.subTest(overrides=overrides):
                with self.assertRaises(SpacesError):
                    self.reject(intent, **overrides)
                self.assertEqual(self.context(), intent)

    def test_refusal_requires_a_live_session_for_the_same_space(self):
        intent = self.claim()["action"]
        other = projects.create_space("Other", owner="Demo", author="test")["id"]
        other_session = sessions.open_session(other)["session"]
        with self.assertRaises(SpacesError):
            self.reject(intent, session=other_session)
        sessions.close_session(self.session)
        with self.assertRaises(SpacesError):
            self.reject(intent)
        fresh = sessions.open_session(self.sid)["session"]
        self.assertEqual(actions.action_context(self.sid, fresh, activation_id="first")["action"], intent)

    def test_admitted_work_cannot_be_relabelled_as_unadmitted(self):
        intent = self.claim()["action"]
        self.observe(intent)
        admitted = self.context()
        self.assertEqual(admitted["admission_id"], "native-1")
        with self.assertRaises(SpacesError):
            self.reject(intent)
        self.assertEqual(self.context(), admitted)

    def test_saved_refusal_cannot_acquire_an_admission_after_reopen(self):
        intent = self.claim()["action"]
        saved = self.reject(intent)["action"]
        db._initialized.discard(str(db.db_path()))
        self.assertEqual(self.context(), saved)
        with self.assertRaises(SpacesError):
            self.observe(intent)
        self.assertEqual(self.context(), saved)
        self.assertTrue(self.claim("fresh")["dispatch"])

    def test_legacy_schema_migrates_idempotently_without_losing_an_intent(self):
        intent = self.claim()["action"]
        with db.write() as conn:
            conn.execute("ALTER TABLE action_intents DROP COLUMN refusal_reason")
        for _ in range(2):
            db._initialized.discard(str(db.db_path()))
            self.assertEqual(self.context(), intent)
        saved = self.reject(intent, "queue_full")["action"]
        db._initialized.discard(str(db.db_path()))
        self.assertEqual(self.context(), saved)

    def test_reject_endpoint_validates_fields_and_session(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        path = ROOT / "src/living-spaces/dashboard/plugin_api.py"
        spec = importlib.util.spec_from_file_location("canvas_refusal_api", path)
        assert spec is not None and spec.loader is not None
        api = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(api)
        app = FastAPI()
        app.include_router(api.router)
        intent = self.claim()["action"]
        body = {"session": self.session, "activation_id": "first", "input_id": intent["input_id"], "reason": "queue_full"}
        url = f"/spaces/{self.sid}/actions/reject"
        with TestClient(app) as client:
            self.assertEqual(client.post(url, json={**body, "receipt": {}}).status_code, 400)
            self.assertEqual(client.post(url, json={**body, "input_id": "wrong"}).status_code, 409)
            response = client.post(url, json=body)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["action"]["refusal_reason"], "queue_full")
            sessions.close_session(self.session)
            self.assertEqual(client.post(url, json=body).status_code, 403)

    def test_observation_and_refusal_race_has_one_consistent_winner(self):
        intent = self.claim()["action"]
        barrier = threading.Barrier(2)
        outcomes = []
        def run(kind):
            barrier.wait()
            try:
                self.reject(intent) if kind == "reject" else self.observe(intent)
                outcomes.append((kind, "saved"))
            except SpacesError:
                outcomes.append((kind, "conflict"))
        threads = [threading.Thread(target=run, args=(kind,)) for kind in ("reject", "observe")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(10)
            self.assertFalse(thread.is_alive())
        self.assertEqual(len(outcomes), 2)
        self.assertEqual(sorted(status for _, status in outcomes), ["conflict", "saved"])
        state = self.context()
        if ("reject", "saved") in outcomes:
            self.assertTrue(state["settled"])
            self.assertEqual(state["refusal_reason"], "permission_denied")
            self.assertIsNone(state["admission_id"])
        else:
            self.assertFalse(state["settled"])
            self.assertIsNone(state["refusal_reason"])
            self.assertEqual(state["admission_id"], "native-1")
