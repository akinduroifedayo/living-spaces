import os
from pathlib import Path
import shutil
import tempfile
from unittest.mock import patch

from .test_file_refs import FileRefCase, PNG, core
from living_spaces_core import file_refs


CACHE_DIRS = (
    'cache/images', 'cache/documents', 'cache/screenshots', 'cache/vision',
    'cache/video', 'cache/videos', 'cache/generated/images', 'downloads/connectors',
    'images', 'cache/scratch',
)
LEGACY_DIRS = (
    'image_cache', 'document_cache', 'browser_screenshots', 'temp_vision_images',
    'temp_video_files', 'video_cache',
)
HERMES_CREDENTIALS = (
    'mcp-tokens/service/data', 'vault/opaque.bin', 'vault/vault.key',
    'webapp/opaque.bin', 'webapp/session-token',
    'browser-profile/Default/Login Data', 'auth/google_oauth.json', 'auth/other.bin',
    'auth.lock', 'auth.json', 'webhook_subscriptions.json', '.anthropic_oauth.json',
    'bws_cache.json', 'bws_cache.enc.json', 'bws_cache.extra.json', 'op_cache.json',
    'photon-sidecar.json', 'state.db', 'state.db-wal', 'state.db-shm',
    'state.db-journal', 'state.db.backup', 'skills/.hub/entry.md',
    'cache/bws_cache.json', 'cache/op_cache.json', 'runtime/photon-sidecar.json',
)
AI_CREDENTIALS = (
    '.claude/session.bin', '.codex/session.bin', '.cursor/session.bin',
    '.gemini/session.bin', '.aider/session.bin', '.continue/session.bin',
    '.codeium/session.bin', '.openclaw/session.bin', '.pi/session.bin',
    '.qwen/session.bin', '.copilot/session.bin', '.windsurf/session.bin',
    '.config/opencode/session.bin',
    '.local/share/opencode/session.bin',
)


