"""Q17 uses the real store and the existing synthetic public cron fixtures."""
from contextlib import ExitStack
import json
import unittest
from unittest.mock import patch

from tests.python.review_customization_support import AGENT_PROMPT, CustomizationFixture


class Q17RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.fx = CustomizationFixture(self.stack)
        self.sid = self.fx.make()

    def uncertain(self):
        original = self.fx.ctx.dispatch_tool

        def dispatch(name, args):
            result = original(name, args)
            if args['action'] == 'create':
                raise OSError('reply lost after native creation')
            return result

        with patch.object(self.fx.ctx, 'dispatch_tool', side_effect=dispatch):
            with self.assertRaises(self.fx.core.SpacesError):
                self.fx.schedule(self.sid, cadence='every 6h')
        self.assertEqual(len(self.fx.cron.jobs), 1)
        return self.fx.upkeep.get_upkeep(self.sid)

    def test_unknown_create_exposes_cause_action_and_saved_settings_without_replay(self):
        state = self.uncertain()
        before = list(self.fx.cron.calls)
        self.assertEqual((state.get('recovery') or {}).get('state'), 'unknown')
        self.assertEqual(state['recovery']['operations'][0]['action'], 'schedule')
        self.assertIn('SQLite', state['recovery']['cause'])
        self.assertEqual(state['recovery_aid']['settings'], dict(kind='agent', cadence='every 6h', timezone='UTC', prompt=AGENT_PROMPT))
        self.assertFalse(state['recovery_aid']['authoritative'])
        self.assertEqual(self.fx.projects.get_space(self.sid)['upkeep']['state'], 'unknown')
        self.assertEqual(self.fx.upkeep.get_upkeep(self.sid), state)
        self.assertEqual(self.fx.cron.calls, before)

    def test_confirmation_is_required_before_recovery_touches_native_state(self):
        self.uncertain()
        before = list(self.fx.ctx.calls)
        client = self.fx.client()
        reply = client.post(f'/spaces/{self.sid}/upkeep', json={'action': 'recover'})
        self.assertEqual(reply.status_code, 400)
        self.assertEqual(reply.json()['error'].get('reason'), 'recovery_confirmation_required')
        self.assertEqual(self.fx.ctx.calls, before)

    def test_confirmed_recovery_is_idempotent_and_recreate_never_duplicates(self):
        self.uncertain()
        client = self.fx.client()
        for _ in range(2):
            reply = client.post(f'/spaces/{self.sid}/upkeep', json={'action': 'recover', 'confirm': self.sid})
            self.assertEqual(reply.status_code, 200, reply.text)
            self.assertIsNone(reply.json()['link'])
            self.assertIsNone(reply.json().get('recovery'))
        self.assertEqual(self.fx.cron.jobs, {})
        self.assertEqual([a for a, _ in self.fx.cron.calls].count('trigger'), 0)
        self.fx.schedule(self.sid)
        self.assertEqual(len(self.fx.cron.jobs), 1)
        self.assertEqual([a for a, _ in self.fx.cron.calls].count('create'), 2)

    def test_unavailable_recovery_is_typed_retryable_and_preserves_aid(self):
        state = self.uncertain()
        client = self.fx.client()
        with patch.object(self.fx.ctx, 'dispatch_tool', side_effect=OSError('native offline')):
            shown = client.get(f'/spaces/{self.sid}/upkeep').json()
            reply = client.post(f'/spaces/{self.sid}/upkeep', json={'action': 'recover', 'confirm': self.sid})
        self.assertEqual((shown.get('native_error') or {}).get('retryable'), True)
        self.assertEqual(reply.json()['error'].get('reason'), 'upkeep_recovery_unavailable')
        self.assertTrue(reply.json()['error']['retryable'])
        self.assertEqual(shown['recovery_aid'], state['recovery_aid'])
        self.assertEqual(len(self.fx.cron.jobs), 1)

    def test_saved_aid_does_not_override_native_settings_or_guest_model_denial(self):
        jid = self.fx.schedule(self.sid)['link']['cron_job_id']
        self.fx.cron.jobs[jid].update(schedule_display='every 12h', prompt='Changed natively', enabled=False, state='paused')
        shown = self.fx.upkeep.get_upkeep(self.sid)
        self.assertEqual(shown['job']['cadence'], 'every 12h')
        self.assertEqual((shown.get('recovery_aid') or {}).get('settings', {}).get('cadence'), '0 * * * *')
        session = self.fx.sessions.open_session(self.sid)['session']
        before = list(self.fx.cron.calls)
        reply = self.fx.bridge.dispatch(self.sid, session, 'refresh', {})
        self.assertEqual(reply['error']['reason'], 'agent_from_guest')
        self.assertEqual(self.fx.cron.calls, before)


if __name__ == '__main__':
    unittest.main()
