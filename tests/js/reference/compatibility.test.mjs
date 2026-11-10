import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { SourceTextModule, SyntheticModule } from 'node:vm';
import { setImmediate as tick } from 'node:timers/promises';
import * as preact from '../../../src/living-spaces/runtime/vendor/preact.mjs';
import * as hooks from '../../../src/living-spaces/runtime/vendor/hooks.mjs';

preact.options.requestAnimationFrame = callback => queueMicrotask(callback);
preact.options.debounceRendering = callback => queueMicrotask(callback);
const base = resolve('src/living-spaces/skills/build-space/references');
const modules = new Map();
let root;
const synthetic = exports => new SyntheticModule(Object.keys(exports), function () {
  for (const [name, value] of Object.entries(exports)) this.setExport(name, value);
});
modules.set('preact', synthetic({...preact, render: vnode => { root = vnode; }}));
modules.set('preact/hooks', synthetic(hooks));
async function load(path, source) {
  if (modules.has(path)) return modules.get(path);
  const module = new SourceTextModule(source ?? readFileSync(path, 'utf8'), {identifier: path});
  modules.set(path, module);
  await module.link(specifier => {
    if (modules.has(specifier)) return modules.get(specifier);
    return load(specifier === 'spaces-kit' ? resolve('src/living-spaces/runtime/kit/spaces-kit.mjs') : resolve(dirname(path), specifier));
  });
  await module.evaluate();
  return module;
}
const kit = (await load(resolve('src/living-spaces/runtime/kit/spaces-kit.mjs'))).namespace;
const {Editor} = (await load(resolve(base, 'research-desk/views/editor.js'))).namespace;
const {Library} = (await load(resolve(base, 'research-desk/views/library.js'))).namespace;
const {Overview} = (await load(resolve(base, 'research-desk/views/overview.js'))).namespace;
globalThis.document = {getElementById() { return {}; }};
const listeners = new Set();
globalThis.location = {hash: '#/overview'};
globalThis.addEventListener = (name, fn) => { if (name === 'hashchange') listeners.add(fn); };
globalThis.removeEventListener = (name, fn) => listeners.delete(fn);
await load(resolve(base, 'research-desk/app.js'));
const App = root.type;
const habit = readFileSync(resolve(base, 'habit-planner.md'), 'utf8').match(/```js\n([\s\S]*?)\n```/)[1];
await load(resolve(base, 'habit-app.js'), habit);
const Planner = root.type;
const deferred = () => {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return {promise, resolve, reject};
};
const walk = tree => Array.isArray(tree) ? tree.flatMap(walk) : tree && typeof tree === 'object' ? [tree, ...walk(tree.props?.children)] : [];
const text = tree => Array.isArray(tree) ? tree.map(text).join(' ') : tree && typeof tree === 'object' ? text(tree.props?.children) : String(tree ?? '');
const find = (tree, type) => walk(tree).find(node => node.type === type);
const all = (tree, type) => walk(tree).filter(node => node.type === type);
const submit = tree => find(tree, 'form').props.onSubmit({preventDefault() {}});
function fixture(Component, props = {}, api = {}) {
  const subscriptions = {change: new Set(), run: new Set()};
  globalThis.space = {field: (record, name) => record.data[name] ?? record.source?.[name],
    on(event, cb) { subscriptions[event].add(cb); return () => subscriptions[event].delete(cb); }, ...api};
  globalThis.window = {space};
  const container = {nodeType: 1, childNodes: []};
  let tree;
  function Capture() { tree = Component(props); return null; }
  const rerender = () => preact.render(preact.h(Capture, {stamp: {}}), container);
  rerender();
  return {get tree() { return tree; }, subscriptions, rerender,
    emit(event, payload) { for (const cb of subscriptions[event]) cb(payload); },
    cleanup() { preact.render(null, container); }};
}
const paper = {collection: 'papers', id: 'demo', rev: 1, data: {title: 'Public fixture', status: 'queued', priority: 'normal', notes: ''}, source: null};
const indicator = tree => find(tree, kit.SaveIndicator).props;
const draft = tree => ({notes: find(tree, 'textarea').props.value, status: all(tree, 'select')[0].props.value, priority: all(tree, 'select')[1].props.value});
async function edit(f) {
  find(f.tree, 'textarea').props.onInput({target: {value: 'My draft'}});
  all(f.tree, 'select')[0].props.onChange({target: {value: 'reading'}});
  all(f.tree, 'select')[1].props.onChange({target: {value: 'high'}});
  await tick();
}

