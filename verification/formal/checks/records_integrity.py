"""Records against a reference model: generated operation sequences on real living_spaces_core.records.

Each sequence runs put / delete / batch / upsert_source / recovery-point restore against two Spaces and, after
every step, compares the whole stored state of both Spaces with a pure-Python model of the documented rules
(records.py:43-71, 80-90, 138-159, 168-190, 255-282):

  Conflict       a write with a stale base_rev is refused; an existing record needs its exact current rev
  RevMonotonic   a record's rev is one past every rev it ever had, across delete and re-create
  UserOwned      a source upsert never changes user data; "unchanged" sources do not bump rev
  BatchAtomic    a batch with one bad operation changes nothing
  Isolation      an operation on one Space never changes the other
  Cursor         changes_since(0) lists every change once, in increasing seq, each record's history in order
"""
from __future__ import annotations

import copy
import random

from harness import Violation, main, space

SEQUENCES = 120
STEPS = 30
COLLECTIONS = ("tasks", "notes")
IDS = ("a", "b", "c")


class Model:
    def __init__(self):
        self.rows = {}      # (sid, coll, rid) -> {"data", "source", "meta", "rev"}
        self.maxrev = {}    # (sid, coll, rid) -> highest rev ever written
        self.log = {}       # sid -> [(coll, rid, op, rev)]

    def _bump(self, key, op):
        rev = self.maxrev.get(key, 0) + 1
        self.maxrev[key] = rev
        self.log.setdefault(key[0], []).append((key[1], key[2], op, rev))
        return rev

    def put(self, sid, coll, rid, data, base_rev, merge):
        key = (sid, coll, rid)
        row = self.rows.get(key)
        if (row is None and base_rev not in (None, 0)) or (row is not None and base_rev != row["rev"]):
            return "conflict"
        merged = {**row["data"], **data} if row and merge else dict(data)
        rev = self._bump(key, "put")
        self.rows[key] = {"data": merged, "source": row["source"] if row else None,
                          "meta": row["meta"] if row else None, "rev": rev}
        return "ok"

    def delete(self, sid, coll, rid, base_rev):
        key = (sid, coll, rid)
        row = self.rows.get(key)
        if row is None:
            return "not_found"
        if base_rev != row["rev"]:
            return "conflict"
        self._bump(key, "delete")
        del self.rows[key]
        return "ok"

    def source(self, sid, coll, rid, source, meta):
        key = (sid, coll, rid)
        row = self.rows.get(key)
        stable = {k: v for k, v in meta.items() if k != "fetched_at"}
        if row and row["source"] == source and {k: v for k, v in (row["meta"] or {}).items() if k != "fetched_at"} == stable:
            return "unchanged"
        rev = self._bump(key, "source")
        self.rows[key] = {"data": row["data"] if row else {}, "source": source, "meta": meta, "rev": rev}
        return "updated" if row else "added"

    def snapshot(self, sid):
        return {k[1:]: copy.deepcopy(v) for k, v in self.rows.items() if k[0] == sid}

    def restore(self, sid, snap):
        current = {k for k in self.rows if k[0] == sid}
        for key in sorted(current - {(sid,) + k for k in snap}):
            self._bump(key, "delete")
            del self.rows[key]
        for k, v in sorted(snap.items()):
            key = (sid,) + k
            rev = self._bump(key, "put")
            self.rows[key] = {**copy.deepcopy(v), "rev": rev}


def stored(core, sid):
    from living_spaces_core import db
    with db.read() as conn:
        rows = conn.execute("SELECT collection,id,data,source,source_meta,rev FROM records WHERE space=?", (sid,)).fetchall()
    import json
    return {(r["collection"], r["id"]): {"data": json.loads(r["data"]), "source": json.loads(r["source"]) if r["source"] else None,
                                         "meta": json.loads(r["source_meta"]) if r["source_meta"] else None, "rev": r["rev"]}
            for r in rows}


def code(fn):
    from living_spaces_core import SpacesError
    try:
        result = fn()
        return result if isinstance(result, str) else "ok"
    except SpacesError as exc:
        return exc.code


def compare(core, model, sids, history):
    for sid in sids:
        got = stored(core, sid)
        want = {k[1:]: {kk: vv for kk, vv in v.items()} for k, v in model.rows.items() if k[0] == sid}
        if got != want:
            diff = {k: (got.get(k), want.get(k)) for k in set(got) | set(want) if got.get(k) != want.get(k)}
            raise Violation(f"stored records of {sid} differ from the model after: {' ; '.join(history[-6:])}. "
                            f"(stored, model) per record: {diff}")
        changes = core.changes_since(sid, 0, limit=100000)["changes"]
        seqs = [c["seq"] for c in changes]
        if seqs != sorted(set(seqs)):
            raise Violation(f"changes_since({sid!r}, 0) seq is not strictly increasing: {seqs}")
        # Per record, the change history must match in order. Order across records inside one restore is
        # not promised (records.py:268-272 deletes in SQLite row order), so it is not compared.
        def per_record(entries):
            grouped = {}
            for coll, rid, op, rev in entries:
                grouped.setdefault((coll, rid), []).append((op, rev))
            return grouped
        log = [(c["collection"], c["id"], c["op"], c["rev"]) for c in changes]
        if per_record(log) != per_record(model.log.get(sid, [])):
            raise Violation(f"change log of {sid} differs from the model after: {' ; '.join(history[-6:])}. "
                            f"stored tail {log[-4:]}, model tail {model.log.get(sid, [])[-4:]}")


