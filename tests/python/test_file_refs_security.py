import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from . import test_file_refs as stock
from living_spaces_core import file_refs, limits


CREDENTIALS = (
    '.aws/credentials', '.aws/config', '.netrc', '_netrc', '.npmrc',
    '.docker/config.json', '.kube/config', '.gnupg/private-keys-v1.d/demo.keygrip',
    '.git-credentials', '.gitconfig', '.git/config', '.config/git/credentials',
    '.config/gh/hosts.yml', '.config/gcloud/application_default_credentials.json',
    'Library/Keychains/login.keychain-db',
    'Library/Application Support/Google/Chrome/Default/Login Data',
    'Library/Application Support/Firefox/Profiles/demo/logins.json',
    '.mozilla/firefox/demo/key4.db', '.config/chromium/Default/Cookies',
    'Library/Safari/Cookies.db',
)


class CredentialTests(stock.FileRefCase):
    def test_standard_credential_paths_and_aliases_are_blocked(self):
        for root in (self.home, self.hermes, self.tmp):
            for index, name in enumerate(CREDENTIALS):
                source = self.place(root, name, b'SYNTHETIC-CREDENTIAL')
                alias = root / f'alias-{index}.bin'
                alias.symlink_to(source)
                for path in (source, str(alias)):
                    with self.subTest(root=root.name, name=name, alias=path == str(alias)):
                        reply = self.call('spaces_create', name='Credential refusal', libraries=[],
                                          files={'index.html': stock.HTML, 'a.bin': {'from_path': path}})
                        self.assertFalse(reply['ok'], reply)
                        self.assertEqual(reply['error']['code'], 'blocked', reply)
                        self.assertEqual(reply['error']['reason'], 'denied_path', reply)
        self.assertEqual(stock.core.list_spaces(), [])

    def test_original_credential_alias_cannot_point_to_public_bytes(self):
        safe = self.place(self.home, 'public.png')
        source = self.home / '.aws/credentials'
        source.parent.mkdir()
        source.symlink_to(safe)
        self.refused('blocked', 'spaces_create', name='Original path', libraries=[],
                     files={'a.png': {'from_path': str(source)}})

    def test_legitimate_bot_files_are_not_generated_only(self):
        for name in ('Downloads/manual.pdf', 'repo/src/library.mjs', '.config/my-app/theme.css'):
            source = self.place(self.home, name, b'public content')
            result = self.create({'a.bin': {'from_path': source}})
            self.assertEqual(self.read_bytes(result['space'], 'a.bin'), b'public content')

    def test_original_outside_alias_to_allowed_file_is_blocked(self):
        source = self.outside / 'alias.png'
        source.symlink_to(self.place(self.home, 'art.png'))
        self.refused('blocked', 'spaces_create', name='Outside alias', libraries=[],
                     files={'a.png': {'from_path': str(source)}})


class DescriptorReadTests(stock.FileRefCase):
    def swap_after_stat(self, source, change):
        original = os.stat
        swaps = []

        def race(path, *args, **kwargs):
            info = original(path, *args, **kwargs)
            if not isinstance(path, int) and Path(path) == source and not swaps:
                swaps.append(str(path))
                change()
            return info

        return patch.object(file_refs.os, 'stat', side_effect=race), swaps

    def test_leaf_symlink_swap_is_refused(self):
        source = Path(self.place(self.home, 'art.png'))
        target = self.place(self.outside, '.env', b'SYNTHETIC-OUTSIDE')

        def change():
            source.unlink()
            source.symlink_to(target)

        seam, swaps = self.swap_after_stat(source, change)
        with seam:
            self.refused('invalid', 'spaces_create', name='Leaf swap', libraries=[],
                         files={'a.png': {'from_path': str(source)}})
        self.assertEqual(len(swaps), 1)
        self.assertEqual(stock.core.list_spaces(), [])

    def test_ancestor_symlink_swap_is_refused(self):
        source = Path(self.place(self.home, 'assets/art.png'))
        self.place(self.outside, 'art.png', b'SYNTHETIC-OUTSIDE')

        def change():
            source.parent.rename(self.home / 'original-assets')
            source.parent.symlink_to(self.outside, target_is_directory=True)

        seam, swaps = self.swap_after_stat(source, change)
        with seam:
            self.refused('invalid', 'spaces_create', name='Ancestor swap', libraries=[],
                         files={'a.png': {'from_path': str(source)}})
        self.assertEqual(len(swaps), 1)
        self.assertEqual(stock.core.list_spaces(), [])

    def test_regular_leaf_replacement_is_refused(self):
        source = Path(self.place(self.home, 'art.png'))
        replacement = Path(self.place(self.home, 'replacement.png', b'other regular bytes'))
        seam, swaps = self.swap_after_stat(source, lambda: replacement.replace(source))
        with seam:
            self.refused('invalid', 'spaces_create', name='Regular swap', libraries=[],
                         files={'a.png': {'from_path': str(source)}})
        self.assertEqual(len(swaps), 1)

    def test_size_growth_after_stat_is_refused(self):
        source = Path(self.place(self.home, 'art.png', b'initial'))
        seam, swaps = self.swap_after_stat(source, lambda: source.write_bytes(b'grown after validation'))
        with seam:
            self.refused('invalid', 'spaces_create', name='Growth', libraries=[],
                         files={'a.png': {'from_path': str(source)}})
        self.assertEqual(len(swaps), 1)

    def test_fifo_swap_returns_without_blocking(self):
        command = [sys.executable, '-B', '-m', 'tests.python.test_file_refs_security', '--fifo-child']
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=3)
        except subprocess.TimeoutExpired as exc:
            self.fail(f'FIFO blocked after substitution, child killed and waited: {exc.stdout!r}')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('FIFO_INSTALLED', result.stdout)
        self.assertIn('REFUSED', result.stdout)

    def test_secure_open_capability_absence_fails_closed(self):
        source = self.place(self.home, 'art.png')
        with patch.object(file_refs, '_HAS_SECURE_OPEN', False, create=True):
            self.refused('blocked', 'spaces_create', name='Unsupported platform', libraries=[],
                         files={'a.png': {'from_path': source}})

    def test_opened_descriptors_close_on_success_and_refusal(self):
        source = self.place(self.home, 'art.png')
        original = os.open
        descriptors = []

        def record(*args, **kwargs):
            fd = original(*args, **kwargs)
            descriptors.append(fd)
            return fd

        for failing in (False, True):
            descriptors.clear()
            with patch.object(file_refs.os, 'open', side_effect=record):
                if failing:
                    with patch.object(file_refs.os, 'read', side_effect=OSError('synthetic read failure')):
                        try:
                            file_refs.read_path(source)
                        except stock.core.SpacesError:
                            pass
                else:
                    self.assertEqual(file_refs.read_path(source), stock.PNG)
            for fd in descriptors:
                with self.assertRaises(OSError):
                    os.fstat(fd)

    def test_static_fifo_and_directory_are_refused(self):
        fifo = self.home / 'pipe.bin'
        os.mkfifo(fifo)
        for source in (fifo, self.home):
            with self.subTest(source=source.name):
                self.refused('invalid', 'spaces_create', name='Nonregular', libraries=[],
                             files={'a.bin': {'from_path': str(source)}})


