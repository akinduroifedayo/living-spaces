"""Send one turn through the Desktop's own chat composer with native input, then wait for the model to finish."""
import asyncio
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp import evaluate, page_ws, Session  # noqa: E402

STATE = Path('/Volumes/Expansion/Development/Build/living-spaces-r1/home/state.db')


def _page(fn):
    import websockets

    async def go():
        async with websockets.connect(page_ws(), max_size=64 << 20) as ws:
            return await fn(Session(ws))
    return asyncio.run(go())


def _last_assistant(session_id, since):
    con = sqlite3.connect(STATE)
    row = con.execute("SELECT timestamp, finish_reason, tool_calls IS NOT NULL, substr(content,1,2000) FROM messages "
                      "WHERE session_id=? AND role='assistant' AND timestamp>=? ORDER BY timestamp DESC LIMIT 1", (session_id, since)).fetchone()
    con.close()
    return row


def submit(session_id, text, timeout=900, settle=20):
    evaluate(f'location.hash="/{session_id}"')
    time.sleep(3)
    box = evaluate("""(() => { const e = document.querySelector('[contenteditable=true][aria-label=Message]'); if (!e) return null;
      e.focus(); const r = e.getBoundingClientRect(); return {x: r.x + 20, y: r.y + r.height / 2} })()""")
    if not box:
        raise LookupError('Desktop composer not found')

    async def type_and_send(s):
        for kind in ('mousePressed', 'mouseReleased'):
            await s.call('Input.dispatchMouseEvent', type=kind, x=box['x'], y=box['y'], button='left', clickCount=1)
        await s.call('Input.insertText', text=text)
        await asyncio.sleep(.5)
        for kind in ('keyDown', 'keyUp'):
            await s.call('Input.dispatchKeyEvent', type=kind, key='Enter', code='Enter', windowsVirtualKeyCode=13)
    t0 = time.time()
    _page(type_and_send)
    end, last, stable_since = t0 + timeout, None, None
    while time.time() < end:
        time.sleep(3)
        row = _last_assistant(session_id, t0)
        done = row and row[1] in ('stop', 'end_turn') and not row[2]
        if done and row == last:
            stable_since = stable_since or time.time()
            if time.time() - stable_since >= settle:
                return {'sent_at': t0, 'finished_at': row[0], 'seconds': round(row[0] - t0, 1), 'finish_reason': row[1], 'reply': row[3]}
        else:
            stable_since = None
        last = row
    raise TimeoutError('model turn did not finish')
