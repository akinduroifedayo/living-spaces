"""On-demand runtime inspection of one saved Space revision (the spaces_inspect tool).

The Space runs once, in a throwaway headless Chromium on this machine, through the packaged sandbox shell and the
real mountSpace, the same code Desktop uses. Nothing it does reaches production state:

- Space data is read through a read-only SQLite connection held in one read transaction, so the revision, records,
  grants and runs it sees form one consistent snapshot and no write is possible (mode=ro, query_only).
- Bridge calls are answered from that snapshot by a passive adapter. Reads are served; writes, Refresh, bot
  requests and network fetches are refused before anything executes, and every refusal is reported.
- The browser is driven over the DevTools pipe (no port), with a temporary profile, a minimal environment, every
  network request failed at the DevTools layer, a dead proxy and an unresolvable host map as backstops.

The report states what was observed. It never claims a screenshot: no pixels are captured.
"""
from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import select
import shutil
import signal
import sqlite3
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import quote

from . import bridge, db, grants as grants_mod, limits, logs, projects, records
from .errors import SpacesError

PACKAGE = Path(__file__).resolve().parent.parent
RUNNER = PACKAGE / "inspection" / "runner.js"
SHELL = PACKAGE / "guest" / "space-host.html"
BROWSER_ENV = "LIVING_SPACES_INSPECT_BROWSER"

WIDTH, HEIGHT = (320, 1024, 2560), (240, 768, 1600)       # (min, default, max) CSS pixels
TIMEOUT_S = (3, 15, 30)
TEXT_LIMIT = (0, 4000, 16000)
MAX_ENTRIES = 50
ENTRY_CHARS = 1000
MAX_NETWORK = 20
SETTLE_MS = 1500                                         # unchanged DOM and bridge for this long count as settled
QUIET_MS = 2000                                          # settle window when the guest cannot report lifecycle
CLEANUP_S = 5
MAX_CONCURRENT = 2
MAX_MESSAGE = 8 * 1024 * 1024                            # one DevTools message; larger ends the inspection as error
TEXT_SLACK = 256                                         # extra raw characters fetched so redaction can see a secret
# Chromium does not know the shell's `webrtc 'block'` CSP directive and says so once per sandboxed document. It is
# emitted for the packaged shell on every Space, so it is reported apart from the Space's own errors.
HOST_NOTICES = ("Unrecognized Content-Security-Policy directive 'webrtc'.",)
# The host page is served by DevTools itself (never the network) from an https origin, so the Space gets a secure
# context as it does in Desktop; crypto.randomUUID and other secure-context APIs then behave the same.
HOST_URL = "https://inspect.living-spaces.invalid/"
HOST_PAGE = "<!doctype html><html><head><meta charset=utf-8><title>Living Spaces inspection</title></head><body></body></html>"

_slots = threading.BoundedSemaphore(MAX_CONCURRENT)

_CANDIDATES = {
    "darwin": ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
               "/Applications/Chromium.app/Contents/MacOS/Chromium",
               "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
               "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"],
    "linux": ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome-headless-shell",
              "microsoft-edge"],
}

LIMITATIONS = [
    "no_pixels_captured: this report has no screenshot; layout and visual quality were not observed",
    "records_current_at_inspection: data comes from the current records, not records as they were at this revision",
    "readiness_is_observational: loaded means the entry scripts settled; it does not prove the Space is correct",
    "visible_text_is_inner_text: text includes rendered content outside the viewport and excludes canvas pixels",
    f"settle_window: observation stops once the page and bridge are quiet for {SETTLE_MS} ms; later work is not seen",
    "webrtc_not_fully_blocked: as in ordinary viewing, WebRTC is constrained but not provably blocked",
]


def find_renderer():
    """Return (path, None) for a local Chromium-family browser, or (None, reason)."""
    explicit = os.environ.get(BROWSER_ENV)
    if explicit is not None:
        if explicit and os.path.isfile(explicit) and os.access(explicit, os.X_OK):
            return explicit, None
        return None, f"{BROWSER_ENV} does not name an executable browser"
    if os.name != "posix":
        return None, "Runtime inspection supports macOS and Linux only"
    for candidate in _CANDIDATES.get(sys.platform if sys.platform == "darwin" else "linux", []):
        path = candidate if os.path.isabs(candidate) else shutil.which(candidate)
        if path and os.path.isfile(path) and os.access(path, os.X_OK):
            return path, None
    return None, "No Chrome, Chromium, Edge or Brave browser was found on this machine"


def _bounded(value, name, bounds):
    low, default, high = bounds
    if value is None:
        return default
    limits.integer(value, name)
    if not low <= value <= high:
        raise SpacesError("invalid", f"{name} must be between {low} and {high}")
    return value


