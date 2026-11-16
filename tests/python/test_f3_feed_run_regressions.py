"""Real feed code and generated shim; cron dispatch and HTTPS are synthetic."""
from contextlib import ExitStack
from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from typing import Any
from unittest.mock import patch

from tests.python.review_customization_support import CustomizationFixture, PACKAGE

ROOT = Path(__file__).resolve().parents[2]
SHIM_BOOTSTRAP = '''import importlib.util, runpy, sys
from importlib import import_module
from pathlib import Path
from unittest.mock import patch
package, shim = sys.argv[1:]
spec = importlib.util.spec_from_file_location('feed_probe_loader', Path(package) / '_core.py')
loader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loader)
core = loader.load_core()
feeds = import_module(core.__name__ + '.feeds')
with patch.object(feeds, 'fetch', return_value=b'<rss><channel/></rss>'):
    runpy.run_path(shim, run_name='__main__')
'''


@dataclass(frozen=True)
class PublicExecution:
    job_id: str
    execution_id: str = 'synthetic-public-feed-execution'


class FeedRunRegressions(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        temp = Path(os.environ.get('F3_PROCESS_TEST_TMPDIR', ROOT / '.run')).resolve()
        if not temp.is_relative_to(Path('/Volumes/Expansion')):
            raise ValueError('Owned Expansion temporary root required')
        temp.mkdir(parents=True, exist_ok=True)
        self.stack.enter_context(patch.object(tempfile, 'tempdir', str(temp)))
        self.fx: Any = CustomizationFixture(self.stack)
        self.sid = self.fx.make(handler='feed')
        self.fx.grants.request(self.sid, 'net', scope={}, purpose='Synthetic feed regression', actor='user')
        self.fx.grants.decide(self.sid, 'net', 'grant')
        self.jid = self.fx.schedule(self.sid, kind='feed')['link']['cron_job_id']
        self.shim = self.fx.home / 'scripts' / ('living-spaces-refresh-' + self.sid + '.py')
        self.attempts = []

    def invoke_shim(self):
        env = {k: v for k, v in os.environ.items() if k in ('PATH', 'LANG', 'LOGNAME', 'SHELL', 'USER')}
        env.update(HOME=str(self.fx.home), HERMES_HOME=str(self.fx.home),
                   LIVING_SPACES_DB=str(self.fx.home / 'spaces.db'), TMPDIR=str(self.fx.home),
                   PYTHONDONTWRITEBYTECODE='1', HERMES_DISABLE_LAZY_INSTALLS='1')
        completed = subprocess.run([sys.executable, '-B', '-c', SHIM_BOOTSTRAP, str(PACKAGE), str(self.shim)],
                                   env=env, capture_output=True, text=True, timeout=25)
        observation = {'exit_code': completed.returncode, 'stdout': completed.stdout, 'stderr': completed.stderr}
        self.attempts.append(observation)
        return observation

    def explicit_run(self, shape):
        original = self.fx.ctx.dispatch_tool

        def dispatch(name, args):
            reply = original(name, args)
            if args['action'] == 'run':
                if shape == 'standalone':
                    self.invoke_shim()
                else:
                    self.fx.ctx.execution = (PublicExecution(args['job_id']) if shape == 'object'
                                             else {'job_id': args['job_id'], 'execution_id': 'synthetic-public-feed-execution'})
                    try:
                        with patch.object(self.fx.feeds, 'fetch', return_value=b'<rss><channel/></rss>'):
                            run = self.fx.runs.start_refresh(self.sid, trigger='schedule', actor='upkeep:schedule', wait=True)
                        self.attempts.append({'run_status': run['status']})
                    except self.fx.core.SpacesError as exc:
                        self.attempts.append({'error': exc.to_dict()})
                    finally:
                        self.fx.ctx.execution = None
            return reply

        with patch.object(self.fx.ctx, 'dispatch_tool', side_effect=dispatch):
            result = self.fx.upkeep.upkeep_action(self.sid, 'run', actor='user')
        return result

    def observe(self, scenario, result=None):
        runs = self.fx.runs.list_runs(self.sid)
        print(json.dumps({'scenario': scenario, 'attempts': self.attempts,
                          'persisted_runs': [{'status': row['status'], 'detail': row['detail']} for row in runs],
                          'api_result': result, 'evidence_scope': 'Real generated script/core/SQLite. Synthetic dispatch and HTTPS.'}), flush=True)
        return runs

    def assert_one_succeeded(self, runs):
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]['status'], 'succeeded')

    def test_scheduled_standalone_feed_shim_refreshes(self):
        result = self.invoke_shim()
        runs = self.observe('scheduled-standalone-control')
        self.assertEqual(result['exit_code'], 0, result)
        self.assert_one_succeeded(runs)

    def test_explicit_feed_run_executes_generated_standalone_shim(self):
        result = self.explicit_run('standalone')
        runs = self.observe('explicit-run-standalone-shim', result)
        self.assertEqual(len(self.attempts), 1)
        self.assertEqual(self.attempts[0]['exit_code'], 0, self.attempts)
        self.assert_one_succeeded(runs)

    def test_public_frozen_cron_identity_attaches_feed_run(self):
        result = self.explicit_run('object')
        runs = self.observe('explicit-run-object-identity', result)
        self.assertEqual(self.attempts, [{'run_status': 'succeeded'}])
        self.assert_one_succeeded(runs)

    def test_existing_synthetic_dict_identity_remains_compatible(self):
        result = self.explicit_run('dict')
        runs = self.observe('explicit-run-dict-control', result)
        self.assertEqual(self.attempts, [{'run_status': 'succeeded'}])
        self.assert_one_succeeded(runs)


if __name__ == '__main__':
    unittest.main(verbosity=2)
