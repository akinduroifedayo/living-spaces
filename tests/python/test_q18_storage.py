"""Q18 retention against real SQLite fixtures. No native runtime qualification."""
import json
import sqlite3
from pathlib import Path

from .test_core_store import CoreCase, db, grants, limits, logs, projects, records
import living_spaces_core as core


class Q18StorageTests(CoreCase):
    def operation(self, name):
        function = getattr(core, name, None)
        self.assertTrue(callable(function), f"Q18 public operation {name} is missing")
        return function

    def summary(self):
        return self.operation('storage_summary')(self.sid)

    def propose(self, categories=None):
        return self.operation('propose_retention')(self.sid, {
            'categories': categories or ['revisions', 'records', 'logs', 'runs'], 'before': 2**53 - 1})

    def execute(self, proposal, **overrides):
        args = dict(scope=proposal['scope'], proposal_id=proposal['id'],
                    confirm=proposal['confirmation'], actor='user')
        args.update(overrides)
        return self.operation('execute_retention')(self.sid, **args)

    def bytes(self):
        path = db.db_path()
        return {suffix: Path(str(path) + suffix).read_bytes() for suffix in ('', '-wal')
                if Path(str(path) + suffix).exists()}

    def seed_history(self):
        self.write({'index.html': 'Older version'})
        self.write({'index.html': 'Current version'})
        records.upsert_source(self.sid, 'papers', 'plain', {'title': 'é'}, {'id': 'feed'}, actor='feed')
        records.upsert_source(self.sid, 'papers', 'annotated', {'title': 'Keep'}, {}, actor='feed')
        records.put(self.sid, 'papers', 'annotated', {'note': 'My note'}, base_rev=1, actor='user')
        self.put('authored')
        logs.add_logs(self.sid, None, [{'level': 'info', 'msg': 'Older diagnostic'}])

    def run_row(self, rid, status='succeeded', at=1, detail=None):
        with db.write() as conn:
            conn.execute("INSERT INTO runs(id,space,trigger,handler,actor,status,queued_at,ended_at,detail) "
                         "VALUES(?,?,'manual','feed','user',?,?,?,?)",
                         (rid, self.sid, status, at, at if status == 'succeeded' else None,
                          limits.dumps(detail or {})))

    def test_usage_separates_categories_and_q15_detail_without_native_reads(self):
        self.operation('storage_summary')
        self.seed_history()
        self.run_row('old', detail={'sources': [{'id': 'feed', 'ok': True}]})
        self.run_row('recent', at=2, detail={'sources': [{'id': 'feed', 'ok': False}]})
        before = self.bytes()
        summary = self.summary()
        self.assertEqual(self.bytes(), before)
        categories = summary['categories']
        self.assertEqual(categories['revisions']['count'], 3)
        self.assertEqual(categories['records']['count'], 3)
        self.assertEqual(categories['source_entries']['count'], 2)
        self.assertEqual(categories['source_entries']['fields'], 2)
        self.assertEqual(categories['logs']['count'], 1)
        self.assertEqual(categories['runs']['count'], 2)
        self.assertEqual(categories['runs']['source_details'], 2)
        self.assertGreater(categories['runs']['bytes'], len(limits.dumps({'sources': [{'id': 'feed', 'ok': True}]})))
        self.assertGreater(categories['blobs']['bytes'], 0)
        self.assertEqual(summary['native_history'], {'ownership': 'native-owned', 'counted': False, 'deletable': False})
        self.assertEqual(projects.get_space(self.sid)['storage'], summary)

    def test_approaching_caps_warn_before_existing_limit_errors(self):
        self.operation('storage_summary')
        with db.write() as conn:
            conn.executemany("INSERT INTO records(space,collection,id,rev,created_at,updated_at,updated_by) "
                             "VALUES(?,'growth',?,1,1,1,'feed')", ((self.sid, str(i)) for i in range(40000)))
        summary = self.summary()
        cap = next(row for row in summary['limits'] if row['resource'] == 'records')
        self.assertEqual((cap['used'], cap['limit'], cap['approaching']), (40000, limits.RECORDS, True))
        self.assertIn('records', [row['resource'] for row in summary['warnings']])
        self.assertEqual(self.put('still-room')['rev'], 1)
        self.assertEqual(records.query(self.sid, 'growth', limit=1)['total'], 40000)

    def fill_logs(self):
        with db.write() as conn:
            conn.executemany("INSERT INTO logs(space,rev,at,level,msg,attribution) VALUES(?,1,1,'info','Diagnostic','unattributed')",
                             ((self.sid,) for _ in range(limits.LOG_HISTORY)))

    def test_full_rolling_log_history_is_not_a_cap_warning(self):
        self.fill_logs()
        summary = self.summary()
        history = next(row for row in summary['limits'] if row['resource'] == 'log_history')
        self.assertEqual((history['used'], history['limit'], history['approaching']), (limits.LOG_HISTORY, limits.LOG_HISTORY, False))
        self.assertEqual(summary['warnings'], [])
        self.assertEqual(logs.add_logs(self.sid, None, [{'level': 'info', 'msg': 'Still logging'}]), 1)
        self.assertEqual(logs.read_logs(self.sid, limit=1)[0]['msg'], 'Still logging')
        self.assertEqual(len(logs.read_logs(self.sid, limit=3000)), limits.LOG_HISTORY)

    def test_full_rolling_log_history_leaves_record_warnings_visible(self):
        self.fill_logs()
        with db.write() as conn:
            conn.executemany("INSERT INTO records(space,collection,id,rev,created_at,updated_at,updated_by) "
                             "VALUES(?,'growth',?,1,1,1,'feed')", ((self.sid, str(i)) for i in range(limits.RECORDS * 85 // 100)))
        self.assertEqual([row['resource'] for row in self.summary()['warnings']], ['records'])

    def test_dry_run_is_byte_identical_and_excludes_protected_items(self):
        self.operation('propose_retention')
        self.seed_history()
        records.create_recovery_point(self.sid, 'Preserve current')
        with db.write() as conn:
            grants._audit(conn, self.sid, 'user', 'review', None, 'ok', {'revision': 1})
        before = self.bytes()
        proposal = self.propose()
        self.assertEqual(self.bytes(), before)
        self.assertEqual([item['rev'] for item in proposal['remove']['revisions']], [2])
        self.assertEqual([item['id'] for item in proposal['remove']['records']], ['plain'])
        self.assertEqual({item['id'] for item in proposal['protected']['records']}, {'annotated', 'authored'})
        self.assertEqual({item['rev'] for item in proposal['protected']['revisions']}, {1, 3})
        self.assertEqual(proposal, self.propose())

    def test_confirmation_is_exact_and_any_changed_state_refuses_stale_proposal(self):
        self.operation('execute_retention')
        self.seed_history()
        proposal = self.propose()
        before = self.bytes()
        self.error('invalid', self.execute, proposal, confirm=self.sid)
        self.assertEqual(self.bytes(), before)
        self.put('late')
        changed = self.bytes()
        self.error('conflict', self.execute, proposal)
        self.assertEqual(self.bytes(), changed)
        scope = {**proposal['scope'], 'categories': ['logs']}
        self.error('conflict', self.execute, proposal, scope=scope)
        fresh = self.propose(['logs'])
        result = self.execute(fresh)
        self.assertEqual(result['proposal_id'], fresh['id'])
        self.assertEqual(logs.read_logs(self.sid), [])
        self.assertEqual(records.get(self.sid, 'papers', 'late')['data'], {'note': 'Demo note'})

    def test_cleanup_preserves_shared_blobs_revision_numbers_and_audit(self):
        self.operation('execute_retention')
        self.seed_history()
        other = self.create('Shared blob Space')['id']
        projects.write_files(other, files={'index.html': 'Older version'}, author='user', summary='Shared')
        with db.read() as conn:
            audit_before = [dict(row) for row in conn.execute('SELECT * FROM audit WHERE space=?', (self.sid,))]
        proposal = self.propose()
        result = self.execute(proposal)
        self.assertEqual(result['removed']['revisions'], 2)
        self.assertEqual([row['rev'] for row in projects.list_revisions(self.sid)], [3])
        self.assertEqual(self.write({'index.html': 'Next version'})['rev'], 4)
        self.assertEqual(projects.read_file(other, 'index.html')['text'], 'Older version')
        self.assertEqual(records.get(self.sid, 'papers', 'annotated')['data'], {'note': 'My note'})
        self.assertEqual(records.upsert_source(self.sid, 'papers', 'plain', {'title': 'Again'}, {}, actor='feed'), 'added')
        self.assertEqual(records.get(self.sid, 'papers', 'plain')['rev'], 3)
        with db.read() as conn:
            self.assertEqual(conn.execute('PRAGMA foreign_key_check').fetchall(), [])
            missing = conn.execute('SELECT value FROM revisions,json_each(files) EXCEPT SELECT sha FROM blobs').fetchall()
            self.assertEqual(missing, [])
            audit_after = [dict(row) for row in conn.execute('SELECT * FROM audit WHERE space=?', (self.sid,))]
        self.assertEqual(audit_after[:-1], audit_before)
        receipt = json.loads(audit_after[-1]['detail'])
        self.assertEqual((audit_after[-1]['action'], receipt['proposal_id']), ('retention', proposal['id']))
        self.assertEqual(receipt['removed'], result['removed'])
        self.error('conflict', self.execute, proposal)

    def test_interrupted_cleanup_rolls_back_every_category_and_receipt(self):
        self.operation('execute_retention')
        self.seed_history()
        # Synthetic SQLite interruption after prior category deletions, before the receipt.
        with db.write() as conn:
            conn.execute("CREATE TRIGGER interrupt_q18 BEFORE INSERT ON audit WHEN NEW.action='retention' "
                         "BEGIN SELECT RAISE(ABORT,'synthetic interruption'); END")
        proposal = self.propose()
        with db.read() as conn:
            before = tuple(conn.iterdump())
        with self.assertRaises(sqlite3.IntegrityError):
            self.execute(proposal)
        with db.read() as conn:
            self.assertEqual(tuple(conn.iterdump()), before)
        with db.write() as conn:
            conn.execute('DROP TRIGGER interrupt_q18')
        self.assertGreater(self.execute(self.propose())['removed']['logs'], 0)

    def test_pending_runs_protect_dependencies_and_q15_last_good_survives(self):
        self.operation('propose_retention')
        self.seed_history()
        source = lambda ok: {'sources': [{'id': 'feed', 'ok': ok, 'last_attempt_at': 1,
                                         'last_success_at': 1 if ok else None, 'source_as_of': 1}]}
        self.run_row('obsolete', detail=source(True))
        self.run_row('last-good', at=2, detail=source(True))
        self.run_row('last-attempt', status='failed', at=3, detail=source(False))
        self.run_row('pending', status='queued', at=4)
        proposal = self.propose()
        self.assertTrue(all(not values for values in proposal['remove'].values()))
        with db.write() as conn:
            conn.execute("UPDATE runs SET status='canceled' WHERE id='pending'")
        from living_spaces_core import runs
        before = runs.freshness(self.sid, include_upkeep=False)
        proposal = self.propose(['runs'])
        self.assertIn('obsolete', [item['id'] for item in proposal['remove']['runs']])
        self.assertNotIn('last-good', [item['id'] for item in proposal['remove']['runs']])
        self.execute(proposal)
        self.assertEqual(runs.freshness(self.sid, include_upkeep=False), before)

    def test_migration_recovery_and_live_session_revisions_are_protected(self):
        self.operation('propose_retention')
        from living_spaces_core import sessions
        sessions.open_session(self.sid)
        self.write({'index.html': 'Version two'}, manifest=self.manifest_v2([]))
        self.write({'index.html': 'Newest'})
        proposal = self.propose(['revisions'])
        self.assertEqual(proposal['remove']['revisions'], [])
        self.assertEqual({item['rev'] for item in proposal['protected']['revisions']}, {1, 2, 3})

    def test_diagnostic_log_stays_bounded_and_explicit_cleanup_still_works(self):
        # Guest logs are the bounded diagnostic and lifecycle channel, not user data. They keep the existing
        # rolling bound so health reporting never fails at the cap; explicit retention can still clear them.
        for start in range(0, limits.LOG_HISTORY, limits.LOG_ENTRIES):
            logs.add_logs(self.sid, None, [{'level': 'info', 'msg': str(i)} for i in range(start, start + 50)])
        self.assertEqual(logs.add_logs(self.sid, None, [{'level': 'info', 'msg': 'newest'}]), 1)
        kept = logs.read_logs(self.sid, limit=3000)
        self.assertEqual(len(kept), limits.LOG_HISTORY)
        self.assertIn('newest', [entry['msg'] for entry in kept])
        self.assertEqual(self.execute(self.propose(['logs']))['removed']['logs'], limits.BATCH_OPS)

    def test_proposals_list_source_fields_and_run_detail_effects(self):
        self.operation('propose_retention')
        records.upsert_source(self.sid, 'papers', 'old', {'title': 'Old', 'url': 'https://example.org'}, {}, actor='feed')
        self.run_row('obsolete', detail={'sources': [{'id': 'feed', 'ok': True}]})
        self.run_row('latest', at=2, detail={'sources': [{'id': 'feed', 'ok': True}]})
        proposal = self.propose(['records', 'runs'])
        self.assertIn('source_entries', proposal['remove'])
        self.assertEqual([(row['id'], row['fields']) for row in proposal['remove']['source_entries']], [('old', 2)])
        self.assertEqual(proposal['remove']['runs'][0]['source_details'], 1)
        receipt = self.execute(proposal)
        self.assertEqual((receipt['removed']['source_entries'], receipt['removed']['source_fields'], receipt['removed']['source_details']), (1, 2, 1))

    def test_bounded_proposal_does_not_starve_eligible_records_behind_annotations(self):
        self.operation('propose_retention')
        records.batch(self.sid, [{'op': 'put', 'collection': 'papers', 'id': f'a{i:04}', 'data': {'note': 'Keep'}}
                                 for i in range(limits.BATCH_OPS)], actor='user')
        records.upsert_source(self.sid, 'papers', 'z-old', {'title': 'Remove'}, {}, actor='feed')
        proposal = self.propose(['records'])
        self.assertEqual([row['id'] for row in proposal['remove']['records']], ['z-old'])
        self.assertEqual(len(proposal['protected']['records']), limits.BATCH_OPS)
