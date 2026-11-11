import ast
import copy
from contextlib import ExitStack
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
for name in ('home', 'tmp', 'evidence'):
    (ROOT / '.run' / name).mkdir(exist_ok=True)
os.environ.update(HERMES_HOME=str(ROOT / '.run/home'), TMPDIR=str(ROOT / '.run/tmp'),
                  LIVING_SPACES_DB=str(ROOT / '.run/home/spaces.db'), PYTHONDONTWRITEBYTECODE='1')
import tempfile
tempfile.tempdir = str(ROOT / '.run/tmp')
from tests.python.review_customization_support import CustomizationFixture, Response, PUBLIC, SCHEDULE_FIELDS


def snapshot(fx, sid):
    row = fx.schedules.get_schedule(sid)
    return {key: row[key] for key in SCHEDULE_FIELDS}


def error(fx, fn):
    try:
        return {'result': fn()}
    except fx.core.SpacesError as exc:
        return {'error': exc.to_dict()}


def retain_db(fx, name):
    with fx.db.read() as source:
        target = sqlite3.connect(ROOT / '.run/evidence' / (name + '.db'))
        source.backup(target)
        target.close()


def missing_upkeep(fx):
    sid = fx.make()
    fx.schedules.request_schedule(sid, cadence='0 * * * *', timezone='UTC', purpose='Demo', actor='agent:review')
    body = {'decision': 'approve', 'requested_schedule': snapshot(fx, sid)}
    response = fx.client().post(f'/spaces/{sid}/schedule', json=body)
    assert response.status_code == 200 and response.json()['status'] == 'active'
    assert len(fx.cron.jobs) == 1
    retain_db(fx, 'missing-upkeep')
    return {'classification': 'counterexample', 'request': body, 'http_status': response.status_code,
            'response': response.json(), 'jobs': fx.cron.jobs,
            'required': 'REST approval must bind the displayed upkeep snapshot as well as all four schedule fields'}


def ui_input(fx):
    sid = fx.make()
    fx.schedules.request_schedule(sid, cadence='0 7 1 * *', timezone='UTC', purpose='Once per month', actor='agent:review')
    space = fx.projects.get_space(sid)
    fields = snapshot(fx, sid)
    (ROOT / '.run/ui-input.json').write_text(json.dumps({'space':space, 'schedule':fx.schedules.get_schedule(sid),
                                                       'grants':{'grants':fx.grants.list_grants(sid)},
                                                       'snapshot':fields}, indent=2))
    retain_db(fx, 'ui-input')
    return {'classification':'fixture', 'space':sid, 'snapshot':fields}


def ui_replay(fx):
    os.environ['LIVING_SPACES_DB'] = str(ROOT / '.run/evidence/ui-input.db')
    inputs = json.loads((ROOT / '.run/ui-input.json').read_text())
    output = json.loads((ROOT / '.run/ui-probe.json').read_text())
    sid = inputs['space']['id']
    body = output['schedule_approval']['body']
    response = fx.client().post(f'/spaces/{sid}/schedule', json=body)
    assert response.status_code == 200 and response.json()['status'] == 'active'
    return {'classification':'control', 'actual_rendered_ui_body':body, 'rest_status':response.status_code,
            'native_job':fx.cron.jobs[response.json()['cron_job_id']]}


def authority_identity(fx):
    sid = fx.make()
    fx.source(sid, 'Original')
    fx.change_upkeep(sid, {'handler': 'agent', 'prompt': 'Changed prompt including exact whitespace.\n'})
    before = fx.records.query(sid, 'items')
    attempts = {
        'manual': error(fx, lambda: fx.runs.start_refresh(sid, trigger='chat', actor='agent:review')),
        'schedule': error(fx, lambda: fx.schedules.decide_schedule(sid, 'approve')),
        'source': error(fx, lambda: fx.source(sid, 'Must fail')),
    }
    assert attempts['manual']['result']['status'] == 'blocked'
    assert attempts['schedule']['error']['code'] == 'not_granted'
    assert attempts['source']['error']['code'] == 'not_granted'
    assert fx.records.query(sid, 'items') == before
    fx.grants.decide(sid, 'refresh', 'grant', scope={'hosts': []})
    stripped = error(fx, lambda: fx.source(sid, 'Must also fail'))
    assert stripped['error']['code'] == 'not_granted'
    fx.approve_refresh(sid)
    approved = fx.source(sid, 'Permitted')
    assert approved['updated'] == 1
    return {'classification': 'control', 'attempts': attempts, 'stripped_scope': stripped, 'reapproved_source': approved}


