"""R1-07 gate against the real isolated Desktop, gateway ticker and native cron.

Approval and pause use native mouse input on host-owned controls. Execution is the
isolated gateway's own cron ticker running the no-agent script. `cron run` style
triggering only moves next_run_at; the ticker still claims and executes the job.
"""
import asyncio
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

RUN = Path('/Volumes/Expansion/Development/Build/living-spaces-r1')
REPO = Path(__file__).resolve().parents[1]
os.environ['HERMES_HOME'] = str(RUN / 'home')
sys.path.insert(0, str(REPO / 'src/living-spaces'))
sys.path.insert(0, str(Path.home() / '.hermes/hermes-agent'))

from cdp import _page, evaluate, screenshot  # noqa: E402
import _core  # noqa: E402
from cron import jobs as cron  # noqa: E402

core = _core.load_core()
SID = 'research-desk'
OUT = RUN / 'evidence/schedule'
OUT.mkdir(parents=True, exist_ok=True)
checks = []
step = sys.argv[1] if len(sys.argv) > 1 else 'all'


def check(name, observed: Any, expected: Any = True):
    ok = observed == expected
    checks.append({'name': name, 'passed': ok, 'observed': observed, 'expected': expected})
    print(('PASS ' if ok else 'FAIL ') + name, json.dumps(observed)[:200])
    if not ok:
        raise AssertionError(checks[-1])


def wait(probe, predicate, seconds=20, every=.25):
    end, value = time.monotonic() + seconds, None
    while time.monotonic() < end:
        value = probe()
        if predicate(value):
            return value
        time.sleep(every)
    raise TimeoutError(value)


def page_text():
    return evaluate('document.body.innerText')


def press(label, within=None):
    scope = f'document.querySelector({json.dumps(within)})' if within else 'document'
    point = evaluate(f"""(() => {{
      const root = {scope}; if (!root) return null;
      const e = [...root.querySelectorAll('button,[role=menuitem],a')].find(e => e.textContent.trim() === {json.dumps(label)});
      if (!e) return null; e.scrollIntoView({{block:'center'}});
      const r = e.getBoundingClientRect(); return {{x:r.x+r.width/2, y:r.y+r.height/2, disabled: !!e.disabled || e.getAttribute('aria-disabled') === 'true'}};
    }})()""")
    if not point:
        raise LookupError(f'missing control {label}')
    if point['disabled']:
        raise AssertionError(f'disabled control {label}')

    async def go(s):
        for kind in ('mousePressed', 'mouseReleased'):
            await s.call('Input.dispatchMouseEvent', type=kind, x=point['x'], y=point['y'], button='left', clickCount=1)
    asyncio.run(_page(go))


def frame_press(label):
    from cdp import frame_eval
    pts = frame_eval(f"""(() => {{const e=[...document.querySelectorAll('a,button')].find(e=>e.textContent.trim()==={json.dumps(label)});
      if(!e) return null; const r=e.getBoundingClientRect(); return {{x:r.x+r.width/2,y:r.y+r.height/2}}}})()""")
    if not pts or not pts[0]:
        raise LookupError(f'missing frame control {label}')
    outer = evaluate('(() => {const r=document.querySelector("iframe").getBoundingClientRect();return {x:r.x,y:r.y}})()')

    x, y = outer['x'] + pts[0]['x'], outer['y'] + pts[0]['y']

    async def go(s):
        hit = await s.call('Runtime.evaluate', expression=f'(() => {{const e=document.elementFromPoint({x},{y}); return e ? e.tagName + "." + e.className : null}})()', returnByValue=True)
        print('frame_press', label, round(x), round(y), hit.get('result', {}).get('value'))
        await s.call('Page.bringToFront')
        for kind in ('mousePressed', 'mouseReleased'):
            await s.call('Input.dispatchMouseEvent', type=kind, x=x, y=y, button='left', clickCount=1)
    asyncio.run(_page(go))


class Visible:
    """Hold Chrome focus emulation so the occluded isolated window reports visible."""

    def __enter__(self):
        import threading
        import websockets
        from cdp import page_ws, Session
        self.stop, ready = threading.Event(), threading.Event()

        async def hold():
            async with websockets.connect(page_ws(), max_size=64 << 20) as ws:
                await Session(ws).call('Emulation.setFocusEmulationEnabled', enabled=True)
                ready.set()
                while not self.stop.is_set():
                    try:
                        await asyncio.wait_for(ws.recv(), .5)
                    except asyncio.TimeoutError:
                        pass

        self.thread = threading.Thread(target=lambda: asyncio.run(hold()), daemon=True)
        self.thread.start()
        ready.wait(10)
        return self

    def __exit__(self, *exc):
        self.stop.set()
        self.thread.join(5)


def frames():
    return evaluate('document.querySelectorAll("iframe").length')