test('Editor confirms notes, status and priority only after the backend, and keeps failed drafts', async () => {
  const pending = deferred();
  const calls = [];
  let reloads = 0;
  const f = fixture(Editor, {record: paper, reload() { reloads++; }}, {put(...args) { calls.push(args); return pending.promise; }});
  try {
    await tick();
    await edit(f);
    const saving = submit(f.tree);
    await tick();
    assert.equal(indicator(f.tree).state, 'saving');
    assert.equal(reloads, 0);
    assert.deepEqual(calls[0], ['papers', 'demo', {notes: 'My draft', status: 'reading', priority: 'high'}, {baseRev: 1}]);
    pending.resolve({...paper, rev: 2, data: {...paper.data, ...calls[0][2]}});
    await saving;
    await tick();
    assert.equal(indicator(f.tree).state, 'saved');
    assert.equal(reloads, 1);
    await edit(f);
    find(f.tree, 'textarea').props.onInput({target: {value: 'Offline draft'}});
    await tick();
    space.put = async () => { throw new Error('Backend unavailable'); };
    await submit(f.tree);
    await tick();
    assert.equal(indicator(f.tree).state, 'failed');
    assert.equal(draft(f.tree).notes, 'Offline draft');
    assert.equal(reloads, 1);
  } finally { f.cleanup(); }
});

test('Editor preserves drafts on conflict, rebases explicitly and requires a separate save', async () => {
  const current = {...paper, rev: 7, data: {...paper.data, notes: 'Chat notes'}};
  const calls = [];
  const props = {record: paper, reload() {}};
  const f = fixture(Editor, props, {async put(...args) {
    calls.push(args);
    if (calls.length === 1) throw Object.assign(new Error('Changed elsewhere'), {code: 'conflict', current});
    return {...current, rev: 8, data: {...current.data, ...args[2]}};
  }});
  try {
    await tick();
    await edit(f);
    await submit(f.tree);
    await tick();
    assert.equal(indicator(f.tree).state, 'conflict');
    assert.equal(draft(f.tree).notes, 'My draft');
    props.record = current;
    f.rerender();
    await tick();
    assert.equal(draft(f.tree).notes, 'My draft');
    const banner = find(f.tree, kit.ConflictBanner);
    assert.equal(banner.props.current, current);
    const buttons = all(kit.ConflictBanner(banner.props), 'button');
    buttons[0].props.onClick();
    await tick();
    assert.equal(calls.length, 1, 'Keep mine must not write automatically');
    assert.equal(draft(f.tree).notes, 'My draft');
    await submit(f.tree);
    await tick();
    assert.equal(calls[1][3].baseRev, 7);
    assert.equal(calls[1][2].notes, 'My draft');
    assert.equal(indicator(f.tree).state, 'saved');
  } finally { f.cleanup(); }
});

test('Editor Use updated adopts authoritative values without writing', async () => {
  const current = {...paper, rev: 4, data: {...paper.data, notes: 'Authoritative', status: 'done'}};
  let calls = 0;
  const f = fixture(Editor, {record: paper, reload() {}}, {async put() {
    calls++;
    throw Object.assign(new Error('Changed'), {code: 'conflict', current});
  }});
  try {
    await tick(); await edit(f); await submit(f.tree); await tick();
    const banner = find(f.tree, kit.ConflictBanner);
    all(kit.ConflictBanner(banner.props), 'button')[1].props.onClick();
    await tick();
    assert.equal(calls, 1);
    assert.equal(draft(f.tree).notes, 'Authoritative');
    assert.equal(draft(f.tree).status, 'done');
    assert.equal(find(f.tree, kit.ConflictBanner), undefined);
  } finally { f.cleanup(); }
});

