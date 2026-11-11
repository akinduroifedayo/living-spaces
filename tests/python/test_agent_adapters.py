import asyncio
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "src" / "living-spaces"


def load(name, path, package=False):
    spec = importlib.util.spec_from_file_location(
        name, path, submodule_search_locations=[str(path.parent)] if package else None
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


errors = load("agent_test_errors", PACKAGE / "living_spaces_core" / "errors.py")
SpacesError = errors.SpacesError
STATUS = {"not_found": 404, "invalid": 400, "conflict": 409, "not_granted": 403,
          "limit": 413, "session_invalid": 403, "archived": 423, "blocked": 423,
          "ambiguous": 409, "incompatible": 409}
SID = "research-desk"
MANIFEST = {"schema": 1, "entry": "index.html", "imports": {"preact": "vendor/preact.mjs"}}
DETAIL = {"id": SID, "name": "Research Desk", "head_rev": 2, "manifest": MANIFEST,
          "upkeep": None, "freshness": {}, "attention": None}
PARAMS = {
    "spaces_list": {},
    "spaces_get": {"space": "Research Desk"},
    "spaces_create": {"name": "Research Desk", "description": "Public reading desk",
                      "files": {"index.html": "<main>Library</main>"}, "manifest": MANIFEST},
    "spaces_read_file": {"space": SID, "path": "app.js"},
    "spaces_write_files": {"space": SID, "files": {"app.js": "export const value = 2"},
                           "summary": "Update value", "base_rev": 2},
    "spaces_edit_file": {"space": SID, "path": "app.js", "old": "1", "new": "2", "summary": "Fix value"},
    "spaces_query": {"space": SID, "collection": "papers", "where": {"status": "reading"}, "limit": 7},
    "spaces_write_records": {"space": SID, "ops": [{"op": "put", "collection": "papers", "id": "demo",
                                                     "data": {"notes": "Demo note"}, "base_rev": 3}]},
    "spaces_read_logs": {"space": SID, "level": "error"},
    "spaces_revisions": {"space": SID},
    "spaces_restore": {"space": SID, "rev": 1},
    "spaces_refresh": {"space": SID},
    "spaces_schedule_upkeep": {"space": SID, "kind": "agent", "cadence": "0 7 * * *", "timezone": "America/Chicago",
                               "prompt": "Read new public papers each morning"},
    "spaces_upkeep": {"space": SID, "action": "status"},
}
TARGETS = {
    "spaces_list": "list_spaces", "spaces_get": "get_space", "spaces_create": "create_space",
    "spaces_read_file": "read_file", "spaces_write_files": "write_files", "spaces_edit_file": "edit_file",
    "spaces_query": "query", "spaces_write_records": "batch", "spaces_read_logs": "read_logs",
    "spaces_revisions": "list_revisions", "spaces_restore": "restore_revision",
    "spaces_refresh": "start_refresh", "spaces_schedule_upkeep": "schedule_upkeep", "spaces_upkeep": "get_upkeep",
}


class AdapterCase(unittest.TestCase):
    def setUp(self):
        run = ROOT / ".run"
        run.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="agent-test-", dir=run)
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {"HERMES_HOME": self.temp.name,
                                          "LIVING_SPACES_DB": str(Path(self.temp.name) / "spaces.db")})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.core = types.ModuleType("living_spaces_core")
        self.core.SpacesError = SpacesError
        returns = {
            "resolve_space": SID, "list_spaces": [DETAIL.copy()], "get_space": DETAIL.copy(),
            "create_space": DETAIL.copy(), "read_file": {"path": "app.js", "text": "value = 2", "rev": 2},
            "list_files": [{"path": "index.html"}, {"path": "app.js"}, {"path": "vendor/preact.mjs"}],
            "write_files": {"rev": 3}, "edit_file": {"rev": 3}, "list_revisions": [{"rev": 2}],
            "restore_revision": {"rev": 3}, "query": {"records": [], "total": 0, "seq": 8},
            "batch": {"results": [{"id": "demo", "rev": 4}], "seq": 9}, "read_logs": [{"level": "error", "msg": "Demo"}],
            "list_grants": [{"capability": "net", "status": "requested", "scope": {},
                             "purpose": "Public feed"}], "audit_log": [],
            "start_refresh": {"id": "run_demo", "status": "queued"},
            "schedule_upkeep": {"link": {"cron_job_id": "demo"}}, "get_upkeep": {"link": None},
            "upkeep_action": {"link": {"cron_job_id": "demo"}},
            "decide": {"capability": "net", "status": "granted"},
            "bundle": {"manifest": MANIFEST, "files": [
                {"path": "index.html", "text": "<main>Library</main>"},
                {"path": "app.js", "text": "export const value = 2"}, {"path": "vendor/preact.mjs", "text": ""}]},
            "open_session": {"session": "session_demo", "grants": [], "head_rev": 2}, "require": None,
            "close_session": None, "dispatch": {"ok": True, "result": {"records": []}},
            "changes_since": {"seq": 8, "changes": []}, "list_runs": [{"id": "run_demo"}],
            "set_status": None, "set_pinned": None, "touch_opened": None,
            "delete_space": {"deleted": True, "removed": {"records": 2, "revisions": 3, "upkeep": False}},
        }
        for name, value in returns.items():
            setattr(self.core, name, Mock(return_value=value))
        self.core.grants = types.SimpleNamespace(FUTURE={"camera": "Unavailable"})
        constants = types.ModuleType("hermes_constants")
        constants.get_hermes_home = lambda: Path(self.temp.name)
        self.modules = patch.dict(sys.modules, {"living_spaces_core": self.core, "hermes_constants": constants})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.plugin = load("agent_test_plugin", PACKAGE / "__init__.py", package=True)
        self.api = load("agent_test_api", PACKAGE / "dashboard" / "plugin_api.py")
        self.ctx = types.SimpleNamespace(register_tool=Mock(), register_skill=Mock())
        self.plugin.register(self.ctx)
        self.tools = {call.kwargs["name"]: call.kwargs for call in self.ctx.register_tool.call_args_list}
        app = FastAPI()
        app.include_router(self.api.router, prefix="/api/plugins/living-spaces")
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def tool(self, name, args=None, **context):
        result = self.tools[name]["handler"](PARAMS[name] if args is None else args, **context)
        self.assertIsInstance(result, str)
        return json.loads(result)

    def request(self, method, path, **kwargs):
        return self.client.request(method, "/api/plugins/living-spaces" + path, **kwargs)


