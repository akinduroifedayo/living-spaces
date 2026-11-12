"""Recovery contracts against real upkeep functions and synthetic public cron faults."""
from contextlib import ExitStack
import ast
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch

from tests.python.review_customization_support import CustomizationFixture, PACKAGE


class UpkeepRecoveryTests(unittest.TestCase):
    def _native_job(self, fx, name, *, paused=False):
        reply = json.loads(fx.ctx.dispatch_tool("cronjob_manage", {
            "action": "create", "name": name, "schedule": "0 * * * *",
            "prompt": "Synthetic task. Do not execute a model.", "no_agent": False,
            "deliver": "local", "paused": paused,
        }))
        self.assertTrue(reply["success"], reply)
        jid = reply["job_id"]
        self.assertIsNotNone(fx.cron.get_job(jid))
        return jid

    def _unrelated(self, fx, sid):
        other = fx.make(handler="feed")
        state = fx.schedule(other, kind="feed")
        native_ids = [state["link"]["cron_job_id"]]
        for name in (f"living-spaces:{sid}-unrelated", f"living-spaces:{sid}:unrelated",
                     f"living-spaces:{sid}:once:unrelated", f"other:living-spaces:{sid}"):
            native_ids.append(self._native_job(fx, name))
        return {
            "space": other, "space_state": fx.projects.get_space(other), "upkeep": state,
            "shim": fx.upkeep._shim(other).read_bytes(),
            "jobs": {jid: fx.cron.get_job(jid) for jid in native_ids},
        }

    def _assert_unrelated(self, fx, before):
        other = before["space"]
        self.assertEqual(fx.projects.get_space(other), before["space_state"])
        self.assertEqual(fx.upkeep.get_upkeep(other), before["upkeep"])
        self.assertEqual(fx.upkeep._shim(other).read_bytes(), before["shim"])
        for jid, job in before["jobs"].items():
            self.assertEqual(fx.cron.get_job(jid), job, jid)

    def _replacement_refusal(self, fx, sid, *, refuse_cleanup):
        old = fx.schedule(sid, kind="feed")["link"]["cron_job_id"]
        original = fx.ctx.dispatch_tool
        created = []
        faults = []

        def dispatch(name, args):
            action = args["action"]
            if action == "create":
                reply = original(name, args)
                created.append(json.loads(reply)["job_id"])
                return reply
            if action == "remove" and args["job_id"] == old:
                faults.append("old-remove")
                return {"success": False, "error": "Synthetic old removal refusal"}
            if refuse_cleanup and args.get("job_id") in created and action in ("pause", "remove"):
                faults.append("candidate-" + action)
                return {"success": False, "error": "Synthetic candidate " + action + " refusal"}
            return original(name, args)

        with patch.object(fx.ctx, "dispatch_tool", side_effect=dispatch):
            with self.assertRaises(fx.core.SpacesError) as caught:
                fx.schedule(sid, kind="agent")
        self.assertEqual(len(created), 1)
        self.assertIn("old-remove", faults)
        error = caught.exception.to_dict()
        self.assertIn("Synthetic old removal refusal", json.dumps(error))
        if refuse_cleanup:
            self.assertIn("candidate-pause", faults)
            self.assertIn("candidate-remove", faults)
            self.assertEqual(error["orphan_job_id"], created[0])
            self.assertTrue(fx.cron.get_job(created[0])["enabled"])
            self.assertIn("Synthetic candidate pause refusal", json.dumps(error))
            self.assertIn("Synthetic candidate remove refusal", json.dumps(error))
        return old, created[0], error

    def _lifecycle_case(self, fx, source):
        sid = fx.make(handler="feed")
        unrelated = self._unrelated(fx, sid)
        if source == "linked_control":
            old = fx.schedule(sid, kind="feed")["link"]["cron_job_id"]
            regular = {old}
            orphans = set()
        elif source == "reported_orphan":
            old, orphan, _error = self._replacement_refusal(fx, sid, refuse_cleanup=True)
            regular = {old, orphan}
            orphans = {orphan}
        else:
            self.assertEqual(source, "native_without_ledger")
            self.assertIsNone(fx.upkeep.get_upkeep(sid)["link"])
            regular = {
                self._native_job(fx, f"living-spaces:{sid}"),
                self._native_job(fx, f"living-spaces:{sid}", paused=True),
            }
            orphans = set(regular)
        once = {self._native_job(fx, f"living-spaces:{sid}:once") for _ in range(7)}
        reopened = fx.load("_a5_reopened_core", PACKAGE / "living_spaces_core/__init__.py")
        fx.core = reopened
        fx.db = reopened.db
        fx.stack.enter_context(patch.object(fx.db, "hermes_home", return_value=fx.home))
        fx.upkeep = importlib.import_module(reopened.__name__ + ".upkeep")
        fx.projects = importlib.import_module(reopened.__name__ + ".projects")
        fx.upkeep.configure_context(fx.ctx)
        if source == "native_without_ledger":
            with fx.db.read() as conn:
                self.assertEqual(conn.execute(
                    "SELECT COUNT(*) FROM upkeep_links WHERE space=?", (sid,)
                ).fetchone()[0], 0)
        return sid, regular, orphans, once, unrelated

    def test_o1_successful_old_remove_with_failed_readback_keeps_recoverable_work(self):
        for fail_readback in (False, True):
            with self.subTest(fail_readback=fail_readback), ExitStack() as stack:
                fx = CustomizationFixture(stack)
                sid = fx.make(handler="feed")
                old = fx.schedule(sid, kind="feed")["link"]["cron_job_id"]
                unrelated = self._unrelated(fx, sid)
                original = fx.ctx.dispatch_tool
                created = []
                pending = []
                faults = []
                removed = []

                def dispatch(name, args):
                    if args["action"] == "list" and pending:
                        pending.clear()
                        faults.append("old-remove-readback")
                        raise OSError("Synthetic list fault after successful old-job removal")
                    reply = original(name, args)
                    if args["action"] == "create":
                        created.append(json.loads(reply)["job_id"])
                    if args["action"] == "remove" and args["job_id"] == old:
                        self.assertTrue(json.loads(reply)["success"])
                        removed.append(old)
                        if fail_readback:
                            pending.append(True)
                    return reply

                error = None
                with patch.object(fx.ctx, "dispatch_tool", side_effect=dispatch):
                    try:
                        fx.schedule(sid, kind="agent")
                    except fx.core.SpacesError as caught:
                        error = caught.to_dict()
                self.assertEqual(len(created), 1)
                self.assertEqual(removed, [old])
                self.assertEqual(faults, ["old-remove-readback"] if fail_readback else [])
                self.assertNotIn(old, fx.cron.jobs)
                self._assert_unrelated(fx, unrelated)
                survivors = [job for job in fx.cron.list_jobs(include_disabled=True)
                             if job["name"] == f"living-spaces:{sid}"]
                self.assertTrue(survivors, "A successful old removal must not destroy every surviving schedule")
                state = fx.upkeep.get_upkeep(sid)
                if error is None:
                    self.assertEqual(state["link"]["cron_job_id"], created[0])
                    self.assertEqual(state["job"]["id"], created[0])
                    self.assertTrue(state["job"]["enabled"])
                    self.assertFalse(state["missing"])
                else:
                    self.assertTrue(fail_readback, error)
                    observed = [error, state]
                    described = set()
                    while observed:
                        value = observed.pop()
                        if isinstance(value, dict):
                            for job in survivors:
                                if (job["id"] in value.values()
                                        and (value.get("state") == job["state"]
                                             or value.get("enabled") is job["enabled"])):
                                    described.add(job["id"])
                            observed.extend(value.values())
                        elif isinstance(value, list):
                            observed.extend(value)
                    self.assertTrue(described, "An error or current status must expose an exact surviving job ID and state")

    def test_r1_old_remove_refusal_with_working_compensation_preserves_old_schedule(self):
        with ExitStack() as stack:
            fx = CustomizationFixture(stack)
            sid = fx.make(handler="feed")
            unrelated = self._unrelated(fx, sid)
            old, candidate, error = self._replacement_refusal(fx, sid, refuse_cleanup=False)
            self.assertNotIn(candidate, fx.cron.jobs)
            self.assertNotIn("orphan_job_id", error)
            state = fx.upkeep.get_upkeep(sid)
            self.assertEqual(state["link"]["cron_job_id"], old)
            self.assertEqual(state["job"]["id"], old)
            self.assertTrue(state["job"]["enabled"])
            self.assertFalse(state["missing"])
            self._assert_unrelated(fx, unrelated)

    def test_r1_status_explicitly_projects_regular_orphans_after_reopen(self):
        for source in ("linked_control", "reported_orphan", "native_without_ledger"):
            with self.subTest(source=source), ExitStack() as stack:
                fx = CustomizationFixture(stack)
                sid, _regular, orphans, _once, unrelated = self._lifecycle_case(fx, source)
                state = fx.upkeep.get_upkeep(sid)
                self._assert_unrelated(fx, unrelated)
                if source == "linked_control":
                    self.assertEqual(state.get("orphan_jobs", []), [])
                    self.assertEqual(state["job"]["id"], next(iter(_regular)))
                    self.assertTrue(state["job"]["enabled"])
                    continue
                self.assertIn("orphan_jobs", state, "Unlinked regular jobs need an explicit status projection")
                projected = state["orphan_jobs"]
                self.assertIsInstance(projected, list)
                self.assertEqual({job["id"] for job in projected}, orphans)
                self.assertEqual(len(projected), len(orphans))
                for job in projected:
                    native = fx.cron.get_job(job["id"])
                    self.assertEqual(job["name"], f"living-spaces:{sid}")
                    self.assertEqual(job["enabled"], native["enabled"])
                    self.assertEqual(job["state"], native["state"])

    def test_r1_archive_pauses_every_attributable_regular_and_one_shot_job(self):
        for source in ("linked_control", "reported_orphan", "native_without_ledger"):
            with self.subTest(source=source), ExitStack() as stack:
                fx = CustomizationFixture(stack)
                sid, regular, _orphans, once, unrelated = self._lifecycle_case(fx, source)
                before_ids = set(fx.cron.jobs)
                fx.projects.set_status(sid, "archived", actor="user")
                self.assertEqual(fx.projects.get_space(sid)["status"], "archived")
                self._assert_unrelated(fx, unrelated)
                self.assertEqual(set(fx.cron.jobs), before_ids)
                for jid in regular | once:
                    job = fx.cron.get_job(jid)
                    self.assertIsNotNone(job, jid)
                    self.assertFalse(job["enabled"], jid)
                    self.assertEqual(job["state"], "paused", jid)
                fx.projects.delete_space(sid, actor="user", confirm=sid)
                self._assert_unrelated(fx, unrelated)
                self.assertEqual(set(fx.cron.jobs), before_ids - regular - once)

    def test_r1_delete_removes_every_attributable_job_without_touching_neighbors(self):
        for source in ("linked_control", "reported_orphan", "native_without_ledger"):
            with self.subTest(source=source), ExitStack() as stack:
                fx = CustomizationFixture(stack)
                sid, regular, _orphans, once, unrelated = self._lifecycle_case(fx, source)
                before_ids = set(fx.cron.jobs)
                fx.projects.delete_space(sid, actor="user", confirm=sid)
                with self.assertRaises(fx.core.SpacesError) as caught:
                    fx.projects.get_space(sid)
                self.assertEqual(caught.exception.code, "not_found")
                self._assert_unrelated(fx, unrelated)
                self.assertEqual(set(fx.cron.jobs), before_ids - regular - once)
                for jid in regular | once:
                    self.assertIsNone(fx.cron.get_job(jid), jid)

    def _refresh_cleanup_case(self, cleanup_action, fail_cleanup):
        with ExitStack() as stack:
            fx = CustomizationFixture(stack)
            sid = fx.make(handler="agent")
            unrelated = self._unrelated(fx, sid)
            before_ids = set(fx.cron.jobs)
            original = fx.ctx.dispatch_tool
            created = []
            run_refused = []
            cleanup_refused = []
            original_message = "Synthetic original run refusal"
            cleanup_message = "Synthetic cleanup-" + cleanup_action + " refusal"

            def dispatch(name, args):
                action = args["action"]
                if action == "create":
                    reply = original(name, args)
                    created.append(json.loads(reply)["job_id"])
                    return reply
                if action == "run":
                    self.assertIn(args["job_id"], created)
                    run_refused.append(args["job_id"])
                    return {"success": False, "error": original_message}
                if (fail_cleanup and run_refused and action == cleanup_action
                        and (action == "list" or args.get("job_id") in created)):
                    cleanup_refused.append(action)
                    return {"success": False, "error": cleanup_message}
                return original(name, args)

            with patch.object(fx.ctx, "dispatch_tool", side_effect=dispatch):
                with self.assertRaises(fx.core.SpacesError) as caught:
                    fx.upkeep.refresh_now(sid, {"handler": "agent", "prompt": "Read synthetic records only."}, actor="user")
            error = caught.exception.to_dict()
            self.assertEqual(len(created), 1)
            self.assertEqual(run_refused, created)
            self._assert_unrelated(fx, unrelated)
            if fail_cleanup:
                self.assertTrue(cleanup_refused, "The cleanup fault must actually be reached")
                self.assertIn(original_message, json.dumps(error), "Cleanup must not replace the original run error")
                self.assertIn(cleanup_message, json.dumps(error))
                self.assertEqual(error["orphan_job_id"], created[0])
                self.assertIn(original_message, json.dumps(error["original"]))
                self.assertIn(cleanup_message, json.dumps(error["cleanup"]))
                self.assertEqual(set(fx.cron.jobs), before_ids | set(created))
                job = fx.cron.get_job(created[0])
                self.assertEqual(job["name"], f"living-spaces:{sid}:once")
                self.assertFalse(job["enabled"])
                self.assertEqual(job["state"], "paused")
            else:
                self.assertEqual(cleanup_refused, [])
                self.assertIn(original_message, json.dumps(error))
                self.assertNotIn("orphan_job_id", error)
                self.assertEqual(set(fx.cron.jobs), before_ids)
                self.assertIsNone(fx.cron.get_job(created[0]))

    def test_r2_run_refusal_and_cleanup_list_refusal_preserve_both_errors_and_job_id(self):
        for fail_cleanup in (False, True):
            with self.subTest(fail_cleanup=fail_cleanup):
                self._refresh_cleanup_case("list", fail_cleanup)

    def test_r2_run_refusal_and_cleanup_remove_refusal_preserve_both_errors_and_job_id(self):
        for fail_cleanup in (False, True):
            with self.subTest(fail_cleanup=fail_cleanup):
                self._refresh_cleanup_case("remove", fail_cleanup)


