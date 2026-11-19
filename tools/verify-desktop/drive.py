"""Drive one real, isolated Hermes Desktop through the no-model note journey.

Launches the installed Desktop with a brand-new HERMES_HOME, userData, OS home and cwd under --state, proves the renderer
uses that storage before writing the single Living Spaces Desktop decision, opens Spaces, saves a note in the synthetic
Verification Notebook through real mouse and keyboard input, leaves and reopens it, and reads the note back both on
screen and from the plugin's SQLite store. Shutdown is the app's own normal quit (TERM to the child this script
started), then at most one TERM to the detached gateway this run started, after re-proving its identity. It never
signals by name or group and never force-kills. Survivors are reported, not killed.

Run with the Hermes runtime's Python (it provides `websockets`). See docs/verification/DESKTOP.md.
"""
import argparse, asyncio, base64, hashlib, json, os, shlex, shutil, signal, sqlite3, subprocess, sys, tempfile, time, traceback, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
KEY = "hermes.desktop.pluginDecisions.v2"
# nous.guest false is the host's own switch that blocks the welcome-trial claim and connector guest mint
# (hermes_cli/welcome_trial.py claim blockers): a fresh OS home would otherwise look like a first install and mint an account.
CONFIG = """plugins:
  enabled: [living-spaces]
nous:
  guest: false
security:
  allow_lazy_installs: false
"""

class ProductFailure(AssertionError):
    """A product expectation failed. Any other exception during the journey is a harness failure."""

def expect(cond, msg):
    if not cond: raise ProductFailure(msg)

def run(*a): return subprocess.run(list(a), capture_output=True, text=True)
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def processes():
    rows = []
    for line in run("ps", "-axo", "pid=,ppid=,pgid=,lstart=,command=").stdout.splitlines():
        p = line.strip().split(None, 8)
        if len(p) == 9: rows.append(dict(pid=int(p[0]), ppid=int(p[1]), pgid=int(p[2]), started=" ".join(p[3:8]), command=p[8]))
    return rows
def row(pid): return next((r for r in processes() if r["pid"] == pid), None)
def env_of(pid): r = run("ps", "eww", "-o", "command=", "-p", str(pid)); return r.stdout if r.returncode == 0 else ""
def has_env(pid, key, value): e = env_of(pid); return f"{key}={value} " in e or e.rstrip().endswith(f"{key}={value}")
def listeners_of(pid):
    r = run("lsof", "-nP", "-a", "-p", str(pid), "-iTCP", "-sTCP:LISTEN", "-Fn"); return [l[1:] for l in r.stdout.splitlines() if l.startswith("n")]
def port_listeners(port): r = run("lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-Fpn"); return r.stdout if r.returncode == 0 else ""
def gateways(): return [r for r in processes() if "hermes_cli.main" in r["command"] and " gateway run" in r["command"]]