class ToolTests(AdapterCase):
    def test_registration_and_skill(self):
        self.assertEqual(set(self.tools), set(PARAMS))
        for name, tool in self.tools.items():
            with self.subTest(name=name):
                self.assertEqual(tool["toolset"], "living_spaces")
                self.assertEqual(tool["emoji"], "🪴")
                self.assertEqual(tool["schema"]["name"], name)
                self.assertEqual(tool["schema"]["parameters"]["type"], "object")
                self.assertTrue(tool["description"])
        call = self.ctx.register_skill.call_args
        self.assertEqual(call.args[0], "build-space")
        self.assertTrue(Path(call.args[1]).is_file())
        self.core.list_spaces.assert_not_called()

    def test_all_tools_preserve_every_core_error(self):
        for name, target in TARGETS.items():
            for code in STATUS:
                with self.subTest(tool=name, code=code):
                    error = SpacesError(code, "Demo error", current={"rev": 9}, candidates=[{"id": "other-desk"}])
                    getattr(self.core, target).side_effect = error
                    self.assertEqual(self.tool(name), {"ok": False, "error": error.to_dict()})
                    getattr(self.core, target).side_effect = None

    def test_ambiguous_reference_never_guesses_or_writes(self):
        error = SpacesError("ambiguous", "Choose a Space", candidates=[{"id": "desk-1"}, {"id": "desk-2"}])
        self.core.resolve_space.side_effect = error
        for name, params in PARAMS.items():
            if "space" not in params:
                continue
            with self.subTest(tool=name):
                self.assertEqual(self.tool(name)["error"], error.to_dict())
                getattr(self.core, TARGETS[name]).assert_not_called()

    def test_owner_context_and_active_profile(self):
        for context in ({"bot_name": "DemoBot"}, {"profile_name": "DemoBot"},
                        {"context": {"profile_name": "DemoBot"}},
                        {"parent_agent": types.SimpleNamespace(bot_name="DemoBot")}):
            with self.subTest(context=context):
                self.assertTrue(self.tool("spaces_create", **context)["ok"])
                self.assertEqual(self.core.create_space.call_args.kwargs["owner"], "DemoBot")
                self.assertEqual(self.core.create_space.call_args.kwargs["author"], "agent:DemoBot")
        sys.modules["hermes_constants"].get_hermes_home = lambda: Path(self.temp.name) / "profiles" / "demo"
        self.tool("spaces_refresh", task_id="task_demo", session_id="session_demo")
        self.assertEqual(self.core.start_refresh.call_args.kwargs["actor"], "agent:demo")
        self.tool("spaces_refresh", profile_name="ContextBot")
        self.assertEqual(self.core.start_refresh.call_args.kwargs["actor"], "agent:ContextBot")

    def test_mutation_attribution(self):
        for name, keyword in (("spaces_write_files", "author"), ("spaces_edit_file", "author"),
                              ("spaces_write_records", "actor"), ("spaces_restore", "author"),
                              ("spaces_refresh", "actor"), ("spaces_schedule_upkeep", "actor")):
            with self.subTest(tool=name):
                self.assertTrue(self.tool(name, profile_name="DemoBot")["ok"])
                self.assertEqual(getattr(self.core, TARGETS[name]).call_args.kwargs[keyword], "agent:DemoBot")

    def test_create_defaults_manifest_extraction_and_open_card(self):
        params = dict(PARAMS["spaces_create"])
        params.pop("manifest")
        params["files"] = {"index.html": "<main>Library</main>", "space.json": json.dumps(MANIFEST)}
        result = self.tool("spaces_create", params)["result"]
        call = self.core.create_space.call_args
        self.assertEqual(call.kwargs["libraries"], ["preact", "preact/hooks", "spaces-kit"])
        self.assertNotIn("space.json", call.kwargs["files"])
        self.assertEqual(call.kwargs["manifest"], MANIFEST)
        self.assertEqual(call.kwargs["owner"], "Hermes")
        self.assertEqual(result["open"], {"directive": '::living-space{id="research-desk"}',
                                          "route": "/spaces?space=research-desk"})
        self.assertEqual(result["rev"], 2)
        self.assertEqual(result["grants_pending"][0]["capability"], "net")
        self.assertIn("directive paragraph", result["next"])
        self.assertEqual(params["files"]["space.json"], json.dumps(MANIFEST))

    def test_explicit_no_libraries_is_preserved(self):
        self.tool("spaces_create", {**PARAMS["spaces_create"], "libraries": []})
        self.assertEqual(self.core.create_space.call_args.kwargs["libraries"], [])

    def test_file_write_base_revision_manifest_and_delete(self):
        files = {"space.json": json.dumps(MANIFEST), "obsolete.js": None}
        result = self.tool("spaces_write_files", {"space": SID, "files": files, "summary": "Remove obsolete", "base_rev": 2})
        self.assertTrue(result["ok"])
        self.core.write_files.assert_called_once_with(SID, files={"obsolete.js": None}, manifest=MANIFEST,
                                                     summary="Remove obsolete", author="agent:Hermes", base_rev=2)

    def test_manifest_exact_edit_uses_head_revision(self):
        self.core.read_file.return_value = {"text": json.dumps(MANIFEST), "rev": 2}
        result = self.tool("spaces_edit_file", {"space": SID, "path": "space.json", "old": '"schema": 1',
                                                "new": '"schema": 2', "summary": "Change manifest"})
        self.assertTrue(result["ok"])
        self.assertEqual(self.core.write_files.call_args.kwargs["base_rev"], 2)
        self.assertEqual(self.core.write_files.call_args.kwargs["manifest"]["schema"], 2)
        self.core.edit_file.assert_not_called()

    def test_manifest_read_delegates_to_core(self):
        self.tool("spaces_read_file", {"space": SID, "path": "space.json"})
        self.core.read_file.assert_called_once_with(SID, "space.json")

    def test_static_warnings_help_repair_the_project(self):
        self.core.bundle.return_value = {"manifest": MANIFEST, "files": [
            {"path": "index.html", "text": "<main>Library</main>"},
            {"path": "app.js", "text": "import './missing.js'; fetch('https://example.org')"}]}
        result = self.tool("spaces_create", {**PARAMS["spaces_create"], "files": {
            "app.js": "import './missing.js'; fetch('https://example.org')"}})["result"]
        self.assertTrue(any("missing.js" in warning for warning in result["warnings"]))
        self.assertTrue(any("network access" in warning for warning in result["warnings"]))
        self.core.bundle.return_value = {"manifest": MANIFEST, "files": [{"path": "app.js", "text": ""}]}
        result = self.tool("spaces_create")["result"]
        self.assertTrue(any("Entry file" in warning for warning in result["warnings"]))

    def test_deleted_dependency_warns_on_unchanged_importer(self):
        self.core.bundle.return_value = {"manifest": MANIFEST, "files": [
            {"path": "index.html", "text": '<script type="module" src="./app.js"></script>'},
            {"path": "app.js", "text": "import './views/library.js'"}]}
        reply = self.tool("spaces_write_files", {"space": SID, "files": {"views/library.js": None},
                                                 "summary": "Remove view", "base_rev": 2})
        self.assertTrue(reply["ok"])
        self.assertTrue(any("library.js" in warning for warning in reply["result"]["warnings"]))
        self.core.bundle.assert_called_once_with(SID, rev=3)

    def test_invalid_arguments_are_json_errors(self):
        cases = [("spaces_get", {}), ("spaces_create", {**PARAMS["spaces_create"], "description": 4}),
                 ("spaces_create", {**PARAMS["spaces_create"], "files": {"app.js": None}}),
                 ("spaces_create", {**PARAMS["spaces_create"], "libraries": ["remote"]}),
                 ("spaces_create", {**PARAMS["spaces_create"], "files": {"space.json": "[]"}, "manifest": None}),
                 ("spaces_write_files", {**PARAMS["spaces_write_files"], "files": {"space.json": "{"}}),
                 ("spaces_write_files", {**PARAMS["spaces_write_files"], "files": {"app.js": 3}}),
                 ("spaces_write_files", {**PARAMS["spaces_write_files"], "base_rev": True}),
                 ("spaces_edit_file", {**PARAMS["spaces_edit_file"], "old": ""}),
                 ("spaces_write_records", {"space": SID, "ops": []}),
                 ("spaces_restore", {"space": SID, "rev": False}),
                 ("spaces_schedule_upkeep", {**PARAMS["spaces_schedule_upkeep"], "timezone": ""}),
                 ("spaces_schedule_upkeep", {**PARAMS["spaces_schedule_upkeep"], "prompt": None}),
                 ("spaces_upkeep", {"space": SID})]
        for name, args in cases:
            with self.subTest(tool=name, args=args):
                self.assertEqual(self.tool(name, args)["error"]["code"], "invalid")
        self.assertEqual(self.tool("spaces_list", [])["error"]["code"], "invalid")

    def test_unexpected_error_is_json_without_exception_details(self):
        self.core.list_spaces.side_effect = RuntimeError("private implementation detail")
        result = self.tool("spaces_list")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "internal")
        self.assertNotIn("private", json.dumps(result))


