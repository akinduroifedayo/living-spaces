"""Remaining R1 partials. Run only against Forge's isolated Desktop.

The refresh fixture uses the real core worker with an injected, gated RSS fetch;
guest writes still cross the mounted Desktop bridge. No external feed or timing
luck is needed. Ambiguous prose requires a trace-bound semantic review when no
correlated tool result carries the structured ambiguous error.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import threading
import time
from unittest.mock import patch

STEPS = ('ambiguous', 'stale-refresh', 'incompatible-restore', 'frame-reload')
REPO = Path(__file__).resolve().parents[1]
PROTECTED = ('research-desk', 'pair-play')
TABLES = ('spaces', 'revisions', 'records', 'changes', 'recovery_points', 'grants', 'runs', 'schedules', 'audit', 'logs')


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def review_ambiguity(path):
    review = json.loads(path.read_text())
    evidence_path = Path(review['evidence'])
    evidence = json.loads(evidence_path.read_text())
    assert evidence['step'] == 'ambiguous' and evidence['status'] == 'NEEDS_REVIEW'
    assert all(c['passed'] for c in evidence['checks']), 'Cannot override a failed preservation check'
    assert review['trace_sha256'] == digest(evidence['trace']), 'Review belongs to another trace'
    assert review['asks_which_space'] is True and review['rationale'].strip(), 'Semantic clarification review required'
    evidence['semantic_review'] = review
    evidence['status'] = 'PASS'
    reviewed = evidence_path.with_name(evidence_path.stem + '-reviewed.json')
    reviewed.write_text(json.dumps(evidence, indent=2))
    print(f'PASS trace-reviewed clarification: {reviewed}')


class Qualification:
    def __init__(self, args):
        saved, sys.argv = sys.argv, [sys.argv[0], 'lib']
        try:
            import qualify_schedule as q
        finally:
            sys.argv = saved
        import guest_realm
        self.q, self.core, self.guest = q, q.core, guest_realm.guest
        self.open_sessions = guest_realm.open_sessions
        self.db = q.RUN / 'home/plugin-data/living-spaces/spaces.db'
        os.environ['LIVING_SPACES_DB'] = str(self.db)
        assert guest_realm.DB == self.db
        self.args = args
        self.out = q.RUN / 'evidence/partials' / f'{time.time_ns()}-{args.step}'
        self.out.mkdir(parents=True)
        self.fixtures = []
        self.result = {'step': args.step, 'status': 'RUNNING', 'checks': [], 'fixtures': self.fixtures,
                       'evidence_class': 'isolated Desktop; native host controls; guest bridge; canonical SQLite'}

    def check(self, name, observed, expected=True):
        passed = observed == expected
        self.result['checks'].append({'name': name, 'passed': passed, 'observed': observed, 'expected': expected})
        print(('PASS ' if passed else 'FAIL ') + name, flush=True)
        if not passed:
            raise AssertionError(name)

    def snapshot(self, sid):
        with sqlite3.connect(f'file:{self.db}?mode=ro', uri=True) as conn:
            conn.execute('BEGIN')
            return encoded({table: conn.execute(
                f'SELECT * FROM {table} WHERE {"id" if table == "spaces" else "space"}=? ORDER BY rowid',
                (sid,)).fetchall() for table in TABLES})

    def records(self, sid):
        with sqlite3.connect(f'file:{self.db}?mode=ro', uri=True) as conn:
            return encoded(conn.execute('SELECT * FROM records WHERE space=? ORDER BY collection,id', (sid,)).fetchall())

    def create(self, name, manifest=None):
        self.check(f'{name} fixture name is unused', any(s['name'] == name for s in self.core.list_spaces()), False)
        sid = self.core.create_space(name, owner='harness', author='harness-fixture', manifest=manifest,
                                     files={'index.html': '<!doctype html><html><body><main>Public partials fixture</main></body></html>'})['id']
        self.fixtures.append(sid)
        return sid

    def mount(self, sid):
        self.q.close_sheets()
        self.q.evaluate(f'location.hash={json.dumps("/spaces?space=" + sid)}')
        self.q.wait(lambda: self.guest('space.meta'),
                    lambda v: v and v.get('ok') and (v.get('value') or {}).get('space', {}).get('id') == sid, 30, .5)
        self.q.wait(lambda: self.open_sessions(sid), lambda v: len(v) == 1, 20)

    def put(self, record, note):
        args = ','.join(map(json.dumps, ['papers', record['id'], {'notes': note}, {'baseRev': record['rev']}]))
        return self.guest(f'space.put({args}).then(record => ({{accepted: true, record}}), '
                          'error => ({accepted: false, code: error.code, current: error.current, message: error.message}))')

    def ambiguous(self):
        from chat_turn import submit, STATE
        sid = self.create('Research Notes')
        self.check('ambiguous fixture has the requested id', sid, 'research-notes')
        self.core.records.put(sid, 'notes', 'public-note', {'text': 'Original public fixture note'}, actor='harness-fixture', base_rev=0)
        before = {s: self.snapshot(s) for s in ('research-desk', sid)}
        with sqlite3.connect(f'file:{STATE}?mode=ro', uri=True) as conn:
            self.check('chat session exists', conn.execute('SELECT count(*) FROM sessions WHERE id=?',
                                                          (self.args.chat_session,)).fetchone()[0], 1)
            self.check('chat has no earlier user turn selecting a Space', conn.execute(
                "SELECT count(*) FROM messages WHERE session_id=? AND role='user'",
                (self.args.chat_session,)).fetchone()[0], 0)
        prompt = 'Add a note to my research space saying Public partials qualification note.'
        self.result['prompt'] = prompt
        self.result['chat_session'] = self.args.chat_session
        turn = submit(self.args.chat_session, prompt)
        with sqlite3.connect(f'file:{STATE}?mode=ro', uri=True) as conn:
            conn.row_factory = sqlite3.Row
            trace = [dict(r) for r in conn.execute(
                'SELECT id,timestamp,role,content,tool_calls,tool_call_id,tool_name,finish_reason FROM messages '
                'WHERE session_id=? AND timestamp>=? ORDER BY id', (self.args.chat_session, turn['sent_at']))]
        self.result['trace'] = trace
        self.result['trace_sha256'] = digest(trace)
        self.result['turn'] = turn
        for s in before:
            after = self.snapshot(s)
            (self.out / f'{s}-before.json').write_bytes(before[s])
            (self.out / f'{s}-after.json').write_bytes(after)
            self.check(f'{s} unchanged by ambiguous request', after == before[s])
        self.check('trace contains the submitted user turn', any(r['role'] == 'user' and r['content'] == prompt for r in trace))
        finals = [r for r in trace if r['role'] == 'assistant' and not r['tool_calls'] and r['finish_reason'] in ('stop', 'end_turn')]
        self.check('trace contains a completed assistant reply', bool(finals) and bool(finals[-1]['content']))
        calls = {}
        errors = []
        for row in trace:
            if row['role'] == 'assistant' and row['tool_calls']:
                for call in json.loads(row['tool_calls']):
                    calls[call.get('id')] = call.get('function', call).get('name', '')
            if row['role'] != 'tool' or not calls.get(row['tool_call_id'], '').startswith('spaces_'):
                continue
            try:
                body = json.loads(row['content'])
            except (ValueError, TypeError):
                continue
            if isinstance(body, dict) and body.get('ok') is False and (body.get('error') or {}).get('code') == 'ambiguous':
                errors.append({'message_id': row['id'], 'call_id': row['tool_call_id'], 'error': body['error']})
        self.result['ambiguous_tool_errors'] = errors
        if not errors:
            self.result['status'] = 'NEEDS_REVIEW'
            print('Read the entire trace in partials.json. Supply a review JSON with evidence (path), trace_sha256, '
                  'asks_which_space (boolean), and rationale. Run ambiguous --review REVIEW.json. '
                  'A keyword match is not a review.', flush=True)

    def stale_refresh(self):
        from living_spaces_core import feeds, runs
        feed = (REPO / 'tests/python/fixtures/feeds/research.rss').read_bytes()
        sid = self.create('Partials Refresh', {'data': {'version': 1}, 'upkeep': {'handler': 'feed', 'sources': [
            {'id': 'demo', 'url': 'https://research.example/feed', 'collection': 'papers'}]}})
        self.core.decide(sid, 'refresh', 'grant', actor='harness-fixture')
        with patch.object(feeds, 'fetch', return_value=feed):
            self.check('seed source refresh succeeds', runs.start_refresh(sid, trigger='manual', actor='harness-fixture', wait=True)['status'], 'succeeded')
        record = next(r for r in self.core.query(sid, 'papers')['records'] if r['source']['title'] == 'Small Models for Imaginary Gardens')
        self.mount(sid)
        current = self.guest(f'space.get("papers", {json.dumps(record["id"])})')
        self.check('guest reads the current record', current, {'ok': True, 'value': record})
        cursor = self.core.query(sid, 'papers')['seq']
        entered, release = threading.Event(), threading.Event()
        outcome = []

        def fetch(space, url):
            entered.set()
            if not release.wait(45):
                raise TimeoutError('Guest edit did not release fixture fetch')
            return feed.replace(b'Small Models for Imaginary Gardens', b'Updated Public Research')

        def refresh():
            outcome.append(runs.start_refresh(sid, trigger='manual', actor='harness-fixture', wait=True))

        self.result['refresh_fixture'] = 'Real local core worker; injected gated public RSS bytes; real Desktop guest writes. No HTTP request or host Refresh now click.'
        with patch.object(feeds, 'fetch', side_effect=fetch):
            worker = threading.Thread(target=refresh)
            worker.start()
            try:
                self.check('refresh reaches the fetch barrier', entered.wait(15))
                self.check('refresh is running during guest edit', self.core.list_runs(sid)[0]['status'], 'running')
                saved = self.put(record, 'User note saved during refresh')
                self.result['guest_edit'] = saved
                self.check('guest edit succeeds at its current rev', saved and saved.get('ok') and saved['value'].get('accepted'))
                saved_record = saved['value']['record']
                self.check('guest edit advances the rev once', saved_record['rev'], record['rev'] + 1)
                self.check('guest edit retains the old source', saved_record['source'], record['source'])
            finally:
                release.set()
                worker.join(30)
        self.check('refresh worker finishes', worker.is_alive(), False)
        self.result['refresh_run'] = outcome[0] if outcome else None
        self.check('refresh succeeds', outcome[0]['status'] if outcome else None, 'succeeded')
        self.check('refresh updates exactly one source', outcome[0]['changed'], {'added': 0, 'updated': 1, 'unchanged': 1, 'removed': 0})
        after = self.core.records.get(sid, 'papers', record['id'])
        self.check('both writes advance the rev', after['rev'], record['rev'] + 2)
        self.check('refresh keeps the user note', after['data'], {'notes': 'User note saved during refresh'})
        self.check('refreshed source survives', after['source']['title'], 'Updated Public Research')
        changes = self.core.changes_since(sid, cursor)
        self.check('change stream has coherent revisions', [(c['op'], c['rev']) for c in changes['changes']],
                   [('put', record['rev'] + 1), ('source', record['rev'] + 2)])
        stale = self.put(saved_record, 'Stale overwrite')
        self.result['stale_guest_reply'] = stale
        self.check('stale guest call settles', stale and stale.get('ok'))
        self.check('stale guest writer receives conflict', (stale['value']['accepted'], stale['value'].get('code')), (False, 'conflict'))
        self.check('conflict supplies the entire current record', stale['value'].get('current'), after)
        self.check('stale writer changes no record', self.core.records.get(sid, 'papers', record['id']), after)
        self.check('stale writer appends no change', self.core.changes_since(sid, cursor), changes)
        self.q.screenshot(str(self.out / 'stale-refresh.png'))

    def incompatible_restore(self):
        sid = self.create('Partials Restore', {'data': {'version': 1}})
        self.core.records.put(sid, 'notes', 'demo', {'note': 'Keep this public note'}, actor='harness-fixture', base_rev=0)
        manifest = copy.deepcopy(self.core.get_space(sid)['manifest'])
        manifest['data'] = {'version': 2, 'migrations': [{'to': 2, 'ops': [
            {'op': 'rename_field', 'collection': 'notes', 'from': 'note', 'to': 'annotation'}]}]}
        self.core.write_files(sid, files={'index.html': '<main>Version two public fixture</main>'}, manifest=manifest,
                              author='harness-fixture', summary='Migrate public note to annotation', base_rev=1)
        self.check('migration created version two data', self.core.records.get(sid, 'notes', 'demo')['data'],
                   {'annotation': 'Keep this public note'})
        before, revisions = self.records(sid), self.core.list_revisions(sid)
        self.mount(sid)
        self.q.press('History')
        self.q.wait(self.q.page_text, lambda t: 'Revisions' in t, 15)
        self.q.press('Revisions', '[role=dialog]')
        self.q.wait(self.q.page_text, lambda t: 'Revision 1' in t and 'Revision 2' in t, 15)
        found = self.q.evaluate("""(() => {
          const row = [...document.querySelectorAll('[role=dialog] article')].find(a => a.querySelector('strong')?.textContent.trim() === 'Revision 1');
          if (!row) return false; row.id = 'partials-restore-target'; return true;
        })()""")
        self.check('revision A is present', found)
        self.q.press('Restore…', '#partials-restore-target')
        self.q.wait(self.q.page_text, lambda t: 'Restore revision 1?' in t, 15)
        self.q.press('Restore as new revision')
        message = self.q.wait(lambda: self.q.evaluate("[...document.querySelectorAll('[role=alert]')].map(e=>e.innerText).join('\\n')"),
                              lambda t: t and 'incompatible' in t.lower(), 20)
        self.result['restore_error_text'] = message
        self.q.screenshot(str(self.out / 'incompatible-restore.png'))
        self.check('blocked restore creates no revision', self.core.list_revisions(sid), revisions)
        self.check('blocked restore does not rewind data bytes', self.records(sid) == before)
        self.check('data version stays at two', self.core.get_space(sid)['data_version'], 2)
        self.check('host error names current and target data versions',
                   bool(re.search(r'(?:current|from)[^\d]*2\b', message, re.I)) and
                   bool(re.search(r'(?:target|to|revision)[^\d]*1\b', message, re.I)))

    def frame_reload(self):
        sid = self.create('Partials Reload')
        self.core.records.put(sid, 'notes', 'demo', {'note': 'Keep this public note'}, actor='harness-fixture', base_rev=0)
        self.mount(sid)
        old = self.open_sessions(sid)[0]
        before, cursor = self.records(sid), self.core.query(sid, 'notes')['seq']
        marker = f'partials-{time.time_ns()}'
        self.q.evaluate(f'window.__partialsPageMarker={json.dumps(marker)}; window.__partialsFrame=document.querySelector("iframe"); '
                        'window.__partialsFrameWindow=window.__partialsFrame.contentWindow; '
                        'window.__partialsReloads=0; window.__partialsReloadListener=e=>{ '
                        'if(e.source===window.__partialsFrameWindow && e.data?.v===1 && e.data.type==="space-reloaded") window.__partialsReloads++; }; '
                        'window.addEventListener("message",window.__partialsReloadListener)')
        try:
            initiated = self.guest('(setTimeout(() => location.reload(), 100), "reload scheduled")')
            self.check('only the guest frame schedules its reload', initiated, {'ok': True, 'value': 'reload scheduled'})
            self.q.wait(lambda: self.open_sessions(sid), lambda v: len(v) == 1 and old not in v, 30)
            self.q.wait(lambda: self.guest('space.meta'),
                        lambda v: v and v.get('ok') and (v.get('value') or {}).get('space', {}).get('id') == sid, 30)
            with sqlite3.connect(f'file:{self.db}?mode=ro', uri=True) as conn:
                closed = conn.execute('SELECT closed_at FROM sessions WHERE id=?', (old,)).fetchone()
            self.check('old session is explicitly closed', closed is not None and closed[0] is not None)
            self.check('shell emitted space-reloaded', self.q.evaluate('window.__partialsReloads > 0'))
            self.check('host page was not reloaded', self.q.evaluate('window.__partialsPageMarker'), marker)
            self.check('host replaced the old Space frame', self.q.evaluate('window.__partialsFrame !== document.querySelector("iframe")'))
            self.result['sessions'] = {'old': old, 'new': self.open_sessions(sid)[0]}
            replay = self.core.dispatch(sid, old, 'data.put', {'collection': 'notes', 'id': 'replayed', 'data': {'note': 'Rejected replay'}, 'base_rev': 0})
            self.result['replay'] = replay
            self.check('old session replay is refused', (replay.get('ok'), (replay.get('error') or {}).get('code')), (False, 'session_invalid'))
            self.check('reload and replay preserve all record bytes', self.records(sid) == before)
            self.check('replay appends no change', self.core.changes_since(sid, cursor)['changes'], [])
            self.q.screenshot(str(self.out / 'frame-reload.png'))
        finally:
            self.q.evaluate('window.removeEventListener("message",window.__partialsReloadListener); delete window.__partialsReloadListener; delete window.__partialsFrame; delete window.__partialsFrameWindow; delete window.__partialsPageMarker; delete window.__partialsReloads')

    def run(self):
        protected = {}
        try:
            self.q.close_sheets()
            self.q.go_index()
            self.q.wait(self.q.frames, lambda n: n == 0)
            for sid in PROTECTED:
                self.check(f'{sid} exists', self.core.get_space(sid)['id'], sid)
                protected[sid] = self.snapshot(sid)
                (self.out / f'{sid}-before.json').write_bytes(protected[sid])
            with self.q.Visible():
                getattr(self, self.args.step.replace('-', '_'))()
            if self.result['status'] == 'RUNNING':
                self.result['status'] = 'PASS'
        except Exception as exc:
            self.result['status'] = 'FAIL'
            self.result['error'] = f'{type(exc).__name__}: {exc}'
        finally:
            cleanup_errors = []
            try:
                if self.q.evaluate('document.querySelectorAll(".ls-confirm").length'):
                    self.q.press('Cancel', '.ls-confirm')
                self.q.go_index()
                self.q.wait(self.q.frames, lambda n: n == 0)
            except Exception as exc:
                cleanup_errors.append(f'Unmount: {exc}')
            for sid in self.fixtures:
                try:
                    self.core.delete_space(sid, actor='harness-fixture', confirm=sid)
                    self.check(f'{sid} fixture deleted', sid in {s['id'] for s in self.core.list_spaces()}, False)
                except Exception as exc:
                    cleanup_errors.append(f'{sid}: {exc}')
            for sid, before in protected.items():
                try:
                    after = self.snapshot(sid)
                    (self.out / f'{sid}-after.json').write_bytes(after)
                    self.check(f'{sid} protected snapshot is byte-identical', after == before)
                except Exception as exc:
                    cleanup_errors.append(f'{sid}: {exc}')
            self.result['cleanup_errors'] = cleanup_errors
            if cleanup_errors:
                self.result['status'] = 'FAIL'
            self.result['passed'] = sum(c['passed'] for c in self.result['checks'])
            self.result['total'] = len(self.result['checks'])
            path = self.out / 'partials.json'
            path.write_text(json.dumps(self.result, indent=2))
            print(f'{self.result["status"]}: {path}', flush=True)
        return 0 if self.result['status'] == 'PASS' else 2 if self.result['status'] == 'NEEDS_REVIEW' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('step', choices=STEPS)
    parser.add_argument('--chat-session', help='Fresh isolated Desktop chat session with no prior user turns')
    parser.add_argument('--review', type=Path, help='Trace-bound semantic review JSON; reads evidence only, does not drive the app')
    args = parser.parse_args()
    if args.review:
        if args.step != 'ambiguous':
            parser.error('--review only applies to ambiguous')
        review_ambiguity(args.review)
        return 0
    if args.step == 'ambiguous' and not args.chat_session:
        parser.error('ambiguous requires --chat-session for an isolated Desktop conversation')
    return Qualification(args).run()


if __name__ == '__main__':
    raise SystemExit(main())