def schedule_fields(fx):
    sid = fx.make()
    fx.schedules.request_schedule(sid, cadence='0 7 * * *', timezone='UTC', purpose='Public demo', actor='agent:review')
    fields = snapshot(fx, sid)
    upkeep = fx.projects.bundle(sid)['manifest']['upkeep']
    client = fx.client()
    results = []
    for key, changed in [('cadence','* * * * *'), ('timezone','Pacific/Auckland'), ('purpose','Other'), ('requested_at',fields['requested_at']-1)]:
        body = dict(decision='approve', requested_upkeep=upkeep, requested_schedule={**fields,key:changed})
        response = client.post(f'/spaces/{sid}/schedule', json=body)
        assert response.status_code == 409 and not fx.cron.jobs
        results.append({'field':key, 'status':response.status_code, 'error':response.json()})
    for value in (None, {}, {k:v for k,v in fields.items() if k!='requested_at'}):
        body = dict(decision='approve', requested_upkeep=upkeep, requested_schedule=value)
        response = client.post(f'/spaces/{sid}/schedule', json=body)
        assert response.status_code == 400 and not fx.cron.jobs
        results.append({'incomplete':value, 'status':response.status_code})
    response = client.post(f'/spaces/{sid}/schedule', json=dict(decision='approve', requested_upkeep={**upkeep,'prompt':'stale'}, requested_schedule=fields))
    assert response.status_code == 409 and not fx.cron.jobs
    return {'classification':'control', 'fields':results, 'stale_upkeep_status':response.status_code}


def source_batch(fx):
    sid = fx.make()
    fx.records.put(sid, 'items', 'one', {'note':'Keep'}, actor='user')
    fx.source(sid, 'Original')
    before = fx.records.get(sid, 'items', 'one')
    seq = fx.records.changes_since(sid, 0)['seq']
    invalid = []
    for rev in (None, True, -1, 1.5, '2', [], {}):
        result = error(fx, lambda: fx.source_ops(sid, [
            {'op':'put','collection':'items','id':'other','source':{'title':'Rollback'}},
            {'op':'put','collection':'items','id':'one','base_rev':rev,'source':{'title':'Original'}},
        ]))
        assert result['error']['code'] == 'invalid'
        assert fx.records.get(sid, 'items', 'one') == before
        assert fx.records.changes_since(sid, 0)['seq'] == seq
        assert fx.records.query(sid, 'items')['total'] == 1
        invalid.append({'revision':rev, 'code':result['error']['code']})
    stale = error(fx, lambda: fx.source(sid, 'Original', before['rev']-1))
    assert stale['error']['code'] == 'conflict'
    unchanged = fx.source(sid, 'Original')
    assert unchanged['unchanged'] == 1
    assert fx.records.get(sid, 'items', 'one') == before
    assert fx.records.changes_since(sid, 0)['seq'] == seq
    updated = fx.source(sid, 'Updated')
    assert updated['updated'] == 1
    assert fx.records.get(sid, 'items', 'one')['data'] == before['data']
    return {'classification':'control', 'invalid':invalid, 'stale_identical_payload':stale,
            'omitted_identical':unchanged, 'omitted_changed':updated}


