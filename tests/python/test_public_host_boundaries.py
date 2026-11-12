import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / 'src/living-spaces'


class PublicHostBoundaryTests(unittest.TestCase):
    def test_python_has_no_private_cron_or_cli_imports(self):
        findings = []
        for path in PACKAGE.rglob('*.py'):
            for node in ast.walk(ast.parse(path.read_text())):
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    names = [node.module or '']
                elif isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant):
                    function = node.func
                    if ((isinstance(function, ast.Attribute) and function.attr == 'import_module')
                            or (isinstance(function, ast.Name) and function.id == '__import__')):
                        names = [node.args[0].value]
                for name in names:
                    if isinstance(name, str) and name.split('.')[0] in {'cron', 'hermes_cli'}:
                        findings.append(f'{path.relative_to(ROOT)}:{node.lineno} {name}')
        self.assertEqual(findings, [])

    def test_renderer_sources_and_bundle_do_not_use_private_desktop_fields(self):
        findings = []
        paths = list((ROOT / 'src/desktop').rglob('*')) + [PACKAGE / 'desktop/plugin.js']
        for path in paths:
            if path.suffix not in {'.js', '.jsx', '.mjs'}:
                continue
            text = path.read_text()
            for token in ('hermesDesktop', 'queryScope'):
                if token in text:
                    findings.append(f'{path.relative_to(ROOT)} uses {token}')
        self.assertEqual(findings, [])

    def test_maintainer_reads_public_session_context(self):
        tree = ast.parse((PACKAGE / '__init__.py').read_text())
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == '_maintainer')
        imports = [node.module for node in ast.walk(function) if isinstance(node, ast.ImportFrom)]
        self.assertIn('gateway.session_context', imports)
        calls = [node for node in ast.walk(function) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == 'get_session_env']
        self.assertEqual(len(calls), 1)
        self.assertEqual([arg.value for arg in calls[0].args], ['HERMES_SESSION_KEY', ''])