def tool_success(name):
    def test(self):
        reply = self.tool(name, task_id="task_demo", session_id="session_demo")
        self.assertTrue(reply["ok"], reply)
        target = getattr(self.core, TARGETS[name])
        target.assert_called_once()
        if name in ("spaces_list", "spaces_read_file", "spaces_query", "spaces_write_records", "spaces_read_logs",
                    "spaces_revisions", "spaces_refresh", "spaces_schedule_upkeep", "spaces_upkeep"):
            self.assertEqual(reply, {"ok": True, "result": target.return_value})
        elif name == "spaces_get":
            self.assertEqual(reply["result"], {**DETAIL, "files": self.core.list_files.return_value})
        elif name == "spaces_restore":
            self.assertEqual(reply["result"]["revision"], {"rev": 3})
            self.assertEqual(reply["result"]["rev"], 3)
        else:
            self.assertEqual(reply["result"]["space"], SID)
            self.assertEqual(reply["result"]["rev"], 2 if name == "spaces_create" else 3)
            self.assertEqual(reply["result"]["warnings"], [])
        if name not in ("spaces_list", "spaces_create"):
            self.core.resolve_space.assert_called_once_with(PARAMS[name]["space"])
            self.assertEqual(target.call_args.args[0], SID)
        if name == "spaces_query":
            self.assertEqual(target.call_args.kwargs, {"where": {"status": "reading"}, "limit": 7})
        if name == "spaces_write_records":
            self.assertEqual(target.call_args.args[1], PARAMS[name]["ops"])
        if name == "spaces_refresh":
            self.assertEqual(target.call_args.kwargs["trigger"], "chat")
        if name == "spaces_schedule_upkeep":
            self.assertEqual(target.call_args.kwargs, {"kind": "agent", "cadence": "0 7 * * *", "timezone": "America/Chicago",
                                                       "prompt": "Read new public papers each morning", "actor": "agent:Hermes"})
    return test


