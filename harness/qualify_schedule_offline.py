"""Forge-only R1-07 gate using real Desktop input and the isolated gateway ticker.

Forge stops the isolated app with harness/app.py before prepare-offline, then
restarts it before verify-catchup. Run revoke next, and cleanup even on failure.
This harness never starts, stops, or directly ticks a gateway. The public-feed
fixture copies upkeep configuration from research-desk, not its user data.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
import importlib
import json
import os
from pathlib import Path
import sys
import time

def wait(probe, predicate, seconds=30):
    deadline = time.monotonic() + seconds
    value = None
    while time.monotonic() < deadline:
        value = probe()
        if predicate(value):
            return value
        time.sleep(1)
    raise TimeoutError(f"Last observation: {value}")


def press(label, selector="document"):
    from cdp import _page, evaluate

    point = evaluate(f"""(() => {{
      const root = {selector};
      const e = root && [...root.querySelectorAll('button,[role=menuitem],a')]
        .find(e => (e.textContent.trim() === {json.dumps(label)} || e.getAttribute('aria-label') === {json.dumps(label)}) && e.getClientRects().length);
      if (!e) return null;
      e.scrollIntoView({{block:'center'}});
      const r = e.getBoundingClientRect();
      return {{x:r.x+r.width/2, y:r.y+r.height/2, disabled:!!e.disabled}};
    }})()""")
    if not point or point["disabled"]:
        raise AssertionError(f"Missing or disabled host control: {label}")

    async def click(session):
        await session.call("Page.bringToFront")
        await session.call("Emulation.setFocusEmulationEnabled", enabled=True)
        for kind in ("mousePressed", "mouseReleased"):
            await session.call("Input.dispatchMouseEvent", type=kind, x=point["x"], y=point["y"],
                               button="left", clickCount=1)
    asyncio.run(_page(click))


class Visible:
    """Keep polling active while the isolated Desktop window is occluded."""

    def __enter__(self):
        import threading
        import websockets
        from cdp import Session, page_ws

        self.stop, ready = threading.Event(), threading.Event()
        self.error = None

        async def hold():
            try:
                async with websockets.connect(page_ws(), max_size=64 << 20) as socket:
                    await Session(socket).call("Emulation.setFocusEmulationEnabled", enabled=True)
                    ready.set()
                    while not self.stop.is_set():
                        try:
                            await asyncio.wait_for(socket.recv(), .5)
                        except asyncio.TimeoutError:
                            pass
            except Exception as exc:
                self.error = exc
                ready.set()

        self.thread = threading.Thread(target=lambda: asyncio.run(hold()), daemon=True)
        self.thread.start()
        if not ready.wait(10) or self.error:
            self.stop.set()
            raise RuntimeError("Desktop focus emulation failed") from self.error
        return self

    def __exit__(self, *exc):
        self.stop.set()
        self.thread.join(5)
        if self.error and exc[0] is None:
            raise self.error


class Qualification:
    def __init__(self, args):
        self.args = args
        self.root = Path(args.run_root).resolve()
        self.home = self.root / "home"
        live = (Path.home() / ".hermes").resolve()
        if self.root == live or self.root.is_relative_to(live) or self.home.resolve().is_relative_to(live):
            raise SystemExit("Refusing a live Hermes profile")
        if not (self.home / "config.yaml").is_file():
            raise SystemExit("Prepare the isolated app with harness/app.py first")
        os.environ["HERMES_HOME"] = str(self.home)
        os.environ["LIVING_SPACES_DB"] = str(self.home / "plugin-data/living-spaces/spaces.db")
        sys.path.insert(0, str(Path.home() / ".hermes/hermes-agent"))
        package = (self.home / "plugins/living-spaces").resolve()
        if not (package / "_core.py").is_file():
            raise SystemExit("Isolated plugin installation is missing")
        sys.path.insert(0, str(package))
        import _core
        from cron import jobs
        from gateway.status import get_running_pid, is_gateway_runtime_lock_active

        self.core, self.cron = _core.load_core(), jobs
        self.schedules = importlib.import_module(self.core.__name__ + ".schedules")
        self.running_pid = lambda: get_running_pid(self.home / "gateway.pid", cleanup_stale=False)
        self.lock_active = lambda: is_gateway_runtime_lock_active(self.home / "gateway.lock")
        self.out = self.root / "evidence/schedule-offline"
        self.out.mkdir(parents=True, exist_ok=True)
        self.state_file = self.out / "state.json"
        self.state = json.loads(self.state_file.read_text()) if self.state_file.exists() else {}
        self.checks = []
        self.result = {"step": args.step, "evidence_class": "real Desktop, native input, isolated gateway ticker, SQLite and cron store"}

    def save(self):
        self.state_file.write_text(json.dumps(self.state, indent=2))

    def check(self, name, observed, expected=True):
        passed = observed == expected
        self.checks.append({"name": name, "passed": passed, "observed": observed, "expected": expected})
        print(("PASS " if passed else "FAIL ") + name, flush=True)
        if not passed:
            raise AssertionError(self.checks[-1])

    def scheduled_runs(self):
        return [run for run in self.core.list_runs(self.state["sid"], limit=500) if run["trigger"] == "schedule"]

    def preserved(self):
        for record in self.state["records"]:
            current = self.core.records.get(self.state["sid"], record["collection"], record["id"])
            self.check("User data preserved for " + record["id"], current["data"], record["data"])

    def open_space(self):
        from cdp import evaluate

        evaluate(f'location.hash="/spaces?space={self.state["sid"]}"')
        wait(self.host_text, lambda text: "Refresh now" in text and self.state["name"] in text)

    @staticmethod
    def host_text():
        from cdp import evaluate
        text = evaluate("document.body.innerText")
        if not isinstance(text, str):
            raise AssertionError(text)
        return text

    @staticmethod
    def close_sheet():
        from cdp import evaluate
        if evaluate('document.querySelector("[role=dialog]") !== null'):
            press("Close", 'document.querySelector("[role=dialog]")')
            wait(lambda: evaluate('document.querySelectorAll("[role=dialog]").length'), lambda count: count == 0)

    def prepare_offline(self):
        self.check("Forge stopped the isolated gateway", self.running_pid(), None)
        self.check("Isolated gateway runtime lock is released", self.lock_active(), False)
        self.check("Previous harness resources were cleaned", not self.state or self.state.get("cleaned", False))
        base = self.core.bundle(self.args.source_space)["manifest"]
        upkeep = base.get("upkeep") or {}
        self.check("Public feed fixture has sources", upkeep.get("handler") == "feed" and bool(upkeep.get("sources")))
        fixture = self.core.create_space(
            "Offline Catchup Probe", owner="harness", author="harness-fixture",
            manifest={"entry": "index.html", "upkeep": upkeep},
            files={"index.html": "<!doctype html><title>Offline Catchup Probe</title><h1>Offline Catchup Probe</h1><p>Public feed schedule qualification. Notes remain in durable records.</p>"},
        )
        self.state = {"sid": fixture["id"], "name": fixture["name"], "records": [], "job_ids": [], "shims": [], "cleaned": False}
        self.save()
        sid = self.state["sid"]
        self.core.decide(sid, "refresh", "grant", actor="harness-fixture")
        for collection in sorted({source["collection"] for source in upkeep["sources"]}):
            source_records = self.core.query(self.args.source_space, collection)["records"]
            record = next((row for row in source_records if row.get("source") and row["source"].get("title")), None)
            self.check("Source fixture has a persisted public record in " + collection, record is not None)
            stale = dict(record["source"], title="Offline fixture title awaiting catch-up")
            self.core.records.upsert_sources(sid, collection, [(record["id"], stale, record["source_meta"])], actor="harness-fixture")
            current = self.core.records.get(sid, collection, record["id"])
            user = {"note": "Keep this public demo note across offline catch-up", "status": "reading"}
            self.core.records.put(sid, collection, record["id"], user, actor="user", base_rev=current["rev"])
            self.state["records"].append({"collection": collection, "id": record["id"], "data": user})
            self.save()
        slot = (datetime.now(timezone.utc) + timedelta(minutes=30)).replace(second=0, microsecond=0)
        self.core.request_schedule(sid, cadence=f"{slot.minute} {slot.hour} * * *", timezone="UTC",
                                   purpose="Public demo offline catch-up qualification", actor="harness-fixture")
        schedule = self.core.decide_schedule(sid, "approve", actor="harness-fixture")
        self.check("Fixture creates an active native schedule", schedule["status"], "active")
        self.state["job_id"] = schedule["cron_job_id"]
        self.state["job_ids"].append(schedule["cron_job_id"])
        self.state["shims"].append(f"living-spaces-refresh-{sid}.py")
        self.save()
        past = (slot - timedelta(days=3)).isoformat()
        self.cron.update_job(schedule["cron_job_id"], {"next_run_at": past, "grace_minutes": 2})
        job = self.cron.get_job(schedule["cron_job_id"])
        self.check("Past slot is beyond the explicit grace window", (datetime.now(timezone.utc) - datetime.fromisoformat(past)).total_seconds() > 120)
        self.check("One-refresh catch-up is enabled", job["catch_up"], True)
        self.state["scheduled_at"] = past
        self.state["before_runs"] = [run["id"] for run in self.scheduled_runs()]
        witness = f"living-spaces-ticker-{sid}.py"
        self.state["shims"].append(witness)
        self.state["witness_name"] = f"living-spaces:{sid}:ticker"
        self.save()
        (self.home / "scripts" / witness).write_text("pass\n")
        job = self.cron.create_job(prompt=None, schedule="* * * * *", name=self.state["witness_name"],
                                   script=witness, no_agent=True, deliver="local", catch_up=True, timezone="UTC")
        self.state["witness_id"] = job["id"]
        self.state["job_ids"].append(job["id"])
        self.state["prepared"] = True
        self.save()
        self.result["fixture"] = self.state
        print("Forge can now restart the isolated app, then run verify-catchup.", flush=True)

    def observe_ticks(self):
        job = self.cron.get_job(self.state["witness_id"])
        initial = job.get("last_run_at")
        stamps = set()
        started = time.monotonic()
        while time.monotonic() - started < 200:
            self.check("Isolated gateway remains live", self.running_pid() is not None)
            witness = self.cron.get_job(self.state["witness_id"])
            stamp = witness.get("last_run_at")
            if stamp and stamp != initial and witness.get("last_status") == "ok":
                stamps.add(stamp)
            if time.monotonic() - started >= 130 and len(stamps) >= 2:
                self.result["ticker_completions"] = sorted(stamps)
                self.result["observation_seconds"] = round(time.monotonic() - started, 1)
                return
            time.sleep(5)
        raise AssertionError(f"Fewer than two successful live ticker witness executions: {stamps}")

    def verify_catchup(self):
        from cdp import screenshot, evaluate

        self.check("Offline preparation completed", self.state.get("prepared", False))
        self.check("Forge restarted the isolated gateway", self.running_pid() is not None)
        known = set(self.state["before_runs"])
        new = lambda: [run for run in self.scheduled_runs() if run["id"] not in known]
        wait(new, lambda rows: rows and all(row["status"] not in ("queued", "running") for row in rows), 240)
        self.observe_ticks()
        rows = new()
        self.check("Exactly one refresh for all missed slots", len(rows), 1)
        run = rows[0]
        self.result["catchup_run"] = run
        self.check("Catch-up refresh succeeds", run["status"], "succeeded")
        dispatch = run["detail"].get("dispatch") or {}
        self.check("Run history records catch-up classification", dispatch.get("kind"), "catch_up")
        self.check("Run history retains the missed slot", dispatch.get("scheduled_at"), self.state["scheduled_at"])
        self.check("Run history retains lateness beyond grace", dispatch.get("lateness_seconds", 0) > 120)
        job = self.cron.get_job(self.state["job_id"])
        self.check("Native job records successful completion", job.get("last_status"), "ok")
        self.check("Native and Space dispatch records agree", job.get("last_dispatch"), dispatch)
        self.check("Next slot is in the future", datetime.fromisoformat(job["next_run_at"]).timestamp() > time.time())
        self.check("Catch-up updated stale source fields", run["changed"]["updated"] >= len(self.state["records"]))
        self.preserved()
        self.state["catchup_run_id"] = run["id"]
        self.save()
        self.open_space()
        self.close_sheet()
        press("History")
        wait(self.host_text, lambda text: "Run history" in text and "Refresh succeeded" in text)
        history = evaluate('document.querySelector("[role=tabpanel]").innerText')
        self.result["history_text"] = history
        screenshot(str(self.out / "catchup-history.png"))
        self.check("Host history identifies this as a catch-up refresh", "catch-up" in history.lower() or "caught up" in history.lower())
        self.check("Host history explains missed or delayed work", "missed" in history.lower() or "delayed" in history.lower())
        self.state["catchup_verified"] = True
        self.save()

    def revoke(self):
        from cdp import evaluate, screenshot

        self.check("Catch-up was observed in canonical history", bool(self.state.get("catchup_run_id")))
        sid = self.state["sid"]
        self.open_space()
        self.close_sheet()
        press("Permissions")
        wait(self.host_text, lambda text: "Host-owned public-source handler" in text and "Revoke" in text)
        selector = "[...document.querySelectorAll('article')].find(a => a.querySelector('strong')?.textContent.trim() === 'Refresh')"
        press("Revoke", selector)
        wait(self.host_text, lambda text: "Revoke Refresh for" in text)
        press("Revoke", 'document.querySelector("[role=alertdialog]")')
        wait(lambda: self.core.get_schedule(sid), lambda schedule: schedule["status"] == "paused")
        schedule = self.core.get_schedule(sid)
        self.result["paused_schedule"] = schedule
        self.check("Schedule explains revoked permission", "revoked" in schedule.get("reason", "").lower())
        job = self.cron.get_job(self.state["job_id"])
        self.check("Host revoke pauses native cron", [job["state"], job["enabled"]], ["paused", False])
        self.check("Paused schedule has no eligible run", schedule["next_run_at"], None)
        known = [run["id"] for run in self.scheduled_runs()]
        self.cron.update_job(job["id"], {"next_run_at": self.state["scheduled_at"]})
        self.observe_ticks()
        self.check("Revoked schedule creates no runs across two live ticker intervals", [run["id"] for run in self.scheduled_runs()], known)
        self.preserved()
        self.close_sheet()
        self.open_space()
        press("More Space actions")
        press("Schedule")
        wait(self.host_text, lambda text: "Schedule, cost and missed-run policy" in text)
        text = evaluate('document.querySelector("[role=dialog]").innerText')
        self.result["schedule_text"] = text
        screenshot(str(self.out / "revoked-schedule.png"))
        self.check("Host schedule says why upkeep stopped", "revoked" in text.lower() and "refresh" in text.lower())
        self.check("Host explains deliberate recovery", "resume" in text.lower() and "approv" in text.lower())
        self.state["revoke_verified"] = True
        self.save()

    def cleanup(self):
        if not self.state:
            self.check("No harness resources were created", True)
            return
        sid = self.state["sid"]
        names = {f"living-spaces:{sid}", self.state.get("witness_name")}
        self.schedules.remove_schedule(sid)
        for job in self.cron.load_jobs():
            if job["id"] in self.state["job_ids"] or job.get("name") in names:
                self.cron.remove_job(job["id"])
        for shim in self.state["shims"]:
            (self.home / "scripts" / shim).unlink(missing_ok=True)
        jobs = self.cron.load_jobs()
        self.check("No created living-spaces job remains in cron/jobs.json",
                   [job["id"] for job in jobs if job["id"] in self.state["job_ids"] or job.get("name") in names], [])
        self.check("Every created shim is deleted", [name for name in self.state["shims"] if (self.home / "scripts" / name).exists()], [])
        self.check("Fixture schedule removed", self.core.get_schedule(sid), None)
        self.preserved()
        self.result["remaining_living_spaces_jobs"] = [job["id"] for job in jobs if job.get("name", "").startswith("living-spaces:")]
        self.state["cleaned"] = True
        self.save()

    def run(self):
        try:
            with self.cron.use_cron_store(self.home):
                action = getattr(self, self.args.step.replace("-", "_"))
                if self.args.step in ("verify-catchup", "revoke"):
                    with Visible():
                        action()
                else:
                    action()
        except BaseException as exc:
            self.result["error"] = str(exc)
            raise
        finally:
            self.result.update(checks=self.checks, passed=sum(check["passed"] for check in self.checks), total=len(self.checks))
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            (self.out / f"{self.args.step}-{stamp}.json").write_text(json.dumps(self.result, indent=2, default=str))
            print(json.dumps({key: self.result[key] for key in ("passed", "total")}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=("prepare-offline", "verify-catchup", "revoke", "cleanup"))
    parser.add_argument("--run-root", default=os.environ.get("LS_RUN_ROOT", "/Volumes/Expansion/Development/Build/living-spaces-r1"))
    parser.add_argument("--source-space", default="research-desk")
    Qualification(parser.parse_args()).run()
