"""R1-01 qualification. Forge runs this serially against the isolated Desktop.

No app or gateway is launched. Only disposable loopback canaries are started.
Run with the Hermes venv Python, with LS_CDP_PORT pointing at the isolated app.
"""
from __future__ import annotations

import asyncio
import base64
from contextlib import ExitStack
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import re
from pathlib import Path
import socket
import socketserver
import sqlite3
import sys
import threading
import time
import traceback

SID = 'hosting-probe'
PROTECTED = ('research-desk', 'pair-play')
FIXTURE = Path(__file__).resolve().parent / 'fixtures/hosting'
NETWORK_PROBES = {'fetch', 'xhr', 'beacon', 'eventsource', 'websocket', 'image', 'link',
                  'script', 'css-url', 'css-import', 'font'}


class Canaries:
    def __init__(self):
        self.hits = []
        self.lock = threading.Lock()
        self.phase = 'control'
        self.servers = []
        self.threads = []

    def record(self, transport, **fields):
        with self.lock:
            self.hits.append({'at': time.time(), 'phase': self.phase, 'transport': transport, **fields})

    def __enter__(self):
        owner = self

        class HTTPServer(ThreadingHTTPServer):
            daemon_threads = True

            def get_request(self):
                conn, address = super().get_request()
                owner.record('http-tcp', peer=list(address))
                conn.settimeout(2)
                return conn, address

        class HTTP(BaseHTTPRequestHandler):
            def handle_one_request(self):
                # Record even malformed methods and upgrade requests before parsing.
                owner.record('http-input', peer=list(self.client_address))
                super().handle_one_request()

            def do_GET(self):
                owner.record('http', method=self.command, path=self.path)
                body = b'public hosting canary'
                self.send_response(200)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            do_POST = do_OPTIONS = do_GET

            def log_message(self, *args):
                pass

        class TCP(socketserver.BaseRequestHandler):
            def handle(self):
                owner.record('tcp', peer=list(self.client_address))
                self.request.settimeout(2)
                try:
                    data = self.request.recv(65536)
                    owner.record('tcp-bytes', bytes=len(data), data=base64.b64encode(data).decode())
                    self.request.sendall(b'HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n')
                except (TimeoutError, OSError):
                    pass

        class UDP(socketserver.BaseRequestHandler):
            def handle(self):
                data = self.request[0]
                owner.record('udp', peer=list(self.client_address), bytes=len(data),
                             data=base64.b64encode(data).decode())

        try:
            for server, handler in ((HTTPServer, HTTP), (socketserver.ThreadingTCPServer, TCP),
                                    (socketserver.ThreadingUDPServer, UDP)):
                instance = server(('127.0.0.1', 0), handler)
                instance.daemon_threads = True
                self.servers.append(instance)
                thread = threading.Thread(target=instance.serve_forever, kwargs={'poll_interval': .1}, daemon=True)
                thread.start()
                self.threads.append(thread)
            self.http_port, self.tcp_port, self.udp_port = [s.server_address[1] for s in self.servers]
            return self
        except BaseException:
            self.__exit__()
            raise

    @property
    def config(self):
        return {'http': f'http://127.0.0.1:{self.http_port}', 'ws': f'ws://127.0.0.1:{self.tcp_port}'}

    def control(self):
        import urllib.request
        with urllib.request.urlopen(self.config['http'] + '/control', timeout=3) as response:
            response.read()
        with socket.create_connection(('127.0.0.1', self.tcp_port), timeout=3) as conn:
            conn.sendall(b'GET /control HTTP/1.1\r\nUpgrade: websocket\r\n\r\n')
            conn.recv(256)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as conn:
            conn.sendto(b'hosting-control', ('127.0.0.1', self.udp_port))
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if {'http', 'tcp-bytes', 'udp'} <= {h['transport'] for h in self.hits}:
                return True
            time.sleep(.05)
        return False

    def __exit__(self, *exc):
        for server in self.servers:
            server.shutdown()
            server.server_close()
        for thread in self.threads:
            thread.join(3)