class ProvenanceTests(stock.FileRefCase):
    def test_signed_original_and_redirect_urls_are_redacted_in_history(self):
        original = 'https://public.example/font?key=SYNTHETIC-ORIGINAL#SYNTHETIC-FRAGMENT'
        redirected = 'https://cdn.example/font.woff2?X-Amz-Signature=SYNTHETIC-REDIRECT#SYNTHETIC-FINAL'
        self.responses = [stock.Response(status=302, headers={'Location': redirected}), stock.Response(b'font bytes')]
        sid = self.create({'font.woff2': {'from_url': original}})['space']
        summary = stock.core.list_revisions(sid)[0]['summary']
        self.assertIn('https://cdn.example/font.woff2', summary)
        self.assertIn(hashlib.sha256(b'font bytes').hexdigest(), summary)
        self.assertNotIn('SYNTHETIC-', summary)
        self.assertNotIn('?', summary)
        self.assertNotIn('#', summary)

    def test_signed_url_error_does_not_echo_query_or_fragment(self):
        self.responses = [stock.Response(status=404)]
        reply = self.call('spaces_create', name='Download error', libraries=[], files={
            'font.woff2': {'from_url': 'https://public.example/font?key=SYNTHETIC-QUERY#SYNTHETIC-FRAGMENT'}})
        self.assertFalse(reply['ok'], reply)
        self.assertNotIn('SYNTHETIC-', json.dumps(reply))
        self.assertEqual(stock.core.list_spaces(), [])

    def test_provenance_is_bounded_and_keeps_hash(self):
        self.responses = [stock.Response(b'font')]
        sid = self.create({'font.woff2': {'from_url': 'https://public.example/' + 'a' * 20000}})['space']
        summary = stock.core.list_revisions(sid)[0]['summary']
        self.assertLessEqual(len(summary), 1400)
        self.assertIn(hashlib.sha256(b'font').hexdigest(), summary)


