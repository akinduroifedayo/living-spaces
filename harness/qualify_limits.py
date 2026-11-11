"""R1-08 limits in the isolated Desktop. Run serially under Forge's control.

Guest calls use guest_realm.guest and the installed bridge. Agent calls use the
registered tool handlers with real core storage, not a model/chat invocation.
The disposable fixture uses the shipped useSaveState and SaveIndicator. This
does not qualify save handling in arbitrary model-built applications.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import time
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
_argv, sys.argv = sys.argv, [sys.argv[0], "lib"]
try:
    import qualify_schedule as q
finally:
    sys.argv = _argv
import guest_realm
from guest_realm import guest
from living_spaces_core import db, limits

SID = "limits-probe"
PROTECTED = ("research-desk", "pair-play")
TABLES = ("revisions", "records", "changes", "recovery_points", "grants", "audit", "runs", "schedules", "logs", "sessions")
OUT = q.RUN / "evidence" / "limits" / time.strftime("%Y%m%d-%H%M%S")
checks = []
result = {
    "evidence_class": "isolated Desktop guest bridge, registered agent handlers, canonical SQLite",
    "fixture": SID,
    "scope": "fixture save UI uses shipped kit; no model turn and no claim about model-built app save UI",
    "attempts": [],
}

HTML = """<!doctype html><html><head><meta charset="utf-8"><title>Limits Probe</title>
<link rel="stylesheet" href="kit/spaces-kit.css"></head><body>
<main id="app"></main><script type="module" src="probe.mjs"></script></body></html>"""
SCRIPT = """import { h, render } from 'preact'
import { useSaveState, SaveIndicator, useCollection } from 'spaces-kit'

