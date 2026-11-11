import sys,time,json
sys.path.insert(0,'/Volumes/Expansion/Development/Projects/living-spaces/harness'); sys.path.insert(0,'.')
import ui
from guest_realm import guest
from cdp import evaluate
fx,fy=evaluate("(()=>{const r=document.querySelector('iframe').getBoundingClientRect();return [r.x,r.y]})()")
def put(ph,val):
    r=guest(f"(()=>{{const e=[...document.querySelectorAll('input')].find(e=>e.placeholder=={json.dumps(ph)});const b=e.getBoundingClientRect();return [b.x+b.width/2,b.y+b.height/2]}})()")['value']
    ui.click(fx+r[0],fy+r[1]); time.sleep(.4)
    ui.page(lambda s:s.call('Input.insertText',text=val)); time.sleep(.4)
    print(ph, guest(f"document.activeElement.value")['value'])
for a,b in zip(sys.argv[1::2],sys.argv[2::2]): put(a,b)
