"""P13 real feed code/SQLite and generated workers with synthetic cron and bytes."""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from tests.python import review_customization_support as support
from tests.python import test_f3_feed_run_regressions as fixtures
from tests.python.test_f3_feed_later_tick import ScheduledExecution, SHIM_BOOTSTRAP


RELEASED = Path(os.environ.get('LIVING_SPACES_RELEASED_ROOT',
    '/Volumes/Expansion/Development/Build/living-spaces-bugfix-evidence/formal-source-released'))
SCOPE = 'Actual core, SQLite, parser and generated worker. Synthetic cron/HTTPS. Not native-host or Desktop UI proof.'


@dataclass(frozen=True)
class FeedPath:
    name: str
    kind: str
    trigger: str = 'manual'
    actor: str = 'user'
    repeats: int = 1


PATHS = (
    FeedPath('desktop-refresh', 'core'),
    FeedPath('chat-refresh', 'core', 'chat', 'chat'),
    FeedPath('valid-guest-refresh', 'core', 'manual', 'guest'),
    FeedPath('upkeep-run', 'run'),
    FeedPath('scheduled-generated-tick', 'worker'),
    FeedPath('scheduled-public-object', 'scheduled', 'schedule', 'upkeep:schedule'),
    FeedPath('scheduled-without-cron-identity', 'core', 'schedule', 'agent:feed'),
    FeedPath('worker-retry', 'worker', repeats=2),
)


class FeedScenario:
    def __init__(self, package):
        self.case = fixtures.FeedRunRegressions(methodName='runTest')
        self.package = package

    def __enter__(self):
        self.patches = [patch.object(support, 'PACKAGE', self.package),
                        patch.object(fixtures, 'PACKAGE', self.package),
                        patch.object(fixtures, 'SHIM_BOOTSTRAP', SHIM_BOOTSTRAP)]
        for item in self.patches:
            item.start()
        try:
            self.case.setUp()
            self.fx, self.sid, self.jid = self.case.fx, self.case.sid, self.case.jid
            self.feed = self.fx.home / 'p12-feed.xml'
            self.calls = self.fx.home / 'p12-fetches.log'
            self.session = self.fx.sessions.open_session(self.sid)['session']
            self.write_feed(False)
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *args):
        self.case.doCleanups()
        for item in reversed(self.patches):
            item.stop()

    def write_feed(self, expanded):
        first = '<item><guid>p13-a</guid><title>' + ('Revised' if expanded else 'Original') + '</title><link>https://example.org/a</link></item>'
        second = '<item><guid>p13-b</guid><title>New</title><link>https://example.org/b</link></item>' if expanded else ''
        self.feed.write_text('<rss version="2.0"><channel><title>P13</title>' + first + second + '</channel></rss>')

    def fetch_count(self):
        return len(self.calls.read_text().splitlines()) if self.calls.exists() else 0

    def fetch(self, *args, **kwargs):
        with self.calls.open('a') as out:
            out.write('fetch\n')
        return self.feed.read_bytes()

    def refresh(self, path):
        try:
            with patch.object(self.fx.feeds, 'fetch', side_effect=self.fetch):
                run = self.fx.runs.start_refresh(self.sid, trigger=path.trigger, actor=path.actor,
                    session=self.session if path.actor == 'guest' else None, wait=True)
            return {'status': run['status']}
        except self.fx.core.SpacesError as exc:
            error = exc.to_dict()
            return {'error': error['code'], 'reason': error.get('reason')}

    def background_run(self):
        self.fx.ctx.run_reply = {'success': True,
            'job': dict(self.fx.ctx.format_job(self.fx.cron.get_job(self.jid)),
                executed=True, execution_mode='background', delegation_id='synthetic-p13-background')}
        try:
            self.fx.upkeep.upkeep_action(self.sid, 'run', actor='user')
        except self.fx.core.SpacesError as exc:
            error = exc.to_dict()
            return {'error': error['code'], 'reason': error.get('reason')}
        return self.worker()

    def worker(self):
        result = self.case.invoke_shim()
        runs = self.fx.runs.list_runs(self.sid)
        return {'exit_code': result['exit_code'],
                'status': runs[0]['status'] if runs else None,
                'stderr': result['stderr'] if result['exit_code'] else ''}

    def invoke(self, path):
        results = []
        for _ in range(path.repeats):
            if path.kind == 'run':
                result = self.background_run()
            elif path.kind == 'worker':
                result = self.worker()
            elif path.kind == 'scheduled':
                self.fx.ctx.execution = ScheduledExecution(self.jid)
                try:
                    result = self.refresh(path)
                finally:
                    self.fx.ctx.execution = None
            else:
                result = self.refresh(path)
            results.append(result)
        return results

    def tokens(self):
        with self.fx.db.read() as conn:
            exists = conn.execute("SELECT 1 FROM sqlite_master WHERE name='refresh_claims'").fetchone()
            return conn.execute('SELECT COUNT(*) FROM refresh_claims WHERE space=?', (self.sid,)).fetchone()[0] if exists else 0

    def prepare(self, background):
        initial = self.refresh(PATHS[0])
        if initial != {'status': 'succeeded'} or self.fetch_count() != 1:
            raise AssertionError({'initial-control': initial, 'fetches': self.fetch_count()})
        record = self.fx.records.query(self.sid, 'items')['records'][0]
        self.record_id = record['id']
        self.user_data = {'title': 'My title', 'note': 'Keep this note', 'pinned': True}
        self.fx.records.put(self.sid, 'items', record['id'], self.user_data, actor='user', base_rev=record['rev'])
        if background:
            result = self.background_run()
            if result['status'] != 'succeeded' or result['exit_code'] != 0 or self.fetch_count() != 2:
                raise AssertionError({'background-worker-control': result, 'fetches': self.fetch_count()})
        self.write_feed(True)

    def observation(self, path, background):
        self.prepare(background)
        before = self.fetch_count()
        results = self.invoke(path)
        rows = self.fx.records.query(self.sid, 'items')
        saved = self.fx.records.get(self.sid, 'items', self.record_id)
        return {'path': path.name, 'after_background_run': background,
                'results': results, 'new_fetches': self.fetch_count() - before,
                'records': rows['total'], 'source_title': saved['source']['title'],
                'user_data_preserved': saved['data'] == self.user_data,
                'coordinator_tokens': self.tokens(), 'schedule_retained': self.jid in self.fx.cron.jobs}


