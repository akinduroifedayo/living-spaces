exec(compile(open('/Volumes/Expansion/Development/Build/r1-qualification-t_b3b306df/addendum/b-live-audit.py').read(), 'audit', 'exec'),globals()|{'__name__':'imported'})
# Import by module spec so helper globals share the evidence log.
import importlib.util,asyncio,json,sys
from pathlib import Path
import websockets
sys.path.insert(0,'/Volumes/Expansion/Development/Projects/living-spaces/harness')
from cdp import page_ws,_targets
OUT=Path('/Volumes/Expansion/Development/Build/r1-qualification-t_b3b306df/addendum')
spec=importlib.util.spec_from_file_location('audit','/Volumes/Expansion/Development/Build/r1-qualification-t_b3b306df/addendum/b-live-audit.py');a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
async def ready():
 for _ in range(20):
  g=await a.guest(a.GSTATE)
  if g is not None:return g
  await asyncio.sleep(.25)
 return None
async def main2():
 orig=json.loads((OUT/'b-live-evidence.json').read_text())['original']
 async with websockets.connect(page_ws(),max_size=64<<20) as ws:
  s=a.S(ws)
  try:
   await ready()
   # Restore pre-audit local search before subsequent checks.
   await a.guest('location.hash='+json.dumps(orig['guest']['hash']));await asyncio.sleep(.2)
   await a.guest("(()=>{let e=document.querySelector('input[type=search]');if(e){e.value='attention';e.dispatchEvent(new Event('input',{bubbles:true}));}})()")
   await a.clicktext(s,'History');await a.clicktext(s,'Revisions');await a.capture(s,'b-live-revisions');await a.key(s,'Escape')
   await a.clicktext(s,'Permissions');await a.capture(s,'b-live-permissions-after')
   await s.call('Emulation.setDeviceMetricsOverride',width=390,height=844,deviceScaleFactor=1,mobile=False);await asyncio.sleep(.3);await a.capture(s,'b-live-permissions-390');await a.key(s,'Escape');await s.call('Emulation.clearDeviceMetricsOverride')
   for slug in ['sky-window','pair-play','research-desk']:
    await a.nav(s,slug);await ready()
    for width in [900,390,320]:
     await s.call('Emulation.setDeviceMetricsOverride',width=width,height=844,deviceScaleFactor=1,mobile=False);await asyncio.sleep(.2)
     await a.capture(s,'b-live-'+slug+'-ready-'+str(width))
    # AX names only for generated document; avoid gameplay or save controls.
    for t in _targets():
     if t['type']=='iframe':
      async with websockets.connect(t['webSocketDebuggerUrl'],max_size=64<<20) as fw:
       fs=a.S(fw);ax=(await fs.call('Accessibility.getFullAXTree'))['nodes']
       a.LOG[slug+'-ax']=[{'role':n.get('role',{}).get('value'),'name':n.get('name',{}).get('value'),'ignored':n.get('ignored')} for n in ax if n.get('role',{}).get('value') in ['button','link','textbox','searchbox','heading']]
    await s.call('Emulation.clearDeviceMetricsOverride')
  finally:
   await a.key(s,'Escape');await s.call('Emulation.clearDeviceMetricsOverride');await a.nav(s,'research-desk');await ready()
   await a.guest('location.hash='+json.dumps(orig['guest']['hash']));await asyncio.sleep(.3)
   await a.guest("(()=>{let e=document.querySelector('input[type=search]');if(e){e.value="+json.dumps(orig['guest']['search'])+";e.dispatchEvent(new Event('input',{bubbles:true}));}scrollTo(0,0)})()")
   await a.ev(s,'scrollTo(0,0)');await asyncio.sleep(.3)
   a.LOG['restored']=await a.ev(s,a.STATE);a.LOG['restored']['guest']=await a.guest(a.GSTATE);a.LOG['restorationEqual']=a.LOG['restored']==orig
   (OUT/'b-live-followup.json').write_text(json.dumps(a.LOG,indent=2));print('FINAL RESTORE',json.dumps(a.LOG['restored']),a.LOG['restorationEqual'])
asyncio.run(main2())
