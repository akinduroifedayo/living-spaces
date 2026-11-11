import json
from pathlib import Path
p=Path('/Volumes/Expansion/Development/Build/r1-qualification-t_b3b306df/addendum')
o=json.loads((p/'a-live-original.json').read_text());r=json.loads((p/'a-live-release.json').read_text())
assert o==r,(o,r)
rows=[]
for f in ['a-live-captures.json','a-live-flow-captures.json','a-live-final-captures.json','a-live-revision-receipts.json']:rows+=json.loads((p/f).read_text())
paths=sorted(set(x['image'] for x in rows));assert all(Path(x).exists() for x in paths)
scores=[2,3,3,3,2,3,2,3,2,3]
print(json.dumps({'restoration_exact':True,'image_count':len(paths),'scores':scores,'total':sum(scores),'max':len(scores)*4,'images':paths},indent=2))
