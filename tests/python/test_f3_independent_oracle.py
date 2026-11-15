"""Independent RED oracle for four Astra-inferred lifecycle hazards on the real core.

Authored without execution (file tools only). Boundaries are SYNTHETIC: the public cron
tool is the existing synthetic double (in-process or file-backed across real processes) and
feed HTTPS is the existing pinned synthetic transport. A pass here is never native
completion proof. Nothing inserts or edits private claim rows; every observation comes
from the public core API, SQLite reads, or the synthetic cron/HTTPS leaves.

Hazards (each has separately named control methods that do not depend on the target fault):
  H1  Equal-time generation reuse with a reordered (late) accepted run reply.
  H2  Created-once acceptance whose reply carries a non-null completion stamp; a later list
      with that SAME stamp is not completion of the accepted background work.
  H3  Real owner death after the accepted reply is durable, before the once pause: the
      follower must expose/reconcile the disable obligation without claiming completion or
      requiring crash-proof exactly-once. No new table/field name is demanded.
  H4  A refused Space delete must not cancel queued/running feed work beforehand.

Process and fixture homes require F3_PROCESS_TEST_TMPDIR on Expansion. Run with the
documented test interpreter from the repository root, for example:
  F3_PROCESS_TEST_TMPDIR=/Volumes/Expansion/... python -m unittest tests.python.test_f3_independent_oracle
Composition only: existing TestCases are never inherited, so their tests are not re-run.
"""
from contextlib import ExitStack
import copy
import importlib
import json
import os
from pathlib import Path
import re
import signal
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests.python import test_f3_process_claims as process_support
from tests.python.review_customization_support import CustomizationFixture, Response
from tests.python.test_agent_refresh_dispatch import RunOutcome
from tests.python.test_f1_f4_regressions import CompletingCronContext

STAMP = "2026-11-14T08:00:00+00:00"
BOUNDED = 12  # seconds; every wait is bounded and every owned thread/process is released in cleanup


def expansion_base():
    raw = os.environ.get("F3_PROCESS_TEST_TMPDIR")
    if not raw:
        raise ValueError("F3_PROCESS_TEST_TMPDIR must name an owned directory on Expansion")
    base = Path(raw).resolve()
    if not base.is_relative_to(Path("/Volumes/Expansion")):
        raise ValueError("F3_PROCESS_TEST_TMPDIR must be an owned directory on Expansion")
    base.mkdir(parents=True, exist_ok=True)
    return base


class Observed:
    """Structured JSON per case, emitted from a cleanup so failures and errors still print it."""
    boundary = "synthetic public cron"

    def start_observation(self):
        self.obs = {"case": self.id(), "boundary": self.boundary}
        self.addCleanup(self.emit)

    def record(self, **values):
        self.obs.update(values)

    def msg(self):
        return json.dumps(self.obs, sort_keys=True, default=str)

    def emit(self):
        print(self.msg(), flush=True)


class InProcessCase(Observed, unittest.TestCase):
    """Real core, in-process synthetic cron, isolated fixture home on Expansion. No tests here."""

    def setUp(self):
        self.start_observation()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(tempfile, "tempdir", str(expansion_base())))
        self.fx = CustomizationFixture(self.stack)
        self.ctx = CompletingCronContext(self.fx)
        self.fx.ctx = self.ctx
        self.fx.upkeep.configure_context(self.ctx)

    def refresh(self, sid, trigger="manual", actor="user"):
        try:
            return {"result": self.fx.runs.start_refresh(sid, trigger=trigger, actor=actor)}
        except self.fx.core.SpacesError as exc:
            return {"error": exc.to_dict()}

    def claim(self, sid):
        with self.fx.db.read() as conn:
            row = conn.execute("SELECT * FROM refresh_claims WHERE space=?", (sid,)).fetchone()
            return dict(row) if row else None

    def created_at(self, sid):
        with self.fx.db.read() as conn:
            row = conn.execute("SELECT created_at FROM spaces WHERE id=?", (sid,)).fetchone()
            return row["created_at"] if row else None


# --------------------------------------------------------------------------------------
# H1: generation reuse with reordered replies
# --------------------------------------------------------------------------------------
class HeldReply:
    """Native executes and accepts, then delivery of its FIRST run reply is held (reordered)."""

    def __init__(self, ctx):
        self.original = ctx.dispatch_tool
        self.entered, self.release = threading.Event(), threading.Event()
        self.lock, self.taken, self.reply = threading.Lock(), False, None

    def __call__(self, name, args):
        reply = self.original(name, args)
        if args["action"] == "run":
            with self.lock:
                first, self.taken = not self.taken, True
            if first:
                self.reply = json.loads(reply)
                self.entered.set()
                if not self.release.wait(BOUNDED + 3):
                    raise TimeoutError("test never released the held native reply")
        return reply