for tool_name in PARAMS:
    setattr(ToolTests, "test_success_" + tool_name, tool_success(tool_name))


class RestTests(AdapterCase):
    def test_all_routes_success(self):
        cases = [("GET", "/spaces", None), ("GET", "/status", None), ("GET", f"/spaces/{SID}", None),
                 ("GET", f"/spaces/{SID}/bundle", None), ("POST", f"/spaces/{SID}/sessions", None),
                 ("DELETE", f"/spaces/{SID}/sessions/session_demo", None),
                 ("GET", f"/spaces/{SID}/changes?since=3", None), ("GET", f"/spaces/{SID}/runs", None),
                 ("POST", f"/spaces/{SID}/refresh", None), ("GET", f"/spaces/{SID}/grants", None),
                 ("POST", f"/spaces/{SID}/grants/net", {"decision": "grant", "scope": {}, "requested_scope": {}}),
                 ("GET", f"/spaces/{SID}/upkeep", None),
                 ("POST", f"/spaces/{SID}/upkeep", {"action": "pause"}),
                 ("GET", f"/spaces/{SID}/revisions", None),
                 ("POST", f"/spaces/{SID}/revisions/1/restore", None),
                 ("GET", f"/spaces/{SID}/logs?level=error", None),
                 ("POST", f"/spaces/{SID}/archive", None), ("POST", f"/spaces/{SID}/unarchive", None),
                 ("POST", f"/spaces/{SID}/pin", {"pinned": True}), ("POST", f"/spaces/{SID}/opened", None),
                 ("DELETE", f"/spaces/{SID}?confirm={SID}", None)]
        for method, path, body in cases:
            with self.subTest(method=method, path=path):
                response = self.request(method, path, json=body) if body is not None else self.request(method, path)
                self.assertEqual(response.status_code, 200, response.text)
        self.core.start_refresh.assert_called_once_with(SID, trigger="manual", actor="user")
        self.core.decide.assert_called_once_with(SID, "net", "grant", actor="user", scope={}, requested_scope={})
        self.core.get_upkeep.assert_called_once_with(SID)
        self.core.upkeep_action.assert_called_once_with(SID, "pause", actor="user")
        self.core.restore_revision.assert_called_once_with(SID, 1, author="user")
        self.core.delete_space.assert_called_once_with(SID, actor="user", confirm=SID)
        self.assertEqual(self.core.set_status.call_args_list[0].args, (SID, "archived"))
        self.assertEqual(self.core.set_status.call_args_list[0].kwargs, {"actor": "user"})
        self.core.set_pinned.assert_called_once_with(SID, True)
        self.core.touch_opened.assert_called_once_with(SID)

    def test_every_error_status_and_payload(self):
        for code, expected in STATUS.items():
            with self.subTest(code=code):
                error = SpacesError(code, "Demo error", current={"rev": 7}, candidates=[{"id": "demo"}])
                self.core.get_space.side_effect = error
                response = self.request("GET", f"/spaces/{SID}")
                self.assertEqual(response.status_code, expected)
                self.assertEqual(response.json(), {"error": error.to_dict()})

    def test_bridge_forwarding_uses_path_identity_and_preserves_args(self):
        args = {"collection": "papers", "space": "foreign-desk", "data": {"notes": "Demo"}, "base_rev": 4}
        body = {"space": "foreign-desk", "session": "session_demo", "op": "data.put", "args": args}
        response = self.request("POST", f"/spaces/{SID}/bridge", json=body)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True, "result": {"records": []}})
        self.core.dispatch.assert_called_once_with(SID, "session_demo", "data.put", args)

    def test_bridge_errors_always_http_200(self):
        body = {"session": "session_demo", "op": "data.query", "args": {"collection": "papers"}}
        for code in STATUS:
            with self.subTest(code=code):
                error = SpacesError(code, "Demo error")
                self.core.dispatch.side_effect = error
                response = self.request("POST", f"/spaces/{SID}/bridge", json=body)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {"ok": False, "error": error.to_dict()})
        self.core.dispatch.side_effect = None
        self.core.dispatch.return_value = {"ok": False, "error": {"code": "session_invalid", "message": "Closed"}}
        self.assertEqual(self.request("POST", f"/spaces/{SID}/bridge", json=body).json(), self.core.dispatch.return_value)
        for invalid in (None, {}, [], {"session": "s", "op": "meta", "args": []}):
            response = self.request("POST", f"/spaces/{SID}/bridge", json=invalid)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["error"]["code"], "invalid")
        response = self.request("POST", f"/spaces/{SID}/bridge", content="{", headers={"Content-Type": "application/json"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["ok"])

    def test_invalid_space_id_never_loads_core(self):
        for method, path, kwargs in (("GET", "/spaces/INVALID/bundle", {}),
                                     ("POST", "/spaces/x/refresh", {}),
                                     ("GET", "/spaces/" + "a" * 49, {}),
                                     ("POST", "/spaces/INVALID/bridge", {"json": {}})):
            with self.subTest(path=path), patch.object(self.api, "load_core") as loader:
                response = self.request(method, path, **kwargs)
                self.assertEqual(response.status_code, 200 if path.endswith("bridge") else 400)
                self.assertEqual(response.json()["error"]["code"], "invalid")
                loader.assert_not_called()

    def test_session_close_checks_space_binding(self):
        self.core.require.side_effect = SpacesError("session_invalid", "Wrong Space")
        response = self.request("DELETE", f"/spaces/{SID}/sessions/foreign_session")
        self.assertEqual(response.status_code, 403)
        self.core.require.assert_called_once_with(SID, "foreign_session")
        self.core.close_session.assert_not_called()

    def test_host_actions_return_summary_without_project_details(self):
        for path, body in (("archive", None), ("unarchive", None), ("opened", None), ("pin", {"pinned": True})):
            with self.subTest(path=path):
                response = self.request("POST", f"/spaces/{SID}/{path}", json=body)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["id"], SID)
                self.assertNotIn("manifest", response.json())

    def test_invalid_requests_are_contract_errors(self):
        cases = [("POST", f"/spaces/{SID}/upkeep", {}),
                 ("POST", f"/spaces/{SID}/upkeep", {"action": "pause", "paused": True}),
                 ("POST", f"/spaces/{SID}/grants/net", {"decision": "approve"}),
                 ("POST", f"/spaces/{SID}/grants/net", {"decision": "grant", "scope": []}),
                 ("POST", f"/spaces/{SID}/pin", {"pinned": 1}),
                 ("POST", f"/spaces/{SID}/pin", {"pinned": True, "extra": True}),
                 ("GET", f"/spaces/{SID}/changes?since=-1", None),
                 ("GET", f"/spaces/{SID}/changes?since=no", None),
                 ("POST", f"/spaces/{SID}/revisions/no/restore", None),
                 ("POST", f"/spaces/{SID}/revisions/0/restore", None)]
        for method, path, body in cases:
            with self.subTest(path=path, body=body):
                response = self.request(method, path, json=body)
                self.assertEqual(response.status_code, 400, response.text)
                self.assertEqual(response.json()["error"]["code"], "invalid")
        self.core.decide.assert_not_called()
        self.core.upkeep_action.assert_not_called()
        self.core.set_pinned.assert_not_called()

    def test_index_and_status_aggregate_public_core_cursors(self):
        self.core.list_spaces.return_value = [DETAIL, {**DETAIL, "id": "other-desk", "attention": {"kind": "failed"}}]
        self.core.changes_since.side_effect = lambda sid, seq, limit: {"seq": 8 if sid == SID else 11}
        response = self.request("GET", "/spaces").json()
        self.assertEqual(response["seq_global"], 11)
        self.assertEqual(len(response["spaces"]), 2)
        self.assertEqual(self.request("GET", "/status").json(), {"seq_global": 11, "spaces": 2, "attention": 1})
        self.core.list_spaces.return_value = []
        self.assertEqual(self.request("GET", "/status").json(), {"seq_global": 0, "spaces": 0, "attention": 0})

    def test_blocking_core_calls_do_not_stall_event_loop(self):
        async def check():
            loop_thread = threading.get_ident()
            entered, release = threading.Event(), threading.Event()

            def blocking(sid):
                self.assertNotEqual(threading.get_ident(), loop_thread)
                entered.set()
                self.assertTrue(release.wait(timeout=2))
                return DETAIL

            self.core.get_space.side_effect = blocking
            task = asyncio.create_task(self.api.space_detail(SID))
            try:
                for _ in range(100):
                    if entered.is_set():
                        break
                    await asyncio.sleep(0.005)
                self.assertTrue(entered.is_set())
            finally:
                release.set()
            self.assertEqual(await task, DETAIL)

        asyncio.run(check())


if __name__ == "__main__":
    unittest.main()