def step(core, model, rng, sids, points, history):
    from living_spaces_core import records
    sid = rng.choice(sids)
    coll, rid = rng.choice(COLLECTIONS), rng.choice(IDS)
    row = model.rows.get((sid, coll, rid))
    base = rng.choice([None, 0, (row or {}).get("rev"), ((row or {}).get("rev") or 1) - 1, ((row or {}).get("rev") or 0) + 1])
    kind = rng.choice(["put", "put", "delete", "batch", "source", "source", "point", "restore"])
    if kind == "put":
        data, merge = {rng.choice("xyz"): rng.randint(0, 3)}, rng.random() < 0.6
        want = model.put(sid, coll, rid, data, base, merge)
        got = code(lambda: records.put(sid, coll, rid, data, actor="user", base_rev=base, merge=merge))
        label = f"put({sid},{coll}/{rid},{data},base_rev={base},merge={merge})"
    elif kind == "delete":
        want = model.delete(sid, coll, rid, base)
        got = code(lambda: records.delete(sid, coll, rid, actor="user", base_rev=base))
        label = f"delete({sid},{coll}/{rid},base_rev={base})"
    elif kind == "source":
        source = {"title": rng.choice(["t1", "t2"])}
        meta = {"handler": "agent", "fetched_at": rng.randint(0, 9), "etag": rng.choice(["e1", "e2"])}
        want = model.source(sid, coll, rid, source, meta)
        got = code(lambda: records.upsert_source(sid, coll, rid, source, meta, actor="upkeep"))
        label = f"upsert_source({sid},{coll}/{rid},{source},{meta})"
    elif kind == "batch":
        ops = []
        for _ in range(rng.randint(1, 3)):
            c, r = rng.choice(COLLECTIONS), rng.choice(IDS)
            if rng.random() < 0.7:
                ops.append({"op": "put", "collection": c, "id": r, "data": {"w": rng.randint(0, 3)},
                            "base_rev": rng.choice([None, 0, 1, 2, 3])})
            else:
                ops.append({"op": "delete", "collection": c, "id": r, "base_rev": rng.choice([None, 1, 2, 3])})
        trial = copy.deepcopy(model)
        want = "ok"
        for op in ops:
            outcome = (trial.put(sid, op["collection"], op["id"], op["data"], op["base_rev"], True) if op["op"] == "put"
                       else trial.delete(sid, op["collection"], op["id"], op["base_rev"]))
            if outcome != "ok":
                want = outcome
                break
        if want == "ok":
            model.__dict__.update(trial.__dict__)
        got = code(lambda: records.batch(sid, ops, actor="user"))
        label = f"batch({sid},{ops})"
    elif kind == "point":
        pid = records.create_recovery_point(sid, "checkpoint")
        points.append((sid, pid, model.snapshot(sid)))
        want = got = "ok"
        label = f"create_recovery_point({sid}) -> {pid}"
    else:
        mine = [p for p in points if p[0] == sid]
        if not mine:
            return
        _, pid, snap = rng.choice(mine)
        before = model.snapshot(sid)
        model.restore(sid, snap)
        got = code(lambda: records.restore_recovery_point(sid, pid, actor="user"))
        want = "ok"
        if got == "ok":  # restore takes its own recovery point of the prior state first (records.py:266)
            points.append((sid, records.list_recovery_points(sid)[0]["id"], before))
        label = f"restore_recovery_point({sid},{pid})"
    history.append(f"{label} -> {got}")
    if got != want:
        raise Violation(f"{label} returned {got}, the model expects {want}. Steps before: {' ; '.join(history[-6:-1])}")


def check(core, home):
    total = 0
    for seed in range(SEQUENCES):
        rng = random.Random(seed)
        sids = [space(core, f"Records {seed} A"), space(core, f"Records {seed} B")]
        model, points, history = Model(), [], []
        for _ in range(STEPS):
            step(core, model, rng, sids, points, history)
            compare(core, model, sids, history)
            total += 1
    return {"sequences": SEQUENCES, "steps": total, "seeds": f"0..{SEQUENCES - 1}"}


if __name__ == "__main__":
    main(check)
