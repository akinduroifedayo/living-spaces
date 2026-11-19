"""Q14 public contracts on disposable real stores, not native acceptance evidence."""
import json
from unittest.mock import patch

from tests.python.test_c_tools import ToolCase, core
from tests.python.test_core_store import CoreCase, bridge, db, grants, records, sessions


PAGE_KEYS = {"records", "total", "seq", "has_more", "next_cursor"}


class Q14PublicQueryTests(ToolCase):
    def seed(self, count=None):
        sid = self.create(name="Q14 Public Query")["space"]
        ids = ("c", "a", "e", "b", "d") if count is None else tuple(
            f"p{index:04d}" for index in range(count))
        with patch.object(db, "now", return_value=100.0):
            for start in range(0, len(ids), 500):
                self.ok("spaces_write_records", space=sid, ops=[
                    {"op": "put", "collection": "papers", "id": rid,
                     "data": {"rank": 7, "status": "reading", "bucket": "keep"}}
                    for rid in ids[start:start + 500]
                ])
        return sid, sessions.open_session(sid)["session"]

    def tool_query(self, sid, **options):
        return self.call("spaces_query", space=sid, collection="papers", **options)

    def bridge_query(self, sid, session, **options):
        return bridge.dispatch(sid, session, "data.query", {"collection": "papers", **options})

    def page(self, reply):
        self.assertTrue(reply["ok"], f"new page capability absent or rejected: {reply}")
        result = reply["result"]
        self.assertEqual(set(result), PAGE_KEYS, "new page capability absent")
        self.assertIs(type(result["seq"]), int)
        self.assertIs(type(result["has_more"]), bool)
        self.assertEqual(result["next_cursor"] is not None, result["has_more"])
        return result

    def assert_ids(self, page, expected, total):
        self.assertEqual([row["id"] for row in page["records"]], expected)
        self.assertEqual(page["total"], total)

    def assert_error(self, reply, code):
        self.assertFalse(reply["ok"], reply)
        self.assertEqual(reply["error"]["code"], code, reply)
        self.assertNotIn("result", reply)
        self.assertNotIn("records", reply["error"])
        self.assertNotIn("next_cursor", reply["error"])
        return reply["error"]

    def test_legacy_registered_filter_and_bridge_envelopes(self):
        sid, session = self.seed()
        tool = self.tool_query(sid, where={"status": "reading"}, limit=2)
        canvas = self.bridge_query(sid, session, where={"status": "reading"}, limit=2)
        self.assertTrue(tool["ok"], tool)
        self.assertTrue(canvas["ok"], canvas)
        self.assertEqual(set(tool["result"]), {"records", "total", "seq"})
        self.assertEqual(tool["result"], canvas["result"])
        self.assert_ids(tool["result"], ["a", "b"], 5)

    def test_legacy_limits_remain_100_for_tool_500_for_bridge_and_allow_501(self):
        sid, session = self.seed(501)
        for invoke, default in ((lambda **opts: self.tool_query(sid, **opts), 100),
                                (lambda **opts: self.bridge_query(sid, session, **opts), 500)):
            with self.subTest(default=default):
                reply = invoke()
                self.assertTrue(reply["ok"], reply)
                self.assertEqual(set(reply["result"]), {"records", "total", "seq"})
                self.assert_ids(reply["result"], [f"p{i:04d}" for i in range(default)], 501)
                for limit, expected in ((0, []), (501, [f"p{i:04d}" for i in range(501)])):
                    result = invoke(limit=limit)
                    self.assertTrue(result["ok"], result)
                    self.assert_ids(result["result"], expected, 501)

    def test_registered_schema_exposes_only_selected_query_fields_and_types(self):
        parameters = self.tools["spaces_query"]["schema"]["parameters"]
        properties = parameters["properties"]
        self.assertEqual(set(properties), {"space", "collection", "where", "order", "limit",
                                           "offset", "page", "cursor"}, "new page capability absent")
        for name, kind in (("order", "string"), ("offset", "integer"),
                           ("page", "boolean"), ("cursor", "object"), ("limit", "integer")):
            with self.subTest(field=name):
                self.assertEqual(properties[name]["type"], kind)
        self.assertEqual(set(parameters["required"]), {"space", "collection"})

    def test_tied_pages_match_and_cursors_continue_across_both_public_surfaces(self):
        sid, session = self.seed()
        options = {"where": {"status": "reading", "bucket": "keep"},
                   "order": "rank", "limit": 2, "page": True}
        cursor = None
        seen = []
        seq = None
        for expected, more, offset in ((["a", "b"], True, 2),
                                       (["c", "d"], True, 4), (["e"], False, 5)):
            with self.subTest(ids=expected):
                args = {**options, **({"cursor": cursor} if cursor is not None else {})}
                tool = self.page(self.tool_query(sid, **args))
                canvas = self.page(self.bridge_query(sid, session, **args))
                self.assertEqual(tool, canvas)
                self.assert_ids(tool, expected, 5)
                self.assertEqual(tool["has_more"], more)
                self.assertEqual(tool["seq"], seq if seq is not None else tool["seq"])
                seq = tool["seq"]
                seen.extend(row["id"] for row in tool["records"])
                cursor = canvas["next_cursor"]
                if more:
                    self.assertEqual(set(cursor), {"v", "space", "created_at", "seq", "offset", "query"})
                    self.assertEqual((cursor["v"], cursor["space"], cursor["seq"], cursor["offset"]),
                                     (1, sid, seq, offset))
                    with db.read() as conn:
                        incarnation = db.space(conn, sid)["created_at"]
                    self.assertEqual(cursor["created_at"], incarnation)
                    self.assertRegex(cursor["query"], r"^[0-9a-f]{64}$")
        self.assertEqual(seen, ["a", "b", "c", "d", "e"])
        self.assertEqual(len(set(seen)), 5)
        first = self.page(self.bridge_query(sid, session, **options))
        continued = self.page(self.tool_query(sid, **options, cursor=first["next_cursor"]))
        self.assert_ids(continued, ["c", "d"], 5)
        self.assertEqual(continued, self.page(self.tool_query(sid, **options, cursor=first["next_cursor"])))

    def test_order_and_offset_forward_in_legacy_and_page_modes(self):
        sid, session = self.seed()
        for page_mode in (False, True):
            with self.subTest(page=page_mode):
                options = {"order": "-rank", "offset": 1, "limit": 2, "page": page_mode}
                tool = self.tool_query(sid, **options)
                canvas = self.bridge_query(sid, session, **options)
                self.assertTrue(tool["ok"], tool)
                self.assertTrue(canvas["ok"], canvas)
                self.assertEqual(tool["result"], canvas["result"])
                self.assert_ids(tool["result"], ["d", "c"], 5)
                if page_mode:
                    result = self.page(tool)
                    self.assertTrue(result["has_more"])
                    self.assertEqual(result["next_cursor"]["offset"], 3)
                    last = self.page(self.bridge_query(sid, session, order="-rank", limit=2,
                                                       page=True, cursor=result["next_cursor"]))
                    self.assert_ids(last, ["b", "a"], 5)
                    self.assertFalse(last["has_more"])

    def test_null_missing_and_source_fallback_order_match_literal_ids(self):
        sid = self.create(name="Q14 Null Order")["space"]
        with patch.object(db, "now", return_value=3.0):
            self.ok("spaces_write_records", space=sid, source_owned=True, ops=[
                {"op": "put", "collection": "papers", "id": "a", "source": {"rank": 2}},
                {"op": "put", "collection": "papers", "id": "d", "source": {"rank": 99}},
            ])
        for rid, data, at in (("a", {"rank": None}, 30.0), ("b", {}, 20.0),
                              ("c", {"rank": None}, 10.0), ("d", {"rank": 0}, 40.0),
                              ("e", {"rank": "x"}, 1.0), ("f", {}, 10.0)):
            with patch.object(db, "now", return_value=at):
                self.ok("spaces_write_records", space=sid, ops=[
                    {"op": "put", "collection": "papers", "id": rid, "data": data,
                     "base_rev": 1 if rid in ("a", "d") else 0}])
        session = sessions.open_session(sid)["session"]
        for order, where, expected in (("rank", {}, ["d", "a", "c", "f", "b", "e"]),
                                        ("-rank", {}, ["e", "b", "f", "c", "a", "d"]),
                                        ("rank", {"rank": None}, ["c", "f", "b"])):
            with self.subTest(order=order, where=where):
                options = {"order": order, "where": where, "limit": 2, "page": True}
                seen = []
                for start in range(0, len(expected), 2):
                    tool = self.page(self.tool_query(sid, **options))
                    canvas = self.page(self.bridge_query(sid, session, **options))
                    self.assertEqual(tool, canvas)
                    self.assert_ids(tool, expected[start:start + 2], len(expected))
                    seen.extend(row["id"] for row in tool["records"])
                    self.assertEqual(tool["has_more"], start + 2 < len(expected))
                    options = {**options, "cursor": canvas["next_cursor"]}
                self.assertEqual(seen, expected)

    def test_effective_equality_filters_and_canonical_key_order_survive_continuation(self):
        sid = self.create(name="Q14 Filter")["space"]
        self.ok("spaces_write_records", space=sid, source_owned=True, ops=[
            {"op": "put", "collection": "papers", "id": rid,
             "source": {"status": "reading", "bucket": "keep", "title": rid.upper()}}
            for rid in ("c", "a", "b")])
        self.ok("spaces_write_records", space=sid, ops=[
            {"op": "put", "collection": "papers", "id": "a", "data": {"status": None}, "base_rev": 1},
            {"op": "put", "collection": "papers", "id": "b", "data": {"status": "done"}, "base_rev": 1},
            {"op": "put", "collection": "papers", "id": "d", "data": {"status": "reading", "bucket": "other"}},
            {"op": "put", "collection": "papers", "id": "e", "data": {}},
        ])
        session = sessions.open_session(sid)["session"]
        options = {"where": {"status": "reading", "bucket": "keep"},
                   "order": "title", "limit": 1, "page": True}
        first = self.page(self.tool_query(sid, **options))
        self.assert_ids(first, ["a"], 2)
        last = self.page(self.bridge_query(sid, session, **{**options,
            "where": {"bucket": "keep", "status": "reading"}, "cursor": first["next_cursor"]}))
        self.assert_ids(last, ["c"], 2)
        self.assertFalse(last["has_more"])

    def test_cursor_rejects_changed_limit_filter_order_collection_and_offset(self):
        sid, session = self.seed()
        options = {"where": {"status": "reading"}, "order": "rank", "limit": 2, "page": True}
        first = self.page(self.tool_query(sid, **options))
        cursor = first["next_cursor"]
        before = records.changes_since(sid, 0)
        for change in ({"limit": 3}, {"where": {"status": "done"}}, {"order": "-rank"},
                       {"offset": 1}, {"page": False}):
            with self.subTest(change=change):
                args = {**options, "cursor": cursor, **change}
                self.assert_error(self.tool_query(sid, **args), "invalid")
                self.assert_error(self.bridge_query(sid, session, **args), "invalid")
        args = {**options, "cursor": cursor, "collection": "other"}
        self.assert_error(self.call("spaces_query", space=sid, **args), "invalid")
        self.assert_error(bridge.dispatch(sid, session, "data.query", args), "invalid")
        self.assertEqual(records.changes_since(sid, 0), before)
        self.assert_ids(self.page(self.bridge_query(sid, session, **options, cursor=cursor)), ["c", "d"], 5)

    def test_registered_boolean_and_cursor_object_arguments_are_validated(self):
        sid, session = self.seed()
        options = {"order": "rank", "limit": 2, "page": True}
        first = self.page(self.tool_query(sid, **options))
        cursor = first["next_cursor"]
        continued = self.page(self.tool_query(sid, **options, cursor=json.dumps(cursor)))
        self.assert_ids(continued, ["c", "d"], 5)
        for change in ({"page": "true"}, {"page": 1}, {"page": 0},
                       {"cursor": []}, {"cursor": "[]"}, {"cursor": "not json"}):
            with self.subTest(change=change):
                self.assert_error(self.tool_query(sid, **{**options, **change}), "invalid")
        for limit in (0, -1, 501, True):
            with self.subTest(limit=limit):
                self.assert_error(self.tool_query(sid, page=True, limit=limit), "invalid")
                self.assert_error(self.bridge_query(sid, session, page=True, limit=limit), "invalid")
        self.assert_ids(self.page(self.tool_query(sid, order="rank", page=True, limit=1)), ["a"], 5)

    def test_page_defaults_differ_and_cross_surface_default_cursors_are_invalid(self):
        sid, session = self.seed(501)
        chat = self.page(self.tool_query(sid, page=True, order="rank"))
        canvas = self.page(self.bridge_query(sid, session, page=True, order="rank"))
        self.assert_ids(chat, [f"p{i:04d}" for i in range(100)], 501)
        self.assert_ids(canvas, [f"p{i:04d}" for i in range(500)], 501)
        self.assertEqual(chat["next_cursor"]["offset"], 100)
        self.assertEqual(canvas["next_cursor"]["offset"], 500)
        self.assert_error(self.bridge_query(sid, session, page=True, order="rank",
                                            cursor=chat["next_cursor"]), "invalid")
        self.assert_error(self.tool_query(sid, page=True, order="rank",
                                         cursor=canvas["next_cursor"]), "invalid")
        last = self.page(self.tool_query(sid, page=True, order="rank", limit=500,
                                         cursor=canvas["next_cursor"]))
        self.assert_ids(last, ["p0500"], 501)
        self.assertFalse(last["has_more"])

    def test_foreign_cursor_is_invalid_and_args_space_cannot_rebind_query(self):
        sid, session = self.seed()
        other = self.create(name="Q14 Foreign")["space"]
        self.ok("spaces_write_records", space=other, ops=[
            {"op": "put", "collection": "papers", "id": "foreign", "data": {"rank": 7}}])
        other_session = sessions.open_session(other)["session"]
        options = {"order": "rank", "limit": 2, "page": True}
        first = self.page(self.tool_query(sid, **options))
        bound = self.page(self.bridge_query(sid, session, space=other, **options))
        self.assertEqual(bound, first)
        self.assert_ids(bound, ["a", "b"], 5)
        self.assert_error(self.tool_query(other, **options, cursor=first["next_cursor"]), "invalid")
        self.assert_error(self.bridge_query(other, other_session, **options,
                                            cursor=first["next_cursor"]), "invalid")
        self.assert_error(self.bridge_query(other, session, **options), "session_invalid")

    def test_real_write_expires_both_public_continuations_without_records(self):
        sid, session = self.seed()
        options = {"order": "rank", "limit": 2, "page": True}
        first = self.page(self.tool_query(sid, **options))
        cursor = first["next_cursor"]
        self.assert_ids(self.page(self.bridge_query(sid, session, **options, cursor=cursor)), ["c", "d"], 5)
        self.ok("spaces_write_records", space=sid, ops=[
            {"op": "put", "collection": "papers", "id": "new", "data": {"rank": 7}}])
        for reply in (self.tool_query(sid, **options, cursor=cursor),
                      self.bridge_query(sid, session, **options, cursor=cursor)):
            error = self.assert_error(reply, "cursor_expired")
            self.assertIs(error["restart_required"], True)
            self.assertEqual(error["reason"], "changed")
        restart = self.page(self.tool_query(sid, **options))
        self.assert_ids(restart, ["a", "b"], 6)
        self.assertGreater(restart["seq"], first["seq"])

    def test_empty_and_exact_boundary_terminal_pages_do_not_need_an_empty_retry(self):
        sid, session = self.seed()
        empty = self.page(self.bridge_query(sid, session, where={"status": "absent"}, page=True, limit=2))
        self.assert_ids(empty, [], 0)
        self.assertFalse(empty["has_more"])
        self.assertIsNone(empty["next_cursor"])
        full = self.page(self.tool_query(sid, page=True, order="rank", limit=5))
        self.assert_ids(full, ["a", "b", "c", "d", "e"], 5)
        self.assertFalse(full["has_more"])
        self.assertIsNone(full["next_cursor"])


