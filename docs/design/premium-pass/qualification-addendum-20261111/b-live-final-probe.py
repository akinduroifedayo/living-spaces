import asyncio,json,importlib.util,datetime
spec=importlib.util.spec_from_file_location('a','/Volumes/Expansion/Development/Build/r1-qualification-t_b3b306df/addendum/b-live-audit.py');a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
async def ready():
 for i in range(25):
  r=await a.guest(a.GSTATE)
  if r is not None:return r
  await asyncio.sleep(.2)
async def main():
 orig=json.loads((a.OUT/'b-live-evidence.json').read_text())['original'];out={}
 async with a.websockets.connect(a.page_ws(),max_size=64<<20) as ws:
  s=a.S(ws)
  try:
   for slug in ['research-desk','sky-window','pair-play']:
    await a.nav(s,slug);await ready()
    out[slug]={}
    await a.clicktext(s,'History');await a.clicktext(s,'Revisions')
    out[slug]['currentRevision']=await a.ev(s,"document.querySelector('[role=dialog]')?.innerText.match(/Revision \\d+\\nCurrent/)?.[0]")
    await a.key(s,'Escape')
    await a.clicktext(s,'Permissions')
    out[slug]['grants']=await a.ev(s,"({switches:[...document.querySelectorAll('[role=dialog] [role=switch]')].map(e=>({label:e.getAttribute('aria-label'),labelledby:e.getAttribute('aria-labelledby'),checked:e.getAttribute('aria-checked'),rect:e.getBoundingClientRect().toJSON()})),text:document.querySelector('[role=dialog]')?.innerText})")
    await a.key(s,'Escape')
    out[slug]['semantics']=await a.guest("({controls:[...document.querySelectorAll('button,input,a,summary')].filter(e=>e.getBoundingClientRect().width>0).map(e=>({tag:e.tagName,text:e.innerText?.slice(0,80),aria:e.getAttribute('aria-label'),labelledby:e.getAttribute('aria-labelledby'),labels:[...(e.labels||[])].map(l=>l.innerText),rect:e.getBoundingClientRect().toJSON()})),motion:[...document.styleSheets].flatMap(s=>{try{return [...s.cssRules].filter(r=>r.cssText.includes('prefers-reduced-motion')).map(r=>r.cssText)}catch(e){return ['inaccessible stylesheet']}}),animations:document.getAnimations().map(a=>({playState:a.playState,timing:a.effect?.getTiming()}))})")
    for t in a._targets():
     if t['type']=='iframe':
      async with a.websockets.connect(t['webSocketDebuggerUrl'],max_size=64<<20) as fw:
       fs=a.S(fw);tree=(await fs.call('Page.getFrameTree'))['frameTree'];fid=tree['childFrames'][0]['frame']['id']
       ax=(await fs.call('Accessibility.getFullAXTree',frameId=fid))['nodes'];out[slug]['ax']=[{'role':n.get('role',{}).get('value'),'name':n.get('name',{}).get('value'),'ignored':n.get('ignored')} for n in ax if n.get('role',{}).get('value') in ['button','link','textbox','searchbox','heading','DisclosureTriangle']]
    out[slug]['focus']=await a.guest("(()=>{let e=[...document.querySelectorAll('a,button')].find(e=>e.getBoundingClientRect().width>0);e?.focus();let s=e?getComputedStyle(e):null;return {tag:e?.tagName,text:e?.innerText?.slice(0,80),active:document.activeElement===e,outline:s?.outline,boxShadow:s?.boxShadow}})()")
  finally:
   await a.key(s,'Escape');await s.call('Emulation.clearDeviceMetricsOverride');await a.nav(s,'research-desk');await ready()
   await a.guest('location.hash='+json.dumps(orig['guest']['hash']));await asyncio.sleep(.2)
   await a.guest("(()=>{let e=document.querySelector('input[type=search]');if(e){e.value="+json.dumps(orig['guest']['search'])+";e.dispatchEvent(new Event('input',{bubbles:true}));}scrollTo(0,0)})()")
   await a.ev(s,'scrollTo(0,0)');await asyncio.sleep(.3)
   out['restored']=await a.ev(s,a.STATE);out['restored']['guest']=await a.guest(a.GSTATE);out['restorationEqual']=out['restored']==orig;out['time']=datetime.datetime.now().astimezone().isoformat()
   first=json.loads((a.OUT/'b-live-evidence.json').read_text())['b-live-permissions']['dialogs'][0]['text'];out['researchGrantsTextUnchanged']=first==out.get('research-desk',{}).get('grants',{}).get('text')
   (a.OUT/'b-live-final-receipt.json').write_text(json.dumps(out,indent=2))
   for slug in ['research-desk','sky-window','pair-play']:
    d=out.get(slug,{});print(slug,json.dumps({'rev':d.get('currentRevision'),'ax':d.get('ax'),'motion':d.get('semantics',{}).get('motion'),'focus':d.get('focus')}))
   print('RESTORE',out['restorationEqual'],'grantsTextSame',out['researchGrantsTextUnchanged'],out['time'])
asyncio.run(main())
