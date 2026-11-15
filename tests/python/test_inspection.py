"""spaces_inspect: runs real Spaces in a throwaway local Chromium and checks what is reported and what is not touched."""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "living-spaces"))
from living_spaces_core import grants, inspection, projects, records, runs, sessions  # noqa: E402
from living_spaces_core.errors import SpacesError  # noqa: E402

RENDERER, NO_RENDERER = inspection.find_renderer()
needs_browser = unittest.skipUnless(RENDERER, f"no local Chromium: {NO_RENDERER}")

MALICIOUS = """<main id=out>probe</main><script type="module">
const tries = {
  put: () => space.put('notes', 'evil', { x: 1 }),
  delete: () => space.delete('notes', 'a'),
  batch: () => space.batch([{ op: 'put', collection: 'notes', id: 'evil2', data: {} }]),
  refresh: () => space.refresh(),
  bot: () => space.ask('hello'),
  net: () => space.net.fetch('https://example.com/'),
  fetch: () => fetch('https://example.com/direct'),
  socket: () => new Promise((ok, no) => { try { const w = new WebSocket('wss://example.com/'); w.onerror = no } catch (e) { no(e) } }),
  storage: async () => localStorage.setItem('k', 'v'),
  cookie: async () => { document.cookie = 'a=b' },
  top: async () => { top.location = 'https://example.com/' },
  popup: async () => { if (!window.open('https://example.com/')) throw new Error('blocked') },
  parent: async () => parent.parent.__lsInspect.reply(1, {}),
}
const out = []
for (const [name, run] of Object.entries(tries)) {
  try { await run(); out.push(name + ':allowed') } catch (e) { out.push(name + ':' + (e.code || 'refused')) }
}
const img = new Image(); img.src = 'https://example.com/pixel.png'; document.body.append(img)
document.getElementById('out').textContent = out.join(' ')
</script>"""


def table_dump(path):
    """Every row of every table, so any write anywhere in the database shows up."""
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        return {table: conn.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall() for table in tables}
    finally:
        conn.close()



def sent_replies(expression):
    """Decode a bridge reply expression exactly as the page does: JSON.parse("<json>")."""
    prefix = "JSON.parse("
    assert expression.startswith(prefix), expression[:40]
    literal, _ = json.JSONDecoder().raw_decode(expression[len(prefix):])
    return json.loads(literal)


class InspectionCase(unittest.TestCase):
    def setUp(self):
        (ROOT / ".run").mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=ROOT / ".run")
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.db = self.home / "spaces.db"
        environment = patch.dict(os.environ, {"LIVING_SPACES_DB": str(self.db), "HERMES_HOME": temporary.name})
        environment.start()
        self.addCleanup(environment.stop)
        os.environ.pop(inspection.BROWSER_ENV, None)

    def space(self, name, html, **files):
        return projects.create_space(name, owner="Demo", author="agent:demo", files={"index.html": html, **files})["id"]

    def inspect(self, sid, rev=1, **options):
        options.setdefault("timeout_s", 15)
        report = inspection.inspect(sid, rev, **options)
        json.dumps(report)                                   # the tool returns it as JSON
        self.assertIsNone(report["screenshot"])
        self.assertTrue(any(item.startswith("no_pixels_captured") for item in report["limitations"]))
        return report


@needs_browser
class RuntimeObservationTests(InspectionCase):
    def test_normal_space_loads_reads_records_and_reports_text(self):
        sid = self.space("Notes", '<main><h1>Reading list</h1><p id=n>…</p></main><script type="module">'
                         'const r = await space.query("notes"); document.getElementById("n").textContent = '
                         '"notes:" + r.map(x => x.data.t).join(",")</script>')
        records.put(sid, "notes", "a", {"t": "one"}, actor="agent:demo")
        report = self.inspect(sid)
        self.assertEqual(report["outcome"], "loaded", report)
        self.assertEqual((report["space"], report["rev"]), (sid, 1))
        self.assertTrue(report["readiness"]["shell_booted"])
        self.assertEqual(report["readiness"]["guest_lifecycle"], "loaded")
        self.assertIn("notes:one", report["text"]["content"])
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["served"].get("data.query"), 1)
        self.assertEqual(report["viewport"]["actual"][:2], [1024, 768])
        self.assertTrue(report["inspection"]["renderer"]["product"].startswith(("Chrome", "HeadlessChrome", "Chromium")))
        self.assertEqual(report["cleanup"], {"process_exited": True, "temp_removed": True})

    def test_explicit_revision_is_the_one_rendered(self):
        sid = self.space("Versions", "<main>first version</main>")
        projects.write_files(sid, files={"index.html": "<main>second version</main>"}, author="agent:demo", summary="v2")
        old, new = self.inspect(sid, 1), self.inspect(sid, 2)
        self.assertIn("first version", old["text"]["content"])
        self.assertIn("second version", new["text"]["content"])
        self.assertFalse(old["inspection"]["snapshot"]["is_head"])
        self.assertTrue(new["inspection"]["snapshot"]["is_head"])
        self.assertNotEqual(old["inspection"]["snapshot"]["files_digest"], new["inspection"]["snapshot"]["files_digest"])

    def test_syntax_error_is_reported_as_an_exception(self):
        sid = self.space("Broken", '<main>shell</main><script type="module">this is not javascript</script>')
        report = self.inspect(sid)
        self.assertEqual(report["outcome"], "loaded_with_errors", report)
        self.assertTrue(any(entry["source"] == "exception" and "SyntaxError" in entry["text"] for entry in report["errors"]))

    def test_missing_module_fails_with_the_failure_panel(self):
        sid = self.space("Missing", '<main>x</main><script type="module" src="app.js"></script>',
                         **{"app.js": "import './nope.js'"})
        report = self.inspect(sid)
        self.assertEqual(report["outcome"], "failed", report)
        self.assertTrue(report["readiness"]["failure_panel"])
        self.assertIn("could not load", report["text"]["content"])

    def test_blank_space_is_flagged(self):
        report = self.inspect(self.space("Blank", "<main></main>"))
        self.assertEqual(report["outcome"], "loaded")
        self.assertTrue(any(item.startswith("blank_suspected") for item in report["limitations"]))

    def test_async_content_is_waited_for(self):
        sid = self.space("Slow", '<main id=m>loading</main><script type="module">'
                         'setTimeout(() => { document.getElementById("m").textContent = "arrived late" }, 1200)</script>')
        report = self.inspect(sid)
        self.assertIn("arrived late", report["text"]["content"], report)

    def test_runaway_space_times_out_and_is_cleaned_up(self):
        sid = self.space("Spin", '<main>spin</main><script type="module">while (true) {}</script>')
        report = self.inspect(sid, timeout_s=3)
        self.assertEqual(report["outcome"], "timed_out", report)
        self.assertNotEqual(report["outcome"], "loaded")
        self.assertEqual(report["cleanup"], {"process_exited": True, "temp_removed": True})
        self.assertLess(report["inspection"]["duration_ms"], 3000 + inspection.CLEANUP_S * 1000 + 2000)

    def test_oversized_text_is_bounded(self):
        sid = self.space("Long", "<main>" + "word " * 12000 + "</main>")
        report = self.inspect(sid, text_limit=100)
        self.assertEqual(len(report["text"]["content"]), 100)
        self.assertTrue(report["text"]["truncated"])
        self.assertGreater(report["text"]["chars"], 50000)
        self.assertLess(len(json.dumps(report)), 20000)

    def test_error_flood_is_bounded(self):
        sid = self.space("Flood", '<main>x</main><script type="module">'
                         'for (let i = 0; i < 500; i++) console.error("err " + i)</script>')
        report = self.inspect(sid)
        self.assertLessEqual(len(report["errors"]), inspection.MAX_ENTRIES)
        self.assertGreater(report["counts"]["dropped"], 0)

    def test_secrets_in_console_are_redacted(self):
        sid = self.space("Leaky", '<main>x</main><script type="module">'
                         'console.error("token sk-abcdefghijklmnopqrstuvwx1234")</script>')
        report = self.inspect(sid)
        text = json.dumps(report["errors"])
        self.assertNotIn("sk-abcdefghijklmnopqrstuvwx1234", text)
        self.assertIn("[REDACTED]", text)

    def test_withheld_console_when_diagnostics_not_granted(self):
        sid = self.space("Quiet", '<main>visible</main><script type="module">console.error("private detail")</script>')
        grants.decide(sid, "logs", "deny", actor="user")
        report = self.inspect(sid)
        self.assertNotIn("private detail", json.dumps(report["errors"]))
        self.assertTrue(any(item.startswith("diagnostics_not_granted") for item in report["limitations"]))
        self.assertIn(report["outcome"], ("rendered_unconfirmed", "loaded"))

    def test_custom_viewport(self):
        report = self.inspect(self.space("Narrow", "<main>narrow</main>"), width=390, height=844)
        self.assertEqual(report["viewport"]["actual"][:2], [390, 844])