class Run:
    def __init__(self, a):
        self.a, self.out, self.state = a, a.out, a.state
        self.home, self.ud, self.osh, self.tmp = (self.state / n for n in ("home", "ud", "os-home", "tmp"))
        self.result = dict(evidence_class="real Desktop, isolated disposable state, synthetic fixture", outcome="incomplete", phases={})
        self.proc = self.gw = None; self.prepared = False
    def dump(self, name, v): (self.out / name).write_text(json.dumps(v, indent=2, default=str) + "\n")
    def phase(self, k, v): self.result["phases"][k] = v; self.dump("result.json", self.result)
    def act(self, **v):
        with (self.out / "actions.jsonl").open("a") as f: f.write(json.dumps({**v, "at": time.time()}) + "\n")

    # --- CDP, bound to the Desktop this run launched ---
    def owned(self):
        r = row(self.proc.pid)
        assert r and r["started"] == self.started and r["command"].startswith(self.a.app_binary + " "), "launched Desktop identity changed"
        l = port_listeners(self.a.cdp_port); assert f"p{self.proc.pid}\n" in l and f"127.0.0.1:{self.a.cdp_port}" in l, "CDP listener not ours"
    def targets(self):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.a.cdp_port}/json/list", timeout=3) as r: return json.load(r)
    def call_many(self, cmds, target=None):
        self.owned(); import websockets
        page = target or next(t for t in self.targets() if t["type"] == "page" and "/dist/index.html" in t["url"])
        async def go():
            out = []
            async with websockets.connect(page["webSocketDebuggerUrl"], max_size=64 << 20) as ws:
                for n, (m, p) in enumerate(cmds, 1):
                    await ws.send(json.dumps(dict(id=n, method=m, params=p)))
                    while True:
                        v = json.loads(await asyncio.wait_for(ws.recv(), 20))
                        if v.get("id") == n: assert "error" not in v, v; out.append(v["result"]); break
            return out
        return asyncio.run(go())
    def call(self, m, **p): return self.call_many([(m, p)])[0]
    def eval(self, expr):
        r = self.call("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
        assert "exceptionDetails" not in r, r; return r.get("result", {}).get("value")
    def text(self): return self.eval("document.body.innerText")
    def capture(self, name):
        self.out.joinpath(name + ".png").write_bytes(base64.b64decode(self.call("Page.captureScreenshot", format="png")["data"]))
        self.out.joinpath(name + ".txt").write_text(self.text())
    def wait_text(self, *texts, timeout=90, product=False):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            t = self.text()
            for x in texts:
                if x in t: return x
            time.sleep(0.5)
        self.capture("wait-failed"); raise (ProductFailure if product else TimeoutError)(f"visible text not found: {texts}")
    def press(self, pos):
        self.call_many([("Page.bringToFront", {}), ("Input.dispatchMouseEvent", dict(type="mouseMoved", **pos)),
                        ("Input.dispatchMouseEvent", dict(type="mousePressed", button="left", clickCount=1, **pos)),
                        ("Input.dispatchMouseEvent", dict(type="mouseReleased", button="left", clickCount=1, **pos))])
    def click(self, sel):
        q = (f'[...document.querySelectorAll("button,[role=button],a,[role=menuitem]")].filter(e=>e.textContent.trim()==={json.dumps(sel[5:])})'
             if sel.startswith("text=") else f"[...document.querySelectorAll({json.dumps(sel)})]")
        pos = self.eval(f"(()=>{{const e={q}.filter(e=>e.getClientRects().length);if(e.length!==1)throw Error('expected one visible target, got '+e.length);"
                        "const r=e[0].getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()")
        self.press(pos); self.act(action="click", selector=sel, at_xy=pos)
    def guest(self, selector):
        """Read one visible element inside the Space's sandboxed frame (DOM read only; no application calls)."""
        self.owned(); import websockets
        async def go():
            hits = []
            for t in self.targets():
                if t["type"] not in ("page", "iframe"): continue
                async with websockets.connect(t["webSocketDebuggerUrl"], max_size=64 << 20) as ws:
                    await ws.send(json.dumps(dict(id=1, method="Runtime.enable"))); ctxs = []
                    while True:
                        v = json.loads(await asyncio.wait_for(ws.recv(), 10))
                        if v.get("method") == "Runtime.executionContextCreated" and v["params"]["context"].get("auxData", {}).get("isDefault"):
                            ctxs.append(v["params"]["context"]["id"])
                        if v.get("id") == 1: break
                    expr = (f"(()=>{{const es=[...document.querySelectorAll({json.dumps(selector)})].filter(e=>e.getClientRects().length);"
                            "if(es.length!==1)return null;const e=es[0],r=e.getBoundingClientRect();return{text:e.innerText,x:r.x+r.width/2,y:r.y+r.height/2}})()")
                    for n, c in enumerate(ctxs, 2):
                        await ws.send(json.dumps(dict(id=n, method="Runtime.evaluate", params=dict(expression=expr, contextId=c, returnByValue=True))))
                        while True:
                            v = json.loads(await asyncio.wait_for(ws.recv(), 10))
                            if v.get("id") == n:
                                val = v.get("result", {}).get("result", {}).get("value")
                                if val: hits.append(val)
                                break
            return hits
        hits = asyncio.run(go()); assert len(hits) == 1, f"expected one guest target for {selector}, got {len(hits)}"
        frame = self.eval('(()=>{const e=document.querySelector(\'iframe[title="Space: Verification Notebook"]\');if(!e)throw Error("no canvas frame");'
                          'const r=e.getBoundingClientRect();return{x:r.x,y:r.y}})()')
        return dict(text=hits[0]["text"], pos=dict(x=frame["x"] + hits[0]["x"], y=frame["y"] + hits[0]["y"]))
    def records(self, label):
        db = self.home / "plugin-data/living-spaces/spaces.db"
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
            res = {}
            for t in ("spaces", "records"):
                cur = conn.execute(f"SELECT * FROM {t}"); res[t] = [dict(zip([d[0] for d in cur.description], x)) for x in cur.fetchall()]
        self.dump(f"records-{label}.json", res); return res

    # --- steps ---
    def prepare(self):
        bad = [p for p in (Path.home() / ".hermes", Path.home() / "Library/Application Support") if self.state.resolve().is_relative_to(p)]
        assert not bad, f"refusing state under a real profile location: {bad}"
        self.state.mkdir(parents=True, exist_ok=False)   # never reuse or erase a previous state directory
        for d in (self.home, self.ud, self.osh, self.tmp): d.mkdir()
        repo, src = self.a.repo, self.a.repo / "src/living-spaces"
        head = run("git", "-C", str(repo), "rev-parse", "HEAD").stdout.strip()
        dirty = run("git", "-C", str(repo), "status", "--porcelain", "--untracked-files=all", "--", "src/living-spaces").stdout
        shutil.copytree(src, self.home / "plugins/living-spaces", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(src / "desktop", self.home / "desktop-plugins/living-spaces")
        (self.home / "config.yaml").write_text(CONFIG)
        stamp = self.a.app / "Contents/Resources/install-stamp.json"
        self.live_before = {g["pid"]: g["started"] for g in gateways()}
        self.real_shared_before = self.real_shared()
        facts = dict(repo_head=head, product_dirty=bool(dirty), product_files=len(list((self.home / "plugins/living-spaces").rglob("*"))),
                     app=str(self.a.app), app_stamp=json.loads(stamp.read_text()) if stamp.exists() else None,
                     app_asar_sha256=sha(self.a.app / "Contents/Resources/app.asar"), hermes_root=str(self.a.hermes_root),
                     hermes_root_head=run("git", "-C", str(self.a.hermes_root), "rev-parse", "HEAD").stdout.strip() or None,
                     python=os.path.realpath(self.a.python), state=str(self.state), credentials_copied=False,
                     cdp_port_free=not port_listeners(self.a.cdp_port), other_gateways_before=len(self.live_before))
        self.dump("prepare.json", facts)
        assert not dirty or self.a.allow_dirty, "product tree has uncommitted changes; commit them or pass --allow-dirty"
        assert facts["cdp_port_free"], f"CDP port {self.a.cdp_port} already has a listener"
        self.prepared = True; self.phase("prepare", dict(repo_head=head, dirty=bool(dirty)))
    REAL_SHARED = Path.home() / ".hermes/shared/nous_auth.json"
    def real_shared(self):
        try: st = self.REAL_SHARED.stat(); return (st.st_mtime_ns, st.st_size)
        except FileNotFoundError: return None
    def identities(self):
        """Credential stores a mint would write: per-home auth.json and the shared nous_auth.json (pinned inside the run).
        The host's empty machine marker is a first-launch probe, not an identity."""
        found = sorted(str(p) for n in ("auth.json", "nous_auth.json") for p in self.state.rglob(n))
        # The run's backend is pinned to its own shared store, and other gateways legitimately rewrite the real one on token
        # refresh, so a change there is reported as an observation, not counted as a mint by this run.
        return dict(stores_in_state=found, real_shared_store_changed_during_run=self.real_shared() != self.real_shared_before)
    def env(self):
        keep = {k: os.environ[k] for k in ("PATH", "LANG", "USER", "LOGNAME", "SHELL") if k in os.environ}
        return {**keep, "HOME": str(self.osh), "HERMES_HOME": str(self.home), "TMPDIR": str(self.tmp),
                "HERMES_DESKTOP_USER_DATA_DIR": str(self.ud), "HERMES_DESKTOP_CWD": str(self.tmp),
                "HERMES_SHARED_AUTH_DIR": str(self.home / "shared"),   # pin the shared Nous store inside the run
                "HERMES_DESKTOP_HERMES_ROOT": str(self.a.hermes_root), "HERMES_DESKTOP_PYTHON": self.a.python,
                "HERMES_DESKTOP_ISOLATED_BACKEND": "1", "HERMES_DISABLE_LAZY_INSTALLS": "1", "PYTHONDONTWRITEBYTECODE": "1",
                "HERMES_DESKTOP_SKIP_QUIT_CONFIRM": "1", "HERMES_DESKTOP_APP_NAME": "Hermes Living Spaces Verification"}
    def launch(self):
        argv = [self.a.app_binary, f"--remote-debugging-port={self.a.cdp_port}", "--remote-debugging-address=127.0.0.1"]
        log = (self.out / "desktop.log").open("wb")
        self.proc = subprocess.Popen(argv, env=self.env(), cwd=str(self.tmp), stdout=log, stderr=log, stdin=subprocess.DEVNULL, start_new_session=True)
        time.sleep(0.5); self.started = row(self.proc.pid)["started"]
        deadline = time.monotonic() + 120
        while True:
            if self.proc.poll() is not None: raise RuntimeError(f"Desktop exited {self.proc.returncode}")
            try:
                if any(t["type"] == "page" and "/dist/index.html" in t["url"] for t in self.targets()): break
            except (OSError, ValueError): pass
            if time.monotonic() > deadline: raise TimeoutError("no Desktop page after 120 s")
            time.sleep(0.5)
        self.phase("launch", dict(pid=self.proc.pid, argv=argv))
    def backend(self):
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            mine = [g for g in gateways() if has_env(g["pid"], "HERMES_HOME", self.home)]
            if len(mine) == 1 and listeners_of(mine[0]["pid"]):
                g = mine[0]; self.gw = dict(pid=g["pid"], started=g["started"], listeners=listeners_of(g["pid"]), command=g["command"])
                self.dump("backend-identity.json", self.gw); self.phase("backend", self.gw); return
            if self.proc.poll() is not None: raise RuntimeError("Desktop exited before its backend started")
            time.sleep(1)
        raise TimeoutError("this run's gateway (HERMES_HOME = run home, listening) was not found")
    def isolation_then_flag(self):
        pg = [r for r in processes() if r["pgid"] == self.proc.pid]
        rend = [r for r in pg if " --type=renderer " in r["command"]]
        dirs = [[x.split("=", 1)[1] for x in shlex.split(r["command"]) if x.startswith("--user-data-dir=")] for r in rend]
        storage = [l[1:] for l in run("lsof", "-nP", "-p", str(self.proc.pid), "-Fn").stdout.splitlines() if l.startswith("n") and "/Local Storage/" in l]
        status = self.eval("window.__HERMES_PLUGIN_SDK__.host.status()")
        rec = dict(renderer_user_data=dirs, open_local_storage=storage, host_status_hermes_home=status.get("hermes_home"))
        self.dump("isolation.json", rec)
        assert rend and all(d == [str(self.ud)] for d in dirs), "renderer userData is not this run's"
        assert str(self.ud / "Local Storage/leveldb/LOCK") in storage and all(Path(p).is_relative_to(self.ud) for p in storage), "foreign Local Storage open"
        assert Path(status.get("hermes_home", "")).resolve() == self.home.resolve(), "renderer talks to a different Hermes home"
        self.phase("isolation", "proven before any write")
        after = self.eval(f"(()=>{{const k={json.dumps(KEY)};const d=JSON.parse(localStorage.getItem(k)||'{{}}');d['living-spaces']=true;"
                          "localStorage.setItem(k,JSON.stringify(d));return localStorage.getItem(k)})()")
        assert json.loads(after).get("living-spaces") is True
        self.call("Page.reload"); time.sleep(4)
        assert json.loads(self.eval(f"localStorage.getItem({json.dumps(KEY)})")).get("living-spaces") is True, "decision lost on reload"
        self.act(action="desktop-decision", key=KEY, value=after); self.phase("desktop_decision", "living-spaces enabled in isolated storage")
    def open_spaces(self):
        label = self.wait_text("I'll choose a provider later", "Skip setup")
        self.capture("onboarding"); self.click("text=" + label); time.sleep(2)
        if "No thanks" in self.text(): self.click("text=No thanks"); time.sleep(1)
        nav = 'Array.from(document.querySelectorAll("button,a,[role=button]")).some(e=>e.getClientRects().length&&e.textContent.trim()==="Spaces")'
        assert self.eval(nav), "Spaces navigation is not visible"
        self.click("text=Spaces"); self.wait_text("Build your first Space in chat"); self.capture("empty-spaces")
        self.phase("open_spaces", "empty Spaces index visible")
    def fixture(self):
        r = subprocess.run([self.a.python, str(HERE / "fixture.py"), str(self.a.repo), str(self.out), str(self.state)],
                           env={**self.env(), "PYTHONPATH": str(self.a.hermes_root)}, capture_output=True, text=True, timeout=60)
        (self.out / "fixture.log").write_text(r.stdout + r.stderr); assert r.returncode == 0, r.stderr[-2000:]
        self.phase("fixture", "Verification Notebook created by spaces_create (synthetic; not chat creation)")
    def journey(self):
        note = "Verification note " + time.strftime("%H%M%S"); card = 'a[href="#/spaces?space=verification-notebook"]'
        self.wait_text("Verification Notebook", product=True); self.click(card); time.sleep(3); self.capture("before-save")
        self.press(self.guest('input[aria-label="Note"]')["pos"]); self.call("Input.insertText", text=note); self.act(action="type", text=note)
        self.press(self.guest("button#save")["pos"]); self.act(action="guest-click", selector="button#save")
        deadline = time.monotonic() + 20
        while self.guest("#status")["text"] != "Note saved":
            expect(time.monotonic() < deadline, f"visible status: {self.guest('#status')['text']}"); time.sleep(0.5)
        self.capture("after-save"); expect(note in self.guest("#notes")["text"], "note not shown after save")
        expect(any(note in str(x["data"]) for x in self.records("after-save")["records"]), "note not persisted")
        self.phase("save", dict(note=note, visible="Note saved", persisted=True))
        self.click("header.ls-framebar > button:first-child"); self.wait_text("Verification Notebook", product=True); time.sleep(1); self.capture("after-leave")
        expect(self.eval('!!document.querySelector(\'[data-testid="spaces-index"]\')'), "did not return to the Spaces index")
        self.click(card); time.sleep(3); self.capture("after-reopen")
        expect(note in self.guest("#notes")["text"], "note not visible after reopen")
        expect(any(note in str(x["data"]) for x in self.records("after-reopen")["records"]), "note not persisted after reopen")
        self.phase("reopen", "note visible after leave and reopen; SQLite readback matches")
        self.result["outcome"] = "journey_passed"
    def shutdown(self):
        s = self.result.setdefault("shutdown", {})
        if self.proc is not None and self.proc.poll() is None:
            r = row(self.proc.pid)
            if r and r["started"] == self.started:
                self.proc.send_signal(signal.SIGTERM)    # our own unreaped child: the app runs its normal quit
                try: s["app_exit"] = self.proc.wait(timeout=45)
                except subprocess.TimeoutExpired: s["app_exit"] = "still running 45 s after TERM (left running)"
        elif self.proc is not None: s["app_exit"] = f"already exited {self.proc.returncode}"
        time.sleep(3)
        if self.gw:
            r = row(self.gw["pid"])
            now = set(listeners_of(self.gw["pid"])); s["gateway_listeners"] = dict(at_discovery=self.gw["listeners"], at_shutdown=sorted(now))
            # still holds every listener it had at discovery; the gateway may open more loopback listeners while it runs
            same = bool(r and r["started"] == self.gw["started"] and has_env(self.gw["pid"], "HERMES_HOME", self.home)
                        and set(self.gw["listeners"]) <= now)
            if same:   # the detached gateway this run identified, re-proven: one TERM, never a group signal or KILL
                os.kill(self.gw["pid"], signal.SIGTERM); deadline = time.monotonic() + 30
                while time.monotonic() < deadline and (row(self.gw["pid"]) or {}).get("started") == self.gw["started"]: time.sleep(0.5)
                s["gateway"] = "exited after one TERM" if (row(self.gw["pid"]) or {}).get("started") != self.gw["started"] else "SURVIVOR (left running)"
            else: s["gateway"] = "already gone" if not r or r["started"] != self.gw["started"] else "identity not re-proven; not signalled"
        time.sleep(2)
        lsof = run("lsof", "-nP", "+D", str(self.state))
        mine, pid = set(), os.getpid()   # this driver and the shell that started it name the state path but are not residue
        table = {r["pid"]: r for r in processes()}
        while pid in table and pid not in mine: mine.add(pid); pid = table[pid]["ppid"]
        refs = [r for r in table.values() if r["pid"] not in mine and (str(self.state) in r["command"] or has_env(r["pid"], "HERMES_HOME", self.home))]
        live_now = {g["pid"]: g["started"] for g in gateways() if not has_env(g["pid"], "HERMES_HOME", self.home)}
        res = dict(processes_referencing_state=refs, open_files_under_state=lsof.stdout[-4000:], lsof_rc=lsof.returncode,
                   cdp_listener=port_listeners(self.a.cdp_port), other_gateways_unchanged=(live_now == self.live_before) if self.prepared else None,
                   limits="snapshot: a detached process with no reference to the state directory and no open file there is not seen")
        if self.prepared:
            ident = self.identities(); self.result["identity"] = ident
            self.result["no_identity_minted"] = not ident["stores_in_state"]
        res["clean"] = (not refs and not lsof.stdout.strip() and lsof.returncode in (0, 1) and not res["cdp_listener"] and res["other_gateways_unchanged"] is True)
        self.result["residue"] = res; self.dump("result.json", self.result)

def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--repo", type=Path, default=HERE.parents[1], help="Living Spaces checkout to load (default: this checkout)")
    p.add_argument("--out", type=Path, required=True, help="new evidence directory (must not exist)")
    p.add_argument("--state", type=Path, help="new disposable state directory (default: a fresh temporary directory)")
    p.add_argument("--app", type=Path, default=Path("/Applications/Hermes.app"))
    p.add_argument("--hermes-root", type=Path, default=Path(os.environ.get("HERMES_DESKTOP_HERMES_ROOT", Path.home() / ".hermes/hermes-agent")))
    p.add_argument("--python", default=sys.executable, help="Hermes runtime Python (default: the one running this script)")
    p.add_argument("--cdp-port", type=int, default=19432)
    p.add_argument("--allow-dirty", action="store_true", help="load uncommitted product changes (recorded in prepare.json)")
    a = p.parse_args()
    a.repo, a.out = a.repo.resolve(), a.out.resolve()
    a.state = (a.state or Path(tempfile.mkdtemp(prefix="lsv-")) / "state").resolve()
    a.app_binary = str(a.app / "Contents/MacOS/Hermes")
    a.out.mkdir(parents=True, exist_ok=False)
    r = Run(a)
    try:
        r.prepare(); r.launch(); r.backend(); r.isolation_then_flag(); r.open_spaces(); r.fixture()
        in_journey = True
        r.journey()
    except ProductFailure as e:   # only a failed product expectation inside the journey judges the product
        r.result["outcome"] = "product_failure"
        r.result["error"] = f"{type(e).__name__}: {e}"; r.result["trace"] = traceback.format_exc()
        try:
            if r.proc is not None and r.proc.poll() is None: r.capture("failure")
        except Exception: pass
    except Exception as e:        # launch, isolation, onboarding, fixture, CDP, screenshots, disk: not a product verdict
        r.result["outcome"] = "harness_failure" if locals().get("in_journey") else "setup_failure"
        r.result["error"] = f"{type(e).__name__}: {e}"; r.result["trace"] = traceback.format_exc()
        try:
            if r.proc is not None and r.proc.poll() is None: r.capture("failure")
        except Exception: pass
    finally:
        r.shutdown()
    print(json.dumps({k: r.result.get(k) for k in ("outcome", "error", "shutdown", "no_identity_minted")}, default=str))
    print("evidence:", a.out, "state:", a.state)
    ok = r.result["outcome"] == "journey_passed" and r.result["residue"]["clean"] and r.result.get("no_identity_minted") is True
    r.result["passed"] = ok; r.dump("result.json", r.result)
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