def transport_seams(fx):
    observations = []
    for seam in ('dns', 'connection', 'body'):
        with ExitStack() as seam_stack:
            fx = CustomizationFixture(seam_stack)
            sid = fx.make()
            session = fx.sessions.open_session(sid)['session']
            response = Response(body=b'private late result')
            transport = fx.transport([response])
            if seam == 'dns':
                def resolve(*args):
                    fx.sessions.close_session(session)
                    return [PUBLIC]
                fx.stack.enter_context(patch.object(fx.net, '_resolve', side_effect=resolve))
            elif seam == 'connection':
                def connect(*args):
                    result = transport.connect(*args)
                    fx.sessions.close_session(session)
                    return result
                fx.stack.enter_context(patch.object(fx.net, '_connection', side_effect=connect))
            else:
                read = response.read1
                def read1(size):
                    fx.sessions.close_session(session)
                    return read(size)
                response.read1 = read1
            reply = fx.bridge.dispatch(sid, session, 'net.fetch', {'url':'https://example.org/','method':'POST','body':'demo'})
            assert reply['error']['code'] == 'session_invalid'
            assert len(transport.requests) == (1 if seam == 'body' else 0)
            observations.append({'seam':seam, 'reply':reply, 'connections':len(transport.connections), 'sends':len(transport.requests)})
    return {'classification':'control', 'seams':observations}


def history_and_revoke(fx):
    sid = fx.make()
    jid = fx.approve_schedule(sid)['cron_job_id']
    for _ in range(1502):
        fx.cron.execution(jid, 'completed')
    missed = fx.cron.execution(jid, 'missed')
    missed.update(error='Hermes was asleep', scheduled_instant=missed['claimed_at'])
    running = [fx.cron.execution(jid, 'running'), fx.cron.execution(jid, 'running')]
    fx.grants.decide(sid, 'refresh', 'revoke')
    calls = [c for c in fx.cron.calls if c[0] == 'cancel']
    assert calls == [('cancel', jid)]
    history = fx.runs.list_runs(sid, limit=1)
    with fx.db.read() as conn:
        rows = conn.execute('SELECT status,detail FROM runs WHERE space=?', (sid,)).fetchall()
    ids = [json.loads(row['detail'])['cron_run_id'] for row in rows]
    assert len(rows) == len(set(ids)) == 1505
    assert [r['status'] for r in running] == ['cancelled', 'cancelled']
    missed_row = next(dict(row) for row in rows if json.loads(row['detail'])['cron_run_id'] == missed['id'])
    assert missed_row['status'] == 'blocked'
    assert json.loads(missed_row['detail'])['reason'] == 'Hermes was asleep'
    fx.approve_refresh(sid)
    assert fx.schedules.get_schedule(sid)['status'] == 'paused'
    fx.schedules.decide_schedule(sid, 'deny')
    with fx.db.read() as conn:
        after = conn.execute('SELECT count(*) FROM runs WHERE space=?', (sid,)).fetchone()[0]
    assert after == 1505 and not fx.cron.jobs
    assert fx.runs.freshness(sid)['last_success_at'] is not None
    return {'classification':'control', 'durable_rows':len(rows), 'display_rows':len(history),
            'cancel_calls':calls, 'missed_row':missed_row, 'after_pointer_removal':after}


