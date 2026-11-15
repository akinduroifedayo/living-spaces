"""spaces_inspect: runs real Spaces in a throwaway local Chromium and checks what is reported and what is not touched."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
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
