"""Evaluate inside a mounted Space's own realm, and read open bridge sessions."""
import asyncio
import json
import sqlite3
from pathlib import Path

import websockets

from cdp import _targets, Session

DB = Path('/Volumes/Expansion/Development/Build/living-spaces-r1/home/plugin-data/living-spaces/spaces.db')


def guest(js):
    async def go():
        frames = [t for t in _targets() if t['type'] == 'iframe']
        if not frames:
            return None
        t = frames[0]
        async with websockets.connect(t['webSocketDebuggerUrl'], max_size=64 << 20) as ws:
            s = Session(ws)
            await ws.send(json.dumps({'id': 9999, 'method': 'Runtime.enable'}))
            ctxs = []
            while True:
                m = json.loads(await ws.recv())
                if m.get('method') == 'Runtime.executionContextCreated':
                    ctxs.append(m['params']['context'])
                if m.get('id') == 9999:
                    break
            for c in ctxs:
                if not c.get('auxData', {}).get('isDefault'):
                    continue
                probe = await s.call('Runtime.evaluate', expression='typeof globalThis.space', contextId=c['id'], returnByValue=True)
                if probe['result'].get('value') == 'object':
                    r = await s.call('Runtime.evaluate', expression=f'(async () => {{ try {{ return {{ok: true, value: await ({js})}} }} catch (e) {{ return {{ok: false, code: e.code, message: String(e.message || e)}} }} }})()',
                                     contextId=c['id'], awaitPromise=True, returnByValue=True)
                    return r['result'].get('value')
            return None
    return asyncio.run(go())


def open_sessions(sid):
    con = sqlite3.connect(DB)
    rows = [r[0] for r in con.execute('SELECT id FROM sessions WHERE space=? AND closed_at IS NULL', (sid,))]
    con.close()
    return rows
