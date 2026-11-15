"""Released-core upgrades with real SQLite and SYNTHETIC file-backed public cron.

Parent execution requires F3_LEGACY_SOURCE, a clean checkout of RELEASED_SHA,
and F3_PROCESS_TEST_TMPDIR on Expansion. No native completion is synthesized.
"""
from contextlib import nullcontext
import hashlib
import importlib
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
import traceback
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
RELEASED_SHA = "4aea12db5375b30e90b5e0fa8f7d12ad7e0fdf98"


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True))


def sql_state(root, identity):
    with sqlite3.connect((root / "spaces.db").as_uri() + "?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        tables = [row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        result = {"tables": tables, "spaces": {}, "claims": None}
        for sid in (identity["space"], identity["foreign"]):
            row = conn.execute("SELECT * FROM spaces WHERE id=?", (sid,)).fetchone()
            result["spaces"][sid] = {
                "space": dict(row) if row else None,
                "links": [dict(r) for r in conn.execute(
                    "SELECT * FROM upkeep_links WHERE space=?", (sid,))],
                "revisions": [dict(r) for r in conn.execute(
                    "SELECT * FROM revisions WHERE space=? ORDER BY rev", (sid,))],
                "records": [dict(r) for r in conn.execute(
                    "SELECT * FROM records WHERE space=? ORDER BY collection,id", (sid,))],
                "runs": [dict(r) for r in conn.execute(
                    "SELECT * FROM runs WHERE space=? ORDER BY id", (sid,))],
            }
        if "refresh_claims" in tables:
            result["claims"] = [dict(r) for r in conn.execute(
                "SELECT * FROM refresh_claims ORDER BY space")]
        return result


def worker(root, source, operation):
    sys.path.insert(0, str(ROOT))
    # Import the support module, not its discoverable TestCase class.
    from tests.python import test_lifecycle_atomic as lifecycle_support
    from tests.python.review_customization_support import SyntheticContext, AGENT_PROMPT

    journal = root / (operation + "-native.jsonl")

    class RecordedContext(SyntheticContext):
        def dispatch_tool(self, name, args):
            with journal.open("a") as stream:
                stream.write(json.dumps({"event": "entered", "name": name, "args": args}) + "\n")
            try:
                reply = super().dispatch_tool(name, args)
            except Exception as exc:
                with journal.open("a") as stream:
                    stream.write(json.dumps({"event": "raised", "type": type(exc).__name__,
                                             "message": str(exc), "args": args}) + "\n")
                raise
            with journal.open("a") as stream:
                stream.write(json.dumps({"event": "returned", "args": args,
                                         "reply": json.loads(reply)}) + "\n")
            return reply

    cron = lifecycle_support.SharedCron(root / "native-jobs.db")
    ctx = RecordedContext(cron)
    record_path = root / (operation + "-result.json")
    record = {"pid": os.getpid(), "operation": operation,
              "isolated": sys.flags.isolated, "no_bytecode": sys.dont_write_bytecode,
              "environment": {key: os.environ.get(key) for key in
                              ("HOME", "HERMES_HOME", "LIVING_SPACES_DB", "TMPDIR")}}

    def snapshot(identity):
        return {"jobs": {job["id"]: job for job in cron.list_jobs(include_disabled=True)},
                "sql": sql_state(root, identity)}

    def checkpoint():
        record["native_events"] = [json.loads(line) for line in journal.read_text().splitlines()] if journal.exists() else []
        save(record_path, record)

    try:
        identity = {}
        if not operation.startswith("old"):
            identity = json.loads((root / "identity.json").read_text())
            record["before_import"] = snapshot(identity)
            checkpoint()
        sys.path.insert(0, str(source / "src/living-spaces"))
        core = importlib.import_module("living_spaces_core")
        if core.__file__ is None:
            raise RuntimeError("Core must resolve to a source file")
        record["core_file"] = str(Path(core.__file__).resolve())
        record["observed_wall_time"] = time.time()
        record["db_path"] = str(core.db.db_path().resolve())
        record["hermes_home"] = str(core.db.hermes_home().resolve())
        core.configure_context(ctx)

        def attempt(label, function):
            try:
                value = {"result": function()}
            except core.SpacesError as exc:
                value = {"error": exc.to_dict()}
            record[label] = {"outcome": value, "state": snapshot(identity)}
            checkpoint()
            return value

        if operation.startswith("old"):
            def create(name):
                return core.create_space(name, owner="Upgrade test", author="agent",
                    files={"index.html": "<h1>Legacy demo</h1>"},
                    manifest={"upkeep": {"handler": "agent", "prompt": AGENT_PROMPT}})["id"]

            sid, foreign = create("Legacy pending Space"), create("Foreign Space")
            foreign_job = core.schedule_upkeep(foreign, kind="agent", cadence="0 * * * *",
                timezone="UTC", prompt=AGENT_PROMPT, actor="user")["link"]["cron_job_id"]
            identity = {"space": sid, "foreign": foreign, "foreign_job": foreign_job,
                        "session": core.open_session(sid)["session"]}
            save(root / "identity.json", identity)
            record["setup"] = "core.start_refresh(sid, trigger='manual', actor='user')"
            if operation == "old-crash":
                def crash_before_trigger(jid):
                    identity["legacy_job"] = jid
                    save(root / "identity.json", identity)
                    record["boundary"] = "owned released process exits after persisted resume, before native trigger"
                    record["old_state"] = snapshot(identity)
                    checkpoint()
                    print(json.dumps(record), flush=True)
                    os._exit(73)

                cron.trigger_job = crash_before_trigger
            record["result"] = core.start_refresh(sid, trigger='manual', actor='user')
            identity["legacy_job"] = record["result"]["cron_job_id"]
            save(root / "identity.json", identity)
            record["old_state"] = snapshot(identity)
        elif operation in ("admission", "admission-aged"):
            sid = identity["space"]
            real_clock = time.time
            offset = 3600 if operation == "admission-aged" else 0
            clock = patch("time.time", side_effect=lambda: real_clock() + offset) if offset else nullcontext()
            with clock:
                record["clock_offset"] = offset
                record["observed_wall_time"] = time.time()
                attempt("refresh", lambda: core.start_refresh(sid, trigger='manual', actor='user'))
            attempt("remove", lambda: core.upkeep_action(sid, "remove", actor="user"))
            attempt("later", lambda: core.start_refresh(sid, trigger='manual', actor='user'))
        elif operation == "delete":
            sid = identity["space"]
            with patch.object(cron, "remove_job", side_effect=OSError("synthetic remove refusal")):
                attempt("refused_delete", lambda: core.delete_space(sid, actor="user", confirm=sid))
            attempt("retry_delete", lambda: core.delete_space(sid, actor="user", confirm=sid))
        elif operation == "archive":
            sid = identity["space"]
            with patch.object(ctx, "dispatch_tool", side_effect=ImportError("synthetic unavailable")):
                attempt("refused_archive", lambda: core.set_status(sid, "archived", actor="user"))
            attempt("frame_after_refusal", lambda: core.require(sid, identity["session"]))
            attempt("retry_archive", lambda: core.set_status(sid, "archived", actor="user"))
            attempt("unarchive", lambda: core.set_status(sid, "active", actor="user"))
        else:
            raise ValueError(operation)
    except Exception:
        record["fatal"] = traceback.format_exc()
        raise
    finally:
        checkpoint()
        print(json.dumps(record), flush=True)


class F3LegacyUpgradeTests(unittest.TestCase):
    def setUp(self):
        supplied = os.environ.get("F3_PROCESS_TEST_TMPDIR")
        if not supplied:
            raise RuntimeError("Set F3_PROCESS_TEST_TMPDIR to owned Expansion scratch; no default or skip")
        base = Path(supplied).resolve()
        if not base.is_relative_to(Path("/Volumes/Expansion")):
            raise ValueError("F3_PROCESS_TEST_TMPDIR must resolve under /Volumes/Expansion")
        base.mkdir(parents=True, exist_ok=True)
        self.root = Path(tempfile.mkdtemp(prefix="f3-legacy-upgrade-", dir=base))
        for name in ("home", "hermes", "tmp"):
            (self.root / name).mkdir()
        self.env = {key: os.environ[key] for key in
                    ("PATH", "LANG", "USER", "LOGNAME", "SHELL") if key in os.environ}
        self.env.setdefault("PATH", "/usr/bin:/bin")
        self.env.setdefault("LANG", "C")
        self.env.update(HOME=str(self.root / "home"), HERMES_HOME=str(self.root / "hermes"),
                        TMPDIR=str(self.root / "tmp"), LIVING_SPACES_DB=str(self.root / "spaces.db"))
        self.children = []
        self.executions = []
        self.addCleanup(self.stop_children)
        supplied_source = os.environ.get("F3_LEGACY_SOURCE")
        if not supplied_source:
            raise RuntimeError("Set F3_LEGACY_SOURCE to a clean checkout of " + RELEASED_SHA +
                               "; no fetch, install, skip, or manufactured legacy state")
        self.source = Path(supplied_source).resolve()
        self.source_before = self.source_identity("before")
        self.addCleanup(self.check_source_untouched)

    def source_identity(self, label):
        commands = {}
        for key, args in (("root", ["rev-parse", "--show-toplevel"]),
                          ("sha", ["rev-parse", "HEAD"]),
                          ("dirty", ["status", "--porcelain=v1", "--untracked-files=all"] )):
            result = subprocess.run(["git", "--no-optional-locks", "-C", str(self.source), *args],
                cwd=self.root, env=self.env, capture_output=True, text=True, timeout=20)
            commands[key] = {"argv": result.args, "exit": result.returncode,
                             "stdout": result.stdout, "stderr": result.stderr}
        hashes = {str(p.relative_to(self.source)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in sorted((self.source / "src/living-spaces").rglob("*")) if p.is_file()}
        value = {"commands": commands, "hashes": hashes}
        save(self.root / ("released-source-" + label + ".json"), value)
        print(json.dumps({"case": self.id(), "source_check": label, "evidence": str(self.root),
                          "commands": commands}), flush=True)
        for command in commands.values():
            self.assertEqual(command["exit"], 0, value)
        self.assertEqual(Path(commands["root"]["stdout"].strip()).resolve(), self.source, value)
        self.assertEqual(commands["sha"]["stdout"].strip(), RELEASED_SHA, value)
        self.assertEqual(commands["dirty"]["stdout"], "", value)
        self.assertIn("src/living-spaces/living_spaces_core/__init__.py", hashes, value)
        return value

    def check_source_untouched(self):
        self.assertEqual(self.source_identity("after"), self.source_before)

    def stop_children(self):
        cleanup = []
        for child, label in self.children:
            alive = child.poll() is None
            if alive:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            cleanup.append({"pid": child.pid, "label": label, "killed_owned_group": alive,
                            "exit": child.wait(timeout=5)})
        save(self.root / "owned-process-cleanup.json", cleanup)

    def call(self, operation, source=None, expected_exit=0):
        source = source or ROOT
        argv = [sys.executable, "-I", "-B", str(Path(__file__).resolve()),
                "--worker", str(self.root), str(source), operation]
        with (self.root / (operation + ".stdout")).open("w") as out, \
                (self.root / (operation + ".stderr")).open("w") as err:
            child = subprocess.Popen(argv, cwd=self.root, env=self.env,
                                     stdout=out, stderr=err, start_new_session=True)
        self.children.append((child, operation))
        try:
            code = child.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self.executions.append({"pid": child.pid, "argv": argv, "timeout": True})
            save(self.root / "execution.json", self.executions)
            raise
        entry = {"pid": child.pid, "argv": argv, "exit": code,
                 "stdout": (self.root / (operation + ".stdout")).read_text(),
                 "stderr": (self.root / (operation + ".stderr")).read_text()}
        self.executions.append(entry)
        save(self.root / "execution.json", self.executions)
        path = self.root / (operation + "-result.json")
        record = json.loads(path.read_text()) if path.exists() else None
        print(json.dumps({"case": self.id(), "evidence": str(self.root),
                          "execution": entry, "observation": record}), flush=True)
        self.assertEqual(code, expected_exit, entry)
        if not isinstance(record, dict):
            self.fail("Worker did not preserve structured observations: " + json.dumps(entry))
        self.assertNotIn("fatal", record, record)
        self.assertEqual(record["pid"], child.pid, record)
        self.assertEqual((record["isolated"], record["no_bytecode"]), (1, True), record)
        self.assertEqual(record["core_file"], str(source / "src/living-spaces/living_spaces_core/__init__.py"), record)
        self.assertEqual(record["db_path"], self.env["LIVING_SPACES_DB"], record)
        self.assertEqual(record["hermes_home"], self.env["HERMES_HOME"], record)
        self.assertEqual(record["environment"], {key: self.env[key] for key in record["environment"]}, record)
        return record

    def observe(self, old, upgraded):
        identity = json.loads((self.root / "identity.json").read_text())
        value = {"case": self.id(), "evidence": str(self.root), "identity": identity,
                 "old": old, "upgraded": upgraded, "executions": self.executions,
                 "boundary": "real released/current core; SYNTHETIC file-backed public cron, not live native evidence"}
        save(self.root / "observations.json", value)
        message = json.dumps(value, sort_keys=True)
        print(message, flush=True)
        return identity, message

    def assert_legacy_setup(self, old, upgraded, identity, message, crash=False):
        sid, jid = identity["space"], identity["legacy_job"]
        state = old["old_state"]
        self.assertEqual(old["setup"], "core.start_refresh(sid, trigger='manual', actor='user')", message)
        self.assertNotIn("refresh_claims", state["sql"]["tables"], message)
        self.assertEqual(upgraded["before_import"], state, message)
        self.assertNotEqual(old["pid"], upgraded["pid"], message)
        job = state["jobs"][jid]
        self.assertEqual(job["name"], "living-spaces:" + sid + ":once", message)
        self.assertEqual(job["repeat"], 1, message)
        self.assertIs(job["enabled"], True, message)
        self.assertEqual(job["state"], "scheduled", message)
        self.assertIsNone(job["last_run_at"], message)
        self.assertIsNone(job["last_status"], message)
        self.assertEqual(state["sql"]["spaces"][sid]["links"], [], message)
        self.assertEqual(state["sql"]["spaces"][sid]["space"]["status"], "active", message)
        self.assertTrue(state["jobs"][identity["foreign_job"]]["enabled"], message)
        entered = [e["args"] for e in old["native_events"] if e["event"] == "entered"]
        returned = [e for e in old["native_events"] if e["event"] == "returned"]
        self.assertIn({"action": "resume", "job_id": jid}, entered, message)
        self.assertIn({"action": "run", "job_id": jid}, entered, message)
        self.assertTrue(any(e["args"] == {"action": "resume", "job_id": jid}
                            and e["reply"]["job"]["enabled"] is True for e in returned), message)
        if crash:
            self.assertEqual(self.executions[0]["exit"], 73, message)
            self.assertIn("before native trigger", old["boundary"], message)
            self.assertNotIn("manual_run_at", job, message)
            self.assertFalse(any(e["args"]["action"] == "run" for e in returned), message)
        else:
            self.assertEqual(self.executions[0]["exit"], 0, message)
            self.assertEqual(old["result"]["cron_job_id"], jid, message)
            self.assertTrue(job["manual_run_at"], message)
            dispatch = old["result"]["dispatch"]
            self.assertIs(dispatch["success"], True, message)
            self.assertNotIn("execution_success", dispatch["job"], message)

    def assert_foreign_unchanged(self, old, states, identity, message):
        sid, jid = identity["foreign"], identity["foreign_job"]
        for state in states:
            self.assertEqual(state["jobs"][jid], old["old_state"]["jobs"][jid], message)
            self.assertEqual(state["sql"]["spaces"][sid], old["old_state"]["sql"]["spaces"][sid], message)

    def admission_contract(self, crash=False):
        old = self.call("old-crash" if crash else "old", self.source, 73 if crash else 0)
        upgraded = self.call("admission-aged" if crash else "admission")
        identity, message = self.observe(old, upgraded)
        self.assert_legacy_setup(old, upgraded, identity, message, crash=crash)
        if crash:
            self.assertGreaterEqual(upgraded["observed_wall_time"] - old["observed_wall_time"], 3600, message)
        sid, jid = identity["space"], identity["legacy_job"]
        before = upgraded["before_import"]
        refreshed = upgraded["refresh"]
        removed, later = upgraded["remove"], upgraded["later"]
        self.assert_foreign_unchanged(old, [refreshed["state"], removed["state"], later["state"]], identity, message)
        # Check authorized recovery even when the preceding admission was unsafe.
        self.assertNotIn("error", removed["outcome"], message)
        self.assertEqual(set(removed["state"]["jobs"]), {identity["foreign_job"]}, message)
        self.assertEqual(removed["state"]["sql"]["spaces"][sid]["links"], [], message)
        self.assertFalse(any(c["space"] == sid for c in removed["state"]["sql"]["claims"] or []), message)
        self.assertNotIn("error", later["outcome"], message)
        result = later["outcome"]["result"]
        self.assertNotEqual(result["cron_job_id"], jid, message)
        self.assertIs(result["dispatch"]["success"], True, message)
        self.assertEqual(result["refresh_state"], "unresolved", message)
        self.assertEqual(set(later["state"]["jobs"]),
                         {identity["foreign_job"], result["cron_job_id"]}, message)
        self.assertIsNone(later["state"]["jobs"][result["cron_job_id"]]["last_run_at"], message)
        self.assertEqual(later["state"]["sql"]["spaces"][sid], before["sql"]["spaces"][sid], message)
        native_runs = [e for e in upgraded["native_events"] if e["event"] == "returned"
                       and e["args"] == {"action": "run", "job_id": result["cron_job_id"]}]
        self.assertEqual(len(native_runs), 1, message)
        self.assertEqual(result["dispatch"], native_runs[0]["reply"], message)
        error = refreshed["outcome"].get("error", {})
        self.assertEqual(error.get("code"), "blocked", message)
        self.assertIn("Upkeep Remove", json.dumps(error), message)
        self.assertEqual(refreshed["state"]["jobs"], before["jobs"], message)
        self.assertEqual(refreshed["state"]["sql"]["spaces"][sid], before["sql"]["spaces"][sid], message)
        events = upgraded["native_events"]
        remove_index = next(i for i, e in enumerate(events)
                            if e["event"] == "entered" and e["args"]["action"] == "remove")
        admission_actions = [e["args"]["action"] for e in events[:remove_index] if e["event"] == "entered"]
        self.assertTrue(all(action == "list" for action in admission_actions), message)

    def test_released_original_refresh_blocks_new_work_until_explicit_remove(self):
        self.admission_contract()

    def test_released_exit73_after_resume_does_not_authorize_new_refresh(self):
        self.admission_contract(crash=True)

    def test_released_original_refresh_remove_refusal_preserves_enabled_job_then_delete_retries(self):
        old = self.call("old", self.source)
        upgraded = self.call("delete")
        identity, message = self.observe(old, upgraded)
        self.assert_legacy_setup(old, upgraded, identity, message)
        sid, jid = identity["space"], identity["legacy_job"]
        refused, retry = upgraded["refused_delete"], upgraded["retry_delete"]
        self.assertEqual(refused["outcome"].get("error", {}).get("code"), "blocked", message)
        self.assertEqual(refused["state"]["sql"]["spaces"][sid]["space"]["status"], "active", message)
        self.assertEqual(refused["state"]["sql"]["spaces"][sid]["links"], [], message)
        self.assertIs(refused["state"]["jobs"][jid]["enabled"], True, message)
        self.assertEqual(refused["state"]["jobs"], old["old_state"]["jobs"], message)
        self.assertEqual(refused["state"]["sql"]["spaces"][sid], old["old_state"]["sql"]["spaces"][sid], message)
        self.assertNotIn("error", retry["outcome"], message)
        self.assertIs(retry["outcome"]["result"]["deleted"], True, message)
        self.assertIsNone(retry["state"]["sql"]["spaces"][sid]["space"], message)
        self.assertEqual(retry["state"]["sql"]["spaces"][sid]["links"], [], message)
        self.assertEqual(set(retry["state"]["jobs"]), {identity["foreign_job"]}, message)
        self.assert_foreign_unchanged(old, [refused["state"], retry["state"]], identity, message)
        mutations = [e["args"] for e in upgraded["native_events"]
                     if e["event"] == "entered" and e["args"]["action"] != "list"]
        self.assertEqual(mutations, [{"action": "remove", "job_id": jid}] * 2, message)

    def test_released_original_refresh_archive_importerror_preserves_frame_and_enabled_job(self):
        old = self.call("old", self.source)
        upgraded = self.call("archive")
        identity, message = self.observe(old, upgraded)
        self.assert_legacy_setup(old, upgraded, identity, message)
        sid, jid = identity["space"], identity["legacy_job"]
        refused = upgraded["refused_archive"]
        error = refused["outcome"].get("error", {})
        self.assertEqual(error.get("code"), "blocked", message)
        self.assertIn("not archived", error.get("message", ""), message)
        self.assertEqual(refused["state"]["sql"]["spaces"][sid]["space"]["status"], "active", message)
        self.assertEqual(refused["state"]["sql"]["spaces"][sid]["links"], [], message)
        self.assertIs(refused["state"]["jobs"][jid]["enabled"], True, message)
        self.assertEqual(refused["state"]["jobs"], old["old_state"]["jobs"], message)
        self.assertNotIn("error", upgraded["frame_after_refusal"]["outcome"], message)
        retry, active = upgraded["retry_archive"], upgraded["unarchive"]
        self.assertNotIn("error", retry["outcome"], message)
        self.assertEqual(retry["outcome"]["result"]["status"], "archived", message)
        self.assertIs(retry["state"]["jobs"][jid]["enabled"], False, message)
        self.assertNotIn("error", active["outcome"], message)
        self.assertEqual(active["outcome"]["result"]["status"], "active", message)
        self.assertIs(active["state"]["jobs"][jid]["enabled"], False, message)
        self.assertEqual(active["state"]["jobs"], retry["state"]["jobs"], message)
        self.assertEqual(set(active["state"]["jobs"]), set(old["old_state"]["jobs"]), message)
        self.assert_foreign_unchanged(old, [refused["state"], retry["state"], active["state"]], identity, message)
        mutations = [e["args"] for e in upgraded["native_events"]
                     if e["event"] == "entered" and e["args"]["action"] != "list"]
        self.assertTrue(mutations, message)
        self.assertTrue(all(args["action"] == "pause" and args["job_id"] == jid for args in mutations), message)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        worker(Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4])
    else:
        unittest.main()
