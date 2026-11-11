import json,sys
from pathlib import Path
p=Path('/Volumes/Expansion/Development/Build/r1-qualification-t_b3b306df/addendum');d=json.loads((p/'b-live-evidence.json').read_text())
for k in ['original','restored','identity']:
 print(k,json.dumps(d[k]))
for k,v in d.items():
 if k.startswith('keyboard-'):print(k,json.dumps({x:v[x] for x in ['initial','afterEscape','dialogsAfterEscape']}),'allTabInside',all(x['inDialog'] for x in v['tabs']))
 if k.startswith('b-live-'):
  print(k,'root',v['root']['width'],'docW',v['docW'],'guest', {x:v['guest'].get(x) for x in ['w','docW','bodyW','motionRules']} if v['guest'] else None)
  if k.endswith(('900','390','320')):print('geometry',[(e['text'][:50],e['rect']['width'],e['rect']['height']) for e in v['elements']])
print('guest-controls',d['b-live-research-320']['guest']['controls'])
