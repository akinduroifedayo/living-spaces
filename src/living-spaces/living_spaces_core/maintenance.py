"""Plugin-owned maintenance admission and evidence. Native cron owns execution."""
from __future__ import annotations

from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
from typing import Any
import json
import math
import uuid

from . import db
from .errors import SpacesError

_WORK = ("refresh", "run")
_operation: ContextVar[dict[str, Any] | None] = ContextVar("maintenance_operation", default=None)
_connection: ContextVar[Any] = ContextVar("maintenance_connection", default=None)
_feed_writer: ContextVar[dict[str, Any] | None] = ContextVar("maintenance_feed_writer", default=None)


def initialize(conn):
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(refresh_claims)")}
    for name, declaration in (("incarnation", "TEXT"), ("link_generation", "INTEGER"),
                              ("command", "TEXT"), ("owner", "TEXT")):
        if name not in columns:
            conn.execute(f"ALTER TABLE refresh_claims ADD COLUMN {name} {declaration}")
    for row in conn.execute("SELECT id FROM spaces WHERE id NOT IN (SELECT space FROM maintenance_spaces)").fetchall():
        create_identity(conn, row["id"])
    for row in conn.execute("SELECT c.* FROM refresh_claims c JOIN spaces s ON s.id=c.space "
                            "WHERE c.incarnation IS NULL AND c.space_created_at=s.created_at").fetchall():
        state = identity(conn, row["space"])
        conn.execute("UPDATE refresh_claims SET incarnation=?,link_generation=?,command='refresh',owner='legacy' "
                     "WHERE token=?", (state["incarnation"], state["link_generation"], row["token"]))
        conn.execute("INSERT OR IGNORE INTO maintenance_operations "
                     "(token,space,incarnation,command,owner,cron_job_id,link_generation,phase,native,created_at) "
                     "VALUES(?,?,?,'refresh','legacy',?,?,?,?,?)",
                     (row["token"], row["space"], state["incarnation"], row["cron_job_id"],
                      state["link_generation"], row["phase"], row["native"], row["created_at"]))
        if row["created_one_shot"]:
            native = json.loads(row["native"]) if row["native"] else None
            baseline = acceptance_baseline(native, row["cron_job_id"])
            conn.execute("UPDATE refresh_claims SET baseline_completion=?,phase=? WHERE token=?",
                         (baseline, "background" if baseline is not None and outcome(native, row["cron_job_id"]) == "background"
                          else "unresolved", row["token"]))
            conn.execute("INSERT OR IGNORE INTO maintenance_effects "
                         "(id,operation,action,cron_job_id,phase,obligation) VALUES(?,?, 'pause',?,'possibly_sent','disable')",
                         (row["token"] + ':disable', row["token"], row["cron_job_id"]))
    conn.execute("INSERT OR IGNORE INTO maintenance_feeds(run,incarnation) "
                 "SELECT r.id,m.incarnation FROM runs r JOIN maintenance_spaces m ON m.space=r.space")


def create_identity(conn, sid):
    conn.execute("INSERT INTO maintenance_spaces(space,incarnation) VALUES(?,?)", (sid, uuid.uuid4().hex))


def identity(conn, sid):
    db.space(conn, sid)
    row = conn.execute("SELECT * FROM maintenance_spaces WHERE space=?", (sid,)).fetchone()
    if row is None:
        create_identity(conn, sid)
        row = conn.execute("SELECT * FROM maintenance_spaces WHERE space=?", (sid,)).fetchone()
    return dict(row)


def claim(conn, sid):
    row = conn.execute("SELECT * FROM refresh_claims WHERE space=?", (sid,)).fetchone()
    return dict(row) if row else None


def connection():
    return _connection.get()


def operation(conn, token):
    row = conn.execute("SELECT * FROM maintenance_operations WHERE token=?", (token,)).fetchone()
    return dict(row) if row else None


