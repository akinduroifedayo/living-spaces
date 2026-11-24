#!/Users/ifedayoakinduro/.hermes/hermes-agent/venv/bin/python
"""Drive only a manifest-owned disposable Living Spaces Desktop."""
import argparse
import asyncio
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.request

PYTHON = '/Users/ifedayoakinduro/.hermes/hermes-agent/venv/bin/python'
RUNTIME = '/Users/ifedayoakinduro/.hermes/hermes-agent'
APP = '/Applications/Hermes.app/Contents/MacOS/Hermes'
PORT = 19432
BASE = '4aea12db5375b30e90b5e0fa8f7d12ad7e0fdf98'
CANDIDATE = '8008dcc'


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, default=str) + '\n')


def processes():
    text = subprocess.check_output(['ps', '-axo', 'pid=,ppid=,pgid=,lstart=,command='], text=True)
    rows = []
    for line in text.splitlines():
        parts = line.strip().split(None, 8)
        if len(parts) == 9:
            rows.append(dict(pid=int(parts[0]), ppid=int(parts[1]), pgid=int(parts[2]),
                             started=' '.join(parts[3:8]), command=parts[8]))
    return rows


def free_port():
    listeners = subprocess.run(['lsof', '-nP', '-iTCP:19432', '-sTCP:LISTEN'], capture_output=True, text=True)
    assert listeners.returncode == 1 and not listeners.stdout, 'CDP port already has a listener'
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('127.0.0.1', PORT))


def targets():
    with urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json/list', timeout=3) as reply:
        return json.load(reply)


def manifest(out):
    return json.loads((out / 'instance.json').read_text())


def env(state):
    return dict(HOME=str(state / 'os-home'), USER=os.environ.get('USER', ''),
                PATH=f'{Path(PYTHON).parent}:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin',
                LANG='en_US.UTF-8', TMPDIR=str(state / 'tmp'), PYTHONDONTWRITEBYTECODE='1',
                HERMES_HOME=str(state / 'home'), HERMES_DESKTOP_USER_DATA_DIR=str(state / 'ud'),
                HERMES_DESKTOP_CWD=str(state / 'cwd'), HERMES_DESKTOP_ISOLATED_BACKEND='1',
                HERMES_DESKTOP_APP_NAME='Hermes W32 Verification', HERMES_DESKTOP_SKIP_QUIT_CONFIRM='1',
                HERMES_DESKTOP_HERMES_ROOT=RUNTIME, HERMES_DESKTOP_PYTHON=PYTHON,
                HERMES_DISABLE_LAZY_INSTALLS='1')


def launch(out, repo, acquisition=None):
    out.mkdir(parents=True, exist_ok=False)
    if acquisition is not None:
        acquisition['created'] = True
    state = out / 'state'
    for part in ['os-home', 'home', 'ud', 'tmp', 'cwd']:
        (state / part).mkdir(parents=True)
    source = repo / 'src/living-spaces'
    checkout_head = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
    product_tree = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD:src/living-spaces'], text=True).strip()
    revision = None
    for pin in [BASE, CANDIDATE]:
        tree = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', f'{pin}:src/living-spaces'], text=True).strip()
        if tree == product_tree:
            revision = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', pin], text=True).strip()
            break
    assert revision, f'Unsupported product tree at {checkout_head}'
    dirty = subprocess.check_output(['git', '-C', str(repo), 'status', '--porcelain', '--untracked-files=all', '--', 'src/living-spaces'], text=True)
    assert not dirty, f'Product working tree differs from pin: {dirty}'
    files = {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in source.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    dump(out / 'product-pin.json', dict(revision=revision, files=files))
    shutil.copytree(source, state / 'home/plugins/living-spaces')
    shutil.copytree(source / 'desktop', state / 'home/desktop-plugins/living-spaces')
    e = env(state)
    (state / 'home/config.yaml').write_text('plugins:\n  enabled: [living-spaces]\n')
    dump(out / 'prepare.json', dict(empty_home_before=True, credentials_copied=False,
                                    config='new disposable verification config, plugin only',
                                    lazy_installs_disabled=True))
    free_port()
    log = (out / 'desktop.log').open('wb')
    argv = [APP, f'--remote-debugging-port={PORT}', '--remote-debugging-address=127.0.0.1']
    proc = subprocess.Popen(argv, env=e, cwd=state / 'cwd', stdout=log, stderr=log, start_new_session=True)
    row = next(p for p in processes() if p['pid'] == proc.pid)
    dump(out / 'instance.json', dict(pid=proc.pid, pgid=proc.pid, started=row['started'], port=PORT,
                                    state=str(state), repo=str(repo), argv=argv, revision=revision))
    deadline = time.monotonic() + 100
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f'Desktop exited {proc.returncode}')
        try:
            pages = targets()
            if any(t['type'] == 'page' and '/dist/index.html' in t['url'] for t in pages):
                dump(out / 'launch-targets.json', pages)
                return
        except (OSError, ValueError):
            pass
        time.sleep(.5)
    raise TimeoutError('No owned Desktop CDP page after 100s')


