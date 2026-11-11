import asyncio
import importlib.util
import json
from pathlib import Path

from tests.python.test_core_store import CoreCase
from living_spaces_core import grants


class ConsentBindingTests(CoreCase):
    def request(self, hosts):
        return grants.request(self.sid, 'refresh', scope={'hosts': hosts}, purpose='Read public feeds', actor='agent:demo')

    def test_changed_request_conflicts_without_granting(self):
        displayed = self.request(['example.com'])
        current = self.request(['unreviewed.example'])
        before = grants.audit_log(self.sid)
        error = self.error('conflict', grants.decide, self.sid, 'refresh', 'grant',
                           requested_scope=displayed['requested_scope'])
        self.assertEqual(error['current'], current)
        self.assertEqual(grants.audit_log(self.sid), before)
        self.assertEqual(next(g for g in grants.list_grants(self.sid) if g['capability'] == 'refresh'), current)

    def test_matching_display_allows_narrower_scope_but_never_wider(self):
        displayed = self.request(['example.com', 'second.example'])['requested_scope']
        result = grants.decide(self.sid, 'refresh', 'grant', requested_scope=displayed,
                               scope={'hosts': ['example.com']})
        self.assertEqual(result['scope'], {'hosts': ['example.com']})
        self.error('invalid', grants.decide, self.sid, 'refresh', 'grant', requested_scope=displayed,
                   scope={'hosts': ['unreviewed.example']})

    def test_route_binds_displayed_scope_and_requires_it_on_approval(self):
        path = Path(__file__).resolve().parents[2] / 'src/living-spaces/dashboard/plugin_api.py'
        spec = importlib.util.spec_from_file_location('repair_api', path)
        api = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(api)
        import living_spaces_core
        api.load_core = lambda: living_spaces_core
        displayed = self.request(['example.com'])['requested_scope']
        self.request(['unreviewed.example'])
        response = asyncio.run(api.grant_decide(self.sid, 'refresh', {'decision': 'grant', 'requested_scope': displayed}))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(json.loads(response.body)['error']['current']['requested_scope'], {'hosts': ['unreviewed.example']})
        response = asyncio.run(api.grant_decide(self.sid, 'refresh', {'decision': 'grant'}))
        self.assertEqual(response.status_code, 400)
        current = {'hosts': ['unreviewed.example']}
        response = asyncio.run(api.grant_decide(self.sid, 'refresh', {'decision': 'grant', 'requested_scope': current}))
        self.assertEqual(response['scope'], current)


class ScheduleReasonTests(CoreCase):
    def test_fresh_schema_has_nullable_reason(self):
        import sqlite3
        from living_spaces_core import db
        with sqlite3.connect(':memory:') as conn:
            conn.executescript(db.DDL)
            self.assertEqual(conn.execute('SELECT reason FROM schedules').fetchall(), [])
            column = next(row for row in conn.execute('PRAGMA table_info(schedules)') if row[1] == 'reason')
            self.assertEqual(column[2:4], ('TEXT', 0))

    def test_existing_schema_is_migrated_once_and_preserves_schedule(self):
        from living_spaces_core import db
        with db.write() as conn:
            if 'reason' in {row['name'] for row in conn.execute('PRAGMA table_info(schedules)')}:
                conn.execute('ALTER TABLE schedules DROP COLUMN reason')
            conn.execute("INSERT INTO schedules(space,status,cadence,timezone,purpose,cron_job_id) VALUES(?,'paused','0 7 * * *','UTC','Public demo','demo-job')", (self.sid,))
        db._initialized.discard(str(db.db_path()))
        with db.write() as conn:
            row = dict(conn.execute('SELECT * FROM schedules WHERE space=?', (self.sid,)).fetchone())
            self.assertIn('reason', row)
            self.assertIsNone(row['reason'])
            self.assertEqual((row['status'], row['cron_job_id']), ('paused', 'demo-job'))
            conn.execute("UPDATE schedules SET reason='Demo reason' WHERE space=?", (self.sid,))
        db._initialized.discard(str(db.db_path()))
        with db.read() as conn:
            self.assertEqual(conn.execute('SELECT reason FROM schedules WHERE space=?', (self.sid,)).fetchone()[0], 'Demo reason')
            self.assertEqual(sum(row['name'] == 'reason' for row in conn.execute('PRAGMA table_info(schedules)')), 1)
