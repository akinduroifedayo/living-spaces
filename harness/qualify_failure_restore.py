"""R1-06 fetch-failure and R1-10 code-restore gate in the real isolated Desktop.

Fixture (disclosed): the harness writes one code revision, author `harness-fixture`,
that keeps the granted host but points the feed at a path arXiv answers with an HTTP
error. Everything after that uses host-owned Desktop controls with native input.
"""
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
_argv, sys.argv = sys.argv, [sys.argv[0], 'lib']
import qualify_schedule as q  # noqa: E402  (step 'lib' matches no branch, so import only defines helpers)
sys.argv = _argv

core, SID, RUN = q.core, 'research-desk', q.RUN
OUT = RUN / 'evidence/failure-restore'
OUT.mkdir(parents=True, exist_ok=True)
BAD = 'https://export.arxiv.org/api/living-spaces-acceptance-missing-path'
checks: list[dict[str, Any]] = []
result: dict[str, Any] = {'evidence_class': 'actual isolated Desktop with native input; one disclosed harness-authored code revision'}


def check(name, observed: Any, expected: Any = True):
    ok = observed == expected
    checks.append({'name': name, 'passed': ok, 'observed': observed, 'expected': expected})
    print(('PASS ' if ok else 'FAIL ') + name, json.dumps(observed, default=str)[:200])
    if not ok:
        raise AssertionError(checks[-1])


def records():
    return {r['id']: r for r in core.query(SID, 'papers', limit=500)['records']}


def runs():
    rows = core.list_runs(SID)
    return rows.get('runs', rows) if isinstance(rows, dict) else rows


