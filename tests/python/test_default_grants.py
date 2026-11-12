import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/living-spaces'))
from living_spaces_core import db, grants, migrations, projects


class DefaultGrantAttributionTests(unittest.TestCase):
    def setUp(self):
        work = ROOT / '.run'
        work.mkdir(exist_ok=True)
        home = tempfile.TemporaryDirectory(dir=work)
        self.addCleanup(home.cleanup)
        env = patch.dict(os.environ, HERMES_HOME=home.name,
                         LIVING_SPACES_DB=str(Path(home.name) / 'spaces.db'))
        env.start()
        self.addCleanup(env.stop)
        summary = patch.object(projects.upkeep, 'summary', return_value=None)
        summary.start()
        self.addCleanup(summary.stop)
        self.sid = projects.create_space('Default grants', owner='test', author='agent:test')['id']

    def test_create_grants_and_audit_attribute_defaults_to_default(self):
        self.assertEqual({g['decided_by'] for g in grants.list_grants(self.sid)}, {'default'})
        decisions = [a for a in grants.audit_log(self.sid) if a['detail'].get('default_on_create')]
        self.assertEqual(len(decisions), 3)
        self.assertEqual({a['actor'] for a in decisions}, {'default'})

    def test_migration_does_not_impersonate_user(self):
        with db.write() as conn:
            conn.execute("DELETE FROM grants WHERE space=? AND capability='net'", (self.sid,))
            migrations.grant_internet_access(conn)
        net = next(g for g in grants.list_grants(self.sid) if g['capability'] == 'net')
        self.assertEqual(net['decided_by'], 'default')
        audit = next(a for a in grants.audit_log(self.sid) if a['detail'].get('default_on_migration'))
        self.assertEqual(audit['actor'], 'default')

    def test_explicit_user_decision_remains_user(self):
        grants.decide(self.sid, 'net', 'revoke', actor='user')
        net = next(g for g in grants.list_grants(self.sid) if g['capability'] == 'net')
        self.assertEqual((net['decided_by'], net['status']), ('user', 'revoked'))
