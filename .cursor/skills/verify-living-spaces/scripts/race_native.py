#!/Users/ifedayoakinduro/.hermes/hermes-agent/venv/bin/python
"""Actual Desktop plus native-chat Refresh race. No product changes."""
import argparse
import json
from pathlib import Path
import sqlite3
import subprocess
import time

import control as c
import flag_enable


def native_snapshot(out):
    path = out / 'state/home/state.db'
    with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as conn:
        conn.execute('PRAGMA query_only=ON')
        conn.row_factory = sqlite3.Row
        sessions = [dict(r) for r in conn.execute('SELECT id,source,model,billing_provider,started_at,ended_at,end_reason,api_call_count,tool_call_count,input_tokens,output_tokens,actual_cost_usd,estimated_cost_usd,cost_status FROM sessions')]
        messages = [dict(r) for r in conn.execute('SELECT id,session_id,role,content,tool_name,tool_call_id,tool_calls,timestamp FROM messages WHERE tool_name="spaces_refresh" OR tool_calls LIKE "%spaces_refresh%"')]
        cron_messages = [dict(r) for r in conn.execute('SELECT id,session_id,role,tool_name,tool_call_id,timestamp FROM messages WHERE session_id IN (SELECT id FROM sessions WHERE source="cron") ORDER BY id')]
    path = out / 'state/home/plugin-data/living-spaces/spaces.db'
    with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as conn:
        conn.row_factory = sqlite3.Row
        runs = [dict(r) for r in conn.execute('SELECT * FROM runs WHERE space="verification-agent-refresh"')]
    return dict(at=time.time(), sessions=sessions, messages=messages, cron_messages=cron_messages, space_runs=runs)


