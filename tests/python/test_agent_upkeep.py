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

ROOT = Path(__file__).resolve().parents[2]


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
        sid = core.create_space("Agent Demo", owner="Demo", author="agent:demo", manifest=manifest, files={"index.html": "<h1>Demo</h1>"})["id"]
        self.assertNotIn("refresh", [grant["capability"] for grant in core.list_grants(sid)])
        cron = Mock()
        cron.create_job.side_effect = lambda **kw: {**kw, "id": "demo-cron"}
        cron.get_job.side_effect = lambda jid: {"id": jid, "no_agent": False, "prompt": "native", "enabled": True, "state": "scheduled"}
        with patch.object(core.upkeep, "_cron", return_value=cron), patch.object(core.upkeep, "_ledger", return_value=Mock(list_executions=Mock(return_value=[]))):
            self.assertEqual(core.schedule_upkeep(sid, kind="agent", cadence="0 * * * *", timezone="UTC", prompt="Chat task", actor="agent:demo")["job"]["prompt"], "native")
            revised = copy.deepcopy(manifest)
            revised["upkeep"]["prompt"] = "Update the changed public demo."
            core.write_files(sid, files={}, manifest=revised, author="agent:demo", summary="New prompt")
            core.restore_revision(sid, 1, author="agent:demo")
            cron.pause_job.assert_not_called()
            cron.remove_job.assert_not_called()
            self.assertEqual(core.get_space(sid)["upkeep"]["cron_job_id"], "demo-cron")

    def test_source_owned_adapter_in_integrated_tree(self):
        package = self.root / "src/living-spaces"
        core = self.load("agent_upkeep_patch_core", package / "living_spaces_core/__init__.py")
        plugin = self.load("agent_upkeep_patch_plugin", package / "__init__.py")
        space = core.create_space("Agent Sources", owner="Demo", author="agent:demo", manifest={"upkeep": {"handler": "agent", "prompt": "Update public demo data."}}, files={"index.html": "<h1>Demo</h1>"})
        sid = space["id"]
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
        core.set_status(sid, "archived", actor="user")
        with self.assertRaises(core.SpacesError) as denied:
            plugin.spaces_write_records(core, args, "Demo")
        self.assertEqual(denied.exception.code, "archived")
        self.assertEqual(core.records.get(sid, "papers", "demo"), updated)


if __name__ == "__main__":
    unittest.main()
