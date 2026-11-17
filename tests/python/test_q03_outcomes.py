import importlib.util
import json
import sqlite3
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from .test_core_store import CoreCase, ROOT
from .test_net import Response
from living_spaces_core import bridge, db, grants, net, records, sessions


class CommitCleanupFault:
    def __init__(self, connection, fault, injected):
        self.connection = connection
        self.fault = fault
        self.injected = injected
        self.mutated = False

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def execute(self, sql, *args):
        result = self.connection.execute(sql, *args)
        self.mutated |= self.connection.total_changes > 0
        if sql.strip().upper() == "COMMIT" and self.mutated and self.fault == "commit":
            self.injected.append("after real commit")
            raise sqlite3.OperationalError("Q03 injected exception after real COMMIT")
        return result

    def close(self):
        self.connection.close()
        if self.mutated and self.fault == "close":
            self.injected.append("after real close")
            raise sqlite3.OperationalError("Q03 injected exception after real close")


class Q03OutcomeTests(CoreCase):
    def setUp(self):
        super().setUp()
        self.session = sessions.open_session(self.sid)["session"]

    def put_args(self, rid, note="Q03 public draft", base_rev=0):
        return {"collection": "papers", "id": rid, "data": {"note": note}, "base_rev": base_rev}

    def dispatch(self, op, args, session=None):
        return bridge.dispatch(self.sid, session or self.session, op, args)

    def http_client(self):
        path = ROOT / "src/living-spaces/dashboard/plugin_api.py"
        spec = importlib.util.spec_from_file_location("q03_outcomes_api", path)
        assert spec is not None and spec.loader is not None
        api = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(api)
        app = FastAPI()
        app.include_router(api.router)
        client = TestClient(app)
        self.addCleanup(client.close)
        return client

    def http_bridge(self, client, op, args, request_id=None):
        body = {"session": self.session, "op": op, "args": args}
        if request_id is not None:
            body["request_id"] = request_id
        response = client.post(f"/spaces/{self.sid}/bridge", json=body)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def net_post(self, *, response_failure=False, audit_failure=False, url="https://probe.invalid/send"):
        connection = Mock()
        connection.getresponse.return_value = Response(b"Q03 public response")
        if response_failure:
            connection.getresponse.side_effect = OSError("Q03 response lost after send")
        original_audit = grants._audit
        audit_faults = []

        def audit(conn, sid, actor, action, capability, outcome, detail=None):
            if audit_failure and action == "net.fetch":
                audit_faults.append(action)
                raise sqlite3.OperationalError("Q03 final net audit unavailable")
            return original_audit(conn, sid, actor, action, capability, outcome, detail)

        with patch.object(net, "_resolve", return_value=["93.184.216.34"]), \
                patch.object(net, "_connection", return_value=connection), \
                patch.object(grants, "_audit", side_effect=audit):
            reply = self.dispatch("net.fetch", {"url": url, "method": "POST", "body": "Q03 synthetic body"})
        return reply, connection.request.call_args_list, audit_faults

    def assert_net_control(self):
        reply, sends, faults = self.net_post()
        self.assertEqual(len(sends), 1)
        self.assertEqual(faults, [])
        self.assertTrue(reply["ok"], reply)
        self.assertEqual(reply["result"]["text"], "Q03 public response")

    def test_http_legacy_success_and_conflict_envelopes_control(self):
        client = self.http_client()
        args = self.put_args("legacy")
        saved = self.http_bridge(client, "data.put", args)
        self.assertTrue(saved["ok"], saved)
        self.assertNotIn("error", saved)
        self.assertEqual(saved["result"]["data"], args["data"])
        current = self.http_bridge(client, "data.get", {"collection": "papers", "id": "legacy"})
        self.assertEqual(current["result"], saved["result"])
        conflict = self.http_bridge(client, "data.put", args)
        self.assertFalse(conflict["ok"], conflict)
        self.assertNotIn("result", conflict)
        self.assertEqual(conflict["error"]["code"], "conflict")
        self.assertEqual(conflict["error"]["current"], saved["result"])
        self.assertEqual(records.get(self.sid, "papers", "legacy"), saved["result"])

    def test_http_outcome_metadata_distinguishes_success_and_rejection(self):
        client = self.http_client()
        args = self.put_args("typed")
        saved = self.http_bridge(client, "data.put", args, request_id="q03-typed-save")
        conflict = self.http_bridge(client, "data.put", args, request_id="q03-typed-conflict")
        self.assertTrue(saved["ok"], saved)
        self.assertEqual(records.get(self.sid, "papers", "typed")["data"], args["data"])
        self.assertFalse(conflict["ok"], conflict)
        self.assertEqual(conflict["error"]["code"], "conflict")
        for label, reply in (("success", saved), ("rejected", conflict)):
            with self.subTest(status=label):
                self.assertEqual(reply.get("outcome", {}).get("status"), label, reply)

    def test_allowed_read_survives_real_sqlite_writer(self):
        self.put()
        args = {"collection": "papers"}
        control = self.dispatch("data.query", args)
        self.assertTrue(control["ok"], control)
        original_connect = db.connect

        def short_connect():
            conn = original_connect()
            conn.execute("PRAGMA busy_timeout=25")
            return conn

        holder = original_connect()
        holder.execute("BEGIN IMMEDIATE")
        try:
            with patch.object(db, "connect", side_effect=short_connect):
                self.assertEqual(records.query(self.sid, "papers")["total"], 1)
                reply = self.dispatch("data.query", args)
        finally:
            holder.execute("ROLLBACK")
            holder.close()
        self.assertTrue(reply["ok"], reply)
        self.assertEqual(reply["result"], control["result"])

    def test_contended_write_is_busy_and_does_not_mutate(self):
        control = self.dispatch("data.put", self.put_args("uncontended"))
        self.assertTrue(control["ok"], control)
        before = self.counts()
        original_connect = db.connect

        def short_connect():
            conn = original_connect()
            conn.execute("PRAGMA busy_timeout=25")
            return conn

        holder = original_connect()
        holder.execute("BEGIN IMMEDIATE")
        try:
            with patch.object(db, "connect", side_effect=short_connect):
                reply = self.dispatch("data.put", self.put_args("contended"))
        finally:
            holder.execute("ROLLBACK")
            holder.close()
        self.assertEqual(self.counts(), before)
        self.error("not_found", records.get, self.sid, "papers", "contended")
        self.assertFalse(reply["ok"], reply)
        self.assertEqual(reply.get("outcome", {}).get("status"), "busy", reply)

    def test_committed_write_cleanup_fault_never_claims_rejection(self):
        original_connect = db.connect
        for fault in ("commit", "close"):
            with self.subTest(fault=fault):
                control = self.dispatch("data.put", self.put_args("control_" + fault))
                self.assertTrue(control["ok"], control)
                rid = "fault_" + fault
                args = self.put_args(rid)
                injected = []

                def connect():
                    return CommitCleanupFault(original_connect(), fault, injected)

                with patch.object(db, "connect", side_effect=connect):
                    reply = self.dispatch("data.put", args)
                saved = records.get(self.sid, "papers", rid)
                self.assertEqual(saved["data"], args["data"])
                self.assertEqual(saved["rev"], 1)
                changes = records.changes_since(self.sid, 0)["changes"]
                self.assertEqual(len([row for row in changes if row["id"] == rid]), 1)
                self.assertEqual(len(injected), 1, "The real committed mutation must reach the injected fault")
                status = reply.get("outcome", {}).get("status")
                self.assertIn(status, {"unknown", "success"}, reply)
                if status == "success":
                    self.assertTrue(reply["ok"], reply)
                    self.assertEqual(reply["result"], saved)
                else:
                    self.assertFalse(reply["ok"], reply)
                    self.assertNotIn("result", reply)

    def test_conflict_payload_requires_current_delivery_authority(self):
        marker = "Q03_PRIVATE_CURRENT"
        original = self.put(data={"note": marker})
        args = self.put_args("paper", note="stale draft")
        original_call = bridge._call
        for boundary in ("grant", "session"):
            with self.subTest(boundary=boundary):
                grants.decide(self.sid, "data", "grant")
                session = sessions.open_session(self.sid)["session"]
                control = self.dispatch("data.put", args, session)
                self.assertEqual(control["error"]["code"], "conflict")
                self.assertEqual(control["error"]["current"], original)

                def lose_authority(*call_args, **kwargs):
                    try:
                        return original_call(*call_args, **kwargs)
                    finally:
                        if boundary == "grant":
                            grants.decide(self.sid, "data", "revoke")
                        else:
                            sessions.close_session(session)

                with patch.object(bridge, "_call", side_effect=lose_authority) as reached:
                    reply = self.dispatch("data.put", args, session)
                self.assertEqual(reached.call_count, 1)
                self.assertEqual(records.get(self.sid, "papers", "paper"), original)
                if boundary == "grant":
                    self.error("not_granted", grants.check, self.sid, "data")
                else:
                    self.error("session_invalid", sessions.require, self.sid, session)
                self.assertFalse(reply["ok"], reply)
                self.assertNotIn("result", reply)
                self.assertNotIn("current", reply.get("error", {}), reply)
                self.assertNotIn(marker, json.dumps(reply))

    def test_committed_write_losing_delivery_authority_is_sanitized_unknown(self):
        original_call = bridge._call
        for boundary in ("grant", "session"):
            with self.subTest(boundary=boundary):
                grants.decide(self.sid, "data", "grant")
                session = sessions.open_session(self.sid)["session"]
                control = self.dispatch("data.put", self.put_args("delivery_control_" + boundary), session)
                self.assertTrue(control["ok"], control)
                rid = "delivery_" + boundary
                args = self.put_args(rid, note="Q03_PRIVATE_COMMITTED")

                def lose_authority(*call_args, **kwargs):
                    result = original_call(*call_args, **kwargs)
                    if boundary == "grant":
                        grants.decide(self.sid, "data", "revoke")
                    else:
                        sessions.close_session(session)
                    return result

                with patch.object(bridge, "_call", side_effect=lose_authority) as reached:
                    reply = self.dispatch("data.put", args, session)
                self.assertEqual(reached.call_count, 1)
                self.assertEqual(records.get(self.sid, "papers", rid)["data"], args["data"])
                self.assertFalse(reply["ok"], reply)
                self.assertNotIn("result", reply)
                self.assertNotIn("Q03_PRIVATE_COMMITTED", json.dumps(reply))
                self.assertEqual(reply.get("outcome", {}).get("status"), "unknown", reply)

    def test_pre_effect_authority_loss_preserves_records_control(self):
        original_call = bridge._call
        for boundary, code in (("grant", "not_granted"), ("session", "session_invalid")):
            with self.subTest(boundary=boundary):
                grants.decide(self.sid, "data", "grant")
                session = sessions.open_session(self.sid)["session"]
                control = self.dispatch("data.put", self.put_args("admitted_" + boundary), session)
                self.assertTrue(control["ok"], control)
                before = self.counts()

                def lose_authority(*call_args, **kwargs):
                    if boundary == "grant":
                        grants.decide(self.sid, "data", "revoke")
                    else:
                        sessions.close_session(session)
                    return original_call(*call_args, **kwargs)

                with patch.object(bridge, "_call", side_effect=lose_authority) as reached:
                    reply = self.dispatch("data.put", self.put_args("refused_" + boundary), session)
                self.assertEqual(reached.call_count, 1)
                self.assertFalse(reply["ok"], reply)
                self.assertEqual(reply["error"]["code"], code)
                self.assertEqual(self.counts(), before)
                self.error("not_found", records.get, self.sid, "papers", "refused_" + boundary)

    def test_net_post_send_audit_failure_is_unknown_one_send(self):
        self.assert_net_control()
        reply, sends, faults = self.net_post(audit_failure=True)
        self.assertEqual(len(sends), 1)
        self.assertEqual(sends[0].args[0], "POST")
        self.assertEqual(sends[0].kwargs["body"], b"Q03 synthetic body")
        self.assertEqual(faults, ["net.fetch"])
        self.assertFalse(reply["ok"], reply)
        self.assertNotIn("result", reply)
        self.assertEqual(reply.get("outcome", {}).get("status"), "unknown", reply)

    def test_net_post_send_response_failure_is_unknown_one_send(self):
        self.assert_net_control()
        for audit_failure in (False, True):
            with self.subTest(audit_failure=audit_failure):
                reply, sends, faults = self.net_post(response_failure=True, audit_failure=audit_failure)
                self.assertEqual(len(sends), 1)
                self.assertEqual(faults, ["net.fetch"] if audit_failure else [])
                self.assertFalse(reply["ok"], reply)
                self.assertNotIn("result", reply)
                self.assertEqual(reply.get("outcome", {}).get("status"), "unknown", reply)

    def test_net_pre_send_rejection_never_sends_control(self):
        self.assert_net_control()
        for boundary, code in (("destination", "blocked"), ("grant", "not_granted")):
            with self.subTest(boundary=boundary):
                url = "https://127.0.0.1/send" if boundary == "destination" else "https://probe.invalid/send"
                if boundary == "grant":
                    grants.decide(self.sid, "net", "revoke")
                reply, sends, faults = self.net_post(url=url)
                self.assertFalse(reply["ok"], reply)
                self.assertEqual(reply["error"]["code"], code)
                self.assertEqual(sends, [])
                self.assertEqual(faults, [])
        self.assertTrue(any(row["action"] == "check" and row["outcome"] == "denied"
                            for row in grants.audit_log(self.sid)))

    def test_missing_receipt_does_not_confirm_equal_record_or_absence(self):
        client = self.http_client()
        current = self.put(data={"note": "same as an uncertain draft"})
        control = self.dispatch("data.get", {"collection": "papers", "id": "paper"})
        self.assertEqual(control["result"], current)
        self.error("not_found", records.get, self.sid, "papers", "already_absent")
        before = self.counts()
        for request_id in ("q03-unseen-put", "q03-unseen-delete"):
            with self.subTest(request_id=request_id):
                reply = self.http_bridge(client, "outcome.get", {"request_id": request_id})
                self.assertEqual(self.counts(), before)
                self.assertEqual(records.get(self.sid, "papers", "paper"), current)
                self.assertEqual(reply.get("outcome", {}).get("status"), "unknown", reply)
