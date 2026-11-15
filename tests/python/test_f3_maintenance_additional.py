"""Additional real-core coordinator cases. Native cron and its outcomes are synthetic.

These cases do not qualify host execution-history or crash-safe exactly-once behavior.
The parent owns execution, including the Expansion-only temporary root.
"""
from contextlib import ExitStack
import copy
import importlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from typing import Any
import unittest
from unittest.mock import patch

from tests.python.review_customization_support import CustomizationFixture
from tests.python.test_agent_refresh_dispatch import RunOutcome
from tests.python.test_f1_f4_regressions import CompletingCronContext


class Interrupted(BaseException):
    pass


class AdditionalMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        root = Path(os.environ['F3_PROCESS_TEST_TMPDIR']).resolve()
        if not root.is_relative_to(Path('/Volumes/Expansion')):
            raise ValueError('Owned Expansion temp root required')
        root.mkdir(parents=True, exist_ok=True)
        self.stack.enter_context(patch.object(tempfile, 'tempdir', str(root)))
        self.fx: Any = CustomizationFixture(self.stack)
        self.ctx: Any = CompletingCronContext(self.fx)
        self.fx.ctx = self.ctx
        self.fx.upkeep.configure_context(self.ctx)
        self.maintenance = importlib.import_module(self.fx.core.__name__ + '.maintenance')
        self.sid = self.fx.make()
        self.foreign = self.fx.make()
        self.foreign_job = self.fx.schedule(self.foreign)['link']['cron_job_id']
        self.foreign_before = self.foreign_state()

    def foreign_state(self):
        return {'space': self.fx.projects.get_space(self.foreign),
                'native': self.fx.cron.get_job(self.foreign_job)}

    def assert_foreign(self):
        self.assertEqual(self.foreign_state(), self.foreign_before)

    def claim(self, sid=None) -> Any:
        with self.fx.db.read() as conn:
            row = conn.execute('SELECT * FROM refresh_claims WHERE space=?', (sid or self.sid,)).fetchone()
            return dict(row) if row else None

    def refresh(self, sid=None):
        return self.fx.runs.start_refresh(sid or self.sid, trigger='manual', actor='user')

    def queue_feed(self, sid):
        run_id = 'run_additional_' + sid.replace('-', '_')
        with self.fx.db.write() as conn:
            conn.execute("INSERT INTO runs(id,space,trigger,handler,actor,status,queued_at,heartbeat_at) "
                         "VALUES(?,?,'manual','feed','user','queued',?,?)",
                         (run_id, sid, self.fx.db.now(), self.fx.db.now()))
            self.maintenance.bind_feed(conn, sid, run_id, None)
        return run_id

    def test_run_owner_and_refresh_join_the_same_raw_reply(self):
        jid = self.fx.schedule(self.sid)['link']['cron_job_id']
        self.ctx.outcome = RunOutcome.BACKGROUND
        owner = self.fx.upkeep.upkeep_action(self.sid, 'run', actor='user')
        held = self.claim()
        follower = self.refresh()
        self.assertTrue(follower['joined'])
        self.assertEqual(follower['dispatch'], owner['dispatch'])
        self.assertEqual(follower['cron_job_id'], jid)
        self.assertEqual(self.claim(), held)
        self.assertEqual([attempt['job_id'] for attempt in self.ctx.run_attempts], [jid])
        self.fx.upkeep.upkeep_action(self.sid, 'remove', actor='user')
        self.assertIsNone(self.claim())
        self.assertIsNotNone(self.fx.schedule(self.sid)['link'])
        self.assert_foreign()

    def test_once_uses_non_null_matching_acceptance_baseline(self):
        original = self.ctx.dispatch_tool
        baseline = '2026-11-01T10:00:00+00:00'

        def dispatch(name, args):
            reply = original(name, args)
            if args['action'] == 'create' and args.get('name') == self.fx.upkeep._once_name(self.sid):
                jid = json.loads(reply)['job_id']
                self.fx.cron.jobs[jid].update(last_run_at=baseline, last_status='ok')
            return reply

        self.ctx.outcome = RunOutcome.BACKGROUND
        with patch.object(self.ctx, 'dispatch_tool', side_effect=dispatch):
            owner = self.refresh()
            self.assertEqual(json.loads(self.claim()['baseline_completion']), baseline)
            follower = self.refresh()
        self.assertTrue(follower['joined'])
        self.assertEqual(follower['dispatch'], owner['dispatch'])
        self.assertEqual(len(self.ctx.run_attempts), 1)
        self.ctx.finish_background(owner['cron_job_id'])
        self.ctx.outcome = RunOutcome.INLINE
        fresh = self.refresh()
        self.assertNotEqual(fresh['cron_job_id'], owner['cron_job_id'])
        self.assertEqual(len(self.ctx.run_attempts), 2)
        self.assertIsNone(self.claim())
        self.assert_foreign()

    def test_mismatched_terminal_reply_is_unknown_and_never_removes_foreign_job(self):
        original = self.ctx.dispatch_tool
        raw = []

        def dispatch(name, args):
            reply = original(name, args)
            if args['action'] == 'run':
                native = json.loads(reply)
                native['job']['job_id'] = self.foreign_job
                raw.append(copy.deepcopy(native))
                return json.dumps(native)
            return reply

        with patch.object(self.ctx, 'dispatch_tool', side_effect=dispatch):
            owner = self.refresh()
            held = self.claim()
            follower = self.refresh()
        self.assertEqual(owner['dispatch'], raw[0])
        self.assertEqual(owner['refresh_state'], 'unresolved')
        self.assertTrue(follower['joined'])
        self.assertEqual(follower['dispatch'], raw[0])
        self.assertEqual(self.claim(), held)
        self.assertFalse(self.fx.cron.get_job(owner['cron_job_id'])['enabled'])
        self.assertEqual(len(self.ctx.run_attempts), 1)
        self.assert_foreign()
        self.fx.upkeep.upkeep_action(self.sid, 'remove', actor='user')
        self.assertIsNone(self.claim())

    def test_missing_acceptance_baseline_does_not_settle_on_a_changed_stamp(self):
        original = self.ctx.dispatch_tool

        def dispatch(name, args):
            reply = original(name, args)
            if args['action'] == 'run':
                native = json.loads(reply)
                native['job'].pop('last_run_at', None)
                return json.dumps(native)
            return reply

        self.ctx.outcome = RunOutcome.BACKGROUND
        with patch.object(self.ctx, 'dispatch_tool', side_effect=dispatch):
            owner = self.refresh()
            held = self.claim()
            self.fx.cron.jobs[owner['cron_job_id']].update(last_run_at='2026-11-14T10:00:00+00:00', last_status='ok')
            follower = self.refresh()
        self.assertIsNone(held['baseline_completion'])
        self.assertEqual(self.claim(), held)
        self.assertTrue(follower['joined'])
        self.assertEqual(follower['dispatch'], owner['dispatch'])
        self.assertEqual(len(self.ctx.run_attempts), 1)
        self.assert_foreign()

    def test_later_join_reconciles_acceptance_before_disable_interruption(self):
        self.ctx.outcome = RunOutcome.BACKGROUND
        with patch.object(self.fx.upkeep, '_consume_one_shot', side_effect=Interrupted):
            with self.assertRaises(Interrupted):
                self.refresh()
        held = self.claim()
        jid = held['cron_job_id']
        self.assertTrue(self.fx.cron.get_job(jid)['enabled'])
        follower = self.refresh()
        self.assertTrue(follower['joined'])
        self.assertEqual(follower['dispatch'], json.loads(held['native']))
        self.assertFalse(self.fx.cron.get_job(jid)['enabled'])
        self.assertEqual(self.claim(), held)
        self.assertEqual(len(self.ctx.run_attempts), 1)
        with self.fx.db.read() as conn:
            obligation = conn.execute("SELECT resolved FROM maintenance_effects WHERE operation=? AND obligation='disable'",
                                      (held['token'],)).fetchone()
        self.assertEqual(obligation['resolved'], 1)
        self.assert_foreign()

    def test_old_reply_after_delete_recreate_returns_not_found_without_new_space_writes(self):
        original = self.ctx.dispatch_tool
        old_identity = None
        with self.fx.db.read() as conn:
            old_identity = self.maintenance.identity(conn, self.sid)['incarnation']
        replacement = []
        raw = []

        def dispatch(name, args):
            reply = original(name, args)
            if args['action'] == 'run':
                raw.append(json.loads(reply))
                self.fx.projects.delete_space(self.sid, actor='user', confirm=self.sid)
                self.assertEqual(self.fx.make(), self.sid)
                self.fx.schedule(self.sid)
                replacement.append(self.fx.projects.get_space(self.sid))
            return reply

        with patch.object(self.ctx, 'dispatch_tool', side_effect=dispatch):
            with self.assertRaises(self.fx.core.SpacesError) as caught:
                self.refresh()
        error = caught.exception.to_dict()
        self.assertEqual(error['code'], 'not_found')
        self.assertEqual(error['native'], raw[0])
        self.assertEqual(self.fx.projects.get_space(self.sid), replacement[0])
        self.assertIsNone(self.claim())
        with self.fx.db.read() as conn:
            self.assertNotEqual(self.maintenance.identity(conn, self.sid)['incarnation'], old_identity)
        self.assert_foreign()

    def test_refused_delete_rolls_back_queued_feed_cancellation(self):
        sid = self.fx.make(handler='feed')
        jid = self.fx.schedule(sid, kind='feed')['link']['cron_job_id']
        run_id = self.queue_feed(sid)
        before = self.fx.runs.get_run(run_id)
        original = self.ctx.dispatch_tool

        def dispatch(name, args):
            if args['action'] == 'remove' and args['job_id'] == jid:
                return {'success': False, 'error': 'Additive native removal refusal'}
            return original(name, args)

        with patch.object(self.ctx, 'dispatch_tool', side_effect=dispatch):
            with self.assertRaises(self.fx.core.SpacesError):
                self.fx.projects.delete_space(sid, actor='user', confirm=sid)
        self.assertEqual(self.fx.runs.get_run(run_id), before)
        self.assertNotEqual(self.fx.projects.get_space(sid)['status'], 'archived')
        self.assertEqual(self.fx.upkeep.get_upkeep(sid)['link']['cron_job_id'], jid)
        self.assertTrue(self.fx.projects.delete_space(sid, actor='user', confirm=sid)['deleted'])
        self.assert_foreign()

    def test_archive_local_cancellation_failure_rolls_back_lifecycle(self):
        sid = self.fx.make(handler='feed')
        jid = self.fx.schedule(sid, kind='feed')['link']['cron_job_id']
        run_id = self.queue_feed(sid)
        before = self.fx.runs.get_run(run_id)
        with self.fx.db.write() as conn:
            conn.execute("CREATE TRIGGER additional_reject_cancel BEFORE UPDATE ON runs "
                         "WHEN NEW.status='canceled' BEGIN SELECT RAISE(ABORT,'Additive cancellation refusal'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.fx.projects.set_status(sid, 'archived', actor='user')
        self.assertNotEqual(self.fx.projects.get_space(sid)['status'], 'archived')
        self.assertEqual(self.fx.runs.get_run(run_id), before)
        # Native suppression is an external partial effect, not a SQLite rollback.
        self.assertFalse(self.fx.cron.get_job(jid)['enabled'])
        with self.fx.db.write() as conn:
            conn.execute('DROP TRIGGER additional_reject_cancel')
        self.assertEqual(self.fx.projects.set_status(sid, 'archived', actor='user')['status'], 'archived')
        self.assertEqual(self.fx.runs.get_run(run_id)['status'], 'canceled')
        self.assert_foreign()

    def test_queued_feed_blocks_schedule_run_and_resume_with_actual_run_id(self):
        sid = self.fx.make(handler='feed')
        jid = self.fx.schedule(sid, kind='feed')['link']['cron_job_id']
        self.fx.upkeep.upkeep_action(sid, 'pause', actor='user')
        run_id = self.queue_feed(sid)
        before = self.fx.cron.get_job(jid)
        for command in ('schedule', 'run', 'resume'):
            with self.subTest(command=command):
                with self.assertRaises(self.fx.core.SpacesError) as caught:
                    if command == 'schedule':
                        self.fx.schedule(sid, kind='feed')
                    else:
                        self.fx.upkeep.upkeep_action(sid, command, actor='user')
                error = caught.exception.to_dict()
                self.assertEqual(error['code'], 'blocked')
                self.assertIn(run_id, error['run_ids'])
                self.assertEqual(self.fx.cron.get_job(jid), before)
        self.fx.projects.set_status(sid, 'archived', actor='user')
        self.assertEqual(self.fx.runs.get_run(run_id)['status'], 'canceled')
        self.assert_foreign()

    def test_feed_attachment_requires_matching_public_cron_identity(self):
        sid = self.fx.make(handler='feed')
        jid = self.fx.schedule(sid, kind='feed')['link']['cron_job_id']
        self.ctx.outcome = RunOutcome.BACKGROUND
        owner = self.fx.upkeep.upkeep_action(sid, 'run', actor='user')
        held = self.claim(sid)
        self.assertEqual(owner['dispatch'], json.loads(held['native']))
        with patch.object(self.fx.grants, '_check', return_value=True), patch.object(self.fx.runs.threading.Thread, 'start'):
            with self.assertRaises(self.fx.core.SpacesError) as caught:
                self.fx.runs.start_refresh(sid, trigger='schedule', actor='agent:feed')
            self.assertEqual(caught.exception.code, 'blocked')
            self.ctx.execution = {'job_id': jid, 'execution_id': 'synthetic-public-feed-execution'}
            try:
                attached = self.fx.runs.start_refresh(sid, trigger='schedule', actor='agent:feed')
            finally:
                self.ctx.execution = None
        self.assertEqual(attached['status'], 'queued')
        with self.fx.db.read() as conn:
            row = conn.execute('SELECT operation FROM maintenance_feeds WHERE run=?', (attached['id'],)).fetchone()
        self.assertEqual(row['operation'], held['token'])
        self.assertEqual(self.claim(sid), held)
        self.assertEqual([attempt['job_id'] for attempt in self.ctx.run_attempts], [jid])
        self.assert_foreign()
