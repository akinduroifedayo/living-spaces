import asyncio,json,importlib.util,collections
spec=importlib.util.spec_from_file_location('a','/Volumes/Expansion/Development/Build/r1-qualification-t_b3b306df/addendum/b-live-audit.py');a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
async def main():
 det=json.loads((a.OUT/'b-live-detector.json').read_text());receipt={'command':"impeccable detect --cdp 9341 --target 'dist/index.html#/spaces' --json",'exitCode':2,'counts':dict(collections.Counter(x['antipattern'] for x in det))}
 async with a.websockets.connect(a.page_ws(),max_size=64<<20) as ws:
  s=a.S(ws);receipt['scope']=[]
  for d in det:
   v=await a.ev(s,"[...document.querySelectorAll("+json.dumps(d['selector'])+")].map(e=>({tag:e.tagName,inLivingSpaces:!!e.closest('.ls-root'),isDocumentBody:e===document.body}))")
   receipt['scope'].append({'selector':d['selector'],'matches':v})
  receipt['finalState']=await a.ev(s,a.STATE);receipt['finalState']['guest']=await a.guest(a.GSTATE)
 orig=json.loads((a.OUT/'b-live-evidence.json').read_text())['original'];receipt['finalStateMatchesOriginal']=orig==receipt['finalState']
 b=json.loads((a.OUT/'b-live-followup.json').read_text())
 receipt['overflowVsInnerWidth']={k:v['guest']['docW']-v['guest']['w'] for k,v in b.items() if 'ready-' in k}
 receipt['screenshotFiles']=sorted(p.name for p in a.OUT.glob('b-live*.png'));receipt['screenshotCount']=len(receipt['screenshotFiles'])
 (a.OUT/'b-live-detector-receipt.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt,indent=2))
asyncio.run(main())
