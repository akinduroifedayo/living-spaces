"""F1-F4 contracts against the real core with synthetic cron and feed transport."""
from contextlib import ExitStack
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from tests.python.review_customization_support import CustomizationFixture
from tests.python.test_agent_refresh_dispatch import PausedRefusingContext, RunOutcome


ROOT = Path(__file__).resolve().parents[2]


class CompletingCronContext(PausedRefusingContext):
    def finish_background(self, jid):
        running = [entry for entry in self.cron.executions
                   if entry["job_id"] == jid and entry["status"] == "running"]
        assert len(running) == 1, running
        job = self.cron.get_job(jid)
        assert job is not None, {"job_id": jid, "executions": running}
        sid = job["name"].split(":")[1]
        marker = {"space": sid, "job_id": jid,
                  "execution_count": 1 + sum(effect["space"] == sid for effect in self.effects)}
        written = self.fx.projects.write_files(
            sid, files={"refresh-effect.json": json.dumps(marker)},
            author="agent:refresh-double", summary="Synthetic background refresh effect")
        observed = json.loads(self.fx.core.read_file(sid, "refresh-effect.json")["text"])
        self.effects.append({**observed, "rev": written["rev"], "origin": "background"})
        stamp = datetime.now(timezone.utc).isoformat()
        running[0].update(status="completed", finished_at=stamp)
        # A manual extra fire stamps its outcome without spending the once slot or resuming a paused job.
        self.cron.jobs[jid].update(last_status="ok", last_run_at=stamp, last_error=None)


