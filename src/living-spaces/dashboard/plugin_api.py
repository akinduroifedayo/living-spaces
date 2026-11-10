"""Desktop REST adapter for the public Living Spaces core API."""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

from fastapi import APIRouter, Body, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.concurrency import run_in_threadpool

_spec = importlib.util.spec_from_file_location(
    "living_spaces_api_loader", Path(__file__).resolve().parent.parent / "_core.py"
)
_loader = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_loader)
load_core = _loader.load_core
_sandbox_spec = importlib.util.spec_from_file_location(
    "living_spaces_sandbox", Path(__file__).resolve().parent / "_sandbox.py"
)
_sandbox = importlib.util.module_from_spec(_sandbox_spec)
_sandbox_spec.loader.exec_module(_sandbox)
SPACE_ID = re.compile(r"[a-z0-9][a-z0-9-]{1,47}\Z")
SUMMARY_FIELDS = {"id", "name", "description", "owner", "status", "head_rev", "accent", "icon", "pinned",
                  "updated_at", "last_opened_at", "freshness", "schedule", "attention"}


class SpacesRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def route(request):
            try:
                return await handler(request)
            except RequestValidationError:
                error = {"code": "invalid", "message": "Invalid request body or query parameters."}
                bridge = request.url.path.endswith("/bridge")
                return JSONResponse({"ok": False, "error": error} if bridge else {"error": error},
                                    status_code=200 if bridge else 400)

        return route


router = APIRouter(route_class=SpacesRoute)


async def _run(space_id, action, *, bridge=False):
    if space_id is not None and not SPACE_ID.fullmatch(space_id):
        error = {"code": "invalid", "message": "Invalid space_id."}
        return JSONResponse({"ok": False, "error": error} if bridge else {"error": error},
                            status_code=200 if bridge else 400)

    def invoke():
        core = load_core()
        try:
            return action(core)
        except core.SpacesError as err:
            payload = {"error": err.to_dict()}
            if bridge:
                payload["ok"] = False
            return JSONResponse(payload, status_code=200 if bridge else err.http_status)

    return await run_in_threadpool(invoke)


def _invalid(core, message):
    raise core.SpacesError("invalid", message)


def _body(core, body, allowed, required=()):
    if not isinstance(body, dict) or set(body) - set(allowed) or set(required) - set(body):
        _invalid(core, "Invalid request fields.")
    return body


def _index(core):
    spaces = core.list_spaces(include_archived=True)
    seq = max((core.changes_since(space["id"], 0, limit=1)["seq"] for space in spaces), default=0)
    return {"spaces": spaces, "seq_global": seq}


@router.get("/spaces")
async def spaces_list():
    return await _run(None, _index)


@router.get("/status")
async def status():
    def action(core):
        index = _index(core)
        return {"seq_global": index["seq_global"], "spaces": len(index["spaces"]),
                "attention": sum(bool(space.get("attention")) for space in index["spaces"])}
    return await _run(None, action)


@router.get("/spaces/{space_id}")
async def space_detail(space_id: str):
    return await _run(space_id, lambda core: core.get_space(space_id))


@router.get("/spaces/{space_id}/bundle")
async def space_bundle(space_id: str):
    def action(core):
        bundle = core.bundle(space_id)
        try:
            sandbox = _sandbox.trusted_document()
        except (OSError, UnicodeError, ValueError):
            return JSONResponse({"error": {"code": "unavailable", "message":
                "The packaged Living Spaces sandbox is unavailable. Reinstall Living Spaces."}}, status_code=503)
        return {**bundle, "sandbox": sandbox}
    return await _run(space_id, action)


@router.post("/spaces/{space_id}/sessions")
async def session_open(space_id: str):
    return await _run(space_id, lambda core: core.open_session(space_id))


@router.delete("/spaces/{space_id}/sessions/{session}")
async def session_close(space_id: str, session: str):
    def action(core):
        core.require(space_id, session)
        core.close_session(session)
        return {"closed": True}
    return await _run(space_id, action)


@router.post("/spaces/{space_id}/bridge")
async def bridge(space_id: str, body=Body(default=None)):
    def action(core):
        if not isinstance(body, dict):
            _invalid(core, "Bridge body must be an object.")
        session, op, args = body.get("session"), body.get("op"), body.get("args")
        if not isinstance(session, str) or not session or not isinstance(op, str) or not op or not isinstance(args, dict):
            _invalid(core, "Bridge requires session, op and object args.")
        return core.dispatch(space_id, session, op, args)
    return await _run(space_id, action, bridge=True)


