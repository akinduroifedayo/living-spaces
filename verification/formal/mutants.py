"""Negative controls: each mutant breaks one property in a scratch copy of the real code.

A mutant is a list of (file under src/living-spaces/living_spaces_core, exact old text, new text). The old text
must occur exactly once; if it does not, the code drifted and the mutant needs updating, which run.py reports.
`expect` is the property name the check must print in its VIOLATION line.
"""

MUTANTS = {
    # Refresh now: the historical defects (a)-(d), put back into upkeep.py.
    "refresh-a-paused-run-reported-ok": {
        "check": "refresh_one_shot", "expect": "NoSuccessForSkipped",
        "why": "(a) the born-paused one-shot is run without resuming it, and the skip is not refused",
        "edits": [("upkeep.py", '        if created:\n            _mutate("resume", jid)\n', "        pass\n"),
                  ("upkeep.py", '(job.get("executed") is False\n                                      or job.get("execution_skipped")\n'
                                '                                      or job.get("execution_success") is False)', "False")]},
    "refresh-b-manual-run-not-consumed": {
        "check": "refresh_one_shot", "expect": "AtMostOnce",
        "why": "(b) after a manual inline run the once slot stays pending and the scheduler fires it again",
        "edits": [("upkeep.py", '                result["one_shot"] = _consume_one_shot(jid, native, actor=actor)\n', "                pass\n")]},
    "refresh-c-background-not-consumed": {
        "check": "refresh_one_shot", "expect": "AtMostOnce",
        "why": "(c) a background run leaves its one-shot enabled",
        "edits": [("upkeep.py", 'result["one_shot"] = _consume_one_shot(jid, native, actor=actor, background=True)', "pass")]},
    "refresh-c-post-run-error-not-cleaned": {
        "check": "refresh_one_shot", "expect": "AtMostOnce",
        "why": "(c) an error after dispatch (DB failure after db.write(), verification) leaves the one-shot due",
        "edits": [("upkeep.py", "    except SpacesError as failure:\n        if created:\n            pause_failure = None\n"
                                '            try:\n                _mutate("pause", jid, reason=f"Living Spaces refresh by {actor} failed")',
                   "    except SpacesError as failure:\n        if created and not dispatched:\n            pause_failure = None\n"
                   '            try:\n                _mutate("pause", jid, reason=f"Living Spaces refresh by {actor} failed")')]},
    "refresh-d-one-shot-due-at-create": {
        "check": "refresh_one_shot", "expect": "NoFalseRefusal",
        "why": "(d) a born-paused one-shot created already due is retired by the scheduler and the success reported as refused",
        "edits": [("upkeep.py", 'ONE_SHOT_SLOT = "in 7d"', 'ONE_SHOT_SLOT = "in 1m"')]},
    # Records.
    "records-stale-base-rev-accepted": {
        "check": "records_integrity", "expect": "the model expects conflict",
        "why": "lost update: a write with an older base_rev is accepted",
        "edits": [("records.py", '(row is not None and base_rev != row["rev"])',
                   '(row is not None and base_rev is not None and base_rev > row["rev"])')]},
    "records-source-overwrites-user-data": {
        "check": "records_integrity", "expect": "differ from the model",
        "why": "a source upsert writes into user-owned data",
        "edits": [("records.py", '"UPDATE records SET source=?,source_meta=?,rev=?', '"UPDATE records SET data=?,source_meta=?,rev=?')]},
    "records-row-lookup-ignores-space": {
        "check": "records_integrity", "expect": "the model expects",
        "why": "a record lookup is not scoped to its Space",
        "edits": [("records.py", '"SELECT * FROM records WHERE space=? AND collection=? AND id=?"',
                   "\"SELECT * FROM records WHERE space<>'~'||? AND collection=? AND id=?\"")]},
    "records-rev-restarts-after-delete": {
        "check": "records_integrity", "expect": "differ from the model",
        "why": "a re-created record reuses revs from before its delete",
        "edits": [("records.py", '"SELECT coalesce(max(rev),0)+1 FROM changes WHERE space=? AND collection=? AND record_id=?"',
                   '"SELECT coalesce(max(rev),0)+1 FROM records WHERE space=? AND collection=? AND id=?"')]},
    "records-batch-partial-commit": {
        "check": "records_integrity", "expect": "the model expects",
        "why": "a batch with a failing operation commits the others",
        "edits": [("records.py", '            raise SpacesError(exc.code, exc.message, **{**exc.extra, "op_index": index}) from exc',
                   "            results.append(None)")]},
    # Bridge authority.
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
        "edits": [("bridge.py", "        if capability:\n            grants.check(sid, capability)\n        limits.object_json(args)",
                   "        limits.object_json(args)"),
                  ("bridge.py", "        sessions.require(sid, session)\n        if capability:\n            grants.check(sid, capability)\n"
                                '        return {"ok": True',
                   '        sessions.require(sid, session)\n        return {"ok": True')]},
    # Delete.
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
    # Internet boundary.
    "net-plain-http-port-allowed": {
        "check": "net_boundary", "expect": "HttpsOnly",
        "why": "port 80 is accepted for the pinned TLS connection",
        "edits": [("net.py", "    if port not in (443, 8443):", "    if port not in (443, 8443, 80):")]},
    "net-only-last-dns-answer-vetted": {
        "check": "net_boundary", "expect": "NoPrivateConnect",
        "why": "DNS rebinding: one answer is vetted while another is connected to",
        "edits": [("net.py", "    if any(not _public(ip) for ip in addresses):", "    if not _public(addresses[-1]):")]},
    "net-credentials-follow-redirect": {
        "check": "net_boundary", "expect": "CredentialsStay",
        "why": "Authorization and Cookie are kept on a redirect to another host",
        "edits": [("net.py", "                    if _target(url)[:2] != (host, port):", "                    if False:")]},
    # Runtime inspection (only on trees that have inspection.py; first in candidate 8008dcc).
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
}