class NetworkCapture:
    """Pause new targets until Network is enabled, including descendant targets."""
    def __init__(self, page_url):
        self.page_url = page_url
        self.events = []
        self.targets = {}
        self.errors = []
        self.ready = threading.Event()
        self.stop = threading.Event()
        self.phase = 'setup'

    def __enter__(self):
        self.thread = threading.Thread(target=lambda: asyncio.run(self.capture()), daemon=True)
        self.thread.start()
        if not self.ready.wait(10) or self.errors:
            self.__exit__()
            raise RuntimeError(f'CDP capture failed to start: {self.errors}')
        return self

    async def capture(self):
        import websockets
        from cdp import Session
        try:
            async with websockets.connect(self.page_url, max_size=64 << 20) as ws:
                # The page has no Space yet, so these setup calls cannot lose guest events.
                session = Session(ws)
                await session.call('Network.enable')
                await session.call('Target.setAutoAttach', autoAttach=True, waitForDebuggerOnStart=True, flatten=True)
                self.ready.set()
                counter = session.n
                pending = {}

                async def send(method, sid, **params):
                    nonlocal counter
                    counter += 1
                    message = {'id': counter, 'method': method, 'params': params}
                    if sid:
                        message['sessionId'] = sid
                    pending[counter] = (method, sid)
                    await ws.send(json.dumps(message))

                while not self.stop.is_set():
                    try:
                        message = json.loads(await asyncio.wait_for(ws.recv(), .2))
                    except asyncio.TimeoutError:
                        continue
                    sid = message.get('sessionId')
                    if 'id' in message:
                        method, target = pending.pop(message['id'], ('unknown', sid))
                        if 'error' in message:
                            self.errors.append({'method': method, 'error': message['error']})
                            if target:
                                await send('Runtime.runIfWaitingForDebugger', target)
                        elif method == 'Network.enable':
                            if self.targets[target]['type'] == 'iframe':
                                await send('Target.setAutoAttach', target, autoAttach=True, waitForDebuggerOnStart=True, flatten=True)
                            else:
                                await send('Runtime.runIfWaitingForDebugger', target)
                        elif method == 'Target.setAutoAttach':
                            await send('Runtime.runIfWaitingForDebugger', target)
                        continue
                    method, params = message.get('method', ''), message.get('params', {})
                    if method == 'Target.attachedToTarget':
                        target = params['sessionId']
                        self.targets[target] = params['targetInfo']
                        await send('Network.enable', target)
                    if (sid and method.startswith('Network.')) or method.startswith('Target.'):
                        self.events.append({'at': time.time(), 'phase': self.phase, 'session': sid,
                                            'method': method, 'params': params})
        except Exception as error:
            self.errors.append(str(error))
            self.ready.set()

    def __exit__(self, *exc):
        self.stop.set()
        self.thread.join(5)
        if self.thread.is_alive():
            self.errors.append('capture thread did not stop')


