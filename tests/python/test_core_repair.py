from tests.python.test_core_store import CoreCase
from living_spaces_core import db, grants


class UpkeepLinkMigrationTests(CoreCase):
    def test_opening_a_legacy_database_links_schedules_and_drops_refresh_grants(self):
        with db.write() as conn:
            conn.execute("CREATE TABLE schedules(space TEXT PRIMARY KEY, status TEXT, cadence TEXT, timezone TEXT, cron_job_id TEXT)")
            conn.execute("INSERT INTO schedules VALUES(?,'paused','0 7 * * *','UTC','demo-job')", (self.sid,))
            conn.execute("INSERT INTO grants(space,capability,status) VALUES(?,'refresh','granted')", (self.sid,))
        for _ in range(2):
            db._initialized.discard(str(db.db_path()))
            with db.read() as conn:
                self.assertEqual([tuple(row) for row in conn.execute("SELECT space,cron_job_id,kind FROM upkeep_links")],
                                 [(self.sid, "demo-job", "feed")])
                self.assertIsNone(conn.execute("SELECT 1 FROM sqlite_master WHERE name='schedules'").fetchone())
        self.assertNotIn("refresh", [row["capability"] for row in grants.list_grants(self.sid)])
        self.error("invalid", grants.request, self.sid, "refresh", scope={}, purpose="", actor="agent:demo")
        self.error("not_found", grants.decide, self.sid, "refresh", "grant")
