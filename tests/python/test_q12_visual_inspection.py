"""Q12 behavior through the real store, parent runner and headless Chromium."""
import base64
import importlib.util
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import zlib
from unittest.mock import patch

from tests.python.test_inspection import InspectionCase, MALICIOUS, needs_browser, table_dump
import living_spaces_core as core
from living_spaces_core import inspection, projects, records
from living_spaces_core.errors import SpacesError

PACKAGE = Path(__file__).resolve().parents[2] / 'src/living-spaces'
spec = importlib.util.spec_from_file_location('q12_plugin', PACKAGE / '__init__.py',
                                            submodule_search_locations=[str(PACKAGE)])
plugin = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = plugin
spec.loader.exec_module(plugin)


def png_pixels(artifact):
    """Decode Chromium's noninterlaced RGB/RGBA PNG, without an image dependency."""
    raw = base64.b64decode(artifact['b64'], validate=True)
    assert raw[:8] == b'\x89PNG\r\n\x1a\n'
    width, height, depth, color, _, _, interlace = struct.unpack('>IIBBBBB', raw[16:29])
    assert (depth, interlace) == (8, 0)
    assert color in (2, 6)
    stride, channels = width * (3 if color == 2 else 4), 3 if color == 2 else 4
    chunks, offset = [], 8
    while offset < len(raw):
        size = struct.unpack('>I', raw[offset:offset + 4])[0]
        if raw[offset + 4:offset + 8] == b'IDAT':
            chunks.append(raw[offset + 8:offset + 8 + size])
        offset += size + 12
    data, previous, pixels = zlib.decompress(b''.join(chunks)), bytearray(stride), []
    for y in range(height):
        start = y * (stride + 1)
        kind, row = data[start], bytearray(data[start + 1:start + 1 + stride])
        for x in range(stride):
            a, b, c = row[x - channels] if x >= channels else 0, previous[x], previous[x - channels] if x >= channels else 0
            if kind == 1:
                predict = a
            elif kind == 2:
                predict = b
            elif kind == 3:
                predict = (a + b) // 2
            elif kind == 4:
                p = a + b - c
                distances = (abs(p - a), abs(p - b), abs(p - c))
                predict = (a, b, c)[distances.index(min(distances))]
            else:
                assert kind == 0
                predict = 0
            row[x] = (row[x] + predict) & 255
        pixels.extend(tuple(row[x:x + 3]) for x in range(0, stride, channels))
        previous = row
    return width, height, pixels


class Q12Case(InspectionCase):
    def visual(self, sid, **options):
        args = {'space': sid, 'rev': 1, 'width': 390, 'height': 300,
                'visual': {'screenshot': True}, **options}
        try:
            return plugin.spaces_inspect(core, args, 'Demo')
        except TypeError as exc:
            self.fail(f'Q12 visual capability is missing: {exc}')
        except SpacesError as exc:
            self.fail(f'Q12 request rejected: {exc.code}: {exc}')

    def assert_no_artifacts(self, report):
        self.assertIsNone(report['screenshot'])
        self.assertTrue(all(route.get('screenshot') is None for route in report['visual']['routes']))
        self.assertNotEqual(report['visual']['status'], 'complete')


class Q12BoundaryTests(Q12Case):
    def test_q12_visual_validation_is_typed_and_requires_explicit_viewport(self):
        sid = self.space('Bounds', '<main>x</main>')
        bad = [{'width': None}, {'height': None}, {'width': 2561}, {'height': 1601},
               {'visual': True}, {'visual': {'max_bytes': 0}}, {'visual': {'max_bytes': 1048577}},
               {'visual': {'screenshot': 1}}, {'visual': {'routes': []}},
               {'visual': {'routes': [{'hash': ''}] * 5}},
               {'visual': {'routes': [{'hash': 'https://example.com'}]}},
               {'visual': {'routes': [{'hash': '#missing'}]}},
               {'visual': {'routes': [{'hash': '', 'landmarks': {'x': 'x' * 257}}]}},
               {'visual': {'routes': [{'hash': '', 'landmarks': {str(i): 'main' for i in range(21)}}]}},
               {'visual': {'path': '../project.png'}}]
        for change in bad:
            args = {'space': sid, 'rev': 1, 'width': 390, 'height': 300, 'visual': {}, **change}
            with self.subTest(change=change), self.assertRaises(SpacesError) as raised:
                plugin.spaces_inspect(core, args, 'Demo')
            self.assertEqual(raised.exception.code, 'invalid')
        # The new option must be recognized even when no browser exists.
        with patch.dict(os.environ, {inspection.BROWSER_ENV: ''}):
            result = self.visual(sid)
        self.assertEqual(result['visual']['error']['code'], 'renderer_unavailable')
        self.assert_no_artifacts(result)

    def test_q12_launch_failure_is_typed_and_removes_only_its_run(self):
        sid = self.space('Launch', '<main>x</main>')
        executable = self.home / 'bad-browser'
        executable.write_bytes(b'\x00\x01 not executable')
        executable.chmod(0o700)
        sentinel = self.home / 'keep.png'
        sentinel.write_bytes(b'keep')
        before = set(Path(tempfile.gettempdir()).glob('ls-inspect-*'))
        with patch.dict(os.environ, {inspection.BROWSER_ENV: str(executable)}):
            report = self.visual(sid)
        self.assertEqual(report['visual']['error']['code'], 'renderer_launch_failed')
        self.assertEqual(report['cleanup'], {'process_exited': True, 'temp_removed': True})
        self.assertEqual(set(Path(tempfile.gettempdir()).glob('ls-inspect-*')), before)
        self.assertEqual(sentinel.read_bytes(), b'keep')
        self.assert_no_artifacts(report)

    def test_q12_missing_entry_reports_failed_visual_coverage(self):
        sid = self.space('Entry', '<main>x</main>')
        projects.write_files(sid, files={'index.html': None, 'other.html': 'x'}, author='agent:demo', summary='drop')
        report = self.visual(sid, rev=2)
        self.assertEqual(report['visual']['error']['code'], 'entry_missing')
        self.assert_no_artifacts(report)