@router.get("/spaces/{space_id}/changes")
async def changes(space_id: str, since: int = Query(default=0, ge=0)):
    return await _run(space_id, lambda core: core.changes_since(space_id, since))


@router.get("/spaces/{space_id}/runs")
async def runs(space_id: str, limit: int = Query(default=50, ge=1, le=500)):
    return await _run(space_id, lambda core: core.list_runs(space_id, limit=limit))


@router.post("/spaces/{space_id}/refresh")
async def refresh(space_id: str):
    return await _run(space_id, lambda core: core.start_refresh(space_id, trigger="manual", actor="user"))


@router.get("/spaces/{space_id}/grants")
async def grants(space_id: str):
    return await _run(space_id, lambda core: {"grants": core.list_grants(space_id),
                      "future": core.grants.FUTURE, "audit": core.audit_log(space_id)})


@router.post("/spaces/{space_id}/grants/{cap}")
async def grant_decide(space_id: str, cap: str, body=Body(default=None)):
    def action(core):
        _body(core, body, ("decision", "scope"), ("decision",))
        if body["decision"] not in ("grant", "deny", "revoke"):
            _invalid(core, "decision must be grant, deny or revoke.")
        if "scope" in body and not isinstance(body["scope"], dict):
            _invalid(core, "scope must be an object.")
        return core.decide(space_id, cap, body["decision"], actor="user", scope=body.get("scope"))
    return await _run(space_id, action)


@router.get("/spaces/{space_id}/schedule")
async def schedule_get(space_id: str):
    return await _run(space_id, lambda core: core.get_schedule(space_id))


@router.post("/spaces/{space_id}/schedule")
async def schedule_update(space_id: str, body=Body(default=None)):
    def action(core):
        _body(core, body, ("decision", "paused"))
        if set(body) == {"decision"} and body["decision"] in ("approve", "deny"):
            return core.decide_schedule(space_id, body["decision"], actor="user")
        if set(body) == {"paused"} and isinstance(body["paused"], bool):
            return core.pause_schedule(space_id, body["paused"], actor="user")
        _invalid(core, "Supply decision approve/deny or a boolean paused.")
    return await _run(space_id, action)


@router.get("/spaces/{space_id}/revisions")
async def revisions(space_id: str):
    return await _run(space_id, lambda core: core.list_revisions(space_id))


@router.post("/spaces/{space_id}/revisions/{rev}/restore")
async def restore(space_id: str, rev: int):
    def action(core):
        if rev < 1:
            _invalid(core, "rev must be positive.")
        return core.restore_revision(space_id, rev, author="user")
    return await _run(space_id, action)


@router.get("/spaces/{space_id}/logs")
async def logs(space_id: str, limit: int = Query(default=100, ge=1, le=2000), level: str | None = None):
    return await _run(space_id, lambda core: core.read_logs(space_id, limit=limit, level=level))


async def _change(space_id, name, *args, **kwargs):
    def action(core):
        getattr(core, name)(space_id, *args, **kwargs)
        return _summary(core, space_id)
    return await _run(space_id, action)


def _summary(core, space_id):
    return {key: value for key, value in core.get_space(space_id).items() if key in SUMMARY_FIELDS}


@router.post("/spaces/{space_id}/archive")
async def archive(space_id: str):
    return await _change(space_id, "set_status", "archived", actor="user")


@router.post("/spaces/{space_id}/unarchive")
async def unarchive(space_id: str):
    return await _change(space_id, "set_status", "active", actor="user")


@router.post("/spaces/{space_id}/pin")
async def pin(space_id: str, body=Body(default=None)):
    def action(core):
        _body(core, body, ("pinned",), ("pinned",))
        if not isinstance(body["pinned"], bool):
            _invalid(core, "pinned must be a boolean.")
        core.set_pinned(space_id, body["pinned"])
        return _summary(core, space_id)
    return await _run(space_id, action)


@router.post("/spaces/{space_id}/opened")
async def opened(space_id: str):
    return await _change(space_id, "touch_opened")


@router.delete("/spaces/{space_id}")
async def delete(space_id: str, confirm: str = ""):
    return await _run(space_id, lambda core: core.delete_space(space_id, actor="user", confirm=confirm))
