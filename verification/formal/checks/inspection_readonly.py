"""Runtime inspection answers the bridge read-only and exactly as the live bridge would (trees with inspection.py).

spaces_inspect (living_spaces_core/inspection.py, first in candidate 8008dcc) runs a Space in a headless browser
and answers its bridge calls from inspection.Snapshot through inspection.PassiveAdapter. No browser is started
here: the check drives the real Snapshot and PassiveAdapter directly, over every combination in a bounded domain,
and compares each answer with the live bridge.dispatch on the same database.

  ReadOnly      no adapter call commits anything to the database (PRAGMA data_version on a watcher connection)
  Refused       data.put, data.delete, data.batch, refresh, bot.request and net.fetch are refused with blocked
  SameAsLive    every other call returns what the live bridge returns with an open session and the same grants
                (records, order, paging, totals, seq, not_granted, invalid and not_found answers)
  Snapshot      a write committed after the snapshot opened is not visible to the adapter

Known findings (bugs on 92486e1, both introduced by 10517b9, which changed bridge.dispatch without PassiveAdapter):
  F4  PassiveAdapter replies to reads lack the live reply's "outcome" envelope ({"status": "success"|"rejected"}).
  F5  the live bridge answers every not_granted with "Operation could not be completed" and no capability
      (bridge._delivery_failure re-authorizes and _failure(authorized=False) redacts), against
      docs/contracts/CONTRACTS.md:118 "not_granted (extra: capability)"; the adapter still returns the documented
      error. Both are counted exactly: any other difference, or a changed case set, fails the check.

On a tree without inspection.py the check prints PASS with "not applicable".
"""
from __future__ import annotations

import hashlib
import itertools
import json
import sqlite3
from pathlib import Path

from harness import Violation, main, space

KNOWN = {"F4": "inspection replies lack the live bridge's outcome envelope",
         "F5": "live not_granted replies drop the documented capability and message"}
KNOWN_CASES_SHA256 = "4df25664e6a96b3afa0d1a78ea57f76c3da435cf4666f2400d7007e391155404"
REDACTED = "Operation could not be completed"


def known_difference(got, live):
    """Return F4/F5 when got differs from live only by those findings, else None."""
    rest = dict(live)
    outcome = rest.pop("outcome", None)
    if outcome != {"status": "success" if got.get("ok") else "rejected"}:
        return None
    if rest == got:
        return "F4"
    if (not got.get("ok") and not rest.get("ok") and set(rest) == {"ok", "error"}
            and got["error"]["code"] == "not_granted" == rest["error"]["code"]
            and rest["error"] == {"code": "not_granted", "message": REDACTED}):
        return "F5"
    return None

CAPS = ("data", "logs", "net")
WRITES = ("data.put", "data.delete", "data.batch", "refresh", "bot.request", "net.fetch")


class Commits:
    """PRAGMA data_version on a separate connection changes whenever any other connection commits."""

    def __init__(self, path):
        self.conn = sqlite3.connect(path, isolation_level=None)

    def __call__(self):
        return self.conn.execute("PRAGMA data_version").fetchone()[0]


def calls():
    wheres = [None, {"tag": "a"}, {"n": 1}, {"title": "t1"}, {"missing": None}]
    orders = [None, "n", "-n", "s", "-s", "title", "-title", "-", "missing"]
    for where, order, limit, offset in itertools.product(wheres, orders, (1, 2, 500), (0, 1, 5)):
        args = {"collection": "tasks", "limit": limit, "offset": offset}
        if where is not None:
            args["where"] = where
        if order is not None:
            args["order"] = order
        yield "data.query", args
    for rid in ("r0", "r3", "nope"):
        yield "data.get", {"collection": "tasks", "id": rid}
    yield "data.get", {"collection": "tasks"}
    yield "data.query", {"collection": "tasks", "limit": 0}
    yield "data.query", {"collection": "tasks", "bogus": 1}
    yield "meta", {}
    for limit in (1, 50, 0):
        yield "runs.list", {"limit": limit}
    yield "log", {"entries": [{"level": "info", "msg": "x"}], "lifecycle": "loaded"}
    yield "files.read", {}
    yield "data.put", {"collection": "tasks", "id": "r0", "data": {"n": 9}, "base_rev": 1}
    yield "data.delete", {"collection": "tasks", "id": "r0", "base_rev": 1}
    yield "data.batch", {"ops": [{"op": "put", "collection": "tasks", "id": "z", "data": {}}]}
    yield "refresh", {}
    yield "bot.request", {"activation_id": "a", "text": "hi"}
    yield "net.fetch", {"url": "https://example.com/"}


