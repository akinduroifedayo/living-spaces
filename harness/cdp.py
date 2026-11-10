"""CDP driver for the isolated app (stdlib + websockets from the hermes venv).

  cdp.py eval '<js>'            evaluate in the app page (awaits promises, returns by value)
  cdp.py shot out.png           screenshot of the app page
  cdp.py feval '<js>' [depth]   evaluate inside Space frames (isolated world; depth 1 = Space document)
  cdp.py click '<css>'          click the first element matching a selector in the app page"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
import urllib.request

import websockets

PORT = int(os.environ.get("LS_CDP_PORT", "9341"))


def _targets():
    return json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/list", timeout=5))


def page_ws() -> str:
    for t in _targets():
        if t["type"] == "page" and "/dist/index.html" in t["url"]:
            return t["webSocketDebuggerUrl"]
    raise SystemExit("no app page")


class Session:
    def __init__(self, ws):
        self.ws, self.n = ws, 0

    async def call(self, method, **params):
        self.n += 1
        await self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            m = json.loads(await self.ws.recv())
            if m.get("id") == self.n:
                if "error" in m:
                    raise RuntimeError(m["error"])
                return m["result"]


async def _page(fn):
    async with websockets.connect(page_ws(), max_size=64 << 20) as ws:
        return await fn(Session(ws))


def evaluate(js: str):
    async def run(s):
        r = await s.call("Runtime.evaluate", expression=js, awaitPromise=True, returnByValue=True)
        if r.get("exceptionDetails"):
            return {"exception": r["exceptionDetails"].get("exception", {}).get("description") or r["exceptionDetails"]}
        return r.get("result", {}).get("value")
    return asyncio.run(_page(run))


def screenshot(path: str) -> str:
    async def run(s):
        r = await s.call("Page.captureScreenshot", format="png")
        open(path, "wb").write(base64.b64decode(r["data"]))
        return path
    return asyncio.run(_page(run))


def frame_eval(js: str, depth: int = 1) -> list:
    async def one(t):
        async with websockets.connect(t["webSocketDebuggerUrl"], max_size=64 << 20) as ws:
            s = Session(ws)
            node = (await s.call("Page.getFrameTree"))["frameTree"]
            for _ in range(depth):
                kids = node.get("childFrames") or []
                if not kids:
                    return None
                node = kids[0]
            ctx = (await s.call("Page.createIsolatedWorld", frameId=node["frame"]["id"], worldName="probe"))["executionContextId"]
            r = await s.call("Runtime.evaluate", expression=js, contextId=ctx, awaitPromise=True, returnByValue=True)
            return r.get("result", {}).get("value", r)

    async def run():
        out = []
        for t in _targets():
            if t["type"] == "iframe":
                v = await one(t)
                if v is not None:
                    out.append(v)
        return out
    return asyncio.run(run())


def click(selector: str):
    return evaluate(f"(() => {{ const el = document.querySelector({json.dumps(selector)}); if (!el) return 'missing';"
                    f" el.click(); return 'clicked' }})()")


if __name__ == "__main__":
    cmd, *rest = sys.argv[1:]
    if cmd == "eval":
        v = evaluate(rest[0])
    elif cmd == "shot":
        v = screenshot(rest[0])
    elif cmd == "feval":
        v = frame_eval(rest[0], int(rest[1]) if len(rest) > 1 else 1)
    elif cmd == "click":
        v = click(rest[0])
    else:
        raise SystemExit(__doc__)
    print(v if isinstance(v, str) else json.dumps(v, indent=1))
