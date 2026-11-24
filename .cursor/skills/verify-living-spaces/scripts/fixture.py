#!/Users/ifedayoakinduro/.hermes/hermes-agent/venv/bin/python
"""Fixture preparation through the released agent tool handler, not chat proof."""
import importlib.util
import json
import os
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]).resolve()
assert Path(os.environ['HERMES_HOME']).resolve() == out / 'state/home'
# Desktop may create its own anonymous Welcome auth state. Never read or copy it.
package = root / 'src/living-spaces'
spec = importlib.util.spec_from_file_location('verification_living_spaces', package / '__init__.py',
                                            submodule_search_locations=[str(package)])
assert spec is not None and spec.loader is not None
plugin = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = plugin
spec.loader.exec_module(plugin)
html = (Path(__file__).resolve().parents[1] / 'fixtures/notebook.html').read_text()
args = dict(name='Verification Notebook', description='Disposable note persistence check',
            files={'index.html': html}, libraries=[], manifest={'entry': 'index.html',
            'data': {'version': 1, 'collections': {'notes': {'description': 'Saved user notes'}}}})
reply = json.loads(plugin._handler(plugin.spaces_create)(args))
(out / 'fixture-create.json').write_text(json.dumps(dict(evidence_class='fixture preparation, not Desktop chat creation',
                                                      arguments=args, reply=reply), indent=2))
assert reply['ok'], reply
print(json.dumps(reply))