def fence(conn, op, *, work=False, archived=False):
    row = conn.execute("SELECT s.status,m.incarnation,m.link_generation FROM spaces s "
                       "JOIN maintenance_spaces m ON m.space=s.id WHERE s.id=?", (op["space"],)).fetchone()
    if row is None or row["incarnation"] != op["incarnation"]:
        raise SpacesError("not_found", "The original Space was deleted", reason="maintenance_incarnation_lost")
    if archived and row["status"] == "archived":
        raise SpacesError("archived", "Space was archived during maintenance")
    current = operation(conn, op["token"])
    if current is None or current["phase"] == "retired" or row["link_generation"] != op["link_generation"]:
        raise SpacesError("blocked", "This maintenance operation was explicitly retired", reason="refresh_claim_lost",
                          cron_job_id=op.get("cron_job_id"))
    if work:
        held = claim(conn, op["space"])
        if (held is None or held["token"] != op["token"] or held["incarnation"] != op["incarnation"]
                or held["cron_job_id"] != op["cron_job_id"]):
            raise SpacesError("blocked", "This refresh no longer owns native work", reason="refresh_claim_lost",
                              cron_job_id=op.get("cron_job_id"))
    return row


@contextmanager
def scope(op):
    marker = _operation.set(op)
    try:
        yield
    finally:
        _operation.reset(marker)


@contextmanager
def transaction(op, *, feed_admission=False):
    if "token" not in op:
        with db.write() as conn:
            db.space(conn, op["space"], writable=op["command"] in ("schedule", "run", "resume"))
            state = identity(conn, op["space"])
            if state["incarnation"] != op["incarnation"]:
                raise SpacesError("not_found", "The original Space was deleted", reason="maintenance_incarnation_lost")
            if state["link_generation"] != op["link_generation"]:
                raise SpacesError("blocked", "The upkeep link changed", reason="refresh_claim_lost",
                                  cron_job_id=op["cron_job_id"])
            if op["command"] != "run" or feed_admission:
                current = _feed_control(conn, op["space"], op["command"])
                if current is None or current["cron_job_id"] != op["cron_job_id"]:
                    raise SpacesError("blocked", "The upkeep is no longer feed-only", reason="refresh_claim_lost",
                                      cron_job_id=op["cron_job_id"])
            marker = _connection.set(conn)
            try:
                with scope(None):
                    yield conn
            finally:
                _connection.reset(marker)
        return
    with db.write() as conn:
        fence(conn, op)
        marker = _connection.set(conn)
        try:
            with scope(op):
                yield conn
                if op["command"] not in _WORK:
                    conn.execute("UPDATE maintenance_operations SET phase='retired',outcome='applied' WHERE token=?",
                                 (op["token"],))
        finally:
            _connection.reset(marker)


def _insert_operation(conn, sid, command, actor, jid=None) -> dict[str, Any]:
    state = identity(conn, sid)
    op: dict[str, Any] = dict(token=uuid.uuid4().hex, space=sid, incarnation=state["incarnation"], command=command,
              owner=actor, cron_job_id=jid, link_generation=state["link_generation"],
              phase="possibly_sent", created_at=db.now())
    conn.execute("INSERT INTO maintenance_operations "
                 "(token,space,incarnation,command,owner,cron_job_id,link_generation,phase,created_at) "
                 "VALUES(:token,:space,:incarnation,:command,:owner,:cron_job_id,:link_generation,:phase,:created_at)", op)
    # This committed command envelope covers effects made inside the following lifecycle writer.
    # If that writer dies, even an unknown create ID remains a recovery barrier.
    conn.execute("INSERT INTO maintenance_effects(id,operation,action,cron_job_id,phase) VALUES(?,?,?,?, 'possibly_sent')",
                 (op["token"] + ':intent', op["token"], command, jid))
    op["effects"] = []
    return op


def _block(ids, *, feeds=()):
    ids = sorted(set(value for value in ids if value))
    raise SpacesError("blocked", "Maintenance completion is unknown. Use Upkeep Remove before retrying: "
                      + ", ".join(ids or feeds or ("unknown native create",)), reason="refresh_outcome_unknown",
                      orphan_job_ids=ids, run_ids=list(feeds))


