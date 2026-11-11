import sys,time,json
sys.path.insert(0,'/Volumes/Expansion/Development/Projects/living-spaces/harness'); sys.path.insert(0,'.')
import ui
from guest_realm import guest
from cdp import evaluate
fx,fy=evaluate("(()=>{const r=document.querySelector('iframe').getBoundingClientRect();return [r.x,r.y]})()")
sel,val=sys.argv[1],sys.argv[2]
r=guest(f"(()=>{{const e=document.querySelectorAll({json.dumps(sel)})[{int(sys.argv[3]) if len(sys.argv)>3 else 0}];e.scrollIntoView({{block:'center'}});const b=e.getBoundingClientRect();return [b.x+Math.min(40,b.width/2),b.y+Math.min(20,b.height/2)]}})()")['value']
ui.click(fx+r[0],fy+r[1]); time.sleep(.4)
ui.page(lambda s:s.call('Input.insertText',text=val)); time.sleep(1.2)
print(guest("[document.activeElement.tagName, (document.activeElement.value ?? document.activeElement.innerText).slice(0,80)]")['value'])
