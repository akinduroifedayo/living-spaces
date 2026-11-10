"""Integration checks against the real core and upkeep, with explicitly injected source transport/failure."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src' / 'living-spaces'))
from living_spaces_core import db, projects, records, grants, feeds, runs


class SourceTransactionTests(unittest.TestCase):
    def setUp(self):
        (ROOT / '.run').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / '.run')
        self.addCleanup(self.temp.cleanup)
        env = patch.dict(os.environ, {'HERMES_HOME': self.temp.name,
                                     'LIVING_SPACES_DB': str(Path(self.temp.name) / 'spaces.db')})
        env.start()
        self.addCleanup(env.stop)
        self.sid = 'atomic-source'
        self.source = {'id': 'public-demo', 'url': 'https://research.example/feed', 'collection': 'papers'}
        projects.create_space('Atomic Source', owner='Demo', author='user',
                              files={'index.html': '<h1>Public demo</h1>'},
                              manifest={'entry': 'index.html', 'upkeep': {'handler': 'feed', 'sources': [self.source]}})
        grants.decide(self.sid, 'refresh', 'grant')
        self.payload = (ROOT / 'tests/python/fixtures/feeds/research.rss').read_bytes()

    def rows(self):
        return records.query(self.sid, 'papers')['records']

    def fetch(self):
        with patch.object(feeds, 'fetch', return_value=self.payload):
            return runs.start_refresh(self.sid, trigger='manual', actor='user', wait=True)

    def test_source_storage_failure_rolls_back_prefix(self):
        original = records._upsert_source
        calls = 0

        def fail_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError('Injected failure after a real first source write')
            return original(*args, **kwargs)

        before = records.changes_since(self.sid, 0)
        with patch.object(records, '_upsert_source', side_effect=fail_second):
            run = self.fetch()
        self.assertEqual(calls, 2)
        self.assertEqual(run['status'], 'failed')
        self.assertEqual(self.rows(), [], 'A failed source must not commit a prefix')
        self.assertEqual(records.changes_since(self.sid, 0), before)
        self.assertEqual(run['changed']['added'], 0)

    def test_successful_refresh_preserves_user_fields_and_no_change_is_truthful(self):
        self.assertEqual(self.fetch()['status'], 'succeeded')
        record = self.rows()[0]
        records.put(self.sid, 'papers', record['id'], {'note': 'Synthetic demo note', 'status': 'reading'},
                    actor='user', base_rev=record['rev'])
        again = self.fetch()
        self.assertEqual(again['status'], 'succeeded')
        self.assertEqual(again['changed']['added'], 0)
        self.assertEqual(again['changed']['updated'], 0)
        saved = records.get(self.sid, 'papers', record['id'])
        self.assertEqual(saved['data'], {'note': 'Synthetic demo note', 'status': 'reading'})
        self.assertTrue(saved['source']['title'])

    def test_revocation_while_transport_runs_prevents_new_records(self):
        def fetch_and_revoke(*args):
            grants.decide(self.sid, 'refresh', 'revoke')
            return self.payload
        with patch.object(feeds, 'fetch', side_effect=fetch_and_revoke):
            run = runs.start_refresh(self.sid, trigger='manual', actor='user', wait=True)
        self.assertEqual(run['status'], 'canceled')
        self.assertEqual(self.rows(), [])

    def test_denied_refresh_never_calls_transport(self):
        grants.decide(self.sid, 'refresh', 'deny')
        with patch.object(feeds, 'fetch') as transport:
            run = runs.start_refresh(self.sid, trigger='manual', actor='user', wait=True)
        self.assertEqual(run['status'], 'blocked')
        transport.assert_not_called()
        self.assertEqual(self.rows(), [])


if __name__ == '__main__':
    unittest.main()
