"""R1-09 repair in the real isolated Desktop.

Fixture (disclosed): a harness-authored revision makes Pair Play's Progress view
throw. The repair is one real model turn in Pair Play's existing Desktop chat,
typed into the Desktop chat composer with native input. The harness never edits the
fix itself.
"""
import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
_argv, sys.argv = sys.argv, [sys.argv[0], 'lib']
import qualify_schedule as q  # noqa: E402
sys.argv = _argv
from chat_turn import submit  # noqa: E402
from guest_realm import guest  # noqa: E402

core, RUN = q.core, q.RUN
SID, CHAT = 'pair-play', 'local-43245b727cb7576c65e6ef7892ef2b23d705b092542d836419a23ac46e3eeaa1'
STATE = RUN / 'home/state.db'
OUT = RUN / 'evidence/repair'
OUT.mkdir(parents=True, exist_ok=True)
MARK = 'acceptance fault: progress view'
PROMPT = ("Pair Play's Progress view stopped working. Read Pair Play's logs to find the cause, then fix the app code. "
          "Keep every saved game, history and settings record exactly as it is. Change only Pair Play.")
checks: list[dict[str, Any]] = []
result: dict[str, Any] = {'evidence_class': 'actual isolated Desktop; one real model turn typed into the existing Pair Play Desktop chat; one disclosed harness fault revision',
                          'prompt': PROMPT, 'chat_session': CHAT}


def check(name, observed: Any, expected: Any = True):
    ok = observed == expected
    checks.append({'name': name, 'passed': ok, 'observed': observed, 'expected': expected})
    print(('PASS ' if ok else 'FAIL ') + name, json.dumps(observed, default=str)[:180])
    if not ok:
        raise AssertionError(checks[-1])


def records(sid):
    con = sqlite3.connect(RUN / 'home/plugin-data/living-spaces/spaces.db')
    rows = con.execute("SELECT collection,id,data,source,rev FROM records WHERE space=? ORDER BY collection,id", (sid,)).fetchall()
    con.close()
    return [list(r) for r in rows]


def progress_text():
    return (guest("(location.hash = '#/progress', new Promise(r => setTimeout(() => r(document.body.innerText), 1500)))") or {}).get('value', '')


def tool_calls_since(t0):
    con = sqlite3.connect(STATE)
    rows = con.execute("SELECT tool_calls FROM messages WHERE session_id=? AND timestamp>=? AND tool_calls IS NOT NULL", (CHAT, t0)).fetchall()
    con.close()
    calls = []
    for (raw,) in rows:
        for c in json.loads(raw):
            fn = c.get('function', c)
            args = json.loads(fn.get('arguments') or '{}')
            if fn.get('name') == 'tool_call':
                calls += [{'name': x.get('name'), 'args': x.get('arguments') or {}} for x in args.get('calls', [])]
            else:
                calls.append({'name': fn.get('name'), 'args': args})
    return calls


visible = q.Visible().__enter__()
try:
    data_before = records(SID)
    desk_logs_before = len(core.read_logs('research-desk', limit=500))
    view = next(f for f in core.bundle(SID)['files'] if f['path'] == 'views/progress.js')['text']
    anchor = 'export function Progress({game: g}) {'
    check('fixture anchor present in the current Progress view', anchor in view)
    if MARK in view:
        fault_rev = core.get_space(SID)['head_rev']
        good_rev = fault_rev - 1
        result['resumed_from_existing_fixture'] = True
    else:
        good_rev = core.get_space(SID)['head_rev']
        core.write_files(SID, files={'views/progress.js': view.replace(anchor, anchor + f"\n  throw new Error('{MARK}');", 1)},
                         author='harness-fixture', summary='Acceptance fixture: make Progress throw', base_rev=good_rev)
        fault_rev = core.get_space(SID)['head_rev']
    check('fault revision is harness-authored', next(r for r in core.list_revisions(SID) if r['rev'] == fault_rev)['author'], 'harness-fixture')
    result['revs'] = {'good': good_rev, 'fault': fault_rev}

    q.close_sheets()
    q.evaluate(f'location.hash="/spaces?space={SID}"')
    q.wait(q.page_text, lambda t: 'Pair Play' in t and 'Permissions' in t, 30)
    q.wait(lambda: guest('typeof space'), lambda v: v and v.get('value') == 'object', 30, 1)
    broken = progress_text()
    q.screenshot(str(OUT / '01-progress-broken.png'))
    logs = q.wait(lambda: [e for e in core.read_logs(SID, limit=50) if MARK in e['msg']], bool, 20, 1)
    result['diagnostic'] = logs[0]
    check('controlled runtime error reaches a Space-scoped diagnostic', (logs[0]['space'], logs[0]['level'], logs[0]['rev']), (SID, 'error', fault_rev))
    check('diagnostic is bounded', len(logs[0]['msg']) <= 4096)
    check('fault never lands in another Space log', any(MARK in e['msg'] for e in core.read_logs('research-desk', limit=500)), False)

    t0 = time.time()
    turn = submit(CHAT, PROMPT, timeout=900)
    result['turn'] = turn
    result['turn_seconds'] = round(time.time() - t0, 1)
    check('repair turn completed through the Desktop composer', turn['finish_reason'] in ('stop', 'end_turn'))
    calls = tool_calls_since(t0 - 1)
    result['tool_calls'] = [{'name': c['name'], 'args': json.dumps(c['args'])[:300]} for c in calls]
    names = [c['name'] for c in calls]
    check('maintainer read the Space logs through the tool', 'spaces_read_logs' in names)
    check('every Space tool call targeted Pair Play only',
          sorted({c['args'].get('space') for c in calls if (c['name'] or '').startswith('spaces_') and c['name'] != 'spaces_list'} - {None}),
          [SID])
    head = core.get_space(SID)['head_rev']
    rev = core.list_revisions(SID)[0]
    result['repair_revision'] = {k: rev.get(k) for k in ('rev', 'kind', 'author', 'summary')}
    check('repair is a new revision after the fault', head > fault_rev)
    check('repair revision is not harness-authored', rev.get('author') != 'harness-fixture')
    fixed = next(f for f in core.bundle(SID)['files'] if f['path'] == 'views/progress.js')['text']
    check('thrown fault removed from the code', MARK in fixed, False)
    check('no saved game, history or settings record changed', records(SID), data_before)

    q.evaluate('location.hash="/spaces"')
    time.sleep(1)
    q.evaluate(f'location.hash="/spaces?space={SID}"')
    q.wait(lambda: guest('typeof space'), lambda v: v and v.get('value') == 'object', 30, 1)
    after = progress_text()
    result['progress_text_after'] = after[:600]
    q.screenshot(str(OUT / '02-progress-repaired.png'))
    check('Progress renders after the repair', 'Progress' in after and len(after) > len(broken))
    fresh = [e for e in core.read_logs(SID, limit=50) if MARK in e['msg'] and e['rev'] == head]
    check('no new fault diagnostics on the repaired revision', fresh, [])
    check('other Space logs untouched by the repair', len(core.read_logs('research-desk', limit=500)), desk_logs_before)
finally:
    visible.__exit__(None, None, None)
    result['checks'] = [c for c in checks if c]
    result['passed'] = sum(c['passed'] for c in checks)
    result['total'] = len(checks)
    (OUT / 'repair.json').write_text(json.dumps(result, indent=2, default=str))
    (RUN / 'evidence/schedule/schedule-lib.json').unlink(missing_ok=True)
    print(json.dumps({k: result[k] for k in ('passed', 'total')}))
