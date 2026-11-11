from __future__ import annotations

import copy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import threading
import unittest
from unittest.mock import Mock, patch

from tests.python.test_upkeep_runs import UpkeepCase
from living_spaces_core import db, runs, schedules
from living_spaces_core.errors import SpacesError

ROOT = Path(__file__).resolve().parents[2]


class AgentUpkeepTests(UpkeepCase):
    def setUp(self):
        super().setUp()
        self.grants._check = lambda conn, sid, capability, scope_need=None: self.grant_status == "granted"
        self.manifest = {"upkeep": {"handler": "agent", "prompt": "Update the public demo research."}}
        self.jobs = {}
        self.executions = []
        self.triggers = []
        self.cancellations = []
        self.native = types.ModuleType("cron.jobs")
        self.native.create_job = self.create_job
        self.native.get_job = lambda jid: copy.deepcopy(self.jobs.get(jid))
        self.native.remove_job = lambda jid: self.jobs.pop(jid, None) is not None
        self.native.pause_job = lambda jid, reason=None: self.update_job(jid, enabled=False, state="paused")
        self.native.resume_job = lambda jid: self.update_job(jid, enabled=True, state="scheduled")
        self.native.trigger_job = self.trigger_job
        self.native.cancel_job_run = lambda jid, reason=None: self.cancellations.append(jid)
        ledger = types.ModuleType("cron.executions")
        ledger.list_executions = lambda *, job_id, limit=500: [copy.deepcopy(e) for e in reversed(self.executions) if e["job_id"] == job_id][:limit]
        item = patch.dict(sys.modules, {"cron.jobs": self.native, "cron.executions": ledger})
        item.start()
        self.addCleanup(item.stop)

    def create_job(self, **kwargs):
        jid = "cron-" + str(len(self.jobs) + 1)
        job = {**kwargs, "id": jid, "enabled": not kwargs.get("paused", False), "state": "paused" if kwargs.get("paused") else "scheduled", "next_run_at": db.now() + 3600}
        self.jobs[jid] = job
        return copy.deepcopy(job)

    def update_job(self, jid, **kwargs):
        if jid not in self.jobs:
            return None
        self.jobs[jid].update(kwargs)
        return copy.deepcopy(self.jobs[jid])

    def trigger_job(self, jid, extra_prompt=None):
        self.triggers.append(jid)
        return self.update_job(jid, manual_run_at=datetime.now(timezone.utc).isoformat(), enabled=True, state="scheduled")

    def approve(self):
        schedules.request_schedule("research-desk", cadence="0 * * * *", timezone="America/Chicago", purpose="Demo upkeep", actor="agent:demo")
        return schedules.decide_schedule("research-desk", "approve")

    def execution(self, jid, status="running"):
        stamp = datetime.now(timezone.utc).isoformat()
        entry = {"id": "exec-" + str(len(self.executions) + 1), "job_id": jid, "status": status, "claimed_at": stamp, "started_at": stamp, "finished_at": stamp if status in ("completed", "failed") else None, "error": "model failed" if status == "failed" else None}
        self.executions.append(entry)
        self.jobs[jid].pop("manual_run_at", None)
        return entry

    def test_agent_approval_uses_native_prompt_and_default_toolsets(self):
        approved = self.approve()
        job = self.jobs[approved["cron_job_id"]]
        self.assertFalse(job["no_agent"])
        self.assertEqual(job["deliver"], "local")
        self.assertTrue(job["catch_up"])
        self.assertEqual(job["timezone"], "America/Chicago")
        self.assertIn("research-desk", job["prompt"])
        self.assertIn("spaces_*", job["prompt"])
        self.assertIn(self.manifest["upkeep"]["prompt"], job["prompt"])
        self.assertNotIn("enabled_toolsets", job)
        self.assertNotIn("skills", job)
        self.assertFalse(job.get("script"))
        self.assertFalse(schedules._shim("research-desk").exists())

    def test_feed_approval_keeps_script_and_no_agent(self):
        self.manifest = {"upkeep": {"handler": "feed", "sources": [self.source("demo")]}}
        approved = self.approve()
        job = self.jobs[approved["cron_job_id"]]
        self.assertTrue(job["no_agent"])
        self.assertIsNone(job["prompt"])
        self.assertTrue(schedules._shim("research-desk").exists())

    def test_refresh_triggers_once_and_dedupes(self):
        jid = self.approve()["cron_job_id"]
        first = self.refresh()
        self.assertEqual(first["status"], "queued")
        self.assertNotEqual(first["detail"]["cron_job_id"], jid)
        self.assertEqual(self.refresh()["id"], first["id"])
        self.assertEqual(self.triggers, [first["detail"]["cron_job_id"]])
        self.fetch.assert_not_called()

    def test_schedule_pause_does_not_strand_queued_manual_refresh(self):
        jid = self.approve()["cron_job_id"]
        run = self.refresh()
        schedules.pause_schedule("research-desk", True, actor="user")
        self.assertFalse(self.jobs[jid]["enabled"])
        self.assertTrue(self.jobs[run["detail"]["cron_job_id"]]["enabled"])

    def test_concurrent_refresh_requests_share_one_native_fire(self):
        self.approve()
        barrier = threading.Barrier(6)

        def refresh(_):
            barrier.wait()
            return self.refresh()["id"]

        with ThreadPoolExecutor(max_workers=6) as pool:
            ids = list(pool.map(refresh, range(6)))
        self.assertEqual(len(set(ids)), 1)
        self.assertEqual(len(self.triggers), 1)

    def test_refresh_dedupes_an_already_running_schedule(self):
        jid = self.approve()["cron_job_id"]
        entry = self.execution(jid)
        run = self.refresh()
        self.assertEqual(run["detail"]["cron_run_id"], entry["id"])
        self.assertEqual(self.triggers, [])

    def test_old_execution_cannot_complete_a_new_manual_run(self):
        jid = self.approve()["cron_job_id"]
        self.execution(jid, "completed")
        run = self.refresh()
        self.assertEqual(run["status"], "queued")
        self.assertNotIn("cron_run_id", run["detail"])
        self.assertEqual(len(runs.list_runs("research-desk")), 2)

    def test_missing_native_job_fails_pending_run(self):
        run = self.refresh()
        self.jobs.clear()
        observed = runs.get_run(run["id"])
        self.assertEqual(observed["status"], "failed")
        self.assertIn("missing", observed["error"])

    def test_native_import_failure_is_visible(self):
        with patch.object(schedules, "_cron", side_effect=ImportError("demo cron unavailable")):
            run = self.refresh()
        self.assertEqual(run["status"], "failed")
        self.assertIn("demo cron unavailable", run["error"])

    def test_native_status_updates_and_long_runs_do_not_expire_as_feed_workers(self):
        first = self.refresh()
        self.assertEqual(first["status"], "queued")
        jid = first["detail"]["cron_job_id"]
        entry = self.execution(jid)
        live = runs.get_run(first["id"])
        self.assertEqual(live["status"], "running")
        self.assertEqual(live["detail"]["cron_run_id"], entry["id"])
        with db.write() as conn:
            conn.execute("UPDATE runs SET heartbeat_at=? WHERE id=?", (db.now() - 600, first["id"]))
        self.assertEqual(self.refresh()["id"], first["id"])
        entry.update(status="completed", finished_at=datetime.now(timezone.utc).isoformat())
        self.assertEqual(runs.get_run(first["id"])["status"], "succeeded")
        self.assertNotIn(jid, self.jobs)

    def test_schedule_execution_is_imported_once_with_failure(self):
        jid = self.approve()["cron_job_id"]
        entry = self.execution(jid, "failed")
        for _ in range(2):
            history = runs.list_runs("research-desk")
            self.assertEqual(len(history), 1)
            self.assertEqual((history[0]["trigger"], history[0]["status"]), ("schedule", "failed"))
            self.assertEqual(history[0]["detail"]["cron_run_id"], entry["id"])
            self.assertEqual(history[0]["error"], "model failed")

    def test_manual_refresh_does_not_resume_paused_schedule(self):
        jid = self.approve()["cron_job_id"]
        schedules.pause_schedule("research-desk", True, actor="user")
        run = self.refresh()
        self.assertEqual(run["status"], "queued")
        self.assertNotEqual(run["detail"]["cron_job_id"], jid)
        self.assertFalse(self.jobs[jid]["enabled"])
        self.assertEqual(self.jobs[run["detail"]["cron_job_id"]]["repeat"], 1)
        self.assertEqual(self.jobs[run["detail"]["cron_job_id"]]["schedule"], "in 1m")

    def test_trigger_failure_is_a_failed_run_and_cleans_one_shot(self):
        self.native.trigger_job = lambda jid, extra_prompt=None: None
        run = self.refresh()
        self.assertEqual(run["status"], "failed")
        self.assertTrue(run["error"])
        self.assertEqual(self.jobs, {})

    def test_grant_and_archive_block_agent_refresh(self):
        self.grant_status = "revoked"
        self.assertEqual(self.refresh()["detail"]["reason"], "not_granted")
        self.grant_status = "granted"
        with db.write() as conn:
            conn.execute("UPDATE spaces SET status='archived'")
        self.assertEqual(self.refresh()["detail"]["reason"], "archived")
        self.assertEqual(self.jobs, {})

    def test_scheduled_entrypoint_cannot_bypass_agent_approval(self):
        run = runs.start_refresh("research-desk", trigger="schedule", actor="upkeep:schedule", wait=True)
        self.assertEqual(run["status"], "blocked")
        self.assertEqual(run["detail"]["reason"], "schedule_not_approved")
        self.assertEqual(self.jobs, {})

    def test_old_feed_shim_cannot_run_a_new_unapproved_agent_prompt(self):
        before = {"upkeep": {"handler": "feed", "sources": [self.source("demo")]}}
        after = copy.deepcopy(self.manifest)
        self.manifest = before
        jid = self.approve()["cron_job_id"]
        with db.write() as conn:
            schedules.on_manifest_change(conn, "research-desk", before, after, actor="agent:demo")
        self.manifest = after
        run = runs.start_refresh("research-desk", trigger="schedule", actor="upkeep:schedule", wait=True)
        self.assertEqual(run["status"], "blocked")
        self.assertEqual(self.triggers, [])
        self.assertFalse(self.jobs[jid]["enabled"])

    def test_revocation_between_check_and_enqueue_stops_agent(self):
        def revoke_after_check(*args, **kwargs):
            self.grant_status = "revoked"

        self.grants.check = revoke_after_check
        self.assertEqual(self.refresh()["detail"]["reason"], "not_granted")
        self.assertEqual(self.jobs, {})

    def test_revocation_between_check_and_approval_stops_agent(self):
        self.grants.check = lambda *args, **kwargs: setattr(self, "grant_status", "revoked")
        with self.assertRaises(SpacesError) as error:
            self.approve()
        self.assertEqual(error.exception.code, "not_granted")
        self.assertEqual(self.jobs, {})

    def test_archive_and_delete_control_native_agent_job(self):
        jid = self.approve()["cron_job_id"]
        schedules.on_archive("research-desk")
        self.assertFalse(self.jobs[jid]["enabled"])
        schedules.on_delete("research-desk")
        self.assertNotIn(jid, self.jobs)

    def test_revocation_pauses_agent_schedule(self):
        jid = self.approve()["cron_job_id"]
        schedules.on_refresh_revoked("research-desk", "revoke", actor="user")
        self.assertEqual(self.jobs[jid]["state"], "paused")

    def test_cancel_pending_removes_one_shot(self):
        run = self.refresh()
        jid = run["detail"]["cron_job_id"]
        runs.cancel_pending("research-desk", "refresh revoked")
        self.assertEqual(runs.get_run(run["id"])["status"], "canceled")
        self.assertNotIn(jid, self.jobs)

    def test_cancel_running_agent_requests_native_interrupt(self):
        jid = self.approve()["cron_job_id"]
        self.execution(jid)
        self.assertEqual(runs.list_runs("research-desk")[0]["status"], "running")
        runs.cancel_pending("research-desk", "refresh revoked")
        self.assertEqual(self.cancellations, [jid])
        self.assertFalse(self.jobs[jid]["enabled"])

    def test_stale_native_snapshot_cannot_reopen_finished_run(self):
        jid = self.approve()["cron_job_id"]
        entry = self.execution(jid, "completed")
        self.assertEqual(runs.list_runs("research-desk")[0]["status"], "succeeded")
        entry.update(status="running", finished_at=None)
        self.assertEqual(runs.list_runs("research-desk")[0]["status"], "succeeded")

    def test_handler_and_prompt_changes_require_fresh_approval(self):
        changes = [({"handler": "feed", "sources": []}, {"handler": "agent", "prompt": "Demo"}),
                   ({"handler": "agent", "prompt": "Demo"}, {"handler": "agent", "prompt": "New demo"}),
                   ({"handler": "agent", "prompt": "Demo"}, {"handler": "feed", "sources": []})]
        for before, after in changes:
            with self.subTest(before=before, after=after):
                self.manifest = {"upkeep": before}
                jid = self.approve()["cron_job_id"]
                with db.write() as conn:
                    schedules.on_manifest_change(conn, "research-desk", {"upkeep": before}, {"upkeep": after}, actor="agent:demo")
                self.manifest = {"upkeep": after}
                self.assertEqual(schedules.get_schedule("research-desk")["status"], "requested")
                self.assertFalse(self.jobs[jid]["enabled"])

    def test_unchanged_prompt_keeps_approval(self):
        self.approve()
        with db.write() as conn:
            schedules.on_manifest_change(conn, "research-desk", self.manifest, copy.deepcopy(self.manifest), actor="agent:demo")
        self.assertEqual(schedules.get_schedule("research-desk")["status"], "active")

    def test_approval_rejects_a_prompt_different_from_the_host_display(self):
        schedules.request_schedule("research-desk", cadence="0 * * * *", timezone="UTC", purpose="Demo", actor="agent:demo")
        with self.assertRaises(SpacesError) as error:
            schedules.decide_schedule("research-desk", "approve", requested_upkeep={"handler": "agent", "prompt": "The old prompt"})
        self.assertEqual(error.exception.code, "conflict")
        self.assertEqual(schedules.get_schedule("research-desk")["status"], "requested")
        self.assertEqual(self.jobs, {})

    def test_invalid_upkeep_is_rejected(self):
        for upkeep in (None, [], {}, {"handler": "shell"}, {"handler": "agent"}, {"handler": "agent", "prompt": " "}, {"handler": "agent", "prompt": 3}, {"handler": "agent", "prompt": "a" * 4001}):
            with self.subTest(upkeep=upkeep), self.assertRaises(SpacesError) as error:
                schedules.validate_upkeep(upkeep)
            self.assertEqual(error.exception.code, "invalid")
        schedules.validate_upkeep({"handler": "agent", "prompt": "a" * 4000})
        schedules.validate_upkeep({"handler": "feed", "sources": []})


