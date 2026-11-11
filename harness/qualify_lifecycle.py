"""R1-11 lifecycle isolation in the real isolated Desktop.

Guest calls run in the Space frame's main world through the real `window.space`
bridge (frame -> renderer -> REST -> core). Replaying a closed session uses
`core.dispatch`, the function the bridge route calls, because the renderer never
exposes session ids to anything else. The archive/delete Space is a disposable
fixture created through core, so no model-built Space is deleted.
"""
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any


sys.path.insert(0, str(Path(__file__).resolve().parent))
_argv, sys.argv = sys.argv, [sys.argv[0], 'lib']
import qualify_schedule as q  # noqa: E402
sys.argv = _argv
from guest_realm import guest, open_sessions  # noqa: E402
from cron import jobs as cron  # noqa: E402

core, SID, RUN = q.core, 'research-desk', q.RUN
OUT = RUN / 'evidence/lifecycle'
OUT.mkdir(parents=True, exist_ok=True)
checks: list[dict[str, Any]] = []
result: dict[str, Any] = {'evidence_class': 'actual isolated Desktop guest bridge, native input for host controls, canonical SQLite'}


def check(name, observed: Any, expected: Any = True):
    ok = observed == expected
    checks.append({'name': name, 'passed': ok, 'observed': observed, 'expected': expected})
    print(('PASS ' if ok else 'FAIL ') + name, json.dumps(observed, default=str)[:180])
    if not ok:
        raise AssertionError(checks[-1])


def snapshot(sid):
    return {f"{r['collection']}/{r['id']}": [r['data'], r.get('source'), r['rev']] for c in ('papers', 'rounds', 'settings', 'probe')
            for r in core.query(sid, c, limit=500)['records']}


def runs(sid):
    rows = core.list_runs(sid)
    return rows.get('runs', rows) if isinstance(rows, dict) else rows


