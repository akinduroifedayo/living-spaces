#!/Users/ifedayoakinduro/.hermes/hermes-agent/venv/bin/python
"""One Desktop decision in proven disposable storage only."""
import asyncio
import json
from pathlib import Path
import shlex
import subprocess
import time

KEY = 'hermes.desktop.pluginDecisions.v2'


def prove_isolation(c, out) -> dict:
    m = c.owned(out)
    state = Path(m['state'])
    ud = state / 'ud'
    assert state.parent == out and ud.resolve() == ud, 'Unexpected or symlinked userData path'
    assert not ud.is_relative_to(Path.home() / 'Library/Application Support'), 'Real Desktop profile refused'
    assert not ud.is_relative_to(Path.home() / '.hermes'), 'Real Hermes home refused'
    rows = [r for r in c.processes() if r['pgid'] == m['pgid']]
    renderers = [r for r in rows if ' --type=renderer ' in r['command']]
    observed_dirs = [[arg.split('=', 1)[1] for arg in shlex.split(r['command'])
                      if arg.startswith('--user-data-dir=')] for r in renderers]
    opened = subprocess.run(['lsof', '-nP', '-p', str(m['pid']), '-Fn'], capture_output=True, text=True)
    storage = [line[1:] for line in opened.stdout.splitlines()
               if line.startswith('n') and '/Local Storage/' in line]
    frame = c.call(out, 'Page.getFrameTree')['frameTree']['frame']
    renderer = c.evaluate(out, f'({{url:location.href,origin:location.origin,flag:localStorage.getItem({json.dumps(KEY)})}})')
    receipt = dict(proven=False, before_any_flag_write=True, pid=m['pid'], started=m['started'],
                   expected_user_data=str(ud), real_application_support=str(Path.home() / 'Library/Application Support'),
                   observed_renderer_directories=observed_dirs, open_local_storage_files=storage,
                   lsof_exit=opened.returncode, frame=frame, renderer=renderer, observed_at=time.time())
    c.dump(out / 'flag-isolation.json', receipt)
    assert renderers and all(d == [str(ud)] for d in observed_dirs), 'Renderer userData not proven'
    assert opened.returncode == 0 and str(ud / 'Local Storage/leveldb/LOCK') in storage, 'No owned Local Storage lock'
    assert all(Path(p).is_relative_to(ud) for p in storage), 'Foreign Local Storage is open'
    assert frame['securityOrigin'] == renderer['origin'] == 'file://', 'Unexpected renderer origin'
    assert frame['url'].endswith('/dist/index.html'), 'Wrong app frame'
    c.owned(out)
    receipt['proven'] = True
    c.dump(out / 'flag-isolation.json', receipt)
    return receipt


def enable(c, out):
    isolation = prove_isolation(c, out)
    before = isolation['renderer']['flag']
    decisions = json.loads(before or '{}')
    assert isinstance(decisions, dict), 'Decision value is not a JSON object'
    expected = {**decisions, 'living-spaces': True}
    c.owned(out)
    after = c.evaluate(out, f'''(() => {{const k={json.dumps(KEY)};
        const d=JSON.parse(localStorage.getItem(k)||'{{}}');
        d['living-spaces']=true; localStorage.setItem(k,JSON.stringify(d));
        return localStorage.getItem(k); }})()''')
    receipt = dict(key=KEY, before=before, after=after, only_changed_field='living-spaces',
                   mechanism='CDP Runtime.evaluate in the owned main renderer',
                   origin=isolation['renderer']['origin'], url=isolation['renderer']['url'],
                   isolation_receipt='flag-isolation.json', written_at=time.time())
    c.dump(out / 'flag-write.json', receipt)
    assert json.loads(after) == expected, 'Flag readback differs from the one-field change'
    with (out / 'actions.jsonl').open('a') as stream:
        stream.write(json.dumps(dict(action='isolated-desktop-decision', **receipt)) + '\n')
    reload_with_logs(c, out)
    readback = c.evaluate(out, f'localStorage.getItem({json.dumps(KEY)})')
    c.dump(out / 'flag-after-reload.json', dict(value=readback, at=time.time()))
    assert json.loads(readback) == expected, 'Flag did not survive renderer reload'


def reload_with_logs(c, out):
    c.owned(out)
    import websockets
    target = next(t for t in c.targets() if t['type'] == 'page' and '/dist/index.html' in t['url'])

    async def observe():
        events = []
        async with websockets.connect(target['webSocketDebuggerUrl'], max_size=64 << 20) as ws:
            for number, method in enumerate(['Runtime.enable', 'Log.enable', 'Page.reload'], 1):
                await ws.send(json.dumps(dict(id=number, method=method)))
                while True:
                    event = json.loads(await asyncio.wait_for(ws.recv(), 20))
                    if event.get('method') in ['Runtime.consoleAPICalled', 'Runtime.exceptionThrown', 'Log.entryAdded']:
                        events.append(event)
                    if event.get('id') == number:
                        assert 'error' not in event, event
                        break
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                try:
                    event = json.loads(await asyncio.wait_for(ws.recv(), max(.1, deadline - time.monotonic())))
                except asyncio.TimeoutError:
                    break
                if event.get('method') in ['Runtime.consoleAPICalled', 'Runtime.exceptionThrown', 'Log.entryAdded']:
                    events.append(event)
        return events

    events = asyncio.run(observe())
    c.dump(out / 'flag-reload-console.json', dict(interval_seconds=8, events=events,
                                               limitation='This is the flag-triggered page reload window, not all later native actions.'))
    c.capture(out, 'after-flag-reload')


if __name__ == '__main__':
    import argparse
    import control
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    enable(control, args.out.resolve())