function Probe() {
  const save = useSaveState()
  const { records, loading, error } = useCollection('probe')
  globalThis.limitsProbe = async (mode, note) => {
    globalThis.limitsStates = []
    let reply
    await save.run(async () => {
      try {
        let value
        if (mode === 'batch') {
          value = await space.batch(Array.from({ length: 501 }, (_, i) =>
            ({ op: 'put', collection: 'probe', id: `overflow-${i}`, data: { note: 'Rejected batch' } })))
        } else if (mode === 'data') {
          value = await space.put('probe', 'overflow', { text: 'x'.repeat(262134) })
        } else if (mode === 'bridge') {
          value = await space.batch(Array.from({ length: 5 }, (_, i) =>
            ({ op: 'put', collection: 'probe', id: `bridge-${i}`, data: { text: 'x'.repeat(210000) } })))
        } else {
          value = await space.put('probe', null, { note })
        }
        reply = { ok: true, result: value }
        return value
      } catch (error) {
        reply = { ok: false, error: { code: error.code, message: error.message,
          limit: error.limit, actual: error.actual } }
        throw error
      }
    })
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))
    return reply
  }
  return h('section', null,
    h('h1', null, 'Limits Probe'),
    h('p', { id: 'revision' }, `Usable revision ${space.meta.space.rev}`),
    h('div', { id: 'save', 'data-state': save.state }, h(SaveIndicator, save)),
    h('p', null, loading ? 'Loading records' : error ? error.message : 'Canonical records'),
    h('ul', null, records.map(record => h('li', { key: record.id }, record.data.note || record.id))))
}
globalThis.limitsStates = []
new MutationObserver(() => {
  const state = document.querySelector('#save')?.dataset.state
  if (state && globalThis.limitsStates.at(-1) !== state) globalThis.limitsStates.push(state)
}).observe(document.body, { childList: true, subtree: true, attributes: true, characterData: true })
render(h(Probe), document.querySelector('#app'))
"""


def check(name, observed, expected=True):
    passed = observed == expected
    checks.append({"name": name, "passed": passed, "observed": observed, "expected": expected})
    print(("PASS " if passed else "FAIL ") + name, json.dumps(observed, default=str)[:180])
    return passed


def require(name, observed, expected=True):
    if not check(name, observed, expected):
        raise AssertionError(name)


def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def snapshot(sid, *, complete=False):
    tables = TABLES if complete else ("revisions", "records", "changes", "recovery_points", "grants")
    with db.read() as conn:
        space = dict(db.space(conn, sid))
        if not complete:
            space.pop("last_opened_at")
        data = {"space": space}
        for table in tables:
            data[table] = [dict(row) for row in conn.execute(f"SELECT * FROM {table} WHERE space=? ORDER BY rowid", (sid,))]
        shas = {sha for rev in data["revisions"] for sha in json.loads(rev["files"]).values()}
        data["blobs"] = {sha: bytes(conn.execute("SELECT content FROM blobs WHERE sha=?", (sha,)).fetchone()[0]).hex()
                         for sha in sorted(shas)}
    return encode(data)


def frame_state():
    response = guest("({id: space.meta.space.id, rev: space.meta.space.rev, text: document.body.innerText, "
                     "state: document.querySelector('#save')?.dataset.state, states: globalThis.limitsStates})")
    return response.get("value") if response and response.get("ok") else None


def open_fixture(rev):
    q.evaluate(f"location.hash = {json.dumps('/spaces?space=' + SID)}")
    return q.wait(frame_state, lambda value: value and value.get("id") == SID and value.get("rev") == rev
                  and "Canonical records" in value.get("text", ""), 30, .25)


def reopen_fixture(rev):
    q.go_index()
    q.wait(lambda: guest_realm.open_sessions(SID), lambda value: not value, 15)
    return open_fixture(rev)


def watch_host():
    q.evaluate("""(() => {
      globalThis.limitsHostObserver?.disconnect()
      globalThis.limitsHostSamples = []
      const sample = () => {
        const visible = element => element.getClientRects().length && getComputedStyle(element).visibility !== 'hidden'
        const messages = [...document.querySelectorAll('[role="alert"],[role="status"],[data-sonner-toast],[data-radix-toast-viewport],.toast')]
          .filter(visible).map(element => element.innerText)
        const entry = { text: document.body.innerText, messages }
        const samples = globalThis.limitsHostSamples
        if (JSON.stringify(samples.at(-1)) !== JSON.stringify(entry)) samples.push(entry)
      }
      sample()
      globalThis.limitsHostSample = sample
      globalThis.limitsHostObserver = new MutationObserver(sample)
      globalThis.limitsHostObserver.observe(document.body, {childList: true, subtree: true, characterData: true, attributes: true})
    })()""")


def host_evidence(name):
    time.sleep(2.5)
    samples = q.evaluate("(() => { globalThis.limitsHostObserver.disconnect(); globalThis.limitsHostSample(); return globalThis.limitsHostSamples })()")
    require(name + " host observations present", isinstance(samples, list) and bool(samples))
    positive = re.compile(r"\b(saved|successfully saved|changes saved)\b", re.IGNORECASE)
    false_saved = [message for sample in (samples[1:] or samples) for message in sample["messages"]
                   if positive.search(re.sub(r"\bnot saved\b", "", message, flags=re.IGNORECASE))]
    check(name + " host never announces Saved for rejected work", false_saved, [])
    q.screenshot(str(OUT / (name + ".png")))
    return samples


def assert_limit(name, reply, maximum, actual=None):
    error = reply.get("error") or {}
    check(name + " returns typed limit", (reply.get("ok"), error.get("code")), (False, "limit"))
    check(name + " includes limit", error.get("limit"), maximum)
    measured = error.get("actual")
    check(name + " includes numeric actual above limit", type(measured) is int and measured > maximum)
    if actual is not None:
        check(name + " reports exact actual", measured, actual)
    check(name + " explains failure", isinstance(error.get("message"), str) and bool(error["message"]))


def agent_tools():
    package = q.REPO / "src/living-spaces"
    spec = importlib.util.spec_from_file_location("limits_probe_plugin", package / "__init__.py",
                                                 submodule_search_locations=[str(package)])
    plugin = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = plugin
    spec.loader.exec_module(plugin)
    registered = {}
    plugin.register(SimpleNamespace(register_tool=lambda **tool: registered.update({tool["name"]: tool}),
                                    register_skill=lambda *args, **kwargs: None))
    return registered


def tool_call(tools, name, args):
    return json.loads(tools[name]["handler"](args, profile_name="LimitsProbe"))


def guest_call(mode, note=None):
    response = guest(f"Promise.race([globalThis.limitsProbe({json.dumps(mode)}, {json.dumps(note)}), "
                     "new Promise((_, reject) => setTimeout(() => reject(new Error('Guest write timed out')), 15000))])")
    require(mode + " guest call settled", bool(response and response.get("ok")))
    return response["value"]


def guest_limits():
    for mode, maximum, actual in (("batch", limits.BATCH_OPS, 501), ("data", limits.DATA_BYTES, 262145),
                                  ("bridge", limits.BRIDGE_BYTES, None)):
        name = "guest-" + mode
        rev = q.core.get_space(SID)["head_rev"]
        reopen_fixture(rev)
        prime = guest_call("retry", "Prime " + name)
        require(name + " prior successful write acknowledged", prime.get("ok"))
        q.wait(q.page_text, lambda text: bool(re.search(r"\bSaved\b", text)), 10)
        before = snapshot(SID)
        watch_host()
        reply = guest_call(mode)
        attempt = {"name": name, "reply": reply}
        result["attempts"].append(attempt)
        assert_limit(name, reply, maximum, actual)
        state = q.wait(frame_state, lambda value: value and value.get("state") in ("failed", "saved", "conflict"), 10)
        check(name + " shipped kit shows failed", state["state"], "failed")
        check(name + " frame never shows Saved for rejected work", "saved" in state["states"] or "Saved" in state["text"], False)
        check(name + " canonical project and data unchanged", snapshot(SID) == before)
        host = host_evidence(name)
        attempt.update(frame=state, host=host)
        opened = reopen_fixture(rev)
        check(name + " previous revision still opens", (opened["rev"], "Original demo note" in opened["text"]), (rev, True))
        note = "Recovered " + name
        recovery = guest_call("retry", note)
        require(name + " next valid guest write succeeds", recovery.get("ok"))
        recovered = q.wait(frame_state, lambda value: value and value["state"] == "saved" and note in value["text"], 15)
        require(name + " saved retry is durable", q.core.records.get(SID, "probe", recovery["result"]["id"])["data"], {"note": note})
        attempt["recovery_frame"] = recovered


def agent_limits(tools):
    for mode in ("batch", "data", "file", "files"):
        name = "agent-" + mode
        rev = q.core.get_space(SID)["head_rev"]
        reopen_fixture(rev)
        before = snapshot(SID)
        if mode in ("batch", "data"):
            tool = "spaces_write_records"
            ops = ([{"op": "put", "collection": "probe", "id": f"overflow-{i}", "data": {}} for i in range(501)]
                   if mode == "batch" else [{"op": "put", "collection": "probe", "id": "overflow", "data": {"text": "x" * 262134}}])
            args = {"space": SID, "ops": ops}
            maximum, actual = (500, 501) if mode == "batch" else (262144, 262145)
        else:
            tool = "spaces_write_files"
            count = len(q.core.list_files(SID))
            files = ({"oversized.txt": "x" * (limits.FILE_BYTES + 1)} if mode == "file" else
                     {f"overflow-{i}.txt": "Public fixture" for i in range(limits.PROJECT_FILES + 1 - count)})
            args = {"space": SID, "files": files, "summary": "Rejected limit probe", "base_rev": rev}
            maximum, actual = (limits.FILE_BYTES, limits.FILE_BYTES + 1) if mode == "file" else (600, 601)
        watch_host()
        reply = tool_call(tools, tool, args)
        attempt = {"name": name, "reply": reply}
        result["attempts"].append(attempt)
        assert_limit(name, reply, maximum, actual)
        check(name + " canonical project and data unchanged", snapshot(SID) == before)
        host = host_evidence(name)
        state = frame_state()
        attempt.update(frame=state, host=host)
        check(name + " frame remains Ready without false Saved", state["state"], "idle")
        opened = reopen_fixture(rev)
        check(name + " previous revision still opens", (opened["rev"], "Original demo note" in opened["text"]), (rev, True))
        if mode in ("batch", "data"):
            note = "Recovered " + name
            recovery = tool_call(tools, tool, {"space": SID, "ops": [{"op": "put", "collection": "probe",
                                 "id": "retry-" + mode, "data": {"note": note}}]})
            require(name + " next valid tool write succeeds", recovery.get("ok"))
            q.wait(frame_state, lambda value: value and note in value["text"], 15)
            require(name + " retry is durable", q.core.records.get(SID, "probe", "retry-" + mode)["data"], {"note": note})
        else:
            path = "recovered-" + mode + ".txt"
            recovery = tool_call(tools, tool, {"space": SID, "files": {path: "Complete public fixture"},
                                  "summary": "Recovered limit probe", "base_rev": rev})
            require(name + " next valid tool write succeeds", recovery.get("ok"))
            require(name + " revision advances once", q.core.get_space(SID)["head_rev"], rev + 1)
            open_fixture(rev + 1)
            require(name + " retry file is durable", q.core.read_file(SID, path)["text"], "Complete public fixture")
        attempt["recovery"] = recovery


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    created = False
    protected = {}
    expected_db = q.RUN / "home/plugin-data/living-spaces/spaces.db"
    try:
        require("core and guest helpers target the isolated database", db.db_path().resolve() == expected_db.resolve()
                == guest_realm.DB.resolve() and expected_db.is_file())
        require("reserved disposable fixture is absent", SID not in {space["id"] for space in q.core.list_spaces()})
        q.go_index()
        q.wait(lambda: q.evaluate('document.querySelectorAll("iframe").length'), lambda count: count == 0, 20)
        q.wait(lambda: [session for sid in PROTECTED for session in guest_realm.open_sessions(sid)], lambda rows: not rows, 15)
        for sid in PROTECTED:
            protected[sid] = snapshot(sid, complete=True)
            (OUT / (sid + "-before.json")).write_bytes(protected[sid])
        fixture = q.core.create_space("Limits Probe", owner="LimitsProbe", author="agent:LimitsProbe",
                                     files={"index.html": HTML, "probe.mjs": SCRIPT}, libraries=["spaces-kit"])
        created = fixture["id"]
        require("fixture has the reserved identity", fixture["id"], SID)
        q.core.records.put(SID, "probe", "original", {"note": "Original demo note"}, actor="app")
        result["source_sha256"] = {str(path.relative_to(q.REPO)): hashlib.sha256(path.read_bytes()).hexdigest()
                                   for path in (q.REPO / "src/living-spaces/__init__.py",
                                                q.REPO / "src/living-spaces/living_spaces_core/limits.py")}
        with q.Visible():
            require("host visible under focus emulation", q.evaluate("document.visibilityState"), "visible")
            open_fixture(fixture["head_rev"])
            guest_limits()
            agent_limits(agent_tools())
    except Exception as exc:
        result["exception"] = f"{type(exc).__name__}: {exc}"
        check("harness completed all scenarios", False)
    finally:
        if created:
            try:
                q.evaluate("globalThis.limitsHostObserver?.disconnect()")
                q.go_index()
                q.wait(lambda: guest_realm.open_sessions(created), lambda rows: not rows, 15)
            except Exception as exc:
                result["close_error"] = str(exc)
            try:
                q.core.delete_space(created, actor="agent:LimitsProbe", confirm=created)
                check("disposable fixture deleted", created not in {space["id"] for space in q.core.list_spaces()})
            except Exception as exc:
                result["cleanup_error"] = str(exc)
                check("disposable fixture deleted", False)
        for sid, before in protected.items():
            try:
                after = snapshot(sid, complete=True)
                (OUT / (sid + "-after.json")).write_bytes(after)
                check(sid + " canonical snapshot byte-identical", after == before)
                result.setdefault("protected_sha256", {})[sid] = {"before": hashlib.sha256(before).hexdigest(),
                                                                  "after": hashlib.sha256(after).hexdigest()}
            except Exception as exc:
                check(sid + " snapshot verified", False)
                result.setdefault("snapshot_errors", {})[sid] = str(exc)
        result.update(checks=checks, passed=sum(item["passed"] for item in checks), total=len(checks))
        result["verdict"] = "PASS" if checks and all(item["passed"] for item in checks) else "FAIL"
        (OUT / "limits.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
        print(json.dumps({key: result[key] for key in ("verdict", "passed", "total")}))
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