class F1F4Regressions(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        temp_root = Path(os.environ.get("F1_F4_TEST_TMPDIR", ROOT / ".run"))
        temp_root.mkdir(parents=True, exist_ok=True)
        self.stack.enter_context(patch.object(tempfile, "tempdir", str(temp_root.resolve())))
        self.fx = CustomizationFixture(self.stack)
        self.ctx = CompletingCronContext(self.fx)
        self.fx.ctx = self.ctx
        self.fx.upkeep.configure_context(self.ctx)

    def observe(self, **values):
        record = {"case": self.id(), **values}
        message = json.dumps(record, sort_keys=True)
        print(message, flush=True)
        return message

    def refresh(self, sid, *, trigger="manual", actor="user"):
        try:
            return {"result": self.fx.runs.start_refresh(sid, trigger=trigger, actor=actor)}
        except self.fx.core.SpacesError as exc:
            return {"error": exc.to_dict()}

    def test_f1_successful_run_then_list_refusal_is_a_post_run_failure(self):
        fx = self.fx
        sid = fx.make()
        jid = fx.schedule(sid)["link"]["cron_job_id"]
        original = self.ctx.dispatch_tool
        refused = []

        def dispatch(name, args):
            if args["action"] == "list" and self.ctx.run_replies and not refused:
                refused.append({"success": False, "error": "Injected post-run list refusal"})
                return json.dumps(refused[-1])
            return original(name, args)

        with patch.object(self.ctx, "dispatch_tool", side_effect=dispatch):
            outcome = self.refresh(sid)
        marker = json.loads(fx.core.read_file(sid, "refresh-effect.json")["text"])
        message = self.observe(outcome=outcome, list_refusals=refused,
                               run_replies=self.ctx.run_replies, marker=marker,
                               executions=fx.cron.executions)
        self.assertEqual(len(refused), 1, message)
        self.assertEqual(len(fx.cron.executions), 1, message)
        self.assertEqual(fx.cron.executions[0]["status"], "completed", message)
        self.assertEqual(marker, {"space": sid, "job_id": jid, "execution_count": 1}, message)
        error = outcome.get("error", {})
        self.assertEqual(error.get("native"), self.ctx.run_replies[0], message)
        self.assertIs(error.get("native", {}).get("job", {}).get("execution_success"), True, message)
        self.assertEqual(error.get("verification", {}).get("native"), refused[0], message)
        self.assertEqual(error.get("verification", {}).get("reason"), "native_refused", message)
        self.assertEqual((error.get("code"), error.get("reason")),
                         ("blocked", "post_run_check_failed"), message)

    def test_f1_genuine_run_refusal_remains_native_refused_without_effects(self):
        fx = self.fx
        sid = fx.make()
        fx.schedule(sid)
        original = self.ctx.dispatch_tool
        refusals = []

        def dispatch(name, args):
            if args["action"] == "run":
                refusals.append({"success": False, "error": "Injected genuine run refusal"})
                return json.dumps(refusals[-1])
            return original(name, args)

        before = fx.projects.bundle(sid)
        with patch.object(self.ctx, "dispatch_tool", side_effect=dispatch):
            outcome = self.refresh(sid)
        after = fx.projects.bundle(sid)
        message = self.observe(outcome=outcome, refusals=refusals, executions=fx.cron.executions,
                               effects=self.ctx.effects, before=before, after=after)
        self.assertEqual(len(refusals), 1, message)
        error = outcome.get("error", {})
        self.assertEqual((error.get("code"), error.get("reason")), ("blocked", "native_refused"), message)
        self.assertEqual(error.get("native"), refusals[0], message)
        self.assertNotIn("verification", error, message)
        self.assertEqual((fx.cron.executions, self.ctx.effects), ([], []), message)
        self.assertEqual(after, before, message)

    def blob_snapshot(self):
        with self.fx.db.read() as conn:
            return {row["sha"]: bytes(row["content"]).hex()
                    for row in conn.execute("SELECT sha,content FROM blobs ORDER BY sha")}

    def deletion_fixture(self):
        fx = self.fx
        shared = "<!doctype html><title>Shared historical content</title>"
        victim = fx.projects.create_space(
            "Delete blob owner", owner="Review", author="user",
            files={"index.html": "<h1>Unique first revision</h1>", "shared.html": shared,
                   "retired.html": "<p>Unique retired file</p>"})["id"]
        survivor = fx.projects.create_space(
            "Keep blob owner", owner="Review", author="user", files={"index.html": shared})["id"]
        fx.projects.write_files(victim, files={"index.html": "<h1>Unique latest revision</h1>",
                                              "retired.html": None}, author="user", summary="Edit victim")
        fx.projects.write_files(survivor, files={"index.html": "<h1>Survivor current content</h1>"},
                                author="user", summary="Keep shared content only in history")
        victim_refs = {sha for rev in fx.projects.list_revisions(victim) for sha in rev["files"].values()}
        survivor_revisions = fx.projects.list_revisions(survivor)
        survivor_refs = {sha for rev in survivor_revisions for sha in rev["files"].values()}
        unique = victim_refs - survivor_refs
        shared_refs = victim_refs & survivor_refs
        self.assertEqual(len(unique), 3, {"unique": sorted(unique), "shared": sorted(shared_refs)})
        self.assertEqual(len(shared_refs), 1, sorted(shared_refs))
        return victim, survivor, unique, shared_refs, survivor_revisions

    def test_f2_delete_removes_all_unique_historical_blobs_and_keeps_shared_history(self):
        fx = self.fx
        victim, survivor, unique, shared, revisions = self.deletion_fixture()
        survivor_before = [fx.projects.bundle(survivor, rev["rev"]) for rev in revisions]
        before = self.blob_snapshot()
        result = fx.projects.delete_space(victim, actor="user", confirm=victim)
        after = self.blob_snapshot()
        survivor_after = [fx.projects.bundle(survivor, rev["rev"]) for rev in revisions]
        with fx.db.read() as conn:
            victim_rows = {table: conn.execute(f"SELECT count(*) FROM {table} WHERE {column}=?",
                                               (victim,)).fetchone()[0]
                           for table, column in (("spaces", "id"), ("revisions", "space"))}
        message = self.observe(result=result, unique=sorted(unique), shared=sorted(shared),
                               remaining_unique=sorted(unique & after.keys()),
                               blobs_before=sorted(before), blobs_after=sorted(after), victim_rows=victim_rows)
        self.assertTrue(result["deleted"], message)
        self.assertEqual(victim_rows, {"spaces": 0, "revisions": 0}, message)
        self.assertEqual(survivor_after, survivor_before, message)
        self.assertTrue(shared <= after.keys(), message)
        self.assertEqual({sha: after[sha] for sha in shared}, {sha: before[sha] for sha in shared}, message)
        self.assertEqual(unique & after.keys(), set(), message)
        self.assertEqual(after.keys(), before.keys() - unique, message)

    def test_f2_failed_delete_rolls_back_blob_removal_with_revisions(self):
        fx = self.fx
        victim, survivor, unique, shared, _ = self.deletion_fixture()
        before_blobs = self.blob_snapshot()
        before_victim = fx.projects.list_revisions(victim)
        before_survivor = fx.projects.list_revisions(survivor)
        with fx.db.write() as conn:
            conn.execute("CREATE TRIGGER refuse_space_delete BEFORE DELETE ON spaces "
                         "BEGIN SELECT RAISE(ABORT, 'Injected deletion rollback'); END")
        with self.assertRaises(sqlite3.IntegrityError) as caught:
            fx.projects.delete_space(victim, actor="user", confirm=victim)
        after_blobs = self.blob_snapshot()
        after_victim = fx.projects.list_revisions(victim)
        after_survivor = fx.projects.list_revisions(survivor)
        message = self.observe(error=str(caught.exception), unique=sorted(unique), shared=sorted(shared),
                               blobs_before=sorted(before_blobs), blobs_after=sorted(after_blobs),
                               victim_revision_count=len(after_victim), survivor_revision_count=len(after_survivor))
        self.assertIn("Injected deletion rollback", str(caught.exception), message)
        self.assertEqual(after_blobs, before_blobs, message)
        self.assertEqual(after_victim, before_victim, message)
        self.assertEqual(after_survivor, before_survivor, message)

    def concurrent_agent_refresh(self, second_trigger):
        fx = self.fx
        sid = fx.make()
        original = self.ctx.dispatch_tool
        first_entered, release = threading.Event(), threading.Event()
        second_started, second_progress = threading.Event(), threading.Event()
        counter_lock, cron_lock = threading.Lock(), threading.RLock()
        entries, outcomes, errors = [], {}, {}

        def dispatch(name, args):
            if args["action"] == "run":
                with counter_lock:
                    entries.append(copy.deepcopy(args))
                    ordinal = len(entries)
                if ordinal == 1:
                    first_entered.set()
                    if not release.wait(10):
                        raise TimeoutError("Test did not release the first synthetic native run")
                else:
                    second_progress.set()
            with cron_lock:
                return original(name, args)

        def request(key, trigger):
            if key == "second":
                second_started.set()
            try:
                outcomes[key] = self.refresh(sid, trigger=trigger,
                                             actor="user" if trigger == "manual" else "agent:review")
            except Exception as exc:
                errors[key] = repr(exc)
            finally:
                if key == "second":
                    second_progress.set()

        first = threading.Thread(target=request, args=("first", "manual"), daemon=True)
        second = threading.Thread(target=request, args=("second", second_trigger), daemon=True)
        with patch.object(self.ctx, "dispatch_tool", side_effect=dispatch):
            try:
                first.start()
                self.assertTrue(first_entered.wait(5), {"outcomes": outcomes, "errors": errors})
                second.start()
                self.assertTrue(second_started.wait(5), errors)
                # A deduplicating caller may return immediately or wait for the owner. Neither needs a second run.
                second_progress.wait(1)
            finally:
                release.set()
                first.join(10)
                if second.ident is not None:
                    second.join(10)
        overlap_executions = copy.deepcopy(fx.cron.executions)
        overlap_effects = copy.deepcopy(self.ctx.effects)
        overlap_creates = [call for call in fx.cron.calls if call[0] == "create"]
        self.assertFalse(first.is_alive() or second.is_alive(), {"outcomes": outcomes, "errors": errors})
        later = self.refresh(sid)
        message = self.observe(precondition="First native run held while a second public start_refresh is invoked",
                               second_trigger=second_trigger, outcomes=outcomes, errors=errors,
                               native_run_entries=entries, overlap_executions=overlap_executions,
                               overlap_effects=overlap_effects, overlap_creates=overlap_creates,
                               later=later, all_executions=fx.cron.executions, all_effects=self.ctx.effects)
        self.assertEqual(errors, {}, message)
        self.assertEqual(set(outcomes), {"first", "second"}, message)
        self.assertNotIn("error", outcomes["first"], message)
        self.assertNotIn("error", outcomes["second"], message)
        first_job = outcomes["first"].get("result", {}).get("cron_job_id")
        second_job = outcomes["second"].get("result", {}).get("cron_job_id")
        self.assertTrue(first_job, message)
        self.assertEqual(second_job, first_job, message)
        self.assertEqual(len(overlap_creates), 1, message)
        self.assertEqual(len(overlap_executions), 1, message)
        self.assertEqual(len(overlap_effects), 1, message)
        self.assertNotIn("error", later, message)
        self.assertEqual(len(fx.cron.executions), 2, message)
        self.assertEqual([effect["execution_count"] for effect in self.ctx.effects], [1, 2], message)

    def test_f3_concurrent_desktop_and_chat_share_one_agent_execution(self):
        self.concurrent_agent_refresh("chat")

    def test_f3_concurrent_desktop_requests_share_one_agent_execution(self):
        self.concurrent_agent_refresh("manual")

    def test_f3_background_followup_deduplicates_until_native_completion(self):
        fx = self.fx
        sid = fx.make()
        self.ctx.outcome = RunOutcome.BACKGROUND
        first = self.refresh(sid)
        second = self.refresh(sid, trigger="chat", actor="agent:review")
        overlapping = copy.deepcopy(fx.cron.executions)
        overlapping_jobs = fx.cron.list_jobs(include_disabled=True)
        jid = first.get("result", {}).get("cron_job_id")
        self.assertTrue(jid, first)
        self.ctx.finish_background(jid)
        completion_seen = fx.upkeep.get_upkeep(sid)
        self.ctx.outcome = RunOutcome.INLINE
        third = self.refresh(sid)
        message = self.observe(first=first, second=second, overlapping_executions=overlapping,
                               overlapping_jobs=overlapping_jobs, native_completion=completion_seen,
                               third=third, all_executions=fx.cron.executions, effects=self.ctx.effects)
        self.assertNotIn("error", second, message)
        self.assertEqual(second.get("result", {}).get("cron_job_id"), jid, message)
        self.assertEqual(len(overlapping), 1, message)
        self.assertEqual(overlapping[0]["status"], "running", message)
        self.assertEqual(len(overlapping_jobs), 1, message)
        self.assertNotIn("error", third, message)
        self.assertEqual(len(fx.cron.executions), 2, message)
        self.assertEqual([entry["status"] for entry in fx.cron.executions], ["completed", "completed"], message)
        self.assertEqual([effect["execution_count"] for effect in self.ctx.effects], [1, 2], message)

    def test_f3_paused_linked_job_is_not_implicitly_run_or_resumed(self):
        fx = self.fx
        sid = fx.make()
        jid = fx.schedule(sid)["link"]["cron_job_id"]
        fx.upkeep.upkeep_action(sid, "pause", actor="user")
        before = fx.cron.get_job(jid)
        outcome = self.refresh(sid)
        after = fx.cron.get_job(jid)
        message = self.observe(outcome=outcome, before=before, after=after,
                               executions=fx.cron.executions, effects=self.ctx.effects)
        self.assertEqual(outcome.get("error", {}).get("reason"), "native_refused", message)
        self.assertEqual(after, before, message)
        self.assertEqual((fx.cron.executions, self.ctx.effects), ([], []), message)

    @staticmethod
    def feed_payload(count, title_prefix="Entry"):
        return ("<rss version='2.0'><channel>" + "".join(
            f"<item><guid>f4-item-{index}</guid><title>{title_prefix} {index}</title></item>"
            for index in range(count)) + "</channel></rss>").encode()

    def feed_refresh(self, sid, payload):
        source = {"id": "demo", "url": "https://example.org/feed", "collection": "items"}
        counts = {"added": 0, "updated": 0, "unchanged": 0}
        arrivals = []

        def before_write():
            arrivals.append("before_write")

        try:
            result, as_of = self.fx.feeds.refresh_source(
                sid, source, actor="user", before_write=before_write,
                fetcher=lambda *_: payload, counts=counts)
            return {"counts": result, "source_as_of": as_of, "arrivals": arrivals}
        except self.fx.core.SpacesError as exc:
            return {"error": exc.to_dict(), "counts": counts, "arrivals": arrivals}

    def source_state(self, sid):
        return {"records": self.fx.records.query(sid, "items", limit=2000),
                "changes": self.fx.records.changes_since(sid, 0, limit=2000)}

    def accepted_feed(self, count):
        fx = self.fx
        sid = fx.make(handler="feed")
        seed = self.feed_refresh(sid, self.feed_payload(1))
        self.assertNotIn("error", seed, seed)
        row = fx.records.query(sid, "items")["records"][0]
        user_data = {"note": "Keep my annotation", "status": "reading"}
        fx.records.put(sid, "items", row["id"], user_data, actor="user", base_rev=row["rev"])
        payload = self.feed_payload(count, "Updated")
        parsed = fx.feeds.parse(payload)
        outcome = self.feed_refresh(sid, payload)
        state = self.source_state(sid)
        saved = fx.records.get(sid, "items", row["id"])
        message = self.observe(entries=count, parsed=len(parsed), outcome=outcome,
                               stored=state["records"]["total"], saved=saved,
                               change_count=len(state["changes"]["changes"]))
        self.assertEqual(len(parsed), count, message)
        self.assertEqual(outcome.get("arrivals"), ["before_write"], message)
        self.assertNotIn("error", outcome, message)
        self.assertEqual(outcome["counts"], {"added": count - 1, "updated": 1, "unchanged": 0}, message)
        self.assertEqual(state["records"]["total"], count, message)
        self.assertEqual({record["id"] for record in state["records"]["records"]},
                         {rid for rid, _ in parsed}, message)
        self.assertEqual(saved["data"], user_data, message)
        self.assertEqual(saved["source"]["title"], "Updated 0", message)

    def test_f4_feed_500_entries_control_preserves_user_data(self):
        self.accepted_feed(500)

    def test_f4_feed_501_entries_is_accepted_without_truncation(self):
        self.accepted_feed(501)

    def test_f4_feed_1000_entries_is_accepted_without_truncation(self):
        self.accepted_feed(1000)

    def test_f4_parser_refuses_1001_and_refresh_leaves_records_and_cursor_unchanged(self):
        fx = self.fx
        sid = fx.make(handler="feed")
        self.assertNotIn("error", self.feed_refresh(sid, self.feed_payload(1)))
        before = self.source_state(sid)
        payload = self.feed_payload(1001)
        with self.assertRaises(fx.core.SpacesError) as caught:
            fx.feeds.parse(payload)
        outcome = self.feed_refresh(sid, payload)
        after = self.source_state(sid)
        error = caught.exception.to_dict()
        message = self.observe(parser_error=error, refresh=outcome, before=before, after=after)
        self.assertEqual((error.get("code"), error.get("limit"), error.get("actual")),
                         ("limit", 1000, 1001), message)
        self.assertEqual(outcome.get("error"), error, message)
        self.assertEqual(outcome["arrivals"], [], message)
        self.assertEqual(after, before, message)

    def atomic_feed_failure(self, count, fail_at):
        fx = self.fx
        sid = fx.make(handler="feed")
        self.assertNotIn("error", self.feed_refresh(sid, self.feed_payload(1)))
        row = fx.records.query(sid, "items")["records"][0]
        fx.records.put(sid, "items", row["id"], {"note": "Rollback keeps this"},
                       actor="user", base_rev=row["rev"])
        before = self.source_state(sid)
        original = fx.records._upsert_source
        calls = []

        def fail_after_real_prefix(*args, **kwargs):
            calls.append(args[3])
            if len(calls) == fail_at:
                raise fx.core.SpacesError("invalid", "Injected storage failure after real source prefix")
            return original(*args, **kwargs)

        with patch.object(fx.records, "_upsert_source", side_effect=fail_after_real_prefix):
            outcome = self.feed_refresh(sid, self.feed_payload(count, "Must roll back"))
        after = self.source_state(sid)
        message = self.observe(entries=count, fail_at=fail_at, upsert_calls=len(calls), outcome=outcome,
                               before=before, after=after)
        self.assertEqual(after, before, message)
        self.assertEqual(outcome["counts"], {"added": 0, "updated": 0, "unchanged": 0}, message)
        self.assertEqual(len(calls), fail_at, message)
        self.assertEqual(outcome.get("error", {}).get("message"),
                         "Injected storage failure after real source prefix", message)

    def test_f4_small_source_failure_rolls_back_real_prefix_control(self):
        self.atomic_feed_failure(3, 3)

    def test_f4_large_source_failure_rolls_back_across_the_500_entry_boundary(self):
        self.atomic_feed_failure(1000, 501)

    def test_f4_user_batch_501_stays_refused_and_atomic(self):
        fx = self.fx
        sid = fx.make(handler="feed")
        before = self.source_state(sid)
        ops = [{"op": "put", "collection": "items", "id": f"user-{index}", "data": {"note": "Mine"}}
               for index in range(501)]
        with self.assertRaises(fx.core.SpacesError) as caught:
            fx.records.batch(sid, ops, actor="user")
        after = self.source_state(sid)
        error = caught.exception.to_dict()
        message = self.observe(error=error, before=before, after=after)
        self.assertEqual((error.get("code"), error.get("limit"), error.get("actual")),
                         ("limit", 500, 501), message)
        self.assertEqual(after, before, message)


if __name__ == "__main__":
    unittest.main()
