"""Disposable interactions use the real snapshot, store and Q03 bridge."""
import hashlib
import json
import os
import sqlite3
from pathlib import Path
import tempfile
import time
from unittest.mock import patch

from tests.python.test_inspection import InspectionCase, needs_browser, table_dump
from tests.python.test_q12_visual_inspection import plugin
import living_spaces_core as core
from living_spaces_core import bridge, db, grants, inspection, records, sessions
from living_spaces_core.errors import SpacesError


class Q13Case(InspectionCase):
    def journey(self, sid, steps, **options):
        try:
            return plugin.spaces_inspect(core, {'space': sid, 'rev': 1, 'interactions': steps, **options}, 'Demo')
        except (TypeError, SpacesError) as exc:
            self.fail(f'Q13 interactions missing or rejected: {exc}')

    def overlay(self, sid):
        factory = getattr(inspection, 'RecordOverlay', None)
        self.assertIsNotNone(factory, 'Q13 disposable record overlay is missing')
        conn = inspection._open_snapshot()
        self.addCleanup(conn.close)
        adapter = factory(inspection.Snapshot(conn, sid, 1), deadline=time.monotonic() + 10)
        self.addCleanup(adapter.close)
        return adapter

    def bytes(self):
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.home.glob('spaces.db*') if not p.name.endswith('-shm')}


