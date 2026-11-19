import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { SourceTextModule, SyntheticModule } from 'node:vm';
import { setImmediate as tick } from 'node:timers/promises';
import * as preact from '../../../src/living-spaces/runtime/vendor/preact.mjs';
import * as hooks from '../../../src/living-spaces/runtime/vendor/hooks.mjs';

// Synthetic space transport inputs; actual kit and Preact modules, never native evidence.
preact.options.requestAnimationFrame = callback => queueMicrotask(callback);
preact.options.debounceRendering = callback => queueMicrotask(callback);
const kitPath = resolve('src/living-spaces/runtime/kit/spaces-kit.mjs');
const synthetic = exports => new SyntheticModule(Object.keys(exports), function () {
  for (const [name, value] of Object.entries(exports)) this.setExport(name, value);
});
async function kitFixture(t, transport) {
  const saved = new Map(['space', 'window', 'document'].map(name =>
    [name, Object.getOwnPropertyDescriptor(globalThis, name)]));
  globalThis.space = transport;
  globalThis.window = {space: transport};
  globalThis.document = {getElementById() { return {}; }};
  t.after(() => {
    for (const [name, descriptor] of saved) {
      if (descriptor) Object.defineProperty(globalThis, name, descriptor);
      else delete globalThis[name];
    }
  });
  const modules = new Map([
    ['preact', synthetic(preact)], ['preact/hooks', synthetic(hooks)]
  ]);
  const module = new SourceTextModule(readFileSync(kitPath, 'utf8'), {identifier: kitPath});
  await module.link(specifier => {
    assert(modules.has(specifier), `Unexpected kit fixture dependency: ${specifier}`);
    return modules.get(specifier);
  });
  await module.evaluate();
  return module.namespace;
}
const deferred = () => {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return {promise, resolve, reject};
};
const requirePage = kit => assert.equal(typeof kit.queryPage, 'function', 'new page capability absent');
const cursor = {v: 1, space: 'q14-fixture', created_at: 10, seq: 12, offset: 2, query: 'a'.repeat(64)};
const firstPage = {
  records: [{id: 'a', data: {rank: 7}}, {id: 'b', data: {rank: 7}}],
  total: 3, seq: 12, has_more: true, next_cursor: cursor
};
const lastPage = {
  records: [{id: 'c', data: {rank: 7}}], total: 3, seq: 12, has_more: false, next_cursor: null
};

test('Q14 legacy useCollection retains records/loading/error/reload and array reloads', async t => {
  const calls = [];
  const jobs = [];
  const listeners = new Set();
  const transport = {
    query(...args) {
      calls.push(args);
      const job = deferred();
      jobs.push(job);
      return job.promise;
    },
    queryPage() { assert.fail('legacy useCollection must not upgrade to page mode'); },
    on(event, callback) {
      assert.equal(event, 'change');
      listeners.add(callback);
      return () => listeners.delete(callback);
    }
  };
  const kit = await kitFixture(t, transport);
  const options = {where: {status: 'reading'}, order: 'rank', limit: 2};
  const container = {nodeType: 1, childNodes: []};
  let value;
  function Capture() { value = kit.useCollection('papers', options); return null; }
  preact.render(preact.h(Capture), container);
  try {
    await tick();
    assert.deepEqual(Object.keys(value).sort(), ['error', 'loading', 'records', 'reload']);
    assert.deepEqual(value.records, []);
    assert.equal(value.loading, true);
    assert.equal(value.error, null);
    assert.equal(typeof value.reload, 'function');
    assert.deepEqual(calls, [['papers', options]]);
    const rows = [{id: 'a'}, {id: 'b'}];
    jobs[0].resolve(rows);
    await tick();
    assert.deepEqual(value.records, rows);
    assert.equal(Array.isArray(value.records), true);
    assert.equal(value.loading, false);
    assert.equal(value.error, null);
    assert.equal(calls.length, 1, 'a legacy array must not trigger a materialize-all query');

    for (const callback of listeners) callback({changes: [{collection: 'other', id: 'x'}]});
    await tick();
    assert.equal(calls.length, 1);
    const reload = value.reload();
    assert.deepEqual(calls[1], ['papers', options]);
    jobs[1].resolve([{id: 'c'}]);
    assert.deepEqual(await reload, [{id: 'c'}]);
    await tick();
    assert.deepEqual(value.records, [{id: 'c'}]);
    assert.equal(value.loading, false);

    const failedReload = value.reload();
    const offline = Object.assign(new Error('Synthetic transport unavailable'), {code: 'unavailable'});
    jobs[2].reject(offline);
    await failedReload;
    await tick();
    assert.deepEqual(value.records, [{id: 'c'}]);
    assert.equal(value.loading, false);
    assert.equal(value.error, offline);
    assert.equal(calls.length, 3, 'failed legacy reload must not retry automatically');
  } finally { preact.render(null, container); }
  assert.equal(listeners.size, 0);
});

