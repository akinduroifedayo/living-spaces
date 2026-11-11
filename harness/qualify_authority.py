"""R1-05 authority gate in the real isolated Desktop.

Fixture (disclosed): a disposable `Authority Probe` Space is created through core
with Research Desk's code, and a later harness-authored revision adds a second
source host. Every grant decision goes through host-owned Permissions controls with
native input. Guest calls run in the Space frame's own realm. The fixture is
deleted at the end.
"""
import asyncio
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
_argv, sys.argv = sys.argv, [sys.argv[0], 'lib']
import qualify_schedule as q  # noqa: E402
sys.argv = _argv
from guest_realm import guest  # noqa: E402

core, RUN = q.core, q.RUN
OUT = RUN / 'evidence/authority'
OUT.mkdir(parents=True, exist_ok=True)
FAKE_SECRET = '-'.join(('sk', 'livingspacesfakeprobe' + '0' * 19))
SECRET_RX = re.compile(r'sk-[A-Za-z0-9_-]{16,}|gh[po]_[A-Za-z0-9_]{20,}|Bearer\s+\S{16,}|/Users/[^/\s]+/\.hermes')
checks: list[dict[str, Any]] = []
result: dict[str, Any] = {'evidence_class': 'actual isolated Desktop, native input on host controls, guest realm bridge calls, canonical SQLite'}


def check(name, observed: Any, expected: Any = True):
    ok = observed == expected
    checks.append({'name': name, 'passed': ok, 'observed': observed, 'expected': expected})
    print(('PASS ' if ok else 'FAIL ') + name, json.dumps(observed, default=str)[:180])
    if not ok:
        raise AssertionError(checks[-1])


def click(find_js, timeout=15):
    locate = lambda: q.evaluate(f"""(() => {{ const e = ({find_js}); if (!e) return null; e.scrollIntoView({{block: 'center'}});
      const r = e.getBoundingClientRect(); return {{x: r.x + r.width / 2, y: r.y + r.height / 2, disabled: !!e.disabled}} }})()""")
    try:
        point = q.wait(locate, lambda p: p and not p['disabled'], timeout, .25)
    except TimeoutError as exc:
        raise LookupError(f'control unavailable: {find_js[:80]}') from exc

    async def go(s):
        for kind in ('mousePressed', 'mouseReleased'):
            await s.call('Input.dispatchMouseEvent', type=kind, x=point['x'], y=point['y'], button='left', clickCount=1)
    asyncio.run(q._page(go))


def card_button(card_text, label):
    return f"""[...document.querySelectorAll('[role=dialog] article')].find(a => a.innerText.includes({json.dumps(card_text)}))
      ?.querySelectorAll('button') && [...[...document.querySelectorAll('[role=dialog] article')].find(a => a.innerText.includes({json.dumps(card_text)})).querySelectorAll('button')].find(b => b.textContent.trim() === {json.dumps(label)})"""


def refresh_grant(sid):
    return next(g for g in core.list_grants(sid) if g['capability'] == 'refresh')


def runs(sid):
    rows = core.list_runs(sid)
    return rows.get('runs', rows) if isinstance(rows, dict) else rows


def open_permissions(sid):
    q.close_sheets()
    q.evaluate(f'location.hash="/spaces?space={sid}"')
    q.wait(q.page_text, lambda t: 'Authority Probe' in t and 'Permissions' in t, 30)
    q.press('Permissions')
    q.wait(lambda: q.evaluate('!!document.querySelector("[role=dialog] [data-testid=webrtc-note]")'), bool, 15)


