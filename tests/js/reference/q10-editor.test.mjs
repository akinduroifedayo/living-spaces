import test from 'node:test'
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { mkdtempSync, rmSync } from 'node:fs'
import { resolve } from 'node:path'
import { setImmediate as tick } from 'node:timers/promises'
import { h, render, options } from 'preact'
import * as kit from '../../../src/living-spaces/runtime/kit/spaces-kit.mjs'

options.requestAnimationFrame = callback => queueMicrotask(callback)
options.debounceRendering = callback => queueMicrotask(callback)
const python = '/Users/ifedayoakinduro/.hermes/hermes-agent/venv/bin/python'
function fixture(t) {
  assert.equal(typeof kit.createEditorStore, 'function', 'Q10 editor lifecycle helper is missing')
  const dir = mkdtempSync(resolve('.run/swarm-03/q10/tmp/editor-'))
  const env = { PATH: process.env.PATH, HOME: dir, TMPDIR: dir, HERMES_HOME: dir, LIVING_SPACES_DB: resolve(dir, 'db.sqlite') }
  const run = code => JSON.parse(execFileSync(python, ['-I', '-B', '-c', `import sys,json; sys.path.insert(0,${JSON.stringify(resolve('src/living-spaces'))}); from living_spaces_core import bridge,projects,records,sessions; ${code}`], {env, encoding: 'utf8'}))
  const opened = run("s=projects.create_space('Q10',owner='fixture',author='fixture',files={'index.html':'Q10'}); print(json.dumps({'sid':s['id'],'session':sessions.open_session(s['id'])['session']}))")
  let session = opened.session
  const requests = [], listeners = new Set()
  let gate = null
  const dispatch = (op, args, requestId) => run(`print(json.dumps(bridge.dispatch(${JSON.stringify(opened.sid)},${JSON.stringify(session)},${JSON.stringify(op)},json.loads(${JSON.stringify(JSON.stringify(args))}),${requestId ? JSON.stringify(requestId) : 'None'})))`)
  const call = async (op, args) => {
    requests.push({op, args: structuredClone(args)})
    const {request_id, ...clean} = args
    const reply = dispatch(op, clean, op === 'editor.save' ? request_id : undefined)
    if (gate && op === 'editor.save') await gate()
    if (!reply.ok) throw Object.assign(new Error(reply.error.message), reply.error, {outcome: reply.outcome})
    return reply.result
  }
  const api = { get: (collection,id) => call('data.get',{collection,id}), on(event, cb) { listeners.add(cb); return () => listeners.delete(cb) },
    drafts: Object.fromEntries(['get','put','delete'].map(name => [name, args => call('draft.' + name, args)])),
    editor: { save: args => call('editor.save', args), outcome: args => { const {request_id,...key}=args; return call('outcome.get',{...key,request_id}) } } }
  // outcome.get's request ID is an argument, whereas writes carry it on the envelope.
  api.editor.outcome = async args => {
    requests.push({op:'outcome.get',args:structuredClone(args)})
    const reply=dispatch('outcome.get',args)
    if (!reply.ok) throw Object.assign(new Error(reply.error.message),reply.error,{outcome:reply.outcome})
    return reply.result
  }
  const store = kit.createEditorStore(api)
  t.after(() => { store.destroy(); rmSync(dir, {recursive:true,force:true}) })
  const key = {editor:'notes',schema:1,collection:'papers',id:'one',record:null,initial:{note:''},validate:value => value.note.trim() ? null : 'Note required'}
  return {store,api,key,requests,run,dispatch,
    emit(change) { for (const cb of listeners) cb({changes:[change]}) },
    setGate(fn) { gate=fn },
    reopen() { run(`sessions.close_session(${JSON.stringify(session)}); print('null')`); session=run(`print(json.dumps(sessions.open_session(${JSON.stringify(opened.sid)})['session']))`); return kit.createEditorStore(api) } }
}

test('Q10 validation duplicate activation and confirmed clearing use the real store', async t => {
  const f=fixture(t), e=f.store.editor(f.key)
  await e.ready
  assert.equal(await e.save(), undefined)
  assert.equal(e.snapshot.validation, 'Note required')
  assert.equal(f.requests.filter(r=>r.op==='editor.save').length,0)
  e.setValue({note:'mine'})
  let release
  f.setGate(()=>new Promise(resolve=>{release=resolve}))
  const pending=e.save(), duplicate=e.save()
  await tick()
  assert.equal(e.snapshot.state,'saving')
  assert.deepEqual(e.snapshot.inFlight.data,{note:'mine'})
  assert.equal(f.requests.filter(r=>r.op==='editor.save').length,1)
  release(); await pending; await duplicate
  assert.equal(e.snapshot.state,'saved')
  assert.equal(e.snapshot.dirty,false)
  assert.equal(e.snapshot.confirmed.rev,1)
  assert.equal((await f.api.drafts.get({...f.key,record:undefined,initial:undefined,validate:undefined})).draft,null)
})