class UpkeepEntrypointTests(unittest.TestCase):
    def test_o2_real_main_runs_the_same_test_identities_as_the_import_loader(self):
        root = Path(__file__).resolve().parents[2]
        module = "tests.python.test_public_upkeep"
        source = ast.parse((root / "tests/python/test_public_upkeep.py").read_text())
        expected = sorted(
            f"{cls.name}.{method.name}"
            for cls in source.body if isinstance(cls, ast.ClassDef)
            for method in cls.body if isinstance(method, ast.FunctionDef) and method.name.startswith("test_")
        )
        self.assertTrue(expected)
        child = textwrap.dedent('''
            import importlib
            import json
            import os
            import runpy
            import sys
            import unittest

            config = json.load(sys.stdin)
            sys.path[:] = config["sys_path"]
            initial_path = list(sys.path)
            module_name = config["module"]
            recorded = []
            original_runner = unittest.TextTestRunner

            def identities(suite):
                result = []
                for item in suite:
                    if isinstance(item, unittest.TestSuite):
                        result.extend(identities(item))
                    else:
                        name = item.id()
                        prefix = "__main__." if name.startswith("__main__.") else module_name + "."
                        assert name.startswith(prefix), name
                        result.append(name[len(prefix):])
                return result

            class RecordingRunner(original_runner):
                def run(self, suite):
                    ids = sorted(identities(suite))
                    result = super().run(suite)
                    recorded.append({"ids": ids, "tests_run": result.testsRun,
                                     "failures": len(result.failures), "errors": len(result.errors),
                                     "skips": len(result.skipped), "successful": result.wasSuccessful()})
                    return result

            unittest.TextTestRunner = RecordingRunner
            unittest.runner.TextTestRunner = RecordingRunner
            exit_code = 0
            if config["mode"] == "direct":
                sys.argv[:] = [module_name]
                try:
                    runpy.run_module(module_name, run_name="__main__", alter_sys=True)
                except SystemExit as exc:
                    exit_code = exc.code
            else:
                imported = importlib.import_module(module_name)
                suite = unittest.defaultTestLoader.loadTestsFromModule(imported)
                result = RecordingRunner().run(suite)
                exit_code = 0 if result.wasSuccessful() else 1
            print("A5_ENTRYPOINT=" + json.dumps({
                "mode": config["mode"], "runs": recorded, "exit_code": exit_code,
                "sys_path": initial_path, "home": os.environ.get("HOME"),
                "hermes_home": os.environ.get("HERMES_HOME"), "tmpdir": os.environ.get("TMPDIR"),
                "isolated": sys.flags.isolated, "dont_write_bytecode": sys.dont_write_bytecode,
            }))
        ''')
        results = {}
        with tempfile.TemporaryDirectory(prefix="spaces-a5-entrypoint-") as temporary:
            for mode in ("loader", "direct"):
                home = Path(temporary) / mode
                home.mkdir()
                runtime = home / "runtime"
                runtime.mkdir()
                env = {
                    "PATH": os.defpath, "LANG": "C.UTF-8", "HOME": str(home),
                    "HERMES_HOME": str(runtime), "TMPDIR": str(home),
                    "LIVING_SPACES_DB": str(home / "spaces.db"),
                }
                process = subprocess.run(
                    [sys.executable, "-I", "-B", "-c", child], cwd=root, env=env,
                    input=json.dumps({"mode": mode, "module": module, "sys_path": list(sys.path)}),
                    text=True, capture_output=True, timeout=180,
                )
                self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
                lines = [line for line in process.stdout.split("\n") if line.startswith("A5_ENTRYPOINT=")]
                self.assertEqual(len(lines), 1, process.stdout + process.stderr)
                receipt = json.loads(lines[0].removeprefix("A5_ENTRYPOINT="))
                self.assertEqual(receipt["mode"], mode)
                self.assertEqual(receipt["sys_path"], list(sys.path))
                self.assertEqual(receipt["home"], str(home))
                self.assertEqual(receipt["hermes_home"], str(runtime))
                self.assertEqual(receipt["tmpdir"], str(home))
                self.assertEqual(receipt["isolated"], 1)
                self.assertTrue(receipt["dont_write_bytecode"])
                self.assertEqual(receipt["exit_code"], 0, process.stderr)
                self.assertEqual(len(receipt["runs"]), 1, receipt)
                result = receipt["runs"][0]
                self.assertTrue(result["successful"], process.stderr)
                self.assertEqual(result["failures"], 0, process.stderr)
                self.assertEqual(result["errors"], 0, process.stderr)
                self.assertEqual(result["skips"], 0, process.stderr)
                self.assertEqual(result["tests_run"], len(result["ids"]))
                results[mode] = result
        self.assertEqual(results["loader"]["ids"], expected, "The loader control must see every declared test")
        self.assertEqual(results["direct"]["tests_run"], results["loader"]["tests_run"])
        self.assertEqual(results["direct"]["ids"], results["loader"]["ids"])


if __name__ == "__main__":
    unittest.main()