visible = q.Visible().__enter__()
pid = None
try:
    base = core.bundle('research-desk')
    manifest = {**base['manifest'], 'name': 'Authority Probe'}
    files = {f['path']: f['text'] for f in base['files'] if 'text' in f}
    made = core.create_space('Authority Probe', owner='harness', author='harness-fixture', manifest=manifest, files=files)
    pid = made['space']['id'] if 'space' in made else made['id']
    result['fixture_space'] = pid
    grants0 = {g['capability']: g['status'] for g in core.list_grants(pid)}
    check('new Space gets own-data and logs, refresh only requested', grants0, {'data': 'granted', 'logs': 'granted', 'refresh': 'requested'})

    open_permissions(pid)
    note = q.evaluate("""(() => { const d = document.querySelector('[role=dialog]'); const n = d.querySelector('[data-testid=webrtc-note]');
      const r = n.getBoundingClientRect(), dr = d.getBoundingClientRect();
      const first = [...d.querySelectorAll('[data-testid=webrtc-note], article')][0];
      return {text: n.innerText, visible: r.top >= dr.top && r.bottom <= Math.min(dr.bottom, innerHeight) && r.height > 0, first: first === n} })()""")
    result['webrtc_note'] = note
    check('WebRTC note is visible without scrolling', note['visible'])
    check('WebRTC note precedes every grant card', note['first'])
    check('note does not promise complete outbound blocking', 'This is not a complete block' in note['text'] and 'WebRTC' in note['text'])
    t0 = time.time()
    cards = q.wait(lambda: q.evaluate("""[...document.querySelectorAll('[role=dialog] article')].map(a => a.innerText)"""),
                   lambda cs: any('export.arxiv.org' in c and 'Needs your decision' in c for c in cs), 20, .25)
    result['requested_card_converged_s'] = round(time.time() - t0, 2)
    result['grant_cards'] = cards
    check('three grant cards show scope and purpose', sum(('Scope' in c and 'Purpose' in c) for c in cards) >= 3)
    check('refresh card names the exact requested host', any('export.arxiv.org' in c and 'Approve' in c and 'Deny' in c for c in cards))
    q.screenshot(str(OUT / '01-permissions-requested.png'))

    click(card_button('export.arxiv.org', 'Deny'))
    q.wait(lambda: refresh_grant(pid)['status'], lambda s: s == 'denied', 15)
    check('host Deny records refresh as denied by the user', (refresh_grant(pid)['status'], refresh_grant(pid)['decided_by']), ('denied', 'user'))
    q.close_sheets()
    before_records, known = core.query(pid, 'papers', limit=500)['records'], {r['id'] for r in runs(pid)}
    refused = q.wait(lambda: guest('space.refresh()'), lambda v: v is not None, 30, 1)
    result['guest_refresh_when_denied'] = refused
    check('guest refresh is refused while denied', (refused['ok'], refused.get('code')), (False, 'not_granted'))
    direct = core.start_refresh(pid, trigger='manual', actor='harness', wait=True)
    check('backend refresh is blocked while denied', direct['status'], 'blocked')
    new_runs = [r for r in runs(pid) if r['id'] not in known]
    result['denied_runs'] = new_runs
    check('denied refresh never started, fetched nothing and wrote nothing',
          (core.query(pid, 'papers', limit=500)['records'] == before_records,
           [(r['status'], r['started_at'], r['source_as_of'], sum(r['changed'].values()), r['detail'].get('reason')) for r in new_runs]),
          (True, [('blocked', None, None, 0, 'not_granted')]))

    open_permissions(pid)
    check('denied card explains the outcome without re-prompting', any('Denied.' in c for c in q.evaluate("[...document.querySelectorAll('[role=dialog] article')].map(a => a.innerText)")))
    q.close_sheets()
    core.grants.request(pid, 'refresh', scope={'hosts': ['export.arxiv.org']}, purpose='Re-request after denial for the authority probe', actor='harness-fixture')
    open_permissions(pid)
    click(card_button('export.arxiv.org', 'Approve'))
    q.wait(lambda: refresh_grant(pid)['status'], lambda s: s == 'granted', 15)
    check('host Approve grants exactly the requested host', refresh_grant(pid)['scope'], {'hosts': ['export.arxiv.org']})
    q.close_sheets()

    widened = json.loads(json.dumps(manifest))
    widened['upkeep']['sources'].append({'id': 'extra', 'url': 'https://example.org/feed.xml', 'collection': 'papers', 'purpose': 'Authority probe: new host'})
    core.write_files(pid, files={}, manifest=widened, author='harness-fixture', summary='Authority probe: add a second source host', base_rev=core.get_space(pid)['head_rev'])
    g = refresh_grant(pid)
    result['grant_after_new_host'] = g
    check('code revision asking for a new host returns refresh to requested', (g['status'], g['requested_scope']), ('requested', {'hosts': ['example.org', 'export.arxiv.org']}))
    blocked = core.start_refresh(pid, trigger='manual', actor='harness', wait=True)
    check('new-host revision gained no authority silently', blocked['status'], 'blocked')
    open_permissions(pid)
    q.wait(lambda: q.evaluate("[...document.querySelectorAll('[role=dialog] article')].map(a => a.innerText).join('|')"), lambda t: 'example.org' in t, 15)
    q.screenshot(str(OUT / '02-new-host-requested.png'))
    click(card_button('example.org', 'Approve'))
    q.wait(lambda: refresh_grant(pid)['status'], lambda s: s == 'granted', 15)
    q.close_sheets()

    open_permissions(pid)
    click(card_button('example.org', 'Revoke'))
    q.wait(q.page_text, lambda t: 'Keep access' in t, 10)
    revoke_text = q.evaluate("[...document.querySelectorAll('[role=dialog],[role=alertdialog]')].map(d => d.innerText).find(t => t.includes('Keep access'))")
    result['revoke_dialog'] = revoke_text
    check('revoke confirmation says delivered data cannot be recalled', "can't be recalled" in revoke_text)
    q.screenshot(str(OUT / '03-revoke-confirm.png'))
    click("[...document.querySelectorAll('[role=dialog],[role=alertdialog]')].find(d => d.innerText.includes('Keep access'))?.querySelectorAll('button') && [...[...document.querySelectorAll('[role=dialog],[role=alertdialog]')].find(d => d.innerText.includes('Keep access')).querySelectorAll('button')].find(b => b.textContent.trim() === 'Revoke')")
    q.wait(lambda: refresh_grant(pid)['status'], lambda s: s == 'revoked', 15)
    check('host Revoke records refresh as revoked', refresh_grant(pid)['status'], 'revoked')
    q.close_sheets()
    q.evaluate('location.hash="/spaces"')
    time.sleep(1)
    q.evaluate(f'location.hash="/spaces?space={pid}"')
    after = q.wait(lambda: guest('space.refresh()'), lambda v: v is not None, 30, 1)
    check('guest refresh refused after revoke on a fresh mount', (after['ok'], after.get('code')), (False, 'not_granted'))

    guest(f"(console.error('probe token {FAKE_SECRET} Bearer {FAKE_SECRET}'), new Promise(r => setTimeout(() => r(true), 1500)))")
    entries = [e for e in core.read_logs(pid, limit=50) if 'probe token' in json.dumps(e)]
    result['redacted_log'] = entries[:1]
    check('guest log reached the Space log', bool(entries))
    check('secret-shaped values are redacted before storage', FAKE_SECRET in json.dumps(entries), False)
    reach = guest("fetch('http://127.0.0.1:53766/api/status').then(r => 'reached ' + r.status, e => 'blocked ' + e.name)")
    result['guest_backend_fetch'] = reach
    check('guest cannot reach the Hermes backend directly', str(reach.get('value', '')).startswith('blocked'))
    probe_env = guest("JSON.stringify({process: typeof process, parentDoc: (() => { try { return typeof parent.document } catch (e) { return 'denied' } })(), cookie: (() => { try { return document.cookie } catch (e) { return 'denied ' + e.name } })(), storage: (() => { try { return typeof localStorage.length } catch (e) { return 'denied ' + e.name } })()})")
    result['guest_environment'] = probe_env
    check('guest realm has no process and is denied parent document, cookies and storage', json.loads(probe_env['value']),
          {'process': 'undefined', 'parentDoc': 'denied', 'cookie': 'denied SecurityError', 'storage': 'denied SecurityError'})

    leaks = {}
    for sid in [s['id'] for s in core.list_spaces()]:
        blob = json.dumps({'bundle': core.bundle(sid), 'records': [core.query(sid, c, limit=500) for c in ('papers', 'rounds', 'settings')],
                           'runs': runs(sid), 'logs': core.read_logs(sid, limit=200)}, default=str)
        hits = sorted(set(SECRET_RX.findall(blob)))
        if hits:
            leaks[sid] = hits
    result['credential_scan'] = leaks
    check('no credential or live-profile path in any Space files, records, runs or logs', leaks, {})
finally:
    visible.__exit__(None, None, None)
    if pid:
        try:
            q.close_sheets()
            q.evaluate('location.hash="/spaces"')
            result['fixture_deleted'] = core.delete_space(pid, actor='harness-cleanup', confirm=pid)
        except Exception as exc:
            result['fixture_cleanup_error'] = repr(exc)
    result['checks'] = checks
    result['passed'] = sum(c['passed'] for c in checks)
    result['total'] = len(checks)
    (OUT / 'authority.json').write_text(json.dumps(result, indent=2, default=str))
    (RUN / 'evidence/schedule/schedule-lib.json').unlink(missing_ok=True)
    print(json.dumps({k: result[k] for k in ('passed', 'total')}))