class GenerationReuseTests(InProcessCase):
    MUTATING = {"create", "remove", "pause", "resume", "trigger", "cancel"}

    def new_state(self, sid, jid):
        fx = self.fx
        return {"claim": self.claim(sid), "link": fx.upkeep.get_upkeep(sid)["link"],
                "job": fx.cron.get_job(jid), "bundle": fx.projects.bundle(sid),
                "executions": copy.deepcopy(fx.cron.executions), "cron_calls": len(fx.cron.calls)}

    def scenario(self, mode):
        """mode: none (late delivery only), delete_only, recreate (delete + same-sid recreate + newer work)."""
        fx, ctx = self.fx, self.ctx
        instant = time.time()
        held = HeldReply(ctx)
        outcome, box = {}, {}
        data = self.obs["scenario"] = {"mode": mode, "frozen_instant": instant}

        def old_caller():
            try:
                outcome["old"] = self.refresh(box["sid"])
            except BaseException as exc:  # recorded and asserted on, never converted into a result
                outcome["raised"] = repr(exc)

        # Freezing db.now makes both incarnations share one created_at: wall-clock cannot tell them apart.
        with patch.object(fx.db, "now", return_value=instant), \
                patch.object(ctx, "dispatch_tool", side_effect=held):
            ctx.outcome = RunOutcome.BACKGROUND
            box["sid"] = sid = fx.make()
            data["sid"], data["old_created_at"] = sid, self.created_at(sid)
            thread = threading.Thread(target=old_caller, name="h1-old-caller", daemon=True)
            thread.start()
            try:
                data["reply_held"] = held.entered.wait(BOUNDED)
                if not data["reply_held"]:
                    self.fail("the accepted native run reply was never produced")
                data["accepted_reply"] = held.reply
                data["old_claim"] = self.claim(sid)
                if mode in ("delete_only", "recreate"):
                    data["deleted"] = fx.projects.delete_space(sid, actor="user", confirm=sid)
                if mode == "recreate":
                    new_sid = fx.make()
                    data["new_sid"], data["new_created_at"] = new_sid, self.created_at(new_sid)
                    link = fx.schedule(new_sid)["link"]
                    data["new_link_job"] = link["cron_job_id"]
                    data["new_owner"] = self.refresh(new_sid)
                    data["new_claim"] = self.claim(new_sid)
                    data["new_before"] = self.new_state(new_sid, link["cron_job_id"])
            finally:
                held.release.set()
                thread.join(BOUNDED + 3)
            data["old_thread_alive"] = thread.is_alive()
            data["old_outcome"] = outcome
            data["cron_calls_total"] = len(fx.cron.calls)
            if mode == "recreate":
                data["new_after"] = self.new_state(data["new_sid"], data["new_link_job"])
            data["old_claim_after"] = self.claim(sid) if mode == "none" else None
        return data

    def test_h1_control_no_race_late_reply_reaches_its_live_owner(self):
        data = self.scenario("none")
        m = self.msg()
        self.assertFalse(data["old_thread_alive"], m)
        self.assertNotIn("raised", data["old_outcome"], m)
        old = data["old_outcome"]["old"]
        self.assertNotIn("error", old, m)
        self.assertEqual(old["result"]["dispatch"], data["accepted_reply"], m)
        self.assertEqual(old["result"]["one_shot"]["consumed"], "paused", m)
        self.assertEqual(data["old_claim_after"]["token"], data["old_claim"]["token"], m)
        self.assertEqual(data["old_claim_after"]["phase"], "background", m)

    def test_h1_control_delete_without_recreate_reports_not_found_with_original_native(self):
        data = self.scenario("delete_only")
        m = self.msg()
        self.assertTrue(data["deleted"]["deleted"], m)
        self.assertFalse(data["old_thread_alive"], m)
        self.assertNotIn("raised", data["old_outcome"], m)
        old = data["old_outcome"]["old"]
        self.assertNotIn("result", old, m)
        self.assertEqual(old["error"]["code"], "not_found", m)
        self.assertEqual(old["error"]["native"], data["accepted_reply"], m)

    def recreated(self):
        data = self.scenario("recreate")
        m = self.msg()
        # Preconditions: this is genuinely the same sid, the same created_at and different generations.
        self.assertTrue(data["deleted"]["deleted"], m)
        self.assertEqual(data["new_sid"], data["sid"], m)
        self.assertEqual(data["new_created_at"], data["old_created_at"], m)
        self.assertNotIn("error", data["new_owner"], m)
        self.assertEqual(data["new_claim"]["space_created_at"], data["old_claim"]["space_created_at"], m)
        self.assertNotEqual(data["new_claim"]["token"], data["old_claim"]["token"], m)
        self.assertNotEqual(data["new_claim"]["cron_job_id"], data["old_claim"]["cron_job_id"], m)
        self.assertFalse(data["old_thread_alive"], m)
        self.assertNotIn("raised", data["old_outcome"], m)
        return data, m

    def test_h1_new_generation_claim_link_job_and_space_survive_the_stale_reply(self):
        data, m = self.recreated()
        before, after = data["new_before"], data["new_after"]
        for key in ("claim", "link", "job", "bundle", "executions"):
            self.assertEqual(after[key], before[key], f"{key}: {m}")
        jid = data["new_link_job"]
        touched = [call for call in self.fx.cron.calls[before["cron_calls"]:]
                   if call[1] == jid and call[0] in self.MUTATING]
        self.assertEqual(touched, [], m)

    def test_h1_stale_reply_after_recreate_reports_not_found_with_its_original_native_reply(self):
        data, m = self.recreated()
        old = data["old_outcome"]["old"]
        self.assertNotIn("result", old, m)
        self.assertEqual(old.get("error", {}).get("code"), "not_found", m)
        self.assertEqual(old.get("error", {}).get("native"), data["accepted_reply"], m)


