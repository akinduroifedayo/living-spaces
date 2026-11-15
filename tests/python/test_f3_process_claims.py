"""Process-level Refresh contracts. Native cron is a shared, file-backed public-tool double."""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import importlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests.python.review_customization_support import AGENT_PROMPT, SyntheticContext, SyntheticCron


def wait_for(predicate, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.02)
    raise TimeoutError("Process fixture did not reach its owned barrier")


@contextmanager
def native_store(root):
    with (root / "native.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = root / "native.json"
        state = json.loads(path.read_text()) if path.exists() else {
            "jobs": {}, "executions": [], "calls": [], "serial": 0, "effects": []}
        try:
            yield state
        finally:
            path.write_text(json.dumps(state))


def snapshot(root):
    with native_store(root) as state:
        return json.loads(json.dumps(state))


class SharedCronContext(SyntheticContext):
    def __init__(self, root, core, label, mode):
        super().__init__()
        self.root, self.core, self.label, self.mode = root, core, label, mode

    def current_cron_execution(self):
        (self.root / (self.label + ".admitted")).touch()
        return None

    def dispatch_tool(self, name, args):
        assert name == "cronjob_manage", name
        with native_store(self.root) as state:
            cron = SyntheticCron()
            for key in ("jobs", "executions", "calls", "serial"):
                setattr(cron, key, state[key])
            self.cron = cron
            action, jid = args["action"], args.get("job_id")
            if action != "run":
                if action == "remove":
                    cron.cancel_job_run(jid, reason="Native removal cancels active execution")
                reply = super().dispatch_tool(name, args)
                state.update({key: getattr(cron, key)
                              for key in ("jobs", "executions", "calls", "serial")})
                return reply
            cron.calls.append(("run", jid))
            job = cron.get_job(jid)
            if job is None:
                return json.dumps({"success": False, "error": "Job not found"})
            if not job["enabled"]:
                return json.dumps({"success": True, "job": dict(self.format_job(job),
                    executed=False, execution_success=False,
                    execution_skipped="Job is paused/disabled; resume it before running.")})
            execution = cron.execution(jid, status="running")
        if self.mode == "background":
            return json.dumps({"success": True, "job": dict(self.format_job(job), executed=True,
                execution_mode="background", delegation_id=execution["id"])})
        wait_for(lambda: (self.root / "inline-release").exists())
        self.finish(execution["id"])
        job = snapshot(self.root)["jobs"][jid]
        return json.dumps({"success": True, "job": dict(self.format_job(job), executed=True,
            execution_mode="inline", execution_success=True, execution_id=execution["id"])})

    def finish(self, execution_id):
        state = snapshot(self.root)
        execution = next(e for e in state["executions"] if e["id"] == execution_id)
        if execution["status"] != "running":
            return
        jid = execution["job_id"]
        sid = state["jobs"][jid]["name"].split(":")[1]
        path = "process-effect-" + execution_id + ".json"
        marker = {"space": sid, "job_id": jid, "execution_id": execution_id}
        written = self.core.write_files(sid, files={path: json.dumps(marker)},
            author="agent:process-double", summary="Synthetic native execution effect")
        observed = json.loads(self.core.read_file(sid, path)["text"])
        stamp = datetime.now(timezone.utc).isoformat()
        with native_store(self.root) as state:
            entry = next(e for e in state["executions"] if e["id"] == execution_id)
            entry.update(status="completed", finished_at=stamp)
            state["effects"].append({**observed, "rev": written["rev"]})
            state["jobs"][jid].update(last_run_at=stamp, last_status="ok", last_error=None)


def worker(root, label, operation, mode, offset):
    sys.path.insert(0, str(ROOT / "src/living-spaces"))
    core = importlib.import_module("living_spaces_core")

    ctx = SharedCronContext(root, core, label, mode)
    core.configure_context(ctx)
    real_clock = time.time
    record = {"pid": os.getpid(), "environment": {key: os.environ.get(key)
        for key in ("HOME", "HERMES_HOME", "TMPDIR", "LIVING_SPACES_DB")},
        "isolated": sys.flags.isolated, "no_bytecode": sys.dont_write_bytecode,
        "clock_offset": offset, "db_path": str(core.db.db_path().resolve()),
        "hermes_home": str(core.db.hermes_home().resolve())}
    with patch("time.time", side_effect=lambda: real_clock() + offset):
        record["observed_wall_time"] = time.time()
        try:
            if operation == "seed":
                result = core.create_space("Process Refresh", owner="Review", author="user",
                    files={"index.html": "<h1>Process Refresh</h1>"},
                    manifest={"upkeep": {"handler": "agent", "prompt": AGENT_PROMPT}})
                (root / "space").write_text(result["id"])
            else:
                sid = (root / "space").read_text()
                if operation == "executor":
                    active = wait_for(lambda: [e for e in snapshot(root)["executions"]
                                               if e["status"] == "running"])
                    (root / "executor-active").write_text(json.dumps(active))
                    wait_for(lambda: (root / "background-release").exists())
                    for execution in snapshot(root)["executions"]:
                        ctx.finish(execution["id"])
                    result = {"finished": True}
                elif operation == "remove":
                    result = core.upkeep_action(sid, "remove", actor="user")
                elif operation == "inspect":
                    result = {"markers": [json.loads(core.read_file(sid, f["path"])["text"])
                        for f in core.list_files(sid) if f["path"].startswith("process-effect-")]}
                elif operation == "direct":
                    result = core.upkeep.refresh_now(sid, {"handler": "agent", "prompt": AGENT_PROMPT},
                                                    actor="agent:process")
                else:
                    result = core.start_refresh(sid, trigger="chat" if label == "second" else "manual",
                                                actor="agent:process")
            record["result"] = result
        except core.SpacesError as exc:
            record["error"] = exc.to_dict()
    (root / (label + ".json")).write_text(json.dumps(record))


class F3ProcessClaimsTests(unittest.TestCase):
    def setUp(self):
        base = Path(os.environ["F3_PROCESS_TEST_TMPDIR"]).resolve()
        if not base.is_relative_to(Path("/Volumes/Expansion")):
            raise ValueError("F3_PROCESS_TEST_TMPDIR must be an owned directory on Expansion")
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="f3-process-", dir=base)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("home", "hermes", "tmp"):
            (self.root / name).mkdir()
        self.env = {"HOME": str(self.root / "home"), "HERMES_HOME": str(self.root / "hermes"),
            "TMPDIR": str(self.root / "tmp"), "LIVING_SPACES_DB": str(self.root / "spaces.db"),
            "PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"}
        self.children = []
        self.addCleanup(self.stop_children)
        self.call("seed", "seed")

    def stop_children(self):
        for child, _ in self.children:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGKILL)
            child.wait(timeout=5)

    def spawn(self, label, operation="refresh", mode="inline", offset=0):
        with (self.root / (label + ".log")).open("w") as log:
            child = subprocess.Popen([sys.executable, "-I", "-B", str(Path(__file__).resolve()),
                "--worker", str(self.root), label, operation, mode, str(offset)],
                cwd=self.root, env=self.env, stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True)
        self.children.append((child, label))
        return child

    def joined(self, child, label):
        self.assertEqual(child.wait(timeout=20), 0, (self.root / (label + ".log")).read_text())
        record = json.loads((self.root / (label + ".json")).read_text())
        self.assertEqual(record["environment"], {key: self.env[key] for key in record["environment"]})
        self.assertEqual(record["db_path"], self.env["LIVING_SPACES_DB"])
        self.assertEqual(record["hermes_home"], self.env["HERMES_HOME"])
        self.assertEqual((record["isolated"], record["no_bytecode"]), (1, True))
        return record

    def call(self, label, operation="refresh", mode="inline", offset=0):
        return self.joined(self.spawn(label, operation, mode, offset), label)

    def observe(self, **values):
        message = json.dumps({"case": self.id(), **values}, sort_keys=True)
        print(message, flush=True)
        return message

    def assert_single_overlap(self, first, second, state, message):
        self.assertNotIn("error", first, message)
        self.assertNotIn("error", second, message)
        jid = first["result"]["cron_job_id"]
        self.assertEqual(second["result"]["cron_job_id"], jid, message)
        self.assertEqual(sum(call[0] == "create" for call in state["calls"]), 1, message)
        self.assertEqual(sum(call[0] == "run" for call in state["calls"]), 1, message)
        self.assertEqual(len(state["executions"]), 1, message)

    def test_overlapping_processes_share_one_native_execution_and_later_refresh_runs(self):
        first_process = self.spawn("first")
        wait_for(lambda: snapshot(self.root)["executions"])
        second_process = self.spawn("second")
        wait_for(lambda: (self.root / "second.admitted").exists())
        try:
            wait_for(lambda: (self.root / "second.json").exists()
                     or len(snapshot(self.root)["executions"]) == 2, timeout=2)
        except TimeoutError:
            pass  # A follower may wait for the owner's result instead of returning immediately.
        finally:
            (self.root / "inline-release").touch()
        first, second = self.joined(first_process, "first"), self.joined(second_process, "second")
        overlap = snapshot(self.root)
        markers = self.call("inspect", "inspect")
        later = self.call("later")
        after = snapshot(self.root)
        message = self.observe(first=first, second=second, overlap=overlap, markers=markers,
                               later=later, after=after)
        self.assertNotIn("error", later, message)
        self.assertEqual(len(after["executions"]) - len(overlap["executions"]), 1, message)
        self.assertEqual(len(after["effects"]) - len(overlap["effects"]), 1, message)
        self.assertNotEqual(first["pid"], second["pid"], message)
        self.assert_single_overlap(first, second, overlap, message)
        self.assertEqual(len(overlap["effects"]), 1, message)
        self.assertEqual(markers["result"]["markers"], [{key: overlap["effects"][0][key]
            for key in ("space", "job_id", "execution_id")}], message)

    def background_owner(self):
        executor = self.spawn("executor", "executor")
        owner = self.call("first", mode="background")
        wait_for(lambda: (self.root / "executor-active").exists())
        self.assertIsNone(executor.poll())
        state = snapshot(self.root)
        self.assertNotIn("error", owner, owner)
        jid = owner["result"]["cron_job_id"]
        self.assertEqual((state["jobs"][jid]["enabled"], state["jobs"][jid]["last_run_at"]),
                         (False, None), state)
        self.assertEqual([e["status"] for e in state["executions"]], ["running"], state)
        return executor, owner

    def test_background_claim_outlives_dispatch_process_and_elapsed_wall_time(self):
        executor, owner = self.background_owner()
        second = self.call("second", "direct", mode="background", offset=3600)
        active = snapshot(self.root)
        executor_alive = executor.poll() is None
        (self.root / "background-release").touch()
        completed = self.joined(executor, "executor")
        settled = snapshot(self.root)
        (self.root / "inline-release").touch()
        later = self.call("later")
        after = snapshot(self.root)
        message = self.observe(owner=owner, second=second, active=active, executor_alive=executor_alive,
                               completed=completed, settled=settled, later=later, after=after)
        self.assertTrue(executor_alive, message)
        self.assertNotEqual(completed["pid"], owner["pid"], message)
        self.assertNotEqual(second["pid"], owner["pid"], message)
        self.assertGreaterEqual(second["observed_wall_time"] - owner["observed_wall_time"], 3600, message)
        self.assertNotIn("error", later, message)
        self.assertEqual(len(after["executions"]) - len(settled["executions"]), 1, message)
        self.assertEqual(len(after["effects"]) - len(settled["effects"]), 1, message)
        self.assert_single_overlap(owner, second, active, message)
        self.assertEqual(active["effects"], [], message)
        self.assertEqual([e["status"] for e in settled["executions"]], ["completed"], message)
        self.assertEqual(len(settled["effects"]), 1, message)

    def test_successful_remove_cancels_native_work_and_allows_later_refresh_control(self):
        executor, owner = self.background_owner()
        removed = self.call("remove", "remove")
        absent = snapshot(self.root)
        (self.root / "inline-release").touch()
        later = self.call("later")
        (self.root / "background-release").touch()
        self.joined(executor, "executor")
        after = snapshot(self.root)
        message = self.observe(owner=owner, removed=removed, absent=absent, later=later, after=after)
        self.assertNotIn("error", removed, message)
        self.assertEqual(absent["jobs"], {}, message)
        self.assertEqual([e["status"] for e in absent["executions"]], ["cancelled"], message)
        self.assertEqual(absent["effects"], [], message)
        self.assertNotIn("error", later, message)
        self.assertNotEqual(later["result"]["cron_job_id"], owner["result"]["cron_job_id"], message)
        self.assertEqual([e["status"] for e in after["executions"]], ["cancelled", "completed"], message)
        self.assertEqual([e["job_id"] for e in after["effects"]], [later["result"]["cron_job_id"]], message)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        worker(Path(sys.argv[2]), sys.argv[3], sys.argv[4], sys.argv[5], int(sys.argv[6]))
    else:
        unittest.main()
