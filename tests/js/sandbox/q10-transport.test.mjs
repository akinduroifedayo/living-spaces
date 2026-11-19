import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { spaceLoader, projectResolver } from '../../../src/guest/loader.mjs'
import { checkGrant, validateRequest } from '../../../src/desktop/sandbox/index.js'
import { createSpaceSession } from '../../../src/desktop/ui/session.mjs'

function guest() {
  const events = new Map(), messages = [], parent = {}
  const element = () => ({attributes:[],style:{},children:[],setAttribute(){},append(...nodes){this.children.push(...nodes)},replaceChildren(){}})
  const document = {head:element(),body:element(),documentElement:element(),createElement:element,querySelector(){return null},addEventListener:(name,fn)=>events.set(name,fn)}
  const window = {parent,addEventListener:(name,fn)=>events.set(name,fn),removeEventListener:name=>events.delete(name)}
  const port = {postMessage:message=>messages.push(structuredClone(message)),close(){}}
  const DOMParser = class {parseFromString(){return {title:'',documentElement:element(),head:{childNodes:[]},body:{attributes:[],childNodes:[]},querySelectorAll(){return []}}}}
  const context=vm.createContext({window,document,DOMParser,Map,Set,Error,TypeError,Promise,Object,JSON,String,Uint8Array,Blob,URL,atob,console:{log(){},warn(){},error(){}},setInterval(){},clearInterval(){}})
  vm.runInContext(`(${spaceLoader.toString()})((${projectResolver.toString()})())`,context)
  events.get('message')({source:parent,data:{type:'space-boot',v:1,grants:['data'],bundle:{space:{id:'q10',name:'Q10'},rev:1,manifest:{},files:[{path:'index.html',text:'Q10'}]}},ports:[port]})
  return {api:window.space,port,messages}
}

test('Q10 guest carries editor request identity and typed unknown outcome without claiming save', async () => {
  const f=guest()
  assert.equal(typeof f.api.editor?.save,'function')
  const key={editor:'note',schema:1,collection:'papers',id:'one'}
  const pending=f.api.editor.save({...key,data:{note:'mine'},base_rev:2,request_id:'q10-wire'})
  assert.deepEqual(f.messages[0],{v:1,id:1,op:'editor.save',args:{...key,data:{note:'mine'},base_rev:2},request_id:'q10-wire'})
  f.port.onmessage({data:{v:1,id:1,ok:false,error:{code:'conflict',message:'Uncertain'},outcome:{status:'unknown'}}})
  await assert.rejects(pending,error=>error.outcome.status==='unknown')
  const lookup=f.api.editor.outcome({...key,request_id:'q10-wire'})
  assert.equal(f.messages[1].op,'outcome.get')
  f.port.onmessage({data:{v:1,id:2,ok:true,result:{found:true},outcome:{status:'success'}}})
  assert.equal((await lookup).found,true)
})

test('Q10 guest recovery operations reject old-session replies and future calls', async () => {
  const f=guest()
  assert.equal(typeof f.api.drafts?.get,'function')
  const pending=f.api.drafts.get({editor:'note',schema:1,collection:'papers',id:'one'})
  f.port.onmessage({data:{v:1,type:'event',event:'session.closed',payload:{reason:'closed'}}})
  f.port.onmessage({data:{v:1,id:1,ok:true,result:{draft:{value:'wrong session'}}}})
  await assert.rejects(pending,error=>error.code==='session_invalid')
  await assert.rejects(f.api.drafts.put({}),error=>error.code==='session_invalid')
  assert.equal(f.messages.length,1)
})

test('Q10 sandbox gates draft and editor operations on data and requires save identity', () => {
  for(const op of ['draft.get','draft.put','draft.delete','editor.save','outcome.get']) {
    assert.equal(checkGrant(op,['data']),null,op)
    assert.equal(checkGrant(op,[]).code,'not_granted')
  }
  assert.match(validateRequest({v:1,id:1,op:'editor.save',args:{}}),/request_id/)
  assert.equal(validateRequest({v:1,id:1,op:'editor.save',args:{},request_id:'q10-valid'}),null)
})

test('Q10 host tracks editor writes with supplied identity and app-owned recovery', async t => {
  const writes=[],requests=[]
  let mounted
  const session=createSpaceSession({sid:'q10',container:{},onEvent(){},onWrite:write=>writes.push(write),
    mount:(_,value)=>{mounted=value;return {destroy(){}}},
    rest:async(path,options={})=>{
      if(path.endsWith('/sessions')) return {session:'live',head_rev:1,grants:['data']}
      if(path.endsWith('/bundle')) return {rev:1}
      if(path.endsWith('/bridge')) {requests.push(options.body);return {ok:false,error:{code:'conflict',current:{rev:9}},outcome:{status:'rejected'}}}
      return {closed:true}
    }})
  t.after(()=>session.destroy())
  await session.ready
  await mounted.call('editor.save',{editor:'note',schema:1,collection:'papers',id:'one',data:{note:'mine'},base_rev:1},undefined,'q10-host')
  assert.equal(requests[0].request_id,'q10-host')
  assert.equal(writes.at(-1).status,'conflict')
  assert.equal(writes.at(-1).editorManaged,true)
})

test('Q10 host conflict banner delegates to editor without contradictory recovery actions', () => {
  const source=readFileSync('src/desktop/ui/space.jsx','utf8')+'\nexport {WriteBanner};'
  const compiled=execFileSync('esbuild',['--loader=jsx','--format=cjs','--jsx=automatic'],{input:source,encoding:'utf8'})
  const module={exports:{}}
  const components={Banner:props=>props,Action:props=>props}
  const imports=name=>name==='react/jsx-runtime' ? {jsx:(type,props)=>({type,props}),jsxs:(type,props)=>({type,props})} : name==='./components.jsx' ? components : name==='./model.mjs' ? {errorText:()=>''} : {}
  new Function('require','module','exports',compiled)(imports,module,module.exports)
  const result=module.exports.WriteBanner({write:{editorManaged:true,status:'conflict',op:'editor.save',args:{},reply:{error:{current:{rev:9}}}}})
  assert.match(result.props.children,/app editor/)
  assert.equal(result.props.actions,undefined)
})
