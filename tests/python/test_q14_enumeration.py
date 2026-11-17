"""Core-only shapeA enumeration contracts; execution belongs to the parent."""
import inspect
from unittest.mock import patch

from tests.python.test_core_store import CoreCase
from living_spaces_core import db, limits, records


class Q14EnumerationTests(CoreCase):
    def seed(self, ids, *, collection="papers", data=None, sid=None):
        ids = list(ids)
        sid = self.sid if sid is None else sid
        data = {"rank": 7} if data is None else data
        for start in range(0, len(ids), limits.BATCH_OPS):
            ops = [{"op": "put", "collection": collection, "id": rid,
                    "data": data, "base_rev": 0}
                   for rid in ids[start:start + limits.BATCH_OPS]]
            result = records.batch(sid, ops, actor="user")
            self.assertEqual(len(result["results"]), len(ops))

    def page(self, collection="papers", *, sid=None, **options):
        if "page" not in inspect.signature(records.query).parameters:
            self.fail("new page capability absent")
        return records.query(self.sid if sid is None else sid, collection,
                             page=True, **options)

    def assert_page(self, result, ids, *, total, more, seq=None):
        self.assertEqual(set(result), {"records", "total", "seq", "has_more", "next_cursor"})
        self.assertEqual([item["id"] for item in result["records"]], ids)
        self.assertIs(type(result["total"]), int)
        self.assertEqual(result["total"], total)
        self.assertIs(type(result["seq"]), int)
        self.assertIs(result["has_more"], more)
        if seq is not None:
            self.assertEqual(result["seq"], seq)
        if more:
            cursor = result["next_cursor"]
            self.assertIsInstance(cursor, dict)
            self.assertEqual(set(cursor), {"v", "space", "created_at", "seq", "offset", "query"})
            self.assertIs(type(cursor["v"]), int)
            self.assertEqual(cursor["v"], 1)
            self.assertEqual(cursor["space"], self.sid)
            self.assertEqual(cursor["seq"], result["seq"])
            self.assertIs(type(cursor["offset"]), int)
            self.assertGreater(cursor["offset"], 0)
            self.assertRegex(cursor["query"], r"^[0-9a-f]{64}$")
            with db.read() as conn:
                self.assertEqual(cursor["created_at"], db.space(conn, self.sid)["created_at"])
        else:
            self.assertIsNone(result["next_cursor"])

    def walk(self, expected_pages, *, total, collection="papers", **options):
        cursor = None
        pages = []
        for index, ids in enumerate(expected_pages):
            continuation = {} if cursor is None else {"cursor": cursor}
            result = self.page(collection, **options, **continuation)
            self.assert_page(result, ids, total=total,
                             more=index < len(expected_pages) - 1,
                             seq=pages[0]["seq"] if pages else None)
            pages.append(result)
            cursor = result["next_cursor"]
        self.assertIsNone(cursor)
        return pages

    def state(self):
        with db.read() as conn:
            return tuple(conn.iterdump())

    def assert_expired(self, cursor, reason, *, collection="papers", **options):
        error = self.error("cursor_expired", self.page, collection, cursor=cursor, **options)
        self.assertIs(error["restart_required"], True)
        self.assertEqual(error["reason"], reason)
        self.assertNotIn("records", error)
        self.assertNotIn("next_cursor", error)
        self.assertNotIn("result", error)

    def null_rows(self):
        with patch.object(db, "now", return_value=5.0):
            records.upsert_source(self.sid, "papers", "a", {"rank": 2}, {}, actor="upkeep:manual")
            self.put("a", {"rank": None}, base_rev=1)
            records.upsert_source(self.sid, "papers", "d", {"rank": 99}, {}, actor="upkeep:manual")
            self.put("d", {"rank": 0}, base_rev=1)
        with patch.object(db, "now", return_value=20.0):
            self.put("b", {})
        with patch.object(db, "now", return_value=10.0):
            self.put("c", {"rank": None})
        with patch.object(db, "now", return_value=30.0):
            self.put("e", {"rank": "x"})

    def test_legacy_zero_limit_and_empty_shape(self):
        empty = records.query(self.sid, "papers")
        self.assertEqual(empty, {"records": [], "total": 0, "seq": 0})
        self.seed(["a", "b", "c"])
        seq = records.changes_since(self.sid, 0)["seq"]
        self.assertEqual(records.query(self.sid, "papers", limit=0),
                         {"records": [], "total": 3, "seq": seq})

    def test_legacy_default_500_and_limit_above_page_bound(self):
        ids = [f"p{index:04d}" for index in range(501)]
        self.seed(reversed(ids))
        default = records.query(self.sid, "papers", order="rank")
        self.assertEqual(set(default), {"records", "total", "seq"})
        self.assertEqual([item["id"] for item in default["records"]], ids[:500])
        self.assertEqual(default["total"], 501)
        all_rows = records.query(self.sid, "papers", order="rank", limit=501)
        self.assertEqual(set(all_rows), {"records", "total", "seq"})
        self.assertEqual([item["id"] for item in all_rows["records"]], ids)
        self.assertEqual((all_rows["total"], all_rows["seq"]), (501, default["seq"]))

    def test_legacy_ties_descending_and_offset(self):
        with patch.object(db, "now", return_value=40.0):
            self.seed(["c", "a", "b"], data={"rank": 4})
        ascending = records.query(self.sid, "papers", order="rank")
        self.assertEqual([item["id"] for item in ascending["records"]], ["a", "b", "c"])
        reverse = records.query(self.sid, "papers", order="-rank")
        self.assertEqual([item["id"] for item in reverse["records"]], ["c", "b", "a"])
        descending = records.query(self.sid, "papers", order="-rank", offset=1, limit=1)
        self.assertEqual(set(descending), {"records", "total", "seq"})
        self.assertEqual([item["id"] for item in descending["records"]], ["b"])
        self.assertEqual(descending["total"], 3)
        self.assertEqual([item["id"] for item in records.query(self.sid, "papers")["records"]],
                         ["a", "b", "c"])

    def test_legacy_null_source_fallback_and_equality(self):
        self.null_rows()
        result = records.query(self.sid, "papers", order="rank")
        self.assertEqual(set(result), {"records", "total", "seq"})
        self.assertEqual([item["id"] for item in result["records"]], ["d", "a", "c", "b", "e"])
        descending = records.query(self.sid, "papers", order="-rank")
        self.assertEqual([item["id"] for item in descending["records"]], ["e", "b", "c", "a", "d"])
        nulls = records.query(self.sid, "papers", where={"rank": None}, order="rank")
        self.assertEqual([item["id"] for item in nulls["records"]], ["c", "b"])
        self.assertEqual(nulls["total"], 2)

    def test_1005_records_complete_in_500_500_5(self):
        ids = [f"p{index:04d}" for index in range(1005)]
        self.seed(reversed(ids))
        pages = self.walk([ids[:500], ids[500:1000], ids[1000:]],
                          total=1005, order="rank", limit=500)
        self.assertEqual([len(page["records"]) for page in pages], [500, 500, 5])
        self.assertEqual([page["next_cursor"]["offset"] for page in pages[:2]], [500, 1000])
        actual = [item["id"] for page in pages for item in page["records"]]
        self.assertEqual(actual, ids)
        self.assertEqual(len(set(actual)), 1005)

    def test_exact_1000_boundary_terminates_on_second_page(self):
        ids = [f"p{index:04d}" for index in range(1000)]
        self.seed(reversed(ids))
        pages = self.walk([ids[:500], ids[500:]], total=1000, order="rank", limit=500)
        self.assertEqual([page["has_more"] for page in pages], [True, False])
        self.assertIsNone(pages[1]["next_cursor"])

    def test_empty_collection_and_offset_past_end_are_terminal(self):
        self.assert_page(self.page(limit=1), [], total=0, more=False, seq=0)
        self.seed(["a", "b", "c"])
        seq = records.changes_since(self.sid, 0)["seq"]
        self.assert_page(self.page("empty", limit=500), [], total=0, more=False, seq=seq)
        self.assert_page(self.page(order="rank", offset=3, limit=2), [], total=3, more=False, seq=seq)
        self.assert_page(self.page(order="rank", offset=99, limit=2), [], total=3, more=False, seq=seq)

    def test_page_ties_reverse_ids_and_default_timestamp_order(self):
        with patch.object(db, "now", return_value=40.0):
            self.seed(["c", "a", "b"], data={"rank": 4})
        for order, expected in (("rank", [["a"], ["b"], ["c"]]),
                                ("-rank", [["c"], ["b"], ["a"]]),
                                (None, [["a"], ["b"], ["c"]])):
            with self.subTest(order=order):
                self.walk(expected, total=3, order=order, limit=1)

    def test_page_null_missing_and_source_fallback_literal_order(self):
        self.null_rows()
        self.walk([["d", "a"], ["c", "b"], ["e"]], total=5, order="rank", limit=2)
        self.walk([["e", "b"], ["c", "a"], ["d"]], total=5, order="-rank", limit=2)
        self.walk([["c"], ["b"]], total=2, where={"rank": None}, order="rank", limit=1)

    def test_page_boolean_text_json_and_null_ties_keep_legacy_order(self):
        with patch.object(db, "now", return_value=10.0):
            for rid, data in (("h", {"rank": "x"}), ("g", {"rank": {"k": 1}}),
                              ("f", {"rank": [1]}), ("e", {"rank": ""}),
                              ("d", {"rank": 0}), ("c", {"rank": None}),
                              ("b", {}), ("a", {"rank": False})):
                self.put(rid, data)
        self.walk([["a", "d", "b"], ["c", "e", "f"], ["h", "g"]],
                  total=8, order="rank", limit=3)
        self.walk([["g", "h", "f"], ["e", "c", "b"], ["d", "a"]],
                  total=8, order="-rank", limit=3)
        self.walk([["b"], ["c"]], total=2, where={"rank": None}, order="rank", limit=1)
        self.walk([["a"], ["d"]], total=2, where={"rank": 0}, order="rank", limit=1)

    def test_equality_filters_source_overrides_and_canonical_key_order(self):
        entries = [(rid, {"status": "reading", "title": title, "kind": kind}, {})
                   for rid, title, kind in (("a", "Alpha", "paper"), ("b", "Beta", "paper"),
                                            ("c", "Gamma", "paper"), ("e", "Epsilon", "note"),
                                            ("f", "Zeta", "paper"))]
        records.upsert_sources(self.sid, "papers", entries, actor="upkeep:manual")
        self.put("b", {"status": "done"}, base_rev=1)
        self.put("c", {"status": None}, base_rev=1)
        self.put("d", {"title": "Delta", "kind": "paper"})
        self.put("f", {"title": "Before"}, base_rev=1)
        self.walk([["a", "f"], ["e", "c"]], total=4,
                  where={"status": "reading"}, order="title", limit=2)
        first = self.page(where={"status": "reading", "kind": "paper"}, order="title", limit=2)
        self.assert_page(first, ["a", "f"], total=3, more=True)
        last = self.page(where={"kind": "paper", "status": "reading"}, order="title", limit=2,
                         cursor=first["next_cursor"])
        self.assert_page(last, ["c"], total=3, more=False, seq=first["seq"])
        self.walk([["d"]], total=1, where={"status": None}, order="title", limit=2)

    def test_cursor_rejects_changed_options_and_conflicting_offset(self):
        self.seed(["a", "b", "c"])
        first = self.page(order="rank", limit=1)
        cursor = first["next_cursor"]
        before = self.state()
        for collection, options in (("other", {"order": "rank", "limit": 1}),
                                    ("papers", {"order": "-rank", "limit": 1}),
                                    ("papers", {"order": "rank", "limit": 2}),
                                    ("papers", {"order": "rank", "limit": 1, "where": {"rank": 8}}),
                                    ("papers", {"order": "rank", "limit": 1, "offset": 1})):
            with self.subTest(collection=collection, options=options):
                error = self.error("invalid", self.page, collection, cursor=cursor, **options)
                self.assertNotIn("records", error)
        for options in ({}, {"page": False}):
            with self.subTest(options=options):
                self.error("invalid", records.query, self.sid, "papers", order="rank", limit=1,
                           cursor=cursor, **options)
        self.assertEqual(self.state(), before)
        self.assert_page(self.page(order="rank", limit=1, offset=0, cursor=cursor),
                         ["b"], total=3, more=True, seq=first["seq"])

    def test_same_space_record_changes_expire_and_explicit_restart_sees_new_set(self):
        mutations = ("insert", "sort_update", "filter_update", "delete", "recreate",
                     "source_update", "other_collection")
        for index, mutation in enumerate(mutations):
            with self.subTest(mutation=mutation):
                collection = f"case_{index}"
                self.seed(["a", "b", "c"], collection=collection,
                          data={"rank": 7, "status": "reading"})
                options = {"where": {"status": "reading"}, "order": "rank", "limit": 1}
                first = self.page(collection, **options)
                self.assert_page(first, ["a"], total=3, more=True)
                expected = ["a", "b", "c"]
                if mutation == "insert":
                    self.seed(["d"], collection=collection, data={"rank": 7, "status": "reading"})
                    expected = ["a", "b", "c", "d"]
                elif mutation == "sort_update":
                    records.put(self.sid, collection, "c", {"rank": 0}, actor="user", base_rev=1)
                    expected = ["c", "a", "b"]
                elif mutation == "filter_update":
                    records.put(self.sid, collection, "c", {"status": "done"}, actor="user", base_rev=1)
                    expected = ["a", "b"]
                elif mutation == "delete":
                    records.delete(self.sid, collection, "b", actor="user", base_rev=1)
                    expected = ["a", "c"]
                elif mutation == "recreate":
                    records.delete(self.sid, collection, "b", actor="user", base_rev=1)
                    self.seed(["b"], collection=collection, data={"rank": 7, "status": "reading"})
                    self.assertGreater(records.get(self.sid, collection, "b")["rev"], 1)
                elif mutation == "source_update":
                    records.upsert_source(self.sid, collection, "c", {"rank": 9}, {}, actor="upkeep:manual")
                else:
                    self.seed([f"change{index}"], collection="unrelated")
                after_mutation = self.state()
                self.assert_expired(first["next_cursor"], "changed", collection=collection, **options)
                self.assertEqual(self.state(), after_mutation)
                restart = self.page(collection, where=options["where"], order="rank", limit=500)
                self.assert_page(restart, expected, total=len(expected), more=False)
                self.assertGreater(restart["seq"], first["seq"])

    def test_other_space_change_does_not_expire_continuation(self):
        self.seed(["a", "b", "c"])
        first = self.page(order="rank", limit=1)
        self.assert_page(first, ["a"], total=3, more=True)
        other = self.create("Other enumeration")["id"]
        self.seed(["foreign"], sid=other)
        self.assertGreater(records.changes_since(other, 0)["seq"], first["seq"])
        self.assert_page(self.page(order="rank", limit=1, cursor=first["next_cursor"]),
                         ["b"], total=3, more=True, seq=first["seq"])

    def test_noop_source_refresh_does_not_expire_or_update_record(self):
        entries = [(rid, {"rank": 7}, {"fetched_at": 1, "source_id": "fixture"})
                   for rid in ("c", "a", "b")]
        records.upsert_sources(self.sid, "papers", entries, actor="upkeep:manual")
        first = self.page(order="rank", limit=1)
        before = self.state()
        refreshed = [(rid, source, {**meta, "fetched_at": 2}) for rid, source, meta in entries]
        self.assertEqual(records.upsert_sources(self.sid, "papers", refreshed, actor="upkeep:manual"),
                         {"added": 0, "updated": 0, "unchanged": 3})
        self.assertEqual(self.state(), before)
        self.assert_page(self.page(order="rank", limit=1, cursor=first["next_cursor"]),
                         ["b"], total=3, more=True, seq=first["seq"])

    def test_valid_cursor_replay_is_identical_and_read_only(self):
        self.seed(["c", "a", "b"])
        before = self.state()
        first = self.page(order="rank", limit=1)
        self.assert_page(first, ["a"], total=3, more=True)
        next_options = {"order": "rank", "limit": 1, "cursor": first["next_cursor"]}
        second = self.page(**next_options)
        self.assert_page(second, ["b"], total=3, more=True, seq=first["seq"])
        self.assertEqual(self.page(**next_options), second)
        self.assertEqual(self.page(order="rank", limit=1), first)
        self.assertEqual(self.state(), before)

    def test_nonzero_initial_offset_enumerates_only_suffix(self):
        self.seed(["e", "d", "c", "b", "a"])
        first = self.page(order="rank", limit=2, offset=2)
        self.assert_page(first, ["c", "d"], total=5, more=True)
        self.assertEqual(first["next_cursor"]["offset"], 4)
        last = self.page(order="rank", limit=2, cursor=first["next_cursor"])
        self.assert_page(last, ["e"], total=5, more=False, seq=first["seq"])

    def test_page_limits_and_offsets_reject_invalid_values(self):
        self.seed(["a", "b"])
        self.assert_page(self.page(order="rank", limit=1), ["a"], total=2, more=True)
        before = self.state()
        for limit in (0, -1, 501, True, 1.5, None):
            with self.subTest(limit=limit):
                self.error("invalid", self.page, limit=limit)
        for offset in (-1, True, 1.5, "1", None):
            with self.subTest(offset=offset):
                self.error("invalid", self.page, limit=1, offset=offset)
        self.assertEqual(self.state(), before)

    def test_explicit_page_false_keeps_legacy_shape_and_limits(self):
        self.seed(["c", "a", "b"])
        self.assert_page(self.page(order="rank", limit=1), ["a"], total=3, more=True)
        for options in ({"limit": 0}, {"order": "-rank", "offset": 1, "limit": 501}):
            with self.subTest(options=options):
                legacy = records.query(self.sid, "papers", **options)
                self.assertEqual(set(legacy), {"records", "total", "seq"})
                self.assertEqual(records.query(self.sid, "papers", page=False, **options), legacy)

    def test_malformed_cursor_fields_are_invalid_and_read_only(self):
        self.seed(["a", "b", "c"])
        first = self.page(order="rank", limit=1)
        cursor = first["next_cursor"]
        malformed = [("container", value) for value in ([], "cursor", True, 0, {})]
        malformed += [(f"missing_{key}", {k: v for k, v in cursor.items() if k != key})
                      for key in cursor]
        malformed.append(("extra_key", {**cursor, "extra": 1}))
        for key, values in (("v", (True, 1.0, "1", None)),
                            ("seq", (True, -1, 1.5, "1", None)),
                            ("offset", (True, -1, 1.5, "1", None)),
                            ("created_at", (True, "time", None, float("nan"), float("inf"), -float("inf"))),
                            ("space", (None, True, "../foreign")),
                            ("query", (None, True, {}, "not-a-digest", "0" * 64))):
            malformed += [(key, {**cursor, key: value}) for value in values]
        before = self.state()
        for label, bad in malformed:
            with self.subTest(label=label, cursor=bad):
                error = self.error("invalid", self.page, order="rank", limit=1, cursor=bad)
                self.assertNotIn("records", error)
        self.assertEqual(self.state(), before)
        self.assert_page(self.page(order="rank", limit=1, cursor=cursor),
                         ["b"], total=3, more=True, seq=first["seq"])

    def test_foreign_space_cursor_is_invalid_in_both_directions(self):
        self.seed(["a", "b", "c"])
        other = self.create("Foreign enumeration")["id"]
        self.seed(["a", "b", "c"], sid=other)
        local = self.page(order="rank", limit=1)
        foreign = self.page(sid=other, order="rank", limit=1)
        self.assertEqual([item["id"] for item in foreign["records"]], ["a"])
        self.assertEqual(foreign["next_cursor"]["space"], other)
        before = self.state()
        self.error("invalid", self.page, order="rank", limit=1, cursor=foreign["next_cursor"])
        self.error("invalid", self.page, sid=other, order="rank", limit=1, cursor=local["next_cursor"])
        self.assertEqual(self.state(), before)
        self.assert_page(self.page(order="rank", limit=1, cursor=local["next_cursor"]),
                         ["b"], total=3, more=True, seq=local["seq"])

    def test_unsupported_version_and_synthetic_old_incarnation_expire(self):
        self.seed(["a", "b", "c"])
        first = self.page(order="rank", limit=1)
        cursor = first["next_cursor"]
        before = self.state()
        self.assert_expired({**cursor, "v": 2}, "version", order="rank", limit=1)
        # Synthetic prior incarnation; this does not exercise Space deletion.
        self.assert_expired({**cursor, "created_at": cursor["created_at"] - 1},
                            "recreated", order="rank", limit=1)
        self.assertEqual(self.state(), before)
        self.assert_page(self.page(order="rank", limit=1, cursor=cursor),
                         ["b"], total=3, more=True, seq=first["seq"])

    def test_snapshot_interleaving_keeps_precommit_page_then_expires(self):
        self.seed(["a", "b", "c"])
        seq = records.changes_since(self.sid, 0)["seq"]
        canonical_space = db.space
        injections = []

        def commit_after_snapshot(conn, sid, *, writable=False):
            row = canonical_space(conn, sid, writable=writable)
            if sid == self.sid and not writable and not injections:
                self.assertTrue(conn.in_transaction)
                self.assertEqual(conn.execute("PRAGMA journal_mode").fetchone()[0], "wal")
                self.assertEqual(conn.execute("PRAGMA busy_timeout").fetchone()[0], 5000)
                injections.append(sid)
                # The real put opens a separate connection; WAL permits this commit
                # while the SELECT above holds the reader snapshot. No threads wait.
                records.put(sid, "papers", "d", {"rank": 7}, actor="user", base_rev=0)
                self.assertEqual(conn.execute("SELECT count(*) FROM records WHERE space=?", (sid,)).fetchone()[0], 3)
            return row

        with patch.object(db, "space", side_effect=commit_after_snapshot):
            first = self.page(order="rank", limit=2)
        self.assertEqual(injections, [self.sid])
        self.assert_page(first, ["a", "b"], total=3, more=True, seq=seq)
        self.assertEqual(first["next_cursor"]["seq"], seq)
        self.assertEqual(records.query(self.sid, "papers")["total"], 4)
        self.assert_expired(first["next_cursor"], "changed", order="rank", limit=2)
        self.walk([["a", "b"], ["c", "d"]], total=4, order="rank", limit=2)

    def test_snapshot_hook_without_writer_keeps_continuation_valid(self):
        self.seed(["a", "b", "c"])
        before = self.state()
        canonical_space = db.space
        reads = []

        def observe_snapshot(conn, sid, *, writable=False):
            row = canonical_space(conn, sid, writable=writable)
            if sid == self.sid and not writable:
                self.assertTrue(conn.in_transaction)
                reads.append(sid)
            return row

        with patch.object(db, "space", side_effect=observe_snapshot):
            first = self.page(order="rank", limit=2)
        self.assertGreaterEqual(len(reads), 1)
        self.assert_page(first, ["a", "b"], total=3, more=True)
        self.assert_page(self.page(order="rank", limit=2, cursor=first["next_cursor"]),
                         ["c"], total=3, more=False, seq=first["seq"])
        self.assertEqual(self.state(), before)
