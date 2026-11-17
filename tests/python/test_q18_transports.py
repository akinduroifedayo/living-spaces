"""Q18 public REST and registered agent tools use the same real store."""
import importlib.util
import json
import sys
from types import SimpleNamespace
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from .test_core_store import CoreCase, ROOT, projects, records


class Q18TransportTests(CoreCase):
    def load(self, name, path, package=False):
        spec = importlib.util.spec_from_file_location(name, path,
            submodule_search_locations=[str(path.parent)] if package else None)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {name: module}):
            spec.loader.exec_module(module)
        return module

    def test_registered_agent_summary_proposal_and_exact_execution(self):
        plugin = self.load('q18_plugin', ROOT / 'src/living-spaces/__init__.py', True)
        tools = {}
        plugin.register(SimpleNamespace(register_tool=lambda **tool: tools.update({tool['name']: tool}),
            register_rpc=lambda *args, **kwargs: None, register_skill=lambda *args, **kwargs: None))
        reply = lambda name, args: json.loads(tools[name]['handler'](args, profile_name='Demo'))
        detail = reply('spaces_get', {'space': self.sid})
        self.assertIn('storage', detail['result'], 'Agent detail needs additive storage accounting')
        self.assertIn('spaces_retention', tools, 'Agent needs an explicit retention entry point')
        records.upsert_source(self.sid, 'papers', 'old', {'title': 'Old'}, {}, actor='feed')
        scope = {'categories': ['records'], 'before': 2**53 - 1}
        proposal = reply('spaces_retention', {'space': self.sid, 'scope': scope})['result']
        self.assertEqual(proposal['remove']['records'][0]['id'], 'old')
        refused = reply('spaces_retention', {'space': self.sid, 'scope': scope, 'proposal_id': proposal['id'], 'confirm': self.sid})
        self.assertFalse(refused['ok'])
        executed = reply('spaces_retention', {'space': self.sid, 'scope': scope, 'proposal_id': proposal['id'], 'confirm': proposal['confirmation']})
        self.assertTrue(executed['ok'], executed)
        self.assertEqual(executed['result']['removed']['records'], 1)

    def test_host_routes_scope_validate_and_reject_stale_without_mutation(self):
        api = self.load('q18_api', ROOT / 'src/living-spaces/dashboard/plugin_api.py')
        app = FastAPI()
        app.include_router(api.router)
        client = TestClient(app)
        self.addCleanup(client.close)
        base = f'/spaces/{self.sid}'
        detail = client.get(base).json()
        self.assertIn('storage', detail, 'Host detail needs additive storage accounting')
        scope = {'categories': ['revisions'], 'before': 2**53 - 1}
        response = client.post(base + '/retention/propose', json={'scope': scope})
        self.assertEqual(response.status_code, 200, response.text)
        proposal = response.json()
        self.assertEqual(client.post(base + '/retention/execute', json={'scope': scope}).status_code, 400)
        self.write({'index.html': 'Changed'})
        response = client.post(base + '/retention/execute', json={'scope': scope, 'proposal_id': proposal['id'], 'confirm': proposal['confirmation']})
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual([row['rev'] for row in projects.list_revisions(self.sid)], [2, 1])
        self.assertEqual(client.post(base + '/retention/propose', json={'scope': {'categories': ['native_history'], 'before': 1}}).status_code, 400)