def owned(out):
    m = manifest(out)
    row = next((p for p in processes() if p['pid'] == m['pid']), None)
    assert row and row['started'] == m['started'] and row['pgid'] == m['pgid'], 'Owned PID identity changed'
    assert row['command'].startswith(APP + ' '), 'Owned PID is not the launched Desktop'
    listeners = subprocess.check_output(['lsof', '-nP', '-iTCP:19432', '-sTCP:LISTEN', '-Fpn'], text=True)
    assert f"p{m['pid']}\n" in listeners and '127.0.0.1:19432' in listeners, 'CDP listener not owned loopback'
    return m


def call_many(out, commands):
    """Keep a complete native gesture in one debugger session."""
    owned(out)
    import websockets
    page = next(t for t in targets() if t['type'] == 'page' and '/dist/index.html' in t['url'])
    async def invoke():
        replies = []
        async with websockets.connect(page['webSocketDebuggerUrl'], max_size=64 << 20) as ws:
            for number, (method, params) in enumerate(commands, 1):
                await ws.send(json.dumps(dict(id=number, method=method, params=params)))
                while True:
                    value = json.loads(await asyncio.wait_for(ws.recv(), 20))
                    if value.get('id') == number:
                        assert 'error' not in value, value
                        replies.append(value['result'])
                        break
        return replies
    return asyncio.run(invoke())


def call(out, method, **params):
    return call_many(out, [(method, params)])[0]


def evaluate(out, expression):
    reply = call(out, 'Runtime.evaluate', expression=expression, returnByValue=True, awaitPromise=True)
    assert 'exceptionDetails' not in reply, reply
    return reply.get('result', {}).get('value')


def capture(out, name):
    result = call(out, 'Page.captureScreenshot', format='png')
    (out / (name + '.png')).write_bytes(base64.b64decode(result['data']))
    dump(out / (name + '.ax.json'), call(out, 'Accessibility.getFullAXTree'))
    (out / (name + '.txt')).write_text(evaluate(out, 'document.body.innerText'))


def click(out, selector):
    call(out, 'Page.bringToFront')
    time.sleep(.2)
    query = (f'[...document.querySelectorAll("button,[role=button],a,[role=menuitem]")].filter(e=>e.textContent.trim()==={json.dumps(selector[5:])})'
             if selector.startswith('text=') else f'[...document.querySelectorAll({json.dumps(selector)})]')
    expr = f'''(() => {{ const els={query}.filter(e=>e.getClientRects().length); if(els.length!==1) throw Error('Expected one visible target, got '+els.length); const r=els[0].getBoundingClientRect(); return {{x:r.x+r.width/2,y:r.y+r.height/2}}; }})()'''
    pos = evaluate(out, expr)
    call_many(out, [('Page.bringToFront', {}),
                    ('Input.dispatchMouseEvent', dict(type='mouseMoved', **pos)),
                    ('Input.dispatchMouseEvent', dict(type='mousePressed', button='left', clickCount=1, **pos)),
                    ('Input.dispatchMouseEvent', dict(type='mouseReleased', button='left', clickCount=1, **pos))])
    with (out / 'actions.jsonl').open('a') as stream:
        stream.write(json.dumps(dict(action='click', selector=selector, coordinates=pos, at=time.time())) + '\n')


