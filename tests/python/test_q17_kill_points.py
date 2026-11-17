"""Real process death at public-native and SQLite boundaries; no real Hermes cron."""
from contextlib import contextmanager
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests.python.test_f3_process_claims import SharedCronContext, snapshot
from tests.python.review_customization_support import AGENT_PROMPT


def worker(root, command, point, native_action):
    sys.path.insert(0, str(ROOT / 'src/living-spaces'))
    core = importlib.import_module('living_spaces_core')
    ctx = SharedCronContext(root, core, 'q17', 'background')
    core.configure_context(ctx)
    if command == 'seed':
        sid = core.create_space('Q17 process', owner='Review', author='user', files={'index.html': '<h1>Q17</h1>'},
                                manifest={'upkeep': {'handler': 'agent', 'prompt': AGENT_PROMPT}})['id']
        (root / 'space').write_text(sid)
        return
    sid = (root / 'space').read_text()
    reached = False
    original_dispatch, original_write = ctx.dispatch_tool, core.db.write

    def dispatch(name, args):
        nonlocal reached
        target = args['action'] == native_action
        if target and point == 'before_native':
            os._exit(73)
        result = original_dispatch(name, args)
        if target:
            reached = True
            if point == 'after_native':
                os._exit(73)
        return result

    @contextmanager
    def write():
        with original_write() as conn:
            yield conn
            if reached and point == 'before_sqlite':
                os._exit(73)
        if reached and point == 'after_sqlite':
            os._exit(73)

    try:
        with patch.object(ctx, 'dispatch_tool', side_effect=dispatch), patch.object(core.db, 'write', write):
            if command in ('schedule', 'replace'):
                result = core.schedule_upkeep(sid, kind='agent', cadence='every 6h', timezone='UTC', prompt=AGENT_PROMPT, actor='user')
            elif command == 'inspect':
                result = core.get_upkeep(sid)
            elif command == 'recover':
                result = core.upkeep_action(sid, 'recover', actor='user', confirm=sid)
            else:
                result = core.upkeep_action(sid, command, actor='user')
        record = {'result': result}
    except core.SpacesError as exc:
        record = {'error': exc.to_dict()}
    print(json.dumps(record))


class Q17KillPointTests(unittest.TestCase):
    def exercise(self, command):
        base = Path(os.environ['TMPDIR'])
        for native_action in ({'schedule': ('create', 'resume'), 'replace': ('create', 'resume', 'remove')}.get(command, (command,))):
            for point in ('before_native', 'after_native', 'before_sqlite', 'after_sqlite'):
                with self.subTest(command=command, native=native_action, point=point), tempfile.TemporaryDirectory(dir=base, prefix='q17-kill-') as tmp:
                    root = Path(tmp)
                    for directory in ('home', 'hermes', 'tmp'):
                        (root / directory).mkdir()
                    env = {'HOME': str(root / 'home'), 'HERMES_HOME': str(root / 'hermes'), 'TMPDIR': str(root / 'tmp'),
                           'LIVING_SPACES_DB': str(root / 'store.db'), 'PATH': '/usr/bin:/bin', 'LANG': 'C', 'LC_ALL': 'C'}

                    def call(action, at='', native=''):
                        return subprocess.run([sys.executable, '-I', '-B', str(Path(__file__).resolve()), '--worker', str(root), action, at, native],
                                              env=env, cwd=root, capture_output=True, text=True, timeout=20)

                    self.assertEqual(call('seed').returncode, 0)
                    if command != 'schedule':
                        seeded = call('schedule')
                        self.assertEqual(seeded.returncode, 0, seeded.stderr)
                        if command == 'resume':
                            self.assertEqual(call('pause').returncode, 0)
                    killed = call(command, point, native_action)
                    self.assertEqual(killed.returncode, 73, killed.stderr)
                    before = snapshot(root)
                    shown = json.loads(call('inspect').stdout)['result']
                    expected_unknown = command == 'run' or point != 'after_sqlite'
                    print(json.dumps({'command': command, 'native': native_action, 'kill': point,
                                      'native_jobs': before['jobs'], 'local': shown, 'expected_unknown': expected_unknown}), flush=True)
                    self.assertEqual(bool(shown.get('recovery')), expected_unknown)
                    self.assertEqual(shown.get('recovery_aid', {}).get('settings', {}).get('prompt'), AGENT_PROMPT)
                    if expected_unknown:
                        self.assertEqual(shown['recovery']['state'], 'unknown')
                        self.assertEqual(shown['recovery']['operations'][0]['action'], 'schedule' if command == 'replace' else command)
                    self.assertEqual(snapshot(root)['calls'], before['calls'])
                    for _ in range(2):
                        recovered = call('recover')
                        self.assertEqual(recovered.returncode, 0, recovered.stderr)
                        self.assertNotIn('error', json.loads(recovered.stdout))
                    after = snapshot(root)
                    self.assertEqual(after['jobs'], {})
                    self.assertEqual(sum(c[0] == 'run' for c in after['calls']), sum(c[0] == 'run' for c in before['calls']))
                    recreated = call('schedule')
                    self.assertNotIn('error', json.loads(recreated.stdout))
                    self.assertEqual(len(snapshot(root)['jobs']), 1)

    def test_schedule_kill_points(self):
        self.exercise('schedule')

    def test_replace_kill_points(self):
        self.exercise('replace')

    def test_pause_kill_points(self):
        self.exercise('pause')

    def test_resume_kill_points(self):
        self.exercise('resume')

    def test_run_kill_points(self):
        self.exercise('run')

    def test_remove_kill_points(self):
        self.exercise('remove')


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--worker':
        worker(Path(sys.argv[2]), *sys.argv[3:6])
    else:
        unittest.main()
