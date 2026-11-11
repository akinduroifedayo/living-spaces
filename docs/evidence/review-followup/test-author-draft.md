# R01/R02 regression authorship

Ife wants normal Hermes chat to build safe durable Spaces with consent users can trust.

**NOT RUN.** No product code, tests, probes, network, native cron, models, or nested agents were executed. The supported workspace preflight and read-only source/AST inspection were the only verification performed.

## Placement clarification pending

The tracked file remains byte-for-byte unchanged, with **27 existing test methods**. Eight methods are drafted below. Inserting them inside the existing `ReviewCustomizationTests` class would give **35 methods**, without subclassing or rerunning inherited cases.

The original file ends with this module-level suffix:

```python
if __name__ == "__main__":
    unittest.main()
```

Consequently, a literal append preserving the **entire original file as a byte prefix** cannot add ordinary method definitions inside the preceding class. I requested permission to insert the eight definitions immediately before the unchanged guard. That preserves every existing byte in order and all existing method bodies, but it does not preserve the entire old file as a literal prefix. No answer has arrived. This is a structural scope conflict, not a product instrumentation gap. No dynamic method attachment, class replacement, subclass, or fixture rewrite has been substituted.

The complete proposed insertion is retained below for review. It is **not applied** to the test file.

## Exact new names and controls

| Proposed method | Contract and control |
| --- | --- |
| `test_r01_missing_upkeep_snapshot_refuses_agent_and_feed_rest_approval` | Agent/feed subtests have valid exact Refresh approval and all four requested schedule fields. Omitting only upkeep must return HTTP 400/invalid, preserve the request, and create no native job. |
| `test_r01_matching_upkeep_and_schedule_approve_one_native_job_control` | Both handlers approve matching snapshots through real REST. Exactly one new synthetic native job retains cadence, timezone and handler/task identity; upkeep and Refresh scope remain unchanged. |
| `test_r01_denial_needs_neither_snapshot_and_creates_no_job_control` | Both handlers deny through REST with neither snapshot. Schedule is disabled without native creation. |
| `test_r02_unavailable_adapter_revoke_without_pending_runs_succeeds_at_rest` | With zero local pending runs, only the adapter loader raises ImportError. Non-raising TestClient exposes HTTP 500 as an assertion failure. Revoke must return revoked, persist inactive state before any reconciling getter, expose unavailability, and leave native leaves unchanged without a false pause acknowledgement. |
| `test_r02_restored_adapter_interrupts_native_job_before_refresh_regrant` | Adapter failure is scoped to revoke, then restored. Observational wrappers delegate to the existing synthetic pause/remove leaves and record committed Refresh state after interruption. The native job must become paused or absent while Refresh is still revoked. Regrant must leave an inactive schedule and never create, resume, or trigger a job. |
| `test_r02_unavailable_adapter_keeps_refresh_regrant_fail_closed` | Adapter remains unavailable for revoke and regrant. Regrant must raise a typed SpacesError and retain revoked Refresh, inactive scheduling, visible unavailability, and unchanged synthetic job state/calls. |
| `test_r02_unavailable_adapter_preserves_pending_run_uncertainty_and_gates_regrant` | Claimed/queued and running subtests import actual synthetic ledger entries through real core into SQLite before failure. Revoke must persist inactive state and revoked Refresh without falsely canceling the local run; error/detail or schedule reason must expose uncertainty. Regrant remains gated and native state/calls remain unchanged. |
| `test_r02_working_adapter_revoke_and_regrant_preserve_unrelated_state_control` | Ordinary REST revoke pauses the existing target native job, cancels its running execution, and preserves completed history, user records, and another Space's native job/execution, local history, schedule and grant. Ordinary regrant does not resume. Explicit Resume is the positive control. |

No product mechanism is prescribed. Assertions accept existing inactive schedule states and either pause or removal for recovery. Native operation counts are not fixed except the commissioned exactly-one creation control. Leaf wrappers observe and delegate; they do not fabricate successful native operations or replace product revoke/regrant/cancellation behavior.

## Input and static verification

