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
                   schedule={"kind": "cron", "expr": kwargs["schedule"], "display": kwargs["schedule"]},
                   schedule_display=kwargs["schedule"], next_run_at="2027-03-12T00:00:00+00:00",
                   last_run_at=None, last_status=None, last_error=None)
        self.jobs[jid] = job
        self.calls.append(("create", jid))
        return copy.deepcopy(job)

    def get_job(self, jid):
        return copy.deepcopy(self.jobs.get(jid))

    def list_jobs(self, include_disabled=False):
        return [copy.deepcopy(job) for job in self.jobs.values() if include_disabled or job["enabled"]]

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


class SyntheticContext:
    """Public cron response shapes, without a model, scheduler, config or host imports."""

    def __init__(self, cron=None):
        self.cron = cron if cron is not None else SyntheticCron()
        self.calls = []
        self.execution = None
        self.run_reply = None

    def current_cron_execution(self):
        return self.execution

    @staticmethod
    def format_job(job):
        prompt = job.get("prompt") or ""
        keys = ("name", "script", "enabled", "state", "next_run_at", "last_run_at",
                "last_status", "last_error")
        return {**{key: job.get(key) for key in keys}, **({"no_agent": True} if job.get("no_agent") else {}), "job_id": job["id"],
                "schedule": job.get("schedule_display"), "prompt_preview": prompt[:100] + ("..." if len(prompt) > 100 else "")}

    def dispatch_tool(self, name, args):
        import json

        assert name == "cronjob_manage", name
        self.calls.append((name, copy.deepcopy(args)))
        args = dict(args)
        action = args.pop("action")
        if action == "list":
            jobs = [self.format_job(job) for job in self.cron.list_jobs(**args)]
            return json.dumps(dict(success=True, count=len(jobs), jobs=jobs))
        if action == "create":
            job = self.cron.create_job(**args)
            return json.dumps(dict(success=True, job_id=job["id"], job=self.format_job(job)))
        jid = args.pop("job_id")
        if self.cron.get_job(jid) is None:
            return json.dumps(dict(success=False, error="Job not found"))
        if action == "remove":
            removed = self.cron.remove_job(jid)
            return json.dumps(dict(success=removed))
        if action == "run":
            if self.run_reply is not None:
                return json.dumps(self.run_reply)
            self.cron.trigger_job(jid)
            return json.dumps(dict(success=True, job=self.format_job(self.cron.get_job(jid) or {"id": jid}), note="Queued by synthetic gateway"))
        job = getattr(self.cron, action + "_job")(jid, **args)
        return json.dumps(dict(success=True, job=self.format_job(job)))


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
        self.ctx = SyntheticContext(self.cron)
        self.core = self.load("_review_customization_core", PACKAGE / "living_spaces_core/__init__.py")
        self.db = self.core.db
        stack.enter_context(patch.object(self.db, "hermes_home", return_value=self.home))
        for name in ("bridge", "feeds", "grants", "net", "projects", "records", "runs", "sessions", "upkeep"):
            setattr(self, name, importlib.import_module(self.core.__name__ + "." + name))
        self.upkeep.configure_context(self.ctx)

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
        return sid

    def schedule(self, sid, kind="agent", prompt=AGENT_PROMPT, cadence="0 * * * *"):
        return self.upkeep.schedule_upkeep(sid, kind=kind, cadence=cadence, timezone="UTC",
                                           prompt=prompt if kind == "agent" else None, actor="agent:review")

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