def _redact(text):
    """logs.redact, but never failing on guest-shaped input (deeply nested JSON recurses past the limit)."""
    try:
        return logs.redact(text)
    except RecursionError:
        text = logs._SECRETS.sub("[REDACTED]", text)
        return logs._CREDENTIAL_ASSIGNMENT.sub(lambda match: match["prefix"] + '"[REDACTED]"', text)


def _clip(text, size=ENTRY_CHARS):
    text = _redact(str(text))
    return text if len(text) <= size else text[:size] + f" [truncated; {len(text)} chars]"


# --- read-only snapshot -------------------------------------------------------------------------------------

def _open_snapshot():
    path = db.db_path()
    if not path.exists():
        raise SpacesError("not_found", "Space not found")
    conn = sqlite3.connect(f"file:{quote(str(path))}?mode=ro", uri=True, timeout=5.0, isolation_level=None,
                           check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        conn.execute("SELECT count(*) FROM spaces").fetchone()      # start the read transaction now
    except BaseException:
        conn.close()
        raise
    return conn


class Snapshot:
    """One read transaction over the Space: every read during the inspection sees the same database state."""

    def __init__(self, conn, ref, rev):
        self.conn = conn
        self.sid = projects._resolve(conn, ref)
        space = db.space(conn, self.sid)
        limits.integer(rev, "rev", minimum=1)
        revision = projects._revision(conn, self.sid, rev)
        self.space = {"id": self.sid, "name": space["name"]}
        self.rev = revision["rev"]
        self.head_rev = space["head_rev"]
        self.status = space["status"]
        self.data_version = space["data_version"]
        self.manifest = revision["manifest"]
        files, digest = [], hashlib.sha256()
        for path, sha in sorted(revision["files"].items()):
            raw = conn.execute("SELECT content FROM blobs WHERE sha=?", (sha,)).fetchone()[0]
            files.append({"path": path, "mime": mimetypes.guess_type(path)[0] or "application/octet-stream",
                          **projects._content(raw)})
            digest.update(f"{path}\0{sha}\n".encode())
        self.files = files
        self.files_digest = digest.hexdigest()
        rows = conn.execute("SELECT * FROM grants WHERE space=? ORDER BY capability", (self.sid,))
        self.grants = [grants_mod._grant(row) for row in rows]
        self.granted = {g["capability"] for g in self.grants if g["status"] == "granted"}
        self.seq = records._seq(conn, self.sid)

    def bundle(self, shell):
        return {"space": self.space, "rev": self.rev, "manifest": self.manifest, "files": self.files,
                "sandbox": {"format": 1, "shell_srcdoc": shell}}

    def provenance(self):
        return {"head_rev": self.head_rev, "is_head": self.rev == self.head_rev, "status": self.status,
                "data_version": self.data_version, "files_digest": self.files_digest, "records_seq": self.seq,
                "read_only": True}


class PassiveAdapter:
    """Answers the Space bridge from a Snapshot. Nothing here can write: the connection is read-only."""

    REFUSED = {
        "data.put": "Inspection is read-only: records are not changed",
        "data.delete": "Inspection is read-only: records are not changed",
        "data.batch": "Inspection is read-only: records are not changed",
        "refresh": "Inspection does not run Refresh or upkeep",
        "bot.request": "Inspection does not contact the bot",
        "net.fetch": "Inspection makes no network requests",
    }

    def __init__(self, snapshot):
        self.snap = snapshot
        self.refused = {}
        self.denied = {}
        self.served = {}
        self.lifecycle = None
        self.guest_logs = {"entries": 0, "dropped": 0, "unconfirmed": 0}

    def call(self, op, args):
        try:
            return {"ok": True, "result": self._call(op, args)}
        except SpacesError as exc:
            return {"ok": False, "error": exc.to_dict()}
        except Exception:
            return {"ok": False, "error": {"code": "invalid", "message": "Operation could not be completed"}}

    def _call(self, op, args):
        if not isinstance(op, str) or op not in bridge._OPS:
            raise SpacesError("not_granted", "Operation is unavailable", capability=op if isinstance(op, str) else "unknown")
        capability, required, optional = bridge._OPS[op]
        if capability and capability not in self.snap.granted:
            self.denied[op] = self.denied.get(op, 0) + 1
            raise SpacesError("not_granted", "Capability or requested scope is not granted", capability=capability)
        limits.object_json(args)
        limits.check(len(limits.dumps({"v": 1, "id": 0, "op": op, "args": args}).encode("utf-8")),
                     limits.BRIDGE_BYTES, "bridge payload")
        args = {key: value for key, value in args.items() if key != "space"}
        if required - args.keys() or args.keys() - required - optional:
            raise SpacesError("invalid", "Missing or unknown operation arguments")
        if op in self.REFUSED:
            self.refused[op] = self.refused.get(op, 0) + 1
            raise SpacesError("blocked", self.REFUSED[op], inspection=True)
        self.served[op] = self.served.get(op, 0) + 1
        conn, sid = self.snap.conn, self.snap.sid
        if op == "meta":
            return {"space": {"id": sid, "name": self.snap.space["name"], "rev": self.snap.head_rev},
                    "grants": sorted(self.snap.granted), "limits": limits.LIMITS.copy()}
        if op == "log":
            if args.get("lifecycle") in ("loaded", "failed"):
                self.lifecycle = args["lifecycle"]
            entries = args.get("entries")
            self.guest_logs["entries"] += len(entries) if isinstance(entries, list) else 0
            for key in ("dropped", "unconfirmed"):
                if isinstance(args.get(key), int):
                    self.guest_logs[key] = max(self.guest_logs[key], args[key])
            return {"stored": len(entries) if isinstance(entries, list) else 0}
        if op == "runs.list":
            limit = args.get("limit", 50)
            if not isinstance(limit, int) or not 1 <= limit <= 500:
                raise SpacesError("invalid", "Run limit must be between 1 and 500")
            rows = conn.execute("SELECT * FROM runs WHERE space=? ORDER BY queued_at DESC, rowid DESC LIMIT ?",
                                (sid, limit)).fetchall()
            return [{**dict(row), "changed": json.loads(row["changed"]), "detail": json.loads(row["detail"])}
                    for row in rows]
        if op == "data.query":
            collection = args["collection"]
            options = {key: args[key] for key in ("where", "order", "limit", "offset") if key in args}
            options.setdefault("limit", 500)
            options.setdefault("offset", 0)
            records._query_args(collection, options.get("where"), options.get("order"), options["limit"], options["offset"])
            rows = [records._record(row) for row in conn.execute(
                "SELECT * FROM records WHERE space=? AND collection=? ORDER BY id", (sid, collection))]
            page, total = records._select(rows, **options)
            return {"records": page, "total": total, "seq": self.snap.seq}
        records._ids(args["collection"], args["id"])                       # data.get
        row = records._row(conn, sid, args["collection"], args["id"])
        if row is None:
            raise SpacesError("not_found", "Record not found")
        return records._record(row)


# --- DevTools pipe ---------------------------------------------------------------------------------------------

class _Timeout(Exception):
    pass


class _Closed(Exception):
    pass


class _LaunchFailed(Exception):
    pass


class _Crashed(Exception):
    pass


class Browser:
    """A throwaway Chromium driven over --remote-debugging-pipe. One instance per inspection."""

    def __init__(self, path, width, height, deadline):
        self.deadline = deadline
        self.pid = None
        self.tmp = None
        self.buf = b""
        self.next_id = 0
        self.responses = {}
        self.listeners = []
        self.max_message = 0
        self.read_fd = self.write_fd = -1
        held = []
        try:
            self.tmp = tempfile.mkdtemp(prefix="ls-inspect-")
            to_child, write_fd = os.pipe()
            held += [to_child, write_fd]
            read_fd, from_child = os.pipe()
            held += [read_fd, from_child]
            held.append(os.open(os.path.join(self.tmp, "stderr.log"), os.O_WRONLY | os.O_CREAT, 0o600))
            held.append(os.open(os.devnull, os.O_RDWR))
            stderr, devnull = held[4], held[5]
            profile = os.path.join(self.tmp, "profile")
            argv = [path, "--headless=new", "--remote-debugging-pipe", f"--user-data-dir={profile}",
                    "--no-first-run", "--no-default-browser-check", "--disable-extensions",
                    "--disable-component-extensions-with-background-pages", "--disable-background-networking",
                    "--disable-component-update", "--disable-sync", "--disable-default-apps",
                    "--disable-domain-reliability", "--disable-client-side-phishing-detection", "--no-pings",
                    "--mute-audio", "--use-mock-keychain", "--password-store=basic", "--deny-permission-prompts",
                    "--host-resolver-rules=MAP * ~NOTFOUND", "--proxy-server=127.0.0.1:9",
                    "--proxy-bypass-list=<-loopback>", "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
                    "--disable-features=MediaRouter,OptimizationHints,Translate,AutofillServerCommunication",
                    f"--window-size={width},{height}", "--hide-scrollbars", "about:blank"]
            env = {"PATH": "/usr/bin:/bin", "HOME": self.tmp, "TMPDIR": self.tmp}
            # Park every source fd above the target range first, so no dup2 overwrites a source still needed.
            park = [(fd, 100 + index) for index, fd in enumerate((devnull, stderr, to_child, from_child))]
            actions = [(os.POSIX_SPAWN_DUP2, fd, high) for fd, high in park]
            actions += [(os.POSIX_SPAWN_DUP2, 100, 0), (os.POSIX_SPAWN_DUP2, 100, 1), (os.POSIX_SPAWN_DUP2, 101, 2),
                        (os.POSIX_SPAWN_DUP2, 102, 3), (os.POSIX_SPAWN_DUP2, 103, 4)]
            actions += [(os.POSIX_SPAWN_CLOSE, high) for _, high in park]
            self.pid = os.posix_spawn(path, argv, env, setsid=True, file_actions=actions)
        except OSError as exc:
            # Nothing is running: release whatever was acquired, including the profile directory.
            for fd in held:
                try:
                    os.close(fd)
                except OSError:
                    pass
            if self.tmp:
                shutil.rmtree(self.tmp, ignore_errors=True)
            raise _LaunchFailed(exc.strerror or type(exc).__name__) from exc
        for fd in (to_child, from_child, stderr, devnull):
            os.close(fd)
        self._use_pipes(read_fd, write_fd)

    def _use_pipes(self, read_fd, write_fd):
        self.read_fd, self.write_fd = read_fd, write_fd
        os.set_blocking(write_fd, False)     # writes must never outlive the deadline

    def _read(self):
        try:
            chunk = os.read(self.read_fd, 1 << 20)
        except BlockingIOError:
            return
        except OSError as exc:
            raise _Closed("Browser exited") from exc
        if not chunk:
            raise _Closed("Browser exited")
        self.buf += chunk
        if len(self.buf) - (self.buf.rfind(b"\0") + 1) > MAX_MESSAGE:
            raise _Closed("A DevTools message exceeded the inspection size cap")

    def _dispatch(self):
        while b"\0" in self.buf:
            raw, self.buf = self.buf.split(b"\0", 1)
            if len(raw) > MAX_MESSAGE:
                raise _Closed("A DevTools message exceeded the inspection size cap")
            self.max_message = max(self.max_message, len(raw))
            message = json.loads(raw)
            if "id" in message:
                self.responses[message["id"]] = message
            else:
                for listener in self.listeners:
                    listener(message)

    def send(self, method, params=None, session=None):
        """Write one message without blocking past the deadline. Incoming data is buffered, not dispatched, so
        listeners never run (and never send) in the middle of a partly written message."""
        self.next_id += 1
        message = {"id": self.next_id, "method": method, "params": params or {}}
        if session:
            message["sessionId"] = session
        data = memoryview(json.dumps(message).encode() + b"\0")
        while data:
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise _Timeout()
            try:
                readable, writable, _ = select.select([self.read_fd], [self.write_fd], [], remaining)
            except (OSError, ValueError) as exc:
                raise _Closed("Browser exited") from exc
            if readable:
                self._read()
            if writable:
                try:
                    data = data[os.write(self.write_fd, data):]
                except BlockingIOError:
                    pass
                except OSError as exc:
                    raise _Closed("Browser exited") from exc
        return self.next_id

    def pump(self, until):
        """Dispatch buffered messages, or wait for more until `until` (monotonic) or the deadline."""
        if b"\0" not in self.buf:
            wait = max(0.0, min(until, self.deadline) - time.monotonic())
            try:
                ready, _, _ = select.select([self.read_fd], [], [], wait)
            except (OSError, ValueError) as exc:
                raise _Closed("Browser exited") from exc
            if not ready:
                if time.monotonic() >= self.deadline:
                    raise _Timeout()
                return
            self._read()
        self._dispatch()

    def call(self, method, params=None, session=None, timeout=None):
        id_ = self.send(method, params, session)
        until = time.monotonic() + timeout if timeout else self.deadline
        while id_ not in self.responses:
            if time.monotonic() >= until:
                raise _Timeout()
            self.pump(until)
        message = self.responses.pop(id_)
        if "error" in message:
            raise RuntimeError(message["error"].get("message", "DevTools error"))
        return message.get("result", {})

    def close(self):
        """Terminate the process group, reap it, delete the profile. Idempotent; returns a cleanup receipt."""
        receipt = {"process_exited": self.pid is None, "temp_removed": False}
        for fd in ("write_fd", "read_fd"):
            try:
                os.close(getattr(self, fd))
            except (OSError, AttributeError):
                pass
            setattr(self, fd, -1)
        if self.pid:
            end = time.monotonic() + CLEANUP_S
            for sig in (signal.SIGTERM, signal.SIGKILL):
                try:
                    os.killpg(self.pid, sig)
                except (ProcessLookupError, PermissionError):     # already gone, or only a zombie leader left
                    pass
                stop = min(end, time.monotonic() + (1.5 if sig == signal.SIGTERM else CLEANUP_S))
                while time.monotonic() < stop:
                    try:
                        done, _ = os.waitpid(self.pid, os.WNOHANG)
                    except ChildProcessError:
                        done = self.pid
                    if done:
                        receipt["process_exited"] = True
                        break
                    time.sleep(0.05)
                if receipt["process_exited"]:
                    break
            try:
                os.killpg(self.pid, signal.SIGKILL)       # stragglers left in the group after the parent exits
            except (ProcessLookupError, PermissionError):
                pass
            self.pid = None if receipt["process_exited"] else self.pid
        if not self.tmp:
            receipt["temp_removed"] = True
            return receipt
        for _ in range(10):
            shutil.rmtree(self.tmp, ignore_errors=True)
            if not os.path.exists(self.tmp):
                receipt["temp_removed"] = True
                break
            time.sleep(0.1)
        return receipt


# --- the inspection ----------------------------------------------------------------------------------------------

class _Run:
    def __init__(self, browser, adapter, text_limit, withhold_console):
        self.b = browser
        self.adapter = adapter
        self.text_limit = text_limit
        self.withhold = withhold_console
        self.page = None
        self.page_target = None
        self.sessions = {}        # sessionId -> targetId
        self.frames = {}          # frameId -> parent frameId
        self.entries = []
        self.seen = {}
        self.host_served = False
        self.host_notices = {}
        self.exceptions = 0
        self.counts = {"error": 0, "warning": 0, "info": 0}
        self.dropped = 0
        self.network = []
        self.network_blocked = 0
        self.booted = False
        self.reloaded = False
        self.events = []
        self.crashed = False
        browser.listeners.append(self.on_event)

    def record(self, source, level, text, url=None):
        level = {"warn": "warning", "assert": "error", "log": "info", "debug": "info", "verbose": "info",
                 "trace": "info", "dir": "info", "table": "info"}.get(level, level)
        level = level if level in self.counts else "info"
        if text in HOST_NOTICES:
            self.host_notices[text] = self.host_notices.get(text, 0) + 1
            return
        self.counts[level] += 1
        if level == "info":
            return
        if source == "exception":
            self.exceptions += 1
        text = "[withheld: Diagnostics is not granted for this Space]" if self.withhold else _clip(text)
        url = None if self.withhold or not url else "blob" if url.startswith("blob:") else _clip(url, 200)
        key = (source.split(":")[0] if source != "exception" else source, level, text)
        # One message can reach several DevTools domains and frames; report it once with a repeat count.
        if key in self.seen:
            self.seen[key]["repeats"] = self.seen[key].get("repeats", 1) + 1
            return
        if len(self.entries) >= MAX_ENTRIES:
            self.dropped += 1
            return
        entry = {"source": source, "level": level, "text": text, **({"url": url} if url else {})}
        self.seen[key] = entry
        self.entries.append(entry)

    def attach(self, session, target_id):
        self.sessions[session] = target_id
        for method, params in (("Runtime.enable", None), ("Page.enable", None), ("Log.enable", None),
                               ("Fetch.enable", {"patterns": [{"urlPattern": "*"}]}),
                               ("Target.setAutoAttach", {"autoAttach": True, "waitForDebuggerOnStart": True,
                                                         "flatten": True})):
            self.b.send(method, params, session)
        self.b.send("Runtime.runIfWaitingForDebugger", None, session)

    def on_event(self, message):
        method, params, session = message.get("method"), message.get("params", {}), message.get("sessionId")
        if method == "Target.attachedToTarget":
            info = params["targetInfo"]
            if info.get("type") in ("iframe", "worker", "page") and session is not None:
                if info.get("type") == "iframe" and info.get("parentFrameId"):
                    self.frames[info["targetId"]] = info["parentFrameId"]
                self.attach(params["sessionId"], info["targetId"])
            elif session is not None:
                self.b.send("Runtime.runIfWaitingForDebugger", None, params["sessionId"])
        elif method in ("Inspector.targetCrashed", "Target.targetCrashed"):
            self.crashed = True
        elif method == "Page.frameAttached":
            self.frames.setdefault(params["frameId"], params.get("parentFrameId"))
        elif method == "Fetch.requestPaused":
            url = params.get("request", {}).get("url", "")
            if url == HOST_URL and session == self.page and params.get("frameId") == self.page_target \
                    and not self.host_served:
                self.host_served = True
                self.b.send("Fetch.fulfillRequest", {
                    "requestId": params["requestId"], "responseCode": 200,
                    "responseHeaders": [{"name": "Content-Type", "value": "text/html; charset=utf-8"},
                                        {"name": "Cache-Control", "value": "no-store"}],
                    "body": base64.b64encode(HOST_PAGE.encode()).decode()}, session)
            elif url == HOST_URL + "favicon.ico" and session == self.page:
                # The browser asks the host origin for an icon on its own; answer locally, it is not Space traffic.
                self.b.send("Fetch.fulfillRequest", {"requestId": params["requestId"], "responseCode": 204,
                                                     "responseHeaders": []}, session)
            elif url.startswith(("blob:", "data:")):
                self.b.send("Fetch.continueRequest", {"requestId": params["requestId"]}, session)
            else:
                self.network_blocked += 1
                if len(self.network) < MAX_NETWORK:
                    self.network.append(_clip(url, 200))
                self.b.send("Fetch.failRequest", {"requestId": params["requestId"], "errorReason": "BlockedByClient"},
                            session)
        elif method == "Runtime.consoleAPICalled" and session != self.page:
            parts = [arg.get("value", arg.get("description", arg.get("type"))) for arg in params.get("args", [])]
            self.record("console", params.get("type", "log"), " ".join(str(part) for part in parts))
        elif method == "Runtime.exceptionThrown":
            details = params.get("exceptionDetails", {})
            text = details.get("exception", {}).get("description") or details.get("text", "Uncaught exception")
            self.record("exception", "error", text, details.get("url"))
        elif method == "Log.entryAdded":
            entry = params.get("entry", {})
            self.record(f"browser:{entry.get('source', 'other')}", entry.get("level", "info"), entry.get("text", ""),
                        entry.get("url"))

    def depth(self, frame):
        depth, seen = 0, set()
        while frame in self.frames and self.frames[frame] and frame not in seen:
            seen.add(frame)
            frame = self.frames[frame]
            depth += 1
        return depth if frame == self.page_target else -1

    def guest_frame(self):
        """The Space document is two frames below the host page: host -> sandbox shell -> guest."""
        guests = [frame for frame in self.frames if self.depth(frame) == 2]
        return guests[-1] if guests else None

    def owner(self, frame):
        by_target = {target: session for session, target in self.sessions.items()}
        while frame is not None:
            if frame in by_target:
                return by_target[frame]
            frame = self.frames.get(frame)
        return None

    def sample(self):
        """Read the guest document from an isolated world, out of reach of the Space's own scripts."""
        frame = self.guest_frame()
        session = self.owner(frame) if frame else None
        if not session:
            return None
        try:
            world = self.b.call("Page.createIsolatedWorld", {"frameId": frame, "worldName": "ls-inspect"}, session,
                                timeout=2)
            keep = self.text_limit + TEXT_SLACK
            result = self.b.call("Runtime.evaluate", {
                "contextId": world["executionContextId"], "returnByValue": True, "timeout": 1500,
                "expression": """(() => { const b = document.body; const t = b ? b.innerText : '';
                  return { text: t.slice(0, %d), chars: t.length, title: String(document.title).slice(0, 1000),""" % keep + """ nodes: document.getElementsByTagName('*').length,
                           images: document.images.length, canvases: document.getElementsByTagName('canvas').length,
                           svgs: document.getElementsByTagName('svg').length,
                           failure: !!document.querySelector('section[role=alert] h1') &&
                                    document.querySelector('section[role=alert] h1').textContent === 'This Space could not load' } })()"""},
                session, timeout=2)
            value = result.get("result", {}).get("value")
            return value if isinstance(value, dict) and "chars" in value else None
        except (_Timeout, RuntimeError):
            return None

    def serve(self, drained):
        replies = []
        for request in drained.get("requests", []):
            replies.append((request["id"], self.adapter.call(request.get("op"), request.get("args") or {})))
        for event in drained.get("events", []):
            kind = event.get("kind")
            if kind == "booted":
                self.booted = True
            elif kind == "reloaded":
                self.reloaded = True
            elif kind == "denied" and isinstance(event.get("op"), str):
                # The sandbox host refuses ungranted operations itself, before they reach the adapter.
                op = event["op"] if event["op"] in bridge._OPS else "unknown"
                self.adapter.denied[op] = self.adapter.denied.get(op, 0) + 1
            if kind in ("error", "log-overflow", "reloaded"):
                self.events.append({"kind": kind, **({"message": _clip(event["message"], 300)} if event.get("message") else {})})
        if replies:
            body = ",".join(f"[{id_},{json.dumps(reply)}]" for id_, reply in replies)
            self.b.call("Runtime.evaluate", {"expression": f"[{body}].forEach(([i, r]) => __lsInspect.reply(i, r))",
                                             "returnByValue": True}, self.page, timeout=5)
        return bool(replies)


def inspect(ref, rev, *, width=None, height=None, timeout_s=None, text_limit=None):
    limits.text(ref, "space")
    width = _bounded(width, "width", WIDTH)
    height = _bounded(height, "height", HEIGHT)
    timeout_s = _bounded(timeout_s, "timeout_s", TIMEOUT_S)
    text_limit = _bounded(text_limit, "text_limit", TEXT_LIMIT)
    if not _slots.acquire(blocking=False):
        raise SpacesError("blocked", f"At most {MAX_CONCURRENT} inspections run at once; try again shortly")
    try:
        return _inspect(ref, rev, width, height, timeout_s, text_limit)
    finally:
        _slots.release()


def _inspect(ref, rev, width, height, timeout_s, text_limit):
    started = time.time()
    clock = time.monotonic()
    conn = _open_snapshot()
    try:
        snap = Snapshot(conn, ref, rev)
        report = {
            "space": snap.sid, "rev": snap.rev,
            "inspection": {"id": "insp_" + uuid.uuid4().hex[:12], "mode": "disposable-headless-passive",
                           "started_at": started, "snapshot": snap.provenance()},
            "outcome": None, "readiness": {"shell_booted": False, "guest_lifecycle": None, "failure_panel": False,
                                           "settled": False, "lifecycle_source": "guest_reported"},
            "errors": [], "counts": {}, "blocked": {}, "denied": {}, "network": {"blocked": 0, "attempts": []},
            "text": None, "dom": None, "viewport": {"requested": [width, height]},
            "screenshot": None, "limitations": list(LIMITATIONS), "cleanup": None,
        }
        if not snap.files or snap.manifest.get("entry") not in {f["path"] for f in snap.files}:
            report["outcome"] = "failed"
            report["readiness"]["reason"] = "entry_missing"
            report["limitations"].append("not_rendered: this revision has no entry file, so nothing was run")
            return report
        path, reason = find_renderer()
        if not path:
            report["outcome"] = "unavailable"
            report["unavailable"] = {"code": "renderer_unavailable", "message": reason}
            report["limitations"].append("not_rendered: no runtime observation was made")
            return report
        shell = SHELL.read_text(encoding="utf-8")
        runner = RUNNER.read_text(encoding="utf-8")
        report["inspection"]["harness_sha256"] = hashlib.sha256((runner + "\0" + shell).encode()).hexdigest()
        adapter = PassiveAdapter(snap)
        withhold = "logs" not in snap.granted
        if withhold:
            report["limitations"].append("diagnostics_not_granted: console text is withheld and the guest cannot report lifecycle")
        deadline = clock + timeout_s
        try:
            browser = Browser(path, width, height, deadline)
        except _LaunchFailed as exc:
            report["outcome"] = "error"
            report["error"] = {"code": "renderer_launch_failed", "message": _clip(f"The browser could not start: {exc}", 300)}
            report["limitations"].append("not_rendered: no runtime observation was made")
            report["cleanup"] = {"process_exited": True, "temp_removed": True}
            report["inspection"]["duration_ms"] = round((time.monotonic() - clock) * 1000)
            return report
        try:
            run = _Run(browser, adapter, text_limit, withhold)
            _drive(run, snap, shell, runner, width, height, deadline, report)
        except _Timeout:
            report["outcome"] = "timed_out"
        except _Crashed as exc:
            report["outcome"] = "error"
            report["error"] = {"code": "renderer_crashed", "message": str(exc)}
        except (_Closed, RuntimeError, ValueError) as exc:
            report["outcome"] = "error"
            report["error"] = {"code": "renderer_exited" if isinstance(exc, _Closed) else "renderer_protocol",
                               "message": _clip(exc, 300)}
        except (KeyboardInterrupt, SystemExit):
            report["outcome"] = "canceled"
            raise
        finally:
            try:
                run_state = locals().get("run")
                if run_state is not None:
                    _finish(run_state, adapter, report)
            except Exception:
                # Never let report formatting skip cleanup, and never report success from a broken report.
                report["outcome"] = "error"
                report["error"] = {"code": "inspection_failed", "message": "The inspection report could not be assembled"}
                report["text"] = report["dom"] = None
            finally:
                report["cleanup"] = browser.close()
            if not (report["cleanup"]["process_exited"] and report["cleanup"]["temp_removed"]):
                report["limitations"].append("cleanup_incomplete: the inspection browser or its files may remain")
            report["inspection"]["duration_ms"] = round((time.monotonic() - clock) * 1000)
            try:
                end = _open_snapshot()
                try:
                    row = end.execute("SELECT head_rev FROM spaces WHERE id=?", (snap.sid,)).fetchone()
                    report["inspection"]["head_rev_at_end"] = row["head_rev"] if row else "deleted"
                finally:
                    end.close()
            except (sqlite3.Error, SpacesError):
                report["inspection"]["head_rev_at_end"] = None
        return report
    finally:
        conn.close()


def _drive(run, snap, shell, runner, width, height, deadline, report):
    b = run.b
    version = b.call("Browser.getVersion")
    report["inspection"]["renderer"] = {"product": version.get("product"), "protocol": version.get("protocolVersion")}
    b.call("Browser.setDownloadBehavior", {"behavior": "deny"})
    target = b.call("Target.createTarget", {"url": "about:blank"})["targetId"]
    run.page_target = target
    session = b.call("Target.attachToTarget", {"targetId": target, "flatten": True})["sessionId"]
    run.page = session
    run.attach(session, target)
    b.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": height, "deviceScaleFactor": 1,
                                                  "mobile": False}, session)
    b.call("Fetch.enable", {"patterns": [{"urlPattern": "*"}]}, session)
    b.call("Page.enable", None, session)
    navigation = b.call("Page.navigate", {"url": HOST_URL}, session)
    if navigation.get("errorText") or not run.host_served:
        raise _Closed("The inspection host page could not be prepared")
    while b.call("Runtime.evaluate", {"expression": "document.readyState", "returnByValue": True},
                 session)["result"].get("value") != "complete":
        b.pump(time.monotonic() + 0.05)
    b.call("Runtime.evaluate", {"expression": runner, "returnByValue": True}, session)
    mounted = b.call("Runtime.evaluate", {
        "expression": f"__lsInspect.mount({json.dumps(snap.bundle(shell))}, {json.dumps(snap.grants)})",
        "returnByValue": True}, session)
    if mounted.get("exceptionDetails"):
        raise _Closed("The sandbox host could not mount this Space")
    stable_since, last, last_traffic = None, None, time.monotonic()
    while True:
        drained = b.call("Runtime.evaluate", {"expression": "__lsInspect.next(200)", "awaitPromise": True,
                                              "returnByValue": True}, session, timeout=5)
        drained = drained.get("result", {}).get("value") or {}
        if drained.get("viewport"):
            report["viewport"]["actual"] = drained["viewport"]
        if run.serve(drained):
            last_traffic = time.monotonic()
        sample = run.sample() if run.booted else None
        now = time.monotonic()
        if run.crashed:
            raise _Crashed("The Space's renderer crashed")
        if sample is not None:
            report["text"] = sample
            key = (sample["chars"], sample["nodes"], sample["failure"])
            if key != last:
                last, stable_since = key, now
        elif run.booted:
            last, stable_since = None, None          # only a current, successful observation can count as settled
        lifecycle = run.adapter.lifecycle or ("failed" if sample and sample["failure"] else None)
        quiet = stable_since is not None and now - stable_since >= SETTLE_MS / 1000 and now - last_traffic >= SETTLE_MS / 1000
        if lifecycle and quiet:
            report["readiness"]["settled"] = True
            report["outcome"] = ("failed" if lifecycle == "failed" else
                                 "loaded_with_errors" if run.counts["error"] else "loaded")
            return
        if not lifecycle and run.withhold and stable_since is not None and now - stable_since >= QUIET_MS / 1000 \
                and now - last_traffic >= QUIET_MS / 1000:
            report["readiness"]["settled"] = True
            report["outcome"] = "rendered_unconfirmed"
            return
        if run.reloaded:
            report["outcome"] = "failed"
            report["readiness"]["reason"] = "space_navigated"
            return
        if now >= deadline:
            raise _Timeout()


