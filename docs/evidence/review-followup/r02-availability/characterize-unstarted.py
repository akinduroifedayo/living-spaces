import json
import sys
from pathlib import Path

ROOT = Path('/Volumes/Expansion/Development/Projects/living-spaces-wt/r02-repair')
sys.path.insert(0, str(ROOT / 'src/living-spaces'))
from living_spaces_core import grants, projects, runs, schedules
from living_spaces_core.errors import SpacesError
from cron import executions, jobs

assert jobs.load_jobs() == []
sid = projects.create_space('Unstarted one-shot probe', owner='Public fixture', author='harness-fixture', files={'index.html': '<main>Public fixture</main>'}, manifest={'upkeep': {'handler': 'agent', 'prompt': 'Disposable fixture. Do not execute.'}})['id']
try:
    grants.decide(sid, 'refresh', 'grant')
    queued = runs.start_refresh(sid, trigger='manual', actor='harness-fixture')
    jid = queued['detail']['cron_job_id']
    before = jobs.get_job(jid)
    assert queued['status'] == 'queued'
    assert executions.list_executions(job_id=jid) == []
    grants.decide(sid, 'refresh', 'revoke')
    assert jobs.get_job(jid) is None
    assert executions.list_executions(job_id=jid) == []
    try:
        granted = grants.decide(sid, 'refresh', 'grant')
    except SpacesError as exc:
        granted = {'error': exc.to_dict()}
    print(json.dumps({'evidence_class': 'Actual R02 core, SQLite and native job/ledger adapters in a disposable home. No gateway ticker, cron worker or model run.', 'before_native_job': {k: before.get(k) for k in ('id', 'enabled', 'state', 'fire_claim', 'run_claim', 'manual_run_at')}, 'after_native_job': jobs.get_job(jid), 'native_executions': executions.list_executions(job_id=jid), 'run_after_revoke': runs.get_run(queued['id']), 'regrant': granted, 'not_claimed': ['Actual native process interruption', 'Concurrent removal/claim race', 'Desktop UI', 'Release acceptance']}, indent=1))
finally:
    projects.set_status(sid, 'archived', actor='harness-fixture')
    projects.delete_space(sid, actor='harness-fixture', confirm=sid)
    assert jobs.load_jobs() == []
