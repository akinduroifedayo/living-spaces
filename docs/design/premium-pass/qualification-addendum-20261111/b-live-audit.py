import sys,asyncio,json,base64,hashlib,re,datetime
from pathlib import Path
sys.path.insert(0,'/Volumes/Expansion/Development/Projects/living-spaces/harness')
from cdp import Session,page_ws,_targets
import websockets
OUT=Path('/Volumes/Expansion/Development/Build/r1-qualification-t_b3b306df/addendum')
LOG={}
class S(Session):
 async def call(self,method,**params):
  self.n+=1;await self.ws.send(json.dumps({'id':self.n,'method':method,'params':params}))
  while True:
   m=json.loads(await self.ws.recv())
   if m.get('method')=='Debugger.scriptParsed': scripts.append(m['params'])
   if m.get('id')==self.n:
    if 'error' in m: raise RuntimeError(m['error'])
    return m['result']
scripts=[]
async def ev(s,e,ctx=None):
 a={'expression':e,'returnByValue':True,'awaitPromise':True}
 if ctx:a['contextId']=ctx
 r=await s.call('Runtime.evaluate',**a)
 if r.get('exceptionDetails'):raise RuntimeError(str(r['exceptionDetails']))
 return r.get('result',{}).get('value')
async def guest(e):
 for t in _targets():
  if t['type']=='iframe':
   async with websockets.connect(t['webSocketDebuggerUrl'],max_size=64<<20) as ws:
    s=S(ws);tree=(await s.call('Page.getFrameTree'))['frameTree'];kids=tree.get('childFrames',[])
    if not kids:continue
    ctx=(await s.call('Page.createIsolatedWorld',frameId=kids[0]['frame']['id'],worldName='b-live-readonly'))['executionContextId']
    return await ev(s,e,ctx)
STATE="({hash:location.hash,w:innerWidth,h:innerHeight,scroll:[scrollX,scrollY],theme:document.documentElement.className,dialogs:document.querySelectorAll('[role=dialog]').length})"
GSTATE="({hash:location.hash,scroll:[scrollX,scrollY],search:document.querySelector('input[type=search]')?.value})"
FOCUS="(()=>{let e=document.activeElement;return {tag:e?.tagName,text:e?.innerText?.slice(0,80),label:e?.getAttribute('aria-label'),inDialog:!!e?.closest('[role=dialog]'),outline:e?getComputedStyle(e).outline:null}})()"
async def key(s,k,shift=False):
 for typ in ['keyDown','keyUp']:await s.call('Input.dispatchKeyEvent',type=typ,key=k,code=k,windowsVirtualKeyCode={'Tab':9,'Escape':27}.get(k,0),modifiers=8 if shift else 0)
 await asyncio.sleep(.12)
async def clicktext(s,text):
 r=await ev(s,"(()=>{let e=[...document.querySelectorAll('.ls-root button,[role=dialog] button')].find(e=>e.innerText.trim()==="+json.dumps(text)+");return e?.getBoundingClientRect().toJSON()})()")
 if not r:raise RuntimeError('missing '+text)
 for typ in ['mousePressed','mouseReleased']:await s.call('Input.dispatchMouseEvent',type=typ,x=r['x']+r['width']/2,y=r['y']+r['height']/2,button='left',clickCount=1)
 await asyncio.sleep(.4)
async def capture(s,name):
 d=await ev(s,"(()=>{let root=document.querySelector('.ls-root');let rect=e=>({text:e.innerText?.slice(0,160),label:e.getAttribute('aria-label'),rect:e.getBoundingClientRect().toJSON(),scrollWidth:e.scrollWidth,clientWidth:e.clientWidth});return {w:innerWidth,h:innerHeight,docW:document.documentElement.scrollWidth,root:root?.getBoundingClientRect().toJSON(),header:document.querySelector('.ls-framebar')?.innerText,elements:[...root.querySelectorAll('button,h1,h2,.ls-identity,.ls-framebar,.ls-card')].map(rect),dialogs:[...document.querySelectorAll('[role=dialog]')].map(e=>({text:e.innerText.slice(0,9000),label:e.getAttribute('aria-labelledby'),modal:e.getAttribute('aria-modal'),rect:e.getBoundingClientRect().toJSON()}))}})()")
 d['guest']=await guest("({w:innerWidth,h:innerHeight,docW:document.documentElement.scrollWidth,bodyW:document.body.scrollWidth,reduced:matchMedia('(prefers-reduced-motion: reduce)').matches,controls:[...document.querySelectorAll('button,input,a,[tabindex]')].map(e=>({tag:e.tagName,text:e.innerText?.slice(0,100),label:e.getAttribute('aria-label'),placeholder:e.getAttribute('placeholder'),title:e.title,tab:e.tabIndex})),motionRules:[...document.querySelectorAll('style')].map(e=>e.textContent).filter(x=>x.includes('prefers-reduced-motion')).map(x=>x.slice(Math.max(0,x.indexOf('prefers-reduced-motion')-30),x.indexOf('prefers-reduced-motion')+600))})")
 r=d['root'];x=max(0,r['x']);y=max(0,r['y']);w=min(d['w'],r['right'])-x;h=min(d['h']-22,r['bottom'])-y
 # Panel-only crop excludes sidebar and footer; drawers may occupy wider x span.
 if d['dialogs']:
  r=d['dialogs'][0]['rect'];x=max(0,r['x']);y=max(34,r['y']);w=min(d['w'],r['right'])-x;h=min(d['h']-22,r['bottom'])-y
 shot=await s.call('Page.captureScreenshot',format='png',clip={'x':x,'y':y,'width':max(1,w),'height':max(1,h),'scale':1},captureBeyondViewport=False)
 (OUT/(name+'.png')).write_bytes(base64.b64decode(shot['data']));LOG[name]=d
 print(name,d['w'],'root',d['root']['width'],'guest',(d['guest'] or {}).get('w'),flush=True)
