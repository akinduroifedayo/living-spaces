"""Real-core admission discrimination; cron replies/effects are synthetic.

Orphan Resume setup uses the public synthetic cron API. Genuine released-core
upgrade fixtures remain in test_f3_legacy_upgrade/routes unchanged.
"""
from contextlib import ExitStack
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.python.review_customization_support import CustomizationFixture
from tests.python.test_agent_refresh_dispatch import RunOutcome
from tests.python.test_f1_f4_regressions import CompletingCronContext


class MaintenanceAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        base = Path(os.environ['F3_PROCESS_TEST_TMPDIR']).resolve()
        if not base.is_relative_to(Path('/Volumes/Expansion')):
            raise ValueError('Owned Expansion temp root required')
        base.mkdir(parents=True, exist_ok=True)
        self.stack.enter_context(patch.object(tempfile, 'tempdir', str(base)))
        self.fx = CustomizationFixture(self.stack)
        self.ctx = CompletingCronContext(self.fx)
        self.fx.ctx = self.ctx
        self.fx.upkeep.configure_context(self.ctx)
        self.ctx.outcome = RunOutcome.BACKGROUND
        self.foreign = self.fx.make()
        self.foreign_job = self.fx.schedule(self.foreign)['link']['cron_job_id']
        self.fx.runs.start_refresh(self.foreign, trigger='manual', actor='user')
        self.foreign_before = self.snapshot(self.foreign)

    def snapshot(self, sid):
        with self.fx.db.read() as conn:
            row = conn.execute('SELECT * FROM refresh_claims WHERE space=?', (sid,)).fetchone()
            claim = dict(row) if row else None
        return {'jobs': [j for j in self.fx.cron.list_jobs(include_disabled=True)
                         if j.get('name') in (f'living-spaces:{sid}', f'living-spaces:{sid}:once')],
                'claim': claim, 'executions': [copy.deepcopy(e) for e in self.fx.cron.executions
                                             if e['job_id'] in {j['id'] for j in self.fx.cron.list_jobs(include_disabled=True)
                                                                if j.get('name') in (f'living-spaces:{sid}', f'living-spaces:{sid}:once')}]}

    def attempt(self, fn):
        try:
            return {'result': fn()}
        except self.fx.core.SpacesError as exc:
            return {'error': exc.to_dict()}

    def observed(self, **values):
        observation = {'case': self.id(), 'boundary': 'real core / synthetic public cron', **values}
        text = json.dumps(observation, sort_keys=True)
        print(text, flush=True)
        return text

    def recovery_control(self, sid):
        removed = self.fx.upkeep.upkeep_action(sid, 'remove', actor='user')
        self.assertIsNone(removed['link'])
        fresh = self.fx.schedule(sid)
        self.assertIsNotNone(fresh['link'])
        self.assertEqual(self.snapshot(self.foreign), self.foreign_before)
        return fresh

    def test_schedule_blocks_claimed_unlinked_background_once(self):
        sid = self.fx.make()
        owner = self.fx.runs.start_refresh(sid, trigger='manual', actor='user')
        before = self.snapshot(sid)
        attempted = self.attempt(lambda: self.fx.schedule(sid))
        after = self.snapshot(sid)
        control = self.recovery_control(sid)
        message = self.observed(owner=owner, before=before, attempted=attempted,
                                after=after, explicit_remove_fresh_schedule=control)
        self.assertEqual(attempted.get('error', {}).get('code'), 'blocked', message)
        self.assertEqual(before, after, message)
        self.assertIn(owner['cron_job_id'], json.dumps(attempted), message)

    def test_linked_run_joins_refresh_without_second_native_dispatch(self):
        sid = self.fx.make()
        jid = self.fx.schedule(sid)['link']['cron_job_id']
        owner = self.fx.runs.start_refresh(sid, trigger='manual', actor='user')
        before = self.snapshot(sid)
        attempted = self.attempt(lambda: self.fx.upkeep.upkeep_action(sid, 'run', actor='user'))
        after = self.snapshot(sid)
        control = self.recovery_control(sid)
        message = self.observed(owner=owner, before=before, attempted=attempted,
                                after=after, explicit_remove_fresh_schedule=control)
        self.assertNotIn('error', attempted, message)
        self.assertEqual(len(after['executions']), len(before['executions']), message)
        self.assertEqual(attempted['result']['dispatch'], owner['dispatch'], message)
        self.assertEqual(before['claim'], after['claim'], message)
        self.assertEqual(owner['cron_job_id'], jid, message)

    def test_resume_blocks_even_disabled_unclaimed_once(self):
        sid = self.fx.make()
        jid = self.fx.schedule(sid)['link']['cron_job_id']
        self.fx.upkeep.upkeep_action(sid, 'pause', actor='user')
        orphan = json.loads(self.ctx.dispatch_tool('cronjob_manage', {
            'action': 'create', 'name': f'living-spaces:{sid}:once',
            'schedule': 'in 7d', 'prompt': 'Unconfirmed prior refresh',
            'repeat': 1, 'no_agent': False, 'deliver': 'local',
            'catch_up': True, 'paused': True}))['job_id']
        before = self.snapshot(sid)
        attempted = self.attempt(lambda: self.fx.upkeep.upkeep_action(sid, 'resume', actor='user'))
        after = self.snapshot(sid)
        enabled_after = self.fx.cron.get_job(jid)['enabled']
        control = self.recovery_control(sid)
        message = self.observed(orphan=orphan, before=before, attempted=attempted,
                                after=after, enabled_after=enabled_after,
                                explicit_remove_fresh_schedule=control)
        self.assertEqual(attempted.get('error', {}).get('code'), 'blocked', message)
        self.assertEqual(before, after, message)
        self.assertIs(enabled_after, False, message)
        self.assertIn(orphan, json.dumps(attempted), message)


if __name__ == '__main__':
    unittest.main()
