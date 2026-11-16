"""P12: actual generated worker/core/SQLite, synthetic cron replies and feed bytes."""
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any
import unittest
from unittest.mock import patch

from tests.python import test_f3_feed_run_regressions as fixtures


SHIM_BOOTSTRAP = '''import importlib.util, os, runpy, sys
from importlib import import_module
from pathlib import Path
from unittest.mock import patch
package, shim = sys.argv[1:]
spec = importlib.util.spec_from_file_location('feed_later_tick_loader', Path(package) / '_core.py')
loader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loader)
core = loader.load_core()
feeds = import_module(core.__name__ + '.feeds')
home = Path(os.environ['HERMES_HOME'])
def fetch(*args, **kwargs):
    with (home / 'p12-fetches.log').open('a') as out:
        out.write('fetch\\n')
    return (home / 'p12-feed.xml').read_bytes()
with patch.object(feeds, 'fetch', side_effect=fetch):
    runpy.run_path(shim, run_name='__main__')
'''


@dataclass(frozen=True)
class ScheduledExecution:
    job_id: str
    execution_id: str = 'p12-distinct-scheduled-execution'
    source: str = 'builtin'
    scheduled_instant: str = '2026-11-16T03:00:00+00:00'


class FeedLaterTickTests(unittest.TestCase):
    def setUp(self):
        self.case: Any = fixtures.FeedRunRegressions(methodName='runTest')
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.fx = self.case.fx
        self.sid = self.case.sid
        self.jid = self.case.jid
        self.observations = []
        self.addCleanup(self.report)
        self.case.stack.enter_context(patch.object(fixtures, 'SHIM_BOOTSTRAP', SHIM_BOOTSTRAP))
        self.feed = self.fx.home / 'p12-feed.xml'
        self.calls = self.fx.home / 'p12-fetches.log'
        self.execution = ScheduledExecution(self.jid)
        self.write_feed(expanded=False)

    def report(self):
        print(json.dumps({'case': self.id(), 'observations': self.observations,
                          'scope': 'Actual generated shim/core/SQLite. Synthetic cron dispatch, scheduled identity and supplied feed bytes; not native-host proof.'}), flush=True)

    def write_feed(self, *, expanded):
        first = '<item><guid>p12-a</guid><title>' + ('Source revised' if expanded else 'Source original') + '</title><link>https://example.org/a</link></item>'
        second = '<item><guid>p12-b</guid><title>New item</title><link>https://example.org/b</link></item>' if expanded else ''
        self.feed.write_text('<rss version="2.0"><channel><title>P12</title>' + first + second + '</channel></rss>')

    def observe(self, phase, caller):
        runs = self.fx.runs.list_runs(self.sid)
        rows = self.fx.records.query(self.sid, 'items')
        observed = {'phase': phase, 'caller': caller,
                    'fetches': len(self.calls.read_text().splitlines()),
                    'run_ids': [run['id'] for run in runs],
                    'run_statuses': [run['status'] for run in runs],
                    'records': rows}
        self.observations.append(observed)
        return observed

    def native_snapshot(self):
        with self.fx.db.read() as conn:
            exists = conn.execute("SELECT 1 FROM sqlite_master WHERE name='refresh_claims'").fetchone()
            claims = [dict(row) for row in conn.execute('SELECT * FROM refresh_claims ORDER BY space')] if exists else []
        return {'claims': claims, 'jobs': json.loads(json.dumps(self.fx.cron.jobs, sort_keys=True)),
                'effects': [entry for entry in self.fx.cron.calls if entry[0] != 'list']}

    def public_scheduled_call(self):
        def fetch(*args, **kwargs):
            with self.calls.open('a') as out:
                out.write('fetch\n')
            return self.feed.read_bytes()
        self.fx.ctx.execution = self.execution
        try:
            with patch.object(self.fx.feeds, 'fetch', side_effect=fetch):
                run = self.fx.runs.start_refresh(self.sid, trigger='schedule', actor='upkeep:schedule', wait=True)
            return {'run_id': run['id'], 'status': run['status']}
        except self.fx.core.SpacesError as exc:
            return {'error': exc.to_dict()}
        finally:
            self.fx.ctx.execution = None

    def check_later_tick(self, shape):
        self.fx.ctx.run_reply = {'success': True,
            'job': dict(self.fx.ctx.format_job(self.fx.cron.get_job(self.jid)),
                        executed=True, execution_mode='background',
                        delegation_id='p12-original-manual-background')}
        self.fx.upkeep.upkeep_action(self.sid, 'run', actor='user')
        first_caller = self.case.invoke_shim()
        self.assertEqual(first_caller['exit_code'], 0, first_caller)
        first = self.observe('first-worker-control', first_caller)
        self.assertEqual(first['fetches'], 1)
        self.assertEqual(first['run_statuses'], ['succeeded'])
        self.assertEqual(first['records']['total'], 1)
        saved = first['records']['records'][0]
        user_data = {'title': 'My title', 'note': 'Keep this note', 'pinned': True}
        self.fx.records.put(self.sid, 'items', saved['id'], user_data, actor='user', base_rev=saved['rev'])
        native_before = self.native_snapshot()
        self.write_feed(expanded=True)
        caller = self.case.invoke_shim() if shape == 'standalone' else self.public_scheduled_call()
        later = self.observe('later-distinct-scheduled-tick', caller)
        if shape == 'standalone':
            self.assertEqual(caller['exit_code'], 0, caller)
        else:
            self.assertNotIn('error', caller, caller)
            self.assertEqual(caller['status'], 'succeeded')
        self.assertEqual(later['fetches'], 2, 'A new scheduled occurrence must fetch fresh input, not report the old run')
        self.assertEqual(len(later['run_ids']), 2)
        self.assertEqual(later['run_statuses'], ['succeeded', 'succeeded'])
        self.assertEqual(later['records']['total'], 2)
        current = self.fx.records.get(self.sid, 'items', saved['id'])
        self.assertEqual(current['source']['title'], 'Source revised')
        self.assertEqual(current['data'], user_data)
        self.assertEqual(self.native_snapshot(), native_before, 'Local feed success must not settle or redispatch native work')
        retry_caller = self.case.invoke_shim() if shape == 'standalone' else self.public_scheduled_call()
        retry = self.observe('retry-fresh-fetch-approved-by-P12', retry_caller)
        if shape == 'standalone':
            self.assertEqual(retry_caller['exit_code'], 0, retry_caller)
        else:
            self.assertNotIn('error', retry_caller, retry_caller)
            self.assertEqual(retry_caller['status'], 'succeeded')
        self.assertEqual(retry['fetches'], 3)
        self.assertEqual(len(retry['run_ids']), 3)
        self.assertTrue(all(status == 'succeeded' for status in retry['run_statuses']))
        self.assertEqual(retry['records'], later['records'])
        self.assertEqual(self.fx.records.get(self.sid, 'items', saved['id'])['data'], user_data)
        self.assertEqual(self.native_snapshot(), native_before)

    def test_later_standalone_tick_fetches_fresh_after_background_manual_run(self):
        self.check_later_tick('standalone')

    def test_distinct_public_scheduled_execution_and_its_retry_fetch_fresh(self):
        self.check_later_tick('public-object')


if __name__ == '__main__':
    unittest.main(verbosity=2)
