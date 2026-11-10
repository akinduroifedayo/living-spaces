import { mountSpace } from '../../../src/desktop/sandbox/index.js';

const example = new URL(location.href).searchParams.get('example') || 'research-desk';
const bundle = await (await fetch('/bundle?example=' + encodeURIComponent(example))).json();
const now = () => Date.now() / 1000;
const rows = new Map();
const key = (collection, id) => `${collection}/${id}`;
const clone = value => structuredClone(value);
const paper = {collection: 'papers', id: 'demo', rev: 1,
  data: {notes: '', status: 'queued', priority: 'normal'},
  source: {title: 'Public synthetic research fixture', summary: 'A fixture, not fetched research.'},
  source_meta: {source_id: 'synthetic', fetched_at: now()}, created_at: now(), updated_at: now(), updated_by: 'agent:fixture'};
const habit = {collection: 'habits', id: 'walk', rev: 1, data: {name: 'Public demo walk'}, source: null};
for (const row of [paper, habit]) rows.set(key(row.collection, row.id), row);
let seq = 0;
let nextId = 0;
const runs = [{id: 'synthetic-success', status: 'succeeded', queued_at: now() - 3600,
  ended_at: now() - 3590, source_as_of: now() - 7200, changed: {unchanged: 1}}];
const announce = row => reference.mount.postEvent('data.changed', {seq: ++seq, changes: [{collection: row.collection, id: row.id, op: 'put', rev: row.rev}]});
const info = message => { document.getElementById('fixture-status').textContent = message; };
window.reference = {synthetic: true, rows, runs, calls: [], events: [], logs: [], denyRefresh: false, failNextSave: false,
  holdSaves: false, heldSaves: [],
  releaseSaves() { for (const release of this.heldSaves.splice(0)) release(); },
  agentWrite(collection, id, data) {
    const previous = rows.get(key(collection, id));
    const row = {...previous, collection, id, data: {...previous?.data, ...data}, rev: (previous?.rev || 0) + 1};
    rows.set(key(collection, id), row); announce(row);
  },
  finishRun(status) {
    const run = runs[0];
    Object.assign(run, {status, ended_at: now(), source_as_of: status === 'succeeded' ? now() - 60 : null,
      error: status === 'failed' ? 'Synthetic source failure' : null});
    reference.mount.postEvent('run.updated', clone(run));
    info('Synthetic run ' + status);
  }
};
const ok = result => ({ok: true, result: clone(result)});
const error = (code, message, extra = {}) => ({ok: false, error: {code, message, ...extra}});
async function call(op, args) {
  reference.calls.push({op, args: clone(args)});
  if (op === 'log') { reference.logs.push(...args.entries); return ok({stored: args.entries.length}); }
  if (op === 'data.query') {
    const records = [...rows.values()].filter(row => row.collection === args.collection &&
      Object.entries(args.where || {}).every(([name, value]) => row.data[name] === value));
    return ok({records: records.slice(args.offset || 0, (args.offset || 0) + (args.limit || 500)), total: records.length, seq});
  }
  if (op === 'data.get') {
    const row = rows.get(key(args.collection, args.id));
    return row ? ok(row) : error('not_found', 'Synthetic record missing');
  }
  if (op === 'data.put') {
    if (reference.holdSaves) await new Promise(resolve => reference.heldSaves.push(resolve));
    await new Promise(resolve => setTimeout(resolve, 500));
    if (reference.failNextSave) { reference.failNextSave = false; return error('blocked', 'Synthetic backend unavailable'); }
    const current = rows.get(key(args.collection, args.id));
    if (current && current.rev !== args.base_rev) return error('conflict', 'Synthetic chat conflict', {current: clone(current)});
    if (!current && ![0, undefined, null].includes(args.base_rev)) return error('not_found', 'Synthetic record missing');
    const row = {...current, collection: args.collection, id: args.id || `demo-${++nextId}`,
      data: {...current?.data, ...args.data}, rev: (current?.rev || 0) + 1};
    rows.set(key(row.collection, row.id), row); announce(row); return ok(row);
  }
  if (op === 'runs.list') return ok(runs);
  if (op === 'refresh') {
    if (reference.denyRefresh) return error('not_granted', 'Synthetic Refresh denial');
    if (['queued', 'running'].includes(runs[0]?.status)) return ok(runs[0]);
    const run = {id: `synthetic-${++nextId}`, status: 'queued', queued_at: now()};
    runs.unshift(run); return ok(run);
  }
  if (op === 'meta') return ok({space: bundle.space, grants: ['data', 'logs', 'refresh'], limits: {}});
  return error('invalid', 'Unsupported synthetic operation');
}
reference.mount = mountSpace(document.getElementById('space'), {bundle,
  grants: ['data', 'logs', 'refresh'], call, onEvent: event => reference.events.push(event)});
document.getElementById('agent').onclick = () => {
  if (example === 'research-desk') reference.agentWrite('papers', 'demo', {notes: 'Synthetic chat notes', status: 'done', priority: 'low'});
  else {
    const date = new Date();
    const day = [date.getFullYear(), String(date.getMonth() + 1).padStart(2, '0'), String(date.getDate()).padStart(2, '0')].join('-');
    reference.agentWrite('checkins', `walk:${day}`, {habit: 'walk', day, done: false});
  }
  info('Synthetic chat edit emitted');
};
document.getElementById('fail').onclick = () => { reference.failNextSave = true; info('Next synthetic save will fail'); };
document.getElementById('deny').onclick = () => { reference.denyRefresh = !reference.denyRefresh; info('Synthetic Refresh denial ' + reference.denyRefresh); };
document.getElementById('success').onclick = () => reference.finishRun('succeeded');
document.getElementById('failure').onclick = () => reference.finishRun('failed');
