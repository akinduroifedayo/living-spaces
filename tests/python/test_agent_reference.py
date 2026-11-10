import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]


class ReferenceDraftTests(unittest.TestCase):
    def test_incoming_changes_keep_selected_editor_and_draft_identity(self):
        (ROOT / ".run").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="agent-reference-", dir=ROOT / ".run") as directory:
            with patch.dict(os.environ, {"HERMES_HOME": directory,
                                         "LIVING_SPACES_DB": str(Path(directory) / "spaces.db")}):
                result = subprocess.run(
                    ["node", "--no-warnings", "--experimental-vm-modules", "--input-type=module"],
                    cwd=ROOT, input=PROBE, text=True, capture_output=True, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("4 draft-retention cases passed", result.stdout)


PROBE = r"""
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { SourceTextModule, SyntheticModule } from 'node:vm';

const base = resolve('src/living-spaces/skills/build-space/references/research-desk/views');
const selected = {id: 'demo-paper', rev: 1, data: {title: 'Public demo paper', priority: 'high', notes: ''}};
const completed = {...selected, rev: 2, data: {...selected.data, status: 'done'}};
const reprioritized = {...selected, rev: 2, data: {...selected.data, priority: 'low'}};

function contains(tree, value) {
  if (tree === value) return true;
  if (Array.isArray(tree)) return tree.some(child => contains(child, value));
  return !!tree && typeof tree === 'object' && Array.isArray(tree.values) && contains(tree.values, value);
}

async function renderView(file, name, states, records) {
  let cursor = 0;
  const Editor = function Editor() {};
  const make = exports => new SyntheticModule(Object.keys(exports), function () {
    for (const [name, value] of Object.entries(exports)) this.setExport(name, value);
  });
  const hooks = make({useState: initial => [states[cursor++], () => {}]});
  const kit = make({
    html: (strings, ...values) => ({strings, values}),
    EmptyState: function EmptyState() {}, SaveIndicator: function SaveIndicator() {},
    useSaveState: () => ({state: 'idle', message: ''})
  });
  const editor = make({Editor});
  const module = new SourceTextModule(readFileSync(resolve(base, file), 'utf8'));
  await module.link(specifier => {
    if (specifier === 'preact/hooks') return hooks;
    if (specifier === 'spaces-kit') return kit;
    if (specifier === './editor.js') return editor;
    throw new Error('Unexpected import ' + specifier);
  });
  await module.evaluate();
  globalThis.window = {space: {field: (record, name) => record.data[name] ?? record.source?.[name]}};
  const tree = module.namespace[name]({records, reload() {}});
  assert(contains(tree, Editor), name + ' removed the selected editor');
  assert(contains(tree, records[0] || selected), name + ' lost the selected record');
  assert(contains(tree, selected.id), name + ' changed the editor key');
}

await renderView('queue.js', 'Queue', ['all', selected], [completed]);
await renderView('queue.js', 'Queue', ['high', selected], [reprioritized]);
await renderView('queue.js', 'Queue', ['all', selected], []);
await renderView('library.js', 'Library', ['', selected, ''], []);
console.log('4 draft-retention cases passed');
"""


if __name__ == "__main__":
    unittest.main()
