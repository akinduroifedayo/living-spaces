"""Isolated Desktop consent qualification without invoking a model."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import sys
import time

from cdp import evaluate, screenshot
from guest_realm import guest
from qualify_net import press, wait


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-root', type=Path, default=Path('/Volumes/Expansion/Development/Build/living-spaces-r1'))
    args = parser.parse_args()
    home = (args.run_root / 'home').resolve()
    live = Path.home() / '.hermes'
    if home == live or live in home.parents:
        raise SystemExit('Refusing a live Hermes home')
    os.environ['HERMES_HOME'] = str(home)
    os.environ['LIVING_SPACES_DB'] = str(home / 'plugin-data/living-spaces/spaces.db')
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src/living-spaces'))
    import living_spaces_core as core

    out = args.run_root / 'evidence/consent'
    out.mkdir(parents=True, exist_ok=True)
    checks = []
    report = {'checks': checks, 'completed': False,
              'evidence_class': 'Real isolated Desktop, host mouse decisions and native cron storage. No model execution or concurrent-approval race injection.'}
    sid = None
    original = evaluate('location.hash')
    prompt1 = 'Maintain only the public demo record with the title Aster.'
    prompt2 = 'Maintain only the public demo record with the title Birch.'

    def check(name: str, observed: object, expected: object = True):
        passed = observed == expected
        checks.append({'name': name, 'passed': passed, 'observed': observed, 'expected': expected})
        print(('PASS ' if passed else 'FAIL ') + name, flush=True)
        if not passed:
            raise AssertionError(checks[-1])

    def fingerprint():
        values = []
        for item in core.list_spaces():
            if item['id'] == sid:
                continue
            detail = core.get_space(item['id'])
            values.append([item['id'], item['head_rev'], {
                c: core.query(item['id'], c, limit=500)['records'] for c in detail['collections']
            }])
        return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()

    def refresh():
        return next(g for g in core.list_grants(sid) if g['capability'] == 'refresh')

    def text():
        return evaluate('document.querySelector("[role=dialog]")?.innerText || ""')

    def card(heading, button):
        return evaluate(f'''(() => {{
          const a = [...document.querySelectorAll('[role=dialog] article')].find(e =>
            e.querySelector('.ls-row-top strong')?.textContent.trim() === {json.dumps(heading)});
          const b = a && [...a.querySelectorAll('button')].find(e => e.textContent.trim() === {json.dumps(button)});
          if (!b) return null;
          b.id = 'consent-probe-action'; return '#consent-probe-action';
        }})()''')

    def action(heading, button):
        selector = wait(lambda: card(heading, button), bool)
        press(selector)

    before = fingerprint()
    try:
        made = core.create_space('Consent Qualification', owner='Public demo', author='harness',
                                 manifest={'upkeep': {'handler': 'agent', 'prompt': prompt1}},
                                 files={'index.html': '<h1>Public consent qualification</h1>'})
        sid = made['id']
        report['fixture_space'] = sid
        core.request_schedule(sid, cadence='0 0 1 1 *', timezone='UTC', purpose='Public demo annual task', actor='harness')
        check('agent task starts with Refresh requested', refresh()['status'], 'requested')
        evaluate(f'location.hash={json.dumps("/spaces?space=" + sid)}')
        wait(lambda: evaluate('!![...document.querySelectorAll("button")].find(e => e.textContent.trim() === "Permissions")'), bool)
        press('button[aria-label="Permissions"]' if evaluate('!!document.querySelector("button[aria-label=Permissions]")') else mark_permissions())
        wait(text, lambda t: prompt1 in t and '0 0 1 1 *' in t and 'UTC' in t)
        visible = text()
        report['first_permissions'] = visible
        check('host displays exact agent prompt before Refresh approval', prompt1 in visible)
        check('host discloses model calls before approval', 'model' in visible.lower() and 'call' in visible.lower())
        check('host displays schedule cadence and timezone before approval', '0 0 1 1 *' in visible and 'UTC' in visible)
        screenshot(str(out / '01-task-and-schedule.png'))
        action('Refresh', 'Approve')
        wait(lambda: refresh()['status'], lambda s: s == 'granted')
        check('Refresh grant binds exact displayed task', refresh()['scope'].get('upkeep'), {'handler': 'agent', 'prompt': prompt1})
        action('Scheduled upkeep', 'Approve')
        sched = wait(lambda: core.get_schedule(sid), lambda s: s['status'] == 'active')
        jobs = core.schedules._cron()
        job = jobs.get_job(sched['cron_job_id'])
        report['approved_job'] = {k: job.get(k) for k in ('id', 'no_agent', 'schedule', 'timezone', 'next_run_at')}
        check('native schedule preserves displayed cadence and timezone', (job['schedule']['expr'], job['timezone']), ('0 0 1 1 *', 'UTC'))
        check('native agent job is far in the future, not a model invocation', job['no_agent'] is False and datetime.fromisoformat(job['next_run_at'].replace('Z', '+00:00')).timestamp() > time.time() + 86400)
        manifest = core.bundle(sid)['manifest']
        manifest['upkeep']['prompt'] = prompt2
        core.write_files(sid, files={}, manifest=manifest, author='harness', summary='Public task changed', base_rev=core.get_space(sid)['head_rev'])
        check('changed prompt requests fresh Refresh consent', refresh()['status'], 'requested')
        check('changed prompt pauses the existing native job', jobs.get_job(sched['cron_job_id'])['enabled'], False)
        refused = wait(lambda: guest('space.refresh()'), lambda value: value is not None)
        assert isinstance(refused, dict), refused
        report['refused_refresh'] = refused
        check('real guest cannot start changed unapproved task', (refused.get('ok'), refused.get('code')), (False, 'not_granted'))
        wait(text, lambda t: prompt2 in t)
        screenshot(str(out / '02-changed-task.png'))
        check('host now presents new exact task', prompt2 in text())
        action('Refresh', 'Approve')
        wait(lambda: refresh()['status'], lambda s: s == 'granted')
        check('reapproval grants only the new task', refresh()['scope'].get('upkeep'), {'handler': 'agent', 'prompt': prompt2})
        action('Scheduled upkeep', 'Deny')
        wait(lambda: core.get_schedule(sid)['status'], lambda s: s == 'disabled')
        check('schedule denial removes the prior native job', jobs.get_job(sched['cron_job_id']), None)
        check('no model run was queued or executed', core.list_runs(sid), [])
        report['completed'] = True
    finally:
        if sid is not None:
            core.delete_space(sid, actor='harness-cleanup', confirm=sid)
            check('disposable fixture deleted', any(s['id'] == sid for s in core.list_spaces()), False)
        evaluate(f'location.hash={json.dumps(original)}')
        check('protected demo code and records unchanged', fingerprint(), before)
        (out / 'consent.json').write_text(json.dumps(report, indent=1, default=str))
    print(json.dumps({'passed': sum(c['passed'] for c in checks), 'total': len(checks), 'completed': report['completed']}))


def mark_permissions():
    return evaluate('''(() => {
      const e = [...document.querySelectorAll('button')].find(e => e.textContent.trim() === 'Permissions');
      if (!e) return null; e.id = 'consent-probe-permissions'; return '#consent-probe-permissions';
    })()''')


if __name__ == '__main__':
    main()
