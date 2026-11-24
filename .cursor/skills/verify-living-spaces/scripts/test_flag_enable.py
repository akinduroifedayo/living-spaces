#!/Users/ifedayoakinduro/.hermes/hermes-agent/venv/bin/python
"""Mocked driver boundary tests. These are not product or Desktop proof."""
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import control as c
import flag_enable as f


class FlagBoundary(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir='/Users/ifedayoakinduro/.hermes/cache/scratch', prefix='w32-flag-tests-')
        self.out = Path(self.tmp.name).resolve()
        self.ud = self.out / 'state/ud'
        self.ud.mkdir(parents=True)
        self.m = dict(pid=456789, pgid=456789, started='test identity', state=str(self.out / 'state'))
        self.command = f'Hermes Helper --type=renderer --user-data-dir={self.ud}'
        self.storage = f'n{self.ud}/Local Storage/leveldb/LOCK\n'
        self.value = '{"other-plugin":false}'
        self.writes = []
        def evaluate(out, expression):
            if 'localStorage.setItem' in expression:
                self.writes.append(expression)
                self.value = '{"other-plugin":false,"living-spaces":true}'
                return self.value
            if expression.startswith('({'):
                return dict(url='file:///app/dist/index.html', origin='file://', flag=self.value)
            return self.value
        self.fake = SimpleNamespace(owned=lambda out: self.m, processes=lambda: [dict(pgid=456789, command=self.command)],
                                    call=lambda *a, **k: dict(frameTree=dict(frame=dict(url='file:///app/dist/index.html', securityOrigin='file://'))),
                                    evaluate=evaluate, dump=c.dump)

    def tearDown(self):
        self.tmp.cleanup()

    def invoke(self):
        with (patch.object(f.Path, 'home', return_value=Path('/test-real-home')),
              patch.object(f.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout=self.storage)),
              patch.object(f, 'reload_with_logs', lambda *_: None)):
            f.enable(self.fake, self.out)

    def test_matching_runtime_storage_permits_only_the_one_decision(self):
        self.invoke()
        self.assertEqual(len(self.writes), 1)
        self.assertEqual(json.loads(self.value), {'other-plugin': False, 'living-spaces': True})
        self.assertTrue(json.loads((self.out / 'flag-isolation.json').read_text())['proven'])
        self.assertTrue((self.out / 'flag-after-reload.json').exists())

    def test_missing_lock_refuses_before_any_flag_write(self):
        self.storage = ''
        with self.assertRaisesRegex(AssertionError, 'Local Storage lock'):
            self.invoke()
        self.assertEqual(self.writes, [])
        self.assertFalse((self.out / 'flag-write.json').exists())

    def test_foreign_renderer_directory_refuses_before_any_flag_write(self):
        self.command = 'Hermes Helper --type=renderer --user-data-dir=/test-real-home/Library/Application Support/Hermes'
        with self.assertRaisesRegex(AssertionError, 'Renderer userData'):
            self.invoke()
        self.assertEqual(self.writes, [])

    def test_foreign_open_local_storage_refuses_before_any_flag_write(self):
        self.storage += 'n/test-real-home/Library/Application Support/Hermes/Local Storage/leveldb/LOCK\n'
        with self.assertRaisesRegex(AssertionError, 'Foreign Local Storage'):
            self.invoke()
        self.assertEqual(self.writes, [])

    def test_fixture_uses_the_sandbox_supported_click_path(self):
        html = (Path(__file__).resolve().parents[1] / 'fixtures/notebook.html').read_text()
        self.assertNotIn('<form', html)
        self.assertNotIn('type="submit"', html)
        self.assertIn('type="button" id="save"', html)
        self.assertIn("save.addEventListener('click'", html)


if __name__ == '__main__':
    unittest.main(verbosity=2)