test('Library uses actual EmptyState children and retains creation text until confirmation', async () => {
  const pending = deferred();
  const f = fixture(Library, {records: [], reload() {}}, {put: () => pending.promise});
  try {
    const empty = find(f.tree, kit.EmptyState);
    assert.match(text(kit.EmptyState(empty.props)), /Add a paper above/);
    all(f.tree, 'input')[1].props.onInput({target: {value: 'Demo paper'}});
    await tick();
    const saving = submit(f.tree);
    await tick();
    assert.equal(indicator(f.tree).state, 'saving');
    assert.equal(all(f.tree, 'input')[1].props.value, 'Demo paper');
    pending.resolve({...paper, id: 'new-demo'});
    await saving; await tick();
    assert.equal(all(f.tree, 'input')[1].props.value, '');
    assert.equal(find(f.tree, Editor).props.record.id, 'new-demo');
  } finally { f.cleanup(); }
});

test('App uses real routing and collection subscriptions without unmounting views on reload', async () => {
  const pending = [];
  const f = fixture(App, {}, {query() { const job = deferred(); pending.push(job); return job.promise; }, async runs() { return []; }});
  try {
    await tick();
    pending[0].resolve([paper]); await tick();
    location.hash = '#/library'; listeners.forEach(fn => fn()); await tick();
    assert.equal(find(f.tree, Library).props.records[0].id, 'demo');
    f.emit('change', {changes: [{collection: 'papers', id: 'demo'}]}); await tick();
    assert(find(f.tree, Library), 'live requery must retain the active view and its drafts');
    pending[1].resolve([{...paper, rev: 2, data: {...paper.data, notes: 'Chat update'}}]); await tick();
    assert.equal(find(f.tree, Library).props.records[0].data.notes, 'Chat update');
    f.emit('change', {changes: [{collection: 'papers', id: 'demo'}]}); await tick();
    pending[2].reject(new Error('Query offline')); await tick();
    assert.equal(find(f.tree, Library).props.records[0].rev, 2);
    assert.match(text(f.tree), /Query offline/);
    location.hash = '#/queue'; listeners.forEach(fn => fn()); await tick();
    assert(walk(f.tree).some(node => node.type?.name === 'Queue'));
    location.hash = '#/overview'; listeners.forEach(fn => fn()); await tick();
    assert(find(f.tree, Overview));
  } finally { f.cleanup(); }
  assert.equal(f.subscriptions.change.size, 0);
  assert.equal(f.subscriptions.run.size, 0);
});

test('freshness keeps failed attempts, successful completion and source time distinct', () => {
  const success = {status: 'succeeded', queued_at: 100, ended_at: 120, source_as_of: 80};
  const latest = {status: 'failed', queued_at: 200, error: 'Public fixture timeout'};
  const tree = Overview({records: [], runs: [latest, success]});
  const values = all(tree, 'dd').map(node => text(node));
  assert.match(values[0], /failed/);
  assert.equal(values[1], new Date(120000).toLocaleString());
  assert.equal(values[2], new Date(80000).toLocaleString());
  assert.match(text(tree), /Existing records and notes remain available/);
  assert.match(text(kit.EmptyState(find(tree, kit.EmptyState).props)), /Add a paper in Library/);
  assert.match(text(Overview({records: [], runs: [latest]})), /No success in recent history/);
});

