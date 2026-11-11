import hashlib
import json
from pathlib import Path

from cron import cancellation, executions, jobs

sources = [Path(module.__file__) for module in (cancellation, executions, jobs)]
before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}
assert jobs.load_jobs() == []
job = jobs.create_job(prompt="Disposable cancellation protocol fixture. Never execute.", schedule="in 1h", paused=True, no_agent=False, deliver="local")
jid = job["id"]
execution = None
try:
    claim = {"at": "2026-11-11T01:00:00-06:00", "by": "r02-disposable-characterization"}
    jobs.update_job(jid, {"fire_claim": claim})
    paused = jobs.pause_job(jid, reason="R02 protocol characterization")
    assert paused["id"] == jid and paused["enabled"] is False
    assert paused["fire_claim"] == claim
    execution = executions.create_execution(jid, source="manual")
    executions.mark_execution_running(execution["id"])
    result = jobs.cancel_job_run(jid, reason="R02 protocol characterization")
    observed = executions.get_execution(execution["id"])
    assert result["success"] is True and result["cancelled"] is True
    assert result["execution_id"] == execution["id"]
    assert observed["status"] == "running"
    assert cancellation.cancel_requested(execution["id"])
    print(json.dumps({"evidence_class": "Source-function characterization through real native adapters and disposable native stores. Synthetic claim and execution descriptors, no actual cron worker.", "adapter_chain": ["cron.jobs.pause_job", "cron.jobs.update_job", "cron.executions.create_execution", "cron.executions.mark_execution_running", "cron.jobs.cancel_job_run", "cron.cancellation.cancel_run", "cron.executions.get_execution"], "observations": {"pause_preserves_existing_fire_claim": True, "cancel_acknowledgement": result, "native_execution_status_after_cancel_acknowledgement": observed["status"], "cancel_marker_present": True}, "not_claimed": ["Actual agent or script interruption", "Claim-versus-pause concurrency qualification", "Cross-store atomicity", "Product repair", "Full suite", "Live Desktop", "Release acceptance"]}))
finally:
    if execution is not None:
        executions.finish_execution(execution["id"], success=False, cancelled=True, error="Disposable fixture cleanup, not worker completion evidence")
        cancellation.clear_cancel(execution["id"])
    jobs.remove_job(jid)
    assert jobs.load_jobs() == []
    assert all(hashlib.sha256(path.read_bytes()).hexdigest() == before[str(path)] for path in sources)
    print(json.dumps({"cleanup": "No native jobs remain in disposable home; fixture ledger retained as terminal history.", "native_sources_unchanged": True}))
