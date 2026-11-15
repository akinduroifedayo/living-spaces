"""Space authority through the frame bridge: every combination in a bounded domain, on real bridge.dispatch.

The only backend entry for Space code is bridge.dispatch(sid, session, op, args) (bridge.py:68-93). This check
enumerates every combination of
  session    open for this Space, open for the other Space, closed, unknown, not a string
  operation  every bridge op that needs no network or native adapter, plus an unknown op
  grants     every on/off combination of data, logs and net for this Space
  space arg  absent, or naming the other Space (Space code may put "space" in args; bridge.py:82 strips it)
and checks two properties:
  Authority  a call succeeds only with an open session bound to this Space and every capability the op needs
             (bridge.py:5-17); a call without them returns session_invalid or not_granted
  NoEffect   a refused call changes no records, changes, runs or logs anywhere, and no call changes the
             other Space's records, changes, runs, logs, grants or sessions
"""
from __future__ import annotations

import itertools

from harness import Violation, main, space

CAPS = ("data", "logs", "net")
TABLES = ("records", "changes", "runs", "logs", "grants", "sessions")


def ops(collection_rev):
    rev = collection_rev
    return {
        "meta": (None, {}),
        "data.query": ("data", {"collection": "tasks"}),
        "data.get": ("data", {"collection": "tasks", "id": "seed"}),
        "data.put": ("data", {"collection": "tasks", "id": "seed", "data": {"done": True}, "base_rev": rev}),
        "data.delete": ("data", {"collection": "tasks", "id": "seed", "base_rev": rev}),
        "data.batch": ("data", {"ops": [{"op": "put", "collection": "tasks", "id": "other", "data": {"n": 1}}]}),
        "runs.list": (None, {}),
        "refresh": (None, {}),
        "log": ("logs", {"entries": [{"level": "info", "msg": "hello"}]}),
        "files.read": ("unknown", {}),
    }


def counts(sid):
    from living_spaces_core import db
    with db.read() as conn:
        return {t: conn.execute(f"SELECT count(*), coalesce(sum(length(CAST(rowid AS TEXT))),0) FROM {t} WHERE space=?", (sid,)).fetchone()[0]
                for t in TABLES} | {"record_state": [tuple(r) for r in conn.execute(
                    "SELECT collection,id,rev,data FROM records WHERE space=? ORDER BY collection,id", (sid,))]}


def set_grants(core, sid, on):
    for cap in CAPS:
        core.decide(sid, cap, "grant" if cap in on else "revoke", actor="user")


def check(core, home):
    from living_spaces_core import records, sessions
    a, b = space(core, "Authority A"), space(core, "Authority B")
    cases = denied = allowed = 0
    for on in itertools.chain.from_iterable(itertools.combinations(CAPS, k) for k in range(4)):
        on = set(on)
        for kind in ("open", "other", "closed", "unknown", "nonstring"):
            for op_name in ops(0):
                for spoof in (False, True):
                    set_grants(core, a, set(CAPS))
                    try:
                        seed = records.get(a, "tasks", "seed")
                    except core.SpacesError:
                        seed = records.put(a, "tasks", "seed", {"done": False}, actor="user")
                    set_grants(core, a, on)
                    session = {"open": lambda: core.open_session(a)["session"],
                               "other": lambda: core.open_session(b)["session"],
                               "closed": lambda: _closed(core, a),
                               "unknown": lambda: "not-a-real-session-token-000000000000",
                               "nonstring": lambda: 12345}[kind]()
                    cap, args = ops(seed["rev"])[op_name]
                    if spoof:
                        args = {**args, "space": b}
                    before_a, before_b = counts(a), counts(b)
                    reply = core.dispatch(a, session, op_name, args)
                    after_a, after_b = counts(a), counts(b)
                    cases += 1
                    authorized = kind == "open" and cap != "unknown" and (cap is None or cap in on)
                    story = (f"dispatch({a!r}, <session {kind}>, {op_name!r}, {args}) with grants {sorted(on) or 'none'} "
                             f"returned {reply}")
                    data_keys = ("records", "changes", "runs", "logs", "record_state")
                    if after_b != before_b and not (kind == "other" and _only_session_rows(before_b, after_b)):
                        raise Violation(f"NoEffect: the other Space {b!r} changed. {story}. before {before_b} after {after_b}")
                    if not authorized:
                        if reply.get("ok"):
                            raise Violation(f"Authority: an unauthorized call succeeded. {story}")
                        if reply["error"]["code"] not in ("session_invalid", "not_granted"):
                            raise Violation(f"Authority: unauthorized call refused with {reply['error']['code']}, "
                                            f"not session_invalid/not_granted. {story}")
                        if any(after_a[k] != before_a[k] for k in data_keys):
                            raise Violation(f"NoEffect: a refused call changed this Space's data. {story}. "
                                            f"before {before_a} after {after_a}")
                        denied += 1
                    else:
                        if not reply.get("ok") and reply["error"]["code"] in ("session_invalid", "not_granted"):
                            raise Violation(f"Authority: an authorized call was refused. {story}")
                        allowed += 1
                    if isinstance(session, str):
                        sessions.close_session(session)
    return {"cases": cases, "refused_unauthorized": denied, "authorized": allowed}


def _closed(core, sid):
    token = core.open_session(sid)["session"]
    core.close_session(token)
    return token


def _only_session_rows(before, after):
    return all(before[k] == after[k] for k in before if k != "sessions")


if __name__ == "__main__":
    main(check)
