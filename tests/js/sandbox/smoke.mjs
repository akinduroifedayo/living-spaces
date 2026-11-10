import { mountSpace } from '../../../src/desktop/sandbox/index.js'

const bundle = await (await fetch('/bundle')).json()
const record = { collection: 'papers', id: 'demo', data: { note: 'Initial public note' }, source: { title: 'Public research fixture' }, rev: 1 }
const records = new Map([['demo', record]])
let seq = 0
let runSeq = 0
const runs = []
const changes = changes => window.smoke.mount.postEvent('data.changed', { seq: ++seq, changes })
window.smoke = {
  events: [], calls: [], logs: [], records, runs,
  denyRefresh: false,
  agentWrite() { record.rev++; record.data.note = 'Updated by demo chat'; changes([{ collection: 'papers', id: 'demo', op: 'put', rev: record.rev }]) },
  run(status) {
    const update = { id: 'demo-run-' + runSeq, status, error: status === 'failed' ? 'Demo fetch failed' : null }
    window.smoke.mount.postEvent('run.updated', update)
  }
}
async function call(op, args) {
  smoke.calls.push({ op, args, at: performance.now() })
  if (op === 'log') { smoke.logs.push(...args.entries); return { ok: true, result: { stored: args.entries.length } } }
  if (op === 'data.query') return { ok: true, result: { records: [...records.values()], total: records.size, seq } }
  if (op === 'data.get') return records.has(args.id) ? { ok: true, result: records.get(args.id) } : { ok: false, error: { code: 'not_found', message: 'Record not found' } }
  if (op === 'data.put') {
    await new Promise(resolve => setTimeout(resolve, 180))
    const current = records.get(args.id)
    if (current && current.rev !== args.base_rev) return { ok: false, error: { code: 'conflict', message: 'This record changed elsewhere', current: structuredClone(current) } }
    const updated = current || { collection: args.collection, id: args.id || 'new-demo', data: {}, source: null, rev: 0 }
    updated.data = { ...updated.data, ...args.data }; updated.rev++
    records.set(updated.id, updated)
    changes([{ collection: args.collection, id: updated.id, op: 'put', rev: updated.rev }])
    return { ok: true, result: updated }
  }
  if (op === 'data.delete') { records.delete(args.id); return { ok: true, result: { deleted: true } } }
  if (op === 'data.batch') return { ok: true, result: { results: args.ops.map(() => ({ deleted: true })), seq } }
  if (op === 'runs.list') return { ok: true, result: runs }
  if (op === 'refresh') {
    if (smoke.denyRefresh) return { ok: false, error: { code: 'not_granted', message: 'Refresh is not granted', capability: 'refresh' } }
    const run = { id: 'demo-run-' + ++runSeq, status: 'queued' }
    runs.push(run)
    return { ok: true, result: run }
  }
  return { ok: true, result: { space: bundle.space, grants: ['data', 'logs', 'refresh'], limits: {} } }
}
smoke.mount = mountSpace(document.getElementById('space'), { bundle, grants: ['data', 'logs', 'refresh'], call, onEvent: e => smoke.events.push(e) })
