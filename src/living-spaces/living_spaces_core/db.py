"""SQLite storage for Living Spaces. One database per Hermes home, schema owned here (CONTRACTS.md §2)."""
from __future__ import annotations

import os
import sqlite3
import time
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA_VERSION = 2

DDL = """
CREATE TABLE IF NOT EXISTS spaces(id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
  owner TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('building','active','archived')),
  head_rev INTEGER NOT NULL DEFAULT 0, data_version INTEGER NOT NULL DEFAULT 1,
  accent TEXT NOT NULL DEFAULT 'blue', icon TEXT NOT NULL DEFAULT 'layers',
  pinned INTEGER NOT NULL DEFAULT 0, last_opened_at REAL, created_at REAL NOT NULL,
  updated_at REAL NOT NULL, archived_at REAL);
CREATE TABLE IF NOT EXISTS maintainers(space TEXT PRIMARY KEY REFERENCES spaces(id) ON DELETE CASCADE,
  binding TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS action_intents(space TEXT NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
  activation_id TEXT NOT NULL, input_id TEXT NOT NULL UNIQUE, target TEXT NOT NULL, text TEXT NOT NULL,
  admission_id TEXT, refusal_reason TEXT, settled INTEGER NOT NULL DEFAULT 0 CHECK(settled IN (0,1)), created_at REAL NOT NULL,
  PRIMARY KEY(space, activation_id));
CREATE UNIQUE INDEX IF NOT EXISTS one_unresolved_action ON action_intents(space) WHERE settled=0;
CREATE TABLE IF NOT EXISTS action_keys(space TEXT NOT NULL, activation_id TEXT NOT NULL, request TEXT NOT NULL,
  intent_id TEXT NOT NULL, PRIMARY KEY(space,activation_id),
  FOREIGN KEY(space,intent_id) REFERENCES action_intents(space,activation_id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS icon_checks(space TEXT PRIMARY KEY REFERENCES spaces(id) ON DELETE CASCADE,
  result TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS blobs(sha TEXT PRIMARY KEY, size INTEGER NOT NULL, content BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS revisions(space TEXT NOT NULL REFERENCES spaces(id) ON DELETE CASCADE, rev INTEGER NOT NULL,
  parent_rev INTEGER, kind TEXT NOT NULL CHECK(kind IN ('create','edit','restore')),
  restored_from INTEGER, manifest TEXT NOT NULL, files TEXT NOT NULL,
  author TEXT NOT NULL, summary TEXT NOT NULL, created_at REAL NOT NULL, PRIMARY KEY(space, rev));
CREATE TABLE IF NOT EXISTS records(space TEXT NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
  collection TEXT NOT NULL, id TEXT NOT NULL, data TEXT NOT NULL DEFAULT '{}', source TEXT, source_meta TEXT,
  rev INTEGER NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL, updated_by TEXT NOT NULL,
  PRIMARY KEY(space, collection, id));
CREATE TABLE IF NOT EXISTS changes(seq INTEGER PRIMARY KEY AUTOINCREMENT, space TEXT NOT NULL, collection TEXT NOT NULL,
  record_id TEXT NOT NULL, op TEXT NOT NULL CHECK(op IN ('put','delete','source')), rev INTEGER NOT NULL,
  actor TEXT NOT NULL, at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS recovery_points(id INTEGER PRIMARY KEY AUTOINCREMENT, space TEXT NOT NULL, reason TEXT NOT NULL,
  data_version INTEGER NOT NULL, head_rev INTEGER NOT NULL, snapshot TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS grants(space TEXT NOT NULL REFERENCES spaces(id) ON DELETE CASCADE, capability TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('requested','granted','denied','revoked')),
  scope TEXT NOT NULL DEFAULT '{}', purpose TEXT NOT NULL DEFAULT '', requested_scope TEXT,
  requested_at REAL, decided_at REAL, decided_by TEXT, PRIMARY KEY(space, capability));
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT, space TEXT NOT NULL, at REAL NOT NULL,
  actor TEXT NOT NULL, action TEXT NOT NULL, capability TEXT, outcome TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, space TEXT NOT NULL, created_at REAL NOT NULL,
  closed_at REAL, head_rev INTEGER NOT NULL, lifecycle TEXT,
  log_errors INTEGER NOT NULL DEFAULT 0, log_warnings INTEGER NOT NULL DEFAULT 0,
  log_dropped INTEGER NOT NULL DEFAULT 0, log_unconfirmed INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS editor_drafts(space TEXT NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
  editor TEXT NOT NULL, schema INTEGER NOT NULL, collection TEXT NOT NULL, record_id TEXT NOT NULL,
  data_version INTEGER NOT NULL, payload TEXT NOT NULL, bytes INTEGER NOT NULL,
  updated_at REAL NOT NULL, expires_at REAL NOT NULL,
  PRIMARY KEY(space,editor,schema,collection,record_id));
CREATE TABLE IF NOT EXISTS bridge_receipts(space TEXT NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
  space_created_at REAL NOT NULL, session TEXT NOT NULL, request_id TEXT NOT NULL,
  operation TEXT NOT NULL, fingerprint TEXT NOT NULL, confirmation TEXT NOT NULL, created_at REAL NOT NULL,
  PRIMARY KEY(space, space_created_at, session, request_id));
CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, space TEXT NOT NULL,
  trigger TEXT NOT NULL CHECK(trigger IN ('manual','schedule','chat')), handler TEXT NOT NULL, actor TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('queued','running','succeeded','failed','canceled','blocked')),
  queued_at REAL NOT NULL, started_at REAL, ended_at REAL, source_as_of REAL,
  changed TEXT NOT NULL DEFAULT '{}', error TEXT, detail TEXT NOT NULL DEFAULT '{}', heartbeat_at REAL);
CREATE TABLE IF NOT EXISTS upkeep_links(space TEXT NOT NULL REFERENCES spaces(id), cron_job_id TEXT NOT NULL UNIQUE,
  kind TEXT NOT NULL CHECK(kind IN ('agent','feed')), created_at REAL NOT NULL, created_by TEXT NOT NULL,
  PRIMARY KEY(space, cron_job_id));
CREATE TABLE IF NOT EXISTS refresh_claims(space TEXT PRIMARY KEY REFERENCES spaces(id) ON DELETE CASCADE,
  space_created_at REAL NOT NULL, token TEXT NOT NULL UNIQUE, cron_job_id TEXT NOT NULL,
  created_one_shot INTEGER NOT NULL CHECK(created_one_shot IN (0,1)), baseline_completion TEXT,
  phase TEXT NOT NULL CHECK(phase IN ('pending','background','unresolved')), native TEXT,
  created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS maintenance_spaces(space TEXT PRIMARY KEY REFERENCES spaces(id) ON DELETE CASCADE,
  incarnation TEXT NOT NULL UNIQUE, link_generation INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS maintenance_operations(token TEXT PRIMARY KEY, space TEXT NOT NULL,
  incarnation TEXT NOT NULL, command TEXT NOT NULL, owner TEXT NOT NULL, cron_job_id TEXT,
  link_generation INTEGER NOT NULL, phase TEXT NOT NULL, outcome TEXT, native TEXT, error TEXT,
  created_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS maintenance_active ON maintenance_operations(space,incarnation,phase);
CREATE TABLE IF NOT EXISTS maintenance_effects(id TEXT PRIMARY KEY,
  operation TEXT NOT NULL REFERENCES maintenance_operations(token), action TEXT NOT NULL,
  cron_job_id TEXT, phase TEXT NOT NULL, native TEXT, verification TEXT,
  obligation TEXT, resolved INTEGER NOT NULL DEFAULT 0 CHECK(resolved IN (0,1)));
CREATE TABLE IF NOT EXISTS maintenance_feeds(run TEXT PRIMARY KEY REFERENCES runs(id) ON DELETE CASCADE,
  incarnation TEXT NOT NULL, operation TEXT REFERENCES maintenance_operations(token));
CREATE TABLE IF NOT EXISTS logs(id INTEGER PRIMARY KEY AUTOINCREMENT, space TEXT NOT NULL, session TEXT, rev INTEGER,
  at REAL NOT NULL, level TEXT NOT NULL, msg TEXT NOT NULL, attribution TEXT NOT NULL DEFAULT 'ingestion_head');
CREATE INDEX IF NOT EXISTS changes_space_seq ON changes(space, seq);
CREATE INDEX IF NOT EXISTS changes_record_rev ON changes(space, collection, record_id, rev);
CREATE INDEX IF NOT EXISTS records_space_coll ON records(space, collection, updated_at);
CREATE INDEX IF NOT EXISTS runs_space_q ON runs(space, queued_at);
CREATE INDEX IF NOT EXISTS logs_space_id ON logs(space, id);
CREATE INDEX IF NOT EXISTS audit_space_id ON audit(space, id);
"""