# --------------------------------------------------------------------------------------
# H2: created-once acceptance with a non-null matching baseline
# --------------------------------------------------------------------------------------
class OnceBaselineTests(InProcessCase):
    def accepted_once(self, sid, stamp):
        """Real fresh Refresh. The synthetic native job already carries `stamp` when it accepts the run."""
        fx, ctx = self.fx, self.ctx
        original = ctx.dispatch_tool

        def stamped(name, args):
            if stamp is not None and args["action"] == "run":
                job = fx.cron.jobs.get(args["job_id"])
                if job is not None and job.get("name") == f"living-spaces:{sid}:once":
                    job["last_run_at"] = stamp  # native fact at the public boundary, not a claim edit
            return original(name, args)

        ctx.outcome = RunOutcome.BACKGROUND
        with patch.object(ctx, "dispatch_tool", side_effect=stamped):
            owner = self.refresh(sid)
        raw = copy.deepcopy(ctx.run_replies[-1])
        return owner, raw, owner.get("result", {}).get("cron_job_id")

    def assert_accepted(self, sid, owner, raw, jid, stamp):
        fx, m = self.fx, self.msg()
        claim = self.claim(sid)
        self.assertNotIn("error", owner, m)
        self.assertEqual(owner["result"]["dispatch"], raw, m)
        self.assertEqual(owner["result"]["one_shot"]["consumed"], "paused", m)
        self.assertEqual(raw["job"]["execution_mode"], "background", m)
        self.assertEqual(raw["job"]["job_id"], jid, m)
        self.assertEqual(raw["job"]["last_run_at"], stamp, m)
        self.assertNotIn("execution_success", raw["job"], m)
        self.assertIsNotNone(claim, m)
        self.assertEqual((claim["cron_job_id"], claim["created_one_shot"], claim["phase"]),
                         (jid, 1, "background"), m)
        self.assertEqual(json.loads(claim["native"]), raw, m)
        self.assertEqual([e["status"] for e in fx.cron.executions if e["job_id"] == jid], ["running"], m)
        self.assertIs(fx.cron.get_job(jid)["enabled"], False, m)
        return claim

    def assert_still_joined(self, sid, follower, raw, jid, claim0, m):
        self.assertNotIn("error", follower, m)
        result = follower["result"]
        self.assertIs(result.get("joined"), True, m)
        self.assertEqual(result["cron_job_id"], jid, m)
        self.assertEqual(result["dispatch"], raw, m)
        self.assertEqual(result["refresh_state"], "background", m)
        self.assertEqual(self.claim(sid), claim0, m)
        self.assertIsNotNone(self.fx.cron.get_job(jid), m)

    def test_h2_target_same_nonnull_stamp_does_not_complete_accepted_once_work(self):
        fx, ctx = self.fx, self.ctx
        sid = fx.make()
        owner, raw, jid = self.accepted_once(sid, STAMP)
        claim0 = self.claim(sid)
        job0 = fx.cron.get_job(jid)
        self.record(owner=owner, accepted=raw, claim_before=claim0, job_before=job0)
        self.assert_accepted(sid, owner, raw, jid, STAMP)
        self.assertEqual(job0["last_run_at"], STAMP, self.msg())  # a later list carries the SAME stamp
        marks = {"calls": len(fx.cron.calls), "attempts": len(ctx.run_attempts),
                 "executions": copy.deepcopy(fx.cron.executions), "effects": len(ctx.effects)}
        follower = self.refresh(sid)
        after = {"claim": self.claim(sid), "job": fx.cron.get_job(jid),
                 "executions": copy.deepcopy(fx.cron.executions),
                 "jobs": fx.cron.list_jobs(include_disabled=True),
                 "cron_calls_after": [list(c) for c in fx.cron.calls[marks["calls"]:]]}
        self.record(follower=follower, after=after, marks=marks)
        m = self.msg()
        self.assertIs(follower.get("result", {}).get("joined"), True, m)
        self.assertEqual(follower["result"]["cron_job_id"], jid, m)
        self.assertEqual(follower["result"]["dispatch"], raw, m)
        self.assertEqual(after["claim"], claim0, m)
        self.assertIsNotNone(after["job"], m)
        self.assertEqual([c for c in after["cron_calls_after"] if c[1] == jid], [], m)
        self.assertEqual([c for c in after["cron_calls_after"] if c[0] in ("create", "remove")], [], m)
        self.assertEqual(len(ctx.run_attempts), marks["attempts"], m)
        self.assertEqual(after["executions"], marks["executions"], m)
        self.assertEqual(len(ctx.effects), marks["effects"], m)

    def test_h2_control_changed_stamp_after_matching_acceptance_settles_and_admits_later_run(self):
        fx, ctx = self.fx, self.ctx
        sid = fx.make()
        owner, raw, jid = self.accepted_once(sid, STAMP)
        self.record(owner=owner, accepted=raw)
        claim0 = self.assert_accepted(sid, owner, raw, jid, STAMP)
        ctx.finish_background(jid)
        completed = fx.cron.get_job(jid)
        ctx.outcome = RunOutcome.INLINE
        later = self.refresh(sid)
        self.record(claim_before=claim0, completed=completed, later=later,
                    claim_after=self.claim(sid), executions=fx.cron.executions, effects=ctx.effects)
        m = self.msg()
        self.assertNotEqual(completed["last_run_at"], STAMP, m)
        self.assertNotIn("error", later, m)
        self.assertFalse(later["result"].get("joined", False), m)
        self.assertNotEqual(later["result"]["cron_job_id"], jid, m)
        old_job = fx.cron.get_job(jid)
        self.assertTrue(old_job is None or old_job["enabled"] is False, m)
        self.assertEqual([e["status"] for e in fx.cron.executions], ["completed", "completed"], m)
        self.assertEqual([e["execution_count"] for e in ctx.effects], [1, 2], m)
        self.assertIsNone(self.claim(sid), m)

    def test_h2_control_unchanged_null_baseline_stays_joined(self):
        fx, ctx = self.fx, self.ctx
        sid = fx.make()
        owner, raw, jid = self.accepted_once(sid, None)
        self.record(owner=owner, accepted=raw)
        claim0 = self.assert_accepted(sid, owner, raw, jid, None)
        follower = self.refresh(sid)
        self.record(claim_before=claim0, follower=follower, executions=fx.cron.executions)
        m = self.msg()
        self.assert_still_joined(sid, follower, raw, jid, claim0, m)
        self.assertEqual(len(fx.cron.executions), 1, m)
        self.assertEqual(ctx.effects, [], m)

    def test_h2_control_foreign_completion_and_malformed_stamp_do_not_settle_accepted_once(self):
        fx, ctx = self.fx, self.ctx
        foreign = fx.make()
        foreign_jid = fx.schedule(foreign)["link"]["cron_job_id"]
        ctx.outcome = RunOutcome.BACKGROUND
        foreign_owner = self.refresh(foreign)
        self.assertNotIn("error", foreign_owner, foreign_owner)
        sid = fx.make()
        # Null acceptance baseline here: this control must not share the H2 target fault.
        owner, raw, jid = self.accepted_once(sid, None)
        claim0 = self.assert_accepted(sid, owner, raw, jid, None)
        ctx.finish_background(foreign_jid)
        foreign_stamp = fx.cron.get_job(foreign_jid)["last_run_at"]
        after_foreign = self.refresh(sid)
        self.record(owner=owner, accepted=raw, foreign_stamp=foreign_stamp, after_foreign=after_foreign,
                    claim_before=claim0)
        m = self.msg()
        self.assertIsNotNone(foreign_stamp, m)
        self.assert_still_joined(sid, after_foreign, raw, jid, claim0, m)
        fx.cron.jobs[jid]["last_run_at"] = "malformed-completion-stamp"
        after_malformed = self.refresh(sid)
        self.record(after_malformed=after_malformed, executions=fx.cron.executions)
        m = self.msg()
        self.assert_still_joined(sid, after_malformed, raw, jid, claim0, m)
        self.assertEqual([e["job_id"] for e in fx.cron.executions], [foreign_jid, jid], m)

    def test_h2_control_linked_job_with_matching_nonnull_baseline_is_not_completed_by_same_stamp(self):
        fx, ctx = self.fx, self.ctx
        sid = fx.make()
        jid = fx.schedule(sid)["link"]["cron_job_id"]
        fx.cron.jobs[jid]["last_run_at"] = STAMP  # earlier native completion, before this acceptance
        ctx.outcome = RunOutcome.BACKGROUND
        owner = self.refresh(sid)
        raw = copy.deepcopy(ctx.run_replies[-1])
        claim0 = self.claim(sid)
        follower = self.refresh(sid)
        self.record(owner=owner, accepted=raw, claim_before=claim0, follower=follower,
                    executions=fx.cron.executions)
        m = self.msg()
        self.assertNotIn("error", owner, m)
        self.assertEqual(raw["job"]["last_run_at"], STAMP, m)
        self.assertEqual(json.loads(claim0["baseline_completion"]), STAMP, m)
        self.assertEqual((claim0["created_one_shot"], claim0["phase"]), (0, "background"), m)
        self.assert_still_joined(sid, follower, raw, jid, claim0, m)
        self.assertEqual(len(fx.cron.executions), 1, m)


