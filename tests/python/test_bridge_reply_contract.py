"""Bridge replies keep the documented error detail, and passive inspection answers reads with the live envelope."""
from unittest.mock import patch

from .test_core_store import CoreCase
from living_spaces_core import bridge, grants, inspection, records, sessions
from living_spaces_core.errors import SpacesError


class LiveNotGrantedTests(CoreCase):
    def setUp(self):
        super().setUp()
        self.session = sessions.open_session(self.sid)["session"]

    def dispatch(self, op, args):
        return bridge.dispatch(self.sid, self.session, op, args)

    def test_not_granted_carries_its_capability(self):
        grants.decide(self.sid, "data", "revoke")
        reply = self.dispatch("data.query", {"collection": "papers"})
        self.assertEqual(reply, {"ok": False, "outcome": {"status": "rejected"}, "error": {
            "code": "not_granted", "message": "Capability or requested scope is not granted", "capability": "data"}})

    def test_unknown_operation_is_not_granted_with_its_name(self):
        reply = self.dispatch("files.read", {})
        self.assertEqual(reply["error"], {"code": "not_granted", "message": "Operation is unavailable", "capability": "files.read"})

    def test_authority_lost_mid_call_replaces_the_operation_detail(self):
        self.put("paper", {"note": "private"})
        original = records.query

        def revoke_then_conflict(*args, **kwargs):
            original(*args, **kwargs)
            grants.decide(self.sid, "data", "revoke")
            raise SpacesError("conflict", "Stale", current=records.get(self.sid, "papers", "paper"))

        with patch.object(records, "query", side_effect=revoke_then_conflict):
            reply = self.dispatch("data.query", {"collection": "papers"})
        self.assertEqual(reply["error"], {"code": "not_granted", "message": "Capability or requested scope is not granted",
                                          "capability": "data"})
        self.assertNotIn("private", str(reply))
        self.assertEqual(reply["outcome"], {"status": "rejected"})

    def test_closed_session_is_reported_as_session_invalid(self):
        sessions.close_session(self.session)
        reply = self.dispatch("meta", {})
        self.assertEqual(reply["error"]["code"], "session_invalid")
        self.assertNotEqual(reply["error"]["message"], "Operation could not be completed")


class PassiveMatchesLiveTests(CoreCase):
    def test_reads_answer_exactly_as_the_live_bridge(self):
        self.put("a", {"rank": 2})
        self.put("b", {"rank": 1})
        calls = [("data.query", {"collection": "papers", "order": "rank"}),
                 ("data.get", {"collection": "papers", "id": "a"}),
                 ("data.get", {"collection": "papers", "id": "missing"}),
                 ("data.query", {"collection": "papers", "bogus": 1}),
                 ("runs.list", {"limit": 0}),
                 ("meta", {}),
                 ("freshness", {}),
                 ("files.read", {})]
        for granted in (True, False):
            grants.decide(self.sid, "data", "grant" if granted else "revoke")
            conn = inspection._open_snapshot()
            self.addCleanup(conn.close)
            adapter = inspection.PassiveAdapter(inspection.Snapshot(conn, self.sid, 1))
            session = sessions.open_session(self.sid)["session"]
            for op, args in calls:
                with self.subTest(granted=granted, op=op, args=args):
                    self.assertEqual(adapter.call(op, dict(args)), bridge.dispatch(self.sid, session, op, dict(args)))