@needs_browser
class PassivityTests(InspectionCase):
    def test_malicious_guest_changes_nothing_and_every_effect_is_refused(self):
        sid = self.space("Hostile", MALICIOUS)
        records.put(sid, "notes", "a", {"t": "keep"}, actor="agent:demo")
        before_rows, before_bytes = table_dump(self.db), hashlib.sha256(self.db.read_bytes()).hexdigest()
        with patch.object(runs, "start_refresh", side_effect=AssertionError("refresh ran")) as refresh:
            report = self.inspect(sid)
        refresh.assert_not_called()
        self.assertEqual(table_dump(self.db), before_rows)
        self.assertEqual(hashlib.sha256(self.db.read_bytes()).hexdigest(), before_bytes)
        text = report["text"]["content"]
        for name in ("put", "delete", "batch", "refresh", "bot", "net"):
            self.assertIn(f"{name}:blocked", text, report)
        # Storage and cookies throw SecurityError (code 18) in an opaque-origin sandbox; navigation and popups fail.
        for name in ("fetch", "socket", "storage", "cookie", "top", "popup", "parent"):
            self.assertNotIn(f"{name}:allowed", text, report)
        self.assertEqual(report["blocked"], {"data.put": 1, "data.delete": 1, "data.batch": 1, "refresh": 1,
                                             "bot.request": 1, "net.fetch": 1})
        self.assertEqual(report["network"]["blocked"], 0)    # CSP refused every request before it was issued
        self.assertTrue(any("connect-src" in entry["text"] or "img-src" in entry["text"] for entry in report["errors"]))

    def test_inspection_does_not_open_sessions_logs_or_mark_opened(self):
        sid = self.space("Plain", '<main>x</main><script type="module">console.error("once")</script>')
        before = table_dump(self.db)
        self.inspect(sid)
        after = table_dump(self.db)
        for table in ("sessions", "logs", "audit", "runs", "upkeep_links", "records", "changes", "spaces"):
            self.assertEqual(after[table], before[table], table)

    def test_records_written_during_inspection_do_not_leak_into_it(self):
        sid = self.space("Snap", '<main id=m></main><script type="module">'
                         'await new Promise(r => setTimeout(r, 1000)); '
                         'document.getElementById("m").textContent = "count:" + (await space.query("notes")).length</script>')
        records.put(sid, "notes", "a", {"t": "1"}, actor="agent:demo")
        writer = threading.Timer(0.3, lambda: records.put(sid, "notes", "b", {"t": "2"}, actor="agent:demo"))
        writer.start()
        report = self.inspect(sid)
        writer.join()
        self.assertIn("count:1", report["text"]["content"], report)
        self.assertEqual(len(records.query(sid, "notes")["records"]), 2)

    def test_other_spaces_records_are_unreachable(self):
        mine = self.space("Mine", '<main id=m></main><script type="module">'
                          'document.getElementById("m").textContent = "n:" + (await space.query("notes")).length</script>')
        other = self.space("Other", "<main>other</main>")
        records.put(other, "notes", "secret", {"t": "x"}, actor="agent:demo")
        report = self.inspect(mine)
        self.assertIn("n:0", report["text"]["content"], report)

    def test_other_profiles_spaces_are_not_found(self):
        sid = self.space("Here", "<main>here</main>")
        with tempfile.TemporaryDirectory(dir=ROOT / ".run") as elsewhere:
            with patch.dict(os.environ, {"LIVING_SPACES_DB": str(Path(elsewhere) / "spaces.db"), "HERMES_HOME": elsewhere}):
                projects.create_space("Elsewhere", owner="Demo", author="agent:demo", files={"index.html": "x"})
                with self.assertRaises(SpacesError) as raised:
                    inspection.inspect(sid, 1)
        self.assertEqual(raised.exception.code, "not_found")

    def test_concurrent_inspections_stay_separate(self):
        a, b = self.space("Alpha", "<main>alpha body</main>"), self.space("Beta", "<main>beta body</main>")
        results = {}
        threads = [threading.Thread(target=lambda s=s: results.__setitem__(s, self.inspect(s))) for s in (a, b)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertIn("alpha body", results[a]["text"]["content"])
        self.assertIn("beta body", results[b]["text"]["content"])
        self.assertNotIn("beta", results[a]["text"]["content"])
        self.assertNotEqual(results[a]["inspection"]["id"], results[b]["inspection"]["id"])

    def test_cancellation_kills_the_browser_and_removes_its_files(self):
        sid = self.space("Cancel", "<main>cancel me</main>")
        seen = {}
        original = inspection.Browser.close

        def close(browser):
            seen["pid"], seen["tmp"] = browser.pid, browser.tmp
            seen["receipt"] = original(browser)
            return seen["receipt"]

        with patch.object(inspection.Browser, "close", close), \
                patch.object(inspection._Run, "sample", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                inspection.inspect(sid, 1)
        self.assertEqual(seen["receipt"], {"process_exited": True, "temp_removed": True})
        self.assertFalse(os.path.exists(seen["tmp"]))
        with self.assertRaises(ProcessLookupError):
            os.killpg(seen["pid"], 0)
        self.assertEqual(inspection._slots._value, inspection.MAX_CONCURRENT)


@needs_browser
class ReviewRepairTests(InspectionCase):
    """Frozen regressions for review-1 (Codex gpt-6-astra, REJECT at bcd437e). Each failed before its repair."""

    def test_f1_a_failed_current_sample_never_counts_as_settled(self):
        sid = self.space("Stale", "<main>stable</main>")
        original, calls = inspection._Run.sample, []

        def sample(run):
            calls.append(1)
            return original(run) if len(calls) == 1 else None    # one good sample, then sampling fails

        with patch.object(inspection._Run, "sample", sample):
            report = self.inspect(sid, timeout_s=4)
        self.assertEqual(report["outcome"], "timed_out", report)
        self.assertFalse(report["readiness"]["settled"])

    def test_f1_a_crashed_guest_is_an_error_not_loaded(self):
        sid = self.space("Crash", "<main>crash</main>")
        original, calls = inspection._Run.sample, []

        def sample(run):
            calls.append(1)
            value = original(run)
            if len(calls) == 2:
                run.on_event({"method": "Inspector.targetCrashed", "params": {},
                              "sessionId": run.owner(run.guest_frame())})
            return value

        with patch.object(inspection._Run, "sample", sample):
            report = self.inspect(sid, timeout_s=6)
        self.assertEqual(report["outcome"], "error", report)
        self.assertEqual(report["error"]["code"], "renderer_crashed")

    def test_f2_report_formatting_failure_still_cleans_up(self):
        sid = self.space("Nested", "<main>" + "[" * 600 + "0" + "]" * 600 + "</main>")
        before = set(Path(tempfile.gettempdir()).glob("ls-inspect-*"))
        report = self.inspect(sid)
        self.assertEqual(report["outcome"], "loaded", report)
        self.assertEqual(report["cleanup"], {"process_exited": True, "temp_removed": True})
        self.assertEqual(set(Path(tempfile.gettempdir()).glob("ls-inspect-*")), before)

    def test_f2_any_reporting_error_still_closes_the_browser(self):
        sid = self.space("Boom", "<main>x</main>")
        closed = []
        original = inspection.Browser.close
        with patch.object(inspection, "_finish", side_effect=ValueError("formatting broke")), \
                patch.object(inspection.Browser, "close", lambda b: closed.append(original(b)) or closed[-1]):
            report = self.inspect(sid)
        self.assertEqual(closed, [{"process_exited": True, "temp_removed": True}])
        self.assertEqual(report["outcome"], "error")
        self.assertEqual(report["error"]["code"], "inspection_failed")

    def test_f5_console_errors_are_loaded_with_errors(self):
        sid = self.space("Noisy", '<main>x</main><script type="module">console.error("visible problem")</script>')
        report = self.inspect(sid)
        self.assertEqual(report["outcome"], "loaded_with_errors", report)

    def test_f6_host_denials_are_reported(self):
        sid = self.space("Denied", '<main id=m>x</main><script type="module">'
                         'try { await space.put("notes", "n", {}) } catch (e) { document.getElementById("m").textContent = e.code }'
                         '</script>')
        grants.decide(sid, "data", "deny", actor="user")
        report = self.inspect(sid)
        self.assertEqual(report["denied"], {"data.put": 1}, report)
        self.assertEqual(report["blocked"], {})

    def test_f7_text_limit_holds_after_redaction(self):
        sid = self.space("Secret", "<main>api_key=x and more text</main>")
        report = self.inspect(sid, text_limit=9)
        self.assertLessEqual(len(report["text"]["content"]), 9, report["text"])
        self.assertTrue(report["text"]["truncated"])
        self.assertNotIn("api_key=x", report["text"]["content"])

    def test_f8_huge_text_is_clipped_in_the_browser(self):
        sid = self.space("Huge", '<main id=m></main><script type="module">'
                         'document.getElementById("m").textContent = "word ".repeat(4000000)</script>')
        seen = {}
        original = inspection.Browser.close

        def close(browser):
            seen["max"] = getattr(browser, "max_message", None)
            return original(browser)

        with patch.object(inspection.Browser, "close", close):
            report = self.inspect(sid, text_limit=100, timeout_s=20)
        self.assertEqual(report["text"]["chars"], 19999999, report.get("text"))   # innerText trims the last space
        self.assertEqual(len(report["text"]["content"]), 100)
        self.assertIsNotNone(seen["max"])
        self.assertLess(seen["max"], 2 * 1024 * 1024)


class ProtocolBoundTests(unittest.TestCase):
    """Review-1 F3, F4 and the incoming-message cap, without a browser."""

    def fake_browser(self, deadline):
        browser = inspection.Browser.__new__(inspection.Browser)
        browser.deadline, browser.buf, browser.next_id, browser.responses, browser.listeners = deadline, b"", 0, {}, []
        browser.max_message, browser.pid, browser.tmp = 0, None, tempfile.mkdtemp(prefix="ls-inspect-test-")
        self.addCleanup(shutil.rmtree, browser.tmp, True)
        return browser

    def test_f3_a_stalled_pipe_times_out_instead_of_hanging(self):
        import time
        browser = self.fake_browser(time.monotonic() + 0.3)
        incoming_r, incoming_w = os.pipe()          # nothing ever arrives
        outgoing_r, outgoing_w = os.pipe()          # nobody ever reads
        for fd in (incoming_w, outgoing_r):
            self.addCleanup(os.close, fd)
        browser._use_pipes(incoming_r, outgoing_w)
        started = time.monotonic()
        with self.assertRaises(inspection._Timeout):
            browser.send("Runtime.evaluate", {"expression": "x" * (4 * 1024 * 1024)})
        self.assertLess(time.monotonic() - started, 2)
        browser.close()

    def test_incoming_message_cap(self):
        import time
        browser = self.fake_browser(time.monotonic() + 2)
        incoming_r, incoming_w = os.pipe()
        outgoing_r, outgoing_w = os.pipe()
        self.addCleanup(os.close, outgoing_r)
        browser._use_pipes(incoming_r, outgoing_w)
        writer = threading.Thread(target=lambda: (os.write(incoming_w, b"y" * 4096), os.close(incoming_w)))
        writer.start()
        with patch.object(inspection, "MAX_MESSAGE", 1024), self.assertRaises(inspection._Closed):
            for _ in range(10):
                browser.pump(time.monotonic() + 1)
        writer.join()
        browser.close()

    def test_f4_allocation_failure_releases_everything(self):
        real_pipe, calls = os.pipe, []

        def pipe():
            calls.append(1)
            if len(calls) == 2:
                raise OSError(24, "Too many open files")
            return real_pipe()

        before_fds = set(os.listdir("/dev/fd"))
        before_dirs = set(Path(tempfile.gettempdir()).glob("ls-inspect-*"))
        with patch.object(inspection.os, "pipe", pipe), self.assertRaises(inspection._LaunchFailed):
            inspection.Browser("/usr/bin/true", 1024, 768, 0)
        self.assertEqual(set(os.listdir("/dev/fd")), before_fds)
        self.assertEqual(set(Path(tempfile.gettempdir()).glob("ls-inspect-*")), before_dirs)


@needs_browser
class ReviewTwoRepairTests(InspectionCase):
    """Frozen regressions for review-2 (Codex gpt-6-astra, REJECT at 94452bb). Each failed before its repair."""

    def test_r1_credential_cut_by_the_browser_clip_is_still_redacted(self):
        sid = self.space("Cut", '<main>api_key="' + "private phrase " * 80 + '"</main>')
        report = self.inspect(sid, text_limit=100)
        self.assertNotIn("private", report["text"]["content"], report["text"])
        self.assertIn("[REDACTED]", report["text"]["content"])

    def _settling(self, on_settle):
        """Wrap sample() so `on_settle(run)` runs on every sample from the one where the Space could first count
        as settled. The hook's clock starts at the first successful sample, no later than the driver's own
        stable_since, so it always acts on or before the settling sample (no race with a fast settle)."""
        original, state = inspection._Run.sample, {}

        def sample(run):
            value = original(run)
            if value is not None:
                state.setdefault("first", time.monotonic())
                if time.monotonic() - state["first"] >= inspection.SETTLE_MS / 1000:
                    on_settle(run)
            return value
        return patch.object(inspection._Run, "sample", sample)

    def test_r2_a_navigation_seen_at_the_settling_sample_is_not_loaded(self):
        sid = self.space("Nav", "<main>steady</main>")
        with self._settling(lambda run: setattr(run, "reloaded", True)):
            report = self.inspect(sid, timeout_s=8)
        self.assertEqual(report["outcome"], "failed", report)
        self.assertEqual(report["readiness"]["reason"], "space_navigated")

    def test_r2_settling_after_the_deadline_is_timed_out(self):
        sid = self.space("Late", "<main>steady</main>")
        started = time.monotonic()
        with self._settling(lambda run: time.sleep(max(0.0, started + 3.4 - time.monotonic()))):
            report = self.inspect(sid, timeout_s=3)
        self.assertEqual(report["outcome"], "timed_out", report)
        self.assertFalse(report["readiness"]["settled"])

    def test_r3_equal_length_changes_never_settle(self):
        sid = self.space("Flip", '<main id=m>AAAA</main><script type="module">'
                         'const m = document.getElementById("m");'
                         'setInterval(() => { m.textContent = m.textContent === "AAAA" ? "BBBB" : "AAAA" }, 150)</script>')
        report = self.inspect(sid, timeout_s=5)
        self.assertEqual(report["outcome"], "timed_out", report)
        self.assertFalse(report["readiness"]["settled"])
        self.assertEqual(report["readiness"]["reason"], "content_still_changing")

    def test_r3_control_static_space_still_settles(self):
        sid = self.space("Still", "<main>quiet</main>")
        self.assertEqual(self.inspect(sid)["outcome"], "loaded")

    def test_r4_launch_works_when_descriptors_sit_around_100(self):
        path, _ = inspection.find_renderer()
        filler = []
        while True:
            fd = os.open(os.devnull, os.O_RDONLY)
            if fd >= 98:
                os.close(fd)
                break
            filler.append(fd)
        try:
            browser = inspection.Browser(path, 1024, 768, time.monotonic() + 15)
        finally:
            for fd in filler:
                os.close(fd)
        try:
            self.assertIn("product", browser.call("Browser.getVersion"))
        finally:
            browser.close()

    def test_r5_cancellation_inside_the_constructor_releases_everything(self):
        path, _ = inspection.find_renderer()
        real_pipe, calls = os.pipe, []

        def pipe():
            calls.append(1)
            if len(calls) == 2:
                raise KeyboardInterrupt
            return real_pipe()

        before_fds = set(os.listdir("/dev/fd"))
        before_dirs = set(Path(tempfile.gettempdir()).glob("ls-inspect-*"))
        with patch.object(inspection.os, "pipe", pipe), self.assertRaises(KeyboardInterrupt):
            inspection.Browser(path, 1024, 768, time.monotonic() + 10)
        self.assertEqual(set(os.listdir("/dev/fd")), before_fds)
        self.assertEqual(set(Path(tempfile.gettempdir()).glob("ls-inspect-*")), before_dirs)

    def test_r5_failure_after_spawn_kills_the_browser(self):
        path, _ = inspection.find_renderer()
        before_dirs = set(Path(tempfile.gettempdir()).glob("ls-inspect-*"))
        spawned = []
        real_spawn = os.posix_spawn

        def spawn(*args, **kwargs):
            spawned.append(real_spawn(*args, **kwargs))
            return spawned[-1]

        with patch.object(inspection.os, "posix_spawn", spawn), \
                patch.object(inspection.os, "set_blocking", side_effect=OSError(9, "Bad file descriptor")), \
                self.assertRaises(inspection._LaunchFailed):
            inspection.Browser(path, 1024, 768, time.monotonic() + 10)
        self.assertEqual(len(spawned), 1)
        with self.assertRaises(ChildProcessError):
            os.waitpid(spawned[0], os.WNOHANG)                    # already reaped
        self.assertEqual(set(Path(tempfile.gettempdir()).glob("ls-inspect-*")), before_dirs)


class ReviewTwoProtocolTests(unittest.TestCase):
    """Review-2 F6 and F7, without a browser."""

    def test_r6_complete_messages_buffered_during_a_stalled_write_are_bounded(self):
        browser = inspection.Browser.__new__(inspection.Browser)
        browser.deadline, browser.buf, browser.next_id, browser.responses, browser.listeners = \
            time.monotonic() + 5, b"", 0, {}, []
        browser.max_message, browser.pid, browser.tmp = 0, None, None
        incoming_r, incoming_w = os.pipe()
        outgoing_r, outgoing_w = os.pipe()               # never read: the write stalls
        self.addCleanup(os.close, outgoing_r)
        browser._use_pipes(incoming_r, outgoing_w)
        stop = threading.Event()

        def flood():
            try:
                while not stop.is_set():
                    os.write(incoming_w, b'{"method":"x"}\0' * 64)
            except OSError:
                pass
            finally:
                os.close(incoming_w)

        writer = threading.Thread(target=flood)
        writer.start()
        started = time.monotonic()
        try:
            with patch.object(inspection, "MAX_BUFFERED", 64 * 1024), self.assertRaises(inspection._Closed):
                browser.send("Runtime.evaluate", {"expression": "x" * (4 * 1024 * 1024)})
            self.assertLess(time.monotonic() - started, 4)
            self.assertLessEqual(len(browser.buf), 64 * 1024 + (1 << 20))
        finally:
            stop.set()
            browser.close()
            writer.join()

    def _run(self, deadline, results):
        class FakeBrowser:
            listeners = []

            def __init__(self):
                self.deadline, self.sent = deadline, []

            def call(self, method, params=None, session=None, timeout=None):
                self.sent.append(params["expression"])
                return {}

        class Adapter:
            calls = 0

            def call(self, op, args):
                Adapter.calls += 1
                return {"ok": True, "result": results}

        run = inspection._Run(FakeBrowser(), Adapter(), 100, False)
        return run, Adapter

    def test_r7_requests_are_not_served_after_the_deadline(self):
        run, adapter = self._run(time.monotonic() - 1, "x")
        with self.assertRaises(inspection._Timeout):
            run.serve({"requests": [{"id": i, "op": "meta", "args": {}} for i in range(1000)]})
        self.assertEqual(adapter.calls, 0)

    def test_r7_replies_are_batched_and_the_response_budget_holds(self):
        run, adapter = self._run(time.monotonic() + 30, "y" * 300_000)
        with patch.object(inspection, "MAX_REPLY_TOTAL", 1_000_000):
            run.serve({"requests": [{"id": i, "op": "meta", "args": {}} for i in range(10)]})
        self.assertGreater(len(run.b.sent), 1)
        self.assertTrue(all(len(body) <= inspection.MAX_REPLY_BATCH + inspection.MAX_REPLY_ITEM for body in run.b.sent))
        self.assertLessEqual(sum(len(body) for body in run.b.sent), 1_000_000 + 10 * 200)
        self.assertEqual(sum(1 for body in run.b.sent for _, reply in sent_replies(body)
                             if reply.get("error", {}).get("code") == "limit"), run.reply_limited)
        self.assertEqual(run.reply_limited, 7)


@needs_browser
class ReviewThreeRepairTests(InspectionCase):
    """Frozen regressions for review-3 (Codex gpt-6-astra, REJECT at 75085a0). Each failed before its repair."""

    def test_s1_cut_credential_in_the_title_is_redacted(self):
        sid = self.space("T", '<title>api_key="' + "private phrase " * 100 + '"</title><main>x</main>')
        report = self.inspect(sid)
        self.assertNotIn("private", report["text"]["title"], report["text"])

    def test_s1_cut_credential_containing_an_apostrophe_is_redacted(self):
        sid = self.space("A", '<main>password="' + "don't share this " * 40 + '"</main>')
        report = self.inspect(sid, text_limit=100)
        self.assertNotIn("share", report["text"]["content"], report["text"])
        self.assertIn("[REDACTED]", report["text"]["content"])

    def test_s1_a_generic_secret_cut_at_the_clip_is_not_partly_returned(self):
        # Review-4 F3: the input must actually exceed text_limit + TEXT_SLACK, so the browser clip cuts the token.
        token = "Q" * 30 + "abcdefghijklmnopqrstuvwxyz0123456789" * 20         # one long secret-shaped token
        body = "word " * 50 + token
        self.assertGreater(len(body), 400 + inspection.TEXT_SLACK)
        sid = self.space("G", "<main>" + body + "</main>")
        report = self.inspect(sid, text_limit=400)
        self.assertTrue(report["text"]["truncated"])
        self.assertGreater(report["text"]["chars"], 400 + inspection.TEXT_SLACK)
        self.assertNotIn("QQQQ", report["text"]["content"], report["text"])

    def test_s4_launch_failure_reports_the_real_cleanup_receipt(self):
        sid = self.space("Any", "<main>x</main>")
        fake = self.home / "not-a-browser"
        fake.write_bytes(b"\x00\x01 not an executable format")
        fake.chmod(0o755)
        with patch.dict(os.environ, {inspection.BROWSER_ENV: str(fake)}), \
                patch.object(inspection.Browser, "close",
                             lambda b, real=inspection.Browser.close: {**real(b), "temp_removed": False}):
            report = self.inspect(sid, timeout_s=5)
        self.assertEqual(report["error"]["code"], "renderer_launch_failed")
        self.assertEqual(report["cleanup"], {"process_exited": True, "temp_removed": False})
        self.assertTrue(any(item.startswith("cleanup_incomplete") for item in report["limitations"]))


class ReviewThreeProtocolTests(InspectionCase):
    """Review-3 S2 and S3, without a browser."""

    def test_s2_dispatching_a_buffered_flood_honours_the_deadline(self):
        browser = inspection.Browser.__new__(inspection.Browser)
        browser.buf = b'{"method":"Runtime.consoleAPICalled","params":{"type":"log","args":[]}}\0' * 60000
        browser.deadline, browser.next_id, browser.responses, browser.max_message = time.monotonic() + 0.3, 0, {}, 0
        seen = []
        browser.listeners = [lambda message: (seen.append(1), time.sleep(0.0005))]   # a listener with real cost
        started = time.monotonic()
        with self.assertRaises(inspection._Timeout):
            browser._dispatch()
        self.assertLess(time.monotonic() - started, 1.5)
        self.assertLess(len(seen), 60000)

    def _serve(self, results, **limits_):
        class FakeBrowser:
            listeners = []
            deadline = time.monotonic() + 30

            def __init__(self):
                self.sent = []

            def call(self, method, params=None, session=None, timeout=None):
                self.sent.append(params["expression"])
                return {}

        class Adapter:
            calls = 0

            def call(self, op, args):
                Adapter.calls += 1
                return {"ok": True, "result": results}

        run = inspection._Run(FakeBrowser(), Adapter(), 100, False)
        with (patch.multiple(inspection, **limits_) if limits_ else contextlib.nullcontext()):
            run.serve({"requests": [{"id": i, "op": "meta", "args": {}} for i in range(10)]})
        return run, Adapter.calls

    def test_s3_one_oversized_reply_is_refused_not_sent(self):
        run, calls = self._serve("z" * (2 * 1024 * 1024))
        self.assertTrue(all(len(body) <= inspection.MAX_REPLY_BATCH + inspection.MAX_REPLY_ITEM for body in run.b.sent))
        self.assertEqual(sum(len(body) for body in run.b.sent) < 64 * 1024, True)
        self.assertEqual(run.reply_limited, 10)

    def test_s3_total_reply_bytes_never_exceed_the_budget(self):
        run, calls = self._serve("y" * 300_000, MAX_REPLY_TOTAL=1_000_000)
        self.assertLessEqual(sum(len(body) for body in run.b.sent), 1_000_000 + 10 * 200)
        self.assertEqual(calls, 10)
        self.assertEqual(run.reply_limited, 10 - 3)

    def snapshot_adapter(self, rows, size):
        sid = projects.create_space("Big", owner="Demo", author="agent:demo", files={"index.html": "<main>x</main>"})["id"]
        grants.decide(sid, "data", "grant", actor="user")
        for index in range(rows):
            records.put(sid, "items", f"r{index:04}", {"v": "x" * size}, actor="agent:demo")
        conn = inspection._open_snapshot()
        self.addCleanup(conn.close)
        return inspection.PassiveAdapter(inspection.Snapshot(conn, sid, 1))

    def test_s3_query_refuses_a_collection_over_the_byte_budget(self):
        adapter = self.snapshot_adapter(20, 10_000)
        with patch.object(inspection, "MAX_QUERY_BYTES", 100_000):
            reply = adapter.call("data.query", {"collection": "items", "limit": 1})
        self.assertEqual(reply["ok"], False, reply)
        self.assertEqual(reply["error"]["code"], "limit")

    def test_s3_query_stops_at_the_deadline(self):
        adapter = self.snapshot_adapter(5, 10)
        adapter.deadline = time.monotonic() - 1
        with self.assertRaises(inspection._Timeout):
            adapter.call("data.query", {"collection": "items"})

    def test_s3_control_small_query_is_served(self):
        adapter = self.snapshot_adapter(3, 10)
        reply = adapter.call("data.query", {"collection": "items", "limit": 2})
        self.assertTrue(reply["ok"], reply)
        self.assertEqual((len(reply["result"]["records"]), reply["result"]["total"]), (2, 3))


class ReviewFourRepairTests(InspectionCase):
    """Frozen regressions for review-4 (Codex gpt-6-astra, REJECT at af49a0a). Each failed before its repair."""

    def test_q1_backslash_runs_redact_in_linear_time(self):
        for n in (40, 400, 4000):
            for text in ('password="' + "\\" * n + 'x" end', 'password="' + "\\" * n, "api_key='" + "\\" * n + "'"):
                started = time.monotonic()
                inspection._redact_cut(text)
                self.assertLess(time.monotonic() - started, 0.5, (n, text[:20]))

    def test_q1_control_cut_and_closed_values_still_redact(self):
        self.assertNotIn("secret", inspection._redact_cut('password="sec\\"ret secret'))
        self.assertNotIn("secret", inspection._redact_cut('password="secret\\'))   # ends in a dangling escape
        # Uncut text keeps everything after a closed value (cut text drops its unfinished last token by design).
        self.assertIn("visible", inspection._redact_cut('password="x" visible', cut=False))
        self.assertNotIn("x", inspection._redact_cut('password="x" visible', cut=False).replace("[REDACTED]", ""))

    @needs_browser
    def test_q2_continuous_denied_requests_are_not_settled(self):
        sid = self.space("Deny", '<main>static</main><script type="module">'
                         'setInterval(() => space.get("notes", "n").catch(() => {}), 200)</script>')
        grants.decide(sid, "data", "deny", actor="user")
        report = self.inspect(sid, timeout_s=5)
        self.assertEqual(report["outcome"], "timed_out", report)
        self.assertFalse(report["readiness"]["settled"])
        self.assertEqual(report["readiness"]["reason"], "bridge_still_active")
        # Headless Chrome throttles this page's timers to about one per second, so ~4 denials land in 5 s.
        self.assertGreaterEqual(report["denied"].get("data.get", 0), 3, report["denied"])

    @needs_browser
    def test_q2_control_one_denial_then_quiet_still_settles(self):
        sid = self.space("Once", '<main>static</main><script type="module">'
                         'space.get("notes", "n").catch(() => {})</script>')
        grants.decide(sid, "data", "deny", actor="user")
        report = self.inspect(sid)
        self.assertEqual(report["outcome"], "loaded", report)
        self.assertEqual(report["denied"], {"data.get": 1})


class ReviewFiveRepairTests(InspectionCase):
    """Frozen regressions for review-5 (Codex gpt-6-astra, REJECT at f451ab5). Each failed before its repair."""

    # Every logs.redact form whose value is unbounded (quoted): only these can outrun TEXT_SLACK at a browser cut.
    QUOTED_FORMS = ['api_key="{}"', "api_key='{}'", 'password: "{}"', '"client_secret": "{}"',
                    'Bearer "{}"', "Bearer '{}'", 'authorization="Bearer {}"']

    def finish(self, text, title=""):
        """Run _finish on a sample cut exactly as the browser cuts it (text_limit + TEXT_SLACK)."""
        limit = 100
        keep = limit + inspection.TEXT_SLACK
        run = type("R", (), {"text_limit": limit, "entries": [], "counts": {"error": 0}, "dropped": 0,
                             "network_blocked": 0, "network": [], "events": [], "host_notices": {}, "booted": True,
                             "stable_since": None})()
        adapter = type("A", (), {"lifecycle": "loaded", "guest_logs": {}, "refused": {}, "denied": {}, "served": {}})()
        report = {"readiness": {}, "limitations": [], "outcome": "loaded",
                  "text": {"text": text[:keep], "chars": len(text), "title": title[:1000], "title_chars": len(title),
                           # The browser reports its own cuts (review-7 U1); model them as the sample() script does.
                           "text_cut": len(text) > keep, "title_cut": len(title) > 1000,
                           "nodes": 1, "images": 0,
                           "canvases": 0, "svgs": 0, "failure": False, "mutations": 0}}
        inspection._finish(run, adapter, report)
        return report["text"]

    def test_r1_every_quoted_secret_form_cut_by_the_browser_is_redacted(self):
        secret = "abc.def." * 200                                       # longer than any slack
        for form in self.QUOTED_FORMS:
            for lead in (0, 40, 99):
                text = ("w" * (lead - 1) + " " if lead else "") + form.format(secret)
                with self.subTest(form=form, lead=lead):
                    out = self.finish(text, title=text)
                    self.assertNotIn("abc.def", out["content"])
                    self.assertNotIn("abc.def", out["title"])

    def test_r1_control_closed_and_harmless_text_survives(self):
        out = self.finish("The weather today: " + "plain words " * 60)
        self.assertEqual(out["content"], ("The weather today: " + "plain words " * 60)[:100])

    def test_r1_a_generic_token_cut_at_the_boundary_is_dropped_not_partly_returned(self):
        # An early redaction shrinks the text, pulling the cut token's first characters into the returned window.
        keep = 100 + inspection.TEXT_SLACK
        head = "api_key=" + "k" * 240 + " "
        text = head + "w" * (keep - len(head) - 20) + " " + "T" * 19 + "S" * 60     # token cut after 19+ chars
        out = self.finish(text)
        self.assertNotIn("TTTT", out["content"], out)

    def snapshot_adapter(self, rows):
        sid = projects.create_space("Big", owner="Demo", author="agent:demo", files={"index.html": "<main>x</main>"})["id"]
        grants.decide(sid, "data", "grant", actor="user")
        for index in range(rows):
            records.put(sid, "items", f"r{index:05}", {"v": index}, actor="agent:demo")
        conn = inspection._open_snapshot()
        self.addCleanup(conn.close)
        return inspection.PassiveAdapter(inspection.Snapshot(conn, sid, 1))

    def test_r2_query_filtering_stops_at_the_deadline(self):
        adapter = self.snapshot_adapter(2000)
        where = {f"missing{index}": None for index in range(10000)}       # every predicate matches every record
        adapter.deadline = time.monotonic() + 0.3
        started = time.monotonic()
        with self.assertRaises(inspection._Timeout):
            adapter.call("data.query", {"collection": "items", "where": where, "limit": 1})
        self.assertLess(time.monotonic() - started, 1.0)

    def test_r2_control_filtered_query_matches_production(self):
        adapter = self.snapshot_adapter(30)
        adapter.deadline = time.monotonic() + 30
        reply = adapter.call("data.query", {"collection": "items", "where": {"v": 7}})
        live = records.query(adapter.snap.sid, "items", where={"v": 7})
        self.assertEqual(reply["result"]["records"], live["records"])
        self.assertEqual(reply["result"]["total"], live["total"])
        reply = adapter.call("data.query", {"collection": "items", "order": "-v", "limit": 3, "offset": 2})
        live = records.query(adapter.snap.sid, "items", order="-v", limit=3, offset=2)
        self.assertEqual(reply["result"]["records"], live["records"])


class ReviewSixRepairTests(InspectionCase):
    """Frozen regressions for review-6 (Codex gpt-6-astra, REJECT at b99bb8f). Each failed before its repair."""

    def snapshot_adapter(self, rows):
        sid = projects.create_space("Big", owner="Demo", author="agent:demo", files={"index.html": "<main>x</main>"})["id"]
        grants.decide(sid, "data", "grant", actor="user")
        for index in range(rows):
            records.put(sid, "items", f"r{index:05}", {"v": index % 7, "s": f"k{index}"}, actor="agent:demo")
        conn = inspection._open_snapshot()
        self.addCleanup(conn.close)
        return inspection.PassiveAdapter(inspection.Snapshot(conn, sid, 1))

    def test_t1_a_huge_order_string_is_parsed_once(self):
        # At b99bb8f this took ~5 s for 2,000 records (the order string was re-stripped per record).
        adapter = self.snapshot_adapter(2000)
        adapter.deadline = time.monotonic() + 30
        started = time.monotonic()
        reply = adapter.call("data.query", {"collection": "items", "order": "-" * 900000 + "v", "limit": 1})
        self.assertLess(time.monotonic() - started, 1.0)
        self.assertTrue(reply["ok"], reply)

    def test_t1_ordering_stops_at_the_deadline(self):
        adapter = self.snapshot_adapter(1500)
        real_field = records._field

        def slow_field(record, name):                    # key building that would far outlive the deadline
            time.sleep(0.002)
            return real_field(record, name)

        adapter.deadline = time.monotonic() + 0.4
        started = time.monotonic()
        with patch.object(inspection.records, "_field", slow_field), self.assertRaises(inspection._Timeout):
            adapter.call("data.query", {"collection": "items", "order": "v", "limit": 1})
        self.assertLess(time.monotonic() - started, 1.5)

    def test_t1_control_ordering_matches_production(self):
        adapter = self.snapshot_adapter(40)
        adapter.deadline = time.monotonic() + 30
        for order in ("v", "-v", "s", "-s", "missing", "--v", None):
            for where in (None, {"v": 3}):
                args = {"collection": "items", "limit": 9, "offset": 2, **({"order": order} if order else {}),
                        **({"where": where} if where else {})}
                with self.subTest(order=order, where=where):
                    reply = adapter.call("data.query", args)
                    live = records.query(adapter.snap.sid, "items", where=where, order=order, limit=9, offset=2)
                    self.assertEqual(reply["result"]["records"], live["records"])
                    self.assertEqual(reply["result"]["total"], live["total"])

    def fake_run(self):
        class FakeBrowser:
            listeners = []
            deadline = time.monotonic() + 30

            def __init__(self):
                self.sent = []

            def call(self, method, params=None, session=None, timeout=None):
                self.sent.append(params["expression"])
                return {}

            def send(self, *args, **kwargs):
                return 0

        class Adapter:
            refused, denied, served, lifecycle, guest_logs = {}, {}, {}, "loaded", {}

            def call(self, op, args):
                return {"ok": True, "result": "z" * (2 * 1024 * 1024)}

        run = inspection._Run(FakeBrowser(), Adapter(), 100, False)
        run.page, run.page_target = "PAGE", "HOSTFRAME"
        return run

    def test_t2_queue_overflow_and_reply_limits_are_reported(self):
        run = self.fake_run()
        run.serve({"requests": [{"id": 1, "op": "meta", "args": {}}], "events": [], "refused": 7})
        report = {"readiness": {}, "limitations": [], "outcome": "loaded", "text": None}
        inspection._finish(run, run.adapter, report)
        self.assertEqual(report["limited"], {"queue_full": 7, "reply_too_large": 1}, report)
        self.assertTrue(any(item.startswith("requests_limited") for item in report["limitations"]))

    def test_t2_control_no_limits_no_noise(self):
        run = self.fake_run()
        report = {"readiness": {}, "limitations": [], "outcome": "loaded", "text": None}
        inspection._finish(run, run.adapter, report)
        self.assertEqual(report["limited"], {})
        self.assertFalse(any(item.startswith("requests_limited") for item in report["limitations"]))

    def test_t3_guest_console_errors_on_the_page_session_are_counted(self):
        run = self.fake_run()
        run.on_event({"method": "Runtime.executionContextCreated", "sessionId": "PAGE",
                      "params": {"context": {"id": 5, "auxData": {"frameId": "GUESTFRAME"}}}})
        run.on_event({"method": "Runtime.consoleAPICalled", "sessionId": "PAGE",
                      "params": {"type": "error", "executionContextId": 5, "args": [{"value": "in-process guest"}]}})
        self.assertEqual(run.counts["error"], 1)
        self.assertEqual(run.entries[0]["text"], "in-process guest")

    def test_t3_control_host_page_console_is_still_ignored(self):
        run = self.fake_run()
        run.on_event({"method": "Runtime.executionContextCreated", "sessionId": "PAGE",
                      "params": {"context": {"id": 1, "auxData": {"frameId": "HOSTFRAME", "isDefault": True}}}})
        run.on_event({"method": "Runtime.consoleAPICalled", "sessionId": "PAGE",
                      "params": {"type": "error", "executionContextId": 1, "args": [{"value": "host"}]}})
        self.assertEqual(run.counts["error"], 0)


class ReviewSevenRepairTests(InspectionCase):
    """Frozen regressions for review-7 (Codex gpt-6-astra, ACCEPT-WITH-FIXES at 099570f). Each failed before repair."""

    @needs_browser
    def test_u1_uncut_unicode_text_and_title_are_returned_whole(self):
        sid = self.space("U", "<title>Done 🟢</title><main>Status 🟢 ready</main>")
        report = self.inspect(sid)
        self.assertEqual(report["text"]["content"], "Status 🟢 ready", report["text"])
        self.assertEqual(report["text"]["title"], "Done 🟢")
        self.assertFalse(report["text"]["truncated"])

    @needs_browser
    def test_u1_emoji_only_text_survives(self):
        sid = self.space("E", "<main>🟢🟢🟢</main>")
        self.assertEqual(self.inspect(sid)["text"]["content"], "🟢🟢🟢")

    def adapter_with(self, rows, data):
        sid = projects.create_space("Q", owner="Demo", author="agent:demo", files={"index.html": "<main>x</main>"})["id"]
        grants.decide(sid, "data", "grant", actor="user")
        for index in range(rows):
            records.put(sid, "items", f"r{index:03}", data(index), actor="agent:demo")
        conn = inspection._open_snapshot()
        self.addCleanup(conn.close)
        adapter = inspection.PassiveAdapter(inspection.Snapshot(conn, sid, 1))
        adapter.deadline = time.monotonic() + 30
        return adapter

    def test_u2_collection_size_refusal_is_reported_in_limited(self):
        adapter = self.adapter_with(5, lambda i: {"v": "x" * 1000})
        with patch.object(inspection, "MAX_QUERY_BYTES", 2000):
            reply = adapter.call("data.query", {"collection": "items", "limit": 1})
        self.assertEqual(reply["error"]["code"], "limit")
        run = ReviewSixRepairTests.fake_run(self)  # type: ignore[arg-type]  # uses no ReviewSix state
        report = {"readiness": {}, "limitations": [], "outcome": "loaded", "text": None}
        inspection._finish(run, adapter, report)
        self.assertEqual(report["limited"], {"collection_too_large": 1}, report)
        self.assertTrue(any(item.startswith("requests_limited") for item in report["limitations"]))

    def test_u3_order_dash_matches_production(self):
        adapter = self.adapter_with(4, lambda i: {"": 3 - i, "n": i})
        for order in ("-", "--", "-n", "n"):
            with self.subTest(order=order):
                reply = adapter.call("data.query", {"collection": "items", "order": order})
                live = records.query(adapter.snap.sid, "items", order=order)
                self.assertEqual([r["id"] for r in reply["result"]["records"]], [r["id"] for r in live["records"]])

    def test_u4_unawaited_acknowledgements_are_not_retained(self):
        browser = inspection.Browser.__new__(inspection.Browser)
        browser.buf = b"".join(b'{"id":%d,"result":{}}\0' % i for i in range(1, 100001))
        browser.deadline, browser.next_id, browser.responses, browser.max_message = time.monotonic() + 30, 0, {}, 0
        browser.listeners, browser.awaited = [], {7}
        browser._dispatch()
        self.assertEqual(list(browser.responses), [7])


class ReviewEightRepairTests(InspectionCase):
    """Frozen regressions for review-8 (Codex gpt-6-astra, REJECT at fbc47e0). Each failed before its repair."""

    def stubborn_browser(self):
        """A Browser whose 'browser' is a real process group that ignores SIGTERM, with a real profile dir."""
        browser = inspection.Browser.__new__(inspection.Browser)
        browser.tmp = tempfile.mkdtemp(prefix="ls-inspect-test-")
        browser.read_fd = browser.write_fd = -1
        browser.pid = os.posix_spawn("/bin/sh", ["/bin/sh", "-c", 'trap "" TERM; exec /bin/sleep 30'],
                                     {"PATH": "/usr/bin:/bin"}, setsid=True)
        time.sleep(0.3)                                    # let the trap install before SIGTERM arrives
        self.addCleanup(shutil.rmtree, browser.tmp, True)
        return browser

    def test_v1_cancellation_during_cleanup_still_kills_and_removes_then_reraises(self):
        browser = self.stubborn_browser()
        pid, tmp = browser.pid, browser.tmp
        real_sleep, calls = time.sleep, []

        def sleep(seconds):
            calls.append(seconds)
            if len(calls) == 1:
                raise KeyboardInterrupt                    # cancellation lands in the termination wait
            real_sleep(seconds)

        with patch.object(inspection.time, "sleep", sleep), self.assertRaises(KeyboardInterrupt):
            browser.close()
        with self.assertRaises(ChildProcessError):
            os.waitpid(pid, os.WNOHANG)                    # killed and reaped despite the cancellation
        self.assertFalse(os.path.exists(tmp))
        self.assertIsNone(browser.pid)

    def test_v1_control_uncancelled_cleanup_returns_a_complete_receipt(self):
        browser = self.stubborn_browser()
        self.assertEqual(browser.close(), {"process_exited": True, "temp_removed": True})

    @needs_browser
    def test_v2_reply_fields_named_proto_reach_the_space(self):
        sid = self.space("P", '<main id=m>…</main><script type="module">'
                         'const r = await space.get("notes", "a");'
                         'document.getElementById("m").textContent = Object.hasOwn(r.data, "__proto__") ? '
                         '"own:" + r.data["__proto__"].marker + ":" + r.data.safe : "lost:" + JSON.stringify(r.data)'
                         '</script>')
        records.put(sid, "notes", "a", json.loads('{"__proto__": {"marker": "saved value"}, "safe": 1}'),
                    actor="agent:demo")
        report = self.inspect(sid)
        self.assertEqual(report["text"]["content"], "own:saved value:1", report["text"])


class ReviewNineRepairTests(InspectionCase):
    """Frozen regressions for review-9 (Codex gpt-6-astra, REJECT at 91d2010). Each failed before its repair."""

    finish = ReviewFiveRepairTests.finish

    CONTAINERS = [json.dumps({"authorization": {"token": "demo-only-secret", "padding": "ordinary words " * 100}}),
                  json.dumps({"password": ["demo-only-secret", "ordinary words " * 100]}),
                  'api_key = {"inner": "demo-only-secret", "pad": "' + "w " * 300 + '"}',
                  "lead text " * 5 + json.dumps({"a": 1, "client_secret": [["demo-only-secret"] * 50]})]

    def test_w1_cut_credential_containers_are_redacted_in_body_and_title(self):
        for text in self.CONTAINERS:
            with self.subTest(text=text[:40]):
                out = self.finish(text, title=text)
                self.assertNotIn("demo-only-secret", out["content"])
                self.assertNotIn("demo-only-secret", out["title"])
                self.assertIn("[REDACTED]", out["content"])

    def test_w1_control_uncut_json_is_still_redacted_structurally(self):
        text = json.dumps({"authorization": {"token": "demo-only-secret"}, "note": "kept"})
        out = inspection._redact_cut(text, cut=False)
        self.assertNotIn("demo-only-secret", out)
        self.assertIn("kept", out)

    def test_w1_control_cut_text_without_credentials_is_kept(self):
        text = json.dumps({"settings": {"theme": "dark", "padding": "ordinary words " * 100}})
        out = self.finish(text)
        self.assertTrue(out["content"].startswith('{"settings": {"theme": "dark"'), out["content"])

    def test_w2_complete_unicode_text_is_not_reported_truncated(self):
        run = type("R", (), {"text_limit": 2, "entries": [], "counts": {"error": 0}, "dropped": 0,
                             "network_blocked": 0, "network": [], "events": [], "host_notices": {}, "booted": True,
                             "stable_since": None})()
        adapter = type("A", (), {"lifecycle": "loaded", "guest_logs": {}, "refused": {}, "denied": {}, "served": {}})()
        report = {"readiness": {}, "limitations": [], "outcome": "loaded",
                  "text": {"text": "🟢🟢", "chars": 4, "title": "", "title_chars": 0, "text_cut": False,
                           "title_cut": False, "nodes": 1, "images": 0, "canvases": 0, "svgs": 0,
                           "failure": False, "mutations": 0}}
        inspection._finish(run, adapter, report)
        self.assertEqual(report["text"]["content"], "🟢🟢")
        self.assertFalse(report["text"]["truncated"])


class ReviewTenRepairTests(InspectionCase):
    """Frozen regressions for review-10 (Codex gpt-6-astra, REJECT at d4f5265). Each failed before its repair."""

    finish = ReviewFiveRepairTests.finish
    REVIEW_CASE = '{"note":"password: {}", "nested":"{\\"password\\":\\"demo-only-secret\\"}"}'

    def test_x1_valid_json_is_redacted_structurally_before_any_textual_rewrite(self):
        self.assertEqual(json.loads(self.REVIEW_CASE)["nested"], '{"password":"demo-only-secret"}')
        out = self.finish(self.REVIEW_CASE, title=self.REVIEW_CASE)
        self.assertNotIn("demo-only-secret", out["content"])
        self.assertNotIn("demo-only-secret", out["title"])
        self.assertNotIn("demo-only-secret", inspection._redact_cut(self.REVIEW_CASE, cut=False))

    def test_x1_cut_escaped_nested_credentials_are_redacted(self):
        for text in ('{"nested":"{\\"password\\":\\"demo-only-secret' + "w" * 400,
                     '{"nested":"{\\"password\\":{\\"v\\":\\"demo-only-secret\\", \\"pad\\":\\"' + "w " * 300):
            with self.subTest(text=text[:30]):
                out = self.finish(text, title=text)
                self.assertNotIn("demo-only-secret", out["content"])
                self.assertNotIn("demo-only-secret", out["title"])

    def test_x1_closed_escaped_credential_mid_cut_text_is_redacted(self):
        # Uncut, the shared redactor finds this through the nested JSON string; the cut must not expose it.
        whole = json.dumps({"n": json.dumps({"password": "demo-only-secret"}), "pad": "ordinary words " * 100})
        self.assertNotIn("demo-only-secret", inspection.logs.redact(whole))
        out = self.finish(whole, title=whole)
        self.assertNotIn("demo-only-secret", out["content"])
        self.assertNotIn("demo-only-secret", out["title"])

    def test_x1_control_ordinary_cut_text_is_untouched(self):
        text = 'Say "hello" to the team: ' + "ordinary words " * 60
        self.assertEqual(self.finish(text)["content"], text[:100])

    def test_x2_cut_redaction_is_linear_on_adversarial_runs(self):
        # Found by Forge while timing the X1 repair: \\S+\\Z (since b99bb8f) took ~5 s on 50k characters.
        for text in ("a" * 200000 + " ", "\\" * 200000 + "x", '\\"password\\" ' * 20000,
                     'password="' * 20000, "[" * 200000, "Bearer '" * 20000):
            with self.subTest(text=text[:12]):
                started = time.monotonic()
                inspection._redact_cut(text, cut=True)
                inspection._redact_cut(text, cut=False)
                self.assertLess(time.monotonic() - started, 2.0)

    def test_x2_control_partial_token_semantics(self):
        self.assertEqual(inspection._drop_partial_token("one two thr"), "one two ")
        self.assertEqual(inspection._drop_partial_token("one two "), "one two ")
        self.assertEqual(inspection._drop_partial_token("token"), "")

    def test_x1_control_matches_the_shared_redactor_on_valid_json(self):
        for text in (self.REVIEW_CASE, json.dumps({"password": {"a": "s3"}, "note": "kept"}),
                     json.dumps([{"api_key": ["s"]}, "plain"])):
            with self.subTest(text=text[:30]):
                self.assertEqual(inspection._redact_cut(text, cut=False), inspection.logs.redact(text))


class BoundaryTests(InspectionCase):
    def test_unavailable_renderer_is_reported_not_faked(self):
        sid = self.space("Any", "<main>x</main>")
        with patch.dict(os.environ, {inspection.BROWSER_ENV: ""}):
            report = self.inspect(sid)
        self.assertEqual(report["outcome"], "unavailable")
        self.assertEqual(report["unavailable"]["code"], "renderer_unavailable")
        self.assertIsNone(report["text"])
        self.assertFalse(report["readiness"]["shell_booted"])

    def test_renderer_that_exits_is_an_error_not_success(self):
        sid = self.space("Any", "<main>x</main>")
        with patch.dict(os.environ, {inspection.BROWSER_ENV: "/usr/bin/true"}):
            report = self.inspect(sid, timeout_s=5)
        self.assertIn(report["outcome"], ("error", "timed_out"))
        self.assertEqual(report["cleanup"]["temp_removed"], True)

    def test_browser_that_cannot_start_is_an_error_and_leaves_nothing_behind(self):
        # Frozen regression: a failed posix_spawn left its ls-inspect-* profile directory behind.
        sid = self.space("Any", "<main>x</main>")
        fake = self.home / "not-a-browser"
        fake.write_bytes(b"\x00\x01 not an executable format")
        fake.chmod(0o755)
        before = set(Path(tempfile.gettempdir()).glob("ls-inspect-*"))
        with patch.dict(os.environ, {inspection.BROWSER_ENV: str(fake)}):
            report = self.inspect(sid, timeout_s=5)
        self.assertEqual(report["outcome"], "error", report)
        self.assertEqual(report["error"]["code"], "renderer_launch_failed")
        self.assertEqual(set(Path(tempfile.gettempdir()).glob("ls-inspect-*")), before)
        self.assertEqual(inspection._slots._value, inspection.MAX_CONCURRENT)

    def test_missing_revision_space_and_entry(self):
        sid = self.space("Present", "<main>x</main>")
        for space, rev, code in ((sid, 99, "not_found"), ("absent-space", 1, "not_found"), (sid, 0, "invalid")):
            with self.subTest(space=space, rev=rev), self.assertRaises(SpacesError) as raised:
                inspection.inspect(space, rev)
            self.assertEqual(raised.exception.code, code)
        projects.write_files(sid, files={"index.html": None, "other.html": "x"}, author="agent:demo", summary="drop entry")
        report = self.inspect(sid, 2)
        self.assertEqual((report["outcome"], report["readiness"]["reason"]), ("failed", "entry_missing"))

    def test_reference_resolves_by_name_and_never_guesses(self):
        sid = self.space("Desk", "<main>x</main>")
        with patch.dict(os.environ, {inspection.BROWSER_ENV: ""}):
            self.assertEqual(self.inspect("desk", 1)["space"], sid)
            self.space("DESK", "<main>y</main>")
            with self.assertRaises(SpacesError) as raised:
                inspection.inspect("Desk", 1)
        self.assertEqual(raised.exception.code, "ambiguous")

    def test_deleted_space_is_not_found(self):
        sid = self.space("Gone", "<main>x</main>")
        with patch.object(projects.upkeep, "on_delete", lambda conn, sid: False):
            projects.delete_space(sid, actor="user", confirm=sid)
        with self.assertRaises(SpacesError) as raised:
            inspection.inspect(sid, 1)
        self.assertEqual(raised.exception.code, "not_found")

    def test_bounds_are_enforced(self):
        sid = self.space("Bounds", "<main>x</main>")
        for options in ({"width": 10}, {"height": 99999}, {"timeout_s": 600}, {"text_limit": -1}, {"width": True}):
            with self.subTest(options=options), self.assertRaises(SpacesError):
                inspection.inspect(sid, 1, **options)

    def test_concurrency_cap_refuses_instead_of_queueing(self):
        sid = self.space("Busy", "<main>x</main>")
        for _ in range(inspection.MAX_CONCURRENT):
            inspection._slots.acquire()
        try:
            with self.assertRaises(SpacesError) as raised:
                inspection.inspect(sid, 1)
            self.assertEqual(raised.exception.code, "blocked")
        finally:
            for _ in range(inspection.MAX_CONCURRENT):
                inspection._slots.release()

    def test_missing_database_is_not_created(self):
        os.environ["LIVING_SPACES_DB"] = str(self.home / "absent" / "spaces.db")
        with self.assertRaises(SpacesError):
            inspection.inspect("anything", 1)
        self.assertFalse((self.home / "absent").exists())

    def test_ordinary_use_never_loads_inspection(self):
        code = (f"import sys; sys.path.insert(0, {str(ROOT / 'src' / 'living-spaces')!r}); "
                "import living_spaces_core as core; "
                "sid = core.create_space('Plain', owner='Demo', author='agent:demo', files={'index.html': 'x'})['id']; "
                "core.write_files(sid, files={'index.html': 'y'}, author='agent:demo', summary='e'); "
                "s = core.open_session(sid)['session']; core.bundle(sid); core.dispatch(sid, s, 'meta', {}); "
                "core.close_session(s); core.list_spaces(); "
                "print('living_spaces_core.inspection' in sys.modules)")
        result = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=60,
                                env={**os.environ})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "False")


if __name__ == "__main__":
    unittest.main()
