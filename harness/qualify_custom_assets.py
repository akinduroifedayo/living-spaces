"""Qualify binary tool input, shelf assets and manifest themes in the isolated Desktop."""
import base64
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from cdp import evaluate, screenshot
from guest_realm import guest
from qualify_net import wait

REPO = Path(__file__).resolve().parents[1]
RUN = Path('/Volumes/Expansion/Development/Build/living-spaces-r1')
HOME = RUN / 'home'
assert not HOME.resolve().is_relative_to(Path.home() / '.hermes')
os.environ.update(HERMES_HOME=str(HOME), LIVING_SPACES_DB=str(HOME / 'plugin-data/living-spaces/spaces.db'))
sys.path.insert(0, str(REPO / 'src/living-spaces'))
spec = importlib.util.spec_from_file_location('assets_plugin', REPO / 'src/living-spaces/__init__.py', submodule_search_locations=[str(REPO / 'src/living-spaces')])
plugin = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = plugin
spec.loader.exec_module(plugin)
core = plugin._core.load_core()
OUT = RUN / 'evidence/custom-assets'
OUT.mkdir(parents=True, exist_ok=True)
report = {'checks': [], 'evidence_class': 'Direct real plugin tool handlers, actual isolated Desktop guest, no model generation', 'commit': subprocess.check_output(['git', '-C', str(REPO), 'rev-parse', 'HEAD'], text=True).strip()}


def check(name, value, expected=True):
    passed = value == expected
    report['checks'].append({'name': name, 'passed': passed, 'observed': value, 'expected': expected})
    print(('PASS ' if passed else 'FAIL ') + name, flush=True)
    if not passed:
        raise AssertionError(report['checks'][-1])


def value(script):
    reply = guest(script)
    assert reply and reply.get('ok'), reply
    return reply['value']


png = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII='
html = '''<!doctype html><html lang="en" data-theme="editorial" onclick="window.bad=true"><head>
<link rel="stylesheet" href="kit/spaces-kit.css"><link rel="stylesheet" href="style.css"></head><body>
<main class="space-shell"><h1>Asset qualification</h1><p id="sample">Inter, an offline shelf font.</p><div id="app"></div><img id="mark" alt="Public test pixel"></main><script type="module" src="main.mjs"></script></body></html>'''
js = '''import {h,render} from 'preact';import htm from 'htm';import {createElement,Sun} from 'lucide';
const html=htm.bind(h);render(html`<p id="htm-result">An htm module rendered this.</p>`,document.getElementById('app'));
document.getElementById('app').append(createElement(Sun));
document.getElementById('mark').src=space.asset('art/mark.png');window.assetsBooted=true;'''
sid = None
try:
    result = plugin.spaces_create(core, {'name': 'Asset Qualification', 'files': {'index.html': html, 'main.mjs': js,
        'style.css': '@font-face{font-family:QualificationInter;src:url("vendor/fonts/inter-latin-400-normal.woff2") format("woff2")} #sample{font-family:QualificationInter} :root{--space-link:rgb(7, 8, 9)}',
        'art/mark.png': {'b64': png, 'mime': 'image/png'}}, 'manifest': {'entry': 'index.html', 'theme': {'preset': 'journal', 'tokens': {'bg': '#112233', 'link': '#ff0000'}}},
        'libraries': ['preact', 'preact/hooks', 'spaces-kit', 'htm', 'lucide', 'font:inter']}, 'Public test')
    sid = result['space']
    check('binary create stores exact PNG bytes', core.read_file(sid, 'art/mark.png')['b64'], png)
    read = plugin.spaces_read_file(core, {'space': sid, 'path': 'art/mark.png'}, 'Public test')
    plugin.spaces_write_files(core, {'space': sid, 'files': {'art/copy.png': {'b64': read['b64']}}, 'summary': 'Round-trip public PNG'}, 'Public test')
    check('binary read then write retains bytes', core.read_file(sid, 'art/copy.png')['b64'], png)
    evaluate(f'location.hash={json.dumps("/spaces?space=" + sid)}')
    def booted():
        try:
            return guest('window.assetsBooted')
        except RuntimeError as exc:
            if 'Cannot find context' not in str(exc):
                raise
            return None
    wait(booted, lambda r: bool(r and r.get('ok') and r.get('value')), seconds=45)
    check('manifest preset wins over html preset', value('document.documentElement.dataset.theme'), 'journal')
    check('vetted root lang copied', value('document.documentElement.lang'), 'en')
    check('html event handler dropped', value('document.documentElement.hasAttribute("onclick")'), False)
    check('manifest token applied on root', value('getComputedStyle(document.documentElement).getPropertyValue("--space-bg").trim()'), '#112233')
    check('app CSS overrides manifest tokens', value('getComputedStyle(document.documentElement).getPropertyValue("--space-link").trim()'), 'rgb(7, 8, 9)')
    check('htm renders through offline import map', value('document.getElementById("htm-result").textContent'), 'An htm module rendered this.')
    check('Lucide creates SVG inside actual frame', value('document.querySelectorAll("#app svg").length'), 1)
    wait(lambda: guest('document.getElementById("mark").naturalWidth'), lambda r: bool(r and r.get('ok') and r.get('value') == 1))
    check('dynamic space.asset PNG decodes in Chromium', value('document.getElementById("mark").naturalHeight'), 1)
    check('asset URLs are frame-local blobs', value('document.getElementById("mark").src.startsWith("blob:null/")'))
    check('WOFF2 loads through guest asset resolver', value('document.fonts.load("16px QualificationInter").then(fonts=>fonts.length)'), 1)
    check('font face is loaded', value('[...document.fonts].find(f=>f.family==="QualificationInter")?.status'), 'loaded')
    screenshot(str(OUT / 'journal.png'))
    report['completed'] = True
finally:
    if sid:
        evaluate('location.hash="/spaces"')
        time.sleep(2)
        core.delete_space(sid, actor='harness-fixture', confirm=sid)
        report['fixture_removed'] = not any(s['id'] == sid for s in core.list_spaces())
    report['passed'] = sum(c['passed'] for c in report['checks'])
    report['total'] = len(report['checks'])
    (OUT / 'custom-assets.json').write_text(json.dumps(report, indent=1))
    print(json.dumps({'passed': report['passed'], 'total': report['total'], 'completed': report.get('completed', False)}), flush=True)