def admit(conn, sid, command, *, actor, target=None, own=None):
    from . import upkeep

    state = identity(conn, sid)
    held = claim(conn, sid)
    if held and held["incarnation"] != state["incarnation"]:
        _block([held["cron_job_id"]])
    if held and command in (*_WORK, "resume"):
        if command == "refresh" or (command == "run" and held["cron_job_id"] == target):
            joined = join(conn, held, actor=actor)
            if joined is not None:
                return joined
        elif command == "resume":
            if join(conn, held, actor=actor) is not None:
                _block([held["cron_job_id"]])
        else:
            _block([held["cron_job_id"]])
        held = claim(conn, sid)
    link = upkeep._link(conn, sid)
    if held and command == "schedule" and (not link or held["cron_job_id"] != link["cron_job_id"]):
        _block([held["cron_job_id"]])
    controls = conn.execute("SELECT * FROM maintenance_operations WHERE space=? AND incarnation=? "
                            "AND phase IN ('possibly_sent','unresolved') AND command NOT IN ('refresh','run')",
                            (sid, state["incarnation"])).fetchall()
    controls = [row for row in controls if row["token"] != own]
    if controls:
        _block([row["cron_job_id"] for row in controls])
    feed_rows = conn.execute("SELECT id FROM runs WHERE space=? AND status IN ('queued','running')", (sid,)).fetchall()
    if feed_rows and command != "feed":
        _block([], feeds=[row["id"] for row in feed_rows])
    jobs = upkeep._jobs()["jobs"]
    unlinked = [job["job_id"] for job in upkeep._owned_jobs(sid, link, jobs)
                if not link or job["job_id"] != link["cron_job_id"]]
    if unlinked:
        _block(unlinked)
    if held and command not in ("schedule",):
        _block([held["cron_job_id"]])
    return None


@contextmanager
def control(sid, command, *, actor, kind=None):
    with db.write() as conn:
        space = db.space(conn, sid)
        if command in ("schedule", "resume") and space["status"] == "archived":
            raise SpacesError("archived", "Unarchive the Space before scheduling upkeep")
        from . import upkeep
        link = upkeep._link(conn, sid)
        if command == "resume" and not link:
            raise SpacesError("not_found", "No upkeep scheduled")
        op = _feed_control(conn, sid, command) if kind == "feed" else None
        if op is None:
            if command in ("schedule", "resume"):
                admit(conn, sid, command, actor=actor, target=link["cron_job_id"] if link else None)
            op = _insert_operation(conn, sid, command, actor, link["cron_job_id"] if link else None)
    try:
        with scope(op if "token" in op else None):
            yield op
    except BaseException as exc:
        if "token" not in op:
            raise
        # A killed process leaves the committed envelope. A live error keeps any
        # receipts that rolled back with the lifecycle transaction.
        try:
            with db.write() as conn:
                error = exc.to_dict() if isinstance(exc, SpacesError) else {"message": str(exc)}
                known_refusal = (isinstance(exc, SpacesError) and exc.extra.get("reason") == "native_refused"
                                 and not (isinstance(exc.extra.get("native"), dict)
                                          and exc.extra["native"].get("job_saved") is True))
                unsent = not op["effects"]
                phase = "retired" if known_refusal or unsent else "unresolved"
                conn.execute("UPDATE maintenance_operations SET phase=?,outcome=?,error=? WHERE token=? AND phase!='retired'",
                             (phase, "refused" if known_refusal else "unsent" if unsent else None, json.dumps(error), op["token"]))
                for effect in op["effects"]:
                    conn.execute("INSERT OR REPLACE INTO maintenance_effects "
                                 "(id,operation,action,cron_job_id,phase,native,verification) "
                                 "VALUES(:id,:operation,:action,:cron_job_id,:phase,:native,:verification)", effect)
        except Exception as storage:
            if isinstance(exc, SpacesError):
                exc.extra["receipt_error"] = str(storage)
        raise