def wait_text(out, text, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if text in evaluate(out, 'document.body.innerText'):
            return
        time.sleep(.5)
    capture(out, 'wait-failed')
    raise TimeoutError(f'Visible text not found: {text}')


def doctor(out):
    m = owned(out)
    cfg = Path(m['state']) / 'home/config.yaml'
    import yaml
    assert 'living-spaces' in yaml.safe_load(cfg.read_text())['plugins']['enabled'], 'Backend half not enabled'
    text = evaluate(out, 'document.body.innerText')
    result = dict(pid=m['pid'], revision=m['revision'], cdp_port=PORT, scope=m['state'],
                  plugin_copied=(Path(m['state']) / 'home/desktop-plugins/living-spaces/plugin.js').is_file(),
                  spaces_text_present='Spaces' in text, auth='not configured; no model journeys authorized',
                  usable='Build your first Space in chat' in text or 'data-testid="spaces-index"' in evaluate(out, 'document.body.innerHTML'))
    print(json.dumps(result))
    assert result['usable'], 'Desktop is not usable at the Spaces index'
    return result


def owned_backends(out):
    """Find detached gateway processes by exact, newly-created HERMES_HOME."""
    home = str(out / 'state/home')
    hits = []
    for row in processes():
        if ' -m hermes_cli.main ' not in row['command'] or ' gateway run ' not in row['command']:
            continue
        raw = subprocess.run(['ps', 'eww', '-p', str(row['pid']), '-o', 'command='], capture_output=True, text=True)
        if f'HERMES_HOME={home} ' in raw.stdout or raw.stdout.rstrip().endswith(f'HERMES_HOME={home}'):
            hits.append(row)
    return hits


def preserve(out, state):
    logs = state / 'home/logs'
    if logs.exists():
        shutil.copytree(logs, out / 'backend-logs', dirs_exist_ok=True)
    dbpath = state / 'home/plugin-data/living-spaces/spaces.db'
    if dbpath.exists():
        with sqlite3.connect(f'file:{dbpath}?mode=ro', uri=True) as conn:
            (out / 'persisted-spaces.sql').write_text('\n'.join(conn.iterdump()))


def cleanup(out):
    try:
        _cleanup(out)
    except BaseException as error:
        m = manifest(out)
        state = Path(m['state'])
        assert state.parent == out and state.name == 'state'
        preservation_error = None
        try:
            preserve(out, state)
        except Exception as export_error:
            preservation_error = str(export_error)
        dump(out / 'cleanup-failed.json', dict(error=str(error), state_removed=not state.exists(),
                                              preservation_error=preservation_error))
        raise


def _cleanup(out):
    m = manifest(out)
    state = Path(m['state'])
    assert state.parent == out and state.name == 'state'
    backends = owned_backends(out)
    dump(out / 'owned-backends-before-cleanup.json', backends)
    rows = processes()
    current = next((p for p in rows if p['pid'] == m['pid']), None)
    tracked = []
    if current:
        assert current['started'] == m['started'] and current['pgid'] == m['pgid'], 'Refusing recycled PID'
        tracked = [p for p in rows if p['pgid'] == m['pgid']]
        dump(out / 'cleanup-before.json', tracked)
        os.kill(m['pid'], signal.SIGTERM)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and any(p['pid'] == m['pid'] for p in processes()):
            time.sleep(.25)
        remaining = [p for p in processes() if p['pgid'] == m['pgid']]
        if remaining:
            os.killpg(m['pgid'], signal.SIGTERM)
            time.sleep(2)
        if any(p['pgid'] == m['pgid'] for p in processes()):
            os.killpg(m['pgid'], signal.SIGKILL)
            time.sleep(1)
    else:
        # Without the leader, group membership alone is insufficient ownership evidence.
        tracked = [p for p in rows if p['pgid'] == m['pgid']]
        dump(out / 'cleanup-before.json', tracked)
        for child in tracked:
            assert str(state / 'ud') in child['command'], 'Unproven orphan ownership; refusing signal'
            live = next((p for p in processes() if p['pid'] == child['pid']), None)
            if live:
                assert live['started'] == child['started'] and live['pgid'] == child['pgid'], 'Recycled orphan PID'
                os.kill(child['pid'], signal.SIGTERM)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and any(p['pgid'] == m['pgid'] for p in processes()):
            time.sleep(.1)
        for child in tracked:
            live = next((p for p in processes() if p['pid'] == child['pid']), None)
            if live:
                assert live['started'] == child['started'] and live['pgid'] == child['pgid'], 'Recycled orphan PID'
                os.kill(child['pid'], signal.SIGKILL)
        time.sleep(.2)
    for backend in backends:
        current_backend = next((p for p in processes() if p['pid'] == backend['pid']), None)
        if current_backend:
            assert current_backend['started'] == backend['started'], 'Refusing recycled backend PID'
            assert backend['pgid'] == backend['pid'], 'Unexpected gateway process group'
            os.kill(backend['pid'], signal.SIGTERM)
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline and owned_backends(out):
        time.sleep(.25)
    for backend in owned_backends(out):
        assert any(p['pid'] == backend['pid'] and p['started'] == backend['started'] for p in backends)
        os.kill(backend['pid'], signal.SIGKILL)
    time.sleep(.5)
    remaining = [p for p in processes() if p['pgid'] == m['pgid'] or str(state / 'ud') in p['command']]
    remaining += owned_backends(out)
    assert not remaining, remaining
    # Do not demand another attempt's owned listener to be gone when repairing older teardown.
    listener = subprocess.run(['lsof', '-nP', '-iTCP:19432', '-sTCP:LISTEN'], capture_output=True, text=True)
    port_free = listener.returncode == 1 and not listener.stdout
    preserve(out, state)
    if state.exists():
        shutil.rmtree(state)
    dump(out / 'cleanup.json', dict(owned_processes_remaining=remaining, cdp_port_free=port_free,
                                   state_removed=not state.exists(), evidence_retained=[p.name for p in out.iterdir() if p.is_file()]))


def key(out, value):
    keys = {'Enter': ('Enter', 13), 'Escape': ('Escape', 27), 'Tab': ('Tab', 9)}
    name, code = keys[value]
    call_many(out, [('Input.dispatchKeyEvent', dict(type=kind, key=name, windowsVirtualKeyCode=code))
                    for kind in ['keyDown', 'keyUp']])
    with (out / 'actions.jsonl').open('a') as stream:
        stream.write(json.dumps(dict(action='key', key=value, at=time.time())) + '\n')


def fill(out, selector, value):
    click(out, selector)
    commands = [('Input.dispatchKeyEvent', dict(type='keyDown', key='a', code='KeyA', modifiers=4, commands=['selectAll'])),
                ('Input.dispatchKeyEvent', dict(type='keyUp', key='a', code='KeyA', modifiers=4))]
    commands += [('Input.insertText', dict(text=value))] if value else [
        ('Input.dispatchKeyEvent', dict(type='keyDown', key='Backspace', windowsVirtualKeyCode=8)),
        ('Input.dispatchKeyEvent', dict(type='keyUp', key='Backspace', windowsVirtualKeyCode=8))]
    call_many(out, commands)
    with (out / 'actions.jsonl').open('a') as stream:
        stream.write(json.dumps(dict(action='fill', selector=selector, value=value, at=time.time())) + '\n')


def fixture(out):
    m = owned(out)
    result = subprocess.run([PYTHON, str(Path(__file__).with_name('fixture.py')), m['repo'], str(out)],
                            env={**env(Path(m['state'])), 'PYTHONPATH': RUNTIME},
                            capture_output=True, text=True, timeout=30)
    (out / 'fixture.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stdout + result.stderr


def records(out):
    m = owned(out)
    path = Path(m['state']) / 'home/plugin-data/living-spaces/spaces.db'
    with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as conn:
        conn.execute('PRAGMA query_only=ON')
        result = {}
        for table in ['spaces', 'records', 'grants', 'audit']:
            if not conn.execute('SELECT 1 FROM sqlite_master WHERE type=? AND name=?', ('table', table)).fetchone():
                continue
            cursor = conn.execute(f'SELECT * FROM {table}')
            result[table] = [dict(zip([d[0] for d in cursor.description], row)) for row in cursor.fetchall()]
    dump(out / f'records-{time.time_ns()}.json', result)
    print(json.dumps(result))
    return result


def setup(out):
    wait_text(out, 'Skip setup')
    capture(out, 'before-skip')
    click(out, 'text=Skip setup')
    wait_text(out, 'No thanks')
    click(out, 'text=No thanks')
    wait_text(out, 'Capabilities')
    click(out, 'text=Capabilities')
    wait_text(out, 'Plugins')
    click(out, 'button[data-tour="tab-plugins"]')
    time.sleep(2)
    selector = 'button[role="switch"][aria-label="Spaces"]'
    if not evaluate(out, f'!!document.querySelector({json.dumps(selector)})'):
        call_many(out, [('Input.dispatchKeyEvent', dict(type='keyDown', key='k', code='KeyK', modifiers=4)),
                        ('Input.dispatchKeyEvent', dict(type='keyUp', key='k', code='KeyK', modifiers=4))])
        fill(out, 'input[role="combobox"]', 'Reload desktop plugins')
        capture(out, 'before-plugin-reload')
        click(out, '[role="option"]')
        time.sleep(3)
        assert not evaluate(out, '!!document.querySelector("input[role=combobox]")'), 'Native reload command did not close its palette'
    capture(out, 'plugin-inventory')
    if not evaluate(out, f'!!document.querySelector({json.dumps(selector)})'):
        raise RuntimeError('Living Spaces is missing from native plugin inventory; see plugin-inventory artifacts')
    if evaluate(out, f'document.querySelector({json.dumps(selector)}).getAttribute("aria-checked")') != 'true':
        click(out, selector)
    wait_text(out, 'Spaces')
    click(out, 'text=Spaces')
    wait_text(out, 'Build your first Space in chat')
    capture(out, 'empty-spaces')


def guest_read(out, selector='body', position=False):
    """Read DOM in debugger execution contexts; never execute application methods."""
    owned(out)
    import websockets
    async def inspect():
        results = []
        for target in targets():
            if target['type'] not in ['page', 'iframe']:
                continue
            async with websockets.connect(target['webSocketDebuggerUrl'], max_size=64 << 20) as ws:
                await ws.send(json.dumps(dict(id=1, method='Runtime.enable')))
                contexts = []
                while True:
                    row = json.loads(await asyncio.wait_for(ws.recv(), 10))
                    if row.get('method') == 'Runtime.executionContextCreated':
                        ctx = row['params']['context']
                        if ctx.get('auxData', {}).get('isDefault'):
                            contexts.append(ctx['id'])
                    if row.get('id') == 1:
                        break
                expression = f'''(() => {{const es=[...document.querySelectorAll({json.dumps(selector)})].filter(e=>e.getClientRects().length); if(es.length!==1) return null; const e=es[0]; const r=e.getBoundingClientRect(); return {{text:e.innerText,value:e.value,x:r.x+r.width/2,y:r.y+r.height/2}} }})()'''
                for number, context in enumerate(contexts, 2):
                    await ws.send(json.dumps(dict(id=number, method='Runtime.evaluate', params=dict(
                        expression=expression, contextId=context, returnByValue=True))))
                    while True:
                        row = json.loads(await asyncio.wait_for(ws.recv(), 10))
                        if row.get('id') == number:
                            value = row.get('result', {}).get('result', {}).get('value')
                            if value and (selector != 'body' or 'Verification Notebook' in value.get('text', '')):
                                results.append(dict(target=target['id'], **value))
                            break
        return results
    matches = asyncio.run(inspect())
    if selector == 'body':
        return matches
    assert len(matches) == 1, f'Expected one guest target, got {len(matches)}: {matches}'
    if position:
        offset = evaluate(out, '''(() => {const e=document.querySelector('iframe[title="Space: Verification Notebook"]'); if(!e) throw Error('Missing native canvas frame'); const r=e.getBoundingClientRect(); return {x:r.x,y:r.y}})()''')
        return dict(x=offset['x'] + matches[0]['x'], y=offset['y'] + matches[0]['y'])
    return matches[0]


def guest_click(out, selector):
    pos = guest_read(out, selector, position=True)
    assert isinstance(pos, dict)
    call_many(out, [('Page.bringToFront', {}),
                    ('Input.dispatchMouseEvent', dict(type='mouseMoved', **pos)),
                    ('Input.dispatchMouseEvent', dict(type='mousePressed', button='left', clickCount=1, **pos)),
                    ('Input.dispatchMouseEvent', dict(type='mouseReleased', button='left', clickCount=1, **pos))])
    with (out / 'actions.jsonl').open('a') as stream:
        stream.write(json.dumps(dict(action='guest-click', selector=selector, coordinates=pos, at=time.time())) + '\n')


def guest_fill(out, selector, value):
    guest_click(out, selector)
    call(out, 'Input.insertText', text=value)
    with (out / 'actions.jsonl').open('a') as stream:
        stream.write(json.dumps(dict(action='guest-fill', selector=selector, value=value, at=time.time())) + '\n')


def diagnostic(out):
    m = owned(out)
    status = evaluate(out, 'window.__HERMES_PLUGIN_SDK__.host.status()')
    assert status.get('hermes_home') == str(Path(m['state']) / 'home'), 'Wrong backend home'
    inventory = evaluate(out, 'window.__HERMES_PLUGIN_SDK__.host.request("plugins.manage",{action:"list"})')
    entries = evaluate(out, f'Promise.all({json.dumps([str(Path(m["state"]) / "home/desktop-plugins"), str(Path(m["state"]) / "home/desktop-plugins/living-spaces")])}.map(p=>window.hermesDesktop.readDir(p)))')
    report = dict(status=status, living_spaces=[p for p in inventory.get('plugins', []) if p['name'] == 'living-spaces'],
                  directory_entries=entries, desktop_switches=evaluate(out, '[...document.querySelectorAll("[role=switch]")].map(e=>({name:e.getAttribute("aria-label"),on:e.getAttribute("aria-checked")}))'))
    dump(out / 'diagnostic.json', report)
    return report


def jobs(out):
    m = owned(out)
    status = evaluate(out, 'window.__HERMES_PLUGIN_SDK__.host.status()')
    assert status['hermes_home'] == str(Path(m['state']) / 'home')
    result = evaluate(out, 'window.__HERMES_PLUGIN_SDK__.host.request("cron.manage",{action:"list",include_disabled:true})')
    dump(out / f'native-jobs-{time.time_ns()}.json', result)
    print(json.dumps(result))
    return result


def inspect_tool(out):
    m = owned(out)
    result = subprocess.run([PYTHON, str(Path(__file__).with_name('inspection_tool.py')), m['repo'], str(out)],
                            env={**env(Path(m['state'])), 'PYTHONPATH': RUNTIME}, capture_output=True, text=True, timeout=60)
    (out / 'inspection-tool.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stdout + result.stderr


def cleanup_acquired(out, acquisition):
    if not acquisition.get('created'):
        return
    if (out / 'instance.json').exists():
        cleanup(out)
    else:
        state = out / 'state'
        if state.exists():
            shutil.rmtree(state)
        dump(out / 'cleanup.json', dict(state_removed=not state.exists(), process_never_recorded=True))


def proof(out, repo):
    result = dict(primary_desktop='unmet', secondary_inspection='not requested', stop_interruption='unverified')
    acquisition = {}
    try:
        launch(out, repo, acquisition)
        try:
            setup(out)
            dump(out / 'doctor.json', doctor(out))
            fixture(out)
            # Native card entry; the fixture preparation above is not chat creation.
            click(out, 'a[href="#/spaces?space=verification-notebook"]')
            time.sleep(3)
            capture(out, 'before-save')
            guest_fill(out, 'input[aria-label="Note"]', 'W32 persisted note')
            guest_click(out, 'button[type="submit"]')
            time.sleep(2)
            capture(out, 'after-save')
            status = guest_read(out, '#status')
            notes = guest_read(out, '#notes')
            assert isinstance(status, dict) and status.get('text') == 'Note saved', 'Visible in-canvas save success missing'
            assert isinstance(notes, dict) and 'W32 persisted note' in notes.get('text', ''), 'Visible saved note missing'
            saved = records(out)
            assert any('W32 persisted note' in str(row) for row in saved['records']), 'No persisted note'
            click(out, 'text=Spaces')
            click(out, 'a[href="#/spaces?space=verification-notebook"]')
            time.sleep(3)
            capture(out, 'after-reopen')
            assert any('W32 persisted note' in row.get('text', '') for row in guest_read(out))
            result['primary_desktop'] = 'passed: records-save + records-reopen via native input'
        except Exception as error:
            result['primary_error'] = str(error)
            capture(out, 'primary-blocked')
            diagnostic(out)
            try:
                doctor(out)
            except Exception as doctor_error:
                result['doctor_error'] = str(doctor_error)
        if manifest(out)['revision'].startswith(CANDIDATE):
            if not (out / 'fixture-create.json').exists():
                fixture(out)
            try:
                inspect_tool(out)
                result['secondary_inspection'] = 'see inspection-proof.json; headless tool-handler proof only'
            except Exception as error:
                result['secondary_inspection'] = 'failed: ' + str(error)
        dump(out / 'result.json', result)
    finally:
        cleanup_acquired(out, acquisition)
    assert result['primary_desktop'].startswith('passed'), result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['launch', 'setup', 'doctor', 'capture', 'click', 'fill', 'key', 'read',
                                          'guest-click', 'guest-fill', 'guest-read', 'fixture', 'records', 'diagnostic',
                                          'inspect', 'jobs', 'proof', 'cleanup'])
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[4])
    parser.add_argument('--value')
    parser.add_argument('--selector')
    args = parser.parse_args()
    out = args.out.resolve()
    if args.command == 'proof':
        proof(out, args.repo.resolve())
    elif args.command == 'launch':
        acquisition = {}
        try:
            launch(out, args.repo.resolve(), acquisition)
        except BaseException:
            cleanup_acquired(out, acquisition)
            raise
    elif args.command == 'doctor':
        doctor(out)
    elif args.command == 'capture':
        assert args.value and '/' not in args.value
        capture(out, args.value)
    elif args.command == 'click':
        click(out, args.value)
    elif args.command == 'fill':
        fill(out, args.selector, args.value)
    elif args.command == 'key':
        key(out, args.value)
    elif args.command == 'read':
        print(evaluate(out, 'document.body.innerText'))
    elif args.command == 'guest-click':
        guest_click(out, args.value)
    elif args.command == 'guest-fill':
        guest_fill(out, args.selector, args.value)
    elif args.command == 'guest-read':
        print(json.dumps(guest_read(out)))
    elif args.command == 'setup':
        setup(out)
    elif args.command == 'fixture':
        fixture(out)
    elif args.command == 'records':
        records(out)
    elif args.command == 'diagnostic':
        print(json.dumps(diagnostic(out)))
    elif args.command == 'jobs':
        jobs(out)
    elif args.command == 'inspect':
        inspect_tool(out)
    else:
        cleanup(out)


if __name__ == '__main__':
    main()
