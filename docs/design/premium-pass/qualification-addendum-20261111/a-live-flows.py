import importlib.util, asyncio, json
spec=importlib.util.spec_from_file_location('capture','/Volumes/Expansion/Development/Build/r1-qualification-t_b3b306df/addendum/a-live-capture.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
async def clicktext(s,text):
    return await m.ev(s,"(()=>{let b=Array.from(document.querySelectorAll('.ls-root button')).find(x=>x.textContent.trim()==="+json.dumps(text)+");if(b){b.click();return true}return false})()")
async def esc(s):
    for typ in ['keyDown','keyUp']:await s.call('Input.dispatchKeyEvent',type=typ,key='Escape',code='Escape',windowsVirtualKeyCode=27)
async def main():
    async with m.websockets.connect(m.page_ws(),max_size=64<<20) as ws:
        s=m.Session(ws)
        try:
            await m.guest("(()=>{let b=Array.from(document.querySelectorAll('button')).find(x=>x.textContent.includes('Attention Is All You Need'));if(b)b.click()})()");await asyncio.sleep(.4)
            await m.capture(s,'a-live-research-detail-desktop')
            await s.call('Emulation.setDeviceMetricsOverride',width=390,height=844,deviceScaleFactor=1,mobile=False);await asyncio.sleep(.4)
            await m.capture(s,'a-live-research-detail-390')
            await s.call('Emulation.clearDeviceMetricsOverride')
            for slug in ['research-desk','sky-window','pair-play']:
                if slug!='research-desk':await m.nav(s,slug)
                await asyncio.sleep(4 if slug=='sky-window' else .5)
                if slug=='sky-window':
                    await m.capture(s,'a-live-sky-loaded-desktop')
                    for width in [390,320]:
                        await s.call('Emulation.setDeviceMetricsOverride',width=width,height=844,deviceScaleFactor=1,mobile=False);await asyncio.sleep(.7)
                        await m.capture(s,'a-live-sky-loaded-'+str(width))
                    await s.call('Emulation.clearDeviceMetricsOverride');await asyncio.sleep(.5)
                if slug=='pair-play':
                    await m.guest("(()=>{let b=Array.from(document.querySelectorAll('button,a')).find(x=>x.textContent.trim()==='History');if(b)b.click()})()");await asyncio.sleep(.5)
                    await m.capture(s,'a-live-pair-history-desktop')
                    await s.call('Emulation.setDeviceMetricsOverride',width=390,height=844,deviceScaleFactor=1,mobile=False);await asyncio.sleep(.4)
                    await m.capture(s,'a-live-pair-history-390');await s.call('Emulation.clearDeviceMetricsOverride')
                await clicktext(s,'History');await asyncio.sleep(.4)
                await clicktext(s,'Revisions');await asyncio.sleep(.4)
                print('REVISION '+slug+' '+str(await m.ev(s,"Array.from(document.querySelectorAll('[role=dialog]')).map(x=>x.innerText.slice(0,2500))")),flush=True)
                await m.capture(s,'a-live-'+slug+'-revisions')
                await esc(s);await asyncio.sleep(.2)
            await m.nav(s,'research-desk');await clicktext(s,'Permissions');await asyncio.sleep(.5)
            await m.capture(s,'a-live-permissions-desktop');await esc(s)
            await clicktext(s,'Upkeep: paused');await asyncio.sleep(.5)
            await m.capture(s,'a-live-upkeep-desktop');await esc(s)
        finally:
            await esc(s);await s.call('Emulation.clearDeviceMetricsOverride')
            await m.nav(s,'research-desk');await m.guest("location.hash='#/library'");await asyncio.sleep(.3)
            await m.guest("(()=>{let x=document.querySelector('input[type=search]');if(x){x.value='attention';x.dispatchEvent(new Event('input',{bubbles:true}));}scrollTo(0,0)})()")
            await m.ev(s,'scrollTo(0,0)');await asyncio.sleep(.3)
            restore=await m.ev(s,"({hash:location.hash,w:innerWidth,h:innerHeight,scroll:[scrollX,scrollY],panels:Array.from(document.querySelectorAll('[role=dialog]')).map(x=>x.innerText)})")
            restore['guest']=await m.guest("({hash:location.hash,scroll:[scrollX,scrollY],search:document.querySelector('input[type=search]')?.value,text:document.body.innerText.slice(0,1300)})")
            (m.OUT/'a-live-flow-restored.json').write_text(json.dumps(restore,indent=2));print('RESTORED '+json.dumps(restore),flush=True)
            (m.OUT/'a-live-flow-captures.json').write_text(json.dumps(m.log,indent=2))
asyncio.run(main())
