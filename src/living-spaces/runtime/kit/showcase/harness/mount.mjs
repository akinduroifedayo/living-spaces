import {mountSpace} from '/src/desktop/sandbox/index.js';
const q=new URL(location.href).searchParams,name=q.get('name')||'sky-window';
const bundle=await(await fetch('/bundle?name='+encodeURIComponent(name))).json();
// Faults are test controls in the outer verifier, never declared live data or host permissions.
const h=window.harness={calls:[],fail:q.get('fault')||'',delay:Number(q.get('delay'))||0,events:[]};
const ok=result=>({ok:true,result}),err=(code,message)=>({ok:false,error:{code,message}});
async function call(op,args){
 h.calls.push({op,args,time:Date.now()});
 if(h.delay)await new Promise(r=>setTimeout(r,h.delay));
 if(op==='log')return ok({stored:args.entries.length});
 if(op==='net.fetch'){
  if(h.fail==='net')return err('unavailable','Injected network failure');
  if(h.fail==='off')return err('not_granted','Injected Internet-off response');
  if(h.fail==='empty')return ok({status:200,json:{current:{},daily:{time:[]}}});
  if(h.fail==='invalid')return ok({status:200,json:{}});
  return(await fetch('/net',{method:'POST',body:JSON.stringify(args)})).json();
 }
 if(op==='data.get'&&h.fail==='get')return err('unavailable','Injected composition load failure');
 if(op==='data.get'&&h.fail==='missing')return err('not_found','Injected missing composition');
 if(op==='data.query'&&h.fail==='query')return err('unavailable','Injected scorecard load failure');
 if(op==='data.put'&&h.fail==='save')return err('unavailable','Injected save failure');
 if(['data.query','data.put','data.get'].includes(op))return(await fetch('/records?name='+encodeURIComponent(name),{method:'POST',body:JSON.stringify({op,args})})).json();
 if(op==='runs.list')return ok([]);
 if(op==='meta')return ok({space:bundle.space,grants:['data','logs','net'],limits:{}});
 return err('invalid','Unsupported reference operation');
}
h.instance=mountSpace(document.getElementById('space'),{bundle,grants:['data','logs','net'],call,onEvent:e=>h.events.push(e)});
