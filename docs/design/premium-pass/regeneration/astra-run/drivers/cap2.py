import sys, time, json, base64
sys.path.insert(0,'/Volumes/Expansion/Development/Projects/living-spaces/harness'); sys.path.insert(0,'.')
import ui
from cdp import evaluate
from guest_realm import guest
OUT='/Volumes/Expansion/Development/Projects/living-spaces/docs/design/premium-pass/regeneration/astra-run/shots/'
import os; os.makedirs(OUT,exist_ok=True)
def go(slug): evaluate(f"location.hash='#/spaces?space={slug}'"); time.sleep(7)
def phone(on):
    async def f(s):
        if on: await s.call('Emulation.setDeviceMetricsOverride',width=390,height=844,deviceScaleFactor=2,mobile=True)
        else: await s.call('Emulation.clearDeviceMetricsOverride')
    ui.page(f); time.sleep(3)
def shot(name, full=False):
    W,H=evaluate('[innerWidth,innerHeight]')
    async def f(s):
        clip={'x':0,'y':0,'width':W,'height':H-(0 if W<600 else 32),'scale':1}
        r=await s.call('Page.captureScreenshot',format='png',clip=clip)
        open(OUT+name,'wb').write(base64.b64decode(r['data']))
    ui.page(f); return name
def buttons(): return guest("[...document.querySelectorAll('button,[role=tab],[role=button],a')].map(b=>(b.getAttribute('aria-label')||b.innerText||'').trim().slice(0,40)).filter(Boolean)")
def click(label):
    return guest(f"(()=>{{const L={json.dumps(label)};const b=[...document.querySelectorAll('button,[role=tab],[role=button],a')].find(b=>((b.getAttribute('aria-label')||b.innerText||'').trim()).startsWith(L));if(!b)return 'missing';b.click();return 'clicked'}})()")
def text(n=1500): return guest(f"document.body.innerText.replace(/\\s+/g,' ').slice(0,{n})")
if __name__=='__main__':
    c=sys.argv[1]
    if c=='go': go(sys.argv[2])
    elif c=='buttons': print(json.dumps(buttons()))
    elif c=='click': print(click(sys.argv[2])); time.sleep(2)
    elif c=='shot': print(shot(sys.argv[2]))
    elif c=='phone': phone(sys.argv[2]=='1')
    elif c=='text': print(json.dumps(text(int(sys.argv[2]) if len(sys.argv)>2 else 1500)))
    elif c=='g': print(json.dumps(guest(sys.argv[2]))[:3000])
