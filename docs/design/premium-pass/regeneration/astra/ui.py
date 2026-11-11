"""Native-input UI helper for the isolated Desktop (CDP 9341). Usage:
  ui.py click X Y | ui.py shot PATH | ui.py eval JS | ui.py key KEY | ui.py type TEXT"""
import asyncio, sys, json, base64
sys.path.insert(0, '/Volumes/Expansion/Development/Projects/living-spaces/harness')
from cdp import evaluate, page_ws, Session
import websockets


def page(fn):
    async def go():
        async with websockets.connect(page_ws(), max_size=64 << 20) as ws:
            return await fn(Session(ws))
    return asyncio.run(go())


def click(x, y):
    async def f(s):
        await s.call('Input.dispatchMouseEvent', type='mouseMoved', x=x, y=y)
        for k in ('mousePressed', 'mouseReleased'):
            await s.call('Input.dispatchMouseEvent', type=k, x=x, y=y, button='left', clickCount=1)
    page(f)


def key(k):
    codes = {'Escape': 27, 'Enter': 13}
    async def f(s):
        for t in ('keyDown', 'keyUp'):
            await s.call('Input.dispatchKeyEvent', type=t, key=k, code=k, windowsVirtualKeyCode=codes.get(k, 0))
    page(f)


def shot(path):
    async def f(s):
        r = await s.call('Page.captureScreenshot', format='png')
        open(path, 'wb').write(base64.b64decode(r['data']))
    page(f)
    print(path)


if __name__ == '__main__':
    c = sys.argv[1]
    if c == 'click': click(float(sys.argv[2]), float(sys.argv[3]))
    elif c == 'shot': shot(sys.argv[2])
    elif c == 'key': key(sys.argv[2])
    elif c == 'type':
        page(lambda s: s.call('Input.insertText', text=sys.argv[2]))
    elif c == 'eval': print(json.dumps(evaluate(sys.argv[2]), indent=1))