class Q13OverlayTests(Q13Case):
    def test_q13_create_edit_read_own_writes_and_production_bytes_unchanged(self):
        sid = self.space('Overlay', '<main>x</main>')
        records.put(sid, 'notes', 'a', {'text': 'real'}, actor='agent:demo')
        before, raw = table_dump(self.db), self.bytes()
        adapter = self.overlay(sid)
        saved = adapter.call('data.put', {'collection': 'notes', 'id': 'a', 'data': {'text': 'copy'}, 'base_rev': 1}, request_id='edit')
        self.assertTrue(saved['ok'], saved)
        self.assertEqual(saved['outcome']['status'], 'success')
        self.assertEqual(adapter.call('data.get', {'collection': 'notes', 'id': 'a'})['result']['data'], {'text': 'copy'})
        self.assertTrue(adapter.call('data.put', {'collection': 'notes', 'id': 'b', 'data': {'text': 'new'}}, request_id='create')['ok'])
        self.assertEqual(adapter.call('data.query', {'collection': 'notes'})['result']['total'], 2)
        changes = adapter.evidence()
        self.assertEqual([(r['id'], r['record']['data']['text']) for r in changes['changes']], [('a', 'copy'), ('b', 'new')])
        adapter.close()
        self.assertEqual(table_dump(self.db), before)
        self.assertEqual(self.bytes(), raw)

    def test_q13_receipts_replay_conflict_and_outcome_get_match_live(self):
        sid = self.space('Receipts', '<main>x</main>')
        adapter = self.overlay(sid)
        args = {'collection': 'notes', 'id': 'a', 'data': {'n': 1}, 'base_rev': 0}
        self.assertTrue(adapter.call('data.put', args, request_id='same')['ok'])
        self.assertTrue(adapter.call('data.put', args, request_id='same')['ok'])
        found = adapter.call('outcome.get', {'request_id': 'same'})
        self.assertEqual(found['result']['confirmation']['changes'][0]['rev'], 1)
        self.assertEqual(adapter.call('outcome.get', {'request_id': 'missing'})['outcome']['status'], 'unknown')
        mismatch = adapter.call('data.put', {**args, 'data': {'n': 2}}, request_id='same')
        self.assertEqual(mismatch['error']['code'], 'conflict')
        self.assertEqual(mismatch['outcome']['status'], 'rejected')
        self.assertEqual(adapter.call('data.get', {'collection': 'notes', 'id': 'a'})['result']['rev'], 1)

    def test_q13_two_writers_conflict_against_overlay_and_batch_rolls_back(self):
        sid = self.space('Writers', '<main>x</main>')
        records.put(sid, 'notes', 'a', {'n': 0}, actor='agent:demo')
        adapter = self.overlay(sid)
        self.assertTrue(adapter.call('data.put', {'collection': 'notes', 'id': 'a', 'data': {'n': 1}, 'base_rev': 1})['ok'])
        stale = adapter.call('data.batch', {'ops': [
            {'op': 'put', 'collection': 'notes', 'id': 'b', 'data': {}},
            {'op': 'put', 'collection': 'notes', 'id': 'a', 'data': {'n': 2}, 'base_rev': 1}]})
        self.assertEqual(stale['error']['code'], 'conflict')
        self.assertEqual(stale['error']['current']['data'], {'n': 1})
        self.assertEqual(adapter.call('data.query', {'collection': 'notes'})['result']['total'], 1)
        self.assertEqual(records.get(sid, 'notes', 'a')['data'], {'n': 0})

    def test_q13_external_native_and_unknown_operations_refused_before_dispatch(self):
        sid = self.space('Denied', '<main>x</main>')
        adapter = self.overlay(sid)
        before = table_dump(self.db)
        for op, args in [('net.fetch', {'url': 'https://example.com', 'method': 'POST', 'body': 'x'}),
                         ('refresh', {}), ('bot.request', {'activation_id': 'a', 'text': 'run'}),
                         ('cron.create', {}), ('space.delete', {}), ('native.open', {})]:
            with self.subTest(op=op):
                reply = adapter.call(op, args)
                self.assertFalse(reply['ok'])
                self.assertEqual(reply['outcome']['status'], 'rejected')
                self.assertEqual(adapter.refused[op], 1)
        self.assertEqual(table_dump(self.db), before)

    def test_q13_overlay_never_sees_private_drafts_but_editor_saves_work_inside_it(self):
        # Integration of Q10 and Q13: a person's real reopen draft must not reach the inspected app, while an app
        # built on the kit editor can still be exercised end to end against the disposable copy.
        from living_spaces_core import drafts, sessions
        sid = self.space('Drafts', '<main>x</main>')
        records.put(sid, 'notes', 'a', {'n': 1}, actor='agent:demo')
        session = sessions.open_session(sid)['session']
        grants.decide(sid, 'data', 'grant')
        key = {'editor': 'note', 'schema': 1, 'collection': 'notes', 'id': 'a'}
        put = bridge.dispatch(sid, session, 'draft.put', {**key, 'draft': {'value': {'n': 'private'}, 'baseRev': 1, 'state': 'idle'}})
        self.assertTrue(put['ok'], put)
        before, hashes = table_dump(self.db), self.bytes()
        adapter = self.overlay(sid)
        seen = adapter.call('draft.get', key)
        self.assertTrue(seen['ok'], seen)
        self.assertIsNone(seen['result']['draft'])    # recovery mode mirrors live so the inspected UI matches
        saved = adapter.call('editor.save', {**key, 'data': {'n': 2}, 'base_rev': 1}, request_id='edit-1')
        self.assertTrue(saved['ok'], saved)
        self.assertEqual(adapter.call('data.get', {'collection': 'notes', 'id': 'a'})['result']['data'], {'n': 2})
        found = adapter.call('outcome.get', {'request_id': 'edit-1', **key})
        self.assertEqual(found['outcome']['status'], 'success', found)
        adapter.close()
        self.assertEqual((table_dump(self.db), self.bytes()), (before, hashes))

    def test_q13_overlay_works_on_a_profile_without_the_draft_table(self):
        sid = self.space('Legacy', '<main>x</main>')
        with db.write() as conn:
            conn.execute("DROP TABLE editor_drafts")
        adapter = self.overlay(sid)
        self.assertTrue(adapter.call('data.put', {'collection': 'notes', 'id': 'a', 'data': {}})['ok'])

    def test_q13_overlays_are_independent_and_discarded_after_close(self):
        sid = self.space('Separate', '<main>x</main>')
        first, second = self.overlay(sid), self.overlay(sid)
        self.assertTrue(first.call('data.put', {'collection': 'notes', 'id': 'a', 'data': {}})['ok'])
        self.assertEqual(second.call('data.query', {'collection': 'notes'})['result']['total'], 0)
        first.close()
        self.assertFalse(first.call('data.query', {'collection': 'notes'})['ok'])
        self.assertEqual(records.query(sid, 'notes')['total'], 0)

    def test_q13_delete_batch_evidence_redaction_and_request_validation(self):
        sid = self.space('Delete', '<main>x</main>')
        records.put(sid, 'notes', 'a', {'n': 1}, actor='agent:demo')
        adapter = self.overlay(sid)
        saved = adapter.call('data.batch', {'ops': [
            {'op': 'delete', 'collection': 'notes', 'id': 'a', 'base_rev': 1},
            {'op': 'put', 'collection': 'notes', 'id': 'b', 'data': {'password': 'demo-only-secret', 'n': 2}}]}, request_id='batch')
        self.assertTrue(saved['ok'], saved)
        evidence = adapter.evidence()
        self.assertIsNone(evidence['changes'][0]['record'])
        self.assertNotIn('demo-only-secret', json.dumps(evidence))
        self.assertEqual(adapter.call('data.query', {'collection': 'notes'}, request_id='read')['error']['code'], 'invalid')
        self.assertEqual(adapter.call('data.put', {'collection': 'notes', 'id': 'c', 'data': {}}, request_id='bad id')['error']['code'], 'invalid')
        self.assertEqual(records.query(sid, 'notes')['total'], 1)

    def test_q13_post_commit_unknown_reconciles_only_inside_overlay(self):
        sid = self.space('Unknown', '<main>x</main>')
        before, raw = table_dump(self.db), self.bytes()
        adapter = self.overlay(sid)
        authorize = bridge._authorize

        def fail_after_commit(invocation):
            authorize(invocation)
            if invocation.effect.state == 'committed':
                raise sqlite3.OperationalError('synthetic delivery fault')

        with patch.object(bridge, '_authorize', fail_after_commit):
            reply = adapter.call('data.put', {'collection': 'notes', 'id': 'a', 'data': {'n': 1}}, request_id='uncertain')
        self.assertEqual(reply['outcome']['status'], 'unknown')
        found = adapter.call('outcome.get', {'request_id': 'uncertain'})
        self.assertEqual(found['result']['confirmation']['changes'][0]['rev'], 1)
        self.assertEqual(table_dump(self.db), before)
        self.assertEqual(self.bytes(), raw)

    def test_q13_snapshot_ignores_later_real_writes_and_bridge_reopen_is_separate(self):
        sid = self.space('Reopen control', '<main>x</main>')
        adapter = self.overlay(sid)
        session = sessions.open_session(sid)['session']
        saved = bridge.dispatch(sid, session, 'data.put', {'collection': 'notes', 'id': 'real', 'data': {'n': 1}}, request_id='real-save')
        self.assertTrue(saved['ok'])
        sessions.close_session(session)
        reopened = sessions.open_session(sid)['session']
        self.assertEqual(bridge.dispatch(sid, reopened, 'data.get', {'collection': 'notes', 'id': 'real'})['result']['data'], {'n': 1})
        self.assertEqual(adapter.call('data.query', {'collection': 'notes'})['result']['total'], 0)
        sessions.close_session(reopened)

    def test_q13_evidence_and_queries_respect_byte_and_time_limits(self):
        sid = self.space('Bounds', '<main>x</main>')
        adapter = self.overlay(sid)
        self.assertTrue(adapter.call('data.put', {'collection': 'notes', 'id': 'a', 'data': {'text': 'x' * 2000}})['ok'])
        evidence = adapter.evidence(max_bytes=100)
        self.assertTrue(evidence['truncated'])
        self.assertLessEqual(len(json.dumps(evidence).encode()), 100)
        adapter.deadline = time.monotonic() - 1
        with self.assertRaises(inspection._Timeout):
            adapter.call('data.query', {'collection': 'notes'})


