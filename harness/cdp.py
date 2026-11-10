"""Minimal CDP driver for the isolated spike app. Usage: cdp.py eval '<js>' | cdp.py shot <png> | cdp.py frames"""
import asyncio
import base64
import json
import sys
import urllib.request

import websockets

PORT = 9339


def page_ws():
    for t in json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/list")):
        if t["type"] == "page" and "/dist/index.html" in t["url"]:
            return t["webSocketDebuggerUrl"]
    raise SystemExit("no app page")


async def run(cmds):
    async with websockets.connect(page_ws(), max_size=64 << 20) as ws:
        n = 0

        async def call(method, **params):
            nonlocal n
            n += 1
            await ws.send(json.dumps({"id": n, "method": method, "params": params}))
            while True:
                m = json.loads(await ws.recv())
                if m.get("id") == n:
                    if "error" in m:
                        raise RuntimeError(m["error"])
                    return m["result"]

        out = []
        for kind, arg in cmds:
            if kind == "eval":
                r = await call("Runtime.evaluate", expression=arg, awaitPromise=True, returnByValue=True)
                out.append(r.get("result", {}).get("value", r))
            elif kind == "shot":
                r = await call("Page.captureScreenshot", format="png")
                open(arg, "wb").write(base64.b64decode(r["data"]))
                out.append(arg)
            elif kind == "frames":
                out.append(await call("Page.getFrameTree"))
        return out


def frame_targets():
    return [t for t in json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/list")) if t["type"] == "iframe"]


async def frame_eval(js, depth):
    """Evaluate in an isolated world of the frame `depth` levels below the iframe target root (DOM is shared,
    page globals are not). depth=1 is the Space document when the target root is the shell."""
    results = []
    for t in frame_targets():
        async with websockets.connect(t["webSocketDebuggerUrl"], max_size=64 << 20) as ws:
            n = 0

            async def call(method, **params):
                nonlocal n
                n += 1
                await ws.send(json.dumps({"id": n, "method": method, "params": params}))
                while True:
                    m = json.loads(await ws.recv())
                    if m.get("id") == n:
                        if "error" in m:
                            raise RuntimeError(m["error"])
                        return m["result"]

            tree = (await call("Page.getFrameTree"))["frameTree"]
            node = tree
            for _ in range(depth):
                if not node.get("childFrames"):
                    node = None
                    break
                node = node["childFrames"][0]
            if node is None:
                continue
            ctx = (await call("Page.createIsolatedWorld", frameId=node["frame"]["id"], worldName="probe"))["executionContextId"]
            r = await call("Runtime.evaluate", expression=js, contextId=ctx, awaitPromise=True, returnByValue=True)
            results.append(r.get("result", {}).get("value", r))
    return results


if len(sys.argv) > 1 and sys.argv[1] == "feval":
    for r in asyncio.run(frame_eval(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 1)):
        print(r if isinstance(r, str) else json.dumps(r))
    raise SystemExit(0)


if __name__ == "__main__":
    args = sys.argv[1:]
    cmds = [(args[i], args[i + 1] if i + 1 < len(args) else None) for i in range(0, len(args), 2)]
    for r in asyncio.run(run(cmds)):
        print(json.dumps(r, indent=1) if not isinstance(r, str) else r)
