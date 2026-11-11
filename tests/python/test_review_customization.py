"""Kept F03, F04 and F08 regressions, using real core/SQLite/adapters.

HTTPS responses are synthetic; no model, ticker or network runs.
"""
from contextlib import ExitStack
import copy
import unittest
from unittest.mock import patch

from tests.python.review_customization_support import (
    PUBLIC, CustomizationFixture, Response,
)


class ReviewCustomizationTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.fx = CustomizationFixture(self.stack)

    def redirect_post(self, transition):
        fx = self.fx
        sid = fx.make()
        session = fx.sessions.open_session(sid)["session"]

        def on_response(response):
            if response.status == 307:
                if transition == "close":
                    fx.sessions.close_session(session)
                elif transition == "revoke":
                    fx.grants.decide(sid, "net", "revoke")

        def observe():
            with fx.db.read() as conn:
                row = conn.execute("SELECT closed_at FROM sessions WHERE id=?", (session,)).fetchone()
                return {"closed": row["closed_at"] is not None}

        transport = fx.transport([Response(307, {"Location": "https://second.example/side-effect"}), Response()],
                                 on_response, observe)
        with patch.object(fx.net, "fetch", wraps=fx.net.fetch) as fetch:
            reply = fx.bridge.dispatch(sid, session, "net.fetch", {
                "url": "https://first.example/start", "method": "POST", "body": "demo",
            })
        return reply, transport, session, fetch.call_args

    def test_f03_bridge_passes_bound_session_to_real_net_fetch(self):
        reply, transport, session, call = self.redirect_post("none")
        self.assertTrue(reply["ok"], reply)
        self.assertEqual(len(transport.requests), 2)
        self.assertEqual(call.kwargs.get("session"), session)

    def test_f03_closed_session_prevents_redirect_post(self):
        reply, transport, _session, _call = self.redirect_post("close")
        self.assertEqual(reply["error"]["code"], "session_invalid")
        self.assertEqual([(call["host"], call["method"], call["body"], call["closed"])
                          for call in transport.requests], [("first.example", "POST", b"demo", False)])
        self.assertEqual(len(transport.connections), 1)

    def test_f03_net_revocation_prevents_redirect_post_control(self):
        reply, transport, _session, _call = self.redirect_post("revoke")
        self.assertEqual(reply["error"]["code"], "not_granted")
        self.assertEqual([(call["host"], call["method"]) for call in transport.requests],
                         [("first.example", "POST")])

    def test_f03_open_session_preserves_redirect_post_control(self):
        reply, transport, _session, _call = self.redirect_post("none")
        self.assertTrue(reply["ok"], reply)
        self.assertEqual(reply["result"]["text"], "ok")
        self.assertEqual([(call["host"], call["method"], call["body"], call["closed"])
                          for call in transport.requests], [
                              ("first.example", "POST", b"demo", False),
                              ("second.example", "POST", b"demo", False),
                          ])

    def source_revisions(self):
        fx = self.fx
        sid = fx.make()
        user = fx.records.put(sid, "items", "one", {"notes": "Keep my note"}, actor="user")
        fx.source(sid, "initial")
        old = fx.records.get(sid, "items", "one")["rev"]
        self.assertEqual(old, 2)
        fx.source(sid, "newer", old)
        current = fx.records.get(sid, "items", "one")
        self.assertEqual(current["rev"], 3)
        return sid, user, old, current

    def test_f04_stale_source_revision_conflicts_and_rolls_back_whole_batch(self):
        fx = self.fx
        sid, user, old, current = self.source_revisions()
        fx.source_ops(sid, [{"op": "put", "collection": "items", "id": "other",
                            "source": {"title": "Keep other source"}}])
        other = fx.records.get(sid, "items", "other")
        before_seq = fx.records.changes_since(sid, 0)["seq"]
        error = None
        try:
            fx.source_ops(sid, [
                {"op": "put", "collection": "items", "id": "other", "base_rev": other["rev"],
                 "source": {"title": "Must roll back"}},
                {"op": "put", "collection": "items", "id": "one", "base_rev": old,
                 "source": {"title": "stale overwrites newer"}},
            ])
        except fx.core.SpacesError as exc:
            error = exc
        final = fx.records.get(sid, "items", "one")
        with self.subTest(boundary="stale source conflict"):
            self.assertIsNotNone(error, "source-owned base_rev=2 must conflict with current rev=3")
            self.assertEqual(error.code, "conflict")
        with self.subTest(boundary="current source and metadata preserved"):
            self.assertEqual(final, current)
        with self.subTest(boundary="whole batch rollback"):
            self.assertEqual(fx.records.get(sid, "items", "other"), other)
            self.assertEqual(fx.records.changes_since(sid, 0)["seq"], before_seq)
        self.assertEqual(final["data"], user["data"])

    def test_f04_current_source_revision_preserves_user_fields_control(self):
        fx = self.fx
        sid, user, old, current = self.source_revisions()
        result = fx.source(sid, "current approved update", current["rev"])
        final = fx.records.get(sid, "items", "one")
        self.assertEqual(result, {"added": 0, "updated": 1, "unchanged": 0})
        self.assertEqual(final["source"], {"title": "current approved update"})
        self.assertEqual(final["source_meta"]["handler"], "agent")
        self.assertEqual(final["data"], user["data"])
        self.assertEqual(final["rev"], 4)

    def test_f04_stale_user_revision_still_conflicts_control(self):
        fx = self.fx
        sid, user, old, current = self.source_revisions()
        with self.assertRaises(fx.core.SpacesError) as error:
            fx.records.put(sid, "items", "one", {"notes": "stale"}, actor="agent:review", base_rev=old)
        self.assertEqual(error.exception.code, "conflict")
        self.assertEqual(fx.records.get(sid, "items", "one"), current)

    def test_f08_feed_rejects_approved_loopback_before_transport(self):
        fx = self.fx
        url = "https://127.0.0.1:8443/feed"
        sid = fx.make(handler="feed", url=url)
        pinned, legacy = fx.feed_transports(b"private fixture content")
        error = None
        try:
            fx.feeds.fetch(sid, url)
        except fx.core.SpacesError as exc:
            error = exc
        with self.subTest(boundary="public address refusal"):
            self.assertIsNotNone(error, "Internet access cannot allow a loopback destination")
            self.assertEqual((error.code, error.extra.get("reason")), ("blocked", "private_address"))
        with self.subTest(boundary="no private egress"):
            self.assertEqual(legacy, [])
            self.assertEqual(pinned.connections, [])

    def test_f08_public_feed_uses_vetted_pinned_destination(self):
        fx = self.fx
        sid = fx.make(handler="feed")
        pinned, legacy = fx.feed_transports(b"public fixture content")
        self.assertEqual(fx.feeds.fetch(sid, "https://example.org/feed"), b"public fixture content")
        self.assertEqual(pinned.connections, [("example.org", 443, PUBLIC)])
        self.assertEqual(legacy, [])
        self.assertEqual(pinned.requests[0]["headers"]["Host"], "example.org")

    def test_f08_feed_needs_internet_access(self):
        fx = self.fx
        sid = fx.make(handler="feed")
        pinned, legacy = fx.feed_transports(b"public fixture content")
        self.assertEqual(fx.feeds.fetch(sid, "https://example.org/feed"), b"public fixture content")
        self.assertEqual(len(pinned.requests) + len(legacy), 1)
        fx.grants.decide(sid, "net", "revoke")
        with self.assertRaises(fx.core.SpacesError) as error:
            fx.feeds.fetch(sid, "https://example.org/feed")
        self.assertEqual(error.exception.code, "not_granted")
        self.assertEqual(len(pinned.requests) + len(legacy), 1)

    def test_f08_mediated_net_rejects_loopback_control(self):
        fx = self.fx
        sid = fx.make(handler="feed", url="https://127.0.0.1:8443/feed")
        transport = fx.transport([Response(body=b"private fixture content")])
        with self.assertRaises(fx.core.SpacesError) as error:
            fx.net.fetch(sid, "https://127.0.0.1:8443/feed")
        self.assertEqual((error.exception.code, error.exception.extra["reason"]),
                         ("blocked", "private_address"))
        self.assertEqual(transport.connections, [])


if __name__ == "__main__":
    unittest.main()
