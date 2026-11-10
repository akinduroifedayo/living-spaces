import { readFile } from 'node:fs/promises';
import { resolve, extname } from 'node:path';

const root = resolve(import.meta.dirname, '../../..');
export const mime = {'.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css'};
export async function referenceBundle(example = 'research-desk') {
  const base = resolve(root, 'src/living-spaces/skills/build-space/references');
  let manifest;
  let files;
  if (example === 'habit-planner') {
    const source = await readFile(resolve(base, 'habit-planner.md'), 'utf8');
    const block = language => source.match(new RegExp('```' + language + '\\n([\\s\\S]*?)\\n```'))[1];
    manifest = JSON.parse(block('json'));
    files = [{path: 'index.html', mime: mime['.html'], text: block('html')}, {path: 'app.js', mime: mime['.js'], text: block('js')}];
  } else if (example === 'research-desk') {
    manifest = JSON.parse(await readFile(resolve(base, example, 'space.json'), 'utf8'));
    const paths = ['index.html', 'styles.css', 'app.js', 'views/editor.js', 'views/library.js', 'views/overview.js', 'views/queue.js'];
    files = await Promise.all(paths.map(async path => ({path, mime: mime[extname(path)], text: await readFile(resolve(base, example, path), 'utf8')})));
  } else throw new Error('Unknown reference example');
  for (const path of ['kit/spaces-kit.mjs', 'kit/spaces-kit.css', 'vendor/preact.mjs', 'vendor/hooks.mjs']) {
    files.push({path, mime: mime[extname(path)], text: await readFile(resolve(root, 'src/living-spaces/runtime', path), 'utf8')});
  }
  const sandbox = {format: 1, shell_srcdoc: await readFile(resolve(root, 'src/living-spaces/guest/space-host.html'), 'utf8')};
  return {sandbox, space: {id: 'reference-demo', name: manifest.name}, rev: 1, manifest, files};
}
