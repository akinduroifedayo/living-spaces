import json
import os
import subprocess

from tests.python.test_core_store import CoreCase, ROOT
from living_spaces_core import projects, records


class Q09SavedControlsTests(CoreCase):
    def test_saved_control_bindings_preserve_real_records(self):
        self.write({}, libraries=["spaces-kit"], base_rev=1)
        self.put(data={"note": "Public Q09 fixture"})
        before = records.get(self.sid, "papers", "paper")
        bundle = projects.bundle(self.sid)
        result = subprocess.run(
            ["node", "--no-warnings", "--experimental-vm-modules", "--input-type=module", "-e", PROBE],
            input=json.dumps(bundle), text=True, capture_output=True, cwd=ROOT,
            env={name: os.environ[name] for name in
                 ("PATH", "HOME", "TMPDIR", "HERMES_HOME", "NODE_PATH", "LANG", "LC_ALL")
                 if name in os.environ}, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("saved Q09 keyboard journey passed", result.stdout)
        self.assertEqual(records.get(self.sid, "papers", "paper"), before)
        self.assertEqual(projects.bundle(self.sid)["rev"], bundle["rev"])


PROBE = r"""
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { homedir } from 'node:os';
import { join, posix } from 'node:path';
import { SourceTextModule } from 'node:vm';
const require = createRequire(join(homedir(), '.hermes/hermes-agent/apps/desktop/node_modules/react/package.json'));
const {JSDOM} = require('jsdom');
const bundle = JSON.parse(readFileSync(0, 'utf8'));
const files = new Map(bundle.files.map(file => [file.path, file.text]));
const cache = new Map();
async function load(path) {
  if (cache.has(path)) return cache.get(path);
  const module = new SourceTextModule(files.get(path), {identifier: path});
  cache.set(path, module);
  await module.link(specifier => load(specifier.startsWith('.')
    ? posix.normalize(posix.join(posix.dirname(path), specifier))
    : bundle.manifest.imports[specifier]));
  return module;
}
const module = await load(bundle.manifest.imports['spaces-kit']);
await module.evaluate();
const kit = module.namespace;
for (const name of ['bindDialog', 'bindDrawer', 'bindMenu', 'bindTabs', 'bindDisclosure']) {
  assert.equal(typeof kit[name], 'function', name + ' must be copied into saved apps');
}
const dom = new JSDOM('<button>Open public fixture</button><dialog><button data-close>Close</button></dialog>');
try {
  const doc = dom.window.document;
  const trigger = doc.querySelector('button'), content = doc.querySelector('dialog');
  const controller = kit.bindDialog({trigger, content, label: 'Public fixture'});
  trigger.focus(); trigger.click();
  assert.equal(content.open, true);
  assert.equal(doc.activeElement, content.querySelector('button'));
  content.dispatchEvent(new dom.window.KeyboardEvent('keydown', {key: 'Escape', bubbles: true, cancelable: true}));
  assert.equal(content.open, false);
  assert.equal(doc.activeElement, trigger);
  assert.equal(doc.querySelector('[inert]'), null);
  controller.destroy();
  console.log('saved Q09 keyboard journey passed');
} finally { dom.window.close(); }
"""
