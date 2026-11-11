// Mounts a showcase Space in the real sandbox. Query params:
//   name=<showcase dir>   net=off (host answers not_granted)   seed=<fixture name>
import { mountSpace } from '../../../../src/desktop/sandbox/index.js';
const q = new URL(location.href).searchParams;
const name = q.get('name') || 'sky-window';
const netOff = q.get('net') === 'off';
const bundle = await (await fetch('/bundle?name=' + encodeURIComponent(name))).json();
const rows = new Map();
const key = (c, id) => c + '/' + id;
let nextId = 0, seq = 0;
const now = () => Date.now() / 1000;
// Optional synthetic seed records, loaded from the showcase's own fixtures/ folder.
const seedName = q.get('seed');
if (seedName) {
  const f = bundle.files.find(x => x.path === `fixtures/${seedName}.json`);
  for (const r of JSON.parse(f.text)) rows.set(key(r.collection, r.id), {rev: 1, source: null, created_at: now(), updated_at: now(), updated_by: 'fixture', ...r});
}
window.harness = {rows, calls: []};
const ok = result => ({ok: true, result: structuredClone(result)});
const err = (code, message, extra = {}) => ({ok: false, error: {code, message, ...extra}});
async function call(op, args) {
  harness.calls.push(op);
  if (op === 'log') return ok({stored: args.entries.length});
  if (op === 'net.fetch') {
    if (netOff) return err('not_granted', 'Internet access is off for this Space');
    return (await fetch('/net', {method: 'POST', body: JSON.stringify(args)})).json();
  }
  if (op === 'data.query') {
    const records = [...rows.values()].filter(r => r.collection === args.collection);
    return ok({records: records.slice(args.offset || 0, (args.offset || 0) + (args.limit || 500)), total: records.length, seq});
  }
  if (op === 'data.get') { const r = rows.get(key(args.collection, args.id)); return r ? ok(r) : err('not_found', 'missing'); }
  if (op === 'data.put') {
    const cur = rows.get(key(args.collection, args.id));
    if (cur && cur.rev !== args.base_rev) return err('conflict', 'conflict', {current: structuredClone(cur)});
    const r = {...cur, collection: args.collection, id: args.id || `r${++nextId}`, data: {...(args.merge ? cur?.data : {}), ...args.data}, rev: (cur?.rev || 0) + 1, updated_at: now()};
    rows.set(key(r.collection, r.id), r); return ok(r);
  }
  if (op === 'data.delete') { rows.delete(key(args.collection, args.id)); return ok({deleted: true}); }
  if (op === 'data.batch') { const out = []; for (const o of args.ops) { const r = await call(o.op === 'put' ? 'data.put' : 'data.delete', o); if (!r.ok) return r; out.push(r.result); } return ok(out); }
  if (op === 'runs.list') return ok([]);
  if (op === 'meta') return ok({space: bundle.space, grants: ['data', 'logs', 'net'], limits: {}});
  return err('invalid', 'Unsupported: ' + op);
}
mountSpace(document.getElementById('space'), {bundle, grants: ['data', 'logs', 'net'], call});