# --------------------------------------------------------------------------------------
# H3: real owner death after durable acceptance, before the once pause
# --------------------------------------------------------------------------------------
class DyingSharedCron(process_support.SharedCronContext):
    """File-backed synthetic cron whose process is SIGKILLed on the first `die_on` call after a run reply."""

    def __init__(self, root, core, label, mode, die_on):
        super().__init__(root, core, label, mode)
        self.die_on, self.accepted = die_on, False

    def evidence(self, args):
        names = ("HOME", "HERMES_HOME", "TMPDIR", "LIVING_SPACES_DB",
                 "PYTHONDONTWRITEBYTECODE", "HERMES_DISABLE_LAZY_INSTALLS")
        return {"pid": os.getpid(), "environment": {key: os.environ.get(key) for key in names},
                "isolated": sys.flags.isolated, "no_bytecode": sys.dont_write_bytecode,
                "db_path": str(self.core.db.db_path().resolve()),
                "hermes_home": str(self.core.db.hermes_home().resolve()), "killed_before": args}

    def dispatch_tool(self, name, args):
        if self.accepted and args["action"] == self.die_on:
            (self.root / (self.label + ".dying")).write_text(json.dumps(self.evidence(args)))
            os.kill(os.getpid(), signal.SIGKILL)
            while True:  # never reached once the signal is delivered
                time.sleep(1)
        reply = super().dispatch_tool(name, args)
        if args["action"] == "run":
            self.accepted = True
        return reply


