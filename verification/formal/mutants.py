"""Negative controls: each mutant breaks one property in a scratch copy of the real code.

A mutant is a list of (file under src/living-spaces/living_spaces_core, exact old text, new text). The old text
must occur exactly once; if it does not, the code drifted and the mutant needs updating, which run.py reports.
`expect` is the property name the check must print in its VIOLATION line.
"""

MUTANTS = {
    "refresh-a-paused-run-reported-ok": {
        "check": "refresh_one_shot", "expect": "NoSuccessForSkipped",
        "signatures": ["NoSuccessForSkipped: start=fresh, run outcome=inline_ok, during run=nothing, post-run DB failure=False, no cron refusals.", "Executions: []"],
        "why": "(a) the born-paused one-shot is run without resuming it, and the skip is not refused",
        "edits": [("upkeep.py", '                if created:\n                    _mutate("resume", jid)\n', "                pass\n"),
                  ("upkeep.py", 'if command == "refresh" and _refresh_outcome(native) == "refused":', "if False:")]},
    "refresh-b-manual-run-not-consumed": {
        "check": "refresh_one_shot", "expect": "AtMostOnce",
        "why": "(b) after a manual inline run the once slot stays pending and the scheduler fires it again",
        "edits": [("upkeep.py", 'if created and outcome in ("completed", "background"):', 'if created and outcome == "background":')]},
    "refresh-c-background-not-consumed": {
        "check": "refresh_one_shot", "expect": "AtMostOnce",
        "why": "(c) a background run leaves its one-shot enabled",
        "edits": [("upkeep.py", 'if created and outcome in ("completed", "background"):', 'if created and outcome == "completed":')]},
    "refresh-c-post-run-error-not-cleaned": {
        "check": "refresh_one_shot", "expect": "AtMostOnce",
        "why": "(c) an error after dispatch (DB failure after db.write(), verification) leaves the one-shot due",
        "edits": [("upkeep.py", "if created and jid and not stale and not creation_cleanup_failed:",
                   "if created and jid and not stale and not creation_cleanup_failed and not dispatched:")]},
    "refresh-d-one-shot-due-at-create": {
        "check": "refresh_one_shot", "expect": "NoFalseRefusal",
        "why": "due-slot analogue of (d): scheduler fires before the manual request; not dispatch-limit retirement mid-run",
        "edits": [("upkeep.py", 'ONE_SHOT_SLOT = "in 7d"', 'ONE_SHOT_SLOT = "in 1m"')]},
    "records-stale-base-rev-accepted": {
        "check": "records_integrity", "expect": "Conflict:",
        "signatures": ["numeric stale base_rev=1 at current rev=2 returned ok, expected conflict"],
        "why": "lost update: a write with an older base_rev is accepted",
        "edits": [("records.py", '(row is not None and base_rev != row["rev"])',
                   '(row is not None and base_rev is not None and base_rev > row["rev"])')]},
    "records-source-overwrites-user-data": {
        "check": "records_integrity", "expect": "UserOwned:",
        "why": "a source upsert writes into user-owned data",
        "edits": [("records.py", '"UPDATE records SET source=?,source_meta=?,rev=?', '"UPDATE records SET data=?,source_meta=?,rev=?')]},
    "records-update-ignores-space": {
        "check": "records_integrity", "expect": "Isolation:",
        "why": "a user update writes matching records in other Spaces too",
        "edits": [("records.py", '"UPDATE records SET data=?,rev=?,updated_at=?,updated_by=? WHERE space=? AND collection=? AND id=?"',
                   "\"UPDATE records SET data=?,rev=?,updated_at=?,updated_by=? WHERE space<>'~'||? AND collection=? AND id=?\"")]},
    "records-rev-restarts-after-delete": {
        "check": "records_integrity", "expect": "RevMonotonic:",
        "why": "a re-created record reuses revs from before its delete",
        "edits": [("records.py", '"SELECT coalesce(max(rev),0)+1 FROM changes WHERE space=? AND collection=? AND record_id=?"',
                   '"SELECT coalesce(max(rev),0)+1 FROM records WHERE space=? AND collection=? AND id=?"')]},
    "records-batch-partial-commit": {
        "check": "records_integrity", "expect": "BatchAtomic:",
        "signatures": ["returned ok, the model expects conflict"],
        "why": "a batch with a failing operation commits the others",
        "edits": [("records.py", '            raise SpacesError(exc.code, exc.message, **{**exc.extra, "op_index": index}) from exc',
                   "            results.append(None)")]},
    "bridge-session-not-bound-to-space": {
        "check": "bridge_authority", "expect": "Authority",
        "why": "a session opened for one Space is accepted for another",
        "edits": [("sessions.py", '"SELECT * FROM sessions WHERE id=? AND space=? AND closed_at IS NULL"',
                   "\"SELECT * FROM sessions WHERE id=? AND space<>'~'||? AND closed_at IS NULL\"")]},
    "bridge-closed-session-accepted": {
        "check": "bridge_authority", "expect": "Authority",
        "why": "a closed session keeps working",
        "edits": [("sessions.py", '"SELECT * FROM sessions WHERE id=? AND space=? AND closed_at IS NULL"',
                   '"SELECT * FROM sessions WHERE id=? AND space=?"')]},
    "bridge-grant-not-checked-for-reads": {
        "check": "bridge_authority", "expect": "Authority",
        "why": "reads skip the capability check before and after the call",
        "edits": [("bridge.py", "            if capability:\n                grants.check(sid, capability)\n            if request_id is not None:",
                   "            if request_id is not None:"),
                  ("bridge.py", "    if invocation.capability:\n        grants.check(invocation.sid, invocation.capability)\n", "")]},
    "delete-keeps-change-log": {
        "check": "delete_residue", "expect": "Gone",
        "why": "delete_space leaves the change log, which the next Space with the same name inherits",
        "edits": [("projects.py", 'for table in ("changes", "recovery_points", "audit", "sessions", "runs", "logs"):',
                   'for table in ("recovery_points", "audit", "sessions", "runs", "logs"):')]},
    "delete-keeps-sessions": {
        "check": "delete_residue", "expect": "Gone",
        "why": "delete_space leaves frame sessions bound to the reused id",
        "edits": [("projects.py", 'for table in ("changes", "recovery_points", "audit", "sessions", "runs", "logs"):',
                   'for table in ("changes", "recovery_points", "audit", "runs", "logs"):')]},
    "net-plain-http-port-allowed": {
        "check": "net_boundary", "expect": "PortAllowlist",
        "why": "port 80 is passed to the transport factory",
        "edits": [("net.py", "    if port not in (443, 8443):", "    if port not in (443, 8443, 80):")]},
    "net-only-last-dns-answer-vetted": {
        "check": "net_boundary", "expect": "VettedIpArgument",
        "why": "one DNS answer is vetted while another is passed to the transport factory",
        "edits": [("net.py", "    if any(not _public(ip) for ip in addresses):", "    if not _public(addresses[-1]):")]},
    "net-credentials-follow-redirect": {
        "check": "net_boundary", "expect": "CredentialsStay",
        "why": "Authorization and Cookie are kept on a redirect to another host",
        "edits": [("net.py", "                    if _target(url)[:2] != (host, port):", "                    if False:")]},
    "inspect-write-served": {
        "check": "inspection_readonly", "expect": "Refused", "requires": "inspection.py",
        "why": "data.put is not refused during inspection",
        "edits": [("inspection.py", '        "data.put": "Inspection is read-only: records are not changed",\n', "")]},
    "inspect-grants-ignored": {
        "check": "inspection_readonly", "expect": "SameAsLive", "requires": "inspection.py",
        "why": "the passive adapter serves reads the Space has no grant for",
        "edits": [("inspection.py", "        if capability and capability not in self.snap.granted:", "        if False:")]},
    "inspect-not-a-snapshot": {
        "check": "inspection_readonly", "expect": "Snapshot", "requires": "inspection.py",
        "why": "no read transaction is held, so later writes leak into the inspection",
        "edits": [("inspection.py", '        conn.execute("BEGIN")\n        conn.execute("SELECT count(*) FROM spaces").fetchone()', "        pass")]},
    "inspect-order-differs": {
        "check": "inspection_readonly", "expect": "SameAsLive", "requires": "inspection.py",
        "why": "the adapter sorts descending orders the wrong way",
        "edits": [("inspection.py", 'keyed.sort(key=lambda pair: pair[0], reverse=bool(order and order.startswith("-")))',
                   'keyed.sort(key=lambda pair: pair[0], reverse=bool(order and not order.startswith("-")))')]},
    "refresh-consumption-leaves-enabled-job": {
        "check": "refresh_one_shot", "expect": "NoLeftoverOneShot",
        "why": "the inline return leaves its one-shot enabled",
        "edits": [("upkeep.py", 'if created and outcome in ("completed", "background"):', 'if created and outcome == "background":')]},
    "refresh-success-falsely-refused": {
        "check": "refresh_one_shot", "expect": "NoFalseRefusal",
        "why": "background execution is refused because its reply lacks a completion field",
        "edits": [("maintenance.py", 'or job.get("execution_success") is False:', 'or job.get("execution_success") is not True:')]},
    "refresh-each-request-runs-twice": {
        "check": "refresh_concurrency", "expect": "OneRunAtATime",
        "why": "the admitted request dispatches twice, so overlapping requests start more than one run",
        "edits": [("upkeep.py", "            native = _run_now(sid, jid, claim=claim, on_reply=lambda reply: _update_refresh_claim(claim, reply))\n",
                   "            _run_now(sid, jid, claim=claim)\n"
                   "            native = _run_now(sid, jid, claim=claim, on_reply=lambda reply: _update_refresh_claim(claim, reply))\n")]},
    "refresh-worker-crashes": {
        "check": "refresh_concurrency", "expect": "ProbeCompleted",
        "why": "thread exceptions must fail the probe rather than look like a single run",
        "edits": [("runs.py", '    if trigger not in ("manual", "schedule", "chat"):',
                   '    raise RuntimeError("broken refresh entry")\n    if trigger not in ("manual", "schedule", "chat"):')]},
    "records-change-cursor-reversed": {
        "check": "records_integrity", "expect": "Cursor:",
        "why": "the changes cursor returns descending sequence numbers",
        "edits": [("records.py", 'WHERE space=? AND seq>? ORDER BY seq LIMIT ?', 'WHERE space=? AND seq>? ORDER BY seq DESC LIMIT ?')]},
    "bridge-refusal-writes-data": {
        "check": "bridge_authority", "expect": "NoEffect",
        "why": "a denied operation changes records before checking its grant",
        "edits": [("bridge.py", '            if capability:\n                grants.check(sid, capability)\n            if request_id is not None:',
                   '            if capability:\n                with db.write() as conn:\n                    conn.execute("UPDATE records SET data=\'{}\' WHERE space=?", (sid,))\n                grants.check(sid, capability)\n            if request_id is not None:')]},
    "bridge-authorized-operations-all-refused": {
        "check": "bridge_authority", "expect": "Authority",
        "why": "valid operations must succeed, not merely avoid authorization errors",
        "edits": [("bridge.py", 'def _call(sid, session, op, args):',
                   'def _call(sid, session, op, args):\n    raise SpacesError("invalid", "broken dispatcher")')]},
    "delete-clears-other-spaces-history": {
        "check": "delete_residue", "expect": "Untouched",
        "why": "history cleanup loses the Space predicate",
        "edits": [("projects.py", 'conn.execute(f"DELETE FROM {table} WHERE space=?", (sid,))',
                   'conn.execute(f"DELETE FROM {table} WHERE space<>\'~\'||?", (sid,))')]},
    "create-without-files-is-not-empty": {
        "check": "delete_residue", "expect": "Fresh",
        "why": "a recreated empty Space unexpectedly contains a record",
        "edits": [("projects.py", '        report = _diagnose(conn, normalized, stored, found)\n    return {**get_space(sid), **report}',
                   '        report = _diagnose(conn, normalized, stored, found)\n    if files is None:\n        records.put(sid, "old", "ghost", {"stale": True}, actor="user")\n    return {**get_space(sid), **report}')]},
    "net-unresolved-address-passed": {
        "check": "net_boundary", "expect": "ResolvedIpArgument",
        "why": "the transport receives a different public IP than the validated resolver answer",
        "edits": [("net.py", 'conn = _connection(host, port, ip, _remaining(deadline))',
                   'conn = _connection(host, port, "9.9.9.9", _remaining(deadline))')]},
    "inspect-commits-a-write": {
        "check": "inspection_readonly", "expect": "ReadOnly", "requires": "inspection.py",
        "why": "the adapter opens a separate writable connection and changes metadata while serving a read",
        "edits": [("inspection.py", '        conn, sid = self.snap.conn, self.snap.sid',
                   '        conn, sid = self.snap.conn, self.snap.sid\n        with sqlite3.connect(db.db_path()) as unsafe:\n            unsafe.execute("UPDATE spaces SET name=name || \'changed\' WHERE id=?", (sid,))')]},
    "refresh-consume-refusal-is-not-F1": {
        "check": "refresh_one_shot", "expect": "NoFalseRefusal",
        "why": "a consume-phase remove refusal surfaced as native_refused after a successful run must fail (17 = 7 nothing + 1 archive + 1 delete + 1 remove + 7 pause)",
        "signatures": ["VIOLATION: 17 scenario(s) broke a property.", "NoFalseRefusal: start=fresh, run outcome=inline_ok", "Hermes cron remove refused: injected remove refusal #1"],
        "edits": [("upkeep.py", '            return {"job_id": jid, "consumed": "paused", "cleanup": cleanup.to_dict()}',
                   '            raise SpacesError(cleanup.code, cleanup.message, **{**cleanup.extra, "native": native})')]},
    "refresh-verify-refusal-reported-as-refused": {
        "check": "refresh_one_shot", "expect": "NoFalseRefusal",
        "why": "F1 regression: a refused post-run verification list is reported as native_refused again",
        "edits": [("upkeep.py", 'raise SpacesError("blocked", verification.message, reason="post_run_check_failed", native=native,',
                   'raise SpacesError("blocked", verification.message, reason="native_refused", native=native,')]},
    "delete-leaves-live-maintenance-history": {
        "check": "delete_residue", "expect": "Gone",
        "why": "the retained maintenance_operations row of the delete itself is left unretired",
        "edits": [("maintenance.py", "UPDATE maintenance_operations SET phase='retired',outcome='applied' WHERE token=?",
                   "UPDATE maintenance_operations SET phase='applied',outcome='applied' WHERE token=?")]},
    "recreate-reuses-incarnation": {
        "check": "delete_residue", "expect": "Fresh",
        "why": "a Space re-created with the same id gets the deleted Space's maintenance incarnation",
        "edits": [("maintenance.py", 'conn.execute("INSERT INTO maintenance_spaces(space,incarnation) VALUES(?,?)", (sid, uuid.uuid4().hex))',
                   'conn.execute("INSERT INTO maintenance_spaces(space,incarnation) VALUES(?,?)", (sid, sid))')]},
    "delete-keeps-unique-blobs": {
        "check": "delete_residue", "expect": "Blobs",
        "why": "F2 regression: delete_space keeps file contents only the deleted Space referenced",
        "edits": [("projects.py", '        conn.execute("""DELETE FROM blobs WHERE sha IN (', '        conn.execute("""SELECT 1 FROM blobs WHERE sha IN (')]},
    "inspect-F5-redaction-change-noticed": {
        "check": "inspection_readonly", "expect": "KnownFindingDrift", "requires": "inspection.py",
        "why": "fixing (or changing) the live not_granted redaction must change the pinned F4/F5 case set",
        "edits": [("bridge.py", "        return _failure(authority, invocation.effect, authorized=False)",
                   "        return _failure(authority, invocation.effect)")]},
    "inspect-F5-wrong-adapter-error-not-excused": {
        "check": "inspection_readonly", "expect": "SameAsLive", "requires": "inspection.py",
        "why": "a wrong not_granted message or capability from PassiveAdapter must not pass as the known F5 difference",
        "edits": [("inspection.py",
                   '            raise SpacesError("not_granted", "Capability or requested scope is not granted", capability=capability)',
                   '            raise SpacesError("not_granted", "WRONG MESSAGE", capability="WRONG CAPABILITY")')]},
}
