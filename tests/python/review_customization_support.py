"""Synthetic cron/HTTPS leaves for real customization core and adapter tests."""
from __future__ import annotations

import copy
import importlib
import importlib.util
import io
import os
from pathlib import Path
import socket
import sys
import tempfile
import types
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import httpx

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "src/living-spaces"
PUBLIC = "93.184.216.34"
AGENT_PROMPT = "Update public demo records."
SCHEDULE_FIELDS = ("cadence", "timezone", "purpose", "requested_at")


def deny_network(*args, **kwargs):
    raise AssertionError("Real sockets and DNS are forbidden in customization regressions")


class SyntheticCron:
    def __init__(self):
        self.jobs = {}
        self.executions = []
        self.calls = []
        self.serial = 0

    def create_job(self, **kwargs):
        self.serial += 1
        jid = "review-cron-" + str(self.serial)
        job = dict(kwargs, id=jid, enabled=not kwargs.get("paused", False),
                   state="paused" if kwargs.get("paused") else "scheduled",
                   next_run_at=1804809600.0)
        self.jobs[jid] = job
        self.calls.append(("create", jid))
        return copy.deepcopy(job)

    def get_job(self, jid):
        return copy.deepcopy(self.jobs.get(jid))

    def remove_job(self, jid):
        self.calls.append(("remove", jid))
        return self.jobs.pop(jid, None) is not None

    def pause_job(self, jid, reason=None):
        self.calls.append(("pause", jid))
        if jid in self.jobs:
            self.jobs[jid].update(enabled=False, state="paused", paused_reason=reason)
        return self.get_job(jid)

    def resume_job(self, jid):
        self.calls.append(("resume", jid))
        if jid in self.jobs:
            self.jobs[jid].update(enabled=True, state="scheduled")
        return self.get_job(jid)

    def trigger_job(self, jid):
        self.calls.append(("trigger", jid))
        self.jobs[jid].update(enabled=True, state="scheduled",
                              manual_run_at=datetime.now(timezone.utc).isoformat())
        return self.get_job(jid)

    def cancel_job_run(self, jid, reason=None):
        self.calls.append(("cancel", jid))
        for execution in self.executions:
            if execution["job_id"] == jid and execution["status"] in ("claimed", "running"):
                execution.update(status="cancelled", finished_at=datetime.now(timezone.utc).isoformat())
        return True

    def list_executions(self, *, job_id=None, limit=50, before_claimed_at=None):
        entries = [entry for entry in self.executions
                   if (job_id is None or entry["job_id"] == job_id)
                   and (before_claimed_at is None or entry["claimed_at"] < before_claimed_at)]
        entries.sort(key=lambda entry: (entry["claimed_at"], entry["id"]), reverse=True)
        return copy.deepcopy(entries[:max(1, min(int(limit), 500))])

    def execution(self, jid, status="running"):
        stamp = (datetime(2026, 11, 10, tzinfo=timezone.utc)
                 + timedelta(seconds=len(self.executions))).isoformat()
        entry = dict(id="review-exec-" + str(len(self.executions) + 1), job_id=jid,
                     status=status, claimed_at=stamp, started_at=stamp,
                     finished_at=stamp if status == "completed" else None, error=None)
        self.executions.append(entry)
        return entry


class Response:
    def __init__(self, status=200, headers=None, body=b"ok"):
        self.status = status
        self.headers = headers or {}
        self.length = None
        self.body = io.BytesIO(body)

    def getheader(self, name, default=None):
        return next((value for key, value in self.headers.items()
                     if key.lower() == name.lower()), default)

    def getheaders(self):
        return list(self.headers.items())

    def read1(self, size):
        return self.body.read(size)

    def close(self):
        self.body.close()


class PinnedTransport:
    def __init__(self, responses, on_response=None, observe=None):
        self.responses = list(responses)
        self.on_response = on_response
        self.observe = observe
        self.connections = []
        self.requests = []

    def connect(self, host, port, ip, timeout):
        transport = self
        self.connections.append((host, port, ip))

        class Connection:
            def request(self, method, target, body=None, headers=None):
                entry = dict(host=host, method=method, target=target, body=body, headers=headers)
                if transport.observe:
                    entry.update(transport.observe())
                transport.requests.append(entry)

            def getresponse(self):
                response = transport.responses.pop(0)
                if transport.on_response:
                    transport.on_response(response)
                return response

            def close(self):
                pass

            def abort(self):
                pass

        return Connection()


