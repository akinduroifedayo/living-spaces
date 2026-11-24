#!/Users/ifedayoakinduro/.hermes/hermes-agent/venv/bin/python
"""Native mapped journeys in an existing, manifest-owned disposable Desktop."""
import argparse
import json
from pathlib import Path
import sqlite3
import subprocess
import time

import control as c

OUT = None
RESULTS = []
CARD = 'a[href="#/spaces?space=verification-notebook"]'
MENU = 'button[aria-label="More Space actions"]'


def wait(predicate, timeout=20):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            last = predicate()
            if last:
                return last
        except AssertionError:
            pass
        time.sleep(.3)
    raise AssertionError(f'Native observable did not arrive; last={last}')


def visible(selector):
    return c.evaluate(OUT, f'!![...document.querySelectorAll({json.dumps(selector)})].find(e=>e.getClientRects().length)')


def index():
    c.key(OUT, 'Escape')
    if visible('[data-testid="space-view"]'):
        c.click(OUT, c.BACK)
    elif not visible('[data-testid="spaces-index"]'):
        c.click(OUT, 'text=Spaces')
    wait(lambda: visible('[data-testid="spaces-index"]'))
    if visible('input[aria-label="Search Spaces or owner"]'):
        c.fill(OUT, 'input[aria-label="Search Spaces or owner"]', '')
    if 'No archived Spaces.' in c.evaluate(OUT, 'document.body.innerText'):
        c.click(OUT, 'text=Recent')


def notebook():
    index()
    wait(lambda: visible(CARD))
    c.click(OUT, CARD)
    wait(lambda: visible('[data-testid="space-view"]'))
    assert c.evaluate(OUT, 'location.hash') == '#/spaces?space=verification-notebook'
    wait(lambda: c.guest_read(OUT, 'button#save'))


def rows():
    return c.records(OUT)


def notebook_row(data):
    return next(r for r in data['spaces'] if r['id'] == 'verification-notebook')


class Unreachable(Exception):
    """A missing prerequisite (named in the message), not a product or harness failure."""


def run_case(name, fn):
    started = time.time()
    try:
        result = fn()
        c.capture(OUT, name + '-result')
        row = dict(feature=name, status='observed' if name == 'refresh-double-agent' else 'passed',
                   started=started, ended=time.time(), observed=result)
    except Unreachable as error:
        row = dict(feature=name, status='verified-unreachable', started=started, ended=time.time(), prerequisite=str(error))
    except Exception as error:
        c.capture(OUT, name + '-failed')
        row = dict(feature=name, status='failed', started=started, ended=time.time(), error=str(error))
    RESULTS.append(row)
    c.dump(OUT / 'mapped-journeys.json', RESULTS)
    print(json.dumps(row))


def save():
    notebook()
    c.capture(OUT, 'records-save-before')
    c.guest_fill(OUT, 'input[aria-label="Note"]', 'W32 mapped note')
    c.guest_click(OUT, 'button#save')
    wait(lambda: c.guest_read(OUT, '#status')['text'] == 'Note saved')
    assert 'W32 mapped note' in c.guest_read(OUT, '#notes')['text']
    data = rows()
    assert any('W32 mapped note' in r['data'] for r in data['records'])
    notebook()
    assert any('W32 mapped note' in r['text'] for r in c.guest_read(OUT))
    return dict(visible_saved=True, persisted=True, reopened=True)


def menu(item):
    c.click(OUT, MENU)
    wait(lambda: visible('[role="menuitem"]'))
    c.click(OUT, 'text=' + item)


def history():
    notebook()
    menu('History')
    c.wait_text(OUT, 'No refresh runs yet.')
    c.capture(OUT, 'history-empty-runs')
    c.click(OUT, 'text=Revisions')
    c.wait_text(OUT, 'Current')
    text = c.evaluate(OUT, 'document.body.innerText')
    assert 'Revision 1' in text or 'Rev 1' in text or 'r1' in text
    c.capture(OUT, 'history-revision-one')
    c.key(OUT, 'Escape')
    return dict(no_runs=True, current_revision=1, restore='blocked: one code revision only')