- Read `.run/packet/pins.json` first, then all twenty-eight complete shards. Truncated combined displays were reread in bounded batches.
- Read the complete requested model policy, Poteto skill, Hermes tools reference and gated-program-delegation reference.
- Verified branch `forge/r1-c-tests-followup` and HEAD `302320b78dfe2b40b44eae2657bd5165fd03d8ae`, with an initially clean tracked tree.
- Ran the supported preflight before the first write. The first invocation exited zero but its tool output was truncated, preventing JSON parsing. Repeated the identical command with sufficient output capacity. The full JSON parsed as `status: verified`, with 423 baseline files.
- Preflight command: `python3 /Users/ifedayoakinduro/.hermes/skills/pstack/hermes-local/native-preflight.py --workspace /Volumes/Expansion/Development/Projects/living-spaces-wt/c-tests-followup --parent /Volumes/Expansion/Development/Projects/living-spaces --manifest .run/baseline.json`.
- The preflight is observation, not an OS sandbox or future-state guarantee.
- Read-only AST parsing of the proposed in-memory insertion succeeded. It contains exactly eight new test methods in the existing class, giving 35 total. All 27 existing test bodies and existing helper bodies compare equal by AST. This is syntax/scope inspection, not test execution.
- No relevant local memory hit. No network-backed GBrain lookup was made under the explicit no-network commission.
- Parent owns stock execution, classification of red events, freezing all 35 bodies, and any subsequent repair commission. This draft does not establish behavioral red or green, release readiness, cross-family review, native qualification, real cancellation, or passing execution.
- Requested model/effort/tier attribution remains parent-owned. No model launch or fallback was attempted here.

## Proposed insertion, NOT APPLIED and NOT RUN

Insert this text immediately before the final blank lines and module-level main guard only if the requested placement clarification is authorized.