def oracle_worker(root, label, die_on, mode):
    sys.path.insert(0, str(ROOT / "src/living-spaces"))
    core = importlib.import_module("living_spaces_core")
    ctx = DyingSharedCron(root, core, label, mode, die_on)
    core.configure_context(ctx)
    record = {"pid": os.getpid(), "survived": True}
    try:
        record["result"] = core.start_refresh((root / "space").read_text(), trigger="manual",
                                              actor="agent:process")
    except core.SpacesError as exc:
        record["error"] = exc.to_dict()
    (root / (label + ".json")).write_text(json.dumps(record))


def claim_row(root, sid):
    with sqlite3.connect((root / "spaces.db").as_uri() + "?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM refresh_claims WHERE space=?", (sid,)).fetchone()
        return dict(row) if row else None


OBLIGATION = re.compile(r"disabl|pause|obligation|enabled|schedul|may (still )?(run|fire)", re.I)
CLAIMS_DISABLED = re.compile(r'"consumed":\s*"paused"|"enabled":\s*false', re.I)


class OwnerDeathTests(Observed, unittest.TestCase):
    boundary = "synthetic public cron (file-backed) with real worker processes"

    def setUp(self):
        self.start_observation()
        expansion_base()
        self.h = process_support.F3ProcessClaimsTests("runTest")
        self.addCleanup(self.h.doCleanups)
        self.h.setUp()
        self.h.env.update(PYTHONDONTWRITEBYTECODE="1", HERMES_DISABLE_LAZY_INSTALLS="1")
        self.root = self.h.root
        self.sid = (self.root / "space").read_text()

    def spawn_dying(self, label, die_on="pause", mode="background"):
        with (self.root / (label + ".log")).open("w") as log:
            child = subprocess.Popen(
                [sys.executable, "-I", "-B", str(Path(__file__).resolve()), "--oracle-worker",
                 str(self.root), label, die_on, mode],
                cwd=self.root, env=self.h.env, stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True)
        self.h.children.append((child, label))
        return child

    def dead_owner(self):
        owner = self.spawn_dying("owner")
        owner.wait(timeout=20)
        dying = json.loads((self.root / "owner.dying").read_text())
        claim = claim_row(self.root, self.sid)
        native = process_support.snapshot(self.root)
        self.record(owner_pid=owner.pid, owner_returncode=owner.returncode, dying=dying,
                    claim_at_death=claim, native_at_death=native,
                    owner_log=(self.root / "owner.log").read_text())
        m = self.msg()
        env = self.h.env
        self.assertEqual(owner.returncode, -signal.SIGKILL, m)
        self.assertFalse((self.root / "owner.json").exists(), m)
        self.assertEqual(dying["pid"], owner.pid, m)
        self.assertEqual({k: dying["environment"][k] for k in ("HOME", "HERMES_HOME", "TMPDIR", "LIVING_SPACES_DB")},
                         {k: env[k] for k in ("HOME", "HERMES_HOME", "TMPDIR", "LIVING_SPACES_DB")}, m)
        self.assertEqual((dying["isolated"], dying["no_bytecode"]), (1, True), m)
        self.assertEqual((dying["db_path"], dying["hermes_home"]), (env["LIVING_SPACES_DB"], env["HERMES_HOME"]), m)
        self.assertEqual(dying["killed_before"]["action"], "pause", m)
        self.assertIsNotNone(claim, m)
        jid = claim["cron_job_id"]
        accepted = json.loads(claim["native"])
        self.assertEqual((claim["phase"], claim["created_one_shot"]), ("background", 1), m)
        self.assertEqual((accepted["job"]["job_id"], accepted["job"]["execution_mode"]), (jid, "background"), m)
        self.assertNotIn("execution_success", accepted["job"], m)
        self.assertEqual([e["status"] for e in native["executions"]], ["running"], m)
        self.assertEqual(accepted["job"]["delegation_id"], native["executions"][0]["id"], m)
        self.assertIs(native["jobs"][jid]["enabled"], True, m)
        calls = [tuple(call) for call in native["calls"]]
        self.assertIn(("resume", jid), calls, m)
        self.assertIn(("run", jid), calls, m)
        self.assertNotIn(("pause", jid), calls, m)
        self.assertEqual(native["effects"], [], m)
        return claim, accepted, jid, native

    def test_h3_control_surviving_owner_pauses_after_acceptance_and_follower_joins(self):
        h = self.h
        owner = h.call("first", mode="background")
        native = process_support.snapshot(self.root)
        claim = claim_row(self.root, self.sid)
        follower = h.call("follower", mode="background")
        after = process_support.snapshot(self.root)
        self.record(owner=owner, native_after_owner=native, claim_after_owner=claim,
                    follower=follower, native_after_follower=after,
                    claim_after_follower=claim_row(self.root, self.sid))
        m = self.msg()
        self.assertNotIn("error", owner, m)
        jid = owner["result"]["cron_job_id"]
        self.assertEqual(owner["result"]["one_shot"],
                         {"job_id": jid, "consumed": "paused", "execution_mode": "background"}, m)
        self.assertIs(native["jobs"][jid]["enabled"], False, m)
        self.assertEqual([e["status"] for e in native["executions"]], ["running"], m)
        self.assertEqual((claim["phase"], native["effects"]), ("background", []), m)
        self.assertNotEqual(follower["pid"], owner["pid"], m)
        self.assertNotIn("error", follower, m)
        self.assertIs(follower["result"].get("joined"), True, m)
        self.assertEqual(follower["result"]["dispatch"], owner["result"]["dispatch"], m)
        self.assertEqual(claim_row(self.root, self.sid), claim, m)
        self.assertIs(after["jobs"][jid]["enabled"], False, m)

    def test_h3_real_owner_death_after_accepted_reply_exposes_or_reconciles_the_disable_obligation(self):
        claim, accepted, jid, before = self.dead_owner()
        follower = self.h.call("follower", mode="background")
        after = process_support.snapshot(self.root)
        claim_after = claim_row(self.root, self.sid)
        result = follower.get("result", {})
        stripped = json.dumps({k: v for k, v in result.items() if k != "dispatch"}, sort_keys=True)
        job_enabled = after["jobs"][jid]["enabled"] if jid in after["jobs"] else None
        disabled_by_follower = job_enabled is False
        exposed = bool(OBLIGATION.search(stripped))
        self.record(follower=follower, follower_reply_without_raw_dispatch=stripped,
                    native_after_follower=after, claim_after_follower=claim_after,
                    job_enabled_after=job_enabled, disabled_by_follower=disabled_by_follower,
                    obligation_exposed=exposed)
        m = self.msg()
        # Ownership stays unresolved: no completion is inferred from death, time or pause.
        self.assertNotIn("error", follower, m)
        self.assertIs(result.get("joined"), True, m)
        self.assertEqual(result.get("cron_job_id"), jid, m)
        self.assertEqual(result.get("dispatch"), accepted, m)
        self.assertIn(result.get("refresh_state"), ("background", "unresolved"), m)
        self.assertIsNotNone(claim_after, m)
        self.assertEqual((claim_after["token"], claim_after["cron_job_id"]), (claim["token"], jid), m)
        self.assertIn(claim_after["phase"], ("background", "unresolved"), m)
        self.assertEqual([e["status"] for e in after["executions"]], ["running"], m)
        self.assertEqual(after["effects"], [], m)
        self.assertEqual(sum(call[0] == "run" for call in after["calls"]), 1, m)
        self.assertEqual(sum(call[0] == "create" for call in after["calls"]), 1, m)
        self.assertFalse([call for call in after["calls"] if call[0] in ("remove", "cancel") and call[1] == jid], m)
        # Target: the unreported obligation. Reconcile (verified safe disable) or expose it truthfully.
        self.assertTrue(disabled_by_follower or exposed, m)
        if job_enabled is True:
            self.assertIsNone(CLAIMS_DISABLED.search(stripped), m)  # never claim a disable that did not happen