class NativeAgentCronTests(UpkeepCase):
    def test_installed_cron_accepts_paused_agent_one_shot_and_run_now(self):
        self.manifest = {"upkeep": {"handler": "agent", "prompt": "Update the public demo."}}
        self.grants._check = lambda *args: True
        path = str(Path.home() / ".hermes/hermes-agent")
        sys.path.insert(0, path)
        self.addCleanup(sys.path.remove, path)
        jobs = schedules._cron()
        with jobs.use_cron_store(self.home):
            run = self.refresh()
            self.assertEqual(run["status"], "queued")
            job = jobs.get_job(run["detail"]["cron_job_id"])
            try:
                self.assertEqual(job["schedule"]["kind"], "once")
                self.assertFalse(job["no_agent"])
                self.assertEqual(job["deliver"], "local")
                self.assertEqual(job["manual_run_at"], job["next_run_at"])
                self.assertIsNone(job["enabled_toolsets"])
                self.assertEqual(self.refresh()["id"], run["id"])
            finally:
                jobs.remove_job(job["id"])


class AgentIntegrationSeamTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="agent-integration-", dir=ROOT / ".run" if (ROOT / ".run").exists() else None)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {"HERMES_HOME": str(self.root / "home"), "LIVING_SPACES_DB": str(self.root / "home/spaces.db")})
        self.env.start()
        self.addCleanup(self.env.stop)
        shutil.copytree(ROOT / "src", self.root / "src", ignore=shutil.ignore_patterns("__pycache__"))

    def load(self, name, path):
        spec = importlib.util.spec_from_file_location(name, path, submodule_search_locations=[str(path.parent)])
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        self.addCleanup(lambda: [sys.modules.pop(key, None) for key in list(sys.modules) if key == name or key.startswith(name + ".")])
        spec.loader.exec_module(module)
        return module

    def test_manifest_hooks_in_integrated_tree(self):
        package = self.root / "src/living-spaces"
        core = self.load("agent_upkeep_patch_core", package / "living_spaces_core/__init__.py")
        manifest = {"upkeep": {"handler": "agent", "prompt": "Update public demo data."}}
        with self.assertRaises(core.SpacesError) as error:
            core.create_space("Invalid Agent", owner="Demo", author="agent:demo", manifest={"upkeep": {"handler": "agent"}})
        self.assertEqual(error.exception.code, "invalid")
        space = core.create_space("Agent Demo", owner="Demo", author="agent:demo", manifest=manifest, files={"index.html": "<h1>Demo</h1>"})
        sid = space["id"]
        core.decide(sid, "refresh", "grant")
        cron = Mock()
        cron.create_job.side_effect = lambda **kw: {**kw, "id": "demo-cron", "next_run_at": db.now() + 3600}
        cron.get_job.return_value = {"id": "demo-cron", "no_agent": False, "enabled": False, "state": "paused"}
        with patch.object(core.schedules, "_cron", return_value=cron), patch.object(core.runs, "_sync_agent_runs"):
            core.request_schedule(sid, cadence="0 * * * *", timezone="UTC", purpose="Demo", actor="agent:demo")
            self.assertEqual(core.decide_schedule(sid, "approve")["status"], "active")
            revised = copy.deepcopy(manifest)
            revised["upkeep"]["prompt"] = "Update the changed public demo."
            core.write_files(sid, files={}, manifest=revised, author="agent:demo", summary="New prompt")
            self.assertEqual(core.get_schedule(sid)["status"], "requested")
            cron.pause_job.assert_called_once()
            refresh = next(grant for grant in core.list_grants(sid) if grant["capability"] == "refresh")
            core.decide(sid, "refresh", "grant", requested_scope=refresh["requested_scope"])
            self.assertEqual(core.decide_schedule(sid, "approve")["status"], "active")
            core.restore_revision(sid, 1, author="agent:demo")
            self.assertEqual(core.get_schedule(sid)["status"], "requested")

    def test_source_owned_adapter_in_integrated_tree(self):
        package = self.root / "src/living-spaces"
        core = self.load("agent_upkeep_patch_core", package / "living_spaces_core/__init__.py")
        plugin = self.load("agent_upkeep_patch_plugin", package / "__init__.py")
        space = core.create_space("Agent Sources", owner="Demo", author="agent:demo", manifest={"upkeep": {"handler": "agent", "prompt": "Update public demo data."}}, files={"index.html": "<h1>Demo</h1>"})
        sid = space["id"]
        core.decide(sid, "refresh", "grant")
        record = core.records.put(sid, "papers", "demo", {"notes": "Keep this user note", "status": "reading"}, actor="user", base_rev=0)
        args = {"space": sid, "source_owned": True, "ops": [{"op": "put", "collection": "papers", "id": "demo", "source": {"title": "Fresh public demo"}, "source_meta": {"url": "https://example.org/demo"}}]}
        plugin.spaces_write_records(core, args, "Demo")
        updated = core.records.get(sid, "papers", "demo")
        self.assertEqual(updated["data"], record["data"])
        self.assertEqual(updated["source"], {"title": "Fresh public demo"})
        self.assertEqual(updated["source_meta"]["handler"], "agent")
        self.assertEqual(updated["source_meta"]["url"], "https://example.org/demo")
        bad = copy.deepcopy(args)
        bad["ops"] += [{"op": "delete", "collection": "papers", "id": "demo"}]
        bad["ops"][0]["source"]["title"] = "Must roll back"
        with self.assertRaises(core.SpacesError):
            plugin.spaces_write_records(core, bad, "Demo")
        self.assertEqual(core.records.get(sid, "papers", "demo"), updated)
        core.decide(sid, "refresh", "revoke")
        with self.assertRaises(core.SpacesError) as denied:
            plugin.spaces_write_records(core, args, "Demo")
        self.assertEqual(denied.exception.code, "not_granted")
        self.assertEqual(core.records.get(sid, "papers", "demo"), updated)

    def test_host_approval_snapshot_reaches_core_in_integrated_tree(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        package = self.root / "src/living-spaces"
        core = self.load("agent_upkeep_patch_core", package / "living_spaces_core/__init__.py")
        api = self.load("agent_upkeep_patch_api", package / "dashboard/plugin_api.py")
        api.load_core = lambda: core
        upkeep = {"handler": "agent", "prompt": "Current public demo task"}
        sid = core.create_space("Approval Demo", owner="Demo", author="agent:demo", manifest={"upkeep": upkeep})["id"]
        core.decide(sid, "refresh", "grant")
        schedule = core.request_schedule(sid, cadence="0 * * * *", timezone="UTC", purpose="Demo", actor="agent:demo")
        snapshot = {key: schedule[key] for key in ("cadence", "timezone", "purpose", "requested_at")}
        app = FastAPI()
        app.include_router(api.router)
        cron = Mock()
        cron.create_job.side_effect = lambda **kw: {**kw, "id": "demo-cron", "next_run_at": db.now() + 3600}
        with TestClient(app) as client, patch.object(core.schedules, "_cron", return_value=cron):
            response = client.post(f"/spaces/{sid}/schedule", json={"decision": "approve", "requested_upkeep": {"handler": "agent", "prompt": "Old task"}, "requested_schedule": snapshot})
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()["error"]["code"], "conflict")
            cron.create_job.assert_not_called()
            response = client.post(f"/spaces/{sid}/schedule", json={"decision": "approve", "requested_upkeep": upkeep, "requested_schedule": snapshot})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "active")
            response = client.post(f"/spaces/{sid}/schedule", json={"decision": "approve", "requested_upkeep": None, "requested_schedule": snapshot})
            self.assertEqual(response.status_code, 400)

    def test_host_cost_and_prompt_render_before_approval_in_integrated_tree(self):
        modules = Path.home() / ".hermes/hermes-agent/apps/desktop/node_modules"
        esbuild = shutil.which("esbuild")
        if not esbuild or not (modules / "react-dom/package.json").exists():
            self.skipTest("Hermes React renderer and esbuild are required for the host render test")
        entry = self.root / "entry.jsx"
        entry.write_text("export { ScheduleSheet } from './src/desktop/ui/schedule.jsx';\nexport { PermissionsContent } from './src/desktop/ui/permissions.jsx';\n")
        bundle = self.root / "ui.cjs"
        built = subprocess.run([esbuild, str(entry), "--bundle", "--platform=node", "--format=cjs", "--jsx=automatic", f"--alias:@hermes/plugin-sdk={ROOT / 'tests/js/ui/sdk-stub.js'}", f"--alias:react={modules / 'react'}", f"--external:{modules / 'react'}", f"--external:{modules / 'react'}/*", f"--outfile={bundle}"], capture_output=True, text=True)
        self.assertEqual(built.returncode, 0, built.stderr)
        script = self.root / "render.cjs"
        script.write_text(f"""const assert = require('node:assert/strict');
const {{createRequire}} = require('node:module');
const req = createRequire({json.dumps(str(modules / 'react-dom/package.json'))});
const React = req('react');
const server = req('react-dom/server');
const ui = require('./ui.cjs');
const prompt = '<script>demo</script>\\nKeep public data current.';
const space = {{id:'agent-demo',name:'Agent Demo',owner:'Demo',manifest:{{upkeep:{{handler:'agent',prompt}}}},schedule:{{status:'requested',cadence:'0 * * * *',timezone:'UTC'}},grants:[]}};
for (const name of ['ScheduleSheet','PermissionsContent']) {{
  const props = {{space, schedule:space.schedule, grants:[], ctx:{{}}, onClose(){{}}, onChanged(){{}}, onSchedule(){{}}, onDecide(){{}}}};
  const html = server.renderToStaticMarkup(React.createElement(ui[name], props));
  assert.ok(html.includes('Uses model calls'));
  assert.ok(!html.includes('No model calls'));
  assert.ok(html.includes('&lt;script&gt;demo&lt;/script&gt;'));
  assert.ok(html.includes('Keep public data current.'));
  if (name === 'PermissionsContent') assert.ok(html.indexOf('Keep public data current.') < html.indexOf('>Approve<'));
}}
space.manifest.upkeep = {{handler:'feed'}};
const feed = server.renderToStaticMarkup(React.createElement(ui.ScheduleSheet, {{space,ctx:{{}},onClose(){{}}}}));
assert.ok(feed.includes('No model calls'));
assert.ok(!feed.includes('Uses model calls'));
""")
        rendered = subprocess.run(["node", str(script)], capture_output=True, text=True)
        self.assertEqual(rendered.returncode, 0, rendered.stderr)


if __name__ == "__main__":
    unittest.main()
