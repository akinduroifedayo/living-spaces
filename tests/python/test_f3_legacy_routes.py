"""Legacy route admission with real released SQLite and SYNTHETIC public cron.

Each attempt retains its outcome, persisted state, scripts, and native events.
The composed frozen fixture owns released setup, source checks, and children.
No accepted dispatch in this file establishes native execution or completion.
"""
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback
import unittest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tests.python import test_f3_legacy_upgrade as legacy


def worker(root, source, operation):
    from tests.python import test_lifecycle_atomic as lifecycle_support
    from tests.python.review_customization_support import SyntheticContext, AGENT_PROMPT

    cron = lifecycle_support.SharedCron(root / "native-jobs.db")
    identity = json.loads((root / "identity.json").read_text())
    sid = identity["space"]
    journal = root / (operation + "-native.jsonl")
    events = []
    record_path = root / (operation + "-result.json")
    record = {
        "pid": os.getpid(), "operation": operation,
        "isolated": sys.flags.isolated, "no_bytecode": sys.dont_write_bytecode,
        "environment": {key: os.environ.get(key) for key in
                        ("HOME", "HERMES_HOME", "LIVING_SPACES_DB", "TMPDIR")},
        "boundary": "real released/current core and SQLite; SYNTHETIC file-backed public cron; no completion proof",
    }

    def snapshot():
        return {"jobs": {job["id"]: job for job in cron.list_jobs(include_disabled=True)},
                "sql": legacy.sql_state(root, identity)}

    def scripts():
        directory = root / "hermes" / "scripts"
        return {str(path.relative_to(directory)): path.read_bytes().hex()
                for path in sorted(directory.rglob("*")) if path.is_file()}

    def event(value):
        events.append(value)
        with journal.open("a") as stream:
            stream.write(json.dumps(value) + "\n")

    class RecordedContext(SyntheticContext):
        def dispatch_tool(self, name, args):
            event({"event": "entered", "name": name, "args": args})
            try:
                reply = super().dispatch_tool(name, args)
            except Exception as exc:
                event({"event": "raised", "name": name, "args": args,
                       "type": type(exc).__name__, "message": str(exc)})
                raise
            event({"event": "returned", "name": name, "args": args,
                   "reply": json.loads(reply)})
            return reply

    def checkpoint():
        record["native_events"] = events
        legacy.save(record_path, record)

    try:
        record["before_import"] = snapshot()
        record["scripts_before_import"] = scripts()
        checkpoint()
        sys.path.insert(0, str(source / "src/living-spaces"))
        core = importlib.import_module("living_spaces_core")
        if core.__file__ is None:
            raise RuntimeError("Core must resolve to a source file")
        record["core_file"] = str(Path(core.__file__).resolve())
        record["db_path"] = str(core.db.db_path().resolve())
        record["hermes_home"] = str(core.db.hermes_home().resolve())
        core.configure_context(RecordedContext(cron))

        def attempt(label, function):
            start = len(events)
            try:
                outcome = {"result": function()}
            except core.SpacesError as exc:
                outcome = {"error": exc.to_dict()}
            record[label] = {"outcome": outcome, "state": snapshot(),
                             "scripts": scripts(), "native_events": events[start:]}
            checkpoint()

        def schedule():
            return core.schedule_upkeep(sid, kind="agent", cadence="0 * * * *",
                                        timezone="UTC", prompt=AGENT_PROMPT, actor="user")

        if operation == "old-schedule":
            attempt("schedule", schedule)
        elif operation in ("schedule", "run"):
            admission = schedule if operation == "schedule" else lambda: core.upkeep_action(sid, "run", actor="user")
            attempt("admission", admission)
            attempt("remove", lambda: core.upkeep_action(sid, "remove", actor="user"))
            attempt("recovered_schedule", schedule)
            attempt("recovered_run", lambda: core.upkeep_action(sid, "run", actor="user"))
        else:
            raise ValueError(operation)
    except Exception:
        record["fatal"] = traceback.format_exc()
        raise
    finally:
        checkpoint()
        print(json.dumps(record), flush=True)