visible = q.Visible().__enter__()
try:
    pair_before = {k: v for k, v in snapshot('pair-play').items()}
    q.go_space()
    q.wait(lambda: guest('space.meta'), lambda v: v and v.get('ok') and v.get('value'), 30, 1)
    old = open_sessions(SID)
    check('mounted Space holds exactly one open session', len(old), 1)
    old = old[0]

    big = guest("space.put('probe', undefined, {blob: 'x'.repeat(1100000)})")
    check('oversized guest write fails safely', (big['ok'], big.get('code')), (False, 'limit'))
    bad = guest("space.put('bad name!', undefined, {a: 1})")
    check('malformed collection fails safely', (bad['ok'], bad.get('code')), (False, 'invalid'))
    check('failed writes stored nothing', core.query(SID, 'probe')['records'], [])

    cross = guest("space.batch([{op: 'put', collection: 'rounds', data: {forged: true}, space: 'pair-play'}])")
    result['cross_space_attempt'] = cross
    check('cross-Space write lands only in the bound Space', [r['data'] for r in core.query(SID, 'rounds')['records']], [{'forged': True}] if cross['ok'] else [])
    check('second Space unchanged by the cross-Space attempt', snapshot('pair-play'), pair_before)
    leak = guest("space.query('rounds').then(records => ({records}))")
    check('bound Space cannot read the other Space records', len((leak.get('value') or {}).get('records', [])), 1 if cross['ok'] else 0)
    if cross['ok']:
        forged = core.query(SID, 'rounds')['records'][0]
        result['forged_cleanup'] = guest(f"space.delete('rounds', {json.dumps(forged['id'])}, {{baseRev: {forged['rev']}}})")
        check('forged probe record cleaned up', core.query(SID, 'rounds')['records'], [])

    q.go_index()
    q.wait(lambda: open_sessions(SID), lambda v: old not in v, 15)
    check('closing the Space closes its bridge session', old in open_sessions(SID), False)
    replay = core.dispatch(SID, old, 'data.put', {'collection': 'probe', 'data': {'late': True}})
    result['closed_session_replay'] = replay
    check('replaying the closed session is refused', (replay.get('ok'), (replay.get('error') or {}).get('code')), (False, 'session_invalid'))
    check('replay wrote nothing', core.query(SID, 'probe')['records'], [])
    q.go_space()
    q.wait(lambda: open_sessions(SID), lambda v: len(v) == 1 and old not in v, 30)
    check('reopen issues a fresh session', open_sessions(SID)[0] != old)

    known = {r['id'] for r in runs(SID)}
    for _ in range(3):
        try:
            q.press('Refresh now')
        except (AssertionError, LookupError):
            pass
        time.sleep(.15)
    q.wait(lambda: [r for r in runs(SID) if r['id'] not in known and r['status'] in ('succeeded', 'failed')], bool, 60, 1)
    time.sleep(3)
    new = [r for r in runs(SID) if r['id'] not in known]
    result['repeat_refresh_runs'] = [(r['id'], r['status']) for r in new]
    check('three rapid Refresh now presses produce one run', len(new), 1)

    fixture_manifest = {**core.bundle(SID)['manifest'], 'name': 'Lifecycle Probe'}
    fixture = core.create_space('Lifecycle Probe', owner='harness', author='harness-fixture', manifest=fixture_manifest,
                                files={f['path']: f['text'] for f in core.bundle(SID)['files'] if 'text' in f})
    pid = fixture['space']['id'] if 'space' in fixture else fixture['id']
    result['fixture_space'] = pid
    if any(g['capability'] == 'refresh' and g['status'] != 'granted' for g in core.list_grants(pid)):
        core.decide(pid, 'refresh', 'grant', actor='harness-fixture')
    core.request_schedule(pid, cadence='0 7 * * *', timezone='America/Chicago', purpose='Lifecycle fixture', actor='harness-fixture')
    sched = core.decide_schedule(pid, 'approve', actor='harness-fixture')
    job_id = sched['cron_job_id']
    check('fixture schedule is an active native job', (sched['status'], bool(cron.get_job(job_id))), ('active', True))

    q.evaluate(f'location.hash="/spaces?space={pid}"')
    q.wait(q.page_text, lambda t: 'Lifecycle Probe' in t and 'Refresh now' in t, 30)
    q.evaluate('document.querySelector("[aria-label=\\"More Space actions\\"]").id = "ls-more-probe"')
    rect = q.evaluate('(() => {const r=document.getElementById("ls-more-probe").getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()')

    async def click_at(s, x, y):
        for kind in ('mousePressed', 'mouseReleased'):
            await s.call('Input.dispatchMouseEvent', type=kind, x=x, y=y, button='left', clickCount=1)
    asyncio.run(q._page(lambda s: click_at(s, rect['x'], rect['y'])))
    q.wait(q.page_text, lambda t: 'Archive Space…' in t, 10)
    q.press('Archive Space…')
    confirm = q.wait(q.page_text, lambda t: 'Archive' in t and q.evaluate('document.querySelectorAll("[role=alertdialog],[role=dialog]").length') > 0, 10)
    q.screenshot(str(OUT / '01-archive-confirm.png'))
    label = q.evaluate('(() => [...document.querySelectorAll("[role=alertdialog] button,[role=dialog] button")].map(b=>b.textContent.trim()).find(t=>/^Archive/.test(t)))()')
    q.press(label)
    q.wait(lambda: core.get_space(pid)['status'], lambda s: s == 'archived', 15)
    job = cron.get_job(job_id) or {}
    check('archive pauses the native cron job', (job.get('state'), job.get('enabled')), ('paused', False))
    archived_run = core.start_refresh(pid, trigger='manual', actor='harness', wait=True)
    check('archived Space refuses refresh', archived_run['status'], 'blocked')
    banner = q.wait(q.page_text, lambda t: 'This Space is archived' in t, 15)
    check('archive explains retention', 'Delete removes it and its data permanently' in banner)
    check('archived page is the fixture, not a model-built Space', 'Lifecycle Probe' in banner and core.get_space(SID)['status'] == 'active')
    q.screenshot(str(OUT / '02-archived.png'))

    q.press('Delete…')
    q.wait(lambda: q.evaluate('document.querySelectorAll("[role=alertdialog],[role=dialog]").length'), bool, 10)
    q.screenshot(str(OUT / '03-delete-confirm.png'))
    dtext = q.evaluate('(() => [...document.querySelectorAll("[role=alertdialog],[role=dialog]")].map(d=>d.innerText).join("\\n"))()')
    result['delete_dialog'] = dtext
    typed = q.evaluate(f'(() => {{const i=document.querySelector("[role=alertdialog] input,[role=dialog] input"); if(!i) return false; const set=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,"value").set; set.call(i,{json.dumps(pid)}); i.dispatchEvent(new Event("input",{{bubbles:true}})); return true}})()')
    result['delete_requires_typed_id'] = typed
    label = q.evaluate('(() => [...document.querySelectorAll("[role=alertdialog] button,[role=dialog] button")].map(b=>b.textContent.trim()).find(t=>/^Delete/.test(t)))()')
    q.press(label)
    q.wait(lambda: pid in {s['id'] for s in core.list_spaces()}, lambda present: not present, 15)
    check('delete removes the Space', pid in {s['id'] for s in core.list_spaces()}, False)
    check('delete removes the native cron job', cron.get_job(job_id), None)
    check('delete removes the schedule shim', (RUN / f'home/scripts/living-spaces-refresh-{pid}.py').exists(), False)
    check('model-built Spaces untouched', sorted(s['id'] for s in core.list_spaces()), ['pair-play', 'research-desk', 'runtime-probe'])
    check('second Space data unchanged across the whole run', snapshot('pair-play'), pair_before)
finally:
    visible.__exit__(None, None, None)
    result['checks'] = checks
    result['passed'] = sum(c['passed'] for c in checks)
    result['total'] = len(checks)
    (OUT / 'lifecycle.json').write_text(json.dumps(result, indent=2, default=str))
    (RUN / 'evidence/schedule/schedule-lib.json').unlink(missing_ok=True)
    print(json.dumps({k: result[k] for k in ('passed', 'total')}))
