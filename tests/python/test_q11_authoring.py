import json
import unittest

from tests.python.test_core_store import CoreCase, projects, records, db, limits
from tests.python.test_c_tools import ToolCase, core, PNG, descriptor, ROOT


class BatchEditTests(CoreCase):
    def edit(self, edits, base_rev=None):
        self.assertTrue(callable(getattr(projects, 'edit_files', None)), 'atomic edit_files capability is missing')
        return projects.edit_files(self.sid, edits=edits,
                                   base_rev=projects.get_space(self.sid)['head_rev'] if base_rev is None else base_rev,
                                   author='agent:demo', summary='Coherent change')

    def snapshot(self):
        with db.read() as conn:
            blobs = conn.execute('SELECT count(*) FROM blobs').fetchone()[0]
        return projects.bundle(self.sid), self.counts(), blobs

    def reject(self, edits, code='invalid', index=1, base_rev=None):
        before = self.snapshot()
        with self.assertRaises(core.SpacesError) as caught:
            self.edit(edits, base_rev)
        error = caught.exception.to_dict()
        self.assertEqual(error['code'], code)
        self.assertEqual(error['edit_index'], index)
        self.assertEqual(error['path'], edits[index]['path'])
        self.assertEqual(self.snapshot(), before)
        return error

    def test_atomic_success_one_revision_preserves_records_and_history(self):
        self.write({'app.js': 'export const title = "Before";var extra = 1;'})
        self.put()
        record = records.get(self.sid, 'papers', 'paper')
        result = self.edit([{'path': 'index.html', 'old': 'Public demo', 'new': 'After'},
                            {'path': 'app.js', 'old': 'Before', 'new': 'After'},
                            {'path': 'app.js', 'old': 'var extra = 1;', 'new': ''}])
        self.assertEqual((result['rev'], result['parent_rev']), (3, 2))
        self.assertEqual([r['rev'] for r in projects.list_revisions(self.sid)], [3, 2, 1])
        self.assertEqual(projects.read_file(self.sid, 'index.html')['text'], '<h1>After</h1>')
        self.assertEqual(projects.read_file(self.sid, 'app.js')['text'], 'export const title = "After";')
        self.assertIn('Before', projects.read_file(self.sid, 'app.js', rev=2)['text'])
        self.assertEqual(records.get(self.sid, 'papers', 'paper'), record)

    def test_stale_head_is_rejected_before_edits(self):
        self.write({'index.html': 'Newer'})
        self.reject([{'path': 'index.html', 'old': 'Public demo', 'new': 'Lost'}],
                    code='conflict', index=0, base_rev=1)

    def test_ambiguity_created_by_earlier_edit_rolls_back(self):
        self.reject([{'path': 'index.html', 'old': 'Public demo', 'new': 'repeat repeat'},
                     {'path': 'index.html', 'old': 'repeat', 'new': 'once'}])

    def test_initial_ambiguity_and_missing_match_roll_back(self):
        self.write({'other.txt': 'repeat repeat'})
        for old in ('repeat', 'absent'):
            with self.subTest(old=old):
                self.reject([{'path': 'index.html', 'old': 'Public demo', 'new': 'After'},
                             {'path': 'other.txt', 'old': old, 'new': 'once'}])

    def test_binary_edit_rolls_back(self):
        self.write({'image.png': PNG})
        self.reject([{'path': 'index.html', 'old': 'Public demo', 'new': 'After'},
                     {'path': 'image.png', 'old': 'PNG', 'new': 'bad'}])

    def test_preexisting_warning_does_not_block_or_misattribute_a_batch(self):
        # int-opus-01 Q11 P2: only diagnostics the batch introduces are blocking.
        self.write({'legacy.js': 'import "./gone.js";'})
        result = self.edit([{'path': 'index.html', 'old': 'Public demo', 'new': 'After'}])
        self.assertEqual(result['rev'], projects.get_space(self.sid)['head_rev'])
        self.assertTrue(any(d['path'] == 'legacy.js' for d in result['diagnostics']), result['diagnostics'])
        error = self.reject([{'path': 'index.html', 'old': 'After', 'new': 'Again'},
                             {'path': 'index.html', 'old': 'Again', 'new': '<img src="missing.png">'}])
        self.assertEqual({d['path'] for d in error['diagnostics']}, {'index.html'})

    def test_invalid_import_and_asset_reject_final_candidate(self):
        for replacement in ('<script type="module">import "./missing.js";</script>',
                            '<img src="missing.png">'):
            with self.subTest(replacement=replacement):
                error = self.reject([{'path': 'index.html', 'old': 'Public demo', 'new': 'After'},
                                     {'path': 'index.html', 'old': 'After', 'new': replacement}])
                self.assertTrue(error['diagnostics'])

    def test_unchanged_importer_is_validated_and_names_manifest_edit(self):
        self.write({'app.js': 'import "dep";', 'dep.js': 'export const value = 1;'},
                   manifest={'imports': {'dep': 'dep.js'}})
        error = self.reject([{'path': 'dep.js', 'old': '1', 'new': '2'},
                             {'path': 'space.json', 'old': '"dep.js"', 'new': '"absent.js"'}])
        self.assertIn('import.alias_target_missing', [d['code'] for d in error['diagnostics']])
        self.assertEqual(projects.read_file(self.sid, 'app.js')['text'], 'import "dep";')

    def test_only_final_candidate_is_validated(self):
        result = self.edit([{'path': 'index.html', 'old': 'Public demo', 'new': '<img src="missing.png">'},
                            {'path': 'index.html', 'old': '<img src="missing.png">', 'new': 'Ready'}])
        self.assertEqual(result['diagnostics'], [])
        self.assertEqual(result['rev'], 2)

    def test_invalid_manifest_names_failing_edit(self):
        self.reject([{'path': 'index.html', 'old': 'Public demo', 'new': 'After'},
                     {'path': 'space.json', 'old': '"schema":1', 'new': '"schema":2'}])

    def test_invalid_path_missing_file_and_malformed_edit_are_atomic(self):
        for last in ({'path': '../escape', 'old': 'x', 'new': 'y'},
                     {'path': 'missing.js', 'old': 'x', 'new': 'y'},
                     {'path': 'index.html', 'old': '', 'new': 'y'},
                     {'path': 'index.html', 'old': 'After', 'new': 3}):
            with self.subTest(last=last):
                self.reject([{'path': 'index.html', 'old': 'Public demo', 'new': 'After'}, last],
                            code='not_found' if last['path'] == 'missing.js' else 'invalid')

    def test_failed_migration_rolls_back_entire_batch(self):
        self.put(data={'stat': 'reading', 'status': 'done'})
        manifest = self.manifest_v2([{'op': 'rename_field', 'collection': 'papers', 'from': 'stat', 'to': 'status'}])
        old = projects.read_file(self.sid, 'space.json')['text']
        self.reject([{'path': 'index.html', 'old': 'Public demo', 'new': 'After'},
                     {'path': 'space.json', 'old': old, 'new': json.dumps(manifest)}])

    def test_edit_count_and_project_bytes_are_bounded(self):
        before = self.snapshot()
        self.error('limit', self.edit, [{'path': 'index.html', 'old': 'Public demo', 'new': 'After'}] * 101)
        self.assertEqual(self.snapshot(), before)
        from unittest.mock import patch
        with patch.object(limits, 'FILE_BYTES', 100):
            self.reject([{'path': 'index.html', 'old': 'Public demo', 'new': 'x' * 101}],
                        code='limit', index=0)


