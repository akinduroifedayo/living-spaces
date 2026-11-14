"""Bounded Space diagnostics with secret redaction before persistence."""
import json
import re

from . import db, limits
from .errors import SpacesError

_CREDENTIAL_KEY = re.compile(r"password|api_key|access_token|refresh_token|client_secret|authorization", re.IGNORECASE)
_CREDENTIAL_ASSIGNMENT = re.compile(
    r'''(?<![\w])(?P<prefix>(?P<key_quote>["']?)(?:''' + _CREDENTIAL_KEY.pattern
    + r''')(?P=key_quote)\s*[:=]\s*)'''
    r'''(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^\s"'&,;{}\[\]<>]+)''',
    re.IGNORECASE,
)
_SECRETS = re.compile(
    r'''\bsk-[A-Za-z0-9_-]+|\bgh[po]_[A-Za-z0-9_]+'''
    r'''|\bBearer\s+(?:"[^"]*"|'[^']*'|[^\s"'<>]+)'''
    r'''|\b[A-Fa-f0-9]{32,}\b'''
    r'''|(?<![A-Za-z0-9_+/=-])[A-Za-z0-9_+/-]{32,}={0,2}(?![A-Za-z0-9_+/=-])''',
    re.IGNORECASE,
)


def redact(message):
    try:
        value = json.loads(message)
    except (ValueError, RecursionError):
        value = None
    if isinstance(value, (dict, list)):
        clean = redact_values(value)
        return json.dumps(clean, ensure_ascii=False) if clean != value else message
    message = _SECRETS.sub("[REDACTED]", message)
    return _CREDENTIAL_ASSIGNMENT.sub(lambda match: match["prefix"] + '"[REDACTED]"', message)


def redact_values(value):
    if isinstance(value, dict):
        return {key: "[REDACTED]" if _CREDENTIAL_KEY.fullmatch(key) else redact_values(item)
                for key, item in value.items()}
    if isinstance(value, list):
        return [redact_values(item) for item in value]
    return redact(value) if isinstance(value, str) else value


def _add_logs(conn, sid, session, entries, *, lifecycle=None, dropped=0, unconfirmed=0):
    if lifecycle is not None and lifecycle not in ("loaded", "failed"):
        raise SpacesError("invalid", "Log lifecycle must be loaded or failed")
    for name, count in (("dropped", dropped), ("unconfirmed", unconfirmed)):
        limits.integer(count, name)
        limits.check(count, 2**53 - 1, name)
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
        message = redact(entry["msg"])
        limits.check(len(message), limits.LOG_MESSAGE, "redacted log message characters")
        clean.append((entry["level"], message))
    space = db.space(conn, sid)
    rev, attribution = space["head_rev"], "unattributed"
    if session is not None:
        from .sessions import _require
        opened = _require(conn, sid, session)
        rev, attribution = opened["head_rev"], "session_opened"
        conn.execute("""UPDATE sessions SET lifecycle=coalesce(lifecycle,?),
            log_errors=log_errors+?, log_warnings=log_warnings+?, log_dropped=max(log_dropped,?),
            log_unconfirmed=max(log_unconfirmed,?) WHERE id=?""",
                     (lifecycle, sum(level == "error" for level, _ in clean),
                      sum(level == "warn" for level, _ in clean), dropped, unconfirmed, session))
    for level, message in clean:
        conn.execute("INSERT INTO logs(space,session,rev,at,level,msg,attribution) VALUES(?,?,?,?,?,?,?)",
                     (sid, session, rev, db.now(), level, message, attribution))
    conn.execute("DELETE FROM logs WHERE space=? AND id NOT IN (SELECT id FROM logs WHERE space=? ORDER BY id DESC LIMIT ?)",
                 (sid, sid, limits.LOG_HISTORY))
    return len(clean)


def add_logs(sid, session, entries):
    with db.write() as conn:
        return _add_logs(conn, sid, session, entries)


def read_logs(sid, limit=100, level=None, *, include_summary=False):
    limits.integer(limit, "limit")
    if level is not None:
        limits.text(level, "level")
    with db.read() as conn:
        space = db.space(conn, sid)
        entries = [dict(row) for row in conn.execute(
            "SELECT * FROM logs WHERE space=? AND (? IS NULL OR level=?) ORDER BY id DESC LIMIT ?",
            (sid, level, level, limit))]
        if not include_summary:
            return entries
        totals = conn.execute("""SELECT count(*) AS sessions,
            coalesce(sum(lifecycle='loaded'),0) AS loaded, coalesce(sum(lifecycle='failed'),0) AS failed,
            coalesce(sum(lifecycle IS NULL),0) AS unreported, coalesce(sum(log_errors),0) AS errors,
            coalesce(sum(log_warnings),0) AS warnings, coalesce(sum(log_dropped),0) AS dropped,
            coalesce(sum(log_unconfirmed),0) AS unconfirmed
            FROM sessions WHERE space=? AND head_rev=?""", (sid, space["head_rev"])).fetchone()
        return {"entries": entries, "summary": {
            "rev": space["head_rev"], "opened": totals["sessions"] > 0, **dict(totals),
        }}