test('Q14 named kit queryPage forwards options and preserves nonterminal and terminal envelopes', async t => {
  const calls = [];
  const jobs = [];
  const kit = await kitFixture(t, {
    query() { assert.fail('named queryPage must delegate to space.queryPage'); },
    queryPage(...args) {
      calls.push(structuredClone(args));
      const job = deferred();
      jobs.push(job);
      return job.promise;
    }
  });
  requirePage(kit);
  const options = {where: {status: 'reading'}, order: 'rank', limit: 2, offset: 0};
  const original = structuredClone(options);
  const pending = kit.queryPage('papers', options);
  assert.deepEqual(calls, [['papers', original]]);
  jobs[0].resolve(firstPage);
  assert.deepEqual(await pending, firstPage);
  assert.deepEqual(options, original);
  await tick();
  assert.equal(calls.length, 1, 'a nonterminal result must not fetch more pages automatically');

  const continuation = {where: {status: 'reading'}, order: 'rank', limit: 2, cursor};
  const next = kit.queryPage('papers', continuation);
  assert.deepEqual(calls[1], ['papers', continuation]);
  jobs[1].resolve(lastPage);
  assert.deepEqual(await next, lastPage);
  await tick();
  assert.equal(calls.length, 2, 'terminal result must not dispatch another query');
});

test('Q14 named kit queryPage preserves typed expiry and never silently restarts', async t => {
  const calls = [];
  const expiry = Object.assign(new Error('Synthetic cursor expiry'), {
    name: 'SpaceError', code: 'cursor_expired', restart_required: true, reason: 'changed'
  });
  const kit = await kitFixture(t, {
    query() { assert.fail('expiry must not fall back to legacy query'); },
    async queryPage(...args) { calls.push(structuredClone(args)); throw expiry; }
  });
  requirePage(kit);
  const options = {where: {status: 'reading'}, order: 'rank', limit: 2, cursor};
  await assert.rejects(kit.queryPage('papers', options), error => {
    assert.equal(error, expiry);
    assert.equal(error.code, 'cursor_expired');
    assert.equal(error.restart_required, true);
    assert.equal(error.reason, 'changed');
    assert.equal('records' in error, false);
    return true;
  });
  await tick();
  assert.deepEqual(calls, [['papers', options]]);
});

test('Q14 named kit queryPage returns an empty terminal Page without converting it to an array', async t => {
  const empty = {records: [], total: 0, seq: 12, has_more: false, next_cursor: null};
  const calls = [];
  const kit = await kitFixture(t, {
    async queryPage(...args) { calls.push(args); return empty; }
  });
  requirePage(kit);
  const options = {order: 'rank', limit: 2};
  const result = await kit.queryPage('papers', options);
  assert.deepEqual(result, empty);
  assert.equal(Array.isArray(result), false);
  await tick();
  assert.deepEqual(calls, [['papers', options]]);
});