def hermes_home() -> Path:
    try:
        from hermes_constants import get_hermes_home  # present inside Hermes processes
        return Path(get_hermes_home())
    except Exception:
        return Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")


def db_path() -> Path:
    override = os.environ.get("LIVING_SPACES_DB")
    if override:
        return Path(override)
    return hermes_home() / "plugin-data" / "living-spaces" / "spaces.db"


_initialized: set[str] = set()
_schema_lock = threading.Lock()
_deadline: ContextVar[float | None] = ContextVar("bridge_db_deadline", default=None)
_invocation: ContextVar[Invocation | None] = ContextVar("bridge_invocation", default=None)
_disposable: ContextVar[str | None] = ContextVar("disposable_database", default=None)


@contextmanager
def disposable_database(uri):
    """Route this context's store calls to an already initialized in-memory copy."""
    if not uri.startswith("file:ls-overlay-") or not uri.endswith("?mode=memory&cache=shared"):
        raise ValueError("A disposable database must be an inspection memory database")
    marker = _disposable.set(uri)
    try:
        yield
    finally:
        _disposable.reset(marker)


@dataclass
class EffectProof:
    owner: tuple
    state: str = "not_started"

    @property
    def possible(self):
        return self.state not in ("not_started", "rolled_back")


@dataclass
class Invocation:
    sid: str
    session: str | None
    op: str
    request_id: str | None = None
    capability: str | None = None
    space_created_at: float | None = None
    effect: EffectProof = field(init=False)

    def __post_init__(self):
        self.effect = EffectProof((self.sid, self.session, self.op))