def empty_upkeep():
    notebook()
    # A Space without a declared refresh shows no Refresh control; Details explains why.
    assert not c.evaluate(OUT, '[...document.querySelectorAll(".ls-frame-actions button")].some(e=>/Refresh/.test(e.textContent))')
    c.click(OUT, 'text=Details')
    c.wait_text(OUT, 'This Space has no refresh of its own.')
    c.capture(OUT, 'details-no-refresh')
    c.click(OUT, 'text=Manage upkeep')
    c.wait_text(OUT, 'No upkeep yet')
    c.capture(OUT, 'upkeep-empty')
    c.key(OUT, 'Escape')
    return dict(empty_upkeep=True, refresh_absent_without_handler=True, explained_in_details=True)


def permissions():
    notebook()
    menu('Permissions')
    c.wait_text(OUT, 'Internet access')
    selector = 'button[role="switch"][aria-labelledby="ls-net-title"]'
    assert c.evaluate(OUT, f'document.querySelector({json.dumps(selector)}).getAttribute("aria-checked")') == 'true'
    c.capture(OUT, 'internet-before-off')
    c.click(OUT, selector)
    wait(lambda: c.evaluate(OUT, f'document.querySelector({json.dumps(selector)}).getAttribute("aria-checked")') == 'false')
    data = rows()
    net = next(r for r in data['grants'] if r['space'] == 'verification-notebook' and r['capability'] == 'net')
    assert net['status'] != 'granted'
    assert any(r['capability'] == 'net' and r['action'] != 'request' and r['outcome'] != 'granted' for r in data['audit'])
    assert 'WebRTC' in c.evaluate(OUT, 'document.body.innerText')
    c.key(OUT, 'Escape')
    # Internet on leaves the island once the grant is off; Details > Manage access is the other route back.
    assert not visible('.ls-frame-actions button[title^="Internet access is on"]')
    c.click(OUT, 'text=Details')
    c.click(OUT, 'text=Manage access')
    c.wait_text(OUT, 'Internet access')
    assert c.evaluate(OUT, f'document.querySelector({json.dumps(selector)}).getAttribute("aria-checked")') == 'false'
    c.capture(OUT, 'internet-off-reopened')
    c.key(OUT, 'Escape')
    return dict(net_status=net['status'], audit=True, reopened_off=True, webrtc_disclosed=True)


def find():
    index()
    selector = 'input[aria-label="Search Spaces or owner"]'
    c.fill(OUT, selector, 'Verification Notebook')
    assert visible(CARD)
    c.capture(OUT, 'search-match')
    c.fill(OUT, selector, 'No such W32 Space')
    c.wait_text(OUT, 'No Spaces match')
    assert not visible(CARD)
    c.capture(OUT, 'search-no-match')
    c.fill(OUT, selector, '')
    c.click(OUT, 'text=Archived')
    c.wait_text(OUT, 'No archived Spaces.')
    c.capture(OUT, 'archive-filter-empty')
    c.click(OUT, 'text=Recent')
    return dict(name_match=True, no_match=True, archived_empty=True)


def pin():
    notebook()
    if notebook_row(rows())['pinned']:   # start unpinned whatever an earlier drive left behind
        menu('Unpin Space')
        wait(lambda: notebook_row(rows())['pinned'] == 0)
    menu('Pin Space')
    wait(lambda: notebook_row(rows())['pinned'] == 1)
    index()
    wait(lambda: visible(CARD + ' .ls-pin'))
    c.capture(OUT, 'pinned-index')
    notebook()
    menu('Unpin Space')
    wait(lambda: notebook_row(rows())['pinned'] == 0)
    return dict(pin=True, unpin=True, persisted=True)


