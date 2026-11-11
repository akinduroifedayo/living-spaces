import copy
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/living-spaces'))
import living_spaces_core as core
from living_spaces_core import feeds, records, runs

FEED = (Path(__file__).parent / 'fixtures/feeds/research.rss').read_bytes()
UPDATED_FEED = FEED.replace(b'Small Models for Imaginary Gardens', b'Updated Public Research')


class CorePartialsTests(unittest.TestCase):
    def setUp(self):
        (ROOT / '.run').mkdir(exist_ok=True)
        temp = tempfile.TemporaryDirectory(prefix='partials-', dir=ROOT / '.run')
        self.addCleanup(temp.cleanup)
        env = patch.dict(os.environ, {'HERMES_HOME': temp.name,
                                     'LIVING_SPACES_DB': str(Path(temp.name) / 'spaces.db')})
        env.start()
        self.addCleanup(env.stop)
        self.sid = core.create_space('Partials Probe', owner='Demo', author='harness-fixture',
                                     files={'index.html': '<main>Public demo</main>'},
                                     manifest={'data': {'version': 1}, 'upkeep': {'handler': 'feed', 'sources': [
                                         {'id': 'demo', 'url': 'https://research.example/feed', 'collection': 'papers'}]}})['id']
        core.decide(self.sid, 'refresh', 'grant', actor='user')
        with patch.object(feeds, 'fetch', return_value=FEED):
            self.assertEqual(runs.start_refresh(self.sid, trigger='manual', actor='user', wait=True)['status'], 'succeeded')
        self.record = next(r for r in core.query(self.sid, 'papers')['records']
                           if r['source']['title'] == 'Small Models for Imaginary Gardens')
        self.record = records.put(self.sid, 'papers', self.record['id'], {'notes': 'Original note', 'status': 'reading'},
                                  actor='app', base_rev=self.record['rev'])
        self.session = core.open_session(self.sid)['session']

    def put(self, rev, note):
        return core.dispatch(self.sid, self.session, 'data.put', {
            'collection': 'papers', 'id': self.record['id'], 'data': {'notes': note}, 'base_rev': rev})

    def race(self, edit_first):
        entered, release = threading.Event(), threading.Event()
        result = []
        failures = []

        def fetch(sid, url):
            entered.set()
            if not release.wait(10):
                raise TimeoutError('Test did not release refresh')
            return UPDATED_FEED

        def refresh():
            try:
                result.append(runs.start_refresh(self.sid, trigger='manual', actor='user', wait=True))
            except Exception as exc:
                failures.append(exc)

        cursor = core.query(self.sid, 'papers')['seq']
        before = self.record
        with patch.object(feeds, 'fetch', side_effect=fetch):
            worker = threading.Thread(target=refresh)
            worker.start()
            try:
                self.assertTrue(entered.wait(10), 'Refresh never reached the fetch barrier')
                self.assertEqual(core.list_runs(self.sid)[0]['status'], 'running')
                if edit_first:
                    saved = self.put(before['rev'], 'Saved during refresh')
                    self.assertTrue(saved['ok'], saved)
                    self.assertEqual(saved['result']['rev'], before['rev'] + 1)
                    self.assertEqual(saved['result']['source'], before['source'])
            finally:
                release.set()
                worker.join(15)
        self.assertFalse(worker.is_alive(), 'Refresh worker did not finish')
        self.assertEqual(failures, [])
        self.assertEqual(result[0]['status'], 'succeeded')
        self.assertEqual(result[0]['changed'], {'added': 0, 'updated': 1, 'unchanged': 1, 'removed': 0})
        current = records.get(self.sid, 'papers', before['id'])
        self.assertEqual(current['rev'], before['rev'] + (2 if edit_first else 1))
        self.assertEqual(current['data'], {'notes': 'Saved during refresh' if edit_first else 'Original note', 'status': 'reading'})
        self.assertEqual(current['source']['title'], 'Updated Public Research')
        changes = core.changes_since(self.sid, cursor)
        stale = self.put(before['rev'] + (1 if edit_first else 0), 'Stale overwrite')
        self.assertFalse(stale['ok'])
        self.assertEqual(stale['error']['code'], 'conflict')
        self.assertEqual(stale['error']['current'], current)
        self.assertEqual(records.get(self.sid, 'papers', before['id']), current)
        self.assertEqual(core.changes_since(self.sid, cursor), changes)
        self.assertEqual([(c['op'], c['rev']) for c in changes['changes']],
                         [('put', before['rev'] + 1), ('source', before['rev'] + 2)] if edit_first
                         else [('source', before['rev'] + 1)])
        if not edit_first:
            saved = self.put(current['rev'], 'Resolved after conflict')
            self.assertTrue(saved['ok'], saved)
            self.assertEqual(saved['result']['source'], current['source'])
            self.assertEqual(saved['result']['data'], {'notes': 'Resolved after conflict', 'status': 'reading'})
            self.assertEqual(saved['result']['rev'], current['rev'] + 1)

    def test_guest_edit_during_refresh_survives_and_then_becomes_stale(self):
        self.race(edit_first=True)

    def test_refresh_wins_race_and_stale_guest_can_resolve_with_current(self):
        self.race(edit_first=False)

    def test_incompatible_restore_keeps_migrated_data_and_revision_history(self):
        manifest = copy.deepcopy(core.get_space(self.sid)['manifest'])
        manifest['data'] = {'version': 2, 'migrations': [{'to': 2, 'ops': [
            {'op': 'rename_field', 'collection': 'papers', 'from': 'notes', 'to': 'annotation'}]}]}
        core.write_files(self.sid, files={}, manifest=manifest, base_rev=1, author='harness-fixture', summary='Migrate notes')
        before = core.query(self.sid, 'papers')
        revisions = core.list_revisions(self.sid)
        self.assertEqual(records.get(self.sid, 'papers', self.record['id'])['data'],
                         {'annotation': 'Original note', 'status': 'reading'})
        with self.assertRaises(core.SpacesError) as caught:
            core.restore_revision(self.sid, 1, author='user')
        error = caught.exception.to_dict()
        self.assertEqual((error['code'], error['from_version'], error['to_version']), ('incompatible', 2, 1))
        self.assertEqual(core.query(self.sid, 'papers'), before)
        self.assertEqual(core.list_revisions(self.sid), revisions)
        self.assertEqual(core.get_space(self.sid)['data_version'], 2)