def runs():
    return core.list_runs(SID) if hasattr(core, 'list_runs') else core.runs.list_runs(SID)


def schedule_runs():
    rows = runs()
    rows = rows.get('runs', rows) if isinstance(rows, dict) else rows
    return [r for r in rows if r['trigger'] == 'schedule']


def fire_and_wait(known_ids, seconds=200):
    job_id = core.get_schedule(SID)['cron_job_id']
    cron.trigger_job(job_id)
    fired_at = time.time()
    run = wait(lambda: [r for r in schedule_runs() if r['id'] not in known_ids and r['status'] in ('succeeded', 'failed', 'blocked', 'canceled')],
               bool, seconds, 2)[0]
    return run, round(time.time() - fired_at, 1)


def close_sheets():
    for _ in range(3):
        if not evaluate('document.querySelectorAll("[role=dialog]").length'):
            return
        press('Close', '[role=dialog]')
        time.sleep(.4)
    raise AssertionError('sheet did not close')


def go_space():
    close_sheets()
    evaluate(f'location.hash="/spaces?space={SID}"')
    wait(page_text, lambda t: 'Refresh now' in t and 'Permissions' in t)


def go_index():
    evaluate('location.hash="/spaces"')
    wait(page_text, lambda t: 'Research Desk' in t and 'Pair Play' in t)


result: dict[str, Any] = {'evidence_class': 'actual isolated Desktop, isolated gateway cron ticker, canonical SQLite and native cron jobs.json',
          'step': step}
