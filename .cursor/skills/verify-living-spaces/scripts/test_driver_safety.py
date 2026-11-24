#!/Users/ifedayoakinduro/.hermes/hermes-agent/venv/bin/python
"""Driver safety tests, NOT Living Spaces product/UI coverage."""
import contextlib
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

import control as c


class DriverSafety(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='w32-safety-', dir='/Users/ifedayoakinduro/.hermes/cache/scratch')
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def prior_run(self, name):
        out = self.root / name
        state = out / 'state'
        state.mkdir(parents=True)
        (state / 'keep.txt').write_text('existing run must survive refusal')
        c.dump(out / 'instance.json', dict(pid=999999991, pgid=999999991, started='not a real process',
                                          state=str(state), revision=c.BASE))
        return out

    def test_reused_path_is_not_cleanup_authority(self):
        out = self.prior_run('proof-existing')
        with self.assertRaises(FileExistsError):
            c.proof(out, Path(__file__).resolve().parents[4])
        self.assertTrue((out / 'state/keep.txt').exists(), 'proof refusal destroyed prior state')
        out = self.prior_run('launch-existing')
        result = subprocess.run([c.PYTHON, str(Path(c.__file__)), 'launch', '--out', str(out)],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((out / 'state/keep.txt').exists(), 'launch refusal destroyed prior state')
        self.assertFalse((out / 'cleanup.json').exists(), 'refusal overwrote prior teardown receipt')

    def test_orphan_child_is_cleaned_and_logs_survive(self):
        out = self.root / 'orphan'
        state = out / 'state'
        (state / 'ud').mkdir(parents=True)
        (state / 'home/logs').mkdir(parents=True)
        (state / 'home/logs/safety.log').write_text('owned orphan cleanup proof')
        child_pid = out / 'child.pid'
        code = ('import subprocess,time; from pathlib import Path; '
                f'p=subprocess.Popen([{c.PYTHON!r},"-c","import time; time.sleep(60)",{str(state / "ud")!r}]); '
                f'Path({str(child_pid)!r}).write_text(str(p.pid)); time.sleep(1)')
        leader = subprocess.Popen([c.PYTHON, '-c', code], start_new_session=True,
                                  env={'PATH': '/usr/bin:/bin', 'TMPDIR': os.environ['TMPDIR']})
        child = None
        try:
            row = next(p for p in c.processes() if p['pid'] == leader.pid)
            c.dump(out / 'instance.json', dict(pid=leader.pid, pgid=leader.pid, started=row['started'],
                                              state=str(state), revision=c.BASE))
            leader.wait(timeout=5)
            child = int(child_pid.read_text())
            self.assertTrue(any(p['pid'] == child for p in c.processes()))
            c.cleanup(out)
            self.assertFalse(any(p['pid'] == child for p in c.processes()))
            self.assertEqual((out / 'backend-logs/safety.log').read_text(), 'owned orphan cleanup proof')
            self.assertTrue(json.loads((out / 'cleanup.json').read_text())['state_removed'])
        finally:
            if leader.poll() is None:
                leader.terminate()
                leader.wait(timeout=5)
            if child and any(p['pid'] == child and p['pgid'] == leader.pid for p in c.processes()):
                os.kill(child, signal.SIGKILL)
                time.sleep(.3)

    def test_persisted_note_without_visible_success_cannot_pass(self):
        # Unit-test the driver classifier, never a substitute for actual UI evidence.
        for status_text, should_pass in [('Not saved: error', False), ('Note saved', True)]:
            with self.subTest(status=status_text):
                out = self.root / ('positive' if should_pass else 'negative')
                def fake_launch(path, repo, acquisition):
                    path.mkdir()
                    acquisition['created'] = True
                def fake_guest_read(path, selector='body', position=False):
                    if selector == '#status':
                        return {'text': status_text}
                    if selector == '#notes':
                        return {'text': 'W32 persisted note'}
                    return [{'text': 'Verification Notebook\nW32 persisted note'}]
                mocks = dict(launch=fake_launch, setup=lambda *_: None, doctor=lambda *_: {},
                             wait_text=lambda *_: None,
                             fixture=lambda *_: None, click=lambda *_: None, capture=lambda *_: None,
                             guest_fill=lambda *_: None, guest_click=lambda *_: None,
                             records=lambda *_: {'records': [{'data': 'W32 persisted note'}]},
                             guest_read=fake_guest_read, diagnostic=lambda *_: {},
                             manifest=lambda *_: {'revision': c.BASE})
                with contextlib.ExitStack() as stack:
                    for name, fn in mocks.items():
                        stack.enter_context(patch.object(c, name, fn))
                    stack.enter_context(patch.object(c.time, 'sleep', lambda *_: None))
                    stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                    if should_pass:
                        c.proof(out, self.root)
                    else:
                        with self.assertRaises(AssertionError):
                            c.proof(out, self.root)
                    result = json.loads((out / 'result.json').read_text())
                    self.assertEqual(result['primary_desktop'].startswith('passed'), should_pass)
                    if not should_pass:
                        self.assertIn('visible', result['primary_error'].lower())


if __name__ == '__main__':
    unittest.main(verbosity=2)