def check(core, home):
    src = Path(core.__file__).resolve().parent
    if not (src / "inspection.py").exists():
        return {"applicable": False, "reason": "not applicable: this tree has no living_spaces_core/inspection.py"}
    from living_spaces_core import db, inspection, records, runs
    sid = space(core, "Inspected")
    for i in range(7):
        records.put(sid, "tasks", f"r{i}", {"n": i % 3, "s": "abc"[i % 3] * (i + 1), "tag": "ab"[i % 2]}, actor="user")
        if i % 2:
            records.upsert_source(sid, "tasks", f"r{i}", {"title": f"t{i % 3}"}, {"handler": "agent"}, actor="upkeep")
    runs.start_refresh(sid, trigger="manual", actor="user")
    path = str(db.db_path())
    commits = Commits(path)
    cases, findings, finding_cases = 0, {}, []
    for on in itertools.chain.from_iterable(itertools.combinations(CAPS, k) for k in range(4)):
        for cap in CAPS:
            core.decide(sid, cap, "grant" if cap in on else "revoke", actor="user")
        head = core.get_space(sid)["head_rev"]
        conn = inspection._open_snapshot()
        try:
            snap = inspection.Snapshot(conn, sid, head)
            adapter = inspection.PassiveAdapter(snap)
            for spoof in (False, True):
                for op, args in calls():
                    if spoof:
                        args = {**args, "space": "someone-else"}
                    session = core.open_session(sid)["session"]
                    before = commits()
                    got = adapter.call(op, dict(args))
                    after = commits()
                    cases += 1
                    story = f"PassiveAdapter.call({op!r}, {args}) with grants {sorted(on) or 'none'} returned {got}"
                    if before != after:
                        raise Violation(f"ReadOnly: the database changed. {story}")
                    if op in WRITES:
                        needed = core.bridge._OPS[op][0]
                        if needed and needed not in on:
                            want_code = "not_granted"
                        else:
                            want_code = "blocked"
                        if got.get("ok") or got["error"]["code"] != want_code:
                            raise Violation(f"Refused: expected {want_code}. {story}")
                    else:
                        live = core.dispatch(sid, session, op, dict(args))
                        if got != live:
                            finding = known_difference(got, live)
                            if finding is None:
                                raise Violation(f"SameAsLive: the live bridge returned {live}. {story}")
                            findings.setdefault(finding, {"count": 0, "example": f"live {live}. {story}"})["count"] += 1
                            finding_cases.append([finding, sorted(on), spoof, op, args])
                    core.close_session(session)
            records.put(sid, "tasks", "late", {"n": 1}, actor="user")
            late = adapter.call("data.get", {"collection": "tasks", "id": "late"}) if "data" in on else None
            records.delete(sid, "tasks", "late", actor="user", base_rev=records.get(sid, "tasks", "late")["rev"])
            if late is not None and late.get("ok"):
                raise Violation(f"Snapshot: a record written after the snapshot opened was served: {late}")
        finally:
            conn.close()
    commits.conn.close()
    digest = hashlib.sha256(json.dumps(finding_cases, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if digest != KNOWN_CASES_SHA256:
        raise Violation(f"KnownFindingDrift: F4/F5 case set changed: "
                        f"{ {k: v['count'] for k, v in findings.items()} }, sha256={digest}. Review the bridge and "
                        "PassiveAdapter before updating the synced baseline.")
    return {"applicable": True, "cases": cases, "finding_cases_sha256": digest,
            "known_findings": {k: {"what": KNOWN[k], **v} for k, v in findings.items()}}


if __name__ == "__main__":
    main(check)
