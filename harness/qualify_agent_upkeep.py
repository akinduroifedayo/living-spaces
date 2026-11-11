"""Forge-only qualification using the isolated Desktop and real cron model calls.

Apply the lane's integration patches and rebuild/install the plugin first. The
harness creates a disposable public fixture, approves it with native host input,
and requests two real model runs. It never starts a gateway or scheduler.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
_argv, sys.argv = sys.argv, [sys.argv[0], "lib"]
import qualify_schedule as q
sys.argv = _argv
from guest_realm import guest
from cron import jobs as cron

core = q.core
OUT = q.RUN / "evidence/agent-upkeep"
OUT.mkdir(parents=True, exist_ok=True)
checks = []
result = {"evidence_class": "Disposable public fixture; real native Hermes cron model calls; host decisions through native mouse input"}
SID = None
TITLE = "Agent upkeep demo refreshed"
PROMPT = (
    "Maintain the public demo record in collection papers, id demo. Read it with spaces_query. "
    "Use spaces_write_records with source_owned=true and a put op containing collection papers, id demo, "
    f"source {{title: '{TITLE}', summary: 'A synthetic public demonstration, not a live research finding.'}}, "
    "and source_meta {url: 'https://example.org/demo', source_id: 'agent-demo'}. "
    "Leave all user notes and status unchanged. Do not fetch anything or change files, grants or schedules. "
    "Report completion after the tool confirms the write."
)


def check(name, observed, expected=True):
    ok = observed == expected
    checks.append({"name": name, "passed": ok, "observed": observed, "expected": expected})
    print(("PASS " if ok else "FAIL ") + name, json.dumps(observed, default=str)[:200], flush=True)
    if not ok:
        raise AssertionError(checks[-1])


def other_spaces():
    values = []
    for space in core.list_spaces():
        if space["id"] == SID:
            continue
        detail = core.get_space(space["id"])
        rows = {collection: core.query(space["id"], collection, limit=500)["records"] for collection in detail["collections"]}
        values.append([space["id"], space["head_rev"], rows])
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def history():
    return core.list_runs(SID)


def finish(known):
    return q.wait(lambda: [run for run in history() if run["id"] not in known],
                  lambda rows: rows and rows[0]["status"] not in ("queued", "running"), seconds=600, every=2)[0]


def pending_card(label):
    q.evaluate(f"""(() => {{const card=[...document.querySelectorAll('article.ls-pending')].find(e=>e.querySelector('strong')?.textContent.trim()==={json.dumps(label)}); if(card) card.id='agent-upkeep-approval'; return !!card}})()""")
    return "#agent-upkeep-approval"


def approve_schedule():
    q.press("Permissions")
    q.wait(q.page_text, lambda text: "Scheduled upkeep" in text and "Uses model calls" in text)
    selector = pending_card("Scheduled upkeep")
    text = q.evaluate(f"document.querySelector({json.dumps(selector)})?.innerText")
    check("model cost and exact prompt are visible before schedule approval", "Uses model calls" in text and PROMPT in text and "No model calls" not in text)
    q.screenshot(str(OUT / "schedule-before-approval.png"))
    q.press("Approve", selector)
    schedule = q.wait(lambda: core.get_schedule(SID), lambda s: s["status"] == "active")
    q.close_sheets()
    return schedule


def assert_source(run):
    check("native model run succeeded", run["status"], "succeeded")
    check("run has native job and execution identifiers", bool(run["detail"].get("cron_job_id") and run["detail"].get("cron_run_id")))
    record = core.records.get(SID, "papers", "demo")
    check("model wrote fresh source fields", record["source"]["title"], TITLE)
    check("user note and status survived", record["data"], {"notes": "Keep this public demo note", "status": "reading"})
    check("source metadata identifies agent upkeep", record["source_meta"]["handler"], "agent")
    check("source metadata retains public provenance", record["source_meta"]["url"], "https://example.org/demo")


visible = q.Visible().__enter__()
try:
    manifest = {"data": {"version": 1, "collections": {"papers": {"source_owned": ["title", "summary"]}}},
                "upkeep": {"handler": "agent", "prompt": PROMPT}}
    html = """<!doctype html><html><body><h1>Agent Upkeep Demo</h1><p id="title">Loading</p><p id="notes"></p>
