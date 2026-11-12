import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/living-spaces"))
import living_spaces_core as core
from desktop_rpc import register_desktop_rpc


class DesktopRpcTests(unittest.TestCase):
    def setUp(self):
        home = tempfile.TemporaryDirectory()
        self.addCleanup(home.cleanup)
        environment = patch.dict(os.environ, HERMES_HOME=home.name,
                                 LIVING_SPACES_DB=str(Path(home.name) / "spaces.db"))
        environment.start()
        self.addCleanup(environment.stop)
        self.sid = core.create_space("Desktop RPC", owner="test", author="agent:test",
                                     files={"index.html": "<h1>Public demo</h1>"})["id"]
        self.session = core.open_session(self.sid)["session"]
        self.methods = {}

        class Context:
            def register_rpc(ctx, name, handler):
                self.methods[name] = handler
                return name

        self.assertEqual(register_desktop_rpc(Context(), lambda: core), "close_session")
        self.assertEqual(set(self.methods), {"close_session"})

    def close(self, params):
        return self.methods["close_session"](params, session_id=None)

    def test_closes_only_bound_space_session_and_is_idempotent(self):
        other = core.open_session(self.sid)["session"]
        params = {"space_id": self.sid, "session": self.session}
        self.assertEqual(self.close(params), {"closed": True})
        self.assertEqual(self.close(params), {"closed": True})
        with self.assertRaises(core.SpacesError) as caught:
            core.require(self.sid, self.session)
        self.assertEqual(caught.exception.code, "session_invalid")
        core.require(self.sid, other)

    def test_mismatched_space_cannot_close_another_session(self):
        other = core.create_space("Other", owner="test", author="agent:test")["id"]
        self.assertEqual(self.close({"space_id": other, "session": self.session}), {"closed": True})
        core.require(self.sid, self.session)

    def test_unknown_and_closed_sessions_are_successfully_closed(self):
        self.assertEqual(self.close({"space_id": self.sid, "session": "unknown-session"}), {"closed": True})
        core.close_session(self.session)
        self.assertEqual(self.close({"space_id": self.sid, "session": self.session}), {"closed": True})

    def test_rejects_invalid_shape_and_scope_override_without_closing(self):
        valid = {"space_id": self.sid, "session": self.session}
        for params in [None, [], {}, {"space_id": self.sid}, {**valid, "profile": "other"},
                       {**valid, "connectionId": "other"}, {**valid, "session_id": "native"},
                       {**valid, "space_id": "../bad"}, {**valid, "space_id": "bad\n"},
                       {**valid, "session": ""}, {**valid, "session": 1}]:
            with self.subTest(params=params):
                self.assertEqual(self.close(params)["error"]["code"], "invalid")
                core.require(self.sid, self.session)

    def test_other_core_errors_are_not_reported_as_closed(self):
        with patch.object(core, "require", side_effect=core.SpacesError("blocked", "Unavailable")):
            self.assertEqual(self.close({"space_id": self.sid, "session": self.session}),
                             {"error": {"code": "blocked", "message": "Unavailable"}})
        core.require(self.sid, self.session)

    def test_storage_failure_is_not_hidden(self):
        with patch.object(core, "close_session", side_effect=OSError("Storage unavailable")):
            with self.assertRaisesRegex(OSError, "Storage unavailable"):
                self.close({"space_id": self.sid, "session": self.session})
        core.require(self.sid, self.session)
