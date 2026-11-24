#!/Users/ifedayoakinduro/.hermes/hermes-agent/venv/bin/python
"""Exercise candidate's registered inspection handler; not Desktop/chat proof."""
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys

root, out = map(lambda p: Path(p).resolve(), sys.argv[1:])
assert Path(os.environ['HERMES_HOME']).resolve() == out / 'state/home'
package = root / 'src/living-spaces'
spec = importlib.util.spec_from_file_location('verification_living_spaces', package / '__init__.py',
                                            submodule_search_locations=[str(package)])
assert spec is not None and spec.loader is not None
plugin = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = plugin
spec.loader.exec_module(plugin)
assert hasattr(plugin, 'spaces_inspect'), 'Runtime inspection is absent in released 0.1.1 (4aea12d)'
db = out / 'state/home/plugin-data/living-spaces/spaces.db'
def snapshot():
    with sqlite3.connect(f'file:{db}?mode=ro', uri=True) as connection:
        connection.execute('PRAGMA query_only=ON')
        text = '\n'.join(connection.iterdump())
    return hashlib.sha256(text.encode()).hexdigest()
before = snapshot()
reply = json.loads(plugin._handler(plugin.spaces_inspect)({'space': 'verification-notebook', 'rev': 1}))
after = snapshot()
proof = dict(evidence_class='registered agent-tool handler + real headless renderer; not native chat or Desktop click',
             before=before, after=after, canonical_sql_unchanged=before == after, reply=reply,
             stop_interruption='unverified: no native /stop was dispatched')
(out / 'inspection-proof.json').write_text(json.dumps(proof, indent=2))
print(json.dumps(proof, indent=2))
assert reply.get('ok') and before == after, proof
result = reply['result']
assert result['rev'] == 1 and result['outcome'] == 'loaded', proof
assert 'Verification Notebook' in result['text']['content'], proof
assert result['cleanup'] == {'process_exited': True, 'temp_removed': True}, proof