@needs_browser
class Q12RuntimeTests(Q12Case):
    def test_q12_png_dimensions_geometry_and_saved_revision(self):
        sid = self.space('Geometry', '<style>html,body{margin:0;background:rgb(12,34,56)}</style>'
                         '<main id=primary style="width:500px;height:40px">Saved</main>')
        projects.write_files(sid, files={'index.html': '<main>newer</main>'}, author='agent:demo', summary='new')
        before = table_dump(self.db)
        report = self.visual(sid, visual={'screenshot': True, 'routes': [{'hash': '', 'landmarks': {'primary': '#primary'}}]})
        self.assertEqual(report['visual']['status'], 'complete', report)
        route = report['visual']['routes'][0]
        geometry = route['geometry']
        self.assertEqual(geometry['canvas'], {'width': 390, 'height': 300})
        self.assertEqual(geometry['outer']['viewport'], [390, 300])
        self.assertEqual(geometry['landmarks']['primary']['width'], 500)
        self.assertEqual(geometry['landmarks']['primary']['height'], 40)
        self.assertTrue(geometry['overflow']['horizontal'])
        self.assertEqual(geometry['overflow']['scroll_width'], 500)
        artifact = route['screenshot']
        width, height, pixels = png_pixels(artifact)
        self.assertEqual((width, height), (390, 300))
        self.assertEqual(pixels[-1], (12, 34, 56))
        self.assertLessEqual(len(base64.b64decode(artifact['b64'])), 1048576)
        self.assertEqual(artifact['inspection_id'], report['inspection']['id'])
        self.assertEqual((artifact['space'], artifact['rev']), (sid, 1))
        self.assertEqual(report['visual']['artifact_paths'], [])
        self.assertEqual(report['visual']['retention'], 'inline-only; no retained artifacts')
        self.assertEqual(table_dump(self.db), before)
        self.assertFalse(any(x.startswith('no_pixels_captured') for x in report['limitations']))

    def test_q12_routes_measure_without_pixels(self):
        sid = self.space('Routes', '<main id=page style="width:100px;height:50px">Home</main><script type=module>'
                         'addEventListener("hashchange",()=>{document.getElementById("page").id="detail"})</script>')
        report = self.visual(sid, visual={'routes': [{'hash': '', 'landmarks': {'home': '#page'}},
                                                      {'hash': '#detail', 'landmarks': {'detail': '#detail'}}]})
        self.assertEqual(report['visual']['status'], 'complete', report)
        self.assertEqual([r['route'] for r in report['visual']['routes']], ['', '#detail'])
        self.assertEqual(report['visual']['routes'][1]['geometry']['landmarks']['detail']['height'], 50)
        self.assertTrue(all(r['screenshot'] is None for r in report['visual']['routes']))
        self.assertEqual(report['visual']['motion'], 'reduce')

    def test_q12_earlier_route_diagnostics_and_network_survive_later_routes(self):
        # Both routes overflow the bounded diagnostics. The final report must count both, not only the last route.
        sid = self.space('Noisy first route', '<main id=page>Home</main><script type=module>'
                         'for(let i=0;i<55;i++)console.warn("warn "+i)</script>')
        report = self.visual(sid, visual={'routes': [{'hash': '', 'landmarks': {'home': '#page'}},
                                                      {'hash': '#quiet', 'landmarks': {'home': '#page'}}]})
        self.assertEqual(report['visual']['status'], 'complete', report)
        # Each route loads the page afresh and logs 55 distinct warnings: totals must cover both routes.
        self.assertGreaterEqual(report['counts']['warning'], 110, report['counts'])
        self.assertGreaterEqual(report['counts']['dropped'], 60, report['counts'])
        self.assertEqual(len(report['errors']), inspection.MAX_ENTRIES)
        self.assertEqual(len(report['visual']['routes'][0]['errors']), inspection.MAX_ENTRIES)

    def test_q12_route_carry_keeps_network_events_and_limits(self):
        class Browser:
            listeners = []
        first = inspection._Run(Browser(), None, 100, False)
        first.counts['warning'], first.dropped, first.network_blocked = 3, 2, 1
        first.network, first.events, first.limited = ['https://a.invalid/'], [{'kind': 'blocked'}], {'reply': 1}
        first.entries = [{'source': 'console', 'level': 'warning', 'text': 'w'}]
        second = inspection._Run(Browser(), None, 100, False)
        second.carry_from(first)
        self.assertEqual((second.counts['warning'], second.dropped, second.network_blocked), (3, 2, 1))
        self.assertEqual((second.network, second.events, second.limited),
                         (['https://a.invalid/'], [{'kind': 'blocked'}], {'reply': 1}))
        self.assertEqual((second.entries, second.prior_entries), ([], first.entries))

    def test_q12_missing_landmark_and_invalid_selector_fail_routes(self):
        sid = self.space('Missing route', '<main>home</main>')
        for selector, code in [('#absent', 'route_missing'), ('[', 'selector_invalid')]:
            with self.subTest(selector=selector):
                report = self.visual(sid, visual={'screenshot': True, 'routes': [
                    {'hash': ''}, {'hash': '#missing', 'landmarks': {'required': selector}}]})
                self.assertEqual(report['outcome'], 'failed', report)
                self.assertEqual(report['visual']['error']['code'], code)
                self.assert_no_artifacts(report)

    def test_q12_artifact_byte_limit_fails_without_partial_images(self):
        sid = self.space('Bytes', '<main>pixels</main>')
        report = self.visual(sid, visual={'screenshot': True, 'max_bytes': 1})
        self.assertEqual(report['visual']['error']['code'], 'artifact_limit', report)
        self.assertEqual(report['outcome'], 'failed')
        self.assert_no_artifacts(report)
        self.assertEqual(report['cleanup'], {'process_exited': True, 'temp_removed': True})

    def test_q12_secondary_route_timeout_discards_prior_image_and_cleans(self):
        sid = self.space('Hang', '<main id=home>home</main><script type=module>'
                         'addEventListener("hashchange",()=>{while(true){}})</script>')
        before = set(Path(tempfile.gettempdir()).glob('ls-inspect-*'))
        report = self.visual(sid, timeout_s=6, visual={'screenshot': True, 'routes': [
            {'hash': ''}, {'hash': '#hang', 'landmarks': {'home': '#home'}}]})
        self.assertEqual(report['outcome'], 'timed_out', report)
        self.assertEqual(report['visual']['error']['code'], 'route_timeout')
        self.assert_no_artifacts(report)
        self.assertEqual(report['cleanup'], {'process_exited': True, 'temp_removed': True})
        self.assertEqual(set(Path(tempfile.gettempdir()).glob('ls-inspect-*')), before)

    def test_q12_bad_import_is_failed_visual_coverage(self):
        sid = self.space('Import', '<script type=module src=app.js></script>', **{'app.js': "import './missing.js'"})
        report = self.visual(sid)
        self.assertEqual(report['visual']['error']['code'], 'route_failed', report)
        self.assert_no_artifacts(report)

    def test_q12_visual_inspection_preserves_passivity(self):
        sid = self.space('Passive', MALICIOUS)
        records.put(sid, 'notes', 'a', {'t': 'keep'}, actor='agent:demo')
        before = table_dump(self.db)
        report = self.visual(sid)
        self.assertEqual(report['visual']['status'], 'complete', report)
        self.assertEqual(report['blocked'], {'data.put': 1, 'data.delete': 1, 'data.batch': 1,
                                             'refresh': 1, 'bot.request': 1, 'net.fetch': 1})
        self.assertEqual(table_dump(self.db), before)
        self.assertEqual(report['cleanup'], {'process_exited': True, 'temp_removed': True})

    def test_q12_pixels_are_space_scoped_and_have_no_host_chrome(self):
        ids = [self.space(name, f'<style>html,body{{margin:0;background:{color}}}</style>')
               for name, color in [('Red', 'rgb(180,20,30)'), ('Blue', 'rgb(10,30,190)')]]
        records.put(ids[1], 'private', 'secret', {'text': 'other Space secret'}, actor='agent:demo')
        for sid, color in zip(ids, [(180, 20, 30), (10, 30, 190)]):
            report = self.visual(sid)
            self.assertEqual(report['visual']['status'], 'complete', report)
            width, height, pixels = png_pixels(report['visual']['routes'][0]['screenshot'])
            self.assertEqual(set(pixels), {color})
            self.assertEqual((width, height), (390, 300))
            self.assertNotIn('other Space secret', json.dumps(report))

    def test_q12_default_result_has_no_visual_fields_or_artifacts(self):
        sid = self.space('Default', '<main>same</main>')
        report = self.inspect(sid)
        self.assertNotIn('visual', report)
        self.assertEqual(report['outcome'], 'loaded', report)
        self.assertIsNone(report['screenshot'])
