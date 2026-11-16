import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "src/living-spaces"
WEATHER = PACKAGE / "skills/build-space/references/weather-window"
INDEX = '<!doctype html><main id="app"></main><script type="module" src="./app.js"></script>'


def codes(result, path=None):
    return [d["code"] for d in result["diagnostics"] if path is None or d["path"] == path]


def network(result):
    return [d for d in result["diagnostics"] if d["code"].startswith("net.")]


class ProjectDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".run").mkdir(exist_ok=True)
        home = tempfile.TemporaryDirectory(dir=ROOT / ".run")
        self.addCleanup(home.cleanup)
        env = patch.dict(os.environ, {"HERMES_HOME": home.name, "LIVING_SPACES_DB": str(Path(home.name) / "spaces.db")})
        env.start()
        self.addCleanup(env.stop)
        spec = importlib.util.spec_from_file_location("diagnostics_tools", PACKAGE / "__init__.py",
                                                      submodule_search_locations=[str(PACKAGE)])
        assert spec is not None and spec.loader is not None
        self.tools = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = self.tools
        spec.loader.exec_module(self.tools)
        self.core = self.tools._core.load_core()

    def create(self, files, name="Diagnostics Demo", **extra):
        return self.tools.spaces_create(self.core, {"name": name, "files": files, "libraries": [], **extra}, "Demo")

    def write(self, sid, files, summary="Change"):
        return self.tools.spaces_write_files(self.core, {"space": sid, "files": files, "summary": summary}, "Demo")

    def edit(self, sid, path, old, new):
        return self.tools.spaces_edit_file(self.core, {"space": sid, "path": path, "old": old, "new": new,
                                                       "summary": "Edit"}, "Demo")

    def test_mediated_fetch_is_not_a_network_warning_on_create_and_edit(self):
        app = ("const response = await space.net.fetch('https://api.open-meteo.com/v1/forecast', {as: 'json'});\n"
               "const again = await window.space.net.fetch(url, {as: 'json'});\n"
               "const net = window.space.net; await net.fetch(url);\n")
        created = self.create({"index.html": INDEX, "app.js": app})
        self.assertEqual(network(created), [], created["warnings"])
        edited = self.edit(created["space"], "app.js", "{as: 'json'});\nconst again", "{as: 'text'});\nconst again")
        self.assertEqual(network(edited), [], edited["warnings"])

    def test_inert_url_text_is_not_a_network_warning(self):
        app = ("const source = 'https://open-meteo.com/';\n"
               "// fetch('https://example.org') is described here, not called\n"
               "/* new WebSocket('wss://example.org') */\n"
               "const label = `Data from https://example.org at ${new Date().getFullYear()}`;\n"
               "const pattern = /fetch\\(/;\n"
               "const help = \"call fetch(url) in a standalone page\";\n"
               "client.fetch(source);\n")
        html = ('<!doctype html><main><a href="https://open-meteo.com/" target="_blank">Open-Meteo</a>'
                '<p>See https://example.org for terms.</p><!-- <script src="https://cdn.example/x.js"></script> -->'
                '</main><script type="module" src="./app.js"></script>')
        created = self.create({"index.html": html, "app.js": app, "styles.css": "/* url(https://cdn.example/a.png) */ body{color:#123}"})
        self.assertEqual(network(created), [], created["warnings"])
        self.assertFalse(any("Network URLs" in w or "network access" in w for w in created["warnings"]), created["warnings"])

    def test_svg_namespaces_are_inert_but_svg_remote_loads_warn(self):
        app = "const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');\n"
        html = ('<!doctype html><svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">'
                '<circle r="4"/></svg><script type="module" src="./app.js"></script>')
        created = self.create({"index.html": html, "app.js": app})
        self.assertEqual(network(created), [], created["warnings"])
        remote = self.write(created["space"], {"index.html": html.replace('<circle r="4"/>', '<image href="https://example.org/a.png"/>')})
        self.assertEqual(codes(remote, "index.html"), ["net.remote_resource"], remote["warnings"])

    def test_direct_network_misuse_still_warns_with_code_and_location(self):
        app = ("const a = await fetch('https://example.org/data.json');\n"
               "const socket = new WebSocket('wss://example.org');\n"
               "const xhr = new XMLHttpRequest();\n"
               "const events = new EventSource('/stream');\n"
               "navigator.sendBeacon('https://example.org/b');\n"
               "await window.fetch('https://example.org');\n"
               "await space.net.fetch(fetch(url));\n")
        created = self.create({"index.html": INDEX, "app.js": app})
        found = [(d["code"], d["line"]) for d in network(created)]
        self.assertEqual(found, [("net.direct_call", n) for n in (1, 2, 3, 4, 5, 6, 7)], created["warnings"])
        self.assertTrue(all(w.startswith("app.js:") for w in created["warnings"] if "[net." in w), created["warnings"])

    def test_a_nested_local_named_fetch_does_not_hide_a_global_call(self):
        app = "function helper(){ const fetch = value => value; return fetch(1); }\nfetch('https://example.org/data');\n"
        created = self.create({"index.html": INDEX, "app.js": app})
        self.assertIn(("net.direct_call", 2), [(d["code"], d["line"]) for d in network(created)], created["warnings"])
        declared = self.create({"index.html": INDEX, "app.js": "function fetch(url) { return url; }\n"}, name="Declared")
        self.assertEqual(network(declared), [], declared["warnings"])

    def test_only_a_module_scope_declaration_hides_fetch(self):
        for name, app in {
            "loop binding": "for (let fetch of []) { fetch(1); }\nfetch(url);\n",
            "named function expression": "const helper = function fetch() {};\nfetch(url);\n",
            "block const": "{ const fetch = x => x; }\nfetch(url);\n",
        }.items():
            with self.subTest(name):
                created = self.create({"index.html": INDEX, "app.js": app}, name=name.title())
                self.assertIn(("net.direct_call", 2), [(d["code"], d["line"]) for d in network(created)], created["warnings"])
        for name, app in {"module const": "const fetch = u => u;\nfetch(url);\n",
                          "exported function": "export function fetch(u) { return u; }\nfetch(url);\n"}.items():
            with self.subTest(name):
                created = self.create({"index.html": INDEX, "app.js": app}, name=name.title())
                self.assertEqual(network(created), [], created["warnings"])

    def test_division_after_a_member_call_or_template_is_not_a_regex(self):
        for name, first in {"member named if": "const n = obj.if(a) / 2;", "template": "const t = `2` / 2;"}.items():
            with self.subTest(name):
                created = self.create({"index.html": INDEX, "app.js": first + "\nfetch(url);\nimport './missing.js';\n"}, name=name.title())
                self.assertEqual(sorted(codes(created, "app.js")), ["import.unresolved", "net.direct_call"], created["warnings"])

    def test_a_comment_inside_css_import_does_not_hide_the_remote_load(self):
        css = ('@import /* hey */ "https://example.org/a.css";\n'
               'p { background: url(/* hey */"https://example.org/b.png"); }\n'
               'p { content: "/* not a comment */ url(https://x.example/y.png)"; }\n')
        created = self.create({"index.html": INDEX, "styles.css": css})
        self.assertEqual([(d["code"], d["line"]) for d in network(created)], [("net.remote_resource", 1), ("net.remote_resource", 2)], created["warnings"])

    def test_many_css_strings_scan_in_linear_time(self):
        import time
        from living_spaces_core import diagnostics
        source = 'p{content:"x"}' * 16000
        start = time.perf_counter()
        diagnostics.scan("styles.css", source)
        self.assertLess(time.perf_counter() - start, 1.0)

    def test_inline_event_handlers_are_code(self):
        html = '<!doctype html><button onclick="fetch(\'https://example.org/data\')">Load</button><a title="fetch(x)">t</a>'
        created = self.create({"index.html": html})
        self.assertEqual(codes(created, "index.html"), ["net.direct_call"], created["warnings"])

    def test_css_strings_and_regex_after_control_parens_are_inert(self):
        created = self.create({"index.html": INDEX, "app.js": "if (ready) /fetch(url)/.test(text);\nconst half = (a) / 2;\n",
                               "styles.css": 'p::before { content: "url(https://example.org/logo.png)"; }\n'
                                             "a::after { content: '@import \"https://x.example/a.css\"'; }"})
        self.assertEqual(network(created), [], created["warnings"])

    def test_deeply_nested_templates_do_not_crash_saves(self):
        source = "const t = " + "`a${" * 1100 + "1" + "}`" * 1100 + ";\nfetch(u);\n"
        created = self.create({"index.html": INDEX, "app.js": source})
        self.assertEqual(codes(created, "app.js"), ["net.direct_call"], created["warnings"])

    def test_remote_imports_scripts_and_styles_warn(self):
        html = ('<!doctype html><link rel="stylesheet" href="https://cdn.example/a.css">'
                '<script src="https://cdn.example/lib.js"></script><script type="module" src="./app.js"></script>')
        created = self.create({"index.html": html, "app.js": "import confetti from 'https://esm.sh/confetti';\n",
                               "styles.css": "@import url('https://fonts.example/f.css');\nbody{background:url(https://cdn.example/b.png)}"})
        self.assertEqual(sorted(codes(created, "index.html")), ["net.remote_resource", "net.remote_resource"], created["warnings"])
        self.assertEqual(codes(created, "app.js"), ["net.remote_import"], created["warnings"])
        self.assertEqual(sorted(codes(created, "styles.css")), ["net.remote_resource", "net.remote_resource"], created["warnings"])

    def test_edit_from_mediated_to_direct_and_back(self):
        created = self.create({"index.html": INDEX, "app.js": "await space.net.fetch(url);\n"})
        self.assertEqual(network(created), [])
        direct = self.edit(created["space"], "app.js", "space.net.fetch", "fetch")
        self.assertEqual(codes(direct, "app.js"), ["net.direct_call"], direct["warnings"])
        back = self.edit(created["space"], "app.js", "await fetch", "await space.net.fetch")
        self.assertEqual(network(back), [], back["warnings"])

    def test_missing_import_is_reported_with_code_and_target(self):
        created = self.create({"index.html": INDEX, "app.js": "import { list } from './views/missing.js';\n"})
        [found] = [d for d in created["diagnostics"] if d["code"] == "import.unresolved"]
        self.assertEqual((found["path"], found["line"], found["ref"], found["target"]),
                         ("app.js", 1, "./views/missing.js", "views/missing.js"))
        self.assertIn("views/missing.js", " ".join(created["warnings"]))

    def test_unchanged_importer_broken_by_edited_dependency(self):
        files = {"index.html": INDEX, "app.js": "import { Library } from './views/library.js';\nLibrary();\n",
                 "views/library.js": "import { row } from './row.js';\nexport const Library = () => row();\n",
                 "views/row.js": "export const row = () => 1;\n"}
        created = self.create(files)
        self.assertEqual([d for d in created["diagnostics"] if d["code"].startswith("import.")], [], created["warnings"])
        sid = created["space"]
        edited = self.edit(sid, "views/library.js", "'./row.js'", "'./rows.js'")
        broken = [(d["path"], d["ref"]) for d in edited["diagnostics"] if d["code"] == "import.unresolved"]
        self.assertEqual(broken, [("views/library.js", "./rows.js")], edited["warnings"])
        renamed = self.write(sid, {"views/library.js": None, "views/catalog.js": "export const Library = () => 2;\n"})
        broken = [(d["path"], d["ref"]) for d in renamed["diagnostics"] if d["code"] == "import.unresolved"]
        self.assertEqual(broken, [("app.js", "./views/library.js")], renamed["warnings"])
        restored = self.tools.spaces_restore(self.core, {"space": sid, "rev": 2}, "Demo")
        broken = [(d["path"], d["ref"]) for d in restored["diagnostics"] if d["code"] == "import.unresolved"]
        self.assertEqual(broken, [("views/library.js", "./rows.js")], restored)

    def test_bare_import_needs_a_manifest_entry_and_manifest_targets_must_exist(self):
        created = self.create({"index.html": INDEX, "app.js": "import { h } from 'preact';\n"})
        self.assertEqual(codes(created, "app.js"), ["import.bare_unmapped"], created["warnings"])
        mapped = self.create({"index.html": INDEX, "app.js": "import { h } from 'preact';\n"}, name="Mapped",
                             manifest={"entry": "index.html", "imports": {"preact": "vendor/preact.mjs"}})
        self.assertEqual([d["code"] for d in mapped["diagnostics"] if d["code"].startswith("import.")],
                         ["import.alias_target_missing"], mapped["warnings"])

    def test_warning_strings_are_derived_from_diagnostics(self):
        created = self.create({"index.html": INDEX, "app.js": "fetch(u)\nimport './gone.js'\n"})
        static = [d["message"] for d in created["diagnostics"]]
        self.assertEqual([w for w in created["warnings"] if "[" in w and "]" in w], static)
        self.assertTrue(all(d["code"] in d["message"] for d in created["diagnostics"]))

    def test_weather_reference_saves_without_false_warnings(self):
        files = {p.name: p.read_text() for p in WEATHER.iterdir() if p.suffix in (".html", ".js", ".css", ".json")}
        created = self.create(files, name="Weather Window")
        self.assertEqual(created["diagnostics"], [], created["warnings"])
        app = files["app.js"]
        self.assertIn("space.net.fetch(", app)
        self.assertIn("response.json", app)
        self.assertNotIn("response.json()", app)
        self.assertNotIn("meta.network", app)
        self.assertIn("not_granted", app)
        self.assertIn("forecasts", json.loads(files["space.json"])["data"]["collections"])
        self.assertIn("space.put('forecasts'", app)
        edited = self.edit(created["space"], "app.js", "{as:'json'}", "{as: 'json'}")
        self.assertEqual(edited["diagnostics"], [], edited["warnings"])


