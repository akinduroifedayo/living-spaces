"""Lifecycle regressions using real product SQLite and synthetic native jobs."""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

from tests.python.review_customization_support import CustomizationFixture, SyntheticCron


class SharedCron:
    """Persist synthetic cron leaves so independent processes observe the same jobs."""

    def __init__(self, path):
        self.path = path
        with sqlite3.connect(path) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS state (value TEXT NOT NULL)")
            if conn.execute("SELECT count(*) FROM state").fetchone()[0] == 0:
                conn.execute("INSERT INTO state VALUES(?)", (json.dumps(dict(jobs={}, serial=0)),))

    def call(self, method, *args, **kwargs):
        with sqlite3.connect(self.path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            state = json.loads(conn.execute("SELECT value FROM state").fetchone()[0])
            cron = SyntheticCron()
            cron.jobs, cron.serial = state['jobs'], state['serial']
            result = getattr(cron, method)(*args, **kwargs)
            conn.execute("UPDATE state SET value=?", (json.dumps(dict(jobs=cron.jobs, serial=cron.serial)),))
            return result

    def create_job(self, **kwargs):
        return self.call('create_job', **kwargs)

    def get_job(self, jid):
        return self.call('get_job', jid)

    def list_jobs(self, include_disabled=False):
        return self.call('list_jobs', include_disabled=include_disabled)

    def remove_job(self, jid):
        return self.call('remove_job', jid)

    def trigger_job(self, jid):
        return self.call('trigger_job', jid)

    def list_executions(self, **kwargs):
        return []


def wait_for(path, timeout=10.0):
    deadline = time.monotonic() + timeout
    while not path.exists():
        if time.monotonic() >= deadline:
            raise TimeoutError(str(path))
        time.sleep(.01)


def worker(mode, home, sid, coordination):
    home, coordination = Path(home), Path(coordination)
    with ExitStack() as stack:
        fx = CustomizationFixture(stack)
        stack.enter_context(patch.dict(os.environ, HERMES_HOME=str(home),
                                       LIVING_SPACES_DB=str(home / 'spaces.db')))
        stack.enter_context(patch.object(fx.db, 'hermes_home', return_value=home))
        cron = SharedCron(home / 'synthetic-cron.db')
        stack.enter_context(patch.object(fx.upkeep, '_cron', return_value=cron))
        stack.enter_context(patch.object(fx.upkeep, '_ledger', return_value=cron))
        with fx.db.read() as conn:
            conn.execute('SELECT count(*) FROM spaces').fetchone()
        (coordination / (mode + '-ready')).touch()
        wait_for(coordination / (mode + '-go'))
        original_connect = fx.db.connect

        def connect():
            conn = original_connect()
            conn.set_trace_callback(lambda sql: (coordination / (mode + '-write')).touch()
                                    if sql == 'BEGIN IMMEDIATE' else None)
            return conn

        stack.enter_context(patch.object(fx.db, 'connect', side_effect=connect))
        if mode == 'delete':
            original = fx.upkeep.on_delete

            def cleanup(*args):
                result = original(*args)
                (coordination / 'cleanup-finished').touch()
                wait_for(coordination / 'delete-release')
                return result

            stack.enter_context(patch.object(fx.upkeep, 'on_delete', side_effect=cleanup))
        if mode == 'refresh-first':
            original = cron.trigger_job

            def trigger(jid):
                result = original(jid)
                (coordination / 'job-triggered').touch()
                wait_for(coordination / 'refresh-release')
                return result

            stack.enter_context(patch.object(cron, 'trigger_job', side_effect=trigger))
        try:
            if mode.startswith('delete'):
                result = fx.projects.delete_space(sid, actor='user', confirm=sid)
            else:
                result = fx.runs.start_refresh(sid, trigger='manual', actor='user')
            outcome = dict(result=result)
        except fx.core.SpacesError as exc:
            outcome = dict(error=exc.to_dict())
        (coordination / (mode + '-result.json')).write_text(json.dumps(outcome))


class LifecycleAtomicTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.fx = CustomizationFixture(self.stack)

    def processes(self, sid, modes):
        fx = self.fx
        cron = SharedCron(fx.home / 'synthetic-cron.db')
        self.stack.enter_context(patch.object(fx.upkeep, '_cron', return_value=cron))
        coordination = fx.home / 'coordination'
        coordination.mkdir()
        processes = []

        def cleanup():
            for mode in modes:
                (coordination / (mode + '-go')).touch()
            for name in ('delete-release', 'refresh-release'):
                (coordination / name).touch()
            for process in processes:
                if process.poll() is None:
                    process.kill()
                process.communicate(timeout=10)

        self.addCleanup(cleanup)
        for mode in modes:
            processes.append(subprocess.Popen(
                [sys.executable, '-B', '-m', 'tests.python.test_lifecycle_atomic',
                 '--worker', mode, str(fx.home), sid, str(coordination)],
                cwd=Path(__file__).resolve().parents[2], env=dict(os.environ),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
        for mode in modes:
            wait_for(coordination / (mode + '-ready'))
        return cron, coordination, processes

    def outcomes(self, coordination, modes, processes):
        outcomes = []
        for mode, process in zip(modes, processes):
            out, err = process.communicate(timeout=15)
            self.assertEqual(process.returncode, 0, (mode, out, err))
            outcomes.append(json.loads((coordination / (mode + '-result.json')).read_text()))
        return outcomes

    def assert_deleted_without_jobs(self, sid, cron):
        with self.fx.db.read() as conn:
            self.assertIsNone(conn.execute('SELECT 1 FROM spaces WHERE id=?', (sid,)).fetchone())
            self.assertEqual(conn.execute('SELECT count(*) FROM upkeep_links WHERE space=?', (sid,)).fetchone()[0], 0)
        self.assertEqual(cron.list_jobs(include_disabled=True), [])

    def test_delete_after_cleanup_gap_cannot_leave_a_future_job(self):
        sid = self.fx.make()
        modes = ('delete', 'refresh')
        cron, coordination, processes = self.processes(sid, modes)
        (coordination / 'delete-go').touch()
        wait_for(coordination / 'cleanup-finished')
        (coordination / 'refresh-go').touch()
        wait_for(coordination / 'refresh-write')
        try:
            wait_for(coordination / 'refresh-result.json', timeout=.75)
        except TimeoutError:
            pass
        (coordination / 'delete-release').touch()
        deleted, refresh = self.outcomes(coordination, modes, processes)
        self.assertTrue(deleted['result']['deleted'])
        self.assert_deleted_without_jobs(sid, cron)
        self.assertEqual(refresh.get('error', {}).get('code'), 'not_found', refresh)

    def test_refresh_committing_before_delete_is_removed(self):
        sid = self.fx.make()
        modes = ('refresh-first', 'delete-second')
        cron, coordination, processes = self.processes(sid, modes)
        (coordination / 'refresh-first-go').touch()
        wait_for(coordination / 'job-triggered')
        (coordination / 'delete-second-go').touch()
        wait_for(coordination / 'delete-second-write')
        (coordination / 'refresh-release').touch()
        refresh, deleted = self.outcomes(coordination, modes, processes)
        self.assertTrue(refresh['result']['triggered'])
        self.assertTrue(deleted['result']['deleted'])
        self.assert_deleted_without_jobs(sid, cron)

    def test_native_remove_failure_preserves_space_and_link_then_retry_cleans_jobs(self):
        fx = self.fx
        sid = fx.make()
        jid = fx.schedule(sid)['link']['cron_job_id']
        before = fx.projects.bundle(sid)
        with patch.object(fx.cron, 'remove_job', side_effect=OSError('synthetic remove failure')):
            with self.assertRaises(OSError):
                fx.projects.delete_space(sid, actor='user', confirm=sid)
        self.assertEqual(fx.projects.bundle(sid), before)
        self.assertEqual(fx.upkeep.get_upkeep(sid)['link']['cron_job_id'], jid)
        self.assertTrue(fx.cron.jobs[jid]['enabled'])
        self.assertTrue(fx.projects.delete_space(sid, actor='user', confirm=sid)['deleted'])
        self.assertEqual(fx.cron.jobs, {})

    def test_one_shot_remove_failure_does_not_orphan_it(self):
        fx = self.fx
        sid = fx.make()
        jid = fx.runs.start_refresh(sid, trigger='manual', actor='user')['cron_job_id']
        with patch.object(fx.cron, 'remove_job', side_effect=OSError('synthetic remove failure')):
            with self.assertRaises(OSError):
                fx.projects.delete_space(sid, actor='user', confirm=sid)
        self.assertEqual(fx.projects.get_space(sid)['status'], 'active')
        self.assertIsNone(fx.upkeep.get_upkeep(sid)['link'])
        self.assertTrue(fx.cron.jobs[jid]['enabled'])
        fx.projects.delete_space(sid, actor='user', confirm=sid)
        self.assertEqual(fx.cron.jobs, {})

    def test_archive_importerror_pending_one_shot_refuses_and_preserves_space(self):
        fx = self.fx
        sid = fx.make()
        jid = fx.runs.start_refresh(sid, trigger='manual', actor='user')['cron_job_id']
        session = fx.sessions.open_session(sid)['session']
        with patch.object(fx.upkeep, '_cron', side_effect=ImportError('synthetic unavailable')):
            with self.assertRaises(fx.core.SpacesError) as caught:
                fx.projects.set_status(sid, 'archived', actor='user')
        self.assertEqual(caught.exception.code, 'blocked')
        self.assertIn('not archived', caught.exception.message)
        self.assertEqual(fx.projects.get_space(sid)['status'], 'active')
        fx.sessions.require(sid, session)
        self.assertIsNone(fx.upkeep.get_upkeep(sid)['link'])
        self.assertTrue(fx.cron.jobs[jid]['enabled'])
        fx.projects.set_status(sid, 'archived', actor='user')
        self.assertFalse(fx.cron.jobs[jid]['enabled'])

    def test_archive_importerror_without_jobs_also_refuses(self):
        fx = self.fx
        sid = fx.make()
        with patch.object(fx.upkeep, '_cron', side_effect=ImportError('synthetic unavailable')):
            with self.assertRaises(fx.core.SpacesError) as caught:
                fx.projects.set_status(sid, 'archived', actor='user')
        self.assertEqual(caught.exception.code, 'blocked')
        self.assertEqual(fx.projects.get_space(sid)['status'], 'active')

    def test_available_empty_cron_archives_and_unarchive_never_resumes(self):
        fx = self.fx
        sid = fx.make()
        self.assertEqual(fx.cron.list_jobs(include_disabled=True), [])
        self.assertEqual(fx.projects.set_status(sid, 'archived', actor='user')['status'], 'archived')
        self.assertEqual(fx.projects.set_status(sid, 'active', actor='user')['status'], 'active')
        self.assertEqual(fx.cron.calls, [])

    def test_delete_does_not_cancel_already_running_native_work(self):
        fx = self.fx
        sid = fx.make()
        jid = fx.schedule(sid)['link']['cron_job_id']
        execution = fx.cron.execution(jid, 'running')
        fx.projects.delete_space(sid, actor='user', confirm=sid)
        self.assertEqual(execution['status'], 'running')
        self.assertEqual(fx.cron.jobs, {})
        self.assertNotIn(('cancel', jid), fx.cron.calls)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--worker':
        worker(*sys.argv[2:])
    else:
        unittest.main()
