import sys, asyncio, json, base64, urllib.request, datetime
from pathlib import Path
sys.path.insert(0,'/Volumes/Expansion/Development/Projects/living-spaces/harness')
from cdp import Session,page_ws,_targets
import websockets
OUT=Path('/Volumes/Expansion/Development/Build/r1-qualification-t_b3b306df/addendum')
log=[]
async def ev(s,expr,ctx=None):
    args={'expression':expr,'returnByValue':True,'awaitPromise':True}
    if ctx: args['contextId']=ctx
    r=await s.call('Runtime.evaluate',**args)
    if r.get('exceptionDetails'): raise RuntimeError(str(r['exceptionDetails']))
    return r.get('result',{}).get('value')
async def guest(expr):
    for t in _targets():
        if t['type']=='iframe':
            async with websockets.connect(t['webSocketDebuggerUrl'],max_size=64<<20) as ws:
                s=Session(ws); tree=(await s.call('Page.getFrameTree'))['frameTree']
                kids=tree.get('childFrames',[])
                if not kids: continue
                ctx=(await s.call('Page.createIsolatedWorld',frameId=kids[0]['frame']['id'],worldName='a-live-readonly'))['executionContextId']
                return await ev(s,expr,ctx)
    return None
async def capture(s,name):
    data=await ev(s,"({route:location.hash,w:innerWidth,h:innerHeight,dpr:devicePixelRatio,root:document.querySelector('.ls-root')?.getBoundingClientRect().toJSON(),frames:Array.from(document.querySelectorAll('iframe')).map(x=>({title:x.title,rect:x.getBoundingClientRect().toJSON()})),header:document.querySelector('.ls-framebar')?.innerText,panels:Array.from(document.querySelectorAll('[role=dialog]')).map(x=>x.innerText.slice(0,3500))})")
    data['guest']=await guest("({hash:location.hash,w:innerWidth,h:innerHeight,scroll:[scrollX,scrollY],text:document.body.innerText.slice(0,7500),buttons:Array.from(document.querySelectorAll('button')).map(x=>({text:x.innerText,label:x.getAttribute('aria-label')}))})")
    r=data['root']; x=max(0,r['x']); y=max(0,r['y']); w=min(data['w'],r['right'])-x; h=min(data['h']-32,r['bottom'])-y
    shot=await s.call('Page.captureScreenshot',format='png',clip={'x':x,'y':y,'width':w,'height':h,'scale':1},captureBeyondViewport=False)
    p=OUT/(name+'.png');p.write_bytes(base64.b64decode(shot['data']));data['image']=str(p);data['crop']={'x':x,'y':y,'width':w,'height':h};log.append(data)
    print(json.dumps({'name':name,'w':data['w'],'guestW':(data['guest'] or {}).get('w'),'image':str(p)}),flush=True)
async def nav(s,slug):
    await ev(s,'location.hash='+json.dumps('#/spaces'+('?space='+slug if slug else '')))
    await asyncio.sleep(1.2)
async def main():
    async with websockets.connect(page_ws(),max_size=64<<20) as ws:
        s=Session(ws)
        orig=await ev(s,"({hash:location.hash,w:innerWidth,h:innerHeight,scroll:[scrollX,scrollY],panels:Array.from(document.querySelectorAll('[role=dialog]')).map(x=>x.innerText)})")
        orig['guest']=await guest("({hash:location.hash,scroll:[scrollX,scrollY],search:document.querySelector('input[type=search]')?.value})")
        (OUT/'a-live-original.json').write_text(json.dumps(orig,indent=2))
        try:
            await capture(s,'a-live-research-desktop-library')
            for slug in ['research-desk','sky-window','pair-play']:
                if slug!='research-desk': await nav(s,slug)
                else:
                    await guest("location.hash='#/overview'");await asyncio.sleep(.4)
                await capture(s,'a-live-'+slug+'-desktop')
                for width in [390,320]:
                    await s.call('Emulation.setDeviceMetricsOverride',width=width,height=844,deviceScaleFactor=1,mobile=False)
                    await asyncio.sleep(.6)
                    await capture(s,'a-live-'+slug+'-'+str(width))
                await s.call('Emulation.clearDeviceMetricsOverride');await asyncio.sleep(.4)
            await nav(s,'')
            await capture(s,'a-live-index-desktop')
            await s.call('Emulation.setDeviceMetricsOverride',width=390,height=844,deviceScaleFactor=1,mobile=False);await asyncio.sleep(.5)
            await capture(s,'a-live-index-390')
        finally:
            await s.call('Emulation.clearDeviceMetricsOverride')
            await nav(s,'research-desk')
            await guest('location.hash='+json.dumps(orig['guest']['hash']));await asyncio.sleep(.4)
            await guest("(()=>{let x=document.querySelector('input[type=search]');if(x){x.value="+json.dumps(orig['guest'].get('search',''))+";x.dispatchEvent(new Event('input',{bubbles:true}));}scrollTo("+','.join(map(str,orig['guest']['scroll']))+");})()")
            await ev(s,'scrollTo('+','.join(map(str,orig['scroll']))+')')
            await asyncio.sleep(.4)
            restore=await ev(s,"({hash:location.hash,w:innerWidth,h:innerHeight,scroll:[scrollX,scrollY],panels:Array.from(document.querySelectorAll('[role=dialog]')).map(x=>x.innerText)})")
            restore['guest']=await guest("({hash:location.hash,scroll:[scrollX,scrollY],search:document.querySelector('input[type=search]')?.value})")
            (OUT/'a-live-restored.json').write_text(json.dumps(restore,indent=2));print('RESTORE '+json.dumps(restore),flush=True)
            (OUT/'a-live-captures.json').write_text(json.dumps(log,indent=2))
if __name__=='__main__': asyncio.run(main())
