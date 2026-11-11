import sys,base64
sys.path.insert(0,'/Volumes/Expansion/Development/Build/living-spaces-r1/run/regen-astra')
import ui
from cdp import evaluate
w,h=evaluate('[innerWidth,innerHeight]')
async def f(s):
    r=await s.call('Page.captureScreenshot',format='png',clip={'x':0,'y':0,'width':w,'height':h-32,'scale':1})
    open(sys.argv[1],'wb').write(base64.b64decode(r['data']))
ui.page(f); print(w,h-32)