def invoke(action, args, call):
    op = _operation.get()
    if op is None or action == "list":
        return call()
    eid = uuid.uuid4().hex
    effect = dict(id=eid, operation=op["token"], action=action, cron_job_id=args.get("job_id"),
                  phase="possibly_sent", native=None, verification=None)
    op.setdefault("effects", []).append(effect)
    conn = connection()
    try:
        with nullcontext(conn) if conn is not None else db.write() as writer:
            fence(writer, op)
            writer.execute("INSERT INTO maintenance_effects(id,operation,action,cron_job_id,phase) VALUES(?,?,?,?, 'possibly_sent')",
                           (eid, op["token"], action, args.get("job_id")))
    except SpacesError:
        raise
    except Exception as exc:
        raise SpacesError("blocked", f"Cannot record intent for native {action}: {exc}",
                          reason="maintenance_store_unavailable", unsent=True, action=action) from exc
    try:
        native = call()
    except SpacesError as exc:
        effect.update(native=json.dumps(exc.extra.get("native")), verification=json.dumps(exc.to_dict()))
        try:
            with nullcontext(conn) if conn is not None else db.write() as writer:
                writer.execute("UPDATE maintenance_effects SET native=?,verification=? WHERE id=?",
                               (json.dumps(exc.extra.get("native")), json.dumps(exc.to_dict()), eid))
        except Exception as record_error:
            exc.extra["receipt_error"] = str(record_error)
        raise
    effect.update(phase="observed", native=json.dumps(native), cron_job_id=args.get("job_id") or native.get("job_id"))
    try:
        with nullcontext(conn) if conn is not None else db.write() as writer:
            writer.execute("UPDATE maintenance_effects SET phase='observed',native=?,cron_job_id=COALESCE(cron_job_id,?) WHERE id=?",
                           (json.dumps(native), native.get("job_id"), eid))
            if action == "run":
                writer.execute("UPDATE maintenance_operations SET native=? WHERE token=?", (json.dumps(native), op["token"]))
    except Exception as exc:
        raise SpacesError("blocked", f"Could not record the native {action} reply: {exc}",
                          reason="post_run_check_failed" if action == "run" else "maintenance_store_unavailable",
                          native=native, action=action, job_id=args.get("job_id")) from exc
    return native


def compensate_without_receipt(work, cleanup):
    """Best effort on a storage outage; never retire ownership or replay work.

    The previously committed intent still blocks admission. Only exact owned IDs
    may be suppressed/removed, after a read-only incarnation/token/generation fence.
    There is no durable new receipt if storage remains unavailable.
    """
    with db.read() as conn:
        fence(conn, work, work=True)
    with scope(None):
        return cleanup()


def acquire(sid, command, *, actor, target=None):
    from . import upkeep
    with db.write() as conn:
        space = db.space(conn, sid, writable=True)
        link = upkeep._link(conn, sid)
        if command == "run":
            if not link:
                raise SpacesError("not_found", "No upkeep scheduled")
            if target != link["cron_job_id"]:
                raise SpacesError("blocked", "Upkeep link changed before admission", reason="refresh_claim_lost")
        joined = admit(conn, sid, command, actor=actor, target=target)
        if joined is not None:
            return None, joined
        created = command == "refresh" and not (link and link["kind"] == "agent")
        if not created and link is None:
            raise SpacesError("not_found", "No upkeep scheduled")
        jid = "" if created else link["cron_job_id"]
        op = _insert_operation(conn, sid, command, actor, jid)
        conn.execute("INSERT INTO refresh_claims(space,space_created_at,token,cron_job_id,created_one_shot,phase,created_at,"
                     "incarnation,link_generation,command,owner) VALUES(?,?,?,?,?,'pending',?,?,?,?,?)",
                     (sid, space["created_at"], op["token"], jid, int(created), op["created_at"],
                      op["incarnation"], op["link_generation"], command, actor))
        if created:
            conn.execute("INSERT INTO maintenance_effects(id,operation,action,phase,obligation) VALUES(?,?,'pause','possibly_sent','disable')",
                         (op["token"] + ':disable', op["token"]))
        return claim(conn, sid), None