# --------------------------------------------------------------------------------------
# H4: refused delete while feed work is queued or running
# --------------------------------------------------------------------------------------
class FeedHold:
    """Holds real feed workers inside the pinned synthetic HTTPS response, keyed by response tag."""

    def __init__(self):
        self.entered, self.release = {}, {}

    def expect(self, tag):
        self.entered[tag], self.release[tag] = threading.Event(), threading.Event()

    def hook(self, response):
        self.entered[response.tag].set()
        if not self.release[response.tag].wait(BOUNDED):
            raise TimeoutError("feed hold was never released")

    def release_all(self):
        for event in self.release.values():
            event.set()


class RefusedDeleteTests(InProcessCase):
    def setUp(self):
        super().setUp()
        self.hold, self.gate, self.threads = FeedHold(), threading.Event(), []
        self.addCleanup(self.drain)

    def drain(self):
        self.hold.release_all()
        self.gate.set()
        for thread in self.threads:
            thread.join(BOUNDED + 3)
        alive = [t.name for t in self.threads if t.is_alive()]
        if alive:
            raise AssertionError(f"owned feed worker threads did not exit: {alive}")

    @staticmethod
    def tagged(tag):
        payload = (f"<rss version='2.0'><channel><item><guid>h4-{tag}</guid>"
                   f"<title>Held {tag}</title></item></channel></rss>").encode()
        response = Response(body=payload)
        response.tag = tag
        return response

    def space(self):
        fx = self.fx
        sid = fx.make(handler="feed")
        link = fx.schedule(sid, kind="feed")["link"]
        fx.records.put(sid, "items", "keep", {"note": "mine"}, actor="user", base_rev=None)
        return {"sid": sid, "link": link, "job": fx.cron.get_job(link["cron_job_id"]),
                "session": fx.sessions.open_session(sid)["session"]}

    def start(self, sid):
        before = set(threading.enumerate())
        run = self.fx.runs.start_refresh(sid, trigger="manual", actor="user")
        self.threads.extend(t for t in threading.enumerate() if t not in before)
        return run

    def state(self, space):
        fx, sid = self.fx, space["sid"]
        with fx.db.read() as conn:
            row = conn.execute("SELECT status,head_rev,created_at FROM spaces WHERE id=?", (sid,)).fetchone()
            runs = [dict(r) for r in conn.execute(
                "SELECT id,status,error,detail FROM runs WHERE space=? ORDER BY queued_at,rowid", (sid,))]
            open_sessions = conn.execute(
                "SELECT count(*) FROM sessions WHERE id=? AND space=? AND closed_at IS NULL",
                (space["session"], sid)).fetchone()[0]
            record_count = conn.execute("SELECT count(*) FROM records WHERE space=?", (sid,)).fetchone()[0]
        for run in runs:
            run["detail"] = json.loads(run["detail"])
        state = {"space": dict(row) if row else None, "runs": runs, "open_sessions": open_sessions,
                 "record_count": record_count, "records": None, "files": None, "link": None,
                 "link_job": fx.cron.get_job(space["link"]["cron_job_id"])}
        if row:
            state["records"] = fx.records.query(sid, "items", limit=2000)["records"]
            state["files"] = fx.core.list_files(sid)
            state["link"] = fx.upkeep.get_upkeep(sid)["link"]
        return state

    def settle(self, run_id):
        deadline = time.monotonic() + BOUNDED
        while time.monotonic() < deadline:
            with self.fx.db.read() as conn:
                row = conn.execute("SELECT status FROM runs WHERE id=?", (run_id,)).fetchone()
            if row is None or row["status"] not in ("queued", "running"):
                return
            time.sleep(0.02)
        self.fail(f"run {run_id} never reached a terminal state: {self.msg()}")

    def scenario(self, *, kind, refuse, foreign):
        """kind: running (worker held in the synthetic HTTPS response) or queued (worker gated before start)."""
        fx, ctx = self.fx, self.ctx
        data = self.obs["scenario"] = {"kind": kind, "refuse_delete": refuse, "foreign": foreign}
        target = self.space()
        other = self.space() if foreign else None
        if kind == "running":
            responses = []
            if foreign:
                self.hold.expect("foreign")
                responses.append(self.tagged("foreign"))
            self.hold.expect("target")
            responses.append(self.tagged("target"))
            fx.transport(responses, on_response=self.hold.hook)
        else:
            fx.transport([self.tagged("target")])
            original_work = fx.runs._work

            def gated(run_id, upkeep):
                if not self.gate.wait(BOUNDED):
                    raise TimeoutError("queued feed worker was never released")
                return original_work(run_id, upkeep)

            self.stack.enter_context(patch.object(fx.runs, "_work", side_effect=gated))
        runs = {}
        if foreign:
            runs["foreign"] = self.start(other["sid"])
            self.assertTrue(self.hold.entered["foreign"].wait(BOUNDED), self.msg())
        runs["target"] = self.start(target["sid"])
        if kind == "running":
            self.assertTrue(self.hold.entered["target"].wait(BOUNDED), self.msg())
        data["runs_started"] = runs
        data["before"] = {"target": self.state(target), "foreign": self.state(other) if other else None}
        refusals = []
        original = ctx.dispatch_tool

        def refuse_link_removal(name, args):
            if args["action"] == "remove" and args.get("job_id") == target["link"]["cron_job_id"]:
                reply = {"success": False, "error": "Injected delete removal refusal"}
                refusals.append(reply)
                return json.dumps(reply)
            return original(name, args)

        def attempt():
            try:
                return {"result": fx.projects.delete_space(target["sid"], actor="user", confirm=target["sid"])}
            except fx.core.SpacesError as exc:
                return {"error": exc.to_dict()}

        try:
            if refuse:
                with patch.object(ctx, "dispatch_tool", side_effect=refuse_link_removal):
                    data["delete"] = attempt()
            else:
                data["delete"] = attempt()
            data["refusals"] = refusals
            data["after_delete"] = {"target": self.state(target),
                                    "foreign": self.state(other) if other else None}
        finally:
            self.hold.release_all()
            self.gate.set()
            for thread in self.threads:
                thread.join(BOUNDED + 3)
        for key, run in runs.items():
            self.settle(run["id"])
        data["workers_alive"] = [t.name for t in self.threads if t.is_alive()]
        data["final"] = {"target": self.state(target), "foreign": self.state(other) if other else None}
        data["target_sid"], data["foreign_sid"] = target["sid"], other["sid"] if other else None
        return data

    def assert_refused(self, data):
        m = self.msg()
        self.assertEqual(data["workers_alive"], [], m)
        self.assertEqual(len(data["refusals"]), 1, m)
        error = data["delete"].get("error", {})
        self.assertEqual((error.get("code"), error.get("reason")), ("blocked", "native_refused"), m)
        return m

    @staticmethod
    def source_records(state):
        return [r["id"] for r in (state["records"] or []) if r["id"].startswith("src_")]

    def test_h4_control_refused_delete_preserves_space_session_data_link_and_foreign_work(self):
        data = self.scenario(kind="running", refuse=True, foreign=True)
        m = self.assert_refused(data)
        before, after = data["before"]["target"], data["after_delete"]["target"]
        self.assertEqual(after["space"], before["space"], m)
        self.assertEqual((before["open_sessions"], after["open_sessions"]), (1, 1), m)
        self.assertEqual(after["records"], before["records"], m)
        self.assertEqual(after["files"], before["files"], m)
        self.assertEqual(after["link"], before["link"], m)
        self.assertEqual(after["link_job"], before["link_job"], m)
        foreign_before, foreign_after = data["before"]["foreign"], data["after_delete"]["foreign"]
        self.assertEqual([r["status"] for r in foreign_after["runs"]], ["running"], m)
        self.assertNotIn("cancel_reason", foreign_after["runs"][0]["detail"], m)
        self.assertEqual(foreign_after["space"], foreign_before["space"], m)
        self.assertEqual(foreign_after["link_job"], foreign_before["link_job"], m)
        final_foreign = data["final"]["foreign"]
        self.assertEqual([r["status"] for r in final_foreign["runs"]], ["succeeded"], m)
        self.assertEqual(len(self.source_records(final_foreign)), 1, m)
        self.assertIsNotNone(data["final"]["target"]["space"], m)

    def test_h4_control_successful_delete_removes_space_and_leaves_foreign_work_untouched(self):
        data = self.scenario(kind="running", refuse=False, foreign=True)
        m = self.msg()
        self.assertEqual(data["workers_alive"], [], m)
        self.assertEqual(data["refusals"] if "refusals" in data else [], [], m)
        self.assertTrue(data["delete"]["result"]["deleted"], m)
        self.assertTrue(data["delete"]["result"]["removed"]["upkeep"], m)
        for stage in ("after_delete", "final"):
            target = data[stage]["target"]
            self.assertIsNone(target["space"], f"{stage}: {m}")
            self.assertEqual((target["runs"], target["record_count"], target["open_sessions"]),
                             ([], 0, 0), f"{stage}: {m}")
            self.assertIsNone(target["link_job"], f"{stage}: {m}")
        foreign_after = data["after_delete"]["foreign"]
        self.assertEqual([r["status"] for r in foreign_after["runs"]], ["running"], m)
        self.assertNotIn("cancel_reason", foreign_after["runs"][0]["detail"], m)
        self.assertEqual([r["status"] for r in data["final"]["foreign"]["runs"]], ["succeeded"], m)

    def test_h4_refused_delete_does_not_cancel_running_feed_work(self):
        data = self.scenario(kind="running", refuse=True, foreign=False)
        m = self.assert_refused(data)
        self.assertEqual([r["status"] for r in data["before"]["target"]["runs"]], ["running"], m)
        runs = data["after_delete"]["target"]["runs"]
        self.assertEqual([r["status"] for r in runs], ["running"], m)
        self.assertNotIn("cancel_reason", runs[0]["detail"], m)
        final = data["final"]["target"]
        self.assertEqual([r["status"] for r in final["runs"]], ["succeeded"], m)
        self.assertEqual(len(self.source_records(final)), 1, m)

    def test_h4_refused_delete_does_not_cancel_queued_feed_work(self):
        data = self.scenario(kind="queued", refuse=True, foreign=False)
        m = self.assert_refused(data)
        self.assertEqual([r["status"] for r in data["before"]["target"]["runs"]], ["queued"], m)
        runs = data["after_delete"]["target"]["runs"]
        self.assertEqual([r["status"] for r in runs], ["queued"], m)
        self.assertNotIn("cancel_reason", runs[0]["detail"], m)
        final = data["final"]["target"]
        self.assertEqual([r["status"] for r in final["runs"]], ["succeeded"], m)
        self.assertEqual(len(self.source_records(final)), 1, m)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--oracle-worker":
        oracle_worker(Path(sys.argv[2]), sys.argv[3], sys.argv[4], sys.argv[5])
    else:
        unittest.main()