visible = q.Visible().__enter__()
try:
    check('page reports visible under focus emulation', q.evaluate('document.visibilityState'), 'visible')
    before = records()
    user_before = {k: v['data'] for k, v in before.items() if v['data']}
    url = lambda rev=None: core.bundle(SID, rev)['manifest']['upkeep']['sources'][0]['url']
    if url() == BAD:
        bad_rev = core.get_space(SID)['head_rev']
        good_rev = next(r['rev'] for r in core.list_revisions(SID) if r['manifest'].get('upkeep', {}).get('sources', [{}])[0].get('url') != BAD)
        result['resumed_from_existing_fixture'] = {'bad_rev': bad_rev, 'good_rev': good_rev}
        good_bundle = core.bundle(SID, good_rev)
    else:
        good_rev = core.get_space(SID)['head_rev']
        good_bundle = core.bundle(SID)
        manifest = json.loads(json.dumps(good_bundle['manifest']))
        manifest['upkeep']['sources'][0]['url'] = BAD
        core.write_files(SID, files={}, manifest=manifest, author='harness-fixture',
                         summary='Acceptance fixture: point feed at a failing path on the granted host', base_rev=good_rev)
        bad_rev = core.get_space(SID)['head_rev']
    result['good_rev'] = good_rev
    check('fixture is a newer code revision than the good one', bad_rev > good_rev)
    check('fixture revision is authored by the harness', core.list_revisions(SID)[0]['author'] if url() == BAD else None, 'harness-fixture')
    check('same host keeps refresh granted (no silent re-prompt needed)',
          next(g['status'] for g in core.list_grants(SID) if g['capability'] == 'refresh'), 'granted')

    q.go_space()
    known = {r['id'] for r in runs()}
    q.press('Refresh now')
    failed = q.wait(lambda: [r for r in runs() if r['id'] not in known and r['status'] in ('failed', 'blocked', 'succeeded')], bool, 60, 1)[0]
    result['failed_run'] = failed
    check('Refresh now against the failing source records a failed run', failed['status'], 'failed')
    after_fail = records()
    check('every record survives the failed fetch unchanged',
          {k: (v['data'], v.get('source'), v['rev']) for k, v in after_fail.items()},
          {k: (v['data'], v.get('source'), v['rev']) for k, v in before.items()})
    banner = q.wait(q.page_text, lambda t: 'Refresh failed at' in t, 20)
    check('host shows failed banner naming last-good data', "You're seeing data from" in banner)
    check('banner says notes and statuses are unchanged', 'Your notes and statuses are unchanged' in banner)
    q.screenshot(str(OUT / '01-refresh-failed-banner.png'))

    q.press('History')
    q.wait(q.page_text, lambda t: 'Run history' in t and 'Revisions' in t, 15)
    q.press('Revisions', '[role=dialog]')
    q.wait(q.page_text, lambda t: f'Revision {good_rev}' in t and 'Current' in t, 15)
    point = q.evaluate(f"""(() => {{
      const row = [...document.querySelectorAll('[role=dialog] article')].find(a => a.querySelector('strong')?.textContent.trim() === 'Revision {good_rev}');
      const b = row && [...row.querySelectorAll('button')].find(b => b.textContent.trim() === 'Restore…');
      if (!b) return null; b.id = 'ls-restore-probe'; return true }})()""")
    check('target revision offers Restore', point, True)
    rect = q.evaluate("(() => {const r=document.getElementById('ls-restore-probe').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()")

    import asyncio

    async def click(s):
        for kind in ('mousePressed', 'mouseReleased'):
            await s.call('Input.dispatchMouseEvent', type=kind, x=rect['x'], y=rect['y'], button='left', clickCount=1)
    asyncio.run(q._page(click))
    dialog = q.wait(q.page_text, lambda t: f'Restore revision {good_rev}?' in t, 10)
    q.screenshot(str(OUT / '02-restore-confirm.png'))
    q.press('Restore as new revision')
    restored = q.wait(lambda: core.get_space(SID), lambda s: s['head_rev'] == bad_rev + 1, 20)
    rev_row = core.list_revisions(SID)[0]
    result['restored_revision'] = {k: rev_row.get(k) for k in ('rev', 'kind', 'author', 'summary', 'restored_from')}
    check('restore creates a new head revision', restored['head_rev'], bad_rev + 1)
    check('new revision records it was restored from the good one', (rev_row.get('kind'), rev_row.get('restored_from')), ('restore', good_rev))
    check('restored manifest points at the original source', core.bundle(SID)['manifest']['upkeep']['sources'][0]['url'], good_bundle['manifest']['upkeep']['sources'][0]['url'])
    check('restored files equal the good revision byte for byte',
          core.list_revisions(SID)[0]['files'], next(r for r in core.list_revisions(SID) if r['rev'] == good_rev)['files'])
    check('restored bundle text is non-empty and identical',
          [(f['path'], f.get('text')) for f in core.bundle(SID)['files'] if f.get('text')],
          [(f['path'], f.get('text')) for f in good_bundle['files'] if f.get('text')])
    after_restore = records()
    check('code restore did not rewind user records', {k: v['data'] for k, v in after_restore.items() if v['data']}, user_before)
    q.close_sheets()

    known = {r['id'] for r in runs()}
    q.press('Refresh now')
    ok = q.wait(lambda: [r for r in runs() if r['id'] not in known and r['status'] in ('failed', 'blocked', 'succeeded')], bool, 60, 1)[0]
    result['recovered_run'] = ok
    check('refresh succeeds again after restore', ok['status'], 'succeeded')
    q.wait(q.page_text, lambda t: 'Refresh failed at' not in t, 20)
    check('failed banner cleared after successful refresh', 'Refresh failed at' in q.page_text(), False)
    check('user records still intact after recovery', {k: v['data'] for k, v in records().items() if v['data']}, user_before)
    q.screenshot(str(OUT / '03-recovered.png'))
finally:
    visible.__exit__(None, None, None)
    result['checks'] = checks
    result['passed'] = sum(c['passed'] for c in checks)
    result['total'] = len(checks)
    (OUT / 'failure-restore.json').write_text(json.dumps(result, indent=2, default=str))
    print(json.dumps({k: result[k] for k in ('passed', 'total')}))