def bind_job(conn, work, jid):
    fence(conn, work, work=True)
    conn.execute("UPDATE refresh_claims SET cron_job_id=? WHERE token=?", (jid, work["token"]))
    conn.execute("UPDATE maintenance_operations SET cron_job_id=? WHERE token=?", (jid, work["token"]))
    conn.execute("UPDATE maintenance_effects SET cron_job_id=? WHERE operation=? AND obligation='disable'", (jid, work["token"]))
    work["cron_job_id"] = jid


def outcome(native, jid=None):
    if not isinstance(native, dict):
        return "unresolved"
    if native.get("success") is False:
        return "refused"
    job = native.get("job")
    if not isinstance(job, dict) or (jid is not None and job.get("job_id") != jid):
        return "unresolved"
    if job.get("executed") is False or job.get("execution_skipped") or job.get("execution_success") is False:
        return "refused"
    if job.get("executed") is True:
        if job.get("execution_success") is True:
            return "completed"
        if job.get("execution_mode") == "background":
            return "background"
    return "unresolved"


def usable_stamp(value):
    from . import upkeep
    try:
        seconds = upkeep._seconds(value)
        return seconds is not None and math.isfinite(seconds)
    except (ValueError, TypeError, OverflowError, OSError):
        return False


def acceptance_baseline(native, jid):
    job = native.get("job") if isinstance(native, dict) else None
    if (outcome(native, jid) == "background" and isinstance(job, dict) and "last_run_at" in job
            and (job["last_run_at"] is None or usable_stamp(job["last_run_at"]))):
        return json.dumps(job["last_run_at"])
    return None


def retire(conn, work, disposition):
    conn.execute("UPDATE maintenance_operations SET phase='retired',outcome=? WHERE token=? AND incarnation=?",
                 (disposition, work["token"], work["incarnation"]))
    conn.execute("DELETE FROM refresh_claims WHERE space=? AND token=? AND incarnation IS ?",
                 (work["space"], work["token"], work["incarnation"]))


def update_work(work, native, *, phase="unresolved", settled=False):
    with db.write() as conn:
        # Receipts belong to their original operation, even when its Space or claim has gone away.
        conn.execute("UPDATE maintenance_operations SET native=? WHERE token=?", (json.dumps(native), work["token"]))
        if work.get("failure"):
            conn.execute("UPDATE maintenance_operations SET error=? WHERE token=?",
                         (json.dumps(work["failure"]), work["token"]))
        for effect in work.get("effects", ()):
            conn.execute("INSERT OR REPLACE INTO maintenance_effects "
                         "(id,operation,action,cron_job_id,phase,native,verification) "
                         "VALUES(:id,:operation,:action,:cron_job_id,:phase,:native,:verification)", effect)
    with db.write() as conn:
        fence(conn, work, work=True)
        baseline = acceptance_baseline(native, work["cron_job_id"])
        phase = "pending" if phase == "pending" else "background" if baseline is not None else "unresolved"
        if settled:
            retire(conn, work, "terminal_reply" if outcome(native, work["cron_job_id"]) in ("completed", "refused") else "abandoned")
        else:
            conn.execute("UPDATE refresh_claims SET native=?,baseline_completion=?,phase=? WHERE token=?",
                         (json.dumps(native), baseline, phase, work["token"]))
            conn.execute("UPDATE maintenance_operations SET phase=?,native=? WHERE token=?",
                         (phase, json.dumps(native), work["token"]))


def disable_done(conn, work):
    conn.execute("UPDATE maintenance_effects SET resolved=1,phase='observed' WHERE operation=? AND obligation='disable'",
                 (work["token"],))