async def nav(s,slug):
 await ev(s,'location.hash='+json.dumps('#/spaces'+('?space='+slug if slug else '')));await asyncio.sleep(.7)
async def main():
 async with websockets.connect(page_ws(),max_size=64<<20) as ws:
  s=S(ws);orig=await ev(s,STATE);orig['guest']=await guest(GSTATE);LOG['original']=orig
  try:
   await s.call('Debugger.enable');await ev(s,'1')
   installed=Path('/Volumes/Expansion/Development/Projects/living-spaces/src/living-spaces/desktop/plugin.js').read_text()
   norm=lambda x:re.sub(r'(from\s*[\"\x27])[^\"\x27]+([\"\x27])',r'\1IMPORT\2',x)
   identities=[]
   for p in list(scripts):
    if p.get('url','').startswith('blob:') and p.get('length',0)>70000:
     src=(await s.call('Debugger.getScriptSource',scriptId=p['scriptId']))['scriptSource']
     if 'ls-framebar' in src:
      identities.append({'id':p['scriptId'],'url':p['url'],'bytes':len(src.encode()),'sha256':hashlib.sha256(src.encode()).hexdigest(),'normalizedMatchInstalled':norm(src)==norm(installed),'installedSha256':hashlib.sha256(installed.encode()).hexdigest(),'normalizedLoadedSha256':hashlib.sha256(norm(src).encode()).hexdigest(),'normalizedInstalledSha256':hashlib.sha256(norm(installed).encode()).hexdigest()})
   LOG['identity']=identities;await s.call('Debugger.disable')
   for text in ['Permissions','History','Upkeep: paused']:
    await clicktext(s,text);item={'initial':await ev(s,FOCUS)}
    await capture(s,'b-live-'+text.split(':')[0].lower())
    item['tabs']=[]
    for i in range(14):
     await key(s,'Tab');item['tabs'].append(await ev(s,FOCUS))
    await key(s,'Tab',True);item['shiftTab']=await ev(s,FOCUS)
    await key(s,'Escape');item['afterEscape']=await ev(s,FOCUS);item['dialogsAfterEscape']=await ev(s,"document.querySelectorAll('[role=dialog]').length")
    LOG['keyboard-'+text]=item
   for slug in ['research-desk','']:
    await nav(s,slug)
    for width in [900,390,320]:
     await s.call('Emulation.setDeviceMetricsOverride',width=width,height=844,deviceScaleFactor=1,mobile=False);await asyncio.sleep(.35)
     await capture(s,'b-live-'+('research' if slug else 'index')+'-'+str(width))
   await s.call('Emulation.clearDeviceMetricsOverride')
   for slug in ['sky-window','pair-play']:
    await nav(s,slug);await capture(s,'b-live-'+slug+'-native')
  finally:
   await key(s,'Escape');await s.call('Emulation.clearDeviceMetricsOverride');await nav(s,'research-desk')
   await guest('location.hash='+json.dumps(orig['guest']['hash']));await asyncio.sleep(.3)
   await guest('scrollTo('+','.join(map(str,orig['guest']['scroll']))+')');await ev(s,'scrollTo('+','.join(map(str,orig['scroll']))+')')
   LOG['restored']=await ev(s,STATE);LOG['restored']['guest']=await guest(GSTATE)
   LOG['restorationEqual']=orig==LOG['restored'];LOG['timestamp']=datetime.datetime.now().astimezone().isoformat()
   (OUT/'b-live-evidence.json').write_text(json.dumps(LOG,indent=2));print('RESTORED',LOG['restorationEqual'],flush=True)
if __name__=='__main__': asyncio.run(main())