class ExpansionBudgetTests(stock.FileRefCase):
    def test_invalid_destination_is_rejected_before_any_source_read(self):
        source = self.place(self.home, 'art.png')
        with patch.object(file_refs, 'read_path', wraps=file_refs.read_path) as reads:
            self.refused('invalid', 'spaces_create', name='Bad destination', libraries=[],
                         files={'a.png': {'from_path': source}, '../escape.png': {'from_path': source}})
        self.assertEqual(reads.call_count, 0)
        self.assertEqual(stock.core.list_spaces(), [])

    def test_count_is_rejected_before_any_source_read(self):
        source = self.place(self.home, 'art.png')
        with patch.object(file_refs, 'read_path', wraps=file_refs.read_path) as reads:
            self.refused('limit', 'spaces_create', name='Too many files', libraries=[],
                         files={f'{i}.png': {'from_path': source} for i in range(limits.PROJECT_FILES + 1)})
        self.assertEqual(reads.call_count, 0)

    def test_accumulated_decoded_bytes_stop_later_reads(self):
        source = self.place(self.home, 'art.png', b'x' * 100)
        with patch.object(limits, 'PROJECT_BYTES', 250):
            with patch.object(file_refs, 'read_path', wraps=file_refs.read_path) as reads:
                self.refused('limit', 'spaces_create', name='Budget', libraries=[],
                             files={f'{i}.bin': {'from_path': source} for i in range(8)})
        self.assertLessEqual(reads.call_count, 3)
        self.assertEqual(stock.core.list_spaces(), [])

    def test_retained_existing_bytes_reduce_expansion_budget(self):
        sid = self.create({'old.bin': {'b64': base64.b64encode(b'o' * 100).decode()}})['space']
        source = self.place(self.home, 'art.png', b'x' * 100)
        with patch.object(limits, 'PROJECT_BYTES', len(stock.HTML.encode()) + 250):
            with patch.object(file_refs, 'read_path', wraps=file_refs.read_path) as reads:
                self.refused('limit', 'spaces_write_files', space=sid, summary='No change',
                             files={f'{i}.bin': {'from_path': source} for i in range(8)})
        self.assertLessEqual(reads.call_count, 2)
        self.assertEqual(stock.core.get_space(sid)['head_rev'], 1)

    def test_replacements_and_deletions_use_final_state_budget(self):
        sid = self.create({'old.bin': {'b64': base64.b64encode(b'o' * 100).decode()},
                           'delete.bin': {'b64': base64.b64encode(b'd' * 100).decode()}})['space']
        source = self.place(self.home, 'art.bin', b'x' * 150)
        with patch.object(limits, 'PROJECT_BYTES', len(stock.HTML.encode()) + 160):
            self.ok('spaces_write_files', space=sid, summary='Replace and delete', files={
                'old.bin': {'from_path': source}, 'delete.bin': None})
        self.assertEqual(self.read_bytes(sid, 'old.bin'), b'x' * 150)
        self.assertNotIn('delete.bin', {f['path'] for f in stock.core.list_files(sid)})

    def test_final_count_includes_existing_files_before_expansion(self):
        sid = self.create({'old.bin': 'old'})['space']
        source = self.place(self.home, 'art.png')
        with patch.object(limits, 'PROJECT_FILES', 2):
            with patch.object(file_refs, 'read_path', wraps=file_refs.read_path) as reads:
                self.refused('limit', 'spaces_write_files', space=sid, summary='Count',
                             files={'new.png': {'from_path': source}})
        self.assertEqual(reads.call_count, 0)

    def test_final_count_allows_delete_and_add_at_limit(self):
        sid = self.create({'old.bin': 'old'})['space']
        with patch.object(limits, 'PROJECT_FILES', 2):
            self.ok('spaces_write_files', space=sid, summary='Replace count',
                    files={'old.bin': None, 'new.png': {'from_path': self.place(self.home, 'art.png')}})

    def test_url_reader_receives_remaining_budget(self):
        self.responses = [stock.Response(b'a' * 100), stock.Response(b'b' * 100), stock.Response(b'c' * 100)]
        with patch.object(limits, 'PROJECT_BYTES', 150):
            with patch.object(stock.net, 'fetch_for_agent', wraps=stock.net.fetch_for_agent) as fetches:
                self.refused('limit', 'spaces_create', name='Download budget', libraries=[], files={
                    f'{i}.bin': {'from_url': f'https://public.example/{i}.bin'} for i in range(3)})
        self.assertEqual(fetches.call_count, 2)
        self.assertEqual(fetches.call_args.kwargs['max_bytes'], 50)

    def test_inline_base64_is_rejected_before_large_decode(self):
        encoded = base64.b64encode(b'x' * 100).decode()
        with patch.object(limits, 'PROJECT_BYTES', 50):
            with patch.object(stock.plugin.base64, 'b64decode', wraps=base64.b64decode) as decodes:
                self.refused('limit', 'spaces_create', name='Inline budget', libraries=[],
                             files={'a.bin': {'b64': encoded}})
        self.assertEqual(decodes.call_count, 0)

    def test_library_count_is_reserved_before_reference_reads(self):
        source = self.place(self.home, 'art.png')
        with patch.object(limits, 'PROJECT_FILES', 1):
            with patch.object(file_refs, 'read_path', wraps=file_refs.read_path) as reads:
                self.refused('limit', 'spaces_create', name='Library count', libraries=['preact'],
                             files={'a.png': {'from_path': source}})
        self.assertEqual(reads.call_count, 0)


def fifo_child():
    case = DescriptorReadTests()
    case.setUp()
    source = Path(case.place(case.home, 'safe.png'))

    def change():
        source.unlink()
        os.mkfifo(source)
        print('FIFO_INSTALLED', flush=True)

    seam, swaps = case.swap_after_stat(source, change)
    try:
        with seam:
            file_refs.read_path(str(source))
    except stock.core.SpacesError:
        print('REFUSED', flush=True)
    finally:
        case.doCleanups()


if __name__ == '__main__':
    if '--fifo-child' in sys.argv:
        fifo_child()
    else:
        unittest.main()