```python

    def test_r01_missing_upkeep_snapshot_refuses_agent_and_feed_rest_approval(self):
        fx = self.fx
        client = fx.client()
        for handler in ("agent", "feed"):
            with self.subTest(handler=handler):
                sid = fx.make(handler=handler)
                grant = fx.refresh_grant(sid)
                self.assertEqual(grant["status"], "granted")
                self.assertEqual(grant["scope"], grant["requested_scope"])
                if handler == "agent":
                    self.assertEqual(grant["scope"]["upkeep"],
                                     {"handler": "agent", "prompt": AGENT_PROMPT})
                displayed = fx.schedules.request_schedule(
                    sid, cadence="0 7 1 * *", timezone="UTC",
                    purpose="Monthly approved task", actor="agent:review")
                snapshot = {key: displayed[key] for key in SCHEDULE_FIELDS}
                jobs_before = copy.deepcopy(fx.cron.jobs)
                calls_before = list(fx.cron.calls)
                response = client.post(f"/spaces/{sid}/schedule", json={
                    "decision": "approve", "requested_schedule": snapshot,
                })
                with self.subTest(boundary="missing upkeep rejected at REST"):
                    self.assertEqual(response.status_code, 400, response.text)
                    self.assertEqual(response.json()["error"]["code"], "invalid")
                with self.subTest(boundary="no native creation"):
                    self.assertEqual(fx.cron.calls, calls_before)
                    self.assertEqual(fx.cron.jobs, jobs_before)
                with self.subTest(boundary="request remains unapproved"):
                    with fx.db.read() as conn:
                        stored = dict(conn.execute(
                            "SELECT * FROM schedules WHERE space=?", (sid,)).fetchone())
                    self.assertEqual(stored["status"], "requested")
                    self.assertIsNone(stored["cron_job_id"])
                    self.assertEqual({key: stored[key] for key in SCHEDULE_FIELDS}, snapshot)

    def test_r01_matching_upkeep_and_schedule_approve_one_native_job_control(self):
        fx = self.fx
        client = fx.client()
        for handler in ("agent", "feed"):
            with self.subTest(handler=handler):
                sid = fx.make(handler=handler)
                upkeep = copy.deepcopy(fx.projects.bundle(sid)["manifest"]["upkeep"])
                grant = copy.deepcopy(fx.refresh_grant(sid))
                displayed = fx.schedules.request_schedule(
                    sid, cadence="0 7 1 * *", timezone="Pacific/Auckland",
                    purpose="Monthly displayed task", actor="agent:review")
                snapshot = {key: displayed[key] for key in SCHEDULE_FIELDS}
                jobs_before = set(fx.cron.jobs)
                call_start = len(fx.cron.calls)
                response = client.post(f"/spaces/{sid}/schedule", json={
                    "decision": "approve", "requested_upkeep": upkeep,
                    "requested_schedule": snapshot,
                })
                self.assertEqual(response.status_code, 200, response.text)
                approved = response.json()
                self.assertEqual(approved["status"], "active")
                self.assertEqual({key: approved[key] for key in SCHEDULE_FIELDS}, snapshot)
                jid = approved["cron_job_id"]
                self.assertEqual(set(fx.cron.jobs) - jobs_before, {jid})
                self.assertEqual([call for call in fx.cron.calls[call_start:]
                                  if call[0] == "create"], [("create", jid)])
                job = fx.cron.jobs[jid]
                self.assertTrue(job["enabled"])
                self.assertEqual((job["schedule"], job["timezone"]),
                                 (snapshot["cadence"], snapshot["timezone"]))
                self.assertEqual(job["no_agent"], handler == "feed")
                if handler == "agent":
                    self.assertTrue(job["prompt"].endswith("Upkeep task:\n" + upkeep["prompt"]))
                else:
                    self.assertEqual(job["script"], f"living-spaces-refresh-{sid}.py")
                self.assertEqual(fx.projects.bundle(sid)["manifest"]["upkeep"], upkeep)
                self.assertEqual(fx.refresh_grant(sid), grant)
                self.assertEqual({key: fx.schedules.get_schedule(sid)[key]
                                  for key in SCHEDULE_FIELDS}, snapshot)

    def test_r01_denial_needs_neither_snapshot_and_creates_no_job_control(self):
        fx = self.fx
        client = fx.client()
        for handler in ("agent", "feed"):
            with self.subTest(handler=handler):
                sid = fx.make(handler=handler)
                displayed = fx.schedules.request_schedule(
                    sid, cadence="0 7 1 * *", timezone="UTC",
                    purpose="Optional monthly upkeep", actor="agent:review")
                jobs_before = copy.deepcopy(fx.cron.jobs)
                calls_before = list(fx.cron.calls)
                response = client.post(f"/spaces/{sid}/schedule", json={"decision": "deny"})
                self.assertEqual(response.status_code, 200, response.text)
                denied = response.json()
                self.assertEqual(denied["status"], "disabled")
                self.assertIsNone(denied["cron_job_id"])
                self.assertIsNone(denied["next_run_at"])
                self.assertEqual({key: denied[key] for key in SCHEDULE_FIELDS},
                                 {key: displayed[key] for key in SCHEDULE_FIELDS})
                self.assertEqual(fx.schedules.get_schedule(sid)["status"], "disabled")
                self.assertEqual(fx.cron.jobs, jobs_before)
                self.assertEqual(fx.cron.calls, calls_before)

    def test_r02_unavailable_adapter_revoke_without_pending_runs_succeeds_at_rest(self):
        from fastapi.testclient import TestClient

        fx = self.fx
        sid = fx.make()
        jid = fx.approve_schedule(sid)["cron_job_id"]
        client = self.stack.enter_context(TestClient(fx.client().app, raise_server_exceptions=False))
        with fx.db.read() as conn:
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM runs WHERE space=? AND status IN ('queued','running')",
                (sid,)).fetchone()[0], 0)
        self.assertTrue(fx.cron.jobs[jid]["enabled"])
        jobs_before = copy.deepcopy(fx.cron.jobs)
        calls_before = list(fx.cron.calls)
        with patch.object(fx.schedules, "_cron", side_effect=ImportError("native adapter unavailable")):
            response = client.post(f"/spaces/{sid}/grants/refresh", json={"decision": "revoke"})
            with fx.db.read() as conn:
                stored = dict(conn.execute(
                    "SELECT * FROM schedules WHERE space=?", (sid,)).fetchone())
            visible = fx.schedules._schedule_row(sid)
            with self.subTest(boundary="REST revoke succeeds"):
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["status"], "revoked")
            with self.subTest(boundary="Refresh durably revoked"):
                self.assertEqual(fx.refresh_grant(sid)["status"], "revoked")
            with self.subTest(boundary="inactive before any reconciling read"):
                self.assertIn(stored["status"], ("disabled", "paused", "requested"))
                self.assertIsNone(stored["next_run_at"])
            with self.subTest(boundary="unconfirmed native interruption is visible"):
                self.assertIn("unavailable", (visible.get("reason") or "").lower())
            with self.subTest(boundary="no fabricated native acknowledgement"):
                self.assertEqual(fx.cron.calls, calls_before)
                self.assertEqual(fx.cron.jobs, jobs_before)
                for event in fx.grants.audit_log(sid):
                    if event["action"] == "schedule.paused" and event["outcome"] == "paused":
                        self.assertIn("unavailable", json.dumps(event["detail"]).lower())

    def test_r02_restored_adapter_interrupts_native_job_before_refresh_regrant(self):
        from fastapi.testclient import TestClient

        fx = self.fx
        sid = fx.make()
        jid = fx.approve_schedule(sid)["cron_job_id"]
        client = self.stack.enter_context(TestClient(fx.client().app, raise_server_exceptions=False))
        calls_before = list(fx.cron.calls)
        with patch.object(fx.schedules, "_cron", side_effect=ImportError("native adapter unavailable")):
            response = client.post(f"/spaces/{sid}/grants/refresh", json={"decision": "revoke"})
        self.assertEqual(fx.refresh_grant(sid)["status"], "revoked")
        self.assertTrue(fx.cron.jobs[jid]["enabled"])
        self.assertEqual(fx.cron.calls, calls_before)
        interruptions = []
        pause, remove = fx.cron.pause_job, fx.cron.remove_job

        def observe_interruption(native_call, job_id, *args, **kwargs):
            result = native_call(job_id, *args, **kwargs)
            if job_id == jid:
                interruptions.append((fx.refresh_grant(sid)["status"],
                                      copy.deepcopy(fx.cron.jobs.get(jid))))
            return result

        with patch.object(fx.cron, "pause_job",
                          side_effect=lambda *args, **kwargs: observe_interruption(pause, *args, **kwargs)), \
                patch.object(fx.cron, "remove_job",
                             side_effect=lambda *args, **kwargs: observe_interruption(remove, *args, **kwargs)):
            granted = fx.approve_refresh(sid)
        with self.subTest(boundary="revoke returns success"):
            self.assertEqual(response.status_code, 200, response.text)
        with self.subTest(boundary="restored adapter permits safe regrant"):
            self.assertEqual(granted["status"], "granted")
            self.assertEqual(fx.refresh_grant(sid)["status"], "granted")
        with self.subTest(boundary="native interruption precedes durable grant"):
            self.assertTrue(interruptions, "Regrant must resolve the enabled native job")
            status, job = interruptions[0]
            self.assertEqual(status, "revoked")
            if job is not None:
                self.assertFalse(job["enabled"])
                self.assertEqual(job["state"], "paused")
        with self.subTest(boundary="native job cannot remain enabled"):
            job = fx.cron.jobs.get(jid)
            if job is not None:
                self.assertFalse(job["enabled"])
                self.assertEqual(job["state"], "paused")
            self.assertTrue(any(call[0] in ("pause", "remove") and call[1] == jid
                                for call in fx.cron.calls[len(calls_before):]))
        with self.subTest(boundary="regrant does not resume or create"):
            self.assertEqual([call for call in fx.cron.calls[len(calls_before):]
                              if call[0] in ("create", "resume", "trigger")], [])
        with self.subTest(boundary="schedule awaits explicit approval or Resume"):
            with fx.db.read() as conn:
                stored = dict(conn.execute(
                    "SELECT * FROM schedules WHERE space=?", (sid,)).fetchone())
            self.assertIn(stored["status"], ("disabled", "paused", "requested"))
            self.assertIsNone(stored["next_run_at"])
            self.assertIn(fx.schedules.get_schedule(sid)["status"],
                          ("disabled", "paused", "requested"))

    def test_r02_unavailable_adapter_keeps_refresh_regrant_fail_closed(self):
        from fastapi.testclient import TestClient

        fx = self.fx
        sid = fx.make()
        fx.approve_schedule(sid)
        client = self.stack.enter_context(TestClient(fx.client().app, raise_server_exceptions=False))
        jobs_before = copy.deepcopy(fx.cron.jobs)
        calls_before = list(fx.cron.calls)
        with patch.object(fx.schedules, "_cron", side_effect=ImportError("native adapter unavailable")):
            response = client.post(f"/spaces/{sid}/grants/refresh", json={"decision": "revoke"})
            self.assertEqual(fx.refresh_grant(sid)["status"], "revoked")
            with self.subTest(boundary="typed refusal while interruption is unavailable"):
                with self.assertRaises(fx.core.SpacesError):
                    fx.approve_refresh(sid)
            with self.subTest(boundary="Refresh stays revoked"):
                self.assertEqual(fx.refresh_grant(sid)["status"], "revoked")
            with self.subTest(boundary="revoke succeeds despite unavailable adapter"):
                self.assertEqual(response.status_code, 200, response.text)
            with self.subTest(boundary="inactive schedule retains visible unavailable reason"):
                with fx.db.read() as conn:
                    stored = dict(conn.execute(
                        "SELECT * FROM schedules WHERE space=?", (sid,)).fetchone())
                self.assertIn(stored["status"], ("disabled", "paused", "requested"))
                self.assertIsNone(stored["next_run_at"])
                self.assertIn("unavailable",
                              (fx.schedules._schedule_row(sid).get("reason") or "").lower())
            with self.subTest(boundary="no fabricated native interruption or restart"):
                self.assertEqual(fx.cron.jobs, jobs_before)
                self.assertEqual(fx.cron.calls, calls_before)

    def test_r02_unavailable_adapter_preserves_pending_run_uncertainty_and_gates_regrant(self):
        from fastapi.testclient import TestClient

        fx = self.fx
        client = self.stack.enter_context(TestClient(fx.client().app, raise_server_exceptions=False))
        for native_status, local_status in (("claimed", "queued"), ("running", "running")):
            with self.subTest(native_status=native_status):
                sid = fx.make()
                jid = fx.approve_schedule(sid)["cron_job_id"]
                execution = fx.cron.execution(jid, native_status)
                pending = fx.runs.list_runs(sid)
                self.assertEqual(len(pending), 1)
                self.assertEqual(pending[0]["status"], local_status)
                self.assertEqual(pending[0]["detail"]["cron_run_id"], execution["id"])
                rid = pending[0]["id"]
                jobs_before = copy.deepcopy(fx.cron.jobs)
                executions_before = copy.deepcopy(fx.cron.executions)
                calls_before = list(fx.cron.calls)
                with patch.object(fx.schedules, "_cron", side_effect=ImportError("native adapter unavailable")):
                    response = client.post(f"/spaces/{sid}/grants/refresh", json={"decision": "revoke"})
                    with fx.db.read() as conn:
                        stored = dict(conn.execute(
                            "SELECT * FROM schedules WHERE space=?", (sid,)).fetchone())
                        run = dict(conn.execute("SELECT * FROM runs WHERE id=?", (rid,)).fetchone())
                    visible = fx.schedules._schedule_row(sid)
                    with self.subTest(boundary="revoke persists and returns successfully"):
                        self.assertEqual(fx.refresh_grant(sid)["status"], "revoked")
                        self.assertEqual(response.status_code, 200, response.text)
                        self.assertEqual(response.json()["status"], "revoked")
                    with self.subTest(boundary="inactive schedule without a getter repair"):
                        self.assertIn(stored["status"], ("disabled", "paused", "requested"))
                        self.assertIsNone(stored["next_run_at"])
                    with self.subTest(boundary="pending work is not falsely canceled"):
                        self.assertIn(run["status"], ("queued", "running", "failed", "blocked"))
                        self.assertEqual(json.loads(run["detail"])["cron_run_id"], execution["id"])
                    with self.subTest(boundary="interruption failure or uncertainty is visible"):
                        detail = json.dumps({"error": run["error"], "detail": json.loads(run["detail"]),
                                             "reason": visible.get("reason")}).lower()
                        self.assertRegex(detail, r"unavailable|unconfirmed|uncertain|cannot|could not|failed")
                    with self.subTest(boundary="regrant is a typed refusal"):
                        with self.assertRaises(fx.core.SpacesError):
                            fx.approve_refresh(sid)
                    with self.subTest(boundary="Refresh remains revoked"):
                        self.assertEqual(fx.refresh_grant(sid)["status"], "revoked")
                    with self.subTest(boundary="native leaves report no successful interruption"):
                        self.assertEqual(fx.cron.jobs, jobs_before)
                        self.assertEqual(fx.cron.executions, executions_before)
                        self.assertEqual(fx.cron.calls, calls_before)

    def test_r02_working_adapter_revoke_and_regrant_preserve_unrelated_state_control(self):
        fx = self.fx
        sid = fx.make()
        jid = fx.approve_schedule(sid)["cron_job_id"]
        completed = fx.cron.execution(jid, "completed")
        running = fx.cron.execution(jid)
        history_before = {run["detail"]["cron_run_id"]: run for run in fx.runs.list_runs(sid)}
        other_sid = fx.make()
        other_jid = fx.approve_schedule(other_sid)["cron_job_id"]
        other_execution = fx.cron.execution(other_jid)
        other_history = fx.runs.list_runs(other_sid)
        other_schedule = fx.schedules.get_schedule(other_sid)
        other_grant = fx.refresh_grant(other_sid)
        other_job = copy.deepcopy(fx.cron.jobs[other_jid])
        other_native_run = copy.deepcopy(other_execution)
        user_record = fx.records.put(
            sid, "items", "keep", {"notes": "Existing user data"}, actor="user")
        call_start = len(fx.cron.calls)
        response = fx.client().post(f"/spaces/{sid}/grants/refresh", json={"decision": "revoke"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "revoked")
        self.assertEqual(fx.refresh_grant(sid)["status"], "revoked")
        self.assertEqual(fx.schedules.get_schedule(sid)["status"], "paused")
        self.assertFalse(fx.cron.jobs[jid]["enabled"])
        self.assertEqual(fx.cron.jobs[jid]["state"], "paused")
        self.assertEqual(running["status"], "cancelled")
        self.assertIn(("pause", jid), fx.cron.calls[call_start:])
        self.assertIn(("cancel", jid), fx.cron.calls[call_start:])
        history = {run["detail"]["cron_run_id"]: run for run in fx.runs.list_runs(sid)}
        self.assertEqual(history[running["id"]]["status"], "canceled")
        self.assertEqual(history[completed["id"]], history_before[completed["id"]])
        call_regrant = len(fx.cron.calls)
        self.assertEqual(fx.approve_refresh(sid)["status"], "granted")
        self.assertEqual(fx.schedules.get_schedule(sid)["status"], "paused")
        self.assertFalse(fx.cron.jobs[jid]["enabled"])
        self.assertEqual(running["status"], "cancelled")
        self.assertEqual([call for call in fx.cron.calls[call_regrant:]
                          if call[0] in ("create", "resume", "trigger")], [])
        self.assertEqual([call for call in fx.cron.calls[call_start:] if call[0] == "remove"], [])
        self.assertEqual(fx.cron.jobs[other_jid], other_job)
        self.assertEqual(other_execution, other_native_run)
        self.assertEqual(fx.runs.list_runs(other_sid), other_history)
        self.assertEqual(fx.schedules.get_schedule(other_sid), other_schedule)
        self.assertEqual(fx.refresh_grant(other_sid), other_grant)
        self.assertEqual(fx.records.get(sid, "items", "keep"), user_record)
        self.assertIn(completed, fx.cron.executions)
        self.assertIn(running, fx.cron.executions)
        self.assertEqual([call for call in fx.cron.calls[call_start:] if call[1] == other_jid], [])
        fx.schedules.pause_schedule(sid, False, actor="user")
        self.assertTrue(fx.cron.jobs[jid]["enabled"])
        self.assertEqual(fx.schedules.get_schedule(sid)["status"], "active")
```

