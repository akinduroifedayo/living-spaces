import json
import os
import sqlite3
from pathlib import Path
from unittest.mock import patch

from .test_core_store import CoreCase
from living_spaces_core import bridge, db, grants, projects, records, sessions


class Q10DraftTests(CoreCase):
    def setUp(self):
        super().setUp()
        self.session = sessions.open_session(self.sid)['session']
        self.key = dict(editor='notes', schema=1, collection='papers', id='paper')
        self.draft = dict(value={'note': 'Q10_PRIVATE_DRAFT'}, baseRev=0, state='idle')

    def call(self, op, args, session=None, sid=None, request_id=None):
        return bridge.dispatch(sid or self.sid, session or self.session, op, args, request_id)

    def store(self, **key):
        reply = self.call('draft.put', {**self.key, **key, 'draft': self.draft})
        self.assertTrue(reply['ok'], reply)
        return reply

    def test_reopen_namespace_is_separate_and_scoped(self):
        before = self.counts()
        self.store()
        sessions.close_session(self.session)
        self.session = sessions.open_session(self.sid)['session']
        found = self.call('draft.get', self.key)
        self.assertTrue(found['ok'], found)
        self.assertEqual(found['result']['draft'], self.draft)
        self.assertEqual(self.counts(), before)
        self.assertEqual(records.query(self.sid, 'papers')['records'], [])
        self.assertNotIn('Q10_PRIVATE_DRAFT', json.dumps(projects.get_space(self.sid)))
        for key in ({'editor': 'other'}, {'id': 'other'}, {'collection': 'other'}, {'schema': 2}):
            reply = self.call('draft.get', {**self.key, **key})
            self.assertTrue(reply['ok'], reply)
            self.assertIsNone(reply['result']['draft'])
        other = self.create('Other')['id']
        other_session = sessions.open_session(other)['session']
        self.assertIsNone(self.call('draft.get', self.key, sid=other, session=other_session)['result']['draft'])

    def test_grant_and_closed_session_never_deliver_drafts(self):
        self.store()
        original_call = bridge._call
        def close_before_delivery(*args):
            result = original_call(*args)
            sessions.close_session(self.session)
            return result
        with patch.object(bridge, '_call', side_effect=close_before_delivery):
            reply = self.call('draft.get', self.key)
        self.assertFalse(reply['ok'], reply)
        self.assertNotIn('Q10_PRIVATE_DRAFT', json.dumps(reply))
        self.session = sessions.open_session(self.sid)['session']
        grants.decide(self.sid, 'data', 'revoke')
        reply = self.call('draft.get', self.key)
        self.assertFalse(reply['ok'], reply)
        self.assertNotIn('Q10_PRIVATE_DRAFT', json.dumps(reply))
        grants.decide(self.sid, 'data', 'grant')
        self.assertEqual(self.call('draft.get', self.key)['result']['draft'], self.draft)

    def test_bounded_count_bytes_and_deterministic_expiry(self):
        self.store()
        from living_spaces_core import drafts
        with patch.object(db, 'now', return_value=1000):
            for n in range(drafts.MAX_COUNT + 1):
                self.store(id=f'r{n:03}')
        with patch.object(db, 'now', return_value=1001):
            self.assertIsNone(self.call('draft.get', {**self.key, 'id': 'r000'})['result']['draft'])
            self.assertEqual(self.call('draft.get', {**self.key, 'id': f'r{drafts.MAX_COUNT:03}'})['result']['draft'], self.draft)
        reply = self.call('draft.put', {**self.key, 'draft': {'value': 'x' * (drafts.MAX_ENTRY_BYTES + 1)}})
        self.assertFalse(reply['ok'], reply)
        self.assertEqual(reply['error']['code'], 'limit')
        with patch.object(db, 'now', return_value=1000 + drafts.TTL_SECONDS + 1):
            self.assertIsNone(self.call('draft.get', {**self.key, 'id': 'r001'})['result']['draft'])

    def test_confirmed_save_clears_draft_conflict_does_not(self):
        self.store()
        args = {**self.key, 'data': {'note': 'mine'}, 'base_rev': 0}
        first = self.call('editor.save', args, request_id='q10-save')
        self.assertTrue(first['ok'], first)
        self.assertEqual(records.get(self.sid, 'papers', 'paper')['data'], {'note': 'mine'})
        self.assertIsNone(self.call('draft.get', self.key)['result']['draft'])
        self.store()
        other = records.put(self.sid, 'papers', 'paper', {'note': 'chat'}, actor='chat', base_rev=1)
        conflict = self.call('editor.save', {**args, 'base_rev': 1}, request_id='q10-conflict')
        self.assertEqual(conflict['error']['code'], 'conflict')
        self.assertEqual(conflict['error']['current'], other)
        self.assertEqual(self.call('draft.get', self.key)['result']['draft'], self.draft)
        self.assertEqual(records.get(self.sid, 'papers', 'paper'), other)

    def test_discard_and_schema_compatibility(self):
        self.store()
        self.assertTrue(self.call('draft.delete', self.key)['ok'])
        self.assertIsNone(self.call('draft.get', self.key)['result']['draft'])
        self.store()
        manifest = self.manifest_v2([])
        self.write({'space.json': json.dumps(manifest)})
        self.session = sessions.open_session(self.sid)['session']
        reply = self.call('draft.get', self.key)
        self.assertTrue(reply['ok'], reply)
        self.assertIsNone(reply['result']['draft'])

    def test_outcome_proof_survives_reopen_and_never_replays(self):
        self.store()
        args = {**self.key, 'data': {'note': 'confirmed'}, 'base_rev': 0}
        self.assertTrue(self.call('editor.save', args, request_id='q10-proof')['ok'])
        sessions.close_session(self.session)
        self.session = sessions.open_session(self.sid)['session']
        before = self.counts()
        reply = self.call('outcome.get', {**self.key, 'request_id': 'q10-proof'})
        self.assertTrue(reply['ok'], reply)
        self.assertEqual(reply['result']['confirmation']['changes'][0]['rev'], 1)
        self.assertEqual(self.counts(), before)
        wrong = self.call('outcome.get', {**self.key, 'editor': 'other', 'request_id': 'q10-proof'})
        self.assertFalse(wrong['ok'], wrong)
        self.assertEqual(wrong['outcome']['status'], 'unknown')

    def test_total_byte_bound_and_profile_isolation(self):
        self.store()
        from living_spaces_core import drafts
        original = self.draft
        self.draft = {'value': {'note': 'x' * (drafts.MAX_ENTRY_BYTES - 100)}}
        for n in range(drafts.MAX_BYTES // (drafts.MAX_ENTRY_BYTES - 100) + 2):
            self.store(id=f'large{n:03}')
        self.assertIsNone(self.call('draft.get', {**self.key, 'id': 'large000'})['result']['draft'])
        newest = f'large{n:03}'
        self.assertEqual(self.call('draft.get', {**self.key, 'id': newest})['result']['draft'], self.draft)
        with db.read() as conn:
            count, size = conn.execute('SELECT count(*),sum(bytes) FROM editor_drafts').fetchone()
        self.assertLessEqual(count, drafts.MAX_COUNT)
        self.assertLessEqual(size, drafts.MAX_BYTES)
        self.draft = original
        self.store()
        with patch.dict(os.environ, {'LIVING_SPACES_DB': str(Path(self.temp.name) / 'profile-two.db')}):
            other = self.create()['id']
            self.assertEqual(other, self.sid)
            other_session = sessions.open_session(other)['session']
            reply = self.call('draft.get', self.key, session=other_session)
            self.assertTrue(reply['ok'], reply)
            self.assertIsNone(reply['result']['draft'])
        self.assertEqual(self.call('draft.get', self.key)['result']['draft'], self.draft)

    def test_after_commit_fault_preserves_proof_and_atomic_draft_clear(self):
        from .test_q03_outcomes import CommitCleanupFault
        self.store()
        original_connect = db.connect
        injected = []
        with patch.object(db, 'connect', side_effect=lambda: CommitCleanupFault(original_connect(), 'commit', injected)):
            reply = self.call('editor.save', {**self.key, 'data': {'note': 'confirmed'}, 'base_rev': 0}, request_id='q10-commit-fault')
        self.assertEqual(injected, ['after real commit'])
        self.assertEqual(reply['outcome']['status'], 'unknown')
        self.assertEqual(records.get(self.sid, 'papers', 'paper')['rev'], 1)
        self.assertIsNone(self.call('draft.get', self.key)['result']['draft'])
        proof = self.call('outcome.get', {**self.key, 'request_id': 'q10-commit-fault'})
        self.assertTrue(proof['ok'], proof)
        self.assertEqual(proof['result']['confirmation']['changes'][0]['rev'], 1)

    def test_inspection_never_reads_or_mutates_private_draft_namespace(self):
        from living_spaces_core import inspection
        self.put()
        self.store()
        before = self.counts()
        conn = inspection._open_snapshot()
        try:
            adapter = inspection.PassiveAdapter(inspection.Snapshot(conn, self.sid, 1))
            self.assertTrue(adapter.call('data.get', {'collection': 'papers', 'id': 'paper'})['ok'])
            for op, extra in [('draft.get', {}), ('draft.put', {'draft': self.draft}), ('draft.delete', {}),
                              ('editor.save', {'data': {'note': 'not saved'}, 'base_rev': 1}),
                              ('outcome.get', {'request_id': 'private-proof'})]:
                reply = adapter.call(op, {**self.key, **extra})
                self.assertFalse(reply['ok'], (op, reply))
                self.assertEqual(reply['error']['code'], 'blocked')
                self.assertNotIn('Q10_PRIVATE_DRAFT', json.dumps(reply))
        finally:
            conn.close()
        self.assertEqual(self.counts(), before)
        self.assertEqual(self.call('draft.get', self.key)['result']['draft'], self.draft)