def join(conn, work, *, actor):
    from . import upkeep
    fence(conn, work, work=True)
    native = json.loads(work["native"]) if work["native"] else None
    receipt = operation(conn, work["token"])
    if native is None and receipt and receipt["native"]:
        native = json.loads(receipt["native"])
        baseline = acceptance_baseline(native, work["cron_job_id"])
        work = {**work, "native": receipt["native"], "baseline_completion": baseline,
                "phase": "background" if baseline is not None else "unresolved"}
        conn.execute("UPDATE refresh_claims SET native=?,baseline_completion=?,phase=? WHERE token=?",
                     (work["native"], baseline, work["phase"], work["token"]))
    result = dict(kind="cron", cron_job_id=work["cron_job_id"], dispatch=native, joined=True,
                  refresh_state=work["phase"])
    job = None
    # A run intent can precede dispatch. Only a nonpending claim permits reconciliation.
    reconcile = work["phase"] != "pending"
    if work["created_one_shot"]:
        obligation = conn.execute("SELECT resolved FROM maintenance_effects WHERE operation=? AND obligation='disable'",
                                  (work["token"],)).fetchone()
        if obligation is not None and not obligation["resolved"]:
            result["disable_obligation"] = dict(job_id=work["cron_job_id"], outstanding=True)
    if reconcile:
        try:
            job = next((job for job in upkeep._jobs()["jobs"] if job["job_id"] == work["cron_job_id"]), None)
        except SpacesError as exc:
            result["recovery"] = dict(reason="refresh_outcome_unknown", verification=exc.to_dict(),
                                      message="Use Upkeep Remove before retrying.")
            return result
    terminal = outcome(native, work["cron_job_id"])
    if terminal in ("completed", "refused"):
        try:
            if work["created_one_shot"]:
                with scope(work):
                    marker = _connection.set(conn)
                    try:
                        upkeep._consume_one_shot(work["cron_job_id"], native, actor=actor)
                    finally:
                        _connection.reset(marker)
                disable_done(conn, work)
            retire(conn, work, "terminal_reply")
            return None
        except SpacesError as exc:
            result["recovery"] = dict(reason="refresh_outcome_unknown", cleanup=exc.to_dict(),
                                      message="Use Upkeep Remove before retrying.")
            return result
    if work["created_one_shot"] and reconcile:
        if job is not None and job.get("enabled") is not False:
            try:
                with scope(work):
                    marker = _connection.set(conn)
                    try:
                        upkeep._mutate("pause", work["cron_job_id"], reason=f"Unconfirmed Living Spaces refresh by {actor}")
                    finally:
                        _connection.reset(marker)
                disable_done(conn, work)
                result.pop("disable_obligation", None)
            except SpacesError as exc:
                result["disable_obligation"] = dict(job_id=work["cron_job_id"], error=exc.to_dict())
        elif job is not None:
            disable_done(conn, work)
            result.pop("disable_obligation", None)
    stamp = job.get("last_run_at") if job else None
    if (work["phase"] == "background" and work["baseline_completion"] is not None and usable_stamp(stamp)
            and stamp != json.loads(work["baseline_completion"])
            and job is not None and job.get("last_status") in ("ok", "success", "succeeded", "error", "failed")):
        if work["created_one_shot"]:
            with scope(work):
                marker = _connection.set(conn)
                try:
                    upkeep._consume_one_shot(work["cron_job_id"], native, actor=actor)
                    disable_done(conn, work)
                finally:
                    _connection.reset(marker)
        retire(conn, work, "conditional_terminal_stamp")
        return None
    if work["phase"] != "pending" or db.now() - work["created_at"] >= 120:
        result["recovery"] = dict(reason="refresh_outcome_unknown",
                                  message="Native completion is unconfirmed. Use Upkeep Remove before retrying.")
        if job is None and work["phase"] != "pending":
            result["refresh_state"] = "unresolved"
    return result


def retire_resources(conn, sid, *, jid=None, all_resources=False):
    state = identity(conn, sid)
    held = claim(conn, sid)
    if held and (all_resources or held["cron_job_id"] == jid):
        retire(conn, held, "abandoned")
    if all_resources:
        current = _operation.get()
        conn.execute("UPDATE maintenance_operations SET phase='retired',outcome='abandoned' "
                     "WHERE space=? AND incarnation=? AND phase!='retired' AND token!=?",
                     (sid, state["incarnation"], current["token"] if current else ""))
    conn.execute("UPDATE maintenance_spaces SET link_generation=link_generation+1 WHERE space=?", (sid,))