class BatchToolTests(ToolCase):
    def require_tool(self, name):
        self.assertIn(name, self.tools, 'public batch tool is missing')

    def test_public_registration_schema_and_single_file_contracts(self):
        self.require_tool('spaces_read_files')
        self.require_tool('spaces_edit_files')
        read = self.tools['spaces_read_files']['schema']['parameters']
        edit = self.tools['spaces_edit_files']['schema']['parameters']
        self.assertEqual(set(read['required']), {'space', 'paths'})
        self.assertEqual(read['properties']['paths']['maxItems'], 20)
        self.assertEqual(set(edit['required']), {'space', 'base_rev', 'edits', 'summary'})
        self.assertEqual(edit['properties']['edits']['maxItems'], 100)
        self.assertEqual(set(edit['properties']['edits']['items']['required']), {'path', 'old', 'new'})
        self.assertEqual(set(self.tools['spaces_edit_file']['schema']['parameters']['properties']),
                         {'space', 'path', 'old', 'new', 'summary'})
        sid = self.create()['space']
        old = self.ok('spaces_read_file', space=sid, path='index.html')
        changed = self.ok('spaces_edit_file', space=sid, path='index.html', old='Assets', new='Changed', summary='Single')
        self.assertEqual(changed['rev'], old['rev'] + 1)

    def test_public_atomic_edit_and_required_base_revision(self):
        self.require_tool('spaces_edit_files')
        sid = self.create()['space']
        edits = [{'path': 'index.html', 'old': 'Assets', 'new': 'Batch'},
                 {'path': 'space.json', 'old': 'Asset Demo', 'new': 'Batch Demo'}]
        self.invalid('spaces_edit_files', space=sid, edits=edits, summary='Missing base')
        self.assertEqual(core.get_space(sid)['head_rev'], 1)
        result = self.ok('spaces_edit_files', space=sid, base_rev=1, edits=edits, summary='Batch')
        self.assertEqual((result['rev'], result['space']), (2, sid))
        self.assertIn('open', result)
        error = self.call('spaces_edit_files', space=sid, base_rev=1, edits=edits, summary='Stale')['error']
        self.assertEqual((error['code'], error['edit_index'], error['path']), ('conflict', 0, 'index.html'))

    def test_bounded_read_has_independent_text_binary_manifest_and_errors(self):
        self.require_tool('spaces_read_files')
        sid = self.create(files={'index.html': 'é', 'image.png': descriptor(PNG)})['space']
        paths = ['index.html', '../escape', 'missing.js', 'image.png', 'space.json', 'index.html']
        result = self.ok('spaces_read_files', space=sid, paths=paths)
        self.assertEqual((result['space'], result['rev']), (sid, 1))
        self.assertEqual([r['path'] for r in result['results']], paths)
        self.assertEqual([r['ok'] for r in result['results']], [True, False, False, True, True, True])
        self.assertEqual(result['results'][1]['error']['code'], 'invalid')
        self.assertEqual(result['results'][2]['error']['code'], 'not_found')
        for i in (0, 3, 4, 5):
            self.assertEqual(result['results'][i]['result'], core.read_file(sid, paths[i]))

    def test_read_bounds_count_utf8_and_base64_and_continue_after_limit(self):
        self.require_tool('spaces_read_files')
        text = 'é' * (128 * 1024)
        binary = b'\xff' * (192 * 1024)
        sid = self.create(files={'index.html': 'small', 'full.txt': text,
                                 'large.txt': text + 'é', 'binary.bin': descriptor(binary)})['space']
        result = self.ok('spaces_read_files', space=sid,
                         paths=['large.txt', 'full.txt', 'binary.bin', 'full.txt', 'full.txt', 'full.txt', 'index.html'])
        self.assertEqual([r['ok'] for r in result['results']], [False, True, True, True, True, False, False])
        self.assertEqual(result['results'][0]['error']['code'], 'limit')
        self.assertEqual(result['results'][5]['error']['code'], 'limit')
        result = self.ok('spaces_read_files', space=sid, paths=['large.txt', 'index.html'])
        self.assertEqual([r['ok'] for r in result['results']], [False, True])
        self.ok('spaces_read_files', space=sid, paths=['index.html'] * 20)
        self.assertEqual(self.call('spaces_read_files', space=sid, paths=['index.html'] * 21)['error']['code'], 'limit')
        for paths in ([], 'index.html', None):
            self.invalid('spaces_read_files', space=sid, paths=paths)

    def test_short_core_routes_recipes_and_retains_authority(self):
        skill = (ROOT / 'src/living-spaces/skills/build-space/SKILL.md').read_text()
        self.assertLess(len(skill.splitlines()), 180, 'core guidance is still monolithic')
        for term in ('spaces_read_files', 'spaces_edit_files', 'base_rev', 'space.net.fetch',
                     'localStorage', 'baseRev', 'native', 'model', 'on demand'):
            self.assertIn(term, skill)
        import re
        links = re.findall(r'\]\((references/[^)]+\.md)\)', skill)
        self.assertGreaterEqual(len(links), 4)
        for link in links:
            self.assertTrue((ROOT / 'src/living-spaces/skills/build-space' / link).is_file(), link)


if __name__ == '__main__':
    unittest.main()