class Q13BoundaryTests(Q13Case):
    def test_q13_optional_input_and_launch_failure_have_incomplete_coverage(self):
        sid = self.space('Launch', '<main>x</main>')
        with patch.dict(os.environ, {inspection.BROWSER_ENV: ''}):
            report = self.journey(sid, [{'action': 'click', 'selector': 'main'}])
        self.assertEqual(report['outcome'], 'unavailable')
        self.assertEqual(report['interactions']['status'], 'incomplete')
        self.assertTrue(report['interactions']['overlay']['discarded'])
        self.assertEqual(report['interactions']['evidence'], 'disposable interaction')
        fake = self.home / 'bad-browser'
        fake.write_bytes(b'\x00\x01 invalid')
        fake.chmod(0o700)
        before, raw = table_dump(self.db), self.bytes()
        with patch.dict(os.environ, {inspection.BROWSER_ENV: str(fake)}):
            report = self.journey(sid, [{'action': 'click', 'selector': 'main'}])
        self.assertEqual(report['error']['code'], 'renderer_launch_failed')
        self.assertTrue(report['interactions']['overlay']['discarded'])
        self.assertEqual(table_dump(self.db), before)
        self.assertEqual(self.bytes(), raw)

    def test_q13_renderer_exit_discards_overlay_and_restores_store_routing(self):
        sid = self.space('Exit', '<main>x</main>')
        before, raw = table_dump(self.db), self.bytes()
        with patch.dict(os.environ, {inspection.BROWSER_ENV: '/usr/bin/true'}):
            report = self.journey(sid, [{'action': 'click', 'selector': 'main'}])
        self.assertEqual(report['outcome'], 'error')
        self.assertTrue(report['interactions']['overlay']['discarded'])
        self.assertEqual(table_dump(self.db), before)
        self.assertEqual(self.bytes(), raw)
        records.put(sid, 'notes', 'after', {'n': 1}, actor='agent:demo')
        self.assertEqual(records.get(sid, 'notes', 'after')['data'], {'n': 1})

    def test_q13_step_validation_is_typed_and_bounded(self):
        sid = self.space('Input', '<main>x</main>')
        for steps in [True, [], [{}], [{'action': 'eval', 'selector': 'main'}],
                      [{'action': 'click', 'selector': 'x' * 257}],
                      [{'action': 'type', 'selector': 'input', 'text': 'x' * 4097}],
                      [{'action': 'key', 'selector': 'input', 'key': 'Unknown'}],
                      [{'action': 'click', 'selector': 'main', 'timeout_ms': 10001}],
                      [{'action': 'click', 'selector': 'main'}] * 21]:
            with self.subTest(steps=str(steps)[:80]), self.assertRaises(SpacesError) as raised:
                plugin.spaces_inspect(core, {'space': sid, 'rev': 1, 'interactions': steps}, 'Demo')
            self.assertEqual(raised.exception.code, 'invalid')
        with patch.dict(os.environ, {inspection.BROWSER_ENV: ''}):
            report = self.journey(sid, [{'action': 'click', 'selector': 'main'}])
        self.assertIn('interactions', report)


