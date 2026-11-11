import importlib.util, asyncio, json, base64
sp=importlib.util.spec_from_file_location('c','/Volumes/Expansion/Development/Build/r1-qualification-t_b3b306df/addendum/a-live-capture.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
async def button(s,text,scope='document'):
    r=await m.ev(s,"(()=>{let x=Array.from("+scope+".querySelectorAll('button,[role=tab]')).find(x=>x.textContent.trim()==="+json.dumps(text)+");return x?.getBoundingClientRect().toJSON()})()")
    if not r:return False
    x=r['x']+r['width']/2;y=r['y']+r['height']/2
    for t in ['mousePressed','mouseReleased']:await s.call('Input.dispatchMouseEvent',type=t,x=x,y=y,button='left',clickCount=1)
    return True
async def esc(s):
    for t in ['keyDown','keyUp']: await s.call('Input.dispatchKeyEvent',type=t,key='Escape',code='Escape',windowsVirtualKeyCode=27)
async def main():
 async with m.websockets.connect(m.page_ws(),max_size=64<<20) as ws:
    s=m.Session(ws); receipts=[]
    try:
      for slug in ['sky-window','research-desk','pair-play']:
        await m.nav(s,slug);await asyncio.sleep(3)
        await button(s,'History',"document.querySelector('.ls-root')");await asyncio.sleep(.4)
        print('TABS',await m.ev(s,"Array.from(document.querySelectorAll('[role=dialog] button,[role=dialog] [role=tab]')).map(x=>({t:x.textContent,tag:x.tagName,role:x.getAttribute('role')}))"))
        await button(s,'Revisions',"document.querySelector('[role=dialog]')");await asyncio.sleep(.7)
        text=await m.ev(s,"document.querySelector('[role=dialog]')?.innerText")
        r=await m.ev(s,"document.querySelector('[role=dialog]').getBoundingClientRect().toJSON()")
        p=m.OUT/('a-live-'+slug+'-revision-proof.png')
        shot=await s.call('Page.captureScreenshot',format='png',clip={'x':r['x'],'y':max(0,r['y']),'width':r['width'],'height':min(r['height'],858),'scale':1});p.write_bytes(base64.b64decode(shot['data']))
        receipts.append({'slug':slug,'text':text,'image':str(p)});print(slug,text[:600],flush=True)
        await esc(s)
      await m.nav(s,'sky-window');await asyncio.sleep(3)
      await m.guest("(()=>{let b=Array.from(document.querySelectorAll('button,a')).find(x=>x.textContent.trim()==='Week');if(b)b.click()})()");await asyncio.sleep(.4)
      await m.capture(s,'a-live-sky-week-desktop')
      await s.call('Emulation.setDeviceMetricsOverride',width=390,height=844,deviceScaleFactor=1,mobile=False);await asyncio.sleep(.4)
      await m.capture(s,'a-live-sky-week-390')
      await m.guest("(()=>{let b=Array.from(document.querySelectorAll('button,a')).find(x=>x.textContent.trim()==='Cities');if(b)b.click()})()");await asyncio.sleep(.4)
      await m.capture(s,'a-live-sky-cities-390')
    finally:
      await esc(s);await s.call('Emulation.clearDeviceMetricsOverride');await m.nav(s,'research-desk');await asyncio.sleep(2)
      await m.guest("location.hash='#/library'");await asyncio.sleep(.3)
      await m.guest("(()=>{let x=document.querySelector('input[type=search]');if(x){x.value='attention';x.dispatchEvent(new Event('input',{bubbles:true}));}scrollTo(0,0)})()")
      await m.ev(s,'scrollTo(0,0)');await asyncio.sleep(.3)
      restore=await m.ev(s,"({hash:location.hash,w:innerWidth,h:innerHeight,scroll:[scrollX,scrollY],panels:Array.from(document.querySelectorAll('[role=dialog]')).map(x=>x.innerText)})")
      restore['guest']=await m.guest("({hash:location.hash,scroll:[scrollX,scrollY],search:document.querySelector('input[type=search]')?.value})")
      (m.OUT/'a-live-release.json').write_text(json.dumps(restore,indent=2));(m.OUT/'a-live-revision-receipts.json').write_text(json.dumps(receipts,indent=2));(m.OUT/'a-live-final-captures.json').write_text(json.dumps(m.log,indent=2));print('RELEASE '+json.dumps(restore))
asyncio.run(main())