<script type="module">
async function render() { const rows = await space.query('papers'); const row = rows.find(r => r.id === 'demo'); document.querySelector('#title').textContent = row?.source?.title || 'Waiting for upkeep'; document.querySelector('#notes').textContent = row?.data?.notes || ''; }
space.on('change', render); await render();
</script></body></html>"""
    space = core.create_space("Agent Upkeep Qualification " + str(int(time.time())), owner="Demo", author="harness", manifest=manifest, files={"index.html": html})
    SID = space["id"]
    q.SID = SID
    result["space"] = SID
    before_others = other_spaces()
    core.records.put(SID, "papers", "demo", {"notes": "Keep this public demo note", "status": "reading"}, actor="harness", base_rev=0)
    core.records.upsert_source(SID, "papers", "demo", {"title": "Waiting for upkeep"}, {"handler": "fixture"}, actor="harness")
    core.request_schedule(SID, cadence="0 7 * * *", timezone="America/Chicago", purpose="Public agent upkeep qualification", actor="harness")
    q.go_space()
    q.press("Permissions")
    q.wait(q.page_text, lambda text: "Refresh" in text and "Approve" in text)
    q.press("Approve", pending_card("Refresh"))
    q.wait(lambda: core.list_grants(SID), lambda grants: any(g["capability"] == "refresh" and g["status"] == "granted" for g in grants))
    q.close_sheets()
    schedule = approve_schedule()
    jid = schedule["cron_job_id"]
    job = cron.get_job(jid)
    check("approval creates a native local agent job", [job["no_agent"], job["deliver"], job["catch_up"]], [False, "local", True])
    check("native prompt is bound to the fixture Space", SID in job["prompt"] and "spaces_*" in job["prompt"])
    check("native job inherits configured cron tools", job.get("enabled_toolsets"), None)
    result["cron_job_id"] = jid
    known = {run["id"] for run in history()}
    q.press("Refresh now")
    for _ in range(2):
        try:
            q.press("Refresh now")
        except (LookupError, AssertionError):
            pass
    manual = finish(known)
    assert_source(manual)
    check("rapid Refresh now produces one run", len([r for r in history() if r["id"] not in known]), 1)
    check("manual trigger is recorded", manual["trigger"], "manual")
    q.wait(lambda: guest("document.body.innerText"), lambda value: value and TITLE in str(value.get("value")), seconds=30)
    q.screenshot(str(OUT / "manual-model-result.png"))
    result["manual_run"] = manual

    core.records.upsert_source(SID, "papers", "demo", {"title": "Fixture divergence for scheduled proof"}, {"handler": "fixture"}, actor="harness")
    q.evaluate('location.hash="/spaces"')
    q.wait(q.frames, lambda count: count == 0)
    known = {run["id"] for run in history()}
    cron.trigger_job(jid)
    scheduled = finish(known)
    assert_source(scheduled)
    check("native fire while Space is closed is recorded as schedule", scheduled["trigger"], "schedule")
    result["scheduled_run"] = scheduled
    q.go_space()
    q.press("Pause upkeep")
    q.wait(lambda: core.get_schedule(SID), lambda s: s["status"] == "paused")
    check("host pause disables the native agent job", cron.get_job(jid)["enabled"], False)
    changed = json.loads(json.dumps(manifest))
    changed["upkeep"]["prompt"] = PROMPT + " Keep the demo concise."
    core.write_files(SID, files={}, manifest=changed, author="harness", summary="Change agent task for approval proof")
    check("prompt change requires fresh schedule approval", core.get_schedule(SID)["status"], "requested")
    check("prompt change leaves old native job paused", cron.get_job(jid)["enabled"], False)
    core.set_status(SID, "archived", actor="harness")
    check("archive prevents another agent refresh", core.start_refresh(SID, trigger="manual", actor="harness")["status"], "blocked")
    check("other Spaces remained unchanged", other_spaces(), before_others)
    core.delete_space(SID, actor="harness", confirm=SID)
    check("deletion removes the native agent job", cron.get_job(jid), None)
    check("deletion removes only the disposable Space", SID in {s["id"] for s in core.list_spaces()}, False)
    result["fixture_deleted"] = True
except Exception as exc:
    result["error"] = str(exc)
    raise
finally:
    if SID and not result.get("fixture_deleted"):
        try:
            core.set_status(SID, "archived", actor="harness")
            result["failure_cleanup"] = "Archived disposable fixture for inspection; no future agent schedule fires."
        except Exception as exc:
            result["failure_cleanup_error"] = str(exc)
    visible.__exit__(None, None, None)
    result.update(checks=checks, passed=sum(c["passed"] for c in checks), total=len(checks))
    (OUT / "agent-upkeep.json").write_text(json.dumps(result, indent=2, default=str))
    (q.RUN / "evidence/schedule/schedule-lib.json").unlink(missing_ok=True)
    print(json.dumps({k: result[k] for k in ("passed", "total")}), flush=True)