class ContentionError(sqlite3.OperationalError):
    pass


def is_busy(error):
    code = getattr(error, "sqlite_errorcode", 0)
    return isinstance(error, ContentionError) or (code & 255) in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)


@contextmanager
def contention_limit(seconds):
    deadline = time.monotonic() + seconds
    previous = _deadline.get()
    marker = _deadline.set(min(previous, deadline) if previous is not None else deadline)
    try:
        yield
    finally:
        _deadline.reset(marker)


@contextmanager
def invocation(sid, session, op, request_id=None):
    current = Invocation(sid, session, op, request_id)
    marker = _invocation.set(current)
    try:
        with contention_limit(.25):
            yield current
    finally:
        _invocation.reset(marker)


def current_invocation():
    return _invocation.get()


def _busy_timeout():
    deadline = _deadline.get()
    return 5.0 if deadline is None else max(0.0, min(5.0, deadline - time.monotonic()))


def connect() -> sqlite3.Connection:
    transient = _disposable.get()
    if transient is not None:
        conn = sqlite3.connect(transient, uri=True, timeout=_busy_timeout(), isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn
    path = db_path()
    existed = path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=_busy_timeout(), check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        key = str(path)
        acquired = _schema_lock.acquire() if _deadline.get() is None else _schema_lock.acquire(timeout=_busy_timeout())
        if not acquired:
            raise ContentionError("Schema initialization is busy")
        try:
            conn.execute(f"PRAGMA busy_timeout={int(_busy_timeout() * 1000)}")
            if key not in _initialized or not existed:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.executescript(DDL)
                conn.execute("BEGIN IMMEDIATE")
                from .migrations import (grant_internet_access, link_native_upkeep,
                                         add_action_refusal_reason, add_runtime_diagnostics)
                grant_internet_access(conn)
                link_native_upkeep(conn)
                add_action_refusal_reason(conn)
                add_runtime_diagnostics(conn)
                from . import maintenance
                maintenance.initialize(conn)
                from . import storage
                storage.initialize(conn)
                conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                conn.execute("COMMIT")
                _initialized.add(key)
        finally:
            _schema_lock.release()
        conn.execute(f"PRAGMA busy_timeout={int(_busy_timeout() * 1000)}")
        return conn
    except BaseException:
        conn.close()
        raise


@contextmanager
def read():
    conn = connect()
    try:
        conn.execute("BEGIN")
        yield conn
    finally:
        conn.close()


@contextmanager
def write(proof=None):
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            from . import maintenance
            maintenance.fence_feed_write(conn)
            yield conn
        except BaseException:
            conn.execute("ROLLBACK")
            if proof is not None and proof.state == "active":
                proof.state = "rolled_back"
            raise
        if proof is not None and proof.state == "active":
            proof.state = "commit_attempted"
        conn.execute("COMMIT")
        if proof is not None and proof.state == "commit_attempted":
            proof.state = "committed"
    finally:
        conn.close()


def now() -> float:
    return time.time()


def space(conn, sid, *, writable=False):
    from .errors import SpacesError
    from .limits import identifier

    identifier(sid, "space")
    row = conn.execute("SELECT * FROM spaces WHERE id=?", (sid,)).fetchone()
    if row is None:
        raise SpacesError("not_found", "Space not found")
    if writable and row["status"] == "archived":
        raise SpacesError("archived", "Space is archived")
    return row