class AllowlistTests(FileRefCase):
    def assert_blocked(self, source):
        with patch.object(file_refs.os, 'open', wraps=os.open) as opens:
            with self.assertRaises(core.SpacesError) as raised:
                file_refs.read_path(str(source))
        self.assertEqual(raised.exception.code, 'blocked')
        opens.assert_not_called()

    def test_exact_supported_cache_and_populated_legacy_dirs_return_bytes(self):
        for directory in (*CACHE_DIRS, *LEGACY_DIRS):
            with self.subTest(directory=directory):
                source = self.place(self.hermes, directory + '/nested/asset.bin', b'authorized bytes')
                self.assertEqual(file_refs.read_path(source), b'authorized bytes')
        source = self.place(self.tmp, 'native-tool-output/library.mjs', b'export default 1;')
        self.assertEqual(file_refs.read_path(source), b'export default 1;')

    def test_populated_legacy_does_not_hide_canonical_files(self):
        canonical = self.place(self.hermes, 'cache/images/canonical.png', b'canonical')
        legacy = self.place(self.hermes, 'image_cache/legacy.png', b'legacy')
        self.assertEqual(file_refs.read_path(canonical), b'canonical')
        self.assertEqual(file_refs.read_path(legacy), b'legacy')

    def test_symlinked_home_keeps_both_supported_path_spellings(self):
        source = self.place(self.hermes, 'cache/images/art.png', b'art')
        link = self.home / 'hermes-link'
        link.symlink_to(self.hermes, target_is_directory=True)
        with patch.dict(os.environ, {'HERMES_HOME': str(link)}):
            self.assertEqual(file_refs.read_path(source), b'art')
            self.assertEqual(file_refs.read_path(str(link / 'cache/images/art.png')), b'art')
            self.assert_blocked(self.place(self.hermes, 'auth/opaque.bin'))

    def test_home_hermes_and_general_cache_are_not_import_roots(self):
        for root, name in (
            (self.home, 'Downloads/manual.pdf'), (self.home, 'repo/app.js'),
            (self.hermes, 'notes.md'), (self.hermes, 'cache/unknown/result.bin'),
            (self.hermes, 'downloads/arbitrary.bin'), (self.hermes, 'cache/generated/other.bin'),
            (self.hermes, 'cache/images-extra/asset.bin'), (self.outside, 'asset.bin'),
        ):
            with self.subTest(root=root, name=name):
                self.assert_blocked(self.place(root, name))

    def test_hermes_credentials_stay_blocked_when_temp_overlaps_each_store(self):
        root = self.hermes
        active = root / 'profiles/active'
        with patch.dict(os.environ, {'HERMES_HOME': str(active)}):
            for base in (active, root, root / 'profiles', root / 'profiles/sibling'):
                for name in HERMES_CREDENTIALS:
                    source = Path(self.place(base, name, b'SYNTHETIC-CREDENTIAL'))
                    with self.subTest(base=base, name=name):
                        with patch.object(tempfile, 'tempdir', str(source.parent)):
                            self.assert_blocked(source)
                        alias = self.tmp / 'asset.bin'
                        alias.symlink_to(source)
                        self.assert_blocked(alias)
                        alias.unlink()
            safe = self.place(active, 'cache/images/public.png')
            self.assertEqual(file_refs.read_path(safe), PNG)

    def test_ai_credential_dirs_stay_blocked_when_temp_is_inside_them(self):
        for name in AI_CREDENTIALS:
            source = Path(self.place(self.home, name, b'SYNTHETIC-CREDENTIAL'))
            with self.subTest(name=name), patch.object(tempfile, 'tempdir', str(source.parent)):
                self.assert_blocked(source)
                alias = self.tmp / 'asset.bin'
                alias.symlink_to(source)
                self.assert_blocked(alias)
                alias.unlink()

    def test_broad_temp_cannot_turn_home_or_hermes_into_an_import_root(self):
        for temp in (self.home, self.hermes, self.hermes / 'cache', self.home.parent):
            with self.subTest(temp=temp), patch.object(tempfile, 'tempdir', str(temp)):
                self.assert_blocked(self.place(self.home, 'ordinary.txt'))
                self.assert_blocked(self.place(self.hermes, 'cache/private.txt'))
                source = self.place(self.hermes, 'cache/images/public.bin', b'public')
                self.assertEqual(file_refs.read_path(source), b'public')

    def test_cache_root_symlinks_do_not_expand_admission_even_inside_temp(self):
        for index, directory in enumerate((*CACHE_DIRS, *LEGACY_DIRS)):
            for target in (self.outside / str(index), self.hermes / 'vault' / str(index)):
                self.place(target, 'asset.bin', b'SYNTHETIC-OUTSIDE')
                root = self.hermes / directory
                root.parent.mkdir(parents=True, exist_ok=True)
                root.symlink_to(target, target_is_directory=True)
                with self.subTest(directory=directory, target=target):
                    with patch.object(tempfile, 'tempdir', str(target)):
                        self.assert_blocked(root / 'asset.bin')
                root.unlink()
                shutil.rmtree(target)

    def test_cache_ancestor_symlink_and_symlinked_temp_cannot_open_credentials(self):
        target = self.outside / 'media'
        source = self.place(target, 'images/art.bin')
        cache = self.hermes / 'cache'
        cache.symlink_to(target, target_is_directory=True)
        with patch.object(tempfile, 'tempdir', str(target)):
            self.assert_blocked(cache / 'images/art.bin')
            self.assertEqual(file_refs.read_path(source), PNG)
        cache.unlink()
        credential = self.place(self.hermes, 'auth/opaque.bin', b'SYNTHETIC-CREDENTIAL')
        temp_link = self.tmp / 'relocated-temp'
        temp_link.symlink_to(Path(credential).parent, target_is_directory=True)
        with patch.object(tempfile, 'tempdir', str(temp_link)):
            self.assert_blocked(temp_link / 'opaque.bin')

    def test_environment_files_are_refused_inside_an_allowed_temp_root(self):
        for name in ('.env', '.env.local', '.env.production', '.envrc'):
            with self.subTest(name=name):
                self.assert_blocked(self.place(self.tmp, name, b'SYNTHETIC-CREDENTIAL'))

    def test_traversal_and_aliases_cannot_bypass_either_path_check(self):
        allowed = self.hermes / 'cache/images'
        allowed.mkdir(parents=True)
        self.place(self.hermes, 'notes.bin')
        outside = self.place(self.outside, 'public.bin')
        alias = allowed / 'alias.bin'
        alias.symlink_to(outside)
        self.assert_blocked(alias)
        safe = self.place(allowed, 'public.bin', b'public')
        outside_alias = self.outside / 'alias.bin'
        outside_alias.symlink_to(safe)
        self.assert_blocked(outside_alias)
        for raw in (
            str(allowed / '../../notes.bin'),
            str(self.outside / '../hermes/cache/images/public.bin'),
        ):
            with self.subTest(raw=raw):
                self.assert_blocked(raw)
        alias.unlink()
        alias.symlink_to(safe)
        self.assertEqual(file_refs.read_path(str(alias)), b'public')

    def test_refused_import_keeps_existing_space_and_revisions_unchanged(self):
        source = self.place(self.tmp, 'app.js', b'export default 1;')
        sid = self.create({'app.js': {'from_path': source}})['space']
        before = core.get_space(sid), core.list_revisions(sid), core.bundle(sid)
        bad = self.place(self.hermes, 'mcp-tokens/provider/opaque.bin', b'SYNTHETIC-CREDENTIAL')
        self.refused('blocked', 'spaces_write_files', space=sid, summary='Must not commit',
                     files={'app.js': {'from_path': source}, 'opaque.bin': {'from_path': bad}})
        self.assertEqual((core.get_space(sid), core.list_revisions(sid), core.bundle(sid)), before)
