from .test_file_refs import FileRefCase


class CredentialSuffixTests(FileRefCase):
    def test_explicit_dotted_credential_files_are_refused(self):
        for name in ('.gbrain/admin.token', 'service.tokens.json', 'client.secret', 'client.secrets.yaml'):
            path = self.place(self.home, name, b'SYNTHETIC-CREDENTIAL-CONTENT')
            with self.subTest(path=name):
                reply = self.call('spaces_create', name='Credential refusal probe', libraries=[], files={
                    'asset.bin': {'from_path': path}})
                self.assertFalse(reply['ok'], reply)
                self.assertEqual(reply['error']['reason'], 'denied_path')

    def test_public_design_tokens_still_import(self):
        data = b':root { --ink: blue; }'
        path = self.place(self.tmp, 'repo/design/tokens.css', data)
        reply = self.call('spaces_create', name='Public asset control', libraries=[], files={
            'tokens.css': {'from_path': path}})
        self.assertTrue(reply['ok'], reply)
        self.assertEqual(self.read_bytes(reply['result']['space'], 'tokens.css'), data)

    def test_known_ssh_path_remains_refused(self):
        path = self.place(self.home, '.ssh/id_ed25519', b'SYNTHETIC-KEY-CONTENT')
        reply = self.call('spaces_create', name='SSH refusal control', libraries=[], files={
            'asset.bin': {'from_path': path}})
        self.assertFalse(reply['ok'], reply)
        self.assertEqual(reply['error']['reason'], 'denied_path')


class ConventionalCredentialStoreTests(FileRefCase):
    def assert_claude_refusal_is_atomic(self, tool_name, *, alias=False):
        from .test_file_refs import core

        css = b':root { --ink: blue; }'
        public = self.place(self.tmp, 'repo/design/tokens.css', css)
        sid = self.create({'tokens.css': {'from_path': public}, 'keep.txt': 'Keep me'})['space']
        before = (core.list_spaces(), core.get_space(sid), core.list_revisions(sid), core.bundle(sid))
        source = self.place(self.home, '.claude/.credentials.json', b'{"synthetic": "CREDENTIAL-FIXTURE"}')
        if alias:
            link = self.tmp / 'public-asset.json'
            link.symlink_to(source)
            source = str(link)
        files = {
            'index.html': '<p>This change must roll back</p>',
            'new/tokens.css': {'from_path': public},
            'asset.json': {'from_path': source},
        }
        args = {'name': 'Rejected credential import', 'libraries': []}
        if tool_name == 'spaces_write_files':
            args = {'space': sid, 'summary': 'Rejected credential update',
                    'base_rev': before[1]['head_rev']}
            files['keep.txt'] = None
        reply = self.call(tool_name, files=files, **args)
        after = (core.list_spaces(), core.get_space(sid), core.list_revisions(sid), core.bundle(sid))
        with self.subTest(contract='credential refusal'):
            self.assertFalse(reply['ok'], reply)
            self.assertEqual(reply['error']['code'], 'blocked', reply)
            self.assertEqual(reply['error']['reason'], 'denied_path', reply)
        with self.subTest(contract='atomic project and revision state'):
            self.assertEqual(after, before)
            self.assertEqual(self.read_bytes(sid, 'tokens.css'), css)
            self.assertEqual(self.read_bytes(sid, 'keep.txt'), b'Keep me')

    def test_create_refuses_claude_credentials_atomically(self):
        self.assert_claude_refusal_is_atomic('spaces_create')

    def test_create_refuses_claude_credentials_alias_atomically(self):
        self.assert_claude_refusal_is_atomic('spaces_create', alias=True)

    def test_write_refuses_claude_credentials_atomically(self):
        self.assert_claude_refusal_is_atomic('spaces_write_files')

    def test_write_refuses_claude_credentials_alias_atomically(self):
        self.assert_claude_refusal_is_atomic('spaces_write_files', alias=True)

    def test_tokens_css_imports_through_create_and_write(self):
        from .test_file_refs import core

        original = b':root { --ink: blue; }'
        source = self.place(self.tmp, 'repo/design/tokens.css', original)
        sid = self.create({'tokens.css': {'from_path': source}})['space']
        head = core.get_space(sid)['head_rev']
        self.assertEqual(self.read_bytes(sid, 'tokens.css'), original)
        updated = b':root { --ink: green; }'
        source = self.place(self.tmp, 'repo/design/tokens.css', updated)
        self.ok('spaces_write_files', space=sid, summary='Update public design tokens', base_rev=head,
                files={'tokens.css': {'from_path': source}})
        self.assertEqual(core.get_space(sid)['head_rev'], head + 1)
        self.assertEqual(len(core.list_revisions(sid)), 2)
        self.assertEqual(self.read_bytes(sid, 'tokens.css'), updated)