def wait_idle(out, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        busy = c.evaluate(out, '[...document.querySelectorAll("button[aria-label=Stop]")].some(e=>e.getClientRects().length && !e.disabled)')
        if not busy:
            return
        time.sleep(.3)
    raise TimeoutError('Native chat did not become idle')


def race(out, repo):
    acquired = {}
    try:
        c.launch(out, repo, acquired)
        flag_enable.enable(c, out)
        c.setup(out)
        c.dump(out / 'doctor.json', c.doctor(out))
        m = c.owned(out)
        argv = [c.PYTHON, str(Path(c.__file__).with_name('fixture.py')), str(repo), str(out), 'agent']
        prepared = subprocess.run(argv, env={**c.env(Path(m['state'])), 'PYTHONPATH': c.RUNTIME}, capture_output=True, text=True, timeout=30)
        (out / 'agent-fixture.log').write_text(prepared.stdout + prepared.stderr)
        assert prepared.returncode == 0, prepared.stdout + prepared.stderr
        c.click(out, 'text=Getting started')
        assert 'nous/welcome' in c.evaluate(out, 'document.body.innerText'), 'Unverified model refused'
        prime = ('Describe spaces_refresh using tool_describe only. Do not refresh or schedule anything yet. '
                 'Be ready to call spaces_refresh with space="verification-agent-refresh" on my next message. '
                 'Use no other tool and make no changes.')
        c.fill(out, '[data-slot=composer-rich-input]', prime)
        c.key(out, 'Enter')
        time.sleep(2)
        wait_idle(out)
        c.capture(out, 'primed-native-chat')
        before = native_snapshot(out)
        assert not any(s['source'] == 'cron' for s in before['sessions']), 'Priming unexpectedly dispatched upkeep'
        next_prompt = ('Refresh now. Call spaces_refresh exactly once with space="verification-agent-refresh". '
                       'Do not use other tools, create recurring schedules, install, change auth, or edit records or code.')
        c.fill(out, '[data-slot=composer-rich-input]', next_prompt)
        c.click(out, 'text=Spaces')
        c.wait_text(out, 'Verification Agent Refresh')
        c.click(out, 'a[href="#/spaces?space=verification-agent-refresh"]')
        c.wait_text(out, 'Refresh now')
        before_jobs = c.jobs(out)
        assert before_jobs.get('count') == len(before_jobs.get('jobs', [])) == 0
        c.capture(out, 'before-desktop-refresh')
        desktop_before = time.time()
        c.click(out, 'text=Refresh now')
        desktop_after = time.time()
        after_desktop_jobs = c.jobs(out)
        c.click(out, 'text=Getting started')
        draft = c.evaluate(out, 'document.querySelector("[data-slot=composer-rich-input]")?.innerText || ""')
        if draft.strip() != next_prompt:
            c.fill(out, '[data-slot=composer-rich-input]', next_prompt)
        chat_before = time.time()
        c.key(out, 'Enter')
        chat_after = time.time()
        c.dump(out / 'race-actions.json', dict(desktop_before=desktop_before, desktop_after=desktop_after,
                                               chat_before=chat_before, chat_after=chat_after,
                                               draft_survived=draft.strip() == next_prompt,
                                               prime=prime, chat_prompt=next_prompt,
                                               before_jobs=before_jobs, after_desktop_jobs=after_desktop_jobs))
        samples = []
        deadline = time.monotonic() + 75
        captured_two = False
        while time.monotonic() < deadline:
            snapshot = native_snapshot(out)
            snapshot['jobs'] = c.jobs(out)
            samples.append(snapshot)
            c.dump(out / 'race-samples.json', samples)
            crons = [s for s in snapshot['sessions'] if s['source'] == 'cron']
            if len(crons) >= 2 and not captured_two:
                c.capture(out, 'race-two-native-cron-sessions')
                c.click(out, 'text=Scheduled jobs')
                time.sleep(.4)
                c.capture(out, 'race-native-scheduled-jobs')
                c.key(out, 'Escape')
                captured_two = True
            quiescent_jobs = snapshot['jobs'].get('count') == 0 or all(not j.get('enabled') for j in snapshot['jobs'].get('jobs', []))
            if crons and all(s['end_reason'] for s in crons) and quiescent_jobs:
                time.sleep(1)
                final = native_snapshot(out)
                final['jobs'] = c.jobs(out)
                samples.append(final)
                c.dump(out / 'race-samples.json', samples)
                break
            time.sleep(.5)
        c.capture(out, 'race-final-native-state')
        final = samples[-1]
        cron_sessions = [s for s in final['sessions'] if s['source'] == 'cron']
        job_ids = sorted({j['job_id'] for s in samples for j in s['jobs'].get('jobs', [])} |
                         {j['job_id'] for j in after_desktop_jobs.get('jobs', [])})
        chat_calls = []
        for message in final['messages']:
            if message['role'] != 'assistant' or not message['tool_calls']:
                continue
            for call in json.loads(message['tool_calls']):
                function = call.get('function', {})
                arguments = function.get('arguments', '')
                if function.get('name') == 'spaces_refresh' or (function.get('name') == 'tool_call' and 'spaces_refresh' in arguments):
                    chat_calls.append(dict(message_id=message['id'], at=message['timestamp'], call=call))
        first = min(cron_sessions, key=lambda s: s['started_at']) if cron_sessions else None
        overlap = bool(first and chat_calls and first['started_at'] <= chat_calls[-1]['at'] and
                       (first['ended_at'] is None or chat_calls[-1]['at'] < first['ended_at']))
        verdict = dict(revision=m['revision'], distinct_observed_native_one_shots=job_ids,
                       native_cron_sessions=cron_sessions, model_runs_with_api_calls=[s['id'] for s in cron_sessions if s['api_call_count'] > 0],
                       chat_refresh_calls=chat_calls, chat_call_overlapped_first_cron=overlap,
                       space_runs=final['space_runs'], final_jobs=final['jobs'],
                       observed_two_with_overlap=len(job_ids) >= 2 and len(cron_sessions) >= 2 and overlap,
                       limitations='No product changes. Counts are observed native jobs and native session/API-call receipts, not synthetic calls.')
        c.dump(out / 'race-result.json', verdict)
        print(json.dumps(verdict, indent=2))
    finally:
        c.cleanup_acquired(out, acquired)
    c.free_port()


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--repo', type=Path, required=True)
    args = p.parse_args()
    race(args.out.resolve(), args.repo.resolve())
