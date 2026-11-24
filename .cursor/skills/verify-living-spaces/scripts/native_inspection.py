#!/Users/ifedayoakinduro/.hermes/hermes-agent/venv/bin/python
"""Native inspection evidence for a manifest-owned disposable Desktop."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import time

import control as c


def sql_snapshot(out, name):
    path = out / 'state/home/plugin-data/living-spaces/spaces.db'
    with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as conn:
        conn.execute('PRAGMA query_only=ON')
        text = '\n'.join(conn.iterdump())
    (out / (name + '.sql')).write_text(text)
    return hashlib.sha256(text.encode()).hexdigest()


def inspect_results(out):
    path = out / 'state/home/state.db'
    with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as conn:
        conn.execute('PRAGMA query_only=ON')
        conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.execute('SELECT id,session_id,role,content,tool_name,tool_call_id,tool_calls,timestamp FROM messages WHERE tool_name="spaces_inspect" OR tool_calls LIKE "%spaces_inspect%" ORDER BY id')]
        sessions = [dict(r) for r in conn.execute('SELECT id,model,billing_provider,billing_mode,actual_cost_usd,estimated_cost_usd,cost_status FROM sessions')]
    result = dict(messages=rows, sessions=sessions)
    c.dump(out / 'native-inspect-tool-results.json', result)
    print(json.dumps(result, indent=2))


def stop_trial(out):
    before_hash = sql_snapshot(out, 'before-native-stop-inspect')
    prompt = ('Inspect Verification Notebook saved revision 1 again using spaces_inspect with timeout_s=30. '
              'Read only. Do not create or edit anything or call any other tool. This run tests native interruption.')
    assert 'nous/welcome' in c.evaluate(out, 'document.body.innerText'), 'Unverified model refused'
    c.fill(out, '[data-slot=composer-rich-input]', prompt)
    c.key(out, 'Enter')
    observations = []
    deadline = time.monotonic() + 65
    started = False
    while time.monotonic() < deadline:
        text = c.evaluate(out, 'document.body.innerText')
        if 'Running spaces inspect' in text:
            started = True
            c.capture(out, 'inspect-running-before-stop')
            processes = [r for r in c.processes() if str(out / 'state') in r['command']]
            c.dump(out / 'inspect-processes-before-stop.json', processes)
            c.fill(out, '[data-slot=composer-rich-input]', '/stop')
            c.capture(out, 'before-stop-submit')
            still_running = 'Running spaces inspect' in c.evaluate(out, 'document.body.innerText')
            c.key(out, 'Enter')
            time.sleep(.4)
            pending = c.evaluate(out, 'document.querySelector("[data-slot=composer-rich-input]")?.innerText || ""')
            if pending.strip() == '/stop':
                c.key(out, 'Enter')
            c.dump(out / 'stop-attempt.json', dict(command='/stop', running_when_detected=True,
                                                   running_immediately_before_submit=still_running,
                                                   submitted_at=time.time()))
            break
        observations.append(dict(at=time.time(), tail=text[-2500:]))
        time.sleep(.15)
    c.dump(out / 'stop-monitor.json', dict(detected_running=started, observations=observations))
    time.sleep(3)
    c.capture(out, 'after-stop')
    snapshots = []
    for _ in range(35):
        rows = [r for r in c.processes() if str(out / 'state/tmp') in r['command']]
        text = c.evaluate(out, 'document.body.innerText')
        snapshots.append(dict(at=time.time(), inspection_processes=rows, running='Running spaces inspect' in text))
        if not rows and 'Running spaces inspect' not in text:
            break
        time.sleep(1)
    after_hash = sql_snapshot(out, 'after-native-stop-inspect')
    c.dump(out / 'stop-outcome.json', dict(attempted=started, snapshots=snapshots,
                                         before_sha256=before_hash, after_sha256=after_hash,
                                         canonical_unchanged=before_hash == after_hash,
                                         final_text=c.evaluate(out, 'document.body.innerText')))
    inspect_results(out)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('command', choices=['inspect-results', 'stop-trial'])
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    out = a.out.resolve()
    c.owned(out)
    if a.command == 'inspect-results':
        inspect_results(out)
    else:
        stop_trial(out)


if __name__ == '__main__':
    main()
