import sys,json,sqlite3,time,hashlib,subprocess
from pathlib import Path
ROOT=Path('/Volumes/Expansion/Development/Projects/living-spaces'); sys.path.insert(0,str(ROOT/'harness'))
from cdp import evaluate,screenshot
out=ROOT/'docs/design/premium-pass/regeneration'
submission=json.loads((out/'sky-window-submission.json').read_text()); since=submission['started_at']; sid=submission['session']
def connect(path):
 c=sqlite3.connect('file:'+path+'?mode=ro',uri=True); c.row_factory=sqlite3.Row; return c
state=connect('/Volumes/Expansion/Development/Build/living-spaces-r1/home/state.db')
trace=[dict(r) for r in state.execute('select role,content,tool_calls,tool_call_id,tool_name,timestamp,finish_reason from messages where session_id=? and timestamp>=? order by timestamp',(sid,since))]
(out/'sky-window-trace.json').write_text(json.dumps(trace,indent=2))
ui=evaluate('document.body.innerText.slice(-2200)').split('Scroll to bottom')[0]; (out/'sky-window-host-message.txt').write_text(ui)
import asyncio,base64
from cdp import _page
async def capture(s):
 size=await s.call('Runtime.evaluate',expression='({width:innerWidth,height:innerHeight})',returnByValue=True)
 size=size['result']['value']
 image=await s.call('Page.captureScreenshot',format='png',clip={'x':0,'y':0,'width':size['width'],'height':size['height']-32,'scale':1})
 (out/'sky-window-provider-blocked.png').write_bytes(base64.b64decode(image['data']))
 return size
viewport=asyncio.run(_page(capture))
store=connect('/Volumes/Expansion/Development/Build/living-spaces-r1/home/plugin-data/living-spaces/spaces.db')
before=json.loads((out/'sky-window-before.json').read_text())
after={table:[dict(r) for r in store.execute('select * from '+table+' where '+('id' if table=='spaces' else 'space')+'=?',('sky-window',))] for table in before}
(out/'sky-window-after.json').write_text(json.dumps(after,indent=2))
heads=[dict(r) for r in store.execute('select id,name,head_rev from spaces where id in (?,?,?)',('sky-window','research-desk','pair-play'))]
skill=ROOT/'src/living-spaces/skills/build-space/SKILL.md'
checks={'exact_user_prompt_recorded_once':sum(r['role']=='user' and r['content']==submission['prompt'] for r in trace)==1,'host_reports_rate_limit':'rate limit' in ui,'host_reports_request_not_processed':'Your request was not processed' in ui,'no_tools_called':not any(r['tool_calls'] or r['role']=='tool' for r in trace),'sky_records_revisions_grants_unchanged':before==after}
receipt={'captured_at':time.time(),'status':'blocked-provider-rate-limit','checks':checks,'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'branch':subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),'cdp':'http://127.0.0.1:9341','hermes_home':'/Volumes/Expansion/Development/Build/living-spaces-r1/home','skill_disk_sha256':hashlib.sha256(skill.read_bytes()).hexdigest(),'loaded_skill_evidence':'none; provider rejected request before any tool call','space_heads':heads,'research_desk_prompt_sent':False,'pair_play_prompt_sent':False,'live_functional_checks':'not reached; no regenerated artifact','provider_change':False,'gateway_restart':False,'data_provenance':'existing generic isolated demo data only; no fresh external data fetched in this attempt','source_memory_hash_attestation':'not available; no backend restart performed'}
receipt['artifacts']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file() and p.name!='blocker-receipt.json'}
(out/'blocker-receipt.json').write_text(json.dumps(receipt,indent=2)); print(json.dumps(receipt,indent=2))
assert all(checks.values()),checks
