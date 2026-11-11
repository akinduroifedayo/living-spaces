"""SQLite storage for Living Spaces. One database per Hermes home, schema owned here (CONTRACTS.md §2)."""
from __future__ import annotations

import os
import sqlite3
import time
import threading
from contextlib import contextmanager
from pathlib import Path

SCHEMA_VERSION = 1

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
  admission_id TEXT, settled INTEGER NOT NULL DEFAULT 0 CHECK(settled IN (0,1)), created_at REAL NOT NULL,
  PRIMARY KEY(space, activation_id));
CREATE UNIQUE INDEX IF NOT EXISTS one_unresolved_action ON action_intents(space) WHERE settled=0;
CREATE TABLE IF NOT EXISTS action_keys(space TEXT NOT NULL, activation_id TEXT NOT NULL, request TEXT NOT NULL,
  intent_id TEXT NOT NULL, PRIMARY KEY(space,activation_id),
  FOREIGN KEY(space,intent_id) REFERENCES action_intents(space,activation_id) ON DELETE CASCADE);
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
  closed_at REAL, head_rev INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, space TEXT NOT NULL,
  trigger TEXT NOT NULL CHECK(trigger IN ('manual','schedule','chat')), handler TEXT NOT NULL, actor TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('queued','running','succeeded','failed','canceled','blocked')),
  queued_at REAL NOT NULL, started_at REAL, ended_at REAL, source_as_of REAL,
  changed TEXT NOT NULL DEFAULT '{}', error TEXT, detail TEXT NOT NULL DEFAULT '{}', heartbeat_at REAL);
CREATE TABLE IF NOT EXISTS upkeep_links(space TEXT NOT NULL REFERENCES spaces(id), cron_job_id TEXT NOT NULL UNIQUE,
  kind TEXT NOT NULL CHECK(kind IN ('agent','feed')), created_at REAL NOT NULL, created_by TEXT NOT NULL,
  PRIMARY KEY(space, cron_job_id));
CREATE TABLE IF NOT EXISTS logs(id INTEGER PRIMARY KEY AUTOINCREMENT, space TEXT NOT NULL, session TEXT, rev INTEGER,
  at REAL NOT NULL, level TEXT NOT NULL, msg TEXT NOT NULL);
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


def connect() -> sqlite3.Connection:
    path = db_path()
    existed = path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=5.0, check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    key = str(path)
    with _schema_lock:
        if key not in _initialized or not existed:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(DDL)
            conn.execute("BEGIN IMMEDIATE")
            try:
                from .migrations import grant_internet_access, link_native_upkeep
                grant_internet_access(conn)
                link_native_upkeep(conn)
                conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                conn.execute("COMMIT")
            except BaseException:
                conn.close()
                raise
            _initialized.add(key)
    return conn


@contextmanager
def read():
    conn = connect()
    try:
        conn.execute("BEGIN")
        yield conn
    finally:
        conn.close()


@contextmanager
def write():
    """One IMMEDIATE transaction: every multi-step write commits whole or not at all."""
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        conn.execute("COMMIT")
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
