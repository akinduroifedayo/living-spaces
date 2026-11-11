import sys,base64,asyncio,json
sys.path.insert(0,'/Volumes/Expansion/Development/Projects/living-spaces/harness'); sys.path.insert(0,'.')
import ui
OUT='/Volumes/Expansion/Development/Projects/living-spaces/docs/design/premium-pass/regeneration/astra-run/shots/'
name=sys.argv[1]; w=int(sys.argv[2]) if len(sys.argv)>2 else 390
async def f(s):
    await s.call('Emulation.setDeviceMetricsOverride',width=w,height=844,deviceScaleFactor=2,mobile=True)
    await asyncio.sleep(4)
    r=await s.call('Runtime.evaluate',expression='[innerWidth, document.documentElement.scrollWidth]',returnByValue=True)
    print(r['result']['value'])
    r=await s.call('Page.captureScreenshot',format='png')
    open(OUT+name,'wb').write(base64.b64decode(r['data']))
    await s.call('Emulation.clearDeviceMetricsOverride')
ui.page(f); print(name)