def _finish(run, adapter, report):
    readiness = report["readiness"]
    readiness["shell_booted"] = run.booted
    readiness["guest_lifecycle"] = adapter.lifecycle
    sample = report.get("text")
    if isinstance(sample, dict) and "nodes" in sample:
        readiness["failure_panel"] = sample["failure"]
        text, chars = sample["text"], sample["chars"]
        report["dom"] = {key: sample[key] for key in ("nodes", "images", "canvases", "svgs")}
        clean = _redact(text)                    # redact before clipping, so a clipped secret is still caught
        report["text"] = {"content": clean[:run.text_limit], "chars": chars,
                          "truncated": chars > run.text_limit or len(clean) > run.text_limit,
                          "title": _clip(sample["title"], 200)}
        if not text.strip() and not (sample["images"] or sample["canvases"] or sample["svgs"]):
            report["limitations"].append("blank_suspected: the Space rendered no text, images, canvas or SVG")
    else:
        report["text"] = None
    if report["outcome"] in (None, "timed_out") and readiness["shell_booted"] and not adapter.lifecycle:
        readiness["reason"] = "lifecycle_not_reported_before_deadline"
    report["errors"] = run.entries
    report["counts"] = {**run.counts, "dropped": run.dropped, "guest_reported": adapter.guest_logs}
    report["blocked"] = dict(adapter.refused)
    report["denied"] = dict(adapter.denied)
    report["served"] = dict(adapter.served)
    report["network"] = {"blocked": run.network_blocked, "attempts": run.network}
    if run.events:
        report["sandbox_events"] = run.events[:MAX_ENTRIES]
    if run.host_notices:
        report["host_notices"] = [{"text": text, "count": count} for text, count in run.host_notices.items()]
