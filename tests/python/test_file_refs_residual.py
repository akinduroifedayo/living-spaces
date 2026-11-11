import hashlib
import unittest

from . import test_file_refs as stock
from living_spaces_core import file_refs


class ResidualTests(stock.FileRefCase):
    def test_signed_path_provenance(self):
        original = 'https://public.example/download?signature=SYNTHETIC-QUERY'
        redirected = 'https://cdn.example/file/bot123456:SYNTHETIC-PATH-CREDENTIAL/photo.jpg'
        self.responses = [stock.Response(status=302, headers={'Location': redirected}), stock.Response(stock.PNG)]
        sid = self.create({'photo.png': {'from_url': original}})['space']
        summary = stock.core.list_revisions(sid)[0]['summary']
        digest = hashlib.sha256(stock.PNG).hexdigest()
        self.assertNotIn('SYNTHETIC-', summary)
        self.assertIn(digest, summary)
        self.assertEqual(summary, f'Created (photo.png from https://public.example to https://cdn.example sha256:{digest})')
        self.assertEqual(self.read_bytes(sid, 'photo.png'), stock.PNG)

    def test_original_and_same_origin_redirect_paths_are_absent_from_history(self):
        original = 'https://public.example:8443/SYNTHETIC-ORIGINAL/file?key=SYNTHETIC-QUERY#SYNTHETIC-FRAGMENT'
        final = 'https://public.example:8443/SYNTHETIC-REDIRECT/file?key=SYNTHETIC-FINAL#SYNTHETIC-FINAL-FRAGMENT'
        self.responses = [stock.Response(stock.PNG)]
        sid = self.create({'photo.png': {'from_url': original}})['space']
        self.responses = [stock.Response(status=302, headers={'Location': final}), stock.Response(stock.PNG)]
        self.ok('spaces_write_files', space=sid, summary='Update', files={'photo.png': {'from_url': original}})
        digest = hashlib.sha256(stock.PNG).hexdigest()
        revisions = stock.core.list_revisions(sid)
        self.assertEqual(len(revisions), 2)
        self.assertEqual({rev['summary'] for rev in revisions}, {
            f'{action} (photo.png from https://public.example:8443 sha256:{digest})'
            for action in ('Created', 'Update')
        })
        self.assertEqual(self.read_bytes(sid, 'photo.png'), stock.PNG)

    def test_public_token_named_asset(self):
        css = b':root { --accent: #e51f4c; }'
        source = self.place(self.home, 'repo/design/tokens.css', css)
        reply = self.call('spaces_create', name='Design tokens', libraries=[], files={
            'index.html': '<link rel="stylesheet" href="tokens.css">', 'tokens.css': {'from_path': source}})
        self.assertTrue(reply['ok'], reply)
        self.assertEqual(self.read_bytes(reply['result']['space'], 'tokens.css'), css)

    def test_known_credential_names_and_aliases_are_blocked(self):
        names = (
            'token', 'tokens.json', '.token', '.tokens.json', 'github_token.txt', 'access-token.json',
            'refresh_token.yaml', 'oauth_tokens.json', 'secret', 'secrets.toml', '.secret', '.secrets.yml',
            'client-secret.json', 'client_secret.json', 'app_secrets.yaml', 'AUTH.JSON',
            '.env', '.env.local', '.env.production', 'server.key', '.aws/credentials',
            '.config/gh/hosts.yml', '.config/gcloud/application_default_credentials.json',
            '.docker/config.json', '.kube/config', '.netrc', '.npmrc',
            'Library/Keychains/login.keychain-db', '.config/chromium/Default/Login Data',
            '.mozilla/firefox/demo/logins.json',
        )
        for index, name in enumerate(names):
            source = self.place(self.home, name, b'SYNTHETIC-CREDENTIAL')
            alias = self.tmp / f'public-{index}.bin'
            alias.symlink_to(source)
            for candidate in (source, str(alias)):
                with self.subTest(name=name, alias=candidate == str(alias)):
                    error = self.refused('blocked', 'spaces_create', name='Credential refusal', libraries=[],
                                         files={'asset.bin': {'from_path': candidate}})
                    self.assertEqual(error['reason'], 'denied_path')
        self.assertEqual(stock.core.list_spaces(), [])

    def test_normal_public_assets_return_exact_bytes(self):
        assets = {
            'theme.css': b':root { --accent: blue; }',
            'token-icons.svg': b'<svg xmlns="http://www.w3.org/2000/svg"/>',
            'tokenizer.js': b'export const tokenize = text => text.split(" ");',
            'secrets-of-design.md': b'Public design notes.',
            'art.png': stock.PNG,
        }
        sid = self.create({name: {'from_path': self.place(self.home, 'repo/assets/' + name, data)}
                           for name, data in assets.items()})['space']
        for name, data in assets.items():
            with self.subTest(name=name):
                self.assertEqual(self.read_bytes(sid, name), data)


class OriginNoteTests(unittest.TestCase):
    def test_userinfo_path_query_and_fragment_are_excluded(self):
        for authority in ('cdn.example:8443', '[2606:4700:4700::1111]:8443'):
            with self.subTest(authority=authority):
                url = f'https://SYNTHETIC-USER:SYNTHETIC-PASSWORD@{authority}/SYNTHETIC-PATH?SYNTHETIC-QUERY#SYNTHETIC-FRAGMENT'
                self.assertEqual(file_refs._url_note(url), f'https://{authority}')
