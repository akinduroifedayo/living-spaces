"""Offline PassiveAdapter regressions. Parent-owned execution; no renderer journey."""
import inspect
import sqlite3
from unittest.mock import patch

from tests.python.test_core_store import CoreCase
from living_spaces_core import db, grants, limits, records
from living_spaces_core import inspection


class _InspectionFixture:
    def snapshot(self, sid=None):
        conn = inspection._open_snapshot()
        self.addCleanup(conn.close)
        snap = inspection.Snapshot(conn, sid or self.sid, 1)
        self.assertEqual(snap.rev, 1)
        self.assertTrue(conn.in_transaction)
        self.assertEqual(conn.execute("PRAGMA query_only").fetchone()[0], 1)
        self.assertEqual(snap.sid, sid or self.sid)
        return snap

    def adapter_query(self, adapter, collection="papers", **options):
        reply = adapter.call("data.query", {"collection": collection, **options})
        self.assertIs(reply["ok"], True, reply)
        return reply["result"]

    def state(self):
        with db.read() as conn:
            state = {table: [tuple(row) for row in conn.execute(
                f"SELECT * FROM {table} WHERE space=? ORDER BY rowid", (self.sid,))]
                for table in ("records", "changes", "revisions", "grants", "audit", "runs",
                              "sessions", "logs", "recovery_points")}
            state["space"] = tuple(db.space(conn, self.sid))
            return state

    def seed_mixed(self):
        with patch.object(db, "now", return_value=10.0):
            records.upsert_source(self.sid, "papers", "a", {"rank": 2, "status": "reading", "group": "x"}, {}, actor="user")
            self.put("a", {"rank": None, "status": None}, base_rev=1)
            self.put("c", {"rank": None})
            self.put("f", {})
            records.upsert_source(self.sid, "papers", "h", {"rank": 2, "status": "reading", "group": "x"}, {}, actor="user")
            self.put("h", {"status": None}, base_rev=1)
            records.upsert_source(self.sid, "papers", "i", {"rank": 2, "status": "reading", "group": "y"}, {}, actor="user")
        with patch.object(db, "now", return_value=20.0):
            self.put("b", {})
        with patch.object(db, "now", return_value=15.0):
            self.put("d", {"rank": 0})
        with patch.object(db, "now", return_value=30.0):
            self.put("e", {"rank": "x"})
            self.put("bool", {"rank": False})
            self.put("empty", {"rank": ""})
            self.put("list", {"rank": []})
            self.put("obj", {"rank": {}})
            records.upsert_source(self.sid, "papers", "g", {"rank": 4, "status": "reading", "group": "x"}, {}, actor="user")
            self.put("g", {"status": "done"}, base_rev=1)

    def require_page(self):
        parameters = inspect.signature(records.query).parameters
        if "page" not in parameters or "cursor" not in parameters:
            self.fail("new page capability absent")

    def assert_page(self, adapter, result, ids, total, more, next_offset=None):
        self.assertEqual(set(result), {"records", "total", "seq", "has_more", "next_cursor"})
        self.assertEqual([row["id"] for row in result["records"]], ids)
        self.assertEqual(result["total"], total)
        self.assertEqual(result["seq"], adapter.snap.seq)
        self.assertIs(result["has_more"], more)
        if more:
            cursor = result["next_cursor"]
            self.assertIsInstance(cursor, dict)
            self.assertEqual(set(cursor), {"v", "space", "created_at", "seq", "offset", "query"})
            self.assertEqual(cursor["v"], 1)
            self.assertEqual(cursor["space"], adapter.snap.sid)
            self.assertEqual(cursor["created_at"], db.space(adapter.snap.conn, adapter.snap.sid)["created_at"])
            self.assertEqual(cursor["seq"], adapter.snap.seq)
            self.assertEqual(cursor["offset"], next_offset)
            for key in ("v", "seq", "offset"):
                self.assertIs(type(cursor[key]), int)
            self.assertRegex(cursor["query"], r"^[0-9a-f]{64}$")
        else:
            self.assertIsNone(result["next_cursor"])

    def parity(self, adapter, collection="papers", **options):
        core = records.query(adapter.snap.sid, collection, page=True, **options)
        passive = self.adapter_query(adapter, collection, page=True, **options)
        self.assertEqual(passive, core)
        return passive

    def refusal(self, adapter, args, code, reason=None):
        reply = adapter.call("data.query", args)
        self.assertIs(reply["ok"], False, reply)
        self.assertNotIn("result", reply)
        self.assertNotIn("records", reply)
        error = reply["error"]
        self.assertEqual(error["code"], code)
        self.assertNotIn("records", error)
        self.assertNotIn("next_cursor", error)
        if reason is not None:
            self.assertIs(error["restart_required"], True)
            self.assertEqual(error["reason"], reason)
        return error

    def exercise_deadline(self, page):
        for rid in ("a", "b", "c"):
            self.put(rid, {"rank": 1})
        snap = self.snapshot()
        options = {"page": True} if page else {}
        adapter = inspection.PassiveAdapter(snap, deadline=10.0)
        before = self.state()
        # Synthetic clock only: canonical decoding still runs for every visited row.
        decoded = []
        original = records._record

        def decode(row):
            decoded.append(row["id"])
            return original(row)

        def clock():
            return 10.0 if len(decoded) >= 2 else 0.0

        with patch.object(inspection.time, "monotonic", return_value=0.0):
            valid = self.adapter_query(adapter, order="rank", limit=1, **options)
        self.assertEqual([row["id"] for row in valid["records"]], ["a"])
        self.assertEqual(valid["total"], 3)
        self.assertEqual(valid, records.query(self.sid, "papers", order="rank", limit=1, **options))
        if page:
            self.assert_page(adapter, valid, ["a"], 3, True, 1)
        else:
            self.assertEqual(set(valid), {"records", "total", "seq"})
        with patch.object(records, "_record", side_effect=decode), \
                patch.object(inspection.time, "monotonic", side_effect=clock):
            with self.assertRaises(inspection._Timeout):
                adapter.call("data.query", {"collection": "papers", "order": "rank", "limit": 1, **options})
        self.assertEqual(decoded, ["a", "b"])
        with patch.object(inspection.time, "monotonic", return_value=0.0):
            self.assertEqual(self.adapter_query(adapter, order="rank", limit=1, **options), valid)
        self.assertEqual(self.state(), before)

    def exercise_collection_cap(self, page):
        # Cross the actual default cap with legal canonical writes, without patching any limit.
        self.assertEqual(inspection.MAX_QUERY_BYTES, 32 * 1024 * 1024)
        payload = {"text": "é" * ((limits.DATA_BYTES - 32) // 2)}
        row_bytes = len(limits.dumps(payload).encode("utf-8"))
        self.assertLess(row_bytes, limits.DATA_BYTES)
        count = inspection.MAX_QUERY_BYTES // row_bytes
        self.assertGreater(count, 1)
        self.assertLessEqual(count, limits.BATCH_OPS)
        ids = [f"b{index:03d}" for index in range(count)]
        result = records.batch(self.sid, [
            {"op": "put", "collection": "bulk", "id": rid, "data": payload} for rid in ids
        ], actor="user")
        self.assertEqual([row["id"] for row in result["results"]], ids)
        options = {"page": True} if page else {}
        held = inspection.PassiveAdapter(self.snapshot())
        valid = self.adapter_query(held, "bulk", order="text", limit=1, **options)
        self.assertEqual([row["id"] for row in valid["records"]], ["b000"])
        self.assertEqual(valid["total"], count)
        self.assertEqual(valid, records.query(self.sid, "bulk", order="text", limit=1, **options))
        if page:
            self.assert_page(held, valid, ["b000"], count, True, 1)
        else:
            self.assertEqual(set(valid), {"records", "total", "seq"})
        records.put(self.sid, "bulk", "overflow", payload, actor="user")
        current = inspection.PassiveAdapter(self.snapshot())
        stored_bytes = current.snap.conn.execute(
            "SELECT sum(length(CAST(data AS BLOB)) + length(CAST(coalesce(source,'') AS BLOB)) "
            "+ length(CAST(coalesce(source_meta,'') AS BLOB))) FROM records "
            "WHERE space=? AND collection='bulk'", (self.sid,)).fetchone()[0]
        self.assertGreater(stored_bytes, inspection.MAX_QUERY_BYTES)
        before = self.state()
        for where in (None, {"text": "does not match"}):
            with self.subTest(where=where):
                self.refusal(current, {"collection": "bulk", "where": where, "limit": 1, **options}, "limit")
        self.assertEqual(current.limited, {"collection_too_large": 2})
        get = current.call("data.get", {"collection": "bulk", "id": "b000"})
        self.assertIs(get["ok"], True, get)
        self.assertEqual(get["result"]["data"], payload)
        self.assertEqual(self.adapter_query(held, "bulk", order="text", limit=1, **options), valid)
        self.assertEqual(self.state(), before)


class Q14InspectionLegacyTests(_InspectionFixture, CoreCase):
    def test_legacy_order_filter_offset_and_limits(self):
        self.seed_mixed()
        adapter = inspection.PassiveAdapter(self.snapshot())
        before = self.state()
        cases = [
            ({"order": "rank"}, ["bool", "d", "a", "h", "i", "g", "c", "f", "b", "empty", "list", "e", "obj"], 13),
            ({"order": "-rank", "limit": 3, "offset": 1}, ["e", "list", "empty"], 13),
            ({"where": {"status": "reading"}, "order": "rank", "limit": 2, "offset": 1}, ["h", "i"], 3),
            ({"where": {"rank": None}, "order": "rank"}, ["c", "f", "b"], 3),
            ({"limit": 0}, [], 13),
            ({"order": "rank", "limit": 501}, ["bool", "d", "a", "h", "i", "g", "c", "f", "b", "empty", "list", "e", "obj"], 13),
        ]
        for options, ids, total in cases:
            with self.subTest(options=options):
                result = self.adapter_query(adapter, **options)
                self.assertEqual(result, records.query(self.sid, "papers", **options))
                self.assertEqual(set(result), {"records", "total", "seq"})
                self.assertEqual([row["id"] for row in result["records"]], ids)
                self.assertEqual((result["total"], result["seq"]), (total, adapter.snap.seq))
        self.assertEqual(self.state(), before)

    def test_read_only_mutation_network_bot_and_refresh_refusals(self):
        guard = self.put("guard", {"rank": 1})
        adapter = inspection.PassiveAdapter(self.snapshot())
        before = self.state()
        self.assertEqual(self.adapter_query(adapter)["records"], [guard])
        with self.assertRaises(sqlite3.OperationalError):
            adapter.snap.conn.execute("UPDATE records SET data='{}' WHERE space=?", (self.sid,))
        cases = [
            ("data.put", {"collection": "papers", "id": "new", "data": {"rank": 2}}),
            ("data.delete", {"collection": "papers", "id": "guard", "base_rev": guard["rev"]}),
            ("data.batch", {"ops": [{"op": "put", "collection": "papers", "id": "new", "data": {}}]}),
            ("net.fetch", {"url": "https://example.invalid/"}),
            ("bot.request", {"activation_id": "q14-test", "text": "test"}),
            ("refresh", {}),
        ]
        for op, args in cases:
            with self.subTest(op=op):
                reply = adapter.call(op, args)
                self.assertIs(reply["ok"], False, reply)
                self.assertNotIn("result", reply)
                self.assertEqual(reply["error"]["code"], "blocked")
                self.assertIs(reply["error"]["inspection"], True)
                self.assertEqual(self.state(), before)
        self.assertEqual(adapter.refused, {op: 1 for op, _ in cases})
        self.assertEqual(self.adapter_query(adapter)["records"], [guard])
        self.assertEqual(self.state(), before)

    def test_ungranted_data_is_denied_without_writes(self):
        guard = self.put("guard", {"rank": 1})
        allowed = inspection.PassiveAdapter(self.snapshot())
        self.assertEqual(self.adapter_query(allowed)["records"], [guard])
        grants.decide(self.sid, "data", "revoke")
        denied = inspection.PassiveAdapter(self.snapshot())
        before = self.state()
        self.refusal(denied, {"collection": "papers"}, "not_granted")
        self.assertEqual(denied.denied, {"data.query": 1})
        self.assertIs(denied.call("meta", {})["ok"], True)
        self.assertEqual(self.state(), before)

    def test_legacy_deadline_interrupts_record_scan(self):
        self.exercise_deadline(page=False)

    def test_legacy_actual_collection_byte_cap(self):
        self.exercise_collection_cap(page=False)


class Q14InspectionPageTests(_InspectionFixture, CoreCase):
    def test_ordered_filtered_null_and_source_parity(self):
        self.seed_mixed()
        adapter = inspection.PassiveAdapter(self.snapshot())
        self.require_page()
        before = self.state()
        cases = [
            ({"order": "rank"}, ["bool", "d", "a", "h", "i", "g", "c", "f", "b", "empty", "list", "e", "obj"], 13),
            ({"order": "-rank"}, ["obj", "e", "list", "empty", "b", "f", "c", "g", "i", "h", "a", "d", "bool"], 13),
            ({"where": {"rank": None}, "order": "rank"}, ["c", "f", "b"], 3),
            ({"where": {"status": "reading"}, "order": "rank"}, ["a", "h", "i"], 3),
        ]
        for options, ids, total in cases:
            with self.subTest(options=options):
                result = self.parity(adapter, limit=500, **options)
                self.assert_page(adapter, result, ids, total, False)
        first = self.parity(adapter, where={"status": "reading", "group": "x"}, order="rank", limit=1)
        self.assert_page(adapter, first, ["a"], 2, True, 1)
        second = self.parity(adapter, where={"group": "x", "status": "reading"}, order="rank", limit=1,
                             cursor=first["next_cursor"])
        self.assert_page(adapter, second, ["h"], 2, False)
        legacy = self.adapter_query(adapter, order="rank", limit=1, page=False)
        self.assertEqual(legacy, records.query(self.sid, "papers", order="rank", limit=1, page=False))
        self.assertEqual(set(legacy), {"records", "total", "seq"})
        self.assertEqual([row["id"] for row in legacy["records"]], ["bool"])
        self.assertEqual(self.state(), before)

    def test_ties_descending_and_default_order(self):
        with patch.object(db, "now", return_value=50.0):
            for rid in ("c", "a", "b"):
                self.put(rid, {"rank": 4})
        adapter = inspection.PassiveAdapter(self.snapshot())
        self.require_page()
        for order, ids in (("rank", ["a", "b", "c"]), ("-rank", ["c", "b", "a"]), (None, ["a", "b", "c"])):
            with self.subTest(order=order):
                cursor = None
                for index, rid in enumerate(ids):
                    result = self.parity(adapter, order=order, limit=1, cursor=cursor)
                    self.assert_page(adapter, result, [rid], 3, index < 2, index + 1)
                    self.assertEqual(self.parity(adapter, order=order, limit=1, cursor=cursor), result)
                    cursor = result["next_cursor"]
                self.assertIsNone(cursor)

    def test_multi_page_completion_exact_boundary_empty_and_suffix(self):
        self.require_page()
        ids = [f"p{index:04d}" for index in range(1005)]
        with patch.object(db, "now", return_value=50.0):
            for start in range(0, len(ids), limits.BATCH_OPS):
                result = records.batch(self.sid, [
                    {"op": "put", "collection": "papers", "id": ids[index],
                     "data": {"rank": 7, "eligible": index < 1000}}
                    for index in range(start, min(start + limits.BATCH_OPS, len(ids)))
                ], actor="user")
                self.assertEqual([row["id"] for row in result["results"]], ids[start:start + limits.BATCH_OPS])
        adapter = inspection.PassiveAdapter(self.snapshot())
        before = self.state()
        cursor, seen = None, []
        for index, expected in enumerate((ids[:500], ids[500:1000], ids[1000:])):
            result = self.parity(adapter, order="rank", limit=500, cursor=cursor)
            self.assert_page(adapter, result, expected, 1005, index < 2, (index + 1) * 500)
            seen.extend(row["id"] for row in result["records"])
            cursor = result["next_cursor"]
        self.assertEqual(seen, ids)
        self.assertEqual(len(set(seen)), 1005)
        self.assertIsNone(cursor)
        first = self.parity(adapter, where={"eligible": True}, order="rank", limit=500)
        self.assert_page(adapter, first, ids[:500], 1000, True, 500)
        last = self.parity(adapter, where={"eligible": True}, order="rank", limit=500, cursor=first["next_cursor"])
        self.assert_page(adapter, last, ids[500:1000], 1000, False)
        self.assert_page(adapter, self.parity(adapter, "empty", limit=1), [], 0, False)
        suffix = self.parity(adapter, order="rank", limit=500, offset=1000)
        self.assert_page(adapter, suffix, ids[1000:], 1005, False)
        self.assertEqual(self.state(), before)

    def test_malformed_foreign_and_oversized_cursors(self):
        for rid in ("a", "b"):
            self.put(rid, {"rank": 1})
        foreign = self.create("Other")["id"]
        adapter = inspection.PassiveAdapter(self.snapshot())
        self.require_page()
        options = {"collection": "papers", "order": "rank", "limit": 1, "page": True}
        first = self.parity(adapter, order="rank", limit=1)
        self.assert_page(adapter, first, ["a"], 2, True, 1)
        cursor = first["next_cursor"]
        malformed = [[], "opaque", {}, {key: value for key, value in cursor.items() if key != "query"}]
        malformed.extend({**cursor, **change} for change in (
            {"extra": True}, {"space": foreign}, {"v": True}, {"v": "1"}, {"seq": True},
            {"seq": -1}, {"seq": "1"}, {"offset": -1}, {"offset": True}, {"offset": 1.5},
            {"created_at": "bad"}, {"query": []}, {"query": "0" * 64},
        ))
        before = self.state()
        for bad in malformed:
            with self.subTest(cursor=bad):
                args = {**options, "cursor": bad}
                self.refusal(adapter, args, "invalid")
                self.error("invalid", records.query, self.sid, **args)
        self.refusal(adapter, {**options, "cursor": {**cursor, "query": "x" * limits.BRIDGE_BYTES}}, "limit")
        self.assert_page(adapter, self.parity(adapter, order="rank", limit=1, cursor=cursor), ["b"], 2, False)
        self.assertEqual(self.state(), before)

    def test_cursor_options_and_page_argument_validation(self):
        for rid in ("a", "b"):
            self.put(rid, {"rank": 1})
        adapter = inspection.PassiveAdapter(self.snapshot())
        self.require_page()
        first = self.parity(adapter, order="rank", limit=1)
        cursor = first["next_cursor"]
        base = {"collection": "papers", "order": "rank", "limit": 1, "page": True, "cursor": cursor}
        invalid = [{**base, **change} for change in (
            {"where": {"rank": 2}}, {"order": "-rank"}, {"limit": 2}, {"collection": "other"},
            {"offset": 1}, {"page": False}, {"page": "true"},
        )]
        invalid.append({key: value for key, value in base.items() if key != "page"})
        invalid.extend({"collection": "papers", "page": True, "limit": value} for value in (0, -1, 501, True))
        invalid.append({"collection": "papers", "page": True, "offset": -1})
        before = self.state()
        for args in invalid:
            with self.subTest(args=args):
                self.refusal(adapter, args, "invalid")
                self.error("invalid", records.query, self.sid, **args)
        self.assert_page(adapter, self.parity(adapter, order="rank", limit=1, cursor=cursor), ["b"], 2, False)
        self.assertEqual(self.state(), before)

    def test_version_and_synthetic_incarnation_expiry(self):
        for rid in ("a", "b"):
            self.put(rid, {"rank": 1})
        adapter = inspection.PassiveAdapter(self.snapshot())
        self.require_page()
        first = self.parity(adapter, order="rank", limit=1)
        cursor = first["next_cursor"]
        before = self.state()
        # Synthetic old-incarnation hint, not a Space deletion/recreation journey.
        for change, reason in (({"v": 2}, "version"), ({"created_at": cursor["created_at"] + 1.0}, "recreated")):
            with self.subTest(reason=reason):
                args = {"collection": "papers", "order": "rank", "limit": 1, "page": True, "cursor": {**cursor, **change}}
                self.refusal(adapter, args, "cursor_expired", reason)
                error = self.error("cursor_expired", records.query, self.sid, **args)
                self.assertIs(error["restart_required"], True)
                self.assertEqual(error["reason"], reason)
                self.assertNotIn("records", error)
                self.assertNotIn("next_cursor", error)
        self.assert_page(adapter, self.parity(adapter, order="rank", limit=1, cursor=cursor), ["b"], 2, False)
        self.assertEqual(self.state(), before)

    def test_held_snapshot_stays_stable_and_new_generation_expires(self):
        self.require_page()
        for mutation, expected in (
            ("insert", ["a", "aa", "b", "c"]), ("update", ["b", "c", "a"]),
            ("delete", ["a", "c"]), ("recreate", ["b", "a", "c"]),
            ("source", ["a", "b", "c"]), ("other_collection", ["a", "b", "c"]),
        ):
            with self.subTest(mutation=mutation):
                collection = "case_" + mutation
                for rid in ("a", "b", "c"):
                    records.put(self.sid, collection, rid, {"rank": 1}, actor="user")
                held = inspection.PassiveAdapter(self.snapshot())
                first = self.parity(held, collection, order="rank", limit=1)
                self.assert_page(held, first, ["a"], 3, True, 1)
                cursor = first["next_cursor"]
                second = self.parity(held, collection, order="rank", limit=1, cursor=cursor)
                self.assert_page(held, second, ["b"], 3, True, 2)
                if mutation == "insert":
                    records.put(self.sid, collection, "aa", {"rank": 1}, actor="user")
                elif mutation == "update":
                    records.put(self.sid, collection, "a", {"rank": 9}, actor="user", base_rev=1)
                elif mutation in ("delete", "recreate"):
                    records.delete(self.sid, collection, "b", actor="user", base_rev=1)
                    if mutation == "recreate":
                        records.put(self.sid, collection, "b", {"rank": 0}, actor="user")
                elif mutation == "source":
                    records.upsert_source(self.sid, collection, "b", {"rank": 0}, {}, actor="user")
                else:
                    records.put(self.sid, "elsewhere", "separate", {}, actor="user")
                before = self.state()
                held_second = self.adapter_query(held, collection, order="rank", limit=1, page=True, cursor=cursor)
                self.assertEqual(held_second, second)
                held_last = self.adapter_query(held, collection, order="rank", limit=1, page=True,
                                               cursor=held_second["next_cursor"])
                self.assert_page(held, held_last, ["c"], 3, False)
                self.assertEqual([row["id"] for row in self.adapter_query(held, collection, order="rank")["records"]], ["a", "b", "c"])
                fresh = inspection.PassiveAdapter(self.snapshot())
                self.assertGreater(fresh.snap.seq, held.snap.seq)
                args = {"collection": collection, "order": "rank", "limit": 1, "page": True, "cursor": cursor}
                self.refusal(fresh, args, "cursor_expired", "changed")
                error = self.error("cursor_expired", records.query, self.sid, **args)
                self.assertIs(error["restart_required"], True)
                self.assertEqual(error["reason"], "changed")
                self.assertNotIn("records", error)
                self.assertNotIn("next_cursor", error)
                restarted = self.parity(fresh, collection, order="rank", limit=500)
                self.assert_page(fresh, restarted, expected, len(expected), False)
                self.assertEqual(self.state(), before)

    def test_other_space_and_unchanged_source_preserve_continuation(self):
        self.require_page()
        for rid in ("a", "b", "c"):
            records.upsert_source(self.sid, "papers", rid, {"rank": 1}, {"fetched_at": 1}, actor="user")
        other = self.create("Other")["id"]
        held = inspection.PassiveAdapter(self.snapshot())
        first = self.parity(held, order="rank", limit=1)
        self.assert_page(held, first, ["a"], 3, True, 1)
        records.put(other, "papers", "foreign", {"rank": 0}, actor="user")
        self.assertEqual(records.upsert_source(self.sid, "papers", "a", {"rank": 1}, {"fetched_at": 2}, actor="user"), "unchanged")
        fresh = inspection.PassiveAdapter(self.snapshot())
        self.assertEqual(fresh.snap.seq, held.snap.seq)
        before = self.state()
        args = {"order": "rank", "limit": 1, "cursor": first["next_cursor"]}
        second = self.parity(fresh, **args)
        self.assert_page(fresh, second, ["b"], 3, True, 2)
        self.assertEqual(self.adapter_query(held, page=True, **args), second)
        last = self.parity(fresh, order="rank", limit=1, cursor=second["next_cursor"])
        self.assert_page(fresh, last, ["c"], 3, False)
        self.assertEqual(self.state(), before)

    def test_page_deadline_interrupts_record_scan(self):
        self.require_page()
        self.exercise_deadline(page=True)

    def test_page_actual_collection_byte_cap(self):
        self.require_page()
        self.exercise_collection_cap(page=True)
