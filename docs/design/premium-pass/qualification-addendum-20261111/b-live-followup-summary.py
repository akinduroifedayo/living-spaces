import json,collections
from pathlib import Path
p=Path('/Volumes/Expansion/Development/Build/r1-qualification-t_b3b306df/addendum');a=json.loads((p/'b-live-evidence.json').read_text());b=json.loads((p/'b-live-followup.json').read_text());det=json.loads((p/'b-live-detector.json').read_text())
print('detector',len(det),dict(collections.Counter(x['antipattern'] for x in det)))
print('grantsVisibleEqual',a['b-live-permissions']['dialogs']==b['b-live-permissions-after']['dialogs'])
print('revisionText',b['b-live-revisions']['dialogs'][0]['text'][:1500])
for k,v in b.items():
 if k.endswith('-ax'):print(k,v)
 if 'ready-' in k:print(k,{x:v['guest'].get(x) for x in ['w','docW','bodyW','motionRules']})
print('permissions390',b['b-live-permissions-390']['dialogs'][0]['rect'])
