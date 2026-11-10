"""Bounded Space diagnostics with secret redaction before persistence."""
import re

from . import db, limits
from .errors import SpacesError

_SECRETS = re.compile(
    r'''\bsk-[A-Za-z0-9_-]+|\bgh[po]_[A-Za-z0-9_]+'''
    r'''|\bBearer\s+(?:"[^"]*"|'[^']*'|[^\s"'<>]+)'''
    r'''|\bpassword\s*=\s*(?:"[^"]*"|'[^']*'|[^\s"'&<>]+)'''
    r'''|\b[A-Fa-f0-9]{32,}\b'''
    r'''|(?<![A-Za-z0-9_+/=-])[A-Za-z0-9_+/-]{32,}={0,2}(?![A-Za-z0-9_+/=-])''',
    re.IGNORECASE,
)


def redact(message):
    return _SECRETS.sub("[REDACTED]", message)


def redact_values(value):
    if isinstance(value, dict):
        return {key: redact_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_values(item) for item in value]
    return redact(value) if isinstance(value, str) else value


def _add_logs(conn, sid, session, entries):
    if not isinstance(entries, list):
        raise SpacesError("invalid", "Log entries must be an array")
    limits.check(len(entries), limits.LOG_ENTRIES, "log entries")
    clean = []
    for entry in entries:
        limits.object_json(entry)
        if set(entry) - {"level", "msg"} or "level" not in entry or "msg" not in entry:
            raise SpacesError("invalid", "Log entries require level and msg")
        limits.text(entry["level"], "log level")
        limits.text(entry["msg"], "log message", nonempty=False)
        limits.check(len(entry["msg"]), limits.LOG_MESSAGE, "log message characters")
        clean.append((entry["level"], redact(entry["msg"])))
    space = db.space(conn, sid)
    if session is not None:
        from .sessions import _require
        _require(conn, sid, session)
    for level, message in clean:
        conn.execute("INSERT INTO logs(space,session,rev,at,level,msg) VALUES(?,?,?,?,?,?)",
                     (sid, session, space["head_rev"], db.now(), level, message))
    conn.execute("DELETE FROM logs WHERE space=? AND id NOT IN (SELECT id FROM logs WHERE space=? ORDER BY id DESC LIMIT ?)",
                 (sid, sid, limits.LOG_HISTORY))
    return len(clean)


def add_logs(sid, session, entries):
    with db.write() as conn:
        return _add_logs(conn, sid, session, entries)


def read_logs(sid, limit=100, level=None):
    limits.integer(limit, "limit")
    if level is not None:
        limits.text(level, "level")
    with db.read() as conn:
        db.space(conn, sid)
        return [dict(row) for row in conn.execute(
            "SELECT * FROM logs WHERE space=? AND (? IS NULL OR level=?) ORDER BY id DESC LIMIT ?",
            (sid, level, level, limit))]