PARITY_SOURCES = [
    "import { h } from 'preact'; export { x } from '../x.js?v=1'; import './side.js#x';",
    "const x = import('./detail.js'); const y = import('./' + name + '.js');",
    "const text = \"import('./unchanged.js')\"; // import('./comment.js')\n/* import './block.js' */",
    "const t = `result: ${await import(\"./view.mjs\")} and ${`nested ${import('./deep.js')}`}`;",
    "const r = /from '.\\/regex.js'/; const d = a / b; import def, * as ns from \"./named.js\";",
    "export * from './all.js'\nexport default 1\nobj.import('./member.js'); import.meta.url;",
]


class LoaderParityTests(unittest.TestCase):
    def test_module_refs_match_the_imports_the_loader_rewrites(self):
        script = ("import { projectResolver } from './src/guest/loader.mjs';"
                  "const r = projectResolver(); const out = [];"
                  "for (const s of JSON.parse(process.argv[1])) {"
                  "  const seen = []; globalThis.__spaceImport = null;"
                  "  const code = r.rewriteImports('views/main.js', s);"
                  "  for (const m of code.matchAll(/\"https:\\/\\/space\\.invalid\\/([^\"]+)\"/g)) seen.push(m[1]);"
                  "  const dynamic = (code.match(/__spaceImport/g) || []).length;"
                  "  out.push({seen: seen.sort(), dynamic}); }"
                  "console.log(JSON.stringify(out));")
        run = subprocess.run(["node", "--input-type=module", "-e", script, json.dumps(PARITY_SOURCES)],
                             cwd=ROOT, text=True, capture_output=True, check=True)
        spec = importlib.util.spec_from_file_location("parity_diagnostics", PACKAGE / "living_spaces_core/diagnostics.py")
        assert spec is not None and spec.loader is not None
        diagnostics = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(diagnostics)
        for source, loader in zip(PARITY_SOURCES, json.loads(run.stdout)):
            refs = [ref.spec for ref in diagnostics.scan("views/main.js", source).refs if ref.spec.startswith((".", "/"))]
            checked = {diagnostics.resolve("views/main.js", spec) for spec in refs}
            literal_dynamic = {diagnostics.resolve("views/main.js", spec) for spec in refs
                               if f"import('{spec}')" in source or f'import("{spec}")' in source}
            self.assertEqual(checked - literal_dynamic, set(loader["seen"]), source)
            self.assertLessEqual(len(literal_dynamic), loader["dynamic"], source)

if __name__ == "__main__":
    unittest.main()