try:
    if step in ('all', 'approve'):
        sched = core.get_schedule(SID)
        check('model-requested schedule awaits user approval', sched['status'], 'requested')
        result['requested'] = sched
        go_space()
        press('Permissions')
        wait(page_text, lambda t: 'Scheduled upkeep' in t and 'Approve' in t)
        screenshot(str(OUT / '01-schedule-requested.png'))
        texts = page_text()
        check('request shows cadence, timezone and no-model cost', all(s in texts for s in ('0 7 * * *', 'America/Chicago', 'No model calls')))
        check('catch-up policy is disclosed before approval', "Missed intervals aren't replayed" in texts)
        evaluate('''(() => {const a=[...document.querySelectorAll('article')].find(a=>a.textContent.includes('Scheduled upkeep')); a.id='ls-sched-probe'; return true})()''')
        press('Approve', '#ls-sched-probe')
        sched = wait(lambda: core.get_schedule(SID), lambda s: s['status'] == 'active', 20)
        job = cron.get_job(sched['cron_job_id'])
        result['approved'] = sched
        result['native_job'] = {k: job.get(k) for k in ('id', 'name', 'schedule', 'timezone', 'no_agent', 'script', 'deliver', 'catch_up', 'next_run_at', 'enabled', 'state')}
        check('approval created one native no-agent cron job', (job['no_agent'], job['name']), (True, f'living-spaces:{SID}'))
        check('native job keeps the requested cadence and timezone', (job['schedule'].get('expr'), job.get('timezone')), ('0 7 * * *', 'America/Chicago'))
        check('next eligible run is the next 07:00 America/Chicago', time.strftime('%H:%M', time.localtime(sched['next_run_at'])), '07:00')
        screenshot(str(OUT / '02-schedule-approved.png'))

    if step in ('all', 'closed'):
        go_index()
        check('Space is closed: no Space frame mounted', frames(), 0)
        known = {r['id'] for r in schedule_runs()}
        before = {r['id']: r for r in core.query(SID, 'papers')['records']}
        run, latency = fire_and_wait(known)
        result['closed_run'] = run
        result['closed_run_latency_s'] = latency
        check('scheduled run executed by the gateway ticker while closed', (run['trigger'], run['status']), ('schedule', 'succeeded'))
        after = {r['id']: r for r in core.query(SID, 'papers')['records']}
        user = {k: v['data'] for k, v in before.items() if v['data']}
        check('user-owned data unchanged by scheduled upkeep', {k: after[k]['data'] for k in user}, user)
        result['closed_counts'] = run['changed']
        out_dir = RUN / 'home/cron/output' / core.get_schedule(SID)['cron_job_id']
        result['cron_output_files'] = sorted(p.name for p in out_dir.glob('*'))[-3:] if out_dir.exists() else []
        go_space()
        press('History')
        hist = wait(page_text, lambda t: 'Run history' in t and ('Schedule' in t or 'schedule' in t), 20)
        check('reopened Space shows the scheduled run in history', 'chedule' in hist)
        screenshot(str(OUT / '03-history-after-closed-run.png'))

    if step in ('all', 'pause'):
        go_space()
        press('Pause upkeep')
        sched = wait(lambda: core.get_schedule(SID), lambda s: s['status'] == 'paused', 20)
        job = cron.get_job(sched['cron_job_id'])
        check('host pause pauses the native job', (job.get('state'), job.get('enabled')), ('paused', False))
        due = [j['id'] for j in cron.get_due_jobs()]
        check('paused job is not due for the ticker', sched['cron_job_id'] in due, False)
        known = {r['id'] for r in schedule_runs()}
        time.sleep(130)
        check('no scheduled run while paused across two ticker intervals', [r['id'] for r in schedule_runs() if r['id'] not in known], [])
        wait(page_text, lambda t: 'Resume upkeep' in t)
        screenshot(str(OUT / '04-paused.png'))
        result['paused'] = sched
    if step == 'updates':
        import sqlite3
        from cdp import frame_eval
        db = RUN / 'home/plugin-data/living-spaces/spaces.db'
        STALE = 'Diverged source title for scheduled-update proof'

        def diverge():
            rec = next(r for r in core.query(SID, 'papers')['records'] if r.get('source') and r['source'].get('title') != STALE)
            con = sqlite3.connect(db)
            src = dict(rec['source'], title=STALE)
            con.execute('UPDATE records SET source=? WHERE space=? AND collection=? AND id=?', (json.dumps(src), SID, 'papers', rec['id']))
            con.commit(); con.close()
            return rec

        sched = core.get_schedule(SID)
        if sched['status'] == 'paused':
            go_space(); press('Resume upkeep')
            wait(lambda: core.get_schedule(SID), lambda s: s['status'] == 'active', 20)
        check('upkeep resumed through the host control', core.get_schedule(SID)['status'], 'active')
        go_index()
        check('Space closed before diverged-source run', frames(), 0)
        leftovers = [r['id'] for r in core.query(SID, 'papers')['records'] if (r.get('source') or {}).get('title') == STALE]
        if leftovers:
            run, _ = fire_and_wait({r['id'] for r in schedule_runs()})
            result['cleanup_run'] = {'leftovers': leftovers, 'run': run}
        stale_left = [r['id'] for r in core.query(SID, 'papers')['records'] if (r.get('source') or {}).get('title') == STALE]
        check('no record carries the stale title before the run', stale_left, [])
        rec = diverge()
        known = {r['id'] for r in schedule_runs()}
        run, latency = fire_and_wait(known)
        result['closed_update_run'] = run
        check('closed scheduled run corrects the diverged source', (run['status'], run['changed'].get('updated')), ('succeeded', 1))
        check('canonical record holds current source after closed run', core.records.get(SID, 'papers', rec['id'])['source']['title'], rec['source']['title'])

        rec = diverge()
        go_space()
        frame_text = lambda: (frame_eval('document.body.innerText') or [''])[0]
        wait(frame_text, lambda t: 'In library' in t and 'Last successful refresh' in t, 30)
        time.sleep(2)
        for _ in range(4):
            if (frame_eval('location.hash') or [''])[0] == '#/library':
                break
            frame_press('Library')
            time.sleep(2)
        if (frame_eval('location.hash') or [''])[0] != '#/library':
            result['navigation_note'] = 'native in-frame tab press did not route in this run; harness set location.hash inside the Space frame. Live pickup, not navigation, is under test.'
            frame_eval('location.hash = "#/library"')
            time.sleep(1.5)
        check('Library view open inside the mounted Space', (frame_eval('location.hash') or [''])[0], '#/library')
        wait(frame_text, lambda t: STALE in t, 20)
        screenshot(str(OUT / '05-open-before-scheduled-write.png'))
        evaluate('document.querySelector("iframe").__lsProbe = "mounted-before-run"')
        frame_eval('window.__lsProbe = "frame-realm-before-run"')
        known = {r['id'] for r in schedule_runs()}
        with Visible():
            check('page reports visible under focus emulation', evaluate('document.visibilityState'), 'visible')
            run, latency = fire_and_wait(known)
            result['open_update_run'] = run
            check('open scheduled run corrects the diverged source', (run['status'], run['changed'].get('updated')), ('succeeded', 1))
            t0 = time.time()
            wait(frame_text, lambda t: STALE not in t and rec['source']['title'][:40] in t, 30)
            result['open_pickup_after_run_s'] = round(time.time() - t0, 1)
        check('open view picked up the scheduled write without remount or reload',
              (evaluate('document.querySelector("iframe").__lsProbe'), (frame_eval('window.__lsProbe') or [None])[0]),
              ('mounted-before-run', 'frame-realm-before-run'))
        screenshot(str(OUT / '06-open-after-scheduled-write.png'))
finally:
    result['checks'] = checks
    result['passed'] = sum(c['passed'] for c in checks)
    result['total'] = len(checks)
    (OUT / f'schedule-{step}.json').write_text(json.dumps(result, indent=2, default=str))
    print(json.dumps({k: result[k] for k in ('passed', 'total')}))
