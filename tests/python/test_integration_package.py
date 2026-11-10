"""Exercise the actual loose-module adapter against the packaged core, not a fake."""
import asyncio
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


class PackagedApiTests(unittest.TestCase):
    def test_loose_rest_adapter_uses_real_public_core(self):
        (ROOT / '.run').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / '.run') as home:
            with patch.dict(os.environ, {'HERMES_HOME': home, 'LIVING_SPACES_DB': str(Path(home) / 'spaces.db')}):
                spec = importlib.util.spec_from_file_location('packaged_api_integration', ROOT / 'src/living-spaces/dashboard/plugin_api.py')
                api = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(api)
                result = asyncio.run(api.spaces_list())
                self.assertEqual(result, {'spaces': [], 'seq_global': 0})
                core = api.load_core()
                created = core.create_space('Public Demo', owner='Demo', author='user', files={'index.html': '<h1>Public demo</h1>'}, manifest={'entry': 'index.html'})
                sid = created['id']
                self.assertEqual(asyncio.run(api.space_detail(sid))['id'], sid)
                self.assertEqual(len(asyncio.run(api.spaces_list())['spaces']), 1)
                session = asyncio.run(api.session_open(sid))
                self.assertTrue(session['session'])
                self.assertTrue(asyncio.run(api.space_bundle(sid))['files'])
                self.assertEqual(asyncio.run(api.opened(sid))['id'], sid)
                self.assertEqual(asyncio.run(api.archive(sid))['status'], 'archived')
                self.assertEqual(asyncio.run(api.unarchive(sid))['status'], 'active')