def _feed_control(conn, sid, command):
    """Select feed controls without reserving native execution ownership."""
    from . import upkeep

    revision = conn.execute("SELECT r.manifest FROM revisions r JOIN spaces s ON s.id=r.space "
                            "AND s.head_rev=r.rev WHERE s.id=?", (sid,)).fetchone()
    if revision is None or (json.loads(revision["manifest"]).get("upkeep") or {}).get("handler") != "feed":
        return None
    link = upkeep._link(conn, sid)
    if link and link["kind"] != "feed":
        return None
    state = identity(conn, sid)
    held = claim(conn, sid)
    if held:
        if (held["incarnation"] != state["incarnation"] or held["link_generation"] != state["link_generation"]
                or held["created_one_shot"]
                or held["command"] != "run" or not link or held["cron_job_id"] != link["cron_job_id"]):
            return None
        receipt = operation(conn, held["token"])
        if receipt is None:
            return None
        try:
            for value in (held["native"], receipt["native"]):
                if value is not None:
                    native = json.loads(value)
                    job = native.get("job") if isinstance(native, dict) else None
                    if not isinstance(job, dict) or job.get("job_id") != link["cron_job_id"] or job.get("no_agent") is not True:
                        return None
        except (TypeError, ValueError):
            return None
    active = conn.execute("SELECT token FROM maintenance_operations WHERE space=? AND incarnation=? AND phase!='retired'",
                          (sid, state["incarnation"])).fetchall()
    if any(row["token"] != (held["token"] if held else None) for row in active):
        return None
    jobs = upkeep._owned_jobs(sid, link, upkeep._jobs()["jobs"], claim=held)
    if any(job.get("no_agent") is not True or job.get("name") == upkeep._once_name(sid) for job in jobs):
        return None
    if command in ("schedule", "run", "resume"):
        rows = conn.execute("SELECT id FROM runs WHERE space=? AND status IN ('queued','running')", (sid,)).fetchall()
        if rows:
            _block([], feeds=[row["id"] for row in rows])
        unlinked = [job["job_id"] for job in jobs if not link or job["job_id"] != link["cron_job_id"]]
        if unlinked:
            _block(unlinked)
    return dict(state, command=command, cron_job_id=link["cron_job_id"] if link else None)


def bind_feed(conn, sid, run_id, op):
    conn.execute("INSERT INTO maintenance_feeds(run,incarnation,operation) VALUES(?,?,?)",
                 (run_id, identity(conn, sid)["incarnation"], op))


def feed_is_current(conn, run_id):
    return conn.execute("SELECT 1 FROM runs r JOIN maintenance_feeds f ON f.run=r.id "
                        "JOIN maintenance_spaces m ON m.space=r.space AND m.incarnation=f.incarnation "
                        "WHERE r.id=?", (run_id,)).fetchone() is not None


@contextmanager
def feed_writes(run_id):
    with db.read() as conn:
        row = conn.execute("SELECT r.space,f.incarnation FROM runs r JOIN maintenance_feeds f ON f.run=r.id "
                           "WHERE r.id=?", (run_id,)).fetchone()
    if row is None:
        raise SpacesError("blocked", "This feed run was removed", reason="feed_canceled")
    marker = _feed_writer.set(dict(row, run=run_id))
    try:
        yield
    finally:
        _feed_writer.reset(marker)


def fence_feed_write(conn):
    expected = _feed_writer.get()
    if expected is None:
        return
    row = conn.execute("SELECT r.status,r.detail,s.status AS lifecycle,m.incarnation FROM runs r "
                       "JOIN spaces s ON s.id=r.space JOIN maintenance_spaces m ON m.space=s.id "
                       "WHERE r.id=? AND r.space=?", (expected["run"], expected["space"])).fetchone()
    if (row is None or row["incarnation"] != expected["incarnation"] or row["lifecycle"] == "archived"
            or row["status"] != "running" or json.loads(row["detail"]).get("cancel_reason")):
        raise SpacesError("blocked", "This feed run no longer owns Space writes", reason="feed_canceled")
