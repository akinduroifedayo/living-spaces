"""Exercise the actual loose-module adapter against the packaged core, not a fake."""
import asyncio
import importlib.util
import os
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.python.review_customization_support import available_empty_cron_modules

ROOT = Path(__file__).resolve().parents[2]


class PackagedApiTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.dict(sys.modules, available_empty_cron_modules()))

    def test_chat_handlers_use_real_core_and_injected_libraries(self):
        (ROOT / '.run').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / '.run') as home:
            with patch.dict(os.environ, {'HERMES_HOME': home, 'LIVING_SPACES_DB': str(Path(home) / 'spaces.db')}):
                package = ROOT / 'src/living-spaces'
                spec = importlib.util.spec_from_file_location('packaged_tools_integration', package / '__init__.py', submodule_search_locations=[str(package)])
                assert spec is not None and spec.loader is not None
                tools = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = tools
                spec.loader.exec_module(tools)
                core = tools._core.load_core()
                result = tools.spaces_create(core, {'name': 'Chat Demo', 'files': {'index.html': '<h1>Public demo</h1>'}}, 'Demo')
                sid = result['space']
                self.assertEqual(result['rev'], 1)
                self.assertEqual(result['warnings'], [])
                self.assertEqual(tools.spaces_get(core, {'space': sid}, 'Demo')['id'], sid)
                detail = tools.spaces_read_file(core, {'space': sid, 'path': 'index.html'}, 'Demo')
                self.assertIn('Public demo', detail['text'])
                result = tools.spaces_edit_file(core, {'space': sid, 'path': 'index.html', 'old': 'Public demo', 'new': 'Changed demo', 'summary': 'Public edit'}, 'Demo')
                self.assertEqual(result['rev'], 2)
                result = tools.spaces_write_files(core, {'space': sid, 'files': {'theme.css': 'body{color:white}'}, 'summary': 'Add style'}, 'Demo')
                self.assertEqual(result['rev'], 3)
                tools.spaces_write_records(core, {'space': sid, 'ops': [{'op': 'put', 'collection': 'notes', 'id': 'one', 'data': {'note': 'Public note'}, 'base_rev': None}]}, 'Demo')
                rows = tools.spaces_query(core, {'space': sid, 'collection': 'notes'}, 'Demo')['records']
                self.assertEqual(rows[0]['data'], {'note': 'Public note'})
                self.assertEqual(len(tools.spaces_list(core, {}, 'Demo')), 1)
                remote = tools.spaces_write_files(core, {'space': sid, 'files': {'app.js': "const u = 'https://example.org/data.json'"}, 'summary': 'Add remote URL'}, 'Demo')
                self.assertIn('Network URLs in app.js are blocked at runtime; use space.net.fetch for public HTTPS', remote['warnings'])

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
