"""Forge-only F6 qualification in the existing isolated Desktop; never starts a service."""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'harness'))
argv, sys.argv = sys.argv, [sys.argv[0], 'lib']
import qualify_schedule as q
sys.argv = argv
from guest_realm import guest, open_sessions

OUT = ROOT / '.run/repair/desktop'
OUT.mkdir(parents=True, exist_ok=True)
checks = []
sid = None


def check(name, actual, expected):
    checks.append({'name': name, 'actual': actual, 'expected': expected, 'passed': actual == expected})
    if actual != expected:
        raise AssertionError(checks[-1])


def has_data(value):
    return any(g == 'data' or isinstance(g, dict) and g.get('capability') == 'data' and g.get('status') == 'granted'
               for g in (value or {}).get('value', {}).get('grants', []))


def listen():
    return guest("(window.__repairChanges = [], space.on('change', value => window.__repairChanges.push(value)), true)")


def received():
    return guest('window.__repairChanges')


try:
    with q.Visible():
        fixture = q.core.create_space('Permission Repair Probe', owner='Demo', author='harness-fixture',
                                      files={'index.html': '<main><h1>Public permission probe</h1></main>'},
                                      manifest={'entry': 'index.html', 'data': {'version': 1}})
        sid = fixture['id']
        q.evaluate(f'location.hash="/spaces?space={sid}"')
        q.wait(lambda: guest('space.meta'), lambda value: value and value.get('ok') and value.get('value', {}).get('space', {}).get('id') == sid, 30)
        check('fixture opens with own-data authority', has_data(guest('space.meta')), True)
        check('change listener installed', listen(), {'ok': True, 'value': True})
        q.core.records.put(sid, 'private_notes', 'before-revoke', {'text': 'Public demo before revoke'}, actor='agent:demo', base_rev=0)
        q.wait(received, lambda value: value and value.get('value'), 15)
        check('granted fixture receives its change metadata', len(received()['value']) > 0, True)
        q.press('Permissions')
        q.wait(q.page_text, lambda text: 'Granted to Permission Repair Probe' in text, 10)
        selected = q.evaluate("(() => { const card = [...document.querySelectorAll('article.ls-grant')].find(e => e.textContent.includes('Own data')); if (!card) return false; card.id='repair-data-card'; return true })()")
        check('own-data permission card selected', selected, True)
        q.press('Revoke', '#repair-data-card')
        q.wait(q.page_text, lambda text: 'Revoke Own data for Permission Repair Probe?' in text, 10)
        selected = q.evaluate("(() => { const dialog = [...document.querySelectorAll('[role=dialog],[role=alertdialog]')].find(e => e.textContent.includes('Revoke Own data for Permission Repair Probe?')); if (!dialog) return false; dialog.id='repair-revoke-dialog'; return true })()")
        check('revoke confirmation selected', selected, True)
        q.press('Revoke', '#repair-revoke-dialog')
        q.wait(lambda: q.core.list_grants(sid), lambda grants: any(g['capability'] == 'data' and g['status'] == 'revoked' for g in grants), 10)
        q.wait(lambda: guest('space.meta'), lambda value: value and value.get('ok') and not has_data(value), 20)
        check('remounted guest lacks own-data authority', has_data(guest('space.meta')), False)
        check('revoked guest listener installed', listen(), {'ok': True, 'value': True})
        denied = guest("space.query('private_notes')")
        check('record query denied after revoke', (denied.get('ok'), denied.get('code')), (False, 'not_granted'))
        q.core.records.put(sid, 'private_notes', 'after-revoke', {'text': 'Public demo after revoke'}, actor='agent:demo', base_rev=0)
        time.sleep(6)
        check('no new change metadata delivered over four poll intervals', received(), {'ok': True, 'value': []})
        q.screenshot(str(OUT / 'revoked-data.png'))
finally:
    try:
        if sid:
            q.evaluate('location.hash="/spaces"')
            q.wait(lambda: open_sessions(sid), lambda sessions: not sessions, 15)
            q.core.delete_space(sid, actor='harness-fixture', confirm=sid)
    except Exception as error:
        checks.append({'name': 'fixture cleanup', 'passed': False, 'error': str(error)})
        raise
    finally:
        result = {'evidence_class': 'real isolated Desktop guest bridge and canonical core; fixture data only',
                  'checks': checks, 'passed': sum(c['passed'] for c in checks), 'total': len(checks)}
        (OUT / 'revoked-data.json').write_text(json.dumps(result, indent=2))
        print(json.dumps(result, indent=2))