def double_refresh():
    m = c.owned(OUT)
    # Needs a model route. control.py launches with nous.guest false, so this case fails closed unless one is approved.
    if 'nous/welcome' not in c.evaluate(OUT, 'document.body.innerText'):
        raise Unreachable('agent Refresh needs a model route; control.py launches with nous.guest false and no provider')
    argv = [c.PYTHON, str(Path(c.__file__).with_name('fixture.py')), m['repo'], str(OUT), 'agent']
    result = subprocess.run(argv, env={**c.env(Path(m['state'])), 'PYTHONPATH': c.RUNTIME}, capture_output=True, text=True, timeout=30)
    (OUT / 'agent-fixture.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stdout + result.stderr
    index()
    selector = 'a[href="#/spaces?space=verification-agent-refresh"]'
    wait(lambda: visible(selector))
    before_jobs = c.jobs(OUT)
    c.click(OUT, selector)
    c.wait_text(OUT, 'Verification Agent Refresh')
    c.capture(OUT, 'double-refresh-before')
    button = '.ls-frame-actions button[title="Refresh this Space"]'
    if not visible(button):
        button = '.ls-frame-actions button[aria-disabled="false"]'
    controls = c.evaluate(OUT, '[...document.querySelectorAll(".ls-frame-actions button")].filter(e=>/Refresh/.test(e.textContent)).map(e=>({text:e.textContent,disabled:e.getAttribute("aria-disabled"),title:e.getAttribute("title")}))')
    c.dump(OUT / 'double-refresh-controls-before.json', controls)
    c.click(OUT, 'text=Refresh now')
    first_state = c.evaluate(OUT, '[...document.querySelectorAll(".ls-frame-actions button")].filter(e=>/Refresh/.test(e.textContent)).map(e=>({text:e.textContent,disabled:e.getAttribute("aria-disabled")}))')
    c.dump(OUT / 'double-refresh-between.json', first_state)
    if any(r['text'] == 'Refreshing…' for r in first_state):
        c.click(OUT, 'text=Refreshing…')
    else:
        c.click(OUT, 'text=Refresh now')
    c.capture(OUT, 'double-refresh-after-two-clicks')
    time.sleep(3)
    after_jobs = c.jobs(OUT)
    path = OUT / 'state/home/plugin-data/living-spaces/spaces.db'
    with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as conn:
        conn.row_factory = sqlite3.Row
        runs = [dict(r) for r in conn.execute('SELECT * FROM runs WHERE space="verification-agent-refresh"')]
    menu('Upkeep')
    time.sleep(2)
    c.capture(OUT, 'double-refresh-upkeep')
    c.key(OUT, 'Escape')
    c.click(OUT, 'text=Scheduled jobs')
    time.sleep(2)
    c.capture(OUT, 'double-refresh-native-scheduled-jobs')
    receipt = dict(before_jobs=before_jobs, after_jobs=after_jobs, runs=runs, between_clicks=first_state,
                   comparison_scope='Two native Desktop clicks; not simultaneous chat/Desktop backend requests',
                   after_text=c.evaluate(OUT, 'document.body.innerText'))
    c.dump(OUT / 'double-refresh.json', receipt)
    return receipt


def lifecycle():
    notebook()
    before = rows()
    notes = [r for r in before['records'] if r['space'] == 'verification-notebook']
    menu('Archive Space…')
    c.capture(OUT, 'archive-confirmation')
    c.click(OUT, 'text=Archive Space')
    c.wait_text(OUT, 'This Space is archived.')
    assert not visible('iframe[title="Space: Verification Notebook"]')
    archived = rows()
    assert notebook_row(archived)['status'] == 'archived'
    assert notes == [r for r in archived['records'] if r['space'] == 'verification-notebook']
    c.capture(OUT, 'archived-note-preserved')
    c.click(OUT, 'text=Restore Space')
    wait(lambda: c.guest_read(OUT, 'button#save'))
    assert any('W32 mapped note' in r['text'] for r in c.guest_read(OUT))
    assert notebook_row(rows())['status'] == 'active'
    c.capture(OUT, 'restored-note')
    menu('Archive Space…')
    c.click(OUT, 'text=Archive Space')
    c.wait_text(OUT, 'This Space is archived.')
    c.click(OUT, 'text=Delete…')
    c.capture(OUT, 'delete-confirmation')
    text = c.evaluate(OUT, 'document.body.innerText')
    assert 'Verification Notebook' in text
    c.click(OUT, 'text=Delete Space')
    wait(lambda: visible('[data-testid="spaces-index"]'))
    data = rows()
    assert not any(r['id'] == 'verification-notebook' for r in data['spaces'])
    assert not any(r['space'] == 'verification-notebook' for r in data['records'])
    return dict(archive_preserved_notes=True, restore_preserved_notes=True, logical_delete=True,
                upkeep_pause='unverified: notebook has no upkeep')


def main():
    global OUT
    p = argparse.ArgumentParser()
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    OUT = a.out.resolve()
    c.owned(OUT)
    for name, fn in [('records-save-reopen', save), ('history-empty-and-revision', history),
                     ('upkeep-empty-and-refresh-unavailable', empty_upkeep), ('access-internet-off', permissions),
                     ('index-find-and-filter', find), ('organize-pin-unpin', pin),
                     ('refresh-double-agent', double_refresh), ('lifecycle-archive-restore-delete', lifecycle)]:
        run_case(name, fn)


if __name__ == '__main__':
    main()