class Q14BridgeAuthorityTests(CoreCase):
    def query(self, session, **options):
        return bridge.dispatch(self.sid, session, "data.query", {"collection": "papers", **options})

    def assert_denied(self, reply, code):
        self.assertFalse(reply["ok"], reply)
        self.assertEqual(reply["error"]["code"], code)
        self.assertNotIn("result", reply)
        self.assertNotIn("records", reply["error"])

    def live_page(self, session):
        reply = self.query(session, page=True, order="rank", limit=1)
        self.assertTrue(reply["ok"], f"new page capability absent or rejected: {reply}")
        self.assertEqual(set(reply["result"]), PAGE_KEYS, "new page capability absent")
        self.assertEqual([row["id"] for row in reply["result"]["records"]], ["a"])
        return reply["result"]

    def test_legacy_query_obeys_bound_space_grants_and_closed_sessions(self):
        self.put("a", {"rank": 7})
        other = self.create("Other Q14")["id"]
        session = sessions.open_session(self.sid)["session"]
        reply = self.query(session, space=other)
        self.assertTrue(reply["ok"], reply)
        self.assertEqual(set(reply["result"]), {"records", "total", "seq"})
        self.assertEqual([row["id"] for row in reply["result"]["records"]], ["a"])
        grants.decide(self.sid, "data", "revoke")
        self.assert_denied(self.query(session), "not_granted")
        sessions.close_session(session)
        self.assert_denied(self.query(session), "session_invalid")

    def test_revoked_data_denies_page_and_cursor_delivery(self):
        self.put("b", {"rank": 7})
        self.put("a", {"rank": 7})
        session = sessions.open_session(self.sid)["session"]
        first = self.live_page(session)
        before = self.counts()
        grants.decide(self.sid, "data", "revoke")
        self.assert_denied(self.query(session, page=True, order="rank", limit=1,
                                      cursor=first["next_cursor"]), "not_granted")
        self.assertEqual(self.counts(), before)

    def test_closed_session_denies_page_and_cursor_delivery(self):
        self.put("b", {"rank": 7})
        self.put("a", {"rank": 7})
        session = sessions.open_session(self.sid)["session"]
        first = self.live_page(session)
        before = self.counts()
        sessions.close_session(session)
        self.assert_denied(self.query(session, page=True, order="rank", limit=1,
                                      cursor=first["next_cursor"]), "session_invalid")
        self.assertEqual(self.counts(), before)

    def assert_inflight_denial(self, invalidate, code):
        self.put("a", {"rank": 7})
        session = sessions.open_session(self.sid)["session"]
        self.live_page(session)
        before = self.counts()
        original = records.query
        observed = []

        # Synthetic scheduling seam, calling the canonical query once before invalidation.
        def finish_then_invalidate(*args, **kwargs):
            result = original(*args, **kwargs)
            observed.append(result)
            invalidate(session)
            return result

        with patch.object(bridge.records, "query", side_effect=finish_then_invalidate) as query:
            reply = self.query(session, page=True, order="rank", limit=1)
        self.assertEqual(query.call_count, 1)
        self.assertEqual(len(observed), 1)
        self.assertEqual(set(observed[0]), PAGE_KEYS)
        self.assertEqual([row["id"] for row in observed[0]["records"]], ["a"])
        self.assert_denied(reply, code)
        self.assertEqual(self.counts(), before)

    def test_completed_page_is_not_delivered_after_session_closes(self):
        self.assert_inflight_denial(sessions.close_session, "session_invalid")

    def test_completed_page_is_not_delivered_after_data_is_revoked(self):
        self.assert_inflight_denial(lambda session: grants.decide(self.sid, "data", "revoke"), "not_granted")