class F3LegacyRoutesTests(unittest.TestCase):
    def setUp(self):
        supplied = os.environ.get("F3_LEGACY_SOURCE")
        if not supplied:
            raise RuntimeError("Set F3_LEGACY_SOURCE to the clean released checkout; no default or skip")
        if not Path(supplied).resolve().is_relative_to(Path("/Volumes/Expansion")):
            raise ValueError("F3_LEGACY_SOURCE must resolve under /Volumes/Expansion")
        fixture = legacy.F3LegacyUpgradeTests()
        fixture.id = self.id
        self.fixture = fixture
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()

    def call_route(self, operation, source=None):
        fixture = self.fixture
        source = source or ROOT
        argv = [sys.executable, "-I", "-B", str(Path(__file__).resolve()),
                "--worker", str(fixture.root), str(source), operation]
        with (fixture.root / (operation + ".stdout")).open("w") as out, \
                (fixture.root / (operation + ".stderr")).open("w") as err:
            child = subprocess.Popen(argv, cwd=fixture.root, env=fixture.env,
                                     stdout=out, stderr=err, start_new_session=True)
        fixture.children.append((child, operation))
        try:
            code = child.wait(timeout=30)
        except subprocess.TimeoutExpired:
            fixture.executions.append({"pid": child.pid, "argv": argv, "timeout": True})
            legacy.save(fixture.root / "execution.json", fixture.executions)
            raise
        entry = {"pid": child.pid, "argv": argv, "exit": code,
                 "stdout": (fixture.root / (operation + ".stdout")).read_text(),
                 "stderr": (fixture.root / (operation + ".stderr")).read_text()}
        fixture.executions.append(entry)
        legacy.save(fixture.root / "execution.json", fixture.executions)
        path = fixture.root / (operation + "-result.json")
        record = json.loads(path.read_text()) if path.exists() else None
        print(json.dumps({"case": self.id(), "evidence": str(fixture.root),
                          "execution": entry, "observation": record}), flush=True)
        self.assertEqual(code, 0, entry)
        if not isinstance(record, dict):
            self.fail("Worker did not preserve structured observations: " + json.dumps(entry))
        self.assertNotIn("fatal", record, record)
        self.assertEqual(record["pid"], child.pid, record)
        self.assertEqual((record["isolated"], record["no_bytecode"]), (1, True), record)
        self.assertEqual(record["core_file"], str(source / "src/living-spaces/living_spaces_core/__init__.py"), record)
        self.assertEqual(record["db_path"], fixture.env["LIVING_SPACES_DB"], record)
        self.assertEqual(record["hermes_home"], fixture.env["HERMES_HOME"], record)
        self.assertEqual(record["environment"], {key: fixture.env[key] for key in record["environment"]}, record)
        return record

    def contract(self, route):
        fixture = self.fixture
        old = fixture.call("old", fixture.source)
        scheduled = self.call_route("old-schedule", fixture.source) if route == "run" else None
        upgraded = self.call_route(route)
        identity = json.loads((fixture.root / "identity.json").read_text())
        observation = {"case": self.id(), "evidence": str(fixture.root), "identity": identity,
                       "old": old, "old_schedule": scheduled, "upgraded": upgraded,
                       "executions": fixture.executions, "source_identity_before": fixture.source_before,
                       "boundary": upgraded["boundary"]}
        legacy.save(fixture.root / "observations.json", observation)
        message = json.dumps(observation, sort_keys=True)
        print(message, flush=True)

        # The linked fixture has two actual old states, not one rewritten setup.
        fixture.assert_legacy_setup(old, scheduled or upgraded, identity, message)
        sid, once, foreign = identity["space"], identity["legacy_job"], identity["foreign_job"]
        before = upgraded["before_import"]
        prior_jobs = {once, foreign}
        if scheduled is not None:
            self.assertNotIn("error", scheduled["schedule"]["outcome"], message)
            linked = scheduled["schedule"]["outcome"]["result"]["link"]["cron_job_id"]
            after_schedule = scheduled["schedule"]["state"]
            self.assertNotEqual(after_schedule, old["old_state"], message)
            self.assertEqual(before, after_schedule, message)
            self.assertNotEqual(scheduled["pid"], upgraded["pid"], message)
            self.assertEqual(after_schedule["jobs"][once], old["old_state"]["jobs"][once], message)
            self.assertEqual(after_schedule["sql"]["spaces"][sid]["links"],
                             [{"space": sid, **scheduled["schedule"]["outcome"]["result"]["link"]}], message)
            self.assertEqual(after_schedule["jobs"][linked]["name"], "living-spaces:" + sid, message)
            self.assertIs(after_schedule["jobs"][linked]["enabled"], True, message)
            self.assertNotIn(linked, {once, foreign}, message)
            prior_jobs.add(linked)
            fixture.assert_foreign_unchanged(old, [scheduled["before_import"], after_schedule], identity, message)
            old_actions = [e["args"] for e in scheduled["native_events"] if e["event"] == "entered"]
            self.assertTrue(any(e["action"] == "create" for e in old_actions), message)
            self.assertIn({"action": "resume", "job_id": linked}, old_actions, message)
            self.assertEqual(scheduled["scripts_before_import"], scheduled["schedule"]["scripts"], message)
        self.assertEqual(set(before["jobs"]), prior_jobs, message)
        self.assertNotIn("refresh_claims", before["sql"]["tables"], message)
        self.assertEqual(before["jobs"][once], old["old_state"]["jobs"][once], message)
        self.assertNotEqual(old["pid"], upgraded["pid"], message)
        self.assertEqual(len({entry["pid"] for entry in fixture.executions}), len(fixture.executions), message)
        self.assertTrue(all(entry["exit"] == 0 for entry in fixture.executions), message)

        admission = upgraded["admission"]
        removed = upgraded["remove"]
        recovered_schedule = upgraded["recovered_schedule"]
        recovered_run = upgraded["recovered_run"]
        states = [before, admission["state"], removed["state"],
                  recovered_schedule["state"], recovered_run["state"]]
        fixture.assert_foreign_unchanged(old, states, identity, message)
        self.assertNotIn("error", removed["outcome"], message)
        self.assertEqual(set(removed["state"]["jobs"]), {foreign}, message)
        self.assertEqual(removed["state"]["sql"]["spaces"][sid]["links"], [], message)
        self.assertFalse(any(c["space"] == sid for c in removed["state"]["sql"]["claims"] or []), message)
        remove_entries = [e["args"] for e in removed["native_events"] if e["event"] == "entered"
                          and e["args"]["action"] != "list"]
        self.assertEqual({e["job_id"] for e in remove_entries}, set(admission["state"]["jobs"]) - {foreign}, message)
        self.assertTrue(all(e["action"] == "remove" for e in remove_entries), message)

        self.assertNotIn("error", recovered_schedule["outcome"], message)
        fresh = recovered_schedule["outcome"]["result"]["link"]["cron_job_id"]
        self.assertNotIn(fresh, admission["state"]["jobs"], message)
        self.assertEqual(set(recovered_schedule["state"]["jobs"]), {foreign, fresh}, message)
        self.assertIs(recovered_schedule["state"]["jobs"][fresh]["enabled"], True, message)
        self.assertEqual(recovered_schedule["state"]["sql"]["spaces"][sid]["links"],
                         [{"space": sid, **recovered_schedule["outcome"]["result"]["link"]}], message)
        fresh_entries = [e["args"] for e in recovered_schedule["native_events"] if e["event"] == "entered"]
        self.assertTrue(any(e["action"] == "create" for e in fresh_entries), message)
        self.assertIn({"action": "resume", "job_id": fresh}, fresh_entries, message)
        self.assertFalse(any(e["action"] == "run" for e in fresh_entries), message)
        self.assertNotIn("error", recovered_run["outcome"], message)
        result = recovered_run["outcome"]["result"]
        self.assertEqual(result["link"]["cron_job_id"], fresh, message)
        run_replies = [e["reply"] for e in recovered_run["native_events"] if e["event"] == "returned"
                       and e["args"] == {"action": "run", "job_id": fresh}]
        self.assertEqual(len(run_replies), 1, message)
        self.assertEqual(result["dispatch"], run_replies[0], message)
        self.assertIs(result["dispatch"]["success"], True, message)
        self.assertNotIn("execution_success", result["dispatch"]["job"], message)
        self.assertIsNone(result["dispatch"]["job"]["last_run_at"], message)
        self.assertIsNone(result["dispatch"]["job"]["last_status"], message)
        self.assertEqual(result["executions"], [], message)
        self.assertEqual(set(recovered_run["state"]["jobs"]), {foreign, fresh}, message)
        self.assertTrue(recovered_run["state"]["jobs"][fresh]["manual_run_at"], message)
        self.assertIsNone(recovered_run["state"]["jobs"][fresh]["last_run_at"], message)
        self.assertIsNone(recovered_run["state"]["jobs"][fresh]["last_status"], message)
        self.assertEqual(recovered_run["state"]["sql"]["spaces"][sid],
                         recovered_schedule["state"]["sql"]["spaces"][sid], message)
        for state in (removed["state"], recovered_schedule["state"], recovered_run["state"]):
            for key in ("space", "revisions", "records", "runs"):
                self.assertEqual(state["sql"]["spaces"][sid][key], before["sql"]["spaces"][sid][key], message)
        for attempt in (removed, recovered_schedule, recovered_run):
            self.assertEqual(attempt["scripts"], upgraded["scripts_before_import"], message)

        # Qualify controls before the intended RED so unsafe admission cannot hide them.
        error = admission["outcome"].get("error", {})
        self.assertEqual(error.get("code"), "blocked", message)
        self.assertIn("Upkeep Remove", json.dumps(error), message)
        self.assertIn(once, json.dumps(error), message)
        self.assertEqual(admission["state"]["jobs"], before["jobs"], message)
        self.assertEqual(admission["state"]["sql"]["spaces"], before["sql"]["spaces"], message)
        self.assertEqual(admission["state"]["sql"]["claims"], [], message)
        self.assertEqual(admission["scripts"], upgraded["scripts_before_import"], message)
        entries = [e for e in admission["native_events"] if e["event"] == "entered"]
        self.assertTrue(entries, message)
        self.assertTrue(all(e["name"] == "cronjob_manage" and e["args"]["action"] == "list"
                            for e in entries), message)

    def test_released_original_refresh_blocks_schedule_until_explicit_remove(self):
        self.contract("schedule")

    def test_released_original_refresh_and_schedule_block_upkeep_run_until_explicit_remove(self):
        self.contract("run")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        worker(Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4])
    else:
        unittest.main()