test('habit check-in keeps its intended value after conflict and retries only explicitly', async () => {
  const habits = [{id: 'walk', rev: 1, data: {name: 'Public demo walk'}}];
  let current = null;
  const calls = [];
  let pending;
  const f = fixture(Planner, {}, {async query(collection) { return collection === 'habits' ? habits : current ? [current] : []; }, put(...args) { calls.push(args); pending = deferred(); return pending.promise; }});
  try {
    await tick();
    const checkbox = () => all(f.tree, 'input').find(node => node.props.type === 'checkbox');
    const saving = checkbox().props.onChange();
    await tick();
    assert.equal(indicator(f.tree).state, 'saving');
    assert.equal(checkbox().props.checked, false);
    current = {id: calls[0][1], rev: 3, data: {...calls[0][2], done: false}};
    pending.reject(Object.assign(new Error('Changed check-in'), {code: 'conflict', current}));
    await saving; await tick();
    assert.equal(indicator(f.tree).state, 'conflict');
    const banner = find(f.tree, kit.ConflictBanner);
    assert(banner, 'conflict needs explicit draft actions');
    assert.equal(banner.props.current.rev, 3);
    const retry = all(kit.ConflictBanner(banner.props), 'button')[0].props.onClick();
    await tick();
    assert.equal(calls.length, 2);
    assert.equal(calls[1][3].baseRev, 3);
    assert.equal(calls[1][2].done, true);
    pending.resolve({...current, rev: 4, data: {...current.data, done: true}});
    current = {...current, rev: 4, data: {...current.data, done: true}};
    await retry; await tick();
    assert.equal(indicator(f.tree).state, 'saved');
    assert.equal(checkbox().props.checked, true);
  } finally { f.cleanup(); }
});

test('Library failed creation retains the title and never selects a fictitious record', async () => {
  const f = fixture(Library, {records: [], reload() { assert.fail('failed create must not reload'); }}, {async put() { throw new Error('Create offline'); }});
  try {
    all(f.tree, 'input')[1].props.onInput({target: {value: 'Unsaved public title'}});
    await tick(); await submit(f.tree); await tick();
    assert.equal(indicator(f.tree).state, 'failed');
    assert.equal(all(f.tree, 'input')[1].props.value, 'Unsaved public title');
    assert.equal(find(f.tree, Editor), undefined);
  } finally { f.cleanup(); }
});

test('habit creation uses confirmation and keeps failed names and EmptyState instructions', async () => {
  let pending;
  const f = fixture(Planner, {}, {async query() { return []; }, put() { pending = deferred(); return pending.promise; }});
  try {
    await tick();
    assert.match(text(kit.EmptyState(find(f.tree, kit.EmptyState).props)), /Add something small/);
    const name = () => all(f.tree, 'input').find(node => !node.props.type);
    name().props.onInput({target: {value: 'Public demo reading'}});
    await tick();
    const saving = submit(f.tree); await tick();
    assert.equal(indicator(f.tree).state, 'saving');
    assert.equal(name().props.value, 'Public demo reading');
    assert.equal(name().props.disabled, true);
    pending.reject(new Error('Create failed')); await saving; await tick();
    assert.equal(indicator(f.tree).state, 'failed');
    assert.equal(name().props.value, 'Public demo reading');
    const retry = submit(f.tree); await tick();
    pending.resolve({id: 'reading', rev: 1, data: {name: 'Public demo reading'}});
    await retry; await tick();
    assert.equal(indicator(f.tree).state, 'saved');
    assert.equal(name().props.value, '');
  } finally { f.cleanup(); }
});

test('habit conflict discard reloads authoritative check-ins without retrying', async () => {
  let current = null;
  let calls = 0;
  const f = fixture(Planner, {}, {async query(collection) { return collection === 'habits' ? [{id: 'walk', data: {name: 'Walk'}}] : current ? [current] : []; }, async put(collection, id, data) {
    calls++;
    current = {id, rev: 5, data: {...data, done: false}};
    throw Object.assign(new Error('Changed'), {code: 'conflict', current});
  }});
  try {
    await tick();
    await all(f.tree, 'input').find(node => node.props.type === 'checkbox').props.onChange(); await tick();
    const banner = find(f.tree, kit.ConflictBanner);
    all(kit.ConflictBanner(banner.props), 'button')[1].props.onClick(); await tick();
    assert.equal(calls, 1);
    assert.equal(find(f.tree, kit.ConflictBanner), undefined);
    assert.equal(all(f.tree, 'input').find(node => node.props.type === 'checkbox').props.checked, false);
    assert.doesNotMatch(text(f.tree), /Unsaved check-in/);
  } finally { f.cleanup(); }
});