test('Q10 broadcast and route or filter unmount preserve the original base and draft', async t => {
  const f=fixture(t)
  assert.equal(typeof kit.useEditor,'function')
  let value
  const container={nodeType:1,childNodes:[]}
  function View(){value=kit.useEditor(f.store,f.key);return null}
  render(h(View),container); await value.ready; await tick()
  value.setValue({note:'unsaved'}); await tick()
  f.emit({collection:'other',id:'one',rev:8}); assert.equal(value.behind,false)
  f.emit({collection:'papers',id:'one',rev:9}); await tick()
  assert.equal(value.baseRev,0); assert.equal(value.behind,true)
  render(null,container)
  render(h(View),container); await tick()
  assert.deepEqual(value.value,{note:'unsaved'}); assert.equal(value.baseRev,0)
  render(null,container)
})

test('Q10 two writers require deliberate conflict choices and lock failed payloads', async t => {
  const f=fixture(t), e=f.store.editor(f.key)
  await e.ready; e.setValue({note:'mine'}); await e.save()
  e.setValue({note:'retained'})
  const current=f.dispatch('data.put',{collection:'papers',id:'one',data:{note:'chat'},base_rev:1}).result
  f.emit({collection:'papers',id:'one',rev:current.rev})
  await e.save()
  assert.equal(e.snapshot.state,'conflict'); assert.equal(e.snapshot.baseRev,1)
  assert.deepEqual(e.snapshot.failedPayload.data,{note:'retained'})
  e.setValue({note:'hidden replacement'}); assert.equal(e.snapshot.value.note,'retained')
  assert.equal(f.requests.filter(r=>r.op==='editor.save').length,2)
  await e.keepMine()
  assert.equal(e.snapshot.state,'saved'); assert.equal(e.snapshot.confirmed.rev,3)
  e.setValue({note:'discard me'})
  f.dispatch('data.put',{collection:'papers',id:'one',data:{note:'updated'},base_rev:3})
  await e.save(); await e.useUpdated()
  assert.equal(e.snapshot.value.note,'updated'); assert.equal(e.snapshot.dirty,false)
  assert.equal((await f.api.drafts.get({editor:'notes',schema:1,collection:'papers',id:'one'})).draft,null)
})

test('Q10 reopen recovers unsaved draft and explicit discard clears host recovery', async t => {
  const f=fixture(t), e=f.store.editor(f.key)
  await e.ready; e.setValue({note:'reopen draft'}); await e.flush()
  f.store.destroy()
  const next=f.reopen(); t.after(()=>next.destroy())
  const recovered=next.editor(f.key); await recovered.ready
  assert.equal(recovered.snapshot.value.note,'reopen draft'); assert.equal(recovered.snapshot.dirty,true)
  assert.equal(recovered.snapshot.recovery,'durable')
  await recovered.discard()
  const third=kit.createEditorStore(f.api); t.after(()=>third.destroy())
  const fresh=third.editor(f.key); await fresh.ready
  assert.equal(fresh.snapshot.value.note,''); assert.equal(fresh.snapshot.dirty,false)
})

test('Q10 late save results cannot update a destroyed Space session', async t => {
  const f=fixture(t), e=f.store.editor(f.key)
  await e.ready; e.setValue({note:'old session'})
  let release
  f.setGate(()=>new Promise(resolve=>{release=resolve}))
  const pending=e.save(); await tick(); f.store.destroy(); release(); await pending
  assert.equal(e.snapshot.confirmed,null)
  assert.notEqual(e.snapshot.state,'saved')
})

test('Q10 unknown outcomes reconcile proof without replay and failures retain exact payload', async t => {
  const f=fixture(t)
  let lost=true
  f.setGate(()=>{if(lost){lost=false;throw Object.assign(new Error('Lost after commit'),{outcome:{status:'unknown'}})}})
  const e=f.store.editor(f.key); await e.ready; e.setValue({note:'confirmed by receipt'}); await e.save()
  assert.equal(e.snapshot.state,'unknown'); assert.equal(e.snapshot.dirty,true)
  await e.retry()
  assert.equal(e.snapshot.state,'saved'); assert.equal(e.snapshot.dirty,false)
  assert.equal(f.requests.filter(r=>r.op==='editor.save').length,1)
  const rejected=kit.createEditorStore({...f.api,editor:{...f.api.editor,save:async()=>{throw Object.assign(new Error('busy'),{outcome:{status:'busy'}})}}})
  t.after(()=>rejected.destroy())
  const fail=rejected.editor({...f.key,id:'two'}); await fail.ready; fail.setValue({note:'failed exact'}); await fail.save()
  assert.equal(fail.snapshot.state,'failed'); fail.setValue({note:'newer'})
  assert.equal(fail.snapshot.value.note,'failed exact'); assert.equal(fail.snapshot.failedPayload.data.note,'failed exact')
})

test('Q10 unavailable host recovery is explicit and retains an in-memory route draft', async t => {
  const f=fixture(t), store=kit.createEditorStore({...f.api,drafts:undefined})
  t.after(()=>store.destroy())
  const e=store.editor(f.key); await e.ready; e.setValue({note:'memory only'}); await e.flush()
  assert.equal(e.snapshot.recovery,'memory')
  assert.match(e.snapshot.recoveryMessage,/unavailable|memory/i)
  assert.equal(store.editor(f.key).snapshot.value.note,'memory only')
})