def feed_tls(fx):
    sid = fx.make(handler='feed')
    fx.grants.decide(sid, 'net', 'revoke')
    raw, tls, context = Mock(), Mock(), Mock()
    tls.makefile.return_value = io.BytesIO(b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok')
    context.wrap_socket.return_value = tls
    with patch.object(fx.net, '_resolve', return_value=[PUBLIC]) as resolve, patch.object(fx.net.socket, 'socket', return_value=raw), patch.object(fx.net.ssl, 'create_default_context', return_value=context):
        result = fx.feeds.fetch(sid, 'https://example.org/feed')
    assert result == b'ok'
    raw.connect.assert_called_once_with((PUBLIC, 443))
    context.wrap_socket.assert_called_once_with(raw, server_hostname='example.org', do_handshake_on_connect=False)
    assert b'Host: example.org' in b''.join(call.args[0] for call in tls.sendall.call_args_list)
    transport = fx.transport([])
    with patch.object(fx.net, '_resolve', return_value=[PUBLIC, '127.0.0.1']):
        refused = error(fx, lambda: fx.feeds.fetch(sid, 'https://example.org/feed'))
    assert refused['error']['reason'] == 'private_address' and not transport.connections
    return {'classification':'control', 'feed_body':result.decode(), 'numeric_destination':[PUBLIC,443],
            'tls_hostname':'example.org', 'dns_calls':resolve.call_count, 'mixed_dns':refused}


def revoke_before_activation(fx):
    observations = []
    for resume in (False, True):
        sid = fx.make(handler='feed')
        if resume:
            fx.approve_schedule(sid)
            fx.schedules.pause_schedule(sid, True, actor='user')
        else:
            fx.schedules.request_schedule(sid, cadence='0 * * * *', timezone='UTC', purpose='Demo', actor='agent:review')
        upkeep = fx.projects.bundle(sid)['manifest']['upkeep']
        fields = snapshot(fx, sid)
        check = fx.grants.check
        transitions = []
        def revoke(*args, **kwargs):
            result = check(*args, **kwargs)
            if not transitions:
                script = "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); c.execute(\"UPDATE grants SET status='revoked' WHERE space=? AND capability='refresh'\", (sys.argv[2],)); c.commit(); print('committed revocation')"
                p = subprocess.run([sys.executable, '-B', '-c', script, str(fx.db.db_path()), sid], capture_output=True, text=True, timeout=10)
                assert p.returncode == 0
                transitions.append({'exit':p.returncode,'stdout':p.stdout.strip()})
            return result
        calls = len(fx.cron.calls)
        with patch.object(fx.grants, 'check', side_effect=revoke):
            response = fx.client().post(f'/spaces/{sid}/schedule', json={'paused':False} if resume else dict(decision='approve',requested_upkeep=upkeep,requested_schedule=fields))
        assert response.status_code == 403 and response.json()['error']['code'] == 'not_granted'
        assert not [c for c in fx.cron.calls[calls:] if c[0] in ('create','resume')]
        fx.approve_refresh(sid)
        assert fx.schedules.get_schedule(sid)['status'] in ('paused','requested')
        observations.append({'resume':resume,'response':response.json(),'status':response.status_code,'transitions':transitions})
    return {'classification':'control', 'boundaries':observations}


def revoke_module_unavailable(fx):
    sid = fx.make()
    jid = fx.approve_schedule(sid)['cron_job_id']
    with patch.object(fx.schedules, '_cron', side_effect=ImportError('synthetic unavailable cron adapter')):
        try:
            fx.grants.decide(sid, 'refresh', 'revoke')
        except ImportError as exc:
            observed_error = str(exc)
        else:
            raise AssertionError('Expected current uncaught ImportError')
        after_revoke = fx.schedules._schedule_row(sid)
        revoked = fx.refresh_grant(sid)
    fx.approve_refresh(sid)
    after_regrant = fx.schedules.get_schedule(sid)
    assert revoked['status'] == 'revoked'
    assert after_revoke['status'] == after_regrant['status'] == 'active'
    assert fx.cron.jobs[jid]['enabled']
    retain_db(fx, 'revoke-module-unavailable')
    old_source = subprocess.check_output(['git','show','e45e094:src/living-spaces/living_spaces_core/runs.py'], text=True)
    node = next(node for node in ast.parse(old_source).body if isinstance(node, ast.FunctionDef) and node.name == 'cancel_pending')
    old_body = ast.get_source_segment(old_source, node)
    with ExitStack() as baseline_stack:
        baseline = CustomizationFixture(baseline_stack)
        old_sid = baseline.make()
        baseline.approve_schedule(old_sid)
        namespace = dict(baseline.runs.__dict__)
        exec(compile(old_body, 'e45e094:runs.cancel_pending', 'exec'), namespace)
        with patch.object(baseline.runs, 'cancel_pending', namespace['cancel_pending']), patch.object(baseline.schedules, '_cron', side_effect=ImportError('synthetic unavailable cron adapter')):
            old_result = baseline.grants.decide(old_sid, 'refresh', 'revoke')
            old_schedule = baseline.schedules._schedule_row(old_sid)
        assert old_result['status'] == 'revoked' and old_schedule['status'] == 'disabled'
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    api = fx.load('_availability_api', ROOT / 'src/living-spaces/dashboard/plugin_api.py')
    api.load_core = lambda: fx.core
    app = FastAPI()
    app.include_router(api.router)
    with TestClient(app, raise_server_exceptions=False) as client, patch.object(fx.schedules, '_cron', side_effect=ImportError('synthetic unavailable cron adapter')):
        response = client.post(f'/spaces/{sid}/grants/refresh', json={'decision':'revoke'})
    assert response.status_code == 500
    return {'classification':'counterexample', 'uncaught_error':observed_error, 'after_revoke':after_revoke,
            'refresh_after_revoke':revoked, 'after_regrant':after_regrant, 'native_job':fx.cron.jobs[jid],
            'calls':fx.cron.calls, 'rest_status':response.status_code, 'rest_body':response.text,
            'old_cancel_pending_control':{'source':'e45e094:runs.cancel_pending','grant':old_result,'schedule':old_schedule},
            'limit':'Only the old cancellation function is substituted in the control; not a full old-tree qualification.'}


def timestamp_cursor_limit(fx):
    sid = fx.make()
    jid = fx.approve_schedule(sid)['cron_job_id']
    for _ in range(501):
        entry = fx.cron.execution(jid, 'completed')
        entry.update(claimed_at='2026-11-10T00:00:00+00:00', started_at='2026-11-10T00:00:00+00:00', finished_at='2026-11-10T00:00:01+00:00')
    fx.runs.list_runs(sid)
    fx.runs.list_runs(sid)
    with fx.db.read() as conn:
        count = conn.execute('SELECT count(*) FROM runs WHERE space=?', (sid,)).fetchone()[0]
    assert count == 500
    return {'classification':'disclosed upstream cursor limitation', 'ledger_count':501,
            'imported_count':count, 'same_timestamp':True, 'not_a_new_finding':True}


def missed_manual_identity(fx):
    sid = fx.make()
    run = fx.runs.start_refresh(sid, trigger='manual', actor='user')
    jid = run['detail']['cron_job_id']
    missed = fx.cron.execution(jid, 'missed')
    stamp = (datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat()
    missed.update(claimed_at=stamp, started_at=None, finished_at=stamp, error='Synthetic missed occurrence')
    history = fx.runs.list_runs(sid)
    original = next(row for row in history if row['id'] == run['id'])
    missed_row = next(row for row in history if row['detail'].get('cron_run_id') == missed['id'])
    assert original['status'] == 'queued' and 'cron_run_id' not in original['detail']
    assert missed_row['status'] == 'blocked' and missed_row['started_at'] is None
    assert missed_row['trigger'] == 'schedule'
    return {'classification':'control', 'manual':original, 'missed':missed_row}


CASES = {
    'missing_upkeep': missing_upkeep,
    'authority_identity': authority_identity,
    'schedule_fields': schedule_fields,
    'source_batch': source_batch,
    'transport_seams': transport_seams,
    'history_and_revoke': history_and_revoke,
    'feed_tls': feed_tls,
    'revoke_before_activation': revoke_before_activation,
    'revoke_module_unavailable': revoke_module_unavailable,
    'timestamp_cursor_limit': timestamp_cursor_limit,
    'missed_manual_identity': missed_manual_identity,
    'ui_input': ui_input,
    'ui_replay': ui_replay,
}
for name in sys.argv[1:] or [key for key in CASES if not key.startswith('ui_')]:
    with ExitStack() as stack:
        observation = CASES[name](CustomizationFixture(stack))
    (ROOT / '.run' / (name + '.json')).write_text(json.dumps(observation, indent=2))
    print(json.dumps({'case':name, **observation}), flush=True)