test('actual RefreshButton handles denial, queued replies, failure and success events', async () => {
  let denied = true;
  const f = fixture(kit.RefreshButton, {}, {async refresh() {
    if (denied) throw Object.assign(new Error('Denied'), {code: 'not_granted'});
    return {id: 'fixture-run', status: 'queued'};
  }});
  try {
    await tick();
    await find(f.tree, 'button').props.onClick(); await tick();
    assert.match(text(f.tree), /approve Refresh in Permissions/);
    denied = false;
    await find(f.tree, 'button').props.onClick(); await tick();
    assert.match(text(f.tree), /Refresh queued/);
    assert.equal(find(f.tree, 'button').props.disabled, true);
    f.emit('run', {id: 'fixture-run', status: 'failed', error: 'Synthetic timeout'}); await tick();
    assert.match(text(f.tree), /Synthetic timeout/);
    assert.equal(find(f.tree, 'button').props.disabled, false);
    f.emit('run', {id: 'fixture-run', status: 'succeeded'}); await tick();
    assert.match(text(f.tree), /Refresh complete/);
  } finally { f.cleanup(); }
  assert.equal(f.subscriptions.run.size, 0);
});

test('Chrome smoke bundles contain the unchanged actual kit, examples and resolvable local imports', async () => {
  const {referenceBundle} = await import('./bundle.mjs');
  for (const example of ['research-desk', 'habit-planner']) {
    const bundle = await referenceBundle(example);
    const files = new Map(bundle.files.map(file => [file.path, file.text]));
    assert.equal(files.get('kit/spaces-kit.mjs'), readFileSync('src/living-spaces/runtime/kit/spaces-kit.mjs', 'utf8'));
    assert.equal(files.get('vendor/preact.mjs'), readFileSync('src/living-spaces/runtime/vendor/preact.mjs', 'utf8'));
    for (const [path, source] of files) {
      if (!/\.m?js$/.test(path)) continue;
      const module = new SourceTextModule(source);
      for (const specifier of module.dependencySpecifiers) {
        const target = specifier.startsWith('.') ? resolve('/', dirname(path), specifier).slice(1) : bundle.manifest.imports[specifier];
        assert(files.has(target), `${example}: ${path} cannot import ${specifier}`);
      }
    }
  }
});

test('habit retry retains its rebased revision if that explicit retry fails', async () => {
  const calls = [];
  const f = fixture(Planner, {}, {async query(collection) { return collection === 'habits' ? [{id: 'walk', data: {name: 'Walk'}}] : []; }, async put(...args) {
    calls.push(args);
    if (calls.length === 1) throw Object.assign(new Error('Changed'), {code: 'conflict', current: {id: args[1], rev: 3, data: {...args[2], done: false}}});
    if (calls.length === 2) throw new Error('Backend offline');
    return {id: args[1], rev: 4, data: args[2]};
  }});
  try {
    await tick();
    await all(f.tree, 'input').find(node => node.props.type === 'checkbox').props.onChange(); await tick();
    const banner = find(f.tree, kit.ConflictBanner);
    await all(kit.ConflictBanner(banner.props), 'button')[0].props.onClick(); await tick();
    assert.equal(indicator(f.tree).state, 'failed');
    const retry = all(f.tree, 'button').find(node => text(node) === 'Retry check-in');
    await retry.props.onClick(); await tick();
    assert.equal(calls[1][3].baseRev, 3);
    assert.equal(calls[2][3].baseRev, 3);
    assert.equal(calls[2][2].done, true);
    assert.equal(indicator(f.tree).state, 'saved');
  } finally { f.cleanup(); }
});