class CustomizationFixture:
    def __init__(self, stack):
        self.stack = stack
        self.home = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="spaces-customization-")))
        stack.enter_context(patch.dict(os.environ, HERMES_HOME=str(self.home),
                                       LIVING_SPACES_DB=str(self.home / "spaces.db")))
        for name in ("connect", "connect_ex", "sendto"):
            stack.enter_context(patch.object(socket.socket, name, deny_network))
        for name in ("getaddrinfo", "gethostbyname", "gethostbyname_ex"):
            stack.enter_context(patch.object(socket, name, deny_network))
        stack.enter_context(patch.object(socket, "create_connection", deny_network))
        self.cron = SyntheticCron()
        parent = types.ModuleType("cron")
        parent.__path__ = []
        jobs = types.ModuleType("cron.jobs")
        for name in ("create_job", "get_job", "remove_job", "pause_job", "resume_job",
                     "trigger_job", "cancel_job_run"):
            setattr(jobs, name, getattr(self.cron, name))
        ledger = types.ModuleType("cron.executions")
        ledger.list_executions = self.cron.list_executions
        parent.jobs, parent.executions = jobs, ledger
        for name, module in (("cron", parent), ("cron.jobs", jobs), ("cron.executions", ledger)):
            self._install_module(name, module)
        self.core = self.load("_review_customization_core", PACKAGE / "living_spaces_core/__init__.py")
        self.db = self.core.db
        stack.enter_context(patch.object(self.db, "hermes_home", return_value=self.home))
        for name in ("bridge", "feeds", "grants", "net", "projects", "records", "runs", "schedules", "sessions"):
            setattr(self, name, importlib.import_module(self.core.__name__ + "." + name))
        stack.enter_context(patch.object(self.schedules, "_cron", return_value=self.cron))

    def _install_module(self, name, module):
        missing = object()
        original = sys.modules.get(name, missing)

        def restore():
            if original is missing:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original

        self.stack.callback(restore)
        sys.modules[name] = module

    def load(self, name, path):
        original = {key: value for key, value in sys.modules.items()
                    if key == name or key.startswith(name + ".")}

        def restore():
            for key in list(sys.modules):
                if key == name or key.startswith(name + "."):
                    sys.modules.pop(key)
            sys.modules.update(original)

        self.stack.callback(restore)
        spec = importlib.util.spec_from_file_location(name, path, submodule_search_locations=[str(path.parent)])
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module

    def make(self, handler="agent", url="https://example.org/feed"):
        upkeep = ({"handler": "agent", "prompt": AGENT_PROMPT} if handler == "agent" else
                  {"handler": "feed", "sources": [{"id": "demo", "url": url, "collection": "items"}]})
        sid = self.projects.create_space("Review Space", owner="Review", author="agent:review",
                                        files={"index.html": "<h1>Demo</h1>"},
                                        manifest={"upkeep": upkeep})["id"]
        self.approve_refresh(sid)
        return sid

    def refresh_grant(self, sid):
        return next(row for row in self.grants.list_grants(sid) if row["capability"] == "refresh")

    def approve_refresh(self, sid):
        row = self.refresh_grant(sid)
        displayed = row["requested_scope"] if row["requested_scope"] is not None else row["scope"]
        return self.grants.decide(sid, "refresh", "grant", requested_scope=copy.deepcopy(displayed))

    def approve_schedule(self, sid):
        self.schedules.request_schedule(sid, cadence="0 * * * *", timezone="UTC",
                                        purpose="Demo", actor="agent:review")
        return self.schedules.decide_schedule(
            sid, "approve", requested_upkeep=self.projects.bundle(sid)["manifest"]["upkeep"])

    def change_upkeep(self, sid, upkeep):
        manifest = self.projects.bundle(sid)["manifest"]
        manifest["upkeep"] = upkeep
        return self.projects.write_files(sid, files={}, manifest=manifest,
                                         author="agent:review", summary="Change task")

    def client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        api = self.load("_review_customization_api", PACKAGE / "dashboard/plugin_api.py")
        api.load_core = lambda: self.core
        app = FastAPI()
        app.include_router(api.router)
        return self.stack.enter_context(TestClient(app))

    def source_ops(self, sid, ops):
        if not hasattr(self, "plugin"):
            self.plugin = self.load("_review_customization_plugin", PACKAGE / "__init__.py")
        return self.plugin.spaces_write_records(
            self.core, {"space": sid, "source_owned": True, "ops": ops}, "Review")

    def source(self, sid, title, rev=None):
        op = {"op": "put", "collection": "items", "id": "one", "source": {"title": title}}
        if rev is not None:
            op["base_rev"] = rev
        return self.source_ops(sid, [op])

    def transport(self, responses, on_response=None, observe=None):
        transport = PinnedTransport(responses, on_response, observe)
        self.stack.enter_context(patch.object(self.net, "_resolve", return_value=[PUBLIC]))
        self.stack.enter_context(patch.object(self.net, "_connection", transport.connect))
        return transport

    def feed_transports(self, body):
        pinned = self.transport([Response(body=body)])
        legacy_requests = []

        def respond(request):
            legacy_requests.append(str(request.url))
            return httpx.Response(200, content=body)

        client_type = httpx.Client

        def client(*args, **kwargs):
            instance = client_type(transport=httpx.MockTransport(respond))
            self.stack.callback(instance.close)
            return instance

        # Keep both real transport boundaries observable across the pinned-helper repair.
        self.stack.enter_context(patch.object(httpx, "Client", side_effect=client))
        return pinned, legacy_requests
