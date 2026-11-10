"""Space-bound frame sessions, invalidated explicitly on close."""
import secrets

from . import db
from .errors import SpacesError


def open_session(sid):
    from .grants import _grant

    with db.write() as conn:
        space = db.space(conn, sid, writable=True)
        session = secrets.token_urlsafe(32)
        conn.execute("INSERT INTO sessions(id,space,created_at,head_rev) VALUES(?,?,?,?)",
                     (session, sid, db.now(), space["head_rev"]))
        grants = [_grant(row) for row in conn.execute("SELECT * FROM grants WHERE space=? ORDER BY capability", (sid,))]
        return {"session": session, "grants": grants, "head_rev": space["head_rev"]}


def close_session(session):
    if not isinstance(session, str):
        raise SpacesError("session_invalid", "Invalid session")
    with db.write() as conn:
        conn.execute("UPDATE sessions SET closed_at=coalesce(closed_at,?) WHERE id=?", (db.now(), session))
    return {"closed": True}


def _require(conn, sid, session):
    if not isinstance(session, str) or not isinstance(sid, str):
        raise SpacesError("session_invalid", "Invalid session")
    row = conn.execute("SELECT * FROM sessions WHERE id=? AND space=? AND closed_at IS NULL", (session, sid)).fetchone()
    if row is None:
        raise SpacesError("session_invalid", "Session is closed, unknown or belongs to another Space")


def require(sid, session):
    with db.read() as conn:
        _require(conn, sid, session)