FORM = '''<input id=text><select id=kind><option value=a>A</option><option value=b>B</option></select>
<button id=save>Save</button><button id=edit>Edit</button><button id=bad>Bad</button><main id=out>ready</main>
<script type=module>
const t=document.querySelector('#text'), o=document.querySelector('#out');
document.querySelector('#save').onclick=async()=>{ const r=await space.put('notes','new',{text:t.value,kind:document.querySelector('#kind').value}); o.textContent='saved:'+r.data.text };
document.querySelector('#edit').onclick=async()=>{ const r=await space.get('notes','new'); const s=await space.put('notes','new',{text:'edited'},{baseRev:r.rev}); o.textContent='edited:'+s.rev };
document.querySelector('#bad').onclick=async()=>{try{await space.put('notes','new',{text:'stale'},{baseRev:0})}catch(e){o.textContent=e.code}};
t.onkeydown=e=>{if(e.key==='Enter') o.textContent='enter'};
</script>'''


@needs_browser
class Q13RuntimeTests(Q13Case):
    def test_q13_click_type_key_select_create_edit_and_post_state_geometry(self):
        sid = self.space('Form', FORM)
        before, raw = table_dump(self.db), self.bytes()
        report = self.journey(sid, [{'action': 'type', 'selector': '#text', 'text': 'draft'},
                                  {'action': 'key', 'selector': '#text', 'key': 'Enter'},
                                  {'action': 'select', 'selector': '#kind', 'value': 'b'},
                                  {'action': 'click', 'selector': '#save'}, {'action': 'click', 'selector': '#edit'}],
                              timeout_s=30, width=390, height=300, visual={'routes': [{'hash': '', 'landmarks': {'saved': '#out'}}]})
        self.assertEqual(report['interactions']['status'], 'complete', report)
        self.assertEqual([s['outcome'] for s in report['interactions']['steps']], ['performed'] * 5)
        self.assertIn('edited:2', report['text']['content'])
        self.assertEqual(report['visual']['evidence'], 'disposable interaction')
        self.assertEqual(report['visual']['status'], 'complete')
        self.assertEqual(report['interactions']['overlay']['changes'][0]['record']['data'], {'text': 'edited', 'kind': 'b'})
        self.assertEqual(table_dump(self.db), before)
        self.assertEqual(self.bytes(), raw)

    def test_q13_missing_disabled_failed_save_stop_remaining_steps(self):
        sid = self.space('Failures', FORM + '<button id=disabled disabled>Disabled</button>')
        cases = [('#absent', 'target missing', []), ('#disabled', 'refused', []),
                 ('#bad', 'refused', [{'action': 'click', 'selector': '#save'}])]
        for target, outcome, prefix in cases:
            with self.subTest(target=target):
                report = self.journey(sid, prefix + [{'action': 'click', 'selector': target}, {'action': 'click', 'selector': '#edit'}], timeout_s=30)
                self.assertEqual(report['interactions']['status'], 'incomplete', report)
                self.assertEqual(report['interactions']['steps'][len(prefix)]['outcome'], outcome)
                self.assertEqual(report['interactions']['steps'][-1]['reason'], 'earlier_step_failed')
                self.assertEqual(report['outcome'], 'failed')

    def test_q13_external_post_and_bot_attempts_counted_and_stop_journey(self):
        sid = self.space('Effects', '<button id=go>go</button><script type=module>document.querySelector("#go").onclick=async()=>{'
                         'for(const f of [()=>space.net.fetch("https://example.com",{method:"POST",body:"x"}),()=>space.ask("run"),()=>space.refresh()]){try{await f()}catch{}}}</script>')
        before = table_dump(self.db)
        report = self.journey(sid, [{'action': 'click', 'selector': '#go'}])
        self.assertEqual(report['interactions']['steps'][0]['outcome'], 'refused', report)
        self.assertEqual(report['blocked'], {'net.fetch': 1, 'bot.request': 1, 'refresh': 1})
        self.assertEqual(table_dump(self.db), before)

    def test_q13_timeout_after_overlay_write_discards_and_never_passes(self):
        sid = self.space('Timeout', '<button id=go>go</button><script type=module>document.querySelector("#go").onclick=async()=>{'
                         'await space.put("notes","a",{n:1}); while(true){}}</script>')
        before, raw = table_dump(self.db), self.bytes()
        dirs = set(Path(tempfile.gettempdir()).glob('ls-inspect-*'))
        report = self.journey(sid, [{'action': 'click', 'selector': '#go', 'timeout_ms': 3000}, {'action': 'click', 'selector': '#go'}], timeout_s=10)
        self.assertEqual(report['outcome'], 'timed_out', report)
        self.assertEqual(report['interactions']['steps'][0]['outcome'], 'timed out')
        self.assertTrue(report['interactions']['overlay']['discarded'])
        self.assertEqual(report['cleanup'], {'process_exited': True, 'temp_removed': True})
        self.assertEqual(set(Path(tempfile.gettempdir()).glob('ls-inspect-*')), dirs)
        self.assertEqual(table_dump(self.db), before)
        self.assertEqual(self.bytes(), raw)