def collect_paths(package, paths=PATHS):
    observed = []
    for background in (False, True):
        for path in paths:
            with FeedScenario(package) as case:
                observed.append(case.observation(path, background))
    return observed


class FeedAdmissionSeparationTests(unittest.TestCase):
    def setUp(self):
        self.observations = {}
        self.addCleanup(self.report)

    def report(self):
        print(json.dumps({'case': self.id(), 'observations': self.observations, 'scope': SCOPE}), flush=True)

    def test_refresh_after_background_feed_run_admits_desktop_chat_and_valid_guest(self):
        rows = collect_paths(support.PACKAGE, PATHS[:3])
        self.observations['paths'] = rows
        controls = [row for row in rows if not row['after_background_run']]
        for row in controls:
            self.assertEqual(row['results'], [{'status': 'succeeded'}], row)
            self.assertEqual(row['new_fetches'], 1, row)
        blocked = [row for row in rows if row['after_background_run'] and
                   row['results'] != [{'status': 'succeeded'}]]
        self.assertEqual(blocked, [], 'Refresh after completed background feed work must admit without native coordinator recovery')
        for row in rows:
            self.assertEqual(row['new_fetches'], 1, row)
            self.assertEqual(row['records'], 2, row)
            self.assertEqual(row['source_title'], 'Revised', row)
            self.assertTrue(row['user_data_preserved'], row)
            self.assertEqual(row['coordinator_tokens'], 0, row)

    def test_every_feed_path_matches_released_admission_with_p12_freshness(self):
        baseline = collect_paths(RELEASED / 'src/living-spaces')
        actual = collect_paths(support.PACKAGE)
        self.observations.update(released=baseline, candidate=actual)
        self.assertEqual(len(baseline), 2 * len(PATHS))
        self.assertEqual(len(actual), len(baseline))
        for row in baseline:
            path = next(path for path in PATHS if path.name == row['path'])
            self.assertTrue(all(result.get('status') == 'succeeded' and not result.get('error')
                                and result.get('exit_code', 0) == 0 for result in row['results']), row)
            self.assertEqual(row['new_fetches'], path.repeats, row)
            self.assertEqual(row['records'], 2, row)
            self.assertTrue(row['user_data_preserved'], row)
            self.assertEqual(row['coordinator_tokens'], 0, row)
            self.assertTrue(row['schedule_retained'], row)
        differences = [{'released': expected, 'candidate': observed}
                       for expected, observed in zip(baseline, actual) if expected != observed]
        self.observations['differences'] = differences
        self.assertEqual(differences, [], 'Every feed path must match released admission while retaining P12 freshness')


if __name__ == '__main__':
    unittest.main(verbosity=2)