def canonical(db, sid=None):
    """Deterministic bytes of SQL values, including exact stored JSON and blobs."""
    with sqlite3.connect(f'file:{db}?mode=ro', uri=True) as conn:
        conn.execute('BEGIN')
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        result = {}
        for table in tables:
            name = '"' + table.replace('"', '""') + '"'
            columns = [r[1] for r in conn.execute(f'PRAGMA table_info({name})')]
            if sid is None:
                rows = conn.execute(f'SELECT * FROM {name}').fetchall()
            elif table == 'spaces':
                rows = conn.execute(f'SELECT * FROM {name} WHERE id=?', (sid,)).fetchall()
            elif 'space' in columns:
                rows = conn.execute(f'SELECT * FROM {name} WHERE space=?', (sid,)).fetchall()
            elif table == 'blobs':
                shas = {sha for r in conn.execute('SELECT files FROM revisions WHERE space=?', (sid,))
                        for sha in json.loads(r[0]).values()}
                rows = [r for sha in sorted(shas) for r in conn.execute('SELECT * FROM blobs WHERE sha=?', (sha,))]
            else:
                continue
            encoded = [[{'b64': base64.b64encode(v).decode()} if isinstance(v, bytes) else v for v in row] for row in rows]
            result[table] = {'columns': columns, 'rows': sorted(encoded, key=lambda r: json.dumps(r, sort_keys=True))}
        return json.dumps(result, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    argv, sys.argv = sys.argv, [sys.argv[0], 'lib']
    try:
        import qualify_schedule as q
    finally:
        sys.argv = argv
    from guest_realm import guest, open_sessions, DB
    from cdp import _targets, page_ws

    core = q.core
    out = q.RUN / 'evidence/hosting' / time.strftime('%Y%m%d-%H%M%S')
    out.mkdir(parents=True, exist_ok=False)
    report = {'evidence_class': 'real isolated Desktop; main-world Space probes; loopback listeners; canonical SQLite',
              'status': 'RUNNING', 'checks': [], 'probes': {}, 'errors': [], 'executed': True, 'completed': False}
    before = {}
    created = None
    canary = capture = None
    log_offsets = {}

    def origin_checks():
        lines = []
        for path in (q.RUN / 'logs').glob('app-*.log'):
            start = log_offsets.get(path, path.stat().st_size)
            with path.open('rb') as log:
                log.seek(start)
                chunk = log.read()
                log_offsets[path] = log.tell()
            for line in chunk.decode(errors='replace').splitlines():
                match = re.search(r'content/browser/site_info\.cc:\d+\] Check failed: origin\.GetTupleOrPrecursorTupleIfOpaque\(\)\.IsValid\(\)\.', line)
                if match:
                    lines.append(match.group())
        return lines

    def check(name, observed, expected=True):
        passed = observed == expected
        report['checks'].append({'name': name, 'passed': passed, 'observed': observed, 'expected': expected})
        print(('PASS ' if passed else 'FAIL ') + name, flush=True)
        return passed

    def value(expression):
        reply = guest(expression)
        if not reply or not reply.get('ok'):
            raise RuntimeError(f'Guest evaluation did not complete: {reply}')
        return reply.get('value')

    def mounted():
        reply = guest('({id: space.meta?.space?.id, ready: !!window.hostingProbe?.ready})')
        return bool(reply and reply.get('ok') and reply.get('value') == {'id': SID, 'ready': True})

    def mount():
        q.evaluate('location.hash="/spaces"')
        q.wait(lambda: q.evaluate('document.querySelectorAll("iframe").length'), lambda n: n == 0, 15)
        q.wait(lambda: open_sessions(SID), lambda rows: not rows, 15)
        q.evaluate(f'location.hash="/spaces?space={SID}"')
        q.wait(mounted, bool, 30)

    def phase(name):
        canary.phase = capture.phase = name

    try:
        if os.environ.get('LIVING_SPACES_DB') and Path(os.environ['LIVING_SPACES_DB']).resolve() != DB.resolve():
            raise RuntimeError('LIVING_SPACES_DB must match the isolated guest_realm database')
        if core.db.db_path().resolve() != DB.resolve():
            raise RuntimeError('Core and guest_realm must use the same isolated database')
        if not DB.is_file():
            raise RuntimeError('Isolated Desktop database is missing')
        if SID in {space['id'] for space in core.list_spaces()}:
            raise RuntimeError('hosting-probe already exists; refusing to replace or delete it')
        # Snapshot before any UI action. Never open either protected Space.
        before = {sid: canonical(DB, sid) for sid in PROTECTED}
        for sid, data in before.items():
            (out / f'{sid}-before.sha256').write_text(hashlib.sha256(data).hexdigest() + '\n')
        if q.evaluate('document.querySelectorAll("iframe").length') != 0 or any(open_sessions(sid) for sid in PROTECTED):
            raise RuntimeError('Start on the Spaces index with protected Space sessions closed')
        log_offsets = {path: path.stat().st_size for path in (q.RUN / 'logs').glob('app-*.log')}
        report['origin_log_available'] = bool(log_offsets)

        async def browser_version(session):
            return await session.call('Browser.getVersion')

        report['browser'] = asyncio.run(q._page(browser_version))
        with ExitStack() as stack:
            canary = stack.enter_context(Canaries())
            check('HTTP, raw TCP/WebSocket and UDP listener controls received', canary.control())
            capture = stack.enter_context(NetworkCapture(page_ws()))
            stack.enter_context(q.Visible())
            phase('positive')
            files = {str(path.relative_to(FIXTURE)): path.read_text() for path in FIXTURE.rglob('*') if path.is_file()}
            fixture = core.create_space('Hosting Probe', owner='harness', author='harness-fixture', files=files,
                                        libraries=['preact'], manifest={'entry': 'index.html'})
            created = fixture['id']
            report['fixture_space'] = created
            if created != SID:
                raise RuntimeError('Core returned an unexpected fixture id')
            bundle = core.bundle(SID)
            vendor = next(f for f in bundle['files'] if f['path'] == 'vendor/preact.mjs')
            packaged = q.REPO / 'src/living-spaces/runtime/vendor/preact.mjs'
            check('fixture uses packaged runtime/vendor/preact.mjs bytes', vendor['text'] == packaged.read_text())
            mount()
            check('mounted A3 document matches the reviewed packaged guest',
                  q.evaluate('document.querySelector("iframe").srcdoc') == (q.REPO / 'src/living-spaces/guest/space-host.html').read_text())
            check('Space has opaque origin', value('window.origin'), 'null')
            check('only the fixture is mounted', value('space.meta.space.id'), SID)
            check('one open fixture bridge session', len(open_sessions(SID)), 1)
            q.wait(lambda: value('document.getElementById("local-image").complete && document.getElementById("local-image").naturalWidth'), bool, 10)
            check('local image decoded', value('document.getElementById("local-image").naturalWidth'), 32)
            check('local CSS applied', value('getComputedStyle(document.documentElement).getPropertyValue("--hosting-local-css").trim()'), 'loaded')
            check('local ES module executed', value('hostingProbe.module'), 'Local module details')
            check('vendored library executed', value('hostingProbe.library'))
            for view in ('details', 'overview'):
                value(f'document.getElementById({json.dumps(view)}).click()')
                q.wait(lambda: value('document.querySelector("[data-view]").dataset.view'), lambda v: v == view, 10)
                check(f'navigation to {view}', value('document.querySelector("[data-view]").dataset.view'), view)
            time.sleep(1)
            frame_sessions = {s for s, t in capture.targets.items() if t['type'] == 'iframe'}
            requests = [e for e in capture.events if e['phase'] == 'positive' and e['session'] in frame_sessions
                        and e['method'] == 'Network.requestWillBeSent']
            report['positive_requests'] = requests
            check('CDP captured Space frame targets before boot', bool(frame_sessions))
            check('CDP observed local blob resource requests', any(e['params']['request']['url'].startswith('blob:') for e in requests))
            check('positive app emitted no non-blob/data resource requests',
                  [e['params']['request']['url'] for e in requests if not e['params']['request']['url'].startswith(('blob:', 'data:'))], [])
            check('positive app sent zero listener traffic', [h for h in canary.hits if h['phase'] == 'positive'], [])

            phase('spoof')
            time.sleep(1.5)
            sql_before = canonical(DB)
            (out / 'spoof-before.sha256').write_text(hashlib.sha256(sql_before).hexdigest() + '\n')
            report['probes']['spoof'] = value('hostingProbe.spoof()')
            time.sleep(2)
            sql_after = canonical(DB)
            (out / 'spoof-after.sha256').write_text(hashlib.sha256(sql_after).hexdigest() + '\n')
            check('raw spoofed parent messages left all canonical SQLite values unchanged', sql_after == sql_before)
            check('bridge still works after spoofed envelopes', value("space.query('probe')"), [])
            phase('privileged')
            rows = value('hostingProbe.privileged()')
            report['probes']['privileged'] = rows
            for row in rows:
                check(f'privileged read {row["name"]} is denied or empty', row['outcome'] == 'threw' or row.get('empty') is True)
            for sid in PROTECTED:
                with sqlite3.connect(f'file:{DB}?mode=ro', uri=True) as conn:
                    collections = [r[0] for r in conn.execute('SELECT DISTINCT collection FROM records WHERE space=?', (sid,))]
                check(f'{sid} has records for cross-Space read control', bool(collections))
                for collection in collections:
                    reply = guest(f'space.query({json.dumps(collection)}, {{space:{json.dumps(sid)}}})')
                    report['probes'][f'forged-read/{sid}/{collection}'] = reply
                    check(f'forged space cannot read {sid}/{collection}', bool(reply) and (reply.get('ok') and reply.get('value') == [] or reply.get('ok') is False and reply.get('code') in ('not_granted', 'invalid')))

            config = json.dumps(canary.config)
            for realm in ('space', 'srcdoc', 'blob'):
                phase(f'network/{realm}')
                if realm == 'space':
                    rows = value(f'hostingProbe.network({config})')
                    report['probes'][realm] = rows
                else:
                    nested = value(f'hostingProbe.nested({config}, {json.dumps(realm)})')
                    report['probes'][realm] = nested
                    rows = nested.get('rows', [])
                    if realm == 'srcdoc':
                        check('fresh srcdoc actually executed the network probes', nested.get('executed') is True)
                    else:
                        check('blob child executed probes or has an observed CSP frame rejection',
                              nested.get('executed') is True or (not nested.get('started') and any(v['directive'] == 'frame-src' for v in nested['violations'])))
                if rows:
                    check(f'{realm} attempted every network API', {r['name'] for r in rows} == NETWORK_PROBES)
                check(f'{realm} network probes sent no listener traffic', [h for h in canary.hits if h['phase'] == f'network/{realm}'], [])
            for shared in (False, True):
                name = 'shared-worker' if shared else 'worker'
                phase(name)
                result = value(f'hostingProbe.worker({config}, {json.dumps(shared)})')
                report['probes'][name] = result
                check(f'{name} was denied or reported blocked fetch', result['outcome'] in ('blocked', 'threw'))
                check(f'{name} sent no listener traffic', [h for h in canary.hits if h['phase'] == name], [])

            for kind in ('location', 'top.location', 'window.open', 'anchor-top', 'meta-refresh', 'form', 'data-location', 'blob-location'):
                phase(f'navigation/{kind}')
                mount()
                host_url = q.evaluate('location.href')
                page_ids = {t['id'] for t in _targets() if t['type'] == 'page'}
                url = canary.config['http'] + '/navigation/' + kind
                report['probes'][kind] = value(f'hostingProbe.navigate({json.dumps(kind)}, {json.dumps(url)})')
                time.sleep(2)
                report['probes'][kind]['after'] = guest('window.hostingNavigation || null')
                report['probes'][kind]['origin_checks_since_previous_probe'] = origin_checks()
                check(f'{kind} left host URL unchanged', q.evaluate('location.href'), host_url)
                check(f'{kind} created no popup', {t['id'] for t in _targets() if t['type'] == 'page'} == page_ids)
                check(f'{kind} reached no listener', [h for h in canary.hits if h['phase'] == f'navigation/{kind}'], [])
                check(f'{kind} leaves a working fixture bridge', value("space.query('probe')"), [])

            phase('webrtc')
            mount()
            report['webrtc'] = value(f'hostingProbe.webrtc({canary.udp_port})')
            report['webrtc']['udp_packets'] = [h for h in canary.hits if h['phase'] == 'webrtc' and h['transport'] == 'udp']
            report['webrtc']['packet_arrived'] = bool(report['webrtc']['udp_packets'])
            report['webrtc']['asserted_blocked'] = False
            phase('settle')
            time.sleep(2)
            report['webrtc']['udp_packets'] = [h for h in canary.hits if h['phase'] in ('webrtc', 'settle') and h['transport'] == 'udp']
            report['webrtc']['packet_arrived'] = bool(report['webrtc']['udp_packets'])
            check('listeners remained active through observation', all(t.is_alive() for t in canary.threads))
            check('zero ordinary listener hits across the entire run', [h for h in canary.hits if h['phase'] != 'control' and h['transport'] != 'udp'], [])
            check('no UDP arrived outside WebRTC observation', [h for h in canary.hits if h['transport'] == 'udp' and h['phase'] not in ('control', 'webrtc', 'settle')], [])
            report['completed'] = True
    except Exception:
        report['errors'].append(traceback.format_exc())
    finally:
        if created:
            try:
                q.evaluate('location.hash="/spaces"')
                q.wait(lambda: open_sessions(created), lambda rows: not rows, 15)
                core.delete_space(created, actor='harness-fixture', confirm=created)
                check('disposable fixture deleted', created not in {space['id'] for space in core.list_spaces()})
            except Exception:
                report['errors'].append('Fixture cleanup failed\n' + traceback.format_exc())
        for sid, data in before.items():
            try:
                after = canonical(DB, sid)
                (out / f'{sid}-after.sha256').write_text(hashlib.sha256(after).hexdigest() + '\n')
                check(f'{sid} snapshot byte-for-byte unchanged', after == data)
            except Exception:
                report['errors'].append(traceback.format_exc())
        if canary:
            (out / 'listeners.json').write_text(json.dumps(canary.hits, indent=2))
        if capture:
            (out / 'network.json').write_text(json.dumps({'targets': capture.targets, 'events': capture.events, 'errors': capture.errors}, indent=2))
            check('CDP capture completed without instrumentation errors', capture.errors, [])
        report['snapshot_sha256'] = {sid: hashlib.sha256(data).hexdigest() for sid, data in before.items()}
        report['passed'] = sum(c['passed'] for c in report['checks'])
        report['total'] = len(report['checks'])
        report['status'] = 'PASS' if report['completed'] and not report['errors'] and report['total'] and report['passed'] == report['total'] else 'ISSUES'
        (out / 'hosting.json').write_text(json.dumps(report, indent=2, default=str))
        print(json.dumps({'status': report['status'], 'passed': report['passed'], 'total': report['total'], 'output': str(out)}))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
